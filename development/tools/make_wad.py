#!/usr/bin/env python3
"""Pack PNG textures into a GoldSrc / Xash3D WAD3 file.

Each PNG becomes one miptex lump (type 0x43) with 4 mip levels and its own
256-colour palette, exactly like textures made with Wally / wadmaker.

Rules (same as GoldSrc):
  * file name (without .png) is the texture name, max 15 characters
  * width and height must be multiples of 16
  * names starting with '{' are masked textures: pure blue (0,0,255) in the
    PNG becomes palette index 255 (transparent)

Usage:
  python3 make_wad.py <png_dir> <out.wad>
  python3 make_wad.py            # defaults: textures_src/house -> game/textures/btt_house.wad
"""
import os
import struct
import sys
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEF_SRC = os.path.join(ROOT, "development", "textures_src", "house")
DEF_OUT = os.path.join(ROOT, "game", "textures", "btt_house.wad")


def quantize(img, masked):
    """Return (palette_bytes[768], [mip0..mip3 index bytes])."""
    img = img.convert("RGB")
    w, h = img.size
    if masked:
        # reserve index 255 for transparency
        px = img.load()
        mask = [[px[x, y] == (0, 0, 255) for x in range(w)] for y in range(h)]
        q = img.quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    else:
        mask = None
        q = img.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[:768]
    pal += [0] * (768 - len(pal))
    if masked:
        pal[765:768] = [0, 0, 255]
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(pal)
    mips = []
    for level in range(4):
        mw, mh = w >> level, h >> level
        if level == 0:
            src = img
        else:
            src = img.resize((mw, mh), Image.Resampling.BOX)
        qi = src.quantize(palette=pal_img, dither=Image.Dither.NONE)
        data = bytearray(qi.tobytes())
        if masked:
            # a mip pixel is transparent if any of its source pixels was
            step = 1 << level
            for y in range(mh):
                for x in range(mw):
                    if any(mask[y * step + j][x * step + i]
                           for j in range(step) for i in range(step)):
                        data[y * mw + x] = 255
                    elif data[y * mw + x] == 255:
                        data[y * mw + x] = 254
        mips.append(bytes(data))
    return bytes(pal), mips


def miptex_lump(name, img):
    w, h = img.size
    if w % 16 or h % 16:
        raise ValueError("%s: size %dx%d is not a multiple of 16" % (name, w, h))
    if len(name) > 15:
        raise ValueError("%s: texture name longer than 15 chars" % name)
    pal, mips = quantize(img, name.startswith("{"))
    header_size = 16 + 4 + 4 + 16
    offsets = []
    pos = header_size
    for m in mips:
        offsets.append(pos)
        pos += len(m)
    data = bytearray()
    data += name.encode("ascii").ljust(16, b"\0")
    data += struct.pack("<II", w, h)
    data += struct.pack("<4I", *offsets)
    for m in mips:
        data += m
    data += struct.pack("<H", 256)
    data += pal
    data += b"\0\0"  # pad
    while len(data) % 4:
        data += b"\0"
    return bytes(data)


def build_wad(src_dir, out_path):
    names = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(".png"))
    lumps = []
    for f in names:
        name = f[:-4]
        img = Image.open(os.path.join(src_dir, f))
        lumps.append((name, miptex_lump(name, img)))
    out = bytearray(b"WAD3" + struct.pack("<ii", len(lumps), 0))
    dirents = []
    for name, data in lumps:
        dirents.append((len(out), len(data), name))
        out += data
    dir_ofs = len(out)
    for pos, size, name in dirents:
        out += struct.pack("<iiibbh", pos, size, size, 0x43, 0, 0)
        out += name.encode("ascii").ljust(16, b"\0")
    struct.pack_into("<i", out, 8, dir_ofs)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as fp:
        fp.write(out)
    return len(lumps), len(out)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEF_SRC
    out = sys.argv[2] if len(sys.argv) > 2 else DEF_OUT
    n, size = build_wad(src, out)
    print("%s: %d textures, %d KB" % (out, n, size // 1024))


if __name__ == "__main__":
    main()
