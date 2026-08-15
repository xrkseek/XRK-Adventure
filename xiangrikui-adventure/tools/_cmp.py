from PIL import Image
from pathlib import Path
import json

base = Path("assets/characters/meijia")
cfg = json.loads((base / "character.json").read_text(encoding="utf-8"))
print("character.json cell/body:", cfg.get("cell"), cfg.get("body_h"))
print("states:", cfg.get("states"))

idle = Image.open(base / "anim/idle_sheet.png").convert("RGBA")
w, h = idle.size
print("idle_sheet", (w, h))
if h >= 400:
    cw, ch = w // 4, h // 4
    layout = "4x4"
else:
    n = 16 if w >= 16 * 100 else max(1, w // 128)
    cw, ch = w // n, h
    layout = "1x%d" % n
idle0 = idle.crop((0, 0, cw, ch))
print("layout", layout, "idle0", idle0.size)

prev = Image.open(base / "refs/idle_pixel_preview.png").convert("RGBA")
print("preview", prev.size)
prev_fit = prev.resize((cw, ch), Image.NEAREST) if prev.size != (cw, ch) else prev

def opaque_bbox(im, a=40):
    px = im.load()
    xs, ys = [], []
    for y in range(im.height):
        for x in range(im.width):
            if px[x, y][3] >= a:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)

def head_crop(im):
    bb = opaque_bbox(im)
    x0, y0, x1, y1 = bb
    hh = max(8, int((y1 - y0) * 0.45))
    return im.crop((x0, y0, x1, y0 + hh)).resize((64, 48), Image.NEAREST)

def colordiff(a, b):
    s = 0.0
    n = 0
    for y in range(a.height):
        for x in range(a.width):
            pa = a.getpixel((x, y))
            pb = b.getpixel((x, y))
            if pa[3] < 16 and pb[3] < 16:
                continue
            n += 1
            s += sum(abs(pa[i] - pb[i]) for i in range(3)) / 3.0
    return s / max(n, 1)

def sil(im, size=(64, 68)):
    bb = opaque_bbox(im)
    crop = im.crop(bb)
    canvas = Image.new("L", size, 0)
    scale = min((size[0] - 4) / float(crop.width), (size[1] - 4) / float(crop.height))
    nw = max(1, int(crop.width * scale))
    nh = max(1, int(crop.height * scale))
    r = crop.resize((nw, nh), Image.NEAREST)
    x = (size[0] - nw) // 2
    y = size[1] - nh - 2
    for yy in range(nh):
        for xx in range(nw):
            if r.getpixel((xx, yy))[3] >= 64:
                canvas.putpixel((x + xx, y + yy), 255)
    return canvas

def iou(a, b):
    inter = 0
    union = 0
    for y in range(a.height):
        for x in range(a.width):
            aa = a.getpixel((x, y) > 0)
