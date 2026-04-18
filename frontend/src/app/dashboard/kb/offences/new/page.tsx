"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowLeft } from "lucide-react";
import { useCreateOffence } from "@/hooks/kb/useKB";

export default function NewOffencePage() {
  const router = useRouter();
  const createOffence = useCreateOffence();

  const [offenceCode, setOffenceCode] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [bnsSection, setBnsSection] = useState("");
  const [bnsSubsection, setBnsSubsection] = useState("");
  const [displayNameEn, setDisplayNameEn] = useState("");
  const [displayNameGu, setDisplayNameGu] = useState("");
  const [shortDescriptionMd, setShortDescriptionMd] = useState("");
  const [punishment, setPunishment] = useState("");
  const [cognizable, setCognizable] = useState(false);
  const [bailable, setBailable] = useState(false);
  const [triableBy, setTriableBy] = useState("");
  const [compoundable, setCompoundable] = useState("no");
  const [scheduleReference, setScheduleReference] = useState("");
  const [relatedCodes, setRelatedCodes] = useState("");
  const [specialActs, setSpecialActs] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!offenceCode.trim() || !categoryId.trim() || !displayNameEn.trim()) {
      setError("Offence code, category, and display name are required.");
      return;
    }

    try {
      const result = await createOffence.mutateAsync({
        offence_code: offenceCode.trim(),
        category_id: categoryId.trim(),
        bns_section: bnsSection.trim() || null,
        bns_subsection: bnsSubsection.trim() || null,
        display_name_en: displayNameEn.trim(),
        display_name_gu: displayNameGu.trim() || null,
        short_description_md: shortDescriptionMd.trim(),
        punishment: punishment.trim() || null,
        cognizable,
        bailable,
        triable_by: triableBy.trim() || null,
        compoundable,
        schedule_reference: scheduleReference.trim() || null,
        related_offence_codes: relatedCodes
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        special_acts: specialActs
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      router.push(`/dashboard/kb/offences/${result.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create offence";
      setError(msg);
    }
  };

  return (
    <div className="max-w-3xl">
      <Link href="/dashboard/kb">
        <Button variant="ghost" size="sm" className="gap-1 mb-4">
          <ArrowLeft className="w-4 h-4" /> Back to KB
        </Button>
      </Link>

      <h2 className="text-2xl font-bold mb-6">Create New Offence</h2>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-md p-3 mb-4 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Identity */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Identity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="offence_code">Offence Code *</Label>
                <Input
                  id="offence_code"
                  value={offenceCode}
                  onChange={(e) => setOffenceCode(e.target.value)}
                  placeholder="e.g. BNS_S103"
                />
              </div>
              <div>
                <Label htmlFor="category_id">Category *</Label>
                <Input
                  id="category_id"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  placeholder="e.g. violent_crimes"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="bns_section">BNS Section</Label>
                <Input
                  id="bns_section"
                  value={bnsSection}
                  onChange={(e) => setBnsSection(e.target.value)}
                  placeholder="e.g. 103"
                />
              </div>
              <div>
                <Label htmlFor="bns_subsection">BNS Subsection</Label>
                <Input
                  id="bns_subsection"
                  value={bnsSubsection}
                  onChange={(e) => setBnsSubsection(e.target.value)}
                  placeholder="e.g. (1)"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Display Names */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Display Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="display_name_en">Display Name (English) *</Label>
              <Input
                id="display_name_en"
                value={displayNameEn}
                onChange={(e) => setDisplayNameEn(e.target.value)}
                placeholder="e.g. Murder"
              />
            </div>
            <div>
              <Label htmlFor="display_name_gu">Display Name (Gujarati)</Label>
              <Input
                id="display_name_gu"
                value={displayNameGu}
                onChange={(e) => setDisplayNameGu(e.target.value)}
                placeholder="Gujarati name"
              />
            </div>
            <div>
              <Label htmlFor="short_description_md">Description</Label>
              <textarea
                id="short_description_md"
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={shortDescriptionMd}
                onChange={(e) => setShortDescriptionMd(e.target.value)}
                placeholder="Brief description of the offence..."
              />
            </div>
          </CardContent>
        </Card>

        {/* Classification */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Classification</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
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
                <Label htmlFor="compoundable">Compoundable</Label>
                <select
                  id="compoundable"
                  value={compoundable}
                  onChange={(e) => setCompoundable(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                  <option value="with court permission">
                    With Court Permission
                  </option>
                </select>
              </div>
              <div>
                <Label htmlFor="triable_by">Triable By</Label>
                <Input
                  id="triable_by"
                  value={triableBy}
                  onChange={(e) => setTriableBy(e.target.value)}
                  placeholder="e.g. Court of Session"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Punishment */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Punishment</CardTitle>
          </CardHeader>
          <CardContent>
            <textarea
              id="punishment"
              className="flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={punishment}
              onChange={(e) => setPunishment(e.target.value)}
              placeholder="e.g. Death or imprisonment for life, and fine"
            />
          </CardContent>
        </Card>

        {/* References */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">References</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="schedule_reference">Schedule Reference</Label>
              <Input
                id="schedule_reference"
                value={scheduleReference}
                onChange={(e) => setScheduleReference(e.target.value)}
                placeholder="e.g. First Schedule, Part I"
              />
            </div>
            <div>
              <Label htmlFor="related_codes">
                Related Offence Codes (comma-separated)
              </Label>
              <Input
                id="related_codes"
                value={relatedCodes}
                onChange={(e) => setRelatedCodes(e.target.value)}
                placeholder="e.g. BNS_S109, BNS_S115"
              />
            </div>
            <div>
              <Label htmlFor="special_acts">
                Special Acts (comma-separated)
              </Label>
              <Input
                id="special_acts"
                value={specialActs}
                onChange={(e) => setSpecialActs(e.target.value)}
                placeholder="e.g. POCSO, SC/ST Act"
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-3">
          <Button
            type="submit"
            disabled={createOffence.isPending}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            {createOffence.isPending ? "Creating..." : "Create Offence"}
          </Button>
          <Link href="/dashboard/kb">
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </Link>
        </div>
      </form>
    </div>
  );
}
