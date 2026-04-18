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
import { Badge } from '@/components/ui/badge';
import {
  ChevronRight,
  ChevronDown,
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
  isDemoMindmap,
} from '@/hooks/mindmap/useMindmap';
import type { MindmapNode, NodeStatusType, NodePriority } from './nodes/types';

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
  const BRANCH_TO_LEAF_X = 290;      // horizontal distance branch → leaf
  const LEAF_VERTICAL_STEP = 38;     // vertical step between sibling leaves
  const MIN_SLOT_HEIGHT = 110;       // minimum vertical slot per branch
  const BRANCH_GAP = 28;             // padding between adjacent branch slots

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

const STATUS_DOT: Record<NodeStatusType, string> = {
  open: 'bg-gray-400',
  in_progress: 'bg-yellow-400',
  addressed: 'bg-green-500',
  not_applicable: 'bg-slate-400',
  disputed: 'bg-red-500',
};

const PRIORITY_LABEL: Record<NodePriority, string> = {
  critical: 'text-red-600',
  recommended: 'text-amber-600',
  optional: 'text-green-600',
};

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

  const toggleCollapse = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

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
          <div className="p-4 space-y-1">
            {flatNodes.map(({ node, depth }) => (
              <div
                key={node.id}
                className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-slate-50 cursor-pointer transition-colors"
                style={{ paddingLeft: `${depth * 24 + 8}px` }}
                onClick={() => handleNodeClick(node)}
              >
                {/* Collapse toggle for nodes with children */}
                {node.children.length > 0 ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleCollapse(node.id);
                    }}
                    className="text-slate-400 hover:text-slate-600"
                  >
                    {collapsed.has(node.id) ? (
                      <ChevronRight className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </button>
                ) : (
                  <span className="w-3.5" />
                )}

                {/* Status dot */}
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    STATUS_DOT[node.current_status ?? 'open']
                  }`}
                />

                {/* Title */}
                <span
                  className={`text-sm flex-1 ${
                    node.current_status === 'addressed'
                      ? 'line-through text-slate-400'
                      : 'text-slate-700'
                  }`}
                >
                  {node.title}
                </span>

                {/* Section pills */}
                {(node.ipc_section || node.bns_section) && (
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                    {[
                      node.ipc_section ? `IPC ${node.ipc_section}` : null,
                      node.bns_section ? `BNS ${node.bns_section}` : null,
                    ]
                      .filter(Boolean)
                      .join(' / ')}
                  </span>
                )}

                {/* Type badge */}
                <Badge variant="outline" className="text-[10px] capitalize">
                  {node.node_type.replace(/_/g, ' ')}
                </Badge>

                {/* Priority */}
                <span
                  className={`text-[10px] font-medium capitalize ${
                    PRIORITY_LABEL[node.priority]
                  }`}
                >
                  {node.priority}
                </span>
              </div>
            ))}

            {flatNodes.length === 0 && (
              <p className="text-sm text-slate-400 text-center py-8">
                No nodes found. Generate a mindmap to get started.
              </p>
            )}
          </div>
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
