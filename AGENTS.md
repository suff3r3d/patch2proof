# AGENTS.md

<<<<<<< HEAD
## Purpose

This repository supports the research project **"Research and Development of an AI Pipeline for Automated Reproduction of 1-Day Vulnerabilities."**

This file defines the rules for AI coding and research assistants working in the repository. These assistants are not the same as any runtime vulnerability-reproduction agents that may be added to the system.

The current implementation priority is **reproduction and verification infrastructure**. Unless the user explicitly requests advanced-agent work, prioritize this infrastructure and do not introduce complex agent reasoning, LangGraph orchestration, a Supervisor Agent, or autonomous PoC generation into the baseline pipeline.

---

## Mandatory User Approval Workflow

This section is a high-priority operating rule for every agent working in this repository.

Before starting any new task or taking any action, the agent must:

1. Briefly state what it plans to do and the expected scope.
2. Ask the user for explicit approval.
3. Wait for approval before using tools, reading or editing files, executing commands, running tests, performing research, delegating work, or making any external change.

A user request does not by itself count as approval to begin execution. The agent must restate the intended action and receive a separate explicit confirmation before proceeding.

Approval is limited to the described task and scope. If an important new action, scope expansion, or materially different approach becomes necessary, pause and ask again. Do not interpret approval for one task as permission for unrelated follow-up work.

After completing the approved work, the agent must:

1. Summarize what was completed and mention any important result or limitation.
2. List the reasonable next steps in a short, ordered list.
3. Ask the user which next step, if any, should be performed.
4. Stop and wait. Do not begin a suggested next step without explicit approval.

If no meaningful next step exists, state that clearly and still return control to the user.

---

## 1. Project Objective

The project studies whether public information about a disclosed 1-day vulnerability can be converted into:

1. A correctly reconstructed vulnerable environment.
2. A comparable patched environment.
3. A minimal trigger or regression test.
4. Executable evidence tied to the target vulnerability.
5. A repeatable and auditable reproduction package.

The project is not satisfied by merely producing a crash, exception, non-zero exit code, or abnormal response.

A reproduction is accepted only when the observed signal can be connected to the target CVE through executable evidence and meaningful comparison with the patched build and appropriate controls.

---

## 2. Authority and Source of Truth

When making project decisions, use the following order of authority:

1. The user's current request.
2. The official project description and research questions.
3. This `AGENTS.md`.
4. Existing repository documentation and schemas.
5. Current implementation conventions.

Do not silently change research scope, success criteria, benchmark policy, or safety boundaries. If the implementation and project description disagree, identify the conflict before making a scope-changing decision.

---

## 3. Scope Boundaries

### Reproduction Infrastructure — Current Priority

The current implementation track builds a deterministic execution substrate for reproduction and verification before complex AI reasoning is introduced.

Its required layers are:

1. **Vulnerability Intake**
   - Accept a CVE ID or vulnerability record.
   - Collect advisories, CWE data, affected/fixed versions, repository references, patch references, and build metadata.

2. **Evidence Normalization**
   - Convert heterogeneous public sources into a versioned vulnerability package with a stable schema.
   - Preserve source, retrieval time, raw value, normalized value, and confidence where applicable.

3. **Environment Reconstruction**
   - Resolve vulnerable and patched revisions.
   - Reconstruct dependencies, compiler/runtime versions, build flags, and required configuration.
   - Produce comparable vulnerable/patched builds in isolated environments.

4. **Static Context Extraction**
   - Extract patch diffs, changed files/functions, nearby call context, and initial reachability information.
   - Keep extraction evidence-based; do not present heuristic inference as confirmed fact.

5. **Execution Harness**
   - Provide a uniform interface to build and run artifacts.
   - Collect stdout, stderr, exit status, timing, sanitizer output, stack traces, debugger evidence, and coverage when available.

6. **Verification Oracle**
   - Execute the same candidate artifact against the vulnerable build, patched build, and negative controls.
   - Produce a structured verdict with evidence and provenance.

This scope also includes a manually verified benchmark, a non-agentic baseline pipeline, RQ1.1/RQ1.2 experiments, failure analysis, reporting, and an end-to-end demonstration.

