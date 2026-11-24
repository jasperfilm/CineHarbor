"""Sign an already staged, credential-free bundle; never install or upload it."""
from pathlib import Path
import argparse, hashlib, json, os, plistlib, shutil, subprocess
from mas_release_config import load_config, app_entitlements, find_cert


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    config = load_config(os.environ)
    app, out = args.app.resolve(), args.out.resolve()
    if not app.name.endswith('.app') or not (app/'Contents/Info.plist').is_file():
        raise ValueError('An existing staged application is required.')
    if out.exists():
        raise ValueError('Output already exists; do not replace an existing candidate.')
    allowed = {hashlib.sha1(c).hexdigest().upper() for c in config.profile['DeveloperCertificates']}
    signer = find_cert(('Apple Distribution:', '3rd Party Mac Developer Application:'), allowed_hashes=allowed)
    installer = find_cert(('3rd Party Mac Developer Installer:',), os.environ.get('CINEHARBOR_MAS_PKG_CERT') or os.environ.get('GC_LABS_MAS_PKG_CERT'))
    contents = app/'Contents'
    info = plistlib.loads((contents/'Info.plist').read_bytes())
    if info['CFBundleIdentifier'] not in ('com.jasper.workstation', config.bundle_id):
        raise ValueError('Only the project-owned staged beta may become a store candidate.')
    info.update(CFBundleIdentifier=config.bundle_id, GCLabsSandboxed=True)
    info.pop('ITSAppUsesNonExemptEncryption', None)
    if config.uses_nonexempt_encryption is not None:
        info['ITSAppUsesNonExemptEncryption'] = config.uses_nonexempt_encryption
    (contents/'Info.plist').write_bytes(plistlib.dumps(info))
    shutil.copy2(config.profile_path, contents/'embedded.provisionprofile')
    base = {'com.apple.security.app-sandbox': True, 'com.apple.security.network.client': True,
            'com.apple.security.network.server': True, 'com.apple.security.files.user-selected.read-write': True}
    ent = app_entitlements(base, config)
    main_ent = app.parent/'candidate-app-entitlements.plist'
    child_ent = app.parent/'candidate-child-entitlements.plist'
    main_ent.write_bytes(plistlib.dumps(ent))
    child_ent.write_bytes(plistlib.dumps({'com.apple.security.app-sandbox': True, 'com.apple.security.inherit': True}))
    magic = (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe')
    binaries = []
    for path in app.rglob('*'):
        if path.is_symlink() or not path.is_file(): continue
        with path.open('rb') as stream: head = stream.read(4)
        if head in magic: binaries.append(path)
    main = contents/'MacOS'/info['CFBundleExecutable']
    for path in sorted(binaries, key=lambda p: len(p.parts), reverse=True):
        if path == main: continue
        command = ['codesign', '--force', '--sign', signer, '--timestamp']
        if path.suffix not in ('.dylib', '.so'): command += ['--entitlements', str(child_ent)]
        subprocess.run(command+[str(path)], check=True)
    subprocess.run(['codesign','--force','--sign',signer,'--timestamp','--entitlements',str(main_ent),str(app)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['productbuild','--component',str(app),'/Applications','--sign',installer,str(out)],check=True)
    subprocess.run(['pkgutil','--check-signature',str(out)],check=True)
    result={'version':info['CFBundleShortVersionString'],'build':info['CFBundleVersion'],
            'bundle_id':config.bundle_id,'mach_o_signed':len(binaries),'sandbox':True,
            'app_signature_verified':True,'package_signature_verified':True,
            'encryption_declaration':config.uses_nonexempt_encryption,
            'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size,
            'uploaded':False,'installed':False,'release_approved':False}
    out.with_suffix('.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__ == '__main__': main()
