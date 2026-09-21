"""Regression tests for the emitted base_link operational collision proxy."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

import generate_base_link_operational_collision as generator
import validate_base_link_operational_collision as validator


ROOT = Path(__file__).resolve().parent
PASS_ARTIFACTS_PRESENT = all(
    (ROOT / name).is_file()
    for name in (generator.NPZ_NAME, generator.STL_NAME, generator.RECEIPT_NAME)
)


def test_hold_diagnostic_is_fail_closed_when_proxy_is_absent() -> None:
    if PASS_ARTIFACTS_PRESENT:
        pytest.skip("operational proxy artifacts are present")
    report = validator.validate_hold()
    assert report["proxy_pass"] is False
    assert report["next_stage_authorized"] is False
    assert report["path_search_authorized"] is False
    assert all(report["checks"].values())


def test_hold_records_all_three_negative_alternative_routes() -> None:
    if PASS_ARTIFACTS_PRESENT:
        pytest.skip("operational proxy artifacts are present")
    hold = json.loads((ROOT / validator.HOLD_NAME).read_text(encoding="utf-8"))
    assert len(hold["missing_faces"]) == 11
    assert hold["missing_surface_area_mm2"] > 0
    assert hold["gate"]["standard_shapefix_produced_promotable_candidate"] is False
    assert hold["gate"]["freecad_occt78_all_positive_area_faces_triangulated"] is False
    assert hold["gate"]["m5_ply_closed_non_degenerate_collision_surface"] is False


def test_receipt_is_fail_closed_and_does_not_authorize_path_search() -> None:
    if not PASS_ARTIFACTS_PRESENT:
        pytest.skip("HOLD: no operational proxy receipt")
    receipt = json.loads((ROOT / generator.RECEIPT_NAME).read_text(encoding="utf-8"))
    assert all(receipt["checks"].values())
    assert receipt["review_status"] == "PENDING_OWNER_REVIEW"
    assert receipt["next_stage_authorized"] is False
    assert receipt["path_search_authorized"] is False
    assert receipt["release_credit"] is False
    assert receipt["forbidden_input"]["opened_by_generator"] is False


def test_npz_encoding_and_collision_schema_are_canonical() -> None:
    if not PASS_ARTIFACTS_PRESENT:
        pytest.skip("HOLD: no canonical NPZ")
    path = ROOT / generator.NPZ_NAME
    with zipfile.ZipFile(path) as archive:
        assert [item.filename for item in archive.infolist()] == [
            "faces.npy",
            "frame.npy",
            "solid_ids.npy",
            "units.npy",
            "vertices_m.npy",
        ]
        assert all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist())
        assert all(item.compress_type == zipfile.ZIP_STORED for item in archive.infolist())
    with np.load(path, allow_pickle=False) as data:
        assert data["vertices_m"].dtype == np.dtype("<f8")
        assert data["faces"].dtype == np.dtype("<u4")
        assert data["solid_ids"].dtype == np.dtype("<u2")
        assert data["units"].item() == "meter"
        assert data["frame"].item() == "base_link"
        assert np.array_equal(np.unique(data["solid_ids"]), np.arange(69, dtype=np.uint16))


def test_stl_is_derived_and_not_the_contaminated_urdf_mesh() -> None:
    if not PASS_ARTIFACTS_PRESENT:
        pytest.skip("HOLD: no operational STL")
    stl_path = ROOT / generator.STL_NAME
    receipt = json.loads((ROOT / generator.RECEIPT_NAME).read_text(encoding="utf-8"))
    stl_hash = generator.sha256_file(stl_path)
    assert stl_hash == receipt["artifacts"]["binary_stl"]["sha256"]
    assert stl_hash != generator.FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256
    assert receipt["mesh"]["plate_exclusion"]["total_triangle_aabb_intersections"] == 0


def test_lightweight_validator_reproduces_geometry_contract() -> None:
    if not PASS_ARTIFACTS_PRESENT:
        pytest.skip("HOLD: no operational proxy geometry")
    report = validator.validate(replay=False)
    assert report["verdict"] == "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_PASS_NO_REPLAY"
    assert report["geometry"]["source_solid_ids"] == 69
    assert report["geometry"]["boundary_edge_count"] == 0
    assert report["geometry"]["nonmanifold_edge_count"] == 0
    assert report["geometry"]["orientation_mismatch_edge_count"] == 0
