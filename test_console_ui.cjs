const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync(__dirname+'/web/app.js','utf8').split('(async()=>{try{[data,verified]')[0];
const addon=fs.readFileSync(__dirname+'/web/console-ui.js','utf8').split('syncOperations().then(')[0];
const context={location:{pathname:'/manager'},document:{hidden:false,addEventListener(){},querySelector(){return null}},window:{LOCAL_KEY:'test',addEventListener(){}},setInterval(){},setTimeout(){},clearTimeout(){},AbortController,fetch:async()=>({ok:true,json:async()=>null})};
vm.createContext(context);vm.runInContext(app,context);
(async()=>{assert.equal(await vm.runInContext("api('/api/inspection')",context),null);vm.runInContext(addon,context);vm.runInContext("data={project:{name:'Test'},models:[],policy:{max_minutes:240}};function hardwareCompareView(){return ''}",context);
for(const state of ['idle','external','owned','unknown']){context.state=state;const html=vm.runInContext("liveReceivedAt=Date.now();live={runtime_state:state,account_ok:true,email:'test',active:state==='idle'?0:1,can_start:state==='idle',can_stop:state==='owned'};managerView()",context);assert.ok(!html.includes('<option>T4</option>'));const start=html.match(/<button[^>]*id="start"[^>]*>/)[0];const stop=html.match(/<button[^>]*id="stop"[^>]*>/)[0];assert.equal(!start.includes('disabled'),state==='idle');assert.equal(!stop.includes('disabled'),state==='owned');}
console.log('Nullable inspection and 4 native manager states passed.');})().catch(e=>{console.error(e);process.exitCode=1});
