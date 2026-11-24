"""Portable ComfyUI workspace snapshots. No models, application login files or live jobs. Custom node fields may contain user-entered secrets.

The canvas is explicitly captured by the frontend; browser autosave is not a
backup. Media are stored at their original managed relative paths, so loaders
keep working on a fresh runtime. Existing different files are never overwritten.
"""
import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA = 'cineharbor.comfy-project.v1'
MAX_FILES = 100000
MAX_BYTES = 100 * 1024 ** 3
FOLDERS = {'input': 'input', 'output': 'output', 'temp': 'temp', 'workflows': 'user/default/workflows'}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def child(root, rel):
    p = PurePosixPath(rel)
    if not rel or p.is_absolute() or '..' in p.parts or '\\' in rel:
        raise ValueError('Unsafe snapshot path')
    target = Path(root) / rel
    if not target.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Snapshot path escapes workspace')
    # Do not traverse even an internal symlink: restores must not alias assets.
    current = Path(root)
    for part in p.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Snapshot paths must not contain symlinks')
    return target


def validate_canvas(canvas):
    if not isinstance(canvas, dict) or not isinstance(canvas.get('nodes'), list) or not isinstance(canvas.get('links'), list):
        raise ValueError('Save a complete ComfyUI UI workflow, not an API prompt')
    # Ensure JSON serializable before creating an archive.
    json.dumps(canvas, allow_nan=False)


def check_media_references(root, canvas):
    """Reject known missing/external media rather than claiming a full snapshot.

Custom nodes can invent their own resource formats; this covers ordinary file
widgets, not arbitrary third-party storage or embedded executable node state.
"""
    extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.webm', '.mov', '.mkv', '.wav', '.mp3', '.flac', '.ogg', '.m4a'}
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
    for node in canvas['nodes']:
        kind = str(node.get('type', '')).lower()
        if kind.startswith(('save', 'preview')) or kind in ('note', 'markdownnote'):
            continue
        for value in strings(node.get('widgets_values', [])):
            value = value.strip()
            if '\n' in value:
                continue
            annotation = None
            for folder in ('input', 'output', 'temp'):
                if value.endswith(' [' + folder + ']'):
                    value, annotation = value[:-(len(folder) + 3)], folder
                    break
            if Path(value).suffix.lower() not in extensions:
                continue
            if '://' in value:
                raise ValueError('Canvas uses external media; copy it into ComfyUI input before saving')
            if Path(value).is_absolute():
                candidate = Path(value)
                if not any(candidate.resolve().is_relative_to((root / folder).resolve()) for folder in ('input', 'output', 'temp')):
                    raise ValueError('Canvas uses media outside managed folders; copy it into ComfyUI input before saving')
                if not candidate.is_file():
                    raise ValueError('Canvas references missing media; snapshot not saved')
            else:
                folders = (annotation,) if annotation else ('input', 'output', 'temp')
                if not any(child(root / folder, value).is_file() for folder in folders):
                    raise ValueError('Canvas references missing media; snapshot not saved')


