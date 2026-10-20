"""One-off script: draws the Simple-Cabin app icon and exports every
size/format the platform installers need. Not part of the app itself and
not run automatically — re-run manually if the icon design ever changes.

Usage: venv/bin/python packaging/icons/generate_icon.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = Path(__file__).parent
APP_RESOURCES = OUT_DIR.parent.parent / "src" / "simple_cabin" / "gui" / "resources"
SIZE = 1024

# A log cabin under a night sky with a lit window and a crescent moon, on
# a deep forest-green tile, beside Simple-Photos' indigo and Simple-Ripper's teal.
TILE_TOP = (30, 70, 60, 255)
TILE_BOTTOM = (14, 38, 34, 255)
LOG = (150, 94, 52, 255)
LOG_DARK = (100, 60, 32, 255)
ROOF = (70, 44, 36, 255)
GLOW = (255, 190, 90, 255)
MOON = (246, 238, 210, 255)
PINE = (22, 58, 40, 255)


def draw_icon() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    tile = Image.new("RGBA", (SIZE, SIZE))
    td = ImageDraw.Draw(tile)
    for y in range(SIZE):
        t = y / SIZE
        td.line([(0, y), (SIZE, y)], fill=tuple(int(TILE_TOP[i] + (TILE_BOTTOM[i] - TILE_TOP[i]) * t) for i in range(3)) + (255,))
    mask = Image.new("L", (SIZE, SIZE), 0)
    margin = SIZE * 0.06
    ImageDraw.Draw(mask).rounded_rectangle([margin, margin, SIZE - margin, SIZE - margin], radius=SIZE * 0.22, fill=255)
    scene = tile
    img = scene  # drawn on the full square, then cut to the rounded tile at the end
    d = ImageDraw.Draw(img)
    s = SIZE / 100

    # crescent moon
    crescent = Image.new("L", (SIZE, SIZE), 0)
    cd = ImageDraw.Draw(crescent)
    cd.ellipse([66 * s, 16 * s, 82 * s, 32 * s], fill=255)
    cd.ellipse([71 * s, 13 * s, 87 * s, 29 * s], fill=0)
    img.paste(MOON, (0, 0), crescent)
    # pines either side
    for x, top, w in ((20, 30, 15), (84, 38, 12)):
        for k in range(4):
            y0 = top + k * 9
            d.polygon([(x * s, y0 * s), ((x - w * (0.4 + k * 0.2)) * s, (y0 + 16) * s), ((x + w * (0.4 + k * 0.2)) * s, (y0 + 16) * s)], fill=PINE)
    # cabin
    d.polygon([(24 * s, 52 * s), (50 * s, 30 * s), (76 * s, 52 * s)], fill=ROOF)
    d.rectangle([30 * s, 50 * s, 70 * s, 78 * s], fill=LOG)
    for i in range(6):
        y = 50 + i * 4.7
        d.line([(30 * s, y * s), (70 * s, y * s)], fill=LOG_DARK, width=max(1, int(0.8 * s)))
    d.rectangle([62 * s, 32 * s, 68 * s, 44 * s], fill=(120, 116, 110, 255))
    # glowing window and door
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([28 * s, 46 * s, 56 * s, 74 * s], fill=(255, 170, 70, 120))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(SIZE * 0.03)))
    d = ImageDraw.Draw(img)
    d.rectangle([35 * s, 56 * s, 47 * s, 67 * s], fill=GLOW)
    d.line([(41 * s, 56 * s), (41 * s, 67 * s)], fill=LOG_DARK, width=max(1, int(1 * s)))
    d.line([(35 * s, 61.5 * s), (47 * s, 61.5 * s)], fill=LOG_DARK, width=max(1, int(1 * s)))
    d.rectangle([54 * s, 60 * s, 63 * s, 78 * s], fill=LOG_DARK)
    # ground
    d.rectangle([0, 78 * s, SIZE, SIZE], fill=(26, 58, 40, 255))
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def main() -> None:
    icon = draw_icon()
    master_png = OUT_DIR / "icon.png"
    icon.save(master_png)
    print(f"wrote {master_png}")

    APP_RESOURCES.mkdir(parents=True, exist_ok=True)
    icon.resize((256, 256), Image.LANCZOS).save(APP_RESOURCES / "icon.png")
    print(f"wrote {APP_RESOURCES / 'icon.png'}")

    # Windows .ico (multi-resolution)
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_path = OUT_DIR / "icon.ico"
    icon.save(ico_path, sizes=[(s, s) for s in ico_sizes])
    print(f"wrote {ico_path}")

    # Linux: a few common hicolor sizes as plain PNGs.
    for s in (16, 32, 48, 64, 128, 256, 512):
        icon.resize((s, s), Image.LANCZOS).save(OUT_DIR / f"icon_{s}.png")
    print("wrote icon_16..512.png")

    # macOS .icns: iconutil on a Mac; elsewhere Pillow's own ICNS writer is
    # good enough to commit, so CI on macOS always has a file to use.
    if sys.platform == "darwin" and shutil.which("iconutil"):
        iconset = OUT_DIR / "icon.iconset"
        iconset.mkdir(exist_ok=True)
        for s in (16, 32, 128, 256, 512):
            icon.resize((s, s), Image.LANCZOS).save(iconset / f"icon_{s}x{s}.png")
            icon.resize((s * 2, s * 2), Image.LANCZOS).save(iconset / f"icon_{s}x{s}@2x.png")
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(OUT_DIR / "icon.icns")],
            check=True,
        )
        for f in iconset.iterdir():
            f.unlink()
        iconset.rmdir()
    else:
        icon.save(OUT_DIR / "icon.icns")
    print(f"wrote {OUT_DIR / 'icon.icns'}")


if __name__ == "__main__":
    main()
