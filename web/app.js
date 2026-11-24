var L=(typeof window!=="undefined"?window:globalThis).GCLabsI18n||{text:x=>x,html:(s,...v)=>s.reduce((a,p,i)=>a+p+(i<v.length?v[i]:""),""),service:x=>x,message:(_k,f)=>f,select:()=>"",bind:()=>{}};
/* Core UI state, transport adapter (GCLabsCore), and slot registry (zero string monkey-patching). */
let data,live,verified,selected,tab='shots',modelKind='all',statusRequest=null,runtimeBusy=false,liveReceivedAt=0,aboutOpen=false,projectFileBusy=false;
const PRODUCT=window.GCLabsBrand||{display_name:'GC Labs',version:'1.0.0',publisher:'GachaFrame'};
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
   const d=await r.json();if(!r.ok||d?.error)throw Error(d?.error||L.text('请求失败'));return d;
  }catch(e){if(e.name==='AbortError')throw Error(L.text('请求超时，请核对连接。已提交任务不会自动重试。'));throw e}finally{clearTimeout(timer)}
 }
});

async function api(path,body){return GCLabsCore.request(path,body)}

// Declarative extension slots for modular feature panels without brittle HTML .replace() patches.
const UI=(window.GCLabsUI={
 tabs:[
  {id:'shots',icon:'▦',label:L.text('分镜工作台'),title:L.text('分镜工作台'),subtitle:L.text('先锁定镜头参数，再生成样片或帧接力。'),count:d=>null},
  {id:'assets',icon:'▧',label:L.text('素材库'),title:L.text('项目素材'),subtitle:L.text('图像、视频与音频资产独立保存在本机项目中。'),count:d=>(d?.assets||[]).length},
  {id:'models',icon:'◈',label:L.text('模型中心'),title:L.text('模型中心'),subtitle:L.text('按能力、许可与实测选择，不以模型名称代替效果。'),count:d=>null},
  {id:'jobs',icon:'◷',label:L.text('生成任务'),title:L.text('生成任务'),subtitle:L.text('独立参数快照，支持单次 G4 顺序排队生成。'),count:d=>(d?.jobs||[]).length}
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
 if(live?.error?.includes('尚未登录或授权已失效'))return L.message('cloud.signinRequired','Sign in to Google from Colab Control.');
 return (live?.error?L.service(live.error):null)||(!liveReceivedAt?L.text('正在核对官方 CLI…'):L.text('状态已超过30秒未更新，操作已锁定；正在重新核对。'));
}

function toast(text){const el=$('#toast');if(!el)return;el.textContent=L.service(text);el.style.display='block';setTimeout(()=>el.style.display='none',5000)}
function asset(id){return (data?.assets||[]).find(a=>a.id===id)}
function media(a,controls=false,poster=null){if(!a)return L.text('<div class="empty">待添加参考素材</div>');let src='/assets/'+encodeURIComponent(a.file);return a.kind==='image'?`<img src="${src}" alt="${esc(a.name)}">`:a.kind==='video'?`<video src="${src}" ${poster?.kind==='image'?`poster="/assets/${encodeURIComponent(poster.file)}"`:''} ${controls?'controls':'muted preload="metadata"'}></video>`:`<audio controls src="${src}"></audio>`}

function header(){
 return L.html`<header><div class="brand-lockup"><a class="brand" href="/studio"><img src="/logo.png" alt="" aria-hidden="true"><span>${esc(PRODUCT.display_name)}<small>VIDEO CREATION WORKSTATION</small></span></a><span class="brand-divider" aria-hidden="true"></span><img class="gacha-cobrand" src="/gachaframe-logo.png" alt="GachaFrame"></div><nav aria-label="工作区"><a href="/studio" class="${!manager?'active':''}">视频制作</a><a href="/manager" class="${manager?'active':''}">Colab 管理</a><button id="comfy-canvas" ${typeof cloudCanvasOpening!=='undefined'&&cloudCanvasOpening?'disabled':''}>${typeof cloudCanvasOpening!=='undefined'&&cloudCanvasOpening?L.text('正在连接 ComfyUI…'):L.text('云端 ComfyUI ↗')}</button></nav><div class="right header-actions">${L.select()}<span class="local-status"><i aria-hidden="true"></i>本机工程</span><button class="ghost about-trigger" id="open-about" data-app-version="${esc(PRODUCT.version)}" aria-label="关于 ${esc(PRODUCT.display_name)}">关于</button></div></header>`;
}

function aboutModal(){
 if(!aboutOpen)return '';
 return L.html`<div class="about-backdrop" id="about-backdrop" role="dialog" aria-modal="true" aria-label="关于 ${esc(PRODUCT.display_name)}"><div class="about-sheet"><div class="about-top"><b>关于 ${esc(PRODUCT.display_name)}</b><button class="about-done" id="close-about">完成</button></div><img class="about-icon" src="/logo.png" alt="${esc(PRODUCT.display_name)}"><h3 class="about-title">${esc(PRODUCT.display_name)}</h3><small class="muted">版本 ${esc(PRODUCT.version)} · 免费应用</small><p class="about-sub">${esc(PRODUCT.tagline_en)}</p><div class="about-rule"></div><img class="about-gacha" src="/gachaframe-logo.png" alt="GachaFrame"><p class="about-maker">By GachaFrame · Video creation workspace</p><p class="about-legal">${L.message("about.legal",L.text("工程默认保存在本机；离线分镜、素材整理及本机剪辑导出无需申请云端 GPU。<br>执行云端任务时，选定的提示词、图片或音视频会发送到你授权的 Google Colab；主动备份的内容可保存到你的 Google Drive。<br>应用本身免费，不提供订阅、算力或生成模型服务。云端功能面向拥有适用 Google Colab 付费服务及正算力余额（CU）的用户；订阅不保证指定 GPU 可用。算力、存储及其他服务由提供方按你的账号另行计费。<br>Google Colab 为 Google LLC 商标。本应用为独立第三方客户端，与 Google 无隶属或背书关系。"))}</p><div class="about-links"><a href="/privacy.html" target="_blank" rel="noopener">隐私说明 ↗</a><a href="/terms.html" target="_blank" rel="noopener">使用与许可 ↗</a><a href="mailto:contact@gachaframe.com">联系支持 ↗</a></div></div></div>`;
}

function render(){
 document.title=(manager?L.text('Colab 管理'):L.text('视频制作'))+' · '+PRODUCT.display_name;
 $('#app').innerHTML=header()+(manager?managerView():studioView())+aboutModal();
 bind();L.bind();
 if(manager&&typeof bindHardwareCompare==='function')bindHardwareCompare();
}

function studioView(){
 const readonly=data.project.status==='completed';
 const activeTab=UI.tabs.find(t=>t.id===tab)||UI.tabs[0];
 const projectControls=UI.studioProjectControls?UI.studioProjectControls():'';
 const shotsCount=(data.shots||[]).length;
 return L.html`<div class="subbar"><h1>${esc(data.project.name)}</h1>${projectControls}<span class="muted">${esc(data.project.ratio||'9:16')} · ${readonly?L.text('已结项只读'):L.text('本地优先工作台')}</span>${readonly?'':L.text('<button class="right" id="import">＋ 导入素材</button>')}<input type="file" id="file" hidden accept="image/*,video/mp4,video/webm,audio/mpeg,audio/wav,audio/flac,audio/mp4"></div><div class="studio"><aside><h2>PRODUCTION</h2><div class="project">${esc(data.project.name)}<br><small>${shotsCount} 个镜头 · ${readonly?L.text('已结项'):L.text('制作中')}</small></div>${UI.tabs.map(t=>{const cnt=t.count?t.count(data):null;return `<a class="side-link ${tab===t.id?'active':''}" href="#" data-tab="${esc(t.id)}">${t.icon} ${esc(t.label)}${cnt!==null?` <small>${cnt}</small>`:''}</a>`}).join('')}<hr style="border:0;border-top:1px solid #303139;margin:24px 0"><div class="sidebar-foot"><span class="eyebrow">${esc(PRODUCT.tagline_en)}</span><p>本机编排 · 云端生成<br>工程与作品，在这里靠港。</p><a href="/manager">查看 Colab 与费用 ↗</a></div></aside><main class="main">${productionJourney()}<div class="summary"><div><h2>${esc(activeTab.title)}</h2><small>${esc(activeTab.subtitle)}</small></div><span class="line"></span>${tab==='shots'&&!readonly?L.text('<button id="newshot">＋ 新镜头</button>'):''}</div>${content()}</main><section class="inspector">${inspector()}</section></div>`;
}

function productionJourney(){
 const shots=data.shots||[],assets=data.assets||[],jobs=data.jobs||[];
 const videos=shots.filter(s=>s.output&&assets.some(a=>a.id===s.output&&a.kind==='video')).length;
 const steps=[['01',L.text('分镜'),'shots',shots.length+L.text(' 镜')],['02',L.text('素材'),'assets',assets.length+L.text(' 项')],['03',L.text('生成'),'jobs',jobs.filter(j=>j.state==='succeeded').length+' / '+jobs.length],['04',L.text('剪辑与交付'),'assembly',videos+L.text(' 段视频')]];
 return L.html`<nav class="production-journey" aria-label="视频制作流程">${steps.map(([n,title,id,count])=>`<button data-tab="${id}" class="journey-step ${tab===id?'current':''}" ${tab===id?'aria-current="step"':''}><span class="journey-number">${n}</span><span><b>${title}</b><small>${count}</small></span><span class="journey-arrow" aria-hidden="true">→</span></button>`).join('')}</nav>`;
}
function emptyProduction(){
 return L.html`<section class="production-empty"><div class="empty-wordmark"><img src="/logo.png" alt="" aria-hidden="true"><span class="eyebrow">CINEHARBOR / NEW PRODUCTION</span></div><h2>让第一个镜头靠港。</h2><p>在本机组织创意，连接你自己的 Google Colab 付费运行时制作镜头。<br>先在本机编排故事，准备好后再开始云端生成。</p><div class="empty-actions"><button class="primary" id="onboard-newshot">＋ 创建第一个镜头</button><button class="ghost" id="onboard-script">从剧本开始</button><button class="ghost" id="onboard-import">导入参考素材</button></div><div class="empty-guide"><div><span>01 / PLAN</span><h3>把故事放进镜头</h3><p>写下动作与运镜，关联角色和场景。</p></div><div><span>02 / CREATE</span><h3>交给自己的 Colab</h3><p>核对账号、模型和费用，再提交生成。</p></div><div><span>03 / BRING HOME</span><h3>挑好片，带回来</h3><p>接镜、剪辑与导出；备份核验后释放算力。</p></div></div><p class="empty-safety">此刻只在本机准备。创建镜头不会自动申请 GPU。</p></section>`;
}

function defaultShotsView(){
 return `<div class="shots">${(data.shots||[]).map((s,i)=>`<article class="shot ${s.id===selected?'selected':''}" data-shot="${s.id}"><div class="preview">${media(asset(s.output||s.reference),false,asset(s.reference))}<span class="number">SHOT ${String(i+1).padStart(2,'0')}</span></div><div class="info"><h3>${esc(s.title)}</h3><div class="meta"><span>${Number(Number(s.duration).toFixed(2))}s · ${s.resolution}</span><span class="state-dot ${s.output?'':'draft'}">${s.accepted?L.text('● 用户已验收'):s.output?L.text('● 已有样片'):L.text('○ 待生成')}</span></div></div></article>`).join('')}</div>`;
}

function content(){
 let html='';
 if(UI.views[tab])html=UI.views[tab](defaultShotsView);
 else if(tab==='shots')html=defaultShotsView();
 else if(tab==='assets')html=`<div class="assets-grid">${(data.assets||[]).map(a=>`<article class="asset">${media(a,true)}<div class="caption">${esc(a.name)}<br><small>${esc(a.kind)}</small></div></article>`).join('')||L.text('<div class="empty">尚无素材，点击右上角导入图像、视频或音频。</div>')}</div>`;
 else if(tab==='models')html=`<div class="chips">${[['all',L.text('全部')],['image',L.text('图像')],['video',L.text('视频')],['audio',L.text('音频')]].map(([k,n])=>`<button data-kind="${k}" class="${modelKind===k?'active':''}">${n}</button>`).join('')}</div><div class="models-grid">${(data.models||[]).filter(m=>modelKind==='all'||m.kind===modelKind).map(m=>`<article class="model"><span class="type">${({image:'IMAGE',video:'VIDEO',audio:'AUDIO'})[m.kind]} / ${esc(m.provider)}</span><h3>${esc(m.name)}</h3><span class="badge ${m.state==='candidate'?'warn':''}">${m.state==='verified'?L.text('历史推理已实测'):m.state==='backed_up'?L.text('权重已备份 · 待推理实测'):L.text('候选 · 按会话核验')}</span><p>${esc(L.service(m.description))}</p><div class="spec">${esc(L.service(m.size))}　/　${esc(m.gpu)}</div>${m.source?L.html`<a href="${esc(m.source)}" target="_blank" rel="noreferrer">官方来源 ↗</a>`:''}</article>`).join('')}</div>`;
 else html=(data.jobs||[]).length?data.jobs.map(j=>L.html`<div class="section-card job"><div><h3>${esc(j.title)}</h3><small>${esc(j.created)}</small><p>${esc(j.message)}</p></div><span class="badge warn right">任务已准备</span><button data-export="${j.id}">导出笔记本</button></div>`).join(''):L.text('<div class="section-card empty">还没有生成任务。选中分镜、保存参数，再创建任务。</div>');
 if(tab==='shots'&&!(data.shots||[]).length)html=emptyProduction();
 if(UI.viewDecorators[tab]&&(!(tab==='shots'&&!(data.shots||[]).length)||(typeof dramaPanelMode!=='undefined'&&dramaPanelMode)))html=UI.viewDecorators[tab](html);
 return html;
}

function defaultShotInspector(){
 if(data.project.status==='completed'){
  const s=(data.shots||[]).find(x=>x.id===selected);
  return L.html`<h2>已验收镜头</h2><p>${esc(s?.title||L.text('未选择镜头'))}</p>${s?.output?`<div class="result-preview">${media(asset(s.output),true)}</div>`:''}<p class="note">项目已结项。新制作请创建新项目，已通过的资产保持原样。</p>`;
 }
 const s=(data.shots||[]).find(s=>s.id===selected);
 if(!s)return L.text('<div class="inspector-intro"><span class="eyebrow">SHOT DETAILS</span><h2>每个镜头，都有自己的位置。</h2><p>选择或创建镜头后，在这里编辑提示词、参考画面与生成参数。</p><div class="inspector-tip"><b>先准备，再开机</b><p>编排分镜、整理素材和本机导出不需要申请 GPU。准备好任务后，再到 Colab 管理启动算力。</p></div><a href="/manager">连接自己的 Colab ↗</a></div>');
 const extraModels=UI.shotModelOptions.map(fn=>fn(s)).join('');
 const extraFields=UI.shotExtraFields.map(fn=>fn(s)).join('');
 const footerActions=UI.shotFooterActions.map(fn=>fn(s)).join('');
 const chosenWf=(data.workflows||[]).find(w=>w.id===s.workflow);
 const maxDur=s.model==='workflow'&&chosenWf?.kind==='audio'?600:15;
 return L.html`<h2>镜头设置 <small> / ${String(data.shots.indexOf(s)+1).padStart(2,'0')}</small></h2><label class="field"><span>镜头名称</span><input id="title" value="${esc(s.title)}"></label><label class="field"><span>提示词</span><textarea id="prompt">${esc(s.prompt)}</textarea></label><label class="field"><span>首帧参考图</span><select id="reference"><option value="">选择素材（或继承 @角色卡）</option>${(data.assets||[]).filter(a=>a.kind==='image').map(a=>`<option value="${a.id}" ${a.id===s.reference?'selected':''}>${esc(a.name)}</option>`).join('')}</select></label><label class="field"><span>尾帧锁死图（首尾双帧锚定 · 可选）</span><select id="end_reference"><option value="">不限定尾帧（单首帧驱动）</option>${(data.assets||[]).filter(a=>a.kind==='image').map(a=>`<option value="${a.id}" ${a.id===s.end_reference?'selected':''}>${esc(a.name)}</option>`).join('')}</select></label><label class="field"><span>执行模型</span><select id="model">${(data.models||[]).filter(m=>m.kind==='video').map(m=>`<option value="${m.id}" ${m.id===s.model?'selected':''}>${esc(m.name)}</option>`).join('')}${extraModels}</select></label>${extraFields}<div class="row"><label class="field"><span>时长 / 秒</span><input id="duration" type="number" min="1" max="${maxDur}" value="${s.duration}"></label><label class="field"><span>分辨率</span><select id="resolution">${['1080P','768P','720P','480P'].map(x=>`<option ${x===s.resolution?'selected':''}>${x}</option>`).join('')}</select></label></div><label class="field"><span>种子</span><input id="seed" type="number" value="${s.seed}"></label><button class="primary" id="save">保存镜头版本</button><button class="primary" id="prepare">创建生成任务</button><p class="note">创建任务不会自动开机。任务页支持单个或批量排队提交到已连接G4。</p>${s.output?`<div class="asset">${media(asset(s.output),true)}</div>`:''}${footerActions}<details><summary>版本记录 · ${(s.versions||[]).length}</summary>${(s.versions||[]).slice(0,6).map(v=>`<p><small>${esc(v.saved_at)}</small><br>${esc(v.title)}</p>`).join('')}</details>`;
}

function inspector(){
 if(UI.inspectors[tab])return UI.inspectors[tab](defaultShotInspector);
 return defaultShotInspector();
}

function managerView(){
 if(UI.managerRenderer)return UI.managerRenderer();
 let ok=live&&!live.error;
 const topPanels=UI.managerTopPanels.map(fn=>fn()).join('');
 return L.html`<main class="manager"><div class="hero"><div><h1>算力随任务启动，完成后释放。</h1><p class="muted">连接自己的 Colab 账号，管理算力、模型和备份</p></div><button id="refresh">↻ 刷新实时状态</button></div><div class="hint">${ok?L.html`当前授权：${esc(live.email)} · ${live.account_ok?L.text('账号核验通过'):L.text('账号不符，禁止启动')} · ${esc(live.checked_at)} · 每15秒自动核对`:live?.error?esc(live.error):L.text('正在读取 CLI 实时状态…')}</div>${topPanels}<section class="stats"><div class="stat"><small>可用算力</small><strong>${ok&&live.balance!==null?live.balance.toFixed(2):'—'}<em>CU</em></strong></div><div class="stat"><small>当前消耗速率</small><strong>${ok&&live.rate!==null?live.rate.toFixed(2):'—'}<em>CU / 小时</em></strong></div><div class="stat"><small>活动运行时</small><strong>${ok&&live.active!==null?live.active:'—'}<em>个</em></strong></div><div class="stat"><small>模型持久备份</small><strong>${verified?.backup_gib ?? '—'}<em>GiB · ${verified?.backup_files ?? 0} 文件</em></strong></div></section><div class="manager-grid"><div><section class="section-card"><h2>运行时控制</h2><span class="badge ${ok&&live.active===0?'':'warn'}">${!ok?L.text('状态未确认'):live.runtime_state==='owned'?L.text('● 工作站会话已连接'):live.runtime_state==='external'?L.text('● 已有外部会话，禁止重复启动'):live.runtime_state==='idle'?L.text('○ 当前没有活动会话'):L.text('会话数据核对中，禁止启动')}</span><div class="flow"><span>账号核对</span><b>→</b><span>恢复缓存</span><b>→</b><span>运行任务</span><b>→</b><span>备份并释放</span></div><div class="row"><label class="field"><span>GPU</span><select id="gpu"><option>G4</option></select></label><label class="field"><span>制作时长提醒 / 分钟</span><input id="maxminutes" type="number" value="${data.policy.max_minutes}" min="5" max="1440"></label></div><button id="save-policy">保存提醒设置</button><p class="muted">启动会开始消耗账户算力。到时仅提醒，生成与备份不会被计时器中断。镜头验收并保存后，再释放 GPU。</p><div class="row"><button class="primary" id="start" ${!ok||!live.can_start||runtimeBusy||live.operation_busy?'disabled':''}>${runtimeBusy?L.text('操作处理中…'):ok&&live.active>0?L.text('GPU 已分配'):ok&&live.lease_state?L.text('需核对开机记录'):L.text('启动 GPU')}</button><button class="danger" id="stop" ${!ok||!live.can_stop||runtimeBusy||live.operation_busy?'disabled':''}>保存后停止</button></div><p class="note">${ok&&live.runtime_state==='external'?L.text('检测到网页或其他工具建立的会话；这里只显示状态，停止按钮不可用。'):ok&&live.lease_state&&!live.can_stop?L.text('存在未确认的开机记录，需先核查，不能重复分配。'):L.text('停止仅作用于本工作站创建且已核实标识的会话。')}</p>${ok&&live.sessions?.length?`<ul>${live.sessions.map(r=>`<li>${esc(r.hardware)} · ${esc(r.name)}<br><small>${esc(r.endpoint)}</small></li>`).join('')}</ul>`:''}<details><summary>实时会话明细</summary><pre>${esc(live?.sessions_text||L.text('点击刷新读取'))}</pre></details></section><section class="section-card"><h2>持久备份与恢复</h2><dl class="details"><dt>备份位置</dt><dd>${esc(verified?.backup_path||L.text('尚未配置'))}</dd><dt>状态</dt><dd>${esc(verified?.backup_status || L.text("尚未在本机核验云端备份"))}</dd><dt>缓存策略</dt><dd>云盘备份 → 本地磁盘推理 → 结果归档</dd><dt>恢复入口</dt><dd><a href="/workstation.ipynb">下载官方工作站笔记本 ↗</a></dd></dl></section></div><div><section class="section-card"><h2>历史环境验证</h2><dl class="details"><dt>GPU</dt><dd>${esc(verified?.gpu||L.text('尚未验证'))}</dd><dt>显存 / 内存</dt><dd>96GB / ${esc(verified?.ram_gib||'—')}GiB</dd><dt>PyTorch / CUDA</dt><dd>${esc(verified?.torch||'—')} / ${esc(verified?.cuda||'—')}</dd><dt>ComfyUI</dt><dd>${esc((verified?.comfy_revision||'').slice(0,12))}</dd><dt>健康检查</dt><dd>${verified?.verified_at?L.text('历史记录；当前环境请重新检查'):L.text('本机尚未验证')}</dd><dt>视频推理</dt><dd>${esc(verified?.video_inference_status || L.text("待视频验收"))}</dd></dl></section><section class="section-card"><h2>操作记录</h2><div class="timeline">${(data.events||[]).slice(0,8).map(e=>`<p><small>${esc(e.time)}</small>${esc(e.text)}</p>`).join('')}<p><small>验证范围</small>环境是否就绪，以本次检查结果为准。GPU 是否占用，以顶部实时状态为准。</p></div></section></div></div>${typeof hardwareCompareView==='function'?hardwareCompareView():''}<footer>官方 CLI 控制运行时。界面不读取或展示登录凭证；历史验证与实时状态分开显示。</footer></main>`;
}

async function saveShot(){
 let body={id:selected,workflow:$('#shot-workflow')?.value||null};
 const curShot=(data.shots||[]).find(x=>x.id===selected);
 if(curShot?.camera_move)body.camera_move=curShot.camera_move;
 if(curShot?.shot_scale)body.shot_scale=curShot.shot_scale;
 for(let k of ['title','prompt','dialogue','subtitle_en','reference','end_reference','model','resolution'])if($('#'+k))body[k]=$('#'+k).value;
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
 if($('#save'))$('#save').onclick=()=>action(async()=>{await saveShot();render();toast(L.text('已保存新版本'))});
 if($('#prepare'))$('#prepare').onclick=()=>action(async()=>{await saveShot();await api('/api/job',{shot:selected});data=await api('/api/workspace');tab='jobs';render();toast(L.text('任务快照已保存；尚未消耗算力'))});
 for(const id of ['newshot','onboard-newshot'])if($('#'+id))$('#'+id).onclick=()=>action(async()=>{await api('/api/shot/new',{});data=await api('/api/workspace');selected=data.shots.at(-1).id;render()});
 if($('#import'))$('#import').onclick=()=>$('#file').click();
 if($('#onboard-import'))$('#onboard-import').onclick=()=>$('#file').click();
 if($('#onboard-script'))$('#onboard-script').onclick=()=>{if(typeof dramaPanelMode!=='undefined')dramaPanelMode='script';render()};
 if($('#file'))$('#file').onchange=()=>action(async()=>{
  let f=$('#file').files[0];if(!f)return;if(f.size>100e6)throw Error(L.text('素材请小于100MB'));
  let value=await new Promise((resolve,reject)=>{let r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(f)});
  await api('/api/asset',{name:f.name,data:value});data=await api('/api/workspace');tab='assets';render();toast(L.text('素材已导入本机项目'));
 });
 if($('#refresh'))$('#refresh').onclick=refresh;
 if($('#save-policy'))$('#save-policy').onclick=()=>action(async()=>{
  const minutes=Number($('#maxminutes').value);
  const cuBudget=$('#maxcubudget')?Number($('#maxcubudget').value):Number(data.policy.max_cu_budget||0);
  if(!Number.isInteger(minutes)||minutes<5||minutes>1440)throw Error(L.text('提醒时间须为5–1440的整数分钟'));
  if(!Number.isFinite(cuBudget)||cuBudget<0||cuBudget>5000)throw Error(L.text('算力预算须为 0（不限）或 0.1–5000 CU'));
  await api('/api/policy',{max_minutes:minutes,max_cu_budget:cuBudget,auto_release:data.policy.auto_release});data=await api('/api/workspace');renderLive();toast(L.text('提醒与算力预算护栏已保存；未改变当前运行时'));
 });
 if($('#start'))$('#start').onclick=()=>runtimeAction('start');
 if($('#stop'))$('#stop').onclick=()=>runtimeAction('stop');
 if($('#open-about'))$('#open-about').onclick=()=>{aboutOpen=true;render()};
 if($('#close-about'))$('#close-about').onclick=()=>{aboutOpen=false;render()};
 if($('#about-backdrop'))$('#about-backdrop').onclick=e=>{if(e.target.id==='about-backdrop'){aboutOpen=false;render()}};
 for(const fn of UI.binders)fn();
}

async function runtimeAction(kind){
 if(runtimeBusy)return;
 const gpu=$('#gpu').value,minutes=Number($('#maxminutes').value);
 await refresh();
 if(live?.error||!(kind==='start'?live.can_start:live.can_stop))return toast(L.text('会话状态已变化，操作已取消，请查看实时状态。'));
 if(!confirm(kind==='start'?L.html`启动 ${gpu} 会消耗 Colab 算力，${minutes} 分钟后提醒，不自动中断任务。确定启动？`:L.text('确认所有结果已保存？将停止本工作站创建的运行时，临时磁盘将释放。')))return;
 runtimeBusy=true;renderLive();
 try{await api('/api/runtime/'+kind,kind==='start'?{gpu,max_minutes:minutes}:{backup_confirmed:true});toast(kind==='start'?L.text('已核查运行时分配'):L.text('已核查停止结果'))}catch(e){toast(e.message)}finally{runtimeBusy=false;await refresh()}
}

async function action(fn){try{return await fn()}catch(e){toast(e.message);if(manager)await refresh()}}

function renderLive(){
 if(!manager||!data||!verified||projectFileBusy)return;
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
  try{live=await api('/api/status');liveReceivedAt=Date.now()}catch(e){liveReceivedAt=0;live={error:L.text('实时状态读取失败，已禁用启停：')+e.message}}
  renderLive();
  for(const hook of UI.refreshHooks){try{await hook()}catch(e){toast(L.text('操作记录读取失败：')+e.message)}}
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
