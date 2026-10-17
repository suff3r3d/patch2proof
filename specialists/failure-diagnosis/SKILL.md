---
name: failure-diagnosis
description: Diagnose a Patch2Proof build or paired execution failure from observed logs, records, and coverage without assigning the final vulnerability verdict.
---

# Failure diagnosis specialist

## Task and inputs

Read declared environment, observed build and execution records, logs, graph coverage, oracle results, and attempt history. Separate dependency, toolchain, configuration, build, startup, harness, reachability, hypothesis, oracle, control, and resource failures. Identify the earliest supported failure layer and alternative explanations.

## Output contract

Return typed `TypedFeedback` or a proposed extension when its current failure classes are insufficient. Include exact build/execution/artifact IDs, relevant log locations, confidence, missing evidence, and the next bounded diagnostic action. Use [build records](../../schemas/build-record.schema.json), [execution records](../../schemas/execution-record.schema.json), and [the failure taxonomy](../../docs/schema-usage-guide.md#41-failure-taxonomy).

## Boundary and handoff

Do not infer successful startup from a successful image build, absence of a signal from truncated logs, or a vulnerability from a crash. Do not select `confirmed` or edit coverage gates. Pass the diagnosed layer to repair planning; deterministic coverage and verification consume only observed evidence.
