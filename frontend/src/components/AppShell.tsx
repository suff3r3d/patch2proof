"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface AppShellProps {
  children: React.ReactNode;
}

const NAV_ITEMS = [
  { num: "01", label: "Pipeline", href: "/pipeline" },
  { num: "02", label: "Reproduction Graph", href: "/dag" },
  { num: "03", label: "Approvals", href: "/approvals", count: "1" },
  { num: "04", label: "Differential", href: "/differential" },
  { num: "05", label: "Cases", href: "/cases" },
  { num: "06", label: "Specialists", href: "/specialists" },
  { num: "07", label: "Proofs", href: "/proofs" },
];

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [isDark, setIsDark] = useState(false);

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

          {/* Numbered Index Navigation */}
          <nav className="space-y-1">
            <div className="pb-2">
              <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
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
                  {item.count && (
                    <span className="ml-auto font-mono text-[10px] text-[var(--ink)]">
                      {item.count}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Minimal Footer */}
        <div className="space-y-3 pt-4 border-t border-[var(--line-subtle)] font-mono text-[10px] text-[var(--ink-tertiary)]">
          <div className="flex justify-between">
            <span>net:none</span>
            <span>6/6 gates</span>
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
