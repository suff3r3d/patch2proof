"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";

interface Specialist {
  id: string;
  name: string;
  role: string;
  stage: string;
  model?: string;
  temperature?: number;
  tags?: string[];
  systemPrompt: string;
  filename: string;
  updatedAt?: string;
}

const STAGE_LABELS: Record<string, string> = {
  hypothesis: "hypothesis",
  safe_poc_plan: "plan",
  repair: "repair",
  review: "review",
  general: "general",
};

export default function SpecialistsStudioPage() {
  const [specialists, setSpecialists] = useState<Specialist[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Specialist | null>(null);
  const [original, setOriginal] = useState<Specialist | null>(null);
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [search, setSearch] = useState("");

  // Modals & Toast
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const [newForm, setNewForm] = useState({
    id: "",
    name: "",
    role: "",
    stage: "hypothesis",
    model: "default",
    temperature: 0.0,
    tags: "diff-analysis, hypothesis",
    systemPrompt: `# Specialist prompt\n\nYou are a defensive software-security analyst.\n`,
  });

  const triggerToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 2800);
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
            const match = data.specialists.find(
              (s: Specialist) => s.id === targetId
            );
            if (match) {
              setSelectedId(match.id);
              setDraft({ ...match });
              setOriginal({ ...match });
            } else if (data.specialists.length > 0) {
              setSelectedId(data.specialists[0].id);
              setDraft({ ...data.specialists[0] });
              setOriginal({ ...data.specialists[0] });
            }
          }
        }
      } catch (err: any) {
        triggerToast(err.message || "Failed to load specialists");
      } finally {
        setLoading(false);
      }
    },
    [selectedId, triggerToast]
  );

  useEffect(() => {
    fetchSpecialists();
  }, []);

  const isDirty = useMemo(() => {
    if (!draft || !original) return false;
    return (
      draft.name !== original.name ||
      draft.role !== original.role ||
      draft.stage !== original.stage ||
      draft.model !== original.model ||
      draft.temperature !== original.temperature ||
      draft.systemPrompt !== original.systemPrompt ||
      JSON.stringify(draft.tags || []) !== JSON.stringify(original.tags || [])
    );
  }, [draft, original]);

  const filteredSpecialists = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return specialists;
    return specialists.filter(
      (s) =>
        s.id.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.role.toLowerCase().includes(q) ||
        s.stage.toLowerCase().includes(q) ||
        (s.tags && s.tags.some((t) => t.toLowerCase().includes(q)))
    );
  }, [specialists, search]);

  const handleSelect = (s: Specialist) => {
    if (isDirty) {
      if (
        !window.confirm(
          `Discard unsaved changes in "${draft?.name}"?`
        )
      ) {
        return;
      }
    }
    setSelectedId(s.id);
    setDraft({ ...s });
    setOriginal({ ...s });
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
          body: JSON.stringify(draft),
        }
      );
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Save failed");
      }
      setOriginal({ ...draft });
      triggerToast(`Saved ${draft.filename}`);
      fetchSpecialists(draft.id);
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
      role: newForm.role.trim() || "Defensive security reasoning specialist",
      stage: newForm.stage,
      model: newForm.model.trim() || "default",
      temperature: Number(newForm.temperature),
      tags: newForm.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
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
      triggerToast(`Created ${cleanId}.md`);
      setShowCreateModal(false);
      setNewForm({
        id: "",
        name: "",
        role: "",
        stage: "hypothesis",
        model: "default",
        temperature: 0.0,
        tags: "diff-analysis, hypothesis",
        systemPrompt: `# Specialist prompt\n\nYou are a defensive software-security analyst.\n`,
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

  const lineCount = useMemo(() => {
    if (!draft) return 0;
    return (draft.systemPrompt.match(/\n/g) || []).length + 1;
  }, [draft]);

  return (
    <div className="flex-1 flex min-w-0 h-full overflow-hidden">
      {/* REGION 2: SPECIALIST INDEX COLUMN (240px) */}
      <section className="w-60 border-r border-[var(--line)] flex flex-col justify-between py-7 px-6 shrink-0 select-none">
        <div className="space-y-6 overflow-hidden flex flex-col">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
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
              placeholder="Filter..."
              className="w-full bg-transparent border-b border-[var(--line)] pb-1.5 text-xs text-[var(--ink)] placeholder-[var(--ink-tertiary)] focus:outline-none focus:border-[var(--ink)] transition font-mono"
            />
          </div>

          {/* Clean typographic list separated by subtle hairlines */}
          <div className="divide-y divide-[var(--line-subtle)] overflow-y-auto flex-1">
            {loading && specialists.length === 0 ? (
              <div className="py-4 font-mono text-[11px] text-[var(--ink-tertiary)]">
                Loading...
              </div>
            ) : filteredSpecialists.length === 0 ? (
              <div className="py-4 font-mono text-[11px] text-[var(--ink-tertiary)]">
                No matches
              </div>
            ) : (
              filteredSpecialists.map((s) => {
                const isSelected = s.id === selectedId;
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
                      <span
                        className={`text-xs truncate ${
                          isSelected
                            ? "font-medium text-[var(--ink)]"
                            : "text-[var(--ink)]"
                        }`}
                      >
                        {s.name}
                      </span>
                      <span className="font-mono text-[10px] text-[var(--ink-tertiary)] shrink-0">
                        {STAGE_LABELS[s.stage] || s.stage}
                      </span>
                    </div>
                    <div className="font-mono text-[10px] text-[var(--ink-tertiary)] mt-0.5 truncate">
                      {s.filename}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="font-mono text-[10px] text-[var(--ink-tertiary)] pt-4">
          config/prompts/*.md
        </div>
      </section>

      {/* REGION 3, 4, 5: EDITORIAL DOCUMENT SHEET */}
      <main className="flex-1 overflow-y-auto px-10 lg:px-20 py-10 select-text">
        {draft ? (
          <div className="max-w-2xl mx-auto space-y-8">
            {/* Document Top Header: Title + Quiet Text Actions */}
            <div className="flex items-baseline justify-between gap-6 border-b border-[var(--line)] pb-5">
              <div className="flex-1 min-w-0">
                <input
                  type="text"
                  value={draft.name}
                  onChange={(e) =>
                    setDraft({ ...draft, name: e.target.value })
                  }
                  className="spec-input text-xl font-medium tracking-tight text-[var(--ink)] w-full"
                />
                <input
                  type="text"
                  value={draft.role}
                  onChange={(e) =>
                    setDraft({ ...draft, role: e.target.value })
                  }
                  className="spec-input text-xs text-[var(--ink-secondary)] mt-0.5 w-full"
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
                  className={`px-3 py-1 bg-[var(--ink)] text-[var(--bg)] rounded-[3px] transition ${
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
            <div className="space-y-1">
              <div className="pb-1">
                <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                  Specification
                </span>
              </div>

              <div className="grid grid-cols-[120px_1fr] gap-y-1.5 text-xs items-baseline">
                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  file
                </span>
                <span className="font-mono text-[11px] text-[var(--ink-secondary)]">
                  config/prompts/{draft.filename}
                </span>

                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  stage
                </span>
                <div>
                  <select
                    value={draft.stage}
                    onChange={(e) =>
                      setDraft({ ...draft, stage: e.target.value })
                    }
                    className="spec-input font-mono text-xs cursor-pointer"
                  >
                    <option value="hypothesis">
                      hypothesis (reasoning node)
                    </option>
                    <option value="safe_poc_plan">
                      safe_poc_plan (poc_reasoning node)
                    </option>
                    <option value="repair">
                      repair (repair_reasoning node)
                    </option>
                    <option value="review">review (skeptic node)</option>
                    <option value="general">general (orchestration)</option>
                  </select>
                </div>

                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  model
                </span>
                <div>
                  <input
                    type="text"
                    value={draft.model || "default"}
                    onChange={(e) =>
                      setDraft({ ...draft, model: e.target.value })
                    }
                    className="spec-input font-mono text-xs w-48"
                  />
                </div>

                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  temperature
                </span>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={draft.temperature ?? 0}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        temperature: parseFloat(e.target.value),
                      })
                    }
                    className="w-32"
                  />
                  <span className="font-mono text-[11px] text-[var(--ink)]">
                    {Number(draft.temperature ?? 0).toFixed(2)}
                  </span>
                </div>

                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  tags
                </span>
                <div>
                  <input
                    type="text"
                    value={(draft.tags || []).join(", ")}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        tags: e.target.value
                          .split(",")
                          .map((t) => t.trim())
                          .filter(Boolean),
                      })
                    }
                    className="spec-input font-mono text-xs w-full max-w-sm text-[var(--ink-secondary)]"
                  />
                </div>
              </div>
            </div>

            {/* REGION 5: FRAMED EDITORIAL PROMPT CANVAS */}
            <div className="border border-[var(--line)] bg-[var(--surface)] rounded-[2px] transition-colors duration-200 focus-within:border-[var(--ink-secondary)] shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
              <div className="px-5 py-2.5 border-b border-[var(--line-subtle)] flex items-center justify-between select-none">
                <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                  System Prompt
                </span>
                <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                  {lineCount} lines • {draft.systemPrompt.length} chars
                </span>
              </div>

              <textarea
                rows={Math.max(lineCount + 2, 16)}
                value={draft.systemPrompt}
                onChange={(e) =>
                  setDraft({ ...draft, systemPrompt: e.target.value })
                }
                onKeyDown={handleTextareaKeyDown}
                spellCheck={false}
                className="w-full px-6 py-5 bg-transparent font-mono text-[13px] text-[var(--ink)] leading-7 resize-none focus:outline-none block selection:bg-stone-200 dark:selection:bg-stone-800"
              />
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
        <div className="fixed bottom-6 right-8 z-50 font-mono text-[11px] px-3 py-1.5 bg-[var(--ink)] text-[var(--bg)] rounded-[3px]">
          {toastMessage}
        </div>
      )}

      {/* MINIMAL CREATE MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/25 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-[var(--bg)] border border-[var(--line)] p-6 space-y-5">
            <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-3">
              <h3 className="text-sm font-medium text-[var(--ink)]">
                New Specialist
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
                  id (slug)
                </label>
                <input
                  type="text"
                  required
                  value={newForm.id}
                  onChange={(e) =>
                    setNewForm({
                      ...newForm,
                      id: e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9-_]/g, "-"),
                    })
                  }
                  placeholder="taint-tracker"
                  className="bg-transparent border-b border-[var(--line)] pb-1 font-mono text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                />

                <label className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  name
                </label>
                <input
                  type="text"
                  required
                  value={newForm.name}
                  onChange={(e) =>
                    setNewForm({ ...newForm, name: e.target.value })
                  }
                  placeholder="Taint Propagation Tracker"
                  className="bg-transparent border-b border-[var(--line)] pb-1 text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                />

                <label className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  role
                </label>
                <input
                  type="text"
                  required
                  value={newForm.role}
                  onChange={(e) =>
                    setNewForm({ ...newForm, role: e.target.value })
                  }
                  placeholder="Traces untrusted input to sink"
                  className="bg-transparent border-b border-[var(--line)] pb-1 text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                />

                <label className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  stage
                </label>
                <select
                  value={newForm.stage}
                  onChange={(e) =>
                    setNewForm({ ...newForm, stage: e.target.value })
                  }
                  className="bg-transparent border-b border-[var(--line)] pb-1 font-mono text-xs text-[var(--ink)] focus:outline-none"
                >
                  <option value="hypothesis">hypothesis</option>
                  <option value="safe_poc_plan">safe_poc_plan</option>
                  <option value="repair">repair</option>
                  <option value="review">review</option>
                  <option value="general">general</option>
                </select>
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
                  className="px-3 py-1 bg-[var(--ink)] text-[var(--bg)] rounded-[3px]"
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
              config/prompts/{draft.filename} will be removed from disk.
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
                className="px-3 py-1 bg-red-600 text-white rounded-[3px]"
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
