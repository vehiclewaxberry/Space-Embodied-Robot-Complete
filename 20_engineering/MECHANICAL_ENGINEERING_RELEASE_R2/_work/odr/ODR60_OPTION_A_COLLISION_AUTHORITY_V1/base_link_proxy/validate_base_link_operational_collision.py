"""Fail-closed validator for the B601 base_link collision proxy."""
from __future__ import annotations

import argparse
import json
import os
import struct
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np

import generate_base_link_operational_collision as generator


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATION_NAME = "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V1.json"
HOLD_NAME = "BASE_LINK_OPERATIONAL_COLLISION_HOLD_DIAGNOSTIC_V1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_npz(path: Path) -> dict[str, np.ndarray]:
    expected_members = [
        "faces.npy",
        "frame.npy",
        "solid_ids.npy",
        "units.npy",
        "vertices_m.npy",
    ]
    with zipfile.ZipFile(path, "r") as archive:
        members = archive.infolist()
        require([item.filename for item in members] == expected_members, "NPZ member order/schema drift")
        for item in members:
            require(item.date_time == (1980, 1, 1, 0, 0, 0), "NPZ timestamp is not canonical")
            require(item.compress_type == zipfile.ZIP_STORED, "NPZ compression drift")
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def read_binary_stl(path: Path) -> tuple[bytes, np.ndarray, np.ndarray]:
    data = path.read_bytes()
    require(len(data) >= 84, "binary STL is truncated")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    require(len(data) == 84 + 50 * triangle_count, "binary STL byte count mismatch")
    dtype = np.dtype(
        [
            ("normal", "<f4", (3,)),
            ("vertices", "<f4", (3, 3)),
            ("attribute", "<u2"),
        ]
    )
    records = np.frombuffer(data, dtype=dtype, count=triangle_count, offset=84)
    require(np.all(records["attribute"] == 0), "nonzero STL attribute words")
    return data[:80], records["normal"].copy(), records["vertices"].copy()


