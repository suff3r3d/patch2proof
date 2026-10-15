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
    const { id, name, role, stage, model, temperature, tags, systemPrompt } = body;

    if (!id || typeof id !== "string") {
      return NextResponse.json(
        { success: false, error: "Specialist ID is required" },
        { status: 400 }
      );
    }

    // Slugify id
    const cleanId = id.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-");

    if (getSpecialistById(cleanId)) {
      return NextResponse.json(
        { success: false, error: `Specialist '${cleanId}' already exists` },
        { status: 409 }
      );
    }

    const newSpecialist = {
      id: cleanId,
      name: name?.trim() || cleanId,
      role: role?.trim() || "Reasoning specialist",
      stage: stage?.trim() || "general",
      model: model?.trim() || "default",
      temperature: typeof temperature === "number" ? temperature : 0.0,
      tags: Array.isArray(tags) ? tags : typeof tags === "string" ? tags.split(",").map((t: string) => t.trim()).filter(Boolean) : [],
      systemPrompt: systemPrompt || `# ${name || cleanId} Prompt\n\nEnter system instructions here.`,
      filename: `${cleanId}.md`,
    };

    saveSpecialist(newSpecialist);

    return NextResponse.json({ success: true, specialist: newSpecialist }, { status: 201 });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to create specialist" },
      { status: 500 }
    );
  }
}
