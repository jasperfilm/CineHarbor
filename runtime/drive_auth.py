"""Bounded official Drive authorization with a loopback-only browser handoff.
OAuth URL and tokens stay in memory; logs contain state labels only.
"""
import argparse, json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from colab_cli.common import State
from colab_cli.runtime import ColabRuntime
from colab_cli.auth import get_credentials

parser = argparse.ArgumentParser()
parser.add_argument('--endpoint', required=True)
args = parser.parse_args()
s = State()
target = args.endpoint
vm = next(a for a in s.client.list_assignments() if a.endpoint == target)
r = ColabRuntime(vm.runtime_proxy_info.url, vm.runtime_proxy_info.token)
ready = threading.Event()
proceed = threading.Event()
shared = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.headers.get('Host') != '127.0.0.1:8768':
            self.send_error(403)
            return
        if self.path == '/auth' and shared.get('uri'):
            self.send_response(302)
            self.send_header('Location', shared['uri'])
            self.end_headers()
        elif self.path == '/status':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({'ready': ready.is_set(), 'done': shared.get('done', False)}).encode())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.headers.get('Host') != '127.0.0.1:8768' or self.headers.get('X-GC-Local') != '1':
            self.send_error(403)
            return
        if self.path != '/continue':
            self.send_error(404)
            return
        proceed.set()
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'OK')


# Browsers preconnect and can leave an idle socket open. One idle connection must not block OAuth redirects.
http = ThreadingHTTPServer(('127.0.0.1', 8768), Handler)
threading.Thread(target=http.serve_forever, daemon=True).start()


def hook(msg, ws):
    if msg.get('content', {}).get('request', {}).get('authType') != 'dfs_ephemeral':
        return False
    msgid = msg.get('metadata', {}).get('colab_msg_id')
    url = s.client.colab_domain + '/tun/m/credentials-propagation/' + target
    params = {'authuser': '0', 'authtype': 'dfs_ephemeral', 'version': '2', 'dryrun': 'false', 'propagate': 'true', 'record': 'false'}

    # Offload OAuth wait & propagation off the WebSocket reader thread so ping/pong frames never stall!
    def _worker():
        try:
            creds = get_credentials(s.client_oauth_config, provider=s.auth_provider)

            def try_prop(dry='false'):
                p = dict(params, dryrun=dry)
                r1 = creds.request('GET', url, params=p)
                tok = json.loads(r1.text.split('\n', 1)[-1]).get('token')
                r2 = creds.request('POST', url, params=p, headers={'x-goog-colab-token': tok}, files={'file_id': (None, 'empty.ipynb')})
                if r2.status_code != 200:
                    return r2.status_code, {}
                return 200, json.loads(r2.text.split('\n', 1)[-1])

            code, data = try_prop('false')
            if code != 200 or not data.get('success'):
                _, dry_data = try_prop('true')
                shared['uri'] = data.get('unauthorized_redirect_uri') or dry_data.get('unauthorized_redirect_uri')
                if not shared['uri'] or not shared['uri'].startswith('https://accounts.google.com/'):
                    raise RuntimeError('No safe Google authorization URL')
                ready.set()
                print('JASPER_EVENT ' + json.dumps({'stage': 'authorization_required', 'message': '请在弹出的 Google 页面点击允许挂载云盘（完成后自动继续）', 'auth_url': 'http://127.0.0.1:8768/auth'}), flush=True)
                deadline = time.time() + 360
                authed = False
                while time.time() < deadline:
                    if proceed.wait(3.0):
                        c2, d2 = try_prop('false')
                        if c2 == 200 and d2.get('success'):
                            authed = True
                            break
                    try:
                        c2, d2 = try_prop('false')
                        if c2 == 200 and d2.get('success'):
                            authed = True
                            break
                    except Exception:
                        pass
                if not authed:
                    raise RuntimeError('Drive authorization handoff timed out')
            reply = ws.session.msg('input_reply', {'value': {'type': 'colab_reply', 'colab_msg_id': msgid}})
            if 'header' in msg:
                reply['parent_header'] = msg['header']
            ws.stdin_channel.send(reply)
            print('JASPER_EVENT ' + json.dumps({'stage': 'mounting', 'message': '授权已传播，正在挂载云盘'}), flush=True)
        except Exception as exc:
            shared['hook_err'] = str(exc)

    threading.Thread(target=_worker, daemon=True).start()
    return True


r.colab_request_hook = hook
try:
    code = (
        "import os\n"
        "if not os.path.isdir('/content/drive/MyDrive'):\n"
        "    from google.colab import drive\n"
        "    drive.mount('/content/drive', timeout_ms=480000)\n"
        "print('DRIVE_MOUNTED', os.path.isdir('/content/drive/MyDrive'))\n"
    )
    output = r.execute_code(code, allow_stdin=True, timeout=480)
    for item in output:
        if item.get('output_type') == 'error':
            raise RuntimeError(item.get('ename', 'RemoteError') + ': ' + item.get('evalue', ''))
        if 'DRIVE_MOUNTED' in item.get('text', ''):
            print('JASPER_RESULT ' + json.dumps({'drive_mounted': 'True' in item['text']}), flush=True)
    shared['done'] = True
finally:
    try:
        r.stop(shutdown_kernel=True)
    except Exception:
        pass
    http.shutdown()
