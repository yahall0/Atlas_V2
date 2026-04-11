"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Recommendation {
  id: string;
  severity: string;
  section?: string;
  category?: string;
  description: string;
  recommendation: string;
  rule_id?: string;
  tier?: string;
  legal_basis?: string;
}

interface Props {
  rec: Recommendation;
  type: "legal_validation" | "evidence_gap";
  isActioned: boolean;
  actionTaken?: string;
  onAccept: (id: string) => void;
  onModify: (id: string, text: string) => void;
  onDismiss: (id: string, reason: string) => void;
}

const SEVERITY_STYLES: Record<string, string> = {
  CRITICAL: "bg-red-50 border-red-200",
  critical: "bg-red-50 border-red-200",
  ERROR: "bg-orange-50 border-orange-200",
  important: "bg-orange-50 border-orange-200",
  WARNING: "bg-yellow-50 border-yellow-200",
  suggested: "bg-blue-50 border-blue-200",
};

const SEVERITY_BADGE: Record<string, string> = {
  CRITICAL: "bg-red-100 text-red-800",
  critical: "bg-red-100 text-red-800",
  ERROR: "bg-orange-100 text-orange-800",
  important: "bg-orange-100 text-orange-800",
  WARNING: "bg-yellow-100 text-yellow-800",
  suggested: "bg-blue-100 text-blue-800",
};

export default function RecommendationCard({
  rec, isActioned, actionTaken, onAccept, onModify, onDismiss,
}: Props) {
  const [mode, setMode] = useState<"view" | "modify" | "dismiss">("view");
  const [modifyText, setModifyText] = useState("");
  const [dismissReason, setDismissReason] = useState("");

  const style = SEVERITY_STYLES[rec.severity] ?? "bg-gray-50 border-gray-200";
  const badgeStyle = SEVERITY_BADGE[rec.severity] ?? "bg-gray-100 text-gray-800";

  return (
    <Card
      className={`border transition-all ${style} ${
        isActioned ? "opacity-60" : ""
      }`}
    >
      <CardContent className="p-4 text-sm space-y-2">
        {/* Header */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${badgeStyle}`}>
            {rec.severity}
          </span>
          {rec.rule_id && (
            <span className="text-xs font-mono text-muted-foreground">{rec.rule_id}</span>
          )}
          {rec.section && <Badge variant="outline" className="text-xs">{rec.section}</Badge>}
          {rec.category && (
            <Badge variant="outline" className="text-xs">
              {rec.category.replace(/_/g, " ")}
            </Badge>
          )}
          {rec.tier && (
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              rec.tier === "rule_based"
                ? "bg-slate-200 text-slate-700"
                : "border border-dashed border-blue-400 text-blue-700"
            }`}>
              {rec.tier === "rule_based" ? "Rule-based" : "AI-suggested"}
            </span>
          )}
          {isActioned && actionTaken && (
            <span className={`ml-auto text-xs px-2 py-0.5 rounded font-medium ${
              actionTaken === "accepted" ? "bg-green-100 text-green-800"
                : actionTaken === "modified" ? "bg-blue-100 text-blue-800"
                : "bg-gray-200 text-gray-600"
            }`}>
              {actionTaken}
            </span>
          )}
        </div>

        {/* Description */}
        <p>{rec.description}</p>
        <p className="text-xs text-muted-foreground">{rec.recommendation}</p>
        {rec.legal_basis && (
          <p className="text-xs text-muted-foreground italic">{rec.legal_basis}</p>
        )}

        {/* Action buttons */}
        {!isActioned && mode === "view" && (
          <div className="flex gap-2 pt-1">
            <Button size="sm" variant="outline"
              className="text-green-700 border-green-300 hover:bg-green-50"
              onClick={() => onAccept(rec.id)}>
              Accept
            </Button>
            <Button size="sm" variant="outline"
              className="text-blue-700 border-blue-300 hover:bg-blue-50"
              onClick={() => setMode("modify")}>
              Modify
            </Button>
            <Button size="sm" variant="outline"
              className="text-gray-600 border-gray-300 hover:bg-gray-50"
              onClick={() => setMode("dismiss")}>
              Dismiss
            </Button>
          </div>
        )}

        {/* Modify input */}
        {!isActioned && mode === "modify" && (
          <div className="space-y-2 pt-1">
            <textarea
              className="w-full border rounded px-3 py-2 text-sm"
              rows={2}
              placeholder="Enter modified recommendation..."
              value={modifyText}
              onChange={(e) => setModifyText(e.target.value)}
            />
            <div className="flex gap-2">
              <Button size="sm" disabled={!modifyText.trim()}
                onClick={() => { onModify(rec.id, modifyText); setMode("view"); }}>
                Save
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setMode("view")}>Cancel</Button>
            </div>
          </div>
        )}

        {/* Dismiss input */}
        {!isActioned && mode === "dismiss" && (
          <div className="space-y-2 pt-1">
            <textarea
              className="w-full border rounded px-3 py-2 text-sm"
              rows={2}
              placeholder="Reason for dismissal (required)..."
              value={dismissReason}
              onChange={(e) => setDismissReason(e.target.value)}
            />
            <div className="flex gap-2">
              <Button size="sm" variant="destructive" disabled={!dismissReason.trim()}
                onClick={() => { onDismiss(rec.id, dismissReason); setMode("view"); }}>
                Confirm Dismiss
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setMode("view")}>Cancel</Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
