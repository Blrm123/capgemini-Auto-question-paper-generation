"use client";

import { useEffect, useState } from "react";
import { getLatestPaperAnalytics, type PaperAnalyticsResponse } from "@/lib/api";
import { AnalyticsView, AnalyticsLoading, AnalyticsEmpty } from "@/components/AnalyticsView";

export default function AnalyticsPage() {
  const [data, setData] = useState<PaperAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLatestPaperAnalytics()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <AnalyticsLoading />;
  if (error || !data) return <AnalyticsEmpty message={
    error?.includes("No papers") || error?.includes("No papers generated")
      ? "Generate a question paper first to see per-paper analytics here."
      : error ?? undefined
  } />;

  return (
    <AnalyticsView
      data={data}
      backHref="/dashboard"
      backLabel="← Dashboard"
    />
  );
}
