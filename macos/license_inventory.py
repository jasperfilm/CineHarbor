"""Collect redistributed Python notices without copying machine configuration."""
from pathlib import Path
import email
import hashlib
import json
import re
import shutil


def collect(python_root, destination):
    python_root, destination = Path(python_root), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    site = python_root / 'lib/python3.13/site-packages'
    rows = []
    for metadata in sorted(site.glob('*.dist-info/METADATA')):
        data = email.message_from_bytes(metadata.read_bytes())
        name, version = data.get('Name'), data.get('Version')
        if not name or not version:
            raise ValueError('Dependency metadata is missing its name or version.')
        slug = re.sub(r'[^A-Za-z0-9._-]', '_', name + '-' + version)
        files = []
        for source in sorted(metadata.parent.rglob('*')):
            if not source.is_file() or not source.name.lower().startswith(('license', 'copying', 'notice')):
                continue
            if not source.resolve().is_relative_to(metadata.parent.resolve()):
                raise ValueError('Dependency notice points outside its package metadata.')
            relative = Path('python') / slug / source.relative_to(metadata.parent)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            files.append({'file': relative.as_posix(), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        rows.append({'name': name, 'version': version,
                     'declared_license': data.get('License-Expression') or data.get('License') or '',
                     'license_files': files, 'notice_status': 'present' if files else 'missing'})
    runtime_license = python_root / 'lib/python3.13/LICENSE.txt'
    if not runtime_license.is_file():
        raise ValueError('The CPython runtime license is missing.')
    shutil.copy2(runtime_license, destination / 'CPython-LICENSE.txt')
    result = {'components': rows, 'component_count': len(rows),
              'missing_notices': [r['name'] for r in rows if not r['license_files']],
              'scope': 'Bundled Python dependency notices and CPython license; not legal or store approval.'}
    (destination / 'python-components.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result
