import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3">
      <h2 className="text-sm font-semibold font-mono text-[var(--text-main)]">404 — Page Not Found</h2>
      <p className="text-xs text-[var(--text-muted)] font-mono">The requested route could not be found.</p>
      <Link
        href="/"
        className="btn-tactile h-7 px-3 rounded text-xs font-medium bg-[var(--accent)] text-[var(--accent-text)] inline-flex items-center"
      >
        Return Home
      </Link>
    </div>
  );
}
