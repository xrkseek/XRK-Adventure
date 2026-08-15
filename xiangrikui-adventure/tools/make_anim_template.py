#!/usr/bin/env python3
"""生成动作模板 + 填格 prompt。

铁律（短）：
- 模板 = 纯幕色；虚拟等格；无边框
- 角色禁幕色；约占格 ~60%，均匀居中留白，方便裁
- 无辅助线时可加特效（尘土/动线），勿用幕色画特效

用法:
  python tools/make_anim_template.py --id xuyuezhen --state walk --print-prompt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CHARS = ROOT / "assets" / "characters"
SA = Path.home() / "Desktop" / "XRKbar" / "sprite-animator"

# 硬约束短：幕色 / 禁幕色上身 / 无边框。占格约60%，均匀留白。
HARD = (
    "Solid flat SCREEN_HEX bg only; no borders/labels/grids. "
    "No SCREEN_HEX on the character (hood eyes white+black, never magenta). "
    "Equal virtual cells; character ~60% of each cell, evenly centered with even margin "
    "(do NOT fill tight — easier crop). Same character height across cells; Cell1=idle pose. "
    "IDENTICAL design; only motion changes. Never truncate L/R. "
    "FX OK (dust, motion lines) if they stay inside the cell and are not screen-colored."
)

PRESETS: dict[str, dict] = {
    "idle": {
        "cols": 4,
        "rows": 4,
        "cell": 288,
        "prompt": (
            "Fill 4x4 equal virtual cells; character ~60% evenly placed. "
            "Refs: cutout=style; idle_pixel=pose lock ONLY (soft cel, not muddy double-pixel). "
            "Row1 breathe up; Row2 BOTH eyes close; Row3 BOTH eyes open; Row4 breathe down. "
            "NEVER wink. " + HARD
        ),
    },
    "walk": {
        "cols": 6,
        "rows": 1,
        "cell": 320,
        "prompt": (
            "Fill 6x1 equal virtual cells; character ~60% evenly placed. "
            "Character reference = confirmed idle PIXEL only (not illustration/立绘). "
            "Cells 2-6: contactR, pass-up, contactL opposite, pass-down, mid — legs clearly change. "
            + HARD
        ),
    },
    "jump": {
        "cols": 8,
        "rows": 1,
        "cell": 300,
        "prompt": (
            "Fill 8x1 equal virtual cells; character ~60% evenly placed in each cell "
            "(keep similar footing/center — jump height shown by pose, not by floating to cell top). "
            "Character reference = confirmed idle PIXEL only (not illustration/立绘). "
            "Cells 2-8: crouch, launch, rise, peak, fall, land, recover. Single row. "
            "Dust/motion FX OK. " + HARD
        ),
    },
    "attack": {
        "cols": 6,
        "rows": 5,
        "cell": 220,
        "prompt": (
            "Fill 5x6 equal virtual cells; character ~60% evenly placed. "
            "Rows top→bottom: aim e, ne, n, se, s. Col1 already = idle — copy that size/outfit. "
            "Character reference = confirmed idle PIXEL only (not illustration/立绘). "
            "Cols 2-6: wind-up → cast → release → follow-through → recover. "
            "No flying projectiles in-sheet. FX OK if not screen-colored. " + HARD
        ),
    },
}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def create_screen_template(cols: int, rows: int, cell_size: int, *, screen_hex: str) -> Image.Image:
    """纯幕色虚拟等格，无可见边框。"""
    return Image.new("RGB", (cols * cell_size, rows * cell_size), hex_to_rgb(screen_hex))


def load_profile(char_id: str) -> dict:
    path = CHARS / char_id / "character.json"
    if not path.is_file():
        raise SystemExit(f"Missing {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def screen_for(profile: dict) -> str:
    hint = str(profile.get("key_hint", "magenta")).lower()
    return "#000000" if hint == "black" else "#FF00FF"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--state", required=True, choices=sorted(PRESETS))
    ap.add_argument("--print-prompt", action="store_true")
    args = ap.parse_args()

    profile = load_profile(args.id)
    preset = PRESETS[args.state]
    screen = screen_for(profile)
    ex = SA / "examples" / args.id
    ex.mkdir(parents=True, exist_ok=True)

    tpl = create_screen_template(
        int(preset["cols"]), int(preset["rows"]), int(preset["cell"]), screen_hex=screen
    )
    name = f"template_{args.state}_{preset['cols']}x{preset['rows']}.png"
    out = ex / name
    tpl.save(out)

    base = CHARS / args.id / "refs" / "idle_pixel_preview.png"
    cutout = CHARS / args.id / "refs" / "cutout.png"
    # walk/jump/attack：第 1 列粘贴 idle；动作参考只用确认后的 idle 像素，禁止立绘 cutout
    if args.state in ("walk", "jump", "attack") and base.is_file():
        cell = int(preset["cell"])
        cols = int(preset["cols"])
        rows = int(preset["rows"])
        idle = Image.open(base).convert("RGBA")
        bb = idle.split()[3].getbbox()
        content = idle.crop(bb) if bb else idle
        scale = min((cell * 0.68) / max(1, content.width), (cell * 0.68) / max(1, content.height))
        nw = max(1, int(content.width * scale))
        nh = max(1, int(content.height * scale))
        big = content.resize((nw, nh), Image.Resampling.NEAREST)
        locked = tpl.convert("RGBA")
        ox = (cell - nw) // 2
        oy = cell - nh - int(cell * 0.06)
        for r in range(rows):
            locked.paste(big, (ox, r * cell + oy), big)
        idlef1 = ex / f"template_{args.state}_{cols}x{rows}_idlef1.png"
        locked.convert("RGB").save(idlef1)
        meta_template = str(idlef1)
        refs_order = ["template_with_idle_col1", "idle_pixel(style+pose lock)", "NO cutout/立绘"]
    else:
        meta_template = str(out)
        refs_order = ["template", "cutout(style)", "idle_pixel(pose lock only)"]

    prompt = preset["prompt"].replace("SCREEN_HEX", screen)
    if args.state in ("walk", "jump", "attack"):
        prompt = (
            "Col1 already has the exact idle pixel character — keep Col1; copy that IDENTICAL "
            "height/scale/outfit into every other cell. Use idle_pixel as the ONLY character "
            "reference (style + pose). Do NOT invent props from any illustration. "
            + prompt
        )
    meta = {
        "id": args.id,
        "state": args.state,
        "template": meta_template,
        "base_idle": str(base),
        "cutout": str(cutout) if args.state == "idle" else "(do not feed for walk/jump/attack)",
        "screen": screen,
        "virtual_cells": f"{preset['cols']}x{preset['rows']}",
        "refs_order": refs_order,
        "cook": (
            f"python tools/cook_attack_dirs.py --id {args.id} --src <fill.png>"
            if args.state == "attack"
            else f"python tools/process_character.py --id {args.id} --state {args.state}"
        ),
        "forbid": [
            "visible borders",
            "labels",
            "grid lines",
            "magenta on character",
            "feeding cutout/立绘 for walk/jump/attack",
            "extra props not in idle",
            "flying projectiles in attack sheet",
        ],
    }
    (ex / f"{args.state}_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ex / f"{args.state}_prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    if args.print_prompt:
        print("--- PROMPT ---")
        print(prompt)
    if not base.is_file():
        print(f"WARN: missing idle base {base}", file=sys.stderr)


if __name__ == "__main__":
    main()
