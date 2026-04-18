'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import {
  Clock,
  FileText,
  User,
  ScrollText,
  FlaskConical,
  MessageSquare,
  AlertTriangle,
  UserPlus,
  Scale,
  Info,
} from 'lucide-react';
import type { MindmapNode, NodeType, NodeStatusType, NodePriority } from './types';

/* ------------------------------------------------------------------ */
/* Colour & icon look-up tables                                       */
/* ------------------------------------------------------------------ */

const NODE_STYLES: Record<NodeType, { bg: string; border: string; icon: React.ElementType }> = {
  legal_section:   { bg: 'bg-blue-50',   border: 'border-blue-300',   icon: Scale },
  immediate_action:{ bg: 'bg-red-50',    border: 'border-red-300',    icon: Clock },
  evidence:        { bg: 'bg-green-50',  border: 'border-green-300',  icon: FileText },
  interrogation:   { bg: 'bg-purple-50', border: 'border-purple-300', icon: User },
  panchnama:       { bg: 'bg-amber-50',  border: 'border-amber-300',  icon: ScrollText },
  forensic:        { bg: 'bg-teal-50',   border: 'border-teal-300',   icon: FlaskConical },
  witness_bayan:   { bg: 'bg-indigo-50', border: 'border-indigo-300', icon: MessageSquare },
  gap_from_fir:    { bg: 'bg-orange-50', border: 'border-orange-300', icon: AlertTriangle },
  custom:          { bg: 'bg-gray-50',   border: 'border-gray-300',   icon: UserPlus },
};

const STATUS_DOT: Record<NodeStatusType, string> = {
  open:           'bg-gray-400',
  in_progress:    'bg-yellow-400',
  addressed:      'bg-green-500',
  not_applicable: 'bg-slate-400',
  disputed:       'bg-red-500',
};

const PRIORITY_DOT: Record<NodePriority, string> = {
  critical:    'bg-red-500',
  recommended: 'bg-amber-400',
  optional:    'bg-green-400',
};

/* ------------------------------------------------------------------ */
/* Node data shape passed through ReactFlow                           */
/* ------------------------------------------------------------------ */

export interface MindmapNodeData {
  node: MindmapNode;
  onClick: (node: MindmapNode) => void;
}

/* ------------------------------------------------------------------ */
/* Component                                                          */
/* ------------------------------------------------------------------ */

function MindmapNodeComponent({ data }: NodeProps<MindmapNodeData>) {
  const { node, onClick } = data;
  const style = NODE_STYLES[node.node_type] ?? NODE_STYLES.custom;
  const Icon = style.icon;

  const sectionParts: string[] = [];
  if (node.ipc_section) sectionParts.push(`IPC ${node.ipc_section}`);
  if (node.bns_section) sectionParts.push(`BNS ${node.bns_section}`);
  const sectionLabel = sectionParts.join(' / ');

  return (
    <div
      onClick={() => onClick(node)}
      className={`
        relative rounded-lg border-2 shadow-sm px-4 py-3 min-w-[200px] max-w-[280px]
        cursor-pointer transition-shadow hover:shadow-md
        ${style.bg} ${style.border}
        ${node.node_type === 'gap_from_fir' ? 'animate-pulse' : ''}
      `}
    >
      {/* Target handle (top) */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2 !h-2 !bg-slate-400 !border-0"
      />

      {/* Header row: icon + title + priority dot */}
      <div className="flex items-start gap-2">
        <Icon className="w-4 h-4 shrink-0 mt-0.5 text-slate-600" />
        <span className="text-sm font-medium leading-tight flex-1 text-slate-800">
          {node.title}
        </span>
        {/* Priority indicator */}
        <span
          className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${PRIORITY_DOT[node.priority]}`}
          title={`Priority: ${node.priority}`}
        />
      </div>

      {/* Footer row: section pill, status, disclaimer */}
      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
        {sectionLabel && (
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-white/70 border border-slate-200 text-slate-600">
            {sectionLabel}
          </span>
        )}

        {node.current_status && (
          <span className="flex items-center gap-1 text-[10px] text-slate-500">
            <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[node.current_status]}`} />
            {node.current_status.replace('_', ' ')}
          </span>
        )}

        {node.requires_disclaimer && (
          <span title="AI-generated — disclaimer applies">
            <Info className="w-3 h-3 text-amber-500 shrink-0" />
          </span>
        )}
      </div>

      {/* Source handle (bottom) */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2 !h-2 !bg-slate-400 !border-0"
      />
    </div>
  );
}

export default memo(MindmapNodeComponent);
