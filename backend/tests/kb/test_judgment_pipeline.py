"""Tests for judgment ingestion pipeline — T53-M-KB."""

import re
import pytest
from app.mindmap.kb.judgment_pipeline import (
    _classify_chunk,
    _BNS_PATTERN,
    COURT_AUTHORITY,
)


class TestChunkClassification:
    def test_operative_chunk(self):
        assert _classify_chunk("The appeal is hereby dismissed.") == "operative"
        assert _classify_chunk("conviction under Section 302 IPC upheld") == "operative"

    def test_facts_chunk(self):
        assert _classify_chunk("The prosecution case is that the accused stabbed the victim.") == "facts"
        assert _classify_chunk("Brief facts of the case are as follows") == "facts"

    def test_ratio_chunk(self):
        assert _classify_chunk("We hold that the principle of law is settled.") == "ratio"

    def test_obiter_chunk(self):
        assert _classify_chunk("We may note in passing that this is a wider issue.") == "obiter"

    def test_other_chunk(self):
        assert _classify_chunk("This is a generic paragraph with no keywords.") == "other"


class TestBNSSectionExtraction:
    def test_extracts_bns_section(self):
        text = "The accused was charged under Section 103 of BNS for murder."
        matches = _BNS_PATTERN.findall(text)
        assert "103" in matches

    def test_extracts_section_with_subsection(self):
        text = "Section 64(1) of Bharatiya Nyaya Sanhita applies here."
        matches = _BNS_PATTERN.findall(text)
        assert any("64" in m for m in matches)

    def test_no_match_for_ipc(self):
        text = "Section 302 of IPC was applied."
        matches = _BNS_PATTERN.findall(text)
        assert len(matches) == 0


class TestCourtAuthority:
    def test_supreme_court_highest(self):
        assert COURT_AUTHORITY["supreme_court"] == 100

    def test_gujarat_hc_second(self):
        assert COURT_AUTHORITY["gujarat_hc"] == 80

    def test_district_lowest(self):
        assert COURT_AUTHORITY["district"] == 40

    def test_authority_ordering(self):
        assert COURT_AUTHORITY["supreme_court"] > COURT_AUTHORITY["gujarat_hc"]
        assert COURT_AUTHORITY["gujarat_hc"] > COURT_AUTHORITY["other_hc"]
        assert COURT_AUTHORITY["other_hc"] > COURT_AUTHORITY["district"]
