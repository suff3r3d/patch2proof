"""The DACN package must remain a draft and detect changed evidence bytes."""

import os
import tempfile
import unittest
from pathlib import Path

from dacn.contracts import SchemaCatalog
from dacn.storage import CaseStore
from dacn.validation import PackageValidator

try:
    from patch2proof.dacn_bridge import publish_dacn_package
    from patch2proof.models import CaseManifest
except ImportError:  # The schema-only Docker test image does not install the pipeline.
    publish_dacn_package = None
    CaseManifest = None


@unittest.skipUnless(publish_dacn_package is not None, "pipeline dependencies are unavailable")
class DacnBridgeTests(unittest.TestCase):
    def test_early_report_omits_unavailable_source_and_vulnerability_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for name in ("case.json", "proof-bundle.json", "final-report.json", "final-report.md"):
                (output / name).write_text("{}\n", encoding="utf-8")
            case = CaseManifest(case_id="early-report", title="Stopped before ingestion")

            result = publish_dacn_package(case, {}, output)
            catalog = SchemaCatalog(Path(__file__).resolve().parents[2] / "schemas")
            package = Path(result["package_path"])
            records = CaseStore(package, catalog).load_records()

            self.assertTrue(result["validation"]["valid"])
            self.assertEqual(
                {record["schema"] for record in records},
                {"artifact-record", "case-manifest"},
            )

    def test_dry_run_package_is_draft_and_artifact_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for name, content in {
                "case.json": "{}\n",
                "proof-bundle.json": "{}\n",
                "final-report.json": "{}\n",
                "final-report.md": "# Draft\n",
                "raw-patch.diff": "diff --git a/a b/a\n",
                "source-identities.json": "{}\n",
            }.items():
                (output / name).write_text(content, encoding="utf-8")
            case = CaseManifest(case_id="bridge-test", title="Local draft case")

            result = publish_dacn_package(case, {"raw_diff": "diff"}, output)
            catalog = SchemaCatalog(Path(__file__).resolve().parents[2] / "schemas")
            package = Path(result["package_path"])
            records = CaseStore(package, catalog).load_records()
            validator = PackageValidator(catalog)

            self.assertEqual(result["status"], "draft")
            self.assertTrue(validator.validate(package, result["manifest_id"], records).valid)
            self.assertFalse({"environment-spec", "build-record", "execution-record",
                              "verification-result"} & {record["schema"] for record in records})

            patch = next(record for record in records if record["schema"] == "source-record")
            patch_artifact = next(
                record for record in records if record["id"] == patch["content"]["id"]
            )
            stored = package / patch_artifact["path"]
            os.chmod(stored, 0o600)
            stored.write_bytes(b"changed patch bytes")
            report = validator.validate(package, result["manifest_id"], records)
            self.assertFalse(report.valid)
            self.assertIn("artifact_hash_mismatch", {item.code for item in report.diagnostics})


if __name__ == "__main__":
    unittest.main()
