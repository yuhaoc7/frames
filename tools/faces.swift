import Vision; import AppKit
for p in CommandLine.arguments.dropFirst() {
  let r = VNDetectFaceRectanglesRequest()
  try? VNImageRequestHandler(url: URL(fileURLWithPath: p)).perform([r])
  if let n = r.results?.filter({ $0.confidence > 0.6 }).count, n > 0 { print(URL(fileURLWithPath: p).lastPathComponent) }
}
