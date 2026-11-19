/* Multi-track rough-cut preview, native AVFoundation MP4 assembly, FCPXML & CapCut draft export. */
let assemblyPlan=null,assemblyEdits={},assemblyAudioId='',assemblyAudioStart=0,assemblyLoading=false,assemblyBusy=false,assemblyLastExport=null,assemblyPlayingIdx=0;

UI.registerTab({
 id:'assembly',
 icon:'▤',
 label:'粗剪与交付',
 title:'多轨粗剪与交付导出',
 subtitle:'按镜头顺序联播预览、对齐配乐/配音，本机零算力合成 MP4 或导出 Final Cut / 剪映时间线草稿。',
 count:d=>(d?.shots||[]).filter(s=>s.output&&asset(s.output)?.kind==='video').length||null
});

UI.workspaceHooks.push(()=>{assemblyPlan=null;assemblyEdits={};assemblyLastExport=null;assemblyPlayingIdx=0});

async function loadAssemblyPlan(force=false){
 if(assemblyLoading||(assemblyPlan&&!force))return;
 assemblyLoading=true;
 try{
  assemblyPlan=await api('/api/assembly/plan');
  for(const s of assemblyPlan.shots||[]){
   if(!assemblyEdits[s.shot_id])assemblyEdits[s.shot_id]={enabled:true,start:0,end:s.duration,mute_source_audio:false};
  }
  if(!assemblyAudioId&&assemblyPlan.audios?.length)assemblyAudioId=assemblyPlan.audios[0].asset_id;
  if(tab==='assembly')render();
 }catch(e){toast('读取粗剪时间线失败：'+e.message)}finally{assemblyLoading=false}
}

function currentAssemblyPayload(){
 const clips=(assemblyPlan?.shots||[]).map(s=>{
  const ed=assemblyEdits[s.shot_id]||{enabled:true,start:0,end:s.duration,mute_source_audio:false};
  return {shot_id:s.shot_id,asset_id:s.asset_id,enabled:ed.enabled!==false,start:Number(ed.start)||0,end:Number(ed.end)||s.duration,mute_source_audio:!!ed.mute_source_audio};
 });
 return {clips,audio_asset_id:assemblyAudioId||null,audio_start:Number(assemblyAudioStart)||0};
}

