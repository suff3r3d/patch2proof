"use client";

import React, { useState } from "react";
import { ShieldCheck, Check, X, CheckCircle2 } from "lucide-react";

export default function ApprovalsPage() {
  const [approved, setApproved] = useState(false);

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
      {/* Sub-Header */}
      <div className="h-10 px-4 border-b border-[var(--border)] bg-[var(--surface-subtle)] flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs font-medium text-[var(--text-main)] font-mono">
            Approval Console
          </span>
          <span className="text-xs text-[var(--text-subtle)] hidden sm:inline font-mono">
            / HITL Safety Clearance
          </span>
        </div>

        <span className="text-[11px] font-mono text-[var(--text-muted)]">
          {approved ? "0 Pending" : "1 Pending Review"}
        </span>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 max-w-3xl mx-auto w-full space-y-4">
        {!approved ? (
          <div className="p-5 rounded-xl bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-xs font-semibold text-[var(--text-main)] font-mono">
                  execution_approval
                </h3>
                <p className="text-[11px] text-[var(--text-subtle)] font-mono mt-0.5">
                  Case: demo-path-canary • Action: http_mock_request
                </p>
              </div>

              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--surface-subtle)] text-[var(--text-muted)] border border-[var(--border)]">
                Awaiting Clearance
              </span>
            </div>

            <div className="space-y-1.5">
              <span className="text-[11px] font-mono text-[var(--text-subtle)]">
                Proposed Action Payload:
              </span>
              <pre className="p-3 rounded bg-[var(--code-bg)] border border-[var(--border)] font-mono text-xs text-[var(--text-muted)] leading-relaxed overflow-x-auto whitespace-pre">
{`{
  "action_type": "http_mock_request",
  "endpoint": "mock://internal/api/v1/download?file=../../proof/canary.txt",
  "method": "GET",
  "expected_vulnerable_status": 200,
  "expected_fixed_status": 403,
  "resource_limits": {
    "network": "none",
    "timeout_seconds": 15,
    "memory_mb": 512
  }
}`}
              </pre>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
              <span className="text-[11px] text-[var(--text-subtle)] font-mono">
                Fail-closed: rejection terminates execution.
              </span>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => alert("Execution rejected.")}
                  className="btn-tactile h-7 px-3 rounded text-xs font-medium border border-[var(--border)] text-[var(--text-muted)] hover:text-red-600 transition font-mono"
                >
                  Reject
                </button>

                <button
                  onClick={() => setApproved(true)}
                  className="btn-tactile h-7 px-3.5 rounded text-xs font-medium bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-[var(--accent-text)] shadow-2xs transition font-mono"
                >
                  Approve Execution
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)] text-center space-y-2">
            <CheckCircle2 className="w-8 h-8 text-[var(--text-muted)] mx-auto" />
            <h3 className="text-xs font-semibold text-[var(--text-main)] font-mono">
              Approval Granted
            </h3>
            <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
              SafePoC execution cleared. Paired Docker containers are running under network isolation.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
