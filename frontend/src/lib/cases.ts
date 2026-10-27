import fs from "fs";
import path from "path";
import crypto from "crypto";
import yaml from "js-yaml";

export interface CasePolicy {
  authorized: boolean;
  network: string;
  allow_docker_build: boolean;
  allow_poc_execution: boolean;
  allowed_repo_root: string;
  allowed_artifact_root: string;
  allowed_base_images: string[];
  max_memory_mb: number;
  max_cpus: number;
  max_pids: number;
  timeout_seconds: number;
  skill_memory_path?: string;
  max_repair_attempts?: number;
  reasoning_mode: string;
  reasoning_model?: string | null;
  reasoning_temperature?: number;
  reasoning_effort: string;
  allow_heuristic_reasoning: boolean;
  source_call_depth?: number;
  source_file_limit?: number;
  source_file_max_bytes?: number;
  source_context_limit_chars?: number;
  source_tool_call_limit?: number;
}

export interface CaseArtifactFile {
  filename: string;
  relativePath: string;
  kind: "json" | "diff" | "markdown" | "other";
  category: "discovery" | "source" | "reasoning" | "execution" | "proof" | "other";
  sizeBytes: number;
  sha256: string;
  updatedAt: string;
}

export interface CaseSummaryRecord {
  id: string;
  title: string;
  repository_path: string;
  source_mode: string;
  vulnerable_ref: string;
  fixed_ref: string;
  language: string;
  build_system: string;
  advisory: string;
  commit_message: string;
  dockerfile: string | null;
  registered_test_id: string;
  output_dir: string;
  tags: string[];
  policy: CasePolicy;
  manifestPath: string;
  manifestFormat: "yaml" | "json";
  artifactDir: string | null;
  claimStatus: string;
  gatesPassed: number;
  gatesTotal: number;
  discoveryStatus: string | null;
  artifactFiles: CaseArtifactFile[];
  rawManifestText: string;
}

const DEFAULT_POLICY: CasePolicy = {
  authorized: true,
  network: "none",
  allow_docker_build: false,
  allow_poc_execution: false,
  allowed_repo_root: ".",
  allowed_artifact_root: "./artifacts",
  allowed_base_images: ["python:", "eclipse-temurin:", "node:"],
  max_memory_mb: 512,
  max_cpus: 1.0,
  max_pids: 128,
  timeout_seconds: 60,
  max_repair_attempts: 4,
  reasoning_mode: "required",
  reasoning_model: null,
  reasoning_temperature: 0.0,
  reasoning_effort: "medium",
  allow_heuristic_reasoning: false,
};

function getRepoRoot(): string {
  const cwd = process.cwd();
  const parentSpecialists = path.resolve(cwd, "..", "specialists");
  if (fs.existsSync(parentSpecialists)) {
    return path.resolve(cwd, "..");
  }
  return cwd;
}

function classifyArtifactCategory(filename: string): CaseArtifactFile["category"] {
  if (
    filename.includes("discovery") ||
    filename.includes("nvd") ||
    filename.includes("osv")
  ) {
    return "discovery";
  }
  if (
    filename.includes("patch") ||
    filename.includes("source") ||
    filename.endsWith(".diff")
  ) {
    return "source";
  }
  if (
    filename.includes("reasoning") ||
    filename.includes("reproduction-graph") ||
    filename.includes("vulnerability-contract") ||
    filename.includes("skill") ||
    filename.includes("retrieved")
  ) {
    return "reasoning";
  }
  if (
    filename.includes("docker") ||
    filename.includes("images") ||
    filename.includes("safepoc") ||
    filename.includes("safe-poc") ||
    filename.includes("attempt") ||
    filename.includes("feedback")
  ) {
    return "execution";
  }
  if (
    filename.includes("proof") ||
    filename.includes("coverage") ||
    filename.includes("final-report") ||
    filename.includes("skeptic") ||
    filename.includes("validation") ||
    filename.includes("dacn")
  ) {
    return "proof";
  }
  return "other";
}

