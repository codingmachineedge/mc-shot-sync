"""Lightweight tests that run without a real Minecraft install or git remote."""
import os
import platform
from pathlib import Path

from mc_shot_sync import __version__
from mc_shot_sync.clipboard import _guess_mime
from mc_shot_sync.config import Config, config_dir, detect_screenshot_dirs
from mc_shot_sync.core import IMAGE_EXTS, SyncEngine


def test_version():
    assert __version__


def test_config_dir_is_platform_specific():
    d = config_dir()
    assert d.name == "mc-shot-sync"
    if platform.system() == "Windows":
        assert "Roaming" in str(d) or "AppData" in str(d)


def test_config_roundtrip(tmp_path, monkeypatch):
    cfgfile = tmp_path / "config.json"
    monkeypatch.setattr("mc_shot_sync.config.CONFIG_PATH", cfgfile)
    c = Config(watch_dirs=["/a"], repo_dir="/b", remote_url="x")
    c.save()
    loaded = Config.load()
    assert loaded.watch_dirs == ["/a"]
    assert loaded.repo_dir == "/b"
    assert loaded.is_configured


def test_detect_returns_list():
    # Should never throw, even with no Minecraft installed.
    dirs = detect_screenshot_dirs()
    assert isinstance(dirs, list)


def test_guess_mime():
    assert _guess_mime(Path("a.png")) == "image/png"
    assert _guess_mime(Path("a.JPG")) == "image/jpeg"
    assert _guess_mime(Path("a.unknown")) == "image/png"


def test_image_exts():
    assert ".png" in IMAGE_EXTS


def test_engine_requires_config():
    eng = SyncEngine(Config())
    try:
        eng.start()
        assert False, "should have raised"
    except RuntimeError:
        pass
