"""Repository access with path and argument validation.

The graph never accepts a raw shell command. Git is invoked with an argument
array and the repository is checked against the case allowlist.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

SAFE_REF = re.compile(r"^[A-Za-z0-9_./@^~:+-]+$")


def ensure_within_root(path: str | Path, root: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    root_path = Path(root).expanduser().resolve()
    try:
        if os.path.commonpath((str(candidate), str(root_path))) != str(root_path):
            raise ValueError(f"Path escapes configured root: {candidate}")
    except ValueError as exc:
        raise ValueError(f"Path escapes configured root: {candidate}") from exc
    return candidate


def validate_ref(ref: str) -> str:
    if not ref or ref.startswith("-") or not SAFE_REF.fullmatch(ref):
        raise ValueError(f"Unsafe git ref: {ref!r}")
    return ref


def run_git(repo: Path, args: list[str], timeout: int = 60) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def git_diff(repo_path: str, old_ref: str, new_ref: str, root: str) -> str:
    repo = ensure_within_root(repo_path, root)
    old = validate_ref(old_ref)
    new = validate_ref(new_ref)
    return run_git(repo, ["diff", "--no-ext-diff", "--unified=80", old, new, "--"])


def git_identity(repo_path: str, root: str, ref: str) -> dict[str, str]:
    repo = ensure_within_root(repo_path, root)
    safe_ref = validate_ref(ref)
    commit = run_git(repo, ["rev-parse", safe_ref]).strip()
    subject = run_git(repo, ["show", "-s", "--format=%s", safe_ref]).strip()
    return {"ref": safe_ref, "commit": commit, "subject": subject}


def validate_repo_path(path: str) -> str:
    """Validate a repository-relative path before using ``git show``."""

    candidate = Path(path)
    if candidate.is_absolute() or not path or ".." in candidate.parts or "\\" in path:
        raise ValueError(f"Unsafe repository path: {path!r}")
    if path.startswith("-") or ":" in path:
        raise ValueError(f"Unsafe repository path: {path!r}")
    return candidate.as_posix()


def git_show_file(repo_path: str, ref: str, path: str, root: str) -> str:
    """Read a source file from a pinned revision without checking it out."""

    repo = ensure_within_root(repo_path, root)
    safe_ref = validate_ref(ref)
    safe_path = validate_repo_path(path)
    return run_git(repo, ["show", f"{safe_ref}:{safe_path}"])


def git_find_files_containing(
    repo_path: str,
    ref: str,
    text: str,
    root: str,
    *,
    pathspecs: list[str],
    limit: int = 2000,
) -> list[str]:
    """Find tracked candidate files with a fixed-string search.

    Results are candidates only. Call-site parsing and model reasoning decide
    whether a textual match represents an actual call.
    """

    repo = ensure_within_root(repo_path, root)
    safe_ref = validate_ref(ref)
    if not text or len(text) > 240 or any(char in text for char in "\n\r\x00"):
        raise ValueError("Search token must be a non-empty single-line symbol")
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "grep",
            "-l",
            "-F",
            "-e",
            text,
            safe_ref,
            "--",
            *pathspecs,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git grep failed")
    prefix = f"{safe_ref}:"
    paths = []
    for line in result.stdout.splitlines():
        if line.startswith(prefix):
            line = line[len(prefix) :]
        if line:
            paths.append(line)
        if len(paths) >= limit:
            break
    return paths


def fixture_diff(path: str | Path) -> str:
    return Path(path).expanduser().read_text(encoding="utf-8")
