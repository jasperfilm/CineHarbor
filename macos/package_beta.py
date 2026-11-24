"""Package the already-built local beta. Does not publish or notarize."""
from pathlib import Path
import hashlib, json, plistlib, shutil, subprocess, sys

root = Path(__file__).resolve().parents[1]
product = json.loads((root / 'assets/branding/product.json').read_text())
name = product['display_name']
app = Path.home() / 'Applications' / (name + '.app')
with (app / 'Contents/Info.plist').open('rb') as f:
    version = plistlib.load(f)['CFBundleShortVersionString']
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)

stage = Path('/tmp') / ('gc-labs-dmg-' + version)
if stage.exists():
    shutil.rmtree(stage)
stage.mkdir()
shutil.copytree(app, stage / app.name, symlinks=True)
(stage / 'Applications').symlink_to('/Applications')
(stage / 'Beta README.txt').write_text(
    f'{name} {version} · Apple Silicon local workstation beta\n'
    'Drag the app to Applications or ~/Applications. This beta uses ad-hoc signing and is not notarized.\n'
    'No account credentials, model weights or personal projects are bundled.\n'
    'Create shots, preserve original media, edit locally and export MP4. Cloud features use your own Google Colab account.\n'
    'Project ZIP backups and ComfyUI Save & resume snapshots are separate. Drive copies require explicit authorization.\n'
    'Application data: ~/Library/Application Support/Jasper Workstation\n'
    'Quitting the app does not release a cloud runtime. Use Back Up and Release in Colab Control.\n'
)

release = root / 'releases'
release.mkdir(exist_ok=True)
file = release / f'{name}-{version}-arm64-beta.dmg'
subprocess.run(['hdiutil', 'create', '-volname', name + ' Beta', '-srcfolder', str(stage), '-ov', '-format', 'UDZO', str(file)], check=True)
subprocess.run(['hdiutil', 'verify', str(file)], check=True)
shutil.rmtree(stage)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cleanup_old_builds import prune
print(prune(root, keep=[app], installer=file))

report = {
    'file': file.name,
    'bytes': file.stat().st_size,
    'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
    'signing': 'ad-hoc; not notarized'
}
(release / (file.name + '.json')).write_text(json.dumps(report, indent=2))
print(json.dumps(report))
