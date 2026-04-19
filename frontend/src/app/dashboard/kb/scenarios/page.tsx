"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronLeft, BookOpen, FileText, Search, X } from "lucide-react";

interface ScenarioRow {
  scenario_id: string;
  scenario_name: string;
  applicable_sections: string[];
  punishment_summary: string | null;
  page_start: number;
  page_end: number;
  linked_acts: string[];
  phase_count: number;
  item_count: number;
  evidence_count: number;
  forms_required: string[];
  deadlines: string[];
  source_authority: string | null;
}

interface ListResponse {
  total: number;
  scenarios: ScenarioRow[];
}

interface FullScenarioItem {
  marker: string;
  text: string;
  actors: string[];
  forms: string[];
  deadline: string | null;
  is_evidence: boolean;
}

interface FullScenarioSubBlock {
  label: string;
  title: string;
  items: FullScenarioItem[];
}

interface FullScenarioPhase {
  number: number;
  title: string;
  sub_blocks: FullScenarioSubBlock[];
}

interface FullScenario extends ScenarioRow {
  phases: FullScenarioPhase[];
  case_facts_template?: string;
}

function useScenarios() {
  return useQuery<ListResponse>({
    queryKey: ["kb-io-scenarios"],
    queryFn: () => apiClient("/api/v1/kb/io-scenarios"),
  });
}

function useScenarioDetail(id: string | null) {
  return useQuery<FullScenario>({
    queryKey: ["kb-io-scenario", id],
    queryFn: () => apiClient(`/api/v1/kb/io-scenarios/${id}`),
    enabled: !!id,
  });
}

