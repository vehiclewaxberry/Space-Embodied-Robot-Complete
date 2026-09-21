from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "10_research" / "competition_convergence" / "src"
sys.path.insert(0, str(SRC))

from evidence_contract import (  # noqa: E402
    CLAIM_FIELDS,
    EvidenceError,
    build_replay_records,
    canonical_csv_table_sha256,
    load_and_verify,
    load_strict_yaml,
    verify_evidence_contract_data,
    write_replay_package,
)


CONTRACT_PATH = (
    ROOT / "10_research" / "competition_convergence" / "mission_demo_contract.yaml"
)
SCENARIO_PATH = (
    ROOT / "10_research" / "competition_convergence" / "three_scenario_manifest.yaml"
)
CLAIM_PATH = (
    ROOT
    / "10_research"
    / "competition_convergence"
    / "competition_claim_evidence_matrix.csv"
)


def fresh_documents() -> tuple[dict, dict]:
    return load_strict_yaml(CONTRACT_PATH), load_strict_yaml(SCENARIO_PATH)


class ContractHappyPathTests(unittest.TestCase):
    def test_contract_and_all_frozen_artifacts_verify(self) -> None:
        _, _, report = load_and_verify(CONTRACT_PATH, SCENARIO_PATH, ROOT)
        self.assertEqual(report["overall"], "PASS")
        self.assertFalse(report["command_emitted"])
        self.assertEqual(report["git"]["scope_violations"], [])
        self.assertEqual(len(report["artifacts"]), 9)

    def test_replay_records_preserve_exact_actions_and_joins(self) -> None:
        contract, manifest, report = load_and_verify(
            CONTRACT_PATH, SCENARIO_PATH, ROOT
        )
        records = build_replay_records(contract, manifest, report)
        self.assertEqual(records["A_low"]["explanation"]["display_action"], "EXECUTE")
        self.assertFalse(records["A_low"]["explanation"]["execution_authority"])
        self.assertFalse(records["A_low"]["command_emitted"])
        a_safe = next(
            stage
            for stage in records["A_low"]["stage_records"]
            if stage["stage_id"] == "SAFE00"
        )
        self.assertEqual(a_safe["join_status"], "EXACT")
        self.assertIn("NO_EXECUTION_AUTHORITY", a_safe["decision"])

        self.assertEqual(records["B_anchor"]["explanation"]["display_action"], "ABORT")
        b_safe = next(
            stage
            for stage in records["B_anchor"]["stage_records"]
            if stage["stage_id"] == "SAFE00"
        )
        b_ctrl = next(
            stage
            for stage in records["B_anchor"]["stage_records"]
            if stage["stage_id"] == "CTRL02"
        )
        self.assertEqual(b_safe["join_status"], "NOT_APPLICABLE")
        self.assertEqual(b_ctrl["join_status"], "NOT_APPLICABLE")

        self.assertEqual(
            records["C_transition"]["explanation"]["display_action"], "MODIFY"
        )
        c_safe = next(
            stage
            for stage in records["C_transition"]["stage_records"]
            if stage["stage_id"] == "SAFE00"
        )
        c_ctrl = next(
            stage
            for stage in records["C_transition"]["stage_records"]
            if stage["stage_id"] == "CTRL02"
        )
        self.assertEqual(c_safe["decision"], "MISSING_REGISTERED_CANDIDATE")
        self.assertEqual(c_ctrl["join_status"], "REFERENCE_ONLY")

    def test_replay_package_is_bitwise_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as left_name, tempfile.TemporaryDirectory() as right_name:
            left = Path(left_name)
            right = Path(right_name)
            first = write_replay_package(
                CONTRACT_PATH, SCENARIO_PATH, left, ROOT
            )
            second = write_replay_package(
                CONTRACT_PATH, SCENARIO_PATH, right, ROOT
            )
            self.assertEqual(first, second)
            self.assertEqual(
                sorted(path.name for path in left.iterdir()),
                sorted(path.name for path in right.iterdir()),
            )
            for left_file in left.iterdir():
                self.assertEqual(
                    left_file.read_bytes(), (right / left_file.name).read_bytes()
                )

    def test_claim_matrix_has_frozen_eleven_field_contract(self) -> None:
        with CLAIM_PATH.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
        self.assertEqual(reader.fieldnames, CLAIM_FIELDS)
        self.assertGreaterEqual(len(rows), 8)
        self.assertEqual(len({row["claim_id"] for row in rows}), len(rows))
        self.assertTrue(all(row["allowed_wording"] for row in rows))
        self.assertTrue(all(row["forbidden_wording"] for row in rows))


