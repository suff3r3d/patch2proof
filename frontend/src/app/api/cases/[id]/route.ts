import { NextResponse } from "next/server";
import {
  getCaseById,
  readCaseArtifactContent,
  saveCaseManifest,
  deleteCaseManifest,
} from "@/lib/cases";

interface RouteParams {
  params: {
    id: string;
  };
}

export async function GET(request: Request, { params }: RouteParams) {
  try {
    const caseRecord = getCaseById(params.id);
    if (!caseRecord) {
      return NextResponse.json(
        { success: false, error: "Case not found" },
        { status: 404 }
      );
    }

    const url = new URL(request.url);
    const artifactName = url.searchParams.get("artifact");
    const includeBundle = url.searchParams.get("bundle") === "1";

    if (artifactName) {
      const artifact = readCaseArtifactContent(caseRecord.id, artifactName);
      if (!artifact) {
        return NextResponse.json(
          { success: false, error: `Artifact '${artifactName}' not found` },
          { status: 404 }
        );
      }
      return NextResponse.json({
        success: true,
        caseRecord,
        artifact,
      });
    }

    let bundle: Record<string, any> | undefined = undefined;
    if (includeBundle) {
      const keyFiles = [
        "revision-discovery-result.json",
        "raw-patch.diff",
        "patch-analysis.json",
        "source-context.json",
        "reasoning-initial.json",
        "reproduction-graph.json",
        "vulnerability-contract.json",
        "docker-plan.json",
        "safe-poc-plan.json",
        "safepoc.json",
        "attempt-1.json",
        "feedback-attempt-1.json",
        "skeptic-review.json",
        "coverage.json",
        "proof-bundle.json",
        "final-report.md",
      ];
      bundle = {};
      for (const fname of keyFiles) {
        const loaded = readCaseArtifactContent(caseRecord.id, fname);
        if (loaded) {
          bundle[fname] =
            loaded.parsedJson !== undefined ? loaded.parsedJson : loaded.content;
        }
      }
    }

    return NextResponse.json({
      success: true,
      caseRecord,
      bundle,
    });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to fetch case" },
      { status: 500 }
    );
  }
}

export async function PUT(request: Request, { params }: RouteParams) {
  try {
    const existing = getCaseById(params.id);
    if (!existing) {
      return NextResponse.json(
        { success: false, error: "Case not found" },
        { status: 404 }
      );
    }

    const body = await request.json();
    const updated = saveCaseManifest({
      id: existing.id,
      title: body.title !== undefined ? String(body.title).trim() : existing.title,
      repository_path:
        body.repository_path !== undefined
          ? String(body.repository_path).trim()
          : existing.repository_path,
      source_mode:
        body.source_mode !== undefined
          ? String(body.source_mode).trim()
          : existing.source_mode,
      vulnerable_ref:
        body.vulnerable_ref !== undefined
          ? String(body.vulnerable_ref).trim()
          : existing.vulnerable_ref,
      fixed_ref:
        body.fixed_ref !== undefined
          ? String(body.fixed_ref).trim()
          : existing.fixed_ref,
      language:
        body.language !== undefined
          ? String(body.language).trim()
          : existing.language,
      build_system:
        body.build_system !== undefined
          ? String(body.build_system).trim()
          : existing.build_system,
      advisory:
        body.advisory !== undefined ? String(body.advisory) : existing.advisory,
      commit_message:
        body.commit_message !== undefined
          ? String(body.commit_message)
          : existing.commit_message,
      dockerfile:
        body.dockerfile !== undefined
          ? body.dockerfile
            ? String(body.dockerfile).trim()
            : null
          : existing.dockerfile,
      registered_test_id:
        body.registered_test_id !== undefined
          ? String(body.registered_test_id).trim()
          : existing.registered_test_id,
      output_dir: existing.output_dir,
      tags: Array.isArray(body.tags) ? body.tags.map(String) : existing.tags,
      policy: body.policy
        ? {
            ...existing.policy,
            ...body.policy,
            network: "none",
          }
        : existing.policy,
      manifestPath: existing.manifestPath,
    });

    return NextResponse.json({ success: true, caseRecord: updated });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to update case" },
      { status: 500 }
    );
  }
}

export async function DELETE(request: Request, { params }: RouteParams) {
  try {
    const deleted = deleteCaseManifest(params.id);
    if (!deleted) {
      return NextResponse.json(
        {
          success: false,
          error:
            "Recorded artifact directories are read-only for audit preservation; only manifest files in examples/ can be removed.",
        },
        { status: 400 }
      );
    }
    return NextResponse.json({
      success: true,
      message: `Removed manifest for '${params.id}'`,
    });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to delete case" },
      { status: 500 }
    );
  }
}
