// Offline API graph editor, automatic LiteGraph canvas converter & custom node commit lockfile.
let workflowDraft=null,workflowNode=null,workflowDirty=false,wireSource=null,modelPresets=[];
const nodePresets={
 CheckpointLoaderSimple:{ckpt_name:''},
 CLIPTextEncode:{text:'',clip:null},UNETLoader:{unet_name:'',weight_dtype:'default'},CLIPLoader:{clip_name:'',type:'stable_diffusion',device:'default'},VAELoader:{vae_name:''},LoadImage:{image:''},EmptyLatentImage:{width:1024,height:1024,batch_size:1},KSampler:{model:null,positive:null,negative:null,latent_image:null,seed:42,steps:30,cfg:7,sampler_name:'euler',scheduler:'normal',denoise:1},VAEDecode:{samples:null,vae:null},SaveImage:{images:null,filename_prefix:'GC_Labs'},CreateVideo:{images:null,fps:24},SaveVideo:{video:null,filename_prefix:'GC_Labs',format:'auto',codec:'auto'},SaveAudio:{audio:null,filename_prefix:'GC_Labs'}
};

const OFFICIAL_TEMPLATES=[
 ['video_wan2_2_14B_i2v','Wan 2.2 A14B 图生视频'],
 ['video_ltx2_5_i2v','LTX 2.5 音视频图生视频'],
 ['image_qwen_Image_2512','Qwen Image 2512 文生图'],
 ['audio_ace_step_1_5_split_4b','ACE-Step 1.5 + 4B 音乐规划']
];

UI.registerTab({
 id:'workflows',
 icon:'⌘',
 label:'工作流画布',
 title:'模型工作流画布',
 subtitle:'支持直接导入 ComfyUI 画布 JSON 自动转 API 格式，绑定完整精度模型与固定 Commit 节点锁。',
 count:d=>(d?.workflows||[]).length||null
},'models');

function dirtyWorkflow(){workflowDirty=true;const button=$('#workflow-save');if(button)button.textContent='保存版本 ●'}
function openWorkflow(id){const item=(data.workflows||[]).find(x=>x.id===id);workflowDraft=item?JSON.parse(JSON.stringify(item)):null;workflowNode=item?Object.keys(item.graph)[0]:null;workflowDirty=false;render()}
function graphLink(v){return Array.isArray(v)&&v.length===2&&typeof v[0]==='string'&&Number.isInteger(v[1])}
function nodeXY(id,i){return workflowDraft.positions?.[id]||[70+(i%3)*330,60+Math.floor(i/3)*420]}

function workflowList(){
 return `<section class="section-card ${workflowDraft?'recipe-open':''}"><div class="summary"><h3>模型工作流</h3><select id="workflow-select" aria-label="选择模型工作流"><option value="">选择工作流</option>${(data.workflows||[]).map(w=>`<option value="${esc(w.id)}" ${workflowDraft?.id===w.id?'selected':''}>${esc(w.name)}</option>`).join('')}</select><button id="workflow-import" class="primary">导入画布 / API JSON</button><input id="workflow-file" type="file" accept=".json" hidden><button id="workflow-new">新建工作流</button></div><p class="note">同时支持 ComfyUI 原始画布 JSON（自动展开子图转为 API 配方）与 API JSON。提交任务才会在已连接的 G4 运行；付费 API 节点禁止执行。</p><div class="recipe-list">${(data.workflows||[]).map(w=>`<button data-workflow="${esc(w.id)}" class="${workflowDraft?.id===w.id?'active':''}">${esc(w.name)} <small>${esc(w.kind)} · v${w.revision} · ${Object.keys(w.graph).length}节点</small></button>`).join('')||'<p class="muted">导入任意 ComfyUI JSON、一键载入下方官方模板，或新建节点工作流。</p>'}</div><details><summary>内置官方 ComfyUI 模板（支持一键转入编辑器）</summary><p class="note">无需先开 GPU 导出 API 格式：点击“一键载入编辑器”即可在本机将官方原始画布（含子图）自动转换为可编辑 API 配方。模板不含模型权重。</p><div class="template-grid">${OFFICIAL_TEMPLATES.map(([f,n])=>`<div class="template-row"><span>${esc(n)}</span><div><button class="primary" data-convert-template="${f}" data-template-label="${esc(n)}">一键载入编辑器</button> <a class="inline-link" href="/templates/${f}.json" download>原始画布 ↓</a></div></div>`).join('')}</div></details></section>`;
}

