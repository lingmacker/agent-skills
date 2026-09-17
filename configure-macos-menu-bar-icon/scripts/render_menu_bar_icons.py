#!/usr/bin/env python3
import argparse
import io
import json
from pathlib import Path

import resvg_py
from PIL import Image


POINT_SIZE = 18


def load_rgba(source: Path) -> Image.Image:
    if source.suffix.lower() == ".svg":
        png = resvg_py.svg_to_bytes(svg_string=source.read_text(encoding="utf-8"))
        return Image.open(io.BytesIO(png)).convert("RGBA")
    return Image.open(source).convert("RGBA")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create fixed 18pt macOS menu bar PNG assets with transparency."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output_imageset", type=Path)
    args = parser.parse_args()

    if not args.source.is_file():
        parser.error(f"source image not found: {args.source}")
    if args.output_imageset.suffix != ".imageset":
        parser.error(f"output path must end in .imageset: {args.output_imageset}")

    master = load_rgba(args.source)
    args.output_imageset.mkdir(parents=True, exist_ok=True)

    for old_asset in args.output_imageset.glob("menu_*.png"):
        old_asset.unlink()
    for old_asset in args.output_imageset.glob("menu_*.svg"):
        old_asset.unlink()

    images = []
    for scale in (1, 2, 3):
        pixels = POINT_SIZE * scale
        suffix = "" if scale == 1 else f"@{scale}x"
        filename = f"menu_{POINT_SIZE}{suffix}.png"
        output = master.resize((pixels, pixels), Image.Resampling.LANCZOS)
        output.save(args.output_imageset / filename, format="PNG")
        images.append(
            {
                "filename": filename,
                "idiom": "universal",
                "scale": f"{scale}x",
            }
        )

    contents = {
        "images": images,
        "info": {"author": "xcode", "version": 1},
        "properties": {"template-rendering-intent": "template"},
    }
    (args.output_imageset / "Contents.json").write_text(
        json.dumps(contents, indent=2) + "\n", encoding="utf-8"
    )

    sizes = ", ".join(f"{POINT_SIZE * scale}px" for scale in (1, 2, 3))
    print(f"Created {args.output_imageset} at 18pt ({sizes}).")


if __name__ == "__main__":
    main()
