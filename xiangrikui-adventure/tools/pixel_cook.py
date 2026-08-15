#!/usr/bin/env python3
"""硬像素共用层：trim / quantize / 装格 / 横条 sheet。

角色与世界管线都必须走这里，禁止在 process_*.py 再复制一份。
量化垫色必须与主体反差（见 PAD_RGB / character.json quant_pad）。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from pixel_matte import despill_chroma_edges, fringe_clean, matte, matte_auto, is_screen_key

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
    alpha_cut: int = 120,
) -> Image.Image:
    """BOX → 硬化 alpha → 反差垫色量化无抖动 → 丢垫色/品红残留 → NEAREST。"""
    pad_rgb = resolve_pad(pad)
    mid = img.convert("RGBA").resize((max(1, tw * 2), max(1, th * 2)), Image.Resampling.BOX)
    px = mid.load()
    for y in range(mid.height):
        for x in range(mid.width):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 255 if a >= alpha_cut else 0)
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
        # 绿垫量化后剥绿晕；品红幕角色用 #FF00FF（由调用方 pad 推断）
        fill = "#00FF00" if pad_rgb == (0, 255, 0) else (
            "#FF00FF" if pad_rgb == (255, 0, 255) else None
        )
        out = matte(out, blob=False, fill_hex=fill)
        if fill:
            out = despill_chroma_edges(out, fill)
        return out
    out = fringe_clean(out, passes=1)
    if pad_rgb == (0, 255, 0):
        out = despill_chroma_edges(out, "#00FF00")
    return out


def fit_bottom_fixed(img: Image.Image, cell: tuple[int, int]) -> Image.Image:
    """脚底对齐画格底边。超高/超宽时 NEAREST 等比缩小装入，禁止裁头顶。"""
    tw, th = cell
    canvas = Image.new("RGBA", cell, (0, 0, 0, 0))
    iw, ih = img.size
    if iw < 1 or ih < 1:
        return canvas
    if iw > tw or ih > th:
        s = min(tw / float(iw), th / float(ih))
        nw = max(1, int(round(iw * s)))
        nh = max(1, int(round(ih * s)))
        img = img.resize((nw, nh), Image.Resampling.NEAREST)
        iw, ih = nw, nh
    canvas.paste(img, ((tw - iw) // 2, th - ih), img)
    return canvas


def fit_cell_preserve_frac(img: Image.Image, cell: tuple[int, int]) -> Image.Image:
    """把「已等格、已抠幕、未 trim」的源格装进固定 cell，保留内容相对位置（跳顶点不坠底）。

    源图必须是虚拟等格整格（含透明留白）。等比缩小装入后按 bbox 中心的归一化坐标粘贴。
    """
    tw, th = cell
    canvas = Image.new("RGBA", cell, (0, 0, 0, 0))
    img = img.convert("RGBA")
    sw, sh = img.size
    if sw < 1 or sh < 1:
        return canvas
    bb = content_bbox(img)
    if not bb:
        return canvas
    # 整格等比装入目标格（虚拟边框 = 等宽等高）
    s = min(tw / float(sw), th / float(sh))
    nw = max(1, int(round(sw * s)))
    nh = max(1, int(round(sh * s)))
    scaled = img.resize((nw, nh), Image.Resampling.NEAREST)
    # 源格内内容中心 → 目标格对应位置
    cx = (bb[0] + bb[2]) * 0.5 / sw
    cy = (bb[1] + bb[3]) * 0.5 / sh
    sbb = content_bbox(scaled)
    if not sbb:
        return canvas
    scw = sbb[2] - sbb[0]
    sch = sbb[3] - sbb[1]
    px = int(round(cx * tw - scw * 0.5)) - sbb[0]
    py = int(round(cy * th - sch * 0.5)) - sbb[1]
    px = max(min(px, tw - nw), min(0, tw - nw))
    py = max(min(py, th - nh), min(0, th - nh))
    # 若整格已缩进目标内，直接居中整格更稳（等宽等高）
    if nw <= tw and nh <= th:
        canvas.paste(scaled, ((tw - nw) // 2, (th - nh) // 2), scaled)
    else:
        canvas.paste(scaled, (px, py), scaled)
    return canvas


def split_frames(img: Image.Image, n: int) -> list[Image.Image]:
    """横条或近方阵网格切帧（不抠图）。保证等宽：用 width//n，余数丢右侧。

    - idle 等 **完全平方** 帧数（16=4×4）→ 方阵（即使整图宽≥高）。
    - walk/jump 等非平方帧数 → 宽≥高时横条（含 8×瘦高格拼成 1536×1024）。
    """
    img = img.convert("RGBA")
    root = int(round(n**0.5))
    square = root * root == n and root >= 2
    if (not square) and img.width >= img.height:
        cw = img.width // n
        ch = img.height
        return [img.crop((i * cw, 0, (i + 1) * cw, ch)) for i in range(n)]
    cols = root if square else int(round(n**0.5))
    if not square:
        while cols > 1 and n % cols:
            cols -= 1
    rows = n // max(1, cols)
    cw, ch = img.width // cols, img.height // rows
    crops: list[Image.Image] = []
    for r in range(rows):
        for c in range(cols):
            crops.append(img.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)))
    return crops[:n]


def matte_frames(
    crops: list[Image.Image],
    *,
    empty_h: int = 8,
    fill_hex: str | None = None,
    mode: str = "flood",
    trim: bool = True,
) -> list[Image.Image]:
    """每格独立 matte。trim=False 时保持等格尺寸（虚拟边框），只把幕变透明。"""
    parts: list[Image.Image] = []
    for part in crops:
        m = matte_auto(part, mode=mode, blob=True, fill_hex=fill_hex)
        if trim:
            m = trim_alpha(m)
            if m.width < 2 or m.height < 2:
                m = Image.new("RGBA", (8, empty_h), (0, 0, 0, 0))
        else:
            # 原地抠：尺寸与源格完全一致
            if m.size != part.size:
                canvas = Image.new("RGBA", part.size, (0, 0, 0, 0))
                canvas.paste(m, (0, 0), m)
                m = canvas
            solid = sum(
                1 for y in range(m.height) for x in range(m.width) if m.getpixel((x, y))[3] > 128
            )
            if solid < 80:
                m = Image.new("RGBA", part.size, (0, 0, 0, 0))
        parts.append(m)
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
