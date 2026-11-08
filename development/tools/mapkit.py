"""mapkit - tiny brush/entity writer for GoldSrc .map files (Valve 220 format).

The output opens in TrenchBroom (Half-Life game config), J.A.C.K. and
Hammer 3.5, and compiles with ZHLT/VHLT/SDHLT.

Conventions
  * units: 1 unit ~ 1 inch, player hull 32x32x72, eye height 64 (28 above origin)
  * every brush is a convex prism: a CCW polygon extruded along x, y or z
  * plane points are integers, so the geometry is exact
"""
import math

# ------------------------------------------------------------------ vectors


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    l = math.sqrt(dot(a, a))
    return (a[0] / l, a[1] / l, a[2] / l)


def scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


# ------------------------------------------------------------------ textures
# default world scale per texture (texels -> units); anything missing = 1.0
TEX_SCALE = {}
TEX_SIZE = {}   # filled by load_tex_sizes(): name -> (w, h)


def load_tex_sizes(png_dir):
    import os
    from PIL import Image
    for f in os.listdir(png_dir):
        if f.endswith(".png"):
            TEX_SIZE[f[:-4]] = Image.open(os.path.join(png_dir, f)).size


class Tex:
    """Texture assignment for one face.

    mode 'world': world-aligned projection, scale from TEX_SCALE (or s)
    mode 'fit'  : the whole texture is stretched exactly over the face
    """

    def __init__(self, name, mode="world", s=None, shift=(0, 0), rot=0):
        self.name, self.mode, self.s, self.shift, self.rot = name, mode, s, shift, rot


def as_tex(t):
    if t is None:
        return None
    return t if isinstance(t, Tex) else Tex(t)


def fit(name):
    return Tex(name, "fit")


