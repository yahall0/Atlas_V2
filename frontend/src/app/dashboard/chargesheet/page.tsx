"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

// ─── Types ──────────────────────────────────────────────────────────────────

interface Accused {
  name?: string;
  age?: number;
  address?: string;
  role?: string;
}

interface Charge {
  section?: string;
  act?: string;
  description?: string;
}

interface Evidence {
  type?: string;
  description?: string;
  status?: string;
}

interface Witness {
  name?: string;
  role?: string;
  statement_summary?: string;
}

interface ChargeSheet {
  id?: string;
  fir_id?: string;
  filing_date?: string;
  court_name?: string;
  accused_json?: Accused[];
  charges_json?: Charge[];
  evidence_json?: Evidence[];
  witnesses_json?: Witness[];
  io_name?: string;
  raw_text?: string;
  parsed_json?: Record<string, unknown>;
  status?: string;
  reviewer_notes?: string;
  uploaded_by?: string;
  district?: string;
  police_station?: string;
  created_at?: string;
}

interface ValidationFinding {
  rule_id: string;
  severity: "CRITICAL" | "ERROR" | "WARNING";
  section: string;
  description: string;
  recommendation: string;
  confidence: number;
  // NLP filter annotations (added by legal_nlp_filter post-processor)
  is_likely_routine?: boolean;
  routine_score?: number;
  merged_count?: number;
}

interface ValidationSummary {
  total_findings: number;
  critical: number;
  errors: number;
  warnings: number;
  sections_validated: number;
  evidence_coverage_pct: number;
}

interface ValidationReport {
  id?: string;
  chargesheet_id: string;
  fir_id?: string | null;
  overall_status: string;
  findings: ValidationFinding[];
  filtered_findings?: ValidationFinding[];
  suppressed_duplicate_count?: number;
  narrative_summary?: string;
  summary: ValidationSummary;
}

interface SectionLookup {
  section: string;
  act: string;
  title: string;
  category?: string;
  cognizable?: boolean;
  bailable?: boolean;
  max_sentence?: string;
  mandatory_evidence?: string[];
  companion_sections?: string[];
  equivalent?: { bns_section?: string; ipc_section?: string };
}

interface EvidenceGap {
  category: string;
  tier: "rule_based" | "ml_pattern";
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

interface EvidenceGapReport {
  id?: string;
  crime_category: string;
  evidence_present: EvidencePresent[];
  evidence_gaps: EvidenceGap[];
  evidence_coverage_pct: number;
  total_expected: number;
  total_present: number;
  total_gaps: number;
  narrative_summary?: string;
}

const STATUS_COLOURS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  parsed: "bg-blue-100 text-blue-800",
  reviewed: "bg-green-100 text-green-800",
  flagged: "bg-red-100 text-red-800",
};

const SEVERITY_STYLES: Record<string, { bg: string; icon: string }> = {
  CRITICAL: { bg: "bg-red-50 border-red-200 text-red-800", icon: "text-red-600" },
  ERROR: { bg: "bg-orange-50 border-orange-200 text-orange-800", icon: "text-orange-600" },
  WARNING: { bg: "bg-yellow-50 border-yellow-200 text-yellow-800", icon: "text-yellow-600" },
};

const SEVERITY_ICON: Record<string, string> = {
  CRITICAL: "\u26D4",
  ERROR: "\u26A0",
  WARNING: "\u25B3",
};

// ─── Component ──────────────────────────────────────────────────────────────

