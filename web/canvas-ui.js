// Project canvas & native AVFoundation frame chaining: reference assets → shots → generated results.
let boardMode=true,boardScale=1,dragNode=null;

function shotXY(s,i){return [Number.isFinite(s.x)?Math.max(220,s.x):80+i*350,Number.isFinite(s.y)?s.y:120]}

function shotBoard(){
 const readonly=data.project.status==='completed';
 return `<div class="board-tools"><button id="board-toggle">${boardMode?'切换卡片':'切换画布'}</button>${boardMode?'<button id="board-zoom-out" aria-label="缩小画布">−</button><span>'+Math.round(boardScale*100)+'%</span><button id="board-zoom-in" aria-label="放大画布">＋</button><button id="board-arrange">整理布局</button>':''}<span class="muted">${readonly?'已结项 · 只读':'拖动镜头标题调整布局，点选后编辑。视频结果可一键提取尾帧接力下一镜头。'}</span></div>${boardMode?`<div class="project-board" id="project-board"><div class="board-world" style="width:${Math.max(1800,...(data.shots||[]).map((s,i)=>shotXY(s,i)[0]+750))}px;height:${Math.max(1000,...(data.shots||[]).map((s,i)=>shotXY(s,i)[1]+600))}px;transform:scale(${boardScale});transform-origin:0 0"><svg class="board-edges" width="100%" height="100%">${(data.shots||[]).map((s,i)=>{const [x,y]=shotXY(s,i);return `${s.reference?`<path d="M${x-40},${y+100} C${x-25},${y+100} ${x-20},${y+100} ${x},${y+100}"/>`:''}${s.output?`<path d="M${x+270},${y+100} C${x+295},${y+100} ${x+300},${y+100} ${x+330},${y+100}"/>`:''}`}).join('')}</svg>${(data.shots||[]).map((s,i)=>{const [x,y]=shotXY(s,i),outAsset=s.output?asset(s.output):null;return `${s.reference?`<article class="board-asset" style="left:${x-190}px;top:${y+30}px">${media(asset(s.reference))}<small>参考图</small></article>`:''}<article class="board-shot ${s.id===selected?'selected':''}" data-board-shot="${s.id}" style="left:${x}px;top:${y}px"><div class="board-handle" data-drag-shot="${s.id}"><small>SHOT ${i+1}</small><b>${esc(s.title)}</b></div><div class="board-preview" data-shot="${s.id}">${media(asset(s.output||s.reference))}</div><small>${esc(s.model==='workflow'?(data.workflows||[]).find(w=>w.id===s.workflow)?.name||'自定义工作流':(data.models||[]).find(m=>m.id===s.model)?.name||s.model)} · ${s.resolution}</small><p>${esc((s.prompt||'').slice(0,90))||'点选镜头填写提示词'}</p><button data-shot="${s.id}">编辑镜头</button></article>${s.output?`<article class="board-asset board-result" style="left:${x+330}px;top:${y+30}px">${media(outAsset,true)}<small>生成结果</small>${!readonly&&outAsset?.kind==='video'?`<button class="chain-btn" data-chain-shot="${esc(s.id)}">↳ 尾帧接力下镜</button>`:''}</article>`:''}`}).join('')||'<p class="empty">点击“新镜头”开始搭建工作流。</p>'}</div></div>`:''}`;
}

UI.views.shots=function(defaultShotsView){
 return shotBoard()+(boardMode?'':defaultShotsView());
};

UI.shotModelOptions.push(s=>`<option value="workflow" ${s.model==='workflow'?'selected':''}>自定义 ComfyUI 工作流</option>`);

UI.shotExtraFields.push(s=>{
 const choices=(data.workflows||[]).map(w=>`<option value="${esc(w.id)}" ${s.workflow===w.id?'selected':''}>${esc(w.name)} · ${esc(w.kind)}</option>`).join('');
 return `<label class="field"><span>工作流</span><select id="shot-workflow"><option value="">选择工作流</option>${choices}</select></label>`;
});

UI.shotFooterActions.push(s=>{
 const outAsset=s.output?asset(s.output):null;
 const chainControls=outAsset?.kind==='video'?`<div class="chain-panel"><small class="muted">画面接力（本机 AVFoundation 提取，零算力）</small><div class="row" style="margin-top:8px"><button id="chain-last-next">↳ 尾帧接力下一镜头</button><button id="chain-last-new">＋ 尾帧新建续镜</button></div><button id="chain-first-asset" class="ghost" style="width:100%;margin-top:6px">提取首帧存入素材库</button></div>`:'';
 return `${chainControls}<div class="row" style="margin-top:12px"><button id="shot-up">前移</button><button id="shot-down">后移</button><button id="shot-remove" class="danger">移除镜头</button></div>`;
});