def validate(*, replay: bool) -> dict[str, Any]:
    npz_path = SCRIPT_DIR / generator.NPZ_NAME
    stl_path = SCRIPT_DIR / generator.STL_NAME
    receipt_path = SCRIPT_DIR / generator.RECEIPT_NAME
    for path in (npz_path, stl_path, receipt_path):
        require(path.is_file() and path.stat().st_size > 0, f"missing artifact: {path.name}")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("schema") == "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V1", "receipt schema drift")
    require(all(receipt.get("checks", {}).values()), "one or more receipt checks failed")
    require(receipt.get("next_stage_authorized") is False, "proxy must not authorize next stage")
    require(receipt.get("path_search_authorized") is False, "proxy must not authorize path search")

    npz_bytes = npz_path.read_bytes()
    stl_bytes = stl_path.read_bytes()
    require(
        generator.sha256_bytes(npz_bytes)
        == receipt["artifacts"]["canonical_npz"]["sha256"],
        "NPZ hash mismatch",
    )
    require(
        generator.sha256_bytes(stl_bytes)
        == receipt["artifacts"]["binary_stl"]["sha256"],
        "STL hash mismatch",
    )
    require(
        generator.sha256_bytes(stl_bytes)
        != generator.FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256,
        "STL equals forbidden raw URDF base_link mesh",
    )

    arrays = load_npz(npz_path)
    vertices = arrays["vertices_m"]
    faces = arrays["faces"]
    solid_ids = arrays["solid_ids"]
    require(vertices.dtype == np.dtype("<f8") and vertices.ndim == 2 and vertices.shape[1] == 3, "vertices schema")
    require(faces.dtype == np.dtype("<u4") and faces.ndim == 2 and faces.shape[1] == 3, "faces schema")
    require(solid_ids.dtype == np.dtype("<u2") and solid_ids.shape == (len(faces),), "solid_ids schema")
    require(str(arrays["units"].item()) == "meter", "NPZ unit drift")
    require(str(arrays["frame"].item()) == "base_link", "NPZ frame drift")
    require(np.all(np.isfinite(vertices)), "nonfinite NPZ vertices")
    require(len(vertices) > 0 and len(faces) > 0, "empty NPZ geometry")
    require(int(faces.max()) < len(vertices), "NPZ face index out of range")
    require(np.array_equal(np.unique(solid_ids), np.arange(69, dtype=np.uint16)), "solid id coverage drift")

    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    twice_area = np.linalg.norm(cross, axis=1)
    require(np.all(twice_area > 1.0e-16), "degenerate NPZ triangles")
    keys = np.sort(faces, axis=1)
    order = np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
    require(not np.any(np.all(keys[order][1:] == keys[order][:-1], axis=1)), "duplicate NPZ triangles")
    manifold = generator.edge_manifold_metrics(faces, solid_ids)

    header, stl_normals, stl_triangles = read_binary_stl(stl_path)
    require(header.startswith(b"B601 BASE_LINK OPERATIONAL COLLISION V1"), "STL header drift")
    require(np.array_equal(stl_triangles, triangles.astype("<f4")), "STL/NPZ triangle mismatch")
    expected_normals = cross / twice_area[:, None]
    require(np.array_equal(stl_normals, expected_normals.astype("<f4")), "STL normal mismatch")

    mesh_bbox_mm = np.vstack((vertices.min(axis=0), vertices.max(axis=0))) * 1000.0
    receipt_bbox_mm = np.asarray(receipt["mesh"]["bbox_mm"], dtype=np.float64)
    require(np.array_equal(mesh_bbox_mm, receipt_bbox_mm), "receipt/NPZ bbox mismatch")
    mesh_volume_mm3 = 0.0
    for solid_id in range(69):
        mesh_volume_mm3 += generator.signed_volume_m3(
            vertices, faces[solid_ids == solid_id]
        ) * 1.0e9
    require(mesh_volume_mm3 > 0, "mesh volume is not positive")
    require(
        math_isclose_exact_report(mesh_volume_mm3, float(receipt["mesh"]["aggregate_volume_mm3"])),
        "receipt/NPZ volume mismatch",
    )

    fresh_replay: dict[str, Any] = {"performed": False, "all_artifact_bytes_identical": None}
    if replay:
        rebuilt = generator.build_artifacts()
        comparisons = {
            generator.NPZ_NAME: rebuilt.npz_bytes == npz_bytes,
            generator.STL_NAME: rebuilt.stl_bytes == stl_bytes,
            generator.RECEIPT_NAME: (
                generator.stable_json_bytes(rebuilt.receipt) == receipt_path.read_bytes()
            ),
        }
        require(all(comparisons.values()), f"fresh replay mismatch: {comparisons}")
        fresh_replay = {
            "performed": True,
            "single_process": True,
            "artifact_byte_identity": comparisons,
            "all_artifact_bytes_identical": True,
        }

    checks = {
        "receipt_gate_all_true": True,
        "artifact_hashes_match_receipt": True,
        "canonical_npz_schema_and_zip_metadata": True,
        "npz_finite_nonempty_index_valid": True,
        "npz_has_69_source_solid_ids": True,
        "no_degenerate_or_duplicate_triangles": True,
        "per_source_solid_meshes_closed_and_oriented": bool(
            manifold["closed"] and manifold["consistently_oriented"]
        ),
        "binary_stl_exactly_matches_npz_geometry": True,
        "receipt_bbox_and_volume_reproduced": True,
        "forbidden_raw_urdf_mesh_not_reemitted": True,
        "fresh_process_replay_byte_identity": (
            fresh_replay["all_artifact_bytes_identical"] if replay else None
        ),
    }
    require(all(value is True for value in checks.values() if value is not None), "validator check failed")
    return {
        "schema": "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V1",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "path_search_authorized": False,
        "artifacts": {
            generator.NPZ_NAME: {
                "bytes": len(npz_bytes),
                "sha256": generator.sha256_bytes(npz_bytes),
            },
            generator.STL_NAME: {
                "bytes": len(stl_bytes),
                "sha256": generator.sha256_bytes(stl_bytes),
            },
            generator.RECEIPT_NAME: {
                "bytes": receipt_path.stat().st_size,
                "sha256": generator.sha256_file(receipt_path),
            },
        },
        "geometry": {
            "vertices": int(len(vertices)),
            "triangles": int(len(faces)),
            "source_solid_ids": int(len(np.unique(solid_ids))),
            "bbox_mm": mesh_bbox_mm.tolist(),
            "volume_mm3": mesh_volume_mm3,
            **manifold,
        },
        "fresh_replay": fresh_replay,
        "checks": checks,
        "verdict": (
            "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_PASS_WITH_FRESH_REPLAY_"
            "PENDING_OWNER_REVIEW_NO_PATH_SEARCH_AUTHORITY"
            if replay
            else "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_PASS_NO_REPLAY"
        ),
    }


