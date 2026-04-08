"use client";

import { useCallback, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FIRResult {
  fir_number?: string;
  district?: string;
  police_station?: string;
  primary_sections?: string[];
  complainant_name?: string;
  completeness_pct?: number;
  narrative?: string;
}

export default function FIRPage() {
  const [result, setResult] = useState<FIRResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

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
    } catch {
      setError("Connection error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

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
            <p className="text-lg font-medium">
              Drag & drop a FIR PDF here
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              or click to browse files
            </p>
          </div>
        )}
      </div>

      {error && <p className="text-red-600 mb-4">{error}</p>}

      {/* Result */}
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
            {result.fir_number && (
              <p>
                <span className="font-medium">FIR Number:</span>{" "}
                {result.fir_number}
              </p>
            )}
            {result.district && (
              <p>
                <span className="font-medium">District:</span>{" "}
                {result.district}
              </p>
            )}
            {result.police_station && (
              <p>
                <span className="font-medium">Police Station:</span>{" "}
                {result.police_station}
              </p>
            )}
            {result.primary_sections && result.primary_sections.length > 0 && (
              <p>
                <span className="font-medium">Sections:</span>{" "}
                {result.primary_sections.join(", ")}
              </p>
            )}
            {result.complainant_name && (
              <p>
                <span className="font-medium">Complainant:</span>{" "}
                {result.complainant_name}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {result?.narrative && (
        <Card>
          <CardHeader>
            <CardTitle>Narrative</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded">
              {result.narrative}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
