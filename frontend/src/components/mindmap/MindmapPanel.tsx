'use client';

import { useCallback, useMemo, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeTypes,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { Button } from '@/components/ui/button';
import {
  Download,
  RefreshCw,
  Plus,
  List,
  GitBranch,
  X,
  AlertTriangle,
} from 'lucide-react';

import MindmapNodeComponent, {
  type MindmapNodeData,
} from './nodes/MindmapNodeComponent';
import NodeDetailDrawer from './NodeDetailDrawer';
import {
  useMindmap,
  useGenerateMindmap,
  useRegenerateMindmap,
  useAddCustomNode,
  useUpdateNodeStatus,
  isDemoMindmap,
} from '@/hooks/mindmap/useMindmap';
import type { MindmapNode, NodeStatusType, NodePriority } from './nodes/types';
// NodeStatusType retained — used by ChecklistView for status transitions.
void (null as unknown as NodeStatusType);

/* ------------------------------------------------------------------ */
/* ReactFlow node type map                                            */
/* ------------------------------------------------------------------ */

const nodeTypes: NodeTypes = {
  mindmapNode: MindmapNodeComponent,
};

/* ------------------------------------------------------------------ */
/* Layout helpers                                                     */
/* ------------------------------------------------------------------ */

interface LayoutInfo {
  nodes: Node<MindmapNodeData>[];
  edges: Edge[];
}

/**
 * Horizontal mindmap layout — matches the classic centre-hub style.
 *
 *   - Single root ("hub") sits at the origin.
 *   - Primary branches are split evenly into a left half and a right
 *     half (first half goes left, second half goes right) and stacked
 *     vertically on each side.
 *   - Each branch's leaves stack vertically next to it, extending
 *     further outward.
 *   - Each branch is given a vertical *slot height* proportional to
 *     its leaf count, then the slots are stacked with a fixed gap.
 *     Total side height is centred on the hub.
 *
 * This guarantees no overlap regardless of how many leaves a branch
 * has, because each branch reserves enough vertical space for its
 * own leaves before the next branch's slot begins.
 *
 * Falls back to the column tree layout for trees with multiple roots.
 */
function layoutHorizontalMindmap(
  roots: MindmapNode[],
  onClick: (node: MindmapNode) => void,
  collapsed: Set<string>
): LayoutInfo {
  if (roots.length === 0) return { nodes: [], edges: [] };
  if (roots.length > 1) {
    return layoutTree(roots, onClick, collapsed);
  }

  // Geometry constants. Tweaked so even the largest categories
  // (Murder, Cyber) fit in a screenful at fitView padding 0.15.
  const HUB_TO_BRANCH_X = 320;       // horizontal distance hub → branch
  const BRANCH_TO_LEAF_X = 320;      // horizontal distance branch → leaf
  // Leaves now render single-line (truncated). 32 px is comfortable for
  // a single text line at text-[13px]; previously 38 was tuned for
  // two-line wraps but those have been disabled.
  const LEAF_VERTICAL_STEP = 32;
  const MIN_SLOT_HEIGHT = 110;       // minimum vertical slot per branch
  const BRANCH_GAP = 32;             // padding between adjacent branch slots

  const nodes: Node<MindmapNodeData>[] = [];
  const edges: Edge[] = [];

  const root = roots[0];

  // Hub at origin
  nodes.push({
    id: root.id,
    type: 'mindmapNode',
    position: { x: 0, y: 0 },
    data: { node: root, onClick, kind: 'hub', side: 'center' },
  });

  if (collapsed.has(root.id)) return { nodes, edges };

  // Split primary branches: first half left, second half right, in the
  // order the demo / generator emitted them.
  const primary = [...root.children].sort(
    (a, b) => a.display_order - b.display_order
  );
  const half = Math.ceil(primary.length / 2);
  const leftBranches  = primary.slice(0, half);
  const rightBranches = primary.slice(half);

  layoutSide('left',  leftBranches);
  layoutSide('right', rightBranches);

  return { nodes, edges };

  // ── side helper ─────────────────────────────────────────────────────────
  function layoutSide(side: 'left' | 'right', branches: MindmapNode[]) {
    if (branches.length === 0) return;
    const sign = side === 'left' ? -1 : 1;
    const branchX = sign * HUB_TO_BRANCH_X;
    const leafX   = sign * (HUB_TO_BRANCH_X + BRANCH_TO_LEAF_X);

    // Compute each branch's slot height from its leaf count. A branch
    // with N leaves needs at least (N * step) vertical space.
    const slotHeights = branches.map((b) => {
      const leafCount = collapsed.has(b.id) ? 0 : b.children.length;
      return Math.max(MIN_SLOT_HEIGHT, leafCount * LEAF_VERTICAL_STEP + 16);
    });

    const totalHeight =
      slotHeights.reduce((s, h) => s + h, 0) +
      (branches.length - 1) * BRANCH_GAP;

    // Centre the stack vertically on the hub.
    let cursorY = -totalHeight / 2;

    branches.forEach((branch, i) => {
      const slotH = slotHeights[i];
      const branchY = cursorY + slotH / 2;

      // Branch box
      nodes.push({
        id: branch.id,
        type: 'mindmapNode',
        position: { x: branchX, y: branchY },
        data: { node: branch, onClick, kind: 'branch', side },
      });

      // Hub → Branch edge: thick coloured Bezier, picks the hub's
      // left/right source handle so the curve emerges from the right side.
      edges.push({
        id: `e-${root.id}-${branch.id}`,
        source: root.id,
        sourceHandle: side,
        target: branch.id,
        targetHandle: 'hub',
        type: 'default', // bezier
        animated: branch.node_type === 'gap_from_fir',
        style: {
          stroke: branchEdgeColor(branch.node_type),
          strokeWidth: 3,
        },
      });

      // Leaves of this branch — stacked vertically next to it, centred
      // on the branch's Y so the layout stays balanced.
      if (!collapsed.has(branch.id)) {
        const leaves = [...branch.children].sort(
          (a, b) => a.display_order - b.display_order
        );
        const M = leaves.length;
        const leavesTop = branchY - ((M - 1) * LEAF_VERTICAL_STEP) / 2;

        leaves.forEach((leaf, li) => {
          const ly = leavesTop + li * LEAF_VERTICAL_STEP;

          nodes.push({
            id: leaf.id,
            type: 'mindmapNode',
            position: { x: leafX, y: ly },
            data: { node: leaf, onClick, kind: 'leaf', side },
          });

          edges.push({
            id: `e-${branch.id}-${leaf.id}`,
            source: branch.id,
            sourceHandle: 'leaf',
            target: leaf.id,
            targetHandle: 'branch',
            type: 'smoothstep',
            style: { stroke: '#cbd5e1', strokeWidth: 1.2 },
          });
        });
      }

      cursorY += slotH + BRANCH_GAP;
    });
  }
}

/** Trunk colour per branch type — matches the pastel palette in
 *  MindmapNodeComponent so the curve fades into the branch box. */
function branchEdgeColor(t: MindmapNode['node_type']): string {
  switch (t) {
    case 'legal_section':    return '#3b82f6'; // blue-500
    case 'immediate_action': return '#ef4444'; // red-500
    case 'panchnama':        return '#f59e0b'; // amber-500
    case 'evidence':         return '#22c55e'; // green-500
    case 'forensic':         return '#14b8a6'; // teal-500
    case 'witness_bayan':    return '#6366f1'; // indigo-500
    case 'gap_from_fir':     return '#f97316'; // orange-500
    default:                 return '#94a3b8'; // slate-400
  }
}

/**
 * Simple column tree layout — kept for the multi-root fallback case.
 */
function layoutTree(
  roots: MindmapNode[],
  onClick: (node: MindmapNode) => void,
  collapsed: Set<string>
): LayoutInfo {
  const nodes: Node<MindmapNodeData>[] = [];
  const edges: Edge[] = [];
  let branchIndex = 0;

  function walk(node: MindmapNode, depth: number, xBase: number) {
    nodes.push({
      id: node.id,
      type: 'mindmapNode',
      position: { x: xBase, y: depth * 140 },
      data: { node, onClick },
    });

    if (node.parent_id) {
      edges.push({
        id: `e-${node.parent_id}-${node.id}`,
        source: node.parent_id,
        target: node.id,
        type: 'smoothstep',
        animated: node.node_type === 'gap_from_fir',
        style: { stroke: '#94a3b8', strokeWidth: 1.5 },
      });
    }

    if (collapsed.has(node.id)) return;

    const children = [...node.children].sort(
      (a, b) => a.display_order - b.display_order
    );
    children.forEach((child, ci) => {
      walk(child, depth + 1, xBase + ci * 300);
    });
  }

  roots
    .sort((a, b) => a.display_order - b.display_order)
    .forEach((root) => {
      walk(root, 0, branchIndex * 300);
      branchIndex += countLeaves(root, collapsed);
    });

  return { nodes, edges };
}

function countLeaves(node: MindmapNode, collapsed: Set<string>): number {
  if (collapsed.has(node.id) || node.children.length === 0) return 1;
  return node.children.reduce(
    (sum, c) => sum + countLeaves(c, collapsed),
    0
  );
}

/* ------------------------------------------------------------------ */
/* Checklist helpers                                                   */
/* ------------------------------------------------------------------ */

interface FlatNode {
  node: MindmapNode;
  depth: number;
}

function flattenTree(nodes: MindmapNode[], depth: number = 0): FlatNode[] {
  const result: FlatNode[] = [];
  for (const n of nodes.sort((a, b) => a.display_order - b.display_order)) {
    result.push({ node: n, depth });
    result.push(...flattenTree(n.children, depth + 1));
  }
  return result;
}

/* ------------------------------------------------------------------ */
/* Status helpers                                                     */
/* ------------------------------------------------------------------ */

const PRIORITY_LABEL: Record<NodePriority, string> = {
  critical: 'text-red-600',
  recommended: 'text-amber-600',
  optional: 'text-green-600',
};

/* ------------------------------------------------------------------ */
/* Checklist view — checkbox-driven, multi-line wrapping              */
/* ------------------------------------------------------------------ */

const NODE_TYPE_PILL: Record<string, string> = {
  legal_section: 'bg-teal-50 text-teal-700 border-teal-200',
  immediate_action: 'bg-rose-50 text-rose-700 border-rose-200',
  evidence: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  panchnama: 'bg-amber-50 text-amber-700 border-amber-200',
  forensic: 'bg-violet-50 text-violet-700 border-violet-200',
  witness_bayan: 'bg-sky-50 text-sky-700 border-sky-200',
  gap_from_fir: 'bg-red-50 text-red-700 border-red-200',
  interrogation: 'bg-orange-50 text-orange-700 border-orange-200',
  custom: 'bg-slate-50 text-slate-600 border-slate-200',
};

function ChecklistView({
  firId,
  flatNodes,
  onItemClick,
}: {
  firId: string;
  flatNodes: FlatNode[];
  onItemClick: (n: MindmapNode) => void;
}) {
  const updateStatus = useUpdateNodeStatus(firId);

  const toggleAddressed = useCallback(
    (node: MindmapNode) => {
      const next: NodeStatusType =
        node.current_status === 'addressed' ? 'open' : 'addressed';
      updateStatus.mutate({
        nodeId: node.id,
        status: next,
        // Echo back the latest status-chain hash so the audit chain stays
        // continuous. Falls back to "GENESIS" when no prior status exists.
        hash_prev: node.last_status_hash ?? 'GENESIS',
      });
    },
    [updateStatus],
  );

  if (flatNodes.length === 0) {
    return (
      <p className="p-6 text-sm text-slate-400 text-center">
        No nodes found. Generate a mindmap to get started.
      </p>
    );
  }

  // Total visible checklist items (leaves only)
  const checkable = flatNodes.filter((f) => f.node.children.length === 0);
  const completed = checkable.filter((f) => f.node.current_status === 'addressed').length;

  return (
    <div className="p-4 space-y-3">
      <div className="sticky top-0 z-10 -mx-4 px-4 py-2 bg-white/95 backdrop-blur border-b text-xs text-slate-500 flex items-center justify-between">
        <span>
          <span className="font-semibold text-slate-700">{completed}</span>
          {' / '}
          <span className="font-semibold text-slate-700">{checkable.length}</span>
          {' items addressed'}
        </span>
        <span className="text-[10px] text-slate-400">
          tap the checkbox to mark complete · click the row for details
        </span>
      </div>

      <ul className="space-y-1.5">
        {flatNodes.map(({ node, depth }) => {
          const isLeaf = node.children.length === 0;
          const isAddressed = node.current_status === 'addressed';
          const pillCls = NODE_TYPE_PILL[node.node_type] ?? NODE_TYPE_PILL.custom;

          return (
            <li
              key={node.id}
              className={`group flex items-start gap-3 rounded-md border ${
                isAddressed ? 'border-slate-100 bg-slate-50/40' : 'border-slate-200 bg-white'
              } px-3 py-2 transition-colors hover:bg-slate-50`}
              style={{ marginLeft: `${depth * 16}px` }}
            >
              {/* Checkbox — only for leaves; non-leaves get an opaque bullet so
                  the indent reads as a hierarchy. */}
              {isLeaf ? (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleAddressed(node);
                  }}
                  aria-label={isAddressed ? 'Mark as not done' : 'Mark as done'}
                  className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded border transition-colors ${
                    isAddressed
                      ? 'border-emerald-500 bg-emerald-500 text-white'
                      : 'border-slate-300 bg-white hover:border-slate-500'
                  }`}
                  disabled={updateStatus.isPending}
                >
                  {isAddressed && (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 16 16"
                      fill="currentColor"
                      className="h-3 w-3"
                    >
                      <path d="M13.485 4.43a.75.75 0 0 1 0 1.061l-6 6a.75.75 0 0 1-1.06 0l-3-3a.75.75 0 1 1 1.06-1.061L7 9.939l5.424-5.51a.75.75 0 0 1 1.06 0Z" />
                    </svg>
                  )}
                </button>
              ) : (
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
              )}

              {/* Title + meta — wraps freely; pills sit below on narrow widths */}
              <div className="min-w-0 flex-1 cursor-pointer" onClick={() => onItemClick(node)}>
                <p
                  className={`whitespace-normal break-words text-sm leading-snug ${
                    isAddressed
                      ? 'text-slate-400 line-through'
                      : 'text-slate-800'
                  }`}
                >
                  {node.title}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[10px] font-medium capitalize ${pillCls}`}
                  >
                    {node.node_type.replace(/_/g, ' ')}
                  </span>
                  <span
                    className={`text-[10px] font-medium capitalize ${PRIORITY_LABEL[node.priority]}`}
                  >
                    {node.priority}
                  </span>
                  {(node.ipc_section || node.bns_section) && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                      {[
                        node.ipc_section ? `IPC ${node.ipc_section}` : null,
                        node.bns_section ? `BNS ${node.bns_section}` : null,
                      ]
                        .filter(Boolean)
                        .join(' / ')}
                    </span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Add Custom Node Dialog (simple inline)                             */
/* ------------------------------------------------------------------ */

function AddNodeDialog({
  firId,
  onDone,
}: {
  firId: string;
  onDone: () => void;
}) {
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const addNode = useAddCustomNode(firId);

  const handleAdd = async () => {
    if (!title.trim()) return;
    await addNode.mutateAsync({
      title: title.trim(),
      description_md: desc || undefined,
      node_type: 'custom',
      priority: 'optional',
    });
    onDone();
  };

  return (
    <div className="border rounded-lg p-4 mb-4 bg-white shadow space-y-3">
      <p className="text-sm font-semibold text-slate-700">Add Custom Node</p>
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Node title"
        className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <textarea
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
        placeholder="Description (optional)"
        rows={2}
        className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <div className="flex gap-2">
        <Button size="sm" onClick={handleAdd} disabled={addNode.isPending}>
          {addNode.isPending ? 'Adding...' : 'Add'}
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
      {addNode.isError && (
        <p className="text-sm text-red-600">Failed to add node.</p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Panel                                                         */
/* ------------------------------------------------------------------ */

interface MindmapPanelProps {
  firId: string;
  /** FIR's nlp_classification — picks the right demo mindmap when the
   *  backend has no real one yet. Optional; the generic demo is used
   *  as fallback. */
  caseCategory?: string | null;
  /** FIR registration number — appears in the centre hub of the demo
   *  mindmap ("FIR 11192050250010 | Murder"). Optional. */
  firNumber?: string | null;
}

export default function MindmapPanel({
  firId,
  caseCategory,
  firNumber,
}: MindmapPanelProps) {
  const { data: mindmap, isLoading, isError, error } = useMindmap(firId, {
    caseCategory,
    firNumber,
  });
  const regenerate = useRegenerateMindmap(firId);
  const generate = useGenerateMindmap(firId);
  const showingDemo = isDemoMindmap(mindmap);

  const [view, setView] = useState<'tree' | 'checklist'>('tree');
  const [selectedNode, setSelectedNode] = useState<MindmapNode | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);

  const handleNodeClick = useCallback((node: MindmapNode) => {
    setSelectedNode(node);
  }, []);

  // Build ReactFlow layout — centre-hub radial: root in middle, primary
  // branches in a ring around it, leaves fanning outward along each
  // branch axis.
  const { nodes: rfNodes, edges: rfEdges } = useMemo(() => {
    if (!mindmap?.nodes) return { nodes: [], edges: [] };
    return layoutHorizontalMindmap(mindmap.nodes, handleNodeClick, collapsed);
  }, [mindmap, handleNodeClick, collapsed]);

  // Flat nodes for checklist
  const flatNodes = useMemo(() => {
    if (!mindmap?.nodes) return [];
    return flattenTree(mindmap.nodes);
  }, [mindmap]);

  const expandAll = () => setCollapsed(new Set());

  const collapseAll = () => {
    if (!mindmap?.nodes) return;
    const ids = new Set<string>();
    function collect(nodes: MindmapNode[]) {
      for (const n of nodes) {
        if (n.children.length > 0) ids.add(n.id);
        collect(n.children);
      }
    }
    collect(mindmap.nodes);
    setCollapsed(ids);
  };

  // (toggleCollapse retained when checklist still used expand/collapse;
  // checkbox-driven ChecklistView no longer needs it. Kept inline-only
  // for the tree view's collapse-all/expand-all controls.)

  const handleRegenerate = () => {
    const justification = prompt('Provide a justification for regeneration:');
    if (justification) {
      regenerate.mutate(justification);
    }
  };

  // First-time generation needs no justification — just POST and the
  // backend builds the mindmap from FIR + KB. The toolbar regenerate
  // button (which prompts for a justification) is reserved for replacing
  // an existing mindmap with a new version.
  const handleFirstGenerate = () => {
    generate.mutate();
  };

  if (!panelOpen) {
    return (
      <div className="flex items-start">
        <Button
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => setPanelOpen(true)}
        >
          <GitBranch className="w-4 h-4 mr-1" />
          Mindmap
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full border rounded-lg bg-white shadow-sm overflow-hidden">
      {/* Disclaimer banner — switches copy when running on the static demo */}
      {showingDemo ? (
        <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
          <p className="text-xs text-blue-800 leading-snug">
            <span className="font-semibold">Demo data</span> — showing a static
            per-category mindmap for{' '}
            <span className="font-mono">
              {mindmap?.case_category ?? caseCategory ?? 'generic'}
            </span>
            . Will be replaced by KB-driven content once the live 3-layer KB
            is wired to this FIR.
          </p>
        </div>
      ) : (
        <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-yellow-600 shrink-0 mt-0.5" />
          <p className="text-xs text-yellow-800 leading-snug">
            Advisory — AI-generated suggestions. Investigating Officer retains
            full discretion. Not a substitute for legal judgment.
          </p>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-1.5 px-3 py-2 border-b flex-wrap">
        <Button size="sm" variant="ghost" onClick={expandAll}>
          Expand All
        </Button>
        <Button size="sm" variant="ghost" onClick={collapseAll}>
          Collapse All
        </Button>

        <div className="h-5 w-px bg-slate-200 mx-1" />

        <Button
          size="sm"
          variant={view === 'tree' ? 'secondary' : 'ghost'}
          onClick={() => setView('tree')}
        >
          <GitBranch className="w-3.5 h-3.5 mr-1" />
          Tree
        </Button>
        <Button
          size="sm"
          variant={view === 'checklist' ? 'secondary' : 'ghost'}
          onClick={() => setView('checklist')}
        >
          <List className="w-3.5 h-3.5 mr-1" />
          Checklist
        </Button>

        <div className="h-5 w-px bg-slate-200 mx-1" />

        <Button size="sm" variant="ghost" title="Export PDF">
          <Download className="w-3.5 h-3.5" />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={handleRegenerate}
          disabled={regenerate.isPending}
          title="Regenerate"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${regenerate.isPending ? 'animate-spin' : ''}`}
          />
        </Button>
        {!showingDemo && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setShowAddDialog(true)}
            title="Add Custom Node"
          >
            <Plus className="w-3.5 h-3.5" />
          </Button>
        )}

        <div className="flex-1" />

        <Button
          size="sm"
          variant="ghost"
          onClick={() => setPanelOpen(false)}
          title="Close panel"
        >
          <X className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* Add node dialog */}
      {showAddDialog && (
        <div className="px-3 pt-3">
          <AddNodeDialog
            firId={firId}
            onDone={() => setShowAddDialog(false)}
          />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto relative">
        {isLoading && (
          <div className="flex items-center justify-center h-full">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {isError && (
          <div className="flex flex-col items-center justify-center h-full gap-3 p-6">
            <p className="text-sm text-red-600">
              {(error as Error)?.message ?? 'Failed to load mindmap.'}
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => window.location.reload()}
            >
              Retry
            </Button>
          </div>
        )}

        {mindmap && !isLoading && !isError && view === 'tree' && (
          <div className="w-full h-full min-h-[500px]">
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              proOptions={{ hideAttribution: true }}
              minZoom={0.2}
              maxZoom={1.5}
            >
              <Background gap={20} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
        )}

        {mindmap && !isLoading && !isError && view === 'checklist' && (
          <ChecklistView
            firId={firId}
            flatNodes={flatNodes}
            onItemClick={handleNodeClick}
          />
        )}

        {!mindmap && !isLoading && !isError && (
          <div className="flex flex-col items-center justify-center h-full gap-3 p-6 text-center">
            <p className="text-sm text-slate-500">
              No mindmap generated yet for this FIR.
            </p>
            <p className="text-xs text-slate-400 max-w-xs">
              The first generation pulls applicable BNS sections,
              investigation playbook (panchnama, evidence, bayan, blood
              forensics), and case-law standards from the 3-layer KB.
            </p>
            <Button
              size="sm"
              onClick={handleFirstGenerate}
              disabled={generate.isPending}
            >
              <RefreshCw
                className={`w-4 h-4 mr-1 ${generate.isPending ? 'animate-spin' : ''}`}
              />
              {generate.isPending ? 'Generating…' : 'Generate Mindmap'}
            </Button>
            {generate.isError && (
              <p className="text-xs text-red-600 max-w-xs">
                {(generate.error as Error)?.message ?? 'Generation failed.'}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Node detail drawer */}
      <NodeDetailDrawer
        node={selectedNode}
        firId={firId}
        onClose={() => setSelectedNode(null)}
        onStatusUpdate={() => setSelectedNode(null)}
      />
    </div>
  );
}
