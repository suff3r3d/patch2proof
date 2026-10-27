"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useActiveCaseId } from "@/lib/activeCaseClient";

interface AppShellProps {
  children: React.ReactNode;
}

const NAV_ITEMS = [
  { num: "01", label: "Pipeline", href: "/pipeline" },
  { num: "02", label: "Reproduction Graph", href: "/dag" },
  { num: "03", label: "Approvals", href: "/approvals" },
  { num: "04", label: "Differential", href: "/differential" },
  { num: "05", label: "Cases", href: "/cases" },
  { num: "06", label: "Specialists", href: "/specialists" },
  { num: "07", label: "Proofs", href: "/proofs" },
];

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [isDark, setIsDark] = useState(false);
  const [activeCaseId, setActiveCaseId] = useActiveCaseId();
  const [caseList, setCaseList] = useState<
    { id: string; gatesPassed: number; gatesTotal: number; claimStatus: string }[]
  >([]);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
      document.documentElement.classList.remove("light");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
    }
  }, [isDark]);

  useEffect(() => {
    fetch("/api/cases")
      .then((r) => r.json())
      .then((d) => {
        if (d.success && Array.isArray(d.cases)) {
          setCaseList(d.cases);
        }
      })
      .catch(() => {});
  }, [activeCaseId]);

  const activeCaseMeta = caseList.find((c) => c.id === activeCaseId);

  return (
    <div className="h-[100dvh] flex overflow-hidden bg-[var(--bg)] text-[var(--ink)] select-none">
      {/* PRIMARY ULTRA-QUIET SWISS RAIL (192px) */}
      <aside className="w-48 border-r border-[var(--line)] flex flex-col justify-between py-7 px-6 shrink-0">
        <div className="space-y-8">
          {/* Plain wordmark */}
          <Link href="/" className="flex items-baseline justify-between group">
            <span className="text-xs font-medium tracking-tight text-[var(--ink)]">
              Patch2Proof
            </span>
            <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
              0.1
            </span>
          </Link>

          {/* Active Case Context Selector */}
          <div className="space-y-1.5 pb-4 border-b border-[var(--line-subtle)]">
            <span className="font-mono text-[10px] text-[var(--ink-tertiary)] uppercase tracking-wider block">
              Active Case
            </span>
            {caseList.length > 0 ? (
              <select
                value={activeCaseId}
                onChange={(e) => setActiveCaseId(e.target.value)}
                className="w-full bg-transparent font-mono text-[11px] text-[var(--ink)] focus:outline-none cursor-pointer truncate"
              >
                {caseList.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.id}
                  </option>
                ))}
              </select>
            ) : (
              <div className="font-mono text-[11px] text-[var(--ink)] truncate">
                {activeCaseId}
              </div>
            )}
            {activeCaseMeta && (
              <div className="font-mono text-[10px] text-[var(--ink-tertiary)] flex justify-between">
                <span>{activeCaseMeta.claimStatus}</span>
                <span>
                  {activeCaseMeta.gatesPassed}/{activeCaseMeta.gatesTotal} gates
                </span>
              </div>
            )}
          </div>

          {/* Numbered Index Navigation */}
          <nav className="space-y-1">
            <div className="pb-2">
              <span className="font-mono text-[10px] text-[var(--ink-tertiary)] uppercase tracking-wider">
                Index
              </span>
            </div>

            {NAV_ITEMS.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href === "/specialists" &&
                  (pathname === "/" || pathname === "/specialists"));

              return (
                <Link
                  key={item.num}
                  href={item.href}
                  className={`group flex items-baseline gap-2.5 py-1 text-xs transition ${
                    isActive
                      ? "font-medium text-[var(--ink)]"
                      : "text-[var(--ink-secondary)] hover:text-[var(--ink)]"
                  }`}
                >
                  <span
                    className={`font-mono text-[10px] ${
                      isActive
                        ? "text-[var(--ink)]"
                        : "text-[var(--ink-tertiary)] group-hover:text-[var(--ink-secondary)]"
                    }`}
                  >
                    {item.num}
                  </span>
                  <span className="truncate">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Minimal Footer */}
        <div className="space-y-3 pt-4 border-t border-[var(--line-subtle)] font-mono text-[10px] text-[var(--ink-tertiary)]">
          <div className="flex justify-between">
            <span>net:none</span>
            <span>fail-closed</span>
          </div>
          <button
            onClick={() => setIsDark(!isDark)}
            className="text-left text-[var(--ink-secondary)] hover:text-[var(--ink)] transition underline underline-offset-4"
          >
            {isDark ? "Switch to light" : "Switch to dark"}
          </button>
        </div>
      </aside>

      {/* ACTIVE WORKSPACE */}
      <div className="flex-1 flex min-w-0 overflow-hidden">{children}</div>
    </div>
  );
}
