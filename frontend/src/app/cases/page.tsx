"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useActiveCaseId } from "@/lib/activeCaseClient";

interface CasePolicy {
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
}

interface CaseArtifactFile {
  filename: string;
  relativePath: string;
  kind: "json" | "diff" | "markdown" | "other";
  category: "discovery" | "source" | "reasoning" | "execution" | "proof" | "other";
  sizeBytes: number;
  sha256: string;
  updatedAt: string;
}

interface CaseSummaryRecord {
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

type CaseWorkbenchMode = "manifest" | "artifacts" | "patch";

export default function CasesPage() {
  const [activeCaseId, setActiveCaseId] = useActiveCaseId();
  const [cases, setCases] = useState<CaseSummaryRecord[]>([]);
  const [draft, setDraft] = useState<CaseSummaryRecord | null>(null);
  const [original, setOriginal] = useState<CaseSummaryRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<CaseWorkbenchMode>("manifest");

  // Artifact Explorer state
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [selectedArtifactName, setSelectedArtifactName] = useState<string | null>(null);
  const [artifactContent, setArtifactContent] = useState<{
    content: string;
    parsedJson?: any;
    file: CaseArtifactFile;
  } | null>(null);
  const [artifactLoading, setArtifactLoading] = useState(false);

  // Patch & Discovery bundle state
  const [patchText, setPatchText] = useState<string | null>(null);
  const [discoveryResult, setDiscoveryResult] = useState<any | null>(null);

  // Modals & Toast
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createMode, setCreateMode] = useState<"cve" | "pinned">("cve");
  const [newForm, setNewForm] = useState({
    id: "",
    title: "",
    repository_path: "./examples/fixture-repository",
    source_mode: "git",
    vulnerable_ref: "v1.0.0",
    fixed_ref: "v1.0.1",
    language: "python",
    reasoning_mode: "required",
  });
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const triggerToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 2800);
  }, []);

  const loadArtifactFile = useCallback(async (caseId: string, filename: string) => {
    try {
      setArtifactLoading(true);
      const res = await fetch(
        `/api/cases/${encodeURIComponent(caseId)}?artifact=${encodeURIComponent(
          filename
        )}`
      );
      const data = await res.json();
      if (data.success && data.artifact) {
        setArtifactContent(data.artifact);
      } else {
        setArtifactContent(null);
      }
    } catch {
      setArtifactContent(null);
    } finally {
      setArtifactLoading(false);
    }
  }, []);

  const loadPatchAndDiscovery = useCallback(async (caseId: string) => {
    setPatchText(null);
    setDiscoveryResult(null);
    try {
      const res = await fetch(
        `/api/cases/${encodeURIComponent(caseId)}?bundle=1`
      );
      const data = await res.json();
      if (data.success && data.bundle) {
        if (typeof data.bundle["raw-patch.diff"] === "string") {
          setPatchText(data.bundle["raw-patch.diff"]);
        }
        if (data.bundle["revision-discovery-result.json"]) {
          setDiscoveryResult(data.bundle["revision-discovery-result.json"]);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  const selectCaseRecord = useCallback(
    (record: CaseSummaryRecord) => {
      setActiveCaseId(record.id);
      setDraft(JSON.parse(JSON.stringify(record)));
      setOriginal(JSON.parse(JSON.stringify(record)));
      const preferredFile =
        record.artifactFiles.find((f) => f.filename === "final-report.md") ||
        record.artifactFiles.find((f) => f.filename === "proof-bundle.json") ||
        record.artifactFiles[0];
      if (preferredFile) {
        setSelectedArtifactName(preferredFile.filename);
        loadArtifactFile(record.id, preferredFile.filename);
      } else {
        setSelectedArtifactName(null);
        setArtifactContent(null);
      }
      loadPatchAndDiscovery(record.id);
    },
    [setActiveCaseId, loadArtifactFile, loadPatchAndDiscovery]
  );

  const fetchCases = useCallback(
    async (preferredId?: string) => {
      try {
        setLoading(true);
        const res = await fetch("/api/cases");
        const data = await res.json();
        if (data.success && Array.isArray(data.cases)) {
          setCases(data.cases);
          const targetId = preferredId || activeCaseId || data.cases[0]?.id;
          const match =
            data.cases.find((c: CaseSummaryRecord) => c.id === targetId) ||
            data.cases[0];
          if (match) {
            selectCaseRecord(match);
          }
        }
      } catch (err: any) {
        triggerToast(err.message || "Failed to load cases");
      } finally {
        setLoading(false);
      }
    },
    [activeCaseId, selectCaseRecord, triggerToast]
  );

  useEffect(() => {
    fetchCases();
  }, []);

  // Keep in sync if activeCaseId is changed via sidebar dropdown
  useEffect(() => {
    if (!cases.length) return;
    if (draft?.id === activeCaseId) return;
    const match = cases.find((c) => c.id === activeCaseId);
    if (match) {
      selectCaseRecord(match);
    }
  }, [activeCaseId, cases, draft?.id, selectCaseRecord]);

  const isDirty = useMemo(() => {
    if (!draft || !original) return false;
    return (
      draft.title !== original.title ||
      draft.repository_path !== original.repository_path ||
      draft.source_mode !== original.source_mode ||
      draft.vulnerable_ref !== original.vulnerable_ref ||
      draft.fixed_ref !== original.fixed_ref ||
      draft.language !== original.language ||
      draft.build_system !== original.build_system ||
      draft.advisory !== original.advisory ||
      draft.commit_message !== original.commit_message ||
      draft.dockerfile !== original.dockerfile ||
      draft.registered_test_id !== original.registered_test_id ||
      JSON.stringify(draft.tags) !== JSON.stringify(original.tags) ||
      JSON.stringify(draft.policy) !== JSON.stringify(original.policy)
    );
  }, [draft, original]);

  const filteredCases = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return cases;
    return cases.filter(
      (c) =>
        c.id.toLowerCase().includes(q) ||
        c.title.toLowerCase().includes(q) ||
        c.language.toLowerCase().includes(q) ||
        c.claimStatus.toLowerCase().includes(q)
    );
  }, [cases, search]);

  const filteredArtifacts = useMemo(() => {
    if (!draft) return [];
    if (categoryFilter === "all") return draft.artifactFiles;
    return draft.artifactFiles.filter((f) => f.category === categoryFilter);
  }, [draft, categoryFilter]);

  const handleSave = useCallback(async () => {
    if (!draft) return;
    setIsSaving(true);
    try {
      const res = await fetch(`/api/cases/${encodeURIComponent(draft.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Failed to save case manifest");
      }
      const saved: CaseSummaryRecord = data.caseRecord;
      setDraft(JSON.parse(JSON.stringify(saved)));
      setOriginal(JSON.parse(JSON.stringify(saved)));
      triggerToast(`Saved ${saved.manifestPath}`);
      fetchCases(saved.id);
    } catch (err: any) {
      triggerToast(err.message);
    } finally {
      setIsSaving(false);
    }
  }, [draft, fetchCases, triggerToast]);

  const handleRevert = () => {
    if (!original) return;
    setDraft(JSON.parse(JSON.stringify(original)));
    triggerToast("Reverted changes");
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const rawId = newForm.id.trim();
    if (!rawId) return;

    try {
      const res = await fetch("/api/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          createMode === "cve"
            ? {
                id: rawId,
                reasoning_mode: newForm.reasoning_mode,
              }
            : newForm
        ),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Failed to create case");
      }
      const created: CaseSummaryRecord = data.caseRecord;
      triggerToast(`Created ${created.manifestPath}`);
      setShowCreateModal(false);
      setNewForm({
        id: "",
        title: "",
        repository_path: "./examples/fixture-repository",
        source_mode: "git",
        vulnerable_ref: "v1.0.0",
        fixed_ref: "v1.0.1",
        language: "python",
        reasoning_mode: "required",
      });
      fetchCases(created.id);
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
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isDirty, handleSave]);

  const shortRef = (ref: string) => {
    if (!ref) return "—";
    if (ref.length > 12 && /^[0-9a-f]+$/i.test(ref)) {
      return ref.slice(0, 8);
    }
    return ref;
  };

  return (
    <div className="flex-1 flex min-w-0 h-full overflow-hidden">
      {/* REGION 2: CASE INDEX COLUMN (256px) */}
      <section className="w-64 border-r border-[var(--line)] flex flex-col justify-between py-7 px-6 shrink-0 select-none">
        <div className="space-y-6 overflow-hidden flex flex-col flex-1">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-[10px] text-[var(--ink-tertiary)] uppercase tracking-wider">
              Cases / {String(cases.length).padStart(2, "0")}
            </span>
            <button
              onClick={() => setShowCreateModal(true)}
              className="font-mono text-[11px] text-[var(--ink)] hover:opacity-60 transition"
            >
              + New
            </button>
          </div>

          <div>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter cases..."
              className="w-full bg-transparent border-b border-[var(--line)] pb-1.5 text-xs text-[var(--ink)] placeholder-[var(--ink-tertiary)] focus:outline-none focus:border-[var(--ink)] transition font-mono"
            />
          </div>

          <div className="divide-y divide-[var(--line-subtle)] overflow-y-auto flex-1 pr-1">
            {loading && cases.length === 0 ? (
              <div className="py-4 font-mono text-[11px] text-[var(--ink-tertiary)]">
                Loading cases...
              </div>
            ) : filteredCases.length === 0 ? (
              <div className="py-4 font-mono text-[11px] text-[var(--ink-tertiary)]">
                No matches
              </div>
            ) : (
              filteredCases.map((c) => {
                const isSel = c.id === draft?.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => {
                      if (
                        isDirty &&
                        !window.confirm(`Discard unsaved changes in "${draft?.id}"?`)
                      ) {
                        return;
                      }
                      selectCaseRecord(c);
                    }}
                    className={`py-3 cursor-pointer transition ${
                      isSel ? "opacity-100" : "opacity-50 hover:opacity-100"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span
                        className={`text-xs font-mono truncate ${
                          isSel
                            ? "font-medium text-[var(--ink)]"
                            : "text-[var(--ink)]"
                        }`}
                      >
                        {c.id}
                      </span>
                      <span className="font-mono text-[10px] text-[var(--ink-tertiary)] shrink-0">
                        {c.claimStatus}
                      </span>
                    </div>
                    <div className="text-[11px] text-[var(--ink-secondary)] mt-0.5 truncate">
                      {c.title}
                    </div>
                    <div className="font-mono text-[10px] text-[var(--ink-tertiary)] mt-1 flex items-center justify-between">
                      <span>
                        {shortRef(c.vulnerable_ref)} → {shortRef(c.fixed_ref)}
                      </span>
                      <span>{c.artifactFiles.length} files</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="font-mono text-[10px] text-[var(--ink-tertiary)] pt-4 border-t border-[var(--line-subtle)] flex items-center justify-between">
          <span>examples/*.yaml</span>
          <span>artifacts/*</span>
        </div>
      </section>

      {/* REGION 3, 4, 5: CASE WORKBENCH SHEET */}
      <main className="flex-1 overflow-y-auto px-10 lg:px-16 py-10 select-text">
        {draft ? (
          <div className="max-w-3xl mx-auto space-y-8">
            {/* Top Header */}
            <div className="flex items-baseline justify-between gap-6 border-b border-[var(--line)] pb-5">
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-3">
                  <h1 className="text-xl font-medium tracking-tight font-mono text-[var(--ink)]">
                    {draft.id}
                  </h1>
                  <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                    [{draft.claimStatus}]
                  </span>
                </div>
                <input
                  type="text"
                  value={draft.title}
                  onChange={(e) =>
                    setDraft({ ...draft, title: e.target.value })
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
                  onClick={handleSave}
                  disabled={isSaving || !isDirty}
                  className={`px-3 py-1 bg-[var(--ink)] text-[var(--bg)] rounded-[2px] transition ${
                    isDirty
                      ? "hover:opacity-85"
                      : "opacity-30 cursor-default"
                  }`}
                >
                  {isSaving ? "Saving..." : "Save Manifest"}
                </button>
              </div>
            </div>

            {/* REGION 4: INLINE SPECIFICATION TABLE */}
            <div className="space-y-1.5">
              <div className="pb-1 flex items-baseline justify-between">
                <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                  Case Overview
                </span>
                <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                  active across pipeline views
                </span>
              </div>

              <div className="grid grid-cols-[130px_1fr] gap-y-2 text-xs items-baseline font-mono">
                <span className="text-[11px] text-[var(--ink-tertiary)]">
                  manifest
                </span>
                <span className="text-[11px] text-[var(--ink)]">
                  {draft.manifestPath}
                </span>

                <span className="text-[11px] text-[var(--ink-tertiary)]">
                  artifacts
                </span>
                <span className="text-[11px] text-[var(--ink-secondary)]">
                  {draft.artifactDir
                    ? `${draft.artifactDir}/ (${draft.artifactFiles.length} recorded files)`
                    : "no recorded run artifacts yet"}
                </span>

                <span className="text-[11px] text-[var(--ink-tertiary)]">
                  verdict
                </span>
                <span className="text-[11px] text-[var(--ink)]">
                  {draft.claimStatus} · {draft.gatesPassed} / {draft.gatesTotal}{" "}
                  coverage gates passed
                </span>

                <span className="text-[11px] text-[var(--ink-tertiary)]">
                  revisions
                </span>
                <span className="text-[11px] text-[var(--ink-secondary)] break-all">
                  {shortRef(draft.vulnerable_ref)} (vulnerable) →{" "}
                  {shortRef(draft.fixed_ref)} (fixed)
                  {draft.discoveryStatus
                    ? ` · discovery: ${draft.discoveryStatus}`
                    : ""}
                </span>

                <span className="text-[11px] text-[var(--ink-tertiary)]">
                  isolation
                </span>
                <span className="text-[11px] text-[var(--ink-secondary)]">
                  network: {draft.policy.network} · mem:{" "}
                  {draft.policy.max_memory_mb}MB · cpus:{" "}
                  {draft.policy.max_cpus} · timeout:{" "}
                  {draft.policy.timeout_seconds}s
                </span>
              </div>
            </div>

            {/* REGION 5: FRAMED ARCHITECTURAL WORKBENCH */}
            <div className="border border-[var(--line)] bg-[var(--surface)] rounded-[2px] transition-colors duration-200 focus-within:border-[var(--ink-secondary)] shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
              {/* Top Hairline Strip */}
              <div className="px-5 py-2.5 border-b border-[var(--line-subtle)] flex flex-wrap items-center justify-between gap-4 select-none">
                <div className="flex items-center gap-5 font-mono text-[11px]">
                  <button
                    type="button"
                    onClick={() => setMode("manifest")}
                    className={`transition ${
                      mode === "manifest"
                        ? "text-[var(--ink)] font-medium underline underline-offset-4"
                        : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                    }`}
                  >
                    01 Manifest & Policy
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("artifacts")}
                    className={`transition ${
                      mode === "artifacts"
                        ? "text-[var(--ink)] font-medium underline underline-offset-4"
                        : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                    }`}
                  >
                    02 Artifact Explorer ({draft.artifactFiles.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("patch")}
                    className={`transition ${
                      mode === "patch"
                        ? "text-[var(--ink)] font-medium underline underline-offset-4"
                        : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                    }`}
                  >
                    03 Patch & Discovery
                  </button>
                </div>

                <div className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                  {mode === "manifest" && `${draft.manifestFormat.toUpperCase()} contract`}
                  {mode === "artifacts" &&
                    (artifactContent
                      ? `sha256: ${artifactContent.file.sha256.slice(0, 12)}…`
                      : "SHA-256 verified store")}
                  {mode === "patch" &&
                    (discoveryResult
                      ? `discovery: ${discoveryResult.status}`
                      : "pinned revision pair")}
                </div>
              </div>

              {/* MODE 01: MANIFEST & POLICY EDITOR */}
              {mode === "manifest" && (
                <div className="divide-y divide-[var(--line-subtle)]">
                  {/* Section 1: Repository & Revisions */}
                  <div className="p-6 space-y-4">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                      01 · Repository & Revisions
                    </div>

                    <div className="grid grid-cols-[160px_1fr] gap-y-2.5 text-xs items-baseline font-mono">
                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        repository_path
                      </span>
                      <input
                        type="text"
                        value={draft.repository_path}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            repository_path: e.target.value,
                          })
                        }
                        className="spec-input text-xs text-[var(--ink)] w-full"
                      />

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        source_mode
                      </span>
                      <div>
                        <select
                          value={draft.source_mode}
                          onChange={(e) =>
                            setDraft({ ...draft, source_mode: e.target.value })
                          }
                          className="spec-input text-xs text-[var(--ink)] cursor-pointer"
                        >
                          <option value="git">git</option>
                          <option value="fixture">fixture</option>
                        </select>
                      </div>

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        vulnerable_ref
                      </span>
                      <input
                        type="text"
                        value={draft.vulnerable_ref}
                        onChange={(e) =>
                          setDraft({ ...draft, vulnerable_ref: e.target.value })
                        }
                        className="spec-input text-xs text-[var(--ink)] w-full"
                      />

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        fixed_ref
                      </span>
                      <input
                        type="text"
                        value={draft.fixed_ref}
                        onChange={(e) =>
                          setDraft({ ...draft, fixed_ref: e.target.value })
                        }
                        className="spec-input text-xs text-[var(--ink)] w-full"
                      />

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        language
                      </span>
                      <div>
                        <select
                          value={draft.language}
                          onChange={(e) =>
                            setDraft({ ...draft, language: e.target.value })
                          }
                          className="spec-input text-xs text-[var(--ink)] cursor-pointer"
                        >
                          <option value="python">python</option>
                          <option value="java">java</option>
                          <option value="javascript">javascript</option>
                          <option value="typescript">typescript</option>
                          <option value="c">c</option>
                          <option value="cpp">cpp</option>
                          <option value="go">go</option>
                          <option value="unknown">unknown</option>
                        </select>
                      </div>

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        build_system
                      </span>
                      <input
                        type="text"
                        value={draft.build_system}
                        onChange={(e) =>
                          setDraft({ ...draft, build_system: e.target.value })
                        }
                        className="spec-input text-xs text-[var(--ink)] w-48"
                      />

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        dockerfile
                      </span>
                      <input
                        type="text"
                        value={draft.dockerfile || ""}
                        placeholder="null (auto-resolved by environment specialist)"
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            dockerfile: e.target.value || null,
                          })
                        }
                        className="spec-input text-xs text-[var(--ink)] w-full"
                      />

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        advisory
                      </span>
                      <input
                        type="text"
                        value={draft.advisory}
                        placeholder="Untrusted advisory text..."
                        onChange={(e) =>
                          setDraft({ ...draft, advisory: e.target.value })
                        }
                        className="spec-input text-xs text-[var(--ink-secondary)] font-sans w-full"
                      />
                    </div>
                  </div>

                  {/* Section 2: Reasoning Plane */}
                  <div className="p-6 space-y-4">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                      02 · Reasoning Plane Policy
                    </div>

                    <div className="grid grid-cols-[160px_1fr] gap-y-2.5 text-xs items-baseline font-mono">
                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        reasoning_mode
                      </span>
                      <div>
                        <select
                          value={draft.policy.reasoning_mode}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              policy: {
                                ...draft.policy,
                                reasoning_mode: e.target.value,
                              },
                            })
                          }
                          className="spec-input text-xs text-[var(--ink)] cursor-pointer"
                        >
                          <option value="required">
                            required (fail-closed default)
                          </option>
                          <option value="openai">
                            openai (OpenAI / DeepSeek API)
                          </option>
                          <option value="ollama">ollama (local model)</option>
                          <option value="heuristic">
                            heuristic (offline test-only)
                          </option>
                        </select>
                      </div>

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        reasoning_model
                      </span>
                      <input
                        type="text"
                        value={draft.policy.reasoning_model || ""}
                        placeholder="default (resolved via P2P_MODEL)"
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            policy: {
                              ...draft.policy,
                              reasoning_model: e.target.value || null,
                            },
                          })
                        }
                        className="spec-input text-xs text-[var(--ink)] w-64"
                      />

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        reasoning_effort
                      </span>
                      <div>
                        <select
                          value={draft.policy.reasoning_effort}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              policy: {
                                ...draft.policy,
                                reasoning_effort: e.target.value,
                              },
                            })
                          }
                          className="spec-input text-xs text-[var(--ink)] cursor-pointer"
                        >
                          <option value="low">low</option>
                          <option value="medium">medium</option>
                          <option value="high">high</option>
                        </select>
                      </div>

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        heuristic_opt_in
                      </span>
                      <label className="inline-flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={draft.policy.allow_heuristic_reasoning}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              policy: {
                                ...draft.policy,
                                allow_heuristic_reasoning: e.target.checked,
                              },
                            })
                          }
                          className="accent-[var(--ink)]"
                        />
                        <span className="text-[11px] text-[var(--ink-secondary)]">
                          allow_heuristic_reasoning (never confirms a CVE)
                        </span>
                      </label>
                    </div>
                  </div>

                  {/* Section 3: Execution Plane & Resource Quotas */}
                  <div className="p-6 space-y-4">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                      03 · Execution Plane & Quotas
                    </div>

                    <div className="grid grid-cols-[160px_1fr] gap-y-2.5 text-xs items-baseline font-mono">
                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        network
                      </span>
                      <span className="text-[11px] text-[var(--ink)]">
                        none (locked by fail-closed policy)
                      </span>

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        docker_build
                      </span>
                      <label className="inline-flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={draft.policy.allow_docker_build}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              policy: {
                                ...draft.policy,
                                allow_docker_build: e.target.checked,
                              },
                            })
                          }
                          className="accent-[var(--ink)]"
                        />
                        <span className="text-[11px] text-[var(--ink-secondary)]">
                          allow_docker_build (requires build_approval gate)
                        </span>
                      </label>

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        poc_execution
                      </span>
                      <label className="inline-flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={draft.policy.allow_poc_execution}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              policy: {
                                ...draft.policy,
                                allow_poc_execution: e.target.checked,
                              },
                            })
                          }
                          className="accent-[var(--ink)]"
                        />
                        <span className="text-[11px] text-[var(--ink-secondary)]">
                          allow_poc_execution (requires execution_approval gate)
                        </span>
                      </label>

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        max_memory_mb
                      </span>
                      <input
                        type="number"
                        value={draft.policy.max_memory_mb}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            policy: {
                              ...draft.policy,
                              max_memory_mb: Number(e.target.value) || 512,
                            },
                          })
                        }
                        className="spec-input text-xs text-[var(--ink)] w-28"
                      />

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        max_cpus / pids
                      </span>
                      <div className="flex items-center gap-4">
                        <input
                          type="number"
                          step="0.5"
                          value={draft.policy.max_cpus}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              policy: {
                                ...draft.policy,
                                max_cpus: Number(e.target.value) || 1.0,
                              },
                            })
                          }
                          className="spec-input text-xs text-[var(--ink)] w-20"
                        />
                        <span className="text-[var(--ink-tertiary)]">cpus</span>
                        <input
                          type="number"
                          value={draft.policy.max_pids}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              policy: {
                                ...draft.policy,
                                max_pids: Number(e.target.value) || 128,
                              },
                            })
                          }
                          className="spec-input text-xs text-[var(--ink)] w-20"
                        />
                        <span className="text-[var(--ink-tertiary)]">pids</span>
                      </div>

                      <span className="text-[11px] text-[var(--ink-tertiary)]">
                        timeout_seconds
                      </span>
                      <input
                        type="number"
                        value={draft.policy.timeout_seconds}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            policy: {
                              ...draft.policy,
                              timeout_seconds: Number(e.target.value) || 60,
                            },
                          })
                        }
                        className="spec-input text-xs text-[var(--ink)] w-28"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* MODE 02: ARTIFACT EXPLORER */}
              {mode === "artifacts" && (
                <div>
                  {draft.artifactFiles.length === 0 ? (
                    <div className="p-6 font-mono text-xs text-[var(--ink-tertiary)]">
                      No recorded artifacts in artifacts/{draft.id}/ yet.
                    </div>
                  ) : (
                    <div className="divide-y divide-[var(--line-subtle)]">
                      {/* Category Filter Strip */}
                      <div className="px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 bg-[var(--bg)]/40 font-mono text-[11px]">
                        <div className="flex flex-wrap items-center gap-4">
                          {[
                            "all",
                            "discovery",
                            "source",
                            "reasoning",
                            "execution",
                            "proof",
                          ].map((cat) => (
                            <button
                              key={cat}
                              type="button"
                              onClick={() => setCategoryFilter(cat)}
                              className={`uppercase text-[10px] tracking-wider transition ${
                                categoryFilter === cat
                                  ? "text-[var(--ink)] font-medium underline underline-offset-4"
                                  : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                              }`}
                            >
                              {cat}
                            </button>
                          ))}
                        </div>
                        <span className="text-[10px] text-[var(--ink-tertiary)]">
                          {filteredArtifacts.length} files
                        </span>
                      </div>

                      {/* Two-Pane Artifact Browser inside Frame */}
                      <div className="grid grid-cols-1 md:grid-cols-[230px_1fr] divide-y md:divide-y-0 md:divide-x divide-[var(--line-subtle)]">
                        {/* File List */}
                        <div className="divide-y divide-[var(--line-subtle)] max-h-[560px] overflow-y-auto">
                          {filteredArtifacts.map((file) => {
                            const isSel =
                              file.filename === selectedArtifactName;
                            return (
                              <button
                                key={file.filename}
                                type="button"
                                onClick={() => {
                                  setSelectedArtifactName(file.filename);
                                  loadArtifactFile(draft.id, file.filename);
                                }}
                                className={`w-full text-left px-4 py-2.5 font-mono transition block ${
                                  isSel
                                    ? "bg-[var(--bg)] text-[var(--ink)] font-medium"
                                    : "text-[var(--ink-secondary)] hover:text-[var(--ink)]"
                                }`}
                              >
                                <div className="text-[11px] truncate">
                                  {file.filename}
                                </div>
                                <div className="text-[10px] text-[var(--ink-tertiary)] flex justify-between mt-0.5">
                                  <span>{file.category}</span>
                                  <span>{file.sizeBytes} B</span>
                                </div>
                              </button>
                            );
                          })}
                        </div>

                        {/* File Content Viewer */}
                        <div className="p-6 min-w-0">
                          {artifactLoading ? (
                            <div className="font-mono text-xs text-[var(--ink-tertiary)]">
                              Reading artifact...
                            </div>
                          ) : artifactContent ? (
                            <div className="space-y-4">
                              <div className="flex items-baseline justify-between border-b border-[var(--line-subtle)] pb-3 font-mono">
                                <div>
                                  <div className="text-xs font-medium text-[var(--ink)]">
                                    {artifactContent.file.relativePath}
                                  </div>
                                  <div className="text-[10px] text-[var(--ink-tertiary)] mt-0.5">
                                    sha256: {artifactContent.file.sha256}
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    navigator.clipboard?.writeText(
                                      artifactContent.content
                                    );
                                    triggerToast(
                                      `Copied ${artifactContent.file.filename}`
                                    );
                                  }}
                                  className="text-[11px] text-[var(--ink-tertiary)] hover:text-[var(--ink)] shrink-0"
                                >
                                  Copy
                                </button>
                              </div>

                              <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto max-h-[480px] whitespace-pre-wrap">
                                {artifactContent.parsedJson !== undefined
                                  ? JSON.stringify(
                                      artifactContent.parsedJson,
                                      null,
                                      2
                                    )
                                  : artifactContent.content}
                              </pre>
                            </div>
                          ) : (
                            <div className="font-mono text-xs text-[var(--ink-tertiary)]">
                              Select an artifact file to inspect.
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* MODE 03: PATCH & REVISION DISCOVERY */}
              {mode === "patch" && (
                <div className="divide-y divide-[var(--line-subtle)]">
                  {/* Revision Discovery Summary */}
                  <div className="p-6 space-y-4">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                      Revision Discovery & Verification Checks
                    </div>

                    {discoveryResult ? (
                      <div className="space-y-4 font-mono text-xs">
                        <div className="grid grid-cols-[140px_1fr] gap-y-1.5">
                          <span className="text-[11px] text-[var(--ink-tertiary)]">
                            status
                          </span>
                          <span className="text-[11px] text-[var(--ink)]">
                            {discoveryResult.status}
                          </span>

                          {discoveryResult.selected && (
                            <>
                              <span className="text-[11px] text-[var(--ink-tertiary)]">
                                repository_url
                              </span>
                              <span className="text-[11px] text-[var(--ink)]">
                                {discoveryResult.selected.repository_url}
                              </span>

                              <span className="text-[11px] text-[var(--ink-tertiary)]">
                                vulnerable_commit
                              </span>
                              <span className="text-[11px] text-[var(--ink-secondary)]">
                                {discoveryResult.selected.vulnerable_commit}
                              </span>

                              <span className="text-[11px] text-[var(--ink-tertiary)]">
                                fixed_commit
                              </span>
                              <span className="text-[11px] text-[var(--ink-secondary)]">
                                {discoveryResult.selected.fixed_commit}
                              </span>

                              <span className="text-[11px] text-[var(--ink-tertiary)]">
                                checks
                              </span>
                              <span className="text-[11px] text-[var(--ink)]">
                                {Object.entries(
                                  discoveryResult.selected.checks || {}
                                )
                                  .map(([k, v]) => `${k}: ${v}`)
                                  .join(" · ")}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="font-mono text-xs text-[var(--ink-secondary)]">
                        Pinned revision pair ({shortRef(draft.vulnerable_ref)} →{" "}
                        {shortRef(draft.fixed_ref)}). No separate{" "}
                        revision-discovery-result.json recorded.
                      </div>
                    )}
                  </div>

                  {/* Unified Patch Diff */}
                  <div className="p-6 space-y-3">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                      Pinned Patch Diff (raw-patch.diff)
                    </div>
                    {patchText ? (
                      <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto max-h-[480px] whitespace-pre">
                        {patchText}
                      </pre>
                    ) : (
                      <div className="font-mono text-xs text-[var(--ink-tertiary)]">
                        No raw-patch.diff recorded for this case yet.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="max-w-2xl mx-auto py-20 font-mono text-xs text-[var(--ink-tertiary)]">
            Select a case from the index.
          </div>
        )}
      </main>

      {/* QUIET MONOSPACE TOAST */}
      {toastMessage && (
        <div className="fixed bottom-6 right-8 z-50 font-mono text-[11px] px-3 py-1.5 bg-[var(--ink)] text-[var(--bg)] rounded-[2px]">
          {toastMessage}
        </div>
      )}

      {/* MINIMAL CREATE CASE MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/25 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-[var(--bg)] border border-[var(--line)] p-6 space-y-5">
            <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-3">
              <h3 className="text-sm font-medium text-[var(--ink)]">
                New Case Manifest
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="font-mono text-xs text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
              >
                Esc
              </button>
            </div>

            {/* Mode Switcher */}
            <div className="flex gap-5 font-mono text-xs border-b border-[var(--line-subtle)] pb-2.5">
              <button
                type="button"
                onClick={() => setCreateMode("cve")}
                className={
                  createMode === "cve"
                    ? "text-[var(--ink)] font-medium underline underline-offset-4"
                    : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                }
              >
                01 By CVE ID
              </button>
              <button
                type="button"
                onClick={() => setCreateMode("pinned")}
                className={
                  createMode === "pinned"
                    ? "text-[var(--ink)] font-medium underline underline-offset-4"
                    : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                }
              >
                02 Pinned Repository
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4 text-xs">
              {createMode === "cve" ? (
                <div className="grid grid-cols-[110px_1fr] items-baseline gap-y-3 font-mono">
                  <label className="text-[11px] text-[var(--ink-tertiary)]">
                    cve_id
                  </label>
                  <input
                    type="text"
                    required
                    value={newForm.id}
                    onChange={(e) =>
                      setNewForm({
                        ...newForm,
                        id: e.target.value.toUpperCase(),
                      })
                    }
                    placeholder="CVE-2024-27287"
                    className="bg-transparent border-b border-[var(--line)] pb-1 text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                  />

                  <label className="text-[11px] text-[var(--ink-tertiary)]">
                    reasoning
                  </label>
                  <select
                    value={newForm.reasoning_mode}
                    onChange={(e) =>
                      setNewForm({ ...newForm, reasoning_mode: e.target.value })
                    }
                    className="bg-transparent border-b border-[var(--line)] pb-1 text-xs text-[var(--ink)] focus:outline-none"
                  >
                    <option value="required">required</option>
                    <option value="openai">openai</option>
                    <option value="ollama">ollama</option>
                  </select>
                </div>
              ) : (
                <div className="grid grid-cols-[110px_1fr] items-baseline gap-y-3 font-mono">
                  <label className="text-[11px] text-[var(--ink-tertiary)]">
                    case_id
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
                    placeholder="local-tornado-xss"
                    className="bg-transparent border-b border-[var(--line)] pb-1 text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                  />

                  <label className="text-[11px] text-[var(--ink-tertiary)]">
                    title
                  </label>
                  <input
                    type="text"
                    required
                    value={newForm.title}
                    onChange={(e) =>
                      setNewForm({ ...newForm, title: e.target.value })
                    }
                    placeholder="Pinned N-day reproduction case"
                    className="bg-transparent border-b border-[var(--line)] pb-1 font-sans text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                  />

                  <label className="text-[11px] text-[var(--ink-tertiary)]">
                    repo_path
                  </label>
                  <input
                    type="text"
                    required
                    value={newForm.repository_path}
                    onChange={(e) =>
                      setNewForm({
                        ...newForm,
                        repository_path: e.target.value,
                      })
                    }
                    className="bg-transparent border-b border-[var(--line)] pb-1 text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                  />

                  <label className="text-[11px] text-[var(--ink-tertiary)]">
                    vulnerable_ref
                  </label>
                  <input
                    type="text"
                    required
                    value={newForm.vulnerable_ref}
                    onChange={(e) =>
                      setNewForm({ ...newForm, vulnerable_ref: e.target.value })
                    }
                    className="bg-transparent border-b border-[var(--line)] pb-1 text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                  />

                  <label className="text-[11px] text-[var(--ink-tertiary)]">
                    fixed_ref
                  </label>
                  <input
                    type="text"
                    required
                    value={newForm.fixed_ref}
                    onChange={(e) =>
                      setNewForm({ ...newForm, fixed_ref: e.target.value })
                    }
                    className="bg-transparent border-b border-[var(--line)] pb-1 text-xs text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                  />
                </div>
              )}

              <div className="font-mono text-[10px] text-[var(--ink-tertiary)] pt-1">
                Saves to examples/{newForm.id || "<case_id>"}.yaml
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
    </div>
  );
}
