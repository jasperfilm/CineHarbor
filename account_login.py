"""User-driven official Colab OAuth. Codes and authorization URLs stay in memory.

The app never handles a Google password. Its UI redirects to Google's registered
landing page, and the user pastes the one-time code into the local password field.
"""
import json,os,secrets,threading,time,tempfile
from pathlib import Path
from urllib.parse import urlparse

class AccountLogin:
 def __init__(self):
  self.lock=threading.RLock();self.flow=None;self.url=None;self.deadline=0;self.state='idle';self.email=None;self.message=''
 def status(self):
  with self.lock:
   if self.state=='waiting' and time.time()>self.deadline:
    self.flow=None;self.url=None;self.state='expired';self.message='授权已超时，请重新开始。'
   return {'state':self.state,'email':self.email,'message':self.message,'expires_at':self.deadline if self.state=='waiting' else None}
 def make_flow(self):
  from importlib import resources
  from google_auth_oauthlib.flow import InstalledAppFlow
  from colab_cli.auth import PUBLIC_SCOPES,REMOTE_REDIRECT_URI
  custom=Path.home()/'.colab-cli-oauth-config.json'
  config=json.loads(custom.read_text() if custom.exists() else resources.files('colab_cli').joinpath('oauth_config.json').read_text())
  flow=InstalledAppFlow.from_client_config(config,PUBLIC_SCOPES);flow.redirect_uri=REMOTE_REDIRECT_URI
  return flow
 def begin(self):
  with self.lock:
   if self.state=='verifying':raise ValueError('正在核验授权，请稍候。')
   self.flow=self.make_flow();self.url,_=self.flow.authorization_url(prompt='consent',token_usage='remote')
   parsed=urlparse(self.url)
   if parsed.scheme!='https' or parsed.hostname!='accounts.google.com':self.flow=None;self.url=None;raise ValueError('官方授权地址异常，未打开。')
   self.state='waiting';self.deadline=time.time()+600;self.email=None;self.message='请在Google完成授权，把一次性授权码粘贴到此处。'
   return self.status()
 def redirect(self):
  with self.lock:
   if self.status()['state']!='waiting' or not self.url:raise ValueError('请先开始登录。')
   return self.url
 def cancel(self):
  with self.lock:
   if self.state=='verifying':raise ValueError('正在核验授权，不能取消；请等待结果。')
   self.flow=None;self.url=None;self.state='idle';self.email=None;self.message='已取消，本机已有账号保持原样。'
   return self.status()
 def submit(self,code):
  with self.lock:
   if self.status()['state']!='waiting':raise ValueError('授权未开始或已超时。')
   if not isinstance(code,str) or not 8<=len(code.strip())<=4096:raise ValueError('请粘贴完整的一次性授权码。')
   self.state='verifying';self.message='正在向Google核验授权…';flow=self.flow
   threading.Thread(target=self.finish,args=(flow,code.strip()),daemon=True).start()
   return self.status()
 def verified_email(self,credentials):
  from google.auth.transport.requests import AuthorizedSession
  with AuthorizedSession(credentials) as session:
   response=session.get('https://www.googleapis.com/oauth2/v2/userinfo',timeout=20);response.raise_for_status();data=response.json()
  if not data.get('verified_email') or '@' not in data.get('email',''):raise ValueError('Google没有返回已验证账号。')
  return data['email']
 def persist(self,credentials):
  from colab_cli.auth import TOKEN_CONFIG_PATH
  target=Path(TOKEN_CONFIG_PATH);target.parent.mkdir(parents=True,exist_ok=True)
  fd,name=tempfile.mkstemp(prefix='.gclabs-token-',dir=target.parent)
  try:
   os.fchmod(fd,0o600)
   with os.fdopen(fd,'w') as stream:stream.write(credentials.to_json());stream.flush();os.fsync(stream.fileno())
   os.replace(name,target)
  finally:
   if Path(name).exists():Path(name).unlink()
 def finish(self,flow,code):
  try:
   flow.fetch_token(code=code,timeout=20);code=None
   email=self.verified_email(flow.credentials)
   self.persist(flow.credentials)
   with self.lock:self.state='succeeded';self.email=email;self.message='登录成功，请核对账号并确认绑定。'
  except Exception:
   # OAuth errors can contain the submitted code or token. Never log/return them.
   with self.lock:self.state='failed';self.message='授权核验失败或已过期。已有凭证未替换，请重新开始登录。'
  finally:
   with self.lock:self.flow=None;self.url=None
