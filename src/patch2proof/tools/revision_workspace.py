"""Materialize immutable vulnerable/fixed source contexts for Docker builds."""

from __future__ import annotations

import json
import subprocess
import tarfile
from pathlib import Path

from .repo import ensure_within_root, git_identity, validate_ref


def _safe_member(member: tarfile.TarInfo) -> bool:
    name = Path(member.name)
    if name.is_absolute() or ".." in name.parts:
        return False
    link = Path(member.linkname) if member.issym() or member.islnk() else Path()
    return not (link.is_absolute() or ".." in link.parts)


def _archive_revision(repo: Path, ref: str, destination: Path, timeout: int) -> None:
    safe_ref = validate_ref(ref)
    temporary_tar = destination.parent / f".{destination.name}.tar"
    try:
        with temporary_tar.open("wb") as stream:
            result = subprocess.run(
                ["git", "-C", str(repo), "archive", "--format=tar", safe_ref],
                stdout=stream,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout,
            )
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.decode(errors="replace").strip() or "git archive failed"
            )
        with tarfile.open(temporary_tar, "r") as archive:
            members = archive.getmembers()
            if not all(_safe_member(member) for member in members):
                raise ValueError("git archive contains an unsafe path or link")
            try:
                archive.extractall(destination, filter="data")
            except TypeError:  # Python 3.11 compatibility
                archive.extractall(destination)
    finally:
        if temporary_tar.exists():
            temporary_tar.unlink()


def materialize_pair(
    repo_path: str | Path,
    allowed_root: str | Path,
    vulnerable_ref: str,
    fixed_ref: str,
    destination: str | Path,
    *,
    artifact_root: str | Path | None = None,
    timeout: int = 60,
) -> dict[str, object]:
    """Create role-separated contexts using read-only ``git archive`` calls."""

    repo = ensure_within_root(repo_path, allowed_root)
    root = Path(destination).expanduser().resolve()
    allowed_destination = ensure_within_root(root, artifact_root or allowed_root)
    if allowed_destination.exists() and any(allowed_destination.iterdir()):
        raise FileExistsError(
            f"Refusing to overwrite an existing source-pair directory: {allowed_destination}"
        )
    allowed_destination.mkdir(parents=True, exist_ok=True)
    contexts: dict[str, str] = {}
    identities: dict[str, dict[str, str]] = {}
    for role, ref in (("vulnerable", vulnerable_ref), ("fixed", fixed_ref)):
        context = allowed_destination / role
        context.mkdir(parents=True, exist_ok=True)
        _archive_revision(repo, ref, context, timeout)
        contexts[role] = str(context)
        identities[role] = git_identity(str(repo), str(allowed_root), ref)
    manifest: dict[str, object] = {
        "repo": str(repo),
        "contexts": contexts,
        "identities": identities,
    }
    (allowed_destination / "source-pair.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
