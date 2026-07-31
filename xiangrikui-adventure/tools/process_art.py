#!/usr/bin/env python3
"""Chroma-key magenta, crop, and pack animation spritesheets for Godot."""
from __future__ import annotations

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
OUT = ROOT / "assets" / "sprites" / "anim"
TILES = ROOT / "assets" / "tiles"
BG = ROOT / "assets" / "bg"
SPRITES = ROOT / "assets" / "sprites"

MAGENTA = (255, 0, 255)
# Also catch near-magenta / green-screen leftovers
THRESH = 55


def remove_bg(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            # magenta / hot pink chroma
            if r > 180 and b > 180 and g < 120:
                px[x, y] = (0, 0, 0, 0)
                continue
            # pure-ish magenta distance
            dr, dg, db = r - 255, g - 0, b - 255
            if dr * dr + dg * dg + db * db < THRESH * THRESH * 3:
                px[x, y] = (0, 0, 0, 0)
            # white-ish studio leftover (seed image)
            elif r > 245 and g > 245 and b > 245:
                px[x, y] = (0, 0, 0, 0)
    return img


def autocrop(img: Image.Image, pad: int = 4) -> Image.Image:
    bbox = img.getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(img.width, x1 + pad)
    y1 = min(img.height, y1 + pad)
    return img.crop((x0, y0, x1, y1))


def fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    img = img.copy()
    img.thumbnail(size, Image.Resampling.LANCZOS)
    x = (size[0] - img.width) // 2
    y = size[1] - img.height  # bottom-align for platformer
    if y < 0:
        y = 0
    canvas.paste(img, (x, y), img)
    return canvas


def sheet(frames: list[Image.Image], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    w = max(f.width for f in frames)
    h = max(f.height for f in frames)
    fitted = [fit(f, (w, h)) for f in frames]
    out = Image.new("RGBA", (w * len(fitted), h), (0, 0, 0, 0))
    for i, f in enumerate(fitted):
        out.paste(f, (i * w, 0), f)
    out.save(path)
    print(f"sheet {path.relative_to(ROOT)}  {out.size}  frames={len(frames)}")


def process_one(name: str) -> Image.Image:
    src = RAW / name
    img = Image.open(src)
    img = remove_bg(img)
    img = autocrop(img)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TILES.mkdir(parents=True, exist_ok=True)
    BG.mkdir(parents=True, exist_ok=True)

    # Player animation sheets
    idle = [process_one("player_idle.png"), process_one("player_idle2.png")]
    walk = [process_one("player_walk1.png"), process_one("player_walk2.png")]
    jump = [process_one("player_jump.png")]
    # unify player cell size
    cell = (128, 160)
    idle_f = [fit(f, cell) for f in idle]
    walk_f = [fit(f, cell) for f in walk]
    jump_f = [fit(f, cell) for f in jump]
    sheet(idle_f, OUT / "player_idle_sheet.png")
    sheet(walk_f, OUT / "player_walk_sheet.png")
    sheet(jump_f, OUT / "player_jump_sheet.png")
    # combined for AnimatedSprite convenience: idle0 idle1 walk0 walk1 jump0
    sheet(idle_f + walk_f + jump_f, OUT / "player_all_sheet.png")

    # Enemies
    for name, out_name, size in [
        ("enemy_bug.png", "enemy_bug.png", (96, 80)),
        ("enemy_weed.png", "enemy_weed.png", (96, 128)),
        ("enemy_boss.png", "enemy_boss.png", (192, 192)),
        ("door_portal.png", "door.png", (128, 160)),
        ("seed_bullet.png", "seed.png", (48, 32)),
    ]:
        img = fit(process_one(name), size)
        dest = SPRITES / out_name if "door" not in out_name else TILES / out_name
        if out_name == "door.png":
            dest = TILES / "door.png"
        elif out_name == "seed.png":
            dest = SPRITES / "seed.png"
        else:
            dest = SPRITES / out_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)
        print(f"sprite {dest.relative_to(ROOT)} {img.size}")

    flyer0 = fit(process_one("enemy_flyer.png"), (96, 80))
    flyer1 = fit(process_one("enemy_flyer_flap.png"), (96, 80))
    sheet([flyer0, flyer1], OUT / "enemy_flyer_sheet.png")
    flyer0.save(SPRITES / "enemy_flyer.png")

    # Background — no chroma needed
    bg = Image.open(RAW / "bg_sky.png").convert("RGBA")
    bg.save(BG / "sky.png")
    print(f"bg {BG.relative_to(ROOT)}/sky.png {bg.size}")

    # Also save single player icon
    idle_f[0].save(SPRITES / "player.png")
    print("Done processing.")


if __name__ == "__main__":
    main()
