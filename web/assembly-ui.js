var L=(typeof window!=="undefined"?window:globalThis).GCLabsI18n||{text:x=>x,html:(s,...v)=>s.reduce((a,p,i)=>a+p+(i<v.length?v[i]:""),""),service:x=>x,message:(_k,f)=>f,select:()=>"",bind:()=>{}};
/* Multi-track rough-cut preview, native AVFoundation MP4 assembly (with bilingual subtitles, ducking & 9:16 reframe), SRT, Storyboard Sheet, FCPXML & CapCut draft export. */
let assemblyPlan=null,assemblyEdits={},assemblyAudioId='',assemblyAudioStart=0,assemblyTargetAspect='auto',assemblyBurnSubs=true,assemblyDucking=true,assemblyLoading=false,assemblyBusy=false,assemblyLastExport=null,assemblyPlayingIdx=0;
let assemblySettingsLoaded=false,assemblySubtitles=null;

UI.registerTab({
 id:'assembly',
 icon:'▤',
 label:L.text('粗剪与交付'),
 title:L.text('剪辑与交付'),
 subtitle:L.text('按镜头顺序联播预览、按对白字幕降低配乐音量、烧录双语影院字幕，本机导出 MP4 / SRT / 分镜单 / Final Cut / 剪映草稿。'),
 count:d=>(d?.shots||[]).filter(s=>s.output&&asset(s.output)?.kind==='video').length||null
});

UI.workspaceHooks.push(()=>{assemblyPlan=null;assemblyEdits={};assemblyLastExport=null;assemblyPlayingIdx=0;assemblyAudioId='';assemblyAudioStart=0;assemblyTargetAspect='auto';assemblyBurnSubs=true;assemblyDucking=true;assemblySettingsLoaded=false;assemblySubtitles=null});

async function loadAssemblyPlan(force=false){
 if(assemblyLoading||(assemblyPlan&&!force))return;
 assemblyLoading=true;
 try{
  assemblyPlan=await api('/api/assembly/plan');
  if(!assemblySettingsLoaded){
   const saved=assemblyPlan.settings;
   if(saved){
    assemblyEdits=Object.fromEntries((saved.clips||[]).map(c=>[c.shot_id,{...c}]));
    assemblyAudioId=saved.audio_asset_id||'';assemblyAudioStart=saved.audio_start||0;assemblyTargetAspect=saved.target_aspect||'auto';
    assemblyBurnSubs=saved.burn_subtitles===true;assemblyDucking=saved.ducking===true;assemblySubtitles=Array.isArray(saved.subtitles)?saved.subtitles:null;
   }else{
    assemblyTargetAspect=['16:9','9:16'].includes(data?.project?.ratio)?data.project.ratio:'auto';
   }
   assemblySettingsLoaded=true;
  }
  for(const s of assemblyPlan.shots||[]){
   if(!assemblyEdits[s.shot_id]){
    assemblyEdits[s.shot_id]={enabled:true,start:0,end:s.duration,mute_source_audio:false,dialogue:s.dialogue||'',subtitle_en:s.subtitle_en||''};
   }
  }
  if(!assemblyAudioId&&!assemblyPlan.settings&&assemblyPlan.audios?.length)assemblyAudioId=assemblyPlan.audios[0].asset_id;
  if(tab==='assembly')render();
 }catch(e){toast(L.text('读取粗剪时间线失败：')+e.message)}finally{assemblyLoading=false}
}

function currentAssemblyPayload(){
 const clips=(assemblyPlan?.shots||[]).map(s=>{
  const ed=assemblyEdits[s.shot_id]||{enabled:true,start:0,end:s.duration,mute_source_audio:false,dialogue:s.dialogue||'',subtitle_en:s.subtitle_en||''};
  return {
   shot_id:s.shot_id,
   asset_id:s.asset_id,
   enabled:ed.enabled!==false,
   start:Number(ed.start)||0,
   end:Number(ed.end)||s.duration,
   mute_source_audio:!!ed.mute_source_audio,
   dialogue:ed.dialogue??s.dialogue??'',
   subtitle_en:ed.subtitle_en??s.subtitle_en??''
  };
 });
 return {
  clips,
  audio_asset_id:assemblyAudioId||null,
  audio_start:Number(assemblyAudioStart)||0,
  target_aspect:assemblyTargetAspect,
  burn_subtitles:!!assemblyBurnSubs,
  ducking:!!assemblyDucking,
  ...(assemblySubtitles?{subtitles:assemblySubtitles}:{})
 };
}

