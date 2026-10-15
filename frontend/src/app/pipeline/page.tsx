"use client";

import React, { useState } from "react";
import {
  Activity,
  Play,
  CheckCircle2,
  Layers,
  Shield,
} from "lucide-react";

const WORKFLOW_STAGES = [
  {
    phase: "Phase 1: Ingestion & Slicing",
    nodes: [
      { id: "fetch_patch", label: "fetch_patch", status: "completed", desc: "Parsed diff hunks and symbols" },
      { id: "case_init", label: "case_init", status: "completed", desc: "Initialized case state and isolated workspaces" },
      { id: "slice_source", label: "slice_source", status: "completed", desc: "Extracted pinned source slices & AST bounds" },
    ],
  },
  {
    phase: "Phase 2: Hypothesis & Planning",
    nodes: [
      { id: "reasoning", label: "reasoning", status: "completed", desc: "Specialist formulated competing hypotheses" },
      { id: "build_approval", label: "build_approval", status: "completed", desc: "HITL human verification of build specs" },
      { id: "build_vulnerable", label: "build_vulnerable", status: "completed", desc: "Isolated Docker build: vulnerable snapshot" },
      { id: "build_fixed", label: "build_fixed", status: "completed", desc: "Isolated Docker build: fixed snapshot" },
    ],
  },
  {
    phase: "Phase 3: SafePoC Planning & Approval",
    nodes: [
      { id: "poc_reasoning", label: "poc_reasoning", status: "active", desc: "Specialist planning bounded SafePoC actions" },
      { id: "execution_approval", label: "execution_approval", status: "pending", desc: "HITL approval before container execution" },
    ],
  },
  {
    phase: "Phase 4: Differential Container Execution",
    nodes: [
      { id: "run_vulnerable", label: "run_vulnerable", status: "pending", desc: "Execute SafePoC in vulnerable container (net:none)" },
      { id: "run_fixed", label: "run_fixed", status: "pending", desc: "Execute SafePoC in fixed container (net:none)" },
      { id: "oracle_eval", label: "oracle_eval", status: "pending", desc: "Evaluate 6 deterministic coverage gates" },
    ],
  },
  {
    phase: "Phase 5: Skeptic Verification & Proof Bundle",
    nodes: [
      { id: "skeptic", label: "skeptic", status: "pending", desc: "Independent audit attempting to falsify candidate" },
      { id: "proof_pack", label: "proof_pack", status: "pending", desc: "SHA-256 evidence bundle generation" },
      { id: "final_report", label: "final_report", status: "pending", desc: "Render markdown & JSON verdict report" },
    ],
  },
];

export default function PipelinePage() {
  const [isRunning, setIsRunning] = useState(false);

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
      {/* Sub-Header */}
      <div className="h-10 px-4 border-b border-[var(--border)] bg-[var(--surface-subtle)] flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs font-medium text-[var(--text-main)] font-mono">
            Pipeline Execution
          </span>
          <span className="text-xs text-[var(--text-subtle)] hidden sm:inline font-mono">
            / run-2026-1014-canary
          </span>
        </div>

        <button
          onClick={() => setIsRunning(!isRunning)}
          className="btn-tactile h-6 px-2.5 rounded text-xs font-medium bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-[var(--accent-text)] shadow-2xs transition flex items-center gap-1 font-sans"
        >
          <Play className="w-3 h-3" />
          <span>{isRunning ? "Pause" : "Resume"}</span>
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* Top KPI row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="p-3 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border)] space-y-0.5">
            <span className="text-[10px] font-mono text-[var(--text-subtle)] uppercase">Current Node</span>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-main)]" />
              <span className="text-xs font-semibold font-mono text-[var(--text-main)]">poc_reasoning</span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border)] space-y-0.5">
            <span className="text-[10px] font-mono text-[var(--text-subtle)] uppercase">Execution Plane</span>
            <div className="text-xs font-semibold font-mono text-[var(--text-main)]">Containers Built (net:none)</div>
          </div>

          <div className="p-3 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border)] space-y-0.5">
            <span className="text-[10px] font-mono text-[var(--text-subtle)] uppercase">HITL Gates</span>
            <div className="text-xs font-semibold font-mono text-[var(--text-main)]">1 Approved, 1 Queued</div>
          </div>

          <div className="p-3 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border)] space-y-0.5">
            <span className="text-[10px] font-mono text-[var(--text-subtle)] uppercase">Coverage Gates</span>
            <div className="text-xs font-semibold font-mono text-[var(--text-main)]">2 / 6 Verified</div>
          </div>
        </div>

        {/* Progression Phases */}
        <div className="space-y-3">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-subtle)] font-mono">
            Workflow Progression (21 Nodes)
          </span>

          <div className="space-y-2.5">
            {WORKFLOW_STAGES.map((phase, pIdx) => (
              <div
                key={pIdx}
                className="p-3.5 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border)] space-y-2"
              >
                <span className="text-[11px] font-semibold text-[var(--text-main)] font-mono">
                  {phase.phase}
                </span>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {phase.nodes.map((node) => {
                    const isDone = node.status === "completed";
                    const isActive = node.status === "active";

                    return (
                      <div
                        key={node.id}
                        className={`p-2.5 rounded border text-xs space-y-0.5 transition ${
                          isActive
                            ? "bg-[var(--surface)] border-[var(--text-main)] text-[var(--text-main)] shadow-2xs"
                            : isDone
                            ? "bg-[var(--surface)] border-[var(--border)] text-[var(--text-main)]"
                            : "bg-[var(--surface)] border-[var(--border)] text-[var(--text-subtle)] opacity-50"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-medium text-[11px]">{node.label}</span>
                          {isDone && <CheckCircle2 className="w-3 h-3 text-[var(--text-muted)]" />}
                          {isActive && <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-main)]" />}
                        </div>
                        <p className="text-[10px] text-[var(--text-muted)] line-clamp-1">{node.desc}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
