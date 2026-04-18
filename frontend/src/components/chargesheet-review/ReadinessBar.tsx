'use client';

import React, { useState } from 'react';
import {
  Scale,
  FileText,
  MessageSquare,
  ClipboardCheck,
  GitBranch,
  CheckCircle,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { Gap, GapCategory } from '@/hooks/chargesheet-gaps/useGapReport';

interface ReadinessBarProps {
  gaps: Gap[];
}

interface CategoryConfig {
  key: GapCategory;
  label: string;
  icon: React.ElementType;
}

const CATEGORIES: CategoryConfig[] = [
  { key: 'legal', label: 'Legal', icon: Scale },
  { key: 'evidence', label: 'Evidence', icon: FileText },
  { key: 'witness', label: 'Witness', icon: MessageSquare },
  { key: 'procedural', label: 'Procedural', icon: ClipboardCheck },
  { key: 'mindmap_divergence', label: 'Mindmap', icon: GitBranch },
  { key: 'completeness', label: 'Completeness', icon: CheckCircle },
];

type ReadinessStatus = 'clear' | 'warning' | 'critical';

function getCategoryStatus(gaps: Gap[], category: GapCategory): ReadinessStatus {
  const categoryGaps = gaps.filter(
    (g) => g.category === category && !g.current_action
  );
  if (categoryGaps.length === 0) return 'clear';
  const hasCriticalOrHigh = categoryGaps.some(
    (g) => g.severity === 'critical' || g.severity === 'high'
  );
  return hasCriticalOrHigh ? 'critical' : 'warning';
}

function StatusIcon({ status }: { status: ReadinessStatus }) {
  switch (status) {
    case 'clear':
      return (
        <CheckCircle2
          className="w-3.5 h-3.5 text-green-600"
          aria-hidden="true"
        />
      );
    case 'warning':
      return (
        <AlertTriangle
          className="w-3.5 h-3.5 text-amber-500"
          aria-hidden="true"
        />
      );
    case 'critical':
      return (
        <XCircle
          className="w-3.5 h-3.5 text-red-600"
          aria-hidden="true"
        />
      );
  }
}

function statusLabel(status: ReadinessStatus): string {
  switch (status) {
    case 'clear':
      return 'No open gaps';
    case 'warning':
      return 'Open gaps (no critical/high)';
    case 'critical':
      return 'Critical or high severity gaps';
  }
}

function statusPillClasses(status: ReadinessStatus): string {
  switch (status) {
    case 'clear':
      return 'bg-green-50 border-green-200 text-green-800';
    case 'warning':
      return 'bg-amber-50 border-amber-200 text-amber-800';
    case 'critical':
      return 'bg-red-50 border-red-200 text-red-800';
  }
}

export default function ReadinessBar({ gaps }: ReadinessBarProps) {
  const [hoveredCategory, setHoveredCategory] = useState<GapCategory | null>(
    null
  );

  return (
    <div className="relative flex items-center gap-2 flex-wrap" role="status" aria-label="Category readiness indicators">
      {CATEGORIES.map((cat) => {
        const status = getCategoryStatus(gaps, cat.key);
        const Icon = cat.icon;
        const categoryGaps = gaps.filter((g) => g.category === cat.key);
        const openCount = categoryGaps.filter((g) => !g.current_action).length;

        return (
          <div
            key={cat.key}
            className="relative"
            onMouseEnter={() => setHoveredCategory(cat.key)}
            onMouseLeave={() => setHoveredCategory(null)}
          >
            <button
              type="button"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs font-medium transition-colors ${statusPillClasses(status)}`}
              aria-label={`${cat.label}: ${statusLabel(status)}${openCount > 0 ? `, ${openCount} open` : ''}`}
            >
              <Icon className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{cat.label}</span>
              <StatusIcon status={status} />
              <span className="sr-only">{statusLabel(status)}</span>
            </button>

            {/* Popover on hover */}
            {hoveredCategory === cat.key && categoryGaps.length > 0 && (
              <div
                className="absolute top-full left-0 mt-1 z-50 w-72 bg-white border border-slate-200 rounded-lg shadow-lg p-3 space-y-1.5"
                role="tooltip"
              >
                <p className="text-xs font-semibold text-slate-700 mb-1.5">
                  {cat.label} Gaps ({categoryGaps.length})
                </p>
                {categoryGaps.slice(0, 8).map((g) => (
                  <div
                    key={g.id}
                    className="flex items-center gap-2 text-xs"
                  >
                    <SeverityDot severity={g.severity} />
                    <span className="truncate flex-1">{g.title}</span>
                    {g.current_action && (
                      <Badge
                        variant="secondary"
                        className="text-[10px] px-1.5 py-0 shrink-0"
                      >
                        {g.current_action}
                      </Badge>
                    )}
                  </div>
                ))}
                {categoryGaps.length > 8 && (
                  <p className="text-[10px] text-slate-400">
                    +{categoryGaps.length - 8} more
                  </p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function SeverityDot({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: 'bg-red-500',
    high: 'bg-orange-500',
    medium: 'bg-amber-400',
    low: 'bg-blue-400',
    advisory: 'bg-gray-400',
  };
  return (
    <span
      className={`w-2 h-2 rounded-full shrink-0 ${colors[severity] ?? 'bg-gray-300'}`}
      aria-hidden="true"
    />
  );
}
