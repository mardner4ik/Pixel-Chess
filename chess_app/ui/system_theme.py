"""Best-effort detection of the operating system's light/dark appearance."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def get_system_accent_color(dark: bool = False):
    """Return Android 12+'s current wallpaper-derived accent as RGBA, if available."""
    try:
        from kivy.utils import platform as kivy_platform
        if kivy_platform != "android" and sys.platform != "android":
            return None
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        resources = activity.getResources()
        color_name = "system_accent1_200" if dark else "system_accent1_600"
        color_id = resources.getIdentifier(color_name, "color", "android")
        if not color_id:
            return None
        color = int(resources.getColor(color_id)) & 0xFFFFFFFF
        return (((color >> 16) & 255) / 255, ((color >> 8) & 255) / 255,
                (color & 255) / 255, ((color >> 24) & 255) / 255)
    except Exception:
        return None


def is_dark_mode() -> bool:
    override = os.environ.get("PIXEL_CHESS_THEME", "").lower()
    if override in {"dark", "light"}:
        return override == "dark"

    try:
        from kivy.utils import platform as kivy_platform
    except Exception:
        kivy_platform = ""

    if kivy_platform == "android" or sys.platform == "android":
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
