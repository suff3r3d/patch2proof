import fs from "fs";
import path from "path";
import matter from "gray-matter";

export interface Specialist {
  id: string;
  name: string;
  role: string;
  stage: "hypothesis" | "safe_poc_plan" | "repair" | "review" | "general" | string;
  model?: string;
  temperature?: number;
  tags?: string[];
  systemPrompt: string;
  filename: string;
  updatedAt?: string;
}

export function getPromptsDir(): string {
  const candidates = [
    path.resolve(process.cwd(), "../config/prompts"),
    path.resolve(process.cwd(), "config/prompts"),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  // Ensure ../config/prompts exists
  const fallback = path.resolve(process.cwd(), "../config/prompts");
  if (!fs.existsSync(fallback)) {
    fs.mkdirSync(fallback, { recursive: true });
  }
  return fallback;
}

export function getAllSpecialists(): Specialist[] {
  const dir = getPromptsDir();
  if (!fs.existsSync(dir)) return [];

  const files = fs.readdirSync(dir).filter((file) => file.endsWith(".md"));

  const specialists: Specialist[] = [];

  for (const file of files) {
    const fullPath = path.join(dir, file);
    const content = fs.readFileSync(fullPath, "utf-8");
    const stat = fs.statSync(fullPath);

    const parsed = matter(content);
    const id = (parsed.data.id as string) || file.replace(/\.md$/, "");

    specialists.push({
      id,
      name: (parsed.data.name as string) || id,
      role: (parsed.data.role as string) || "Pipeline reasoning specialist",
      stage: (parsed.data.stage as string) || "general",
      model: (parsed.data.model as string) || "default",
      temperature: typeof parsed.data.temperature === "number" ? parsed.data.temperature : 0.0,
      tags: Array.isArray(parsed.data.tags) ? parsed.data.tags : [],
      systemPrompt: parsed.content.trim(),
      filename: file,
      updatedAt: stat.mtime.toISOString(),
    });
  }

  // Sort by id alphabetically
  return specialists.sort((a, b) => a.id.localeCompare(b.id));
}

export function getSpecialistById(id: string): Specialist | null {
  const all = getAllSpecialists();
  return all.find((s) => s.id === id) || null;
}

export function saveSpecialist(specialist: Specialist): void {
  const dir = getPromptsDir();
  const filename = specialist.filename || `${specialist.id}.md`;
  const fullPath = path.join(dir, filename);

  const frontmatterData: Record<string, any> = {
    id: specialist.id,
    name: specialist.name,
    role: specialist.role,
    stage: specialist.stage,
    model: specialist.model || "default",
    temperature: specialist.temperature ?? 0.0,
    tags: specialist.tags || [],
  };

  const fileContent = matter.stringify(specialist.systemPrompt.trim() + "\n", frontmatterData);
  fs.writeFileSync(fullPath, fileContent, "utf-8");
}

export function deleteSpecialist(id: string): boolean {
  const specialist = getSpecialistById(id);
  if (!specialist) return false;

  const dir = getPromptsDir();
  const fullPath = path.join(dir, specialist.filename);
  if (fs.existsSync(fullPath)) {
    fs.unlinkSync(fullPath);
    return true;
  }
  return false;
}
