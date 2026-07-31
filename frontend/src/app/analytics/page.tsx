"use client";

import Link from "next/link";
import React, { useEffect, useState } from "react";
import { getAnalytics, type AnalyticsResponse } from "@/lib/api";
import { motion } from "framer-motion";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";
import { Activity, Brain, Clock, FileText, Zap } from "lucide-react";



const BLOOM_COLORS = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#ec4899"];
const DIFF_COLORS: Record<string, string> = { easy: "#10b981", medium: "#f59e0b", hard: "#ef4444" };

function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAnalytics()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-background p-4 text-center">
        <p className="text-destructive font-medium mb-4">{error || "Failed to load data"}</p>
        <Link href="/" className="text-primary hover:underline">
          Return Home
        </Link>
      </div>
    );
  }

  const bloomData = Object.entries(data.bloom_distribution).map(([name, value]) => ({ name, value }));
  const diffData = Object.entries(data.difficulty_distribution).map(([name, value]) => ({ name, value }));

  return (
    <div className="min-h-screen bg-background pb-12 relative overflow-hidden">
      {/* Premium Glassmorphism Background Glow */}
      <div className="absolute top-0 right-0 w-[800px] h-[800px] bg-primary/10 rounded-full blur-[120px] pointer-events-none -translate-y-1/2 translate-x-1/3" />
      <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-purple-500/10 rounded-full blur-[100px] pointer-events-none translate-y-1/3 -translate-x-1/3" />
      
      

      <main className="relative mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-10"
        >
          <h1 className="text-3xl font-bold tracking-tight text-secondary">System Analytics</h1>
          <p className="mt-2 text-muted-foreground">Detailed insights and performance metrics for your RAG generation pipeline.</p>
        </motion.div>

        {/* Stats Grid */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-10">
          <StatCard 
            title="Total Papers" 
            value={data.total_papers} 
            icon={FileText} 
            iconColor="text-primary"
            delay={0.1}
          />
          <StatCard 
            title="Questions Generated" 
            value={data.total_questions.toLocaleString()} 
            icon={Activity} 
            iconColor="text-emerald-500"
            delay={0.2}
          />
          <StatCard 
            title="Avg. Gen Time" 
            value={`${data.average_generation_time}s`} 
            icon={Clock} 
            iconColor="text-amber-500"
            delay={0.3}
          />
          <StatCard 
            title="Avg Qs / Paper" 
            value={data.total_papers > 0 ? Math.round(data.total_questions / data.total_papers).toString() : "0"} 
            icon={Zap} 
            iconColor="text-purple-500"
            delay={0.4}
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-2 mb-6">
          {/* Recent Activity Line Chart */}
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.5 }}
            className="rounded-2xl border border-white/20 bg-white/40 dark:bg-black/40 backdrop-blur-md p-6 shadow-xl shadow-black/5"
          >
            <h3 className="text-lg font-semibold mb-6">Generation Activity (Last 7 Days)</h3>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={[...data.recent_activity].reverse()}>
                  <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="opacity-10" vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    stroke="currentColor" 
                    className="text-xs opacity-50"
                    tickFormatter={(val) => val.split('-').slice(1).join('/')}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis stroke="currentColor" className="text-xs opacity-50" tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)', borderRadius: '12px', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                    itemStyle={{ color: 'var(--foreground)' }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="papers" 
                    stroke="var(--primary)" 
                    strokeWidth={4}
                    dot={{ fill: 'var(--background)', stroke: 'var(--primary)', strokeWidth: 2, r: 4 }}
                    activeDot={{ r: 8, fill: 'var(--primary)', stroke: 'var(--background)' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          {/* Bloom's Taxonomy Donut Chart */}
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.6 }}
            className="rounded-2xl border border-white/20 bg-white/40 dark:bg-black/40 backdrop-blur-md p-6 shadow-xl shadow-black/5 flex flex-col"
          >
            <h3 className="text-lg font-semibold mb-2">Bloom's Taxonomy Distribution</h3>
            <div className="flex-1 min-h-[300px] w-full relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={bloomData}
                    cx="50%"
                    cy="50%"
                    innerRadius={80}
                    outerRadius={110}
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                  >
                    {bloomData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={BLOOM_COLORS[index % BLOOM_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)', borderRadius: '12px' }}
                    itemStyle={{ color: 'var(--foreground)', fontWeight: '600' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Center Text */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-4xl font-extrabold tracking-tight bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">{data.total_questions}</span>
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold mt-1">Total Qs</span>
              </div>
            </div>
            <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 mt-4">
              {bloomData.map((entry, index) => (
                <div key={entry.name} className="flex items-center gap-1.5 text-xs">
                  <div className="w-3 h-3 rounded-full shadow-sm" style={{ backgroundColor: BLOOM_COLORS[index % BLOOM_COLORS.length] }} />
                  <span className="text-muted-foreground font-medium">{entry.name}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Difficulty Bar Chart */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="rounded-2xl border border-white/20 bg-white/40 dark:bg-black/40 backdrop-blur-md p-6 shadow-xl shadow-black/5"
        >
          <h3 className="text-lg font-semibold mb-6">Difficulty Spread</h3>
          <div className="h-[250px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={diffData} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="currentColor" className="opacity-10" />
                <XAxis type="number" stroke="currentColor" className="text-xs opacity-50" tickLine={false} axisLine={false} />
                <YAxis 
                  dataKey="name" 
                  type="category" 
                  stroke="currentColor" 
                  className="text-xs font-semibold capitalize opacity-80" 
                  width={60}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip 
                  cursor={{fill: 'var(--muted)', opacity: 0.2}}
                  contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)', borderRadius: '12px' }}
                />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={24}>
                  {diffData.map((entry) => (
                    <Cell key={entry.name} fill={DIFF_COLORS[entry.name] || "var(--primary)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      </main>
    </div>
  );
}

function StatCard({ title, value, icon: Icon, iconColor, delay }: { title: string; value: string | number; icon: React.ElementType; iconColor: string; delay: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5, ease: "easeOut" }}
      className="rounded-2xl border border-white/20 bg-white/40 dark:bg-black/40 backdrop-blur-md p-6 shadow-lg shadow-black/5 hover:shadow-xl transition-shadow relative overflow-hidden group cursor-default"
    >
      <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-all transform group-hover:scale-125 group-hover:rotate-12 duration-500">
        <Icon className="w-24 h-24" />
      </div>
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2.5 rounded-xl bg-background/80 shadow-sm border border-border/50">
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
        <h3 className="font-semibold text-sm text-muted-foreground">{title}</h3>
      </div>
      <p className="text-4xl font-extrabold tracking-tight bg-gradient-to-br from-foreground to-foreground/80 bg-clip-text text-transparent">{value}</p>
    </motion.div>
  );
}

export default AnalyticsPage;
