"use client";

import React, { useState } from "react";

export default function ApprovalsPage() {
  const [status, setStatus] = useState<"pending" | "approved" | "rejected">("pending");

  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-20 py-10 select-text">
      <div className="max-w-2xl mx-auto space-y-8">
        <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-5">
          <div>
            <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
              Approval Console
            </h1>
            <p className="text-xs text-[var(--ink-secondary)] mt-1">
              Human-in-the-loop clearance before container build or SafePoC execution.
            </p>
          </div>

          {status === "pending" && (
            <div className="flex items-center gap-5 font-mono text-xs shrink-0">
              <button
                onClick={() => setStatus("rejected")}
                className="text-[var(--ink-tertiary)] hover:text-red-600 transition"
              >
                Reject
              </button>
              <button
                onClick={() => setStatus("approved")}
                className="px-3 py-1 bg-[var(--ink)] text-[var(--bg)] rounded-[3px] hover:opacity-85 transition"
              >
                Approve
              </button>
            </div>
          )}
        </div>

        <div className="grid grid-cols-[120px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
          <span className="text-[11px] text-[var(--ink-tertiary)]">interrupt</span>
          <span className="text-[11px] text-[var(--ink)]">execution_approval</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">case_id</span>
          <span className="text-[11px] text-[var(--ink-secondary)]">demo-path-canary</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">state</span>
          <span className="text-[11px] text-[var(--ink)]">{status}</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">isolation</span>
          <span className="text-[11px] text-[var(--ink-secondary)]">network: none • memory: 512MB • timeout: 15s</span>
        </div>

        <div className="space-y-3">
          <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
            Proposed SafePoC Action Plan
          </span>
          <pre className="font-mono text-[13px] text-[var(--ink)] leading-7 whitespace-pre-wrap">
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
      </div>
    </main>
  );
}
