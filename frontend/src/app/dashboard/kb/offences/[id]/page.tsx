"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ArrowLeft,
  Scale,
  ShieldCheck,
  ShieldOff,
  BookOpenCheck,
  Quote,
  Pencil,
  Plus,
  Trash2,
  Check,
  X,
} from "lucide-react";
import {
  useKBOffenceDetail,
  useCurrentUser,
  useUpdateOffence,
  useReviewOffence,
  useCreateNode,
  useUpdateNode,
  useDeleteNode,
  type KnowledgeNode,
  type LegalCitation,
} from "@/hooks/kb/useKB";

const TIER_COLOURS: Record<string, string> = {
  canonical: "bg-blue-100 text-blue-800 border-blue-200",
  judgment_derived: "bg-purple-100 text-purple-800 border-purple-200",
};

const APPROVAL_COLOURS: Record<string, string> = {
  approved: "bg-green-100 text-green-800",
  proposed: "bg-yellow-100 text-yellow-800",
  contested: "bg-orange-100 text-orange-800",
  deprecated: "bg-red-100 text-red-800",
  draft: "bg-gray-100 text-gray-700",
  reviewed: "bg-blue-100 text-blue-800",
};

const PRIORITY_LABELS: Record<string, { label: string; className: string }> = {
  critical: { label: "Critical", className: "text-red-600" },
  high: { label: "High", className: "text-orange-600" },
  medium: { label: "Medium", className: "text-yellow-600" },
  low: { label: "Low", className: "text-green-600" },
  advisory: { label: "Advisory", className: "text-gray-500" },
};

const PRIORITY_COMPAT: Record<number, string> = {
  1: "critical", 2: "high", 3: "medium", 4: "low", 5: "advisory",
};

const BRANCH_TYPES = [
  "legal_section",
  "immediate_action",
  "panchnama",
  "evidence",
  "witness_bayan",
  "forensic",
  "gap_historical",
  "procedural_safeguard",
];

const PRIORITY_OPTIONS = ["critical", "high", "medium", "low", "advisory"];

function MetadataRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <span className="text-sm text-muted-foreground w-32 shrink-0 font-medium">
        {label}
      </span>
      <span className="text-sm">{value}</span>
    </div>
  );
}

function BooleanBadge({ value, trueLabel, falseLabel }: { value: boolean; trueLabel: string; falseLabel: string }) {
  return (
    <Badge className={value ? "bg-green-100 text-green-800 gap-1" : "bg-gray-100 text-gray-600 gap-1"}>
      {value ? <ShieldCheck className="w-3 h-3" /> : <ShieldOff className="w-3 h-3" />}
      {value ? trueLabel : falseLabel}
    </Badge>
  );
}

function CitationList({ citations }: { citations: LegalCitation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {citations.map((citation, idx) => (
        <span
          key={idx}
          className="inline-flex items-center gap-1 text-xs bg-slate-50 border border-slate-200 rounded px-2 py-0.5"
          title={citation.description}
        >
          <Quote className="w-3 h-3 text-slate-400" />
          {citation.framework || citation.act} S.{citation.section}
          {citation.subsection ? `(${citation.subsection})` : ""}
        </span>
      ))}
    </div>
  );
}

// ── Citation Editor ────────────────────────────────────────────────────────

