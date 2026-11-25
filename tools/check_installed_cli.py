"""Smoke-test the installed entry points from outside the source checkout."""

import contextlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sysconfig
import tempfile
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


def check(launcher, directory):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    opener = build_opener(ProxyHandler({}))
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(
            [str(launcher), "--port", str(port), "--no-browser", "--data-dir", str(directory / launcher.name)],
            cwd=directory, stdout=log, stderr=log,
        )
        try:
            for _ in range(100):
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read().decode(errors="replace"))
                try:
                    with opener.open(origin + "/api/health", timeout=1) as response:
                        assert json.load(response)["version"] != "1.0.0"
                    break
                except URLError:
                    time.sleep(0.05)
            else:
                raise RuntimeError(f"{launcher.name} did not start")
            for path in (
                "/studio", "/style.css", "/api/camera-presets", "/api/bridge",
                "/templates/video_wan2_2_14B_i2v.json", "/licenses/models/MiniMax-H3-LICENSE.txt",
            ):
                with opener.open(origin + path, timeout=3) as response:
                    assert response.status == 200 and response.read(), path
        finally:
            with contextlib.suppress(ProcessLookupError):
                process.terminate()
            process.wait(timeout=5)
    print(f"{launcher.name}: installed workspace, API, templates, and license checks passed")


if __name__ == "__main__":
    scripts = Path(sysconfig.get_path("scripts"))
    suffix = ".exe" if os.name == "nt" else ""
    with tempfile.TemporaryDirectory() as location:
        for name in ("cineharbor", "gclabs"):
            check(scripts / (name + suffix), Path(location))
