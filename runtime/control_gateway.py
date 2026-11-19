"""Explicit-endpoint Colab SDK transport. Credentials remain inside the SDK."""
import argparse,json,sys
from pathlib import Path
from types import SimpleNamespace
from colab_cli.common import State
from colab_cli.runtime import ColabRuntime
from colab_cli.contents import ContentsClient
p=argparse.ArgumentParser();p.add_argument('--endpoint',required=True);args=p.parse_args();payload=json.load(sys.stdin)
s=State();vm=next((a for a in s.client.list_assignments() if a.endpoint==args.endpoint),None)
if vm is None:raise SystemExit('指定运行时已不在当前账号分配列表中')
if payload['action']=='release':
 s.client.unassign(args.endpoint)
 if any(a.endpoint==args.endpoint for a in s.client.list_assignments()):raise SystemExit('目标会话仍在分配列表中，释放尚未确认')
 print('JASPER_RESULT '+json.dumps({'released':True,'endpoint':args.endpoint}),flush=True);raise SystemExit(0)
r=ColabRuntime(vm.runtime_proxy_info.url,vm.runtime_proxy_info.token);text=[]
def hook(item):
 if item.get('output_type')=='stream':
  value=item.get('text','');text.append(value)
  for line in value.splitlines():
   if line.startswith('JASPER_EVENT '):print(line,flush=True)
 elif item.get('output_type')=='error':raise RuntimeError(item.get('ename','RemoteError')+': '+item.get('evalue',''))
try:
 code='CONTROL = '+repr(payload)+'\n'+(Path(__file__).parent.parent/'workflow_library.py').read_text()+'\n'+Path(__file__).with_name('managed_runtime.py').read_text()
 outputs=r.execute_code(code,timeout=28800,output_hook=hook)
 alltext=''.join(text)
 if not alltext:alltext=''.join(x.get('text','') for x in outputs if x.get('output_type')=='stream')
 lines=[x[14:] for x in alltext.splitlines() if x.startswith('JASPER_RESULT ')]
 if not lines:raise RuntimeError('远端没有返回完成记录；保留会话，禁止自动重提')
 result=json.loads(lines[-1]);local=[]
 if payload['action'] in ('generate','resume'):
  dest=Path(payload['local_results']);dest.mkdir(parents=True,exist_ok=True)
  contents=ContentsClient(SimpleNamespace(url=vm.runtime_proxy_info.url,token=vm.runtime_proxy_info.token))
  for name in result.get('outputs',[]):
   src=Path(name)
   if not src.is_relative_to('/content/ComfyUI/output') or src.suffix.lower() not in ('.mp4','.webm','.png','.jpg','.jpeg','.wav','.mp3','.flac','.ogg','.m4a'):raise ValueError('结果路径不在允许的输出目录')
   target=dest/(str(len(local))+'_'+src.name);part=target.with_suffix(target.suffix+'.partial')
   contents.download(str(src),str(part));part.replace(target);local.append(str(target))
  result['local_files']=local
 print('JASPER_RESULT '+json.dumps(result,ensure_ascii=False),flush=True)
finally:r.stop()
