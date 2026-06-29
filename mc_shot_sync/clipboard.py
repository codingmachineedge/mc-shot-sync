"""Cross-platform 'copy image file to system clipboard'.

Windows : PowerShell + System.Windows.Forms.Clipboard (STA).
Linux   : wl-copy (Wayland) or xclip (X11).
macOS   : osascript (AppleScript) for PNG.

All failures are raised as ClipboardError so the caller can warn but continue.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path


class ClipboardError(RuntimeError):
    pass


def copy_image(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        raise ClipboardError(f"file not found: {path}")
    system = platform.system()
    if system == "Windows":
        _copy_windows(path)
    elif system == "Darwin":
        _copy_macos(path)
    else:
        _copy_linux(path)


def _copy_windows(path: Path) -> None:
    # Clipboard image ops require an STA thread. Windows PowerShell is STA by
    # default; pwsh 7 needs -STA. Try powershell first, then pwsh -sta.
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "Add-Type -AssemblyName System.Drawing;"
        "$bytes=[System.IO.File]::ReadAllBytes($env:MCSS_IMG);"
        "$ms=New-Object System.IO.MemoryStream(,$bytes);"
        "$img=[System.Drawing.Image]::FromStream($ms);"
        "[System.Windows.Forms.Clipboard]::SetImage($img);"
    )
    env = {"MCSS_IMG": str(path)}
    attempts = [
        ["powershell", "-NoProfile", "-STA", "-Command", script],
        ["pwsh", "-NoProfile", "-STA", "-Command", script],
    ]
    last_err = None
    for cmd in attempts:
        exe = shutil.which(cmd[0])
        if not exe:
            continue
        try:
            cmd[0] = exe
            _run(cmd, extra_env=env)
            return
        except ClipboardError as e:  # noqa: PERF203
            last_err = e
    raise ClipboardError(f"no working PowerShell for clipboard: {last_err}")


def _copy_macos(path: Path) -> None:
    # AppleScript: read a PNG file into the clipboard as a picture.
    script = f'set the clipboard to (read (POSIX file "{path}") as «class PNGf»)'
    if not shutil.which("osascript"):
        raise ClipboardError("osascript not found")
    _run(["osascript", "-e", script])


def _copy_linux(path: Path) -> None:
    import os

    mime = _guess_mime(path)
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    data = path.read_bytes()

    if wayland and shutil.which("wl-copy"):
        _run(["wl-copy", "--type", mime], stdin=data)
        return
    if shutil.which("xclip"):
        _run(["xclip", "-selection", "clipboard", "-t", mime, "-i"], stdin=data)
        return
    if shutil.which("wl-copy"):
        _run(["wl-copy", "--type", mime], stdin=data)
        return
    raise ClipboardError(
        "no clipboard tool found. Install 'wl-clipboard' (Wayland) or 'xclip' (X11)."
    )


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
    }.get(ext, "image/png")


def _run(cmd, stdin: bytes | None = None, extra_env=None) -> None:
    import os

    env = None
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            env=env,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise ClipboardError(str(e)) from e
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip() if proc.stderr else ""
        raise ClipboardError(f"{cmd[0]} exited {proc.returncode}: {err}")
