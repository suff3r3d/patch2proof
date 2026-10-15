"""Extension protocols for source, binary and application-specific adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol


class SourceAdapter(Protocol):
    """Turn a source/version pair into normalized patch evidence."""

    def collect(self, case: dict[str, Any]) -> dict[str, Any]: ...


class BinaryDiffAdapter(Protocol):
    """Optional bridge for DiffRays/Ghidra/IDA-style binary analysis."""

    def diff(self, vulnerable_binary: Path, fixed_binary: Path) -> dict[str, Any]: ...

    def extract_changed_functions(self, diff_artifact: dict[str, Any]) -> list[dict[str, Any]]: ...


class CaseTestAdapter(Protocol):
    """Reviewed, case-specific test registry used by the sandbox worker."""

    case_id: str

    def allowed_test_ids(self) -> set[str]: ...

    def build_context(self, role: Literal["vulnerable", "fixed"]) -> Path: ...

    def collect_observation(self, run_directory: Path) -> dict[str, Any]: ...

    def run_role(
        self,
        role: Literal["vulnerable", "fixed"],
        poc: dict[str, Any],
        run_directory: Path,
    ) -> dict[str, Any]: ...
