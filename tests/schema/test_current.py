import unittest
from copy import deepcopy

from jsonschema import Draft202012Validator, FormatChecker

from .fixtures import invalid_fixtures
from .fixtures_current import (
    CHECK_KEYS, VALID, check, docker_unavailable, non_success, partial_manifest,
)
from .test_schemas import PERSISTED, load_registry


class CurrentSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas, cls.by_name, cls.registry = load_registry()

    def validator(self, name):
        return Draft202012Validator(
            self.by_name[name], registry=self.registry, format_checker=FormatChecker(),
        )

    def assert_valid(self, name, value):
        errors = list(self.validator(name).iter_errors(value))
        self.assertEqual([], errors, "\n".join(str(error) for error in errors))

    def assert_invalid(self, name, value):
        self.assertFalse(self.validator(name).is_valid(value))

    def test_inventory_dialect_and_offline_references(self):
        self.assertEqual(PERSISTED | {"common"}, set(self.by_name))
        self.assertEqual(PERSISTED, set(VALID))
        for name, schema in self.by_name.items():
            with self.subTest(schema=name):
                self.assertEqual(f"urn:dacn:schema:{name}", schema["$id"])
                Draft202012Validator.check_schema(schema)
                pending = [schema]
                while pending:
                    node = pending.pop()
                    if isinstance(node, dict):
                        if "$ref" in node:
                            self.registry.resolver(base_uri=schema["$id"]).lookup(node["$ref"])
                        pending.extend(node.values())
                    elif isinstance(node, list):
                        pending.extend(node)

    def test_valid_fixture_for_every_record(self):
        for name, record in VALID.items():
            with self.subTest(schema=name):
                self.assert_valid(name, record)

    def test_invalid_records_remain_invalid(self):
        for name, value in invalid_fixtures().items():
            with self.subTest(schema=name):
                self.assert_invalid(name, value)

    def test_docker_unavailable_needs_no_fabricated_executions(self):
        value = docker_unavailable()
        self.assertNotIn("executions", value)
        self.assert_valid("verification-result", value)
        self.assert_valid("case-manifest", partial_manifest("invalid_environment"))

    def test_partial_build_and_execution_references(self):
        value = partial_manifest("invalid_environment")
        value["builds"] = {"vulnerable": "build-failed"}
        self.assert_valid("case-manifest", value)
        value["executions"] = {"vulnerable": "execution-startup-failed"}
        self.assert_valid("case-manifest", value)
        result = docker_unavailable()
        result["executions"] = {"vulnerable": "execution-startup-failed"}
        self.assert_valid("verification-result", result)

    def test_non_success_outcomes(self):
        cases = [
            non_success("NOT_REPRODUCED", "vulnerable_target_signal", "hypothesis_failure"),
            non_success("INCONCLUSIVE", "negative_controls", "control_failure"),
            docker_unavailable(),
        ]
        for value in cases:
            with self.subTest(verdict=value["verdict"]):
                self.assert_valid("verification-result", value)
                self.assert_valid("case-manifest", partial_manifest(value["verdict"].lower()))
                del value["failure_class"]
                self.assert_invalid("verification-result", value)

    def test_draft_failure_does_not_require_verdict(self):
        self.assert_valid("case-manifest", partial_manifest())
        value = partial_manifest()
        del value["failure"]
        del value["artifact_ids"]
        self.assert_valid("case-manifest", value)

    def test_failure_requires_stage_class_summary_and_diagnostics(self):
        for key in ("stage", "class", "summary", "evidence"):
            value = partial_manifest()
            del value["failure"][key]
            with self.subTest(missing=key):
                self.assert_invalid("case-manifest", value)
        for key, invalid in (("stage", "invented"), ("class", "crashed"), ("summary", ""), ("evidence", [])):
            value = partial_manifest()
            value["failure"][key] = invalid
            with self.subTest(invalid=key):
                self.assert_invalid("case-manifest", value)
        value = partial_manifest()
        del value["artifact_ids"]
        self.assert_invalid("case-manifest", value)

    def test_final_failure_requires_verification_and_artifact_inventory(self):
        for status in ("not_reproduced", "inconclusive", "invalid_environment"):
            for key in ("verification_result_id", "artifact_ids"):
                value = partial_manifest(status)
                del value[key]
                with self.subTest(status=status, missing=key):
                    self.assert_invalid("case-manifest", value)

    def test_verified_and_replayable_manifests_still_require_complete_package(self):
        keys = ("vulnerability_id", "source_ids", "environment_id", "builds", "artifact_ids",
                "executions", "verification_result_id", "replay")
        for status in ("verified", "replayable"):
            complete = deepcopy(VALID["case-manifest"])
            complete["status"] = status
            self.assert_valid("case-manifest", complete)
            for key in keys:
                value = deepcopy(complete)
                del value[key]
                with self.subTest(status=status, missing=key):
                    self.assert_invalid("case-manifest", value)
            for group, roles in (("builds", ("vulnerable", "patched")),
                                 ("executions", ("vulnerable", "patched", "negative_controls"))):
                for role in roles:
                    value = deepcopy(complete)
                    del value[group][role]
                    with self.subTest(status=status, group=group, role=role):
                        self.assert_invalid("case-manifest", value)

    def test_verified_manifest_cannot_carry_current_failure(self):
        value = deepcopy(VALID["case-manifest"])
        value["failure"] = partial_manifest()["failure"]
        self.assert_invalid("case-manifest", value)

    def test_empty_or_unknown_role_maps_rejected(self):
        for group in ("builds", "executions"):
            for roles in ({}, {"unknown": "some-record"}, {"vulnerable": ""}, {"vulnerable": None}):
                value = partial_manifest()
                value[group] = roles
                with self.subTest(group=group, roles=roles):
                    self.assert_invalid("case-manifest", value)
        for roles in ({}, {"unknown": "run"}, {"negative_controls": []},
                      {"negative_controls": ["run", "run"]}):
            value = docker_unavailable()
            value["executions"] = roles
            with self.subTest(roles=roles):
                self.assert_invalid("verification-result", value)

    def test_verified_requires_all_checks_passed(self):
        for key in CHECK_KEYS:
            for status in ("failed", "not_evaluated"):
                value = deepcopy(VALID["verification-result"])
                value["checks"][key] = check(
                    status, "Fixture observation.", "artifact-observation",
                    "Required observation unavailable." if status == "not_evaluated" else None,
                )
                with self.subTest(check=key, status=status):
                    self.assert_invalid("verification-result", value)
            value = deepcopy(VALID["verification-result"])
            del value["checks"][key]
            with self.subTest(missing=key):
                self.assert_invalid("verification-result", value)

    def test_all_passed_cannot_claim_non_success(self):
        for verdict in ("NOT_REPRODUCED", "INCONCLUSIVE", "INVALID_ENVIRONMENT"):
            value = deepcopy(VALID["verification-result"])
            value.update(verdict=verdict, failure_class="oracle_failure")
            with self.subTest(verdict=verdict):
                self.assert_invalid("verification-result", value)

    def test_verified_requires_complete_executions_and_no_failure_class(self):
        for role in (None, "vulnerable", "patched", "negative_controls"):
            value = deepcopy(VALID["verification-result"])
            if role is None:
                del value["executions"]
            else:
                del value["executions"][role]
            with self.subTest(role=role):
                self.assert_invalid("verification-result", value)
        value = deepcopy(VALID["verification-result"])
        value["failure_class"] = "oracle_failure"
        self.assert_invalid("verification-result", value)

    def test_passed_and_failed_checks_require_evidence(self):
        for status in ("passed", "failed"):
            for key in CHECK_KEYS:
                value = non_success("INCONCLUSIVE", "patch_consistency", "oracle_failure")
                value["checks"][key] = check(status, "No supporting observation.")
                with self.subTest(status=status, check=key):
                    self.assert_invalid("verification-result", value)

    def test_not_evaluated_requires_reason_but_can_have_no_observation(self):
        value = docker_unavailable()
        self.assert_valid("verification-result", value)
        for reason in (None, ""):
            value = docker_unavailable()
            if reason is None:
                del value["checks"]["reachability"]["reason"]
            else:
                value["checks"]["reachability"]["reason"] = reason
            with self.subTest(reason=reason):
                self.assert_invalid("verification-result", value)
        value = docker_unavailable()
        value["checks"]["environment_and_build_identity"]["reason"] = "Contradictory skip reason."
        self.assert_invalid("verification-result", value)

    def test_unknown_check_status_and_legacy_boolean_rejected(self):
        for status in ("unknown", True, None):
            value = docker_unavailable()
            value["checks"]["reachability"]["status"] = status
            with self.subTest(status=status):
                self.assert_invalid("verification-result", value)
        value = deepcopy(VALID["verification-result"])
        value["checks"]["reachability"]["passed"] = True
        self.assert_invalid("verification-result", value)

    def test_overall_evidence_and_expectations_cannot_be_omitted(self):
        for field in ("evidence", "expectations"):
            value = docker_unavailable()
            del value[field]
            with self.subTest(field=field):
                self.assert_invalid("verification-result", value)
        value = docker_unavailable()
        value["evidence"] = []
        self.assert_invalid("verification-result", value)

    def test_oracle_adapter_and_case_identity_are_required(self):
        for field in ("name", "version", "adapter", "case_definition"):
            value = deepcopy(VALID["verification-result"])
            del value["oracle"][field]
            with self.subTest(field=field):
                self.assert_invalid("verification-result", value)
        for field in ("name", "version", "implementation"):
            value = docker_unavailable()
            del value["oracle"]["adapter"][field]
            with self.subTest(adapter=field):
                self.assert_invalid("verification-result", value)
        for field in ("id", "sha256"):
            for reference in ("implementation", "case_definition"):
                value = docker_unavailable()
                ref = (value["oracle"]["adapter"][reference] if reference == "implementation"
                       else value["oracle"][reference])
                del ref[field]
                with self.subTest(reference=reference, field=field):
                    self.assert_invalid("verification-result", value)
        value = docker_unavailable()
        del value["oracle"]
        self.assert_invalid("verification-result", value)

    def test_schema_validity_does_not_claim_cross_record_integrity(self):
        # This boundary is intentional: these calls only perform schema validation.
        value = deepcopy(VALID["case-manifest"])
        value["builds"]["patched"] = value["builds"]["vulnerable"]
        self.assert_valid("case-manifest", value)
        value = deepcopy(VALID["verification-result"])
        value["oracle"]["case_definition"]["id"] = "not-in-inventory"
        self.assert_valid("verification-result", value)


if __name__ == "__main__":
    unittest.main()
