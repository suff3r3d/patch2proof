"use client";

import React, { useState, useEffect } from "react";
import { useActiveCaseId } from "@/lib/activeCaseClient";

const GATE_DEFINITIONS = [
  {
    num: "01",
    key: "source_grounded",
    desc: "Full patch diff and modified symbols are mapped to pinned repository revisions.",
  },
  {
    num: "02",
    key: "static_reachability",
    desc: "Call-graph and source slice evidence connects in-scope entrypoint to modified symbol.",
  },
  {
    num: "03",
    key: "dynamic_reachability",
    desc: "Runtime container execution reaches the patched code path without simulation.",
  },
  {
    num: "04",
    key: "semantic_transition",
    desc: "SafePoC triggers the hypothesized security state transition and oracle signal.",
  },
  {
    num: "05",
    key: "counterfactual_separation",
    desc: "Identical SafePoC input succeeds on vulnerable image and is blocked on fixed image.",
  },
  {
    num: "06",
    key: "repeatable",
    desc: "Repeated clean container runs reproduce the differential signal deterministically.",
  },
];

export default function ProofsPage() {
  const [activeCaseId] = useActiveCaseId();
  const [caseRecord, setCaseRecord] = useState<any | null>(null);
  const [bundle, setBundle] = useState<Record<string, any>>({});
  const [viewMode, setViewMode] = useState<"report" | "bundle">("report");

  useEffect(() => {
    fetch(`/api/cases/${encodeURIComponent(activeCaseId)}?bundle=1`)
      .then((r) => r.json())
      .then((d) => {
        if (d.success) {
          setCaseRecord(d.caseRecord);
          setBundle(d.bundle || {});
        }
      })
      .catch(() => {});
  }, [activeCaseId]);

  const coverage = bundle["coverage.json"] || {};
  const proofBundle = bundle["proof-bundle.json"] || null;
  const finalReportMd = bundle["final-report.md"] || null;

  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-16 py-10 select-text">
      <div className="max-w-3xl mx-auto space-y-8">
        <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-5">
          <div>
            <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
              Proof Bundle & Report
            </h1>
            <p className="text-xs text-[var(--ink-secondary)] mt-1">
              Six deterministic coverage gates and auditable verdict for{" "}
              <span className="font-mono text-[var(--ink)]">{activeCaseId}</span>.
            </p>
          </div>
          <span className="font-mono text-xs text-[var(--ink)]">
            verdict: {proofBundle?.claim_status || caseRecord?.claimStatus || "not_executed"}
          </span>
        </div>

        <div className="grid grid-cols-[130px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
          <span className="text-[11px] text-[var(--ink-tertiary)]">
            claim_status
          </span>
          <span className="text-[11px] text-[var(--ink)]">
            {proofBundle?.claim_status || caseRecord?.claimStatus || "not_executed"}{" "}
            ({caseRecord?.gatesPassed ?? 0} / {caseRecord?.gatesTotal ?? 6} gates true)
          </span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">
            schema_version
          </span>
          <span className="text-[11px] text-[var(--ink-secondary)]">
            {proofBundle?.schema_version || "proof-bundle/0.4.0"}
          </span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">
            claim_rule
          </span>
          <span className="text-[11px] text-[var(--ink-secondary)] font-sans">
            {proofBundle?.claim_rule ||
              "confirmed iff skeptic verdict=confirmed, all six coverage gates are true, and validation is non-simulated."}
          </span>
        </div>

        {/* 6 Coverage Gates Table */}
        <div className="space-y-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
            Six Deterministic Coverage Gates
          </span>
          <div className="divide-y divide-[var(--line-subtle)] border-t border-b border-[var(--line)]">
            {GATE_DEFINITIONS.map((g) => {
              const passed = coverage[g.key] === true;
              return (
                <div
                  key={g.key}
                  className="py-3 grid grid-cols-[32px_190px_1fr_60px] items-baseline gap-4 text-xs"
                >
                  <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                    {g.num}
                  </span>
                  <span className="font-mono text-xs text-[var(--ink)]">
                    {g.key}
                  </span>
                  <span className="text-[var(--ink-secondary)]">{g.desc}</span>
                  <span
                    className={`font-mono text-[10px] text-right ${
                      passed
                        ? "text-[var(--ink)] font-medium"
                        : "text-[var(--ink-tertiary)]"
                    }`}
                  >
                    {passed ? "true ✓" : "false"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Framed Report & Proof Bundle Viewer */}
        <div className="border border-[var(--line)] bg-[var(--surface)] rounded-[2px]">
          <div className="px-5 py-2.5 border-b border-[var(--line-subtle)] flex items-center justify-between font-mono text-[11px]">
            <div className="flex items-center gap-5">
              <button
                type="button"
                onClick={() => setViewMode("report")}
                className={
                  viewMode === "report"
                    ? "text-[var(--ink)] font-medium underline underline-offset-4"
                    : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                }
              >
                01 final-report.md
              </button>
              <button
                type="button"
                onClick={() => setViewMode("bundle")}
                className={
                  viewMode === "bundle"
                    ? "text-[var(--ink)] font-medium underline underline-offset-4"
                    : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                }
              >
                02 proof-bundle.json
              </button>
            </div>
            <span className="text-[10px] text-[var(--ink-tertiary)]">
              artifacts/{activeCaseId}/
            </span>
          </div>

          <div className="p-6">
            {viewMode === "report" ? (
              finalReportMd ? (
                <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed whitespace-pre-wrap overflow-x-auto max-h-[520px]">
                  {finalReportMd}
                </pre>
              ) : (
                <div className="font-mono text-xs text-[var(--ink-tertiary)]">
                  No final-report.md recorded for {activeCaseId}.
                </div>
              )
            ) : proofBundle ? (
              <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto max-h-[520px]">
                {JSON.stringify(proofBundle, null, 2)}
              </pre>
            ) : (
              <div className="font-mono text-xs text-[var(--ink-tertiary)]">
                No proof-bundle.json recorded for {activeCaseId}.
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
