#!/usr/bin/env bash
set -euo pipefail

bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_root="${XDG_DATA_HOME:-$HOME/.local/share}/pixel-chess"
app_dir="$install_root/PixelChess"
applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

mkdir -p "$install_root" "$applications_dir"
rm -rf "$app_dir"
cp -a "$bundle_dir/PixelChess" "$app_dir"
cat > "$applications_dir/pixel-chess.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Pixel Chess
Comment=Play chess against the computer or online
Exec=$app_dir/PixelChess
Icon=$app_dir/_internal/assets/pixelchess-icon.png
Terminal=false
Categories=Game;BoardGame;
EOF

printf 'Installed Pixel Chess for this user. Launch it from the applications menu.\n'
