var L=(typeof window!=="undefined"?window:globalThis).GCLabsI18n||{text:x=>x,html:(s,...v)=>s.reduce((a,p,i)=>a+p+(i<v.length?v[i]:""),""),service:x=>x,message:(_k,f)=>f,select:()=>"",bind:()=>{}};
/* Industrial AI Short-Drama Director Toolbar, Script Breakdown, 9-Grid Slicer, Camera Rig Pills & Visual QC Filmstrip. */
let dramaPanelMode='',scriptDraft='',scriptStyle=L.text('电影级实拍 IMAX 35mm 胶片质感，高对比戏剧布光'),scriptReplace=false,gridSceneBrief='',sliceAssetId='',sliceGridDim='3x3';

const BUILTIN_CAMERA_PRESETS=[
 {id:'push_in_ecu',label:L.text('推镜特写'),scale:L.text('近景→大特写'),prompt:'Smooth motorized dolly push-in camera gliding into an intimate expressive facial close-up, shallow 85mm cinema depth of field.'},
 {id:'crane_reveal',label:L.text('大摇臂拉远'),scale:L.text('中景→大远景'),prompt:'Grand sweeping 12m cinema crane-up and pull-back reveal shot unveiling the vast surrounding environment in epic scale.'},
 {id:'whip_orbit_180',label:L.text('180°环绕甩镜'),scale:L.text('中近景环绕'),prompt:'Dynamic 180-degree orbital whip-pan tracking shot swinging smoothly around the subject with dramatic parallax.'},
 {id:'ots_reverse',label:L.text('过肩正反打'),scale:L.text('过肩中近景'),prompt:'Anamorphic 50mm over-the-shoulder dialogue framing with foreground shoulder silhouette and crisp rack-focus onto the speaker.'},
 {id:'handheld_combat',label:L.text('手持搏击'),scale:L.text('贴身动作中景'),prompt:'Visceral kinetic handheld shutter-snap action camera tightly tracking close-quarters movement with raw physical impact.'},
 {id:'fpv_dive',label:L.text('FPV极速俯冲'),scale:L.text('航拍俯冲追拍'),prompt:'High-velocity cinema FPV drone cliff-dive pursuit shot plunging steeply forward and skimming inches past the subject.'},
 {id:'russian_arm',label:L.text('俄罗斯臂追车'),scale:L.text('贴地高速跟拍'),prompt:'Ultra-low-angle Russian-arm gyro-stabilized tracking camera racing at 180 km/h inches above the ground beside the subject.'},
 {id:'dolly_zoom',label:L.text('希区柯克变焦'),scale:L.text('心理悬疑近景'),prompt:'Dramatic Hitchcock dolly-zoom keeping the subject face size constant while the background warps in psychological tension.'},
 {id:'low_orbit',label:L.text('贴地仰拍环绕'),scale:L.text('低角度英雄景'),prompt:'Heroic ultra-low-angle orbital camera skimming near ground level looking up at the subject against dramatic rim lighting.'},
 {id:'macro_slider',label:L.text('超微距滑轨'),scale:L.text('极微距特写'),prompt:'Precision 100mm macro cinema slider shot gliding across intricate surface textures, water droplets, and mechanical micro-details.'},
 {id:'lateral_track',label:L.text('高速横移跟拍'),scale:L.text('侧面全/中景'),prompt:'High-speed lateral dolly tracking shot moving parallel beside the subject through layered foreground silhouettes.'},
 {id:'speed_ramp',label:L.text('升格变速定格'),scale:L.text('动作爆发特写'),prompt:'1000fps Phantom ultra-slow-motion impact transitioning via a sudden speed-ramp snap into a poised hero freeze-frame.'}
];

