#!/usr/bin/env python3
"""蜘蛛人 boss 填格 → 局内 120×120@1× → ×2=240。

硬约束：
- 强制 Nx1 等宽横条
- 只抠热品红（禁止浅灰 rekey）
- 整身：放大 → 硬量化 → NEAREST 缩小（不加第二颗头）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from pixel_cook import content_bbox, resolve_pad, write_hsheet, _is_pad_pixel  # noqa: E402
from pixel_matte import (  # noqa: E402
    despill_chroma_edges,
    fringe_clean,
    is_hot_magenta_only,
    matte_hot_magenta,
)

ENEMIES = ROOT / "assets" / "enemies" / "anim"
RAW = ROOT / "assets" / "enemies" / "raw"
SPRITES = ROOT / "assets" / "sprites"
REFS = ROOT / "assets" / "enemies" / "refs"

CELL_1X = 120
PX = 2
FRAMES = {"idle": 4, "walk": 6, "attack": 6}
PALETTE = 128
UPSCALE = 12


def crisp_pixel(img: Image.Image, tw: int, th: int) -> Image.Image:
    """整身放大 → 少色无抖动 → NEAREST 两级缩回。"""
    pad_rgb = resolve_pad("green")
    big_w, big_h = max(1, tw * UPSCALE), max(1, th * UPSCALE)
    big = img.convert("RGBA").resize((big_w, big_h), Image.Resampling.BOX)
    px = big.load()
    for y in range(big.height):
        for x in range(big.width):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 255 if a >= 110 else 0)
    flat = Image.new("RGBA", big.size, (*pad_rgb, 255))
    flat.paste(big, mask=big.split()[3])
    q = (
        flat.convert("RGB")
        .quantize(colors=PALETTE, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
        .convert("RGBA")
    )
    qpx, mpx = q.load(), big.load()
    for y in range(q.height):
        for x in range(q.width):
            r, g, b, _ = qpx[x, y]
            if (
                mpx[x, y][3] == 0
                or _is_pad_pixel(r, g, b, pad_rgb)
                or is_hot_magenta_only(r, g, b)
            ):
                qpx[x, y] = (0, 0, 0, 0)
            else:
                qpx[x, y] = (r, g, b, 255)
    mid = q.resize((max(1, tw * 2), max(1, th * 2)), Image.Resampling.NEAREST)
    out = mid.resize((tw, th), Image.Resampling.NEAREST)
    out = fringe_clean(out, passes=1)
    out = despill_chroma_edges(out, "#00FF00")
    return out


def _richest_band(im: Image.Image) -> Image.Image:
    a = np.asarray(im.convert("RGBA"))
    h, w = a.shape[:2]
    rgb = a[:, :, :3].astype(np.int16)
    mag = (rgb[:, :, 0] >= 200) & (rgb[:, :, 2] >= 190) & (rgb[:, :, 1] <= 70)
    solid = (a[:, :, 3] > 40) & (~mag)
    row_c = solid.sum(axis=1)
    thresh = max(8, w // 80)
    bands: list[tuple[int, int]] = []
    inb = False
    s = 0
    for y, c in enumerate(row_c.tolist()):
        if c >= thresh and not inb:
            inb, s = True, y
        elif c < thresh and inb:
            inb = False
            bands.append((s, y - 1))
    if inb:
        bands.append((s, h - 1))
    min_h = max(64, h // 5)
    bands = [(a0, b0) for a0, b0 in bands if (b0 - a0 + 1) >= min_h]
    if len(bands) < 2:
        return im
    best = max(bands, key=lambda ab: int(row_c[ab[0] : ab[1] + 1].sum()))
    pad = 8
    y0 = max(0, best[0] - pad)
    y1 = min(h, best[1] + 1 + pad)
    print(f"  layout multi-row → band y={y0}:{y1}")
    return im.crop((0, y0, w, y1))


def force_nx1_cells(im: Image.Image, n: int) -> list[Image.Image]:
    im = im.convert("RGBA")
    if im.height > im.width * 0.45:
        im = _richest_band(im)
    w, h = im.size
    cw = w // n
    if cw < 8:
        raise SystemExit(f"FAIL cell too narrow: {w}x{h} / {n}")
    cells = [im.crop((i * cw, 0, (i + 1) * cw, h)) for i in range(n)]
    print(f"  force {n}x1 equal cells {cw}x{h}")
    return cells


def cook_state(state: str, src: Path) -> Path:
    n = FRAMES[state]
    im = Image.open(src).convert("RGBA")
    RAW.mkdir(parents=True, exist_ok=True)
    im.save(RAW / f"boss_{state}_ai.png")

    cells = force_nx1_cells(im, n)
    fitted: list[Image.Image] = []
    for i, cell in enumerate(cells):
        m = matte_hot_magenta(cell, blob=False)
        bb = content_bbox(m)
        if not bb:
            raise SystemExit(f"FAIL empty f{i+1}")
        content = m.crop(bb)
        if state == "idle" and i == 0:
            REFS.mkdir(parents=True, exist_ok=True)
            content.save(REFS / "_boss_f1_matted_check.png")
        scale = min(CELL_1X / float(content.width), CELL_1X / float(content.height)) * 0.98
        tw = max(1, round(content.width * scale))
        th = max(1, round(content.height * scale))
        pix = crisp_pixel(content, tw, th)
        canvas = Image.new("RGBA", (CELL_1X, CELL_1X), (0, 0, 0, 0))
        canvas.paste(pix, ((CELL_1X - tw) // 2, CELL_1X - th), pix)
        solid = int((np.asarray(canvas)[:, :, 3] > 128).sum())
        fitted.append(canvas)
        print(f"  f{i+1} →{tw}x{th} solid={solid}")
        if solid < 800:
            raise SystemExit(f"FAIL f{i+1} nearly empty")

    ENEMIES.mkdir(parents=True, exist_ok=True)
    out = (
        ENEMIES / "enemy_boss_sheet.png"
        if state == "idle"
        else ENEMIES / f"enemy_boss_{state}_sheet.png"
    )
    write_hsheet(fitted, out, px=PX, root=ROOT)

    if state == "idle":
        single = fitted[0].resize((CELL_1X * PX, CELL_1X * PX), Image.Resampling.NEAREST)
        SPRITES.mkdir(parents=True, exist_ok=True)
        single.save(SPRITES / "enemy_boss.png")
        print(f"  sprites/enemy_boss.png {single.size}")
        fitted[0].resize((CELL_1X * 4, CELL_1X * 4), Image.Resampling.NEAREST).save(
            REFS / "boss_pixel_preview.png"
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, choices=sorted(FRAMES))
    ap.add_argument("--src", required=True, type=Path)
    args = ap.parse_args()
    out = cook_state(args.state, args.src)
    print("ok", out, f"whole-body up={UPSCALE}x palette={PALETTE} (no face paste)")


if __name__ == "__main__":
    main()
