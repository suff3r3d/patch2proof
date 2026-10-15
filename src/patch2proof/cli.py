"""Command-line interface for the research scaffold."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from .config import load_case
from .graph import invoke_case

app = typer.Typer(help="Patch2Proof: evidence-grounded N-day reproduction pipeline")
console = Console()


@app.command()
def inspect(case_file: str):
    """Validate and print a case manifest without executing tools."""
    case = load_case(case_file)
    console.print_json(json.dumps(case.model_dump(mode="json"), indent=2))


@app.command()
def run(
    case_file: str,
    dry_run: bool = typer.Option(True, help="Do not build or execute Docker by default."),
    auto_approve: bool = typer.Option(False, help="Auto-approve only a reviewed dry-run case."),
    reasoning_mode: str | None = typer.Option(
        None,
        help="Explicit provider override: openai or ollama. Heuristic is test-only and opt-in.",
    ),
):
    """Run the complete LangGraph workflow."""
    result = invoke_case(
        case_file,
        dry_run=dry_run,
        auto_approve=auto_approve,
        reasoning_mode=reasoning_mode,
    )
    console.print(f"[bold]status:[/bold] {result.get('status')}")
    console.print(f"[bold]phase:[/bold] {result.get('phase')}")
    if result.get("report_path"):
        console.print(f"[bold]report:[/bold] {result['report_path']}")
    if result.get("errors"):
        console.print_json(json.dumps(result["errors"], indent=2))
    if "__interrupt__" in result:
        console.print(
            "Graph paused for approval. Resume through the LangGraph API or a case client."
        )


@app.command()
def show_graph():
    """Print the graph design summary."""
    path = Path("docs/graph.md")
    console.print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    app()
