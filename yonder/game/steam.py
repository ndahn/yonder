import os
import re
from pathlib import Path


def get_steam_root() -> Path:
    """Find the steam install directory."""
    if os.name == "nt":
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "SteamPath")
        return Path(path)
    else:
        # common linux install locations
        candidates = [
            "~/.steam/steam",
            "~/.local/share/Steam",
            "~/.var/app/com.valvesoftware.Steam/data/Steam",  # flatpak
        ]
        for c in candidates:
            p = Path(c).expanduser().resolve()
            if p.is_dir():
                return p

        raise FileNotFoundError("steam install not found")


def get_steam_library_folders(steam_root: Path) -> list[Path]:
    """Parse libraryfolders.vdf to get all steam library paths."""
    vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
    content = vdf_path.read_text(encoding="utf-8")

    # matches "path"  "C:\\SteamLibrary" style lines
    paths = re.findall(r'"path"\s+"(.+?)"', content)
    return [Path(p.replace("\\\\", "\\")) for p in paths]


def find_game_folder(app_id: int) -> Path:
    """Locate an installed steam game's folder."""
    steam_root = get_steam_root()
    libraries = get_steam_library_folders(steam_root)

    for lib in libraries:
        manifest = lib / "steamapps" / f"appmanifest_{app_id}.acf"
        if manifest.is_file():
            content = manifest.read_text()
            match = re.search(r'"installdir"\s+"(.+?)"', content)
            if match:
                return Path(match.group(1))

    raise FileNotFoundError(f"Could not find game with app ID {app_id}")