function assemblySummary(){
 const shots=assemblyPlan?.shots||[],enabled=shots.filter(s=>assemblyEdits[s.shot_id]?.enabled!==false);
 const seconds=enabled.reduce((sum,s)=>{const ed=assemblyEdits[s.shot_id]||{};return sum+Math.max(0,(Number(ed.end)||s.duration)-(Number(ed.start)||0))},0);
 return L.message('assembly.summary','Enabled {enabled} / {total} video clips · Estimated duration {seconds} s').replace('{enabled}',enabled.length).replace('{total}',shots.length).replace('{seconds}',seconds.toFixed(2));
}
function updateAssemblySummary(){const counter=$('#assembly-total');if(counter)counter.textContent=assemblySummary()}

function assemblyView(){
 if(!assemblyPlan&&!assemblyLoading){setTimeout(()=>loadAssemblyPlan(true),10);return L.text('<div class="section-card empty">正在使用本机 AVFoundation 探测分镜视频时长与轨道信息…</div>')}
 if(assemblyLoading&&!assemblyPlan)return L.text('<div class="section-card empty">正在读取分镜与音轨元数据…</div>');
 const shots=assemblyPlan?.shots||[];
 const audios=assemblyPlan?.audios||[];
 const enabledShots=shots.filter(s=>(assemblyEdits[s.shot_id]?.enabled??true));
 const totalSec=enabledShots.reduce((sum,s)=>{
  const ed=assemblyEdits[s.shot_id]||{start:0,end:s.duration};
  return sum+Math.max(0,(Number(ed.end)||s.duration)-(Number(ed.start)||0));
 },0);
 const activeClip=enabledShots[Math.min(assemblyPlayingIdx,Math.max(0,enabledShots.length-1))]||shots[0];
 const selectedAudio=audios.find(a=>a.asset_id===assemblyAudioId);

 return L.html`${assemblyPlan?.final_file?L.html`<section class="section-card"><div class="summary"><h3>项目归档交付成片</h3><span class="badge">已验收归档</span></div><div class="result-preview"><video controls preload="metadata" src="/api/project/final-media"></video></div></section>`:''}
 <section class="section-card"><div class="summary"><div><h3>粗剪序列联播预览</h3><small id="assembly-total">${assemblySummary()}</small></div><span class="line"></span><button id="assembly-save" ${data?.project?.status==='completed'?'disabled':''}>保存剪辑设置</button><button id="assembly-refresh">↻ 重新探测轨道</button></div><p class="note">保存后，入出点、配乐与导出选项随工程及备份保留。联播使用原片预览；画幅、字幕和配乐闪避以合成 MP4 为准。</p>
 ${activeClip?L.html`<div class="assembly-stage"><video id="assembly-player" controls preload="metadata" src="/assets/${encodeURIComponent(activeClip.file)}"></video>${selectedAudio?`<audio id="assembly-bgm" src="/assets/${encodeURIComponent(selectedAudio.file)}"></audio>`:''}<div class="assembly-controls"><button id="assembly-play-all" class="primary">▶ 从头联播预览${selectedAudio?L.text('（含配乐同步）'):''}</button><span id="assembly-current" class="muted">当前预览：${esc(activeClip.title)}（${activeClip.width}×${activeClip.height} · ${Math.round(activeClip.fps)}fps）</span></div></div>`:L.text('<div class="empty">当前项目还没有已生成的视频样片。完成分镜生成后即可在此粗剪与导出。</div>')}
 </section>
 ${shots.length?L.html`<section class="section-card"><h3>视频与对白字幕主轨道（跟随分镜顺序）</h3><div class="assembly-track">${shots.map((s,idx)=>{
  const ed=assemblyEdits[s.shot_id]||{enabled:true,start:0,end:s.duration,mute_source_audio:false,dialogue:s.dialogue||'',subtitle_en:s.subtitle_en||''};
  return L.html`<div class="assembly-clip ${ed.enabled!==false?'':'muted-clip'}"><div class="summary"><label style="display:flex;align-items:center;gap:8px"><input type="checkbox" style="width:auto" data-asm-enable="${esc(s.shot_id)}" ${ed.enabled!==false?'checked':''}> <b>#${idx+1} ${esc(s.title)}</b></label><small>${s.width}×${s.height} · 原始 ${s.duration.toFixed(2)}s</small><button class="ghost" data-asm-preview="${idx}">预览此镜</button></div><div class="row" style="margin-top:8px"><label class="field" style="margin:0"><span>入点 (秒)</span><input type="number" step="0.1" min="0" max="${s.duration}" data-asm-start="${esc(s.shot_id)}" value="${ed.start}"></label><label class="field" style="margin:0"><span>出点 (秒)</span><input type="number" step="0.1" min="0.1" max="${s.duration}" data-asm-end="${esc(s.shot_id)}" value="${ed.end}"></label><label class="field" style="margin:0"><span>原片音轨</span><select data-asm-mute="${esc(s.shot_id)}"><option value="false" ${!ed.mute_source_audio?'selected':''}>保留对白/拟音</option><option value="true" ${ed.mute_source_audio?'selected':''}>静音原声</option></select></label></div><div class="row" style="margin-top:8px"><label class="field" style="margin:0"><span>${L.message('assembly.primarySubtitle','Primary subtitle / Dialogue')}</span><input data-asm-zh="${esc(s.shot_id)}" placeholder="填写此镜压制字幕…" value="${esc(ed.dialogue??s.dialogue??'')}"></label><label class="field" style="margin:0"><span>英文双语副字幕（可选）</span><input data-asm-en="${esc(s.shot_id)}" placeholder="Optional English subtitle…" value="${esc(ed.subtitle_en??s.subtitle_en??'')}"></label></div></div>`;
 }).join('')}</div></section>`:''}`;
}

