"""Typed contracts shared by graph nodes and execution workers.

The most important design rule is that LLM output must be converted into one
of these contracts before it can influence a tool. Free-form shell commands
are deliberately absent from the public state model.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Verdict(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    NOT_EXECUTED = "not_executed"


class FailureClass(str, Enum):
    """Typed failure categories used to route repair instead of guessing."""

    METADATA = "metadata_failure"
    REVISION = "revision_failure"
    DEPENDENCY = "dependency_failure"
    TOOLCHAIN = "toolchain_failure"
    CONFIGURATION = "configuration_failure"
    BUILD = "build_failure"
    STARTUP = "startup_failure"
    HARNESS = "harness_failure"
    REACHABILITY = "reachability_failure"
    HYPOTHESIS = "hypothesis_failure"
    ORACLE = "oracle_failure"
    CONTROL = "control_failure"
    RESOURCE = "resource_failure"
    POLICY = "policy_failure"


class GraphNodeKind(str, Enum):
    PATCH_HUNK = "patch_hunk"
    SYMBOL = "symbol"
    ENTRYPOINT = "entrypoint"
    PRECONDITION = "precondition"
    STATE = "state"
    ACTION = "action"
    OBSERVATION = "observation"
    ARTIFACT = "artifact"
    REVISION = "revision"
    CONTROL = "control"


class GraphEdgeKind(str, Enum):
    MODIFIES = "modifies"
    CALLS = "calls"
    FLOWS_TO = "flows_to"
    REQUIRES = "requires"
    REACHES = "reaches"
    TRANSITIONS = "transitions"
    OBSERVED_BY = "observed_by"
    DERIVED_FROM = "derived_from"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    ABSENT_ON_FIXED = "absent_on_fixed"


class GraphStatus(str, Enum):
    HYPOTHESIZED = "hypothesized"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    UNOBSERVED = "unobserved"


class AttemptStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"


class SkillStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PROMOTED = "promoted"
    RETIRED = "retired"


class NetworkPolicy(str, Enum):
    NONE = "none"
    MOCK_ONLY = "mock_only"


class ReasoningMode(str, Enum):
    """How the agent creates decisions that can influence the workflow.

    ``REQUIRED`` is deliberately not a provider.  It is the fail-closed
    default: a case must explicitly select a real model provider or an
    explicitly authorised offline test mode.
    """

    REQUIRED = "required"
    OPENAI = "openai"
    OLLAMA = "ollama"
    HEURISTIC = "heuristic"


class ExecutionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorized: bool = False
    network: NetworkPolicy = NetworkPolicy.NONE
    allow_docker_build: bool = False
    allow_poc_execution: bool = False
    allowed_repo_root: str = "."
    allowed_artifact_root: str = "artifacts"
    allowed_base_images: list[str] = Field(
        default_factory=lambda: ["python:", "eclipse-temurin:", "node:"]
    )
    max_memory_mb: int = Field(default=512, ge=128, le=4096)
    max_cpus: float = Field(default=1.0, gt=0, le=4)
    max_pids: int = Field(default=128, ge=16, le=2048)
    timeout_seconds: int = Field(default=60, ge=5, le=900)
    skill_memory_path: str = "artifacts/skill-memory.json"
    max_repair_attempts: int = Field(default=4, ge=0, le=20)
    reasoning_mode: ReasoningMode = ReasoningMode.REQUIRED
    reasoning_model: str | None = None
    reasoning_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning_effort: Literal["low", "medium", "high"] | None = "medium"
    allow_heuristic_reasoning: bool = False
    source_call_depth: int = Field(default=3, ge=1, le=5)
    source_file_limit: int = Field(default=2000, ge=10, le=10000)
    source_file_max_bytes: int = Field(default=1_000_000, ge=10_000, le=10_000_000)
    source_context_limit_chars: int = Field(default=50000, ge=4000, le=250000)
    source_tool_call_limit: int = Field(default=6, ge=0, le=20)

    @model_validator(mode="after")
    def reject_implicit_heuristic_mode(self) -> "ExecutionPolicy":
        if self.reasoning_mode == ReasoningMode.HEURISTIC and not self.allow_heuristic_reasoning:
            raise ValueError(
                "reasoning_mode=heuristic requires allow_heuristic_reasoning=true; "
                "heuristic reasoning is test-only and never a production default"
            )
        return self


class CaseManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,80}$")
    title: str
    repository_path: str = "."
    source_mode: Literal["git", "fixture"] = "git"
    vulnerable_ref: str = "HEAD"
    fixed_ref: str = "HEAD"
    language: Literal["python", "java", "php", "node", "go", "cpp", "unknown"] = "unknown"
    build_system: Literal[
        "pip", "poetry", "maven", "gradle", "npm", "composer", "go", "cmake", "custom"
    ] = "custom"
    advisory: str = ""
    commit_message: str = ""
    dockerfile: str | None = None
    registered_test_id: str = "fixture_noop"
    output_dir: str = "artifacts"
    policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    tags: list[str] = Field(default_factory=list)

    @field_validator("repository_path", "output_dir")
    @classmethod
    def non_empty_path(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("path cannot be empty")
        return value


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    kind: Literal["diff", "source", "runtime", "docker", "test", "advisory", "review"]
    observation: str
    path: str | None = None
    symbol: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    version: str | None = None
    commit: str | None = None
    content_hash: str | None = None
    artifact_path: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    title: str
    vulnerability_class: str
    observation: str
    preconditions: list[str] = Field(default_factory=list)
    affected_paths: list[str] = Field(default_factory=list)
    sink: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.35, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class ReasoningCandidate(BaseModel):
    """One evidence-linked hypothesis considered by the reasoning model."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    title: str
    vulnerability_class: str
    observation: str
    preconditions: list[str] = Field(default_factory=list)
    affected_paths: list[str] = Field(default_factory=list)
    sink: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    disconfirmation_test: str
    confidence: float = Field(default=0.35, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class AgentReasoning(BaseModel):
    """Auditable decision record, not an unrestricted chain-of-thought dump.

    The record stores evidence links, alternatives, uncertainty and the next
    bounded transition. It intentionally does not store hidden/private model
    reasoning or executable instructions.
    """

    model_config = ConfigDict(extra="forbid")

    reasoning_id: str
    stage: Literal["hypothesis", "safe_poc_plan", "repair"]
    mode: ReasoningMode
    provider: str
    model: str | None = None
    reasoning_effort: str | None = None
    prompt_version: str
    input_sha256: str
    output_sha256: str
    candidates: list[ReasoningCandidate] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    observations: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    missing_transitions: list[str] = Field(default_factory=list)
    next_action: str
    decision_rationale: str
    uncertainty: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class SourceQuery(BaseModel):
    """Read-only source query requested by the reasoning model."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["read_symbol", "find_callers", "find_callees", "read_test"]
    symbol: str | None = Field(default=None, max_length=240)
    path: str | None = Field(default=None, max_length=500)
    revision: Literal["vulnerable", "fixed"] = "vulnerable"
    depth: int = Field(default=1, ge=1, le=3)


class SourceContextBundle(BaseModel):
    """Versioned source slices and static call-path candidates for one patch."""

    model_config = ConfigDict(extra="forbid")

    patch_sha256: str
    patch_complete: bool
    hunk_count: int = Field(ge=0)
    mapped_hunk_count: int = Field(ge=0)
    status: Literal["sufficient", "insufficient"]
    changed_symbols: list[dict[str, Any]] = Field(default_factory=list)
    caller_paths: list[dict[str, Any]] = Field(default_factory=list)
    callee_paths: list[dict[str, Any]] = Field(default_factory=list)
    callee_candidates: list[dict[str, Any]] = Field(default_factory=list)
    source_slices: list[dict[str, Any]] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    parser_coverage: dict[str, int] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)


class SafePoCPlan(BaseModel):
    """Typed plan proposed by the reasoning model and compiled by SafePoC."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    hypothesis_id: str
    graph_id: str
    target_edge_ids: list[str] = Field(default_factory=list)
    objective: str
    observation_op: Literal[
        "read_canary",
        "write_marker",
        "http_mock_request",
        "assert_log",
        "observe_exit",
        "observe_trace",
        "assert_state",
    ]
    target: str
    value: str = ""
    expected: str
    oracle: Literal[
        "canary_content",
        "marker_file",
        "mock_hit",
        "log_record",
        "exit_status",
    ]
    vulnerable_expectation: dict[str, Any]
    fixed_expectation: dict[str, Any]
    expected_transitions: list[str] = Field(default_factory=list)
    forbidden_effects: list[str] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(default=0.35, ge=0, le=1)
    reasoning_id: str | None = None


class RepairDecision(BaseModel):
    """Model-ranked repair choices constrained by deterministic feedback."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    reasoning_id: str
    mode: ReasoningMode
    provider: str
    model: str | None = None
    reasoning_effort: str | None = None
    prompt_version: str
    failure_class: FailureClass
    missing_transition: str
    ranked_repairs: list[str] = Field(default_factory=list)
    selected_repair: str
    expected_observation: str
    reject_if: list[str] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(default=0.35, ge=0, le=1)


class VulnerabilityContract(BaseModel):
    """Executable, evidence-backed contract for one reproduction hypothesis."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    case_id: str
    hypothesis_id: str
    preconditions: list[str] = Field(default_factory=list)
    required_entrypoints: list[str] = Field(default_factory=list)
    semantic_transition: str
    safe_observables: list[str] = Field(default_factory=list)
    fixed_behavior: list[str] = Field(default_factory=list)
    negative_controls: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["hypothesis", "reviewed", "rejected"] = "hypothesis"


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    kind: GraphNodeKind
    label: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    status: GraphStatus = GraphStatus.UNOBSERVED
    confidence: float = Field(default=0.35, ge=0, le=1)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    source: str
    target: str
    kind: GraphEdgeKind
    label: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    status: GraphStatus = GraphStatus.HYPOTHESIZED
    confidence: float = Field(default=0.35, ge=0, le=1)
    cost: float = Field(default=1.0, ge=0)
    policy_risk: float = Field(default=0.0, ge=0, le=1)


class ReproductionGraph(BaseModel):
    """Case-local multi-layer directed graph used for planning and proof."""

    model_config = ConfigDict(extra="forbid")

    graph_id: str
    case_id: str
    hypothesis_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    goal_node_ids: list[str] = Field(default_factory=list)
    current_node_ids: list[str] = Field(default_factory=list)
    uncovered_edge_ids: list[str] = Field(default_factory=list)
    revision: int = Field(default=0, ge=0)


class CoverageVector(BaseModel):
    """Six independent requirements for a source-grounded safe reproduction."""

    model_config = ConfigDict(extra="forbid")

    static_reachability: bool = False
    dynamic_reachability: bool = False
    semantic_transition: bool = False
    counterfactual_separation: bool = False
    repeatable: bool = False
    source_grounded: bool = False

    @property
    def complete(self) -> bool:
        return all(
            (
                self.static_reachability,
                self.dynamic_reachability,
                self.semantic_transition,
                self.counterfactual_separation,
                self.repeatable,
                self.source_grounded,
            )
        )


class SkillKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = "unknown"
    framework: str = "unknown"
    build_system: str = "custom"
    vulnerability_class: str = "unknown"
    failure_class: FailureClass
    missing_transition: str = "unknown"
    observable: str = "unknown"


class Skill(BaseModel):
    """Reusable safe strategy, not an exploit or an oracle verdict."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str
    name: str
    description: str
    key: SkillKey
    allowed_operators: list[str] = Field(default_factory=list)
    expected_transitions: list[str] = Field(default_factory=list)
    forbidden_effects: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    status: SkillStatus = SkillStatus.CANDIDATE
    applications: int = Field(default=0, ge=0)
    verified_applications: int = Field(default=0, ge=0)
    failed_applications: int = Field(default=0, ge=0)
    average_cost: float = Field(default=1.0, ge=0)
    provenance: dict[str, Any] = Field(default_factory=dict)


class SkillApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str
    skill_id: str
    case_id: str
    attempt_id: str
    outcome: Literal["verified", "failed", "inconclusive", "blocked"]
    transitions_gained: list[str] = Field(default_factory=list)
    failure_class: FailureClass | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    counterfactual_verified: bool = False
    notes: str = ""


class TypedFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    attempt_id: str
    failure_class: FailureClass
    observed_nodes: list[str] = Field(default_factory=list)
    observed_edges: list[str] = Field(default_factory=list)
    missing_transition: str = "unknown"
    allowed_repairs: list[str] = Field(default_factory=list)
    forbidden_repairs: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class AttemptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    case_id: str
    hypothesis_id: str
    graph_id: str
    parent_attempt_id: str | None = None
    selected_skill_id: str | None = None
    target_edge_ids: list[str] = Field(default_factory=list)
    action_ids: list[str] = Field(default_factory=list)
    status: AttemptStatus = AttemptStatus.PLANNED
    failure_class: FailureClass | None = None
    before_graph_hash: str = ""
    after_graph_hash: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    cost: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class DockerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    language: str
    context_dir: str
    vulnerable_context_dir: str | None = None
    fixed_context_dir: str | None = None
    dockerfile_path: str
    vulnerable_ref: str
    fixed_ref: str
    build_network: NetworkPolicy = NetworkPolicy.NONE
    runtime_network: NetworkPolicy = NetworkPolicy.NONE
    base_image: str
    entrypoint: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    exposed_ports: list[int] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)


class SafeAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    op: Literal[
        "read_canary",
        "write_marker",
        "http_mock_request",
        "assert_log",
        "observe_exit",
        "establish_fixture_state",
        "invoke_entrypoint",
        "observe_trace",
        "assert_state",
        "reset_environment",
    ]
    target: str
    value: str = ""
    expected: str = ""
    transition_ids: list[str] = Field(default_factory=list)


class SafePoC(BaseModel):
    model_config = ConfigDict(extra="forbid")

    poc_id: str
    hypothesis_id: str
    objective: str
    actions: list[SafeAction] = Field(min_length=1)
    oracle: Literal["canary_content", "marker_file", "mock_hit", "log_record", "exit_status"]
    vulnerable_expectation: dict[str, Any]
    fixed_expectation: dict[str, Any]
    allowed_effects: list[str] = Field(default_factory=list)
    forbidden_effects: list[str] = Field(default_factory=list)
    generator: str = "patch2proof.safe_poc.unset"
    reviewed: bool = False
    graph_id: str | None = None
    plan_id: str | None = None
    entrypoint: str | None = None
    repair_budget: int = Field(default=3, ge=0, le=20)


class ImageArtifact(BaseModel):
    role: Literal["vulnerable", "fixed"]
    tag: str
    digest: str | None = None
    dockerfile: str
    build_log: str | None = None
    built: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    status: Literal["passed", "failed", "planned", "skipped", "error"]
    vulnerable_observation: dict[str, Any] = Field(default_factory=dict)
    fixed_observation: dict[str, Any] = Field(default_factory=dict)
    oracle_match: bool = False
    differential: bool = False
    violations: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    adapter_id: str | None = None
    simulation: bool = False
    coverage: CoverageVector = Field(default_factory=CoverageVector)
    evidence_ids: list[str] = Field(default_factory=list)
    failure_class: FailureClass | None = None


class ReviewResult(BaseModel):
    verdict: Verdict
    rationale: str
    confidence: float = Field(default=0.0, ge=0, le=1)
    missing_evidence: list[str] = Field(default_factory=list)
    suggested_next_step: str | None = None


class ReportModel(BaseModel):
    case: CaseManifest
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    docker_spec: DockerSpec | None = None
    images: list[ImageArtifact] = Field(default_factory=list)
    safe_poc: SafePoC | None = None
    validation: ValidationResult | None = None
    review: ReviewResult | None = None
    generated_at: str
    limitations: list[str] = Field(default_factory=list)
    vulnerability_contract: VulnerabilityContract | None = None
    reproduction_graph: ReproductionGraph | None = None
    coverage: CoverageVector | None = None
    attempts: list[AttemptRecord] = Field(default_factory=list)
    feedback: list[TypedFeedback] = Field(default_factory=list)
    skill_applications: list[SkillApplication] = Field(default_factory=list)
    reasoning: list[AgentReasoning] = Field(default_factory=list)
    source_context: SourceContextBundle | None = None
    proof_bundle: dict[str, Any] = Field(default_factory=dict)


def case_output_dir(case: CaseManifest) -> Path:
    return Path(case.output_dir).expanduser().resolve() / case.case_id
