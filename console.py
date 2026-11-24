"""Durable, asynchronous operations & FIFO batch queue for the local workstation. Never auto-allocates."""
from pathlib import Path
import json, os, shutil, subprocess, threading, time, uuid

LABELS = {
    'mount': '挂载模型云盘',
    'adopt': '接管已分配 G4',
    'start': '启动 G4',
    'stop': '保存、核验并释放 GPU',
    'inspect': '检查远端环境',
    'restore': '恢复完整 BF16 模型',
    'bridge': '连接 ComfyUI 画布',
    'setup': '启动 ComfyUI',
    'backup': '备份工作结果',
    'reconcile': '核对旧会话记录',
    'generate': '生成作品',
    'resume': '恢复任务跟踪',
    'models': '准备工作流模型',
}


class Console:
    def __init__(self, server):
        self.s = server
        self.root = server.DATA / 'operations'
        self.root.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.worker_lock = threading.Lock()
        self._pending = []
        for p in self.root.glob('*.json'):
            d = json.loads(p.read_text())
            if d.get('state') in ('queued', 'running'):
                d.update(state='interrupted', message='本机服务已重启。任务不会自动重提；可检查远端任务并恢复跟踪。', finished=time.time())
                self.write(d)
                if d.get('job_id'):
                    self.job_update(d['job_id'], state='interrupted', message='本机服务已重启，可恢复跟踪')

    def write(self, d):
        p = self.root / (d['id'] + '.json')
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2))
        tmp.replace(p)

    def all(self):
        with self.lock:
            return sorted([json.loads(p.read_text()) for p in self.root.glob('*.json')], key=lambda x: x['created'], reverse=True)[:50]

    def event(self, d, stage, message, **extra):
        with self.lock:
            d.update(stage=stage, message=message, updated=time.time(), **extra)
            d.setdefault('events', []).append({'at': time.time(), 'stage': stage, 'message': message})
            d['events'] = d['events'][-100:]
            self.write(d)

    def _active_ops(self):
        return [json.loads(p.read_text()) for p in self.root.glob('*.json') if json.loads(p.read_text()).get('state') in ('queued', 'running')]

    def start(self, kind, body):
        if kind == 'generate_batch':
            return self.enqueue_batch(body.get('jobs') or [])
        if kind not in LABELS:
            raise ValueError('未知操作')
        with self.lock:
            active = self._active_ops()
            if kind == 'generate':
                # Allow queuing multiple 'generate' jobs while only 'generate' operations are active!
                if any(op.get('action') != 'generate' for op in active):
                    raise ValueError('当前有环境或管理操作正在执行，请等待完成后提交生成任务。')
                job_id = body.get('job')
                if not job_id:
                    raise ValueError('请选择要提交的任务。')
                if any(op.get('job_id') == job_id for op in active):
                    raise ValueError('该镜头任务已在队列或执行中，请勿重复提交。')
                d = {
                    'id': uuid.uuid4().hex,
                    'action': 'generate',
                    'label': LABELS['generate'],
                    'state': 'queued',
                    'stage': 'queued',
                    'message': '已在单次 G4 队列中排队等待执行' if active else '等待执行',
                    'created': time.time(),
                    'job_id': job_id,
                    'events': []
                }
                self.write(d)
                self._pending.append((d, dict(body)))
            else:
                if active:
                    raise ValueError('已有操作正在执行，请等待完成。')
                d = {
                    'id': uuid.uuid4().hex,
                    'action': kind,
                    'label': LABELS[kind],
                    'state': 'queued',
                    'stage': 'queued',
                    'message': '等待执行',
                    'created': time.time(),
                    'events': []
                }
                self.write(d)
                self._pending.append((d, dict(body)))
        threading.Thread(target=self._drain_queue, daemon=True).start()
        return d

    def enqueue_batch(self, job_ids):
        if not isinstance(job_ids, list) or not job_ids:
            raise ValueError('请选择至少一个待提交任务。')
        clean_ids = []
        for jid in job_ids:
            if isinstance(jid, str) and jid not in clean_ids:
                clean_ids.append(jid)
        if not clean_ids:
            raise ValueError('任务列表为空。')
        db = self.s.load()
        jobs_by_id = {j['id']: j for j in db.get('jobs', [])}
        for jid in clean_ids:
            job = jobs_by_id.get(jid)
            if not job:
                raise ValueError(f'任务 {jid[:8]} 不存在。')
            if job.get('attempted') or job.get('prompt_id') or job.get('state') != 'prepared':
                raise ValueError(f'任务《{job.get("title", jid[:8])}》已提交过，不能加入新批次。')

        created_ops = []
        with self.lock:
            active = self._active_ops()
            if any(op.get('action') != 'generate' for op in active):
                raise ValueError('当前有环境或管理操作正在执行，请等待完成后批量排队。')
            queued_jobs = {op.get('job_id') for op in active}
            base_ts = time.time()
            for idx, jid in enumerate(clean_ids):
                if jid in queued_jobs:
                    continue
                job_title = jobs_by_id[jid].get('title', '镜头')
                d = {
                    'id': uuid.uuid4().hex,
                    'action': 'generate',
                    'label': f"{LABELS['generate']} · {job_title}",
                    'state': 'queued',
                    'stage': 'queued',
                    'message': f'批次排队中（第 {idx + 1}/{len(clean_ids)} 项）',
                    'created': base_ts + idx * 0.001,
                    'job_id': jid,
                    'events': []
                }
                self.write(d)
                self._pending.append((d, {'job': jid}))
                created_ops.append(d)
        if not created_ops:
            raise ValueError('所选任务已在执行队列中。')
        threading.Thread(target=self._drain_queue, daemon=True).start()
        return {'queued_count': len(created_ops), 'operations': created_ops}

    def _drain_queue(self):
        if not self.worker_lock.acquire(blocking=False):
            return
        try:
            while True:
                with self.lock:
                    if not self._pending:
                        break
                    d, body = self._pending.pop(0)
                # Skip if cancelled before execution started
                fresh = json.loads((self.root / f"{d['id']}.json").read_text())
                if fresh.get('state') != 'queued':
                    continue
                # Check CU budget guardrail before starting the next queued generation
                if fresh.get('action') == 'generate':
                    if self._check_cu_budget_exceeded():
                        d.update(state='failed', stage='budget_paused', message='已达到本次会话设定的 CU 预算护栏上限，队列已暂停；未重复提交，GPU保留。', finished=time.time())
                        self.write(d)
                        continue
                self.run(d, body)
        finally:
            self.worker_lock.release()
            with self.lock:
                still_more = bool(self._pending)
            if still_more:
                threading.Thread(target=self._drain_queue, daemon=True).start()

    def _check_cu_budget_exceeded(self):
        try:
            db = self.s.load()
            budget = float(db.get('policy', {}).get('max_cu_budget') or 0)
            if budget <= 0:
                return False
            lease_p = self.s.DATA / 'lease.json'
            if not lease_p.exists():
                return False
            lease = json.loads(lease_p.read_text())
            start_bal = lease.get('start_balance')
            if start_bal is None:
                return False
            st = self.s.refresh()
            cur_bal = st.get('balance')
            if cur_bal is None:
                return False
            spent = float(start_bal) - float(cur_bal)
            if spent >= budget:
                with self.s.LOCK:
                    db = self.s.load()
                    db['policy']['budget_paused'] = True
                    db['events'].insert(0, {'time': self.s.now(), 'text': f'已触发 CU 预算护栏（已消耗 {spent:.2f} / 限额 {budget:.2f} CU），后续排队任务已自动暂停。'})
                    self.s.save(db)
                return True
        except Exception:
            return False
        return False

    def cancel_queued(self, op_id=None):
        """Cancel queued (not-yet-submitted) batch items safely without touching running jobs or GPU."""
        cancelled = 0
        with self.lock:
            remaining = []
            for d, body in self._pending:
                if op_id is None or d['id'] == op_id:
                    d.update(state='failed', stage='cancelled', message='已在提交前从本机队列移出；未消耗算力。', finished=time.time())
                    self.write(d)
                    cancelled += 1
                else:
                    remaining.append((d, body))
            self._pending = remaining
        return {'cancelled_queued': cancelled}

    def interrupt_active(self):
        """Send ComfyUI /interrupt to the owned G4 VM for an in-flight sampling task without releasing the GPU."""
        target = self.owned()
        active_gen = next((op for op in self.all() if op.get('state') == 'running' and op.get('action') in ('generate', 'resume')), None)
        if not active_gen:
            raise ValueError('当前没有正在远端采样中的生成任务。')
        script = self.s.ROOT / 'runtime/control_gateway.py'
        python = self.s.sdk_python()
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        p = subprocess.run(
            [python, '-B', str(script), '--endpoint', target['endpoint']],
            input=json.dumps({'action': 'interrupt'}),
            capture_output=True,
            text=True,
            timeout=35,
            env=env
        )
        if p.returncode != 0:
            raise RuntimeError('发送中断信号失败：' + (p.stderr or p.stdout)[-500:])
        self.event(active_gen, 'interrupting', '已发送安全中断指令，等待当前步结束（保留 G4 会话）')
        return {'interrupted': True, 'operation_id': active_gen['id'], 'endpoint': target['endpoint']}

    def owned(self):
        self.s.guarded()
        state = self.s.refresh()
        if state.get('runtime_state') != 'owned' or not state.get('managed_session'):
            raise ValueError('当前没有已核实归属的工作站会话。网页手动会话不会被接管或停止。')
        return state['managed_session']

    def remote(self, d, kind, body):
        target = self.owned()
        self.event(d, 'connecting', '连接已核实的远端会话', endpoint=target['endpoint'])
        payload = {
            'action': kind,
            'job': body.get('job'),
            'config': body.get('config'),
            'reference': body.get('reference'),
            'end_reference': body.get('end_reference'),
            'prompt_id': body.get('prompt_id'),
            'model_files': body.get('model_files'),
            'custom_nodes': body.get('custom_nodes'),
            'require_h3': body.get('require_h3', True),
            'local_results': str(self.s.DATA / 'results' / d['id'])
        }
        script = self.s.ROOT / 'runtime/control_gateway.py'
        python = self.s.sdk_python()
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        p = subprocess.Popen([python, '-B', str(script), '--endpoint', target['endpoint']], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        p.stdin.write(json.dumps(payload))
        p.stdin.close()
        result = None
        errors = []

        def stderr():
            for line in p.stderr:
                errors.append('[Google授权地址已隐藏；请在管理台登录。]' if 'accounts.google.com/' in line or 'sdk.cloud.google.com/' in line else line[-500:])
                del errors[:-8]

        threading.Thread(target=stderr, daemon=True).start()
        for line in p.stdout:
            if line.startswith('JASPER_EVENT '):
                event = json.loads(line[13:])
                self.event(d, event.pop('stage', 'running'), event.pop('message', '处理中'), **event)
                if d.get('job_id') and d.get('prompt_id'):
                    self.job_update(d['job_id'], state='running', prompt_id=d['prompt_id'], operation_id=d['id'])
            elif line.startswith('JASPER_RESULT '):
                result = json.loads(line[14:])
        rc = p.wait()
        if rc or result is None:
            raise RuntimeError('远端操作未完成：' + ''.join(errors)[-1500:])
        if kind == 'inspect':
            result['endpoint'] = target['endpoint']
        return result

    def mount(self, d):
        target = self.owned()
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        process = subprocess.Popen([self.s.sdk_python(), str(self.s.ROOT / 'runtime/drive_auth.py'), '--endpoint', target['endpoint']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        result = None
        errors = []

        def stderr():
            for line in process.stderr:
                errors.append('[Google授权地址已隐藏；请在管理台登录。]' if 'accounts.google.com/' in line or 'sdk.cloud.google.com/' in line else line[-500:])
                del errors[:-8]

        threading.Thread(target=stderr, daemon=True).start()
        for line in process.stdout:
            if line.startswith('JASPER_EVENT '):
                event = json.loads(line[13:])
                self.event(d, event.pop('stage'), event.pop('message'), **event)
            elif line.startswith('JASPER_RESULT '):
                result = json.loads(line[14:])
        if process.wait() or not result or result.get('drive_mounted') is not True:
            raise RuntimeError('云盘挂载未完成；保留G4。' + ''.join(errors)[-1000:])
        return result

    def job_update(self, ident, **values):
        with self.s.LOCK:
            db = self.s.load()
            job = next((x for x in db['jobs'] if x['id'] == ident), None)
            if job:
                job.update(values, updated=self.s.now())
                self.s.save(db)

    def run(self, d, body):
        try:
            self.event(d, 'checking', '核对账号、会话与操作条件', state='running')
            kind = d['action']
            self.s.guarded()
            if kind == 'start':
                if body.get('gpu', 'G4') != 'G4':
                    raise ValueError('生产配置锁定 G4，不会自动降级。')
                result = self.s.operation('start', body)
            elif kind == 'adopt':
                with self.s.OP_LOCK:
                    state = self.s.refresh()
                    target = next((x for x in state['sessions'] if x['endpoint'] == body.get('endpoint') and x['hardware'] == 'G4'), None)
                    if state.get('runtime_state') == 'unknown' or not target:
                        raise ValueError('未找到明确匹配的G4会话，未接管。')
                    lease = self.s.DATA / 'lease.json'
                    if lease.exists():
                        old = json.loads(lease.read_text())
                        if any(x['endpoint'] == old.get('endpoint') for x in state['sessions']):
                            raise ValueError('已有仍存活的工作站会话，不更换归属。')
                        shutil.move(lease, self.root / (d['id'] + '_lease.record'))
                    lease.write_text(json.dumps({
                        'session': target['name'],
                        'endpoint': target['endpoint'],
                        'state': 'active',
                        'adopted': True,
                        'started': time.time(),
                        'start_balance': state.get('balance'),
                        'reminder_at': time.time() + int(self.s.load()['policy']['max_minutes']) * 60
                    }))
                    result = {'adopted': target, 'status': self.s.refresh()}
            elif kind == 'mount':
                with self.s.OP_LOCK:
                    result = self.mount(d)
            elif kind == 'bridge':
                with self.s.OP_LOCK:
                    from runtime.local_bridge import start
                    target = self.owned()
                    result = start(self.s, target['endpoint'])
            elif kind == 'reconcile':
                with self.s.OP_LOCK:
                    state = self.s.refresh()
                    lease = self.s.DATA / 'lease.json'
                    if state.get('active') != 0 or state.get('runtime_state') != 'idle':
                        raise ValueError('仍有会话或状态不确定，不能清理开机记录。')
                    if lease.exists():
                        shutil.move(lease, self.root / (d['id'] + '_lease.record'))
                    result = {'status': self.s.refresh()}
            else:
                with self.s.OP_LOCK:
                    if kind == 'stop' and body.get('backup_confirmed') is not True:
                        raise ValueError('需要先确认当前制作任务已结束。')
                    if kind in ('generate', 'resume'):
                        db = self.s.load()
                        job = next((j for j in db['jobs'] if j['id'] == body.get('job')), None)
                        if not job:
                            raise ValueError('任务不存在')
                        if kind == 'generate' and (job.get('attempted') or job.get('prompt_id') or job['state'] != 'prepared'):
                            raise ValueError('任务已经提交；请恢复跟踪，不重复生成。')
                        if kind == 'resume' and not job.get('attempted'):
                            raise ValueError('任务尚未提交，无法恢复跟踪。')
                        config = job['config']
                        if config['model'] not in ('h3', 'workflow'):
                            raise ValueError('请为此模型导入工作流后提交。')
                        ref = next((a for a in db['assets'] if a['id'] == config['reference']), None)
                        if not ref and (config['model'] == 'h3' or config.get('recipe', {}).get('bindings', {}).get('reference')):
                            raise ValueError('参考素材不存在')
                        end_ref = next((a for a in db['assets'] if a['id'] == config.get('end_reference')), None) if config.get('end_reference') else None
                        import base64
                        body.update(config=config, prompt_id=job.get('prompt_id'), reference=None, end_reference=None)
                        if ref:
                            source = Path(ref.get('path') or self.s.ASSETS / ref['file'])
                            body['reference'] = {'suffix': source.suffix, 'base64': base64.b64encode(source.read_bytes()).decode()}
                        if end_ref:
                            end_src = Path(end_ref.get('path') or self.s.ASSETS / end_ref['file'])
                            body['end_reference'] = {'suffix': end_src.suffix, 'base64': base64.b64encode(end_src.read_bytes()).decode()}
                        d['job_id'] = job['id']
                        self.job_update(job['id'], state='connecting', attempted=True, operation_id=d['id'])
                    if kind == 'models':
                        item = next((x for x in self.s.load().get('workflows', []) if x['id'] == body.get('workflow')), None)
                        if not item or not item.get('model_files'):
                            raise ValueError('此工作流尚未配置官方模型文件。')
                        body['model_files'] = item['model_files']
                    if kind == 'setup' and body.get('workflow'):
                        item = next((x for x in self.s.load().get('workflows', []) if x['id'] == body.get('workflow')), None)
                        if item:
                            body['custom_nodes'] = item.get('custom_nodes', [])
                            body['require_h3'] = False
                    result = self.remote(d, 'backup_stop' if kind == 'stop' else kind, body)
                    if kind == 'stop':
                        if result.get('hash_verified') is not True or result.get('drive_flushed') is not True:
                            raise RuntimeError('未取得备份校验及云盘刷新成功记录，保留运行时。')
                        self.event(d, 'releasing', '远端备份已核验、云盘已刷新，正在释放运行时')
                        result['release'] = self.s._operation('stop', {'backup_confirmed': True})
                        from runtime.local_bridge import stop
                        try:
                            result['local_bridge_cleanup'] = stop(self.s)
                        except Exception as error:
                            result['local_bridge_cleanup'] = {'stopped': False, 'warning': str(error)}
                    if kind == 'inspect':
                        (self.s.DATA / 'remote_inspection.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
                    if kind in ('generate', 'resume'):
                        with self.s.LOCK:
                            db = self.s.load()
                            job = next(j for j in db['jobs'] if j['id'] == d['job_id'])
                            asset_ids = []
                            for file in result.get('local_files', []):
                                p = Path(file)
                                ident = uuid.uuid4().hex
                                managed = self.s.ASSETS / (ident + p.suffix)
                                shutil.copy2(p, managed)
                                db['assets'].append({
                                    'id': ident,
                                    'name': p.name,
                                    'file': managed.name,
                                    'kind': 'video' if p.suffix.lower() in ('.mp4', '.webm') else 'audio' if p.suffix.lower() in ('.wav', '.mp3', '.flac', '.ogg', '.m4a') else 'image',
                                    'created': self.s.now()
                                })
                                asset_ids.append(ident)
                            job.update(state='succeeded', message='已下载实际生成结果，待画面验收', results=asset_ids, operation_id=d['id'])
                            if job.get('bind_element_id') and asset_ids:
                                elem = next((e for e in db.get('elements', []) if e['id'] == job['bind_element_id']), None)
                                if elem:
                                    elem['asset_id'] = asset_ids[0]
                            shot = next((s for s in db['shots'] if s['id'] == job.get('shot')), None)
                            if shot and asset_ids:
                                bind_slot = job.get('bind_slot')
                                if bind_slot in ('reference', 'end_reference'):
                                    shot[bind_slot] = asset_ids[0]
                                else:
                                    takes = shot.setdefault('takes', [])
                                    if shot.get('output') and not any(t.get('asset_id') == shot['output'] for t in takes):
                                        takes.append({'id': uuid.uuid4().hex, 'asset_id': shot['output'], 'seed': shot.get('seed'), 'created': '历史样片'})
                                    for aid in asset_ids:
                                        takes.insert(0, {
                                            'id': uuid.uuid4().hex,
                                            'asset_id': aid,
                                            'job_id': job['id'],
                                            'seed': job.get('config', {}).get('seed'),
                                            'prompt': (job.get('config', {}).get('prompt') or '')[:160],
                                            'created': self.s.now()
                                        })
                                    shot['output'] = asset_ids[0]
                                    out_asset = next((a for a in db['assets'] if a['id'] == asset_ids[0]), None)
                                    if out_asset and out_asset.get('kind') == 'video':
                                        try:
                                            from timeline_export import media_tool_binary
                                            tool = media_tool_binary(self.s.ROOT)
                                            strip_name = f"qcstrip_{asset_ids[0][:16]}.jpg"
                                            strip_path = self.s.ASSETS / strip_name
                                            subprocess.run([str(tool), 'filmstrip', str(self.s.ASSETS / out_asset['file']), str(strip_path), '4'], capture_output=True, timeout=20)
                                            if strip_path.is_file():
                                                shot['qc_strip_file'] = strip_name
                                        except Exception:
                                            pass
                            self.s.save(db)
            if kind == 'restore' and result.get('verified_files') and result.get('bytes'):
                d.update(bytes_done=result['bytes'], bytes_total=result['bytes'])
            self.event(d, 'complete', '操作完成', state='succeeded', result=result, finished=time.time())
        except Exception as e:
            safely_interrupted = d.get('action') in ('generate', 'resume') and '采样已按指令安全中断；GPU 会话保留。' in str(e)
            message = '采样已按指令安全中断；GPU 会话保留。' if safely_interrupted else str(e)
            if d.get('job_id'):
                values = {'state': 'interrupted' if d.get('prompt_id') or safely_interrupted else 'failed', 'message': message}
                if d.get('not_submitted') is True and not d.get('prompt_id'):
                    values.update(attempted=False, state='prepared')
                self.job_update(d['job_id'], **values)
            self.event(d, 'interrupted' if safely_interrupted else 'failed', message, state='interrupted' if safely_interrupted else 'failed', finished=time.time())