const SAMPLE_SCRIPT=L.html`【场景】坍缩星门近地轨道 · 燃烧战舰残骸区
【角色】林默：32岁亚洲硬汉星际铁驭，眉骨带淡疤，深灰钛合金外骨骼与透明HUD头盔面罩
1. 驾驶舱红光警报闪烁，林默紧盯前方坍缩的金色星门呼叫：“指挥塔，推进器只剩三成，航道快撑不住了！”
2. 巨型母舰龙骨轰然折断封死航道，林默侧倾闪避咬牙低吼：“来不及绕行了——全功率过载！”
3. 驾驶舱侧面特写，林默右手重重推满蓝色等离子过载杆：“星门还有五秒闭合，抓稳了，硬闯过去！”
4. FPV极速俯冲跟拍林默拖着双道蓝焰冲进金色坍缩星门核心，引力电弧轰鸣炸裂。
5. 穿出星门后的幽蓝深空万籁俱寂，镜头慢推至林默透明面罩正脸大特写：“信标点亮了……地球，听得到吗？”`;

function dramaDirectorToolbar(){
 if(data.project.status==='completed')return '';
 const images=(data.assets||[]).filter(a=>a.kind==='image'&&!a.is_qc_strip);
 if(!sliceAssetId&&images.length)sliceAssetId=images.at(-1).id;
 return L.html`<section class="section-card drama-bar"><div class="summary" style="margin-bottom:${dramaPanelMode?'14px':'0'}"><div><b>故事与分镜</b><small style="display:block;margin-top:3px">剧本拆解 · 角色参考 · 分镜推演 · 字幕与声音</small></div><span class="line"></span>
 <button class="${dramaPanelMode==='script'?'primary':'ghost'}" id="toggle-script-panel">📜 剧本一键拆解分镜</button>
 <button class="${dramaPanelMode==='grid'?'primary':'ghost'}" id="toggle-grid-panel">⊞ 九宫格连贯分镜 & 切图</button>
 <button class="ghost" id="quick-export-sheet">🖼 导出分镜通告单</button></div>
 ${dramaPanelMode==='script'?L.html`<div class="drama-drawer"><div class="row"><label class="field" style="flex:2"><span>全剧视觉美学基调</span><input id="drama-style" value="${esc(scriptStyle)}"></label><label class="field" style="flex:1;display:flex;align-items:flex-end;gap:8px;padding-bottom:8px"><input type="checkbox" id="drama-replace" style="width:auto" ${scriptReplace?'checked':''}> <span>清空现有分镜后重建</span></label><div style="display:flex;align-items:flex-end;padding-bottom:4px"><button class="ghost" id="fill-sample-script">填入示例剧本</button></div></div>
 <label class="field"><span>粘贴分场剧本 / 小说段落 / 故事大纲（支持自动识别【场景】、【角色】与“人物台词”）</span><textarea id="drama-script-input" rows="6" placeholder="粘贴分场剧本或小说段落，每行一镜或一段剧情…">${esc(scriptDraft)}</textarea></label>
 <div class="row"><button class="primary" id="run-script-breakdown">⚡ 一键拆解生成角色卡与分镜画布（本机 0 算力）</button><button class="ghost" id="close-drama-drawer">收起面板</button></div></div>`:''}
 ${dramaPanelMode==='grid'?L.html`<div class="drama-drawer"><div class="row"><div style="flex:1.2"><h4 style="margin:0 0 8px">步骤 A · 生成九宫格连贯分镜母版（云端 Qwen Edit 2511 BF16）</h4><p class="note" style="margin:0 0 8px">自动继承项目 @角色卡 定妆照，在一张大图内推演 9 个连续机位；角色与光影一致性需检查生成结果。</p><input id="grid-scene-brief" placeholder="输入本场戏核心情节（留空则自动汇总当前前9镜剧情）" value="${esc(gridSceneBrief)}"><button class="primary" id="create-nine-grid-job" style="width:100%;margin-top:10px">⊞ 创建九宫格连贯分镜生成任务</button></div>
 <div style="flex:1;border-left:1px solid var(--edge);padding-left:16px"><h4 style="margin:0 0 8px">步骤 B · 本机宫格切分上画布（0 算力）</h4><p class="note" style="margin:0 0 8px">选择任意已生成的九宫格（3×3）或四宫格（2×2）大图，自动去边框裁切并填入分镜画布。</p><div class="row"><select id="slice-asset-select">${images.map(a=>`<option value="${esc(a.id)}" ${a.id===sliceAssetId?'selected':''}>${esc(a.name)}</option>`).join('')||L.text('<option value="">暂无图像素材</option>')}</select><select id="slice-dim-select" style="max-width:115px"><option value="3x3" ${sliceGridDim==='3x3'?'selected':''}>3×3 九宫格</option><option value="2x2" ${sliceGridDim==='2x2'?'selected':''}>2×2 四宫格</option></select></div><button class="primary" id="run-slice-grid" style="width:100%;margin-top:10px" ${!images.length?'disabled':''}>✂️ 一键切分为独立分镜镜头</button></div></div></div>`:''}
 </section>`;
}

