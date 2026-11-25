"""Import a backup as a new project without restoring credentials or live jobs."""
import io,json,zipfile,stat,uuid,hashlib,tempfile,shutil
from pathlib import PurePosixPath

def import_project(server,raw):
 if len(raw)>100_000_000:raise ValueError('备份请小于100MB')
 return import_project_file(server,io.BytesIO(raw))

def import_project_file(server,source):
 with tempfile.TemporaryDirectory(prefix='cineharbor-restore-',dir=server.DATA) as staging, zipfile.ZipFile(source) as z:
  entries=z.infolist()
  if len(entries)>100000 or sum(x.file_size for x in entries)>100*1024**3:raise ValueError('备份解压规模超过限制')
  for item in entries:
   path=PurePosixPath(item.filename)
   if path.is_absolute() or '..' in path.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr>>16):raise ValueError('备份包含不安全路径')
  if len({x.filename for x in entries})!=len(entries):raise ValueError('备份包含重复路径')
  if z.getinfo('workspace.json').file_size>32*1024**2:raise ValueError('工作区记录过大')
  if shutil.disk_usage(server.DATA).free<sum(x.file_size for x in entries):raise ValueError('本机磁盘空间不足，无法恢复')
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
   from pathlib import Path
   blob=Path(staging)/uuid.uuid4().hex;h=hashlib.sha256()
   with z.open(path) as src,blob.open('wb') as dst:
    for block in iter(lambda:src.read(1024*1024),b''):
     dst.write(block);h.update(block)
   sha=h.hexdigest()
   if asset.get('sha256') and asset['sha256']!=sha:raise ValueError('备份素材校验失败')
   ident=uuid.uuid4().hex;mapping[asset['id']]=ident
   assets.append(({'id':ident,'name':str(asset.get('name',name)),'file':ident+suffix,'kind':asset['kind'],'sha256':sha,'created':server.now()},blob))
  d['project'].update(id=uuid.uuid4().hex,name=str(d['project']['name'])+' (Restored)');d['project'].pop('final_file',None)
  d['assets']=[a for a,_ in assets]
  if d['project'].get('latest_export_asset'):
   d['project']['latest_export_asset']=mapping.get(d['project']['latest_export_asset'])
  final_id=mapping.get(d.pop('portable_final_asset_id',None))
  if final_id:
   final_asset=next(a for a in d['assets'] if a['id']==final_id)
   d['project']['final_file']=str(server.ASSETS/final_asset['file'])
  elem_map={}
  restored_elems=[]
  for el in d.get('elements',[]):
   if not isinstance(el,dict) or not el.get('tag'):continue
   nid=uuid.uuid4().hex;elem_map[el.get('id')]=nid
   restored_elems.append({'id':nid,'tag':str(el['tag'])[:40],'kind':el.get('kind','character'),'prompt_snippet':str(el.get('prompt_snippet',''))[:1000],'asset_id':mapping.get(el.get('asset_id')),'voice_asset_id':mapping.get(el.get('voice_asset_id')),'voice_profile':str(el.get('voice_profile') or '')[:240],'voice_reference_mode':'reference_only','created':server.now()})
  d['elements']=restored_elems
  shot_map={s['id']:uuid.uuid4().hex for s in d['shots']}
  for shot in d['shots']:
   shot['id']=shot_map[shot['id']];shot['reference']=mapping.get(shot.get('reference'));shot['end_reference']=mapping.get(shot.get('end_reference'));shot['output']=mapping.get(shot.get('output'))
   shot.pop('qc_strip_file',None)  # Derived filmstrips can be regenerated from the restored video.
   shot['elements']=[elem_map[eid] for eid in (shot.get('elements') or []) if eid in elem_map]
   shot['takes']=[dict(t,id=uuid.uuid4().hex,asset_id=mapping[t['asset_id']]) for t in (shot.get('takes') or []) if isinstance(t,dict) and t.get('asset_id') in mapping]
   shot['versions']=[dict(v,reference=mapping.get(v.get('reference')),end_reference=mapping.get(v.get('end_reference')),output=mapping.get(v.get('output')),elements=[elem_map[eid] for eid in (v.get('elements') or []) if eid in elem_map]) for v in shot.get('versions',[]) if isinstance(v,dict)]
  if isinstance(d.get('assembly'),dict):
   from timeline_export import assembly_settings
   settings=dict(d['assembly']);settings['audio_asset_id']=mapping.get(settings.get('audio_asset_id'))
   settings['clips']=[dict(c,shot_id=shot_map[c['shot_id']],asset_id=mapping[c['asset_id']]) for c in settings.get('clips',[]) if c.get('shot_id') in shot_map and c.get('asset_id') in mapping]
   d['assembly']=assembly_settings(d,settings)
  d['historical_jobs']=d.pop('jobs',[])+d.get('historical_jobs',[])
  for job in d['historical_jobs']:
   if not isinstance(job,dict):continue
   if 'shot' in job:job['shot']=shot_map.get(job['shot'])
   if isinstance(job.get('results'),list):job['results']=[mapping[aid] for aid in job['results'] if aid in mapping]
   for field in ('config','shot_snapshot'):
    config=job.get(field)
    if not isinstance(config,dict):continue
    for key in ('reference','end_reference','output'):
     if key in config:config[key]=mapping.get(config[key])
    if isinstance(config.get('elements'),list):config['elements']=[elem_map[eid] for eid in config['elements'] if eid in elem_map]
  d['jobs']=[];d['schema_version']=2
  d['models']=server.MODELS;d['policy']=server.load()['policy'];d['events']=[{'time':server.now(),'text':'从本机备份导入独立项目；历史任务不会自动提交。'}]
  old=server.load();folder=server.DATA/'projects';folder.mkdir(exist_ok=True)
  (folder/(old['project']['id']+'.json')).write_text(json.dumps(old,ensure_ascii=False,indent=2), encoding='utf-8')
  for asset,blob in assets:shutil.move(str(blob),str(server.ASSETS/asset['file']))
  server.save(d)
  return {'project':d['project'],'assets':len(assets),'missing_external_assets':missing}
