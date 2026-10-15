"""Small, explicit test-adapter registry.

Adapters are the only bridge from a case's registered test ID to runtime
observations. The built-in adapter is a synthetic CI fixture: it exercises the
oracle and graph contracts without pretending that a real target was run.
Target projects should register a reviewed adapter in their own lab package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..models import CoverageVector, SafePoC, ValidationResult

RoleObservation = Callable[[SafePoC, str, Path], dict[str, Any]]


def _fixture_simulated_observation(poc: SafePoC, role: str, run_dir: Path) -> dict[str, Any]:
    """Return a deterministic paired observation for contract/integration tests."""

    vulnerable = role == "vulnerable"
    return {
        "adapter_id": "fixture_simulated_differential",
        "role": role,
        "simulation": True,
        "preconditions_satisfied": True,
        "entrypoint_invoked": True,
        "patch_slice_reached": True,
        "semantic_transition": vulnerable,
        "safe_observable": vulnerable,
        "oracle_signal": vulnerable,
        "repeatable": True,
        "run_directory": str(run_dir),
        "poc_id": poc.poc_id,
    }


ADAPTERS: dict[str, RoleObservation] = {
    "fixture_simulated_differential": _fixture_simulated_observation,
}


def register_adapter(adapter_id: str, adapter: RoleObservation) -> None:
    """Register a reviewed adapter in the worker process.

    Registration is an application/deployment action, never an LLM action.
    IDs are namespaced as identifiers to keep them out of shell/URL syntax.
    """

    if not adapter_id or any(character in adapter_id for character in " /\\\t\n"):
        raise ValueError("adapter_id must be a non-empty identifier")
    if adapter_id == "fixture_simulated_differential":
        raise ValueError("the built-in simulation adapter cannot be replaced")
    ADAPTERS[adapter_id] = adapter


def run_registered_differential(
    registered_test_id: str,
    poc: SafePoC,
    artifact_dir: Path,
) -> ValidationResult:
    adapter = ADAPTERS.get(registered_test_id)
    if adapter is None:
        raise NotImplementedError(
            "No reviewed adapter is registered for this case; add a target-local adapter "
            "that returns typed observations instead of exposing a command to the LLM"
        )
    observations = {
        role: adapter(poc, role, artifact_dir / f"adapter-{registered_test_id}-{role}")
        for role in ("vulnerable", "fixed")
    }
    vulnerable = observations["vulnerable"]
    fixed = observations["fixed"]
    oracle_match = bool(vulnerable.get("oracle_signal")) and not bool(fixed.get("oracle_signal"))
    differential = (
        bool(vulnerable.get("semantic_transition"))
        and not bool(fixed.get("semantic_transition"))
        and bool(vulnerable.get("entrypoint_invoked"))
        and bool(fixed.get("entrypoint_invoked"))
    )
    coverage = {
        "static_reachability": True,
        "dynamic_reachability": bool(vulnerable.get("patch_slice_reached")),
        "semantic_transition": bool(vulnerable.get("semantic_transition")),
        "counterfactual_separation": differential,
        "repeatable": bool(vulnerable.get("repeatable")) and bool(fixed.get("repeatable")),
    }
    return ValidationResult(
        status="passed" if oracle_match and differential else "failed",
        vulnerable_observation=vulnerable,
        fixed_observation=fixed,
        oracle_match=oracle_match,
        differential=differential,
        logs=[f"registered adapter {registered_test_id} completed for both roles"],
        adapter_id=registered_test_id,
        simulation=bool(vulnerable.get("simulation") or fixed.get("simulation")),
        coverage=CoverageVector.model_validate(coverage),
    )
