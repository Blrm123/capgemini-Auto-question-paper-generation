"use client";

import Link from "next/link";
import React from "react";
import { type PaperAnalyticsResponse } from "@/lib/api";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, RadarChart, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Radar,
} from "recharts";
import {
  Activity, Brain, Clock, FileText, Layers, BookOpen, BarChart2, Target,
} from "lucide-react";

const BLOOM_ORDER = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"];

const BLOOM_COLORS: Record<string, string> = {
  Remember: "var(--chart-1)",
  Understand: "var(--chart-2)",
  Apply: "var(--chart-3)",
  Analyze: "var(--chart-4)",
  Evaluate: "var(--chart-5)",
  Create: "var(--muted-foreground)",
};

const DIFF_COLORS: Record<string, string> = {
  easy: "var(--chart-3)",
  medium: "var(--chart-4)",
  hard: "var(--chart-5)",
};

const MARKS_COLORS: Record<string, string> = {
  "1": "var(--chart-1)",
  "2": "var(--chart-2)",
  "5": "var(--chart-3)",
  "10": "var(--chart-4)",
  "15": "var(--chart-5)",
};

const UNIT_GRADIENT = [
  "var(--foreground)",
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--muted-foreground)",
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
];

export function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("en-IN", {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

export function fmtSeconds(s: number) {
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${(s % 60).toFixed(0)}s`;
}

const tooltipStyle = {
  backgroundColor: "var(--background)",
  border: "1px solid var(--border)",
  borderRadius: "6px",
  boxShadow: "0 8px 20px -6px rgba(0,0,0,0.15)",
  color: "var(--foreground)",
  fontSize: "12px",
  fontWeight: 600,
  fontFamily: "var(--font-mono)",
};

export function AnalyticsView({
  data,
  backHref = "/dashboard",
  backLabel = "← Back",
}: {
  data: PaperAnalyticsResponse;
  backHref?: string;
  backLabel?: string;
}) {
  const bloomData = BLOOM_ORDER.map((n) => ({ name: n, value: data.bloom_distribution[n] ?? 0 })).filter((d) => d.value > 0);
  const diffData = Object.entries(data.difficulty_distribution).map(([name, value]) => ({ name, value })).filter((d) => d.value > 0);
  const marksData = Object.entries(data.marks_distribution).map(([name, value]) => ({ name: `${name}M`, value })).filter((d) => d.value > 0);
  const unitData = data.unit_coverage.slice(0, 10);
  const bloomDiffData = Object.entries(data.bloom_by_difficulty).map(([diff, levels]) => ({
    diff: diff.charAt(0).toUpperCase() + diff.slice(1), ...levels,
  }));
  const totalBloom = BLOOM_ORDER.reduce((s, l) => s + (data.bloom_distribution[l] ?? 0), 0);
  const radarData = BLOOM_ORDER.map((level) => ({
    level, value: totalBloom > 0 ? Math.round(((data.bloom_distribution[level] ?? 0) / totalBloom) * 100) : 0,
  }));
  const bloomUsed = BLOOM_ORDER.filter((l) => (data.bloom_distribution[l] ?? 0) > 0).length;

  return (
    <div className="relative min-h-screen bg-background text-foreground font-serif">
      {/* Paper margin line */}
      <div className="fixed top-0 bottom-0 left-[20px] sm:left-[48px] w-[1.5px] bg-primary/35 z-0" />

      <main className="relative z-10 mx-auto max-w-[1180px] px-7 sm:px-[64px] pt-4">
        {/* Header */}
        <header className="mb-10 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-primary">
              Paper Analytics
            </p>
            <h1 className="font-serif text-[clamp(28px,4vw,40px)] font-bold leading-tight m-0 text-secondary">
              {data.course_name} <span className="font-medium text-muted-foreground">— {data.exam_type}</span>
            </h1>
            <p className="mt-2.5 font-mono text-[13px] text-muted-foreground">
              {fmtDate(data.generated_at)} &nbsp;·&nbsp; Paper ID: <span className="font-bold text-foreground">{data.paper_id}</span>
            </p>
          </div>
          <Link
            href={backHref}
            className="rounded-lg border border-foreground/20 bg-card px-[18px] py-[10px] text-[12px] font-bold tracking-[0.03em] text-foreground no-underline transition hover:bg-muted"
          >
            {backLabel}
          </Link>
        </header>

        {/* Stat cards */}
        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard title="Total Questions" value={data.total_questions} icon={FileText} color="var(--foreground)" />
          <StatCard title="Total Marks" value={data.total_marks} icon={Target} color="var(--chart-3)" />
          <StatCard title="Generation Time" value={fmtSeconds(data.elapsed_seconds)} icon={Clock} color="var(--chart-4)" />
          <StatCard title="Bloom Levels Used" value={`${bloomUsed} / 6`} icon={Brain} color="var(--chart-1)" />
        </div>

        {/* Row 1 */}
        <div className="mb-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
          <ChartCard title="Bloom's Taxonomy Distribution" icon={Brain}>
            <div className="flex flex-col items-center">
              <div className="relative h-[260px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={bloomData} cx="50%" cy="50%" innerRadius={70} outerRadius={102} paddingAngle={3} dataKey="value" stroke="none">
                      {bloomData.map((e) => <Cell key={e.name} fill={BLOOM_COLORS[e.name]} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [`${v} question${v !== 1 ? "s" : ""} (${Math.round((Number(v) / totalBloom) * 100)}%)`, String(n)]} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="font-serif text-[38px] font-bold text-foreground">{data.total_questions}</span>
                  <span className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Questions</span>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-2">
                {bloomData.map((e) => (
                  <Legend2 key={e.name} color={BLOOM_COLORS[e.name]} label={e.name} value={e.value} />
                ))}
              </div>
            </div>
          </ChartCard>

          <ChartCard title="Difficulty Level Spread" icon={Layers}>
            <div className="h-[270px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={diffData} layout="vertical" margin={{ left: 8, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--foreground)" strokeOpacity={0.08} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} />
                  <YAxis dataKey="name" type="category" width={65} tickLine={false} axisLine={false}
                    tick={{ fontSize: 12, fontWeight: 700, fill: "var(--foreground)" }}
                    tickFormatter={(v) => String(v).charAt(0).toUpperCase() + String(v).slice(1)} />
                  <Tooltip cursor={{ fill: "var(--foreground)", opacity: 0.05 }} contentStyle={tooltipStyle}
                    formatter={(v, n) => [`${v} questions`, String(n).charAt(0).toUpperCase() + String(n).slice(1)]} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={26}>
                    {diffData.map((e) => <Cell key={e.name} fill={DIFF_COLORS[e.name]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3.5 flex flex-wrap gap-2.5">
              {diffData.map((d) => {
                const pct = Math.round((d.value / data.total_questions) * 100);
                return (
                  <div key={d.name} className="flex-1 min-w-[80px] rounded-lg p-2.5 text-center bg-foreground/5">
                    <div className="font-serif text-[22px] font-bold" style={{ color: DIFF_COLORS[d.name] }}>{pct}%</div>
                    <div className="mt-0.5 text-[10px] font-bold uppercase tracking-[0.06em] text-muted-foreground">
                      {d.name}
                    </div>
                  </div>
                );
              })}
            </div>
          </ChartCard>
        </div>

        {/* Row 2 */}
        <div className="mb-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
          <ChartCard title="Marks Distribution" icon={Activity}>
            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={marksData} margin={{ top: 4, right: 10, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--foreground)" strokeOpacity={0.08} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip cursor={{ fill: "var(--foreground)", opacity: 0.05 }} contentStyle={tooltipStyle} formatter={(v) => [`${v} question${v !== 1 ? "s" : ""}`, "Count"]} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={34}>
                    {marksData.map((e) => <Cell key={e.name} fill={MARKS_COLORS[e.name.replace("M", "")]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3.5 flex flex-wrap justify-center gap-3.5">
              {marksData.map((m) => (
                <Legend2 key={m.name} color={MARKS_COLORS[m.name.replace("M", "")]} label={m.name} value={m.value} prefix="×" />
              ))}
            </div>
          </ChartCard>

          <ChartCard title="Unit Coverage" icon={BookOpen}>
            <div className="h-[270px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={unitData} layout="vertical" margin={{ left: 4, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--foreground)" strokeOpacity={0.08} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <YAxis dataKey="unit" type="category" width={120} tickLine={false} axisLine={false}
                    tick={{ fontSize: 11, fill: "var(--foreground)", fontWeight: 600 }}
                    tickFormatter={(v: string) => (v.length > 18 ? v.slice(0, 17) + "…" : v)} />
                  <Tooltip cursor={{ fill: "var(--foreground)", opacity: 0.05 }} contentStyle={tooltipStyle} formatter={(v) => [`${v} question${v !== 1 ? "s" : ""}`, "Count"]} />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={20}>
                    {unitData.map((_, i) => <Cell key={i} fill={UNIT_GRADIENT[i % UNIT_GRADIENT.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>
        </div>

        {/* Row 3 */}
        <div className="mb-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
          <ChartCard title="Bloom's Level by Difficulty" icon={BarChart2}>
            <div className="h-[270px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bloomDiffData} margin={{ top: 4, right: 10, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--foreground)" strokeOpacity={0.08} />
                  <XAxis dataKey="diff" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip cursor={{ fill: "var(--foreground)", opacity: 0.05 }} contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 10, paddingTop: 10 }} formatter={(v) => <span className="font-bold text-muted-foreground">{v}</span>} />
                  {BLOOM_ORDER.map((level) => (
                    <Bar key={level} dataKey={level} stackId="bloom" fill={BLOOM_COLORS[level]} radius={[0, 0, 0, 0]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>

          <ChartCard title="Cognitive Level Radar" icon={Brain}>
            <div className="h-[270px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={92}>
                  <PolarGrid stroke="var(--foreground)" strokeOpacity={0.15} />
                  <PolarAngleAxis dataKey="level" tick={{ fill: "var(--muted-foreground)", fontSize: 10, fontWeight: 700 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "var(--muted-foreground)", fontSize: 9 }} tickCount={4} axisLine={false} />
                  <Radar name="Coverage %" dataKey="value" stroke="var(--primary)" fill="var(--primary)" fillOpacity={0.2} strokeWidth={2} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v}%`, "Coverage"]} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-center font-mono text-[11px] text-muted-foreground">
              % of questions at each Bloom's level
            </p>
          </ChartCard>
        </div>

        
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------------
   Sub-components
------------------------------------------------------------------------- */
function StatCard({ title, value, icon: Icon, color }: { title: string, value: string | number, icon: any, color: string }) {
  return (
    <div className="relative overflow-hidden rounded-[10px] border border-foreground/[0.08] bg-card p-[18px_18px_16px] shadow-sm">
      <div className="mb-3 flex items-center gap-2.5">
        <div className="flex h-[30px] w-[30px] items-center justify-center rounded-full border-2 border-current" style={{ color }}>
          <Icon size={14} />
        </div>
        <h3 className="m-0 text-[11px] font-bold uppercase tracking-[0.06em] text-muted-foreground">{title}</h3>
      </div>
      <p className="m-0 font-serif text-[30px] font-bold text-foreground">{value}</p>
    </div>
  );
}

function ChartCard({ title, icon: Icon, children }: { title: string, icon: any, children: React.ReactNode }) {
  return (
    <div className="rounded-[10px] border border-foreground/[0.08] bg-card p-[22px] shadow-sm">
      <div className="mb-[18px] flex items-center gap-2">
        <div className="flex h-[26px] w-[26px] items-center justify-center rounded-md bg-primary/10">
          <Icon size={13} className="text-primary" />
        </div>
        <h3 className="m-0 text-[14px] font-bold text-foreground">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function Legend2({ color, label, value, prefix = "" }: { color: string, label: string, value: number, prefix?: string }) {
  return (
    <div className="flex items-center gap-1.5 text-[12px]">
      <div className="h-[9px] w-[9px] shrink-0 rounded-[3px]" style={{ backgroundColor: color }} />
      <span className="font-semibold text-muted-foreground">{label}</span>
      <span className="font-mono font-extrabold text-foreground">{prefix}{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading & Error states
// ---------------------------------------------------------------------------
export function AnalyticsLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background font-serif">
      <div className="flex flex-col items-center gap-4">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-foreground/20 border-t-primary" />
        <p className="text-[14px] font-semibold text-muted-foreground">Loading analytics…</p>
      </div>
    </div>
  );
}

export function AnalyticsEmpty({ message, href = "/dashboard" }: { message?: string; href?: string }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4 font-serif">
      <div className="max-w-[384px] w-full rounded-[10px] border border-foreground/[0.08] bg-card p-10 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
          <BarChart2 size={32} className="text-primary" />
        </div>
        <h2 className="mb-2 font-serif text-[20px] font-bold text-foreground">No Analytics Yet</h2>
        <p className="mb-6 text-[14px] leading-relaxed text-muted-foreground">
          {message ?? "Generate a question paper first to see per-paper analytics here."}
        </p>
        <Link
          href={href}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-[14px] font-semibold text-primary-foreground no-underline transition hover:opacity-90"
        >
          {href === "/dashboard" ? "Go to Dashboard" : "← Back"}
        </Link>
      </div>
    </div>
  );
}
