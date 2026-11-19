/* Shared operations, batch queue, step progress & safe interrupt UI. Zero string monkey-patching. */
let operations=[],remoteInspection=null,projectList=[],monitorState={enabled:false,urls:[],qr_svg:''},opsRequest=null,currentBridge=null,bridgeCheckedAt=0,opsCheckedAt=0,opsError=null;
const stateNames={queued:'等待执行',running:'执行中',succeeded:'已完成',failed:'失败',interrupted:'跟踪中断',prepared:'待提交',connecting:'正在连接'};
const busyOperation=()=>operations.some(x=>['queued','running'].includes(x.state));
const busyNonGenerate=()=>operations.some(x=>['queued','running'].includes(x.state)&&x.action!=='generate');

function bytes(n){if(n==null)return '—';return (n/1024**3).toFixed(2)+' GiB'}
function transferSize(n){if(n==null)return '—';return n>=1024**3?(n/1024**3).toFixed(2)+' GiB':n>=1024**2?(n/1024**2).toFixed(1)+' MiB':Math.round(n/1024)+' KiB'}
const operationNames={start:'启动 GPU',stop:'保存并关闭 GPU',inspect:'检查工作环境',setup:'准备运行环境',bridge:'连接 ComfyUI 画布',mount:'连接云盘',models:'准备模型',restore:'恢复模型',backup:'备份项目',generate:'生成作品',resume:'继续跟踪作品',adopt:'接管已有 GPU',reconcile:'核对会话记录'};
function operationTime(o){return new Date((o.finished||o.updated||o.created)*1000).toLocaleString()}

function technicalLog(o){
 return `<details class="technical-log" id="op-log-${esc(o.id)}"><summary>查看技术日志</summary><pre>${esc((o.events||[]).slice(-12).map(e=>new Date(e.at*1000).toLocaleTimeString()+' '+e.message).join('\n')||o.message||'无详细日志')}</pre>${o.result?`<pre>${esc(JSON.stringify(o.result,null,2))}</pre>`:''}</details>`;
}

function activeOperation(o){
 const speed=o.bytes_done&&o.updated>o.created?o.bytes_done/(o.updated-o.created):0;
 const bytePct=o.bytes_total?Math.max(0,Math.min(100,100*(o.bytes_done||0)/o.bytes_total)):null;
 const stepPct=o.step_total>0?Math.max(0,Math.min(100,100*(o.step_done||0)/o.step_total)):null;
 const canInterrupt=o.state==='running'&&['generate','resume'].includes(o.action);
 const canRemoveQueue=o.state==='queued'&&o.action==='generate';
 return `<article class="operation ${o.state==='running'?'running':'queued'}"><div class="summary"><b>${esc(operationNames[o.action]||o.label)}</b><span class="badge ${o.state==='queued'?'warn':''}">${esc(stateNames[o.state]||o.state)}</span></div><p>${esc(o.message||'正在处理…')}</p>${
  stepPct!==null
   ? `<progress value="${stepPct}" max="100"></progress><small>采样第 ${o.step_done||0} / ${o.step_total} 步 · ${stepPct.toFixed(1)}%${o.eta_seconds!=null?` · 预计剩余 ${o.eta_seconds} 秒`:''}</small>`
   : bytePct!==null
   ? `<progress value="${bytePct}" max="100"></progress><small>${transferSize(o.bytes_done||0)} / ${transferSize(o.bytes_total)} · ${bytePct.toFixed(1)}%${speed?' · 约 '+(speed/1024**2).toFixed(1)+' MiB/s':''}</small>`
   : '<div class="activity"><span></span></div>'
 }${o.elapsed?`<small style="display:block;margin-top:4px">已运行 ${Math.floor(o.elapsed/60)} 分 ${Math.floor(o.elapsed%60)} 秒</small>`:''}${
  canInterrupt?`<div class="row" style="margin-top:10px"><button class="danger" id="interrupt-sampling">⏹ 中断当前采样（保留 GPU）</button></div>`:''
 }${
  canRemoveQueue?`<div class="row" style="margin-top:8px"><button class="ghost" data-cancel-queued="${esc(o.id)}">✕ 移出等待队列</button></div>`:''
 }${o.stage==='authorization_required'?'<p><a class="inline-link" href="http://127.0.0.1:8768/auth" target="_blank">前往 Google 完成云盘授权 →</a> <button id="drive-continue">已授权，继续</button></p>':''}${technicalLog(o)}</article>`;
}

