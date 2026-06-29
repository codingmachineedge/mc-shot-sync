"""System-tray GUI helper. Cross-platform via pystray + Pillow.

Shows status, lets you start/stop the watcher, toggle auto-push and clipboard,
open the repo folder, and view the last few events — all from the tray icon menu.
"""
from __future__ import annotations

import platform
import subprocess
import sys
import threading
import webbrowser
from collections import deque
from pathlib import Path

from .config import Config
from .core import Event, SyncEngine

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception as e:  # pragma: no cover
    pystray = None
    _IMPORT_ERR = e


_RECENT = deque(maxlen=8)


def _make_icon_image(active: bool) -> "Image.Image":
    """A simple 64x64 'creeper-ish' green square that dims when stopped."""
    size = 64
    bg = (60, 180, 75) if active else (120, 120, 120)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, size - 2, size - 2], radius=10, fill=bg)
    face = (20, 20, 20)
    # eyes
    d.rectangle([16, 18, 26, 30], fill=face)
    d.rectangle([38, 18, 48, 30], fill=face)
    # mouth
    d.rectangle([26, 34, 38, 46], fill=face)
    d.rectangle([22, 40, 30, 52], fill=face)
    d.rectangle([34, 40, 42, 52], fill=face)
    return img


def _open_folder(path: str) -> None:
    p = Path(path)
    if not p.exists():
        return
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["explorer", str(p)])
        elif system == "Darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except OSError:
        pass


def run_tray() -> int:
    if pystray is None:
        print(
            "Tray GUI needs 'pystray' and 'Pillow'. Install with:\n"
            "  pip install pystray Pillow\n"
            f"(import error: {_IMPORT_ERR})",
            file=sys.stderr,
        )
        return 2

    cfg = Config.load()
    if not cfg.is_configured:
        print("Not configured. Run `mc-shot-sync init` first.", file=sys.stderr)
        return 2

    icon_holder = {}

    def emit(e: Event) -> None:
        _RECENT.appendleft(e)
        icon = icon_holder.get("icon")
        if icon is not None:
            icon.title = _title()
            try:
                icon.update_menu()
            except Exception:
                pass

    engine = SyncEngine(cfg, emit=emit)

    def _title() -> str:
        state = "running" if engine.running else "stopped"
        return f"mc-shot-sync — {state} ({engine.processed_count} synced)"

    # ---- menu actions
    def do_toggle(icon, item):
        if engine.running:
            engine.stop()
        else:
            try:
                engine.start()
            except RuntimeError as ex:
                emit(Event("error", str(ex), __import__("time").time()))
        icon.icon = _make_icon_image(engine.running)
        icon.title = _title()
        icon.update_menu()

    def do_toggle_push(icon, item):
        cfg.auto_push = not cfg.auto_push
        cfg.save()
        icon.update_menu()

    def do_toggle_clip(icon, item):
        cfg.copy_to_clipboard = not cfg.copy_to_clipboard
        cfg.save()
        icon.update_menu()

    def do_open_repo(icon, item):
        _open_folder(cfg.repo_dir)

    def do_open_remote(icon, item):
        if cfg.remote_url:
            url = cfg.remote_url
            if url.endswith(".git"):
                url = url[:-4]
            if url.startswith("git@github.com:"):
                url = "https://github.com/" + url[len("git@github.com:"):]
            webbrowser.open(url)

    def do_quit(icon, item):
        engine.stop()
        icon.stop()

    def recent_items():
        if not _RECENT:
            return [pystray.MenuItem("(no activity yet)", None, enabled=False)]
        items = []
        for e in list(_RECENT):
            icon_ch = {"info": "·", "ok": "✓", "warn": "!", "error": "✗"}.get(e.level, "·")
            text = f"{icon_ch} {e.message}"
            items.append(pystray.MenuItem(text[:60], None, enabled=False))
        return items

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: _title(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            lambda item: "Stop watching" if engine.running else "Start watching",
            do_toggle,
        ),
        pystray.MenuItem(
            "Auto-push to GitHub",
            do_toggle_push,
            checked=lambda item: cfg.auto_push,
        ),
        pystray.MenuItem(
            "Copy to clipboard",
            do_toggle_clip,
            checked=lambda item: cfg.copy_to_clipboard,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open repo folder", do_open_repo),
        pystray.MenuItem("Open repo on GitHub", do_open_remote,
                         visible=lambda item: bool(cfg.remote_url)),
        pystray.MenuItem("Recent activity", pystray.Menu(recent_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", do_quit),
    )

    icon = pystray.Icon(
        "mc-shot-sync",
        icon=_make_icon_image(False),
        title=_title(),
        menu=menu,
    )
    icon_holder["icon"] = icon

    # Auto-start watching on launch.
    def _autostart():
        try:
            engine.start()
            icon.icon = _make_icon_image(True)
            icon.title = _title()
            icon.update_menu()
        except RuntimeError as ex:
            emit(Event("error", str(ex), __import__("time").time()))

    threading.Timer(0.5, _autostart).start()
    icon.run()
    return 0
