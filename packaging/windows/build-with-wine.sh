#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
win_python="${PIXELCHESS_WIN_PYTHON:-C:\\Python311\\python.exe}"
inno_compiler="${PIXELCHESS_INNO_ISCC:-C:\\InnoSetup\\ISCC.exe}"
app_version="${APP_VERSION:-$(sed -n 's/^version = //p' "$project_root/buildozer.spec" | head -n 1)}"

if ! command -v wine >/dev/null || ! command -v winepath >/dev/null; then
    echo "Wine and winepath are required." >&2
    exit 1
fi
if [[ -z "$app_version" ]]; then
    echo "Could not read the app version from buildozer.spec." >&2
    exit 1
fi

cd "$project_root"
mkdir -p Release
wine "$win_python" -m pip install --upgrade pip
wine "$win_python" -m pip install "kivy[base]==2.3.1" "python-chess==1.999" pyinstaller
wine "$win_python" -m PyInstaller --noconfirm --clean --log-level WARN \
    --windowed --onedir --name PixelChess \
    --icon assets/pixelchess-icon.ico \
    --add-data "assets;assets" \
    --add-data "chess_app/ui/theme.kv;chess_app/ui" main.py

windows_iss="$(winepath -w "$project_root/packaging/windows/PixelChess.iss")"
windows_release="$(winepath -w "$project_root/Release")"
wine "$inno_compiler" "/DAppVersion=$app_version" "/O$windows_release" "$windows_iss"
