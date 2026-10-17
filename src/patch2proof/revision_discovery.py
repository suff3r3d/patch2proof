"""Bounded, evidence-backed CVE-to-revision discovery before patch ingestion.

Only direct GitHub commit references from an NVD or OSV record are supported. Public
metadata retrieval is separate from target execution; no fetched text is run.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .tools.repo import ensure_within_root

CVE_PATTERN = re.compile(r"^CVE-[0-9]{4}-[0-9]{4,}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REFERENCES = 8
GIT_TIMEOUT = 90
MAX_GIT_BYTES = 128 * 1024 * 1024


class DiscoveryError(ValueError):
    """Evidence was unavailable, unsupported, or inconsistent."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise DiscoveryError("Metadata endpoint redirected; refusing new destination")


def fetch_json(url: str) -> tuple[bytes, dict[str, Any]]:
    """Fetch JSON only from fixed metadata hosts, with strict bounds."""

    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "services.nvd.nist.gov", "api.osv.dev", "api.github.com"
    } or parsed.port is not None or parsed.username or parsed.password:
        raise DiscoveryError("Unsupported metadata endpoint")
    request = Request(url, headers={
        "Accept": "application/json", "User-Agent": "Patch2Proof-revision-discovery/1",
    })
    try:
        with build_opener(_NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise DiscoveryError(f"Metadata retrieval failed: HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise DiscoveryError(f"Metadata retrieval failed: {type(exc).__name__}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise DiscoveryError("Metadata response exceeds size limit")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DiscoveryError("Metadata response is not JSON") from exc
    if not isinstance(data, dict):
        raise DiscoveryError("Metadata response is not an object")
    return raw, data


def _github_commit_reference(url: str) -> tuple[str, str, str] | None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.port is not None:
        return None
    if parsed.username or parsed.password:
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 4 or parts[2] != "commit":
        return None
    owner, repo, _, sha = parts
    if not NAME_PATTERN.fullmatch(owner) or not NAME_PATTERN.fullmatch(repo):
        return None
    if owner in {".", ".."} or repo in {".", ".."} or not SHA_PATTERN.fullmatch(sha):
        return None
    return owner, repo, sha


def _run_git(args: list[str], *, timeout: int = GIT_TIMEOUT) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1",
    })
    return subprocess.run(
        ["git", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null", *args],
        capture_output=True, text=True, check=False, timeout=timeout, env=env,
    )


def materialize_github_pair(owner: str, repo: str, fix_sha: str, root: Path) -> Path:
    """Fetch the fix and parent into a new, size-checked case-scoped Git repo."""

    if not NAME_PATTERN.fullmatch(owner) or not NAME_PATTERN.fullmatch(repo):
        raise DiscoveryError("Unsafe repository name")
    if not SHA_PATTERN.fullmatch(fix_sha):
        raise DiscoveryError("Invalid fixing commit identity")
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="discovered-repo-", dir=root))
    ensure_within_root(path, root)
    try:
        init = _run_git(["init", "--quiet", str(path)], timeout=15)
        if init.returncode != 0:
            raise DiscoveryError("Could not initialize local Git repository")
        remote = f"https://github.com/{owner}/{repo}.git"
        if _run_git(["-C", str(path), "remote", "add", "origin", remote], timeout=15).returncode:
            raise DiscoveryError("Could not configure the constrained Git remote")
        fetched = _run_git([
            "-C", str(path), "fetch", "--no-tags", "--depth=2", "origin", fix_sha,
        ])
        if fetched.returncode != 0:
            raise DiscoveryError("Could not fetch the referenced fixing commit")
        stored_bytes = sum(item.stat().st_size for item in (path / ".git").rglob("*")
                           if item.is_file())
        if stored_bytes > MAX_GIT_BYTES:
            raise DiscoveryError("Fetched Git repository exceeds size limit")
        return path
    except Exception:
        shutil.rmtree(path)
        raise


