"""Command-line interface for mc-shot-sync."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__, gitpush
from .config import (
    Config,
    default_repo_dir,
    detect_screenshot_dirs,
)
from .core import Event, SyncEngine


def _print_event(e: Event) -> None:
    icon = {"info": "*", "ok": "+", "warn": "!", "error": "x"}.get(e.level, "*")
    ts = time.strftime("%H:%M:%S", time.localtime(e.when))
    print(f"[{ts}] {icon} {e.message}", flush=True)


# --------------------------------------------------------------------------- init
def cmd_init(args: argparse.Namespace) -> int:
    cfg = Config.load()

    # 1) Watch dirs
    if args.watch:
        watch_dirs = [str(Path(w).expanduser()) for w in args.watch]
    else:
        detected = detect_screenshot_dirs()
        if detected:
            print("Detected Minecraft screenshot folder(s):")
            for d in detected:
                print(f"  - {d}")
            watch_dirs = [str(d) for d in detected]
        else:
            print("No Minecraft screenshot folder auto-detected.")
            print("Pass one explicitly:  mc-shot-sync init --watch <path>")
            return 2
    cfg.watch_dirs = watch_dirs

    # 2) Repo dir
    repo_dir = Path(args.repo_dir).expanduser() if args.repo_dir else default_repo_dir()
    cfg.repo_dir = str(repo_dir)

    # 3) Init git repo
    gitpush.init_repo(repo_dir)
    print(f"Local repo: {repo_dir}")

    # Seed a README + .gitignore so the first push isn't empty.
    (repo_dir / Path(cfg.subdir)).mkdir(parents=True, exist_ok=True)
    readme = repo_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# {args.name or repo_dir.name}\n\n"
            "Minecraft screenshots, synced automatically by "
            "[mc-shot-sync](https://github.com/).\n",
            encoding="utf-8",
        )
    keep = repo_dir / cfg.subdir / ".gitkeep"
    if not keep.exists():
        keep.write_text("", encoding="utf-8")

    # 4) Remote: existing, explicit, or create via gh
    remote = gitpush.current_remote(repo_dir)
    if args.remote:
        gitpush.set_remote(repo_dir, args.remote)
        remote = args.remote
        print(f"Remote set to: {remote}")
    elif not remote and not args.no_create:
        name = args.name or repo_dir.name
        print(f"Creating PUBLIC GitHub repo '{name}' via gh ...")
        try:
            remote = gitpush.gh_create_public_repo(repo_dir, name)
            print(f"Created: {remote}")
        except gitpush.GitError as e:
            print(f"\nCould not create the GitHub repo automatically:\n{e}\n", file=sys.stderr)
            print("Fix the issue above (e.g. `gh auth login`) and re-run, or pass\n"
                  "  --remote <git-url>  to use a repo you already created.", file=sys.stderr)
            cfg.save()
            return 3
    cfg.remote_url = remote

    cfg.save()

    # 5) Initial commit + push
    try:
        gitpush.commit_and_push(
            repo_dir,
            ["README.md", cfg.subdir],
            "Initial commit (mc-shot-sync)",
            push=bool(remote),
        )
        print("Initial commit done." + ("" if remote else " (no remote — not pushed)"))
    except gitpush.GitError as e:
        print(f"Initial commit/push warning: {e}", file=sys.stderr)

    print("\nSetup complete. Start watching with:")
    print("  mc-shot-sync watch      (headless)")
    print("  mc-shot-sync tray       (system-tray GUI)")
    return 0


# -------------------------------------------------------------------------- watch
def cmd_watch(args: argparse.Namespace) -> int:
    cfg = Config.load()
    if not cfg.is_configured:
        print("Not configured. Run `mc-shot-sync init` first.", file=sys.stderr)
        return 2
    engine = SyncEngine(cfg, emit=_print_event)
    try:
        engine.start()
    except RuntimeError as e:
        print(f"Cannot start: {e}", file=sys.stderr)
        return 2
    print("Watching for new screenshots. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
    finally:
        engine.stop()
    return 0


# --------------------------------------------------------------------------- tray
def cmd_tray(args: argparse.Namespace) -> int:
    from .tray import run_tray  # imported lazily (optional GUI deps)

    return run_tray()


# ---------------------------------------------------------------------------- once
def cmd_once(args: argparse.Namespace) -> int:
    cfg = Config.load()
    if not cfg.is_configured:
        print("Not configured. Run `mc-shot-sync init` first.", file=sys.stderr)
        return 2
    engine = SyncEngine(cfg, emit=_print_event)
    engine.process_file(Path(args.file).expanduser())
    return 0


# -------------------------------------------------------------------------- status
def cmd_status(args: argparse.Namespace) -> int:
    cfg = Config.load()
    from .config import CONFIG_PATH

    print(f"mc-shot-sync {__version__}")
    print(f"config file : {CONFIG_PATH}")
    print(f"configured  : {cfg.is_configured}")
    print(f"watch dirs  : {cfg.watch_dirs or '(none)'}")
    print(f"repo dir    : {cfg.repo_dir or '(none)'}")
    print(f"remote      : {cfg.remote_url or '(none)'}")
    print(f"auto push   : {cfg.auto_push}")
    print(f"clipboard   : {cfg.copy_to_clipboard}")
    print(f"gh present  : {gitpush.have('gh')}")
    print(f"git present : {gitpush.have('git')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mc-shot-sync",
        description="Auto-detect new Minecraft screenshots, copy to clipboard, git push.",
    )
    p.add_argument("--version", action="version", version=f"mc-shot-sync {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="detect screenshots, create repo, configure")
    pi.add_argument("--watch", action="append", help="screenshot folder to watch (repeatable)")
    pi.add_argument("--repo-dir", help="local folder for the screenshot repo")
    pi.add_argument("--name", help="GitHub repo name to create (default: repo dir name)")
    pi.add_argument("--remote", help="use this existing git remote URL instead of creating one")
    pi.add_argument("--no-create", action="store_true", help="do not create a GitHub repo")
    pi.set_defaults(func=cmd_init)

    pw = sub.add_parser("watch", help="run the watcher in the foreground")
    pw.set_defaults(func=cmd_watch)

    pt = sub.add_parser("tray", help="run the system-tray GUI helper")
    pt.set_defaults(func=cmd_tray)

    po = sub.add_parser("once", help="process a single screenshot file now")
    po.add_argument("file", help="path to an image file")
    po.set_defaults(func=cmd_once)

    ps = sub.add_parser("status", help="show current configuration")
    ps.set_defaults(func=cmd_status)

    return p


def main(argv=None) -> int:
    # Make console output robust to non-cp1252 characters in filenames/paths.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
