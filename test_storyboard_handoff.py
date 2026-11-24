import base64,json,tempfile,unittest
from pathlib import Path
from storyboard_handoff import prepare
class HandoffTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'ref.png').write_bytes(b'image fixture')
  self.w={'project':{'name':'New Film','ratio':'16:9'},'assets':[{'id':'a','kind':'image','file':'ref.png'}],'workflows':[{'id':'w','name':'Video','graph':{'1':{'class_type':'LoadImage','inputs':{'image':'old.png'}},'2':{'class_type':'Sample','inputs':{'image':['1',0],'prompt':'old','seed':1}}},'bindings':{'reference':[{'node':'1','input':'image'}],'prompt':[{'node':'2','input':'prompt'}],'seed':[{'node':'2','input':'seed'}]},'timing':{'fps':24,'frame_multiple':17,'frame_offset':5}}],'shots':[{'id':'s','title':'Launch','workflow':'w','prompt':'Launch upward','seed':35,'duration':5,'reference':'a','x':200,'y':80}]}
 def test_materializes_without_mutation_or_paths(self):
  before=json.dumps(self.w);p=prepare(self.w,self.root);self.assertEqual(before,json.dumps(self.w));self.assertEqual(p['graph']['2']['inputs']['prompt'],'Launch upward');self.assertEqual(p['graph']['2']['inputs']['seed'],35);self.assertNotIn(str(self.root),json.dumps(p));self.assertEqual(base64.b64decode(p['images'][0]['base64']),b'image fixture');self.assertEqual(p['shots'][0]['frames'],124);self.assertFalse(p['round_trip'])
 def test_two_shots_have_disjoint_links(self):
  self.w['shots'].append({**self.w['shots'][0],'id':'s2','title':'Cloud','x':1000});p=prepare(self.w,self.root);self.assertEqual(p['graph']['4']['inputs']['image'],['3',0]);self.assertEqual(len(p['images']),1);self.assertGreater(p['positions']['3'][0],p['positions']['1'][0])
 def test_missing_reference_fails(self):
  self.w['shots'][0]['reference']=None
  with self.assertRaises(ValueError):prepare(self.w,self.root)
 def test_unsupported_last_frame_fails(self):
  self.w['shots'][0]['end_reference']='a'
  with self.assertRaisesRegex(ValueError,'last-frame'):prepare(self.w,self.root)
 def test_unselected_unsupported_shot_does_not_block(self):
  self.w['shots'].append({'id':'bad'});self.assertEqual(len(prepare(self.w,self.root,['s'])['shots']),1)
 def test_traversal_rejected(self):
  self.w['assets'][0]['file']='../secret.png'
  with self.assertRaises(ValueError):prepare(self.w,self.root)
 def test_missing_workflow_does_not_guess(self):
  self.w['shots'][0]['workflow']='missing'
  with self.assertRaises(ValueError):prepare(self.w,self.root)
if __name__=='__main__':unittest.main()
