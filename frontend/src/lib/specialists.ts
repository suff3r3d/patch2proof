import fs from "fs";
import path from "path";
import crypto from "crypto";
import matter from "gray-matter";

export interface SpecialistLink {
  label: string;
  href: string;
  resolvedPath: string;
  kind: "schema" | "model" | "doc" | "other";
}

export interface SpecialistSchemaProperty {
  name: string;
  type: string;
  required: boolean;
  enumValues?: string[];
  description?: string;
}

export interface SpecialistSchemaSummary {
  filename: string;
  relativePath: string;
  title: string;
  required: string[];
  properties: SpecialistSchemaProperty[];
  raw: Record<string, any>;
}

export interface SpecialistCaseTrace {
  caseId: string;
  artifacts: {
    filename: string;
    relativePath: string;
    role: "input" | "output" | "audit";
    sizeBytes: number;
    preview: Record<string, any> | any[];
  }[];
}

export interface SpecialistSections {
  taskAndInputs: string;
  outputContract: string;
  boundaryAndHandoff: string;
}

export interface Specialist {
  id: string;
  name: string;
  description: string;
  role: string;
  stage: string;
  stageOrder: number;
  pipelineNode: string;
  model: string;
  temperature: number;
  tags: string[];
  systemPrompt: string;
  filename: string;
  skillSha256: string;
  sections: SpecialistSections;
  links: SpecialistLink[];
  schemas: SpecialistSchemaSummary[];
  updatedAt?: string;
}

interface StageMetadata {
  order: number;
  stage: string;
  pipelineNode: string;
  tags: string[];
  traceFiles: { filename: string; role: "input" | "output" | "audit" }[];
}

const CANONICAL_STAGE_MAP: Record<string, StageMetadata> = {
  "revision-discovery": {
    order: 1,
    stage: "01 · Revision Discovery",
    pipelineNode: "discover_revisions",
    tags: ["git", "revisions", "commits"],
    traceFiles: [
      { filename: "case-manifest.json", role: "input" },
      { filename: "revision-discovery-result.json", role: "output" },
    ],
  },
  "source-investigation": {
    order: 2,
    stage: "02 · Source Investigation",
    pipelineNode: "investigate_sources",
    tags: ["diff", "callers", "callees", "context"],
    traceFiles: [
      { filename: "patch-diff-summary.json", role: "input" },
      { filename: "source-context.json", role: "output" },
    ],
  },
  "vulnerability-reasoning": {
    order: 3,
    stage: "03 · Vulnerability Reasoning",
    pipelineNode: "reason_vulnerability",
    tags: ["hypothesis", "dag", "root-cause"],
    traceFiles: [
      { filename: "source-context.json", role: "input" },
      { filename: "reasoning-initial.json", role: "output" },
      { filename: "reproduction-dag.json", role: "output" },
    ],
  },
  "strategy-selection": {
    order: 4,
    stage: "04 · Strategy Selection",
    pipelineNode: "select_strategy",
    tags: ["skills", "ranking", "entrypoint"],
    traceFiles: [
      { filename: "reasoning-initial.json", role: "input" },
      { filename: "skill-candidates.json", role: "output" },
    ],
  },
  "environment-reproduction": {
    order: 5,
    stage: "05 · Environment Reproduction",
    pipelineNode: "plan_environment",
    tags: ["docker", "paired-builds", "sandbox"],
    traceFiles: [
      { filename: "case-manifest.json", role: "input" },
      { filename: "docker-plan.json", role: "output" },
    ],
  },
  "reproduction-planning": {
    order: 6,
    stage: "06 · Reproduction Planning",
    pipelineNode: "plan_safe_poc",
    tags: ["safe-poc", "oracle", "canary"],
    traceFiles: [
      { filename: "reasoning-initial.json", role: "input" },
      { filename: "safe-poc-plan.json", role: "output" },
      { filename: "skeptic-review.json", role: "audit" },
    ],
  },
  "failure-diagnosis": {
    order: 7,
    stage: "07 · Failure Diagnosis",
    pipelineNode: "diagnose_failure",
    tags: ["triage", "contradictions", "logs"],
    traceFiles: [
      { filename: "differential-summary.json", role: "input" },
      { filename: "feedback-attempt-1.json", role: "output" },
    ],
  },
  "repair-planning": {
    order: 8,
    stage: "08 · Repair Planning",
    pipelineNode: "plan_repair",
    tags: ["repair", "bounded-retry", "refinement"],
    traceFiles: [
      { filename: "feedback-attempt-1.json", role: "input" },
      { filename: "safe-poc-plan.json", role: "output" },
    ],
  },
  "report-writing": {
    order: 9,
    stage: "09 · Report Writing",
    pipelineNode: "write_final_report",
    tags: ["verdict", "proof-bundle", "audit"],
    traceFiles: [
      { filename: "coverage-evaluation.json", role: "input" },
      { filename: "final-report.json", role: "output" },
      { filename: "proof-bundle.json", role: "audit" },
    ],
  },
};

