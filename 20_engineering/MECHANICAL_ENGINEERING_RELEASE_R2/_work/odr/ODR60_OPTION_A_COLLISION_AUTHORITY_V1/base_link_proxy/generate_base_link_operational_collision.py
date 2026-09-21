"""Emit the deterministic B601 base_link operational collision proxy.

The accepted URDF remains the kinematic, mass, inertia, and joint authority.
This generator consumes only the WP11-approved filtered B50 STEP BRep for
physical geometry, then applies the body-fixed WP11 ``D_base_link``
translation into the accepted URDF ``base_link`` frame.

The raw accepted-URDF ``base_link.STL`` is deliberately not opened.  Its
known SHA-256 is retained only as a forbidden-input/output-inequality sentinel.
"""
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
import yaml
from OCP import __version__ as OCP_VERSION
from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS


SCRIPT_DIR = Path(__file__).resolve().parent
NPZ_NAME = "BASE_LINK_OPERATIONAL_COLLISION_V1.npz"
STL_NAME = "BASE_LINK_OPERATIONAL_COLLISION_V1.stl"
RECEIPT_NAME = "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V1.json"

LINEAR_DEFLECTION_MM = 0.05
ANGULAR_DEFLECTION_RAD = 0.15
VERTEX_ROUND_DECIMALS_M = 12
BBOX_CONTRACT_TOLERANCE_MM = 0.001
MESH_BBOX_TO_TIGHT_BREP_TOLERANCE_MM = 0.10
AGGREGATE_VOLUME_RELATIVE_TOLERANCE = 0.001

D_BASE_LINK_MM = np.array(
    [-0.05732750272995675, -0.03253727084589079, 0.05006764302725364],
    dtype=np.float64,
)
EXPECTED_CONSERVATIVE_BREP_BBOX_MM = np.array(
    [
        [-45.97565753859685, -46.05786730671302, 2.4517376071601486],
        [46.03100253313692, 45.94879276502116, 82.60839767892430],
    ],
    dtype=np.float64,
)

# G06 -> B50 fixed link-local placement, used only to move the classified
# deleted plate witness into final base_link coordinates.  Do not bake the
# spacecraft 208 mm / 25 degree mount or T_SM into this link-local proxy.
G06_TO_B50_ROTATION = np.diag([-1.0, -1.0, 1.0])
G06_TO_B50_TRANSLATION_MM = np.array([0.085, -0.022, -3.395], dtype=np.float64)

FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256 = (
    "22641C079014FE968702393F61E7F7F1A8F80C6C1DF45A61E31545F6EAFF3B65"
)

SOURCE_PINS: dict[str, dict[str, str | int]] = {
    "b50_filtered_linklocal_step": {
        "path": "20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/"
        "vendor_reference_linklocal/B50_REF_base_link_LINKLOCAL.step",
        "sha256": "A451B9150D00EC8E381AE69C0BB9D62B3A1FED1B1CD1AD373A719E28290F07C5",
        "bytes": 25111906,
    },
    "g06_filtered_lineage_step": {
        "path": "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/"
        "130_B601_Vendor_CAD_Direct_Integration_03/vendor_groups/G06_Base_FILTERED.step",
        "sha256": "C3B64B42078200BD983442E2380BEC6B7DFECF0F6B6E613E849D52D18A14C055",
        "bytes": 23726169,
    },
    "wp11_calibration": {
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml",
        "sha256": "7463C1309C3530A42BB32CB4A661FFA56575691DFB7A4BE801AAE9094BEB51E1",
        "bytes": 36293,
    },
    "wp11_o2_ruling": {
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp11_cad_urdf_registration/O2_DISPOSITION_RULING_V1.yaml",
        "sha256": "AD7AAD0E84789CE523710DF4E9F6E516A082AF24BA4CD1ABD7806930A3B1F315",
        "bytes": 9563,
    },
    "wp11_registration_analysis": {
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp11_cad_urdf_registration/CAD_URDF_REGISTRATION_ANALYSIS_V1.json",
        "sha256": "8D8B433D5D855321AFCD2876C944F7E40B929789CE50B151C5F257790B5021B9",
        "bytes": 173105,
    },
    "base_plate_classification": {
        "path": "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/"
        "130_B601_Vendor_CAD_Direct_Integration_03/design/base_classification.json",
        "sha256": "FE669FE95514B923398D582BF1FC2B215DB20F203A5882F459E3598751FD96E0",
        "bytes": 1036,
    },
}


