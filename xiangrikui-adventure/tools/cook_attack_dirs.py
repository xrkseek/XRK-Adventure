#!/usr/bin/env python3
"""多向攻击填格 → attack_sheet.png（等比切格；与 idle 同高；每行 f1=idle）。

用法:
  python tools/cook_attack_dirs.py --id yumumu --src path/to/fill.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from pixel_cook import content_bbox, trim_alpha  # noqa: E402
from pixel_matte import matte_auto  # noqa: E402
from process_character import (  # noqa: E402
    apply_shared_scale,
    fit_bottom_from_cell,
    idle_content_1x,
    idle_frame_1x,
    load_profile,
)

CHARS = ROOT / "assets" / "characters"
DEFAULT_DIRS = ["e", "ne", "n", "se", "s"]


def cook_attack_dirs(char_id: str, src: Path) -> Path:
    profile = load_profile(char_id)
    st = profile["states"]["attack"]
    dirs = list(st.get("dirs") or DEFAULT_DIRS)
    frames = int(st.get("frames", 6))
    rows, cols = len(dirs), frames
    cell = (int(profile["cell_w"]), int(profile["cell_h"]))
    px = int(profile.get("px", 2))
    matte_mode = str(profile.get("matte", "")).lower()
    hint = str(profile.get("key_hint", "magenta")).lower()
    fill_hex = "#000000" if hint == "black" else "#FF00FF"
    if not matte_mode:
        matte_mode = "flood" if hint == "black" else "chroma"
    if matte_mode not in ("chroma", "key", "colorkey", "screen", "flood", "rembg"):
        matte_mode = "chroma" if hint != "black" else "flood"

    im = Image.open(src).convert("RGBA")
    w, h = im.size
    cw, ch = w // cols, h // rows
    if cw < 8 or ch < 8:
        raise SystemExit(f"grid too small: {w}x{h} / {cols}x{rows}")
    print(f"cook_attack_dirs {char_id}: src={im.size} cell={cw}x{ch} matte={matte_mode}")

    raw_dir = CHARS / char_id / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    im.save(raw_dir / "attack_dirs_ai.png")

    idle_c = idle_content_1x(profile)
    idle_full = idle_frame_1x(profile)
    idle_h = idle_c.height if idle_c else int(profile["body_h"])

    # 收集全部动作格（col0 将换成 idle，不参与 scale）
    grid: list[list[Image.Image]] = []
    for r in range(rows):
        row: list[Image.Image] = []
        for c in range(cols):
            crop = im.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
            part = trim_alpha(matte_auto(crop, mode=matte_mode, fill_hex=fill_hex))
            row.append(part)
        grid.append(row)

    action = [grid[r][c] for r in range(rows) for c in range(1, cols)]
    chs = []
    for p in action:
        bb = content_bbox(p)
        chs.append((bb[3] - bb[1]) if bb else max(4, p.height))
    if not chs:
        raise SystemExit("no action cells after matte")
    target_h = float(sorted(chs)[len(chs) // 2])
    scale = float(idle_h) / max(4.0, target_h)
    print(
        f"  shared-scale={scale:.4f} idle_h={idle_h} "
        f"action_median_h={target_h:.0f} (n={len(chs)})"
    )

    fitted: list[list[Image.Image]] = []
    for r in range(rows):
        row_fits: list[Image.Image] = []
        for c in range(cols):
            if c == 0 and idle_full is not None:
                fit = idle_full
            else:
                locked = apply_shared_scale(profile, grid[r][c], scale)
                fit = fit_bottom_from_cell(locked, cell)
            row_fits.append(fit)
            bb = content_bbox(fit)
            bh = (bb[3] - bb[1]) if bb else 0
            bw = (bb[2] - bb[0]) if bb else 0
            print(f"  {dirs[r]} f{c+1} content={bw}x{bh}")
        fitted.append(row_fits)

    out_w = cell[0] * cols * px
    out_h = cell[1] * rows * px
    sheet = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    for r in range(rows):
        for c in range(cols):
            up = fitted[r][c].resize((cell[0] * px, cell[1] * px), Image.Resampling.NEAREST)
            sheet.paste(up, (c * cell[0] * px, r * cell[1] * px), up)

    anim = CHARS / char_id / "anim"
    anim.mkdir(parents=True, exist_ok=True)
    out = anim / "attack_sheet.png"
    sheet.save(out)
    print("saved", out, sheet.size, f"(expect {out_w}x{out_h})")
    # preview
    refs = CHARS / char_id / "refs"
    refs.mkdir(parents=True, exist_ok=True)
    fitted[0][0].resize((cell[0] * 4, cell[1] * 4), Image.Resampling.NEAREST).save(
        refs / "attack_pixel_preview.png"
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--src", required=True, type=Path)
    args = ap.parse_args()
    if not args.src.is_file():
        raise SystemExit(f"missing {args.src}")
    cook_attack_dirs(args.id, args.src)


if __name__ == "__main__":
    main()