export default function ChargesheetPage() {
  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadResult, setUploadResult] = useState<ChargeSheet | null>(null);
  const [dragOver, setDragOver] = useState(false);

  // List state
  const [sheets, setSheets] = useState<ChargeSheet[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [filterDistrict, setFilterDistrict] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const PAGE_SIZE = 10;

  // Detail state
  const [selected, setSelected] = useState<ChargeSheet | null>(null);
  const [activeTab, setActiveTab] = useState<
    "accused" | "charges" | "evidence" | "witnesses" | "validation" | "evidence_analysis"
  >("accused");

  // Validation state
  const [validating, setValidating] = useState(false);
  const [validationReport, setValidationReport] =
    useState<ValidationReport | null>(null);
  const [validationError, setValidationError] = useState("");

  // Section lookup tooltip
  const [tooltipSection, setTooltipSection] = useState<SectionLookup | null>(null);
  const [tooltipLoading, setTooltipLoading] = useState(false);

  // Evidence analysis state
  const [analyzing, setAnalyzing] = useState(false);
  const [evidenceReport, setEvidenceReport] = useState<EvidenceGapReport | null>(null);
  const [evidenceError, setEvidenceError] = useState("");

  // ── Data loading ────────────────────────────────────────────────────────

  const loadSheets = useCallback(
    async (pageIndex: number, district: string, status: string) => {
      setListLoading(true);
      setListError("");
      try {
        const params = new URLSearchParams({
          limit: String(PAGE_SIZE),
          offset: String(pageIndex * PAGE_SIZE),
        });
        if (district) params.set("district", district);
        if (status) params.set("status", status);
        const data: ChargeSheet[] = await apiClient(
          `/api/v1/chargesheet?${params.toString()}`
        );
        if (pageIndex === 0) {
          setSheets(data);
        } else {
          setSheets((prev) => [...prev, ...data]);
        }
        setHasMore(data.length === PAGE_SIZE);
      } catch {
        setListError("Failed to load charge-sheets.");
      } finally {
        setListLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    setPage(0);
    loadSheets(0, filterDistrict, filterStatus);
  }, [filterDistrict, filterStatus, loadSheets]);

  const loadMore = () => {
    const next = page + 1;
    setPage(next);
    loadSheets(next, filterDistrict, filterStatus);
  };

  // ── Upload ──────────────────────────────────────────────────────────────

  const uploadFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setUploadError("Only PDF files are accepted.");
        return;
      }
      setUploading(true);
      setUploadError("");
      setUploadResult(null);
      try {
        const formData = new FormData();
        formData.append("file", file);
        const token = localStorage.getItem("atlas_token");
        const res = await fetch(`${BASE_URL}/api/v1/chargesheet/upload`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        });
        if (res.status === 403) {
          setUploadError("Insufficient permissions. Minimum role: SHO.");
          return;
        }
        if (!res.ok) {
          setUploadError(`Upload failed (${res.status})`);
          return;
        }
        const data = await res.json();
        setUploadResult(data);
        loadSheets(0, filterDistrict, filterStatus);
        setPage(0);
      } catch {
        setUploadError("Connection error. Is the backend running?");
      } finally {
        setUploading(false);
      }
    },
    [filterDistrict, filterStatus, loadSheets]
  );

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  }

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  }

  // ── Validation ─────────────────────────────────────────────────────────

  async function runValidation(csId: string) {
    setValidating(true);
    setValidationError("");
    setValidationReport(null);
    try {
      const data: ValidationReport = await apiClient(
        `/api/v1/validate/chargesheet/${csId}`,
        { method: "POST" }
      );
      setValidationReport(data);
      setActiveTab("validation");
    } catch (err) {
      setValidationError(
        err instanceof Error ? err.message : "Validation failed."
      );
    } finally {
      setValidating(false);
    }
  }

  // ── Section lookup ─────────────────────────────────────────────────────

  async function lookupSection(section: string, act: string) {
    setTooltipLoading(true);
    try {
      const data: SectionLookup = await apiClient(
        `/api/v1/validate/sections/lookup?section=${encodeURIComponent(section)}&act=${encodeURIComponent(act.toLowerCase())}`
      );
      setTooltipSection(data);
    } catch {
      setTooltipSection(null);
    } finally {
      setTooltipLoading(false);
    }
  }

  // ── Evidence analysis ────────────────────────────────────────────────

  async function runEvidenceAnalysis(csId: string) {
    setAnalyzing(true);
    setEvidenceError("");
    setEvidenceReport(null);
    try {
      const data: EvidenceGapReport = await apiClient(
        `/api/v1/evidence/analyze/${csId}`,
        { method: "POST" }
      );
      setEvidenceReport(data);
      setActiveTab("evidence_analysis");
    } catch (err) {
      setEvidenceError(
        err instanceof Error ? err.message : "Evidence analysis failed."
      );
    } finally {
      setAnalyzing(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Charge-Sheet Module</h2>

      {/* Upload zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors mb-6 ${
          dragOver
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 hover:border-gray-400"
        }`}
        onClick={() => document.getElementById("cs-file-input")?.click()}
      >
        <input
          id="cs-file-input"
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={handleFileInput}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-muted-foreground">Processing charge-sheet PDF...</p>
          </div>
        ) : (
          <div>
            <p className="text-lg font-medium">
              Drag & drop a Charge-Sheet PDF here
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              or click to browse files
            </p>
          </div>
        )}
      </div>

      {uploadError && <p className="text-red-600 mb-4">{uploadError}</p>}

      {/* Upload result card */}
      {uploadResult && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Parsed Charge-Sheet
              <Badge variant="secondary">{uploadResult.status}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {uploadResult.court_name && (
              <p>
                <span className="font-medium">Court:</span>{" "}
                {uploadResult.court_name}
              </p>
            )}
            {uploadResult.district && (
              <p>
                <span className="font-medium">District:</span>{" "}
                {uploadResult.district}
              </p>
            )}
            {uploadResult.io_name && (
              <p>
                <span className="font-medium">IO:</span>{" "}
                {uploadResult.io_name}
              </p>
            )}
            {uploadResult.accused_json && uploadResult.accused_json.length > 0 && (
              <p>
                <span className="font-medium">Accused:</span>{" "}
                {uploadResult.accused_json.length} person(s)
              </p>
            )}
            {uploadResult.charges_json && uploadResult.charges_json.length > 0 && (
              <p>
                <span className="font-medium">Charges:</span>{" "}
                {uploadResult.charges_json
                  .map((c) => `${c.section} ${c.act}`)
                  .join(", ")}
              </p>
            )}
            {uploadResult.fir_id && (
              <p className="text-green-700 font-medium">
                Linked to FIR record
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Browse table */}
      <div className="mt-8">
        <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
          <h3 className="text-xl font-semibold">Charge-Sheet Browse</h3>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Filter by district..."
              value={filterDistrict}
              onChange={(e) => setFilterDistrict(e.target.value)}
              className="border rounded px-3 py-1 text-sm w-44"
            />
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="border rounded px-3 py-1 text-sm"
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="parsed">Parsed</option>
              <option value="reviewed">Reviewed</option>
              <option value="flagged">Flagged</option>
            </select>
          </div>
        </div>

        {listError && <p className="text-red-600 mb-3">{listError}</p>}

        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Court</th>
                <th className="text-left px-4 py-3 font-medium">District</th>
                <th className="text-left px-4 py-3 font-medium">PS</th>
                <th className="text-left px-4 py-3 font-medium">IO</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Accused</th>
                <th className="text-left px-4 py-3 font-medium">Charges</th>
                <th className="text-left px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {sheets.map((cs) => (
                <tr
                  key={cs.id}
                  className="border-t hover:bg-muted/40 transition-colors"
                >
                  <td className="px-4 py-3 max-w-[200px] truncate">
                    {cs.court_name ?? "--"}
                  </td>
                  <td className="px-4 py-3">{cs.district ?? "--"}</td>
                  <td className="px-4 py-3">{cs.police_station ?? "--"}</td>
                  <td className="px-4 py-3">{cs.io_name ?? "--"}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        STATUS_COLOURS[cs.status ?? ""] ??
                        "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {cs.status ?? "pending"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {cs.accused_json?.length ?? 0}
                  </td>
                  <td className="px-4 py-3">
                    {cs.charges_json
                      ?.map((c) => `${c.section ?? "?"} ${c.act ?? ""}`)
                      .join(", ") || "--"}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {cs.created_at
                      ? new Date(cs.created_at).toLocaleDateString()
                      : "--"}
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelected(cs);
                        setActiveTab("accused");
                        setValidationReport(null);
                        setValidationError("");
                        setTooltipSection(null);
                        setEvidenceReport(null);
                        setEvidenceError("");
                      }}
                    >
                      View
                    </Button>
                  </td>
                </tr>
              ))}
              {sheets.length === 0 && !listLoading && (
                <tr>
                  <td
                    colSpan={9}
                    className="px-4 py-8 text-center text-muted-foreground"
                  >
                    No charge-sheets found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {hasMore && sheets.length > 0 && (
          <div className="mt-4 text-center">
            <Button
              variant="outline"
              onClick={loadMore}
              disabled={listLoading}
            >
              {listLoading ? "Loading..." : "Load More"}
            </Button>
          </div>
        )}
      </div>

      {/* Detail slide-over panel */}
      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setSelected(null)}
          />
          <div className="relative w-full max-w-2xl bg-white shadow-xl overflow-y-auto">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between z-10">
              <div>
                <h3 className="font-semibold text-lg">Charge-Sheet Detail</h3>
                <p className="text-sm text-muted-foreground">
                  {selected.court_name ?? "Unknown Court"} &middot;{" "}
                  {selected.district ?? ""}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="default"
                  disabled={validating || !selected.id}
                  onClick={() => selected.id && runValidation(selected.id)}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {validating ? "Validating..." : "Validate"}
                </Button>
                <Button
                  size="sm"
                  variant="default"
                  disabled={analyzing || !selected.id}
                  onClick={() => selected.id && runEvidenceAnalysis(selected.id)}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {analyzing ? "Analyzing..." : "Analyze Evidence"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setSelected(null)}
                >
                  Close
                </Button>
              </div>
            </div>

            <div className="px-6 py-4 space-y-4">
              {/* Summary cards */}
              <div className="grid grid-cols-2 gap-3">
                <Card>
                  <CardContent className="p-3">
                    <p className="text-xs text-muted-foreground">IO</p>
                    <p className="font-medium text-sm">
                      {selected.io_name ?? "--"}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3">
                    <p className="text-xs text-muted-foreground">Status</p>
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        STATUS_COLOURS[selected.status ?? ""] ??
                        "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {selected.status ?? "pending"}
                    </span>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3">
                    <p className="text-xs text-muted-foreground">PS</p>
                    <p className="font-medium text-sm">
                      {selected.police_station ?? "--"}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3">
                    <p className="text-xs text-muted-foreground">FIR Linked</p>
                    <p className="font-medium text-sm">
                      {selected.fir_id ? "Yes" : "No"}
                    </p>
                  </CardContent>
                </Card>
              </div>

              {selected.reviewer_notes && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm">
                  <span className="font-medium">Reviewer notes:</span>{" "}
                  {selected.reviewer_notes}
                </div>
              )}

              {validationError && (
                <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-800">
                  Validation error: {validationError}
                </div>
              )}

              {evidenceError && (
                <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-800">
                  Evidence analysis error: {evidenceError}
                </div>
              )}

              {/* Evidence coverage bar */}
              {evidenceReport && (
                <div className="flex items-center gap-3 p-3 rounded-lg border bg-emerald-50">
                  <div className="w-12 h-12 rounded-full border-4 border-emerald-400 flex items-center justify-center text-sm font-bold text-emerald-700">
                    {Math.round(evidenceReport.evidence_coverage_pct)}%
                  </div>
                  <div className="flex-1">
                    <span className="text-sm font-semibold">Evidence Coverage</span>
                    <p className="text-xs text-muted-foreground">
                      {evidenceReport.total_present} of {evidenceReport.total_expected} expected items present
                      &middot; {evidenceReport.total_gaps} gaps found
                      &middot; Crime: {evidenceReport.crime_category?.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
              )}

              {/* Validation summary bar */}
              {validationReport && (
                <div className="flex items-center gap-3 p-3 rounded-lg border bg-slate-50">
                  <span className="text-sm font-semibold">Validation:</span>
                  {validationReport.summary.critical > 0 && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">
                      {validationReport.summary.critical} critical
                    </span>
                  )}
                  {validationReport.summary.errors > 0 && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium">
                      {validationReport.summary.errors} errors
                    </span>
                  )}
                  {validationReport.summary.warnings > 0 && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 font-medium">
                      {validationReport.summary.warnings} warnings
                    </span>
                  )}
                  {validationReport.summary.total_findings === 0 && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
                      All checks passed
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground ml-auto">
                    Evidence coverage:{" "}
                    {validationReport.summary.evidence_coverage_pct}%
                  </span>
                </div>
              )}

              {/* Tabs */}
              <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit flex-wrap">
                {(
                  [
                    "accused",
                    "charges",
                    "evidence",
                    "witnesses",
                    "validation",
                    "evidence_analysis",
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all capitalize ${
                      activeTab === tab
                        ? "bg-white shadow-sm text-slate-800"
                        : "text-slate-500 hover:text-slate-700"
                    } ${
                      tab === "validation" && validationReport
                        ? validationReport.overall_status === "critical"
                          ? "text-red-600"
                          : validationReport.overall_status === "errors"
                          ? "text-orange-600"
                          : ""
                        : ""
                    }`}
                  >
                    {tab === "evidence_analysis" ? "Gaps" : tab}
                    {tab === "evidence_analysis" &&
                      evidenceReport &&
                      evidenceReport.total_gaps > 0 && (
                        <span className="ml-1 text-xs text-emerald-600">
                          ({evidenceReport.total_gaps})
                        </span>
                      )}
                    {tab === "validation" &&
                      validationReport &&
                      validationReport.summary.total_findings > 0 && (
                        <span className="ml-1 text-xs">
                          ({validationReport.summary.total_findings})
                        </span>
                      )}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              {activeTab === "accused" && (
                <div className="space-y-2">
                  {(selected.accused_json ?? []).length === 0 && (
                    <p className="text-muted-foreground text-sm">
                      No accused extracted.
                    </p>
                  )}
                  {(selected.accused_json ?? []).map((a, i) => (
                    <Card key={i}>
                      <CardContent className="p-3 text-sm space-y-1">
                        <p className="font-medium">{a.name ?? "Unknown"}</p>
                        {a.age && (
                          <p className="text-muted-foreground">Age: {a.age}</p>
                        )}
                        {a.address && (
                          <p className="text-muted-foreground">
                            Address: {a.address}
                          </p>
                        )}
                        {a.role && (
                          <Badge variant="secondary" className="text-xs">
                            {a.role}
                          </Badge>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              {activeTab === "charges" && (
                <div className="space-y-2">
                  {(selected.charges_json ?? []).length === 0 && (
                    <p className="text-muted-foreground text-sm">
                      No charges extracted.
                    </p>
                  )}
                  {(selected.charges_json ?? []).map((c, i) => (
                    <Card key={i}>
                      <CardContent className="p-3 text-sm">
                        <div className="flex items-center gap-2">
                          <button
                            className="font-medium text-blue-600 hover:underline cursor-pointer"
                            onClick={() =>
                              lookupSection(
                                c.section ?? "",
                                c.act ?? "ipc"
                              )
                            }
                          >
                            Section {c.section ?? "?"}{" "}
                            <span className="text-muted-foreground">
                              {c.act ?? ""}
                            </span>
                          </button>
                          {tooltipLoading && (
                            <span className="text-xs text-muted-foreground">
                              Loading...
                            </span>
                          )}
                        </div>
                        {c.description && (
                          <p className="text-muted-foreground mt-1">
                            {c.description}
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                  {/* Section lookup tooltip */}
                  {tooltipSection && (
                    <Card className="border-blue-200 bg-blue-50">
                      <CardContent className="p-3 text-sm space-y-1">
                        <div className="flex items-center justify-between">
                          <p className="font-semibold">
                            Section {tooltipSection.section}{" "}
                            {tooltipSection.act} &mdash;{" "}
                            {tooltipSection.title}
                          </p>
                          <button
                            className="text-xs text-muted-foreground hover:text-slate-800"
                            onClick={() => setTooltipSection(null)}
                          >
                            Close
                          </button>
                        </div>
                        {tooltipSection.category && (
                          <p>
                            <span className="font-medium">Category:</span>{" "}
                            {tooltipSection.category}
                          </p>
                        )}
                        <p>
                          <span className="font-medium">Cognizable:</span>{" "}
                          {tooltipSection.cognizable ? "Yes" : "No"} &middot;{" "}
                          <span className="font-medium">Bailable:</span>{" "}
                          {tooltipSection.bailable ? "Yes" : "No"}
                        </p>
                        {tooltipSection.max_sentence && (
                          <p>
                            <span className="font-medium">Max sentence:</span>{" "}
                            {tooltipSection.max_sentence}
                          </p>
                        )}
                        {tooltipSection.equivalent?.bns_section && (
                          <p>
                            <span className="font-medium">
                              BNS equivalent:
                            </span>{" "}
                            Section {tooltipSection.equivalent.bns_section}
                          </p>
                        )}
                        {tooltipSection.equivalent?.ipc_section && (
                          <p>
                            <span className="font-medium">
                              IPC equivalent:
                            </span>{" "}
                            Section {tooltipSection.equivalent.ipc_section}
                          </p>
                        )}
                        {tooltipSection.mandatory_evidence &&
                          tooltipSection.mandatory_evidence.length > 0 && (
                            <p>
                              <span className="font-medium">
                                Required evidence:
                              </span>{" "}
                              {tooltipSection.mandatory_evidence
                                .map((e) => e.replace(/_/g, " "))
                                .join(", ")}
                            </p>
                          )}
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}

              {activeTab === "evidence" && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-muted-foreground border-b">
                        <th className="text-left pb-2">#</th>
                        <th className="text-left pb-2">Type</th>
                        <th className="text-left pb-2">Description</th>
                        <th className="text-left pb-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selected.evidence_json ?? []).map((e, i) => (
                        <tr key={i} className="border-b last:border-0">
                          <td className="py-2 text-muted-foreground">
                            {i + 1}
                          </td>
                          <td className="py-2 font-medium">
                            {e.type ?? "--"}
                          </td>
                          <td className="py-2">{e.description ?? "--"}</td>
                          <td className="py-2">
                            <span
                              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                e.status === "collected"
                                  ? "bg-green-100 text-green-700"
                                  : "bg-yellow-100 text-yellow-700"
                              }`}
                            >
                              {e.status ?? "pending"}
                            </span>
                          </td>
                        </tr>
                      ))}
                      {(selected.evidence_json ?? []).length === 0 && (
                        <tr>
                          <td
                            colSpan={4}
                            className="py-4 text-center text-muted-foreground"
                          >
                            No evidence extracted.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === "witnesses" && (
                <div className="space-y-2">
                  {(selected.witnesses_json ?? []).length === 0 && (
                    <p className="text-muted-foreground text-sm">
                      No witnesses extracted.
                    </p>
                  )}
                  {(selected.witnesses_json ?? []).map((w, i) => (
                    <Card key={i}>
                      <CardContent className="p-3 text-sm space-y-1">
                        <p className="font-medium">{w.name ?? "Unknown"}</p>
                        {w.role && (
                          <Badge variant="secondary" className="text-xs">
                            {w.role}
                          </Badge>
                        )}
                        {w.statement_summary && (
                          <p className="text-muted-foreground mt-1">
                            {w.statement_summary}
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              {activeTab === "validation" && (
                <div className="space-y-3">
                  {!validationReport && (
                    <div className="text-center py-8 text-muted-foreground">
                      <p className="text-sm">
                        Click &quot;Validate&quot; to run legal
                        cross-reference checks.
                      </p>
                    </div>
                  )}
                  {validationReport &&
                    validationReport.findings.length === 0 && (
                      <div className="text-center py-8">
                        <p className="text-green-700 font-medium">
                          All validation checks passed.
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                          {validationReport.summary.sections_validated}{" "}
                          sections validated
                        </p>
                      </div>
                    )}
                  {validationReport &&
                    validationReport.findings.length > 0 && (
                      <div className="space-y-3">
                        {/* NLP narrative summary */}
                        {validationReport.narrative_summary && (
                          <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
                            <p className="font-semibold text-xs uppercase tracking-wide mb-1 text-blue-700">
                              AI Summary
                            </p>
                            {validationReport.narrative_summary
                              .split("\n\n")
                              .map((para, pi) => (
                                <p key={pi} className={pi > 0 ? "mt-2" : ""}>
                                  {para}
                                </p>
                              ))}
                            {(validationReport.suppressed_duplicate_count ?? 0) >
                              0 && (
                              <p className="mt-2 text-xs text-blue-600">
                                {validationReport.suppressed_duplicate_count}{" "}
                                duplicate finding(s) were merged above.
                              </p>
                            )}
                          </div>
                        )}
                        {/* Finding cards — use filtered_findings (deduplicated + scored) when available */}
                        <div className="space-y-2">
                          {(
                            validationReport.filtered_findings ??
                            validationReport.findings
                          ).map((f, i) => {
                            const style =
                              SEVERITY_STYLES[f.severity] ??
                              SEVERITY_STYLES.WARNING;
                            return (
                              <div
                                key={i}
                                className={`p-3 rounded-lg border text-sm ${
                                  f.is_likely_routine
                                    ? "opacity-60 " + style.bg
                                    : style.bg
                                }`}
                              >
                                <div className="flex items-start gap-2">
                                  <span
                                    className={`text-lg leading-none ${style.icon}`}
                                  >
                                    {SEVERITY_ICON[f.severity] ?? "\u25B3"}
                                  </span>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <span className="font-semibold text-xs uppercase">
                                        {f.rule_id}
                                      </span>
                                      <Badge
                                        variant="outline"
                                        className="text-xs"
                                      >
                                        {f.section}
                                      </Badge>
                                      <span className="text-xs font-medium uppercase">
                                        {f.severity}
                                      </span>
                                      {(f.merged_count ?? 1) > 1 && (
                                        <Badge
                                          variant="secondary"
                                          className="text-xs"
                                        >
                                          {f.merged_count} merged
                                        </Badge>
                                      )}
                                      {f.is_likely_routine && (
                                        <Badge
                                          variant="outline"
                                          className="text-xs text-gray-500 border-gray-300"
                                        >
                                          likely routine
                                        </Badge>
                                      )}
                                    </div>
                                    <p className="mt-1">{f.description}</p>
                                    <p className="mt-1 text-xs opacity-80">
                                      Recommendation: {f.recommendation}
                                    </p>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                </div>
              )}

              {activeTab === "evidence_analysis" && (
                <div className="space-y-3">
                  {!evidenceReport && (
                    <div className="text-center py-8 text-muted-foreground">
                      <p className="text-sm">
                        Click &quot;Analyze Evidence&quot; to detect
                        missing evidence categories.
                      </p>
                    </div>
                  )}
                  {evidenceReport &&
                    evidenceReport.evidence_gaps.length === 0 && (
                      <div className="text-center py-8">
                        <p className="text-emerald-700 font-medium">
                          All expected evidence is present.
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                          Coverage: {evidenceReport.evidence_coverage_pct}%
                        </p>
                      </div>
                    )}
                  {evidenceReport &&
                    evidenceReport.evidence_gaps.length > 0 && (
                      <div className="space-y-3">
                        {/* AI narrative summary */}
                        {evidenceReport.narrative_summary && (
                          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                            <p className="font-semibold text-xs uppercase tracking-wide mb-1 text-emerald-700">
                              AI Summary
                            </p>
                            {evidenceReport.narrative_summary
                              .split("\n\n")
                              .map((para, pi) => (
                                <p key={pi} className={pi > 0 ? "mt-2" : ""}>
                                  {para}
                                </p>
                              ))}
                          </div>
                        )}
                        <div className="space-y-2">
                        {evidenceReport.evidence_gaps.map((gap, i) => (
                          <div
                            key={i}
                            className={`p-3 rounded-lg border text-sm ${
                              gap.severity === "critical"
                                ? "bg-red-50 border-red-200 text-red-800"
                                : gap.severity === "important"
                                ? "bg-orange-50 border-orange-200 text-orange-800"
                                : "bg-blue-50 border-blue-200 text-blue-800"
                            }`}
                          >
                            <div className="flex items-start gap-2">
                              <span className="text-lg leading-none">
                                {gap.severity === "critical"
                                  ? "\u26D4"
                                  : gap.severity === "important"
                                  ? "\u26A0"
                                  : "\u2139\uFE0F"}
                              </span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-semibold text-xs">
                                    {gap.category.replace(/_/g, " ").toUpperCase()}
                                  </span>
                                  <Badge
                                    variant="outline"
                                    className="text-xs"
                                  >
                                    {gap.tier === "rule_based"
                                      ? "Rule-based"
                                      : "AI-suggested"}
                                  </Badge>
                                  <span className="text-xs font-medium uppercase">
                                    {gap.severity}
                                  </span>
                                </div>
                                <p className="mt-1">{gap.recommendation}</p>
                                {gap.legal_basis && (
                                  <p className="mt-1 text-xs opacity-80">
                                    Legal basis: {gap.legal_basis}
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                        </div>
                      </div>
                    )}

                  {/* Present evidence */}
                  {evidenceReport &&
                    evidenceReport.evidence_present.length > 0 && (
                      <div className="mt-4">
                        <h4 className="text-sm font-semibold text-muted-foreground mb-2">
                          Evidence Present ({evidenceReport.evidence_present.length})
                        </h4>
                        <div className="space-y-1">
                          {evidenceReport.evidence_present.map((ep, i) => (
                            <div
                              key={i}
                              className="flex items-center gap-2 text-sm p-2 rounded bg-green-50 border border-green-200"
                            >
                              <span className="text-green-600">&#10003;</span>
                              <span className="font-medium">
                                {ep.category.replace(/_/g, " ")}
                              </span>
                              <span className="text-xs text-muted-foreground truncate">
                                {ep.source_text}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
