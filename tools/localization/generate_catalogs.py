"""Developer-only offline translation draft generator. No user content or cloud compute."""
from pathlib import Path
import json,time,re,os
from mlx_lm import load,generate
from mlx_lm.sample_utils import make_sampler
from huggingface_hub import HfApi
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'web/locales'; OUT.mkdir(exist_ok=True)
items=json.loads((Path(__file__).with_name('source-fragments.json')).read_text())
langs=[('en','English'),('ja','Japanese'),('ko','Korean')]
repo='mlx-community/Qwen3-4B-Instruct-2507-4bit'
sha=HfApi().model_info(repo).sha
print('Loading local translation model',repo,sha,flush=True)
model,tok=load(repo,revision=sha)
(ROOT/'tools/localization/model-provenance.json').write_text(json.dumps(dict(repository=repo,revision=sha,license='Apache-2.0',purpose='Developer-only UI translation drafts; not bundled with app; no user content'),indent=2))
for code,name in langs:
 path=OUT/(code+'.json'); catalog=json.loads(path.read_text()) if path.exists() else {}; missing=[x for x in items if x not in catalog]
 for offset in range(0,len(missing),30):
  batch=missing[offset:offset+30]; payload={str(i):x for i,x in enumerate(batch)}
  system=f'You are a professional software UI translator for CineHarbor, a video production workspace. Translate Simplified Chinese UI text fragments to {name}. The fragments can be partial sentences adjoining numbers or brand names. Use concise natural software terminology. Return ONLY a JSON object with the SAME numeric string keys, each value a translation. Never add explanations, Markdown, HTML, untranslated Chinese, or extra keys. Preserve punctuation intent. Do not invent features or remove fee/privacy/consent warnings. Translate all entries. Use G4, GPU, CU, Colab, ComfyUI, MiniMax, AVFoundation unchanged when present.'
  prompt=tok.apply_chat_template([{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],tokenize=False,add_generation_prompt=True)
  raw=generate(model,tok,prompt=prompt,max_tokens=6500,sampler=make_sampler(temp=0),verbose=False)
  try:
   start=raw.index('{');result,_=json.JSONDecoder().raw_decode(raw[start:]); assert set(result)==set(payload);assert all(isinstance(v,str) and v.strip() for v in result.values())
  except Exception as e:
   (OUT/f'{code}-batch-{offset}-failed.txt').write_text(raw);print('INVALID',code,offset,type(e).__name__,flush=True);continue
  catalog.update({x:result[str(i)].strip() for i,x in enumerate(batch)});path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n');print('SAVED',code,len(catalog),'/',len(items),time.strftime('%H:%M:%S'),flush=True)
 print('LANGUAGE',code,'complete',len(catalog)==len(items),flush=True)
