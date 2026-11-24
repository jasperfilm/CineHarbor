"""Endpoint-bound local previews of original input bytes verified on the runtime."""
from pathlib import Path
import hashlib,json,mimetypes,re,shutil,uuid
from urllib.parse import urlsplit,parse_qs


def _root(cache,endpoint):
    return Path(cache)/'verified_input_previews'/hashlib.sha256(endpoint.encode()).hexdigest()


def publish(cache,endpoint,name,source,expected):
    if not re.fullmatch(r'cineharbor_[a-f0-9]{24}\.[a-z0-9]+',name):
        raise ValueError('Invalid verified media name')
    source=Path(source)
    if source.is_symlink() or not source.is_file():raise ValueError('Invalid verified source')
    with source.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=expected or not name.startswith('cineharbor_'+actual[:24]+'.'):
        raise ValueError('Verified preview checksum mismatch')
    root=_root(cache,endpoint);root.mkdir(parents=True,exist_ok=True)
    root.chmod(0o700)
    target=root/name
    part=root/(name+'.'+uuid.uuid4().hex+'.partial')
    shutil.copyfile(source,part);part.chmod(0o600);part.replace(target)
    meta=root/(name+'.json');temporary=meta.with_suffix('.tmp')
    temporary.write_text(json.dumps({'sha256':actual,'bytes':target.stat().st_size}))
    temporary.chmod(0o600);temporary.replace(meta)


def find(cache,endpoint,url):
    parsed=urlsplit(url);query=parse_qs(parsed.query,keep_blank_values=True)
    if parsed.path not in ('/view','/api/view') or query.get('type')!=['input'] or query.get('subfolder',[''])!=['']:
        return None
    name=query.get('filename',[''])[0]
    if not re.fullmatch(r'cineharbor_[a-f0-9]{24}\.[a-z0-9]+',name):return None
    root=_root(cache,endpoint);target=root/name;meta=root/(name+'.json')
    if target.is_symlink() or meta.is_symlink() or not target.is_file() or not meta.is_file():return None
    try:
        expected=json.loads(meta.read_text())
        if target.stat().st_size!=expected['bytes']:return None
        with target.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=expected['sha256'] or not name.startswith('cineharbor_'+actual[:24]+'.'):return None
    except (OSError,ValueError,KeyError):return None
    return target,mimetypes.guess_type(name)[0] or 'application/octet-stream'
