# ADR-D01: Modular monolith architecture

**Status:** Accepted
**Date:** 2026-04-06
**Deciders:** Amit (Lead), Aditya (Backend/ML), Prishav (Frontend/NLP)

## Context
- 2-developer team, 11-month timeline
- 4 modules: SOP Assistant, FIR Review, Charge-Sheet Review, Dashboard
- 5 external integrations: eGujCop, ICJS, e-Prison, NCRB, SCRB
- Must deploy on-premise at 6 district hub servers
- All data confidential — no external API calls permitted

## Decision
Modular monolith deployed as Docker Compose services on district hub servers. Police stations access via browser (no local installation). Three AI model tiers run on the hub:
- Tesseract OCR (CPU) — FIR document ingestion
- IndicBERT/MuRIL (CPU) — classification and NER
- Sarvam-30B quantized (GPU) — SOP conversational assistant

## Consequences
- Simple deployment: one docker-compose.yml per district
- Single repo, easy debugging for 2-person team
- Cannot independently deploy individual modules
- Revisit if team grows beyond 5 developers or system scales beyond Gujarat
