#!/usr/bin/env python3
"""Before the Thaw - procedural texture generator.

Creates the source PNGs for the house WAD in development/textures_src/house/
and the skybox TGAs in game/gfx/env/.

All textures are generated from scratch (no third-party or Half-Life art).
Resolution and colour depth are deliberately period-correct: 32..128 px,
later quantised to an 8-bit palette per texture by make_wad.py.

Usage:  python3 development/tools/gen_textures.py
After editing/painting the PNGs by hand you do NOT need to rerun this
script - just run make_wad.py.  Rerunning it overwrites the PNGs.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from btt_noise import (rng, noise, fbm, grain, ramp, solid, mul, mix, rect,
                       frame, disc, bevel, dirt, to_pil)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "development", "textures_src", "house")
SKY_OUT = os.path.join(ROOT, "game", "gfx", "env")

TEX = {}


def tex(name):
    def deco(fn):
        TEX[name] = fn
        return fn
    return deco


# ---------------------------------------------------------------- wood bits
def wood_grain(w, h, seed, along="x", cells=6, streak=24):
    """Stretched noise that reads as wood fibres."""
    if along == "x":
        g = fbm(w, h, max(1, w // streak), cells * 4, seed, octaves=3)
    else:
        g = fbm(w, h, cells * 4, max(1, h // streak), seed, octaves=3)
    return g


def boards(w, h, board, seed, base, along="x", gap_col=(18, 13, 10),
           var=0.18, knots=2):
    """Generic board pattern. along='x' -> boards run horizontally."""
    r = rng(seed)
    img = np.zeros((h, w, 3))
    g = wood_grain(w, h, seed, along)
    n = (h if along == "x" else w) // board
    for i in range(n):
        shade = 1.0 + (r.random() - 0.5) * 2 * var
        tint = np.array(base) * shade
        tint = tint * (1 + (r.random(3) - 0.5) * 0.08)
        if along == "x":
            sl = (slice(i * board, (i + 1) * board), slice(None))
        else:
            sl = (slice(None), slice(i * board, (i + 1) * board))
        local = g[sl]
        img[sl] = tint * (0.78 + 0.4 * local[..., None])
        # board end joints (butt joints) at random spots
        if along == "x" and r.random() < 0.6:
            jx = r.integers(4, w - 4)
            img[i * board:(i + 1) * board, jx] = gap_col
        if along == "y" and r.random() < 0.3:
            jy = r.integers(4, h - 4)
            img[jy, i * board:(i + 1) * board] = gap_col
    # gaps between boards
    for i in range(n):
        if along == "x":
            img[i * board, :] = gap_col
            img[min(h - 1, i * board + 1), :] *= 0.8
        else:
            img[:, i * board] = gap_col
            img[:, min(w - 1, i * board + 1)] *= 0.8
    # knots
    for _ in range(knots):
        cx, cy = r.integers(0, w), r.integers(0, h)
        disc(img, cx, cy, 1.6 + r.random(), np.array(base) * 0.45)
    img += grain(w, h, seed + 7, 6)[..., None]
    return img


# ---------------------------------------------------------------- walls
def logs(w, h, seed, base, logh=16, crack=0.5, soot=0.0, caulk=(120, 104, 80)):
    r = rng(seed)
    img = np.zeros((h, w, 3))
    g = wood_grain(w, h, seed, "x", cells=8, streak=20)
    yy = np.arange(h)
    for i in range(h // logh):
        y0 = i * logh
        prof = np.sin(np.pi * (yy[y0:y0 + logh] - y0 + 0.5) / logh)
        prof = 0.30 + 0.75 * prof ** 0.6
        tint = np.array(base) * (1 + (r.random() - 0.5) * 0.25)
        img[y0:y0 + logh] = tint * prof[:, None, None] * (0.75 + 0.45 * g[y0:y0 + logh, :, None])
        # long drying cracks
        if r.random() < crack:
            cy = y0 + r.integers(4, logh - 4)
            x = r.integers(0, w)
            ln = r.integers(w // 4, w)
            for k in range(ln):
                xx = (x + k) % w
                if r.random() < 0.15:
                    cy += r.integers(-1, 2)
                    cy = int(np.clip(cy, y0 + 3, y0 + logh - 4))
                img[cy, xx] *= 0.35
        # caulk (moss/tow) squeezed out in the seam
        seam = y0 + logh - 1
        img[seam] = np.array(caulk) * 0.35
        for x in range(w):
            if r.random() < 0.35:
                c = np.array(caulk) * (0.55 + 0.3 * r.random())
                img[seam - (1 if r.random() < 0.5 else 0), x] = c
            if r.random() < 0.25:
                img[(seam + 1) % h, x] = np.array(caulk) * (0.5 + 0.4 * r.random())
    img = dirt(img, seed + 3, 0.3, 3)
    if soot > 0:
        # soot gathers near the top of the texture (ceiling side)
        f = 1 - soot * np.clip(1 - yy / h, 0, 1) ** 2
        img = mul(img, np.repeat(f[:, None], w, 1))
    img += grain(w, h, seed + 9, 7)[..., None]
    return img


@tex("log_wall")
def t_log_wall():
    return logs(128, 128, 11, (104, 78, 54), crack=0.6, soot=0.25)


@tex("log_wall_old")
def t_log_wall_old():
    # cold rooms: greyer, dry, more cracks
    return logs(128, 128, 12, (98, 88, 74), crack=0.85, soot=0.1,
                caulk=(110, 104, 92))


@tex("log_ext")
def t_log_ext():
    # outside face: weathered silver-grey
    return logs(128, 128, 13, (110, 106, 100), crack=0.9, caulk=(96, 92, 84))


@tex("log_end")
def t_log_end():
    # cut log ends at the corners / firewood
    w = h = 32
    img = solid(w, h, (120, 92, 60))
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot(xx - 15.5 + 1.5 * noise(w, h, 3, 3, 5) , yy - 15.5)
    rings = 0.75 + 0.25 * np.sin(d * 1.9 + 2 * noise(w, h, 4, 4, 6))
    img = mul(img, rings)
    bark = d > 13
    img[bark] = (52, 40, 30)
    img[d > 15.5] = (30, 24, 18)
    # radial cracks
    r = rng(14)
    for a in r.random(3) * 2 * np.pi:
        for k in range(3, 12):
            img[int(15.5 + np.sin(a) * k), int(15.5 + np.cos(a) * k)] *= 0.4
    img += grain(w, h, 15, 6)[..., None]
    return img


@tex("birch_bark")
def t_birch():
    w, h = 32, 32
    r = rng(16)
    img = solid(w, h, (200, 198, 188))
    img = mul(img, 0.85 + 0.15 * noise(w, h, 2, 8, 17))
    for _ in range(14):
        y = r.integers(0, h)
        x = r.integers(0, w)
        ln = r.integers(2, 9)
        for k in range(ln):
            img[y, (x + k) % w] = (34, 30, 28)
            if r.random() < 0.4:
                img[(y + 1) % h, (x + k) % w] = (60, 54, 48)
    img += grain(w, h, 18, 8)[..., None]
    return img


@tex("boards_paint")
def t_boards_paint():
    # partition boards, old pale blue paint worn through to wood
    w, h = 64, 128
    wood = boards(w, h, 16, 21, (110, 84, 58), along="y")
    paint = solid(w, h, (128, 148, 150)) * (0.9 + 0.12 * noise(w, h, 4, 8, 22)[..., None])
    wear = fbm(w, h, 4, 8, 23)
    m = np.clip((wear - 0.62) * 8, 0, 1)
    img = mix(paint, wood, m)
    for x in range(0, w, 16):
        img[:, x] = (30, 30, 30)
        img[:, x + 1] *= 0.82
    img = dirt(img, 24, 0.25, 3)
    img += grain(w, h, 25, 5)[..., None]
    return img


@tex("boards_raw")
def t_boards_raw():
    return dirt(boards(64, 128, 16, 31, (106, 98, 86), along="y", knots=3), 32, 0.3)


@tex("wallpaper")
def t_wallpaper():
    # faded beige paper with a brown diamond-flower motif, water stains
    w = h = 64
    img = solid(w, h, (176, 160, 128))
    img = mul(img, 0.92 + 0.1 * noise(w, h, 4, 4, 41))
    motif = (126, 98, 72)
    for oy in (0, 32):
        for ox in (0, 32):
            cx, cy = ox + 16 + (16 if oy else 0), oy + 16
            cx %= 64
            for k in range(-5, 6):
                for dx, dy in ((k, 5 - abs(k)), (k, -(5 - abs(k)))):
                    img[(cy + dy) % h, (cx + dx) % w] = motif
            disc(img, cx, cy, 1.6, (150, 82, 70))
    # thin vertical stripes
    for x in (0, 1):
        img[:, x] = img[:, x] * 0.86
    stain = fbm(w, h, 3, 3, 42)
    img = mul(img, 1 - 0.22 * np.clip((stain - 0.55) * 4, 0, 1))
    img += grain(w, h, 43, 5)[..., None]
    return img


@tex("wall_carpet")
def t_wall_carpet():
    # the obligatory carpet on the bedroom wall: burgundy field, ornament
    w, h = 64, 64
    img = solid(w, h, (112, 26, 30))
    img = mul(img, 0.85 + 0.2 * noise(w, h, 16, 16, 51))
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = 32, 32
    d = np.abs(xx - cx + 0.5) + np.abs(yy - cy + 0.5)
    img[(d > 18) & (d < 21)] = (176, 140, 72)
    img[(d > 9) & (d < 12)] = (30, 40, 70)
    img[d < 5] = (170, 130, 66)
    # border
    for t, col in ((0, (34, 26, 40)), (3, (176, 140, 72)), (5, (34, 26, 40))):
        frame(img, t, t, w - t, h - t, col, 2 if t == 0 else 1)
    for i in range(6, 58, 6):
        for p in ((i, 2), (2, i), (i, 61), (61, i)):
            img[p[1], p[0]] = (190, 160, 90)
    img += grain(w, h, 52, 10)[..., None]
    img = dirt(img, 53, 0.2)
    return img


@tex("whitewash")
def t_whitewash():
    # lime-washed stove / plaster: uneven, cracked, greyed by soot
    w = h = 64
    r = rng(61)
    n = fbm(w, h, 4, 4, 62, 4)
    img = ramp(n, [(0, (150, 148, 140)), (0.5, (196, 194, 184)), (1, (214, 212, 202))])
    # cracks: a few random walks
    for _ in range(3):
        x, y = r.integers(0, w), r.integers(0, h)
        for _ in range(30):
            img[y % h, x % w] *= 0.6
            x += r.integers(-1, 2)
            y += r.integers(0, 2)
    # exposed clay where whitewash flaked
    m = np.clip((fbm(w, h, 6, 6, 63) - 0.7) * 10, 0, 1)
    img = mix(img, solid(w, h, (150, 108, 80)), m * 0.8)
    img += grain(w, h, 64, 5)[..., None]
    return img


@tex("stove_soot")
def t_stove_soot():
    w = h = 64
    n = fbm(w, h, 4, 4, 71, 4)
    img = ramp(n, [(0, (22, 20, 19)), (0.6, (52, 48, 44)), (1, (96, 90, 82))])
    img += grain(w, h, 72, 6)[..., None]
    return img


@tex("brick_old")
def t_brick():
    # brick exposed in the stove base where plaster fell off
    w, h = 64, 64
    r = rng(81)
    img = solid(w, h, (64, 58, 52))
    for row in range(8):
        off = 8 if row % 2 else 0
        for col in range(-1, 4):
            x0 = col * 16 + off
            c = np.array((132, 68, 48)) * (0.8 + 0.35 * r.random())
            rect(img, x0 + 1, row * 8 + 1, x0 + 16, row * 8 + 8, c)
    img = mul(img, 0.85 + 0.25 * noise(w, h, 8, 8, 82))
    wash = np.clip((fbm(w, h, 4, 4, 83) - 0.45) * 4, 0, 1)
    img = mix(img, solid(w, h, (188, 184, 172)), wash * 0.85)
    img += grain(w, h, 84, 8)[..., None]
    return img


@tex("iron_door")
def t_iron_door():
    w = h = 32
    img = solid(w, h, (44, 42, 40))
    img = mul(img, 0.8 + 0.35 * noise(w, h, 6, 6, 91))
    frame(img, 0, 0, w, h, (24, 22, 21), 2)
    rect(img, 4, 4, 28, 28, (54, 50, 46))
    bevel(img, 4, 4, 28, 28, 1.3, 0.6)
    rect(img, 13, 14, 19, 17, (88, 84, 76))  # latch
    rect(img, 19, 13, 21, 18, (30, 28, 26))
    rust = np.clip((fbm(w, h, 5, 5, 92) - 0.55) * 5, 0, 1)
    img = mix(img, solid(w, h, (96, 54, 30)), rust * 0.6)
    img += grain(w, h, 93, 7)[..., None]
    return img


# ---------------------------------------------------------------- floors, ceiling
@tex("floor_paint")
def t_floor_paint():
    # wide floor boards painted brown-red, worn down to grey wood on paths
    w = h = 128
    wood = boards(w, h, 16, 101, (118, 96, 70), along="x")
    paint = solid(w, h, (112, 50, 34)) * (0.9 + 0.15 * noise(w, h, 4, 16, 102)[..., None])
    wear = fbm(w, h, 3, 3, 103, 4)
    m = np.clip((wear - 0.55) * 4, 0, 1) * 0.85
    img = mix(paint, wood, m)
    for y in range(0, h, 16):
        img[y] = (20, 12, 9)
        img[y + 1] *= 0.85
    r = rng(104)
    for _ in range(18):  # nail heads
        x, y = r.integers(0, w), (r.integers(0, h // 16) * 16 + 8) % h
        img[y, x] = (40, 34, 30)
    img = dirt(img, 105, 0.3, 4)
    img += grain(w, h, 106, 5)[..., None]
    return img


@tex("floor_raw")
def t_floor_raw():
    img = boards(128, 128, 16, 111, (104, 92, 76), along="x", knots=6)
    return dirt(img, 112, 0.4, 4)


@tex("ceiling")
def t_ceiling():
    img = boards(128, 128, 16, 121, (134, 116, 88), along="y", gap_col=(40, 32, 24), knots=3)
    img = dirt(img, 122, 0.35, 3)
    return img


@tex("beam")
def t_beam():
    w = h = 64
    g = wood_grain(w, h, 131, "x", 4, 28)
    img = ramp(g, [(0, (46, 34, 24)), (0.6, (82, 62, 42)), (1, (100, 78, 54))])
    r = rng(132)
    for _ in range(5):
        y = r.integers(0, h)
        x = r.integers(0, w)
        for k in range(r.integers(6, 30)):
            img[y, (x + k) % w] *= 0.45
    img = dirt(img, 133, 0.3)
    img += grain(w, h, 134, 5)[..., None]
    return img


# ---------------------------------------------------------------- furniture
@tex("wood_dark")
def t_wood_dark():
    w = h = 64
    g = wood_grain(w, h, 141, "x", 4, 32)
    img = ramp(g, [(0, (40, 24, 16)), (0.7, (74, 44, 26)), (1, (96, 60, 36))])
    r = rng(142)
    for _ in range(10):  # scratches in the varnish
        x, y = r.integers(0, w), r.integers(0, h)
        for k in range(r.integers(3, 12)):
            yy = (y + k // 3) % h
            img[yy, (x + k) % w] = img[yy, (x + k) % w] * 1.5
    img = dirt(img, 143, 0.2)
    img += grain(w, h, 144, 4)[..., None]
    return img


@tex("wood_light")
def t_wood_light():
    w = h = 64
    g = wood_grain(w, h, 151, "x", 4, 24)
    img = ramp(g, [(0, (110, 84, 52)), (0.6, (150, 118, 76)), (1, (170, 138, 92))])
    img = dirt(img, 152, 0.3)
    img += grain(w, h, 153, 5)[..., None]
    return img


@tex("wood_blue")
def t_wood_blue():
    # kitchen cupboards: old blue-green oil paint, chipped
    w = h = 64
    wood = t_wood_light()
    paint = solid(w, h, (70, 104, 104)) * (0.88 + 0.16 * noise(w, h, 6, 6, 161)[..., None])
    m = np.clip((fbm(w, h, 5, 5, 162) - 0.66) * 7, 0, 1)
    img = mix(paint, wood, m)
    img = dirt(img, 163, 0.25)
    img += grain(w, h, 164, 4)[..., None]
    return img


@tex("wood_white")
def t_wood_white():
    # window frames: white paint, yellowed and peeling
    w = h = 32
    wood = t_wood_dark()[:32, :32] * 1.2
    paint = solid(w, h, (196, 192, 172)) * (0.9 + 0.12 * noise(w, h, 4, 4, 171)[..., None])
    m = np.clip((fbm(w, h, 4, 4, 172) - 0.68) * 8, 0, 1)
    img = mix(paint, wood, m)
    img += grain(w, h, 173, 5)[..., None]
    return img


@tex("door_padded")
def t_door_padded():
    # the warm door: brown leatherette over felt, held by upholstery studs
    w, h = 64, 128
    img = solid(w, h, (88, 52, 36))
    img = mul(img, 0.85 + 0.2 * noise(w, h, 8, 16, 181))
    # quilted diamonds: shade between studs
    yy, xx = np.mgrid[0:h, 0:w]
    u = ((xx + yy) % 16) / 16.0
    v = ((xx - yy) % 16) / 16.0
    q = 0.8 + 0.25 * np.sin(np.pi * u) * np.sin(np.pi * v)
    img = mul(img, q)
    for y in range(0, h, 16):
        for x in range(0, w + 1, 16):
            for sx, sy in ((x, y), (x + 8, y + 8)):
                if 4 <= sx < w - 4 and 4 <= sy < h - 4:
                    img[sy, sx] = (190, 170, 120)
                    img[sy + 1, sx] = (90, 74, 50)
    frame(img, 0, 0, w, h, (40, 26, 18), 2)
    frame(img, 2, 2, w - 2, h - 2, (150, 130, 96), 1)
    # torn corner showing grey felt
    rect(img, 46, 98, 56, 104, (110, 104, 92))
    img += grain(w, h, 182, 5)[..., None]
    return img


@tex("door_boards")
def t_door_boards():
    w, h = 64, 128
    img = boards(w, h, 16, 191, (112, 86, 58), along="y", knots=3)
    # Z brace
    for y0 in (14, 106):
        rect(img, 2, y0, 62, y0 + 8, (92, 70, 48))
        bevel(img, 2, y0, 62, y0 + 8)
    for k in range(0, 92):
        x = int(4 + k * 56 / 92)
        y = 22 + k
        img[y, max(0, x - 3):x + 4] = np.array((92, 70, 48)) * (1.05 if k % 5 else 0.9)
    img = dirt(img, 192, 0.3)
    return img


@tex("door_ext")
def t_door_ext():
    # outer door: heavy grey boards, iron straps
    img = boards(64, 128, 16, 195, (100, 94, 84), along="y", knots=4)
    for y0 in (16, 104):
        rect(img, 0, y0, 48, y0 + 4, (40, 36, 34))
        for x in range(4, 48, 10):
            img[y0 + 2, x] = (90, 86, 80)
    return dirt(img, 196, 0.35)


@tex("handle")
def t_handle():
    w = h = 16
    img = solid(w, h, (60, 56, 50))
    img = mul(img, 0.7 + 0.5 * noise(w, h, 4, 4, 199))
    return img


# ---------------------------------------------------------------- glass, metal
@tex("glass_frost")
def t_glass_frost():
    # winter window: grey-blue daylight with frost ferns climbing from below
    w = h = 64
    r = rng(201)
    yy = np.arange(h)[:, None] / h
    base = ramp(np.repeat(yy, w, 1), [(0, (150, 166, 186)), (1, (196, 206, 216))])
    frost = np.zeros((h, w))
    for _ in range(28):
        x, y = r.random() * w, h - 1 - r.random() * 18
        ang = -np.pi / 2 + (r.random() - 0.5) * 1.6
        for step in range(int(10 + r.random() * 30)):
            xi, yi = int(x) % w, int(y)
            if 0 <= yi < h:
                frost[yi, xi] = 1
                # side branches
                if step % 3 == 0:
                    for s in (-1, 1):
                        bx = int(x + s * 2) % w
                        by = int(y + 1)
                        if 0 <= by < h:
                            frost[by, bx] = max(frost[by, bx], 0.7)
            x += np.cos(ang) * 1.2
            y += np.sin(ang) * 1.2
            ang += (r.random() - 0.5) * 0.5
    haze = np.clip(1 - yy * 1.6, 0, 1) * 0  # (top clear)
    haze = np.clip((yy - 0.45) * 1.4, 0, 1)
    f = np.clip(frost + np.repeat(haze, w, 1) * 0.55 + noise(w, h, 8, 8, 202) * 0.15, 0, 1)
    img = mix(base, solid(w, h, (232, 238, 242)), f)
    return img


@tex("enamel")
def t_enamel():
    w = h = 32
    img = solid(w, h, (206, 206, 196)) * (0.92 + 0.1 * noise(w, h, 4, 4, 211)[..., None])
    r = rng(212)
    for _ in range(5):  # chips
        disc(img, r.integers(0, w), r.integers(0, h), 0.6 + r.random() * 0.9, (44, 42, 46))
    img = dirt(img, 213, 0.2, 2)
    return img


@tex("enamel_blue")
def t_enamel_blue():
    img = t_enamel()
    img = img * np.array((0.5, 0.6, 0.9))
    return img


@tex("metal_rust")
def t_metal_rust():
    w = h = 32
    n = fbm(w, h, 4, 4, 221)
    img = ramp(n, [(0, (60, 40, 30)), (0.5, (110, 64, 36)), (1, (88, 82, 76))])
    img += grain(w, h, 222, 10)[..., None]
    return img


@tex("metal_dark")
def t_metal_dark():
    w = h = 32
    img = solid(w, h, (52, 52, 54)) * (0.8 + 0.3 * noise(w, h, 4, 4, 231)[..., None])
    img += grain(w, h, 232, 6)[..., None]
    return img


@tex("metal_zinc")
def t_metal_zinc():
    # galvanised buckets / wash tub
    w = h = 32
    img = solid(w, h, (138, 140, 138)) * (0.8 + 0.3 * fbm(w, h, 4, 4, 236)[..., None])
    for x in range(0, w, 8):
        img[:, x] *= 0.85
    img += grain(w, h, 237, 6)[..., None]
    return img


# ---------------------------------------------------------------- fabric
@tex("fab_blanket")
def t_fab_blanket():
    w = h = 64
    yy, xx = np.mgrid[0:h, 0:w]
    a = ((xx // 8) % 2) ^ ((yy // 8) % 2)
    img = np.where(a[..., None] == 1, np.array((98, 40, 34)), np.array((70, 46, 36)))
    img = img.astype(float)
    img[(xx % 16 == 0) | (yy % 16 == 0)] = (130, 110, 70)
    img = mul(img, 0.85 + 0.25 * noise(w, h, 32, 32, 241))
    return dirt(img, 242, 0.25)


@tex("fab_patch")
def t_fab_patch():
    # patchwork quilt (лоскутное одеяло)
    w = h = 64
    r = rng(251)
    pal = [(150, 60, 50), (60, 80, 120), (170, 150, 90), (80, 110, 70),
           (160, 140, 130), (110, 60, 90), (190, 180, 160), (90, 70, 50)]
    img = np.zeros((h, w, 3))
    for by in range(4):
        for bx in range(4):
            c = np.array(pal[r.integers(0, len(pal))], float)
            rect(img, bx * 16, by * 16, bx * 16 + 16, by * 16 + 16, c * 0.85)
            if r.random() < 0.5:  # print: dots or stripes
                for k in range(2, 16, 4):
                    if r.random() < 0.5:
                        rect(img, bx * 16 + k, by * 16, bx * 16 + k + 1, by * 16 + 16, c * 1.15)
                    else:
                        rect(img, bx * 16, by * 16 + k, bx * 16 + 16, by * 16 + k + 1, c * 0.7)
            frame(img, bx * 16, by * 16, bx * 16 + 16, by * 16 + 16, c * 0.55)
    img = mul(img, 0.85 + 0.25 * noise(w, h, 32, 32, 252))
    return dirt(img, 253, 0.25)


@tex("fab_pillow")
def t_fab_pillow():
    w = h = 32
    img = solid(w, h, (196, 190, 176)) * (0.85 + 0.2 * noise(w, h, 4, 4, 261)[..., None])
    frame(img, 0, 0, w, h, (160, 150, 130))
    return dirt(img, 262, 0.25, 2)


@tex("fab_rug")
def t_fab_rug():
    # woven rag runner (половик): stripes across, runs along X
    w, h = 64, 64
    r = rng(271)
    pal = [(120, 40, 40), (60, 70, 100), (150, 130, 90), (70, 90, 60),
           (110, 100, 110), (40, 40, 44)]
    img = np.zeros((h, w, 3))
    x = 0
    while x < w:
        sw = int(r.integers(2, 7))
        c = np.array(pal[r.integers(0, len(pal))], float)
        rect(img, x, 0, x + sw, h, c)
        x += sw
    img = mul(img, 0.75 + 0.4 * noise(w, h, 64, 16, 272))
    img = dirt(img, 273, 0.35, 3)
    return img


@tex("fab_curtain")
def t_fab_curtain():
    # faded floral chintz
    w = h = 64
    img = solid(w, h, (176, 166, 140)) * (0.9 + 0.1 * noise(w, h, 4, 4, 281)[..., None])
    r = rng(282)
    for _ in range(9):
        cx, cy = r.integers(0, w), r.integers(0, h)
        disc(img, cx, cy, 3, (160, 80, 70))
        disc(img, cx, cy, 1, (200, 180, 90))
        img[(cy + 4) % h, (cx + 2) % w] = (90, 120, 80)
        img[(cy + 5) % h, (cx + 3) % w] = (90, 120, 80)
    # vertical folds
    xx = np.arange(w)
    fold = 0.82 + 0.18 * np.sin(xx * 2 * np.pi / 16)
    return mul(img, np.repeat(fold[None, :], h, 0))


@tex("fab_coat")
def t_fab_coat():
    w = h = 32
    img = solid(w, h, (54, 54, 58)) * (0.75 + 0.35 * noise(w, h, 16, 16, 291)[..., None])
    return img


@tex("fab_quilted")
def t_fab_quilted():
    # padded work jacket (телогрейка): dark cotton, horizontal quilting
    w = h = 32
    img = solid(w, h, (46, 50, 46)) * (0.8 + 0.3 * noise(w, h, 8, 8, 295)[..., None])
    for y in range(0, h, 8):
        img[y] *= 0.5
        img[y + 1] *= 1.15
    return img


@tex("fab_felt")
def t_fab_felt():
    w = h = 32
    img = solid(w, h, (90, 86, 80)) * (0.8 + 0.3 * noise(w, h, 16, 16, 301)[..., None])
    img += grain(w, h, 302, 10)[..., None]
    return img


@tex("fab_towel")
def t_fab_towel():
    # embroidered towel (рушник): white linen, red cross-stitch band
    w, h = 32, 64
    img = solid(w, h, (206, 200, 186)) * (0.9 + 0.1 * noise(w, h, 4, 8, 311)[..., None])
    for y0 in (44, 52):
        for x in range(0, w, 4):
            for d in range(3):
                img[y0 + d, x + d] = (150, 30, 30)
                img[y0 + 2 - d, x + d] = (150, 30, 30)
    for y in range(58, 64):
        for x in range(0, w, 2):
            img[y, x] = (180, 170, 150)
    return img


@tex("fab_shade")
def t_fab_shade():
    # orange fabric lampshade (абажур)
    w = h = 32
    img = solid(w, h, (200, 112, 40)) * (0.85 + 0.2 * noise(w, h, 8, 4, 321)[..., None])
    for x in range(0, w, 4):
        img[:, x] *= 0.8
    rect(img, 0, h - 4, w, h, (220, 170, 80))  # fringe
    for x in range(0, w, 2):
        img[h - 2:, x] = (120, 70, 30)
    return img


@tex("burlap")
def t_burlap():
    w = h = 32
    yy, xx = np.mgrid[0:h, 0:w]
    weave = 0.85 + 0.15 * (((xx % 2) ^ (yy % 2)))
    img = solid(w, h, (140, 116, 80)) * weave[..., None]
    img = mul(img, 0.8 + 0.3 * noise(w, h, 4, 4, 331))
    return dirt(img, 332, 0.2, 2)


@tex("cardboard")
def t_cardboard():
    w = h = 64
    img = solid(w, h, (150, 118, 80)) * (0.9 + 0.12 * noise(w, h, 4, 4, 341)[..., None])
    rect(img, 0, 30, w, 34, (176, 160, 120))  # tape
    frame(img, 0, 0, w, h, (110, 84, 56))
    rect(img, 8, 8, 28, 20, (60, 50, 44), 0.5)  # stamped marking
    return dirt(img, 342, 0.3)


@tex("paper")
def t_paper():
    # newspaper stack edge / top
    w = h = 32
    img = solid(w, h, (186, 180, 160))
    for y in range(2, h - 2, 3):
        for x in range(2, w - 2):
            if rng(y * 99 + x).random() < 0.6:
                img[y, x] = (110, 106, 100)
    rect(img, 2, 2, 30, 6, (60, 58, 56))  # masthead
    return dirt(img, 351, 0.25, 2)


@tex("books")
def t_books():
    w, h = 64, 32
    r = rng(361)
    img = solid(w, h, (30, 24, 20))
    x = 0
    pal = [(90, 30, 30), (40, 60, 90), (70, 80, 50), (120, 100, 60), (60, 40, 30), (110, 110, 100)]
    while x < w:
        bw = int(r.integers(3, 8))
        bh = int(r.integers(20, 31))
        c = np.array(pal[r.integers(0, len(pal))], float) * (0.8 + 0.4 * r.random())
        rect(img, x, h - bh, x + bw - 1, h, c)
        rect(img, x, h - bh + 3, x + bw - 1, h - bh + 4, (170, 150, 90))
        if x + bw - 2 < w:
            img[h - bh:, x + bw - 2] *= 0.7
        x += bw
    return img


@tex("jars")
def t_jars():
    # shelf full of preserves: pickles, jam, sauerkraut
    w, h = 64, 32
    r = rng(371)
    img = solid(w, h, (34, 28, 22))
    x = 1
    fills = [(70, 96, 40), (120, 30, 36), (170, 150, 90), (150, 70, 30), (90, 110, 60)]
    while x < w - 8:
        jw = int(r.integers(9, 13))
        jh = int(r.integers(18, 28))
        c = np.array(fills[r.integers(0, len(fills))], float)
        rect(img, x, h - jh, x + jw, h, c * 0.8)
        rect(img, x + 1, h - jh + 3, x + 3, h - 2, (200, 210, 200), 0.35)  # glint
        rect(img, x + 1, h - jh - 3, x + jw - 1, h - jh, (150, 150, 140))  # lid
        x += jw + 2
    return img


@tex("crockery")
def t_crockery():
    # plates and cups seen on an open shelf
    w, h = 64, 32
    img = solid(w, h, (40, 32, 24))
    for i, cx in enumerate(range(8, 64, 16)):
        disc(img, cx, 16, 7, (200, 196, 186))
        disc(img, cx, 16, 5, (180, 176, 168))
        disc(img, cx, 16, 6.2, (60, 90, 140), 0.0)
        img[16 - 7:16 + 7, cx - 1] *= 0.95
    for cx in range(4, 64, 16):
        rect(img, cx, 24, cx + 6, 31, (196, 60, 50) if cx % 32 else (210, 205, 190))
    return img


# ---------------------------------------------------------------- appliances, decor
@tex("tv_front")
def t_tv_front():
    # old CRT set: veneer cabinet, curved dark screen, knobs on the right
    w = h = 64
    img = t_wood_dark()
    rect(img, 4, 6, 46, 50, (26, 28, 28))
    yy, xx = np.mgrid[0:h, 0:w]
    scr = (xx >= 6) & (xx < 44) & (yy >= 8) & (yy < 48)
    d = np.hypot((xx - 25) / 22, (yy - 28) / 22)
    img[scr] = (np.array((50, 58, 56)) * (1.1 - 0.5 * d[scr, None]))
    rect(img, 10, 11, 18, 13, (110, 120, 120), 0.6)  # reflection
    rect(img, 48, 6, 60, 58, (120, 116, 106))
    for cy in (14, 26):
        disc(img, 54, cy, 3.5, (30, 28, 26))
        disc(img, 54, cy, 1.5, (90, 86, 80))
    for y in range(36, 56, 2):
        rect(img, 49, y, 59, y + 1, (60, 58, 52))
    rect(img, 4, 54, 46, 58, (150, 140, 110))  # name plate strip
    return img


@tex("radio_front")
def t_radio_front():
    w, h = 64, 32
    img = solid(w, h, (92, 60, 36)) * (0.9 + 0.15 * noise(w, h, 8, 4, 401)[..., None])
    rect(img, 3, 3, 30, 29, (70, 62, 50))
    for y in range(4, 29, 2):
        img[y, 3:30] *= 0.7  # speaker cloth
    rect(img, 33, 4, 61, 14, (200, 184, 130))  # tuning scale
    for x in range(35, 60, 3):
        img[6:9, x] = (60, 50, 40)
    img[4:14, 47] = (170, 30, 20)  # needle
    for cx in (39, 55):
        disc(img, cx, 23, 4, (40, 30, 24))
        disc(img, cx, 23, 1.5, (160, 150, 120))
    return img


@tex("phone_top")
def t_phone_top():
    # rotary telephone seen from above: ivory body, dial
    w = h = 32
    img = solid(w, h, (176, 166, 140)) * (0.9 + 0.12 * noise(w, h, 4, 4, 411)[..., None])
    disc(img, 16, 18, 10, (40, 40, 40))
    disc(img, 16, 18, 8.5, (170, 162, 140))
    for k in range(10):
        a = -0.6 + k * 0.5
        disc(img, 16 + np.cos(a) * 6.5, 18 + np.sin(a) * 6.5, 1.4, (30, 30, 30))
    disc(img, 16, 18, 3, (200, 196, 180))
    return img


@tex("phone_side")
def t_phone_side():
    w = h = 16
    img = solid(w, h, (160, 150, 126)) * (0.85 + 0.2 * noise(w, h, 4, 4, 415)[..., None])
    return img


@tex("clock_face")
def t_clock_face():
    w = h = 32
    img = t_wood_dark()[:32, :32]
    disc(img, 16, 16, 13, (200, 190, 160))
    for k in range(12):
        a = k * np.pi / 6
        img[int(16 + np.sin(a) * 11), int(16 + np.cos(a) * 11)] = (30, 26, 22)
    for k in range(9):  # hour hand ~ 4 o'clock (overcast afternoon)
        img[int(16 + k * 0.45), int(16 + k * 0.75)] = (20, 18, 16)
    for k in range(11):  # minute hand ~ :40
        img[int(16 + k * 0.85), int(16 - k * 0.5)] = (20, 18, 16)
    return img


@tex("calendar")
def t_calendar():
    # tear-off style wall calendar: winter picture + month grid (Jan 2000)
    w, h = 32, 48
    img = solid(w, h, (210, 204, 190))
    sky = ramp(np.repeat(np.linspace(0, 1, 18)[:, None], 28, 1),
               [(0, (120, 140, 170)), (1, (200, 206, 214))])
    img[2:20, 2:30] = sky
    for x in range(2, 30):  # trees silhouette
        th = int(4 + 3 * abs(np.sin(x * 1.7)))
        img[20 - th:20, x] = (40, 56, 50)
    img[2:6, 2:30] = (160, 40, 40)  # red header strip
    for row in range(5):
        for col in range(7):
            x, y = 3 + col * 4, 23 + row * 5
            img[y:y + 2, x:x + 2] = (40, 40, 40) if col < 6 else (170, 30, 30)
    img[43:45, 3 + 3 * 4:3 + 3 * 4 + 2] = (30, 30, 160)  # circled date
    return dirt(img, 421, 0.2, 2)


@tex("photos")
def t_photos():
    # glazed frame with a collage of old family photos
    w, h = 64, 48
    r = rng(431)
    img = t_wood_dark()[:48, :64]
    rect(img, 3, 3, 61, 45, (40, 40, 38))
    spots = [(5, 5, 20, 22), (23, 5, 40, 20), (43, 5, 59, 24), (5, 25, 18, 43),
             (21, 23, 36, 43), (39, 27, 59, 43)]
    for (x0, y0, x1, y1) in spots:
        sep = np.array((150, 130, 100)) if r.random() < 0.6 else np.array((150, 150, 146))
        rect(img, x0, y0, x1, y1, (200, 194, 180))
        rect(img, x0 + 1, y0 + 1, x1 - 1, y1 - 1, sep * 0.7)
        # one or two blurry figures
        for k in range(r.integers(1, 3)):
            cx = x0 + (x1 - x0) * (0.35 + 0.3 * k)
            disc(img, cx, y0 + (y1 - y0) * 0.38, 2.2, sep * 1.1)
            rect(img, cx - 3, y0 + (y1 - y0) * 0.5, cx + 3, y1 - 1, sep * 0.4)
    rect(img, 6, 6, 30, 8, (230, 230, 230), 0.25)  # glass glare
    return img


@tex("icon")
def t_icon():
    # small dark icon in the corner shelf (красный угол)
    w = h = 32
    img = solid(w, h, (60, 40, 20))
    rect(img, 2, 2, 30, 30, (140, 106, 50))
    rect(img, 4, 4, 28, 28, (70, 50, 30))
    disc(img, 16, 11, 5, (170, 130, 60))
    disc(img, 16, 11, 3, (120, 84, 60))
    rect(img, 11, 15, 21, 28, (60, 30, 30))
    rect(img, 15, 16, 17, 27, (130, 96, 50))
    return dirt(img, 441, 0.35, 2)


@tex("switch")
def t_switch():
    # bakelite rotary light switch on a round plate
    w = h = 16
    img = solid(w, h, (110, 70, 40))
    disc(img, 8, 8, 7, (150, 104, 60))
    disc(img, 8, 8, 4, (60, 36, 20))
    rect(img, 7, 3, 9, 13, (90, 56, 30))
    return img


@tex("bulb")
def t_bulb():
    w = h = 16
    img = solid(w, h, (255, 236, 190))
    disc(img, 8, 8, 4, (255, 255, 240))
    return img


@tex("stove_tile")
def t_stove_tile():
    # cast-iron cooking plate with rings on the stove's cooking ledge
    w = h = 32
    img = t_metal_dark()
    disc(img, 16, 16, 12, (36, 34, 32))
    disc(img, 16, 16, 9, (58, 56, 52))
    disc(img, 16, 16, 6, (36, 34, 32))
    disc(img, 16, 16, 3, (58, 56, 52))
    return img


@tex("snow")
def t_snow():
    w = h = 128
    n = fbm(w, h, 4, 4, 451, 5)
    img = ramp(n, [(0, (150, 156, 164)), (0.6, (196, 200, 206)), (1, (214, 218, 222))])
    r = rng(452)
    for _ in range(14):  # footprints / ruts
        x, y = r.integers(0, w), r.integers(0, h)
        rect(img, x, y, x + 3, y + 6, (150, 154, 160))
    img += grain(w, h, 453, 4)[..., None]
    return img


@tex("sky")
def t_sky():
    return solid(16, 16, (120, 130, 150))


# ---------------------------------------------------------------- skybox
def skybox():
    """Six 256x256 faces of a flat overcast winter day.

    Engine face mapping (verified in Xash3D ref code):
      rt=+X east (field), bk=-X west, lf=+Y north (forest), ft=-Y south (road)
    The silhouettes keep the agreed geography readable from the windows.
    """
    S = 256
    r = rng(901)
    os.makedirs(SKY_OUT, exist_ok=True)

    def base(horizon):
        y = np.arange(S)[:, None] / S
        t = np.repeat(y, S, 1)
        sky = ramp(t / horizon, [(0, (112, 118, 128)), (1, (176, 180, 186))])
        ground = ramp((t - horizon) / (1 - horizon), [(0, (186, 190, 196)), (1, (150, 154, 160))])
        img = np.where(t[..., None] < horizon, sky, ground)
        cloud = fbm(S, S, 3, 6, int(r.integers(0, 9999)), 4)
        img = img * (0.93 + 0.12 * cloud[..., None])
        return img

    def treeline(img, hz, hmin, hmax, dens, col, spruce=0.7, seed=0):
        rr = rng(seed)
        x = 0
        while x < S:
            th = int(rr.integers(hmin, hmax))
            tw = max(2, th // 4 + int(rr.integers(0, 3)))
            is_spruce = rr.random() < spruce
            for k in range(-tw, tw + 1):
                if 0 <= x + k < S:
                    if is_spruce:
                        # layered spruce: triangle with ragged tiers
                        hh = int(th * (1 - abs(k) / (tw + 1)))
                        hh -= int((abs(k) * 3 + x) % 4) if abs(k) > 1 else 0
                    else:
                        hh = int(th * 0.85 * (1 - (abs(k) / (tw + 1)) ** 3))
                    top = hz - hh
                    if is_spruce:
                        img[max(0, top):hz, x + k] = col
                    else:  # bare crowns: a see-through grey-brown haze
                        img[max(0, top):hz, x + k] = (img[max(0, top):hz, x + k] * 0.62
                                                      + np.array((96, 90, 86)) * 0.38)
            if not is_spruce:  # bare birch/aspen trunk
                img[hz - th:hz, x] = (150, 148, 140)
            x += int(rr.integers(max(2, tw // 2), max(3, tw // 2 + dens)))
        img[hz:hz + 2, :] = np.array(col) * 1.1

    faces = {}
    # north: forest right behind the house
    f = base(0.62)
    treeline(f, int(S * 0.62), 30, 70, 5, (52, 58, 58), seed=11)
    treeline(f, int(S * 0.64), 40, 90, 4, (40, 46, 46), seed=12)
    faces["lf"] = f
    # east: open snowy field sloping away, distant thin forest
    f = base(0.6)
    treeline(f, int(S * 0.6), 6, 16, 4, (96, 102, 106), seed=21)
    for _ in range(9):  # dry grass and shrubs in the field
        x, y = r.integers(0, S), r.integers(int(S * 0.63), S - 20)
        for k in range(int(r.integers(3, 8))):
            f[y - k:y, (x + k % 3) % S] = (96, 88, 74)
    faces["rt"] = f
    # south: the road goes downhill to the village - roofs, smoke, poles
    f = base(0.6)
    hz = int(S * 0.6)
    treeline(f, hz, 4, 10, 6, (100, 106, 110), seed=31)
    for x0 in (30, 70, 96, 150, 196):
        rw, rh = int(r.integers(14, 22)), int(r.integers(6, 10))
        for k in range(rw):
            rh_k = int(rh * (1 - abs(k - rw / 2) / (rw / 2)) * 0.6) + rh // 2
            f[hz - rh_k:hz, x0 + k] = (82, 80, 80)
        f[hz - rh - 6:hz - rh, x0 + rw // 3] = (70, 66, 64)  # chimney
    for x0 in (20, 120, 220):  # power poles + sagging wire
        f[hz - 34:hz + 6, x0] = (60, 56, 52)
        f[hz - 34, x0 - 3:x0 + 4] = (60, 56, 52)
    for x in range(20, 220):
        seg = 100 if x < 120 else 100
        t = ((x - 20) % seg) / seg
        y = hz - 33 + int(8 * 4 * t * (1 - t))
        f[y, x] = (76, 72, 70)
    # road ruts going down to the village
    for y in range(hz + 2, S):
        k = (y - hz) / (S - hz)
        cx = int(S * 0.55 + 10 * np.sin(k * 3))
        half = int(4 + 50 * k)
        f[y, max(0, cx - half):cx - half + 3] = (140, 136, 130)
        f[y, cx + half - 3:min(S, cx + half)] = (140, 136, 130)
    faces["ft"] = f
    # west: mixed forest at medium distance
    f = base(0.61)
    treeline(f, int(S * 0.61), 18, 44, 5, (66, 72, 72), spruce=0.5, seed=41)
    faces["bk"] = f
    # up / down
    f = ramp(fbm(S, S, 4, 4, 51, 4), [(0, (104, 110, 120)), (1, (138, 142, 150))])
    faces["up"] = f
    faces["dn"] = solid(S, S, (150, 154, 160)) * (0.9 + 0.1 * noise(S, S, 8, 8, 52)[..., None])
    for k, img in faces.items():
        to_pil(img).save(os.path.join(SKY_OUT, "btt_overcast%s.tga" % k))
    return list(faces)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in TEX.items():
        img = fn()
        h, w = img.shape[:2]
        assert w % 16 == 0 and h % 16 == 0, name
        to_pil(img).save(os.path.join(OUT, name + ".png"))
    sky = skybox()
    print("textures: %d -> %s" % (len(TEX), OUT))
    print("skybox faces: %s -> %s" % (", ".join(sky), SKY_OUT))


if __name__ == "__main__":
    main()
