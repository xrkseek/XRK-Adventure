#!/usr/bin/env python3
"""世界 / 敌人 / 道具 AI→硬像素（角色请用 process_character.py）。"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from pixel_matte import fringe_clean, matte, assert_margin, fit_contain  # noqa: E402
from pixel_cook import hard_pixel, trim_alpha  # noqa: E402

RAW = ROOT / "assets" / "raw"
SPRITES = ROOT / "assets" / "sprites"
ENEMIES = ROOT / "assets" / "enemies" / "anim"
PROPS = ROOT / "assets" / "props"
BG = ROOT / "assets" / "bg"
TILES = ROOT / "assets" / "tiles"
DECOR = ROOT / "assets" / "decor"
REF = ROOT / "assets" / "refs"
CURSOR_ASSETS = Path.home() / ".cursor" / "projects" / "c-Users-sunflowerss-Desktop-XRKgrocery-XRK-Adventure" / "assets"


def sync_raw(name: str) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    dst = RAW / name
    src = CURSOR_ASSETS / name
    if src.is_file():
        shutil.copy2(src, dst)
    if not dst.is_file():
        raise SystemExit(f"Missing AI raw: {dst} (and {src})")
    return dst


def chroma(img: Image.Image, kill_black: bool = False) -> Image.Image:
    _ = kill_black
    return matte(img, blob=False)


def fringe(img: Image.Image) -> Image.Image:
    return fringe_clean(img)


def trim(img: Image.Image, pad: int = 2) -> Image.Image:
    return trim_alpha(img, threshold=16, pad=pad)


def split_sheet(src: Path, n: int) -> list[Image.Image]:
    img = Image.open(src).convert("RGBA")
    cw = img.width // n
    parts = []
    for i in range(n):
        cell = img.crop((i * cw, 0, (i + 1) * cw, img.height))
        part = matte(cell, blob=True)
        assert_margin(part, name=f"{src.name}[{i}] after-matte")
        parts.append(trim(part))
    return parts


def process_flyer() -> None:
    sync_raw("enemy_flyer_ai.png")
    parts = split_sheet(RAW / "enemy_flyer_ai.png", 4)
    tw, th, frames = 64, 48, 4
    ENEMIES.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGBA", (tw * frames, th), (0, 0, 0, 0))

    def _hp(img, w, h, colors=48):
        return hard_pixel(img, w, h, colors=colors, pad="black", rematte=False)

    for i, part in enumerate(parts):
        if part.width < 2 or part.height < 2:
            print(f"  flyer frame {i} empty after matte")
            continue
        cell = fit_contain(part, tw, th, margin=5, colors=48, hard_pixel_fn=_hp)
        assert_margin(cell, name=f"flyer out[{i}]")
        sheet.paste(cell, (i * tw, 0), cell)
        if i == 0:
            cell.resize((tw * 2, th * 2), Image.Resampling.NEAREST).save(SPRITES / "enemy_flyer.png")
    final = sheet.resize((tw * frames * 2, th * 2), Image.Resampling.NEAREST)
    out = ENEMIES / "enemy_flyer_sheet.png"
    final.save(out)
    print(f"  {out.relative_to(ROOT)} {final.size} cell={tw}x{th}@1x")


def bg_pixel(
    src: Path,
    out: Path,
    tw: int,
    th: int,
    colors: int = 56,
    *,
    key_magenta: bool = False,
) -> None:
    img = Image.open(src).convert("RGBA")
    if key_magenta:
        img = fringe(chroma(img))
    small = img.resize((tw, th), Image.Resampling.BOX)
    if key_magenta:
        # Preserve alpha through quantize (opaque bg would otherwise bake sky).
        px = small.load()
        for y in range(small.height):
            for x in range(small.width):
                r, g, b, a = px[x, y]
                px[x, y] = (r, g, b, 255 if a >= 120 else 0)
        flat = Image.new("RGBA", small.size, (255, 0, 255, 255))
        flat.paste(small, mask=small.split()[3])
        q = flat.convert("RGB").quantize(
            colors=colors, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE
        ).convert("RGBA")
        qpx, spx = q.load(), small.load()
        for y in range(q.height):
            for x in range(q.width):
                r, g, b, _ = qpx[x, y]
                if (r, g, b) == (255, 0, 255) or spx[x, y][3] == 0:
                    qpx[x, y] = (0, 0, 0, 0)
                else:
                    qpx[x, y] = (r, g, b, 255)
        final = fringe(q.resize((tw * 2, th * 2), Image.Resampling.NEAREST))
    else:
        q = small.convert("RGB").quantize(
            colors=colors, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE
        ).convert("RGBA")
        final = q.resize((tw * 2, th * 2), Image.Resampling.NEAREST)
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(out)
    print(f"  {out.relative_to(ROOT)} {final.size}")


def _tint_sky(src: Path, out_raw: Path, mul: tuple[float, float, float]) -> None:
    img = Image.open(src).convert("RGBA")
    px = img.load()
    mr, mg, mb = mul
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            px[x, y] = (
                min(255, int(r * mr)),
                min(255, int(g * mg)),
                min(255, int(b * mb)),
                a,
            )
    out_raw.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_raw)


def make_scene_tiles() -> None:
    """Full-bleed tiles matching GameConstants: TILE=32, PLAT_TEX=96×28 @2×."""
    from PIL import ImageDraw

    pal = {
        "grass": (90, 168, 78, 255),
        "grass_l": (120, 196, 96, 255),
        "grass_d": (62, 128, 58, 255),
        "soil": (156, 110, 68, 255),
        "soil_d": (120, 82, 50, 255),
        "soil_dd": (92, 60, 36, 255),
        "soil_l": (180, 134, 88, 255),
        "wood": (168, 118, 70, 255),
        "wood_d": (128, 86, 50, 255),
        "wood_l": (198, 150, 96, 255),
    }

    def new(w: int, h: int) -> Image.Image:
        return Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def rect(im: Image.Image, x: int, y: int, w: int, h: int, c: tuple) -> None:
        ImageDraw.Draw(im).rectangle([x, y, x + w - 1, y + h - 1], fill=c)

    def put(im: Image.Image, x: int, y: int, c: tuple) -> None:
        if 0 <= x < im.width and 0 <= y < im.height:
            im.putpixel((x, y), c)

    # ground 16×16 @1× → 32×32 (TILE display width)
    g = new(16, 16)
    rect(g, 0, 0, 16, 16, pal["soil"])
    rect(g, 0, 4, 16, 12, pal["soil_d"])
    for x, y in ((2, 7), (7, 10), (12, 8), (5, 13), (11, 14)):
        put(g, x, y, pal["soil_dd"])
    for x, y in ((3, 6), (9, 9), (14, 12)):
        put(g, x, y, pal["soil_l"])
    rect(g, 0, 0, 16, 4, pal["grass"])
    rect(g, 0, 0, 16, 2, pal["grass_l"])
    for x in range(0, 16, 3):
        put(g, x, 0, pal["grass_d"])
        put(g, x + 1, 1, pal["grass_l"])
    g2 = g.resize((32, 32), Image.Resampling.NEAREST)
    TILES.mkdir(parents=True, exist_ok=True)
    g2.save(TILES / "ground.png")
    print(f"  tiles/ground.png {g2.size} (TILE=32)")

    # grass edge 16×5 → 32×10 (sits on ground lip)
    edge = new(16, 5)
    rect(edge, 0, 2, 16, 3, pal["soil"])
    rect(edge, 0, 0, 16, 3, pal["grass"])
    for x in (1, 4, 7, 10, 13):
        put(edge, x, 0, pal["grass_l"])
        put(edge, x + 1, 1, pal["grass_d"])
    e2 = edge.resize((32, 10), Image.Resampling.NEAREST)
    e2.save(TILES / "grass_edge.png")
    print(f"  tiles/grass_edge.png {e2.size}")

    # platform 48×14 → 96×28 = PLAT_TEX_W/H (full bleed, no empty margins)
    plat = new(48, 14)
    rect(plat, 0, 0, 48, 14, pal["wood_d"])
    rect(plat, 0, 0, 48, 11, pal["wood"])
    rect(plat, 0, 0, 48, 2, pal["wood_l"])
    for x in (12, 24, 36):
        rect(plat, x, 2, 1, 10, pal["wood_d"])
    for x in (3, 18, 33, 44):
        put(plat, x, 6, pal["wood_d"])
    for x in (6, 20, 34):
        put(plat, x, 0, pal["grass_l"])
        put(plat, x + 1, 0, pal["grass"])
    p2 = plat.resize((96, 28), Image.Resampling.NEAREST)
    p2.save(TILES / "platform.png")
    print(f"  tiles/platform.png {p2.size} (PLAT_TEX)")

    # cloud 48×20 → 96×40 (soft cutout, no black box)
    cloud = new(48, 20)
    for cx, cy, rw, rh in ((10, 10, 14, 10), (22, 8, 18, 12), (34, 11, 14, 9), (16, 14, 12, 8)):
        ImageDraw.Draw(cloud).ellipse(
            [cx - rw // 2, cy - rh // 2, cx + rw // 2, cy + rh // 2],
            fill=(248, 250, 255, 255),
        )
    for cx, cy, rw, rh in ((12, 14, 10, 6), (28, 15, 12, 6)):
        ImageDraw.Draw(cloud).ellipse(
            [cx - rw // 2, cy - rh // 2, cx + rw // 2, cy + rh // 2],
            fill=(210, 222, 235, 255),
        )
    c2 = cloud.resize((96, 40), Image.Resampling.NEAREST)
    DECOR.mkdir(parents=True, exist_ok=True)
    c2.save(DECOR / "cloud.png")
    print(f"  decor/cloud.png {c2.size}")


def cutout_prop(src: Path, out: Path, tw: int, th: int, colors: int = 48, px: int = 2) -> None:
    img = trim(fringe(chroma(Image.open(src).convert("RGBA"))))
    # 保持比例塞进 tw×th
    scale = min(tw / img.width, th / img.height)
    nw = max(1, round(img.width * scale))
    nh = max(1, round(img.height * scale))
    pix = hard_pixel(img, nw, nh, colors=colors)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(pix, ((tw - nw) // 2, th - nh), pix)
    final = canvas.resize((tw * px, th * px), Image.Resampling.NEAREST)
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(out)
    print(f"  {out.relative_to(ROOT)} {final.size}")


def process_dice() -> None:
    sync_raw("dice_ai.png")
    PROPS.mkdir(parents=True, exist_ok=True)
    cutout_prop(RAW / "dice_ai.png", PROPS / "dice.png", 16, 16, colors=32, px=2)


def process_title() -> None:
    """标题背景 2 帧横条（干净向日葵田，无变形树）。"""
    sync_raw("title_bg_anim_ai.png")
    _process_bg_anim_sheet(
        RAW / "title_bg_anim_ai.png",
        BG / "title_sheet.png",
        BG / "title.png",
        480,
        270,
        colors=48,
        key_magenta=False,
        split="vertical",
    )


def process_title_logo() -> None:
    """鹿历险记标题 Logo 横条动画（向日葵装饰，不含角色名）。

    抠图走统一 pixel_matte（含中段品红 AA / 深紫封边）；硬像素后再 fringe 一次。
    """
    sync_raw("title_logo_anim_ai.png")
    src = RAW / "title_logo_anim_ai.png"
    ui = ROOT / "assets" / "ui"
    ui.mkdir(parents=True, exist_ok=True)
    img = Image.open(src).convert("RGBA")
    n = 4
    cw = img.width // n
    parts: list[Image.Image] = []
    for i in range(n):
        cell = img.crop((i * cw, 0, (i + 1) * cw, img.height))
        cell = fringe(matte(cell, blob=True))
        cell = trim(cell, pad=2)
        if cell.width < 8 or cell.height < 8:
            print(f"  title_logo frame {i} empty after matte")
            cell = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
        else:
            assert_margin(cell, name=f"title_logo[{i}]")
        parts.append(cell)
        print(f"  title_logo[{i}] trimmed {cell.size}")

    mw = max(p.width for p in parts)
    mh = max(p.height for p in parts)
    tw = max(280, min(440, mw + 8))
    th = max(120, min(220, mh + 8))
    sheet = Image.new("RGBA", (tw * n, th), (0, 0, 0, 0))
    for i, part in enumerate(parts):
        scale = min((tw - 6) / part.width, (th - 6) / part.height)
        nw = max(1, round(part.width * scale))
        nh = max(1, round(part.height * scale))
        pix = hard_pixel(part, nw, nh, colors=56, pad="green", rematte=True)
        pix = fringe(pix)
        canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        canvas.paste(pix, ((tw - nw) // 2, (th - nh) // 2), pix)
        sheet.paste(canvas, (i * tw, 0), canvas)
    final = sheet.resize((tw * n * 2, th * 2), Image.Resampling.NEAREST)
    out = ui / "title_logo_sheet.png"
    final.save(out)
    final.crop((0, 0, tw * 2, th * 2)).save(ui / "title_logo.png")
    print(f"  {out.relative_to(ROOT)} {final.size} cell={tw}x{th}@1x → {tw*2}x{th*2}@2x frames={n}")
    print(f"  UPDATE SpriteFactory TITLE_LOGO_W/H = {tw*2}, {th*2}")


def process_skies() -> None:
    """Sky / mid 均为 ≥2 帧；mid 只留山丘，禁止变形树当中景。"""
    sync_raw("sky_anim_ai.png")
    sync_raw("mid_anim_ai.png")
    _process_bg_anim_sheet(
        RAW / "sky_anim_ai.png",
        BG / "sky_sheet.png",
        BG / "sky.png",
        480,
        180,
        colors=40,
        key_magenta=False,
        split="horizontal",
    )
    # dusk / creek：整条 sheet 着色
    _tint_sheet(BG / "sky_sheet.png", BG / "sky_dusk_sheet.png", (1.15, 0.85, 0.72))
    _tint_sheet(BG / "sky_sheet.png", BG / "sky_creek_sheet.png", (0.88, 0.95, 1.08))
    # 单帧回退
    Image.open(BG / "sky_dusk_sheet.png").crop((0, 0, 960, 360)).save(BG / "sky_dusk.png")
    Image.open(BG / "sky_creek_sheet.png").crop((0, 0, 960, 360)).save(BG / "sky_creek.png")
    _process_bg_anim_sheet(
        RAW / "mid_anim_ai.png",
        BG / "mid_sheet.png",
        BG / "mid.png",
        480,
        140,
        colors=36,
        key_magenta=True,
        bottom_align=True,
        split="vertical",
    )


def _split_anim_frames(
    img: Image.Image,
    n: int = 2,
    *,
    prefer: str = "auto",
) -> list[Image.Image]:
    """按中缝色差判断竖排/横排；prefer 可强制 vertical/horizontal。"""
    img = img.convert("RGBA")
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()

    def _band_diff(horizontal_seam: bool) -> float:
        acc = 0.0
        cnt = 0
        if horizontal_seam:
            y = h // 2
            for x in range(0, w, 2):
                r1, g1, b1 = px[x, max(0, y - 2)]
                r2, g2, b2 = px[x, min(h - 1, y + 1)]
                acc += abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
                cnt += 1
        else:
            x = w // 2
            for y in range(0, h, 2):
                r1, g1, b1 = px[max(0, x - 2), y]
                r2, g2, b2 = px[min(w - 1, x + 1), y]
                acc += abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
                cnt += 1
        return acc / max(1, cnt)

    if prefer == "vertical":
        use_vert = True
        print("  split=vertical (forced)")
    elif prefer == "horizontal":
        use_vert = False
        print("  split=horizontal (forced)")
    else:
        h_seam = _band_diff(True)
        v_seam = _band_diff(False)
        use_vert = h_seam >= v_seam
        print(f"  seam H={h_seam:.1f} V={v_seam:.1f} → {'vertical' if use_vert else 'horizontal'}")
    if use_vert:
        ch = h // n
        return [img.crop((0, i * ch, w, (i + 1) * ch)) for i in range(n)]
    cw = w // n
    return [img.crop((i * cw, 0, (i + 1) * cw, h)) for i in range(n)]


def _crop_to_aspect(img: Image.Image, aspect: float) -> Image.Image:
    """中心裁到目标比例，不拉伸。"""
    img = img.convert("RGBA")
    w, h = img.size
    if w < 2 or h < 2:
        return img
    cur = w / h
    if abs(cur - aspect) < 0.01:
        return img
    if cur > aspect:
        nw = max(1, int(round(h * aspect)))
        x0 = (w - nw) // 2
        return img.crop((x0, 0, x0 + nw, h))
    nh = max(1, int(round(w / aspect)))
    y0 = (h - nh) // 2
    return img.crop((0, y0, w, y0 + nh))


def _process_bg_anim_sheet(
    src: Path,
    sheet_out: Path,
    frame0_out: Path,
    tw: int,
    th: int,
    *,
    colors: int,
    key_magenta: bool,
    bottom_align: bool = False,
    split: str = "auto",
) -> None:
    """等比：先中心裁到 tw:th，再 BOX 缩小；禁止非等比拉伸变形。"""
    parts = _split_anim_frames(Image.open(src), 2, prefer=split)
    n = len(parts)
    aspect = tw / th
    sheet = Image.new("RGBA", (tw * n, th), (0, 0, 0, 0))
    for i, part in enumerate(parts):
        if key_magenta:
            part = fringe(matte(part, blob=False))
            part = trim(part, pad=2)
            if part.width < 4 or part.height < 4:
                print(f"  empty bg frame {i}")
                continue
            # 透明底山丘：等比塞进格子，不拉扁
            scale = min(tw / part.width, th / part.height)
            nw = max(1, round(part.width * scale))
            nh = max(1, round(part.height * scale))
            pix = hard_pixel(part, nw, nh, colors=colors, pad="green", rematte=True)
            pix = fringe(pix)
            canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            y = th - nh if bottom_align else (th - nh) // 2
            canvas.paste(pix, ((tw - nw) // 2, y), pix)
            sheet.paste(canvas, (i * tw, 0), canvas)
            print(f"  frame{i} src={part.size} -> fit {nw}x{nh} in {tw}x{th}")
        else:
            part = _crop_to_aspect(part, aspect)
            print(f"  frame{i} cropped={part.size} -> {tw}x{th} (aspect-kept)")
            small = part.resize((tw, th), Image.Resampling.BOX)
            q = small.convert("RGB").quantize(
                colors=colors, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE
            ).convert("RGBA")
            sheet.paste(q, (i * tw, 0))
    final = sheet.resize((tw * n * 2, th * 2), Image.Resampling.NEAREST)
    sheet_out.parent.mkdir(parents=True, exist_ok=True)
    final.save(sheet_out)
    final.crop((0, 0, tw * 2, th * 2)).save(frame0_out)
    print(f"  {sheet_out.relative_to(ROOT)} {final.size} frames={n}")


def _tint_sheet(src: Path, out: Path, mul: tuple[float, float, float]) -> None:
    img = Image.open(src).convert("RGBA")
    px = img.load()
    mr, mg, mb = mul
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            px[x, y] = (min(255, int(r * mr)), min(255, int(g * mg)), min(255, int(b * mb)), a)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"  tinted {out.relative_to(ROOT)}")


def process_door() -> None:
    sync_raw("door_ai.png")
    cutout_prop(RAW / "door_ai.png", TILES / "door.png", 48, 72, colors=56, px=2)


def process_tiles() -> None:
    """Prefer scene-sized full-bleed tiles (AI sheet left empty margins / pink fringe)."""
    make_scene_tiles()


def process_decor() -> None:
    sync_raw("decor_sheet_ai.png")
    parts = split_sheet(RAW / "decor_sheet_ai.png", 6)
    # tree,bush,fence,rock,flower — cloud from make_scene_tiles (exact slot size)
    specs = [
        (parts[0], DECOR / "tree.png", 48, 64),
        (parts[1], DECOR / "bush.png", 32, 24),
        (parts[2], DECOR / "fence.png", 24, 24),
        (parts[3], DECOR / "rock.png", 20, 14),
        (parts[4], DECOR / "flower.png", 14, 18),
    ]
    for part, out, tw, th in specs:
        cutout_prop_from_img(part, out, tw, th, colors=48, px=2)

    sync_raw("decor2_sheet_ai.png")
    parts2 = split_sheet(RAW / "decor2_sheet_ai.png", 5)
    specs2 = [
        (parts2[0], DECOR / "flower_pink.png", 14, 18),
        (parts2[1], DECOR / "crop.png", 16, 28),
        (parts2[2], DECOR / "moss.png", 16, 8),
        (parts2[3], DECOR / "petal.png", 10, 10),
        (parts2[4], SPRITES / "seed.png", 14, 10),
    ]
    for part, out, tw, th in specs2:
        cutout_prop_from_img(part, out, tw, th, colors=40, px=2)


def cutout_prop_from_img(img: Image.Image, out: Path, tw: int, th: int, colors: int, px: int) -> None:
    img = trim(fringe(img.convert("RGBA")))
    if img.width < 2 or img.height < 2:
        print(f"  skip empty {out.name}")
        return
    scale = min(tw / img.width, th / img.height)
    nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    pix = hard_pixel(img, nw, nh, colors=colors)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(pix, ((tw - nw) // 2, max(0, th - nh)), pix)
    final = canvas.resize((tw * px, th * px), Image.Resampling.NEAREST)
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(out)
    print(f"  {out.relative_to(ROOT)} {final.size}")


def process_tree() -> None:
    """单棵完整树 → decor/tree.png（48×64@1× → 96×128）。"""
    sync_raw("tree_ai.png")
    cutout_prop(RAW / "tree_ai.png", DECOR / "tree.png", 48, 64, colors=48, px=2)


def process_enemies() -> None:
    """敌人静态精细立绘 → 复制为多帧 sheet（后续可换真 walk 循环）。"""
    sync_raw("enemies_sheet_ai.png")
    parts = split_sheet(RAW / "enemies_sheet_ai.png", 4)
    specs = [
        (parts[0], ENEMIES / "enemy_bug_sheet.png", 36, 28, 4),
        (parts[1], ENEMIES / "enemy_weed_sheet.png", 32, 44, 4),
        (parts[2], ENEMIES / "enemy_flyer_sheet.png", 48, 36, 4),
        (parts[3], ENEMIES / "enemy_boss_sheet.png", 72, 72, 4),
    ]
    ENEMIES.mkdir(parents=True, exist_ok=True)
    singles = [
        SPRITES / "enemy_bug.png",
        SPRITES / "enemy_weed.png",
        SPRITES / "enemy_flyer.png",
        SPRITES / "enemy_boss.png",
    ]
    for i, (part, out, tw, th, frames) in enumerate(specs):
        img = trim(fringe(part.convert("RGBA")))
        scale = min(tw / max(1, img.width), th / max(1, img.height))
        nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
        pix = hard_pixel(img, nw, nh, colors=48)
        cell = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        cell.paste(pix, ((tw - nw) // 2, th - nh), pix)
        # slight bob variants for faux anim
        sheet = Image.new("RGBA", (tw * frames, th), (0, 0, 0, 0))
        for f in range(frames):
            fr = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            dy = (0, -1, 0, 1)[f % 4]
            fr.paste(cell, (0, dy), cell)
            sheet.paste(fr, (f * tw, 0), fr)
        final = sheet.resize((tw * frames * 2, th * 2), Image.Resampling.NEAREST)
        final.save(out)
        # single preview icon
        icon = cell.resize((tw * 2, th * 2), Image.Resampling.NEAREST)
        icon.save(singles[i])
        print(f"  {out.relative_to(ROOT)} {final.size} + {singles[i].name}")


def process_all_world() -> None:
    print("=== skies / mid ===")
    process_skies()
    print("=== door ===")
    process_door()
    print("=== tiles ===")
    process_tiles()
    print("=== decor ===")
    process_decor()
    print("=== tree (AI single) ===")
    try:
        process_tree()
    except SystemExit as e:
        print("skip tree:", e)
    print("=== flyer (AI sheet) ===")
    try:
        process_flyer()
    except SystemExit as e:
        print("skip flyer:", e)
    print("=== enemies ===")
    try:
        process_enemies()
    except SystemExit as e:
        print("skip enemies:", e)
    print("=== dice / title (if present) ===")
    if (CURSOR_ASSETS / "dice_ai.png").is_file() or (RAW / "dice_ai.png").is_file():
        process_dice()
    if (CURSOR_ASSETS / "title_bg_ai.png").is_file() or (RAW / "title_bg_ai.png").is_file():
        process_title()
    if (CURSOR_ASSETS / "title_logo_anim_ai.png").is_file() or (RAW / "title_logo_anim_ai.png").is_file():
        process_title_logo()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--what",
        default="world",
        choices=[
            "dice",
            "title",
            "title_logo",
            "skies",
            "door",
            "tiles",
            "decor",
            "tree",
            "flyer",
            "enemies",
            "world",
            "all",
        ],
    )
    args = ap.parse_args()
    if args.what == "dice":
        process_dice()
    elif args.what == "title":
        process_title()
    elif args.what == "title_logo":
        process_title_logo()
    elif args.what == "skies":
        process_skies()
    elif args.what == "door":
        process_door()
    elif args.what == "tiles":
        process_tiles()
    elif args.what == "decor":
        process_decor()
    elif args.what == "tree":
        process_tree()
    elif args.what == "flyer":
        process_flyer()
    elif args.what == "enemies":
        process_enemies()
    elif args.what in ("world", "all"):
        process_all_world()
    print("Done", args.what)


if __name__ == "__main__":
    main()
