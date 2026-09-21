#!/usr/bin/env python3
"""Generate the seeded 2 x 3 x 3 categorical pilot design without executing it."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import random
from pathlib import Path

M3 = Path(__file__).resolve().parents[1]
OUTPUT = M3 / "11_validation" / "M3_COUPLED_CAPTURE_PILOT_RUN_PLAN.csv"
RECEIPT = M3 / "11_validation" / "M3_COUPLED_CAPTURE_PILOT_RUN_PLAN_RECEIPT.json"
SEED = 20260821

FACTORS = {
    "target_anchor": ["ANCHOR_22KG_0P5DPS", "ANCHOR_150KG_3DPS"],
    "capture_timing_id": ["T_EARLY", "T_NOMINAL", "T_LATE"],
    "strategy_id": ["S1", "S3a", "ABORT"],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    combinations = list(itertools.product(*FACTORS.values()))
    rng = random.Random(SEED)
    rng.shuffle(combinations)
    rows = []
    for run_order, values in enumerate(combinations, start=1):
        row = dict(zip(FACTORS, values))
        row.update(
            {
                "run_order": run_order,
                "independent_replicate_id": "",
                "replicate_seed": "",
                "execution_status": "PLANNED_NOT_EXECUTABLE",
                "block_geometry_hash": "",
                "block_solver_version": "",
            }
        )
        rows.append(row)
    fieldnames = [
        "run_order",
        *FACTORS.keys(),
        "independent_replicate_id",
        "replicate_seed",
        "execution_status",
        "block_geometry_hash",
        "block_solver_version",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    receipt = {
        "schema": "M3_COUPLED_CAPTURE_PILOT_RUN_PLAN_RECEIPT_V1",
        "design": "FULL_CATEGORICAL_FACTORIAL_2_X_3_X_3",
        "design_cell_count": len(rows),
        "randomization_seed": SEED,
        "run_order_unique_count": len({row["run_order"] for row in rows}),
        "factor_level_coverage": {
            key: sorted({row[key] for row in rows}) for key in FACTORS
        },
        "replicate_count": None,
        "replicate_status": "HOLD_UNTIL_VARIANCE_OR_UNCERTAINTY_MODEL_EXISTS",
        "execution_authorized": False,
        "execution_status": "HOLD_CONTACT_PHYSICS_MASS_PROPERTIES_AND_ACCEPTANCE_INPUTS",
        "output_path": str(OUTPUT.relative_to(M3)).replace("\\", "/"),
        "output_sha256": sha256(OUTPUT),
        "status": "PASS_PLAN_STRUCTURE_ONLY",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
