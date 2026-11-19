// Exercise stale snapshots, HTTP timeouts and preflight races without a GPU.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync(__dirname+'/web/app.js','utf8').split('(async()=>{try{[data,verified]')[0];
const addon=fs.readFileSync(__dirname+'/web/console-ui.js','utf8').split('syncOperations().then(')[0];
let requests=[],timers=[];
const ctx={AbortController,location:{pathname:'/manager'},document:{hidden:false,addEventListener(){},querySelector(){return null}},window:{LOCAL_KEY:'test',addEventListener(){}},setInterval(){},setTimeout(fn){timers.push(fn);return timers.length},clearTimeout(){},confirm:()=>true,fetch:async(path)=>{requests.push(path);return {ok:true,json:async()=>({})}}};
vm.createContext(ctx);vm.runInContext(app,ctx);vm.runInContext(addon,ctx);
vm.runInContext(`data={project:{name:'Test'},models:[],policy:{max_minutes:240}};function hardwareCompareView(){return ''};renderLive=()=>{};toast=(message)=>lastToast=message;`,ctx);
const setState=(extra='')=>vm.runInContext(`liveReceivedAt=Date.now();live={account_ok:true,runtime_state:'owned',can_stop:true,active:1,sessions:[]};${extra}`,ctx);
const enabled=(html,attr)=>!html.match(new RegExp('<button[^>]*'+attr+'[^>]*>'))[0].includes('disabled');
(async()=>{
 setState();assert.ok(enabled(vm.runInContext('managerView()',ctx),'id="stop"'));
 setState('liveReceivedAt-=31000');let html=vm.runInContext('managerView()',ctx);assert.ok(!enabled(html,'id="stop"'));assert.ok(!enabled(html,'data-control="restore"'));assert.ok(html.includes('超过30秒'));assert.ok(!html.includes('工作站会话已连接'));
 setState('live.account_ok=false');assert.ok(!enabled(vm.runInContext('managerView()',ctx),'data-control="restore"'));
 setState('runtimeBusy=true');assert.ok(!enabled(vm.runInContext('managerView()',ctx),'id="stop"'));vm.runInContext('runtimeBusy=false',ctx);
 // The state changes between the click and fresh server preflight: no POST.
 vm.runInContext(`refresh=async()=>{liveReceivedAt=Date.now();live={account_ok:true,runtime_state:'external',active:1,can_start:false}}`,ctx);
 await vm.runInContext(`control('start',{gpu:'G4'})`,ctx);assert.deepEqual(requests,[]);assert.match(vm.runInContext('lastToast',ctx),/未重复/);assert.equal(vm.runInContext('runtimeBusy',ctx),false);
 vm.runInContext(`refresh=async()=>{liveReceivedAt=Date.now();live={account_ok:true,runtime_state:'external',sessions:[]}}`,ctx);
 await vm.runInContext(`control('adopt',{endpoint:'gone'})`,ctx);assert.deepEqual(requests,[]);assert.match(vm.runInContext('lastToast',ctx),/已变化/);
 // Abort a hanging fetch; it must reject and never retry the operation.
 ctx.fetch=async(path,options)=>{requests.push(path);return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('aborted'),{name:'AbortError'}))))};
 timers=[];const timeout=vm.runInContext(`api('/api/operations',{action:'start'})`,ctx);timers.at(-1)();await assert.rejects(timeout,/不会自动重试/);assert.equal(requests.length,1);
 console.log('Live status expiry, account lock, preflight races and timeout passed; no cloud actions.');
})().catch(e=>{console.error(e);process.exitCode=1});
