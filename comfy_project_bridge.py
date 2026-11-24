"""Snapshot transport for an already owned ComfyUI bridge; never allocates a VM."""
import asyncio
import base64
import json
import re
import threading
import uuid
from pathlib import Path
from aiohttp import web
from comfy_project_store import digest, inspect_archive


class ProjectBridge:
    def __init__(self, remote, directory, preview_cache=None, endpoint=None):
        self.remote = remote
        self.preview_cache = preview_cache
        self.endpoint = endpoint
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.directory.chmod(0o700)
        self.lock = threading.Lock()

    def install(self):
        source = Path(__file__).with_name('comfy_project_store.py').read_text()
        self.remote.run("import pathlib,tempfile,shutil,hashlib,base64,json,uuid\n"
                        "__ch_store={}\nexec(" + repr(source) + ",__ch_store)\n"
                        "__ch_drive=pathlib.Path('/content/drive/MyDrive/AI_Workstations/CineHarbor/ComfyProjects')")

    def rpc(self, code):
        result = self.remote.run("try:\n exec(" + repr(code) + ",globals())\n"
            "except ValueError as __ch_e:\n __ch_result={'__snapshot_error':str(__ch_e)}\n"
            "print('JASPER_RPC: '+json.dumps(__ch_result))")
        if isinstance(result, dict) and '__snapshot_error' in result:
            raise ValueError(result['__snapshot_error'])
        return result

    def idle(self):
        self.rpc("__ch_q=requests.get('http://127.0.0.1:8188/queue',timeout=15).json()\n"
                 "assert not __ch_q.get('queue_running') and not __ch_q.get('queue_pending'), 'Finish queued work before saving or restoring'\n"
                 "__ch_result=True")

    def local_path(self, ident):
        if not re.fullmatch('[a-f0-9]{32}', ident):
            raise ValueError('Invalid snapshot ID')
        return self.directory / (ident + '.zip')

    def download(self, ident, remote_path):
        path = self.local_path(ident)
        info = self.rpc("__ch_p=pathlib.Path(" + repr(remote_path) + ")\n"
                        "__ch_result={'bytes':__ch_p.stat().st_size,'sha256':__ch_store['digest'](__ch_p)}")
        pending = path.with_suffix('.partial')
        try:
            with pending.open('wb') as f:
                for offset in range(0, info['bytes'], 4 * 1024 * 1024):
                    data = self.rpc("with __ch_p.open('rb') as __ch_f:\n __ch_f.seek(" + str(offset) + ")\n __ch_result=base64.b64encode(__ch_f.read(4194304)).decode()")
                    f.write(base64.b64decode(data, validate=True))
            if pending.stat().st_size != info['bytes'] or digest(pending) != info['sha256']:
                raise ValueError('Local snapshot transfer checksum mismatch')
            manifest, _ = inspect_archive(pending)
            pending.replace(path)
            path.with_suffix('.json').write_text(json.dumps({'id': ident, 'name': manifest['name'],
                'bytes': info['bytes'], 'sha256': info['sha256'], 'files': len(manifest['files'])}))
            return {'id': ident, 'files': len(manifest['files']), 'bytes': info['bytes'], 'sha256': info['sha256']}
        finally:
            pending.unlink(missing_ok=True)

    def save(self, data):
        self.install()
        self.idle()
        ident = uuid.uuid4().hex
        payload = json.dumps({'canvas': data['canvas'], 'name': data.get('name', '')})
        remote_path = '/tmp/cineharbor-project-' + ident + '.zip'
        try:
            self.rpc("__ch_data=json.loads(" + repr(payload) + ")\n"
                     "import sys,subprocess,importlib.metadata\n"
                     "__ch_env={'python':sys.version,'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']}}\n"
                     "__ch_git=subprocess.run(['git','-C','/content/ComfyUI','rev-parse','HEAD'],capture_output=True,text=True)\n"
                     "__ch_env['comfy_revision']=__ch_git.stdout.strip() if __ch_git.returncode==0 else None\n"
                     "__ch_manifest=__ch_store['pack']('/content/ComfyUI'," + repr(remote_path) + ",__ch_data['canvas'],__ch_data['name'],__ch_env)\n"
                     "__ch_result={'files':len(__ch_manifest['files'])}")
            result = self.download(ident, remote_path)
            result['drive_saved'] = False
            if data.get('drive') is True:
                try:
                    self.rpc("assert pathlib.Path('/content/drive/MyDrive').is_dir(), 'Mount your Drive first'\n"
                             "__ch_drive.mkdir(parents=True,exist_ok=True)\n"
                             "__ch_dst=__ch_drive/" + repr(ident + '.zip') + "\n"
                             "__ch_part=__ch_dst.with_suffix('.partial')\n"
                             "shutil.copyfile(" + repr(remote_path) + ",__ch_part)\n"
                             "assert __ch_store['digest'](__ch_part)==" + repr(result['sha256']) + ", 'Drive checksum mismatch'\n"
                             "__ch_part.replace(__ch_dst)\n__ch_result=True")
                    result['drive_saved'] = True
                except Exception:
                    result['warning'] = 'Local snapshot saved. Drive copy failed; keep the runtime open and retry. Drive is not confirmed saved.'
            return result
        finally:
            try:
                self.remote.run("pathlib.Path(" + repr(remote_path) + ").unlink(missing_ok=True)")
            except Exception:
                pass  # Never turn a verified local save into failure over temp cleanup.

    def restore(self, ident):
        path = self.local_path(ident)
        inspect_archive(path)
        self.install()
        self.idle()
        remote_path = '/tmp/cineharbor-restore-' + uuid.uuid4().hex + '.zip'
        try:
            expected = digest(path)
            # A Drive snapshot just copied onto this Mac is already on the VM.
            # Reuse only the fixed, ID-derived path with an exact archive hash;
            # never trust an arbitrary path supplied in local metadata.
            reuse = self.rpc("__ch_existing=__ch_drive/" + repr(ident + '.zip') + "\n"
                             "try:\n __ch_result=__ch_existing.is_file() and not __ch_existing.is_symlink() and __ch_store['digest'](__ch_existing)==" + repr(expected) + "\n"
                             "except OSError:\n __ch_result=False")
            if reuse:
                self.rpc("__ch_upload=__ch_existing\n__ch_result=True")
            else:
                self.rpc("__ch_upload=pathlib.Path(" + repr(remote_path) + ")\n__ch_upload.touch(exist_ok=False)\n__ch_result=True")
                with path.open('rb') as f:
                    for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
                        self.rpc("with __ch_upload.open('ab') as __ch_f:\n __ch_f.write(base64.b64decode(" + repr(base64.b64encode(block).decode()) + "))\n__ch_result=True")
            result = self.rpc("assert __ch_store['digest'](__ch_upload)==" + repr(expected) + ", 'Restore archive checksum mismatch'\n"
                              "__ch_result=__ch_store['restore']('/content/ComfyUI',__ch_upload)")
            result['archive_source'] = 'verified_drive' if reuse else 'verified_mac_upload'
            if hasattr(self.remote, 'meta_cache'):
                with self.remote.meta_lock:
                    self.remote.meta_cache.clear()
            if self.preview_cache is not None and self.endpoint:
                from comfy_verified_media import publish
                import tempfile,zipfile,shutil
                manifest,_=inspect_archive(path)
                with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory() as staging:
                    for item in manifest['files']:
                        parts=Path(item['path']).parts
                        if len(parts)!=3 or parts[:2]!=('files','input') or not re.fullmatch(r'cineharbor_[a-f0-9]{24}\.[a-z0-9]+',parts[2]):
                            continue
                        local=Path(staging)/parts[2]
                        with archive.open(item['path']) as source,local.open('wb') as destination:
                            shutil.copyfileobj(source,destination)
                        publish(self.preview_cache,self.endpoint,parts[2],local,item['sha256'])
            return result
        finally:
            try:
                self.remote.run("pathlib.Path(" + repr(remote_path) + ").unlink(missing_ok=True)")
            except Exception:
                pass

    def drive_list(self):
        self.install()
        return self.rpc("__ch_result=[]\n"
                        "for __ch_file in sorted(__ch_drive.glob('*.zip')):\n"
                        " if len(__ch_file.stem)!=32: continue\n"
                        " try:\n"
                        "  with __ch_store['zipfile'].ZipFile(__ch_file) as __ch_z:\n"
                        "   __ch_m=json.loads(__ch_z.read('manifest.json'))\n"
                        "  if __ch_m.get('schema')==__ch_store['SCHEMA']: __ch_result.append({'id':__ch_file.stem,'name':__ch_m['name'],'bytes':__ch_file.stat().st_size})\n"
                        " except Exception: continue")

    async def handle(self, request):
        tail = request.path.removeprefix('/__gc_projects').strip('/')
        if request.method == 'GET' and tail == '':
            return web.json_response([json.loads(p.read_text()) for p in sorted(self.directory.glob('*.json'))])
        if request.method == 'GET' and tail.startswith('download/'):
            path = self.local_path(tail.split('/')[-1])
            if not path.is_file():
                raise web.HTTPNotFound()
            return web.FileResponse(path, headers={'Content-Disposition': 'attachment; filename="CineHarbor-ComfyUI-' + path.name + '"', 'Cache-Control': 'no-store'})
        if not self.lock.acquire(blocking=False):
            return web.json_response({'error': 'A save or restore is already running.'}, status=409)
        try:
            if request.method == 'POST' and tail == 'save':
                result = await asyncio.to_thread(self.save, await request.json())
            elif request.method == 'POST' and tail.startswith('restore/'):
                result = await asyncio.to_thread(self.restore, tail.split('/')[-1])
            elif request.method == 'GET' and tail == 'drive':
                result = await asyncio.to_thread(self.drive_list)
            elif request.method == 'POST' and tail.startswith('fetch-drive/'):
                ident = tail.split('/')[-1]
                self.local_path(ident)
                await asyncio.to_thread(self.install)
                result = await asyncio.to_thread(self.download, ident,
                    '/content/drive/MyDrive/AI_Workstations/CineHarbor/ComfyProjects/' + ident + '.zip')
            elif request.method == 'POST' and tail == 'import-start':
                data = await request.json()
                size = data.get('bytes')
                if not isinstance(size, int) or not 0 < size <= 100 * 1024 ** 3:
                    raise ValueError('Invalid snapshot size')
                ident = uuid.uuid4().hex
                self.local_path(ident).with_suffix('.upload').touch(exist_ok=False)
                self.local_path(ident).with_suffix('.upload-info').write_text(str(size))
                result = {'id': ident}
            elif request.method == 'POST' and tail.startswith('import-chunk/'):
                path = self.local_path(tail.split('/')[-1])
                pending = path.with_suffix('.upload')
                size = int(path.with_suffix('.upload-info').read_text())
                offset = int(request.headers.get('X-Snapshot-Offset', '-1'))
                body = await request.read()
                if not body or len(body) > 4 * 1024 ** 2 or pending.stat().st_size != offset or offset + len(body) > size:
                    raise ValueError('Snapshot upload offset or size mismatch')
                with pending.open('ab') as f:
                    f.write(body)
                result = {'bytes': pending.stat().st_size}
            elif request.method == 'POST' and tail.startswith('import-finish/'):
                path = self.local_path(tail.split('/')[-1])
                pending = path.with_suffix('.upload')
                try:
                    if pending.stat().st_size != int(path.with_suffix('.upload-info').read_text()):
                        raise ValueError('Snapshot upload is incomplete')
                    manifest, _ = await asyncio.to_thread(inspect_archive, pending)
                    info = {'id': path.stem, 'name': manifest['name'], 'bytes': pending.stat().st_size,
                            'sha256': await asyncio.to_thread(digest, pending), 'files': len(manifest['files'])}
                    pending.replace(path)
                    path.with_suffix('.json').write_text(json.dumps(info))
                    result = info
                finally:
                    pending.unlink(missing_ok=True)
                    path.with_suffix('.upload-info').unlink(missing_ok=True)
            else:
                raise web.HTTPNotFound()
            return web.json_response(result)
        except web.HTTPException:
            raise
        except Exception as error:
            # Runtime exceptions can carry private paths; return a concise type.
            message = str(error) if isinstance(error, ValueError) and str(error).startswith(('Canvas ', 'Existing workspace ', 'Not enough ', 'Snapshot ', 'Invalid snapshot ', 'Save a complete ')) else 'Snapshot operation failed (' + type(error).__name__ + ').'
            return web.json_response({'error': message + ' No generation started.'}, status=400)
        finally:
            self.lock.release()
