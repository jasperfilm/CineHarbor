"""Validate MAS inputs before staging files or using signing identities."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import plistlib
import re
import subprocess


@dataclass(frozen=True)
class MASConfig:
    bundle_id: str
    profile_path: Path
    uses_nonexempt_encryption: Optional[bool]
    profile: dict


def validate_profile(profile, bundle_id, now=None):
    ent = profile.get('Entitlements', {})
    identifier = ent.get('com.apple.application-identifier') or ent.get('application-identifier', '')
    teams = profile.get('TeamIdentifier', [])
    if len(teams) != 1 or identifier != teams[0] + '.' + bundle_id:
        raise ValueError('Profile does not match the explicit Bundle ID and team.')
    if not set(profile.get('Platform', [])) & {'OSX', 'macOS'}:
        raise ValueError('A macOS provisioning profile is required.')
    expires = profile.get('ExpirationDate')
    if not isinstance(expires, datetime):
        raise ValueError('Profile has no valid expiration date.')
    expires = expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires
    if expires <= (now or datetime.now(timezone.utc)):
        raise ValueError('Provisioning profile has expired.')
    if ('ProvisionedDevices' in profile or profile.get('ProvisionsAllDevices')
            or ent.get('get-task-allow') or ent.get('com.apple.security.get-task-allow')):
        raise ValueError('A Mac App Store distribution profile is required.')
    if not profile.get('DeveloperCertificates'):
        raise ValueError('Profile has no signing certificates.')
    return ent


def _first(env, *names):
    for name in names:
        value = env.get(name, '')
        if isinstance(value, str):
            value = value.strip()
        if value:
            return value
    return ''


def load_config(env, decode=None):
    bundle_id = _first(env, 'CINEHARBOR_BUNDLE_ID', 'GC_LABS_BUNDLE_ID')
    if not re.fullmatch(r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+', bundle_id):
        raise ValueError('Set CINEHARBOR_BUNDLE_ID explicitly to the existing App Store Connect Bundle ID. GC_LABS_BUNDLE_ID is still accepted.')
    declaration = _first(env, 'CINEHARBOR_NONEXEMPT_ENCRYPTION', 'GC_LABS_NONEXEMPT_ENCRYPTION').lower()
    if declaration not in ('true', 'false', 'defer'):
        raise ValueError('Set CINEHARBOR_NONEXEMPT_ENCRYPTION explicitly after the encryption assessment, or defer for a local candidate with no declaration; there is no default declaration. GC_LABS_NONEXEMPT_ENCRYPTION is still accepted.')
    path = Path(_first(env, 'CINEHARBOR_MAS_PROFILE', 'GC_LABS_MAS_PROFILE')).expanduser()
    if not path.is_file():
        raise ValueError('Set CINEHARBOR_MAS_PROFILE to an existing matching distribution profile. GC_LABS_MAS_PROFILE is still accepted.')
    if decode is None:
        decode = lambda p: plistlib.loads(subprocess.check_output(['security', 'cms', '-D', '-i', str(p)]))
    profile = decode(path)
    validate_profile(profile, bundle_id)
    return MASConfig(bundle_id, path, None if declaration == 'defer' else declaration == 'true', profile)


def app_entitlements(base, config):
    result = dict(base)
    profile_ent = validate_profile(config.profile, config.bundle_id)
    for key in ('com.apple.application-identifier', 'application-identifier', 'com.apple.developer.team-identifier'):
        if key in profile_ent:
            result[key] = profile_ent[key]
    if result.get('com.apple.security.app-sandbox') is not True:
        raise ValueError('The MAS app must keep its sandbox entitlement.')
    return result


def find_cert(prefixes, requested=None, allowed_hashes=None):
    out = subprocess.check_output(['security', 'find-identity', '-v'], text=True)
    for line in out.splitlines():
        match = re.search(r'\b([A-Fa-f0-9]{40})\s+"([^"]+)"', line)
        if not match or not any(match.group(2).startswith(prefix) for prefix in prefixes):
            continue
        if requested and requested not in (match.group(1), match.group(1).upper(), match.group(2)):
            continue
        if allowed_hashes is not None and match.group(1).upper() not in allowed_hashes:
            continue
        return match.group(1)
    raise RuntimeError('No available signing identity matches the requested certificate and profile.')
