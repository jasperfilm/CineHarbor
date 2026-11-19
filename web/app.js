/* Core UI state, transport adapter (GCLabsCore), and slot registry (zero string monkey-patching). */
let data,live,verified,selected,tab='shots',modelKind='all',statusRequest=null,runtimeBusy=false,liveReceivedAt=0;
const manager=location.pathname==='/manager';
const $=s=>document.querySelector(s);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// Shell-agnostic Core API client: future Web/Desktop shells only configure baseUrl/keyProvider.
const GCLabsCore=(window.GCLabsCore=window.GCLabsCore||{
 baseUrl:'',
 keyProvider:()=>window.LOCAL_KEY,
 async request(path,body){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),path==='/api/status'?85000:path?.startsWith('/api/assembly/')?190000:25000);
  try{
   const r=await fetch(this.baseUrl+path,{...(body?{method:'POST',headers:{'Content-Type':'application/json','X-Local-Key':this.keyProvider()},body:JSON.stringify(body)}:{}),signal:controller.signal});
   const d=await r.json();if(!r.ok||d?.error)throw Error(d?.error||'请求失败');return d;
  }catch(e){if(e.name==='AbortError')throw Error('请求超时，请核对连接。已提交任务不会自动重试。');throw e}finally{clearTimeout(timer)}
 }
});

async function api(path,body){return GCLabsCore.request(path,body)}

// Declarative extension slots for modular feature panels without brittle HTML .replace() patches.
const UI=(window.GCLabsUI={
 tabs:[
  {id:'shots',icon:'▦',label:'分镜工作台',title:'分镜工作台',subtitle:'先锁定镜头参数，再生成样片或帧接力。',count:d=>null},
  {id:'assets',icon:'▧',label:'素材库',title:'项目素材',subtitle:'图像、视频与音频资产独立保存在本机项目中。',count:d=>(d?.assets||[]).length},
  {id:'models',icon:'◈',label:'模型中心',title:'模型中心',subtitle:'按能力、许可与实测选择，不以模型名称代替效果。',count:d=>null},
  {id:'jobs',icon:'◷',label:'生成任务',title:'生成任务',subtitle:'独立参数快照，支持单次 G4 顺序排队生成。',count:d=>(d?.jobs||[]).length}
 ],
 registerTab(spec,beforeId){
  const idx=this.tabs.findIndex(t=>t.id===spec.id);
  if(idx>=0){this.tabs[idx]={...this.tabs[idx],...spec};return}
  const pos=beforeId?this.tabs.findIndex(t=>t.id===beforeId):-1;
  if(pos>=0)this.tabs.splice(pos,0,spec);else this.tabs.push(spec);
 },
 views:{},
 viewDecorators:{},
 inspectors:{},
 shotModelOptions:[],
 shotExtraFields:[],
 shotFooterActions:[],
 studioProjectControls:null,
 managerTopPanels:[],
 managerRenderer:null,
 liveGuards:[],
 hintProviders:[],
 leaveGuards:[],
 binders:[],
 refreshHooks:[],
 workspaceHooks:[]
});

function liveUsable(){
 const base=!!live&&!live.error&&liveReceivedAt>0&&Date.now()-liveReceivedAt<30000;
 return base&&UI.liveGuards.every(fn=>fn());
}
function liveHint(){
 for(const fn of UI.hintProviders){const msg=fn();if(msg)return msg}
 return live?.error||(!liveReceivedAt?'正在核对官方 CLI…':'状态已超过30秒未更新，操作已锁定；正在重新核对。');
}

function toast(text){const el=$('#toast');if(!el)return;el.textContent=text;el.style.display='block';setTimeout(()=>el.style.display='none',5000)}
function asset(id){return (data?.assets||[]).find(a=>a.id===id)}
function media(a,controls=false){if(!a)return '<div class="empty">待添加参考素材</div>';let src='/assets/'+encodeURIComponent(a.file);return a.kind==='image'?`<img src="${src}" alt="${esc(a.name)}">`:a.kind==='video'?`<video src="${src}" ${controls?'controls':'muted preload="metadata"'}></video>`:`<audio controls src="${src}"></audio>`}

