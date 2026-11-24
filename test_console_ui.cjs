const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync(__dirname+'/web/app.js','utf8').split('(async()=>{try{[data,verified]')[0];
const addon=fs.readFileSync(__dirname+'/web/console-ui.js','utf8').split('syncOperations().then(')[0];
const context={location:{pathname:'/manager'},document:{hidden:false,addEventListener(){},querySelector(){return null}},window:{LOCAL_KEY:'test',addEventListener(){}},setInterval(){},setTimeout(){},clearTimeout(){},AbortController,fetch:async()=>({ok:true,json:async()=>null})};
vm.createContext(context);vm.runInContext(app,context);
(async()=>{assert.equal(await vm.runInContext("api('/api/inspection')",context),null);vm.runInContext(addon,context);vm.runInContext("data={project:{name:'Test'},models:[],policy:{max_minutes:240}};function hardwareCompareView(){return ''}",context);
for(const state of ['idle','external','owned','unknown']){context.state=state;const html=vm.runInContext("liveReceivedAt=Date.now();live={runtime_state:state,account_ok:true,email:'test',active:state==='idle'?0:1,can_start:state==='idle',can_stop:state==='owned'};managerView()",context);assert.ok(!html.includes('<option>T4</option>'));const start=html.match(/<button[^>]*id="start"[^>]*>/)[0];const stop=html.match(/<button[^>]*id="stop"[^>]*>/)[0];assert.equal(!start.includes('disabled'),state==='idle');assert.equal(!stop.includes('disabled'),state==='owned');}
vm.runInContext("data.jobs=[{id:'draft',title:'Draft',state:'prepared',config:{}}];operations=[]",context);
assert.match(vm.runInContext('UI.views.jobs()',context),/data-archive-job="draft"/);
vm.runInContext("operations=[{id:'queued',job_id:'draft',state:'queued',action:'generate'}]",context);
assert.doesNotMatch(vm.runInContext('UI.views.jobs()',context),/data-archive-job="draft"/);
vm.runInContext("projectFileBusy=true;verified={};render=()=>{throw Error('Picker input replaced')};renderLive();projectFileBusy=false",context);
context.submit = async (path, body) => {
  assert.equal(path, '/api/operations');
  context.submissions.push(JSON.parse(JSON.stringify(body)));
  return {accepted: true};
};
context.submissions = [];
context.confirmations = [];
context.confirm = copy => { context.confirmations.push(copy); return true; };
context.L = {text: value => value, html: (parts, ...values) => String.raw({raw: parts}, ...values)};
vm.runInContext(`
  operations=[];
  refresh=async()=>{};
  syncOperations=async()=>{};
  liveUsable=()=>true;
  live={runtime_state:'owned',account_ok:true};
  action=async run=>run();
  renderLive=()=>{};
  toast=()=>{};
  api=submit;
`, context);
for (const [action, jobs] of [['generate', {job: 'a'}], ['generate_batch', {jobs: ['a','b']}]]) {
  context.args = [action, jobs];
  assert.equal((await vm.runInContext('control(...args)', context))?.accepted, true);
  assert.deepEqual(context.submissions.at(-1), {
    action, ...jobs, cloud_data_consent: true, cloud_data_notice_version: '2026-11-21'
  });
}
assert.equal(context.confirmations.length, 2);
assert.ok(context.confirmations.every(copy => copy.includes('Google Colab')));
console.log('Manager states and single/batch submission with only cloud data consent passed.');})().catch(e=>{console.error(e);process.exitCode=1});
