var L=(typeof window!=="undefined"?window:globalThis).GCLabsI18n||{text:x=>x,html:(s,...v)=>s.reduce((a,p,i)=>a+p+(i<v.length?v[i]:""),""),service:x=>x,message:(_k,f)=>f,select:()=>"",bind:()=>{}};
/* Character / Scene / Prop consistency cards (Elements) & Multi-Take Hero selection. */
let editingElementId='';

UI.registerTab({
 id:'elements',
 icon:'✦',
 label:L.text('角色与场景卡'),
 title:L.text('项目角色、场景与道具参考卡'),
 subtitle:L.text('统一锚定跨镜头的人物长相、服装与场景描述；分镜勾选后自动注入提示词并继承参考图。'),
 count:d=>(d?.elements||[]).length||null
},'models');

function elementsView(){
 const elems=data.elements||[];
 const kindLabel={character:L.text('👤 角色'),scene:L.text('🏞 场景'),prop:L.text('📦 道具')};
 if(!elems.length)return L.text('<div class="section-card empty">尚未创建角色或场景参考卡。<br>在右侧填写名称（如“艾伦”、“火星基地”）、固定外观提示词与参考图，即可在所有分镜中一键复用。</div>');
 return `<div class="assets-grid">${elems.map(el=>{
  const img=el.asset_id?asset(el.asset_id):null;
  return `<article class="asset element-card ${editingElementId===el.id?'selected':''}" data-edit-element="${esc(el.id)}">${img?media(img):L.text('<div class="empty" style="height:180px;display:flex;align-items:center;justify-content:center">未绑定参考图</div>')}<div class="caption"><span class="badge" style="margin-bottom:8px">${kindLabel[el.kind]||L.text('✦ 设定')}</span><h3 style="margin:4px 0">@${esc(el.tag)}</h3><p class="note" style="margin:6px 0 0">${esc(el.prompt_snippet||L.text('暂无固定外观描述'))}</p></div></article>`;
 }).join('')}</div>`;
}

function elementsInspector(){
 const readonly=data.project.status==='completed';
 if(readonly)return L.text('<h2>角色与场景卡</h2><p class="note">已结项项目只读。</p>');
 const current=(data.elements||[]).find(e=>e.id===editingElementId);
 const images=(data.assets||[]).filter(a=>a.kind==='image'&&!a.is_qc_strip);
 const audios=(data.assets||[]).filter(a=>a.kind==='audio');
 return L.html`<h2>${current?L.text('编辑参考卡 · @')+esc(current.tag):L.text('新建角色 / 场景参考卡')}</h2>
 <label class="field"><span>类型</span><select id="elem-kind">${[['character',L.text('角色 (Character)')],['scene',L.text('场景 (Scene)')],['prop',L.text('道具 / 载具 (Prop)')]].map(([k,n])=>`<option value="${k}" ${current?.kind===k?'selected':''}>${n}</option>`).join('')}</select></label>
 <label class="field"><span>标识符名称（无需输入 @）</span><input id="elem-tag" placeholder="例如：艾伦、银色越野车" value="${esc(current?.tag||'')}"></label>
 <label class="field"><span>固定一致性外观 / 环境提示词</span><textarea id="elem-snippet" rows="4" placeholder="例如：30岁亚洲男性宇航员，短发，白色磨损宇航服，左肩印有橙色徽章">${esc(current?.prompt_snippet||'')}</textarea></label>
 <label class="field"><span>默认锚定参考图 / 三视图母版（可选）</span><select id="elem-asset"><option value="">不绑定参考图</option>${images.map(a=>`<option value="${esc(a.id)}" ${current?.asset_id===a.id?'selected':''}>${esc(a.name)}</option>`).join('')}</select></label>
 <label class="field"><span>声音描述 · 加入提示词（可选）</span><input id="elem-voice-profile" placeholder="例如：低沉磁性的30岁成年男中音，语速沉稳克制" value="${esc(current?.voice_profile||'')}"></label>
 <label class="field"><span>关联声音参考音轨 · 素材记录（可选）</span><select id="elem-voice-asset"><option value="">未绑定声音参考</option>${audios.map(a=>`<option value="${esc(a.id)}" ${current?.voice_asset_id===a.id?'selected':''}>${esc(a.name)}</option>`).join('')}</select></label>
 <button class="primary" id="elem-save">${current?L.text('保存修改'):L.text('＋ 添加到项目参考库')}</button>
 ${current?L.html`<button id="elem-turnaround" style="width:100%;margin-top:8px">👤 一键生成角色三视图定妆母版（正/侧/背）</button><div class="row" style="margin-top:10px"><button id="elem-reset">新建另一张</button><button class="danger" id="elem-delete">移除此卡</button></div>`:''}
 <p class="note">分镜勾选后会注入外观与声音描述。参考音轨保存在素材库；当前 H3 未接入音频样本条件，不保证跨镜音色一致。点击“生成角色三视图定妆母版”将在 G4 生成正/侧/背同图定妆照并自动回填此卡。</p>`;
}

