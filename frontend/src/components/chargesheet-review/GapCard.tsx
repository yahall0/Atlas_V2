'use client';

import React, { useState, useCallback } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Bot,
  Clock,
  User,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  useGapAction,
  useGapHistory,
  useApplySuggestion,
} from '@/hooks/chargesheet-gaps/useGapReport';
import type {
  Gap,
  GapActionType,
  GapAction,
  GapSeverity,
  GapCategory,
} from '@/hooks/chargesheet-gaps/useGapReport';

// ─── Props ──────────────────────────────────────────────────────────────────

interface GapCardProps {
  gap: Gap;
  chargesheetId: string;
  onJumpToDocument?: (gap: Gap) => void;
  onActionComplete?: () => void;
  selected?: boolean;
  onSelectToggle?: (gapId: string) => void;
}

// ─── Severity Styling ───────────────────────────────────────────────────────

const SEVERITY_STYLES: Record<GapSeverity, { bg: string; text: string; label: string }> = {
  critical: { bg: 'bg-red-100', text: 'text-red-800', label: 'Critical' },
  high: { bg: 'bg-orange-100', text: 'text-orange-800', label: 'High' },
  medium: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Medium' },
  low: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Low' },
  advisory: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Advisory' },
};

const CATEGORY_LABELS: Record<GapCategory, string> = {
  legal: 'Legal',
  evidence: 'Evidence',
  witness: 'Witness',
  procedural: 'Procedural',
  mindmap_divergence: 'Mindmap',
  completeness: 'Completeness',
  kb_playbook_gap: 'Playbook (KB L2)',
  kb_caselaw_gap: 'Case Law (KB L3)',
};

const ACTION_STYLES: Record<GapActionType, { bg: string; text: string; label: string }> = {
  accepted: { bg: 'bg-green-100', text: 'text-green-800', label: 'Accepted' },
  modified: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Modified' },
  dismissed: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Dismissed' },
  deferred: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Deferred' },
  escalated: { bg: 'bg-red-100', text: 'text-red-800', label: 'Escalated' },
};

const ACTION_BUTTONS: { action: GapActionType; label: string; variant: 'default' | 'outline' | 'secondary' | 'destructive' }[] = [
  { action: 'accepted', label: 'Accept', variant: 'default' },
  { action: 'modified', label: 'Modify', variant: 'outline' },
  { action: 'dismissed', label: 'Dismiss', variant: 'secondary' },
  { action: 'deferred', label: 'Defer', variant: 'outline' },
  { action: 'escalated', label: 'Escalate', variant: 'destructive' },
];

// ─── Component ──────────────────────────────────────────────────────────────

