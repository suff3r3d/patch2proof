"use client";

import React, { useState } from "react";
import { FileCheck, Download, Check } from "lucide-react";

const COVERAGE_GATES = [
  {
    id: "gate_symbol_changed",
    title: "1. Changed Symbol Localized",
    description: "Patch modifies vulnerability-relevant function AST boundary (sanitize_path).",
    passed: true,
  },
  {
    id: "gate_entrypoint_reached",
    title: "2. Entrypoint Reachability",
    description: "Call-graph traversal connects public route handler GET /api/v1/download to modified symbol.",
    passed: true,
  },
  {
    id: "gate_state_transition",
    title: "3. Traversed State Transition",
    description: "SafePoC input induces non-standard directory traversal path resolution.",
    passed: true,
  },
  {
    id: "gate_observable_effect",
    title: "4. Observable Canary Effect",
    description: "Vulnerable container execution observed expected canary content without arbitrary shell execution.",
    passed: true,
  },
  {
    id: "gate_fixed_contrast",
    title: "5. Fixed Version Contrast",
    description: "Identical SafePoC executed against fixed container produced rejection (403 Forbidden) and canary was preserved.",
    passed: true,
  },
  {
    id: "gate_reproducibility",
    title: "6. Deterministic Reproducibility",
    description: "Repeated executions verify 100% signal consistency across clean container re-instantiations.",
    passed: true,
  },
];

export default function ProofsPage() {
  const [downloading, setDownloading] = useState(false);

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
      {/* Sub-Header */}
      <div className="h-10 px-4 border-b border-[var(--border)] bg-[var(--surface-subtle)] flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-2">
          <FileCheck className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs font-medium text-[var(--text-main)] font-mono">
            Proof Bundles & Gates
          </span>
          <span className="text-xs text-[var(--text-subtle)] hidden sm:inline font-mono">
            / Deterministic Verification Checklist
          </span>
        </div>

        <button
          onClick={() => {
            setDownloading(true);
            setTimeout(() => setDownloading(false), 1200);
          }}
          className="btn-tactile h-6 px-2.5 rounded text-xs font-medium bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-[var(--accent-text)] shadow-2xs transition flex items-center gap-1 font-sans"
        >
          <Download className="w-3 h-3" />
          <span>{downloading ? "Packaging..." : "Download Proof Bundle"}</span>
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5 max-w-3xl mx-auto w-full">
        {/* Verdict Banner */}
        <div className="p-4 rounded-xl bg-[var(--surface)] border border-[var(--border)] shadow-xs flex items-center justify-between">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2 font-mono text-xs font-semibold text-[var(--text-main)]">
              <span>VERDICT: CONFIRMED VULNERABILITY</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-[var(--surface-subtle)] text-[var(--text-muted)] border border-[var(--border)]">
                6 / 6 Gates Passed
              </span>
            </div>
            <p className="text-[10px] text-[var(--text-subtle)] font-mono">
              SHA-256: 8f4b11928374a2b919d837c427f891bca7289b71a2839912bc817349127e912f
            </p>
          </div>
        </div>

        {/* 6 Deterministic Coverage Gates Checklist */}
        <div className="space-y-2">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-subtle)] font-mono">
            6 Coverage Gates
          </span>

          <div className="space-y-1.5">
            {COVERAGE_GATES.map((gate) => (
              <div
                key={gate.id}
                className="p-3 rounded-lg bg-[var(--surface)] border border-[var(--border)] flex items-start gap-3"
              >
                <div className="w-4 h-4 rounded bg-[var(--surface-subtle)] border border-[var(--border)] flex items-center justify-center text-[var(--text-main)] shrink-0 mt-0.5">
                  <Check className="w-2.5 h-2.5" />
                </div>
                <div className="space-y-0.5">
                  <span className="text-xs font-medium text-[var(--text-main)] font-mono">
                    {gate.title}
                  </span>
                  <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">
                    {gate.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
