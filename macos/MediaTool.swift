import Foundation
import AVFoundation
import CoreMedia
import CoreGraphics
import CoreText
import AppKit
import ImageIO
import UniformTypeIdentifiers

func fail(_ message: String) -> Never {
    let payload: [String: Any] = ["ok": false, "error": message]
    if let data = try? JSONSerialization.data(withJSONObject: payload),
       let text = String(data: data, encoding: .utf8) {
        FileHandle.standardError.write((text + "\n").data(using: .utf8)!)
    } else {
        FileHandle.standardError.write((message + "\n").data(using: .utf8)!)
    }
    exit(1)
}

func emit(_ object: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: object),
          let text = String(data: data, encoding: .utf8) else {
        fail("JSON 序列化失败")
    }
    print(text)
}

func transformedSize(naturalSize: CGSize, preferredTransform: CGAffineTransform) -> CGSize {
    let rect = CGRect(origin: .zero, size: naturalSize).applying(preferredTransform)
    return CGSize(width: abs(rect.width), height: abs(rect.height))
}

func writePNG(_ cgImage: CGImage, to outURL: URL) throws {
    try FileManager.default.createDirectory(at: outURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    let tempURL = outURL.deletingLastPathComponent().appendingPathComponent("." + UUID().uuidString + ".png")
    guard let dest = CGImageDestinationCreateWithURL(tempURL as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        fail("无法创建 PNG 输出目标")
    }
    CGImageDestinationAddImage(dest, cgImage, nil)
    guard CGImageDestinationFinalize(dest) else {
        try? FileManager.default.removeItem(at: tempURL)
        fail("PNG 编码写入失败")
    }
    if FileManager.default.fileExists(atPath: outURL.path) {
        try? FileManager.default.removeItem(at: outURL)
    }
    try FileManager.default.moveItem(at: tempURL, to: outURL)
}

func makeSubtitleCGImage(zh: String, en: String, width: Int, height: Int) -> CGImage? {
    let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: width,
        pixelsHigh: height,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    )
    guard let bitmap = rep else { return nil }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)

    let para = NSMutableParagraphStyle()
    para.alignment = .center

    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.0, alpha: 0.92)
    shadow.shadowBlurRadius = 8.0
    shadow.shadowOffset = NSSize(width: 0, height: -2)

    let isVertical = height > width
    let zhSize: CGFloat = isVertical ? max(28, CGFloat(width) * 0.044) : max(26, CGFloat(width) * 0.021)
    let enSize: CGFloat = isVertical ? max(17, CGFloat(width) * 0.025) : max(15, CGFloat(width) * 0.0125)

    let zhFont = NSFont(name: "PingFangSC-Semibold", size: zhSize) ?? NSFont.boldSystemFont(ofSize: zhSize)
    let enFont = NSFont(name: "AvenirNext-Medium", size: enSize) ?? NSFont.systemFont(ofSize: enSize, weight: .medium)

    let zhStroke: [NSAttributedString.Key: Any] = [
        .font: zhFont, .strokeColor: NSColor(calibratedWhite: 0.0, alpha: 0.95),
        .strokeWidth: 5.0, .paragraphStyle: para, .shadow: shadow
    ]
    let zhFill: [NSAttributedString.Key: Any] = [
        .font: zhFont, .foregroundColor: NSColor.white, .paragraphStyle: para
    ]
    let enStroke: [NSAttributedString.Key: Any] = [
        .font: enFont, .strokeColor: NSColor(calibratedWhite: 0.0, alpha: 0.95),
        .strokeWidth: 4.0, .paragraphStyle: para, .shadow: shadow
    ]
    let enFill: [NSAttributedString.Key: Any] = [
        .font: enFont, .foregroundColor: NSColor(calibratedRed: 0.93, green: 0.94, blue: 0.98, alpha: 0.95),
        .paragraphStyle: para
    ]

    let baseBottom: CGFloat = isVertical ? CGFloat(height) * 0.14 : max(36, CGFloat(height) * 0.042)
    let padX: CGFloat = max(36, CGFloat(width) * 0.05)
    let zhRect = NSRect(x: padX, y: baseBottom + (en.isEmpty ? 8 : enSize * 1.65), width: CGFloat(width) - padX * 2, height: zhSize * 1.6)
    let enRect = NSRect(x: padX, y: baseBottom, width: CGFloat(width) - padX * 2, height: enSize * 1.55)

    if !zh.isEmpty {
        (zh as NSString).draw(in: zhRect, withAttributes: zhStroke)
        (zh as NSString).draw(in: zhRect, withAttributes: zhFill)
    }
    if !en.isEmpty {
        (en as NSString).draw(in: enRect, withAttributes: enStroke)
        (en as NSString).draw(in: enRect, withAttributes: enFill)
    }
    NSGraphicsContext.restoreGraphicsState()
    return bitmap.cgImage
}