const prevShotsDecorator=UI.viewDecorators.shots;
UI.viewDecorators.shots=html=>dramaDirectorToolbar()+(prevShotsDecorator?prevShotsDecorator(html):html);

// Shot Inspector: Dialogue + Bilingual Subtitle + 12 Cinema Camera Rig Pills
UI.shotExtraFields.push(s=>{
 return L.html`<div class="field"><span>人物台词 · 同步生成对白并加入字幕</span><input id="dialogue" placeholder="例如：星门还有五秒闭合，抓稳了，硬闯过去！" value="${esc(s.dialogue||'')}"></div>
 <div class="field"><span>英文副字幕 · 可选</span><input id="subtitle_en" placeholder="Optional English subtitle line..." value="${esc(s.subtitle_en||'')}"></div>
 <details class="camera-settings"><summary>运镜方式 · 可选</summary><div class="cam-pills">${BUILTIN_CAMERA_PRESETS.map(c=>`<button type="button" class="cam-pill ${s.camera_move===c.id?'active':''}" data-cam-preset="${esc(c.id)}" title="${esc(c.scale+' · '+c.prompt)}">${esc(c.label)}</button>`).join('')}</div></details>`;
});

// Shot Footer: 4-Frame Visual QC Filmstrip & Extract Voice Timbre to @Character
UI.shotFooterActions.push(s=>{
 const outAsset=s.output?asset(s.output):null;
 if(outAsset?.kind!=='video')return '';
 const hasChar=(s.elements||[]).some(eid=>(data.elements||[]).some(e=>e.id===eid&&e.kind==='character'));
 return L.html`<div class="qc-panel"><div class="summary" style="margin-bottom:8px"><small style="color:var(--gold);font-weight:700">画面检查与角色声音</small><div style="display:flex;gap:6px"><button type="button" class="ghost" id="btn-qc-strip" style="font-size:11px;padding:4px 8px">↻ 刷新四格抽帧</button>${hasChar?L.html`<button type="button" class="ghost" id="btn-lock-voice" style="font-size:11px;padding:4px 8px">🎙 保存角色声音参考</button>`:''}</div></div>${s.qc_strip_file?L.html`<img src="/assets/${encodeURIComponent(s.qc_strip_file)}" alt="四格抽帧质检条" style="width:100%;border-radius:7px;border:1px solid var(--edge)">`:L.text('<small class="muted">点击“刷新四格抽帧”提取首/中/尾四帧胶片条，一眼核验五官一致性与背景文字。</small>')}</div>`;
});

