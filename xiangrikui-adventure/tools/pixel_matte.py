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
    """热品红 / 亮粉幕布（AI 常用 #FF00FF），含量化后褪色与抗锯齿溢色。

    粉主体请用黑幕；此键主要服务品红幕角色/道具。过宽会误伤粉蛾，过窄留品红边。
    """
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
    # 中段品红抗锯齿（AI 把 #FF00FF 混进轮廓）：R、B 都明显高于 G
    # 例：(175,79,146) (126,53,136) — 旧阈值漏掉 → 标题/轮廓品红边
    if (
        g <= 120
        and r >= 100
        and b >= 90
        and (r - g) >= 35
        and (b - g) >= 25
        and (r + b) >= (2 * g + 50)
    ):
        return True
    # 红偏品红 AA（B 略低于 R，仍是幕溢色，不是黄花/木板）
    if (
        g <= 100
        and r >= 150
        and b >= 70
        and (r - g) >= 50
        and (b - g) >= 15
        and (r + b) >= (2 * g + 45)
        and r >= b - 10
    ):
        return True
    return False


def is_dark_purple_screen(r: int, g: int, b: int) -> bool:
    """品红幕外圈的深紫/灰紫（会封住边缘洪水，导致「只裁格不抠」）。

    仅作幕布连通；内部紫色衣若被非键色包围则不会被吃掉。
    """
    mx = max(r, g, b)
    mn = min(r, g, b)
    if mx > 105 or mx < 18:
        return False
    if g > 58:
        return False
    if r < 24 or b < 28:
        return False
    if abs(r - b) > 48:
        return False
    if (r + b) < (2 * g + 12):
        return False
    # 排除近中性深灰（已由 is_dark_key 处理）
    if (mx - mn) < 8:
        return False
    return True


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


def is_neutral_grid_grey(r: int, g: int, b: int) -> bool:
    """旧灰格线兼容。新模板禁止灰格，仅 flood 黑幕路径可能遇到。"""
    mx = max(r, g, b)
    mn = min(r, g, b)
    if (mx - mn) > 14:
        return False
    return 48 <= mx <= 140


def is_edge_seed(r: int, g: int, b: int, a: int) -> bool:
    return (
        is_screen_key(r, g, b, a)
        or (a >= 36 and is_dark_key(r, g, b))
        or (a >= 36 and is_dark_purple_screen(r, g, b))
        or (a >= 36 and is_neutral_grid_grey(r, g, b))
    )


def _is_floodable_key(r: int, g: int, b: int, a: int) -> bool:
    return (
        is_screen_key(r, g, b, a)
        or is_dark_key(r, g, b)
        or is_dark_purple_screen(r, g, b)
        or is_neutral_grid_grey(r, g, b)
    )


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
                if _is_floodable_key(r, g, b, a):
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
        return a >= 128 and not _is_floodable_key(r, g, b, a)

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


def fringe_clean(img: Image.Image, passes: int = 3) -> Image.Image:
    """只清边缘键色溢色/白晕；禁止删粉主体、禁止删内部深色。

    关键贴透明/画布边的像素才杀；内部腮红/粉翅不碰。
    """
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
                empty_n = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if nx < 0 or ny < 0 or nx >= w or ny >= h or px[nx, ny][3] < 64:
                            near_empty = True
                            empty_n += 1
                if not near_empty:
                    continue
                # 只清品红/深紫幕溢色；禁止用 is_dark_key（会抠掉黑裤脚/描边）
                if is_screen_key(r, g, b, a) or is_dark_purple_screen(r, g, b):
                    kill.append((x, y))
                    continue
                lum = (r + g + b) / 3.0
                # 边缘白晕（抗锯齿）；禁止中性灰全杀——灰衣/裤脚边缘会被啃穿
                neutral = abs(r - g) <= 16 and abs(g - b) <= 16 and abs(r - b) <= 20
                if neutral and lum >= 160:
                    kill.append((x, y))
                    continue
                # 边缘粉紫溢色：R、B 明显高于 G（放宽 lum，旧 >140 漏掉 175,79,146）
                if r > g + 35 and b > g + 20 and g < 130 and (r + b) > (2 * g + 40):
                    kill.append((x, y))
                    continue
                # 强贴边（≥3 邻空）时更狠：红偏品红/灰紫晕 —— 仍不杀近黑
                if empty_n >= 3:
                    if g <= 120 and r >= 120 and b >= 60 and (r - g) >= 30 and (b - g) >= 8:
                        kill.append((x, y))
                        continue
                    if is_dark_purple_screen(r, g, b):
                        kill.append((x, y))
                        continue
                # 品红幕抗锯齿浅粉（左上常见）：R≈B 很高，仍偏品红
                if (
                    r >= 220
                    and b >= 200
                    and g <= 180
                    and abs(r - b) <= 40
                    and r > g + 15
                    and b > g + 10
                ):
                    kill.append((x, y))
        for x, y in kill:
            px[x, y] = (0, 0, 0, 0)
    return img


