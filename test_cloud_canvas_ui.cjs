const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync(__dirname+'/web/app.js','utf8').split('(async()=>{try{[data,verified]')[0];
const addon=fs.readFileSync(__dirname+'/web/console-ui.js','utf8').split('syncOperations().then(')[0];
const button={disabled:false,textContent:''};let alerts=[],posts=[],confirms=0,ready=false,opStates=[],endpoint='g4',accept=true,refreshCount=0,changeSession=false;
const ctx={location:{pathname:'/studio',href:'/studio'},document:{hidden:false,addEventListener(){},querySelector(s){return s==='#comfy-canvas'?button:null}},window:{LOCAL_KEY:'isolated',addEventListener(){}},AbortController,setInterval(){},setTimeout(fn){fn();return 0},clearTimeout(){},alert(x){alerts.push(x)},confirm(){confirms++;return accept}};
vm.createContext(ctx);vm.runInContext(app,ctx);vm.runInContext(addon,ctx);
ctx.apiMock=async(path,body)=>{
 if(path==='/api/bridge')return {ready,endpoint:'g4',url:'http://127.0.0.1:8767/'};
 if(path==='/api/operations'&&body){posts.push(body);return {id:'new-bridge',state:'queued'}};
 if(path==='/api/operations'){const state=opStates.shift()||'succeeded';if(state==='succeeded')ready=true;return [{id:'new-bridge',action:'bridge',state,message:'ComfyUI environment unavailable'}]}
 throw Error('Unexpected '+path);
};
ctx.refreshMock=()=>{refreshCount++;ctx.ownerEndpoint=changeSession&&refreshCount>=3?'other':endpoint;vm.runInContext("liveReceivedAt=Date.now();live={account_ok:true,runtime_state:ownerEndpoint?'owned':'idle',managed_session:{endpoint:ownerEndpoint}}",ctx)};
vm.runInContext("api=(...args)=>apiMock(...args);refresh=async()=>refreshMock();syncOperations=async()=>{};toast=()=>{}",ctx);
function reset(){alerts=[];posts=[];confirms=0;ready=false;opStates=[];endpoint='g4';accept=true;refreshCount=0;changeSession=false;ctx.location.href='/studio';vm.runInContext("operations=[];runtimeBusy=false;cloudCanvasOpening=false",ctx)}
(async()=>{
 reset();endpoint='';await vm.runInContext('openCloudCanvas()',ctx);assert.equal(posts.length,0);assert.match(alerts[0],/Colab 管理/);assert.equal(ctx.location.href,'/studio');assert.equal(button.disabled,false);
 reset();ready=true;await vm.runInContext('openCloudCanvas()',ctx);assert.equal(confirms,1);assert.equal(posts.length,0);assert.equal(ctx.location.href,'http://127.0.0.1:8767/');
 reset();opStates=['running','succeeded'];await vm.runInContext('openCloudCanvas()',ctx);assert.equal(posts.length,1);assert.equal(posts[0].action,'bridge');assert.equal(ctx.location.href,'http://127.0.0.1:8767/','First click must continue into the canvas after connecting');assert.equal(button.disabled,false);
 reset();accept=false;await vm.runInContext('openCloudCanvas()',ctx);assert.equal(posts.length,0);assert.equal(ctx.location.href,'/studio');
 reset();opStates=['failed'];await vm.runInContext('openCloudCanvas()',ctx);assert.equal(posts.length,1);assert.match(alerts[0],/ComfyUI environment unavailable/);assert.equal(ctx.location.href,'/studio');
 reset();opStates=['succeeded'];changeSession=true;await vm.runInContext('openCloudCanvas()',ctx);assert.match(alerts[0],/会话或画布连接已变化/);assert.equal(ctx.location.href,'/studio');
 reset();vm.runInContext('cloudCanvasOpening=true',ctx);await vm.runInContext('openCloudCanvas()',ctx);assert.equal(posts.length,0);assert.equal(refreshCount,0);
 reset();opStates=Array(5).fill('running');let clock=1;ctx.clock=()=>clock;vm.runInContext('Date.now=()=>clock()',ctx);ctx.setTimeout=fn=>{clock+=100000;fn();return 0};await vm.runInContext('openCloudCanvas()',ctx);assert.match(alerts[0],/仍在连接/);assert.equal(posts.length,1);assert.equal(ctx.location.href,'/studio');
 assert.ok(posts.every(p=>p.action==='bridge'));console.log('Cloud canvas: idle, ready, first-click connect, cancel, failure, session change, repeated click and bounded timeout passed; no GPU allocated.');
})().catch(e=>{console.error(e);process.exitCode=1});
