"""Build an arm64 standalone release with its Python, official Colab SDK & AVFoundation media tool included.
No credentials, model weights, user projects or machine configuration are bundled.
"""
from pathlib import Path
import json, plistlib, shutil, subprocess, sys

VERSION = '0.5.0'
BUILD_NUMBER = '10'
root = Path(__file__).resolve().parents[1]
app = Path.home() / 'Applications/GC Labs.app'
commands = subprocess.check_output(['ps', '-axo', 'command='], text=True).splitlines()
if any(line.strip().startswith(str(app / 'Contents/MacOS/JasperWorkstation')) or (line.strip().startswith(str(app / 'Contents/Resources/Python/bin/python3.13')) and '/backend/server.py' in line) for line in commands):
    raise RuntimeError('请先退出GC Labs并完成当前后台任务，再替换应用包；未改动已安装版本。')

stage = Path('/tmp/gc-labs-build/GC Labs.app')
contents = stage / 'Contents'
resources = contents / 'Resources'
backend = resources / 'backend'
binary = contents / 'MacOS'

cli = Path.home() / '.local/bin/colab'
sdk_python = Path(cli.read_text().splitlines()[0][2:]).resolve()
info = json.loads(subprocess.check_output([str(sdk_python), '-c', 'import sys,sysconfig,json;print(json.dumps({"prefix":sys.base_prefix,"site":sysconfig.get_path("purelib")}))'], text=True))

frontend_zip = root / 'vendor/comfy_frontend.zip'
if not frontend_zip.is_file():
    fallback = Path('/tmp/jasper_comfy_frontend.zip')
    if fallback.is_file():
        frontend_zip.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fallback, frontend_zip)
    else:
        raise RuntimeError('缺少 vendor/comfy_frontend.zip（官方 ComfyUI 前端归档）。')

if stage.exists():
    shutil.rmtree(stage)
binary.mkdir(parents=True)
backend.mkdir(parents=True)

backend_modules = [
    'server.py', 'console.py', 'comfy_local_bridge.py', 'workspace_backup.py',
    'account_login.py', 'workflow_library.py', 'workflow_converter.py', 'timeline_export.py',
    'model_presets.py', 'mobile_monitor.py', 'gclabs_cli.py'
]
for name in backend_modules:
    shutil.copy2(root / name, backend / name)

shutil.copytree(root / 'assets/workflow-templates', backend / 'assets/workflow-templates')
shutil.copytree(root / 'web', backend / 'web')
(backend / 'runtime').mkdir()
for name in ['control_gateway.py', 'managed_runtime.py', 'colab_entry.py', 'local_bridge.py', 'drive_auth.py']:
    shutil.copy2(root / 'runtime' / name, backend / 'runtime' / name)

(backend / 'vendor/bin').mkdir(parents=True)
shutil.copy2(frontend_zip, backend / 'vendor/comfy_frontend.zip')

# Compile native AVFoundation media helper into both dev vendor/bin and bundled backend/vendor/bin
dev_media_bin = root / 'vendor/bin/gclabs-media'
dev_media_bin.parent.mkdir(parents=True, exist_ok=True)
subprocess.run([
    'swiftc', '-parse-as-library', '-target', 'arm64-apple-macos13.0', '-O',
    '-framework', 'AVFoundation', '-framework', 'CoreMedia', '-framework', 'CoreGraphics',
    '-framework', 'ImageIO', '-framework', 'UniformTypeIdentifiers',
    str(root / 'macos/MediaTool.swift'), '-o', str(dev_media_bin)
], check=True)
shutil.copy2(dev_media_bin, backend / 'vendor/bin/gclabs-media')
shutil.copy2(dev_media_bin, binary / 'gclabs-media')

ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store')
shutil.copytree(info['prefix'], resources / 'Python', symlinks=True, ignore=ignore)
if not Path(info['site']).resolve().is_relative_to(Path(info['prefix']).resolve()):
    shutil.copytree(info['site'], resources / 'Python/lib/python3.13/site-packages', dirs_exist_ok=True, symlinks=True, ignore=ignore)
extra = root / 'vendor/python-extra'
if (extra / 'aiohttp').is_dir():
    shutil.copytree(extra, resources / 'Python/lib/python3.13/site-packages', dirs_exist_ok=True, ignore=ignore)
elif not (resources / 'Python/lib/python3.13/site-packages/aiohttp').is_dir():
    raise RuntimeError('先按 macos/requirements-local.lock 安装本地桥接依赖到 vendor/python-extra')

(resources / 'THIRD_PARTY_NOTICES.txt').write_text(
    f'GC Labs {VERSION}\n\nIncludes CPython (PSF license) and google-colab-cli (Apache-2.0), with their dependencies.\n'
    'Original licenses and package metadata are retained in Python/lib/python3.13/site-packages and Python/LICENSE*.\n'
    'Google Colab is a Google service. GC Labs is an independent local-first client.\n\n'
    + subprocess.check_output([
        str(resources / 'Python/bin/python3.13'), '-B', '-c',
        'import importlib.metadata as m; print("\\n".join(sorted(d.metadata["Name"]+"=="+d.version for d in m.distributions())))'
    ], text=True)
)
shutil.copy2(root / 'assets/branding/AppIcon.icns', resources / 'AppIcon.icns')
with (contents / 'Info.plist').open('wb') as f:
    plistlib.dump({
        'CFBundleExecutable': 'JasperWorkstation',
        'CFBundleIdentifier': 'com.jasper.workstation',
        'CFBundleName': 'GC Labs',
        'CFBundleDisplayName': 'GC Labs',
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': BUILD_NUMBER,
        'CFBundleIconFile': 'AppIcon',
        'LSMinimumSystemVersion': '13.0',
        'NSHighResolutionCapable': True,
        'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
        'NSHumanReadableCopyright': f'GC Labs · {VERSION}'
    }, f)

subprocess.run([
    'swiftc', '-target', 'arm64-apple-macos13.0', '-O',
    '-framework', 'AppKit', '-framework', 'WebKit',
    str(root / 'macos/JasperWorkstation.swift'), '-o', str(binary / 'JasperWorkstation')
], check=True)

for attr in ['com.apple.FinderInfo', 'com.apple.ResourceFork']:
    subprocess.run(['xattr', '-dr', attr, str(stage)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(stage)], check=True)

if '--stage-only' in sys.argv:
    print(stage)
    raise SystemExit(0)

app.parent.mkdir(exist_ok=True)
incoming = app.with_name('.GC Labs.incoming.app')
previous = app.with_name('.GC Labs.replacing.app')
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cleanup_old_builds import prune

if incoming.exists():
    shutil.rmtree(incoming)
shutil.copytree(stage, incoming, symlinks=True)
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(incoming)], check=True)
if previous.exists():
    shutil.rmtree(previous)
if app.exists():
    app.rename(previous)
try:
    incoming.rename(app)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
except Exception:
    if app.exists():
        shutil.rmtree(app)
    if previous.exists():
        previous.rename(app)
    raise
if previous.exists():
    shutil.rmtree(previous)

app.touch()
subprocess.run(['/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister', '-f', str(app)], check=True)
shutil.rmtree(stage.parent)
print(prune(root, keep=[app]))
print(app)
