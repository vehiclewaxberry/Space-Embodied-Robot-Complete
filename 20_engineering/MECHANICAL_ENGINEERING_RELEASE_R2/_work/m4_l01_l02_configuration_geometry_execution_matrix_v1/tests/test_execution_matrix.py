from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

import build_execution_matrix as builder  # noqa: E402
import frozen_execution_spec_v1 as spec  # noqa: E402
import validate_execution_matrix as validator  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def test_nine_current_configurations_are_all_fail_closed() -> None:
    assert spec.CONFIG_IDS == tuple(f"C{i:02d}" for i in range(1, 10))
    assert len(spec.CONFIGURATIONS) == 9
    assert all(row["configuration_current_step_buildable_now"] is False for row in spec.CONFIGURATIONS)
    assert all(row["current_complete_integrated_geometry"] is False for row in spec.CONFIGURATIONS)


def test_c01_qhome_cannot_be_replaced_by_fixed_q0() -> None:
    assert spec.CONFIGURATIONS[0]["authoritative_q6_rad"] == spec.Q_HOME
    assert spec.D01_CONTRACT["q6_rad"] == spec.Q_ZERO
    assert spec.Q_HOME != spec.Q_ZERO
    assert spec.D01_CONTRACT["configuration_current"] is False
    assert spec.D01_CONTRACT["reason_not_c01_current"] == "STATIC_CAD_Q0_CANNOT_STAND_IN_FOR_C01_QHOME"


def test_c05_c09_authoritative_q_and_all_target_attachments_remain_null() -> None:
    assert all(row["authoritative_q6_rad"] is None for row in spec.CONFIGURATIONS[4:])
    assert all(row["target_attachment_transform_S_rows"] is None for row in spec.CONFIGURATIONS)
    assert spec.CONFIGURATIONS[7]["target_attached"] is True
    assert spec.CONFIGURATIONS[8]["target_attached"] is True


def test_d01_counts_groups_bbox_and_datum_are_frozen() -> None:
    contract = spec.D01_CONTRACT
    assert len(contract["master_retained"]) == 9
    assert len(contract["solar_selected"]) == 6
    assert contract["b601_source_shape_count"] == 388
    assert contract["expected"]["groups"] == {
        "B601_FULL_ARM_FIXED_Q0_INSTALLED": 388,
        "R2_SERVICER_CORE_WITHOUT_LEGACY_SOLAR_AXIS_WITNESS_OR_DETACHED_PALM": 9,
        "SOLAR_R2_DEPLOYED_LEAVES_ONLY": 6,
    }
    assert contract["expected"]["leaf_solid_count"] == 403
    assert contract["expected"]["intermediate_group_count"] == 3
    assert contract["expected"]["bbox_S_mm"] == {
        "min": [-230.25, -715.4, -274.86072587989787],
        "max": [488.533214, 715.4, 285.63229786565915],
        "absolute_tolerance_mm": 0.1,
    }
    assert contract["expected"]["m3r_arm_datum"] == {
        "installed_b601_min_x_mm": 210.405,
        "m3r_outer_face_x_mm": 210.405,
        "absolute_tolerance_mm": 0.01,
    }


def test_units_frames_placements_and_structured_unknowns() -> None:
    assert spec.D01_CONTRACT["units"] == "mm"
    assert spec.D01_CONTRACT["root_frame"] == "S"
    assert spec.FRAME_LEDGER["unit_policy"]["urdf_length"] == "m"
    assert spec.D01_CONTRACT["placements"]["B601_FIXED_Q0_LOCAL_TO_S_ROWS_MM"] == spec.T_S_B601_ARM_BASE_ROWS_MM
    for key in ("TARGET_22KG", "TARGET_150KG", "ARM_HDRM", "SOLAR_HDRM_HARDWARE"):
        assert key in spec.D01_CONTRACT["placements"]
        assert spec.D01_CONTRACT["placements"][key] is None


def test_solar_selection_excludes_stowed_and_keepout_shapes() -> None:
    assert [row["index"] for row in spec.D01_CONTRACT["solar_selected"]] == [7, 8, 9, 10, 11, 12]
    assert spec.D01_CONTRACT["solar_rejected_ranges"] == [
        {"indices": [1, 6], "reason": "STOWED_LEAVES_NOT_PART_OF_DEPLOYED_DIAGNOSTIC"},
        {"indices": [13, 18], "reason": "HINGE_KEEPOUTS_ARE_NOT_HARDWARE_SOLIDS"},
        {"indices": [19, 22], "reason": "HDRM_KEEPOUTS_ARE_NOT_HARDWARE_SOLIDS"},
    ]


