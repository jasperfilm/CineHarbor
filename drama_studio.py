"""Industrial AI Short-Drama & Cinema Studio Engine (LibTV / TapNow parity + Pro Local Mastering).

Provides:
1. 12 Cinema Camera Rig & Shot-Scale Presets
2. Script / Novel -> Multi-Shot Storyboard Breakdown (auto-extracts @Characters, @Scenes, Dialogue & Camera Moves)
3. 1-Click Character 3-View Turnaround Sheet Job Builder (Qwen 2512 / Qwen Edit 2511 BF16)
4. 1-Click 3x3 Coherent Storyboard Grid Job Builder + Native 0.1s 9-Panel Auto-Slicer (`gclabs-media slice-grid`)
5. @Character Voice Timbre Sample Extraction & Locking (`gclabs-media extract-audio`)
6. Per-Shot 4-Frame Director Visual QC Filmstrip (`gclabs-media filmstrip`) & Gallery Storyboard Sheet PNG Export
"""
from pathlib import Path
import copy, hashlib, json, re, shutil, subprocess, tempfile, time, uuid

CAMERA_PRESETS = [
    {
        'id': 'push_in_ecu',
        'label': '推镜特写 Push-In',
        'scale': '近景→大特写',
        'prompt': 'Smooth motorized dolly push-in camera gliding into an intimate expressive facial close-up, shallow 85mm cinema depth of field.'
    },
    {
        'id': 'crane_reveal',
        'label': '大摇臂拉远 Crane Reveal',
        'scale': '中景→大远景',
        'prompt': 'Grand sweeping 12m cinema crane-up and pull-back reveal shot unveiling the vast surrounding environment in epic scale.'
    },
    {
        'id': 'whip_orbit_180',
        'label': '180°环绕甩镜 Whip Orbit',
        'scale': '中近景环绕',
        'prompt': 'Dynamic 180-degree orbital whip-pan tracking shot swinging smoothly around the subject with dramatic parallax.'
    },
    {
        'id': 'ots_reverse',
        'label': '过肩正反打 OTS',
        'scale': '过肩中近景',
        'prompt': 'Anamorphic 50mm over-the-shoulder dialogue framing with foreground shoulder silhouette and crisp rack-focus onto the speaker.'
    },
    {
        'id': 'handheld_combat',
        'label': '手持搏击跟拍 Handheld',
        'scale': '贴身动作中景',
        'prompt': 'Visceral kinetic handheld shutter-snap action camera tightly tracking close-quarters movement with raw physical impact.'
    },
    {
        'id': 'fpv_dive',
        'label': 'FPV极速俯冲 FPV Dive',
        'scale': '航拍俯冲追拍',
        'prompt': 'High-velocity cinema FPV drone cliff-dive pursuit shot plunging steeply forward and skimming inches past the subject.'
    },
    {
        'id': 'russian_arm',
        'label': '俄罗斯臂贴地追车 Russian Arm',
        'scale': '贴地高速跟拍',
        'prompt': 'Ultra-low-angle Russian-arm gyro-stabilized tracking camera racing at 180 km/h inches above the ground beside the subject.'
    },
    {
        'id': 'dolly_zoom',
        'label': '希区柯克变焦 Vertigo',
        'scale': '心理悬疑近景',
        'prompt': 'Dramatic Hitchcock dolly-zoom (contra-zoom) keeping the subject face size constant while the background warps in psychological tension.'
    },
    {
        'id': 'low_orbit',
        'label': '贴地仰拍环绕 Low Orbit',
        'scale': '低角度英雄景',
        'prompt': 'Heroic ultra-low-angle orbital camera skimming near ground level looking up at the subject against dramatic rim lighting.'
    },
    {
        'id': 'macro_slider',
        'label': '超微距滑轨 Macro Slider',
        'scale': '极微距特写',
        'prompt': 'Precision 100mm macro cinema slider shot gliding across intricate surface textures, water droplets, and mechanical micro-details.'
    },
    {
        'id': 'lateral_track',
        'label': '高速横移跟拍 Lateral',
        'scale': '侧面全/中景',
        'prompt': 'High-speed lateral dolly tracking shot moving parallel beside the subject through layered foreground silhouettes.'
    },
    {
        'id': 'speed_ramp',
        'label': '升格变速定格 Speed-Ramp',
        'scale': '动作爆发特写',
        'prompt': '1000fps Phantom ultra-slow-motion impact transitioning via a sudden speed-ramp snap into a poised hero freeze-frame.'
    },
]


