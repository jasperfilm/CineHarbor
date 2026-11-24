import json,tempfile,unittest,threading,urllib.request,urllib.error,hashlib
from pathlib import Path
from unittest.mock import patch
import server
from console import Console
class Operations(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name);self.p=patch.object(server,'DATA',self.data);self.p.start();self.c=Console(server)
 def tearDown(self):self.p.stop();self.tmp.cleanup()
 def record(self,k):return {'id':'test','action':k,'label':k,'state':'queued','events':[],'created':1}
 def test_restart_does_not_allocate(self):
  self.c.write(self.record('start'))
  with patch.object(server,'cli') as cli:c=Console(server)
  self.assertEqual(c.all()[0]['state'],'interrupted');cli.assert_not_called()
 def test_no_gpu_downgrade(self):
  d=self.record('start')
  with patch.object(server,'guarded'),patch.object(server,'operation') as op:self.c.run(d,{'gpu':'T4'})
  self.assertEqual(d['state'],'failed');op.assert_not_called()
 def test_requested_interrupt_is_distinct_from_an_unexpected_failure(self):
  marker='RuntimeError: 采样已按指令安全中断；GPU 会话保留。'
  for error,expected in [(marker,'interrupted'),('network lost','failed'),('interrupt connection timed out','failed')]:
   d=self.record('generate');d.update(prompt_id='p1')
   db={'jobs':[{'id':'j1','state':'prepared','config':{'model':'workflow','reference':None}}],'assets':[]}
   with patch.object(server,'guarded'),patch.object(server,'load',return_value=db),patch.object(self.c,'job_update') as update,patch.object(self.c,'remote',side_effect=RuntimeError(error)):
    self.c.run(d,{'job':'j1'})
   self.assertEqual(d['state'],expected)
   if expected=='interrupted':
    self.assertEqual(d['message'],'采样已按指令安全中断；GPU 会话保留。')
    self.assertEqual(update.call_args.kwargs['state'],'interrupted')
 def test_backup_failure_prevents_release(self):
  d=self.record('stop')
  with patch.object(server,'guarded'),patch.object(self.c,'remote',side_effect=RuntimeError('hash mismatch')),patch.object(server,'_operation') as op:self.c.run(d,{'backup_confirmed':True})
  op.assert_not_called();self.assertEqual(d['state'],'failed')
 def test_backup_success_before_release(self):
  d=self.record('stop')
  with patch.object(server,'guarded'),patch.object(self.c,'remote',return_value={'hash_verified':True,'drive_flushed':True}),patch.object(server,'_operation',return_value={}) as op:self.c.run(d,{'backup_confirmed':True})
  op.assert_called_once_with('stop',{'backup_confirmed':True});self.assertEqual(d['state'],'succeeded')
 def test_external_lease_not_reconciled(self):
  p=self.data/'lease.json';p.write_text('{}');d=self.record('reconcile')
  with patch.object(server,'guarded'),patch.object(server,'refresh',return_value={'active':1,'runtime_state':'external'}):self.c.run(d,{})
  self.assertTrue(p.exists());self.assertEqual(d['state'],'failed')
 def test_idle_lease_archived(self):
  p=self.data/'lease.json';p.write_text('{}');d=self.record('reconcile')
  with patch.object(server,'guarded'),patch.object(server,'refresh',return_value={'active':0,'runtime_state':'idle'}):self.c.run(d,{})
  self.assertFalse(p.exists());self.assertTrue((self.c.root/'test_lease.record').exists())
