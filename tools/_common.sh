# shared helpers for the *.sh scripts
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/tools"
SRC="$TOOLS/src"
# shellcheck disable=SC1091
source <(grep -E '^[A-Z_]+=' "$TOOLS/versions.txt")
fetch() { # fetch <url> <ref> <dir>
    if [ ! -d "$3/.git" ]; then
        git clone "$1" "$3"
    fi
    git -C "$3" fetch --tags origin
    git -C "$3" checkout -q "$2"
    git -C "$3" submodule update --init --recursive
}
