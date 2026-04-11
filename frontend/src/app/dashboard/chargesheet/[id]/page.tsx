"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";
import RecommendationCard from "@/components/RecommendationCard";
import AuditTimeline from "@/components/AuditTimeline";
import CoverageMeter from "@/components/CoverageMeter";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ──────────────────────────────────────────────────────────────────

interface ChargeSheet {
  id: string;
  fir_id?: string;
  filing_date?: string;
  court_name?: string;
  accused_json?: { name?: string; age?: number; address?: string; role?: string }[];
  charges_json?: { section?: string; act?: string; description?: string }[];
  evidence_json?: { type?: string; description?: string; status?: string }[];
  witnesses_json?: { name?: string; role?: string; statement_summary?: string }[];
  io_name?: string;
  status?: string;
  district?: string;
  police_station?: string;
}

interface ValidationFinding {
  rule_id: string;
  severity: string;
  section: string;
  description: string;
  recommendation: string;
  confidence: number;
}

interface EvidenceGap {
  category: string;
  tier: string;
  severity: string;
  recommendation: string;
  legal_basis?: string;
  confidence: number;
}

interface EvidencePresent {
  category: string;
  source_text: string;
  confidence: number;
}

interface AuditEntry {
  id: string;
  action: string;
  user_id: string;
  detail_json?: Record<string, unknown>;
  entry_hash: string;
  created_at: string;
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function ChargesheetReviewPage() {
  const params = useParams();
  const csId = params.id as string;

  // Data
  const [cs, setCs] = useState<ChargeSheet | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Recommendations
  const [validationFindings, setValidationFindings] = useState<ValidationFinding[]>([]);
  const [evidenceGaps, setEvidenceGaps] = useState<EvidenceGap[]>([]);
  const [evidencePresent, setEvidencePresent] = useState<EvidencePresent[]>([]);
  const [coveragePct, setCoveragePct] = useState(100);
  const [totalExpected, setTotalExpected] = useState(0);
  const [totalPresent, setTotalPresent] = useState(0);

  // Actions taken
  const [actions, setActions] = useState<Map<string, string>>(new Map());
  const [rightTab, setRightTab] = useState<"legal" | "evidence" | "summary">("legal");

  // Audit
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [chainStatus, setChainStatus] = useState<{ valid: boolean; first_break_at?: number | null } | null>(null);
  const [showAudit, setShowAudit] = useState(false);

  // Review
  const [reviewStarted, setReviewStarted] = useState(false);
  const [assessmentNotes, setAssessmentNotes] = useState("");
  const [flagForSenior, setFlagForSenior] = useState(false);

  // Collapsible sections
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggleCollapse = (key: string) =>
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

  // ── Load data ──────────────────────────────────────────────────────────

  const loadChargesheet = useCallback(async () => {
    try {
      const data = await apiClient(`/api/v1/chargesheet/${csId}`);
      setCs(data);
    } catch {
      setError("Failed to load chargesheet.");
    } finally {
      setLoading(false);
    }
  }, [csId]);

  const loadAudit = useCallback(async () => {
    try {
      const data = await apiClient(`/api/v1/review/chargesheet/${csId}/audit`);
      setAuditEntries(data.entries || []);
    } catch {
      // DySP+ only
    }
  }, [csId]);

  useEffect(() => {
    loadChargesheet();
    loadAudit();
  }, [loadChargesheet, loadAudit]);

  // ── Review flow ────────────────────────────────────────────────────────

  async function startReview() {
    try {
      const data = await apiClient(`/api/v1/review/chargesheet/${csId}/start`, {
        method: "POST",
      });
      setReviewStarted(true);

      // Load existing actions
      const existingActions = data.existing_actions || [];
      const map = new Map<string, string>();
      for (const a of existingActions) {
        map.set(a.recommendation_id, a.action_taken);
      }
      setActions(map);

      // Run validation
      try {
        const vr = await apiClient(`/api/v1/validate/chargesheet/${csId}`, { method: "POST" });
        setValidationFindings(vr.findings || []);
      } catch { /* validation may not be available */ }

      // Run evidence analysis
      try {
        const er = await apiClient(`/api/v1/evidence/analyze/${csId}`, { method: "POST" });
        setEvidenceGaps(er.evidence_gaps || []);
        setEvidencePresent(er.evidence_present || []);
        setCoveragePct(er.evidence_coverage_pct ?? 100);
        setTotalExpected(er.total_expected ?? 0);
        setTotalPresent(er.total_present ?? 0);
      } catch { /* evidence analysis may not be available */ }

      loadAudit();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start review.");
    }
  }

  async function actOnRecommendation(
    recId: string,
    recType: "legal_validation" | "evidence_gap",
    action: "accepted" | "modified" | "dismissed",
    modifiedText?: string,
    reason?: string,
    sourceRule?: string,
  ) {
    try {
      await apiClient(`/api/v1/review/chargesheet/${csId}/recommendation`, {
        method: "POST",
        body: JSON.stringify({
          recommendation_id: recId,
          recommendation_type: recType,
          action,
          modified_text: modifiedText,
          reason,
          source_rule: sourceRule,
        }),
      });
      setActions((prev) => new Map(prev).set(recId, action));
      loadAudit();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    }
  }

  async function completeReview() {
    try {
      await apiClient(`/api/v1/review/chargesheet/${csId}/complete`, {
        method: "POST",
        body: JSON.stringify({
          overall_assessment: assessmentNotes,
          flag_for_senior: flagForSenior,
        }),
      });
      loadChargesheet();
      loadAudit();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Complete failed.");
    }
  }

  async function verifyChain() {
    try {
      const data = await apiClient(`/api/v1/review/chargesheet/${csId}/audit/verify`);
      setChainStatus(data);
    } catch {
      setError("Chain verification failed (requires SP role).");
    }
  }

  async function exportAudit() {
    try {
      const token = localStorage.getItem("atlas_token");
      const res = await fetch(`${BASE_URL}/api/v1/review/chargesheet/${csId}/audit/export`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit_${csId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Export failed (requires DySP role).");
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!cs) {
    return <p className="text-red-600 p-4">Chargesheet not found.</p>;
  }

  // Compute summary
  const totalRecs = validationFindings.length + evidenceGaps.length;
  const actionValues = Array.from(actions.values());
  const accepted = actionValues.filter((v) => v === "accepted").length;
  const modified = actionValues.filter((v) => v === "modified").length;
  const dismissed = actionValues.filter((v) => v === "dismissed").length;

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-white shrink-0">
        <div>
          <h2 className="text-lg font-bold">Chargesheet Review</h2>
          <p className="text-sm text-muted-foreground">
            {cs.court_name ?? "Unknown Court"} &middot; {cs.district ?? ""} &middot; {cs.police_station ?? ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={
            cs.status === "reviewed" ? "bg-green-100 text-green-800"
              : cs.status === "flagged" ? "bg-red-100 text-red-800"
              : cs.status === "under_review" ? "bg-yellow-100 text-yellow-800"
              : "bg-blue-100 text-blue-800"
          }>
            {cs.status ?? "parsed"}
          </Badge>
          {!reviewStarted && cs.status !== "reviewed" && cs.status !== "flagged" && (
            <Button onClick={startReview} className="bg-blue-600 hover:bg-blue-700 text-white">
              Start Review
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-800">
          {error}
          <button className="ml-2 underline" onClick={() => setError("")}>dismiss</button>
        </div>
      )}

      {/* Three-panel layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT PANEL — Document Viewer */}
        <div className="w-2/5 border-r overflow-y-auto p-4 space-y-3">
          {/* Metadata */}
          <Card>
            <CardHeader className="pb-2 cursor-pointer" onClick={() => toggleCollapse("meta")}>
              <CardTitle className="text-sm">Case Details</CardTitle>
            </CardHeader>
            {!collapsed.meta && (
              <CardContent className="text-sm space-y-1">
                {cs.io_name && <p><span className="font-medium">IO:</span> {cs.io_name}</p>}
                {cs.court_name && <p><span className="font-medium">Court:</span> {cs.court_name}</p>}
                {cs.filing_date && <p><span className="font-medium">Filing:</span> {cs.filing_date}</p>}
                {cs.fir_id && <p><span className="font-medium">FIR Linked:</span> Yes</p>}
              </CardContent>
            )}
          </Card>

          {/* Accused */}
          <Card>
            <CardHeader className="pb-2 cursor-pointer" onClick={() => toggleCollapse("accused")}>
              <CardTitle className="text-sm">
                Accused ({cs.accused_json?.length ?? 0})
              </CardTitle>
            </CardHeader>
            {!collapsed.accused && (
              <CardContent>
                <table className="w-full text-xs">
                  <thead><tr className="text-muted-foreground border-b">
                    <th className="text-left pb-1">Name</th><th className="text-left pb-1">Age</th><th className="text-left pb-1">Role</th>
                  </tr></thead>
                  <tbody>
                    {(cs.accused_json ?? []).map((a, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="py-1">{a.name ?? "--"}</td>
                        <td className="py-1">{a.age ?? "--"}</td>
                        <td className="py-1">{a.role ?? "--"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            )}
          </Card>

          {/* Charges */}
          <Card>
            <CardHeader className="pb-2 cursor-pointer" onClick={() => toggleCollapse("charges")}>
              <CardTitle className="text-sm">
                Charges ({cs.charges_json?.length ?? 0})
              </CardTitle>
            </CardHeader>
            {!collapsed.charges && (
              <CardContent className="space-y-1">
                {(cs.charges_json ?? []).map((c, i) => (
                  <div key={i} className="text-xs flex items-center gap-1">
                    <Badge variant="outline" className="text-xs shrink-0">
                      {c.section} {c.act}
                    </Badge>
                    {c.description && <span className="text-muted-foreground truncate">{c.description}</span>}
                  </div>
                ))}
              </CardContent>
            )}
          </Card>

          {/* Evidence */}
          <Card>
            <CardHeader className="pb-2 cursor-pointer" onClick={() => toggleCollapse("evidence")}>
              <CardTitle className="text-sm">
                Evidence ({cs.evidence_json?.length ?? 0})
              </CardTitle>
            </CardHeader>
            {!collapsed.evidence && (
              <CardContent>
                <table className="w-full text-xs">
                  <thead><tr className="text-muted-foreground border-b">
                    <th className="text-left pb-1">Type</th><th className="text-left pb-1">Description</th><th className="text-left pb-1">Status</th>
                  </tr></thead>
                  <tbody>
                    {(cs.evidence_json ?? []).map((e, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="py-1 font-medium">{e.type ?? "--"}</td>
                        <td className="py-1">{e.description ?? "--"}</td>
                        <td className="py-1">
                          <span className={`px-1 py-0.5 rounded text-[10px] ${
                            e.status === "collected" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                          }`}>{e.status ?? "pending"}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            )}
          </Card>

          {/* Witnesses */}
          <Card>
            <CardHeader className="pb-2 cursor-pointer" onClick={() => toggleCollapse("witnesses")}>
              <CardTitle className="text-sm">
                Witnesses ({cs.witnesses_json?.length ?? 0})
              </CardTitle>
            </CardHeader>
            {!collapsed.witnesses && (
              <CardContent>
                {(cs.witnesses_json ?? []).map((w, i) => (
                  <div key={i} className="text-xs py-1 border-b last:border-0">
                    <span className="font-medium">{w.name ?? "Unknown"}</span>
                    {w.role && <Badge variant="secondary" className="text-[10px] ml-1">{w.role}</Badge>}
                    {w.statement_summary && (
                      <p className="text-muted-foreground mt-0.5">{w.statement_summary}</p>
                    )}
                  </div>
                ))}
              </CardContent>
            )}
          </Card>
        </div>

        {/* RIGHT PANEL — AI Recommendations */}
        <div className="w-3/5 overflow-y-auto p-4 space-y-3">
          {!reviewStarted && (
            <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
              Click &quot;Start Review&quot; to load AI recommendations.
            </div>
          )}

          {reviewStarted && (
            <>
              {/* Tabs */}
              <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
                {(["legal", "evidence", "summary"] as const).map((tab) => (
                  <button key={tab} onClick={() => setRightTab(tab)}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-all ${
                      rightTab === tab ? "bg-white shadow-sm text-slate-800" : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {tab === "legal" ? `Legal (${validationFindings.length})`
                      : tab === "evidence" ? `Evidence (${evidenceGaps.length})`
                      : "Summary"}
                  </button>
                ))}
              </div>

              {/* Legal Validation tab */}
              {rightTab === "legal" && (
                <div className="space-y-2">
                  {validationFindings.length === 0 && (
                    <p className="text-sm text-muted-foreground py-4 text-center">No legal validation findings.</p>
                  )}
                  {validationFindings.map((f, i) => {
                    const recId = `legal_${f.rule_id}_${f.section}_${i}`;
                    return (
                      <RecommendationCard
                        key={recId}
                        rec={{
                          id: recId,
                          severity: f.severity,
                          section: f.section,
                          description: f.description,
                          recommendation: f.recommendation,
                          rule_id: f.rule_id,
                        }}
                        type="legal_validation"
                        isActioned={actions.has(recId)}
                        actionTaken={actions.get(recId)}
                        onAccept={(id) => actOnRecommendation(id, "legal_validation", "accepted", undefined, undefined, f.rule_id)}
                        onModify={(id, text) => actOnRecommendation(id, "legal_validation", "modified", text, undefined, f.rule_id)}
                        onDismiss={(id, reason) => actOnRecommendation(id, "legal_validation", "dismissed", undefined, reason, f.rule_id)}
                      />
                    );
                  })}
                </div>
              )}

              {/* Evidence Gaps tab */}
              {rightTab === "evidence" && (
                <div className="space-y-3">
                  <CoverageMeter
                    percentage={coveragePct}
                    totalExpected={totalExpected}
                    totalPresent={totalPresent}
                    totalGaps={evidenceGaps.length}
                  />
                  {evidenceGaps.map((g, i) => {
                    const recId = `evidence_${g.category}_${g.tier}_${i}`;
                    return (
                      <RecommendationCard
                        key={recId}
                        rec={{
                          id: recId,
                          severity: g.severity,
                          category: g.category,
                          description: g.recommendation,
                          recommendation: g.legal_basis ?? "",
                          tier: g.tier,
                          legal_basis: g.legal_basis,
                        }}
                        type="evidence_gap"
                        isActioned={actions.has(recId)}
                        actionTaken={actions.get(recId)}
                        onAccept={(id) => actOnRecommendation(id, "evidence_gap", "accepted", undefined, undefined, g.tier)}
                        onModify={(id, text) => actOnRecommendation(id, "evidence_gap", "modified", text, undefined, g.tier)}
                        onDismiss={(id, reason) => actOnRecommendation(id, "evidence_gap", "dismissed", undefined, reason, g.tier)}
                      />
                    );
                  })}

                  {/* Present evidence */}
                  {evidencePresent.length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Present Evidence ({evidencePresent.length})</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-1">
                        {evidencePresent.map((ep, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="text-green-600">&#10003;</span>
                            <span className="font-medium">{ep.category.replace(/_/g, " ")}</span>
                            <span className="text-muted-foreground truncate">{ep.source_text}</span>
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}

              {/* Summary tab */}
              {rightTab === "summary" && (
                <div className="space-y-4">
                  {/* Action counts */}
                  <div className="grid grid-cols-4 gap-3">
                    <Card><CardContent className="p-3 text-center">
                      <p className="text-2xl font-bold">{totalRecs}</p>
                      <p className="text-xs text-muted-foreground">Total</p>
                    </CardContent></Card>
                    <Card><CardContent className="p-3 text-center">
                      <p className="text-2xl font-bold text-green-600">{accepted}</p>
                      <p className="text-xs text-muted-foreground">Accepted</p>
                    </CardContent></Card>
                    <Card><CardContent className="p-3 text-center">
                      <p className="text-2xl font-bold text-blue-600">{modified}</p>
                      <p className="text-xs text-muted-foreground">Modified</p>
                    </CardContent></Card>
                    <Card><CardContent className="p-3 text-center">
                      <p className="text-2xl font-bold text-gray-500">{dismissed}</p>
                      <p className="text-xs text-muted-foreground">Dismissed</p>
                    </CardContent></Card>
                  </div>

                  {/* Assessment */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Overall Assessment</label>
                    <textarea
                      className="w-full border rounded px-3 py-2 text-sm"
                      rows={3}
                      value={assessmentNotes}
                      onChange={(e) => setAssessmentNotes(e.target.value)}
                      placeholder="Notes on the overall review..."
                    />
                  </div>

                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={flagForSenior}
                      onChange={(e) => setFlagForSenior(e.target.checked)} />
                    Flag for senior review
                  </label>

                  <Button
                    className="w-full bg-green-600 hover:bg-green-700 text-white"
                    onClick={completeReview}
                    disabled={cs.status === "reviewed" || cs.status === "flagged"}
                  >
                    Complete Review
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* BOTTOM PANEL — Audit Trail */}
      <div className="border-t bg-white shrink-0">
        <button
          className="w-full px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-slate-50 text-left"
          onClick={() => setShowAudit(!showAudit)}
        >
          {showAudit ? "Hide" : "Show"} Audit Trail ({auditEntries.length} entries)
        </button>
        {showAudit && (
          <div className="px-4 pb-3 max-h-52 overflow-y-auto">
            <AuditTimeline
              entries={auditEntries}
              onVerify={verifyChain}
              onExport={exportAudit}
              canVerify={true}
              canExport={true}
              chainStatus={chainStatus}
            />
          </div>
        )}
      </div>
    </div>
  );
}
