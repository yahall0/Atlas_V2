from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import Json


ROOT = Path("/home/user/app")
RESULT_PATH = ROOT / "result.json"
DATABASE_URL = os.environ["DATABASE_URL"]

DEMO_CHARGESHEET_ID = "c7c0c8e0-4e3b-4f1f-9db8-8d2c7f4e1a01"
DEMO_VALIDATION_ID = "d7c0c8e0-4e3b-4f1f-9db8-8d2c7f4e1a02"
DEMO_EVIDENCE_ID = "e7c0c8e0-4e3b-4f1f-9db8-8d2c7f4e1a03"


def _load_demo_fir() -> dict:
    with RESULT_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _ensure_seed_users(cursor) -> None:
    users_sql = """
        INSERT INTO users (username, password_hash, full_name, role, district, police_station, is_active)
        VALUES
          ('admin', '$2b$12$M0GZyLyHMwJ97TXtN8rWceqZC6NgZf9Sa9luiO3Ldyj3BSgG1D4nu', 'ATLAS Admin', 'ADMIN', 'Ahmedabad', NULL, TRUE),
          ('io_sanand', '$2b$12$Kr4pYSDrDCnqmprDmLNXJONzWdpEBxakYNsZaiMdiXcie9yBzPc7i', 'Sanand IO', 'IO', 'Ahmedabad', 'Sanand', TRUE),
          ('sho_sanand', '$2b$12$QMRP38Xzg.d4g/atPcvCHurKI3gjfEVcj1ZRzDc4MIWbkt5.C2w/C', 'Sanand SHO', 'SHO', 'Ahmedabad', 'Sanand', TRUE)
        ON CONFLICT (username) DO NOTHING;
    """
    cursor.execute(users_sql)


def _seed_fir(cursor, fir: dict) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stolen_property = fir.get("stolen_property")
    if stolen_property is not None:
        stolen_property = Json(stolen_property)
    cursor.execute(
        """
        INSERT INTO firs (
            id, fir_number, police_station, district,
            fir_date, primary_act, primary_sections, sections_flagged,
            complainant_name, accused_name, gpf_no,
            occurrence_from, occurrence_to, time_from, time_to,
            info_received_date, info_received_time, info_type,
            place_distance_km, place_address,
            complainant_father_name, complainant_age,
            complainant_nationality, complainant_occupation,
            io_name, io_rank, io_number, officer_name,
            dispatch_date, dispatch_time,
            stolen_property, completeness_pct,
            narrative, raw_text, source_system,
            created_at, status, nlp_metadata, nlp_classification,
            nlp_confidence, nlp_classified_at, nlp_classified_by, nlp_model_version
        ) VALUES (
            %(id)s, %(fir_number)s, %(police_station)s, %(district)s,
            %(fir_date)s, %(primary_act)s, %(primary_sections)s, %(sections_flagged)s,
            %(complainant_name)s, %(accused_name)s, %(gpf_no)s,
            %(occurrence_from)s, %(occurrence_to)s, %(time_from)s, %(time_to)s,
            %(info_received_date)s, %(info_received_time)s, %(info_type)s,
            %(place_distance_km)s, %(place_address)s,
            %(complainant_father_name)s, %(complainant_age)s,
            %(complainant_nationality)s, %(complainant_occupation)s,
            %(io_name)s, %(io_rank)s, %(io_number)s, %(officer_name)s,
            %(dispatch_date)s, %(dispatch_time)s,
            %(stolen_property)s, %(completeness_pct)s,
            %(narrative)s, %(raw_text)s, %(source_system)s,
            %(created_at)s, %(status)s, %(nlp_metadata)s, %(nlp_classification)s,
            %(nlp_confidence)s, %(nlp_classified_at)s, %(nlp_classified_by)s, %(nlp_model_version)s
        )
        ON CONFLICT (id) DO UPDATE SET
            fir_number = EXCLUDED.fir_number,
            police_station = EXCLUDED.police_station,
            district = EXCLUDED.district,
            fir_date = EXCLUDED.fir_date,
            primary_act = EXCLUDED.primary_act,
            primary_sections = EXCLUDED.primary_sections,
            sections_flagged = EXCLUDED.sections_flagged,
            complainant_name = EXCLUDED.complainant_name,
            accused_name = EXCLUDED.accused_name,
            gpf_no = EXCLUDED.gpf_no,
            occurrence_from = EXCLUDED.occurrence_from,
            occurrence_to = EXCLUDED.occurrence_to,
            time_from = EXCLUDED.time_from,
            time_to = EXCLUDED.time_to,
            info_received_date = EXCLUDED.info_received_date,
            info_received_time = EXCLUDED.info_received_time,
            info_type = EXCLUDED.info_type,
            place_distance_km = EXCLUDED.place_distance_km,
            place_address = EXCLUDED.place_address,
            complainant_father_name = EXCLUDED.complainant_father_name,
            complainant_age = EXCLUDED.complainant_age,
            complainant_nationality = EXCLUDED.complainant_nationality,
            complainant_occupation = EXCLUDED.complainant_occupation,
            io_name = EXCLUDED.io_name,
            io_rank = EXCLUDED.io_rank,
            io_number = EXCLUDED.io_number,
            officer_name = EXCLUDED.officer_name,
            dispatch_date = EXCLUDED.dispatch_date,
            dispatch_time = EXCLUDED.dispatch_time,
            stolen_property = EXCLUDED.stolen_property,
            completeness_pct = EXCLUDED.completeness_pct,
            narrative = EXCLUDED.narrative,
            raw_text = EXCLUDED.raw_text,
            source_system = EXCLUDED.source_system,
            status = EXCLUDED.status,
            nlp_metadata = EXCLUDED.nlp_metadata,
            nlp_classification = EXCLUDED.nlp_classification,
            nlp_confidence = EXCLUDED.nlp_confidence,
            nlp_classified_at = EXCLUDED.nlp_classified_at,
            nlp_classified_by = EXCLUDED.nlp_classified_by,
            nlp_model_version = EXCLUDED.nlp_model_version
        ;
        """,
        {
            **fir,
            "created_at": now,
            "status": "classified",
            "stolen_property": stolen_property,
            "nlp_metadata": Json({
                "mismatch": False,
                "section_inferred_category": "theft",
                "nlp_category": "theft",
                "nlp_confidence": 0.97,
            }),
            "nlp_classification": "theft",
            "nlp_confidence": 0.97,
            "nlp_classified_at": now,
            "nlp_classified_by": "section_map",
            "nlp_model_version": "demo-seed",
        },
    )

    cursor.execute("DELETE FROM complainants WHERE fir_id = %s", (fir["id"],))
    cursor.execute("DELETE FROM accused WHERE fir_id = %s", (fir["id"],))

    for complainant in fir.get("complainants", []):
        cursor.execute(
            """
            INSERT INTO complainants (id, fir_id, name, father_name, age, address)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                fir_id = EXCLUDED.fir_id,
                name = EXCLUDED.name,
                father_name = EXCLUDED.father_name,
                age = EXCLUDED.age,
                address = EXCLUDED.address
            """,
            (
                complainant.get("id"),
                fir["id"],
                complainant.get("name"),
                complainant.get("father_name"),
                complainant.get("age"),
                complainant.get("address"),
            ),
        )

    for accused in fir.get("accused", []):
        cursor.execute(
            """
            INSERT INTO accused (id, fir_id, name, age, address)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                fir_id = EXCLUDED.fir_id,
                name = EXCLUDED.name,
                age = EXCLUDED.age,
                address = EXCLUDED.address
            """,
            (
                accused.get("id"),
                fir["id"],
                accused.get("name"),
                accused.get("age"),
                accused.get("address"),
            ),
        )


