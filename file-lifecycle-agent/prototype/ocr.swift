import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count == 2 else { exit(2) }
do {
    let url = URL(fileURLWithPath: CommandLine.arguments[1])
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["ko-KR", "en-US"]
    request.usesLanguageCorrection = true
    try VNImageRequestHandler(url: url).perform([request])
    let rows: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let b = observation.boundingBox
        return ["text": candidate.string, "confidence": candidate.confidence,
                "bbox": [b.origin.x, b.origin.y, b.width, b.height]]
    }
    let data = try JSONSerialization.data(withJSONObject: rows, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)
} catch {
    fputs("OCR failed: \(error)\n", stderr)
    exit(1)
}
