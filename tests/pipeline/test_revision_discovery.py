"""Offline tests for evidence-backed CVE revision discovery."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from patch2proof.graph import discovery_node, graph, initial_state, invoke_case, route_discovery
from patch2proof.llm import (
    ReasoningConfigurationError,
    RevisionSelection,
    select_revision_candidate,
)
from patch2proof.revision_discovery import (
    DiscoveryError,
    DiscoveryOutcome,
    _github_commit_reference,
    discover_revisions,
)

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


class RevisionDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        (self.repo / "code.py").write_text("vulnerable = True\n", encoding="utf-8")
        git(self.repo, "add", "code.py")
        git(self.repo, "commit", "-qm", "Before fix")
        self.vulnerable = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "code.py").write_text("vulnerable = False\n", encoding="utf-8")
        git(self.repo, "commit", "-qam", "Fix CVE-2026-12345")
        self.fixed = git(self.repo, "rev-parse", "HEAD")
        self.cve = "CVE-2026-12345"
        self.commit_url = f"https://github.com/acme/project/commit/{self.fixed}"

    def payloads(self, *, two_refs=False):
        references = [{"url": self.commit_url, "tags": ["Patch"]}]
        if two_refs:
            references.append({
                "url": f"https://github.com/other/project/commit/{self.fixed}",
                "tags": ["Patch"],
            })
        nvd = {"vulnerabilities": [{"cve": {
            "id": self.cve, "references": references,
        }}]}
        commit = {
            "sha": self.fixed,
            "html_url": self.commit_url,
            "parents": [{"sha": self.vulnerable}],
        }
        def fake_fetch(url):
            value = nvd if "nvd.nist.gov" in url else commit
            raw = json.dumps(value, sort_keys=True).encode()
            return raw, value
        return fake_fetch

    def test_resolves_single_evidenced_pair(self):
        def materialize(_owner, _repo, _sha, root):
            destination = root / "repo"
            shutil.copytree(self.repo, destination)
            return destination
        outcome = discover_revisions(
            self.cve, self.root / "output", SCHEMAS,
            fetcher=self.payloads(),
            materializer=materialize,
        )
        self.assertEqual("resolved", outcome.result["status"])
        selected = outcome.result["selected"]
        self.assertEqual(self.vulnerable, selected["vulnerable_commit"])
        self.assertEqual(self.fixed, selected["fixed_commit"])
        self.assertTrue(all(value == "passed" for value in selected["checks"].values()))
        self.assertEqual(2, len(outcome.artifacts))

    def test_multiple_fix_links_remain_ambiguous(self):
        outcome = discover_revisions(
            self.cve, self.root / "output", SCHEMAS,
            fetcher=self.payloads(two_refs=True),
            materializer=lambda *_: self.fail("must not fetch repository"),
        )
        self.assertEqual("ambiguous", outcome.result["status"])
        self.assertNotIn("selected", outcome.result)

    def test_specialist_selection_is_still_subject_to_git_checks(self):
        calls = []
        def select(cve_id, candidates):
            calls.append((cve_id, candidates))
            return 0
        def materialize(_owner, _repo, _sha, root):
            destination = root / "repo"
            shutil.copytree(self.repo, destination)
            return destination
        outcome = discover_revisions(
            self.cve, self.root / "output", SCHEMAS,
            fetcher=self.payloads(), materializer=materialize, selector=select,
        )
        self.assertEqual("resolved", outcome.result["status"])
        self.assertEqual(1, len(calls))
        self.assertEqual(self.cve, calls[0][0])
        self.assertEqual("passed", outcome.result["selected"]["checks"]["revisions_exist"])

    def test_specialist_refusal_and_invalid_choice_stay_ambiguous(self):
        for choice in (None, 3):
            with self.subTest(choice=choice):
                outcome = discover_revisions(
                    self.cve, self.root / f"output-{choice}", SCHEMAS,
                    fetcher=self.payloads(),
                    selector=lambda _cve, _candidates, selected=choice: selected,
                    materializer=lambda *_: self.fail("must not fetch repository"),
                )
                self.assertEqual("ambiguous", outcome.result["status"])
                self.assertNotIn("selected", outcome.result)

    def test_specialist_cannot_promote_untagged_reference(self):
        base_fetch = self.payloads()
        def fetch(url):
            raw, value = base_fetch(url)
            if "nvd.nist.gov" in url:
                value["vulnerabilities"][0]["cve"]["references"][0].pop("tags")
                raw = json.dumps(value).encode()
            if "api.osv.dev" in url:
                value = {"id": self.cve, "references": []}
                raw = json.dumps(value).encode()
            return raw, value
        outcome = discover_revisions(
            self.cve, self.root / "output", SCHEMAS,
            fetcher=fetch, selector=lambda _cve, _candidates: 0,
            materializer=lambda *_: self.fail("must not fetch repository"),
        )
        self.assertEqual("ambiguous", outcome.result["status"])

    def test_specialist_can_select_second_supported_fix(self):
        (self.repo / "code.py").write_text("vulnerable = False\nextra = True\n", encoding="utf-8")
        git(self.repo, "commit", "-qam", "Follow-up fix")
        later_fix = git(self.repo, "rev-parse", "HEAD")
        nvd = {"vulnerabilities": [{"cve": {
            "id": self.cve,
            "descriptions": [{"lang": "en", "value": "Two related patch commits"}],
            "references": [
                {"url": self.commit_url, "tags": ["Patch"]},
                {"url": f"https://github.com/acme/project/commit/{later_fix}",
                 "tags": ["Patch"]},
            ],
        }}]}
        def fetch(url):
            if "nvd.nist.gov" in url:
                value = nvd
            else:
                sha = url.rsplit("/", 1)[-1]
                value = {
                    "sha": sha,
                    "html_url": f"https://github.com/acme/project/commit/{sha}",
                    "parents": [{"sha": self.fixed if sha == later_fix else self.vulnerable}],
                    "commit": {"message": "Follow-up fix" if sha == later_fix else "First fix"},
                    "files": [{"filename": "code.py"}],
                }
            return json.dumps(value).encode(), value
        def materialize(_owner, _repo, _sha, root):
            destination = root / "repo"
            shutil.copytree(self.repo, destination)
            return destination
        outcome = discover_revisions(
            self.cve, self.root / "output", SCHEMAS,
            fetcher=fetch, materializer=materialize,
            selector=lambda _cve, candidates: 1 if len(candidates) == 2 else None,
        )
        self.assertEqual("resolved", outcome.result["status"])
        self.assertEqual(later_fix, outcome.result["selected"]["fixed_commit"])
        self.assertEqual(self.fixed, outcome.result["selected"]["vulnerable_commit"])

    def test_model_selection_validates_cited_evidence(self):
        candidate = {
            "checks": {"cve_link_supported": "passed"},
            "evidence": [{"kind": "cve_record"}],
        }
        with patch("patch2proof.llm._invoke_structured", return_value=(
            RevisionSelection(candidate_index=0, rationale="Tagged fix", evidence_indices=[0]),
            "openai",
        )):
            choice, record = select_revision_candidate(
                self.cve, [candidate], mode="openai", model_name="test-model",
            )
        self.assertEqual(0, choice.candidate_index)
        self.assertEqual("revision-discovery", record["specialist"])
        self.assertEqual("openai", record["provider"])
        self.assertEqual(64, len(record["input_sha256"]))
        with patch("patch2proof.llm._invoke_structured", return_value=(
            RevisionSelection(candidate_index=0, rationale="Unsupported", evidence_indices=[1]),
            "openai",
        )):
            with self.assertRaisesRegex(ReasoningConfigurationError, "invalid evidence"):
                select_revision_candidate(
                    self.cve, [candidate], mode="openai", model_name="test-model",
                )
        with self.assertRaisesRegex(ReasoningConfigurationError, "No reasoning provider"):
            select_revision_candidate(self.cve, [candidate], mode="required")

    def test_osv_fallback_when_nvd_is_unavailable(self):
        base_fetch = self.payloads()
        def fetch(url):
            if "nvd.nist.gov" in url:
                raise DiscoveryError("NVD unavailable")
            if "api.osv.dev" in url:
                value = {"id": self.cve, "references": [{
                    "url": self.commit_url, "type": "FIX",
                }]}
                return json.dumps(value).encode(), value
            return base_fetch(url)
        def materialize(_owner, _repo, _sha, root):
            destination = root / "repo"
            shutil.copytree(self.repo, destination)
            return destination
        outcome = discover_revisions(
            self.cve, self.root / "output", SCHEMAS,
            fetcher=fetch, materializer=materialize,
        )
        self.assertEqual("resolved", outcome.result["status"])
        self.assertIn("discovery-osv.json", outcome.artifacts)
        self.assertNotIn("discovery-nvd.json", outcome.artifacts)

    def test_untagged_commit_link_is_not_selected_as_a_fix(self):
        base_fetch = self.payloads()
        def fetch(url):
            if "nvd.nist.gov" in url:
                raw, value = base_fetch(url)
                value["vulnerabilities"][0]["cve"]["references"][0].pop("tags")
                return json.dumps(value).encode(), value
            if "api.osv.dev" in url:
                value = {"id": self.cve, "references": []}
                return json.dumps(value).encode(), value
            return base_fetch(url)
        outcome = discover_revisions(
            self.cve, self.root / "output", SCHEMAS,
            fetcher=fetch,
            materializer=lambda *_: self.fail("must not fetch repository"),
        )
        self.assertEqual("ambiguous", outcome.result["status"])
        self.assertNotIn("selected", outcome.result)

    def test_no_fix_reference_fails_closed(self):
        def fetch(_url):
            value = {"vulnerabilities": [{"cve": {
                "id": self.cve, "references": [{"url": "https://example.invalid/advisory"}],
            }}]}
            return json.dumps(value).encode(), value
        outcome = discover_revisions(self.cve, self.root / "output", SCHEMAS, fetcher=fetch)
        self.assertEqual("failed", outcome.result["status"])
        self.assertNotIn("selected", outcome.result)

    def test_rejects_untrusted_commit_url_shapes(self):
        self.assertIsNone(_github_commit_reference(
            f"https://github.com.evil.invalid/acme/project/commit/{self.fixed}"
        ))
        self.assertIsNone(_github_commit_reference(
            f"http://github.com/acme/project/commit/{self.fixed}"
        ))
        self.assertIsNone(_github_commit_reference(
            "https://github.com/acme/project/commit/HEAD"
        ))

    def test_cve_only_state_routes_through_discovery(self):
        state = initial_state(self.cve)
        state["case"]["output_dir"] = str(self.root)
        state["case"]["policy"]["allowed_repo_root"] = str(self.root)
        self.assertEqual({"cve_id": self.cve}, state["discovery_request"])
        self.assertFalse(state["case"]["policy"]["allow_docker_build"])
        candidate = {
            "repository_url": "https://github.com/acme/project.git",
            "vulnerable_commit": self.vulnerable,
            "fixed_commit": self.fixed,
        }
        result = {"status": "resolved", "selected": candidate}
        outcome = DiscoveryOutcome(result, self.repo, ())
        with patch("patch2proof.graph.discover_revisions", return_value=outcome):
            updated = discovery_node(state)
        self.assertEqual("ingest", route_discovery(updated))
        self.assertEqual(self.vulnerable, updated["case"]["vulnerable_ref"])
        self.assertEqual(self.fixed, updated["case"]["fixed_ref"])

    def test_graph_loads_specialist_selection_and_records_decision(self):
        state = initial_state(self.cve)
        state["case"]["output_dir"] = str(self.root)
        state["case"]["policy"]["allowed_repo_root"] = str(self.root)
        candidate = {
            "repository_url": "https://github.com/acme/project.git",
            "vulnerable_commit": self.vulnerable,
            "fixed_commit": self.fixed,
            "checks": {"cve_link_supported": "passed"},
            "evidence": [{"kind": "cve_record"}],
        }
        def discover(_cve, _output, _schemas, *, repository_hint, selector):
            self.assertIsNone(repository_hint)
            self.assertEqual(0, selector(self.cve, [candidate]))
            return DiscoveryOutcome(
                {"request": {"cve_id": self.cve}, "status": "ambiguous",
                 "candidates": [candidate], "failure_reason": "fixture stop"},
                None, (),
            )
        with patch("patch2proof.graph.select_revision_candidate", return_value=(
            RevisionSelection(candidate_index=0, rationale="Supported", evidence_indices=[0]),
            {"provider": "openai", "decision": {"candidate_index": 0}},
        )) as specialist:
            with patch("patch2proof.graph.discover_revisions", side_effect=discover):
                updated = discovery_node(state)
        specialist.assert_called_once()
        self.assertIn("revision-discovery-reasoning.json", updated["discovery_artifacts"])
        self.assertTrue((self.root / self.cve / "revision-discovery-reasoning.json").exists())

    def test_unresolved_cve_run_writes_candidate_report_without_ingestion(self):
        result = {
            "request": {"cve_id": self.cve}, "status": "failed", "candidates": [],
            "failure_reason": "No supported fixing commit reference was found.",
        }
        outcome = DiscoveryOutcome(result, None, ())
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            with patch("patch2proof.graph.discover_revisions", return_value=outcome):
                state = invoke_case(self.cve, dry_run=True, auto_approve=True)
        finally:
            os.chdir(previous)
        self.assertEqual("completed", state["status"])
        self.assertNotIn("raw_diff", state)
        self.assertEqual("failed", state["discovery_result"]["status"])
        self.assertEqual("not_executed", state["proof_bundle"]["claim_status"])
        self.assertTrue(state["dacn_package"]["validation"]["valid"])

    def test_resolved_cve_run_reaches_patch_ingestion(self):
        cve = "CVE-2026-12346"
        repository = self.root / "artifacts" / cve / "repository"
        repository.parent.mkdir(parents=True)
        shutil.copytree(self.repo, repository)
        candidate = {
            "repository_url": "https://github.com/acme/project.git",
            "vulnerable_commit": self.vulnerable,
            "fixed_commit": self.fixed,
        }
        outcome = DiscoveryOutcome(
            {"request": {"cve_id": cve}, "status": "resolved",
             "candidates": [candidate], "selected": candidate},
            repository, (),
        )
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            with patch("patch2proof.graph.discover_revisions", return_value=outcome):
                with patch.dict(os.environ, {
                    "P2P_LLM_MODE": "heuristic", "P2P_ALLOW_HEURISTIC_REASONING": "1",
                }):
                    state = invoke_case(cve, dry_run=True, auto_approve=True)
        finally:
            os.chdir(previous)
        self.assertEqual("completed", state["status"])
        self.assertIn("vulnerable = False", state["raw_diff"])
        self.assertEqual(str(repository), state["case"]["repository_path"])
        self.assertTrue(state["dacn_package"]["validation"]["valid"])

    def test_graph_accepts_cve_only_state(self):
        cve = "CVE-2026-12347"
        result = {
            "request": {"cve_id": cve}, "status": "failed", "candidates": [],
            "failure_reason": "No supported fixing commit reference was found.",
        }
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            with patch("patch2proof.graph.discover_revisions", return_value=DiscoveryOutcome(
                result, None, (),
            )):
                state = graph.invoke({"cve_id": cve})
        finally:
            os.chdir(previous)
        self.assertEqual("completed", state["status"])
        self.assertEqual(cve, state["case"]["case_id"])
        self.assertEqual("not_executed", state["proof_bundle"]["claim_status"])

    def test_cve_only_cannot_request_target_execution(self):
        with self.assertRaisesRegex(ValueError, "dry-run only"):
            invoke_case(self.cve, dry_run=False, auto_approve=True)


if __name__ == "__main__":
    unittest.main()
