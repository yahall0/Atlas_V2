'use client';

import React from 'react';
import { BookOpen } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

/**
 * Reference to a Delhi Police Academy Compendium scenario.
 *
 * Backend persists this on `firs.nlp_metadata.compendium_scenarios`
 * (per ADR-D19) and on individual gap entries
 * (per ADR-D20). Render anywhere a recommendation or playbook node
 * needs court-grade provenance.
 */
export interface CompendiumScenarioReference {
  scenario_id: string;
  scenario_name?: string;
  name?: string; // backend uses both keys; tolerate either
  page_start: number;
  page_end: number;
  applicable_sections?: string[];
}

interface PlaybookReferenceProps {
  references: CompendiumScenarioReference[];
  /** Compact mode renders only a small badge; expanded shows the scenario list. */
  compact?: boolean;
  className?: string;
}

const TITLE = 'Source: Delhi Police Academy — Compendium of Scenarios for Investigating Officers, 2024';

export function PlaybookReference({
  references,
  compact = false,
  className,
}: PlaybookReferenceProps) {
  if (!references || references.length === 0) return null;

  if (compact) {
    return (
      <Badge
        variant="outline"
        className={`gap-1 border-indigo-300 bg-indigo-50 text-indigo-800 ${className ?? ''}`}
        title={TITLE}
      >
        <BookOpen className="h-3 w-3" />
        Playbook · {references.length} scenario{references.length === 1 ? '' : 's'}
      </Badge>
    );
  }

  return (
    <div className={`rounded-md border border-indigo-200 bg-indigo-50/60 p-3 ${className ?? ''}`}>
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-indigo-900">
        <BookOpen className="h-4 w-4" />
        Investigation playbook reference
      </div>
      <ul className="space-y-1.5 text-sm text-indigo-900">
        {references.map((ref) => {
          const name = ref.scenario_name ?? ref.name ?? ref.scenario_id;
          return (
            <li key={ref.scenario_id} className="flex items-start justify-between gap-2">
              <span>
                <span className="font-medium">{name}</span>
                {ref.applicable_sections && ref.applicable_sections.length > 0 && (
                  <span className="ml-1.5 text-xs text-indigo-700">
                    ({ref.applicable_sections.join(', ')})
                  </span>
                )}
              </span>
              <span className="shrink-0 text-xs text-indigo-700">
                pp.{ref.page_start}–{ref.page_end}
              </span>
            </li>
          );
        })}
      </ul>
      <div className="mt-2 text-[11px] italic text-indigo-700/80">{TITLE}</div>
    </div>
  );
}

export default PlaybookReference;
