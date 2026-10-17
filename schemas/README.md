# Schema registry

The JSON Schema Draft 2020-12 files in this directory are the current
contract. Eight describe persisted records; `common.schema.json` supplies shared
definitions. `cve-discovery-request.schema.json` and
`revision-discovery-result.schema.json` define the pre-ingestion interface for
CVE-led revision discovery. Schema IDs use
`urn:dacn:schema:<schema-name>` and persisted records select one with their
`schema` field. Records have no `schema_version` field, and the manifest has no
`schema_versions` map.

See the [discovery contract](../docs/revision-discovery-contract.md) for the
candidate evidence and unresolved-result rules. The CLI and graph now use this
interface for CVE-only dry runs.

Patch2Proof writes a validated draft package at the end of a pipeline report.
Its `dacn-package.json` index identifies the manifest and validation report.
Only record types supported by actual run data are published; the adapter does
not create synthetic build or execution records.

Revision resolution and patch context belong to `vulnerability-record`.
`execution-record` combines the requested invocation and observations for one
run. `verification-result` combines expectations, checks, and the reported
verdict. Environment declarations remain separate from observed builds. Raw
evidence is stored externally and referenced by records with provenance and
opaque IDs.

The environment contract supports Docker only. Every environment specification
must use `isolation.type: docker` and a digest-pinned image.

Validation is offline. Consumers register these files by `$id` before validating
a document; the test suite demonstrates this with `referencing.Registry`. The
[package validator](../docs/package-foundation.md) checks references, paired
identities, artifact hashes, ordering, and reported verdict consistency. Schema
validity alone does not establish factual evidence or a vulnerability verdict.
