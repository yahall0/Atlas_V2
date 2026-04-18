"""Tests for hash chain integrity — T53-M8.

Verifies:
- Hash chain remains unbroken across 10 status updates
- Tampered chain is detected
"""

from __future__ import annotations

import pytest

from app.mindmap.generator import _compute_status_hash


class TestHashChainIntegrity:
    """Hash chain must remain unbroken across multiple status updates."""

    def _build_chain(self, n: int = 10) -> list[dict]:
        """Build a chain of N status entries."""
        chain = []
        prev_hash = "GENESIS"

        statuses = ["open", "in_progress", "addressed", "disputed",
                     "open", "in_progress", "addressed", "not_applicable",
                     "open", "addressed"]

        for i in range(n):
            timestamp = f"2026-01-01T{i:02d}:00:00+00:00"
            note = f"note_{i}" if i % 2 == 0 else ""
            evidence = f"ref_{i}" if i % 3 == 0 else ""

            h = _compute_status_hash(
                "node-001", "user-io1", statuses[i % len(statuses)],
                note, evidence, timestamp, prev_hash,
            )

            chain.append({
                "index": i,
                "status": statuses[i % len(statuses)],
                "note": note,
                "evidence_ref": evidence,
                "timestamp": timestamp,
                "hash_prev": prev_hash,
                "hash_self": h,
            })
            prev_hash = h

        return chain

    def _verify_chain(self, chain: list[dict]) -> tuple[bool, int | None]:
        """Verify chain integrity. Returns (valid, first_break_at)."""
        expected_prev = "GENESIS"

        for entry in chain:
            if entry["hash_prev"] != expected_prev:
                return False, entry["index"]

            recomputed = _compute_status_hash(
                "node-001", "user-io1", entry["status"],
                entry["note"], entry["evidence_ref"],
                entry["timestamp"], entry["hash_prev"],
            )

            if recomputed != entry["hash_self"]:
                return False, entry["index"]

            expected_prev = entry["hash_self"]

        return True, None

    def test_chain_unbroken_10_entries(self):
        """Chain of 10 entries should verify cleanly."""
        chain = self._build_chain(10)
        valid, break_at = self._verify_chain(chain)
        assert valid is True
        assert break_at is None

    def test_chain_unbroken_1_entry(self):
        chain = self._build_chain(1)
        valid, break_at = self._verify_chain(chain)
        assert valid is True

    def test_tampered_hash_detected(self):
        """Modifying an entry's hash_self should break the chain."""
        chain = self._build_chain(10)
        # Tamper with entry at index 5
        chain[5]["hash_self"] = "0" * 64
        valid, break_at = self._verify_chain(chain)
        assert valid is False
        # Break detected at entry 5 (recomputed hash doesn't match stored)
        # or entry 6 (prev doesn't match). Either is valid detection.
        assert break_at in (5, 6)

    def test_tampered_status_detected(self):
        """Modifying an entry's status field should break the chain."""
        chain = self._build_chain(10)
        # Tamper with entry at index 3 — change the status
        original_status = chain[3]["status"]
        chain[3]["status"] = "disputed" if original_status != "disputed" else "open"
        valid, break_at = self._verify_chain(chain)
        assert valid is False
        assert break_at == 3

    def test_tampered_note_detected(self):
        """Modifying an entry's note should break the chain."""
        chain = self._build_chain(10)
        chain[2]["note"] = "TAMPERED NOTE"
        valid, break_at = self._verify_chain(chain)
        assert valid is False
        assert break_at == 2

    def test_tampered_prev_hash_detected(self):
        """Modifying hash_prev in the middle of chain should be detected."""
        chain = self._build_chain(10)
        chain[4]["hash_prev"] = "bad_hash_value"
        valid, break_at = self._verify_chain(chain)
        assert valid is False
        assert break_at == 4

    def test_empty_chain_valid(self):
        valid, break_at = self._verify_chain([])
        assert valid is True
        assert break_at is None

    def test_inserted_entry_detected(self):
        """Inserting a forged entry into the middle should break the chain."""
        chain = self._build_chain(10)
        forged = {
            "index": 99,
            "status": "addressed",
            "note": "forged",
            "evidence_ref": "",
            "timestamp": "2026-01-01T05:30:00+00:00",
            "hash_prev": chain[4]["hash_self"],
            "hash_self": _compute_status_hash(
                "node-001", "user-io1", "addressed",
                "forged", "", "2026-01-01T05:30:00+00:00",
                chain[4]["hash_self"],
            ),
        }
        # Insert between entries 5 and 6
        chain.insert(5, forged)
        # The original entry 5 now at index 6 has hash_prev pointing
        # to entry 4, not to the forged entry
        valid, break_at = self._verify_chain(chain)
        assert valid is False
