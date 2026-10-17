---
name: report-writing
description: Draft an evidence-grounded Patch2Proof research narrative from validated records, coverage, and computed verdict without changing the verdict.
---

# Report writing specialist

## Task and inputs

Read the case, source and vulnerability records, environment declaration, observed build/execution records, graph, attempts, coverage, verification result, and artifact inventory. Explain what was observed, what is inferred, what remains hypothetical, and what would be needed to resolve gaps.

## Output contract

Draft concise report sections with record/artifact citations, precise vulnerable/fixed comparisons, reproducible settings, limitations, and a claim strength that matches the computed verdict. Use the [verification result](../../schemas/verification-result.schema.json) and [case manifest](../../schemas/case-manifest.schema.json) as the authoritative outcome and package index.

## Boundary and handoff

Do not invent build flags, observed signals, hashes, or missing controls. Do not upgrade candidate, simulated, invalid-environment, or unexecuted outcomes. The report renderer and package validator retain control of the final verdict, artifact hashes, and published records.
