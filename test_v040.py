"""GC Labs 0.4.0 comprehensive offline test suite:
- Open-source privacy & zero-monkey-patch architecture audit
- Core/Shell capabilities & health 0.4.0
- FIFO Batch Queue, queue cancellation & safe /interrupt (no GPU released)
- LiteGraph + Subgraph -> API recipe conversion across all 4 official templates
- Custom node 40-char commit SHA lockfile validation & isolated setup
- Real native AVFoundation frame chaining, MP4 rough-cut render, FCPXML 1.10 & CapCut draft export
"""
import base64, io, json, math, shutil, struct, subprocess, tempfile, threading, time, unittest, urllib.error, urllib.request, wave, xml.etree.ElementTree as ET, zipfile
from pathlib import Path
from unittest.mock import patch
import server
from console import Console
from workflow_library import validate_custom_nodes, recipe
from workflow_converter import convert_canvas_to_api

REPO = Path(__file__).resolve().parent


class ArchitectureAndPrivacyAudit(unittest.TestCase):
    def test_no_personal_identifiers_in_tracked_source(self):
        forbidden = ('imjasper', 'jiasihao', 'Tesla RTX 先装个驱动', 'Tesla_RTX_车型声音字幕修正版')
        checked = 0
        for ext in ('*.py', '*.js', '*.cjs', '*.swift', '*.html', '*.css', '*.md', '*.toml', '*.yml'):
            for p in REPO.rglob(ext):
                if any(part in ('vendor', 'releases', 'build', 'backups', 'data') for part in p.relative_to(REPO).parts) or p.name in ('工作交接.txt', '研究与验收.md'):
                    continue
                text = p.read_text(encoding='utf-8', errors='replace')
                if p.name != 'test_v040.py':
                    for word in forbidden:
                        self.assertNotIn(word, text, f'Personal identifier {word!r} leaked in {p.relative_to(REPO)}')
                checked += 1
        self.assertGreaterEqual(checked, 20)

    def test_zero_html_monkey_patch_replace_in_feature_modules(self):
        for name in ('console-ui.js', 'account-ui.js', 'canvas-ui.js', 'elements-ui.js', 'workflows-ui.js', 'assembly-ui.js'):
            src = (REPO / 'web' / name).read_text(encoding='utf-8')
            # Only filename regex replace(/\.json$/i,'') is allowed; zero HTML template .replace('<...')
            self.assertNotIn(".replace('<", src, f'HTML monkey-patch found in {name}')
            self.assertNotIn(".replace('尚未", src, f'Text monkey-patch found in {name}')
            self.assertNotIn(".replace('>火星", src, f'Hardcoded project monkey-patch found in {name}')

    def test_runtime_dir_contains_only_core_engine_files(self):
        files = {p.name for p in (REPO / 'runtime').iterdir() if p.is_file()}
        self.assertEqual(files, {'colab_entry.py', 'control_gateway.py', 'drive_auth.py', 'local_bridge.py', 'managed_runtime.py'})


