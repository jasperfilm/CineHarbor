// Verify 0.5.0 UI additions: Elements tab, Shot Element chips, Multi-Take gallery, Full-Precision Presets, CU Budget & Mobile Monitor QR.
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
 ['elements-ui.js',null],
 ['workflows-ui.js',null],
 ['assembly-ui.js',null]
]){
 let source=fs.readFileSync(__dirname+'/web/'+name,'utf8');
 if(end)source=source.slice(0,name==='account-ui.js'?source.lastIndexOf(end):source.indexOf(end));
 vm.runInContext(source,context);
}

const tabIds=Array.from(vm.runInContext('UI.tabs.map(t=>t.id)',context));
assert.deepEqual(tabIds,['shots','assets','elements','workflows','models','jobs','assembly']);

vm.runInContext(`
data={
 project:{id:'p05',name:'Studio 0.5',status:'active',ratio:'16:9'},
 policy:{max_minutes:240,max_cu_budget:25,budget_paused:true},
 models:[{id:'h3',name:'MiniMax H3',kind:'video',state:'candidate'}],
 assets:[{id:'img1',name:'hero.png',file:'i1.png',kind:'image'},{id:'v1',name:'t1.mp4',file:'v1.mp4',kind:'video'},{id:'v2',name:'t2.mp4',file:'v2.mp4',kind:'video'}],
 elements:[{id:'el1',kind:'character',tag:'艾伦',prompt_snippet:'white suit',asset_id:'img1'}],
 shots:[{id:'s1',title:'镜头1',prompt:'mars',duration:5,resolution:'1080P',model:'h3',seed:1,elements:['el1'],output:'v2',takes:[{id:'tk2',asset_id:'v2',seed:2},{id:'tk1',asset_id:'v1',seed:1}],versions:[]}],
 jobs:[],workflows:[]
};
selected='s1';
modelPresets=[{id:'wan22_i2v_14b_fp16',name:'Wan 2.2 FP16',approx_gb:71.1,model_files:[]}];
monitorState={enabled:true,urls:['http://192.168.1.10:8769/m/tok'],qr_svg:'<svg id="qr"></svg>'};
liveReceivedAt=Date.now();
live={runtime_state:'idle',account_ok:true,email:'u@example.com',balance:500,rate:0,active:0,can_start:true};
render=()=>{};
`,context);

// Shot inspector shows @艾伦 chip + Multi-Take gallery
let shotInsp=vm.runInContext("tab='shots';inspector()",context);
assert.match(shotInsp,/@艾伦/);
assert.match(shotInsp,/候选抽卡挑片/);
assert.match(shotInsp,/data-select-take="v1"/);

// Elements tab & inspector
let elemHtml=vm.runInContext("tab='elements';content()",context);
assert.match(elemHtml,/@艾伦/);
let elemInsp=vm.runInContext("inspector()",context);
assert.match(elemInsp,/id="elem-save"/);

// Workflows inspector shows G4 Full-Precision Preset selector
vm.runInContext("tab='workflows';workflowDraft={id:'w1',name:'Wan',kind:'video',revision:1,graph:{'1':{class_type:'SaveVideo',inputs:{video:null}}},bindings:{},positions:{},model_files:[],custom_nodes:[],versions:[]};workflowNode='1'",context);
let wfInsp=vm.runInContext('inspector()',context);
assert.match(wfInsp,/id="preset-select"/);
assert.match(wfInsp,/Wan 2\.2 FP16/);

// Manager shows CU Budget Guardrail, budget paused banner & Mobile Read-Only Monitor QR
let mgrHtml=vm.runInContext('managerView()',context);
assert.match(mgrHtml,/id="maxcubudget"/);
assert.match(mgrHtml,/已达到本次会话设定的 CU 算力预算护栏上限/);
assert.match(mgrHtml,/id="monitor-toggle"/);
assert.match(mgrHtml,/<svg id="qr"><\/svg>/);

console.log('GC Labs 0.5.0 Elements, Multi-Takes, Full-Precision Presets, CU Budget & Mobile QR Monitor UI passed.');