function historyGroups(){
 const groups=new Map();
 for(const o of operations.filter(x=>!['queued','running'].includes(x.state))){
  if(!groups.has(o.action))groups.set(o.action,[]);
  groups.get(o.action).push(o);
 }
 return [...groups.values()].map(rows=>rows.sort((a,b)=>b.created-a.created)).sort((a,b)=>b[0].created-a[0].created);
}

function opCards(){
 const active=operations.filter(x=>['queued','running'].includes(x.state)).sort((a,b)=>(a.state==='running'?-1:1)||(a.created-b.created));
 const history=historyGroups(),count=history.reduce((n,g)=>n+g.length,0);
 return `<div class="task-status-caption">${opsError?'任务同步失败，以下为上次记录。请重新核对。':opsCheckedAt?'执行中每 3 秒更新；空闲时每 15 秒核对。':'正在同步任务…'}</div>${opsError?`<p class="note">${esc(opsError)}</p>`:''}${active.length?active.map(activeOperation).join(''):`<div class="task-empty"><span class="task-idle-dot"></span><div><b>${opsError||!opsCheckedAt?'当前任务状态待确认':'当前没有运行中的任务'}</b><p>下方历史记录不表示 GPU 或画布仍在连接。</p></div></div>`}<details class="operation-history" id="operation-history"><summary>历史操作 <span>${count} 条记录</span></summary><p class="note">这里是以前的操作结果，不是当前状态。同类操作合并显示，失败后重试成功也保留记录。</p>${history.map(rows=>{const latest=rows[0],status=latest.state==='succeeded'?'成功':latest.state==='failed'?'失败':latest.state==='interrupted'?'跟踪中断':stateNames[latest.state]||latest.state;return `<details class="history-group" data-disclosure="history-${esc(latest.action)}"><summary><b>${esc(operationNames[latest.action]||latest.label)}</b><span>${rows.length} 次 · 最近${esc(status)}</span><time>${operationTime(latest)}</time></summary>${rows.map(o=>`<article class="history-entry"><div class="summary"><span class="history-result">当时${esc(o.state==='succeeded'?'成功':o.state==='failed'?'失败':stateNames[o.state]||o.state)}</span><time>${operationTime(o)}</time></div><p class="note">当时记录：${esc(o.message||'操作结束')}</p>${technicalLog(o)}</article>`).join('')}</details>`}).join('')||'<p class="note">暂无历史操作。</p>'}</details>`;
}

function currentEnvironment(){
 if(!liveUsable()||live.runtime_state!=='owned'||!remoteInspection?.endpoint||remoteInspection.endpoint!==live.managed_session?.endpoint)return null;
 return remoteInspection;
}

function connectionView(){
 const fresh=liveUsable(),owned=fresh&&live.runtime_state==='owned',off=fresh&&live.runtime_state==='idle',snapshot=currentEnvironment();
 const bridgeFresh=bridgeCheckedAt&&Date.now()-bridgeCheckedAt<30000;
 const bridgeReady=owned&&bridgeFresh&&currentBridge?.ready&&currentBridge.endpoint===live.managed_session?.endpoint;
 let drive=off?'GPU 已关闭，未挂载':snapshot?(snapshot.drive_mounted?'最近检查：已挂载':'最近检查：未挂载'):'尚未检查';
 return `<section class="section-card connection-card"><div class="summary"><h2>当前连接</h2><small>${fresh?'GPU 每 15 秒核对':'正在核对连接'}</small></div><div class="connection-row"><span>GPU</span><b>${!fresh?'状态待确认':off?'未启动':owned?'已连接 G4':live.runtime_state==='external'?'检测到外部会话':'状态待确认'}</b></div><div class="connection-row"><span>ComfyUI 画布</span><b>${!fresh?'状态待确认':off?'未连接':bridgeReady?'连接通道可用':bridgeFresh?'未连接':'正在检查'}</b></div><div class="connection-row"><span>云盘挂载</span><b>${esc(drive)}</b></div>${snapshot?`<p class="note">云盘与磁盘来自本次会话的环境检查（${new Date(snapshot.checked_at*1000).toLocaleString()}），不会把旧会话的快照显示为当前状态。</p>`:owned?'<p class="note">点击“检查工作环境”核对本次云盘与磁盘；不会自动启动其他会话。</p>':''}</section>`;
}

