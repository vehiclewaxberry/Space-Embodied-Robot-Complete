"""Independent read-only validator for the CHECKPOINT-B package."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
CAD_SUFFIXES = {".fcstd", ".step", ".stp", ".stl", ".glb", ".obj", ".iges", ".igs"}
ROUTE_C_ROOT = PROJECT_ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"CHECKPOINT_B_VALIDATION_FAIL: {message}")


def main() -> None:
    hash_path = HERE / "CHECKPOINT_B_SHA256.csv"
    with hash_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 16, f"expected 16 hash rows, got {len(rows)}")
    for row in rows:
        path = PROJECT_ROOT / row["path"]
        require(path.is_file(), f"missing pinned file: {row['path']}")
        require(path.stat().st_size == int(row["bytes"]), f"byte count mismatch: {row['path']}")
        require(digest(path) == row["sha256"], f"SHA-256 mismatch: {row['path']}")

    gate = json.loads((HERE / "ROUTE_C_CHECKPOINT_B_GATE_V1.json").read_text(encoding="utf-8"))
    require(gate["checkpoint_reached"] is True and gate["checkpoint_outcome"] == "HOLD",
            "checkpoint state changed")
    require(gate["evaluation_integrity"]["summary"] == {"passed": 8, "total": 8, "failed": []},
            "integrity tally changed")
    require(gate["admission"]["summary"]["pass"] == 2 and
            gate["admission"]["summary"]["fail"] == 6 and
            gate["admission"]["ROUTE_C_CAD_AUTHORIZED"] is False,
            "admission state changed")
    require(gate["physical_registry"]["entries_total"] == 13 and
            gate["physical_registry"]["value_non_null"] == 0 and
            gate["physical_registry"]["status_HOLD"] == 13,
            "physical registry count changed")
    require(all(item["value"] is None and item["value_uncertainty"] is None and
                item["status"] == "HOLD" for item in gate["physical_registry"]["fields"]),
            "a physical field was promoted or null-coerced")
    require(gate["rfi_state"]["rfi_ids"] == ["RFI-E", "RFI-F", "RFI-G"] and
            gate["rfi_state"]["responses_received"] == 0,
            "RFI state changed")

    with (HERE / "CHECKPOINT_B_PHYSICAL_INPUT_MATRIX_V1.csv").open(
            "r", encoding="utf-8-sig", newline="") as handle:
        matrix = list(csv.DictReader(handle))
    require(len(matrix) == 13, f"matrix expected 13 rows, got {len(matrix)}")
    require(all(row["value"] == "" and row["value_uncertainty"] == "" and
                row["status"] == "HOLD" and row["candidate_source_is_authority"] == "false"
                for row in matrix), "matrix contains an unauthorized value or promotion")

    cad_assets = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in ROUTE_C_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in CAD_SUFFIXES
    ]
    require(not cad_assets, f"unauthorized Route-C CAD found: {cad_assets}")

    print(json.dumps({
        "schema": "CHECKPOINT_B_INDEPENDENT_VALIDATION_STDOUT_V1",
        "pass": True,
        "hash_rows_verified": len(rows),
        "matrix_rows_verified": len(matrix),
        "admission": "2/8 PASS; 6/8 FAIL",
        "registry": "0/13 non-null; 13/13 HOLD",
        "route_c_cad_assets_found": 0,
        "ROUTE_C_CAD_AUTHORIZED": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