def _git_check(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return _run_git(["-C", str(repo), *args])


def verify_pair(repo: Path, vulnerable: str, fixed: str) -> dict[str, str]:
    """Check identities and patch relation without interpreting vulnerability behavior."""

    checks = {
        "repository_matches_source": "passed",
        "revisions_exist": "failed",
        "vulnerable_precedes_fixed": "not_evaluated",
        "patch_delta_nonempty": "not_evaluated",
        "cve_link_supported": "passed",
    }
    if not SHA_PATTERN.fullmatch(vulnerable) or not SHA_PATTERN.fullmatch(fixed):
        return checks
    actual = []
    for sha in (vulnerable, fixed):
        result = _git_check(repo, ["rev-parse", "--verify", f"{sha}^{{commit}}"])
        if result.returncode != 0:
            return checks
        actual.append(result.stdout.strip())
    if actual != [vulnerable, fixed]:
        return checks
    checks["revisions_exist"] = "passed"
    lineage = _git_check(repo, ["rev-list", "--parents", "-n", "1", fixed])
    parent_ids = lineage.stdout.strip().split() if lineage.returncode == 0 else []
    checks["vulnerable_precedes_fixed"] = (
        "passed" if parent_ids == [fixed, vulnerable] else "failed"
    )
    delta = _git_check(repo, ["diff", "--quiet", vulnerable, fixed, "--"])
    checks["patch_delta_nonempty"] = "passed" if delta.returncode == 1 else "failed"
    return checks


@dataclass(frozen=True)
class DiscoveryOutcome:
    result: dict[str, Any]
    repository_path: Path | None
    artifacts: tuple[str, ...]


def _validate_result(result: dict[str, Any], schema_root: Path) -> None:
    schemas = {}
    for path in schema_root.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[schema["$id"]] = schema
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    validator = Draft202012Validator(
        schemas["urn:dacn:schema:revision-discovery-result"],
        registry=registry, format_checker=FormatChecker(),
    )
    errors = list(validator.iter_errors(result))
    if errors:
        raise DiscoveryError(f"Discovery result violates schema: {errors[0].message}")
    if result["status"] == "resolved" and result["selected"] not in result["candidates"]:
        raise DiscoveryError("Selected pair is absent from candidate list")


def discover_revisions(
    cve_id: str,
    output_dir: Path,
    schema_root: Path,
    *,
    repository_hint: str | None = None,
    fetcher: Callable[[str], tuple[bytes, dict[str, Any]]] = fetch_json,
    materializer: Callable[[str, str, str, Path], Path] = materialize_github_pair,
) -> DiscoveryOutcome:
    """Resolve a single tagged GitHub fix or retain candidates for review."""

    if not CVE_PATTERN.fullmatch(cve_id):
        raise DiscoveryError("Invalid CVE ID")
    request: dict[str, str] = {"cve_id": cve_id}
    if repository_hint is not None:
        request["repository_hint"] = repository_hint
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[str] = []
    candidates: list[dict[str, Any]] = []
    selected_repo: Path | None = None
    reason: str | None = None
    def timestamp() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        nvd_url = "https://services.nvd.nist.gov/rest/json/cves/2.0?" + urlencode({
            "cveId": cve_id
        })
        osv_url = f"https://api.osv.dev/v1/vulns/{cve_id}"
        parsed_refs: dict[tuple[str, str, str], tuple[str, bytes, bool]] = {}
        source_error = ""
        for provider, url, filename in (
            ("nvd", nvd_url, "discovery-nvd.json"),
            ("osv", osv_url, "discovery-osv.json"),
        ):
            try:
                provider_raw, record = fetcher(url)
                if provider == "nvd":
                    vulnerabilities = record.get("vulnerabilities", [])
                    if not isinstance(vulnerabilities, list):
                        raise DiscoveryError("Malformed NVD vulnerability list")
                    matching = [item["cve"] for item in vulnerabilities
                                if isinstance(item, dict) and isinstance(item.get("cve"), dict)
                                and item["cve"].get("id") == cve_id]
                    if len(matching) != 1:
                        raise DiscoveryError("NVD returned no unique record for this CVE")
                    references = matching[0].get("references", [])
                else:
                    aliases = record.get("aliases", [])
                    if not isinstance(aliases, list):
                        aliases = []
                    if record.get("id") != cve_id and cve_id not in aliases:
                        raise DiscoveryError("OSV record does not identify the requested CVE")
                    references = record.get("references", [])
                if not isinstance(references, list):
                    raise DiscoveryError("Malformed CVE reference list")
                (output_dir / filename).write_bytes(provider_raw)
                artifacts.append(filename)
                fixed_ranges: set[tuple[str, str, str]] = set()
                if provider == "osv":
                    affected_records = record.get("affected", [])
                    for affected in affected_records if isinstance(affected_records, list) else []:
                        if not isinstance(affected, dict):
                            continue
                        ranges = affected.get("ranges", [])
                        for entry in ranges if isinstance(ranges, list) else []:
                            if not isinstance(entry, dict) or entry.get("type") != "GIT":
                                continue
                            range_url = entry.get("repo")
                            parsed_repo = (
                                urlsplit(range_url) if isinstance(range_url, str) else None
                            )
                            if (not parsed_repo or parsed_repo.scheme != "https"
                                    or parsed_repo.hostname != "github.com"
                                    or parsed_repo.port is not None):
                                continue
                            repo_parts = parsed_repo.path.strip("/").removesuffix(".git").split("/")
                            if len(repo_parts) != 2:
                                continue
                            events = entry.get("events", [])
                            for event in events if isinstance(events, list) else []:
                                sha = event.get("fixed") if isinstance(event, dict) else None
                                if isinstance(sha, str) and SHA_PATTERN.fullmatch(sha):
                                    fixed_ranges.add((repo_parts[0], repo_parts[1], sha))
                for reference in references:
                    ref_url = reference.get("url") if isinstance(reference, dict) else None
                    parsed = (
                        _github_commit_reference(ref_url)
                        if isinstance(ref_url, str) else None
                    )
                    if parsed:
                        if provider == "nvd":
                            tags = reference.get("tags", [])
                            tagged_fix = isinstance(tags, list) and any(
                                str(tag).lower() == "patch" for tag in tags
                            )
                        else:
                            tagged_fix = reference.get("type") == "FIX" or parsed in fixed_ranges
                        previous = parsed_refs.get(parsed)
                        if previous is None or (tagged_fix and not previous[2]):
                            parsed_refs[parsed] = (url, provider_raw, tagged_fix)
                if any(item[2] for item in parsed_refs.values()):
                    break
            except DiscoveryError as exc:
                source_error = str(exc)
        if not parsed_refs:
            raise DiscoveryError(
                "No direct GitHub fixing commit reference found in NVD or OSV. "
                + source_error
            )
        fixing_refs = {key: value for key, value in parsed_refs.items() if value[2]}
        if fixing_refs:
            parsed_refs = fixing_refs
        else:
            reason = "No metadata reference explicitly identifies a fixing commit."
        if len(parsed_refs) > 1:
            reason = "Multiple fixing commit references require review."
        if len(parsed_refs) > MAX_REFERENCES:
            reason = "Too many fixing commit references for automatic selection."
        candidate_errors: list[str] = []
        for index, ((owner, repo, linked_sha), (source_url, raw, fix_supported)) in enumerate(
            list(parsed_refs.items())[:MAX_REFERENCES]
        ):
            repository_url = f"https://github.com/{owner}/{repo}.git"
            if repository_hint and repository_hint.rstrip("/") != repository_url:
                continue
            api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{linked_sha}"
            try:
                commit_raw, commit = fetcher(api_url)
                commit_name = f"discovery-commit-{index}.json"
                (output_dir / commit_name).write_bytes(commit_raw)
                artifacts.append(commit_name)
                fixed = commit.get("sha")
                parents = commit.get("parents", [])
                if (
                    fixed != linked_sha
                    or _github_commit_reference(str(commit.get("html_url", "")))
                    != (owner, repo, linked_sha)
                    or not isinstance(parents, list)
                    or len(parents) != 1
                ):
                    continue
                vulnerable = parents[0].get("sha") if isinstance(parents[0], dict) else None
                if not isinstance(vulnerable, str) or not SHA_PATTERN.fullmatch(vulnerable):
                    continue
                evidence = [
                    {"kind": "cve_record", "url": source_url, "retrieved_at": timestamp(),
                     "content_sha256": hashlib.sha256(raw).hexdigest()},
                    {"kind": "commit", "url": api_url, "retrieved_at": timestamp(),
                     "content_sha256": hashlib.sha256(commit_raw).hexdigest()},
                ]
                checks = {key: "not_evaluated" for key in (
                    "repository_matches_source", "revisions_exist",
                    "vulnerable_precedes_fixed", "patch_delta_nonempty", "cve_link_supported",
                )}
                checks["repository_matches_source"] = "passed"
                checks["cve_link_supported"] = (
                    "passed" if fix_supported else "not_evaluated"
                )
                candidates.append({
                    "repository_url": repository_url,
                    "vulnerable_commit": vulnerable,
                    "fixed_commit": fixed,
                    "fix_commit": fixed,
                    "evidence": evidence,
                    "checks": checks,
                    "notes": (
                        "Vulnerable commit is the direct parent of the referenced fix; "
                        "affected behavior is unproven."
                    ),
                })
            except DiscoveryError as exc:
                candidate_errors.append(str(exc))
                continue
        if not candidates:
            detail = f" First error: {candidate_errors[0]}" if candidate_errors else ""
            raise DiscoveryError(
                "No supported single-parent fixing commit could be resolved." + detail
            )
        if len(candidates) == 1 and reason is None:
            candidate = candidates[0]
            selected_url = (
                candidate["repository_url"].removesuffix(".git")
                + "/commit/" + candidate["fixed_commit"]
            )
            owner, repo, _ = _github_commit_reference(selected_url) or (None, None, None)
            if owner is None or repo is None:
                raise DiscoveryError("Invalid candidate repository")
            try:
                selected_repo = materializer(
                    owner, repo, candidate["fixed_commit"], output_dir,
                )
                selected_repo = ensure_within_root(selected_repo, output_dir)
                candidate["checks"] = verify_pair(
                    selected_repo, candidate["vulnerable_commit"], candidate["fixed_commit"]
                )
            except (DiscoveryError, subprocess.TimeoutExpired, OSError) as exc:
                reason = f"Local Git verification failed: {type(exc).__name__}"
                selected_repo = None
            if all(value == "passed" for value in candidate["checks"].values()):
                result = {"request": request, "status": "resolved", "candidates": candidates,
                          "selected": candidate}
            else:
                reason = reason or "Candidate did not pass all Git checks."
                result = {"request": request, "status": "ambiguous", "candidates": candidates,
                          "failure_reason": reason}
                selected_repo = None
        else:
            result = {"request": request, "status": "ambiguous", "candidates": candidates,
                      "failure_reason": reason or "Multiple fixing commits require review."}
    except DiscoveryError as exc:
        result = {"request": request, "status": "failed", "candidates": candidates,
                  "failure_reason": str(exc)}
    _validate_result(result, schema_root)
    return DiscoveryOutcome(result, selected_repo, tuple(artifacts))
