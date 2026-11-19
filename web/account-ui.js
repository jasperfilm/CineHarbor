// Authorization codes stay in this local form; no logging or persistent storage.
let loginState={state:'idle'},loginRequest=false;

function loginPanel(){
 const state=loginState.state,waiting=state==='waiting',working=state==='verifying';
 return `<section class="section-card account-panel"><div class="summary"><h2>Google 账号</h2><small>使用官方 Colab 授权 · 不需要 Google 密码</small></div>${loginState.message?`<p role="status">${esc(loginState.message)}</p>`:''}${waiting?`<ol><li><a class="inline-link" href="/account/authorize" target="_blank" rel="noopener">打开 Google 官方授权页面 ↗</a></li><li>完成授权后，把 Google 显示的一次性授权码粘贴到下面。</li></ol><label class="field"><span>一次性授权码（仅在本机核验）</span><input id="login-code" type="password" autocomplete="off" spellcheck="false"></label><button id="login-submit" class="primary">验证并登录</button> <button id="login-cancel">取消</button>`:working?'<div class="activity"><span></span></div><p>正在核验，请稍候。不会申请GPU。</p>':`<button id="login-begin">${live?.email?'Google 登录 / 切换账号':'Google 登录'}</button>`}<p class="note">登录凭证保存在官方 CLI 的本机凭证目录，不会进入项目备份。更换账号前需先结束当前GPU会话。</p></section>`;
}

UI.managerTopPanels.push(loginPanel);
UI.liveGuards.push(()=>!['waiting','verifying'].includes(loginState.state));
UI.hintProviders.push(()=>['waiting','verifying'].includes(loginState.state)?'Google登录进行中，云端操作已锁定。':'');

async function loginSync(){
 if(loginRequest)return;
 loginRequest=true;
 try{
  const before=JSON.stringify(loginState);
  loginState=await api('/api/account/login');
  if(JSON.stringify(loginState)!==before){
   if(manager)renderLive();
   if(loginState.state==='succeeded')await refresh();
  }
 }finally{loginRequest=false}
}

UI.binders.push(()=>{
 if($('#login-begin'))$('#login-begin').onclick=()=>action(async()=>{
  if(live?.active>0||busyOperation())throw Error('请先结束任务、保存并释放GPU，再切换登录。');
  if(live?.email&&!confirm('开始Google重新授权？成功后会更新官方CLI的本机登录凭证。当前项目数据保持原样。'))return;
  loginState=await api('/api/account/login/begin',{});renderLive();
 });
 if($('#login-submit'))$('#login-submit').onclick=()=>action(async()=>{
  const code=$('#login-code').value;$('#login-code').value='';
  loginState=await api('/api/account/login/submit',{code});renderLive();
 });
 if($('#login-cancel'))$('#login-cancel').onclick=()=>action(async()=>{
  loginState=await api('/api/account/login/cancel',{});renderLive();await refresh();
 });
});

setInterval(()=>{if(manager&&!document.hidden&&['waiting','verifying'].includes(loginState.state))loginSync().catch(()=>{})},2000);
loginSync().catch(()=>{});