UI.managerRenderer=function(){
 const ok=liveUsable(),can=ok&&live.account_ok&&!runtimeBusy&&!live.operation_busy&&live.runtime_state==='owned'&&!busyOperation(),ri=remoteInspection,disk=currentEnvironment()?.disk;
 const topPanels=UI.managerTopPanels.map(fn=>fn()).join('');
 return `<main class="manager"><div class="hero"><div><h1>Colab 算力管理</h1><p class="muted">最高配置 G4 · 按任务恢复 · 保存核验后释放</p></div><button id="refresh">↻ 核对实时状态</button></div><div class="hint">${ok?`${esc(live.email)} · ${live.account_ok?'账号核验通过':'需确认绑定账号'} · ${esc(live.checked_at)} · 15秒核对一次`:esc(liveHint())}</div>${ok&&!live.account_ok?'<button id="bind-account">确认绑定当前账号</button>':''}${topPanels}<section class="stats"><div class="stat"><small>可用算力</small><strong>${ok&&live.balance!=null?live.balance.toFixed(2):'—'}<em>CU</em></strong></div><div class="stat"><small>当前消耗速率</small><strong>${ok&&live.rate!=null?live.rate.toFixed(2):'—'}<em>CU / 小时</em></strong></div><div class="stat"><small>活动会话</small><strong>${ok?live.active??'—':'—'}<em>个</em></strong></div><div class="stat"><small>本次磁盘余量</small><strong>${disk?(disk.free/1024**3).toFixed(1):'—'}<em>GiB</em></strong></div></section><div class="manager-grid"><div>${connectionView()}<section class="section-card"><h2>运行时</h2><span class="badge ${ok&&live.runtime_state==='idle'?'':'warn'}">${!ok?'状态未确认':live.runtime_state==='owned'?'● 工作站会话已连接':live.runtime_state==='external'?'● 已有外部会话，禁止重复启动':live.runtime_state==='idle'?'○ 当前没有活动会话':'会话数据核对中，禁止启动'}</span><div class="row"><label class="field"><span>生产配置</span><select id="gpu"><option>G4</option></select></label><label class="field"><span>时长提醒 / 分钟</span><input id="maxminutes" type="number" min="5" max="1440" value="${data.policy.max_minutes}"></label><label class="field"><span>会话算力护栏 / CU</span><input id="maxcubudget" type="number" min="0" max="5000" step="0.5" placeholder="0=不限" value="${data.policy.max_cu_budget||0}"></label></div><div class="row"><button id="save-policy">保存提醒与预算设置</button>${ok&&live.can_reconcile?'<button data-control="reconcile">核对并清理旧开机记录</button>':''}</div>${data.policy.budget_paused?'<p class="hint" style="border:1px solid #ebd39a;color:#ebd39a;margin:10px 0">⚠ 已达到本次会话设定的 CU 算力预算护栏上限，后续排队镜头已自动暂停（当前 GPU 与已完成资产保留）。调整预算保存后可继续排队。</p>':''}<p class="note">提醒不会中断正在采样的任务；设定 CU 预算护栏后，累计消耗达标会自动暂停后续等待队列。网页会话先显示，由你选择G4并点击接管。</p><div class="row"><button class="primary" id="start" ${!ok||!live.account_ok||!live.can_start||runtimeBusy||live.operation_busy||busyOperation()?'disabled':''}>${busyOperation()?'操作执行中…':ok&&live.active>0?'GPU 已分配':'启动 GPU'}</button><button class="danger" id="stop" ${!ok||!live.account_ok||!live.can_stop||runtimeBusy||live.operation_busy||busyOperation()?'disabled':''}>备份核验后关机</button></div>${ok&&live.account_ok&&!busyOperation()&&live.runtime_state==='external'&&live.sessions?.some(s=>s.hardware==='G4')?`<div class="row"><select id="adopt-endpoint" aria-label="选择接管G4">${live.sessions.filter(s=>s.hardware==='G4').map(s=>`<option value="${esc(s.endpoint)}">${esc(s.name)} · ${esc(s.endpoint)}</option>`).join('')}</select><button id="adopt">接管此G4</button></div>`:''}${can?'<button data-control="mount">挂载模型云盘</button>':''}<details><summary>实时会话明细</summary><pre>${esc(live?.sessions_text||'尚未读取')}</pre></details></section><section class="section-card"><h2>工作环境</h2><div class="control-grid"><button data-control="inspect" ${!can?'disabled':''}>检查工作环境</button><button data-control="restore" ${!can?'disabled':''}>恢复完整 BF16 模型</button><button data-control="setup" ${!can?'disabled':''}>启动 ComfyUI 环境</button><button data-control="backup" ${!can?'disabled':''}>备份结果与工作流</button></div><p class="note">模型从已有云盘清单恢复，逐文件校验。工作结果备份到专用目录；关机前额外等待 Drive 刷新。新会话先点击“挂载模型云盘”，按 Google 页面完成已有账号授权。</p><p><a class="inline-link" href="/workstation.ipynb">下载挂载与恢复笔记本</a> · <button id="local-backup">导出本机工作区备份</button> <button id="local-restore">从备份导入新项目</button><input id="restore-file" type="file" accept=".zip" hidden></p>${ri?`<details class="environment-history" id="environment-history"><summary>上次环境检查 · ${new Date(ri.checked_at*1000).toLocaleString()}（历史快照）</summary><p class="note">以下数据只反映检查当时，不代表现在仍在线。</p><dl class="details"><dt>检查时间</dt><dd>${new Date(ri.checked_at*1000).toLocaleString()} · 历史快照</dd><dt>GPU 实际分配</dt><dd>${esc((ri.gpu||[]).join('\n')||'未检测到')}</dd><dt>磁盘 / 空闲</dt><dd>${bytes(ri.disk?.total)} / ${bytes(ri.disk?.free)}</dd><dt>Drive</dt><dd>${ri.drive_mounted?'已挂载':'未挂载'}</dd><dt>ComfyUI</dt><dd>${ri.comfy?.online?'在线 · 运行 '+ri.comfy.queue_running+' / 排队 '+ri.comfy.queue_pending:'未就绪'}</dd><dt>本地模型文件</dt><dd>${ri.models?.length||0} 个（不代表已推理验收）</dd></dl></details>`:'<p class="muted">尚无本控制台产生的远端检查。开机后点击检查。</p>'}</section><section class="section-card"><h2>模型目录</h2>${(data.models||[]).map(m=>`<div class="catalog-row"><div><b>${esc(m.name)}</b><p>${esc(m.description)}</p></div><span class="badge ${m.tested?'':'warn'}">${m.tested?'历史实测':'候选'}</span></div>`).join('')}<small>历史实测、云盘备份、当前会话就绪分别记录。新模型接入前验证许可、完整权重和执行适配器。</small></section></div><div><section class="section-card"><h2>当前任务</h2><div id="operations-panel">${opCards()}</div></section><section class="section-card" id="monitor-panel"><div class="summary"><h2>手机只读监看</h2><span class="badge ${monitorState?.enabled?'':'warn'}">${monitorState?.enabled?'● 已开启只读通道':'默认关闭'}</span></div><p class="note">在同一局域网或 Tailscale 下用手机扫码查看实时 CU、速率与批次采样步数。<b>纯只读零写权限</b>，不暴露任何 Google 凭证，关闭即刻失效。</p><button id="monitor-toggle">${monitorState?.enabled?'关闭手机监看通道':'开启局域网 / Tailscale 只读监看'}</button>${monitorState?.enabled?`<div class="qr-box">${monitorState.qr_svg||''}<div style="flex:1;min-width:180px"><small>手机扫码或访问一次性只读地址：</small>${(monitorState.urls||[]).map(u=>`<p style="margin:6px 0;font-size:12px;word-break:break-all"><a class="inline-link" href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a></p>`).join('')}</div></div>`:''}</section><section class="section-card"><h2>最近项目</h2><p>${esc(data.project.name)} · ${data.project.status==='completed'?'已结项':'制作中'}</p><a class="inline-link" href="/studio">打开视频工作区 →</a><p class="note">退出窗口与释放云端 GPU 是独立操作。结束工作请使用“备份核验后关机”。</p></section></div></div>${typeof hardwareCompareView==='function'?hardwareCompareView():''}<footer>状态来自官方CLI与明确绑定的运行时。没有会话时不会为了检查而分配GPU。</footer></main>`;
};

