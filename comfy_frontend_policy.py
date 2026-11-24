"""Explicit, version-checked local frontend privacy modification.

The upstream localhost bundle embeds a Sentry DSN and enables error reporting
when it is nonempty. Disable that optional reporting without changing workflows,
media, or generation. The original archive and its GPL notices remain intact.
"""
import re

POLICY_REVISION = 'localhost-sentry-disabled-v1'
_RESOLVER = re.compile(r'function resolveRuntimeSentryDsn\(\)\{return`[^`]*`\}')


def apply_local_policy(name, payload):
    if not name.endswith('.js') or b'function resolveRuntimeSentryDsn()' not in payload:
        return payload, False
    text = payload.decode('utf-8')
    if len(_RESOLVER.findall(text)) != 1:
        raise ValueError('Unrecognized frontend Sentry configuration; review before serving.')
    return _RESOLVER.sub('function resolveRuntimeSentryDsn(){return``}', text).encode('utf-8'), True
