#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_root"

version="$(awk -F= '/^version[[:space:]]*=/ { gsub(/[[:space:]]/, "", $2); print $2; exit }' buildozer.spec)"
pyinstaller --noconfirm --clean --onedir --name PixelChess \
    --add-data 'assets:assets' \
    --add-data 'chess_app/ui/theme.kv:chess_app/ui' \
    main.py
cp packaging/linux/README.txt dist/README.txt
cp packaging/linux/install.sh dist/install.sh
chmod +x dist/install.sh
mkdir -p Release
tar -czf "Release/PixelChess-${version}-linux-x86_64.tar.gz" \
    -C dist PixelChess README.txt install.sh
printf 'Created Release/PixelChess-%s-linux-x86_64.tar.gz\n' "$version"
