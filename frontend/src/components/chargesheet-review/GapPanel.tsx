'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { AlertTriangle, Filter, ArrowUpDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import GapCard from './GapCard';
import type {
  Gap,
  GapSeverity,
  GapCategory,
  GapActionType,
} from '@/hooks/chargesheet-gaps/useGapReport';
import { useGapAction } from '@/hooks/chargesheet-gaps/useGapReport';

// ─── Props ──────────────────────────────────────────────────────────────────

interface GapPanelProps {
  chargesheetId: string;
  gaps: Gap[];
  onJumpToDocument?: (gap: Gap) => void;
}

// ─── Filter / sort types ────────────────────────────────────────────────────

type SortField = 'display_order' | 'severity' | 'category' | 'confidence';
type SortDirection = 'asc' | 'desc';

const SEVERITY_ORDER: Record<GapSeverity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  advisory: 4,
};

const SEVERITY_OPTIONS: { value: GapSeverity | 'all'; label: string }[] = [
  { value: 'all', label: 'All severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
  { value: 'advisory', label: 'Advisory' },
];

const CATEGORY_OPTIONS: { value: GapCategory | 'all'; label: string }[] = [
  { value: 'all', label: 'All categories' },
  { value: 'legal', label: 'Legal' },
  { value: 'evidence', label: 'Evidence' },
  { value: 'witness', label: 'Witness' },
  { value: 'procedural', label: 'Procedural' },
  { value: 'mindmap_divergence', label: 'Mindmap' },
  { value: 'completeness', label: 'Completeness' },
  // ADR-D20: Compendium playbook gap categories
  { value: 'playbook_form_missing', label: 'Playbook · Form' },
  { value: 'playbook_evidence_missing', label: 'Playbook · Evidence' },
  { value: 'playbook_deadline_reminder', label: 'Playbook · Deadline' },
];

const SOURCE_OPTIONS: { value: string; label: string }[] = [
  { value: 'all', label: 'All sources' },
  { value: 'T54', label: 'T54' },
  { value: 'T55', label: 'T55' },
  { value: 'mindmap', label: 'Mindmap' },
  { value: 'completeness', label: 'Completeness' },
  { value: 'compendium_playbook', label: 'Compendium playbook' },
  { value: 'manual', label: 'Manual' },
];

const SORT_OPTIONS: { value: SortField; label: string }[] = [
  { value: 'display_order', label: 'Default order' },
  { value: 'severity', label: 'Severity' },
  { value: 'category', label: 'Category' },
  { value: 'confidence', label: 'Confidence' },
];

// ─── Severity distribution bar segment ──────────────────────────────────────

const SEVERITY_BAR_COLORS: Record<GapSeverity, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-amber-400',
  low: 'bg-blue-400',
  advisory: 'bg-gray-300',
};

// ─── Component ──────────────────────────────────────────────────────────────

