// Served only by the owned loopback bridge. Import never queues a prompt.
const token = new URL(location.href).searchParams.get('cineharbor_handoff');
if (token && /^[a-f0-9]{32}$/.test(token)) {
 const banner=document.createElement('div');
 Object.assign(banner.style,{position:'fixed',top:'12px',left:'50%',transform:'translateX(-50%)',zIndex:99999,background:'#282034',color:'#fff',padding:'14px 20px',border:'1px solid #bfa6eb',borderRadius:'12px',maxWidth:'80vw',font:'14px system-ui'});
 banner.setAttribute('role','status');document.body.append(banner);
 const status=t=>{banner.textContent=t};
 let previousCanvas=null,previousApp=null,importStarted=false;
 (async()=>{
  status('Preparing CineHarbor project handoff. Nothing will run automatically.');
  let app;
  const deadline=Date.now()+180000;
  while(Date.now()<deadline){app=window.comfyAPI?.app?.app;if(app?.graph&&app?.canvas&&app?.loadApiJson&&app?.positionConversion)break;await new Promise(r=>setTimeout(r,250))}
  if(!app?.loadApiJson||!app?.positionConversion)throw Error('ComfyUI is not ready. Reload to retry this import.');
  const response=await fetch('/__gc_handoff/'+token,{cache:'no-store'});
  if(!response.ok)throw Error('This handoff expired. Prepare it again in CineHarbor.');
  const data=await response.json();
  if(!['cineharbor.comfy-handoff.v1','cineharbor.comfy-handoff.v2'].includes(data.schema))throw Error('Unsupported handoff format.');
  const assetsHandoff=data.schema==='cineharbor.comfy-handoff.v2';
  const metadataResponse=await fetch('/object_info');
  if(!metadataResponse.ok)throw Error('Cannot verify the cloud nodes. Nothing was imported or queued.');
  const metadata=await metadataResponse.json();
  const importGraph=structuredClone(data.graph);
  if(assetsHandoff){
   data.warnings=data.warnings||[];
   for(const shot of data.shots){
    const ids=shot.recipe_node_ids||[];
    if(ids.some(id=>{const m=metadata[importGraph[id]?.class_type];return !m||m.api_node||m.is_api_node||String(m.category||'').toLowerCase().includes('api_node')})){
     for(const id of ids)delete importGraph[id];
     data.warnings.push({shot_id:shot.shot_id,message:'Generation recipe requires unavailable or API nodes; original assets and shot context still imported.'});
    }
   }
  }
  const missing=[...new Set(Object.values(importGraph).map(n=>n.class_type))].filter(n=>!metadata[n]);
  if(missing.length)throw Error('Required cloud nodes are missing: '+missing.join(', ')+'. Nothing was imported or queued.');
  const paid=Object.values(importGraph).some(n=>metadata[n.class_type]?.api_node||metadata[n.class_type]?.is_api_node||String(metadata[n.class_type]?.category||'').toLowerCase().includes('api_node'));
  if(paid)throw Error('This handoff contains paid API nodes. Import stopped; no generation queued.');
  // Do not replace an existing cloud canvas silently.
  if(app.graph._nodes?.length){
   // An inline choice does not raise a browser-wide dialog over the user's work.
   status(assetsHandoff?'Import these original assets and shot context? Save the current ComfyUI canvas first. No generation will start.':'Import the CineHarbor storyboard? Save any existing cloud workflow first. No generation will start.');
   const accepted=await new Promise(resolve=>{
    const yes=document.createElement('button'),no=document.createElement('button');
    yes.textContent=assetsHandoff?'Import assets and context':'Import storyboard';no.textContent='Keep current canvas';
    yes.style.marginLeft=no.style.marginLeft='12px';
    yes.onclick=()=>resolve(true);no.onclick=()=>resolve(false);
    banner.append(yes,no);
   });
   if(!accepted){status('Import cancelled. Existing cloud canvas kept.');return}
  }
  const graph=importGraph;
  if(assetsHandoff){
   status(`Transferring ${data.assets.length} original media assets. Keep this page open. No generation queued.`);
   const transfer=await fetch('/__gc_handoff/'+token+'/transfer',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
   const receipt=await transfer.json();
   if(!transfer.ok||!receipt.hash_verified)throw Error(receipt.error||'Original media transfer could not be verified.');
   for(const node of Object.values(graph))for(const [key,value]of Object.entries(node.inputs))if(typeof value==='string'&&Object.hasOwn(receipt.files,value))node.inputs[key]=receipt.files[value];
   // Populate loader combo options with the newly transferred filenames before
   // importing, otherwise the frontend may replace them with stale defaults.
   if(app.refreshComboInNodes)await app.refreshComboInNodes();
  }
  for(let i=0;i<(data.images||[]).length;i++){
   const image=data.images[i];status(`Uploading reference ${i+1}/${data.images.length}. No generation queued.`);
   const bytes=Uint8Array.from(atob(image.base64),c=>c.charCodeAt(0));
   const file=new FormData();file.append('image',new Blob([bytes]),image.name);file.append('type','input');file.append('overwrite','false');
   const upload=await fetch('/upload/image',{method:'POST',body:file});
   if(!upload.ok)throw Error('Reference upload failed. Import stopped; no generation queued.');
   const saved=await upload.json();
   if(typeof saved.name!=='string'||!saved.name)throw Error('Reference upload returned no filename. Import stopped; no generation queued.');
   const name=(saved.subfolder?saved.subfolder+'/':'')+saved.name;
   for(const node of Object.values(graph))for(const [key,value]of Object.entries(node.inputs))if(value===image.name)node.inputs[key]=name;
  }
  previousApp=app;previousCanvas=app.graph.serialize?app.graph.serialize():null;importStarted=true;
  await app.loadApiJson(graph,data.project+'.json');
  for(const [id,pos]of Object.entries(data.positions)){
   if(!graph[id])continue;
   const node=app.graph.getNodeById(Number(id));
   if(!node||node.comfyClass!==graph[id]?.class_type)throw Error('Workflow node '+id+' ('+graph[id]?.class_type+') could not be imported correctly. Nothing queued; check the cloud node versions.');
   node.pos=[...pos];
  }
  if(assetsHandoff){
   // Existing results are the starting point. Keep the old recipe inspectable,
   // but prevent Run on a new branch from also re-running its old output nodes.
   for(const shot of data.shots)for(const id of shot.recipe_node_ids||[]){
    const node=app.graph.getNodeById(Number(id));if(node)node.mode=2;
   }
  }
  if(assetsHandoff){
   const verify=app.graphToPrompt?await app.graphToPrompt():null;
   const actual=verify?.output;
   for(const asset of data.assets){
    const expected=graph[asset.node_id];
    if(actual){
     const node=actual[asset.node_id];
     if(!node||node.class_type!==expected.class_type||Object.entries(expected.inputs).some(([key,value])=>node.inputs[key]!==value))throw Error('A media loader did not retain its transferred file. Existing media are saved; retry import after refreshing node definitions.');
    }
   }
  }
  const allNodes=app.graph._nodes||[];
  const focusIds=assetsHandoff?new Set([...data.assets.map(a=>Number(a.node_id)),...data.shots.map(s=>Number(s.context_node_id))]):null;
  const nodes=focusIds?allNodes.filter(n=>focusIds.has(Number(n.id))):allNodes;
  if(nodes.length&&app.canvas.ds){
   const xs=nodes.map(n=>n.pos[0]),ys=nodes.map(n=>n.pos[1]);
   const minx=Math.min(...xs),miny=Math.min(...ys),maxx=Math.max(...nodes.map(n=>n.pos[0]+(n.size?.[0]||300))),maxy=Math.max(...nodes.map(n=>n.pos[1]+(n.size?.[1]||400)));
   if(app.canvas.ds.fitToBounds){
    // Use ComfyUI's viewport fitting; direct scale assignment can be clamped
    // by its zoom limits and leave the first shot behind the sidebar.
    app.canvas.ds.fitToBounds([minx,miny,maxx-minx,maxy-miny],{zoom:.88,viewport:[80,110,innerWidth-110,innerHeight-160]});
   }else{
    app.canvas.ds.scale=Math.min(.7,Math.max(.05,Math.min((innerWidth-180)/(maxx-minx+100),(innerHeight-220)/(maxy-miny+100))));
    app.canvas.ds.offset=[-minx+100/app.canvas.ds.scale,-miny+140/app.canvas.ds.scale];
   }
  }
  app.graph.setDirtyCanvas(true,true);
  status(assetsHandoff?`Imported ${data.assets.length} original media assets and ${data.shots.length} shot context${data.shots.length===1?'':'s'}. Image, video and audio loaders are ready to connect. ${data.shots.some(s=>s.recipe_node_ids?.length)?'Original generation recipes are disabled; enable them only to regenerate. ':''}${data.warnings?.length?data.warnings.length+' generation recipe(s) need manual setup; original assets are preserved. ':''}Nothing queued.`:`Imported ${data.shots.length} shot workflow(s). Prompts, references and parameters transferred. Nothing queued. This is a one-way handoff, not live two-way synchronization.`);
  history.replaceState(null,'',location.pathname);
 })().catch(async e=>{let rollback='';if(importStarted&&previousCanvas&&previousApp?.loadGraphData){try{await previousApp.loadGraphData(previousCanvas);rollback=' Previous canvas restored.'}catch{rollback=' Reopen your saved previous workflow.'}}status('CineHarbor: '+e.message+rollback);const retry=document.createElement('button');retry.textContent='Retry import';retry.style.marginLeft='12px';retry.onclick=()=>location.reload();banner.append(retry)});
}
