"use client";

import React, { useState, useEffect } from "react";
import { useActiveCaseId } from "@/lib/activeCaseClient";

export default function ApprovalsPage() {
  const [activeCaseId] = useActiveCaseId();
  const [caseRecord, setCaseRecord] = useState<any | null>(null);
  const [bundle, setBundle] = useState<Record<string, any>>({});
  const [gateView, setGateView] = useState<"execution" | "build">("execution");

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

  const safePoc = bundle["safepoc.json"] || bundle["safe-poc-plan.json"] || null;
  const dockerPlan = bundle["docker-plan.json"] || null;

  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-16 py-10 select-text">
      <div className="max-w-3xl mx-auto space-y-8">
        <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-5">
          <div>
            <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
              Approval Console
            </h1>
            <p className="text-xs text-[var(--ink-secondary)] mt-1">
              Human-in-the-loop review gates for{" "}
              <span className="font-mono text-[var(--ink)]">{activeCaseId}</span>{" "}
              before container build or SafePoC execution.
            </p>
          </div>
          <span className="font-mono text-xs text-[var(--ink-tertiary)]">
            {safePoc?.reviewed ? "reviewed" : "awaiting operator review"}
          </span>
        </div>

        <div className="grid grid-cols-[130px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
          <span className="text-[11px] text-[var(--ink-tertiary)]">case_id</span>
          <span className="text-[11px] text-[var(--ink)]">{activeCaseId}</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">
            build_policy
          </span>
          <span className="text-[11px] text-[var(--ink-secondary)]">
            allow_docker_build:{" "}
            {String(caseRecord?.policy?.allow_docker_build ?? false)}
          </span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">
            exec_policy
          </span>
          <span className="text-[11px] text-[var(--ink-secondary)]">
            allow_poc_execution:{" "}
            {String(caseRecord?.policy?.allow_poc_execution ?? false)}
          </span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">
            isolation
          </span>
          <span className="text-[11px] text-[var(--ink-secondary)]">
            network: {caseRecord?.policy?.network || "none"} · memory:{" "}
            {caseRecord?.policy?.max_memory_mb || 512}MB · timeout:{" "}
            {caseRecord?.policy?.timeout_seconds || 60}s
          </span>
        </div>

        <div className="border border-[var(--line)] bg-[var(--surface)] rounded-[2px]">
          <div className="px-5 py-2.5 border-b border-[var(--line-subtle)] flex items-center justify-between font-mono text-[11px]">
            <div className="flex items-center gap-5">
              <button
                type="button"
                onClick={() => setGateView("execution")}
                className={
                  gateView === "execution"
                    ? "text-[var(--ink)] font-medium underline underline-offset-4"
                    : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                }
              >
                01 execution_approval (safepoc.json)
              </button>
              <button
                type="button"
                onClick={() => setGateView("build")}
                className={
                  gateView === "build"
                    ? "text-[var(--ink)] font-medium underline underline-offset-4"
                    : "text-[var(--ink-tertiary)] hover:text-[var(--ink)]"
                }
              >
                02 build_approval (docker-plan.json)
              </button>
            </div>
            <span className="text-[10px] text-[var(--ink-tertiary)]">
              fail-closed contract
            </span>
          </div>

          <div className="p-6">
            {gateView === "execution" ? (
              safePoc ? (
                <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto">
                  {JSON.stringify(safePoc, null, 2)}
                </pre>
              ) : (
                <div className="font-mono text-xs text-[var(--ink-tertiary)]">
                  No SafePoC plan recorded for {activeCaseId}.
                </div>
              )
            ) : dockerPlan ? (
              <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto">
                {JSON.stringify(dockerPlan, null, 2)}
              </pre>
            ) : (
              <div className="font-mono text-xs text-[var(--ink-tertiary)]">
                No docker-plan.json recorded for {activeCaseId}.
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