function header(){
 return `<header><a class="brand" href="/studio"><img src="/logo.png" alt="" aria-hidden="true"> GC LABS</a><nav><a href="/studio" class="${!manager?'active':''}">视频制作</a><a href="/manager" class="${manager?'active':''}">Colab 管理</a><button id="comfy-canvas">ComfyUI 画布 ↗</button></nav><span class="right badge">本机工作站 · 0.5.0</span></header>`;
}

function render(){
 document.title=manager?'Colab 管理 · GC Labs':'视频制作 · GC Labs';
 $('#app').innerHTML=header()+(manager?managerView():studioView());
 bind();
 if(manager&&typeof bindHardwareCompare==='function')bindHardwareCompare();
}

function studioView(){
 const readonly=data.project.status==='completed';
 const activeTab=UI.tabs.find(t=>t.id===tab)||UI.tabs[0];
 const projectControls=UI.studioProjectControls?UI.studioProjectControls():'';
 const shotsCount=(data.shots||[]).length;
 return `<div class="subbar"><h1>${esc(data.project.name)}</h1>${projectControls}<span class="muted">${esc(data.project.ratio||'9:16')} · ${readonly?'已结项只读':'本地优先工作台'}</span>${readonly?'':'<button class="right" id="import">＋ 导入素材</button>'}<input type="file" id="file" hidden accept="image/*,video/mp4,video/webm,audio/mpeg,audio/wav,audio/flac,audio/mp4"></div><div class="studio"><aside><h2>创作空间</h2><div class="project">${esc(data.project.name)}<br><small>${shotsCount} 个镜头 · ${readonly?'已结项':'制作中'}</small></div>${UI.tabs.map(t=>{const cnt=t.count?t.count(data):null;return `<a class="side-link ${tab===t.id?'active':''}" href="#" data-tab="${esc(t.id)}">${t.icon} ${esc(t.label)}${cnt!==null?` <small>${cnt}</small>`:''}</a>`}).join('')}<hr style="border:0;border-top:1px solid #303139;margin:24px 0"><p>图像、视频与音频工作流<br>素材 → 分镜 → 排队生成 → 粗剪交付</p><p>模型安装状态与推理实测分开记录。</p></aside><main class="main"><div class="summary"><div><h2>${esc(activeTab.title)}</h2><small>${esc(activeTab.subtitle)}</small></div><span class="line"></span>${tab==='shots'&&!readonly?'<button id="newshot">＋ 新镜头</button>':''}</div>${content()}</main><section class="inspector">${inspector()}</section></div>`;
}

function defaultShotsView(){
 return `<div class="shots">${(data.shots||[]).map((s,i)=>`<article class="shot ${s.id===selected?'selected':''}" data-shot="${s.id}"><div class="preview">${media(asset(s.output||s.reference))}<span class="number">SHOT ${String(i+1).padStart(2,'0')}</span></div><div class="info"><h3>${esc(s.title)}</h3><div class="meta"><span>${Number(Number(s.duration).toFixed(2))}s · ${s.resolution}</span><span class="state-dot ${s.output?'':'draft'}">${s.accepted?'● 用户已验收':s.output?'● 已有样片':'○ 待生成'}</span></div></div></article>`).join('')}</div>`;
}

