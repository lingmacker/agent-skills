---
name: configure-macos-menu-bar-icon
description: Configure a custom image as a native 18×18 pt macOS menu bar icon in SwiftUI or AppKit projects. Use when Codex must replace a MenuBarExtra or NSStatusItem symbol/image, convert an SVG or raster source into fixed transparent 18/36/54 px PNG template assets for 1x/2x/3x, create or repair an Xcode imageset, or diagnose a menu bar icon that is blurry, oversized, tinted incorrectly, or confused with the application icon.
---

# Configure macOS Menu Bar Icon

## Workflow

1. Inspect the repository and its local instructions.
2. Locate the real menu bar entry point before editing assets:
   - SwiftUI: search for `MenuBarExtra`.
   - AppKit: search for `NSStatusItem`, `statusItem`, or `button.image`.
3. Locate the target's `.xcassets` directory and confirm it is compiled by the app target.
4. Do not modify `AppIcon.appiconset`, Icon Composer resources, `CFBundleIcon`, or `ASSETCATALOG_COMPILER_APPICON_NAME` unless the user explicitly asks for the application icon.
5. Prepare the source:
   - Preserve every transparent and partially transparent pixel from the source.
   - Never add a white, black, or colored background.
   - Never flatten or composite the source before resizing.
   - Rasterize SVG sources with the bundled Python renderer (`resvg_py`), never Quick Look.
   - Use solid monochrome artwork for a template image.
   - Keep all meaningful artwork inside the canvas.
   - If editing SVG strokes, increase the inset by half the stroke-width increase so the outer edge is not clipped.
6. Generate the menu bar imageset with:

   ```bash
   <skill-dir>/scripts/make_menu_bar_imageset.sh <source.svg-or-image> <path/to/Assets.xcassets/MenuBarIcon.imageset>
   ```

   Always use 18 points. The wrapper runs `render_menu_bar_icons.py` with `resvg_py` and Pillow. It first uses the system `python3` when both dependencies are available. Otherwise, it creates `scripts/.venv` and installs the pinned dependencies from `scripts/requirements.txt`; the first such run requires package-index access. For both SVG and raster input, it creates `menu_18.png`, `menu_18@2x.png`, and `menu_18@3x.png` at 18×18, 36×36, and 54×54 pixels and writes a template `Contents.json`.
7. Wire the image into the menu bar UI.

## SwiftUI

Use the image at its intrinsic 18-point size from the 1x/2x/3x imageset:

```swift
MenuBarExtra {
    MenuBarContent()
} label: {
    Image("MenuBarIcon")
}
.menuBarExtraStyle(.menu)
```

Use the asset without image modifiers. The imageset already supplies the template-rendering intent and intrinsic 18-point size. Replace an existing `systemImage:` initializer rather than creating a second menu bar item.

## AppKit

Load the asset directly:

```swift
statusItem.button?.image = NSImage(named: "MenuBarIcon")
```

Reuse the existing `NSStatusItem`. Do not assign `image.size` or `image.isTemplate`; the imageset already supplies both properties.

## Validation

1. Confirm the imageset contains:
   - `menu_18.png` at 18×18
   - `menu_18@2x.png` at 36×36
   - `menu_18@3x.png` at 54×54

2. Inspect at least the 2x or 3x PNG visually for clipping and legibility.
3. Confirm the menu bar image has no manual sizing or template-rendering modifiers in SwiftUI or AppKit.
4. Build the relevant target without signing when practical.
5. Verify the diff contains no application-icon changes.
6. Report the source format, intrinsic 18-point logical size, generated 18/36/54 pixel sizes, and build result.

Run the wrapper instead of invoking the Python renderer directly. If dependency installation needs network access in the current environment, request approval and rerun the wrapper. Do not vendor Python packages, invoke `uv`, or fall back to Quick Look.
