# Patch2Proof

Evidence-grounded, differential, and safety-preserving N-day vulnerability reproduction pipeline.

Patch2Proof v0.4 is a research-oriented project for a final-year project or thesis. It orchestrates complete patch ingestion, revision-aware source context, recursive caller/callee investigation, provider-backed agent reasoning, a directed reproduction graph, failure-conditioned safe strategy memory, reproducible Docker environments, SafePoC generation, vulnerable/fixed differential validation, skeptic review, and evidence-backed reporting.

Patch2Proof v0.4 gives the model the complete patch, maps each hunk into the
vulnerable and fixed source snapshots, builds recursive caller and callee call
slices, and supports bounded read-only source queries. Static call edges are
candidates; they do not replace runtime reachability evidence. See
[`docs/source-analysis.md`](docs/source-analysis.md).

The project deliberately separates:

1. **Reasoning** — an explicitly selected model proposes evidence-linked hypotheses, bounded SafePoC plans and constrained repairs.
2. **Execution** — typed tools and a sandbox worker perform bounded actions.
3. **Proof** — deterministic oracles compare the vulnerable and fixed builds.
4. **Reporting** — only evidence-backed claims become findings.

The v2 contribution is an agent overlay on top of the DACN-style evidence
substrate: `VulnerabilityContract`, `ReproductionGraph`, typed
`TypedFeedback`, `AttemptRecord`, `SkillApplication` and a deterministic
`proof-bundle.json`. See [`docs/architecture-v2.md`](docs/architecture-v2.md),
[`docs/agent-reasoning.md`](docs/agent-reasoning.md),
[`docs/reproduction-graph.md`](docs/reproduction-graph.md),
[`docs/skill-memory.md`](docs/skill-memory.md) and
[`docs/dacn-integration.md`](docs/dacn-integration.md).

This repository is for authorized local labs and defensive research. The default policy is dry-run, network-disabled, no host mounts except a scoped artifact directory, and human approval before Docker builds or PoC execution.

## Research position

The project combines ideas from Patch-to-PoC/K-Repro, PoC-Adapt, CyberGym, SEC-bench, ReproBench, DrillAgent, and differential benchmark design. The project contribution is not merely “using LangGraph”; the proposed contribution is a **patch-to-proof protocol**:

```text
patch or advisory
  -> complete patch + source/call context
  -> evidence graph
  -> reproducible vulnerable/fixed environment
  -> constrained SafePoC
  -> semantic and differential oracle
  -> auditable final report
```

See [`docs/research-review.md`](docs/research-review.md) for the literature matrix and [`docs/novelty-and-research-questions.md`](docs/novelty-and-research-questions.md) for the proposed research questions.

The Ghostbyt3 reference workflow is discussed in [`docs/ghostbyt3-reference.md`](docs/ghostbyt3-reference.md). It inspired the optional local Ollama/Qdrant track, while Patch2Proof adds typed contracts, approval gates and differential validation.

## Quick start

### 1. Install

Using `uv`:

```bash
uv sync
uv run p2p --help
```

Using `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
p2p --help
```

### 2. Inspect the example case

```bash
p2p inspect examples/demo_case.yaml
```

The example uses a fixture patch and stays in dry-run mode. It does not contact any external target.

### 3. Run the graph in dry-run mode

The default policy is fail-closed and requires a reasoning provider. Configure
OpenAI or Ollama first; otherwise the graph writes a candidate report with a
configuration error instead of silently using a heuristic.

The case policy defaults to `reasoning_effort: medium` for a reasoning-capable
OpenAI model. Set it to `null` when using a standard chat model.

```bash
uv sync --extra llm
export P2P_LLM_MODE=ollama
export P2P_OLLAMA_MODEL=<reviewed-model>
p2p run examples/demo_case.yaml --dry-run --auto-approve
```

For dependency-light offline tests only:

