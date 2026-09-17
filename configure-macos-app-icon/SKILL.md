---
name: configure-macos-app-icon
description: Create, replace, migrate, and verify macOS application icons using Xcode Icon Composer `.icon` documents, layered SVG or PNG artwork, Liquid Glass effects, and Xcode app targets. Use when Codex must adapt an app icon to macOS 26 or 27, convert existing artwork into an Icon Composer package, wire `AppIcon.icon` into an `.xcodeproj`, preserve a classic app-icon fallback, diagnose app-icon build or cache problems, or verify `Assets.car`, `AppIcon.icns`, bundle metadata, and Finder rendering. Do not use for menu bar/status-item icons.
---

# Configure macOS App Icon

Produce a native Icon Composer app icon, integrate it into the macOS application target, and prove that the built bundle contains both the dynamic icon stack and static representations.

## Workflow

### 1. Inspect before editing

- Locate the macOS application target, `.xcodeproj` or project generator, current icon assets, build command, deployment target, and selected Xcode.
- Inspect available artwork dimensions and alpha rather than guessing. Prefer the highest-quality SVG or 1024×1024-or-larger source.
- Read `references/icon-composer.md` before hand-authoring `icon.json`, changing `project.pbxproj`, or diagnosing a compiled icon.
- Preserve the current icon until the new Icon Composer document renders successfully.

### 2. Prepare native layers

- Use a 1024×1024 canvas or SVG `viewBox="0 0 1024 1024"` for every layer.
- Split artwork by semantic depth: background details, primary object, and foreground badge or lens. Keep a single layer when the mark is genuinely flat; do not invent depth.
- Prefer simple vector paths. Avoid SVG filters, masks, baked glass, baked platform corner masks, and baked outer shadows; Icon Composer supplies platform shape, materials, lighting, and shadows.
- Keep essential details away from the outer edge and inspect the result at 16, 32, 64, 128, and 1024 px.
- Create `AppIcon.icon/Assets/` and place only referenced source layers inside it.

### 3. Create the Icon Composer document

- Prefer saving through the installed Icon Composer app when interactive editing is available.
- When hand-authoring, start from the minimal manifest in `references/icon-composer.md`; treat undocumented keys as Xcode-version-specific.
- Set `supported-platforms.squares` to `macOS`.
- List groups from foreground to background. Use separate groups when layers need different blur, translucency, specular, or shadow behavior.
- Use an automatic or solid fill for the system-managed square background.
- Apply Liquid Glass effects with restraint. Preserve silhouette and contrast before adding translucency.

### 4. Validate the document independently

Run:

```bash
python3 <skill-dir>/scripts/validate_icon_composer.py path/to/AppIcon.icon
```

Require successful generation-26 and generation-27 renders. Inspect both rendered images when the script prints their temporary paths; do not accept a successful exit alone when visual quality is part of the request.

If the installed Icon Composer tool does not support generation 27, report the exact toolchain limitation. Do not fake a generation-27 result.

### 5. Wire the app target

- Add `AppIcon.icon` as a `folder.iconcomposer.icon` file reference and include it in the application target's Resources build phase.
- Use the repository's project generator when one owns the Xcode project. Otherwise patch `project.pbxproj` using its existing object-ID and formatting conventions.
- Keep `ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon` or the repository's established icon name.
- Keep an existing complete `AppIcon.appiconset` as a classic fallback unless the project explicitly targets only toolchains that consume `.icon` documents. Xcode 27 should select the matching `.icon` document for the modern icon stack.
- Never add the app icon to an extension target unless that extension is itself an application.

### 6. Build and verify the bundle

- Run the repository's real application build, not only `ictool`.
- Check build logs for `AppIcon.icon` in `actool` input and fail on icon-related warnings or errors.
- Run the validator again with the built app:

```bash
python3 <skill-dir>/scripts/validate_icon_composer.py \
  path/to/AppIcon.icon \
  --app path/to/Product.app
```

Require all of these invariants:

- `CFBundleIconName` resolves to the intended icon name.
- `Assets.car` contains an `IconImageStack`, vector layers, and a `MultiSized Image` for that name.
- The stack exposes Aqua, Dark Aqua, and tintable appearances when produced by the current toolchain.
- `AppIcon.icns` exists as the static bundle representation.

Render the built app's icon through `NSWorkspace.shared.icon(forFile:)` using an absolute application path, then inspect the PNG. A direct source render does not prove bundle integration.

### 7. Handle stale installed icons only when observed

- Rebuild and replace the installed application first.
- Reset Launch Services or restart icon-owning processes only after confirming that the bundle is correct but Finder still shows stale artwork.
- Do not routinely kill Dock, Finder, or shared cache services.

### 8. Clean and report

- Remove temporary generation renders, extracted iconsets, and one-off Swift probes.
- Keep the `.icon` document, its referenced layers, project wiring, and any intentionally retained fallback catalog.
- Report exact changed paths, build result, icon-stack evidence, static fallback evidence, and the visual inspection result.

## Resources

- `references/icon-composer.md`: baseline manifest, Xcode wiring, commands, and bundled-icon rendering probe.
- `scripts/validate_icon_composer.py`: deterministic package, render, and built-bundle validation.