UI.views.elements=elementsView;
UI.inspectors.elements=elementsInspector;
UI.workspaceHooks.push(()=>{editingElementId=''});

// Shot Inspector integration: Element checkboxes + Multi-Take Gallery
UI.shotExtraFields.push(s=>{
 const elems=data.elements||[];
 if(!elems.length)return '';
 const bound=new Set(s.elements||[]);
 return L.html`<div class="field"><span>关联角色 / 场景卡（一致性锚定）</span><div class="elem-chips">${elems.map(e=>`<label class="elem-chip"><input type="checkbox" style="width:auto" data-shot-elem="${esc(e.id)}" ${bound.has(e.id)?'checked':''}> @${esc(e.tag)}</label>`).join('')}</div><div class="row" style="margin-top:8px"><button type="button" class="ghost" id="derive-kf-start" style="font-size:11.5px;padding:6px 8px">🎭 锁脸派生本镜首帧</button><button type="button" class="ghost" id="derive-kf-end" style="font-size:11.5px;padding:6px 8px">🎯 锁脸派生本镜尾帧</button></div></div>`;
});

UI.shotFooterActions.push(s=>{
 const rawTakes=Array.isArray(s.takes)?s.takes:[];
 const takes=rawTakes.filter(t=>asset(t.asset_id));
 if(takes.length<=1)return '';
 return L.html`<details class="takes-panel" open><summary>候选抽卡挑片（Takes · ${takes.length} 条）</summary><div class="takes-list">${takes.map((t,idx)=>{
  const a=asset(t.asset_id),isHero=s.output===t.asset_id;
  return `<div class="take-card ${isHero?'hero-take':''}"><div class="summary"><small>#${takes.length-idx}${t.seed!=null?' · Seed '+esc(t.seed):''}</small>${isHero?L.text('<span class="badge">★ 当前采用版</span>'):L.html`<button class="primary" style="width:auto;margin:0;padding:4px 10px;font-size:11px" data-select-take="${esc(t.asset_id)}">设为采用版</button>`}</div><div style="margin-top:6px">${media(a,true)}</div></div>`;
 }).join('')}</div></details>`;
});

UI.binders.push(()=>{
 document.querySelectorAll('[data-edit-element]').forEach(card=>card.onclick=()=>{editingElementId=card.dataset.editElement;render()});
 if($('#elem-reset'))$('#elem-reset').onclick=()=>{editingElementId='';render()};
 if($('#elem-save'))$('#elem-save').onclick=()=>action(async()=>{
  const payload={id:editingElementId||undefined,kind:$('#elem-kind').value,tag:$('#elem-tag').value,prompt_snippet:$('#elem-snippet').value,asset_id:$('#elem-asset').value||null,voice_profile:$('#elem-voice-profile')?.value||'',voice_asset_id:$('#elem-voice-asset')?.value||null};
  await api('/api/element',payload);
  data=await api('/api/workspace');editingElementId='';render();toast(L.text('角色/场景参考卡已保存'));
 });
 if($('#elem-turnaround'))$('#elem-turnaround').onclick=()=>action(async()=>{
  if(!editingElementId)return;
  await api('/api/element',{id:editingElementId,kind:$('#elem-kind').value,tag:$('#elem-tag').value,prompt_snippet:$('#elem-snippet').value,asset_id:$('#elem-asset').value||null,voice_profile:$('#elem-voice-profile')?.value||'',voice_asset_id:$('#elem-voice-asset')?.value||null});
  await api('/api/element/turnaround',{element_id:editingElementId});
  data=await api('/api/workspace');tab='jobs';render();
  toast(L.text('已创建角色三视图（正/侧/背）定妆母版任务；在 G4 生成后将自动回填此角色卡'));
 });
 if($('#elem-delete'))$('#elem-delete').onclick=()=>action(async()=>{
  if(!editingElementId||!confirm(L.text('移除此参考卡？已创建的历史任务快照不受影响。')))return;
  await api('/api/element/delete',{id:editingElementId});
  data=await api('/api/workspace');editingElementId='';render();toast(L.text('参考卡已移除'));
 });
 document.querySelectorAll('[data-select-take]').forEach(btn=>btn.onclick=()=>action(async()=>{
  await api('/api/shot/select-take',{shot_id:selected,asset_id:btn.dataset.selectTake});
  data=await api('/api/workspace');render();toast(L.text('已切换当前镜头采用版（粗剪时间线已同步更新）'));
 }));
 for(const [btnId,slot] of [['derive-kf-start','reference'],['derive-kf-end','end_reference']])if($('#'+btnId))$('#'+btnId).onclick=()=>action(async()=>{
  await saveShot();
  await api('/api/shot/derive-keyframe',{shot_id:selected,slot});
  data=await api('/api/workspace');tab='jobs';render();
  toast(slot==='end_reference'?L.text('已创建锁脸尾帧派生任务（生成后自动填入本镜尾帧锁死图）'):L.text('已创建锁脸首帧派生任务（生成后自动填入本镜首帧参考图）'));
 });
});
