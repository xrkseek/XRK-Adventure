#!/usr/bin/env python3
"""世界 / 敌人 / 道具 AI→硬像素（角色请用 process_character.py）。"""
from __future__ import annotations

import argparse
import json
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
GEN_SPEC_PATH = Path(__file__).resolve().parent / "gen_spec.json"


def load_gen_spec() -> dict:
    return json.loads(GEN_SPEC_PATH.read_text(encoding="utf-8"))


def gen_spec() -> dict:
    if not hasattr(gen_spec, "_cache"):
        gen_spec._cache = load_gen_spec()  # type: ignore[attr-defined]
    return gen_spec._cache  # type: ignore[attr-defined]


def sync_raw(name: str) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    dst = RAW / name
    src = CURSOR_ASSETS / name
    if src.is_file():
        shutil.copy2(src, dst)
    if not dst.is_file():
        raise SystemExit(f"Missing AI raw: {dst} (and {src})")
    return dst


def try_sync_raw(name: str) -> Path | None:
    RAW.mkdir(parents=True, exist_ok=True)
    dst = RAW / name
    src = CURSOR_ASSETS / name
    if src.is_file():
        shutil.copy2(src, dst)
    return dst if dst.is_file() else None


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
    """通用兜底 + 各主题满幅硬像素 tiles（禁止 AI 抠图残留）。"""
    _write_tile_set(TILES, _TILE_PALETTES["meadow"], also_cloud=True)
    for sid, pal in _TILE_PALETTES.items():
        _write_tile_set(TILES / sid, pal, also_cloud=False)


_TILE_PALETTES: dict[str, dict[str, tuple[int, int, int, int]]] = {
    "meadow": {
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
        "accent": (230, 210, 90, 255),
    },
    "orchard": {
        "grass": (78, 148, 72, 255),
        "grass_l": (110, 178, 90, 255),
        "grass_d": (52, 112, 54, 255),
        "soil": (148, 98, 62, 255),
        "soil_d": (112, 72, 44, 255),
        "soil_dd": (84, 52, 32, 255),
        "soil_l": (172, 122, 78, 255),
        "wood": (158, 108, 64, 255),
        "wood_d": (118, 78, 46, 255),
        "wood_l": (188, 140, 88, 255),
        "accent": (210, 70, 64, 255),  # 落果红
    },
    "creek": {
        "grass": (72, 140, 110, 255),
        "grass_l": (96, 168, 132, 255),
        "grass_d": (48, 108, 88, 255),
        "soil": (110, 96, 78, 255),
        "soil_d": (78, 72, 64, 255),
        "soil_dd": (54, 52, 50, 255),
        "soil_l": (140, 132, 118, 255),
        "wood": (120, 128, 132, 255),  # 石台
        "wood_d": (86, 92, 98, 255),
        "wood_l": (158, 164, 168, 255),
        "accent": (64, 150, 140, 255),
    },
    "dusk": {
        "grass": (168, 110, 58, 255),
        "grass_l": (210, 140, 70, 255),
        "grass_d": (128, 72, 40, 255),
        "soil": (132, 78, 52, 255),
        "soil_d": (98, 54, 36, 255),
        "soil_dd": (72, 40, 28, 255),
        "soil_l": (160, 100, 68, 255),
        "wood": (120, 78, 52, 255),
        "wood_d": (88, 54, 36, 255),
        "wood_l": (160, 108, 72, 255),
        "accent": (220, 90, 48, 255),  # 枫叶
    },
    "cliff": {
        "grass": (96, 120, 88, 255),
        "grass_l": (124, 148, 108, 255),
        "grass_d": (68, 92, 70, 255),
        "soil": (118, 112, 108, 255),
        "soil_d": (88, 84, 82, 255),
        "soil_dd": (58, 56, 56, 255),
        "soil_l": (150, 146, 140, 255),
        "wood": (130, 128, 126, 255),
        "wood_d": (96, 94, 92, 255),
        "wood_l": (168, 166, 162, 255),
        "accent": (90, 140, 100, 255),
    },
}


