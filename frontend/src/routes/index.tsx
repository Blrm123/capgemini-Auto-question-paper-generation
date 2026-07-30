import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { getHealth, type HealthResponse } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Question Paper Generator - AI-assisted Exam Builder" },
      {
        name: "description",
        content:
          "Create professional college-level question papers and answer keys with multi-agent LangGraph orchestration and RAG.",
      },
      { property: "og:title", content: "Question Paper Generator - AI-assisted Exam Builder" },
      {
        property: "og:description",
        content:
          "Create professional college-level question papers and answer keys with multi-agent LangGraph orchestration and RAG.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

/* ---------------- scroll reveal ---------------- */

function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: any;
}) {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof window === "undefined" || !("IntersectionObserver" in window)) {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            setVisible(true);
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -60px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <Tag
      ref={ref as any}
      style={{ transitionDelay: `${delay}ms` }}
      className={`qpg-reveal ${visible ? "qpg-in" : ""} ${className}`}
    >
      {children}
    </Tag>
  );
}

function useScrollY() {
  const [y, setY] = useState(0);
  useEffect(() => {
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => setY(window.scrollY));
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);
  return y;
}

/* ---------------- page ---------------- */

const AGENTS = [
  {
    name: "Planner Agent",
    desc: "Breaks the syllabus into a blueprint: units, weightage, Bloom's levels and mark distribution.",
    tone: "from-indigo-500 to-violet-500",
  },
  {
    name: "Retriever Agent",
    desc: "RAG over your uploaded notes, textbooks and past papers to ground every question in real material.",
    tone: "from-violet-500 to-fuchsia-500",
  },
  {
    name: "Writer Agent",
    desc: "Drafts questions in clean academic language with correct marks, sections and instructions.",
    tone: "from-fuchsia-500 to-rose-500",
  },
  {
    name: "Reviewer Agent",
    desc: "Checks difficulty balance, duplication and syllabus coverage before the paper is finalised.",
    tone: "from-cyan-500 to-indigo-500",
  },
];

