/* Character / Scene / Prop consistency cards (Elements) & Multi-Take Hero selection. */
let editingElementId='';

UI.registerTab({
 id:'elements',
 icon:'✦',
 label:'角色与场景卡',
 title:'项目角色、场景与道具参考卡',
 subtitle:'统一锚定跨镜头的人物长相、服装与场景描述；分镜勾选后自动注入提示词并继承参考图。',
 count:d=>(d?.elements||[]).length||null
},'models');

function elementsView(){
 const elems=data.elements||[];
 const kindLabel={character:'👤 角色',scene:'🏞 场景',prop:'📦 道具'};
 if(!elems.length)return '<div class="section-card empty">尚未创建角色或场景参考卡。<br>在右侧填写名称（如“艾伦”、“火星基地”）、固定外观提示词与参考图，即可在所有分镜中一键复用。</div>';
 return `<div class="assets-grid">${elems.map(el=>{
  const img=el.asset_id?asset(el.asset_id):null;
  return `<article class="asset element-card ${editingElementId===el.id?'selected':''}" data-edit-element="${esc(el.id)}">${img?media(img):'<div class="empty" style="height:180px;display:flex;align-items:center;justify-content:center">未绑定参考图</div>'}<div class="caption"><span class="badge" style="margin-bottom:8px">${kindLabel[el.kind]||'✦ 设定'}</span><h3 style="margin:4px 0">@${esc(el.tag)}</h3><p class="note" style="margin:6px 0 0">${esc(el.prompt_snippet||'暂无固定外观描述')}</p></div></article>`;
 }).join('')}</div>`;
}

function elementsInspector(){
 const readonly=data.project.status==='completed';
 if(readonly)return '<h2>角色与场景卡</h2><p class="note">已结项项目只读。</p>';
 const current=(data.elements||[]).find(e=>e.id===editingElementId);
 const images=(data.assets||[]).filter(a=>a.kind==='image');
 return `<h2>${current?'编辑参考卡 · @'+esc(current.tag):'新建角色 / 场景参考卡'}</h2>
 <label class="field"><span>类型</span><select id="elem-kind">${[['character','角色 (Character)'],['scene','场景 (Scene)'],['prop','道具 / 载具 (Prop)']].map(([k,n])=>`<option value="${k}" ${current?.kind===k?'selected':''}>${n}</option>`).join('')}</select></label>
 <label class="field"><span>标识符名称（无需输入 @）</span><input id="elem-tag" placeholder="例如：艾伦、银色越野车" value="${esc(current?.tag||'')}"></label>
 <label class="field"><span>固定一致性外观 / 环境提示词</span><textarea id="elem-snippet" rows="5" placeholder="例如：30岁亚洲男性宇航员，短发，白色磨损宇航服，左肩印有橙色徽章">${esc(current?.prompt_snippet||'')}</textarea></label>
 <label class="field"><span>默认锚定参考图（可选）</span><select id="elem-asset"><option value="">不绑定参考图</option>${images.map(a=>`<option value="${esc(a.id)}" ${current?.asset_id===a.id?'selected':''}>${esc(a.name)}</option>`).join('')}</select></label>
 <button class="primary" id="elem-save">${current?'保存修改':'＋ 添加到项目参考库'}</button>
 ${current?`<div class="row" style="margin-top:10px"><button id="elem-reset">新建另一张</button><button class="danger" id="elem-delete">移除此卡</button></div>`:''}
 <p class="note">在“分镜工作台”勾选关联参考卡后，创建任务快照时会自动拼入上述外观描述；若分镜未单独指定参考图，将自动继承此卡绑定的参考图。</p>`;
}

UI.views.elements=elementsView;
UI.inspectors.elements=elementsInspector;
UI.workspaceHooks.push(()=>{editingElementId=''});

// Shot Inspector integration: Element checkboxes + Multi-Take Gallery
UI.shotExtraFields.push(s=>{
 const elems=data.elements||[];
 if(!elems.length)return '';
 const bound=new Set(s.elements||[]);
 return `<div class="field"><span>关联角色 / 场景卡（一致性锚定）</span><div class="elem-chips">${elems.map(e=>`<label class="elem-chip"><input type="checkbox" style="width:auto" data-shot-elem="${esc(e.id)}" ${bound.has(e.id)?'checked':''}> @${esc(e.tag)}</label>`).join('')}</div></div>`;
});

UI.shotFooterActions.push(s=>{
 const rawTakes=Array.isArray(s.takes)?s.takes:[];
 const takes=rawTakes.filter(t=>asset(t.asset_id));
 if(takes.length<=1)return '';
 return `<details class="takes-panel" open><summary>候选抽卡挑片（Takes · ${takes.length} 条）</summary><div class="takes-list">${takes.map((t,idx)=>{
  const a=asset(t.asset_id),isHero=s.output===t.asset_id;
  return `<div class="take-card ${isHero?'hero-take':''}"><div class="summary"><small>#${takes.length-idx}${t.seed!=null?' · Seed '+esc(t.seed):''}</small>${isHero?'<span class="badge">★ 当前采用版</span>':`<button class="primary" style="width:auto;margin:0;padding:4px 10px;font-size:11px" data-select-take="${esc(t.asset_id)}">设为采用版</button>`}</div><div style="margin-top:6px">${media(a,true)}</div></div>`;
 }).join('')}</div></details>`;
});

UI.binders.push(()=>{
 document.querySelectorAll('[data-edit-element]').forEach(card=>card.onclick=()=>{editingElementId=card.dataset.editElement;render()});
 if($('#elem-reset'))$('#elem-reset').onclick=()=>{editingElementId='';render()};
 if($('#elem-save'))$('#elem-save').onclick=()=>action(async()=>{
  const payload={id:editingElementId||undefined,kind:$('#elem-kind').value,tag:$('#elem-tag').value,prompt_snippet:$('#elem-snippet').value,asset_id:$('#elem-asset').value||null};
  await api('/api/element',payload);
  data=await api('/api/workspace');editingElementId='';render();toast('角色/场景参考卡已保存');
 });
 if($('#elem-delete'))$('#elem-delete').onclick=()=>action(async()=>{
  if(!editingElementId||!confirm('移除此参考卡？已创建的历史任务快照不受影响。'))return;
  await api('/api/element/delete',{id:editingElementId});
  data=await api('/api/workspace');editingElementId='';render();toast('参考卡已移除');
 });
 document.querySelectorAll('[data-select-take]').forEach(btn=>btn.onclick=()=>action(async()=>{
  await api('/api/shot/select-take',{shot_id:selected,asset_id:btn.dataset.selectTake});
  data=await api('/api/workspace');render();toast('已切换当前镜头采用版（粗剪时间线已同步更新）');
 }));
});
