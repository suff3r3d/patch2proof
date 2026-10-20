"use client";

import React from "react";

export default function DifferentialPage() {
  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-20 py-10 select-text">
      <div className="max-w-3xl mx-auto space-y-8">
        <div className="border-b border-[var(--line)] pb-5">
          <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
            Differential Observation
          </h1>
          <p className="text-xs text-[var(--ink-secondary)] mt-1">
            Paired container execution output comparing vulnerable and fixed revisions under identical SafePoC input.
          </p>
        </div>

        <div className="grid grid-cols-[120px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
          <span className="text-[11px] text-[var(--ink-tertiary)]">contrast</span>
          <span className="text-[11px] text-[var(--ink)]">confirmed differential signal</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">vulnerable</span>
          <span className="text-[11px] text-[var(--ink-secondary)]">rev 9e3f1c • exit 0 • canary read</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">fixed</span>
          <span className="text-[11px] text-[var(--ink-secondary)]">rev c821a4 • exit 1 • 403 forbidden</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 divide-y md:divide-y-0 md:divide-x divide-[var(--line)]">
          <div className="space-y-3">
            <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
              01 / Vulnerable Container (9e3f1c)
            </span>
            <pre className="font-mono text-xs text-[var(--ink)] leading-6 whitespace-pre-wrap">
{`[INIT] /repos/target-case (ro)
[NET]  none (loopback)
[REQ]  GET /api/v1/download?file=../../proof/canary.txt
[RES]  200 OK (32 bytes)
[OBS]  "CANARY-9381-VERIFIED"
[OUT]  state transition observed`}
            </pre>
          </div>

          <div className="space-y-3 md:pl-8 pt-6 md:pt-0">
            <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
              02 / Fixed Container (c821a4)
            </span>
            <pre className="font-mono text-xs text-[var(--ink)] leading-6 whitespace-pre-wrap">
{`[INIT] /repos/target-case (ro)
[NET]  none (loopback)
[REQ]  GET /api/v1/download?file=../../proof/canary.txt
[LOG]  sanitize_path: rejected '../'
[RES]  403 Forbidden
[OUT]  canary unreached`}
            </pre>
          </div>
        </div>
      </div>
    </main>
  );
}
