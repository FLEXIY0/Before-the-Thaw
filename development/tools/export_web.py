#!/usr/bin/env python3
"""Export a .map into a browser walkthrough scene (development/web_preview/).

This is NOT the game engine - it is a preview to walk through the level in a
browser before/without compiling: real textures, collision boxes, sounds,
and a baked per-vertex light (point lights + overcast sky through the
windows, with shadows from brushes), in the spirit of the GoldSrc look.

Output:
  development/web_preview/scene.json   geometry, colliders, entities
  development/web_preview/tex/*.png    textures (copied from textures_src)
  development/web_preview/sky/*.png    skybox faces
  development/web_preview/snd/*.wav    sounds used by the map

usage: python3 export_web.py [map]
"""
import json
import math
import os
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import check_map
from preview_map import parse_full

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEXDIR = os.path.join(ROOT, "development", "textures_src", "house")
OUT = os.path.join(ROOT, "development", "web_preview")
TOOL = {"null", "origin", "clip", "skip", "hint", "aaatrigger", "bevel"}
STEP = 16          # light sample spacing (units), like a GoldSrc luxel
SHADOW_SKIP = {"func_wall", "func_illusionary"}   # glass and curtains let light through


def face_polys(ents):
    """Yield (entity_index, classname, kv, brush_index, planes, verts, faces)."""
    for ei, (kv, brushes) in enumerate(ents):
        for bi, faces in enumerate(brushes):
            pl = check_map.planes_of([(f[0], f[1]) for f in faces])
            vs = np.array(check_map.brush_verts(pl))
            yield ei, kv.get("classname"), kv, bi, pl, vs, faces


def order_face(fv, n):
    c = np.mean(fv, 0)
    u = np.cross(n, [0, 0, 1]) if abs(n[2]) < 0.9 else np.array([1.0, 0, 0])
    u /= np.linalg.norm(u)
    w = np.cross(n, u)
    return sorted(fv, key=lambda v: math.atan2(np.dot(v - c, w), np.dot(v - c, u))), u, w, c


def grid_face(fv, n):
    """Split a planar convex polygon into small triangles for vertex lighting.

    Rectangles become a grid of ~STEP quads; other polygons are fanned and
    their triangles subdivided uniformly.
    """
    fv, u, w, c = order_face(fv, n)
    fv = np.array(fv)
    uu, ww = (fv - c) @ u, (fv - c) @ w
    tris = []
    is_rect = len(fv) == 4 and len(set(np.round(uu, 3))) == 2 and len(set(np.round(ww, 3))) == 2
    if is_rect:
        u0, u1, w0, w1 = uu.min(), uu.max(), ww.min(), ww.max()
        nu = max(1, int(math.ceil((u1 - u0) / STEP)))
        nw = max(1, int(math.ceil((w1 - w0) / STEP)))
        P = lambda a, b: c + u * a + w * b
        for i in range(nu):
            for j in range(nw):
                a0, a1 = u0 + (u1 - u0) * i / nu, u0 + (u1 - u0) * (i + 1) / nu
                b0, b1 = w0 + (w1 - w0) * j / nw, w0 + (w1 - w0) * (j + 1) / nw
                p00, p10, p11, p01 = P(a0, b0), P(a1, b0), P(a1, b1), P(a0, b1)
                tris += [(p00, p10, p11), (p00, p11, p01)]
    else:
        for k in range(1, len(fv) - 1):
            a, b, cc = fv[0], fv[k], fv[k + 1]
            size = max(np.linalg.norm(b - a), np.linalg.norm(cc - a), np.linalg.norm(cc - b))
            m = max(1, int(math.ceil(size / STEP)))
            for i in range(m):
                for j in range(m - i):
                    q = lambda s, t: a + (b - a) * s / m + (cc - a) * t / m
                    tris.append((q(i, j), q(i + 1, j), q(i, j + 1)))
                    if j < m - i - 1:
                        tris.append((q(i + 1, j), q(i + 1, j + 1), q(i, j + 1)))
    # keep front-facing winding (counter-clockwise seen from outside)
    out = []
    for t in tris:
        if np.dot(np.cross(t[1] - t[0], t[2] - t[0]), n) < 0:
            t = (t[0], t[2], t[1])
        out.append(t)
    return out


