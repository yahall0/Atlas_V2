"use client";

import { Button } from "@/components/ui/button";

interface AuditEntry {
  id: string;
  action: string;
  user_id: string;
  detail_json?: Record<string, unknown>;
  entry_hash: string;
  created_at: string;
}

interface Props {
  entries: AuditEntry[];
  onVerify?: () => void;
  onExport?: () => void;
  canVerify?: boolean;
  canExport?: boolean;
  chainStatus?: { valid: boolean; first_break_at?: number | null } | null;
}

const ACTION_COLORS: Record<string, string> = {
  REVIEW_STARTED: "bg-blue-400",
  REVIEW_COMPLETED: "bg-green-400",
  REVIEW_FLAGGED: "bg-red-400",
  RECOMMENDATION_ACCEPTED: "bg-green-500",
  RECOMMENDATION_MODIFIED: "bg-blue-500",
  RECOMMENDATION_DISMISSED: "bg-gray-400",
  VALIDATION_RUN: "bg-purple-400",
  EVIDENCE_ANALYSIS_RUN: "bg-teal-400",
  EXPORT_GENERATED: "bg-yellow-400",
  DOCUMENT_VIEWED: "bg-slate-300",
};

export default function AuditTimeline({
  entries, onVerify, onExport, canVerify, canExport, chainStatus,
}: Props) {
  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <h4 className="text-sm font-semibold">Audit Trail</h4>
        {chainStatus && (
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
            chainStatus.valid
              ? "bg-green-100 text-green-800"
              : "bg-red-100 text-red-800"
          }`}>
            {chainStatus.valid
              ? "Chain verified"
              : `Chain broken at entry ${chainStatus.first_break_at}`}
          </span>
        )}
        <div className="ml-auto flex gap-2">
          {canVerify && onVerify && (
            <Button size="sm" variant="outline" onClick={onVerify}>
              Verify Chain
            </Button>
          )}
          {canExport && onExport && (
            <Button size="sm" variant="outline" onClick={onExport}>
              Export CSV
            </Button>
          )}
        </div>
      </div>

      {/* Timeline */}
      {entries.length === 0 && (
        <p className="text-sm text-muted-foreground">No audit entries yet.</p>
      )}
      <div className="space-y-1 max-h-64 overflow-y-auto">
        {entries.map((entry) => (
          <div key={entry.id} className="flex items-start gap-2 text-xs py-1.5 border-b last:border-0">
            <span className={`w-2 h-2 rounded-full mt-1 shrink-0 ${
              ACTION_COLORS[entry.action] ?? "bg-gray-300"
            }`} />
            <div className="flex-1 min-w-0">
              <span className="font-medium">{entry.action.replace(/_/g, " ")}</span>
              <span className="text-muted-foreground"> by {entry.user_id}</span>
            </div>
            <span className="text-muted-foreground font-mono shrink-0">
              {entry.entry_hash?.slice(0, 8)}...
            </span>
            <span className="text-muted-foreground shrink-0">
              {entry.created_at ? new Date(entry.created_at).toLocaleTimeString() : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