def _write_tile_set(
    out_dir: Path,
    pal: dict[str, tuple[int, int, int, int]],
    *,
    also_cloud: bool,
) -> None:
    from PIL import ImageDraw

    def new(w: int, h: int) -> Image.Image:
        return Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def rect(im: Image.Image, x: int, y: int, w: int, h: int, c: tuple) -> None:
        ImageDraw.Draw(im).rectangle([x, y, x + w - 1, y + h - 1], fill=c)

    def put(im: Image.Image, x: int, y: int, c: tuple) -> None:
        if 0 <= x < im.width and 0 <= y < im.height:
            im.putpixel((x, y), c)

    out_dir.mkdir(parents=True, exist_ok=True)

    # ground 16×16 @1× → 32×32
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
    if "accent" in pal:
        put(g, 4, 1, pal["accent"])
        put(g, 11, 0, pal["accent"])
    g2 = g.resize((32, 32), Image.Resampling.NEAREST)
    g2.save(out_dir / "ground.png")
    print(f"  {out_dir.relative_to(ROOT)}/ground.png {g2.size}")

    edge = new(16, 5)
    rect(edge, 0, 2, 16, 3, pal["soil"])
    rect(edge, 0, 0, 16, 3, pal["grass"])
    for x in (1, 4, 7, 10, 13):
        put(edge, x, 0, pal["grass_l"])
        put(edge, x + 1, 1, pal["grass_d"])
    if "accent" in pal:
        put(edge, 6, 0, pal["accent"])
    e2 = edge.resize((32, 10), Image.Resampling.NEAREST)
    e2.save(out_dir / "grass_edge.png")
    print(f"  {out_dir.relative_to(ROOT)}/grass_edge.png {e2.size}")

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
    if "accent" in pal:
        put(plat, 10, 0, pal["accent"])
        put(plat, 28, 1, pal["accent"])
    p2 = plat.resize((96, 28), Image.Resampling.NEAREST)
    p2.save(out_dir / "platform.png")
    print(f"  {out_dir.relative_to(ROOT)}/platform.png {p2.size}")

    if also_cloud:
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
    """标题场景 scene_title：上下双帧微动超宽景。"""
    process_scene("title")


# 关卡/标题场景真源：id → 显示名（尺寸见 tools/gen_spec.json）
def _scene_names() -> dict[str, str]:
    return dict(gen_spec()["scene"]["names"])


SCENE_SPECS: dict[str, str] = {}  # filled lazily via _scene_names()


def _scene_raw_candidates(scene_id: str) -> list[str]:
    """新名优先，旧名仅做迁移兼容（不把云海误挂到草地）。"""
    names = [f"scene_{scene_id}_ai.png"]
    legacy = {
        "title": ["title_ai.png", "title_bg_anim_ai.png", "title_bg_ai.png"],
        "creek": ["sky_creek_ai.png", "sky_creek_anim_ai.png"],
        "dusk": ["sky_dusk_ai.png", "sky_dusk_anim_ai.png"],
    }
    names.extend(legacy.get(scene_id, []))
    return names


def process_scene(scene_id: str) -> None:
    specs = _scene_names()
    if scene_id not in specs:
        raise SystemExit(f"unknown scene id: {scene_id} (want {list(specs)})")
    src = None
    for name in _scene_raw_candidates(scene_id):
        src = try_sync_raw(name)
        if src is not None:
            canon = RAW / f"scene_{scene_id}_ai.png"
            if src.resolve() != canon.resolve():
                shutil.copy2(src, canon)
                src = canon
            break
    if src is None:
        raise SystemExit(f"need raw for scene '{scene_id}': scene_{scene_id}_ai.png")
    cook = gen_spec()["scene"]["cook"]
    print(f"=== scene:{scene_id} ({specs[scene_id]}) ===")
    _process_bg_anim_sheet(
        src,
        BG / f"scene_{scene_id}_sheet.png",
        BG / f"scene_{scene_id}.png",
        0,
        int(cook["frame_h_1x"]),
        colors=48 if scene_id == "title" else int(cook["colors"]),
        key_magenta=False,
        split=str(cook["split"]),
        keep_wide=bool(cook["keep_wide"]),
        subtle=True,
        min_aspect=float(cook["min_aspect"]),
    )