@dataclass(frozen=True)
class ArtifactBuild:
    npz_bytes: bytes
    stl_bytes: bytes
    receipt: dict[str, Any]


def find_workspace_root() -> Path:
    for candidate in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (
            candidate / "20_engineering"
        ).is_dir():
            return candidate
    raise RuntimeError("workspace root with PROJECT_MAP.md was not found")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_source_pins(workspace: Path) -> dict[str, dict[str, Any]]:
    actual: dict[str, dict[str, Any]] = {}
    for name, pin in SOURCE_PINS.items():
        path = (workspace / str(pin["path"])).resolve()
        if not path.is_file():
            raise RuntimeError(f"pinned source missing: {name}: {path}")
        file_hash = sha256_file(path)
        file_bytes = path.stat().st_size
        if file_hash != pin["sha256"] or file_bytes != pin["bytes"]:
            raise RuntimeError(
                f"pinned source drift: {name}: sha={file_hash}, bytes={file_bytes}"
            )
        actual[name] = {
            "path": str(pin["path"]),
            "sha256": file_hash,
            "bytes": file_bytes,
            "role": (
                "SOLE_BREP_GEOMETRY_INPUT"
                if name == "b50_filtered_linklocal_step"
                else "READ_ONLY_LINEAGE_OR_FRAME_AUTHORITY"
            ),
        }
    return actual


def require_wp11_translation(workspace: Path) -> None:
    calibration_path = workspace / str(SOURCE_PINS["wp11_calibration"]["path"])
    calibration = yaml.safe_load(calibration_path.read_text(encoding="utf-8"))
    observed = np.asarray(
        calibration["links"]["base_link"]["D_i_translation_mm"],
        dtype=np.float64,
    )
    if observed.shape != (3,) or not np.array_equal(observed, D_BASE_LINK_MM):
        raise RuntimeError(
            f"WP11 D_base_link drift: {observed.tolist()} != {D_BASE_LINK_MM.tolist()}"
        )
    if calibration["links"]["base_link"].get("D_i_rotation") != "IDENTITY":
        raise RuntimeError("WP11 base_link rotation is no longer IDENTITY")


def require_plate_classification(workspace: Path) -> np.ndarray:
    path = workspace / str(SOURCE_PINS["base_plate_classification"]["path"])
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("n_solids_kept") != 69:
        raise RuntimeError("base classification no longer keeps exactly 69 solids")
    deleted = data.get("deleted", {}).get("01_BASE_Plate", {})
    if deleted.get("solids_dropped") != 1 or len(deleted.get("bboxes", [])) != 1:
        raise RuntimeError("desktop plate classification is not the frozen one-solid deletion")
    flat = np.asarray(deleted["bboxes"][0], dtype=np.float64)
    if flat.shape != (6,):
        raise RuntimeError("deleted desktop plate bbox is malformed")
    return flat.reshape(2, 3)


def bbox(shape: Any, *, conservative: bool) -> np.ndarray:
    box = Bnd_Box()
    if conservative:
        # Add_s retains the native shape tolerance/gap.  This is the frozen
        # conservative contract used by ODR60 and therefore intentionally not
        # replaced by the visually tighter tessellation bbox.
        BRepBndLib.Add_s(shape, box, False)
    else:
        BRepBndLib.AddOptimal_s(shape, box, False, False)
    values = np.asarray(box.Get(), dtype=np.float64)
    return values.reshape(2, 3)


def volume_and_center(solid: Any) -> tuple[float, np.ndarray]:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, props, False, False, True)
    center = props.CentreOfMass()
    return float(props.Mass()), np.array([center.X(), center.Y(), center.Z()])


