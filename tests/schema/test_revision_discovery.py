"""Contract checks for CVE-led revision discovery before pipeline ingestion."""

import unittest
from copy import deepcopy

from jsonschema import Draft202012Validator, FormatChecker

from .test_schemas import load_registry

REQUEST = {"cve_id": "CVE-2026-12345"}
CANDIDATE = {
    "repository_url": "https://example.invalid/project.git",
    "vulnerable_commit": "a" * 40,
    "fixed_commit": "b" * 40,
    "fix_commit": "b" * 40,
    "evidence": [{
        "kind": "advisory",
        "url": "https://example.invalid/advisory",
        "retrieved_at": "2026-10-15T00:00:00Z",
        "content_sha256": "c" * 64,
    }],
    "checks": {
        "repository_matches_source": "passed",
        "revisions_exist": "passed",
        "vulnerable_precedes_fixed": "passed",
        "patch_delta_nonempty": "passed",
        "cve_link_supported": "passed",
    },
}


class RevisionDiscoveryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, schemas, registry = load_registry()
        cls.request_validator = Draft202012Validator(
            schemas["cve-discovery-request"], registry=registry,
            format_checker=FormatChecker(),
        )
        cls.result_validator = Draft202012Validator(
            schemas["revision-discovery-result"], registry=registry,
            format_checker=FormatChecker(),
        )

    def test_cve_alone_is_a_valid_request(self):
        self.assertTrue(self.request_validator.is_valid(REQUEST))
        self.assertFalse(self.request_validator.is_valid({"cve_id": "not-a-cve"}))
        self.assertFalse(self.request_validator.is_valid({
            "cve_id": REQUEST["cve_id"], "repository_hint": "file:///private/repo",
        }))

    def test_resolved_pair_requires_all_checks_and_provenance(self):
        result = {
            "request": REQUEST, "status": "resolved", "candidates": [CANDIDATE],
            "selected": CANDIDATE,
        }
        self.assertTrue(self.result_validator.is_valid(result))
        for field in CANDIDATE["checks"]:
            changed = deepcopy(result)
            changed["selected"]["checks"][field] = "not_evaluated"
            with self.subTest(check=field):
                self.assertFalse(self.result_validator.is_valid(changed))
        missing = deepcopy(result)
        missing["selected"]["evidence"] = []
        self.assertFalse(self.result_validator.is_valid(missing))
        missing = deepcopy(result)
        missing["selected"]["vulnerable_commit"] = "HEAD"
        self.assertFalse(self.result_validator.is_valid(missing))
        missing = deepcopy(result)
        missing["candidates"] = []
        self.assertFalse(self.result_validator.is_valid(missing))

    def test_ambiguous_and_failed_remain_unselected(self):
        ambiguous = {
            "request": REQUEST, "status": "ambiguous", "candidates": [CANDIDATE],
            "failure_reason": "Two plausible fixing commits remain.",
        }
        self.assertTrue(self.result_validator.is_valid(ambiguous))
        ambiguous["selected"] = CANDIDATE
        self.assertFalse(self.result_validator.is_valid(ambiguous))
        failed = {
            "request": REQUEST, "status": "failed", "candidates": [],
            "failure_reason": "No supported repository reference was found.",
        }
        self.assertTrue(self.result_validator.is_valid(failed))
        del failed["failure_reason"]
        self.assertFalse(self.result_validator.is_valid(failed))


if __name__ == "__main__":
    unittest.main()