function scanArtifactFiles(caseId: string, repoRoot: string): {
  artifactDir: string | null;
  files: CaseArtifactFile[];
  claimStatus: string;
  gatesPassed: number;
  gatesTotal: number;
  discoveryStatus: string | null;
} {
  const caseArtifactDir = path.join(repoRoot, "artifacts", caseId);
  if (!fs.existsSync(caseArtifactDir) || !fs.statSync(caseArtifactDir).isDirectory()) {
    return {
      artifactDir: null,
      files: [],
      claimStatus: "not_executed",
      gatesPassed: 0,
      gatesTotal: 6,
      discoveryStatus: null,
    };
  }

  const entries = fs.readdirSync(caseArtifactDir, { withFileTypes: true });
  const files: CaseArtifactFile[] = [];

  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const fullPath = path.join(caseArtifactDir, entry.name);
    const stat = fs.statSync(fullPath);
    const rawBuffer = fs.readFileSync(fullPath);
    const sha256 = crypto.createHash("sha256").update(rawBuffer).digest("hex");

    let kind: CaseArtifactFile["kind"] = "other";
    if (entry.name.endsWith(".json")) kind = "json";
    else if (entry.name.endsWith(".diff")) kind = "diff";
    else if (entry.name.endsWith(".md")) kind = "markdown";

    files.push({
      filename: entry.name,
      relativePath: `artifacts/${caseId}/${entry.name}`,
      kind,
      category: classifyArtifactCategory(entry.name),
      sizeBytes: stat.size,
      sha256,
      updatedAt: stat.mtime.toISOString(),
    });
  }

  files.sort((a, b) => a.filename.localeCompare(b.filename));

  let claimStatus = "not_executed";
  let gatesPassed = 0;
  const gatesTotal = 6;
  let discoveryStatus: string | null = null;

  const proofBundlePath = path.join(caseArtifactDir, "proof-bundle.json");
  if (fs.existsSync(proofBundlePath)) {
    try {
      const pb = JSON.parse(fs.readFileSync(proofBundlePath, "utf-8"));
      if (typeof pb.claim_status === "string") {
        claimStatus = pb.claim_status;
      }
    } catch {
      // ignore
    }
  }

  const coveragePath = path.join(caseArtifactDir, "coverage.json");
  if (fs.existsSync(coveragePath)) {
    try {
      const cov = JSON.parse(fs.readFileSync(coveragePath, "utf-8"));
      const gateKeys = [
        "static_reachability",
        "dynamic_reachability",
        "semantic_transition",
        "counterfactual_separation",
        "repeatable",
        "source_grounded",
      ];
      gatesPassed = gateKeys.filter((k) => cov[k] === true).length;
    } catch {
      // ignore
    }
  }

  const discoveryPath = path.join(caseArtifactDir, "revision-discovery-result.json");
  if (fs.existsSync(discoveryPath)) {
    try {
      const disc = JSON.parse(fs.readFileSync(discoveryPath, "utf-8"));
      if (typeof disc.status === "string") {
        discoveryStatus = disc.status;
      }
    } catch {
      // ignore
    }
  }

  return {
    artifactDir: `artifacts/${caseId}`,
    files,
    claimStatus,
    gatesPassed,
    gatesTotal,
    discoveryStatus,
  };
}

