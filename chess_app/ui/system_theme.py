"""Best-effort detection of the operating system's light/dark appearance."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def is_dark_mode() -> bool:
    override = os.environ.get("PIXEL_CHESS_THEME", "").lower()
    if override in {"dark", "light"}:
        return override == "dark"

    if sys.platform == "android":
        try:
            from jnius import autoclass

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            config = activity.getResources().getConfiguration()
            ui_mode = autoclass("android.content.res.Configuration").UI_MODE_NIGHT_MASK
            night = autoclass("android.content.res.Configuration").UI_MODE_NIGHT_YES
            return config.uiMode & ui_mode == night
        except Exception:
            pass
    elif sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            result = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                    capture_output=True, text=True, timeout=1)
            return result.stdout.strip().lower() == "dark"
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=1,
            )
            if result.returncode == 0 and result.stdout.strip():
                return "dark" in result.stdout.lower()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        try:
            kdeglobals = Path.home() / ".config" / "kdeglobals"
            for line in kdeglobals.read_text(errors="ignore").splitlines():
                if line.lower().startswith("colorscheme="):
                    return "dark" in line.split("=", 1)[1].lower()
        except OSError:
            pass
        gtk_theme = os.environ.get("GTK_THEME", "")
        if gtk_theme:
            return "dark" in gtk_theme.lower()

    return False
