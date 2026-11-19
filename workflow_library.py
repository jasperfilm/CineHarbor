"""Portable, local ComfyUI API recipes. Importing never executes a graph."""
import copy, json, re, uuid
from pathlib import PurePosixPath
from urllib.parse import urlparse

BINDINGS = {'prompt', 'negative_prompt', 'seed', 'width', 'height', 'frames', 'duration', 'reference', 'fps'}
ID = re.compile(r'^[A-Za-z0-9_:\-]{1,100}$')
NODE_DIR_RE = re.compile(r'^[A-Za-z0-9_.\-]{1,80}$')
SHA40_RE = re.compile(r'^[0-9a-f]{40}$')


def validate_graph(graph):
    if not isinstance(graph, dict) or not 1 <= len(graph) <= 512:
        raise ValueError('API工作流须包含1–512个节点。请使用ComfyUI的API格式导出，或使用自动画布转换。')
    if len(json.dumps(graph, ensure_ascii=False).encode()) > 2_000_000:
        raise ValueError('工作流请小于2MB。')
    edges = {str(k): [] for k in graph}
    for ident, node in graph.items():
        if (not isinstance(ident, str) or not ID.fullmatch(ident) or not isinstance(node, dict)
                or not isinstance(node.get('class_type'), str) or not node['class_type']
                or not isinstance(node.get('inputs'), dict)):
            raise ValueError('工作流节点缺少ID、class_type或inputs；不是API格式。')
        for key, value in node['inputs'].items():
            if key.lower() in ('api_key', 'access_token', 'auth_token', 'authorization', 'password'):
                raise ValueError('工作流不可包含账号密钥。只使用本地免费模型节点。')
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int) and not isinstance(value[1], bool):
                if value[0] not in graph or not 0 <= value[1] <= 64:
                    raise ValueError('节点连线指向不存在的节点或输出。')
                edges[ident].append(value[0])
    visiting = set()
    done = set()

    def visit(n):
        if n in visiting:
            raise ValueError('工作流包含循环连线。')
        if n in done:
            return
        visiting.add(n)
        for other in edges[n]:
            visit(other)
        visiting.remove(n)
        done.add(n)

    for n in edges:
        visit(n)
    return copy.deepcopy(graph)


def validate_bindings(graph, bindings):
    if not isinstance(bindings, dict) or set(bindings) - BINDINGS:
        raise ValueError('不支持的参数绑定。')
    for key, targets in bindings.items():
        if not isinstance(targets, list) or len(targets) > 64:
            raise ValueError('参数绑定须为节点列表。')
        for target in targets:
            if not isinstance(target, dict) or target.get('node') not in graph or target.get('input') not in graph[target['node']]['inputs']:
                raise ValueError('参数绑定指向不存在的输入。')
    return copy.deepcopy(bindings)


def infer_bindings(graph):
    result = {}
    aliases = {
        'text': 'prompt', 'prompt': 'prompt', 'caption': 'prompt', 'tags': 'prompt',
        'seed': 'seed', 'noise_seed': 'seed',
        'width': 'width', 'height': 'height',
        'length': 'frames', 'frames_number': 'frames',
        'seconds': 'duration', 'duration': 'duration',
        'fps': 'fps', 'frame_rate': 'fps'
    }
    for ident, node in graph.items():
        for key, value in node['inputs'].items():
            if isinstance(value, (list, dict)):
                continue
            bind = 'reference' if node['class_type'] == 'LoadImage' and key == 'image' else aliases.get(key)
            if bind == 'prompt' and ('negative' in node.get('_meta', {}).get('title', '').lower() or (isinstance(value, str) and any(w in value for w in ('低质量', '最差质量', 'blurry', 'ugly')))):
                bind = 'negative_prompt'
            if bind:
                result.setdefault(bind, []).append({'node': ident, 'input': key})
    return result


def validate_model_files(files):
    if not isinstance(files, list) or len(files) > 64:
        raise ValueError('模型文件清单超过限制。')
    allowed = {'diffusion_models', 'text_encoders', 'vae', 'checkpoints', 'clip_vision', 'loras', 'latent_upscale_models', 'controlnet'}
    clean = []
    for item in files:
        if not isinstance(item, dict):
            raise ValueError('模型清单无效。')
        name = item.get('file', '')
        path = PurePosixPath(name)
        url = item.get('url', '')
        u = urlparse(url)
        if path.is_absolute() or len(path.parts) < 2 or path.parts[0] not in allowed or '..' in path.parts or '\\' in name or path.suffix != '.safetensors':
            raise ValueError('模型文件须在ComfyUI模型目录中，使用safetensors。')
        if u.scheme != 'https' or u.hostname != 'huggingface.co' or u.username or u.password or u.query or '/resolve/' not in u.path:
            raise ValueError('只支持不含密钥的Hugging Face HTTPS模型地址。')
        sha = item.get('sha256', '')
        if sha and not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('SHA256须为64位小写十六进制。')
        if re.search(r'(?i)(fp8|int8|gguf|int4|fp4|4bit|8bit)', path.name):
            raise ValueError('当前生产要求完整高精度模型；不安装量化权重。')
        clean.append({'file': name, 'url': url, 'sha256': sha})
    if len({x['file'] for x in clean}) != len(clean):
        raise ValueError('模型文件清单重复。')
    return clean


