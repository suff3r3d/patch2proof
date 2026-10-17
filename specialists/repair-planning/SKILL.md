---
name: repair-planning
description: Propose bounded, evidence-backed repairs to a failed Patch2Proof environment, startup, harness, or SafePoC attempt without widening policy.
---

# Repair planning specialist

## Task and inputs

Read typed failure diagnosis, current environment and SafePoC plans, logs, graph, prior attempts, allowed operators, and remaining budgets. Choose the failed layer before proposing a change. State the exact setting, fixture action, or allowed operator to change, why it should help, and what observation would reject it.

## Output contract

For SafePoC repairs, return a [typed `RepairDecision`](../../src/patch2proof/models.py) over allowed operators. For environment or startup repairs, return a proposal against the [environment declaration](../../schemas/environment-spec.schema.json) with affected fields, evidence IDs, role parity impact, and review requirement; this proposal contract still needs implementation. Preserve each attempt and its original artifacts rather than overwriting history.

## Boundary and handoff

Do not change source revisions, vulnerability semantics, oracle expectations, permissions, or network settings to force a passing result. Do not replay an identical failed attempt without a reason. Validators enforce operator allowlists and policy, and human approval applies to revised build or execution plans before controlled tools run them.
