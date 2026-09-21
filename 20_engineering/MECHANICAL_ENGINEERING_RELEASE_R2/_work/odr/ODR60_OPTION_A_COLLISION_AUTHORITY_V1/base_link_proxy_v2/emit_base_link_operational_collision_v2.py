"""Emit deterministic NPZ/STL collision assets from the STEP-first V2 proxy."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import platform
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from OCP import __version__ as OCP_VERSION
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS


SCRIPT_DIR = Path(__file__).resolve().parent
STEP_NAME = "B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2.step"
NPZ_NAME = "BASE_LINK_OPERATIONAL_COLLISION_V2.npz"
STL_NAME = "BASE_LINK_OPERATIONAL_COLLISION_V2.stl"
RECEIPT_NAME = "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2.json"

SOURCE_STEP_REL = Path(
    "20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/"
    "vendor_reference_linklocal/B50_REF_base_link_LINKLOCAL.step"
)
SOURCE_STEP_SHA256 = "A451B9150D00EC8E381AE69C0BB9D62B3A1FED1B1CD1AD373A719E28290F07C5"
SOURCE_STEP_BYTES = 25_111_906
CATALOG_STEP_REL = Path(
    "80_third_party/external/step_parts/damiao_dm_j4340p_2ec/"
    "damiao_dm_j4340p_2ec.step"
)
CATALOG_STEP_SHA256 = "F70211997AB35E20FE9E17376C351A5FBEC83732508B57A18CB64A73D257894E"
CATALOG_STEP_BYTES = 5_174_032
WP11_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml"
)
WP11_SHA256 = "7463C1309C3530A42BB32CB4A661FFA56575691DFB7A4BE801AAE9094BEB51E1"
D_BASE_LINK_MM = np.asarray(
    [-0.05732750272995675, -0.03253727084589079, 0.05006764302725364],
    dtype=np.float64,
)
FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256 = (
    "22641C079014FE968702393F61E7F7F1A8F80C6C1DF45A61E31545F6EAFF3B65"
)
EXPECTED_MOTOR_BOX_FINAL_MM = np.asarray(
    [
        [-28.472365541309, -28.554541686675, 20.904413552661],
        [28.527710535850, 28.445475560459, 77.409686962672],
    ],
    dtype=np.float64,
)
EXPECTED_PLATE_BOX_FINAL_MM = np.asarray(
    [
        [-45.972327602730, -46.054537370844, 75.655067543008],
        [46.027672597270, 45.945462829156, 82.605067743057],
    ],
    dtype=np.float64,
)
EXPECTED_FINAL_TIGHT_BBOX_MM = np.asarray(
    [
        [-45.972327502730, -46.054537270846, 2.455067643028],
        [46.027672497270, 45.945462729154, 82.605067643027],
    ],
    dtype=np.float64,
)

LINEAR_DEFLECTION_MM = 0.05
ANGULAR_DEFLECTION_RAD = 0.15
VERTEX_ROUND_DECIMALS_M = 12
MESH_VOLUME_RELATIVE_TOLERANCE = 1.0e-3
BBOX_TOLERANCE_MM = 2.0e-5


@dataclass(frozen=True)
class ArtifactBuild:
    npz_bytes: bytes
    stl_bytes: bytes
    receipt: dict[str, Any]


def workspace_root() -> Path:
    for candidate in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root containing PROJECT_MAP.md was not found")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def require_file(path: Path, expected_bytes: int | None, expected_sha256: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"required file is missing: {path}")
    if expected_bytes is not None and path.stat().st_size != expected_bytes:
        raise RuntimeError(f"required file byte count drifted: {path}")
    if sha256_path(path) != expected_sha256:
        raise RuntimeError(f"required file SHA-256 drifted: {path}")


def read_step(path: Path):
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed: {path}")
    roots = int(reader.TransferRoots())
    shape = reader.OneShape()
    if roots != 1 or shape.IsNull():
        raise RuntimeError(f"STEP transfer invalid: roots={roots}, null={shape.IsNull()}")
    return shape


def bbox_mm(shape, *, use_shape_tolerance: bool = False) -> np.ndarray:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, use_shape_tolerance)
    return np.asarray(box.Get(), dtype=np.float64).reshape(2, 3)


def volume_mm3(shape) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties, False, False, True)
    return float(properties.Mass())


def solid_rows(shape) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = TopoDS.Solid_s(explorer.Current())
        rows.append(
            {
                "shape": solid,
                "bbox_mm": bbox_mm(solid),
                "volume_mm3": volume_mm3(solid),
                "brep_valid": bool(BRepCheck_Analyzer(solid, True).IsValid()),
            }
        )
        explorer.Next()
    return rows


def transform_node(point, location: TopLoc_Location) -> tuple[float, float, float]:
    transformed = point.Transformed(location.Transformation())
    return transformed.X(), transformed.Y(), transformed.Z()


def extract_triangles_m(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, int]:
    triangles: list[np.ndarray] = []
    triangle_solid_ids: list[int] = []
    missing_face_count = 0
    for solid_id, row in enumerate(rows):
        mesher = BRepMesh_IncrementalMesh(
            row["shape"],
            LINEAR_DEFLECTION_MM,
            False,
            ANGULAR_DEFLECTION_RAD,
            False,
        )
        mesher.Perform()
        if not mesher.IsDone():
            raise RuntimeError(f"meshing did not complete for solid {solid_id}")
        face_explorer = TopExp_Explorer(row["shape"], TopAbs_FACE)
        while face_explorer.More():
            face = TopoDS.Face_s(face_explorer.Current())
            location = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation_s(face, location)
            if triangulation is None or triangulation.NbTriangles() <= 0:
                missing_face_count += 1
                face_explorer.Next()
                continue
            nodes = np.asarray(
                [
                    transform_node(triangulation.Node(index), location)
                    for index in range(1, triangulation.NbNodes() + 1)
                ],
                dtype=np.float64,
            ) * 1.0e-3
            reverse = face.Orientation() == TopAbs_REVERSED
            for index in range(1, triangulation.NbTriangles() + 1):
                node_a, node_b, node_c = triangulation.Triangle(index).Get()
                indices = [node_a - 1, node_b - 1, node_c - 1]
                if reverse:
                    indices[1], indices[2] = indices[2], indices[1]
                triangles.append(nodes[indices])
                triangle_solid_ids.append(solid_id)
            face_explorer.Next()
    if missing_face_count:
        raise RuntimeError(f"{missing_face_count} positive-area faces lack triangulation")
    if not triangles:
        raise RuntimeError("no collision triangles were produced")
    return (
        np.asarray(triangles, dtype=np.float64),
        np.asarray(triangle_solid_ids, dtype=np.uint16),
        missing_face_count,
    )


def signed_volume_m3(vertices: np.ndarray, faces: np.ndarray) -> float:
    triangles = vertices[faces]
    return float(
        np.einsum(
            "ij,ij->i",
            triangles[:, 0],
            np.cross(triangles[:, 1], triangles[:, 2]),
        ).sum()
        / 6.0
    )


def canonicalize(
    triangles_m: np.ndarray, solid_ids: np.ndarray, solid_count: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    flat = np.round(
        triangles_m.reshape(-1, 3), decimals=VERTEX_ROUND_DECIMALS_M
    ).astype("<f8")
    vertices, inverse = np.unique(flat, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(np.int64)
    cross = np.cross(
        vertices[faces[:, 1]] - vertices[faces[:, 0]],
        vertices[faces[:, 2]] - vertices[faces[:, 0]],
    )
    twice_area = np.linalg.norm(cross, axis=1)
    repeated = (
        (faces[:, 0] == faces[:, 1])
        | (faces[:, 1] == faces[:, 2])
        | (faces[:, 2] == faces[:, 0])
    )
    degenerate = repeated | (twice_area <= 1.0e-16)
    removed_degenerate_count = int(np.count_nonzero(degenerate))
    if removed_degenerate_count:
        # OCCT may encode a degenerated analytical edge as a zero-area mesh
        # triangle.  It carries no surface area.  Remove only those triangles,
        # then require the final per-solid exact edge-incidence audit below to
        # remain closed; otherwise the build still fails.
        faces = faces[~degenerate]
        solid_ids = solid_ids[~degenerate]

    flipped: list[int] = []
    duplicate_count = 0
    for solid_id in range(solid_count):
        selection = np.flatnonzero(solid_ids == solid_id)
        if not len(selection):
            raise RuntimeError(f"solid {solid_id} emitted no triangles")
        volume = signed_volume_m3(vertices, faces[selection])
        if not math.isfinite(volume) or abs(volume) <= 1.0e-15:
            raise RuntimeError(f"solid {solid_id} has zero/nonfinite mesh volume")
        if volume < 0:
            faces[selection, 1], faces[selection, 2] = (
                faces[selection, 2].copy(),
                faces[selection, 1].copy(),
            )
            flipped.append(solid_id)
        keys = np.sort(faces[selection], axis=1)
        keys = keys[np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))]
        duplicate_count += int(np.count_nonzero(np.all(keys[1:] == keys[:-1], axis=1)))
    if duplicate_count:
        raise RuntimeError(f"within-solid duplicate triangles are forbidden: {duplicate_count}")

    minimum_position = np.argmin(faces, axis=1)
    rotated = np.empty_like(faces)
    for position in range(3):
        selection = minimum_position == position
        rotated[selection] = faces[selection][
            :, [position, (position + 1) % 3, (position + 2) % 3]
        ]
    faces = rotated
    order = np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0], solid_ids))
    return (
        vertices.astype("<f8"),
        faces[order].astype("<u4"),
        solid_ids[order].astype("<u2"),
        {
            "removed_zero_area_triangle_count": removed_degenerate_count,
            "final_degenerate_triangle_count": 0,
            "within_solid_duplicate_triangle_count": duplicate_count,
            "outward_winding_flipped_solid_ids": flipped,
        },
    )


def manifold_metrics(
    faces: np.ndarray, solid_ids: np.ndarray, solid_count: int
) -> dict[str, Any]:
    boundary = 0
    nonmanifold = 0
    orientation_mismatch = 0
    for solid_id in range(solid_count):
        local = faces[solid_ids == solid_id].astype(np.int64)
        directed = np.concatenate(
            (local[:, [0, 1]], local[:, [1, 2]], local[:, [2, 0]]), axis=0
        )
        undirected = np.sort(directed, axis=1)
        unique_edges, inverse, counts = np.unique(
            undirected, axis=0, return_inverse=True, return_counts=True
        )
        boundary += int(np.count_nonzero(counts == 1))
        nonmanifold += int(np.count_nonzero(counts > 2))
        forward = np.bincount(
            inverse,
            weights=(directed[:, 0] < directed[:, 1]).astype(np.int8),
            minlength=len(unique_edges),
        )
        reverse = counts - forward
        orientation_mismatch += int(np.count_nonzero(forward != reverse))
    if boundary or nonmanifold or orientation_mismatch:
        raise RuntimeError(
            "per-solid shell audit failed: "
            f"boundary={boundary}, nonmanifold={nonmanifold}, "
            f"orientation_mismatch={orientation_mismatch}"
        )
    return {
        "boundary_edge_count": boundary,
        "nonmanifold_edge_count": nonmanifold,
        "orientation_mismatch_edge_count": orientation_mismatch,
        "per_solid_closed": True,
        "per_solid_consistently_oriented": True,
    }


def npy_bytes(array: np.ndarray) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(stream, array, allow_pickle=False)
    return stream.getvalue()


def canonical_npz_bytes(arrays: dict[str, np.ndarray]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(arrays):
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o600 << 16
            info.create_system = 3
            archive.writestr(info, npy_bytes(arrays[name]))
    return stream.getvalue()


def binary_stl_bytes(vertices: np.ndarray, faces: np.ndarray) -> bytes:
    header = b"B601 BASE_LINK OPERATIONAL COLLISION V2; UNITS=M; FRAME=base_link"
    output = io.BytesIO()
    output.write(header[:80].ljust(80, b"\0"))
    output.write(struct.pack("<I", int(len(faces))))
    triangles = vertices[faces].astype(np.float64)
    normals = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    for normal, triangle in zip(
        normals.astype("<f4"), triangles.astype("<f4"), strict=True
    ):
        output.write(
            struct.pack(
                "<12fH", *(normal.tolist() + triangle.reshape(-1).tolist()), 0
            )
        )
    return output.getvalue()


def stable_json_bytes(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def artifact_record(name: str, data: bytes) -> dict[str, Any]:
    return {"path": name, "bytes": len(data), "sha256": sha256_bytes(data)}


def _find_box(rows: list[dict[str, Any]], expected_bbox: np.ndarray, label: str) -> int:
    errors = [float(np.max(np.abs(row["bbox_mm"] - expected_bbox))) for row in rows]
    index = int(np.argmin(errors))
    if errors[index] > BBOX_TOLERANCE_MM:
        raise RuntimeError(f"{label} replacement box was not found; best error={errors[index]}")
    return index


def build_artifacts() -> ArtifactBuild:
    root = workspace_root()
    source_path = root / SOURCE_STEP_REL
    catalog_path = root / CATALOG_STEP_REL
    wp11_path = root / WP11_REL
    step_path = SCRIPT_DIR / STEP_NAME
    require_file(source_path, SOURCE_STEP_BYTES, SOURCE_STEP_SHA256)
    require_file(catalog_path, CATALOG_STEP_BYTES, CATALOG_STEP_SHA256)
    require_file(wp11_path, None, WP11_SHA256)
    if not step_path.is_file():
        raise RuntimeError("primary V2 STEP has not been generated")

    shape = read_step(step_path)
    rows = solid_rows(shape)
    if len(rows) != 68:
        raise RuntimeError(f"expected 68 proxy solids, found {len(rows)}")
    if not all(row["brep_valid"] for row in rows):
        raise RuntimeError("one or more proxy solids fail BRepCheck")
    if not all(math.isfinite(row["volume_mm3"]) and row["volume_mm3"] > 0 for row in rows):
        raise RuntimeError("one or more proxy solids have invalid volume")

    motor_box_id = _find_box(rows, EXPECTED_MOTOR_BOX_FINAL_MM, "motor")
    plate_box_id = _find_box(rows, EXPECTED_PLATE_BOX_FINAL_MM, "plate")
    if motor_box_id == plate_box_id:
        raise RuntimeError("motor and plate replacement boxes resolved to one solid")

    final_bbox = bbox_mm(shape)
    bbox_error = float(np.max(np.abs(final_bbox - EXPECTED_FINAL_TIGHT_BBOX_MM)))
    if bbox_error > BBOX_TOLERANCE_MM:
        raise RuntimeError(f"final tight bbox contract failed: {bbox_error} mm")

    triangles_m, raw_solid_ids, missing_face_count = extract_triangles_m(rows)
    vertices_m, faces, solid_ids, canonical = canonicalize(
        triangles_m, raw_solid_ids, len(rows)
    )
    topology = manifold_metrics(faces, solid_ids, len(rows))

    brep_volume = float(sum(row["volume_mm3"] for row in rows))
    mesh_volume_by_solid = [
        signed_volume_m3(vertices_m, faces[solid_ids == solid_id]) * 1.0e9
        for solid_id in range(len(rows))
    ]
    mesh_volume = float(sum(mesh_volume_by_solid))
    aggregate_volume_error = abs(mesh_volume - brep_volume) / brep_volume
    per_solid_volume_errors = [
        abs(mesh_volume_by_solid[index] - rows[index]["volume_mm3"])
        / rows[index]["volume_mm3"]
        for index in range(len(rows))
    ]
    if aggregate_volume_error > MESH_VOLUME_RELATIVE_TOLERANCE:
        raise RuntimeError(f"mesh/BRep volume error too large: {aggregate_volume_error}")

    mesh_bbox = np.vstack((vertices_m.min(axis=0), vertices_m.max(axis=0))) * 1000.0
    mesh_bbox_error = float(np.max(np.abs(mesh_bbox - final_bbox)))
    if mesh_bbox_error > 0.10:
        raise RuntimeError(f"mesh/STEP bbox error too large: {mesh_bbox_error} mm")

    source_shape = read_step(source_path)
    source_rows = solid_rows(source_shape)
    if len(source_rows) != 69:
        raise RuntimeError("pinned B50 source no longer has 69 solids")
    source_total_volume = float(sum(row["volume_mm3"] for row in source_rows))
    substituted_source_volume_sum = float(
        sum(source_rows[index]["volume_mm3"] for index in (58, 59, 68))
    )
    replacement_volume = float(
        rows[motor_box_id]["volume_mm3"] + rows[plate_box_id]["volume_mm3"]
    )
    expected_proxy_volume = source_total_volume - substituted_source_volume_sum + replacement_volume
    proxy_volume_recomposition_error = abs(brep_volume - expected_proxy_volume)
    if proxy_volume_recomposition_error > 0.05:
        raise RuntimeError(
            f"proxy volume does not recompose from source and replacements: "
            f"{proxy_volume_recomposition_error} mm^3"
        )

    source_motor_bounds = np.vstack(
        (
            np.minimum(source_rows[58]["bbox_mm"][0], source_rows[59]["bbox_mm"][0]),
            np.maximum(source_rows[58]["bbox_mm"][1], source_rows[59]["bbox_mm"][1]),
        )
    ) + D_BASE_LINK_MM
    source_plate_bounds = source_rows[68]["bbox_mm"] + D_BASE_LINK_MM
    motor_contains = bool(
        np.all(rows[motor_box_id]["bbox_mm"][0] <= source_motor_bounds[0])
        and np.all(rows[motor_box_id]["bbox_mm"][1] >= source_motor_bounds[1])
    )
    plate_contains = bool(
        np.all(rows[plate_box_id]["bbox_mm"][0] <= source_plate_bounds[0])
        and np.all(rows[plate_box_id]["bbox_mm"][1] >= source_plate_bounds[1])
    )
    if not motor_contains or not plate_contains:
        raise RuntimeError("replacement AABB does not contain source exact bbox")

    arrays = {
        "faces": faces,
        "frame": np.asarray("base_link"),
        "solid_ids": solid_ids,
        "units": np.asarray("meter"),
        "vertices_m": vertices_m,
    }
    npz_data = canonical_npz_bytes(arrays)
    stl_data = binary_stl_bytes(vertices_m, faces)
    if sha256_bytes(stl_data) == FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256:
        raise RuntimeError("derived STL equals forbidden raw accepted-URDF base mesh")

    source_substitution_inflation = (
        replacement_volume / substituted_source_volume_sum - 1.0
    )
    aggregate_proxy_inflation = brep_volume / source_total_volume - 1.0
    checks = {
        "source_catalog_wp11_hashes_match": True,
        "primary_step_present": True,
        "proxy_solid_count_68": len(rows) == 68,
        "all_proxy_solids_brep_valid": all(row["brep_valid"] for row in rows),
        "all_nonzero_area_faces_triangulated": missing_face_count == 0,
        "motor_tolerance_aabb_contains_source": motor_contains,
        "plate_tolerance_aabb_contains_source": plate_contains,
        "per_solid_mesh_closed": topology["per_solid_closed"],
        "per_solid_mesh_orientation_consistent": topology[
            "per_solid_consistently_oriented"
        ],
        "no_degenerate_triangles_in_final_mesh": canonical[
            "final_degenerate_triangle_count"
        ]
        == 0,
        "zero_area_source_mesh_artifacts_removed_then_closed": canonical[
            "removed_zero_area_triangle_count"
        ]
        >= 0,
        "no_within_solid_duplicate_triangles": canonical[
            "within_solid_duplicate_triangle_count"
        ]
        == 0,
        "aggregate_mesh_brep_volume_error_le_0p1_percent": aggregate_volume_error
        <= MESH_VOLUME_RELATIVE_TOLERANCE,
        "final_bbox_contract_pass": bbox_error <= BBOX_TOLERANCE_MM,
        "mesh_bbox_within_0p10mm_of_step": mesh_bbox_error <= 0.10,
        "raw_urdf_mesh_hash_not_used": True,
    }
    if not all(checks.values()):
        raise RuntimeError(f"fail-closed V2 checks failed: {checks}")

    receipt: dict[str, Any] = {
        "schema": "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2",
        "artifact_role": "B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY",
        "authority_class": "STEP_FIRST_66_EXACT_BREP_PLUS_2_TOLERANCE_AABB_SUBSTITUTIONS",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "path_search_authorized": False,
        "system_pair_evaluation_authorized": False,
        "release_credit": False,
        "primary_step": file_record(step_path, root),
        "source_pins": {
            "filtered_b50": file_record(source_path, root),
            "wp11_frame_authority": file_record(wp11_path, root),
            "step_parts_dm_j4340p_2ec_candidate": file_record(catalog_path, root),
        },
        "frame_contract": {
            "frame": "base_link",
            "handedness": "RIGHT_HANDED",
            "step_unit": "millimeter",
            "collision_unit": "meter",
            "D_base_link_translation_mm": D_BASE_LINK_MM.tolist(),
            "D_base_link_rotation": "IDENTITY",
            "spacecraft_mount_transform_baked": False,
            "mission_pose_baked": False,
        },
        "source_disposition": {
            "retained_exact_traversal_solid_count": 66,
            "replaced_zero_based_traversal_indices": [58, 59, 68],
            "replacement_count": 2,
            "motor_58_59_combined_by_one_tolerance_aabb": True,
            "base_plate_68_replaced_by_tolerance_aabb": True,
            "catalog_candidate_promoted_to_operational_proxy": False,
            "catalog_candidate_nonpromotion_reasons": [
                "LOCAL_VARIANT_2EC_SUFFIX_NOT_INDEPENDENTLY_BOUND",
                "CATALOG_MODEL_17_OF_18_BREPCHECK_VALID",
                "CATALOG_TO_LOCAL_VOLUME_DELTA_PLUS_0P15089_PERCENT",
                "FULL_SURFACE_EQUIVALENCE_NOT_PROVED",
            ],
        },
        "catalog_candidate_audit": {
            "solid_count": 18,
            "face_count": 3038,
            "brepcheck_valid_solid_count": 17,
            "all_positive_area_faces_triangulated": True,
            "rigid_transform_candidate_to_b50": {
                "R": [[0, 0, -1], [1, 0, 0], [0, -1, 0]],
                "t_mm": [0.085, -0.022, 77.355],
                "det_R": 1,
            },
            "mapped_bbox_y_deficit_mm": 0.017346,
            "volume_delta_relative_percent": 0.15089,
            "use_limit": "HIGH_CONFIDENCE_GEOMETRY_CANDIDATE_NOT_EXACT_OR_CONTACT_AUTHORITY",
        },
        "brep": {
            "solid_count": len(rows),
            "brepcheck_valid_solid_count": sum(row["brep_valid"] for row in rows),
            "tight_bbox_mm": final_bbox.tolist(),
            "tight_bbox_contract_max_abs_error_mm": bbox_error,
            "aggregate_volume_mm3": brep_volume,
            "source_aggregate_volume_mm3": source_total_volume,
            "substituted_source_volume_sum_mm3": substituted_source_volume_sum,
            "replacement_volume_sum_mm3": replacement_volume,
            "substituted_region_volume_inflation_relative": source_substitution_inflation,
            "aggregate_proxy_volume_inflation_relative": aggregate_proxy_inflation,
            "proxy_volume_recomposition_error_mm3": proxy_volume_recomposition_error,
            "motor_replacement_solid_id": motor_box_id,
            "plate_replacement_solid_id": plate_box_id,
            "motor_replacement_bbox_mm": rows[motor_box_id]["bbox_mm"].tolist(),
            "plate_replacement_bbox_mm": rows[plate_box_id]["bbox_mm"].tolist(),
        },
        "mesh": {
            "engine": "OpenCascade_BRepMesh_IncrementalMesh_plus_canonical_encoder",
            "parallel": False,
            "linear_deflection_mm": LINEAR_DEFLECTION_MM,
            "angular_deflection_rad": ANGULAR_DEFLECTION_RAD,
            "vertex_round_decimals_m": VERTEX_ROUND_DECIMALS_M,
            "vertex_count": int(len(vertices_m)),
            "triangle_count": int(len(faces)),
            "solid_id_count": int(len(np.unique(solid_ids))),
            "bbox_mm": mesh_bbox.tolist(),
            "bbox_to_step_max_abs_error_mm": mesh_bbox_error,
            "aggregate_volume_mm3": mesh_volume,
            "aggregate_volume_relative_error": aggregate_volume_error,
            "per_solid_volume_relative_error_max": float(max(per_solid_volume_errors)),
            **canonical,
            **topology,
        },
        "forbidden_input": {
            "asset": "accepted URDF raw base_link.STL with phantom desktop plate",
            "sha256": FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256,
            "opened_by_emitter": False,
            "permitted_use": "HASH_INEQUALITY_SENTINEL_ONLY",
        },
        "checks": checks,
        "artifacts": {
            "canonical_npz": artifact_record(NPZ_NAME, npz_data),
            "binary_stl": artifact_record(STL_NAME, stl_data),
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "ocp": OCP_VERSION,
            "platform": sys.platform,
        },
        "verdict": "BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2_GEOMETRY_PASS_PENDING_OWNER_REVIEW_NO_PAIR_OR_PATH_AUTHORITY",
    }
    return ArtifactBuild(npz_data, stl_data, receipt)


def atomic_write(path: Path, data: bytes, *, replace: bool) -> None:
    if path.parent.resolve() != SCRIPT_DIR:
        raise RuntimeError(f"output escapes owned directory: {path}")
    if path.exists() and not replace:
        raise FileExistsError(f"output exists; use --replace: {path.name}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def verify_existing(build: ArtifactBuild) -> dict[str, Any]:
    expected = {
        NPZ_NAME: build.npz_bytes,
        STL_NAME: build.stl_bytes,
        RECEIPT_NAME: stable_json_bytes(build.receipt),
    }
    result: dict[str, Any] = {}
    for name, fresh in expected.items():
        path = SCRIPT_DIR / name
        if not path.is_file():
            raise RuntimeError(f"existing artifact is missing: {name}")
        existing = path.read_bytes()
        same = existing == fresh
        result[name] = {
            "same_bytes": same,
            "existing_sha256": sha256_bytes(existing),
            "fresh_sha256": sha256_bytes(fresh),
        }
        if not same:
            raise RuntimeError(f"fresh deterministic replay differs: {name}")
    return result


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.verify_existing and args.replace:
        raise SystemExit("--replace cannot be used with --verify-existing")
    build = build_artifacts()
    if args.verify_existing:
        print(json.dumps(verify_existing(build), indent=2, sort_keys=True))
        return 0
    atomic_write(SCRIPT_DIR / NPZ_NAME, build.npz_bytes, replace=args.replace)
    atomic_write(SCRIPT_DIR / STL_NAME, build.stl_bytes, replace=args.replace)
    atomic_write(
        SCRIPT_DIR / RECEIPT_NAME,
        stable_json_bytes(build.receipt),
        replace=args.replace,
    )
    print(json.dumps(build.receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
