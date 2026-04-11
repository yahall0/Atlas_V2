"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

const STATUS_COLOURS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  parsed: "bg-blue-100 text-blue-800",
  reviewed: "bg-green-100 text-green-800",
  flagged: "bg-red-100 text-red-800",
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
  const [activeTab, setActiveTab] = useState<"accused" | "charges" | "evidence" | "witnesses">("accused");

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
          `/api/v1/chargesheet/?${params.toString()}`
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
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelected(null)}
              >
                Close
              </Button>
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

              {/* Tabs */}
              <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
                {(
                  ["accused", "charges", "evidence", "witnesses"] as const
                ).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all capitalize ${
                      activeTab === tab
                        ? "bg-white shadow-sm text-slate-800"
                        : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {tab}
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
                        {a.age && <p className="text-muted-foreground">Age: {a.age}</p>}
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
                        <p className="font-medium">
                          Section {c.section ?? "?"}{" "}
                          <span className="text-muted-foreground">
                            {c.act ?? ""}
                          </span>
                        </p>
                        {c.description && (
                          <p className="text-muted-foreground mt-1">
                            {c.description}
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  ))}
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
                          <td className="py-2 font-medium">{e.type ?? "--"}</td>
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
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