@main
struct MediaTool {
    static func main() async {
        let args = CommandLine.arguments
        guard args.count >= 3 else {
            fail("用法: gclabs-media <probe|extract-frame|extract-audio|slice-grid|filmstrip|storyboard-sheet|concat> ...")
        }
        let cmd = args[1]
        do {
            switch cmd {
            case "probe":
                try await runProbe(path: args[2])
            case "extract-frame":
                guard args.count >= 4 else { fail("用法: gclabs-media extract-frame <video> <out.png> [first|last|<sec>]") }
                let mode = args.count >= 5 ? args[4] : "last"
                try await runExtractFrame(videoPath: args[2], outputPath: args[3], mode: mode)
            case "extract-audio":
                guard args.count >= 4 else { fail("用法: gclabs-media extract-audio <video> <out.m4a>") }
                try await runExtractAudio(videoPath: args[2], outputPath: args[3])
            case "slice-grid":
                guard args.count >= 6 else { fail("用法: gclabs-media slice-grid <image> <out_dir> <rows> <cols> [inset_pct]") }
                let rows = max(1, min(6, Int(args[4]) ?? 3))
                let cols = max(1, min(6, Int(args[5]) ?? 3))
                let inset = args.count >= 7 ? max(0.0, min(0.08, Double(args[6]) ?? 0.012)) : 0.012
                try runSliceGrid(imagePath: args[2], outDir: args[3], rows: rows, cols: cols, insetPct: inset)
            case "filmstrip":
                guard args.count >= 4 else { fail("用法: gclabs-media filmstrip <video> <out.jpg> [count]") }
                let count = args.count >= 5 ? max(2, min(8, Int(args[4]) ?? 4)) : 4
                try await runFilmstrip(videoPath: args[2], outputPath: args[3], count: count)
            case "storyboard-sheet":
                guard args.count >= 4 else { fail("用法: gclabs-media storyboard-sheet <spec.json> <out.png>") }
                try runStoryboardSheet(specPath: args[2], outputPath: args[3])
            case "concat":
                guard args.count >= 4 else { fail("用法: gclabs-media concat <spec.json> <out.mp4>") }
                try await runConcat(specPath: args[2], outputPath: args[3])
            default:
                fail("未知子命令: \(cmd)")
            }
        } catch {
            fail(error.localizedDescription)
        }
    }

    static func runProbe(path: String) async throws {
        let url = URL(fileURLWithPath: path)
        guard FileManager.default.fileExists(atPath: url.path) else { fail("媒体文件不存在") }
        let asset = AVURLAsset(url: url)
        let durationCM = try await asset.load(.duration)
        let duration = CMTimeGetSeconds(durationCM)
        let vTracks = try await asset.loadTracks(withMediaType: .video)
        let aTracks = try await asset.loadTracks(withMediaType: .audio)
        var width = 0
        var height = 0
        var fps = 24.0
        if let vt = vTracks.first {
            let natural = try await vt.load(.naturalSize)
            let transform = try await vt.load(.preferredTransform)
            let nominal = try await vt.load(.nominalFrameRate)
            let sz = transformedSize(naturalSize: natural, preferredTransform: transform)
            width = Int(sz.width.rounded())
            height = Int(sz.height.rounded())
            if nominal > 0 { fps = Double(nominal) }
        }
        emit([
            "ok": true,
            "duration": duration.isFinite ? duration : 0.0,
            "width": width,
            "height": height,
            "fps": fps,
            "has_video": !vTracks.isEmpty,
            "has_audio": !aTracks.isEmpty
        ])
    }