function normalizeManifestData(
  rawObj: Record<string, any>,
  fallbackId: string,
  manifestPath: string,
  manifestFormat: "yaml" | "json",
  rawManifestText: string,
  repoRoot: string
): CaseSummaryRecord {
  const id = String(rawObj.case_id || fallbackId).trim();
  const policyObj = rawObj.policy || {};
  const policy: CasePolicy = {
    ...DEFAULT_POLICY,
    ...policyObj,
    allowed_base_images: Array.isArray(policyObj.allowed_base_images)
      ? policyObj.allowed_base_images.map(String)
      : DEFAULT_POLICY.allowed_base_images,
  };

  const artifactScan = scanArtifactFiles(id, repoRoot);

  return {
    id,
    title: String(rawObj.title || `Case ${id}`),
    repository_path: String(rawObj.repository_path || "."),
    source_mode: String(rawObj.source_mode || "git"),
    vulnerable_ref: String(rawObj.vulnerable_ref || "UNRESOLVED"),
    fixed_ref: String(rawObj.fixed_ref || "UNRESOLVED"),
    language: String(rawObj.language || "python"),
    build_system: String(rawObj.build_system || "custom"),
    advisory: String(rawObj.advisory || ""),
    commit_message: String(rawObj.commit_message || ""),
    dockerfile: rawObj.dockerfile ? String(rawObj.dockerfile) : null,
    registered_test_id: String(rawObj.registered_test_id || "fixture_noop"),
    output_dir: String(rawObj.output_dir || "artifacts"),
    tags: Array.isArray(rawObj.tags) ? rawObj.tags.map(String) : [],
    policy,
    manifestPath,
    manifestFormat,
    artifactDir: artifactScan.artifactDir,
    claimStatus: artifactScan.claimStatus,
    gatesPassed: artifactScan.gatesPassed,
    gatesTotal: artifactScan.gatesTotal,
    discoveryStatus: artifactScan.discoveryStatus,
    artifactFiles: artifactScan.files,
    rawManifestText,
  };
}

export function getAllCases(): CaseSummaryRecord[] {
  const repoRoot = getRepoRoot();
  const byId = new Map<string, CaseSummaryRecord>();

  // 1. Scan artifacts/<caseId>/case.json first
  const artifactsRoot = path.join(repoRoot, "artifacts");
  if (fs.existsSync(artifactsRoot)) {
    const entries = fs.readdirSync(artifactsRoot, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const caseJsonPath = path.join(artifactsRoot, entry.name, "case.json");
      if (!fs.existsSync(caseJsonPath)) continue;
      try {
        const rawText = fs.readFileSync(caseJsonPath, "utf-8");
        const parsed = JSON.parse(rawText);
        const record = normalizeManifestData(
          parsed,
          entry.name,
          `artifacts/${entry.name}/case.json`,
          "json",
          rawText,
          repoRoot
        );
        byId.set(record.id, record);
      } catch {
        // ignore invalid case.json
      }
    }
  }

  // 2. Scan examples/*.yaml and cases/*.yaml (if present)
  const manifestDirs = ["examples", "cases"];
  for (const dirName of manifestDirs) {
    const absDir = path.join(repoRoot, dirName);
    if (!fs.existsSync(absDir)) continue;
    const entries = fs.readdirSync(absDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isFile()) continue;
      const ext = path.extname(entry.name).toLowerCase();
      if (ext !== ".yaml" && ext !== ".yml" && ext !== ".json") continue;
      const fullPath = path.join(absDir, entry.name);
      try {
        const rawText = fs.readFileSync(fullPath, "utf-8");
        const parsed =
          ext === ".json"
            ? JSON.parse(rawText)
            : (yaml.load(rawText) as Record<string, any>);
        if (!parsed || typeof parsed !== "object" || !parsed.case_id) continue;

        const relPath = `${dirName}/${entry.name}`;
        const record = normalizeManifestData(
          parsed,
          path.basename(entry.name, ext),
          relPath,
          ext === ".json" ? "json" : "yaml",
          rawText,
          repoRoot
        );
        // Prefer YAML manifest path when both exist, while keeping artifact scan
        byId.set(record.id, record);
      } catch {
        // ignore unparseable files
      }
    }
  }

  const list = Array.from(byId.values());
  return list.sort((a, b) => {
    // Sort cases with more artifacts first, then alphabetically
    if (b.artifactFiles.length !== a.artifactFiles.length) {
      return b.artifactFiles.length - a.artifactFiles.length;
    }
    return a.id.localeCompare(b.id);
  });
}

export function getCaseById(id: string): CaseSummaryRecord | null {
  const all = getAllCases();
  return all.find((c) => c.id === id) || null;
}

