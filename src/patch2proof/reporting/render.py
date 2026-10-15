"""Evidence-backed Markdown and JSON report rendering."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..evidence import write_json
from ..models import CaseManifest, ReportModel


def render_report(
    case: CaseManifest,
    hypotheses: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    docker_spec: dict[str, Any] | None,
    images: list[dict[str, Any]],
    safe_poc: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    review: dict[str, Any] | None,
    output_dir: Path,
    vulnerability_contract: dict[str, Any] | None = None,
    reproduction_graph: dict[str, Any] | None = None,
    coverage: dict[str, Any] | None = None,
    attempts: list[dict[str, Any]] | None = None,
    feedback: list[dict[str, Any]] | None = None,
    skill_applications: list[dict[str, Any]] | None = None,
    reasoning: list[dict[str, Any]] | None = None,
    source_context: dict[str, Any] | None = None,
    proof_bundle: dict[str, Any] | None = None,
) -> str:
    report = ReportModel.model_validate(
        {
            "case": case,
            "hypotheses": hypotheses,
            "evidence": evidence,
            "docker_spec": docker_spec,
            "images": images,
            "safe_poc": safe_poc,
            "validation": validation,
            "review": review,
            "generated_at": datetime.now(UTC).isoformat(),
            "limitations": [
                "This report is valid only for the pinned local artifacts.",
                "A candidate or planned result is not a confirmed vulnerability.",
                "The SafePoC is intentionally non-weaponized and sandbox-bound.",
            ],
            "vulnerability_contract": vulnerability_contract,
            "reproduction_graph": reproduction_graph,
            "coverage": coverage,
            "attempts": attempts or [],
            "feedback": feedback or [],
            "skill_applications": skill_applications or [],
            "reasoning": reasoning or [],
            "source_context": source_context,
            "proof_bundle": proof_bundle or {},
        }
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "final-report.json", report.model_dump(mode="json"))

    template_dir = Path(__file__).resolve().parents[3] / "templates"
    if not template_dir.exists():
        from importlib.resources import files

        template_dir = Path(str(files("patch2proof").joinpath("templates")))
    environment = Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        autoescape=False,
    )
    template = environment.get_template("final-report.md.j2")
    text = template.render(report=report.model_dump(mode="json"))
    (output_dir / "final-report.md").write_text(text, encoding="utf-8")
    return str(output_dir / "final-report.md")
