"""Read-only, revision-aware source context and call-slice retrieval.

Python files use the standard-library AST. Other supported languages use a
bounded structural scanner that labels its output as candidate evidence. No
call-graph edge produced here is treated as runtime reachability proof.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from collections import deque
from pathlib import Path
from typing import Any, Mapping

from .evidence import sha256_text
from .models import SourceContextBundle, SourceQuery
from .tools.diff_analysis import parse_patch_hunks
from .tools.repo import (
    ensure_within_root,
    git_find_files_containing,
    git_show_file,
    validate_repo_path,
)

_IGNORED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "vendor",
    "build",
    "dist",
    "target",
    "out",
    "__pycache__",
}
_EXTENSIONS = {
    "python": ["*.py", "*.pyi"],
    "java": ["*.java"],
    "php": ["*.php", "*.phtml"],
    "node": ["*.js", "*.jsx", "*.mjs", "*.cjs", "*.ts", "*.tsx"],
    "go": ["*.go"],
    "cpp": ["*.c", "*.cc", "*.cpp", "*.h", "*.hpp"],
    "unknown": ["*.py", "*.java", "*.php", "*.js", "*.ts", "*.go", "*.c", "*.cpp"],
}
_CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
_CONTROL_NAMES = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "new",
    "synchronized",
    "try",
    "assert",
    "throw",
    "super",
    "this",
    "sizeof",
    "typeof",
}


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _slice_lines(text: str, first: int, last: int, limit: int = 10000) -> str:
    lines = text.splitlines()
    value = "\n".join(lines[max(0, first - 1) : min(len(lines), last)])
    return value[:limit]


def _python_symbols(text: str, path: str, revision: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.splitlines()
    symbols: list[dict[str, Any]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.parents: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.parents.append(node.name)
            for child in node.body:
                self.visit(child)
            self.parents.pop()

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            decorator_start = min(
                (item.lineno for item in node.decorator_list), default=node.lineno
            )
            start = min(node.lineno, decorator_start)
            end = getattr(node, "end_lineno", node.lineno)
            qualified = ".".join([*self.parents, node.name])
            symbol_id = f"{path}::{qualified}"
            calls: list[dict[str, Any]] = []

            class Calls(ast.NodeVisitor):
                def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
                    if child is node:
                        for statement in child.body:
                            self.visit(statement)

                visit_AsyncFunctionDef = visit_FunctionDef

                def visit_Lambda(self, child: ast.Lambda) -> None:
                    return

                def visit_Call(self, child: ast.Call) -> None:
                    target = child.func.id if isinstance(child.func, ast.Name) else None
                    if isinstance(child.func, ast.Attribute):
                        target = child.func.attr
                    if target:
                        calls.append(
                            {
                                "target_name": target,
                                "line": child.lineno,
                                "column": child.col_offset,
                            }
                        )
                    self.generic_visit(child)

            Calls().visit(node)
            full_content = "\n".join(lines[start - 1 : end])
            symbols.append(
                {
                    "symbol_id": symbol_id,
                    "name": node.name,
                    "qualified_name": qualified,
                    "path": path,
                    "revision": revision,
                    "line_start": start,
                    "line_end": end,
                    "kind": (
                        "async_function"
                        if isinstance(node, ast.AsyncFunctionDef)
                        else "function"
                    ),
                    "parser": "python-ast",
                    "confidence": 1.0,
                    "content": full_content[:10000],
                    "content_truncated": len(full_content) > 10000,
                    "calls": calls,
                }
            )
            self.parents.append(node.name)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    self.visit(child)
            self.parents.pop()

        visit_FunctionDef = _visit_function
        visit_AsyncFunctionDef = _visit_function

    Visitor().visit(tree)
    return symbols


def _mask_non_code(text: str) -> str:
    """Mask comments and quoted strings while preserving offsets/newlines."""

    chars = list(text)
    i = 0
    state = "code"
    quote = ""
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "line"
                continue
            if char == "/" and nxt == "*":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "block"
                continue
            if char in {"'", '"', "`"}:
                quote = char
                chars[i] = " "
                state = "string"
        elif state == "line":
            if char == "\n":
                state = "code"
            else:
                chars[i] = " "
        elif state == "block":
            if char == "*" and nxt == "/":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "code"
                continue
            if char != "\n":
                chars[i] = " "
        elif state == "string":
            if char == "\\":
                if char != "\n":
                    chars[i] = " "
                if i + 1 < len(text):
                    if text[i + 1] != "\n":
                        chars[i + 1] = " "
                    i += 2
                    continue
            elif char == quote:
                chars[i] = " "
                state = "code"
            elif char != "\n":
                chars[i] = " "
        i += 1
    return "".join(chars)


def _matching_brace(masked: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(masked)


def _generic_patterns(language: str) -> list[re.Pattern[str]]:
    if language == "java":
        return [
            re.compile(
                r"(?m)^[ \t]*(?:(?:@[\w.$]+(?:\([^\n]*?\))?)[ \t]*\n[ \t]*)*"
                r"(?:(?:public|protected|private|static|final|synchronized|native|abstract|"
                r"default|strictfp)\s+)*"
                r"(?:<[^\n{}]+>\s*)?[\w$?.<>\[\],]+\s+"
                r"(?P<name>[A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*(?:throws\s+[^{}]+)?\{"
            )
        ]
    if language in {"node", "javascript", "typescript"}:
        return [
            re.compile(r"\bfunction\s+(?P<name>[A-Za-z_$][\w$]*)\s*\([^{}]*\)\s*\{"),
            re.compile(
                r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
                r"(?:async\s*)?(?:function\s*\([^{}]*\)|\([^{}]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{"
            ),
            re.compile(r"(?m)^\s*(?P<name>[A-Za-z_$][\w$]*)\s*\([^{}]*\)\s*\{"),
        ]
    if language == "php":
        return [re.compile(r"\bfunction\s+&?\s*(?P<name>[A-Za-z_$][\w$]*)\s*\([^{}]*\)\s*\{")]
    if language == "go":
        return [
            re.compile(
                r"\bfunc\s+(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][\w]*)\s*\([^{}]*\)"
                r"(?:\s*\([^{}]*\)|\s+[\w.*\[\]]+)?\s*\{"
            )
        ]
    if language == "cpp":
        return [
            re.compile(
                r"(?m)^[ \t]*(?:[\w:<>*&~]+\s+)+(?P<name>[A-Za-z_~][\w:]*)"
                r"\s*\([^;{}]*\)\s*(?:const\s*)?\{"
            )
        ]
    return []


def _generic_symbols(text: str, path: str, revision: str, language: str) -> list[dict[str, Any]]:
    masked = _mask_non_code(text)
    found: dict[tuple[str, int], dict[str, Any]] = {}
    for pattern in _generic_patterns(language):
        for match in pattern.finditer(masked):
            name = match.group("name")
            opening = masked.find("{", match.start(), match.end())
            if opening < 0:
                continue
            closing = _matching_brace(masked, opening)
            start_line = _line_number(text, match.start())
            end_line = _line_number(text, closing)
            body = masked[opening + 1 : closing]
            raw_calls = []
            for call_match in _CALL_RE.finditer(body):
                target = call_match.group(1)
                if target in _CONTROL_NAMES:
                    continue
                absolute = opening + 1 + call_match.start(1)
                raw_calls.append(
                    {
                        "target_name": target,
                        "line": _line_number(text, absolute),
                        "column": absolute - text.rfind("\n", 0, absolute) - 1,
                    }
                )
            start_offset = text.rfind("\n", 0, match.start()) + 1
            full_content = text[start_offset : closing + 1]
            key = (name, start_line)
            found[key] = {
                "symbol_id": f"{path}::{name}@{start_line}",
                "name": name,
                "qualified_name": name,
                "path": path,
                "revision": revision,
                "line_start": start_line,
                "line_end": end_line,
                "kind": "method_or_function",
                "parser": f"{language}-structural-candidate",
                "confidence": 0.65,
                "content": full_content[:10000],
                "content_truncated": len(full_content) > 10000,
                "calls": raw_calls,
            }
    return sorted(found.values(), key=lambda item: (item["line_start"], item["name"]))


def parse_source_symbols(
    text: str, path: str, revision: str, language: str
) -> list[dict[str, Any]]:
    if language == "python" or path.endswith((".py", ".pyi")):
        return _python_symbols(text, path, revision)
    return _generic_symbols(text, path, revision, language)


class SourceRepositoryReader:
    """Read-only facade over pinned Git revisions or fixture snapshots."""

    def __init__(self, case: Mapping[str, Any]):
        self.case = dict(case)
        policy = self.case.get("policy", {})
        self.repo = ensure_within_root(
            self.case["repository_path"], policy.get("allowed_repo_root", ".")
        )
        self.mode = self.case.get("source_mode", "git")
        self.language = self.case.get("language", "unknown")
        self.limit = int(policy.get("source_file_limit", 2000))
        self.max_file_bytes = int(policy.get("source_file_max_bytes", 1_000_000))
        self.extensions = _EXTENSIONS.get(self.language, _EXTENSIONS["unknown"])
        self._suffixes = {Path(ext.replace("*", "x")).suffix for ext in self.extensions}
        self._file_cache: dict[tuple[str, str], str] = {}
        self._symbol_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._search_cache: dict[tuple[str, str], list[str]] = {}

    def revision_ref(self, role: str) -> str:
        if role not in {"vulnerable", "fixed"}:
            raise ValueError("revision must be vulnerable or fixed")
        return str(self.case[f"{role}_ref"])

    def read_file(self, role: str, path: str) -> str:
        safe_path = validate_repo_path(path)
        cache_key = (role, safe_path)
        if cache_key in self._file_cache:
            return self._file_cache[cache_key]
        revision = self.revision_ref(role)
        if self.mode == "git":
            content = git_show_file(
                str(self.repo),
                revision,
                safe_path,
                self.case["policy"].get("allowed_repo_root", "."),
            )
        elif self.mode == "fixture":
            safe_revision = validate_repo_path(revision)
            root = ensure_within_root(
                self.repo / safe_revision, self.case["policy"].get("allowed_repo_root", ".")
            )
            candidate = ensure_within_root(root / safe_path, root)
            content = candidate.read_text(encoding="utf-8", errors="replace")
        else:
            raise ValueError(f"Unsupported source mode: {self.mode}")
        if len(content.encode("utf-8", errors="replace")) > self.max_file_bytes:
            raise ValueError(
                "Source file exceeds the configured "
                f"{self.max_file_bytes}-byte read limit: {safe_path}"
            )
        self._file_cache[cache_key] = content
        return content

    def find_files_containing(self, role: str, symbol: str) -> list[str]:
        cache_key = (role, symbol)
        if cache_key in self._search_cache:
            return list(self._search_cache[cache_key])
        revision = self.revision_ref(role)
        if self.mode == "git":
            matches = git_find_files_containing(
                str(self.repo),
                revision,
                symbol,
                self.case["policy"].get("allowed_repo_root", "."),
                pathspecs=self.extensions,
                limit=self.limit,
            )
        elif self.mode == "fixture":
            root = ensure_within_root(
                self.repo / validate_repo_path(revision),
                self.case["policy"].get("allowed_repo_root", "."),
            )
            matches = []
            for current, dirs, files in os.walk(root):
                dirs[:] = [name for name in dirs if name not in _IGNORED_DIRS]
                for filename in files:
                    path = Path(current) / filename
                    if path.suffix not in self._suffixes:
                        continue
                    try:
                        if path.stat().st_size > self.max_file_bytes:
                            continue
                        text = path.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    if symbol in text:
                        matches.append(path.relative_to(root).as_posix())
                        if len(matches) >= self.limit:
                            break
                if len(matches) >= self.limit:
                    break
        else:
            raise ValueError(f"Unsupported source mode: {self.mode}")
        self._search_cache[cache_key] = matches
        return list(matches)

    def symbols_in_file(self, role: str, path: str) -> list[dict[str, Any]]:
        cache_key = (role, validate_repo_path(path))
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]
        text = self.read_file(role, path)
        symbols = parse_source_symbols(text, path, self.revision_ref(role), self.language)
        self._symbol_cache[cache_key] = symbols
        return symbols

    def find_callers(self, role: str, target: str, limit: int = 32) -> list[dict[str, Any]]:
        callers: list[dict[str, Any]] = []
        definitions = self.read_symbol(role, target, limit=128)
        definition_count = len({item["symbol_id"] for item in definitions})
        for path in self.find_files_containing(role, target):
            for symbol in self.symbols_in_file(role, path):
                for call in symbol["calls"]:
                    if call["target_name"] == target:
                        parser_is_exact = symbol["parser"] == "python-ast"
                        confidence = (
                            0.78 if definition_count == 1 else 0.62
                        ) if parser_is_exact else (0.58 if definition_count == 1 else 0.42)
                        callers.append(
                            {
                                "caller": symbol,
                                "target_name": target,
                                "call_site": call,
                                "edge_confidence": confidence,
                                "resolution": (
                                    "unique_definition_name_candidate"
                                    if definition_count == 1
                                    else "ambiguous_definition_name_candidate"
                                ),
                            }
                        )
                        if len(callers) >= limit:
                            return callers
        return callers

    def callees_of_symbol(
        self, role: str, definition: dict[str, Any], limit: int = 24
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for call in definition["calls"]:
            target = call["target_name"]
            candidates = self.read_symbol(role, target, limit=8)
            exact_parser = definition["parser"] == "python-ast"
            confidence = (
                0.78 if len(candidates) == 1 else 0.62
            ) if exact_parser else (0.58 if len(candidates) == 1 else 0.42)
            result.append(
                {
                    "caller": definition,
                    "call": call,
                    "callee_candidates": candidates,
                    "resolution": (
                        "unique_definition_name_candidate"
                        if len(candidates) == 1
                        else "ambiguous_definition_name_candidate"
                        if candidates
                        else "unresolved_name_candidate"
                    ),
                    "edge_confidence": confidence,
                }
            )
            if len(result) >= limit:
                break
        return result

    def find_callees(self, role: str, symbol_name: str, limit: int = 24) -> list[dict[str, Any]]:
        definitions = self.read_symbol(role, symbol_name, limit=32)
        result: list[dict[str, Any]] = []
        for definition in definitions:
            result.extend(
                self.callees_of_symbol(role, definition, limit=max(1, limit - len(result)))
            )
            if len(result) >= limit:
                break
        return result

    def read_symbol(self, role: str, name: str, limit: int = 8) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        token = name.rsplit(".", 1)[-1]
        for path in self.find_files_containing(role, token):
            for symbol in self.symbols_in_file(role, path):
                if symbol["name"] == token or symbol["qualified_name"] == name:
                    results.append(symbol)
                    if len(results) >= limit:
                        return results
        return results


def _source_evidence(
    evidence_id: str,
    observation: str,
    *,
    path: str,
    symbol: str | None,
    first: int,
    last: int,
    revision: str,
    content: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "kind": "source",
        "observation": observation,
        "path": path,
        "symbol": symbol,
        "line_start": max(1, first),
        "line_end": max(max(1, first), last),
        "version": revision,
        "content_hash": sha256_text(content),
        "provenance": provenance,
    }


def _hunk_matches_source(hunk: Mapping[str, Any], role: str, source: str) -> list[int]:
    """Return source line numbers whose patch text disagrees with the snapshot."""

    source_lines = source.splitlines()
    mismatches: list[int] = []
    for row in hunk.get("lines", []):
        if row.get("kind") == "context":
            line = row.get("old_line" if role == "vulnerable" else "new_line")
        elif role == "vulnerable" and row.get("kind") == "removed":
            line = row.get("line")
        elif role == "fixed" and row.get("kind") == "added":
            line = row.get("line")
        else:
            continue
        if not isinstance(line, int) or line < 1 or line > len(source_lines):
            mismatches.append(int(line) if isinstance(line, int) else 0)
        elif source_lines[line - 1] != row.get("text", ""):
            mismatches.append(line)
    return mismatches


def build_source_context(
    case: Mapping[str, Any],
    raw_diff: str,
    diff_summary: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Map all patch hunks to both source snapshots and build bounded slices."""

    reader = SourceRepositoryReader(case)
    policy = case.get("policy", {})
    max_depth = int(policy.get("source_call_depth", 3))
    max_chars = int(policy.get("source_context_limit_chars", 50000))
    _files, hunks, parsed_complete = parse_patch_hunks(raw_diff)
    slices: list[dict[str, Any]] = []
    changed_symbols: list[dict[str, Any]] = []
    source_evidence: list[dict[str, Any]] = []
    missing: list[str] = []
    mapped_hunks = 0
    parser_counts: dict[str, int] = {}
    changed_targets: list[dict[str, Any]] = []

    for hunk in hunks:
        hunk_mapped = True
        if not hunk.get("old_path") and not hunk.get("new_path"):
            hunk_mapped = False
            missing.append(f"No source path could be resolved for {hunk['hunk_id']}")
        for role, path_key, line_key in (
            ("vulnerable", "old_path", "old_start"),
            ("fixed", "new_path", "new_start"),
        ):
            path = hunk.get(path_key)
            if not path:
                continue
            try:
                source = reader.read_file(role, path)
            except (OSError, RuntimeError, ValueError) as exc:
                hunk_mapped = False
                missing.append(f"{role} source unavailable for {path}: {str(exc)[:240]}")
                continue
            mismatches = _hunk_matches_source(hunk, role, source)
            if mismatches:
                hunk_mapped = False
                shown = ", ".join(str(item) for item in mismatches[:8])
                missing.append(
                    f"Patch/source mismatch for {hunk['hunk_id']} in {role}:{path} "
                    f"at line(s) {shown}"
                )
            symbols = parse_source_symbols(source, path, reader.revision_ref(role), reader.language)
            parser = (
                symbols[0]["parser"]
                if symbols
                else "python-ast"
                if reader.language == "python"
                else f"{reader.language}-structural-candidate"
            )
            parser_counts[parser] = parser_counts.get(parser, 0) + 1
            line_candidates = [
                int(row["line"])
                for row in hunk.get("lines", [])
                if (role == "vulnerable" and row["kind"] == "removed")
                or (role == "fixed" and row["kind"] == "added")
            ]
            if not line_candidates:
                line_candidates = [int(hunk.get(line_key, 1))]
            enclosing = [
                item
                for item in symbols
                if any(item["line_start"] <= line <= item["line_end"] for line in line_candidates)
            ]
            selected = (
                min(enclosing, key=lambda item: item["line_end"] - item["line_start"])
                if enclosing
                else None
            )
            if selected:
                enriched = {
                    key: selected[key]
                    for key in (
                        "symbol_id",
                        "name",
                        "qualified_name",
                        "path",
                        "revision",
                        "line_start",
                        "line_end",
                        "kind",
                        "parser",
                        "confidence",
                    )
                }
                enriched.update({"hunk_id": hunk["hunk_id"], "role": role})
                changed_symbols.append(enriched)
                if role == "vulnerable" and not any(
                    item["symbol_id"] == selected["symbol_id"] for item in changed_targets
                ):
                    changed_targets.append(selected)
                slice_content = selected["content"]
                first = selected["line_start"]
                last = selected["line_end"]
                symbol_name = selected["qualified_name"]
            else:
                # Module-level/configuration changes still get a source slice.
                anchor_line = max(1, int(hunk.get(line_key, 1)))
                first = max(1, anchor_line - 12)
                last = anchor_line + 24
                slice_content = _slice_lines(source, first, last, 10000)
                symbol_name = None
                missing.append(
                    f"No enclosing function/method found for {hunk['hunk_id']} "
                    f"in {role}:{path}"
                )
            slice_record = {
                "slice_id": f"SLICE-{hunk['hunk_id']}-{role}",
                "hunk_id": hunk["hunk_id"],
                "role": role,
                "revision": reader.revision_ref(role),
                "path": path,
                "symbol": symbol_name,
                "line_start": first,
                "line_end": last,
                "parser": parser,
                "confidence": selected["confidence"] if selected else 0.5,
                "content": slice_content,
                "content_hash": sha256_text(slice_content),
            }
            slices.append(slice_record)
            source_evidence.append(
                _source_evidence(
                    f"EV-SOURCE-{len(source_evidence) + 1:04d}",
                    f"Source slice for {hunk['hunk_id']} ({role})",
                    path=path,
                    symbol=symbol_name,
                    first=first,
                    last=last,
                    revision=reader.revision_ref(role),
                    content=slice_content,
                    provenance={
                        "analyzer": slice_record["parser"],
                        "slice_id": slice_record["slice_id"],
                        "hunk_id": hunk["hunk_id"],
                        "static_only": True,
                        "content_truncated": bool(
                            selected and selected.get("content_truncated")
                        ),
                    },
                )
            )
        if hunk_mapped:
            mapped_hunks += 1

    # Backward caller slicing to bounded depth. Each edge is a candidate static
    # call relation with a source location, never a runtime reachability claim.
    caller_paths: list[dict[str, Any]] = []
    source_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def add_symbol_slice(symbol: dict[str, Any], role: str) -> None:
        cache_key = (role, symbol["symbol_id"])
        if cache_key in source_cache:
            return
        source_cache[cache_key] = symbol
        slices.append(
            {
                "slice_id": f"SOURCE-{len(source_cache):03d}",
                "hunk_id": None,
                "role": role,
                "revision": symbol["revision"],
                "path": symbol["path"],
                "symbol": symbol["qualified_name"],
                "line_start": symbol["line_start"],
                "line_end": symbol["line_end"],
                "parser": symbol["parser"],
                "confidence": symbol["confidence"],
                "content": symbol["content"],
                "truncated": bool(symbol.get("content_truncated")),
                "content_hash": sha256_text(symbol["content"]),
            }
        )

    queue: deque[tuple[dict[str, Any], list[dict[str, Any]], int]] = deque(
        (target, [target], 0) for target in changed_targets
    )
    seen_paths: set[tuple[str, ...]] = set()
    while queue and len(caller_paths) < 64:
        target, path_chain, depth = queue.popleft()
        if depth >= max_depth:
            continue
        try:
            callers = reader.find_callers("vulnerable", target["name"], limit=32)
        except (OSError, RuntimeError, ValueError) as exc:
            missing.append(f"Caller lookup failed for {target['name']}: {str(exc)[:200]}")
            continue
        for relation in callers:
            caller = relation["caller"]
            if caller["symbol_id"] in {item["symbol_id"] for item in path_chain}:
                continue
            new_chain = [caller, *path_chain]
            path_key = tuple(item["symbol_id"] for item in new_chain)
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)
            call = relation["call_site"]
            source_snippet = _slice_lines(
                reader.read_file("vulnerable", caller["path"]),
                caller["line_start"],
                caller["line_end"],
                10000,
            )
            edge_evidence = _source_evidence(
                f"EV-CALL-{len(source_evidence) + 1:04d}",
                f"Static call candidate {caller['qualified_name']} → {target['qualified_name']}",
                path=caller["path"],
                symbol=caller["qualified_name"],
                first=call["line"],
                last=call["line"],
                revision=reader.revision_ref("vulnerable"),
                content=source_snippet,
                provenance={
                    "analyzer": caller["parser"],
                    "relation": "candidate_call",
                    "target": target["qualified_name"],
                    "call_site": call,
                    "content_truncated": bool(caller.get("content_truncated")),
                },
            )
            source_evidence.append(edge_evidence)
            path_record = {
                "path_id": f"CALLPATH-{len(caller_paths) + 1:03d}",
                "revision": reader.revision_ref("vulnerable"),
                "direction": "caller_to_patched_symbol",
                "symbols": [
                    {
                        "symbol_id": item["symbol_id"],
                        "qualified_name": item["qualified_name"],
                        "path": item["path"],
                        "line_start": item["line_start"],
                        "line_end": item["line_end"],
                        "parser": item["parser"],
                    }
                    for item in new_chain
                ],
                "call_site": call,
                "resolution": relation["resolution"],
                "evidence_ids": [edge_evidence["evidence_id"]],
                "confidence": relation["edge_confidence"],
            }
            caller_paths.append(path_record)
            add_symbol_slice(caller, "vulnerable")
            queue.append((caller, new_chain, depth + 1))

    # Forward callee slicing resolves names to source definitions when possible.
    # Unresolved and ambiguous names remain explicit candidates in the bundle.
    callee_paths: list[dict[str, Any]] = []
    callee_candidates: list[dict[str, Any]] = []
    forward_queue: deque[tuple[dict[str, Any], list[dict[str, Any]], int]] = deque(
        (target, [target], 0) for target in changed_targets
    )
    seen_forward_paths: set[tuple[str, ...]] = set()
    while forward_queue and len(callee_paths) < 64 and len(callee_candidates) < 128:
        caller, path_chain, depth = forward_queue.popleft()
        if depth >= max_depth:
            continue
        try:
            relations = reader.callees_of_symbol("vulnerable", caller, limit=32)
        except (OSError, RuntimeError, ValueError) as exc:
            missing.append(f"Callee lookup failed for {caller['name']}: {str(exc)[:200]}")
            continue
        for relation in relations:
            call = relation["call"]
            candidates = relation["callee_candidates"]
            callee_evidence = _source_evidence(
                f"EV-CALLEE-{len(source_evidence) + 1:04d}",
                f"Static callee candidate {caller['qualified_name']} → {call['target_name']}",
                path=caller["path"],
                symbol=caller["qualified_name"],
                first=int(call["line"]),
                last=int(call["line"]),
                revision=reader.revision_ref("vulnerable"),
                content=caller["content"],
                provenance={
                    "analyzer": caller["parser"],
                    "relation": "candidate_callee",
                    "resolution": relation["resolution"],
                    "call_site": call,
                    "content_truncated": bool(caller.get("content_truncated")),
                },
            )
            source_evidence.append(callee_evidence)
            candidate_record = {
                "source_symbol_id": caller["symbol_id"],
                "source_symbol": caller["qualified_name"],
                "target_name": call["target_name"],
                "call_site": call,
                "resolution": relation["resolution"],
                "candidate_symbol_ids": [item["symbol_id"] for item in candidates],
                "evidence_ids": [callee_evidence["evidence_id"]],
                "confidence": relation["edge_confidence"],
            }
            if len(callee_candidates) < 128:
                callee_candidates.append(candidate_record)
            for callee in candidates:
                if callee["symbol_id"] in {item["symbol_id"] for item in path_chain}:
                    continue
                new_chain = [*path_chain, callee]
                path_key = tuple(item["symbol_id"] for item in new_chain)
                if path_key in seen_forward_paths:
                    continue
                seen_forward_paths.add(path_key)
                path_record = {
                    "path_id": f"CALLEE-PATH-{len(callee_paths) + 1:03d}",
                    "revision": reader.revision_ref("vulnerable"),
                    "direction": "changed_symbol_to_callee",
                    "symbols": [
                        {
                            "symbol_id": item["symbol_id"],
                            "qualified_name": item["qualified_name"],
                            "path": item["path"],
                            "line_start": item["line_start"],
                            "line_end": item["line_end"],
                            "parser": item["parser"],
                        }
                        for item in new_chain
                    ],
                    "call_site": call,
                    "resolution": relation["resolution"],
                    "evidence_ids": [callee_evidence["evidence_id"]],
                    "confidence": relation["edge_confidence"],
                }
                callee_paths.append(path_record)
                add_symbol_slice(callee, "vulnerable")
                forward_queue.append((callee, new_chain, depth + 1))

    # Bound the serialized source context while retaining a full patch hash and
    # all hunk records in the analysis artifact.
    remaining = max_chars
    bounded_slices: list[dict[str, Any]] = []
    for item in slices:
        if remaining <= 0:
            missing.append(
                "Source slice budget reached; use read-only source queries for omitted context"
            )
            break
        content = item["content"][:remaining]
        remaining -= len(content)
        bounded_slices.append(
            {
                **item,
                "content": content,
                "truncated": bool(item.get("truncated"))
                or len(content) < len(item["content"]),
            }
        )

    sufficient = bool(
        parsed_complete and hunks and mapped_hunks == len(hunks) and bounded_slices
    )
    if not parsed_complete:
        missing.append("Patch parser did not account for every hunk header")
    if mapped_hunks != len(hunks):
        missing.append("At least one patch hunk could not be matched to source snapshots")
    if not changed_targets:
        missing.append("No changed callable symbol was resolved in the vulnerable snapshot")

    bundle = SourceContextBundle(
        patch_sha256=str(
            diff_summary.get("patch_hash", sha256_text(raw_diff))
        ),
        patch_complete=parsed_complete,
        hunk_count=len(hunks),
        mapped_hunk_count=mapped_hunks,
        status="sufficient" if sufficient else "insufficient",
        changed_symbols=changed_symbols,
        caller_paths=caller_paths,
        callee_paths=callee_paths,
        callee_candidates=callee_candidates,
        source_slices=bounded_slices,
        missing_context=list(dict.fromkeys(missing)),
        parser_coverage=parser_counts,
        evidence_ids=[item["evidence_id"] for item in source_evidence],
    )
    return bundle.model_dump(mode="json"), source_evidence