function graphEditor(){
 if(!workflowDraft)return '<div class="empty">选择工作流后可编辑参数、拖动节点和连线。<br>将节点右侧的输出点拖到另一个节点的输入点，即可连接输出0；其他输出序号在右侧设置。</div>';
 const entries=Object.entries(workflowDraft.graph);
 return `<div class="board-tools"><label>名称 <input id="workflow-name" value="${esc(workflowDraft.name)}"></label><label>类型 <select id="workflow-kind">${['image','video','audio'].map(k=>`<option ${workflowDraft.kind===k?'selected':''}>${k}</option>`).join('')}</select></label><button id="workflow-save" class="primary">保存版本${workflowDirty?' ●':''}</button><button id="workflow-export">导出 API JSON</button><button id="workflow-delete" class="danger">移除工作流</button><select id="node-preset" aria-label="节点类型">${Object.keys(nodePresets).map(k=>`<option>${k}</option>`).join('')}</select><button id="node-add">＋ 节点</button></div><div class="graph-board"><div class="graph-world" style="width:${Math.max(1800,...entries.map(([id],i)=>nodeXY(id,i)[0]+350))}px;height:${Math.max(1000,...entries.map(([id],i)=>nodeXY(id,i)[1]+330))}px"><svg class="board-edges" width="100%" height="100%">${entries.map(([id,n],i)=>Object.entries(n.inputs).filter(([,v])=>graphLink(v)).map(([k,v])=>{const from=entries.findIndex(([x])=>x===v[0]);if(from<0)return '';const [x,y]=nodeXY(v[0],from),[tx,ty]=nodeXY(id,i),slot=Object.keys(n.inputs).indexOf(k);return `<path d="M${x+280},${y+45} C${x+330},${y+45} ${tx-50},${ty+65+slot*24} ${tx},${ty+65+slot*24}"/>`}).join('')).join('')}</svg>${entries.map(([id,n],i)=>{const [x,y]=nodeXY(id,i);return `<article class="graph-node ${workflowNode===id?'selected':''}" style="left:${x}px;top:${y}px" data-graph-node="${esc(id)}"><div class="graph-handle" data-drag-graph="${esc(id)}"><small>#${esc(id)}</small><b>${esc(n._meta?.title||n.class_type)}</b><button class="socket output" data-output-node="${esc(id)}" aria-label="${esc(id)}输出0"></button></div><div class="graph-inputs">${Object.entries(n.inputs).map(([key,value])=>`<div><button class="socket input" data-input-node="${esc(id)}" data-input-key="${esc(key)}" aria-label="${esc(id+' '+key)}输入"></button><span>${esc(key)}</span><small>${graphLink(value)?'← '+esc(value[0])+':'+value[1]:esc(String(value??'未连接').slice(0,26))}</small></div>`).join('')}</div><button data-edit-node="${esc(id)}">编辑参数</button></article>`}).join('')}</div></div>`;
}

function workflowView(){return workflowList()+graphEditor()}

