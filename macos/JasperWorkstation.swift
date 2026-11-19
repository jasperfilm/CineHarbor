import AppKit
import WebKit
import Foundation

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var child: Process?
    var logHandle: FileHandle?
    var quitting = false
    let appVersion = "0.5.0"
    let base = URL(string: "http://127.0.0.1:8766")!
    let support = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Jasper Workstation")
    var config: [String: String] = [:]

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let url = Bundle.main.url(forResource: "LocalConfig", withExtension: "json"), let bytes = try? Data(contentsOf: url), let value = try? JSONSerialization.jsonObject(with: bytes) as? [String: String] { config = value }
        if let icon = Bundle.main.url(forResource: "AppIcon", withExtension: "icns") { NSApp.applicationIconImage = NSImage(contentsOf: icon) }
        makeMenu()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1380, height: 930), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "GC Labs"
        window.subtitle = "Colab 管理与视频制作 · \(appVersion)"
        window.minSize = NSSize(width: 900, height: 620)
        window.center(); window.delegate = self
        let options = WKWebViewConfiguration()
        options.preferences.javaScriptCanOpenWindowsAutomatically = true
        web = WKWebView(frame: window.contentView!.bounds, configuration: options)
        web.autoresizingMask = [.width, .height]; web.navigationDelegate = self; web.uiDelegate = self
        window.contentView!.addSubview(web)
        window.makeKeyAndOrderFront(nil)
        web.loadHTMLString("<body style='background:#101114;color:#eee;font:18px -apple-system;padding:60px'><h2>GC Labs</h2><p>正在检查本机服务…</p></body>", baseURL: nil)
        health { good in
            if good { self.load("manager") }
            else { self.startBackend() }
        }
    }
    func makeMenu() {
        let main = NSMenu(); let root = NSMenuItem(); main.addItem(root); let app = NSMenu(); root.submenu = app
        app.addItem(withTitle: "关于 GC Labs", action: #selector(about), keyEquivalent: "")
        app.addItem(NSMenuItem.separator())
        app.addItem(withTitle: "Colab 管理", action: #selector(manager), keyEquivalent: "1")
        app.addItem(withTitle: "视频制作", action: #selector(studio), keyEquivalent: "2")
        app.addItem(withTitle: "重新加载界面", action: #selector(reload), keyEquivalent: "r")
        app.addItem(withTitle: "打开工作区文件夹", action: #selector(openData), keyEquivalent: "")
        app.addItem(NSMenuItem.separator())
        app.addItem(withTitle: "退出 GC Labs", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        for item in app.items where item.action != #selector(NSApplication.terminate(_:)) { item.target = self }
        let editRoot = NSMenuItem(title: "编辑", action: nil, keyEquivalent: ""); let edit = NSMenu(title: "编辑"); editRoot.submenu = edit; main.addItem(editRoot)
        for (title, selector, key) in [("撤销", "undo:", "z"), ("剪切", "cut:", "x"), ("拷贝", "copy:", "c"), ("粘贴", "paste:", "v"), ("全选", "selectAll:", "a")] { edit.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key) }
        NSApp.mainMenu = main
    }
    @objc func about() { let a = NSAlert(); a.messageText = "GC Labs \(appVersion)"; a.informativeText = "本地优先 Mac 工作站。项目与素材保存在 Mac，GPU 在 Colab G4 按任务运行。内置 Python、官方 Colab CLI 与 AVFoundation 媒体合成引擎。账号凭证与项目数据独立保存在本机用户目录。"; a.runModal() }
    @objc func manager() { load("manager") }
    @objc func studio() { load("studio") }
    @objc func reload() { web.reload() }
    @objc func openData() { NSWorkspace.shared.open(support) }
    func load(_ page: String) { web.load(URLRequest(url: base.appendingPathComponent(page))) }
    func health(_ completion: @escaping (Bool) -> Void) {
        var req = URLRequest(url: base.appendingPathComponent("api/health")); req.timeoutInterval = 2
        URLSession.shared.dataTask(with: req) { bytes, _, _ in
            let obj = bytes.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async { completion(obj?["version"] as? String == self.appVersion) }
        }.resume()
    }
    func startBackend() {
        let fm = FileManager.default
        guard let resources = Bundle.main.resourceURL else { return }
        let code = resources.appendingPathComponent("backend")
        let python = resources.appendingPathComponent("Python/bin/python3.13").path
        guard fm.isExecutableFile(atPath: python) else { failure("Python 运行环境不存在。请检查安装依赖；不会自动申请GPU。"); return }
        do {
            try fm.createDirectory(at: support, withIntermediateDirectories: true)
            let log = support.appendingPathComponent("app-backend.log")
            if !fm.fileExists(atPath: log.path) { fm.createFile(atPath: log.path, contents: nil) }
            logHandle = try FileHandle(forWritingTo: log); try logHandle?.seekToEnd()
            let process = Process(); process.executableURL = URL(fileURLWithPath: python); process.arguments = [code.appendingPathComponent("server.py").path]; process.currentDirectoryURL = code
            var env = ProcessInfo.processInfo.environment
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["JASPER_WORKSTATION_ROOT"] = code.path; env["JASPER_WORKSTATION_DATA"] = support.path
            env["GC_LABS_PYTHON"] = python
            env["GC_LABS_CLI_ENTRY"] = code.appendingPathComponent("runtime/colab_entry.py").path
            env["PATH"] = FileManager.default.homeDirectoryForCurrentUser.path + "/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            process.environment = env; process.standardOutput = logHandle; process.standardError = logHandle
            try process.run(); child = process
            waitReady(0)
        } catch { failure(error.localizedDescription) }
    }
    func waitReady(_ attempt: Int) {
        health { ready in
            if ready { self.load("manager") }
            else if attempt < 25 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { self.waitReady(attempt + 1) } }
            else { self.failure("本机服务未就绪。请从菜单打开工作区，查看 app-backend.log。没有启动云端GPU。") }
        }
    }
    func failure(_ message: String) { let a = NSAlert(); a.messageText = "工作站启动失败"; a.informativeText = message; a.runModal() }
    func windowShouldClose(_ sender: NSWindow) -> Bool { NSApp.terminate(nil); return false }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if quitting { return .terminateNow }
        let group = DispatchGroup(); let lock = NSLock(); var active = false; var unknown = false
        for path in ["api/status", "api/operations"] {
            group.enter(); var req = URLRequest(url: base.appendingPathComponent(path)); req.timeoutInterval = 10
            URLSession.shared.dataTask(with: req) { bytes, _, error in
                lock.lock(); defer { lock.unlock(); group.leave() }
                guard error == nil, let bytes = bytes, let obj = try? JSONSerialization.jsonObject(with: bytes) else { unknown = true; return }
                if let status = obj as? [String: Any] { if let error = status["error"], !(error is NSNull) { unknown = true }; if (status["active"] as? Double ?? 0) > 0 { active = true } }
                if let ops = obj as? [[String: Any]], ops.contains(where: { ["queued", "running"].contains($0["state"] as? String ?? "") }) { active = true }
            }.resume()
        }
        group.notify(queue: .main) {
            if active || unknown {
                let a = NSAlert(); a.messageText = active ? "云端会话或任务仍在运行" : "暂时无法确认云端状态"
                a.informativeText = "退出App不会释放Colab GPU。后台任务会保留；结束工作请返回管理台，使用“备份核验后关机”。"
                a.addButton(withTitle: "返回管理台"); a.addButton(withTitle: "保留会话并退出")
                if a.runModal() == .alertFirstButtonReturn { self.manager(); sender.reply(toApplicationShouldTerminate: false); return }
            } else { self.child?.terminate() }
            self.quitting = true; sender.reply(toApplicationShouldTerminate: true)
        }
        return .terminateLater
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if action.shouldPerformDownload { decisionHandler(.download); return }
        if url.scheme == "about" || url.host == "127.0.0.1" || url.host == "localhost" { decisionHandler(.allow) }
        else if ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url); decisionHandler(.cancel) }
        else { decisionHandler(.cancel) }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? { if let url = action.request.url { NSWorkspace.shared.open(url) }; return nil }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) { let a = NSAlert(); a.messageText = "GC Labs"; a.informativeText = message; a.addButton(withTitle: "继续"); a.addButton(withTitle: "取消"); completionHandler(a.runModal() == .alertFirstButtonReturn) }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) { let a = NSAlert(); a.messageText = message; a.runModal(); completionHandler() }
    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) { let a = NSAlert(); a.messageText = prompt; let field = NSTextField(string: defaultText ?? ""); field.frame = NSRect(x: 0, y: 0, width: 320, height: 24); a.accessoryView = field; a.addButton(withTitle: "创建"); a.addButton(withTitle: "取消"); completionHandler(a.runModal() == .alertFirstButtonReturn ? field.stringValue : nil) }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) { let p = NSOpenPanel(); p.allowsMultipleSelection = parameters.allowsMultipleSelection; p.canChooseDirectories = false; p.begin { completionHandler($0 == .OK ? p.urls : nil) } }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) { let p = NSSavePanel(); p.nameFieldStringValue = suggestedFilename; p.begin { completionHandler($0 == .OK ? p.url : nil) } }
}
let app = NSApplication.shared
let delegate = AppDelegate(); app.delegate = delegate; app.setActivationPolicy(.regular); app.run()
