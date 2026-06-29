"""The sync engine: watch screenshot folders, on a new image copy it to the
clipboard and commit+push it into the repo. Used by both the CLI and the tray."""
from __future__ import annotations

import shutil
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import clipboard, gitpush
from .config import Config

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}


@dataclass
class Event:
    """A user-facing log line emitted by the engine."""
    level: str  # info | ok | warn | error
    message: str
    when: float


class _Handler(FileSystemEventHandler):
    def __init__(self, on_new: Callable[[Path], None]):
        self._on_new = on_new

    def _maybe(self, path_str: str) -> None:
        p = Path(path_str)
        if p.suffix.lower() in IMAGE_EXTS:
            self._on_new(p)

    def on_created(self, event):
        if not event.is_directory:
            self._maybe(event.src_path)

    def on_moved(self, event):
        # Some apps write to a temp file then rename into place.
        if not event.is_directory:
            self._maybe(event.dest_path)


class SyncEngine:
    """Owns the watchdog observer + processing thread.

    Thread-safe start()/stop(). Push the `emit` callback to receive log Events
    (the tray uses this to render a live log; the CLI prints them).
    """

    def __init__(self, config: Config, emit: Optional[Callable[[Event], None]] = None):
        self.config = config
        self._emit = emit or (lambda e: None)
        self._observer: Optional[Observer] = None
        self._lock = threading.Lock()
        self._seen: set[str] = set()
        self.processed_count = 0
        self.running = False

    # ------------------------------------------------------------------ logging
    def _log(self, level: str, message: str) -> None:
        self._emit(Event(level=level, message=message, when=time.time()))

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            cfg = self.config
            if not cfg.watch_dirs:
                raise RuntimeError("no watch_dirs configured — run `mc-shot-sync init`")
            obs = Observer()
            handler = _Handler(self._handle_new)
            watched = 0
            for d in cfg.watch_dirs:
                p = Path(d)
                if p.is_dir():
                    obs.schedule(handler, str(p), recursive=False)
                    watched += 1
                    self._log("info", f"watching {p}")
                else:
                    self._log("warn", f"skip (not found): {p}")
            if watched == 0:
                raise RuntimeError("none of the configured watch_dirs exist")
            obs.start()
            self._observer = obs
            self.running = True
            self._log("ok", f"started — watching {watched} folder(s)")

    def stop(self) -> None:
        with self._lock:
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=5)
                self._observer = None
            self.running = False
            self._log("info", "stopped")

    # ------------------------------------------------------------------ processing
    def _handle_new(self, path: Path) -> None:
        # Debounce duplicate events for the same file.
        key = str(path.resolve())
        if key in self._seen:
            return
        self._seen.add(key)
        threading.Thread(target=self._process, args=(path,), daemon=True).start()

    def _wait_until_stable(self, path: Path, tries: int = 30) -> bool:
        """Wait for the file to finish being written (size stops changing)."""
        last = -1
        for _ in range(tries):
            try:
                size = path.stat().st_size
            except OSError:
                time.sleep(0.2)
                continue
            if size == last and size > 0:
                return True
            last = size
            time.sleep(0.2)
        return path.exists()

    def process_file(self, path: Path) -> None:
        """Public single-shot processing (used by `mc-shot-sync once`)."""
        self._process(path)

    def _process(self, path: Path) -> None:
        cfg = self.config
        if not self._wait_until_stable(path):
            self._log("warn", f"vanished before stable: {path.name}")
            return
        self._log("info", f"new screenshot: {path.name}")

        # 1) clipboard
        if cfg.copy_to_clipboard:
            try:
                clipboard.copy_image(path)
                self._log("ok", f"copied to clipboard: {path.name}")
            except clipboard.ClipboardError as e:
                self._log("warn", f"clipboard failed: {e}")

        # 2) copy into repo + commit + push
        try:
            committed = self._commit_screenshot(path)
            if committed:
                verb = "pushed" if cfg.auto_push else "committed"
                self._log("ok", f"{verb}: {path.name}")
            else:
                self._log("info", f"nothing to commit for {path.name}")
        except gitpush.GitError as e:
            self._log("error", f"git failed: {e}")

        self.processed_count += 1

    def _commit_screenshot(self, path: Path) -> bool:
        cfg = self.config
        repo = Path(cfg.repo_dir)
        dest_dir = repo / cfg.subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / path.name
        if dest.resolve() != path.resolve():
            shutil.copy2(path, dest)
        rel = dest.relative_to(repo)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        msg = f"Add screenshot {path.name} ({ts})"
        return gitpush.commit_and_push(repo, [rel], msg, push=cfg.auto_push)