### Advanced-Agent Architecture — Deferred Unless Explicitly Requested

Advanced-agent work adds AI reasoning above the reproduction and verification substrate. Planned roles include:

- Vulnerability Analyst.
- Reproduction Planner.
- Environment Agent.
- Test Generator.
- Execution Agent.
- Failure Classifier.
- Adaptive Refiner.
- Verifier.
- A Supervisor or equivalent orchestration component.

The planned loop is:

```text
Observe -> Analyze -> Plan -> Execute -> Verify -> Refine
```

Advanced-agent work may use LangGraph or another orchestration framework, but the core infrastructure interfaces must remain usable without it.

Do not couple core schemas, environment builders, runners, or verification logic to a particular LLM provider or agent framework.

---

## 4. Core Research Principles

### 4.1 Evidence Over Model Claims

LLM output is never proof of successful reproduction.

Treat model-generated explanations as hypotheses or interpretations. Final claims must be supported by executable artifacts and observations collected from the controlled environment.

### 4.2 Paired Counterfactual Execution

Prefer the following comparison for every candidate trigger:

```text
same artifact + vulnerable build -> target signal
same artifact + patched build    -> target signal absent or safe behavior
negative control                 -> target signal absent
```

Keep the two builds comparable. Except for the target revision and unavoidable revision-specific changes, use the same:

- Operating-system base.
- Architecture.
- Compiler and runtime.
- Dependency policy.
- Build mode and relevant flags.
- Instrumentation.
- Resource limits.
- Harness behavior.

Record and justify any asymmetry.

### 4.3 Reproducibility

Every accepted case must retain enough information to run it again:

- Source repository and immutable revisions.
- Dependency versions and checksums where available.
- Compiler/runtime identity.
- Build commands, configuration, and environment.
- Trigger or regression harness.
- Execution commands.
- Raw evidence.
- Vulnerable/patched/control results.
- Oracle verdict.
- Replay script or equivalent automated entry point.

### 4.4 Provenance

Important derived values must remain traceable to their sources. Do not overwrite raw evidence with normalized or summarized values.

For each material decision, retain where practical:

- Input source.
- Transformation or command.
- Tool version.
- Timestamp.
- Output artifact.
- Exit status.
- Content hash.
- Confidence or uncertainty.

### 4.5 Minimality

The target output is a minimal vulnerability trigger or regression test sufficient to verify the vulnerability. Full weaponization is neither required nor desired.

Minimization must not remove the behavior that connects the trigger to the patch or root cause.

---

## 5. Verification Contract

The oracle must not reduce verification to `crashed == true`.

At minimum, evaluate:

- Whether the expected signal appears on the vulnerable build.
- Whether the signal disappears or becomes the expected safe behavior on the patched build.
- Whether matched benign inputs avoid the target signal.
- Whether the stack trace, sanitizer report, coverage, state change, or regression assertion reaches the relevant code region.
- Whether the observed difference is consistent with the patch and known root cause.
- Whether environment instability could explain the result.

Use explicit verdicts. Recommended top-level states are:

```text
VERIFIED
NOT_REPRODUCED
INCONCLUSIVE
INVALID_ENVIRONMENT
```

Suggested meanings:

- `VERIFIED`: executable evidence supports a CVE-specific reproduction and required controls pass.
- `NOT_REPRODUCED`: the environment is valid, but the candidate does not produce sufficient target evidence.
- `INCONCLUSIVE`: some evidence exists, but attribution or controls are insufficient or contradictory.
- `INVALID_ENVIRONMENT`: build or runtime validity is insufficient for a reproduction judgment.

Never convert `INCONCLUSIVE` or `INVALID_ENVIRONMENT` into success for reporting convenience.

---

## 6. Failure Taxonomy

Failures must be classified before repair or retry. At minimum distinguish:

