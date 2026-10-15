"""Complete unified-diff parsing plus conservative security observations.

The patch parser preserves every file section and hunk. Pattern matches are
only retrieval hints; they are never vulnerability verdicts.
"""

from __future__ import annotations

import re
from typing import Any

from ..evidence import sha256_text

SECURITY_PATTERNS: list[tuple[str, str]] = [
    ("auth_boundary", r"allow_guest|is_authenticated|authorize|permission|role|csrf"),
    ("path_or_file", r"open\(|read_text|write_text|Path\(|File\(|filename|upload|attachment"),
    ("command_sink", r"subprocess|os\.system|Runtime\.getRuntime|ProcessBuilder|exec\("),
    ("deserialization", r"pickle|yaml\.load|ObjectInputStream|readObject|deserialize|unmarshal"),
    ("template_or_markup", r"template|render|html|innerHTML|safe\b|mark_safe"),
    ("network_sink", r"requests\.|urllib|socket|HttpClient|RestTemplate|curl"),
]

_DIFF_HEADER = re.compile(r"^diff --git a/(.*?) b/(.*?)$")
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


def parse_patch_hunks(diff: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Return file records, complete hunk records and a parser completeness flag."""

    lines = diff.splitlines()
    files: list[dict[str, Any]] = []
    hunks: list[dict[str, Any]] = []
    current_file: dict[str, Any] | None = None
    index = 0
    expected_headers = 0
    parsed_headers = 0
    valid_hunk_bodies = 0
    saw_diff_header = False

    while index < len(lines):
        line = lines[index]
        match = _DIFF_HEADER.match(line)
        if match:
            saw_diff_header = True
            current_file = {
                "old_path": match.group(1),
                "new_path": match.group(2),
                "status": "modified",
                "hunk_ids": [],
            }
            files.append(current_file)
            index += 1
            continue

        if current_file is not None and line.startswith("--- "):
            old_path = line[4:].split("\t", 1)[0]
            current_file["old_path"] = None if old_path == "/dev/null" else old_path.removeprefix("a/")
            if old_path == "/dev/null":
                current_file["status"] = "added"
            index += 1
            continue

        if current_file is not None and line.startswith("+++ "):
            new_path = line[4:].split("\t", 1)[0]
            current_file["new_path"] = None if new_path == "/dev/null" else new_path.removeprefix("b/")
            if new_path == "/dev/null":
                current_file["status"] = "deleted"
            index += 1
            continue

        if line.startswith("@@"):
            expected_headers += 1
            hunk_match = _HUNK_HEADER.match(line)
            if not hunk_match or current_file is None:
                index += 1
                continue
            parsed_headers += 1
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2) or "1")
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4) or "1")
            index += 1
            body: list[str] = []
            old_line = old_start
            new_line = new_start
            old_remaining = old_count
            new_remaining = new_count
            records: list[dict[str, Any]] = []
            while index < len(lines) and (old_remaining > 0 or new_remaining > 0):
                content = lines[index]
                if content.startswith("\\ No newline"):
                    body.append(content)
                    index += 1
                    continue
                if content.startswith(("@@ ", "diff --git ")):
                    break
                if content.startswith("+") and new_remaining > 0:
                    records.append({"kind": "added", "line": new_line, "text": content[1:]})
                    new_line += 1
                    new_remaining -= 1
                elif content.startswith("-") and old_remaining > 0:
                    records.append({"kind": "removed", "line": old_line, "text": content[1:]})
                    old_line += 1
                    old_remaining -= 1
                elif content.startswith(" ") and old_remaining > 0 and new_remaining > 0:
                    records.append(
                        {"kind": "context", "old_line": old_line, "new_line": new_line, "text": content[1:]}
                    )
                    old_line += 1
                    new_line += 1
                    old_remaining -= 1
                    new_remaining -= 1
                else:
                    # A malformed hunk body should not be silently discarded.
                    records.append({"kind": "unknown", "text": content})
                    break
                body.append(content)
                index += 1
            if old_remaining == 0 and new_remaining == 0:
                valid_hunk_bodies += 1

            hunk_id = f"HUNK-{len(hunks) + 1:04d}"
            hunk = {
                "hunk_id": hunk_id,
                "old_path": current_file.get("old_path"),
                "new_path": current_file.get("new_path"),
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "header_context": hunk_match.group(5).strip(),
                "lines": records,
                "body_complete": old_remaining == 0 and new_remaining == 0,
                "text": "\n".join([line, *body]),
                "content_hash": sha256_text("\n".join([line, *body])),
            }
            hunks.append(hunk)
            current_file["hunk_ids"].append(hunk_id)
            continue

        if current_file is not None and line.startswith("Binary files "):
            current_file["status"] = "binary"
        index += 1

    complete = (
        (saw_diff_header or not diff.strip())
        and expected_headers == parsed_headers
        and parsed_headers == valid_hunk_bodies
    )
    for file_record in files:
        if file_record.get("status") == "modified" and not file_record["hunk_ids"]:
            # A mode-only/rename-only diff is valid but has no source hunk.
            file_record["status"] = "metadata_only"
    return files, hunks, complete


def changed_paths(diff: str) -> list[str]:
    files, _, _ = parse_patch_hunks(diff)
    paths = [item.get("new_path") or item.get("old_path") for item in files]
    return list(dict.fromkeys(path for path in paths if path))


def changed_lines(diff: str) -> list[dict[str, Any]]:
    _, hunks, _ = parse_patch_hunks(diff)
    return [
        {"path": hunk.get("new_path") or hunk.get("old_path"), "line": row["text"]}
        for hunk in hunks
        for row in hunk["lines"]
        if row["kind"] == "added"
    ]


def analyze_diff(diff: str, version: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    files, hunks, patch_complete = parse_patch_hunks(diff)
    paths = [item.get("new_path") or item.get("old_path") for item in files]
    paths = list(dict.fromkeys(path for path in paths if path))
    lines = changed_lines(diff)
    tags: set[str] = set()
    evidence: list[dict[str, Any]] = []

    for hunk in hunks:
        evidence.append(
            {
                "evidence_id": f"EV-{hunk['hunk_id']}",
                "kind": "diff",
                "observation": (
                    f"Complete patch hunk {hunk['hunk_id']} in "
                    f"{hunk.get('new_path') or hunk.get('old_path')}"
                ),
                "path": hunk.get("new_path") or hunk.get("old_path"),
                "line_start": hunk["new_start"],
                "line_end": max(hunk["new_start"], hunk["new_start"] + hunk["new_count"] - 1),
                "version": version,
                "content_hash": hunk["content_hash"],
                "provenance": {"analyzer": "patch2proof.diff_analysis", "hunk_id": hunk["hunk_id"]},
            }
        )

    for index, item in enumerate(lines, start=1):
        line = item["line"]
        for tag, pattern in SECURITY_PATTERNS:
            if re.search(pattern, line, flags=re.IGNORECASE):
                tags.add(tag)
                evidence.append(
                    {
                        "evidence_id": f"EV-DIFF-LINE-{index:04d}",
                        "kind": "diff",
                        "observation": (
                            f"Added line matches retrieval pattern {tag}: {line[:240]}"
                        ),
                        "path": item["path"],
                        "version": version,
                        "content_hash": sha256_text(line),
                        "provenance": {
                            "analyzer": "patch2proof.diff_analysis",
                            "line_index": index,
                            "heuristic_hint_only": True,
                        },
                    }
                )

    summary = {
        "changed_paths": paths,
        "file_changes": files,
        "hunks": hunks,
        "hunk_count": len(hunks),
        "patch_complete": patch_complete,
        "added_line_count": len(lines),
        "security_tags": sorted(tags),
        "patch_hash": sha256_text(diff),
    }
    return summary, evidence
