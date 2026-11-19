"""Import a backup as a new project without restoring credentials or live jobs."""
import io,json,zipfile,stat,uuid,hashlib
from pathlib import PurePosixPath

def import_project(server,raw):
 if len(raw)>100_000_000:raise ValueError('备份请小于100MB')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  entries=z.infolist()
  if len(entries)>5000 or sum(x.file_size for x in entries)>2_000_000_000:raise ValueError('备份解压规模超过限制')
  for item in entries:
   path=PurePosixPath(item.filename)
   if path.is_absolute() or '..' in path.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr>>16):raise ValueError('备份包含不安全路径')
  d=json.loads(z.read('workspace.json'))
  if not isinstance(d,dict) or not all(k in d for k in ('project','assets','shots')):raise ValueError('缺少工作区数据')
  if d['project'].get('ratio','9:16') not in ('9:16','16:9','1:1'):raise ValueError('不支持的画幅')
  for shot in d['shots']:
   limit=600 if shot.get('model')=='workflow' and any(w.get('id')==shot.get('workflow') and w.get('kind')=='audio' for w in d.get('workflows',[])) else 15
   if not 1<=float(shot['duration'])<=limit or shot['resolution'] not in ('480P','720P','768P','1080P'):raise ValueError('镜头参数不受支持')
   if shot['model'] not in ({m['id'] for m in server.MODELS}|{'workflow'}):raise ValueError('镜头模型未注册')
  from workflow_library import recipe
  workflows=[]
  for item in d.get('workflows',[]):
   validated=recipe(item);validated['id']=item['id'];workflows.append(validated)
  d['workflows']=workflows
  # Validate everything before writing any asset. Only bundled media are restored.
  assets=[];mapping={};missing=0
  for asset in d['assets']:
   name=asset.get('file','');path='assets/'+name
   if PurePosixPath(name).name!=name or path not in z.namelist():missing+=1;continue
   suffix=PurePosixPath(name).suffix.lower()
   if suffix not in ('.png','.jpg','.jpeg','.webp','.mp4','.webm','.wav','.mp3','.flac','.ogg','.m4a'):raise ValueError('备份包含未知素材格式')
   blob=z.read(path);sha=hashlib.sha256(blob).hexdigest()
   if asset.get('sha256') and asset['sha256']!=sha:raise ValueError('备份素材校验失败')
   ident=uuid.uuid4().hex;mapping[asset['id']]=ident
   assets.append(({'id':ident,'name':str(asset.get('name',name)),'file':ident+suffix,'kind':asset['kind'],'sha256':sha,'created':server.now()},blob))
  d['project'].update(id=uuid.uuid4().hex,name=str(d['project']['name'])+'（备份恢复）');d['project'].pop('final_file',None)
  d['assets']=[a for a,_ in assets]
  elem_map={}
  restored_elems=[]
  for el in d.get('elements',[]):
   if not isinstance(el,dict) or not el.get('tag'):continue
   nid=uuid.uuid4().hex;elem_map[el.get('id')]=nid
   restored_elems.append({'id':nid,'tag':str(el['tag'])[:40],'kind':el.get('kind','character'),'prompt_snippet':str(el.get('prompt_snippet',''))[:1000],'asset_id':mapping.get(el.get('asset_id')),'created':server.now()})
  d['elements']=restored_elems
  for shot in d['shots']:
   shot['id']=uuid.uuid4().hex;shot['reference']=mapping.get(shot.get('reference'));shot['output']=mapping.get(shot.get('output'))
   shot['elements']=[elem_map[eid] for eid in (shot.get('elements') or []) if eid in elem_map]
   shot['takes']=[dict(t,id=uuid.uuid4().hex,asset_id=mapping[t['asset_id']]) for t in (shot.get('takes') or []) if isinstance(t,dict) and t.get('asset_id') in mapping]
   shot['versions']=[dict(v,reference=mapping.get(v.get('reference')),output=mapping.get(v.get('output'))) for v in shot.get('versions',[]) if isinstance(v,dict)]
  d['historical_jobs']=d.pop('jobs',[])+d.get('historical_jobs',[]);d['jobs']=[];d['schema_version']=2
  d['models']=server.MODELS;d['policy']=server.load()['policy'];d['events']=[{'time':server.now(),'text':'从本机备份导入独立项目；历史任务不会自动提交。'}]
  old=server.load();folder=server.DATA/'projects';folder.mkdir(exist_ok=True)
  (folder/(old['project']['id']+'.json')).write_text(json.dumps(old,ensure_ascii=False,indent=2))
  for asset,blob in assets:(server.ASSETS/asset['file']).write_bytes(blob)
  server.save(d)
  return {'project':d['project'],'assets':len(assets),'missing_external_assets':missing}
