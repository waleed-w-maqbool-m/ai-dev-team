"""Tiles screenshots into a labelled contact sheet: python sheet.py OUT.png COLS img1 img2 ..."""
import os
import sys

from PIL import Image, ImageDraw

out, cols, files = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
W = 720
ims = [Image.open(f).convert("RGB") for f in files]
H = int(ims[0].height * W / ims[0].width)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (W + 8) + 8, rows * (H + 26) + 8), (40, 40, 40))
d = ImageDraw.Draw(sheet)
for i, (f, im) in enumerate(zip(files, ims)):
    x, y = 8 + (i % cols) * (W + 8), 8 + (i // cols) * (H + 26)
    sheet.paste(im.resize((W, H)), (x, y + 18))
    d.text((x, y + 2), os.path.basename(f), fill=(255, 210, 0))
sheet.save(out)
