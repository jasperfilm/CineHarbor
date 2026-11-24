/* Static, offline policy text shared with the release website. No user data. */
(() => {
 const kind=document.currentScript.dataset.policyKind;
 const catalog=window.CineHarborPolicyContent[L.locale]||window.CineHarborPolicyContent.en;
 const page=catalog[kind];
 L.policy();
 document.title=page.title;
 document.querySelector('h1').textContent=page.title;
 for(const section of page.sections){
  const title=document.createElement('h2');title.textContent=section.title;
  const body=document.createElement('p');body.textContent=section.body;
  document.querySelector('#policy-sections').append(title,body);
 }
 const links=document.querySelector('#policy-links');
 for(const [href,label] of [['/studio',L.message('licenses.back','Back to the workspace')],
  ...['privacy','terms','support'].filter(k=>k!==kind).map(k=>['/'+k+'.html',catalog[k].title]),
  ['/opensource.html',L.message('licenses.title','Open-source licenses')],
  ['/model-terms.html',window.CineHarborModelTermsCopy?.[L.locale]?.title||'Model licenses & usage'],
  ['https://www.apple.com/legal/internet-services/itunes/dev/stdeula/','Apple Standard EULA'],
  ['https://policies.google.com/privacy','Google Privacy Policy']]){
  if(links.childNodes.length)links.append(document.createTextNode(' · '));
  const link=document.createElement('a');link.href=href;link.textContent=label;
  if(href.startsWith('https:')){link.target='_blank';link.rel='noopener noreferrer'}
  links.append(link);
 }
})();