function graphInspector(){
 if(!workflowDraft)return '<h2>工作流参数</h2><p>导入画布/API JSON、载入官方模板或新建工作流。</p>';
 const node=workflowDraft.graph[workflowNode];
 return `<h2>节点参数</h2>${node?`<p>#${esc(workflowNode)}</p><label class="field"><span>节点类型</span><input id="node-class" value="${esc(node.class_type)}"></label>${Object.entries(node.inputs).map(([key,value])=>{const link=graphLink(value);return `<label class="field"><span>${esc(key)}</span>${link?`<div class="row"><select data-link-input="${esc(key)}">${Object.keys(workflowDraft.graph).filter(id=>id!==workflowNode).map(id=>`<option value="${esc(id)}" ${value[0]===id?'selected':''}>#${esc(id)} ${esc(workflowDraft.graph[id].class_type)}</option>`).join('')}</select><input data-link-slot="${esc(key)}" type="number" min="0" max="64" value="${value[1]}" aria-label="输出序号"></div><button data-unlink="${esc(key)}">断开连线</button>`:typeof value==='boolean'?`<select data-node-input="${esc(key)}" data-value-type="boolean"><option value="true" ${value?'selected':''}>true</option><option value="false" ${!value?'selected':''}>false</option></select>`:typeof value==='number'?`<input data-node-input="${esc(key)}" data-value-type="number" type="number" value="${value}">`:typeof value==='object'&&value!==null?`<textarea data-node-input="${esc(key)}" data-value-type="json">${esc(JSON.stringify(value))}</textarea>`:`<textarea data-node-input="${esc(key)}" data-value-type="text">${esc(value??'')}</textarea>`}</label>`}).join('')}<button id="node-delete" class="danger">移除节点</button><label class="field"><span>新增输入名称</span><input id="node-new-input"></label><button id="node-input-add">新增输入</button>`:'<p>选择节点编辑。</p>'}<details><summary>视频帧率与帧数对齐</summary><p class="note">帧数取满足对齐规则的最近上整值。例如Wan为4n+1，LTX为8n+1。</p><textarea id="workflow-timing" rows="4">${esc(workflowDraft._timing_text??JSON.stringify(workflowDraft.timing||{fps:24,frame_multiple:4,frame_offset:1},null,2))}</textarea></details><details><summary>镜头参数绑定</summary><p class="note">绑定的输入会在任务提交时使用镜头参数替换。每项对应一个或多个 {node,input}。</p><textarea id="workflow-bindings" rows="8">${esc(workflowDraft._bindings_text??JSON.stringify(workflowDraft.bindings||{},null,2))}</textarea></details><details open><summary>官方模型文件清单（含 G4 全精度一键预设）</summary><p class="note">完整精度 safetensors（拒绝量化版）。可从下方一键套用经核实的官方 Hugging Face 全精度套件，并自动把工作流节点中的量化文件名升级为全精度文件名。</p>${modelPresets.length?`<div class="row" style="margin-bottom:8px"><select id="preset-select" aria-label="选择G4全精度预设"><option value="">选择 G4 全精度认证模型预设…</option>${modelPresets.map(p=>`<option value="${esc(p.id)}">${esc(p.name)} (~${p.approx_gb}GB)</option>`).join('')}</select><button id="apply-model-preset" style="flex:0 0 auto">一键套用</button></div>`:''}<textarea id="workflow-models" rows="7">${esc(workflowDraft._models_text??JSON.stringify(workflowDraft.model_files||[],null,2))}</textarea><button id="workflow-models-prepare">准备模型并备份</button></details><details><summary>自定义节点锁文件（GitHub + 40位 Commit）</summary><p class="note">只允许公开 GitHub 仓库并强制固定 40 位小写十六进制 Commit SHA，禁止浮动分支。示例：[{"repo":"https://github.com/owner/repo","commit":"40位sha"}]</p><textarea id="workflow-custom-nodes" rows="6">${esc(workflowDraft._custom_nodes_text??JSON.stringify(workflowDraft.custom_nodes||[],null,2))}</textarea><button id="workflow-nodes-setup">检出锁定节点并启动 ComfyUI</button></details><details><summary>版本记录 · ${(workflowDraft.versions||[]).length}</summary>${(workflowDraft.versions||[]).map((v,i)=>`<p>v${v.revision} · ${esc(v.name)} <button data-restore-workflow="${i}">载入为草稿</button></p>`).join('')}</details>`;
}

UI.views.workflows=workflowView;
UI.inspectors.workflows=graphInspector;
UI.viewDecorators.models=html=>`<div class="section-card"><button id="manage-workflows" class="primary">管理模型工作流</button><p class="note">图像、视频与音乐均可接入本地ComfyUI工作流。支持原始画布一键转API、完整精度模型清单与固定Commit节点锁。</p></div>`+html;

