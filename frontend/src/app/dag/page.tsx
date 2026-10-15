"use client";

import React, { useState } from "react";
import { Network } from "lucide-react";

const DAG_NODES = [
  { id: "hunk", type: "patch_hunk", label: "Diff Hunk #1", file: "file_service.py:45", status: "supported" },
  { id: "sym", type: "changed_symbol", label: "sanitize_path()", file: "file_service.py", status: "supported" },
  { id: "entry", type: "entrypoint", label: "GET /api/v1/download", file: "routes.py:12", status: "supported" },
  { id: "state", type: "state_transition", label: "Directory Traversal", effect: "../ traversal sequence", status: "hypothesized" },
  { id: "obs", type: "observable", label: "Canary Marker Read", target: "/proof/canary.txt", status: "hypothesized" },
  { id: "ctrl", type: "fixed_control", label: "Fixed Contrast Check", expect: "403 Forbidden in fixed", status: "pending" },
];

export default function DagPage() {
  const [selectedNode, setSelectedNode] = useState(DAG_NODES[3]);

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
      {/* Sub-Header */}
      <div className="h-10 px-4 border-b border-[var(--border)] bg-[var(--surface-subtle)] flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-2">
          <Network className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs font-medium text-[var(--text-main)] font-mono">
            Reproduction DAG
          </span>
          <span className="text-xs text-[var(--text-subtle)] hidden sm:inline font-mono">
            / 6 nodes • 5 edges
          </span>
        </div>
      </div>

      {/* Main Workspace Split */}
      <div className="flex-1 flex flex-col lg:flex-row min-h-0 overflow-hidden">
        {/* Visual Graph Canvas */}
        <div className="flex-1 p-6 bg-[var(--code-bg)] overflow-auto flex flex-col justify-center items-center space-y-3">
          <div className="w-full max-w-xl space-y-3">
            {DAG_NODES.map((node, i) => {
              const isSelected = selectedNode.id === node.id;
              return (
                <div key={node.id} className="space-y-1.5">
                  <div
                    onClick={() => setSelectedNode(node)}
                    className={`p-3 rounded-lg border cursor-pointer transition select-none flex items-center justify-between ${
                      isSelected
                        ? "bg-[var(--surface)] border-[var(--text-main)] text-[var(--text-main)] shadow-2xs"
                        : "bg-[var(--surface)] border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--text-muted)]"
                    }`}
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] uppercase font-mono px-1 py-0.2 rounded bg-[var(--surface-subtle)] border border-[var(--border)] text-[var(--text-muted)]">
                          {node.type}
                        </span>
                        <span className="text-xs font-medium text-[var(--text-main)] font-mono">
                          {node.label}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--text-subtle)] font-mono">
                        {node.file || node.effect || node.target || node.expect}
                      </p>
                    </div>

                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[var(--surface-subtle)] border border-[var(--border)] text-[var(--text-muted)]">
                      {node.status}
                    </span>
                  </div>

                  {i < DAG_NODES.length - 1 && (
                    <div className="flex justify-center text-[var(--text-subtle)]">
                      <span className="font-mono text-[11px]">↓</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Node Inspector Sidebar */}
        <div className="w-full lg:w-72 border-t lg:border-t-0 lg:border-l border-[var(--border)] bg-[var(--surface-subtle)] p-4 space-y-3 shrink-0 overflow-y-auto">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-subtle)] font-mono">
            Node Inspector
          </span>

          <div className="p-3.5 rounded-lg bg-[var(--surface)] border border-[var(--border)] space-y-2.5 text-xs">
            <div>
              <span className="text-[10px] font-mono text-[var(--text-subtle)] uppercase">Selected</span>
              <div className="font-mono font-medium text-[var(--text-main)] mt-0.5">
                {selectedNode.label}
              </div>
            </div>

            <div>
              <span className="text-[10px] font-mono text-[var(--text-subtle)]">Type:</span>
              <div className="font-mono text-[var(--text-main)] text-[11px]">{selectedNode.type}</div>
            </div>

            <div>
              <span className="text-[10px] font-mono text-[var(--text-subtle)]">Status:</span>
              <div className="font-mono text-[var(--text-main)] text-[11px]">{selectedNode.status}</div>
            </div>

            <div className="pt-2 border-t border-[var(--border)]">
              <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">
                Hypothesized transitions require empirical confirmation through deterministic paired container execution.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
