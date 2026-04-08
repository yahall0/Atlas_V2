"""Tests for app.core.pii — mask_pii_for_role, victim identity masking."""

from __future__ import annotations

import pytest

from app.core.pii import mask_pii_for_role


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_fir(**kwargs) -> dict:
    base = {
        "id": "test-uuid",
        "fir_number": "FIR001",
        "district": "Ahmedabad",
        "complainant_name": "Dinaben Rameshbhai Patel",
        "narrative": "The accused stole cash. Aadhaar: 1234 5678 9012. Phone: 9876543210.",
        "raw_text": "raw aadhaar 1234 5678 9012 phone 9876543210.",
        "place_address": "123 Main Street, Ahmedabad",
        "primary_sections": ["379"],
        "complainants": [{"name": "Dinaben Patel", "address": "123 Main St"}],
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Role-based PII masking
# ---------------------------------------------------------------------------


def test_sp_no_masking():
    fir = make_fir()
    result = mask_pii_for_role(fir, "SP")
    assert result["complainant_name"] == "Dinaben Rameshbhai Patel"
    # Aadhaar / phone NOT redacted for SP (except victim protection which doesn't apply here)
    assert "1234 5678 9012" in result["narrative"]


def test_admin_no_masking():
    fir = make_fir()
    result = mask_pii_for_role(fir, "ADMIN")
    assert result["complainant_name"] == "Dinaben Rameshbhai Patel"


def test_io_name_not_masked():
    fir = make_fir()
    result = mask_pii_for_role(fir, "IO")
    assert result["complainant_name"] == "Dinaben Rameshbhai Patel"


def test_sho_name_not_masked():
    fir = make_fir()
    result = mask_pii_for_role(fir, "SHO")
    assert result["complainant_name"] == "Dinaben Rameshbhai Patel"


def test_dysp_name_masked():
    fir = make_fir()
    result = mask_pii_for_role(fir, "DYSP")
    assert result["complainant_name"] == "Dinaben P."


def test_readonly_name_masked():
    fir = make_fir()
    result = mask_pii_for_role(fir, "READONLY")
    name = result["complainant_name"]
    assert name.endswith(".")
    assert len(name.split()) >= 2


def test_io_aadhaar_redacted_in_narrative():
    fir = make_fir()
    result = mask_pii_for_role(fir, "IO")
    assert "[AADHAAR]" in result["narrative"]
    assert "1234 5678 9012" not in result["narrative"]


def test_io_phone_redacted_in_narrative():
    fir = make_fir()
    result = mask_pii_for_role(fir, "IO")
    assert "[PHONE-" in result["narrative"]
    assert "9876543210" not in result["narrative"]


def test_original_dict_not_mutated():
    fir = make_fir()
    original_name = fir["complainant_name"]
    mask_pii_for_role(fir, "DYSP")
    assert fir["complainant_name"] == original_name  # original dict unchanged


# ---------------------------------------------------------------------------
# Victim identity masking (BNS Chapter V)
# ---------------------------------------------------------------------------


def test_victim_masking_sexual_offence_all_roles():
    """Complainant name must be masked for ALL roles if sections include rape."""
    fir = make_fir(primary_sections=["376"])
    for role in ("SP", "ADMIN", "IO", "SHO", "DYSP", "READONLY"):
        result = mask_pii_for_role(fir, role)
        assert result["complainant_name"] == "[VICTIM-PROTECTED]", \
            f"Role {role} did not mask victim for section 376"


def test_victim_masking_bns_section_63():
    fir = make_fir(primary_sections=["63"])
    result = mask_pii_for_role(fir, "SP")
    assert result["complainant_name"] == "[VICTIM-PROTECTED]"


def test_victim_masking_address_protected():
    fir = make_fir(primary_sections=["376"])
    result = mask_pii_for_role(fir, "ADMIN")
    assert result["place_address"] == "[ADDRESS-PROTECTED]"


def test_victim_masking_complainants_list():
    fir = make_fir(primary_sections=["376"])
    result = mask_pii_for_role(fir, "ADMIN")
    for c in result["complainants"]:
        assert c["name"] == "[VICTIM-PROTECTED]"
        assert c["address"] == "[ADDRESS-PROTECTED]"


def test_no_victim_masking_for_non_sexual_offence():
    fir = make_fir(primary_sections=["302"])  # murder
    result = mask_pii_for_role(fir, "SP")
    assert result["complainant_name"] != "[VICTIM-PROTECTED]"


def test_mixed_sections_triggers_victim_masking():
    """If any section is in the sexual offence list, victim must be masked."""
    fir = make_fir(primary_sections=["302", "376"])
    result = mask_pii_for_role(fir, "SP")
    assert result["complainant_name"] == "[VICTIM-PROTECTED]"
