// Deterministic size/mask packaging only; the selected raster artwork is never redrawn.
import AppKit
import ImageIO
let root=URL(fileURLWithPath:CommandLine.arguments[1])
let productData=try Data(contentsOf:root.appendingPathComponent("assets/branding/product.json"))
let product=try JSONSerialization.jsonObject(with:productData) as! [String:Any]
let sourceURL=root.appendingPathComponent(product["icon_master"] as! String)
guard let src=CGImageSourceCreateWithURL(sourceURL as CFURL,nil),let image=CGImageSourceCreateImageAtIndex(src,0,nil) else {fatalError("Cannot read product artwork")}
func render(_ size:Int,_ mac:Bool)->Data {
 let context=CGContext(data:nil,width:size,height:size,bitsPerComponent:8,bytesPerRow:size*4,space:CGColorSpace(name:CGColorSpace.sRGB)!,bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue|CGBitmapInfo.byteOrder32Big.rawValue)!
 context.clear(CGRect(x:0,y:0,width:size,height:size))
 if !mac {context.setFillColor(CGColor(srgbRed:0.976,green:0.957,blue:0.937,alpha:1));context.fill(CGRect(x:0,y:0,width:size,height:size))}
 let inset=mac ? CGFloat(size)*0.10:0
 let rect=CGRect(x:inset,y:inset,width:CGFloat(size)-inset*2,height:CGFloat(size)-inset*2)
 context.addPath(CGPath(roundedRect:rect,cornerWidth:rect.width*0.30,cornerHeight:rect.height*0.30,transform:nil));context.clip();context.interpolationQuality = .high;context.draw(image,in:rect)
 let cg=context.makeImage()!
 if mac {return NSBitmapImageRep(cgImage:cg).representation(using:.png,properties:[:])!}
 let rgb=NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:size,pixelsHigh:size,bitsPerSample:8,samplesPerPixel:3,hasAlpha:false,isPlanar:false,colorSpaceName:.deviceRGB,bytesPerRow:size*3,bitsPerPixel:24)!
 let input=context.data!.assumingMemoryBound(to:UInt8.self),output=rgb.bitmapData!
 for y in 0..<size {for x in 0..<size {let a=(y*size+x)*4,b=y*rgb.bytesPerRow+x*3;output[b]=input[a];output[b+1]=input[a+1];output[b+2]=input[a+2]}}
 return rgb.representation(using:.png,properties:[:])!
}
let dir=root.appendingPathComponent("assets/branding/CineHarbor.iconset")
try FileManager.default.createDirectory(at:dir,withIntermediateDirectories:true)
for size in [16,32,128,256,512] {
 try render(size,true).write(to:dir.appendingPathComponent("icon_\(size)x\(size).png"))
 try render(size*2,true).write(to:dir.appendingPathComponent("icon_\(size)x\(size)@2x.png"))
}
try render(1024,false).write(to:root.appendingPathComponent("assets/branding/AppStore-Icon-1024x1024.png"))
try render(256,true).write(to:root.appendingPathComponent("web/logo.png"))
print("Packaged product icon; artwork and publisher marks preserved")
