"""Complete Patch2Proof LangGraph workflow.

LangGraph is the orchestration layer. Target-specific reasoning is kept in
typed contracts, a case-local directed reproduction graph, and evidence
artifacts. No LLM output can become a shell command or unrestricted Docker
operation.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Literal, cast

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .config import load_case
from .dacn_bridge import _schema_root, publish_dacn_package
from .environment_profile import inspect_environment_pair
from .evidence import write_json
from .feedback import (
    application_for,
    apply_feedback_to_graph,
    classify_feedback,
    repair_safe_poc,
    skill_key_for,
)
from .llm import (
    ReasoningConfigurationError,
    reason_about_patch,
    reason_about_repair,
    reason_about_safe_poc,
    select_revision_candidate,
)
from .models import (
    AttemptRecord,
    AttemptStatus,
    CaseManifest,
    DockerSpec,
    Evidence,
    FailureClass,
    Hypothesis,
    RepairDecision,
    ReproductionGraph,
    ReviewResult,
    SafePoC,
    SafePoCPlan,
    Skill,
    SourceQuery,
    TypedFeedback,
    Verdict,
    VulnerabilityContract,
    case_output_dir,
)
from .proof_bundle import build_proof_bundle
from .reporting.render import render_report
from .reproduction_graph import (
    build_reproduction_graph,
    coverage_from_state,
    graph_hash,
    next_uncovered_edge,
)
from .retrieval import retrieve_context
from .revision_discovery import CVE_PATTERN, discover_revisions
from .safe_poc import generate_safe_poc
from .skill_memory import SkillMemory
from .source_analysis import build_source_context, execute_source_query
from .state import ResearchState
from .tools.diff_analysis import analyze_diff
from .tools.docker_worker import DockerWorker, dockerfile_base_image
from .tools.repo import fixture_diff, git_diff, git_identity


def _case(state: ResearchState) -> CaseManifest:
    return CaseManifest.model_validate(state["case"])


def _out(state: ResearchState) -> Path:
    destination = case_output_dir(_case(state))
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _hypothesis(state: ResearchState) -> Hypothesis:
    return Hypothesis.model_validate((state.get("hypotheses") or [{}])[-1])


def _rgraph(state: ResearchState) -> ReproductionGraph:
    return ReproductionGraph.model_validate(state["reproduction_graph"])


def _memory_path(case: CaseManifest) -> Path:
    path = Path(case.policy.skill_memory_path).expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def _skill_memory(case: CaseManifest) -> SkillMemory:
    return SkillMemory(_memory_path(case))


def _reasoning_settings(state: ResearchState) -> dict[str, Any]:
    """Resolve case/provider settings without allowing an implicit fallback."""

    case = _case(state)
    policy = case.policy
    return {
        "mode": state.get("reasoning_mode")
        or os.getenv("P2P_LLM_MODE")
        or policy.reasoning_mode.value,
        "model_name": policy.reasoning_model,
        "temperature": policy.reasoning_temperature,
        "reasoning_effort": policy.reasoning_effort,
        "allow_heuristic": policy.allow_heuristic_reasoning,
    }


def _discovery_case(cve_id: str) -> CaseManifest:
    if not CVE_PATTERN.fullmatch(cve_id):
        raise ValueError("CVE discovery requires a valid CVE ID")
    output_root = Path("artifacts").resolve()
    return CaseManifest.model_validate({
        "case_id": cve_id,
        "title": f"Revision discovery for {cve_id}",
        "repository_path": str(output_root / cve_id),
        "vulnerable_ref": "UNRESOLVED",
        "fixed_ref": "UNRESOLVED",
        "policy": {
            "authorized": True,
            "network": "none",
            "allowed_repo_root": str(output_root / cve_id),
            "allowed_artifact_root": str(output_root),
        },
    })


def preflight_node(state: ResearchState) -> ResearchState:
    updates: ResearchState = {}
    if not state.get("case"):
        cve_id = state.get("cve_id") or (state.get("discovery_request") or {}).get("cve_id")
        if not isinstance(cve_id, str):
            raise ValueError("Graph input requires a case or CVE ID")
        case = _discovery_case(cve_id)
        request = dict(state.get("discovery_request") or {"cve_id": cve_id})
        if request.get("cve_id") != cve_id:
            raise ValueError("Conflicting CVE IDs in graph input")
        updates = {
            "case": case.model_dump(mode="json"),
            "discovery_request": request,
            "events": [{"node": "preflight", "dry_run": True, "auto_approve": True}],
        }
    else:
        case = _case(state)
    output_dir = case_output_dir(case)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "case.json", case.model_dump(mode="json"))
    if not case.policy.authorized:
        return {**updates, "phase": "preflight", "status": "blocked",
                "errors": ["Case is not authorized"]}
    if case.policy.network.value != "none":
        return {**updates,
            "phase": "preflight",
            "status": "blocked",
            "errors": [
                "Default project policy requires network=none; use an explicit mock-only adapter"
            ],
        }
    return {**updates, "phase": "preflight", "status": "ready",
            "events": [*updates.get("events", []), {"node": "preflight", "ok": True}]}


def route_preflight(state: ResearchState) -> Literal["discovery", "ingest", "blocked"]:
    if state.get("status") != "ready":
        return "blocked"
    return "discovery" if state.get("discovery_request") else "ingest"


def discovery_node(state: ResearchState) -> ResearchState:
    request = state["discovery_request"]
    case = _case(state)
    specialist_artifacts: list[str] = []

    def select(cve_id: str, candidates: list[dict[str, Any]]) -> int | None:
        decision, record = select_revision_candidate(
            cve_id, candidates, **_reasoning_settings(state),
        )
        write_json(_out(state) / "revision-discovery-reasoning.json", record)
        specialist_artifacts.append("revision-discovery-reasoning.json")
        return decision.candidate_index

    outcome = discover_revisions(
        request["cve_id"], _out(state), _schema_root(),
        repository_hint=request.get("repository_hint"),
        selector=select,
    )
    write_json(_out(state) / "revision-discovery-result.json", outcome.result)
    artifacts = [*outcome.artifacts, *specialist_artifacts, "revision-discovery-result.json"]
    if outcome.result["status"] != "resolved" or outcome.repository_path is None:
        return {
            "phase": "discovery", "status": "unresolved",
            "discovery_result": outcome.result, "discovery_artifacts": artifacts,
            "errors": [outcome.result["failure_reason"]],
        }
    selected = outcome.result["selected"]
    try:
        profile = inspect_environment_pair(
            outcome.repository_path, case.policy.allowed_repo_root,
            selected["vulnerable_commit"], selected["fixed_commit"],
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        profile = {
            "status": "review_required", "language": "unknown",
            "build_system": "custom", "review_reasons": [str(exc)],
            "default_template_ready": False,
        }
    write_json(_out(state) / "environment-profile.json", profile)
    resolved_case = CaseManifest.model_validate({
        **case.model_dump(mode="json"),
        "repository_path": str(outcome.repository_path),
        "vulnerable_ref": selected["vulnerable_commit"],
        "fixed_ref": selected["fixed_commit"],
        "language": profile["language"],
        "build_system": profile["build_system"],
    })
    write_json(_out(state) / "case.json", resolved_case.model_dump(mode="json"))
    return {
        "phase": "discovery", "status": "resolved",
        "case": resolved_case.model_dump(mode="json"),
        "discovery_result": outcome.result, "discovery_artifacts": artifacts,
        "environment_profile": profile,
        "events": [{"node": "discovery", "repository": selected["repository_url"],
                    "vulnerable": selected["vulnerable_commit"],
                    "fixed": selected["fixed_commit"]}],
    }


def route_discovery(state: ResearchState) -> Literal["ingest", "report"]:
    return "ingest" if state.get("status") == "resolved" else "report"


def ingest_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    identities: dict[str, Any]
    try:
        if case.source_mode == "fixture":
            fixture_path = Path("examples/fixtures/demo.patch")
            raw_diff = fixture_diff(fixture_path)
            identities = {"mode": "fixture", "path": str(fixture_path.resolve())}
        else:
            raw_diff = git_diff(
                case.repository_path,
                case.vulnerable_ref,
                case.fixed_ref,
                case.policy.allowed_repo_root,
            )
            identities = {
                "vulnerable": git_identity(
                    case.repository_path, case.policy.allowed_repo_root, case.vulnerable_ref
                ),
                "fixed": git_identity(
                    case.repository_path, case.policy.allowed_repo_root, case.fixed_ref
                ),
            }
        (_out(state) / "raw-patch.diff").write_text(raw_diff, encoding="utf-8")
        write_json(_out(state) / "source-identities.json", identities)
        return {
            "phase": "ingest",
            "status": "ingested",
            "raw_diff": raw_diff,
            "events": [{"node": "ingest", "ok": True, "source": identities}],
        }
    except Exception as exc:
        return {"phase": "ingest", "status": "error", "errors": [str(exc)]}


def route_ingest(state: ResearchState) -> Literal["analysis", "report"]:
    return "analysis" if state.get("status") == "ingested" else "report"


def analysis_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    summary, evidence = analyze_diff(state.get("raw_diff", ""), case.fixed_ref)
    write_json(_out(state) / "patch-analysis.json", {"summary": summary, "evidence": evidence})
    return {
        "phase": "analysis",
        "status": "analysis_ready",
        "diff_summary": summary,
        "evidence": evidence,
        "events": [{"node": "analysis", "tags": summary.get("security_tags", [])}],
    }


def source_context_node(state: ResearchState) -> ResearchState:
    """Build complete patch mapping and bounded source/call context."""

    case = _case(state)
    try:
        bundle, source_evidence = build_source_context(
            case.model_dump(mode="json"),
            state.get("raw_diff", ""),
            state.get("diff_summary", {}),
        )
        write_json(_out(state) / "source-context.json", bundle)
        return {
            "phase": "source_context",
            "status": "source_context_ready",
            "source_context": bundle,
            "context_sufficiency": {
                "status": bundle["status"],
                "patch_complete": bundle["patch_complete"],
                "hunk_count": bundle["hunk_count"],
                "mapped_hunk_count": bundle["mapped_hunk_count"],
                "missing_context": bundle["missing_context"],
            },
            "evidence": source_evidence,
            "events": [
                {
                    "node": "source_context",
                    "status": bundle["status"],
                    "hunks": bundle["hunk_count"],
                    "mapped_hunks": bundle["mapped_hunk_count"],
                    "changed_symbols": len(bundle["changed_symbols"]),
                    "caller_paths": len(bundle["caller_paths"]),
                }
            ],
        }
    except Exception as exc:
        context = {
            "status": "insufficient",
            "patch_sha256": state.get("diff_summary", {}).get("patch_hash", ""),
            "patch_complete": False,
            "hunk_count": 0,
            "mapped_hunk_count": 0,
            "changed_symbols": [],
            "caller_paths": [],
            "callee_paths": [],
            "callee_candidates": [],
            "source_slices": [],
            "missing_context": [f"Source analysis failed: {str(exc)[:500]}"],
            "parser_coverage": {},
            "evidence_ids": [],
            "tool_results": [],
        }
        write_json(_out(state) / "source-context.json", context)
        return {
            "phase": "source_context",
            "status": "source_context_error",
            "source_context": context,
            "context_sufficiency": {
                "status": "insufficient",
                "missing_context": context["missing_context"],
            },
            "errors": context["missing_context"],
        }


def route_source_context(state: ResearchState) -> Literal["reasoning", "report"]:
    return (
        "reasoning"
        if state.get("context_sufficiency", {}).get("status") == "sufficient"
        else "report"
    )


def reasoning_node(state: ResearchState) -> ResearchState:
    """Run provider-backed deliberation and materialize an auditable decision."""

    case = _case(state)
    settings = _reasoning_settings(state)
    tool_evidence: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []

    def source_tool(query: SourceQuery) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        result, evidence = execute_source_query(case.model_dump(mode="json"), query)
        tool_results.append(result)
        tool_evidence.extend(evidence)
        return result, evidence

    try:
        hypothesis, reasoning = reason_about_patch(
            case.model_dump(mode="json"),
            state.get("diff_summary", {}),
            state.get("evidence", []),
            raw_diff=state.get("raw_diff", ""),
            source_context=state.get("source_context", {}),
            source_tool=source_tool,
            max_tool_calls=case.policy.source_tool_call_limit,
            **settings,
        )
        source_context = dict(state.get("source_context", {}))
        source_context["tool_results"] = [*source_context.get("tool_results", []), *tool_results]
        source_context["evidence_ids"] = list(
            dict.fromkeys(
                source_context.get("evidence_ids", [])
                + [item["evidence_id"] for item in tool_evidence]
            )
        )
        write_json(_out(state) / "source-context.json", source_context)
        write_json(_out(state) / "reasoning-initial.json", reasoning.model_dump(mode="json"))
        write_json(
            _out(state) / "patch-analysis.json",
            {
                "summary": state.get("diff_summary", {}),
                "evidence": state.get("evidence", []),
                "source_context": source_context,
                "selected_hypothesis": hypothesis.model_dump(mode="json"),
            },
        )
        return {
            "phase": "reasoning",
            "status": "reasoned",
            "hypotheses": [hypothesis.model_dump(mode="json")],
            "reasoning": [reasoning.model_dump(mode="json")],
            "source_context": source_context,
            "evidence": tool_evidence,
            "events": [
                {
                    "node": "reasoning",
                    "mode": reasoning.mode.value,
                    "provider": reasoning.provider,
                    "reasoning_id": reasoning.reasoning_id,
                }
            ],
        }
    except ReasoningConfigurationError as exc:
        return {
            "phase": "reasoning",
            "status": "reasoning_error",
            "errors": [str(exc)],
            "events": [{"node": "reasoning", "provider_error": str(exc)}],
        }


def route_reasoning(state: ResearchState) -> Literal["reproduction_graph", "report"]:
    return "reproduction_graph" if state.get("status") == "reasoned" else "report"


def reproduction_graph_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    hypothesis = _hypothesis(state)
    evidence = [Evidence.model_validate(item) for item in state.get("evidence", [])]
    graph, contract = build_reproduction_graph(
        case,
        hypothesis,
        state.get("diff_summary", {}),
        evidence,
        source_context=state.get("source_context", {}),
    )
    write_json(_out(state) / "vulnerability-contract.json", contract.model_dump(mode="json"))
    write_json(_out(state) / "reproduction-graph.json", graph.model_dump(mode="json"))
    return {
        "phase": "reproduction_graph",
        "status": "graph_ready",
        "vulnerability_contract": contract.model_dump(mode="json"),
        "reproduction_graph": graph.model_dump(mode="json"),
        "events": [{"node": "reproduction_graph", "graph_id": graph.graph_id}],
    }


def knowledge_node(state: ResearchState) -> ResearchState:
    """Retrieve prior notes as context, never as proof."""
    case = _case(state)
    summary = state.get("diff_summary", {})
    hypothesis = (state.get("hypotheses") or [{}])[-1]
    query = " ".join(
        [
            case.title,
            case.language,
            hypothesis.get("vulnerability_class", ""),
            " ".join(summary.get("security_tags", [])),
        ]
    )
    context = retrieve_context(query)
    write_json(_out(state) / "retrieved-context.json", context)
    return {
        "phase": "knowledge",
        "status": "context_retrieved",
        "retrieved_context": context,
        "events": [{"node": "knowledge", "chunks": len(context), "not_evidence": True}],
    }


def skill_retrieval_node(state: ResearchState) -> ResearchState:
    """Select a safe strategy using typed failure and graph constraints."""
    case = _case(state)
    hypothesis = _hypothesis(state)
    graph = _rgraph(state)
    edge = next_uncovered_edge(graph)
    missing = edge.target if edge else "node-precondition"
    initial_feedback = TypedFeedback(
        feedback_id="feedback-initial-plan",
        attempt_id="attempt-0",
        failure_class=FailureClass.REACHABILITY,
        missing_transition=missing,
        allowed_repairs=["establish_fixture_state", "invoke_entrypoint", "observe_trace"],
        forbidden_repairs=[
            "arbitrary_shell",
            "source_mutation",
            "network_expansion",
            "credential_access",
        ],
    )
    key = skill_key_for(case.model_dump(), hypothesis.model_dump(), initial_feedback)
    memory = _skill_memory(case)
    candidates = memory.retrieve_for_feedback(key, initial_feedback, graph)
    selected = candidates[0] if candidates else None
    payload = [item.model_dump(mode="json") for item in candidates]
    write_json(_out(state) / "skill-candidates.json", payload)
    return {
        "phase": "skill_retrieval",
        "status": "skills_retrieved",
        "skill_candidates": payload,
        "selected_skill": selected.model_dump(mode="json") if selected else {},
        "events": [
            {
                "node": "skill_retrieval",
                "candidate_count": len(candidates),
                "selected": selected.skill_id if selected else None,
                "typed_key": key.model_dump(mode="json"),
            }
        ],
    }


def poc_reasoning_node(state: ResearchState) -> ResearchState:
    """Use the selected model to choose a bounded observation plan."""

    case = _case(state)
    hypothesis = _hypothesis(state)
    graph = _rgraph(state)
    contract = VulnerabilityContract.model_validate(state["vulnerability_contract"])
    selected = (
        Skill.model_validate(state["selected_skill"]) if state.get("selected_skill") else None
    )
    settings = _reasoning_settings(state)
    try:
        plan, reasoning = reason_about_safe_poc(
            case.model_dump(mode="json"),
            hypothesis,
            graph,
            contract,
            selected,
            **settings,
        )
        write_json(_out(state) / "safe-poc-plan.json", plan.model_dump(mode="json"))
        write_json(_out(state) / "reasoning-plan.json", reasoning.model_dump(mode="json"))
        return {
            "phase": "poc_reasoning",
            "status": "poc_plan_ready",
            "safe_poc_plan": plan.model_dump(mode="json"),
            "reasoning": [reasoning.model_dump(mode="json")],
            "events": [
                {
                    "node": "poc_reasoning",
                    "mode": reasoning.mode.value,
                    "provider": reasoning.provider,
                    "reasoning_id": reasoning.reasoning_id,
                }
            ],
        }
    except ReasoningConfigurationError as exc:
        return {
            "phase": "poc_reasoning",
            "status": "reasoning_error",
            "errors": [str(exc)],
            "events": [{"node": "poc_reasoning", "provider_error": str(exc)}],
        }


def route_poc_reasoning(state: ResearchState) -> Literal["environment_plan", "report"]:
    return "environment_plan" if state.get("status") == "poc_plan_ready" else "report"


def environment_plan_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    profile = state.get("environment_profile")
    if profile is None and case.source_mode == "git":
        try:
            profile = inspect_environment_pair(
                case.repository_path, case.policy.allowed_repo_root,
                case.vulnerable_ref, case.fixed_ref,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return {
                "phase": "environment_plan", "status": "environment_review_required",
                "errors": [f"Could not inspect pinned build metadata: {exc}"],
            }
        write_json(_out(state) / "environment-profile.json", profile)
    elif profile is None:
        profile = {
            "status": "fixture",
            "language": case.language,
            "build_system": case.build_system,
            "review_reasons": ["Fixture input does not identify a Git revision pair"],
        }
        write_json(_out(state) / "environment-profile.json", profile)
    language = case.language if case.language != "unknown" else (
        profile or {}
    ).get("language", "unknown")
    if language == "unknown" and not case.dockerfile:
        return {
            "phase": "environment_plan", "status": "environment_review_required",
            "environment_profile": profile or {},
            "errors": ["Build system could not be identified; supply a reviewed case Dockerfile"],
        }
    context_dir = str(Path(case.repository_path).expanduser().resolve())
    defaults = {
        "python": ("templates/docker/python.Dockerfile", "python:3.12-slim"),
        "node": ("templates/docker/node.Dockerfile", "node:22-bookworm-slim"),
        "java": ("templates/docker/java.Dockerfile", "eclipse-temurin:21-jre"),
    }
    if language not in defaults and not case.dockerfile:
        return {
            "phase": "environment_plan", "status": "environment_review_required",
            "environment_profile": profile or {},
            "errors": [f"No default Docker template for {language}; supply a reviewed Dockerfile"],
        }
    default_dockerfile, _default_base = defaults.get(language, ("", ""))
    dockerfile = case.dockerfile or str(Path(default_dockerfile).resolve())
    reviewed_dockerfile = bool(case.dockerfile) and Path(case.dockerfile).resolve() != (
        Path(default_dockerfile).resolve() if default_dockerfile else None
    )
    if profile and not profile.get("default_template_ready") and not reviewed_dockerfile:
        return {
            "phase": "environment_plan", "status": "environment_review_required",
            "environment_profile": profile,
            "errors": profile.get("default_template_reasons") or profile.get("review_reasons") or [
                "The default Docker template cannot reproduce this project environment"
            ],
        }
    try:
        base_image = dockerfile_base_image(Path(dockerfile))
    except (OSError, ValueError) as exc:
        return {
            "phase": "environment_plan", "status": "environment_review_required",
            "environment_profile": profile or {}, "errors": [str(exc)],
        }
    spec = DockerSpec(
        case_id=case.case_id,
        language=language,
        context_dir=context_dir,
        dockerfile_path=str(Path(dockerfile).expanduser().resolve()),
        vulnerable_ref=case.vulnerable_ref,
        fixed_ref=case.fixed_ref,
        build_network=case.policy.network,
        runtime_network=case.policy.network,
        base_image=base_image,
        labels={"org.patch2proof.case": case.case_id, "org.patch2proof.role": "pair"},
    )
    write_json(_out(state) / "docker-plan.json", spec.model_dump(mode="json"))
    return {
        "phase": "environment_plan",
        "status": "planned",
        "environment_profile": profile or {},
        "docker_spec": spec.model_dump(mode="json"),
    }


def route_environment_plan(state: ResearchState) -> Literal["build_approval", "report"]:
    return "build_approval" if state.get("status") == "planned" else "report"


def build_approval_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    auto_approved = any(event.get("auto_approve") for event in state.get("events", []))
    dry_run = any(event.get("dry_run") for event in state.get("events", []))
    if auto_approved and (dry_run or case.policy.allow_docker_build):
        return {"phase": "build_approval", "status": "approved"}
    decision = interrupt(
        {
            "type": "build_approval",
            "case_id": case.case_id,
            "message": "Review and approve the Docker pair build.",
            "docker_spec": state.get("docker_spec"),
            "network": case.policy.network.value,
        }
    )
    return {
        "phase": "build_approval",
        "status": "approved" if decision.get("approved") else "rejected",
    }


def route_build_approval(state: ResearchState) -> Literal["build", "report"]:
    return "build" if state.get("status") == "approved" else "report"


def build_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    spec = DockerSpec.model_validate(state["docker_spec"])
    dry_run = any(event.get("dry_run") for event in state.get("events", []))
    if not dry_run and not case.policy.allow_docker_build:
        return {
            "phase": "build",
            "status": "blocked",
            "errors": ["Case policy does not allow Docker builds"],
        }
    if not dry_run and case.source_mode != "git":
        return {
            "phase": "build", "status": "blocked",
            "errors": ["Real paired builds require two pinned Git revisions"],
        }
    worker = DockerWorker(
        case.policy, _out(state), dry_run=dry_run
    )
    try:
        if not dry_run and case.source_mode == "git":
            from .tools.revision_workspace import materialize_pair

            build_run_id = uuid.uuid4().hex[:12]
            pair = materialize_pair(
                case.repository_path,
                case.policy.allowed_repo_root,
                case.vulnerable_ref,
                case.fixed_ref,
                _out(state) / "source-pairs" / build_run_id,
                artifact_root=case.policy.allowed_artifact_root,
                timeout=case.policy.timeout_seconds,
            )
            contexts = cast(dict[str, str], pair["contexts"])
            archive_hashes = cast(dict[str, str], pair["archive_sha256"])
            spec = spec.model_copy(
                update={
                    "vulnerable_context_dir": contexts["vulnerable"],
                    "fixed_context_dir": contexts["fixed"],
                    "labels": {
                        **spec.labels,
                        "org.patch2proof.run_id": build_run_id,
                        "org.patch2proof.vulnerable.archive_sha256": archive_hashes["vulnerable"],
                        "org.patch2proof.fixed.archive_sha256": archive_hashes["fixed"],
                    },
                }
            )
            write_json(_out(state) / "source-pair.json", pair)
            write_json(_out(state) / "docker-plan.json", spec.model_dump(mode="json"))
        images = worker.build_pair(spec)
        write_json(_out(state) / "images.json", [image.model_dump(mode="json") for image in images])
        return {
            "phase": "build",
            "status": "built",
            "images": [image.model_dump(mode="json") for image in images],
        }
    except Exception as exc:
        return {"phase": "build", "status": "error", "errors": [str(exc)]}


def route_build(state: ResearchState) -> Literal["poc", "report"]:
    return "poc" if state.get("status") == "built" else "report"


def poc_node(state: ResearchState) -> ResearchState:
    hypothesis = _hypothesis(state)
    graph = _rgraph(state)
    contract = VulnerabilityContract.model_validate(state["vulnerability_contract"])
    selected = (
        Skill.model_validate(state["selected_skill"]) if state.get("selected_skill") else None
    )
    plan = SafePoCPlan.model_validate(state["safe_poc_plan"])
    poc = generate_safe_poc(
        hypothesis,
        graph=graph,
        contract=contract,
        selected_skill=selected,
        plan=plan,
        require_reasoned_plan=True,
    )
    write_json(_out(state) / "safepoc.json", poc.model_dump(mode="json"))
    return {"phase": "safe_poc", "status": "poc_planned", "safe_poc": poc.model_dump(mode="json")}


def attempt_plan_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    hypothesis = _hypothesis(state)
    graph = _rgraph(state)
    poc = SafePoC.model_validate(state["safe_poc"])
    attempt_number = state.get("attempt", 0) + 1
    attempt_id = f"attempt-{attempt_number}"
    target = next_uncovered_edge(graph)
    record = AttemptRecord(
        attempt_id=attempt_id,
        case_id=case.case_id,
        hypothesis_id=hypothesis.hypothesis_id,
        graph_id=graph.graph_id,
        parent_attempt_id=state.get("current_attempt_id"),
        selected_skill_id=(state.get("selected_skill") or {}).get("skill_id"),
        target_edge_ids=[target.edge_id] if target else [],
        action_ids=[action.action_id for action in poc.actions],
        before_graph_hash=graph_hash(graph),
        status=AttemptStatus.PLANNED,
    )
    attempts = list(state.get("attempts", []))
    attempts.append(record.model_dump(mode="json"))
    write_json(_out(state) / f"{attempt_id}.json", record.model_dump(mode="json"))
    return {
        "phase": "attempt_plan",
        "status": "attempt_planned",
        "attempt": attempt_number,
        "current_attempt_id": attempt_id,
        "attempts": attempts,
    }


def execution_approval_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    auto_approved = any(event.get("auto_approve") for event in state.get("events", []))
    dry_run = any(event.get("dry_run") for event in state.get("events", []))
    if auto_approved and (dry_run or case.policy.allow_poc_execution):
        return {"phase": "execution_approval", "status": "approved"}
    decision = interrupt(
        {
            "type": "poc_execution_approval",
            "case_id": case.case_id,
            "message": "Review and approve the SafePoC in the disposable lab.",
            "safe_poc": state.get("safe_poc"),
            "images": state.get("images", []),
            "network": case.policy.network.value,
        }
    )
    return {
        "phase": "execution_approval",
        "status": "approved" if decision.get("approved") else "rejected",
    }


def route_execution_approval(state: ResearchState) -> Literal["validate", "skill_update"]:
    return "validate" if state.get("status") == "approved" else "skill_update"


def validate_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    from .models import ImageArtifact

    poc = SafePoC.model_validate(state["safe_poc"])
    images = state.get("images", [])
    dry_run = any(event.get("dry_run") for event in state.get("events", []))
    worker = DockerWorker(
        case.policy, _out(state), dry_run=dry_run or not case.policy.allow_poc_execution
    )
    result = worker.run_differential(
        [ImageArtifact.model_validate(item) for item in images],
        poc,
        case.registered_test_id,
    )
    write_json(_out(state) / "validation.json", result.model_dump(mode="json"))
    return {
        "phase": "validation",
        "status": result.status,
        "validation": result.model_dump(mode="json"),
    }


def feedback_node(state: ResearchState) -> ResearchState:
    graph = _rgraph(state)
    validation = state.get("validation") or {}
    attempt_id = state.get("current_attempt_id", "attempt-unknown")
    feedback = classify_feedback(graph, validation, attempt_id=attempt_id)
    updated_graph = apply_feedback_to_graph(graph, feedback)
    coverage = coverage_from_state(
        updated_graph,
        validation=validation,
        runtime_nodes=feedback.observed_nodes,
        source_context=state.get("source_context", {}),
    )
    attempts: list[dict[str, Any]] = []
    for item in state.get("attempts", []):
        record = AttemptRecord.model_validate(item)
        if record.attempt_id == attempt_id:
            if validation.get("status") == "passed" and validation.get("differential"):
                record.status = AttemptStatus.SUCCEEDED
            elif validation.get("status") in {"failed", "error"}:
                record.status = AttemptStatus.FAILED
            else:
                record.status = AttemptStatus.INCONCLUSIVE
            record.failure_class = feedback.failure_class
            record.after_graph_hash = graph_hash(updated_graph)
            record.evidence_ids = sorted(set(record.evidence_ids + feedback.evidence_ids))
        attempts.append(record.model_dump(mode="json"))
    write_json(_out(state) / f"{feedback.feedback_id}.json", feedback.model_dump(mode="json"))
    write_json(_out(state) / "reproduction-graph.json", updated_graph.model_dump(mode="json"))
    write_json(_out(state) / "coverage.json", coverage.model_dump(mode="json"))
    return {
        "phase": "feedback",
        "status": "feedback_ready",
        "feedback": [*state.get("feedback", []), feedback.model_dump(mode="json")],
        "reproduction_graph": updated_graph.model_dump(mode="json"),
        "coverage": coverage.model_dump(mode="json"),
        "attempts": attempts,
        "events": [
            {
                "node": "feedback",
                "failure_class": feedback.failure_class.value,
                "missing_transition": feedback.missing_transition,
                "coverage_complete": coverage.complete,
            }
        ],
    }


def skeptic_node(state: ResearchState) -> ResearchState:
    validation = state.get("validation") or {}
    coverage = state.get("coverage") or {}
    reasoning = state.get("reasoning") or []
    reasoning_provider_backed = bool(reasoning) and all(
        item.get("mode") in {"openai", "ollama"} for item in reasoning
    )
    complete = all(
        bool(coverage.get(item))
        for item in (
            "static_reachability",
            "dynamic_reachability",
            "semantic_transition",
            "counterfactual_separation",
            "repeatable",
            "source_grounded",
        )
    )
    if (
        validation.get("status") == "passed"
        and validation.get("differential")
        and validation.get("oracle_match")
        and complete
        and not validation.get("simulation", False)
        and not validation.get("violations")
        and reasoning_provider_backed
    ):
        review = ReviewResult(
            verdict=Verdict.CONFIRMED,
            rationale=(
                "The deterministic oracle and all coverage gates observed the expected "
                "vulnerable/fixed differential."
            ),
            confidence=0.9,
        )
    elif validation.get("status") == "planned":
        review = ReviewResult(
            verdict=Verdict.CANDIDATE,
            rationale=(
                "The PoC and validation plan exist, but runtime execution was not "
                "approved or enabled."
            ),
            confidence=0.35,
            missing_evidence=[
                "runtime result on vulnerable image",
                "runtime result on fixed image",
            ],
        )
    elif not reasoning_provider_backed:
        review = ReviewResult(
            verdict=Verdict.CANDIDATE,
            rationale=(
                "The execution evidence may be useful, but confirmation requires provider-backed "
                "agent reasoning; heuristic or missing reasoning artifacts are not sufficient."
            ),
            confidence=0.2,
            missing_evidence=["provider-backed reasoning artifacts"],
            suggested_next_step="Configure OpenAI or Ollama reasoning and rerun the case.",
        )
    elif validation.get("simulation", False):
        review = ReviewResult(
            verdict=Verdict.CANDIDATE,
            rationale=(
                "A synthetic adapter exercised the graph and oracle, but simulated "
                "evidence cannot confirm a target vulnerability."
            ),
            confidence=0.2,
            missing_evidence=["non-simulated paired container execution"],
        )
    elif validation.get("status") in {"failed", "error"} or not complete:
        missing = [
            name
            for name, value in {
                "static_reachability": coverage.get("static_reachability"),
                "dynamic_reachability": coverage.get("dynamic_reachability"),
                "semantic_transition": coverage.get("semantic_transition"),
                "counterfactual_separation": coverage.get("counterfactual_separation"),
                "repeatable": coverage.get("repeatable"),
                "source_grounded": coverage.get("source_grounded"),
            }.items()
            if not value
        ]
        review = ReviewResult(
            verdict=Verdict.CANDIDATE,
            rationale=(
                "The validation or coverage gates did not establish the required "
                "differential; do not claim confirmation."
            ),
            confidence=0.15,
            missing_evidence=missing,
            suggested_next_step=(
                "Review the fixture, environment and oracle; do not widen permissions "
                "automatically."
            ),
        )
    else:
        review = ReviewResult(
            verdict=Verdict.NOT_EXECUTED,
            rationale="No runtime evidence was collected.",
            confidence=0.0,
        )
    write_json(_out(state) / "skeptic-review.json", review.model_dump(mode="json"))
    return {
        "phase": "skeptic",
        "status": review.verdict.value,
        "review": review.model_dump(mode="json"),
    }


def route_skeptic(state: ResearchState) -> Literal["repair_reasoning", "skill_update"]:
    validation_status = (state.get("validation") or {}).get("status")
    if validation_status in {"planned", "skipped"}:
        return "skill_update"
    coverage = state.get("coverage") or {}
    incomplete = not all(
        bool(coverage.get(item))
        for item in (
            "static_reachability",
            "dynamic_reachability",
            "semantic_transition",
            "counterfactual_separation",
            "repeatable",
            "source_grounded",
        )
    )
    if (
        state.get("status") == Verdict.CANDIDATE.value
        and state.get("attempt", 0) < state.get("max_attempts", 1)
        and (validation_status in {"failed", "error"} or incomplete)
    ):
        return "repair_reasoning"
    return "skill_update"


def repair_reasoning_node(state: ResearchState) -> ResearchState:
    """Ask the model to rank only repairs already allowed by policy/FCSM."""

    case = _case(state)
    hypothesis = _hypothesis(state)
    graph = _rgraph(state)
    feedback = TypedFeedback.model_validate((state.get("feedback") or [{}])[-1])
    selected = (
        Skill.model_validate(state["selected_skill"]) if state.get("selected_skill") else None
    )
    settings = _reasoning_settings(state)
    try:
        decision, reasoning = reason_about_repair(
            case.model_dump(mode="json"),
            hypothesis,
            graph,
            feedback,
            selected,
            **settings,
        )
        write_json(_out(state) / "repair-decision.json", decision.model_dump(mode="json"))
        write_json(
            _out(state) / f"{reasoning.reasoning_id}.json",
            reasoning.model_dump(mode="json"),
        )
        return {
            "phase": "repair_reasoning",
            "status": "repair_plan_ready",
            "repair_decision": decision.model_dump(mode="json"),
            "reasoning": [reasoning.model_dump(mode="json")],
            "events": [
                {
                    "node": "repair_reasoning",
                    "mode": reasoning.mode.value,
                    "provider": reasoning.provider,
                    "reasoning_id": reasoning.reasoning_id,
                    "selected_repair": decision.selected_repair,
                }
            ],
        }
    except ReasoningConfigurationError as exc:
        return {
            "phase": "repair_reasoning",
            "status": "reasoning_error",
            "errors": [str(exc)],
            "events": [{"node": "repair_reasoning", "provider_error": str(exc)}],
        }


def route_repair_reasoning(state: ResearchState) -> Literal["repair", "skill_update"]:
    return "repair" if state.get("status") == "repair_plan_ready" else "skill_update"


def repair_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    hypothesis = _hypothesis(state)
    graph = _rgraph(state)
    feedback = TypedFeedback.model_validate((state.get("feedback") or [{}])[-1])
    current = Skill.model_validate(state["selected_skill"]) if state.get("selected_skill") else None
    decision = (
        RepairDecision.model_validate(state["repair_decision"])
        if state.get("repair_decision")
        else None
    )
    applications = list(state.get("skill_applications", []))
    memory = _skill_memory(case)
    if current:
        failed_application = application_for(
            current, case.case_id, feedback.attempt_id, feedback, outcome="failed"
        )
        memory.record_application(failed_application)
        applications.append(failed_application.model_dump(mode="json"))
    key = skill_key_for(case.model_dump(), hypothesis.model_dump(), feedback)
    candidates = memory.retrieve_for_feedback(key, feedback, graph)
    selected = candidates[0] if candidates else current
    poc = SafePoC.model_validate(state["safe_poc"])
    repaired = repair_safe_poc(
        poc,
        feedback,
        selected,
        preferred_operator=decision.selected_repair if decision else None,
    )
    memory.save()
    write_json(_out(state) / "skill-memory-summary.json", memory.summary())
    write_json(
        _out(state) / f"safepoc-repair-{state.get('attempt', 0) + 1}.json",
        repaired.model_dump(mode="json"),
    )
    return {
        "phase": "repair",
        "status": "refined",
        "safe_poc": repaired.model_dump(mode="json"),
        "skill_candidates": [item.model_dump(mode="json") for item in candidates],
        "selected_skill": selected.model_dump(mode="json") if selected else {},
        "skill_applications": applications,
        "events": [
            {
                "node": "repair",
                "selected": selected.skill_id if selected else None,
                "failure_class": feedback.failure_class.value,
            }
        ],
    }


def skill_update_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    validation = state.get("validation") or {}
    feedback_items = list(state.get("feedback", []))
    applications = list(state.get("skill_applications", []))
    selected = (
        Skill.model_validate(state["selected_skill"]) if state.get("selected_skill") else None
    )
    if selected and feedback_items:
        feedback = TypedFeedback.model_validate(feedback_items[-1])
        coverage = state.get("coverage") or {}
        verified = bool(
            validation.get("status") == "passed"
            and validation.get("differential")
            and validation.get("oracle_match")
            and not validation.get("simulation", False)
            and all(
                bool(coverage.get(item))
                for item in (
                    "static_reachability",
                    "dynamic_reachability",
                    "semantic_transition",
                    "counterfactual_separation",
                    "repeatable",
                    "source_grounded",
                )
            )
        )
        outcome = (
            "verified"
            if verified
            else "failed"
            if validation.get("status") in {"failed", "error"}
            else "blocked"
            if validation.get("status") == "skipped"
            else "inconclusive"
        )
        application = application_for(
            selected,
            case.case_id,
            feedback.attempt_id,
            feedback,
            outcome=outcome,
            verified=verified,
        )
        if not any(
            item.get("application_id") == application.application_id for item in applications
        ):
            applications.append(application.model_dump(mode="json"))
            memory = _skill_memory(case)
            memory.record_application(application)
            memory.save()
            write_json(_out(state) / "skill-memory-summary.json", memory.summary())
    return {"phase": "skill_update", "status": "skill_updated", "skill_applications": applications}


def report_node(state: ResearchState) -> ResearchState:
    case = _case(state)
    bundle = build_proof_bundle(state, output_dir=_out(state))
    write_json(_out(state) / "proof-bundle.json", bundle)
    report_path = render_report(
        case=case,
        hypotheses=state.get("hypotheses", []),
        evidence=state.get("evidence", []),
        docker_spec=state.get("docker_spec"),
        images=state.get("images", []),
        safe_poc=state.get("safe_poc"),
        validation=state.get("validation"),
        review=state.get("review"),
        output_dir=_out(state),
        vulnerability_contract=state.get("vulnerability_contract"),
        reproduction_graph=state.get("reproduction_graph"),
        coverage=state.get("coverage"),
        attempts=state.get("attempts", []),
        feedback=state.get("feedback", []),
        skill_applications=state.get("skill_applications", []),
        reasoning=state.get("reasoning", []),
        source_context=state.get("source_context") or None,
        proof_bundle=bundle,
    )
    dacn_package = publish_dacn_package(case, state, _out(state))
    return {
        "phase": "report",
        "status": "completed",
        "report_path": report_path,
        "proof_bundle": bundle,
        "dacn_package": dacn_package,
    }


def blocked_node(state: ResearchState) -> ResearchState:
    return {"phase": "blocked", "status": "blocked"}


def build_graph(*, local_checkpointer: bool = False):
    builder = StateGraph(ResearchState)
    for name, node in {
        "preflight": preflight_node,
        "discovery": discovery_node,
        "ingest": ingest_node,
        "analysis": analysis_node,
        "source_context": source_context_node,
        "reasoning": reasoning_node,
        "reproduction_graph": reproduction_graph_node,
        "knowledge": knowledge_node,
        "skill_retrieval": skill_retrieval_node,
        "poc_reasoning": poc_reasoning_node,
        "environment_plan": environment_plan_node,
        "build_approval": build_approval_node,
        "build": build_node,
        "poc": poc_node,
        "attempt_plan": attempt_plan_node,
        "execution_approval": execution_approval_node,
        "validate": validate_node,
        "feedback": feedback_node,
        "skeptic": skeptic_node,
        "repair_reasoning": repair_reasoning_node,
        "repair": repair_node,
        "skill_update": skill_update_node,
        "report": report_node,
        "blocked": blocked_node,
    }.items():
        builder.add_node(name, node)

    builder.add_edge(START, "preflight")
    builder.add_conditional_edges("preflight", route_preflight)
    builder.add_conditional_edges("discovery", route_discovery)
    builder.add_conditional_edges("ingest", route_ingest)
    builder.add_edge("analysis", "source_context")
    builder.add_conditional_edges("source_context", route_source_context)
    builder.add_conditional_edges("reasoning", route_reasoning)
    builder.add_edge("reproduction_graph", "knowledge")
    builder.add_edge("knowledge", "skill_retrieval")
    builder.add_edge("skill_retrieval", "poc_reasoning")
    builder.add_conditional_edges("poc_reasoning", route_poc_reasoning)
    builder.add_conditional_edges("environment_plan", route_environment_plan)
    builder.add_conditional_edges("build_approval", route_build_approval)
    builder.add_conditional_edges("build", route_build)
    builder.add_edge("poc", "attempt_plan")
    builder.add_edge("attempt_plan", "execution_approval")
    builder.add_conditional_edges("execution_approval", route_execution_approval)
    builder.add_edge("validate", "feedback")
    builder.add_edge("feedback", "skeptic")
    builder.add_conditional_edges("skeptic", route_skeptic)
    builder.add_conditional_edges("repair_reasoning", route_repair_reasoning)
    builder.add_edge("repair", "attempt_plan")
    builder.add_edge("skill_update", "report")
    builder.add_edge("report", END)
    builder.add_edge("blocked", "report")
    return builder.compile(checkpointer=InMemorySaver() if local_checkpointer else None)


graph = build_graph()
_local_graph = build_graph(local_checkpointer=True)


def initial_state(
    case_path: str,
    auto_approve: bool = False,
    max_attempts: int | None = None,
    reasoning_mode: str | None = None,
) -> ResearchState:
    if CVE_PATTERN.fullmatch(case_path):
        case = _discovery_case(case_path)
        discovery_request = {"cve_id": case_path}
    else:
        case = load_case(case_path)
        discovery_request = None
    total_attempts = (
        max_attempts if max_attempts is not None else 1 + case.policy.max_repair_attempts
    )
    state: ResearchState = {
        "case": case.model_dump(mode="json"),
        "phase": "created",
        "status": "created",
        "attempt": 0,
        "max_attempts": total_attempts,
        "reasoning_mode": reasoning_mode or "",
        "evidence": [],
        "hypotheses": [],
        "attempts": [],
        "feedback": [],
        "skill_applications": [],
        "reasoning": [],
        "context_sufficiency": {},
        "errors": [],
        "events": [{"node": "cli", "auto_approve": auto_approve}],
    }
    if discovery_request:
        state["discovery_request"] = discovery_request
    return state


def invoke_case(
    case_path: str,
    dry_run: bool = True,
    auto_approve: bool = False,
    reasoning_mode: str | None = None,
) -> dict:
    if CVE_PATTERN.fullmatch(case_path) and not dry_run:
        raise ValueError("CVE-only runs are dry-run only; review a pinned case before execution")
    state = initial_state(
        case_path,
        auto_approve=auto_approve,
        reasoning_mode=reasoning_mode,
    )
    if dry_run:
        state["events"] = [*state.get("events", []), {"node": "cli", "dry_run": True}]
    config = {"configurable": {"thread_id": _case(state).case_id}}
    return dict(_local_graph.invoke(state, config=config))


def resume_case(case_path: str, decision: dict, reasoning_mode: str | None = None) -> dict:
    state = initial_state(case_path, reasoning_mode=reasoning_mode)
    config = {"configurable": {"thread_id": _case(state).case_id}}
    return dict(_local_graph.invoke(Command(resume=decision), config=config))