function assemblyView(){
 if(!assemblyPlan&&!assemblyLoading){setTimeout(()=>loadAssemblyPlan(true),10);return '<div class="section-card empty">正在使用本机 AVFoundation 探测分镜视频时长与轨道信息…</div>'}
 if(assemblyLoading&&!assemblyPlan)return '<div class="section-card empty">正在读取分镜与音轨元数据…</div>';
 const shots=assemblyPlan?.shots||[];
 const audios=assemblyPlan?.audios||[];
 const enabledShots=shots.filter(s=>(assemblyEdits[s.shot_id]?.enabled??true));
 const totalSec=enabledShots.reduce((sum,s)=>{
  const ed=assemblyEdits[s.shot_id]||{start:0,end:s.duration};
  return sum+Math.max(0,(Number(ed.end)||s.duration)-(Number(ed.start)||0));
 },0);
 const activeClip=enabledShots[Math.min(assemblyPlayingIdx,Math.max(0,enabledShots.length-1))]||shots[0];
 const selectedAudio=audios.find(a=>a.asset_id===assemblyAudioId);

 return `${assemblyPlan?.final_file?`<section class="section-card"><div class="summary"><h3>项目归档交付成片</h3><span class="badge">已验收归档</span></div><div class="result-preview"><video controls preload="metadata" src="/api/project/final-media"></video></div></section>`:''}
 <section class="section-card"><div class="summary"><div><h3>粗剪序列联播预览</h3><small>已启用 ${enabledShots.length} / ${shots.length} 个视频镜头 · 预计成片总长 ${totalSec.toFixed(2)} 秒</small></div><span class="line"></span><button id="assembly-refresh">↻ 重新探测轨道</button></div>
 ${activeClip?`<div class="assembly-stage"><video id="assembly-player" controls preload="metadata" src="/assets/${encodeURIComponent(activeClip.file)}"></video>${selectedAudio?`<audio id="assembly-bgm" src="/assets/${encodeURIComponent(selectedAudio.file)}"></audio>`:''}<div class="assembly-controls"><button id="assembly-play-all" class="primary">▶ 从头联播预览${selectedAudio?'（含配乐同步）':''}</button><span class="muted">当前预览：${esc(activeClip.title)}（${activeClip.width}×${activeClip.height} · ${Math.round(activeClip.fps)}fps）</span></div></div>`:'<div class="empty">当前项目还没有已生成的视频样片。完成分镜生成后即可在此粗剪与导出。</div>'}
 </section>
 ${shots.length?`<section class="section-card"><h3>视频主轨道（跟随分镜顺序）</h3><div class="assembly-track">${shots.map((s,idx)=>{
  const ed=assemblyEdits[s.shot_id]||{enabled:true,start:0,end:s.duration,mute_source_audio:false};
  return `<div class="assembly-clip ${ed.enabled!==false?'':'muted-clip'}"><div class="summary"><label style="display:flex;align-items:center;gap:8px"><input type="checkbox" style="width:auto" data-asm-enable="${esc(s.shot_id)}" ${ed.enabled!==false?'checked':''}> <b>#${idx+1} ${esc(s.title)}</b></label><small>${s.width}×${s.height} · 原始 ${s.duration.toFixed(2)}s</small><button class="ghost" data-asm-preview="${idx}">预览此镜</button></div><div class="row" style="margin-top:8px"><label class="field" style="margin:0"><span>入点 (秒)</span><input type="number" step="0.1" min="0" max="${s.duration}" data-asm-start="${esc(s.shot_id)}" value="${ed.start}"></label><label class="field" style="margin:0"><span>出点 (秒)</span><input type="number" step="0.1" min="0.1" max="${s.duration}" data-asm-end="${esc(s.shot_id)}" value="${ed.end}"></label><label class="field" style="margin:0"><span>原片音轨</span><select data-asm-mute="${esc(s.shot_id)}"><option value="false" ${!ed.mute_source_audio?'selected':''}>保留原声</option><option value="true" ${ed.mute_source_audio?'selected':''}>静音原声</option></select></label></div></div>`;
 }).join('')}</div></section>`:''}`;
}

function assemblyInspector(){
 const audios=assemblyPlan?.audios||[];
 const hasVideo=(assemblyPlan?.shots||[]).some(s=>(assemblyEdits[s.shot_id]?.enabled??true));
 return `<h2>音轨与交付导出</h2>
 <label class="field"><span>叠加配乐 / 配音音轨</span><select id="assembly-audio"><option value="">不叠加外部音频</option>${audios.map(a=>`<option value="${esc(a.asset_id)}" ${a.asset_id===assemblyAudioId?'selected':''}>${esc(a.name)} (${a.duration.toFixed(1)}s)</option>`).join('')}</select></label>
 <label class="field"><span>音频起始偏移 / 秒</span><input id="assembly-audio-start" type="number" min="0" step="0.1" value="${assemblyAudioStart}"></label>
 <hr style="border:0;border-top:1px solid var(--edge);margin:20px 0">
 <p class="note">以下导出均由本机 Apple Silicon 硬件引擎完成，<b>零云端算力消耗</b>：</p>
 <button class="primary" id="export-rough-mp4" ${!hasVideo||assemblyBusy?'disabled':''}>${assemblyBusy?'正在合成处理…':'🎬 合成粗剪 MP4 成片'}</button>
 <button class="primary" id="export-fcpxml" style="margin-top:10px;background:#2a2c38;color:var(--text);border-color:#4b4e62" ${!hasVideo||assemblyBusy?'disabled':''}>🎞 导出 Final Cut / 达芬奇 FCPXML</button>
 <button class="primary" id="export-capcut" style="margin-top:10px;background:#2a2c38;color:var(--text);border-color:#4b4e62" ${!hasVideo||assemblyBusy?'disabled':''}>✂️ 导出剪映 / CapCut 草稿包 (.zip)</button>
 ${assemblyLastExport?`<div class="section-card" style="margin-top:16px;padding:14px"><b>最近导出已完成</b><p class="note" style="margin:6px 0">${esc(assemblyLastExport.file)} (${(assemblyLastExport.bytes/1024/1024).toFixed(2)} MiB)</p><a class="inline-link" href="${esc(assemblyLastExport.url)}" download="${esc(assemblyLastExport.file)}">点击下载到本地 ↗</a></div>`:''}`;
}

