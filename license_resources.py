"""Resolve only public, packaged license documents, never workspace data."""
from pathlib import Path, PurePosixPath


def resolve_license(root, relative):
    root = Path(root)
    packaged = root.parent / 'Licenses'
    base = packaged if root.name == 'backend' and packaged.is_dir() else root / 'assets/licenses'
    path = PurePosixPath(relative)
    if not relative or not path.parts or len(relative) > 1000 or path.is_absolute() or '..' in path.parts or '\\' in relative:
        return None
    candidate = (base / relative).resolve()
    allowed_document = candidate.suffix.lower() in ('.txt', '.md', '.json')
    allowed_source = path.parts[0] == 'sources' and candidate.name.endswith('.tar.gz')
    if not candidate.is_relative_to(base.resolve()) or not (allowed_document or allowed_source):
        return None
    return candidate if candidate.is_file() else None
