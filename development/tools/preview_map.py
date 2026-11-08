#!/usr/bin/env python3
"""Quick software preview of a .map without compiling it.

Rasterises brush faces with their real textures (Valve 220 projection,
nearest-neighbour like the game) and a crude light model (no shadows, no
radiosity - the real lighting comes from RAD).  Useful to check layout,
texture alignment and composition before the compile tools are set up.

  python3 preview_map.py <map> <out.png> --eye X Y Z --look YAW PITCH [--fov 90]
  python3 preview_map.py <map> <out.png> --cutaway     (isometric, roof removed)
"""
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import check_map

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEXDIR = os.path.join(ROOT, "development", "textures_src", "house")
SKIP_TEX = {"null", "origin", "clip", "skip", "hint", "sky"}


def parse_full(path):
    """Like check_map.parse but keeps texture axes."""
    import re
    txt = re.sub(r"//[^\n]*", "", open(path).read())
    tokens = re.findall(r'"[^"]*"|[{}()\[\]]|[^\s{}()\[\]"]+', txt)
    pos = 0
    ents = []
    while pos < len(tokens):
        pos += 1
        kv, brushes = {}, []
        while True:
            t = tokens[pos]; pos += 1
            if t == "}":
                break
            if t.startswith('"'):
                kv[t[1:-1]] = tokens[pos][1:-1]; pos += 1
            elif t == "{":
                faces = []
                while tokens[pos] != "}":
                    pts = []
                    for _ in range(3):
                        pts.append(tuple(float(tokens[pos + 1 + i]) for i in range(3)))
                        pos += 5
                    tex = tokens[pos]; pos += 1
                    vals = []
                    while len(vals) < 11:
                        t = tokens[pos]; pos += 1
                        if t not in ("[", "]"):
                            vals.append(float(t))
                    faces.append((pts, tex, vals))
                pos += 1
                brushes.append(faces)
        ents.append((kv, brushes))
    return ents


TEXCACHE = {}


def texture(name):
    if name not in TEXCACHE:
        p = os.path.join(TEXDIR, name + ".png")
        TEXCACHE[name] = np.asarray(Image.open(p).convert("RGB"), float) if os.path.exists(p) else \
            np.full((16, 16, 3), 200.0)
    return TEXCACHE[name]


def collect(ents, cutaway_bounds=None):
    polys = []
    lights = []
    for kv, brushes in ents:
        cls = kv.get("classname")
        if cls == "light":
            o = np.array([float(v) for v in kv["origin"].split()])
            r, g, b, br = (float(v) for v in kv["_light"].split())
            on = kv.get("spawnflags", "0") != "1"
            if on:
                lights.append((o, np.array([r, g, b]) / 255.0, br))
        for faces in brushes:
            pl = check_map.planes_of([(f[0], f[1]) for f in faces])
            vs = np.array(check_map.brush_verts(pl))
            lo, hi = vs.min(0), vs.max(0)
            if cutaway_bounds and not cutaway_bounds(cls, lo, hi):
                continue
            for (n, d, tex), f in zip(pl, faces):
                if tex.lower() in SKIP_TEX:
                    continue
                fv = [v for v in vs if abs(np.dot(n, v) - d) < 0.01]
                if len(fv) < 3:
                    continue
                c = np.mean(fv, 0)
                u = np.cross(n, [0, 0, 1]) if abs(n[2]) < 0.9 else np.array([1.0, 0, 0])
                u /= np.linalg.norm(u)
                w = np.cross(n, u)
                fv = sorted(fv, key=lambda v: math.atan2(np.dot(v - c, w), np.dot(v - c, u)))
                vals = f[2]
                alpha = 0.55 if cls == "func_wall" else 1.0
                polys.append(dict(v=np.array(fv), n=n, tex=tex, U=np.array(vals[0:3]), ou=vals[3],
                                  V=np.array(vals[4:7]), ov=vals[7], su=vals[9], sv=vals[10],
                                  alpha=alpha))
    return polys, lights


def shade(P, N, lights, outdoor):
    """Very rough lighting: ambient + unshadowed point lights."""
    col = np.zeros(P.shape) + np.array([0.20, 0.21, 0.24])
    for o, c, br in lights:
        d = o[None, :] - P
        dist = np.linalg.norm(d, axis=1, keepdims=True) + 1e-3
        lam = np.clip(np.sum(d / dist * N, axis=1, keepdims=True), 0, 1) * 0.8 + 0.2
        col += c[None, :] * lam * (br * 55.0) / (dist ** 1.25 + 40)
    if outdoor is not None:
        col = np.where(outdoor[:, None], np.array([0.85, 0.88, 0.95]), col)
    return np.clip(col, 0, 1.6)


