/* Local, static UI catalogs. User text and template substitutions never enter translation. */
var L = (() => {
 const catalogs=window.CineHarborLocales||{};
 const languages=[['en','English'],['zh-Hans','简体中文'],['zh-Hant','繁體中文'],['ja','日本語'],['ko','한국어']];
 let locale='en';try{const saved=localStorage.getItem('CineHarbor.locale');if(languages.some(([k])=>k===saved))locale=saved}catch{}
 const pattern=/[\u4e00-\u9fff][\u4e00-\u9fff，。；：、！？（）《》“”「」…]*/g;
 const safe=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function translate(value,html=false){
   const source=String(value);
   let result=source.replace(pattern,(key,offset)=>{
     let translated=locale==='zh-Hans'?key:(catalogs[locale]?.[key]??catalogs.en?.[key]??key);
     if(locale==='en'){
       if(/[A-Za-z0-9]/.test(source[offset-1]||'')&&/^[A-Za-z]/.test(translated))translated=' '+translated;
       if(/[A-Za-z0-9]/.test(source[offset+key.length]||'')&&/[A-Za-z]$/.test(translated))translated+=' ';
     }
     return html?safe(translated):translated;
   });
   if(locale==='en')result=result.replace(/[，。；：！？（）]/g,c=>({'，':',','。':'.','；':';','：':':','！':'!','？':'?','（':'(', '）':')'}[c]));
   return result;
 }

 const api={
  get locale(){return locale},languages,
  text(value){return translate(value,/<[a-z][a-z0-9-]*(?:\s|>)/i.test(value))},
  html(strings,...values){const markup=strings.some(x=>/<[a-z][a-z0-9-]*(?:\s|>)/i.test(x));return strings.reduce((s,part,i)=>s+translate(part,markup)+(i<values.length?values[i]:''),'')},
  message(key,fallback=""){return catalogs[locale]?.[key]??catalogs.en?.[key]??fallback},
  service(value){return translate(value)},
  policy(){
    const main=document.querySelector('main');if(!main)return;
    const walker=document.createTreeWalker(main,NodeFilter.SHOW_TEXT);const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
    for(const node of nodes)if(!['SCRIPT','STYLE'].includes(node.parentElement?.tagName))node.textContent=translate(node.textContent);
    for(const node of main.querySelectorAll('[data-policy-message]'))node.textContent=api.message(node.getAttribute('data-policy-message'),node.textContent);
    document.title=translate(document.title);
    const holder=document.createElement('div');holder.innerHTML=api.select();main.prepend(holder);api.bind();
  },
  select(){return `<label class="language-control"><span class="sr-only">Language</span><select id="ui-language" aria-label="Language">${languages.map(([key,name])=>`<option value="${key}" ${key===locale?'selected':''}>${name}</option>`).join('')}</select></label>`},
  bind(){const select=document.querySelector('#ui-language');if(!select)return;select.onchange=()=>{
    const next=select.value;
    const workflowPrompted=typeof workflowDirty!=='undefined'&&workflowDirty;
    if(typeof UI!=='undefined'&&UI.leaveGuards.some(guard=>!guard())){select.value=locale;return}
    if(api.dirty&&!workflowPrompted&&!confirm(api.text('切换语言会重新加载界面。请先保存修改。仍然继续？'))){select.value=locale;return}
    try{localStorage.setItem('CineHarbor.locale',next)}catch{select.value=locale;return}
    window.webkit?.messageHandlers?.localeChanged?.postMessage(next);location.reload();
  }},dirty:false
 };
 if(typeof document!=='undefined'){
  document.documentElement.lang=locale;document.documentElement.dir=locale==='ar'?'rtl':'ltr';
  document.addEventListener('input',event=>{if(event.target?.id!=='ui-language'&&event.target?.type!=='password')api.dirty=true},{capture:true});
 }
 window.webkit?.messageHandlers?.localeChanged?.postMessage(locale);
 window.GCLabsI18n=api;return api;
})();
