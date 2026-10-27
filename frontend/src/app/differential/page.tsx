"use client";

import React, { useState, useEffect } from "react";
import { useActiveCaseId } from "@/lib/activeCaseClient";

export default function DifferentialPage() {
  const [activeCaseId] = useActiveCaseId();
  const [caseRecord, setCaseRecord] = useState<any | null>(null);
  const [bundle, setBundle] = useState<Record<string, any>>({});

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

  const validation = bundle["validation.json"] || null;
  const safePoc = bundle["safepoc.json"] || bundle["safe-poc-plan.json"] || null;
  const feedback = bundle["feedback-attempt-1.json"] || null;

  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-16 py-10 select-text">
      <div className="max-w-3xl mx-auto space-y-8">
        <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-5">
          <div>
            <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
              Differential Observation
            </h1>
            <p className="text-xs text-[var(--ink-secondary)] mt-1">
              Paired vulnerable vs. fixed container expectations and runtime validation for{" "}
              <span className="font-mono text-[var(--ink)]">{activeCaseId}</span>.
            </p>
          </div>
          <span className="font-mono text-xs text-[var(--ink-tertiary)]">
            {validation?.status || "not_executed"}
          </span>
        </div>

        <div className="grid grid-cols-[130px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
          <span className="text-[11px] text-[var(--ink-tertiary)]">
            validation
          </span>
          <span className="text-[11px] text-[var(--ink)]">
            status: {validation?.status || "none"} · differential:{" "}
            {String(validation?.differential ?? false)} · oracle_match:{" "}
            {String(validation?.oracle_match ?? false)}
          </span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">
            vulnerable_ref
          </span>
          <span className="text-[11px] text-[var(--ink-secondary)]">
            {caseRecord?.vulnerable_ref || "—"}
          </span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">
            fixed_ref
          </span>
          <span className="text-[11px] text-[var(--ink-secondary)]">
            {caseRecord?.fixed_ref || "—"}
          </span>

          {feedback?.failure_class && (
            <>
              <span className="text-[11px] text-[var(--ink-tertiary)]">
                diagnosis
              </span>
              <span className="text-[11px] text-[var(--ink)]">
                {feedback.failure_class}: {feedback.summary}
              </span>
            </>
          )}
        </div>

        <div className="border border-[var(--line)] bg-[var(--surface)] rounded-[2px] divide-y divide-[var(--line-subtle)]">
          <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-[var(--line-subtle)]">
            <div className="p-6 space-y-3">
              <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                01 · Vulnerable Container
              </span>
              <div className="font-mono text-[11px] text-[var(--ink-secondary)]">
                Expected:
              </div>
              <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto">
                {JSON.stringify(
                  safePoc?.vulnerable_expectation || {},
                  null,
                  2
                )}
              </pre>
              <div className="font-mono text-[11px] text-[var(--ink-secondary)] pt-2">
                Observed:
              </div>
              <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto">
                {JSON.stringify(
                  validation?.vulnerable_observation || {},
                  null,
                  2
                )}
              </pre>
            </div>

            <div className="p-6 space-y-3">
              <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                02 · Fixed Container
              </span>
              <div className="font-mono text-[11px] text-[var(--ink-secondary)]">
                Expected:
              </div>
              <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto">
                {JSON.stringify(safePoc?.fixed_expectation || {}, null, 2)}
              </pre>
              <div className="font-mono text-[11px] text-[var(--ink-secondary)] pt-2">
                Observed:
              </div>
              <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto">
                {JSON.stringify(validation?.fixed_observation || {}, null, 2)}
              </pre>
            </div>
          </div>

          {validation?.logs?.length > 0 && (
            <div className="p-6 space-y-2">
              <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                Execution & Adapter Logs
              </span>
              <pre className="font-mono text-xs text-[var(--ink-secondary)] leading-relaxed whitespace-pre-wrap">
                {validation.logs.join("\n")}
              </pre>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
