"use client";

import React, { useState, useEffect } from "react";
import { useActiveCaseId } from "@/lib/activeCaseClient";

export default function DagPage() {
  const [activeCaseId] = useActiveCaseId();
  const [graphData, setGraphData] = useState<any | null>(null);
  const [contractData, setContractData] = useState<any | null>(null);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);

  useEffect(() => {
    fetch(`/api/cases/${encodeURIComponent(activeCaseId)}?bundle=1`)
      .then((r) => r.json())
      .then((d) => {
        if (d.success && d.bundle) {
          const rg = d.bundle["reproduction-graph.json"] || null;
          const vc = d.bundle["vulnerability-contract.json"] || null;
          setGraphData(rg);
          setContractData(vc);
          if (rg?.nodes?.length) {
            setSelectedNode(rg.nodes[0]);
          } else {
            setSelectedNode(null);
          }
        }
      })
      .catch(() => {});
  }, [activeCaseId]);

  const nodes: any[] = graphData?.nodes || [];
  const edges: any[] = graphData?.edges || [];

  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-16 py-10 select-text">
      <div className="max-w-3xl mx-auto space-y-8">
        <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-5">
          <div>
            <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
              Reproduction Graph
            </h1>
            <p className="text-xs text-[var(--ink-secondary)] mt-1">
              Directed causal graph and evidence-linked transitions for{" "}
              <span className="font-mono text-[var(--ink)]">{activeCaseId}</span>.
            </p>
          </div>
          <span className="font-mono text-xs text-[var(--ink-tertiary)]">
            {graphData?.graph_id || "no graph recorded"}
          </span>
        </div>

        {graphData ? (
          <>
            {/* Selected Node Spec */}
            {selectedNode && (
              <div className="grid grid-cols-[130px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
                <span className="text-[11px] text-[var(--ink-tertiary)]">
                  node_id
                </span>
                <span className="text-[11px] text-[var(--ink)]">
                  {selectedNode.node_id} ({selectedNode.kind})
                </span>

                <span className="text-[11px] text-[var(--ink-tertiary)]">
                  label
                </span>
                <span className="text-[11px] text-[var(--ink-secondary)] font-sans">
                  {selectedNode.label}
                </span>

                <span className="text-[11px] text-[var(--ink-tertiary)]">
                  evidence_refs
                </span>
                <span className="text-[11px] text-[var(--ink-secondary)]">
                  {(selectedNode.evidence_ids || []).length} linked evidence items
                  {selectedNode.evidence_ids?.length > 0
                    ? ` (${selectedNode.evidence_ids.slice(0, 5).join(", ")}${
                        selectedNode.evidence_ids.length > 5 ? "…" : ""
                      })`
                    : ""}
                </span>

                {contractData?.sink && (
                  <>
                    <span className="text-[11px] text-[var(--ink-tertiary)]">
                      contract_sink
                    </span>
                    <span className="text-[11px] text-[var(--ink)]">
                      {contractData.sink}
                    </span>
                  </>
                )}
              </div>
            )}

            {/* Framed Graph Nodes & Edges */}
            <div className="border border-[var(--line)] bg-[var(--surface)] rounded-[2px] divide-y divide-[var(--line-subtle)]">
              <div className="px-5 py-2.5 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                <span>Causal Nodes ({nodes.length})</span>
                <span>hypothesis: {graphData.hypothesis_id}</span>
              </div>

              <div className="divide-y divide-[var(--line-subtle)]">
                {nodes.map((node, idx) => {
                  const isSel = selectedNode?.node_id === node.node_id;
                  return (
                    <div
                      key={node.node_id}
                      onClick={() => setSelectedNode(node)}
                      className={`px-6 py-3 grid grid-cols-[32px_160px_1fr_90px] items-baseline gap-4 text-xs cursor-pointer transition ${
                        isSel ? "bg-[var(--bg)] opacity-100" : "opacity-65 hover:opacity-100"
                      }`}
                    >
                      <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                        {String(idx + 1).padStart(2, "0")}
                      </span>
                      <span className="font-mono text-[11px] text-[var(--ink-tertiary)] truncate">
                        {node.kind}
                      </span>
                      <span
                        className={`truncate ${
                          isSel
                            ? "font-medium text-[var(--ink)]"
                            : "text-[var(--ink)]"
                        }`}
                      >
                        {node.label}
                      </span>
                      <span className="font-mono text-[10px] text-right text-[var(--ink-secondary)]">
                        {(node.evidence_ids || []).length} ev
                      </span>
                    </div>
                  );
                })}
              </div>

              {edges.length > 0 && (
                <div className="p-6 space-y-3">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
                    Directed Edges ({edges.length})
                  </div>
                  <div className="divide-y divide-[var(--line-subtle)] max-h-72 overflow-y-auto">
                    {edges.map((edge: any) => (
                      <div
                        key={edge.edge_id}
                        className="py-2 flex items-baseline justify-between gap-4 font-mono text-[11px]"
                      >
                        <span className="text-[var(--ink)] truncate">
                          {edge.source} → {edge.target}
                        </span>
                        <span className="text-[var(--ink-tertiary)] shrink-0">
                          {edge.status || edge.relation}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="py-12 font-mono text-xs text-[var(--ink-tertiary)]">
            No reproduction-graph.json recorded for {activeCaseId}.
          </div>
        )}
      </div>
    </main>
  );
}
