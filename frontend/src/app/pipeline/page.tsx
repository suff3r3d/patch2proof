"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useActiveCaseId } from "@/lib/activeCaseClient";

interface PipelineNodeDef {
  num: string;
  id: string;
  phase: string;
  artifactKey: string;
  desc: string;
}

const CANONICAL_NODES: PipelineNodeDef[] = [
  {
    num: "01",
    id: "discover_revisions",
    phase: "discovery",
    artifactKey: "revision-discovery-result.json",
    desc: "Resolve and verify vulnerable/fixed commit pair from advisory references",
  },
  {
    num: "02",
    id: "analyze_patch",
    phase: "ingestion",
    artifactKey: "patch-analysis.json",
    desc: "Extract diff hunks, security tags, and modified AST symbols",
  },
  {
    num: "03",
    id: "investigate_sources",
    phase: "ingestion",
    artifactKey: "source-context.json",
    desc: "Trace callers, callees, and pinned source slices across both revisions",
  },
  {
    num: "04",
    id: "reason_vulnerability",
    phase: "reasoning",
    artifactKey: "reasoning-initial.json",
    desc: "Formulate competing evidence-linked hypotheses and disconfirmation tests",
  },
  {
    num: "05",
    id: "build_reproduction_graph",
    phase: "reasoning",
    artifactKey: "reproduction-graph.json",
    desc: "Construct directed reproduction graph and vulnerability contract",
  },
  {
    num: "06",
    id: "select_strategy",
    phase: "planning",
    artifactKey: "skill-candidates.json",
    desc: "Retrieve and rank applicable prior reproduction skills",
  },
  {
    num: "07",
    id: "plan_environment",
    phase: "build",
    artifactKey: "docker-plan.json",
    desc: "Synthesize paired isolated container specifications (network: none)",
  },
  {
    num: "08",
    id: "build_approval",
    phase: "hitl",
    artifactKey: "images.json",
    desc: "Operator clearance and paired vulnerable/fixed Docker image build",
  },
  {
    num: "09",
    id: "plan_safe_poc",
    phase: "planning",
    artifactKey: "safe-poc-plan.json",
    desc: "Compile bounded SafePoC observation operators and oracle expectations",
  },
  {
    num: "10",
    id: "execution_approval",
    phase: "hitl",
    artifactKey: "safepoc.json",
    desc: "Operator clearance and paired container execution under strict quotas",
  },
  {
    num: "11",
    id: "evaluate_coverage",
    phase: "verdict",
    artifactKey: "coverage.json",
    desc: "Evaluate six deterministic coverage gates and skeptic review",
  },
  {
    num: "12",
    id: "write_proof_bundle",
    phase: "bundle",
    artifactKey: "proof-bundle.json",
    desc: "Emit SHA-256 verified proof-bundle.json and final-report.md",
  },
];

