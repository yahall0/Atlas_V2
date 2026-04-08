"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  ScrollText,
  User,
  Scale,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Download,
  Eye,
} from "lucide-react";

// ─── Dummy Data ──────────────────────────────────────────────────────────────
const DUMMY_FIRS = [
  {
    id: "cs-001",
    fir_number: "11192050250010",
    district: "Ahmedabad",
    police_station: "Navrangpura",
    primary_act: "BNS",
    primary_sections: ["303", "34"],
    section_category: "theft",
    nlp_classification: "theft",
    status: "review_needed",
    complainant: "Rajesh Kumar Patel",
    accused: "Unknown (2)",
    date: "2026-04-06",
    narrative_summary: "Alleged theft of gold jewellery worth ₹1.8L from locked residence between 14:00–18:00 hrs.",
  },
  {
    id: "cs-002",
    fir_number: "11192050250021",
    district: "Surat",
    police_station: "Adajan",
    primary_act: "IPC",
    primary_sections: ["420", "34"],
    section_category: "fraud",
    nlp_classification: "fraud",
    status: "classified",
    complainant: "Meera Suresh Shah",
    accused: "Ramesh Desai",
    date: "2026-04-05",
    narrative_summary: "Cheating through false promise of employment abroad; ₹3.5L collected as processing fees.",
  },
  {
    id: "cs-003",
    fir_number: "11192050250034",
    district: "Vadodara",
    police_station: "Sayajigunj",
    primary_act: "BNS",
    primary_sections: ["101", "34"],
    section_category: "murder",
    nlp_classification: "assault",
    status: "review_needed",
    complainant: "Anita Dilip Mehta",
    accused: "Suresh Mehta",
    date: "2026-04-04",
    narrative_summary: "Fatal assault during domestic dispute. Victim succumbed to head injuries at SSGH.",
  },
];

const SECTION_DETAILS: Record<string, { title: string; description: string; penalty: string }> = {
  "303": { title: "BNS §303 – Theft", description: "Whoever intending to take dishonestly any moveable property out of the possession of any person without that person's consent.", penalty: "Imprisonment up to 3 years, or fine, or both." },
  "34":  { title: "BNS §34 / IPC §34 – Common Intention", description: "When a criminal act is done by several persons in furtherance of the common intention of all.", penalty: "Each person liable as if done by them alone." },
  "420": { title: "IPC §420 – Cheating", description: "Whoever cheats and thereby dishonestly induces the delivery of property or alteration of a signed document.", penalty: "Imprisonment up to 7 years and fine." },
  "101": { title: "BNS §101 – Culpable Homicide amounting to Murder", description: "Culpable homicide is murder if the act is done with intention of causing death.", penalty: "Death or imprisonment for life." },
};

const EVIDENCE_ITEMS = [
  { id: 1, type: "Documentary", description: "Original FIR copy", status: "collected" },
  { id: 2, type: "Physical", description: "CCTV footage from premises", status: "pending" },
  { id: 3, type: "Witness Statement", description: "Statement of complainant (Ex. 1)", status: "collected" },
  { id: 4, type: "Forensic", description: "Fingerprint analysis report", status: "pending" },
];

const WITNESS_LIST = [
  { name: "Sunil Bhai Patel", role: "Eye-witness", contact: "9876543210", statement: "recorded" },
  { name: "Kavita Ramesh", role: "Complainant", contact: "9876512345", statement: "recorded" },
  { name: "PC Amit Sharma (3412)", role: "Investigating Officer", contact: "PS-Direct", statement: "pending" },
];