function content(){
 let html='';
 if(UI.views[tab])html=UI.views[tab](defaultShotsView);
 else if(tab==='shots')html=defaultShotsView();
 else if(tab==='assets')html=`<div class="assets-grid">${(data.assets||[]).map(a=>`<article class="asset">${media(a,true)}<div class="caption">${esc(a.name)}<br><small>${esc(a.kind)}</small></div></article>`).join('')||'<div class="empty">尚无素材，点击右上角导入图像、视频或音频。</div>'}</div>`;
 else if(tab==='models')html=`<div class="chips">${[['all','全部'],['image','图像'],['video','视频'],['audio','音频']].map(([k,n])=>`<button data-kind="${k}" class="${modelKind===k?'active':''}">${n}</button>`).join('')}</div><div class="models-grid">${(data.models||[]).filter(m=>modelKind==='all'||m.kind===modelKind).map(m=>`<article class="model"><span class="type">${({image:'IMAGE',video:'VIDEO',audio:'AUDIO'})[m.kind]} / ${esc(m.provider)}</span><h3>${esc(m.name)}</h3><span class="badge ${m.state==='candidate'?'warn':''}">${m.state==='verified'?'历史推理已实测':m.state==='backed_up'?'权重已备份 · 待推理实测':'候选 · 未安装'}</span><p>${esc(m.description)}</p><div class="spec">${esc(m.size)}　/　${esc(m.gpu)}</div>${m.source?`<a href="${esc(m.source)}" target="_blank" rel="noreferrer">官方来源 ↗</a>`:''}</article>`).join('')}</div>`;
 else html=(data.jobs||[]).length?data.jobs.map(j=>`<div class="section-card job"><div><h3>${esc(j.title)}</h3><small>${esc(j.created)}</small><p>${esc(j.message)}</p></div><span class="badge warn right">任务已准备</span><button data-export="${j.id}">导出笔记本</button></div>`).join(''):'<div class="section-card empty">还没有生成任务。选中分镜、保存参数，再创建任务。</div>';
 if(UI.viewDecorators[tab])html=UI.viewDecorators[tab](html);
 return html;
}

function defaultShotInspector(){
 if(data.project.status==='completed'){
  const s=(data.shots||[]).find(x=>x.id===selected);
  return `<h2>已验收镜头</h2><p>${esc(s?.title||'未选择镜头')}</p>${s?.output?`<div class="result-preview">${media(asset(s.output),true)}</div>`:''}<p class="note">项目已结项。新制作请创建新项目，已通过的资产保持原样。</p>`;
 }
 const s=(data.shots||[]).find(s=>s.id===selected);
 if(!s)return '<h2>镜头设置</h2><p class="muted">选择一个镜头开始编辑。</p>';
 const extraModels=UI.shotModelOptions.map(fn=>fn(s)).join('');
 const extraFields=UI.shotExtraFields.map(fn=>fn(s)).join('');
 const footerActions=UI.shotFooterActions.map(fn=>fn(s)).join('');
 const chosenWf=(data.workflows||[]).find(w=>w.id===s.workflow);
 const maxDur=s.model==='workflow'&&chosenWf?.kind==='audio'?600:15;
 return `<h2>镜头设置 <small> / ${String(data.shots.indexOf(s)+1).padStart(2,'0')}</small></h2><label class="field"><span>镜头名称</span><input id="title" value="${esc(s.title)}"></label><label class="field"><span>提示词</span><textarea id="prompt">${esc(s.prompt)}</textarea></label><label class="field"><span>参考图</span><select id="reference"><option value="">选择素材</option>${(data.assets||[]).filter(a=>a.kind==='image').map(a=>`<option value="${a.id}" ${a.id===s.reference?'selected':''}>${esc(a.name)}</option>`).join('')}</select></label><label class="field"><span>执行模型</span><select id="model">${(data.models||[]).filter(m=>m.kind==='video').map(m=>`<option value="${m.id}" ${m.id===s.model?'selected':''}>${esc(m.name)}${m.state==='candidate'?' · 未安装':''}</option>`).join('')}${extraModels}</select></label>${extraFields}<div class="row"><label class="field"><span>时长 / 秒</span><input id="duration" type="number" min="1" max="${maxDur}" value="${s.duration}"></label><label class="field"><span>分辨率</span><select id="resolution">${['1080P','768P','720P','480P'].map(x=>`<option ${x===s.resolution?'selected':''}>${x}</option>`).join('')}</select></label></div><label class="field"><span>种子</span><input id="seed" type="number" value="${s.seed}"></label><button class="primary" id="save">保存镜头版本</button><button class="primary" id="prepare">创建生成任务</button><p class="note">创建任务不会自动开机。任务页支持单个或批量排队提交到已连接G4。</p>${s.output?`<div class="asset">${media(asset(s.output),true)}</div>`:''}${footerActions}<details><summary>版本记录 · ${(s.versions||[]).length}</summary>${(s.versions||[]).slice(0,6).map(v=>`<p><small>${esc(v.saved_at)}</small><br>${esc(v.title)}</p>`).join('')}</details>`;
}

