"""Local process ownership for an explicitly selected, already allocated VM."""
from pathlib import Path
import json, os, subprocess, time, urllib.request, socket

def status(server):
 p=server.DATA/'bridge.json'
 if not p.exists():return {'ready':False}
 try:
  record=json.loads(p.read_text());lease=json.loads((server.DATA/'lease.json').read_text())
  if record['endpoint']!=lease.get('endpoint'):return {'ready':False}
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  with opener.open('http://127.0.0.1:8767/__gc_health',timeout=1) as f:health=json.load(f)
  return {'ready':health.get('endpoint')==record['endpoint'],'endpoint':record['endpoint'],'url':'http://127.0.0.1:8767/'}
 except Exception:return {'ready':False}

def start(server,endpoint):
 current=status(server)
 if current.get('ready') and current['endpoint']==endpoint:return current
 with socket.socket() as s:
  if s.connect_ex(('127.0.0.1',8767))==0:raise RuntimeError('本机8767端口已占用。保留现有进程，请先检查已有画布。')
 frontend=server.ROOT/'vendor/comfy_frontend.zip'
 if not frontend.exists():raise RuntimeError('安装包缺少官方ComfyUI前端。')
 log=open(server.DATA/'bridge.log','ab')
 env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';cache=str(server.DATA/'cache');env['CINEHARBOR_CACHE']=cache;env['GC_LABS_CACHE']=cache
 process=subprocess.Popen([server.sdk_python(),str(server.ROOT/'comfy_local_bridge.py'),'--endpoint',endpoint,'--frontend',str(frontend)],stdout=log,stderr=log,env=env);log.close()
 record={'pid':process.pid,'endpoint':endpoint};(server.DATA/'bridge.json').write_text(json.dumps(record))
 for _ in range(90):
  if process.poll() is not None:raise RuntimeError('当前 ComfyUI 后端未就绪或连接失败。请先在 Colab 管理启动 ComfyUI 环境后重试；GPU 未关闭。技术记录见 bridge.log。')
  ready=status(server)
  if ready.get('ready'):return ready
  time.sleep(1)
 # Only the process just created is stopped. The Colab VM is untouched.
 process.terminate();raise RuntimeError('画布连接超时，已停止本次本机桥接进程；GPU仍保留。')

def stop(server):
 """Stop only the recorded local bridge; never releases a cloud VM."""
 import signal
 record=server.DATA/'bridge.json'
 if not record.exists():return {'stopped':True,'already_absent':True}
 d=json.loads(record.read_text());pid=int(d['pid'])
 try:command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True).strip()
 except subprocess.CalledProcessError:record.unlink(missing_ok=True);return {'stopped':True,'already_absent':True}
 expected=str(server.ROOT/'comfy_local_bridge.py')
 if expected not in command or '--endpoint '+d['endpoint'] not in command:return {'stopped':False,'warning':'本机进程身份不匹配，未停止。'}
 os.kill(pid,signal.SIGTERM)
 for _ in range(30):
  try:os.kill(pid,0)
  except ProcessLookupError:record.unlink(missing_ok=True);return {'stopped':True,'pid':pid}
  time.sleep(.1)
 # Only our verified disposable bridge process is terminated, with no project data.
 try:os.kill(pid,signal.SIGKILL)
 except ProcessLookupError:pass
 record.unlink(missing_ok=True);return {'stopped':True,'pid':pid,'forced_local_process':True}
