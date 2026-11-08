#!/usr/bin/env python3
"""Sanity checks for a GoldSrc .map (Valve 220) before handing it to the compiler.

Independent from the generator: it parses the .map text itself.

  * every brush is a valid closed convex solid (no degenerate planes)
  * every texture used exists in the WAD (tool textures excepted)
  * leak test: flood fill from info_player_start through empty space of the
    world (world + func_detail brushes); reaching the grid border = leak
  * point entities are not buried in solid geometry
  * optional --plan out.png : top-down plan render for a quick look

Usage: python3 check_map.py <map> [--wad file.wad] [--plan plan.png]
"""
import itertools
import re
import struct
import sys

import numpy as np

TOOL_TEX = {"null", "origin", "clip", "skip", "hint", "aaatrigger", "sky", "bevel"}
SOLID_CLASSES = {"worldspawn", "func_detail"}
EPS = 0.01


def parse(path):
    txt = open(path).read()
    txt = re.sub(r"//[^\n]*", "", txt)
    ents, i = [], 0
    tokens = re.findall(r'"[^"]*"|[{}()\[\]]|[^\s{}()\[\]"]+', txt)
    pos = 0

    def nxt():
        nonlocal pos
        t = tokens[pos]
        pos += 1
        return t

    while pos < len(tokens):
        assert nxt() == "{"
        kv, brushes = {}, []
        while True:
            t = nxt()
            if t == "}":
                break
            if t.startswith('"'):
                kv[t[1:-1]] = nxt()[1:-1]
            elif t == "{":
                faces = []
                while True:
                    t = nxt()
                    if t == "}":
                        break
                    pts = []
                    for _ in range(3):
                        assert t == "("
                        p = tuple(float(nxt()) for _ in range(3))
                        assert nxt() == ")"
                        pts.append(p)
                        t = nxt()
                    tex = t
                    # [ ux uy uz ou ] [ vx vy vz ov ] rot sx sy
                    vals = []
                    while len(vals) < 11:
                        t = nxt()
                        if t not in "[]":
                            vals.append(float(t))
                    faces.append((pts, tex))
                brushes.append(faces)
        ents.append((kv, brushes))
    return ents


def planes_of(faces):
    out = []
    for (p0, p1, p2), tex in faces:
        p0, p1, p2 = map(np.array, (p0, p1, p2))
        n = np.cross(p0 - p1, p2 - p1)
        ln = np.linalg.norm(n)
        if ln < 1e-9:
            raise ValueError("degenerate plane")
        n = n / ln
        out.append((n, float(np.dot(n, p1)), tex))
    return out


def brush_verts(planes):
    verts = []
    for a, b, c in itertools.combinations(planes, 3):
        m = np.array([a[0], b[0], c[0]])
        if abs(np.linalg.det(m)) < 1e-9:
            continue
        p = np.linalg.solve(m, np.array([a[1], b[1], c[1]]))
        if all(np.dot(n, p) - d <= EPS for n, d, _ in planes):
            verts.append(p)
    return verts


def wad_names(path):
    data = open(path, "rb").read()
    _, n, ofs = struct.unpack_from("<4sii", data, 0)
    return {data[ofs + 32 * i + 16:ofs + 32 * i + 32].split(b"\0")[0].decode().lower()
            for i in range(n)}


