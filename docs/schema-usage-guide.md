# Phase 1 Schema Usage Guide

## 1. Purpose

This guide explains how pipeline components and future runtime agents should
use the `schemas/` records. The JSON Schemas define valid document shape;
this guide defines the intended workflow and meaning.


The active family contains eight persisted records:

```text
source-record ───────────────┐
                             v
artifact-record ──> vulnerability-record ──> environment-spec
                                                    |
                                                    v
                                              build-record
                                                    |
                                                    v
                                             execution-record
                                                    |
                                                    v
                                         verification-result
                                                    |
                                                    v
                                              case-manifest
```

`common.schema.json` is a definition library and is never persisted by itself.

## 2. Rules for every producer

Every pipeline component or agent that creates a record must follow these
rules:

1. Record only observed, sourced, or explicitly declared information.
2. Never invent a revision, version, digest, command, tool version, signal, or
   evidence reference to satisfy a required field.
3. If required information is unavailable, emit the appropriate failed,
   ambiguous, inconclusive, or invalid state.
4. Store raw bytes as artifacts. Do not embed full advisories, logs, binaries,
   traces, patches, or coverage files in records.
5. Preserve the same `case_id` across every record belonging to one case.
6. Treat record and artifact IDs as immutable after publication.
7. Use case-relative paths. Never store host-specific absolute paths or host
   credentials.
8. Keep vulnerable, patched, and negative-control roles explicit.
9. Validate the completed record against its schema before returning it.
10. Schema validity is not proof that the record is factually correct.
11. Execute builds and triggers only in project-controlled Docker containers.
    Never substitute host execution, another container engine, a sandbox, or a
    virtual machine when Docker is unavailable.
12. Never scan, probe, or execute against public or third-party targets.
13. Never add persistence, credential access, destructive behavior, stealth,
    lateral movement, or post-exploitation behavior.

When a value is uncertain, use an uncertainty field, a low or unknown
confidence, an appropriate failure state, or omit an optional field. Do not
convert uncertainty into a confirmed fact.

## 3. Stage and record ownership

| Stage | Reads | Produces | Primary responsibility |
|---|---|---|---|
| Collect | CVE ID or initial advisory locator | `source-record`, `artifact-record` | Preserve retrieved public evidence exactly. |
| Normalize and resolve | Sources and source artifacts | `vulnerability-record` | Normalize identity, revisions, patch facts, and uncertainty. |
| Specify environment | Vulnerability and patch requirements | `environment-spec` | Declare one comparable paired environment. |
| Build | Vulnerability revisions and environment | `build-record`, artifacts | Record what was actually built for each role. |
| Execute | Builds, candidate input, and harness | `execution-record`, artifacts | Record one bounded invocation and its observations. |
| Verify | Vulnerability context and all executions | `verification-result` | Apply the seven checks and issue one justified verdict. |
| Package | All accepted records and artifacts | `case-manifest` | Index the current replayable package. |

A component may read records from earlier stages. It should not silently edit
them. A corrected observation creates a new record with a new ID.

## 4. Common envelope

Every persisted record begins with:

```yaml
schema: execution-record
id: execution-vulnerable-001
case_id: case-001
provenance:
  created_at: 2026-09-22T00:00:00Z
  created_by: execution-harness
  method: bounded-docker-run
  inputs:
    - build-vulnerable-001
    - artifact-trigger-001
```

Field meanings:

- `schema` selects the record contract.
- `id` identifies this immutable record.
- `case_id` connects the record to its case.
- `provenance` identifies when, by whom, and optionally how the record was
  produced and which records it consumed.

`provenance.inputs` contains record IDs, not filesystem paths or raw data.

### 4.1 Failure taxonomy

Use the failure class that identifies the failed layer. Do not choose a class
based only on the final symptom.

