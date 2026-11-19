// Render the real manager against representative server responses. No Colab calls.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/web/app.js','utf8').split('(async()=>{try{[data,verified]')[0];
const ctx={location:{pathname:'/manager'},document:{addEventListener(){}},window:{addEventListener(){}},setInterval(){}};
vm.createContext(ctx);vm.runInContext(source,ctx);
vm.runInContext(`data={policy:{max_minutes:240},events:[]};verified={backup_path:'backup',comfy_revision:'test'};function hardwareCompareView(){return ''}`,ctx);
function check(state,start,stop,label){
 ctx.response=state;
 const html=vm.runInContext('live=response;managerView()',ctx);
 for(const [id,enabled] of [['start',start],['stop',stop]]){
  const tag=html.match(new RegExp('<button[^>]*id="'+id+'"[^>]*>'))[0];
  assert.equal(!tag.includes('disabled'),enabled,label+':'+id);
 }
 assert.ok(html.includes(label));
}
const base={account_ok:true,email:'test',balance:1,rate:0,active:0,sessions:[],can_start:true,can_stop:false,runtime_state:'idle'};
check(base,true,false,'当前没有活动会话');
check({...base,active:1,can_start:false,runtime_state:'external',sessions:[{name:'?',endpoint:'manual',hardware:'G4'}]},false,false,'已有外部会话');
check({...base,active:1,can_start:false,can_stop:true,runtime_state:'owned'},false,true,'工作站会话已连接');
check({error:'offline'},false,false,'状态未确认');
check({...base,can_start:false,runtime_state:'unknown'},false,false,'会话数据核对中');
console.log('5 runtime UI scenarios passed; no VM allocated or released.');
