import { NextResponse } from "next/server";
import { getAllCases, getCaseById, saveCaseManifest } from "@/lib/cases";

export async function GET() {
  try {
    const cases = getAllCases();
    return NextResponse.json({ success: true, cases });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to load cases" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const rawId = String(body.id || body.case_id || "").trim();

    if (!rawId) {
      return NextResponse.json(
        { success: false, error: "case_id is required" },
        { status: 400 }
      );
    }

    const isCve = /^CVE-\d{4}-\d{4,}$/i.test(rawId);
    const cleanId = isCve
      ? rawId.toUpperCase()
      : rawId.toLowerCase().replace(/[^a-z0-9_-]/g, "-");

    if (getCaseById(cleanId)) {
      return NextResponse.json(
        { success: false, error: `Case '${cleanId}' already exists` },
        { status: 409 }
      );
    }

    const created = saveCaseManifest({
      id: cleanId,
      title:
        body.title?.trim() ||
        (isCve ? `Revision discovery for ${cleanId}` : `Pinned case ${cleanId}`),
      repository_path:
        body.repository_path?.trim() ||
        (isCve ? `./artifacts/${cleanId}` : "./examples/fixture-repository"),
      source_mode: body.source_mode || (isCve ? "git" : "fixture"),
      vulnerable_ref:
        body.vulnerable_ref?.trim() || (isCve ? "UNRESOLVED" : "v1.0.0"),
      fixed_ref: body.fixed_ref?.trim() || (isCve ? "UNRESOLVED" : "v1.0.1"),
      language: body.language || (isCve ? "unknown" : "python"),
      build_system: body.build_system || "custom",
      advisory: body.advisory || "",
      commit_message: body.commit_message || "",
      dockerfile: body.dockerfile || "./templates/docker/python.Dockerfile",
      registered_test_id: body.registered_test_id || "fixture_noop",
      output_dir: "artifacts",
      tags: Array.isArray(body.tags)
        ? body.tags
        : isCve
        ? ["cve-discovery"]
        : ["local-lab"],
      policy: {
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
        reasoning_mode: body.reasoning_mode || "required",
        reasoning_model: body.reasoning_model || null,
        reasoning_temperature: 0.0,
        reasoning_effort: body.reasoning_effort || "medium",
        allow_heuristic_reasoning: false,
      },
      manifestPath: `examples/${cleanId}.yaml`,
    });

    return NextResponse.json({ success: true, caseRecord: created }, { status: 201 });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to create case" },
      { status: 500 }
    );
  }
}
