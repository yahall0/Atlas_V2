"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api";
import {
  FileText,
  Clock,
  MapPin,
  BarChart2,
  CalendarCheck,
  Cpu,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";

interface Stats {
  total_firs: number;
  districts: number;
  pending_review: number;
  completeness_avg: number;
  ingested_today: number;
}

interface ModelInfo {
  status: string;
  best_f1?: number;
  model_version?: string;
}

const METRIC_ICONS = [FileText, Clock, MapPin, BarChart2, CalendarCheck];
const METRIC_COLORS = [
  "bg-blue-50 text-blue-600",
  "bg-amber-50 text-amber-600",
  "bg-emerald-50 text-emerald-600",
  "bg-violet-50 text-violet-600",
  "bg-sky-50 text-sky-600",
];

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient("/api/v1/dashboard/stats")
      .then(setStats)
      .catch(() => setError(true));
    apiClient("/api/v1/predict/model-info")
      .then((data: ModelInfo) => setModelInfo(data))
      .catch(() => {/* non-critical */});
  }, []);

  const metrics = [
    { title: "Total FIRs", value: stats?.total_firs ?? "—", sub: "all time" },
    { title: "Pending Review", value: stats?.pending_review ?? "—", sub: "awaiting IO" },
    { title: "Districts", value: stats?.districts ?? "—", sub: "covered" },
    { title: "Avg Completeness", value: stats ? `${stats.completeness_avg}%` : "—", sub: "extraction score" },
    { title: "Ingested Today", value: stats?.ingested_today ?? "—", sub: "PDFs processed" },
  ];

  const modelF1Value =
    modelInfo?.best_f1 != null
      ? modelInfo.best_f1.toFixed(3)
      : modelInfo?.status === "heuristic"
      ? "heuristic"
      : "—";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-800">Overview</h2>
        <p className="text-sm text-slate-500 mt-0.5">Real-time FIR pipeline metrics</p>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2.5">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          Could not load statistics. Please refresh the page.
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {metrics.map((m, i) => {
          const Icon = METRIC_ICONS[i];
          return (
            <Card key={m.title} className="border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-3 ${METRIC_COLORS[i]}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <p className="text-2xl font-bold text-slate-800">{m.value}</p>
                <p className="text-xs font-medium text-slate-600 mt-0.5">{m.title}</p>
                <p className="text-[10px] text-slate-400">{m.sub}</p>
              </CardContent>
            </Card>
          );
        })}

        {/* Model card */}
        <Card className="border-slate-200 shadow-sm hover:shadow-md transition-shadow">
          <CardContent className="p-4">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-3 bg-indigo-50 text-indigo-600">
              <Cpu className="w-4 h-4" />
            </div>
            <p className="text-2xl font-bold text-slate-800">{modelF1Value}</p>
            <p className="text-xs font-medium text-slate-600 mt-0.5">Model F1</p>
            <p className="text-[10px] text-slate-400 truncate" title={modelInfo?.model_version ?? ""}>
              {modelInfo?.model_version ?? "macro-averaged"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Mismatch callout */}
      <Card className="border-amber-200 bg-amber-50 shadow-sm">
        <CardContent className="p-4 flex items-start gap-3">
          <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center shrink-0">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-amber-800">Section Mismatch Detection Active</p>
            <p className="text-xs text-amber-700 mt-0.5">
              FIRs where the NLP narrative analysis contradicts the registered sections are automatically flagged as <strong>review_needed</strong>. Check the FIR Review tab to inspect flagged records.
            </p>
          </div>
          <div className="ml-auto shrink-0">
            <div className="flex items-center gap-1 text-emerald-700 bg-emerald-100 rounded-full px-2.5 py-1">
              <TrendingUp className="w-3 h-3" />
              <span className="text-[10px] font-semibold">Live</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