function Index() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState(false);
  const scrollY = useScrollY();
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    getHealth()
      .then((res) => setHealth(res))
      .catch(() => setHealthError(true));
  }, []);

  useEffect(() => {
    const doc = document.documentElement;
    const max = doc.scrollHeight - doc.clientHeight;
    setProgress(max > 0 ? (scrollY / max) * 100 : 0);
  }, [scrollY]);

  const online = !!health && !healthError;

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[#f7f8fc] text-slate-800 antialiased">
      <StyleFX />
      <BackgroundFX scrollY={scrollY} />

      {/* scroll progress */}
      <div className="fixed inset-x-0 top-0 z-50 h-[3px] bg-transparent">
        <div
          className="h-full bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 transition-[width] duration-150 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3.5">
          <Link to="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-500 text-white shadow-md shadow-indigo-500/20">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                className="h-5 w-5"
              >
                <path d="M6 3h9l4 4v14H6z" strokeLinejoin="round" />
                <path d="M9 12h6M9 16h4" strokeLinecap="round" />
              </svg>
            </div>
            <div className="leading-tight">
              <p className="text-sm font-semibold text-slate-900">Question Paper Generator</p>
              <p className="text-xs text-slate-500">AI assessment studio</p>
            </div>
          </Link>

          <nav className="hidden items-center gap-2 rounded-full border border-slate-200 bg-white/80 p-1 md:flex">
            <Link
              to="/"
              className="rounded-full px-3.5 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
            >
              Home
            </Link>
            <Link
              to="/dashboard"
              className="rounded-full px-3.5 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
            >
              Dashboard
            </Link>
            <Link
              to="/history"
              className="rounded-full px-3.5 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
            >
              History
            </Link>
          </nav>

          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1.5 text-[11px] font-medium ${online ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-50 text-slate-600"}`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${online ? "bg-emerald-500" : "bg-slate-400"}`}
              />
              {online ? "Online" : "Offline"}
            </span>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto w-full max-w-6xl px-6 pb-24 pt-24 sm:pt-32">
        {/* Hero */}
        <section className="text-center">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-indigo-200/80 bg-white/70 px-4 py-1.5 text-xs font-medium tracking-wide text-indigo-700 shadow-sm backdrop-blur">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-500" />
              </span>
              Multi-agent LangGraph orchestration
            </span>
          </Reveal>

          <Reveal delay={90}>
            <h1 className="mt-7 text-balance text-4xl font-semibold leading-[1.08] tracking-tight text-slate-900 sm:text-6xl">
              Build exam-ready{" "}
              <span className="qpg-gradient-text bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 bg-clip-text text-transparent">
                question papers
              </span>{" "}
              in minutes
            </h1>
          </Reveal>

          <Reveal delay={170}>
            <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-relaxed text-slate-600 sm:text-lg">
              Upload your syllabus and reference material. A team of AI agents plans the blueprint,
              retrieves grounded content, drafts the paper and reviews it — complete with an answer
              key.
            </p>
          </Reveal>

          <Reveal delay={250}>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <Link
                to="/dashboard"
                className="qpg-shine group relative inline-flex items-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-indigo-500/35"
              >
                Generate a paper
                <span className="transition-transform duration-300 group-hover:translate-x-1">
                  →
                </span>
              </Link>
              <Link
                to="/history"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-6 py-3 text-sm font-semibold text-slate-700 shadow-sm backdrop-blur transition-all duration-300 hover:-translate-y-0.5 hover:border-indigo-200 hover:bg-white hover:text-indigo-700 hover:shadow-md"
              >
                View saved papers
              </Link>
            </div>
          </Reveal>

          <Reveal delay={330}>
            <div className="mt-8 flex justify-center">
              <span
                className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-medium backdrop-blur transition-colors ${
                  online
                    ? "border-emerald-200 bg-emerald-50/80 text-emerald-700"
                    : healthError
                      ? "border-rose-200 bg-rose-50/80 text-rose-700"
                      : "border-slate-200 bg-white/70 text-slate-500"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    online ? "bg-emerald-500" : healthError ? "bg-rose-500" : "bg-slate-400"
                  } ${online ? "animate-pulse" : ""}`}
                />
                {online
                  ? `Backend online${health?.status ? ` · ${health.status}` : ""}`
                  : healthError
                    ? "Backend unreachable"
                    : "Checking backend…"}
              </span>
            </div>
          </Reveal>
        </section>

        {/* Agents */}
        <section className="mt-28">
          <Reveal>
            <h2 className="text-center text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
              Four agents, one clean paper
            </h2>
          </Reveal>
          <Reveal delay={80}>
            <p className="mx-auto mt-3 max-w-xl text-center text-sm text-slate-600 sm:text-base">
              Each stage is specialised, inspectable and re-runnable.
            </p>
          </Reveal>

          <div className="mt-12 grid gap-5 sm:grid-cols-2">
            {AGENTS.map((a, i) => (
              <Reveal key={a.name} delay={120 + i * 90}>
                <article className="qpg-card group relative h-full overflow-hidden rounded-2xl border border-slate-200/80 bg-white/75 p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_12px_30px_-18px_rgba(79,70,229,0.35)] backdrop-blur transition-all duration-500 hover:-translate-y-1.5 hover:border-indigo-200 hover:shadow-[0_1px_2px_rgba(15,23,42,0.05),0_24px_50px_-20px_rgba(124,58,237,0.45)]">
                  <div
                    className={`absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r ${a.tone} opacity-70 transition-opacity duration-500 group-hover:opacity-100`}
                  />
                  <div
                    className={`mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${a.tone} text-sm font-bold text-white shadow-md transition-transform duration-500 group-hover:scale-110 group-hover:rotate-3`}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <h3 className="text-base font-semibold text-slate-900">{a.name}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{a.desc}</p>
                  <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-gradient-to-br from-indigo-300/0 to-fuchsia-300/40 opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-100" />
                </article>
              </Reveal>
            ))}
          </div>
        </section>

        {/* Highlights */}
        <section className="mt-28 grid gap-5 sm:grid-cols-3">
          {[
            [
              "RAG-grounded",
              "Questions trace back to your own uploaded material, not generic web text.",
            ],
            ["Answer keys", "Every paper ships with a matching key and marking scheme."],
            ["Export ready", "Clean, printable formatting suitable for institutional use."],
          ].map(([title, desc], i) => (
            <Reveal key={title} delay={i * 110}>
              <div className="qpg-card h-full rounded-2xl border border-slate-200/80 bg-white/70 p-6 text-center backdrop-blur transition-all duration-500 hover:-translate-y-1 hover:border-violet-200 hover:bg-white">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-indigo-600">
                  {title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-600">{desc}</p>
              </div>
            </Reveal>
          ))}
        </section>

        {/* CTA */}
        <Reveal delay={80}>
          <section className="relative mt-28 overflow-hidden rounded-3xl border border-indigo-200/70 bg-gradient-to-br from-indigo-50 via-white to-fuchsia-50 px-8 py-14 text-center shadow-[0_30px_60px_-40px_rgba(79,70,229,0.5)]">
            <div className="pointer-events-none absolute inset-0 opacity-60 [background:radial-gradient(600px_200px_at_50%_0%,rgba(124,58,237,0.18),transparent_70%)]" />
            <h2 className="relative text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
              Ready to set your next paper?
            </h2>
            <p className="relative mx-auto mt-3 max-w-md text-sm text-slate-600">
              Start from a syllabus and get a reviewed draft with an answer key.
            </p>
            <Link
              to="/generate"
              className="qpg-shine relative mt-8 inline-flex items-center gap-2 overflow-hidden rounded-xl bg-slate-900 px-6 py-3 text-sm font-semibold text-white shadow-lg transition-all duration-300 hover:-translate-y-0.5 hover:bg-slate-800"
            >
              Get started
              <span>→</span>
            </Link>
          </section>
        </Reveal>

        {/* Footer */}
        <Reveal delay={60}>
          <footer className="mt-20 border-t border-slate-200 pt-8">
            <p className="text-center text-xs text-slate-500">
              Question Paper Generator · For institutional use
            </p>
          </footer>
        </Reveal>
      </main>
    </div>
  );
}

/* ---------------- background + styles ---------------- */

function BackgroundFX({ scrollY }: { scrollY: number }) {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {/* plain background color only */}
      <div className="absolute inset-0 bg-[#f7f8fc]" />

      {/* Decorative background layer temporarily disabled */}
      {/* <div className="absolute inset-0 bg-[linear-gradient(180deg,#ffffff_0%,#f6f7fd_45%,#f4f2fb_100%)]" /> */}
      {/* <div className="absolute inset-0 opacity-[0.5] [background-image:linear-gradient(to_right,rgba(15,23,42,0.05)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.05)_1px,transparent_1px)] [background-size:64px_64px] [mask-image:radial-gradient(ellipse_at_50%_0%,black_10%,transparent_75%)]" /> */}
      {/* <div
        className="absolute -left-32 -top-24 h-[34rem] w-[34rem] rounded-full bg-indigo-400/25 blur-[130px] [animation:qpgFloat_18s_ease-in-out_infinite]"
        style={{ transform: `translateY(${scrollY * 0.12}px)` }}
      /> */}
      {/* <div
        className="absolute right-[-10rem] top-40 h-[30rem] w-[30rem] rounded-full bg-fuchsia-400/20 blur-[130px] [animation:qpgFloatAlt_22s_ease-in-out_infinite]"
        style={{ transform: `translateY(${scrollY * -0.08}px)` }}
      /> */}
      {/* <div
        className="absolute bottom-[-8rem] left-1/3 h-[26rem] w-[26rem] rounded-full bg-cyan-300/25 blur-[120px] [animation:qpgFloat_26s_ease-in-out_infinite]"
        style={{ transform: `translateY(${scrollY * 0.05}px)` }}
      /> */}
    </div>
  );
}

function StyleFX() {
  return (
    <style>{`
      @keyframes qpgFloat {
        0%,100% { translate: 0 0; }
        50% { translate: 30px -24px; }
      }
      @keyframes qpgFloatAlt {
        0%,100% { translate: 0 0; }
        50% { translate: -34px 26px; }
      }
      @keyframes qpgGradient {
        0%,100% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
      }
      @keyframes qpgShine {
        0% { transform: translateX(-120%) skewX(-20deg); }
        100% { transform: translateX(220%) skewX(-20deg); }
      }
      .qpg-gradient-text {
        background-size: 200% auto;
        animation: qpgGradient 6s ease-in-out infinite;
      }
      .qpg-reveal {
        opacity: 0;
        transform: translateY(28px) scale(0.985);
        transition: opacity 700ms cubic-bezier(0.22,1,0.36,1),
                    transform 700ms cubic-bezier(0.22,1,0.36,1);
        will-change: opacity, transform;
      }
      .qpg-reveal.qpg-in {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
      .qpg-shine::after {
        content: "";
        position: absolute;
        top: 0; left: 0;
        height: 100%; width: 45%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.45), transparent);
        transform: translateX(-120%) skewX(-20deg);
      }
      .qpg-shine:hover::after {
        animation: qpgShine 900ms ease-out;
      }
      @media (prefers-reduced-motion: reduce) {
        .qpg-reveal { opacity: 1 !important; transform: none !important; transition: none !important; }
        .qpg-gradient-text, .qpg-shine:hover::after { animation: none !important; }
      }
    `}</style>
  );
}