class Occluders:
    """Convex brushes as plane sets; segment occlusion test (Cyrus-Beck)."""

    def __init__(self, brushes):
        self.b = brushes  # list of (N[k,3], D[k], lo, hi)

    def blocked(self, P, Q):
        """P, Q: (n,3). Returns bool (n,) - segment P->Q passes through a solid."""
        n = len(P)
        hit = np.zeros(n, bool)
        dvec = Q - P
        lo_seg, hi_seg = np.minimum(P, Q), np.maximum(P, Q)
        for N, D, lo, hi in self.b:
            cand = ~hit & np.all(hi_seg >= lo - 0.1, 1) & np.all(lo_seg <= hi + 0.1, 1)
            if not cand.any():
                continue
            idx = np.where(cand)[0]
            p, d = P[idx], dvec[idx]
            t0 = np.zeros(len(idx))
            t1 = np.ones(len(idx))
            ok = np.ones(len(idx), bool)
            for k in range(len(D)):
                num = D[k] - p @ N[k]          # >0 means p is inside this half-space
                den = d @ N[k]
                par = np.abs(den) < 1e-9
                ok &= ~(par & (num < 0))
                with np.errstate(divide="ignore", invalid="ignore"):
                    t = num / den
                ent = (den < 0) & ~par
                ext = (den > 0) & ~par
                t0 = np.where(ent, np.maximum(t0, t), t0)
                t1 = np.where(ext, np.minimum(t1, t), t1)
            inside = ok & (t0 < t1 - 1e-4) & (t1 > 1e-3) & (t0 < 1 - 1e-3)
            hit[idx[inside]] = True
        return hit


def bake(points, normals, lights, occ, sky_dirs, sky_col, sky_scale):
    """Per-vertex light (linear, 1.0 = full texture brightness)."""
    col = np.zeros_like(points) + np.array([0.075, 0.07, 0.07])   # bounce ambient
    P = points + normals * 0.75
    for o, c, br in lights:
        d = o[None, :] - P
        dist = np.linalg.norm(d, axis=1)
        lam = np.clip(np.sum(d * normals, 1) / np.maximum(dist, 1e-3), 0, 1)
        reach = (lam > 0) & (dist < br * 6)
        vis = np.zeros(len(P), bool)
        idx = np.where(reach)[0]
        if len(idx):
            vis[idx] = ~occ.blocked(P[idx], np.repeat(o[None, :], len(idx), 0))
        # GoldSrc-ish falloff: brightness / distance, softened near the source
        inten = br * 1.15 / (dist + 30) * lam * vis
        col += np.outer(inten, c)
    for sd in sky_dirs:
        lam = np.clip(normals @ sd, 0, 1)
        idx = np.where(lam > 0)[0]
        if not len(idx):
            continue
        far = P[idx] + sd[None, :] * 900
        vis = ~occ.blocked(P[idx], far)
        add = np.zeros(len(P))
        add[idx] = lam[idx] * vis * sky_scale
        col += np.outer(add, sky_col)
    return col


