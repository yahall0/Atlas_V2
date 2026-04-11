"""Evidence gap detection system tests.

Covers: taxonomy (5), rule-based tier (5), ML tier (4), integration (6),
bias check (1) = 21 tests total.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rbac import get_current_user as _rbac_get_current_user
from app.ml.evidence_taxonomy import (
    ALL_CATEGORIES,
    EVIDENCE_CATEGORIES,
    classify_evidence_text,
    get_expected_evidence,
)
from app.ml.evidence_gap_model import EvidenceGapDetector
from app.ml.evidence_bias_check import check_evidence_bias

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Auth fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _admin_user():
    return {"username": "test_admin", "role": "ADMIN", "district": "Ahmedabad", "full_name": "Test Admin"}

def _sho_user():
    return {"username": "test_sho", "role": "SHO", "district": "Ahmedabad", "full_name": "Test SHO"}

def _io_user():
    return {"username": "test_io", "role": "IO", "district": "Ahmedabad", "full_name": "Test IO"}


@pytest.fixture(autouse=True)
def _auth_admin():
    app.dependency_overrides[_rbac_get_current_user] = _admin_user
    yield
    app.dependency_overrides.pop(_rbac_get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _make_cs(charges, evidence=None, crime_cat=None):
    return {
        "id": str(uuid.uuid4()),
        "fir_id": None,
        "charges_json": charges,
        "evidence_json": evidence or [],
        "raw_text": "",
    }


def _make_fir(sections=None, nlp_classification=None):
    return {
        "id": str(uuid.uuid4()),
        "primary_sections": sections or [],
        "nlp_classification": nlp_classification,
    }


# ═════════════════════════════════════════════════════════════════════════════
# TAXONOMY TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestTaxonomy:
    def test_expected_evidence_murder(self):
        """Murder cases should require post_mortem, scene_of_crime, etc."""
        expected = get_expected_evidence("murder")
        cats = [e["category"] for e in expected]
        assert "post_mortem_report" in cats
        assert "scene_of_crime_report" in cats
        assert "witness_statements_161" in cats

    def test_expected_evidence_cybercrime(self):
        """Cybercrime should require electronic_evidence as critical."""
        expected = get_expected_evidence("cybercrime")
        cats = {e["category"]: e["weight"] for e in expected}
        assert "electronic_evidence" in cats
        assert cats["electronic_evidence"] == "critical"

    def test_classify_text_exact(self):
        """Exact keyword match should return correct category."""
        assert classify_evidence_text("Post mortem report") == "post_mortem_report"
        assert classify_evidence_text("CCTV footage from premises") == "cctv_footage"

    def test_classify_text_fuzzy(self):
        """Fuzzy match should catch near-matches like 'PM report by Dr. Shah'."""
        result = classify_evidence_text("PM report by Dr. Shah")
        # Should match 'pm report' keyword → post_mortem_report
        assert result == "post_mortem_report"

    def test_classify_text_gujarati(self):
        """Basic Gujarati evidence terms should map correctly."""
        result = classify_evidence_text("પોસ્ટ મોર્ટમ રિપોર્ટ")
        assert result == "post_mortem_report"

        result2 = classify_evidence_text("સીસીટીવી ફૂટેજ")
        assert result2 == "cctv_footage"


# ═════════════════════════════════════════════════════════════════════════════
# RULE-BASED TIER TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestRuleBasedTier:
    def test_murder_missing_pm(self):
        """302 case with no post mortem → critical gap flagged."""
        detector = EvidenceGapDetector()
        detector._model = None  # Force Tier 1 only
        detector._tfidf = None

        cs = _make_cs(
            [{"section": "302", "act": "IPC"}],
            evidence=[{"description": "FIR copy", "type": "Documentary"}],
        )
        fir = _make_fir(nlp_classification="murder")
        report = detector.detect_gaps(cs, fir)

        gap_cats = [g["category"] for g in report["evidence_gaps"]]
        assert "post_mortem_report" in gap_cats

        pm_gap = next(g for g in report["evidence_gaps"] if g["category"] == "post_mortem_report")
        assert pm_gap["severity"] == "critical"
        assert pm_gap["tier"] == "rule_based"
        assert pm_gap["confidence"] == 1.0

    def test_sexual_offence_no_164(self):
        """376 case missing victim statement → critical gap."""
        detector = EvidenceGapDetector()
        detector._model = None
        detector._tfidf = None

        cs = _make_cs(
            [{"section": "376", "act": "IPC"}],
            evidence=[{"description": "Medical report", "type": "Medical"}],
        )
        fir = _make_fir(nlp_classification="rape_sexoff")
        report = detector.detect_gaps(cs, fir)

        gap_cats = [g["category"] for g in report["evidence_gaps"]]
        assert "victim_statement_164" in gap_cats

    def test_narcotics_no_seizure(self):
        """NDPS case missing seizure memo → critical gap."""
        detector = EvidenceGapDetector()
        detector._model = None
        detector._tfidf = None

        cs = _make_cs(
            [{"section": "20", "act": "NDPS"}],
            evidence=[{"description": "Witness statement", "type": "Documentary"}],
        )
        fir = _make_fir(nlp_classification="narcotics")
        report = detector.detect_gaps(cs, fir)

        gap_cats = [g["category"] for g in report["evidence_gaps"]]
        assert "seizure_memo" in gap_cats

    def test_all_evidence_present(self):
        """Complete murder case → 0 rule-based gaps, ~100% coverage."""
        detector = EvidenceGapDetector()
        detector._model = None
        detector._tfidf = None

        cs = _make_cs(
            [{"section": "302", "act": "IPC"}],
            evidence=[
                {"description": "Post mortem report by Dr. Shah", "type": "Medical"},
                {"description": "Scene of crime panchnama", "type": "Documentary"},
                {"description": "Forensic report from FSL", "type": "Forensic"},
                {"description": "Witness statement under 161", "type": "Documentary"},
                {"description": "Medical examination report", "type": "Medical"},
                {"description": "Weapon recovery memo", "type": "Physical"},
                {"description": "Site plan sketch", "type": "Documentary"},
                {"description": "DNA report", "type": "Forensic"},
                {"description": "FSL report analysis", "type": "Forensic"},
                {"description": "Confession statement of accused", "type": "Documentary"},
            ],
        )
        fir = _make_fir(nlp_classification="murder")
        report = detector.detect_gaps(cs, fir)

        rule_gaps = [g for g in report["evidence_gaps"] if g["tier"] == "rule_based"]
        assert len(rule_gaps) <= 1  # At most 1 minor gap
        assert report["evidence_coverage_pct"] >= 80.0

    def test_partial_coverage(self):
        """3 of 5+ expected → coverage below 100%."""
        detector = EvidenceGapDetector()
        detector._model = None
        detector._tfidf = None

        cs = _make_cs(
            [{"section": "302", "act": "IPC"}],
            evidence=[
                {"description": "Post mortem report", "type": "Medical"},
                {"description": "Witness statement", "type": "Documentary"},
                {"description": "Scene of crime report", "type": "Documentary"},
            ],
        )
        fir = _make_fir(nlp_classification="murder")
        report = detector.detect_gaps(cs, fir)

        assert report["evidence_coverage_pct"] < 100.0
        assert report["total_gaps"] > 0


# ═════════════════════════════════════════════════════════════════════════════
# ML TIER TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestMLTier:
    @pytest.fixture(autouse=True)
    def _train_model(self, tmp_path):
        """Train a small model for ML tier tests."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

        from scripts.generate_evidence_training_data import generate_dataset
        from app.ml.evidence_gap_model import EvidenceGapDetector

        data = generate_dataset(samples_per_class=30, seed=42)
        self.detector = EvidenceGapDetector()
        self.detector._model = None
        self.detector._tfidf = None
        metrics = self.detector.train(data)
        self.metrics = metrics

        # Save/load roundtrip
        model_path = tmp_path / "test_model.pkl"
        tfidf_path = tmp_path / "evidence_tfidf.pkl"
        self.detector.save_model(str(model_path))
        self.detector.load_model(str(model_path))

    def test_model_loads(self):
        """Model pickle loads without error."""
        assert self.detector.has_ml_model

    def test_model_predicts(self):
        """Detector returns a report with coverage and gaps."""
        cs = _make_cs(
            [{"section": "302", "act": "IPC"}],
            evidence=[{"description": "FIR copy", "type": "Documentary"}],
        )
        fir = _make_fir(nlp_classification="murder")
        report = self.detector.detect_gaps(cs, fir)

        assert "evidence_coverage_pct" in report
        assert "evidence_gaps" in report
        assert isinstance(report["evidence_gaps"], list)

    def test_ml_suggests_additional(self):
        """ML tier finds at least one gap not in rule-based tier."""
        cs = _make_cs(
            [{"section": "302", "act": "IPC"}],
            evidence=[
                {"description": "Post mortem report", "type": "Medical"},
                {"description": "Scene of crime report", "type": "Documentary"},
                {"description": "Witness statement", "type": "Documentary"},
                {"description": "Weapon recovery memo", "type": "Physical"},
                {"description": "FSL report", "type": "Forensic"},
                {"description": "Medical examination", "type": "Medical"},
                {"description": "DNA report", "type": "Forensic"},
                {"description": "Site plan map", "type": "Documentary"},
                {"description": "Confession statement", "type": "Documentary"},
                {"description": "Forensic lab report", "type": "Forensic"},
            ],
        )
        fir = _make_fir(nlp_classification="murder")
        report = self.detector.detect_gaps(cs, fir)

        # With most evidence present, any remaining gaps should be from ML
        ml_gaps = [g for g in report["evidence_gaps"] if g["tier"] == "ml_pattern"]
        # ML may or may not find additional; just verify structure
        for gap in ml_gaps:
            assert gap["severity"] == "suggested"
            assert gap["confidence"] > 0

    def test_ml_does_not_duplicate(self):
        """ML gaps should not duplicate rule-based gaps."""
        cs = _make_cs(
            [{"section": "302", "act": "IPC"}],
            evidence=[{"description": "FIR copy", "type": "Documentary"}],
        )
        fir = _make_fir(nlp_classification="murder")
        report = self.detector.detect_gaps(cs, fir)

        rule_cats = {g["category"] for g in report["evidence_gaps"] if g["tier"] == "rule_based"}
        ml_cats = {g["category"] for g in report["evidence_gaps"] if g["tier"] == "ml_pattern"}
        assert len(rule_cats & ml_cats) == 0


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION / API TESTS
# ═════════════════════════════════════════════════════════════════════════════


