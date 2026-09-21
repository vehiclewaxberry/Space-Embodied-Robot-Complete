#!/usr/bin/env python
"""Read-only package-level regression tests for R2 HF/ROM V2."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
GATE = PKG / "R2_FULL_FLEX_HF_ROM_GATE_V2.json"
INDEPENDENT = HERE / "INDEPENDENT_RECOMPUTE_V2.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class PackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = json.loads(GATE.read_text(encoding="utf-8"))

    def test_gate_criteria(self):
        self.assertEqual(self.gate["technical_verdict"],
                         "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS")
        self.assertEqual(self.gate["summary"], {"passed": 17, "total": 17})
        self.assertTrue(all(c["pass"] for c in self.gate["criteria"]))

    def test_fail_closed_footer(self):
        self.assertEqual(self.gate["scope_guards"]["r2_coupled_diagnostics"],
                         "NOT_EVALUATED")
        self.assertEqual(self.gate["scope_guards"]["e15_inheritance"],
                         "NOT_INHERITED")
        self.assertFalse(self.gate["scope_guards"]["owner_accepted"])
        self.assertFalse(self.gate["next_stage_authorized"])
        self.assertFalse(self.gate["release_credit"])

    def test_evidence_hashes(self):
        root = PKG.parents[3]
        for raw_path, expected in self.gate["evidence_hashes"].items():
            path = Path(raw_path)
            if not path.is_absolute():
                path = root / path
            self.assertTrue(path.exists(), raw_path)
            self.assertEqual(digest(path), expected, raw_path)

    def test_independent_recompute(self):
        report = json.loads(INDEPENDENT.read_text(encoding="utf-8"))
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["summary"], {"passed": 10, "total": 10})

    def test_no_unhandled_disposition(self):
        rows = self.gate["evidence_disposition_register"]
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(r.get("disposition") for r in rows))


if __name__ == "__main__":
    unittest.main(verbosity=2)
