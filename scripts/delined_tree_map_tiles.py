"""One-off touch-up of the /tree survey-map background tiles: erases the
straight horizontal/vertical grid lines (and the bolder "+" ticks at their
intersections) while leaving everything else — leather/parchment grain,
speckles, the wandering dotted contour lines — untouched, then drops a
single small dot at each former intersection so the tiles still read as a
surveyed map without any axis-aligned strokes that could be confused with
the tree's own rectilinear connector lines.

Operates in place on the four tiles under app/static/img/tree-map-tile*.jpg.
Not part of the app; run manually if the tiles ever need retouching again:

    python scripts/delined_tree_map_tiles.py
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

GRID_STEP = 128
SIZE = 1024
GRID_COORDS = list(range(0, SIZE, GRID_STEP))

# Thin-line erase: replace a narrow band straddling each grid coordinate
# with a straight copy of the real texture a few pixels further into the
# same cell (not a blend — averaging pixels either side of the band wipes
# out the fine grain and leaves a smoother, MORE visible stripe than the
# line it replaced). The shift has to stay well inside the 128px cell so
# the source pixels are never themselves part of another grid line.
LINE_BAND = 3
LINE_SHIFT = 24

# Intersection patch: the bold "+" tick extends further than the thin
# line, so each of the 8x8 crossing points gets a separate circular
# "shrink" inpaint (sample radius r reflected out to 2*RADIUS-r, the
# standard blemish-removal trick) big enough to swallow the tick.
TICK_RADIUS = 20
FEATHER = 5

# Landmark dot left behind at each former intersection: a small, low
# opacity mark, not a stroke — enough to still read as a measured
# reference point without drawing any line.
DOT_RADIUS = 1.6


def erase_grid_lines(img):
    px = img.load()
    w, h = img.size

    # Verticals: replace each column in the band with a straight copy of
    # the column LINE_SHIFT further right, full height.
    for g in GRID_COORDS:
        for x in range(g - LINE_BAND, g + LINE_BAND + 1):
            src_x = (x + LINE_SHIFT) % w
            dst_x = x % w
            for y in range(h):
                px[dst_x, y] = px[src_x, y]

    # Horizontals: same idea, shifted down instead of right. Runs after
    # the vertical pass so any row it copies from is already line-free.
    for g in GRID_COORDS:
        for y in range(g - LINE_BAND, g + LINE_BAND + 1):
            src_y = (y + LINE_SHIFT) % h
            dst_y = y % h
            for x in range(w):
                px[x, dst_y] = px[x, src_y]


def patch_intersections(img):
    px = img.load()
    w, h = img.size
    src = img.copy()
    spx = src.load()

    for gx in GRID_COORDS:
        for gy in GRID_COORDS:
            for dy in range(-TICK_RADIUS - FEATHER, TICK_RADIUS + FEATHER + 1):
                for dx in range(-TICK_RADIUS - FEATHER, TICK_RADIUS + FEATHER + 1):
                    r = math.hypot(dx, dy)
                    if r > TICK_RADIUS + FEATHER:
                        continue
                    x = (gx + dx) % w
                    y = (gy + dy) % h
                    if r <= TICK_RADIUS:
                        rr = 2 * TICK_RADIUS - r
                    else:
                        rr = r
                    if r < 1e-6:
                        sx, sy = gx, gy - rr
                    else:
                        scale = rr / r
                        sx = gx + dx * scale
                        sy = gy + dy * scale
                    fetched = spx[round(sx) % w, round(sy) % h]
                    if r <= TICK_RADIUS:
                        px[x, y] = fetched
                    else:
                        # Feather the seam between the reflected fill and
                        # the untouched original over a few pixels.
                        blend = (r - TICK_RADIUS) / FEATHER
                        original = spx[x, y]
                        px[x, y] = (
                            round(fetched[0] * (1 - blend) + original[0] * blend),
                            round(fetched[1] * (1 - blend) + original[1] * blend),
                            round(fetched[2] * (1 - blend) + original[2] * blend),
                        )


def draw_landmark_dots(img, dot_color):
    from PIL import ImageDraw

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    r = DOT_RADIUS
    for gx in GRID_COORDS:
        for gy in GRID_COORDS:
            draw.ellipse((gx - r, gy - r, gx + r, gy + r), fill=dot_color)
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))


def delined(path, dot_color):
    img = Image.open(path).convert("RGB")
    erase_grid_lines(img)
    patch_intersections(img)
    draw_landmark_dots(img, dot_color)
    img.save(path, format="JPEG", quality=92)
    print("wrote", path)


def main():
    img_dir = Path(__file__).resolve().parent.parent / "app" / "static" / "img"
    delined(img_dir / "tree-map-tile.jpg", dot_color=(154, 130, 92, 130))
    delined(img_dir / "tree-map-tile-dark.jpg", dot_color=(196, 176, 132, 110))


if __name__ == "__main__":
    main()
