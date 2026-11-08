#!/usr/bin/env bash
# Builds the SDHLT map compilers (sdHLCSG/sdHLBSP/sdHLVIS/sdHLRAD) into tools/sdhlt/
# Needs: git, cmake >= 3.20, a C++ compiler.
source "$(dirname "$0")/_common.sh"
fetch "$SDHLT_URL" "$SDHLT_REF" "$SRC/SDHLT"
cmake -S "$SRC/SDHLT" -B "$SRC/SDHLT/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$SRC/SDHLT/build" --config Release -j"$(nproc 2>/dev/null || echo 4)"
mkdir -p "$TOOLS/sdhlt"
for t in sdHLCSG sdHLBSP sdHLVIS sdHLRAD; do cp "$SRC/SDHLT/tools/$t" "$TOOLS/sdhlt/"; done
cp "$SRC/SDHLT/tools/sdhlt.wad" "$SRC/SDHLT/tools/sdhlt.fgd" "$TOOLS/sdhlt/"
echo "SDHLT ready in tools/sdhlt"