def execute_source_query(
    case: Mapping[str, Any], query: SourceQuery | Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Execute one validated, bounded, read-only source query."""

    request = query if isinstance(query, SourceQuery) else SourceQuery.model_validate(query)
    reader = SourceRepositoryReader(case)
    if request.kind == "read_test":
        test_path = request.path.lower() if request.path else ""
        test_name = Path(test_path).name
        if not request.path or not (
            test_name.startswith("test_")
            or test_name.endswith(
                (
                    "test.py",
                    "_test.py",
                    "test.java",
                    "_test.go",
                    ".spec.js",
                    ".test.js",
                    ".test.ts",
                )
            )
        ):
            raise ValueError("read_test requires a path that looks like a test source")
        content = reader.read_file(request.revision, request.path)
        result = [
            {
                "path": request.path,
                "revision": reader.revision_ref(request.revision),
                "content": content[:12000],
            }
        ]
    elif not request.symbol:
        raise ValueError(f"{request.kind} requires a symbol name")
    elif request.kind == "read_symbol":
        result = reader.read_symbol(request.revision, request.symbol)
    elif request.kind == "find_callers":
        target = request.symbol.rsplit(".", 1)[-1]
        result = reader.find_callers(request.revision, target, limit=32)
        if request.depth > 1:
            expanded: list[dict[str, Any]] = []
            queue = deque(
                (item["caller"], 1, [item["caller"]["qualified_name"]]) for item in result
            )
            while queue and len(expanded) < 64:
                symbol, depth, chain = queue.popleft()
                expanded.append({"depth": depth, "chain": chain, "symbol": symbol})
                if depth >= request.depth:
                    continue
                for relation in reader.find_callers(request.revision, symbol["name"], limit=24):
                    parent = relation["caller"]
                    if parent["qualified_name"] not in chain:
                        queue.append((parent, depth + 1, [parent["qualified_name"], *chain]))
            result = expanded
    else:
        result = reader.find_callees(request.revision, request.symbol.rsplit(".", 1)[-1])
        if request.depth > 1:
            expanded = [
                {
                    "depth": 1,
                    **item,
                    "chain": [
                        item["caller"]["qualified_name"],
                        *[candidate["qualified_name"] for candidate in item["callee_candidates"]],
                    ],
                }
                for item in result
            ]
            queue = deque(
                (candidate, 1, [item["caller"]["qualified_name"], candidate["qualified_name"]])
                for item in result
                for candidate in item["callee_candidates"]
            )
            while queue and len(expanded) < 64:
                symbol, depth, chain = queue.popleft()
                if depth >= request.depth:
                    continue
                for relation in reader.callees_of_symbol(request.revision, symbol, limit=24):
                    names = [item["qualified_name"] for item in relation["callee_candidates"]]
                    expanded.append(
                        {
                            "depth": depth + 1,
                            **relation,
                            "chain": [*chain, *names],
                        }
                    )
                    for candidate in relation["callee_candidates"]:
                        if candidate["qualified_name"] not in chain:
                            queue.append(
                                (candidate, depth + 1, [*chain, candidate["qualified_name"]])
                            )
            result = expanded

    bounded_result: list[dict[str, Any]] = []
    for item in result[:12]:
        if not isinstance(item, dict):
            continue
        value = dict(item)
        for key in ("caller", "symbol"):
            nested = value.get(key)
            if isinstance(nested, dict) and "content" in nested:
                original_content = str(nested["content"])
                nested = {
                    **nested,
                    "content": original_content[:4000],
                    "query_content_truncated": bool(
                        nested.get("content_truncated")
                        or nested.get("query_content_truncated")
                        or len(original_content) > 4000
                    ),
                }
                value[key] = nested
        candidates = value.get("callee_candidates")
        if isinstance(candidates, list):
            bounded_candidates = []
            for candidate in candidates[:4]:
                original_content = str(candidate.get("content", ""))
                bounded_candidates.append(
                    {
                        **candidate,
                        "content": original_content[:4000],
                        "query_content_truncated": bool(
                            candidate.get("content_truncated")
                            or candidate.get("query_content_truncated")
                            or len(original_content) > 4000
                        ),
                    }
                )
            value["callee_candidates"] = bounded_candidates
        if "content" in value:
            original_content = str(value["content"])
            value["content"] = original_content[:4000]
            value["query_content_truncated"] = len(original_content) > 4000
        bounded_result.append(value)
    result = bounded_result
    truncated = False

    def serialized_size() -> int:
        return len(json.dumps(result, sort_keys=True, separators=(",", ":"), default=str))

    while len(result) > 1 and serialized_size() > 16000:
        result.pop()
        truncated = True
    if serialized_size() > 16000:
        for item in result:
            for key in ("caller", "symbol"):
                nested = item.get(key)
                if isinstance(nested, dict) and "content" in nested:
                    nested["content"] = str(nested["content"])[:1000]
                    nested["query_content_truncated"] = True
            for candidate in item.get("callee_candidates", []):
                candidate["content"] = str(candidate.get("content", ""))[:1000]
                candidate["query_content_truncated"] = True
        truncated = True
    compact_json = json.dumps(result, sort_keys=True, separators=(",", ":"), default=str)
    evidence: list[dict[str, Any]] = []
    for index, item in enumerate(result[:32], start=1):
        symbols = [item.get("caller") or item.get("symbol") or item]
        symbols.extend(item.get("callee_candidates", []))
        for symbol in symbols:
            if not isinstance(symbol, dict) or not symbol.get("path"):
                continue
            content = str(symbol.get("content", ""))
            digest_input = (
                f"{request.kind}:{request.revision}:{index}:"
                f"{symbol.get('symbol_id')}:{content}"
            )
            first_line = int(symbol.get("line_start", 1))
            original_last_line = symbol.get("line_end")
            last_line = (
                min(int(original_last_line), first_line + content.count("\n"))
                if original_last_line is not None
                else first_line + content.count("\n")
            )
            evidence.append(
                _source_evidence(
                    f"EV-TOOL-{hashlib.sha256(digest_input.encode()).hexdigest()[:12]}",
                    "Read-only source tool result: "
                    f"{request.kind} {request.symbol or request.path}",
                    path=symbol["path"],
                    symbol=symbol.get("qualified_name"),
                    first=first_line,
                    last=last_line,
                    revision=reader.revision_ref(request.revision),
                    content=content,
                    provenance={
                        "tool": request.kind,
                        "read_only": True,
                        "result_index": index,
                        "content_truncated": original_last_line is not None
                        and int(original_last_line) > last_line
                        or bool(symbol.get("query_content_truncated")),
                    },
                )
            )
    return {
        "query": request.model_dump(mode="json"),
        "result": result,
        "truncated": truncated,
        "result_sha256": sha256_text(compact_json),
        "read_only": True,
    }, evidence