function assemblyInspector(){
 const audios=assemblyPlan?.audios||[];
 const hasVideo=(assemblyPlan?.shots||[]).some(s=>(assemblyEdits[s.shot_id]?.enabled??true));
 const hasShots=(data?.shots||[]).length>0;
 return L.html`<h2>导出设置</h2>
 <label class="field"><span>叠加背景配乐音轨</span><select id="assembly-audio"><option value="">不叠加外部配乐</option>${audios.map(a=>`<option value="${esc(a.asset_id)}" ${a.asset_id===assemblyAudioId?'selected':''}>${esc(a.name)} (${a.duration.toFixed(1)}s)</option>`).join('')}</select></label>
 <div class="row"><label class="field"><span>配乐起始偏移(秒)</span><input id="assembly-audio-start" type="number" min="0" step="0.1" value="${assemblyAudioStart}"></label><label class="field"><span>输出画幅构图</span><select id="assembly-aspect"><option value="auto" ${assemblyTargetAspect==='auto'?'selected':''}>原片画幅</option><option value="16:9" ${assemblyTargetAspect==='16:9'?'selected':''}>16:9 横屏影院 · 1920×1080</option><option value="9:16" ${assemblyTargetAspect==='9:16'?'selected':''}>9:16 竖屏短剧 · 1080×1920</option></select></label></div>
 <label class="elem-chip" style="width:100%;margin-top:4px"><input type="checkbox" id="assembly-burn-subs" style="width:auto" ${assemblyBurnSubs?'checked':''}> ${L.message('assembly.burnSubtitles','Burn in subtitles')}</label>
 <label class="elem-chip" style="width:100%;margin-top:8px"><input type="checkbox" id="assembly-ducking" style="width:auto" ${assemblyDucking?'checked':''}> 按对白字幕区间降低背景配乐</label>
 <hr style="border:0;border-top:1px solid var(--edge);margin:18px 0">
 <p class="note">本机合成，无需启动 GPU。若 Colab GPU 仍保持连接，其会话费用继续累计。</p>
 <button class="primary" id="export-rough-mp4" ${!hasVideo||assemblyBusy?'disabled':''}>${assemblyBusy?L.message('export.rendering','Exporting…'):L.message('export.mp4','Export MP4')}</button>
 <button id="export-srt" style="width:100%;margin-top:9px" ${!hasVideo||assemblyBusy?'disabled':''}>📝 导出标准时间轴字幕 (.SRT)</button>
 <button id="export-storyboard-sheet" style="width:100%;margin-top:9px" ${!hasShots||assemblyBusy?'disabled':''}>🖼 导出导演分镜通告单 (.PNG)</button>
 <button id="export-fcpxml" style="width:100%;margin-top:9px" ${!hasVideo||assemblyBusy?'disabled':''}>🎞 导出 Final Cut / 达芬奇 FCPXML</button>
 <button id="export-capcut" style="width:100%;margin-top:9px" ${!hasVideo||assemblyBusy?'disabled':''}>✂️ 导出剪映草稿包（含字幕轨 .zip）</button>
 <p class="note">画幅、烧录字幕和配乐闪避应用于 MP4。FCPXML 保留镜序、裁剪与独立音轨，字幕另导出 SRT；剪映包包含字幕轨，需核对客户端版本兼容性。</p>
 ${assemblyLastExport?L.html`<div class="section-card" style="margin-top:16px;padding:14px"><b>最近导出已完成</b><p class="note" style="margin:6px 0">${esc(assemblyLastExport.file)} (${(assemblyLastExport.bytes/1024/1024).toFixed(2)} MiB)</p><a class="inline-link" href="${esc(assemblyLastExport.url)}" download="${esc(assemblyLastExport.file)}">点击下载到本地 ↗</a></div>`:''}`;
}