def validate_hold() -> dict[str, Any]:
    hold_path = SCRIPT_DIR / HOLD_NAME
    require(hold_path.is_file(), "HOLD diagnostic missing")
    hold = json.loads(hold_path.read_text(encoding="utf-8"))
    require(hold.get("schema") == "BASE_LINK_OPERATIONAL_COLLISION_HOLD_DIAGNOSTIC_V1", "HOLD schema drift")
    require(hold.get("next_stage_authorized") is False, "HOLD must not authorize next stage")
    require(hold.get("path_search_authorized") is False, "HOLD must not authorize path search")
    require(hold.get("release_credit") is False, "HOLD must not grant release credit")
    require(hold["missing_surface_area_mm2"] > 0, "HOLD missing area must be positive")
    require(len(hold["missing_faces"]) == 11, "HOLD missing-face count drift")
    require(hold["gate"]["all_nonzero_area_faces_triangulated"] is False, "triangulation HOLD lost")
    require(hold["gate"]["standard_shapefix_produced_promotable_candidate"] is False, "ShapeFix HOLD lost")
    require(hold["gate"]["freecad_occt78_all_positive_area_faces_triangulated"] is False, "FreeCAD HOLD lost")
    require(hold["gate"]["m5_ply_closed_non_degenerate_collision_surface"] is False, "M5 PLY HOLD lost")
    require(hold["outputs"] == {
        "canonical_npz_written": False,
        "binary_stl_written": False,
        "pass_receipt_written": False,
    }, "HOLD output ledger drift")
    for forbidden in (generator.NPZ_NAME, generator.STL_NAME, generator.RECEIPT_NAME):
        require(not (SCRIPT_DIR / forbidden).exists(), f"HOLD directory contains forbidden pass artifact: {forbidden}")
    workspace = generator.find_workspace_root()
    source_step = workspace / hold["source_step"]["path"]
    require(generator.sha256_file(source_step) == hold["source_step"]["sha256"], "HOLD source STEP hash drift")
    m5 = hold["alternative_route_c_m5_base_ply"]
    require(generator.sha256_file(workspace / m5["path"]) == m5["sha256"], "M5 PLY hash drift")
    checks = {
        "hold_schema_and_authorization_fail_closed": True,
        "source_step_hash_matches": True,
        "eleven_nonzero_area_faces_recorded": True,
        "standard_shapefix_negative_result_recorded": True,
        "freecad_occt78_negative_result_recorded": True,
        "m5_ply_negative_topology_result_recorded": True,
        "no_npz_stl_or_pass_receipt_present": True,
    }
    return {
        "schema": "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V1",
        "proxy_pass": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "path_search_authorized": False,
        "hold_diagnostic": {
            "path": HOLD_NAME,
            "bytes": hold_path.stat().st_size,
            "sha256": generator.sha256_file(hold_path),
        },
        "checks": checks,
        "verdict": "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_HOLD_ALL_ALTERNATIVE_ROUTES_FAIL_NO_PROXY_NO_PATH_SEARCH_AUTHORITY",
    }


def math_isclose_exact_report(a: float, b: float) -> bool:
    return abs(a - b) <= max(1.0e-9, 1.0e-12 * max(abs(a), abs(b)))


def atomic_write(path: Path, data: bytes) -> None:
    require(path.parent.resolve() == SCRIPT_DIR, "validation output escapes owned directory")
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-replay",
        action="store_true",
        help="skip the expensive fresh OCP rebuild; not acceptable for final promotion",
    )
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    pass_artifacts = all(
        (SCRIPT_DIR / name).is_file()
        for name in (generator.NPZ_NAME, generator.STL_NAME, generator.RECEIPT_NAME)
    )
    report = validate(replay=not args.no_replay) if pass_artifacts else validate_hold()
    data = generator.stable_json_bytes(report)
    if args.write_report:
        atomic_write(SCRIPT_DIR / VALIDATION_NAME, data)
    print(data.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
