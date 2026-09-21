from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "P1_RC_CROSS_THREADED_OVERLAY.py"
SPEC = importlib.util.spec_from_file_location("v9f_p1_overlay", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
P1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P1)


class P1OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _data, cls.source = P1._read_pinned_source()
        cls.transformed, cls.audit = P1.transform_source(cls.source)

    def test_hash_pins_and_compile(self) -> None:
        self.assertEqual(
            self.audit["active_source_sha256"], P1.EXPECTED_ACTIVE_SHA256
        )
        self.assertEqual(
            self.audit["original_rc_loop_sha256"], P1.EXPECTED_RC_LOOP_SHA256
        )
        compile(self.transformed, str(P1.ACTIVE_EVALUATOR), "exec")

    def test_external_manifest_binds_wrapper(self) -> None:
        audit = P1._verify_external_manifest()
        self.assertTrue(audit["match"])
        self.assertEqual(audit["wrapper_sha256"], P1._sha256_path(MODULE_PATH))

    def test_scientific_constants_and_kernel_fragments_unchanged(self) -> None:
        checks = P1._static_equivalence_checks(self.source, self.transformed)
        self.assertEqual(checks["scientific_constant_assignments"], 14)
        self.assertEqual(checks["ordered_map_injections"], 1)
        self.assertEqual(checks["strict_tie_reducers"], 1)

    def test_only_one_threaded_outer_q_map_exists(self) -> None:
        tree = ast.parse(self.transformed)
        thread_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_p1_ordered_map"
        ]
        self.assertEqual(len(thread_calls), 1)
        self.assertEqual(self.transformed.count("_p1_eval_batch("), 1)
        self.assertNotIn("ProcessPoolExecutor", self.transformed)

    def test_order_tie_count_and_exception_contract(self) -> None:
        checks = P1._synthetic_order_and_tie_checks(workers=4)
        self.assertTrue(checks["ordered_result_match"])
        self.assertEqual(checks["strict_first_hit_tie_record"], "q1-first-tie")
        self.assertEqual(checks["comparison_count_sum"], 60)
        self.assertTrue(checks["worker_exception_propagates"])

    def test_mission_order_cache_and_frozen_base_contract(self) -> None:
        checks = P1._synthetic_mission_cache_checks(workers=4)
        self.assertTrue(checks["ordered_results_match"])
        self.assertTrue(checks["preexisting_cache_hit_preserved"])
        self.assertTrue(checks["duplicate_q_deterministic"])
        self.assertEqual(checks["base_precompute_order"], [1.0, 2.0, 1.0])
        self.assertTrue(checks["thread_local_state_cleared"])

    def test_frozen_mission_has_no_intra_batch_round12_collision(self) -> None:
        audit = P1._audit_mission_round12_batch_keys()
        self.assertTrue(audit["pass"])
        self.assertEqual(audit["steps"]["0.250_deg"]["total_samples"], 2512)
        self.assertEqual(audit["steps"]["0.125_deg"]["total_samples"], 5014)
        for report in audit["steps"].values():
            self.assertEqual(report["exact_duplicate_count"], 0)
            self.assertEqual(report["distinct_round12_collision_count"], 0)

    def test_candidate_outputs_are_isolated(self) -> None:
        for path in (P1.OUT_SWEEP, P1.OUT_LEDGER, P1.OUT_GATE, P1.OUT_RECEIPT):
            self.assertEqual(path.parent, HERE)
        self.assertFalse(
            {
                P1.OUT_SWEEP.name,
                P1.OUT_LEDGER.name,
                P1.OUT_GATE.name,
            }
            & {
                "ROUTE_C_EXACT_SWEEP_V9F.json",
                "ROUTE_C_ROBUST_MARGIN_LEDGER_V9F.csv",
                "ROUTE_C_MISSION_COVERAGE_GATE_V9F.json",
            }
        )
        resolved = P1._assert_resolved_output_isolation()
        self.assertTrue(resolved["pass"])
        self.assertEqual(resolved["active_output_alias_count"], 0)

    def test_authority_is_demoted_before_execution(self) -> None:
        self.assertNotIn(P1.AUTHORITY_LINE, self.transformed)
        self.assertIn(P1.NONAUTHORITY_LINE, self.transformed)


if __name__ == "__main__":
    unittest.main()