| Failure class | Use when |
|---|---|
| `metadata_failure` | Source metadata is missing, conflicting, or normalized incorrectly. |
| `revision_failure` | Vulnerable or patched revisions cannot be resolved correctly. |
| `dependency_failure` | Dependencies cannot be acquired, pinned, or resolved. |
| `toolchain_failure` | Compiler, runtime, SDK, or build-tool requirements are not met. |
| `configuration_failure` | Required features, flags, services, or configuration are missing. |
| `build_failure` | Valid prerequisites exist, but compilation or linking fails. |
| `startup_failure` | A built target cannot start or initialize. |
| `harness_failure` | The harness cannot invoke or observe the target correctly. |
| `reachability_failure` | The candidate does not reach the relevant code or state. |
| `hypothesis_failure` | The proposed trigger condition or root-cause hypothesis is wrong. |
| `oracle_failure` | Available telemetry cannot support a reliable judgment. |
| `control_failure` | The patched build or negative control produces the target signal. |
| `resource_failure` | Time, memory, process, disk, or output limits prevent judgment. |

Classify the failure before retrying. Do not modify the trigger to repair an
environment failure, and do not rebuild a valid environment to repair a
reachability or hypothesis failure.

## 5. Sources and artifacts

### 5.1 `source-record`

Create one source record for each independently retrieved public source, such
as a vendor advisory, repository, fixing commit, issue, or CWE entry.

For successful retrieval:

- Set `retrieval_status` to `succeeded`.
- Store the exact response bytes as an artifact.
- Put that artifact reference in `content`.
- Record the actual retrieval time, not the advisory publication time.

For failed retrieval:

- Set `retrieval_status` to `failed`.
- Use `error` with the appropriate failure class and summary.
- Do not create fake content or treat an HTTP error page as advisory content.

`metadata` is for shallow retrieval metadata. It must not become an unbounded
replacement for normalized fields.

### 5.2 `artifact-record`

Create an artifact record after bytes have been written and hashed. Examples
include source snapshots, patches, binaries, triggers, logs, sanitizer output,
stack traces, coverage summaries, dependency inventories, and replay scripts.

For an available artifact, record:

- case-relative `path`;
- SHA-256 of the stored bytes;
- exact `size_bytes`;
- artifact `kind`;
- producer or derivation when applicable.

For an unavailable artifact, set `available: false` and provide
`unavailable_reason`. Do not invent an empty file, digest, or path.

Derived or redacted content must use a new artifact ID and list its parents in
`derived_from`. Raw artifacts remain unchanged.

## 6. Vulnerability normalization

### 6.1 `vulnerability-record`

This record combines normalized vulnerability identity, revision resolution,
patch context, and initial static context.

`revision_status` controls revision handling:

- `resolved`: both repository and vulnerable/patched revisions are required.
- `ambiguous`: retain competing information and add a `revision_failure`.
- `failed`: add a `revision_failure`; do not guess revisions.

### 6.2 Evidence-backed normalized claims

Every material normalized decision must have an entry in `claims`. Material
decisions include vulnerable and patched revisions, affected/fixed versions,
fixing commits, root cause, and expected signal.

Example:

```yaml
field: /revisions/vulnerable
raw_value: "versions before 2.4.1"
normalized_value: 0123456789abcdef0123456789abcdef01234567
source_id: source-vendor-advisory
classification: strong_inference
confidence: medium
evidence:
  - id: artifact-vendor-advisory
    sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
method: Resolved the last affected tag to its immutable commit.
```

Classifications mean:

- `confirmed_fact`: directly supported by authoritative or executable evidence.
- `strong_inference`: well supported but not directly stated or observed.
- `hypothesis`: plausible and awaiting verification.
- `unknown`: currently unresolved.

Confidence expresses evidence strength; it does not upgrade an inference into
a fact.

### 6.3 Patch and static context

Patch context may identify commits, diff artifacts, changed files, changed
functions, code locations, and nearby caller/callee relationships.

Reachability status means:

- `confirmed`: executable evidence reaches the relevant location or state.
- `inferred`: static context suggests a path, but execution has not confirmed it.
- `unknown`: current evidence cannot establish reachability.

Do not label heuristic call-graph output as confirmed. Confirmed and inferred
reachability must retain the artifact evidence used for the assessment.

## 7. Declared environment versus observed build

### 7.1 `environment-spec` is a declaration

The environment specification declares how both vulnerable and patched builds
should be produced. It is not proof of what was installed or executed.

Use one shared paired specification whenever possible. Place unavoidable
role-specific differences in `role_overrides`, with a reason. Do not duplicate
the whole environment merely to change a revision.

`isolation.type` must be `docker`, and `isolation.image_digest` must identify
the image by immutable SHA-256 digest. Image tags may be retained outside this
record for convenience, but they never replace the digest. Docker is the only
supported build and execution environment; a missing or inaccessible Docker
daemon is an environment failure, not permission to fall back to host, VM,
sandbox, Podman, or another runtime.

