"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { downloadFile, listPapers } from "@/lib/api";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
interface PaperPair {
  timestamp: string;           // e.g. "20260807_191531"
  questionFile: string | null; // "question_paper_TIMESTAMP.pdf"
  answerFile:   string | null; // "answer_key_TIMESTAMP.pdf"
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function extractTimestamp(filename: string): string | null {
  const m = filename.match(/(\d{8}_\d{6})/);
  return m ? m[1] : null;
}

function groupIntoPairs(files: string[]): PaperPair[] {
  const byTs: Record<string, PaperPair> = {};

  for (const f of files) {
    const ts = extractTimestamp(f);
    if (!ts) continue;
    if (!byTs[ts]) byTs[ts] = { timestamp: ts, questionFile: null, answerFile: null };
    if (/answer/i.test(f))  byTs[ts].answerFile   = f;
    else                     byTs[ts].questionFile = f;
  }

  // Sort newest first
  return Object.values(byTs).sort((a, b) => b.timestamp.localeCompare(a.timestamp));
}

function formatTimestamp(ts: string): string {
  if (ts.length !== 15) return ts;
  const year     = ts.slice(0, 4);
  const monthIdx = parseInt(ts.slice(4, 6)) - 1;
  const day      = parseInt(ts.slice(6, 8));
  const hour     = ts.slice(9, 11);
  const min      = ts.slice(11, 13);
  const months   = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${months[monthIdx] ?? ""} ${day}, ${year} · ${hour}:${min}`;
}

/** Derive the analytics paper_id from a file timestamp */
function toPaperId(ts: string): string {
  return `paper_${ts}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// DownloadButton
// ─────────────────────────────────────────────────────────────────────────────
function DownloadButton({
  filename, label, variant = "primary",
}: {
  filename: string;
  label: string;
  variant?: "primary" | "ghost";
}) {
  const [busy, setBusy] = useState(false);
  const [err,  setErr]  = useState<string | null>(null);

  const isPrimary = variant === "primary";

  return (
    <div className="flex-1 min-w-0">
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true); setErr(null);
          try { await downloadFile(filename); }
          catch (e) { setErr((e as Error).message); }
          finally { setBusy(false); }
        }}
        className={`flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-[12px] font-bold transition focus:outline-none disabled:opacity-50 ${
          isPrimary
            ? "bg-primary text-primary-foreground hover:opacity-90"
            : "border border-foreground/20 bg-background text-foreground hover:bg-muted"
        }`}
      >
        {busy ? (
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current/30 border-t-current" />
        ) : (
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
        )}
        <span className="truncate">{busy ? "Downloading…" : label}</span>
      </button>
      {err && <p className="mt-1 font-mono text-[10px] text-center text-primary">{err}</p>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PaperPairCard
// ─────────────────────────────────────────────────────────────────────────────
function PaperPairCard({ pair }: { pair: PaperPair }) {
  const paperId    = toPaperId(pair.timestamp);
  const fmtDate    = formatTimestamp(pair.timestamp);
  const hasQP      = !!pair.questionFile;
  const hasAK      = !!pair.answerFile;
  const isPaired   = hasQP && hasAK;

  return (
    <div className="flex flex-col justify-between overflow-hidden rounded-[10px] border border-foreground/[0.08] bg-card p-5 shadow-sm transition hover:border-primary/30 group">
      <div>
        <div className="mb-4 flex items-start justify-between gap-3">
          <span className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full border-2 border-primary text-primary">
            <svg viewBox="0 0 24 24" className="h-[14px] w-[14px]" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <path d="M6 4h8l4 4v12H6z" />
              <path d="M14 4v4h4" />
            </svg>
          </span>
          <span className={`inline-flex rounded-[4px] px-2 py-1 text-[9px] font-bold uppercase tracking-widest border ${
            isPaired
              ? "bg-primary/10 text-primary border-primary/20"
              : "bg-foreground/5 text-muted-foreground border-foreground/10"
          }`}>
            {isPaired ? "Complete" : hasQP ? "QP Only" : "AK Only"}
          </span>
        </div>

        <h3 className="font-serif text-[18px] font-bold text-foreground line-clamp-1 group-hover:text-primary transition-colors">
          Paper {pair.timestamp.slice(0, 8).replace(/(\d{4})(\d{2})(\d{2})/, "$3/$2/$1")}
        </h3>
        <p className="mt-1.5 font-mono text-[11px] text-muted-foreground">
          Generated: {fmtDate}
        </p>
      </div>

      <div className="mt-5 border-t border-foreground/10 pt-4 flex flex-col gap-3">
        <div className="flex gap-2">
          {hasQP && pair.questionFile && (
            <DownloadButton filename={pair.questionFile} label="Questions" variant="primary" />
          )}
          {hasAK && pair.answerFile && (
            <DownloadButton filename={pair.answerFile} label="Answers" variant="ghost" />
          )}
        </div>

        <Link
          href={`/analytics/${paperId}`}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-foreground/10 bg-foreground/5 px-4 py-2.5 text-[12px] font-bold text-foreground transition hover:bg-muted focus:outline-none"
        >
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
          View Paper Analytics
        </Link>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Background Effect
// ─────────────────────────────────────────────────────────────────────────────
function BackgroundFX() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 bg-background">
      <div className="absolute left-[20px] sm:left-[48px] top-0 bottom-0 w-[1.5px] bg-primary/35" />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────
function HistoryPage() {
  const [papers,      setPapers]      = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState<string | null>(null);

  const refreshPapers = useCallback(() => {
    setLoading(true);
    setError(null);
    listPapers()
      .then((r) => setPapers(r.files))
      .catch((e) => setError((e as Error).message || "Failed to load generated papers."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { refreshPapers(); }, [refreshPapers]);

  const pairs = groupIntoPairs(papers);
  const filteredPairs = pairs.filter((p) => {
    const term = searchQuery.toLowerCase();
    if (!term) return true;
    const dateStr = formatTimestamp(p.timestamp).toLowerCase();
    return dateStr.includes(term) || p.questionFile?.toLowerCase().includes(term) || p.answerFile?.toLowerCase().includes(term);
  });

  return (
    <div className="relative min-h-screen text-foreground font-serif z-10 pl-[20px] sm:pl-0">
      <BackgroundFX />

      <main className="relative mx-auto w-full max-w-6xl px-4 pt-4 pb-12 sm:px-[64px] lg:px-[64px]">
        <div className="mb-10 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="mb-2 font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-primary">Archived Documents</p>
            <h2 className="font-serif text-[clamp(28px,4vw,40px)] font-bold leading-tight m-0 text-secondary">
              Previously Generated Papers
            </h2>
            <p className="mt-2.5 font-mono text-[13px] text-muted-foreground">
              Browse, download, and view analytics for all question papers generated in past sessions.
            </p>
          </div>
          <Link
            href="/dashboard"
            className="self-start sm:self-center inline-flex items-center gap-2 rounded-lg bg-primary px-[18px] py-[10px] text-[12px] font-bold tracking-[0.03em] text-primary-foreground shadow-sm transition hover:opacity-90 no-underline"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 5v14" /><path d="M5 12h14" />
            </svg>
            Create New Paper
          </Link>
        </div>

        {/* Filters & Search */}
        <div className="mb-6 flex items-center gap-4 rounded-[10px] border border-foreground/[0.08] bg-card p-4 shadow-sm">
          <div className="relative flex-1">
            <span className="absolute inset-y-0 left-3.5 flex items-center text-muted-foreground">
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
              </svg>
            </span>
            <input
              type="text"
              placeholder="Search by date, type (question, answer)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-foreground/10 bg-background pl-10 pr-4 py-2.5 text-[13px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:outline-none"
            />
          </div>
          <button
            onClick={refreshPapers}
            className="rounded-lg border border-foreground/20 bg-background px-4 py-2.5 text-[12px] font-bold text-foreground transition hover:bg-muted active:scale-[0.98]"
            title="Refresh database"
          >
            Refresh
          </button>
        </div>

        {/* Main List */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <span className="h-8 w-8 animate-spin rounded-full border-3 border-foreground/20 border-t-primary" />
            <p className="mt-4 font-mono text-[12px] text-muted-foreground font-bold">
              Loading generation archive...
            </p>
          </div>
        ) : error ? (
          <div className="rounded-xl border border-primary/20 bg-primary/10 p-6 text-center">
            <h3 className="text-base font-bold text-primary">Archive failed to load</h3>
            <p className="mt-2 text-[13px] text-primary/80">{error}</p>
            <button
              onClick={refreshPapers}
              className="mt-4 rounded-lg bg-primary px-4 py-2 text-[12px] font-bold text-primary-foreground hover:opacity-90"
            >
              Retry
            </button>
          </div>
        ) : filteredPairs.length === 0 ? (
          <div className="rounded-[10px] border border-dashed border-foreground/20 bg-foreground/5 py-16 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
                <path d="M6 4h8l4 4v12H6z" />
                <path d="M14 4v4h4" />
              </svg>
            </div>
            <h3 className="font-serif text-[20px] font-bold text-foreground">No papers found</h3>
            <p className="mt-1 text-[13px] text-muted-foreground">
              {searchQuery
                ? "No papers match your search term."
                : "You haven't generated any papers yet."}
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredPairs.map((pair) => (
              <PaperPairCard key={pair.timestamp} pair={pair} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

export default HistoryPage;
