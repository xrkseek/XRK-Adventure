#!/usr/bin/env python3
"""统一抠图：只从画布边缘洪水填「键色」，禁止全图扫粉/扫黑（会抠穿粉蛾/深色裤子）。

生图选幕规则（与 deer-ai-pixel-pipeline 一致）：
- 粉色系主体 → 纯黑幕（禁止品红幕，会与粉身撞色混量化）
- 深色衣/黑发多 → 热品红幕（禁止纯黑幕）
- 键色必须与主体反差，不要「看起来像」主体颜色。
"""
from __future__ import annotations

from collections import deque

from PIL import Image


def is_screen_key(r: int, g: int, b: int, a: int = 255) -> bool:
    """热品红 / 亮粉幕布（AI 常用 #FF00FF），含量化后褪色的品红垫。"""
    if a < 36:
        return True
    # 真品红：R、B 高且 G 明显低
    if r >= 190 and b >= 170 and g <= 110 and r + b >= 2 * g + 100:
        return True
    # 偏亮粉幕（仍要求 G 很低，避免误杀角色腮红/粉蛾身）
    if r >= 230 and b >= 200 and g <= 90:
        return True
    # 量化褪色品红垫（常见于脚下「粉地板」）：G 极低，R≈B
    if g <= 45 and r >= 70 and b >= 70 and abs(r - b) <= 50 and r + b >= 2 * g + 80:
        return True
    return False


def is_matte_black(r: int, g: int, b: int) -> bool:
    """纯黑/近黑画布底（仅允许作为边缘洪水种子，不删内部阴影）。"""
    return r <= 22 and g <= 22 and b <= 22


def is_dark_key(r: int, g: int, b: int) -> bool:
    """黑幕 + AI 常画的深灰格线/格内底（会封住洪水，导致「只裁格不抠图」）。

    角色眼睛/描边是小块近黑且被彩色包围，不会从边缘连通进来。
    """
    if is_matte_black(r, g, b):
        return True
    mx = max(r, g, b)
    mn = min(r, g, b)
    # 深灰中性：格线、格内垫底（约 #1F–#30）
    if mx <= 50 and (mx - mn) <= 12:
        return True
    return False


def is_edge_seed(r: int, g: int, b: int, a: int) -> bool:
    return is_screen_key(r, g, b, a) or (a >= 36 and is_dark_key(r, g, b))


def chroma_flood(img: Image.Image) -> Image.Image:
    """从四边种子洪水填键色 → 透明。角色内部深色/粉色只要不连通到边缘就保留。"""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    visited = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()

    def try_seed(x: int, y: int) -> None:
        r, g, b, a = px[x, y]
        if is_edge_seed(r, g, b, a):
            q.append((x, y))
            visited[y][x] = True

    for x in range(w):
        try_seed(x, 0)
        try_seed(x, h - 1)
    for y in range(h):
        try_seed(0, y)
        try_seed(w - 1, y)

    while q:
        x, y = q.popleft()
        px[x, y] = (0, 0, 0, 0)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= w or ny >= h or visited[ny][nx]:
                    continue
                r, g, b, a = px[nx, ny]
                # 洪水只沿「仍像幕布」的像素走；一旦碰到实体色就停
                if is_screen_key(r, g, b, a) or is_dark_key(r, g, b):
                    visited[ny][nx] = True
                    q.append((nx, ny))
                else:
                    visited[ny][nx] = True  # 标记已看，但不入队
    return img


def strip_orphan_dark(img: Image.Image) -> Image.Image:
    """清掉灰框封住的封闭黑/深灰底；保留贴着彩色的近黑小块（眼睛/描边）。"""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()

    def is_color(r: int, g: int, b: int, a: int) -> bool:
        return a >= 128 and not is_dark_key(r, g, b) and not is_screen_key(r, g, b, a)

    seen = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if seen[y][x]:
                continue
            r, g, b, a = px[x, y]
            if a < 128 or not is_dark_key(r, g, b):
                seen[y][x] = True
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            seen[y][x] = True
            cells: list[tuple[int, int]] = []
            touches_color = False
            while q:
                cx, cy = q.popleft()
                cells.append((cx, cy))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = cx + dx, cy + dy
                        if nx < 0 or ny < 0 or nx >= w or ny >= h or seen[ny][nx]:
                            continue
                        nr, ng, nb, na = px[nx, ny]
                        if na < 128:
                            seen[ny][nx] = True
                            continue
                        if is_color(nr, ng, nb, na):
                            touches_color = True
                            seen[ny][nx] = True
                            continue
                        if is_dark_key(nr, ng, nb):
                            seen[ny][nx] = True
                            q.append((nx, ny))
                        else:
                            seen[ny][nx] = True
            if not touches_color:
                for cx, cy in cells:
                    px[cx, cy] = (0, 0, 0, 0)
                continue
            if len(cells) <= 800:
                continue
            # 大块黑底贴到轮廓：只留贴彩色 ≤2px 的暗像素（眼睛/外描边）
            keep: set[tuple[int, int]] = set()
            for cx, cy in cells:
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            nr, ng, nb, na = px[nx, ny]
                            if is_color(nr, ng, nb, na):
                                keep.add((cx, cy))
                                break
                    if (cx, cy) in keep:
                        break
            for cx, cy in cells:
                if (cx, cy) not in keep:
                    px[cx, cy] = (0, 0, 0, 0)
    return img