    static func runExtractFrame(videoPath: String, outputPath: String, mode: String) async throws {
        let inputURL = URL(fileURLWithPath: videoPath)
        let outURL = URL(fileURLWithPath: outputPath)
        guard FileManager.default.fileExists(atPath: inputURL.path) else { fail("视频文件不存在") }
        let asset = AVURLAsset(url: inputURL)
        let duration = CMTimeGetSeconds(try await asset.load(.duration))
        let vTracks = try await asset.loadTracks(withMediaType: .video)
        guard duration.isFinite && duration > 0, let vt = vTracks.first else {
            fail("无法读取视频轨道或时长无效")
        }
        let nominal = try await vt.load(.nominalFrameRate)
        let fps = nominal > 0 ? Double(nominal) : 24.0
        let frameStep = 1.0 / fps
        let videoRange = try await vt.load(.timeRange)
        let videoEnd = CMTimeGetSeconds(CMTimeRangeGetEnd(videoRange))
        let endSec = videoEnd.isFinite && videoEnd > 0 ? min(duration, videoEnd) : duration
        let targetSec: Double
        if mode == "first" {
            targetSec = 0.0
        } else if mode == "last" {
            // Request inside the final video sample. A fixed 42 ms offset skipped frames
            // at 24/30/60 fps; asset duration can also include a longer audio tail.
            targetSec = max(0.0, endSec - frameStep * 0.5)
        } else if let custom = Double(mode), custom.isFinite {
            targetSec = min(max(0.0, custom), max(0.0, endSec - frameStep * 0.5))
        } else {
            fail("无效的帧位置参数")
        }

        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = .zero

        let reqTime = CMTime(seconds: targetSec, preferredTimescale: 60000)
        let cgImage: CGImage
        let actualTime: CMTime
        do {
            let pair = try await generator.image(at: reqTime)
            cgImage = pair.image
            actualTime = pair.actualTime
        } catch {
            generator.requestedTimeToleranceBefore = CMTime(seconds: 0.25, preferredTimescale: 600)
            generator.requestedTimeToleranceAfter = CMTime(seconds: 0.25, preferredTimescale: 600)
            let pair = try await generator.image(at: reqTime)
            cgImage = pair.image
            actualTime = pair.actualTime
        }

        try writePNG(cgImage, to: outURL)
        emit([
            "ok": true,
            "width": cgImage.width,
            "height": cgImage.height,
            "timestamp": CMTimeGetSeconds(actualTime),
            "output": outURL.path
        ])
    }

    static func runExtractAudio(videoPath: String, outputPath: String) async throws {
        let inputURL = URL(fileURLWithPath: videoPath)
        let outURL = URL(fileURLWithPath: outputPath)
        guard FileManager.default.fileExists(atPath: inputURL.path) else { fail("视频文件不存在") }
        let asset = AVURLAsset(url: inputURL)
        let aTracks = try await asset.loadTracks(withMediaType: .audio)
        guard let aTrack = aTracks.first else { fail("该视频不包含音轨") }
        let dur = try await asset.load(.duration)

        let comp = AVMutableComposition()
        guard let dstTrack = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            fail("无法创建音频提取轨道")
        }
        try dstTrack.insertTimeRange(CMTimeRange(start: .zero, duration: dur), of: aTrack, at: .zero)

        try FileManager.default.createDirectory(at: outURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        let tempOut = outURL.deletingLastPathComponent().appendingPathComponent("." + UUID().uuidString + ".m4a")
        guard let exporter = AVAssetExportSession(asset: comp, presetName: AVAssetExportPresetAppleM4A) else {
            fail("无法初始化音频导出器")
        }
        exporter.outputURL = tempOut
        exporter.outputFileType = .m4a
        await exporter.export()
        if exporter.status != .completed {
            try? FileManager.default.removeItem(at: tempOut)
            fail("提取音频失败: \(exporter.error?.localizedDescription ?? "")")
        }
        if FileManager.default.fileExists(atPath: outURL.path) {
            try? FileManager.default.removeItem(at: outURL)
        }
        try FileManager.default.moveItem(at: tempOut, to: outURL)
        emit(["ok": true, "duration": CMTimeGetSeconds(dur), "output": outURL.path])
    }

    static func runSliceGrid(imagePath: String, outDir: String, rows: Int, cols: Int, insetPct: Double) throws {
        let inURL = URL(fileURLWithPath: imagePath)
        guard let src = CGImageSourceCreateWithURL(inURL as CFURL, nil),
              let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
            fail("无法读取待切分的宫格图像")
        }
        let dirURL = URL(fileURLWithPath: outDir)
        try FileManager.default.createDirectory(at: dirURL, withIntermediateDirectories: true)
        let cellW = Double(cg.width) / Double(cols)
        let cellH = Double(cg.height) / Double(rows)
        let insetX = cellW * insetPct
        let insetY = cellH * insetPct

