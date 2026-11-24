"""Remove only identified GC Labs build products; never user data or model storage."""
from pathlib import Path
import plistlib,shutil,json
BUNDLE_ID='com.jasper.workstation'
def owned_app(path):
 try:
  with (path/'Contents/Info.plist').open('rb') as f:return plistlib.load(f).get('CFBundleIdentifier')==BUNDLE_ID
 except (OSError,plistlib.InvalidFileException):return False

def byte_size(path):
 if path.is_file():return path.stat().st_size
 return sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())

def prune(root,keep=(),installer=None):
 root=Path(root);kept={Path(p).resolve() for p in keep};removed=[]
 def delete(path):
  size=byte_size(path)
  if path.is_dir():shutil.rmtree(path)
  else:path.unlink()
  removed.append({'path':str(path),'bytes':size})
 candidates=[]
 for folder in [root/'build',root/'backups',Path.home()/'Applications',Path('/Applications')]:
  if not folder.exists():continue
  candidates.extend(folder.rglob('*.app') if folder in (root/'build',root/'backups') else folder.glob('*.app'))
 for app in sorted(candidates,key=lambda p:len(p.parts)):
  if app.exists() and app.resolve() not in kept and not app.is_symlink() and owned_app(app):delete(app)
 temps=[Path('/tmp/jasper-workstation-build'),Path('/tmp/gc-labs-build'),Path('/tmp/gc-labs-dmg'),*Path('/tmp').glob('gc-labs-dmg-*')]
 for folder in temps:
  if not folder.exists():continue
  apps=list(folder.glob('*.app'))
  if apps and all(owned_app(a) and a.resolve() not in kept for a in apps):delete(folder)
 if installer is not None:
  current=Path(installer).resolve()
  for folder in (root/'releases',root/'backups/releases'):
   if not folder.exists():continue
   for file in [*folder.glob('GC-Labs-*-arm64-beta.dmg'),*folder.glob('CineHarbor-*-arm64-beta.dmg')]:
    if file.resolve()!=current:
     delete(file);meta=file.with_suffix(file.suffix+'.json')
     if meta.exists():delete(meta)
 report={'removed':removed,'removed_bytes':sum(x['bytes'] for x in removed)}
 records=root/'reports';records.mkdir(exist_ok=True)
 path=records/'build-cleanup.json';previous=json.loads(path.read_text()) if path.exists() else {'runs':[]}
 previous['runs'].append(report);path.write_text(json.dumps(previous,ensure_ascii=False,indent=2))
 return report
