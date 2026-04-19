'use client';

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useUpdateNodeStatus, useNodeHistory } from '@/hooks/mindmap/useMindmap';
import type { MindmapNode, NodeStatusType } from './nodes/types';

const STATUS_OPTIONS: { value: NodeStatusType; label: string }[] = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'addressed', label: 'Addressed' },
  { value: 'not_applicable', label: 'Not Applicable' },
  { value: 'disputed', label: 'Disputed' },
];

const STATUS_COLOUR: Record<NodeStatusType, string> = {
  open: 'bg-gray-100 text-gray-700',
  in_progress: 'bg-yellow-100 text-yellow-800',
  addressed: 'bg-green-100 text-green-800',
  not_applicable: 'bg-slate-100 text-slate-600',
  disputed: 'bg-red-100 text-red-800',
};

interface NodeDetailDrawerProps {
  node: MindmapNode | null;
  firId: string;
  onClose: () => void;
  onStatusUpdate: () => void;
}

export default function NodeDetailDrawer({
  node,
  firId,
  onClose,
  onStatusUpdate,
}: NodeDetailDrawerProps) {
  const [status, setStatus] = useState<NodeStatusType>('open');
  const [note, setNote] = useState('');
  const [evidenceRef, setEvidenceRef] = useState('');

  const updateStatus = useUpdateNodeStatus(firId);
  const { data: history, isLoading: historyLoading } = useNodeHistory(
    firId,
    node?.id ?? ''
  );

  // Sync local state when node changes
  useEffect(() => {
    if (node) {
      setStatus(node.current_status ?? 'open');
      setNote('');
      setEvidenceRef('');
    }
  }, [node]);

  if (!node) return null;

  const handleSave = async () => {
    const lastHash =
      history && history.length > 0
        ? history[history.length - 1].hash_self
        : '';

    await updateStatus.mutateAsync({
      nodeId: node.id,
      status,
      note: note || undefined,
      evidence_ref: evidenceRef || undefined,
      hash_prev: lastHash,
    });

    onStatusUpdate();
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/40" onClick={onClose} />

      {/* Drawer */}
      <div className="w-full max-w-lg bg-white shadow-xl overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b">
          <div>
            <h3 className="text-lg font-bold text-slate-800">{node.title}</h3>
            <Badge variant="outline" className="mt-1 text-xs capitalize">
              {node.node_type.replace(/_/g, ' ')}
            </Badge>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 p-6 space-y-6 overflow-y-auto">
          {/* Description */}
          {node.description_md && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                Description
              </p>
              <div className="text-sm text-slate-700 whitespace-pre-wrap bg-slate-50 rounded p-3 border">
                {node.description_md}
              </div>
            </div>
          )}

          {/* Compendium playbook provenance (ADR-D19) */}
          {node.source === 'playbook' && (
            <div className="rounded-md border border-indigo-200 bg-indigo-50/60 p-3">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-indigo-700">
                Source
              </p>
              <p className="text-sm text-indigo-900">
                Delhi Police Academy — Compendium of Scenarios for Investigating Officers, 2024
              </p>
              {node.metadata && (
                <div className="mt-2 space-y-1 text-xs text-indigo-800">
                  {(node.metadata as Record<string, unknown>).forms ? (
                    <div>
                      <span className="font-medium">Forms:</span>{' '}
                      {((node.metadata as Record<string, unknown>).forms as string[]).join(', ')}
                    </div>
                  ) : null}
                  {(node.metadata as Record<string, unknown>).deadline ? (
                    <div>
                      <span className="font-medium">Deadline:</span>{' '}
                      {(node.metadata as Record<string, unknown>).deadline as string}
                    </div>
                  ) : null}
                  {(node.metadata as Record<string, unknown>).actors ? (
                    <div>
                      <span className="font-medium">Actors:</span>{' '}
                      {((node.metadata as Record<string, unknown>).actors as string[]).join(', ')}
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          )}

          {/* Legal references */}
          {(node.ipc_section || node.bns_section || node.crpc_section) && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Legal References
              </p>
              <div className="flex flex-wrap gap-2">
                {node.ipc_section && (
                  <Badge variant="secondary">IPC {node.ipc_section}</Badge>
                )}
                {node.bns_section && (
                  <Badge variant="secondary">BNS {node.bns_section}</Badge>
                )}
                {node.crpc_section && (
                  <Badge variant="secondary">CrPC {node.crpc_section}</Badge>
                )}
              </div>
            </div>
          )}

          {/* Status update form */}
          <div className="border rounded-lg p-4 space-y-4">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Update Status
            </p>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Status
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as NodeStatusType)}
                className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Note
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                placeholder="Add a note about this status change..."
                className="w-full border rounded-md px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Attach Evidence Reference
              </label>
              <input
                type="text"
                value={evidenceRef}
                onChange={(e) => setEvidenceRef(e.target.value)}
                placeholder="e.g. Document ID, exhibit number..."
                className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <Button
              onClick={handleSave}
              disabled={updateStatus.isPending}
              className="w-full"
            >
              {updateStatus.isPending ? 'Saving...' : 'Save Status'}
            </Button>

            {updateStatus.isError && (
              <p className="text-sm text-red-600">
                Failed to update status. Please try again.
              </p>
            )}
          </div>

          {/* Audit history */}
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Audit History
            </p>

            {historyLoading && (
              <div className="flex justify-center py-4">
                <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              </div>
            )}

            {history && history.length === 0 && (
              <p className="text-sm text-slate-400">No history yet.</p>
            )}

            {history && history.length > 0 && (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {history.map((entry) => (
                  <div
                    key={entry.id}
                    className="border rounded p-3 text-sm space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          STATUS_COLOUR[entry.status] ?? 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {entry.status.replace('_', ' ')}
                      </span>
                      <span className="text-xs text-slate-400">
                        {new Date(entry.updated_at).toLocaleString()}
                      </span>
                    </div>
                    {entry.note && (
                      <p className="text-slate-600">{entry.note}</p>
                    )}
                    {entry.evidence_ref && (
                      <p className="text-xs text-slate-500">
                        Evidence: {entry.evidence_ref}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
