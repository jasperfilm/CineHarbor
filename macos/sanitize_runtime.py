"""Remove build-machine paths from the relocated CPython runtime."""
from pathlib import Path
import shutil
import subprocess

_PREFIX_MARKER = '__CINEHARBOR_PYTHON_PREFIX__'


def sanitize(python_root, original_prefix):
    """Keep the app's runtime relocatable and omit interpreter-install metadata."""
    python_root = Path(python_root)
    prefix = str(Path(original_prefix).resolve())
    for library in (python_root / 'lib').glob('libpython*.dylib'):
        if not library.is_symlink():
            subprocess.run(['install_name_tool', '-id', '@rpath/' + library.name, str(library)], check=True)

    for config in (python_root / 'lib').glob('python*/_sysconfigdata_*.py'):
        before = config.read_text()
        if prefix not in before:
            continue
        config.write_text(
            before.replace(prefix, _PREFIX_MARKER)
            + '\n# Resolve the original install prefix from the packaged interpreter.\n'
            + 'import sys as _sys\n'
            + 'build_time_vars = {\n'
            + f'    key: value.replace({_PREFIX_MARKER!r}, _sys.base_prefix)\n'
            + '    if isinstance(value, str) else value\n'
            + '    for key, value in build_time_vars.items()\n'
            + '}\n'
        )

    for site in (python_root / 'lib').glob('python*/site-packages'):
        for provenance in site.glob('*.dist-info/direct_url.json'):
            provenance.unlink()
        # The packaged bridge imports Tornado at runtime. Its test certificates are not used.
        tornado_tests = site / 'tornado/test'
        if tornado_tests.is_dir():
            shutil.rmtree(tornado_tests)
        for entry in (site / 'bin').glob('*'):
            if entry.is_symlink() or not entry.is_file():
                continue
            head, sep, tail = entry.read_bytes().partition(b'\n')
            executable = head[2:].split(maxsplit=1)
            if head.startswith(b'#!/') and executable and Path(executable[0].decode()).name.startswith('python'):
                entry.write_bytes(b'#!/usr/bin/env python3' + sep + tail)