UI.binders.push(()=>{
 if($('#toggle-script-panel'))$('#toggle-script-panel').onclick=()=>{dramaPanelMode=dramaPanelMode==='script'?'':'script';render()};
 if($('#toggle-grid-panel'))$('#toggle-grid-panel').onclick=()=>{dramaPanelMode=dramaPanelMode==='grid'?'':'grid';render()};
 if($('#close-drama-drawer'))$('#close-drama-drawer').onclick=()=>{dramaPanelMode='';render()};
 if($('#drama-style'))$('#drama-style').oninput=()=>{scriptStyle=$('#drama-style').value};
 if($('#drama-replace'))$('#drama-replace').onchange=()=>{scriptReplace=$('#drama-replace').checked};
 if($('#drama-script-input'))$('#drama-script-input').oninput=()=>{scriptDraft=$('#drama-script-input').value};
 if($('#fill-sample-script'))$('#fill-sample-script').onclick=()=>{scriptDraft=SAMPLE_SCRIPT;render()};
 if($('#run-script-breakdown'))$('#run-script-breakdown').onclick=()=>action(async()=>{
  const res=await api('/api/script/breakdown',{script:scriptDraft,style:scriptStyle,replace_shots:scriptReplace});
  data=await api('/api/workspace');selected=data.shots[0]?.id;dramaPanelMode='';render();
  toast(L.html`已拆解生成 ${res.created_shots} 个分镜镜头与 ${res.created_elements} 张角色/场景卡`);
 });
 if($('#grid-scene-brief'))$('#grid-scene-brief').oninput=()=>{gridSceneBrief=$('#grid-scene-brief').value};
 if($('#create-nine-grid-job'))$('#create-nine-grid-job').onclick=()=>action(async()=>{
  await api('/api/drama/nine-grid',{scene_brief:gridSceneBrief});
  data=await api('/api/workspace');dramaPanelMode='';tab='jobs';render();
  toast(L.text('已创建九宫格连贯分镜推演任务；在 G4 生成后可一键切分为 9 个独立镜头'));
 });
 if($('#slice-asset-select'))$('#slice-asset-select').onchange=()=>{sliceAssetId=$('#slice-asset-select').value};
 if($('#slice-dim-select'))$('#slice-dim-select').onchange=()=>{sliceGridDim=$('#slice-dim-select').value};
 if($('#run-slice-grid'))$('#run-slice-grid').onclick=()=>action(async()=>{
  const [r,c]=sliceGridDim.split('x').map(Number);
  const res=await api('/api/drama/slice-grid',{asset_id:sliceAssetId,rows:r,cols:c});
  data=await api('/api/workspace');selected=res.shots?.[0]||data.shots[0]?.id;dramaPanelMode='';render();
  toast(L.html`已在本机 0 算力切出 ${res.count} 张高清分镜图并自动排入分镜画布`);
 });
 if($('#quick-export-sheet'))$('#quick-export-sheet').onclick=()=>action(async()=>{
  const res=await api('/api/assembly/storyboard-sheet',{});
  const a=document.createElement('a');a.href=res.url;a.download=res.file;a.click();
  toast(L.html`已导出高清《导演分镜通告单》：${res.file}`);
 });
 document.querySelectorAll('[data-cam-preset]').forEach(btn=>btn.onclick=()=>{
  const preset=BUILTIN_CAMERA_PRESETS.find(x=>x.id===btn.dataset.camPreset);
  if(!preset)return;
  const s=(data.shots||[]).find(x=>x.id===selected);
  if(s){s.camera_move=preset.id;s.shot_scale=preset.scale}
  const pEl=$('#prompt');
  if(pEl&&!pEl.value.includes(preset.prompt))pEl.value=(preset.prompt+' '+pEl.value).trim();
  document.querySelectorAll('[data-cam-preset]').forEach(b=>b.classList.toggle('active',b===btn));
  toast(L.html`已注入「${preset.label}」摄影机调度指令`);
 });
 if($('#btn-qc-strip'))$('#btn-qc-strip').onclick=()=>action(async()=>{
  await api('/api/shot/qc-filmstrip',{shot_id:selected});
  data=await api('/api/workspace');render();toast(L.text('已生成本镜首/中/尾四格胶片质检条'));
 });
 if($('#btn-lock-voice'))$('#btn-lock-voice').onclick=()=>action(async()=>{
  const res=await api('/api/element/extract-voice',{shot_id:selected});
  data=await api('/api/workspace');render();toast(L.html`已保存本镜音轨，绑定为 @${res.element.tag} 的声音参考`);
 });
});
