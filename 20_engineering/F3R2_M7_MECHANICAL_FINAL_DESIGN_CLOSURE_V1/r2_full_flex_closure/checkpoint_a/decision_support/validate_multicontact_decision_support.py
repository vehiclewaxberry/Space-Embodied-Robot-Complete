"""Read-only cross-artifact validator for multi-contact ROM decision support."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "MULTICONTACT_ROM_DIMENSION_DECISION_SUPPORT_V1.json"
NOMINAL = HERE.parent / "red_team/ROM5_DIMENSION_FALSIFIER_V1.json"
EXPECTED_SOURCE_SHA256 = "3237660693EC9790223559028264E115AEAB45AAA8A37250E0A58A5CAA81341D"
EXPECTED_NOMINAL_SHA256 = "D219E69FE8D3555228BB007774F0B59F4F5BDFAD7711569EB7CD074130104E18"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"MULTICONTACT_VALIDATION_FAIL:{message}")


def close(left: float, right: float, tolerance: float = 1.0e-14) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def main() -> None:
    require(digest(SOURCE) == EXPECTED_SOURCE_SHA256, "decision-support hash drift")
    require(digest(NOMINAL) == EXPECTED_NOMINAL_SHA256, "nominal falsifier hash drift")
    current = json.loads(SOURCE.read_text(encoding="utf-8"))
    nominal = json.loads(NOMINAL.read_text(encoding="utf-8"))

    n20 = current["per_window"]["TC_20MS"]
    old = nominal["dimension_combination_falsifier"]
    require(n20["minimum_passing_dimension_within_first12"] ==
            old["minimum_passing_dimension_within_first12"] == 6,
            "20 ms minimum dimension does not reproduce nominal falsifier")
    require(n20["minimum_passing_dimension_preserving_three_bending"] ==
            old["minimum_passing_dimension_preserving_all_three_bending_modes"] == 7,
            "20 ms three-bending minimum does not reproduce nominal falsifier")
    require(close(n20["minimum_passing_subset"]["global_max_relative_error"],
                  old["best_six_dimensional_subset"]["global_max_relative_error"]),
            "20 ms 6D score mismatch")
    require(close(n20["minimum_passing_subset_preserving_three_bending"]
                  ["global_max_relative_error"],
                  old["best_seven_dimensional_subset_preserving_three_bending_modes"]
                  ["global_max_relative_error"]), "20 ms 7D score mismatch")

    for key, item in current["per_window"].items():
        old_item = nominal["contact_window_sensitivity"][key]
        require(close(item["round3_rom5"]["per_wing_relative_errors"]["L"]
                      ["torsion_peak_rad"], old_item["current_first_two_relative_error"]),
                f"{key} Round3 torsion error mismatch")

    fixed = current["single_fixed_basis_across_all_windows"]
    require(fixed["minimum_passing_dimension_within_first12"] == 11,
            "fixed all-window minimum is not 11")
    require(fixed["minimum_passing_dimension_preserving_three_bending"] == 11,
            "three-bending all-window minimum is not 11")
    for dimension in range(1, 11):
        require(fixed["best_by_dimension_1_to_12"][str(dimension)]
                ["passes_1pct_all_windows"] is False,
                f"dimension {dimension} unexpectedly passes")
    selected = fixed["minimum_passing_subset"]
    require(selected["labels"] ==
            ["B1", "T1", "T2", "B2", "T3", "T4", "T5", "B3", "T6", "T7", "T8"],
            "11D basis membership changed")
    require(selected["passes_1pct_all_windows"] is True and
            selected["global_max_relative_error_across_windows"] < 0.01,
            "11D basis does not pass all windows")

    print(json.dumps({
        "schema": "MULTICONTACT_ROM_DIMENSION_VALIDATION_STDOUT_V1",
        "pass": True,
        "source_hash_verified": True,
        "nominal_20ms_cross_artifact_reproduction": True,
        "contact_window_torsion_cross_artifact_reproduction": "5/5",
        "dimensions_1_to_10_fail_all_window_contract": True,
        "minimum_fixed_dimension": 11,
        "minimum_fixed_dimension_preserving_three_bending": 11,
        "maximum_error_11D": selected["global_max_relative_error_across_windows"],
        "owner_contract_changed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
