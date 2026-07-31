#!/usr/bin/env python3
"""Generate cohesive pixel-art assets for 向日葵历险记."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
TILES = ROOT / "assets" / "tiles"
UI = ROOT / "assets" / "ui"
BG = ROOT / "assets" / "bg"

# Art bible palette — sunflower field, no purple/cream-terracotta defaults
PAL = {
    "petal": (255, 213, 74, 255),
    "petal_d": (240, 180, 41, 255),
    "center": (107, 58, 31, 255),
    "center_d": (74, 38, 18, 255),
    "leaf": (61, 155, 85, 255),
    "leaf_d": (40, 110, 58, 255),
    "stem": (46, 125, 70, 255),
    "sky_t": (74, 168, 204, 255),
    "sky_b": (183, 228, 242, 255),
    "hill": (47, 122, 69, 255),
    "hill_d": (36, 99, 56, 255),
    "soil": (122, 83, 52, 255),
    "soil_d": (92, 61, 38, 255),
    "grass": (61, 155, 85, 255),
    "cream": (255, 246, 214, 255),
    "ink": (26, 36, 28, 255),
    "bug": (90, 70, 58, 255),
    "bug_h": (140, 100, 70, 255),
    "weed": (70, 130, 50, 255),
    "weed_f": (220, 80, 60, 255),
    "flyer": (220, 120, 140, 255),
    "flyer_w": (255, 200, 210, 255),
    "boss_p": (139, 90, 40, 255),
    "boss_c": (40, 24, 16, 255),
    "danger": (232, 93, 76, 255),
    "door": (255, 213, 74, 255),
    "ui_bg": (30, 42, 31, 220),
    "white": (255, 255, 255, 255),
    "trans": (0, 0, 0, 0),
}


def new(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def px(img: Image.Image, x: int, y: int, c: tuple) -> None:
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), c)


def fill_rect(img: Image.Image, x: int, y: int, w: int, h: int, c: tuple) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=c)


def ellipse(img: Image.Image, x0: int, y0: int, x1: int, y1: int, c: tuple) -> None:
    ImageDraw.Draw(img).ellipse([x0, y0, x1, y1], fill=c)


def save(img: Image.Image, path: Path, scale: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = img if scale == 1 else img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    out.save(path)
    print(f"  {path.relative_to(ROOT)} ({out.width}x{out.height})")


def make_player() -> None:
    """32x40 sunflower character — idle / walk / jump frames."""
    frames = []
    for fi in range(4):
        img = new(32, 40)
        sway = [-1, 0, 1, 0][fi]
        # stem
        for y in range(22, 36):
            px(img, 15 + sway, y, PAL["stem"])
            px(img, 16 + sway, y, PAL["leaf"])
        # leaves
        fill_rect(img, 8 + sway, 26, 6, 3, PAL["leaf"])
        fill_rect(img, 18 + sway, 28, 6, 3, PAL["leaf_d"])
        # petals
        cx, cy = 16 + sway, 14
        for ang_i in range(8):
            import math
            a = ang_i / 8 * math.pi * 2 + fi * 0.1
            px_x = int(cx + math.cos(a) * 7)
            px_y = int(cy + math.sin(a) * 7)
            col = PAL["petal"] if ang_i % 2 == 0 else PAL["petal_d"]
            ellipse(img, px_x - 3, px_y - 2, px_x + 3, px_y + 2, col)
        # center face
        ellipse(img, cx - 5, cy - 5, cx + 5, cy + 5, PAL["center"])
        ellipse(img, cx - 4, cy - 4, cx + 4, cy + 4, PAL["center_d"])
        # eyes
        px(img, cx - 2, cy - 1, PAL["cream"])
        px(img, cx + 2, cy - 1, PAL["cream"])
        # smile
        px(img, cx - 1, cy + 2, PAL["cream"])
        px(img, cx, cy + 3, PAL["cream"])
        px(img, cx + 1, cy + 2, PAL["cream"])
        frames.append(img)

    # spritesheet horizontal
    sheet = new(32 * 4, 40)
    for i, f in enumerate(frames):
        sheet.paste(f, (i * 32, 0))
    save(sheet, SPRITES / "player_sheet.png", scale=2)

    # single idle for icon
    save(frames[0], SPRITES / "player.png", scale=2)


def make_enemies() -> None:
    # bug 32x24
    bug = new(32, 24)
    ellipse(bug, 4, 6, 28, 20, PAL["bug"])
    ellipse(bug, 8, 8, 24, 18, PAL["bug_h"])
    px(bug, 12, 11, PAL["ink"])
    px(bug, 20, 11, PAL["ink"])
    for i in range(3):
        px(bug, 8 + i * 6, 20, PAL["ink"])
        px(bug, 7 + i * 6, 22, PAL["ink"])
    save(bug, SPRITES / "enemy_bug.png", scale=2)

    # weed 28x40
    weed = new(28, 40)
    fill_rect(weed, 12, 16, 4, 22, PAL["weed"])
    # leaves triangle-ish
    for y in range(8):
        w = 10 - y
        fill_rect(weed, 14 - w, 8 + y, w * 2, 1, PAL["weed"] if y % 2 == 0 else PAL["leaf"])
    ellipse(weed, 10, 14, 18, 22, PAL["weed_f"])
    save(weed, SPRITES / "enemy_weed.png", scale=2)

    # flyer 32x24
    flyer = new(32, 24)
    ellipse(flyer, 2, 8, 14, 16, PAL["flyer_w"])
    ellipse(flyer, 18, 8, 30, 16, PAL["flyer_w"])
    ellipse(flyer, 10, 6, 22, 18, PAL["flyer"])
    px(flyer, 14, 10, PAL["ink"])
    px(flyer, 18, 10, PAL["ink"])
    save(flyer, SPRITES / "enemy_flyer.png", scale=2)

    # boss 64x64
    boss = new(64, 64)
    import math
    cx, cy = 32, 30
    for i in range(12):
        a = i / 12 * math.pi * 2
        px_x = int(cx + math.cos(a) * 20)
        px_y = int(cy + math.sin(a) * 20)
        ellipse(boss, px_x - 7, px_y - 4, px_x + 7, px_y + 4, PAL["boss_p"])
    ellipse(boss, cx - 14, cy - 14, cx + 14, cy + 14, PAL["boss_c"])
    ellipse(boss, cx - 10, cy - 10, cx + 10, cy + 10, PAL["center_d"])
    # angry eyes
    fill_rect(boss, cx - 8, cy - 3, 4, 3, PAL["danger"])
    fill_rect(boss, cx + 4, cy - 3, 4, 3, PAL["danger"])
    # frown
    px(boss, cx - 3, cy + 6, PAL["danger"])
    px(boss, cx, cy + 5, PAL["danger"])
    px(boss, cx + 3, cy + 6, PAL["danger"])
    # stem stump
    fill_rect(boss, 28, 46, 8, 14, PAL["soil_d"])
    save(boss, SPRITES / "enemy_boss.png", scale=2)


def make_projectiles() -> None:
    seed = new(12, 8)
    ellipse(seed, 1, 1, 10, 6, PAL["center"])
    ellipse(seed, 2, 2, 6, 5, PAL["petal"])
    save(seed, SPRITES / "seed.png", scale=2)

    spit = new(10, 10)
    ellipse(spit, 1, 1, 8, 8, PAL["danger"])
    ellipse(spit, 3, 3, 6, 6, PAL["cream"])
    save(spit, SPRITES / "enemy_shot.png", scale=2)


def make_tiles() -> None:
    # ground top 32x32
    ground = new(32, 32)
    fill_rect(ground, 0, 0, 32, 32, PAL["soil"])
    fill_rect(ground, 0, 0, 32, 8, PAL["hill"])
    for x in range(0, 32, 4):
        px(ground, x + 1, 0, PAL["grass"])
        px(ground, x + 2, 1, PAL["leaf"])
    for y in range(10, 32, 5):
        for x in range(2, 30, 7):
            px(ground, x, y, PAL["soil_d"])
    save(ground, TILES / "ground.png", scale=2)

    # platform
    plat = new(48, 12)
    fill_rect(plat, 0, 0, 48, 12, PAL["soil_d"])
    fill_rect(plat, 0, 0, 48, 4, PAL["hill"])
    fill_rect(plat, 0, 0, 48, 1, PAL["cream"])
    save(plat, TILES / "platform.png", scale=2)

    # door
    door = new(40, 64)
    fill_rect(door, 4, 4, 32, 56, PAL["center"])
    fill_rect(door, 6, 6, 28, 52, PAL["center_d"])
    ellipse(door, 12, 16, 28, 32, PAL["petal"])
    ellipse(door, 16, 20, 24, 28, PAL["center"])
    # glow frame
    for i in range(40):
        if i % 3 == 0:
            px(door, i, 2, PAL["petal"])
            px(door, i, 60, PAL["petal"])
    save(door, TILES / "door.png", scale=2)


def make_ui() -> None:
    # heart / petal life
    heart = new(16, 16)
    ellipse(heart, 1, 3, 14, 14, PAL["petal"])
    ellipse(heart, 4, 6, 11, 12, PAL["center"])
    save(heart, UI / "heart.png", scale=2)

    heart_empty = new(16, 16)
    ellipse(heart_empty, 1, 3, 14, 14, (255, 255, 255, 50))
    save(heart_empty, UI / "heart_empty.png", scale=2)

    # upgrade card bg
    card = new(64, 80)
    fill_rect(card, 0, 0, 64, 80, (30, 42, 31, 230))
    fill_rect(card, 2, 2, 60, 76, (255, 246, 214, 30))
    for i in range(64):
        if i % 2 == 0:
            px(card, i, 0, PAL["petal"])
            px(card, i, 79, PAL["petal"])
    save(card, UI / "card.png", scale=2)

    # panel
    panel = new(32, 32)
    fill_rect(panel, 0, 0, 32, 32, (18, 28, 20, 210))
    save(panel, UI / "panel.png", scale=1)

    # title sunflower emblem
    emblem = new(48, 48)
    import math
    cx, cy = 24, 24
    for i in range(10):
        a = i / 10 * math.pi * 2
        px_x = int(cx + math.cos(a) * 14)
        px_y = int(cy + math.sin(a) * 14)
        ellipse(emblem, px_x - 5, px_y - 3, px_x + 5, px_y + 3, PAL["petal"] if i % 2 else PAL["petal_d"])
    ellipse(emblem, cx - 8, cy - 8, cx + 8, cy + 8, PAL["center"])
    px(emblem, cx - 3, cy - 1, PAL["cream"])
    px(emblem, cx + 3, cy - 1, PAL["cream"])
    save(emblem, UI / "emblem.png", scale=3)


def make_bg() -> None:
    # sky gradient strip
    sky = new(320, 180)
    for y in range(180):
        t = y / 179
        r = int(PAL["sky_t"][0] * (1 - t) + PAL["sky_b"][0] * t)
        g = int(PAL["sky_t"][1] * (1 - t) + PAL["sky_b"][1] * t)
        b = int(PAL["sky_t"][2] * (1 - t) + PAL["sky_b"][2] * t)
        fill_rect(sky, 0, y, 320, 1, (r, g, b, 255))
    # sun
    ellipse(sky, 260, 20, 300, 60, PAL["petal"])
    ellipse(sky, 250, 10, 310, 70, (255, 213, 74, 60))
    # hills
    import math
    for x in range(320):
        h1 = int(120 + math.sin(x * 0.03) * 18 + math.sin(x * 0.01) * 10)
        for y in range(h1, 180):
            px(sky, x, y, PAL["hill_d"])
        h2 = int(140 + math.sin(x * 0.05 + 1) * 12)
        for y in range(h2, 180):
            px(sky, x, y, PAL["hill"])
    save(sky, BG / "sky.png", scale=2)

    # particle petal
    p = new(8, 8)
    ellipse(p, 1, 2, 6, 6, PAL["petal"])
    save(p, SPRITES / "petal_particle.png", scale=2)


def make_icon() -> None:
    icon = new(16, 16)
    import math
    for i in range(8):
        a = i / 8 * math.pi * 2
        px_x = int(8 + math.cos(a) * 5)
        px_y = int(8 + math.sin(a) * 5)
        px(icon, px_x, px_y, PAL["petal"])
        px(icon, px_x + 1, px_y, PAL["petal_d"])
    ellipse(icon, 5, 5, 10, 10, PAL["center"])
    save(icon, ROOT / "icon.png", scale=8)


def main() -> None:
    print("Generating art for 向日葵历险记...")
    make_player()
    make_enemies()
    make_projectiles()
    make_tiles()
    make_ui()
    make_bg()
    make_icon()
    print("Done.")


if __name__ == "__main__":
    main()