UI.studioProjectControls=function(){
 return `<select id="project-select" aria-label="切换项目">${projectList.map(p=>`<option value="${esc(p.id)}" ${p.id===data.project.id?'selected':''}>${esc(p.name)}${p.status==='completed'?' · 已结项':''}</option>`).join('')}</select><button id="new-project">＋ 新项目</button><button id="remove-project" class="ghost">移除项目</button>`;
};

UI.views.jobs=function(){
 const jobs=data.jobs||[];
 if(!jobs.length)return '<div class="section-card empty">暂无任务。创建任务保存参数快照；支持单个或批量排队提交到G4。</div>';
 const activeJobIds=new Set(operations.filter(o=>['queued','running'].includes(o.state)&&o.job_id).map(o=>o.job_id));
 const batchable=jobs.filter(j=>j.state==='prepared'&&!j.attempted&&!activeJobIds.has(j.id));
 const activeGen=operations.find(o=>o.state==='running'&&['generate','resume'].includes(o.action));
 const queuedCount=operations.filter(o=>o.state==='queued'&&o.action==='generate').length;
 const toolbar=(batchable.length||activeGen||queuedCount)?`<div class="section-card batch-bar"><div class="summary"><div><b>单次 G4 任务队列</b><p class="note" style="margin:4px 0 0">待提交 ${batchable.length} 项 · 队列等待 ${queuedCount} 项${activeGen?(activeGen.step_total?` · 当前采样 ${activeGen.step_done||0}/${activeGen.step_total} 步`:' · 正在采样 1 项'):''}</p></div><span class="line"></span>${batchable.length>1?`<button class="primary" id="run-batch-jobs">⚡ 批量排队提交 (${batchable.length})</button>`:''}${activeGen?`<button class="danger" id="interrupt-sampling-studio">⏹ 中断当前采样</button>`:''}</div></div>`:'';
 return toolbar+jobs.map(j=>{
  const queuedOp=operations.find(o=>o.job_id===j.id&&o.state==='queued');
  const runningOp=operations.find(o=>o.job_id===j.id&&o.state==='running');
  return `<section class="section-card"><div class="summary"><h3>${esc(j.title)}</h3><span class="badge ${j.state==='succeeded'?'':'warn'}">${queuedOp?'队列等待中':runningOp&&runningOp.step_total?`采样 ${runningOp.step_done||0}/${runningOp.step_total}`:esc(stateNames[j.state]||j.state)}</span></div><p>${esc(runningOp?.message||queuedOp?.message||j.message||'任务参数已保存')}</p>${runningOp&&runningOp.step_total?`<progress value="${Math.min(100,100*(runningOp.step_done||0)/runningOp.step_total)}" max="100" style="width:100%;height:8px;margin-bottom:8px"></progress>`:''}${j.prompt_id?`<small>远端任务 ${esc(j.prompt_id)}</small>`:''}<div class="row" style="margin-top:10px">${j.state==='prepared'&&!queuedOp?`<button class="primary" data-run="${j.id}">${busyOperation()?'加入 G4 队列':'提交到当前 G4'}</button>`:''}${queuedOp?`<button class="ghost" data-cancel-queued="${esc(queuedOp.id)}">移出等待队列</button>`:''}${['interrupted','failed','running','connecting'].includes(j.state)&&j.attempted&&!runningOp?`<button data-resume="${j.id}">检查并恢复跟踪</button>`:''}<button data-export="${j.id}">${j.config?.model==='workflow'?'导出任务工作流':'导出笔记本'}</button></div>${(j.results||[]).map(id=>`<div class="result-preview" style="margin-top:12px">${media(asset(id),true)}</div>`).join('')}</section>`;
 }).join('');
};

