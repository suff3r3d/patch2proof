# Package Storage and Semantic Validation

The `dacn` package provides immutable artifact/record storage, offline schema
validation, and deterministic package consistency checks. It does not build or
execute targets, interpret vulnerability signals, or derive a new CVE verdict.
It has no agent or LLM dependency.

## Interfaces and layout

Use Python 3.12 and the dependencies in
[`tests/schema/requirements-lock.txt`](../tests/schema/requirements-lock.txt).
The source package runs from the repository root without a build step. Run tests
and executable examples inside Docker using the [test workflow](../tests/schema/README.md).

| Interface | Input | Output |
|---|---|---|
| `SchemaCatalog(schema_root)` | Explicit trusted schema directory | Offline validators for the schemas in `schemas/`. |
| `CaseStore(root, catalog)` | Explicit case root and configurable limits | Store handle; construction and reads do not create files. |
| `put_artifact(stream, ...)` / `put_bytes(bytes, ...)` | Bytes, artifact ID, case ID, kind, provenance, optional parents | `StoredArtifact` with typed reference, relative path, size, and persisted record. |
| `put_record(record)` | Schema-valid JSON record | Relative path of a write-once record. Available artifacts must already match their bytes. |
| `load_records()` | Store's `records/` directory | Bounded, strictly decoded and schema-validated record list. |
| `PackageValidator(catalog).validate(root, manifest_id, records)` | Explicit case root, manifest ID, and record set | `ValidationReport` with diagnostics, timestamp, validator version, and canonical record hashes. |

```text
case/
  records/<sha256-of-record-id>.json
  artifacts/sha256/<sha256-of-raw-bytes>
```

IDs remain opaque; hashing them prevents their use as filesystem paths. Identical
bytes can share a blob while retaining separate artifact IDs and provenance.
All supplied records must belong to the selected case, and the manifest must
index every supplied source and artifact, including retained failed-attempt
evidence. All references resolve within that set. The CLI loads all records in
the case store; the API can accept an explicitly selected set for managed history.

## Publication, interruption, and immutability

Artifacts stream into a temporary file on the destination filesystem. The store
computes SHA-256 and size, enforces its byte limit, flushes and fsyncs the complete
bytes, and publishes through a no-overwrite hard link. It publishes the artifact
record only after the blob exists and matches its digest and size. Records use
the same atomic publication mechanism with deterministic JSON encoding.

Reusing a record ID succeeds only for identical canonical content, including
provenance. Preserve the original provenance on an idempotent retry. Corrections
require new IDs. Redaction/normalization creates a new artifact with `derived_from`
references; original bytes remain unchanged.

Caught interruptions remove the current temporary file. A process kill may leave
`.pending-*` files, which readers ignore. Failure between blob and record
publication may leave a complete unreferenced blob. Retrying checks and reuses
that blob. There is no garbage collection or multi-record transaction: publish
a new manifest after its records. Never promote partial files or delete orphan
evidence automatically.

The API publishes files read-only and never overwrites them. This does not stop
a host administrator modifying bytes; validation rehashes them. Keep package
directories application-controlled and unwritable by target containers. Do not
mutate in-memory inputs concurrently during validation.

Directory-descriptor traversal rejects symlinks at every component, absolute
paths, parent segments, Windows drive paths, and special files such as FIFOs.
The store requires POSIX filesystem features available in Linux Docker; an
unsupported operation fails explicitly. Stored artifacts are not executable.

## Checks and diagnostics

Validation checks schemas, duplicate IDs, and manifest identity first.
Invalid structures stop reference traversal. It then checks references and bytes;
invalid references or integrity failures stop relational checks. Diagnostics
contain a stable `code`, research `failure_class`, `record_id`, JSON pointer
`path`, and message. Fix prerequisites and rerun to reach subsequent checks.

Implemented checks include:

- Reference existence/type, case membership, source/artifact
  inventories, and reference-to-artifact digests. Raw metadata and claim values
  are never interpreted as links.
- Actual artifact hash/size, availability, path safety, and changes during a read.
- Selected build roles/environments/revisions, distinct source trees and output
  sets, and consistent observed paired toolchains and dependencies.
- Execution-to-build and executable-to-output relationships, candidate digests,
  comparison groups, and matched benign-control inputs.