export default function GapCard({
  gap,
  chargesheetId,
  onActionComplete,
  selected,
  onSelectToggle,
}: GapCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showSuggested, setShowSuggested] = useState(false);
  const [modifyMode, setModifyMode] = useState(false);
  const [modifyNote, setModifyNote] = useState('');
  const [modifyDiff, setModifyDiff] = useState('');
  const [copied, setCopied] = useState(false);

  const gapAction = useGapAction(chargesheetId);
  const applySuggestion = useApplySuggestion(chargesheetId);
  const {
    data: history,
    isLoading: historyLoading,
  } = useGapHistory(chargesheetId, showHistory ? gap.id : '');

  const sevStyle = SEVERITY_STYLES[gap.severity];

  // Determine the hash_prev from latest history action
  const getHashPrev = useCallback((): string => {
    if (history && history.length > 0) {
      return history[history.length - 1].hash_self;
    }
    return 'GENESIS';
  }, [history]);

  const handleAction = useCallback(
    async (action: GapActionType) => {
      if (action === 'modified') {
        setModifyMode(true);
        // Expand history to get latest hash
        setShowHistory(true);
        return;
      }
      try {
        // Need to fetch history first if not loaded
        const hashPrev = getHashPrev();
        await gapAction.mutateAsync({
          gapId: gap.id,
          action,
          hash_prev: hashPrev,
        });
        onActionComplete?.();
      } catch {
        // Error handled by mutation
      }
    },
    [gap.id, gapAction, getHashPrev, onActionComplete]
  );

  const submitModify = useCallback(async () => {
    try {
      const hashPrev = getHashPrev();
      await gapAction.mutateAsync({
        gapId: gap.id,
        action: 'modified',
        note: modifyNote || undefined,
        modification_diff: modifyDiff || undefined,
        hash_prev: hashPrev,
      });
      setModifyMode(false);
      setModifyNote('');
      setModifyDiff('');
      onActionComplete?.();
    } catch {
      // Error handled by mutation
    }
  }, [gap.id, gapAction, getHashPrev, modifyNote, modifyDiff, onActionComplete]);

  const handleApplySuggestion = useCallback(async () => {
    try {
      await applySuggestion.mutateAsync(gap.id);
      onActionComplete?.();
    } catch {
      // Error handled by mutation
    }
  }, [gap.id, applySuggestion, onActionComplete]);

  const handleCopy = useCallback(async () => {
    if (gap.remediation.suggested_language) {
      await navigator.clipboard.writeText(gap.remediation.suggested_language);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [gap.remediation.suggested_language]);

  return (
    <Card
      className={`transition-shadow hover:shadow-sm ${selected ? 'ring-2 ring-blue-400' : ''}`}
    >
      {/* ── Always-visible header with title + description ─────────────── */}
      <div className="px-4 pt-3 pb-2">
        {/* Top row: pills + status */}
        <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
          {onSelectToggle && (
            <input
              type="checkbox"
              checked={!!selected}
              onChange={() => onSelectToggle(gap.id)}
              className="shrink-0"
              aria-label={`Select gap: ${gap.title}`}
            />
          )}
          <Badge
            className={`${sevStyle.bg} ${sevStyle.text} text-[10px] px-1.5 py-0 shrink-0 border-0`}
            aria-label={`Severity: ${sevStyle.label}`}
          >
            {sevStyle.label}
          </Badge>
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0">
            {CATEGORY_LABELS[gap.category]}
          </Badge>
          {gap.requires_disclaimer && (
            <span className="inline-flex items-center gap-0.5 text-[10px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-1 py-0 shrink-0">
              <Bot className="w-3 h-3" aria-hidden="true" />
              AI
            </span>
          )}
          {gap.current_action && (
            <Badge
              className={`${ACTION_STYLES[gap.current_action].bg} ${ACTION_STYLES[gap.current_action].text} text-[10px] px-1.5 py-0 shrink-0 border-0`}
            >
              {ACTION_STYLES[gap.current_action].label}
            </Badge>
          )}
          <span className="ml-auto text-[10px] text-slate-400">
            {Math.round(gap.confidence * 100)}%
          </span>
        </div>

        {/* Title — always visible */}
        <p className="text-sm font-semibold text-slate-800 leading-snug">
          {gap.title}
        </p>

        {/* Description — always visible */}
        {gap.description_md && (
          <p className="text-xs text-slate-600 mt-1 leading-relaxed line-clamp-3">
            {gap.description_md}
          </p>
        )}

        {/* Remediation summary — always visible */}
        {gap.remediation.summary && (
          <p className="text-xs text-blue-700 bg-blue-50 rounded px-2 py-1 mt-2">
            <span className="font-medium">Remediation:</span> {gap.remediation.summary}
          </p>
        )}

        {/* Quick actions + expand toggle */}
        <div className="flex items-center gap-1.5 mt-2">
          {!gap.current_action && !modifyMode && (
            <>
              <Button variant="default" size="sm" className="h-6 text-[11px] px-2 bg-green-600 hover:bg-green-700 text-white" onClick={() => handleAction('accepted')} disabled={gapAction.isPending} aria-label="Accept">Accept</Button>
              <Button variant="outline" size="sm" className="h-6 text-[11px] px-2" onClick={() => handleAction('modified')} disabled={gapAction.isPending} aria-label="Modify">Modify</Button>
              <Button variant="secondary" size="sm" className="h-6 text-[11px] px-2" onClick={() => handleAction('dismissed')} disabled={gapAction.isPending} aria-label="Dismiss">Dismiss</Button>
            </>
          )}
          <button
            className="ml-auto flex items-center gap-0.5 text-[11px] text-slate-400 hover:text-slate-600"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-label={expanded ? 'Show less' : 'Show details'}
          >
            {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            {expanded ? 'Less' : 'Details'}
          </button>
        </div>
      </div>

      {/* ── Expanded details (remediation steps, legal refs, actions) ───── */}
      {expanded && (
        <CardContent className="pt-0 pb-3 space-y-3">
          {/* Legal references */}
          {gap.legal_refs.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">Legal References</p>
              <div className="flex flex-wrap gap-1">
                {gap.legal_refs.map((ref, i) => (
                  <Badge key={i} variant="outline" className="text-[11px] px-1.5 py-0">
                    {ref.framework} {ref.section}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Remediation steps */}
          {gap.remediation.steps.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">Steps</p>
              <ol className="list-decimal list-inside space-y-0.5 text-xs text-slate-600">
                {gap.remediation.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
              <p className="text-[10px] text-slate-400 mt-1">
                Effort: {gap.remediation.estimated_effort}
              </p>
            </div>
          )}

          {/* Suggested language */}
          {gap.remediation.suggested_language && (
            <div>
              <button
                type="button"
                className="flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700 mb-1"
                onClick={() => setShowSuggested(!showSuggested)}
              >
                {showSuggested ? (
                  <ChevronDown className="w-3 h-3" aria-hidden="true" />
                ) : (
                  <ChevronRight className="w-3 h-3" aria-hidden="true" />
                )}
                Suggested Language
              </button>
              {showSuggested && (
                <div className="bg-blue-50 border border-blue-200 rounded-md p-3 text-sm text-slate-800 whitespace-pre-wrap">
                  {gap.remediation.suggested_language}
                  <div className="flex gap-2 mt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={handleCopy}
                      aria-label="Copy suggested language to clipboard"
                    >
                      {copied ? (
                        <>
                          <Check className="w-3 h-3 mr-1" aria-hidden="true" />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3 mr-1" aria-hidden="true" />
                          Copy
                        </>
                      )}
                    </Button>
                    <Button
                      size="sm"
                      className="h-7 text-xs bg-blue-600 hover:bg-blue-700 text-white"
                      onClick={handleApplySuggestion}
                      disabled={applySuggestion.isPending}
                      aria-label="Apply suggested language to chargesheet"
                    >
                      {applySuggestion.isPending ? 'Applying...' : 'Apply'}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Confidence & tags */}
          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span>Confidence: {Math.round(gap.confidence * 100)}%</span>
            {gap.tags.length > 0 && (
              <div className="flex gap-1">
                {gap.tags.map((tag) => (
                  <span
                    key={tag}
                    className="bg-slate-100 text-slate-500 rounded px-1.5 py-0"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Modify mode */}
          {modifyMode && (
            <div className="space-y-2 bg-slate-50 rounded-md p-3">
              <label className="block text-xs font-medium text-slate-600">
                Note
              </label>
              <textarea
                className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
                rows={2}
                value={modifyNote}
                onChange={(e) => setModifyNote(e.target.value)}
                placeholder="Describe your modification..."
                aria-label="Modification note"
              />
              <label className="block text-xs font-medium text-slate-600">
                Modification diff
              </label>
              <textarea
                className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
                rows={3}
                value={modifyDiff}
                onChange={(e) => setModifyDiff(e.target.value)}
                placeholder="Paste your modified text..."
                aria-label="Modification diff"
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="h-7 text-xs bg-blue-600 hover:bg-blue-700 text-white"
                  onClick={submitModify}
                  disabled={gapAction.isPending}
                  aria-label="Submit modification"
                >
                  {gapAction.isPending ? 'Submitting...' : 'Submit'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setModifyMode(false)}
                  aria-label="Cancel modification"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* Action row */}
          {!modifyMode && (
            <div className="flex flex-wrap gap-1.5">
              {ACTION_BUTTONS.map((btn) => (
                <Button
                  key={btn.action}
                  variant={btn.variant}
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => handleAction(btn.action)}
                  disabled={gapAction.isPending}
                  aria-label={`${btn.label} this gap`}
                >
                  {btn.label}
                </Button>
              ))}
            </div>
          )}

          {/* Error display */}
          {gapAction.isError && (
            <p className="text-xs text-red-600">
              Action failed: {gapAction.error instanceof Error ? gapAction.error.message : 'Unknown error'}
            </p>
          )}

          {/* Audit history (collapsible) */}
          <div>
            <button
              type="button"
              className="flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700"
              onClick={() => setShowHistory(!showHistory)}
            >
              {showHistory ? (
                <ChevronDown className="w-3 h-3" aria-hidden="true" />
              ) : (
                <ChevronRight className="w-3 h-3" aria-hidden="true" />
              )}
              Audit History
            </button>
            {showHistory && (
              <div className="mt-2 space-y-2 max-h-48 overflow-y-auto">
                {historyLoading && (
                  <p className="text-xs text-slate-400">Loading history...</p>
                )}
                {history && history.length === 0 && (
                  <p className="text-xs text-slate-400">No actions taken yet.</p>
                )}
                {history?.map((entry: GapAction) => (
                  <div
                    key={entry.id}
                    className="flex items-start gap-2 text-xs border-l-2 border-slate-200 pl-3 py-1"
                  >
                    <User className="w-3 h-3 text-slate-400 mt-0.5 shrink-0" aria-hidden="true" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-slate-700">
                          {entry.user_id}
                        </span>
                        <Badge
                          className={`${ACTION_STYLES[entry.action]?.bg ?? 'bg-gray-100'} ${ACTION_STYLES[entry.action]?.text ?? 'text-gray-700'} text-[10px] px-1.5 py-0 border-0`}
                        >
                          {ACTION_STYLES[entry.action]?.label ?? entry.action}
                        </Badge>
                      </div>
                      {entry.note && (
                        <p className="text-slate-500 mt-0.5">{entry.note}</p>
                      )}
                      <div className="flex items-center gap-1 text-slate-400 mt-0.5">
                        <Clock className="w-3 h-3" aria-hidden="true" />
                        <span>
                          {new Date(entry.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
