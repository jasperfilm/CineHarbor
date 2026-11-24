/* Local, optional model-license information. */
(() => {
 const catalog=window.CineHarborModelTermsCopy;
 const text=()=>catalog[L.locale]||catalog.en;
 const sources=[['MiniMax H3 License (offline copy)','/licenses/models/MiniMax-H3-LICENSE.txt'],['MiniMax H3 License','https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE'],['MiniMax H3 License Q&A','https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/QA-about-License.md'],['Wan 2.2','https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B'],['LTX 2.5','https://huggingface.co/Lightricks/LTX-2.5'],['Qwen Image','https://huggingface.co/Qwen/Qwen-Image-2512']];
 const element=(tag,value,parent)=>{const e=document.createElement(tag);if(value)e.textContent=value;if(parent)parent.append(e);return e};
 const link=(title,url,parent)=>{const a=element('a',title,parent);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a};
 function showNotice(notice){
  if(document.getElementById('model-terms-dialog'))return;
  const t=text();
  const dialog=element('dialog');
  dialog.id='model-terms-dialog';
  dialog.className='model-terms-dialog';
  dialog.setAttribute('aria-labelledby','model-terms-title');
  element('h2',t.title,dialog).id='model-terms-title';
  element('p',t.intro,dialog);
  element('p',t.responsibility,dialog);
  element('h3',notice.name,dialog);
  element('p',notice.id==='minimax-h3'?t.h3:t.unknown,dialog);
  for(const source of notice.links)link(source.title,source.url,element('p','',dialog));
  element('p',t.local,dialog);

  const close=element('button',t.close,dialog);
  close.type='button';
  close.onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
 }
 if(document.getElementById('model-terms-page')){
  const parent=document.getElementById('model-terms-page'),t=text();L.policy();document.title=t.title;element('h1',t.title,parent);
  for(const value of [t.intro,t.responsibility,t.h3,t.unknown,t.local])element('p',value,parent);
  element('h2',t.source,parent);for(const [title,url]of sources)link(title,url,element('p','',parent));const a=element('a',t.back,element('p','',parent));a.href='/studio';
 }
 if(typeof UI!=='undefined'){
  UI.shotFooterActions.push(()=>`<p><button type="button" id="review-model-terms">${esc(text().open)}</button> · <a href="/model-terms.html" target="_blank" rel="noopener">${esc(text().source)}</a></p>`);
  UI.binders.push(()=>{
   const button=document.getElementById('review-model-terms');
   if(!button)return;
   button.onclick=()=>action(async()=>{
    const notice=await api('/api/model-terms',{
     model:document.getElementById('model')?.value,
     workflow:document.getElementById('shot-workflow')?.value
    });
    showNotice(notice);
   });
  });
 }
})();