function inspector(){
 if(UI.inspectors[tab])return UI.inspectors[tab](defaultShotInspector);
 return defaultShotInspector();
}

function managerView(){
 if(UI.managerRenderer)return UI.managerRenderer();
 let ok=live&&!live.error;
 const topPanels=UI.managerTopPanels.map(fn=>fn()).join('');
 return `<main class="manager"><div class="hero"><div><h1>算力随任务启动，完成后释放。</h1><p class="muted">GC Labs Colab 算力控制台 · G4 生命周期、模型与持久备份</p></div><button id="refresh">↻ 刷新实时状态</button></div><div class="hint">${ok?`当前授权：${esc(live.email)} · ${live.account_ok?'账号核验通过':'账号不符，禁止启动'} · ${esc(live.checked_at)} · 每15秒自动核对`:live?.error?esc(live.error):'正在读取 CLI 实时状态…'}</div>${topPanels}<section class="stats"><div class="stat"><small>可用算力</small><strong>${ok&&live.balance!==null?live.balance.toFixed(2):'—'}<em>CU</em></strong></div><div class="stat"><small>当前消耗速率</small><strong>${ok&&live.rate!==null?live.rate.toFixed(2):'—'}<em>CU / 小时</em></strong></div><div class="stat"><small>活动运行时</small><strong>${ok&&live.active!==null?live.active:'—'}<em>个</em></strong></div><div class="stat"><small>模型持久备份</small><strong>${verified?.backup_gib ?? '—'}<em>GiB · ${verified?.backup_files ?? 0} 文件</em></strong></div></section><div class="manager-grid"><div><section class="section-card"><h2>运行时控制</h2><span class="badge ${ok&&live.active===0?'':'warn'}">${!ok?'状态未确认':live.runtime_state==='owned'?'● 工作站会话已连接':live.runtime_state==='external'?'● 已有外部会话，禁止重复启动':live.runtime_state==='idle'?'○ 当前没有活动会话':'会话数据核对中，禁止启动'}</span><div class="flow"><span>账号核对</span><b>→</b><span>恢复缓存</span><b>→</b><span>运行任务</span><b>→</b><span>备份并释放</span></div><div class="row"><label class="field"><span>GPU</span><select id="gpu"><option>G4</option></select></label><label class="field"><span>制作时长提醒 / 分钟</span><input id="maxminutes" type="number" value="${data.policy.max_minutes}" min="5" max="1440"></label></div><button id="save-policy">保存提醒设置</button><p class="muted">启动会开始消耗账户算力。到时仅提醒，生成与备份不会被计时器中断。镜头验收并保存后，再释放 GPU。</p><div class="row"><button class="primary" id="start" ${!ok||!live.can_start||runtimeBusy||live.operation_busy?'disabled':''}>${runtimeBusy?'操作处理中…':ok&&live.active>0?'GPU 已分配':ok&&live.lease_state?'需核对开机记录':'启动 GPU'}</button><button class="danger" id="stop" ${!ok||!live.can_stop||runtimeBusy||live.operation_busy?'disabled':''}>保存后停止</button></div><p class="note">${ok&&live.runtime_state==='external'?'检测到网页或其他工具建立的会话；这里只显示状态，停止按钮不可用。':ok&&live.lease_state&&!live.can_stop?'存在未确认的开机记录，需先核查，不能重复分配。':'停止仅作用于本工作站创建且已核实标识的会话。'}</p>${ok&&live.sessions?.length?`<ul>${live.sessions.map(r=>`<li>${esc(r.hardware)} · ${esc(r.name)}<br><small>${esc(r.endpoint)}</small></li>`).join('')}</ul>`:''}<details><summary>实时会话明细</summary><pre>${esc(live?.sessions_text||'点击刷新读取')}</pre></details></section><section class="section-card"><h2>持久备份与恢复</h2><dl class="details"><dt>备份位置</dt><dd>${esc(verified?.backup_path||'尚未配置')}</dd><dt>状态</dt><dd>${esc(verified?.backup_status || "历史备份已验证；以实时任务状态为准")}</dd><dt>缓存策略</dt><dd>云盘备份 → 本地磁盘推理 → 结果归档</dd><dt>恢复入口</dt><dd><a href="/workstation.ipynb">下载官方工作站笔记本 ↗</a></dd></dl></section></div><div><section class="section-card"><h2>历史环境验证</h2><dl class="details"><dt>GPU</dt><dd>${esc(verified?.gpu||'尚未验证')}</dd><dt>显存 / 内存</dt><dd>96GB / ${esc(verified?.ram_gib||'—')}GiB</dd><dt>PyTorch / CUDA</dt><dd>${esc(verified?.torch||'—')} / ${esc(verified?.cuda||'—')}</dd><dt>ComfyUI</dt><dd>${esc((verified?.comfy_revision||'').slice(0,12))}</dd><dt>健康检查</dt><dd>服务与核心节点通过</dd><dt>视频推理</dt><dd>${esc(verified?.video_inference_status || "待视频验收")}</dd></dl></section><section class="section-card"><h2>操作记录</h2><div class="timeline">${(data.events||[]).slice(0,8).map(e=>`<p><small>${esc(e.time)}</small>${esc(e.text)}</p>`).join('')}<p><small>历史安装记录</small>CLI 与环境已验证。GPU 当前是否占用，以页面顶部实时状态为准。</p></div></section></div></div>${typeof hardwareCompareView==='function'?hardwareCompareView():''}<footer>官方 CLI 控制运行时。界面不读取或展示登录凭证；历史验证与实时状态分开显示。</footer></main>`;
}

