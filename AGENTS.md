# CineHarbor project rules

- 每次迭代只保留一份当前安装的 CineHarbor.app 和一个最新版 DMG；新版构建、签名验证成功后删除旧版 App/旧安装包，不把完整应用包留在 backups。
- 打包临时目录在成功后清理。--stage-only 属于显式调试例外；下一次正常安装或打包应清理这些副本。
- 仅清理已核实 bundle ID 为 com.jasper.workstation 的构建产物，以及本项目明确命名的 CineHarbor 与旧 GC-Labs 安装包。不得清理其他项目或其他软件。
- Application Support 内的项目、素材、版本、账号配置，以及模型和云盘备份不得随 App 清理。Mac 应用数据目录仍是 ~/Library/Application Support/Jasper Workstation。
- 替换运行中的 App 前先退出；新包必须先验证，替换失败应恢复旧包。源码与文本验收记录保留。
