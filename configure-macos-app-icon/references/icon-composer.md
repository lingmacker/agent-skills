# Icon Composer macOS reference

## Contents

- [Package layout](#package-layout)
- [Minimal macOS manifest](#minimal-macos-manifest)
- [Locate and invoke `ictool`](#locate-and-invoke-ictool)
- [Xcode project wiring](#xcode-project-wiring)
- [Compiled bundle checks](#compiled-bundle-checks)
- [Render the bundled icon](#render-the-bundled-icon)

## Package layout

```text
AppIcon.icon/
├── icon.json
└── Assets/
    ├── 01 Background.svg
    ├── 02 Primary.svg
    └── 03 Foreground.svg
```

`image-name` values are relative to `Assets/`. Groups are ordered foreground first.

## Minimal macOS manifest

Use this as a baseline, then validate it with the installed Xcode toolchain:

```json
{
  "fill": {
    "automatic-gradient": "extended-srgb:0.10588,0.10588,0.10588,1.00000"
  },
  "groups": [
    {
      "blur-material": 0.15,
      "layers": [
        {
          "image-name": "03 Foreground.svg",
          "name": "Foreground"
        }
      ],
      "shadow": {
        "kind": "neutral",
        "opacity": 0.45
      },
      "specular": true,
      "translucency": {
        "enabled": true,
        "value": 0.12
      }
    }
  ],
  "supported-platforms": {
    "squares": ["macOS"]
  }
}
```

Use one group per independently rendered depth plane. Valid observed shadow kinds include `neutral` and `layer-color`. Keep values restrained; the generated icon must remain legible without relying on glass effects.

## Locate and invoke `ictool`

The executable normally lives beside the selected Xcode's Icon Composer app:

```text
<Xcode.app>/Contents/Applications/Icon Composer.app/Contents/Executables/ictool
```

Inspect supported flags with `ictool --help`. A current Xcode 27 invocation is:

```bash
ictool AppIcon.icon \
  --export-image \
  --output-file /tmp/AppIcon-27.png \
  --platform macOS \
  --rendition Default \
  --width 1024 \
  --height 1024 \
  --scale 1 \
  --design-generation 27
```

Repeat with `--design-generation 26`. Validate both because one `.icon` document is used across system design generations.

## Xcode project wiring

Add three records using unused object IDs and the project's existing formatting:

```text
/* PBXFileReference */
F... /* AppIcon.icon */ = {isa = PBXFileReference; lastKnownFileType = folder.iconcomposer.icon; path = AppIcon.icon; sourceTree = "<group>"; };

/* PBXBuildFile */
A... /* AppIcon.icon in Resources */ = {isa = PBXBuildFile; fileRef = F... /* AppIcon.icon */; };

/* PBXResourcesBuildPhase files */
A... /* AppIcon.icon in Resources */,
```

Also add the file reference to the source group that owns the physical `.icon` path. Do not edit the generated product `Info.plist`; keep the target build setting `ASSETCATALOG_COMPILER_APPICON_NAME` aligned with the document name.

## Compiled bundle checks

The application should contain:

```text
Product.app/Contents/Resources/Assets.car
Product.app/Contents/Resources/AppIcon.icns
```

`assetutil --info Assets.car` should report:

- `AssetType: IconImageStack` for `AppIcon`
- one or more `AssetType: Vector` records for source layers
- `LayerHasLightingEffects: true` for Icon Composer-rendered layers
- `AssetType: MultiSized Image` with static sizes through 1024×1024

The built `Info.plist` should resolve `CFBundleIconName` and normally `CFBundleIconFile` to `AppIcon`.

## Render the bundled icon

Use an absolute app path. A relative path can produce the generic application icon and create a false failure.

```swift
import AppKit
import Foundation

let appPath = URL(fileURLWithPath: CommandLine.arguments[1])
    .standardizedFileURL.path
let outputPath = URL(fileURLWithPath: CommandLine.arguments[2])
let icon = NSWorkspace.shared.icon(forFile: appPath)
let size = 512
let bitmap = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: size,
    pixelsHigh: size,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
NSColor.clear.setFill()
NSRect(x: 0, y: 0, width: size, height: size).fill()
icon.draw(in: NSRect(x: 0, y: 0, width: size, height: size))
NSGraphicsContext.restoreGraphicsState()
let png = bitmap.representation(using: .png, properties: [:])!
try png.write(to: outputPath, options: .atomic)
```

Run with `xcrun swift render-icon.swift /absolute/Product.app /tmp/bundled-icon.png`, inspect the result, then delete the probe and output.