function CitationEditor({
  citations,
  onChange,
}: {
  citations: LegalCitation[];
  onChange: (c: LegalCitation[]) => void;
}) {
  const addRow = () =>
    onChange([...citations, { act: "", section: "", framework: "", subsection: "", description: "" }]);
  const removeRow = (i: number) => onChange(citations.filter((_, idx) => idx !== i));
  const updateRow = (i: number, field: string, value: string) => {
    const updated = [...citations];
    updated[i] = { ...updated[i], [field]: value };
    onChange(updated);
  };

  return (
    <div className="space-y-2">
      <Label>Legal Citations</Label>
      {citations.map((c, i) => (
        <div key={i} className="flex gap-2 items-start">
          <Input
            placeholder="Framework (BNS, BNSS...)"
            value={c.framework || c.act || ""}
            onChange={(e) => updateRow(i, "framework", e.target.value)}
            className="flex-1"
          />
          <Input
            placeholder="Section"
            value={c.section || ""}
            onChange={(e) => updateRow(i, "section", e.target.value)}
            className="w-24"
          />
          <Input
            placeholder="Sub"
            value={c.subsection || ""}
            onChange={(e) => updateRow(i, "subsection", e.target.value)}
            className="w-20"
          />
          <Input
            placeholder="Description"
            value={c.description || ""}
            onChange={(e) => updateRow(i, "description", e.target.value)}
            className="flex-1"
          />
          <Button type="button" variant="ghost" size="sm" onClick={() => removeRow(i)}>
            <X className="w-4 h-4 text-red-500" />
          </Button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={addRow} className="gap-1">
        <Plus className="w-3 h-3" /> Add Citation
      </Button>
    </div>
  );
}

// ── Node Form (create/edit) ────────────────────────────────────────────────

function NodeForm({
  initial,
  onSave,
  onCancel,
  saving,
}: {
  initial?: KnowledgeNode;
  onSave: (data: Record<string, unknown>) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [branchType, setBranchType] = useState(initial?.branch_type || "legal_section");
  const [priority, setPriority] = useState(
    typeof initial?.priority === "number"
      ? PRIORITY_COMPAT[initial.priority] || "medium"
      : initial?.priority || "medium"
  );
  const [titleEn, setTitleEn] = useState(initial?.title_en || initial?.title || "");
  const [titleGu, setTitleGu] = useState(initial?.title_gu || "");
  const [descriptionMd, setDescriptionMd] = useState(initial?.description_md || initial?.description || "");
  const [citations, setCitations] = useState<LegalCitation[]>(
    initial?.legal_basis_citations || initial?.legal_citations || []
  );
  const [requiresDisclaimer, setRequiresDisclaimer] = useState(initial?.requires_disclaimer || false);
  const [displayOrder, setDisplayOrder] = useState(initial?.display_order ?? 0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!titleEn.trim()) return;
    onSave({
      branch_type: branchType,
      priority,
      title_en: titleEn.trim(),
      title_gu: titleGu.trim() || null,
      description_md: descriptionMd.trim(),
      legal_basis_citations: citations.filter((c) => c.section || c.framework || c.act),
      requires_disclaimer: requiresDisclaimer,
      display_order: displayOrder,
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <Card className="border-2 border-blue-200">
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Branch Type</Label>
              <select
                value={branchType}
                onChange={(e) => setBranchType(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {BRANCH_TYPES.map((bt) => (
                  <option key={bt} value={bt}>
                    {bt.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label>Priority</Label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p} value={p}>
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <Label>Title (English) *</Label>
            <Input value={titleEn} onChange={(e) => setTitleEn(e.target.value)} placeholder="Node title" />
          </div>
          <div>
            <Label>Title (Gujarati)</Label>
            <Input value={titleGu} onChange={(e) => setTitleGu(e.target.value)} placeholder="Gujarati title" />
          </div>
          <div>
            <Label>Description</Label>
            <textarea
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={descriptionMd}
              onChange={(e) => setDescriptionMd(e.target.value)}
              placeholder="Detailed description (supports markdown)..."
            />
          </div>

          <CitationEditor citations={citations} onChange={setCitations} />

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={requiresDisclaimer}
                onChange={(e) => setRequiresDisclaimer(e.target.checked)}
                className="rounded border-gray-300"
              />
              Requires Disclaimer
            </label>
            <div className="flex items-center gap-2">
              <Label className="text-sm">Display Order</Label>
              <Input
                type="number"
                value={displayOrder}
                onChange={(e) => setDisplayOrder(parseInt(e.target.value) || 0)}
                className="w-20"
              />
            </div>
          </div>

          <div className="flex gap-2 pt-2">
            <Button type="submit" disabled={saving} size="sm" className="bg-blue-600 hover:bg-blue-700 text-white gap-1">
              <Check className="w-4 h-4" />
              {saving ? "Saving..." : initial ? "Update Node" : "Add Node"}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={onCancel} className="gap-1">
              <X className="w-4 h-4" /> Cancel
            </Button>
          </div>
        </CardContent>
      </Card>
    </form>
  );
}

// ── Node Card ──────────────────────────────────────────────────────────────

function NodeCard({
  node,
  isAdmin,
  offenceId,
}: {
  node: KnowledgeNode;
  isAdmin: boolean;
  offenceId: string;
}) {
  const [editing, setEditing] = useState(false);
  const updateNode = useUpdateNode();
  const deleteNode = useDeleteNode();

  const priorityKey =
    typeof node.priority === "number"
      ? PRIORITY_COMPAT[node.priority] || "medium"
      : String(node.priority);
  const priorityInfo = PRIORITY_LABELS[priorityKey] ?? {
    label: priorityKey,
    className: "text-gray-500",
  };

  if (editing) {
    return (
      <NodeForm
        initial={node}
        saving={updateNode.isPending}
        onCancel={() => setEditing(false)}
        onSave={(data) =>
          updateNode.mutate(
            { nodeId: node.id, offenceId, data },
            { onSuccess: () => setEditing(false) }
          )
        }
      />
    );
  }

  return (
    <Card className="border-l-4" style={{ borderLeftColor: node.tier === "canonical" ? "#3b82f6" : "#8b5cf6" }}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className={TIER_COLOURS[node.tier] ?? "bg-gray-100 text-gray-700"}>
              {node.tier === "canonical" ? "Canonical" : "Judgment Derived"}
            </Badge>
            <span className={`text-xs font-medium ${priorityInfo.className}`}>
              {priorityInfo.label}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge className={APPROVAL_COLOURS[node.approval_status] ?? "bg-gray-100 text-gray-700"}>
              {node.approval_status.replace(/_/g, " ")}
            </Badge>
            {isAdmin && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={() => setEditing(true)}
                  title="Edit node"
                >
                  <Pencil className="w-3.5 h-3.5 text-blue-600" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={() => {
                    if (window.confirm("Deprecate this knowledge node?")) {
                      deleteNode.mutate({ nodeId: node.id, offenceId });
                    }
                  }}
                  title="Deprecate node"
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-500" />
                </Button>
              </>
            )}
          </div>
        </div>

        <h4 className="font-semibold text-sm mb-1">
          {node.title_en || node.title}
        </h4>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {node.description_md || node.description}
        </p>

        {(node.legal_basis_citations || node.legal_citations || []).length > 0 && (
          <CitationList citations={node.legal_basis_citations || node.legal_citations || []} />
        )}
      </CardContent>
    </Card>
  );
}

// ── Offence Edit Form ──────────────────────────────────────────────────────

function OffenceEditForm({
  offence,
  onSave,
  onCancel,
  saving,
}: {
  offence: Record<string, unknown>;
  onSave: (data: Record<string, unknown>) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [displayNameEn, setDisplayNameEn] = useState((offence.display_name_en as string) || "");
  const [displayNameGu, setDisplayNameGu] = useState((offence.display_name_gu as string) || "");
  const [bnsSection, setBnsSection] = useState((offence.bns_section as string) || "");
  const [bnsSubsection, setBnsSubsection] = useState((offence.bns_subsection as string) || "");
  const [punishment, setPunishment] = useState((offence.punishment as string) || "");
  const [triableBy, setTriableBy] = useState((offence.triable_by as string) || "");
  const [cognizable, setCognizable] = useState(!!offence.cognizable);
  const [bailable, setBailable] = useState(!!offence.bailable);
  const [compoundable, setCompoundable] = useState(String(offence.compoundable || "no"));
  const [shortDescMd, setShortDescMd] = useState((offence.short_description_md as string) || "");
  const [scheduleRef, setScheduleRef] = useState((offence.schedule_reference as string) || "");
  const [relatedCodes, setRelatedCodes] = useState(
    ((offence.related_offence_codes as string[]) || []).join(", ")
  );
  const [specialActs, setSpecialActs] = useState(
    ((offence.special_acts as string[]) || []).join(", ")
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      display_name_en: displayNameEn.trim(),
      display_name_gu: displayNameGu.trim() || null,
      bns_section: bnsSection.trim() || null,
      bns_subsection: bnsSubsection.trim() || null,
      punishment: punishment.trim() || null,
      triable_by: triableBy.trim() || null,
      cognizable,
      bailable,
      compoundable,
      short_description_md: shortDescMd.trim(),
      schedule_reference: scheduleRef.trim() || null,
      related_offence_codes: relatedCodes.split(",").map((s) => s.trim()).filter(Boolean),
      special_acts: specialActs.split(",").map((s) => s.trim()).filter(Boolean),
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Display Name (English)</Label>
            <Input value={displayNameEn} onChange={(e) => setDisplayNameEn(e.target.value)} />
          </div>
          <div>
            <Label>Display Name (Gujarati)</Label>
            <Input value={displayNameGu} onChange={(e) => setDisplayNameGu(e.target.value)} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>BNS Section</Label>
            <Input value={bnsSection} onChange={(e) => setBnsSection(e.target.value)} />
          </div>
          <div>
            <Label>BNS Subsection</Label>
            <Input value={bnsSubsection} onChange={(e) => setBnsSubsection(e.target.value)} />
          </div>
        </div>
        <div>
          <Label>Description</Label>
          <textarea
            className="flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={shortDescMd}
            onChange={(e) => setShortDescMd(e.target.value)}
          />
        </div>
        <div>
          <Label>Punishment</Label>
          <textarea
            className="flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={punishment}
            onChange={(e) => setPunishment(e.target.value)}
          />
        </div>
        <div className="flex gap-6">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={cognizable}
              onChange={(e) => setCognizable(e.target.checked)}
              className="rounded border-gray-300"
            />
            Cognizable
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={bailable}
              onChange={(e) => setBailable(e.target.checked)}
              className="rounded border-gray-300"
            />
            Bailable
          </label>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Compoundable</Label>
            <select
              value={compoundable}
              onChange={(e) => setCompoundable(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="no">No</option>
              <option value="yes">Yes</option>
              <option value="with court permission">With Court Permission</option>
            </select>
          </div>
          <div>
            <Label>Triable By</Label>
            <Input value={triableBy} onChange={(e) => setTriableBy(e.target.value)} />
          </div>
        </div>
        <div>
          <Label>Schedule Reference</Label>
          <Input value={scheduleRef} onChange={(e) => setScheduleRef(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Related Offence Codes (comma-separated)</Label>
            <Input value={relatedCodes} onChange={(e) => setRelatedCodes(e.target.value)} />
          </div>
          <div>
            <Label>Special Acts (comma-separated)</Label>
            <Input value={specialActs} onChange={(e) => setSpecialActs(e.target.value)} />
          </div>
        </div>
        <div className="flex gap-2 pt-2">
          <Button type="submit" disabled={saving} size="sm" className="bg-blue-600 hover:bg-blue-700 text-white gap-1">
            <Check className="w-4 h-4" /> {saving ? "Saving..." : "Save Changes"}
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={onCancel} className="gap-1">
            <X className="w-4 h-4" /> Cancel
          </Button>
        </div>
      </CardContent>
    </form>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function OffenceDetailPage() {
  const params = useParams();
  const offenceId = typeof params.id === "string" ? params.id : "";
  const { data: offence, isLoading, isError } = useKBOffenceDetail(offenceId);
  const { data: currentUser } = useCurrentUser();
  const isAdmin = currentUser?.role === "ADMIN" || currentUser?.role === "SP";

  const updateOffence = useUpdateOffence();
  const reviewOffence = useReviewOffence();
  const createNode = useCreateNode();

  const [editingOffence, setEditingOffence] = useState(false);
  const [addingNode, setAddingNode] = useState(false);

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isError || !offence) {
    return (
      <div className="py-8">
        <Link href="/dashboard/kb">
          <Button variant="ghost" size="sm" className="gap-1 mb-4">
            <ArrowLeft className="w-4 h-4" /> Back to KB
          </Button>
        </Link>
        <p className="text-red-600">
          Failed to load offence details. The offence may not exist.
        </p>
      </div>
    );
  }

  const nodesByBranch = (offence.nodes ?? []).reduce<Record<string, KnowledgeNode[]>>(
    (acc, node) => {
      if (node.approval_status === "deprecated") return acc;
      const branch = node.branch_type || "general";
      if (!acc[branch]) acc[branch] = [];
      acc[branch].push(node);
      return acc;
    },
    {}
  );

  return (
    <div>
      {/* Back link */}
      <Link href="/dashboard/kb">
        <Button variant="ghost" size="sm" className="gap-1 mb-4">
          <ArrowLeft className="w-4 h-4" /> Back to KB
        </Button>
      </Link>

      {/* Offence metadata */}
      <Card className="mb-4">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Scale className="w-5 h-5 text-blue-600" />
                <span className="text-xs font-mono bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                  {offence.offence_code}
                </span>
              </div>
              <CardTitle className="text-xl">
                {offence.display_name_en}
              </CardTitle>
            </div>
            <div className="flex items-center gap-2">
              <Badge className={APPROVAL_COLOURS[offence.review_status] ?? "bg-gray-100 text-gray-700"}>
                {offence.review_status.replace(/_/g, " ")}
              </Badge>
              {isAdmin && !editingOffence && (
                <Button variant="outline" size="sm" onClick={() => setEditingOffence(true)} className="gap-1">
                  <Pencil className="w-3.5 h-3.5" /> Edit
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        {editingOffence ? (
          <OffenceEditForm
            offence={offence as unknown as Record<string, unknown>}
            saving={updateOffence.isPending}
            onCancel={() => setEditingOffence(false)}
            onSave={(data) =>
              updateOffence.mutate(
                { id: offenceId, data },
                { onSuccess: () => setEditingOffence(false) }
              )
            }
          />
        ) : (
          <CardContent>
            <div className="divide-y">
              <MetadataRow label="BNS Section" value={offence.bns_section} />
              {offence.bns_subsection && (
                <MetadataRow label="Subsection" value={offence.bns_subsection} />
              )}
              <MetadataRow label="Category" value={offence.category_id} />
              <MetadataRow label="Punishment" value={offence.punishment || "N/A"} />
              {offence.triable_by && (
                <MetadataRow label="Triable By" value={offence.triable_by} />
              )}
              <MetadataRow
                label="Classification"
                value={
                  <div className="flex gap-2 flex-wrap">
                    <BooleanBadge value={offence.cognizable} trueLabel="Cognizable" falseLabel="Non-cognizable" />
                    <BooleanBadge value={offence.bailable} trueLabel="Bailable" falseLabel="Non-bailable" />
                    <BooleanBadge
                      value={offence.compoundable === true || offence.compoundable === "yes"}
                      trueLabel="Compoundable"
                      falseLabel="Non-compoundable"
                    />
                  </div>
                }
              />
              {offence.schedule_reference && (
                <MetadataRow label="Schedule Ref" value={offence.schedule_reference} />
              )}
              {offence.reviewed_by && (
                <MetadataRow
                  label="Reviewed By"
                  value={
                    <span>
                      {offence.reviewed_by}
                      {offence.reviewed_at && (
                        <span className="text-muted-foreground ml-2">
                          ({new Date(offence.reviewed_at).toLocaleDateString()})
                        </span>
                      )}
                    </span>
                  }
                />
              )}
            </div>
          </CardContent>
        )}
      </Card>

      {/* Review workflow — admin only */}
      {isAdmin && (
        <Card className="mb-8">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-muted-foreground">
                Review Status:
              </span>
              <Badge className={APPROVAL_COLOURS[offence.review_status] ?? "bg-gray-100 text-gray-700"}>
                {offence.review_status.replace(/_/g, " ")}
              </Badge>
              <div className="flex gap-2 ml-auto">
                {offence.review_status === "draft" && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={reviewOffence.isPending}
                    onClick={() =>
                      reviewOffence.mutate({ id: offenceId, review_status: "reviewed" })
                    }
                  >
                    Mark as Reviewed
                  </Button>
                )}
                {(offence.review_status === "draft" || offence.review_status === "reviewed") && (
                  <Button
                    size="sm"
                    className="bg-green-600 hover:bg-green-700 text-white"
                    disabled={reviewOffence.isPending}
                    onClick={() =>
                      reviewOffence.mutate({ id: offenceId, review_status: "approved" })
                    }
                  >
                    Approve
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Knowledge Nodes */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BookOpenCheck className="w-5 h-5 text-muted-foreground" />
          <h3 className="text-lg font-semibold">
            Knowledge Nodes ({offence.nodes?.length ?? 0})
          </h3>
        </div>
        {isAdmin && (
          <Button
            size="sm"
            onClick={() => setAddingNode(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white gap-1"
          >
            <Plus className="w-4 h-4" /> Add Node
          </Button>
        )}
      </div>

      {addingNode && (
        <div className="mb-4">
          <NodeForm
            saving={createNode.isPending}
            onCancel={() => setAddingNode(false)}
            onSave={(data) =>
              createNode.mutate(
                { offenceId, data },
                { onSuccess: () => setAddingNode(false) }
              )
            }
          />
        </div>
      )}

      {Object.keys(nodesByBranch).length === 0 ? (
        <p className="text-muted-foreground text-sm py-4">
          No knowledge nodes found for this offence.
        </p>
      ) : (
        <div className="space-y-8">
          {Object.entries(nodesByBranch).map(([branchType, nodes]) => (
            <div key={branchType}>
              <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 border-b pb-1">
                {branchType.replace(/_/g, " ")}
              </h4>
              <div className="space-y-3">
                {nodes.map((node) => (
                  <NodeCard
                    key={node.id}
                    node={node}
                    isAdmin={isAdmin}
                    offenceId={offenceId}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