// ─── Component ───────────────────────────────────────────────────────────────
export default function ChargesheetPage() {
  const [selected, setSelected] = useState(DUMMY_FIRS[0]);
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [activeTab, setActiveTab] = useState<"sections" | "evidence" | "witnesses" | "preview">("sections");

  function handleGenerate() {
    setGenerating(true);
    setGenerated(false);
    setTimeout(() => {
      setGenerating(false);
      setGenerated(true);
      setActiveTab("preview");
    }, 2200);
  }

  const mismatch = selected.nlp_classification !== selected.section_category;

  return (
    <div className="flex gap-6 h-[calc(100vh-8rem)]">
      {/* Left: FIR list */}
      <div className="w-72 shrink-0 flex flex-col gap-3">
        <h2 className="text-base font-semibold text-slate-700">Pending Chargesheets</h2>
        <div className="flex flex-col gap-2 overflow-y-auto">
          {DUMMY_FIRS.map((fir) => (
            <button
              key={fir.id}
              onClick={() => { setSelected(fir); setGenerated(false); setActiveTab("sections"); }}
              className={`text-left p-3.5 rounded-xl border transition-all ${
                selected.id === fir.id
                  ? "border-blue-500 bg-blue-50 shadow-sm"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs text-slate-500 truncate">{fir.fir_number}</span>
                {fir.nlp_classification !== fir.section_category && (
                  <AlertCircle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                )}
              </div>
              <p className="text-sm font-medium text-slate-800 leading-snug">{fir.district} — {fir.police_station}</p>
              <p className="text-xs text-slate-500 mt-0.5 truncate">{fir.narrative_summary}</p>
              <div className="flex gap-1.5 mt-2">
                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                  fir.status === "review_needed" ? "bg-amber-100 text-amber-700" : "bg-green-100 text-green-700"
                }`}>
                  {fir.status === "review_needed" ? "⚠ Review" : "✓ Classified"}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600">{fir.primary_act}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Right: Chargesheet builder */}
      <div className="flex-1 flex flex-col min-w-0 gap-4">
        {/* FIR header */}
        <Card className="border-slate-200 shadow-sm">
          <CardContent className="py-4 px-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <ScrollText className="w-4 h-4 text-blue-600" />
                  <h3 className="font-semibold text-slate-800">FIR {selected.fir_number}</h3>
                  {mismatch && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" /> NLP mismatch detected
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-500">{selected.district} · {selected.police_station} · {selected.date}</p>
                <p className="text-sm text-slate-600 mt-1.5 max-w-xl">{selected.narrative_summary}</p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-xs text-slate-400">Complainant</p>
                <p className="text-sm font-medium">{selected.complainant}</p>
                <p className="text-xs text-slate-400 mt-1">Accused</p>
                <p className="text-sm font-medium">{selected.accused}</p>
              </div>
            </div>
            {mismatch && (
              <div className="mt-3 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
                <strong>Mismatch:</strong> Sections imply <strong>{selected.section_category}</strong>, but NLP narrative analysis predicts <strong>{selected.nlp_classification}</strong>. Verify sections before generating chargesheet.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
          {(["sections", "evidence", "witnesses", "preview"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all capitalize ${
                activeTab === tab ? "bg-white shadow-sm text-slate-800" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab === "preview" ? "📄 Preview" : tab === "sections" ? "⚖ Sections" : tab === "evidence" ? "🔍 Evidence" : "👤 Witnesses"}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === "sections" && (
            <div className="space-y-3">
              {selected.primary_sections.map((sec) => {
                const detail = SECTION_DETAILS[sec];
                return (
                  <Card key={sec} className="border-slate-200 shadow-sm">
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center shrink-0">
                          <Scale className="w-4 h-4 text-blue-600" />
                        </div>
                        <div className="flex-1">
                          <p className="font-semibold text-slate-800 text-sm">{detail?.title ?? `Section ${sec}`}</p>
                          <p className="text-xs text-slate-500 mt-1">{detail?.description ?? "—"}</p>
                          <p className="text-xs text-slate-600 mt-2 bg-slate-50 px-2 py-1 rounded"><strong>Penalty:</strong> {detail?.penalty ?? "—"}</p>
                        </div>
                        <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {activeTab === "evidence" && (
            <Card className="border-slate-200 shadow-sm">
              <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold text-slate-700">Evidence List</CardTitle></CardHeader>
              <CardContent>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-400 border-b">
                      <th className="text-left pb-2">#</th>
                      <th className="text-left pb-2">Type</th>
                      <th className="text-left pb-2">Description</th>
                      <th className="text-left pb-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {EVIDENCE_ITEMS.map((e) => (
                      <tr key={e.id} className="border-b last:border-0">
                        <td className="py-2.5 text-slate-400">{e.id}</td>
                        <td className="py-2.5 font-medium text-slate-700">{e.type}</td>
                        <td className="py-2.5 text-slate-600">{e.description}</td>
                        <td className="py-2.5">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            e.status === "collected" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                          }`}>{e.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {activeTab === "witnesses" && (
            <div className="space-y-3">
              {WITNESS_LIST.map((w) => (
                <Card key={w.name} className="border-slate-200 shadow-sm">
                  <CardContent className="p-4 flex items-center gap-4">
                    <div className="w-9 h-9 bg-slate-100 rounded-full flex items-center justify-center shrink-0">
                      <User className="w-4 h-4 text-slate-500" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-sm text-slate-800">{w.name}</p>
                      <p className="text-xs text-slate-500">{w.role} · {w.contact}</p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      w.statement === "recorded" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                    }`}>Statement {w.statement}</span>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {activeTab === "preview" && generated && (
            <Card className="border-slate-200 shadow-sm">
              <CardHeader className="pb-2 flex-row items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-700">Draft Chargesheet</CardTitle>
                <Button size="sm" variant="outline" className="gap-1.5 text-xs">
                  <Download className="w-3.5 h-3.5" /> Export PDF
                </Button>
              </CardHeader>
              <CardContent>
                <div className="bg-slate-50 rounded-lg p-5 text-sm font-mono text-slate-700 space-y-3 whitespace-pre-wrap leading-relaxed border border-slate-200">
{`IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS
CHARGE-SHEET No.: CS/${selected.fir_number}/2026

FIR No.   : ${selected.fir_number}
P.S.      : ${selected.police_station}, ${selected.district}
U/S       : ${selected.primary_sections.join(", ")} ${selected.primary_act}
Date      : ${selected.date}

ACCUSED PERSON(S):
  Name    : ${selected.accused}
  Address : [Address on record]

COMPLAINANT:
  Name    : ${selected.complainant}

CHARGE:
  It is hereby charged that the accused committed an offence
  punishable under Section(s) ${selected.primary_sections.join(", ")} of the
  ${selected.primary_act} in connection with ${selected.narrative_summary}

EVIDENCE ON RECORD:
  1. Original FIR — Exhibit A
  2. Witness statements — Exhibits B–C
  3. Investigation report — Exhibit D

IO CERTIFICATION:
  I certify that the investigation has been completed and
  charge sheet is filed under Section 173 CrPC.

  [Signature of Investigating Officer]
  [Date: ${selected.date}]`}
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === "preview" && !generated && (
            <div className="flex flex-col items-center justify-center h-48 gap-3 text-slate-400">
              <Eye className="w-10 h-10 opacity-30" />
              <p className="text-sm">Generate chargesheet to preview the draft</p>
            </div>
          )}
        </div>

        {/* Action bar */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-200">
          <p className="text-xs text-slate-400">Draft based on FIR {selected.fir_number} · {selected.primary_act} · Sections: {selected.primary_sections.join(", ")}</p>
          <Button
            onClick={handleGenerate}
            disabled={generating}
            className="bg-blue-600 hover:bg-blue-700 text-white gap-2"
          >
            {generating ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Generating…</>
            ) : generated ? (
              <><CheckCircle2 className="w-4 h-4" /> Regenerate</>
            ) : (
              <><ScrollText className="w-4 h-4" /> Generate Chargesheet</>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
