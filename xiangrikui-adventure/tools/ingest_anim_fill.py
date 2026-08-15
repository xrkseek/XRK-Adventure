#!/usr/bin/env python3
"""把模板填格结果 → raw/<state>_ai.png → process_character。

用法:
  python tools/ingest_anim_fill.py --id meijia --state walk --src path/to/fill.png
  python tools/ingest_anim_fill.py --id meijia --state jump --src path/to/bounce.png
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SA = Path.home() / "Desktop" / "XRKbar" / "sprite-animator"
sys.path.insert(0, str(SA))

from pixel_cook import split_frames  # noqa: E402
from pixel_matte import content_touches_border, matte_auto, rekey_template_bg_to_screen  # noqa: E402
from sprite_animator.template import extract_frames  # noqa: E402


def lower_body_diff(a: Image.Image, b: Image.Image) -> float:
    """只比下半身，抓 walk 迈腿。"""
    aa = np.array(a.convert("RGBA"))
    bb = np.array(b.convert("RGBA"))
    h = min(aa.shape[0], bb.shape[0])
    w = min(aa.shape[1], bb.shape[1])
    y0 = h // 2
    aa = aa[y0:h, :w]
    bb = bb[y0:h, :w]
    aa = np.array(Image.fromarray(aa).resize((64, 64), Image.Resampling.BILINEAR))
    bb = np.array(Image.fromarray(bb).resize((64, 64), Image.Resampling.BILINEAR))
    m = (aa[:, :, 3] > 40) | (bb[:, :, 3] > 40)
    if not m.any():
        return 0.0
    return float(np.abs(aa.astype(int) - bb.astype(int))[m].mean())


def head_w(im: Image.Image) -> int:
    bb = im.split()[3].getbbox()
    if not bb:
        return 0
    x0, y0, x1, y1 = bb
    band = im.crop((x0, y0, x1, y0 + max(4, int((y1 - y0) * 0.42))))
    b2 = band.split()[3].getbbox()
    return (b2[2] - b2[0]) if b2 else 0
CHARS = ROOT / "assets" / "characters"

# jump bounce 4×4 → 入库 8 帧（crouch→launch→rise→peak→fall start→fall→land→recover）
JUMP_PICK_8 = [3, 4, 5, 6, 8, 9, 10, 12]
# 旧 3 帧兼容
JUMP_PICK_3 = [2, 6, 10]


def frame_diff(a: Image.Image, b: Image.Image) -> float:
    aa = np.array(a.resize((96, 96), Image.Resampling.BILINEAR))
    bb = np.array(b.resize((96, 96), Image.Resampling.BILINEAR))
    m = (aa[:, :, 3] > 40) | (bb[:, :, 3] > 40)
    if not m.any():
        return 0.0
    return float(np.abs(aa.astype(int) - bb.astype(int))[m].mean())


def compose_wide(
    frames: list[Image.Image],
    pad: int = 16,
    *,
    matte_mode: str = "flood",
    strip_bg: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """拼宽横条。strip_bg 必须与角色 matte 匹配：chroma→品红，flood 黑幕→黑。

    chroma：拼条时只做轻量抠幕（与入库同逻辑）；禁止在这里二次毁掉原图。
    """
    bg = (*strip_bg, 255)
    cells: list[Image.Image] = []
    fill_hex = "#FF00FF" if strip_bg[0] > 200 else "#000000"
    for fr in frames:
        m = matte_auto(fr, mode=matte_mode, fill_hex=fill_hex)
        bb = m.split()[3].getbbox()
        if bb:
            m = m.crop(bb)
        canvas = Image.new("RGBA", (m.width + pad * 2, m.height + pad * 2), bg)
        canvas.paste(m, (pad, pad), m)
        cells.append(canvas)
    cw = max(c.width for c in cells)
    ch = max(c.height for c in cells)
    n = len(cells)
    cw = max(cw, (ch * 2) // n + 8)
    strip = Image.new("RGBA", (cw * n, ch), bg)
    for i, c in enumerate(cells):
        fr = Image.new("RGBA", (cw, ch), bg)
        fr.paste(c, ((cw - c.width) // 2, ch - c.height), c)
        strip.paste(fr, (i * cw, 0))
    return strip


def compose_equal_cells(
    frames: list[Image.Image],
    *,
    strip_bg: tuple[int, int, int] = (255, 0, 255),
) -> Image.Image:
    """虚拟等格拼条：每帧同一 cw×ch，不 trim（保留跳顶点）。无边框。"""
    bg = (*strip_bg, 255)
    cells = [fr.convert("RGBA") for fr in frames]
    cw = max(c.width for c in cells)
    ch = max(c.height for c in cells)
    n = len(cells)
    strip = Image.new("RGBA", (cw * n, ch), bg)
    for i, fr in enumerate(cells):
        cell = Image.new("RGBA", (cw, ch), bg)
        cell.paste(fr, ((cw - fr.width) // 2, (ch - fr.height) // 2), fr)
        strip.paste(cell, (i * cw, 0))
    print(f"compose equal cells {n}×{cw}x{ch}")
    return strip


def is_bg(r: int, g: int, b: int, a: int) -> bool:
    if a < 20:
        return True
    if r <= 28 and g <= 28 and b <= 28:
        return True
    if r >= 240 and g <= 40 and b >= 240:
        return True
    return False


def content_column_segs(im: Image.Image, *, min_width: int | None = None) -> list[tuple[int, int]]:
    w, h = im.size
    px = im.load()
    cols = [sum(1 for y in range(h) if not is_bg(*px[x, y])) for x in range(w)]
    thresh = max(8, h // 50)
    segs: list[tuple[int, int]] = []
    inseg = False
    s = 0
    for x, c in enumerate(cols):
        if c >= thresh and not inseg:
            inseg = True
            s = x
        elif c < thresh and inseg:
            inseg = False
            segs.append((s, x - 1))
    if inseg:
        segs.append((s, w - 1))
    mw = min_width if min_width is not None else max(40, w // 12)
    return [(a, b) for a, b in segs if (b - a + 1) >= mw]


def _richest_horizontal_band(im: Image.Image) -> Image.Image | None:
    """AI 常把 1×N 画成多行；取实体像素最多的水平带（至少高 h/5）。"""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()

    def is_bg(r: int, g: int, b: int, a: int) -> bool:
        if a < 20:
            return True
        if r <= 28 and g <= 28 and b <= 28:
            return True
        if r >= 190 and b >= 160 and g <= 120:
            return True
        return False

    row_c = [
        sum(1 for x in range(0, w, 3) if not is_bg(*px[x, y])) for y in range(h)
    ]
    thresh = max(6, w // 100)
    bands: list[tuple[int, int]] = []
    inb = False
    s = 0
    for y, c in enumerate(row_c):
        if c >= thresh and not inb:
            inb = True
            s = y
        elif c < thresh and inb:
            inb = False
            bands.append((s, y - 1))
    if inb:
        bands.append((s, h - 1))
    min_h = max(48, h // 5)
    bands = [(a, b) for a, b in bands if (b - a + 1) >= min_h]
    if len(bands) < 2:
        return None
    best = max(bands, key=lambda ab: sum(row_c[ab[0] : ab[1] + 1]))
    pad = 8
    y0 = max(0, best[0] - pad)
    y1 = min(h, best[1] + 1 + pad)
    return im.crop((0, y0, w, y1))


def load_frames(im: Image.Image, state: str, n_out: int) -> list[Image.Image]:
    w, h = im.size
    # 若 AI 画成多行横条：取「实体最多」的那一行再切 Nx1（防 8x1 横切双行碎掉）
    if state in ("walk", "jump") and n_out >= 4 and h > w * 0.45:
        band = _richest_horizontal_band(im)
        if band is not None:
            print(f"layout {state} multi-row → use band {band.size}")
            im = band
            w, h = im.size
    # walk/jump：强制等格横条（content_cols 紧裁会假阳性贴边）
    if state == "walk" and n_out in (4, 6) and w >= h * 0.8:
        print(f"layout walk force {n_out}x1")
        return extract_frames(im, cols=n_out, rows=1)
    if state == "jump" and n_out >= 8 and w >= h:
        print(f"layout jump force {n_out}x1")
        return extract_frames(im, cols=n_out, rows=1)
    segs = content_column_segs(im)
    if len(segs) >= n_out and (state != "jump" or w >= h * 2):
        if state != "jump" or len(segs) == n_out:
            print(f"layout content_cols n={len(segs)} segs={segs[:n_out]}")
            return [im.crop((a, 0, b + 1, h)) for a, b in segs[:n_out]]
    if state == "jump" and w < h * 2:
        all_f = extract_frames(im, cols=4, rows=4)
        pick = JUMP_PICK_8 if n_out >= 8 else JUMP_PICK_3
        print("layout jump 4x4 pick", pick[:n_out])
        return [all_f[i] for i in pick[:n_out]]
    if state == "attack" and n_out == 6 and abs(w - h) < max(w, h) * 0.15:
        raise SystemExit(
            "attack multi-dir square fill: use "
            f"python tools/cook_attack_dirs.py --id … --src {im.size}"
        )
    if w >= h * 2:
        print("layout wide strip", n_out)
        return extract_frames(im, cols=n_out, rows=1)
    if n_out == 4:
        print("layout 2x2 fallback")
        return extract_frames(im, cols=2, rows=2)
    if n_out in (3, 6, 8) and w > h:
        return extract_frames(im, cols=n_out, rows=1)
    return split_frames(im, n_out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--state", required=True, choices=("walk", "jump", "attack", "idle"))
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--skip-cook", action="store_true")
    args = ap.parse_args()

    profile = json.loads((CHARS / args.id / "character.json").read_text(encoding="utf-8-sig"))
    n_out = int(profile["states"][args.state]["frames"])
    matte_mode = str(profile.get("matte", "")).lower()
    if not matte_mode:
        matte_mode = (
            "flood"
            if str(profile.get("key_hint", "magenta")).lower() == "black"
            else "chroma"
        )
    im = Image.open(args.src).convert("RGBA")
    print("src", args.src, im.size, "matte", matte_mode)
    # AI 常画灰底：边缘浅灰/电青格线 → 幕色，再走 chroma（不动黑裤）
    screen_hex = "#000000" if str(profile.get("key_hint", "magenta")).lower() == "black" else "#FF00FF"
    im = rekey_template_bg_to_screen(im, screen_hex)
    print("rekeyed non-screen bg →", screen_hex)

    # 多向攻击：正方形/网格填格走 cook_attack_dirs（禁止拉扁）
    atk = profile["states"].get("attack", {})
    if args.state == "attack" and atk.get("dirs"):
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "cook_attack_dirs.py"),
                "--id",
                args.id,
                "--src",
                str(args.src),
            ],
            cwd=str(ROOT),
        )
        raise SystemExit(r.returncode)

    frames = load_frames(im, args.state, n_out)
    if len(frames) != n_out:
        raise SystemExit(f"expected {n_out} frames, got {len(frames)}")

    ok = True
    fill_hex = "#000000" if str(profile.get("key_hint", "magenta")).lower() == "black" else "#FF00FF"
    if matte_mode in ("chroma", "key", "colorkey", "screen"):
        fill_hex = "#FF00FF"
    matted = []
    for i, fr in enumerate(frames):
        m = matte_auto(fr, mode=matte_mode, fill_hex=fill_hex)
        bb = m.split()[3].getbbox()
        solid = sum(1 for y in range(m.height) for x in range(m.width) if m.getpixel((x, y))[3] > 128)
        touch = [k for k, v in content_touches_border(m, inset=1).items() if v]
        print(f"f{i+1} solid={solid} bbox={bb} touch={touch or 'ok'}")
        if solid < 800:
            print(f"FAIL: f{i+1} near-empty")
            ok = False
        # 半裁：左右同时贴边且上下也贴/几乎占满 = 真裁切；宽角鹿仅左右贴边只 WARN
        if "left" in touch and "right" in touch:
            cell_area = m.width * m.height
            fat = solid / max(1, cell_area) >= 0.55
            also_tb = ("top" in touch) or ("bottom" in touch)
            if fat or also_tb:
                print(f"FAIL: f{i+1} clipped L+R (fat={fat} tb={also_tb}) — regenerate")
                ok = False
            else:
                print(f"WARN: f{i+1} wide L+R touch (antlers/arms) {touch}")
        elif "left" in touch or "right" in touch:
            print(f"WARN: f{i+1} near L/R edge {touch}")
        matted.append(m)

    if args.state in ("walk", "jump") and n_out >= 3:
        # 与 f1 同高：头宽 / 内容高波动过大 = 没锁 idle（禁止大小不一硬入库）
        hws = [head_w(m) for m in matted]
        chs = []
        for m in matted:
            bb = m.split()[3].getbbox()
            chs.append((bb[3] - bb[1]) if bb else 0)
        ref_hw = float(sorted(h for h in hws if h >= 4)[len([h for h in hws if h >= 4]) // 2])
        ref_ch = float(sorted(h for h in chs if h >= 8)[len([h for h in chs if h >= 8]) // 2])
        print(f"size lock head_w={hws} content_h={chs} ref_hw={ref_hw:.0f} ref_ch={ref_ch:.0f}")
        for i, (hw, ch) in enumerate(zip(hws, chs)):
            if hw >= 4 and abs(hw - ref_hw) / ref_hw > 0.18:
                print(f"FAIL: f{i+1} head_w={hw} vs ref={ref_hw:.0f} (>18%) — regenerate")
                ok = False
            if ch >= 8 and abs(ch - ref_ch) / ref_ch > 0.22:
                print(f"FAIL: f{i+1} content_h={ch} vs ref={ref_ch:.0f} (>22%) — regenerate")
                ok = False

    if args.state == "walk" and n_out >= 3:
        # f1 将是 idle；对侧 contact 比 f3 vs f5；下半身必须有明显迈腿
        a, b = (2, 4) if n_out >= 5 else (0, 2)
        d = frame_diff(matted[a], matted[b])
        print(f"walk contact diff f{a+1}-f{b+1}={d:.1f}")
        if d < 22:
            print("FAIL: contacts too similar — regenerate walk")
            ok = False
        # f2/f4 相对 f1 下半身差：防止「六格站桩」
        for fi in (1, 3) if n_out >= 4 else (1,):
            if fi >= len(matted):
                break
            ld = lower_body_diff(matted[0], matted[fi])
            print(f"walk lower-body diff f1-f{fi+1}={ld:.1f}")
            if ld < 12:
                print(f"FAIL: f{fi+1} legs barely moved vs f1 — regenerate")
                ok = False

    strip_bg = (255, 0, 255)
    if str(profile.get("key_hint", "magenta")).lower() == "black":
        strip_bg = (0, 0, 0)
    if matte_mode in ("chroma", "key", "colorkey", "screen"):
        strip_bg = (255, 0, 255)

    if not ok:
        print("FAIL: not saving raw / not cooking — fix fill and retry")
        raise SystemExit(1)

    if matte_mode in ("chroma", "key", "colorkey", "screen"):
        strip = compose_equal_cells(frames, strip_bg=strip_bg)
    else:
        strip = compose_wide(frames, matte_mode=matte_mode, strip_bg=strip_bg)
    if strip.width < n_out * 40:
        raise SystemExit(f"strip too narrow for {n_out} cells: {strip.size}")
    # 虚拟等格：宽 = n×cw 即合格（允许格高 > 格宽，如 192×1024）
    cw = strip.width // n_out
    if cw * n_out != strip.width:
        raise SystemExit(f"strip width not divisible by {n_out}: {strip.size}")
    print(f"virtual cells {n_out}×{cw}x{strip.height}")
    out = CHARS / args.id / "raw" / f"{args.state}_ai.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out)
    arch = SA / "examples" / args.id / f"{args.state}_fill_raw.png"
    arch.parent.mkdir(parents=True, exist_ok=True)
    Image.open(args.src).convert("RGBA").save(arch)
    strip.save(SA / "examples" / args.id / f"{args.state}_strip.png")
    print("saved", out, strip.size, "wide_ok")

    if args.skip_cook:
        return
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "process_character.py"), "--id", args.id, "--state", args.state],
        cwd=str(ROOT),
    )
    raise SystemExit(r.returncode)


if __name__ == "__main__":
    main()
