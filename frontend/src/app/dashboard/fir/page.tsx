"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";
import { apiClient } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface NlpMeta {
  mismatch?: boolean;
  section_inferred_category?: string | null;
}

interface FIRResult {
  id?: string;
  fir_number?: string;
  district?: string;
  police_station?: string;
  primary_sections?: string[];
  complainant_name?: string;
  completeness_pct?: number;
  narrative?: string;
  status?: string;
  nlp_classification?: string;
  nlp_confidence?: number;
  nlp_metadata?: NlpMeta;
  created_at?: string;
}

const STATUS_COLOURS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  classified: "bg-green-100 text-green-800",
  reviewed: "bg-blue-100 text-blue-800",
  review_needed: "bg-amber-100 text-amber-800",
};

export default function FIRPage() {
  // Upload state
  const [result, setResult] = useState<FIRResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  // Browse state
  const [firs, setFirs] = useState<FIRResult[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [selectedFir, setSelectedFir] = useState<FIRResult | null>(null);
  const [filterDistrict, setFilterDistrict] = useState("");
  const PAGE_SIZE = 10;

  const loadFirs = useCallback(
    async (pageIndex: number, district: string) => {
      setListLoading(true);
      setListError("");
      try {
        const params = new URLSearchParams({
          limit: String(PAGE_SIZE),
          offset: String(pageIndex * PAGE_SIZE),
        });
        if (district) params.set("district", district);
        const data: FIRResult[] = await apiClient(
          `/api/v1/firs?${params.toString()}`
        );
        if (pageIndex === 0) {
          setFirs(data);
        } else {
          setFirs((prev) => [...prev, ...data]);
        }
        setHasMore(data.length === PAGE_SIZE);
      } catch {
        setListError("Failed to load FIRs.");
      } finally {
        setListLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    setPage(0);
    loadFirs(0, filterDistrict);
  }, [filterDistrict, loadFirs]);

  const loadMore = () => {
    const next = page + 1;
    setPage(next);
    loadFirs(next, filterDistrict);
  };

  // Upload handlers
  const uploadFile = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are accepted.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const token = localStorage.getItem("atlas_token");
      const res = await fetch(`${BASE_URL}/api/v1/ingest`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!res.ok) {
        setError(`Upload failed (${res.status})`);
        return;
      }
      const data = await res.json();
      setResult(data);
      // Refresh list after successful upload
      loadFirs(0, filterDistrict);
      setPage(0);
    } catch {
      setError("Connection error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [filterDistrict, loadFirs]);

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

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">FIR Review Module</h2>

      {/* Upload zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors mb-6 ${
          dragOver
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 hover:border-gray-400"
        }`}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={handleFileInput}
        />
        {loading ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-muted-foreground">Processing PDF...</p>
          </div>
        ) : (
          <div>
            <p className="text-lg font-medium">Drag & drop a FIR PDF here</p>
            <p className="text-sm text-muted-foreground mt-1">or click to browse files</p>
          </div>
        )}
      </div>

      {error && <p className="text-red-600 mb-4">{error}</p>}

      {/* Inline upload result */}
      {result && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>
              Extracted FIR Data
              {result.completeness_pct !== undefined && (
                <Badge className="ml-2" variant="secondary">
                  {result.completeness_pct}% complete
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {result.fir_number && <p><span className="font-medium">FIR Number:</span> {result.fir_number}</p>}
            {result.district && <p><span className="font-medium">District:</span> {result.district}</p>}
            {result.police_station && <p><span className="font-medium">Police Station:</span> {result.police_station}</p>}
            {result.primary_sections && result.primary_sections.length > 0 && (
              <p><span className="font-medium">Sections:</span> {result.primary_sections.join(", ")}</p>
            )}
            {result.complainant_name && <p><span className="font-medium">Complainant:</span> {result.complainant_name}</p>}
          </CardContent>
        </Card>
      )}

      {result?.narrative && (
        <Card className="mb-8">
          <CardHeader><CardTitle>Narrative</CardTitle></CardHeader>
          <CardContent>
            <div className="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded">
              {result.narrative}
            </div>
          </CardContent>
        </Card>
      )}

      {/* FIR Browse Table */}
      <div className="mt-8">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold">FIR Browse</h3>
          <input
            type="text"
            placeholder="Filter by district…"
            value={filterDistrict}
            onChange={(e) => setFilterDistrict(e.target.value)}
            className="border rounded px-3 py-1 text-sm w-48"
          />
        </div>

        {listError && <p className="text-red-600 mb-3">{listError}</p>}

        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="text-left px-4 py-3 font-medium">FIR Number</th>
                <th className="text-left px-4 py-3 font-medium">District</th>
                <th className="text-left px-4 py-3 font-medium">Police Station</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">NLP Category</th>
                <th className="text-left px-4 py-3 font-medium">Completeness</th>
                <th className="text-left px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {firs.map((fir) => (
                <tr key={fir.id} className="border-t hover:bg-muted/40 transition-colors">
                  <td className="px-4 py-3 font-mono">{fir.fir_number ?? "—"}</td>
                  <td className="px-4 py-3">{fir.district ?? "—"}</td>
                  <td className="px-4 py-3">{fir.police_station ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLOURS[fir.status ?? ""] ?? "bg-gray-100 text-gray-700"}`}>
                      {fir.status ?? "pending"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {fir.nlp_classification ? (
                      <div className="flex flex-col gap-1 min-w-[120px]">
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline">{fir.nlp_classification}</Badge>
                          {fir.nlp_metadata?.mismatch && (
                            <span title="Section mismatch detected">
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                            </span>
                          )}
                        </div>
                        {fir.nlp_metadata?.mismatch && fir.nlp_metadata.section_inferred_category && (
                          <span className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5">
                            sections → {fir.nlp_metadata.section_inferred_category}
                          </span>
                        )}
                        {fir.nlp_confidence != null && (
                          <div className="flex items-center gap-1">
                            <div className="flex-1 h-1.5 rounded-full bg-gray-200 overflow-hidden">
                              <div
                                className="h-full rounded-full bg-blue-500"
                                style={{ width: `${Math.round(fir.nlp_confidence * 100)}%` }}
                              />
                            </div>
                            <span className="text-xs text-muted-foreground tabular-nums w-9 text-right">
                              {Math.round(fir.nlp_confidence * 100)}%
                            </span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {fir.completeness_pct != null ? `${fir.completeness_pct}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {fir.created_at ? new Date(fir.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Button size="sm" variant="outline" onClick={() => setSelectedFir(fir)}>
                      View
                    </Button>
                  </td>
                </tr>
              ))}
              {firs.length === 0 && !listLoading && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                    No FIRs found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {listLoading && (
          <div className="flex justify-center mt-4">
            <div className="w-6 h-6 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {hasMore && !listLoading && firs.length > 0 && (
          <div className="flex justify-center mt-4">
            <Button variant="outline" onClick={loadMore}>Load more</Button>
          </div>
        )}
      </div>

      {/* Slide-over detail panel */}
      {selectedFir && (
        <div className="fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="flex-1 bg-black/40"
            onClick={() => setSelectedFir(null)}
          />
          {/* Panel */}
          <div className="w-full max-w-lg bg-white shadow-xl overflow-y-auto p-6">
            <div className="flex items-start justify-between mb-6">
              <h3 className="text-lg font-bold">
                FIR {selectedFir.fir_number ?? selectedFir.id}
              </h3>
              <button
                onClick={() => setSelectedFir(null)}
                className="text-muted-foreground hover:text-foreground text-xl leading-none"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <span className="font-medium">District</span>
                <span>{selectedFir.district ?? "—"}</span>
                <span className="font-medium">Police Station</span>
                <span>{selectedFir.police_station ?? "—"}</span>
                <span className="font-medium">Status</span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium w-fit ${STATUS_COLOURS[selectedFir.status ?? ""] ?? "bg-gray-100 text-gray-700"}`}>
                  {selectedFir.status ?? "pending"}
                </span>
                <span className="font-medium">Sections</span>
                <span>{selectedFir.primary_sections?.join(", ") ?? "—"}</span>
                <span className="font-medium">Complainant</span>
                <span>{selectedFir.complainant_name ?? "—"}</span>
                <span className="font-medium">Completeness</span>
                <span>{selectedFir.completeness_pct != null ? `${selectedFir.completeness_pct}%` : "—"}</span>
              </div>

              {selectedFir.nlp_classification && (
                <div className="border rounded p-3 mt-4 bg-gray-50">
                  <p className="font-medium mb-2">NLP Classification</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge>{selectedFir.nlp_classification}</Badge>
                    {selectedFir.nlp_confidence != null && (
                      <span className="text-xs text-muted-foreground">
                        {(selectedFir.nlp_confidence * 100).toFixed(1)}% confidence
                      </span>
                    )}
                  </div>
                  {selectedFir.nlp_metadata?.mismatch && (
                    <div className="mt-3 flex items-start gap-2 p-2.5 rounded-lg bg-amber-50 border border-amber-200">
                      <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                      <div className="text-xs">
                        <p className="font-semibold text-amber-800">Section mismatch detected</p>
                        <p className="text-amber-700 mt-0.5">
                          The narrative text suggests <strong>{selectedFir.nlp_classification}</strong>, but the registered sections ({selectedFir.primary_sections?.join(", ") ?? "—"}) imply <strong>{selectedFir.nlp_metadata.section_inferred_category ?? "unknown"}</strong>.
                          This FIR has been flagged for review.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {selectedFir.narrative && (
                <div className="mt-4">
                  <p className="font-medium mb-2">Narrative</p>
                  <div className="max-h-64 overflow-y-auto whitespace-pre-wrap bg-gray-50 p-3 rounded text-xs border">
                    {selectedFir.narrative}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