UI.views.assembly=assemblyView;
UI.inspectors.assembly=assemblyInspector;

async function triggerAssemblyExport(endpoint,label){
 if(assemblyBusy)return;
 const originProject=data?.project?.id;
 assemblyBusy=true;render();
 try{
  const payload=currentAssemblyPayload();
  if(data?.project?.status!=='completed')await api('/api/assembly/settings',payload);
  const res=await api(endpoint,payload);
  const current=await api('/api/workspace').catch(()=>null);
  if(data?.project?.id===originProject){
   if(current?.project?.id===originProject)data=current;
   assemblyLastExport=res;
  }
  const a=document.createElement('a');a.href=res.url;a.download=res.file;a.click();
  toast(L.html`${label}已生成：${res.file}`);
 }catch(e){toast(e.message)}finally{assemblyBusy=false;render()}
}

UI.binders.push(()=>{
 if(tab!=='assembly')return;
 if($('#assembly-save'))$('#assembly-save').onclick=()=>action(async()=>{await api('/api/assembly/settings',currentAssemblyPayload());toast(L.text('剪辑设置已保存到本机工程'))});
 if($('#assembly-refresh'))$('#assembly-refresh').onclick=()=>loadAssemblyPlan(true);
 if($('#assembly-audio'))$('#assembly-audio').onchange=()=>{assemblyAudioId=$('#assembly-audio').value;render()};
 if($('#assembly-audio-start'))$('#assembly-audio-start').oninput=()=>{assemblyAudioStart=Math.max(0,Number($('#assembly-audio-start').value)||0)};
 if($('#assembly-aspect'))$('#assembly-aspect').onchange=()=>{assemblyTargetAspect=$('#assembly-aspect').value};
 if($('#assembly-burn-subs'))$('#assembly-burn-subs').onchange=()=>{assemblyBurnSubs=$('#assembly-burn-subs').checked};
 if($('#assembly-ducking'))$('#assembly-ducking').onchange=()=>{assemblyDucking=$('#assembly-ducking').checked};
 document.querySelectorAll('[data-asm-enable]').forEach(el=>el.onchange=()=>{
  const id=el.dataset.asmEnable;assemblySubtitles=null;assemblyEdits[id]??={};assemblyEdits[id].enabled=el.checked;render();
 });
 document.querySelectorAll('[data-asm-start]').forEach(el=>el.oninput=()=>{
  const id=el.dataset.asmStart;assemblySubtitles=null;assemblyEdits[id]??={};assemblyEdits[id].start=Math.max(0,Number(el.value)||0);updateAssemblySummary();
 });
 document.querySelectorAll('[data-asm-end]').forEach(el=>el.oninput=()=>{
  const id=el.dataset.asmEnd;assemblySubtitles=null;assemblyEdits[id]??={};assemblyEdits[id].end=Math.max(0.1,Number(el.value)||0.1);updateAssemblySummary();
 });
 document.querySelectorAll('[data-asm-mute]').forEach(el=>el.onchange=()=>{
  const id=el.dataset.asmMute;assemblyEdits[id]??={};assemblyEdits[id].mute_source_audio=el.value==='true';
 });
 document.querySelectorAll('[data-asm-zh]').forEach(el=>el.oninput=()=>{
  const id=el.dataset.asmZh;assemblySubtitles=null;assemblyEdits[id]??={};assemblyEdits[id].dialogue=el.value;
 });
 document.querySelectorAll('[data-asm-en]').forEach(el=>el.oninput=()=>{
  const id=el.dataset.asmEn;assemblySubtitles=null;assemblyEdits[id]??={};assemblyEdits[id].subtitle_en=el.value;
 });
 document.querySelectorAll('[data-asm-preview]').forEach(btn=>btn.onclick=()=>{
  const enabledShots=(assemblyPlan?.shots||[]).filter(s=>(assemblyEdits[s.shot_id]?.enabled??true));
  const targetShot=(assemblyPlan?.shots||[])[Number(btn.dataset.asmPreview)];
  const idx=enabledShots.findIndex(s=>s.shot_id===targetShot?.shot_id);
  if(idx>=0){assemblyPlayingIdx=idx;render()}
 });
 if($('#assembly-play-all'))$('#assembly-play-all').onclick=()=>{
  const enabledShots=(assemblyPlan?.shots||[]).filter(s=>(assemblyEdits[s.shot_id]?.enabled??true));
  if(!enabledShots.length)return;
  const v=$('#assembly-player'),bgm=$('#assembly-bgm');
  const playClip=i=>{
   v.pause();v.ontimeupdate=null;v.onended=null;
   if(i>=enabledShots.length){if(bgm)bgm.pause();return}
   assemblyPlayingIdx=i;
   const s=enabledShots[i],ed=assemblyEdits[s.shot_id]||{start:0,end:s.duration};
   const label=$('#assembly-current');if(label)label.textContent=L.text('当前预览：')+s.title+' ('+s.width+'×'+s.height+' · '+Math.round(s.fps)+'fps)';
   v.src='/assets/'+encodeURIComponent(s.file);
   v.muted=!!ed.mute_source_audio;
   v.onloadedmetadata=()=>{v.currentTime=Number(ed.start)||0;v.play().catch(()=>{})};
   v.ontimeupdate=()=>{if(v.currentTime>=(Number(ed.end)||s.duration)){v.ontimeupdate=null;playClip(i+1)}};
   v.onended=()=>{v.ontimeupdate=null;playClip(i+1)};
  };
  if(bgm){bgm.currentTime=Number(assemblyAudioStart)||0;bgm.volume=0.36;bgm.play().catch(()=>{})}
  playClip(0);
 };
 if($('#export-rough-mp4'))$('#export-rough-mp4').onclick=()=>triggerAssemblyExport('/api/assembly/render',L.text('MP4 成片'));
 if($('#export-srt'))$('#export-srt').onclick=()=>triggerAssemblyExport('/api/assembly/srt',L.text('标准 SRT 字幕文件'));
 if($('#export-storyboard-sheet'))$('#export-storyboard-sheet').onclick=()=>triggerAssemblyExport('/api/assembly/storyboard-sheet',L.text('导演分镜通告单'));
 if($('#export-fcpxml'))$('#export-fcpxml').onclick=()=>triggerAssemblyExport('/api/assembly/fcpxml',L.text('FCPXML 时间线'));
 if($('#export-capcut'))$('#export-capcut').onclick=()=>triggerAssemblyExport('/api/assembly/capcut',L.text('剪映草稿包'));
});