async function workspaceRefresh(){
 for(const fn of UI.workspaceHooks)fn();
 [data,projectList]=await Promise.all([api('/api/workspace'),api('/api/projects')]);
 selected=data.shots[0]?.id;
 render();
}

async function syncOperations(){
 if(opsRequest)return opsRequest;
 opsRequest=(async()=>{
  const results=await Promise.allSettled([api('/api/operations'),api('/api/inspection'),api('/api/projects'),api('/api/bridge'),api('/api/monitor')]);
  if(results[0].status==='fulfilled'&&Array.isArray(results[0].value)){operations=results[0].value;opsCheckedAt=Date.now();opsError=null}else opsError=results[0].reason?.message||'任务记录读取失败';
  if(results[1].status==='fulfilled')remoteInspection=results[1].value;
  if(results[2].status==='fulfilled'&&Array.isArray(results[2].value))projectList=results[2].value;
  if(results[3].status==='fulfilled'){currentBridge=results[3].value;bridgeCheckedAt=Date.now()}else{currentBridge=null;bridgeCheckedAt=0}
  if(results[4].status==='fulfilled'&&results[4].value)monitorState=results[4].value;
  if(manager)renderLive();else if(tab==='jobs'){data=await api('/api/workspace');render()}
 })();
 try{await opsRequest}finally{opsRequest=null}
}

