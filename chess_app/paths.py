"""Stable paths for bundled app resources, independent of the launch directory."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
UI_DIR = Path(__file__).resolve().parent / "ui"


def asset_path(*parts: str) -> Path:
    """Return an absolute path inside the bundled assets directory."""
    return ASSETS_DIR.joinpath(*parts)
