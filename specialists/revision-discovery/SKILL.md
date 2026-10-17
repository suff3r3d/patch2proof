---
name: revision-discovery
description: Resolve a CVE to evidence-backed vulnerable and fixed Git revisions for Patch2Proof; use during CVE-led discovery, not runtime verification.
---

# Revision discovery specialist

## Task and inputs

Read a `cve-discovery-request`, retrieved advisory/source records, and bounded Git metadata. Compare plausible repositories, fixing commits, tags, and affected ranges. Establish why each proposed revision represents the vulnerable or fixed state; a fixing commit's parent is only a candidate.

## Output contract

Propose a `revision-discovery-result` with candidate pairs, source IDs, immutable commit IDs, checks, uncertainty, and selection rationale. Feed supported identity and revision claims into `vulnerability-record`. Follow [the discovery contract](../../docs/revision-discovery-contract.md) and validate against [the request](../../schemas/cve-discovery-request.schema.json), [result](../../schemas/revision-discovery-result.schema.json), and [vulnerability record](../../schemas/vulnerability-record.schema.json).

Return `ambiguous` or `failed` when sources conflict or a required check cannot be supported. Do not invent revisions, promote an untagged commit link to proof, or call a resolved pair a reproduced vulnerability.

## Boundary and handoff

Request retrieval and Git inspection through bounded, read-only tools. The verifier checks source hashes, repository identity, commits, and selected-candidate consistency. Pass only verified pinned revisions to ingestion. Never execute the target or change case policy.
