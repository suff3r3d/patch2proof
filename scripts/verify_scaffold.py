"""Dependency-light scaffold verification.

Run this before installing optional LangGraph/LLM dependencies. It checks
syntax, YAML manifests, the fixture diff and SafePoC policy.
"""

from __future__ import annotations

import compileall
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from patch2proof.config import load_case  # noqa: E402
from patch2proof.feedback import classify_feedback, repair_safe_poc  # noqa: E402
from patch2proof.models import Hypothesis, SkillKey  # noqa: E402
from patch2proof.reproduction_graph import build_reproduction_graph  # noqa: E402
from patch2proof.safe_poc import generate_safe_poc  # noqa: E402
from patch2proof.skill_memory import SkillMemory  # noqa: E402
from patch2proof.tools.diff_analysis import analyze_diff  # noqa: E402
from patch2proof.tools.docker_worker import validate_safe_poc  # noqa: E402


def main() -> int:
    if not compileall.compile_dir(str(ROOT / "src"), quiet=1):
        return 1
    for path in (ROOT / "config").rglob("*.yaml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))
    case = load_case(ROOT / "examples/demo_case.yaml")
    diff = (ROOT / "examples/fixtures/demo.patch").read_text(encoding="utf-8")
    summary, evidence = analyze_diff(diff, case.fixed_ref)
    hypothesis = Hypothesis(
        hypothesis_id="VERIFY-001",
        title="Fixture file boundary",
        vulnerability_class="CWE-22",
        observation="verification",
        affected_paths=summary["changed_paths"],
        evidence_ids=[item["evidence_id"] for item in evidence],
    )
    graph, contract = build_reproduction_graph(case, hypothesis, summary, evidence)
    poc = generate_safe_poc(
        hypothesis,
        graph=graph,
        contract=contract,
        require_reasoned_plan=False,
    )
    validate_safe_poc(poc)
    feedback = classify_feedback(
        graph,
        {"status": "failed", "vulnerable_observation": {"patch_slice_reached": False}},
        attempt_id="verify-attempt",
    )
    validate_safe_poc(repair_safe_poc(poc, feedback, None))
    with tempfile.TemporaryDirectory() as temp_dir:
        memory = SkillMemory(Path(temp_dir) / "verify-skill-memory.json")
        assert memory.retrieve(
            SkillKey(
                failure_class=feedback.failure_class, missing_transition=feedback.missing_transition
            )
        )
    print("Patch2Proof scaffold verification passed")
    details = (
        f"case={case.case_id} paths={len(summary['changed_paths'])} "
        f"evidence={len(evidence)} graph={graph.graph_id}"
    )
    print(details)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
