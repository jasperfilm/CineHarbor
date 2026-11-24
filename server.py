"""Two local workbenches (Core API + Static Shell). No credentials leave this machine."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote
import base64, copy, hashlib, json, mimetypes, os, re, secrets, shutil, subprocess, sys, threading, time, uuid

ROOT = Path(os.environ.get('JASPER_WORKSTATION_ROOT', Path(__file__).resolve().parent))
# Use built-in MIME tables: an App Sandbox must not read host Apache configuration.
mimetypes.knownfiles = []
mimetypes.init(files=[])
PRODUCT = json.loads((ROOT/'assets/branding/product.json').read_text()) if (ROOT/'assets/branding/product.json').is_file() else {'version':'1.0.0','display_name':'GC Labs'}
VERSION = PRODUCT['version']
DATA = Path(os.environ.get('GC_LABS_DATA') or os.environ.get('JASPER_WORKSTATION_DATA') or (ROOT / 'data'))
WEB = ROOT / 'web'
ASSETS = DATA / 'assets'
DATA.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()
OP_LOCK = threading.Lock()
KEY = secrets.token_urlsafe(32)

from account_login import AccountLogin
LOGIN = AccountLogin()

DB = DATA / 'workspace.json'
CLI = Path.home() / '.local/bin/colab'
EXPECTED = ''
SESSION = 'gc-labs-workstation'
LEGACY_SESSION = 'jasper-video-workstation'
PORT = int(os.environ.get('JASPER_WORKSTATION_PORT', '8766'))
SOURCE = Path(os.environ.get('JASPER_MEDIA_ROOT') or (DATA / 'external-media'))


def sdk_python():
    bundled = os.environ.get('GC_LABS_PYTHON')
    if bundled:
        return bundled
    first = CLI.read_text().splitlines()[0]
    return first[2:] if first.startswith('#!') else sys.executable


def cli_command(args):
    entry = os.environ.get('GC_LABS_CLI_ENTRY')
    return [sdk_python(), entry, *args] if entry else [str(CLI), *args]


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def save(data):
    with LOCK:
        tmp = DB.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        tmp.replace(DB)


def load():
    with LOCK:
        return json.loads(DB.read_text())


def cli(args, timeout=25):
    env = os.environ.copy()
    env['NO_COLOR'] = '1'
    env['TERM'] = 'dumb'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    p = subprocess.run(cli_command(args), capture_output=True, text=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    text = p.stdout + p.stderr
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    if p.returncode:
        if any(x in text.lower() for x in ('authorization code', 'to authorize', 'no valid default credentials', 'defaultcredentialserror', 'eof when reading', 'invalid_grant', 'invalidgrant', 'refresherror', 'invalid_scope')):
            raise RuntimeError('尚未登录或授权已失效。请在管理台点击Google登录。')
        raise RuntimeError(text[-3000:])
    return text


def identity():
    text = cli(['whoami'])
    m = re.search(r'Email:\s*(\S+)', text)
    if not m:
        raise RuntimeError('CLI 需要重新授权，请在本机终端完成登录。')
    return m.group(1)


def expected_account():
    profile = DATA / 'profile.json'
    if profile.exists():
        return json.loads(profile.read_text()).get('expected_account', '')
    if DB.exists():
        return load().get('policy', {}).get('expected_account', EXPECTED)
    return EXPECTED


def bind_account(email):
    if (DATA / 'lease.json').exists() or OP_LOCK.locked():
        raise ValueError('请先结束并核对当前会话，再更换绑定账号。')
    actual = identity()
    if email != actual:
        raise ValueError('当前CLI账号已变化，请刷新后再确认。')
    tmp = DATA / 'profile.tmp'
    tmp.write_text(json.dumps({'expected_account': actual}, ensure_ascii=False))
    tmp.replace(DATA / 'profile.json')
    return {'email': actual, 'bound': True}


def guarded():
    if LOGIN.status()['state'] in ('waiting', 'verifying'):
        raise ValueError('正在登录，请先完成或取消授权。')
    email = identity()
    expected = expected_account()
    if not expected:
        raise ValueError('请先在管理台确认绑定当前账号。')
    if email != expected:
        raise ValueError('账号不匹配：当前 ' + email + '，需要 ' + expected)
    return email


MODELS = [
    {'id': 'h3', 'name': 'MiniMax H3', 'kind': 'video', 'provider': 'MiniMax / ComfyUI', 'state': 'candidate', 'description': '完整BF16图生视频适配器已接入；需准备相应权重、核对许可并在当前会话验证。', 'source': 'https://docs.comfy.org/tutorials/video/minimax/minimax-h3', 'size': '按完整BF16清单核验', 'gpu': 'G4 · 96GB', 'tested': False},
    {'id': 'ltx25', 'name': 'LTX 2.5', 'kind': 'video', 'provider': 'Lightricks', 'state': 'candidate', 'description': '官方开放权重候选；支持一键载入官方工作流模板并配置完整精度权重。', 'source': 'https://huggingface.co/Lightricks/LTX-2.5', 'size': '待核对', 'gpu': 'G4 · 96GB', 'tested': False},
    {'id': 'wan22', 'name': 'Wan 2.2 I2V A14B', 'kind': 'video', 'provider': 'Wan-AI', 'state': 'candidate', 'description': '图生视频开放模型候选；支持一键载入官方画布模板自动转换API工作流。', 'source': 'https://github.com/Wan-Video/Wan2.2', 'size': '按组件安装', 'gpu': 'G4 · 96GB', 'tested': False},
    {'id': 'qwenimage', 'name': 'Qwen Image', 'kind': 'image', 'provider': 'Qwen', 'state': 'candidate', 'description': '图像生成与编辑系列；支持一键载入官方画布模板转换为API工作流。', 'source': 'https://qwen.ai/blog?id=qwen-image-2.0', 'size': '待核对', 'gpu': 'G4 · 96GB', 'tested': False},
    {'id': 'acestep', 'name': 'ACE-Step 1.5', 'kind': 'audio', 'provider': 'ACE-Step', 'state': 'candidate', 'description': '音乐生成系列；支持一键载入官方模板生成长音频并接入粗剪音轨。', 'source': 'https://huggingface.co/ACE-Step/Ace-Step1.5', 'size': '待核对', 'gpu': 'G4 · 96GB', 'tested': False},
]


def seed():
    if DB.exists():
        return
    save({
        'schema_version': 2,
        'project': {'id': uuid.uuid4().hex, 'name': 'New Project', 'ratio': '9:16', 'description': '', 'status': 'active'},
        'assets': [],
        'shots': [],
        'workflows': [],
        'jobs': [],
        'historical_jobs': [],
        'models': copy.deepcopy(MODELS),
        'events': [],
        'policy': {'expected_account': EXPECTED, 'gpu': 'G4', 'max_minutes': 240, 'auto_release': False}
    })


def parse_sessions(text):
    rows = []
    for line in text.splitlines():
        m = re.match(r'^\[([^]]+)\]\s+(\S+)\s+\|\s+Hardware:\s*([^|]+)', line)
        if m:
            rows.append({'name': m[1], 'endpoint': m[2], 'hardware': m[3].strip()})
    return rows


def runtime_state(result):
    rows = result['sessions']
    active = result['active']
    lease_path = DATA / 'lease.json'
    lease = json.loads(lease_path.read_text()) if lease_path.exists() else None
    consistent = active is not None and int(active) == len(rows)
    owned = next((r for r in rows if lease and lease.get('endpoint') == r['endpoint'] and lease.get('session') == r['name']), None)
    # An endpoint, not a friendly name, identifies the VM we may release.
    state = 'unknown' if not consistent else 'owned' if owned else 'external' if rows else 'idle'
    return {
        'runtime_state': state,
        'can_start': bool(result['account_ok'] and consistent and active == 0 and not lease),
        'can_stop': bool(result['account_ok'] and consistent and owned and lease.get('state') == 'active'),
        'managed_session': owned,
        'lease_state': lease.get('state') if lease else None,
        'operation_busy': OP_LOCK.locked(),
        'can_reconcile': bool(result['account_ok'] and consistent and active == 0 and lease)
    }


def refresh():
    email = identity()
    usage = cli(['usage'])
    sessions = cli(['sessions'])

    def number(pattern):
        m = re.search(pattern, usage)
        return float(m.group(1)) if m else None

    result = {
        'email': email,
        'account_ok': bool(expected_account()) and email == expected_account(),
        'expected_account': expected_account(),
        'balance': number(r'Current balance:\s*([\d.]+)'),
        'rate': number(r'Usage rate:\s*([\d.]+)'),
        'active': number(r'Active assignments:\s*(\d+)'),
        'checked_at': now(),
        'sessions_text': sessions,
        'sessions': parse_sessions(sessions),
        'error': None
    }
    result.update(runtime_state(result))
    (DATA / 'live_status.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def operation(action, body):
    if not OP_LOCK.acquire(blocking=False):
        raise ValueError('已有运行时操作正在执行，请勿重复提交。')
    try:
        return _operation(action, body)
    finally:
        OP_LOCK.release()


def _operation(action, body):
    guarded()
    if action == 'start':
        gpu = body.get('gpu', 'G4')
        if (DATA / 'lease.json').exists():
            raise ValueError('已有开机记录。先核对并处理它，不重复申请。')
        current = refresh()
        if current['active'] != 0 or current.get('runtime_state') == 'unknown':
            raise ValueError('已有运行时或状态未确认，禁止重复开机。')
        # Read saved settings only when needed, after ownership checks. dict.get
        # evaluates its default eagerly even when the caller supplied minutes.
        minutes = int(body['max_minutes'] if 'max_minutes' in body else load().get('policy', {}).get('max_minutes', 240))
        if gpu != 'G4' or not 5 <= minutes <= 1440:
            raise ValueError('生产配置锁定G4；提醒须为5–1440分钟，不自动降级')
        lease = {'session': SESSION, 'started': time.time(), 'start_balance': current.get('balance'), 'reminder_at': time.time() + minutes * 60, 'backup_pending': False, 'state': 'allocating'}
        (DATA / 'lease.json').write_text(json.dumps(lease))
        try:
            output = cli(['new', '-s', SESSION, '--gpu', gpu], timeout=240)
        except Exception:
            lease['state'] = 'uncertain'
            (DATA / 'lease.json').write_text(json.dumps(lease))
            raise
        created = refresh()
        assigned = next((r for r in created['sessions'] if r['name'] == SESSION), None)
        if not assigned:
            raise ValueError('已请求开机，但尚未确认会话标识。请核查会话，不重复启动。')
        lease.update(state='active', endpoint=assigned['endpoint'])
        (DATA / 'lease.json').write_text(json.dumps(lease))
        # A production reminder must never discard in-progress generations or backups.
        guard = DATA / 'runtime' / 'lease_guard.py'
        guard.parent.mkdir(exist_ok=True)
        guard.write_text(
            'import threading,json,time\nfrom pathlib import Path\n'
            'def reminder():\n    Path("/content/jasper_session_reminder.json").write_text(json.dumps({"state":"budget_reminder","at":time.time(),"release":False}))\n'
            't=threading.Timer(' + str(minutes * 60) + ',reminder)\nt.daemon=True\nt.start()\nprint("RUNTIME_REMINDER_ARMED_NO_FORCED_SHUTDOWN")\n'
        )
        try:
            cli(['exec', '-s', SESSION, '-f', str(guard)], timeout=60)
        except Exception:
            cli(['stop', '-s', SESSION], timeout=90)
            (DATA / 'lease.json').unlink(missing_ok=True)
            raise ValueError('时长提醒未启动，已停止此次运行时。')
        d = load()
        d['policy']['budget_paused'] = False
        d['events'].insert(0, {'time': now(), 'text': '已请求 ' + gpu + '；' + str(minutes) + ' 分钟后提醒，不强制关机。'})
        save(d)
        return {'output': output, 'status': refresh()}
    if action == 'stop':
        if body.get('backup_confirmed') is not True:
            raise ValueError('请先确认结果已保存。')
        lease = DATA / 'lease.json'
        if not lease.exists():
            raise ValueError('没有由此工作站创建的运行时；不会停止其他会话。')
        owned = json.loads(lease.read_text())
        before = refresh()
        if not before['can_stop']:
            raise ValueError('未确认此工作站拥有当前会话；不会停止其他会话。')
        if owned.get('adopted'):
            python = sdk_python()
            process = subprocess.run([python, str(ROOT / 'runtime/control_gateway.py'), '--endpoint', owned['endpoint']], input=json.dumps({'action': 'release'}), capture_output=True, text=True, timeout=90)
            if process.returncode:
                raise RuntimeError('明确绑定的运行时释放失败：' + process.stderr[-1000:])
            output = '已释放接管的明确运行时'
        else:
            output = cli(['stop', '-s', owned['session']], timeout=90)
        status = refresh()
        if any(r['endpoint'] == owned['endpoint'] for r in status['sessions']):
            raise ValueError('停止命令已执行，但目标会话仍存在，请核查。')
        lease.unlink()
        return {'output': output, 'status': refresh()}
    raise ValueError('不支持的操作')


def export_shot(shot, d):
    if shot.get('model') == 'workflow':
        recipe_item = shot.get('recipe') or next((w for w in d.get('workflows', []) if w['id'] == shot.get('workflow')), None)
        if not recipe_item:
            raise ValueError('未找到绑定的自定义工作流。')
        ref = next((a for a in d['assets'] if a['id'] == shot.get('reference') and a['kind'] == 'image'), None) if shot.get('reference') else None
        ref_payload = None
        if ref:
            source = Path(ref.get('path') or ASSETS / ref['file'])
            ref_payload = {'suffix': source.suffix, 'base64': base64.b64encode(source.read_bytes()).decode()}
        end_ref = next((a for a in d['assets'] if a['id'] == shot.get('end_reference') and a['kind'] == 'image'), None) if shot.get('end_reference') else None
        end_ref_payload = None
        if end_ref:
            esource = Path(end_ref.get('path') or ASSETS / end_ref['file'])
            end_ref_payload = {'suffix': esource.suffix, 'base64': base64.b64encode(esource.read_bytes()).decode()}
        config = {k: shot.get(k) for k in ('title', 'prompt', 'negative_prompt', 'duration', 'resolution', 'model', 'seed', 'reference', 'end_reference', 'workflow')}
        config['ratio'] = d['project']['ratio']
        config['recipe'] = recipe_item
        payload = {'action': 'generate', 'job': uuid.uuid4().hex, 'config': config, 'reference': ref_payload, 'end_reference': end_ref_payload, 'custom_nodes': recipe_item.get('custom_nodes', []), 'require_h3': False}
        lib_src = (ROOT / 'workflow_library.py').read_text()
        common = (ROOT / 'runtime/managed_runtime.py').read_text().split("kind=CONTROL['action'];event")[0]

        def cell(code):
            return {'cell_type': 'code', 'metadata': {}, 'source': [code], 'execution_count': None, 'outputs': []}

        return {
            'nbformat': 4, 'nbformat_minor': 5,
            'metadata': {'colab': {'name': (shot.get('title') or 'workflow') + '.ipynb'}, 'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
            'cells': [
                {'cell_type': 'markdown', 'metadata': {}, 'source': ['# ' + str(shot.get('title') or 'GC Labs 工作流任务') + '\n选择 G4 运行时，挂载云盘后依次执行环境准备与真实推理。结果核验后请执行云盘备份释放。']},
                cell('from google.colab import drive\ndrive.mount("/content/drive")'),
                cell('CONTROL = ' + repr(payload) + '\n' + lib_src + '\n' + common + '\nprint(setup())'),
                cell('print(generate())')
            ]
        }

    if shot['model'] != 'h3':
        raise ValueError('该候选模型尚未安装适配器，请导入或选择自定义工作流。')
    ref = next((a for a in d['assets'] if a['id'] == shot['reference'] and a['kind'] == 'image'), None)
    if not ref:
        raise ValueError('请先选择一张参考图。')
    source = Path(ref.get('path') or ASSETS / ref['file'])
    end_ref = next((a for a in d['assets'] if a['id'] == shot.get('end_reference') and a['kind'] == 'image'), None) if shot.get('end_reference') else None
    end_payload = {'suffix': Path(end_ref.get('path') or ASSETS / end_ref['file']).suffix, 'base64': base64.b64encode(Path(end_ref.get('path') or ASSETS / end_ref['file']).read_bytes()).decode()} if end_ref else None
    config = {k: shot.get(k) for k in ('title', 'prompt', 'duration', 'resolution', 'model', 'seed', 'end_reference')}
    config['ratio'] = d['project']['ratio']
    payload = {'action': 'restore', 'job': uuid.uuid4().hex, 'config': config, 'reference': {'suffix': source.suffix, 'base64': base64.b64encode(source.read_bytes()).decode()}, 'end_reference': end_payload}
    common = (ROOT / 'runtime/managed_runtime.py').read_text().split("kind=CONTROL['action'];event")[0]

    def cell(code):
        return {'cell_type': 'code', 'metadata': {}, 'source': [code], 'execution_count': None, 'outputs': []}

    return {
        'nbformat': 4, 'nbformat_minor': 5,
        'metadata': {'colab': {'name': shot['title'] + '.ipynb'}, 'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
        'cells': [
            {'cell_type': 'markdown', 'metadata': {}, 'source': ['# ' + shot['title'] + '\n完整BF16工作站任务。先选择G4，再挂载云盘、恢复、启动、生成。不会自动申请其他GPU或在生成后强制关机；结果核验后回管理台备份释放。']},
            cell('from google.colab import drive\ndrive.mount("/content/drive")'),
            cell('CONTROL = ' + repr(payload) + '\n' + common + '\nprint(restore())'),
            cell('print(setup())'),
            cell('print(generate())')
        ]
    }


def record_local_film(project_id, result):
    """Register a rendered film in its originating project without clobbering live jobs."""
    source = (DATA / 'exports' / Path(result['file']).name).resolve()
    if not source.is_file() or not source.is_relative_to((DATA / 'exports').resolve()):
        raise ValueError('Exported film was not found')
    with source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    with LOCK:
        workspace = load()
        active = workspace['project']['id'] == project_id
        target = DATA / 'projects' / (project_id + '.json')
        if not active:
            if not re.fullmatch(r'[a-zA-Z0-9_-]+', project_id) or not target.is_file():
                raise ValueError('The source project is unavailable; the exported file is preserved')
            workspace = json.loads(target.read_text())
        existing = next((a for a in workspace.get('assets', []) if a.get('path') == str(source)), None)
        if existing is None:
            existing = {'id': uuid.uuid4().hex, 'name': source.name, 'file': source.name,
                        'path': str(source), 'kind': 'video', 'is_local_export': True,
                        'sha256': digest, 'created': now()}
            workspace.setdefault('assets', []).append(existing)
        workspace['project']['latest_export_asset'] = existing['id']
        if active:
            save(workspace)
        else:
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(workspace, ensure_ascii=False, indent=2))
            temporary.replace(target)
    return existing['id']


def projects():
    directory = DATA / 'projects'
    directory.mkdir(exist_ok=True)
    current = load()
    rows = [current['project']]
    for path in sorted(directory.glob('*.json')):
        item = json.loads(path.read_text())['project']
        if item.get('id') != current['project'].get('id'):
            rows.append(item)
    return rows


def migrate():
    d = load()
    if d.get('schema_version', 0) >= 2:
        return
    d['historical_jobs'] = d.get('jobs', [])
    d['jobs'] = []
    d['schema_version'] = 2
    d.setdefault('workflows', [])
    d['policy'].update(gpu='G4', auto_release=False)
    save(d)


def capabilities():
    from timeline_export import media_tool_binary
    try:
        has_media = media_tool_binary(ROOT).is_file()
    except Exception:
        has_media = False
    return {
        'ok': True,
        'version': VERSION,
        'shell_agnostic': True,
        'gpu_policy': 'G4 only',
        'media_engine': has_media,
        'features': [
            'core_shell_decoupled',
            'batch_queue',
            'step_progress',
            'safe_interrupt',
            'frame_chaining',
            'canvas_to_api',
            'custom_node_lockfile',
            'rough_cut_mp4',
            'fcpxml_export',
            'capcut_export',
            'full_precision_presets',
            'cu_budget_guardrail',
            'mobile_readonly_monitor',
            'multi_take_gallery',
            'character_scene_elements',
            'dual_frame_lock',
            'native_joint_av',
            'offline_demo_project',
            'character_keyframe_derivation',
            'script_to_storyboard',
            'character_turnaround_3view',
            'nine_grid_storyboard_slicer',
            'camera_rig_presets',
            'voice_timbre_lock',
            'qc_filmstrip',
            'subtitle_burn_and_ducking',
            'srt_and_storyboard_sheet_export',
        ]
    }


CONSOLE = None
MONITOR = None


def get_monitor():
    global MONITOR
    if MONITOR is None:
        from mobile_monitor import MobileMonitor
        MONITOR = MobileMonitor(sys.modules[__name__])
    return MONITOR


def inspection():
    path = DATA / 'remote_inspection.json'
    return json.loads(path.read_text()) if path.exists() else None


def local_backup():
    import zipfile
    from timeline_export import resolve_asset_file
    # Freeze the active project and bundle external references too. Never change
    # the live workspace merely to make a portable copy.
    workspace = json.loads(json.dumps(load()))
    # A portable project is not an account or machine-state backup. Keep only
    # reproducible generation history, never old operations or unrelated projects.
    workspace['policy'] = {key: value for key, value in workspace.get('policy', {}).items()
                           if key in ('gpu', 'max_minutes', 'max_cu_budget', 'auto_release')}
    job_fields = {'id', 'shot', 'title', 'model', 'config', 'shot_snapshot', 'state',
                  'created', 'updated', 'finished', 'results', 'bind_element_id',
                  'bind_slot', 'is_nine_grid', 'is_turnaround'}
    for field in ('jobs', 'historical_jobs'):
        workspace[field] = [{key: value for key, value in job.items() if key in job_fields}
                            for job in workspace.get(field, []) if isinstance(job, dict)]
    secret_fields = {'api_key', 'apikey', 'access_token', 'refresh_token', 'id_token',
                     'password', 'authorization', 'cookie', 'client_secret', 'private_key'}
    def omit_secrets(value):
        if isinstance(value, dict):
            return {key: omit_secrets(item) for key, item in value.items()
                    if str(key).lower() not in secret_fields}
        if isinstance(value, list):
            return [omit_secrets(item) for item in value]
        return value
    workspace = omit_secrets(workspace)
    final_file = workspace.get('project', {}).get('final_file')
    if final_file:
        final_source = Path(final_file)
        if not final_source.is_file():
            raise ValueError('成片文件不存在，无法生成完整备份')
        final_asset = next((a for a in workspace.get('assets', []) if resolve_asset_file(sys.modules[__name__], a).resolve() == final_source.resolve()), None)
        if final_asset is None:
            final_asset = {'id': uuid.uuid4().hex, 'name': final_source.name, 'kind': 'video', 'path': str(final_source), 'created': now()}
            workspace.setdefault('assets', []).append(final_asset)
        workspace['portable_final_asset_id'] = final_asset['id']
        workspace['project'].pop('final_file', None)
    media = {}
    for asset in workspace.get('assets', []):
        source = resolve_asset_file(sys.modules[__name__], asset)
        name = asset.get('file', '')
        if asset.get('path') or not name or Path(name).name != name:
            name = hashlib.sha256(str(asset['id']).encode()).hexdigest()[:32] + source.suffix.lower()
        asset['file'] = name
        asset.pop('path', None)
        from comfy_project_store import digest
        asset['sha256'] = digest(source)
        media[name] = source
    ident = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    dest = DATA / 'exports'
    dest.mkdir(exist_ok=True)
    file = dest / ('CineHarbor_Project_' + ident + '.zip')
    pending = file.with_suffix('.partial')
    try:
      with zipfile.ZipFile(pending, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('workspace.json', json.dumps(workspace, ensure_ascii=False, indent=2))
        for name, p in media.items():
            z.write(p, 'assets/' + name)
        z.writestr('README.txt', 'Active project and its media, including external references. Models and cloud ComfyUI snapshots are separate. Application login files are excluded. Remove secrets manually entered in custom workflows before sharing.')
      with zipfile.ZipFile(pending) as z:
        for asset in workspace.get('assets', []):
            h = hashlib.sha256()
            with z.open('assets/' + asset['file']) as src:
                for block in iter(lambda: src.read(1024 * 1024), b''):
                    h.update(block)
            if h.hexdigest() != asset['sha256']:
                raise ValueError('素材在备份期间发生变化，请停止编辑后重试')
      pending.replace(file)
    finally:
      pending.unlink(missing_ok=True)
    return {'file': file.name, 'url': '/exports/' + file.name, 'bytes': file.stat().st_size}


def _chain_shot_frame(d, body):
    from timeline_export import extract_video_frame, resolve_asset_file
    if d['project'].get('status') == 'completed':
        raise ValueError('已结项项目只读，请新建项目。')
    source_shot_id = body.get('source_shot')
    asset_id = body.get('asset_id')
    position = str(body.get('position', 'last'))
    src_shot = next((s for s in d['shots'] if s['id'] == source_shot_id), None) if source_shot_id else None
    if not asset_id and src_shot:
        asset_id = src_shot.get('output')
    src_asset = next((a for a in d['assets'] if a['id'] == asset_id and a.get('kind') == 'video'), None)
    if not src_asset:
        raise ValueError('未找到可提取画面的视频样片素材。')
    video_path = resolve_asset_file(sys.modules[__name__], src_asset)
    ident = uuid.uuid4().hex
    out_file = ident + '.png'
    out_path = ASSETS / out_file
    frame_info = extract_video_frame(ROOT, video_path, out_path, position=position)
    pos_label = 'first-frame' if position == 'first' else 'last-frame' if position == 'last' else f'frame-{position}s'
    base_title = src_shot['title'] if src_shot else src_asset['name']
    new_asset = {
        'id': ident,
        'name': f'{base_title} · {pos_label}.png',
        'file': out_file,
        'kind': 'image',
        'sha256': frame_info['sha256'],
        'created': now()
    }
    d['assets'].append(new_asset)

    target_mode = body.get('target', 'next')  # 'next' | 'new' | 'none' | explicit shot id
    bound_shot = None
    if target_mode == 'new':
        idx = d['shots'].index(src_shot) + 1 if src_shot in d['shots'] else len(d['shots'])
        sx = (src_shot.get('x', 220) + 460) if src_shot else (220 + len(d['shots']) * 340)
        sy = src_shot.get('y', 80) if src_shot else 80
        new_shot = {
            'id': uuid.uuid4().hex,
            'title': f'{base_title} · continuation',
            'prompt': '',
            'duration': src_shot.get('duration', 5) if src_shot else 5,
            'resolution': src_shot.get('resolution', '1080P') if src_shot else '1080P',
            'model': src_shot.get('model', 'h3') if src_shot else 'h3',
            'workflow': src_shot.get('workflow') if src_shot else None,
            'seed': 2711,
            'reference': ident,
            'output': None,
            'versions': [],
            'x': sx,
            'y': sy
        }
        d['shots'].insert(idx, new_shot)
        bound_shot = new_shot['id']
    elif target_mode == 'next' and src_shot in d['shots']:
        idx = d['shots'].index(src_shot)
        if idx + 1 < len(d['shots']):
            nxt = d['shots'][idx + 1]
            nxt['versions'].insert(0, {**{k: v for k, v in nxt.items() if k != 'versions'}, 'saved_at': now()})
            nxt['reference'] = ident
            bound_shot = nxt['id']
        else:
            new_shot = {
                'id': uuid.uuid4().hex,
                'title': f'{base_title} · continuation',
                'prompt': '',
                'duration': src_shot.get('duration', 5),
                'resolution': src_shot.get('resolution', '1080P'),
                'model': src_shot.get('model', 'h3'),
                'workflow': src_shot.get('workflow'),
                'seed': 2711,
                'reference': ident,
                'output': None,
                'versions': [],
                'x': src_shot.get('x', 220) + 460,
                'y': src_shot.get('y', 80)
            }
            d['shots'].append(new_shot)
            bound_shot = new_shot['id']
    elif target_mode not in ('none', None, ''):
        explicit = next((s for s in d['shots'] if s['id'] == target_mode), None)
        if explicit:
            explicit['versions'].insert(0, {**{k: v for k, v in explicit.items() if k != 'versions'}, 'saved_at': now()})
            explicit['reference'] = ident
            bound_shot = explicit['id']

    save(d)
    return {'ok': True, 'asset': new_asset, 'bound_shot': bound_shot, 'timestamp': frame_info.get('timestamp')}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}'):
            return self.reply({'error': 'invalid host'}, 403)
        path = self.path.split('?')[0]
        if path == '/api/capabilities':
            return self.reply(capabilities())
        if path == '/api/camera-presets':
            from drama_studio import CAMERA_PRESETS
            return self.reply(CAMERA_PRESETS)
        if path == '/api/model-presets':
            from model_presets import list_presets
            return self.reply(list_presets())
        if path == '/api/monitor':
            return self.reply(get_monitor().status())
        if path == '/api/elements':
            return self.reply(load().get('elements', []))
        if path == '/api/workflows':
            return self.reply(load().get('workflows', []))
        if path == '/api/assembly/plan':
            from timeline_export import probe_media, resolve_asset_file
            ws = load()
            assets_by_id = {a['id']: a for a in ws.get('assets', [])}
            video_shots = []
            for s in ws.get('shots', []):
                a = assets_by_id.get(s.get('output') or '')
                if not a or a.get('kind') != 'video':
                    continue
                try:
                    fp = resolve_asset_file(sys.modules[__name__], a)
                    meta = probe_media(ROOT, fp)
                    video_shots.append({
                        'shot_id': s['id'], 'title': s['title'], 'asset_id': a['id'], 'file': a['file'],
                        'duration': round(float(meta['duration']), 3), 'width': meta['width'], 'height': meta['height'],
                        'fps': meta['fps'], 'has_audio': meta['has_audio'],
                        'dialogue': s.get('dialogue', ''), 'subtitle_en': s.get('subtitle_en', '')
                    })
                except Exception:
                    continue
            audio_assets = []
            for a in ws.get('assets', []):
                if a.get('kind') != 'audio':
                    continue
                try:
                    fp = resolve_asset_file(sys.modules[__name__], a)
                    meta = probe_media(ROOT, fp)
                    audio_assets.append({'asset_id': a['id'], 'name': a['name'], 'file': a['file'], 'duration': round(float(meta['duration']), 3)})
                except Exception:
                    audio_assets.append({'asset_id': a['id'], 'name': a['name'], 'file': a['file'], 'duration': 0.0})
            return self.reply({'project_id': ws['project']['id'], 'settings': ws.get('assembly'), 'shots': video_shots, 'audios': audio_assets, 'final_file': bool(ws['project'].get('final_file') and Path(ws['project']['final_file']).is_file())})
        if path == '/api/project/final-media':
            ws = load()
            ff = ws.get('project', {}).get('final_file')
            if not ff or not Path(ff).is_file():
                return self.reply({'error': 'not found'}, 404)
            return self.media_file(Path(ff))
        if path.startswith('/templates/'):
            name = Path(path).name
            f = ROOT / 'assets/workflow-templates' / name
            if not f.is_file() or f.suffix != '.json':
                return self.reply({'error': 'not found'}, 404)
            raw = f.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Disposition', 'attachment; filename="' + name + '"')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == '/api/workspace':
            return self.reply(load())
        if path == '/api/status':
            try:
                return self.reply(refresh())
            except Exception as e:
                return self.reply({'error': str(e)}, 502)
        if path == '/api/verified':
            record = DATA / 'verified_state.json'
            return self.reply(json.loads(record.read_text()) if record.exists() else {'gpu': '尚未验证', 'ram_gib': '—', 'torch': '—', 'cuda': '—', 'comfy_revision': '', 'backup_path': '尚未配置', 'backup_status': '尚未验证', 'video_inference_status': '尚未验证'})
        if path == '/api/operations':
            return self.reply(CONSOLE.all())
        if path == '/api/inspection':
            return self.reply(inspection())
        if path == '/api/projects':
            return self.reply(projects())
        if path == '/api/bridge':
            from runtime.local_bridge import status
            return self.reply(status(sys.modules[__name__]))
        if path == '/api/session-url':
            return self.reply({'error': '官方网页接入链接实测会误开CPU，已停用。请使用管理台的挂载模型云盘。'}, 409)
        if path == '/api/account/login':
            return self.reply(LOGIN.status())
        if path == '/account/authorize':
            try:
                url = LOGIN.redirect()
            except ValueError as e:
                return self.reply({'error': str(e)}, 400)
            self.send_response(302)
            self.send_header('Location', url)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return
        if path == '/api/health':
            return self.reply({'ok': True, 'version': VERSION, 'data': str(DATA), 'gpu_policy': 'G4 only'})
        if path.startswith('/api/export/'):
            d = load()
            ident = path.rsplit('/', 1)[1]
            job = next((j for j in d['jobs'] if j['id'] == ident), None)
            shot = job['config'] if job else next((s for s in d['shots'] if s['id'] == ident), None)
            try:
                return self.reply(export_shot(shot, d)) if shot else self.reply({'error': '任务不存在'}, 404)
            except ValueError as e:
                return self.reply({'error': str(e)}, 400)
        if path.startswith('/licenses/'):
            from license_resources import resolve_license
            f = resolve_license(ROOT, unquote(path[len('/licenses/'):]))
            if f is None:
                return self.reply({'error': 'not found'}, 404)
        elif path.startswith('/assets/'):
            name = unquote(Path(path).name)
            ws = load()
            asset = next((a for a in ws['assets'] if a['file'] == name), None)
            f = Path(asset.get('path') or ASSETS / name) if asset else ASSETS / name
            explicit_registered = bool(asset and asset.get('path') and Path(asset['path']).resolve() == f.resolve())
            if not explicit_registered and not f.resolve().is_relative_to(ASSETS.resolve()) and not f.resolve().is_relative_to(SOURCE.resolve()) and not f.resolve().is_relative_to((DATA / 'results').resolve()):
                return self.reply({'error': 'invalid asset path'}, 403)
        elif path.startswith('/exports/'):
            f = (DATA / 'exports' / Path(path).name).resolve()
            if not f.is_relative_to((DATA / 'exports').resolve()):
                return self.reply({'error': 'invalid export path'}, 403)
        elif path in ('/', '/studio', '/manager'):
            f = WEB / 'index.html'
        else:
            f = WEB / Path(path).name
        if not f.is_file():
            return self.reply({'error': 'not found'}, 404)
        if f.suffix.lower() in ('.mp4', '.webm', '.wav', '.mp3', '.flac', '.ogg', '.m4a'):
            return self.media_file(f)
        if path.startswith('/exports/'):
            raw = f.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(f.name)[0] or 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{f.name}"')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(raw)
            return
        body = f.read_bytes()
        if f.suffix == '.html':
            body = body.replace(b'__LOCAL_KEY__', KEY.encode())
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(f.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def media_file(self, f):
        size = f.stat().st_size
        start = 0
        end = size - 1
        status = 200
        value = self.headers.get('Range')
        if value:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
            if not match or not any(match.groups()):
                return self.reply({'error': 'unsupported range'}, 416)
            a, b = match.groups()
            if a:
                start = int(a)
                end = min(int(b), size - 1) if b else size - 1
            else:
                start = max(0, size - int(b))
            if start >= size or start > end:
                return self.reply({'error': 'range outside file'}, 416)
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', mimetypes.guess_type(f.name)[0] or 'application/octet-stream')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command == 'HEAD':
            return
        try:
            with f.open('rb') as reader:
                reader.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = reader.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}') or self.headers.get('X-Local-Key') != KEY:
            return self.reply({'error': '需要本机页面授权'}, 403)
        try:
            length = int(self.headers.get('Content-Length', 0))
            if self.path == '/api/local-restore-file':
                if OP_LOCK.locked() or any(x['state'] in ('queued', 'running') for x in CONSOLE.all()):
                    raise ValueError('请等当前操作结束后导入项目')
                if not 0 < length <= 100 * 1024 ** 3:
                    raise ValueError('Invalid project backup size')
                cache = DATA / 'cache'
                cache.mkdir(exist_ok=True)
                archive = cache / ('restore-' + uuid.uuid4().hex + '.zip')
                try:
                    with archive.open('xb') as out:
                        remaining = length
                        while remaining:
                            block = self.rfile.read(min(1024 ** 2, remaining))
                            if not block:
                                raise ValueError('Project backup upload was interrupted')
                            out.write(block)
                            remaining -= len(block)
                    from workspace_backup import import_project_file
                    return self.reply(import_project_file(sys.modules[__name__], archive))
                finally:
                    archive.unlink(missing_ok=True)
            if length > 140_000_000:
                raise ValueError('素材请小于100MB')
            b = json.loads(self.rfile.read(length))
            d = load()
            path = self.path
            if path == '/api/model-terms':
                from model_terms import describe_config
                model = b.get('model')
                name = next((item['name'] for item in MODELS if item['id'] == model), 'ComfyUI workflow')
                recipe = next((w for w in d.get('workflows', []) if w.get('id') == b.get('workflow')), None)
                return self.reply(describe_config({'model': model, 'recipe': recipe}, name=name))
            if path == '/api/storyboard/handoff':
                from storyboard_handoff import prepare, freeze_assets
                from runtime.local_bridge import status as bridge_status
                if any(o['state'] in ('queued', 'running') for o in CONSOLE.all()):
                    raise ValueError('Wait for current operations before handing off the storyboard.')
                guarded()
                current = refresh()
                bridge = bridge_status(sys.modules[__name__])
                if current.get('runtime_state') != 'owned' or not bridge.get('ready') or bridge.get('endpoint') != current.get('managed_session', {}).get('endpoint'):
                    raise ValueError('Connect the owned cloud ComfyUI canvas first. No GPU was allocated.')
                if b.get('cloud_data_consent') is not True:
                    raise ValueError('Confirm sending the selected original media, prompts and project context to your runtime.')
                payload = prepare(d, ASSETS, b.get('shots'), include_assets=True, asset_ids=b.get('assets'))
                raw = json.dumps(payload, ensure_ascii=False).encode()
                if len(raw) > 30 * 1024 ** 2:
                    raise ValueError('Select fewer shots: the handoff metadata exceeds 30 MB.')
                directory = DATA / 'cache' / 'comfy-handoffs'
                directory.mkdir(parents=True, exist_ok=True)
                token = secrets.token_hex(16)
                record = directory / (token + '.json')
                try:
                    freeze_assets(d, ASSETS, payload, directory/token)
                except Exception:
                    shutil.rmtree(directory/token, ignore_errors=True)
                    raise
                record.write_bytes(raw)
                record.chmod(0o600)
                return self.reply({'url': bridge['url'] + '?cineharbor_handoff=' + token, 'shots': len(payload['shots']), 'assets':len(payload['assets']), 'bytes':sum(a['bytes'] for a in payload['assets']), 'queued': False})
            if path == '/api/runtime/interrupt':
                return self.reply(CONSOLE.interrupt_active())
            if path == '/api/operations/cancel-queued':
                return self.reply(CONSOLE.cancel_queued(b.get('id')))
            if path.startswith('/api/runtime/') or path == '/api/operations':
                action = path.rsplit('/', 1)[1] if path.startswith('/api/runtime/') else b['action']
                if action in ('generate', 'generate_batch') and not (b.get('cloud_data_consent') is True and b.get('cloud_data_notice_version') == '2026-11-21'):
                    raise ValueError('请先阅读云端数据说明并明确同意本次发送到 Google Colab；未提交生成任务。')
                return self.reply(CONSOLE.start(action, b), 202)
            if path == '/api/local-backup':
                return self.reply(local_backup())
            if path == '/api/local-restore':
                if OP_LOCK.locked() or any(x['state'] in ('queued', 'running') for x in CONSOLE.all()):
                    raise ValueError('请等当前操作结束后导入项目')
                from workspace_backup import import_project
                return self.reply(import_project(sys.modules[__name__], base64.b64decode(b['data'], validate=True)))
            if path == '/api/monitor/toggle':
                mon = get_monitor()
                return self.reply(mon.start() if b.get('enabled') else mon.stop())
            if path == '/api/workflow/convert':
                from workflow_converter import convert_canvas_to_api, load_cached_object_info
                from workflow_library import recipe
                from model_presets import get_preset, upgrade_graph_to_preset
                matched_preset = None
                if b.get('template'):
                    tname = Path(str(b['template'])).name
                    if not tname.endswith('.json'):
                        tname += '.json'
                    tf = ROOT / 'assets/workflow-templates' / tname
                    if not tf.is_file():
                        raise ValueError('内置官方模板不存在。')
                    canvas = json.loads(tf.read_text())
                    default_name = str(b.get('name') or tf.stem)
                    if not b.get('raw_precision'):
                        matched_preset = get_preset(template_name=tname)
                else:
                    canvas = b.get('canvas')
                    default_name = str(b.get('name') or '导入工作流')
                converted = convert_canvas_to_api(canvas, object_info=load_cached_object_info(DATA))
                if matched_preset:
                    converted['graph'] = upgrade_graph_to_preset(converted['graph'], matched_preset)
                    converted['model_files'] = matched_preset['model_files']
                if b.get('save'):
                    if d['project'].get('status') == 'completed':
                        raise ValueError('已结项项目只读，请新建项目。')
                    saved = recipe({'name': default_name, **converted})
                    d.setdefault('workflows', []).append(saved)
                    save(d)
                    return self.reply(saved)
                return self.reply({'name': default_name, **converted})
            if path == '/api/workflow/apply-preset':
                from model_presets import get_preset, upgrade_graph_to_preset
                from workflow_library import recipe
                if d['project'].get('status') == 'completed':
                    raise ValueError('已结项项目只读，请新建项目。')
                preset = get_preset(preset_id=b.get('preset_id'))
                if not preset:
                    raise ValueError('未找到所选的全精度模型预设。')
                items = d.setdefault('workflows', [])
                old = next((x for x in items if x['id'] == b.get('workflow_id')), None)
                if not old:
                    raise ValueError('工作流不存在，请先保存或选择工作流。')
                upgraded_graph = upgrade_graph_to_preset(old['graph'], preset)
                updated = recipe({**old, 'graph': upgraded_graph, 'model_files': preset['model_files']}, old)
                items[items.index(old)] = updated
                save(d)
                return self.reply(updated)
            if path == '/api/shot/select-take':
                if d['project'].get('status') == 'completed':
                    raise ValueError('已结项项目只读。')
                shot = next((s for s in d['shots'] if s['id'] == b.get('shot_id')), None)
                if not shot:
                    raise ValueError('镜头不存在。')
                aid = b.get('asset_id')
                if not any(a['id'] == aid for a in d['assets']):
                    raise ValueError('候选样片素材不存在。')
                shot['versions'].insert(0, {**{k: v for k, v in shot.items() if k != 'versions'}, 'saved_at': now()})
                shot['output'] = aid
                shot.pop('qc_strip_file', None)
                save(d)
                return self.reply({'ok': True, 'output': aid})
            if path in ('/api/element', '/api/element/delete'):
                if d['project'].get('status') == 'completed':
                    raise ValueError('已结项项目只读。')
                elems = d.setdefault('elements', [])
                if path.endswith('/delete'):
                    target = next((e for e in elems if e['id'] == b.get('id')), None)
                    if not target:
                        raise ValueError('角色/场景参考卡不存在。')
                    elems.remove(target)
                    for s in d['shots']:
                        if 'elements' in s and isinstance(s['elements'], list):
                            s['elements'] = [eid for eid in s['elements'] if eid != target['id']]
                    save(d)
                    return self.reply({'ok': True})
                tag = str(b.get('tag', '')).strip().lstrip('@')[:40]
                if not tag:
                    raise ValueError('请填写角色/场景名称（如：艾伦、火星基地）。')
                ekind = b.get('kind', 'character')
                if ekind not in ('character', 'scene', 'prop'):
                    raise ValueError('资产卡类型须为 character、scene 或 prop。')
                snippet = str(b.get('prompt_snippet', '')).strip()[:1000]
                asset_ref = b.get('asset_id') or None
                if asset_ref and not any(a['id'] == asset_ref and a['kind'] == 'image' for a in d['assets']):
                    raise ValueError('关联参考图不存在或不是图像。')
                voice_ref = b.get('voice_asset_id') or None
                if voice_ref and not any(a['id'] == voice_ref and a['kind'] == 'audio' for a in d['assets']):
                    raise ValueError('关联音色样本不存在或不是音频。')
                voice_prof = str(b.get('voice_profile', '')).strip()[:240]
                existing = next((e for e in elems if e['id'] == b.get('id')), None)
                if existing:
                    existing.update(tag=tag, kind=ekind, prompt_snippet=snippet, asset_id=asset_ref)
                    if 'voice_asset_id' in b:
                        existing['voice_asset_id'] = voice_ref
                    if 'voice_profile' in b:
                        existing['voice_profile'] = voice_prof
                    item = existing
                else:
                    item = {'id': uuid.uuid4().hex, 'tag': tag, 'kind': ekind, 'prompt_snippet': snippet, 'asset_id': asset_ref, 'voice_asset_id': voice_ref, 'voice_profile': voice_prof, 'created': now()}
                    elems.append(item)
                save(d)
                return self.reply(item)
            if path == '/api/script/breakdown':
                from drama_studio import breakdown_script_to_storyboard
                return self.reply(breakdown_script_to_storyboard(sys.modules[__name__], d, b))
            if path == '/api/element/turnaround':
                from drama_studio import prepare_character_turnaround_job
                return self.reply(prepare_character_turnaround_job(sys.modules[__name__], d, b))
            if path == '/api/drama/nine-grid':
                from drama_studio import prepare_nine_grid_storyboard_job
                return self.reply(prepare_nine_grid_storyboard_job(sys.modules[__name__], d, b))
            if path == '/api/drama/slice-grid':
                from drama_studio import slice_grid_to_shots
                return self.reply(slice_grid_to_shots(sys.modules[__name__], d, b))
            if path == '/api/element/extract-voice':
                from drama_studio import extract_voice_sample_to_element
                return self.reply(extract_voice_sample_to_element(sys.modules[__name__], d, b))
            if path == '/api/shot/qc-filmstrip':
                from drama_studio import generate_shot_qc_filmstrip
                return self.reply(generate_shot_qc_filmstrip(sys.modules[__name__], d, b))
            if path == '/api/assembly/storyboard-sheet':
                from drama_studio import export_storyboard_sheet_png
                return self.reply(export_storyboard_sheet_png(sys.modules[__name__], d, b))
            if path == '/api/assembly/srt':
                from timeline_export import export_srt_subtitles
                return self.reply(export_srt_subtitles(sys.modules[__name__], d, b))
            if path == '/api/shot/derive-keyframe':
                from workflow_library import recipe
                if d['project'].get('status') == 'completed':
                    raise ValueError('已结项项目只读，请新建项目。')
                shot = next((s for s in d['shots'] if s['id'] == b.get('shot_id')), None)
                if not shot:
                    raise ValueError('请先选择要派生锁脸首帧的分镜。')
                bound_elems = [e for e in d.get('elements', []) if e['id'] in (shot.get('elements') or [])]
                anchor_asset = b.get('anchor_asset') or next((e['asset_id'] for e in bound_elems if e.get('asset_id')), None) or shot.get('reference')
                if not anchor_asset or not any(a['id'] == anchor_asset and a['kind'] == 'image' for a in d['assets']):
                    raise ValueError('请先为关联的 @角色/道具卡 绑定定妆参考图，或在分镜中选择首帧参考图。')
                target_slot = 'end_reference' if b.get('slot') == 'end_reference' else 'reference'
                angle_prompt = str(b.get('edit_prompt') or shot.get('prompt') or '').strip()
                if not angle_prompt:
                    raise ValueError('请填写本镜的景别、机位或动作描述。')
                wf_name = 'Qwen Image Edit 2511 · 完整 BF16 锁脸分镜配方'
                wf_edit = next((w for w in d.get('workflows', []) if w.get('name') == wf_name), None)
                if not wf_edit:
                    from model_presets import get_preset
                    preset = get_preset(preset_id='qwen_image_edit_2511_bf16')
                    def _n(kind, **inputs):
                        return {'class_type': kind, 'inputs': inputs}
                    edit_graph = {
                        '1': _n('UNETLoader', unet_name='qwen_image_edit_2511_bf16.safetensors', weight_dtype='default'),
                        '2': _n('CLIPLoader', clip_name='qwen_2.5_vl_7b.safetensors', type='qwen_image', device='default'),
                        '3': _n('VAELoader', vae_name='qwen_image_vae.safetensors'),
                        '4': _n('ModelSamplingAuraFlow', model=['1', 0], shift=3.1),
                        '5': _n('CFGNorm', model=['4', 0], strength=1.0),
                        '6': _n('LoraLoaderModelOnly', model=['5', 0], lora_name='Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors', strength_model=1.0),
                        '7': _n('LoadImage', image='anchor.png'),
                        '8': _n('TextEncodeQwenImageEditPlus', clip=['2', 0], vae=['3', 0], image1=['7', 0], prompt=''),
                        '9': _n('TextEncodeQwenImageEditPlus', clip=['2', 0], vae=['3', 0], image1=['7', 0], prompt=''),
                        '10': _n('FluxKontextMultiReferenceLatentMethod', conditioning=['8', 0], reference_latents_method='index_timestep_zero'),
                        '11': _n('FluxKontextMultiReferenceLatentMethod', conditioning=['9', 0], reference_latents_method='index_timestep_zero'),
                        '12': _n('EmptySD3LatentImage', width=1920, height=1088, batch_size=1),
                        '13': _n('KSampler', model=['6', 0], positive=['10', 0], negative=['11', 0], latent_image=['12', 0], seed=1024, steps=4, cfg=1.0, sampler_name='euler', scheduler='simple', denoise=1.0),
                        '14': _n('VAEDecode', samples=['13', 0], vae=['3', 0]),
                        '15': _n('SaveImage', images=['14', 0], filename_prefix='GC_Labs_QwenEdit'),
                    }
                    wf_edit = recipe({
                        'name': wf_name,
                        'kind': 'image',
                        'graph': edit_graph,
                        'bindings': {
                            'reference': [{'node': '7', 'input': 'image'}],
                            'prompt': [{'node': '8', 'input': 'prompt'}],
                            'negative_prompt': [{'node': '9', 'input': 'prompt'}],
                            'width': [{'node': '12', 'input': 'width'}],
                            'height': [{'node': '12', 'input': 'height'}],
                            'seed': [{'node': '13', 'input': 'seed'}],
                        },
                        'model_files': preset['model_files'] if preset else [],
                    })
                    d.setdefault('workflows', []).append(wf_edit)
                char_hint = ' '.join(f"Keep exact character/prop identity from Picture 1 ({e['tag']}: {e['prompt_snippet']})." for e in bound_elems if e.get('prompt_snippet'))
                full_edit_prompt = (char_hint + ' ' + angle_prompt).strip()
                job = {
                    'id': uuid.uuid4().hex,
                    'shot': shot['id'],
                    'bind_slot': target_slot,
                    'title': f"{shot['title']} · {'锁脸尾帧派生' if target_slot == 'end_reference' else '锁脸首帧派生'}",
                    'state': 'prepared',
                    'created': now(),
                    'config': {
                        'title': shot['title'],
                        'prompt': full_edit_prompt,
                        'negative_prompt': '',
                        'duration': 5,
                        'resolution': shot.get('resolution', '1080P'),
                        'model': 'workflow',
                        'workflow': wf_edit['id'],
                        'seed': int(b.get('seed') or shot.get('seed') or 1024),
                        'reference': anchor_asset,
                        'ratio': d['project']['ratio'],
                        'recipe': {k: copy.deepcopy(wf_edit.get(k)) for k in ('id', 'name', 'kind', 'graph', 'bindings', 'model_files', 'custom_nodes', 'timing', 'revision')},
                    },
                    'message': '已创建 Qwen Image Edit 2511 BF16 锁脸分镜图任务；生成完成后将自动回填本镜参考图。'
                }
                d['jobs'].insert(0, job)
                save(d)
                return self.reply({'ok': True, 'job': job, 'workflow_id': wf_edit['id']})
            if path == '/api/shot/chain-frame':
                return self.reply(_chain_shot_frame(d, b))
            if path == '/api/assembly/render':
                from timeline_export import render_rough_cut_mp4
                result = render_rough_cut_mp4(sys.modules[__name__], d, b)
                result['asset_id'] = record_local_film(d['project']['id'], result)
                return self.reply(result)
            if path == '/api/assembly/settings':
                from timeline_export import assembly_settings
                if d['project'].get('status') == 'completed':
                    raise ValueError('已结项项目只读。')
                d['assembly'] = assembly_settings(d, b)
                save(d)
                return self.reply({'ok': True, 'settings': d['assembly']})
            if path == '/api/assembly/fcpxml':
                from timeline_export import export_fcpxml
                return self.reply(export_fcpxml(sys.modules[__name__], d, b))
            if path == '/api/assembly/capcut':
                from timeline_export import export_capcut_draft
                return self.reply(export_capcut_draft(sys.modules[__name__], d, b))
            if path.startswith('/api/account/login/'):
                if (DATA / 'lease.json').exists() or OP_LOCK.locked() or any(x['state'] in ('queued', 'running') for x in CONSOLE.all()):
                    raise ValueError('请先完成当前任务、保存并释放GPU，再切换登录。')
                if path.endswith('/begin'):
                    return self.reply(LOGIN.begin())
                if path.endswith('/submit'):
                    return self.reply(LOGIN.submit(b.get('code')))
                if path.endswith('/cancel'):
                    return self.reply(LOGIN.cancel())
                raise ValueError('未知登录操作')
            if path in ('/api/workflow', '/api/workflow/delete'):
                from workflow_library import recipe
                if d['project'].get('status') == 'completed':
                    raise ValueError('已结项项目只读，请新建项目。')
                items = d.setdefault('workflows', [])
                old = next((x for x in items if x['id'] == b.get('id')), None)
                if b.get('id') and not old:
                    raise ValueError('工作流不存在。')
                if old and b.get('base_revision') != old['revision']:
                    raise ValueError('工作流已更新，请重新打开，避免覆盖新版本。')
                if path.endswith('/delete'):
                    if not old:
                        raise ValueError('工作流不存在。')
                    d.setdefault('workflow_trash', []).append(old)
                    items.remove(old)
                    for shot in d['shots']:
                        if shot.get('workflow') == old['id']:
                            shot['workflow'] = None
                    save(d)
                    return self.reply({'ok': True})
                item = recipe(b, old)
                if old:
                    items[items.index(old)] = item
                else:
                    items.append(item)
                save(d)
                return self.reply(item)
            if path == '/api/job/archive':
                if d['project'].get('status') == 'completed':
                    raise ValueError('Completed projects are read-only.')
                job = next((j for j in d['jobs'] if j.get('id') == b.get('id')), None)
                if not job or job.get('state') != 'prepared' or job.get('attempted'):
                    raise ValueError('Only unsubmitted tasks can be discarded.')
                if any(op.get('job_id') == job['id'] and op.get('state') in ('queued', 'running') for op in CONSOLE.all()):
                    raise ValueError('Remove this task from the waiting queue first.')
                d.setdefault('historical_jobs', []).append(dict(job, state='cancelled'))
                d['jobs'].remove(job)
                save(d)
                return self.reply({'ok': True})
            if path == '/api/shot/delete':
                if d['project'].get('status') == 'completed':
                    raise ValueError('已结项项目只读。')
                target = next((s for s in d['shots'] if s['id'] == b.get('id')), None)
                if not target:
                    raise ValueError('镜头不存在。')
                related = [j for j in d['jobs'] if j.get('shot') == target['id']]
                related_ids = {j['id'] for j in related}
                if any(j.get('state') in ('queued', 'connecting', 'running') for j in related) or any(
                    op.get('job_id') in related_ids and op.get('state') in ('queued', 'running') for op in CONSOLE.all()
                ):
                    raise ValueError('镜头任务运行中，不能移除。')
                for job in related:
                    if job.get('state') == 'prepared' and not job.get('attempted'):
                        d.setdefault('historical_jobs', []).append(dict(job, state='cancelled'))
                        d['jobs'].remove(job)
                d.setdefault('shot_trash', []).append(target)
                d['shots'].remove(target)
                save(d)
                return self.reply({'ok': True})
            if path == '/api/layout':
                if d['project'].get('status') == 'completed':
                    raise ValueError('已结项项目只读。')
                for pos in b.get('shots', []):
                    target = next((s for s in d['shots'] if s['id'] == pos['id']), None)
                    if not target or not all(isinstance(pos.get(k), (int, float)) and abs(pos[k]) <= 50000 for k in ('x', 'y')):
                        raise ValueError('画布位置无效。')
                    target.update(x=pos['x'], y=pos['y'])
                if 'order' in b:
                    if sorted(b['order']) != sorted(s['id'] for s in d['shots']):
                        raise ValueError('镜头顺序无效。')
                    lookup = {s['id']: s for s in d['shots']}
                    d['shots'] = [lookup[i] for i in b['order']]
                save(d)
                return self.reply({'ok': True})
            if path == '/api/account/bind':
                return self.reply(bind_account(b.get('email')))
            if path == '/api/drive/continue':
                if not any(x.get('action') == 'mount' and x.get('state') == 'running' and x.get('stage') == 'authorization_required' for x in CONSOLE.all()):
                    raise ValueError('没有等待授权的挂载任务')
                import urllib.request
                request = urllib.request.Request('http://127.0.0.1:8768/continue', data=b'{}', headers={'X-GC-Local': '1'})
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as response:
                    response.read()
                return self.reply({'ok': True})
            if path in ('/api/project/new', '/api/project/select', '/api/project/delete'):
                if any(x['state'] in ('queued', 'running') for x in CONSOLE.all()):
                    raise ValueError('操作运行中，请完成后切换项目')
                directory = DATA / 'projects'
                directory.mkdir(exist_ok=True)
                (directory / (d['project']['id'] + '.json')).write_text(json.dumps(d, ensure_ascii=False, indent=2))
                if path.endswith('/delete'):
                    candidates = [p for p in directory.glob('*.json') if p.stem != d['project']['id']]
                    if not candidates:
                        raise ValueError('请先创建另一个项目，再移除此项目')
                    trash = DATA / 'project-trash'
                    trash.mkdir(exist_ok=True)
                    shutil.move(directory / (d['project']['id'] + '.json'), trash / (d['project']['id'] + '_' + str(int(time.time())) + '.json'))
                    d = json.loads(candidates[0].read_text())
                elif path.endswith('/new'):
                    name = str(b.get('name', '')).strip()[:80]
                    if not name:
                        raise ValueError('请填写项目名称')
                    ratio = b.get('ratio', '9:16') if b.get('ratio') in ('9:16', '16:9', '1:1') else '9:16'
                    d = {
                        'schema_version': 2,
                        'project': {'id': uuid.uuid4().hex, 'name': name, 'ratio': ratio, 'description': '', 'status': 'active'},
                        'assets': [], 'elements': [], 'shots': [], 'workflows': [], 'jobs': [], 'historical_jobs': [], 'events': [],
                        'models': copy.deepcopy(d['models']), 'policy': copy.deepcopy(d['policy'])
                    }
                else:
                    ident = str(b['id'])
                    if not re.fullmatch(r'[a-zA-Z0-9_-]+', ident):
                        raise ValueError('无效项目')
                    d = json.loads((directory / (ident + '.json')).read_text())
                save(d)
                return self.reply({'ok': True})
            if d['project'].get('status') == 'completed' and path in ('/api/shot', '/api/shot/new', '/api/asset', '/api/job'):
                raise ValueError('该项目已结项，请新建项目后制作。')
            if path == '/api/shot':
                shot = next(s for s in d['shots'] if s['id'] == b['id'])
                shot['versions'].insert(0, {**{k: v for k, v in shot.items() if k != 'versions'}, 'saved_at': now()})
                for k in ('title', 'prompt', 'negative_prompt', 'dialogue', 'subtitle_en', 'camera_move', 'shot_scale', 'duration', 'resolution', 'model', 'seed', 'reference', 'end_reference', 'x', 'y', 'workflow'):
                    if k in b:
                        shot[k] = b[k]
                if 'elements' in b and isinstance(b['elements'], list):
                    valid_ids = {e['id'] for e in d.get('elements', [])}
                    shot['elements'] = [eid for eid in b['elements'] if eid in valid_ids]
                chosen = next((w for w in d.get('workflows', []) if w['id'] == shot.get('workflow')), None)
                limit = 600 if shot.get('model') == 'workflow' and chosen and chosen['kind'] == 'audio' else 15
                if not 1 <= float(shot['duration']) <= limit:
                    raise ValueError('时长须为1–' + str(limit) + '秒')
                if shot['resolution'] not in ('480P', '720P', '768P', '1080P'):
                    raise ValueError('不支持的分辨率')
                if shot['model'] not in ({m['id'] for m in d['models']} | {'workflow'}):
                    raise ValueError('未知模型')
            elif path == '/api/shot/new':
                d['shots'].append({'id': uuid.uuid4().hex, 'title': 'New shot', 'prompt': '', 'duration': 5, 'resolution': '1080P', 'model': 'h3', 'seed': 2711, 'reference': None, 'end_reference': None, 'output': None, 'versions': [], 'x': 220 + len(d['shots']) * 340, 'y': 80})
            elif path == '/api/asset':
                ext = Path(b['name']).suffix.lower()
                if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.mp4', '.webm', '.wav', '.mp3', '.flac', '.ogg', '.m4a'):
                    raise ValueError('不支持的素材格式')
                raw = base64.b64decode(b['data'], validate=True)
                if len(raw) > 100_000_000:
                    raise ValueError('素材请小于100MB')
                ident = uuid.uuid4().hex
                name = ident + ext
                (ASSETS / name).write_bytes(raw)
                d['assets'].append({
                    'id': ident,
                    'name': b['name'],
                    'file': name,
                    'sha256': hashlib.sha256(raw).hexdigest(),
                    'kind': 'video' if ext in ('.mp4', '.webm') else 'audio' if ext in ('.mp3', '.wav', '.flac', '.ogg', '.m4a') else 'image',
                    'created': now()
                })
            elif path == '/api/job':
                shot = next(s for s in d['shots'] if s['id'] == b['shot'])
                bound_elems = [e for e in d.get('elements', []) if e['id'] in (shot.get('elements') or [])]
                base_prompt = (shot.get('prompt') or '').strip()
                elem_snippets = [f"[{e['tag']}: {e['prompt_snippet']}]" for e in bound_elems if e.get('prompt_snippet') and e['prompt_snippet'] not in base_prompt]
                voice_snippets = [f"[{e['tag']} vocal timbre: {e['voice_profile']}]" for e in bound_elems if e.get('voice_profile') and e['voice_profile'] not in base_prompt]
                dial = (shot.get('dialogue') or '').strip()
                dial_snippet = f'Synchronized expressive lip-sync speech in the original language of this dialogue: "{dial}".' if dial and dial not in base_prompt else ''
                effective_prompt = ' '.join(x for x in [' '.join(elem_snippets), ' '.join(voice_snippets), base_prompt, dial_snippet] if x).strip()
                if not effective_prompt:
                    raise ValueError('请先填写提示词')
                if len(effective_prompt) > 200000:
                    raise ValueError('提示词过长。')
                effective_ref = shot.get('reference') or next((e['asset_id'] for e in bound_elems if e.get('asset_id')), None)
                recipe_item = next((w for w in d.get('workflows', []) if w['id'] == shot.get('workflow')), None)
                if shot.get('model') == 'workflow' and not recipe_item:
                    raise ValueError('请选择工作流。')
                needs_reference = shot.get('model') != 'workflow' or bool(recipe_item.get('bindings', {}).get('reference'))
                if needs_reference and not any(a['id'] == effective_ref and a['kind'] == 'image' for a in d['assets']):
                    raise ValueError('请先选择参考图（或绑定带参考图的角色/场景资产卡）')
                effective_end_ref = shot.get('end_reference') or None
                if effective_end_ref and not any(a['id'] == effective_end_ref and a['kind'] == 'image' for a in d['assets']):
                    raise ValueError('所选尾帧锁死参考图不存在或不是图像。')
                shot_snapshot = {k: copy.deepcopy(shot.get(k)) for k in ('title', 'prompt', 'negative_prompt', 'dialogue', 'subtitle_en', 'camera_move', 'shot_scale', 'duration', 'resolution', 'model', 'seed', 'reference', 'end_reference', 'workflow', 'elements')}
                shot_snapshot['prompt'] = effective_prompt
                shot_snapshot['reference'] = effective_ref
                shot_snapshot['end_reference'] = effective_end_ref
                job = {
                    'id': uuid.uuid4().hex,
                    'shot': shot['id'],
                    'title': shot['title'],
                    'state': 'prepared',
                    'created': now(),
                    'config': {
                        **shot_snapshot,
                        'ratio': d['project']['ratio']
                    },
                    'message': '已保存独立任务快照；可单个或批量排队提交到G4。'
                }
                if recipe_item and shot.get('model') == 'workflow':
                    job['config']['recipe'] = {k: copy.deepcopy(recipe_item.get(k)) for k in ('id', 'name', 'kind', 'graph', 'bindings', 'model_files', 'custom_nodes', 'timing', 'revision')}
                d['jobs'].insert(0, job)
            elif path == '/api/policy':
                minutes = int(b.get('max_minutes', 240))
                if not 5 <= minutes <= 1440:
                    raise ValueError('提醒时间须为 5–1440 分钟')
                budget = float(b.get('max_cu_budget', d['policy'].get('max_cu_budget', 0)) or 0)
                if not 0 <= budget <= 5000:
                    raise ValueError('单次会话算力预算须为 0（不限）或 0.1–5000 CU')
                d['policy'].update({'max_minutes': minutes, 'max_cu_budget': round(budget, 2), 'budget_paused': False, 'auto_release': False})
            elif path in ('/api/runtime/start', '/api/runtime/stop'):
                return self.reply(operation(path.rsplit('/', 1)[1], b))
            else:
                raise ValueError('未知操作')
            save(d)
            return self.reply({'ok': True})
        except Exception as e:
            return self.reply({'error': str(e)}, 400)


def cleanup_local_helpers():
    # Quit never releases a VM. Dispose only of this backend's owned local
    # viewer and monitoring listener, including after a cloud lease expires.
    from runtime.local_bridge import stop
    stop(sys.modules[__name__])
    if MONITOR is not None:
        MONITOR.stop()


if __name__ == '__main__':
    seed()
    migrate()
    from console import Console
    CONSOLE = Console(sys.modules[__name__])
    try:
        httpd = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError:
        if os.environ.get('GC_LABS_DYNAMIC_PORT') == '1':
            httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            PORT = httpd.server_port
        else:
            raise
    port_file = os.environ.get('GC_LABS_PORT_FILE')
    if port_file:
        Path(port_file).write_text(json.dumps({'port': PORT, 'version': VERSION}))
    print(f'Local: http://127.0.0.1:{PORT}/studio', flush=True)
    import signal
    def exit_local_backend(_signal, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, exit_local_backend)
    try:
        httpd.serve_forever()
    finally:
        try:
            cleanup_local_helpers()
        finally:
            httpd.server_close()
