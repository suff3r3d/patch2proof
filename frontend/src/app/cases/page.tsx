"use client";

import React, { useState } from "react";

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
  const [selected, setSelected] = useState(DEMO_CASES[0]);

  return (
    <div className="flex-1 flex min-w-0 h-full overflow-hidden">
      {/* Left Index Column */}
      <section className="w-60 border-r border-[var(--line)] flex flex-col justify-between py-7 px-6 shrink-0 select-none">
        <div className="space-y-6">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
              Cases / 03
            </span>
          </div>

          <div className="divide-y divide-[var(--line-subtle)]">
            {DEMO_CASES.map((c) => {
              const isSel = c.id === selected.id;
              return (
                <div
                  key={c.id}
                  onClick={() => setSelected(c)}
                  className={`py-3 cursor-pointer transition ${
                    isSel ? "opacity-100" : "opacity-50 hover:opacity-100"
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className={`text-xs truncate ${isSel ? "font-medium text-[var(--ink)]" : "text-[var(--ink)]"}`}>
                      {c.id}
                    </span>
                    <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                      {c.language}
                    </span>
                  </div>
                  <div className="text-[11px] text-[var(--ink-tertiary)] mt-0.5 truncate">
                    {c.title}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="font-mono text-[10px] text-[var(--ink-tertiary)]">
          cases/*.json
        </div>
      </section>

      {/* Right Spec Sheet */}
      <main className="flex-1 overflow-y-auto px-10 lg:px-20 py-10 select-text">
        <div className="max-w-2xl mx-auto space-y-8">
          <div className="border-b border-[var(--line)] pb-5">
            <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
              {selected.id}
            </h1>
            <p className="text-xs text-[var(--ink-secondary)] mt-1">
              {selected.title}
            </p>
          </div>

          <div className="grid grid-cols-[140px_1fr] gap-y-2 text-xs items-baseline font-mono">
            <span className="text-[11px] text-[var(--ink-tertiary)]">manifest</span>
            <span className="text-[11px] text-[var(--ink-secondary)]">cases/{selected.id}.json</span>

            <span className="text-[11px] text-[var(--ink-tertiary)]">repository</span>
            <span className="text-[11px] text-[var(--ink)]">{selected.targetRepo}</span>

            <span className="text-[11px] text-[var(--ink-tertiary)]">language</span>
            <span className="text-[11px] text-[var(--ink)]">{selected.language}</span>

            <span className="text-[11px] text-[var(--ink-tertiary)]">vulnerable_rev</span>
            <span className="text-[11px] text-[var(--ink)]">{selected.vulnerableRef}</span>

            <span className="text-[11px] text-[var(--ink-tertiary)]">fixed_rev</span>
            <span className="text-[11px] text-[var(--ink)]">{selected.fixedRef}</span>

            <span className="text-[11px] text-[var(--ink-tertiary)]">network</span>
            <span className="text-[11px] text-[var(--ink-secondary)]">none</span>

            <span className="text-[11px] text-[var(--ink-tertiary)]">memory_limit</span>
            <span className="text-[11px] text-[var(--ink-secondary)]">512 MB</span>
          </div>
        </div>
      </main>
    </div>
  );
}
