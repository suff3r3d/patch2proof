"""Directed, typed reproduction graph used by the planner and verifier.

The graph is deliberately separate from LangGraph's workflow graph.  LangGraph
controls orchestration; this module models the target vulnerability's causal
path from patch context to a bounded observable.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Sequence

from .models import (
    CaseManifest,
    CoverageVector,
    Evidence,
    GraphEdge,
    GraphEdgeKind,
    GraphNode,
    GraphNodeKind,
    GraphStatus,
    Hypothesis,
    ReproductionGraph,
    VulnerabilityContract,
)

EvidenceInput = Evidence | dict[str, Any]


def _evidence_ids(evidence: Sequence[EvidenceInput]) -> list[str]:
    return [
        item.evidence_id if isinstance(item, Evidence) else str(item["evidence_id"])
        for item in evidence
    ]


def _slug(value: str, fallback: str = "item") -> str:
    result = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-").lower()
    return result[:48] or fallback


def _node(
    node_id: str,
    kind: GraphNodeKind,
    label: str,
    *,
    evidence_ids: list[str] | None = None,
    status: GraphStatus = GraphStatus.UNOBSERVED,
    confidence: float = 0.35,
    **attributes: Any,
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        kind=kind,
        label=label,
        attributes=attributes,
        evidence_ids=evidence_ids or [],
        status=status,
        confidence=confidence,
    )


def _edge(
    edge_id: str,
    source: str,
    target: str,
    kind: GraphEdgeKind,
    *,
    label: str = "",
    cost: float = 1.0,
    policy_risk: float = 0.0,
) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        source=source,
        target=target,
        kind=kind,
        label=label,
        cost=cost,
        policy_risk=policy_risk,
    )


def build_contract(
    case: CaseManifest,
    hypothesis: Hypothesis,
    summary: dict[str, Any],
    evidence: Sequence[EvidenceInput],
) -> VulnerabilityContract:
    """Create a hypothesis-level contract without upgrading guesses to facts."""

    evidence_ids = _evidence_ids(evidence)
    sink = hypothesis.sink or "target-specific bounded observable"
    transition = f"reach {sink} and produce a vulnerability-specific safe state change"
    return VulnerabilityContract(
        contract_id=f"contract-{case.case_id}-{hypothesis.hypothesis_id}",
        case_id=case.case_id,
        hypothesis_id=hypothesis.hypothesis_id,
        preconditions=list(hypothesis.preconditions) or ["target fixture is initialized"],
        required_entrypoints=[f"registered://{case.registered_test_id}"],
        semantic_transition=transition,
        safe_observables=["controlled canary, marker, mock hit, log record, or state assertion"],
        fixed_behavior=["the target transition is absent or becomes the expected safe behavior"],
        negative_controls=["matched benign input on both paired builds"],
        evidence_ids=evidence_ids,
        status="hypothesis",
    )


def build_reproduction_graph(
    case: CaseManifest,
    hypothesis: Hypothesis,
    summary: dict[str, Any],
    evidence: Sequence[EvidenceInput],
    *,
    source_context: dict[str, Any] | None = None,
) -> tuple[ReproductionGraph, VulnerabilityContract]:
    """Build a small typed graph that can be refined by runtime observations."""

    contract = build_contract(case, hypothesis, summary, evidence)
    evidence_ids = _evidence_ids(evidence)
    graph_id = f"rgraph-{case.case_id}-{hypothesis.hypothesis_id}"
    patch_id = "node-patch"
    symbol_label = hypothesis.sink or (
        hypothesis.affected_paths[0] if hypothesis.affected_paths else "changed code"
    )
    symbol_id = "node-symbol-" + _slug(symbol_label, "changed-code")
    entry_id = "node-entrypoint"
    pre_id = "node-precondition"
    reach_id = "node-patch-slice-reached"
    semantic_id = "node-semantic-transition"
    observable_id = "node-safe-observable"
    fixed_id = "node-fixed-control"

    nodes = [
        _node(
            patch_id,
            GraphNodeKind.PATCH_HUNK,
            "fixing patch hunk",
            evidence_ids=evidence_ids,
            status=GraphStatus.SUPPORTED
            if summary.get("changed_paths")
            else GraphStatus.HYPOTHESIZED,
            confidence=0.75 if summary.get("changed_paths") else 0.3,
            changed_paths=summary.get("changed_paths", []),
        ),
        _node(
            symbol_id,
            GraphNodeKind.SYMBOL,
            symbol_label,
            evidence_ids=evidence_ids,
            status=GraphStatus.SUPPORTED if hypothesis.affected_paths else GraphStatus.HYPOTHESIZED,
            confidence=0.7 if hypothesis.affected_paths else 0.3,
            symbol=hypothesis.sink,
            affected_paths=hypothesis.affected_paths,
        ),
        _node(
            entry_id,
            GraphNodeKind.ENTRYPOINT,
            "registered case entrypoint",
            entrypoint=case.registered_test_id,
        ),
        _node(
            pre_id,
            GraphNodeKind.PRECONDITION,
            "controlled preconditions",
            preconditions=hypothesis.preconditions or ["target fixture is initialized"],
        ),
        _node(
            reach_id,
            GraphNodeKind.STATE,
            "patch-relevant code slice reached",
            transition="reachability",
        ),
        _node(
            semantic_id,
            GraphNodeKind.STATE,
            contract.semantic_transition,
            transition="semantic_effect",
        ),
        _node(
            observable_id, GraphNodeKind.OBSERVATION, "bounded vulnerability-specific observable"
        ),
        _node(
            fixed_id,
            GraphNodeKind.CONTROL,
            "fixed/benign counterfactual control",
            roles=["fixed", "negative_control"],
        ),
    ]
    edges = [
        _edge(
            "edge-patch-symbol",
            patch_id,
            symbol_id,
            GraphEdgeKind.MODIFIES,
            label="patch changes symbol",
        ),
        _edge(
            "edge-entry-pre",
            entry_id,
            pre_id,
            GraphEdgeKind.REQUIRES,
            label="entrypoint establishes preconditions",
        ),
        _edge(
            "edge-pre-reach",
            pre_id,
            reach_id,
            GraphEdgeKind.REACHES,
            label="preconditions reach patch slice",
        ),
        _edge(
            "edge-reach-semantic",
            reach_id,
            semantic_id,
            GraphEdgeKind.TRANSITIONS,
            label="runtime state transition",
        ),
        _edge(
            "edge-semantic-observable",
            semantic_id,
            observable_id,
            GraphEdgeKind.SUPPORTS,
            label="safe observable",
        ),
        _edge(
            "edge-semantic-fixed",
            semantic_id,
            fixed_id,
            GraphEdgeKind.ABSENT_ON_FIXED,
            label="must separate on fixed/control",
        ),
    ]
    # Patch-to-symbol attribution is static evidence, not a runtime target.
    # Treating it as already covered keeps the planner focused on executable
    # reachability and semantic separation.
    edges[0].status = GraphStatus.SUPPORTED if evidence_ids else GraphStatus.HYPOTHESIZED
    edges[0].evidence_ids = list(evidence_ids)
    edges[0].confidence = 0.75 if evidence_ids else 0.3

    # Add source-derived caller/callee slices as a separate, explicitly
    # unobserved subgraph. Static call candidates guide planning but never
    # count as dynamic reachability proof.
    source_context = source_context or {}
    symbol_nodes: dict[str, GraphNode] = {}
    for item in source_context.get("changed_symbols", []):
        if item.get("role") != "vulnerable":
            continue
        stable_name = str(item.get("symbol_id") or item.get("qualified_name"))
        node_id = "node-src-" + _slug(stable_name, "source-symbol")
        symbol_nodes[node_id] = _node(
            node_id,
            GraphNodeKind.SYMBOL,
            str(item.get("qualified_name", stable_name)),
            evidence_ids=list(source_context.get("evidence_ids", [])),
            status=GraphStatus.HYPOTHESIZED,
            confidence=float(item.get("confidence", 0.5)),
            path=item.get("path"),
            line_start=item.get("line_start"),
            line_end=item.get("line_end"),
            parser=item.get("parser"),
            static_candidate=True,
        )
    for path in source_context.get("caller_paths", []):
        path_symbols = path.get("symbols", [])
        for item in path_symbols:
            stable_name = str(item.get("symbol_id") or item.get("qualified_name"))
            node_id = "node-src-" + _slug(stable_name, "source-symbol")
            if node_id not in symbol_nodes:
                symbol_nodes[node_id] = _node(
                    node_id,
                    GraphNodeKind.SYMBOL,
                    str(item.get("qualified_name", stable_name)),
                    evidence_ids=list(path.get("evidence_ids", [])),
                    status=GraphStatus.HYPOTHESIZED,
                    confidence=float(path.get("confidence", 0.45)),
                    path=item.get("path"),
                    line_start=item.get("line_start"),
                    line_end=item.get("line_end"),
                    parser=item.get("parser"),
                    static_candidate=True,
                )
        for index in range(len(path_symbols) - 1):
            caller = path_symbols[index]
            callee = path_symbols[index + 1]
            caller_stable_name = str(caller.get("symbol_id") or caller.get("qualified_name"))
            callee_stable_name = str(callee.get("symbol_id") or callee.get("qualified_name"))
            caller_id = "node-src-" + _slug(caller_stable_name)
            callee_id = "node-src-" + _slug(callee_stable_name)
            edge_id = f"edge-src-call-{_slug(path.get('path_id', 'path'))}-{index}"
            if not any(item.edge_id == edge_id for item in edges):
                edges.append(
                    GraphEdge(
                        edge_id=edge_id,
                        source=caller_id,
                        target=callee_id,
                        kind=GraphEdgeKind.CALLS,
                        label="static caller candidate; requires runtime reachability observation",
                        evidence_ids=list(path.get("evidence_ids", [])),
                        status=GraphStatus.HYPOTHESIZED,
                        confidence=float(path.get("confidence", 0.45)),
                        cost=0.8,
                    )
                )

    for path in source_context.get("callee_paths", []):
        path_symbols = path.get("symbols", [])
        for item in path_symbols:
            stable_name = str(item.get("symbol_id") or item.get("qualified_name"))
            node_id = "node-src-" + _slug(stable_name, "source-symbol")
            if node_id not in symbol_nodes:
                symbol_nodes[node_id] = _node(
                    node_id,
                    GraphNodeKind.SYMBOL,
                    str(item.get("qualified_name", stable_name)),
                    evidence_ids=list(path.get("evidence_ids", [])),
                    status=GraphStatus.HYPOTHESIZED,
                    confidence=float(path.get("confidence", 0.45)),
                    path=item.get("path"),
                    line_start=item.get("line_start"),
                    line_end=item.get("line_end"),
                    parser=item.get("parser"),
                    static_candidate=True,
                )
        for index in range(len(path_symbols) - 1):
            caller = path_symbols[index]
            callee = path_symbols[index + 1]
            caller_stable_name = str(caller.get("symbol_id") or caller.get("qualified_name"))
            callee_stable_name = str(callee.get("symbol_id") or callee.get("qualified_name"))
            caller_id = "node-src-" + _slug(caller_stable_name)
            callee_id = "node-src-" + _slug(callee_stable_name)
            edge_id = f"edge-src-callee-path-{_slug(path.get('path_id', 'path'))}-{index}"
            if not any(item.edge_id == edge_id for item in edges):
                edges.append(
                    GraphEdge(
                        edge_id=edge_id,
                        source=caller_id,
                        target=callee_id,
                        kind=GraphEdgeKind.CALLS,
                        label="static callee candidate; requires runtime reachability observation",
                        evidence_ids=list(path.get("evidence_ids", [])),
                        status=GraphStatus.HYPOTHESIZED,
                        confidence=float(path.get("confidence", 0.45)),
                        cost=0.8,
                    )
                )

    for candidate in source_context.get("callee_candidates", []):
        if candidate.get("candidate_symbol_ids"):
            # Resolved candidates already have explicit edges in callee_paths.
            continue
        source_name = str(candidate.get("source_symbol", "changed-symbol"))
        source_id = "node-src-" + _slug(
            str(candidate.get("source_symbol_id") or source_name), "source-symbol"
        )
        if source_id not in symbol_nodes:
            symbol_nodes[source_id] = _node(
                source_id,
                GraphNodeKind.SYMBOL,
                source_name,
                evidence_ids=list(candidate.get("evidence_ids", [])),
                status=GraphStatus.HYPOTHESIZED,
                confidence=0.4,
                static_candidate=True,
            )
        target_name = str(candidate.get("target_name", "unresolved-callee"))
        target_id = "node-src-" + _slug(f"{source_name}->{target_name}")
        if target_id not in symbol_nodes:
            symbol_nodes[target_id] = _node(
                target_id,
                GraphNodeKind.SYMBOL,
                target_name,
                status=GraphStatus.HYPOTHESIZED,
                confidence=0.3,
                unresolved=True,
            )
        edge_id = f"edge-src-callee-{_slug(source_name)}-{_slug(target_name)}"
        if not any(item.edge_id == edge_id for item in edges):
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source=source_id,
                    target=target_id,
                    kind=GraphEdgeKind.CALLS,
                    label="callee candidate from changed symbol",
                    evidence_ids=list(candidate.get("evidence_ids", [])),
                    status=GraphStatus.HYPOTHESIZED,
                    confidence=0.35,
                    cost=0.9,
                )
            )
    nodes.extend(symbol_nodes.values())
    return (
        ReproductionGraph(
            graph_id=graph_id,
            case_id=case.case_id,
            hypothesis_id=hypothesis.hypothesis_id,
            nodes=nodes,
            edges=edges,
            goal_node_ids=[semantic_id, observable_id, fixed_id],
            current_node_ids=[entry_id],
            uncovered_edge_ids=[
                edge.edge_id for edge in edges if edge.status != GraphStatus.SUPPORTED
            ],
        ),
        contract,
    )


def graph_hash(graph: ReproductionGraph) -> str:
    payload = graph.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def next_uncovered_edge(graph: ReproductionGraph) -> GraphEdge | None:
    candidates = [edge for edge in graph.edges if edge.edge_id in graph.uncovered_edge_ids]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.policy_risk, item.cost, item.edge_id))[0]


def mark_supported(
    graph: ReproductionGraph,
    *,
    node_ids: list[str] | None = None,
    edge_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
) -> ReproductionGraph:
    """Apply trusted observations to a copy; never mutate an earlier graph."""

    node_ids = node_ids or []
    edge_ids = edge_ids or []
    evidence_ids = evidence_ids or []
    updated = graph.model_copy(deep=True)
    for node in updated.nodes:
        if node.node_id in node_ids:
            node.status = GraphStatus.SUPPORTED
            node.evidence_ids = sorted(set(node.evidence_ids + evidence_ids))
            node.confidence = max(node.confidence, 0.8)
    for edge in updated.edges:
        if edge.edge_id in edge_ids:
            edge.status = GraphStatus.SUPPORTED
            edge.evidence_ids = sorted(set(edge.evidence_ids + evidence_ids))
            edge.confidence = max(edge.confidence, 0.8)
    updated.uncovered_edge_ids = [
        item for item in updated.uncovered_edge_ids if item not in edge_ids
    ]
    updated.current_node_ids = sorted(set(updated.current_node_ids + node_ids))
    updated.revision += 1
    return updated


def mark_rejected(graph: ReproductionGraph, edge_ids: list[str]) -> ReproductionGraph:
    updated = graph.model_copy(deep=True)
    for edge in updated.edges:
        if edge.edge_id in edge_ids:
            edge.status = GraphStatus.REJECTED
    updated.uncovered_edge_ids = [
        item for item in updated.uncovered_edge_ids if item not in edge_ids
    ]
    updated.revision += 1
    return updated


def coverage_from_state(
    graph: ReproductionGraph,
    *,
    validation: dict[str, Any] | None = None,
    runtime_nodes: list[str] | None = None,
    source_context: dict[str, Any] | None = None,
) -> CoverageVector:
    """Derive a conservative coverage vector from typed state, never from text alone."""

    validation = validation or {}
    runtime_nodes = runtime_nodes or graph.current_node_ids
    source_context = source_context or {}
    node_set = set(runtime_nodes)
    static = any(
        node.kind in {GraphNodeKind.PATCH_HUNK, GraphNodeKind.SYMBOL}
        and node.status == GraphStatus.SUPPORTED
        for node in graph.nodes
    )
    dynamic = "node-patch-slice-reached" in node_set or bool(
        validation.get("vulnerable_observation", {}).get("patch_slice_reached")
    )
    semantic = "node-semantic-transition" in node_set or bool(validation.get("oracle_match"))
    separation = bool(validation.get("differential"))
    repeatable = bool(validation.get("repeatable"))
    return CoverageVector(
        static_reachability=static,
        dynamic_reachability=dynamic,
        semantic_transition=semantic,
        counterfactual_separation=separation,
        repeatable=repeatable,
        source_grounded=bool(
            source_context.get("status") == "sufficient"
            and source_context.get("patch_complete")
            and source_context.get("hunk_count", 0) == source_context.get("mapped_hunk_count", -1)
            and any(
                item.get("role") == "vulnerable"
                for item in source_context.get("changed_symbols", [])
            )
        ),
    )
