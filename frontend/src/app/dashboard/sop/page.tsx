"use client";

import { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  BookOpen,
  Send,
  Bot,
  User,
  FileText,
  ChevronRight,
  Loader2,
  Lightbulb,
} from "lucide-react";

// ─── Dummy Context FIRs ──────────────────────────────────────────────────────
const CONTEXT_FIRS = [
  { id: "cs-001", fir_number: "11192050250010", district: "Ahmedabad", offence: "Theft (BNS §303)" },
  { id: "cs-002", fir_number: "11192050250021", district: "Surat", offence: "Fraud (IPC §420)" },
  { id: "cs-003", fir_number: "11192050250034", district: "Vadodara", offence: "Murder (BNS §101)" },
];

// ─── Dummy SOP responses ─────────────────────────────────────────────────────
const SOP_QA: Record<string, { answer: string; sources: string[] }> = {
  default: {
    answer: "I can help with procedural queries related to FIR investigation, arrest procedures, remand, bail, chargesheet timelines, and court processes under the Bharatiya Nagarik Suraksha Sanhita 2023. Please type your question or select a suggestion above.",
    sources: [],
  },
  arrest: {
    answer: `**Arrest Procedure under BNSS 2023**\n\nUnder Section 35 BNSS, a police officer may arrest without a warrant when:\n- The accused has committed or is suspected of committing a cognisable offence\n- There is reasonable apprehension of further offence\n\n**Mandatory steps:**\n1. Inform the accused of the grounds of arrest and right to bail (§35(1))\n2. Inform a nominated person immediately (§35(3))\n3. Medical examination within 24 hours\n4. Produce before magistrate within 24 hours (§57)\n\n**Arrest memo** must be prepared and signed by witness and arrested person.`,
    sources: ["BNSS §35", "BNSS §57", "BNSS §60A", "MHA SOP Circular 2024"],
  },
  remand: {
    answer: `**Remand Procedure**\n\nUnder BNSS §187, police custody remand:\n- Maximum 15 days initial remand\n- Extended to 60 days (offences punishable ≥ 10 years) or 90 days (death/life)\n- After 60/90 days without chargesheet → default bail accrues\n\n**To apply for remand:**\n1. Produce accused before magistrate with Arrest Memo\n2. Submit custody remand application with grounds\n3. Magistrate may allow up to 15-day PC remand in first instance\n\n**Note:** BNSS §187(2) allows remand to be authorised by Executive Magistrate if Judicial Magistrate unavailable.`,
    sources: ["BNSS §187", "BNSS §167 (old CrPC §167)", "High Court Circular 12/2024"],
  },
  chargesheet: {
    answer: `**Chargesheet Filing Timeline**\n\nUnder BNSS §193 (replaces CrPC §173):\n- **60 days** — offences punishable up to 7 years\n- **90 days** — offences punishable > 7 years / death\n\n**If chargesheet not filed within time:**\nAccused entitled to **default bail** under BNSS §187(2) on furnishing bail bond.\n\n**Chargesheet must contain:**\n1. Names of parties\n2. Nature and details of offence\n3. List of witnesses\n4. FIR copy\n5. Recovery memos / FSL reports\n6. Arrest & custody memos\n\nSubmit to court with forwarding letter signed by SHO.`,
    sources: ["BNSS §193", "BNSS §187(2)", "Gujarat Police Standing Order 45/2024"],
  },
  bail: {
    answer: `**Bail Application Procedure**\n\nFor bailable offences (First Schedule BNSS):\n- Bail is a right — station bail by SHO under BNSS §478\n\nFor non-bailable offences:\n- Application to Magistrate under BNSS §480\n- Sessions Court under BNSS §483 for serious offences\n\n**Anticipatory Bail:**\nUnder BNSS §482 (replaces CrPC §438) — application to Sessions or High Court.\n\n**IO's duties:**\n1. File opposition with grounds if bail likely to obstruct investigation\n2. Attach list of previous convictions if any\n3. File recovery status report`,
    sources: ["BNSS §478", "BNSS §480", "BNSS §482–483"],
  },
  witness: {
    answer: `**Witness Statement Recording**\n\nUnder BNSS §180 (replaces CrPC §161):\n- Statement recorded by IO in writing\n- Must be signed by the witness\n- **Audio-video recording mandatory** for victim of sexual offences (BNSS §180(3))\n\n**Protected Witnesses:**\nUnder BNSS §398, identity protection possible on court application.\n\n**Hostile Witness Procedure:**\n1. Apply to court under Evidence Act §154\n2. Permission to cross-examine own witness\n3. Record contradiction with prior statement`,
    sources: ["BNSS §180", "BNSS §398", "Indian Evidence Act §154"],
  },
};

