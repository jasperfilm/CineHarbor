"""Build a Mac App Store (MAS) Sandboxed .pkg signed with Apple Distribution & 3rd Party Mac Developer Installer.
Auto-discovers installed MAS certificates from macOS Keychain without hardcoding personal identities in git.
"""
from pathlib import Path
import hashlib, json, os, plistlib, shutil, stat, subprocess, sys

from mas_release_config import load_config, app_entitlements, find_cert
CONFIG = load_config(os.environ)
BUNDLE_ID = CONFIG.bundle_id
PRODUCT = json.loads((Path(__file__).resolve().parents[1] / 'assets/branding/product.json').read_text())
VERSION = os.environ.get('CINEHARBOR_VERSION') or os.environ.get('GC_LABS_VERSION') or PRODUCT['version']
BUILD_NUMBER = os.environ.get('CINEHARBOR_BUILD') or os.environ.get('GC_LABS_BUILD') or PRODUCT['build']

root = Path(__file__).resolve().parents[1]


profile_certs = {hashlib.sha1(cert).hexdigest().upper() for cert in CONFIG.profile['DeveloperCertificates']}
app_cert = find_cert(('Apple Distribution:', '3rd Party Mac Developer Application:'), os.environ.get('CINEHARBOR_MAS_APP_CERT') or os.environ.get('GC_LABS_MAS_APP_CERT'), profile_certs)
pkg_cert = find_cert(('3rd Party Mac Developer Installer:',), os.environ.get('CINEHARBOR_MAS_PKG_CERT') or os.environ.get('GC_LABS_MAS_PKG_CERT'))

# First stage standard bundle via build_app.py --stage-only into /tmp/gc-labs-build/GC Labs.app
subprocess.run([sys.executable, '-B', str(root / 'macos/build_app.py'), '--stage-only'], check=True)
src_stage = Path('/tmp/gc-labs-build/GC Labs.app')

mas_root = Path('/tmp/gc-labs-mas-build')
if mas_root.exists():
    shutil.rmtree(mas_root)
mas_root.mkdir(parents=True)
mas_app = mas_root / (PRODUCT['display_name'] + '.app')
shutil.copytree(src_stage, mas_app, symlinks=True)

contents = mas_app / 'Contents'
resources = contents / 'Resources'
binary = contents / 'MacOS'

# Copy Apple Privacy Manifest
shutil.copy2(root / 'macos/PrivacyInfo.xcprivacy', resources / 'PrivacyInfo.xcprivacy')

# Profile validation is mandatory and happens before staging.
shutil.copy2(CONFIG.profile_path, contents / 'embedded.provisionprofile')

# Update Info.plist for Mac App Store compliance (LSApplicationCategoryType & ITSAppUsesNonExemptEncryption)
plist_file = contents / 'Info.plist'
with plist_file.open('rb') as f:
    info = plistlib.load(f)
info.update({
    'CFBundleIdentifier': BUNDLE_ID,
    'CFBundleShortVersionString': VERSION,
    'CFBundleVersion': BUILD_NUMBER,
    'LSApplicationCategoryType': 'public.app-category.video',
    'GCLabsSandboxed': True,
})
if CONFIG.uses_nonexempt_encryption is None:
    # A signed local candidate is not an export-compliance declaration.
    # Apple still requires the assessment before testing/distribution.
    info.pop('ITSAppUsesNonExemptEncryption', None)
else:
    info['ITSAppUsesNonExemptEncryption'] = CONFIG.uses_nonexempt_encryption
with plist_file.open('wb') as f:
    plistlib.dump(info, f)

# Strip extended attributes
for attr in ['com.apple.FinderInfo', 'com.apple.ResourceFork', 'com.apple.quarantine']:
    subprocess.run(['xattr', '-dr', attr, str(mas_app)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

child_ent = str(root / 'macos/entitlements-child-mas.plist')
app_ent = str(mas_root / 'app-entitlements.plist')
with (root / 'macos/entitlements-app-mas.plist').open('rb') as f:
    base_entitlements = plistlib.load(f)
with open(app_ent, 'wb') as f:
    plistlib.dump(app_entitlements(base_entitlements, CONFIG), f)

# Bottom-up signing: sign all Mach-O .dylib / .so libraries first, then child executables, then main bundle
libs = []
execs = []
for p in mas_app.rglob('*'):
    if p.is_symlink() or not p.is_file():
        continue
    if p.suffix in ('.dylib', '.so'):
        libs.append(p)
    elif (p.stat().st_mode & stat.S_IXUSR) and p.parent.name in ('bin', 'MacOS') and p.name != 'JasperWorkstation':
        # Check if Mach-O binary (skip shell/python text scripts)
        head = p.read_bytes()[:4]
        if head in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe'):
            execs.append(p)

for lib in sorted(libs, key=lambda x: len(x.parts), reverse=True):
    subprocess.run(['codesign', '--force', '--sign', app_cert, '--timestamp', str(lib)], check=True)

for exe in sorted(execs, key=lambda x: len(x.parts), reverse=True):
    subprocess.run(['codesign', '--force', '--sign', app_cert, '--timestamp', '--entitlements', child_ent, str(exe)], check=True)

subprocess.run(['codesign', '--force', '--sign', app_cert, '--timestamp', '--entitlements', app_ent, str(mas_app)], check=True)
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(mas_app)], check=True)

out_dir = root / 'releases'
out_dir.mkdir(exist_ok=True)
out_pkg = out_dir / f'{PRODUCT["display_name"]}-{VERSION}-MacAppStore.pkg'
if out_pkg.exists():
    out_pkg.unlink()

subprocess.run([
    'productbuild',
    '--component', str(mas_app), '/Applications',
    '--sign', pkg_cert,
    str(out_pkg)
], check=True)

shutil.rmtree(mas_root, ignore_errors=True)
shutil.rmtree(src_stage.parent, ignore_errors=True)
print(f'MAS Package ready: {out_pkg} ({out_pkg.stat().st_size} bytes)')
