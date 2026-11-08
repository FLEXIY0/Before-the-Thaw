#!/usr/bin/env bash
# Regenerates every procedural asset + the map source, then checks the map.
# Only needed when you change the generators (Python 3 + Pillow + numpy).
# The .map is NOT regenerated unless you pass --map (that would overwrite
# changes made in the level editor).
source "$(dirname "$0")/_common.sh"
cd "$ROOT/development/tools"
python3 gen_textures.py
python3 make_wad.py
python3 gen_sounds.py
python3 gen_sprites.py
if [ "${1:-}" = --map ]; then python3 build_house.py; fi
python3 check_map.py "$ROOT/development/maps_src/btt_house.map" --wad "$ROOT/game/textures/btt_house.wad"