def main():
    mp = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "development", "maps_src", "btt_house.map")
    ents = parse_full(mp)
    os.makedirs(os.path.join(OUT, "tex"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "sky"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "snd"), exist_ok=True)

    lights, switchable = [], {}
    sun = None
    point_ents = []
    for kv, br in ents:
        cls = kv.get("classname")
        if cls == "light":
            o = np.array([float(v) for v in kv["origin"].split()])
            r, g, b, bright = (float(v) for v in kv["_light"].split())
            L = (o, np.array([r, g, b]) / 255.0, bright)
            if "targetname" in kv:
                switchable.setdefault(kv["targetname"], []).append((L, kv.get("spawnflags") == "1"))
            else:
                lights.append(L)
        elif cls == "light_environment":
            sun = kv
        if not br and "origin" in kv:
            point_ents.append(kv)

    occl, solids, entities = [], [], {}
    meshes = []   # per entity: list of (tex, verts)
    for ei, cls, kv, bi, pl, vs, faces in face_polys(ents):
        if any(t.lower() == "origin" for *_, t in pl):
            entities.setdefault(ei, {"cls": cls, "kv": kv, "origin": vs.mean(0).tolist()})
            entities[ei]["origin"] = vs.mean(0).tolist()
            continue
        lo, hi = vs.min(0), vs.max(0)
        is_sky = any(t.lower() == "sky" for *_, t in pl)
        if cls not in SHADOW_SKIP and not is_sky:
            N = np.array([p[0] for p in pl])
            D = np.array([p[1] for p in pl])
            occl.append((N, D, lo, hi))
        if cls not in ("func_illusionary",) and not is_sky:
            solids.append((ei, cls, lo.tolist(), hi.tolist()))
        entities.setdefault(ei, {"cls": cls, "kv": kv, "origin": None})
        for (n, d, tex), f in zip(pl, faces):
            if tex.lower() in TOOL or tex.lower() == "sky":
                continue
            fv = [v for v in vs if abs(np.dot(n, v) - d) < 0.01]
            if len(fv) < 3:
                continue
            vals = f[2]
            meshes.append(dict(ent=ei, cls=cls, tex=tex, n=n, tris=grid_face(fv, n),
                               U=np.array(vals[0:3]), ou=vals[3], V=np.array(vals[4:7]),
                               ov=vals[7], su=vals[9], sv=vals[10]))
    occ = Occluders(occl)

    # sky: overcast dome = a ring of directions, stronger from above
    pitch = math.radians(float(sun.get("pitch", -60))) if sun else math.radians(-60)
    sky_dirs = []
    for el in (20, 45, 70):
        for k in range(8):
            a = 2 * math.pi * k / 8 + 0.3
            sky_dirs.append(np.array([math.cos(a) * math.cos(math.radians(el)),
                                      math.sin(a) * math.cos(math.radians(el)),
                                      math.sin(math.radians(el))]))
    sky_col = np.array([170, 184, 205]) / 255.0

    # flatten all vertices for baking
    pts, nrm, owner = [], [], []
    for mi, m in enumerate(meshes):
        for t in m["tris"]:
            for v in t:
                pts.append(v)
                nrm.append(m["n"])
                owner.append(mi)
    pts, nrm = np.array(pts), np.array(nrm)
    print("vertices to bake: %d, occluders: %d" % (len(pts), len(occl)))
    base = bake(pts, nrm, lights, occ, sky_dirs, sky_col, 0.16)
    outdoor = (pts[:, 0] < -17) | (pts[:, 1] < -17) | (pts[:, 0] > 337) | (pts[:, 1] > 289)
    base[outdoor] = np.array([0.95, 0.97, 1.0])      # snow/fence outside: flat daylight
    sw = {}
    for name, items in switchable.items():
        sw[name] = {"on": not items[0][1],
                    "rgb": np.round(bake(pts, nrm, [it[0] for it in items], occ, [], sky_col, 0)
                                    - np.array([0.075, 0.07, 0.07]), 3)}
        sw[name]["rgb"][outdoor] = 0

    # pack per texture & entity
    groups = {}
    vi = 0
    for mi, m in enumerate(meshes):
        tw, th = Image.open(os.path.join(TEXDIR, m["tex"] + ".png")).size if \
            os.path.exists(os.path.join(TEXDIR, m["tex"] + ".png")) else (16, 16)
        key = (m["ent"], m["tex"])
        g = groups.setdefault(key, {"pos": [], "uv": [], "col": [], "sw": {k: [] for k in sw}})
        for t in m["tris"]:
            for v in t:
                s = (v @ m["U"]) / m["su"] + m["ou"]
                tt = (v @ m["V"]) / m["sv"] + m["ov"]
                g["pos"] += [round(float(v[0]), 2), round(float(v[2]), 2), round(float(-v[1]), 2)]
                g["uv"] += [round(s / tw, 4), round(-tt / th, 4)]
                g["col"] += [round(float(x), 3) for x in base[vi]]
                for k in sw:
                    g["sw"][k] += [float(x) for x in sw[k]["rgb"][vi]]
                vi += 1
    ent_out = {}
    for ei, e in entities.items():
        kv = e["kv"]
        ent_out[str(ei)] = {"cls": e["cls"], "origin": e["origin"],
                            **{k: v for k, v in kv.items() if k not in ("classname",)}}
    scene = {
        "units": "GoldSrc units, exported as three.js (x, z, -y)",
        "groups": [{"ent": k[0], "tex": k[1], **v} for k, v in groups.items()],
        "switches": {k: v["on"] for k, v in sw.items()},
        "solids": solids,
        "entities": ent_out,
        "points": point_ents,
    }
    # drop empty switch arrays to save space
    for g in scene["groups"]:
        g["sw"] = {k: [round(x, 3) for x in v] for k, v in g["sw"].items() if any(abs(x) > 1e-3 for x in v)}
    with open(os.path.join(OUT, "scene.json"), "w") as fp:
        json.dump(scene, fp, separators=(",", ":"))
    used = {g["tex"] for g in scene["groups"]}
    for t in used:
        src = os.path.join(TEXDIR, t + ".png")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, "tex", t + ".png"))
    for k in ("rt", "bk", "lf", "ft", "up", "dn"):
        Image.open(os.path.join(ROOT, "game", "gfx", "env", "btt_overcast%s.tga" % k)).save(
            os.path.join(OUT, "sky", k + ".png"))
    snd = {kv["message"] for kv in point_ents if kv.get("classname") == "ambient_generic"}
    snd |= {"doors/doormove1.wav", "buttons/lightswitch2.wav", "buttons/latchlocked1.wav",
            "debris/pushbox1.wav", "player/pl_step1.wav", "player/pl_step2.wav",
            "player/pl_step3.wav", "player/pl_step4.wav"}
    for s in snd:
        shutil.copy(os.path.join(ROOT, "game", "sound", s), os.path.join(OUT, "snd", s.replace("/", "_")))
    size = os.path.getsize(os.path.join(OUT, "scene.json"))
    print("scene.json %.1f MB, %d groups, %d textures, %d sounds" % (size / 1e6, len(groups), len(used), len(snd)))


if __name__ == "__main__":
    main()