def test_source_lock_exact_and_externally_recomputed() -> None:
    checks = validator.evaluate_core(PACKAGE, validator.workspace_root(PACKAGE), verify_external_sources=True)
    assert checks
    assert all(row["pass"] for row in checks), [row for row in checks if not row["pass"]]


def test_generator_ast_has_no_top_level_cad_import_and_keeps_gates_before_import() -> None:
    path = PACKAGE / "source_only_step_generator_v1.py"
    ast.parse(path.read_text(encoding="utf-8"))
    no_top, delayed, gated, guards = validator._generator_ast_checks(path)
    assert (no_top, delayed, gated, guards) == (True, True, True, True)
    assert not ({"OCP", "build123d"} & set(sys.modules))


def test_no_geometry_output_and_snapshots_are_unexecuted() -> None:
    assert not list(PACKAGE.glob("*.step"))
    assert not list(PACKAGE.glob("*.stp"))
    assert not list(PACKAGE.glob("*.FCStd"))
    snapshot = validator.strict_json(PACKAGE / "SNAPSHOT_TASK_PLAN_V1.json")
    assert all(row["executed"] is False and row["artifact"] is None for row in snapshot["tasks"])


def test_duplicate_keys_and_nonfinite_numbers_fail_closed() -> None:
    # Use a private, automatically removed directory under this owned package.
    # Some Windows hosts expose a stale, unreadable global pytest temp root.
    with tempfile.TemporaryDirectory(prefix="strict_json_test_", dir=PACKAGE) as temp:
        temp_path = Path(temp)
        duplicate = temp_path / "duplicate.json"
        duplicate.write_text('{"x": 1, "x": 2}\n', encoding="utf-8")
        with pytest.raises(validator.ValidationError, match="DUPLICATE_JSON_KEY"):
            validator.strict_json(duplicate)
        nonfinite = temp_path / "nan.json"
        nonfinite.write_text('{"x": NaN}\n', encoding="utf-8")
        with pytest.raises(validator.ValidationError, match="NONFINITE_JSON_CONSTANT"):
            validator.strict_json(nonfinite)


def test_negative_receipt_is_36_of_36_and_boundaries_false() -> None:
    receipt = validator.strict_json(PACKAGE / validator.NEGATIVE_NAME)
    assert receipt["expected_count"] == receipt["executed_count"] == receipt["passed_count"] == spec.NEGATIVE_CONTROL_COUNT == 36
    assert receipt["all_passed"] is True
    assert len({row["id"] for row in receipt["results"]}) == 36
    assert receipt["next_stage_authorized"] is False
    assert receipt["release_credit"] is False


def test_gate_is_30_of_30_with_zero_current_and_one_diagnostic() -> None:
    gate = validator.strict_json(PACKAGE / validator.GATE_NAME)
    assert gate["gate_passed"] is True
    assert gate["passed_count"] == gate["expected_count"] == spec.GATE_CRITERION_COUNT == 30
    assert gate["configuration_current_step_buildable_count"] == 0
    assert gate["source_only_diagnostic_recipe_count"] == 1
    for key in (
        "parent_gate_credit", "configuration_credit", "fresh_cad_run_authorized",
        "memory_gate_passed", "owner_override_present", "cad_kernel_loaded",
        "step_generation_executed", "collision_authority", "contact_authority",
        "mass_authority", "next_stage_authorized", "operational_authorized",
        "production_complete", "release_credit",
    ):
        assert gate[key] is False


def test_independent_full_validator_and_manifest_pass() -> None:
    checks = validator.evaluate_all(PACKAGE, validator.workspace_root(PACKAGE), verify_external_sources=False)
    assert len(checks) > 60
    assert all(row["pass"] for row in checks), [row for row in checks if not row["pass"]]


def test_builder_is_deterministic_after_negative_receipt() -> None:
    controlled = [PACKAGE / name for name in spec.LOCAL_MANIFEST_ROLES if name not in {
        "README.md", "build_execution_matrix.py", "frozen_execution_spec_v1.py",
        "source_only_step_generator_v1.py", "validate_execution_matrix.py",
        "run_negative_controls.py", "tests/test_execution_matrix.py",
    }]
    first_gate = builder.build()
    first_hashes = {path.name: sha256(path) for path in controlled}
    second_gate = builder.build()
    second_hashes = {path.name: sha256(path) for path in controlled}
    assert first_gate == second_gate
    assert first_hashes == second_hashes
