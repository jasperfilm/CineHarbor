"""Local media probing, frame chaining, rough-cut MP4 rendering, FCPXML 1.10 & CapCut/Jianying draft export.

Zero cloud GPU usage. Uses bundled native Apple Silicon AVFoundation helper (`gclabs-media`).
"""
import hashlib, io, json, math, shutil, subprocess, tempfile, time, uuid, zipfile
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


def media_tool_binary(root: Path) -> Path:
    candidates = [
        root / 'vendor/bin/gclabs-media',
        root.parent.parent / 'MacOS/gclabs-media',
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise RuntimeError('本机 AVFoundation 媒体组件 gclabs-media 未就绪。')


def probe_media(root: Path, media_path: Path) -> dict:
    tool = media_tool_binary(root)
    p = subprocess.run([str(tool), 'probe', str(media_path)], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        raise ValueError(f'无法探测媒体文件 {media_path.name}')
    info = json.loads(p.stdout)
    if not info.get('ok'):
        raise ValueError(info.get('error', '媒体探测失败'))
    return info


def extract_video_frame(root: Path, video_path: Path, out_png: Path, position: str = 'last') -> dict:
    if position not in ('first', 'last'):
        try:
            val = float(position)
            if val < 0 or val > 3600:
                raise ValueError()
            position = f'{val:.3f}'
        except ValueError:
            raise ValueError('帧提取位置须为 first、last 或有效秒数。')
    tool = media_tool_binary(root)
    p = subprocess.run([str(tool), 'extract-frame', str(video_path), str(out_png), position], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        detail = p.stderr.strip() or p.stdout.strip()
        try:
            detail = json.loads(detail).get('error', detail)
        except Exception:
            pass
        raise RuntimeError(f'视频帧提取失败：{detail}')
    res = json.loads(p.stdout)
    res['sha256'] = hashlib.sha256(out_png.read_bytes()).hexdigest()
    return res


def resolve_asset_file(server, asset: dict) -> Path:
    p = Path(asset['path']) if asset.get('path') else (server.ASSETS / asset['file'])
    if not p.is_file():
        raise ValueError(f"素材文件不存在：{asset.get('name', asset.get('file', ''))}")
    return p


def assembly_settings(workspace: dict, payload: dict) -> dict:
    """Validate portable editing settings without reading media or starting compute."""
    if len(json.dumps(payload, ensure_ascii=False)) > 100_000:
        raise ValueError('剪辑设置过大。')
    shots = {s['id']: s for s in workspace.get('shots', [])}
    assets = {a['id']: a for a in workspace.get('assets', [])}
    def seconds(value):
        n = float(value)
        if not math.isfinite(n) or not 0 <= n <= 36_000:
            raise ValueError('剪辑时间须为有效秒数。')
        return n
    raw = payload.get('clips', [])
    if not isinstance(raw, list) or len(raw) > 500:
        raise ValueError('剪辑镜头列表无效。')
    clips = []
    for c in raw:
        s = shots.get(c.get('shot_id')) if isinstance(c, dict) else None
        a = assets.get(c.get('asset_id')) if s else None
        if not s or not a or a.get('kind') != 'video':
            raise ValueError('剪辑设置引用的镜头或视频不存在。')
        start, end = seconds(c.get('start', 0)), seconds(c.get('end', s.get('duration', 5)))
        if end <= start:
            raise ValueError('出点须晚于入点。')
        clips.append({'shot_id': s['id'], 'asset_id': a['id'], 'enabled': c.get('enabled') is not False,
                      'start': start, 'end': end, 'mute_source_audio': c.get('mute_source_audio') is True,
                      'dialogue': str(c.get('dialogue') or '')[:2000], 'subtitle_en': str(c.get('subtitle_en') or '')[:2000]})
    aid = payload.get('audio_asset_id') or None
    if aid and assets.get(aid, {}).get('kind') != 'audio':
        raise ValueError('剪辑配乐素材不存在。')
    aspect = payload.get('target_aspect', 'auto')
    if aspect not in ('auto', '16:9', '9:16'):
        raise ValueError('不支持的剪辑画幅。')
    settings = {'clips': clips, 'audio_asset_id': aid, 'audio_start': seconds(payload.get('audio_start', 0)),
                'target_aspect': aspect, 'burn_subtitles': payload.get('burn_subtitles') is True,
                'ducking': payload.get('ducking') is True}
    if 'subtitles' in payload:
        cues = payload['subtitles']
        if not isinstance(cues, list) or len(cues) > 500:
            raise ValueError('字幕列表无效。')
        settings['subtitles'] = []
        for c in cues:
            start, end = seconds(c['start']), seconds(c['end'])
            if end <= start:
                raise ValueError('字幕结束时间须晚于开始时间。')
            settings['subtitles'].append({'start': start, 'end': end, 'zh': str(c.get('zh') or '')[:2000], 'en': str(c.get('en') or '')[:2000]})
    return settings


def _normalize_assembly_items(server, workspace: dict, payload: dict):
    shots_by_id = {s['id']: s for s in workspace.get('shots', [])}
    assets_by_id = {a['id']: a for a in workspace.get('assets', [])}
    raw_items = payload.get('clips')
    if raw_items is None:
        raw_items = [{'shot_id': s['id']} for s in workspace.get('shots', []) if s.get('output')]
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError('当前没有可用于粗剪的已生成视频镜头。')

    resolved = []
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        if entry.get('enabled') is False:
            continue
        shot = shots_by_id.get(entry.get('shot_id', ''))
        asset_id = entry.get('asset_id') or (shot.get('output') if shot else None)
        asset = assets_by_id.get(asset_id) if asset_id else None
        if not asset or asset.get('kind') != 'video':
            continue
        path = resolve_asset_file(server, asset)
        meta = probe_media(server.ROOT, path)
        total = float(meta['duration'])
        start = max(0.0, float(entry.get('start', 0.0) or 0.0))
        end_raw = entry.get('end')
        end = min(total, float(end_raw)) if end_raw not in (None, '') and float(end_raw) > 0 else total
        if end - start < 0.05:
            raise ValueError(f"镜头《{shot['title'] if shot else asset['name']}》有效裁剪时长不足 0.05 秒。")
        resolved.append({
            'shot_id': shot['id'] if shot else '',
            'title': shot['title'] if shot else asset['name'],
            'asset_id': asset['id'],
            'path': path,
            'start': start,
            'end': end,
            'duration': end - start,
            'total_duration': total,
            'width': int(meta['width'] or 1080),
            'height': int(meta['height'] or 1920),
            'fps': float(meta['fps'] or 24.0),
            'has_audio': bool(meta.get('has_audio')),
            'mute_source_audio': bool(entry.get('mute_source_audio', False)),
            'dialogue': str(entry['dialogue'] if 'dialogue' in entry else (shot.get('dialogue', '') if shot else '')).strip(),
            'subtitle_en': str(entry['subtitle_en'] if 'subtitle_en' in entry else (shot.get('subtitle_en', '') if shot else '')).strip(),
        })
    if not resolved:
        raise ValueError('请至少保留一个包含视频样片的镜头用于粗剪。')

    audio_info = None
    audio_id = payload.get('audio_asset_id')
    if audio_id:
        a = assets_by_id.get(audio_id)
        if not a or a.get('kind') != 'audio':
            raise ValueError('所选背景音轨素材不存在或不是音频类型。')
        apath = resolve_asset_file(server, a)
        ameta = probe_media(server.ROOT, apath)
        audio_start = max(0.0, float(payload.get('audio_start', 0.0) or 0.0))
        audio_info = {
            'asset_id': a['id'],
            'name': a['name'],
            'path': apath,
            'start': audio_start,
            'total_duration': float(ameta['duration'] or 0.0),
        }
    return resolved, audio_info


def _build_timeline_subtitles(clips: list, explicit_subtitles=None) -> list:
    if isinstance(explicit_subtitles, list) and explicit_subtitles:
        out = []
        for s in explicit_subtitles:
            if isinstance(s, dict) and (s.get('zh') or s.get('en')):
                out.append({
                    'zh': str(s.get('zh', '')).strip(),
                    'en': str(s.get('en', '')).strip(),
                    'start': float(s.get('start', 0.0)),
                    'end': float(s.get('end', 0.0)),
                })
        return out
    cues = []
    cursor = 0.0
    for c in clips:
        dur = float(c['duration'])
        zh = c.get('dialogue', '')
        en = c.get('subtitle_en', '')
        if (zh or en) and dur >= 0.6:
            pad_in = min(0.45, dur * 0.12)
            pad_out = min(0.35, dur * 0.10)
            cues.append({
                'zh': zh,
                'en': en,
                'start': round(cursor + pad_in, 3),
                'end': round(cursor + dur - pad_out, 3),
            })
        cursor += dur
    return cues


def render_rough_cut_mp4(server, workspace: dict, payload: dict) -> dict:
    clips, audio = _normalize_assembly_items(server, workspace, payload)
    exports = server.DATA / 'exports'
    exports.mkdir(exist_ok=True)
    safe_proj = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in workspace['project'].get('name', 'Project'))[:40] or 'Project'
    stamp = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    target_aspect = payload.get('target_aspect', 'auto')
    if target_aspect not in ('auto', '16:9', '9:16'):
        target_aspect = 'auto'
    subtitles = _build_timeline_subtitles(clips, payload.get('subtitles'))
    burn_subtitles = bool(payload['burn_subtitles']) if 'burn_subtitles' in payload else False
    ducking = bool(payload.get('ducking', True))
    aspect_tag = '_9x16' if target_aspect == '9:16' else '_16x9' if target_aspect == '16:9' else ''
    sub_tag = '_subtitled' if (burn_subtitles and subtitles) else ''
    out_name = f'{safe_proj}{aspect_tag}{sub_tag}_roughcut_{stamp}.mp4'
    out_path = exports / out_name

    spec = {
        'clips': [
            {'path': str(c['path']), 'start': c['start'], 'end': c['end'], 'mute_source_audio': c['mute_source_audio']}
            for c in clips
        ],
        'audio_path': str(audio['path']) if audio else '',
        'audio_start': audio['start'] if audio else 0.0,
        'target_aspect': target_aspect,
        'burn_subtitles': burn_subtitles,
        'ducking': ducking,
        'bgm_base_volume': float(payload.get('bgm_base_volume', 0.36)),
        'bgm_duck_volume': float(payload.get('bgm_duck_volume', 0.12)),
        'subtitles': subtitles,
    }
    tool = media_tool_binary(server.ROOT)
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as tf:
        json.dump(spec, tf, ensure_ascii=False)
        spec_path = Path(tf.name)
    try:
        p = subprocess.run([str(tool), 'concat', str(spec_path), str(out_path)], capture_output=True, text=True, timeout=180)
        if p.returncode != 0:
            detail = p.stderr.strip() or p.stdout.strip()
            try:
                detail = json.loads(detail).get('error', detail)
            except Exception:
                pass
            raise RuntimeError(f'粗剪视频合成失败：{detail}')
        res = json.loads(p.stdout)
    finally:
        spec_path.unlink(missing_ok=True)

    return {
        'file': out_name,
        'url': f'/exports/{out_name}',
        'bytes': out_path.stat().st_size,
        'duration': round(float(res.get('duration', sum(c['duration'] for c in clips))), 3),
        'width': res.get('width', clips[0]['width']),
        'height': res.get('height', clips[0]['height']),
        'clips': len(clips),
    }


def _fcpxml_time(seconds: float, fps: int = 24) -> str:
    frames = max(0, round(seconds * fps))
    frac = Fraction(frames, fps)
    return f'{frac.numerator}/{frac.denominator}s' if frac.denominator != 1 else f'{frac.numerator}s'


def export_fcpxml(server, workspace: dict, payload: dict) -> dict:
    clips, audio = _normalize_assembly_items(server, workspace, payload)
    exports = server.DATA / 'exports'
    exports.mkdir(exist_ok=True)
    fps = max(12, min(60, round(clips[0]['fps'] or 24)))
    w, h = clips[0]['width'], clips[0]['height']
    proj_name = workspace['project'].get('name', 'CineHarbor Project')
    stamp = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    file_name = f'CineHarbor_Timeline_{stamp}.fcpxml'
    out_path = exports / file_name

    resources = [f'    <format id="r1" name="FFVideoFormat{w}x{h}p{fps}" frameDuration="1/{fps}s" width="{w}" height="{h}"/>']
    asset_res_map = {}
    next_r = 2
    for c in clips:
        key = str(c['path'])
        if key not in asset_res_map:
            rid = f'r{next_r}'
            next_r += 1
            asset_res_map[key] = rid
            uri = c['path'].resolve().as_uri()
            has_a = '1' if c['has_audio'] else '0'
            resources.append(
                f'    <asset id="{rid}" name="{xml_escape(c["title"])}" src="{xml_escape(uri)}" start="0s" '
                f'duration="{_fcpxml_time(c["total_duration"], fps)}" hasVideo="1" hasAudio="{has_a}" format="r1"/>'
            )
    audio_rid = None
    if audio:
        audio_rid = f'r{next_r}'
        uri = audio['path'].resolve().as_uri()
        resources.append(
            f'    <asset id="{audio_rid}" name="{xml_escape(audio["name"])}" src="{xml_escape(uri)}" start="0s" '
            f'duration="{_fcpxml_time(audio["total_duration"], fps)}" hasVideo="0" hasAudio="1"/>'
        )

    spine_lines = []
    offset_sec = 0.0
    for idx, c in enumerate(clips):
        rid = asset_res_map[str(c['path'])]
        dur_s = _fcpxml_time(c['duration'], fps)
        off_s = _fcpxml_time(offset_sec, fps)
        start_s = _fcpxml_time(c['start'], fps)
        if idx == 0 and audio and audio_rid:
            take_a = min(sum(x['duration'] for x in clips), max(0.0, audio['total_duration'] - audio['start']))
            spine_lines.append(
                f'            <asset-clip name="{xml_escape(c["title"])}" ref="{rid}" offset="{off_s}" start="{start_s}" duration="{dur_s}">\n'
                f'              <asset-clip name="{xml_escape(audio["name"])}" lane="-1" ref="{audio_rid}" offset="{start_s}" '
                f'start="{_fcpxml_time(audio["start"], fps)}" duration="{_fcpxml_time(take_a, fps)}" role="music"/>\n'
                f'            </asset-clip>'
            )
        else:
            spine_lines.append(
                f'            <asset-clip name="{xml_escape(c["title"])}" ref="{rid}" offset="{off_s}" start="{start_s}" duration="{dur_s}"/>'
            )
        offset_sec += c['duration']

    total_str = _fcpxml_time(offset_sec, fps)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE fcpxml>\n'
        '<fcpxml version="1.10">\n'
        '  <resources>\n' + '\n'.join(resources) + '\n  </resources>\n'
        f'  <library>\n    <event name="{xml_escape(proj_name)}">\n'
        f'      <project name="{xml_escape(proj_name)} · 粗剪">\n'
        f'        <sequence format="r1" duration="{total_str}" tcStart="0s" tcFormat="NDF">\n'
        '          <spine>\n' + '\n'.join(spine_lines) + '\n          </spine>\n'
        '        </sequence>\n      </project>\n    </event>\n  </library>\n</fcpxml>\n'
    )
    out_path.write_text(xml, encoding='utf-8')
    return {'file': file_name, 'url': f'/exports/{file_name}', 'bytes': out_path.stat().st_size, 'clips': len(clips)}


def export_capcut_draft(server, workspace: dict, payload: dict) -> dict:
    """Export a self-contained Jianying/CapCut draft ZIP (`draft_content.json` + `draft_meta_info.json` + bundled media)."""
    clips, audio = _normalize_assembly_items(server, workspace, payload)
    exports = server.DATA / 'exports'
    exports.mkdir(exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    file_name = f'CineHarbor_CapCut_Draft_{stamp}.zip'
    out_path = exports / file_name

    w, h = clips[0]['width'], clips[0]['height']
    fps = round(clips[0]['fps'] or 24)
    us = lambda sec: int(round(sec * 1_000_000))

    videos_mat = []
    audios_mat = []
    v_segments = []
    a_segments = []
    media_to_pack = []
    cursor_us = 0

    for idx, c in enumerate(clips):
        mat_id = uuid.uuid4().hex.upper()
        rel_media = f'Resources/{idx:02d}_{c["path"].name}'
        media_to_pack.append((c['path'], rel_media))
        videos_mat.append({
            'id': mat_id,
            'type': 'video',
            'path': f'##_draftpath_placeholder_0E685133-18CE-45ED-8CB8-2904A212EC80_##/{rel_media}',
            'material_name': c['title'],
            'width': c['width'],
            'height': c['height'],
            'duration': us(c['total_duration']),
            'has_audio': c['has_audio'],
        })
        dur_us = us(c['duration'])
        v_segments.append({
            'id': uuid.uuid4().hex.upper(),
            'material_id': mat_id,
            'source_timerange': {'start': us(c['start']), 'duration': dur_us},
            'target_timerange': {'start': cursor_us, 'duration': dur_us},
            'volume': 0.0 if c['mute_source_audio'] else 1.0,
            'speed': 1.0,
        })
        cursor_us += dur_us

    if audio:
        amat_id = uuid.uuid4().hex.upper()
        rel_audio = f'Resources/audio_{audio["path"].name}'
        media_to_pack.append((audio['path'], rel_audio))
        audios_mat.append({
            'id': amat_id,
            'type': 'extract_music',
            'path': f'##_draftpath_placeholder_0E685133-18CE-45ED-8CB8-2904A212EC80_##/{rel_audio}',
            'name': audio['name'],
            'duration': us(audio['total_duration']),
        })
        take_us = min(cursor_us, max(0, us(audio['total_duration'] - audio['start'])))
        if take_us > 0:
            a_segments.append({
                'id': uuid.uuid4().hex.upper(),
                'material_id': amat_id,
                'source_timerange': {'start': us(audio['start']), 'duration': take_us},
                'target_timerange': {'start': 0, 'duration': take_us},
                'volume': 1.0,
                'speed': 1.0,
            })

    tracks = [{'id': uuid.uuid4().hex.upper(), 'type': 'video', 'segments': v_segments}]
    if a_segments:
        tracks.append({'id': uuid.uuid4().hex.upper(), 'type': 'audio', 'segments': a_segments})

    texts_mat = []
    t_segments = []
    for cue in _build_timeline_subtitles(clips, payload.get('subtitles')):
        tid = uuid.uuid4().hex.upper()
        label = cue['zh'] + (f"\n{cue['en']}" if cue.get('en') else '')
        texts_mat.append({'id': tid, 'type': 'subtitle', 'content': label})
        t_segments.append({
            'id': uuid.uuid4().hex.upper(),
            'material_id': tid,
            'target_timerange': {'start': us(cue['start']), 'duration': max(100_000, us(cue['end'] - cue['start']))},
        })
    if t_segments:
        tracks.append({'id': uuid.uuid4().hex.upper(), 'type': 'text', 'segments': t_segments})

    draft_id = str(uuid.uuid4()).upper()
    now_us = int(time.time() * 1_000_000)
    draft_content = {
        'id': draft_id,
        'duration': cursor_us,
        'fps': float(fps),
        'canvas_config': {'width': w, 'height': h, 'ratio': workspace['project'].get('ratio', '9:16')},
        'materials': {'videos': videos_mat, 'audios': audios_mat, 'texts': texts_mat, 'canvases': []},
        'tracks': tracks,
    }
    draft_meta = {
        'draft_id': draft_id,
        'draft_name': workspace['project'].get('name', 'CineHarbor Draft'),
        'tm_draft_create': now_us,
        'tm_draft_modified': now_us,
        'tm_duration': cursor_us,
    }

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('draft_content.json', json.dumps(draft_content, ensure_ascii=False, indent=2))
        z.writestr('draft_meta_info.json', json.dumps(draft_meta, ensure_ascii=False, indent=2))
        z.writestr('README.txt', '包含时间线、字幕轨与自包含媒体的剪映 / CapCut 草稿交换包。请保留完整目录，并在目标客户端核对版本兼容性；不保证所有版本可直接打开。\n')
        for src_p, arc_name in media_to_pack:
            z.write(src_p, arc_name)

    return {'file': file_name, 'url': f'/exports/{file_name}', 'bytes': out_path.stat().st_size, 'clips': len(clips)}


def _srt_timestamp(sec: float) -> str:
    ms_total = max(0, int(round(sec * 1000)))
    hh, rem = divmod(ms_total, 3_600_000)
    mm, rem = divmod(rem, 60_000)
    ss, ms = divmod(rem, 1000)
    return f'{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}'


def export_srt_subtitles(server, workspace: dict, payload: dict) -> dict:
    clips, _ = _normalize_assembly_items(server, workspace, payload)
    cues = _build_timeline_subtitles(clips, payload.get('subtitles'))
    if not cues:
        raise ValueError('当前时间线镜头尚未填写对白/字幕文本。可在分镜设置或粗剪轨道中填写台词。')
    exports = server.DATA / 'exports'
    exports.mkdir(exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    file_name = f'CineHarbor_Subtitles_{stamp}.srt'
    out_path = exports / file_name
    blocks = []
    for i, c in enumerate(cues, 1):
        lines = [line for line in (c.get('zh', ''), c.get('en', '')) if line]
        blocks.append(f"{i}\n{_srt_timestamp(c['start'])} --> {_srt_timestamp(c['end'])}\n" + '\n'.join(lines))
    out_path.write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')
    return {'file': file_name, 'url': f'/exports/{file_name}', 'bytes': out_path.stat().st_size, 'cues': len(cues)}
