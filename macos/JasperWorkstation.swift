import AppKit
import WebKit
import Foundation

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, WKScriptMessageHandler {
    var window: NSWindow!
    var web: WKWebView!
    var child: Process?
    var logHandle: FileHandle?
    var quitting = false
    var uiLocale = UserDefaults.standard.string(forKey: "CineHarbor.Locale") ?? "en"
    var nativeCatalogs: [String: [String: String]] = [:]
    func n(_ key: String) -> String { nativeCatalogs[uiLocale]?[key] ?? key }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "localeChanged", message.frameInfo.isMainFrame,
              let origin = message.frameInfo.request.url, origin.host == "127.0.0.1", origin.port == base.port,
              let locale = message.body as? String, ["en", "zh-Hans", "zh-Hant", "ja", "ko"].contains(locale) else { return }
        uiLocale = locale; UserDefaults.standard.set(locale, forKey: "CineHarbor.Locale")
        makeMenu(); window.subtitle = "by GachaFrame · \(n("Video workspace")) · \(appVersion)"
    }
    let appVersion = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0.0"
    let appName = Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String ?? "CineHarbor"
    var base = URL(string: "http://127.0.0.1:8766")!
    let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!.appendingPathComponent("Jasper Workstation", isDirectory: true)
    var config: [String: String] = [:]

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.appearance = NSAppearance(named: .darkAqua)
        if let url = Bundle.main.url(forResource: "LocalConfig", withExtension: "json"), let bytes = try? Data(contentsOf: url), let value = try? JSONSerialization.jsonObject(with: bytes) as? [String: String] { config = value }
        if let icon = Bundle.main.url(forResource: "AppIcon", withExtension: "icns") { NSApp.applicationIconImage = NSImage(contentsOf: icon) }
        if let url = Bundle.main.url(forResource: "NativeLocales", withExtension: "json"), let bytes = try? Data(contentsOf: url), let catalog = try? JSONDecoder().decode([String: [String: String]].self, from: bytes) { nativeCatalogs = catalog }
        makeMenu()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1400, height: 940), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = NSColor(srgbRed: 0.094, green: 0.086, blue: 0.106, alpha: 1.0)
        window.title = appName
        window.subtitle = "by GachaFrame · \(n("Video workspace")) · \(appVersion)"
        window.minSize = NSSize(width: 900, height: 620)
        window.center(); window.delegate = self
        let options = WKWebViewConfiguration()
        options.preferences.javaScriptCanOpenWindowsAutomatically = true
        options.userContentController.add(self, name: "localeChanged")
        web = WKWebView(frame: window.contentView!.bounds, configuration: options)
        web.autoresizingMask = [.width, .height]; web.navigationDelegate = self; web.uiDelegate = self
        window.contentView!.addSubview(web)
        window.makeKeyAndOrderFront(nil)
        web.loadHTMLString("<body style='background:#18161b;color:#f4f1ea;font:17px -apple-system;padding:64px'><h2>\(appName) · GachaFrame</h2><p style='color:#b6aebe'>\(n("Starting the local workspace. No cloud GPU is allocated."))</p></body>", baseURL: nil)
        syncPortFromDisk()
        health { good in
            if good { self.load("studio") }
            else { self.startBackend() }
        }
    }
    func makeMenu() {
        let main = NSMenu(); let root = NSMenuItem(); main.addItem(root); let app = NSMenu(); root.submenu = app
        app.addItem(withTitle: n("About") + " " + appName, action: #selector(about), keyEquivalent: "")
        app.addItem(NSMenuItem.separator())
        app.addItem(withTitle: n("Colab Control"), action: #selector(manager), keyEquivalent: "1")
        app.addItem(withTitle: n("Video Studio"), action: #selector(studio), keyEquivalent: "2")
        app.addItem(withTitle: n("Reload Interface"), action: #selector(reload), keyEquivalent: "r")
        app.addItem(withTitle: n("Open Workspace Folder"), action: #selector(openData), keyEquivalent: "")
        app.addItem(NSMenuItem.separator())
        app.addItem(withTitle: n("Quit") + " " + appName, action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        for item in app.items where item.action != #selector(NSApplication.terminate(_:)) { item.target = self }
        let editRoot = NSMenuItem(title: n("Edit"), action: nil, keyEquivalent: ""); let edit = NSMenu(title: n("Edit")); editRoot.submenu = edit; main.addItem(editRoot)
        for (title, selector, key) in [(n("Undo"), "undo:", "z"), (n("Cut"), "cut:", "x"), (n("Copy"), "copy:", "c"), (n("Paste"), "paste:", "v"), (n("Select All"), "selectAll:", "a")] { edit.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key) }
        NSApp.mainMenu = main
    }
    @objc func about() { web.evaluateJavaScript("aboutOpen=true;render()", completionHandler: nil) }
    @objc func manager() { load("manager") }
    @objc func studio() { load("studio") }
    @objc func reload() { web.reload() }
    @objc func openData() { NSWorkspace.shared.open(support) }
    func syncPortFromDisk() {
        let pf = support.appendingPathComponent("active_port.json")
        if let bytes = try? Data(contentsOf: pf),
           let obj = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any],
           let p = obj["port"] as? Int, p > 0,
           let u = URL(string: "http://127.0.0.1:\(p)") {
            base = u
        }
    }
    func load(_ page: String) { web.load(URLRequest(url: base.appendingPathComponent(page))) }
    func health(_ completion: @escaping (Bool) -> Void) {
        syncPortFromDisk()
        var req = URLRequest(url: base.appendingPathComponent("api/health")); req.timeoutInterval = 2
        URLSession.shared.dataTask(with: req) { bytes, _, _ in
            let obj = bytes.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            let workspace = (obj?["data"] as? String).map {
                URL(fileURLWithPath: $0).standardizedFileURL.resolvingSymlinksInPath().path
            }
            let expectedWorkspace = self.support.standardizedFileURL.resolvingSymlinksInPath().path
            DispatchQueue.main.async {
                completion(obj?["version"] as? String == self.appVersion && workspace == expectedWorkspace)
            }
        }.resume()
    }
    func startBackend() {
        let fm = FileManager.default
        guard let resources = Bundle.main.resourceURL else { return }
        let code = resources.appendingPathComponent("backend")
        let python = resources.appendingPathComponent("Python/bin/python3.13").path
        guard fm.isExecutableFile(atPath: python) else { failure(n("The Python runtime is missing. Check the installation. No GPU was allocated.")); return }
        do {
            try fm.createDirectory(at: support, withIntermediateDirectories: true)
            let portFile = support.appendingPathComponent("active_port.json")
            try? fm.removeItem(at: portFile)
            let log = support.appendingPathComponent("app-backend.log")
            if !fm.fileExists(atPath: log.path) { fm.createFile(atPath: log.path, contents: nil) }
            logHandle = try FileHandle(forWritingTo: log); try logHandle?.seekToEnd()
            let process = Process(); process.executableURL = URL(fileURLWithPath: python); process.arguments = [code.appendingPathComponent("server.py").path]; process.currentDirectoryURL = code
            var env = ProcessInfo.processInfo.environment
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["JASPER_WORKSTATION_ROOT"] = code.path; env["JASPER_WORKSTATION_DATA"] = support.path
            env["CINEHARBOR_DATA"] = support.path
            env["GC_LABS_DATA"] = support.path
            let cliEntry = code.appendingPathComponent("runtime/colab_entry.py").path
            env["CINEHARBOR_PYTHON"] = python
            env["GC_LABS_PYTHON"] = python
            env["CINEHARBOR_CLI_ENTRY"] = cliEntry
            env["GC_LABS_CLI_ENTRY"] = cliEntry
            env["CINEHARBOR_DYNAMIC_PORT"] = "1"
            env["GC_LABS_DYNAMIC_PORT"] = "1"
            env["CINEHARBOR_PORT_FILE"] = portFile.path
            env["GC_LABS_PORT_FILE"] = portFile.path
            if env["APP_SANDBOX_CONTAINER_ID"] != nil || (Bundle.main.object(forInfoDictionaryKey: "GCLabsSandboxed") as? Bool == true) {
                let sandboxCfg = support.appendingPathComponent("config")
                try? fm.createDirectory(at: sandboxCfg, withIntermediateDirectories: true)
                env["XDG_CONFIG_HOME"] = sandboxCfg.path
            }
            env["PATH"] = FileManager.default.homeDirectoryForCurrentUser.path + "/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            process.environment = env; process.standardOutput = logHandle; process.standardError = logHandle
            try process.run(); child = process
            waitReady(0)
        } catch { failure(error.localizedDescription) }
    }
    func waitReady(_ attempt: Int) {
        health { ready in
            if ready { self.load("studio") }
            else if attempt < 25 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { self.waitReady(attempt + 1) } }
            else { self.failure(self.n("The local service is not ready. Open the workspace folder and check app-backend.log. No cloud GPU was started.")) }
        }
    }
    func failure(_ message: String) { let a = NSAlert(); a.messageText = n("Workspace startup failed"); a.informativeText = message; a.runModal() }
    func windowShouldClose(_ sender: NSWindow) -> Bool { NSApp.terminate(nil); return false }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if quitting { return .terminateNow }
        let group = DispatchGroup(); let lock = NSLock(); var active = false; var unknown = false
        let hasLocalLease = FileManager.default.fileExists(atPath: support.appendingPathComponent("lease.json").path)
        let shutdownChecks = hasLocalLease ? ["api/status", "api/operations"] : ["api/operations"]
        for path in shutdownChecks {
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
                let a = NSAlert(); a.messageText = active ? self.n("Cloud sessions or tasks are still running") : self.n("Cloud status could not be confirmed")
                a.informativeText = self.n("Quitting does not release your Colab GPU. Background tasks remain active. To finish, return to Colab Control and use Back Up and Release.")
                a.addButton(withTitle: self.n("Return to Colab Control")); a.addButton(withTitle: self.n("Keep Session and Quit"))
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
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) { let a = NSAlert(); a.messageText = appName; a.informativeText = message; a.addButton(withTitle: n("Continue")); a.addButton(withTitle: n("Cancel")); completionHandler(a.runModal() == .alertFirstButtonReturn) }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) { let a = NSAlert(); a.messageText = message; a.runModal(); completionHandler() }
    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) { let a = NSAlert(); a.messageText = prompt; let field = NSTextField(string: defaultText ?? ""); field.frame = NSRect(x: 0, y: 0, width: 320, height: 24); a.accessoryView = field; a.addButton(withTitle: n("Create")); a.addButton(withTitle: n("Cancel")); completionHandler(a.runModal() == .alertFirstButtonReturn ? field.stringValue : nil) }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) { let p = NSOpenPanel(); p.allowsMultipleSelection = parameters.allowsMultipleSelection; p.canChooseDirectories = false; p.begin { completionHandler($0 == .OK ? p.urls : nil) } }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) { let p = NSSavePanel(); p.nameFieldStringValue = suggestedFilename; p.begin { completionHandler($0 == .OK ? p.url : nil) } }
}
let app = NSApplication.shared
let delegate = AppDelegate(); app.delegate = delegate; app.setActivationPolicy(.regular); app.run()
