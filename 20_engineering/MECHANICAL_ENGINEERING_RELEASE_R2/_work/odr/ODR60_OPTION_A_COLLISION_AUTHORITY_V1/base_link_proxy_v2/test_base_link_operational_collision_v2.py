from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_checked_in_collision_bytes_are_a_fresh_deterministic_replay():
    emitter = load_module("base_proxy_v2_emitter_test", "emit_base_link_operational_collision_v2.py")
    replay = emitter.verify_existing(emitter.build_artifacts())
    assert all(row["same_bytes"] for row in replay.values())


def test_receipt_is_geometry_pass_but_remains_non_authorizing():
    receipt = json.loads((HERE / "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2.json").read_text(encoding="utf-8"))
    assert all(receipt["checks"].values())
    assert receipt["next_stage_authorized"] is False
    assert receipt["path_search_authorized"] is False
    assert receipt["system_pair_evaluation_authorized"] is False
    assert receipt["release_credit"] is False
    assert receipt["source_disposition"]["catalog_candidate_promoted_to_operational_proxy"] is False
    assert receipt["brep"]["brepcheck_valid_solid_count"] == 68
    assert receipt["brep"]["aggregate_proxy_volume_inflation_relative"] > 0.20


def test_npz_contract_has_68_closed_proxy_solid_ids_and_no_raw_mesh_alias():
    emitter = load_module("base_proxy_v2_emitter_npz_test", "emit_base_link_operational_collision_v2.py")
    with np.load(HERE / emitter.NPZ_NAME, allow_pickle=False) as archive:
        faces = np.asarray(archive["faces"])
        solid_ids = np.asarray(archive["solid_ids"])
        assert archive["frame"].item() == "base_link"
        assert archive["units"].item() == "meter"
    assert np.array_equal(np.unique(solid_ids), np.arange(68, dtype=np.uint16))
    metrics = emitter.manifold_metrics(faces, solid_ids, 68)
    assert metrics["per_solid_closed"] is True
    assert metrics["per_solid_consistently_oriented"] is True
    assert emitter.sha256_path(HERE / emitter.STL_NAME) != emitter.FORBIDDEN_RAW_URDF_BASE_LINK_STL_SHA256


def test_independent_validation_is_hash_bound_and_all_true():
    validation = json.loads((HERE / "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V2.json").read_text(encoding="utf-8"))
    assert all(validation["checks"].values())
    assert validation["independent_metrics"]["solid_id_count"] == 68
    assert validation["independent_metrics"]["boundary_edge_count"] == 0
    assert validation["independent_metrics"]["nonmanifold_edge_count"] == 0
    assert validation["independent_metrics"]["orientation_mismatch_edge_count"] == 0
    assert validation["path_search_authorized"] is False
    assert validation["system_pair_evaluation_authorized"] is False
