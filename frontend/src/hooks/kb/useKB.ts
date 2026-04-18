import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';

// ---- Types ----

export type KBLayer =
  | 'canonical_legal'
  | 'investigation_playbook'
  | 'case_law_intelligence';

export type AuthoredByRole =
  | 'legal_advisor'
  | 'sop_committee'
  | 'judgment_extraction'
  | 'manual_curation';

export type UpdateCadence = 'rare' | 'annual' | 'continuous';

export const KB_LAYER_LABELS: Record<KBLayer, string> = {
  canonical_legal: 'Layer 1 — Statute (BNS / BNSS / BSA)',
  investigation_playbook: 'Layer 2 — Investigation Playbook',
  case_law_intelligence: 'Layer 3 — Case Law Intelligence',
};

export const KB_LAYER_BLURB: Record<KBLayer, string> = {
  canonical_legal:
    'What the statute says. Binding absolutely. Authored by legal advisor; updates only on Parliamentary amendment.',
  investigation_playbook:
    'What good investigation looks like — panchnama, evidence packaging, forensic sequencing, bayan. Senior IPS / Gujarat Police training wing. Annual review.',
  case_law_intelligence:
    'What courts have ruled on investigation quality and acquittal patterns. Graded by court (SC > HC-GJ > HC-other > District). Continuous.',
};

export interface LayerStats {
  canonical_legal: number;
  investigation_playbook: number;
  case_law_intelligence: number;
}

export interface KBStats {
  total_offences: number;
  total_nodes: number;
  total_judgments: number;
  pending_insights: number;
  current_version: string;
  // Layer-wise node counts (added by the 3-layer refactor; the backend
  // keeps the legacy canonical/judgment_derived counts too for
  // back-compat).
  canonical_legal_nodes?: number;
  investigation_playbook_nodes?: number;
  case_law_intelligence_nodes?: number;
}

export interface KBOffence {
  id: string;
  offence_code: string;
  display_name_en: string;
  bns_section: string;
  category_id: string;
  node_count: number;
  review_status: string;
}

export interface LegalCitation {
  act: string;
  section: string;
  subsection?: string;
  description?: string;
  framework?: string;
  case_citation?: string;
  source_authority?: string;
}

export interface KnowledgeNode {
  id: string;
  offence_id: string;
  title: string;
  title_en: string;
  title_gu?: string;
  description: string;
  description_md?: string;
  tier: 'canonical' | 'judgment_derived';
  branch_type: string;
  priority: number | string;
  legal_citations: LegalCitation[];
  legal_basis_citations?: LegalCitation[];
  procedural_metadata?: Record<string, unknown>;
  requires_disclaimer?: boolean;
  display_order?: number;
  approval_status: string;
  // 3-layer fields (always populated by the backend after migration 012).
  kb_layer?: KBLayer;
  authored_by_role?: AuthoredByRole;
  update_cadence?: UpdateCadence;
}

export interface OffenceDetail {
  id: string;
  offence_code: string;
  display_name_en: string;
  display_name_gu?: string;
  bns_section: string;
  bns_subsection?: string;
  category_id: string;
  short_description_md?: string;
  punishment: string;
  cognizable: boolean;
  bailable: boolean;
  compoundable: boolean | string;
  triable_by?: string;
  schedule_reference?: string;
  related_offence_codes?: string[];
  special_acts?: string[];
  court: string;
  review_status: string;
  reviewed_by?: string;
  reviewed_at?: string;
  nodes: KnowledgeNode[];
}

export interface CurrentUser {
  username: string;
  role: string;
  full_name: string;
}

export interface JudgmentInsight {
  id: string;
  title: string;
  content: string;
  approval_status: string;
  review_notes?: string;
}

export interface Judgment {
  id: string;
  citation: string;
  case_name: string;
  court: string;
  judgment_date: string;
  binding_authority: string;
  review_status: string;
  insight_count: number;
  insights?: JudgmentInsight[];
}

// ---- Hooks ----

export function useKBStats() {
  return useQuery<KBStats>({
    queryKey: ['kb-stats'],
    queryFn: () => apiClient('/api/v1/kb/stats'),
  });
}

export function useKBOffences(categoryId?: string) {
  return useQuery<KBOffence[]>({
    queryKey: ['kb-offences', categoryId],
    queryFn: () =>
      apiClient(
        `/api/v1/kb/offences${categoryId ? '?category_id=' + categoryId : ''}`
      ),
  });
}