function getRepoRoot(): string {
  const cwd = process.cwd();
  const parentSpecialists = path.resolve(cwd, "..", "specialists");
  if (fs.existsSync(parentSpecialists)) {
    return path.resolve(cwd, "..");
  }
  return cwd;
}

export function getSpecialistsDir(): string {
  const root = getRepoRoot();
  const dir = path.join(root, "specialists");
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return dir;
}

function parseCanonicalSections(markdownBody: string): SpecialistSections {
  const sections: SpecialistSections = {
    taskAndInputs: "",
    outputContract: "",
    boundaryAndHandoff: "",
  };

  const normalized = markdownBody.replace(/\r\n/g, "\n");
  const headingRegex = /^##\s+(.+)$/gm;
  const matches: { title: string; start: number; contentStart: number }[] = [];

  let match: RegExpExecArray | null;
  while ((match = headingRegex.exec(normalized)) !== null) {
    matches.push({
      title: match[1].trim().toLowerCase(),
      start: match.index,
      contentStart: match.index + match[0].length,
    });
  }

  for (let i = 0; i < matches.length; i++) {
    const current = matches[i];
    const end = i + 1 < matches.length ? matches[i + 1].start : normalized.length;
    const body = normalized.slice(current.contentStart, end).trim();

    if (current.title.includes("task") || current.title.includes("input")) {
      sections.taskAndInputs = body;
    } else if (current.title.includes("output") || current.title.includes("contract")) {
      sections.outputContract = body;
    } else if (current.title.includes("boundary") || current.title.includes("handoff")) {
      sections.boundaryAndHandoff = body;
    }
  }

  return sections;
}

function extractLinks(markdownBody: string, skillDir: string, repoRoot: string): SpecialistLink[] {
  const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
  const links: SpecialistLink[] = [];
  const seen = new Set<string>();

  let match: RegExpExecArray | null;
  while ((match = linkRegex.exec(markdownBody)) !== null) {
    const label = match[1].trim();
    const href = match[2].trim();
    const absTarget = path.resolve(skillDir, href.split("#")[0]);
    const relToRoot = path.relative(repoRoot, absTarget).replace(/\\/g, "/");

    if (seen.has(relToRoot)) continue;
    seen.add(relToRoot);

    let kind: SpecialistLink["kind"] = "other";
    if (relToRoot.startsWith("schemas/") || relToRoot.endsWith(".schema.json")) {
      kind = "schema";
    } else if (relToRoot.includes("models.py")) {
      kind = "model";
    } else if (relToRoot.startsWith("docs/") || relToRoot.endsWith(".md")) {
      kind = "doc";
    }

    links.push({
      label,
      href,
      resolvedPath: relToRoot,
      kind,
    });
  }

  return links;
}

function resolveSchemas(links: SpecialistLink[], repoRoot: string): SpecialistSchemaSummary[] {
  const summaries: SpecialistSchemaSummary[] = [];

  for (const link of links) {
    if (link.kind !== "schema") continue;
    const schemaAbsPath = path.join(repoRoot, link.resolvedPath);
    if (!fs.existsSync(schemaAbsPath)) continue;

    try {
      const rawText = fs.readFileSync(schemaAbsPath, "utf-8");
      const parsed = JSON.parse(rawText);
      const requiredList: string[] = Array.isArray(parsed.required) ? parsed.required : [];
      const propsObj = parsed.properties || {};

      const properties: SpecialistSchemaProperty[] = Object.entries(propsObj).map(
        ([propName, propDef]: [string, any]) => {
          let propType = "any";
          if (Array.isArray(propDef?.type)) {
            propType = propDef.type.join(" | ");
          } else if (typeof propDef?.type === "string") {
            if (propDef.type === "array" && propDef.items?.type) {
              propType = `${propDef.items.type}[]`;
            } else {
              propType = propDef.type;
            }
          }

          return {
            name: propName,
            type: propType,
            required: requiredList.includes(propName),
            enumValues: Array.isArray(propDef?.enum) ? propDef.enum.map(String) : undefined,
            description: typeof propDef?.description === "string" ? propDef.description : undefined,
          };
        }
      );

      summaries.push({
        filename: path.basename(schemaAbsPath),
        relativePath: link.resolvedPath,
        title: parsed.title || path.basename(schemaAbsPath, ".schema.json"),
        required: requiredList,
        properties,
        raw: parsed,
      });
    } catch {
      // Ignore malformed schema files
    }
  }

  return summaries;
}

