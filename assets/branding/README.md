# GC Labs app identity

使用内置 image_gen 生成；随后仅用 sips/iconutil 导出原生图标尺寸和格式，没有使用外部付费API。

- gc-labs-logo-master.png：透明圆角外部、完整不透明深色底板的最终源图。
- AppIcon.icns：16–1024像素原生Mac图标，构建时安装到Resources并配置CFBundleIconFile。
- ../../web/logo.png：256像素应用内标志与favicon。

## Initial prompt

Use case: logo-brand. Asset type: final macOS application icon for GC Labs, an independent cloud GPU creative workstation. Create ONE polished square icon, not a presentation or mockup. A bold sculptural continuous loop subtly combines the letters G and C with a compact compute-core shape; intelligent, calm, technical, instantly recognizable at 32 pixels. Large simple central mark, strong silhouette, carefully balanced negative space. Follow the existing app's charcoal and soft lavender visual identity with restrained mint light as a small accent. Premium satin material and subtle depth, not glossy gaming aesthetics. Full-bleed charcoal square tile with a softly rounded-square face, centered straight-on, no perspective. No typography, no wordmark, no tiny circuit details, no cloud clip art, no laboratory flask, no Google or Colab branding, no watermark, no scene, no surrounding mockup. Crisp intentional edges, balanced macOS utility icon design, 1024x1024 composition.

## Alpha preparation prompt

Prepare this exact GC Labs icon for native macOS use. Keep the entire rounded charcoal tile, lavender interlocking GC symbol and mint compute core unchanged in design, shape, color, material and placement. Remove ONLY the black surrounding outside the rounded-square tile so those outer corner regions become genuinely transparent. Preserve the charcoal tile itself as fully opaque. No redesign, no text, no new objects, no shadow outside the tile. Square app-icon asset with clean alpha edges, icon centered and almost filling its square canvas.
