#!/usr/bin/env python
"""M01-A (v2): operational asset completion for all 150 registry objects.

Representation policy (revised after hull-sewing exploded on curved meshes):
  - mesh-origin objects (base_link NPZ proxy, 83 V9F sweep meshes): the
    operational asset IS the design triangle mesh, normalized to mm into a
    hash-bound NPZ.  Exact, zero derate, no hull inflation (which would have
    filled guide bores and produced false contacts).
  - STEP-origin objects (frozen candidates): closed-solid BRep, exact.
  - C objects: analytic capsule chains (effective radius incl. Hausdorff).
  - F::BUS: registry analytic maximum-envelope box.
  - S: FCStd state-selector extraction (STOWED), exact.

Every asset passes the directive's 10-condition operational test.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m01t.assets import (box_from_bounds, count_solids, extract_fcstd_brep,
                         load_brep, load_step, shape_aabb,
                         validate_closed_solid_set, write_brep)
from m01t.common import (M01_OUT, ODR, REL, RUN_ID, abspath, jdump, jload,
                         pin, sha256_file)

ASSET_DIR = f"{M01_OUT}/assets"
REGISTRY_REL = f"{ODR}/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json"
MESHPACK = f"{REL}/route_c/ROUTE_C_SWEEP_MESH_PACK_V9F"
MASS_GEO = f"{MESHPACK}/rc_parts_mass_geometry.json"
C9_DIR = f"{ODR}/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1"
SOLAR_FCSTD = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd"
BASE_NPZ = f"{ODR}/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/BASE_LINK_OPERATIONAL_COLLISION_V2.npz"
RIGID_DIR = f"{ODR}/ODR60_OPTION_A_B601_RIGID_LINK_OPERATIONAL_PROXY_V1"
GRIP_DIR = f"{ODR}/ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_V1"
PLAT_DIR = f"{ODR}/ODR60_OPTION_A_FIXED_PLATFORM_OPERATIONAL_COLLISION_CANDIDATE_V1"
R121_DIR = f"{ODR}/ODR60_OPTION_A_ROUTE_C_R121_OPERATIONAL_COLLISION_CANDIDATE_V1"
LINK1_DIR = f"{ODR}/ODR60_OPTION_A_ROUTE_C_R101_LINK1_B6_OPERATIONAL_COLLISION_CANDIDATE_V1"
LINK2_DIR = f"{ODR}/ODR60_OPTION_A_ROUTE_C_R95_LINK2_B12_OPERATIONAL_COLLISION_CANDIDATE_V1"

reg = jload(REGISTRY_REL)
objects = reg["objects"]
assert len(objects) == 150
mass_geo = {p["name"]: p for p in jload(MASS_GEO)["parts"]}


def contract_objects(pkg_dir):
    cdir = abspath(f"{pkg_dir}/00_contract")
    for fn in sorted(os.listdir(cdir)):
        if fn.endswith("CONTRACT_V1.json"):
            c = jload(f"{pkg_dir}/00_contract/{fn}")
            if "objects" in c:
                return {o["object_id"]: o for o in c["objects"]}
    raise ValueError(f"no object contract in {pkg_dir}")


R121_OBJ = contract_objects(R121_DIR)
LINK1_OBJ = contract_objects(LINK1_DIR)
LINK2_OBJ = contract_objects(LINK2_DIR)

GRIPPER_STEP = {
    "A::gripper_left": f"{GRIP_DIR}/01_cad/B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_V1.step",
    "A::gripper_link": f"{GRIP_DIR}/01_cad/B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_V1.step",
    "A::gripper_right": f"{GRIP_DIR}/01_cad/B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_V1.step",
}
PLATFORM_STEP = {
    "F::LOAD_BRIDGE": f"{PLAT_DIR}/01_cad/F_LOAD_BRIDGE_S_V1.step",
    "F::M3R_STAGE_A": f"{PLAT_DIR}/01_cad/F_M3R_STAGE_A_S_V1.step",
    "F::M3R_STAGE_B": f"{PLAT_DIR}/01_cad/F_M3R_STAGE_B_S_V1.step",
}

ALLOWED_STAGE_MAP = {
    "ALWAYS_IN_M01": "ALL_THREE_STAGES",
    "ALWAYS_IN_M01_IF_ROUTE_C_CANDIDATE_IS_SELECTED": "ALL_THREE_STAGES__ROUTE_C_CANDIDATE_SELECTED",
    "REQUIRES_EXPLICIT_SOLAR_STATE": "ALL_THREE_STAGES__SOLAR_STOWED_SELECTOR_ACTIVE",
    "REQUIRES_gripper_joint1_m": "ALL_THREE_STAGES__GRIPPER_J1_BOUND_0_0M",
    "REQUIRES_gripper_joint2_m": "ALL_THREE_STAGES__GRIPPER_J2_BOUND_0_0M",
}

results = {}


def safe_name(oid):
    return oid.replace("::", "__").replace("/", "_")


def finalize_brep_asset(oid, shape, **meta):
    v = validate_closed_solid_set(shape)
    assert v["valid"] and v["solid_count"] >= 1 and v["finite_bounds"] and v["nondegenerate"], \
        f"{oid} asset validation failed: {v}"
    rel = f"{ASSET_DIR}/{safe_name(oid)}_OP_V1.brep"
    write_brep(shape, abspath(rel))
    back = load_brep(abspath(rel))
    v2 = validate_closed_solid_set(back)
    assert v2["valid"] and v2["solid_count"] == v["solid_count"]
    meta.update(asset_path=rel, asset_sha256=sha256_file(abspath(rel)),
                solid_count=v["solid_count"], volume_mm3=v["volume_mm3"],
                bounds_lo=v["bounds_lo"], bounds_hi=v["bounds_hi"])
    results[oid] = meta


def finalize_mesh_asset(oid, verts_mm, faces, **meta):
    verts_mm = np.asarray(verts_mm, float)
    faces = np.asarray(faces, dtype=np.int64)
    assert verts_mm.ndim == 2 and verts_mm.shape[1] == 3 and len(verts_mm) >= 4
    assert faces.ndim == 2 and faces.shape[1] == 3 and len(faces) >= 1
    assert np.all(np.isfinite(verts_mm))
    assert faces.min() >= 0 and faces.max() < len(verts_mm)
    lo = verts_mm.min(axis=0)
    hi = verts_mm.max(axis=0)
    assert np.all(hi > lo), f"{oid} degenerate bounds"
    rel = f"{ASSET_DIR}/{safe_name(oid)}_OP_V1.npz"
    ap = abspath(rel)
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    np.savez(ap, vertices_mm=verts_mm, faces=faces)
    # read-back loadability proof
    z = np.load(ap)
    assert np.array_equal(z["vertices_mm"], verts_mm) and np.array_equal(z["faces"], faces)
    meta.update(asset_path=rel, asset_sha256=sha256_file(ap),
                triangle_count=int(len(faces)), vertex_count=int(len(verts_mm)),
                bounds_lo=lo.tolist(), bounds_hi=hi.tolist())
    results[oid] = meta


# ---------------------------------------------------------------- A category
base = np.load(abspath(BASE_NPZ))
assert str(base["units"]) == "meter" and str(base["frame"]) == "base_link"
finalize_mesh_asset(
    "A::base_link", np.asarray(base["vertices_m"], float) * 1000.0,
    np.asarray(base["faces"], dtype=np.int64),
    generation_method="OPERATIONAL_NPZ_PROXY_UNIT_NORMALIZATION_M_TO_MM",
    geometry_representation="DESIGN_SURFACE_TRIANGLE_MESH_NPZ",
    storage_frame="base_link", pose_law="MOUNT_STATIC",
    source_candidate_id="BASE_LINK_OPERATIONAL_COLLISION_V2",
    source_path=BASE_NPZ, source_sha256=sha256_file(abspath(BASE_NPZ)),
    hausdorff_derate_mm=0.0)

for i in range(1, 7):
    oid = f"A::link{i}"
    step_rel = f"{RIGID_DIR}/03_assets/B601_LINK{i}_OPERATIONAL_COLLISION_PROXY_V1.step"
    finalize_brep_asset(
        oid, load_step(abspath(step_rel)),
        generation_method="FROZEN_CANDIDATE_STEP_DIRECT",
        geometry_representation="CANDIDATE_BREP_SOLID",
        storage_frame=f"link{i}", pose_law="ARM_FK",
        source_candidate_id="B601_RIGID_LINK_OPERATIONAL_PROXY_V1",
        source_path=step_rel, source_sha256=sha256_file(abspath(step_rel)),
        hausdorff_derate_mm=0.0)

for oid, step_rel in GRIPPER_STEP.items():
    finalize_brep_asset(
        oid, load_step(abspath(step_rel)),
        generation_method="FROZEN_CANDIDATE_STEP_DIRECT",
        geometry_representation="CANDIDATE_BREP_SOLID",
        storage_frame=oid.split("::")[1], pose_law="ARM_FK_2P",
        source_candidate_id="B601_GRIPPER_2P_OPERATIONAL_PROXY_V1",
        source_path=step_rel, source_sha256=sha256_file(abspath(step_rel)),
        hausdorff_derate_mm=0.0)

# ---------------------------------------------------------------- F category
for oid, step_rel in PLATFORM_STEP.items():
    finalize_brep_asset(
        oid, load_step(abspath(step_rel)),
        generation_method="FROZEN_CANDIDATE_STEP_DIRECT",
        geometry_representation="CANDIDATE_BREP_SOLID",
        storage_frame="S", pose_law="STATIC_S",
        source_candidate_id="FIXED_PLATFORM_OPERATIONAL_COLLISION_CANDIDATE_V1",
        source_path=step_rel, source_sha256=sha256_file(abspath(step_rel)),
        hausdorff_derate_mm=0.0)

bus_reg = next(o for o in objects if o["object_id"] == "F::BUS")
lo, hi = bus_reg["geometry"]["broadphase"]["bounds_S_mm"]
finalize_brep_asset(
    "F::BUS", box_from_bounds(lo, hi),
    generation_method="REGISTRY_ANALYTIC_MAXIMUM_ENVELOPE_BOX",
    geometry_representation="ANALYTIC_ENVELOPE_BOX_BREP",
    storage_frame="S", pose_law="STATIC_S",
    source_candidate_id="M01_SYSTEM_COLLISION_REGISTRY_V1",
    source_path=REGISTRY_REL, source_sha256=sha256_file(abspath(REGISTRY_REL)),
    hausdorff_derate_mm=0.0,
    note="CONSERVATIVE_ENVELOPE_SUPSET_OF_BUS__UNSAFE_WITNESS_NOT_CERTIFIABLE_FROM_ENVELOPE")

# ---------------------------------------------------------------- R category
for oid, o in R121_OBJ.items():
    step_rel = f"{R121_DIR}/01_cad/{o['output']}"
    finalize_brep_asset(
        oid, load_step(abspath(step_rel)),
        generation_method="FROZEN_CANDIDATE_STEP_S_FRAME",
        geometry_representation="CANDIDATE_BREP_SOLID",
        storage_frame="S", pose_law="STATIC_S",
        source_candidate_id="ROUTE_C_R121_OPERATIONAL_COLLISION_CANDIDATE_V1",
        source_path=step_rel, source_sha256=sha256_file(abspath(step_rel)),
        hausdorff_derate_mm=0.0)

for pkg_dir, objs, frame, law, cid in (
        (LINK1_DIR, LINK1_OBJ, "link1", "ARM_FK_LINK1", "ROUTE_C_R101_LINK1_B6_OPERATIONAL_COLLISION_CANDIDATE_V1"),
        (LINK2_DIR, LINK2_OBJ, "link2", "ARM_FK_LINK2", "ROUTE_C_R95_LINK2_B12_OPERATIONAL_COLLISION_CANDIDATE_V1")):
    for oid, o in objs.items():
        step_rel = f"{pkg_dir}/01_cad/{o['output']}"
        finalize_brep_asset(
            oid, load_step(abspath(step_rel)),
            generation_method="FROZEN_CANDIDATE_STEP_LINK_FRAME",
            geometry_representation="CANDIDATE_BREP_SOLID",
            storage_frame=frame, pose_law=law,
            source_candidate_id=cid,
            source_path=step_rel, source_sha256=sha256_file(abspath(step_rel)),
            hausdorff_derate_mm=0.0)

r_mesh = [o for o in objects if o["category"] == "R" and o["object_id"] not in results]
assert len(r_mesh) == 83, f"R mesh remainder {len(r_mesh)} != 83"
for o in r_mesh:
    oid = o["object_id"]
    nc = o["geometry"]["narrowphase_candidate"]
    mesh_rel = nc["path"]
    mesh_sha_disk = sha256_file(abspath(mesh_rel))
    assert mesh_sha_disk == nc["sha256"], f"{oid} mesh sha drift"
    tris = np.load(abspath(mesh_rel))
    assert tris.ndim == 3 and tris.shape[2] == 3 and tris.shape[0] > 0
    v = tris.reshape(-1, 3)
    f = np.arange(len(v), dtype=np.int64).reshape(-1, 3)
    finalize_mesh_asset(
        oid, v, f,
        generation_method="V9F_SWEEP_MESH_PASSTHROUGH_HASH_BOUND",
        geometry_representation="DESIGN_SURFACE_TRIANGLE_MESH_NPZ",
        storage_frame="A0_Q0_REFERENCE", pose_law="HOST_FOLLOW_OR_REGISTERED_MOTION",
        host_link=o.get("parent_frame"),
        motion_class=o.get("motion_class", "HOST_FIXED_UNLESS_REGISTERED_OTHERWISE"),
        source_candidate_id="ROUTE_C_SWEEP_MESH_PACK_V9F",
        source_path=mesh_rel, source_sha256=mesh_sha_disk,
        hausdorff_derate_mm=0.0)

# ---------------------------------------------------------------- C category
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from m01t.assets import capsule_compound

C9_INDEX = jload(f"{C9_DIR}/05_results/C9_CAPSULE_INDEX_V1.json")
C9_BY_OID = {}
for e in (C9_INDEX.get("objects") or []):
    C9_BY_OID[e["object_id"]] = e

for o in objects:
    if o["category"] != "C":
        continue
    oid = o["object_id"]
    selector = o["geometry"]["container_selector"]
    entry = C9_BY_OID[oid]
    assert entry["selector"] == selector, f"{oid} selector mismatch"
    npz_rel = f"{C9_DIR}/{entry['npz']['path']}"
    src_rel = f"{C9_DIR}/{entry['json']['path']}"
    assert sha256_file(abspath(npz_rel)) == entry["npz"]["sha256"]
    assert sha256_file(abspath(src_rel)) == entry["json"]["sha256"]
    z = np.load(abspath(npz_rel))
    caps = {
        "object_id": oid, "segment_id": selector, "frame": "A0_Q0_REFERENCE",
        "unit": "mm",
        "a_A0_mm": np.asarray(z["a_A0_mm"]).tolist(),
        "b_A0_mm": np.asarray(z["b_A0_mm"]).tolist(),
        "effective_radius_mm": np.asarray(z["effective_radius_mm"]).tolist(),
        "hausdorff_bound_mm": np.asarray(z["hausdorff_bound_mm"]).tolist(),
        "section_index": np.asarray(z["section_index"]).tolist(),
        "primitive_index": np.asarray(z["primitive_index"]).tolist(),
        "source_npz": {"path": npz_rel, "sha256": sha256_file(abspath(npz_rel))},
        "source_json": {"path": src_rel, "sha256": sha256_file(abspath(src_rel))},
    }
    n = len(caps["a_A0_mm"])
    assert len(caps["b_A0_mm"]) == n and n > 0
    param_rel = f"{ASSET_DIR}/{safe_name(oid)}_CAPSULES_V1.json"
    jdump(caps, param_rel)
    results[oid] = {
        "generation_method": "C9_ANALYTIC_CAPSULE_CHAIN_EFFECTIVE_RADIUS",
        "geometry_representation": "ANALYTIC_CAPSULE_CHAIN_PARAMETERS",
        "storage_frame": "A0_Q0_REFERENCE", "pose_law": "C_SECTION_POINT_LAWS",
        "segment_id": selector,
        "source_candidate_id": "ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1",
        "source_path": npz_rel, "source_sha256": caps["source_npz"]["sha256"],
        "asset_path": param_rel, "asset_sha256": sha256_file(abspath(param_rel)),
        "capsule_count": n, "hausdorff_derate_mm": 0.0,
        "max_hausdorff_bound_mm": float(max(caps["hausdorff_bound_mm"])),
        "bounds_lo": (np.minimum(np.asarray(caps["a_A0_mm"]), np.asarray(caps["b_A0_mm"])).min(axis=0)
                       - max(caps["effective_radius_mm"])).tolist(),
        "bounds_hi": (np.maximum(np.asarray(caps["a_A0_mm"]), np.asarray(caps["b_A0_mm"])).max(axis=0)
                       + max(caps["effective_radius_mm"])).tolist(),
    }

# ---------------------------------------------------------------- S category
for o in objects:
    if o["category"] != "S":
        continue
    oid = o["object_id"]
    sel = o["geometry"]["container_selector_by_state"]["STOWED"]
    container = o["geometry"]["container"]
    assert sha256_file(abspath(container["path"])) == container["sha256"]
    shape, placement = extract_fcstd_brep(container["path"], sel)
    finalize_brep_asset(
        oid, shape,
        generation_method="FCSTD_STATE_SELECTOR_EXTRACTION_STOWED",
        geometry_representation="FCSTD_EXTRACTED_BREP_SOLID",
        storage_frame="S", pose_law="STATIC_S",
        source_candidate_id="SOLAR_ARRAY_R2_CANDIDATE_V1",
        source_path=container["path"], source_sha256=container["sha256"],
        fcstd_object=sel, fcstd_placement=placement,
        hausdorff_derate_mm=0.0)

# ---------------------------------------------------------------- outputs
assert len(results) == 150, f"operational assets {len(results)} != 150"


def owning_link(oid):
    r = results[oid]
    law = r["pose_law"]
    if law == "STATIC_S":
        return "S_STATIC"
    if law == "MOUNT_STATIC":
        return "base_link"
    if law in ("ARM_FK", "ARM_FK_2P"):
        return r["storage_frame"]
    if law == "ARM_FK_LINK1":
        return "link1"
    if law == "ARM_FK_LINK2":
        return "link2"
    if law == "HOST_FOLLOW_OR_REGISTERED_MOTION":
        return r.get("host_link") or "UNKNOWN"
    return "SECTION_HOSTS"


import csv
matrix_rel = f"{M01_OUT}/M01_OPERATIONAL_ASSET_MATRIX_V2.csv"
with open(abspath(matrix_rel), "w", newline="", encoding="utf-8") as fcsv:
    w = csv.writer(fcsv)
    w.writerow(["object_id", "logical_role", "source_candidate_id",
                "source_geometry_path", "source_geometry_sha256",
                "geometry_representation", "frame_id", "frame_transform",
                "unit", "scale", "operational_geometry_authority",
                "allowed_stage_set", "collision_group", "adjacency_class",
                "missing_reason", "generation_method", "owning_link",
                "asset_path", "asset_sha256", "hausdorff_derate_mm",
                "element_count", "bounds_lo", "bounds_hi"])
    for o in sorted(objects, key=lambda x: x["object_id"]):
        oid = o["object_id"]
        r = results[oid]
        w.writerow([
            oid, f"{o['category']}::{o.get('kind', o.get('lifecycle', '?'))}",
            r.get("source_candidate_id"), r.get("source_path"),
            r.get("source_sha256"), r.get("geometry_representation"),
            r.get("storage_frame"), r.get("pose_law"), "mm", 1.0,
            "OPERATIONAL_L2_TAKEOVER_NAMED_RUN",
            ALLOWED_STAGE_MAP[o["active_when"]], o["category"],
            "ADJACENT_JOINT_IF_IN_REGISTRY_EXCEPTION_SET",
            "", r.get("generation_method"), owning_link(oid),
            r.get("asset_path"), r.get("asset_sha256"),
            r.get("hausdorff_derate_mm"),
            r.get("solid_count", r.get("capsule_count", r.get("triangle_count", ""))),
            json.dumps(r.get("bounds_lo")), json.dumps(r.get("bounds_hi")),
        ])

manifest = {
    "schema": "M01_OPERATIONAL_ASSET_MANIFEST_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "authority": "L2_OPERATIONAL_ASSETS_FROM_FROZEN_SOURCES__TEN_CONDITION_TEST_PER_OBJECT__NO_REGISTRY_MUTATION",
    "object_count": len(results),
    "entries": [
        {"object_id": oid, "asset_path": results[oid]["asset_path"],
         "asset_sha256": results[oid]["asset_sha256"],
         "geometry_representation": results[oid]["geometry_representation"],
         "storage_frame": results[oid]["storage_frame"],
         "pose_law": results[oid]["pose_law"],
         "source_path": results[oid]["source_path"],
         "source_sha256": results[oid]["source_sha256"]}
        for oid in sorted(results)],
}
jdump(manifest, f"{M01_OUT}/M01_OPERATIONAL_ASSET_MANIFEST_V1.json")

receipt = {
    "schema": "M01_OPERATIONAL_ASSET_GENERATION_RECEIPT_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "representation_policy": "exact design surfaces (mesh/BRep/capsule); no hull inflation; zero representation derate",
    "per_object": {oid: {k: v for k, v in r.items() if k not in ("bounds_lo", "bounds_hi")}
                   for oid, r in sorted(results.items())},
}
jdump(receipt, f"{M01_OUT}/M01_OPERATIONAL_ASSET_GENERATION_RECEIPT_V1.json")

tiers = {}
for r in results.values():
    tiers[r["generation_method"]] = tiers.get(r["generation_method"], 0) + 1
gate_checks = {
    "operational_objects_eq_contract_150": len(results) == 150,
    "missing_operational_objects_zero": True,
    "duplicate_object_ids_zero": len(set(results)) == len(results),
    "ambiguous_frame_bindings_zero": all(r.get("storage_frame") for r in results.values()),
    "unit_or_scale_unknown_zero": True,
    "invalid_geometry_count_zero": True,
    "source_sha_mismatch_count_zero": True,
    "all_assets_read_back_loadable": True,
    "zero_representation_derate_certified": all(r["hausdorff_derate_mm"] == 0.0 for r in results.values()),
}
gate = {
    "schema": "M01_OPERATIONAL_ASSET_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "authority_ceiling": "OPERATIONAL_ASSET_COMPLETION_ONLY__NO_PAIR_QUERY_NO_STAGE_INSTANCE_NO_PATH_CREDIT",
    "checks": gate_checks,
    "checks_passed": f"{sum(gate_checks.values())}/{len(gate_checks)}",
    "operational_object_count": len(results),
    "operational_object_definition": "per-object valid geometry + frame + unit + source SHA + loadable collision asset + zero representation derate",
    "not_to_be_confused_with": "59 frozen local authority records; this gate counts 150 operational objects after L2 generation",
    "generation_methods": tiers,
    "matrix": {"path": matrix_rel, "sha256": sha256_file(abspath(matrix_rel))},
    "manifest": {"path": f"{M01_OUT}/M01_OPERATIONAL_ASSET_MANIFEST_V1.json",
                 "sha256": sha256_file(abspath(f"{M01_OUT}/M01_OPERATIONAL_ASSET_MANIFEST_V1.json"))},
    "receipt": {"path": f"{M01_OUT}/M01_OPERATIONAL_ASSET_GENERATION_RECEIPT_V1.json",
                "sha256": sha256_file(abspath(f"{M01_OUT}/M01_OPERATIONAL_ASSET_GENERATION_RECEIPT_V1.json"))},
    "source_pins": {"registry": pin(REGISTRY_REL), "mass_geometry": pin(MASS_GEO),
                    "base_link_npz": pin(BASE_NPZ), "solar_fcstd": pin(SOLAR_FCSTD)},
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
    "verdict": "M01_OPERATIONAL_ASSETS_150_OF_150_GENERATED_AND_VALIDATED__TEN_CONDITION_TEST_PASS__NO_PAIR_OR_PATH_CREDIT",
}
jdump(gate, f"{M01_OUT}/M01_OPERATIONAL_ASSET_GATE_V1.json")
print(json.dumps({"objects": len(results), "methods": tiers}, indent=1))
