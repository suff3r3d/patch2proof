"""Small, explicit records demonstrating the current schema contracts."""

from copy import deepcopy


SHA = "0" * 64
IMAGE = "sha256:" + "1" * 64
CASE = "case-001"


def artifact_ref(identifier):
    return {"id": identifier, "sha256": SHA}


def provenance(*inputs):
    value = {
        "created_at": "2026-09-17T00:00:00Z",
        "created_by": "schema-fixture",
    }
    if inputs:
        value["inputs"] = list(inputs)
    return value


def envelope(schema, identifier, *inputs):
    return {
        "schema": schema,
        "id": identifier,
        "case_id": CASE,
        "provenance": provenance(*inputs),
    }


def verification_check(summary, evidence_id="artifact-sanitizer"):
    return {
        "status": "passed",
        "summary": summary,
        "evidence": [artifact_ref(evidence_id)],
    }


VALID = {
    "source-record": {
        **envelope("source-record", "source-advisory"),
        "source_type": "advisory",
        "url": "https://example.invalid/advisory",
        "retrieved_at": "2026-09-17T00:00:00Z",
        "retrieval_status": "succeeded",
        "content": artifact_ref("artifact-advisory"),
    },
    "artifact-record": {
        **envelope("artifact-record", "artifact-trigger"),
        "kind": "trigger",
        "available": True,
        "path": "artifacts/trigger.bin",
        "sha256": SHA,
        "size_bytes": 4,
    },
    "vulnerability-record": {
        **envelope("vulnerability-record", "vulnerability-001", "source-advisory"),
        "identifiers": ["CVE-2026-0001"],
        "title": "Fixture vulnerability",
        "summary": "A safe synthetic fixture used to validate the schema.",
        "sources": ["source-advisory"],
        "revision_status": "resolved",
        "claims": [{
            "field": "/revisions/vulnerable",
            "raw_value": "affected before the fixing commit",
            "normalized_value": "a" * 40,
            "source_id": "source-advisory",
            "classification": "confirmed_fact",
            "confidence": "high",
            "evidence": [artifact_ref("artifact-advisory")],
            "method": "Resolved the advisory repository reference to an immutable commit.",
        }],
        "repository": {"url": "https://example.invalid/project.git"},
        "revisions": {"vulnerable": "a" * 40, "patched": "b" * 40},
        "patch": {
            "commits": ["b" * 40],
            "changed_files": ["src/parser.c"],
            "changed_functions": ["parse_record"],
            "evidence": [artifact_ref("artifact-patch")],
            "static_context": {
                "code_locations": [{"file": "src/parser.c", "function": "parse_record", "line": 42}],
                "call_context": [{"caller": "process_input", "callee": "parse_record"}],
                "reachability": {
                    "status": "confirmed",
                    "summary": "The sanitizer trace reaches parse_record.",
                    "evidence": [artifact_ref("artifact-sanitizer")],
                },
            },
        },
    },
    "environment-spec": {
        **envelope("environment-spec", "environment-paired"),
        "platform": {"os": "linux", "arch": "x86_64"},
        "isolation": {"type": "docker", "image_digest": IMAGE},
        "toolchain": {"compiler": "clang 18", "build_system": "cmake 3.30"},
        "dependencies": {"policy": "locked"},
        "build": {
            "configure_commands": [["cmake", "-S", ".", "-B", "build"]],
            "commands": [["cmake", "--build", "build"]],
            "expected_outputs": ["build/fixture"],
        },
        "network": {"acquisition": True, "build": False, "execution": False},
        "limits": {
            "timeout_seconds": 60,
            "memory_mb": 512,
            "processes": 32,
            "disk_mb": 1024,
            "output_bytes": 1048576,
        },
        "instrumentation": [{"kind": "asan", "availability": "required"}],
    },
    "build-record": {
        **envelope("build-record", "build-vulnerable", "environment-paired"),
        "role": "vulnerable",
        "environment_id": "environment-paired",
        "revision": "a" * 40,
        "source_tree_sha256": "2" * 64,
        "status": "succeeded",
        "started_at": "2026-09-17T00:01:00Z",
        "completed_at": "2026-09-17T00:02:00Z",
        "commands": [{
            "command": ["cmake", "--build", "build"],
            "exit_code": 0,
            "stdout": artifact_ref("artifact-build-stdout"),
            "stderr": artifact_ref("artifact-build-stderr"),
        }],
        "outputs": [artifact_ref("artifact-vulnerable-binary")],
        "observed_toolchain": {"compiler": "clang 18.1.8", "build_system": "cmake 3.30.2"},
        "dependency_resolution": {
            "status": "resolved",
            "manager": "system",
            "manager_version": "fixture-1",
            "inventory": artifact_ref("artifact-dependency-inventory"),
            "checksums_verified": True,
        },
    },
    "execution-record": {
        **envelope("execution-record", "execution-vulnerable", "build-vulnerable"),
        "role": "vulnerable",
        "comparison_group": "candidate-001",
        "build_id": "build-vulnerable",
        "executable": artifact_ref("artifact-vulnerable-binary"),
        "input": artifact_ref("artifact-trigger"),
        "input_role": "candidate",
        "command": ["build/fixture", "artifacts/trigger.bin"],
        "working_directory": "runtime",
        "environment": {},
        "limits": {
            "timeout_seconds": 10,
            "memory_mb": 256,
            "processes": 8,
            "disk_mb": 128,
            "output_bytes": 65536,
        },
        "status": "completed",
        "started_at": "2026-09-17T00:03:00Z",
        "completed_at": "2026-09-17T00:03:01Z",
        "stdout": artifact_ref("artifact-run-stdout"),
        "stderr": artifact_ref("artifact-run-stderr"),
        "process": {"signal": "SIGABRT"},
        "sanitizer_report": artifact_ref("artifact-sanitizer"),
    },
    "verification-result": {
        **envelope(
            "verification-result", "verification-001",
            "execution-vulnerable", "execution-patched", "execution-control",
        ),
        "expectations": {
            "target_signal": "AddressSanitizer reports heap-buffer-overflow",
            "reachability": "The trace contains parse_record",
            "patched_behavior": "The process rejects the input without the target signal",
        },
        "executions": {
            "vulnerable": "execution-vulnerable",
            "patched": "execution-patched",
            "negative_controls": ["execution-control"],
        },
        "checks": {
            "environment_and_build_identity": verification_check("Environment and build identity valid"),
            "same_candidate": verification_check("Same candidate used"),
            "vulnerable_target_signal": verification_check("Vulnerable target signal present"),
            "reachability": verification_check("Relevant code reached"),
            "patched_behavior": verification_check("Patched behavior safe"),
            "negative_controls": verification_check("Negative controls passed"),
            "patch_consistency": verification_check("Observation consistent with patch"),
        },
        "verdict": "VERIFIED",
        "rationale": "Paired execution and the negative control satisfy the expected checks.",
        "evidence": [artifact_ref("artifact-sanitizer")],
        "oracle": {
            "name": "fixture-oracle",
            "version": "0.2.0",
            "adapter": {
                "name": "synthetic-parser",
                "version": "1.0.0",
                "implementation": artifact_ref("artifact-adapter-source"),
            },
            "case_definition": artifact_ref("artifact-reviewed-case"),
        },
    },
    "case-manifest": {
        **envelope("case-manifest", "manifest-001", "verification-001"),
        "package_version": "0.1.0",
        "status": "verified",
        "vulnerability_id": "vulnerability-001",
        "source_ids": ["source-advisory"],
        "environment_id": "environment-paired",
        "builds": {"vulnerable": "build-vulnerable", "patched": "build-patched"},
        "artifact_ids": [
            "artifact-trigger", "artifact-sanitizer",
            "artifact-adapter-source", "artifact-reviewed-case",
        ],
        "executions": {
            "vulnerable": "execution-vulnerable",
            "patched": "execution-patched",
            "negative_controls": ["execution-control"],
        },
        "verification_result_id": "verification-001",
        "replay": {
            "entry_point": artifact_ref("artifact-replay-script"),
            "command": ["scripts/replay.sh"],
            "working_directory": ".",
        },
    },
}


def invalid_fixtures():
    fixtures = {}

    value = deepcopy(VALID["source-record"])
    del value["content"]
    fixtures["source-record"] = value

    value = deepcopy(VALID["artifact-record"])
    del value["sha256"]
    fixtures["artifact-record"] = value

    value = deepcopy(VALID["vulnerability-record"])
    del value["revisions"]
    fixtures["vulnerability-record"] = value

    value = deepcopy(VALID["environment-spec"])
    value["network"]["public_target"] = True
    fixtures["environment-spec"] = value

    value = deepcopy(VALID["build-record"])
    del value["outputs"]
    fixtures["build-record"] = value

    value = deepcopy(VALID["execution-record"])
    value["status"] = "timed_out"
    del value["process"]
    fixtures["execution-record"] = value

    value = deepcopy(VALID["verification-result"])
    value["verdict"] = "INCONCLUSIVE"
    fixtures["verification-result"] = value

    value = deepcopy(VALID["case-manifest"])
    del value["replay"]
    fixtures["case-manifest"] = value

    return fixtures
