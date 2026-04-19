"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Scale,
  GitBranch,
  Gavel,
  Clock,
  Tag,
  ChevronRight,
  Plus,
  BookOpen,
} from "lucide-react";
import {
  useKBStats,
  useKBOffences,
  useKBJudgments,
  useCurrentUser,
  type KBOffence,
  type Judgment,
} from "@/hooks/kb/useKB";

const REVIEW_STATUS_COLOURS: Record<string, string> = {
  approved: "bg-green-100 text-green-800",
  pending: "bg-yellow-100 text-yellow-800",
  rejected: "bg-red-100 text-red-800",
  needs_revision: "bg-amber-100 text-amber-800",
  draft: "bg-gray-100 text-gray-700",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge
      className={
        REVIEW_STATUS_COLOURS[status] ?? "bg-gray-100 text-gray-700"
      }
    >
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

function StatsSection() {
  const { data: stats, isLoading, isError } = useKBStats();

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        {Array.from({ length: 5 }).map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-4">
              <div className="h-4 bg-gray-200 rounded w-20 mb-2" />
              <div className="h-8 bg-gray-200 rounded w-12" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <Card className="mb-8">
        <CardContent className="p-4 text-red-600">
          Failed to load KB statistics.
        </CardContent>
      </Card>
    );
  }

  const statItems = [
    { label: "Offences", value: stats.total_offences, icon: Scale },
    { label: "Nodes", value: stats.total_nodes, icon: GitBranch },
    { label: "Judgments", value: stats.total_judgments, icon: Gavel },
    { label: "Pending Review", value: stats.pending_insights, icon: Clock },
    { label: "Version", value: stats.current_version, icon: Tag },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
      {statItems.map((item) => {
        const Icon = item.icon;
        return (
          <Card key={item.label}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </div>
              <p className="text-2xl font-bold">{item.value}</p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function OffencesTab() {
  const { data: offences, isLoading, isError } = useKBOffences();

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <p className="text-red-600 py-4">Failed to load offences.</p>
    );
  }

  if (!offences || offences.length === 0) {
    return (
      <p className="text-muted-foreground py-8 text-center">
        No offences found in the knowledge base.
      </p>
    );
  }

  // Group by category_id
  const grouped = offences.reduce<Record<string, KBOffence[]>>(
    (acc, offence) => {
      const cat = offence.category_id || "uncategorized";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(offence);
      return acc;
    },
    {}
  );

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([categoryId, categoryOffences]) => (
        <div key={categoryId}>
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            {categoryId}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {categoryOffences.map((offence) => (
              <Link
                key={offence.id}
                href={`/dashboard/kb/offences/${offence.id}`}
              >
                <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span className="text-xs font-mono bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded">
                        {offence.offence_code}
                      </span>
                      <StatusBadge status={offence.review_status} />
                    </div>
                    <p className="font-medium text-sm mb-1 line-clamp-2">
                      {offence.display_name_en}
                    </p>
                    <div className="flex items-center justify-between text-xs text-muted-foreground mt-2">
                      <span>BNS {offence.bns_section}</span>
                      <span>{offence.node_count} nodes</span>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function JudgmentsTab() {
  const { data: judgments, isLoading, isError } = useKBJudgments();

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <p className="text-red-600 py-4">Failed to load judgments.</p>
    );
  }

  if (!judgments || judgments.length === 0) {
    return (
      <p className="text-muted-foreground py-8 text-center">
        No judgments found.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {judgments.slice(0, 20).map((judgment: Judgment) => (
        <Card key={judgment.id}>
          <CardContent className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-sm truncate">
                  {judgment.case_name}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {judgment.citation} &middot; {judgment.court}
                </p>
                <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                  <span>
                    {judgment.judgment_date
                      ? new Date(judgment.judgment_date).toLocaleDateString()
                      : "N/A"}
                  </span>
                  <span>&middot;</span>
                  <span>{judgment.binding_authority}</span>
                  <span>&middot;</span>
                  <span>{judgment.insight_count} insights</span>
                </div>
              </div>
              <StatusBadge status={judgment.review_status} />
            </div>
          </CardContent>
        </Card>
      ))}
      <div className="flex justify-center pt-2">
        <Link href="/dashboard/kb/judgments">
          <Button variant="outline" size="sm" className="gap-1">
            View All Judgments
            <ChevronRight className="w-3.5 h-3.5" />
          </Button>
        </Link>
      </div>
    </div>
  );
}

export default function KBDashboardPage() {
  const [activeTab, setActiveTab] = useState<"offences" | "judgments">(
    "offences"
  );
  const { data: stats } = useKBStats();
  const { data: currentUser } = useCurrentUser();
  const isAdmin = currentUser?.role === "ADMIN" || currentUser?.role === "SP";

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-2xl font-bold">Knowledge Base</h2>
          {isAdmin && (
            <Link href="/dashboard/kb/offences/new">
              <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white gap-1">
                <Plus className="w-4 h-4" /> New Offence
              </Button>
            </Link>
          )}
          <Link href="/dashboard/kb/scenarios">
            <Button
              size="sm"
              variant="outline"
              className="gap-1 border-indigo-300 text-indigo-700 hover:bg-indigo-50"
            >
              <BookOpen className="w-4 h-4" />
              IO Scenarios (Compendium)
            </Button>
          </Link>
        </div>
        {stats && stats.pending_insights > 0 && (
          <Link href="/dashboard/kb/judgments">
            <Badge className="bg-amber-100 text-amber-800 cursor-pointer gap-1">
              <Clock className="w-3 h-3" />
              {stats.pending_insights} Pending Review
            </Badge>
          </Link>
        )}
      </div>

      <StatsSection />

      {/* Tab selector */}
      <div className="flex gap-1 border-b mb-6">
        <button
          onClick={() => setActiveTab("offences")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "offences"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Offences
        </button>
        <button
          onClick={() => setActiveTab("judgments")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "judgments"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Judgments
        </button>
      </div>

      {activeTab === "offences" ? <OffencesTab /> : <JudgmentsTab />}
    </div>
  );
}
