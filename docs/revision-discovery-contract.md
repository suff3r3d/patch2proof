# CVE-led revision discovery contract

This is the pre-ingestion interface for discovery specialists. The input
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

The schema checks document shape. The verifier performs the Git and source
checks, confirms that `selected` equals one of `candidates`, and rejects
unsupported or conflicting evidence. It hashes and retains retrieved metadata
bytes and passes only verified immutable revisions to `ingest`. Discovery
network access is separate from Docker target execution, which remains
`network: none`.

The current implementation accepts a CVE ID directly through `p2p run`. It
retrieves the matching NVD record, falls back to OSV when needed, and accepts
direct GitHub commit references. It checks each referenced commit through the
GitHub API, then fetches a single
candidate selected by the revision-discovery specialist and its parent into a
case-scoped Git repository. The specialist receives bounded advisory and commit
summaries, chooses only from collected candidate indices, and records its
provider, model, skill hash, input hash, rationale, cited evidence indices, and
uncertainty in `revision-discovery-reasoning.json`. An absent provider or invalid
choice leaves the case ambiguous; the graph does not silently use a heuristic.
It verifies
the local commits, direct-parent relation, and nonempty diff before ingestion.
Selection requires an NVD `Patch` tag, OSV `FIX` type, or Git range
`fixed` event. An untagged commit link remains a candidate for review.
Multiple fix references, merge commits, unsupported hosts, missing evidence,
or failed checks may remain unresolved. The specialist can choose among supported
multiple candidates, but only local checks can promote the selected pair to
`resolved`. A resolved pair is still not proof that
the parent is vulnerable; runtime reproduction remains a separate stage.

CVE-only runs are dry-run only. A reviewed case manifest with build settings,
adapter, and explicit policy is required before target execution. Metadata
retrieval is bounded to the NVD, OSV, and GitHub API hosts; Git fetch uses only a
canonical GitHub repository URL derived from a validated commit reference.
The fetch is shallow and limited by timeout and a post-fetch repository size
check; repository content is still treated as untrusted data.