def _is_orphan_screen_key(r: int, g: int, b: int, a: int) -> bool:
    """strip_orphan 只认热品红/深紫幕残。禁止 dark_key / 中性灰（灰衣黑裤会被整块删光）。"""
    return is_screen_key(r, g, b, a) or is_dark_purple_screen(r, g, b)


def strip_orphan_screen(img: Image.Image, *, max_keep: int = 400) -> Image.Image:
    """清掉封在轮廓里的品红/深紫小岛（量化粉条、格内残幕）。

    - 只扫品红系键，不动灰衣/黑裤/描边。
    - 不贴实体色 → 删（真残幕岛）。
    - 贴实体但块很小（≤max_keep）→ 当溢色环删。
    - 贴实体且块很大 → 保留（角色故意画的品红瞳/装饰）。
    """
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()

    def is_solid(r: int, g: int, b: int, a: int) -> bool:
        return a >= 128 and not _is_orphan_screen_key(r, g, b, a)

    seen = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if seen[y][x]:
                continue
            r, g, b, a = px[x, y]
            if a < 128 or not _is_orphan_screen_key(r, g, b, a):
                seen[y][x] = True
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            seen[y][x] = True
            cells: list[tuple[int, int]] = []
            touches_solid = False
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
                        if is_solid(nr, ng, nb, na):
                            touches_solid = True
                            seen[ny][nx] = True
                            continue
                        if _is_orphan_screen_key(nr, ng, nb, na):
                            seen[ny][nx] = True
                            q.append((nx, ny))
                        else:
                            seen[ny][nx] = True
            if (not touches_solid) or len(cells) <= max_keep:
                for cx, cy in cells:
                    px[cx, cy] = (0, 0, 0, 0)
    return img


def keep_largest_blob(img: Image.Image, min_keep_ratio: float = 0.05) -> Image.Image:
    """去掉游离噪点；保留与主连通域邻近的中等碎块（翅膀尖、被幕洞切开的肢体）。"""
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
    # 若最大块明显小于总实体（幕洞把身体切碎），合并所有 ≥ 次大阈值的邻近块
    total = sum(len(b) for b in blobs)
    main = blobs[0]
    keep = set(main)
    main_n = len(main)
    # 主块过碎：放宽邻近合并距离
    pad = 24 if main_n < total * 0.55 else 6
    mxs = [p[0] for p in main]
    mys = [p[1] for p in main]
    for blob in blobs[1:]:
        if len(blob) < max(8, int(main_n * min_keep_ratio)):
            continue
        xs = [p[0] for p in blob]
        ys = [p[1] for p in blob]
        if (
            max(xs) >= min(mxs) - pad
            and min(xs) <= max(mxs) + pad
            and max(ys) >= min(mys) - pad
            and min(ys) <= max(mys) + pad
        ):
            keep.update(blob)
            # 扩展主 bbox，便于链式合并切开的肢体
            mxs.extend(xs)
            mys.extend(ys)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    opx = out.load()
    for x, y in keep:
        opx[x, y] = px[x, y]
    return out


