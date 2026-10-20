"use client";

import React, { useState } from "react";

const WORKFLOW_NODES = [
  { num: "01", id: "fetch_patch", phase: "ingestion", status: "done", desc: "Parsed diff hunks and modified symbols" },
  { num: "02", id: "case_init", phase: "ingestion", status: "done", desc: "Initialized case state and isolated workspaces" },
  { num: "03", id: "slice_source", phase: "ingestion", status: "done", desc: "Extracted pinned source slices and AST bounds" },
  { num: "04", id: "reasoning", phase: "hypothesis", status: "done", desc: "Patch Analyst formulated competing hypotheses" },
  { num: "05", id: "build_approval", phase: "hitl", status: "done", desc: "Operator verified container build specifications" },
  { num: "06", id: "build_vulnerable", phase: "build", status: "done", desc: "Isolated Docker build: vulnerable snapshot" },
  { num: "07", id: "build_fixed", phase: "build", status: "done", desc: "Isolated Docker build: fixed snapshot" },
  { num: "08", id: "poc_reasoning", phase: "planning", status: "active", desc: "SafePoC Planner generating bounded observation actions" },
  { num: "09", id: "execution_approval", phase: "hitl", status: "pending", desc: "Operator clearance before container execution" },
  { num: "10", id: "run_vulnerable", phase: "execution", status: "pending", desc: "Execute SafePoC in vulnerable container (net:none)" },
  { num: "11", id: "run_fixed", phase: "execution", status: "pending", desc: "Execute SafePoC in fixed container (net:none)" },
  { num: "12", id: "oracle_eval", phase: "verdict", status: "pending", desc: "Evaluate 6 deterministic coverage gates" },
  { num: "13", id: "skeptic", phase: "verdict", status: "pending", desc: "Independent audit attempting to falsify candidate" },
  { num: "14", id: "proof_pack", phase: "bundle", status: "pending", desc: "SHA-256 evidence bundle generation" },
];

export default function PipelinePage() {
  const [paused, setPaused] = useState(false);

  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-20 py-10 select-text">
      <div className="max-w-2xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-5">
          <div>
            <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
              Pipeline Execution
            </h1>
            <p className="text-xs text-[var(--ink-secondary)] mt-1">
              LangGraph state progression across ingestion, reasoning, paired execution, and verification.
            </p>
          </div>

          <button
            onClick={() => setPaused(!paused)}
            className="px-3 py-1 bg-[var(--ink)] text-[var(--bg)] rounded-[3px] font-mono text-xs hover:opacity-85 transition shrink-0"
          >
            {paused ? "Resume" : "Pause"}
          </button>
        </div>

        {/* Inline Telemetry Spec */}
        <div className="grid grid-cols-[120px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
          <span className="text-[11px] text-[var(--ink-tertiary)]">run_id</span>
          <span className="text-[11px] text-[var(--ink)]">run-2026-1014-canary</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">active_node</span>
          <span className="text-[11px] text-[var(--ink)]">08 / poc_reasoning</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">containers</span>
          <span className="text-[11px] text-[var(--ink-secondary)]">vulnerable (9e3f1c), fixed (c821a4) — net:none</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">gates</span>
          <span className="text-[11px] text-[var(--ink-secondary)]">2 / 6 verified</span>
        </div>

        {/* Node Table */}
        <div className="space-y-2">
          <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
            Node Sequence
          </span>

          <div className="divide-y divide-[var(--line-subtle)] border-t border-[var(--line)]">
            {WORKFLOW_NODES.map((n) => {
              const isActive = n.status === "active";
              const isPending = n.status === "pending";
              return (
                <div
                  key={n.id}
                  className={`py-2.5 grid grid-cols-[32px_160px_1fr_70px] items-baseline gap-4 text-xs ${
                    isPending ? "opacity-40" : ""
                  }`}
                >
                  <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                    {n.num}
                  </span>
                  <span
                    className={`font-mono text-xs ${
                      isActive ? "font-medium text-[var(--ink)]" : "text-[var(--ink)]"
                    }`}
                  >
                    {n.id}
                  </span>
                  <span className="text-[var(--ink-secondary)] truncate">
                    {n.desc}
                  </span>
                  <span className="font-mono text-[10px] text-right text-[var(--ink-tertiary)]">
                    {isActive ? "● active" : n.status}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </main>
  );
}
