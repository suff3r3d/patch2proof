# AGENTS.md

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
