"""
CreateStoryboard.py

Build a vertical storyboard image from a folder produced by ExtractKeyframes.py.

Reads `timestamps.txt` in the given folder, then for each line:
  - loads the referenced frame
  - downscales it to a target vertical resolution (TARGET_HEIGHT)
  - draws a black border around it
  - prints the timestamp range in a column on the left

All rows are stacked vertically into a single `storyboard.png`.

With --pairs, each row instead shows two frames per cut — the _FIRST frame
and the _LAST frame side by side, with an arrow pointing from the first
frame to the last frame. The canvas is extended horizontally to fit both.

Usage:
    python CreateStoryboard.py path/to/folder [--pairs]
"""

import argparse
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

# ---- Tweakable layout settings -------------------------------------------
TARGET_HEIGHT = 400      # vertical resolution each frame is scaled to (px)
BORDER = 4               # black border thickness around each frame (px)
TEXT_COL_WIDTH = 278     # width of the left-hand timestamp column (px)
ROW_PADDING = 12         # vertical gap between rows (px)
SIDE_PADDING = 16        # outer left/right margin (px)
BG_COLOR = (255, 255, 255)
BORDER_COLOR = (0, 0, 0)
TEXT_COLOR = (0, 0, 0)
FONT_SIZE = 56
ARROW_GAP = 140          # horizontal space between first/last frames (px, --pairs)
ARROW_MARGIN = 20        # gap between arrow ends and the frames (px)
ARROW_WIDTH = 10         # arrow shaft thickness (px)
ARROW_HEAD = 32          # arrow head length (px)
ARROW_COLOR = (0, 0, 0)
# --------------------------------------------------------------------------


def load_font():
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, FONT_SIZE)
        except OSError:
            continue
    return ImageFont.load_default()


def parse_timestamps(path):
    """Return a list of (timestamp_label, filename) tuples."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^(.*?):\s*(.+)$", line)
            if not m:
                continue
            rows.append((m.group(1).strip(), m.group(2).strip()))
    return rows


def scale_to_height(img, height):
    w, h = img.size
    if h == 0:
        return img
    new_w = max(1, round(w * height / h))
    return img.resize((new_w, height), Image.LANCZOS)


def load_frame(folder, filename, height):
    """Load a frame and scale it, or return None with a warning."""
    img_path = os.path.join(folder, filename)
    if not os.path.isfile(img_path):
        print(f"WARNING: missing frame, skipping: {filename}")
        return None
    try:
        img = Image.open(img_path).convert("RGB")
    except Exception as e:
        print(f"WARNING: could not open {filename}: {e}")
        return None
    return scale_to_height(img, height)


def draw_arrow(draw, x0, x1, y):
    """Draw a horizontal arrow from (x0, y) pointing right to (x1, y)."""
    draw.line([(x0, y), (x1 - ARROW_HEAD, y)], fill=ARROW_COLOR, width=ARROW_WIDTH)
    draw.polygon(
        [(x1, y),
         (x1 - ARROW_HEAD, y - ARROW_HEAD // 2),
         (x1 - ARROW_HEAD, y + ARROW_HEAD // 2)],
        fill=ARROW_COLOR,
    )


def main():
    parser = argparse.ArgumentParser(description="Create a vertical storyboard from extracted frames.")
    parser.add_argument("folder", help="Folder containing timestamps.txt and the frame PNGs.")
    parser.add_argument("--height", type=int, default=TARGET_HEIGHT,
                        help=f"Target vertical resolution per frame (default {TARGET_HEIGHT}).")
    parser.add_argument("--output", default=None,
                        help="Output path (default <folder>/storyboard.png).")
    parser.add_argument("--pairs", action="store_true",
                        help="Show the _FIRST and _LAST frame of each cut side by "
                             "side, with an arrow pointing from first to last.")
    args = parser.parse_args()

    target_height = args.height

    if not os.path.isdir(args.folder):
        sys.exit(f"ERROR: folder not found: {args.folder}")

    ts_path = os.path.join(args.folder, "timestamps.txt")
    if not os.path.isfile(ts_path):
        sys.exit(f"ERROR: timestamps.txt not found in {args.folder}")

    rows = parse_timestamps(ts_path)
    if not rows:
        sys.exit("ERROR: no usable entries found in timestamps.txt")

    font = load_font()

    # Load and scale all images first so we can size the canvas.
    panels = []  # (label, [scaled_image]) — or [first, last] with --pairs
    for label, filename in rows:
        names = [filename]
        if args.pairs:
            if "_FIRST" not in filename:
                print(f"WARNING: no _FIRST suffix in {filename}; skipping "
                      f"(--pairs needs frames from the updated ExtractKeyframes.py).")
                continue
            names.append(filename.replace("_FIRST", "_LAST"))
        imgs = [load_frame(args.folder, n, target_height) for n in names]
        if any(img is None for img in imgs):
            continue
        panels.append((label, imgs))

    if not panels:
        sys.exit("ERROR: no frames could be loaded.")

    max_img_w = max(img.width for _, imgs in panels for img in imgs)
    bordered_h = target_height + 2 * BORDER
    row_h = bordered_h + ROW_PADDING

    # With --pairs the canvas is extended horizontally to fit the second
    # frame plus the arrow gap between the two.
    frames_w = max_img_w + 2 * BORDER
    if args.pairs:
        frames_w = frames_w * 2 + ARROW_GAP
    canvas_w = SIDE_PADDING + TEXT_COL_WIDTH + frames_w + SIDE_PADDING
    canvas_h = ROW_PADDING + row_h * len(panels)

    canvas = Image.new("RGB", (canvas_w, canvas_h), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    y = ROW_PADDING
    img_x = SIDE_PADDING + TEXT_COL_WIDTH
    for label, imgs in panels:
        x = img_x
        for i, img in enumerate(imgs):
            if i > 0:
                # Arrow from the first frame to the last frame, centered
                # vertically against the row.
                draw_arrow(draw, x + ARROW_MARGIN, x + ARROW_GAP - ARROW_MARGIN,
                           y + bordered_h // 2)
                x += ARROW_GAP
            # Black border: filled rect behind the frame.
            draw.rectangle(
                [x, y, x + img.width + 2 * BORDER, y + img.height + 2 * BORDER],
                fill=BORDER_COLOR,
            )
            canvas.paste(img, (x + BORDER, y + BORDER))
            x += img.width + 2 * BORDER

        # Timestamp text, centered in the empty space to the left of the frame
        # (both horizontally within that column and vertically against the frame).
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = (img_x - text_w) // 2 - bbox[0]
        text_y = y + (bordered_h - text_h) // 2 - bbox[1]
        draw.text((text_x, text_y), label, fill=TEXT_COLOR, font=font)

        y += row_h

    out_path = args.output or os.path.join(args.folder, "storyboard.png")
    canvas.save(out_path)
    print(f"Saved storyboard with {len(panels)} panels to {out_path}")


if __name__ == "__main__":
    main()