export function readCaseArtifactContent(
  caseId: string,
  filename: string
): { content: string; parsedJson?: any; file: CaseArtifactFile } | null {
  const repoRoot = getRepoRoot();
  const record = getCaseById(caseId);
  if (!record) return null;

  const cleanFile = path.basename(filename);
  const fileMeta = record.artifactFiles.find((f) => f.filename === cleanFile);
  if (!fileMeta) return null;

  const absPath = path.join(repoRoot, "artifacts", record.id, cleanFile);
  if (!fs.existsSync(absPath)) return null;

  const content = fs.readFileSync(absPath, "utf-8");
  let parsedJson: any = undefined;
  if (fileMeta.kind === "json") {
    try {
      parsedJson = JSON.parse(content);
    } catch {
      // ignore
    }
  }

  return {
    content,
    parsedJson,
    file: fileMeta,
  };
}

export function saveCaseManifest(input: {
  id: string;
  title: string;
  repository_path: string;
  source_mode: string;
  vulnerable_ref: string;
  fixed_ref: string;
  language: string;
  build_system: string;
  advisory: string;
  commit_message: string;
  dockerfile: string | null;
  registered_test_id: string;
  output_dir: string;
  tags: string[];
  policy: CasePolicy;
  manifestPath?: string;
}): CaseSummaryRecord {
  const repoRoot = getRepoRoot();
  const existing = getCaseById(input.id);

  const manifestObj: Record<string, any> = {
    case_id: input.id,
    title: input.title,
    repository_path: input.repository_path,
    source_mode: input.source_mode,
    vulnerable_ref: input.vulnerable_ref,
    fixed_ref: input.fixed_ref,
    language: input.language,
    build_system: input.build_system,
    advisory: input.advisory,
    commit_message: input.commit_message,
    dockerfile: input.dockerfile || null,
    registered_test_id: input.registered_test_id || "fixture_noop",
    output_dir: input.output_dir || "artifacts",
    tags: input.tags || [],
    policy: {
      ...DEFAULT_POLICY,
      ...input.policy,
      network: "none", // Enforce fail-closed network: none
    },
  };

  let targetRelPath =
    existing?.manifestPath || input.manifestPath || `examples/${input.id}.yaml`;

  // Prevent path traversal outside repo root
  const absTarget = path.resolve(repoRoot, targetRelPath);
  if (!absTarget.startsWith(repoRoot)) {
    throw new Error("Invalid manifest path");
  }

  const parentDir = path.dirname(absTarget);
  if (!fs.existsSync(parentDir)) {
    fs.mkdirSync(parentDir, { recursive: true });
  }

  if (absTarget.endsWith(".json")) {
    fs.writeFileSync(absTarget, JSON.stringify(manifestObj, null, 2) + "\n", "utf-8");
  } else {
    const yamlText = yaml.dump(manifestObj, { lineWidth: 100, noRefs: true });
    fs.writeFileSync(absTarget, yamlText, "utf-8");
  }

  // If artifacts/<id>/case.json also exists, keep it synchronized
  const artifactCaseJson = path.join(repoRoot, "artifacts", input.id, "case.json");
  if (fs.existsSync(artifactCaseJson) && absTarget !== artifactCaseJson) {
    fs.writeFileSync(
      artifactCaseJson,
      JSON.stringify(manifestObj, null, 2) + "\n",
      "utf-8"
    );
  }

  const updated = getCaseById(input.id);
  if (!updated) {
    throw new Error(`Failed to reload case '${input.id}' after saving`);
  }
  return updated;
}

export function deleteCaseManifest(id: string): boolean {
  const repoRoot = getRepoRoot();
  const existing = getCaseById(id);
  if (!existing) return false;

  // Only delete YAML manifests in examples/ or cases/, never delete recorded artifacts/
  if (
    existing.manifestPath.startsWith("examples/") ||
    existing.manifestPath.startsWith("cases/")
  ) {
    const absPath = path.join(repoRoot, existing.manifestPath);
    if (fs.existsSync(absPath)) {
      fs.unlinkSync(absPath);
      return true;
    }
  }
  return false;
}
