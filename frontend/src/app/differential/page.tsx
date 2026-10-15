"use client";

import React, { useState } from "react";
import { GitCompare } from "lucide-react";

export default function DifferentialPage() {
  const [activeTab, setActiveTab] = useState<"stdout" | "assertions">("stdout");

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
      {/* Sub-Header */}
      <div className="h-10 px-4 border-b border-[var(--border)] bg-[var(--surface-subtle)] flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-2">
          <GitCompare className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs font-medium text-[var(--text-main)] font-mono">
            Differential Logs
          </span>
          <span className="text-xs text-[var(--text-subtle)] hidden sm:inline font-mono">
            / Paired Container Execution
          </span>
        </div>

        <span className="text-[11px] font-mono text-[var(--text-muted)]">
          Signal: <strong className="text-[var(--text-main)] font-medium">DIFFERENTIAL DETECTED</strong>
        </span>
      </div>

      {/* Tabs */}
      <div className="px-5 bg-[var(--surface-subtle)] border-b border-[var(--border)] flex items-center gap-5 text-xs font-medium h-8 shrink-0">
        <button
          onClick={() => setActiveTab("stdout")}
          className={`h-full border-b transition ${
            activeTab === "stdout"
              ? "border-[var(--text-main)] text-[var(--text-main)] font-medium"
              : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-main)]"
          }`}
        >
          Container Logs
        </button>
        <button
          onClick={() => setActiveTab("assertions")}
          className={`h-full border-b transition ${
            activeTab === "assertions"
              ? "border-[var(--text-main)] text-[var(--text-main)] font-medium"
              : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-main)]"
          }`}
        >
          Exit Codes & Assertions
        </button>
      </div>

      {/* Side-by-Side Differential View */}
      <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
        {/* Left: Vulnerable Container */}
        <div className="flex-1 flex flex-col border-b md:border-b-0 md:border-r border-[var(--border)] bg-[var(--code-bg)] overflow-hidden">
          <div className="h-8 px-4 bg-[var(--surface-subtle)] border-b border-[var(--border)] flex items-center justify-between text-xs font-mono">
            <span className="text-[var(--text-main)] font-medium">
              Vulnerable (Pinned: 9e3f1c)
            </span>
            <span className="text-[10px] text-[var(--text-subtle)]">exit: 0 • canary: read</span>
          </div>

          <pre className="flex-1 p-4 font-mono text-xs text-[var(--text-main)] leading-relaxed overflow-auto whitespace-pre">
{`[CONTAINER: vulnerable-canary-01]
[INIT] Mounting read-only /repos/target-case...
[NET] Network sandbox: NONE (Loopback only)
[SAFE_POC] Sending mock request: GET /api/v1/download?file=../../proof/canary.txt
[SERVER] 200 OK - Content-Length: 32
[ORACLE_EVIDENCE] Read canary marker content:
  >>> "CANARY-9381-VERIFIED-EXPLOITATION" <<<
[VERDICT] Observable vulnerable state transition confirmed.`}
          </pre>
        </div>

        {/* Right: Fixed Container */}
        <div className="flex-1 flex flex-col bg-[var(--code-bg)] overflow-hidden">
          <div className="h-8 px-4 bg-[var(--surface-subtle)] border-b border-[var(--border)] flex items-center justify-between text-xs font-mono">
            <span className="text-[var(--text-main)] font-medium">
              Fixed (Pinned: c821a4)
            </span>
            <span className="text-[10px] text-[var(--text-subtle)]">exit: 1 • canary: blocked</span>
          </div>

          <pre className="flex-1 p-4 font-mono text-xs text-[var(--text-main)] leading-relaxed overflow-auto whitespace-pre">
{`[CONTAINER: fixed-canary-01]
[INIT] Mounting read-only /repos/target-case...
[NET] Network sandbox: NONE (Loopback only)
[SAFE_POC] Sending mock request: GET /api/v1/download?file=../../proof/canary.txt
[SERVER] sanitize_path: Detected path traversal sequence: '../../'
[SERVER] 403 Forbidden - Security policy violation
[ORACLE_EVIDENCE] Canary marker was NOT reached or modified.
[VERDICT] Contrast verified: Fix cleanly mitigates state transition.`}
          </pre>
        </div>
      </div>
    </div>
  );
}