def sorted_solids(shape: Any) -> list[dict[str, Any]]:
    solids: list[dict[str, Any]] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    traversal_index = 0
    while explorer.More():
        solid = TopoDS.Solid_s(explorer.Current())
        solid_bbox = bbox(solid, conservative=False)
        solid_volume, center = volume_and_center(solid)
        valid = bool(BRepCheck_Analyzer(solid).IsValid())
        # STEPControl does not propagate TopoDS.Closed() for this assembly: the
        # flag is false on all 69 imported solids.  It is metadata, not a
        # sufficient topology test.  The emitted mesh is instead required to
        # pass an exact per-source-solid edge-incidence/orientation audit.
        closed_flag = bool(solid.Closed())
        key = tuple(
            np.round(
                np.concatenate((solid_bbox.reshape(-1), [solid_volume], center)), 9
            ).tolist()
        )
        solids.append(
            {
                "shape": solid,
                "bbox_mm": solid_bbox,
                "volume_mm3": solid_volume,
                "center_mm": center,
                "valid": valid,
                "topods_closed_flag": closed_flag,
                "sort_key": key,
                "traversal_index": traversal_index,
            }
        )
        traversal_index += 1
        explorer.Next()
    solids.sort(key=lambda item: (item["sort_key"], item["traversal_index"]))
    if len(solids) != 69:
        raise RuntimeError(f"expected 69 source solids, got {len(solids)}")
    if not all(math.isfinite(item["volume_mm3"]) and item["volume_mm3"] > 0 for item in solids):
        raise RuntimeError("one or more source solids have nonpositive/nonfinite volume")
    # Pinned B50 has 67/69 BRepCheck-valid solids.  The two known imported
    # solids contain five BRepCheck_UnorientableShape face reports.  Preserve
    # that negative fact; do not relabel it as a clean BRep.  Source hashes pin
    # it, and the derived collision mesh must independently close all 69 shells.
    valid_count = sum(bool(item["valid"]) for item in solids)
    if valid_count != 67:
        raise RuntimeError(f"pinned BRepCheck profile drift: expected 67/69, got {valid_count}/69")
    return solids


def transform_point(point: Any, location: TopLoc_Location) -> tuple[float, float, float]:
    transformed = point.Transformed(location.Transformation())
    return transformed.X(), transformed.Y(), transformed.Z()


def extract_triangles_m(
    shape: Any, solids: list[dict[str, Any]]
) -> tuple[np.ndarray, np.ndarray]:
    mesher = BRepMesh_IncrementalMesh(
        shape,
        LINEAR_DEFLECTION_MM,
        False,
        ANGULAR_DEFLECTION_RAD,
        False,  # fail-safe low-memory policy: do not enable parallel meshing
    )
    mesher.Perform()
    if not mesher.IsDone():
        raise RuntimeError("OpenCascade triangulation did not finish")

    triangles: list[np.ndarray] = []
    triangle_solid_ids: list[int] = []
    for solid_id, solid_entry in enumerate(solids):
        face_explorer = TopExp_Explorer(solid_entry["shape"], TopAbs_FACE)
        while face_explorer.More():
            face = TopoDS.Face_s(face_explorer.Current())
            location = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation_s(face, location)
            if triangulation is None or triangulation.NbTriangles() <= 0:
                raise RuntimeError(f"source face has no triangulation: solid {solid_id}")
            nodes = np.asarray(
                [
                    transform_point(triangulation.Node(index), location)
                    for index in range(1, triangulation.NbNodes() + 1)
                ],
                dtype=np.float64,
            )
            nodes = (nodes + D_BASE_LINK_MM) * 1.0e-3
            reverse = face.Orientation() == TopAbs_REVERSED
            for index in range(1, triangulation.NbTriangles() + 1):
                node_a, node_b, node_c = triangulation.Triangle(index).Get()
                indices = [node_a - 1, node_b - 1, node_c - 1]
                if reverse:
                    indices[1], indices[2] = indices[2], indices[1]
                triangles.append(nodes[indices])
                triangle_solid_ids.append(solid_id)
            face_explorer.Next()
    if not triangles:
        raise RuntimeError("OpenCascade produced no triangles")
    return np.asarray(triangles), np.asarray(triangle_solid_ids, dtype=np.uint16)


def signed_volume_m3(vertices: np.ndarray, faces: np.ndarray) -> float:
    tri = vertices[faces]
    return float(
        np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()
        / 6.0
    )