UI.views.assembly=assemblyView;
UI.inspectors.assembly=assemblyInspector;

async function triggerAssemblyExport(endpoint,label){
 if(assemblyBusy)return;
 assemblyBusy=true;render();
 try{
  const res=await api(endpoint,currentAssemblyPayload());
  assemblyLastExport=res;
  const a=document.createElement('a');a.href=res.url;a.download=res.file;a.click();
  toast(`${label}已生成：${res.file}`);
 }catch(e){toast(e.message)}finally{assemblyBusy=false;render()}
}

UI.binders.push(()=>{
 if(tab!=='assembly')return;
 if($('#assembly-refresh'))$('#assembly-refresh').onclick=()=>loadAssemblyPlan(true);
 if($('#assembly-audio'))$('#assembly-audio').onchange=()=>{assemblyAudioId=$('#assembly-audio').value;render()};
 if($('#assembly-audio-start'))$('#assembly-audio-start').oninput=()=>{assemblyAudioStart=Math.max(0,Number($('#assembly-audio-start').value)||0)};
 document.querySelectorAll('[data-asm-enable]').forEach(el=>el.onchange=()=>{
  const id=el.dataset.asmEnable;assemblyEdits[id]??={};assemblyEdits[id].enabled=el.checked;render();
 });
 document.querySelectorAll('[data-asm-start]').forEach(el=>el.onchange=()=>{
  const id=el.dataset.asmStart;assemblyEdits[id]??={};assemblyEdits[id].start=Math.max(0,Number(el.value)||0);render();
 });
 document.querySelectorAll('[data-asm-end]').forEach(el=>el.onchange=()=>{
  const id=el.dataset.asmEnd;assemblyEdits[id]??={};assemblyEdits[id].end=Math.max(0.1,Number(el.value)||0.1);render();
 });
 document.querySelectorAll('[data-asm-mute]').forEach(el=>el.onchange=()=>{
  const id=el.dataset.asmMute;assemblyEdits[id]??={};assemblyEdits[id].mute_source_audio=el.value==='true';
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
  let idx=0;
  const playClip=i=>{
   if(i>=enabledShots.length){if(bgm)bgm.pause();return}
   const s=enabledShots[i],ed=assemblyEdits[s.shot_id]||{start:0,end:s.duration};
   v.src='/assets/'+encodeURIComponent(s.file);
   v.muted=!!ed.mute_source_audio;
   v.onloadedmetadata=()=>{v.currentTime=Number(ed.start)||0;v.play().catch(()=>{})};
   v.ontimeupdate=()=>{if(v.currentTime>=(Number(ed.end)||s.duration)){v.ontimeupdate=null;playClip(i+1)}};
   v.onended=()=>{v.ontimeupdate=null;playClip(i+1)};
  };
  if(bgm){bgm.currentTime=Number(assemblyAudioStart)||0;bgm.play().catch(()=>{})}
  playClip(0);
 };
 if($('#export-rough-mp4'))$('#export-rough-mp4').onclick=()=>triggerAssemblyExport('/api/assembly/render','粗剪 MP4 成片');
 if($('#export-fcpxml'))$('#export-fcpxml').onclick=()=>triggerAssemblyExport('/api/assembly/fcpxml','FCPXML 时间线');
 if($('#export-capcut'))$('#export-capcut').onclick=()=>triggerAssemblyExport('/api/assembly/capcut','剪映草稿包');
});