async function saveShot(){
 let body={id:selected,workflow:$('#shot-workflow')?.value||null};
 for(let k of ['title','prompt','reference','model','resolution'])if($('#'+k))body[k]=$('#'+k).value;
 for(let k of ['duration','seed'])if($('#'+k))body[k]=Number($('#'+k).value);
 if(document.querySelectorAll){
  const boxes=[...document.querySelectorAll('[data-shot-elem]')];
  if(boxes.length||(data.elements||[]).length)body.elements=boxes.filter(c=>c.checked).map(c=>c.dataset.shotElem);
 }
 await api('/api/shot',body);
 data=await api('/api/workspace');
}

function bind(){
 document.querySelectorAll('[data-tab]').forEach(e=>e.onclick=ev=>{
  ev.preventDefault();
  const nextTab=e.dataset.tab;
  if(nextTab!==tab&&!UI.leaveGuards.every(fn=>fn(tab,nextTab)))return;
  tab=nextTab;
  render();
 });
 document.querySelectorAll('[data-shot]').forEach(e=>e.onclick=()=>{selected=e.dataset.shot;render()});
 document.querySelectorAll('[data-kind]').forEach(e=>e.onclick=()=>{modelKind=e.dataset.kind;render()});
 document.querySelectorAll('[data-export]').forEach(e=>e.onclick=()=>download(e.dataset.export));
 if($('#save'))$('#save').onclick=()=>action(async()=>{await saveShot();render();toast('已保存新版本')});
 if($('#prepare'))$('#prepare').onclick=()=>action(async()=>{await saveShot();await api('/api/job',{shot:selected});data=await api('/api/workspace');tab='jobs';render();toast('任务快照已保存；尚未消耗算力')});
 if($('#newshot'))$('#newshot').onclick=()=>action(async()=>{await api('/api/shot/new',{});data=await api('/api/workspace');selected=data.shots.at(-1).id;render()});
 if($('#import'))$('#import').onclick=()=>$('#file').click();
 if($('#file'))$('#file').onchange=()=>action(async()=>{
  let f=$('#file').files[0];if(!f)return;if(f.size>100e6)throw Error('素材请小于100MB');
  let value=await new Promise((resolve,reject)=>{let r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(f)});
  await api('/api/asset',{name:f.name,data:value});data=await api('/api/workspace');tab='assets';render();toast('素材已导入本机项目');
 });
 if($('#refresh'))$('#refresh').onclick=refresh;
 if($('#save-policy'))$('#save-policy').onclick=()=>action(async()=>{
  const minutes=Number($('#maxminutes').value);
  const cuBudget=$('#maxcubudget')?Number($('#maxcubudget').value):Number(data.policy.max_cu_budget||0);
  if(!Number.isInteger(minutes)||minutes<5||minutes>1440)throw Error('提醒时间须为5–1440的整数分钟');
  if(!Number.isFinite(cuBudget)||cuBudget<0||cuBudget>5000)throw Error('算力预算须为 0（不限）或 0.1–5000 CU');
  await api('/api/policy',{max_minutes:minutes,max_cu_budget:cuBudget,auto_release:data.policy.auto_release});data=await api('/api/workspace');renderLive();toast('提醒与算力预算护栏已保存；未改变当前运行时');
 });
 if($('#start'))$('#start').onclick=()=>runtimeAction('start');
 if($('#stop'))$('#stop').onclick=()=>runtimeAction('stop');
 for(const fn of UI.binders)fn();
}

