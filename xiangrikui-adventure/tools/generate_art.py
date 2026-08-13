#!/usr/bin/env python3
"""Stardew-inspired pixel art for 向日葵历险记 — multi-frame, soft shade, scenic props."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
ANIM = SPRITES / "anim"
TILES = ROOT / "assets" / "tiles"
UI = ROOT / "assets" / "ui"
BG = ROOT / "assets" / "bg"
DECOR = ROOT / "assets" / "decor"

# 1× pixel grid → nearest upscale (Stardew-like crisp pixels)
PX = 2

# Soft farm palette — warm sky, layered greens, soil depth (Stardew-adjacent)
PAL = {
    "sky0": (120, 186, 230, 255),
    "sky1": (168, 214, 240, 255),
    "sky2": (210, 234, 248, 255),
    "cloud": (255, 255, 255, 220),
    "cloud_s": (210, 225, 235, 200),
    "sun": (255, 236, 140, 255),
    "sun_c": (255, 214, 80, 255),
    "hill_f": (78, 150, 88, 255),
    "hill_m": (58, 122, 72, 255),
    "hill_b": (42, 96, 58, 255),
    "tree": (52, 118, 64, 255),
    "tree_d": (34, 86, 48, 255),
    "tree_l": (86, 160, 90, 255),
    "bark": (110, 78, 48, 255),
    "bark_d": (78, 52, 32, 255),
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
    "petal": (255, 220, 70, 255),
    "petal_d": (240, 180, 40, 255),
    "petal_l": (255, 240, 140, 255),
    "center": (120, 68, 36, 255),
    "center_d": (82, 44, 22, 255),
    "center_l": (150, 92, 50, 255),
    "stem": (56, 140, 72, 255),
    "stem_d": (36, 108, 54, 255),
    "leaf": (72, 170, 88, 255),
    "leaf_d": (44, 128, 62, 255),
    "cream": (255, 248, 220, 255),
    "ink": (36, 40, 32, 255),
    "cheek": (255, 170, 140, 255),
    "bug": (110, 84, 64, 255),
    "bug_l": (150, 118, 88, 255),
    "bug_d": (72, 52, 40, 255),
    "weed": (68, 140, 56, 255),
    "weed_d": (44, 100, 40, 255),
    "weed_f": (220, 72, 64, 255),
    "weed_fl": (255, 120, 100, 255),
    "flyer": (230, 130, 150, 255),
    "flyer_l": (255, 180, 190, 255),
    "flyer_d": (180, 80, 110, 255),
    "flyer_w": (255, 230, 235, 255),
    "boss_p": (180, 120, 50, 255),
    "boss_pd": (140, 90, 36, 255),
    "boss_c": (48, 28, 18, 255),
    "danger": (230, 70, 60, 255),
    "fence": (140, 100, 60, 255),
    "fence_d": (100, 70, 42, 255),
    "rock": (140, 140, 132, 255),
    "rock_d": (100, 100, 96, 255),
    "rock_l": (180, 180, 172, 255),
    "flower_p": (255, 140, 180, 255),
    "flower_b": (120, 170, 255, 255),
    "white": (255, 255, 255, 255),
}


def new(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def px(img: Image.Image, x: int, y: int, c: tuple) -> None:
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), c)


def fill_rect(img: Image.Image, x: int, y: int, w: int, h: int, c: tuple) -> None:
    ImageDraw.Draw(img).rectangle([x, y, x + w - 1, y + h - 1], fill=c)


def ellipse(img: Image.Image, x0: int, y0: int, x1: int, y1: int, c: tuple) -> None:
    ImageDraw.Draw(img).ellipse([x0, y0, x1, y1], fill=c)


def save(img: Image.Image, path: Path, scale: int = PX) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = img if scale == 1 else img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    out.save(path)
    print(f"  {path.relative_to(ROOT)} ({out.width}x{out.height})")


def hsheet(frames: list[Image.Image], path: Path, scale: int = PX) -> None:
    w, h = frames[0].width, frames[0].height
    sheet = new(w * len(frames), h)
    for i, f in enumerate(frames):
        sheet.paste(f, (i * w, 0), f)
    save(sheet, path, scale=scale)


# --- Player (48x56) — denser sunflower hero ---

def _petals(img: Image.Image, cx: int, cy: int, rot: float = 0.0) -> None:
    for ring, rad, half_w, half_h in ((0, 12, 5, 4), (1, 11, 4, 3)):
        n = 12 if ring == 0 else 10
        for i in range(n):
            a = i / n * math.pi * 2 + rot + (0.12 if ring else 0.0)
            ox = int(cx + math.cos(a) * rad)
            oy = int(cy + math.sin(a) * (rad - 1))
            if ring == 0:
                col = PAL['petal_d'] if i % 2 == 0 else PAL['petal']
            else:
                col = PAL['petal_l'] if i % 3 == 0 else PAL['petal']
            ellipse(img, ox - half_w, oy - half_h, ox + half_w, oy + half_h, col)
            if ring == 1:
                px(img, ox, oy - half_h + 1, PAL['petal_l'])


def draw_player(
    sway: int = 0,
    bob: int = 0,
    leg: int = 0,
    jump: bool = False,
    petal_rot: float = 0.0,
) -> Image.Image:
    img = new(48, 56)
    cx = 24 + sway
    cy = 16 - bob
    if not jump:
        ellipse(img, cx - 8, 50, cx + 8, 54, (40, 50, 30, 70))
    top = 26 - bob
    bot = 48 if not jump else 42
    for y in range(top, bot):
        px(img, cx - 2, y, PAL['stem_d'])
        px(img, cx - 1, y, PAL['stem'])
        px(img, cx, y, PAL['leaf'])
        px(img, cx + 1, y, PAL['stem'])
        if y % 3 == 0:
            px(img, cx + 2, y, PAL['stem_d'])
    ly = 32 - bob
    fill_rect(img, cx - 14, ly, 11, 4, PAL['leaf'])
    fill_rect(img, cx - 13, ly + 1, 9, 2, PAL['leaf_d'])
    px(img, cx - 9, ly + 1, PAL['stem'])
    fill_rect(img, cx + 3, ly + 2, 11, 4, PAL['leaf'])
    fill_rect(img, cx + 4, ly + 3, 9, 2, PAL['leaf_d'])
    px(img, cx + 8, ly + 3, PAL['stem'])
    fill_rect(img, cx - 8, 28 - bob, 6, 2, PAL['leaf'])
    if jump:
        fill_rect(img, cx - 4, 42, 8, 3, PAL['soil_d'])
        px(img, cx - 3, 43, PAL['soil_l'])
    else:
        l_off = (-3, -1, 2, 0)[leg % 4]
        r_off = (3, 1, -2, 0)[leg % 4]
        fill_rect(img, cx - 7 + l_off, 48, 5, 4, PAL['soil_d'])
        fill_rect(img, cx - 6 + l_off, 49, 3, 2, PAL['soil'])
        fill_rect(img, cx + 2 + r_off, 48, 5, 4, PAL['soil_d'])
        fill_rect(img, cx + 3 + r_off, 49, 3, 2, PAL['soil'])
        px(img, cx - 5 + l_off, 51, PAL['soil_dd'])
        px(img, cx + 5 + r_off, 51, PAL['soil_dd'])
    _petals(img, cx, cy, petal_rot)
    ellipse(img, cx - 9, cy - 9, cx + 9, cy + 9, PAL['center_d'])
    ellipse(img, cx - 8, cy - 8, cx + 8, cy + 8, PAL['center'])
    ellipse(img, cx - 6, cy - 5, cx + 6, cy + 5, PAL['center_l'])
    for sx, sy in ((-3, -2), (2, -3), (-1, 1), (3, 0), (0, -4), (-4, 1)):
        px(img, cx + sx, cy + sy, PAL['center_d'])
    for ex in (-4, 4):
        fill_rect(img, cx + ex - 1, cy - 2, 3, 3, PAL['cream'])
        px(img, cx + ex, cy - 1, PAL['ink'])
        px(img, cx + ex - 1, cy - 2, PAL['white'])
    px(img, cx - 5, cy - 4, PAL['ink'])
    px(img, cx - 4, cy - 4, PAL['ink'])
    px(img, cx + 3, cy - 4, PAL['ink'])
    px(img, cx + 4, cy - 4, PAL['ink'])
    px(img, cx - 7, cy + 1, PAL['cheek'])
    px(img, cx + 7, cy + 1, PAL['cheek'])
    for dx, dy in ((-3, 3), (-2, 4), (-1, 5), (0, 5), (1, 5), (2, 4), (3, 3)):
        px(img, cx + dx, cy + dy, PAL['cream'])
    return img


def make_player() -> None:
    import process_character as _char

    _char.process_all(_char.load_profile("xuyuezhen"))


# --- Enemies ---

def draw_bug(frame: int) -> Image.Image:
    img = new(36, 28)
    lx = (-1, 0, 1, 0)[frame % 4]
    ellipse(img, 6, 8, 30, 22, PAL["bug_d"])
    ellipse(img, 8, 9, 28, 20, PAL["bug"])
    ellipse(img, 10, 10, 26, 18, PAL["bug_l"])
    # spots
    px(img, 14, 13, PAL["bug_d"])
    px(img, 20, 14, PAL["bug_d"])
    px(img, 16, 16, PAL["bug_d"])
    # eyes
    px(img, 13, 12, PAL["cream"])
    px(img, 21, 12, PAL["cream"])
    px(img, 13, 13, PAL["ink"])
    px(img, 21, 13, PAL["ink"])
    # legs
    for i, base in enumerate((10, 16, 22)):
        px(img, base + lx, 22, PAL["ink"])
        px(img, base + lx - 1, 24, PAL["ink"])
        px(img, base - lx + 2, 22, PAL["ink"])
        px(img, base - lx + 3, 25, PAL["ink"])
    # antenna
    px(img, 12, 6, PAL["ink"])
    px(img, 11, 4, PAL["ink"])
    px(img, 22, 6, PAL["ink"])
    px(img, 23, 4, PAL["ink"])
    return img


def draw_weed(frame: int) -> Image.Image:
    img = new(32, 44)
    sway = (-1, 0, 1, 0)[frame % 4]
    fill_rect(img, 14 + sway, 18, 4, 24, PAL["weed"])
    fill_rect(img, 15 + sway, 18, 2, 24, PAL["weed_d"])
    for y in range(10):
        w = 11 - y // 2
        col = PAL["weed"] if y % 2 == 0 else PAL["leaf"]
        fill_rect(img, 16 + sway - w, 6 + y, w * 2, 1, col)
    # flower head bob
    fy = 14 + (1 if frame % 2 else 0)
    ellipse(img, 10 + sway, fy, 22 + sway, fy + 12, PAL["weed_f"])
    ellipse(img, 12 + sway, fy + 2, 20 + sway, fy + 10, PAL["weed_fl"])
    px(img, 14 + sway, fy + 5, PAL["ink"])
    px(img, 18 + sway, fy + 5, PAL["ink"])
    return img


def draw_flyer(frame: int) -> Image.Image:
    """Larger, outlined flyer — readable on bright sky."""
    img = new(48, 36)
    wing_y = (8, 4, 8, 12)[frame % 4]
    wing_h = (10, 6, 10, 12)[frame % 4]

    def wing(x0: int, x1: int) -> None:
        # ink outline then fill
        ellipse(img, x0 - 1, wing_y - 1, x1 + 1, wing_y + wing_h + 1, PAL["ink"])
        ellipse(img, x0, wing_y, x1, wing_y + wing_h, PAL["flyer_w"])
        ellipse(img, x0 + 2, wing_y + 2, x1 - 2, wing_y + wing_h - 1, (255, 255, 255, 160))

    wing(2, 18)
    wing(30, 46)
    # body outline + fill
    ellipse(img, 14, 10, 34, 30, PAL["ink"])
    ellipse(img, 15, 11, 33, 28, PAL["flyer_d"])
    ellipse(img, 16, 12, 32, 26, PAL["flyer"])
    ellipse(img, 18, 13, 30, 23, PAL["flyer_l"])
    # eyes
    px(img, 20, 17, PAL["cream"])
    px(img, 28, 17, PAL["cream"])
    px(img, 20, 18, PAL["ink"])
    px(img, 28, 18, PAL["ink"])
    # beak hint
    px(img, 24, 20, PAL["petal"])
    px(img, 24, 21, PAL["petal_d"])
    # feet
    px(img, 21, 29, PAL["ink"])
    px(img, 27, 29, PAL["ink"])
    return img


def draw_boss(frame: int) -> Image.Image:
    img = new(72, 72)
    bob = (0, 1, 0, -1)[frame % 4]
    rot = frame * 0.08
    cx, cy = 36, 32 + bob
    for i in range(14):
        a = i / 14 * math.pi * 2 + rot
        ox = int(cx + math.cos(a) * 24)
        oy = int(cy + math.sin(a) * 22)
        col = PAL["boss_p"] if i % 2 == 0 else PAL["boss_pd"]
        ellipse(img, ox - 8, oy - 5, ox + 8, oy + 5, col)
        px(img, ox, oy - 3, PAL["petal_l"])
    ellipse(img, cx - 16, cy - 16, cx + 16, cy + 16, PAL["boss_c"])
    ellipse(img, cx - 13, cy - 13, cx + 13, cy + 13, PAL["center_d"])
    ellipse(img, cx - 10, cy - 8, cx + 10, cy + 8, PAL["center"])
    # angry eyes
    fill_rect(img, cx - 9, cy - 4, 5, 4, PAL["danger"])
    fill_rect(img, cx + 4, cy - 4, 5, 4, PAL["danger"])
    px(img, cx - 7, cy - 3, PAL["ink"])
    px(img, cx + 6, cy - 3, PAL["ink"])
    # frown
    px(img, cx - 4, cy + 6, PAL["danger"])
    px(img, cx - 2, cy + 7, PAL["danger"])
    px(img, cx, cy + 7, PAL["danger"])
    px(img, cx + 2, cy + 7, PAL["danger"])
    px(img, cx + 4, cy + 6, PAL["danger"])
    fill_rect(img, 32, 52 + bob, 8, 16, PAL["soil_d"])
    fill_rect(img, 33, 52 + bob, 6, 16, PAL["bark"])
    return img


def make_enemies() -> None:
    hsheet([draw_bug(i) for i in range(4)], ANIM / "enemy_bug_sheet.png")
    hsheet([draw_weed(i) for i in range(4)], ANIM / "enemy_weed_sheet.png")
    hsheet([draw_flyer(i) for i in range(4)], ANIM / "enemy_flyer_sheet.png")
    hsheet([draw_boss(i) for i in range(4)], ANIM / "enemy_boss_sheet.png")
    # static fallbacks (first frame)
    save(draw_bug(0), SPRITES / "enemy_bug.png")
    save(draw_weed(0), SPRITES / "enemy_weed.png")
    save(draw_boss(0), SPRITES / "enemy_boss.png")


def make_projectiles() -> None:
    seed = new(14, 10)
    ellipse(seed, 1, 2, 12, 8, PAL["center_d"])
    ellipse(seed, 2, 2, 10, 7, PAL["center"])
    ellipse(seed, 3, 3, 7, 6, PAL["petal"])
    px(seed, 4, 4, PAL["petal_l"])
    save(seed, SPRITES / "seed.png")

    spit = new(12, 12)
    ellipse(spit, 1, 1, 10, 10, PAL["danger"])
    ellipse(spit, 3, 3, 8, 8, PAL["weed_fl"])
    px(spit, 5, 5, PAL["cream"])
    save(spit, SPRITES / "enemy_shot.png")


# --- Tiles & decor ---

def make_tiles() -> None:
    # 16x16 ground tile (dirt + grass top) — tileable
    g = new(16, 16)
    fill_rect(g, 0, 0, 16, 16, PAL["soil"])
    fill_rect(g, 0, 4, 16, 12, PAL["soil_d"])
    for x, y in ((2, 7), (7, 10), (12, 8), (5, 13), (11, 14)):
        px(g, x, y, PAL["soil_dd"])
    for x, y in ((3, 6), (9, 9), (14, 12)):
        px(g, x, y, PAL["soil_l"])
    fill_rect(g, 0, 0, 16, 4, PAL["grass"])
    fill_rect(g, 0, 0, 16, 2, PAL["grass_l"])
    for x in range(0, 16, 3):
        px(g, x, 0, PAL["grass_d"])
        px(g, x + 1, 1, PAL["grass_l"])
    save(g, TILES / "ground.png")

    # grass edge strip for top of cliffs
    edge = new(16, 8)
    fill_rect(edge, 0, 3, 16, 5, PAL["soil"])
    fill_rect(edge, 0, 0, 16, 4, PAL["grass"])
    for x in (1, 4, 7, 10, 13):
        px(edge, x, 0, PAL["grass_l"])
        px(edge, x + 1, 1, PAL["grass_d"])
    save(edge, TILES / "grass_edge.png")

    # wooden platform (Stardew plank feel)
    plat = new(48, 14)
    fill_rect(plat, 0, 0, 48, 14, PAL["wood_d"])
    fill_rect(plat, 0, 0, 48, 11, PAL["wood"])
    fill_rect(plat, 0, 0, 48, 2, PAL["wood_l"])
    for x in (12, 24, 36):
        fill_rect(plat, x, 2, 1, 10, PAL["wood_d"])
    for x in (3, 18, 33, 44):
        px(plat, x, 6, PAL["wood_d"])
    # grass tuft on top
    for x in (6, 20, 34):
        px(plat, x, 0, PAL["grass_l"])
        px(plat, x + 1, 0, PAL["grass"])
    save(plat, TILES / "platform.png")

    # glowing sunflower portal door
    door = new(48, 72)
    fill_rect(door, 8, 8, 32, 60, PAL["bark_d"])
    fill_rect(door, 10, 10, 28, 56, PAL["bark"])
    fill_rect(door, 12, 12, 24, 52, PAL["center_d"])
    for i in range(12):
        a = i / 12 * math.pi * 2
        ox = int(24 + math.cos(a) * 14)
        oy = int(28 + math.sin(a) * 12)
        ellipse(door, ox - 5, oy - 3, ox + 5, oy + 3, PAL["petal"] if i % 2 else PAL["petal_d"])
    ellipse(door, 16, 20, 32, 36, PAL["center"])
    ellipse(door, 19, 23, 29, 33, PAL["center_l"])
    px(door, 21, 26, PAL["cream"])
    px(door, 27, 26, PAL["cream"])
    for i in range(48):
        if i % 2 == 0:
            px(door, i, 6, PAL["petal_l"])
            px(door, i, 68, PAL["petal"])
    save(door, TILES / "door.png")


def make_decor() -> None:
    # tree
    tree = new(48, 64)
    fill_rect(tree, 21, 36, 6, 28, PAL["bark_d"])
    fill_rect(tree, 22, 36, 4, 28, PAL["bark"])
    ellipse(tree, 6, 8, 42, 40, PAL["tree_d"])
    ellipse(tree, 10, 6, 38, 36, PAL["tree"])
    ellipse(tree, 14, 10, 34, 30, PAL["tree_l"])
    px(tree, 18, 16, PAL["grass_l"])
    px(tree, 28, 20, PAL["grass_l"])
    save(tree, DECOR / "tree.png")

    # bush
    bush = new(32, 24)
    ellipse(bush, 2, 6, 30, 22, PAL["tree_d"])
    ellipse(bush, 4, 4, 28, 20, PAL["tree"])
    ellipse(bush, 8, 6, 22, 16, PAL["tree_l"])
    px(bush, 12, 10, PAL["flower_p"])
    px(bush, 20, 12, PAL["petal"])
    save(bush, DECOR / "bush.png")

    # fence post segment
    fence = new(24, 24)
    fill_rect(fence, 4, 4, 4, 20, PAL["fence_d"])
    fill_rect(fence, 5, 4, 2, 20, PAL["fence"])
    fill_rect(fence, 16, 4, 4, 20, PAL["fence_d"])
    fill_rect(fence, 17, 4, 2, 20, PAL["fence"])
    fill_rect(fence, 4, 8, 16, 3, PAL["fence"])
    fill_rect(fence, 4, 14, 16, 3, PAL["fence"])
    save(fence, DECOR / "fence.png")

    # rock
    rock = new(20, 14)
    ellipse(rock, 1, 3, 18, 13, PAL["rock_d"])
    ellipse(rock, 2, 2, 16, 11, PAL["rock"])
    ellipse(rock, 4, 3, 12, 8, PAL["rock_l"])
    save(rock, DECOR / "rock.png")

    # wildflower (ground) — cleaner stem + petals
    fl = new(14, 18)
    fill_rect(fl, 6, 9, 2, 9, PAL["stem"])
    fill_rect(fl, 5, 12, 4, 1, PAL["leaf"])
    ellipse(fl, 2, 1, 12, 11, PAL["flower_b"])
    ellipse(fl, 4, 3, 10, 9, PAL["flower_p"])
    px(fl, 7, 5, PAL["cream"])
    save(fl, DECOR / "flower.png")

    # pink wildflower variant
    fl2 = new(14, 18)
    fill_rect(fl2, 6, 9, 2, 9, PAL["stem"])
    ellipse(fl2, 2, 1, 12, 11, PAL["flower_p"])
    ellipse(fl2, 4, 3, 10, 9, PAL["petal_l"])
    px(fl2, 7, 5, PAL["cream"])
    save(fl2, DECOR / "flower_pink.png")

    # moss tuft for platform tops (not hanging under)
    moss = new(16, 8)
    for x in range(16):
        hgt = 3 + (x * 5) % 4
        for y in range(8 - hgt, 8):
            px(moss, x, y, PAL["grass"] if y > 8 - hgt else PAL["grass_l"])
    save(moss, DECOR / "moss.png")

    # crop sunflower (short)
    crop = new(16, 28)
    fill_rect(crop, 7, 12, 2, 16, PAL["stem"])
    fill_rect(crop, 2, 16, 5, 2, PAL["leaf"])
    fill_rect(crop, 9, 18, 5, 2, PAL["leaf_d"])
    for i in range(6):
        a = i / 6 * math.pi * 2
        ox = int(8 + math.cos(a) * 4)
        oy = int(8 + math.sin(a) * 4)
        px(crop, ox, oy, PAL["petal"])
    ellipse(crop, 5, 5, 11, 11, PAL["center"])
    save(crop, DECOR / "crop.png")

    # cloud for parallax
    cloud = new(48, 20)
    ellipse(cloud, 4, 6, 28, 18, PAL["cloud"])
    ellipse(cloud, 16, 2, 44, 16, PAL["cloud"])
    ellipse(cloud, 8, 8, 24, 16, PAL["cloud_s"])
    save(cloud, DECOR / "cloud.png")

    # floating petal particle for title
    pet = new(10, 10)
    ellipse(pet, 1, 2, 8, 8, PAL["petal"])
    px(pet, 3, 3, PAL["petal_l"])
    save(pet, DECOR / "petal.png")


def make_bg() -> None:
    # Sky ONLY (no hills) 480×180 → 960×360. Hills live in mid.png.
    w, h = 480, 180
    sky = new(w, h)
    for y in range(h):
        t = y / (h - 1)
        if t < 0.45:
            u = t / 0.45
            r = int(PAL["sky0"][0] * (1 - u) + PAL["sky1"][0] * u)
            g = int(PAL["sky0"][1] * (1 - u) + PAL["sky1"][1] * u)
            b = int(PAL["sky0"][2] * (1 - u) + PAL["sky1"][2] * u)
        else:
            u = (t - 0.45) / 0.55
            r = int(PAL["sky1"][0] * (1 - u) + PAL["sky2"][0] * u)
            g = int(PAL["sky1"][1] * (1 - u) + PAL["sky2"][1] * u)
            b = int(PAL["sky1"][2] * (1 - u) + PAL["sky2"][2] * u)
        fill_rect(sky, 0, y, w, 1, (r, g, b, 255))

    ellipse(sky, 400, 18, 440, 58, PAL["sun"])
    ellipse(sky, 408, 26, 432, 50, PAL["sun_c"])
    for cx, cy, rw, rh in ((60, 40, 50, 22), (140, 28, 40, 18), (220, 50, 56, 24), (320, 36, 44, 20)):
        ellipse(sky, cx - rw // 2, cy - rh // 2, cx + rw // 2, cy + rh // 2, PAL["cloud"])
        ellipse(
            sky,
            cx - rw // 3,
            cy,
            cx + rw // 3,
            cy + rh // 2,
            PAL["cloud_s"],
        )
    save(sky, BG / "sky.png")

    # Mid: hills fill ~85% of strip (not a flat bottom ribbon). Transparent sky above.
    mw, mh = 480, 120
    mid = new(mw, mh)
    for x in range(mw):
        h1 = int(28 + math.sin(x * 0.018) * 10 + math.sin(x * 0.006) * 8)
        for y in range(h1, mh):
            px(mid, x, y, PAL["hill_b"])
    for x in range(mw):
        h2 = int(48 + math.sin(x * 0.03 + 1.1) * 12 + math.sin(x * 0.01) * 6)
        for y in range(h2, mh):
            px(mid, x, y, PAL["hill_m"])
    for x in range(mw):
        h3 = int(72 + math.sin(x * 0.045 + 0.4) * 10)
        for y in range(h3, mh):
            px(mid, x, y, PAL["hill_f"])
            if y == h3 and x % 4 == 0:
                px(mid, x, y - 1, PAL["grass_l"])
    for tx in range(16, mw - 16, 40):
        th = 22 + (tx * 5) % 14
        top = 78 - th
        fill_rect(mid, tx + 8, top + 10, 4, th, PAL["bark_d"])
        ellipse(mid, tx, top, tx + 22, top + 22, PAL["tree_d"])
        ellipse(mid, tx + 3, top + 3, tx + 19, top + 18, PAL["tree"])
    save(mid, BG / "mid.png")

    # Title hero background — golden hour sunflower field
    tw, th = 480, 270
    title = new(tw, th)
    for y in range(th):
        t = y / (th - 1)
        r = int(90 * (1 - t) + 255 * t * 0.55 + 120)
        g = int(150 * (1 - t) + 200 * t)
        b = int(210 * (1 - t) + 120 * t)
        r = min(255, r)
        fill_rect(title, 0, y, tw, 1, (r, g, b, 255))
    ellipse(title, 340, 24, 420, 104, (255, 230, 150, 255))
    ellipse(title, 355, 40, 405, 90, PAL["sun_c"])
    for x in range(tw):
        h1 = int(170 + math.sin(x * 0.025) * 16)
        for y in range(h1, th):
            px(title, x, y, PAL["hill_m"])
        h2 = int(195 + math.sin(x * 0.04 + 0.8) * 10)
        for y in range(h2, th):
            px(title, x, y, PAL["hill_f"])
    # sunflower crop rows
    for row, base_y in enumerate((200, 220, 240)):
        for i in range(14):
            sx = 20 + i * 34 + (row % 2) * 12
            fill_rect(title, sx + 6, base_y, 2, 22, PAL["stem"])
            for j in range(8):
                a = j / 8 * math.pi * 2
                ox = int(sx + 7 + math.cos(a) * 5)
                oy = int(base_y - 2 + math.sin(a) * 4)
                px(title, ox, oy, PAL["petal"] if j % 2 == 0 else PAL["petal_d"])
            ellipse(title, sx + 4, base_y - 5, sx + 11, base_y + 2, PAL["center"])
    # large hero sunflower left
    hx, hy = 90, 150
    for i in range(14):
        a = i / 14 * math.pi * 2
        ox = int(hx + math.cos(a) * 28)
        oy = int(hy + math.sin(a) * 24)
        ellipse(title, ox - 8, oy - 5, ox + 8, oy + 5, PAL["petal"] if i % 2 else PAL["petal_d"])
    ellipse(title, hx - 16, hy - 16, hx + 16, hy + 16, PAL["center"])
    ellipse(title, hx - 10, hy - 8, hx + 10, hy + 8, PAL["center_l"])
    px(title, hx - 5, hy - 2, PAL["cream"])
    px(title, hx + 5, hy - 2, PAL["cream"])
    save(title, BG / "title.png")

    # dusk / creek alternate skies for room themes
    dusk = sky.copy()
    for y in range(h):
        t = y / (h - 1)
        r = int(40 + 180 * t)
        g = int(60 + 90 * t)
        b = int(120 + 40 * (1 - t))
        for x in range(w):
            pr, pg, pb, pa = dusk.getpixel((x, y))
            if pa and y < 110:
                dusk.putpixel((x, y), (min(255, (pr + r) // 2), min(255, (pg + g) // 2), min(255, (pb + b) // 2), 255))
    save(dusk, BG / "sky_dusk.png")

    creek = sky.copy()
    for x in range(w):
        for y in range(155, h):
            creek.putpixel((x, y), (70, 140, 170, 255) if (x + y) % 5 else (90, 160, 190, 255))
    save(creek, BG / "sky_creek.png")


def make_ui() -> None:
    heart = new(16, 16)
    ellipse(heart, 1, 2, 8, 10, PAL["petal"])
    ellipse(heart, 7, 2, 14, 10, PAL["petal"])
    ellipse(heart, 2, 5, 13, 14, PAL["petal_d"])
    ellipse(heart, 5, 7, 10, 12, PAL["center"])
    save(heart, UI / "heart.png")

    heart_empty = new(16, 16)
    ellipse(heart_empty, 1, 2, 8, 10, (255, 255, 255, 60))
    ellipse(heart_empty, 7, 2, 14, 10, (255, 255, 255, 60))
    ellipse(heart_empty, 2, 5, 13, 14, (255, 255, 255, 40))
    save(heart_empty, UI / "heart_empty.png")

    emblem = new(48, 48)
    cx, cy = 24, 24
    for i in range(12):
        a = i / 12 * math.pi * 2
        ox = int(cx + math.cos(a) * 16)
        oy = int(cy + math.sin(a) * 16)
        ellipse(emblem, ox - 5, oy - 3, ox + 5, oy + 3, PAL["petal"] if i % 2 else PAL["petal_d"])
    ellipse(emblem, cx - 9, cy - 9, cx + 9, cy + 9, PAL["center"])
    ellipse(emblem, cx - 6, cy - 5, cx + 6, cy + 5, PAL["center_l"])
    px(emblem, cx - 3, cy - 1, PAL["cream"])
    px(emblem, cx + 3, cy - 1, PAL["cream"])
    save(emblem, UI / "emblem.png", scale=3)


def make_icon() -> None:
    icon = new(16, 16)
    for i in range(8):
        a = i / 8 * math.pi * 2
        px(icon, int(8 + math.cos(a) * 5), int(8 + math.sin(a) * 5), PAL["petal"])
    ellipse(icon, 5, 5, 10, 10, PAL["center"])
    save(icon, ROOT / "icon.png", scale=8)


def main() -> None:
    print("Generating Stardew-style pixel art...")
    make_player()
    make_enemies()
    make_projectiles()
    make_tiles()
    make_decor()
    make_bg()
    make_ui()
    make_icon()
    print("Done.")


if __name__ == "__main__":
    main()