class CustomNodeLockAndConverter(unittest.TestCase):
    def test_custom_node_lock_validation(self):
        sha = 'a' * 40
        locked = validate_custom_nodes([{'repo': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite', 'commit': sha}])
        self.assertEqual(locked[0]['name'], 'ComfyUI-VideoHelperSuite')
        self.assertEqual(locked[0]['commit'], sha)
        for bad in [
            [{'repo': 'https://github.com/owner/repo', 'commit': 'main'}],
            [{'repo': 'https://gitlab.com/owner/repo', 'commit': sha}],
            [{'repo': 'https://user:token@github.com/owner/repo', 'commit': sha}],
            [{'repo': 'https://github.com/owner/repo?token=1', 'commit': sha}],
            [{'repo': 'https://github.com/owner/repo', 'commit': sha, 'name': '../escape'}],
        ]:
            with self.assertRaises(ValueError):
                validate_custom_nodes(bad)

    def test_all_four_official_canvas_templates_convert_cleanly(self):
        tpl_dir = REPO / 'assets/workflow-templates'
        expected_kinds = {
            'audio_ace_step_1_5_split_4b.json': 'audio',
            'image_qwen_Image_2512.json': 'image',
            'video_ltx2_5_i2v.json': 'video',
            'video_wan2_2_14B_i2v.json': 'video',
        }
        for fname, kind in expected_kinds.items():
            raw = json.loads((tpl_dir / fname).read_text())
            conv = convert_canvas_to_api(raw)
            self.assertEqual(conv['kind'], kind)
            rec = recipe({'name': fname, **conv})
            self.assertGreaterEqual(len(rec['graph']), 8)
            self.assertIn('prompt', rec['bindings'])

    def test_managed_runtime_setup_installs_locked_custom_nodes_without_requiring_h3(self):
        import types, sys
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            src = (REPO / 'workflow_library.py').read_text() + '\n' + (REPO / 'runtime/managed_runtime.py').read_text().split("kind=CONTROL['action'];event")[0]
            for a, b in [('/content/ComfyUI', 'ComfyUI'), ('/content/jasper_workstation', 'work'), ('/content/jasper_comfy_env', 'env'), ('/content/drive/MyDrive/AI_Workstations/Jasper_Workstation', 'backup'), ('/content/drive/MyDrive/AI_Workstations/MiniMax_H3_official', 'H3')]:
                src = src.replace(repr(a), repr(str(d / b)))
            src = src.replace(repr('/content'), repr(str(d)))
            ns = {}
            exec(compile(src, 'setup_cn_test', 'exec'), ns)

            sha = 'b' * 40
            calls = []

            def fake_run(args):
                calls.append(args)
                if 'checkout' in args:
                    target = Path(args[2])
                    if target == ns['ROOT']:
                        (target / 'main.py').write_text('')
                if '-m' in args and 'venv' in args:
                    venv_py = Path(args[-1]) / 'bin/python'
                    venv_py.parent.mkdir(parents=True, exist_ok=True)
                    venv_py.write_text('')

            class DummyProc:
                pid = 43210

            fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True, get_device_properties=lambda _: types.SimpleNamespace(total_memory=96 * 2 ** 30)))
            ns['CONTROL'] = {'custom_nodes': [{'repo': 'https://github.com/Wan-Video/ComfyUI-Wan', 'commit': sha}], 'require_h3': False}
            ns['setup_run'] = fake_run
            ns['request'] = lambda path, data=None: {'WanImageToVideo': {}}  # Note: no MiniMaxH3ImageToVideo!
            with patch.dict(sys.modules, {'torch': fake_torch}), patch.object(ns['subprocess'], 'Popen', return_value=DummyProc()):
                res = ns['setup']()
            self.assertTrue(res['online'])
            self.assertEqual(res['custom_nodes_installed'], 1)
            self.assertTrue(any(sha in cmd for cmd in calls))


class BatchQueueInterruptAndMediaHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.a = self.d / 'assets'
        self.a.mkdir()
        self.db = self.d / 'workspace.json'
        (self.d / 'profile.json').write_text(json.dumps({'expected_account': 'creator@example.com'}))
        self.db.write_text(json.dumps({
            'schema_version': 2,
            'project': {'id': 'p1', 'name': 'Local Studio Test', 'ratio': '9:16', 'status': 'active'},
            'assets': [], 'shots': [], 'workflows': [], 'models': server.MODELS,
            'jobs': [], 'historical_jobs': [], 'events': [],
            'policy': {'expected_account': 'creator@example.com', 'gpu': 'G4', 'max_minutes': 240, 'auto_release': False}
        }))
        self.p = [
            patch.object(server, 'DATA', self.d),
            patch.object(server, 'DB', self.db),
            patch.object(server, 'ASSETS', self.a),
            patch.object(server, 'SOURCE', self.d / 'source'),
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
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def _make_sample_mp4_and_wav(self, fps=12):
        """Create a real valid 1-second MP4 and WAV using native macOS sips + gclabs-media / existing sample."""
        wav_path = self.d / 'tone.wav'
        with wave.open(str(wav_path), 'w') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(b''.join(struct.pack('<h', int(3000 * math.sin(2 * math.pi * 330 * i / 24000))) for i in range(24000)))

        # Generate a tiny synthetic MP4 via Swift AVAssetWriter so test has zero external media dependency
        mp4_path = self.d / f'tiny-{fps}.mp4'
        swift_gen = self.d / 'gen_mp4.swift'
        swift_gen.write_text("""
import Foundation
import AVFoundation
import CoreVideo
let out = URL(fileURLWithPath: CommandLine.arguments[1])
let fps = Int(CommandLine.arguments[2])!
let writer = try! AVAssetWriter(outputURL: out, fileType: .mp4)
let settings: [String: Any] = [AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: 320, AVVideoHeightKey: 568]
let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
    kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32ARGB),
    kCVPixelBufferWidthKey as String: 320,
    kCVPixelBufferHeightKey as String: 568
])
writer.add(input)
writer.startWriting()
writer.startSession(atSourceTime: .zero)
for f in 0..<fps {
    while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.005) }
    var pb: CVPixelBuffer?
    CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &pb)
    CVPixelBufferLockBaseAddress(pb!, [])
    let ptr = CVPixelBufferGetBaseAddress(pb!)!.assumingMemoryBound(to: UInt8.self)
    let bytesPerRow = CVPixelBufferGetBytesPerRow(pb!)
    for y in 0..<568 {
        for x in 0..<320 {
            let off = y * bytesPerRow + x * 4
            ptr[off] = 255; ptr[off+1] = UInt8((f * 20) % 255); ptr[off+2] = UInt8((x * 255) / 320); ptr[off+3] = UInt8((y * 255) / 568)
        }
    }
    CVPixelBufferUnlockBaseAddress(pb!, [])
    adaptor.append(pb!, withPresentationTime: CMTime(value: Int64(f), timescale: Int32(fps)))
}
input.markAsFinished()
let sem = DispatchSemaphore(value: 0)
writer.finishWriting { sem.signal() }
sem.wait()
""")
        subprocess.run(['swiftc', '-target', 'arm64-apple-macos13.0', '-framework', 'AVFoundation', '-framework', 'CoreVideo', '-framework', 'CoreMedia', str(swift_gen), '-o', str(self.d / 'gen_mp4')], check=True)
        subprocess.run([str(self.d / 'gen_mp4'), str(mp4_path), str(fps)], check=True)
        return mp4_path, wav_path

    @unittest.skipUnless(__import__('sys').platform == 'darwin', 'Native AVFoundation test runs on macOS')
    def test_last_frame_at_24_30_60_fps(self):
        from timeline_export import extract_video_frame
        for fps in (24, 30, 60):
            clip, _ = self._make_sample_mp4_and_wav(fps)
            frame = extract_video_frame(server.ROOT, clip, self.d / f'last-{fps}.png', 'last')
            self.assertAlmostEqual(frame['timestamp'], 1 - 1/fps, delta=0.001)

    def test_capabilities_and_template_convert_endpoint(self):
        cap = self.api('/api/capabilities')
        self.assertEqual(cap['version'], server.PRODUCT['version'])
        if __import__('sys').platform == 'darwin':
            self.assertTrue(cap['media_engine'])
        self.assertIn('batch_queue', cap['features'])

        saved = self.api('/api/workflow/convert', {'template': 'image_qwen_Image_2512', 'name': 'Qwen2512', 'save': True})
        self.assertEqual(saved['kind'], 'image')
        self.assertEqual(len(self.api('/api/workflows')), 1)

    def test_batch_queue_fifo_and_safe_interrupt(self):
        # Create a text-to-image workflow so no reference image is needed
        wf = self.api('/api/workflow', {
            'name': 'T2I', 'kind': 'image',
            'graph': {'1': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'hi', 'clip': None}}, '2': {'class_type': 'SaveImage', 'inputs': {'images': ['1', 0]}}}
        })
        job_ids = []
        for idx in range(3):
            self.api('/api/shot/new', {})
            shot = server.load()['shots'][-1]
            self.api('/api/shot', {'id': shot['id'], 'title': f'Shot {idx+1}', 'prompt': f'Prompt {idx+1}', 'model': 'workflow', 'workflow': wf['id']})
            self.api('/api/job', {'shot': shot['id']})
            job_ids.append(server.load()['jobs'][0]['id'])

        executed_order = []
        gate = threading.Event()

        def fake_remote(d, kind, body):
            executed_order.append(body['job'])
            if len(executed_order) == 1:
                gate.wait(timeout=2.0)
            out = self.d / f"out_{body['job']}.png"
            out.write_bytes(b'\x89PNG\r\n\x1a\nfake')
            return {'local_files': [str(out)]}

        with patch.object(server, 'identity', return_value='creator@example.com'), patch.object(self.console, 'remote', side_effect=fake_remote):
            batch_res = self.api('/api/operations', {'action': 'generate_batch', 'jobs': job_ids, 'cloud_data_consent': True, 'cloud_data_notice_version': '2026-11-21'})
            self.assertEqual(batch_res['queued_count'], 3)
            time.sleep(0.15)
            # Cancel the 3rd queued job before Shot 1 finishes
            ops = self.api('/api/operations')
            third_op = next(o for o in ops if o.get('job_id') == job_ids[2])
            cancel_res = self.api('/api/operations/cancel-queued', {'id': third_op['id']})
            self.assertEqual(cancel_res['cancelled_queued'], 1)
            gate.set()
            for _ in range(40):
                if not any(o['state'] in ('queued', 'running') for o in self.api('/api/operations')):
                    break
                time.sleep(0.05)

        self.assertEqual(executed_order, [job_ids[0], job_ids[1]])

        # Verify safe interrupt calls control_gateway with action='interrupt' and preserves lease.json
        (self.d / 'lease.json').write_text(json.dumps({'session': server.SESSION, 'endpoint': 'g4-ep', 'state': 'active'}))
        running_op = {'id': 'run1', 'action': 'generate', 'label': '生成作品', 'state': 'running', 'created': time.time(), 'events': []}
        self.console.write(running_op)
        with patch.object(server, 'identity', return_value='creator@example.com'), \
             patch.object(server, 'refresh', return_value={'runtime_state': 'owned', 'managed_session': {'endpoint': 'g4-ep', 'name': server.SESSION}}), \
             patch.object(server, 'sdk_python', return_value=__import__('sys').executable), \
             patch('console.subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            intr = self.api('/api/runtime/interrupt', {})
            self.assertTrue(intr['interrupted'])
            self.assertTrue((self.d / 'lease.json').exists(), 'Interrupt must NEVER delete GPU lease')
            sent_payload = json.loads(mock_run.call_args.kwargs['input'])
            self.assertEqual(sent_payload, {'action': 'interrupt'})

    @unittest.skipUnless(__import__('sys').platform == 'darwin', 'Native AVFoundation test runs on macOS')
    def test_native_frame_chaining_and_rough_cut_fcpxml_capcut_exports(self):
        mp4_path, wav_path = self._make_sample_mp4_and_wav()
        self.api('/api/asset', {'name': 'clip.mp4', 'data': base64.b64encode(mp4_path.read_bytes()).decode()})
        self.api('/api/asset', {'name': 'bgm.wav', 'data': base64.b64encode(wav_path.read_bytes()).decode()})
        ws = server.load()
        vid_asset = next(a for a in ws['assets'] if a['kind'] == 'video')
        aud_asset = next(a for a in ws['assets'] if a['kind'] == 'audio')

        # Create Shot 1 with output video
        self.api('/api/shot/new', {})
        ws = server.load()
        ws['shots'][0]['title'] = 'Opening Shot'
        ws['shots'][0]['output'] = vid_asset['id']
        server.save(ws)
        shot1_id = ws['shots'][0]['id']

        # 1. Frame chaining: extract last frame and auto-create Shot 2 bound to that PNG
        chained = self.api('/api/shot/chain-frame', {'source_shot': shot1_id, 'position': 'last', 'target': 'new'})
        self.assertTrue(chained['ok'])
        ws = server.load()
        self.assertEqual(len(ws['shots']), 2)
        self.assertEqual(ws['shots'][1]['reference'], chained['asset']['id'])
        self.assertTrue((self.a / chained['asset']['file']).is_file())

        # Give Shot 2 the video output too so we test a 2-clip multi-track timeline
        ws['shots'][1]['output'] = vid_asset['id']
        server.save(ws)

        plan = self.api('/api/assembly/plan')
        self.assertEqual(len(plan['shots']), 2)
        self.assertEqual(len(plan['audios']), 1)

        payload = {
            'clips': [
                {'shot_id': ws['shots'][0]['id'], 'start': 0.0, 'end': 0.8},
                {'shot_id': ws['shots'][1]['id'], 'start': 0.1, 'end': 0.9},
            ],
            'audio_asset_id': aud_asset['id'],
            'audio_start': 0.0,
        }

        # 2. Native AVFoundation MP4 rough-cut render
        mp4_res = self.api('/api/assembly/render', payload)
        rendered_file = self.d / 'exports' / mp4_res['file']
        self.assertTrue(rendered_file.is_file())
        self.assertEqual(mp4_res['clips'], 2)
        self.assertAlmostEqual(mp4_res['duration'], 1.6, places=1)

        # 3. FCPXML 1.10 export
        fcp_res = self.api('/api/assembly/fcpxml', payload)
        xml_root = ET.parse(self.d / 'exports' / fcp_res['file']).getroot()
        self.assertEqual(xml_root.tag, 'fcpxml')
        self.assertEqual(xml_root.attrib['version'], '1.10')

        # 4. CapCut / Jianying draft ZIP export
        cc_res = self.api('/api/assembly/capcut', payload)
        with zipfile.ZipFile(self.d / 'exports' / cc_res['file']) as z:
            names = set(z.namelist())
            self.assertIn('draft_content.json', names)
            self.assertIn('draft_meta_info.json', names)
            draft = json.loads(z.read('draft_content.json'))
            self.assertEqual(len(draft['tracks']), 2)
            self.assertEqual(len(draft['tracks'][0]['segments']), 2)


if __name__ == '__main__':
    unittest.main()