- `metadata_failure`: missing, conflicting, or incorrectly normalized vulnerability information.
- `revision_failure`: vulnerable/fixed revision cannot be resolved or is incorrect.
- `dependency_failure`: dependency cannot be obtained, pinned, or made compatible.
- `toolchain_failure`: compiler, runtime, SDK, or build-tool mismatch.
- `configuration_failure`: required feature, flag, service, or runtime configuration is absent.
- `build_failure`: source does not compile or link after prerequisites are valid.
- `startup_failure`: target builds but cannot start or initialize correctly.
- `harness_failure`: the test interface does not invoke or observe the target correctly.
- `reachability_failure`: the candidate input does not reach the relevant code path or state.
- `hypothesis_failure`: the proposed root cause or triggering condition is wrong.
- `oracle_failure`: telemetry or controls cannot distinguish the target behavior reliably.
- `control_failure`: the patched build or negative control produces the same supposedly CVE-specific signal.
- `resource_failure`: timeout, memory, disk, or execution quota prevents a valid judgment.

Do not repeatedly modify the trigger when evidence indicates an environment failure. Do not repeatedly repair the environment when the paired builds are valid and evidence indicates a hypothesis or reachability failure.

Store failed attempts when they provide useful evidence; failed trajectories are research data.

---

## 7. Vulnerability Package Requirements

Use a stable, versioned schema. A package should be able to represent:

```text
identity
  CVE/advisory identifiers
  title and description
  CWE or vulnerability class

sources
  advisory references
  repository references
  issue/commit references
  retrieval metadata

revisions
  vulnerable revision
  patched revision
  revision-resolution evidence

patch
  commits and diff
  changed files/functions
  patch evidence

environments
  platform and architecture
  toolchain/runtime
  dependencies
  configuration and build commands

artifacts
  trigger/harness
  replay entry point
  generated files and hashes

executions
  vulnerable run
  patched run
  negative-control runs

verification
  expected signal
  observations
  verdict
  rationale and uncertainty
```

Schema changes must be backward-aware. Version the schema and provide migration or compatibility handling when stored benchmark cases already use an older form.

---

## 8. Artifact and Evidence Rules

Do not place large logs, binaries, core dumps, coverage databases, or debugger transcripts directly in shared state or summary records.

Store them as artifacts and reference them using metadata such as:

```yaml
artifact_id: run-vuln-asan-log
kind: sanitizer_report
path: artifacts/<case>/<run>/asan.log
sha256: <digest>
producer: execution_harness
```

Keep summaries concise, but preserve raw evidence.

Do not edit raw run output after collection. If redaction or normalization is needed, create a derived artifact and retain the relationship to the original.

Avoid embedding host-specific absolute paths in reusable packages. Use case-relative artifact paths in stored manifests.

---

## 9. Environment Reconstruction Rules

- Docker containers are the only permitted build and execution environment.
  Do not run project builds, targets, triggers, or generated artifacts directly
  on the host or in another container engine, sandbox, or virtual machine. If
  the Docker daemon is unavailable, stop and report the environment as
  unavailable rather than substituting another runtime.
- Prefer immutable source revisions over moving branches or tags.
- Pin every Docker base image by immutable digest. A tag alone is insufficient.
- Pin dependencies or record the exact resolution result.
- Record compiler, linker, runtime, package-manager, and build-system versions.
- Keep dependency acquisition separate from reproduction execution.
- Disable network egress during build execution and trigger execution by default; enable it only for a controlled dependency-acquisition step.
- Never repair vulnerable source code merely to make it compile without recording the change.
- Classify repairs as environment-only, source-compatible, or semantics-changing.
- A semantics-changing repair invalidates direct comparison unless explicitly justified and reviewed.
- Ensure vulnerable and patched builds are not accidentally backed by the same binary, layer, cache entry, or revision.
- Hash relevant source, build outputs, and triggers to detect accidental reuse or drift.

---

## 10. Execution Harness Rules

The harness should expose a stable interface independent of individual projects.

Each run should capture, where applicable:

- Command and arguments.
- Working directory.
- Explicit environment variables.
- Input artifact identity.
- Start/end time and duration.
- Exit code and terminating signal.
- stdout and stderr.
- Timeout or resource-limit event.
- Sanitizer report.
- Stack trace or debugger output.
- Coverage summary and relevant code locations.
- Output files and state changes.

