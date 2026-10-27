"""Tile every <step>-th dumped frame into one labelled image, to see a whole run at a glance.

Usage: python contact_sheet.py <frames dir> <out.png> [step=200] [first=0] [last=-1] [cols=6] [width=280]
"""
import os
import re
import sys

from PIL import Image, ImageDraw


def main():
    src, out = sys.argv[1], sys.argv[2]
    step, first, last, cols, width = (int(a) for a in (sys.argv[3:] + ["200", "0", "-1", "6", "280"][len(sys.argv) - 3:]))
    frames = {}
    for name in os.listdir(src):
        m = re.fullmatch(r"framedump_(\d+)\.png", name)
        if m:
            frames[int(m.group(1))] = name
    if last < 0:
        last = max(frames)
    picks = [n for n in range(first, last + 1, step) if n in frames]
    tiles = []
    for n in picks:
        try:
            im = Image.open(os.path.join(src, frames[n])).convert("RGB")
        except OSError:
            continue  # frame cut short when Dolphin was stopped
        im = im.resize((width, width * im.height // im.width))
        ImageDraw.Draw(im).text((4, 4), str(n), fill=(255, 0, 0))
        tiles.append(im)
    w, h = tiles[0].size
    sheet = Image.new("RGB", (cols * w, -(-len(tiles) // cols) * h))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(out)
    print(f"{len(tiles)} frames -> {out}")


if __name__ == "__main__":
    main()
