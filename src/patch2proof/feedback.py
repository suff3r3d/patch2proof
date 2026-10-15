"""Typed feedback and conservative repair planning."""

from __future__ import annotations

from typing import Any

from .models import (
    FailureClass,
    ReproductionGraph,
    SafeAction,
    SafePoC,
    Skill,
    SkillApplication,
    SkillKey,
    TypedFeedback,
)
from .reproduction_graph import mark_supported, next_uncovered_edge


def _joined_logs(validation: dict[str, Any]) -> str:
    values = validation.get("logs", [])
    return " ".join(str(item) for item in values).lower()


def classify_feedback(
    graph: ReproductionGraph,
    validation: dict[str, Any],
    *,
    attempt_id: str,
) -> TypedFeedback:
    """Map observations to one repair class; do not let an LLM choose it."""

    status = str(validation.get("status", "error"))
    logs = _joined_logs(validation)
    if status == "passed" and validation.get("differential"):
        failure = FailureClass.ORACLE
        confidence = 1.0
    elif any(token in logs for token in ("dependency", "lockfile", "package")):
        failure = FailureClass.DEPENDENCY
        confidence = 0.8
    elif any(token in logs for token in ("startup", "listen", "service")):
        failure = FailureClass.STARTUP
        confidence = 0.75
    elif any(token in logs for token in ("harness", "entrypoint", "adapter")):
        failure = FailureClass.HARNESS
        confidence = 0.75
    elif validation.get("vulnerable_observation", {}).get("patch_slice_reached") is False:
        failure = FailureClass.REACHABILITY
        confidence = 0.85
    elif validation.get("vulnerable_observation", {}).get("entrypoint_invoked") is False:
        failure = FailureClass.HARNESS
        confidence = 0.8
    elif status in {"planned", "skipped"}:
        failure = FailureClass.CONFIGURATION
        confidence = 0.65
    else:
        failure = FailureClass.ORACLE
        confidence = 0.45

    observation = validation.get("vulnerable_observation", {}) or {}
    observed_nodes: list[str] = []
    if observation.get("preconditions_satisfied"):
        observed_nodes.append("node-precondition")
    if observation.get("entrypoint_invoked"):
        observed_nodes.append("node-entrypoint")
    if observation.get("patch_slice_reached"):
        observed_nodes.append("node-patch-slice-reached")
    if observation.get("semantic_transition") or validation.get("oracle_match"):
        observed_nodes.append("node-semantic-transition")
    if validation.get("oracle_match"):
        observed_nodes.append("node-safe-observable")
    if validation.get("differential"):
        observed_nodes.append("node-fixed-control")
    observed_set = set(observed_nodes)
    observed_edges = [
        edge.edge_id
        for edge in graph.edges
        if edge.source in observed_set and edge.target in observed_set
    ]
    edge = next_uncovered_edge(graph)
    missing = edge.target if edge else "node-semantic-transition"
    allowed = {
        FailureClass.DEPENDENCY: ["reset_environment"],
        FailureClass.STARTUP: ["establish_fixture_state", "reset_environment"],
        FailureClass.HARNESS: ["invoke_entrypoint", "observe_trace"],
        FailureClass.REACHABILITY: [
            "establish_fixture_state",
            "invoke_entrypoint",
            "observe_trace",
        ],
        FailureClass.ORACLE: ["observe_trace", "assert_state"],
        FailureClass.CONFIGURATION: ["establish_fixture_state", "reset_environment"],
    }.get(failure, ["observe_trace"])
    forbidden = ["arbitrary_shell", "source_mutation", "network_expansion", "credential_access"]
    return TypedFeedback(
        feedback_id=f"feedback-{attempt_id}",
        attempt_id=attempt_id,
        failure_class=failure,
        observed_nodes=observed_nodes,
        observed_edges=observed_edges,
        missing_transition=missing,
        allowed_repairs=allowed,
        forbidden_repairs=forbidden,
        evidence_ids=list(validation.get("evidence_ids", [])),
        confidence=confidence,
    )