def _ensure_qwen_2512_workflow(workspace: dict):
    from workflow_converter import convert_canvas_to_api
    from workflow_library import recipe
    from model_presets import get_preset, upgrade_graph_to_preset
    wf_name = 'Qwen Image 2512 · 完整 BF16 文生图母版配方'
    existing = next((w for w in workspace.get('workflows', []) if w.get('name') == wf_name), None)
    if existing:
        return existing
    root = Path(__file__).resolve().parent
    tpl = json.loads((root / 'assets/workflow-templates/image_qwen_Image_2512.json').read_text())
    conv = convert_canvas_to_api(tpl)
    preset = get_preset(preset_id='qwen_image_2512_bf16')
    if preset:
        conv['graph'] = upgrade_graph_to_preset(conv['graph'], preset)
        conv['model_files'] = preset['model_files']
    saved = recipe({'name': wf_name, **conv})
    workspace.setdefault('workflows', []).append(saved)
    return saved


def _ensure_qwen_edit_workflow(workspace: dict, custom_width=1920, custom_height=1088, wf_name=None):
    from workflow_library import recipe
    from model_presets import get_preset
    wf_name = wf_name or 'Qwen Image Edit 2511 · 完整 BF16 锁脸分镜配方'
    existing = next((w for w in workspace.get('workflows', []) if w.get('name') == wf_name), None)
    if existing:
        return existing
    preset = get_preset(preset_id='qwen_image_edit_2511_bf16')

    def _n(kind, **inputs):
        return {'class_type': kind, 'inputs': inputs}

    edit_graph = {
        '1': _n('UNETLoader', unet_name='qwen_image_edit_2511_bf16.safetensors', weight_dtype='default'),
        '2': _n('CLIPLoader', clip_name='qwen_2.5_vl_7b.safetensors', type='qwen_image', device='default'),
        '3': _n('VAELoader', vae_name='qwen_image_vae.safetensors'),
        '4': _n('ModelSamplingAuraFlow', model=['1', 0], shift=3.1),
        '5': _n('CFGNorm', model=['4', 0], strength=1.0),
        '6': _n('LoraLoaderModelOnly', model=['5', 0], lora_name='Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors', strength_model=1.0),
        '7': _n('LoadImage', image='anchor.png'),
        '8': _n('TextEncodeQwenImageEditPlus', clip=['2', 0], vae=['3', 0], image1=['7', 0], prompt=''),
        '9': _n('TextEncodeQwenImageEditPlus', clip=['2', 0], vae=['3', 0], image1=['7', 0], prompt=''),
        '10': _n('FluxKontextMultiReferenceLatentMethod', conditioning=['8', 0], reference_latents_method='index_timestep_zero'),
        '11': _n('FluxKontextMultiReferenceLatentMethod', conditioning=['9', 0], reference_latents_method='index_timestep_zero'),
        '12': _n('EmptySD3LatentImage', width=custom_width, height=custom_height, batch_size=1),
        '13': _n('KSampler', model=['6', 0], positive=['10', 0], negative=['11', 0], latent_image=['12', 0], seed=1024, steps=4, cfg=1.0, sampler_name='euler', scheduler='simple', denoise=1.0),
        '14': _n('VAEDecode', samples=['13', 0], vae=['3', 0]),
        '15': _n('SaveImage', images=['14', 0], filename_prefix='GC_Labs_QwenEdit'),
    }
    saved = recipe({
        'name': wf_name,
        'kind': 'image',
        'graph': edit_graph,
        'bindings': {
            'reference': [{'node': '7', 'input': 'image'}],
            'prompt': [{'node': '8', 'input': 'prompt'}],
            'negative_prompt': [{'node': '9', 'input': 'prompt'}],
            'width': [{'node': '12', 'input': 'width'}],
            'height': [{'node': '12', 'input': 'height'}],
            'seed': [{'node': '13', 'input': 'seed'}],
        },
        'model_files': preset['model_files'] if preset else [],
    })
    workspace.setdefault('workflows', []).append(saved)
    return saved


