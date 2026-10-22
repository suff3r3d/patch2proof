import { NextResponse } from "next/server";
import {
  getSpecialistById,
  saveSpecialist,
  deleteSpecialist,
  getCaseTracesForSpecialist,
} from "@/lib/specialists";

interface RouteParams {
  params: {
    id: string;
  };
}

export async function GET(request: Request, { params }: RouteParams) {
  try {
    const specialist = getSpecialistById(params.id);
    if (!specialist) {
      return NextResponse.json(
        { success: false, error: "Specialist not found" },
        { status: 404 }
      );
    }

    const traces = getCaseTracesForSpecialist(params.id);
    return NextResponse.json({ success: true, specialist, traces });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to fetch specialist" },
      { status: 500 }
    );
  }
}

export async function PUT(request: Request, { params }: RouteParams) {
  try {
    const existing = getSpecialistById(params.id);
    if (!existing) {
      return NextResponse.json(
        { success: false, error: "Specialist not found" },
        { status: 404 }
      );
    }

    const body = await request.json();
    const { name, description, role, stage, model, temperature, tags, systemPrompt } = body;

    const updated = saveSpecialist({
      id: existing.id,
      name: name !== undefined ? name.trim() : existing.name,
      description:
        description !== undefined
          ? description.trim()
          : role !== undefined
          ? role.trim()
          : existing.description,
      role:
        role !== undefined
          ? role.trim()
          : description !== undefined
          ? description.trim()
          : existing.role,
      stage: stage !== undefined ? stage.trim() : existing.stage,
      model: model !== undefined ? model.trim() : existing.model,
      temperature: typeof temperature === "number" ? temperature : existing.temperature,
      tags: Array.isArray(tags)
        ? tags
        : typeof tags === "string"
        ? tags
            .split(",")
            .map((t: string) => t.trim())
            .filter(Boolean)
        : existing.tags,
      systemPrompt: systemPrompt !== undefined ? systemPrompt : existing.systemPrompt,
    });

    return NextResponse.json({ success: true, specialist: updated });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to update specialist" },
      { status: 500 }
    );
  }
}

export async function DELETE(request: Request, { params }: RouteParams) {
  try {
    const success = deleteSpecialist(params.id);
    if (!success) {
      return NextResponse.json(
        { success: false, error: "Specialist not found or could not be deleted" },
        { status: 404 }
      );
    }
    return NextResponse.json({ success: true, message: `Specialist '${params.id}' deleted` });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to delete specialist" },
      { status: 500 }
    );
  }
}