def canonicalize(
    triangles_m: np.ndarray, solid_ids: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    flat = np.round(
        triangles_m.reshape(-1, 3), decimals=VERTEX_ROUND_DECIMALS_M
    ).astype("<f8")
    vertices, inverse = np.unique(flat, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(np.int64)

    repeated_vertex = np.any(
        (faces[:, 0] == faces[:, 1])
        | (faces[:, 1] == faces[:, 2])
        | (faces[:, 2] == faces[:, 0])
    )
    cross = np.cross(
        vertices[faces[:, 1]] - vertices[faces[:, 0]],
        vertices[faces[:, 2]] - vertices[faces[:, 0]],
    )
    twice_area_m2 = np.linalg.norm(cross, axis=1)
    degenerate_count = int(np.count_nonzero(twice_area_m2 <= 1.0e-16))
    if repeated_vertex or degenerate_count:
        raise RuntimeError(
            f"degenerate triangles are forbidden: {degenerate_count}, repeated={repeated_vertex}"
        )

    # Ensure each source-solid shell is outward-oriented before canonical face
    # rotation/sorting.  This changes winding only, never geometry.
    flipped_solid_ids: list[int] = []
    for solid_id in range(69):
        selection = np.flatnonzero(solid_ids == solid_id)
        if selection.size == 0:
            raise RuntimeError(f"source solid {solid_id} emitted no triangles")
        volume = signed_volume_m3(vertices, faces[selection])
        if not math.isfinite(volume) or abs(volume) <= 1.0e-15:
            raise RuntimeError(f"source solid {solid_id} has zero/nonfinite mesh volume")
        if volume < 0:
            faces[selection, 1], faces[selection, 2] = (
                faces[selection, 2].copy(),
                faces[selection, 1].copy(),
            )
            flipped_solid_ids.append(solid_id)

    # Cyclic rotation preserves winding while selecting one representation.
    minimum_position = np.argmin(faces, axis=1)
    rotated = np.empty_like(faces)
    for position in range(3):
        selection = minimum_position == position
        rotated[selection] = faces[selection][:, [position, (position + 1) % 3, (position + 2) % 3]]
    faces = rotated

    unoriented_keys = np.sort(faces, axis=1)
    duplicate_order = np.lexsort(
        (unoriented_keys[:, 2], unoriented_keys[:, 1], unoriented_keys[:, 0])
    )
    sorted_keys = unoriented_keys[duplicate_order]
    duplicate_mask = np.all(sorted_keys[1:] == sorted_keys[:-1], axis=1)
    duplicate_count = int(np.count_nonzero(duplicate_mask))
    if duplicate_count:
        raise RuntimeError(f"duplicate triangles are forbidden: {duplicate_count}")

    order = np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0], solid_ids))
    faces = faces[order].astype("<u4")
    solid_ids = solid_ids[order].astype("<u2")
    vertices = vertices.astype("<f8")
    return vertices, faces, solid_ids, {
        "degenerate_triangle_count": degenerate_count,
        "duplicate_triangle_count": duplicate_count,
        "outward_winding_flipped_source_solid_ids": flipped_solid_ids,
    }


def edge_manifold_metrics(
    faces: np.ndarray, solid_ids: np.ndarray
) -> dict[str, Any]:
    boundary_total = 0
    nonmanifold_total = 0
    orientation_mismatch_total = 0
    for solid_id in range(69):
        local = faces[solid_ids == solid_id].astype(np.int64)
        directed = np.concatenate(
            (local[:, [0, 1]], local[:, [1, 2]], local[:, [2, 0]]), axis=0
        )
        undirected = np.sort(directed, axis=1)
        unique_edges, inverse, counts = np.unique(
            undirected, axis=0, return_inverse=True, return_counts=True
        )
        boundary_total += int(np.count_nonzero(counts == 1))
        nonmanifold_total += int(np.count_nonzero(counts > 2))
        direction = directed[:, 0] < directed[:, 1]
        forward = np.bincount(inverse, weights=direction.astype(np.int8), minlength=len(unique_edges))
        reverse = counts - forward
        orientation_mismatch_total += int(np.count_nonzero(forward != reverse))
    if boundary_total or nonmanifold_total or orientation_mismatch_total:
        raise RuntimeError(
            "mesh shell failure: "
            f"boundary={boundary_total}, nonmanifold={nonmanifold_total}, "
            f"orientation_mismatch={orientation_mismatch_total}"
        )
    return {
        "boundary_edge_count": boundary_total,
        "nonmanifold_edge_count": nonmanifold_total,
        "orientation_mismatch_edge_count": orientation_mismatch_total,
        "closed": True,
        "consistently_oriented": True,
    }


