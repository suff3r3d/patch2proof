"use client";

import React, { useState } from "react";
import { Briefcase, Plus } from "lucide-react";

const DEMO_CASES = [
  {
    id: "demo-path-canary",
    title: "Path Traversal in File Service",
    language: "python",
    targetRepo: "repos/target-case",
    vulnerableRef: "9e3f1c",
    fixedRef: "c821a4",
  },
  {
    id: "cve-2024-express-prototype",
    title: "Prototype Pollution in Query Parser",
    language: "typescript",
    targetRepo: "repos/express-case",
    vulnerableRef: "4a21e0",
    fixedRef: "7b89d2",
  },
  {
    id: "cve-2023-fastapi-header-inject",
    title: "Header Injection via Unescaped Delimiter",
    language: "python",
    targetRepo: "repos/fastapi-case",
    vulnerableRef: "1128cc",
    fixedRef: "2480bb",
  },
];

export default function CasesPage() {
  const [selectedCase, setSelectedCase] = useState(DEMO_CASES[0]);

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
      {/* Sub-Header */}
      <div className="h-10 px-4 border-b border-[var(--border)] bg-[var(--surface-subtle)] flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-2">
          <Briefcase className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs font-medium text-[var(--text-main)] font-mono">
            Case Manifests
          </span>
          <span className="text-xs text-[var(--text-subtle)] hidden sm:inline font-mono">
            / Pinned Revisions & Quotas
          </span>
        </div>

        <button className="btn-tactile h-6 px-2.5 rounded text-xs font-medium bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-[var(--accent-text)] shadow-2xs transition flex items-center gap-1 font-sans">
          <Plus className="w-3 h-3" />
          <span>New Manifest</span>
        </button>
      </div>

      {/* Main Workspace Split */}
      <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
        {/* Cases List */}
        <div className="w-full md:w-64 border-b md:border-b-0 md:border-r border-[var(--border)] bg-[var(--surface-subtle)] p-2 space-y-1.5 shrink-0 overflow-y-auto">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-subtle)] font-mono px-2">
            Cases ({DEMO_CASES.length})
          </span>

          <div className="space-y-1 pt-1">
            {DEMO_CASES.map((item) => {
              const isSelected = selectedCase.id === item.id;
              return (
                <div
                  key={item.id}
                  onClick={() => setSelectedCase(item)}
                  className={`p-2.5 rounded-md cursor-pointer transition select-none ${
                    isSelected
                      ? "bg-[var(--surface)] border border-[var(--border)] text-[var(--text-main)] shadow-2xs"
                      : "hover:bg-[var(--surface-hover)] text-[var(--text-muted)]"
                  }`}
                >
                  <div className="text-xs font-medium text-[var(--text-main)]">
                    {item.id}
                  </div>
                  <p className="text-[11px] text-[var(--text-subtle)] mt-0.5 line-clamp-1">
                    {item.title}
                  </p>
                  <div className="flex items-center gap-2 pt-1 text-[10px] font-mono text-[var(--text-subtle)]">
                    <span>{item.language}</span>
                    <span>•</span>
                    <span>{item.vulnerableRef}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Case Manifest Detail Editor */}
        <div className="flex-1 p-6 space-y-5 overflow-y-auto max-w-xl">
          <div>
            <h3 className="text-xs font-semibold text-[var(--text-main)] font-mono">
              Manifest Specification
            </h3>
            <p className="text-[11px] text-[var(--text-subtle)] mt-0.5 font-mono">
              cases/{selectedCase.id}.json
            </p>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <label className="block font-medium text-[var(--text-muted)] mb-1">Identifier</label>
              <input
                type="text"
                readOnly
                value={selectedCase.id}
                className="w-full h-7 px-2.5 font-mono rounded bg-[var(--surface-subtle)] border border-[var(--border)] text-[var(--text-main)]"
              />
            </div>

            <div>
              <label className="block font-medium text-[var(--text-muted)] mb-1">Repository Path</label>
              <input
                type="text"
                readOnly
                value={selectedCase.targetRepo}
                className="w-full h-7 px-2.5 font-mono rounded bg-[var(--surface-subtle)] border border-[var(--border)] text-[var(--text-main)]"
              />
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="block font-medium text-[var(--text-muted)] mb-1">Vulnerable Ref</label>
                <input
                  type="text"
                  readOnly
                  value={selectedCase.vulnerableRef}
                  className="w-full h-7 px-2.5 font-mono rounded bg-[var(--surface-subtle)] border border-[var(--border)] text-[var(--text-main)]"
                />
              </div>

              <div>
                <label className="block font-medium text-[var(--text-muted)] mb-1">Fixed Ref</label>
                <input
                  type="text"
                  readOnly
                  value={selectedCase.fixedRef}
                  className="w-full h-7 px-2.5 font-mono rounded bg-[var(--surface-subtle)] border border-[var(--border)] text-[var(--text-main)]"
                />
              </div>
            </div>

            <div className="p-3 rounded bg-[var(--surface-subtle)] border border-[var(--border)] space-y-1">
              <span className="font-medium text-[var(--text-main)] text-[11px]">Execution Quotas</span>
              <div className="grid grid-cols-3 gap-2 pt-0.5 font-mono text-[10px] text-[var(--text-muted)]">
                <div>Network: <strong>none</strong></div>
                <div>Memory: <strong>512 MB</strong></div>
                <div>Timeout: <strong>30s</strong></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
