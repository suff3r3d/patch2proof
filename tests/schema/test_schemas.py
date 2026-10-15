import json
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .fixtures import invalid_fixtures
from .fixtures_current import VALID


ROOT = Path(__file__).resolve().parents[2]
PERSISTED = {
    "artifact-record", "source-record", "vulnerability-record",
    "environment-spec", "build-record", "execution-record",
    "verification-result", "case-manifest",
}


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_registry():
    schemas = {}
    names = {}
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        with path.open(encoding="utf-8") as stream:
            schema = json.load(stream, object_pairs_hook=reject_duplicate_keys)
        schemas[schema["$id"]] = schema
        names[path.name.removesuffix(".schema.json")] = schema
    registry = Registry().with_resources(
        [(uri, Resource.from_contents(schema)) for uri, schema in schemas.items()]
    )
    return schemas, names, registry


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas, cls.by_name, cls.registry = load_registry()

    def validator(self, name):
        return Draft202012Validator(
            self.by_name[name],
            registry=self.registry,
            format_checker=FormatChecker(),
        )

    def test_inventory(self):
        self.assertEqual(PERSISTED | {"common"}, set(self.by_name))
        self.assertEqual(PERSISTED, set(VALID))
        self.assertFalse(any((ROOT / "schemas").glob("[0-9]*")))

    def test_schemas_are_valid_draft_2020_12(self):
        for name, schema in self.by_name.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    def test_every_reference_resolves_offline(self):
        for name, schema in self.by_name.items():
            pending = [schema]
            while pending:
                value = pending.pop()
                if isinstance(value, dict):
                    reference = value.get("$ref")
                    if reference:
                        with self.subTest(schema=name, reference=reference):
                            self.registry.resolver(base_uri=schema["$id"]).lookup(reference)
                    pending.extend(value.values())
                elif isinstance(value, list):
                    pending.extend(value)

    def test_explicit_valid_fixture_for_each_persisted_schema(self):
        for name, instance in VALID.items():
            with self.subTest(schema=name):
                errors = sorted(self.validator(name).iter_errors(instance), key=lambda error: list(error.path))
                self.assertEqual([], errors, "\n".join(error.message for error in errors))

    def test_targeted_invalid_fixture_for_each_persisted_schema(self):
        invalid = invalid_fixtures()
        self.assertEqual(PERSISTED, set(invalid))
        for name, instance in invalid.items():
            with self.subTest(schema=name):
                self.assertFalse(self.validator(name).is_valid(instance))

    def test_five_audited_gaps_are_enforced(self):
        cases = []

        value = deepcopy(VALID["vulnerability-record"])
        del value["claims"]
        cases.append(("vulnerability-record", "material claims", value))

        value = deepcopy(VALID["vulnerability-record"])
        value["patch"]["static_context"]["reachability"]["evidence"] = []
        cases.append(("vulnerability-record", "reachability evidence", value))

        value = deepcopy(VALID["environment-spec"])
        del value["limits"]["disk_mb"]
        cases.append(("environment-spec", "complete resource limits", value))

        value = deepcopy(VALID["environment-spec"])
        value["instrumentation"][0]["availability"] = "maybe"
        cases.append(("environment-spec", "instrumentation availability", value))

        value = deepcopy(VALID["build-record"])
        del value["observed_toolchain"]
        cases.append(("build-record", "observed toolchain", value))

        value = deepcopy(VALID["build-record"])
        value["dependency_resolution"]["status"] = "partial"
        cases.append(("build-record", "resolved dependencies", value))

        value = deepcopy(VALID["build-record"])
        del value["dependency_resolution"]["inventory"]
        cases.append(("build-record", "dependency inventory", value))

        value = deepcopy(VALID["verification-result"])
        value["checks"]["negative_controls"]["status"] = "failed"
        cases.append(("verification-result", "all VERIFIED checks pass", value))

        value = deepcopy(VALID["verification-result"])
        value["checks"]["negative_controls"]["id"] = "redundant-id"
        cases.append(("verification-result", "check key is the identifier", value))

        for schema, requirement, instance in cases:
            with self.subTest(schema=schema, requirement=requirement):
                self.assertFalse(self.validator(schema).is_valid(instance))

    def test_environment_requires_digest_pinned_docker(self):
        for isolation_type in ("container", "virtual_machine", "sandbox", "podman"):
            value = deepcopy(VALID["environment-spec"])
            value["isolation"]["type"] = isolation_type
            with self.subTest(isolation_type=isolation_type):
                self.assertFalse(self.validator("environment-spec").is_valid(value))

        value = deepcopy(VALID["environment-spec"])
        del value["isolation"]["image_digest"]
        self.assertFalse(self.validator("environment-spec").is_valid(value))


if __name__ == "__main__":
    unittest.main()