        var outputs: [[String: Any]] = []
        var idx = 1
        for r in 0..<rows {
            for c in 0..<cols {
                let rx = Int((Double(c) * cellW + insetX).rounded())
                let ry = Int((Double(r) * cellH + insetY).rounded())
                let rw = max(16, Int((cellW - insetX * 2.0).rounded()) & ~1)
                let rh = max(16, Int((cellH - insetY * 2.0).rounded()) & ~1)
                let cropRect = CGRect(x: rx, y: ry, width: min(rw, cg.width - rx), height: min(rh, cg.height - ry))
                guard let sub = cg.cropping(to: cropRect) else { fail("宫格裁切越界") }
                let outFile = dirURL.appendingPathComponent(String(format: "panel_%02d.png", idx))
                try writePNG(sub, to: outFile)
                outputs.append([
                    "index": idx,
                    "row": r + 1,
                    "col": c + 1,
                    "width": sub.width,
                    "height": sub.height,
                    "path": outFile.path
                ])
                idx += 1
            }
        }
        emit(["ok": true, "rows": rows, "cols": cols, "count": outputs.count, "panels": outputs])
    }

    static func runFilmstrip(videoPath: String, outputPath: String, count: Int) async throws {
        let inputURL = URL(fileURLWithPath: videoPath)
        let outURL = URL(fileURLWithPath: outputPath)
        guard FileManager.default.fileExists(atPath: inputURL.path) else { fail("视频文件不存在") }
        let asset = AVURLAsset(url: inputURL)
        let duration = CMTimeGetSeconds(try await asset.load(.duration))
        let vTracks = try await asset.loadTracks(withMediaType: .video)
        guard duration.isFinite && duration > 0.05, let vt = vTracks.first else { fail("无效视频时长") }
        let sz = transformedSize(naturalSize: try await vt.load(.naturalSize), preferredTransform: try await vt.load(.preferredTransform))
        let aspect = max(0.5, min(2.4, sz.width / max(1, sz.height)))

        let gen = AVAssetImageGenerator(asset: asset)
        gen.appliesPreferredTrackTransform = true
        gen.requestedTimeToleranceBefore = CMTime(seconds: 0.08, preferredTimescale: 600)
        gen.requestedTimeToleranceAfter = CMTime(seconds: 0.08, preferredTimescale: 600)

        let cellH = 220
        let cellW = Int((Double(cellH - 28) * Double(aspect)).rounded()) + 12
        let stripW = cellW * count
        let stripH = cellH

        let rep = NSBitmapImageRep(
            bitmapDataPlanes: nil, pixelsWide: stripW, pixelsHigh: stripH,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
        )!

        var captured: [(Double, CGImage?)] = []
        for i in 0..<count {
            let frac = count == 1 ? 0.5 : (0.08 + 0.84 * Double(i) / Double(count - 1))
            let t = min(max(0.0, duration * frac), max(0.0, duration - 0.05))
            let cm = CMTime(seconds: t, preferredTimescale: 600)
            let img = (try? await gen.image(at: cm))?.image
            captured.append((t, img))
        }

        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
        let ctx = NSGraphicsContext.current!.cgContext
        ctx.setFillColor(CGColor(srgbRed: 0.055, green: 0.05, blue: 0.075, alpha: 1.0))
        ctx.fill(CGRect(x: 0, y: 0, width: stripW, height: stripH))

        let labelAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedDigitSystemFont(ofSize: 12, weight: .semibold),
            .foregroundColor: NSColor(srgbRed: 1.0, green: 0.80, blue: 0.12, alpha: 1.0)
        ]

        for (i, (sec, cgOpt)) in captured.enumerated() {
            let x = i * cellW
            if let cg = cgOpt {
                ctx.draw(cg, in: CGRect(x: x + 6, y: 6, width: cellW - 12, height: cellH - 28))
            }
            let tag = String(format: "F%d · %.2fs", i + 1, sec)
            (tag as NSString).draw(at: NSPoint(x: x + 10, y: cellH - 20), withAttributes: labelAttrs)
        }
        NSGraphicsContext.restoreGraphicsState()

        try FileManager.default.createDirectory(at: outURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        guard let jpg = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.88]) else {
            fail("生成抽帧质检条失败")
        }
        try jpg.write(to: outURL)
        emit(["ok": true, "frames": count, "width": stripW, "height": stripH, "output": outURL.path])
    }

    static func runStoryboardSheet(specPath: String, outputPath: String) throws {
        guard let raw = try? Data(contentsOf: URL(fileURLWithPath: specPath)),
              let spec = try? JSONSerialization.jsonObject(with: raw) as? [String: Any],
              let shots = spec["shots"] as? [[String: Any]], !shots.isEmpty else {
            fail("分镜表配置为空")
        }
        let productName = (spec["product_name"] as? String) ?? "CineHarbor"
        let projectTitle = (spec["project_name"] as? String) ?? "\(productName) 分镜通告单"
        let cols = min(3, max(1, shots.count))
        let rows = Int(ceil(Double(shots.count) / Double(cols)))
        let cardW = 520, cardH = 400
        let pad = 32, headerH = 96
        let totalW = pad * 2 + cols * cardW + (cols - 1) * 20
        let totalH = headerH + pad + rows * cardH + (rows - 1) * 20

        let rep = NSBitmapImageRep(
            bitmapDataPlanes: nil, pixelsWide: totalW, pixelsHigh: totalH,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
        )!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
        let ctx = NSGraphicsContext.current!.cgContext
        ctx.setFillColor(CGColor(srgbRed: 0.045, green: 0.04, blue: 0.065, alpha: 1.0))
        ctx.fill(CGRect(x: 0, y: 0, width: totalW, height: totalH))

        let titleAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.boldSystemFont(ofSize: 24),
            .foregroundColor: NSColor(srgbRed: 0.96, green: 0.95, blue: 0.92, alpha: 1.0)
        ]
        let subAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 13, weight: .medium),
            .foregroundColor: NSColor(srgbRed: 0.71, green: 0.60, blue: 0.91, alpha: 0.92)
        ]
        (projectTitle as NSString).draw(at: NSPoint(x: pad, y: totalH - 48), withAttributes: titleAttrs)
        (("\(productName) · by GachaFrame  |  共 \(shots.count) 镜分镜通告单") as NSString).draw(at: NSPoint(x: pad, y: totalH - 74), withAttributes: subAttrs)

        let numAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.boldSystemFont(ofSize: 14),
            .foregroundColor: NSColor(srgbRed: 0.71, green: 0.60, blue: 0.91, alpha: 1.0)
        ]
        let headAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.boldSystemFont(ofSize: 14),
            .foregroundColor: NSColor.white
        ]
        let bodyAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 12),
            .foregroundColor: NSColor(calibratedWhite: 0.78, alpha: 1.0)
        ]

        for (i, sh) in shots.enumerated() {
            let c = i % cols
            let r = i / cols
            let x = pad + c * (cardW + 20)
            let y = totalH - headerH - (r + 1) * cardH - r * 20

            let cardRect = CGRect(x: x, y: y, width: cardW, height: cardH)
            let cardPath = CGPath(roundedRect: cardRect, cornerWidth: 14, cornerHeight: 14, transform: nil)
            ctx.addPath(cardPath)
            ctx.setFillColor(CGColor(srgbRed: 0.10, green: 0.09, blue: 0.14, alpha: 1.0))
            ctx.fillPath()
            ctx.addPath(cardPath)
            ctx.setStrokeColor(CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.12))
            ctx.setLineWidth(1.0)
            ctx.strokePath()

            let imgRect = CGRect(x: x + 12, y: y + 112, width: cardW - 24, height: 252)
            ctx.setFillColor(CGColor(srgbRed: 0.06, green: 0.055, blue: 0.085, alpha: 1.0))
            ctx.fill(imgRect)
            if let imgPath = sh["image_path"] as? String, !imgPath.isEmpty,
               let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: imgPath) as CFURL, nil),
               let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) {
                ctx.draw(cg, in: imgRect)
            }

            let numStr = String(format: "SHOT %02d  ·  %.1fs", i + 1, (sh["duration"] as? Double) ?? 5.0)
            (numStr as NSString).draw(at: NSPoint(x: x + 14, y: y + cardH - 28), withAttributes: numAttrs)
            let stitle = (sh["title"] as? String) ?? ""
            (stitle as NSString).draw(in: NSRect(x: x + 14, y: y + 78, width: cardW - 28, height: 24), withAttributes: headAttrs)
            let dial = (sh["dialogue"] as? String) ?? ""
            let desc = !dial.isEmpty ? "台词：「\(dial)」" : ((sh["prompt"] as? String) ?? "")
            (desc as NSString).draw(in: NSRect(x: x + 14, y: y + 14, width: cardW - 28, height: 58), withAttributes: bodyAttrs)
        }

        NSGraphicsContext.restoreGraphicsState()
        guard let cgOut = rep.cgImage else { fail("无法生成分镜通告单图像") }
        try writePNG(cgOut, to: URL(fileURLWithPath: outputPath))
        emit(["ok": true, "shots": shots.count, "width": totalW, "height": totalH, "output": outputPath])
    }

    static func runConcat(specPath: String, outputPath: String) async throws {
        let specURL = URL(fileURLWithPath: specPath)
        let outURL = URL(fileURLWithPath: outputPath)
        guard let raw = try? Data(contentsOf: specURL),
              let spec = try? JSONSerialization.jsonObject(with: raw) as? [String: Any],
              let clips = spec["clips"] as? [[String: Any]], !clips.isEmpty else {
            fail("粗剪配置无效或镜头为空")
        }

        let targetAspect = (spec["target_aspect"] as? String) ?? "auto"
        let burnSubtitles = (spec["burn_subtitles"] as? Bool) ?? false
        let enableDucking = (spec["ducking"] as? Bool) ?? true
        let baseBGMVol = Float((spec["bgm_base_volume"] as? Double) ?? 0.36)
        let duckBGMVol = Float((spec["bgm_duck_volume"] as? Double) ?? 0.12)
        let rawSubtitles = (spec["subtitles"] as? [[String: Any]]) ?? []

        let composition = AVMutableComposition()
        guard let trackA = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid),
              let trackB = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            fail("无法创建视频合成轨道")
        }
        var clipAudioTrack: AVMutableCompositionTrack? = nil
        var usedTrackB = false

        var cursor = CMTime.zero
        var renderSize = CGSize.zero
        var renderFPS: Int32 = 24
        var instructions: [AVMutableVideoCompositionInstruction] = []
        var addedClips = 0

        for item in clips {
            guard let path = item["path"] as? String, FileManager.default.fileExists(atPath: path) else {
                fail("镜头视频文件不存在: \(item["path"] ?? "")")
            }
            let asset = AVURLAsset(url: URL(fileURLWithPath: path))
            let totalDur = CMTimeGetSeconds(try await asset.load(.duration))
            let vTracks = try await asset.loadTracks(withMediaType: .video)
            guard totalDur.isFinite && totalDur > 0.05, let vTrack = vTracks.first else {
                fail("镜头视频不可读: \(path)")
            }
            let natural = try await vTrack.load(.naturalSize)
            let prefTransform = try await vTrack.load(.preferredTransform)
            let nominal = try await vTrack.load(.nominalFrameRate)

            let startSec = max(0.0, (item["start"] as? Double) ?? 0.0)
            let rawEnd = (item["end"] as? Double) ?? totalDur
            let endSec = min(totalDur, rawEnd > 0 ? rawEnd : totalDur)
            guard endSec - startSec >= 0.05 else {
                fail("镜头裁剪时长过短: \(path)")
            }

            let naturalTransformed = transformedSize(naturalSize: natural, preferredTransform: prefTransform)
            if renderSize == .zero {
                if targetAspect == "9:16" {
                    renderSize = CGSize(width: 1080, height: 1920)
                } else if targetAspect == "16:9" {
                    renderSize = CGSize(width: 1920, height: 1080)
                } else {
                    let w = max(2, Int(naturalTransformed.width.rounded()) & ~1)
                    let h = max(2, Int(naturalTransformed.height.rounded()) & ~1)
                    renderSize = CGSize(width: w, height: h)
                }
                if nominal >= 1 {
                    renderFPS = Int32(min(60, max(12, Int(nominal.rounded()))))
                }
            }

            let startTime = CMTime(seconds: startSec, preferredTimescale: 600)
            let segDuration = CMTime(seconds: endSec - startSec, preferredTimescale: 600)
            let timeRange = CMTimeRange(start: startTime, duration: segDuration)

            let segTrack = (addedClips % 2 == 0) ? trackA : trackB
            if addedClips % 2 == 1 { usedTrackB = true }
            try segTrack.insertTimeRange(timeRange, of: vTrack, at: cursor)

            let muteSource = (item["mute_source_audio"] as? Bool) ?? false
            if !muteSource {
                let aTracks = try await asset.loadTracks(withMediaType: .audio)
                if let aTrack = aTracks.first {
                    if clipAudioTrack == nil {
                        clipAudioTrack = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)
                    }
                    try? clipAudioTrack?.insertTimeRange(timeRange, of: aTrack, at: cursor)
                }
            }

            let useFillCrop = (targetAspect == "9:16" || targetAspect == "16:9")
            let scale = useFillCrop
                ? max(renderSize.width / max(1, naturalTransformed.width), renderSize.height / max(1, naturalTransformed.height))
                : min(renderSize.width / max(1, naturalTransformed.width), renderSize.height / max(1, naturalTransformed.height))
            let scaledW = naturalTransformed.width * scale
            let scaledH = naturalTransformed.height * scale
            let tx = (renderSize.width - scaledW) / 2.0
            let ty = (renderSize.height - scaledH) / 2.0

            let rawBox = CGRect(origin: .zero, size: natural).applying(prefTransform)
            let normalize = prefTransform.concatenating(CGAffineTransform(translationX: -rawBox.origin.x, y: -rawBox.origin.y))
            let finalTransform = normalize
                .concatenating(CGAffineTransform(scaleX: scale, y: scale))
                .concatenating(CGAffineTransform(translationX: tx, y: ty))

            let instruction = AVMutableVideoCompositionInstruction()
            instruction.timeRange = CMTimeRange(start: cursor, duration: segDuration)
            let layer = AVMutableVideoCompositionLayerInstruction(assetTrack: segTrack)
            layer.setTransform(finalTransform, at: cursor)
            instruction.layerInstructions = [layer]
            instructions.append(instruction)

            cursor = CMTimeAdd(cursor, segDuration)
            addedClips += 1
        }

        if !usedTrackB {
            composition.removeTrack(trackB)
        }

        let totalSec = CMTimeGetSeconds(cursor)
        var audioMixParams: [AVMutableAudioMixInputParameters] = []
        if let dt = clipAudioTrack {
            let dp = AVMutableAudioMixInputParameters(track: dt)
            dp.setVolume(1.0, at: .zero)
            audioMixParams.append(dp)
        }

        if let audioPath = spec["audio_path"] as? String, !audioPath.isEmpty, FileManager.default.fileExists(atPath: audioPath) {
            let audioAsset = AVURLAsset(url: URL(fileURLWithPath: audioPath))
            let bgTracks = try await audioAsset.loadTracks(withMediaType: .audio)
            if let bgTrack = bgTracks.first {
                let audioDur = CMTimeGetSeconds(try await audioAsset.load(.duration))
                let audioStart = max(0.0, (spec["audio_start"] as? Double) ?? 0.0)
                let avail = max(0.0, audioDur - audioStart)
                let takeSec = min(totalSec, avail)
                if takeSec > 0.05,
                   let compBGM = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) {
                    let range = CMTimeRange(start: CMTime(seconds: audioStart, preferredTimescale: 600),
                                            duration: CMTime(seconds: takeSec, preferredTimescale: 600))
                    try? compBGM.insertTimeRange(range, of: bgTrack, at: .zero)

                    let bp = AVMutableAudioMixInputParameters(track: compBGM)
                    let effBase: Float = clipAudioTrack != nil ? baseBGMVol : 1.0
                    bp.setVolume(effBase, at: .zero)
                    let fadeOutStart = max(0.2, takeSec - 1.0)
                    var lastRampEnd = 0.0

                    if enableDucking && clipAudioTrack != nil && !rawSubtitles.isEmpty {
                        for cue in rawSubtitles {
                            let cStart = (cue["start"] as? Double) ?? 0.0
                            let cEnd = (cue["end"] as? Double) ?? 0.0
                            guard cEnd > cStart + 0.1 else { continue }
                            let downStart = max(lastRampEnd + 0.02, cStart - 0.15)
                            let downEnd = min(fadeOutStart - 0.25, downStart + 0.18)
                            if downEnd > downStart + 0.03 {
                                bp.setVolumeRamp(fromStartVolume: effBase, toEndVolume: duckBGMVol,
                                                 timeRange: CMTimeRange(start: CMTime(seconds: downStart, preferredTimescale: 600),
                                                                        duration: CMTime(seconds: downEnd - downStart, preferredTimescale: 600)))
                                lastRampEnd = downEnd
                            }
                            let upStart = max(lastRampEnd + 0.02, cEnd)
                            let upEnd = min(fadeOutStart - 0.04, upStart + 0.25)
                            if upEnd > upStart + 0.03 {
                                bp.setVolumeRamp(fromStartVolume: duckBGMVol, toEndVolume: effBase,
                                                 timeRange: CMTimeRange(start: CMTime(seconds: upStart, preferredTimescale: 600),
                                                                        duration: CMTime(seconds: upEnd - upStart, preferredTimescale: 600)))
                                lastRampEnd = upEnd
                            }
                        }
                    }
                    if takeSec > fadeOutStart + 0.1 && fadeOutStart > lastRampEnd + 0.01 {
                        let startVol = (enableDucking && lastRampEnd >= fadeOutStart - 0.05) ? duckBGMVol : effBase
                        bp.setVolumeRamp(fromStartVolume: startVol, toEndVolume: 0.02,
                                         timeRange: CMTimeRange(start: CMTime(seconds: fadeOutStart, preferredTimescale: 600),
                                                                duration: CMTime(seconds: takeSec - fadeOutStart, preferredTimescale: 600)))
                    }
                    audioMixParams.append(bp)
                }
            }
        }

        let videoComp = AVMutableVideoComposition()
        videoComp.renderSize = renderSize
        videoComp.frameDuration = CMTime(value: 1, timescale: renderFPS)
        videoComp.instructions = instructions

        if burnSubtitles && !rawSubtitles.isEmpty {
            let parentLayer = CALayer()
            parentLayer.frame = CGRect(origin: .zero, size: renderSize)
            let videoLayer = CALayer()
            videoLayer.frame = CGRect(origin: .zero, size: renderSize)
            parentLayer.addSublayer(videoLayer)

            for cue in rawSubtitles {
                let zh = (cue["zh"] as? String) ?? ""
                let en = (cue["en"] as? String) ?? ""
                let cStart = max(0.0, (cue["start"] as? Double) ?? 0.0)
                let cEnd = min(totalSec, (cue["end"] as? Double) ?? 0.0)
                guard (!zh.isEmpty || !en.isEmpty), cEnd > cStart + 0.1 else { continue }
                guard let cgImg = makeSubtitleCGImage(zh: zh, en: en, width: Int(renderSize.width), height: Int(renderSize.height)) else { continue }

                let subLayer = CALayer()
                subLayer.frame = CGRect(origin: .zero, size: renderSize)
                subLayer.contents = cgImg
                subLayer.opacity = 0.0

                let anim = CAKeyframeAnimation(keyPath: "opacity")
                let sFrac = max(0.0, min(1.0, cStart / max(0.1, totalSec)))
                let inFrac = min(1.0, (cStart + 0.14) / max(0.1, totalSec))
                let outFrac = max(inFrac, (cEnd - 0.14) / max(0.1, totalSec))
                let eFrac = max(outFrac, min(1.0, cEnd / max(0.1, totalSec)))
                anim.keyTimes = [0.0, NSNumber(value: max(0.0, sFrac - 0.001)), NSNumber(value: inFrac), NSNumber(value: outFrac), NSNumber(value: eFrac), 1.0]
                anim.values = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0]
                anim.duration = totalSec
                anim.beginTime = AVCoreAnimationBeginTimeAtZero
                anim.isRemovedOnCompletion = false
                anim.fillMode = .both
                subLayer.add(anim, forKey: "subOpacity")
                parentLayer.addSublayer(subLayer)
            }
            videoComp.animationTool = AVVideoCompositionCoreAnimationTool(postProcessingAsVideoLayer: videoLayer, in: parentLayer)
        }

        try FileManager.default.createDirectory(at: outURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        let tempOut = outURL.deletingLastPathComponent().appendingPathComponent("." + UUID().uuidString + ".mp4")
        guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetHighestQuality) else {
            fail("无法初始化 AVFoundation 导出会话")
        }
        exporter.outputURL = tempOut
        exporter.outputFileType = .mp4
        exporter.videoComposition = videoComp
        if !audioMixParams.isEmpty {
            let mix = AVMutableAudioMix()
            mix.inputParameters = audioMixParams
            exporter.audioMix = mix
        }
        exporter.shouldOptimizeForNetworkUse = true

        await exporter.export()
        if exporter.status != .completed {
            try? FileManager.default.removeItem(at: tempOut)
            fail("视频合成导出失败: \(exporter.error?.localizedDescription ?? "状态 \(exporter.status.rawValue)")")
        }
        if FileManager.default.fileExists(atPath: outURL.path) {
            try? FileManager.default.removeItem(at: outURL)
        }
        try FileManager.default.moveItem(at: tempOut, to: outURL)
        emit([
            "ok": true,
            "duration": totalSec,
            "width": Int(renderSize.width),
            "height": Int(renderSize.height),
            "clips": addedClips,
            "subtitles_burned": burnSubtitles ? rawSubtitles.count : 0,
            "output": outURL.path
        ])
    }
}