export default function PipelinePage() {
  const [activeCaseId] = useActiveCaseId();
  const [caseRecord, setCaseRecord] = useState<any | null>(null);
  const [bundle, setBundle] = useState<Record<string, any>>({});
  const [selectedNodeId, setSelectedNodeId] = useState<string>("reason_vulnerability");

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

  const nodesWithStatus = useMemo(() => {
    const existingSet = new Set(
      (caseRecord?.artifactFiles || []).map((f: any) => f.filename)
    );
    return CANONICAL_NODES.map((n) => {
      const hasArtifact = existingSet.has(n.artifactKey);
      return {
        ...n,
        status: hasArtifact ? "recorded" : "not_run",
      };
    });
  }, [caseRecord]);

  const selectedNode =
    nodesWithStatus.find((n) => n.id === selectedNodeId) || nodesWithStatus[0];
  const selectedArtifactPayload = selectedNode
    ? bundle[selectedNode.artifactKey]
    : null;

  return (
    <main className="flex-1 overflow-y-auto px-10 lg:px-16 py-10 select-text">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-baseline justify-between border-b border-[var(--line)] pb-5">
          <div>
            <h1 className="text-xl font-medium tracking-tight text-[var(--ink)]">
              Pipeline Execution
            </h1>
            <p className="text-xs text-[var(--ink-secondary)] mt-1">
              LangGraph stage progression and recorded stage artifacts for{" "}
              <span className="font-mono text-[var(--ink)]">{activeCaseId}</span>.
            </p>
          </div>
          <span className="font-mono text-xs text-[var(--ink-tertiary)]">
            {caseRecord?.claimStatus || "not_executed"}
          </span>
        </div>

        {/* Inline Telemetry Spec */}
        <div className="grid grid-cols-[130px_1fr] gap-y-1.5 text-xs items-baseline border-b border-[var(--line)] pb-6 font-mono">
          <span className="text-[11px] text-[var(--ink-tertiary)]">case_id</span>
          <span className="text-[11px] text-[var(--ink)]">{activeCaseId}</span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">revisions</span>
          <span className="text-[11px] text-[var(--ink-secondary)] break-all">
            {caseRecord
              ? `${caseRecord.vulnerable_ref.slice(0, 12)} → ${caseRecord.fixed_ref.slice(0, 12)}`
              : "—"}
          </span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">isolation</span>
          <span className="text-[11px] text-[var(--ink-secondary)]">
            network: {caseRecord?.policy?.network || "none"} · build:{" "}
            {caseRecord?.policy?.allow_docker_build ? "allowed" : "dry-run"}
          </span>

          <span className="text-[11px] text-[var(--ink-tertiary)]">gates</span>
          <span className="text-[11px] text-[var(--ink)]">
            {caseRecord
              ? `${caseRecord.gatesPassed} / ${caseRecord.gatesTotal} verified`
              : "0 / 6 verified"}
          </span>
        </div>

        {/* Node Sequence Table */}
        <div className="space-y-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
            LangGraph Node Sequence (click node to inspect recorded output)
          </span>

          <div className="divide-y divide-[var(--line-subtle)] border-t border-b border-[var(--line)]">
            {nodesWithStatus.map((n) => {
              const isSelected = n.id === selectedNode?.id;
              return (
                <div
                  key={n.id}
                  onClick={() => setSelectedNodeId(n.id)}
                  className={`py-2.5 grid grid-cols-[32px_185px_1fr_80px] items-baseline gap-4 text-xs cursor-pointer transition ${
                    isSelected
                      ? "opacity-100"
                      : n.status === "not_run"
                      ? "opacity-40 hover:opacity-75"
                      : "opacity-70 hover:opacity-100"
                  }`}
                >
                  <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                    {n.num}
                  </span>
                  <span
                    className={`font-mono text-xs ${
                      isSelected
                        ? "font-medium text-[var(--ink)] underline underline-offset-4"
                        : "text-[var(--ink)]"
                    }`}
                  >
                    {n.id}
                  </span>
                  <span className="text-[var(--ink-secondary)] truncate">
                    {n.desc}
                  </span>
                  <span className="font-mono text-[10px] text-right text-[var(--ink-tertiary)]">
                    {n.status}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Framed Stage Artifact Inspector */}
        {selectedNode && (
          <div className="border border-[var(--line)] bg-[var(--surface)] rounded-[2px]">
            <div className="px-5 py-2.5 border-b border-[var(--line-subtle)] flex items-center justify-between font-mono text-[11px]">
              <span className="text-[var(--ink)] font-medium">
                {selectedNode.num} · {selectedNode.id} ({selectedNode.artifactKey})
              </span>
              <span className="text-[10px] text-[var(--ink-tertiary)]">
                artifacts/{activeCaseId}/{selectedNode.artifactKey}
              </span>
            </div>
            <div className="p-6">
              {selectedArtifactPayload ? (
                <pre className="font-mono text-xs text-[var(--ink)] leading-relaxed overflow-x-auto max-h-[420px]">
                  {typeof selectedArtifactPayload === "string"
                    ? selectedArtifactPayload
                    : JSON.stringify(selectedArtifactPayload, null, 2)}
                </pre>
              ) : (
                <div className="font-mono text-xs text-[var(--ink-tertiary)]">
                  No {selectedNode.artifactKey} recorded for {activeCaseId}.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
