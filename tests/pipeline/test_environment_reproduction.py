"""Environment plans must retain source identity and fail closed on missing build inputs."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from patch2proof.cli import app
from patch2proof.environment_profile import inspect_environment_pair
from patch2proof.graph import (
    build_node,
    environment_plan_node,
    route_build,
    route_build_approval,
    route_environment_plan,
)
from patch2proof.models import CaseManifest, DockerSpec, ExecutionPolicy
from patch2proof.proof_bundle import build_proof_bundle
from patch2proof.tools.docker_worker import DockerWorker
from patch2proof.tools.revision_workspace import materialize_pair


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


class EnvironmentReproductionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        (self.repo / "requirements.txt").write_text("", encoding="utf-8")
        (self.repo / "app.py").write_text("fixed = False\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "Before")
        self.vulnerable = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "app.py").write_text("fixed = True\n", encoding="utf-8")
        git(self.repo, "commit", "-qam", "After")
        self.fixed = git(self.repo, "rev-parse", "HEAD")

    def case(self, **policy_overrides):
        return CaseManifest.model_validate({
            "case_id": "env-case", "title": "Environment test",
            "repository_path": str(self.repo),
            "vulnerable_ref": self.vulnerable, "fixed_ref": self.fixed,
            "language": "python", "output_dir": str(self.root / "artifacts"),
            "policy": {
                "authorized": True,
                "allowed_repo_root": str(self.root),
                "allowed_artifact_root": str(self.root),
                **policy_overrides,
            },
        })

    def test_detects_same_profile_and_records_both_manifests(self):
        profile = inspect_environment_pair(self.repo, self.root, self.vulnerable, self.fixed)
        self.assertEqual(profile["status"], "detected")
        self.assertEqual(profile["language"], "python")
        self.assertEqual(profile["build_system"], "pip")
        self.assertEqual(profile["revisions"]["vulnerable"]["commit"], self.vulnerable)
        self.assertIn("requirements.txt", profile["revisions"]["fixed"]["manifests"])

    def test_materializes_distinct_contexts_with_archive_hashes(self):
        pair = materialize_pair(
            self.repo, self.root, self.vulnerable, self.fixed,
            self.root / "artifacts" / "source-pair", artifact_root=self.root,
        )
        contexts = pair["contexts"]
        self.assertNotEqual(
            (Path(contexts["vulnerable"]) / "app.py").read_text(),
            (Path(contexts["fixed"]) / "app.py").read_text(),
        )
        self.assertEqual(len(pair["archive_sha256"]["vulnerable"]), 64)
        self.assertNotEqual(
            pair["archive_sha256"]["vulnerable"], pair["archive_sha256"]["fixed"]
        )

    def test_unknown_build_system_requires_review(self):
        (self.repo / "requirements.txt").unlink()
        git(self.repo, "add", "-u")
        git(self.repo, "commit", "-qm", "Remove build manifest")
        case = self.case()
        case = case.model_copy(update={
            "language": "unknown", "fixed_ref": git(self.repo, "rev-parse", "HEAD"),
        })
        result = environment_plan_node({"case": case.model_dump(mode="json")})
        self.assertEqual(result["status"], "environment_review_required")
        self.assertEqual(route_environment_plan(result), "report")

    def test_real_build_does_not_continue_when_policy_disallows_it(self):
        case = self.case(allow_docker_build=False)
        state = {
            "case": case.model_dump(mode="json"),
            "docker_spec": self.spec().model_dump(mode="json"),
            "events": [],
        }
        result = build_node(state)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(route_build(result), "report")
        self.assertEqual(route_build_approval({"status": "rejected"}), "report")
        self.assertEqual(
            build_proof_bundle({**state, **result}, output_dir=self.root)["claim_status"],
            "blocked",
        )

    def spec(self):
        vulnerable_context = self.root / "vulnerable-context"
        fixed_context = self.root / "fixed-context"
        vulnerable_context.mkdir(exist_ok=True)
        fixed_context.mkdir(exist_ok=True)
        return DockerSpec(
            case_id="env-case", language="python", context_dir=str(self.repo),
            vulnerable_context_dir=str(vulnerable_context),
            fixed_context_dir=str(fixed_context),
            dockerfile_path=str(Path("templates/docker/python.Dockerfile").resolve()),
            vulnerable_ref=self.vulnerable, fixed_ref=self.fixed,
            base_image="python:3.12-slim",
        )

    def test_offline_build_refuses_missing_base_image(self):
        policy = ExecutionPolicy.model_validate(self.case(allow_docker_build=True).policy)
        worker = DockerWorker(policy, self.root / "artifacts", dry_run=False)
        with patch.object(worker, "_check_docker_daemon"):
            with patch.object(worker, "_inspect_digest", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "not present locally"):
                    worker.build_pair(self.spec())

    def test_pair_build_uses_distinct_contexts_and_records_image_ids(self):
        policy = self.case(allow_docker_build=True).policy
        worker = DockerWorker(policy, self.root / "artifacts", dry_run=False)
        spec = self.spec().model_copy(update={
            "labels": {"org.patch2proof.run_id": "test-run"},
        })
        command_results = []

        def fake_run(command, **kwargs):
            command_results.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="built", stderr="")

        with patch.object(worker, "_check_docker_daemon"):
            with patch.object(worker, "_inspect_digest", side_effect=[
                "sha256:base", "sha256:vulnerable", "sha256:base", "sha256:fixed",
            ]):
                with patch("patch2proof.tools.docker_worker.subprocess.run", side_effect=fake_run):
                    images = worker.build_pair(spec)
        self.assertEqual([item.digest for item in images], [
            "sha256:vulnerable", "sha256:fixed",
        ])
        self.assertEqual(len(command_results), 2)
        self.assertNotEqual(command_results[0][-1], command_results[1][-1])
        for command in command_results:
            self.assertIn("--network=none", command)
            self.assertIn("--pull=false", command)
            self.assertIn("org.patch2proof.run_id=test-run", command)
        self.assertEqual(images[0].provenance["base_image_digest"], "sha256:base")
        self.assertTrue((self.root / "artifacts" / "build-vulnerable.log").exists())
        self.assertEqual(
            json.loads((self.root / "artifacts" / "image-fixed.json").read_text())["digest"],
            "sha256:fixed",
        )

    def test_cli_writes_read_only_environment_plan(self):
        case_file = self.root / "case.json"
        case_file.write_text(json.dumps(self.case().model_dump(mode="json")))
        result = CliRunner().invoke(app, ["recreate-environment", str(case_file)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("planned; no Docker build requested", result.output)
        profiles = list((self.root / "artifacts" / "environment-runs").glob(
            "*/env-case/environment-profile.json"
        ))
        self.assertEqual(len(profiles), 1)
        self.assertEqual(json.loads(profiles[0].read_text())["language"], "python")

    def test_cli_build_preserves_source_pair_when_docker_is_unavailable(self):
        case_file = self.root / "build-case.json"
        case_file.write_text(json.dumps(
            self.case(allow_docker_build=True).model_dump(mode="json")
        ))
        with patch.object(
            DockerWorker, "_check_docker_daemon", side_effect=RuntimeError("daemon offline")
        ):
            result = CliRunner().invoke(app, [
                "recreate-environment", str(case_file), "--build",
            ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("daemon offline", result.output)
        pair_records = list((self.root / "artifacts" / "environment-runs").glob(
            "*/env-case/source-pair.json"
        ))
        self.assertEqual(len(pair_records), 1)
        pair = json.loads(pair_records[0].read_text())
        self.assertEqual(pair["identities"]["fixed"]["commit"], self.fixed)


if __name__ == "__main__":
    unittest.main()
