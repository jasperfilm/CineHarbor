// Verify 0.4.0 modular UI slots, GCLabsCore adapter, step progress, batch queue, frame chaining, template converter & assembly UI.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={
 AbortController,
 location:{pathname:'/studio'},
 document:{hidden:false,addEventListener(){},querySelector(){return null},querySelectorAll(){return []}},
 window:{LOCAL_KEY:'test',addEventListener(){}},
 setInterval(){},setTimeout(){},clearTimeout(){},
 fetch:async(path)=>({ok:true,json:async()=>path==='/api/account/login'?{state:'idle'}:[]})
};
vm.createContext(context);
for(const [name,end] of [
 ['compare.js',null],
 ['app.js','(async()=>{try{[data,verified]'],
 ['console-ui.js','syncOperations().then('],
 ['account-ui.js','loginSync().catch('],
 ['canvas-ui.js',null],
 ['workflows-ui.js',null],
 ['assembly-ui.js',null]
]){
 let source=fs.readFileSync(__dirname+'/web/'+name,'utf8');
 if(end)source=source.slice(0,name==='account-ui.js'?source.lastIndexOf(end):source.indexOf(end));
 vm.runInContext(source,context);
}

// 1. Core/Shell decoupling & registered tabs
assert.equal(typeof context.window.GCLabsCore.request,'function');
const tabIds=Array.from(vm.runInContext('UI.tabs.map(t=>t.id)',context));
assert.deepEqual(tabIds,['shots','assets','workflows','models','jobs','assembly']);

// 2. Studio frame-chaining controls & batch queue toolbar
vm.runInContext(`
data={
 project:{id:'p1',name:'Studio 0.4',status:'active',ratio:'9:16'},
 policy:{max_minutes:240},
 models:[{id:'h3',name:'MiniMax H3',kind:'video',state:'candidate'}],
 assets:[{id:'v1',name:'out.mp4',file:'v1.mp4',kind:'video'},{id:'a1',name:'bgm.wav',file:'a1.wav',kind:'audio'}],
 shots:[{id:'s1',title:'镜头1',prompt:'cyberpunk',duration:5,resolution:'1080P',model:'h3',seed:1,output:'v1',versions:[]}],
 jobs:[
  {id:'j1',shot:'s1',title:'镜头1',state:'prepared',attempted:false,created:'now',config:{model:'h3'}},
  {id:'j2',shot:'s1',title:'镜头2',state:'prepared',attempted:false,created:'now',config:{model:'h3'}}
 ],
 workflows:[]
};
selected='s1';
render=()=>{};
`,context);

let studioHtml=vm.runInContext('studioView()',context);
assert.ok(!studioHtml.includes('火星游戏之夜'),'Hardcoded private project title must be gone');
assert.match(studioHtml,/粗剪与交付/);
assert.match(studioHtml,/chain-last-next/);
assert.match(studioHtml,/chain-last-new/);

let jobsHtml=vm.runInContext("tab='jobs';content()",context);
assert.match(jobsHtml,/id="run-batch-jobs"/);

// 3. Step-level sampling progress + safe interrupt button
vm.runInContext(`operations=[{id:'op1',action:'generate',label:'生成作品',state:'running',created:10,updated:15,step_done:12,step_total:20,eta_seconds:18,message:'采样第 12 / 20 步'}]`,context);
let opsHtml=vm.runInContext('opCards()',context);
assert.match(opsHtml,/采样第 12 \/ 20 步 · 60.0% · 预计剩余 18 秒/);
assert.match(opsHtml,/id="interrupt-sampling"/);

// 4. Official template 1-click converter & custom node lockfile UI
let wfHtml=vm.runInContext("tab='workflows';content()",context);
assert.match(wfHtml,/data-convert-template="video_wan2_2_14B_i2v"/);
vm.runInContext("workflowDraft={id:'w1',name:'Wan',kind:'video',revision:1,graph:{'1':{class_type:'SaveVideo',inputs:{video:null}}},bindings:{},positions:{},model_files:[],custom_nodes:[],versions:[]};workflowNode='1'",context);
let wfInsp=vm.runInContext('inspector()',context);
assert.match(wfInsp,/id="workflow-custom-nodes"/);
assert.match(wfInsp,/id="workflow-nodes-setup"/);

// 5. Rough-cut assembly view & exporters
vm.runInContext(`assemblyPlan={shots:[{shot_id:'s1',title:'镜头1',asset_id:'v1',file:'v1.mp4',duration:5.0,width:1088,height:1920,fps:24,has_audio:false}],audios:[{asset_id:'a1',name:'bgm.wav',file:'a1.wav',duration:12.0}],final_file:false};assemblyEdits={s1:{enabled:true,start:0,end:5.0,mute_source_audio:false}};tab='assembly'`,context);
let asmHtml=vm.runInContext('content()',context);
let asmInsp=vm.runInContext('inspector()',context);
assert.match(asmHtml,/id="assembly-player"/);
assert.match(asmHtml,/id="assembly-play-all"/);
assert.match(asmInsp,/id="export-rough-mp4"/);
assert.match(asmInsp,/id="export-fcpxml"/);
assert.match(asmInsp,/id="export-capcut"/);

console.log('CineHarbor 0.4.0 modular UI, batch queue, step progress, frame chaining, template converter and rough-cut assembly UI passed.');
