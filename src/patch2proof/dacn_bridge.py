"""Publish a truthful, schema-validated DACN snapshot of a pipeline run.

The graph's working artifacts remain unchanged. DACN records are a separate,
immutable package; records that require unobserved builds or executions are
deliberately absent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from dacn.contracts import SchemaCatalog, utc_now
from dacn.storage import CaseStore, open_case_file
from dacn.validation import PackageValidator

from .evidence import write_json
from .models import CaseManifest

PACKAGE_VERSION = "patch2proof-dacn-draft/1"


def _schema_root() -> Path:
    source_tree = Path(__file__).resolve().parents[2] / "schemas"
    installed = Path(__file__).resolve().parents[1] / "schemas"
    for candidate in (source_tree, installed):
        if (candidate / "common.schema.json").is_file():
            return candidate
    raise FileNotFoundError("Bundled DACN schemas are unavailable")


def _envelope(kind: str, identifier: str, case_id: str, created_at: str,
              *, inputs: list[str] | None = None) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "created_at": created_at,
        "created_by": "patch2proof.dacn_bridge",
        "method": "offline pipeline artifact snapshot",
    }
    if inputs:
        provenance["inputs"] = inputs
    return {
        "schema": kind,
        "id": identifier,
        "case_id": case_id,
        "provenance": provenance,
    }


def _artifact_names(state: Mapping[str, Any]) -> list[str]:
    names = ["case.json", "proof-bundle.json", "final-report.json", "final-report.md"]
    names.extend(name for name in state.get("discovery_artifacts", [])
                 if isinstance(name, str) and (
                     name in {"discovery-nvd.json", "discovery-osv.json",
                              "revision-discovery-result.json",
                              "revision-discovery-reasoning.json"}
                     or name in {f"discovery-commit-{index}.json" for index in range(8)}
                 ))
    for key, filename in (
        ("raw_diff", "raw-patch.diff"),
        ("raw_diff", "source-identities.json"),
        ("diff_summary", "patch-analysis.json"),
        ("source_context", "source-context.json"),
        ("vulnerability_contract", "vulnerability-contract.json"),
        ("reproduction_graph", "reproduction-graph.json"),
        ("safe_poc_plan", "safe-poc-plan.json"),
        ("safe_poc", "safepoc.json"),
        ("docker_spec", "docker-plan.json"),
        ("environment_profile", "environment-profile.json"),
        ("images", "images.json"),
        ("validation", "validation.json"),
        ("coverage", "coverage.json"),
        ("review", "skeptic-review.json"),
    ):
        if state.get(key) is not None:
            names.append(filename)
    return names


def publish_dacn_package(
    case: CaseManifest, state: Mapping[str, Any], output_dir: Path
) -> dict[str, Any]:
    """Snapshot current outputs into a validated DACN draft package."""

    catalog = SchemaCatalog(_schema_root())
    run_id = uuid4().hex[:16]
    created_at = utc_now()
    package_root = output_dir / "dacn" / run_id
    store = CaseStore(package_root, catalog)
    records: list[dict[str, Any]] = []
    artifacts: dict[str, dict[str, str]] = {}

    artifact_names = _artifact_names(state)
    if (output_dir / "source-pair.json").exists():
        artifact_names.append("source-pair.json")
    artifact_names.extend(
        name for name in (
            "build-vulnerable.log", "build-fixed.log",
            "image-vulnerable.json", "image-fixed.json",
        )
        if (output_dir / name).exists()
    )
    for filename in artifact_names:
        identifier = f"artifact-{run_id}-{filename}"
        with open_case_file(output_dir, filename) as stream:
            stored = store.put_artifact(
                stream,
                identifier=identifier,
                case_id=case.case_id,
                kind="pipeline-output",
                provenance=_envelope("artifact-record", identifier, case.case_id, created_at)[
                    "provenance"
                ],
            )
        records.append(stored.record)
        artifacts[filename] = stored.reference.to_dict()

    source_id: str | None = None
    vulnerability_id: str | None = None
    patch_ref = artifacts.get("raw-patch.diff")
    if patch_ref is not None:
        source_id = f"source-{run_id}-patch"
        source = {
            **_envelope("source-record", source_id, case.case_id, created_at,
                        inputs=[patch_ref["id"]]),
            "source_type": "other",
            "url": f"urn:patch2proof:case:{case.case_id}:patch:{patch_ref['sha256']}",
            "retrieved_at": created_at,
            "retrieval_status": "succeeded",
            "content": patch_ref,
            "title": "Locally ingested patch",
            "notes": "Internal case URI; this record identifies stored local patch bytes.",
        }
        catalog.require_valid(source)
        store.put_record(source)
        records.append(source)

        vulnerability_id = f"vulnerability-{run_id}"
        vulnerability = {
            **_envelope("vulnerability-record", vulnerability_id, case.case_id, created_at,
                        inputs=[source_id]),
            "identifiers": [case.case_id],
            "title": case.title,
            "summary": case.advisory or case.title,
            "sources": [source_id],
            "revision_status": "ambiguous",
            "failure": {
                "class": "revision_failure",
                "summary": (
                    "The DACN package has no independently recorded, immutable "
                    "repository and paired revision identities."
                ),
            },
            "claims": [{
                "field": "/patch/diff",
                "raw_value": "raw-patch.diff",
                "normalized_value": patch_ref["sha256"],
                "source_id": source_id,
                "classification": "confirmed_fact",
                "confidence": "high",
                "evidence": [patch_ref],
                "method": "SHA-256 measured from the stored local patch bytes.",
            }],
            "uncertainties": ["Paired revision identity is not established by this draft package."],
        }
        catalog.require_valid(vulnerability)
        store.put_record(vulnerability)
        records.append(vulnerability)

    manifest_id = f"case-manifest-{run_id}"
    manifest = {
        **_envelope("case-manifest", manifest_id, case.case_id, created_at,
                    inputs=[record["id"] for record in records]),
        "package_version": PACKAGE_VERSION,
        "status": "draft",
        "artifact_ids": [
            record["id"] for record in records if record["schema"] == "artifact-record"
        ],
    }
    if source_id is not None:
        manifest["source_ids"] = [source_id]
    if vulnerability_id is not None:
        manifest["vulnerability_id"] = vulnerability_id
    catalog.require_valid(manifest)
    store.put_record(manifest)
    records.append(manifest)

    validation = PackageValidator(catalog).validate(package_root, manifest_id, records)
    validation_payload = validation.to_dict()
    write_json(package_root / "validation-report.json", validation_payload)
    if not validation.valid:
        raise ValueError(f"DACN package validation failed: {validation_payload['diagnostics']}")

    summary = {
        "manifest_id": manifest_id,
        "status": "draft",
        "package_path": str(package_root),
        "record_count": len(records),
        "validation": validation_payload,
    }
    write_json(output_dir / "dacn-package.json", summary)
    return summary
