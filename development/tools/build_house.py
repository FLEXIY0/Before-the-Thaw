#!/usr/bin/env python3
"""Before the Thaw - blockout generator for the starting location (btt_house).

Writes development/maps_src/btt_house.map (Valve 220 format).

The .map is the real source of the level: open it in TrenchBroom / J.A.C.K. /
Hammer and keep working there.  This script only exists so the first
version is reproducible and the layout is documented in code.  Re-running it
OVERWRITES manual edits to the .map, so once you start editing by hand,
stop using it (or copy the map under a new name).

One-room izba (изба в одну комнату), 320 x 272 units inside (~8 x 7 m),
ceiling 96 (~2.4 m).  Top view, X = east, Y = north:

  Y=272 +-------------------------------------------------+
        | STOVE  |wash| kitchen counter |      BED        |
        | (печь) |    |   [ window ]    | (carpet above)  |
        |  mouth>|    |                 |       nightstand|
  Y=176 +--------+                      +-----------------+ chest, clock
        | fridge   firewood                               |
        | side-          (lamp)     stool                 |[window]
        | board+TV                                        | bench
        | coats      rug                chair             |
        | boots          [win1] photos [win2] TABLE+calendar (red corner)
  Y=0   +--[ door ]----------------------------------------+
       X=0                                               X=320

The front (south) faces the road, the east window the field, the north
(kitchen) window the forest - see development/docs/environment_concept.md.
Table, chair and stool are func_pushable: walk into them to push, hold USE
to pull.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mapkit as mk
from mapkit import box, prism, cyl, fit, Tex

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "development", "maps_src", "btt_house.map")
mk.load_tex_sizes(os.path.join(ROOT, "development", "textures_src", "house"))

# smaller props read better with denser texels
for t in ("wood_dark", "wood_light", "wood_blue", "wood_white", "metal_dark",
          "metal_rust", "metal_zinc", "enamel", "enamel_blue", "fab_felt",
          "fab_coat", "fab_quilted", "fab_pillow", "burlap", "cardboard",
          "birch_bark", "log_end", "handle", "fab_blanket", "fab_patch", "fab_shade",
          "fab_curtain", "stove_tile", "fab_rug"):
    mk.TEX_SCALE[t] = 0.5
mk.TEX_SCALE["snow"] = 2.0

NULL = "NULL"     # tool textures come from sdhlt.wad (compile time only)
ORIGIN = "ORIGIN"
SKY = "sky"

# ------------------------------------------------------------------ dimensions
RX, RY = 320, 272  # room interior
H = 96             # ceiling height
GROUND = -40       # outside ground level: the house stands on a log base
CEIL_TOP = 112
WIN_SILL, WIN_TOP = 40, 80
LOG, LOG_EXT = "log_wall", "log_ext"

M = mk.Map(
    mapversion="220",
    wad="btt_house.wad;sdhlt.wad",
    skyname="btt_overcast",
    message="Before the Thaw - House",
    sounds="0",
    MaxRange="4096",
    _generator="development/tools/build_house.py",
)
W = M.world

lights = []


def light(x, y, z, rgb, bright, name=None, dark=False, **kw):
    e = M.ent("light", origin=(x, y, z), _light="%d %d %d %d" % (rgb + (bright,)), **kw)
    if name:
        e.kv["targetname"] = name
        if dark:
            e.kv["spawnflags"] = "1"
    lights.append(e)
    return e


def detail(*brushes, **kv):
    """func_detail: compiled into the world, but does not cut the BSP tree."""
    e = M.ent("func_detail", zhlt_detaillevel="1", **kv)
    e.add(*brushes)
    return e


# ------------------------------------------------------------------ walls
def wall(axis, t0, t1, b0, b1, z0, z1, side_lo, side_hi, holes=(), end_tex=None,
         top=NULL, bottom=NULL):
    """A straight wall with rectangular holes.

    axis 'x': the wall runs along X, thickness along Y in [t0, t1]
    axis 'y': the wall runs along Y, thickness along X in [t0, t1]
    side_lo/side_hi: textures of the faces looking to -thickness / +thickness
    holes: (b_lo, b_hi, z_lo, z_hi)
    """
    cuts = sorted({b0, b1} | {h[0] for h in holes} | {h[1] for h in holes})
    out = []

    def piece(a0, a1, zz0, zz1):
        if a1 <= a0 or zz1 <= zz0:
            return
        e = end_tex or side_lo
        if axis == "x":
            out.append(box(a0, t0, zz0, a1, t1, zz1, e, ny=side_lo, py=side_hi,
                           pz=top if zz1 == z1 else e, nz=bottom if zz0 == z0 else e))
        else:
            out.append(box(t0, a0, zz0, t1, a1, zz1, e, nx=side_lo, px=side_hi,
                           pz=top if zz1 == z1 else e, nz=bottom if zz0 == z0 else e))

    for a0, a1 in zip(cuts, cuts[1:]):
        hs = [h for h in holes if h[0] <= a0 and h[1] >= a1]
        if not hs:
            piece(a0, a1, z0, z1)
        else:
            h = hs[0]
            piece(a0, a1, z0, h[2])
            piece(a0, a1, h[3], z1)
    return out


# ------------------------------------------------------------------ windows
def window(axis, t0, t1, b0, b1, z0, z1, inner_sign, name, curtains=True):
    """Double-glazed village window inside a wall hole.

    inner_sign: +1 if the room is on the +thickness side, -1 otherwise.
    Creates frames + sill (func_detail), two glass panes (func_wall),
    cotton wool between the frames and short curtains.
    """
    def B(a0, a1, s0, s1, zz0, zz1, tex, **kw):
        # a: along the wall, s: across (thickness), z: up
        if axis == "x":
            return box(a0, s0, zz0, a1, s1, zz1, tex, **kw)
        return box(s0, a0, zz0, s1, a1, zz1, tex, **kw)

    inner = t1 if inner_sign > 0 else t0
    outer = t0 if inner_sign > 0 else t1
    d = inner_sign
    frames = []
    panes = []
    for depth in (4, 12):  # inner and outer frame, measured from the room face
        c = inner - d * depth
        s0, s1 = sorted((c - 1.5 * d, c + 1.5 * d))
        s0, s1 = int(s0), int(s1 + 0.5)
        fw = 3
        frames += [
            B(b0, b0 + fw, s0, s1, z0, z1, "wood_white"),
            B(b1 - fw, b1, s0, s1, z0, z1, "wood_white"),
            B(b0 + fw, b1 - fw, s0, s1, z0, z0 + fw, "wood_white"),
            B(b0 + fw, b1 - fw, s0, s1, z1 - fw, z1, "wood_white"),
        ]
        mid = (b0 + b1) // 2
        tz = z1 - (z1 - z0) // 3
        frames.append(B(mid - 1, mid + 1, s0, s1, z0 + fw, z1 - fw, "wood_white"))
        frames.append(B(b0 + fw, b1 - fw, s0, s1, tz - 1, tz + 1, "wood_white"))
        g0, g1 = sorted((c, c + d))
        panes.append(B(b0 + fw, b1 - fw, int(g0), int(g1), z0 + fw, z1 - fw, "glass_frost"))
    # cotton wool laid between the frames (old way of keeping the cold out)
    w0, w1 = sorted((inner - d * 10, inner - d * 6))
    frames.append(B(b0, b1, w0, w1, z0, z0 + 3, "fab_pillow"))
    # sill board sticking into the room
    s0, s1 = sorted((inner - d * 3, inner + d * 6))
    frames.append(B(b0 - 4, b1 + 4, s0, s1, z0 - 2, z0, "wood_white"))
    detail(*frames)
    glass = M.ent("func_wall", targetname=name, rendermode="2", renderamt="150",
                  zhlt_lightflags="0")
    glass.add(*panes)
    if curtains:
        c0, c1 = sorted((inner + d * 1, inner + d * 3))
        detail(
            B(b0 - 6, b1 + 6, c0, c1, z1, z1 + 8, "fab_curtain"),            # valance
            B(b0 - 8, b0 - 1, c0, c1, z0 + 4, z1, "fab_curtain"),
            B(b1 + 1, b1 + 8, c0, c1, z0 + 4, z1, "fab_curtain"),
        )
    # soft cold fill light just inside the window (1999-style "fake bounce")
    mid_s = inner + d * 24
    if axis == "x":
        light((b0 + b1) // 2, mid_s, (z0 + z1) // 2, (168, 186, 214), 28)
    else:
        light(mid_s, (b0 + b1) // 2, (z0 + z1) // 2, (168, 186, 214), 28)


# ------------------------------------------------------------------ doors
def door(name, hinge, slab, tex, edge="wood_dark", swing=+1, use=True, extra=(),
         **kv):
    """func_door_rotating around a vertical hinge.

    hinge: (x, y, z0, z1) - an ORIGIN brush 2x2 around the hinge axis
    slab : (x0, y0, z0, x1, y1, z1) - the closed door leaf
    swing: +1 = counter-clockwise seen from above, -1 = clockwise
    """
    hx, hy, hz0, hz1 = hinge
    x0, y0, z0, x1, y1, z1 = slab
    thin_x = (x1 - x0) < (y1 - y0)
    if thin_x:
        leaf = box(x0, y0, z0, x1, y1, z1, edge, nx=tex, px=tex)
    else:
        leaf = box(x0, y0, z0, x1, y1, z1, edge, ny=tex, py=tex)
    flags = 32  # toggle: stays open until used again
    if use:
        flags |= 256
    if swing < 0:
        flags |= 2
    e = M.ent("func_door_rotating", targetname=name, speed="80", distance="90",
              wait="-1", movesnd="1", stopsnd="1", spawnflags=str(flags),
              lip="0", dmg="0", **kv)
    e.add(leaf, box(hx - 2, hy - 2, hz0, hx + 2, hy + 2, hz0 + 4, ORIGIN), *extra)
    return e


def handle_x(x0, x1, y, z):
    """Door handle pair on a leaf that is thin along X."""
    return [box(x0 - 3, y - 4, z - 1, x0, y, z + 1, "handle"),
            box(x1, y - 4, z - 1, x1 + 3, y, z + 1, "handle")]


def handle_y(y0, y1, x, z):
    return [box(x, y0 - 3, z - 1, x + 4, y0, z + 1, "handle"),
            box(x, y1, z - 1, x + 4, y1 + 3, z + 1, "handle")]



def pushable(brushes, origin, friction="200", size="3"):
    """Furniture the player can move: walk into it to push, hold USE to pull."""
    ox, oy, oz = origin
    e = M.ent("func_pushable", friction=friction, size=size, buoyancy="0",
              spawnflags="0", rendermode="0")
    e.add(*brushes)
    e.add(box(ox - 2, oy - 2, oz, ox + 2, oy + 2, oz + 4, ORIGIN))
    return e


def switch(name, x0, y0, z0, x1, y1, z1, face):
    b = M.ent("func_button", target=name, spawnflags="1", sounds="14", wait="0.5")
    b.add(box(x0, y0, z0, x1, y1, z1, "switch", **{face: fit("switch")}))


# ------------------------------------------------------------------ shell
W.add(box(0, 0, GROUND, RX, RY, 0, "floor_paint", nz=NULL))
W.add(box(-16, -16, H, RX + 16, RY + 16, CEIL_TOP, LOG_EXT, nz="ceiling", pz=NULL))
# log walls (inside: dark logs, outside: weathered grey logs)
W.add(wall("x", -16, 0, -16, RX + 16, GROUND, H, LOG_EXT, LOG,
           holes=[(24, 72, 0, 80), (112, 152, WIN_SILL, WIN_TOP),
                  (196, 236, WIN_SILL, WIN_TOP)], end_tex=LOG_EXT))      # south: door + 2 windows
W.add(wall("x", RY, RY + 16, -16, RX + 16, GROUND, H, LOG, LOG_EXT,
           holes=[(136, 176, 44, WIN_TOP)], end_tex=LOG_EXT))           # north: kitchen window
W.add(wall("y", -16, 0, 0, RY, GROUND, H, LOG_EXT, LOG, end_tex=LOG_EXT))   # west: stove side
W.add(wall("y", RX, RX + 16, 0, RY, GROUND, H, LOG, LOG_EXT,
           holes=[(96, 136, WIN_SILL, WIN_TOP)], end_tex=LOG_EXT))      # east: field window
# central ceiling beam (матица)
detail(box(0, 128, 86, RX, 144, H, "beam"))

window("x", -16, 0, 112, 152, WIN_SILL, WIN_TOP, +1, "win_s1")
window("x", -16, 0, 196, 236, WIN_SILL, WIN_TOP, +1, "win_s2")
window("x", RY, RY + 16, 136, 176, 44, WIN_TOP, -1, "win_n")
window("y", RX, RX + 16, 96, 136, WIN_SILL, WIN_TOP, -1, "win_e")

# ------------------------------------------------------------------ front door
# locked from outside (its master never fires): pushing it rattles the hook
front = M.ent("func_door_rotating", targetname="door_front", speed="80", distance="90",
              wait="-1", movesnd="1", stopsnd="1", spawnflags="0", lip="0", dmg="0",
              master="btt_front_unlocked", locked_sound="12")
front.add(box(26, -10, 1, 70, -6, 79, "wood_dark", py="door_padded", ny="door_ext"),
          box(24, -10, 0, 28, -6, 4, ORIGIN),
          *handle_y(-10, -6, 62, 40))

# ------------------------------------------------------------------ RUSSIAN STOVE (NW corner)
# body 88 x 96, lime-washed, mouth (чело) facing east into the room
SX1, SY0, SY1, SZ = 88, 176, RY, 64
MY0, MY1 = 204, 244   # mouth opening along Y
stove = [
    box(0, SY0, 0, SX1, SY1, 8, "brick_old"),                                   # base
    box(0, SY0, 8, SX1 - 16, SY1, SZ, "whitewash", px="stove_soot"),            # body behind mouth
    box(SX1 - 16, SY0, 8, SX1, MY0, SZ, "whitewash"),                           # right of mouth
    box(SX1 - 16, MY1, 8, SX1, SY1, SZ, "whitewash"),                           # left of mouth
    box(SX1 - 16, MY0, 8, SX1, MY1, 28, "whitewash", pz="stove_soot"),          # hearth floor
    box(SX1 - 16, MY0, 52, SX1, MY1, SZ, "whitewash", nz="stove_soot"),         # lintel
    box(0, SY0, SZ, SX1, SY1, SZ + 4, "whitewash"),                             # top (лежанка)
    box(8, 224, SZ + 4, 48, 264, H, "whitewash"),                               # chimney
    box(SX1 - 20, MY0 - 4, SZ + 4, SX1, MY1 + 4, 84, "whitewash", nz="stove_soot"),  # smoke hood
    box(SX1, MY0, 24, SX1 + 6, MY1, 28, "whitewash", pz="stove_soot"),          # hearth ledge (шесток)
    # small iron firebox door low on the south face
    box(62, SY0 - 1, 8, 78, SY0, 24, "metal_dark", ny=fit("iron_door")),
]
detail(*stove)
# damper leaning by the mouth, cast-iron pots on the ledge, oven fork and poker
detail(box(SX1, MY1 + 2, 2, SX1 + 2, MY1 + 16, 30, "metal_dark", px=fit("iron_door")),
       cyl(SX1 + 3, 214, 5, 28, 36, "metal_dark", top="stove_soot"),
       cyl(SX1 + 3, 230, 4, 28, 33, "metal_rust"),
       box(SX1 + 4, SY0 - 8, 0, SX1 + 6, SY0 - 6, 70, "wood_light"),
       box(SX1 + 2, SY0 - 12, 66, SX1 + 8, SY0 - 2, 68, "metal_dark"),
       box(SX1 + 8, SY0 - 6, 0, SX1 + 10, SY0 - 4, 64, "wood_light"),
       box(SX1 + 7, SY0 - 7, 0, SX1 + 11, SY0 - 3, 3, "metal_dark"))
light(SX1 - 8, 224, 38, (255, 116, 40), 45)
M.ent("ambient_generic", origin=(SX1 + 4, 224, 34), message="ambience/stove_fire.wav",
      health="4", spawnflags="2", pitch="100")
# birch firewood stacked along the stove's south side
logs = []
for (cy, cz) in ((SY0 - 6, 5), (SY0 - 15, 5), (SY0 - 10, 13)):
    logs.append(prism(mk.ngon(cy, cz, 5, 6), 30, 58, "x", side="birch_bark",
                      top=fit("log_end"), bottom=fit("log_end")))
detail(*logs)

# ------------------------------------------------------------------ KITCHEN CORNER (бабий кут)
k = []
# washstand (рукомойник) right next to the stove
k.append(box(92, 248, 0, 116, RY, 30, "wood_blue", pz="enamel"))
k.append(box(96, 252, 30, 112, 268, 33, "enamel"))
k.append(box(98, 262, 52, 110, RY, 68, "metal_zinc"))
k.append(box(103, 260, 46, 105, 263, 52, "metal_dark"))
k.append(box(92, 270, 34, 116, RY, 50, "enamel"))
k.append(box(118, 271, 60, 130, RY, 92, "wood_white", ny=fit("fab_towel")))
# cupboards + worktop under the north window
k.append(box(120, 250, 0, 220, RY, 34, "wood_blue", pz="wood_light"))
k.append(box(118, 246, 34, 222, RY, 37, "wood_light"))
for x in (144, 170, 196):
    k.append(box(x, 249, 4, x + 1, 250, 32, "wood_dark"))
k.append(cyl(130, 258, 7, 37, 41, "enamel", top="enamel"))                 # bowl
k.append(cyl(150, 262, 5, 37, 46, "enamel_blue", top="metal_dark"))        # pot
k.append(cyl(208, 260, 5, 37, 44, "metal_zinc", top="metal_dark"))         # kettle
k.append(box(207, 256, 44, 210, 257, 46, "metal_dark"))
k.append(box(180, 252, 37, 196, 264, 38, "wood_light"))                    # bread board
# old enamel fridge between the sideboard and the stove
k.append(box(0, 148, 0, 26, 174, 60, "enamel", px=Tex("enamel", s=1.0)))
k.append(box(26, 154, 30, 28, 158, 44, "metal_dark"))
k.append(box(2, 150, 60, 24, 172, 62, "enamel"))
detail(*k)
M.ent("ambient_generic", origin=(32, 162, 40), message="ambience/fridge_hum.wav",
      health="2", spawnflags="2", pitch="100")

# ------------------------------------------------------------------ BED CORNER (NE)
b = []
BX0, BY0, BX1, BY1 = 224, 228, 316, 270          # bed along the north wall, head east
for (x, y, top) in ((BX0, BY0, 32), (BX0, BY1 - 3, 32), (BX1 - 3, BY0, 44), (BX1 - 3, BY1 - 3, 44)):
    b.append(box(x, y, 0, x + 3, y + 3, top, "metal_dark"))
    b.append(box(x - 1, y - 1, top, x + 4, y + 4, top + 3, "metal_zinc"))
b.append(box(BX1 - 2, BY0 + 3, 20, BX1 - 1, BY1 - 3, 42, "metal_dark"))   # head grille
for y in range(BY0 + 7, BY1 - 3, 6):
    b.append(box(BX1 - 3, y, 22, BX1, y + 1, 40, "metal_dark"))
b.append(box(BX0, BY0 + 3, 20, BX0 + 1, BY1 - 3, 30, "metal_dark"))       # foot rail
b.append(box(BX0 + 1, BY0 + 1, 6, BX1 - 1, BY1 - 1, 16, "fab_patch"))     # quilt hanging down
b.append(box(BX0 + 2, BY0 + 2, 16, BX1 - 2, BY1 - 2, 24, "fab_patch"))    # mattress + quilt
b.append(box(BX1 - 18, BY0 + 6, 24, BX1 - 4, BY1 - 6, 31, "fab_pillow"))  # pyramid of pillows
b.append(box(BX1 - 15, BY0 + 9, 31, BX1 - 6, BY1 - 9, 36, "fab_pillow"))
b.append(box(BX1 - 13, BY0 + 12, 36, BX1 - 8, BY1 - 12, 39, "fab_pillow"))
# carpet on the wall over the bed
b.append(box(228, RY - 2, 30, 312, RY, 84, "wall_carpet", ny=fit("wall_carpet")))
# nightstand with books and an alarm clock
b.append(box(292, 196, 0, 316, 222, 26, "wood_dark"))
b.append(box(294, 195, 4, 314, 196, 22, "wood_dark"))
b.append(box(296, 204, 26, 310, 216, 30, "books", pz="wood_dark"))
# chest (сундук) against the east wall, folded padded jacket on it
b.append(box(296, 146, 0, RX, 190, 20, "wood_dark"))
b.append(box(295, 145, 20, RX, 191, 23, "wood_dark"))
for y in (152, 182):
    b.append(box(294, y, 0, RX, y + 3, 23, "metal_dark"))
b.append(box(300, 150, 23, 316, 172, 28, "fab_quilted"))
b.append(box(300, 174, 23, 314, 188, 26, "fab_blanket"))
# small rag rug by the bed
b.append(box(232, 196, 0, 286, 222, 1, "fab_rug"))
detail(*b)

# ходики - wall clock with pendulum and weights, on the east wall above the chest
detail(box(314, 160, 54, RX, 176, 78, "wood_dark", nx=fit("clock_face")),
       box(313, 158, 76, RX, 178, 80, "wood_dark"),
       box(314, 163, 30, 315, 164, 54, "metal_dark"),
       box(314, 171, 38, 315, 172, 54, "metal_dark"),
       box(313, 162, 24, 316, 165, 30, "metal_dark"),
       box(313, 170, 32, 316, 173, 38, "metal_dark"))
M.ent("func_pendulum", speed="38", distance="20", spawnflags="73",
      angles="0 0 -10", rendermode="0").add(
    box(313, 167, 36, 314, 169, 54, "metal_dark"),
    box(312, 164, 33, 314, 172, 39, "metal_rust"),
    box(311, 166, 52, 315, 170, 56, ORIGIN))
M.ent("ambient_generic", origin=(310, 168, 64), message="ambience/clock_tick.wav",
      health="5", spawnflags="2", pitch="100")

# radio on the nightstand - press USE to switch it on/off
radio = M.ent("func_button", target="radio_snd", spawnflags="1", sounds="14", wait="0.5")
radio.add(box(298, 212, 30, 312, 220, 38, "wood_dark", ny=fit("radio_front")))
M.ent("ambient_generic", targetname="radio_snd", origin=(305, 204, 40),
      message="ambience/radio_static.wav", health="5", spawnflags="20", pitch="100")

# ------------------------------------------------------------------ RED CORNER (SE): table by the window
# the table stands to the left of window 2 (looking out), the calendar hangs above it
TX0, TY0, TX1, TY1 = 244, 6, 300, 50
table = [box(TX0, TY0, 28, TX1, TY1, 31, "wood_light"),
         box(TX0 + 2, TY0 + 2, 31, TX1 - 2, TY1 - 2, 32, "fab_curtain"),      # oilcloth
         box(TX0 + 4, TY0 + 4, 22, TX1 - 4, TY0 + 6, 26, "wood_light"),
         box(TX0 + 4, TY1 - 6, 22, TX1 - 4, TY1 - 4, 26, "wood_light"),
         box(TX0 + 34, TY0 + 8, 32, TX1 - 6, TY0 + 20, 41, "wood_dark"),      # bread box
         box(TX0 + 8, TY1 - 16, 32, TX0 + 24, TY1 - 6, 34, "paper", pz=fit("paper")),
         cyl(TX0 + 30, TY1 - 10, 2, 32, 36, "enamel_blue")]                  # mug
for (x, y) in ((TX0 + 2, TY0 + 2), (TX1 - 5, TY0 + 2), (TX0 + 2, TY1 - 5), (TX1 - 5, TY1 - 5)):
    table.append(box(x, y, 0, x + 3, y + 3, 28, "wood_light"))
pushable(table, ((TX0 + TX1) // 2, (TY0 + TY1) // 2, 0), friction="300", size="2")
detail(box(262, 0, 46, 278, 1, 70, "paper", py=fit("calendar")))
# bench along the east wall (лавка)
detail(box(306, 4, 16, RX, 144, 19, "wood_light"),
       *[box(308, y, 0, 318, y + 4, 16, "wood_light") for y in (8, 72, 136)])
# corner shelf (божница) with an icon and an embroidered towel
detail(prism([(296, 0), (RX, 0), (RX, 24)], 74, 76, "z", side="wood_dark"),
       prism([(303, 18), (314, 7), (316, 9), (305, 20)], 76, 92, "z", side="wood_dark",
             sides=[fit("icon"), "wood_dark", "wood_dark", "wood_dark"]),
       prism([(298, 22), (316, 4), (317, 5), (299, 23)], 50, 74, "z", side="fab_towel",
             sides=[fit("fab_towel"), "fab_towel", "fab_towel", "fab_towel"]))
# chair at the table and a stool by the stove - both can be moved
CX, CY = 262, 58
chair = [box(CX, CY, 16, CX + 16, CY + 16, 18, "wood_dark"),
         box(CX, CY + 14, 18, CX + 16, CY + 16, 36, "wood_dark")]
for (dx, dy) in ((0, 0), (14, 0), (0, 14), (14, 14)):
    chair.append(box(CX + dx, CY + dy, 0, CX + dx + 2, CY + dy + 2, 16, "wood_dark"))
pushable(chair, (CX + 8, CY + 8, 0))
SX, SY = 116, 206
stool = [box(SX, SY, 18, SX + 16, SY + 16, 20, "wood_light")]
for (dx, dy) in ((1, 1), (13, 1), (1, 13), (13, 13)):
    stool.append(box(SX + dx, SY + dy, 0, SX + dx + 2, SY + dy + 2, 18, "wood_light"))
pushable(stool, (SX + 8, SY + 8, 0))
# family photos between the two front windows
detail(box(165, 0, 52, 187, 1, 72, "wood_dark", py=fit("photos")))

# ------------------------------------------------------------------ WEST WALL: sideboard, TV, phone
w = [box(0, 84, 0, 22, 146, 32, "wood_dark"),
     box(22, 86, 4, 23, 114, 30, "wood_dark"),
     box(22, 116, 4, 23, 144, 30, "wood_dark"),
     box(0, 88, 32, 16, 142, 60, "wood_dark", px=fit("crockery")),
     box(0, 84, 60, 24, 146, 62, "wood_dark")]
# old CRT TV with a doily and a rabbit-ear antenna on top of the sideboard
w += [box(0, 90, 62, 24, 120, 88, "wood_dark", px=fit("tv_front")),
      box(4, 96, 88, 20, 114, 89, "fab_pillow"),
      box(10, 104, 89, 12, 106, 94, "metal_dark")]
# rotary telephone next to it
w += [box(3, 125, 66, 15, 128, 68, "phone_side"),
      box(0, 130, 40, 1, 131, 62, "metal_dark")]
detail(*w)
phone = M.ent("func_button", target="phone_snd", spawnflags="1", sounds="0", wait="3")
phone.add(box(4, 126, 62, 14, 136, 66, "phone_side", pz=fit("phone_top")))
M.ent("ambient_generic", targetname="phone_snd", origin=(20, 131, 70),
      message="ambience/phone_dial.wav", health="5", spawnflags="50", pitch="100")

# ------------------------------------------------------------------ BY THE DOOR: coats, felt boots, buckets
d = [box(0, 8, 60, 4, 76, 64, "wood_dark"),                                   # coat board
     box(4, 12, 22, 14, 30, 62, "fab_quilted"),                               # padded jacket
     box(4, 36, 18, 12, 56, 62, "fab_coat"),                                  # coat
     box(4, 60, 52, 8, 72, 64, "fab_felt")]                                   # fur hat
for y in (14, 22, 40, 48):                                                    # валенки
    d.append(box(14, y, 0, 24, y + 6, 4, "fab_felt"))
    d.append(box(14, y, 4, 19, y + 6, 18, "fab_felt"))
d += [box(26, 60, 0, 38, 66, 4, "metal_dark"), box(26, 68, 0, 38, 74, 4, "metal_dark")]  # galoshes
d += [cyl(88, 12, 7, 0, 14, "metal_zinc", top="glass_frost"),                # water buckets
      cyl(102, 12, 7, 0, 14, "metal_zinc", top="metal_dark"),
      box(86, 10, 14, 89, 18, 15, "enamel_blue"),
      box(80, 2, 12, 82, 4, 50, "wood_light"),                                # broom
      box(78, 0, 0, 84, 6, 12, "burlap")]
# woven runner from the door into the room
d.append(box(28, 4, 0, 68, 120, 1, "fab_rug"))
d.append(box(68, 96, 0, 240, 124, 1, "fab_rug"))
detail(*d)

# ------------------------------------------------------------------ light
# lamp with an orange fabric shade hanging from the beam, switch by the door
detail(box(159, 135, 78, 161, 137, 86, "metal_dark"),
       prism(mk.ngon(160, 136, 12, 8), 70, 78, "z", side="fab_shade", bottom="fab_shade"),
       cyl(160, 136, 3, 66, 70, "bulb"))
light(160, 136, 62, (255, 190, 120), 150, name="light_main")
switch("light_main", 76, 0, 50, 82, 1, 56, "py")

# ------------------------------------------------------------------ OUTSIDE (only seen from the windows)
# Everything outside lives in its own TrenchBroom layer "Outside" so it can be
# hidden while editing the room (compilers treat func_group as world).
outside = M.ent("func_group", _tb_type="_tb_layer", _tb_name="Outside", _tb_id="1")
SK0, SK1 = (-512, -512, GROUND - 24), (900, 800, 320)
x0, y0, z0 = SK0
x1, y1, z1 = SK1
outside.add(box(x0, y0, z0, x1, y1, GROUND, "snow", nz=NULL),                  # ground
            box(x0 - 16, y0 - 16, z0, x0, y1 + 16, z1 + 16, SKY),              # sky box
            box(x1, y0 - 16, z0, x1 + 16, y1 + 16, z1 + 16, SKY),
            box(x0, y0 - 16, z0, x1, y0, z1 + 16, SKY),
            box(x0, y1, z0, x1, y1 + 16, z1 + 16, SKY),
            box(x0, y0, z1, x1, y1, z1 + 16, SKY))
# snow banks against the house and an old fence along the road (south) and field (east)
outside.add(box(-32, -40, GROUND, RX + 32, -16, GROUND + 6, "snow"),
            box(RX + 16, -32, GROUND, RX + 48, RY + 32, GROUND + 8, "snow"),
            box(-32, RY + 16, GROUND, RX + 32, RY + 48, GROUND + 10, "snow"))
for x in range(-160, 560, 72):
    outside.add(box(x, -228, GROUND, x + 6, -222, GROUND + 52, "boards_raw"))
outside.add(box(-160, -226, GROUND + 16, 566, -224, GROUND + 22, "boards_raw"),
            box(-160, -226, GROUND + 38, 566, -224, GROUND + 44, "boards_raw"))
for y in range(-220, 560, 80):
    outside.add(box(560, y, GROUND, 566, y + 6, GROUND + 52, "boards_raw"))
outside.add(box(562, -220, GROUND + 30, 564, 566, GROUND + 36, "boards_raw"))
M.ent("light_environment", angles="0 215 0", pitch="-60",
      _light="168 178 196 60", _diffuse_light="170 184 205 90")
M.ent("ambient_generic", origin=(160, 160, 70), message="ambience/wind_house.wav",
      health="3", spawnflags="1", pitch="100")

# ------------------------------------------------------------------ player
# the game starts by the bed, looking across the room to the front windows
M.ent("info_player_start", origin=(200, 190, 37), angles="0 250 0")


def main():
    hdr = ("// Before the Thaw - btt_house (starting location)\n"
           "// Valve 220 .map. Generated by development/tools/build_house.py,\n"
           "// edit freely in TrenchBroom / J.A.C.K. / Hammer afterwards.\n")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="\n") as fp:
        fp.write(M.text(hdr))
    nb = sum(len(e.brushes) for e in M.entities)
    print("%s: %d entities, %d brushes" % (OUT, len(M.entities), nb))


if __name__ == "__main__":
    main()
