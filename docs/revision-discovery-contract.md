# CVE-led revision discovery contract

This is the pre-ingestion interface for future discovery specialists. The input
is a [CVE discovery request](../schemas/cve-discovery-request.schema.json) with
only `cve_id` required. An optional HTTPS `repository_hint` narrows the search;
it does not supply a trusted repository identity or revisions.

The [discovery result](../schemas/revision-discovery-result.schema.json) records
candidate repository and commit pairs. Every candidate has an HTTPS repository
URL, immutable Git commit IDs for vulnerable and fixed source, the proposed fix
commit, source evidence with retrieval time and SHA-256 content digest, and five
checks. A fixing commit's parent may be a vulnerable candidate, but parenthood
alone does not establish that it is affected. A failed or unperformed check is
recorded as `failed` or `not_evaluated`.

`resolved` requires a selected pair with all five checks marked `passed`.
`ambiguous` keeps one or more candidates and a reason without selecting one.
`failed` gives a reason and may have no candidates. Neither a candidate nor a
resolved revision pair is a vulnerability reproduction verdict.

The schema checks document shape. The future verifier must perform the Git and
source checks itself, confirm that `selected` equals one of `candidates`, and
reject unsupported or conflicting evidence. It must hash and retain retrieved
source bytes, avoid arbitrary network destinations, and pass only verified
immutable revisions to `ingest`. Discovery network access is separate from
Docker target execution, which remains `network: none`.

The current CLI still requires a pinned repository and two refs. These schemas
specify the interface for the discovery step; no retrieval or graph integration
is implemented by this contract change.
