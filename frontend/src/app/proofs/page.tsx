"use client";

import React from "react";

const COVERAGE_GATES = [
  { num: "01", id: "gate_symbol_changed", desc: "Patch modifies vulnerability-relevant function AST boundary (sanitize_path)." },
  { num: "02", id: "gate_entrypoint_reached", desc: "Call-graph traversal connects public route handler GET /api/v1/download to modified symbol." },
  { num: "03", id: "gate_state_transition", desc: "SafePoC input induces non-standard directory traversal path resolution." },
  { num: "04", id: "gate_observable_effect", desc: "Vulnerable container execution observed expected canary content without shell execution." },
  { num: "05", id: "gate_fixed_contrast", desc: "Identical SafePoC against fixed container produced 403 rejection and preserved canary." },
  { num: "06", id: "gate_reproducibility", desc: "Repeated executions verified 100% signal consistency across clean container runs." },
];

export default function ProofsPage() {
  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-20 py-10 select-text">
      <div className="max-w-2xl mx-auto space-y-8">
        <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-5">
          <div>
            <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
              Proof Bundle
            </h1>
            <p className="text-xs text-[var(--ink-secondary)] mt-1">
              Six deterministic coverage gates and SHA-256 verified reproduction report.
            </p>
          </div>

          <button className="px-3 py-1 bg-[var(--ink)] text-[var(--bg)] rounded-[3px] font-mono text-xs hover:opacity-85 transition shrink-0">
            Export JSON
          </button>
        </div>

        <div className="grid grid-cols-[120px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
          <span className="text-[11px] text-[var(--ink-tertiary)]">verdict</span>
          <span className="text-[11px] text-[var(--ink)]">confirmed (6 / 6 gates passed)</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">bundle</span>
          <span className="text-[11px] text-[var(--ink-secondary)]">proof-bundle.json</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">sha256</span>
          <span className="text-[11px] text-[var(--ink-secondary)] truncate">
            8f4b11928374a2b919d837c427f891bca7289b71a2839912bc817349127e912f
          </span>
        </div>

        <div className="divide-y divide-[var(--line-subtle)] border-t border-[var(--line)]">
          {COVERAGE_GATES.map((g) => (
            <div
              key={g.id}
              className="py-3 grid grid-cols-[32px_180px_1fr_50px] items-baseline gap-4 text-xs"
            >
              <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                {g.num}
              </span>
              <span className="font-mono text-xs text-[var(--ink)]">
                {g.id}
              </span>
              <span className="text-[var(--ink-secondary)]">
                {g.desc}
              </span>
              <span className="font-mono text-[10px] text-right text-[var(--ink)]">
                pass
              </span>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
