"""Case and policy loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .models import CaseManifest


def load_mapping(path: str | Path) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() == ".json":
        value = json.loads(text)
    else:
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a mapping in {file_path}")
    return value


def load_case(path: str | Path) -> CaseManifest:
    return CaseManifest.model_validate(load_mapping(path))


def load_policy(path: str | Path = "config/policy.yaml") -> dict[str, Any]:
    return load_mapping(path)
