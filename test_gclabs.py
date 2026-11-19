"""No live cloud operations: account binding, adoption and release guards."""
import unittest, tempfile, json
from pathlib import Path
from unittest.mock import patch
import server
from console import Console
class Guards(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
  self.patches=[patch.object(server,'DATA',self.data),patch.object(server,'DB',self.data/'workspace.json')]
  for p in self.patches:p.start()
  server.seed();self.c=Console(server)
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def record(self,action):return {'id':'test','action':action,'state':'queued','events':[],'created':1}
 def test_new_install_requires_explicit_binding(self):
  with patch.object(server,'identity',return_value='one@example.com'):
   with self.assertRaisesRegex(ValueError,'确认绑定'):server.guarded()
   server.bind_account('one@example.com');self.assertEqual(server.guarded(),'one@example.com')
 def test_account_change_is_blocked(self):
  with patch.object(server,'identity',return_value='one@example.com'):server.bind_account('one@example.com')
  with patch.object(server,'identity',return_value='two@example.com'):
   with self.assertRaisesRegex(ValueError,'账号不匹配'):server.guarded()
 def test_live_lease_prevents_rebinding(self):
  (self.data/'lease.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'当前会话'):server.bind_account('one@example.com')
 def test_adopt_only_selected_g4_no_allocation(self):
  state={'runtime_state':'external','sessions':[{'endpoint':'g4','hardware':'G4','name':'?'},{'endpoint':'other','hardware':'T4','name':'?'}]}
  d=self.record('adopt')
  with patch.object(server,'guarded'),patch.object(server,'refresh',return_value=state),patch.object(server,'cli') as cli:self.c.run(d,{'endpoint':'g4'})
  cli.assert_not_called();self.assertEqual(d['state'],'succeeded');self.assertEqual(json.loads((self.data/'lease.json').read_text())['endpoint'],'g4')
 def test_wrong_hardware_cannot_be_adopted(self):
  d=self.record('adopt')
  with patch.object(server,'guarded'),patch.object(server,'refresh',return_value={'runtime_state':'external','sessions':[{'endpoint':'other','hardware':'T4','name':'?'}]}):self.c.run(d,{'endpoint':'other'})
  self.assertEqual(d['state'],'failed');self.assertFalse((self.data/'lease.json').exists())
 def test_failed_flush_keeps_gpu(self):
  d=self.record('stop')
  with patch.object(server,'guarded'),patch.object(self.c,'remote',return_value={'hash_verified':True,'drive_flushed':False}),patch.object(server,'_operation') as release:self.c.run(d,{'backup_confirmed':True})
  self.assertEqual(d['state'],'failed');release.assert_not_called()
class GenerationRecords(unittest.TestCase):
 setUp=Guards.setUp
 tearDown=Guards.tearDown
 record=Guards.record
 def prepare(self):
  assets=self.data/'assets';assets.mkdir();self.assetpatch=patch.object(server,'ASSETS',assets);self.assetpatch.start();self.addCleanup(self.assetpatch.stop)
  image=self.data/'ref.png';image.write_bytes(b'reference');d=server.load();d['assets']=[{'id':'ref','file':'ref.png','path':str(image),'kind':'image'}];d['shots']=[{'id':'shot'}];d['jobs']=[{'id':'job','shot':'shot','state':'prepared','config':{'model':'h3','reference':'ref'}}];server.save(d)
 def test_explicit_validation_rejection_can_retry(self):
  self.prepare();d=self.record('generate')
  def reject(record,*args):record['not_submitted']=True;raise RuntimeError('Rejected before queue')
  with patch.object(server,'guarded'),patch.object(self.c,'remote',side_effect=reject):self.c.run(d,{'job':'job'})
  job=server.load()['jobs'][0];self.assertEqual(job['state'],'prepared');self.assertFalse(job['attempted'])
 def test_unknown_submission_stays_attempted(self):
  self.prepare();d=self.record('generate')
  with patch.object(server,'guarded'),patch.object(self.c,'remote',side_effect=RuntimeError('Connection lost')):self.c.run(d,{'job':'job'})
  self.assertTrue(server.load()['jobs'][0]['attempted'])
 def test_generated_file_is_in_portable_backup(self):
  import zipfile
  self.prepare();d=self.record('generate');output=self.data/'generated.mp4';output.write_bytes(b'video-output')
  with patch.object(server,'guarded'),patch.object(self.c,'remote',return_value={'local_files':[str(output)]}):self.c.run(d,{'job':'job'})
  asset=server.load()['assets'][-1];self.assertNotIn('path',asset);self.assertEqual((server.ASSETS/asset['file']).read_bytes(),b'video-output')
  backup=server.local_backup()
  with zipfile.ZipFile(self.data/'exports'/backup['file']) as z:self.assertEqual(z.read('assets/'+asset['file']),b'video-output')
class BackupImport(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.assets=self.root/'assets';self.assets.mkdir()
  self.patches=[patch.object(server,'DATA',self.root),patch.object(server,'DB',self.root/'workspace.json'),patch.object(server,'ASSETS',self.assets)]
  for p in self.patches:p.start()
  server.seed();self.original=server.load()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def archive(self,change=None,extra=None):
  import io,zipfile,copy
  d=copy.deepcopy(self.original);d['assets']=[{'id':'asset','file':'a.png','kind':'image','name':'a'}];d['jobs']=[{'id':'old','attempted':True,'prompt_id':'remote-old'}]
  if change:change(d)
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:
   z.writestr('workspace.json',json.dumps(d));z.writestr('assets/a.png',b'reference')
   if extra:z.writestr(extra,b'x')
  return buf.getvalue()
 def test_import_keeps_original_and_archives_jobs(self):
  from workspace_backup import import_project
  result=import_project(server,self.archive());d=server.load()
  self.assertEqual(result['assets'],1);self.assertEqual(d['jobs'],[]);self.assertEqual(d['historical_jobs'][0]['prompt_id'],'remote-old')
  self.assertNotEqual(d['project']['id'],self.original['project']['id']);self.assertTrue((self.root/'projects'/(self.original['project']['id']+'.json')).exists());self.assertNotIn('path',d['assets'][0])
 def test_zip_path_traversal_is_rejected(self):
  from workspace_backup import import_project
  with self.assertRaisesRegex(ValueError,'不安全'):import_project(server,self.archive(extra='../escape'))
  self.assertEqual(server.load(),self.original);self.assertFalse(list(self.assets.iterdir()))
 def test_wrong_hash_does_not_write(self):
  from workspace_backup import import_project
  with self.assertRaisesRegex(ValueError,'校验失败'):import_project(server,self.archive(lambda d:d['assets'][0].update(sha256='bad')))
  self.assertFalse(list(self.assets.iterdir()))
 def test_external_path_not_restored(self):
  from workspace_backup import import_project
  result=import_project(server,self.archive(lambda d:d['assets'].append({'id':'outside','file':'missing.png','path':'/private/file','kind':'image'})))
  self.assertEqual(result['missing_external_assets'],1);self.assertEqual(len(server.load()['assets']),1)
class LocalBridgeCleanup(unittest.TestCase):
 def test_unrelated_process_is_not_killed(self):
  from types import SimpleNamespace
  from runtime.local_bridge import stop
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp);record=data/'bridge.json';record.write_text(json.dumps({'pid':123456,'endpoint':'g4'}));s=SimpleNamespace(DATA=data,ROOT=data/'code')
   with patch('runtime.local_bridge.subprocess.check_output',return_value='/other/process'),patch('runtime.local_bridge.os.kill') as kill:result=stop(s)
   self.assertFalse(result['stopped']);kill.assert_not_called();self.assertTrue(record.exists())
 def test_verified_local_process_only(self):
  from types import SimpleNamespace
  from runtime.local_bridge import stop
  import signal
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp);record=data/'bridge.json';record.write_text(json.dumps({'pid':123456,'endpoint':'g4'}));s=SimpleNamespace(DATA=data,ROOT=data/'code')
   with patch('runtime.local_bridge.subprocess.check_output',return_value=f'python {s.ROOT}/comfy_local_bridge.py --endpoint g4'),patch('runtime.local_bridge.os.kill',side_effect=[None,ProcessLookupError]) as kill:result=stop(s)
   self.assertTrue(result['stopped']);self.assertEqual(kill.call_args_list[0].args,(123456,signal.SIGTERM));self.assertFalse(record.exists())
if __name__=='__main__':unittest.main()
