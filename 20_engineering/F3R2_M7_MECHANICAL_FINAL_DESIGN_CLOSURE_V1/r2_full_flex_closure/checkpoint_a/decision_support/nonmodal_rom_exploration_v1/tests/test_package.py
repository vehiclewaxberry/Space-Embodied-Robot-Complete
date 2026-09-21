import hashlib
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
PROJECT_ROOT = HERE.parents[5]
RESULT = HERE / "R2_NONMODAL_ROM_EXPLORATION_RESULTS_V1.json"
INDEPENDENT = HERE / "INDEPENDENT_RECOMPUTE_V1.json"
GATE = HERE / "R2_NONMODAL_ROM_EXPLORATION_DECISION_SUPPORT_GATE_V1.json"
MANIFEST = HERE / "NONMODAL_ROM_EXPLORATION_SHA256_MANIFEST_V1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class TestNonmodalExplorationPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.independent = json.loads(INDEPENDENT.read_text(encoding="utf-8"))
        cls.gate = json.loads(GATE.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_evidence_class_and_no_authorization(self):
        self.assertEqual(
            self.result["evidence_class"], "EXPLORATORY_DECISION_SUPPORT_ONLY"
        )
        self.assertEqual(
            self.gate["evidence_class"], "EXPLORATORY_DECISION_SUPPORT_ONLY"
        )
        for value in self.result["governance"].values():
            if isinstance(value, bool):
                self.assertFalse(value)
        for value in self.gate["authorizations"].values():
            self.assertFalse(value)

    def test_headline_recompute(self):
        h = self.result["headline_findings"]
        self.assertAlmostEqual(
            h["best_tested_5d_weighted_pod"]["global_max_relative_error"],
            0.04001049363625929,
            delta=2.0e-12,
        )
        self.assertAlmostEqual(
            h["hybrid_9d_3b_plus_6t_pod"]["global_max_relative_error"],
            0.013757336666856242,
            delta=2.0e-12,
        )
        self.assertAlmostEqual(
            h["hybrid_10d_3b_plus_7t_pod"]["global_max_relative_error"],
            0.0096651825271157,
            delta=2.0e-12,
        )
        self.assertAlmostEqual(
            h["hybrid_10d_5ms_dense_torsion_peak"][
                "global_dense_relative_peak_error"
            ],
            0.00948126119892961,
            delta=2.0e-12,
        )

    def test_independent_recompute_and_negative_control(self):
        self.assertTrue(self.independent["all_comparisons_pass"])
        self.assertTrue(
            self.independent["negative_control"]["negative_control_pass"]
        )
        self.assertGreater(
            self.independent["negative_control"]["rank6_9d_error"], 0.01
        )

    def test_gate_is_integrity_only(self):
        self.assertEqual(
            self.gate["decision_support_integrity_status"],
            "PASS_BOUNDED_EVIDENCE_INTEGRITY_ONLY",
        )
        self.assertTrue(self.gate["decision_support_evidence_integrity_pass"])
        self.assertEqual(
            self.gate["criteria_passed"], self.gate["criteria_total"]
        )
        self.assertFalse(self.gate["authorizations"]["component_gate_pass"])
        self.assertFalse(self.gate["authorizations"]["next_stage_authorized"])

    def test_manifest_is_acyclic_and_hashes_match(self):
        self.assertFalse(self.manifest["acyclicity"]["manifest_self_included"])
        self.assertFalse(
            self.manifest["acyclicity"]["manifest_hash_referenced_by_gate"]
        )
        manifest_rel = self.manifest["acyclicity"]["manifest_path"]
        paths = {entry["path"] for entry in self.manifest["entries"]}
        self.assertNotIn(manifest_rel, paths)
        for entry in self.manifest["entries"]:
            path = PROJECT_ROOT / entry["path"]
            self.assertTrue(path.is_file(), entry["path"])
            self.assertEqual(path.stat().st_size, entry["bytes"])
            self.assertEqual(sha(path), entry["sha256"])

    def test_no_global_grassmann_impossibility_claim(self):
        text = " ".join(self.result["limitations_and_nonclaims"])
        self.assertIn("do not prove a global minimum", text)
        self.assertIn("not a theorem", text)
        family = self.result["candidate_families_tested"][
            "weighted_full_state_pod_5d"
        ]
        self.assertFalse(family["global_optimality_claimed"])


if __name__ == "__main__":
    unittest.main()
