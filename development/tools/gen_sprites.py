#!/usr/bin/env python3
"""Before the Thaw - HUD sprite + sprites/hud.txt.

The HLSDK client code looks up a fixed set of HUD sprite names in
sprites/hud.txt (number_0, cross, suit_full, dmg_bio ...).  If the file or
a name is missing, parts of the HUD index arrays with -1, so we ship our
own minimal sheet: white glyphs on black, additive (the HUD tints them).

Writes game/sprites/btt_hud.spr (SPR v2, single frame) and game/sprites/hud.txt.
"""
import os
import struct
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "game", "sprites")

# 5x7 pixel digits
FONT = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
}

W, H = 256, 64
img = np.zeros((H, W), np.uint8)
regions = {}


def glyph(ch, x, y, s=3):
    for r, row in enumerate(FONT[ch]):
        for c, v in enumerate(row):
            if v == "1":
                img[y + r * s:y + (r + 1) * s, x + c * s:x + (c + 1) * s] = 255


# digits 0-9: 20x24 cells in the first row
for i in range(10):
    glyph(str(i), i * 20 + 2, 2)
    regions["number_%d" % i] = (i * 20, 0, 20, 24)
# divider
img[2:22, 201] = 200
regions["divider"] = (200, 0, 2, 24)
# cross (health) 24x24
img[8:16, 210:226] = 255
img[2:22, 214:222] = 255
regions["cross"] = (206, 0, 24, 24)
# suit / armour, flashlight, damage icons, buckets, selection: plain shapes
x = 0
for name, w, h in (("suit_empty", 40, 40), ("suit_full", 40, 40),
                   ("flash_empty", 32, 32), ("flash_full", 32, 32), ("flash_beam", 48, 32),
                   ("selection", 32, 32)):
    if name.endswith("full") or name == "flash_beam":
        img[24:24 + h, x:x + w] = 160
    else:
        img[24, x:x + w] = img[23 + h, x:x + w] = 160
        img[24:24 + h, x] = img[24:24 + h, x + w - 1] = 160
    regions[name] = (x, 24, w, h)
    x += w
for i, name in enumerate(["dmg_bio", "dmg_poison", "dmg_chem", "dmg_cold", "dmg_drown",
                          "dmg_burn", "dmg_gas", "dmg_rad", "dmg_shock"]):
    regions[name] = (x, 24, 8, 8)
for i in range(1, 6):
    regions["bucket%d" % i] = (0, 0, 20, 24)
for name in ("d_skull", "title_half", "title_life", "item_battery", "item_healthkit",
             "item_longjump", "train_back", "train_stop", "train_forward1",
             "train_forward2", "train_forward3", "number_slash"):
    regions[name] = (x, 24, 8, 8)


def write_spr(path):
    pal = bytearray()
    for i in range(256):
        pal += bytes((i, i, i))
    hdr = struct.pack("<4siiifiiifi", b"IDSP", 2, 2, 1,
                      float(np.hypot(W, H) / 2), W, H, 1, 0.0, 0)
    data = hdr + struct.pack("<H", 256) + pal
    data += struct.pack("<iiiii", 0, -W // 2, H // 2, W, H)
    data += img.tobytes()
    with open(path, "wb") as fp:
        fp.write(data)


def main():
    os.makedirs(OUT, exist_ok=True)
    write_spr(os.path.join(OUT, "btt_hud.spr"))
    lines = []
    for res in (320, 640):
        for name, (x, y, w, h) in regions.items():
            lines.append("%s\t%d\tbtt_hud\t%d\t%d\t%d\t%d" % (name, res, x, y, w, h))
    with open(os.path.join(OUT, "hud.txt"), "w", newline="\n") as fp:
        fp.write("%d\n" % len(lines))
        fp.write("\n".join(lines) + "\n")
    print("sprites: btt_hud.spr + hud.txt (%d entries)" % len(lines))


if __name__ == "__main__":
    main()