class RedTeamAttackTests(unittest.TestCase):
    def assert_rejected(self, mutate) -> None:
        contract, scenarios = fresh_documents()
        mutate(contract, scenarios)
        with self.assertRaises(EvidenceError):
            verify_evidence_contract_data(
                contract,
                scenarios,
                ROOT,
                check_git=False,
                check_claims=False,
            )

    # Physics / provenance: five attacks.
    def test_rt_p01_raw_hash_drift_is_rejected(self) -> None:
        self.assert_rejected(
            lambda contract, _: contract["artifact_registry"]["sim10_gate"].update(
                raw_sha256="0" * 64
            )
        )

    def test_rt_p02_canonical_hash_drift_is_rejected(self) -> None:
        self.assert_rejected(
            lambda contract, _: contract["artifact_registry"]["ctrl02_gate"].update(
                canonical_sha256="1" * 64
            )
        )

    def test_rt_p03_duplicate_csv_row_key_is_rejected(self) -> None:
        rows = [
            {"case": "A_low", "strategy": "S1"},
            {"case": "A_low", "strategy": "S1"},
        ]
        with self.assertRaises(ValueError):
            canonical_csv_table_sha256(rows, ["case", "strategy"])

    def test_rt_p04_case_key_hash_mismatch_is_rejected(self) -> None:
        self.assert_rejected(
            lambda _, scenarios: scenarios["scenarios"]["C_transition"][
                "case_source"
            ].update(canonical_case_sha256="2" * 64)
        )

    def test_rt_p05_cross_stage_strategy_controller_conflation_is_rejected(self) -> None:
        self.assert_rejected(
            lambda _, scenarios: scenarios["scenarios"]["C_transition"][
                "ctrl02"
            ].update(strategy_equivalence_claimed=True)
        )

    # Safety / claim discipline: five attacks.
    def test_rt_s01_a_candidate_rebinding_is_rejected(self) -> None:
        self.assert_rejected(
            lambda _, scenarios: scenarios["scenarios"]["A_low"]["safe00"].update(
                candidate_id="C_transition-S3a_wheel_bias"
            )
        )

    def test_rt_s02_command_emission_is_rejected(self) -> None:
        self.assert_rejected(
            lambda _, scenarios: scenarios["scenarios"]["A_low"][
                "explanation"
            ].update(command_emitted=True)
        )

    def test_rt_s03_fabricated_b_safe_request_is_rejected(self) -> None:
        self.assert_rejected(
            lambda _, scenarios: scenarios["scenarios"]["B_anchor"][
                "safe00"
            ].update(actual_authorization_request_present=True)
        )

    def test_rt_s04_missing_c_candidate_promoted_to_exact_is_rejected(self) -> None:
        def mutate(_, scenarios) -> None:
            safe = scenarios["scenarios"]["C_transition"]["safe00"]
            safe["join_status"] = "EXACT"
            safe["authorized_candidate_binding"] = "EXACT"

        self.assert_rejected(mutate)

    def test_rt_s05_safe_next_stage_reclassification_is_rejected(self) -> None:
        self.assert_rejected(
            lambda _, scenarios: scenarios["scenarios"]["A_low"]["safe00"][
                "required_gate_values"
            ].update(next_stage_authorized=True)
        )

    # Reproducibility / scope: five attacks.
    def test_rt_r01_b_counterfactual_promotion_is_rejected(self) -> None:
        def mutate(_, scenarios) -> None:
            ctrl = scenarios["scenarios"]["B_anchor"]["ctrl02"]
            ctrl["join_status"] = "EXACT"
            ctrl["included_in_execution_chain"] = True

        self.assert_rejected(mutate)

    def test_rt_r02_missing_required_watermark_is_rejected(self) -> None:
        self.assert_rejected(
            lambda _, scenarios: scenarios["watermarks"].remove(
                "NO COMMAND OUTPUT"
            )
        )

    def test_rt_r03_widened_owned_scope_is_rejected(self) -> None:
        self.assert_rejected(
            lambda contract, _: contract["baseline"].update(
                owned_path_prefix="10_research/"
            )
        )

    def test_rt_r04_removed_provisional_limit_is_rejected(self) -> None:
        self.assert_rejected(
            lambda _, scenarios: scenarios["scenarios"]["A_low"]["ctrl02"][
                "limitations"
            ].remove("PROVISIONAL_L1_MOMENTUM_ACTUATOR")
        )

    def test_rt_r05_stale_hidden_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            output = Path(name)
            (output / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(EvidenceError):
                write_replay_package(
                    CONTRACT_PATH, SCENARIO_PATH, output, ROOT
                )


if __name__ == "__main__":
    unittest.main()
