// Auto-fix exposure, contrast, white balance and shadows on JPGs with Core Image's
// auto-adjust filters (the same engine as Photos' "Auto Enhance"). Originals are never touched.
//
//   swift tools/auto-enhance.swift <photo folder> [output folder]
//
// Output defaults to <photo folder>/enhanced, files named DSCF0001_auto.jpg with EXIF kept.
import CoreImage
import Foundation
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
guard args.count >= 2 else { print("usage: swift auto-enhance.swift <photo folder> [output folder]"); exit(1) }
let src = URL(fileURLWithPath: args[1])
let out = args.count > 2 ? URL(fileURLWithPath: args[2]) : src.appendingPathComponent("enhanced")
try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)

let ctx = CIContext()
let files = try FileManager.default.contentsOfDirectory(at: src, includingPropertiesForKeys: nil)
    .filter { ["jpg", "jpeg"].contains($0.pathExtension.lowercased()) && !$0.lastPathComponent.hasPrefix("._") }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }

var done = 0
for f in files {
    let dst = out.appendingPathComponent(f.deletingPathExtension().lastPathComponent + "_auto.jpg")
    if FileManager.default.fileExists(atPath: dst.path) { continue }
    guard let source = CGImageSourceCreateWithURL(f as CFURL, nil),
          var img = CIImage(contentsOf: f, options: [.applyOrientationProperty: true]) else { print("skip \(f.lastPathComponent)"); continue }

    for filter in img.autoAdjustmentFilters(options: [.redEye: false]) {
        filter.setValue(img, forKey: kCIInputImageKey)
        img = filter.outputImage ?? img
    }

    // keep EXIF/GPS, but orientation is already baked into the pixels
    var props = (CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any]) ?? [:]
    props[kCGImagePropertyOrientation] = 1
    if var tiff = props[kCGImagePropertyTIFFDictionary] as? [CFString: Any] {
        tiff[kCGImagePropertyTIFFOrientation] = 1; props[kCGImagePropertyTIFFDictionary] = tiff
    }
    props[kCGImageDestinationLossyCompressionQuality] = 0.92

    guard let cg = ctx.createCGImage(img, from: img.extent, format: .RGBA8, colorSpace: CGColorSpace(name: CGColorSpace.sRGB)),
          let dest = CGImageDestinationCreateWithURL(dst as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else { continue }
    CGImageDestinationAddImage(dest, cg, props as CFDictionary)
    CGImageDestinationFinalize(dest)
    done += 1
    print("\(done)/\(files.count) \(dst.lastPathComponent)")
}
print("Done: \(done) enhanced → \(out.path)")
