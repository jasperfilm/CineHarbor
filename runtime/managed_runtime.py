"""Runs only inside the explicitly selected VM. No unconditional auto-shutdown."""
from pathlib import Path
import base64, hashlib, json, os, re, shutil, subprocess, sys, threading, time, urllib.error, urllib.request

ROOT = Path('/content/ComfyUI')
WORK = Path('/content/jasper_workstation')
WORK.mkdir(exist_ok=True)
BACKUP = Path('/content/drive/MyDrive/AI_Workstations/Jasper_Workstation')
H3 = Path('/content/drive/MyDrive/AI_Workstations/MiniMax_H3_official')


def event(stage, message, **extra):
    print('JASPER_EVENT ' + json.dumps(dict(stage=stage, message=message, **extra), ensure_ascii=False), flush=True)


def request(path, data=None):
    q = urllib.request.Request(
        'http://127.0.0.1:8188' + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(q, timeout=15) as f:
            raw = f.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')[-2500:]
        if path == '/prompt' and error.code == 400:
            event('rejected', 'ComfyUI验证拒绝，任务未入队', not_submitted=True)
        raise RuntimeError('ComfyUI HTTP ' + str(error.code) + ': ' + detail) from error


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(16 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def safe_child(root, rel):
    p = (root / rel).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError('清单包含越界路径')
    return p


def queue_idle():
    try:
        q = request('/queue')
    except Exception:
        # An unreachable backend may coexist with unrelated GPU work. Stop stays conservative.
        q = None
    if q and (q.get('queue_running') or q.get('queue_pending')):
        raise RuntimeError('ComfyUI 尚有运行或排队任务，请完成后备份/停止。')
    try:
        util = subprocess.check_output(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], text=True)
        if any(int(x.strip()) > 10 for x in util.splitlines() if x.strip()):
            raise RuntimeError('GPU 仍在工作，暂不执行备份后停止。')
    except FileNotFoundError:
        pass
    return q


def interrupt_sampling():
    request('/interrupt', {})
    event('interrupting', '已向 ComfyUI 发送中断当前采样指令；GPU 与已保存资产保留')
    return {'interrupted': True, 'at': time.time()}


def inspect():
    disk = shutil.disk_usage('/content')
    gpu = []
    try:
        gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu', '--format=csv,noheader'], text=True).strip().splitlines()
    except Exception:
        pass
    try:
        stats = request('/system_stats')
        queue = request('/queue')
        comfy = {'online': True, 'queue_running': len(queue.get('queue_running', [])), 'queue_pending': len(queue.get('queue_pending', [])), 'stats': stats}
    except Exception as e:
        comfy = {'online': False, 'error': type(e).__name__}
    manifests = []
    for folder in (H3, BACKUP / 'model_library'):
        for p in sorted(folder.glob('*manifest*.json')) if folder.exists() else []:
            try:
                d = json.loads(p.read_text())
                manifests.append({'name': p.name, 'complete': d.get('complete', True), 'files': len(d.get('files', [])), 'bytes': sum(x.get('bytes', 0) for x in d.get('files', []))})
            except Exception:
                pass
    models = []
    for p in (ROOT / 'models').rglob('*.safetensors') if (ROOT / 'models').exists() else []:
        models.append({'file': str(p.relative_to(ROOT / 'models')), 'bytes': p.stat().st_size})
    custom = []
    for p in sorted((ROOT / 'custom_nodes').iterdir()) if (ROOT / 'custom_nodes').exists() else []:
        if p.is_dir() and (p / '.git').exists():
            try:
                rev = subprocess.check_output(['git', '-C', str(p), 'rev-parse', 'HEAD'], text=True).strip()
                custom.append({'name': p.name, 'commit': rev})
            except Exception:
                pass
    return {'checked_at': time.time(), 'gpu': gpu, 'disk': {'total': disk.total, 'free': disk.free, 'used': disk.used}, 'drive_mounted': Path('/content/drive/MyDrive').is_dir(), 'comfy': comfy, 'models': models, 'custom_nodes': custom, 'backup_manifests': manifests}


def _reclaim_ephemeral_space(needed_bytes, keep_rels=()):
    margin = 8 * 2 ** 30
    if shutil.disk_usage('/content').free >= needed_bytes + margin:
        return
    try:
        request('/free', {'unload_models': True, 'free_memory': True})
    except Exception:
        pass
    if shutil.disk_usage('/content').free >= needed_bytes + margin:
        return
    # Evict only local /content weights that already exist verified on Google Drive
    keep = {str(Path(r)) for r in keep_rels}
    backed_up = set()
    for mf, base in ((BACKUP / 'model_library/manifest.json', BACKUP / 'model_library/models'), (H3 / 'models_manifest_bf16.json', H3 / 'models')):
        if mf.exists():
            try:
                for entry in json.loads(mf.read_text()).get('files', []):
                    rel = str(Path(entry['file']))
                    src = safe_child(base, rel)
                    if src.exists() and src.stat().st_size == entry.get('bytes'):
                        backed_up.add(rel)
            except Exception:
                pass
    models_root = ROOT / 'models'
    if models_root.exists():
        candidates = []
        for p in models_root.rglob('*.safetensors'):
            rel = str(p.relative_to(models_root))
            if rel not in keep and rel in backed_up:
                candidates.append((p.stat().st_size, p))
        for _, p in sorted(candidates, reverse=True):
            if shutil.disk_usage('/content').free >= needed_bytes + margin:
                break
            p.unlink(missing_ok=True)
        try:
            request('/free', {'unload_models': True, 'free_memory': True})
            time.sleep(0.5)
        except Exception:
            pass


def restore():
    manifest = H3 / 'models_manifest_bf16.json'
    if not manifest.exists():
        raise RuntimeError('未发现完整 BF16 备份。请先挂载云盘并核对模型备份清单；不会改用量化版本。')
    d = json.loads(manifest.read_text())
    if not d.get('complete'):
        raise RuntimeError('BF16 备份清单未完成，停止恢复')
    files = d['files']
    needed = sum(x['bytes'] for x in files if not safe_child(ROOT / 'models', x['file']).exists())
    _reclaim_ephemeral_space(needed, [x['file'] for x in files])
    if shutil.disk_usage('/content').free < needed + 8 * 2 ** 30:
        raise RuntimeError('磁盘不足：需要模型文件空间及至少8GiB余量。')
    total = sum(x['bytes'] for x in files)
    done = 0
    for item in files:
        src = safe_child(H3 / 'models', item['file'])
        dst = safe_child(ROOT / 'models', item['file'])
        expected = item['sha256']
        event('verifying', '校验 ' + item['file'], bytes_done=done, bytes_total=total)
        if dst.exists() and dst.stat().st_size == item['bytes'] and digest(dst) == expected:
            done += item['bytes']
            continue
        if not src.exists() or src.stat().st_size != item['bytes']:
            raise RuntimeError('云盘源文件缺失或长度不符：' + item['file'])
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(f"{dst.name}.{os.getpid()}.partial")
        h = hashlib.sha256()
        copied = 0
        last = 0
        with src.open('rb') as reader, part.open('wb') as writer:
            for block in iter(lambda: reader.read(16 * 1024 * 1024), b''):
                writer.write(block)
                h.update(block)
                copied += len(block)
                if time.time() - last > 2:
                    event('restoring', item['file'], bytes_done=done + copied, bytes_total=total)
                    last = time.time()
        if h.hexdigest() != expected or copied != item['bytes']:
            raise RuntimeError('恢复哈希不符：' + item['file'])
        part.replace(dst)
        done += copied
    return {'manifest': str(manifest), 'verified_files': len(files), 'bytes': done, 'precision': 'BF16 full'}


def prepare_models():
    files = validate_model_files(CONTROL.get('model_files', []))
    if not files:
        raise ValueError('模型清单为空。')
    if not Path('/content/drive/MyDrive').is_dir():
        raise RuntimeError('先挂载云盘，模型准备成功后同步持久备份。')
    queue_idle()
    store = BACKUP / 'model_library'
    store.mkdir(parents=True, exist_ok=True)
    manifest = store / 'manifest.json'
    previous = json.loads(manifest.read_text()) if manifest.exists() else {'files': []}
    known = {x['file']: x for x in previous['files']}
    verified = []
    for item in files:
        dst = safe_child(ROOT / 'models', item['file'])
        cached = safe_child(store / 'models', item['file'])
        old = known.get(item['file'], {})
        expected = item.get('sha256') or (old.get('sha256') if old.get('url') == item['url'] else None)
        dst.parent.mkdir(parents=True, exist_ok=True)
        cached.parent.mkdir(parents=True, exist_ok=True)
        if expected and dst.exists() and digest(dst) == expected:
            event('verifying', '复用已核验模型 ' + item['file'])
            sha = expected
        elif expected and cached.exists() and digest(cached) == expected:
            _reclaim_ephemeral_space(cached.stat().st_size, [x['file'] for x in files])
            if shutil.disk_usage('/content').free < cached.stat().st_size + 8 * 2 ** 30:
                raise RuntimeError('恢复模型的临时磁盘不足。')
            part = dst.with_name(f"{dst.name}.{os.getpid()}.partial")
            shutil.copyfile(cached, part)
            if digest(part) != expected:
                raise RuntimeError('恢复校验失败；保留源文件。')
            part.replace(dst)
            sha = expected
        else:
            event('downloading', '下载官方模型 ' + item['file'])
            try:
                response = urllib.request.urlopen(item['url'], timeout=30)
            except urllib.error.HTTPError as error:
                if error.code in (401, 403):
                    raise RuntimeError('模型需要下载权限，请先在官方页面取得授权；未接受任何条款。') from None
                raise RuntimeError('模型下载失败 HTTP ' + str(error.code)) from None
            with response:
                size = int(response.headers.get('Content-Length', '0'))
                if size > 0:
                    _reclaim_ephemeral_space(size, [x['file'] for x in files])
                if size <= 0 or shutil.disk_usage('/content').free < size + 8 * 2 ** 30:
                    raise RuntimeError('无法核对下载长度或本地磁盘不足。')
                part = dst.with_name(f"{dst.name}.{os.getpid()}.partial")
                h = hashlib.sha256()
                done = 0
                last = 0
                with part.open('wb') as stream:
                    for block in iter(lambda: response.read(16 * 1024 * 1024), b''):
                        stream.write(block)
                        h.update(block)
                        done += len(block)
                        if time.time() - last > 2:
                            event('downloading', item['file'], bytes_done=done, bytes_total=size)
                            last = time.time()
                sha = h.hexdigest()
                if done != size or (expected and sha != expected):
                    raise RuntimeError('模型长度或哈希不符，未启用下载文件。')
                part.replace(dst)
        if not cached.exists() or digest(cached) != sha:
            event('backing_up', '持久备份模型 ' + item['file'])
            part = cached.with_name(f"{cached.name}.{os.getpid()}.partial")
            shutil.copyfile(dst, part)
            if digest(part) != sha:
                raise RuntimeError('云盘模型备份核验失败，GPU保留。')
            part.replace(cached)
        record = dict(item, sha256=sha, bytes=dst.stat().st_size)
        known[item['file']] = record
        verified.append(record)
        tmp = manifest.with_suffix('.tmp')
        tmp.write_text(json.dumps({'files': list(known.values()), 'updated': time.time()}, indent=2))
        tmp.replace(manifest)
    try:
        request('/free', {'unload_models': True, 'free_memory': True})
    except Exception:
        pass
    return {'verified_files': len(verified), 'files': verified, 'backup_path': str(store), 'hash_verified': True}


def setup_run(args):
    log = WORK / 'setup.log'
    with log.open('a') as stream:
        p = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError('环境准备失败：' + log.read_text()[-2000:])


def _install_locked_custom_nodes(python_bin, raw_nodes):
    if not raw_nodes:
        return []
    validator = globals().get('validate_custom_nodes')
    locked = validator(raw_nodes) if validator else raw_nodes
    installed = []
    cn_root = ROOT / 'custom_nodes'
    cn_root.mkdir(parents=True, exist_ok=True)
    for item in locked:
        dest = safe_child(cn_root, item['name'])
        commit = item['commit']
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('自定义节点缺少40位固定Commit SHA')
        current_rev = None
        if (dest / '.git').exists():
            try:
                current_rev = subprocess.check_output(['git', '-C', str(dest), 'rev-parse', 'HEAD'], text=True).strip()
            except Exception:
                current_rev = None
        if current_rev == commit:
            continue
        event('installing', f"检出锁定节点 {item['name']} @ {commit[:10]}")
        dest.mkdir(parents=True, exist_ok=True)
        if not (dest / '.git').exists():
            setup_run(['git', 'init', str(dest)])
            setup_run(['git', '-C', str(dest), 'remote', 'add', 'origin', item['repo']])
        setup_run(['git', '-C', str(dest), 'fetch', '--depth', '1', 'origin', commit])
        setup_run(['git', '-C', str(dest), 'checkout', '--detach', 'FETCH_HEAD'])
        req = dest / 'requirements.txt'
        if req.is_file():
            setup_run([sys.executable, '-m', 'pip', '--python', str(python_bin), 'install', '--no-cache-dir', '-r', str(req)])
        installed.append({'name': item['name'], 'commit': commit})
    return installed


def setup():
    import torch
    if not torch.cuda.is_available() or torch.cuda.get_device_properties(0).total_memory < 90 * 2 ** 30:
        raise RuntimeError('未分配到目标96GB级G4，停止启动；不降级。')
    ctrl = globals().get('CONTROL') or {}
    custom_nodes = ctrl.get('custom_nodes') or []
    require_h3 = ctrl.get('require_h3', not bool(custom_nodes))
    if not (ROOT / 'main.py').exists():
        event('installing', '准备固定版本官方 ComfyUI，保留已有模型')
        if not (ROOT / '.git').exists():
            if ROOT.exists() and any(p.name not in ('models', 'input', 'output', 'custom_nodes') for p in ROOT.iterdir()):
                raise RuntimeError('现有目录包含未知文件，停止覆盖。')
            ROOT.mkdir(parents=True, exist_ok=True)
            setup_run(['git', 'init', str(ROOT)])
            setup_run(['git', '-C', str(ROOT), 'remote', 'add', 'origin', 'https://github.com/Comfy-Org/ComfyUI.git'])
        setup_run(['git', '-C', str(ROOT), 'fetch', '--depth', '1', 'origin', '46659e65e95920e5d29cae011b43b02699c0bfd3'])
        setup_run(['git', '-C', str(ROOT), 'checkout', '--detach', 'FETCH_HEAD'])

    env = Path('/content/jasper_comfy_env')
    python = env / 'bin/python'
    if not custom_nodes:
        try:
            info = request('/object_info')
            if not require_h3 or 'MiniMaxH3ImageToVideo' in info:
                return {'online': True, 'reused': True}
        except Exception:
            pass

    if not python.exists():
        setup_run([sys.executable, '-m', 'venv', '--without-pip', '--system-site-packages', str(env)])
        event('installing', '安装隔离环境依赖，保留系统环境')
        setup_run([sys.executable, '-m', 'pip', '--python', str(python), 'install', '--no-cache-dir', '-r', str(ROOT / 'requirements.txt')])

    changed_nodes = _install_locked_custom_nodes(python, custom_nodes)
    try:
        info = request('/object_info')
        if not changed_nodes and (not require_h3 or 'MiniMaxH3ImageToVideo' in info):
            return {'online': True, 'reused': True, 'custom_nodes_installed': 0}
        if changed_nodes:
            queue_idle()
            pid_file = WORK / 'comfy_pid.json'
            if pid_file.exists():
                old_pid = json.loads(pid_file.read_text()).get('pid')
                if old_pid:
                    import signal
                    try:
                        os.kill(int(old_pid), signal.SIGTERM)
                        time.sleep(2)
                    except OSError:
                        pass
    except RuntimeError:
        raise
    except Exception:
        pass

    log = (WORK / 'comfy.log').open('a')
    p = subprocess.Popen([str(python), str(ROOT / 'main.py'), '--listen', '127.0.0.1', '--port', '8188', '--disable-auto-launch'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    (WORK / 'comfy_pid.json').write_text(json.dumps({'pid': p.pid}))
    for _ in range(120):
        try:
            info = request('/object_info')
            if require_h3 and 'MiniMaxH3ImageToVideo' not in info:
                raise RuntimeError('服务启动但未发现H3节点')
            return {'online': True, 'pid': p.pid, 'custom_nodes_installed': len(changed_nodes)}
        except Exception:
            time.sleep(2)
    raise RuntimeError('ComfyUI未就绪，日志保存在 /content/jasper_workstation/comfy.log')


def backup(flush=False):
    queue_idle()
    import platform
    environment = {
        'python': sys.version,
        'platform': platform.platform(),
        'comfy_revision': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip() if (ROOT / '.git').exists() else None
    }
    try:
        environment['packages'] = json.loads(subprocess.check_output([sys.executable, '-m', 'pip', '--python', '/content/jasper_comfy_env/bin/python', 'list', '--format=json'], text=True))
    except Exception as error:
        environment['package_inventory_error'] = type(error).__name__
    (WORK / 'environment.json').write_text(json.dumps(environment, indent=2))
    if not Path('/content/drive/MyDrive').is_dir():
        raise RuntimeError('请先通过管理台挂载模型云盘。未备份，不会关机。')
    dest = BACKUP / 'runs' / time.strftime('%Y%m%d_%H%M%S')
    dest.mkdir(parents=True, exist_ok=True)
    files = []
    for label, folder in [('production', Path('/content/jasper_production')), ('outputs', ROOT / 'output'), ('inputs', ROOT / 'input'), ('workflows', ROOT / 'user/default/workflows'), ('control', WORK)]:
        if folder.exists():
            files.extend((label, folder, p) for p in folder.rglob('*') if p.is_file() and not p.is_symlink())
    total = sum(p.stat().st_size for _, _, p in files)
    done = 0
    manifest = []
    for label, folder, src in files:
        before = src.stat()
        target = dest / label / src.relative_to(folder)
        target.parent.mkdir(parents=True, exist_ok=True)
        event('backing_up', str(src.relative_to(folder)), bytes_done=done, bytes_total=total)
        part = target.with_name(target.name + '.partial')
        shutil.copy2(src, part)
        h = digest(src)
        if digest(part) != h or src.stat().st_mtime_ns != before.st_mtime_ns:
            raise RuntimeError('源文件仍在变化或备份校验失败；保留运行时。')
        part.replace(target)
        manifest.append({'file': str(target.relative_to(dest)), 'bytes': before.st_size, 'sha256': h})
        done += before.st_size
    (dest / 'manifest.json').write_text(json.dumps({'complete': True, 'files': manifest, 'created': time.time()}, indent=2))
    event('saved', '文件逐项校验完成，等待云盘刷新', bytes_done=done, bytes_total=total)
    if flush:
        from google.colab import drive
        drive.flush_and_unmount()
        event('flushed', '云盘已完成刷新并卸载')
    return {'backup_path': str(dest), 'files': len(manifest), 'bytes': done, 'hash_verified': True, 'drive_flushed': flush, 'models': '模型权重沿用独立持久备份，未重复复制'}


def _start_ws_progress_watcher(client_id, pid_holder, stop_flag, started):
    """Stream real-time step/node progress from local ComfyUI WebSocket when available."""
    def worker():
        try:
            import websocket
            ws = websocket.create_connection(f'ws://127.0.0.1:8188/ws?clientId={client_id}', origin='http://127.0.0.1:8188', timeout=4)
        except Exception:
            return
        last_emit = 0.0
        cur_node = None
        step_t0 = None
        first_step = None
        try:
            while not stop_flag.is_set():
                try:
                    raw = ws.recv()
                except Exception:
                    continue
                if not isinstance(raw, str):
                    continue
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                mtype = msg.get('type')
                data = msg.get('data') or {}
                pid = pid_holder.get('pid')
                if pid and data.get('prompt_id') and data['prompt_id'] != pid:
                    continue
                if mtype == 'executing' and data.get('node'):
                    cur_node = str(data['node'])
                elif mtype == 'progress':
                    val = int(data.get('value', 0))
                    mx = int(data.get('max', 0))
                    if mx > 0 and (time.time() - last_emit >= 0.9 or val >= mx):
                        if step_t0 is None or val <= (first_step or 0):
                            step_t0 = time.time()
                            first_step = val
                        eta = None
                        if val > first_step and time.time() > step_t0:
                            per_step = (time.time() - step_t0) / (val - first_step)
                            eta = max(0, round(per_step * (mx - val)))
                        node_hint = f'（节点 #{cur_node}）' if cur_node else ''
                        event(
                            'sampling',
                            f'采样第 {val} / {mx} 步{node_hint}',
                            prompt_id=pid,
                            step_done=val,
                            step_total=mx,
                            current_node=cur_node,
                            eta_seconds=eta,
                            elapsed=time.time() - started
                        )
                        last_emit = time.time()
        finally:
            try:
                ws.close()
            except Exception:
                pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


def generate(resume=False):
    config = CONTROL['config']
    job = CONTROL['job']
    out = WORK / 'jobs' / job
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    stop_ws = threading.Event()
    pid_holder = {'pid': CONTROL.get('prompt_id')}
    _start_ws_progress_watcher(job, pid_holder, stop_ws, started)
    try:
        if resume or (out / 'submitted.json').exists():
            pid = CONTROL.get('prompt_id') or json.loads((out / 'submitted.json').read_text())['prompt_id']
            pid_holder['pid'] = pid
            event('resumed', '恢复已有任务跟踪，不重新提交', prompt_id=pid)
        else:
            memory = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], text=True).strip().splitlines()
            if not memory or float(memory[0]) < 90000:
                raise RuntimeError('当前GPU不满足目标96GB配置，停止提交；不降级。')
            width, height = {'480P': (480, 848), '720P': (736, 1280), '768P': (768, 1360), '1080P': (1088, 1920)}[config['resolution']]
            if config.get('ratio') == '16:9':
                width, height = height, width
            if config.get('ratio') == '1:1':
                width = height = min(width, height)
            ref = CONTROL.get('reference')
            name = None
            if ref:
                name = 'jasper_' + job + ref['suffix']
                (ROOT / 'input').mkdir(exist_ok=True)
                (ROOT / 'input' / name).write_bytes(base64.b64decode(ref['base64']))
            if config.get('model') == 'workflow':
                timing = config['recipe'].get('timing', {'fps': 24, 'frame_multiple': 4, 'frame_offset': 1})
                fps = timing['fps']
                multiple = timing['frame_multiple']
                offset = timing['frame_offset']
                frames = max(1, round(float(config['duration']) * fps))
                frames += (offset - frames % multiple) % multiple
                values = dict(prompt=config['prompt'], seed=int(config['seed']), width=width, height=height, frames=frames, duration=float(config['duration']), fps=fps)
                if config.get('negative_prompt'):
                    values['negative_prompt'] = config['negative_prompt']
                if name:
                    values['reference'] = name
                graph = materialize(config['recipe'], values)
                remote_validate(graph, request('/object_info'))
                for node in graph.values():
                    if 'filename_prefix' in node['inputs']:
                        node['inputs']['filename_prefix'] = 'jasper/' + job
            else:
                required = [
                    ROOT / 'models/diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors',
                    ROOT / 'models/text_encoders/qwen3vl_32b_minimax_h3_bf16.safetensors',
                    ROOT / 'models/vae/minimax_h3_video_vae_fp16.safetensors'
                ]
                if any(not p.exists() for p in required):
                    raise RuntimeError('完整BF16模型缺失，请先恢复模型。')

                def node(kind, **inputs):
                    return {'class_type': kind, 'inputs': inputs}

                frames = max(5, round(float(config['duration']) * 24))
                frames += (5 - frames % 17) % 17
                graph = {
                    '1': node('UNETLoader', unet_name=required[0].name, weight_dtype='default'),
                    '2': node('CLIPLoader', clip_name=required[1].name, type='minimax', device='default'),
                    '3': node('VAELoader', vae_name=required[2].name),
                    '5': node('LoadImage', image=name),
                    '6': node('MiniMaxH3ImageToVideo', clip=['2', 0], vae=['3', 0], first_frame=['5', 0], prompt=config['prompt'], width=width, height=height, length=frames),
                    '8': node('BasicScheduler', model=['1', 0], scheduler='simple', steps=20, denoise=1.0),
                    '9': node('BasicGuider', model=['1', 0], conditioning=['6', 0]),
                    '10': node('RandomNoise', noise_seed=int(config['seed'])),
                    '11': node('KSamplerSelect', sampler_name='res_multistep'),
                    '12': node('SamplerCustomAdvanced', noise=['10', 0], guider=['9', 0], sampler=['11', 0], sigmas=['8', 0], latent_image=['6', 1]),
                    '13': node('VAEDecode', samples=['12', 0], vae=['3', 0]),
                    '15': node('CreateVideo', images=['13', 0], fps=24, bit_depth=8),
                    '16': node('SaveVideo', video=['15', 0], filename_prefix='jasper/' + job, format='auto', codec='auto')
                }
            (out / 'workflow_api.json').write_text(json.dumps(graph, indent=2))
            (out / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2))
            answer = request('/prompt', {'prompt': graph, 'client_id': job})
            pid = answer['prompt_id']
            pid_holder['pid'] = pid
            (out / 'submitted.json').write_text(json.dumps({'prompt_id': pid}))
            event('submitted', '已提交真实推理任务', prompt_id=pid)

        while time.time() - started < 21600:
            history = request('/history/' + pid)
            if pid in history:
                result = history[pid]
                (out / 'history.json').write_text(json.dumps(result))
                st = result.get('status', {})
                if st.get('status_str') == 'error':
                    msgs = str(st.get('messages', ''))
                    if 'InterruptProcessingException' in msgs or 'execution_interrupted' in msgs:
                        raise RuntimeError('采样已按指令安全中断；GPU 会话保留。')
                    raise RuntimeError(msgs[-1500:])
                outputs = []
                for value in result.get('outputs', {}).values():
                    for key in ('videos', 'gifs', 'images', 'audio'):
                        for item in value.get(key, []):
                            p = safe_child(ROOT / 'output', str(Path(item.get('subfolder', '')) / item['filename']))
                            if p.exists() and p.suffix.lower() in ('.mp4', '.webm', '.png', '.jpg', '.jpeg', '.wav', '.mp3', '.flac', '.ogg', '.m4a') and str(p) not in outputs:
                                outputs.append(str(p))
                if not outputs:
                    if any('execution_interrupted' in str(m) for m in st.get('messages', [])):
                        raise RuntimeError('采样已按指令安全中断；GPU 会话保留。')
                    raise RuntimeError('推理结束但没有实际输出文件')
                return {'prompt_id': pid, 'outputs': outputs, 'elapsed': time.time() - started}
            q = request('/queue')
            running = any(row[1] == pid for row in q.get('queue_running', []))
            pending = any(row[1] == pid for row in q.get('queue_pending', []))
            if not running and not pending:
                raise RuntimeError('任务已不在队列且未产生输出（可能已手动中断）；保留ID，GPU未关闭。')
            event('sampling' if running else 'waiting', '采样运行中' if running else '等待队列', prompt_id=pid, elapsed=time.time() - started)
            time.sleep(5)
        raise TimeoutError('跟踪达到6小时；任务未自动取消，保留ID可恢复跟踪')
    finally:
        stop_ws.set()


kind=CONTROL['action'];event('connected', '远端连接已建立')
if kind == 'models':
    result = prepare_models()
elif kind == 'inspect':
    result = inspect()
elif kind == 'restore':
    result = restore()
elif kind == 'setup':
    result = setup()
elif kind == 'interrupt':
    result = interrupt_sampling()
elif kind in ('backup', 'backup_stop'):
    result = backup(kind == 'backup_stop')
elif kind in ('generate', 'resume'):
    result = generate(kind == 'resume')
else:
    raise ValueError('未知远端操作')
print('JASPER_RESULT ' + json.dumps(result, ensure_ascii=False), flush=True)
