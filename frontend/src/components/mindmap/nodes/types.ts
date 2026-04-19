export type NodeType =
  | 'legal_section'
  | 'immediate_action'
  | 'evidence'
  | 'interrogation'
  | 'panchnama'
  | 'forensic'
  | 'witness_bayan'
  | 'gap_from_fir'
  | 'custom';

export type NodeSource =
  | 'static_template'
  | 'ml_suggestion'
  | 'completeness_engine'
  | 'io_custom'
  | 'playbook';   // ADR-D19/D20: Delhi Police Academy Compendium scenario

export type NodePriority = 'critical' | 'recommended' | 'optional';

export type NodeStatusType =
  | 'open'
  | 'in_progress'
  | 'addressed'
  | 'not_applicable'
  | 'disputed';

export interface MindmapNode {
  id: string;
  mindmap_id: string;
  parent_id: string | null;
  node_type: NodeType;
  title: string;
  description_md: string | null;
  source: NodeSource;
  bns_section: string | null;
  ipc_section: string | null;
  crpc_section: string | null;
  priority: NodePriority;
  requires_disclaimer: boolean;
  display_order: number;
  metadata: Record<string, unknown>;
  current_status: NodeStatusType | null;
  /** Latest hash in this node's status chain. Echoed back as `hash_prev`
   *  on the next status PATCH so the audit chain stays continuous. */
  last_status_hash?: string | null;
  children: MindmapNode[];
}

export interface MindmapData {
  id: string;
  fir_id: string;
  case_category: string;
  template_version: string;
  generated_at: string;
  generated_by_model_version: string | null;
  root_node_id: string | null;
  status: 'active' | 'superseded';
  nodes: MindmapNode[];
  disclaimer: string;
}

export interface MindmapVersion {
  id: string;
  case_category: string;
  template_version: string;
  generated_at: string;
  status: 'active' | 'superseded';
  node_count: number;
}

export interface NodeStatusEntry {
  id: string;
  node_id: string;
  user_id: string;
  status: NodeStatusType;
  note: string | null;
  evidence_ref: string | null;
  updated_at: string;
  hash_prev: string;
  hash_self: string;
}
