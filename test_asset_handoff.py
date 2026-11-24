import ast
import copy
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from storyboard_handoff import prepare, freeze_assets
from comfy_asset_transfer import AssetTransfer
from comfy_project_store import digest,pack,restore


class AssetHandoff(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.media=self.root/'media';self.media.mkdir()
        self.assets=[]
        for ident,kind,suffix in [('image','image','.png'),('video','video','.mp4'),('audio','audio','.wav')]:
            p=self.media/(ident+suffix);p.write_bytes((ident+'-original-bytes').encode())
            self.assets.append({'id':ident,'name':'Approved '+ident,'kind':kind,'file':p.name})
        self.ws={'project':{'name':'Asset continuation QA','ratio':'16:9'},'assets':self.assets,
                 'shots':[{'id':'shot','title':'Approved launch','prompt':'Keep the original launch','seed':42,'duration':5,'resolution':'1080P','model':'h3','reference':'image','output':'video','dialogue':'Hello','subtitle_en':'Hello','takes':[{'id':'take','asset_id':'video'}]}],
                 'elements':[],'workflows':[],'assembly':{'audio_asset_id':'audio','clips':[]}}

    def stage(self):
        self.payload=prepare(self.ws,self.media,include_assets=True)
        self.cache=self.root/'cache';directory=self.cache/'comfy-handoffs';directory.mkdir(parents=True)
        self.token='a'*32;self.record=directory/(self.token+'.json')
        freeze_assets(self.ws,self.media,self.payload,directory/self.token)
        self.record.write_text(json.dumps(self.payload))

    def transport(self):
        # Run the actual production Remote.run and its protocol parsing, while
        # the SDK execution happens in an isolated CPU filesystem, not a VM.
        source=ast.parse(Path('comfy_local_bridge.py').read_text())
        namespace={'json':json}
        exec(compile(ast.Module(body=[n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='Remote'],type_ignores=[]),'<production-Remote>','exec'),namespace)
        root=self.root/'runtime/ComfyUI';kernel={}
        class CPUKernel:
            def execute_code(inner,code,**kw):
                code=code.replace('/content/ComfyUI',str(root))
                out=io.StringIO()
                with redirect_stdout(out):exec(code,kernel)
                return [{'output_type':'stream','text':out.getvalue()}]
        remote=namespace['Remote'].__new__(namespace['Remote']);remote.lock=threading.Lock();remote.runtime=CPUKernel();remote.meta_cache={'old':1};remote.meta_lock=threading.Lock()
        return remote,root

    def test_all_original_media_and_context_become_connectable_loader_nodes(self):
        original=copy.deepcopy(self.ws);self.stage()
        self.assertEqual(self.ws,original)
        self.assertEqual(self.payload['schema'],'cineharbor.comfy-handoff.v2')
        self.assertEqual(len(self.payload['assets']),3)
        self.assertNotIn(str(self.root),json.dumps(self.payload))
        self.assertNotIn('base64',json.dumps(self.payload))
        types={n['class_type'] for n in self.payload['graph'].values()}
        self.assertTrue({'LoadImage','LoadVideo','LoadAudio','PrimitiveStringMultiline'}<=types)
        context=next(n['inputs']['value'] for n in self.payload['graph'].values() if n['class_type']=='PrimitiveStringMultiline')
        self.assertEqual(json.loads(context)['prompt'],self.ws['shots'][0]['prompt'])
        self.assertEqual(self.payload['project_context']['assembly']['audio_asset_id'],'audio')

    def test_transfer_preserves_bytes_idempotent_and_survives_snapshot_restore(self):
        self.stage();remote,root=self.transport();transfer=AssetTransfer(remote,self.cache,'isolated-cpu')
        result=transfer.transfer(self.token)
        self.assertTrue(result['hash_verified']);self.assertFalse(result['generation_started'])
        for a in self.payload['assets']:
            self.assertEqual(digest(root/'input'/result['files'][a['file']]),a['sha256'])
        self.assertEqual(remote.meta_cache,{})
        self.assertEqual(transfer.transfer(self.token),result)
        canvas={'nodes':[{'id':int(a['node_id']),'type':self.payload['graph'][a['node_id']]['class_type'],
                         'widgets_values':[result['files'][a['file']]],'pos':[10,20]} for a in self.payload['assets']], 'links':[]}
        archive=self.root/'snapshot.zip';pack(root,archive,canvas,'After full asset handoff')
        fresh=self.root/'fresh';restored=restore(fresh,archive)
        self.assertEqual(restored['canvas'],canvas)
        for a in self.payload['assets']:self.assertEqual(digest(fresh/'input'/a['file']),a['sha256'])

    def test_changed_staging_blocks_before_remote_calls(self):
        self.stage();a=self.payload['assets'][0];(self.record.with_suffix('')/a['file']).write_bytes(b'changed')
        from unittest.mock import Mock
        remote=Mock()
        with self.assertRaisesRegex(ValueError,'changed'):AssetTransfer(remote,self.cache,'cpu').transfer(self.token)
        remote.run.assert_not_called()

    def test_single_shot_excludes_unrelated_assets_and_required_refs_cannot_be_lost(self):
        p=prepare(self.ws,self.media,['shot'],include_assets=True,asset_ids=['video'])
        self.assertEqual({a['asset_id'] for a in p['assets']},{'image','video'})

    def test_external_asset_and_final_export_are_carried_without_private_paths(self):
        external=self.root/'outside.mp4';external.write_bytes(b'approved-external-video')
        self.assets[1]['path']=str(external)
        final=self.root/'final.mp4';final.write_bytes(b'final-cut');self.ws['project']['final_file']=str(final)
        self.stage();self.assertEqual(len(self.payload['assets']),4)
        self.assertNotIn(str(self.root),json.dumps(self.payload))
        for a in self.payload['assets']:self.assertEqual(digest(self.record.with_suffix('')/a['file']),a['sha256'])

    def test_large_video_is_streamed_not_embedded_in_handoff_json(self):
        with (self.media/'video.mp4').open('wb') as f:
            for _ in range(33):f.write(b'v'*1024**2)
        self.stage();self.assertLess(len(json.dumps(self.payload)),20000)
        remote,root=self.transport();r=AssetTransfer(remote,self.cache,'cpu').transfer(self.token)
        video=next(a for a in self.payload['assets'] if a['kind']=='video')
        self.assertEqual((root/'input'/video['file']).stat().st_size,33*1024**2)
        self.assertTrue(r['hash_verified'])

    def test_missing_asset_is_an_error_not_silent_omission(self):
        (self.media/'video.mp4').unlink()
        with self.assertRaisesRegex(ValueError,'unavailable'):prepare(self.ws,self.media,include_assets=True)

    def test_actual_generation_prompt_and_seed_survive_later_shot_edits(self):
        self.ws['jobs']=[{'id':'actual-job','shot':'shot','state':'succeeded','results':['video'],
                         'local_results':str(self.root/'private'),'config':{'prompt':'Original successful prompt','seed':123,'model':'h3'}}]
        p=prepare(self.ws,self.media,include_assets=True)
        context=next(json.loads(n['inputs']['value']) for n in p['graph'].values() if n['class_type']=='PrimitiveStringMultiline')
        self.assertEqual(context['generation_records'][0]['config']['prompt'],'Original successful prompt')
        self.assertEqual(context['generation_records'][0]['config']['seed'],123)
        self.assertEqual(context['prompt'],'Keep the original launch')
        self.assertNotIn(str(self.root),json.dumps(p))


if __name__=='__main__':unittest.main()