def deleted_plate_final_bbox_mm(deleted_bbox_g06_mm: np.ndarray) -> np.ndarray:
    corners = np.asarray(
        [
            [x, y, z]
            for x in deleted_bbox_g06_mm[:, 0]
            for y in deleted_bbox_g06_mm[:, 1]
            for z in deleted_bbox_g06_mm[:, 2]
        ],
        dtype=np.float64,
    )
    final_translation = G06_TO_B50_TRANSLATION_MM + D_BASE_LINK_MM
    transformed = corners @ G06_TO_B50_ROTATION.T + final_translation
    return np.vstack((transformed.min(axis=0), transformed.max(axis=0)))


def plate_exclusive_metrics(
    vertices_m: np.ndarray,
    faces: np.ndarray,
    deleted_plate_bbox_mm: np.ndarray,
    clean_bbox_mm: np.ndarray,
) -> dict[str, Any]:
    triangles_mm = vertices_m[faces].astype(np.float64) * 1000.0
    tri_min = triangles_mm.min(axis=1)
    tri_max = triangles_mm.max(axis=1)
    # A 0.5 mm guard outside the clean BRep envelope defines four regions that
    # could only belong to the removed 140 x 200 mm desktop plate, not the
    # retained <=92 x 92 mm base hardware.
    guard_mm = 0.5
    pmin, pmax = deleted_plate_bbox_mm
    cmin, cmax = clean_bbox_mm
    slabs = {
        "x_minus": np.array([[pmin[0], pmin[1], pmin[2]], [cmin[0] - guard_mm, pmax[1], pmax[2]]]),
        "x_plus": np.array([[cmax[0] + guard_mm, pmin[1], pmin[2]], [pmax[0], pmax[1], pmax[2]]]),
        "y_minus": np.array([[pmin[0], pmin[1], pmin[2]], [pmax[0], cmin[1] - guard_mm, pmax[2]]]),
        "y_plus": np.array([[pmin[0], cmax[1] + guard_mm, pmin[2]], [pmax[0], pmax[1], pmax[2]]]),
    }
    counts: dict[str, int] = {}
    for name, slab in slabs.items():
        valid = np.all(slab[0] < slab[1])
        if not valid:
            raise RuntimeError(f"plate-exclusive slab is empty: {name}")
        overlap = np.all(tri_max >= slab[0], axis=1) & np.all(tri_min <= slab[1], axis=1)
        counts[name] = int(np.count_nonzero(overlap))
    total = sum(counts.values())
    if total:
        raise RuntimeError(f"triangles enter deleted-plate exclusive slabs: {counts}")
    return {
        "deleted_plate_bbox_in_base_link_mm": deleted_plate_bbox_mm.tolist(),
        "exclusive_guard_from_clean_brep_mm": guard_mm,
        "triangle_aabb_intersection_count_by_slab": counts,
        "total_triangle_aabb_intersections": total,
        "pass": True,
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
    header_text = b"B601 BASE_LINK OPERATIONAL COLLISION V1; UNITS=M; FRAME=base_link"
    header = header_text[:80].ljust(80, b"\0")
    output = io.BytesIO()
    output.write(header)
    output.write(struct.pack("<I", int(len(faces))))
    triangles = vertices[faces].astype(np.float64)
    normal = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    for n, triangle in zip(normal.astype("<f4"), triangles.astype("<f4"), strict=True):
        output.write(struct.pack("<12fH", *(n.tolist() + triangle.reshape(-1).tolist()), 0))
    return output.getvalue()


def stable_json_bytes(data: dict[str, Any]) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def record_bytes(name: str, data: bytes) -> dict[str, Any]:
    return {"path": name, "bytes": len(data), "sha256": sha256_bytes(data)}


def build_artifacts() -> ArtifactBuild:
    workspace = find_workspace_root()
    pins = require_source_pins(workspace)
    require_wp11_translation(workspace)
    deleted_plate_bbox_g06_mm = require_plate_classification(workspace)

    step_path = workspace / str(SOURCE_PINS["b50_filtered_linklocal_step"]["path"])
    reader = STEPControl_Reader()
    read_status = reader.ReadFile(str(step_path))
    if read_status != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed: {read_status!r}")
    roots = int(reader.TransferRoots())
    shape = reader.OneShape()
    if roots != 1 or shape.IsNull():
        raise RuntimeError(f"STEP transfer invalid: roots={roots}, null={shape.IsNull()}")

    source_conservative_bbox_mm = bbox(shape, conservative=True)
    source_tight_bbox_mm = bbox(shape, conservative=False)
    final_conservative_bbox_mm = source_conservative_bbox_mm + D_BASE_LINK_MM
    final_tight_bbox_mm = source_tight_bbox_mm + D_BASE_LINK_MM
    contract_bbox_max_abs_error_mm = float(
        np.max(
            np.abs(
                final_conservative_bbox_mm - EXPECTED_CONSERVATIVE_BREP_BBOX_MM
            )
        )
    )
    if contract_bbox_max_abs_error_mm > BBOX_CONTRACT_TOLERANCE_MM:
        raise RuntimeError(
            "conservative BRep bbox contract failed: "
            f"max error {contract_bbox_max_abs_error_mm} mm"
        )

    solids = sorted_solids(shape)
    triangles_m, triangle_solid_ids = extract_triangles_m(shape, solids)
    vertices_m, faces, solid_ids, canonical_metrics = canonicalize(
        triangles_m, triangle_solid_ids
    )
    manifold_metrics = edge_manifold_metrics(faces, solid_ids)

    source_volume_mm3 = float(sum(item["volume_mm3"] for item in solids))
    mesh_volumes_mm3: list[float] = []
    for solid_id in range(69):
        mesh_volumes_mm3.append(
            signed_volume_m3(vertices_m, faces[solid_ids == solid_id]) * 1.0e9
        )
    mesh_volume_mm3 = float(sum(mesh_volumes_mm3))
    aggregate_volume_relative_error = abs(mesh_volume_mm3 - source_volume_mm3) / source_volume_mm3
    per_solid_relative_errors = [
        abs(mesh_volume - solids[index]["volume_mm3"]) / solids[index]["volume_mm3"]
        for index, mesh_volume in enumerate(mesh_volumes_mm3)
    ]
    if aggregate_volume_relative_error > AGGREGATE_VOLUME_RELATIVE_TOLERANCE:
        raise RuntimeError(
            "aggregate mesh/BRep volume mismatch: "
            f"{aggregate_volume_relative_error:.9g}"
        )

    mesh_bbox_mm = np.vstack((vertices_m.min(axis=0), vertices_m.max(axis=0))) * 1000.0
    mesh_bbox_to_tight_brep_max_abs_error_mm = float(
        np.max(np.abs(mesh_bbox_mm - final_tight_bbox_mm))
    )
    if (
        mesh_bbox_to_tight_brep_max_abs_error_mm
        > MESH_BBOX_TO_TIGHT_BREP_TOLERANCE_MM
    ):
        raise RuntimeError(
            "mesh bbox deviates from tight BRep bbox beyond bound: "
            f"{mesh_bbox_to_tight_brep_max_abs_error_mm} mm"
        )

    deleted_plate_bbox_final_mm = deleted_plate_final_bbox_mm(
        deleted_plate_bbox_g06_mm
    )
    plate_metrics = plate_exclusive_metrics(
        vertices_m,
        faces,
        deleted_plate_bbox_final_mm,
        final_conservative_bbox_mm,
    )

    arrays = {
        "faces": faces,
        "frame": np.asarray("base_link"),
        "solid_ids": solid_ids,
        "units": np.asarray("meter"),
        "vertices_m": vertices_m,
    }
    npz_data = canonical_npz_bytes(arrays)
    stl_data = binary_stl_bytes(vertices_m, faces)
    npz_record = record_bytes(NPZ_NAME, npz_data)
    stl_record = record_bytes(STL_NAME, stl_data)
    if stl_record["sha256"] == FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256:
        raise RuntimeError("derived STL hash equals forbidden raw URDF mesh hash")

    checks = {
        "all_source_hashes_and_sizes_match": True,
        "wp11_translation_exact_match": True,
        "wp11_rotation_identity": True,
        "source_step_transfer_one_root": roots == 1,
        "source_brep_69_solids_present_positive_volume": True,
        "source_brepcheck_profile_matches_pinned_67_of_69": (
            sum(bool(item["valid"]) for item in solids) == 67
        ),
        "conservative_brep_bbox_contract_within_0p001_mm": (
            contract_bbox_max_abs_error_mm <= BBOX_CONTRACT_TOLERANCE_MM
        ),
        "mesh_bbox_within_0p10_mm_of_tight_brep": (
            mesh_bbox_to_tight_brep_max_abs_error_mm
            <= MESH_BBOX_TO_TIGHT_BREP_TOLERANCE_MM
        ),
        "aggregate_mesh_volume_error_le_0p1_percent": (
            aggregate_volume_relative_error <= AGGREGATE_VOLUME_RELATIVE_TOLERANCE
        ),
        "no_degenerate_triangles": canonical_metrics["degenerate_triangle_count"] == 0,
        "no_duplicate_triangles": canonical_metrics["duplicate_triangle_count"] == 0,
        "per_source_solid_meshes_closed_and_oriented": bool(
            manifold_metrics["closed"] and manifold_metrics["consistently_oriented"]
        ),
        "deleted_plate_exclusive_regions_clear": plate_metrics["pass"],
        "output_stl_hash_differs_from_forbidden_raw_urdf_stl": True,
        "single_process_parallel_meshing_disabled": True,
    }
    if not all(checks.values()):
        raise RuntimeError(f"fail-closed gate failure: {checks}")

    receipt: dict[str, Any] = {
        "schema": "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V1",
        "artifact_role": "B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY",
        "authority_class": "DERIVED_FROM_FILTERED_BREP_IN_ACCEPTED_URDF_LINK_FRAME",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "path_search_authorized": False,
        "release_credit": False,
        "source_pins": pins,
        "forbidden_input": {
            "artifact": "accepted URDF raw base_link.STL with phantom desktop plate",
            "sha256_known_from_wp11": FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256,
            "opened_by_generator": False,
            "permitted_use": "HASH_INEQUALITY_SENTINEL_ONLY",
        },
        "frame_contract": {
            "link": "base_link",
            "handedness": "RIGHT_HANDED",
            "output_length_unit": "meter",
            "stl_unit_convention": "meter",
            "npz_vertex_array": "vertices_m",
            "wp11_D_base_link_translation_mm": D_BASE_LINK_MM.tolist(),
            "wp11_D_base_link_rotation": "IDENTITY",
            "spacecraft_mount_transform_baked_into_proxy": False,
            "T_SM_baked_into_proxy": False,
        },
        "brep": {
            "reader": "OpenCascade STEPControl_Reader",
            "transfer_roots": roots,
            "solid_count": len(solids),
            "brepcheck_valid_solid_count": sum(bool(item["valid"]) for item in solids),
            "brepcheck_invalid_solid_count": sum(not bool(item["valid"]) for item in solids),
            "brepcheck_invalid_traversal_indices": sorted(
                int(item["traversal_index"]) for item in solids if not item["valid"]
            ),
            "known_invalid_face_status": "5_FACES_BRepCheck_UnorientableShape_ACROSS_TRAVERSAL_SOLIDS_58_59",
            "topods_closed_flag_true_count": sum(
                bool(item["topods_closed_flag"]) for item in solids
            ),
            "topods_closed_flag_used_as_gate": False,
            "closure_authority": "PER_SOURCE_SOLID_MESH_EDGE_INCIDENCE_AND_ORIENTATION_AUDIT",
            "source_conservative_bbox_mm": source_conservative_bbox_mm.tolist(),
            "source_tight_bbox_mm": source_tight_bbox_mm.tolist(),
            "final_conservative_bbox_mm": final_conservative_bbox_mm.tolist(),
            "expected_final_conservative_bbox_mm": EXPECTED_CONSERVATIVE_BREP_BBOX_MM.tolist(),
            "conservative_bbox_contract_tolerance_mm": BBOX_CONTRACT_TOLERANCE_MM,
            "conservative_bbox_max_abs_error_mm": contract_bbox_max_abs_error_mm,
            "final_tight_bbox_mm": final_tight_bbox_mm.tolist(),
            "aggregate_per_solid_volume_mm3": source_volume_mm3,
        },
        "mesh": {
            "engine": "OpenCascade BRepMesh_IncrementalMesh plus canonical custom encoders",
            "parallel_meshing": False,
            "linear_deflection_mm": LINEAR_DEFLECTION_MM,
            "angular_deflection_rad": ANGULAR_DEFLECTION_RAD,
            "vertex_round_decimals_m": VERTEX_ROUND_DECIMALS_M,
            "vertex_count": int(len(vertices_m)),
            "triangle_count": int(len(faces)),
            "source_solid_id_count": int(len(np.unique(solid_ids))),
            "bbox_mm": mesh_bbox_mm.tolist(),
            "bbox_to_tight_brep_max_abs_error_mm": mesh_bbox_to_tight_brep_max_abs_error_mm,
            "bbox_to_tight_brep_acceptance_mm": MESH_BBOX_TO_TIGHT_BREP_TOLERANCE_MM,
            "aggregate_volume_mm3": mesh_volume_mm3,
            "aggregate_volume_relative_error": aggregate_volume_relative_error,
            "aggregate_volume_acceptance_relative": AGGREGATE_VOLUME_RELATIVE_TOLERANCE,
            "per_solid_volume_relative_error_max": float(max(per_solid_relative_errors)),
            "per_solid_volume_relative_error_p95": float(np.quantile(per_solid_relative_errors, 0.95)),
            **canonical_metrics,
            **manifold_metrics,
            "plate_exclusion": plate_metrics,
        },
        "determinism_contract": {
            "canonical_vertex_order": "LEXICOGRAPHIC_FLOAT64_AFTER_1E-12_M_ROUNDING",
            "canonical_triangle_order": "SOLID_ID_THEN_ORIENTED_VERTEX_INDICES",
            "npz_zip_member_order": "LEXICOGRAPHIC",
            "npz_zip_member_timestamp": "1980-01-01T00:00:00",
            "npz_compression": "ZIP_STORED",
            "stl_header": "FIXED_80_BYTE_ASCII_ZERO_PADDED",
            "stl_encoding": "BINARY_LITTLE_ENDIAN_FLOAT32_METER",
            "wall_clock_embedded": False,
            "fresh_process_replay": "VALIDATOR_MUST_REBUILD_AND_COMPARE_ALL_ARTIFACT_BYTES",
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyyaml": yaml.__version__,
            "ocp": OCP_VERSION,
            "platform": sys.platform,
        },
        "checks": checks,
        "artifacts": {
            "canonical_npz": npz_record,
            "binary_stl": stl_record,
        },
        "verdict": "BASE_LINK_OPERATIONAL_COLLISION_PROXY_GENERATED_PASS_PENDING_OWNER_REVIEW_NO_PATH_SEARCH_AUTHORITY",
    }
    receipt_data = stable_json_bytes(receipt)
    return ArtifactBuild(npz_bytes=npz_data, stl_bytes=stl_data, receipt=receipt)


def atomic_write(path: Path, data: bytes, *, replace: bool) -> None:
    if path.parent.resolve() != SCRIPT_DIR:
        raise RuntimeError(f"output escapes owned directory: {path}")
    if path.exists() and not replace:
        raise FileExistsError(f"output exists; pass --replace to regenerate: {path.name}")
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
    results: dict[str, Any] = {}
    for name, data in expected.items():
        path = SCRIPT_DIR / name
        if not path.is_file():
            raise RuntimeError(f"existing artifact missing: {name}")
        existing = path.read_bytes()
        same = existing == data
        results[name] = {
            "same_bytes": same,
            "existing_sha256": sha256_bytes(existing),
            "fresh_sha256": sha256_bytes(data),
        }
        if not same:
            raise RuntimeError(f"fresh deterministic replay differs: {name}")
    return results


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="atomically replace only the three fixed artifacts in this directory",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.verify_existing and args.replace:
        raise SystemExit("--replace is not valid with --verify-existing")
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
