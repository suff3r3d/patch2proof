---
name: reproduction-planning
description: Plan bounded paired Patch2Proof reproduction attempts, fixture state, startup conditions, and observations for an evidence-linked hypothesis.
---

# Reproduction planning specialist

## Task and inputs

Read the hypothesis, causal graph, vulnerability contract, source evidence, available adapter capabilities, selected strategy, and environment facts. Choose the next uncovered transition. Describe fixture state, invocation, startup assumptions, observable signal, vulnerable expectation, fixed expectation, and negative control.

## Output contract

Produce a typed `SafePoCPlan` proposal using [the plan and SafePoC models](../../src/patch2proof/models.py). Identify required build or runtime flags as *requirements for environment review*, with source evidence and uncertainty; do not smuggle them into an action target. Give a measurable oracle and the result that would falsify the hypothesis.

## Boundary and handoff

Use only registered adapters and the finite SafePoC action vocabulary. No arbitrary shell, public target, credential access, destructive effect, or network expansion. The compiler validates actions and the execution gate reviews the concrete paired attempt. Never present a planned or simulated result as observed reproduction.