- Equal paired limits, environment variables, and working directories. Execution
  limits may be stricter than environment limits, treated as ceilings here.
- Build/run ordering, verification after consumed runs, manifest/verification
  execution selection, and final status/verdict agreement.
- Observable check prerequisites; `VERIFIED` records require completed,
  untruncated runs and benign controls on both selected builds.

`valid: true` means these integrity and consistency checks passed. It does not
mean `VERIFIED`, prove a source claim, or establish that observations support the
reported signal. An intact early-failure package can be valid with
`INVALID_ENVIRONMENT`. Contradictory identities produce diagnostics even if a
stored verdict already acknowledges failure; nothing is silently repaired.
Signal parsing, code-region evidence, patch attribution, and evidence-based
verdict selection remain the future adapter/oracle's responsibility.

## Supported baseline and limits

- Schema and semantic validation use the current schemas in `schemas/`.
- Build/execution network flags must be false. Nonempty role overrides require
  future comparison-policy support and are rejected explicitly.
- Controls use different benign input bytes on the selected paired builds.
  Alternative control dimensions and separate control builds are not supported.
  No case-definition or adapter code is dynamically loaded or executed.
- Semantics-changing repairs require an invalid build. Successful builds cannot
  contain failed commands; no review exception is silently inferred.
- Defaults: 64 MiB per artifact, 1 MiB per stored metadata record, and 10,000
  records per load/validation. Callers can adjust limits. Docker resource controls
  bound the process; this is not a target execution harness or build disk quota.

## Minimal API example

Run inside the documented Docker environment with writable `/tmp`:

```python
from pathlib import Path
from dacn.contracts import SchemaCatalog, utc_now
from dacn.storage import CaseStore
from dacn.validation import PackageValidator

catalog = SchemaCatalog(Path("/workspace/schemas"))
store = CaseStore(Path("/tmp/example-case"), catalog)
artifact = store.put_bytes(
    b"Synthetic fixture observation.\n",
    identifier="artifact-demo", case_id="case-demo", kind="fixture",
    provenance={"created_at": utc_now(), "created_by": "example"},
)
manifest = {
    "schema": "case-manifest",
    "id": "manifest-demo", "case_id": "case-demo", "package_version": "0.1.0",
    "provenance": {"created_at": utc_now(), "created_by": "example"},
    "status": "draft", "artifact_ids": [artifact.reference.id],
}
store.put_record(manifest)
report = PackageValidator(catalog).validate(store.root, manifest["id"], store.load_records())
assert report.valid
```

This draft has no reproduction claim. `StorageError` carries a diagnostic code
and failure class; `ContractError` carries schema diagnostics. Underlying I/O and
source errors propagate to the caller for classification in stage failure records.

## CLI and report persistence

Inside Docker, use:

```sh
python -m dacn validate --root /case --schemas /workspace/schemas --manifest-id manifest-demo
```

Mount the repository at `/workspace`, case at `/case`, and installed dependencies
at `/deps`, all read-only. Set `PYTHONPATH=/deps`, disable networking, and use the
pinned image and resource controls from the test workflow. No target or replay
command runs. Optional limits are `--max-artifact-bytes`, `--max-record-bytes`,
and `--max-records`.

Exit codes are `0` for valid, `1` for validation diagnostics, and `2` when inputs
or configuration cannot be loaded. Stdout is JSON suitable for capture as an
artifact. `canonical_record_sha256` hashes canonical JSON, not source formatting;
artifact digests always hash exact raw bytes.

Persist reports through `CaseStore.put_bytes(canonical_json(report.to_dict()), ... )`
using `kind="validation_report"`, creator/time provenance, and the checked
manifest ID as an input. Add the report to a new manifest's inventory. The report
describes the old snapshot; it must not claim to validate itself. The validator
performs no implicit writes.

## Tests

`tests/infrastructure/` exercises storage, interrupted publication, concurrent ID
conflicts, corruption, unsafe paths, paired identities, matched controls, and
store/load/CLI integration. Complete synthetic packages use real hashed bytes;
success-shaped and early-failure packages pass, while corrupted or inconsistent
variants fail. No live targets or real CVE reproductions run in these tests.
