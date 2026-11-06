import Cocoa


final class FolderSelection: NSObject {
    private var folders: [URL] = []
    private let alert = NSAlert()
    private let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 520, height: 250))

    private var adding = false

    func choose(adding: Bool = false, creating: Bool = false) -> [String]? {
        self.adding = adding
        alert.messageText = "처음 사용할 폴더를 설정해요"
        alert.informativeText = (creating ? "선택창의 ‘새로운 폴더’로 폴더를 만든 뒤 그 폴더를 선택하세요. 지침 준비 후 웹에서 이 폴더를 골라 파일의 답변을 보내세요.\n" : "") + (adding ? "기존 폴더와 지침은 유지됩니다. 새로 추가할 폴더를 선택하세요.\n" : "") + "‘폴더 추가’로 여러 위치의 폴더를 차례로 담으세요. 모두 고른 뒤 완료하면 QWEN이 폴더별 정리 지침을 만듭니다. 최대 20개까지 추가할 수 있어요."
        if creating { alert.informativeText = "‘폴더 추가’를 누르고 Mac 선택창의 ‘새로운 폴더’로 폴더를 만드세요. 이 파일을 분류할 폴더 하나를 선택하면 QWEN이 지침을 만듭니다. 준비 후 웹에서 새 폴더를 골라 답변을 보내세요. 기존 폴더는 유지됩니다." }
        alert.addButton(withTitle: "선택 완료 · 지침 만들기")
        alert.addButton(withTitle: "폴더 추가")
        alert.addButton(withTitle: "취소")
        scroll.hasVerticalScroller = true
        scroll.borderType = .bezelBorder
        alert.accessoryView = scroll
        while true {
            render()
            let response = alert.runModal()
            if response == .alertFirstButtonReturn && !folders.isEmpty {
                return folders.map { $0.path }
            }
            guard response == .alertSecondButtonReturn else { return nil }
            let picker = NSOpenPanel()
            picker.title = "모아가 접근할 폴더 추가"
            picker.message = "여러 폴더를 함께 선택하거나, 한 개씩 추가할 수 있어요. 다른 위치의 폴더도 계속 추가할 수 있습니다."
            picker.prompt = "목록에 추가"
            picker.canChooseFiles = false
            picker.canChooseDirectories = true
            picker.allowsMultipleSelection = !creating
            picker.canCreateDirectories = true
            guard picker.runModal() == .OK else { continue }
            var next = folders
            var problem: String?
            for url in picker.urls {
                let folder = url.resolvingSymlinksInPath().standardizedFileURL
                if next.contains(folder) { continue }
                let parts = folder.pathComponents
                if next.contains(where: { existing in
                    let other = existing.pathComponents
                    return parts.starts(with: other) || other.starts(with: parts)
                }) {
                    problem = "상위 폴더와 그 안의 하위 폴더는 함께 추가할 수 없어요. 필요한 범위의 폴더 하나를 골라 주세요."
                    break
                }
                next.append(folder)
                if creating && next.count > 1 {
                    problem = "이 파일을 분류할 새 폴더 하나만 선택해 주세요."
                    break
                }
                if next.count > 20 {
                    problem = "폴더는 최대 20개까지 추가할 수 있어요. 목록에서 폴더를 뺀 뒤 다시 추가해 주세요."
                    break
                }
            }
            if let problem = problem {
                let notice = NSAlert()
                notice.messageText = "폴더 목록을 확인해 주세요"
                notice.informativeText = problem
                notice.addButton(withTitle: "확인")
                notice.runModal()
            } else {
                folders = next
            }
        }
    }

    private func render() {
        alert.buttons[0].isEnabled = !folders.isEmpty
        alert.messageText = "\(adding ? "추가할 폴더" : "처음 사용할 폴더") · \(folders.count)개 선택"
        let height = max(250, folders.count * 62)
        let content = NSView(frame: NSRect(x: 0, y: 0, width: 500, height: height))
        if folders.isEmpty {
            let empty = NSTextField(wrappingLabelWithString: "아직 선택한 폴더가 없어요.\n아래 ‘폴더 추가’ 버튼을 눌러 시작하세요.")
            empty.frame = NSRect(x: 16, y: height - 80, width: 460, height: 56)
            content.addSubview(empty)
        }
        for (index, folder) in folders.enumerated() {
            let y = height - (index + 1) * 62
            let name = NSTextField(labelWithString: folder.lastPathComponent)
            name.font = .boldSystemFont(ofSize: 13)
            name.frame = NSRect(x: 12, y: y + 32, width: 390, height: 20)
            content.addSubview(name)
            let path = NSTextField(labelWithString: (folder.path as NSString).abbreviatingWithTildeInPath)
            path.font = .systemFont(ofSize: 11)
            path.textColor = .secondaryLabelColor
            path.lineBreakMode = .byTruncatingMiddle
            path.toolTip = folder.path
            path.frame = NSRect(x: 12, y: y + 10, width: 390, height: 18)
            content.addSubview(path)
            let remove = NSButton(title: "빼기", target: self, action: #selector(removeFolder(_:)))
            remove.tag = index
            remove.frame = NSRect(x: 414, y: y + 18, width: 70, height: 28)
            content.addSubview(remove)
        }
        scroll.documentView = content
        content.scroll(NSPoint(x: 0, y: max(0, height - 250)))
    }

    @objc private func removeFolder(_ sender: NSButton) {
        guard folders.indices.contains(sender.tag) else { return }
        folders.remove(at: sender.tag)
        render()
    }
}