def pack(root, destination, canvas, name, environment=None):
    validate_canvas(canvas)
    root, destination = Path(root), Path(destination)
    check_media_references(root, canvas)
    if destination.resolve().is_relative_to(root.resolve()):
        raise ValueError('Archive must be outside the workspace')
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'schema': SCHEMA, 'id': uuid.uuid4().hex,
                'name': str(name).strip()[:160] or 'ComfyUI workspace',
                'scope': 'All managed ComfyUI input/output files and saved workflows; no models.',
                'files': [], 'environment': environment or {}}
    pending = destination.with_name(destination.name + '.partial')
    try:
        with zipfile.ZipFile(pending, 'w', zipfile.ZIP_STORED, allowZip64=True) as z:
            z.writestr('canvas.json', json.dumps(canvas, ensure_ascii=False, allow_nan=False))
            total = 0
            for label, folder in FOLDERS.items():
                source = root / folder
                if source.is_symlink():
                    raise ValueError('Managed folder is a symlink')
                for p in sorted(source.rglob('*')) if source.exists() else []:
                    if p.is_symlink():
                        raise ValueError('Managed media contains a symlink; snapshot not complete')
                    if not p.is_file():
                        continue
                    rel = p.relative_to(source).as_posix()
                    child(source, rel)
                    before = p.stat()
                    total += before.st_size
                    if len(manifest['files']) >= MAX_FILES or total > MAX_BYTES:
                        raise ValueError('Snapshot exceeds supported size')
                    arcname = 'files/' + label + '/' + rel
                    sha = digest(p)
                    z.write(p, arcname)
                    if p.stat().st_mtime_ns != before.st_mtime_ns or digest(p) != sha:
                        raise ValueError('Workspace changed during snapshot; retry after work stops')
                    manifest['files'].append({'path': arcname, 'bytes': before.st_size, 'sha256': sha})
            z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
        inspect_archive(pending)
        pending.chmod(0o600)
        os.replace(pending, destination)
    finally:
        pending.unlink(missing_ok=True)
    return manifest


def inspect_archive(archive):
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or len(names) > MAX_FILES + 2 or sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError('Invalid or oversized snapshot')
        for i in infos:
            child(Path(tempfile.gettempdir()) / 'cineharbor-validation-only', i.filename)
            if stat.S_ISLNK(i.external_attr >> 16):
                raise ValueError('Snapshot contains a symlink')
        if z.getinfo('manifest.json').file_size > 32 * 1024 ** 2 or z.getinfo('canvas.json').file_size > 30 * 1024 ** 2:
            raise ValueError('Snapshot metadata is too large')
        manifest = json.loads(z.read('manifest.json'))
        canvas = json.loads(z.read('canvas.json'))
        validate_canvas(canvas)
        if manifest.get('schema') != SCHEMA:
            raise ValueError('Unsupported snapshot format')
        expected = {'canvas.json', 'manifest.json'}
        for entry in manifest['files']:
            name = entry['path']
            parts = PurePosixPath(name).parts
            if len(parts) < 3 or parts[0] != 'files' or parts[1] not in FOLDERS or name in expected:
                raise ValueError('Invalid file mapping')
            expected.add(name)
            info = z.getinfo(name)
            h = hashlib.sha256()
            with z.open(name) as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(block)
            if info.file_size != entry['bytes'] or h.hexdigest() != entry['sha256']:
                raise ValueError('Snapshot file checksum mismatch')
        if expected != set(names):
            raise ValueError('Unlisted snapshot files')
    return manifest, canvas


def restore(root, archive):
    """Validate before writes; preserve existing files and never queue generation."""
    root = Path(root)
    manifest, canvas = inspect_archive(archive)
    targets = []
    for entry in manifest['files']:
        parts = PurePosixPath(entry['path']).parts
        target = child(root, FOLDERS[parts[1]] + '/' + '/'.join(parts[2:]))
        if target.exists() and (not target.is_file() or digest(target) != entry['sha256']):
            raise ValueError('Existing workspace contains a different file; use a fresh workspace')
        targets.append((entry, target))
    root.mkdir(parents=True, exist_ok=True)
    required = sum(e['bytes'] for e, p in targets if not p.exists())
    if shutil.disk_usage(root).free < required + 1024 ** 2:
        raise ValueError('Not enough free disk space to restore')
    created = []
    try:
        with zipfile.ZipFile(archive) as z:
            for entry, target in targets:
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation: never silently overwrite a concurrent edit.
                with target.open('xb') as out:
                    created.append(target)
                    with z.open(entry['path']) as src:
                        shutil.copyfileobj(src, out)
                if digest(target) != entry['sha256']:
                    raise ValueError('Restored file checksum mismatch')
    except Exception:
        for p in reversed(created):
            p.unlink(missing_ok=True)
        raise
    return {'canvas': canvas, 'name': manifest['name'], 'files': len(targets), 'hash_verified': True,
            'generation_started': False, 'environment': manifest.get('environment', {})}