```bash
P2P_LLM_MODE=heuristic P2P_ALLOW_HEURISTIC_REASONING=1 \
  p2p run examples/demo_case.yaml --dry-run --auto-approve
```

The command writes artifacts under `artifacts/demo-path-canary/`, including:

- `case.json`
- `raw-patch.diff` (complete ingested patch)
- `patch-analysis.json`
- `source-context.json` (verified hunk mapping, changed symbols, static caller/callee paths and query results)
- `reasoning-initial.json` and `reasoning-plan.json`
- `safe-poc-plan.json`
- `docker-plan.json`
- `safepoc.json`
- `validation.json`
- `vulnerability-contract.json`
- `reproduction-graph.json`
- `coverage.json`
- `attempt-*.json` and `feedback-*.json`
- `proof-bundle.json`
- `final-report.md`

### 4. Run the LangGraph server locally

```bash
langgraph dev
```

Install the server extra first if the CLI is not already available:

```bash
uv sync --extra server
```

The graph is declared in [`langgraph.json`](langgraph.json). For a Docker image of the orchestration server:

```bash
langgraph build -t patch2proof:dev
```

The target application images are built by the separate worker described in [`docs/docker-execution.md`](docs/docker-execution.md), not by giving the LLM direct Docker access.

Optional local AI services are described in [`deploy/docker-compose.local-ai.yaml`](deploy/docker-compose.local-ai.yaml). Start them only when the case policy and data-handling plan permit local model/RAG services:

```bash
docker compose -f deploy/docker-compose.local-ai.yaml up -d
```

Then set `P2P_LLM_MODE=ollama`, `P2P_OLLAMA_MODEL=<reviewed-model>` and `OLLAMA_BASE_URL=http://localhost:11434`. See [`docs/agent-reasoning.md`](docs/agent-reasoning.md).

## Real case workflow

1. Create a case manifest from [`examples/case-template.yaml`](examples/case-template.yaml).
2. Pin vulnerable and fixed Git references.
3. Supply a repository path under the configured allowlist.
4. Add a reviewed Dockerfile or select a supported language template.
5. Register a SafePoC test fixture and oracle.
6. Run the graph in dry-run mode first.
7. Review the generated Docker plan and SafePoC.
8. Enable build/execute only inside a disposable lab. Git cases are materialized into separate vulnerable/fixed contexts with `git archive` before Docker build.
9. Validate that the vulnerable build passes and the fixed build fails.
10. Inspect the report and evidence manifest before making a research claim.

## Repository map

```text
patch2proof/
├── src/patch2proof/          # Graph, models, analysis, worker and reporting code
├── templates/                # Dockerfile and report templates
├── config/                   # Default safety policy and prompts
├── examples/                 # Safe fixture case and case template
├── tests/                    # Unit tests for policy, diff analysis and reporting
├── docs/                     # Design, threat model, research review and evaluation
├── scripts/                  # Utility scripts
├── langgraph.json            # LangGraph CLI configuration
└── pyproject.toml            # Package and dependency definition
```

## Important limitations

- This is a thesis-grade research system, not a claim that vulnerability reproduction is solved.
- A successful trigger on the vulnerable image alone is insufficient; the fixed-image counterfactual is mandatory.
- LLM output is untrusted input. Source files, advisories and tool output are treated as data, not instructions.
- Python callers use AST extraction. Java and other non-Python call relations are structural candidates and must be checked against runtime traces; static call candidates alone never establish reachability.
- The runtime worker intentionally refuses arbitrary shell commands from the model.
- The production graph never silently falls back to heuristic reasoning; provider-backed artifacts are required for confirmation.
- Deserialization, RCE, SSRF and multi-service cases require additional reviewed adapters and should not be enabled by default.
- The built-in `fixture_simulated_differential` adapter is for contract tests only; its results are explicitly marked simulation and can never become `confirmed`.

## License

This scaffold is provided for research and educational use. Add the license required by your institution before publication.
