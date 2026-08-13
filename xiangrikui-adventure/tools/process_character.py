#!/usr/bin/env python3
"""通用角色管线：assets/characters/<id>/ → anim/<state>_sheet.png

用法:
  python tools/process_character.py --id xuyuezhen --state idle
  python tools/process_character.py --id xuyuezhen --state all

新角色：复制 character.json 模板，放入 raw/<state>_ai.png 与 refs/cutout.png，再跑本脚本。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from pixel_cook import (  # noqa: E402
    content_bbox,
    fit_bottom_fixed,
    hard_pixel,
    matte_frames,
    split_frames,
    write_hsheet,
)

CHARS = ROOT / "assets" / "characters"


def load_profile(char_id: str) -> dict[str, Any]:
    path = CHARS / char_id / "character.json"
    if not path.is_file():
        raise SystemExit(f"Missing character profile: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("id") != char_id:
        raise SystemExit(f"character.json id={data.get('id')!r} != --id {char_id!r}")
    return data


def char_dirs(char_id: str) -> dict[str, Path]:
    base = CHARS / char_id
    return {
        "base": base,
        "raw": base / "raw",
        "refs": base / "refs",
        "anim": base / "anim",
    }


def extract_parts(profile: dict[str, Any], state: str) -> list[Image.Image]:
    dirs = char_dirs(profile["id"])
    n = int(profile["states"][state]["frames"])
    src = dirs["raw"] / f"{state}_ai.png"
    if not src.is_file():
        raise SystemExit(f"Missing AI raw: {src}")
    crops = split_frames(Image.open(src), n)
    return matte_frames(crops, empty_h=int(profile["body_h"]))


def lock_body_height(profile: dict[str, Any], part: Image.Image) -> Image.Image:
    body_h = int(profile["body_h"])
    bb = content_bbox(part)
    if not bb or part.height < 4:
        return Image.new("RGBA", (8, body_h), (0, 0, 0, 0))
    scale = body_h / part.height
    tw = max(8, round(part.width * scale))
    return hard_pixel(
        part,
        tw,
        body_h,
        int(profile.get("palette", 96)),
        pad=str(profile.get("quant_pad", "green")),
        rematte=True,
    )


def finalize_state(profile: dict[str, Any], state: str, locked: list[Image.Image]) -> None:
    dirs = char_dirs(profile["id"])
    cell = (int(profile["cell_w"]), int(profile["cell_h"]))
    px = int(profile.get("px", 2))
    frames = [fit_bottom_fixed(f, cell) for f in locked]
    out = dirs["anim"] / f"{state}_sheet.png"
    write_hsheet(frames, out, px=px, root=ROOT)
    dirs["refs"].mkdir(parents=True, exist_ok=True)
    prev = frames[0].resize((cell[0] * 4, cell[1] * 4), Image.Resampling.NEAREST)
    prev.save(dirs["refs"] / f"{state}_pixel_preview.png")
    if state == "idle":
        prev.save(dirs["refs"] / "pixel_preview.png")


def process_state(profile: dict[str, Any], state: str) -> None:
    if state not in profile["states"]:
        raise SystemExit(f"Unknown state {state!r}; have {sorted(profile['states'])}")
    locked = [lock_body_height(profile, p) for p in extract_parts(profile, state)]
    finalize_state(profile, state, locked)
    print(f"  ok {profile['id']}/{state}")


def process_all(profile: dict[str, Any]) -> None:
    cw, ch = int(profile["cell_w"]), int(profile["cell_h"])
    print(
        f"{profile['display_name']} ({profile['id']}) "
        f"BODY_H={profile['body_h']} cell={cw}x{ch} px={profile.get('px', 2)}"
    )
    for state in profile["states"]:
        process_state(profile, state)


def main() -> None:
    ap = argparse.ArgumentParser(description="Process character AI sheets → pixel anim")
    ap.add_argument("--id", required=True, help="character id under assets/characters/")
    ap.add_argument("--state", default="all", help="idle|walk|jump|attack|all")
    args = ap.parse_args()
    profile = load_profile(args.id)
    states = list(profile["states"])
    if args.state == "all":
        process_all(profile)
    elif args.state in states:
        process_state(profile, args.state)
    else:
        raise SystemExit(f"--state must be all or one of {states}")
    cw = int(profile["cell_w"]) * int(profile.get("px", 2))
    ch = int(profile["cell_h"]) * int(profile.get("px", 2))
    print(f"Done. SpriteFactory cell @2× = {cw}x{ch}. Reimport in Godot if size changed.")


if __name__ == "__main__":
    main()
