'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronRight } from 'lucide-react';
import { apiClient } from '@/lib/api';
import MindmapPanel from '@/components/mindmap/MindmapPanel';

interface FIRDetail {
  id: string;
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
  created_at?: string;
}

const STATUS_COLOURS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  classified: 'bg-green-100 text-green-800',
  reviewed: 'bg-blue-100 text-blue-800',
  review_needed: 'bg-amber-100 text-amber-800',
};

export default function FIRDetailPage() {
  const params = useParams();
  const firId = params.firId as string;

  const [fir, setFir] = useState<FIRDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!firId) return;
    setLoading(true);
    apiClient(`/api/v1/firs/${firId}`)
      .then((data) => {
        setFir(data);
        setError('');
      })
      .catch((err) => {
        setError(err.message || 'Failed to load FIR.');
      })
      .finally(() => setLoading(false));
  }, [firId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600 mb-4">{error}</p>
        <Link href="/dashboard/fir">
          <Button variant="outline" size="sm">
            Back to FIR List
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-sm text-slate-500 mb-4">
        <Link
          href="/dashboard/fir"
          className="hover:text-slate-800 transition-colors"
        >
          FIR Review
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <span className="font-medium text-slate-800">
          {fir?.fir_number ?? firId}
        </span>
      </div>

      {/* Main layout: FIR details + Mindmap */}
      <div className="flex-1 flex gap-6 min-h-0">
        {/* Left: FIR details */}
        <div className="w-full lg:w-[400px] shrink-0 overflow-y-auto space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                FIR {fir?.fir_number ?? '—'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="grid grid-cols-[120px_1fr] gap-y-2 gap-x-3">
                <span className="font-medium text-slate-600">District</span>
                <span>{fir?.district ?? '—'}</span>

                <span className="font-medium text-slate-600">
                  Police Station
                </span>
                <span>{fir?.police_station ?? '—'}</span>

                <span className="font-medium text-slate-600">Status</span>
                <span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      STATUS_COLOURS[fir?.status ?? ''] ??
                      'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {fir?.status ?? 'pending'}
                  </span>
                </span>

                <span className="font-medium text-slate-600">Complainant</span>
                <span>{fir?.complainant_name ?? '—'}</span>

                <span className="font-medium text-slate-600">Completeness</span>
                <span>
                  {fir?.completeness_pct != null
                    ? `${fir.completeness_pct}%`
                    : '—'}
                </span>

                <span className="font-medium text-slate-600">
                  Classification
                </span>
                <span>
                  {fir?.nlp_classification ? (
                    <Badge variant="outline">{fir.nlp_classification}</Badge>
                  ) : (
                    '—'
                  )}
                </span>
              </div>

              {/* Sections */}
              {fir?.primary_sections && fir.primary_sections.length > 0 && (
                <div>
                  <p className="font-medium text-slate-600 mb-1">Sections</p>
                  <div className="flex flex-wrap gap-1.5">
                    {fir.primary_sections.map((s) => (
                      <Badge key={s} variant="secondary" className="text-xs">
                        {s}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Narrative */}
          {fir?.narrative && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Narrative</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm bg-slate-50 p-3 rounded border">
                  {fir.narrative}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Mindmap panel */}
        <div className="hidden lg:flex flex-1 min-w-0">
          <div className="w-full">
            <MindmapPanel
              firId={firId}
              caseCategory={fir?.nlp_classification}
              firNumber={fir?.fir_number}
            />
          </div>
        </div>
      </div>

      {/* Mobile mindmap toggle (below lg breakpoint) */}
      <div className="lg:hidden mt-4">
        <MindmapPanel firId={firId} />
      </div>
    </div>
  );
}
