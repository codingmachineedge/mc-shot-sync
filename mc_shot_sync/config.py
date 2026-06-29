"""Configuration and Minecraft screenshot-folder detection (cross-platform)."""
from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


def config_dir() -> Path:
    """Per-OS config directory for mc-shot-sync."""
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "mc-shot-sync"
    # macOS + Linux: respect XDG, else ~/.config
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "mc-shot-sync"


CONFIG_PATH = config_dir() / "config.json"


def _candidate_screenshot_dirs() -> List[Path]:
    """Common Minecraft screenshot locations across vanilla + popular launchers."""
    home = Path.home()
    cands: List[Path] = []
    system = platform.system()

    if system == "Windows":
        appdata = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
        cands.append(appdata / ".minecraft" / "screenshots")
        # Curseforge / Overwolf
        cands.append(home / "curseforge" / "minecraft" / "Instances")
        # Prism / MultiMC store per-instance screenshots; scan their roots
        cands.append(appdata / "PrismLauncher" / "instances")
        cands.append(home / "AppData" / "Roaming" / "ModrinthApp" / "profiles")
    elif system == "Darwin":
        app = home / "Library" / "Application Support"
        cands.append(app / "minecraft" / "screenshots")
        cands.append(app / "PrismLauncher" / "instances")
        cands.append(app / "ModrinthApp" / "profiles")
    else:  # Linux / other
        cands.append(home / ".minecraft" / "screenshots")
        # Flatpak vanilla launcher
        cands.append(home / ".var" / "app" / "com.mojang.Minecraft" / ".minecraft" / "screenshots")
        cands.append(home / ".local" / "share" / "PrismLauncher" / "instances")
        cands.append(home / ".var" / "app" / "org.prismlauncher.PrismLauncher" / "data" / "PrismLauncher" / "instances")
        cands.append(home / ".local" / "share" / "ModrinthApp" / "profiles")

    return cands


def _scan_for_screenshots(root: Path, depth: int = 4) -> List[Path]:
    """Find */screenshots dirs under a launcher instances root."""
    found: List[Path] = []
    if not root.exists():
        return found
    try:
        for dirpath, dirnames, _ in os.walk(root):
            rel = Path(dirpath).relative_to(root)
            if len(rel.parts) > depth:
                dirnames[:] = []
                continue
            if Path(dirpath).name == "screenshots":
                found.append(Path(dirpath))
    except (PermissionError, OSError):
        pass
    return found


def detect_screenshot_dirs() -> List[Path]:
    """Return all plausible Minecraft screenshot folders that currently exist."""
    results: List[Path] = []
    for cand in _candidate_screenshot_dirs():
        if cand.name == "screenshots" and cand.exists():
            results.append(cand)
        elif cand.is_dir():
            results.extend(_scan_for_screenshots(cand))
    # De-dup while preserving order
    seen = set()
    unique: List[Path] = []
    for p in results:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    return unique


def default_repo_dir() -> Path:
    return Path.home() / "MinecraftScreenshots"


@dataclass
class Config:
    watch_dirs: List[str] = field(default_factory=list)
    repo_dir: str = ""
    remote_url: str = ""
    auto_push: bool = True
    copy_to_clipboard: bool = True
    subdir: str = "screenshots"  # where shots land inside the repo

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
        return cls()

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @property
    def is_configured(self) -> bool:
        return bool(self.watch_dirs) and bool(self.repo_dir)