def despill_chroma_edges(
    img: Image.Image,
    fill_hex: str,
    *,
    ring: int = 2,
    lum_max: float = 90.0,
) -> Image.Image:
    """学自 spritebrew `despillChromaEdges`：只改贴透明边的溢色，不改 alpha。

    - 品红幕：削弱轮廓环上偏品红分量（min(R,B)-G）
    - 绿垫：削弱轮廓环上偏绿分量（G-max(R,B)）
    - 黑/灰幕：no-op（中性幕无色相溢色可剥）
    - 亮度门控：只动 lum≤lum_max 的暗环，保护腮红/粉衣高光
    """
    m = fill_hex.strip().lstrip("#")
    if len(m) != 6:
        return img
    try:
        fr, fg, fb = int(m[0:2], 16), int(m[2:4], 16), int(m[4:6], 16)
    except ValueError:
        return img
    magenta = fr >= fg + 60 and fb >= fg + 60
    green = fg >= max(fr, fb) + 60
    if not magenta and not green:
        return img

    img = img.convert("RGBA")
    w, h = img.size
    if w == 0 or h == 0:
        return img
    px = img.load()
    transparent = [[px[x, y][3] == 0 for x in range(w)] for y in range(h)]

    def dilate(src: list[list[bool]]) -> list[list[bool]]:
        out = [[False] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                if src[y][x]:
                    out[y][x] = True
                    continue
                hit = False
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and src[ny][nx]:
                            hit = True
                            break
                    if hit:
                        break
                out[y][x] = hit
        return out

    band = transparent
    for _ in range(max(1, ring)):
        band = dilate(band)

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0 or not band[y][x]:
                continue
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum > lum_max:
                continue
            if magenta:
                excess = min(r, b) - g
                if excess > 0:
                    px[x, y] = (r - excess, g, b - excess, a)
            else:
                excess = g - max(r, b)
                if excess > 0:
                    px[x, y] = (r, g - excess, b, a)
    return img


def matte(
    img: Image.Image,
    *,
    blob: bool = True,
    fill_hex: str | None = None,
) -> Image.Image:
    """标准管线：边缘洪水抠幕 → 清封闭黑底 → 清残品红岛 → fringe → despill → 可选主连通域。

    fill_hex：生图/量化幕布色（如 #FF00FF / #00FF00）。黑幕传 None 或 #000000（despill no-op）。
    """
    out = strip_orphan_dark(chroma_flood(img))
    out = strip_orphan_screen(out)
    out = fringe_clean(out)
    if fill_hex:
        out = despill_chroma_edges(out, fill_hex)
    if blob:
        out = keep_largest_blob(out)
    return out


_rembg_sessions: dict[str, object] = {}


def _get_rembg_session(model: str = "u2net"):
    if model not in _rembg_sessions:
        from rembg import new_session

        _rembg_sessions[model] = new_session(model)
    return _rembg_sessions[model]


def fill_internal_holes(img: Image.Image, *, max_hole: int = 800) -> Image.Image:
    """把被实心围住的透明岛填回（用邻域色），保留从画布边连进来的真背景。"""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    seen = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if px[x, y][3] < 128 and not seen[y][x]:
                seen[y][x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if px[x, y][3] < 128 and not seen[y][x]:
                seen[y][x] = True
                q.append((x, y))
    while q:
        cx, cy = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and px[nx, ny][3] < 128:
                seen[ny][nx] = True
                q.append((nx, ny))
    # 未从边到达的透明像素 = 内洞
    holes: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if px[x, y][3] < 128 and not seen[y][x]:
                holes.append((x, y))
    if not holes or len(holes) > max_hole * 20:
        # 过大则可能是误判（几乎全空），跳过
        if len(holes) > max_hole * 20:
            return img
    # 按连通域限制单洞大小
    hole_seen = set()
    for hx, hy in holes:
        if (hx, hy) in hole_seen:
            continue
        q2: deque[tuple[int, int]] = deque([(hx, hy)])
        hole_seen.add((hx, hy))
        cells: list[tuple[int, int]] = []
        while q2:
            cx, cy = q2.popleft()
            cells.append((cx, cy))
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = cx + dx, cy + dy
                if (
                    0 <= nx < w
                    and 0 <= ny < h
                    and (nx, ny) not in hole_seen
                    and px[nx, ny][3] < 128
                    and not seen[ny][nx]
                ):
                    hole_seen.add((nx, ny))
                    q2.append((nx, ny))
        if len(cells) > max_hole:
            continue
        for cx, cy in cells:
            # 邻域实心色均值
            rs = gs = bs = n = 0
            for dy in (-2, -1, 0, 1, 2):
                for dx in (-2, -1, 0, 1, 2):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] >= 128:
                        r, g, b, _ = px[nx, ny]
                        rs += r
                        gs += g
                        bs += b
                        n += 1
            if n:
                px[cx, cy] = (rs // n, gs // n, bs // n, 255)
    return img


def matte_rembg(
    img: Image.Image,
    *,
    blob: bool = True,
    fill_hex: str | None = "#FF00FF",
    model: str = "u2net",
) -> Image.Image:
    """AI 抠图（rembg）。mask 回贴原图像素，填内洞，保住深色角/蹄。

    **不做** strip_orphan_dark / 深色键洪水。
    """
    from rembg import remove

    img = img.convert("RGBA")
    session = _get_rembg_session(model)
    # only_mask + post_process；alpha_matting 对 chroma 幕不稳定，默认关
    mask = remove(
        img,
        session=session,
        only_mask=True,
        post_process_mask=True,
    )
    if not isinstance(mask, Image.Image):
        mask = Image.open(mask)  # type: ignore[arg-type]
    mask = mask.convert("L")
    # 略扩张再收回：保住细角尖（形态学 close）
    mpx = mask.load()
    w, h = mask.size
    bin_a = [[1 if mpx[x, y] >= 90 else 0 for x in range(w)] for y in range(h)]
    for _ in range(2):  # dilate
        nxt = [row[:] for row in bin_a]
        for y in range(h):
            for x in range(w):
                if bin_a[y][x]:
                    continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and bin_a[ny][nx]:
                            nxt[y][x] = 1
                            break
                    else:
                        continue
                    break
        bin_a = nxt
    for _ in range(1):  # erode 少一圈 → 净扩张 1px
        nxt = [row[:] for row in bin_a]
        for y in range(h):
            for x in range(w):
                if not bin_a[y][x]:
                    continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if nx < 0 or ny < 0 or nx >= w or ny >= h or not bin_a[ny][nx]:
                            nxt[y][x] = 0
                            break
                    else:
                        continue
                    break
        bin_a = nxt
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    opx = out.load()
    ipx = img.load()
    for y in range(h):
        for x in range(w):
            if not bin_a[y][x]:
                continue
            r, g, b, a = ipx[x, y]
            if is_screen_key(r, g, b, a):
                continue
            opx[x, y] = (r, g, b, 255)
    out = fill_internal_holes(out, max_hole=600)
    out = strip_orphan_screen(out)
    # rembg 路径 fringe 轻一点，避免啃棕角边
    out = fringe_clean(out, passes=1)
    if fill_hex and fill_hex.upper() not in ("#000000", "#000"):
        out = despill_chroma_edges(out, fill_hex)
    if blob:
        out = keep_largest_blob(out, min_keep_ratio=0.02)
    return out


def is_pure_black_key(r: int, g: int, b: int, a: int = 255) -> bool:
    """纯黑幕（ingest 旧横条），不含棕蹄/深棕角（那些 G/R 通常 >25）。"""
    if a < 36:
        return True
    return r <= 22 and g <= 22 and b <= 22


def strip_edge_pure_black(img: Image.Image) -> Image.Image:
    """从画布边洪水清纯黑底；不沿棕色走，保住蹄/角/眼（眼被彩色围住）。"""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    visited = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()

    def try_seed(x: int, y: int) -> None:
        r, g, b, a = px[x, y]
        if is_pure_black_key(r, g, b, a):
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
                visited[ny][nx] = True
                if is_pure_black_key(r, g, b, a):
                    q.append((nx, ny))
    return img


def is_hot_magenta_only(r: int, g: int, b: int, a: int = 255) -> bool:
    """严格热品红：只认 #FF00FF 及近邻 AA。禁止宽粉键（会抠穿白衣/肤色）。"""
    if a < 36:
        return True
    # 真热品红：R、B 都很高，G 极低
    if r >= 200 and b >= 190 and g <= 70 and abs(r - b) <= 55:
        return True
    # 略褪色但仍是幕：G 仍很低
    if r >= 220 and b >= 200 and g <= 55:
        return True
    return False


def matte_hot_magenta(img: Image.Image, *, blob: bool = False) -> Image.Image:
    """Boss 等白衣+深色体：只抠热品红，不做浅灰 rekey、不扫宽粉、默认不丢次大块。"""
    img = img.convert("RGBA")
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ipx, opx = img.load(), out.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = ipx[x, y]
            if is_hot_magenta_only(r, g, b, a):
                continue
            if a < 36:
                continue
            opx[x, y] = (r, g, b, 255)
    out = fringe_clean(out, passes=1)
    out = despill_chroma_edges(out, "#FF00FF")
    if blob:
        out = keep_largest_blob(out, min_keep_ratio=0.01)
    return out


def matte_chroma(
    img: Image.Image,
    *,
    blob: bool = True,
    fill_hex: str | None = "#FF00FF",
) -> Image.Image:
    """只抠热品红幕。禁止扫黑/扫中性灰。角色禁画品红（否则会被抠穿）。"""
    img = img.convert("RGBA")
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ipx, opx = img.load(), out.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = ipx[x, y]
            if a < 36:
                continue
            if (
                is_screen_key(r, g, b, a)
                or is_dark_purple_screen(r, g, b)
            ):
                continue
            opx[x, y] = (r, g, b, 255)
    out = fill_internal_holes(out, max_hole=1200)
    out = strip_orphan_screen(out)
    out = fringe_clean(out, passes=2)
    if fill_hex and fill_hex.upper() not in ("#000000", "#000"):
        out = despill_chroma_edges(out, fill_hex)
    if blob:
        # 高分辨率填格：主连通域可能被幕洞切开；保留邻近大块，阈值放宽
        out = keep_largest_blob(out, min_keep_ratio=0.01)
    return out


def is_light_template_grey(r: int, g: int, b: int) -> bool:
    """AI 常无视幕色、把格底画成浅灰（~#C8C8C8）。与炭黑裤（mx≤110）分离。"""
    mx = max(r, g, b)
    mn = min(r, g, b)
    if (mx - mn) > 18:
        return False
    return mx >= 150


def rekey_template_bg_to_screen(
    img: Image.Image,
    screen_hex: str = "#FF00FF",
) -> Image.Image:
    """把边缘连通的浅灰格底 / 电青格线 / 已有幕色，统一重键为 screen_hex。

    不动角色内部深灰裤/描边（不与边缘浅灰连通）。GenerateImage 常无视品红幕时用。
    """
    img = img.convert("RGBA")
    h = screen_hex.strip().lstrip("#")
    sr, sg, sb = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    screen = (sr, sg, sb, 255)
    w, hgt = img.size
    px = img.load()
    visited = [[False] * w for _ in range(hgt)]
    q: deque[tuple[int, int]] = deque()

    def is_rekey(r: int, g: int, b: int, a: int) -> bool:
        if a < 36:
            return True
        if is_screen_key(r, g, b, a):
            return True
        if is_light_template_grey(r, g, b):
            return True
        if is_neutral_grid_grey(r, g, b):
            return True
        if is_matte_black(r, g, b):
            return True
        # AI 偶发青线/标签残（非角色绿）：高饱和青且 R 极低
        if a >= 36 and r <= 70 and g >= 170 and b >= 170 and abs(g - b) <= 60:
            return True
        return False

    def try_seed(x: int, y: int) -> None:
        r, g, b, a = px[x, y]
        if is_rekey(r, g, b, a):
            q.append((x, y))
            visited[y][x] = True

    for x in range(w):
        try_seed(x, 0)
        try_seed(x, hgt - 1)
    for y in range(hgt):
        try_seed(0, y)
        try_seed(w - 1, y)

    while q:
        x, y = q.popleft()
        px[x, y] = screen
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if nx < 0 or ny < 0 or nx >= w or ny >= hgt or visited[ny][nx]:
                continue
            visited[ny][nx] = True
            r, g, b, a = px[nx, ny]
            if is_rekey(r, g, b, a):
                q.append((nx, ny))
    return img


def matte_auto(
    img: Image.Image,
    *,
    mode: str = "flood",
    blob: bool = True,
    fill_hex: str | None = None,
) -> Image.Image:
    """mode=flood|chroma|rembg。品红幕深色主体优先 chroma；rembg 需 CUDA/GPU ORT 才划算。"""
    m = str(mode).lower()
    if m in ("chroma", "key", "colorkey", "screen"):
        return matte_chroma(img, blob=blob, fill_hex=fill_hex or "#FF00FF")
    if m in ("rembg", "ai", "u2net"):
        return matte_rembg(img, blob=blob, fill_hex=fill_hex or "#FF00FF")
    return matte(img, blob=blob, fill_hex=fill_hex)


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