def render(polys, lights, W, H, project, sky_col=(170, 175, 182), outdoor_fn=None):
    zb = np.full((H, W), np.inf)
    img = np.zeros((H, W, 3)) + np.array(sky_col, float)
    order = sorted(range(len(polys)), key=lambda i: polys[i]["alpha"] < 1)  # opaque first
    for i in order:
        p = polys[i]
        sp, depth, ok = project(p["v"])
        if not ok:
            continue
        for k in range(1, len(sp) - 1):
            tri = np.array([sp[0], sp[k], sp[k + 1]])
            dz = np.array([depth[0], depth[k], depth[k + 1]])
            tv = np.array([p["v"][0], p["v"][k], p["v"][k + 1]])
            x0, y0 = np.floor(tri.min(0)).astype(int)
            x1, y1 = np.ceil(tri.max(0)).astype(int)
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W - 1), min(y1, H - 1)
            if x1 < x0 or y1 < y0:
                continue
            X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            a, b, c = tri
            den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(den) < 1e-9:
                continue
            l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / den
            l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / den
            l3 = 1 - l1 - l2
            m = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
            # perspective-correct interpolation (depth = view distance)
            iz = l1 / dz[0] + l2 / dz[1] + l3 / dz[2]
            z = 1 / np.maximum(iz, 1e-9)
            sub = zb[y0:y1 + 1, x0:x1 + 1]
            upd = m & (z < sub - 0.01)
            if not upd.any():
                continue
            w1, w2, w3 = (l1 / dz[0] * z)[upd], (l2 / dz[1] * z)[upd], (l3 / dz[2] * z)[upd]
            P = w1[:, None] * tv[0] + w2[:, None] * tv[1] + w3[:, None] * tv[2]
            tex = texture(p["tex"])
            th, tw = tex.shape[:2]
            s = (P @ p["U"]) / p["su"] + p["ou"]
            t = (P @ p["V"]) / p["sv"] + p["ov"]
            texel = tex[np.floor(t).astype(int) % th, np.floor(s).astype(int) % tw]
            N = np.repeat(p["n"][None, :], len(P), 0)
            lit = shade(P, N, lights, outdoor_fn(P) if outdoor_fn else None)
            col = texel * lit
            reg = img[y0:y1 + 1, x0:x1 + 1]
            if p["alpha"] < 1:
                reg[upd] = reg[upd] * (1 - p["alpha"]) + col * p["alpha"]
            else:
                reg[upd] = col
                sub[upd] = z[upd]
    return np.clip(img, 0, 255).astype(np.uint8)


def main():
    a = sys.argv[1:]
    mp, out = a[0], a[1]
    ents = parse_full(mp)
    outdoor = lambda P: (P[:, 0] < -17) | (P[:, 1] < -17) | (P[:, 0] > 337) | (P[:, 1] > 289)
    if "--cutaway" in a:
        def keep(cls, lo, hi):
            if lo[2] >= 95:
                return False
            if lo[0] < -20 or lo[1] < -20 or hi[0] > 340 or hi[1] > 292:
                return False
            return not (cls == "worldspawn" and (lo[1] >= 272 or lo[0] >= 320))
        polys, lights = collect(ents, keep)
        lights.append((np.array([160.0, 136, 300]), np.array([1.0, 1, 1]), 120))
        W, H = 1400, 900

        def project(vs):
            sp = np.stack([560 + (vs[:, 0] - vs[:, 1] * 1.3) * 2.0,
                           150 + (vs[:, 0] * 0.5 + vs[:, 1] * 0.38) * 2.0 - vs[:, 2] * 2.1], 1)
            depth = 4000 - (vs[:, 0] * 0.5 + vs[:, 1] * 0.38 + vs[:, 2] * 1.0)
            return sp, depth, True
        img = render(polys, lights, W, H, project, (235, 235, 230))
    else:
        eye = np.array([float(v) for v in a[a.index("--eye") + 1:a.index("--eye") + 4]])
        yaw, pitch = (math.radians(float(v)) for v in a[a.index("--look") + 1:a.index("--look") + 3])
        fov = math.radians(float(a[a.index("--fov") + 1])) if "--fov" in a else math.radians(90)
        polys, lights = collect(ents, lambda cls, lo, hi: not (lo[0] < -40 and hi[0] > 600))
        W, H = 960, 600
        fwd = np.array([math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)])
        right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        f = (W / 2) / math.tan(fov / 2)

        def project(vs):
            d = vs - eye
            x, y, z = d @ right, d @ up, d @ fwd
            if np.all(z < 1):
                return None, None, False
            if np.any(z < 1):
                return None, None, False   # (no clipping: skip faces crossing the eye plane)
            sp = np.stack([W / 2 + x / z * f, H / 2 - y / z * f], 1)
            return sp, z, True
        # split big faces so fewer get culled by the near plane
        polys = subdivide(polys, 32)
        img = render(polys, lights, W, H, project, outdoor_fn=outdoor)
    Image.fromarray(img).save(out)
    print(out)


def subdivide(polys, step):
    """Split faces into a grid of quads (in their own plane) of ~step units."""
    out = []
    for p in polys:
        v = p["v"]
        n = p["n"]
        u = np.cross(n, [0, 0, 1]) if abs(n[2]) < 0.9 else np.array([1.0, 0, 0])
        u /= np.linalg.norm(u)
        w = np.cross(n, u)
        c = v.mean(0)
        uu, ww = (v - c) @ u, (v - c) @ w
        if len(v) != 4 or (np.ptp(uu) <= step and np.ptp(ww) <= step):
            out.append(p)
            continue
        nu = max(1, int(math.ceil(np.ptp(uu) / step)))
        nw = max(1, int(math.ceil(np.ptp(ww) / step)))
        # only exact rectangles are split; others are kept whole
        corners = sorted(zip(uu, ww))
        if len(set(np.round(uu, 3))) != 2 or len(set(np.round(ww, 3))) != 2:
            out.append(p)
            continue
        u0, u1, w0, w1 = uu.min(), uu.max(), ww.min(), ww.max()
        for i in range(nu):
            for j in range(nw):
                a0, a1 = u0 + (u1 - u0) * i / nu, u0 + (u1 - u0) * (i + 1) / nu
                b0, b1 = w0 + (w1 - w0) * j / nw, w0 + (w1 - w0) * (j + 1) / nw
                q = dict(p)
                q["v"] = np.array([c + u * a0 + w * b0, c + u * a1 + w * b0,
                                   c + u * a1 + w * b1, c + u * a0 + w * b1])
                out.append(q)
    return out


if __name__ == "__main__":
    main()
