

import os
import subprocess
import sys
from pathlib import Path

FLATPAK_ID = os.environ.get("FLATPAK_ID")
TOKENIZER_VENV_SUBDIR = "Tkonverter/tokenizer_venv"
FROZEN_WINDOWS_VENV_SUBDIR = "Tkonverter/tokenizer_venv"

def is_flatpak() -> bool:
    return bool(FLATPAK_ID)

def is_frozen_windows() -> bool:
    return getattr(sys, "frozen", False) is True and sys.platform == "win32"

def _get_frozen_windows_data_dir() -> Path | None:
    if not is_frozen_windows():
        return None
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local)
    return None

def get_frozen_windows_venv_root() -> Path | None:
    data_dir = _get_frozen_windows_data_dir()
    if not data_dir:
        return None
    return data_dir / FROZEN_WINDOWS_VENV_SUBDIR

def get_frozen_windows_venv_python() -> Path | None:
    venv_root = get_frozen_windows_venv_root()
    if not venv_root or not venv_root.is_dir():
        return None
    exe = venv_root / "Scripts" / "python.exe"
    return exe if exe.exists() else None

def get_frozen_windows_site_packages() -> Path | None:
    venv_root = get_frozen_windows_venv_root()
    if not venv_root or not venv_root.is_dir():
        return None
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = venv_root / "Lib" / "site-packages"
    if site_packages.is_dir():
        return site_packages
    return None

def ensure_frozen_windows_tokenizer_path() -> None:
    if not is_frozen_windows():
        return
    site_packages = get_frozen_windows_site_packages()
    if not site_packages:
        return
    path_str = str(site_packages)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

def setup_frozen_windows_hf_cache() -> None:
    if not is_frozen_windows():
        return
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return
    hf_home = os.path.join(local, "Tkonverter", "hf_cache")
    os.environ["HF_HOME"] = hf_home
    os.environ["TRANSFORMERS_CACHE"] = hf_home

def get_frozen_windows_system_python() -> str | None:
    for candidate in ("py", "python", "python3"):
        try:
            r = subprocess.run(
                [candidate, "-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode == 0 and r.stdout and r.stdout.strip():
                return r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None

def _get_flatpak_data_dir() -> Path | None:
    if not FLATPAK_ID:
        return None
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home)
    home = os.environ.get("HOME", "")
    if not home:
        return None
    return Path(home) / ".local" / "share"

def get_flatpak_venv_root() -> Path | None:
    data_dir = _get_flatpak_data_dir()
    if not data_dir:
        return None
    return data_dir / TOKENIZER_VENV_SUBDIR

def get_flatpak_venv_site_packages() -> Path | None:
    venv_root = get_flatpak_venv_root()
    if not venv_root or not venv_root.is_dir():
        return None
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = venv_root / "lib" / py_ver / "site-packages"
    if site_packages.is_dir():
        return site_packages
    return None

def get_flatpak_venv_python() -> Path | None:
    venv_root = get_flatpak_venv_root()
    if not venv_root:
        return None
    if sys.platform == "win32":
        exe = venv_root / "Scripts" / "python.exe"
    else:
        exe = venv_root / "bin" / "python"
    return exe if exe.exists() else None

def ensure_flatpak_tokenizer_path() -> None:
    if not FLATPAK_ID:
        return
    site_packages = get_flatpak_venv_site_packages()
    if not site_packages:
        return
    path_str = str(site_packages)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

def setup_flatpak_hf_cache() -> None:
    if not FLATPAK_ID:
        return
    cache_home = os.environ.get("XDG_CACHE_HOME")
    if not cache_home:
        home = os.environ.get("HOME", "")
        if home:
            cache_home = os.path.join(home, ".cache")
    if cache_home:
        hf_home = os.path.join(cache_home, "huggingface")
        os.environ["HF_HOME"] = hf_home
        os.environ["TRANSFORMERS_CACHE"] = hf_home
