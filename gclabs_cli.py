#!/usr/bin/env python3
"""Cross-platform launcher for CineHarbor (macOS / Linux / Windows).

Runs the loopback-only Core HTTP server and opens the local Studio/Manager UI in the default browser.
Existing workspace folders are unchanged: the Mac app data directory stays
~/Library/Application Support/Jasper Workstation.
"""
import argparse, os, platform, sys, threading, time, webbrowser
from pathlib import Path


def _env(*names):
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ''


def default_data_dir() -> Path:
    env = _env('CINEHARBOR_DATA', 'GC_LABS_DATA', 'JASPER_WORKSTATION_DATA')
    if env:
        return Path(env).expanduser()
    sys_name = platform.system()
    if sys_name == 'Darwin':
        return Path.home() / 'Library/Application Support/Jasper Workstation'
    if sys_name == 'Windows':
        appdata = os.environ.get('APPDATA') or str(Path.home() / 'AppData/Roaming')
        return Path(appdata) / 'GC Labs'
    xdg = os.environ.get('XDG_DATA_HOME') or str(Path.home() / '.local/share')
    return Path(xdg) / 'gc-labs'


def main():
    parser = argparse.ArgumentParser(description='CineHarbor — local-first video workspace for macOS, Linux, and Windows')
    parser.add_argument('--port', type=int, default=int(os.environ.get('JASPER_WORKSTATION_PORT', '8766')), help='Loopback port (default: 8766)')
    parser.add_argument('--data-dir', type=str, default='', help='Override local workspace directory')
    parser.add_argument('--page', choices=['manager', 'studio'], default='manager', help='Initial workbench tab to open')
    parser.add_argument('--no-browser', action='store_true', help='Do not open web browser automatically')
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    data = Path(args.data_dir).expanduser() if args.data_dir else default_data_dir()
    os.environ['JASPER_WORKSTATION_ROOT'] = str(root)
    os.environ['CINEHARBOR_DATA'] = str(data)
    os.environ['GC_LABS_DATA'] = str(data)
    os.environ['JASPER_WORKSTATION_PORT'] = str(args.port)
    sys.dont_write_bytecode = True

    import server
    from console import Console
    server.seed()
    server.migrate()
    server.CONSOLE = Console(server)

    url = f'http://127.0.0.1:{args.port}/{args.page}'
    print(f'CineHarbor {server.VERSION} ready at {url}')
    print(f'Workspace data: {data}')
    if not args.no_browser:
        threading.Thread(target=lambda: (time.sleep(0.5), webbrowser.open(url)), daemon=True).start()
    try:
        server.ThreadingHTTPServer(('127.0.0.1', args.port), server.Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nCineHarbor local server stopped (cloud GPU sessions, if any, remain untouched).')


if __name__ == '__main__':
    main()
