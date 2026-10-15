"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Network,
  ShieldCheck,
  GitCompare,
  Briefcase,
  BrainCircuit,
  FileCheck,
  PanelLeft,
  Sun,
  Moon,
} from "lucide-react";

interface AppShellProps {
  children: React.ReactNode;
}

const NAV_ITEMS = [
  {
    id: "pipeline",
    label: "Pipeline Execution",
    href: "/pipeline",
    icon: Activity,
    badge: "Live",
  },
  {
    id: "dag",
    label: "Interactive DAG",
    href: "/dag",
    icon: Network,
  },
  {
    id: "approvals",
    label: "Approval Console",
    href: "/approvals",
    icon: ShieldCheck,
    badge: "1 Pending",
  },
  {
    id: "differential",
    label: "Differential Logs",
    href: "/differential",
    icon: GitCompare,
  },
  {
    id: "cases",
    label: "Case Manifests",
    href: "/cases",
    icon: Briefcase,
  },
  {
    id: "specialists",
    label: "Specialist Studio",
    href: "/specialists",
    icon: BrainCircuit,
    badge: "4",
  },
  {
    id: "proofs",
    label: "Proof Bundles",
    href: "/proofs",
    icon: FileCheck,
    badge: "6 Gates",
  },
];

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isDark, setIsDark] = useState(false); // Default to Swiss Editorial Paper light mode

  // Sync theme
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
      document.documentElement.classList.remove("light");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
    }
  }, [isDark]);

  return (
    <div className="h-[100dvh] flex flex-col bg-[var(--bg)] text-[var(--text-main)] overflow-hidden font-sans">
      {/* GLOBAL TOP APP HEADER */}
      <header className="h-11 px-4 border-b border-[var(--border)] bg-[var(--surface-subtle)] flex items-center justify-between shrink-0 select-none z-20">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-6 h-6 rounded bg-[var(--surface)] border border-[var(--border)] flex items-center justify-center font-bold text-[11px] text-[var(--text-main)] font-mono transition group-hover:scale-105">
              P2P
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold tracking-tight text-[var(--text-main)]">
                Patch2Proof
              </span>
              <span className="text-[10px] text-[var(--text-subtle)] font-mono hidden sm:inline">
                / research-pipeline
              </span>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          {/* Execution Plane Status - Minimalist */}
          <div className="flex items-center gap-2 px-2 py-0.5 rounded bg-[var(--surface)] border border-[var(--border)] text-[11px] font-mono text-[var(--text-muted)]">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-muted)]" />
            <span className="hidden sm:inline">Execution:</span>
            <span className="text-[var(--text-main)] font-medium">Docker net:none</span>
          </div>

          {/* Color Mode Switcher */}
          <button
            onClick={() => setIsDark(!isDark)}
            className="btn-tactile h-6 px-2 rounded text-[11px] font-medium border border-[var(--border)] hover:bg-[var(--surface-hover)] transition flex items-center gap-1.5 text-[var(--text-muted)] hover:text-[var(--text-main)] font-mono"
            title="Toggle theme"
          >
            {isDark ? (
              <>
                <Sun className="w-3 h-3 text-amber-500" />
                <span className="hidden sm:inline text-[11px]">Light</span>
              </>
            ) : (
              <>
                <Moon className="w-3 h-3 text-stone-600" />
                <span className="hidden sm:inline text-[11px]">Dark</span>
              </>
            )}
          </button>
        </div>
      </header>

      {/* APP BODY: SIDE NAVBAR + WORKSPACE VIEW */}
      <div className="flex-1 flex overflow-hidden">
        {/* PRIMARY SIDE NAVBAR */}
        <aside
          className={`border-r border-[var(--border)] bg-[var(--nav-bg)] flex flex-col justify-between shrink-0 transition-all duration-200 select-none z-10 ${
            isCollapsed ? "w-14" : "w-56"
          }`}
        >
          {/* Top Section: Nav Links */}
          <div className="p-2 space-y-3">
            {/* Header / Collapse Toggle */}
            <div className="flex items-center justify-between px-2 pt-1">
              {!isCollapsed && (
                <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-subtle)] font-mono">
                  Navigation
                </span>
              )}
              <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className={`p-1 rounded text-[var(--text-subtle)] hover:text-[var(--text-main)] hover:bg-[var(--surface-hover)] transition ${
                  isCollapsed ? "mx-auto" : "ml-auto"
                }`}
                title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                <PanelLeft className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Navigation List */}
            <nav className="space-y-0.5">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive =
                  pathname === item.href ||
                  (item.href === "/specialists" && (pathname === "/" || pathname === "/specialists"));

                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    title={isCollapsed ? item.label : undefined}
                    className={`nav-item flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs transition group relative ${
                      isActive
                        ? "bg-[var(--surface-hover)] text-[var(--text-main)] font-medium border-l-2 border-[var(--text-main)] shadow-2xs"
                        : "text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--surface-hover)]"
                    } ${isCollapsed ? "justify-center px-0" : ""}`}
                  >
                    <Icon
                      className={`w-3.5 h-3.5 shrink-0 transition ${
                        isActive
                          ? "text-[var(--text-main)]"
                          : "text-[var(--text-subtle)] group-hover:text-[var(--text-main)]"
                      }`}
                      strokeWidth={isActive ? 2 : 1.75}
                    />

                    {!isCollapsed && (
                      <>
                        <span className="truncate">{item.label}</span>
                        {item.badge && (
                          <span className="ml-auto text-[10px] px-1.5 py-0.2 rounded font-mono bg-[var(--surface-subtle)] text-[var(--text-muted)] border border-[var(--border)]">
                            {item.badge}
                          </span>
                        )}
                      </>
                    )}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Bottom Section: Telemetry Box */}
          <div className="p-2.5 border-t border-[var(--border)] space-y-1.5">
            {!isCollapsed ? (
              <div className="p-2 rounded bg-[var(--surface-subtle)] border border-[var(--border)] space-y-0.5 text-[10px] font-mono text-[var(--text-subtle)]">
                <div className="flex justify-between">
                  <span>LangGraph</span>
                  <span className="text-[var(--text-main)] font-medium">21 Nodes</span>
                </div>
                <div className="flex justify-between">
                  <span>Coverage</span>
                  <span className="text-[var(--text-main)] font-medium">6 Gates</span>
                </div>
              </div>
            ) : (
              <div
                className="flex justify-center py-1 text-[var(--text-subtle)] font-mono text-[10px]"
                title="LangGraph: 21 Nodes | 6 Gates Ready"
              >
                21N
              </div>
            )}
          </div>
        </aside>

        {/* WORKSPACE VIEW (PAGE CONTENT) */}
        <main className="flex-1 flex flex-col min-w-0 bg-[var(--surface)] overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
