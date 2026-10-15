"""Package integrity and record consistency. Does not interpret CVE signals."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from pathlib import Path
from typing import Sequence

from . import __version__
from .contracts import Diagnostic, Record, SchemaCatalog, canonical_json, utc_now
from .references import references
from .storage import DEFAULT_MAX_ARTIFACT_BYTES, StorageError, measure, open_case_file, relative_parts


@dataclass(frozen=True)
class ValidationReport:
    manifest_id: str
    checked_at: str
    diagnostics: tuple[Diagnostic, ...]
    record_hashes: dict[str, str]

    @property
    def valid(self) -> bool:
        return not self.diagnostics

    def to_dict(self) -> dict:
        return {
            "validator": {"name": "dacn-package-validator", "version": __version__},
            "manifest_id": self.manifest_id, "checked_at": self.checked_at,
            "valid": self.valid, "diagnostics": [item.to_dict() for item in self.diagnostics],
            "canonical_record_sha256": self.record_hashes,
        }


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))


class PackageValidator:
    """Validate an explicit current-case record set against a selected manifest.

    Schema-valid input is required before cross-record traversal. All referenced
    records must be supplied; no implicit host/global/network lookup is allowed.
    """

    def __init__(self, catalog: SchemaCatalog, *, max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
                 max_records: int = 10000):
        if max_artifact_bytes < 0 or max_records < 1:
            raise ValueError("invalid package validation limits")
        self.catalog = catalog
        self.max_artifact_bytes = max_artifact_bytes
        self.max_records = max_records

    def validate(self, root: Path, manifest_id: str, records: Sequence[Record]) -> ValidationReport:
        issues: list[Diagnostic] = []
        indexed: dict[str, Record] = {}
        hashes = {}

        def issue(code, failure_class, message, record=None, path=""):
            issues.append(Diagnostic(code, failure_class, message,
                                     record.get("id") if record else None, path))

        def report():
            return ValidationReport(manifest_id, utc_now(), tuple(issues), hashes)

        if len(records) > self.max_records:
            issue("record_count_limit", "resource_failure", "Package exceeds the record count limit.")
            return report()
        for record in records:
            diagnostics = self.catalog.validate(record)
            issues.extend(diagnostics)
            if diagnostics:
                continue
            if record["id"] in indexed:
                issue("duplicate_record_id", "metadata_failure", "Record IDs must be unique.", record)
            else:
                indexed[record["id"]] = record
                hashes[record["id"]] = hashlib.sha256(canonical_json(record)).hexdigest()
        manifest = indexed.get(manifest_id)
        if not manifest or manifest["schema"] != "case-manifest":
            issue("missing_manifest", "metadata_failure", "Selected manifest does not exist or has the wrong type.")
        if issues:
            return report()

        root = Path(root).absolute()
        case_id = manifest["case_id"]
        inventory = set(manifest.get("artifact_ids", []))
        for record in indexed.values():
            if record["case_id"] != case_id:
                issue("case_mismatch", "metadata_failure", "Record belongs to a different case.", record, "/case_id")
            for ref in references(record):
                target = indexed.get(ref.identifier)
                if target is None:
                    issue("missing_reference", "metadata_failure", f"Referenced record is absent: {ref.identifier}.", record, ref.path)
                elif ref.schema and target["schema"] != ref.schema:
                    issue("reference_type_mismatch", "metadata_failure", f"Reference requires {ref.schema}.", record, ref.path)
                elif ref.sha256 is not None:
                    if not target["available"]:
                        issue("unavailable_evidence", "oracle_failure", "Referenced evidence is unavailable.", record, ref.path)
                    elif ref.sha256 != target["sha256"]:
                        issue("reference_hash_mismatch", "metadata_failure", "Reference digest disagrees with the artifact record.", record, ref.path)
            if record["schema"] == "artifact-record":
                if record["id"] not in inventory:
                    issue("artifact_not_indexed", "metadata_failure", "Artifact is missing from the manifest inventory.", record)
                if record["available"]:
                    self._artifact(root, record, issue)
            elif record["schema"] == "source-record" and record["id"] not in manifest.get("source_ids", []):
                issue("source_not_indexed", "metadata_failure", "Source is missing from the manifest inventory.", record)
            if "started_at" in record:
                if _time(record["completed_at"]) < _time(record["started_at"]):
                    issue("reversed_time", "metadata_failure", "Completion precedes start.", record, "/completed_at")
            if record["schema"] in ("execution-record", "environment-spec", "case-manifest"):
                self._paths(record, issue)

        # Bad references and integrity failures are already explicit. Do not
        # dereference them or trust them for relational checks.
        if issues:
            return report()

        vulnerability = indexed.get(manifest.get("vulnerability_id"))
        environment = indexed.get(manifest.get("environment_id"))
        builds = {role: indexed[identifier] for role, identifier in manifest.get("builds", {}).items()}
        executions = manifest.get("executions", {})
        verification = indexed.get(manifest.get("verification_result_id"))

        if vulnerability and vulnerability["revision_status"] == "resolved":
            revisions = vulnerability["revisions"]
            if revisions["vulnerable"] == revisions["patched"]:
                issue("same_revision", "revision_failure", "Vulnerable and patched revisions are identical.", vulnerability)
        for record in indexed.values():
            if record["schema"] == "environment-spec":
                if record["network"]["build"] or record["network"]["execution"]:
                    issue("network_enabled", "configuration_failure", "This baseline requires offline builds and execution.", record, "/network")
                if record.get("role_overrides"):
                    issue("unsupported_overrides", "configuration_failure", "Role overrides require a future explicit comparison policy.", record, "/role_overrides")
            elif record["schema"] == "build-record":
                if record["status"] == "succeeded" and any(command["exit_code"] != 0 for command in record["commands"]):
                    issue("build_status_mismatch", "build_failure", "Successful build contains a failed command.", record)
                if record["status"] != "invalid" and any(repair["classification"] == "semantics_changing" for repair in record.get("repairs", [])):
                    issue("semantics_changed", "build_failure", "Semantics-changing repairs require invalid build status in this baseline.", record)
            elif record["schema"] == "execution-record":
                self._execution(record, indexed, issue)

        for role, build in builds.items():
            if build["role"] != role:
                issue("build_role_mismatch", "revision_failure", "Manifest build role disagrees with the build record.", build, "/role")
            if not environment or build["environment_id"] != environment["id"]:
                issue("build_environment_mismatch", "configuration_failure", "Selected build does not use the declared paired environment.", build)
            if not vulnerability or vulnerability["revision_status"] != "resolved":
                issue("unresolved_build_revision", "revision_failure", "A selected build needs resolved vulnerability revisions.", build)
            elif build["revision"] != vulnerability["revisions"][role]:
                issue("build_revision_mismatch", "revision_failure", "Build revision disagrees with the vulnerability record.", build, "/revision")
        if set(builds) == {"vulnerable", "patched"}:
            left, right = builds["vulnerable"], builds["patched"]
            for key, code in (("id", "same_build"), ("source_tree_sha256", "same_source_tree")):
                if left[key] == right[key]:
                    issue(code, "revision_failure", "Paired builds must have distinct identities and source trees.", manifest, "/builds")
            if left["status"] == right["status"] == "succeeded":
                if {ref["sha256"] for ref in left["outputs"]} == {ref["sha256"] for ref in right["outputs"]}:
                    issue("same_build_outputs", "revision_failure", "Paired builds have identical output digest sets.", manifest, "/builds")
                if left["observed_toolchain"] != right["observed_toolchain"]:
                    issue("toolchain_mismatch", "toolchain_failure", "Observed paired toolchains differ.", manifest, "/builds")
                if left["dependency_resolution"] != right["dependency_resolution"]:
                    # Artifact IDs may differ while referring to the same inventory bytes.
                    ldep, rdep = dict(left["dependency_resolution"]), dict(right["dependency_resolution"])
                    ldep["inventory"] = ldep["inventory"]["sha256"]
                    rdep["inventory"] = rdep["inventory"]["sha256"]
                    if ldep != rdep:
                        issue("dependency_mismatch", "dependency_failure", "Observed paired dependency resolutions differ.", manifest, "/builds")

        self._comparison(executions, builds, indexed, manifest, issue)
        if verification:
            if verification.get("executions", {}) != executions:
                issue("verification_execution_mismatch", "oracle_failure", "Manifest and verifier select different executions.", manifest, "/executions")
            expected_status = verification["verdict"].lower()
            if manifest["status"] not in ("draft", "buildable", "replayable") and manifest["status"] != expected_status:
                issue("verdict_mismatch", "oracle_failure", "Manifest status disagrees with the verification verdict.", manifest, "/status")
            for role, identifiers in executions.items():
                for identifier in identifiers if isinstance(identifiers, list) else [identifiers]:
                    if _time(verification["provenance"]["created_at"]) < _time(indexed[identifier]["completed_at"]):
                        issue("verification_before_execution", "oracle_failure", "Verification predates an execution it consumes.", verification)
            self._check_prerequisites(verification, executions, builds, indexed, issue)
        return report()

    def _artifact(self, root, record, issue):
        try:
            with open_case_file(root, record["path"]) as stream:
                before = os.fstat(stream.fileno())
                digest, size = measure(stream, self.max_artifact_bytes)
                after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                issue("artifact_changed", "metadata_failure", "Artifact changed during validation.", record, "/path")
            if digest != record["sha256"]:
                issue("artifact_hash_mismatch", "metadata_failure", "Stored bytes disagree with the recorded SHA-256.", record, "/sha256")
            if size != record["size_bytes"]:
                issue("artifact_size_mismatch", "metadata_failure", "Stored bytes disagree with the recorded size.", record, "/size_bytes")
        except StorageError as error:
            issue(error.code, error.failure_class, str(error), record, "/path")
        except OSError:
            issue("artifact_unreadable", "metadata_failure", "Artifact is missing, unsafe, or unreadable.", record, "/path")

    @staticmethod
    def _paths(record, issue):
        paths = []
        if record["schema"] == "execution-record":
            paths = [("/working_directory", record["working_directory"])]
        elif record["schema"] == "case-manifest" and "replay" in record:
            paths = [("/replay/working_directory", record["replay"]["working_directory"])]
        elif record["schema"] == "environment-spec":
            paths = [("/build/expected_outputs", path) for path in record["build"].get("expected_outputs", [])]
        for location, path in paths:
            if path == "." and location.endswith("working_directory"):
                continue
            try:
                relative_parts(path)
            except StorageError as error:
                issue(error.code, error.failure_class, str(error), record, location)

    @staticmethod
    def _execution(run, indexed, issue):
        build = indexed[run["build_id"]]
        environment = indexed[build["environment_id"]]
        if build["status"] != "succeeded":
            issue("execution_build_invalid", "build_failure", "Execution references a build that did not succeed.", run, "/build_id")
        if run["executable"] not in build.get("outputs", []):
            issue("executable_not_build_output", "harness_failure", "Executable is not an output of its declared build.", run, "/executable")
        if _time(run["started_at"]) < _time(build["completed_at"]):
            issue("execution_before_build", "harness_failure", "Execution starts before its build completes.", run)
        expected_input = "benign_control" if run["role"] == "negative_control" else "candidate"
        if run["input_role"] != expected_input:
            issue("input_role_mismatch", "harness_failure", "Input role disagrees with execution role.", run, "/input_role")
        if run["role"] != "negative_control" and run["role"] != build["role"]:
            issue("execution_role_mismatch", "harness_failure", "Execution and build roles disagree.", run, "/role")
        if any(run["limits"][key] > value for key, value in environment["limits"].items()):
            issue("limits_exceeded", "resource_failure", "Execution limits exceed the environment ceilings.", run, "/limits")

    @staticmethod
    def _comparison(executions, builds, indexed, manifest, issue):
        paired = {role: indexed[executions[role]] for role in ("vulnerable", "patched") if role in executions}
        for role, run in paired.items():
            if run["role"] != role or role not in builds or run["build_id"] != builds[role]["id"]:
                issue("selected_execution_mismatch", "harness_failure", "Selected execution does not match its manifest build and role.", run)
        if len(paired) == 2:
            left, right = paired["vulnerable"], paired["patched"]
            if left["id"] == right["id"]:
                issue("same_execution", "harness_failure", "Paired roles reference the same invocation.", manifest)
            if left["input"]["sha256"] != right["input"]["sha256"]:
                issue("candidate_mismatch", "harness_failure", "Paired runs did not use identical candidate bytes.", manifest)
            if left["executable"]["sha256"] == right["executable"]["sha256"]:
                issue("same_executable", "revision_failure", "Paired runs execute identical binaries.", manifest)
            for key in ("comparison_group", "limits", "environment", "working_directory"):
                if left[key] != right[key]:
                    issue("comparison_mismatch", "harness_failure", f"Paired runs differ in {key}.", manifest)
        for identifier in executions.get("negative_controls", []):
            control = indexed[identifier]
            matched = next((run for run in paired.values() if run["build_id"] == control["build_id"]), None)
            if control["role"] != "negative_control" or not matched:
                issue("control_build_mismatch", "control_failure", "Benign control must use a selected paired build and control role.", control)
                continue
            if control["input"]["sha256"] == matched["input"]["sha256"]:
                issue("control_input_matches_candidate", "control_failure", "Benign control bytes equal the candidate bytes.", control)
            for key in ("comparison_group", "limits", "environment", "working_directory", "executable"):
                if control[key] != matched[key]:
                    issue("control_comparison_mismatch", "control_failure", f"Control differs from its matched run in {key}.", control)

    @staticmethod
    def _check_prerequisites(result, executions, builds, indexed, issue):
        # Only prerequisites observable from records are checked here. Signal
        # interpretation and evidence-based verdict derivation belong to the oracle.
        checks = result["checks"]
        runs = {role: indexed[executions[role]] for role in ("vulnerable", "patched") if role in executions}
        if checks["environment_and_build_identity"]["status"] == "passed":
            if len(builds) != 2 or any(build["status"] != "succeeded" for build in builds.values()):
                issue("check_prerequisite_missing", "oracle_failure", "Environment check passed without two successful builds.", result)
        prerequisites = {
            "same_candidate": len(runs) == 2,
            "vulnerable_target_signal": "vulnerable" in runs,
            "reachability": "vulnerable" in runs,
            "patched_behavior": "patched" in runs,
            "negative_controls": bool(executions.get("negative_controls")),
            "patch_consistency": len(runs) == 2,
        }
        for name, present in prerequisites.items():
            if checks[name]["status"] != "not_evaluated" and not present:
                issue("check_prerequisite_missing", "oracle_failure", f"Check {name} has no required execution observations.", result, f"/checks/{name}")
        if result["verdict"] == "VERIFIED":
            identifiers = list(runs.values()) + [indexed[key] for key in executions.get("negative_controls", [])]
            if any(run["status"] != "completed" or run.get("output_truncated", False) for run in identifiers):
                issue("incomplete_verified_execution", "oracle_failure", "This baseline cannot verify incomplete or truncated executions.", result)
            if not set(build["id"] for build in builds.values()).issubset({run["build_id"] for run in identifiers if run["role"] == "negative_control"}):
                issue("control_coverage_missing", "control_failure", "Milestone verification requires benign controls on both paired builds.", result)