function downloadJSON(name,value){
 const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),a=document.createElement('a');
 a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function draftFields(){
 if(!workflowDraft)return;
 workflowDraft.name=$('#workflow-name')?.value||workflowDraft.name;
 workflowDraft.kind=$('#workflow-kind')?.value||workflowDraft.kind;
 if($('#workflow-bindings'))workflowDraft.bindings=JSON.parse($('#workflow-bindings').value);
 if($('#workflow-models'))workflowDraft.model_files=JSON.parse($('#workflow-models').value);
 if($('#workflow-custom-nodes'))workflowDraft.custom_nodes=JSON.parse($('#workflow-custom-nodes').value);
 if($('#workflow-timing'))workflowDraft.timing=JSON.parse($('#workflow-timing').value);
}

function canLeaveWorkflow(){return !workflowDirty||confirm('工作流有未保存修改，确定离开？')}
UI.leaveGuards.push(fromTab=>fromTab!=='workflows'||canLeaveWorkflow());
UI.workspaceHooks.push(()=>{workflowDraft=null;workflowNode=null;workflowDirty=false});

async function saveWorkflow(){
 draftFields();
 const saved=await api('/api/workflow',{...workflowDraft,base_revision:workflowDraft.revision});
 data=await api('/api/workspace');
 workflowDraft=saved;workflowDirty=false;render();toast('工作流版本已保存；未启动GPU');
}

