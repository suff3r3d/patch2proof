"""Synthetic structural examples for the current contract."""

from copy import deepcopy

from .fixtures import VALID as BASE_VALID, artifact_ref


VALID = deepcopy(BASE_VALID)

CHECK_KEYS = tuple(VALID["verification-result"]["checks"])


def check(status, summary, evidence_id=None, reason=None):
    value = {
        "status": status,
        "summary": summary,
        "evidence": [artifact_ref(evidence_id)] if evidence_id else [],
    }
    if reason is not None:
        value["reason"] = reason
    return value


def docker_unavailable():
    value = deepcopy(VALID["verification-result"])
    del value["executions"]
    value["provenance"]["inputs"] = ["artifact-docker-diagnostic"]
    value["verdict"] = "INVALID_ENVIRONMENT"
    value["failure_class"] = "configuration_failure"
    value["rationale"] = "Docker preflight failed; no target commands ran."
    value["evidence"] = [artifact_ref("artifact-docker-diagnostic")]
    value["checks"] = {
        name: check(
            "not_evaluated", "No execution observations exist.",
            reason="Docker preflight prevented builds and executions.",
        )
        for name in CHECK_KEYS
    }
    value["checks"]["environment_and_build_identity"] = check(
        "failed", "Docker daemon is unavailable.", "artifact-docker-diagnostic",
    )
    return value


def partial_manifest(status="draft"):
    value = deepcopy(VALID["case-manifest"])
    for key in ("vulnerability_id", "source_ids", "environment_id", "builds", "executions", "replay"):
        del value[key]
    value["status"] = status
    value["artifact_ids"] = ["artifact-docker-diagnostic"]
    value["failure"] = {
        "stage": "build",
        "class": "configuration_failure",
        "summary": "Docker preflight failed before any build command ran.",
        "evidence": [artifact_ref("artifact-docker-diagnostic")],
    }
    if status in ("draft", "buildable"):
        del value["verification_result_id"]
        value["provenance"]["inputs"] = ["artifact-docker-diagnostic"]
    return value


def non_success(verdict, check_name, failure_class):
    value = deepcopy(VALID["verification-result"])
    value["verdict"] = verdict
    value["failure_class"] = failure_class
    value["checks"][check_name] = check(
        "failed", "Observed fixture condition does not satisfy the check.",
        "artifact-comparison-observation",
    )
    value["rationale"] = "Synthetic observations support this non-success verdict."
    return value
