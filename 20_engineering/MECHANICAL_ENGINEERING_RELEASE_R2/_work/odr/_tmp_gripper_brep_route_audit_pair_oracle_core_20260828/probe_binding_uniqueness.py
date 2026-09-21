#!/usr/bin/env python3
"""Quantify deterministic fingerprint-binding margins for selected finger solids."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment


HERE = Path(__file__).resolve().parent
AUDIT = HERE / "audit_extract_finger_breps.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("finger_audit", AUDIT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audit helpers")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    builder = audit.load_r1_builder()
    receipt = json.loads(builder.V5_RECEIPT.read_text(encoding="utf-8"))
    evidence = list(receipt["source_open"]["evidence"])
    model = audit.import_step(builder.NEUTRAL_STEP)
    solids = list(model.solids())
    assignment, _semantic = builder.read_assignment()

    costs = []
    for solid in solids:
        ibox = builder.bbox_values(solid)
        icenter, isize = builder.center_and_size(ibox)
        ivolume = float(solid.volume)
        row = []
        for target in evidence:
            tbox = [float(value) for value in target["bbox_mm"]]
            tcenter, tsize = builder.center_and_size(tbox)
            center_delta = builder.vector_norm(a - b for a, b in zip(icenter, tcenter))
            size_delta = builder.vector_norm(a - b for a, b in zip(isize, tsize))
            row.append(
                center_delta
                + 0.25 * size_delta
                + 10.0 * abs(math.log(max(ivolume, 1e-12) / float(target["volume_mm3"])))
            )
        costs.append(row)
    matrix = np.asarray(costs, dtype=float)
    source_indices, target_indices = linear_sum_assignment(matrix)
    rows = []
    for source_index, target_index in zip(source_indices, target_indices):
        name = str(evidence[int(target_index)]["mapped_source_name"])
        group = assignment[name]
        if group not in ("gripper_left", "gripper_right"):
            continue
        row_values = np.sort(matrix[int(source_index), :])
        column_values = np.sort(matrix[:, int(target_index)])
        rows.append(
            {
                "source_name": name,
                "group": group,
                "source_index": int(source_index),
                "target_index": int(target_index),
                "assigned_cost": float(matrix[int(source_index), int(target_index)]),
                "row_runner_up_margin": float(row_values[1] - matrix[int(source_index), int(target_index)]),
                "column_runner_up_margin": float(column_values[1] - matrix[int(source_index), int(target_index)]),
                "assigned_is_unique_row_minimum": bool(
                    abs(row_values[0] - matrix[int(source_index), int(target_index)]) <= 1e-14
                    and row_values[1] > row_values[0]
                ),
                "assigned_is_unique_column_minimum": bool(
                    abs(column_values[0] - matrix[int(source_index), int(target_index)]) <= 1e-14
                    and column_values[1] > column_values[0]
                ),
            }
        )
    report = {
        "schema": "TEMP_B601_GRIPPER_B50_V5_BINDING_UNIQUENESS_PROBE_V1",
        "authority": "TEMPORARY_READ_ONLY_NO_CREDIT",
        "selected_count": len(rows),
        "all_selected_unique_row_minimum": all(row["assigned_is_unique_row_minimum"] for row in rows),
        "all_selected_unique_column_minimum": all(row["assigned_is_unique_column_minimum"] for row in rows),
        "minimum_row_runner_up_margin": min(row["row_runner_up_margin"] for row in rows),
        "minimum_column_runner_up_margin": min(row["column_runner_up_margin"] for row in rows),
        "ten_smallest_row_margins": sorted(rows, key=lambda row: row["row_runner_up_margin"])[:10],
        "ten_smallest_column_margins": sorted(rows, key=lambda row: row["column_runner_up_margin"])[:10],
    }
    output = HERE / "TEMP_B601_GRIPPER_B50_V5_BINDING_UNIQUENESS_PROBE_V1.json"
    if output.exists():
        raise RuntimeError(f"refusing overwrite: {output}")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
