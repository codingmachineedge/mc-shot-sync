"""Thin git/gh wrappers used by the sync engine and the `init` command."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


class GitError(RuntimeError):
    pass


def _run(args, cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise GitError(f"{args[0]} failed to run: {e}") from e
    if check and proc.returncode != 0:
        raise GitError(
            f"`{' '.join(args)}` exited {proc.returncode}\n"
            f"stdout: {proc.stdout.strip()}\nstderr: {proc.stderr.strip()}"
        )
    return proc


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def is_repo(repo_dir: Path) -> bool:
    if not repo_dir.exists():
        return False
    proc = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_dir, check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def init_repo(repo_dir: Path, default_branch: str = "main") -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    if not is_repo(repo_dir):
        _run(["git", "init", "-b", default_branch], cwd=repo_dir)


def current_remote(repo_dir: Path) -> str:
    proc = _run(["git", "remote", "get-url", "origin"], cwd=repo_dir, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def set_remote(repo_dir: Path, url: str) -> None:
    if current_remote(repo_dir):
        _run(["git", "remote", "set-url", "origin", url], cwd=repo_dir)
    else:
        _run(["git", "remote", "add", "origin", url], cwd=repo_dir)


def gh_create_public_repo(repo_dir: Path, name: str) -> str:
    """Create a PUBLIC GitHub repo for repo_dir via gh and return its URL.

    Uses --source so gh wires up the 'origin' remote automatically.
    """
    if not have("gh"):
        raise GitError("GitHub CLI 'gh' is not installed. See https://cli.github.com/")
    # Fail fast with a clear message if not authenticated.
    auth = _run(["gh", "auth", "status"], check=False)
    if auth.returncode != 0:
        raise GitError("gh is not authenticated. Run: gh auth login")
    _run(
        [
            "gh", "repo", "create", name,
            "--public",
            "--source", str(repo_dir),
            "--remote", "origin",
        ],
        cwd=repo_dir,
    )
    return current_remote(repo_dir)


def commit_and_push(repo_dir: Path, paths, message: str, push: bool = True) -> bool:
    """Stage given paths, commit, and (optionally) push. Returns True if a commit was made."""
    rels = [str(p) for p in paths]
    _run(["git", "add", "--", *rels], cwd=repo_dir)
    # Anything staged?
    status = _run(["git", "diff", "--cached", "--name-only"], cwd=repo_dir)
    if not status.stdout.strip():
        return False
    _run(["git", "commit", "-m", message], cwd=repo_dir)
    if push:
        # Determine current branch and push, setting upstream on first push.
        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir).stdout.strip()
        proc = _run(["git", "push", "-u", "origin", branch], cwd=repo_dir, check=False)
        if proc.returncode != 0:
            raise GitError(f"git push failed:\n{proc.stderr.strip()}")
    return True
