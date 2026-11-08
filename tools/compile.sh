#!/usr/bin/env bash
# Compiles development/maps_src/<map>.map into game/maps/<map>.bsp
# usage: tools/compile.sh [mapname] [fast|full]      (default: btt_house full)
source "$(dirname "$0")/_common.sh"
MAP="${1:-btt_house}"
MODE="${2:-full}"
BIN="${SDHLT_DIR:-$TOOLS/sdhlt}"
[ -x "$BIN/sdHLCSG" ] || { echo "SDHLT not found in $BIN - run tools/build_tools.sh"; exit 1; }
WORK="$ROOT/development/build"
mkdir -p "$WORK" "$ROOT/game/maps"
cp "$ROOT/development/maps_src/$MAP.map" "$WORK/"
cp "$ROOT/game/textures/"*.wad "$BIN/sdhlt.wad" "$WORK/"
cd "$WORK"
if [ "$MODE" = fast ]; then VIS=-fast; RAD="-fast -bounce 2"; else VIS=-full; RAD="-extra -bounce 8 -smooth 50"; fi
"$BIN/sdHLCSG" -wadinclude btt_house -wadautodetect "$MAP"
"$BIN/sdHLBSP" "$MAP"
"$BIN/sdHLVIS" $VIS "$MAP"
"$BIN/sdHLRAD" $RAD -chop 32 -texchop 16 "$MAP"
cp "$MAP.bsp" "$ROOT/game/maps/"
echo "OK: game/maps/$MAP.bsp"
