import Foundation
import Vision
import ImageIO
var output: [[String:Any]] = []
for p in CommandLine.arguments.dropFirst() {
 do {
  guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath:p) as CFURL, nil), let props = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString:Any] else { throw NSError(domain:"ImageRead",code:1) }
  let o = CGImagePropertyOrientation(rawValue:(props[kCGImagePropertyOrientation] as? UInt32) ?? 1) ?? .up
  let request = VNDetectFaceRectanglesRequest()
  try VNImageRequestHandler(url:URL(fileURLWithPath:p), orientation:o, options:[:]).perform([request])
  let faces = (request.results ?? []).map { ["confidence":Double($0.confidence),"box":[$0.boundingBox.origin.x,$0.boundingBox.origin.y,$0.boundingBox.width,$0.boundingBox.height]] as [String:Any] }
  output.append(["path":p,"faces":faces])
 } catch { fputs("Face detection failed: \(p): \(error)\n",stderr);exit(1) }
}
let data=try JSONSerialization.data(withJSONObject:output,options:[.prettyPrinted,.sortedKeys])
FileHandle.standardOutput.write(data)