def breakdown_script_to_storyboard(server, workspace: dict, payload: dict) -> dict:
    """Parse dramatic script / novel text into @Characters, @Scenes, and sequential Storyboard Shots."""
    if workspace['project'].get('status') == 'completed':
        raise ValueError('已结项项目只读，请新建项目。')
    script_text = str(payload.get('script', '')).strip()
    if len(script_text) < 6:
        raise ValueError('请粘贴至少一段剧本、故事梗概或分场台词。')
    visual_style = str(payload.get('style', 'Cinematic live action, IMAX 35mm film texture, dramatic high-contrast lighting')).strip()
    replace_existing = bool(payload.get('replace_shots', False))

    elems = workspace.setdefault('elements', [])
    existing_tags = {e['tag']: e['id'] for e in elems}
    created_elements = []

    # Explicit metadata is not a shot. Preserve the scene active at each beat,
    # including normal INT./EXT. headings and the five supported UI languages.
    scene_words = r'Scene|Location|场景|場景|地点|地點|シーン|場所|장면|장소'
    character_words = r'Character|角色|キャラクター|登場人物|캐릭터|인물'
    def header(words):
        return re.compile(r'^(?:(?:\[|【)(?:'+words+r')(?:\]|】)\s*[:：]?|(?:'+words+r')\s*[:：])\s*(.+)$', re.I)
    scene_header, character_header = header(scene_words), header(character_words)
    lines = [line.strip() for line in script_text.splitlines() if line.strip()]
    for line in lines:
        match = character_header.match(line)
        definition = re.match(r'([^：:—]+)[：:—]\s*(.+)$', match.group(1)) if match else None
        if definition:
            ctag = definition.group(1).strip().lstrip('@')[:20]
            cdesc = definition.group(2).strip()[:500]
            if ctag and ctag not in existing_tags:
                item = {'id': uuid.uuid4().hex, 'tag': ctag, 'kind': 'character', 'prompt_snippet': cdesc, 'asset_id': None, 'created': server.now()}
                elems.append(item)
                existing_tags[ctag] = item['id']
                created_elements.append(item)

    scene_id = None
    raw_lines = []
    for line in lines:
        match = scene_header.match(line) or re.match(r'^(?:INT\.|EXT\.|INT\./EXT\.)\s*(.+)$', line, re.I)
        if match:
            raw_scene = match.group(1).strip()[:500]
            scene_tag = re.split(r'[，,。—]', raw_scene)[0].strip()[:32] or 'Main scene'
            if scene_tag not in existing_tags:
                item = {'id': uuid.uuid4().hex, 'tag': scene_tag, 'kind': 'scene',
                        'prompt_snippet': f'{raw_scene}. {visual_style}. No on-screen text or signage.',
                        'asset_id': None, 'created': server.now()}
                elems.append(item)
                existing_tags[scene_tag] = item['id']
                created_elements.append(item)
            scene_id = existing_tags[scene_tag]
        elif not character_header.match(line):
            raw_lines.append((line, scene_id))

    if len(raw_lines) == 1 and len(raw_lines[0][0]) > 45:
        line, active_scene = raw_lines[0]
        raw_lines = [(part.strip(), active_scene) for part in re.split(r'(?<=[。！？!?])\s*', line) if len(part.strip()) >= 4]

    beats = raw_lines[:16]
    if not beats:
        raise ValueError('未能从输入文本中提取出有效剧情分镜句，请补充动作或台词描述。')

    if replace_existing:
        workspace['shots'] = []

    cycle_cameras = [
        CAMERA_PRESETS[0],  # Push-In
        CAMERA_PRESETS[3],  # OTS
        CAMERA_PRESETS[10], # Lateral Track
        CAMERA_PRESETS[2],  # Whip Orbit
        CAMERA_PRESETS[1],  # Crane Reveal
    ]

    created_shots = []
    start_idx = len(workspace['shots'])
    for i, (beat, scene_id) in enumerate(beats):
        clean_beat = re.sub(r'^\s*(?:第?\d+[镜场幕.\s、:：\-]+|SHOT\s*\d+[:：.\-\s]*)', '', beat, flags=re.I).strip()
        # Extract speaker + spoken quote if present: e.g. 林默：“星门快塌了！” or “台词”
        speaker = ''
        dialogue = ''
        m_spk = re.search(r'([\u4e00-\u9fa5A-Za-z0-9_]{1,10})\s*(?:说|喊|低语|冷声道|大喊|道)?\s*[：:]?\s*[“"「『]([^”"」』]+)[”"」』]', clean_beat)
        if m_spk:
            cand = m_spk.group(1).strip()
            # A narration verb (e.g. 她轻声说) is not a new character name.
            known_characters = [e['tag'] for e in elems if e.get('kind') == 'character']
            before_quote = clean_beat[:m_spk.end(1)]
            named = [(before_quote.rfind(tag), tag) for tag in known_characters if tag in before_quote]
            if named:
                speaker = max(named)[1]
            elif not known_characters:
                cand = re.sub(r'(?:轻声|低声|大声|冷声|柔声)?(?:说道|说|喊|低语|冷声道|大喊|道)$', '', cand).strip()
                if cand and cand not in ('她', '他', '它', '镜头', '画面', '旁白', '画外音', '特写', '远景', '中景', '近景'):
                    speaker = cand
            dialogue = m_spk.group(2).strip()
        else:
            m_q = re.search(r'[“"「『]([^”"」』]+)[”"」』]', clean_beat)
            if m_q:
                dialogue = m_q.group(1).strip()

        shot_elem_ids = []
        if speaker:
            if speaker not in existing_tags:
                item = {
                    'id': uuid.uuid4().hex,
                    'tag': speaker,
                    'kind': 'character',
                    'prompt_snippet': f'{speaker}，固定五官特征与服装造型，{visual_style}',
                    'asset_id': None,
                    'created': server.now()
                }
                elems.append(item)
                existing_tags[speaker] = item['id']
                created_elements.append(item)
            shot_elem_ids.append(existing_tags[speaker])
        for tag_name, eid in existing_tags.items():
            if tag_name in clean_beat and eid not in shot_elem_ids:
                shot_elem_ids.append(eid)
        if scene_id and scene_id not in shot_elem_ids:
            shot_elem_ids.append(scene_id)

        # Match explicit camera keyword or pick cinematic progression preset
        chosen_cam = cycle_cameras[i % len(cycle_cameras)]
        for cp in CAMERA_PRESETS:
            kw = cp['label'].split()[0][:2]
            if kw in clean_beat:
                chosen_cam = cp
                break
        if any(w in clean_beat for w in ('打', '拳', '踢', '斩', '搏', '战')):
            chosen_cam = CAMERA_PRESETS[4]
        elif any(w in clean_beat for w in ('俯冲', '穿行', '疾驰', '狂飙')):
            chosen_cam = CAMERA_PRESETS[5]

        shot_num = start_idx + i + 1
        short_headline = re.sub(r'[“"「『][^”"」』]+[”"」』]', '', clean_beat).strip(' ，,。：:；;—-')[:16] or (dialogue[:14] if dialogue else f'剧情分镜 {shot_num:02d}')
        title = f"SHOT {shot_num:02d} · {short_headline}"

        prompt_parts = [f"{visual_style}. {chosen_cam['prompt']} {clean_beat}"]
        if dialogue:
            voice_note = f'Synchronized expressive lip-sync speech in the original language of this dialogue: "{dialogue}".'
            prompt_parts.append(voice_note)
        prompt_parts.append('Realistic environmental Foley audio, strictly no on-screen text or garbled signage.')

        new_shot = {
            'id': uuid.uuid4().hex,
            'title': title,
            'prompt': ' '.join(prompt_parts),
            'dialogue': dialogue,
            'subtitle_en': '',
            'camera_move': chosen_cam['id'],
            'shot_scale': chosen_cam['scale'],
            'duration': 5,
            'resolution': '1080P',
            'model': 'h3',
            'seed': 2000 + shot_num * 101,
            'reference': None,
            'end_reference': None,
            'elements': shot_elem_ids,
            'output': None,
            'versions': [],
            'x': 220 + ((shot_num - 1) % 3) * 440,
            'y': 80 + ((shot_num - 1) // 3) * 460,
        }
        workspace['shots'].append(new_shot)
        created_shots.append(new_shot)

    server.save(workspace)
    return {
        'ok': True,
        'created_shots': len(created_shots),
        'created_elements': len(created_elements),
        'shots': created_shots,
        'elements': created_elements,
    }


def prepare_character_turnaround_job(server, workspace: dict, payload: dict) -> dict:
    """Create a 1920x1088 3-View Character Turnaround Master Sheet job for @Element consistency locking."""
    if workspace['project'].get('status') == 'completed':
        raise ValueError('已结项项目只读。')
    elem_id = payload.get('element_id')
    elem = next((e for e in workspace.get('elements', []) if e['id'] == elem_id), None)
    if not elem:
        raise ValueError('请先选择或保存一张 @角色 / 道具参考卡。')
    desc = (elem.get('prompt_snippet') or payload.get('prompt_snippet') or '').strip()
    if not desc:
        raise ValueError('请先填写该角色的固定外观与服装描述。')

    has_anchor = bool(elem.get('asset_id') and any(a['id'] == elem['asset_id'] and a['kind'] == 'image' for a in workspace.get('assets', [])))
    if has_anchor:
        wf = _ensure_qwen_edit_workflow(workspace)
        ref_id = elem['asset_id']
        turnaround_prompt = (
            f"Keep the exact same character facial features, hairstyle, and outfit from Picture 1 ({elem['tag']}: {desc}). "
            "Create a clean professional 3-view character turnaround reference sheet side-by-side on a neutral dark studio backdrop: "
            "(Left) front medium close-up portrait, (Center) full-body front standing view, (Right) full-body 3/4 back-side profile view. "
            "Uniform studio rim lighting, ultra-sharp costume details, no text, no labels."
        )
    else:
        wf = _ensure_qwen_2512_workflow(workspace)
        ref_id = None
        turnaround_prompt = (
            f"Professional cinema character design 3-view turnaround master sheet for {elem['tag']} ({desc}), "
            "arranged cleanly left-to-right on a neutral dark studio backdrop: "
            "(Left) expressive front close-up portrait, (Center) full-body front view, (Right) full-body side-back view. "
            "Consistent facial structure, identical outfit across all three views, 8k photorealistic detail, strictly no text or watermarks."
        )

    job = {
        'id': uuid.uuid4().hex,
        'shot': None,
        'bind_element_id': elem['id'],
        'title': f"@{elem['tag']} · 角色三视图定妆母版",
        'state': 'prepared',
        'created': server.now(),
        'config': {
            'title': f"@{elem['tag']} 三视图定妆母版",
            'prompt': turnaround_prompt,
            'negative_prompt': 'blurry, inconsistent face, extra limbs, text, watermark, letters',
            'duration': 5,
            'resolution': '1080P',
            'model': 'workflow',
            'workflow': wf['id'],
            'seed': int(payload.get('seed') or 8801),
            'reference': ref_id,
            'ratio': '16:9',
            'recipe': {k: copy.deepcopy(wf.get(k)) for k in ('id', 'name', 'kind', 'graph', 'bindings', 'model_files', 'custom_nodes', 'timing', 'revision')},
        },
        'message': '已创建角色三视图定妆母版任务；在 G4 生成完成后将自动绑定为此 @角色卡 的主参考图。'
    }
    workspace['jobs'].insert(0, job)
    server.save(workspace)
    return {'ok': True, 'job': job}


def prepare_nine_grid_storyboard_job(server, workspace: dict, payload: dict) -> dict:
    """Create a 3x3 Coherent Cinema Contact-Sheet Storyboard generation job (Qwen Edit 2511 / Qwen 2512 BF16)."""
    if workspace['project'].get('status') == 'completed':
        raise ValueError('已结项项目只读。')
    scene_brief = str(payload.get('scene_brief', '')).strip()
    if not scene_brief:
        scene_brief = ' ；'.join(f"Panel {i+1}: {s['title']} ({(s.get('prompt') or '')[:80]})" for i, s in enumerate(workspace.get('shots', [])[:9]))
    if not scene_brief:
        raise ValueError('请填写本场戏剧情描述，或先拆解分镜列表。')

    anchor_id = payload.get('anchor_asset_id')
    if not anchor_id:
        anchor_id = next((e['asset_id'] for e in workspace.get('elements', []) if e.get('asset_id')), None)
    has_anchor = bool(anchor_id and any(a['id'] == anchor_id and a['kind'] == 'image' for a in workspace.get('assets', [])))

    if has_anchor:
        wf = _ensure_qwen_edit_workflow(workspace, custom_width=2400, custom_height=1344, wf_name='Qwen Image Edit 2511 · 九宫格连贯分镜推演配方')
        grid_prompt = (
            "Keep the exact same protagonist face, hair, and costume from Picture 1 across all 9 panels, ignoring any plain studio backdrop from Picture 1. "
            "Generate a seamless 3x3 widescreen 9-panel cinema storyboard contact sheet (3 rows by 3 columns, thin clean black borders) "
            f"where EVERY panel is set inside the rich atmospheric story environment for: {scene_brief}. "
            "Each of the 9 panels MUST depict a distinctly different dramatic action beat and camera scale: "
            "(1) extreme wide environment establishing shot, (2) medium tracking walk, (3) over-the-shoulder confrontation, "
            "(4) dynamic mid-air action leap, (5) macro hand/prop detail, (6) Dutch-angle close-up tension, "
            "(7) kinetic wide action climax, (8) emotional close-up reaction, (9) epic wide silhouette finale. "
            "100% consistent color grading, rich environmental lighting in all 9 panels, strictly no plain studio backgrounds, no text, no numbers, no captions."
        )
    else:
        wf = _ensure_qwen_2512_workflow(workspace)
        anchor_id = None
        grid_prompt = (
            "Masterpiece 3x3 widescreen 9-panel cinema storyboard contact sheet (3 rows by 3 columns, thin black panel dividers) "
            f"with 100% consistent character face, costume, and color grading across all 9 sequential shots: {scene_brief}. "
            "Diverse shot scales from wide establishing shot to intimate close-up and kinetic tracking angles, strictly no text, no numbers, no subtitles."
        )

    job = {
        'id': uuid.uuid4().hex,
        'shot': None,
        'is_nine_grid': True,
        'title': f"九宫格连贯分镜推演 · {workspace['project']['name'][:18]}",
        'state': 'prepared',
        'created': server.now(),
        'config': {
            'title': '九宫格连贯分镜母版',
            'prompt': grid_prompt,
            'negative_prompt': 'text, numbers, captions, speech bubbles, inconsistent character, watermark',
            'duration': 5,
            'resolution': '1080P',
            'model': 'workflow',
            'workflow': wf['id'],
            'seed': int(payload.get('seed') or 9901),
            'reference': anchor_id,
            'ratio': '16:9',
            'recipe': {k: copy.deepcopy(wf.get(k)) for k in ('id', 'name', 'kind', 'graph', 'bindings', 'model_files', 'custom_nodes', 'timing', 'revision')},
        },
        'message': '已创建九宫格连贯分镜推演任务；生成后可在素材库或分镜台点击“✂️ 一键切分九宫格上画布”秒切成 9 个独立镜头。'
    }
    workspace['jobs'].insert(0, job)
    server.save(workspace)
    return {'ok': True, 'job': job}


def slice_grid_to_shots(server, workspace: dict, payload: dict) -> dict:
    """Slice a 3x3 (or 2x2) grid image asset locally in 0.1s at 0 CU into standalone assets & Storyboard Shots."""
    from timeline_export import media_tool_binary, resolve_asset_file
    if workspace['project'].get('status') == 'completed':
        raise ValueError('已结项项目只读。')
    asset_id = payload.get('asset_id')
    grid_asset = next((a for a in workspace.get('assets', []) if a['id'] == asset_id and a.get('kind') == 'image'), None)
    if not grid_asset:
        raise ValueError('请选择一张九宫格（或四宫格）分镜图像素材。')
    rows = int(payload.get('rows') or 3)
    cols = int(payload.get('cols') or 3)
    if rows not in (2, 3) or cols not in (2, 3):
        raise ValueError('分镜切图目前支持 3×3 九宫格或 2×2 四宫格。')
    bind_mode = payload.get('bind_mode', 'create_or_fill')  # fill existing unreferenced shots or append new shots

    src_path = resolve_asset_file(server, grid_asset)
    tool = media_tool_binary(server.ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        p = subprocess.run(
            [str(tool), 'slice-grid', str(src_path), tmp, str(rows), str(cols), '0.012'],
            capture_output=True, text=True, timeout=30
        )
        if p.returncode != 0:
            raise RuntimeError('九宫格切图失败：' + (p.stderr or p.stdout)[-400:])
        info = json.loads(p.stdout)
        created_assets = []
        affected_shots = []
        existing_unfilled = [s for s in workspace.get('shots', []) if not s.get('reference') and not s.get('output')]
        default_elem_ids = [e['id'] for e in workspace.get('elements', [])[:2]]

        for idx, panel in enumerate(info.get('panels', []), 1):
            panel_bytes = Path(panel['path']).read_bytes()
            aid = uuid.uuid4().hex
            fname = f'{aid}.png'
            (server.ASSETS / fname).write_bytes(panel_bytes)
            new_asset = {
                'id': aid,
                'name': f"{Path(grid_asset['name']).stem}_分镜格{idx:02d}.png",
                'file': fname,
                'sha256': hashlib.sha256(panel_bytes).hexdigest(),
                'kind': 'image',
                'created': server.now()
            }
            workspace['assets'].append(new_asset)
            created_assets.append(new_asset)

            if bind_mode == 'create_or_fill' and existing_unfilled:
                target_shot = existing_unfilled.pop(0)
                target_shot['reference'] = aid
                affected_shots.append(target_shot['id'])
            else:
                snum = len(workspace['shots']) + 1
                cam = CAMERA_PRESETS[(idx - 1) % len(CAMERA_PRESETS)]
                new_shot = {
                    'id': uuid.uuid4().hex,
                    'title': f"SHOT {snum:02d} · 宫格分镜 #{idx:02d} ({cam['scale']})",
                    'prompt': cam['prompt'],
                    'dialogue': '',
                    'subtitle_en': '',
                    'camera_move': cam['id'],
                    'shot_scale': cam['scale'],
                    'duration': 5,
                    'resolution': '1080P',
                    'model': 'h3',
                    'seed': 3000 + idx * 77,
                    'reference': aid,
                    'end_reference': None,
                    'elements': default_elem_ids,
                    'output': None,
                    'versions': [],
                    'x': 220 + ((idx - 1) % cols) * 430,
                    'y': 80 + ((idx - 1) // cols) * 450,
                }
                workspace['shots'].append(new_shot)
                affected_shots.append(new_shot['id'])

    server.save(workspace)
    return {'ok': True, 'count': len(created_assets), 'assets': created_assets, 'shots': affected_shots}


def extract_voice_sample_to_element(server, workspace: dict, payload: dict) -> dict:
    """Save the original clip audio as a character reference; no voice cloning or stem separation."""
    from timeline_export import media_tool_binary, resolve_asset_file
    if workspace['project'].get('status') == 'completed':
        raise ValueError('已结项项目只读。')
    shot = next((s for s in workspace.get('shots', []) if s['id'] == payload.get('shot_id')), None)
    if not shot or not shot.get('output'):
        raise ValueError('请先选择一个已生成有声视频样片的镜头。')
    vid_asset = next((a for a in workspace.get('assets', []) if a['id'] == shot['output'] and a.get('kind') == 'video'), None)
    if not vid_asset:
        raise ValueError('未找到该镜头的视频资产。')

    elem_id = payload.get('element_id') or next((eid for eid in (shot.get('elements') or []) if any(e['id'] == eid and e['kind'] == 'character' for e in workspace.get('elements', []))), None)
    elem = next((e for e in workspace.get('elements', []) if e['id'] == elem_id), None)
    if not elem:
        raise ValueError('请先将此镜头关联到一张 @角色卡，再保存声音参考。')

    vid_path = resolve_asset_file(server, vid_asset)
    tool = media_tool_binary(server.ROOT)
    aid = uuid.uuid4().hex
    fname = f'{aid}.m4a'
    out_path = server.ASSETS / fname
    p = subprocess.run([str(tool), 'extract-audio', str(vid_path), str(out_path)], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError('提取角色声音参考音轨失败：' + (p.stderr or p.stdout)[-400:])

    raw = out_path.read_bytes()
    voice_asset = {
        'id': aid,
        'name': f"@{elem['tag']}_audio-reference.m4a",
        'file': fname,
        'sha256': hashlib.sha256(raw).hexdigest(),
        'kind': 'audio',
        'created': server.now()
    }
    workspace['assets'].append(voice_asset)
    elem['voice_asset_id'] = aid
    if payload.get('voice_profile'):
        elem['voice_profile'] = str(payload['voice_profile']).strip()[:200]
    elem['voice_reference_mode'] = 'reference_only'
    # This is the original clip audio (including ambience), not a speaker embedding or isolated vocal stem.
    server.save(workspace)
    return {'ok': True, 'voice_asset': voice_asset, 'element': elem}


def generate_shot_qc_filmstrip(server, workspace: dict, payload: dict) -> dict:
    """Generate a 4-frame timestamped visual QC filmstrip for a shot's current video output at 0 CU."""
    from timeline_export import media_tool_binary, resolve_asset_file
    shot = next((s for s in workspace.get('shots', []) if s['id'] == payload.get('shot_id')), None)
    if not shot or not shot.get('output'):
        raise ValueError('该镜头尚无已生成的视频样片。')
    vid_asset = next((a for a in workspace.get('assets', []) if a['id'] == shot['output'] and a.get('kind') == 'video'), None)
    if not vid_asset:
        raise ValueError('当前镜头输出不是视频文件。')

    vid_path = resolve_asset_file(server, vid_asset)
    tool = media_tool_binary(server.ROOT)
    strip_id = f"qcstrip_{vid_asset['id'][:16]}.jpg"
    out_path = server.ASSETS / strip_id
    if not out_path.is_file():
        p = subprocess.run([str(tool), 'filmstrip', str(vid_path), str(out_path), '4'], capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            raise RuntimeError('生成四格抽帧质检条失败：' + (p.stderr or p.stdout)[-400:])
    if not any(a['file'] == strip_id for a in workspace.get('assets', [])):
        workspace['assets'].append({
            'id': uuid.uuid4().hex,
            'name': f"{shot['title']} · frame-check.jpg",
            'file': strip_id,
            'sha256': hashlib.sha256(out_path.read_bytes()).hexdigest(),
            'kind': 'image',
            'is_qc_strip': True,
            'created': server.now()
        })
    shot['qc_strip_file'] = strip_id
    server.save(workspace)
    return {'ok': True, 'file': strip_id, 'url': '/assets/' + strip_id}


def export_storyboard_sheet_png(server, workspace: dict, payload: dict) -> dict:
    """Export a high-resolution GachaFrame Gallery Continuity Storyboard Sheet PNG into /exports/."""
    from timeline_export import extract_video_frame, media_tool_binary, resolve_asset_file
    assets_by_id = {a['id']: a for a in workspace.get('assets', [])}
    wfs_by_id = {w['id']: w for w in workspace.get('workflows', [])}
    shots = [
        s for s in workspace.get('shots', [])
        if not (assets_by_id.get(s.get('output') or '', {}).get('kind') == 'audio')
        and not (s.get('model') == 'workflow' and wfs_by_id.get(s.get('workflow') or '', {}).get('kind') == 'audio')
    ]
    edited_clips = None
    if payload.get('clips'):
        from timeline_export import _normalize_assembly_items
        edited_clips = {c['shot_id']: c for c in _normalize_assembly_items(server, workspace, payload)[0]}
        shots = [s for s in shots if s['id'] in edited_clips]
    if not shots:
        raise ValueError('当前项目尚无可视分镜，无法导出分镜通告单。')
    exports = server.DATA / 'exports'
    exports.mkdir(exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    file_name = f'CineHarbor_Storyboard_Sheet_{stamp}.png'
    out_path = exports / file_name

    tool = media_tool_binary(server.ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        rows = []
        for idx, s in enumerate(shots):
            img_path = ''
            ref_a = assets_by_id.get(s.get('reference') or '')
            out_a = assets_by_id.get(s.get('output') or '')
            if out_a and out_a.get('kind') == 'image':
                img_path = str(resolve_asset_file(server, out_a))
            elif out_a and out_a.get('kind') == 'video':
                try:
                    vid_p = resolve_asset_file(server, out_a)
                    f_png = Path(tmp) / f's_{idx}.png'
                    extract_video_frame(server.ROOT, vid_p, f_png, position='first')
                    img_path = str(f_png)
                except Exception:
                    img_path = ''
            if not img_path and ref_a and ref_a.get('kind') == 'image':
                try:
                    img_path = str(resolve_asset_file(server, ref_a))
                except Exception:
                    img_path = ''
            rows.append({
                'title': s.get('title', f'SHOT {idx+1:02d}'),
                'duration': edited_clips[s['id']]['duration'] if edited_clips is not None else float(s.get('duration') or 5.0),
                'dialogue': s.get('dialogue', ''),
                'prompt': (s.get('prompt') or '')[:140],
                'image_path': img_path,
            })
        spec_file = Path(tmp) / 'sheet_spec.json'
        spec_file.write_text(json.dumps({'product_name': server.PRODUCT['display_name'], 'project_name': workspace['project'].get('name', 'CineHarbor 项目'), 'shots': rows}, ensure_ascii=False))
        p = subprocess.run([str(tool), 'storyboard-sheet', str(spec_file), str(out_path)], capture_output=True, text=True, timeout=45)
        if p.returncode != 0:
            raise RuntimeError('导出分镜通告单失败：' + (p.stderr or p.stdout)[-400:])
        res = json.loads(p.stdout)

    return {
        'file': file_name,
        'url': f'/exports/{file_name}',
        'bytes': out_path.stat().st_size,
        'shots': len(rows),
        'width': res.get('width'),
        'height': res.get('height'),
    }
