#!/usr/bin/env python3
"""Before the Thaw - blockout generator for the starting location (btt_house).

Writes development/maps_src/btt_house.map (Valve 220 format).

The .map is the real source of the level: open it in TrenchBroom / J.A.C.K. /
Hammer and keep working there.  This script only exists so the first
version is reproducible and the layout is documented in code.  Re-running it
OVERWRITES manual edits to the .map, so once you start editing by hand,
stop using it (or copy the map under a new name).

Layout (top view, X = east, Y = north, 1 unit ~ 2.5 cm):

  Y=352 +------------------+--------------+-----------------+-------------+
        | STORAGE          | KITCHEN      |                 | BEDROOM     |
        | (кладовая)       | washstand,   |   (kitchen win) | bed, chest, |
        | shelves, barrel  | fridge,      |                 | wardrobe,   |
  Y=208 +----[door]--------+ cupboards    +--curtain--+-----+ carpet      |
        | HALL (сени)      | STOVE (печь) |   nook    |[door]-------------+ Y=200
        | coats, felt      |              |  woodpile |                   |
        | boots, buckets,  +--------------+-----------+                   |
        | attic hatch      [padded door]   MAIN ROOM: table in the "red    |
        | ladder           |               corner", benches, sideboard,  |
  Y=0   +---[front door]---+--------------------------------------------- +
       X=0               X=160/176      X=256      X=352/360            X=528

The house faces the road (south, -Y). East windows look at the field,
north windows at the forest - the same geography as the environment concept
in development/docs/environment_concept.md.
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
          "fab_curtain", "stove_tile"):
    mk.TEX_SCALE[t] = 0.5
mk.TEX_SCALE["fab_rug"] = 0.5
mk.TEX_SCALE["snow"] = 2.0
mk.TEX_SCALE["log_ext"] = 1.0

NULL = "NULL"     # tool textures come from sdhlt.wad (compile time only)
ORIGIN = "ORIGIN"
SKY = "sky"

# ------------------------------------------------------------------ dimensions
H = 96            # ceiling height in the warm part of the house
FLOOR_COLD = -8   # hall and storage are one step lower (cold annex)
GROUND = -40      # outside ground level: the house stands on a log base
CEIL_TOP = 112

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


# ------------------------------------------------------------------ shell
# floors (slabs reach down to the ground so there are no hidden voids)
W.add(box(176, 0, GROUND, 528, 352, 0, "floor_paint", nz=NULL))           # warm part
W.add(box(0, 0, GROUND, 160, 352, FLOOR_COLD, "floor_raw", nz=NULL))       # hall + storage
# ceiling slab over the whole house
W.add(box(-16, -16, H, 544, 368, CEIL_TOP, "log_ext", nz="ceiling", pz=NULL))

LOG, LOG_OLD, LOG_EXT, WP = "log_wall", "log_wall_old", "log_ext", "wallpaper"
WIN_SILL, WIN_TOP = 40, 80

# exterior walls, split per room so every room gets its own inner texture
# south wall (Y -16..0): hall (front door + nothing else), main (2 windows)
W.add(wall("x", -16, 0, -16, 160, GROUND, H, LOG_EXT, LOG_OLD,
           holes=[(56, 104, FLOOR_COLD, 72)], end_tex=LOG_EXT))
W.add(wall("x", -16, 0, 160, 544, GROUND, H, LOG_EXT, LOG,
           holes=[(216, 256, WIN_SILL, WIN_TOP), (432, 472, WIN_SILL, WIN_TOP)],
           end_tex=LOG_EXT))
# north wall (Y 352..368): storage | kitchen (window) | bedroom (window)
W.add(wall("x", 352, 368, -16, 176, GROUND, H, LOG_OLD, LOG_EXT, end_tex=LOG_EXT))
W.add(wall("x", 352, 368, 176, 356, GROUND, H, LOG, LOG_EXT,
           holes=[(296, 336, 44, WIN_TOP)], end_tex=LOG_EXT))
W.add(wall("x", 352, 368, 356, 544, GROUND, H, WP, LOG_EXT,
           holes=[(392, 432, WIN_SILL, WIN_TOP)], end_tex=LOG_EXT))
# west wall (X -16..0): hall window
W.add(wall("y", -16, 0, 0, 352, GROUND, H, LOG_EXT, LOG_OLD,
           holes=[(120, 148, 36, 64)], end_tex=LOG_EXT))
# east wall (X 528..544): main room window | bedroom window
W.add(wall("y", 528, 544, 0, 204, GROUND, H, LOG, LOG_EXT,
           holes=[(112, 152, WIN_SILL, WIN_TOP)], end_tex=LOG_EXT))
W.add(wall("y", 528, 544, 204, 352, GROUND, H, WP, LOG_EXT,
           holes=[(216, 248, WIN_SILL, WIN_TOP)], end_tex=LOG_EXT))

# inner log wall between the cold annex and the warm part (X 160..176)
W.add(wall("y", 160, 176, 0, 208, FLOOR_COLD, H, LOG_OLD, LOG,
           holes=[(40, 88, 0, 80)], end_tex=LOG, bottom="floor_raw"))
W.add(wall("y", 160, 176, 208, 352, FLOOR_COLD, H, LOG_OLD, LOG, end_tex=LOG,
           bottom="floor_raw"))
# hall / storage plank partition (Y 200..208)
W.add(wall("x", 200, 208, 0, 160, FLOOR_COLD, H, "boards_raw", "boards_raw",
           holes=[(104, 144, FLOOR_COLD, 72)], end_tex="boards_raw"))
# bedroom partitions (painted boards on the main side, wallpaper inside)
BP = "boards_paint"
W.add(wall("x", 200, 208, 352, 528, 0, H, BP, WP, holes=[(368, 408, 0, 80)], end_tex=BP))
W.add(wall("y", 352, 360, 208, 352, 0, H, BP, WP, end_tex=BP))
# kitchen partition next to the stove, with a curtained opening (304..352)
W.add(box(256, 256, 0, 304, 264, H, BP))

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


window("x", -16, 0, 216, 256, WIN_SILL, WIN_TOP, +1, "win_main_s1")
window("x", -16, 0, 432, 472, WIN_SILL, WIN_TOP, +1, "win_main_s2")
window("y", 528, 544, 112, 152, WIN_SILL, WIN_TOP, -1, "win_main_e")
window("x", 352, 368, 296, 336, 44, WIN_TOP, -1, "win_kitchen")
window("x", 352, 368, 392, 432, WIN_SILL, WIN_TOP, -1, "win_bed_n")
window("y", 528, 544, 216, 248, WIN_SILL, WIN_TOP, -1, "win_bed_e")
window("y", -16, 0, 120, 148, 36, 64, +1, "win_hall", curtains=False)

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


# warm padded door hall -> main room. Hinge at the north jamb, opens into the room
door("door_main", (168, 87, 0, 80), (166, 41, 1, 170, 87, 79), "door_padded",
     swing=+1, extra=handle_x(166, 170, 50, 40))
# hall -> storage, plank door, opens into the storage
door("door_store", (105, 204, -8, 72), (105, 202, -8, 143, 206, 71), "door_boards",
     swing=+1, extra=handle_y(202, 206, 136, 32))
# main room -> bedroom
door("door_bed", (369, 204, 0, 80), (369, 202, 0, 407, 206, 79), "door_boards",
     swing=+1, extra=handle_y(202, 206, 400, 40))
# front door: locked (its master never fires) - rattles the latch when pushed
front = door("door_front", (58, -8, -8, 72), (58, -10, -8, 102, -6, 71), "door_ext",
             use=False, master="btt_front_unlocked", locked_sound="12",
             extra=handle_y(-10, -6, 94, 32))
front.kv["spawnflags"] = "0"

# ------------------------------------------------------------------ RUSSIAN STOVE
# body 80 x 88, lime-washed, mouth (чело) facing the kitchen (north)
SX0, SY0, SX1, SY1, SZ = 176, 168, 256, 256, 64
stove = []
stove.append(box(SX0, SY0, 0, SX1, SY1, 8, "brick_old"))                          # base
stove.append(box(SX0, SY0, 8, SX1, SY1 - 16, SZ, "whitewash", py="stove_soot"))  # body behind mouth
stove.append(box(SX0, SY1 - 16, 8, 196, SY1, SZ, "whitewash"))                    # left of mouth
stove.append(box(236, SY1 - 16, 8, SX1, SY1, SZ, "whitewash"))                    # right of mouth
stove.append(box(196, SY1 - 16, 8, 236, SY1, 28, "whitewash", pz="stove_soot"))   # hearth floor
stove.append(box(196, SY1 - 16, 52, 236, SY1, SZ, "whitewash", nz="stove_soot"))  # mouth lintel
stove.append(box(SX0, SY0, SZ, SX1, SY1, SZ + 4, "whitewash", pz="whitewash"))    # top (лежанка)
# chimney to the ceiling and the smoke hood above the mouth
stove.append(box(184, 176, SZ + 4, 224, 216, H, "whitewash"))
stove.append(box(192, SY1 - 20, SZ + 4, 240, SY1, 84, "whitewash", nz="stove_soot"))
# hearth ledge (шесток) in front of the mouth
stove.append(box(192, SY1, 24, 240, SY1 + 6, 28, "whitewash", pz="stove_soot"))
# small cooking firebox with cast-iron plate on the east side
stove.append(box(SX1, 184, 0, SX1 + 20, 232, 40, "whitewash"))
stove.append(box(SX1 + 1, 192, 40, SX1 + 19, 224, 41, "stove_tile", pz=fit("stove_tile")))
stove.append(box(SX1 + 20, 200, 8, SX1 + 21, 216, 24, "metal_dark", px=fit("iron_door")))
detail(*stove)
# iron damper (заслонка) leaning beside the mouth, cast-iron pot on the ledge
detail(box(238, SY1, 2, 252, SY1 + 2, 30, "metal_dark", py=fit("iron_door")),
       cyl(210, SY1 + 3, 5, 28, 36, "metal_dark", top="stove_soot"),
       cyl(225, SY1 + 3, 4, 28, 33, "metal_rust"))
# ухват / кочерга - stove tools leaning in the corner by the stove
detail(box(250, SY1 + 8, 0, 252, SY1 + 10, 70, "wood_light"),
       box(246, SY1 + 6, 66, 256, SY1 + 12, 68, "metal_dark"),
       box(253, SY1 + 9, 0, 255, SY1 + 11, 64, "wood_light"),
       box(252, SY1 + 8, 0, 256, SY1 + 12, 3, "metal_dark"))
# warm glow and fire sound
light(216, SY1 - 8, 38, (255, 116, 40), 45)
M.ent("ambient_generic", origin=(216, 250, 34), message="ambience/stove_fire.wav",
      health="4", spawnflags="2", pitch="100")

# firewood stacked in the nook next to the stove (birch logs)
logs = []
for i, (cy, cz) in enumerate([(240, 5), (249, 5), (244, 13)]):
    for k, x0 in enumerate((262, 300)):
        logs.append(prism(mk.ngon(cy, cz, 5, 6), x0, x0 + 34, "x", side="birch_bark",
                          top=fit("log_end"), bottom=fit("log_end")))
detail(*logs)

# ------------------------------------------------------------------ KITCHEN (бабий кут)
kitchen = []
# low cupboards along the north wall + worktop
kitchen.append(box(260, 330, 0, 348, 352, 34, "wood_blue", pz="wood_light"))
kitchen.append(box(258, 326, 34, 350, 352, 37, "wood_light"))
for x in (282, 304, 326):  # cupboard door seams
    kitchen.append(box(x, 329, 4, x + 1, 330, 32, "wood_dark"))
# enamel bowl, pot, kettle and a bread board on the worktop
kitchen.append(cyl(272, 340, 7, 37, 41, "enamel", top="enamel"))
kitchen.append(cyl(292, 340, 5, 37, 46, "enamel_blue", top="metal_dark"))
kitchen.append(cyl(338, 340, 5, 37, 44, "metal_zinc", top="metal_dark"))
kitchen.append(box(337, 336, 44, 340, 337, 46, "metal_dark"))                  # kettle lid knob
kitchen.append(box(314, 334, 37, 330, 346, 38, "wood_light"))
# open dish shelf on the north wall above the stove side
kitchen.append(box(212, 340, 52, 256, 352, 54, "wood_light"))
kitchen.append(box(212, 350, 54, 256, 352, 74, "wood_light", ny=fit("crockery")))
kitchen.append(box(212, 340, 74, 256, 352, 76, "wood_light"))
# washstand (рукомойник): cabinet, basin, wall tank, slop bucket
kitchen.append(box(176, 290, 0, 200, 322, 30, "wood_blue", pz="enamel"))
kitchen.append(box(180, 294, 30, 196, 318, 33, "enamel"))
kitchen.append(box(176, 298, 52, 186, 314, 68, "metal_zinc"))
kitchen.append(box(185, 305, 46, 188, 307, 52, "metal_dark"))                  # push valve
kitchen.append(box(176, 288, 34, 178, 324, 50, "enamel"))                      # splash board
kitchen.append(box(176, 312, 72, 177, 324, 96, "wood_white", px=fit("fab_towel")))
# old fridge in the corner (round-shouldered enamel box)
kitchen.append(box(176, 326, 0, 204, 352, 60, "enamel", px=Tex("enamel", s=1.0)))
kitchen.append(box(204, 330, 30, 206, 334, 44, "metal_dark"))                  # handle
kitchen.append(box(178, 328, 60, 202, 350, 62, "enamel"))
# stool
kitchen.append(box(220, 290, 18, 236, 306, 20, "wood_light"))
for (x, y) in ((221, 291), (233, 291), (221, 303), (233, 303)):
    kitchen.append(box(x, y, 0, x + 2, y + 2, 18, "wood_light"))
detail(*kitchen)
# curtain in the kitchen opening (non-solid, gathered to one side)
M.ent("func_illusionary", rendermode="0").add(
    box(304, 258, 4, 318, 262, 92, "fab_curtain"),
    box(304, 257, 92, 352, 263, 96, "wood_dark"))
light(296, 300, 84, (255, 200, 140), 90, name="light_kitchen", dark=True)
M.ent("ambient_generic", origin=(208, 340, 40), message="ambience/fridge_hum.wav",
      health="2", spawnflags="2", pitch="100")

# ------------------------------------------------------------------ MAIN ROOM
main = []
# central ceiling beam (матица)
main.append(box(176, 92, 86, 528, 108, H, "beam"))
# benches fixed to the walls (лавки)
main.append(box(368, 0, 16, 528, 14, 19, "wood_light"))
main.append(box(514, 14, 16, 528, 108, 19, "wood_light"))
for x in (372, 448, 520):
    main.append(box(x, 2, 0, x + 4, 12, 16, "wood_light"))
for y in (40, 100):
    main.append(box(516, y, 0, 526, y + 4, 16, "wood_light"))
# table in the red corner
main.append(box(412, 22, 28, 500, 74, 31, "wood_light"))
for (x, y) in ((416, 26), (494, 26), (416, 68), (494, 68)):
    main.append(box(x, y, 0, x + 3, y + 3, 28, "wood_light"))
main.append(box(416, 26, 22, 497, 28, 26, "wood_light"))
main.append(box(416, 68, 22, 497, 70, 26, "wood_light"))
# oilcloth on the table + bread box, newspapers, a glass and a mug
main.append(box(418, 26, 31, 494, 70, 32, "fab_curtain"))
main.append(box(470, 32, 32, 488, 46, 42, "wood_dark"))
main.append(box(428, 50, 32, 446, 62, 34, "paper", pz=fit("paper")))
main.append(cyl(456, 58, 2, 32, 37, "glass_frost"))
main.append(cyl(440, 36, 2, 32, 36, "enamel_blue"))
# two chairs
for (cx, cy, back) in ((394, 40, "w"), (448, 80, "n")):
    main.append(box(cx, cy, 16, cx + 16, cy + 16, 18, "wood_dark"))
    for (dx, dy) in ((0, 0), (14, 0), (0, 14), (14, 14)):
        main.append(box(cx + dx, cy + dy, 0, cx + dx + 2, cy + dy + 2, 16, "wood_dark"))
    if back == "w":
        main.append(box(cx, cy, 18, cx + 2, cy + 16, 40, "wood_dark"))
    else:
        main.append(box(cx, cy + 14, 18, cx + 16, cy + 16, 40, "wood_dark"))
# corner shelf (божница) with an icon and an embroidered towel
main.append(prism([(504, 0), (528, 0), (528, 24)], 74, 76, "z", side="wood_dark"))
main.append(prism([(511, 18), (522, 7), (524, 9), (513, 20)], 76, 92, "z",
                  side="wood_dark", sides=[fit("icon"), "wood_dark", "wood_dark", "wood_dark"]))
main.append(prism([(506, 22), (524, 4), (525, 5), (507, 23)], 50, 74, "z",
                  side="fab_towel", sides=[fit("fab_towel"), "fab_towel", "fab_towel", "fab_towel"]))
# sideboard (сервант): cabinet, glazed dish section, top
main.append(box(296, 0, 0, 360, 22, 32, "wood_dark"))
main.append(box(298, 22, 4, 327, 23, 30, "wood_dark"))
main.append(box(329, 22, 4, 358, 23, 30, "wood_dark"))
main.append(box(300, 0, 32, 356, 16, 62, "wood_dark", py=fit("crockery")))
main.append(box(296, 0, 62, 360, 18, 64, "wood_dark"))
main.append(box(298, 0, 0, 358, 22, 2, "wood_dark"))
# books on top of the sideboard
main.append(box(334, 2, 64, 356, 12, 75, "wood_dark", py=fit("books")))
# wall calendar next to the sideboard
main.append(box(272, 0, 48, 288, 1, 72, "paper", py=fit("calendar")))
# old CRT TV on a stand + knitted doily
main.append(box(470, 172, 0, 504, 198, 2, "wood_dark"))
for (x, y) in ((471, 173), (501, 173), (471, 195), (501, 195)):
    main.append(box(x, y, 2, x + 2, y + 2, 22, "wood_dark"))
main.append(box(468, 170, 22, 506, 200, 24, "wood_dark"))
main.append(box(472, 176, 24, 502, 200, 50, "wood_dark", ny=fit("tv_front")))
main.append(box(478, 182, 50, 496, 196, 51, "fab_pillow"))
main.append(box(486, 188, 51, 488, 190, 64, "metal_dark"))                    # antenna
# family photos above the TV
main.append(box(424, 198, 52, 456, 200, 76, "wood_dark", ny=fit("photos")))
# phone table by the hall door with a rotary telephone
main.append(box(178, 100, 26, 198, 118, 28, "wood_dark"))
for (x, y) in ((179, 101), (195, 101), (179, 115), (195, 115)):
    main.append(box(x, y, 0, x + 2, y + 2, 26, "wood_dark"))
main.append(box(184, 104, 28, 194, 114, 32, "phone_side", pz=fit("phone_top")))
main.append(box(183, 103, 32, 186, 115, 34, "phone_side"))                     # handset
main.append(box(176, 108, 10, 178, 109, 30, "metal_dark"))                     # wire
# woven runner from the hall door into the room
main.append(box(180, 50, 0, 400, 78, 1, "fab_rug"))
# lamp with an orange fabric shade hanging from the beam
main.append(box(351, 99, 78, 353, 101, 86, "metal_dark"))
main.append(prism(mk.ngon(352, 100, 12, 8), 70, 78, "z", side="fab_shade", bottom="fab_shade"))
main.append(cyl(352, 100, 3, 66, 70, "bulb"))
detail(*main)
light(352, 100, 62, (255, 190, 120), 150, name="light_main")

# ходики - wall clock with pendulum and chain weights on the west wall
detail(box(176, 120, 54, 182, 136, 78, "wood_dark", px=fit("clock_face")),
       box(176, 118, 76, 183, 138, 80, "wood_dark"),
       box(181, 123, 30, 182, 124, 54, "metal_dark"),
       box(181, 131, 38, 182, 132, 54, "metal_dark"),
       box(180, 122, 24, 183, 125, 30, "metal_dark"),
       box(180, 130, 32, 183, 133, 38, "metal_dark"))
M.ent("func_pendulum", speed="38", distance="20", spawnflags="73",
      angles="0 0 -10", rendermode="0").add(
    box(182, 127, 36, 183, 129, 54, "metal_dark"),
    box(182, 124, 33, 184, 132, 39, "metal_rust"),
    box(181, 126, 52, 185, 130, 56, ORIGIN))
M.ent("ambient_generic", origin=(184, 128, 64), message="ambience/clock_tick.wav",
      health="5", spawnflags="2", pitch="100")

# radio on the sideboard - press USE to switch it on/off
radio = M.ent("func_button", target="radio_snd", spawnflags="1", sounds="14",
              wait="0.5", delay="0")
radio.add(box(302, 2, 64, 330, 14, 78, "wood_dark", py=fit("radio_front")))
M.ent("ambient_generic", targetname="radio_snd", origin=(316, 20, 70),
      message="ambience/radio_static.wav", health="5", spawnflags="20", pitch="100")
# telephone: picking it up plays the dial tone once
phone = M.ent("func_button", target="phone_snd", spawnflags="1", sounds="0", wait="3")
phone.add(box(184, 104, 32, 194, 114, 33, "phone_side", pz=fit("phone_top")))
M.ent("ambient_generic", targetname="phone_snd", origin=(190, 110, 36),
      message="ambience/phone_dial.wav", health="5", spawnflags="50", pitch="100")


def switch(name, x0, y0, z0, x1, y1, z1, face):
    b = M.ent("func_button", target=name, spawnflags="1", sounds="14", wait="0.5")
    b.add(box(x0, y0, z0, x1, y1, z1, "switch", **{face: fit("switch")}))


switch("light_main", 176, 94, 50, 177, 100, 56, "px")        # by the padded door
switch("light_kitchen", 350, 264, 50, 352, 270, 56, "nx")    # kitchen opening
switch("light_bed", 410, 208, 50, 416, 209, 56, "py")        # inside the bedroom
switch("light_hall", 159, 92, 50, 160, 98, 56, "nx")         # hall side of the door
switch("light_store", 146, 199, 50, 152, 200, 56, "ny")      # next to the storage door

# ------------------------------------------------------------------ BEDROOM
bed = []
# iron bed with nickel knobs, patchwork quilt and a pyramid of pillows
BX0, BY0, BX1, BY1 = 482, 258, 524, 346
for (x, y, top) in ((BX0, BY0, 32), (BX1 - 3, BY0, 32), (BX0, BY1 - 3, 44), (BX1 - 3, BY1 - 3, 44)):
    bed.append(box(x, y, 0, x + 3, y + 3, top, "metal_dark"))
    bed.append(box(x - 1, y - 1, top, x + 4, y + 4, top + 3, "metal_zinc"))
bed.append(box(BX0 + 3, BY1 - 2, 20, BX1 - 3, BY1 - 1, 42, "metal_dark"))       # head grille
for x in range(BX0 + 7, BX1 - 3, 6):
    bed.append(box(x, BY1 - 3, 22, x + 1, BY1, 40, "metal_dark"))
bed.append(box(BX0 + 3, BY0, 20, BX1 - 3, BY0 + 1, 30, "metal_dark"))           # foot rail
bed.append(box(BX0 + 1, BY0 + 1, 12, BX1 - 1, BY1 - 1, 16, "metal_dark"))       # spring frame
bed.append(box(BX0 + 2, BY0 + 2, 16, BX1 - 2, BY1 - 2, 24, "fab_patch"))        # mattress + quilt
bed.append(box(BX0 + 1, BY0 + 1, 6, BX1 - 1, BY1 - 1, 16, "fab_patch"))         # quilt hanging down
bed.append(box(BX0 + 6, BY1 - 18, 24, BX1 - 6, BY1 - 4, 31, "fab_pillow"))
bed.append(box(BX0 + 9, BY1 - 15, 31, BX1 - 9, BY1 - 6, 36, "fab_pillow"))
bed.append(box(BX0 + 12, BY1 - 13, 36, BX1 - 12, BY1 - 8, 39, "fab_pillow"))
# carpet on the wall over the bed
bed.append(box(526, 262, 30, 528, 340, 82, "wall_carpet", nx=fit("wall_carpet")))
# nightstand with books and an alarm clock
bed.append(box(452, 322, 0, 476, 348, 26, "wood_dark"))
bed.append(box(455, 321, 4, 473, 322, 22, "wood_dark"))
bed.append(box(456, 328, 26, 470, 340, 30, "books", pz="wood_dark"))
bed.append(box(458, 342, 26, 466, 346, 34, "metal_dark", ny=fit("clock_face")))
# wardrobe against the partition
bed.append(box(362, 278, 0, 388, 338, 88, "wood_dark"))
bed.append(box(388, 280, 4, 389, 307, 84, "wood_dark"))
bed.append(box(388, 309, 4, 389, 336, 84, "wood_dark"))
bed.append(box(389, 302, 40, 390, 304, 48, "handle"))
bed.append(box(389, 312, 40, 390, 314, 48, "handle"))
bed.append(box(366, 300, 88, 384, 322, 94, "cardboard"))                       # box on top
# chest (сундук) under the north window, folded clothes on top
bed.append(box(380, 326, 0, 428, 350, 20, "wood_dark"))
bed.append(box(379, 325, 20, 429, 351, 23, "wood_dark"))
for x in (388, 418):
    bed.append(box(x, 324, 0, x + 3, 352, 23, "metal_dark"))
bed.append(box(386, 330, 23, 408, 346, 28, "fab_quilted"))
bed.append(box(410, 332, 23, 424, 346, 26, "fab_blanket"))
# chair with an old padded jacket thrown over it
bed.append(box(420, 228, 16, 436, 244, 18, "wood_dark"))
for (dx, dy) in ((0, 0), (14, 0), (0, 14), (14, 14)):
    bed.append(box(420 + dx, 228 + dy, 0, 422 + dx, 230 + dy, 16, "wood_dark"))
bed.append(box(420, 242, 18, 436, 244, 40, "wood_dark"))
bed.append(box(419, 236, 18, 437, 246, 42, "fab_quilted"))
bed.append(box(419, 226, 10, 421, 246, 18, "fab_quilted"))
# small rag rug by the bed
bed.append(box(440, 270, 0, 478, 330, 1, "fab_rug"))
# bare bulb on a cord
bed.append(box(443, 279, 84, 445, 281, H, "metal_dark"))
bed.append(cyl(444, 280, 3, 79, 84, "bulb"))
detail(*bed)
light(444, 280, 76, (255, 196, 132), 95, name="light_bed")

# ------------------------------------------------------------------ HALL (сени)
hall = []
F = FLOOR_COLD
# coat board with hooks on the partition, coats, padded jacket, scarf
hall.append(box(12, 196, 60, 100, 200, 64, "wood_dark"))
hall.append(box(18, 186, 22, 36, 196, 62, "fab_quilted"))
hall.append(box(42, 188, 18, 62, 196, 62, "fab_coat"))
hall.append(box(66, 190, 30, 80, 196, 62, "fab_blanket"))
hall.append(box(84, 192, 52, 96, 196, 64, "fab_felt"))                         # fur hat
# felt boots (валенки) and rubber galoshes on the floor
for x in (20, 28, 46, 54):
    hall.append(box(x, 184, F, x + 6, 194, F + 4, "fab_felt"))
    hall.append(box(x, 189, F + 4, x + 6, 194, F + 18, "fab_felt"))
hall.append(box(66, 182, F, 72, 194, F + 4, "metal_dark"))
hall.append(box(74, 182, F, 80, 194, F + 4, "metal_dark"))
# bench along the west wall, two water buckets and a ladle
hall.append(box(0, 20, F + 16, 16, 104, F + 19, "wood_light"))
for y in (24, 96):
    hall.append(box(2, y, F, 14, y + 4, F + 16, "wood_light"))
hall.append(cyl(8, 40, 7, F + 19, F + 33, "metal_zinc", top="glass_frost"))
hall.append(cyl(8, 60, 7, F + 19, F + 33, "metal_zinc", top="metal_dark"))
hall.append(box(6, 38, F + 33, 9, 46, F + 34, "enamel_blue"))
# broom in the corner by the front door
hall.append(box(146, 4, F + 12, 148, 6, F + 50, "wood_light"))
hall.append(box(144, 2, F, 150, 8, F + 12, "burlap"))
# ladder to the attic hatch (future: attic location)
for y in (128, 156):
    hall.append(box(150, y, F, 154, y + 3, H, "wood_light"))
for z in range(F + 12, H - 8, 14):
    hall.append(box(150, 131, z, 154, 156, z + 2, "wood_light"))
hall.append(box(110, 124, H - 2, 156, 164, H, "door_boards"))                  # closed hatch
hall.append(box(108, 122, H - 4, 158, 124, H, "beam"))
hall.append(box(108, 164, H - 4, 158, 166, H, "beam"))
# two beams under the ceiling
hall.append(box(0, 60, H - 8, 160, 72, H, "beam"))
hall.append(box(0, 268, H - 8, 160, 280, H, "beam"))
detail(*hall)
light(70, 100, 84, (255, 216, 176), 60, name="light_hall")

# ------------------------------------------------------------------ STORAGE (кладовая)
st = []
# shelving along the north wall with preserves, tins and a kerosene lamp
for x in (8, 78, 148):
    st.append(box(x, 328, F, x + 4, 352, H, "wood_light"))
for z in (F + 20, F + 48, F + 76):
    st.append(box(8, 328, z, 152, 352, z + 2, "wood_light"))
st.append(box(12, 350, F + 22, 78, 352, F + 46, "wood_light", ny=fit("jars")))
st.append(box(82, 350, F + 22, 148, 352, F + 46, "wood_light", ny=fit("jars")))
st.append(box(12, 336, F + 50, 40, 348, F + 64, "cardboard"))
st.append(box(84, 340, F + 50, 108, 350, F + 62, "books", ny=fit("books")))
st.append(cyl(126, 342, 4, F + 50, F + 60, "glass_frost", top="metal_dark"))  # kerosene lamp
st.append(cyl(126, 342, 5, F + 60, F + 62, "metal_rust"))
# sacks of potatoes / flour, boxes, a barrel of sauerkraut
st.append(box(16, 300, F, 40, 322, F + 22, "burlap"))
st.append(box(20, 302, F + 22, 38, 320, F + 30, "burlap"))
st.append(box(44, 304, F, 66, 324, F + 18, "burlap"))
st.append(box(110, 290, F, 140, 320, F + 20, "cardboard"))
st.append(box(114, 296, F + 20, 136, 318, F + 36, "cardboard"))
st.append(cyl(126, 240, 12, F, F + 30, "wood_light", top="wood_dark", n=10))
st.append(cyl(126, 240, 13, F + 4, F + 7, "metal_rust", n=10))
st.append(cyl(126, 240, 13, F + 22, F + 25, "metal_rust", n=10))
# tools on the west wall: saw, scythe blade, and skis / shovel leaning
st.append(box(0, 230, 40, 2, 270, 52, "metal_zinc"))
st.append(box(0, 226, 42, 3, 232, 50, "wood_light"))
st.append(box(0, 280, 66, 2, 330, 68, "wood_light"))
st.append(box(0, 296, 54, 2, 330, 58, "metal_dark"))
for y in (216, 222):
    st.append(box(4, y, F, 6, y + 4, F + 80, "wood_light"))
st.append(box(10, 214, F, 12, 216, F + 64, "wood_light"))
st.append(box(8, 212, F, 14, 218, F + 12, "metal_rust"))
detail(*st)
light(80, 270, 84, (255, 210, 160), 55, name="light_store", dark=True)

# ------------------------------------------------------------------ OUTSIDE (only seen from the windows)
SK0, SK1 = (-512, -512, GROUND - 24), (1040, 864, 320)
x0, y0, z0 = SK0
x1, y1, z1 = SK1
W.add(box(x0, y0, z0, x1, y1, GROUND, "snow", nz=NULL))                 # ground
W.add(box(x0 - 16, y0 - 16, z0, x0, y1 + 16, z1 + 16, SKY))          # sky walls
W.add(box(x1, y0 - 16, z0, x1 + 16, y1 + 16, z1 + 16, SKY))
W.add(box(x0, y0 - 16, z0, x1, y0, z1 + 16, SKY))
W.add(box(x0, y1, z0, x1, y1 + 16, z1 + 16, SKY))
W.add(box(x0, y0, z1, x1, y1, z1 + 16, SKY))
# snow banks against the house and an old fence along the road (south)
outside = [box(-32, -40, GROUND, 560, -16, GROUND + 6, "snow"),
           box(544, -32, GROUND, 576, 384, GROUND + 8, "snow"),
           box(-32, 368, GROUND, 560, 400, GROUND + 10, "snow")]
for x in range(-160, 760, 72):
    outside.append(box(x, -228, GROUND, x + 6, -222, GROUND + 52, "boards_raw"))
outside.append(box(-160, -226, GROUND + 16, 766, -224, GROUND + 22, "boards_raw"))
outside.append(box(-160, -226, GROUND + 38, 766, -224, GROUND + 44, "boards_raw"))
for y in range(-220, 640, 80):  # east fence towards the field
    outside.append(box(760, y, GROUND, 766, y + 6, GROUND + 52, "boards_raw"))
outside.append(box(762, -220, GROUND + 30, 764, 646, GROUND + 36, "boards_raw"))
detail(*outside)
M.ent("light_environment", angles="0 215 0", pitch="-60",
      _light="168 178 196 60", _diffuse_light="170 184 205 90")
M.ent("ambient_generic", origin=(270, 180, 70), message="ambience/wind_house.wav",
      health="3", spawnflags="1", pitch="100")

# ------------------------------------------------------------------ player
# the game starts in the bedroom, facing the door to the main room
M.ent("info_player_start", origin=(436, 300, 37), angles="0 235 0")


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
