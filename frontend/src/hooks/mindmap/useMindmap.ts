import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type {
  MindmapData,
  MindmapVersion,
  NodeStatusEntry,
} from '@/components/mindmap/nodes/types';

export function useMindmap(firId: string) {
  return useQuery<MindmapData>({
    queryKey: ['mindmap', firId],
    queryFn: () => apiClient(`/api/v1/fir/${firId}/mindmap`),
    enabled: !!firId,
  });
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
