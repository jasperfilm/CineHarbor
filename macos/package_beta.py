"""Package the already-built local beta. Does not publish or notarize."""
from pathlib import Path
import hashlib, json, plistlib, shutil, subprocess, sys

root = Path(__file__).resolve().parents[1]
app = Path.home() / 'Applications/GC Labs.app'
with (app / 'Contents/Info.plist').open('rb') as f:
    version = plistlib.load(f)['CFBundleShortVersionString']
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)

stage = Path('/tmp') / ('gc-labs-dmg-' + version)
if stage.exists():
    shutil.rmtree(stage)
stage.mkdir()
shutil.copytree(app, stage / 'GC Labs.app', symlinks=True)
(stage / 'Applications').symlink_to('/Applications')
(stage / '内测说明.txt').write_text(
    f'GC Labs {version} · Apple Silicon 本地工作站版\n'
    '拖到 Applications（或 ~/Applications）安装。此版本采用本地 ad-hoc 签名。\n'
    '不包含任何账号凭证、模型权重或个人项目。\n'
    '支持 G4 算力管理、单次会话多镜头排队、实时采样步数与安全中断、官方画布一键转 API、固定 Commit 节点锁，\n'
    '以及本机 AVFoundation 帧接力、粗剪 MP4 合成、Final Cut FCPXML 与剪映草稿导出。\n'
    '数据目录保持兼容：~/Library/Application Support/Jasper Workstation\n'
    '退出 App 不等于关闭 GPU，请在管理台完成备份核验后关机。\n'
)
release = root / 'releases'
release.mkdir(exist_ok=True)
file = release / f'GC-Labs-{version}-arm64-beta.dmg'
subprocess.run(['hdiutil', 'create', '-volname', 'GC Labs Beta', '-srcfolder', str(stage), '-ov', '-format', 'UDZO', str(file)], check=True)
subprocess.run(['hdiutil', 'verify', str(file)], check=True)
shutil.rmtree(stage)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cleanup_old_builds import prune
print(prune(root, keep=[app], installer=file))

report = {
    'file': file.name,
    'bytes': file.stat().st_size,
    'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
    'signing': 'ad-hoc; not notarized'
}
(release / (file.name + '.json')).write_text(json.dumps(report, indent=2))
print(json.dumps(report))
