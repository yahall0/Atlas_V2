import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, ApiError } from '@/lib/api';
import { getDemoMindmap } from '@/components/mindmap/demoMindmaps';
import type {
  MindmapData,
  MindmapVersion,
  NodeStatusEntry,
} from '@/components/mindmap/nodes/types';

export interface UseMindmapOptions {
  /** FIR's nlp_classification — used to pick the demo mindmap when the
   *  backend has no real one yet. Optional; if absent, the generic demo
   *  is used as fallback. */
  caseCategory?: string | null;
  /** FIR registration number — printed in the centre hub of the demo
   *  mindmap ("FIR 11192050250010 | Murder"). Optional. */
  firNumber?: string | null;
  /** Set false to disable the per-category demo fallback (e.g. once the
   *  live KB is wired and you want the empty state instead). */
  useDemoFallback?: boolean;
}

/**
 * Fetches the active mindmap for a FIR, with two graceful fallbacks:
 *
 *   1. 404 from the backend (no mindmap stored yet) → returns a *demo*
 *      mindmap chosen by the FIR's case category, marked with
 *      `metadata.demo === true` so the UI can show a "Demo data" badge.
 *      This is what powers the demo flow before the live 3-layer KB is
 *      wired to the deployment. Set `useDemoFallback: false` to opt out
 *      and get `null` instead.
 *
 *   2. Other API errors propagate as react-query's `isError`, with the
 *      status code preserved on `error.status`.
 */
export function useMindmap(firId: string, opts: UseMindmapOptions = {}) {
  const { caseCategory, firNumber, useDemoFallback = true } = opts;
  return useQuery<MindmapData | null>({
    queryKey: [
      'mindmap', firId, caseCategory ?? null, firNumber ?? null, useDemoFallback,
    ],
    queryFn: async () => {
      try {
        return await apiClient(`/api/v1/fir/${firId}/mindmap`);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          return useDemoFallback
            ? getDemoMindmap(caseCategory, { firNumber })
            : null;
        }
        throw e;
      }
    },
    enabled: !!firId,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && (error.status === 404 || error.status === 401)) {
        return false;
      }
      return failureCount < 2;
    },
  });
}

/** Convenience: true if this MindmapData came from the static demo
 *  registry (vs a live, KB-driven generation by the backend). */
export function isDemoMindmap(data: MindmapData | null | undefined): boolean {
  return Boolean(
    data &&
      typeof data.id === 'string' &&
      data.id.startsWith('demo-')
  );
}

export function useGenerateMindmap(firId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient(`/api/v1/fir/${firId}/mindmap`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mindmap', firId] }),
  });
}

export function useUpdateNodeStatus(firId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      nodeId,
      ...body
    }: {
      nodeId: string;
      status: string;
      note?: string;
      evidence_ref?: string;
      hash_prev: string;
    }) =>
      apiClient(`/api/v1/fir/${firId}/mindmap/nodes/${nodeId}/status`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mindmap', firId] }),
  });
}

export function useAddCustomNode(firId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      parent_id?: string;
      title: string;
      description_md?: string;
      node_type?: string;
      priority?: string;
    }) =>
      apiClient(`/api/v1/fir/${firId}/mindmap/nodes`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mindmap', firId] }),
  });
}

export function useMindmapVersions(firId: string) {
  return useQuery<MindmapVersion[]>({
    queryKey: ['mindmap-versions', firId],
    queryFn: () => apiClient(`/api/v1/fir/${firId}/mindmap/versions`),
    enabled: !!firId,
  });
}

export function useRegenerateMindmap(firId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (justification: string) =>
      apiClient(`/api/v1/fir/${firId}/mindmap/regenerate`, {
        method: 'POST',
        body: JSON.stringify({ justification }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mindmap', firId] });
      qc.invalidateQueries({ queryKey: ['mindmap-versions', firId] });
    },
  });
}

export function useNodeHistory(firId: string, nodeId: string) {
  return useQuery<NodeStatusEntry[]>({
    queryKey: ['node-history', nodeId],
    queryFn: () =>
      apiClient(`/api/v1/fir/${firId}/mindmap/nodes/${nodeId}/history`),
    enabled: !!nodeId,
  });
}