export default function GapPanel({
  chargesheetId,
  gaps,
  onJumpToDocument,
}: GapPanelProps) {
  // Filters
  const [severityFilter, setSeverityFilter] = useState<GapSeverity | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<GapCategory | 'all'>('all');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [sortField, setSortField] = useState<SortField>('display_order');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Bulk selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkAction, setBulkAction] = useState<GapActionType | ''>('');
  const gapAction = useGapAction(chargesheetId);

  // Filter + sort
  const filteredGaps = useMemo(() => {
    let result = [...gaps];

    if (severityFilter !== 'all') {
      result = result.filter((g) => g.severity === severityFilter);
    }
    if (categoryFilter !== 'all') {
      result = result.filter((g) => g.category === categoryFilter);
    }
    if (sourceFilter !== 'all') {
      result = result.filter((g) => g.source === sourceFilter);
    }

    result.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'severity':
          cmp = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
          break;
        case 'category':
          cmp = a.category.localeCompare(b.category);
          break;
        case 'confidence':
          cmp = b.confidence - a.confidence;
          break;
        case 'display_order':
        default:
          cmp = a.display_order - b.display_order;
          break;
      }
      return sortDirection === 'desc' ? -cmp : cmp;
    });

    return result;
  }, [gaps, severityFilter, categoryFilter, sourceFilter, sortField, sortDirection]);

  // Severity counts for the distribution bar
  const severityCounts = useMemo(() => {
    const counts: Record<GapSeverity, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      advisory: 0,
    };
    for (const g of gaps) {
      counts[g.severity]++;
    }
    return counts;
  }, [gaps]);

  const toggleSelect = useCallback((gapId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(gapId)) {
        next.delete(gapId);
      } else {
        next.add(gapId);
      }
      return next;
    });
  }, []);

  const handleBulkAction = useCallback(async () => {
    if (!bulkAction || selectedIds.size === 0) return;
    const promises = Array.from(selectedIds).map((gapId) =>
      gapAction.mutateAsync({
        gapId,
        action: bulkAction,
        hash_prev: 'GENESIS', // Simplified for bulk
      })
    );
    try {
      await Promise.allSettled(promises);
      setSelectedIds(new Set());
      setBulkAction('');
    } catch {
      // Errors handled by individual mutations
    }
  }, [bulkAction, selectedIds, gapAction]);

  return (
    <div className="flex flex-col h-full">
      {/* ── Disclaimer Banner (non-dismissable) ─────────────────────────── */}
      <div
        className="bg-yellow-50 border border-yellow-300 rounded-md px-4 py-3 mb-3 shrink-0"
        role="alert"
        aria-live="polite"
      >
        <div className="flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-yellow-600 mt-0.5 shrink-0" aria-hidden="true" />
          <p className="text-xs text-yellow-800 leading-relaxed">
            <span className="font-semibold">Advisory</span> — AI-assisted
            review. Investigating Officer retains full legal responsibility.
            Not a substitute for legal judgment or supervisor review.
          </p>
        </div>
      </div>

      {/* ── Header: counts + distribution bar ────────────────────────────── */}
      <div className="space-y-2 shrink-0 mb-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800">
            Gaps ({filteredGaps.length}
            {filteredGaps.length !== gaps.length && ` of ${gaps.length}`})
          </h3>
        </div>

        {/* Severity distribution bar */}
        {gaps.length > 0 && (
          <div className="space-y-1">
            <div className="flex h-2.5 rounded-full overflow-hidden bg-slate-100">
              {(
                ['critical', 'high', 'medium', 'low', 'advisory'] as GapSeverity[]
              ).map((sev) => {
                const pct = (severityCounts[sev] / gaps.length) * 100;
                if (pct === 0) return null;
                return (
                  <div
                    key={sev}
                    className={`${SEVERITY_BAR_COLORS[sev]} transition-all`}
                    style={{ width: `${pct}%` }}
                    title={`${sev}: ${severityCounts[sev]}`}
                    aria-label={`${sev}: ${severityCounts[sev]} gaps`}
                  />
                );
              })}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-500">
              {(
                ['critical', 'high', 'medium', 'low', 'advisory'] as GapSeverity[]
              ).map((sev) =>
                severityCounts[sev] > 0 ? (
                  <span key={sev} className="flex items-center gap-1">
                    <span
                      className={`w-2 h-2 rounded-full ${SEVERITY_BAR_COLORS[sev]}`}
                      aria-hidden="true"
                    />
                    {sev}: {severityCounts[sev]}
                  </span>
                ) : null
              )}
            </div>
          </div>
        )}

        {/* ── Filters ──────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />

          <select
            className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white focus:ring-2 focus:ring-blue-400"
            value={severityFilter}
            onChange={(e) =>
              setSeverityFilter(e.target.value as GapSeverity | 'all')
            }
            aria-label="Filter by severity"
          >
            {SEVERITY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>

          <select
            className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white focus:ring-2 focus:ring-blue-400"
            value={categoryFilter}
            onChange={(e) =>
              setCategoryFilter(e.target.value as GapCategory | 'all')
            }
            aria-label="Filter by category"
          >
            {CATEGORY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>

          <select
            className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white focus:ring-2 focus:ring-blue-400"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            aria-label="Filter by source"
          >
            {SOURCE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>

          <div className="flex items-center gap-1 ml-auto">
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
            <select
              className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white focus:ring-2 focus:ring-blue-400"
              value={sortField}
              onChange={(e) => setSortField(e.target.value as SortField)}
              aria-label="Sort by"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="text-xs text-slate-400 hover:text-slate-600 px-1"
              onClick={() =>
                setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'))
              }
              aria-label={`Sort direction: ${sortDirection === 'asc' ? 'ascending' : 'descending'}. Click to toggle.`}
            >
              {sortDirection === 'asc' ? '\u2191' : '\u2193'}
            </button>
          </div>
        </div>

        {/* ── Bulk actions ─────────────────────────────────────────────────── */}
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-md px-3 py-2">
            <Badge variant="secondary" className="text-xs">
              {selectedIds.size} selected
            </Badge>
            <select
              className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white"
              value={bulkAction}
              onChange={(e) =>
                setBulkAction(e.target.value as GapActionType | '')
              }
              aria-label="Bulk action to apply"
            >
              <option value="">Select action...</option>
              <option value="accepted">Accept</option>
              <option value="modified">Modify</option>
              <option value="dismissed">Dismiss</option>
              <option value="deferred">Defer</option>
              <option value="escalated">Escalate</option>
            </select>
            <Button
              size="sm"
              className="h-7 text-xs"
              disabled={!bulkAction || gapAction.isPending}
              onClick={handleBulkAction}
              aria-label="Apply bulk action to selected gaps"
            >
              {gapAction.isPending ? 'Applying...' : 'Apply'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={() => setSelectedIds(new Set())}
              aria-label="Clear selection"
            >
              Clear
            </Button>
          </div>
        )}
      </div>

      {/* ── Gap cards list ───────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto space-y-2 min-h-0 pr-1">
        {filteredGaps.length === 0 && (
          <div className="flex items-center justify-center h-32 text-sm text-slate-400">
            No gaps match the current filters.
          </div>
        )}
        {filteredGaps.map((gap) => (
          <GapCard
            key={gap.id}
            gap={gap}
            chargesheetId={chargesheetId}
            onJumpToDocument={onJumpToDocument}
            onActionComplete={() => {
              // Handled by query invalidation in the hooks
            }}
            selected={selectedIds.has(gap.id)}
            onSelectToggle={toggleSelect}
          />
        ))}
      </div>
    </div>
  );
}