export function useKBOffenceDetail(id: string) {
  return useQuery<OffenceDetail>({
    queryKey: ['kb-offence', id],
    queryFn: () => apiClient(`/api/v1/kb/offences/${id}`),
    enabled: !!id,
  });
}

/**
 * Group an offence's nodes into the three KB layers, deriving the layer
 * from (branch_type, tier) when the backend hasn't yet populated `kb_layer`
 * (e.g. against an older deployment). Mirrors the SQL backfill in
 * migration 012 and the Python helper `derive_kb_layer`.
 */
export function groupNodesByLayer(
  nodes: KnowledgeNode[] | undefined
): Record<KBLayer, KnowledgeNode[]> {
  const out: Record<KBLayer, KnowledgeNode[]> = {
    canonical_legal: [],
    investigation_playbook: [],
    case_law_intelligence: [],
  };
  if (!nodes) return out;
  for (const n of nodes) {
    const layer = n.kb_layer ?? deriveKbLayer(n.branch_type, n.tier);
    out[layer].push(n);
  }
  return out;
}

function deriveKbLayer(
  branch_type: string,
  tier: 'canonical' | 'judgment_derived'
): KBLayer {
  if (tier === 'judgment_derived') return 'case_law_intelligence';
  if (branch_type === 'gap_historical') return 'case_law_intelligence';
  if (branch_type === 'legal_section') return 'canonical_legal';
  return 'investigation_playbook';
}

export function useKBJudgments(status?: string) {
  return useQuery<Judgment[]>({
    queryKey: ['kb-judgments', status],
    queryFn: () =>
      apiClient(
        `/api/v1/kb/judgments${status ? '?review_status=' + status : ''}`
      ),
  });
}

export function useReviewInsight() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      insightId,
      action,
      review_notes,
    }: {
      insightId: string;
      action: string;
      review_notes?: string;
    }) =>
      apiClient(`/api/v1/kb/insights/${insightId}/review`, {
        method: 'PATCH',
        body: JSON.stringify({ action, review_notes }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kb-judgments'] });
      qc.invalidateQueries({ queryKey: ['kb-stats'] });
    },
  });
}

// ---- Auth ----

export function useCurrentUser() {
  return useQuery<CurrentUser>({
    queryKey: ['current-user'],
    queryFn: () => apiClient('/api/v1/auth/me'),
    staleTime: 5 * 60 * 1000,
  });
}

// ---- Admin mutations ----

export function useCreateOffence() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient('/api/v1/kb/offences', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kb-offences'] });
      qc.invalidateQueries({ queryKey: ['kb-stats'] });
    },
  });
}

export function useUpdateOffence() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      apiClient(`/api/v1/kb/offences/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_resp, vars) => {
      qc.invalidateQueries({ queryKey: ['kb-offence', vars.id] });
      qc.invalidateQueries({ queryKey: ['kb-offences'] });
      qc.invalidateQueries({ queryKey: ['kb-stats'] });
    },
  });
}

export function useReviewOffence() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, review_status }: { id: string; review_status: string }) =>
      apiClient(`/api/v1/kb/offences/${id}/review`, {
        method: 'PATCH',
        body: JSON.stringify({ review_status }),
      }),
    onSuccess: (_resp, vars) => {
      qc.invalidateQueries({ queryKey: ['kb-offence', vars.id] });
      qc.invalidateQueries({ queryKey: ['kb-offences'] });
      qc.invalidateQueries({ queryKey: ['kb-stats'] });
    },
  });
}

export function useCreateNode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      offenceId,
      data,
    }: {
      offenceId: string;
      data: Record<string, unknown>;
    }) =>
      apiClient(`/api/v1/kb/offences/${offenceId}/nodes`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: (_resp, vars) => {
      qc.invalidateQueries({ queryKey: ['kb-offence', vars.offenceId] });
    },
  });
}

export function useUpdateNode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      nodeId: string;
      offenceId: string;
      data: Record<string, unknown>;
    }) =>
      apiClient(`/api/v1/kb/nodes/${vars.nodeId}`, {
        method: 'PUT',
        body: JSON.stringify(vars.data),
      }),
    onSuccess: (_resp, vars) => {
      qc.invalidateQueries({ queryKey: ['kb-offence', vars.offenceId] });
    },
  });
}

export function useDeleteNode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { nodeId: string; offenceId: string }) =>
      apiClient(`/api/v1/kb/nodes/${vars.nodeId}`, {
        method: 'DELETE',
      }),
    onSuccess: (_resp, vars) => {
      qc.invalidateQueries({ queryKey: ['kb-offence', vars.offenceId] });
    },
  });
}
