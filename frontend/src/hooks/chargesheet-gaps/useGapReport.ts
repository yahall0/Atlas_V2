'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';

// Types
export interface GapLocation {
  page_num?: number;
  char_offset_start?: number;
  char_offset_end?: number;
  bbox?: number[];
}

export interface LegalRef {
  framework: string;
  section: string;
  deep_link?: string;
}

export interface Remediation {
  summary: string;
  steps: string[];
  suggested_language?: string;
  sop_refs: Array<Record<string, string>>;
  estimated_effort: string;
}

export type GapSeverity = 'critical' | 'high' | 'medium' | 'low' | 'advisory';
export type GapCategory =
  | 'legal'
  | 'evidence'
  | 'witness'
  | 'procedural'
  | 'mindmap_divergence'
  | 'completeness'
  | 'kb_playbook_gap'
  | 'kb_caselaw_gap';
export type GapActionType =
  | 'accepted'
  | 'modified'
  | 'dismissed'
  | 'deferred'
  | 'escalated';

export type KBLayer =
  | 'canonical_legal'
  | 'investigation_playbook'
  | 'case_law_intelligence';

export interface Gap {
  id: string;
  report_id: string;
  category: GapCategory;
  severity: GapSeverity;
  source: string;
  requires_disclaimer: boolean;
  title: string;
  description_md?: string;
  location?: GapLocation;
  legal_refs: LegalRef[];
  remediation: Remediation;
  related_mindmap_node_id?: string;
  confidence: number;
  tags: string[];
  display_order: number;
  current_action?: GapActionType;
  // 3-layer KB attribution. Tells the UI which authority column the
  // finding belongs in (Statute / Playbook / Case-Law).
  kb_layer?: KBLayer;
  kb_node_ref?: string;
}

export interface LayerCounts {
  canonical_legal: number;
  investigation_playbook: number;
  case_law_intelligence: number;
  unattributed: number;
}

export interface GapReport {
  id: string;
  chargesheet_id: string;
  generated_at: string;
  generator_version: string;
  gap_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  advisory_count: number;
  generation_duration_ms?: number;
  gaps: Gap[];
  disclaimer: string;
  partial_sources: string[];
  layer_counts?: LayerCounts;
}

/** Group a gap list into the three KB authority columns. */
export function groupGapsByLayer(
  gaps: Gap[] | undefined
): Record<KBLayer | 'unattributed', Gap[]> {
  const out: Record<KBLayer | 'unattributed', Gap[]> = {
    canonical_legal: [],
    investigation_playbook: [],
    case_law_intelligence: [],
    unattributed: [],
  };
  if (!gaps) return out;
  for (const g of gaps) {
    const k = g.kb_layer ?? 'unattributed';
    out[k].push(g);
  }
  return out;
}

export interface GapAction {
  id: string;
  gap_id: string;
  user_id: string;
  action: GapActionType;
  note?: string;
  modification_diff?: string;
  evidence_ref?: string;
  created_at: string;
  hash_prev: string;
  hash_self: string;
}

export function useGapReport(chargesheetId: string) {
  return useQuery<GapReport>({
    queryKey: ['gap-report', chargesheetId],
    queryFn: () =>
      apiClient(`/api/v1/chargesheet/${chargesheetId}/gaps/report`),
    enabled: !!chargesheetId,
    retry: false,
  });
}

export function useAnalyzeGaps(chargesheetId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient(`/api/v1/chargesheet/${chargesheetId}/gaps/analyze`, {
        method: 'POST',
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['gap-report', chargesheetId] }),
  });
}

export function useGapAction(chargesheetId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      gapId,
      ...body
    }: {
      gapId: string;
      action: string;
      note?: string;
      modification_diff?: string;
      evidence_ref?: string;
      hash_prev: string;
    }) =>
      apiClient(
        `/api/v1/chargesheet/${chargesheetId}/gaps/${gapId}/action`,
        {
          method: 'PATCH',
          body: JSON.stringify(body),
        }
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['gap-report', chargesheetId] }),
  });
}

export function useApplySuggestion(chargesheetId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (gapId: string) =>
      apiClient(
        `/api/v1/chargesheet/${chargesheetId}/gaps/${gapId}/apply-suggestion`,
        {
          method: 'POST',
          body: JSON.stringify({ confirm: true }),
        }
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['gap-report', chargesheetId] }),
  });
}

export function useReanalyze(chargesheetId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (justification: string) =>
      apiClient(`/api/v1/chargesheet/${chargesheetId}/gaps/reanalyze`, {
        method: 'POST',
        body: JSON.stringify({ justification }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gap-report', chargesheetId] });
      qc.invalidateQueries({ queryKey: ['gap-reports', chargesheetId] });
    },
  });
}

export function useGapReportHistory(chargesheetId: string) {
  return useQuery({
    queryKey: ['gap-reports', chargesheetId],
    queryFn: () =>
      apiClient(`/api/v1/chargesheet/${chargesheetId}/gaps/reports`),
    enabled: !!chargesheetId,
  });
}

export function useGapHistory(chargesheetId: string, gapId: string) {
  return useQuery<GapAction[]>({
    queryKey: ['gap-history', gapId],
    queryFn: () =>
      apiClient(
        `/api/v1/chargesheet/${chargesheetId}/gaps/${gapId}/history`
      ),
    enabled: !!gapId,
  });
}
