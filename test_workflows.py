"""Recipe edits and OAuth use only disposable files and fake Google responses."""
import copy,json,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch,Mock
from account_login import AccountLogin
from workflow_library import recipe,validate_graph,materialize,remote_validate,validate_model_files
from test_console import HTTP

GRAPH={'1':{'class_type':'CLIPTextEncode','inputs':{'text':'original','clip':None}},'2':{'class_type':'SaveImage','inputs':{'images':['1',0],'filename_prefix':'test'}}}
class Graphs(unittest.TestCase):
 def test_cycle_and_missing_source_rejected(self):
  g=copy.deepcopy(GRAPH);g['1']['inputs']['clip']=['2',0]
  with self.assertRaisesRegex(ValueError,'循环'):validate_graph(g)
  g['1']['inputs']['clip']=['gone',0]
  with self.assertRaisesRegex(ValueError,'不存在'):validate_graph(g)
 def test_snapshot_materialization_does_not_modify_source(self):
  r=recipe({'name':'image','kind':'image','graph':GRAPH});g=materialize(r,{'prompt':'new'})
  self.assertEqual(g['1']['inputs']['text'],'new');self.assertEqual(r['graph']['1']['inputs']['text'],'original')
 def test_recipe_versions_and_full_precision(self):
  first=recipe({'name':'v1','graph':GRAPH});new=recipe({'name':'v2','graph':GRAPH},first)
  self.assertEqual(new['revision'],2);self.assertEqual(new['versions'][0]['name'],'v1')
  with self.assertRaisesRegex(ValueError,'量化'):validate_model_files([{'file':'diffusion_models/model_fp8.safetensors','url':'https://huggingface.co/test/model/resolve/main/model.safetensors'}])
 def test_paid_and_missing_nodes_rejected(self):
  with self.assertRaisesRegex(ValueError,'缺少节点'):remote_validate(GRAPH,{})
  with self.assertRaisesRegex(ValueError,'付费'):remote_validate(GRAPH,{'CLIPTextEncode':{},'SaveImage':{'api_node':True}})
 def test_model_urls_no_embedded_secrets(self):
  with self.assertRaises(ValueError):validate_model_files([{'file':'diffusion_models/a.safetensors','url':'https://huggingface.co/test/repo/resolve/main/a?token=private'}])
 def test_workflow_cannot_store_api_secret(self):
  g=copy.deepcopy(GRAPH);g['1']['inputs']['api_key']='test'
  with self.assertRaisesRegex(ValueError,'密钥'):validate_graph(g)

class Login(unittest.TestCase):
 def test_no_secret_in_status_and_expiry(self):
  login=AccountLogin();flow=Mock();flow.authorization_url.return_value=('https://accounts.google.com/o/oauth2/auth?state=secret-state','state')
  with patch.object(login,'make_flow',return_value=flow):status=login.begin()
  self.assertNotIn('secret-state',json.dumps(status));self.assertNotIn('secret-state',json.dumps(login.status()))
  login.deadline=time.time()-1;self.assertEqual(login.status()['state'],'expired')
  with self.assertRaises(ValueError):login.redirect()
 def test_failed_exchange_does_not_replace_credentials(self):
  login=AccountLogin();flow=Mock();flow.fetch_token.side_effect=Exception('submitted-code-and-token')
  with patch.object(login,'persist') as persist:login.finish(flow,'private-code');persist.assert_not_called()
  self.assertEqual(login.status()['state'],'failed');self.assertNotIn('submitted-code',json.dumps(login.status()));self.assertIsNone(login.flow)
 def test_success_verifies_identity_before_persist(self):
  login=AccountLogin();flow=Mock()
  with patch.object(login,'verified_email',return_value='test@example.com'),patch.object(login,'persist') as persist:login.finish(flow,'fake-code');persist.assert_called_once_with(flow.credentials)
  self.assertEqual(login.status()['email'],'test@example.com');self.assertIsNone(login.url)
 def test_non_google_redirect_rejected(self):
  login=AccountLogin();flow=Mock();flow.authorization_url.return_value=('https://example.com/auth','state')
  with patch.object(login,'make_flow',return_value=flow):
   with self.assertRaisesRegex(ValueError,'异常'):login.begin()

class WorkflowHTTP(HTTP):
 def fresh(self):self.req('/api/project/new',{'name':'Recipe test'}).close()
 def post(self,path,body):
  with self.req(path,body) as r:return json.load(r)
 def test_recipe_revision_conflict_and_history(self):
  import urllib.error
  self.fresh();first=self.post('/api/workflow',{'name':'Image','kind':'image','graph':GRAPH})
  with self.assertRaises(urllib.error.HTTPError):self.post('/api/workflow',{**first,'name':'Changed','base_revision':0})
  saved=self.post('/api/workflow',{**first,'name':'Changed','base_revision':1});self.assertEqual(saved['revision'],2);self.assertEqual(saved['versions'][0]['name'],'Image')
 def test_text_to_image_job_has_immutable_workflow(self):
  self.fresh();item=self.post('/api/workflow',{'name':'Image','kind':'image','graph':GRAPH});self.post('/api/shot/new',{});shot=__import__('server').load()['shots'][0]
  self.post('/api/shot',{'id':shot['id'],'model':'workflow','workflow':item['id'],'prompt':'picture'})
  self.post('/api/job',{'shot':shot['id']});job=__import__('server').load()['jobs'][0]
  self.assertEqual(job['state'],'prepared');self.assertEqual(job['config']['recipe']['graph'],GRAPH)
  self.post('/api/workflow',{**item,'base_revision':1,'name':'changed'});self.assertEqual(__import__('server').load()['jobs'][0]['config']['recipe']['name'],'Image')
 def test_canvas_reorder_and_soft_delete(self):
  self.fresh();self.post('/api/shot/new',{});self.post('/api/shot/new',{});shots=__import__('server').load()['shots'];ids=[s['id'] for s in shots]
  self.post('/api/layout',{'shots':[{'id':ids[0],'x':230,'y':100}],'order':ids[::-1]});d=__import__('server').load();self.assertEqual(d['shots'][0]['id'],ids[1]);self.assertEqual(d['shots'][1]['x'],230)
  self.post('/api/shot/delete',{'id':ids[0]});d=__import__('server').load();self.assertEqual(len(d['shots']),1);self.assertEqual(d['shot_trash'][0]['id'],ids[0])

