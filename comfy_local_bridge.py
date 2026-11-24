"""Local-only viewer for an existing ComfyUI VM through Colab's authenticated SDK.

No public tunnel, no credential files, no VM allocation. The official
ComfyUI frontend, with its optional Sentry reporter disabled, is served locally
with ETag caching; read-only metadata and /view
previews are cached locally to avoid serial Jupyter kernel bottlenecks.
"""
import argparse, asyncio, base64, hashlib, json, os, threading, time, zipfile
from pathlib import Path
from aiohttp import web, WSMsgType
from colab_cli.common import State
from colab_cli.runtime import ColabRuntime
from comfy_frontend_policy import POLICY_REVISION, apply_local_policy

parser = argparse.ArgumentParser()
parser.add_argument('--endpoint', required=True)
parser.add_argument('--port', type=int, default=8767)
parser.add_argument('--frontend', default=str(Path(__file__).resolve().parent / 'vendor/comfy_frontend.zip'))
args = parser.parse_args()

cache_root = Path(os.environ.get('GC_LABS_CACHE', '/tmp'))
static = cache_root / 'comfy_frontend'
view_cache = cache_root / 'view_cache'
static.mkdir(parents=True, exist_ok=True)
view_cache.mkdir(parents=True, exist_ok=True)

marker = static / '.extracted_sha256'
archive_sha = hashlib.sha256(Path(args.frontend).read_bytes() + POLICY_REVISION.encode()).hexdigest()
if not marker.exists() or marker.read_text().strip() != archive_sha:
    with zipfile.ZipFile(args.frontend) as z:
        for n in z.namelist():
            if not (static / n).resolve().is_relative_to(static.resolve()):
                raise ValueError('Unsafe archive path')
        modified = []
        for entry in z.infolist():
            if entry.is_dir():
                (static / entry.filename).mkdir(parents=True, exist_ok=True)
                continue
            payload, changed = apply_local_policy(entry.filename, z.read(entry))
            target = static / entry.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            if changed:
                modified.append(entry.filename)
        if len(modified) != 1:
            raise ValueError('Expected one reviewed frontend Sentry configuration; refusing unknown build.')
    marker.write_text(archive_sha)


