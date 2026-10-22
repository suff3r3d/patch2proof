"use client";

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";

interface SpecialistLink {
  label: string;
  href: string;
  resolvedPath: string;
  kind: "schema" | "model" | "doc" | "other";
}

interface SpecialistSchemaProperty {
  name: string;
  type: string;
  required: boolean;
  enumValues?: string[];
  description?: string;
}

interface SpecialistSchemaSummary {
  filename: string;
  relativePath: string;
  title: string;
  required: string[];
  properties: SpecialistSchemaProperty[];
  raw: Record<string, any>;
}

interface SpecialistCaseTrace {
  caseId: string;
  artifacts: {
    filename: string;
    relativePath: string;
    role: "input" | "output" | "audit";
    sizeBytes: number;
    preview: Record<string, any> | any[];
  }[];
}

interface SpecialistSections {
  taskAndInputs: string;
  outputContract: string;
  boundaryAndHandoff: string;
}

interface Specialist {
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

type WorkbenchMode = "markdown" | "contract" | "traces";

export default function SpecialistsWorkbenchPage() {
  const [specialists, setSpecialists] = useState<Specialist[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Specialist | null>(null);
  const [original, setOriginal] = useState<Specialist | null>(null);
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<WorkbenchMode>("markdown");

  // Traces state for the selected specialist
  const [traces, setTraces] = useState<SpecialistCaseTrace[]>([]);
  const [tracesLoading, setTracesLoading] = useState(false);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [selectedArtifactFile, setSelectedArtifactFile] = useState<string | null>(null);
  const [showRawSchema, setShowRawSchema] = useState<Record<string, boolean>>({});

  // Modals & Toast
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const [newForm, setNewForm] = useState({
    id: "",
    name: "",
    description: "",
    systemPrompt: `# custom-specialist\n\n## Task and inputs\n\nDescribe the specialist task and the artifacts it consumes.\n\n## Output contract\n\nReturn JSON matching the target schema.\n\n## Boundary and handoff\n\nKeep reasoning evidence-grounded and deterministic.\n`,
  });

  const triggerToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 2800);
  }, []);

  const fetchTracesForSpecialist = useCallback(async (id: string) => {
    try {
      setTracesLoading(true);
      const res = await fetch(`/api/specialists/${encodeURIComponent(id)}`);
      const data = await res.json();
      if (data.success && Array.isArray(data.traces)) {
        setTraces(data.traces);
        if (data.traces.length > 0) {
          const firstCase = data.traces[0];
          setSelectedCaseId(firstCase.caseId);
          const defaultArtifact =
            firstCase.artifacts.find((a: any) => a.role === "output") ||
            firstCase.artifacts[0];
          setSelectedArtifactFile(defaultArtifact ? defaultArtifact.filename : null);
        } else {
          setSelectedCaseId(null);
          setSelectedArtifactFile(null);
        }
      }
    } catch {
      setTraces([]);
    } finally {
      setTracesLoading(false);
    }
  }, []);

  const fetchSpecialists = useCallback(
    async (preferredId?: string) => {
      try {
        setLoading(true);
        const res = await fetch("/api/specialists");
        const data = await res.json();
        if (data.success && Array.isArray(data.specialists)) {
          setSpecialists(data.specialists);
          const targetId = preferredId || selectedId || data.specialists[0]?.id;
          if (targetId) {
            const match =
              data.specialists.find((s: Specialist) => s.id === targetId) ||
              data.specialists[0];
            if (match) {
              setSelectedId(match.id);
              setDraft({ ...match });
              setOriginal({ ...match });
              fetchTracesForSpecialist(match.id);
            }
          }
        }
      } catch (err: any) {
        triggerToast(err.message || "Failed to load specialists");
      } finally {
        setLoading(false);
      }
    },
    [selectedId, triggerToast, fetchTracesForSpecialist]
  );

  useEffect(() => {
    fetchSpecialists();
  }, []);

  const isDirty = useMemo(() => {
    if (!draft || !original) return false;
    return (
      draft.name !== original.name ||
      draft.description !== original.description ||
      draft.systemPrompt !== original.systemPrompt
    );
  }, [draft, original]);

  const filteredSpecialists = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return specialists;
    return specialists.filter(
      (s) =>
        s.id.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        s.stage.toLowerCase().includes(q) ||
        s.pipelineNode.toLowerCase().includes(q) ||
        (s.tags && s.tags.some((t) => t.toLowerCase().includes(q)))
    );
  }, [specialists, search]);

  // Live check of canonical H2 sections in the current draft markdown
  const liveSectionStatus = useMemo(() => {
    const text = draft?.systemPrompt || "";
    return {
      taskAndInputs: /^##\s+Task and inputs/im.test(text),
      outputContract: /^##\s+Output contract/im.test(text),
      boundaryAndHandoff: /^##\s+Boundary and handoff/im.test(text),
    };
  }, [draft?.systemPrompt]);

  const handleSelect = (s: Specialist) => {
    if (isDirty) {
      if (!window.confirm(`Discard unsaved changes in "${draft?.name}"?`)) {
        return;
      }
    }
    setSelectedId(s.id);
    setDraft({ ...s });
    setOriginal({ ...s });
    fetchTracesForSpecialist(s.id);
  };

  const handleSave = useCallback(async () => {
    if (!draft) return;
    setIsSaving(true);
    try {
      const res = await fetch(
        `/api/specialists/${encodeURIComponent(draft.id)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: draft.name,
            description: draft.description,
            role: draft.description,
            systemPrompt: draft.systemPrompt,
          }),
        }
      );
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Save failed");
      }
      const saved: Specialist = data.specialist;
      setDraft({ ...saved });
      setOriginal({ ...saved });
      triggerToast(`Saved ${saved.filename}`);
      fetchSpecialists(saved.id);
    } catch (err: any) {
      triggerToast(err.message);
    } finally {
      setIsSaving(false);
    }
  }, [draft, fetchSpecialists, triggerToast]);

  const handleRevert = () => {
    if (!original) return;
    setDraft({ ...original });
    triggerToast("Reverted changes");
  };

  const handleDelete = async () => {
    if (!draft) return;
    try {
      const res = await fetch(
        `/api/specialists/${encodeURIComponent(draft.id)}`,
        {
          method: "DELETE",
        }
      );
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Delete failed");
      }
      triggerToast(`Deleted ${draft.filename}`);
      setShowDeleteModal(false);
      setSelectedId(null);
      setDraft(null);
      setOriginal(null);
      fetchSpecialists();
    } catch (err: any) {
      triggerToast(err.message);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanId = newForm.id
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9-_]/g, "-")
      .replace(/-+/g, "-");

    if (!cleanId) return;

    const payload = {
      id: cleanId,
      name: newForm.name.trim() || cleanId,
      description:
        newForm.description.trim() ||
        "Specialist skill contract for Patch2Proof.",
      systemPrompt: newForm.systemPrompt,
    };

    try {
      const res = await fetch("/api/specialists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Failed to create specialist");
      }
      triggerToast(`Created specialists/${cleanId}/SKILL.md`);
      setShowCreateModal(false);
      setNewForm({
        id: "",
        name: "",
        description: "",
        systemPrompt: `# custom-specialist\n\n## Task and inputs\n\nDescribe the specialist task and the artifacts it consumes.\n\n## Output contract\n\nReturn JSON matching the target schema.\n\n## Boundary and handoff\n\nKeep reasoning evidence-grounded and deterministic.\n`,
      });
      fetchSpecialists(cleanId);
    } catch (err: any) {
      triggerToast(err.message);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (isDirty) handleSave();
      }
      if (e.key === "Escape") {
        setShowCreateModal(false);
        setShowDeleteModal(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isDirty, handleSave]);

  const handleTextareaKeyDown = (
    e: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const target = e.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const val = target.value;
      const updated = val.substring(0, start) + "  " + val.substring(end);
      if (draft) {
        setDraft({ ...draft, systemPrompt: updated });
      }
      setTimeout(() => {
        target.selectionStart = target.selectionEnd = start + 2;
      }, 0);
    }
  };

  const jumpToSection = (heading: string) => {
    setMode("markdown");
    setTimeout(() => {
      const el = textareaRef.current;
      if (!el || !draft) return;
      const idx = draft.systemPrompt
        .toLowerCase()
        .indexOf(`## ${heading.toLowerCase()}`);
      if (idx !== -1) {
        el.focus();
        el.setSelectionRange(idx, idx);
      }
    }, 20);
  };

  const appendMissingSection = (heading: string, placeholder: string) => {
    if (!draft) return;
    const suffix = `\n\n## ${heading}\n\n${placeholder}\n`;
    setDraft({
      ...draft,
      systemPrompt: draft.systemPrompt.trimEnd() + suffix,
    });
  };

  const lineCount = useMemo(() => {
    if (!draft) return 0;
    return (draft.systemPrompt.match(/\n/g) || []).length + 1;
  }, [draft]);

  const activeCaseTrace = useMemo(() => {
    if (!traces.length) return null;
    return (
      traces.find((t) => t.caseId === selectedCaseId) || traces[0] || null
    );
  }, [traces, selectedCaseId]);

  const activeArtifact = useMemo(() => {
    if (!activeCaseTrace) return null;
    return (
      activeCaseTrace.artifacts.find(
        (a) => a.filename === selectedArtifactFile
      ) ||
      activeCaseTrace.artifacts[0] ||
      null
    );
  }, [activeCaseTrace, selectedArtifactFile]);

  return (
    <div className="flex-1 flex min-w-0 h-full overflow-hidden">
      {/* REGION 2: SPECIALIST INDEX COLUMN (256px) */}
      <section className="w-64 border-r border-[var(--line)] flex flex-col justify-between py-7 px-6 shrink-0 select-none">
        <div className="space-y-6 overflow-hidden flex flex-col flex-1">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-[10px] text-[var(--ink-tertiary)] uppercase tracking-wider">
              Specialists / {String(specialists.length).padStart(2, "0")}
            </span>
            <button
              onClick={() => setShowCreateModal(true)}
              className="font-mono text-[11px] text-[var(--ink)] hover:opacity-60 transition"
            >
              + New
            </button>
          </div>

          {/* Borderless search line */}
          <div>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter skills..."
              className="w-full bg-transparent border-b border-[var(--line)] pb-1.5 text-xs text-[var(--ink)] placeholder-[var(--ink-tertiary)] focus:outline-none focus:border-[var(--ink)] transition font-mono"
            />
          </div>

          {/* Pipeline-ordered typographic list */}
          <div className="divide-y divide-[var(--line-subtle)] overflow-y-auto flex-1 pr-1">
            {loading && specialists.length === 0 ? (
              <div className="py-4 font-mono text-[11px] text-[var(--ink-tertiary)]">
                Loading specialists...
              </div>
            ) : filteredSpecialists.length === 0 ? (
              <div className="py-4 font-mono text-[11px] text-[var(--ink-tertiary)]">
                No matches
              </div>
            ) : (
              filteredSpecialists.map((s) => {
                const isSelected = s.id === selectedId;
                const orderPrefix =
                  s.stageOrder < 99
                    ? String(s.stageOrder).padStart(2, "0")
                    : "—";
                return (
                  <div
                    key={s.id}
                    onClick={() => handleSelect(s)}
                    className={`py-3 cursor-pointer transition ${
                      isSelected
                        ? "opacity-100"
                        : "opacity-50 hover:opacity-100"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <div className="flex items-baseline gap-2 min-w-0">
                        <span className="font-mono text-[10px] text-[var(--ink-tertiary)] shrink-0">
                          {orderPrefix}
                        </span>
                        <span
                          className={`text-xs truncate ${
                            isSelected
                              ? "font-medium text-[var(--ink)]"
                              : "text-[var(--ink)]"
                          }`}
                        >
                          {s.name}
                        </span>
                      </div>
                      <span className="font-mono text-[10px] text-[var(--ink-tertiary)] shrink-0">
                        {s.links?.length || 0} ref
                      </span>
                    </div>
                    <div className="font-mono text-[10px] text-[var(--ink-tertiary)] mt-0.5 pl-5 truncate">
                      {s.filename}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="font-mono text-[10px] text-[var(--ink-tertiary)] pt-4 border-t border-[var(--line-subtle)] flex items-center justify-between">
          <span>specialists/*/SKILL.md</span>
          <span>SHA-256</span>
        </div>
      </section>

      {/* REGION 3, 4, 5: EDITORIAL WORKBENCH SHEET */}
      <main className="flex-1 overflow-y-auto px-10 lg:px-16 py-10 select-text">
        {draft ? (
          <div className="max-w-3xl mx-auto space-y-8">
            {/* Document Top Header: Title + Description + Quiet Text Actions */}
            <div className="flex items-baseline justify-between gap-6 border-b border-[var(--line)] pb-5">
              <div className="flex-1 min-w-0">
                <input
                  type="text"
                  value={draft.name}
                  onChange={(e) =>
                    setDraft({ ...draft, name: e.target.value })
                  }
                  className="spec-input text-xl font-medium tracking-tight text-[var(--ink)] w-full font-mono"
                />
                <input
                  type="text"
                  value={draft.description}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      description: e.target.value,
                      role: e.target.value,
                    })
                  }
                  className="spec-input text-xs text-[var(--ink-secondary)] mt-1 w-full"
                />
              </div>

              <div className="flex items-center gap-5 font-mono text-xs shrink-0 select-none">
                {isDirty && (
                  <button
                    onClick={handleRevert}
                    className="text-[var(--ink-tertiary)] hover:text-[var(--ink)] transition"
                  >
                    Revert
                  </button>
                )}
                <button
                  onClick={() => setShowDeleteModal(true)}
                  className="text-[var(--ink-tertiary)] hover:text-red-600 transition"
                >
                  Delete
                </button>
                <button
                  onClick={handleSave}
                  disabled={isSaving || !isDirty}
                  className={`px-3 py-1 bg-[var(--ink)] text-[var(--bg)] rounded-[2px] transition ${
                    isDirty
                      ? "hover:opacity-85"
                      : "opacity-30 cursor-default"
                  }`}
                >
                  {isSaving ? "Saving..." : "Save"}
                </button>
              </div>
            </div>

            {/* REGION 4: INLINE SPECIFICATION TABLE */}
            <div className="space-y-1.5">
              <div className="pb-1 flex items-baseline justify-between">
                <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                  Specification
                </span>
                <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                  node: {draft.pipelineNode}
                </span>
              </div>

              <div className="grid grid-cols-[120px_1fr] gap-y-2 text-xs items-baseline">
                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  path
                </span>
                <span className="font-mono text-[11px] text-[var(--ink)]">
                  {draft.filename}
                </span>

                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  skill_sha256
                </span>
                <div className="flex items-baseline gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard?.writeText(draft.skillSha256);
                      triggerToast("Copied skill_sha256 to clipboard");
                    }}
                    title="Click to copy full SHA-256 digest"
                    className="font-mono text-[11px] text-[var(--ink-secondary)] hover:text-[var(--ink)] transition text-left"
                  >
                    {draft.skillSha256.slice(0, 16)}…
                    {draft.skillSha256.slice(-8)}
                  </button>
                  {isDirty && (
                    <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                      (modified in buffer)
                    </span>
                  )}
                </div>

                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  stage
                </span>
                <span className="font-mono text-[11px] text-[var(--ink-secondary)]">
                  {draft.stage}
                </span>

                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  sections
                </span>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px]">
                  <button
                    type="button"
                    onClick={() => jumpToSection("Task and inputs")}
                    className={`hover:underline ${
                      liveSectionStatus.taskAndInputs
                        ? "text-[var(--ink)]"
                        : "text-[var(--ink-tertiary)] line-through"
                    }`}
                  >
                    Task & inputs {liveSectionStatus.taskAndInputs ? "✓" : "×"}
                  </button>
                  <span className="text-[var(--line)]">·</span>
                  <button
                    type="button"
                    onClick={() => jumpToSection("Output contract")}
                    className={`hover:underline ${
                      liveSectionStatus.outputContract
                        ? "text-[var(--ink)]"
                        : "text-[var(--ink-tertiary)] line-through"
                    }`}
                  >
                    Output contract{" "}
                    {liveSectionStatus.outputContract ? "✓" : "×"}
                  </button>
                  <span className="text-[var(--line)]">·</span>
                  <button
                    type="button"
                    onClick={() => jumpToSection("Boundary and handoff")}
                    className={`hover:underline ${
                      liveSectionStatus.boundaryAndHandoff
                        ? "text-[var(--ink)]"
                        : "text-[var(--ink-tertiary)] line-through"
                    }`}
                  >
                    Boundary & handoff{" "}
                    {liveSectionStatus.boundaryAndHandoff ? "✓" : "×"}
                  </button>
                </div>

                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  contracts
                </span>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px]">
                  {draft.links && draft.links.length > 0 ? (
                    draft.links.map((link, idx) => (
                      <React.Fragment key={link.resolvedPath}>
                        {idx > 0 && (
                          <span className="text-[var(--line)]">·</span>
                        )}
                        <button
                          type="button"
                          onClick={() => setMode("contract")}
                          className="text-[var(--ink-secondary)] hover:text-[var(--ink)] hover:underline transition"
                        >
                          {link.resolvedPath}
                        </button>
                      </React.Fragment>
                    ))
                  ) : (
                    <span className="text-[var(--ink-tertiary)]">
                      none linked
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* REGION 5: ARCHITECTURAL FRAMED WORKBENCH */}
            <div className="border border-[var(--line)] bg-[var(--surface)] rounded-[2px] transition-colors duration-200 focus-within:border-[var(--ink-secondary)] shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
              {/* Framed Top Hairline Strip: Mode Switcher + Context Meta */}
              <div className="px-5 py-2.5 border-b border-[var(--line-subtle)] flex flex-wrap items-center justify-between gap-4 select-none">
                <div className="flex items-center gap-5 font-mono text-[11px]">
                  <button
                    type="button"
                    onClick={() => setMode("markdown")}
                    className={`transition ${
                      mode === "markdown"
                        ? "text-[var(--ink)] font-medium underline underline-offset-4"
                        : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                    }`}
                  >
                    01 Skill Markdown
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("contract")}
                    className={`transition ${
                      mode === "contract"
                        ? "text-[var(--ink)] font-medium underline underline-offset-4"
                        : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                    }`}
                  >
                    02 Contract & Schemas ({draft.links?.length || 0})
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("traces")}
                    className={`transition ${
                      mode === "traces"
                        ? "text-[var(--ink)] font-medium underline underline-offset-4"
                        : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                    }`}
                  >
                    03 Case Traces ({traces.length})
                  </button>
                </div>

                {/* Right-side contextual strip */}
                {mode === "markdown" && (
                  <div className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                    {lineCount} lines • {draft.systemPrompt.length} chars
                  </div>
                )}

                {mode === "contract" && (
                  <div className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                    {draft.links?.length || 0} linked references
                  </div>
                )}

                {mode === "traces" && traces.length > 0 && (
                  <div className="flex items-center gap-2 font-mono text-[10px]">
                    <span className="text-[var(--ink-tertiary)]">case:</span>
                    {traces.map((t, idx) => (
                      <React.Fragment key={t.caseId}>
                        {idx > 0 && (
                          <span className="text-[var(--line)]">/</span>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedCaseId(t.caseId);
                            const defaultArt =
                              t.artifacts.find((a) => a.role === "output") ||
                              t.artifacts[0];
                            setSelectedArtifactFile(
                              defaultArt ? defaultArt.filename : null
                            );
                          }}
                          className={`transition ${
                            activeCaseTrace?.caseId === t.caseId
                              ? "text-[var(--ink)] font-medium underline underline-offset-4"
                              : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                          }`}
                        >
                          {t.caseId}
                        </button>
                      </React.Fragment>
                    ))}
                  </div>
                )}
              </div>

              {/* MODE 01: SKILL MARKDOWN EDITOR */}
              {mode === "markdown" && (
                <div>
                  <textarea
                    ref={textareaRef}
                    rows={Math.max(lineCount + 2, 18)}
                    value={draft.systemPrompt}
                    onChange={(e) =>
                      setDraft({ ...draft, systemPrompt: e.target.value })
                    }
                    onKeyDown={handleTextareaKeyDown}
                    spellCheck={false}
                    className="w-full px-6 py-5 bg-transparent font-mono text-[13px] text-[var(--ink)] leading-7 resize-none focus:outline-none block selection:bg-stone-200 dark:selection:bg-stone-800"
                  />

                  {/* Subtle bottom bar inside frame if any canonical section is missing */}
                  {(!liveSectionStatus.taskAndInputs ||
                    !liveSectionStatus.outputContract ||
                    !liveSectionStatus.boundaryAndHandoff) && (
                    <div className="px-6 py-2.5 border-t border-[var(--line-subtle)] flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-[var(--ink-secondary)]">
                      <span>Missing canonical SKILL.md section:</span>
                      <div className="flex items-center gap-3">
                        {!liveSectionStatus.taskAndInputs && (
                          <button
                            type="button"
                            onClick={() =>
                              appendMissingSection(
                                "Task and inputs",
                                "Describe the task and input artifacts."
                              )
                            }
                            className="hover:text-[var(--ink)] underline"
                          >
                            + Task and inputs
                          </button>
                        )}
                        {!liveSectionStatus.outputContract && (
                          <button
                            type="button"
                            onClick={() =>
                              appendMissingSection(
                                "Output contract",
                                "Return JSON matching the target schema."
                              )
                            }
                            className="hover:text-[var(--ink)] underline"
                          >
                            + Output contract
                          </button>
                        )}
                        {!liveSectionStatus.boundaryAndHandoff && (
                          <button
                            type="button"
                            onClick={() =>
                              appendMissingSection(
                                "Boundary and handoff",
                                "Define execution and safety boundaries."
                              )
                            }
                            className="hover:text-[var(--ink)] underline"
                          >
                            + Boundary and handoff
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* MODE 02: CONTRACT & SCHEMAS INSPECTOR */}
              {mode === "contract" && (
                <div className="divide-y divide-[var(--line-subtle)]">
                  {/* Canonical Sections Breakdown */}
                  <div className="p-6 space-y-5">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                      Canonical Skill Structure
                    </div>

                    <div className="grid grid-cols-1 gap-5">
                      <div className="space-y-1.5">
                        <div className="font-mono text-xs font-medium text-[var(--ink)]">
                          § 01 · Task and inputs
                        </div>
                        <p className="text-xs text-[var(--ink-secondary)] leading-relaxed whitespace-pre-wrap font-mono">
                          {draft.sections?.taskAndInputs ||
                            "No `## Task and inputs` section parsed."}
                        </p>
                      </div>

                      <div className="space-y-1.5 pt-4 border-t border-[var(--line-subtle)]">
                        <div className="font-mono text-xs font-medium text-[var(--ink)]">
                          § 02 · Output contract
                        </div>
                        <p className="text-xs text-[var(--ink-secondary)] leading-relaxed whitespace-pre-wrap font-mono">
                          {draft.sections?.outputContract ||
                            "No `## Output contract` section parsed."}
                        </p>
                      </div>

                      <div className="space-y-1.5 pt-4 border-t border-[var(--line-subtle)]">
                        <div className="font-mono text-xs font-medium text-[var(--ink)]">
                          § 03 · Boundary and handoff
                        </div>
                        <p className="text-xs text-[var(--ink-secondary)] leading-relaxed whitespace-pre-wrap font-mono">
                          {draft.sections?.boundaryAndHandoff ||
                            "No `## Boundary and handoff` section parsed."}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Linked JSON Schemas */}
                  {draft.schemas && draft.schemas.length > 0 ? (
                    draft.schemas.map((schema) => {
                      const isRawOpen = !!showRawSchema[schema.relativePath];
                      return (
                        <div key={schema.relativePath} className="p-6 space-y-4">
                          <div className="flex items-baseline justify-between gap-4">
                            <div>
                              <div className="font-mono text-xs font-medium text-[var(--ink)]">
                                {schema.title}
                              </div>
                              <div className="font-mono text-[11px] text-[var(--ink-tertiary)] mt-0.5">
                                {schema.relativePath} ·{" "}
                                {schema.properties.length} properties (
                                {schema.required.length} required)
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() =>
                                setShowRawSchema((prev) => ({
                                  ...prev,
                                  [schema.relativePath]: !isRawOpen,
                                }))
                              }
                              className="font-mono text-[11px] text-[var(--ink-secondary)] hover:text-[var(--ink)] underline underline-offset-4"
                            >
                              {isRawOpen ? "Table view" : "Raw schema.json"}
                            </button>
                          </div>

                          {isRawOpen ? (
                            <pre className="p-4 bg-[var(--bg)] border border-[var(--line-subtle)] font-mono text-[11px] text-[var(--ink)] overflow-x-auto leading-relaxed">
                              {JSON.stringify(schema.raw, null, 2)}
                            </pre>
                          ) : (
                            <div className="divide-y divide-[var(--line-subtle)] border-t border-b border-[var(--line-subtle)]">
                              <div className="grid grid-cols-[180px_110px_80px_1fr] py-2 font-mono text-[10px] text-[var(--ink-tertiary)] uppercase tracking-wider">
                                <span>Field</span>
                                <span>Type</span>
                                <span>Constraint</span>
                                <span>Values / Notes</span>
                              </div>
                              {schema.properties.map((prop) => (
                                <div
                                  key={prop.name}
                                  className="grid grid-cols-[180px_110px_80px_1fr] py-2.5 font-mono text-[11px] items-baseline gap-2"
                                >
                                  <span className="text-[var(--ink)] truncate">
                                    {prop.name}
                                  </span>
                                  <span className="text-[var(--ink-secondary)]">
                                    {prop.type}
                                  </span>
                                  <span
                                    className={
                                      prop.required
                                        ? "text-[var(--ink)]"
                                        : "text-[var(--ink-tertiary)]"
                                    }
                                  >
                                    {prop.required ? "required" : "optional"}
                                  </span>
                                  <span className="text-[var(--ink-secondary)] break-words">
                                    {prop.enumValues
                                      ? `enum: ${prop.enumValues.join(" | ")}`
                                      : prop.description || "—"}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <div className="p-6 font-mono text-xs text-[var(--ink-tertiary)]">
                      No JSON schema files linked in Output contract.
                    </div>
                  )}

                  {/* Linked Repository Files */}
                  <div className="p-6 space-y-3">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                      Repository Contract References
                    </div>
                    <div className="divide-y divide-[var(--line-subtle)]">
                      {draft.links?.map((link) => (
                        <div
                          key={link.resolvedPath}
                          className="py-2 flex items-baseline justify-between font-mono text-xs"
                        >
                          <span className="text-[var(--ink)]">
                            {link.resolvedPath}
                          </span>
                          <span className="text-[10px] text-[var(--ink-tertiary)] uppercase">
                            {link.kind}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* MODE 03: RECORDED CASE TRACES */}
              {mode === "traces" && (
                <div>
                  {tracesLoading ? (
                    <div className="p-6 font-mono text-xs text-[var(--ink-tertiary)]">
                      Loading case traces from artifacts/...
                    </div>
                  ) : !activeCaseTrace ? (
                    <div className="p-6 font-mono text-xs text-[var(--ink-tertiary)]">
                      No recorded case artifacts found for this specialist in
                      artifacts/.
                    </div>
                  ) : (
                    <div className="divide-y divide-[var(--line-subtle)]">
                      {/* Artifact selector strip for the chosen case */}
                      <div className="px-6 py-3 flex flex-wrap items-center justify-between gap-4 bg-[var(--bg)]/50">
                        <div className="flex flex-wrap items-center gap-4 font-mono text-xs">
                          {activeCaseTrace.artifacts.map((art) => {
                            const isCurrent =
                              activeArtifact?.filename === art.filename;
                            return (
                              <button
                                key={art.filename}
                                type="button"
                                onClick={() =>
                                  setSelectedArtifactFile(art.filename)
                                }
                                className={`transition flex items-baseline gap-1.5 ${
                                  isCurrent
                                    ? "text-[var(--ink)] font-medium underline underline-offset-4"
                                    : "text-[var(--ink-secondary)] hover:text-[var(--ink)]"
                                }`}
                              >
                                <span className="text-[10px] uppercase text-[var(--ink-tertiary)]">
                                  [{art.role}]
                                </span>
                                <span>{art.filename}</span>
                              </button>
                            );
                          })}
                        </div>
                        {activeArtifact && (
                          <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                            {activeArtifact.relativePath} (
                            {activeArtifact.sizeBytes} B)
                          </span>
                        )}
                      </div>

                      {/* Formatted JSON Trace Payload */}
                      {activeArtifact && (
                        <div className="p-6 space-y-3">
                          <div className="flex items-baseline justify-between">
                            <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                              {activeArtifact.role} artifact payload
                            </span>
                            <button
                              type="button"
                              onClick={() => {
                                navigator.clipboard?.writeText(
                                  JSON.stringify(
                                    activeArtifact.preview,
                                    null,
                                    2
                                  )
                                );
                                triggerToast(
                                  `Copied ${activeArtifact.filename}`
                                );
                              }}
                              className="font-mono text-[11px] text-[var(--ink-tertiary)] hover:text-[var(--ink)] transition"
                            >
                              Copy JSON
                            </button>
                          </div>
                          <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto max-h-[540px]">
                            {JSON.stringify(activeArtifact.preview, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="max-w-2xl mx-auto py-20 font-mono text-xs text-[var(--ink-tertiary)]">
            Select a specialist from the index.
          </div>
        )}
      </main>

      {/* QUIET MONOSPACE TOAST */}
      {toastMessage && (
        <div className="fixed bottom-6 right-8 z-50 font-mono text-[11px] px-3 py-1.5 bg-[var(--ink)] text-[var(--bg)] rounded-[2px]">
          {toastMessage}
        </div>
      )}

      {/* MINIMAL CREATE MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/25 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-[var(--bg)] border border-[var(--line)] p-6 space-y-5">
            <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-3">
              <h3 className="text-sm font-medium text-[var(--ink)]">
                New Specialist Skill
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="font-mono text-xs text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
              >
                Esc
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4 text-xs">
              <div className="grid grid-cols-[100px_1fr] items-baseline gap-y-3">
                <label className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  id (folder)
                </label>
                <input
                  type="text"
                  required
                  value={newForm.id}
                  onChange={(e) => {
                    const slug = e.target.value
                      .toLowerCase()
                      .replace(/[^a-z0-9-_]/g, "-");
                    setNewForm({
                      ...newForm,
                      id: slug,
                      name: slug,
                    });
                  }}
                  placeholder="sanitizer-triage"
                  className="bg-transparent border-b border-[var(--line)] pb-1 font-mono text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                />

                <label className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  description
                </label>
                <input
                  type="text"
                  required
                  value={newForm.description}
                  onChange={(e) =>
                    setNewForm({ ...newForm, description: e.target.value })
                  }
                  placeholder="Interpret sanitizer traces and extract root-cause frames."
                  className="bg-transparent border-b border-[var(--line)] pb-1 text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                />
              </div>

              <div className="font-mono text-[10px] text-[var(--ink-tertiary)] pt-1">
                Creates specialists/{newForm.id || "<id>"}/SKILL.md
              </div>

              <div className="flex justify-end gap-4 pt-4 border-t border-[var(--line)] font-mono text-xs">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1 bg-[var(--ink)] text-[var(--bg)] rounded-[2px]"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MINIMAL DELETE MODAL */}
      {showDeleteModal && draft && (
        <div className="fixed inset-0 z-50 bg-black/25 flex items-center justify-center p-4">
          <div className="w-full max-w-sm bg-[var(--bg)] border border-[var(--line)] p-6 space-y-4">
            <h3 className="text-sm font-medium text-[var(--ink)]">
              Delete {draft.name}?
            </h3>
            <p className="text-xs text-[var(--ink-secondary)] font-mono">
              {draft.filename} will be removed from disk.
            </p>
            <div className="flex justify-end gap-4 pt-3 border-t border-[var(--line)] font-mono text-xs">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="px-3 py-1 bg-red-600 text-white rounded-[2px]"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