async function runFrameChain(shotId,position,target){
 await action(async()=>{
  const res=await api('/api/shot/chain-frame',{source_shot:shotId,position,target});
  data=await api('/api/workspace');
  if(res.bound_shot)selected=res.bound_shot;
  render();
  toast(res.bound_shot?'已提取高清帧并自动绑定为下一镜头参考图':'已提取高清帧存入项目素材库');
 });
}

UI.binders.push(()=>{
 if($('#shot-workflow'))$('#shot-workflow').onchange=()=>{
  if($('#shot-workflow').value)$('#model').value='workflow';
  const recipe=(data.workflows||[]).find(w=>w.id===$('#shot-workflow').value);
  if($('#duration'))$('#duration').max=recipe?.kind==='audio'?600:15;
 };
 if($('#board-toggle'))$('#board-toggle').onclick=()=>{boardMode=!boardMode;render()};
 for(const [id,delta] of [['board-zoom-in',.1],['board-zoom-out',-.1]])if($('#'+id))$('#'+id).onclick=()=>{boardScale=Math.max(.4,Math.min(1.5,boardScale+delta));render()};
 if($('#board-arrange'))$('#board-arrange').onclick=()=>action(async()=>{
  if(data.project.status==='completed')throw Error('已结项项目只读。');
  await api('/api/layout',{shots:data.shots.map((s,i)=>({id:s.id,x:220+(i%3)*820,y:70+Math.floor(i/3)*510}))});
  data=await api('/api/workspace');render();
 });
 document.querySelectorAll('[data-drag-shot]').forEach(handle=>{
  handle.onpointerdown=event=>{
   if(data.project.status==='completed'||event.button!==0)return;
   const s=data.shots.find(x=>x.id===handle.dataset.dragShot),[x,y]=shotXY(s,data.shots.indexOf(s));
   dragNode={s,x,y,clientX:event.clientX,clientY:event.clientY,card:handle.closest('.board-shot')};
   handle.setPointerCapture(event.pointerId);event.preventDefault();
  };
  handle.onpointermove=event=>{
   if(!dragNode)return;
   const x=Math.max(200,dragNode.x+(event.clientX-dragNode.clientX)/boardScale),y=Math.max(30,dragNode.y+(event.clientY-dragNode.clientY)/boardScale);
   dragNode.s.x=Math.round(x);dragNode.s.y=Math.round(y);dragNode.card.style.left=x+'px';dragNode.card.style.top=y+'px';
  };
  handle.onpointerup=()=>{
   if(!dragNode)return;const s=dragNode.s;dragNode=null;
   action(async()=>{await api('/api/layout',{shots:[{id:s.id,x:s.x,y:s.y}]});render()});
  };
  handle.onpointercancel=()=>{dragNode=null;render()};
 });
 document.querySelectorAll('[data-chain-shot]').forEach(btn=>{
  btn.onclick=e=>{e.stopPropagation();runFrameChain(btn.dataset.chainShot,'last','next')};
 });
 if($('#chain-last-next'))$('#chain-last-next').onclick=()=>runFrameChain(selected,'last','next');
 if($('#chain-last-new'))$('#chain-last-new').onclick=()=>runFrameChain(selected,'last','new');
 if($('#chain-first-asset'))$('#chain-first-asset').onclick=()=>runFrameChain(selected,'first','none');
 if($('#shot-remove'))$('#shot-remove').onclick=()=>action(async()=>{
  if(!confirm('移除此镜头？记录进入本机回收区，素材和历史任务保留。'))return;
  await api('/api/shot/delete',{id:selected});await workspaceRefresh();
 });
 for(const [id,step] of [['shot-up',-1],['shot-down',1]])if($('#'+id))$('#'+id).onclick=()=>action(async()=>{
  const ids=data.shots.map(s=>s.id),i=ids.indexOf(selected),j=i+step;
  if(j<0||j>=ids.length)return;
  [ids[i],ids[j]]=[ids[j],ids[i]];
  await api('/api/layout',{order:ids});data=await api('/api/workspace');render();
 });
});