function getResponse(question: string) {
  const q = question.toLowerCase();
  if (q.includes("arrest")) return SOP_QA.arrest;
  if (q.includes("remand") || q.includes("custody")) return SOP_QA.remand;
  if (q.includes("chargesheet") || q.includes("charge sheet") || q.includes("173") || q.includes("193")) return SOP_QA.chargesheet;
  if (q.includes("bail")) return SOP_QA.bail;
  if (q.includes("witness") || q.includes("statement") || q.includes("161") || q.includes("180")) return SOP_QA.witness;
  return {
    answer: `I don't have a specific SOP entry for that query in the current knowledge base. For detailed procedural guidance, please refer to the BNSS 2023, BSA 2023, or contact the State Police Legal Cell.\n\nYou may also try rephrasing your question around: arrest procedure, remand, chargesheet timelines, bail, or witness statements.`,
    sources: ["BNSS 2023 (Bharatiya Nagarik Suraksha Sanhita)"],
  };
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

const SUGGESTIONS = [
  "What is the arrest procedure under BNSS?",
  "How many days for chargesheet filing?",
  "How to apply for remand?",
  "When is the accused entitled to bail?",
  "How to record a witness statement?",
];

// ─── Component ───────────────────────────────────────────────────────────────
export default function SOPPage() {
  const [selectedFir, setSelectedFir] = useState(CONTEXT_FIRS[0]);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: SOP_QA.default.answer,
      sources: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  function handleSend(question?: string) {
    const q = question ?? input.trim();
    if (!q) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setThinking(true);
    setTimeout(() => {
      const resp = getResponse(q);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: resp.answer, sources: resp.sources },
      ]);
      setThinking(false);
    }, 900 + Math.random() * 600);
  }

  function renderMarkdown(text: string) {
    return text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^(\d+\.\s)/gm, "<br/>$1")
      .replace(/\n/g, "<br/>");
  }

  return (
    <div className="flex gap-5 h-[calc(100vh-8rem)]">
      {/* Left: Context panel */}
      <div className="w-64 shrink-0 flex flex-col gap-3">
        <h2 className="text-base font-semibold text-slate-700">FIR Context</h2>
        <div className="flex flex-col gap-2">
          {CONTEXT_FIRS.map((fir) => (
            <button
              key={fir.id}
              onClick={() => setSelectedFir(fir)}
              className={`text-left p-3 rounded-xl border transition-all ${
                selectedFir.id === fir.id
                  ? "border-blue-500 bg-blue-50 shadow-sm"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <p className="font-mono text-xs text-slate-400 truncate">{fir.fir_number}</p>
              <p className="text-sm font-medium text-slate-800 mt-0.5">{fir.district}</p>
              <p className="text-xs text-slate-500 mt-0.5">{fir.offence}</p>
              {selectedFir.id === fir.id && (
                <div className="flex items-center gap-1 mt-1.5 text-blue-600">
                  <ChevronRight className="w-3 h-3" />
                  <span className="text-[10px] font-medium">Active context</span>
                </div>
              )}
            </button>
          ))}
        </div>

        {/* Active context card */}
        <Card className="border-slate-200 shadow-sm mt-1">
          <CardHeader className="pb-1 pt-3 px-3">
            <CardTitle className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" /> Active FIR
            </CardTitle>
          </CardHeader>
          <CardContent className="px-3 pb-3 pt-0 space-y-1">
            <p className="text-xs text-slate-700"><strong>FIR:</strong> {selectedFir.fir_number}</p>
            <p className="text-xs text-slate-700"><strong>District:</strong> {selectedFir.district}</p>
            <p className="text-xs text-slate-700"><strong>Offence:</strong> {selectedFir.offence}</p>
          </CardContent>
        </Card>

        {/* Suggestions */}
        <div className="mt-1">
          <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5">
            <Lightbulb className="w-3.5 h-3.5" /> Suggested questions
          </p>
          <div className="flex flex-col gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => handleSend(s)}
                className="text-left text-xs text-slate-600 px-2.5 py-1.5 rounded-lg bg-slate-50 hover:bg-blue-50 hover:text-blue-700 border border-slate-200 hover:border-blue-300 transition-all"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right: Chat */}
      <div className="flex-1 flex flex-col min-w-0 gap-0">
        <Card className="flex-1 flex flex-col border-slate-200 shadow-sm overflow-hidden">
          <CardHeader className="py-3 px-4 border-b border-slate-100">
            <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-blue-600" />
              SOP Assistant
              <span className="text-xs font-normal text-slate-400 ml-1">· BNSS 2023 / BSA 2023</span>
            </CardTitle>
          </CardHeader>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "assistant" && (
                  <div className="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center shrink-0 mt-0.5">
                    <Bot className="w-4 h-4 text-blue-600" />
                  </div>
                )}
                <div className={`max-w-[78%] ${msg.role === "user" ? "order-first" : ""}`}>
                  <div className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white rounded-tr-sm"
                      : "bg-slate-100 text-slate-800 rounded-tl-sm"
                  }`}>
                    {msg.role === "assistant" ? (
                      <span dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                    ) : msg.content}
                  </div>
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5 px-1">
                      {msg.sources.map((s) => (
                        <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100 font-medium">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="w-7 h-7 bg-slate-200 rounded-full flex items-center justify-center shrink-0 mt-0.5">
                    <User className="w-4 h-4 text-slate-500" />
                  </div>
                )}
              </div>
            ))}

            {thinking && (
              <div className="flex gap-3 justify-start">
                <div className="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-blue-600" />
                </div>
                <div className="bg-slate-100 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-slate-100">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                placeholder={`Ask about procedures for FIR ${selectedFir.fir_number}…`}
                className="flex-1 text-sm border-slate-200 focus-visible:ring-blue-500"
                disabled={thinking}
              />
              <Button
                onClick={() => handleSend()}
                disabled={!input.trim() || thinking}
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white px-3"
              >
                {thinking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </Button>
            </div>
            <p className="text-[10px] text-slate-400 mt-1.5 text-center">
              Responses are based on BNSS/BSA 2023. Verify with official circulars before action.
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