class Remote:
    META_PATHS = {'/object_info', '/embeddings', '/extensions', '/models'}

    def __init__(self):
        s = State()
        a = next(a for a in s.client.list_assignments() if a.endpoint == args.endpoint)
        self.runtime = ColabRuntime(a.runtime_proxy_info.url, a.runtime_proxy_info.token)
        self.lock = threading.Lock()
        self.meta_cache = {}
        self.meta_lock = threading.Lock()
        self.run("import requests,base64,json,threading,collections,time,websocket\n__jasper_channels={}")

    def run(self, code):
        with self.lock:
            outputs = self.runtime.execute_code(code, timeout=150)
        text = ''.join(str(x.get('text', '')) for x in outputs if x.get('output_type') == 'stream')
        errors = [x for x in outputs if x.get('output_type') == 'error']
        if errors:
            raise RuntimeError(errors[0].get('ename', 'RemoteError'))
        result = [x[11:] for x in text.splitlines() if x.startswith('JASPER_RPC: ')]
        return json.loads(result[-1]) if result else None

    def _prune_view_cache(self, limit_files=160):
        files = sorted(view_cache.glob('*.bin'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[limit_files:]:
            old.unlink(missing_ok=True)
            old.with_suffix('.meta.json').unlink(missing_ok=True)

    def http(self, method, path, headers, body):
        cache_key = path[4:] if path.startswith('/api/') else path
        bare = cache_key.split('?', 1)[0]
        metadata = bare in self.META_PATHS or bare == '/global_subgraphs' or bare.startswith('/global_subgraphs/')
        if method == 'GET' and metadata and 'refresh=1' not in path:
            with self.meta_lock:
                cached = self.meta_cache.get(cache_key)
                if cached and time.time() - cached[0] < 60:
                    return cached[1]

        if method == 'GET' and bare == '/view':
            key = hashlib.sha256((args.endpoint + '\0' + path).encode('utf-8')).hexdigest()[:32]
            bin_file = view_cache / f'{key}.bin'
            meta_file = view_cache / f'{key}.meta.json'
            if bin_file.is_file() and meta_file.is_file() and 'Range' not in headers and 'range' not in headers:
                meta = json.loads(meta_file.read_text())
                return {'status': 200, 'headers': meta['headers'], 'raw_body': bin_file.read_bytes()}

        payload = json.dumps({'method': method, 'path': path, 'headers': headers, 'body': base64.b64encode(body).decode()})
        # The frontend eagerly requests every blueprint missing `data`. Sending
        # each through a separate, serialized Jupyter execution causes a long
        # startup queue. Read the bodies on the VM in one bounded RPC instead.
        hydrate = method == 'GET' and bare == '/global_subgraphs'
        res = self.run(
            "_p=json.loads(" + repr(payload) + ")\n"
            "_r=requests.request(_p['method'],'http://127.0.0.1:8188'+_p['path'],headers=_p['headers'],data=base64.b64decode(_p['body']),timeout=120)\n"
            "_body=_r.content\n"
            + (self.blueprint_batch_code() if hydrate else '') +
            "print('JASPER_RPC: '+json.dumps({'status':_r.status_code,'headers':{k:v for k,v in _r.headers.items() if k.lower() in ('content-type','content-disposition','content-range','accept-ranges')},'body':base64.b64encode(_body).decode()}))"
        )
        raw = base64.b64decode(res['body'])
        out = {'status': res['status'], 'headers': res['headers'], 'raw_body': raw}

        if method == 'GET' and res['status'] == 200:
            if metadata:
                with self.meta_lock:
                    if len(self.meta_cache) >= 160:
                        self.meta_cache.pop(next(iter(self.meta_cache)))
                    self.meta_cache[cache_key] = (time.time(), out)
                if bare == '/object_info':
                    try:
                        (cache_root / 'object_info.json').write_bytes(raw)
                    except OSError:
                        pass
            elif bare == '/view' and len(raw) <= 25 * 1024 * 1024 and 'Range' not in headers and 'range' not in headers:
                try:
                    key = hashlib.sha256((args.endpoint + '\0' + path).encode('utf-8')).hexdigest()[:32]
                    (view_cache / f'{key}.bin').write_bytes(raw)
                    (view_cache / f'{key}.meta.json').write_text(json.dumps({'headers': res['headers']}))
                    self._prune_view_cache()
                except OSError:
                    pass
        elif method != 'GET':
            with self.meta_lock:
                self.meta_cache.clear()
        return out

    @staticmethod
    def blueprint_batch_code():
        # Leave failed entries intact: their individual endpoint remains
        # retryable, and ComfyUI still reports genuinely broken blueprints.
        return '''
if _r.status_code == 200:
    try:
        from concurrent.futures import ThreadPoolExecutor
        from urllib.parse import quote
        _catalog = _r.json()
        if isinstance(_catalog, dict):
            def _load_blueprint(item):
                key, entry = item
                if not isinstance(entry, dict) or entry.get('data'):
                    return
                try:
                    result = requests.get('http://127.0.0.1:8188/global_subgraphs/' + quote(key, safe=''), headers=_p['headers'], timeout=8)
                    if result.status_code == 200:
                        detail = result.json()
                        if isinstance(detail, dict) and isinstance(detail.get('data'), str) and detail['data'].strip():
                            entry['data'] = detail['data']
                except Exception:
                    pass
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(_load_blueprint, _catalog.items()))
            _body = json.dumps(_catalog).encode('utf-8')
    except (ValueError, TypeError):
        pass
'''

    def start_ws(self, ident, path):
        code = """
def __jasper_ws_reader(ident,path):
    q=collections.deque(maxlen=256)
    __jasper_channels[ident]={'q':q,'closed':False}
    try:
        ws=websocket.create_connection('ws://127.0.0.1:8188'+path,origin='http://127.0.0.1:8188',timeout=5)
        __jasper_channels[ident]['ws']=ws
        while not __jasper_channels[ident]['closed']:
            try:
                message=ws.recv()
                q.append({'binary':isinstance(message,bytes),'data':base64.b64encode(message).decode() if isinstance(message,bytes) else message})
            except websocket.WebSocketTimeoutException:continue
    except Exception:__jasper_channels[ident]['closed']=True
threading.Thread(target=__jasper_ws_reader,args=(IDENT,PATH),daemon=True).start()
print('JASPER_RPC: true')
""".replace('IDENT', repr(ident)).replace('PATH', repr(path))
        self.run(code)

    def poll_ws(self, ident):
        return self.run(
            "_c=__jasper_channels.get(" + repr(ident) + ",{})\n"
            "_q=_c.get('q',collections.deque())\n"
            "_messages=[]\n"
            "while _q:_messages.append(_q.popleft())\n"
            "print('JASPER_RPC: '+json.dumps({'messages':_messages,'closed':_c.get('closed',False)}))"
        )

    def send_ws(self, ident, message):
        self.run("_w=__jasper_channels.get(" + repr(ident) + ",{}).get('ws')\nif _w:_w.send(" + repr(message) + ")")

    def close_ws(self, ident):
        self.run("_c=__jasper_channels.get(" + repr(ident) + ",{})\n_c['closed']=True\nif _c.get('ws'):_c['ws'].close()")


try:
    remote = Remote()
    if remote.http("GET", "/system_stats", {}, b"")["status"] != 200:
        raise RuntimeError("当前ComfyUI后端未就绪")
except Exception as error:
    # The SDK may retain worker threads after startup fails. Exit this disposable
    # bridge promptly so the parent reports the real failure instead of a timeout.
    print('ComfyUI bridge startup failed: ' + type(error).__name__, flush=True)
    os._exit(1)


def warm_node_metadata():
    # Fetch before the frontend fans out optional blueprint requests. Both modern
    # /api/object_info and legacy /object_info share this local, short-lived cache.
    try:
        remote.http('GET', '/object_info', {}, b'')
    except Exception:
        pass  # Readiness is still decided by actual requests, not this best effort.


threading.Thread(target=warm_node_metadata, daemon=True).start()

allowed = {f'127.0.0.1:{args.port}', f'localhost:{args.port}'}


async def handler(request):
    if request.host not in allowed:
        return web.Response(status=403)
    origin = request.headers.get('Origin')
    if origin and origin not in {f'http://{h}' for h in allowed}:
        return web.Response(status=403)
    if request.path == '/__gc_projects.js' and request.method == 'GET':
        return web.FileResponse(Path(__file__).parent / 'web' / 'comfy-projects.js')
    if request.path == '/__gc_projects' or request.path.startswith('/__gc_projects/'):
        # Browser form posts must originate from this loopback UI.
        if request.method != 'GET' and origin not in {f'http://{h}' for h in allowed}:
            return web.Response(status=403)
        return await project_bridge.handle(request)
    if request.path == '/__gc_health':
        return web.json_response({'endpoint': args.endpoint, 'ready': True})
    if request.path == '/__gc_storyboard.js' and request.method == 'GET':
        return web.FileResponse(Path(__file__).parent / 'web' / 'comfy-handoff.js', headers={'Cache-Control': 'no-store'})
    if request.path.startswith('/__gc_handoff/') and request.method == 'GET':
        import re
        token = request.path.rsplit('/', 1)[-1]
        if not re.fullmatch(r'[0-9a-f]{32}', token):
            return web.Response(status=404)
        record = cache_root / 'comfy-handoffs' / (token + '.json')
        if not record.is_file() or record.is_symlink() or time.time() - record.stat().st_mtime > 24*3600:
            return web.Response(status=410)
        return web.Response(body=record.read_bytes(), content_type='application/json', headers={'Cache-Control': 'no-store'})
    if request.path.startswith('/__gc_handoff/') and request.path.endswith('/transfer') and request.method == 'POST':
        if origin not in {f'http://{h}' for h in allowed}:
            return web.Response(status=403)
        token = request.path.split('/')[-2]
        return await asset_transfer.handle(request, token)
    if request.method in ('GET','HEAD'):
        from comfy_verified_media import find
        preview = find(cache_root,args.endpoint,str(request.rel_url))
        if preview:
            path,mime=preview
            return web.FileResponse(path,headers={'Content-Type':mime,'Cache-Control':'private, no-cache'})
    if request.path == '/ws':
        import uuid
        ident = uuid.uuid4().hex
        await asyncio.to_thread(remote.start_ws, ident, str(request.rel_url))
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)

        async def pump():
            while not ws.closed:
                event = await asyncio.to_thread(remote.poll_ws, ident)
                for item in event.get('messages', []):
                    if item['binary']:
                        await ws.send_bytes(base64.b64decode(item['data']))
                    else:
                        await ws.send_str(item['data'])
                if event.get('closed'):
                    await ws.close()
                    break
                await asyncio.sleep(0.35)

        task = asyncio.create_task(pump())
        try:
            async for message in ws:
                if message.type == WSMsgType.TEXT:
                    await asyncio.to_thread(remote.send_ws, ident, message.data)
        finally:
            task.cancel()
            try:
                await asyncio.to_thread(remote.close_ws, ident)
            except Exception:
                pass
        return ws

    p = (static / ('index.html' if request.path == '/' else request.path.lstrip('/'))).resolve()
    if request.method == 'GET' and p.is_relative_to(static.resolve()) and p.is_file():
        if p.name == 'index.html':
            html = p.read_text().replace('</body>', '<script type="module" src="/__gc_storyboard.js"></script><script type="module" src="/__gc_projects.js"></script></body>')
            return web.Response(text=html, content_type='text/html', headers={'Cache-Control': 'no-store'})
        resp = web.FileResponse(p)
        if p.name != 'index.html':
            resp.headers['Cache-Control'] = 'private, max-age=3600'
        return resp

    headers = {k: v for k, v in request.headers.items() if k.lower() in ('content-type', 'range', 'comfy-user', 'accept')}
    response = await asyncio.to_thread(remote.http, request.method, str(request.rel_url), headers, await request.read())
    return web.Response(status=response['status'], headers=response['headers'], body=response['raw_body'])


from comfy_project_bridge import ProjectBridge
from comfy_asset_transfer import AssetTransfer
project_bridge = ProjectBridge(remote, cache_root.parent / 'comfy-projects', cache_root, args.endpoint)
asset_transfer = AssetTransfer(remote, cache_root, args.endpoint)
app = web.Application(client_max_size=30 * 1024 ** 2)
app.router.add_route('*', '/{tail:.*}', handler)
web.run_app(app, host='127.0.0.1', port=args.port, print=lambda *_: print('ComfyUI local bridge ready: http://127.0.0.1:' + str(args.port), flush=True))
