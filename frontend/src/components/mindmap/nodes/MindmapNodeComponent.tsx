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
  ChevronRight,
} from 'lucide-react';
import type { MindmapNode, NodeType, NodeStatusType, NodePriority } from './types';

/* ------------------------------------------------------------------ */
/* Visual variants                                                    */
/* ------------------------------------------------------------------ */

/**
 * The mindmap renders three visually-distinct node kinds:
 *
 *   - `hub`    – the centre "FIR {number} | {category}" pill. One per
 *                tree. Has source handles on both left and right.
 *   - `branch` – a primary topic box ("⚖️ Applicable BNS Sections" etc.).
 *                Has the type-coloured pastel background, an icon,
 *                and inward-facing handle towards the hub plus
 *                outward-facing handle towards its leaves.
 *   - `leaf`   – a terminal item ("BNS S.103 — Murder" etc.). Plain
 *                text with a small chevron and a single handle on the
 *                inward side.
 *
 * `side` tells the component whether the node sits on the left or right
 * of the centre hub (or is the centre itself), which determines on
 * which side its handles are placed.
 */
export type NodeKind = 'hub' | 'branch' | 'leaf';
export type NodeSide = 'left' | 'right' | 'center';

const NODE_STYLES: Record<NodeType, { bg: string; border: string; accent: string; icon: React.ElementType }> = {
  legal_section:    { bg: 'bg-blue-50',   border: 'border-blue-300',   accent: 'text-blue-600',   icon: Scale },
  immediate_action: { bg: 'bg-red-50',    border: 'border-red-300',    accent: 'text-red-600',    icon: Clock },
  evidence:         { bg: 'bg-green-50',  border: 'border-green-300',  accent: 'text-green-600',  icon: FileText },
  interrogation:    { bg: 'bg-purple-50', border: 'border-purple-300', accent: 'text-purple-600', icon: User },
  panchnama:        { bg: 'bg-amber-50',  border: 'border-amber-300',  accent: 'text-amber-600',  icon: ScrollText },
  forensic:         { bg: 'bg-teal-50',   border: 'border-teal-300',   accent: 'text-teal-600',   icon: FlaskConical },
  witness_bayan:    { bg: 'bg-indigo-50', border: 'border-indigo-300', accent: 'text-indigo-600', icon: MessageSquare },
  gap_from_fir:     { bg: 'bg-orange-50', border: 'border-orange-300', accent: 'text-orange-600', icon: AlertTriangle },
  custom:           { bg: 'bg-gray-50',   border: 'border-gray-300',   accent: 'text-gray-600',   icon: UserPlus },
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
  /** Visual kind. Defaults to `branch` when omitted (back-compat). */
  kind?: NodeKind;
  /** Which side of the hub this node sits on. Defaults to `right`. */
  side?: NodeSide;
}

/* ------------------------------------------------------------------ */
/* Hub variant — the centre "FIR {n} | {category}" pill               */
/* ------------------------------------------------------------------ */

function HubNode({ data }: { data: MindmapNodeData }) {
  const { node, onClick } = data;
  return (
    <div
      onClick={() => onClick(node)}
      className="
        relative rounded-full px-6 py-3 shadow-md
        bg-teal-500 text-white text-base font-semibold tracking-tight
        cursor-pointer transition-shadow hover:shadow-lg
        whitespace-nowrap
      "
    >
      {/* Source handles for both sides; edges pick the right one */}
      <Handle id="left"  type="source" position={Position.Left}  className="!w-2 !h-2 !bg-teal-300 !border-0" />
      <Handle id="right" type="source" position={Position.Right} className="!w-2 !h-2 !bg-teal-300 !border-0" />
      {node.title}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Branch variant — primary topic box                                 */
/* ------------------------------------------------------------------ */

function BranchNode({ data }: { data: MindmapNodeData }) {
  const { node, onClick, side = 'right' } = data;
  const style = NODE_STYLES[node.node_type] ?? NODE_STYLES.custom;
  const Icon = style.icon;

  // Inward handle (toward hub) + outward handle (toward leaves).
  const inward  = side === 'left' ? Position.Right : Position.Left;
  const outward = side === 'left' ? Position.Left  : Position.Right;

  return (
    <div
      onClick={() => onClick(node)}
      className={`
        relative rounded-xl border-2 shadow-sm px-4 py-2.5 min-w-[210px] max-w-[260px]
        cursor-pointer transition-shadow hover:shadow-md
        ${style.bg} ${style.border}
      `}
    >
      <Handle id="hub"  type="target" position={inward}  className="!w-2 !h-2 !bg-slate-400 !border-0" />
      <Handle id="leaf" type="source" position={outward} className="!w-2 !h-2 !bg-slate-400 !border-0" />

      <div className="flex items-center gap-2">
        <Icon className={`w-4 h-4 shrink-0 ${style.accent}`} />
        <span className="text-sm font-semibold leading-tight flex-1 text-slate-800">
          {node.title}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Leaf variant — terminal text item with chevron                     */
/* ------------------------------------------------------------------ */

function LeafNode({ data }: { data: MindmapNodeData }) {
  const { node, onClick, side = 'right' } = data;
  const inward = side === 'left' ? Position.Right : Position.Left;

  const sectionParts: string[] = [];
  if (node.ipc_section) sectionParts.push(`IPC ${node.ipc_section}`);
  if (node.bns_section) sectionParts.push(`BNS ${node.bns_section}`);
  const sectionLabel = sectionParts.join(' / ');

  // Right-side leaves: chevron sits at the front (between line and text).
  // Left-side leaves: chevron faces the other way and sits at the end.
  const chevronCls =
    side === 'left'
      ? 'order-2 rotate-180 text-slate-400'
      : 'order-0 text-slate-400';

  return (
    <div
      onClick={() => onClick(node)}
      className={`
        group relative px-2 py-1 cursor-pointer max-w-[260px]
        flex items-center gap-1.5
        ${side === 'left' ? 'flex-row-reverse text-right' : 'flex-row text-left'}
      `}
    >
      <Handle id="branch" type="target" position={inward} className="!w-1.5 !h-1.5 !bg-slate-300 !border-0" />

      <ChevronRight className={`w-3 h-3 shrink-0 ${chevronCls}`} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className={`text-[13px] leading-tight text-slate-700 group-hover:text-slate-900 ${
              node.current_status === 'addressed' ? 'line-through text-slate-400' : ''
            }`}
          >
            {node.title}
          </span>
          <span
            className={`w-1.5 h-1.5 rounded-full shrink-0 ${PRIORITY_DOT[node.priority]}`}
            title={`Priority: ${node.priority}`}
          />
          {node.current_status && (
            <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[node.current_status]}`} />
          )}
          {node.requires_disclaimer && (
            <Info className="w-3 h-3 text-amber-500 shrink-0" />
          )}
        </div>
        {sectionLabel && (
          <span className="text-[10px] font-medium text-slate-500 mt-0.5 block">
            {sectionLabel}
          </span>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Dispatch                                                           */
/* ------------------------------------------------------------------ */

function MindmapNodeComponent({ data }: NodeProps<MindmapNodeData>) {
  switch (data.kind) {
    case 'hub':    return <HubNode    data={data} />;
    case 'leaf':   return <LeafNode   data={data} />;
    case 'branch':
    default:       return <BranchNode data={data} />;
  }
}

export default memo(MindmapNodeComponent);
