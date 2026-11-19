import Foundation
import AVFoundation
import CoreMedia
import CoreGraphics
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

@main
struct MediaTool {
    static func main() async {
        let args = CommandLine.arguments
        guard args.count >= 3 else {
            fail("用法: gclabs-media <probe|extract-frame|concat> ...")
        }
        let cmd = args[1]
        do {
            switch cmd {
            case "probe":
                try await runProbe(path: args[2])
            case "extract-frame":
                guard args.count >= 4 else {
                    fail("用法: gclabs-media extract-frame <video> <out.png> [first|last|<sec>]")
                }
                let mode = args.count >= 5 ? args[4] : "last"
                try await runExtractFrame(videoPath: args[2], outputPath: args[3], mode: mode)
            case "concat":
                guard args.count >= 4 else {
                    fail("用法: gclabs-media concat <spec.json> <out.mp4>")
                }
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
        let frameStep = max(1.0 / fps, 0.042)
        let targetSec: Double
        if mode == "first" {
            targetSec = 0.0
        } else if mode == "last" {
            targetSec = max(0.0, duration - frameStep)
        } else if let custom = Double(mode), custom.isFinite {
            targetSec = min(max(0.0, custom), max(0.0, duration - frameStep))
        } else {
            fail("无效的帧位置参数")
        }

        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = .zero

        let reqTime = CMTime(seconds: targetSec, preferredTimescale: 600)
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
        emit([
            "ok": true,
            "width": cgImage.width,
            "height": cgImage.height,
            "timestamp": CMTimeGetSeconds(actualTime),
            "output": outURL.path
        ])
    }

    static func runConcat(specPath: String, outputPath: String) async throws {
        let specURL = URL(fileURLWithPath: specPath)
        let outURL = URL(fileURLWithPath: outputPath)
        guard let raw = try? Data(contentsOf: specURL),
              let spec = try? JSONSerialization.jsonObject(with: raw) as? [String: Any],
              let clips = spec["clips"] as? [[String: Any]], !clips.isEmpty else {
            fail("粗剪配置无效或镜头为空")
        }

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
                let w = max(2, Int(naturalTransformed.width.rounded()) & ~1)
                let h = max(2, Int(naturalTransformed.height.rounded()) & ~1)
                renderSize = CGSize(width: w, height: h)
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

            let scale = min(renderSize.width / max(1, naturalTransformed.width), renderSize.height / max(1, naturalTransformed.height))
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

        if let audioPath = spec["audio_path"] as? String, !audioPath.isEmpty, FileManager.default.fileExists(atPath: audioPath) {
            let audioAsset = AVURLAsset(url: URL(fileURLWithPath: audioPath))
            let bgTracks = try await audioAsset.loadTracks(withMediaType: .audio)
            if let bgTrack = bgTracks.first {
                let audioDur = CMTimeGetSeconds(try await audioAsset.load(.duration))
                let audioStart = max(0.0, (spec["audio_start"] as? Double) ?? 0.0)
                let avail = max(0.0, audioDur - audioStart)
                let takeSec = min(CMTimeGetSeconds(cursor), avail)
                if takeSec > 0.05,
                   let compBGM = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) {
                    let range = CMTimeRange(start: CMTime(seconds: audioStart, preferredTimescale: 600),
                                            duration: CMTime(seconds: takeSec, preferredTimescale: 600))
                    try? compBGM.insertTimeRange(range, of: bgTrack, at: .zero)
                }
            }
        }

        let videoComp = AVMutableVideoComposition()
        videoComp.renderSize = renderSize
        videoComp.frameDuration = CMTime(value: 1, timescale: renderFPS)
        videoComp.instructions = instructions

        try FileManager.default.createDirectory(at: outURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        let tempOut = outURL.deletingLastPathComponent().appendingPathComponent("." + UUID().uuidString + ".mp4")
        guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetHighestQuality) else {
            fail("无法初始化 AVFoundation 导出会话")
        }
        exporter.outputURL = tempOut
        exporter.outputFileType = .mp4
        exporter.videoComposition = videoComp
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
            "duration": CMTimeGetSeconds(cursor),
            "width": Int(renderSize.width),
            "height": Int(renderSize.height),
            "clips": addedClips,
            "output": outURL.path
        ])
    }
}