def _seed_chargesheet(cursor, fir_id: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    parsed_json = {
        "fir_reference_number": "11192050250010",
        "court_name": "IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS, AHMEDABAD",
        "filing_date": "2026-03-15",
        "investigation_officer": "PSI R.K. Sharma, Navrangpura Police Station",
        "district": "Ahmedabad",
        "police_station": "Navrangpura",
    }
    cursor.execute(
        """
        INSERT INTO chargesheets (
            id, fir_id, filing_date, court_name,
            accused_json, charges_json, evidence_json, witnesses_json,
            io_name, raw_text, parsed_json,
            status, uploaded_by, district, police_station,
            created_at, updated_at
        ) VALUES (
            %(id)s, %(fir_id)s, %(filing_date)s, %(court_name)s,
            %(accused_json)s, %(charges_json)s, %(evidence_json)s, %(witnesses_json)s,
            %(io_name)s, %(raw_text)s, %(parsed_json)s,
            %(status)s, %(uploaded_by)s, %(district)s, %(police_station)s,
            %(created_at)s, %(updated_at)s
        )
        ON CONFLICT (id) DO UPDATE SET
            fir_id = EXCLUDED.fir_id,
            filing_date = EXCLUDED.filing_date,
            court_name = EXCLUDED.court_name,
            accused_json = EXCLUDED.accused_json,
            charges_json = EXCLUDED.charges_json,
            evidence_json = EXCLUDED.evidence_json,
            witnesses_json = EXCLUDED.witnesses_json,
            io_name = EXCLUDED.io_name,
            raw_text = EXCLUDED.raw_text,
            parsed_json = EXCLUDED.parsed_json,
            status = EXCLUDED.status,
            uploaded_by = EXCLUDED.uploaded_by,
            district = EXCLUDED.district,
            police_station = EXCLUDED.police_station,
            updated_at = EXCLUDED.updated_at
        ;
        """,
        {
            "id": DEMO_CHARGESHEET_ID,
            "fir_id": fir_id,
            "filing_date": "2026-03-15",
            "court_name": "IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS, AHMEDABAD",
            "accused_json": Json([
                {"name": "Rajesh Kumar Patel", "age": 32, "address": "45 MG Road, Navrangpura, Ahmedabad", "role": "Primary accused"},
                {"name": "Sunil Bhatt", "age": 28, "address": "12 SG Highway, Ahmedabad", "role": "Accomplice"},
            ]),
            "charges_json": Json([
                {"section": "303", "act": "BNS", "description": "Theft of moveable property"},
                {"section": "34", "act": "BNS", "description": "Common intention"},
            ]),
            "evidence_json": Json([
                {"type": "Documentary", "description": "Original FIR copy", "status": "collected"},
                {"type": "Digital", "description": "CCTV footage from premises", "status": "pending"},
                {"type": "Forensic", "description": "Fingerprint analysis report", "status": "collected"},
            ]),
            "witnesses_json": Json([
                {"name": "Kavita Ramesh", "role": "Complainant", "statement_summary": "Filed the original complaint"},
                {"name": "Sunil Bhai Patel", "role": "Eye-witness", "statement_summary": "Saw the accused at the scene"},
            ]),
            "io_name": "PSI R.K. Sharma, Navrangpura Police Station",
            "raw_text": "Demo chargesheet for ATLAS Space deployment.",
            "parsed_json": Json(parsed_json),
            "status": "parsed",
            "uploaded_by": "admin",
            "district": "Ahmedabad",
            "police_station": "Navrangpura",
            "created_at": now,
            "updated_at": now,
        },
    )

    cursor.execute(
        """
        INSERT INTO validation_reports (
            id, chargesheet_id, fir_id, findings_json, summary_json,
            overall_status, validated_by, created_at, updated_at
        ) VALUES (
            %(id)s, %(chargesheet_id)s, %(fir_id)s, %(findings_json)s, %(summary_json)s,
            %(overall_status)s, %(validated_by)s, %(created_at)s, %(updated_at)s
        )
        ON CONFLICT (id) DO UPDATE SET
            chargesheet_id = EXCLUDED.chargesheet_id,
            fir_id = EXCLUDED.fir_id,
            findings_json = EXCLUDED.findings_json,
            summary_json = EXCLUDED.summary_json,
            overall_status = EXCLUDED.overall_status,
            validated_by = EXCLUDED.validated_by,
            updated_at = EXCLUDED.updated_at
        ;
        """,
        {
            "id": DEMO_VALIDATION_ID,
            "chargesheet_id": DEMO_CHARGESHEET_ID,
            "fir_id": fir_id,
            "findings_json": Json([
                {
                    "rule_id": "RULE_1",
                    "severity": "WARNING",
                    "section": "303",
                    "description": "Sample finding for demo dashboard.",
                    "recommendation": "Review section mapping.",
                    "confidence": 0.91,
                }
            ]),
            "summary_json": Json({
                "total_findings": 1,
                "critical": 0,
                "errors": 0,
                "warnings": 1,
                "sections_validated": 2,
                "evidence_coverage_pct": 66.7,
            }),
            "overall_status": "warnings",
            "validated_by": "admin",
            "created_at": now,
            "updated_at": now,
        },
    )

    cursor.execute(
        """
        INSERT INTO evidence_gap_reports (
            id, chargesheet_id, fir_id, crime_category, gaps_json, present_json,
            coverage_pct, total_gaps, analyzed_by, created_at
        ) VALUES (
            %(id)s, %(chargesheet_id)s, %(fir_id)s, %(crime_category)s, %(gaps_json)s, %(present_json)s,
            %(coverage_pct)s, %(total_gaps)s, %(analyzed_by)s, %(created_at)s
        )
        ON CONFLICT (id) DO UPDATE SET
            chargesheet_id = EXCLUDED.chargesheet_id,
            fir_id = EXCLUDED.fir_id,
            crime_category = EXCLUDED.crime_category,
            gaps_json = EXCLUDED.gaps_json,
            present_json = EXCLUDED.present_json,
            coverage_pct = EXCLUDED.coverage_pct,
            total_gaps = EXCLUDED.total_gaps,
            analyzed_by = EXCLUDED.analyzed_by
        ;
        """,
        {
            "id": DEMO_EVIDENCE_ID,
            "chargesheet_id": DEMO_CHARGESHEET_ID,
            "fir_id": fir_id,
            "crime_category": "theft",
            "gaps_json": Json([
                {
                    "category": "CCTV",
                    "tier": "rule_based",
                    "severity": "warning",
                    "recommendation": "Verify footage chain of custody.",
                    "confidence": 0.82,
                }
            ]),
            "present_json": Json([
                {
                    "category": "FIR",
                    "source_text": "Original FIR copy",
                    "confidence": 0.98,
                }
            ]),
            "coverage_pct": 66.7,
            "total_gaps": 1,
            "analyzed_by": "admin",
            "created_at": now,
        },
    )


def main() -> None:
    fir = _load_demo_fir()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            _ensure_seed_users(cursor)
            _seed_fir(cursor, fir)
            _seed_chargesheet(cursor, fir["id"])
        conn.commit()
    print("Demo database seeded.")


if __name__ == "__main__":
    main()