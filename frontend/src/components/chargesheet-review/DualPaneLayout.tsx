'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  Download,
  ChevronDown,
  RefreshCw,
  FileText,
  AlertCircle,
  Loader2,
  Search,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { apiClient } from '@/lib/api';
import ReadinessBar from './ReadinessBar';
import GapPanel from './GapPanel';
import {
  useGapReport,
  useAnalyzeGaps,
  useReanalyze,
} from '@/hooks/chargesheet-gaps/useGapReport';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─── Types ──────────────────────────────────────────────────────────────────

interface ChargeSheet {
  id: string;
  fir_id?: string;
  filing_date?: string;
  court_name?: string;
  accused_json?: {
    name?: string;
    age?: number;
    address?: string;
    role?: string;
  }[];
  charges_json?: {
    section?: string;
    act?: string;
    description?: string;
  }[];
  evidence_json?: {
    type?: string;
    description?: string;
    status?: string;
  }[];
  witnesses_json?: {
    name?: string;
    role?: string;
    statement_summary?: string;
  }[];
  io_name?: string;
  status?: string;
  district?: string;
  police_station?: string;
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function DualPaneLayout({
  chargesheetId,
}: {
  chargesheetId: string;
}) {
  // Chargesheet data
  const [cs, setCs] = useState<ChargeSheet | null>(null);
  const [csLoading, setCsLoading] = useState(true);
  const [csError, setCsError] = useState('');

  // Gap report
  const {
    data: gapReport,
    isLoading: gapLoading,
    error: gapError,
  } = useGapReport(chargesheetId);

  const analyzeGaps = useAnalyzeGaps(chargesheetId);
  const reanalyzeMut = useReanalyze(chargesheetId);

  // Reanalyze modal
  const [showReanalyze, setShowReanalyze] = useState(false);
  const [reanalyzeJustification, setReanalyzeJustification] = useState('');

  // Export dropdown
  const [showExportMenu, setShowExportMenu] = useState(false);

  // Mobile tab
  const [mobileTab, setMobileTab] = useState<'document' | 'gaps'>('document');

  // Draggable divider (desktop >=1280px)
  const [splitPct, setSplitPct] = useState(50);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Collapsible sections in document pane
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggleCollapse = (key: string) =>
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

  // ── Load chargesheet ──────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await apiClient(
          `/api/v1/chargesheet/${chargesheetId}`
        );
        if (!cancelled) setCs(data);
      } catch {
        if (!cancelled) setCsError('Failed to load chargesheet.');
      } finally {
        if (!cancelled) setCsLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [chargesheetId]);

  // ── Draggable divider handlers ────────────────────────────────────────

  const onDividerMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
  }, []);

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPct(Math.min(Math.max(pct, 25), 75));
    }
    function onMouseUp() {
      dragging.current = false;
    }
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  // ── Export handlers ───────────────────────────────────────────────────

  const handleExport = useCallback(
    async (type: 'clean_pdf' | 'review_report' | 'redline') => {
      setShowExportMenu(false);
      try {
        const token = localStorage.getItem('atlas_token');
        const endpoint = `/api/v1/chargesheet/${chargesheetId}/gaps/export/${type}`;
        const res = await fetch(`${BASE_URL}${endpoint}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error(`Export failed: HTTP ${res.status}`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${type}_${chargesheetId.slice(0, 8)}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        setCsError(`Export (${type}) failed.`);
      }
    },
    [chargesheetId]
  );

  // ── Reanalyze handler ─────────────────────────────────────────────────

  const handleReanalyze = useCallback(async () => {
    if (!reanalyzeJustification.trim()) return;
    try {
      await reanalyzeMut.mutateAsync(reanalyzeJustification);
      setShowReanalyze(false);
      setReanalyzeJustification('');
    } catch {
      // Error handled by mutation
    }
  }, [reanalyzeMut, reanalyzeJustification]);

  // ── Jump to document handler ──────────────────────────────────────────

  const handleJumpToDocument = useCallback(
    (gap: { id: string; location?: { page_num?: number } }) => {
      setMobileTab('document');
      // Future: scroll to gap.location.page_num in PDF viewer
      if (gap.location?.page_num) {
        console.debug('Jump to page', gap.location.page_num);
      }
    },
    []
  );

  // ── Render: loading / error ───────────────────────────────────────────

  if (csLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2
          className="w-8 h-8 text-blue-500 animate-spin"
          aria-label="Loading chargesheet"
        />
      </div>
    );
  }

  if (csError && !cs) {
    return (
      <div className="flex items-center justify-center h-64 text-red-600 text-sm">
        <AlertCircle className="w-5 h-5 mr-2" aria-hidden="true" />
        {csError}
      </div>
    );
  }

  if (!cs) {
    return (
      <div className="flex items-center justify-center h-64 text-red-600 text-sm">
        <AlertCircle className="w-5 h-5 mr-2" aria-hidden="true" />
        Chargesheet not found.
      </div>
    );
  }

  const gaps = gapReport?.gaps ?? [];

  // ── Document pane content ─────────────────────────────────────────────

  const documentPane = (
    <div className="h-full overflow-y-auto p-4 space-y-3">
      {/* Case Details */}
      <Card>
        <CardHeader
          className="pb-2 cursor-pointer"
          onClick={() => toggleCollapse('meta')}
        >
          <CardTitle className="text-sm">Case Details</CardTitle>
        </CardHeader>
        {!collapsed.meta && (
          <CardContent className="text-sm space-y-1">
            {cs.io_name && (
              <p>
                <span className="font-medium">IO:</span> {cs.io_name}
              </p>
            )}
            {cs.court_name && (
              <p>
                <span className="font-medium">Court:</span> {cs.court_name}
              </p>
            )}
            {cs.filing_date && (
              <p>
                <span className="font-medium">Filing:</span>{' '}
                {cs.filing_date}
              </p>
            )}
            {cs.fir_id && (
              <p>
                <span className="font-medium">FIR Linked:</span> Yes
              </p>
            )}
            {cs.district && (
              <p>
                <span className="font-medium">District:</span>{' '}
                {cs.district}
              </p>
            )}
            {cs.police_station && (
              <p>
                <span className="font-medium">Police Station:</span>{' '}
                {cs.police_station}
              </p>
            )}
          </CardContent>
        )}
      </Card>

      {/* Charges */}
      <Card>
        <CardHeader
          className="pb-2 cursor-pointer"
          onClick={() => toggleCollapse('charges')}
        >
          <CardTitle className="text-sm">
            Charges ({cs.charges_json?.length ?? 0})
          </CardTitle>
        </CardHeader>
        {!collapsed.charges && (
          <CardContent className="space-y-1">
            {(cs.charges_json ?? []).length > 0 ? (
              (cs.charges_json ?? []).map((c, i) => (
                <div key={i} className="text-xs flex items-center gap-1">
                  <Badge variant="outline" className="text-xs shrink-0">
                    {c.section} {c.act}
                  </Badge>
                  {c.description && (
                    <span className="text-muted-foreground truncate">
                      {c.description}
                    </span>
                  )}
                </div>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">
                No charges recorded.
              </p>
            )}
          </CardContent>
        )}
      </Card>

      {/* Accused */}
      <Card>
        <CardHeader
          className="pb-2 cursor-pointer"
          onClick={() => toggleCollapse('accused')}
        >
          <CardTitle className="text-sm">
            Accused ({cs.accused_json?.length ?? 0})
          </CardTitle>
        </CardHeader>
        {!collapsed.accused && (
          <CardContent>
            {(cs.accused_json ?? []).length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-muted-foreground border-b">
                    <th className="text-left pb-1">Name</th>
                    <th className="text-left pb-1">Age</th>
                    <th className="text-left pb-1">Role</th>
                  </tr>
                </thead>
                <tbody>
                  {(cs.accused_json ?? []).map((a, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-1">{a.name ?? '--'}</td>
                      <td className="py-1">{a.age ?? '--'}</td>
                      <td className="py-1">{a.role ?? '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-xs text-muted-foreground">
                No accused listed.
              </p>
            )}
          </CardContent>
        )}
      </Card>

      {/* Evidence */}
      <Card>
        <CardHeader
          className="pb-2 cursor-pointer"
          onClick={() => toggleCollapse('evidence')}
        >
          <CardTitle className="text-sm">
            Evidence ({cs.evidence_json?.length ?? 0})
          </CardTitle>
        </CardHeader>
        {!collapsed.evidence && (
          <CardContent>
            {(cs.evidence_json ?? []).length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-muted-foreground border-b">
                    <th className="text-left pb-1">Type</th>
                    <th className="text-left pb-1">Description</th>
                    <th className="text-left pb-1">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(cs.evidence_json ?? []).map((e, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-1 font-medium">
                        {e.type ?? '--'}
                      </td>
                      <td className="py-1">
                        {e.description ?? '--'}
                      </td>
                      <td className="py-1">
                        <span
                          className={`px-1 py-0.5 rounded text-[10px] ${
                            e.status === 'collected'
                              ? 'bg-green-100 text-green-700'
                              : 'bg-yellow-100 text-yellow-700'
                          }`}
                        >
                          {e.status ?? 'pending'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-xs text-muted-foreground">
                No evidence listed.
              </p>
            )}
          </CardContent>
        )}
      </Card>

      {/* Witnesses */}
      <Card>
        <CardHeader
          className="pb-2 cursor-pointer"
          onClick={() => toggleCollapse('witnesses')}
        >
          <CardTitle className="text-sm">
            Witnesses ({cs.witnesses_json?.length ?? 0})
          </CardTitle>
        </CardHeader>
        {!collapsed.witnesses && (
          <CardContent>
            {(cs.witnesses_json ?? []).length > 0 ? (
              (cs.witnesses_json ?? []).map((w, i) => (
                <div
                  key={i}
                  className="text-xs py-1 border-b last:border-0"
                >
                  <span className="font-medium">
                    {w.name ?? 'Unknown'}
                  </span>
                  {w.role && (
                    <Badge
                      variant="secondary"
                      className="text-[10px] ml-1"
                    >
                      {w.role}
                    </Badge>
                  )}
                  {w.statement_summary && (
                    <p className="text-muted-foreground mt-0.5">
                      {w.statement_summary}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">
                No witnesses listed.
              </p>
            )}
          </CardContent>
        )}
      </Card>
    </div>
  );

  // ── Gaps pane content ─────────────────────────────────────────────────

  const gapsPane = (
    <div className="h-full flex flex-col p-4">
      {/* Readiness bar */}
      <div className="shrink-0 mb-3">
        <ReadinessBar gaps={gaps} />
      </div>

      {/* Loading */}
      {gapLoading && (
        <div className="flex items-center justify-center h-32">
          <Loader2
            className="w-6 h-6 text-blue-500 animate-spin"
            aria-label="Loading gap report"
          />
        </div>
      )}

      {/* No report yet (error = 404 or similar) */}
      {gapError && !gapLoading && (
        <div className="flex flex-col items-center justify-center h-48 space-y-4">
          <div className="text-center">
            <Search
              className="w-10 h-10 text-slate-300 mx-auto mb-3"
              aria-hidden="true"
            />
            <p className="text-sm text-slate-600 font-medium">
              No Gap Analysis Available
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Run an analysis to identify gaps in this chargesheet.
            </p>
          </div>
          <Button
            className="bg-blue-600 hover:bg-blue-700 text-white"
            onClick={() => analyzeGaps.mutate()}
            disabled={analyzeGaps.isPending}
            aria-label="Analyze gaps in this chargesheet"
          >
            {analyzeGaps.isPending ? (
              <>
                <Loader2
                  className="w-4 h-4 mr-2 animate-spin"
                  aria-hidden="true"
                />
                Analyzing...
              </>
            ) : (
              <>
                <Search
                  className="w-4 h-4 mr-2"
                  aria-hidden="true"
                />
                Analyze Gaps
              </>
            )}
          </Button>
          {analyzeGaps.isError && (
            <p className="text-xs text-red-600">
              Analysis failed:{' '}
              {analyzeGaps.error instanceof Error
                ? analyzeGaps.error.message
                : 'Unknown error'}
            </p>
          )}
        </div>
      )}

      {/* Report loaded */}
      {!gapLoading && !gapError && gapReport && (
        <div className="flex-1 min-h-0">
          <GapPanel
            chargesheetId={chargesheetId}
            gaps={gaps}
            onJumpToDocument={handleJumpToDocument}
          />
        </div>
      )}
    </div>
  );

  // ── Main layout ───────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* ── Sticky top bar ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b bg-white shrink-0 gap-2 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold truncate">
                {cs.court_name ?? 'Case'} &middot;{' '}
                {chargesheetId.slice(0, 8)}
              </h2>
              <Badge
                className={
                  cs.status === 'reviewed'
                    ? 'bg-green-100 text-green-800'
                    : cs.status === 'flagged'
                      ? 'bg-red-100 text-red-800'
                      : cs.status === 'under_review'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-blue-100 text-blue-800'
                }
              >
                {cs.status ?? 'parsed'}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground truncate">
              {[cs.io_name, cs.district, cs.filing_date]
                .filter(Boolean)
                .join(' \u00b7 ')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Export dropdown */}
          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={() => setShowExportMenu(!showExportMenu)}
              aria-label="Export options"
              aria-expanded={showExportMenu}
            >
              <Download
                className="w-3.5 h-3.5 mr-1"
                aria-hidden="true"
              />
              Export
              <ChevronDown
                className="w-3 h-3 ml-1"
                aria-hidden="true"
              />
            </Button>
            {showExportMenu && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setShowExportMenu(false)}
                />
                <div className="absolute right-0 top-full mt-1 z-50 bg-white border border-slate-200 rounded-lg shadow-lg py-1 w-52">
                  <button
                    className="w-full text-left px-3 py-2 text-xs hover:bg-slate-50 flex items-center gap-2"
                    onClick={() => handleExport('clean_pdf')}
                  >
                    <FileText
                      className="w-3.5 h-3.5 text-slate-400"
                      aria-hidden="true"
                    />
                    <div>
                      <span className="font-medium">Clean PDF</span>
                      <span className="block text-[10px] text-slate-400">
                        Court-ready, no AI markings
                      </span>
                    </div>
                  </button>
                  <button
                    className="w-full text-left px-3 py-2 text-xs hover:bg-slate-50 flex items-center gap-2"
                    onClick={() => handleExport('review_report')}
                  >
                    <FileText
                      className="w-3.5 h-3.5 text-slate-400"
                      aria-hidden="true"
                    />
                    <div>
                      <span className="font-medium">Review Report</span>
                      <span className="block text-[10px] text-slate-400">
                        Internal, watermarked
                      </span>
                    </div>
                  </button>
                  <button
                    className="w-full text-left px-3 py-2 text-xs hover:bg-slate-50 flex items-center gap-2"
                    onClick={() => handleExport('redline')}
                  >
                    <FileText
                      className="w-3.5 h-3.5 text-slate-400"
                      aria-hidden="true"
                    />
                    <div>
                      <span className="font-medium">Redline</span>
                      <span className="block text-[10px] text-slate-400">
                        Original vs current diff
                      </span>
                    </div>
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Reanalyze */}
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs"
            onClick={() => setShowReanalyze(true)}
            disabled={!gapReport}
            aria-label="Reanalyze gaps"
          >
            <RefreshCw
              className="w-3.5 h-3.5 mr-1"
              aria-hidden="true"
            />
            Reanalyze
          </Button>
        </div>
      </div>

      {/* Error banner */}
      {csError && (
        <div className="mx-4 mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-800 shrink-0">
          {csError}
          <button
            className="ml-2 underline"
            onClick={() => setCsError('')}
          >
            dismiss
          </button>
        </div>
      )}

      {/* Reanalyze modal */}
      {showReanalyze && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-sm font-semibold mb-3">
              Reanalyze Gaps
            </h3>
            <p className="text-xs text-slate-500 mb-3">
              Provide a justification for re-running the gap analysis.
              This will generate a new report.
            </p>
            <textarea
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-3 focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
              rows={3}
              value={reanalyzeJustification}
              onChange={(e) =>
                setReanalyzeJustification(e.target.value)
              }
              placeholder="Justification for reanalysis..."
              aria-label="Reanalysis justification"
            />
            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowReanalyze(false);
                  setReanalyzeJustification('');
                }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white"
                onClick={handleReanalyze}
                disabled={
                  !reanalyzeJustification.trim() ||
                  reanalyzeMut.isPending
                }
                aria-label="Submit reanalysis"
              >
                {reanalyzeMut.isPending
                  ? 'Analyzing...'
                  : 'Reanalyze'}
              </Button>
            </div>
            {reanalyzeMut.isError && (
              <p className="text-xs text-red-600 mt-2">
                Reanalysis failed:{' '}
                {reanalyzeMut.error instanceof Error
                  ? reanalyzeMut.error.message
                  : 'Unknown error'}
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Mobile tabbed layout (<768px) ─────────────────────────────── */}
      <div className="flex-1 min-h-0 md:hidden flex flex-col">
        <div className="flex border-b shrink-0">
          <button
            className={`flex-1 px-4 py-2 text-sm font-medium text-center transition-colors ${
              mobileTab === 'document'
                ? 'border-b-2 border-blue-500 text-blue-700'
                : 'text-slate-500 hover:text-slate-700'
            }`}
            onClick={() => setMobileTab('document')}
            role="tab"
            aria-selected={mobileTab === 'document'}
            aria-controls="mobile-document-panel"
          >
            Document
          </button>
          <button
            className={`flex-1 px-4 py-2 text-sm font-medium text-center transition-colors ${
              mobileTab === 'gaps'
                ? 'border-b-2 border-blue-500 text-blue-700'
                : 'text-slate-500 hover:text-slate-700'
            }`}
            onClick={() => setMobileTab('gaps')}
            role="tab"
            aria-selected={mobileTab === 'gaps'}
            aria-controls="mobile-gaps-panel"
          >
            Gaps
            {gaps.length > 0 && (
              <Badge className="ml-1.5 bg-red-100 text-red-700 text-[10px] px-1.5 py-0 border-0">
                {gaps.length}
              </Badge>
            )}
          </button>
        </div>
        <div className="flex-1 min-h-0">
          {mobileTab === 'document' && (
            <div
              id="mobile-document-panel"
              role="tabpanel"
              className="h-full"
            >
              {documentPane}
            </div>
          )}
          {mobileTab === 'gaps' && (
            <div
              id="mobile-gaps-panel"
              role="tabpanel"
              className="h-full"
            >
              {gapsPane}
            </div>
          )}
        </div>
      </div>

      {/* ── Tablet layout (768-1279px): 60/40 split ──────────────────── */}
      <div className="flex-1 min-h-0 hidden md:flex xl:hidden">
        <div className="w-[60%] border-r">{documentPane}</div>
        <div className="w-[40%]">{gapsPane}</div>
      </div>

      {/* ── Desktop layout (>=1280px) with draggable divider ─────────── */}
      <div
        ref={containerRef}
        className="flex-1 min-h-0 hidden xl:flex relative"
      >
        {/* Left pane */}
        <div
          style={{ width: `${splitPct}%` }}
          className="min-w-0"
        >
          {documentPane}
        </div>

        {/* Draggable divider */}
        <div
          className="w-1.5 bg-slate-200 hover:bg-blue-300 cursor-col-resize shrink-0 transition-colors relative group"
          onMouseDown={onDividerMouseDown}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize panes"
          aria-valuenow={Math.round(splitPct)}
        >
          <div className="absolute inset-y-0 -left-1 -right-1" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-8 rounded-full bg-slate-400 group-hover:bg-blue-500 transition-colors" />
        </div>

        {/* Right pane */}
        <div
          style={{ width: `${100 - splitPct}%` }}
          className="min-w-0"
        >
          {gapsPane}
        </div>
      </div>
    </div>
  );
}
