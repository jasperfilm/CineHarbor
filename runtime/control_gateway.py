"""Explicit-endpoint Colab SDK transport with automatic proxy token refresh & resume-on-drop. Credentials remain inside the SDK."""
import argparse, json, sys, threading, time
from pathlib import Path
from types import SimpleNamespace
from colab_cli.common import State
from colab_cli.runtime import ColabRuntime
from colab_cli.contents import ContentsClient

p = argparse.ArgumentParser()
p.add_argument('--endpoint', required=True)
args = p.parse_args()
payload = json.load(sys.stdin)
s = State()


def get_vm():
    vm = next((a for a in s.client.list_assignments() if a.endpoint == args.endpoint), None)
    if vm is None:
        raise SystemExit('指定运行时已不在当前账号分配列表中')
    return vm


vm = get_vm()
if payload['action'] == 'release':
    s.client.unassign(args.endpoint)
    if any(a.endpoint == args.endpoint for a in s.client.list_assignments()):
        raise SystemExit('目标会话仍在分配列表中，释放尚未确认')
    print('JASPER_RESULT ' + json.dumps({'released': True, 'endpoint': args.endpoint}), flush=True)
    raise SystemExit(0)


def _keep_alive_loop():
    while True:
        try:
            s.client._issue_request(
                f"{s.client.colab_domain}/tun/m/{args.endpoint}/keep-alive/",
                method="GET",
                headers={"X-Colab-Tunnel": "Google"},
            )
        except Exception:
            pass
        time.sleep(180)


threading.Thread(target=_keep_alive_loop, daemon=True).start()

wf_lib_src = (Path(__file__).parent.parent / 'workflow_library.py').read_text()
managed_src = Path(__file__).with_name('managed_runtime.py').read_text()
submitted_prompt_id = payload.get('prompt_id')
idempotent_actions = ('setup', 'inspect', 'models', 'restore', 'resume', 'backup_stop', 'backup')

last_err = None
result = None
for attempt in range(4):
    if attempt > 0:
        time.sleep(3 * attempt)
        vm = get_vm()
        if payload['action'] == 'generate' and submitted_prompt_id:
            payload = dict(payload, action='resume', prompt_id=submitted_prompt_id)
        print('JASPER_EVENT ' + json.dumps({'stage': 'reconnecting', 'message': f'检测到云端代理闪断，正在无损重连（第 {attempt} 次）'}), flush=True)
    r = ColabRuntime(vm.runtime_proxy_info.url, vm.runtime_proxy_info.token)
    text = []

    def hook(item):
        global submitted_prompt_id
        if item.get('output_type') == 'stream':
            value = item.get('text', '')
            text.append(value)
            for line in value.splitlines():
                if line.startswith('JASPER_EVENT '):
                    print(line, flush=True)
                    try:
                        ev = json.loads(line[13:])
                        if ev.get('prompt_id'):
                            submitted_prompt_id = ev['prompt_id']
                    except Exception:
                        pass
        elif item.get('output_type') == 'error':
            raise RuntimeError(item.get('ename', 'RemoteError') + ': ' + item.get('evalue', ''))

    try:
        code = 'CONTROL = ' + repr(payload) + '\n' + wf_lib_src + '\n' + managed_src
        outputs = r.execute_code(code, timeout=28800, output_hook=hook)
        alltext = ''.join(text)
        if not alltext:
            alltext = ''.join(x.get('text', '') for x in outputs if x.get('output_type') == 'stream')
        lines = [x[14:] for x in alltext.splitlines() if x.startswith('JASPER_RESULT ')]
        if not lines:
            raise RuntimeError('远端没有返回完成记录；保留会话，禁止自动重提')
        result = json.loads(lines[-1])
        break
    except Exception as exc:
        last_err = exc
        transient = any(k in str(exc) for k in ('Connection was lost', 'WebSocket', 'Timeout waiting for reply', 'ConnectionResetError', 'Broken pipe', 'EOFError'))
        can_retry = transient and (payload['action'] in idempotent_actions or bool(submitted_prompt_id))
        if not can_retry or attempt == 3:
            raise
    finally:
        try:
            r.stop(shutdown_kernel=True)
        except Exception:
            pass

local = []
if payload['action'] in ('generate', 'resume'):
    vm = get_vm()
    dest = Path(payload['local_results'])
    dest.mkdir(parents=True, exist_ok=True)
    contents = ContentsClient(SimpleNamespace(url=vm.runtime_proxy_info.url, token=vm.runtime_proxy_info.token))
    for name in result.get('outputs', []):
        src = Path(name)
        if not src.is_relative_to('/content/ComfyUI/output') or src.suffix.lower() not in ('.mp4', '.webm', '.png', '.jpg', '.jpeg', '.wav', '.mp3', '.flac', '.ogg', '.m4a'):
            raise ValueError('结果路径不在允许的输出目录')
        target = dest / (str(len(local)) + '_' + src.name)
        part = target.with_suffix(target.suffix + '.partial')
        for dl_try in range(3):
            try:
                contents.download(str(src), str(part))
                break
            except Exception:
                if dl_try == 2:
                    raise
                time.sleep(2)
                vm = get_vm()
                contents = ContentsClient(SimpleNamespace(url=vm.runtime_proxy_info.url, token=vm.runtime_proxy_info.token))
        part.replace(target)
        local.append(str(target))
    result['local_files'] = local
print('JASPER_RESULT ' + json.dumps(result, ensure_ascii=False), flush=True)
