"""Smoke-test the installed entry points from outside the source checkout."""

import contextlib
import json
import locale
import os
from pathlib import Path
import re
import socket
import subprocess
import sysconfig
import tempfile
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener


def check(launcher, directory):
    data_dir = directory / (launcher.name + "-工作台")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    opener = build_opener(ProxyHandler({}))
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(
            [str(launcher), "--port", str(port), "--no-browser", "--data-dir", str(data_dir)],
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
            with opener.open(origin + "/studio", timeout=3) as response:
                html = response.read().decode("utf-8")
            key = re.search(r"window\.LOCAL_KEY='([^']+)'", html).group(1)
            for path in (
                "/style.css", "/api/camera-presets", "/api/bridge",
                "/templates/video_wan2_2_14B_i2v.json", "/licenses/models/MiniMax-H3-LICENSE.txt",
            ):
                with opener.open(origin + path, timeout=3) as response:
                    assert response.status == 200 and response.read(), path

            for name in ("中文镜头 🎬", "カット 두 번째"):
                request = Request(
                    origin + "/api/project/new", data=json.dumps({"name": name}).encode(),
                    headers={"X-Local-Key": key, "Content-Type": "application/json"},
                )
                with opener.open(request, timeout=3) as response:
                    assert json.load(response)["ok"]
            with opener.open(origin + "/api/projects", timeout=3) as response:
                projects = {project["name"]: project["id"] for project in json.load(response)}
            if os.name == "nt" and locale.getencoding().lower() == "cp1252":
                legacy = {"project": {"id": "legacy", "name": "Café"}}
                (data_dir / "projects" / "legacy.json").write_text(
                    json.dumps(legacy, ensure_ascii=False), encoding="cp1252",
                )
                with opener.open(origin + "/api/projects", timeout=3) as response:
                    assert any(row["name"] == "Café" for row in json.load(response))
                print(f"{launcher.name}: legacy Windows project encoding remains readable")
            request = Request(
                origin + "/api/project/select", data=json.dumps({"id": projects["中文镜头 🎬"]}).encode(),
                headers={"X-Local-Key": key, "Content-Type": "application/json"},
            )
            with opener.open(request, timeout=3) as response:
                assert json.load(response)["ok"]
            with opener.open(origin + "/api/workspace", timeout=3) as response:
                assert json.load(response)["project"]["name"] == "中文镜头 🎬"
            assert json.loads((data_dir / "workspace.json").read_text(encoding="utf-8"))["project"]["name"] == "中文镜头 🎬"
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    # A pip-generated launcher starts a separate Python process on Windows.
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10)
                else:
                    with contextlib.suppress(ProcessLookupError):
                        process.terminate()
            process.wait(timeout=5)
    print(f"{launcher.name}: installed workspace, Unicode project switching, API, templates, and license checks passed")


if __name__ == "__main__":
    scripts = Path(sysconfig.get_path("scripts"))
    suffix = ".exe" if os.name == "nt" else ""
    with tempfile.TemporaryDirectory() as location:
        for name in ("cineharbor", "gclabs"):
            check(scripts / (name + suffix), Path(location))