class GenericRuntime(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  source=Path('workflow_library.py').read_text()+'\n'+Path('runtime/managed_runtime.py').read_text().split("kind=CONTROL['action'];event")[0]
  for a,b in [('/content/ComfyUI','ComfyUI'),('/content/jasper_workstation','work'),('/content/drive/MyDrive/AI_Workstations/Jasper_Workstation','backup'),('/content/drive/MyDrive/AI_Workstations/MiniMax_H3_official','H3')]:source=source.replace(repr(a),repr(str(self.root/b)))
  source=source.replace(repr('/content'),repr(str(self.root)))
  self.ns={};exec(compile(source,'runtime-test','exec'),self.ns)
 def tearDown(self):self.temp.cleanup()
 def test_generic_audio_graph_download_tracking(self):
  graph={'1':{'class_type':'Music','inputs':{'prompt':'old','duration':10}},'2':{'class_type':'SaveAudio','inputs':{'audio':['1',0],'filename_prefix':'test'}}}
  r=recipe({'name':'Music','kind':'audio','graph':graph})
  output=self.root/'ComfyUI/output/song.flac';output.parent.mkdir(parents=True);output.write_bytes(b'generated')
  calls=[]
  def request(path,data=None):
   calls.append((path,data))
   if path=='/object_info':return {'Music':{},'SaveAudio':{}}
   if path=='/prompt':return {'prompt_id':'test-prompt'}
   if path=='/history/test-prompt':return {'test-prompt':{'outputs':{'2':{'audio':[{'filename':'song.flac'}]}},'status':{'status_str':'success'}}}
   raise AssertionError(path)
  self.ns.update(CONTROL={'job':'job','config':{'model':'workflow','recipe':r,'prompt':'new music','duration':120,'resolution':'1080P','seed':42},'reference':None},request=request)
  with patch.object(self.ns['subprocess'],'check_output',return_value='97887\n'):result=self.ns['generate']()
  self.assertEqual(result['outputs'],[str(output.resolve())]);submitted=next(data for path,data in calls if path=='/prompt')['prompt'];self.assertEqual(submitted['1']['inputs']['prompt'],'new music');self.assertEqual(submitted['1']['inputs']['duration'],120)
  self.ns['CONTROL']['prompt_id']='test-prompt';calls.clear();self.ns['generate'](True);self.assertFalse(any(path=='/prompt' for path,_ in calls))
 def test_model_cache_reuse_hash_and_no_download(self):
  raw=b'safetensors-test';import hashlib
  sha=hashlib.sha256(raw).hexdigest();url='https://huggingface.co/official/model/resolve/main/test.safetensors'
  root=self.root/'ComfyUI/models/diffusion_models';root.mkdir(parents=True);(root/'test.safetensors').write_bytes(raw)
  self.ns['request']=Mock(return_value={})
  self.ns.update(CONTROL={'model_files':[{'file':'diffusion_models/test.safetensors','url':url,'sha256':sha}]},queue_idle=lambda:None)
  original=self.ns['Path'].is_dir
  def is_dir(path):return True if str(path)=='/content/drive/MyDrive' else original(path)
  with patch.object(self.ns['Path'],'is_dir',is_dir),patch.object(self.ns['urllib'].request,'urlopen') as download:result=self.ns['prepare_models']();download.assert_not_called()
  self.assertTrue(result['hash_verified']);manifest=json.loads((self.root/'backup/model_library/manifest.json').read_text());self.assertEqual(manifest['files'][0]['sha256'],sha)
 def test_history_timeout_retains_existing_prompt_without_submission(self):
  output=self.root/'ComfyUI/output/existing.mp4';output.parent.mkdir(parents=True);output.write_bytes(b'existing result')
  calls=[]
  def request(path,data=None):
   calls.append(path)
   if path=='/prompt':raise AssertionError('An uncertain task must never be resubmitted')
   if len(calls)==1:raise TimeoutError('temporarily busy')
   return {'saved-prompt':{'outputs':{'1':{'videos':[{'filename':'existing.mp4'}]}},'status':{'status_str':'success'}}}
  self.ns.update(CONTROL={'job':'existing-job','prompt_id':'saved-prompt','config':{}},request=request,_start_ws_progress_watcher=lambda *a:None)
  with patch.object(self.ns['time'],'sleep'):
   result=self.ns['generate'](True)
  self.assertEqual(result['outputs'],[str(output.resolve())]);self.assertEqual(calls,['/history/saved-prompt']*2)
