"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api";

interface Stats {
  total_firs: number;
  districts: number;
  pending_review: number;
  completeness_avg: number;
  ingested_today: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient("/api/v1/dashboard/stats")
      .then(setStats)
      .catch(() => setError(true));
  }, []);

  const metrics = [
    { title: "Total FIRs", value: stats?.total_firs ?? "—" },
    { title: "Pending Review", value: stats?.pending_review ?? "—" },
    { title: "Districts", value: stats?.districts ?? "—" },
    {
      title: "Completeness Avg",
      value: stats ? `${stats.completeness_avg}%` : "—",
    },
    { title: "Ingested Today", value: stats?.ingested_today ?? "—" },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
      {error && (
        <p className="text-destructive text-sm mb-4">
          Could not load statistics. Please try refreshing.
        </p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        {metrics.map((m) => (
          <Card key={m.title}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {m.title}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{m.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="text-muted-foreground">
        NLP classification pipeline active — Sprint 2
      </p>
    </div>
  );
}

