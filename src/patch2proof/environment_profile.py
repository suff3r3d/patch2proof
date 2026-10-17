"""Read-only build profile detection from two pinned Git revisions."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from .tools.repo import ensure_within_root, validate_ref

_PROFILES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("python", "pip", ("pyproject.toml", "requirements.txt", "setup.py")),
    ("node", "npm", ("package.json", "package-lock.json")),
    ("java", "maven", ("pom.xml",)),
    ("java", "gradle", ("build.gradle", "build.gradle.kts", "gradlew")),
    ("go", "go", ("go.mod", "go.sum")),
    ("php", "composer", ("composer.json", "composer.lock")),
    ("cpp", "cmake", ("CMakeLists.txt",)),
)
_MANIFEST_LIMIT = 5 * 1024 * 1024


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip() or "Git inspection failed")
    return result.stdout


def _revision_profile(repo: Path, ref: str) -> dict[str, Any]:
    ref = validate_ref(ref)
    names = set(_git(repo, "ls-tree", "--name-only", ref).decode().splitlines())
    matches = [
        (language, build_system, markers)
        for language, build_system, markers in _PROFILES
        if any(marker in names for marker in markers)
    ]
    if len(matches) == 1:
        language, build_system, markers = matches[0]
    else:
        language, build_system, markers = "unknown", "custom", ()
    manifests: dict[str, dict[str, Any]] = {}
    default_template_reasons: list[str] = []
    for marker in markers:
        if marker not in names:
            continue
        size = int(_git(repo, "cat-file", "-s", f"{ref}:{marker}").strip())
        if size > _MANIFEST_LIMIT:
            raise ValueError(f"Build manifest {marker} exceeds inspection limit")
        data = _git(repo, "show", f"{ref}:{marker}")
        manifests[marker] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        if language == "python" and marker == "requirements.txt":
            declarations = [
                line for line in data.decode(errors="replace").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            manifests[marker]["declarations"] = len(declarations)
            if declarations:
                default_template_reasons.append(
                    "Python requirements need a reviewed offline dependency supply"
                )
    if language == "python" and ({"pyproject.toml", "setup.py"} & names):
        default_template_reasons.append(
            "Project packaging needs reviewed installation and startup steps"
        )
    if language not in {"python", "unknown"}:
        default_template_reasons.append(
            f"{language} build needs reviewed dependency and startup steps"
        )
    return {
        "commit": _git(repo, "rev-parse", f"{ref}^{{commit}}").decode().strip(),
        "language": language,
        "build_system": build_system,
        "manifests": manifests,
        "default_template_reasons": default_template_reasons,
    }


def inspect_environment_pair(
    repository_path: str | Path,
    allowed_root: str | Path,
    vulnerable_ref: str,
    fixed_ref: str,
) -> dict[str, Any]:
    """Identify the build system without running project-supplied code."""

    repo = ensure_within_root(repository_path, allowed_root)
    revisions = {
        "vulnerable": _revision_profile(repo, vulnerable_ref),
        "fixed": _revision_profile(repo, fixed_ref),
    }
    profiles = {
        (item["language"], item["build_system"]) for item in revisions.values()
    }
    if len(profiles) == 1 and ("unknown", "custom") not in profiles:
        language, build_system = profiles.pop()
        status = "detected"
        reasons: list[str] = []
    else:
        language, build_system = "unknown", "custom"
        status = "review_required"
        reasons = ["Build system is missing or differs between revisions"]
    default_reasons = sorted({
        reason for record in revisions.values()
        for reason in record["default_template_reasons"]
    })
    return {
        "status": status,
        "language": language,
        "build_system": build_system,
        "revisions": revisions,
        "review_reasons": reasons,
        "default_template_ready": status == "detected" and not default_reasons,
        "default_template_reasons": default_reasons,
    }