Runs must have bounded time, memory, process count, disk use, and output size. A timeout is not automatically a vulnerability signal.

Instrumentation must be configurable. A case should declare which instrumentation is required, optional, unavailable, or incompatible.

---

## 11. Benchmark Rules

The benchmark is a research dataset, not a collection of unreviewed public PoCs.

Each benchmark case should have manually reviewed ground truth including:

- Why the selected revision is vulnerable.
- Why the selected comparison revision is patched.
- Patch or fixed-version evidence.
- Expected vulnerability class and root cause.
- Expected observable signal.
- Known prerequisites and limitations.
- A replayable reference artifact when available.

Benchmark selection should favor, initially:

- Open-source projects.
- Linux-compatible targets.
- Legally retrievable historical versions.
- Memory-safety, parser/input-validation, and observable logic vulnerabilities.
- Cases with a usable patch, fixed version, or fixing commit.

Avoid making the initial benchmark dominated by one project, one language, one vulnerability class, or only trivially buildable cases.

Keep benchmark curation separate from evaluation. Human ground-truth work is allowed, but humans must not manually repair the agent strategy during automated evaluation runs.

---

## 12. Baseline and Experiment Integrity

The baseline must work without complex agent reasoning.

Do not quietly add model-generated hints, manual trigger edits, patch-derived answers, or hidden environment repair to a baseline run. Record intervention level explicitly.

For controlled comparisons:

- Use the same benchmark split.
- Use comparable compute and time budgets.
- Freeze relevant pipeline and schema versions.
- Record all supplied information sources.
- Separate development cases from held-out evaluation cases.
- Report failures, retries, excluded cases, and missing data.
- Preserve every final verdict and the evidence used to produce it.

Track at least:

- Environment reconstruction success rate.
- CVE-specific reproduction success rate.
- Oracle false-positive rate on patched builds and negative controls.
- Time to environment and time to verdict.
- Number and class of repair attempts.
- Resource cost.
- Degree of automation and human intervention.

For later advanced-agent comparisons, also track model/tool cost, iterations, replanning behavior, and trajectory provenance.

---

## 13. Implementation Architecture

Maintain clear boundaries between:

```text
collect -> normalize -> resolve -> build -> extract -> execute -> verify -> report
```

Each stage should consume and produce structured data. Avoid hidden cross-stage mutation and avoid reading arbitrary global files when required inputs can be declared explicitly.

Recommended design properties:

- Idempotent stage execution where practical.
- Resumable runs.
- Content-addressed or uniquely identified artifacts.
- Explicit stage status and failure reason.
- Pluggable project-specific adapters.
- Generic core orchestration.
- Deterministic behavior before heuristic fallback.
- Machine-readable results plus concise human-readable reports.

Project-specific build logic belongs in adapters, manifests, or case definitions rather than conditionals scattered across the core runtime.

The verification oracle must remain callable independently from any AI agent.

---

## 14. Advanced-Agent Architectural Guidance

When advanced-agent work is explicitly in scope, use the existing reproduction substrate rather than duplicating build, execution, or verification inside prompts or agent code.

The user should interact with a configurable Supervisor as the default entry point. The Supervisor may interpret a request, decompose it into bounded tasks, assign specialist roles, manage dependencies, evaluate results, and produce the final response.

Keep these concepts distinct:

```text
Agent       = specialized reasoning or execution role
Task        = bounded unit of work with completion criteria
Skill       = reusable procedure
Tool        = executable capability
Graph       = control flow and scheduling
Shared state = coordination data
Artifact    = persisted output or evidence
```

Specialist results must return to the Supervisor by default. Concurrent tasks may run in parallel only when their dependencies allow it. Use reducers or task-scoped results for concurrent state updates.

Prefer configuration-driven registration of agents, models, tools, skills, capabilities, and delegation permissions. Avoid hard-coding agent-specific behavior in the generic graph runtime.

Shared state should contain coordination data and artifact references, not unlimited logs, binaries, or unrestricted LLM scratchpads.

