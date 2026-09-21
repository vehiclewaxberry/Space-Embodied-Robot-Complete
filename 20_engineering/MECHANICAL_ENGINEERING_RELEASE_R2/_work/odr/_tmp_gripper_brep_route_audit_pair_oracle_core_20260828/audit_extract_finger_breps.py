#!/usr/bin/env python3
"""Temporary, non-authoritative audit of the R1 B601 finger BRep extraction route.

This script deliberately reuses the frozen R1 builder's source binding functions.
It never writes outside its own directory and never executes a system collision query.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import time
from pathlib import Path
from typing import Any, Iterable

# build123d 0.11.1 scans every Windows font at import time.  One host font is
# malformed, so install the canary alias before importing build123d.  This does
# not affect geometry or the OCCT STEP writer.
from OCP.Font import Font_FontMgr
from OCP.TCollection import TCollection_AsciiString

_font_manager = Font_FontMgr.GetInstance_s()
_font_manager.AddFontAlias(
    TCollection_AsciiString("singleline"),
    TCollection_AsciiString("Arial"),
)

import numpy as np
import trimesh
from build123d import Compound, export_step, export_stl, import_step
from OCP.BRepCheck import BRepCheck_Analyzer
from scipy.spatial import cKDTree


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
HERE = Path(__file__).resolve().parent
R1_BUILDER = (
    ROOT
    / "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/99_tools"
    / "gripper_r1_build_and_validate.py"
)
R1_DIR = (
    ROOT
    / "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/01_native_cad/gripper_r1"
)
M5_DIR = (
    ROOT
    / "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1"
    / "01_geometry_authority/assets/b601_link_local_surfaces"
)
FROZEN_TIMESTAMP = "2026-08-28T00:00:00+00:00"
STEP_NAMES = {
    "left": "B601_GRIPPER_LEFT_FINGER_GRIPPER_LINK_LOCAL_R1_SOURCE.step",
    "right": "B601_GRIPPER_RIGHT_FINGER_GRIPPER_LINK_LOCAL_R1_SOURCE.step",
}
R1_STL = {
    "left": R1_DIR / "B601_GRIPPER_LEFT_FINGER_NEUTRAL_SOURCE.stl",
    "right": R1_DIR / "B601_GRIPPER_RIGHT_FINGER_NEUTRAL_SOURCE.stl",
}
M5_PLY = {
    "left": M5_DIR / "B601_GRIPPER_R1_LEFT_FINGER_GRIPPER_LINK_LOCAL_M.ply",
    "right": M5_DIR / "B601_GRIPPER_R1_RIGHT_FINGER_GRIPPER_LINK_LOCAL_M.ply",
}
PALM_STEP = R1_DIR / "B601_GRIPPER_PALM_RAIL_SLOT_R1.step"


def load_r1_builder() -> Any:
    spec = importlib.util.spec_from_file_location("frozen_gripper_r1_builder", R1_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load R1 builder: {R1_BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def bbox(shape: Any) -> list[float]:
    box = shape.bounding_box()
    return [
        float(box.min.X),
        float(box.min.Y),
        float(box.min.Z),
        float(box.max.X),
        float(box.max.Y),
        float(box.max.Z),
    ]


def canonical_solid_rows(shape: Any, digits: int = 8) -> list[dict[str, Any]]:
    rows = []
    for solid in shape.solids():
        rows.append(
            {
                "bbox_mm": [round(value, digits) for value in bbox(solid)],
                "volume_mm3": round(float(solid.volume), digits),
                "area_mm2": round(float(solid.area), digits),
                "faces": len(solid.faces()),
                "edges": len(solid.edges()),
            }
        )
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))


def canonical_digest(shape: Any) -> str:
    payload = json.dumps(
        canonical_solid_rows(shape),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def shape_facts(shape: Any) -> dict[str, Any]:
    solids = list(shape.solids())
    return {
        "ocp_compound_valid": bool(BRepCheck_Analyzer(shape.wrapped).IsValid()),
        "solid_count": len(solids),
        "all_solids_ocp_valid": all(BRepCheck_Analyzer(item.wrapped).IsValid() for item in solids),
        "all_solids_build123d_valid": all(bool(item.is_valid) for item in solids),
        "all_solids_positive_volume": all(float(item.volume) > 0.0 for item in solids),
        "volume_mm3": float(sum(float(item.volume) for item in solids)),
        "bbox_mm": bbox(shape),
        "canonical_geometry_sha256": canonical_digest(shape),
    }


def load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(path, process=False)
    if isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise RuntimeError(f"empty mesh scene: {path}")
        loaded = trimesh.util.concatenate(tuple(loaded.geometry.values()))
    if not isinstance(loaded, trimesh.Trimesh):
        raise TypeError(f"unexpected mesh type for {path}: {type(loaded).__name__}")
    return loaded


def sampled_vertices(vertices: np.ndarray, maximum: int = 50_000) -> np.ndarray:
    values = np.asarray(vertices, dtype=np.float64)
    if len(values) <= maximum:
        return values
    indices = np.linspace(0, len(values) - 1, maximum, dtype=np.int64)
    return values[indices]


def nearest_residual(source: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    query = sampled_vertices(source)
    distances, _ = cKDTree(np.asarray(target, dtype=np.float64)).query(query, k=1)
    return {
        "sample_count": int(len(query)),
        "maximum_mm": float(np.max(distances)),
        "p99_mm": float(np.quantile(distances, 0.99)),
        "median_mm": float(np.median(distances)),
    }


def mesh_comparison(
    brep_shape: Any,
    fresh_stl_path: Path,
    frozen_r1_stl_path: Path,
    m5_ply_path: Path,
) -> dict[str, Any]:
    fresh = load_mesh(fresh_stl_path)
    frozen = load_mesh(frozen_r1_stl_path)
    m5 = load_mesh(m5_ply_path)
    fresh_vertices_mm = np.asarray(fresh.vertices, dtype=np.float64)
    frozen_vertices_mm = np.asarray(frozen.vertices, dtype=np.float64)
    m5_vertices_mm = np.asarray(m5.vertices, dtype=np.float64) * 1000.0
    brep_bbox = np.asarray(bbox(brep_shape), dtype=np.float64).reshape((2, 3))

    return {
        "fresh_stl_sha256": sha256(fresh_stl_path),
        "frozen_r1_stl_sha256": sha256(frozen_r1_stl_path),
        "fresh_stl_byte_identical_to_frozen_r1": sha256(fresh_stl_path) == sha256(frozen_r1_stl_path),
        "m5_ply_sha256": sha256(m5_ply_path),
        "brep_bbox_mm": brep_bbox.tolist(),
        "fresh_stl_bbox_mm": np.asarray(fresh.bounds, dtype=float).tolist(),
        "frozen_r1_stl_bbox_mm": np.asarray(frozen.bounds, dtype=float).tolist(),
        "m5_ply_bbox_mm_after_explicit_x1000": np.asarray(m5.bounds, dtype=float).__mul__(1000.0).tolist(),
        "brep_to_fresh_stl_bbox_endpoint_max_abs_mm": float(np.max(np.abs(brep_bbox - fresh.bounds))),
        "brep_to_frozen_r1_bbox_endpoint_max_abs_mm": float(np.max(np.abs(brep_bbox - frozen.bounds))),
        "brep_to_m5_bbox_endpoint_max_abs_mm": float(np.max(np.abs(brep_bbox - m5.bounds * 1000.0))),
        "brep_volume_mm3": float(brep_shape.volume),
        "fresh_stl_abs_volume_mm3": float(abs(fresh.volume)),
        "frozen_r1_stl_abs_volume_mm3": float(abs(frozen.volume)),
        "m5_ply_abs_volume_mm3_after_x1e9": float(abs(m5.volume) * 1.0e9),
        "fresh_to_frozen_vertex_registration": nearest_residual(fresh_vertices_mm, frozen_vertices_mm),
        "frozen_to_fresh_vertex_registration": nearest_residual(frozen_vertices_mm, fresh_vertices_mm),
        "fresh_to_m5_vertex_registration": nearest_residual(fresh_vertices_mm, m5_vertices_mm),
        "m5_to_fresh_vertex_registration": nearest_residual(m5_vertices_mm, fresh_vertices_mm),
    }


def export_and_reopen(name: str, shape: Any) -> dict[str, Any]:
    label = f"B601_GRIPPER_{name.upper()}_FINGER_GRIPPER_LINK_LOCAL_R1_SOURCE"
    shape.label = label
    paths = []
    # run_a/run_b may contain a deliberately retained partial probe from an
    # earlier host-API compatibility failure; use fresh names and never delete
    # pre-existing temporary evidence.
    for run in ("verified_run_a", "verified_run_b"):
        folder = HERE / run
        folder.mkdir(exist_ok=True)
        path = folder / STEP_NAMES[name]
        if path.exists():
            raise RuntimeError(f"temporary output already exists; refusing overwrite: {path}")
        export_step(shape, path, timestamp=FROZEN_TIMESTAMP)
        paths.append(path)
        time.sleep(1.1)

    reopen = [import_step(path) for path in paths]
    source_facts = shape_facts(shape)
    reopen_facts = [shape_facts(item) for item in reopen]
    stl_path = HERE / "runtime_probe" / f"B601_GRIPPER_{name.upper()}_FINGER_NEUTRAL_SOURCE_REEXPORT.stl"
    stl_path.parent.mkdir(exist_ok=True)
    if stl_path.exists():
        raise RuntimeError(f"temporary output already exists; refusing overwrite: {stl_path}")
    export_stl(shape, stl_path, tolerance=0.05, angular_tolerance=0.1)

    return {
        "label": label,
        "source": source_facts,
        "fixed_timestamp": FROZEN_TIMESTAMP,
        "exports": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in paths
        ],
        "bitwise_repeatable_across_distinct_directories_and_seconds": sha256(paths[0]) == sha256(paths[1]),
        "reopen": reopen_facts,
        "reopen_solid_count_exact": all(item["solid_count"] == source_facts["solid_count"] for item in reopen_facts),
        "reopen_geometry_digest_exact": all(
            item["canonical_geometry_sha256"] == source_facts["canonical_geometry_sha256"] for item in reopen_facts
        ),
        "maximum_reopen_volume_abs_delta_mm3": max(
            abs(item["volume_mm3"] - source_facts["volume_mm3"]) for item in reopen_facts
        ),
        "maximum_reopen_bbox_endpoint_abs_delta_mm": max(
            max(abs(a - b) for a, b in zip(item["bbox_mm"], source_facts["bbox_mm"])) for item in reopen_facts
        ),
        "fresh_stl_path": str(stl_path),
        "mesh_registration": mesh_comparison(shape, stl_path, R1_STL[name], M5_PLY[name]),
    }


def main() -> None:
    builder = load_r1_builder()
    input_facts = builder.audit_fixed_inputs()
    receipt = json.loads(builder.V5_RECEIPT.read_text(encoding="utf-8"))
    evidence = list(receipt["source_open"]["evidence"])
    assignment, _semantic = builder.read_assignment()
    neutral_model = import_step(builder.NEUTRAL_STEP)
    bound, binding_rows = builder.bind_neutral_solids(neutral_model, evidence)

    selected_names = {
        "left": sorted(name for name, group in assignment.items() if group == "gripper_left"),
        "right": sorted(name for name, group in assignment.items() if group == "gripper_right"),
    }
    candidates = {
        side: Compound(children=[bound[name] for name in names])
        for side, names in selected_names.items()
    }

    results = {side: export_and_reopen(side, candidates[side]) for side in ("left", "right")}
    palm = import_step(PALM_STEP)
    selected_rows = {
        side: [row for row in binding_rows if row["source_name"] in set(selected_names[side])]
        for side in ("left", "right")
    }
    receipt_out = {
        "schema": "TEMP_B601_GRIPPER_2P_BREP_EXTRACTION_ROUTE_AUDIT_V1",
        "authority": "TEMPORARY_READ_ONLY_ROUTE_AUDIT_NO_PROJECT_GATE_OR_CREDIT",
        "inputs": {
            "neutral_b50_step": input_facts[str(builder.NEUTRAL_STEP)],
            "v5_receipt": input_facts[str(builder.V5_RECEIPT)],
            "assignment_csv": input_facts[str(builder.ASSIGNMENT_CSV)],
            "palm_r1_step": {
                "path": str(PALM_STEP),
                "sha256": sha256(PALM_STEP),
            },
            "r1_builder": {"path": str(R1_BUILDER), "sha256": sha256(R1_BUILDER)},
        },
        "binding": {
            "method": "EXACT_REUSE_OF_FROZEN_R1_HUNGARIAN_ONE_TO_ONE_B50_TO_V5_RECEIPT_BINDING",
            "neutral_solid_count": len(list(neutral_model.solids())),
            "receipt_evidence_count": len(evidence),
            "assigned_counts": {side: len(names) for side, names in selected_names.items()},
            "left_names": selected_names["left"],
            "right_names": selected_names["right"],
            "selected_residual_maxima": {
                side: {
                    "center_delta_mm": max(row["center_delta_mm"] for row in selected_rows[side]),
                    "size_delta_mm": max(row["size_delta_mm"] for row in selected_rows[side]),
                    "volume_relative": max(row["volume_relative"] for row in selected_rows[side]),
                }
                for side in ("left", "right")
            },
            "native_v5_exact_brep_equivalence": False,
            "exactness_scope": "EXACT_SELECTION_AND_EXPORT_OF_UNMODIFIED_B50_BREP_SOLIDS_ONLY",
        },
        "palm_existing_r1_step": shape_facts(palm),
        "fingers": results,
        "aggregate_pass": all(
            row["source"]["solid_count"] == 24
            and row["source"]["ocp_compound_valid"]
            and row["source"]["all_solids_ocp_valid"]
            and row["bitwise_repeatable_across_distinct_directories_and_seconds"]
            and row["reopen_solid_count_exact"]
            and row["reopen_geometry_digest_exact"]
            and row["mesh_registration"]["fresh_stl_byte_identical_to_frozen_r1"]
            for row in results.values()
        ),
        "prohibited_credit": [
            "NATIVE_V5_SLDPRT_BREP_EQUIVALENCE",
            "M01_OPERATIONAL_NARROWPHASE_PROMOTION",
            "CONTACT_OR_STRENGTH_AUTHORITY",
            "SYSTEM_PAIR_EDGE_PATH_SAFE_OR_RELEASE_CREDIT",
        ],
    }
    output = HERE / "TEMP_B601_GRIPPER_2P_BREP_EXTRACTION_ROUTE_AUDIT_V1.json"
    if output.exists():
        raise RuntimeError(f"temporary receipt already exists; refusing overwrite: {output}")
    output.write_text(json.dumps(receipt_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "aggregate_pass": receipt_out["aggregate_pass"]}, indent=2))


if __name__ == "__main__":
    main()
