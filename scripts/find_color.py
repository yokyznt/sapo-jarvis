import sys
from PIL import Image
hexc = sys.argv[1]
t = tuple(int(hexc[i:i + 2], 16) for i in (0, 2, 4))
for f in sys.argv[2:]:
    im = Image.open(f).convert("RGB")
    w, h = im.size
    px = im.load()
    xs, ys = [], []
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            r, g, b = px[x, y]
            if abs(r - t[0]) < 6 and abs(g - t[1]) < 6 and abs(b - t[2]) < 6:
                xs.append(x)
                ys.append(y)
    print(f, (min(xs), min(ys), max(xs), max(ys)) if xs else None, len(xs))
