"""Build an arm64 standalone release with its Python, official Colab SDK & AVFoundation media tool included.
No credentials, model weights, user projects or machine configuration are bundled.
"""
from pathlib import Path
import json, plistlib, shutil, subprocess, sys

PRODUCT = json.loads((Path(__file__).resolve().parents[1] / 'assets/branding/product.json').read_text())
VERSION = PRODUCT['version']
BUILD_NUMBER = PRODUCT['build']
DISPLAY_NAME = PRODUCT['display_name']
root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(root / 'tools/localization/pack.py')], check=True)
(root / 'web/brand.js').write_text('// Generated from assets/branding/product.json.\nwindow.GCLabsBrand=Object.freeze(' + json.dumps(PRODUCT, ensure_ascii=False) + ');\n')
app = Path.home() / 'Applications' / (DISPLAY_NAME + '.app')
legacy_app = Path.home() / 'Applications/GC Labs.app'
commands = subprocess.check_output(['ps', '-axo', 'command='], text=True).splitlines()
if '--stage-only' not in sys.argv and any(line.strip().startswith(str(bundle / 'Contents/MacOS/JasperWorkstation')) or (line.strip().startswith(str(bundle / 'Contents/Resources/Python/bin/python3.13')) and '/backend/server.py' in line) for line in commands for bundle in (app, legacy_app)):
    raise RuntimeError(f'请先退出{DISPLAY_NAME}并完成当前后台任务，再替换应用包；未改动已安装版本。')

stage = Path('/tmp/gc-labs-build/GC Labs.app')
contents = stage / 'Contents'
resources = contents / 'Resources'
backend = resources / 'backend'
binary = contents / 'MacOS'

cli = Path.home() / '.local/bin/colab'
import os
# Preserve the venv executable path: resolving its symlink loses the CLI site-packages.
sdk_python = Path(os.environ.get('CINEHARBOR_SDK_PYTHON') or os.environ.get('GC_LABS_SDK_PYTHON') or cli.read_text().splitlines()[0][2:]).absolute()
info = json.loads(subprocess.check_output([str(sdk_python), '-B', '-c', 'import sys,sysconfig,json;print(json.dumps({"prefix":sys.base_prefix,"site":sysconfig.get_path("purelib")}))'], text=True))

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
    'server.py', 'console.py', 'comfy_local_bridge.py', 'comfy_frontend_policy.py', 'workspace_backup.py', 'license_resources.py',
    'comfy_project_store.py', 'comfy_project_bridge.py',
    'comfy_asset_transfer.py', 'comfy_verified_media.py',
    'account_login.py', 'workflow_library.py', 'workflow_converter.py', 'timeline_export.py',
    'model_presets.py', 'model_terms.py', 'mobile_monitor.py', 'gclabs_cli.py', 'drama_studio.py', 'storyboard_handoff.py'
]
for name in backend_modules:
    shutil.copy2(root / name, backend / name)

(backend / 'assets/branding').mkdir(parents=True)
shutil.copy2(root / 'assets/branding/product.json', backend / 'assets/branding/product.json')
shutil.copy2(root / 'assets/branding/native-locales.json', resources / 'NativeLocales.json')
shutil.copytree(root / 'assets/licenses', resources / 'Licenses')
shutil.copy2(root / 'macos/PrivacyInfo.xcprivacy', resources / 'PrivacyInfo.xcprivacy')
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
    '-framework', 'CoreText', '-framework', 'AppKit', '-framework', 'QuartzCore',
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

from sanitize_runtime import sanitize
sanitize(resources / 'Python', info['prefix'])

# Check the actual relocated runtime before signing or replacing the installed app.
subprocess.run([
    str(resources / 'Python/bin/python3.13'), '-B', '-c',
    'import colab_cli.cli, aiohttp; from colab_cli.runtime import ColabRuntime'
], check=True)

from license_inventory import collect as collect_python_licenses
license_inventory = collect_python_licenses(resources / 'Python', resources / 'Licenses')
if license_inventory['missing_notices']:
    raise RuntimeError('Missing dependency license notices: ' + ', '.join(license_inventory['missing_notices']))

(resources / 'THIRD_PARTY_NOTICES.txt').write_text(
    f'{DISPLAY_NAME} {VERSION}\n\nIncludes CPython (PSF license) and google-colab-cli (Apache-2.0), with their dependencies.\n'
    'See Licenses/python-components.json, Licenses/python/ and Licenses/CPython-LICENSE.txt for original notices.\n'
    'Google Colab is a Google service. This is an independent local-first client.\n'
    'Includes the separately licensed ComfyUI frontend 1.59.1 (GPL-3.0-only), commit cded88fdffbb78f191fc8e454e7f2cfa5016ee43.\n'
    'See Licenses/ComfyUI-frontend-GPL-3.0.txt and https://github.com/Comfy-Org/ComfyUI_frontend/tree/cded88fdffbb78f191fc8e454e7f2cfa5016ee43 for its version and corresponding source reference.\n\n'
    'html2text is separately licensed GPL-3.0-or-later; see its exact-version notice under Licenses/python/.\n'
    'Font and workflow-template licenses and source provenance are in Licenses/.\n\n'
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
        'CFBundleName': DISPLAY_NAME,
        'CFBundleDisplayName': DISPLAY_NAME,
        'CFBundlePackageType': 'APPL',
        'CFBundleDevelopmentRegion': 'en',
        'CFBundleLocalizations': PRODUCT.get('supported_locales', ['en']),
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': BUILD_NUMBER,
        'CFBundleIconFile': 'AppIcon',
        'LSMinimumSystemVersion': '13.0',
        'NSHighResolutionCapable': True,
        'NSLocalNetworkUsageDescription': '仅在你启用手机只读监看后，用于同一网络内查看制作进度。',
        'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
        'LSApplicationCategoryType': 'public.app-category.video',
        'NSHumanReadableCopyright': '© 2026 CineHarbor'
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
