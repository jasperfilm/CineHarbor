from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
items=json.loads((Path(__file__).with_name('source-fragments.json')).read_text())
langs=['en','zh-Hans','zh-Hant','ja','ko'];out={};coverage={}
for code in langs:
 p=ROOT/'web/locales'/f'{code}.json'
 d={x:x for x in items} if code=='zh-Hans' else json.loads(p.read_text())
 if code=='en': d.update(json.loads(Path(__file__).with_name('english-overrides.json').read_text()))
 missing=[x for x in items if x not in d]
 if missing: raise SystemExit(f'{code}: {len(missing)} missing translations')
 d.update(json.loads(Path(__file__).with_name('editorial-messages.json').read_text())[code])
 out[code]=d;coverage[code]=len(d)
(ROOT/'web/catalogs.js').write_text('window.CineHarborLocales='+json.dumps(out,ensure_ascii=False,separators=(',',':'))+';\n')
(ROOT/'web/locales/coverage.json').write_text(json.dumps({'default':'en','counts':coverage,'source_entries':len(items),'status':'translation drafts; native speaker review pending'},indent=2)+'\n')
print(coverage)
