"""Generate home-screen install icons (FEATURES.md F9). Run manually:

    python scripts/make_icons.py

Writes app/static/icons/icon-192.png, icon-512.png, apple-touch-icon.png
(180px) — a dark rounded-square background with a stylized open book in the
theme's accent amber. Pillow only, no other dependencies. Outputs are
committed; re-run and re-commit if the design changes.
"""

from pathlib import Path

from PIL import Image, ImageDraw

BG = (20, 18, 16)  # --color-bg (dark theme)
ACCENT = (217, 164, 65)  # --color-accent

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"

SIZES = {
    "icon-192.png": 192,
    "icon-512.png": 512,
    "apple-touch-icon.png": 180,
}


def _make_icon(size: int) -> Image.Image:
    corner = round(size * 0.18)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=corner, fill=255)

    canvas = Image.new("RGB", (size, size), (0, 0, 0))
    bg = Image.new("RGB", (size, size), BG)
    canvas.paste(bg, (0, 0), mask)
    draw = ImageDraw.Draw(canvas)

    cx, cy = size / 2, size / 2
    half_w = size * 0.30
    half_h = size * 0.19
    spine_gap = size * 0.015
    stroke = max(2, round(size * 0.022))

    draw.polygon(
        [
            (cx - spine_gap, cy - half_h),
            (cx - spine_gap - half_w, cy - half_h * 0.65),
            (cx - spine_gap - half_w, cy + half_h * 0.65),
            (cx - spine_gap, cy + half_h),
        ],
        outline=ACCENT,
        width=stroke,
    )
    draw.polygon(
        [
            (cx + spine_gap, cy - half_h),
            (cx + spine_gap + half_w, cy - half_h * 0.65),
            (cx + spine_gap + half_w, cy + half_h * 0.65),
            (cx + spine_gap, cy + half_h),
        ],
        outline=ACCENT,
        width=stroke,
    )
    draw.line([(cx, cy - half_h * 0.9), (cx, cy + half_h * 0.9)], fill=ACCENT, width=stroke)

    return canvas


def make_icons() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, size in SIZES.items():
        path = OUTPUT_DIR / filename
        _make_icon(size).save(path, format="PNG")
        print(f"Wrote {path}")


if __name__ == "__main__":
    make_icons()
