"""Constrained SafePoC planning.

The generator emits observables that are useful for a defensive lab while
excluding weaponized actions. It never emits a shell command or a payload.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from .models import (
    Hypothesis,
    ReproductionGraph,
    SafeAction,
    SafePoC,
    SafePoCPlan,
    Skill,
    VulnerabilityContract,
)


def _scaffold(
    observation: SafeAction,
    *,
    graph: ReproductionGraph | None,
    contract: VulnerabilityContract | None,
) -> list[SafeAction]:
    """Add typed fixture/entrypoint actions before the bounded oracle action."""

    entrypoint = (
        contract.required_entrypoints[0]
        if contract and contract.required_entrypoints
        else "registered://case-entrypoint"
    )
    return [
        SafeAction(
            action_id="A-FIX-001",
            op="establish_fixture_state",
            target="/proof/fixture/state.json",
            value="prepared",
            expected="fixture-ready",
            transition_ids=["node-precondition"],
        ),
        SafeAction(
            action_id="A-ENTRY-001",
            op="invoke_entrypoint",
            target=entrypoint
            if entrypoint.startswith("registered://")
            else "registered://case-entrypoint",
            expected="entrypoint-invoked",
            transition_ids=["node-entrypoint", "node-patch-slice-reached"],
        ),
        observation,
    ]


def generate_safe_poc(
    hypothesis: Hypothesis,
    graph: ReproductionGraph | None = None,
    contract: VulnerabilityContract | None = None,
    selected_skill: Skill | None = None,
    plan: SafePoCPlan | None = None,
    require_reasoned_plan: bool = True,
) -> SafePoC:
    """Create a non-weaponized SafePoC intermediate representation.

    ``selected_skill`` is intentionally metadata-only in the first plan. It
    can influence bounded repair operators, but it cannot inject a command,
    payload, or arbitrary target into this IR.
    """

    if require_reasoned_plan and plan is None:
        raise ValueError(
            "Production SafePoC compilation requires a provider-backed SafePoCPlan; "
            "heuristic generation is test-only"
        )

    vulnerability_class = hypothesis.vulnerability_class.lower()
    oracle: Literal["canary_content", "marker_file", "mock_hit", "log_record", "exit_status"]
    if plan is not None:
        allowed_prefixes = {
            "read_canary": "/proof/fixture/",
            "write_marker": "/proof/",
            "http_mock_request": "mock://",
            "assert_log": "/proof/logs/",
            "observe_exit": "/proof/",
            "observe_trace": "/proof/trace/",
            "assert_state": "/proof/",
        }
        prefix = allowed_prefixes.get(plan.observation_op)
        if (
            prefix is None
            or ".." in PurePosixPath(plan.target).parts
            or not plan.target.startswith(prefix)
        ):
            raise ValueError("SafePoC plan target is outside the operation boundary")
        if graph is not None and plan.graph_id != graph.graph_id:
            raise ValueError("SafePoC plan graph_id does not match the current graph")
        actions = _scaffold(
            SafeAction(
                action_id="A-OBS-LLM-001",
                op=plan.observation_op,
                target=plan.target,
                value=plan.value,
                expected=plan.expected,
                transition_ids=plan.expected_transitions or ["node-safe-observable"],
            ),
            graph=graph,
            contract=contract,
        )
        oracle = plan.oracle
        vulnerable_expectation = plan.vulnerable_expectation
        fixed_expectation = plan.fixed_expectation
        objective = plan.objective
        generator = "patch2proof.safe_poc.reasoned_compiler"
    elif (
        "22" in vulnerability_class
        or "73" in vulnerability_class
        or "file" in hypothesis.title.lower()
    ):
        actions = _scaffold(
            SafeAction(
                action_id="A-OBS-001",
                op="read_canary",
                target="/proof/fixture/canary.txt",
                expected="canary-content",
                transition_ids=["node-safe-observable"],
            ),
            graph=graph,
            contract=contract,
        )
        oracle = "canary_content"
        vulnerable_expectation = {"canary_observed": True}
        fixed_expectation = {"canary_observed": False}
        objective = "Demonstrate only whether the controlled canary crosses the file boundary."
        generator = "patch2proof.safe_poc.heuristic-test-only"
    elif "78" in vulnerability_class or "command" in hypothesis.title.lower():
        actions = _scaffold(
            SafeAction(
                action_id="A-OBS-001",
                op="write_marker",
                target="/proof/marker.txt",
                value="P2P_MARKER",
                expected="marker-created",
                transition_ids=["node-safe-observable"],
            ),
            graph=graph,
            contract=contract,
        )
        oracle = "marker_file"
        vulnerable_expectation = {"marker_created": True}
        fixed_expectation = {"marker_created": False}
        objective = "Demonstrate controlled marker creation inside the disposable container only."
        generator = "patch2proof.safe_poc.heuristic-test-only"
    elif "918" in vulnerability_class or "network" in hypothesis.title.lower():
        actions = _scaffold(
            SafeAction(
                action_id="A-OBS-001",
                op="http_mock_request",
                target="mock://proof-service/marker",
                expected="mock-hit",
                transition_ids=["node-safe-observable"],
            ),
            graph=graph,
            contract=contract,
        )
        oracle = "mock_hit"
        vulnerable_expectation = {"mock_hit": True}
        fixed_expectation = {"mock_hit": False}
        objective = (
            "Demonstrate a request to an explicitly local mock service, never to the Internet."
        )
        generator = "patch2proof.safe_poc.heuristic-test-only"
    elif "502" in vulnerability_class or "deserial" in hypothesis.title.lower():
        actions = _scaffold(
            SafeAction(
                action_id="A-OBS-001",
                op="assert_log",
                target="/proof/logs/deserialization.log",
                value="safe-object-observed",
                expected="log-record",
                transition_ids=["node-safe-observable"],
            ),
            graph=graph,
            contract=contract,
        )
        oracle = "log_record"
        vulnerable_expectation = {"safe_object_observed": True}
        fixed_expectation = {"safe_object_observed": False}
        objective = "Demonstrate an instrumented safe-object observation without gadget execution."
        generator = "patch2proof.safe_poc.heuristic-test-only"
    else:
        actions = _scaffold(
            SafeAction(
                action_id="A-OBS-001",
                op="observe_exit",
                target="/proof/observation.json",
                expected="target-observation",
                transition_ids=["node-safe-observable"],
            ),
            graph=graph,
            contract=contract,
        )
        oracle = "exit_status"
        vulnerable_expectation = {"target_observation": True}
        fixed_expectation = {"target_observation": False}
        objective = "Record a bounded target-specific observation for manual review."
        generator = "patch2proof.safe_poc.heuristic-test-only"

    return SafePoC(
        poc_id=f"POC-{hypothesis.hypothesis_id}",
        hypothesis_id=hypothesis.hypothesis_id,
        objective=objective,
        actions=actions,
        oracle=oracle,
        vulnerable_expectation=vulnerable_expectation,
        fixed_expectation=fixed_expectation,
        allowed_effects=[
            "write only under /proof",
            "read only the supplied canary fixture",
            "mock-only network",
        ],
        forbidden_effects=[
            "reverse shell",
            "persistence",
            "host filesystem access",
            "credential access",
            "Internet egress",
        ],
        generator=generator,
        reviewed=False,
        graph_id=graph.graph_id if graph else None,
        plan_id=contract.contract_id if contract else None,
        entrypoint=(
            contract.required_entrypoints[0] if contract and contract.required_entrypoints else None
        ),
        repair_budget=3,
    )


def refine_safe_poc(poc: SafePoC, attempt: int) -> SafePoC:
    """Make a conservative refinement marker without widening capabilities."""
    updated = poc.model_copy(deep=True)
    updated.poc_id = f"{poc.poc_id}-R{attempt}"
    updated.objective += f" Refinement attempt {attempt} remains confined to the same oracle."
    return updated