export default function KBScenariosPage() {
  const { data, isLoading, isError } = useScenarios();
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const rows = data?.scenarios ?? [];
    if (!filter.trim()) return rows;
    const q = filter.toLowerCase();
    return rows.filter(
      (r) =>
        r.scenario_name.toLowerCase().includes(q) ||
        r.applicable_sections.some((s) => s.toLowerCase().includes(q)) ||
        r.scenario_id.toLowerCase().includes(q),
    );
  }, [data, filter]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/dashboard/kb" className="text-slate-400 hover:text-slate-700">
          <ChevronLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-semibold text-slate-800 flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-indigo-600" />
            IO Scenarios — Compendium Review
          </h1>
          <p className="text-sm text-slate-500">
            Delhi Police Academy Compendium of Scenarios for Investigating
            Officers, 2024 · {data?.total ?? "…"} scenarios. Use this table to
            spot-check the KB; flag any mis-categorised content for the next
            ratification round.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search by name, scenario id, or section (e.g. BNS 304)"
            className="w-full rounded border border-slate-300 pl-8 pr-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        {filter && (
          <Button variant="ghost" size="sm" onClick={() => setFilter("")}>
            Clear
          </Button>
        )}
        <span className="text-xs text-slate-400 ml-auto">
          {filtered.length} of {data?.total ?? 0}
        </span>
      </div>

      {isLoading && (
        <p className="p-6 text-center text-sm text-slate-400">Loading…</p>
      )}
      {isError && (
        <p className="p-6 text-center text-sm text-red-600">
          Failed to load IO scenarios from the KB.
        </p>
      )}

      {data && (
        <div className="overflow-auto rounded border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr className="border-b border-slate-200 [&>th]:px-3 [&>th]:py-2 [&>th]:text-left [&>th]:font-medium">
                <th>ID</th>
                <th>Scenario</th>
                <th>Sections</th>
                <th>Acts</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr
                  key={row.scenario_id}
                  className="border-b border-slate-100 last:border-0 hover:bg-slate-50/40"
                >
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">
                    {row.scenario_id}
                  </td>
                  <td className="px-3 py-2 text-slate-800">
                    <div className="font-medium">{row.scenario_name}</div>
                    {row.punishment_summary && (
                      <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">
                        {row.punishment_summary}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {row.applicable_sections.map((s) => (
                        <Badge
                          key={s}
                          variant="outline"
                          className="text-[10px] border-indigo-300 bg-indigo-50 text-indigo-800"
                        >
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {row.linked_acts.map((a) => (
                        <span
                          key={a}
                          className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600"
                        >
                          {a}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => setSelected(row.scenario_id)}
                    >
                      <FileText className="h-3 w-3 mr-1" />
                      Review
                    </Button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-12 text-center text-slate-400 text-sm">
                    No scenarios match the filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <ScenarioDetailDrawer
          scenarioId={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function ScenarioDetailDrawer({
  scenarioId,
  onClose,
}: {
  scenarioId: string;
  onClose: () => void;
}) {
  const { data, isLoading, isError } = useScenarioDetail(scenarioId);

  return (
    <div className="fixed inset-0 z-40 flex items-stretch justify-end bg-black/30">
      <div className="w-full max-w-3xl bg-white shadow-xl flex flex-col">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <div>
            <p className="text-xs uppercase tracking-wider text-slate-500">
              {scenarioId}
            </p>
            <p className="text-base font-semibold text-slate-800">
              {data?.scenario_name ?? "Loading…"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-auto px-5 py-4 space-y-4">
          {isLoading && (
            <p className="text-sm text-slate-400">Loading scenario detail…</p>
          )}
          {isError && (
            <p className="text-sm text-red-600">
              Failed to load scenario {scenarioId}.
            </p>
          )}
          {data && (
            <>
              <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Sections" value={data.applicable_sections.join(", ")} />
                  <Field label="Acts" value={data.linked_acts.join(", ")} />
                  <Field
                    label="Source pages"
                    value={`${data.page_start}–${data.page_end}`}
                  />
                  <Field label="Phases / items" value={`${data.phase_count} / ${data.item_count}`} />
                </div>
                {data.punishment_summary && (
                  <Field label="Punishment" value={data.punishment_summary} block />
                )}
              </div>

              {data.case_facts_template && (
                <Section title="Case facts (illustrative)">
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">
                    {data.case_facts_template}
                  </p>
                </Section>
              )}

              {data.phases.map((phase) => (
                <Section
                  key={`${phase.number}-${phase.title}`}
                  title={`${phase.number}. ${phase.title}`}
                >
                  {phase.sub_blocks.map((sb) => (
                    <div key={`${phase.number}-${sb.label}-${sb.title}`} className="mb-3 last:mb-0">
                      <p className="text-xs font-semibold text-slate-700 mb-1.5">
                        {sb.label && sb.label !== "·" ? `${sb.label}. ` : ""}
                        {sb.title}
                      </p>
                      <ul className="space-y-1">
                        {sb.items.map((it, i) => (
                          <li key={i} className="text-sm text-slate-700 leading-snug">
                            <span className="text-slate-400 font-mono mr-1.5">{it.marker}</span>
                            {it.text}
                            <span className="ml-1 inline-flex flex-wrap gap-1">
                              {it.is_evidence && (
                                <span className="rounded bg-amber-100 px-1 text-[10px] font-medium text-amber-800">
                                  evidence
                                </span>
                              )}
                              {it.deadline && (
                                <span className="rounded bg-red-100 px-1 text-[10px] font-medium text-red-800">
                                  ⏱ {it.deadline}
                                </span>
                              )}
                              {it.forms?.map((f) => (
                                <span
                                  key={f}
                                  className="rounded bg-slate-100 px-1 text-[10px] font-medium text-slate-700"
                                >
                                  {f}
                                </span>
                              ))}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </Section>
              ))}
            </>
          )}
        </div>

        <div className="border-t border-slate-200 px-5 py-2 text-[11px] text-slate-500">
          Source: {data?.source_authority ?? "Delhi Police Academy"}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  block = false,
}: {
  label: string;
  value: string;
  block?: boolean;
}) {
  return (
    <div className={block ? "col-span-2 mt-1" : undefined}>
      <p className="text-[10px] uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <p className="text-sm text-slate-800">{value}</p>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded border border-slate-200 bg-white p-3">
      <h2 className="text-sm font-semibold text-slate-800 mb-2">{title}</h2>
      {children}
    </div>
  );
}
