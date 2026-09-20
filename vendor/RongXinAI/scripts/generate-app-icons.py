#!/usr/bin/env python3
"""Generate the cross-platform ZhiYuan application icon set.

Requires Pillow. Generated PNG, ICO, and ICNS files are committed so
packaging jobs do not need to regenerate them.

Sources (P1-4): the ``src/renderer/assets/brand/xiongbao/`` directory holds
the dedicated ``logo-icon.png`` (master 1024px+) and ``mascot.png``. The
script composites them on the same cool-white gradient the previous brand
mark used so the in-app and installer visuals stay aligned.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "src" / "renderer" / "assets" / "brand" / "xiongbao"
LEGACY_SOURCE = PROJECT_ROOT / "public" / "zhiyuan-logo-light-1600.png"
PNG_DIR = PROJECT_ROOT / "build" / "icons" / "png"
WINDOWS_ICON = PROJECT_ROOT / "build" / "icons" / "win" / "icon.ico"
MAC_ICON = PROJECT_ROOT / "build" / "icons" / "mac" / "icon.icns"
MASTER_ICON = PROJECT_ROOT / "build" / "icons" / "app-icon-master.png"

CANVAS_SIZE = 1024
ICON_BOUNDS = (64, 64, 960, 960)
ICON_RADIUS = 220
WINDOWS_ICON_BOUNDS = ICON_BOUNDS
WINDOWS_ICON_RADIUS = ICON_RADIUS
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = ((16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256))


def _resolve_source(source_dir: Path) -> tuple[Path | None, Path | None]:
    """Pick the icon and mascot source files for the master canvas."""
    candidates = [
        source_dir / "logo-icon-original.jpg",
        source_dir / "logo-icon.png",
        source_dir / "logo-icon@2x.png",
        LEGACY_SOURCE,
    ]
    icon = next((p for p in candidates if p.exists()), None)
    mascot = source_dir / "mascot.png" if (source_dir / "mascot.png").exists() else None
    return icon, mascot


def make_gradient() -> Image.Image:
    top = (255, 255, 255)
    bottom = (237, 245, 255)
    gradient = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    pixels = gradient.load()

    for y in range(CANVAS_SIZE):
        vertical = y / (CANVAS_SIZE - 1)
        for x in range(CANVAS_SIZE):
            horizontal = x / (CANVAS_SIZE - 1)
            blend = min(1.0, vertical * 0.76 + horizontal * 0.24)
            base = tuple(
                round(top[channel] * (1 - blend) + bottom[channel] * blend)
                for channel in range(3)
            )

            glow_x = (x - 760) / 540
            glow_y = (y - 800) / 500
            glow = max(0.0, 1.0 - (glow_x * glow_x + glow_y * glow_y))
            accent = (108, 165, 255)
            accent_strength = glow * 0.14
            pixels[x, y] = tuple(
                round(base[channel] * (1 - accent_strength) + accent[channel] * accent_strength)
                for channel in range(3)
            ) + (255,)

    return gradient


def _place_logo(canvas: Image.Image, logo: Image.Image) -> None:
    alpha = logo.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        # JPG sources have no alpha; fall back to the full image.
        wordmark = logo.convert("RGBA")
    else:
        wordmark = logo.crop(bbox)

    logo_width = 748
    if wordmark.width == 0:
        return
    logo_height = round(wordmark.height * logo_width / wordmark.width)
    wordmark = wordmark.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
    position = ((CANVAS_SIZE - logo_width) // 2, (CANVAS_SIZE - logo_height) // 2 + 8)
    canvas.alpha_composite(wordmark, position)


def make_master_icon(
    bounds: tuple[int, int, int, int],
    radius: int,
    source_logo: Path,
) -> Image.Image:
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    mask = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(bounds, radius=radius, fill=255)

    canvas.alpha_composite(Image.composite(make_gradient(), Image.new("RGBA", canvas.size), mask))

    border = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        bounds,
        radius=radius,
        outline=(208, 213, 221, 210),
        width=12,
    )
    canvas.alpha_composite(border)

    _place_logo(canvas, Image.open(source_logo).convert("RGBA"))
    return canvas


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate ZhiYuan app icons.")
    ap.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory holding logo-icon.png / mascot.png (P1-4 default).",
    )
    args = ap.parse_args()

    icon_path, _mascot_path = _resolve_source(args.source_dir)
    if icon_path is None:
        raise SystemExit(
            f"No icon source found under {args.source_dir} or {LEGACY_SOURCE.parent}; "
            "provide --source-dir or place a logo-icon.png / zhiyuan-logo-light-1600.png."
        )

    PNG_DIR.mkdir(parents=True, exist_ok=True)
    WINDOWS_ICON.parent.mkdir(parents=True, exist_ok=True)
    MAC_ICON.parent.mkdir(parents=True, exist_ok=True)

    master = make_master_icon(ICON_BOUNDS, ICON_RADIUS, icon_path)
    windows_master = make_master_icon(WINDOWS_ICON_BOUNDS, WINDOWS_ICON_RADIUS, icon_path)
    master.save(MASTER_ICON, optimize=True)

    for size in PNG_SIZES:
        resized = master.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(PNG_DIR / f"{size}x{size}.png", optimize=True)

    windows_master.save(WINDOWS_ICON, format="ICO", sizes=ICO_SIZES)
    master.save(MAC_ICON, format="ICNS")

    print(f"Generated application icon master: {MASTER_ICON}")
    print(f"Generated Windows icon: {WINDOWS_ICON}")
    print(f"Generated macOS icon: {MAC_ICON}")
    print(f"Source: {icon_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