def fringe_clean(img: Image.Image, passes: int = 2) -> Image.Image:
    """只清边缘键色溢色/白晕；禁止删粉主体、禁止删内部深色。"""
    img = img.convert("RGBA")
    w, h = img.size
    for _ in range(passes):
        px = img.load()
        kill: list[tuple[int, int]] = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a < 128:
                    continue
                near_empty = False
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if nx < 0 or ny < 0 or nx >= w or ny >= h or px[nx, ny][3] < 64:
                            near_empty = True
                            break
                    if near_empty:
                        break
                if not near_empty:
                    continue
                # 边缘残留真品红
                if is_screen_key(r, g, b, a):
                    kill.append((x, y))
                    continue
                # 边缘白晕（抗锯齿）
                lum = (r + g + b) / 3.0
                neutral = abs(r - g) <= 16 and abs(g - b) <= 16 and abs(r - b) <= 20
                if neutral and lum >= 200:
                    kill.append((x, y))
                    continue
                # 边缘粉紫溢色：R、B 明显高于 G
                if r > g + 40 and b > g + 30 and g < 100 and lum > 140:
                    kill.append((x, y))
                    continue
                # 品红幕抗锯齿浅粉（左上常见）：R≈B 很高，仍偏品红
                if (
                    r >= 230
                    and b >= 220
                    and abs(r - b) <= 35
                    and (r + b) / 2.0 > g + 12
                ):
                    kill.append((x, y))
                    continue
                if (
                    r >= 220
                    and b >= 200
                    and g <= 180
                    and abs(r - b) <= 40
                    and r > g + 20
                    and b > g + 15
                ):
                    kill.append((x, y))
        for x, y in kill:
            px[x, y] = (0, 0, 0, 0)
    return img


def keep_largest_blob(img: Image.Image, min_keep_ratio: float = 0.05) -> Image.Image:
    """去掉游离噪点；保留与主连通域邻近的中等碎块（翅膀尖等）。"""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    seen = [[False] * w for _ in range(h)]
    blobs: list[list[tuple[int, int]]] = []

    def solid(x: int, y: int) -> bool:
        return px[x, y][3] >= 128

    for y in range(h):
        for x in range(w):
            if seen[y][x] or not solid(x, y):
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            seen[y][x] = True
            cells: list[tuple[int, int]] = []
            while q:
                cx, cy = q.popleft()
                cells.append((cx, cy))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and solid(nx, ny):
                            seen[ny][nx] = True
                            q.append((nx, ny))
            blobs.append(cells)
    if not blobs:
        return img
    blobs.sort(key=len, reverse=True)
    main = blobs[0]
    keep = set(main)
    main_n = len(main)
    mxs = [p[0] for p in main]
    mys = [p[1] for p in main]
    for blob in blobs[1:]:
        if len(blob) < max(8, int(main_n * min_keep_ratio)):
            continue
        xs = [p[0] for p in blob]
        ys = [p[1] for p in blob]
        if (
            max(xs) >= min(mxs) - 6
            and min(xs) <= max(mxs) + 6
            and max(ys) >= min(mys) - 6
            and min(ys) <= max(mys) + 6
        ):
            keep.update(blob)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    opx = out.load()
    for x, y in keep:
        opx[x, y] = px[x, y]
    return out


def matte(img: Image.Image, *, blob: bool = True) -> Image.Image:
    """标准管线：边缘洪水抠幕 → 清封闭黑底 → 边缘 fringe → 可选主连通域。"""
    out = strip_orphan_dark(chroma_flood(img))
    out = fringe_clean(out)
    if blob:
        out = keep_largest_blob(out)
    return out


def content_touches_border(img: Image.Image, inset: int = 1) -> dict[str, bool]:
    """实体像素是否贴齐画布边（贴边 ≈ 生成/裁切时被截断）。"""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    t = b = l = r = False
    for y in range(h):
        for x in range(w):
            if px[x, y][3] < 128:
                continue
            if y <= inset:
                t = True
            if y >= h - 1 - inset:
                b = True
            if x <= inset:
                l = True
            if x >= w - 1 - inset:
                r = True
    return {"top": t, "bottom": b, "left": l, "right": r}


def assert_margin(img: Image.Image, name: str = "", inset: int = 1) -> None:
    touch = content_touches_border(img, inset=inset)
    hit = [k for k, v in touch.items() if v]
    if hit:
        print(f"  WARN clip-risk {name}: content touches {hit} — regenerate with margin")


def fit_contain(
    img: Image.Image,
    tw: int,
    th: int,
    *,
    margin: int = 2,
    colors: int = 48,
    hard_pixel_fn=None,
) -> Image.Image:
    """等比塞进 tw×th，四周留 margin；绝不裁切主体（只缩小）。"""
    img = img.convert("RGBA")
    # 装格前的 trim 图必然贴边，勿对输入误报；只在输出侧 assert
    inner_w = max(1, tw - margin * 2)
    inner_h = max(1, th - margin * 2)
    scale = min(inner_w / max(1, img.width), inner_h / max(1, img.height))
    nw = max(1, round(img.width * scale))
    nh = max(1, round(img.height * scale))
    if hard_pixel_fn is not None:
        pix = hard_pixel_fn(img, nw, nh, colors=colors)
    else:
        pix = img.resize((nw, nh), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(pix, ((tw - nw) // 2, (th - nh) // 2), pix)
    return canvas
