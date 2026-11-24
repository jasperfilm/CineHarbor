"""Non-executing storyboard handoff. No cloud calls or credentials."""
import base64, hashlib, copy, json
from pathlib import Path
from workflow_library import materialize, validate_graph


def _prepare_generation(workspace, assets_dir, shot_ids=None, inline_images=True):
    shots = workspace.get('shots', [])
    if shot_ids is not None:
        wanted = set(shot_ids)
        if not wanted or wanted - {s['id'] for s in shots}:
            raise ValueError('Select existing shots for the handoff.')
        shots = [s for s in shots if s['id'] in wanted]
    if not shots:
        raise ValueError('Add a shot before preparing a ComfyUI handoff.')
    workflows = {w['id']: w for w in workspace.get('workflows', [])}
    assets = {a['id']: a for a in workspace.get('assets', [])}
    elements = {e['id']: e for e in workspace.get('elements', [])}
    images, graph, layout, sections = {}, {}, {}, []
    asset_names = {}
    total_image_bytes = 0
    next_id = 1
    ratio = workspace.get('project', {}).get('ratio', '16:9')

    def image(ident):
        nonlocal total_image_bytes
        if ident in asset_names:
            return asset_names[ident]
        a = assets.get(ident)
        if not a or a.get('kind') != 'image':
            raise ValueError('A selected shot reference is missing or is not an image.')
        filename = str(a.get('file', ''))
        if Path(filename).name != filename or filename in ('', '.', '..'):
            raise ValueError('The reference filename is invalid.')
        path = Path(a['path']) if not inline_images and a.get('path') else Path(assets_dir) / filename
        if not path.is_file() or path.is_symlink():
            raise ValueError('A selected reference file is unavailable locally.')
        if inline_images and path.stat().st_size > 25 * 1024 ** 2:
            raise ValueError('A reference exceeds the 25 MB handoff limit.')
        from comfy_project_store import digest as file_digest
        digest = file_digest(path)
        raw = path.read_bytes() if inline_images else b''
        name = 'cineharbor_' + digest[:24] + path.suffix.lower()
        if name not in images:
            total_image_bytes += len(raw)
        if total_image_bytes > 20 * 1024 ** 2:
            raise ValueError('Combined references exceed 20 MB. Select fewer shots or smaller references.')
        images[name] = dict(name=name, sha256=digest)
        if inline_images: images[name]['base64'] = base64.b64encode(raw).decode()
        asset_names[ident] = name
        return name

    for index, shot in enumerate(shots):
        item = workflows.get(shot.get('workflow'))
        if not item:
            raise ValueError(f'Shot {index + 1}: select and save a model workflow first.')
        bound = [elements[e] for e in shot.get('elements', []) if e in elements]
        prompt = shot.get('prompt', '').strip()
        snippets = [e['prompt_snippet'] for e in bound if e.get('prompt_snippet') and e['prompt_snippet'] not in prompt]
        voices = [f"[{e.get('tag', 'Reference')} vocal timbre: {e['voice_profile']}]" for e in bound if e.get('voice_profile') and e['voice_profile'] not in prompt]
        prompt = ' '.join(snippets + voices + [prompt]).strip()
        if not prompt:
            raise ValueError(f'Shot {index + 1}: enter a prompt first.')
        if shot.get('dialogue'):
            raise ValueError(f'Shot {index + 1}: include dialogue in the workflow prompt before handoff.')
        ref = shot.get('reference') or next((e['asset_id'] for e in bound if e.get('asset_id')), None)
        binds = item.get('bindings', {})
        if binds.get('reference') and not ref:
            raise ValueError(f'Shot {index + 1}: this workflow requires a reference image.')
        if ref and not binds.get('reference'):
            raise ValueError(f'Shot {index + 1}: this workflow has no reference binding.')
        if shot.get('end_reference') and not binds.get('end_reference'):
            raise ValueError(f'Shot {index + 1}: this workflow has no last-frame binding.')
        width, height = {'480P': (848, 480), '720P': (1280, 736), '768P': (1360, 768), '1080P': (1920, 1088)}[shot.get('resolution', '1080P')]
        if ratio == '9:16': width, height = height, width
        if ratio == '1:1': width = height = min(width, height)
        timing = item.get('timing') or dict(fps=24, frame_multiple=4, frame_offset=1)
        fps = float(timing['fps']); frames = max(1, round(float(shot['duration']) * fps))
        frames += (int(timing['frame_offset']) - frames % int(timing['frame_multiple'])) % int(timing['frame_multiple'])
        values = dict(prompt=prompt, seed=int(shot['seed']), width=width, height=height, frames=frames, duration=float(shot['duration']), fps=fps)
        if shot.get('negative_prompt'): values['negative_prompt'] = shot['negative_prompt']
        if ref: values['reference'] = image(ref)
        if shot.get('end_reference'): values['end_reference'] = image(shot['end_reference'])
        part = materialize(item, values)
        ids = {old: str(next_id + n) for n, old in enumerate(part)}; next_id += len(ids)
        positions = item.get('positions') or {}
        origin = [float(shot.get('x', 220 + index * 820)) * 8, float(shot.get('y', 80)) * 8]
        for n, (old, node) in enumerate(part.items()):
            for key, val in node['inputs'].items():
                if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) and isinstance(val[1], int):
                    node['inputs'][key] = [ids[val[0]], val[1]]
            title = node.get('_meta', {}).get('title') or node['class_type']
            node.setdefault('_meta', {})['title'] = f'{index + 1:02d} · {shot["title"]} / {title}'
            if 'filename_prefix' in node['inputs']: node['inputs']['filename_prefix'] = f'cineharbor/shot_{index + 1:02d}'
            graph[ids[old]] = node
            local = positions.get(old, [(n % 5) * 380, (n // 5) * 440])
            layout[ids[old]] = [origin[0] + float(local[0]), origin[1] + float(local[1])]
        sections.append(dict(shot_id=shot['id'], title=shot['title'], node_ids=list(ids.values()), workflow=item['name'], width=width, height=height, fps=fps, frames=frames))
    validate_graph(graph)
    return dict(schema='cineharbor.comfy-handoff.v1', project=workspace['project']['name'], graph=graph, positions=layout, shots=sections, images=list(images.values()), execution='Import only. Never queued automatically.', round_trip=False)


def prepare(workspace, assets_dir, shot_ids=None, include_assets=False, asset_ids=None):
    if not include_assets:
        return _prepare_generation(workspace, assets_dir, shot_ids)
    from comfy_project_store import digest
    all_shots = workspace.get('shots', [])
    wanted = set(shot_ids) if shot_ids is not None else {s['id'] for s in all_shots}
    if shot_ids is not None and (not wanted or wanted - {s['id'] for s in all_shots}):
        raise ValueError('Select existing shots for the handoff.')
    shots = [s for s in all_shots if s['id'] in wanted]
    assets = {a['id']: copy.deepcopy(a) for a in workspace.get('assets', [])}
    final = workspace.get('project', {}).get('final_file')
    if shot_ids is None and final:
        match = next((a['id'] for a in assets.values() if str(a.get('path') or Path(assets_dir)/a.get('file','')) == str(final)), None)
        if not match: assets['project-final'] = {'id':'project-final','name':'Final film','kind':'video','path':str(final),'file':Path(final).name}
    elements = {e['id']: e for e in workspace.get('elements', [])}
    associations = {ident: [] for ident in assets}
    selected_assets = set(assets) if shot_ids is None else set()
    for shot in shots:
        related = [(shot.get('reference'),'first-frame reference'),(shot.get('end_reference'),'last-frame reference'),(shot.get('output'),'selected result')]
        related += [(t.get('asset_id'),'candidate') for t in shot.get('takes', [])]
        for e in shot.get('elements', []):
            el = elements.get(e, {})
            related += [(el.get('asset_id'),'reference card'),(el.get('voice_asset_id'),'voice reference')]
        for ident, role in related:
            if ident:
                if ident not in assets: raise ValueError('A linked shot asset is missing from the project.')
                selected_assets.add(ident)
                associations[ident].append({'shot_id':shot['id'],'shot_title':shot['title'],'role':role})
    if asset_ids is not None:
        chosen = set(asset_ids)
        if chosen - set(assets): raise ValueError('Select existing project assets.')
        # References used by the model recipe must travel with the recipe.
        required = {ident for ident, roles in associations.items() if assets[ident].get('kind')=='image' and any('reference' in r['role'] for r in roles)}
        selected_assets = chosen | required
        if shot_ids is None and 'project-final' in assets:selected_assets.add('project-final')
    if not shots and not selected_assets: raise ValueError('Add project assets or shots before handing off.')
    files = []
    total = 0
    for ident in sorted(selected_assets):
        a = assets[ident]
        name = a.get('file', '')
        if not a.get('path') and (not name or Path(name).name != name): raise ValueError('Invalid project media filename.')
        path = Path(a['path']) if a.get('path') else Path(assets_dir)/name
        if not path.is_file() or path.is_symlink(): raise ValueError('A selected project media file is unavailable locally.')
        kind = a.get('kind')
        if kind not in ('image','video','audio'): raise ValueError('Unsupported project asset kind.')
        suffix = path.suffix.lower()
        allowed = {'image':{'.png','.jpg','.jpeg','.webp'},'video':{'.mp4','.webm','.mov','.mkv'},'audio':{'.wav','.mp3','.flac','.ogg','.m4a'}}
        if suffix not in allowed[kind]: raise ValueError('Unsupported project media extension.')
        sha = digest(path); size = path.stat().st_size; total += size
        if total > 100*1024**3: raise ValueError('Selected project assets exceed 100 GiB.')
        files.append({'asset_id':ident,'name':str(a.get('name') or path.name),'kind':kind,
                      'file':'cineharbor_'+sha[:24]+suffix,'sha256':sha,'bytes':size,'associations':associations[ident]})
    graph, positions, sections, warnings = {}, {}, [], []
    records=[]
    config_keys=('title','prompt','negative_prompt','duration','resolution','model','seed','reference','end_reference','workflow','ratio','recipe')
    for job in workspace.get('jobs',[])+workspace.get('historical_jobs',[]):
        if job.get('shot') in wanted or set(job.get('results',[])) & selected_assets:
            records.append({'id':job.get('id'),'shot':job.get('shot'),'state':job.get('state'),
                            'results':copy.deepcopy(job.get('results',[])),
                            'config':{k:copy.deepcopy(job['config'][k]) for k in config_keys if k in job.get('config',{})}})
    next_id = 1
    for i, shot in enumerate(shots):
        # The original recipe is useful but must never block carrying an approved
        # result when its old model recipe is incomplete or unavailable.
        recipe_ws = copy.deepcopy(workspace)
        recipe_ws['shots'] = [copy.deepcopy(shot)]
        recipe_ws['shots'][0].pop('dialogue', None)
        node_ids=[]
        if shot.get('workflow'):
            try:
                recipe = _prepare_generation(recipe_ws, assets_dir, [shot['id']], inline_images=False)
                remap = {old:str(next_id+n) for n,old in enumerate(recipe['graph'])}
                next_id += len(remap)
                for old,node in recipe['graph'].items():
                    for key,value in node['inputs'].items():
                        if isinstance(value,list) and len(value)==2 and isinstance(value[0],str) and isinstance(value[1],int): node['inputs'][key]=[remap[value[0]],value[1]]
                    node.setdefault('_meta',{})['title']=f'{i+1:02d} · {shot["title"]} / '+node['_meta']['title'].split(' / ',1)[-1]
                    graph[remap[old]]=node;positions[remap[old]]=[1800+recipe['positions'][old][0]-float(shot.get('x',220))*8, i*1800+recipe['positions'][old][1]]
                    node_ids.append(remap[old])
            except (ValueError,KeyError,TypeError) as error:
                warnings.append({'shot_id':shot['id'],'message':'Generation recipe not included: '+str(error)})
        context = {k:shot[k] for k in ('id','title','prompt','negative_prompt','dialogue','subtitle_en','seed','duration','resolution','model','workflow','reference','end_reference','output','elements','takes','versions') if k in shot}
        context['generation_records']=[r for r in records if r['shot']==shot['id']]
        ident=str(next_id);next_id+=1
        graph[ident]={'class_type':'PrimitiveStringMultiline','inputs':{'value':json.dumps(context,ensure_ascii=False,indent=2)},'_meta':{'title':f'{i+1:02d} · {shot["title"]} / Shot context & prompt'}}
        positions[ident]=[80+(i%3)*460,(i//3)*520+100]
        sections.append({'shot_id':shot['id'],'title':shot['title'],'node_ids':node_ids+[ident], 'recipe_node_ids':node_ids,'context_node_id':ident})
    for i, asset in enumerate(files):
        ident=str(next_id);next_id+=1
        cls,key={'image':('LoadImage','image'),'video':('LoadVideo','file'),'audio':('LoadAudio','audio')}[asset['kind']]
        roles=asset['associations']; owner=roles[0]['shot_title'] if roles else 'Project media'
        role=roles[0]['role'] if roles else asset['kind']
        graph[ident]={'class_type':cls,'inputs':{key:asset['file']},'_meta':{'title':owner+' / '+role+' / '+asset['name']}}
        positions[ident]=[80+(i%3)*460,((len(shots)+2)//3)*520+(i//3)*600+100]
        asset['node_id']=ident
    validate_graph(graph)
    return {'schema':'cineharbor.comfy-handoff.v2','project':workspace['project']['name'],
            'graph':graph,'positions':positions,'shots':sections,'assets':files,'warnings':warnings,
            'project_context':{'ratio':workspace.get('project',{}).get('ratio'),'assembly':copy.deepcopy(workspace.get('assembly',{})),
                               'generation_records':records,
                               'workflows':copy.deepcopy([w for w in workspace.get('workflows',[]) if w['id'] in {s.get('workflow') for s in shots}])},
            'execution':'Original media and canvas import only. Never queued automatically.','round_trip':False}


def freeze_assets(workspace, assets_dir, payload, directory):
    """Copy exact approved bytes to a private immutable transfer staging area."""
    import shutil
    from comfy_project_store import digest
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);directory.chmod(0o700)
    sources={a['id']:a for a in workspace.get('assets',[])}
    final=workspace.get('project',{}).get('final_file')
    if final:sources['project-final']={'path':final}
    unique={a['file']:a for a in payload['assets']}
    needed=sum(a['bytes'] for a in unique.values())
    if shutil.disk_usage(directory).free < needed+1024**2:raise ValueError('Not enough local disk space to stage the handoff.')
    for asset in unique.values():
        source=sources[asset['asset_id']]
        path=Path(source['path']) if source.get('path') else Path(assets_dir)/source['file']
        target=directory/asset['file'];shutil.copyfile(path,target);target.chmod(0o600)
        if target.stat().st_size!=asset['bytes'] or digest(target)!=asset['sha256']:raise ValueError('A media file changed while preparing the handoff. Retry after saving your project.')
