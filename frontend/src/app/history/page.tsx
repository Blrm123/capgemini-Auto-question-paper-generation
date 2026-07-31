"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { downloadFile, listPapers } from "@/lib/api";



function formatTimestamp(ts: string): string {
  // Timestamp format: YYYYMMDD_HHMMSS -> e.g. 20260611_190746
  if (ts.length !== 15) return ts;
  const year = ts.slice(0, 4);
  const monthIdx = parseInt(ts.slice(4, 6)) - 1;
  const day = parseInt(ts.slice(6, 8));
  const hour = ts.slice(9, 11);
  const minute = ts.slice(11, 13);
  const second = ts.slice(13, 15);

  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const monthName = months[monthIdx] || ts.slice(4, 6);

  return `${monthName} ${day}, ${year} at ${hour}:${minute}:${second}`;
}

function HistoryPage() {
  const [papers, setPapers] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshPapers = useCallback(() => {
    setLoading(true);
    setError(null);
    listPapers()
      .then((r) => {
        setPapers(r.files);
      })
      .catch((e) => {
        setError((e as Error).message || "Failed to load generated papers.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    refreshPapers();
  }, [refreshPapers]);

  const filteredPapers = papers.filter((p) => {
    const term = searchQuery.toLowerCase();
    const isAnswer = /answer/i.test(p);
    const label = isAnswer ? "answer key" : "question paper";
    return p.toLowerCase().includes(term) || label.includes(term);
  });

  return (
    <div className="relative min-h-screen text-foreground pb-12">
      <BackgroundFX />
      
      <main className="relative mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm font-medium text-primary/80">Archived Documents</p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight text-secondary sm:text-3xl">
              Previously Generated Papers
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Browse, filter, and download question papers and answer keys generated in past
              sessions.
            </p>
          </div>
          <Link
            href="/dashboard"
            className="self-start sm:self-center inline-flex items-center gap-2 rounded-lg bg-primary px-4.5 py-2.5 text-xs font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/95"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M12 5v14" />
              <path d="M5 12h14" />
            </svg>
            Create New Paper
          </Link>
        </div>

        {/* Filters & Search */}
        <div className="mb-6 flex items-center gap-4 rounded-xl border border-border bg-background/85 p-4 shadow-[0_1px_2px_oklch(0.32_0.07_257/0.02)] backdrop-blur-sm">
          <div className="relative flex-1">
            <span className="absolute inset-y-0 left-3.5 flex items-center text-muted-foreground">
              <svg
                viewBox="0 0 24 24"
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
            </span>
            <input
              type="text"
              placeholder="Search by date, type (question, answer)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-input/80 bg-background/90 pl-10 pr-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/50 hover:border-primary/30 focus:border-primary/50 focus:bg-background focus:outline-none focus:ring-2 focus:ring-primary/10"
            />
          </div>
          <button
            onClick={refreshPapers}
            className="rounded-lg border border-border/80 bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:bg-primary/[0.04] active:scale-[0.98]"
            title="Refresh database"
          >
            Refresh
          </button>
        </div>

        {/* Main List */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <span className="h-8 w-8 animate-spin rounded-full border-3 border-primary/30 border-t-primary" />
            <p className="mt-4 text-sm text-muted-foreground font-medium">
              Loading generation archive...
            </p>
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50/90 p-6 text-center">
            <h3 className="text-base font-semibold text-red-800">Archive failed to load</h3>
            <p className="mt-2 text-sm text-red-900/90">{error}</p>
            <button
              onClick={refreshPapers}
              className="mt-4 rounded-lg bg-red-800 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        ) : filteredPapers.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border/80 bg-[oklch(0.975_0.012_245/0.4)] py-16 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <svg
                viewBox="0 0 24 24"
                className="h-6 w-6"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                aria-hidden
              >
                <path d="M6 4h8l4 4v12H6z" />
                <path d="M14 4v4h4" />
              </svg>
            </div>
            <h3 className="text-base font-semibold text-foreground">No papers found</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {searchQuery
                ? "No papers match your search term."
                : "You haven't generated any papers yet."}
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredPapers.map((filename) => {
              const isAnswer = /answer/i.test(filename);
              // Extract timestamp from pattern e.g. question_paper_20260611_190746.pdf
              const rawTimestamp = filename
                .replace(/^(question_paper_|answer_key_)/, "")
                .replace(".pdf", "");
              const formattedDate = formatTimestamp(rawTimestamp);

              return (
                <div
                  key={filename}
                  className="flex flex-col justify-between overflow-hidden rounded-xl border border-border bg-background/85 p-5 shadow-[0_1px_2px_oklch(0.32_0.07_257/0.02),0_6px_20px_-10px_oklch(0.32_0.07_257/0.08)] backdrop-blur-sm transition-all duration-200 hover:shadow-[0_8px_30px_-8px_oklch(0.32_0.07_257/0.12)] hover:border-primary/15 group"
                >
                  <div>
                    <div className="mb-4 flex items-start justify-between gap-3">
                      <span
                        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition ${
                          isAnswer
                            ? "bg-muted text-muted-foreground border border-border"
                            : "bg-primary/10 text-primary border border-primary/5"
                        }`}
                      >
                        <svg
                          viewBox="0 0 24 24"
                          className="h-5 w-5"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.75"
                          aria-hidden
                        >
                          {isAnswer ? (
                            <>
                              <path d="M12 2v4" />
                              <path d="M12 18v4" />
                              <path d="m4.93 4.93 2.83 2.83" />
                              <path d="m16.24 16.24 2.83 2.83" />
                              <path d="M2 12h4" />
                              <path d="M18 12h4" />
                            </>
                          ) : (
                            <>
                              <path d="M6 4h8l4 4v12H6z" />
                              <path d="M14 4v4h4" />
                            </>
                          )}
                        </svg>
                      </span>
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide border ${
                          isAnswer
                            ? "bg-muted text-muted-foreground border-border"
                            : "bg-primary/[0.06] text-primary border-primary/10"
                        }`}
                      >
                        {isAnswer ? "Answer Key" : "Question Paper"}
                      </span>
                    </div>

                    <h3
                      className="text-[14px] font-semibold text-foreground tracking-tight line-clamp-1 group-hover:text-primary transition-colors"
                      title={filename}
                    >
                      {filename.replace(".pdf", "")}
                    </h3>
                    <p className="mt-1.5 text-xs text-muted-foreground font-medium">
                      Generated: {formattedDate}
                    </p>
                  </div>

                  <div className="mt-5 border-t border-border/40 pt-4">
                    <DownloadButton filename={filename} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
      <div className="border-t border-border bg-background py-6">
        <p className="text-center text-sm text-muted-foreground">
          QUBIT &middot; Secure Institutional Ledger
        </p>
      </div>
    </div>
  );
}

function DownloadButton({ filename }: { filename: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div>
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setErr(null);
          try {
            await downloadFile(filename);
          } catch (e) {
            setErr((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary/5 px-4 py-2.5 text-xs font-semibold text-primary transition hover:bg-primary hover:text-primary-foreground focus:outline-none"
      >
        {busy ? (
          <>
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-current" />
            Downloading…
          </>
        ) : (
          <>
            <svg
              viewBox="0 0 24 24"
              className="h-3.5 w-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Download PDF
          </>
        )}
      </button>
      {err && <p className="mt-1 text-[11px] text-center text-red-700">{err}</p>}
    </div>
  );
}



function BackgroundFX({ scrollY }: { scrollY?: number } = {}) {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 bg-background">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background"></div>
    </div>
  );
}

export default HistoryPage;
