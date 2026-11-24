"""Convert ComfyUI LiteGraph canvas JSON (including ComfyUI 1.59+ subgraphs) into clean API recipes."""
import ast, copy, json, math, operator
from pathlib import Path
from workflow_library import infer_bindings, validate_graph

# Built-in widget order specs for standard ComfyUI nodes and all bundled official templates.
# Entries named '_control' represent LiteGraph UI-only seed/control widgets ('fixed'/'randomize'/etc.) that are not sent to /prompt.
WIDGET_SPECS = {
    'CheckpointLoaderSimple': ['ckpt_name'],
    'UNETLoader': ['unet_name', 'weight_dtype'],
    'CLIPLoader': ['clip_name', 'type', 'device'],
    'DualCLIPLoader': ['clip_name1', 'clip_name2', 'type', 'device'],
    'VAELoader': ['vae_name'],
    'LoraLoader': ['lora_name', 'strength_model', 'strength_clip'],
    'LoraLoaderModelOnly': ['lora_name', 'strength_model'],
    'LatentUpscaleModelLoader': ['model_name'],
    'CLIPTextEncode': ['text'],
    'ConditioningZeroOut': [],
    'EmptyLatentImage': ['width', 'height', 'batch_size'],
    'EmptySD3LatentImage': ['width', 'height', 'batch_size'],
    'EmptyLTXVLatentVideo': ['width', 'height', 'length', 'batch_size'],
    'EmptyAceStep1.5LatentAudio': ['seconds', 'batch_size'],
    'LTXVEmptyLatentAudio': ['frames_number', 'frame_rate', 'batch_size'],
    'WanImageToVideo': ['width', 'height', 'length', 'batch_size'],
    'MiniMaxH3ImageToVideo': ['prompt', 'width', 'height', 'length'],
    'KSampler': ['seed', '_control', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise'],
    'KSamplerAdvanced': ['add_noise', 'noise_seed', '_control', 'steps', 'cfg', 'sampler_name', 'scheduler', 'start_at_step', 'end_at_step', 'return_with_leftover_noise'],
    'KSamplerSelect': ['sampler_name'],
    'BasicScheduler': ['scheduler', 'steps', 'denoise'],
    'ManualSigmas': ['sigmas'],
    'RandomNoise': ['noise_seed', '_control'],
    'SamplerCustomAdvanced': [],
    'BasicGuider': [],
    'CFGGuider': ['cfg'],
    'LTXVDualCFGGuider': ['cfg', 'stg'],
    'LTXVConditioning': ['frame_rate'],
    'LTXVImgToVideoInplace': ['strength', 'bypass'],
    'LTXVPreprocess': ['img_compression'],
    'LTXVLatentUpsampler': [],
    'LTXVSeparateAVLatent': [],
    'LTXVConcatAVLatent': [],
    'LTXVAudioVAEDecode': [],
    'ModelSamplingAuraFlow': ['shift'],
    'ModelSamplingSD3': ['shift'],
    'MiniMaxH3SigmaShift': ['shift_video', 'shift_audio'],
    'CFGNorm': ['strength', 'pre_cfg'],
    'FluxKontextMultiReferenceLatentMethod': ['reference_latents_method'],
    'FluxKontextImageScale': [],
    'TextEncodeQwenImageEdit': ['prompt'],
    'TextEncodeQwenImageEditPlus': ['prompt'],
    'VAEDecode': [],
    'VAEDecodeTiled': ['tile_size', 'overlap', 'temporal_size', 'temporal_overlap'],
    'VAEDecodeAudio': [],
    'LoadImage': ['image', 'upload'],
    'ResizeImageMaskNode': ['resize_type', 'scale_To_length', 'interpolation'],
    'ResolutionSelector': ['aspect_ratio', 'megapixels', 'divisible_by'],
    'CreateVideo': ['fps', 'bit_depth'],
    'SaveImage': ['filename_prefix'],
    'SaveVideo': ['filename_prefix', 'format', 'codec'],
    'SaveAudio': ['filename_prefix'],
    'SaveAudioMP3': ['filename_prefix', 'quality'],
    'PreviewImage': [],
    'PreviewAny': [],
    'TextEncodeAceStepAudio1.5': [
        'tags', 'lyrics', 'seed', '_control', 'bpm', 'duration', 'timesignature',
        'language', 'keyscale', 'generate_audio_codes', 'cfg_scale', 'temperature', 'top_p', 'top_k', 'min_p'
    ],
    'TextGenerateLTX2Prompt': [
        'prompt', 'max_length', 'sampling_mode', 'temperature', 'top_k', 'top_p',
        'min_p', 'repetition_penalty', 'seed', '_control', 'do_sample', 'add_generation_prompt'
    ],
    'ComfySwitchNode': ['switch'],
    'ComfyMathExpression': ['expression'],
    'PrimitiveInt': ['value', '_control'],
    'PrimitiveFloat': ['value'],
    'PrimitiveBoolean': ['value'],
    'PrimitiveString': ['value'],
    'PrimitiveStringMultiline': ['value'],
}

UI_SKIP_TYPES = {'Note', 'MarkdownNote'}
SEED_CONTROL_WORDS = {'fixed', 'increment', 'decrement', 'randomize'}


def _widget_names_from_object_info(class_type, object_info):
    if not object_info or class_type not in object_info:
        return None
    spec = object_info[class_type]
    inp = spec.get('input', {})
    names = []
    for section in ('required', 'optional'):
        block = inp.get(section, {})
        if not isinstance(block, dict):
            continue
        for name, meta in block.items():
            if not isinstance(meta, list) or not meta:
                continue
            kind = meta[0]
            opts = meta[1] if len(meta) > 1 and isinstance(meta[1], dict) else {}
            if isinstance(kind, list) or kind in ('INT', 'FLOAT', 'STRING', 'BOOLEAN', 'COMBO'):
                names.append(name)
                if name in ('seed', 'noise_seed') or opts.get('control_after_generate'):
                    names.append('_control')
    return names


def _normalize_links(raw_links):
    """Support both top-level array links [id, orig, orig_slot, target, target_slot, type] and subgraph dict links."""
    by_id = {}
    for item in raw_links or []:
        if isinstance(item, list) and len(item) >= 5:
            by_id[item[0]] = (str(item[1]), int(item[2]), str(item[3]), int(item[4]))
        elif isinstance(item, dict) and 'id' in item:
            by_id[item['id']] = (str(item['origin_id']), int(item['origin_slot']), str(item['target_id']), int(item['target_slot']))
    return by_id


def _safe_math_eval(expr, env):
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
    funcs = {'floor': math.floor, 'ceil': math.ceil, 'round': round, 'min': min, 'max': max, 'int': int, 'float': float, 'abs': abs}

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id in env:
            return env[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            val = ev(node.operand)
            return +val if isinstance(node.op, ast.UAdd) else -val
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in funcs and not node.keywords:
            return funcs[node.func.id](*[ev(a) for a in node.args])
        raise ValueError('Unsupported math expression')

    return ev(ast.parse(expr.strip(), mode='eval'))


def _assign_node_inputs(node, link_lookup, object_info=None):
    ctype = node['type']
    inputs_list = node.get('inputs') or []
    wv = node.get('widgets_values')
    result = {}

    for slot in inputs_list:
        name = slot.get('name')
        lid = slot.get('link')
        if name and lid is not None and lid in link_lookup:
            orig_id, orig_slot = link_lookup[lid]
            result[name] = [orig_id, orig_slot]

    if isinstance(wv, dict):
        for k, v in wv.items():
            if k not in result and k != 'videopreview':
                result[k] = copy.deepcopy(v)
        return result

    if not isinstance(wv, list) or not wv:
        return result

    spec_names = _widget_names_from_object_info(ctype, object_info)
    if spec_names is None:
        spec_names = WIDGET_SPECS.get(ctype)

    if spec_names is None:
        # Fallback: map from declared widget slots on the LiteGraph node itself
        declared = [s['name'] for s in inputs_list if 'widget' in s and s.get('name')]
        spec_names = []
        idx = 0
        for name in declared:
            spec_names.append(name)
            idx += 1
            if idx < len(wv) and name in ('seed', 'noise_seed') and wv[idx] in SEED_CONTROL_WORDS:
                spec_names.append('_control')
                idx += 1
        while len(spec_names) < len(wv):
            val = wv[len(spec_names)]
            if val in SEED_CONTROL_WORDS and spec_names and spec_names[-1] in ('seed', 'noise_seed', 'value'):
                spec_names.append('_control')
            else:
                spec_names.append(f'param_{len(spec_names)}')

    for name, val in zip(spec_names, wv):
        if name == '_control' or (ctype == 'LoadImage' and name == 'upload'):
            continue
        if name not in result:
            result[name] = copy.deepcopy(val)
    return result


def convert_canvas_to_api(canvas, object_info=None):
    """Convert a LiteGraph canvas dict (with 'nodes') into {'graph', 'positions', 'kind', 'bindings'}."""
    if not isinstance(canvas, dict) or not isinstance(canvas.get('nodes'), list):
        raise ValueError('不是有效的 ComfyUI 画布 JSON。')

    subgraphs = {sg['id']: sg for sg in (canvas.get('definitions') or {}).get('subgraphs') or [] if isinstance(sg, dict) and 'id' in sg}
    flat_nodes = {}
    positions = {}
    raw_sources = {}  # (node_id, input_name) -> (origin_id, origin_slot) or scalar

    def expand_scope(nodes, links_raw, prefix='', ext_inputs=None, offset_xy=(0.0, 0.0)):
        ext_inputs = ext_inputs or {}
        links = _normalize_links(links_raw)
        # Map link_id -> (resolved_origin_id, resolved_origin_slot) or ('__CONST__', value)
        link_source = {}
        for lid, (oid, oslot, _tid, _tslot) in links.items():
            if oid == '-10':
                if oslot in ext_inputs:
                    link_source[lid] = ext_inputs[oslot]
            else:
                link_source[lid] = (f'{prefix}{oid}', oslot)

        sub_out_map = {}  # (prefixed_sg_call_id, out_slot) -> resolved source

        for n in nodes:
            if not isinstance(n, dict) or 'id' not in n or 'type' not in n:
                continue
            if n.get('mode', 0) in (2, 4):
                # Muted or bypassed node: pass through first linked input if same-type, or skip
                nid = f"{prefix}{n['id']}"
                first_link = next((inp.get('link') for inp in (n.get('inputs') or []) if inp.get('link') in link_source), None)
                if first_link is not None:
                    sub_out_map[(nid, 0)] = link_source[first_link]
                continue

            ntype = n['type']
            if ntype in UI_SKIP_TYPES:
                continue

            nid = f"{prefix}{n['id']}"
            pos = n.get('pos')
            if isinstance(pos, list) and len(pos) >= 2 and all(isinstance(v, (int, float)) for v in pos[:2]):
                xy = [round(pos[0] + offset_xy[0]), round(pos[1] + offset_xy[1])]
            elif isinstance(pos, dict) and '0' in pos and '1' in pos:
                xy = [round(float(pos['0']) + offset_xy[0]), round(float(pos['1']) + offset_xy[1])]
            else:
                xy = [120 + len(positions) * 280, 100]

            if ntype in subgraphs:
                sg = subgraphs[ntype]
                sg_inputs = sg.get('inputs') or []
                call_inputs_by_name = {inp.get('name'): inp for inp in (n.get('inputs') or []) if inp.get('name')}
                wv = n.get('widgets_values') if isinstance(n.get('widgets_values'), list) else []

                # Match outer widget values to subgraph inputs that carry widgets/defaults
                # Note: ComfyUI subgraph call nodes store widget values in sg.inputs order skipping pure non-widget socket types (like IMAGE/MODEL/LATENT/AUDIO/VAE/CLIP)
                NON_WIDGET_TYPES = {'IMAGE', 'MASK', 'IMAGE,MASK', 'LATENT', 'MODEL', 'CLIP', 'VAE', 'CONDITIONING', 'AUDIO', 'VIDEO', 'SIGMAS', 'GUIDER', 'SAMPLER', 'NOISE', 'CLIP_VISION_OUTPUT', 'LATENT_UPSCALE_MODEL'}
                w_idx = 0
                child_ext = {}
                for idx, sgi in enumerate(sg_inputs):
                    sname = sgi.get('name')
                    stype = str(sgi.get('type', ''))
                    outer_slot = call_inputs_by_name.get(sname)
                    is_widget_type = stype not in NON_WIDGET_TYPES
                    w_val = None
                    if is_widget_type and w_idx < len(wv):
                        w_val = wv[w_idx]
                        w_idx += 1
                    if outer_slot and outer_slot.get('link') is not None and outer_slot['link'] in link_source:
                        child_ext[idx] = link_source[outer_slot['link']]
                    elif w_val is not None:
                        child_ext[idx] = ('__CONST__', copy.deepcopy(w_val))

                inner_out = expand_scope(sg.get('nodes') or [], sg.get('links') or [], prefix=f'{nid}_', ext_inputs=child_ext, offset_xy=(xy[0], xy[1]))
                sg_links = _normalize_links(sg.get('links') or [])
                for out_idx, sgo in enumerate(sg.get('outputs') or []):
                    lids = sgo.get('linkIds') or []
                    lid = lids[0] if lids else next((k for k, v in sg_links.items() if v[2] == '-20' and v[3] == out_idx), None)
                    if lid is not None and lid in sg_links:
                        oid, oslot, _, _ = sg_links[lid]
                        src_key = (f'{nid}_{oid}', oslot)
                        sub_out_map[(nid, out_idx)] = inner_out.get(src_key, src_key)
                continue

            flat_nodes[nid] = n
            positions[nid] = [max(20, min(48000, xy[0])), max(20, min(48000, xy[1]))]
            raw_sources[nid] = link_source

        return sub_out_map

    top_out_map = expand_scope(canvas['nodes'], canvas.get('links') or [])

    # First build raw input dictionary for every flattened node
    api_nodes = {}
    for nid, n in flat_nodes.items():
        link_source = raw_sources[nid]
        local_links = {}
        const_overrides = {}
        for inp in n.get('inputs') or []:
            lid = inp.get('link')
            name = inp.get('name')
            if not name or lid is None or lid not in link_source:
                continue
            target = link_source[lid]
            while isinstance(target, tuple) and len(target) == 2 and target[0] != '__CONST__' and target in top_out_map:
                target = top_out_map[target]
            if isinstance(target, tuple) and len(target) == 2 and target[0] == '__CONST__':
                const_overrides[name] = target[1]
            elif isinstance(target, tuple) and len(target) == 2:
                local_links[lid] = target
        inputs = _assign_node_inputs(n, local_links, object_info=object_info)
        inputs.update(const_overrides)
        meta = {'title': n['title']} if n.get('title') else {}
        entry = {'class_type': n['type'], 'inputs': inputs}
        if meta:
            entry['_meta'] = meta
        api_nodes[nid] = entry

    # Resolve pure utility/frontend helper nodes: Reroute, Primitive*, ComfySwitchNode, ComfyMathExpression
    memo = {}

    def resolve_output(nid, slot, stack=frozenset()):
        if (nid, slot) in memo:
            return memo[(nid, slot)]
        if nid in stack or nid not in api_nodes:
            return [nid, slot]
        stack = stack | {nid}
        node = api_nodes[nid]
        ctype = node['class_type']
        ins = node['inputs']

        def val_of(key):
            v = ins.get(key)
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int):
                return resolve_output(v[0], v[1], stack)
            return v

        resolved = [nid, slot]
        if ctype == 'Reroute':
            first_key = next(iter(ins), None)
            if first_key is not None:
                resolved = val_of(first_key)
        elif ctype in ('PrimitiveNode', 'PrimitiveInt', 'PrimitiveFloat', 'PrimitiveBoolean', 'PrimitiveString', 'PrimitiveStringMultiline'):
            if 'value' in ins:
                resolved = val_of('value')
            elif ins:
                resolved = val_of(next(iter(ins)))
        elif ctype == 'ComfySwitchNode':
            sw = val_of('switch')
            if isinstance(sw, bool):
                branch = val_of('on_true' if sw else 'on_false')
                if branch is not None:
                    resolved = branch
        elif ctype == 'ComfyMathExpression':
            expr = ins.get('expression', '')
            env = {}
            ok = True
            for var in ('a', 'b', 'c'):
                k = f'values.{var}'
                if k in ins and ins[k] is not None:
                    rv = val_of(k)
                    if isinstance(rv, (int, float, bool)):
                        env[var] = float(rv) if not isinstance(rv, bool) else int(rv)
                    else:
                        ok = False
            if ok and isinstance(expr, str) and expr.strip():
                try:
                    num = _safe_math_eval(expr, env)
                    resolved = int(num) if isinstance(num, int) or (isinstance(num, float) and num.is_integer()) else float(num)
                except Exception:
                    pass

        memo[(nid, slot)] = resolved
        return resolved

    HELPER_TYPES = {'Reroute', 'PrimitiveNode', 'PrimitiveInt', 'PrimitiveFloat', 'PrimitiveBoolean', 'PrimitiveString', 'PrimitiveStringMultiline', 'ComfySwitchNode', 'ComfyMathExpression'}
    final_graph = {}
    for nid, node in api_nodes.items():
        if node['class_type'] in HELPER_TYPES:
            # Keep helper node only if it could not be statically resolved and something still links to it later
            continue
        new_inputs = {}
        for k, v in node['inputs'].items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int):
                rv = resolve_output(v[0], v[1])
                new_inputs[k] = rv
            else:
                new_inputs[k] = v
        # Drop None optional unlinked sockets cleanly except where required
        cleaned_inputs = {k: v for k, v in new_inputs.items() if v is not None}
        final_graph[nid] = {**node, 'inputs': cleaned_inputs}

    # If any remaining link points to a helper node that wasn't statically folded, keep that helper node
    needed_helpers = set()
    for node in final_graph.values():
        for v in node['inputs'].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in api_nodes and v[0] not in final_graph:
                needed_helpers.add(v[0])
    while needed_helpers:
        hid = needed_helpers.pop()
        hnode = copy.deepcopy(api_nodes[hid])
        for k, v in list(hnode['inputs'].items()):
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int):
                rv = resolve_output(v[0], v[1])
                hnode['inputs'][k] = rv
                if isinstance(rv, list) and rv[0] in api_nodes and rv[0] not in final_graph:
                    needed_helpers.add(rv[0])
        final_graph[hid] = hnode

    # Normalize coordinates so top-left starts near (80, 70)
    final_positions = {nid: positions[nid] for nid in final_graph if nid in positions}
    if final_positions:
        min_x = min(p[0] for p in final_positions.values())
        min_y = min(p[1] for p in final_positions.values())
        final_positions = {
            nid: [max(40, min(48000, round(p[0] - min_x + 80))), max(40, min(48000, round(p[1] - min_y + 70)))]
            for nid, p in final_positions.items()
        }

    validate_graph(final_graph)
    ctypes = ' '.join(n['class_type'] for n in final_graph.values())
    if any(t in ctypes for t in ('SaveAudio', 'VAEDecodeAudio', 'AceStep')):
        kind = 'audio'
    elif any(t in ctypes for t in ('SaveVideo', 'CreateVideo', 'ImageToVideo', 'LTXV', 'WanImageToVideo')):
        kind = 'video'
    else:
        kind = 'image'

    return {
        'graph': final_graph,
        'positions': final_positions,
        'kind': kind,
        'bindings': infer_bindings(final_graph),
        'converted_from_canvas': True
    }


def load_cached_object_info(data_dir):
    p = Path(data_dir) / 'cache/object_info.json'
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None
