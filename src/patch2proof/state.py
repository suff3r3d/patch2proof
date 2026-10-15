"""LangGraph state and stage names."""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict


class ResearchState(TypedDict, total=False):
    case: dict
    phase: str
    status: str
    attempt: int
    max_attempts: int

    raw_diff: str
    diff_summary: dict
    source_context: dict
    context_sufficiency: dict
    retrieved_context: list[dict]
    docker_spec: dict
    images: list[dict]
    safe_poc: dict
    safe_poc_plan: dict
    validation: dict
    review: dict
    report_path: str
    vulnerability_contract: dict
    reproduction_graph: dict
    coverage: dict
    skill_candidates: list[dict]
    selected_skill: dict
    repair_decision: dict
    reasoning_mode: str
    current_attempt_id: str
    proof_bundle: dict
    dacn_package: dict

    evidence: Annotated[list[dict], add]
    hypotheses: Annotated[list[dict], add]
    attempts: list[dict]
    feedback: list[dict]
    skill_applications: list[dict]
    reasoning: Annotated[list[dict], add]
    errors: Annotated[list[str], add]
    events: Annotated[list[dict], add]