def main():
    args = sys.argv[1:]
    path = args[0]
    wad = args[args.index("--wad") + 1] if "--wad" in args else None
    plan = args[args.index("--plan") + 1] if "--plan" in args else None
    ents = parse(path)
    errors, warns = [], []
    names = wad_names(wad) if wad else None
    solids = []   # (planes, bounds, classname)
    all_brushes = []
    for ei, (kv, brushes) in enumerate(ents):
        cls = kv.get("classname", "?")
        for bi, faces in enumerate(brushes):
            try:
                pl = planes_of(faces)
            except ValueError as e:
                errors.append("ent %d (%s) brush %d: %s" % (ei, cls, bi, e))
                continue
            vs = brush_verts(pl)
            if len(vs) < 4:
                errors.append("ent %d (%s) brush %d: not a closed solid" % (ei, cls, bi))
                continue
            vs = np.array(vs)
            lo, hi = vs.min(0), vs.max(0)
            if np.any(hi - lo < 0.99):
                errors.append("ent %d (%s) brush %d: thinner than 1 unit" % (ei, cls, bi))
            # every plane must touch the solid (no redundant/inverted planes)
            for n, d, tex in pl:
                if not np.any(np.abs(vs @ n - d) < EPS):
                    errors.append("ent %d (%s) brush %d: plane does not touch brush (%s)"
                                  % (ei, cls, bi, tex))
                if names is not None and tex.lower() not in TOOL_TEX and tex.lower() not in names:
                    errors.append("ent %d brush %d: texture '%s' not in wad" % (ei, bi, tex))
            all_brushes.append((pl, lo, hi, cls, kv))
            if cls in SOLID_CLASSES:
                solids.append((pl, lo, hi))
    # ---- leak test on a voxel grid
    G = 4
    lo = np.min([b[1] for b in solids], 0) - G
    hi = np.max([b[2] for b in solids], 0) + G
    dims = np.ceil((hi - lo) / G).astype(int)
    solid = np.zeros(dims, bool)
    cx = lo[0] + (np.arange(dims[0]) + 0.5) * G
    cy = lo[1] + (np.arange(dims[1]) + 0.5) * G
    cz = lo[2] + (np.arange(dims[2]) + 0.5) * G
    for pl, blo, bhi in solids:
        ix = np.where((cx > blo[0]) & (cx < bhi[0]))[0]
        iy = np.where((cy > blo[1]) & (cy < bhi[1]))[0]
        iz = np.where((cz > blo[2]) & (cz < bhi[2]))[0]
        if not len(ix) or not len(iy) or not len(iz):
            continue
        X, Y, Z = np.meshgrid(cx[ix], cy[iy], cz[iz], indexing="ij")
        inside = np.ones(X.shape, bool)
        for n, d, _ in pl:
            inside &= (X * n[0] + Y * n[1] + Z * n[2] - d) < 0
        sub = solid[ix[0]:ix[-1] + 1, iy[0]:iy[-1] + 1, iz[0]:iz[-1] + 1]
        sub |= inside

    def cell(p):
        return tuple(((np.array(p) - lo) / G).astype(int))

    start = [kv for kv, _ in ents if kv.get("classname") == "info_player_start"]
    if not start:
        errors.append("no info_player_start")
    else:
        org = [float(v) for v in start[0]["origin"].split()]
        c0 = cell(org)
        if solid[c0]:
            errors.append("info_player_start is inside solid")
        else:
            from collections import deque
            seen = np.zeros(dims, bool)
            seen[c0] = True
            q = deque([c0])
            leak = None
            while q:
                c = q.popleft()
                for dd in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                    n = (c[0] + dd[0], c[1] + dd[1], c[2] + dd[2])
                    if min(n) < 0 or n[0] >= dims[0] or n[1] >= dims[1] or n[2] >= dims[2]:
                        leak = c
                        q.clear()
                        break
                    if not seen[n] and not solid[n]:
                        seen[n] = True
                        q.append(n)
            if leak:
                errors.append("LEAK near %s" % (lo + np.array(leak) * G))
            else:
                print("leak test: sealed (%d empty cells reachable)" % seen.sum())
        # hull test: player standing box at start must be free of world solids
        p = np.array(org)
        pmin, pmax = p + (-16, -16, -36), p + (16, 16, 36)
        for pl, blo, bhi in solids:
            if np.all(blo < pmax) and np.all(bhi > pmin):
                corners = np.array(list(itertools.product(*zip(pmin + 0.5, pmax - 0.5))))
                if any(all(np.dot(n, c) - d < 0 for n, d, _ in pl) for c in corners):
                    errors.append("player start overlaps solid brush at %s..%s" % (blo, bhi))
    for kv, br in ents:
        if "origin" in kv and not br and kv["classname"] not in ("info_player_start",):
            o = np.array([float(v) for v in kv["origin"].split()])
            if solid[cell(o)]:
                warns.append("%s at %s is inside solid" % (kv["classname"], o))
    ncls = {}
    for kv, _ in ents:
        ncls[kv.get("classname")] = ncls.get(kv.get("classname"), 0) + 1
    print("entities:", ", ".join("%s x%d" % kv for kv in sorted(ncls.items())))
    print("brushes: %d" % len(all_brushes))
    if plan:
        render_plan(all_brushes, ents, plan)
    for w in warns:
        print("WARNING:", w)
    for e in errors:
        print("ERROR:", e)
    if errors:
        sys.exit(1)
    print("OK")


def render_plan(brushes, ents, out):
    from PIL import Image, ImageDraw
    S = 2
    x0, y0, x1, y1 = -40, -40, 580, 400
    img = Image.new("RGB", ((x1 - x0) * S, (y1 - y0) * S), (250, 250, 246))
    dr = ImageDraw.Draw(img)

    def P(x, y):
        return ((x - x0) * S, (y1 - y) * S)

    order = sorted(brushes, key=lambda b: b[2][2])
    for pl, lo, hi, cls, kv in order:
        if hi[2] < -30 and cls == "worldspawn":
            continue
        if lo[2] > 95 and cls == "worldspawn":
            continue
        if any(t.lower() in ("sky", "origin") for _, _, t in pl):
            continue
        col = {"worldspawn": (70, 60, 50), "func_detail": (190, 160, 120),
               "func_wall": (120, 170, 220), "func_door_rotating": (200, 80, 60),
               "func_button": (60, 160, 60), "func_pendulum": (160, 60, 160),
               "func_illusionary": (230, 200, 120)}.get(cls, (128, 128, 128))
        if cls == "worldspawn" and lo[2] <= 0 and hi[2] <= 0:
            col = (225, 220, 205)
        dr.rectangle([P(lo[0], hi[1]), P(hi[0], lo[1])], fill=col, outline=(0, 0, 0))
    for kv, br in ents:
        if br or "origin" not in kv:
            continue
        x, y, z = (float(v) for v in kv["origin"].split())
        c = {"light": (255, 200, 0), "info_player_start": (255, 0, 0)}.get(kv["classname"], (0, 0, 255))
        dr.ellipse([P(x - 4, y + 4), P(x + 4, y - 4)], fill=c, outline=(0, 0, 0))
    img.save(out)


if __name__ == "__main__":
    main()