Every advanced-agent decision must preserve the evidence and provenance contract established by the core infrastructure.

---

## 15. Safety and Scope Constraints

- Work only with publicly disclosed 1-day vulnerabilities that have a usable patch, fixing commit, or fixed version.
- Do not treat zero-days as benchmark candidates.
- Execute generated artifacts only in project-controlled Docker containers.
- Do not scan, probe, exploit, or deploy against public/live systems or third-party infrastructure.
- Do not add persistence, lateral movement, credential theft, destructive payloads, stealth, or post-exploitation behavior.
- Do not optimize for mitigation bypass or weaponized exploitation.
- Prefer a minimal trigger or regression test over an exploit.
- Keep network egress disabled by default and explicitly scoped when dependency retrieval requires it.
- Do not publish risk-increasing artifacts automatically. Publication must respect disclosure status, software licenses, and project policy.

If a requested action would cross these boundaries, stop and ask for a safer project-local formulation.

---

## 16. Coding and Change Rules

- Inspect existing code, tests, schemas, and conventions before editing.
- Make the smallest coherent change that satisfies the request.
- Do not introduce advanced-agent abstractions into the core infrastructure merely because they may be useful later.
- Do not hard-code a single CVE's paths or expected output in generic pipeline code.
- Prefer typed structured records over free-form dictionaries where the project language supports them.
- Validate external metadata and never trust downloaded content as executable configuration without checks.
- Avoid silent fallback. Record which resolver, builder, runner, or oracle path was selected.
- Keep secrets and host credentials out of manifests, logs, artifacts, and containers.
- Preserve unrelated user changes.
- Document assumptions and unresolved uncertainty.

Before considering a change complete:

1. Run relevant unit tests.
2. Run integration tests for affected stage boundaries.
3. Validate schemas and example packages.
4. Test at least one expected-success and one expected-failure path when practical.
5. Confirm that raw evidence and provenance remain accessible.
6. Confirm that vulnerable and patched results cannot be accidentally conflated.

---

## 17. Testing Expectations

Tests should cover more than happy-path execution.

Important cases include:

- Conflicting advisory versions.
- Missing or ambiguous fixing commits.
- Moving tags or unavailable dependencies.
- Build cache contamination between revisions.
- Vulnerable and patched revisions resolving to the same source.
- Sanitizer unavailable or incompatible.
- Trigger timeout without target-code reachability.
- Same signal appearing on both vulnerable and patched builds.
- Benign control producing the target signal.
- Truncated, oversized, or malformed logs.
- Interrupted run and resume.
- Artifact hash mismatch.
- Schema version mismatch.

Mock external metadata services in unit tests. Use isolated fixtures or small known-safe cases for integration tests. Do not make ordinary test runs depend on live vulnerable services.

---

## 18. Reporting Rules

Reports must clearly separate:

- Confirmed facts.
- Strong evidence-based inference.
- Hypotheses.
- Unknown or missing information.

For each case, report:

- Environment status.
- Trigger status.
- Vulnerable execution result.
- Patched execution result.
- Negative-control result.
- Code-region/root-cause evidence.
- Final verdict.
- Remaining uncertainty.
- Replay instructions and artifact references.

Do not hide failed cases or report only successful examples. Aggregate results must include denominators, exclusion reasons, and the selected unit of analysis.

---

## 19. Completion Criteria

A core infrastructure feature is complete when:

- Its input and output contracts are defined.
- Success and failure states are explicit.
- Relevant evidence and provenance are persisted.
- It is independently testable.
- It works without an LLM or runtime agent unless the feature is explicitly experimental.
- It integrates with adjacent pipeline stages.
- It has replayable tests or fixtures.
- Documentation states assumptions and limitations.

A benchmark reproduction is complete only when:

- The environment is valid.
- The vulnerable and patched builds are correctly identified.
- The artifact runs reproducibly.
- The vulnerable build provides the expected target evidence.
- The patched counterfactual and negative controls behave as required.
- The oracle emits a justified structured verdict.
- The entire case can be replayed in its declared Docker container.

---