UI.binders.push(()=>{
 if($('#manage-workflows'))$('#manage-workflows').onclick=()=>{tab='workflows';render()};
 if($('#node-class'))$('#node-class').oninput=()=>{workflowDraft.graph[workflowNode].class_type=$('#node-class').value.trim();dirtyWorkflow()};
 if($('#workflow-delete'))$('#workflow-delete').onclick=()=>action(async()=>{
  if(!workflowDraft.id){workflowDraft=null;workflowDirty=false;render();return}
  if(!confirm('移除工作流？保留本机回收记录和已提交任务的快照。'))return;
  await api('/api/workflow/delete',{id:workflowDraft.id,base_revision:workflowDraft.revision});
  data=await api('/api/workspace');workflowDraft=null;workflowDirty=false;render();
 });
 if($('#workflow-select'))$('#workflow-select').onchange=()=>{if(canLeaveWorkflow())openWorkflow($('#workflow-select').value)};
 document.querySelectorAll('[data-workflow]').forEach(e=>e.onclick=()=>{if(canLeaveWorkflow())openWorkflow(e.dataset.workflow)});
 document.querySelectorAll('[data-convert-template]').forEach(btn=>btn.onclick=()=>action(async()=>{
  if(!canLeaveWorkflow())return;
  const saved=await api('/api/workflow/convert',{template:btn.dataset.convertTemplate,name:btn.dataset.templateLabel,save:true});
  data=await api('/api/workspace');openWorkflow(saved.id);
  toast('已自动展开官方模板画布并载入编辑器；未启动GPU');
 }));
 if($('#workflow-import'))$('#workflow-import').onclick=()=>$('#workflow-file').click();
 if($('#workflow-file'))$('#workflow-file').onchange=()=>action(async()=>{
  const f=$('#workflow-file').files[0];if(!f)return;
  if(f.size>2000000)throw Error('工作流请小于2MB');
  const raw=JSON.parse(await f.text());
  const defaultName=raw.name||f.name.replace(/\.json$/i,'');
  let saved;
  if(Array.isArray(raw.nodes)){
   saved=await api('/api/workflow/convert',{canvas:raw,name:defaultName,save:true});
   data=await api('/api/workspace');openWorkflow(saved.id);
   toast('已将 ComfyUI 画布自动转换为可编辑 API 工作流');
   return;
  }
  const graph=raw.graph||raw.prompt||raw;
  saved=await api('/api/workflow',{name:defaultName,kind:raw.kind||'video',graph,...(raw.bindings?{bindings:raw.bindings}:{}),positions:raw.positions||{},model_files:raw.model_files||[],custom_nodes:raw.custom_nodes||[],...(raw.timing?{timing:raw.timing}:{})});
  data=await api('/api/workspace');openWorkflow(saved.id);toast('API 工作流已导入');
 });
 if($('#workflow-new'))$('#workflow-new').onclick=()=>{
  if(!canLeaveWorkflow())return;
  workflowDraft={name:'新工作流',kind:'image',graph:{'1':{class_type:'CLIPTextEncode',inputs:{text:'',clip:null}}},bindings:{prompt:[{node:'1',input:'text'}]},positions:{},model_files:[],custom_nodes:[],versions:[]};
  workflowNode='1';workflowDirty=true;render();
 };
 if($('#workflow-save'))$('#workflow-save').onclick=()=>action(saveWorkflow);
 for(const [id,key] of [['workflow-name','name'],['workflow-kind','kind'],['workflow-bindings','_bindings_text'],['workflow-models','_models_text'],['workflow-custom-nodes','_custom_nodes_text'],['workflow-timing','_timing_text']])if($('#'+id))$('#'+id).oninput=()=>{workflowDraft[key]=$('#'+id).value;dirtyWorkflow()};
 if($('#workflow-export'))$('#workflow-export').onclick=()=>action(async()=>{
  draftFields();
  downloadJSON(workflowDraft.name+'.json',{name:workflowDraft.name,kind:workflowDraft.kind,graph:workflowDraft.graph,bindings:workflowDraft.bindings,positions:workflowDraft.positions,model_files:workflowDraft.model_files,custom_nodes:workflowDraft.custom_nodes||[],timing:workflowDraft.timing});
 });
 if($('#workflow-models-prepare'))$('#workflow-models-prepare').onclick=()=>action(async()=>{
  if(workflowDirty||!workflowDraft.id)throw Error('请先保存工作流版本。');
  await control('models',{workflow:workflowDraft.id});
 });
 if($('#apply-model-preset'))$('#apply-model-preset').onclick=()=>action(async()=>{
  const pid=$('#preset-select')?.value;
  if(!pid)throw Error('请先选择一个 G4 全精度模型预设。');
  if(!workflowDraft.id){
   const preset=modelPresets.find(x=>x.id===pid);
   if(preset){workflowDraft.model_files=JSON.parse(JSON.stringify(preset.model_files));workflowDraft._models_text=null;dirtyWorkflow();render();toast('已填入全精度模型清单草稿')}
   return;
  }
  const updated=await api('/api/workflow/apply-preset',{workflow_id:workflowDraft.id,preset_id:pid});
  data=await api('/api/workspace');
  workflowDraft=updated;workflowDirty=false;render();
  toast('已套用 G4 全精度预设并同步升级节点权重文件名；未启动GPU');
 });
 if($('#workflow-nodes-setup'))$('#workflow-nodes-setup').onclick=()=>action(async()=>{
  if(workflowDirty||!workflowDraft.id)throw Error('请先保存工作流版本。');
  await control('setup',{workflow:workflowDraft.id});
 });
 document.querySelectorAll('[data-edit-node]').forEach(e=>e.onclick=()=>{draftFields();workflowNode=e.dataset.editNode;render()});
 document.querySelectorAll('[data-node-input]').forEach(e=>e.oninput=()=>{
  let value=e.value;
  if(e.dataset.valueType==='number'){value=Number(value);if(!Number.isFinite(value))return}
  else if(e.dataset.valueType==='boolean')value=value==='true';
  else if(e.dataset.valueType==='json'){try{value=JSON.parse(value)}catch{return}}
  workflowDraft.graph[workflowNode].inputs[e.dataset.nodeInput]=value;dirtyWorkflow();
 });
 document.querySelectorAll('[data-link-input]').forEach(e=>e.onchange=()=>{workflowDraft.graph[workflowNode].inputs[e.dataset.linkInput][0]=e.value;dirtyWorkflow();render()});
 document.querySelectorAll('[data-link-slot]').forEach(e=>e.oninput=()=>{workflowDraft.graph[workflowNode].inputs[e.dataset.linkSlot][1]=Number(e.value);dirtyWorkflow()});
 document.querySelectorAll('[data-unlink]').forEach(e=>e.onclick=()=>{workflowDraft.graph[workflowNode].inputs[e.dataset.unlink]=null;dirtyWorkflow();render()});
 if($('#node-add'))$('#node-add').onclick=()=>{
  draftFields();
  let id=String(Math.max(0,...Object.keys(workflowDraft.graph).map(Number).filter(Number.isFinite))+1);
  while(workflowDraft.graph[id])id+='n';
  const type=$('#node-preset').value;
  workflowDraft.graph[id]={class_type:type,inputs:JSON.parse(JSON.stringify(nodePresets[type]))};
  workflowNode=id;dirtyWorkflow();render();
 };
 if($('#node-delete'))$('#node-delete').onclick=()=>{
  const ident=workflowNode;delete workflowDraft.graph[ident];
  for(const n of Object.values(workflowDraft.graph))for(const [k,v] of Object.entries(n.inputs))if(graphLink(v)&&v[0]===ident)n.inputs[k]=null;
  for(const key of Object.keys(workflowDraft.bindings||{}))workflowDraft.bindings[key]=workflowDraft.bindings[key].filter(x=>x.node!==ident);
  workflowNode=Object.keys(workflowDraft.graph)[0];dirtyWorkflow();render();
 };
 if($('#node-input-add'))$('#node-input-add').onclick=()=>{
  const name=$('#node-new-input').value.trim();
  if(!/^[a-zA-Z0-9_]{1,80}$/.test(name))return toast('输入名称只能使用字母、数字和下划线。');
  workflowDraft.graph[workflowNode].inputs[name]='';dirtyWorkflow();render();
 };
 document.querySelectorAll('[data-restore-workflow]').forEach(e=>e.onclick=()=>{
  const version=JSON.parse(JSON.stringify(workflowDraft.versions[Number(e.dataset.restoreWorkflow)]));
  Object.assign(workflowDraft,{graph:version.graph,bindings:version.bindings,positions:version.positions,model_files:version.model_files||[],custom_nodes:version.custom_nodes||[],timing:version.timing,name:version.name,kind:version.kind});
  workflowDraft._bindings_text=null;workflowDraft._models_text=null;workflowDraft._custom_nodes_text=null;workflowDraft._timing_text=null;
  workflowNode=Object.keys(workflowDraft.graph)[0];dirtyWorkflow();render();
 });
 document.querySelectorAll('[data-output-node]').forEach(e=>e.onpointerdown=event=>{wireSource=e.dataset.outputNode;event.stopPropagation();event.preventDefault()});
 document.querySelectorAll('[data-input-node]').forEach(e=>e.onpointerup=()=>{
  if(!wireSource||wireSource===e.dataset.inputNode)return;
  workflowDraft.graph[e.dataset.inputNode].inputs[e.dataset.inputKey]=[wireSource,0];wireSource=null;dirtyWorkflow();render();
 });
 document.querySelectorAll('[data-drag-graph]').forEach(handle=>{
  let drag=null;
  handle.onpointerdown=event=>{
   if(event.target.closest('button')||event.button!==0)return;
   const id=handle.dataset.dragGraph,[x,y]=nodeXY(id,Object.keys(workflowDraft.graph).indexOf(id));
   drag={id,x,y,cx:event.clientX,cy:event.clientY};handle.setPointerCapture(event.pointerId);event.preventDefault();
  };
  handle.onpointermove=event=>{
   if(!drag)return;
   const point=[Math.max(10,Math.round(drag.x+event.clientX-drag.cx)),Math.max(10,Math.round(drag.y+event.clientY-drag.cy))];
   workflowDraft.positions??={};workflowDraft.positions[drag.id]=point;
   const card=handle.closest('.graph-node');card.style.left=point[0]+'px';card.style.top=point[1]+'px';dirtyWorkflow();
  };
  handle.onpointerup=()=>{if(drag){drag=null;render()}};
  handle.onpointercancel=()=>{drag=null;render()};
 });
});

window.addEventListener('beforeunload',e=>{if(workflowDirty){e.preventDefault();e.returnValue=''}});
document.addEventListener('pointerup',()=>{wireSource=null});
api('/api/model-presets').then(list=>{if(Array.isArray(list))modelPresets=list}).catch(()=>{});
