"""Deterministic collision-proxy geometry for the six rigid B601 links."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import ConvexHull


PACKAGE_DIR = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PACKAGE_DIR / "00_contract" / "B601_RIGID_LINK_OPERATIONAL_COLLISION_CONTRACT_V1.json"
SOURCE_LOCK_PATH = PACKAGE_DIR / "01_sources" / "SOURCE_AUTHORITY_LOCK_V1.json"


def workspace_root() -> Path:
    for candidate in (PACKAGE_DIR, *PACKAGE_DIR.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root containing PROJECT_MAP.md was not found")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def link_source_record(link_id: str) -> dict:
    lock = read_json(SOURCE_LOCK_PATH)
    if link_id not in lock["link_sources"]:
        raise KeyError(f"unsupported B601 link id: {link_id}")
    return lock["link_sources"][link_id]


def load_source_mesh(link_id: str) -> trimesh.Trimesh:
    record = link_source_record(link_id)
    path = workspace_root() / record["path"]
    if not path.is_file():
        raise RuntimeError(f"source PLY missing: {path}")
    if path.stat().st_size != record["bytes"]:
        raise RuntimeError(f"source byte count drift: {link_id}")
    if sha256_path(path) != record["sha256"]:
        raise RuntimeError(f"source SHA-256 drift: {link_id}")
    mesh = trimesh.load_mesh(path, process=False)
    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError(f"source is not one mesh: {link_id}")
    if len(mesh.vertices) != record["vertices"] or len(mesh.faces) != record["faces"]:
        raise RuntimeError(f"source topology count drift: {link_id}")
    return mesh


def _unique_hull_edges(simplices: np.ndarray) -> np.ndarray:
    edges = np.concatenate(
        (simplices[:, [0, 1]], simplices[:, [1, 2]], simplices[:, [2, 0]]),
        axis=0,
    )
    edges.sort(axis=1)
    return np.unique(edges, axis=0)


def sectional_convex_cover(link_id: str) -> dict:
    """Return an analytical slab cover of the source point cloud convex hull.

    Extrema of a convex polytope clipped by two parallel planes occur at an
    original hull vertex or an edge/plane intersection.  Each slab AABB is
    therefore a conservative cover of the entire clipped hull, not merely of
    sampled source vertices.
    """

    contract = read_json(CONTRACT_PATH)
    slab_count = int(contract["geometry_method"]["slab_count"])
    transverse_guard_m = float(contract["geometry_method"]["transverse_guard_mm"]) * 1.0e-3
    mesh = load_source_mesh(link_id)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    hull = ConvexHull(vertices, qhull_options="Qx")
    hull_vertices = vertices[np.asarray(hull.vertices, dtype=np.int64)]
    hull_simplices_global = np.asarray(hull.simplices, dtype=np.int64)
    global_to_local = {int(index): position for position, index in enumerate(hull.vertices)}
    hull_simplices = np.asarray(
        [[global_to_local[int(index)] for index in row] for row in hull_simplices_global],
        dtype=np.int64,
    )
    edges = _unique_hull_edges(hull_simplices)
    extents = np.ptp(hull_vertices, axis=0)
    long_axis = int(np.argmax(extents))
    other_axes = [axis for axis in range(3) if axis != long_axis]
    lower = float(hull_vertices[:, long_axis].min())
    upper = float(hull_vertices[:, long_axis].max())
    boundaries = np.linspace(lower, upper, slab_count + 1, dtype=np.float64)
    tolerance = 2.0e-13
    boxes = []
    cross_section_point_counts = []

    for slab_index in range(slab_count):
        a = float(boundaries[slab_index])
        b = float(boundaries[slab_index + 1])
        points = []
        inside = (hull_vertices[:, long_axis] >= a - tolerance) & (
            hull_vertices[:, long_axis] <= b + tolerance
        )
        if np.any(inside):
            points.extend(hull_vertices[inside])
        for edge in edges:
            p0 = hull_vertices[int(edge[0])]
            p1 = hull_vertices[int(edge[1])]
            x0 = float(p0[long_axis])
            x1 = float(p1[long_axis])
            if abs(x1 - x0) <= tolerance:
                continue
            for plane in (a, b):
                if plane < min(x0, x1) - tolerance or plane > max(x0, x1) + tolerance:
                    continue
                t = (plane - x0) / (x1 - x0)
                if -tolerance <= t <= 1.0 + tolerance:
                    points.append(p0 + t * (p1 - p0))
        if not points:
            raise RuntimeError(f"empty convex cross-section for {link_id} slab {slab_index}")
        section = np.asarray(points, dtype=np.float64)
        box = np.zeros((2, 3), dtype=np.float64)
        box[0, long_axis] = a
        box[1, long_axis] = b
        for axis in other_axes:
            box[0, axis] = float(section[:, axis].min()) - transverse_guard_m
            box[1, axis] = float(section[:, axis].max()) + transverse_guard_m
        if not np.all(box[1] > box[0]):
            raise RuntimeError(f"non-positive proxy box for {link_id} slab {slab_index}")
        boxes.append(box)
        cross_section_point_counts.append(int(len(section)))

    boxes_m = np.asarray(boxes, dtype=np.float64)
    return {
        "link_id": link_id,
        "mesh": mesh,
        "hull": hull,
        "hull_vertices_m": hull_vertices,
        "hull_edges": edges,
        "long_axis": long_axis,
        "boundaries_m": boundaries,
        "boxes_m": boxes_m,
        "cross_section_point_counts": cross_section_point_counts,
        "source_bbox_m": np.vstack((vertices.min(axis=0), vertices.max(axis=0))),
        "hull_volume_m3": float(hull.volume),
        "proxy_sum_volume_m3": float(np.prod(boxes_m[:, 1] - boxes_m[:, 0], axis=1).sum()),
    }


def point_membership(points: np.ndarray, boxes_m: np.ndarray, tolerance_m: float = 2.0e-12) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    lower_ok = points[:, None, :] >= boxes_m[None, :, 0, :] - tolerance_m
    upper_ok = points[:, None, :] <= boxes_m[None, :, 1, :] + tolerance_m
    return np.any(np.all(lower_ok & upper_ok, axis=2), axis=1)

