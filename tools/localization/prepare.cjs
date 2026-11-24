const fs=require('fs'),path=require('path');const acorn=require('acorn');
const root=path.resolve(__dirname,'../..'),web=path.join(root,'web');const inventory=new Set();const zh=/[\u4e00-\u9fff]/;const fragments=/[\u4e00-\u9fff][\u4e00-\u9fff，。；：、！？（）《》“”「」…]*/g;
for(const name of fs.readdirSync(web).filter(x=>x.endsWith('.js')&&!['brand.js','i18n.js'].includes(x))){
 const filename=path.join(web,name),source=fs.readFileSync(filename,'utf8'),ast=acorn.parse(source,{ecmaVersion:'latest'}),edits=[];
 function walk(n,parent){if(!n||typeof n!=='object')return;
  if(n.type==='Literal'&&typeof n.value==='string'&&zh.test(n.value)&&!(parent?.type==='Property'&&parent.key===n&&!parent.computed)){
   for(const f of n.value.matchAll(fragments))inventory.add(f[0]);if(!(parent?.type==='CallExpression'&&parent.callee?.object?.name==='L'&&parent.callee?.property?.name==='text'))edits.push({at:n.start,s:'L.text('},{at:n.end,s:')'});
  }
  if(n.type==='TemplateLiteral'&&n.quasis.some(q=>zh.test(q.value.raw))){
   n.quasis.forEach(q=>{for(const f of q.value.raw.matchAll(fragments))inventory.add(f[0])});if(!(parent?.type==='TaggedTemplateExpression'&&parent.tag?.object?.name==='L'&&parent.tag?.property?.name==='html'))edits.push({at:n.start,s:'L.html'});
  }
  for(const [key,v] of Object.entries(n))if(!['start','end','loc'].includes(key)){if(Array.isArray(v))v.forEach(x=>walk(x,n));else if(v&&typeof v==='object')walk(v,n)}
 }
 walk(ast);let transformed=source;for(const e of edits.sort((a,b)=>b.at-a.at))transformed=transformed.slice(0,e.at)+e.s+transformed.slice(e.at);
 acorn.parse(transformed,{ecmaVersion:'latest'});fs.writeFileSync(filename,transformed);
}
fs.writeFileSync(path.join(root,'tools/localization/source-fragments.json'),JSON.stringify([...inventory].sort((a,b)=>b.length-a.length),null,2)+'\n');
console.log('localizable static fragments',inventory.size);
