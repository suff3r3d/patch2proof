"""Complete synthetic package with real stored bytes; never executed as a CVE."""

from copy import deepcopy

from dacn.storage import CaseStore
from schema.fixtures_current import VALID, docker_unavailable, partial_manifest


PROVENANCE = {"created_at": "2026-10-04T00:10:00Z", "created_by": "infrastructure-fixture"}


def complete_case(root, catalog, *, persist=False):
    store = CaseStore(root, catalog)
    values = deepcopy(VALID)
    del values["artifact-record"]
    patched_build = deepcopy(values["build-record"])
    patched_build.update(id="build-patched", role="patched", revision="b" * 40, source_tree_sha256="3" * 64)
    patched_build["outputs"][0]["id"] = "artifact-patched-binary"
    patched_run = deepcopy(values["execution-record"])
    patched_run.update(id="execution-patched", role="patched", build_id="build-patched", process={"exit_code": 0})
    patched_run["executable"]["id"] = "artifact-patched-binary"
    patched_run["provenance"]["inputs"] = ["build-patched"]
    patched_run.pop("sanitizer_report", None)
    controls = []
    for run, identifier in ((values["execution-record"], "execution-control"), (patched_run, "execution-control-patched")):
        control = deepcopy(run)
        control.update(id=identifier, role="negative_control", input_role="benign_control", process={"exit_code": 0})
        control["input"]["id"] = "artifact-benign-input"
        control.pop("sanitizer_report", None)
        controls.append(control)
    for name in ("verification-result", "case-manifest"):
        values[name]["executions"]["negative_controls"] = [run["id"] for run in controls]
    records = [*values.values(), patched_build, patched_run, *controls]
    for record in records:
        record["provenance"]["created_at"] = PROVENANCE["created_at"]
    return _store_artifacts(store, records, values["case-manifest"], persist)


def early_failure(root, catalog, *, persist=False):
    result, manifest = docker_unavailable(), partial_manifest("invalid_environment")
    records = [result, manifest]
    return _store_artifacts(CaseStore(root, catalog), records, manifest, persist)


def _store_artifacts(store, records, manifest, persist):
    artifacts = {}

    def replace_references(value):
        if isinstance(value, dict):
            if set(value) == {"id", "sha256"}:
                identifier = value["id"]
                if identifier not in artifacts:
                    artifacts[identifier] = store.put_bytes(
                        f"Synthetic evidence bytes for {identifier}.\n".encode(),
                        identifier=identifier, case_id=manifest["case_id"], kind="fixture",
                        provenance=deepcopy(PROVENANCE),
                    )
                value.update(artifacts[identifier].reference.to_dict())
            else:
                for child in value.values():
                    replace_references(child)
        elif isinstance(value, list):
            for child in value:
                replace_references(child)

    for record in records:
        replace_references(record)
    manifest["artifact_ids"] = sorted(artifacts)
    records += [artifact.record for artifact in artifacts.values()]
    if persist:
        for record in records:
            store.put_record(record)
    return records, manifest["id"]
