"""Unit and contract tests for the isolated R2 MuJoCo diagnostic."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import mujoco
import numpy as np


sys.dont_write_bytecode = True
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = PACKAGE_ROOT / "02_conversion" / "r2_mujoco_precontact_v1.py"
VALIDATOR_PATH = PACKAGE_ROOT / "04_validation" / "independent_validate_mujoco_v1.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_SPEC_FAILED:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


core = _load_module("_test_r2_mujoco_candidate", CORE_PATH)
independent = _load_module("_test_r2_mujoco_independent", VALIDATOR_PATH)


class R2MuJoCoPrecontactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = core.load_json(core.CONTRACT_PATH)
        cls.source_lock = core.load_json(core.SOURCE_LOCK_PATH)
        pins = {row["id"]: row for row in cls.source_lock["pins"]}
        cls.unified_path = core.PROJECT_ROOT / pins["unified_r2_urdf"]["path"]
        cls.urdf = core.parse_urdf(cls.unified_path)
        cls.rendered = {
            lane: core.render_mjcf(cls.urdf, cls.contract, lane)
            for lane in core.LANES
        }

    def test_01_pinned_runtime_is_exact(self) -> None:
        environment = core.environment_receipt(self.contract)
        self.assertTrue(environment["runtime_matches_contract"])
        self.assertEqual(mujoco.__version__, "3.12.0")

    def test_02_source_authority_lock_matches(self) -> None:
        audit = core.audit_source_pins()
        self.assertTrue(audit["all_match"])
        self.assertEqual(audit["matched"], audit["total"])
        for key in (
            "mutation_authorized",
            "parent_gate_upgrade_authorized",
            "next_stage_authorized",
            "release_credit",
        ):
            self.assertIs(self.source_lock[key], False)

    def test_03_source_hash_mutation_is_caught(self) -> None:
        mutated = copy.deepcopy(self.source_lock)
        mutated["pins"][0]["sha256"] = "0" * 64
        audit = core.audit_source_pins(mutated)
        self.assertFalse(audit["all_match"])
        self.assertEqual(audit["matched"], audit["total"] - 1)

    def test_04_strict_json_rejects_duplicate_and_nonfinite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            duplicate = Path(temp_dir) / "duplicate.json"
            duplicate.write_text('{"x":1,"x":2}\n', encoding="utf-8")
            with self.assertRaises(core.DiagnosticError):
                core.load_json(duplicate)
            nonfinite = Path(temp_dir) / "nonfinite.json"
            nonfinite.write_text('{"x":NaN}\n', encoding="utf-8")
            with self.assertRaises(core.DiagnosticError):
                core.load_json(nonfinite)

    def test_05_urdf_inventory_and_mass_are_frozen(self) -> None:
        self.assertEqual(self.urdf.root_link, "spacecraft_bus")
        self.assertEqual(len(self.urdf.links), 19)
        self.assertEqual(len(self.urdf.joints), 18)
        physical = [
            link for link in self.urdf.links.values()
            if core._link_inertial_record(link) is not None
        ]
        masses = [core._link_inertial_record(link)["mass_kg"] for link in physical]
        self.assertEqual(len(physical), 16)
        self.assertEqual(len(self.urdf.links) - len(physical), 3)
        self.assertAlmostEqual(sum(masses), self.contract["model"]["total_mass_kg"], places=12)

    def test_06_emission_is_deterministic_and_semantically_labeled(self) -> None:
        for lane, (first_xml, first_mapping) in self.rendered.items():
            second_xml, second_mapping = core.render_mjcf(self.urdf, self.contract, lane)
            self.assertEqual(first_xml, second_xml)
            self.assertEqual(first_mapping["mjcf_sha256"], second_mapping["mjcf_sha256"])
            self.assertEqual(first_mapping["2p_semantics"], self.contract["lanes"][lane]["lock_semantics"])
            self.assertTrue(first_mapping["contact_disabled_by_option"])

    def test_07_unknown_lane_fails_closed(self) -> None:
        with self.assertRaisesRegex(core.DiagnosticError, "UNKNOWN_LANE"):
            core.render_mjcf(self.urdf, self.contract, "UNREGISTERED_LANE")

    def test_08_three_lane_dimensions_and_lock_semantics(self) -> None:
        expected = {
            "LOCKED_2P_REDUCED_6R": (13, 12, 7, 0),
            "LOCKED_2P_EQUALITY_6R2P": (15, 14, 9, 2),
            "FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL": (15, 14, 9, 0),
        }
        for lane, (xml_bytes, _) in self.rendered.items():
            model, _ = core.compile_lane(xml_bytes)
            nq, nv, njnt, neq = expected[lane]
            self.assertEqual((model.nq, model.nv, model.njnt, model.neq), (nq, nv, njnt, neq))
            self.assertEqual(model.nu, 6)
            for joint_name in core.R_JOINTS:
                self.assertGreaterEqual(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name), 0)
            p_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in core.P_JOINTS]
            if lane == "LOCKED_2P_REDUCED_6R":
                self.assertEqual(p_ids, [-1, -1])
            else:
                self.assertTrue(all(identifier >= 0 for identifier in p_ids))
        self.assertFalse(self.contract["lanes"]["LOCKED_2P_EQUALITY_6R2P"]["exact_kkt_claim_allowed"])

    def test_09_free_root_zero_gravity_and_noncontact_are_enforced(self) -> None:
        contact_bit = int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
        for lane, (xml_bytes, _) in self.rendered.items():
            xml_root = ET.fromstring(xml_bytes)
            flag = xml_root.find("./option/flag")
            self.assertIsNotNone(flag)
            self.assertEqual(flag.get("contact"), "disable")
            self.assertIsNone(xml_root.find("./contact"))
            self.assertTrue(
                all(
                    node.get("contype") == "0" and node.get("conaffinity") == "0"
                    for node in xml_root.iter("geom")
                )
            )
            model, data = core.compile_lane(xml_bytes)
            free_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "servicer_free")
            root_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "spacecraft_bus")
            self.assertGreaterEqual(free_id, 0)
            self.assertEqual(int(model.jnt_type[free_id]), int(mujoco.mjtJoint.mjJNT_FREE))
            self.assertEqual(int(model.jnt_bodyid[free_id]), root_id)
            self.assertTrue(all(float(value) == 0.0 for value in model.opt.gravity))
            self.assertTrue(int(model.opt.disableflags) & contact_bit)
            self.assertTrue(all(int(value) == 0 for value in model.geom_contype))
            self.assertTrue(all(int(value) == 0 for value in model.geom_conaffinity))
            mujoco.mj_forward(model, data)
            self.assertEqual(data.ncon, 0)
            self.assertAlmostEqual(float(np.sum(model.body_mass)), self.contract["model"]["total_mass_kg"], places=12)

    def test_10_initial_state_mapping_normalizes_quaternion_and_sets_qp(self) -> None:
        for lane, (xml_bytes, _) in self.rendered.items():
            model, data = core.compile_lane(xml_bytes)
            core.set_state(model, data, self.contract, lane)
            self.assertAlmostEqual(float(np.linalg.norm(data.qpos[3:7])), 1.0, places=14)
            q_r_addresses, _ = core._joint_addresses(model, core.R_JOINTS)
            np.testing.assert_allclose(
                data.qpos[q_r_addresses],
                self.contract["initial_state"]["q8_mixed_rad_m"][:6],
                rtol=0.0,
                atol=1e-15,
            )
            if lane != "LOCKED_2P_REDUCED_6R":
                q_p_addresses, _ = core._joint_addresses(model, core.P_JOINTS)
                np.testing.assert_allclose(
                    data.qpos[q_p_addresses],
                    self.contract["model"]["qP_star_m"],
                    rtol=0.0,
                    atol=1e-15,
                )

    def test_11_tau_p_zero_is_not_a_lock(self) -> None:
        diagnostic = core.soft_equality_diagnostic(
            self.contract,
            self.rendered["LOCKED_2P_EQUALITY_6R2P"][0],
            self.rendered["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"][0],
        )
        equality = diagnostic["LOCKED_2P_EQUALITY_6R2P"]
        free = diagnostic["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]
        self.assertFalse(equality["exact_kkt_lock_reproduced_claim"])
        self.assertGreater(free["qP_drift_max_abs_m"], equality["qP_drift_max_abs_m"])
        self.assertGreater(diagnostic["unlock_drift_ratio_to_equality"], 1.0)

    def test_12_authority_boundary_is_literal_false(self) -> None:
        boundary = self.contract["authority_boundaries"]
        self.assertTrue(boundary)
        self.assertTrue(all(value is False for value in boundary.values()))
        self.assertIs(self.contract["next_stage_authorized"], False)
        self.assertIs(self.contract["release_credit"], False)

    def test_13_independent_static_validator_passes_without_core_import(self) -> None:
        report = independent.validate(require_results=False)
        self.assertFalse(report["candidate_core_imported"])
        self.assertTrue(report["independent_validation_pass"])
        self.assertEqual(report["groups_passed"], report["groups_total"])
        self.assertIs(report["next_stage_authorized"], False)
        self.assertIs(report["release_credit"], False)

    def test_14_full_result_validation_when_results_exist(self) -> None:
        required = (independent.GATE_PATH, independent.MANIFEST_PATH, independent.SHA_CSV_PATH)
        if not all(path.is_file() for path in required):
            return
        report = independent.validate(require_results=True)
        self.assertTrue(report["independent_validation_pass"], json.dumps(report, ensure_ascii=False))
        self.assertTrue(report["group_pass"]["IV-G2_GATE_AUTHORITY_BOUNDARY"])
        self.assertTrue(report["group_pass"]["IV-G3_PACKAGE_MANIFEST"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