def process_scenes(ids: list[str] | None = None) -> None:
    """处理全部或指定场景；缺 raw 的跳过并列出。"""
    specs = _scene_names()
    todo = ids if ids else list(specs.keys())
    missing: list[str] = []
    for sid in todo:
        try:
            process_scene(sid)
        except SystemExit as e:
            print(f"  skip {sid}: {e}")
            missing.append(sid)
    if missing:
        print("MISSING scenes (regen AI → assets/raw/scene_<id>_ai.png):", ", ".join(missing))


def process_skies() -> None:
    """兼容旧命令：关卡场景（不含 title）。"""
    process_scenes([i for i in _scene_names() if i != "title"])


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


def _frame_diff_mean(a: Image.Image, b: Image.Image) -> float:
    a = a.convert("RGB").resize((64, 36), Image.Resampling.BOX)
    b = b.convert("RGB").resize((64, 36), Image.Resampling.BOX)
    pa, pb = a.load(), b.load()
    acc = 0.0
    n = a.width * a.height
    for y in range(a.height):
        for x in range(a.width):
            r1, g1, b1 = pa[x, y]
            r2, g2, b2 = pb[x, y]
            acc += abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
    return acc / max(1, n * 3)


def _subtle_second_frame(base: Image.Image, *, shift_px: int = 6) -> Image.Image:
    """同一景微动：水平滚一点，避免上下半幅色光差太大。"""
    base = base.convert("RGBA")
    w, h = base.size
    sx = max(1, min(shift_px, w // 40))
    out = Image.new("RGBA", (w, h))
    # 左移缝：右侧补左侧条带（环绕，无黑边）
    left = base.crop((sx, 0, w, h))
    right = base.crop((0, 0, sx, h))
    out.paste(left, (0, 0))
    out.paste(right, (w - sx, 0))
    return out


def _pair_subtle_frames(parts: list[Image.Image], *, max_diff: float = 10.0) -> list[Image.Image]:
    """双帧必须接近：差异大则丢弃下半幅，用上半幅微位移做第 2 帧。"""
    if len(parts) < 2:
        base = parts[0]
        return [base, _subtle_second_frame(base)]
    a, b = parts[0], parts[1]
    # 对齐尺寸再比
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.BOX)
    d = _frame_diff_mean(a, b)
    if d <= max_diff:
        print(f"  subtle OK diff={d:.1f} (keep AI pair)")
        return [a, b]
    print(f"  subtle FAIL diff={d:.1f} > {max_diff} → micro-shift from frame0")
    return [a, _subtle_second_frame(a)]


def _crop_to_min_aspect(img: Image.Image, min_aspect: float) -> Image.Image:
    """若不够宽，中心裁高，拉成更超宽横幅（左右更开）。"""
    img = img.convert("RGBA")
    w, h = img.size
    if w < 2 or h < 2:
        return img
    cur = w / h
    if cur >= min_aspect - 0.01:
        return img
    nh = max(1, int(round(w / min_aspect)))
    y0 = max(0, (h - nh) // 2)
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
    keep_wide: bool = False,
    subtle: bool = False,
    min_aspect: float = 0.0,
) -> None:
    """BOX 缩小 + 量化；keep_wide=按高缩放；min_aspect>0 时先裁成更超宽。"""
    parts = _split_anim_frames(Image.open(src), 2, prefer=split)
    if subtle and not key_magenta:
        parts = _pair_subtle_frames(parts)
    if min_aspect > 0 and not key_magenta:
        parts = [_crop_to_min_aspect(p, min_aspect) for p in parts]
        print(f"  ultra-wide crop aspect≥{min_aspect:.2f} → {[p.size for p in parts]}")
    n = len(parts)
    cooked: list[Image.Image] = []
    for i, part in enumerate(parts):
        if key_magenta:
            part = fringe(matte(part, blob=False))
            part = trim(part, pad=2)
            if part.width < 4 or part.height < 4:
                print(f"  empty bg frame {i}")
                cooked.append(Image.new("RGBA", (max(1, tw), th), (0, 0, 0, 0)))
                continue
            cell_w = tw if tw > 0 else max(480, int(round(th * part.width / max(1, part.height))))
            scale = min(cell_w / part.width, th / part.height)
            nw = max(1, round(part.width * scale))
            nh = max(1, round(part.height * scale))
            pix = hard_pixel(part, nw, nh, colors=colors, pad="green", rematte=True)
            pix = fringe(pix)
            canvas = Image.new("RGBA", (cell_w, th), (0, 0, 0, 0))
            y = th - nh if bottom_align else (th - nh) // 2
            canvas.paste(pix, ((cell_w - nw) // 2, y), pix)
            cooked.append(canvas)
            print(f"  frame{i} src={part.size} -> fit {nw}x{nh} in {cell_w}x{th}")
        elif keep_wide:
            # 对齐 VIEW 高：th@1x → ×2 后约 720，局内 1:1 不糊
            scale = th / max(1, part.height)
            nw = max(1, round(part.width * scale))
            nh = th
            # BOX 到 2× 目标再 NEAREST 回目标 → 块更硬
            mid = part.resize((nw * 2, nh * 2), Image.Resampling.BOX)
            q = mid.convert("RGB").quantize(
                colors=colors, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE
            ).convert("RGBA")
            q = q.resize((nw, nh), Image.Resampling.NEAREST)
            cooked.append(q)
            print(f"  frame{i} src={part.size} -> wide {nw}x{nh} (aspect={nw/nh:.2f})")
        else:
            aspect = tw / th
            part = _crop_to_aspect(part, aspect)
            print(f"  frame{i} cropped={part.size} -> {tw}x{th} (aspect-kept)")
            small = part.resize((tw, th), Image.Resampling.BOX)
            q = small.convert("RGB").quantize(
                colors=colors, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE
            ).convert("RGBA")
            cooked.append(q)
    cell_w = max(p.width for p in cooked)
    cell_h = th
    sheet = Image.new("RGBA", (cell_w * n, cell_h), (0, 0, 0, 0))
    for i, q in enumerate(cooked):
        x = i * cell_w + (cell_w - q.width) // 2
        sheet.paste(q, (x, 0), q if q.mode == "RGBA" else None)
    final = sheet.resize((cell_w * n * 2, cell_h * 2), Image.Resampling.NEAREST)
    sheet_out.parent.mkdir(parents=True, exist_ok=True)
    final.save(sheet_out)
    final.crop((0, 0, cell_w * 2, cell_h * 2)).save(frame0_out)
    print(f"  {sheet_out.relative_to(ROOT)} {final.size} cell={cell_w*2}x{cell_h*2}@2x frames={n}")


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
    """主题地面/平台：每个部件单独 AI（ground|edge|platform），禁止三格拼图。"""
    print("=== theme tiles (single-part AI / gen_spec) ===")
    ids = list(gen_spec()["tiles"]["ids"])
    parts = list(gen_spec()["tiles"]["parts"])
    ok = 0
    for sid in ids:
        for part in parts:
            src = try_sync_raw(f"tiles_{sid}_{part}_ai.png")
            if src is None:
                print(f"  skip {sid}/{part}: no tiles_{sid}_{part}_ai.png")
                continue
            try:
                _cook_tile_part_ai(sid, part, src)
                ok += 1
            except Exception as e:
                print(f"  FAIL {sid}/{part}: {e}")
    _write_tile_set(TILES, _TILE_PALETTES["meadow"], also_cloud=True)
    if gen_spec()["tiles"].get("palette_fallback", True):
        for sid in ids:
            out_dir = TILES / sid
            need = []
            mapping = {"ground": "ground.png", "edge": "grass_edge.png", "platform": "platform.png"}
            for part, fname in mapping.items():
                if not (out_dir / fname).is_file():
                    need.append(fname)
            if need:
                print(f"  fill {sid} missing {need} via palette")
                _write_tile_set(out_dir, _TILE_PALETTES[sid], also_cloud=False)
    print(f"  AI-cooked parts: {ok}")


def _cook_tile_part_ai(scene_id: str, part: str, src: Path) -> None:
    """单部件：matte → hard_pixel → 清屏键。"""
    cook_all = gen_spec()["tiles"]["cook"]
    if part not in cook_all:
        raise RuntimeError(f"unknown part {part}")
    cfg = cook_all[part]
    tw, th = int(cfg["w"]), int(cfg["h"])
    opaque = bool(cfg["opaque"])
    colors = int(cfg["colors"])
    pad = str(cook_all.get("pad", "green"))
    out_name = str(cfg.get("out", f"{part}.png"))
    if part == "edge":
        out_name = "grass_edge.png"
    elif part == "ground":
        out_name = "ground.png"
    elif part == "platform":
        out_name = "platform.png"

    raw = Image.open(src).convert("RGBA")
    cell = fringe(matte(raw, blob=True))
    cell = trim(cell, pad=2)
    cell = _kill_screen_pixels(cell)
    if cell.width < 6 or cell.height < 4:
        raise RuntimeError(f"{part} empty after matte")

    if opaque:
        scale = min(tw * 3 / cell.width, th * 3 / cell.height)
        nw = max(tw, round(cell.width * scale))
        nh = max(th, round(cell.height * scale))
        pix = hard_pixel(cell, nw, nh, colors=colors, pad=pad, rematte=True)
        pix = fringe(_kill_screen_pixels(pix))
        pix = _fill_opaque_cell(pix, tw, th)
    else:
        pix = hard_pixel(cell, tw, th, colors=colors, pad=pad, rematte=True)
        pix = fringe(_kill_screen_pixels(pix))
        canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        canvas.paste(pix, ((tw - pix.width) // 2, th - pix.height), pix)
        pix = canvas

    pix = _kill_screen_pixels(pix)
    out_dir = TILES / scene_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / out_name
    pix.save(path)
    from pixel_matte import is_screen_key

    px = pix.load()
    bad = sum(
        1
        for y in range(pix.height)
        for x in range(pix.width)
        if px[x, y][3] > 20 and is_screen_key(*px[x, y][:3], px[x, y][3])
    )
    print(f"  {path.relative_to(ROOT)} {pix.size} screen_left={bad}")
    if bad:
        raise RuntimeError(f"{scene_id}/{out_name} screen residue ({bad})")


def print_gen_prompt(kind: str, theme_id: str = "meadow", part: str = "ground") -> None:
    """打印统一生图 prompt（助手/人工共用）。"""
    spec = gen_spec()
    if kind == "scene":
        name = spec["scene"]["names"].get(theme_id, theme_id)
        ai = spec["scene"]["ai"]
        must = "; ".join(ai["prompt_must"])
        print(
            f"SCENE {theme_id} ({name})\n"
            f"aspect={ai['aspect']} layout={ai['layout']}\n"
            f"style: {ai['style']}\n"
            f"MUST: {must}\n"
            f"theme: {name}. Out: scene_{theme_id}_ai.png"
        )
    elif kind == "tiles":
        ai = spec["tiles"]["ai"]
        cook = spec["tiles"]["cook"]
        theme = spec["tiles"]["themes"].get(theme_id, theme_id)
        if part not in ai["parts"]:
            raise SystemExit(f"part want {list(ai['parts'])}")
        p = ai["parts"][part]
        common = "; ".join(ai["prompt_common"])
        must = "; ".join(p["must"])
        ckey = "edge" if part == "edge" else part
        if ckey == "edge":
            ckey = "edge"
        sz = cook[part]
        print(
            f"TILE PART {theme_id}/{part}\n"
            f"theme: {theme}\n"
            f"aspect={p['aspect']} screen={ai['screen']}\n"
            f"style: {ai['style']}\n"
            f"COMMON: {common}\n"
            f"PART MUST: {must}\n"
            f"cook: {sz['w']}x{sz['h']} opaque={sz['opaque']}\n"
            f"Out: tiles_{theme_id}_{part}_ai.png"
        )
    else:
        raise SystemExit("kind want scene|tiles")


def _kill_screen_pixels(img: Image.Image) -> Image.Image:
    from pixel_matte import is_screen_key

    img = img.convert("RGBA")
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a > 0 and is_screen_key(r, g, b, a):
                px[x, y] = (0, 0, 0, 0)
    return img


def _fill_opaque_cell(img: Image.Image, tw: int, th: int) -> Image.Image:
    """地面/平台必须满格不透：cover 装格，空洞用中位土色填。"""
    img = trim(img, pad=0)
    if img.width < 2 or img.height < 2:
        return Image.new("RGBA", (tw, th), (120, 82, 50, 255))
    scale = max(tw / img.width, th / img.height)
    nw = max(1, round(img.width * scale))
    nh = max(1, round(img.height * scale))
    scaled = img.resize((nw, nh), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(scaled, ((tw - nw) // 2, (th - nh) // 2), scaled)
    # 采样不透明像素中位色
    px = canvas.load()
    samples: list[tuple[int, int, int]] = []
    for y in range(th):
        for x in range(tw):
            r, g, b, a = px[x, y]
            if a >= 200:
                samples.append((r, g, b))
    if not samples:
        fill = (120, 82, 50)
    else:
        samples.sort()
        fill = samples[len(samples) // 2]
    for y in range(th):
        for x in range(tw):
            if px[x, y][3] < 200:
                px[x, y] = (*fill, 255)
            else:
                r, g, b, _ = px[x, y]
                px[x, y] = (r, g, b, 255)
    return canvas


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
        (parts[3], ENEMIES / "enemy_boss_sheet.png", 120, 120, 4),
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
    print("=== scenes ===")
    process_scenes()
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
    print("=== dice / title logo (if present) ===")
    if (CURSOR_ASSETS / "dice_ai.png").is_file() or (RAW / "dice_ai.png").is_file():
        process_dice()
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
            "scenes",
            "skies",
            "door",
            "tiles",
            "decor",
            "tree",
            "flyer",
            "enemies",
            "world",
            "all",
            "prompt",
            "spec",
        ],
    )
    ap.add_argument(
        "--id",
        default="",
        help="id for scenes|title|prompt (title|meadow|orchard|creek|dusk|cliff)",
    )
    ap.add_argument(
        "--kind",
        default="scene",
        choices=["scene", "tiles"],
        help="with --what prompt",
    )
    ap.add_argument(
        "--part",
        default="ground",
        choices=["ground", "edge", "platform"],
        help="tile part with --what prompt --kind tiles",
    )
    args = ap.parse_args()
    if args.what == "spec":
        print(GEN_SPEC_PATH)
        print(json.dumps(gen_spec(), ensure_ascii=False, indent=2)[:2000], "...")
    elif args.what == "prompt":
        print_gen_prompt(args.kind, args.id or "meadow", args.part)
    elif args.what == "dice":
        process_dice()
    elif args.what == "title":
        process_scene(args.id or "title")
    elif args.what == "title_logo":
        process_title_logo()
    elif args.what in ("scenes", "skies"):
        if args.id:
            process_scene(args.id)
        elif args.what == "skies":
            process_skies()
        else:
            process_scenes()
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
