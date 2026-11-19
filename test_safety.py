import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import server

class RuntimeSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'runtime').mkdir();self.data=self.root/'data';self.data.mkdir()
        self.patches=[patch.object(server,'ROOT',self.root),patch.object(server,'DATA',self.data)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def test_wrong_account_cannot_allocate(self):
        (self.data/'profile.json').write_text(json.dumps({'expected_account':'owner@example.com'}))
        with patch.object(server,'identity',return_value='other@example.com'),patch.object(server,'cli') as call:
            with self.assertRaisesRegex(ValueError,'账号不匹配'):server.operation('start',{'gpu':'G4'})
            call.assert_not_called()
    def test_cannot_stop_unowned_session(self):
        with patch.object(server,'guarded'),patch.object(server,'cli') as call:
            with self.assertRaisesRegex(ValueError,'工作站创建'):server.operation('stop',{'backup_confirmed':True})
            call.assert_not_called()
    def test_duplicate_or_uncertain_allocation_is_blocked(self):
        (self.data/'lease.json').write_text(json.dumps({'state':'uncertain'}))
        with patch.object(server,'guarded'),patch.object(server,'cli') as call:
            with self.assertRaisesRegex(ValueError,'已有开机记录'):server.operation('start',{'gpu':'G4'})
            call.assert_not_called()
    def test_failed_release_guard_stops_new_vm(self):
        calls=[]
        def run(args,timeout=25):
            calls.append(args)
            if args[0]=='exec':raise RuntimeError('guard failed')
            return 'ok'
        with patch.object(server,'guarded'),patch.object(server,'refresh',side_effect=[{'active':0},{'sessions':[{'name':server.SESSION,'endpoint':'owned-endpoint'}]}]),patch.object(server,'cli',side_effect=run):
            with self.assertRaisesRegex(ValueError,'已停止此次运行时'):server.operation('start',{'gpu':'G4','max_minutes':5})
        self.assertEqual(calls[-1],['stop','-s',server.SESSION])
        self.assertFalse((self.data/'lease.json').exists())
    def test_manual_session_disables_start_and_stop(self):
        state=server.runtime_state({'sessions':[{'name':'?','endpoint':'manual-g4','hardware':'G4'}],'active':1,'account_ok':True})
        self.assertEqual(state['runtime_state'],'external')
        self.assertFalse(state['can_start']);self.assertFalse(state['can_stop'])
    def test_mismatched_usage_is_unknown(self):
        state=server.runtime_state({'sessions':[],'active':1,'account_ok':True})
        self.assertEqual(state['runtime_state'],'unknown');self.assertFalse(state['can_start'])
    def test_owned_endpoint_required_even_if_name_matches(self):
        (self.data/'lease.json').write_text(json.dumps({'session':server.SESSION,'endpoint':'old-vm','state':'active'}))
        state=server.runtime_state({'sessions':[{'name':server.SESSION,'endpoint':'replacement-vm'}],'active':1,'account_ok':True})
        self.assertFalse(state['can_stop']);self.assertFalse(state['can_start'])
    def test_owned_session_can_stop_with_other_manual_session(self):
        (self.data/'lease.json').write_text(json.dumps({'session':server.SESSION,'endpoint':'owned-vm','state':'active'}))
        state=server.runtime_state({'sessions':[{'name':server.SESSION,'endpoint':'owned-vm'},{'name':'?','endpoint':'manual-vm'}],'active':2,'account_ok':True})
        self.assertTrue(state['can_stop']);self.assertFalse(state['can_start'])
    def test_session_output_parsing_ignores_notices(self):
        rows=server.parse_sessions('[colab] update notice\n[?] gpu-g4-abc | Hardware: G4 | Shape: HIGHMEM | Variant: GPU\n')
        self.assertEqual(rows,[{'name':'?','endpoint':'gpu-g4-abc','hardware':'G4'}])
    def test_external_session_is_blocked_before_allocation(self):
        with patch.object(server,'guarded'),patch.object(server,'refresh',return_value={'active':1,'runtime_state':'external'}),patch.object(server,'cli') as call:
            with self.assertRaisesRegex(ValueError,'禁止重复开机'):server.operation('start',{'gpu':'G4'})
            call.assert_not_called()
    def test_stop_requires_saved_result_confirmation(self):
        with patch.object(server,'guarded'),patch.object(server,'cli') as call:
            with self.assertRaisesRegex(ValueError,'结果已保存'):server.operation('stop',{})
            call.assert_not_called()

if __name__=='__main__':unittest.main()
