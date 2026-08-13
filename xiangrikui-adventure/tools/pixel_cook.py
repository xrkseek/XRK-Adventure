#!/usr/bin/env python3
"""硬像素共用层：trim / quantize / 装格 / 横条 sheet。

角色与世界管线都必须走这里，禁止在 process_*.py 再复制一份。
量化垫色必须与主体反差（见 PAD_RGB / character.json quant_pad）。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from pixel_matte import fringe_clean, matte, is_screen_key

# 量化垫色预设：透明区填充色，须与主体反差
PAD_RGB: dict[str, tuple[int, int, int]] = {
    "black": (0, 0, 0),  # 粉色系主体
    "green": (0, 255, 0),  # 深色衣/品红幕角色（默认鹿）
    "magenta": (255, 0, 255),  # 仅兼容旧资产；新资产禁止
}


def trim_alpha(img: Image.Image, threshold: int = 12, pad: int = 2) -> Image.Image:
    alpha = img.split()[3].point(lambda a: 255 if a > threshold else 0)
    bbox = alpha.getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    return img.crop(
        (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(img.width, x1 + pad),
            min(img.height, y1 + pad),
        )
    )


def content_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    a = img.split()[3].point(lambda v: 255 if v >= 128 else 0)
    return a.getbbox()


def resolve_pad(pad: str | tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(pad, tuple):
        return pad
    if pad not in PAD_RGB:
        raise ValueError(f"Unknown quant_pad={pad!r}; use {sorted(PAD_RGB)}")
    return PAD_RGB[pad]


def _is_pad_pixel(r: int, g: int, b: int, pad: tuple[int, int, int]) -> bool:
    pr, pg, pb = pad
    # 绿垫
    if pad == (0, 255, 0):
        return g >= 240 and r <= 40 and b <= 40
    # 黑垫：只靠原 alpha 丢，不按颜色删黑（防抠穿眼睛）
    if pad == (0, 0, 0):
        return False
    return abs(r - pr) <= 8 and abs(g - pg) <= 8 and abs(b - pb) <= 8


def hard_pixel(
    img: Image.Image,
    tw: int,
    th: int,
    colors: int = 64,
    *,
    pad: str | tuple[int, int, int] = "black",
    rematte: bool = True,
) -> Image.Image:
    """BOX → 硬化 alpha → 反差垫色量化无抖动 → 丢垫色/品红残留 → NEAREST。"""
    pad_rgb = resolve_pad(pad)
    mid = img.convert("RGBA").resize((max(1, tw * 2), max(1, th * 2)), Image.Resampling.BOX)
    px = mid.load()
    for y in range(mid.height):
        for x in range(mid.width):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 255 if a >= 120 else 0)
    flat = Image.new("RGBA", mid.size, (*pad_rgb, 255))
    flat.paste(mid, mask=mid.split()[3])
    q = (
        flat.convert("RGB")
        .quantize(colors=colors, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
        .convert("RGBA")
    )
    qpx, mpx = q.load(), mid.load()
    for y in range(q.height):
        for x in range(q.width):
            r, g, b, _ = qpx[x, y]
            if mpx[x, y][3] == 0 or _is_pad_pixel(r, g, b, pad_rgb) or is_screen_key(r, g, b):
                qpx[x, y] = (0, 0, 0, 0)
            else:
                qpx[x, y] = (r, g, b, 255)
    out = q.resize((tw, th), Image.Resampling.NEAREST)
    if rematte:
        return matte(out, blob=False)
    return fringe_clean(out)


def fit_bottom_fixed(img: Image.Image, cell: tuple[int, int]) -> Image.Image:
    """脚底对齐画格底边（站立角色）。"""
    tw, th = cell
    canvas = Image.new("RGBA", cell, (0, 0, 0, 0))
    iw, ih = img.size
    if iw > tw:
        x0 = (iw - tw) // 2
        img = img.crop((x0, 0, x0 + tw, ih))
        iw = tw
    if ih > th:
        y0 = ih - th
        img = img.crop((0, y0, iw, y0 + th))
        ih = th
    canvas.paste(img, ((tw - iw) // 2, th - ih), img)
    return canvas


def split_frames(img: Image.Image, n: int) -> list[Image.Image]:
    """横条或近方阵网格切帧（不抠图）。"""
    img = img.convert("RGBA")
    if img.width >= img.height * 2:
        cw = img.width // n
        return [img.crop((i * cw, 0, (i + 1) * cw, img.height)) for i in range(n)]
    cols = int(round(n**0.5))
    while cols > 1 and n % cols:
        cols -= 1
    rows = n // max(1, cols)
    cw, ch = img.width // cols, img.height // rows
    crops: list[Image.Image] = []
    for r in range(rows):
        for c in range(cols):
            crops.append(img.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)))
    return crops[:n]


def matte_frames(crops: list[Image.Image], *, empty_h: int = 8) -> list[Image.Image]:
    """每格独立 matte + trim；空帧占位。"""
    parts: list[Image.Image] = []
    for part in crops:
        part = trim_alpha(matte(part, blob=True))
        if part.width < 2 or part.height < 2:
            part = Image.new("RGBA", (8, empty_h), (0, 0, 0, 0))
        parts.append(part)
    return parts


def write_hsheet(
    frames: list[Image.Image],
    path: Path,
    *,
    px: int = 2,
    root: Path | None = None,
    min_solid: int = 80,
) -> Image.Image:
    """横条拼 sheet → NEAREST×px 写出；空帧 WARN。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = frames[0].size
    sheet = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * w, 0), f)
    out = sheet.resize((sheet.width * px, sheet.height * px), Image.Resampling.NEAREST)
    out.save(path)
    heights: list[int] = []
    solids: list[int] = []
    for f in frames:
        bb = content_bbox(f)
        heights.append(bb[3] - bb[1] if bb else 0)
        fpx = f.load()
        solids.append(
            sum(1 for y in range(f.height) for x in range(f.width) if fpx[x, y][3] >= 128)
        )
    rel = path.relative_to(root) if root else path
    print(f"  {rel} {out.size} frames={len(frames)} content_h={heights}")
    empty = [i for i, s in enumerate(solids) if s < min_solid]
    if empty:
        print(f"  WARN nearly-empty frames: {empty} solids={solids}")
    return out
