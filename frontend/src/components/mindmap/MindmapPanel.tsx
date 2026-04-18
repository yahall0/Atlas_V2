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
  useRegenerateMindmap,
  useAddCustomNode,
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
 * Simple tree layout: position nodes vertically.
 * Each top-level branch gets its own x column (300px apart).
 * Children stack below parents (120px per level).
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
      // Advance branch index past all descendants
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
}

export default function MindmapPanel({ firId }: MindmapPanelProps) {
  const { data: mindmap, isLoading, isError, error } = useMindmap(firId);
  const regenerate = useRegenerateMindmap(firId);

  const [view, setView] = useState<'tree' | 'checklist'>('tree');
  const [selectedNode, setSelectedNode] = useState<MindmapNode | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);

  const handleNodeClick = useCallback((node: MindmapNode) => {
    setSelectedNode(node);
  }, []);

  // Build ReactFlow layout
  const { nodes: rfNodes, edges: rfEdges } = useMemo(() => {
    if (!mindmap?.nodes) return { nodes: [], edges: [] };
    return layoutTree(mindmap.nodes, handleNodeClick, collapsed);
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
      {/* Disclaimer banner */}
      <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-yellow-600 shrink-0 mt-0.5" />
        <p className="text-xs text-yellow-800 leading-snug">
          Advisory — AI-generated suggestions. Investigating Officer retains
          full discretion. Not a substitute for legal judgment.
        </p>
      </div>

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
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setShowAddDialog(true)}
          title="Add Custom Node"
        >
          <Plus className="w-3.5 h-3.5" />
        </Button>

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
          <div className="flex flex-col items-center justify-center h-full gap-3 p-6">
            <p className="text-sm text-slate-500">
              No mindmap generated yet for this FIR.
            </p>
            <Button
              size="sm"
              onClick={handleRegenerate}
              disabled={regenerate.isPending}
            >
              <RefreshCw className="w-4 h-4 mr-1" />
              Generate Mindmap
            </Button>
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
