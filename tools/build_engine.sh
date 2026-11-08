#!/usr/bin/env bash
# Builds Xash3D FWGS (64-bit) into engine/ and the game code (HLSDK-portable)
# into game/dlls + game/cl_dlls.
# Debian/Ubuntu deps: git build-essential python3 cmake libsdl2-dev libfreetype-dev
#                     libfontconfig-dev libopus-dev libbz2-dev libvorbis-dev libopusfile-dev libogg-dev
source "$(dirname "$0")/_common.sh"
fetch "$XASH_URL" "$XASH_REF" "$SRC/xash3d-fwgs"
( cd "$SRC/xash3d-fwgs"
  python3 ./waf configure -T release -8 --gamedir=game
  python3 ./waf build
  python3 ./waf install --destdir="$ROOT/engine" )
fetch "$HLSDK_URL" "$HLSDK_REF" "$SRC/hlsdk-portable"
cmake -S "$SRC/hlsdk-portable" -B "$SRC/hlsdk-portable/build" -DCMAKE_BUILD_TYPE=Release \
      -D64BIT=ON -DGAMEDIR=game -DCMAKE_INSTALL_PREFIX="$ROOT"
cmake --build "$SRC/hlsdk-portable/build" --config Release --target install -j"$(nproc 2>/dev/null || echo 4)"
echo "engine in engine/, game libraries in game/dlls and game/cl_dlls"