final class HelperApp: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var message: NSTextField!
    var installing = false
    var folderManagementRequested = false
    var createFolderRequested = false
    var ticket: String?
    var process: Process?
    let origin = Bundle.main.object(forInfoDictionaryKey: "MoaOrigin") as? String ?? "https://moa.3-38-192-19.sslip.io"

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu(); let item = NSMenuItem(); let submenu = NSMenu()
        let foldersItem = submenu.addItem(withTitle: "폴더 추가…", action: #selector(openFolderManagement), keyEquivalent: "o")
        foldersItem.target = self
        submenu.addItem(withTitle: "모아 연결 종료", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.submenu = submenu; menu.addItem(item); NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 460, height: 190), styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = "모아 Mac 연결"
        let title = NSTextField(labelWithString: "Mac 연결 프로그램을 준비하고 있어요")
        title.font = .boldSystemFont(ofSize: 19); title.frame = NSRect(x: 28, y: 126, width: 410, height: 28)
        message = NSTextField(wrappingLabelWithString: "처음에는 필요한 프로그램을 자동으로 내려받습니다.\n준비가 끝나면 모아 연결 화면이 열려요.")
        message.frame = NSRect(x: 28, y: 62, width: 405, height: 54)
        let spinner = NSProgressIndicator(frame: NSRect(x: 28, y: 23, width: 24, height: 24))
        spinner.style = .spinning; spinner.startAnimation(nil)
        window.contentView?.addSubview(title); window.contentView?.addSubview(message); window.contentView?.addSubview(spinner)
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        start()
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        guard let url = urls.first, url.scheme == "moa-helper" else { return }
        if url.host == "folders", url.fragment == nil, url.path.isEmpty,
           url.query == nil || url.query == "create=1" {
            folderManagementRequested = true
            createFolderRequested = url.query == "create=1"
            if window != nil && !installing { start() }
            return
        }
        guard url.host == "connect",
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.queryItems?.count == 1,
              let value = components.queryItems?.first, value.name == "ticket", let secret = value.value,
              secret.range(of: "^[A-Za-z0-9_-]{32,128}$", options: .regularExpression) != nil else { return }
        ticket = secret
        if window != nil && !installing { start() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window?.makeKeyAndOrderFront(nil)
        if !installing { start() }
        return true
    }

    func start() {
        guard !installing else { return }; installing = true
        guard let resources = Bundle.main.resourceURL,
              let hash = Bundle.main.object(forInfoDictionaryKey: "MoaSourceSHA256") as? String else { return }
        let data = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Moa")
        do {
            try FileManager.default.createDirectory(at: data, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let logURL = data.appendingPathComponent("installer.log")
            if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil, attributes: [.posixPermissions: 0o600]) }
            let log = try FileHandle(forWritingTo: logURL); log.seekToEndOfFile()
            let job = Process(); process = job; job.executableURL = URL(fileURLWithPath: "/bin/zsh")
            job.arguments = [resources.appendingPathComponent("install-helper.sh").path, resources.appendingPathComponent("source.tar.gz").path, hash, Bundle.main.bundleURL.path, origin]
            job.standardOutput = log; job.standardError = log
            job.terminationHandler = { child in
                try? log.close()
                DispatchQueue.main.async {
                    self.installing = false
                    if child.terminationStatus == 0 { self.finish() }
                    else {
                        self.message.stringValue = "설치를 완료하지 못했어요. 인터넷 연결을 확인하고 다시 열어 주세요."
                        let alert = NSAlert(); alert.messageText = "Mac 연결 준비 실패"; alert.informativeText = "설치 로그에서 원인을 확인할 수 있습니다."
                        alert.addButton(withTitle: "닫기"); alert.addButton(withTitle: "설치 로그 열기")
                        if alert.runModal() == .alertSecondButtonReturn { NSWorkspace.shared.open(logURL) }
                    }
                }
            }
            try job.run()
        } catch { installing = false; message.stringValue = "연결 프로그램을 실행하지 못했어요. 앱을 다시 열어 주세요." }
    }

    @objc func openFolderManagement() {
        guard !installing else { return }
        folderManagementRequested = true
        start()
    }

    func finish() {
        let data = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Moa")
        if ticket == nil && (folderManagementRequested || FileManager.default.fileExists(atPath: data.appendingPathComponent("icloud.json").path)) {
            folderManagementRequested = false
            manageFolders()
            return
        }
        guard let secret = ticket else {
            message.stringValue = "준비가 끝났어요. 모아 웹앱에서 ‘설치한 앱으로 Mac 연결하기’를 눌러 주세요."
            return
        }
        ticket = nil
        installing = true
        let alert = NSAlert()
        alert.messageText = "이 Mac을 모아에 연결할까요?"
        alert.informativeText = "연결 주소: \(origin)\n다음 화면에서 모아가 사용할 폴더를 선택합니다. 선택한 폴더의 파일 이름을 QWEN이 Mac에서 살펴보고 정리 지침(_project.md)을 만듭니다. 기존 지침은 보존합니다. 이어서 다운로드와 스크린샷 저장 폴더의 문서·이미지를 작업 사본으로 일괄 분류합니다. 원본은 유지하며, 기타 파일의 새 분류안은 웹에서 확인한 뒤 적용합니다. 파일 분류 상태는 모아 계정에 표시됩니다."
        alert.addButton(withTitle: "폴더 선택하기")
        alert.addButton(withTitle: "취소")
        guard alert.runModal() == .alertFirstButtonReturn else {
            installing = false
            message.stringValue = "연결을 취소했어요. 모아 웹앱에서 다시 시도할 수 있습니다."
            return
        }
        guard let folders = FolderSelection().choose() else {
            installing = false
            message.stringValue = "폴더 선택을 취소했어요. 모아 웹앱에서 다시 연결할 수 있습니다."
            return
        }
        message.stringValue = "선택한 \(folders.count)개 폴더의 QWEN 지침을 준비하고 있어요…"
        installing = true
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try self.connect(secret: secret, folders: folders)
                DispatchQueue.main.async {
                    let done = NSAlert()
                    done.messageText = "Mac 연결이 끝났어요"
                    done.informativeText = "선택한 \(folders.count)개 폴더에 정리 지침이 준비됐어요.\n모아 웹앱으로 돌아가면 다음 단계가 자동으로 표시됩니다."
                    done.addButton(withTitle: "확인")
                    done.runModal()
                    NSApp.terminate(nil)
                }
            } catch {
                DispatchQueue.main.async {
                    self.installing = false
                    self.message.stringValue = "연결하지 못했어요. 모아 웹앱에서 다시 시도해 주세요."
                    let failed = NSAlert()
                    failed.messageText = "Mac 연결 실패"
                    failed.informativeText = error.localizedDescription
                    failed.addButton(withTitle: "확인")
                    failed.runModal()
                }
            }
        }
    }

    func manageFolders() {
        installing = true
        let creating = createFolderRequested
        createFolderRequested = false
        guard let folders = FolderSelection().choose(adding: true, creating: creating) else {
            installing = false
            message.stringValue = "폴더 추가를 취소했어요. 기존 설정은 유지됩니다."
            return
        }
        message.stringValue = "추가한 폴더의 QWEN 지침을 준비하고 있어요…"
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try self.unlockLocal()
                _ = try self.request("local/folders/", body: ["folders": folders, "mode": "add"], csrf: self.currentCSRF())
                try self.waitForFolders(count: folders.count, configureInbox: false)
                DispatchQueue.main.async {
                    self.installing = false
                    self.message.stringValue = "폴더 추가가 끝났어요. 모아의 폴더 화면에서 확인하세요."
                    let done = NSAlert()
                    done.messageText = "폴더를 추가했어요"
                    done.informativeText = "기존 폴더와 지침은 유지하고 새 폴더를 등록했습니다. 모아 화면에 자동 반영됩니다."
                    done.addButton(withTitle: "확인")
                    done.runModal()
                }
            } catch {
                DispatchQueue.main.async {
                    self.installing = false
                    self.message.stringValue = "폴더를 추가하지 못했어요. 기존 폴더는 유지됩니다."
                    let failed = NSAlert()
                    failed.messageText = "폴더 추가 실패"
                    failed.informativeText = error.localizedDescription
                    failed.addButton(withTitle: "확인")
                    failed.runModal()
                }
            }
        }
    }

    func currentCSRF() throws -> String {
        guard let value = try request("auth/session/")["csrf"] as? String else {
            throw NSError(domain: "MoaHelper", code: 2, userInfo: [NSLocalizedDescriptionKey: "로컬 보안 세션을 시작하지 못했어요."])
        }
        return value
    }

    func unlockLocal() throws {
        let keyURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Moa/local-key")
        let key = try String(contentsOf: keyURL, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !key.isEmpty else { throw NSError(domain: "MoaHelper", code: 1, userInfo: [NSLocalizedDescriptionKey: "Mac 연결 프로그램을 다시 설치해 주세요."]) }
        _ = try request("local/unlock/", body: [:], csrf: currentCSRF(), localKey: key)
    }

    func connect(secret: String, folders: [String]) throws {
        try unlockLocal()
        _ = try request("local/folders/", body: ["folders": folders, "initial_cleanup": true], csrf: currentCSRF())
        if let _ = try request("local/setup/")["cloud_origin"] as? String {
            _ = try request("local/cloud/disconnect/", body: [:], csrf: currentCSRF())
        }
        _ = try request("local/cloud/connect/", body: ["origin": origin, "pairing_secret": secret], csrf: currentCSRF())
        try waitForFolders(count: folders.count, configureInbox: true)
    }

    func waitForFolders(count: Int, configureInbox: Bool) throws {
        let deadline = Date().addingTimeInterval(3600)
        while Date() < deadline {
            let progress = try request("local/folders/")
            let state = progress["status"] as? String ?? "failed"
            if state == "completed" {
                if configureInbox { _ = try request("local/setup/", body: [:], csrf: currentCSRF()) }
                return
            }
            if state == "failed" {
                throw NSError(domain: "MoaHelper", code: 4, userInfo: [NSLocalizedDescriptionKey: progress["detail"] as? String ?? "QWEN 지침을 다시 만들어 주세요."])
            }
            let completed = progress["completed"] as? Int ?? 0
            let folder = progress["folder"] as? String ?? ""
            DispatchQueue.main.async {
                self.message.stringValue = state == "generating"
                    ? "QWEN이 지침을 작성하고 있어요. \(completed + 1)/\(count)\n\(folder)"
                    : "QWEN을 Mac에 준비하고 있어요. 처음에는 모델 다운로드로 시간이 걸릴 수 있어요."
            }
            Thread.sleep(forTimeInterval: 2)
        }
        throw NSError(domain: "MoaHelper", code: 5, userInfo: [NSLocalizedDescriptionKey: "지침 준비 시간이 오래 걸리고 있어요. 연결 앱에서 다시 확인해 주세요."])
    }

    func request(_ path: String, body: [String: Any]? = nil, csrf: String? = nil, localKey: String? = nil) throws -> [String: Any] {
        let url = URL(string: "http://127.0.0.1:8000/api/v1/" + path)!
        var request = URLRequest(url: url)
        request.timeoutInterval = 22
        if let body = body {
            request.httpMethod = "POST"
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if let csrf = csrf { request.setValue(csrf, forHTTPHeaderField: "X-CSRFToken") }
        if let localKey = localKey { request.setValue(localKey, forHTTPHeaderField: "X-Moa-Local-Key") }
        let wait = DispatchSemaphore(value: 0)
        var result: Data?
        var response: URLResponse?
        var failure: Error?
        URLSession.shared.dataTask(with: request) { data, received, error in
            result = data; response = received; failure = error; wait.signal()
        }.resume()
        guard wait.wait(timeout: .now() + 24) == .success, let http = response as? HTTPURLResponse, let data = result else {
            throw failure ?? NSError(domain: "MoaHelper", code: 3, userInfo: [NSLocalizedDescriptionKey: "Mac 연결 프로그램이 실행 중인지 확인해 주세요."])
        }
        let payload = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        guard (200..<300).contains(http.statusCode) else {
            throw NSError(domain: "MoaHelper", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: payload["detail"] as? String ?? "연결 요청을 완료하지 못했어요."])
        }
        return payload
    }
}
let app = NSApplication.shared
let delegate = HelperApp(); app.delegate = delegate; app.setActivationPolicy(.regular); app.run()
