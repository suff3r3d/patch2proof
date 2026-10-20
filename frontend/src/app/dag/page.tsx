"use client";

import React, { useState } from "react";

const DAG_NODES = [
  { num: "01", id: "hunk", type: "patch_hunk", label: "Diff Hunk #1", loc: "file_service.py:45", status: "supported", detail: "Pre-patch slice lacks normalized path boundary check." },
  { num: "02", id: "sym", type: "changed_symbol", label: "sanitize_path()", loc: "file_service.py", status: "supported", detail: "Function AST modified in commit c821a4." },
  { num: "03", id: "entry", type: "entrypoint", label: "GET /api/v1/download", loc: "routes.py:12", status: "supported", detail: "Public route passes query parameter directly to sanitize_path()." },
  { num: "04", id: "state", type: "state_transition", label: "Directory Traversal", loc: "../ sequence", status: "hypothesized", detail: "Relative parent segments escape base directory before fix." },
  { num: "05", id: "obs", type: "observable", label: "Canary Marker Read", loc: "/proof/canary.txt", status: "hypothesized", detail: "SafePoC read_canary operator targets isolated proof marker." },
  { num: "06", id: "ctrl", type: "fixed_control", label: "Fixed Contrast Check", loc: "403 in fixed", status: "pending", detail: "Patched build must reject identical request with 403." },
];

export default function DagPage() {
  const [selected, setSelected] = useState(DAG_NODES[3]);

  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-20 py-10 select-text">
      <div className="max-w-2xl mx-auto space-y-8">
        <div className="border-b border-[var(--line)] pb-5">
          <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
            Reproduction Graph
          </h1>
          <p className="text-xs text-[var(--ink-secondary)] mt-1">
            Directed chain from modified patch hunk to empirical runtime oracle.
          </p>
        </div>

        {/* Selected Node Spec */}
        <div className="grid grid-cols-[120px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
          <span className="text-[11px] text-[var(--ink-tertiary)]">selected</span>
          <span className="text-[11px] text-[var(--ink)]">{selected.num} / {selected.label}</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">node_type</span>
          <span className="text-[11px] text-[var(--ink-secondary)]">{selected.type}</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">evidence_state</span>
          <span className="text-[11px] text-[var(--ink)]">{selected.status}</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">observation</span>
          <span className="text-[11px] text-[var(--ink-secondary)] font-sans">{selected.detail}</span>
        </div>

        {/* Chain List */}
        <div className="divide-y divide-[var(--line-subtle)] border-t border-[var(--line)]">
          {DAG_NODES.map((node) => {
            const isSel = selected.id === node.id;
            return (
              <div
                key={node.id}
                onClick={() => setSelected(node)}
                className={`py-3 grid grid-cols-[32px_130px_1fr_90px] items-baseline gap-4 text-xs cursor-pointer transition ${
                  isSel ? "opacity-100" : "opacity-55 hover:opacity-100"
                }`}
              >
                <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                  {node.num}
                </span>
                <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                  {node.type}
                </span>
                <div>
                  <span className={isSel ? "font-medium text-[var(--ink)]" : "text-[var(--ink)]"}>
                    {node.label}
                  </span>
                  <span className="font-mono text-[11px] text-[var(--ink-tertiary)] ml-2">
                    {node.loc}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-right text-[var(--ink-secondary)]">
                  {node.status}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
