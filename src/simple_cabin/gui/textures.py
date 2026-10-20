"""Procedural textures: wood, stone, burr veneer, bark, woven jute and knit.

Made with numpy the first time they're ever asked for, then kept: in
memory for the rest of the run, and as PNGs in the cache folder (once
set_cache_dir has been called) so later launches just load them. Each is a
QImage the scenes clip to a shape and shade on top of. Bump TEXTURE_VERSION
after changing how any texture looks, so old files get remade.
"""
from __future__ import annotations

import functools
import hashlib
import random
import shutil
import threading
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath

TEXTURE_VERSION = 1
_cache_dir: Path | None = None
_memory: dict = {}
_lock = threading.Lock()


def set_cache_dir(directory: Path) -> None:
    """Keep generated textures as files here (and drop older versions')."""
    global _cache_dir
    _cache_dir = directory / f"v{TEXTURE_VERSION}"
    try:
        _cache_dir.mkdir(parents=True, exist_ok=True)
        for old in directory.glob("v*"):
            if old.is_dir() and old != _cache_dir:
                shutil.rmtree(old, ignore_errors=True)
    except OSError:
        _cache_dir = None


def cached(fn):
    """Remember a texture in memory and on disk, keyed by its arguments."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = (fn.__name__, args, tuple(sorted(kwargs.items())))
        with _lock:
            img = _memory.get(key)
        if img is not None:
            return img
        path = None
        if _cache_dir is not None:
            digest = hashlib.sha1(repr(key).encode()).hexdigest()[:20]
            path = _cache_dir / f"{fn.__name__}-{digest}.png"
            if path.exists():
                loaded = QImage(str(path))
                if not loaded.isNull():
                    img = loaded.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        if img is None:
            img = fn(*args, **kwargs)
            if path is not None:
                tmp = path.with_suffix(".tmp.png")
                if img.save(str(tmp), "PNG", 90):  # light compression: quick to save and load
                    try:
                        tmp.replace(path)
                    except OSError:
                        pass
        with _lock:
            _memory[key] = img
        return img

    return wrapper


# --- noise


def value_noise(h: int, w: int, cell_y: float, cell_x: float, rng: np.random.Generator) -> np.ndarray:
    """Smooth random values in 0..1, changing every cell_y × cell_x pixels."""
    gh, gw = int(h / cell_y) + 3, int(w / cell_x) + 3
    grid = rng.random((gh, gw))
    ys = np.arange(h) / cell_y
    xs = np.arange(w) / cell_x
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = ys - y0, xs - x0
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = grid[y0][:, x0]
    b = grid[y0][:, x0 + 1]
    c = grid[y0 + 1][:, x0]
    d = grid[y0 + 1][:, x0 + 1]
    top = a + (b - a) * fx[None, :]
    bottom = c + (d - c) * fx[None, :]
    return top + (bottom - top) * fy[:, None]


def fbm(h: int, w: int, cell_y: float, cell_x: float, seed: int, octaves: int = 4, gain: float = 0.5) -> np.ndarray:
    """Fractal noise in roughly 0..1: several octaves of value noise."""
    rng = np.random.default_rng(seed)
    total = np.zeros((h, w))
    amp, norm = 1.0, 0.0
    for _ in range(octaves):
        total += amp * value_noise(h, w, max(1.0, cell_y), max(1.0, cell_x), rng)
        norm += amp
        amp *= gain
        cell_y, cell_x = cell_y / 2, cell_x / 2
    return total / norm


def colour_map(t: np.ndarray, stops: list[tuple[float, tuple[int, int, int]]]) -> np.ndarray:
    """Map 0..1 values through colour stops to an RGB float array (0..255)."""
    t = np.clip(t, 0, 1)
    positions = [s[0] for s in stops]
    out = np.zeros(t.shape + (3,))
    for ch in range(3):
        out[..., ch] = np.interp(t, positions, [s[1][ch] for s in stops])
    return out


def to_qimage(rgb: np.ndarray, alpha: np.ndarray | None = None) -> QImage:
    h, w = rgb.shape[:2]
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    rgba[..., 3] = 255 if alpha is None else np.clip(alpha * 255, 0, 255).astype(np.uint8)
    img = QImage(rgba.data, w, h, 4 * w, QImage.Format_RGBA8888)
    return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)  # (also copies out of numpy)


def from_qimage(img: QImage) -> np.ndarray:
    img = img.convertToFormat(QImage.Format_RGBA8888)
    ptr = img.constBits()
    return np.frombuffer(ptr, dtype=np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[:, : img.width()].astype(float)


# --- palettes

PINE = [(0.0, (120, 70, 34)), (0.35, (170, 108, 56)), (0.65, (204, 140, 78)), (1.0, (228, 176, 112))]
OAK = [(0.0, (70, 38, 20)), (0.4, (118, 68, 36)), (0.75, (150, 92, 50)), (1.0, (178, 120, 70))]
WALNUT = [(0.0, (40, 18, 10)), (0.35, (78, 34, 18)), (0.7, (116, 56, 30)), (1.0, (156, 86, 48))]
WEATHERED = [(0.0, (60, 40, 26)), (0.4, (104, 72, 46)), (0.75, (140, 100, 64)), (1.0, (168, 128, 86))]
CEDAR = [(0.0, (90, 48, 22)), (0.4, (140, 78, 38)), (0.75, (178, 108, 56)), (1.0, (208, 140, 80))]
PALETTES = {"pine": PINE, "oak": OAK, "walnut": WALNUT, "weathered": WEATHERED, "cedar": CEDAR}


# --- wood


@cached
def wood(w: int, h: int, plank: int = 60, horizontal: bool = True, palette: str = "pine", seed: int = 1,
         seams: bool = True, rough: float = 0.0) -> QImage:
    """Wooden boards: grain running along each board, growth-ring figure,
    a different tint per board, dark seams and staggered butt joints."""
    L, A = (w, h) if horizontal else (h, w)  # along / across the grain
    rng = np.random.default_rng(seed)
    across = np.arange(A)[:, None] * np.ones((1, L))
    along = np.ones((A, 1)) * np.arange(L)[None, :]
    streak = fbm(A, L, 2.5, 140, seed, 4)
    wave = fbm(A, L, 40, 220, seed + 1, 2)
    rings = np.sin((across + wave * 60) / rng.uniform(5, 8) + along / 400)
    figure = 0.55 + 0.32 * (streak - 0.5) * 2 + 0.12 * rings

    row = (across // plank).astype(int)
    n_rows = int(A // plank) + 2
    tints = rng.normal(0, 0.07, n_rows)
    figure += tints[row]
    if rough:
        figure += rough * (fbm(A, L, 6, 6, seed + 2, 3) - 0.5)

    # knots (each only touches a small window)
    for _ in range(int(L * A / 60000) + 1):
        ky, kx = int(rng.uniform(0, A)), int(rng.uniform(0, L))
        r = rng.uniform(3, 7)
        y0, y1, x0, x1 = max(0, ky - 20), min(A, ky + 20), max(0, kx - 40), min(L, kx + 40)
        d = np.sqrt(((across[y0:y1, x0:x1] - ky) / r) ** 2 + ((along[y0:y1, x0:x1] - kx) / (r * 2.2)) ** 2)
        figure[y0:y1, x0:x1] -= 0.45 * np.exp(-d * d)

    shade = np.ones((A, L))
    if seams:
        pos = across % plank
        shade *= np.where(pos < 1.5, 0.45, 1.0) * np.where(pos > plank - 2, 0.8, 1.0)
        # butt joints, staggered
        for r_i in range(n_rows):
            y0, y1 = r_i * plank, min(A, (r_i + 1) * plank)
            x = rng.uniform(0, 300)
            while x < L and y0 < A:
                xi = int(x)
                shade[y0:y1, max(0, xi - 1):xi + 1] *= 0.5
                x += rng.uniform(260, 520)
    rgb = colour_map(figure, PALETTES[palette]) * shade[..., None]
    if not horizontal:
        rgb = rgb.transpose(1, 0, 2)
    return to_qimage(rgb)


@cached
def burl(w: int, h: int, seed: int = 3) -> QImage:
    """Burr walnut / flame veneer for the clock case: swirling figure."""
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    warp = fbm(h, w, 60, 25, seed, 3)
    v = fbm(h, w, 40, 10, seed + 2, 4)
    # flame figure: tall feathery chevrons rising from the centre line
    flame = np.sin(np.abs(xs - w / 2) * 0.09 + ys * 0.035 + warp * 10)
    figure = 0.5 + 0.18 * flame + 0.35 * (v - 0.5)
    figure += 0.12 * (fbm(h, w, 14, 1.5, seed + 4, 2) - 0.5)  # fine straight grain
    return to_qimage(colour_map(figure, WALNUT))


@cached
def bark(w: int, h: int, seed: int = 5) -> QImage:
    """Pine bark: dark furrows between long reddish-grey plates."""
    plates = fbm(h, w, 26, 7, seed, 4)
    fine = fbm(h, w, 6, 2, seed + 1, 3)
    furrow = np.clip((plates - 0.38) * 4, 0, 1)
    t = 0.15 + 0.6 * furrow + 0.25 * (fine - 0.5)
    stops = [(0.0, (22, 16, 12)), (0.4, (58, 42, 32)), (0.75, (104, 80, 62)), (1.0, (138, 110, 88))]
    return to_qimage(colour_map(t, stops))


@cached
def jute(w: int, h: int, seed: int = 7) -> QImage:
    """A chunky braided jute rug: rows of plaits leaning alternately."""
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    row_h = 14.0
    row = (ys // row_h).astype(int)
    v = (ys % row_h) / row_h
    lean = np.where(row % 2 == 0, 1.0, -1.0)
    u = ((xs + v * row_h * 0.9 * lean) % 11) / 11
    strand = np.sin(np.pi * u) * np.sin(np.pi * v) ** 0.6
    noise = fbm(h, w, 3, 3, seed, 3)
    t = 0.2 + 0.65 * strand + 0.25 * (noise - 0.5)
    stops = [(0.0, (84, 62, 40)), (0.45, (150, 118, 80)), (0.8, (196, 164, 118)), (1.0, (220, 194, 150))]
    return to_qimage(colour_map(t, stops))


@cached
def knit(w: int, h: int, base: tuple[int, int, int] = (150, 60, 36), seed: int = 8) -> QImage:
    """Chunky cable knit (the throw on the sofa)."""
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    col_w, row_h = 12.0, 9.0
    cu = (xs % col_w) / col_w
    cv = ((ys + np.where((xs // col_w) % 2 == 0, 0, row_h / 2)) % row_h) / row_h
    # a "V" stitch in each cell
    stitch = np.exp(-((np.abs(cu - 0.5) * 2 - cv) ** 2) / 0.08)
    noise = fbm(h, w, 4, 4, seed, 2)
    t = 0.25 + 0.6 * stitch + 0.2 * (noise - 0.5)
    r, g, b = base
    stops = [(0.0, (r * 0.4, g * 0.4, b * 0.4)), (0.6, (r, g, b)), (1.0, (min(255, r * 1.3), min(255, g * 1.3), min(255, b * 1.3)))]
    return to_qimage(colour_map(t, stops))


@cached
def fabric(w: int, h: int, base: tuple[int, int, int] = (226, 216, 196), seed: int = 9) -> QImage:
    """Fine woven upholstery (linen)."""
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    weave = 0.5 + 0.25 * np.sin(xs * 2.2) * np.sin(ys * 2.2)
    noise = fbm(h, w, 2, 6, seed, 2)
    t = 0.75 + 0.12 * (weave - 0.5) + 0.2 * (noise - 0.5)
    rgb = np.stack([np.full((h, w), c) * t for c in base], -1)
    return to_qimage(rgb)


@cached
def stone_wall(w: int, h: int, seed: int = 11, size: float = 1.0) -> QImage:
    """Tightly stacked rough fieldstone: blocky stones in rough courses,
    greys and tans, thin dark joints, each stone lit from above."""
    from simple_cabin.gui.paint import radial

    rng = random.Random(seed)
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(40, 35, 31))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    y = -12.0
    while y < h:
        course = rng.uniform(30, 58) * size
        x = -rng.uniform(0, 60)
        while x < w:
            sw = rng.uniform(45, 115) * size
            r = QRectF(x + 1.5, y + 1.5, sw - 3, course - 3 + rng.uniform(-3, 4))
            # a blocky stone: an irregular octagon with slightly rounded corners
            cut = min(r.width(), r.height()) * 0.18
            pts = [(r.left() + cut * rng.uniform(0.3, 1.2), r.top() + rng.uniform(-1, 2)),
                   (r.right() - cut * rng.uniform(0.3, 1.2), r.top() + rng.uniform(-1, 2)),
                   (r.right() + rng.uniform(-2, 1), r.top() + cut * rng.uniform(0.4, 1.2)),
                   (r.right() + rng.uniform(-2, 1), r.bottom() - cut * rng.uniform(0.4, 1.2)),
                   (r.right() - cut * rng.uniform(0.3, 1.2), r.bottom() + rng.uniform(-2, 1)),
                   (r.left() + cut * rng.uniform(0.3, 1.2), r.bottom() + rng.uniform(-2, 1)),
                   (r.left() + rng.uniform(-1, 2), r.bottom() - cut * rng.uniform(0.4, 1.2)),
                   (r.left() + rng.uniform(-1, 2), r.top() + cut * rng.uniform(0.4, 1.2))]
            path = QPainterPath()
            path.moveTo((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
            for i in range(1, 9):
                x1, y1 = pts[i % 8]
                x2, y2 = pts[(i + 1) % 8]
                path.quadTo(x1, y1, (x1 + x2) / 2, (y1 + y2) / 2)
            path.closeSubpath()
            base = rng.uniform(100, 165)
            kind = rng.random()
            if kind < 0.5:  # grey
                c = QColor(int(base), int(base * 0.98), int(base * 0.94))
            elif kind < 0.88:  # tan
                c = QColor(int(base * 1.06), int(base * 0.97), int(base * 0.84))
            else:  # brown
                c = QColor(int(base * 0.95), int(base * 0.8), int(base * 0.64))
            g = radial(r.center().x() - r.width() * 0.15, r.top() + r.height() * 0.2, max(r.width(), r.height()) * 0.85,
                       (0, c.lighter(118)), (0.6, c), (1, c.darker(165)))
            p.setBrush(g)
            p.drawPath(path)
            x += sw
        y += course
    p.end()
    # rough faces: grit, pits and broad mottling over everything
    arr = from_qimage(img)
    grit = fbm(h, w, 2.5, 2.5, seed, 2)
    pits = fbm(h, w, 7, 7, seed + 2, 3)
    mottle = fbm(h, w, 28, 28, seed + 1, 3)
    arr[..., :3] *= (0.7 + 0.35 * grit + 0.35 * (pits - 0.5) + 0.25 * (mottle - 0.5) + 0.15)[..., None]
    return to_qimage(arr[..., :3])


@cached
def forest_floor(w: int, h: int, seed: int = 13) -> QImage:
    """Pine needles, earth and moss under the trees."""
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    patches = fbm(h, w, 24, 40, seed, 4)
    needles = fbm(h, w, 1.5, 9, seed + 1, 2)
    moss = np.clip((fbm(h, w, 30, 30, seed + 2, 3) - 0.55) * 4, 0, 1)
    t = 0.3 + 0.4 * (patches - 0.5) * 2 + 0.3 * (needles - 0.5) * 2
    earth = colour_map(t, [(0.0, (40, 30, 20)), (0.4, (86, 62, 38)), (0.75, (130, 96, 58)), (1.0, (160, 124, 80))])
    green = colour_map(t, [(0.0, (40, 52, 26)), (1.0, (96, 116, 56))])
    return to_qimage(earth * (1 - moss[..., None]) + green * moss[..., None])


def shade_rect(p: QPainter, rect: QRectF, top: float = 0.0, bottom: float = 0.35, left: float = 0.0, right: float = 0.0) -> None:
    """Darken a drawn area towards its edges (multiply), for volume."""
    from simple_cabin.gui.paint import hgrad, vgrad

    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Multiply)
    if top or bottom:
        p.fillRect(rect, vgrad(rect.top(), rect.bottom(), (0, QColor.fromRgbF(1 - top, 1 - top, 1 - top)),
                               (0.5, QColor(255, 255, 255)), (1, QColor.fromRgbF(1 - bottom, 1 - bottom, 1 - bottom))))
    if left or right:
        p.fillRect(rect, hgrad(rect.left(), rect.right(), (0, QColor.fromRgbF(1 - left, 1 - left, 1 - left)),
                               (0.5, QColor(255, 255, 255)), (1, QColor.fromRgbF(1 - right, 1 - right, 1 - right))))
    p.restore()


def draw_textured(p: QPainter, shape, texture: QImage, offset: QPointF = QPointF(0, 0)) -> None:
    """Fill a QPainterPath or QRectF with a texture (drawn at 1 texel = 1 unit)."""
    p.save()
    if isinstance(shape, QRectF):
        p.setClipRect(shape, Qt.IntersectClip)
        rect = shape
    else:
        p.setClipPath(shape, Qt.IntersectClip)
        rect = shape.boundingRect()
    p.drawImage(QPointF(rect.left() + offset.x(), rect.top() + offset.y()), texture)
    p.restore()
