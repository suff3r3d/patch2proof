"""Build the machine-readable proof bundle used by the final report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def _canonical(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    return value


def build_proof_bundle(state: Mapping[str, Any], *, output_dir: Path) -> dict[str, Any]:
    """Create a conservative claim envelope from persisted state.

    A bundle is ``confirmed`` only when the skeptic verdict and every coverage
    dimension agree. This rule is intentionally duplicated outside the LLM
    prompt so a report cannot be upgraded by prose generation.
    """

    review = _canonical(state.get("review") or {})
    coverage = _canonical(state.get("coverage") or {})
    required = (
        "static_reachability",
        "dynamic_reachability",
        "semantic_transition",
        "counterfactual_separation",
        "repeatable",
        "source_grounded",
    )
    coverage_complete = bool(coverage) and all(bool(coverage.get(item)) for item in required)
    validation = _canonical(state.get("validation") or {})
    source_context = _canonical(state.get("source_context") or {})
    source_grounded = bool(
        source_context.get("status") == "sufficient"
        and source_context.get("patch_complete")
        and source_context.get("hunk_count", 0) == source_context.get("mapped_hunk_count", -1)
        and any(
            item.get("role") == "vulnerable"
            for item in source_context.get("changed_symbols", [])
        )
    )
    reasoning = _canonical(state.get("reasoning") or [])
    reasoning_provider_backed = bool(reasoning) and all(
        item.get("mode") in {"openai", "ollama"} for item in reasoning
    )
    confirmed = (
        review.get("verdict") == "confirmed"
        and coverage_complete
        and not validation.get("simulation", False)
        and not validation.get("violations")
        and reasoning_provider_backed
        and source_grounded
    )
    artifact_names = ["case.json"]
    artifact_names.extend(name for name in state.get("discovery_artifacts", [])
                          if isinstance(name, str) and (
                              name in {"discovery-nvd.json", "discovery-osv.json",
                                       "revision-discovery-result.json"}
                              or name in {f"discovery-commit-{index}.json" for index in range(8)}
                          ))
    state_artifacts = {
        "raw_diff": "raw-patch.diff",
        "diff_summary": "patch-analysis.json",
        "source_context": "source-context.json",
        "vulnerability_contract": "vulnerability-contract.json",
        "reproduction_graph": "reproduction-graph.json",
        "docker_spec": "docker-plan.json",
        "environment_profile": "environment-profile.json",
        "images": "images.json",
        "safe_poc_plan": "safe-poc-plan.json",
        "safe_poc": "safepoc.json",
        "validation": "validation.json",
        "coverage": "coverage.json",
        "review": "skeptic-review.json",
    }
    artifact_names.extend(
        filename for key, filename in state_artifacts.items() if state.get(key) is not None
    )
    if state.get("raw_diff") is not None:
        artifact_names.append("source-identities.json")
    if state.get("images") is not None and (output_dir / "source-pair.json").exists():
        artifact_names.append("source-pair.json")
    artifact_names.extend(
        name for name in (
            "build-vulnerable.log", "build-fixed.log",
            "image-vulnerable.json", "image-fixed.json",
        )
        if (output_dir / name).exists()
    )
    reasoning_stages = {item.get("stage") for item in reasoning}
    if "hypothesis" in reasoning_stages:
        artifact_names.append("reasoning-initial.json")
    if "safe_poc_plan" in reasoning_stages:
        artifact_names.append("reasoning-plan.json")
    overlay_names = [
        f"attempt-{item.get('attempt_id')}.json"
        for item in state.get("attempts", [])
        if item.get("attempt_id")
    ] + [
        f"{item.get('feedback_id')}.json"
        for item in state.get("feedback", [])
        if item.get("feedback_id")
    ]
    reasoning_names = [
        f"{item.get('reasoning_id')}.json"
        for item in state.get("reasoning", [])
        if item.get("reasoning_id") not in {"reasoning-initial", "reasoning-plan"}
        and item.get("reasoning_id")
    ]
    artifact_names.extend(
        ["skill-candidates.json", "skill-memory-summary.json", *reasoning_names, *overlay_names]
    )
    present = [name for name in artifact_names if (output_dir / name).exists()]
    payload = {
        "schema_version": "proof-bundle/0.4.0",
        "case_id": (state.get("case") or {}).get("case_id"),
        "claim_status": (
            "not_executed"
            if state.get("discovery_result", {}).get("status") in {"ambiguous", "failed"}
            else "blocked"
            if state.get("status") in {"blocked", "error", "environment_review_required"}
            else "confirmed" if confirmed else "candidate"
        ),
        "claim_rule": (
            "confirmed iff skeptic verdict=confirmed, all six coverage gates are true, "
            "validation is non-simulated, violations is empty, and every reasoning artifact "
            "is provider-backed; the full patch and changed source symbols are mapped"
        ),
        "review": review,
        "validation": validation,
        "coverage": coverage,
        "reasoning": reasoning,
        "reasoning_provider_backed": reasoning_provider_backed,
        "source_grounded": source_grounded,
        "discovery_result": state.get("discovery_result"),
        "artifact_names": present,
        "artifact_paths": [str(output_dir / name) for name in present],
        "graph_id": (state.get("reproduction_graph") or {}).get("graph_id"),
        "attempt_ids": [item.get("attempt_id") for item in state.get("attempts", [])],
        "feedback_ids": [item.get("feedback_id") for item in state.get("feedback", [])],
        "skill_application_ids": [
            item.get("application_id") for item in state.get("skill_applications", [])
        ],
    }
    digest = hashlib.sha256(
        json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**payload, "bundle_sha256": digest}