class HTTP(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name);self.a=self.d/'assets';self.a.mkdir();self.db=self.d/'workspace.json';self.db.write_text(json.dumps({'schema_version':2,'project':{'id':'test','name':'Test','status':'completed'},'assets':[],'shots':[],'models':server.MODELS,'jobs':[],'events':[],'policy':{'max_minutes':240}}))
  self.p=[patch.object(server,'DATA',self.d),patch.object(server,'DB',self.db),patch.object(server,'ASSETS',self.a),patch.object(server,'SOURCE',self.d/'source')]
  for p in self.p:p.start()
  self.h=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.port=self.h.server_port
  extra=[patch.object(server,'PORT',self.port),patch.object(server,'CONSOLE',Console(server))]
  for p in extra:p.start()
  self.p+=extra;threading.Thread(target=self.h.serve_forever,daemon=True).start()
 def tearDown(self):
  self.h.shutdown();self.h.server_close()
  for p in reversed(self.p):p.stop()
  self.tmp.cleanup()
 def req(self,path,body=None,headers=None):
  h={'X-Local-Key':server.KEY};h.update(headers or {})
  return urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{self.port}'+path,data=None if body is None else json.dumps(body).encode(),headers=h))
 def test_completed_project_read_only(self):
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/shot/new',{})
  self.assertFalse(server.load()['shots'])
 def test_new_project_does_not_inherit_private_history(self):
  d=server.load();d['historical_jobs']=[{'prompt':'old-private-project'}];d['events']=[{'text':'old-private-event'}];server.save(d)
  self.req('/api/project/new',{'name':'Clean'}).close();fresh=server.load();self.assertEqual(fresh['historical_jobs'],[]);self.assertEqual(fresh['events'],[])
  self.assertEqual(json.loads((self.d/'projects/test.json').read_text())['historical_jobs'][0]['prompt'],'old-private-project')
 def test_project_round_trip(self):
  self.req('/api/project/new',{'name':'Next'}).close();self.assertEqual(server.load()['project']['name'],'Next')
  self.req('/api/project/select',{'id':'test'}).close();self.assertEqual(server.load()['project']['status'],'completed')
 def test_unreliable_notebook_url_is_disabled(self):
  with self.assertRaises(urllib.error.HTTPError) as error:self.req('/api/session-url')
  self.assertEqual(error.exception.code,409)
 def test_clean_install_has_empty_verification(self):
  with self.req('/api/verified') as r:self.assertEqual(json.load(r)['gpu'],'尚未验证')
 def test_no_lease_bridge_is_offline(self):
  with self.req('/api/bridge') as r:self.assertFalse(json.load(r)['ready'])
 def test_head_media_has_no_body(self):
  (self.a/'head.mp4').write_bytes(b'12345')
  req=urllib.request.Request(f'http://127.0.0.1:{self.port}/assets/head.mp4',method='HEAD')
  with urllib.request.urlopen(req) as r:self.assertEqual(r.read(),b'');self.assertEqual(r.headers['Content-Length'],'5')
 def test_range_exact(self):
  raw=b'0123456789'*100;(self.a/'a.mp4').write_bytes(raw)
  with self.req('/assets/a.mp4',headers={'Range':'bytes=9-99'}) as r:self.assertEqual(r.status,206);self.assertEqual(r.read(),raw[9:100]);self.assertEqual(r.headers['Content-Range'],'bytes 9-99/1000')
 def test_key_required(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.req('/api/project/new',{'name':'no'},{'X-Local-Key':'wrong'})
  self.assertEqual(e.exception.code,403)
 def test_backup_no_credentials(self):
  import zipfile
  with self.req('/api/local-backup',{}) as f:r=json.load(f)
  with zipfile.ZipFile(self.d/'exports'/r['file']) as z:self.assertEqual(set(z.namelist()),{'workspace.json','README.txt'})
 def test_project_path_rejected(self):
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/project/select',{'id':'../../secrets'})
 def test_assembly_settings_persist_across_project_switches(self):
  key={'X-Local-Key':server.KEY}
  self.req('/api/project/new',{'name':'Assembly QA'},key).close()
  d=server.load();pid=d['project']['id'];d['assets']=[{'id':'v','kind':'video','file':'v.mp4'},{'id':'a','kind':'audio','file':'a.mp3'}];d['shots']=[{'id':'s','duration':5}];server.save(d)
  payload={'clips':[{'shot_id':'s','asset_id':'v','start':1,'end':4,'mute_source_audio':True,'dialogue':'回家了。'}],'audio_asset_id':'a','audio_start':2,'target_aspect':'16:9','burn_subtitles':True,'ducking':True}
  with self.req('/api/assembly/settings',payload,key) as response:saved=json.load(response)['settings']
  self.assertEqual(json.loads(self.db.read_text())['assembly'],saved)
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/assembly/settings',dict(payload,audio_asset_id='missing'),key)
  self.assertEqual(server.load()['assembly'],saved)
  self.req('/api/project/new',{'name':'Other'},key).close();self.assertNotIn('assembly',server.load())
  self.req('/api/project/select',{'id':pid},key).close();self.assertEqual(server.load()['assembly'],saved)
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/assembly/settings',dict(payload,audio_start=float('nan')),key)
 def test_queued_shot_cannot_be_deleted_or_task_archived(self):
  d=server.load();d['project']['status']='active';d['shots']=[{'id':'shot','title':'Queued shot'}];d['jobs']=[{'id':'job','shot':'shot','state':'prepared'}];server.save(d)
  op={'id':'queue','created':1,'state':'queued','action':'generate','job_id':'job'};server.CONSOLE.write(op)
  for path in ('/api/shot/delete','/api/job/archive'):
   with self.assertRaises(urllib.error.HTTPError):self.req(path,{'id':'shot' if path.endswith('/delete') else 'job'})
  self.assertEqual(len(server.load()['shots']),1);self.assertEqual(len(server.load()['jobs']),1)
  op['state']='interrupted';server.CONSOLE.write(op);self.req('/api/job/archive',{'id':'job'}).close()
  saved=server.load();self.assertEqual(saved['jobs'],[]);self.assertEqual(saved['historical_jobs'][0]['state'],'cancelled')
 def test_deleting_shot_archives_its_unsubmitted_tasks(self):
  d=server.load();d['project']['status']='active';d['shots']=[{'id':'shot','title':'Unused shot'}];d['jobs']=[{'id':'job','shot':'shot','state':'prepared'}];server.save(d)
  self.req('/api/shot/delete',{'id':'shot'}).close();saved=server.load()
  self.assertEqual(saved['shots'],[]);self.assertEqual(saved['jobs'],[]);self.assertEqual(saved['shot_trash'][0]['id'],'shot')
  self.assertEqual(saved['historical_jobs'][0]['id'],'job')
class Recipes(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name)
  src=(server.ROOT/'runtime/managed_runtime.py').read_text().split("kind=CONTROL['action'];event")[0]
  for a,b in [('/content/ComfyUI','ComfyUI'),('/content/jasper_workstation','work'),('/content/drive/MyDrive/AI_Workstations/Jasper_Workstation','backup'),('/content/drive/MyDrive/AI_Workstations/MiniMax_H3_official','H3')]:src=src.replace(repr(a),repr(str(self.d/b)))
  src=src.replace(repr('/content'),repr(str(self.d)))
  self.n={};exec(compile(src,'recipe_test','exec'),self.n)
 def tearDown(self):self.tmp.cleanup()
 def manifest(self,hash):
  h=self.d/'H3';(h/'models').mkdir(parents=True);(h/'models/a').write_bytes(b'abc');(h/'models_manifest_bf16.json').write_text(json.dumps({'complete':True,'files':[{'file':'a','bytes':3,'sha256':hash}]}))
 def test_full_manifest_required(self):
  with self.assertRaisesRegex(RuntimeError,'完整 BF16'):self.n['restore']()
 def test_restore_hash_and_reuse(self):
  self.manifest(hashlib.sha256(b'abc').hexdigest());self.assertEqual(self.n['restore']()['verified_files'],1);self.assertEqual(self.n['restore']()['bytes'],3)
 def test_bad_hash_not_committed(self):
  self.manifest('0'*64)
  with self.assertRaisesRegex(RuntimeError,'哈希不符'):self.n['restore']()
  self.assertFalse((self.d/'ComfyUI/models/a').exists())
 def test_busy_queue_blocks_backup(self):
  self.n['request']=lambda *args:{'queue_running':[[0,'busy']]}
  with self.assertRaisesRegex(RuntimeError,'尚有'):self.n['queue_idle']()
 def test_existing_id_not_resubmitted(self):
  p=self.d/'work/jobs/job';p.mkdir(parents=True);(p/'submitted.json').write_text('{"prompt_id":"existing"}');out=self.d/'ComfyUI/output';out.mkdir(parents=True);(out/'clip.mp4').write_bytes(b'v');calls=[]
  self.n['CONTROL']={'job':'job','config':{}}
  def request(path,data=None):calls.append(path);return {'existing':{'outputs':{'16':{'videos':[{'filename':'clip.mp4'}]}},'status':{'status_str':'success'}}}
  self.n['request']=request;self.assertEqual(self.n['generate']()['prompt_id'],'existing');self.assertNotIn('/prompt',calls)
 def test_setup_preserves_restored_models(self):
  import types,sys
  root=self.n['ROOT'];root.mkdir();(root/'models').mkdir();(root/'models'/'weight').write_bytes(b'keep');calls=[]
  def command(args):
   calls.append(args)
   if 'checkout' in args:(root/'main.py').write_text('')
  fake=types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda:True,get_device_properties=lambda _:types.SimpleNamespace(total_memory=96*2**30)))
  self.n['setup_run']=command;self.n['request']=lambda path:{'MiniMaxH3ImageToVideo':{}}
  with patch.dict(sys.modules,{'torch':fake}):result=self.n['setup']()
  self.assertTrue(result['online']);self.assertEqual((root/'models'/'weight').read_bytes(),b'keep');self.assertTrue(any('fetch' in x for x in calls))
 def test_setup_logging_accepts_notebook_streams(self):
  import io,sys
  with patch.object(sys,'stderr',io.StringIO()):self.n['setup_run']([sys.executable,'-c','print("READY")'])
  self.assertIn('READY',(self.n['WORK']/'setup.log').read_text())
if __name__=='__main__':unittest.main()
