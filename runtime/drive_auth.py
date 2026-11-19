"""Bounded official Drive authorization with a loopback-only browser handoff.
OAuth URL and tokens stay in memory; logs contain state labels only.
"""
import json,threading,time,sys,argparse
from http.server import BaseHTTPRequestHandler,HTTPServer
from colab_cli.common import State
from colab_cli.runtime import ColabRuntime
from colab_cli.auth import get_credentials
parser=argparse.ArgumentParser();parser.add_argument('--endpoint',required=True);args=parser.parse_args()
s=State();target=args.endpoint;vm=next(a for a in s.client.list_assignments() if a.endpoint==target)
r=ColabRuntime(vm.runtime_proxy_info.url,vm.runtime_proxy_info.token)
ready=threading.Event();proceed=threading.Event();shared={}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  if self.headers.get('Host')!='127.0.0.1:8768':self.send_error(403);return
  if self.path=='/auth' and shared.get('uri'):
   self.send_response(302);self.send_header('Location',shared['uri']);self.end_headers()
  elif self.path=='/status':self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'ready':ready.is_set(),'done':shared.get('done',False)}).encode())
  else:self.send_error(404)
 def do_POST(self):
  if self.headers.get('Host')!='127.0.0.1:8768' or self.headers.get('X-GC-Local')!='1':self.send_error(403);return
  if self.path!='/continue':self.send_error(404);return
  proceed.set();self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'OK')
http=HTTPServer(('127.0.0.1',8768),Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
def hook(msg,ws):
 if msg.get('content',{}).get('request',{}).get('authType')!='dfs_ephemeral':return False
 msgid=msg.get('metadata',{}).get('colab_msg_id');url=s.client.colab_domain+'/tun/m/credentials-propagation/'+target
 params={'authuser':'0','authtype':'dfs_ephemeral','version':'2','dryrun':'true','propagate':'true','record':'false'}
 creds=get_credentials(s.client_oauth_config,provider=s.auth_provider)
 a=creds.request('GET',url,params=params);data=json.loads(a.text.split('\n',1)[-1]);headers={'x-goog-colab-token':data.get('token')}
 a=creds.request('POST',url,params=params,headers=headers,files={'file_id':(None,'empty.ipynb')});data=json.loads(a.text.split('\n',1)[-1])
 if not data.get('success'):
  shared['uri']=data.get('unauthorized_redirect_uri')
  if not shared['uri'] or not shared['uri'].startswith('https://accounts.google.com/'):raise RuntimeError('No safe Google authorization URL')
  ready.set();print('JASPER_EVENT '+json.dumps({'stage':'authorization_required','message':'请在Google页面完成本次云盘授权，然后点击继续挂载。','auth_url':'http://127.0.0.1:8768/auth'}),flush=True)
  if not proceed.wait(360):raise RuntimeError('Drive authorization handoff timed out')
 params['dryrun']='false';a=creds.request('POST',url,params=params,headers=headers,files={'file_id':(None,'empty.ipynb')})
 if a.status_code!=200:raise RuntimeError('Credential propagation status '+str(a.status_code))
 reply=ws.session.msg('input_reply',{'value':{'type':'colab_reply','colab_msg_id':msgid}})
 if 'header' in msg:reply['parent_header']=msg['header']
 ws.stdin_channel.send(reply);print('JASPER_EVENT '+json.dumps({'stage':'mounting','message':'授权已传播，正在挂载云盘'}),flush=True);return True
r.colab_request_hook=hook
try:
 output=r.execute_code("from google.colab import drive\ndrive.mount('/content/drive', timeout_ms=480000)\nimport os\nprint('DRIVE_MOUNTED',os.path.isdir('/content/drive/MyDrive'))",allow_stdin=True,timeout=480)
 for item in output:
  if item.get('output_type')=='error':raise RuntimeError(item.get('ename','RemoteError')+': '+item.get('evalue',''))
  if 'DRIVE_MOUNTED' in item.get('text',''):print('JASPER_RESULT '+json.dumps({'drive_mounted':'True' in item['text']}),flush=True)
 shared['done']=True
finally:r.stop();http.shutdown()
