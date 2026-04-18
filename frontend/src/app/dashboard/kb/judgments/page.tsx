"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  RotateCcw,
  Loader2,
} from "lucide-react";
import {
  useKBJudgments,
  useReviewInsight,
  type Judgment,
  type JudgmentInsight,
} from "@/hooks/kb/useKB";

const STATUS_FILTERS = [
  { label: "All", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
  { label: "Needs Revision", value: "needs_revision" },
];

const REVIEW_STATUS_COLOURS: Record<string, string> = {
  approved: "bg-green-100 text-green-800",
  pending: "bg-yellow-100 text-yellow-800",
  rejected: "bg-red-100 text-red-800",
  needs_revision: "bg-amber-100 text-amber-800",
  draft: "bg-gray-100 text-gray-700",
};

function InsightReviewCard({ insight }: { insight: JudgmentInsight }) {
  const reviewMutation = useReviewInsight();
  const [rejectNotes, setRejectNotes] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  const handleApprove = () => {
    reviewMutation.mutate({
      insightId: insight.id,
      action: "approved",
    });
  };

  const handleReject = () => {
    if (!showRejectInput) {
      setShowRejectInput(true);
      return;
    }
    reviewMutation.mutate({
      insightId: insight.id,
      action: "rejected",
      review_notes: rejectNotes,
    });
    setShowRejectInput(false);
    setRejectNotes("");
  };

  const handleNeedsRevision = () => {
    if (!showRejectInput) {
      setShowRejectInput(true);
      return;
    }
    reviewMutation.mutate({
      insightId: insight.id,
      action: "needs_revision",
      review_notes: rejectNotes,
    });
    setShowRejectInput(false);
    setRejectNotes("");
  };

  const isPending = insight.approval_status === "pending";

  return (
    <div className="border rounded-lg p-3 bg-slate-50">
      <div className="flex items-start justify-between gap-2 mb-1">
        <h5 className="text-sm font-medium">{insight.title}</h5>
        <Badge
          className={
            REVIEW_STATUS_COLOURS[insight.approval_status] ??
            "bg-gray-100 text-gray-700"
          }
        >
          {insight.approval_status.replace(/_/g, " ")}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed mb-2">
        {insight.content}
      </p>

      {insight.review_notes && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mb-2">
          Review notes: {insight.review_notes}
        </p>
      )}

      {isPending && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="default"
              className="bg-green-600 hover:bg-green-700 text-white gap-1 h-7 text-xs"
              onClick={handleApprove}
              disabled={reviewMutation.isPending}
            >
              {reviewMutation.isPending ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Check className="w-3 h-3" />
              )}
              Approve
            </Button>
            <Button
              size="sm"
              variant="destructive"
              className="gap-1 h-7 text-xs"
              onClick={handleReject}
              disabled={reviewMutation.isPending}
            >
              {reviewMutation.isPending ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <X className="w-3 h-3" />
              )}
              Reject
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="gap-1 h-7 text-xs"
              onClick={handleNeedsRevision}
              disabled={reviewMutation.isPending}
            >
              <RotateCcw className="w-3 h-3" />
              Needs Revision
            </Button>
          </div>

          {showRejectInput && (
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Review notes (optional for reject/revision)..."
                value={rejectNotes}
                onChange={(e) => setRejectNotes(e.target.value)}
                className="flex-1 border rounded px-2 py-1 text-xs"
              />
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs"
                onClick={() => {
                  setShowRejectInput(false);
                  setRejectNotes("");
                }}
              >
                Cancel
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function JudgmentRow({ judgment }: { judgment: Judgment }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card>
      <CardContent className="p-0">
        {/* Summary row */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full text-left p-4 flex items-start gap-3 hover:bg-muted/30 transition-colors"
        >
          <div className="min-w-0 flex-1">
            <p className="font-medium text-sm truncate">
              {judgment.case_name}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {judgment.citation}
            </p>
          </div>
          <div className="hidden md:flex items-center gap-4 shrink-0 text-xs text-muted-foreground">
            <span className="w-24 truncate">{judgment.court}</span>
            <span className="w-20 text-right">
              {judgment.judgment_date
                ? new Date(judgment.judgment_date).toLocaleDateString()
                : "N/A"}
            </span>
            <span className="w-20 truncate">{judgment.binding_authority}</span>
            <span className="w-16 text-right">
              {judgment.insight_count} insights
            </span>
          </div>
          <Badge
            className={`shrink-0 ${
              REVIEW_STATUS_COLOURS[judgment.review_status] ??
              "bg-gray-100 text-gray-700"
            }`}
          >
            {judgment.review_status.replace(/_/g, " ")}
          </Badge>
          {expanded ? (
            <ChevronUp className="w-4 h-4 shrink-0 text-muted-foreground mt-0.5" />
          ) : (
            <ChevronDown className="w-4 h-4 shrink-0 text-muted-foreground mt-0.5" />
          )}
        </button>

        {/* Expanded details */}
        {expanded && (
          <div className="border-t px-4 py-4 bg-white">
            {/* Mobile metadata */}
            <div className="md:hidden grid grid-cols-2 gap-2 text-xs text-muted-foreground mb-4">
              <div>
                <span className="font-medium">Court:</span> {judgment.court}
              </div>
              <div>
                <span className="font-medium">Date:</span>{" "}
                {judgment.judgment_date
                  ? new Date(judgment.judgment_date).toLocaleDateString()
                  : "N/A"}
              </div>
              <div>
                <span className="font-medium">Authority:</span>{" "}
                {judgment.binding_authority}
              </div>
              <div>
                <span className="font-medium">Insights:</span>{" "}
                {judgment.insight_count}
              </div>
            </div>

            {/* Insights */}
            <h4 className="text-sm font-semibold mb-3">Insights</h4>
            {judgment.insights && judgment.insights.length > 0 ? (
              <div className="space-y-3">
                {judgment.insights.map((insight) => (
                  <InsightReviewCard key={insight.id} insight={insight} />
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No insights available for this judgment. Insights are extracted
                during processing.
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function JudgmentsPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const {
    data: judgments,
    isLoading,
    isError,
  } = useKBJudgments(statusFilter || undefined);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link href="/dashboard/kb">
          <Button variant="ghost" size="sm" className="gap-1">
            <ArrowLeft className="w-4 h-4" /> Back
          </Button>
        </Link>
        <h2 className="text-2xl font-bold">Judgments & Review Queue</h2>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2 mb-6 flex-wrap">
        <span className="text-sm text-muted-foreground mr-1">Status:</span>
        {STATUS_FILTERS.map((filter) => (
          <Button
            key={filter.value}
            size="sm"
            variant={statusFilter === filter.value ? "default" : "outline"}
            className={`h-7 text-xs ${
              statusFilter === filter.value
                ? "bg-blue-600 hover:bg-blue-700 text-white"
                : ""
            }`}
            onClick={() => setStatusFilter(filter.value)}
          >
            {filter.label}
          </Button>
        ))}
      </div>

      {/* Table header (desktop) */}
      <div className="hidden md:flex items-center gap-3 px-4 py-2 text-xs font-medium text-muted-foreground border-b mb-2">
        <span className="flex-1">Case</span>
        <span className="w-24">Court</span>
        <span className="w-20 text-right">Date</span>
        <span className="w-20">Authority</span>
        <span className="w-16 text-right">Insights</span>
        <span className="w-20 text-right">Status</span>
        <span className="w-4" />
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* Error */}
      {isError && (
        <p className="text-red-600 py-4">Failed to load judgments.</p>
      )}

      {/* Judgment list */}
      {judgments && (
        <div className="space-y-2">
          {judgments.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center">
              No judgments found
              {statusFilter ? ` with status "${statusFilter.replace(/_/g, " ")}"` : ""}.
            </p>
          ) : (
            judgments.map((judgment) => (
              <JudgmentRow key={judgment.id} judgment={judgment} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
