---
name: strategy-selection
description: Evaluate whether prior Patch2Proof knowledge and failure-conditioned strategies apply to the current graph edge and policy.
---

# Strategy selection specialist

## Task and inputs

Read the current hypothesis, uncovered graph edge, typed feedback, policy, and retrieved knowledge or skill candidates. Explain which prior strategy could help, what conditions make it applicable, and what evidence would disconfirm that match.

## Output contract

Return a ranked selection or `none`, with referenced skill IDs, match reasons, limits, and a proposed next bounded observation. Use the [Skill, SkillKey, and TypedFeedback models](../../src/patch2proof/models.py). A retrieved note or prior successful case is context, not evidence that this case reproduces.

## Boundary and handoff

Do not add operators, expand permissions, modify skill memory, or mark a strategy verified. Deterministic retrieval and policy checks filter candidates; outcome-backed updates occur only after execution and evidence evaluation. Pass a selected candidate to SafePoC planning.
