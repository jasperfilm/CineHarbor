"""Read-only local MAS preflight. A passing binary scan is not App Review approval."""
from pathlib import Path
import argparse, datetime, email, hashlib, json, plistlib, subprocess, zipfile


def command(args):
    r = subprocess.run(args, capture_output=True)
    return r.returncode, (r.stdout + r.stderr).decode(errors='replace')


def inspect(app, repo):
    app, repo = Path(app), Path(repo)
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    ok, signing = command(['codesign', '-dv', '--verbose=4', str(app)])
    code, ent = command(['codesign', '-d', '--entitlements', ':-', str(app)])
    entitlements = {}
    if '<?xml' in ent:
        try:
            entitlements = plistlib.loads(ent[ent.index('<?xml'):].encode())
        except (ValueError, plistlib.InvalidFileException):
            pass
    verify, _ = command(['codesign', '--verify', '--deep', '--strict', str(app)])
    identity_code, identities = command(['security', 'find-identity', '-v'])
    cert = lambda text: identity_code == 0 and text in identities
    packages = []
    for meta in (app / 'Contents/Resources/Python').rglob('*.dist-info/METADATA'):
        data = email.message_from_bytes(meta.read_bytes())
        expression = data.get('License-Expression') or data.get('License') or ''
        license_files = [str(x.relative_to(meta.parent)) for x in meta.parent.rglob('*')
                         if x.is_file() and x.name.lower().startswith(('license', 'copying', 'notice'))]
        packages.append({'name': data.get('Name'), 'version': data.get('Version'),
                         'declared_license': expression[:400], 'license_files': license_files,
                         'review_status': 'inventory_only_not_redistribution_clearance'})
    frontend = repo / 'vendor/comfy_frontend.zip'
    with zipfile.ZipFile(frontend) as z:
        manifest = json.loads(z.read('build-manifest.json'))
    fields = ('CFBundleIdentifier', 'CFBundleShortVersionString', 'CFBundleVersion',
              'LSMinimumSystemVersion', 'CFBundleLocalizations')
    results = {
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': 'Local installed app, local keychain identity availability and bundled dependency inventory only. No account modification, credential export, signing or upload.',
        'installed': {k: info.get(k) for k in fields},
        'strict_signature_verifies': verify == 0,
        'ad_hoc_signature': 'Signature=adhoc' in signing,
        'sandbox_entitlement': entitlements.get('com.apple.security.app-sandbox') is True,
        'apple_distribution_identity_available': cert('Apple Distribution:') or cert('3rd Party Mac Developer Application:'),
        'mas_installer_identity_available': cert('3rd Party Mac Developer Installer:'),
        'keychain_query_succeeded': identity_code == 0,
        'embedded_provisioning_profile_present': (app / 'Contents/embedded.provisionprofile').is_file(),
        'frontend': {'manifest': manifest, 'sha256': hashlib.sha256(frontend.read_bytes()).hexdigest(),
                     'license': 'GPL-3.0-only; corresponding-source/distribution compatibility review pending'},
        'dependency_inventory': sorted(packages, key=lambda x: (x['name'] or '').lower()),
        'submission_ready': False,
        'nonbinary_reviews': ['Public privacy/support URLs', 'Actual SDK data-flow and privacy labels',
                             'ComfyUI frontend and all bundled redistribution rights',
                             'Reviewer cloud access without shared Google credentials',
                             'Final store Bundle ID/profile and sandboxed authorization persistence',
                             'Export encryption assessment', 'Age rating, territories and AI compliance declarations'],
    }
    results['local_binary_blockers'] = [name for name, condition in [
        ('Installed app uses ad-hoc signing', results['ad_hoc_signature']),
        ('Installed app is not sandbox-entitled', not results['sandbox_entitlement']),
        ('No available MAS app-signing identity in the current local keychain', not results['apple_distribution_identity_available']),
        ('No available MAS installer-signing identity in the current local keychain', not results['mas_installer_identity_available']),
        ('No embedded provisioning profile in the installed app', not results['embedded_provisioning_profile_present']),
    ] if condition]
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=Path.home() / 'Applications/CineHarbor.app')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.app, Path(__file__).resolve().parents[1])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('installed', 'strict_signature_verifies',
          'sandbox_entitlement', 'local_binary_blockers', 'submission_ready')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
