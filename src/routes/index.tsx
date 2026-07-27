import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Question Paper Generator - AI-assisted Exam Builder" },
      { name: "description", content: "Create professional college-level question papers and answer keys with multi-agent LangGraph orchestration and RAG." },
    ],
  }),
  component: LandingPage,
});

function LandingPage() {
  const [healthOk, setHealthOk] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => {
        setHealth(h);
        setHealthOk(true);
      })
      .catch(() => setHealthOk(false));
  }, []);

  const agents = [
    {
      step: 1,
      name: "Syllabus Agent",
      role: "Syllabus Analysis",
      desc: "Extracts logical unit boundaries, course objectives, and syllabus topic hierarchies from course PDFs.",
      icon: (
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-indigo-600" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6 6h10M6 10h10"/>
        </svg>
      )
    },
    {
      step: 2,
      name: "Question Generator",
      role: "RAG Synthesis",
      desc: "Generates relevant examination questions utilizing hybrid search across lecture notes and textbooks.",
      icon: (
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-purple-600" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Z"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      )
    },
    {
      step: 3,
      name: "Bloom Classifier",
      role: "Cognitive Auditing",
      desc: "Classifies each question based on Bloom's Taxonomy, balancing levels from Remember to Apply and Create.",
      icon: (
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-pink-600" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
      )
    },
    {
      step: 4,
      name: "Validation Agent",
      role: "Exam Compliance",
      desc: "Ensures that exam formatting, total marks distribution, and coverage comply with set guidelines.",
      icon: (
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-emerald-600" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
      )
    },
    {
      step: 5,
      name: "Answer Key Agent",
      role: "Rubric Generation",
      desc: "Autogenerates corresponding model answers, marking schemes, and detailed point-by-point keys.",
      icon: (
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-amber-600" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 8h10M7 12h10M7 16h6"/>
        </svg>
      )
    }
  ];

  return (
    <div className="relative min-h-screen text-foreground overflow-x-hidden">
      <BackgroundFX />
      
      {/* Navigation Header */}
      <header className="sticky top-0 z-30 border-b border-white/60 bg-white/75 shadow-[0_1px_0_0_oklch(0.929_0.013_255.508),0_4px_24px_-12px_oklch(0.32_0.07_257/0.08)] backdrop-blur-xl">
        <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-primary/25 to-transparent" />
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3.5">
            <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-[oklch(0.42_0.09_255)] text-primary-foreground shadow-[0_2px_8px_-2px_oklch(0.32_0.07_257/0.4)]">
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M6 4h8l4 4v12H6z"/><path d="M14 4v4h4"/><path d="M8 13h8"/><path d="M8 17h6"/></svg>
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight text-foreground sm:text-lg">
                Question Paper Generator
              </h1>
              <p className="text-xs text-muted-foreground sm:text-[13px]">
                AI-assisted examination paper creation
              </p>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
            <Link
              to="/"
              className="text-muted-foreground hover:text-foreground transition-colors [&.active]:text-primary [&.active]:font-semibold"
            >
              Home
            </Link>
            <Link
              to="/dashboard"
              className="text-muted-foreground hover:text-foreground transition-colors [&.active]:text-primary [&.active]:font-semibold"
            >
              Studio
            </Link>
            <Link
              to="/history"
              className="text-muted-foreground hover:text-foreground transition-colors [&.active]:text-primary [&.active]:font-semibold"
            >
              History
            </Link>
          </nav>

          <div className="flex items-center gap-3">
            <div
              className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium shadow-sm ${
                healthOk
                  ? "border-emerald-200/80 bg-emerald-50/90 text-emerald-800"
                  : "border-red-200/80 bg-red-50/90 text-red-800"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${healthOk ? "bg-emerald-500" : "bg-red-500"}`}
                aria-hidden
              />
              {healthOk ? "System online" : "System offline"}
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-16 pb-20 px-4 sm:px-6 lg:px-8 mx-auto max-w-6xl text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/10 bg-primary/[0.04] px-4 py-1.5 text-xs font-semibold text-primary mb-6 animate-fade-in">
          <span>Powered by LangGraph &amp; Local RAG</span>
        </div>
        
        <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl md:text-6xl max-w-4xl mx-auto leading-[1.15]">
          Generate Professional University{" "}
          <span className="bg-gradient-to-r from-primary via-[oklch(0.42_0.09_255)] to-indigo-600 bg-clip-text text-transparent">
            Question Papers
          </span>{" "}
          in Minutes
        </h1>
        
        <p className="mt-6 text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          Upload your syllabus, configure question weightings, and let our multi-agent AI system handle the ingestion, difficulty distribution, compliance checking, and answer key generation.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            to="/dashboard"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-7 py-4 text-sm font-semibold tracking-wide text-primary-foreground shadow-[0_4px_14px_-4px_oklch(0.32_0.07_257/0.45)] ring-1 ring-primary/20 transition hover:bg-primary/95 hover:scale-[1.02] active:scale-[0.98]"
          >
            Open Exam Studio
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 5"/>
            </svg>
          </Link>
          <Link
            to="/history"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-border/80 bg-white/90 px-7 py-4 text-sm font-semibold text-foreground transition hover:border-primary/30 hover:bg-primary/[0.04] hover:scale-[1.02] active:scale-[0.98]"
          >
            Browse History
          </Link>
        </div>
      </section>

      {/* Features Overview */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 mx-auto max-w-6xl border-t border-border/40">
        <div className="text-center mb-12">
          <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            A Compliant Multi-Agent System
          </h2>
          <p className="mt-2 text-sm text-muted-foreground max-w-xl mx-auto">
            Our pipeline is split into isolated specialized agents, working sequentially to generate highly accurate outputs.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-5">
          {agents.map((ag) => (
            <div
              key={ag.step}
              className="relative overflow-hidden rounded-xl border border-white/80 bg-white/85 p-5 shadow-[0_1px_2px_oklch(0.32_0.07_257/0.02),0_6px_20px_-10px_oklch(0.32_0.07_257/0.06)] backdrop-blur-sm transition-all duration-200 hover:shadow-[0_8px_24px_-8px_oklch(0.32_0.07_257/0.1)] hover:border-primary/10"
            >
              <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-primary/10 via-primary/30 to-primary/10" />
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm border border-border/50 mb-4">
                {ag.icon}
              </div>
              <span className="text-[10px] font-bold text-primary tracking-wider uppercase">{ag.role}</span>
              <h3 className="mt-1 text-sm font-bold text-foreground">{ag.name}</h3>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{ag.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Stats Summary */}
      <section className="py-12 bg-white/40 border-y border-border/40 backdrop-blur-sm">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3 text-center">
            <div className="p-4">
              <span className="block text-4xl font-extrabold text-primary tracking-tight">100%</span>
              <span className="mt-1.5 block text-sm font-medium text-muted-foreground">Syllabus Alignment Guarantee</span>
            </div>
            <div className="p-4 border-y sm:border-y-0 sm:border-x border-border/50">
              <span className="block text-4xl font-extrabold text-primary tracking-tight">RAG-first</span>
              <span className="mt-1.5 block text-sm font-medium text-muted-foreground">Contextual Search Retrieval</span>
            </div>
            <div className="p-4">
              <span className="block text-4xl font-extrabold text-primary tracking-tight">A4 PDF</span>
              <span className="mt-1.5 block text-sm font-medium text-muted-foreground">ReportLab Ready formatting</span>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative py-8 border-t border-border/40 bg-white/20">
        <p className="text-center text-xs text-muted-foreground">
          Question Paper Generator · For institutional use
        </p>
      </footer>
    </div>
  );
}

function BackgroundFX() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10">
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(165deg, oklch(0.97 0.012 240) 0%, oklch(0.955 0.018 235) 35%, oklch(0.975 0.008 250) 65%, oklch(0.988 0.006 255) 100%)",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.55]"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 90% 60% at 10% -10%, oklch(0.88 0.04 240 / 0.35), transparent 55%), radial-gradient(ellipse 70% 50% at 95% 20%, oklch(0.9 0.035 230 / 0.25), transparent 50%), radial-gradient(ellipse 60% 40% at 50% 100%, oklch(0.92 0.025 250 / 0.2), transparent 45%)",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.4]"
        style={{
          backgroundImage:
            "linear-gradient(oklch(0.32 0.07 257 / 0.04) 1px, transparent 1px), linear-gradient(90deg, oklch(0.32 0.07 257 / 0.04) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "linear-gradient(to bottom, black 0%, transparent 85%)",
          WebkitMaskImage: "linear-gradient(to bottom, black 0%, transparent 85%)",
        }}
      />
    </div>
  );
}
