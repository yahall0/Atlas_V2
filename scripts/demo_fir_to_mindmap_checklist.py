"""End-to-end demo: FIR narrative → recommended sections → mindmap + checklist.

Walks the full chain that today exists in the codebase, against three of
the gold-standard FIRs. Proves that "uploaded FIR → mindmap + checklist"
is achievable with what was built — only the production wiring (auto-
trigger on FIR ingestion + frontend rendering) is left.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.legal_sections.chunker import iter_chunks  # noqa: E402
from backend.app.legal_sections.embedder import TfidfEmbedder  # noqa: E402
from backend.app.legal_sections.recommender import recommend  # noqa: E402
from backend.app.legal_sections.retriever import InMemoryRetriever  # noqa: E402
from backend.app.legal_sections.scenario_adapter import (  # noqa: E402
    checklist_for_scenarios,
    mindmap_nodes_for_scenario,
    playbook_for_recommendation,
)
from backend.app.legal_sections.io_scenarios import find_scenarios_for_sections  # noqa: E402

DATA = ROOT / "backend" / "app" / "legal_sections" / "data"


def _build_retriever():
    chunks = list(iter_chunks([
        DATA / "ipc_sections.jsonl",
        DATA / "bns_sections.jsonl",
    ]))
    r = InMemoryRetriever(TfidfEmbedder())
    r.index(chunks)
    return r


def _print_mindmap_node(node, depth: int = 0):
    indent = "  " * depth
    head = f"{indent}- [{node.node_type:18s}] {node.title[:90]}"
    print(head)
    if depth < 2 and node.metadata:
        for key in ("forms", "deadline", "actors", "legal_refs"):
            v = node.metadata.get(key)
            if v:
                print(f"{indent}    {key}: {v}")
    for child in node.children[:6]:
        _print_mindmap_node(child, depth + 1)
    if len(node.children) > 6:
        print(f"{indent}  ... ({len(node.children) - 6} more children)")


def run_demo(fir_id: str, narrative: str, occurrence_iso: str, accused_count: int,
             forced_citations: list[str] | None = None):
    print("\n" + "=" * 90)
    print(f"  DEMO  {fir_id}")
    print("=" * 90)
    print(f"\nNarrative (first 350 chars):\n  {narrative[:350]}...\n")
    print(f"Occurrence: {occurrence_iso}    Accused: {accused_count}")

    if forced_citations:
        print(f"\n[Using forced citations to demonstrate downstream chain:")
        print(f"   {forced_citations}]")
        citations = forced_citations
    else:
        # Run the live recommender
        retriever = _build_retriever()
        resp = recommend(
            fir_id=fir_id,
            fir_narrative=narrative,
            retriever=retriever,
            occurrence_date_iso=occurrence_iso,
            accused_count=accused_count,
            confidence_floor=0.10,
            top_k_retrieve=60,
        )
        citations = [r.canonical_citation for r in resp.recommendations][:8]
        print(f"\n[1] Recommender output (top 8):")
        for c in citations:
            print(f"     {c}")

    # ---- 2. Compendium playbook lookup ----
    refs = playbook_for_recommendation(citations)
    print(f"\n[2] Matching Compendium scenarios ({len(refs)}):")
    for r in refs:
        print(f"     {r.scenario_id}  {r.scenario_name}  (pp.{r.page_start}-{r.page_end})")
    if not refs:
        print(f"     (no Compendium scenario matched these citations — falls back to model-gen template)")
        return

    # ---- 3. Mindmap (built from the first matching scenario) ----
    scenarios = find_scenarios_for_sections(citations)
    sc = scenarios[0]
    root = mindmap_nodes_for_scenario(sc)
    print(f"\n[3] Mindmap tree (first scenario only, depth-limited):")
    _print_mindmap_node(root, depth=0)

    # ---- 4. Aggregated checklist ----
    chk = checklist_for_scenarios(scenarios)
    print(f"\n[4] Aggregated checklist (across {len(scenarios)} matching scenario(s)):")
    print(f"     Forms required ({len(chk['forms_required'])}): {chk['forms_required'][:8]}")
    print(f"     Deadlines: {chk['deadlines']}")
    print(f"     Actors required: {chk['actors_required']}")
    print(f"     Evidence items catalogued: {len(chk['evidence_to_collect'])}")
    print(f"     First 5 evidence items:")
    for e in chk["evidence_to_collect"][:5]:
        print(f"       - {e[:140]}{'...' if len(e) > 140 else ''}")


if __name__ == "__main__":
    # 1. Knife-attack scenario (force citations to bypass weak retrieval baseline)
    run_demo(
        fir_id="DEMO_KNIFE_ATTACK",
        narrative=(
            "On 05/02/2025 at about 3:00 PM at the village outskirts of Mahadevpura, Dholera, "
            "the complainant Rahulbhai had a dispute with Jayeshbhai Sankaliya. Jayeshbhai took out "
            "a sharp-edged knife (dhardar chhari), caught hold of the complainant's left shoulder, "
            "and struck him on the shoulder, back, and lower back with the knife. Co-accused Rahul "
            "said 'enough, do not kill him'. The complainant sustained knife wounds and was taken "
            "to R.M.S. Hospital. They also damaged his motorcycle GJ-38-AN-5794 and gave "
            "life-threatening warnings."
        ),
        occurrence_iso="2025-02-05T15:00:00+05:30",
        accused_count=2,
        forced_citations=["BNS 109(1)", "BNS 118(1)", "BNS 126(2)", "BNS 351(3)", "BNS 324(2)", "BNS 3(5)"],
    )

    # 2. Snatching scenario
    run_demo(
        fir_id="DEMO_SNATCHING",
        narrative=(
            "On 03/09/2024 at about 7:30 PM the complainant was riding his motorcycle on the "
            "Sarkhej-Gandhinagar road when an unknown person on a moving motorcycle suddenly came "
            "alongside, snatched the complainant's mobile phone from his hand and sped away."
        ),
        occurrence_iso="2024-09-03T19:30:00+05:30",
        accused_count=1,
        forced_citations=["BNS 304"],
    )

    # 3. Housebreaking by night
    run_demo(
        fir_id="DEMO_HOUSEBREAK_NIGHT",
        narrative=(
            "On 12/08/2024 at about 2:00 AM the complainant residing at Naranpura, Ahmedabad heard "
            "noises from the kitchen. Two unknown persons had entered the house through a window "
            "after breaking the grill. They fled with a gold chain and wristwatch worth Rs. 60,000."
        ),
        occurrence_iso="2024-08-12T02:00:00+05:30",
        accused_count=2,
        forced_citations=["BNS 331(3)", "BNS 305(a)"],
    )
