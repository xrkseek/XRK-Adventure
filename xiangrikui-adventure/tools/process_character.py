#!/usr/bin/env python3
"""通用角色管线：assets/characters/<id>/ → anim/<state>_sheet.png

用法:
  python tools/process_character.py --id xuyuezhen --state idle
  python tools/process_character.py --id xuyuezhen --state all

装格对齐:
  - idle：每帧内容高度 → body_h。
  - walk/jump/attack：第 1 帧 = idle 首帧；整张一个
    scale = idle_content_h / f1_content_h（与 idle 同高）。
    无所谓占满格。禁止最高帧 bbox→body_h；禁止逐帧 lock_body_h。
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
    data = json.loads(path.read_text(encoding="utf-8-sig"))
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
    # 虚拟等格：walk/jump 禁止 trim（trim 会弄丢等宽等高 + 跳跃高度）
    trim = state not in ("walk", "jump")
    hint = str(profile.get("key_hint", "magenta")).lower()
    fill = "#000000" if hint == "black" else "#FF00FF"
    if "matte" in profile:
        mode = str(profile.get("matte", "flood")).lower()
    else:
        mode = "flood" if hint == "black" else "chroma"
    print(f"  matte={mode} fill={fill} trim={trim} cell0={crops[0].size if crops else None}")
    parts = matte_frames(
        crops, empty_h=int(profile["body_h"]), fill_hex=fill, mode=mode, trim=trim
    )
    if not trim and parts:
        cw = parts[0].width
        ch = parts[0].height
        for i, p in enumerate(parts):
            if p.size != (cw, ch):
                raise SystemExit(f"FAIL unequal cell after matte: f{i+1}={p.size} want {cw}x{ch}")
        print(f"  equal virtual cells {len(parts)}×{cw}x{ch}")
    return parts


def content_height(im: Image.Image) -> int:
    bb = content_bbox(im)
    return (bb[3] - bb[1]) if bb else max(1, im.height)


def head_width(im: Image.Image) -> int:
    """内容顶约 42% 的宽度 ≈ 头宽（同图同比例时各帧接近）。"""
    bb = content_bbox(im)
    if not bb:
        return 0
    x0, y0, x1, y1 = bb
    hy = y0 + max(1, int((y1 - y0) * 0.42))
    px = im.load()
    xs = [
        x
        for y in range(y0, min(hy, y1))
        for x in range(x0, x1)
        if px[x, y][3] >= 40
    ]
    return (max(xs) - min(xs) + 1) if xs else 0


def idle_frame_1x(profile: dict[str, Any]) -> Image.Image | None:
    """已确认 idle 首帧，缩到 @1×。"""
    dirs = char_dirs(profile["id"])
    path = dirs["anim"] / "idle_sheet.png"
    if not path.is_file():
        return None
    im = Image.open(path).convert("RGBA")
    n = max(1, int(profile["states"]["idle"]["frames"]))
    cw = im.width // n
    cell = im.crop((0, 0, cw, im.height))
    px = int(profile.get("px", 2))
    if px > 1:
        cell = cell.resize(
            (max(1, cell.width // px), max(1, cell.height // px)),
            Image.Resampling.NEAREST,
        )
    return cell


def _no_flood_rematte(profile: dict[str, Any]) -> bool:
    """chroma/rembg 已干净抠过，禁止 hard_pixel 再走 flood rematte（会抠穿棕蹄/角）。"""
    return str(profile.get("matte", "flood")).lower() in (
        "rembg",
        "ai",
        "u2net",
        "chroma",
        "key",
        "colorkey",
        "screen",
    )


def _want_hard_pixel(profile: dict[str, Any]) -> bool:
    """AI 已出像素时禁止二次 BOX/量化（双像素糊）。默认 true。"""
    v = profile.get("hard_pixel", True)
    if isinstance(v, str):
        return v.strip().lower() not in ("0", "false", "no", "off", "nearest")
    return bool(v)


def lock_body_height(profile: dict[str, Any], part: Image.Image) -> Image.Image:
    body_h = int(profile["body_h"])
    if part.height < 4:
        return Image.new("RGBA", (8, body_h), (0, 0, 0, 0))
    scale = body_h / part.height
    tw = max(8, round(part.width * scale))
    if not _want_hard_pixel(profile):
        return part.resize((tw, body_h), Image.Resampling.NEAREST)
    safe = _no_flood_rematte(profile)
    return hard_pixel(
        part,
        tw,
        body_h,
        int(profile.get("palette", 96)),
        pad=str(profile.get("quant_pad", "green")),
        rematte=not safe,
        alpha_cut=40 if safe else 120,
    )


def idle_content_1x(profile: dict[str, Any]) -> Image.Image | None:
    """已确认 idle 首帧的不透明内容（trim 后），高度即动作同高真源。"""
    idle = idle_frame_1x(profile)
    if idle is None:
        return None
    bb = content_bbox(idle)
    return idle.crop(bb) if bb else idle


def inject_idle_frame0(profile: dict[str, Any], parts: list[Image.Image]) -> list[Image.Image]:
    """第 1 帧强制为 idle。等格模式：idle 贴进与其它帧同尺寸的虚拟格。"""
    idle_c = idle_content_1x(profile)
    if idle_c is None or not parts:
        return parts
    out = list(parts)
    cell_w, cell_h = parts[0].size
    # 等格（未 trim）：把 idle 按 f1 内容高度对齐后贴进整格
    if cell_w >= 32 and cell_h >= 32 and content_bbox(parts[0]) is not None:
        f1_bb = content_bbox(parts[0])
        target_h = max(4, f1_bb[3] - f1_bb[1]) if f1_bb else cell_h // 2
        scale = target_h / float(max(4, idle_c.height))
        tw = max(8, round(idle_c.width * scale))
        th = max(8, round(idle_c.height * scale))
        idle_r = idle_c.resize((tw, th), Image.Resampling.NEAREST)
        canvas = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
        # 脚底对齐到 f1 内容底边，保留跳跃格的纵向参考
        foot_y = f1_bb[3] if f1_bb else cell_h
        px = (cell_w - tw) // 2
        py = max(0, min(cell_h - th, foot_y - th))
        canvas.paste(idle_r, (px, py), idle_r)
        out[0] = canvas
        print(f"  inject idle→f1 equal-cell {cell_w}x{cell_h} (content_h={target_h})")
        return out
    others = parts[1:] if len(parts) > 1 else parts
    target_h = int(sorted(max(4, content_height(p)) for p in others)[len(others) // 2])
    scale = target_h / float(max(4, idle_c.height))
    tw = max(8, round(idle_c.width * scale))
    th = max(8, target_h)
    idle_ai = idle_c.resize((tw, th), Image.Resampling.NEAREST)
    out[0] = idle_ai
    print(f"  inject idle→f1 ai={idle_ai.size} (target_h={target_h})")
    return out


def sheet_scale(profile: dict[str, Any], parts: list[Image.Image]) -> float:
    """整张一个 scale：按头宽对齐 idle。蹲/跳 content_h 变矮时不能再缩体型。

    walk/jump 的 f1 会换成 idle，勿把「注入后的大 idle」头宽混进中位数，
    否则 median 偏大 → scale 偏小 → 动作帧比 idle 矮一截。
    """
    idle_c = idle_content_1x(profile)
    body_h = int(profile["body_h"])
    if idle_c is None:
        max_h = float(max(content_height(p) for p in parts))
        return body_h / max_h
    idle_hw = float(head_width(idle_c) or max(4, idle_c.width))
    action = parts[1:] if len(parts) > 1 else parts
    hws = [h for h in (head_width(p) for p in action) if h >= 4]
    if not hws:
        hws = [h for h in (head_width(p) for p in parts) if h >= 4]
    if not hws:
        return float(max(4, idle_c.height)) / float(max(4, content_height(parts[0])))
    ref_hw = float(sorted(hws)[len(hws) // 2])
    scale = idle_hw / ref_hw
    # 头宽锁之后若站立帧仍明显高于 idle，再压到 idle 同高（防 AI 整体偏大）
    chs = [content_height(p) for p in action if content_height(p) >= 8]
    if chs:
        ref_ch = float(sorted(chs)[len(chs) // 2])
        if ref_ch * scale > idle_c.height * 1.06:
            scale = float(idle_c.height) / ref_ch
    return scale


def apply_shared_scale(
    profile: dict[str, Any], part: Image.Image, scale: float
) -> Image.Image:
    """统一 scale：等格只缩内容；脚底锚原 bbox 底。

    hard_pixel=true（默认）：BOX→量化→NEAREST。
    hard_pixel=false：源已是像素，只 NEAREST（禁止二次像素化）。
    """
    body_h = int(profile["body_h"])
    if part.height < 4:
        return Image.new("RGBA", (8, body_h), (0, 0, 0, 0))
    do_hp = _want_hard_pixel(profile)
    safe = _no_flood_rematte(profile)
    colors = int(profile.get("palette", 96))
    pad = str(profile.get("quant_pad", "green"))
    alpha_cut = 40 if safe else 120

    def _scale_img(img: Image.Image, tw: int, th: int) -> Image.Image:
        if do_hp:
            return hard_pixel(
                img, tw, th, colors, pad=pad, rematte=not safe, alpha_cut=alpha_cut
            )
        return img.resize((tw, th), Image.Resampling.NEAREST)

    bb = content_bbox(part)
    if bb and part.width >= 64 and part.height >= 96:
        x0, y0, x1, y1 = bb
        content = part.crop(bb)
        tw = max(1, round(content.width * scale))
        th = max(1, round(content.height * scale))
        scaled = _scale_img(content, tw, th)
        canvas = Image.new("RGBA", part.size, (0, 0, 0, 0))
        px = int(round((x0 + x1) * 0.5 - tw * 0.5))
        py = int(round(y1 - th))
        canvas.paste(scaled, (px, py), scaled)
        return canvas
    tw = max(8, round(part.width * scale))
    th = max(8, round(part.height * scale))
    return _scale_img(part, tw, th)


def uniform_fit_scale(parts: list[Image.Image], cell: tuple[int, int]) -> float:
    """超出 cell 时整张共用一个 fit，禁止逐帧二次缩放。"""
    tw, th = cell
    max_w = 1
    max_h = 1
    for p in parts:
        bb = content_bbox(p)
        if not bb:
            continue
        max_w = max(max_w, bb[2] - bb[0])
        max_h = max(max_h, bb[3] - bb[1])
    return float(min(1.0, tw / float(max_w), th / float(max_h)))


def fit_bottom_from_cell(src: Image.Image, cell: tuple[int, int]) -> Image.Image:
    """取内容脚底对齐；不再调用会逐帧缩小的 fit_bottom_fixed。"""
    bb = content_bbox(src)
    content = src.crop(bb) if bb else src
    tw, th = cell
    canvas = Image.new("RGBA", cell, (0, 0, 0, 0))
    iw, ih = content.size
    if iw < 1 or ih < 1:
        return canvas
    if iw > tw or ih > th:
        content = content.crop((0, 0, min(iw, tw), min(ih, th)))
        iw, ih = content.size
    canvas.paste(content, ((tw - iw) // 2, th - ih), content)
    return canvas


def finalize_state(profile: dict[str, Any], state: str, locked: list[Image.Image]) -> None:
    dirs = char_dirs(profile["id"])
    cell = (int(profile["cell_w"]), int(profile["cell_h"]))
    px = int(profile.get("px", 2))
    if state in ("walk", "jump"):
        fit = uniform_fit_scale(locked, cell)
        if fit < 0.999:
            print(f"  uniform-fit={fit:.4f}")
            locked = [apply_shared_scale(profile, p, fit) for p in locked]
        frames = [fit_bottom_from_cell(f, cell) for f in locked]
        idle_full = idle_frame_1x(profile)
        if idle_full is not None:
            frames[0] = fit_bottom_from_cell(idle_full, cell)
    else:
        frames = [fit_bottom_fixed(f, cell) for f in locked]
    for i, f in enumerate(frames):
        if f.size != cell:
            raise SystemExit(f"FAIL frame size f{i+1}={f.size} want {cell}")
    out = dirs["anim"] / f"{state}_sheet.png"
    write_hsheet(frames, out, px=px, root=ROOT)
    dirs["refs"].mkdir(parents=True, exist_ok=True)
    prev = frames[0].resize((cell[0] * 4, cell[1] * 4), Image.Resampling.NEAREST)
    prev.save(dirs["refs"] / f"{state}_pixel_preview.png")
    if state == "idle":
        prev.save(dirs["refs"] / "pixel_preview.png")
        prev.save(dirs["refs"] / "idle_pixel_preview.png")


def process_state(profile: dict[str, Any], state: str) -> None:
    if state not in profile["states"]:
        raise SystemExit(f"Unknown state {state!r}; have {sorted(profile['states'])}")
    parts = extract_parts(profile, state)
    if state == "idle":
        locked = [lock_body_height(profile, p) for p in parts]
    else:
        parts = inject_idle_frame0(profile, parts)
        idle_c = idle_content_1x(profile)
        idle_h = idle_c.height if idle_c else int(profile["body_h"])
        scale = sheet_scale(profile, parts)
        hws = [head_width(p) for p in parts]
        print(
            f"  sheet-scale={scale:.4f} (head-lock) "
            f"(idle_h={idle_h} head_w={hws} content_h={[content_height(p) for p in parts]})"
        )
        locked = [apply_shared_scale(profile, p, scale) for p in parts]
        if idle_c is not None and state not in ("walk", "jump"):
            locked[0] = idle_c
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
