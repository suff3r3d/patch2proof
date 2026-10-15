"""Constrained Docker worker.

The worker is deliberately boring: it accepts validated specs, uses fixed
argument arrays, and defaults to dry-run. A production implementation should
run this worker in a separate disposable VM or rootless BuildKit environment.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from ..models import DockerSpec, ExecutionPolicy, ImageArtifact, SafePoC, ValidationResult
from .repo import ensure_within_root


def safe_slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return result[:80] or "case"


class DockerWorker:
    def __init__(self, policy: ExecutionPolicy, artifact_dir: Path, dry_run: bool = True):
        self.policy = policy
        self.artifact_dir = artifact_dir.resolve()
        self.dry_run = dry_run

    def validate_spec(self, spec: DockerSpec) -> None:
        context = ensure_within_root(spec.context_dir, self.policy.allowed_repo_root)
        for role_context in (spec.vulnerable_context_dir, spec.fixed_context_dir):
            if role_context:
                self._ensure_context(role_context)
        dockerfile = Path(spec.dockerfile_path).expanduser().resolve()
        trusted_template_root = Path("templates").resolve()
        try:
            dockerfile_is_trusted_template = os.path.commonpath(
                (str(dockerfile), str(trusted_template_root))
            ) == str(trusted_template_root)
        except ValueError:
            dockerfile_is_trusted_template = False
        if not dockerfile_is_trusted_template:
            dockerfile = ensure_within_root(dockerfile, context)
        if not context.exists():
            raise ValueError(f"Docker context does not exist: {context}")
        if not dockerfile.exists():
            raise ValueError(f"Dockerfile does not exist: {dockerfile}")
        if spec.base_image and not any(
            spec.base_image.startswith(prefix) for prefix in self.policy.allowed_base_images
        ):
            raise ValueError(f"Base image is not allowlisted: {spec.base_image}")
        if (
            spec.runtime_network.value != self.policy.network.value
            and self.policy.network.value != "none"
        ):
            raise ValueError("Runtime network policy is broader than case policy")

    def build_pair(self, spec: DockerSpec) -> list[ImageArtifact]:
        self.validate_spec(spec)
        images: list[ImageArtifact] = []
        for role, ref in (("vulnerable", spec.vulnerable_ref), ("fixed", spec.fixed_ref)):
            role = cast(Literal["vulnerable", "fixed"], role)
            tag = f"patch2proof/{safe_slug(spec.case_id)}:{role}"
            if self.dry_run or not self.policy.allow_docker_build:
                images.append(
                    ImageArtifact(
                        role=role,
                        tag=tag,
                        dockerfile=str(Path(spec.dockerfile_path).resolve()),
                        built=False,
                        provenance={"mode": "dry_run", "source_ref": ref},
                    )
                )
                continue
            images.append(self._build_one(spec, role, ref, tag))
        return images

    def _build_one(
        self, spec: DockerSpec, role: Literal["vulnerable", "fixed"], ref: str, tag: str
    ) -> ImageArtifact:
        # The source checkout for each ref should be materialized into a
        # per-role context by a higher-level adapter. This worker never checks
        # out arbitrary refs or executes a shell string.
        role_context = (
            spec.vulnerable_context_dir if role == "vulnerable" else spec.fixed_context_dir
        )
        context = self._ensure_context(role_context or spec.context_dir)
        dockerfile = Path(spec.dockerfile_path).expanduser().resolve()
        trusted_template_root = Path("templates").resolve()
        try:
            trusted_template = os.path.commonpath(
                (str(dockerfile), str(trusted_template_root))
            ) == str(trusted_template_root)
        except ValueError:
            trusted_template = False
        if not trusted_template:
            dockerfile = ensure_within_root(dockerfile, spec.context_dir)
        command = [
            "docker",
            "build",
            "--pull=false",
            "--network=none",
            "--tag",
            tag,
            "--file",
            str(dockerfile),
            str(context),
        ]
        start = time.monotonic()
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.policy.timeout_seconds,
        )
        log = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode != 0:
            raise RuntimeError(f"Docker build failed for {role}: {log[-4000:]}")
        digest = self._inspect_digest(tag)
        return ImageArtifact(
            role=role,
            tag=tag,
            digest=digest,
            dockerfile=str(dockerfile),
            build_log=log[-4000:],
            built=True,
            provenance={"source_ref": ref, "duration_seconds": time.monotonic() - start},
        )

    def _ensure_context(self, path: str | Path) -> Path:
        """Allow source contexts or the separate, scoped artifact workspace."""
        try:
            return ensure_within_root(path, self.policy.allowed_repo_root)
        except ValueError:
            return ensure_within_root(path, self.policy.allowed_artifact_root)

    @staticmethod
    def _inspect_digest(tag: str) -> str | None:
        result = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", tag],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip() or None if result.returncode == 0 else None

    def run_differential(
        self,
        images: list[ImageArtifact],
        poc: SafePoC,
        registered_test_id: str,
    ) -> ValidationResult:
        validate_safe_poc(poc)
        if self.dry_run or not self.policy.allow_poc_execution:
            return ValidationResult(
                status="planned",
                logs=[f"Would run registered test {registered_test_id}"],
            )
        if len(images) != 2 or not all(image.built for image in images):
            return ValidationResult(
                status="error", logs=["Both images must be built before execution"]
            )
        # The actual test adapter is intentionally registered by test ID. This
        # prevents the LLM from supplying an arbitrary command line. The
        # built-in simulation is useful for CI contract tests only; it cannot
        # produce a confirmed verdict.
        from .test_adapters import run_registered_differential

        return run_registered_differential(registered_test_id, poc, self.artifact_dir)


def validate_safe_poc(poc: SafePoC) -> None:
    blocked_words = {
        "reverse shell",
        "reverse_shell",
        "persistence",
        "host filesystem",
        "host_filesystem",
        "credential",
        "secret",
        "curl",
        "wget",
        "arbitrary shell",
        "command injection",
    }
    action_text = " ".join(
        [
            poc.objective,
            *(action.op for action in poc.actions),
            *(action.target for action in poc.actions),
            *(action.value for action in poc.actions),
        ]
    ).lower()
    if any(word in action_text for word in blocked_words):
        raise ValueError("SafePoC action contains a forbidden effect")

    def safe_virtual_target(target: str, prefix: str) -> bool:
        return target.startswith(prefix) and ".." not in PurePosixPath(target).parts

    for action in poc.actions:
        if action.op == "write_marker" and not safe_virtual_target(action.target, "/proof/"):
            raise ValueError("write_marker may only target /proof/")
        if action.op == "read_canary" and not safe_virtual_target(action.target, "/proof/fixture/"):
            raise ValueError("read_canary may only read /proof/fixture/")
        if action.op == "establish_fixture_state" and not safe_virtual_target(
            action.target, "/proof/fixture/"
        ):
            raise ValueError("establish_fixture_state may only target /proof/fixture/")
        if action.op == "invoke_entrypoint" and not action.target.startswith("registered://"):
            raise ValueError("invoke_entrypoint must use a registered:// adapter")
        if action.op == "observe_trace" and not safe_virtual_target(action.target, "/proof/trace/"):
            raise ValueError("observe_trace may only target /proof/trace/")
        if action.op == "assert_log" and not safe_virtual_target(action.target, "/proof/logs/"):
            raise ValueError("assert_log may only target /proof/logs/")
        if action.op == "observe_exit" and not safe_virtual_target(action.target, "/proof/"):
            raise ValueError("observe_exit may only target /proof/")
        if action.op == "assert_state" and not safe_virtual_target(action.target, "/proof/"):
            raise ValueError("assert_state may only target /proof/")
        if action.op == "http_mock_request" and not action.target.startswith("mock://"):
            raise ValueError("http_mock_request may only target mock://")
        if action.op == "reset_environment" and not action.target.startswith("snapshot://"):
            raise ValueError("reset_environment must use a snapshot:// target")


def deterministic_artifact_hash(value: Any) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()