UI.refreshHooks.push(syncOperations);

async function control(kind,body={}){
 const allowQueuedGenerate=(kind==='generate'||kind==='generate_batch')&&!busyNonGenerate();
 if(runtimeBusy||(busyOperation()&&!allowQueuedGenerate))return toast('已有操作正在执行。');
 runtimeBusy=true;renderLive();
 try{
  await refresh();
  if(!liveUsable()||!live.account_ok)throw Error('未取得当前账号的实时状态，未提交操作。');
  if(kind==='start'&&!live.can_start)throw Error('已有会话或开机记录，未重复申请GPU。');
  if(kind==='stop'&&!live.can_stop)throw Error('未确认当前工作站会话，未提交关机。');
  if(kind==='adopt'&&!live.sessions?.some(s=>s.endpoint===body.endpoint&&s.hardware==='G4'))throw Error('所选G4已变化，请重新选择。');
  if(!['start','adopt','reconcile'].includes(kind)&&live.runtime_state!=='owned')throw Error('当前没有已核实归属的G4会话。');
  const notices={
   models:'在当前G4下载清单中的完整精度模型并核验、备份到已挂载云盘，会消耗当前会话时间和磁盘空间。继续？',
   mount:'将当前G4连接到已授权的Google云盘？凭证由Google传播，App只记录挂载状态。',
   bridge:'连接当前G4的ComfyUI画布？只建立本机连接，不申请新的GPU。',
   adopt:'把所选G4交由工作站管理？不会新建GPU。之后可检查、备份并释放这个明确会话。',
   restore:'从已授权云盘恢复完整BF16模型，可能耗时并持续消耗当前会话算力。继续？',
   setup:'在当前G4中安装隔离依赖并启动ComfyUI。继续？',
   backup:'备份当前工作结果与配置到工作站云盘目录。继续？',
   generate:'使用当前G4执行此任务，会消耗Colab算力。确认提交（若已有生成任务将自动顺序排队）？',
   generate_batch:`将 ${body.jobs?.length||0} 个待生成镜头按顺序加入当前 G4 队列连续执行？`,
   stop:'确认制作任务已结束？将备份结果、逐项校验、等待云盘刷新后释放本工作站GPU。任何一步失败都会保留运行时。',
   start:'启动最高配置G4会消耗Colab算力。不自动改用其他配置。确定启动？'
  };
  if(notices[kind]&&!confirm(notices[kind]))return;
  await action(async()=>{
   await api('/api/operations',{action:kind,...body});
   await syncOperations();
   toast(kind==='generate_batch'?'批量任务已加入G4队列':'操作已登记，可在进度区查看');
  });
 }catch(e){toast(e.message)}finally{runtimeBusy=false;renderLive()}
}

runtimeAction=async function(kind){
 if(kind==='start')return control('start',{gpu:'G4',max_minutes:Number($('#maxminutes').value)});
 return control('stop',{backup_confirmed:true});
};

async function triggerInterrupt(){
 if(!confirm('中断当前正在采样的镜头任务？不会关闭 ComfyUI，也不会释放 G4 GPU，已完成资产保留。'))return;
 await action(async()=>{await api('/api/runtime/interrupt',{});await syncOperations();toast('已发送安全中断信号；GPU 会话保留')});
}

