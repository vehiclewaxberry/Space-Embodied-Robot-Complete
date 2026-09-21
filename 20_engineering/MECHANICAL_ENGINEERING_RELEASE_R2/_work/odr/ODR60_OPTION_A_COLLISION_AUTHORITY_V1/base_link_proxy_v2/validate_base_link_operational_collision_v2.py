"""Independent fail-closed validator for the base_link collision proxy V2."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import struct
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from OCP.BRepCheck import BRepCheck_Analyzer


SCRIPT_DIR = Path(__file__).resolve().parent
EMITTER_PATH = SCRIPT_DIR / "emit_base_link_operational_collision_v2.py"
VALIDATION_NAME = "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V2.json"


def load_emitter():
    spec = importlib.util.spec_from_file_location("base_link_proxy_v2_emitter", EMITTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load V2 emitter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate() -> dict[str, Any]:
    emitter = load_emitter()
    root = emitter.workspace_root()
    receipt_path = SCRIPT_DIR / emitter.RECEIPT_NAME
    npz_path = SCRIPT_DIR / emitter.NPZ_NAME
    stl_path = SCRIPT_DIR / emitter.STL_NAME
    step_path = SCRIPT_DIR / emitter.STEP_NAME
    for path in (receipt_path, npz_path, stl_path, step_path):
        require(path.is_file(), f"required artifact missing: {path.name}")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt["schema"] == "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2", "receipt schema mismatch")
    require(receipt["review_status"] == "PENDING_OWNER_REVIEW", "receipt review status mismatch")
    require(receipt["next_stage_authorized"] is False, "receipt improperly authorizes next stage")
    require(receipt["path_search_authorized"] is False, "receipt improperly authorizes path search")
    require(receipt["system_pair_evaluation_authorized"] is False, "receipt improperly authorizes pair evaluation")
    require(receipt["release_credit"] is False, "receipt improperly grants release credit")
    require(all(receipt["checks"].values()), "one or more receipt checks are not true")

    for key, path in (("canonical_npz", npz_path), ("binary_stl", stl_path)):
        record = receipt["artifacts"][key]
        require(record["bytes"] == path.stat().st_size, f"{key} byte count mismatch")
        require(record["sha256"] == emitter.sha256_path(path), f"{key} SHA mismatch")
    require(receipt["primary_step"]["bytes"] == step_path.stat().st_size, "STEP byte count mismatch")
    require(receipt["primary_step"]["sha256"] == emitter.sha256_path(step_path), "STEP SHA mismatch")

    with np.load(npz_path, allow_pickle=False) as archive:
        require(set(archive.files) == {"faces", "frame", "solid_ids", "units", "vertices_m"}, "NPZ member set mismatch")
        vertices = np.asarray(archive["vertices_m"])
        faces = np.asarray(archive["faces"])
        solid_ids = np.asarray(archive["solid_ids"])
        frame = str(np.asarray(archive["frame"]).item())
        units = str(np.asarray(archive["units"]).item())
    require(vertices.dtype == np.dtype("<f8"), "vertices dtype mismatch")
    require(faces.dtype == np.dtype("<u4"), "faces dtype mismatch")
    require(solid_ids.dtype == np.dtype("<u2"), "solid_ids dtype mismatch")
    require(vertices.ndim == 2 and vertices.shape[1] == 3, "vertices shape mismatch")
    require(faces.ndim == 2 and faces.shape[1] == 3, "faces shape mismatch")
    require(len(faces) == len(solid_ids), "face/solid-id length mismatch")
    require(frame == "base_link", "NPZ frame mismatch")
    require(units == "meter", "NPZ units mismatch")
    require(int(faces.max()) < len(vertices), "face index out of bounds")
    require(np.array_equal(np.unique(solid_ids), np.arange(68, dtype=np.uint16)), "solid-id set mismatch")

    topology = emitter.manifold_metrics(faces, solid_ids, 68)
    require(topology["per_solid_closed"], "independent per-solid closure failed")
    require(topology["per_solid_consistently_oriented"], "independent orientation audit failed")
    mesh_bbox_mm = np.vstack((vertices.min(axis=0), vertices.max(axis=0))) * 1000.0
    require(
        np.array_equal(mesh_bbox_mm, np.asarray(receipt["mesh"]["bbox_mm"], dtype=np.float64)),
        "receipt/NPZ bbox mismatch",
    )
    mesh_volume_mm3 = sum(
        emitter.signed_volume_m3(vertices, faces[solid_ids == solid_id]) * 1.0e9
        for solid_id in range(68)
    )
    require(
        abs(mesh_volume_mm3 - float(receipt["mesh"]["aggregate_volume_mm3"])) <= 1.0e-7,
        "receipt/NPZ volume mismatch",
    )

    raw_stl = stl_path.read_bytes()
    require(len(raw_stl) >= 84, "STL is truncated")
    require(raw_stl[:80].rstrip(b"\0") == b"B601 BASE_LINK OPERATIONAL COLLISION V2; UNITS=M; FRAME=base_link", "STL header mismatch")
    triangle_count = struct.unpack("<I", raw_stl[80:84])[0]
    require(triangle_count == len(faces), "STL triangle count mismatch")
    require(len(raw_stl) == 84 + 50 * triangle_count, "STL byte layout mismatch")
    require(emitter.sha256_path(stl_path) != emitter.FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256, "STL equals forbidden raw mesh")

    step_shape = emitter.read_step(step_path)
    step_rows = emitter.solid_rows(step_shape)
    require(len(step_rows) == 68, "reopened STEP solid count mismatch")
    require(all(BRepCheck_Analyzer(row["shape"], True).IsValid() for row in step_rows), "reopened STEP BRepCheck failure")

    fresh_build = emitter.build_artifacts()
    replay = emitter.verify_existing(fresh_build)
    require(all(row["same_bytes"] for row in replay.values()), "fresh deterministic replay mismatch")

    checks = {
        "receipt_schema_and_fail_closed_flags": True,
        "receipt_all_geometry_checks_true": True,
        "step_npz_stl_hashes_and_bytes_match": True,
        "npz_schema_dtype_frame_units_valid": True,
        "npz_face_indices_and_68_solid_ids_valid": True,
        "independent_per_solid_edge_incidence_closed": True,
        "independent_orientation_consistent": True,
        "independent_bbox_and_volume_reproduced": True,
        "binary_stl_layout_and_triangle_count_valid": True,
        "raw_urdf_mesh_negative_control_pass": True,
        "reopened_step_68_of_68_brep_valid": True,
        "fresh_process_equivalent_rebuild_byte_identical": True,
    }
    return {
        "schema": "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V2",
        "artifact_role": "INDEPENDENT_VALIDATION_OF_BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "path_search_authorized": False,
        "system_pair_evaluation_authorized": False,
        "release_credit": False,
        "receipt": emitter.file_record(receipt_path, root),
        "primary_step": emitter.file_record(step_path, root),
        "canonical_npz": emitter.file_record(npz_path, root),
        "binary_stl": emitter.file_record(stl_path, root),
        "independent_metrics": {
            "vertex_count": int(len(vertices)),
            "triangle_count": int(len(faces)),
            "solid_id_count": int(len(np.unique(solid_ids))),
            "bbox_mm": mesh_bbox_mm.tolist(),
            "volume_mm3": float(mesh_volume_mm3),
            **topology,
        },
        "fresh_replay": replay,
        "checks": checks,
        "verdict": "BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2_INDEPENDENT_GEOMETRY_VALIDATION_PASS_NO_PAIR_OR_PATH_AUTHORITY",
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.verify_existing and args.replace:
        raise SystemExit("--replace cannot be combined with --verify-existing")
    result = validate()
    encoded = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output = SCRIPT_DIR / VALIDATION_NAME
    if args.verify_existing:
        require(output.is_file(), "existing validation is missing")
        require(output.read_bytes() == encoded, "existing validation differs from fresh run")
    else:
        if output.exists() and not args.replace:
            raise FileExistsError(f"output exists; use --replace: {output.name}")
        temporary = output.with_suffix(output.suffix + ".tmp")
        if temporary.exists():
            temporary.unlink()
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
