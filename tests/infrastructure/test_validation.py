from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from dacn.contracts import SchemaCatalog, canonical_json
from dacn.storage import CaseStore
from dacn.validation import PackageValidator
from .fixtures import complete_case, early_failure


ROOT = Path(__file__).resolve().parents[2]


class PackageValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = SchemaCatalog(ROOT / "schemas")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.records, self.manifest_id = complete_case(self.root, self.catalog)
        self.validator = PackageValidator(self.catalog)

    def record(self, identifier, records=None):
        return next(record for record in (self.records if records is None else records) if record["id"] == identifier)

    def report(self, records=None):
        return self.validator.validate(self.root, self.manifest_id, self.records if records is None else records)

    def assert_code(self, code, records=None):
        report = self.report(records)
        self.assertFalse(report.valid)
        self.assertIn(code, [item.code for item in report.diagnostics], report.to_dict())
        return report

    def test_complete_package_validates_without_mutating_any_input(self):
        original = deepcopy(self.records)
        report = self.report()
        self.assertTrue(report.valid, report.to_dict())
        self.assertEqual(original, self.records)
        self.assertEqual(set(record["id"] for record in self.records), set(report.record_hashes))
        self.assertNotIn("verdict", report.to_dict())
        self.assertIsInstance(json.loads(canonical_json(report.to_dict())), dict)

    def test_docker_failure_package_validates_without_builds_or_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            records, manifest = early_failure(Path(directory), self.catalog)
            report = self.validator.validate(Path(directory), manifest, records)
            self.assertTrue(report.valid, report.to_dict())
            self.assertFalse(any(record["schema"] in ("build-record", "execution-record") for record in records))

    def test_draft_can_be_empty_and_does_not_become_verified(self):
        manifest = self.record(self.manifest_id)
        record = {key: manifest[key] for key in ("schema", "id", "case_id", "package_version")}
        record.update(status="draft", provenance={"created_at": "2026-10-04T00:10:00Z", "created_by": "fixture"})
        self.assertTrue(self.report([record]).valid)

    def test_missing_reference_wrong_type_and_cross_case(self):
        for change, code in (("missing", "missing_reference"), ("wrong_type", "reference_type_mismatch"), ("case", "case_mismatch")):
            records = deepcopy(self.records)
            run = self.record("execution-vulnerable", records)
            if change == "missing":
                run["build_id"] = "not-present"
            elif change == "wrong_type":
                run["build_id"] = "source-advisory"
            else:
                run["case_id"] = "another-case"
            with self.subTest(change=change):
                self.assert_code(code, records)

    def test_duplicate_id_and_structural_errors_stop_before_artifact_reads(self):
        records = [*self.records, deepcopy(self.records[0])]
        self.assert_code("duplicate_record_id", records)
        records = deepcopy(self.records)
        self.record("execution-vulnerable", records)["limits"] = None
        self.assert_code("schema_invalid", records)

    def test_schema_version_field_is_rejected(self):
        self.record("source-advisory")["schema_version"] = "0.2.0"
        self.assert_code("schema_invalid")

    def test_hash_corruption_size_mismatch_and_missing_bytes(self):
        artifact = self.record("artifact-trigger")
        path = self.root / artifact["path"]
        path.chmod(0o600)
        path.write_bytes(b"tampered")
        report = self.assert_code("artifact_hash_mismatch")
        self.assertIn("artifact_size_mismatch", {item.code for item in report.diagnostics})
        path.unlink()
        self.assert_code("artifact_unreadable")

    def test_reference_digest_and_inventory_must_match(self):
        records = deepcopy(self.records)
        self.record("execution-vulnerable", records)["input"]["sha256"] = "f" * 64
        self.assert_code("reference_hash_mismatch", records)
        self.record(self.manifest_id)["artifact_ids"].remove("artifact-trigger")
        self.assert_code("artifact_not_indexed")

    def test_source_inventory_and_undeclared_manifest_fields(self):
        records = deepcopy(self.records)
        self.record(self.manifest_id, records)["source_ids"] = ["source-not-present"]
        self.assert_code("source_not_indexed", records)
        self.record(self.manifest_id)["schema_versions"] = {"source-record": "0.1.0"}
        self.assert_code("schema_invalid")

    def test_available_reference_cannot_point_to_unavailable_artifact(self):
        artifact = self.record("artifact-trigger")
        for key in ("path", "sha256", "size_bytes"):
            del artifact[key]
        artifact.update(available=False, unavailable_reason="Fixture file was lost.")
        self.assert_code("unavailable_evidence")

    def test_oversized_artifact_is_bounded_and_classified(self):
        report = PackageValidator(self.catalog, max_artifact_bytes=2).validate(self.root, self.manifest_id, self.records)
        self.assertFalse(report.valid)
        self.assertTrue(any(item.code == "size_limit" and item.failure_class == "resource_failure" for item in report.diagnostics))

    def test_unsafe_and_symlinked_artifact_paths_are_rejected(self):
        artifact = self.record("artifact-trigger")
        (self.root / "link").symlink_to(self.root / artifact["path"])
        artifact["path"] = "link"
        self.assert_code("artifact_unreadable")
        artifact["path"] = "C:/outside"
        self.assert_code("unsafe_path")

    def test_claim_raw_values_and_source_metadata_are_not_interpreted_as_references(self):
        self.record("vulnerability-001")["claims"][0]["raw_value"] = {"id": "not-a-reference", "sha256": "0" * 64}
        self.record("source-advisory")["metadata"] = {"id": "raw-server-id", "sha256": "f" * 64}
        self.assertTrue(self.report().valid, self.report().to_dict())

    def test_same_revisions_source_trees_builds_and_binaries_rejected(self):
        for kind, code in (("revision", "same_revision"), ("tree", "same_source_tree"),
                           ("build", "same_build"), ("binary", "same_executable")):
            records = deepcopy(self.records)
            if kind == "revision":
                self.record("vulnerability-001", records)["revisions"]["patched"] = "a" * 40
            elif kind == "tree":
                self.record("build-patched", records)["source_tree_sha256"] = "2" * 64
            elif kind == "build":
                self.record(self.manifest_id, records)["builds"]["patched"] = "build-vulnerable"
            else:
                output = deepcopy(self.record("build-vulnerable", records)["outputs"])
                self.record("build-patched", records)["outputs"] = output
                for run_id in ("execution-patched", "execution-control-patched"):
                    self.record(run_id, records)["executable"] = deepcopy(output[0])
            with self.subTest(kind=kind):
                self.assert_code(code, records)

    def test_build_revision_role_and_environment_must_match_manifest(self):
        for field, value, code in (("revision", "wrong-revision", "build_revision_mismatch"),
                                   ("role", "control", "build_role_mismatch")):
            records = deepcopy(self.records)
            self.record("build-patched", records)[field] = value
            with self.subTest(field=field):
                self.assert_code(code, records)
        records = deepcopy(self.records)
        other = deepcopy(self.record("environment-paired", records))
        other["id"] = "environment-other"
        records.append(other)
        self.record("build-patched", records)["environment_id"] = other["id"]
        self.assert_code("build_environment_mismatch", records)

    def test_selected_run_and_executable_must_match_build(self):
        self.record("execution-patched")["build_id"] = "build-vulnerable"
        report = self.assert_code("selected_execution_mismatch")
        self.assertIn("executable_not_build_output", {item.code for item in report.diagnostics})

    def test_candidate_and_control_inputs_must_be_distinct_as_declared(self):
        records = deepcopy(self.records)
        self.record("execution-patched", records)["input"] = deepcopy(self.record("execution-control", records)["input"])
        self.assert_code("candidate_mismatch", records)
        self.record("execution-control")["input"] = deepcopy(self.record("execution-vulnerable")["input"])
        self.assert_code("control_input_matches_candidate")

    def test_comparison_group_limits_and_environments_are_matched(self):
        for key, value in (("comparison_group", "other"), ("environment", {"MODE": "different"}),
                           ("limits", {**self.record("execution-patched")["limits"], "memory_mb": 128})):
            records = deepcopy(self.records)
            self.record("execution-patched", records)[key] = value
            with self.subTest(key=key):
                self.assert_code("comparison_mismatch", records)

    def test_execution_limit_above_environment_ceiling_rejected(self):
        self.record("execution-vulnerable")["limits"]["memory_mb"] = 100000
        self.assert_code("limits_exceeded")

    def test_control_requires_correct_role_and_selected_build(self):
        self.record("execution-control")["role"] = "vulnerable"
        report = self.assert_code("control_build_mismatch")
        self.assertIn("input_role_mismatch", {item.code for item in report.diagnostics})

    def test_verified_requires_controls_on_both_builds(self):
        for identifier in (self.manifest_id, "verification-001"):
            self.record(identifier)["executions"]["negative_controls"] = ["execution-control"]
        self.assert_code("control_coverage_missing")

    def test_manifest_verdict_and_execution_selection_must_agree(self):
        self.record(self.manifest_id)["status"] = "inconclusive"
        self.assert_code("verdict_mismatch")
        self.record(self.manifest_id)["status"] = "verified"
        self.record("verification-001")["executions"]["negative_controls"] = ["execution-control"]
        self.assert_code("verification_execution_mismatch")

    def test_timing_is_checked_with_offsets_not_lexicographic_order(self):
        self.record("execution-vulnerable")["started_at"] = "2026-09-17T07:03:00+07:00"
        self.assertTrue(self.report().valid, self.report().to_dict())
        self.record("execution-vulnerable")["started_at"] = "2026-09-17T00:00:00Z"
        self.assert_code("execution_before_build")
        self.record("build-vulnerable")["completed_at"] = "2026-09-16T00:00:00Z"
        self.assert_code("reversed_time")

    def test_verification_cannot_predate_its_observations(self):
        self.record("verification-001")["provenance"]["created_at"] = "2026-09-01T00:00:00Z"
        self.assert_code("verification_before_execution")

    def test_failed_build_and_semantics_changing_repair_are_not_success(self):
        self.record("build-vulnerable")["commands"][0]["exit_code"] = 2
        self.assert_code("build_status_mismatch")
        self.record("build-vulnerable")["repairs"] = [{"classification": "semantics_changing", "description": "Altered parser."}]
        self.assert_code("semantics_changed")

    def test_observed_toolchain_and_dependency_drift_are_reported(self):
        self.record("build-patched")["observed_toolchain"]["compiler"] = "different compiler"
        self.assert_code("toolchain_mismatch")
        self.record("build-patched")["dependency_resolution"]["manager_version"] = "different version"
        self.assert_code("dependency_mismatch")

    def test_network_or_unsupported_overrides_fail_explicitly(self):
        self.record("environment-paired")["network"]["execution"] = True
        self.assert_code("network_enabled")
        self.record("environment-paired")["role_overrides"] = {"patched": {"reason": "Fixture difference", "values": {"flags": ["-O2"]}}}
        self.assert_code("unsupported_overrides")

    def test_timeout_and_truncation_cannot_support_verified(self):
        self.record("execution-vulnerable")["output_truncated"] = True
        self.assert_code("incomplete_verified_execution")
        run = self.record("execution-vulnerable")
        run.update(status="timed_out", failure={"class": "resource_failure", "summary": "Fixture timeout."})
        self.assert_code("incomplete_verified_execution")

    def test_check_cannot_claim_execution_observations_before_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            records, manifest = early_failure(Path(directory), self.catalog)
            result = next(record for record in records if record["schema"] == "verification-result")
            result["checks"]["reachability"] = {
                "status": "failed", "summary": "False claim of an observation.", "evidence": result["evidence"],
            }
            report = self.validator.validate(Path(directory), manifest, records)
            self.assertIn("check_prerequisite_missing", {item.code for item in report.diagnostics})

    def test_real_bytes_do_not_turn_validation_into_an_oracle(self):
        # An opaque synthetic observation can be intact without proving its claim.
        self.record("verification-001")["rationale"] = "This text is not executable proof."
        self.assertTrue(self.report().valid)


class PackageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = SchemaCatalog(ROOT / "schemas")

    def test_store_load_validate_and_cli_then_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records, manifest_id = complete_case(root, self.catalog, persist=True)
            loaded = CaseStore(root, self.catalog).load_records()
            report = PackageValidator(self.catalog).validate(root, manifest_id, loaded)
            self.assertTrue(report.valid, report.to_dict())
            command = [sys.executable, "-m", "dacn", "validate", "--root", str(root),
                       "--schemas", str(ROOT / "schemas"), "--manifest-id", manifest_id]
            result = subprocess.run(command, capture_output=True, cwd=ROOT, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr.decode())
            self.assertTrue(json.loads(result.stdout)["valid"])
            artifact = next(record for record in records if record["id"] == "artifact-trigger")
            path = root / artifact["path"]
            path.chmod(0o600)
            path.write_bytes(b"corrupt")
            result = subprocess.run(command, capture_output=True, cwd=ROOT, timeout=30)
            self.assertEqual(1, result.returncode)
            report = json.loads(result.stdout)
            self.assertFalse(report["valid"])
            self.assertIn("artifact_hash_mismatch", {item["code"] for item in report["diagnostics"]})

    def test_cli_missing_package_is_explicit_and_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "absent"
            result = subprocess.run([
                sys.executable, "-m", "dacn", "validate", "--root", str(root),
                "--schemas", str(ROOT / "schemas"), "--manifest-id", "missing",
            ], capture_output=True, cwd=ROOT, timeout=30)
            self.assertEqual(2, result.returncode)
            self.assertFalse(json.loads(result.stdout)["valid"])
            self.assertFalse(root.exists())

    def test_early_failure_survives_storage_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, manifest = early_failure(root, self.catalog, persist=True)
            store = CaseStore(root, self.catalog)
            records = store.load_records()
            result = PackageValidator(self.catalog).validate(root, manifest, records)
            self.assertTrue(result.valid, result.to_dict())
            # Persist the report through the same immutable artifact interface.
            report_artifact = store.put_bytes(
                canonical_json(result.to_dict()), identifier="artifact-validation-report",
                case_id="case-001", kind="validation_report",
                provenance={"created_at": result.checked_at, "created_by": "dacn-package-validator", "inputs": [manifest]},
            )
            self.assertEqual(result.to_dict(), json.loads((root / report_artifact.path).read_bytes()))