def repair_safe_poc(
    poc: SafePoC,
    feedback: TypedFeedback,
    skill: Skill | None,
    preferred_operator: str | None = None,
) -> SafePoC:
    """Apply only bounded SafePoC IR repairs; never widen capability."""

    updated = poc.model_copy(deep=True)
    updated.poc_id = f"{poc.poc_id}-repair-{feedback.attempt_id}"
    updated.repair_budget = max(0, poc.repair_budget - 1)
    selected = skill.allowed_operators if skill else feedback.allowed_repairs
    selected = [item for item in selected if item in feedback.allowed_repairs]
    if preferred_operator:
        if preferred_operator not in selected:
            raise ValueError("Reasoning-selected repair is not allowed by the typed policy")
        selected = [preferred_operator]
    if "establish_fixture_state" in selected:
        updated.actions.insert(
            0,
            SafeAction(
                action_id=f"A-FIX-{feedback.attempt_id}",
                op="establish_fixture_state",
                target="/proof/fixture/state.json",
                value="prepared",
                expected="fixture-ready",
                transition_ids=[feedback.missing_transition],
            ),
        )
    elif "observe_trace" in selected:
        updated.actions.append(
            SafeAction(
                action_id=f"A-OBS-{feedback.attempt_id}",
                op="observe_trace",
                target="/proof/trace/patch-slice.json",
                expected="patch-slice-reached",
                transition_ids=[feedback.missing_transition],
            )
        )
    elif "invoke_entrypoint" in selected:
        updated.actions.insert(
            0,
            SafeAction(
                action_id=f"A-ENTRY-{feedback.attempt_id}",
                op="invoke_entrypoint",
                target="registered://case-entrypoint",
                expected="entrypoint-invoked",
                transition_ids=[feedback.missing_transition],
            ),
        )
    elif "reset_environment" in selected:
        updated.actions.insert(
            0,
            SafeAction(
                action_id=f"A-RESET-{feedback.attempt_id}",
                op="reset_environment",
                target="snapshot://case-baseline",
                expected="environment-reset",
                transition_ids=[feedback.missing_transition],
            ),
        )
    else:
        updated.actions.append(
            SafeAction(
                action_id=f"A-ASSERT-{feedback.attempt_id}",
                op="assert_state",
                target="/proof/observation.json",
                expected="state-observed",
                transition_ids=[feedback.missing_transition],
            )
        )
    return SafePoC.model_validate(updated)


def apply_feedback_to_graph(graph: ReproductionGraph, feedback: TypedFeedback) -> ReproductionGraph:
    """Mark only observed runtime progress; inferred edges stay unobserved."""

    observed = set(feedback.observed_nodes)
    edge_ids = list(feedback.observed_edges)
    return mark_supported(
        graph, node_ids=list(observed), edge_ids=edge_ids, evidence_ids=feedback.evidence_ids
    )


def skill_key_for(
    case: dict[str, Any],
    hypothesis: dict[str, Any],
    feedback: TypedFeedback,
    *,
    observable: str = "unknown",
) -> SkillKey:
    return SkillKey(
        language=str(case.get("language", "unknown")),
        framework=str(case.get("tags", ["unknown"])[0] if case.get("tags") else "unknown"),
        build_system=str(case.get("build_system", "custom")),
        vulnerability_class=str(hypothesis.get("vulnerability_class", "unknown")),
        failure_class=feedback.failure_class,
        missing_transition=feedback.missing_transition,
        observable=observable,
    )


def application_for(
    skill: Skill,
    case_id: str,
    attempt_id: str,
    feedback: TypedFeedback,
    *,
    outcome: str = "inconclusive",
    verified: bool = False,
) -> SkillApplication:
    return SkillApplication(
        application_id=f"application-{skill.skill_id}-{attempt_id}",
        skill_id=skill.skill_id,
        case_id=case_id,
        attempt_id=attempt_id,
        outcome=outcome,  # type: ignore[arg-type]
        transitions_gained=feedback.observed_nodes,
        failure_class=feedback.failure_class,
        evidence_ids=feedback.evidence_ids,
        counterfactual_verified=verified,
    )