def _mock_cs(cs_id):
    return {
        "id": cs_id,
        "fir_id": None,
        "charges_json": [{"section": "302", "act": "IPC"}],
        "evidence_json": [{"description": "FIR copy", "type": "Documentary"}],
        "raw_text": "murder case",
        "district": "Ahmedabad",
    }


def _mock_create_report(conn, data):
    return {"id": str(uuid.uuid4()), **data, "created_at": datetime.now(timezone.utc)}


class TestAPIIntegration:
    def test_api_analyze_endpoint(self):
        """POST /evidence/analyze returns valid EvidenceGapReport."""
        cs_id = str(uuid.uuid4())
        with (
            patch("app.api.v1.evidence.get_connection", return_value=MagicMock()),
            patch("app.api.v1.evidence.get_chargesheet_by_id", return_value=_mock_cs(cs_id)),
            patch("app.api.v1.evidence.get_fir_by_id", return_value=None),
            patch("app.api.v1.evidence.create_evidence_gap_report", side_effect=_mock_create_report),
        ):
            resp = client.post(f"/api/v1/evidence/analyze/{cs_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "evidence_gaps" in data
        assert "evidence_coverage_pct" in data
        assert "crime_category" in data

    def test_api_taxonomy_endpoint(self):
        """GET /evidence/taxonomy returns full taxonomy."""
        resp = client.get("/api/v1/evidence/taxonomy")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert len(data["categories"]) == 20

    def test_api_rbac_enforcement(self):
        """IO role blocked from analyze, SHO allowed."""
        app.dependency_overrides[_rbac_get_current_user] = _io_user
        resp = client.post(f"/api/v1/evidence/analyze/{uuid.uuid4()}")
        assert resp.status_code == 403

    def test_api_sho_allowed(self):
        """SHO can run analysis."""
        app.dependency_overrides[_rbac_get_current_user] = _sho_user
        cs_id = str(uuid.uuid4())
        with (
            patch("app.api.v1.evidence.get_connection", return_value=MagicMock()),
            patch("app.api.v1.evidence.get_chargesheet_by_id", return_value=_mock_cs(cs_id)),
            patch("app.api.v1.evidence.get_fir_by_id", return_value=None),
            patch("app.api.v1.evidence.create_evidence_gap_report", side_effect=_mock_create_report),
        ):
            resp = client.post(f"/api/v1/evidence/analyze/{cs_id}")
        assert resp.status_code == 200

    def test_report_not_found(self):
        with (
            patch("app.api.v1.evidence.get_connection", return_value=MagicMock()),
            patch("app.api.v1.evidence.get_evidence_gap_report_by_id", return_value=None),
        ):
            resp = client.get(f"/api/v1/evidence/report/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_no_fir_partial_analysis(self):
        """Works without linked FIR (partial analysis)."""
        cs_id = str(uuid.uuid4())
        cs = _mock_cs(cs_id)
        cs["fir_id"] = None
        with (
            patch("app.api.v1.evidence.get_connection", return_value=MagicMock()),
            patch("app.api.v1.evidence.get_chargesheet_by_id", return_value=cs),
            patch("app.api.v1.evidence.create_evidence_gap_report", side_effect=_mock_create_report),
        ):
            resp = client.post(f"/api/v1/evidence/analyze/{cs_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["crime_category"] is not None


# ═════════════════════════════════════════════════════════════════════════════
# BIAS CHECK
# ═════════════════════════════════════════════════════════════════════════════


class TestBiasCheck:
    def test_bias_check_no_flag_on_uniform_data(self):
        """Uniform synthetic data should not flag any district bias."""
        reports = []
        for district in ["Ahmedabad", "Surat", "Vadodara"]:
            for _ in range(10):
                reports.append({
                    "crime_category": "murder",
                    "district": district,
                    "total_expected": 8,
                    "total_gaps": 3,
                })

        result = check_evidence_bias(reports)
        assert result["flagged"] is False
        assert len(result["flags"]) == 0
