// Explicit workspace snapshots: capture the actual UI graph, never queue work.
const panel=document.createElement('details');
panel.className='cineharbor-snapshots';
const styles=document.createElement('style');styles.textContent=`
.cineharbor-snapshots{box-shadow:0 12px 36px #0006;line-height:1.5;width:360px;max-width:calc(100vw - 28px);max-height:75vh;overflow:auto}
.cineharbor-snapshots summary{cursor:pointer;font-weight:600;letter-spacing:.01em}
.cineharbor-snapshots p{margin:12px 0;color:#d6d0df}
.cineharbor-snapshots input:not([type=checkbox]){box-sizing:border-box;width:100%;padding:9px 11px;border:1px solid #645573;border-radius:7px;background:#1d1824;color:#f8f5fc;font:inherit}
.cineharbor-snapshots label{display:flex;align-items:center;gap:8px;margin-top:10px}
.cineharbor-snapshots label input{accent-color:#bfa6eb}
.cineharbor-snapshots button,.cineharbor-snapshot-dialog button{padding:8px 11px;border:1px solid #6e5a83;border-radius:7px;background:#3a3045;color:#f7f3fc;font:inherit;cursor:pointer}
.cineharbor-snapshots button:hover,.cineharbor-snapshot-dialog button:hover{background:#51415e}
.cineharbor-snapshots button:focus-visible,.cineharbor-snapshot-dialog button:focus-visible{outline:2px solid #d5bfff;outline-offset:2px}
.cineharbor-snapshots a{display:inline-block;margin:8px 0 0 7px;text-decoration:underline}
.cineharbor-snapshots div>div{border-top:1px solid #51445f;padding:10px 0;margin-top:8px}
.cineharbor-snapshots div>div>span{display:block;overflow-wrap:anywhere}
`;document.head.append(styles);
Object.assign(panel.style,{position:'fixed',right:'14px',top:'75px',zIndex:99990,background:'#282034',color:'#fff',padding:'12px',border:'1px solid #bfa6eb',borderRadius:'10px',maxWidth:'380px',font:'13px system-ui'});
const summary=document.createElement('summary');summary.textContent='CineHarbor · Save & resume';panel.append(summary);
const description=document.createElement('p');description.textContent='Save this canvas and all managed ComfyUI input/output files. Models and custom node installations are not included. Finish running jobs first. Saved node fields may contain secrets you entered; remove them before sharing.';panel.append(description);
const name=document.createElement('input');name.placeholder='Project snapshot name';name.maxLength=160;name.value='ComfyUI project';name.setAttribute('aria-label','Project snapshot name');panel.append(name);
const label=document.createElement('label'),drive=document.createElement('input');drive.type='checkbox';label.append(drive,document.createTextNode(' Also copy to my mounted Google Drive'));panel.append(document.createElement('br'),label);
const status=document.createElement('p');status.setAttribute('role','status');
const list=document.createElement('div');
const importFile=document.createElement('input');importFile.type='file';importFile.accept='.zip';importFile.hidden=true;
importFile.onchange=()=>run(async()=>{
 const file=importFile.files[0];if(!file)return;
 status.textContent='Importing saved snapshot onto this Mac…';
 const started=await api('/import-start',{bytes:file.size});
 for(let offset=0;offset<file.size;offset+=4*1024*1024){
  const r=await fetch('/__gc_projects/import-chunk/'+started.id,{method:'POST',headers:{'X-Snapshot-Offset':String(offset)},body:file.slice(offset,offset+4*1024*1024)});
  if(!r.ok)throw Error('Snapshot upload interrupted. Re-select the file to retry.');
 }
 await api('/import-finish/'+started.id,{});await refresh();status.textContent='Imported and checksum verified on this Mac. Choose Open to restore; nothing queued.';importFile.value='';
});
let busy=false;
async function api(path,body){const r=await fetch('/__gc_projects'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'Snapshot request failed');return d}
async function appReady(){const app=window.comfyAPI?.app?.app;if(!app?.graph||!app?.loadGraphData)throw Error('ComfyUI is still loading. Try again when the canvas is ready.');return app}
async function run(fn){if(busy)return;busy=true;try{await fn()}catch(e){status.textContent=e.message}finally{busy=false}}
function button(text,action){const b=document.createElement('button');b.textContent=text;b.style.margin='6px 6px 0 0';b.onclick=()=>run(action);return b}
function confirmRestore(){return new Promise(resolve=>{
 const dialog=document.createElement('dialog'),message=document.createElement('p');dialog.className='cineharbor-snapshot-dialog';
 Object.assign(dialog.style,{background:'#282034',color:'#fff',border:'1px solid #bfa6eb',borderRadius:'12px',maxWidth:'460px',font:'14px system-ui',padding:'24px'});
 message.textContent='Restore this saved canvas and its media? Save current edits first. Existing different media files will not be overwritten. No generation will start.';
 const finish=value=>{dialog.close();dialog.remove();resolve(value)};
 const yes=document.createElement('button'),no=document.createElement('button');yes.textContent='Restore snapshot';no.textContent='Keep current canvas';yes.style.marginRight='12px';yes.onclick=()=>finish(true);no.onclick=()=>finish(false);
 dialog.append(message,yes,no);dialog.addEventListener('cancel',e=>{e.preventDefault();finish(false)});document.body.append(dialog);dialog.showModal();no.focus();
})}
async function restore(id){
 const app=await appReady();
 if(!await confirmRestore())return;
 status.textContent='Restoring and checking media… Keep this page open.';
 const d=await api('/restore/'+id,{});
 // Restored files must enter loader combo lists before graph configuration;
 // stale node definitions can otherwise reset a restored media selection.
 if(app.refreshComboInNodes)await app.refreshComboInNodes();
 await app.loadGraphData(d.canvas,true,true,d.name+'.json');
 status.textContent=`Restored ${d.files} files and the saved canvas. Models and custom nodes may need preparation. Nothing queued.`;
}
async function refresh(){
 const entries=await api('');list.replaceChildren();
 for(const item of entries){const row=document.createElement('div'),title=document.createElement('span');title.textContent=item.name+' · '+(item.bytes/1024/1024).toFixed(1)+' MB ';const link=document.createElement('a');link.textContent='Download ZIP';link.href='/__gc_projects/download/'+item.id;link.style.color='#dbc6ff';row.append(title,button('Open',()=>restore(item.id)),link);list.append(row)}
 if(!entries.length)list.textContent='No local snapshots yet.';
}
panel.append(document.createElement('br'),button('Save snapshot',async()=>{
 const app=await appReady();
 if(!name.value.trim())throw Error('Enter a project name.');
 status.textContent='Saving canvas and transferring media to this Mac… Keep this page open.';
 const d=await api('/save',{canvas:app.graph.serialize(),name:name.value.trim(),drive:drive.checked});
 status.textContent=d.warning||`Saved ${d.files} files on this Mac${d.drive_saved?' and copied to Drive (checksum verified; use Save & close GPU to flush Drive before release)':''}. No generation started.`;
 await refresh();
}),button('Local snapshots',refresh),button('Find Drive snapshots',async()=>{
 status.textContent='Reading snapshots from your mounted Drive…';
 const entries=await api('/drive');list.replaceChildren();
 for(const item of entries){const row=document.createElement('div'),title=document.createElement('span');title.textContent=item.name+' ';row.append(title,button('Copy to Mac',async()=>{status.textContent='Copying and verifying Drive snapshot…';await api('/fetch-drive/'+item.id,{});await refresh();status.textContent='Copied to this Mac. Choose Open to restore.'}));list.append(row)}
 status.textContent=entries.length?'Choose a snapshot to copy to this Mac.':'No snapshots found. Make sure your Drive is mounted.';
}),button('Import snapshot ZIP',()=>importFile.click()),importFile,status,list);
document.body.append(panel);
