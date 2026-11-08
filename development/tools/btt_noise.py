"""Small helpers for procedural, deliberately low-fi textures.

Everything here is our own code: tileable value noise, colour ramps and a
few drawing helpers. Images are numpy float arrays (H, W, 3) in 0..255.
"""
import numpy as np
from PIL import Image


def rng(seed):
    return np.random.default_rng(seed)


def _upscale_wrap(grid, w, h):
    """Bilinear upscale of a small random grid, wrapping at the edges so the
    result tiles seamlessly."""
    gh, gw = grid.shape
    ys = np.arange(h) * gh / h
    xs = np.arange(w) * gw / w
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    # smoothstep for softer cells
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    y1 = (y0 + 1) % gh
    x1 = (x0 + 1) % gw
    a = grid[y0][:, x0]
    b = grid[y0][:, x1]
    c = grid[y1][:, x0]
    d = grid[y1][:, x1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def noise(w, h, cx, cy, seed):
    """Tileable value noise, cx*cy random cells, output 0..1."""
    r = rng(seed)
    return _upscale_wrap(r.random((cy, cx)), w, h)


def fbm(w, h, cx, cy, seed, octaves=4, gain=0.5):
    total = np.zeros((h, w))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        mx, my = cx * (2 ** o), cy * (2 ** o)
        mx, my = min(mx, w), min(my, h)
        total += amp * noise(w, h, mx, my, seed + o * 101)
        norm += amp
        amp *= gain
    return total / norm


def grain(w, h, seed, amount=1.0):
    """Per-pixel white noise, centred on 0."""
    return (rng(seed).random((h, w)) - 0.5) * 2.0 * amount


def ramp(t, stops):
    """Map scalar field t (0..1) through colour stops [(pos, (r,g,b)), ...]."""
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,))
    pos = np.array([p for p, _ in stops])
    cols = np.array([c for _, c in stops], dtype=float)
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, cols[:, ch])
    return out


def solid(w, h, col):
    img = np.zeros((h, w, 3))
    img[:] = col
    return img


def mul(img, f):
    if np.ndim(f) == 2:
        f = f[..., None]
    return img * f


def mix(a, b, t):
    if np.ndim(t) == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def rect(img, x0, y0, x1, y1, col, alpha=1.0):
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(img.shape[1], int(x1)), min(img.shape[0], int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - alpha) + np.array(col, float) * alpha


def frame(img, x0, y0, x1, y1, col, t=1):
    rect(img, x0, y0, x1, y0 + t, col)
    rect(img, x0, y1 - t, x1, y1, col)
    rect(img, x0, y0, x0 + t, y1, col)
    rect(img, x1 - t, y0, x1, y1, col)


def disc(img, cx, cy, r, col, alpha=1.0):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    m = ((xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2) <= r * r
    img[m] = img[m] * (1 - alpha) + np.array(col, float) * alpha
    return m


def bevel(img, x0, y0, x1, y1, light=1.18, dark=0.7):
    """Old-school 1px bevel: lighter top/left, darker bottom/right."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    img[y0, x0:x1] *= light
    img[y0:y1, x0] *= light
    img[y1 - 1, x0:x1] *= dark
    img[y0:y1, x1 - 1] *= dark


def dirt(img, seed, strength=0.25, cells=4):
    """Large soft blotches of grime."""
    h, w = img.shape[:2]
    n = fbm(w, h, cells, cells, seed, octaves=3)
    f = 1.0 - strength * np.clip((n - 0.45) * 2.5, 0, 1)
    return mul(img, f)


def to_pil(img):
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
