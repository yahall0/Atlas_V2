import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';

// ---- Types ----

export interface KBStats {
  total_offences: number;
  total_nodes: number;
  total_judgments: number;
  pending_insights: number;
  current_version: string;
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
    mutationFn: ({
      nodeId,
      offenceId,
      data,
    }: {
      nodeId: string;
      offenceId: string;
      data: Record<string, unknown>;
    }) =>
      apiClient(`/api/v1/kb/nodes/${nodeId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_resp, vars) => {
      qc.invalidateQueries({ queryKey: ['kb-offence', vars.offenceId] });
    },
  });
}

export function useDeleteNode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      nodeId,
      offenceId,
    }: {
      nodeId: string;
      offenceId: string;
    }) =>
      apiClient(`/api/v1/kb/nodes/${nodeId}`, {
        method: 'DELETE',
      }),
    onSuccess: (_resp, vars) => {
      qc.invalidateQueries({ queryKey: ['kb-offence', vars.offenceId] });
    },
  });
}
