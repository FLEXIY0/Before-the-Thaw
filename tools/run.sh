#!/usr/bin/env bash
# Starts Before the Thaw. Extra arguments go to the engine (e.g. -windowed -width 1280 -height 720)
source "$(dirname "$0")/_common.sh"
ENGINE="$ROOT/engine/xash3d"
[ -x "$ENGINE" ] || { echo "engine not found - run tools/build_engine.sh"; exit 1; }
export XASH3D_BASEDIR="$ROOT"
[ -f "$ROOT/engine/extras.pk3" ] && export XASH3D_EXTRAS_PAK1="$ROOT/engine/extras.pk3"
cd "$ROOT"
exec "$ENGINE" -game game -console +map btt_house "$@"