Resource limits must bound:

- elapsed time;
- memory;
- process count;
- disk use;
- captured output size.

Network settings are phase-specific. Build and execution network access should
normally be false. Acquisition access does not imply build or runtime access.
Dependency acquisition is the normal permitted network phase. Enabling runtime
network access requires explicit review before the specification is accepted;
until review metadata is supported, keep `network.execution` false.

Each instrumentation entry declares its availability:

- `required`: the case is invalid without it;
- `optional`: collect it when available;
- `unavailable`: intentionally not present in this environment;
- `incompatible`: known to conflict with the target or toolchain.

### 7.2 `build-record` is an observation

Create a separate build record for vulnerable, patched, and any control build.
Its revision and source-tree digest describe what was actually checked out.

A successful build must include:

- command results and raw stdout/stderr artifacts;
- at least one output artifact;
- observed tool names and versions;
- resolved dependency manager identity and version;
- dependency inventory and checksum-verification result.

A failed or invalid build uses `failure`. Repairs must be visible and classified
as environment-only, source-compatible, or semantics-changing. Never hide a
source modification inside a build command. A semantics-changing repair makes
the build invalid for direct vulnerable/patched comparison unless the change is
explicitly justified and reviewed.

The requested environment and observed build are intentionally separate. Do
not copy declared tool versions into `observed_toolchain` unless they were
actually measured.

## 8. Executions

Create one `execution-record` for every invocation. Repeated runs therefore
receive distinct IDs.

The comparison roles are:

- `vulnerable`: candidate input against the vulnerable build;
- `patched`: the same candidate input against the patched build;
- `negative_control`: a matched benign input or declared control condition.

All records in one paired comparison use the same `comparison_group`. The
vulnerable and patched runs must reference the same input artifact digest.

An execution record contains both the requested invocation and the observed
result:

- build and executable identity;
- input identity and input role;
- argument vector, working directory, and explicit environment;
- resource limits;
- start/end timestamps and terminal status;
- stdout and stderr artifacts, including empty output;
- exit code or signal when a process completed;
- optional sanitizer, stack, coverage, generated-output, and resource data.

Timeout and resource exhaustion are execution conditions, not vulnerability
signals. Startup and harness failures require their corresponding failure
classes. Record output truncation explicitly.

## 9. Verification

The verification component reads available evidence and exact IDs of executions
that actually occurred, and produces one `verification-result`. It must account
for all seven checks:

| Check key | Required question |
|---|---|
| `environment_and_build_identity` | Are environments valid and are vulnerable/patched revisions and outputs correct and distinct? |
| `same_candidate` | Did paired executions use the same candidate artifact digest? |
| `vulnerable_target_signal` | Did the expected target signal occur on the vulnerable build? |
| `reachability` | Is there relevant code-region or state evidence? |
| `patched_behavior` | Is the target signal absent or replaced by defined safe behavior on the patched build? |
| `negative_controls` | Did every required negative control avoid the target signal? |
| `patch_consistency` | Is the observed difference consistent with patch and root-cause evidence? |

The enclosing key identifies each check. Each value contains `status`,
`summary`, and `evidence`. Status is `passed`, `failed`, or `not_evaluated`.
Passed and failed checks require nonempty evidence and cannot have a skip
`reason`. A not-evaluated check requires a nonempty `reason` describing the
missing prerequisite; its evidence array may be empty if no observation exists.
Missing or truncated telemetry is not evidence that a signal was absent.

The overall evidence list must be nonempty, including for early failures.
Omit `executions` if none occurred; otherwise include only actual execution
references. Empty role maps and empty control lists are invalid: omit absent
roles. `VERIFIED` still requires vulnerable, patched, and negative-control IDs.

Every result requires `oracle.name`, `oracle.version`, `oracle.adapter.name`,
`oracle.adapter.version`, `oracle.adapter.implementation`, and
`oracle.case_definition`. The last two fields are artifact references with IDs
and SHA-256 hashes. They identify the reviewed adapter implementation and case
definition, including expectations and intervention records. Names or prose
alone do not identify the executable assertions. These fields describe the
contract; the adapter and oracle runtime are not implemented yet.

