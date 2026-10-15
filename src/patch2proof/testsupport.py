"""Shared fixture helpers kept outside the runtime graph."""

from pathlib import Path

from .config import load_case
from .llm import propose_hypothesis
from .reproduction_graph import build_reproduction_graph
from .tools.diff_analysis import analyze_diff


def fixture_graph():
    case = load_case("examples/demo_case.yaml")
    summary, evidence = analyze_diff(
        Path("examples/fixtures/demo.patch").read_text(), case.fixed_ref
    )
    hypothesis = propose_hypothesis(
        case.model_dump(), summary, evidence, mode="heuristic", allow_heuristic=True
    )
    graph, _ = build_reproduction_graph(case, hypothesis, summary, evidence)
    return graph