def face_axes(n):
    """Readable (non-mirrored when seen from outside) projection axes."""
    if abs(n[2]) > 0.75:
        return (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
    u = norm(cross((0, 0, 1), n))
    v = norm(cross(u, n))
    return u, v


# ------------------------------------------------------------------ brushes
# cyclic coordinate permutations keep the handedness (and so the winding)
_PERM = {"z": (0, 1, 2), "x": (1, 2, 0), "y": (2, 0, 1)}


def _to_world(axis, a, b, c):
    loc = (a, b, c)
    p = _PERM[axis]
    out = [0, 0, 0]
    for i in range(3):
        out[p[i]] = loc[i]
    return tuple(out)


class Face:
    def __init__(self, n, c, verts, tex):
        self.n, self.c, self.verts, self.tex = n, c, verts, tex

    def points(self):
        n = self.n
        u = None
        for cand in ((0, 0, 1), (1, 0, 0), (0, 1, 0)):
            if dot(n, cand) == 0:
                u = cand
                break
        assert u is not None, "plane must contain one world axis"
        v = cross(n, u)
        k = 64
        p1 = self.c
        p0 = add(p1, scale(u, k))
        p2 = add(p1, scale(v, k))
        # (p0-p1) x (p2-p1) must point along the outward normal
        assert dot(cross(sub(p0, p1), sub(p2, p1)), n) > 0
        return p0, p1, p2

    def line(self):
        p0, p1, p2 = self.points()
        t = self.tex
        nn = norm(self.n)
        u, v = face_axes(nn)
        if t.mode == "fit":
            us = [dot(p, u) for p in self.verts]
            vs = [dot(p, v) for p in self.verts]
            tw, th = TEX_SIZE.get(t.name, (64, 64))
            su = (max(us) - min(us)) / tw
            sv = (max(vs) - min(vs)) / th
            ou = -min(us) / su
            ov = -min(vs) / sv
        else:
            s = t.s if t.s is not None else TEX_SCALE.get(t.name, 1.0)
            su = sv = s
            ou, ov = t.shift
        def f(x):
            if isinstance(x, float):
                x = round(x, 6)
                if x == int(x):
                    return str(int(x))
                return ("%.6f" % x).rstrip("0").rstrip(".")
            return str(x)
        pts = " ".join("( %s %s %s )" % tuple(f(c) for c in p) for p in (p0, p1, p2))
        return "%s %s [ %s %s %s %s ] [ %s %s %s %s ] %s %s %s" % (
            pts, t.name, f(u[0]), f(u[1]), f(u[2]), f(ou), f(v[0]), f(v[1]), f(v[2]), f(ov),
            t.rot, f(su), f(sv))


class Brush:
    def __init__(self, faces):
        self.faces = faces

    def bounds(self):
        vs = [p for f in self.faces for p in f.verts]
        return (tuple(min(p[i] for p in vs) for i in range(3)),
                tuple(max(p[i] for p in vs) for i in range(3)))

    def text(self):
        return "{\n" + "\n".join(f.line() for f in self.faces) + "\n}\n"


def prism(poly, c0, c1, axis="z", side=None, top=None, bottom=None, sides=None):
    """Extrude a CCW polygon (in the plane perpendicular to `axis`) from c0 to c1.

    side   : texture for all side faces
    sides  : optional list of per-edge textures (same order as poly edges)
    top    : texture of the c1 cap, bottom: texture of the c0 cap
    """
    assert c1 > c0
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    assert area > 0, "polygon must be CCW"
    faces = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        da, db = b[0] - a[0], b[1] - a[1]
        g = math.gcd(int(abs(da)), int(abs(db))) or 1
        nl = (db // g, -da // g, 0)
        nw = _to_world(axis, *nl)
        verts = [_to_world(axis, a[0], a[1], c0), _to_world(axis, b[0], b[1], c0),
                 _to_world(axis, b[0], b[1], c1), _to_world(axis, a[0], a[1], c1)]
        t = sides[i] if sides else side
        faces.append(Face(nw, verts[0], verts, as_tex(t)))
    capv1 = [_to_world(axis, p[0], p[1], c1) for p in poly]
    capv0 = [_to_world(axis, p[0], p[1], c0) for p in poly]
    faces.append(Face(_to_world(axis, 0, 0, 1), capv1[0], capv1, as_tex(top or side)))
    faces.append(Face(_to_world(axis, 0, 0, -1), capv0[0], capv0, as_tex(bottom or side)))
    return Brush(faces)


def box(x0, y0, z0, x1, y1, z1, tex, **faces):
    """Axis aligned box. Face overrides: px nx py ny pz nz (x+, x-, ...)."""
    assert x1 > x0 and y1 > y0 and z1 > z0, (x0, y0, z0, x1, y1, z1)
    t = lambda k: faces.get(k, tex)
    poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    # edges: (x0,y0)->(x1,y0) faces -y ; ->(x1,y1) +x ; ->(x0,y1) +y ; -> -x
    return prism(poly, z0, z1, "z", sides=[t("ny"), t("px"), t("py"), t("nx")],
                 top=t("pz"), bottom=t("nz"))


def ngon(cx, cy, r, n=8, rot=0.0):
    """Integer CCW polygon approximating a circle."""
    pts = []
    for i in range(n):
        a = rot + 2 * math.pi * i / n
        p = (int(round(cx + r * math.cos(a))), int(round(cy + r * math.sin(a))))
        if not pts or p != pts[-1]:
            pts.append(p)
    if pts[0] == pts[-1]:
        pts.pop()
    return pts


def cyl(cx, cy, r, z0, z1, side, top=None, bottom=None, n=8, axis="z"):
    return prism(ngon(cx, cy, r, n, math.pi / n), z0, z1, axis, side=side, top=top, bottom=bottom)


# ------------------------------------------------------------------ entities
class Entity:
    def __init__(self, classname, **kv):
        self.kv = {"classname": classname}
        for k, v in kv.items():
            self.kv[k] = v
        self.brushes = []

    def add(self, *brushes):
        for b in brushes:
            if isinstance(b, (list, tuple)):
                self.add(*b)
            else:
                self.brushes.append(b)
        return self

    def text(self):
        out = "{\n"
        for k, v in self.kv.items():
            if isinstance(v, (tuple, list)):
                v = " ".join(str(x) for x in v)
            out += '"%s" "%s"\n' % (k, v)
        for b in self.brushes:
            out += b.text()
        out += "}\n"
        return out


class Map:
    def __init__(self, **world_kv):
        self.world = Entity("worldspawn", **world_kv)
        self.entities = [self.world]

    def ent(self, classname, **kv):
        e = Entity(classname, **kv)
        self.entities.append(e)
        return e

    def text(self, header=""):
        return header + "".join(e.text() for e in self.entities)
