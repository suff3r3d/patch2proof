import { NextResponse } from "next/server";
import { getAllSpecialists, saveSpecialist, getSpecialistById } from "@/lib/specialists";

export async function GET() {
  try {
    const specialists = getAllSpecialists();
    return NextResponse.json({ success: true, specialists });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to load specialists" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { id, name, description, role, stage, model, temperature, tags, systemPrompt } = body;

    if (!id || typeof id !== "string") {
      return NextResponse.json(
        { success: false, error: "Specialist ID is required" },
        { status: 400 }
      );
    }

    const cleanId = id.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-");

    if (getSpecialistById(cleanId)) {
      return NextResponse.json(
        { success: false, error: `Specialist '${cleanId}' already exists` },
        { status: 409 }
      );
    }

    const defaultPrompt =
      systemPrompt ||
      `# ${cleanId}\n\n## Task and inputs\n\nDescribe the specialist task and required inputs.\n\n## Output contract\n\nReturn JSON matching the target schema.\n\n## Boundary and handoff\n\nDefine execution and reasoning boundaries.`;

    const created = saveSpecialist({
      id: cleanId,
      name: name?.trim() || cleanId,
      description: (description ?? role ?? "Specialist skill contract for Patch2Proof.").trim(),
      role: (role ?? description ?? "Specialist skill contract for Patch2Proof.").trim(),
      stage: stage?.trim() || "Custom Specialist",
      model: model?.trim() || "claude-3-7-sonnet",
      temperature: typeof temperature === "number" ? temperature : 0.0,
      tags: Array.isArray(tags)
        ? tags
        : typeof tags === "string"
        ? tags
            .split(",")
            .map((t: string) => t.trim())
            .filter(Boolean)
        : [],
      systemPrompt: defaultPrompt,
    });

    return NextResponse.json({ success: true, specialist: created }, { status: 201 });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to create specialist" },
      { status: 500 }
    );
  }
}
