const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const content=fs.readFileSync(__dirname+'/web/policy-content.js','utf8');
const render=fs.readFileSync(__dirname+'/web/policy-page.js','utf8');
for(const locale of ['en','zh-Hans','zh-Hant','ja','ko','unsupported']){
 for(const kind of ['privacy','terms','support']){
  const element=()=>({textContent:'',childNodes:[],append(...nodes){this.childNodes.push(...nodes)}});
  const nodes={'h1':element(),'#policy-sections':element(),'#policy-links':element()};
  const ctx={window:{},L:{locale,policy(){},message(_key,fallback){return fallback}},document:{currentScript:{dataset:{policyKind:kind}},title:'',querySelector(key){return nodes[key]},createElement:element,createTextNode(text){return {textContent:text}}}};
  vm.createContext(ctx);vm.runInContext(content,ctx);vm.runInContext(render,ctx);
  const expected=ctx.window.CineHarborPolicyContent[locale]||ctx.window.CineHarborPolicyContent.en;
  const publicCopy=JSON.stringify(expected[kind]);
  assert.ok(!/Sihao\s+Jia|GachaFrame LLC|individual developer|个人开发者|個人開發者|個人開発者|개인 개발자/i.test(publicCopy),'No personal developer identity or internal ownership explanation in public policy copy');
  assert.ok(!/\/Users\/|file:\/\/|Apple Distribution:/.test(publicCopy),'No private filesystem or signing identity in policy copy');
  assert.ok((publicCopy.match(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi)||[]).every(email=>email==='contact@gachaframe.com'),'Only the approved public support mailbox is disclosed');
  assert.equal(ctx.document.title,expected[kind].title);
  assert.equal(nodes.h1.textContent,expected[kind].title);
  assert.equal(nodes['#policy-sections'].childNodes.length,expected[kind].sections.length*2);
  const bodies=nodes['#policy-sections'].childNodes.filter((_,i)=>i%2).map(x=>x.textContent);
  assert.deepEqual(bodies,Array.from(expected[kind].sections,x=>x.body));
  assert.ok(!bodies.some(x=>/Internal policy review|尚未发布或生效/.test(x)));
  assert.ok(nodes['#policy-links'].childNodes.some(x=>x.href==='/opensource.html'));
  if(locale==='en'||locale==='unsupported')assert.ok(!bodies.some(x=>/[\u4e00-\u9fff]/.test(x)));
 }
}
console.log('All five locales and English fallback render complete offline policies without fragment translation or draft status; source-license link retained.');
