// Local macOS OCR; requires Apple's Swift runtime and Vision, no network.
import Foundation
import Vision
import ImageIO

var images: [[String: Any]] = []
var failed = false
for path in CommandLine.arguments.dropFirst() {
    do {
        let url = URL(fileURLWithPath: path)
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            throw NSError(domain: "ClassCheckOCR", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "Image cannot be decoded"])
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = true
        try VNImageRequestHandler(cgImage: image).perform([request])
        let lines = (request.results ?? []).compactMap { observation -> [String: Any]? in
            guard let candidate = observation.topCandidates(1).first else { return nil }
            return ["text": candidate.string, "confidence": candidate.confidence]
        }
        images.append(["path": url.path, "text": lines.compactMap { $0["text"] as? String }.joined(separator: "\n"),
                       "lines": lines, "scope": "screenshot_only"])
    } catch {
        failed = true
        images.append(["path": path, "text": "", "error": error.localizedDescription])
    }
}
if CommandLine.arguments.count < 2 {
    FileHandle.standardError.write(Data("Usage: swift ocr-image.swift IMAGE [IMAGE...]\n".utf8))
    exit(2)
}
let output = try JSONSerialization.data(withJSONObject: ["images": images], options: [.prettyPrinted, .sortedKeys])
FileHandle.standardOutput.write(output)
FileHandle.standardOutput.write(Data("\n".utf8))
exit(failed ? 1 : 0)