Verdict selection (implemented later in the independent oracle):

- `VERIFIED`: all seven checks pass.
- `NOT_REPRODUCED`: the environment is valid and adequate observations establish
  that the target signal or target reachability is absent.
- `INCONCLUSIVE`: evidence is missing, conflicting, or controls fail in a way
  that prevents attribution.
- `INVALID_ENVIRONMENT`: build, startup, harness, toolchain, or environment
  validity prevents a reproduction judgment.

Every non-`VERIFIED` result requires a failure class. Never upgrade
`INCONCLUSIVE` or `INVALID_ENVIRONMENT` for reporting convenience.
All seven passed checks require `VERIFIED`; a non-success result cannot contain
only passed checks. Other detailed verdict/check relationships and competing
failure precedence require semantic validation, not just JSON Schema. See the
[verification contract](verification-contract.md#check-states-and-verdict-precedence).

## 10. Packaging and replay

`case-manifest` is the root index for the current package state. It references
records and artifacts; it does not duplicate them.

`draft` and `buildable` manifests may be incomplete. `replayable` and `verified`
manifests must include:

- vulnerability and source records;
- paired environment;
- vulnerable and patched builds;
- complete artifact inventory;
- vulnerable, patched, and negative-control executions;
- verification result;
- replay entry-point artifact, command, and working directory.

The other final statuses require a verification-result ID and nonempty artifact
inventory. Preserve all available records, but do not invent missing builds,
executions, or replay artifacts. Partial nonempty role maps are allowed. Replay
information is optional for these non-success packages.

An optional manifest `failure` contains `stage`, `class`, `summary`, and a
nonempty diagnostic `evidence` list. `stage` uses the pipeline vocabulary
(`collect`, `normalize`, `resolve`, `build`, `extract`, `execute`, `verify`,
`report`); for example, Docker preflight for building uses `build`. Register the
diagnostics in `artifact_ids`. A `verified` manifest cannot carry a current
failure. Historical failures remain separate immutable records and artifacts.

Before case expectations are available, keep a draft with failure diagnostics.
For a prepared case where Docker is unavailable, emit `INVALID_ENVIRONMENT`
with the observed diagnostic: fail the environment check and mark downstream
checks not evaluated. Do not create build records for commands that never ran.

Manifest status must agree with the referenced verification verdict:

| Verification verdict | Manifest status |
|---|---|
| `VERIFIED` | `verified` |
| `NOT_REPRODUCED` | `not_reproduced` |
| `INCONCLUSIVE` | `inconclusive` |
| `INVALID_ENVIRONMENT` | `invalid_environment` |

A `replayable` package means it can run in its declared Docker container; it
does not mean the vulnerability was verified.

## 11. Validation workflow

The [package foundation](package-foundation.md) now implements offline schema,
artifact-integrity, and cross-record checks for the current schema set. It does not
replace the independent CVE oracle.

Before returning any record:

1. Select the schema matching the record's `schema` field.
2. Validate through the complete offline schema registry so `$ref` resolution
   never uses the network.
3. Correct structural validation errors without fabricating values.
4. Confirm every referenced artifact is registered and its digest matches.
5. Confirm all record references use the same case unless explicitly shared.
6. Confirm vulnerable, patched, and control identities have not been conflated.
7. Return the record together with unresolved uncertainties or failure status.

If a required field cannot be populated truthfully, stop that stage and emit a
classified failure. Do not weaken or bypass validation silently.

## 12. Guidance for future agent prompts

Do not paste the entire schema family into every system prompt. Give an agent:

1. its bounded stage responsibility;
2. the relevant section of this guide;
3. only the schemas it reads and produces;
4. one matching valid example;
5. access to offline schema validation.

All agent prompts should repeat these non-negotiable rules:

```text
Never invent missing evidence.
Preserve raw evidence as immutable artifacts.
Keep facts, inferences, hypotheses, and unknowns distinct.
Keep vulnerable, patched, and control roles distinct.
Execute only in project-controlled Docker containers; never target public systems.
Keep runtime network access disabled unless explicitly reviewed.
A crash alone is not verification.
Emit VERIFIED only when all seven checks pass with evidence.
Validate every produced record before returning it.
```

The schemas constrain output. This guide constrains behavior. Executable
evidence—not schema validity or an agent's explanation—supports the final
research claim.