def validate_custom_nodes(nodes):
    """Validate auditable custom node lock entries (HTTPS GitHub repo + pinned 40-char commit SHA)."""
    if nodes is None:
        return []
    if not isinstance(nodes, list) or len(nodes) > 32:
        raise ValueError('自定义节点锁文件数量超过限制（最多32项）。')
    clean = []
    seen_names = set()
    seen_urls = set()
    for item in nodes:
        if not isinstance(item, dict):
            raise ValueError('自定义节点锁条目格式无效。')
        url = str(item.get('repo', '')).strip().rstrip('/')
        if url.endswith('.git'):
            url = url[:-4]
        commit = str(item.get('commit', '')).strip()
        u = urlparse(url)
        parts = [p for p in u.path.split('/') if p]
        if u.scheme != 'https' or u.hostname != 'github.com' or u.username or u.password or u.query or u.fragment or len(parts) != 2:
            raise ValueError('自定义节点仅支持公开 HTTPS GitHub 仓库地址（https://github.com/owner/repo）。')
        if not all(NODE_DIR_RE.fullmatch(p) and p not in ('.', '..') for p in parts):
            raise ValueError('GitHub 仓库路径不合法。')
        if not SHA40_RE.fullmatch(commit):
            raise ValueError('自定义节点必须锁定完整40位小写十六进制 Commit SHA，禁止浮动分支。')
        name = str(item.get('name') or parts[1]).strip()
        if not NODE_DIR_RE.fullmatch(name) or name in ('.', '..'):
            raise ValueError('自定义节点目录名不合法。')
        if name in seen_names or url.lower() in seen_urls:
            raise ValueError('自定义节点目录名或仓库重复。')
        seen_names.add(name)
        seen_urls.add(url.lower())
        clean.append({'name': name, 'repo': f'https://github.com/{parts[0]}/{parts[1]}.git', 'commit': commit})
    return clean


def recipe(payload, previous=None):
    graph = validate_graph(payload.get('graph', {}))
    bindings = validate_bindings(graph, payload.get('bindings', infer_bindings(graph)))
    kind = payload.get('kind', 'video')
    if kind not in ('image', 'video', 'audio'):
        raise ValueError('工作流类型须为图像、视频或音频。')
    timing = payload.get('timing', {})
    if not timing:
        types = ' '.join(n['class_type'] for n in graph.values())
        fps = next((n['inputs'].get(k) for n in graph.values() for k in ('fps', 'frame_rate') if isinstance(n['inputs'].get(k), (int, float)) and 1 <= n['inputs'].get(k) <= 60), 24)
        timing = {'fps': fps, 'frame_multiple': 17 if 'MiniMaxH3' in types else 8 if 'LTX' in types else 4, 'frame_offset': 5 if 'MiniMaxH3' in types else 1}
    if (not isinstance(timing, dict) or not 1 <= float(timing.get('fps', 0)) <= 60
            or not isinstance(timing.get('frame_multiple'), int) or not 1 <= timing['frame_multiple'] <= 64
            or not isinstance(timing.get('frame_offset'), int) or not 0 <= timing['frame_offset'] < timing['frame_multiple']):
        raise ValueError('帧率或帧数对齐设置无效。')
    name = str(payload.get('name', '')).strip()[:100]
    if not name:
        raise ValueError('请填写工作流名称。')
    positions = {}
    for key, p in payload.get('positions', {}).items():
        if key not in graph or not isinstance(p, list) or len(p) != 2:
            raise ValueError('节点位置无效。')
        if not all(isinstance(x, (int, float)) and abs(x) <= 50000 for x in p):
            raise ValueError('节点位置越界。')
        positions[key] = p
    return {
        'id': previous['id'] if previous else uuid.uuid4().hex,
        'name': name,
        'kind': kind,
        'graph': graph,
        'bindings': bindings,
        'positions': positions,
        'timing': copy.deepcopy(timing),
        'model_files': validate_model_files(payload.get('model_files', [])),
        'custom_nodes': validate_custom_nodes(payload.get('custom_nodes', [])),
        'revision': previous.get('revision', 0) + 1 if previous else 1,
        'versions': ([dict((k, v) for k, v in previous.items() if k != 'versions')] + previous.get('versions', []))[:20] if previous else []
    }


def materialize(item, values):
    graph = validate_graph(item['graph'])
    bindings = validate_bindings(graph, item.get('bindings', {}))
    for key, targets in bindings.items():
        if key not in values:
            continue
        for target in targets:
            graph[target['node']]['inputs'][target['input']] = values[key]
    return graph


def remote_validate(graph, info):
    missing = sorted({n['class_type'] for n in graph.values()} - set(info))
    if missing:
        raise ValueError('当前ComfyUI缺少节点：' + ', '.join(missing))
    for node in graph.values():
        spec = info[node['class_type']]
        if spec.get('api_node') or spec.get('is_api_node') or 'api_node' in spec.get('category', '').lower():
            raise ValueError('此工作流包含付费API节点；只允许运行本地模型。')
    return True
