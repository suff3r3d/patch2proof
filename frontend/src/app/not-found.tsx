import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3">
      <h2 className="text-sm font-medium font-mono text-[var(--ink)]">
        404 — Not Found
      </h2>
      <p className="text-xs text-[var(--ink-secondary)] font-mono">
        The requested route could not be found.
      </p>
      <Link
        href="/"
        className="px-3 py-1 bg-[var(--ink)] text-[var(--bg)] rounded-[3px] font-mono text-xs"
      >
        Return
      </Link>
    </main>
  );
}