async function runtimeAction(kind){
 if(runtimeBusy)return;
 const gpu=$('#gpu').value,minutes=Number($('#maxminutes').value);
 await refresh();
 if(live?.error||!(kind==='start'?live.can_start:live.can_stop))return toast('会话状态已变化，操作已取消，请查看实时状态。');
 if(!confirm(kind==='start'?`启动 ${gpu} 会消耗 Colab 算力，${minutes} 分钟后提醒，不自动中断任务。确定启动？`:'确认所有结果已保存？将停止本工作站创建的运行时，临时磁盘将释放。'))return;
 runtimeBusy=true;renderLive();
 try{await api('/api/runtime/'+kind,kind==='start'?{gpu,max_minutes:minutes}:{backup_confirmed:true});toast(kind==='start'?'已核查运行时分配':'已核查停止结果')}catch(e){toast(e.message)}finally{runtimeBusy=false;await refresh()}
}

async function action(fn){try{await fn()}catch(e){toast(e.message);if(manager)await refresh()}}

function renderLive(){
 if(!manager||!data||!verified)return;
 const values=document.querySelectorAll?[...document.querySelectorAll('input[id],select[id]')].filter(e=>e?.id).map(e=>[e.id,e.value]):[];
 const detailKey=e=>e.id||e.dataset?.disclosure||e.querySelector?.('summary')?.textContent||'';
 const open=new Map((document.querySelectorAll?[...document.querySelectorAll('details')]:[]).map(e=>[detailKey(e),e.open]));
 const focus=document.activeElement?.id,scroll=window.scrollY||0;
 render();
 for(const [id,value] of values){const e=document.getElementById?.(id);if(e)e.value=value}
 (document.querySelectorAll?[...document.querySelectorAll('details')]:[]).forEach(e=>{if(open.has(detailKey(e)))e.open=open.get(detailKey(e))});
 if(focus)document.getElementById?.(focus)?.focus?.({preventScroll:true});
 window.scrollTo?.(0,scroll);
}

async function refresh(){
 if(statusRequest)return statusRequest;
 statusRequest=(async()=>{
  try{live=await api('/api/status');liveReceivedAt=Date.now()}catch(e){liveReceivedAt=0;live={error:'实时状态读取失败，已禁用启停：'+e.message}}
  renderLive();
  for(const hook of UI.refreshHooks){try{await hook()}catch(e){toast('操作记录读取失败：'+e.message)}}
 })();
 try{await statusRequest}finally{statusRequest=null}
}

if(manager){
 setInterval(()=>{if(live&&!live.error&&liveReceivedAt&&!liveUsable())renderLive()},5000);
 setInterval(()=>{if(!document.hidden&&!runtimeBusy)refresh()},15000);
 window.addEventListener('focus',()=>{if(!runtimeBusy)refresh()});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!runtimeBusy)refresh()});
}

async function download(id){
 const job=(data.jobs||[]).find(j=>j.id===id);
 if(job?.config?.model==='workflow'){
  const url=URL.createObjectURL(new Blob([JSON.stringify(job.config.recipe,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=(job.title||'workflow')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;
 }
 let blob=new Blob([JSON.stringify(await api('/api/export/'+id),null,2)],{type:'application/x-ipynb+json'});
 let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='shot-'+id.slice(0,8)+'.ipynb';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}

(async()=>{try{[data,verified]=await Promise.all([api('/api/workspace'),api('/api/verified')]);selected=data.shots[0]?.id;render();if(manager)refresh()}catch(e){$('#app').textContent=e.message}})();
