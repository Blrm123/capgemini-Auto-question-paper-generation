"use client";

import { use, useEffect, useState } from "react";
import { getPaperAnalytics, type PaperAnalyticsResponse } from "@/lib/api";
import { AnalyticsView, AnalyticsLoading, AnalyticsEmpty } from "@/components/AnalyticsView";

export default function PaperAnalyticsPage({
  params,
}: {
  params: Promise<{ paper_id: string }>;
}) {
  const { paper_id } = use(params);
  const [data, setData]       = useState<PaperAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!paper_id) return;
    getPaperAnalytics(paper_id)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [paper_id]);

  if (loading) return <AnalyticsLoading />;
  if (error || !data) return (
    <AnalyticsEmpty
      message={
        error?.includes("not found")
          ? "No analytics record found for this paper. Analytics are only available for papers generated after the analytics upgrade."
          : (error ?? "Failed to load analytics for this paper.")
      }
      href="/history"
    />
  );

  return (
    <AnalyticsView
      data={data}
      backHref="/history"
      backLabel="← History"
    />
  );
}
