from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[3]
OWNED_ROOT = THIS_FILE.parents[1]
SRC_DIR = OWNED_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from asm00_gate import (  # noqa: E402
    EXTERNAL_STATUS_BLOCKED,
    EXTERNAL_STATUS_PASS_PROVISIONAL,
    EXTERNAL_STATUS_REPEAT,
    RAW_VERDICT_BLOCKED,
    RAW_VERDICT_PASS_PROVISIONAL,
    RAW_VERDICT_REPEAT,
    check_authorizations,
    check_file_binding,
    classify_red_flags,
    evaluate_success,
    load_yaml,
    validate_success_contract,
)


class CurrentDraftClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.draft = load_yaml(
            REPO_ROOT
            / "10_research/on_orbit_assembly/interface_ssot_draft.yaml"
        )
        cls.preflight = load_yaml(
            OWNED_ROOT / "config/preflight_contract.yaml"
        )

    def test_current_draft_preserves_all_three_red_flags(self) -> None:
        result = classify_red_flags(
            self.draft, self.preflight["rf_contract"]
        )
        by_id = {
            item["rf_id"]: item for item in result["results"]
        }
        self.assertEqual("BLOCKED", by_id["RF-1"]["status"])
        self.assertEqual("BLOCKED", by_id["RF-2"]["status"])
        self.assertEqual("BLOCKED", by_id["RF-3"]["status"])
        self.assertEqual(
            "BLOCKED", result["shared_critical_fields"]["status"]
        )

    def test_rf1_nominal_funnel_is_below_required_reduction(self) -> None:
        result = classify_red_flags(
            self.draft, self.preflight["rf_contract"]
        )["results"][0]
        self.assertFalse(
            result["derived"]["nominal_funnel_alone_closes_chain"]
        )
        self.assertAlmostEqual(
            2.143593539449,
            result["derived"]["nominal_funnel_reduction_mm"],
            places=11,
        )

    def test_rf2_nominal_wedge_condition_fails(self) -> None:
        result = classify_red_flags(
            self.draft, self.preflight["rf_contract"]
        )["results"][1]
        self.assertFalse(
            result["derived"][
                "nominal_sliding_condition_tan_alpha_ge_mu"
            ]
        )
        self.assertLess(
            result["derived"]["nominal_tan_alpha_minus_mu"], 0.0
        )
        self.assertFalse(
            result["derived"]["guide_depth_can_resolve_wedge_condition"]
        )

    def test_rf3_both_unfrozen_semantic_branches_fail(self) -> None:
        result = classify_red_flags(
            self.draft, self.preflight["rf_contract"]
        )["results"][2]
        self.assertFalse(
            result["derived"]["diametral_interpretation_pass"]
        )
        self.assertFalse(result["derived"]["radial_interpretation_pass"])

    def test_synthetic_complete_inputs_can_be_classified_resolved(self) -> None:
        ssot = copy.deepcopy(self.draft)
        cone = ssot["interface"]["guide_cone"]
        cone["half_angle_deg"] = 45.0
        cone["depth_mm"] = 5.0
        cone["throat_r_mm"] = 1.0
        cone["mouth_r_mm"] = 6.0
        cone["wedge_margin_factor"] = 1.1
        friction = ssot["interface"]["friction_coulomb"]
        friction.update(
            {
                "value": 0.3,
                "material_pair": "SYNTHETIC_TEST_PAIR",
                "surface_finish": "SYNTHETIC_TEST_FINISH",
                "citation_key": "SYNTHETIC_TEST_ONLY",
                "citation_verified": True,
            }
        )
        pin = ssot["interface"]["pin_hole"]
        pin["clearance_mm"] = 0.4
        pin["clearance_semantics"] = "DIAMETRAL"
        pin["pin_spacing_mm"] = 20.0
        pin["chamfer_width_mm"] = 0.5
        result = classify_red_flags(
            ssot, self.preflight["rf_contract"]
        )
        self.assertEqual(
            {"RESOLVED": 3, "REPEAT": 0, "BLOCKED": 0},
            result["status_counts"],
        )


class SuccessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_yaml(
            OWNED_ROOT
            / "contracts/assembly_success_evaluator_v1.yaml"
        )
        cls.preflight = load_yaml(
            OWNED_ROOT / "config/preflight_contract.yaml"
        )
        cls.draft = load_yaml(
            REPO_ROOT
            / "10_research/on_orbit_assembly/interface_ssot_draft.yaml"
        )

    def _all_pass_evidence(self) -> dict[str, object]:
        return {
            "final_position_error_mm": 0.05,
            "final_orientation_error_deg": 0.25,
            "insertion_depth_reached": True,
            "latch_state": "LOCKED",
            "geometry_consistent": True,
            "contact_load_within_limit": True,
            "base_wheel_within_resources": True,
            "flexible_response_within_validated_envelope": True,
            "provenance_complete": True,
            "phase_transition_adjudication_ledger_complete": True,
            "all_contact_history_peaks_within_limits": True,
            "all_contact_segments_converged": True,
            "contact_log_complete": True,
        }

    def test_contract_is_exactly_nine_and_fail_closed(self) -> None:
        result = validate_success_contract(
            self.contract, self.preflight["success_evaluator"]
        )
        self.assertEqual("PASS", result["status"])
        self.assertEqual(9, result["criterion_count"])
        self.assertFalse(result["contract_freeze_is_HAG_A_approval"])

    def test_all_nine_pass_is_success(self) -> None:
        result = evaluate_success(
            self.contract, self._all_pass_evidence(), self.draft
        )
        self.assertTrue(result["success"])
        self.assertEqual("ASSEMBLY_SUCCESS", result["overall"])
        self.assertEqual(9, len(result["criteria"]))

    def test_missing_history_is_unknown_not_success(self) -> None:
        evidence = self._all_pass_evidence()
        evidence.pop("contact_log_complete")
        result = evaluate_success(self.contract, evidence, self.draft)
        self.assertFalse(result["success"])
        self.assertEqual("UNKNOWN", result["overall"])

    def test_false_geometry_is_fail_not_success(self) -> None:
        evidence = self._all_pass_evidence()
        evidence["geometry_consistent"] = False
        result = evaluate_success(self.contract, evidence, self.draft)
        self.assertFalse(result["success"])
        self.assertEqual("FAIL", result["overall"])

    def test_duplicate_or_eight_criterion_contract_is_rejected(self) -> None:
        broken = copy.deepcopy(self.contract)
        broken["criteria"] = broken["criteria"][:8]
        result = validate_success_contract(
            broken, self.preflight["success_evaluator"]
        )
        self.assertEqual("FAIL", result["status"])
        self.assertIn("criterion_count_mismatch", result["failures"])


class PreflightGuardTests(unittest.TestCase):
    def test_absent_authorizations_never_grant_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = {
                "HAG-A": "10_research/on_orbit_assembly/approvals/HAG-A.yaml",
                "HAG-B": "10_research/on_orbit_assembly/approvals/HAG-B.yaml",
                "HAG-I": "10_research/on_orbit_assembly/approvals/HAG-I.yaml",
            }
            result = check_authorizations(root, root, records)
            self.assertTrue(
                all(item["status"] == "ABSENT" for item in result.values())
            )
            self.assertTrue(
                all(
                    item["authorization_granted"] is False
                    for item in result.values()
                )
            )

    def test_raw_mismatch_is_not_hidden_by_lf_equivalence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relative = "input.txt"
            lf_bytes = b"alpha\nbeta\n"
            (root / relative).write_bytes(b"alpha\r\nbeta\r\n")
            import hashlib

            expected = hashlib.sha256(lf_bytes).hexdigest()
            result = check_file_binding(
                root,
                {"path": relative, "expected_sha256": expected},
            )
            self.assertFalse(result["raw_hash_match"])
            self.assertTrue(result["lf_normalized_hash_match"])
            self.assertEqual("FAIL_RAW_HASH", result["status"])

    def test_external_status_mapping_is_exact(self) -> None:
        mapping = {
            RAW_VERDICT_BLOCKED: EXTERNAL_STATUS_BLOCKED,
            RAW_VERDICT_REPEAT: EXTERNAL_STATUS_REPEAT,
            RAW_VERDICT_PASS_PROVISIONAL: (
                EXTERNAL_STATUS_PASS_PROVISIONAL
            ),
        }
        self.assertEqual(
            "ASM00_BLOCKED_BY_MISSING_PARAMETERS",
            mapping[RAW_VERDICT_BLOCKED],
        )
        self.assertEqual(
            "ASM00_REPEAT_GEOMETRY", mapping[RAW_VERDICT_REPEAT]
        )
        self.assertEqual(
            "ASM00_INTERFACE_QUALIFIED_WITH_PROVISIONAL_PARAMS",
            mapping[RAW_VERDICT_PASS_PROVISIONAL],
        )


if __name__ == "__main__":
    unittest.main()
