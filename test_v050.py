"""CineHarbor 0.5.0 test suite:
- Verified G4 full-precision model presets & automatic fp8->bf16/fp16 node upgrade
- CU budget guardrail (pauses subsequent queued jobs without killing running GPU)
- Opt-in read-only LAN/Tailscale mobile monitor + local QR SVG + masked identity + zero write methods
- Multi-take gallery & Hero Take selection
- Project-level Character/Scene/Prop elements with automatic prompt & reference inheritance
- Cross-platform CLI data directory resolution
"""
import base64, json, os, tempfile, threading, time, unittest, urllib.error, urllib.request
from pathlib import Path
from unittest.mock import patch
import server
from console import Console
from model_presets import list_presets
import gclabs_cli
import mobile_monitor


class PresetsAndCLITests(unittest.TestCase):
    def test_all_presets_are_full_precision_and_validated(self):
        presets = list_presets()
        self.assertEqual(len(presets), 6)
        self.assertIn('qwen_image_edit_2511_bf16', [p['id'] for p in presets])
        for p in presets:
            self.assertTrue(p['model_files'])
            for mf in p['model_files']:
                self.assertTrue(mf['url'].startswith('https://huggingface.co/'))
                self.assertNotIn('fp8', mf['file'].lower())
                self.assertNotIn('int8', mf['file'].lower())

    def test_cross_platform_cli_paths(self):
        with patch.dict('os.environ', {}, clear=False):
            os_env = __import__('os').environ
            os_env.pop('CINEHARBOR_DATA', None)
            os_env.pop('GC_LABS_DATA', None)
            os_env.pop('JASPER_WORKSTATION_DATA', None)
            with patch('platform.system', return_value='Darwin'):
                self.assertTrue(str(gclabs_cli.default_data_dir()).endswith('Jasper Workstation'))
            with patch('platform.system', return_value='Linux'):
                self.assertTrue(str(gclabs_cli.default_data_dir()).endswith('gc-labs'))
            with patch('platform.system', return_value='Windows'):
                self.assertTrue(str(gclabs_cli.default_data_dir()).endswith('GC Labs'))

    def test_data_dir_prefers_cineharbor_env_and_accepts_gc_labs(self):
        with patch.dict(os.environ, {'CINEHARBOR_DATA': '/tmp/cineharbor-data', 'GC_LABS_DATA': '/tmp/gc-labs-data'}):
            self.assertEqual(gclabs_cli.default_data_dir(), Path('/tmp/cineharbor-data'))
        with patch.dict(os.environ, {'GC_LABS_DATA': '/tmp/gc-labs-data'}, clear=False):
            os.environ.pop('CINEHARBOR_DATA', None)
            self.assertEqual(gclabs_cli.default_data_dir(), Path('/tmp/gc-labs-data'))

    def test_workspace_json_survives_a_narrow_windows_code_page(self):
        original_write = Path.write_text
        original_read = Path.read_text

        def write(self, data, *args, **kwargs):
            if 'encoding' not in kwargs and not args:
                data.encode('cp1252')
                kwargs['encoding'] = 'utf-8'
            return original_write(self, data, *args, **kwargs)

        def read(self, *args, **kwargs):
            kwargs.setdefault('encoding', 'cp1252')
            return original_read(self, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'workspace.json'
            with patch.object(server, 'DB', db), patch.object(Path, 'write_text', write), patch.object(Path, 'read_text', read):
                server.seed()
                loaded = server.load()
        self.assertIn('完整', loaded['models'][0]['description'])

    def test_bundled_python_env_prefers_cineharbor_name(self):
        with patch.dict(os.environ, {'CINEHARBOR_PYTHON': '/opt/cineharbor/python', 'GC_LABS_PYTHON': '/opt/gc-labs/python'}):
            self.assertEqual(server.sdk_python(), '/opt/cineharbor/python')
        with patch.dict(os.environ, {'GC_LABS_PYTHON': '/opt/gc-labs/python'}, clear=False):
            os.environ.pop('CINEHARBOR_PYTHON', None)
            self.assertEqual(server.sdk_python(), '/opt/gc-labs/python')


class V050StudioAndGuardrailsHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.a = self.d / 'assets'
        self.a.mkdir()
        self.db = self.d / 'workspace.json'
        (self.d / 'profile.json').write_text(json.dumps({'expected_account': 'director@example.com'}))
        self.db.write_text(json.dumps({
            'schema_version': 2,
            'project': {'id': 'p05', 'name': 'Open Source Film', 'ratio': '16:9', 'status': 'active'},
            'assets': [], 'elements': [], 'shots': [], 'workflows': [], 'models': server.MODELS,
            'jobs': [], 'historical_jobs': [], 'events': [],
            'policy': {'expected_account': 'director@example.com', 'gpu': 'G4', 'max_minutes': 240, 'max_cu_budget': 0, 'auto_release': False}
        }))
        self.p = [
            patch.object(server, 'DATA', self.d),
            patch.object(server, 'DB', self.db),
            patch.object(server, 'ASSETS', self.a),
            patch.object(server, 'SOURCE', self.d / 'source'),
            patch.object(server, 'MONITOR', None),
        ]
        for p in self.p:
            p.start()
        self.h = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.port = self.h.server_port
        self.console = Console(server)
        extra = [patch.object(server, 'PORT', self.port), patch.object(server, 'CONSOLE', self.console)]
        for p in extra:
            p.start()
        self.p += extra
        threading.Thread(target=self.h.serve_forever, daemon=True).start()

    def tearDown(self):
        try:
            if server.MONITOR:
                server.MONITOR.stop()
        except Exception:
            pass
        self.h.shutdown()
        self.h.server_close()
        for p in reversed(self.p):
            p.stop()
        self.tmp.cleanup()

    def api(self, path, body=None):
        req = urllib.request.Request(
            f'http://127.0.0.1:{self.port}{path}',
            data=None if body is None else json.dumps(body).encode(),
            headers={'X-Local-Key': server.KEY, 'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    def test_template_convert_auto_upgrades_to_full_precision_preset(self):
        saved = self.api('/api/workflow/convert', {'template': 'video_wan2_2_14B_i2v', 'name': 'Wan Full FP16', 'save': True})
        self.assertGreaterEqual(len(saved['model_files']), 4)
        graph_str = json.dumps(saved['graph'])
        self.assertIn('wan2.2_i2v_high_noise_14B_fp16.safetensors', graph_str)
        self.assertIn('umt5_xxl_fp16.safetensors', graph_str)
        self.assertNotIn('fp8_scaled', graph_str)

    def test_elements_inheritance_and_multi_take_hero_selection(self):
        # Upload a character reference image
        self.api('/api/asset', {'name': 'hero.png', 'data': base64.b64encode(b'\x89PNG\r\n\x1a\nhero').decode()})
        img_id = server.load()['assets'][0]['id']

        # Create @艾伦 element card
        elem = self.api('/api/element', {
            'kind': 'character',
            'tag': '艾伦',
            'prompt_snippet': '30yo astronaut in weathered white suit',
            'asset_id': img_id
        })
        self.assertEqual(elem['tag'], '艾伦')

        # Create shot without explicit reference image, bound to @艾伦
        self.api('/api/shot/new', {})
        shot_id = server.load()['shots'][0]['id']
        workflow = self.api('/api/workflow/convert', {'template':'video_wan2_2_14B_i2v', 'save':True})
        self.api('/api/shot', {'id': shot_id, 'workflow': workflow['id'], 'title': 'Mars Walk', 'prompt': 'walking through red dust storm', 'elements': [elem['id']]})

        # Creating a job automatically injects element snippet & inherits reference image!
        self.api('/api/job', {'shot': shot_id})
        job1 = server.load()['jobs'][0]
        self.assertIn('30yo astronaut in weathered white suit', job1['config']['prompt'])
        self.assertEqual(job1['config']['reference'], img_id)

        # Create second job with another seed to verify multi-take recording
        self.api('/api/shot', {'id': shot_id, 'seed': 9999})
        self.api('/api/job', {'shot': shot_id})
        job2 = server.load()['jobs'][0]

        out1 = self.d / 'take1.mp4'
        out2 = self.d / 'take2.mp4'
        out1.write_bytes(b'video-take-1')
        out2.write_bytes(b'video-take-2')

        with patch.object(server, 'guarded'):
            with patch.object(self.console, 'remote', return_value={'local_files': [str(out1)]}):
                self.console.run({'id': 'op1', 'action': 'generate', 'label': 'g1', 'state': 'queued', 'created': 1, 'events': []}, {'job': job1['id']})
            with patch.object(self.console, 'remote', return_value={'local_files': [str(out2)]}):
                self.console.run({'id': 'op2', 'action': 'generate', 'label': 'g2', 'state': 'queued', 'created': 2, 'events': []}, {'job': job2['id']})

        shot_after = server.load()['shots'][0]
        self.assertEqual(len(shot_after['takes']), 2)
        take1_asset = shot_after['takes'][1]['asset_id']
        take2_asset = shot_after['takes'][0]['asset_id']
        self.assertEqual(shot_after['output'], take2_asset)

        # Switch Hero Take back to Take 1
        cached=server.load();cached['shots'][0]['qc_strip_file']='old-take-strip.jpg';server.save(cached)
        self.api('/api/shot/select-take', {'shot_id': shot_id, 'asset_id': take1_asset})
        self.assertEqual(server.load()['shots'][0]['output'], take1_asset)
        self.assertNotIn('qc_strip_file',server.load()['shots'][0])

    def test_cu_budget_guardrail_pauses_subsequent_queue_without_killing_gpu(self):
        self.api('/api/policy', {'max_minutes': 120, 'max_cu_budget': 10.0})
        wf = self.api('/api/workflow', {
            'name': 'T2I', 'kind': 'image',
            'graph': {'1': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'a', 'clip': None}}, '2': {'class_type': 'SaveImage', 'inputs': {'images': ['1', 0]}}}
        })
        jobs = []
        for idx in range(2):
            self.api('/api/shot/new', {})
            sid = server.load()['shots'][-1]['id']
            self.api('/api/shot', {'id': sid, 'title': f'S{idx}', 'prompt': 'p', 'model': 'workflow', 'workflow': wf['id']})
            self.api('/api/job', {'shot': sid})
            jobs.append(server.load()['jobs'][0]['id'])

        (self.d / 'lease.json').write_text(json.dumps({'session': server.SESSION, 'endpoint': 'g4-ep', 'state': 'active', 'start_balance': 100.0}))

        # Shot 1 runs while balance is 95.0 (spent 5 < 10); before Shot 2 starts, balance is 88.0 (spent 12 >= 10)!
        balances = iter([95.0, 88.0, 88.0])
        ran = []

        def fake_remote(d, kind, body):
            ran.append(body['job'])
            f = self.d / f"{body['job']}.png"
            f.write_bytes(b'\x89PNG\r\n\x1a\nx')
            return {'local_files': [str(f)]}

        with patch.object(server, 'identity', return_value='director@example.com'), \
             patch.object(server, 'refresh', side_effect=lambda: {'balance': next(balances, 88.0), 'runtime_state': 'owned', 'managed_session': {'endpoint': 'g4-ep'}}), \
             patch.object(self.console, 'remote', side_effect=fake_remote):
            self.api('/api/operations', {'action': 'generate_batch', 'jobs': jobs, 'cloud_data_consent': True, 'cloud_data_notice_version': '2026-11-21'})
            for _ in range(40):
                if not any(o['state'] in ('queued', 'running') for o in self.api('/api/operations')):
                    break
                time.sleep(0.05)

        self.assertEqual(ran, [jobs[0]], 'Second job must be paused when CU budget is exceeded')
        self.assertTrue(server.load()['policy']['budget_paused'])
        self.assertTrue((self.d / 'lease.json').exists(), 'GPU lease must remain intact for inspection & backup')

    def test_mobile_readonly_monitor_security_and_qr_svg(self):
        (self.d / 'live_status.json').write_text(json.dumps({'email': 'director@example.com', 'balance': 881.72, 'rate': 0.0, 'active': 0, 'runtime_state': 'idle', 'checked_at': 'now'}))
        # Exercise the real HTTP handler without exposing the test server to the LAN.
        monitor_http_server = mobile_monitor.ThreadingHTTPServer
        with (
            patch.object(mobile_monitor, '_detect_lan_ips', return_value=['127.0.0.1']),
            patch.object(mobile_monitor, 'ThreadingHTTPServer',
                         side_effect=lambda _address, handler: monitor_http_server(('127.0.0.1', 0), handler)),
        ):
            st = self.api('/api/monitor/toggle', {'enabled': True})
        self.assertTrue(st['enabled'])
        self.assertIn('<svg', st['qr_svg'])
        token_path = '/m/' + st['primary_url'].split('/m/')[1]
        mon_base = f"http://127.0.0.1:{st['port']}{token_path}"

        with urllib.request.urlopen(mon_base + '/data', timeout=5) as r:
            snap = json.load(r)
        self.assertEqual(snap['account'], 'di***@example.com')
        self.assertNotIn('director@example.com', json.dumps(snap))

        # POST to monitor port must be rejected (read-only!)
        post_req = urllib.request.Request(mon_base + '/data', data=b'{}', method='POST')
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(post_req, timeout=5)
        self.assertIn(ctx.exception.code, (405, 501))

        off = self.api('/api/monitor/toggle', {'enabled': False})
        self.assertFalse(off['enabled'])

    def test_status_hides_missing_colab_cli_path(self):
        missing = self.d / 'missing-colab'
        with patch.object(server, 'CLI', missing), patch.dict(os.environ, {}, clear=False):
            for key in ('CINEHARBOR_CLI_ENTRY', 'GC_LABS_CLI_ENTRY', 'CINEHARBOR_PYTHON', 'GC_LABS_PYTHON'):
                os.environ.pop(key, None)
            req = urllib.request.Request(f'http://127.0.0.1:{self.port}/api/status', headers={'X-Local-Key': server.KEY})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(req, timeout=20)
        body = caught.exception.read().decode()
        self.assertEqual(caught.exception.code, 502)
        self.assertNotIn(str(missing), body)
        self.assertNotIn(str(Path.home()), body)
        self.assertIn('Colab CLI', body)
        self.assertNotIn('no such file', body.lower())

    @unittest.skipUnless(os.name == "posix", "Requires POSIX executable permission and file format errors")
    def test_status_reports_cli_startup_errors_separately(self):
        for file_mode, phrase in ((0o600, '权限不足'), (0o700, '文件格式不正确')):
            with self.subTest(file_mode=file_mode):
                candidate = self.d / 'colab'
                candidate.write_text('Not an executable')
                candidate.chmod(file_mode)
                with patch.object(server, 'CLI', candidate), patch.dict(os.environ, {}, clear=False):
                    for key in ('CINEHARBOR_CLI_ENTRY', 'GC_LABS_CLI_ENTRY'):
                        os.environ.pop(key, None)
                    req = urllib.request.Request(f'http://127.0.0.1:{self.port}/api/status')
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(req, timeout=20)
                body = caught.exception.read().decode()
                self.assertEqual(caught.exception.code, 502)
                self.assertIn(phrase, body)
                self.assertNotIn(server.COLAB_CLI_MISSING, body)
                self.assertNotIn(str(candidate), body)


if __name__ == '__main__':
    unittest.main()