## 20. Non-Goals

Unless the user explicitly changes the research scope, do not optimize the project for:

- Zero-day discovery.
- Fully weaponized exploits.
- Public-target testing.
- Automated post-exploitation.
- Training a new foundation model.
- Replacing empirical evidence with LLM judgment.
- Maximizing raw crash count.
- Supporting every operating system, architecture, or vulnerability class in the initial implementation scope.
- Building the full multi-agent framework before the reproduction substrate is usable and evaluated.

---

## 21. Guiding Principle

The project should move from:

```text
"the input caused something unusual"
```

to:

```text
"a replayable artifact produced vulnerability-specific evidence on the
vulnerable build, did not produce that evidence on the patched build or
matched negative controls, and the result is traceable to the target patch
and code path."
```

Build every component around making that final claim reliable, repeatable, and auditable.
=======
Guidelines and operating principles for AI assistants working on **Patch2Proof**.

---

## 1. Project Overview

**Patch2Proof** is an evidence-grounded, differential, and safety-preserving N-day vulnerability reproduction research pipeline.

The system enforces a clean separation across four planes:
1. **Reasoning Plane**: LLM generates hypotheses, plans bounded SafePoCs, and proposes constrained repairs.
2. **Control Plane**: LangGraph orchestrates the 21-node workflow with human-in-the-loop approval gates.
3. **Execution Plane**: Paired Docker containers (`vulnerable` vs. `fixed`) run identical SafePoC actions with strict resource quotas and `network: none`.
4. **Proof & Evidence Plane**: Six deterministic coverage gates evaluate evidence, computing an auditable verdict (`confirmed`, `candidate`, `rejected`, `blocked`, `not_executed`) and a SHA-256 verified `proof-bundle.json`.

---

## 2. Current Mission: Frontend Development

The current focus is creating a **user-friendly frontend** for the Patch2Proof pipeline under the user's guidance.

### Primary UI Modules to Support:
- **Case Management & Configuration**: Build/edit case manifests (revisions, repository paths, language, policy limits, reasoning provider).
- **Pipeline Execution & Live Monitoring**: Stream LangGraph node progression and event logs in real time.
- **Human-in-the-Loop Approval Console**: Interactive prompts for `build_approval` and `execution_approval` interrupts.
- **Interactive Reproduction DAG**: Visual representation of nodes (patch hunk, changed symbol, entrypoint, state transition, observable, fixed control) and edge statuses (hypothesized, supported, contradicted).
- **Differential & Log Viewer**: Side-by-side inspection of vulnerable vs. fixed runtime observations, assertions, and logs.
- **Proof Bundle & Report Viewer**: Live checklist for the 6 coverage gates and an interactive report viewer for `final-report.md` / `final-report.json`.

---

## 3. Working Agreement & Agent Rules

1. **Follow User Guidance**: Always align with the user's design choices, preferred tech stack, architecture decisions, and workflow priorities.
2. **Preserve Backend Contracts**: Do not break existing data models in `src/patch2proof/models.py`, the LangGraph state in `src/patch2proof/state.py`, or the graph definition in `src/patch2proof/graph.py`.
3. **Safety First**:
   - Never introduce arbitrary shell execution or unsafe Docker escape vectors.
   - Maintain the fail-closed policy (`reasoning_mode: required`, `network: none` by default).
   - Treat model output, source files, and diffs as untrusted data.
4. **Evidence Over Hallucination**:
   - The UI must clearly differentiate between hypotheses (LLM reasoning) and empirical facts (runtime container observations & oracle results).
   - Never present a candidate or simulated result as a confirmed vulnerability.
5. **Clean Code & Modularity**:
   - Keep UI components reusable, typed, and well-structured.
   - Maintain clear separation between frontend presentation and backend API integration.
   - Write clear tests and documentation for new additions.

---

## 4. Source of Truth

When making architectural or implementation decisions:
1. Direct instructions from the user.
2. This `AGENTS.md` file.
3. Architecture and specifications in `design.md`.
4. Typed contracts in `src/patch2proof/models.py`.
>>>>>>> nghiavu