function readSpecialistFromDirectory(dirName: string): Specialist | null {
  const repoRoot = getRepoRoot();
  const specialistsDir = getSpecialistsDir();
  const skillDir = path.join(specialistsDir, dirName);
  const skillFile = path.join(skillDir, "SKILL.md");

  if (!fs.existsSync(skillFile)) {
    return null;
  }

  const raw = fs.readFileSync(skillFile, "utf-8");
  const stats = fs.statSync(skillFile);
  const skillSha256 = crypto.createHash("sha256").update(raw, "utf-8").digest("hex");
  const parsed = matter(raw);
  const data = parsed.data || {};
  const content = parsed.content.trim();

  const meta = CANONICAL_STAGE_MAP[dirName];
  const name = typeof data.name === "string" && data.name.trim() ? data.name.trim() : dirName;
  const description =
    typeof data.description === "string" && data.description.trim()
      ? data.description.trim()
      : typeof data.role === "string"
      ? data.role.trim()
      : "Specialist skill instructions and output contract.";

  const sections = parseCanonicalSections(content);
  const links = extractLinks(content, skillDir, repoRoot);
  const schemas = resolveSchemas(links, repoRoot);

  return {
    id: dirName,
    name,
    description,
    role: description,
    stage: data.stage || meta?.stage || "Custom Specialist",
    stageOrder: typeof meta?.order === "number" ? meta.order : 99,
    pipelineNode: data.pipelineNode || meta?.pipelineNode || "custom_specialist",
    model: data.model || "claude-3-7-sonnet",
    temperature: typeof data.temperature === "number" ? data.temperature : 0.0,
    tags: Array.isArray(data.tags) ? data.tags : meta?.tags || ["specialist"],
    systemPrompt: content,
    filename: `specialists/${dirName}/SKILL.md`,
    skillSha256,
    sections,
    links,
    schemas,
    updatedAt: stats.mtime.toISOString(),
  };
}

export function getAllSpecialists(): Specialist[] {
  const specialistsDir = getSpecialistsDir();
  const entries = fs.readdirSync(specialistsDir, { withFileTypes: true });

  const specialists: Specialist[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const spec = readSpecialistFromDirectory(entry.name);
    if (spec) {
      specialists.push(spec);
    }
  }

  return specialists.sort((a, b) => {
    if (a.stageOrder !== b.stageOrder) {
      return a.stageOrder - b.stageOrder;
    }
    return a.id.localeCompare(b.id);
  });
}

export function getSpecialistById(id: string): Specialist | null {
  const cleanId = id.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!cleanId) return null;
  return readSpecialistFromDirectory(cleanId);
}

export function saveSpecialist(specialist: {
  id: string;
  name: string;
  description?: string;
  role?: string;
  stage?: string;
  model?: string;
  temperature?: number;
  tags?: string[];
  systemPrompt: string;
}): Specialist {
  const specialistsDir = getSpecialistsDir();
  const cleanId = specialist.id.replace(/[^a-zA-Z0-9_-]/g, "");
  const skillDir = path.join(specialistsDir, cleanId);
  if (!fs.existsSync(skillDir)) {
    fs.mkdirSync(skillDir, { recursive: true });
  }

  const skillFile = path.join(skillDir, "SKILL.md");
  const description = (specialist.description ?? specialist.role ?? "").trim();

  // Keep frontmatter clean and canonical (`name` and `description`) to preserve SKILL.md format
  const frontmatter: Record<string, any> = {
    name: (specialist.name || cleanId).trim(),
    description: description || "Specialist skill contract for Patch2Proof.",
  };

  const fileContent = matter.stringify(`\n${specialist.systemPrompt.trim()}\n`, frontmatter);
  fs.writeFileSync(skillFile, fileContent, "utf-8");

  const updated = getSpecialistById(cleanId);
  if (!updated) {
    throw new Error(`Failed to reload saved specialist '${cleanId}'`);
  }
  return updated;
}

export function deleteSpecialist(id: string): boolean {
  const specialistsDir = getSpecialistsDir();
  const cleanId = id.replace(/[^a-zA-Z0-9_-]/g, "");
  const skillDir = path.join(specialistsDir, cleanId);

  if (!fs.existsSync(skillDir)) {
    return false;
  }

  fs.rmSync(skillDir, { recursive: true, force: true });
  return true;
}

export function getCaseTracesForSpecialist(id: string): SpecialistCaseTrace[] {
  const repoRoot = getRepoRoot();
  const artifactsDir = path.join(repoRoot, "artifacts");
  if (!fs.existsSync(artifactsDir)) {
    return [];
  }

  const meta = CANONICAL_STAGE_MAP[id];
  const targetFiles = meta?.traceFiles || [
    { filename: "case-manifest.json", role: "input" as const },
    { filename: "final-report.json", role: "output" as const },
  ];

  const entries = fs.readdirSync(artifactsDir, { withFileTypes: true });
  const traces: SpecialistCaseTrace[] = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const caseId = entry.name;
    const caseDir = path.join(artifactsDir, caseId);

    const matchedArtifacts: SpecialistCaseTrace["artifacts"] = [];
    for (const tf of targetFiles) {
      const filePath = path.join(caseDir, tf.filename);
      if (!fs.existsSync(filePath)) continue;

      try {
        const stats = fs.statSync(filePath);
        const raw = fs.readFileSync(filePath, "utf-8");
        const parsed = JSON.parse(raw);
        matchedArtifacts.push({
          filename: tf.filename,
          relativePath: `artifacts/${caseId}/${tf.filename}`,
          role: tf.role,
          sizeBytes: stats.size,
          preview: parsed,
        });
      } catch {
        // Ignore unparseable files
      }
    }

    if (matchedArtifacts.length > 0) {
      traces.push({
        caseId,
        artifacts: matchedArtifacts,
      });
    }
  }

  return traces.sort((a, b) => a.caseId.localeCompare(b.caseId));
}
