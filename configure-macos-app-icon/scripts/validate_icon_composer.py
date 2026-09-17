#!/usr/bin/env python3
"""Validate a macOS Icon Composer document and an optional built app bundle."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class ValidationError(RuntimeError):
    pass


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def locate_ictool(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("ICTOOL"):
        candidates.append(Path(os.environ["ICTOOL"]))

    selected = run(["/usr/bin/xcode-select", "-p"])
    if selected.returncode == 0:
        developer_dir = Path(selected.stdout.strip())
        candidates.append(
            developer_dir.parent
            / "Applications/Icon Composer.app/Contents/Executables/ictool"
        )

    applications = Path("/Applications")
    if applications.is_dir():
        candidates.extend(
            sorted(
                applications.glob(
                    "Xcode*.app/Contents/Applications/"
                    "Icon Composer.app/Contents/Executables/ictool"
                ),
                reverse=True,
            )
        )

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    raise ValidationError(
        "Unable to locate ictool. Select an Xcode containing Icon Composer, "
        "set ICTOOL, or pass --ictool."
    )


def load_manifest(icon_document: Path) -> tuple[dict[str, Any], int, int]:
    if icon_document.suffix != ".icon" or not icon_document.is_dir():
        raise ValidationError(f"Not an Icon Composer package: {icon_document}")

    manifest_path = icon_document / "icon.json"
    assets_dir = icon_document / "Assets"
    if not manifest_path.is_file():
        raise ValidationError(f"Missing manifest: {manifest_path}")
    if not assets_dir.is_dir():
        raise ValidationError(f"Missing assets directory: {assets_dir}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"Invalid icon.json: {error}") from error

    squares = manifest.get("supported-platforms", {}).get("squares")
    supports_macos = squares == "shared" or (
        isinstance(squares, list) and "macOS" in squares
    )
    if not supports_macos:
        raise ValidationError(
            "supported-platforms.squares must contain macOS or equal shared"
        )

    groups = manifest.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValidationError("icon.json must contain at least one group")

    assets_root = assets_dir.resolve()
    layer_count = 0
    for group_index, group in enumerate(groups, start=1):
        layers = group.get("layers") if isinstance(group, dict) else None
        if not isinstance(layers, list) or not layers:
            raise ValidationError(f"Group {group_index} has no layers")
        for layer_index, layer in enumerate(layers, start=1):
            image_name = layer.get("image-name") if isinstance(layer, dict) else None
            if not isinstance(image_name, str) or not image_name:
                raise ValidationError(
                    f"Group {group_index}, layer {layer_index} has no image-name"
                )
            asset = (assets_dir / image_name).resolve()
            try:
                asset.relative_to(assets_root)
            except ValueError as error:
                raise ValidationError(f"Asset escapes Assets directory: {image_name}") from error
            if not asset.is_file():
                raise ValidationError(f"Missing referenced asset: {asset}")
            layer_count += 1

    return manifest, len(groups), layer_count


def render_generations(
    ictool: Path, icon_document: Path, output_dir: Path
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for generation in (26, 27):
        output = output_dir / f"{icon_document.stem}-generation{generation}.png"
        command = [
            str(ictool),
            str(icon_document),
            "--export-image",
            "--output-file",
            str(output),
            "--platform",
            "macOS",
            "--rendition",
            "Default",
            "--width",
            "1024",
            "--height",
            "1024",
            "--scale",
            "1",
            "--design-generation",
            str(generation),
        ]
        result = run(command)
        if result.returncode != 0:
            details = "\n".join(
                part.strip() for part in (result.stdout, result.stderr) if part.strip()
            )
            raise ValidationError(
                f"ictool failed for design generation {generation}:\n{details}"
            )
        if not output.is_file() or output.stat().st_size == 0:
            raise ValidationError(
                f"ictool produced no generation-{generation} render: {output}"
            )
        outputs.append(output)
    return outputs


def nested_flag(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return value.get(key) is True or any(
            nested_flag(child, key) for child in value.values()
        )
    if isinstance(value, list):
        return any(nested_flag(child, key) for child in value)
    return False


def validate_built_app(app: Path, expected_icon_name: str) -> tuple[str, int]:
    if app.suffix != ".app" or not app.is_dir():
        raise ValidationError(f"Not an application bundle: {app}")

    contents = app / "Contents"
    info_path = contents / "Info.plist"
    resources = contents / "Resources"
    try:
        with info_path.open("rb") as info_file:
            info = plistlib.load(info_file)
    except (OSError, plistlib.InvalidFileException) as error:
        raise ValidationError(f"Unable to read built Info.plist: {error}") from error

    icon_name = info.get("CFBundleIconName")
    if icon_name != expected_icon_name:
        raise ValidationError(
            f"CFBundleIconName is {icon_name!r}; expected {expected_icon_name!r}"
        )

    icon_file = info.get("CFBundleIconFile", expected_icon_name)
    if not isinstance(icon_file, str) or Path(icon_file).stem != expected_icon_name:
        raise ValidationError(
            f"CFBundleIconFile is {icon_file!r}; expected {expected_icon_name!r}"
        )

    assets_car = resources / "Assets.car"
    static_icon = resources / f"{expected_icon_name}.icns"
    if not assets_car.is_file():
        raise ValidationError(f"Missing compiled asset catalog: {assets_car}")
    if not static_icon.is_file() or static_icon.stat().st_size == 0:
        raise ValidationError(f"Missing static icon representation: {static_icon}")

    assetutil = shutil.which("assetutil") or "/usr/bin/assetutil"
    result = run([assetutil, "--info", str(assets_car)])
    if result.returncode != 0:
        raise ValidationError(f"assetutil failed:\n{result.stderr.strip()}")
    try:
        records = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValidationError(f"assetutil returned invalid JSON: {error}") from error

    matching_stacks = [
        record
        for record in records
        if record.get("AssetType") == "IconImageStack"
        and record.get("Name") == expected_icon_name
    ]
    if not matching_stacks:
        raise ValidationError(f"No IconImageStack named {expected_icon_name} in Assets.car")

    vector_prefix = f"{expected_icon_name}_Assets/"
    vectors = [
        record
        for record in records
        if record.get("AssetType") == "Vector"
        and str(record.get("Name", "")).startswith(vector_prefix)
    ]
    if not vectors:
        raise ValidationError(f"No Icon Composer vectors for {expected_icon_name}")

    multisized = any(
        record.get("AssetType") == "MultiSized Image"
        and record.get("Name") == expected_icon_name
        for record in records
    )
    if not multisized:
        raise ValidationError(f"No MultiSized Image named {expected_icon_name}")

    appearances = {
        record.get("Appearance")
        for record in matching_stacks
        if isinstance(record.get("Appearance"), str)
    }
    required_appearances = {
        "NSAppearanceNameAqua",
        "NSAppearanceNameDarkAqua",
        "ISAppearanceTintable",
    }
    missing_appearances = required_appearances - appearances
    if missing_appearances:
        raise ValidationError(
            "IconImageStack is missing appearances: "
            + ", ".join(sorted(missing_appearances))
        )

    if not nested_flag(records, "LayerHasLightingEffects"):
        raise ValidationError("Compiled icon layers do not expose lighting effects")

    return icon_name, len(vectors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("icon_document", type=Path, help="Path to AppIcon.icon")
    parser.add_argument("--app", type=Path, help="Optional built Product.app")
    parser.add_argument("--ictool", help="Explicit path to ictool")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for generation renders; defaults to a new temporary directory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        icon_document = args.icon_document.resolve()
        _, group_count, layer_count = load_manifest(icon_document)
        print(f"PASS manifest: {group_count} groups, {layer_count} referenced layers")

        ictool = locate_ictool(args.ictool)
        output_dir = (
            args.output_dir.resolve()
            if args.output_dir
            else Path(tempfile.mkdtemp(prefix="macos-icon-validation-"))
        )
        renders = render_generations(ictool, icon_document, output_dir)
        print(f"PASS ictool: {ictool}")
        for render in renders:
            print(f"PASS render: {render}")

        if args.app:
            icon_name, vector_count = validate_built_app(
                args.app.resolve(), icon_document.stem
            )
            print(
                f"PASS bundle: {icon_name} IconImageStack, "
                f"{vector_count} vectors, static .icns"
            )

        print(f"Inspect renders, then remove: {output_dir}")
        return 0
    except ValidationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