UI.binders.push(()=>{
 if($('#adopt'))$('#adopt').onclick=()=>control('adopt',{endpoint:$('#adopt-endpoint').value});
 if($('#monitor-toggle'))$('#monitor-toggle').onclick=()=>action(async()=>{
  monitorState=await api('/api/monitor/toggle',{enabled:!monitorState?.enabled});
  renderLive();
  toast(monitorState.enabled?'已开启手机只读监看二维码（零控制权限）':'已关闭手机监看并销毁临时令牌');
 });
 if($('#interrupt-sampling'))$('#interrupt-sampling').onclick=triggerInterrupt;
 if($('#interrupt-sampling-studio'))$('#interrupt-sampling-studio').onclick=triggerInterrupt;
 document.querySelectorAll('[data-cancel-queued]').forEach(e=>e.onclick=()=>action(async()=>{
  await api('/api/operations/cancel-queued',{id:e.dataset.cancelQueued});
  await syncOperations();toast('已从等待队列移出');
 }));
 if($('#run-batch-jobs'))$('#run-batch-jobs').onclick=()=>{
  const activeJobIds=new Set(operations.filter(o=>['queued','running'].includes(o.state)&&o.job_id).map(o=>o.job_id));
  const ids=(data.jobs||[]).filter(j=>j.state==='prepared'&&!j.attempted&&!activeJobIds.has(j.id)).map(j=>j.id);
  if(ids.length)control('generate_batch',{jobs:ids});
 };
 if($('#remove-project'))$('#remove-project').onclick=()=>action(async()=>{
  if(!UI.leaveGuards.every(fn=>fn(tab,tab)))return;
  if(!confirm('将当前项目移出列表，可从本机项目回收记录恢复。素材文件不会永久删除。继续？'))return;
  await api('/api/project/delete',{});await workspaceRefresh();
 });
 if($('#drive-continue'))$('#drive-continue').onclick=()=>action(async()=>{await api('/api/drive/continue',{});toast('正在继续挂载，请查看操作状态')});
 if($('#comfy-canvas'))$('#comfy-canvas').onclick=()=>action(async()=>{
  await refresh();
  if(!liveUsable()||!live.account_ok||live.runtime_state!=='owned')return toast('请先连接并接管当前G4，再启动ComfyUI环境。');
  const bridge=await api('/api/bridge');
  if(bridge.ready&&bridge.endpoint===live.managed_session?.endpoint){location.href=bridge.url;return}
  await control('bridge');
 });
 if($('#bind-account'))$('#bind-account').onclick=()=>action(async()=>{
  if(!confirm('将当前CLI账号 '+live.email+' 绑定到 GC Labs？此操作不会申请GPU。'))return;
  await api('/api/account/bind',{email:live.email});await refresh();
 });
 document.querySelectorAll('[data-control]').forEach(e=>e.onclick=()=>control(e.dataset.control));
 document.querySelectorAll('[data-run]').forEach(e=>e.onclick=()=>control('generate',{job:e.dataset.run}));
 document.querySelectorAll('[data-resume]').forEach(e=>e.onclick=()=>control('resume',{job:e.dataset.resume}));
 if($('#local-restore'))$('#local-restore').onclick=()=>$('#restore-file').click();
 if($('#restore-file'))$('#restore-file').onchange=()=>action(async()=>{
  const file=$('#restore-file').files[0];if(!file)return;
  if(file.size>100000000)return toast('备份请小于100MB');
  if(!confirm('从此备份导入独立项目？保留现有项目，历史任务不会自动执行。'))return;
  const raw=await file.arrayBuffer();let binary='';
  for(let i=0;i<raw.byteLength;i+=32768)binary+=String.fromCharCode(...new Uint8Array(raw,i,Math.min(32768,raw.byteLength-i)));
  const result=await api('/api/local-restore',{data:btoa(binary)});await workspaceRefresh();
  toast('已恢复 '+result.assets+' 个素材；未随备份打包的外部素材 '+result.missing_external_assets+' 个');
 });
 if($('#local-backup'))$('#local-backup').onclick=()=>action(async()=>{
  const r=await api('/api/local-backup',{});const a=document.createElement('a');a.href=r.url;a.download=r.file;a.click();
  toast('工作区备份已生成；外部引用素材保持原路径');
 });
 if($('#new-project'))$('#new-project').onclick=()=>action(async()=>{
  if(!UI.leaveGuards.every(fn=>fn(tab,tab)))return;
  const name=prompt('新项目名称');if(!name)return;
  await api('/api/project/new',{name});await workspaceRefresh();
 });
 if($('#project-select'))$('#project-select').onchange=()=>action(async()=>{
  if(!UI.leaveGuards.every(fn=>fn(tab,tab))){$('#project-select').value=data.project.id;return}
  await api('/api/project/select',{id:$('#project-select').value});await workspaceRefresh();
 });
});

setInterval(()=>{if(!document.hidden&&busyOperation())syncOperations().catch(()=>{})},3000);
syncOperations().then(()=>{if(data)render()}).catch(()=>{});
