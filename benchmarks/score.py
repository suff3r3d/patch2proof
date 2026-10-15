"""Dependency-light scorer for Patch2Proof case-result JSON records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def load_records(paths: list[str], include_simulation: bool = False) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for value in paths:
        path = Path(value)
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("simulation") and not include_simulation:
                continue
            records.append(item)
    return records


def score(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    confirmed = [item for item in records if item.get("claim_status") == "confirmed"]
    true_confirmed = [item for item in confirmed if item.get("ground_truth") == "confirmed"]
    valid = [item for item in records if item.get("valid_differential")]
    edge_denominator = sum(float(item.get("graph_edges_total", 0)) for item in records)
    edge_numerator = sum(float(item.get("graph_edges_supported", 0)) for item in records)
    return {
        "cases": total,
        "valid_differential_rate": len(valid) / total if total else 0.0,
        "confirmation_precision": len(true_confirmed) / len(confirmed) if confirmed else 0.0,
        "false_confirmation_count": len(confirmed) - len(true_confirmed),
        "evidence_completeness_mean": mean(
            float(item.get("evidence_completeness", 0.0)) for item in records
        )
        if total
        else 0.0,
        "graph_edge_completion": edge_numerator / edge_denominator if edge_denominator else 0.0,
        "attempts_mean": mean(float(item.get("attempts", 0)) for item in records) if total else 0.0,
        "duration_seconds_mean": mean(float(item.get("duration_seconds", 0.0)) for item in records)
        if total
        else 0.0,
        "safety_violation_rate": sum(float(item.get("safety_violations", 0)) for item in records)
        / total
        if total
        else 0.0,
        "fcs_memory_hit_rate": sum(bool(item.get("fcs_memory_hit")) for item in records) / total
        if total
        else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("records", nargs="+", help="JSON result files")
    parser.add_argument("--include-simulation", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            score(load_records(args.records, args.include_simulation)), indent=2, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
