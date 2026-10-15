"""Failure-conditioned, evidence-aware strategy memory.

This memory proposes repair strategies to the planner. It never assigns a
vulnerability verdict and it never stores arbitrary exploit payloads.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .models import (
    FailureClass,
    ReproductionGraph,
    Skill,
    SkillApplication,
    SkillKey,
    SkillStatus,
    TypedFeedback,
)


def _default_skills() -> list[Skill]:
    common = ["no arbitrary shell", "no network expansion", "no secrets", "no host paths"]
    return [
        Skill(
            skill_id="skill-fixture-state",
            name="initialize-controlled-fixture-state",
            description=(
                "Establish a bounded fixture state before invoking the registered entrypoint."
            ),
            key=SkillKey(
                failure_class=FailureClass.REACHABILITY, missing_transition="node-precondition"
            ),
            allowed_operators=["establish_fixture_state", "reset_environment"],
            expected_transitions=["node-precondition", "node-patch-slice-reached"],
            forbidden_effects=common,
            provenance={"source": "built-in-safe-template", "review": "static-policy"},
        ),
        Skill(
            skill_id="skill-entrypoint-harness",
            name="repair-registered-entrypoint-harness",
            description=(
                "Repair only the typed harness/entrypoint adapter while preserving "
                "the candidate bytes."
            ),
            key=SkillKey(failure_class=FailureClass.HARNESS, missing_transition="node-entrypoint"),
            allowed_operators=["invoke_entrypoint", "observe_trace"],
            expected_transitions=["node-entrypoint", "node-patch-slice-reached"],
            forbidden_effects=common,
            provenance={"source": "built-in-safe-template", "review": "static-policy"},
        ),
        Skill(
            skill_id="skill-trace-observation",
            name="add-source-aligned-observation",
            description=(
                "Add bounded trace observation for the patch-relevant slice without "
                "changing target semantics."
            ),
            key=SkillKey(
                failure_class=FailureClass.ORACLE, missing_transition="node-semantic-transition"
            ),
            allowed_operators=["observe_trace", "assert_state"],
            expected_transitions=["node-patch-slice-reached", "node-semantic-transition"],
            forbidden_effects=common,
            provenance={"source": "built-in-safe-template", "review": "static-policy"},
        ),
        Skill(
            skill_id="skill-runtime-config",
            name="repair-local-runtime-configuration",
            description=(
                "Repair a declared local service/configuration prerequisite without "
                "widening network policy."
            ),
            key=SkillKey(failure_class=FailureClass.STARTUP, missing_transition="node-entrypoint"),
            allowed_operators=["establish_fixture_state", "reset_environment"],
            expected_transitions=["node-entrypoint"],
            forbidden_effects=common + ["Internet egress", "credential access"],
            provenance={"source": "built-in-safe-template", "review": "static-policy"},
        ),
        Skill(
            skill_id="skill-dependency-lock",
            name="repair-pinned-dependency-resolution",
            description=(
                "Use the recorded lockfile and checksum policy to repair a deterministic build."
            ),
            key=SkillKey(
                failure_class=FailureClass.DEPENDENCY, missing_transition="node-entrypoint"
            ),
            allowed_operators=["reset_environment"],
            expected_transitions=["node-entrypoint"],
            forbidden_effects=common,
            provenance={"source": "built-in-safe-template", "review": "static-policy"},
        ),
    ]


class SkillMemory:
    """Small JSON-backed memory suitable for a local research prototype.

    The storage format is intentionally boring and inspectable. A production
    deployment may add an embedding index, but retrieval must remain filtered by
    typed failure and policy constraints first.
    """

    def __init__(self, path: str | Path, *, seed_defaults: bool = True):
        self.path = Path(path).expanduser()
        self.skills: dict[str, Skill] = {}
        self.applications: list[SkillApplication] = []
        if seed_defaults:
            for skill in _default_skills():
                self.skills[skill.skill_id] = skill
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(payload, dict):
            return
        for item in payload.get("skills", []):
            try:
                skill = Skill.model_validate(item)
            except Exception:
                continue
            self.skills[skill.skill_id] = skill
        for item in payload.get("applications", []):
            try:
                self.applications.append(SkillApplication.model_validate(item))
            except Exception:
                continue

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "skills": [
                item.model_dump(mode="json")
                for item in sorted(self.skills.values(), key=lambda x: x.skill_id)
            ],
            "applications": [item.model_dump(mode="json") for item in self.applications],
        }
        fd, temporary = tempfile.mkstemp(
            prefix=".skill-memory-", dir=str(self.path.parent), text=True
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, sort_keys=True, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _match(skill: Skill, key: SkillKey) -> float:
        score = 0.0
        fields = ("language", "framework", "build_system", "vulnerability_class", "observable")
        for field in fields:
            left = getattr(skill.key, field)
            right = getattr(key, field)
            if right and right != "unknown" and left in (right, "unknown"):
                score += 1.0 if left == right else 0.25
        if skill.key.failure_class == key.failure_class:
            score += 3.0
        if key.missing_transition and key.missing_transition != "unknown":
            if skill.key.missing_transition == key.missing_transition:
                score += 2.0
            elif key.missing_transition in skill.expected_transitions:
                score += 1.0
        score += min(skill.verified_applications, 5) * 0.4
        score -= min(skill.average_cost, 10) * 0.05
        if skill.status == SkillStatus.RETIRED:
            return -1.0
        return score

    def retrieve(self, key: SkillKey, *, limit: int = 5) -> list[Skill]:
        ranked = sorted(self.skills.values(), key=lambda item: self._match(item, key), reverse=True)
        return [item for item in ranked if self._match(item, key) > 0][:limit]

    def retrieve_for_feedback(
        self,
        key: SkillKey,
        feedback: TypedFeedback,
        graph: ReproductionGraph,
        *,
        limit: int = 5,
    ) -> list[Skill]:
        """Retrieve by failure + missing transition + graph goal, not text similarity alone."""

        candidates = self.retrieve(key, limit=max(limit * 2, 5))
        goal_ids = set(graph.goal_node_ids)
        return [
            skill
            for skill in candidates
            if set(skill.allowed_operators).intersection(feedback.allowed_repairs)
            and not set(skill.allowed_operators).intersection(feedback.forbidden_repairs)
            and (
                feedback.missing_transition in skill.expected_transitions
                or feedback.missing_transition in goal_ids
                or not feedback.missing_transition
            )
        ][:limit]

    def record_application(self, application: SkillApplication) -> None:
        self.applications.append(application)
        skill = self.skills.get(application.skill_id)
        if skill is None:
            return
        skill.applications += 1
        if application.outcome == "verified" and application.counterfactual_verified:
            skill.verified_applications += 1
        elif application.outcome == "failed":
            skill.failed_applications += 1
        # Promotion requires evidence from at least two verified applications
        # so one lucky trajectory cannot become a reusable strategy.
        if skill.verified_applications >= 2:
            skill.status = SkillStatus.PROMOTED
        elif skill.verified_applications >= 1:
            skill.status = SkillStatus.VALIDATED

    def summary(self) -> dict[str, Any]:
        return {
            "skill_count": len(self.skills),
            "application_count": len(self.applications),
            "promoted_skill_ids": [
                skill.skill_id
                for skill in self.skills.values()
                if skill.status == SkillStatus.PROMOTED
            ],
        }
