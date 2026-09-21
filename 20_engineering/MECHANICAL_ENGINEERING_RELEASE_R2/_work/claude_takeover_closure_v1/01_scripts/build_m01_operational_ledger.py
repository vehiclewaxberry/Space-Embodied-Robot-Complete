#!/usr/bin/env python
"""WP-B — M01 operationalization ledger builder (deterministic, fail-closed).

Consumes (read-only):
  - M01_SYSTEM_COLLISION_REGISTRY_V1.json      (150 objects + 10 K candidates)
  - M01_OPERATIONAL_ASSET_READINESS_V1.csv     (167-row prebind readiness ledger)
  - M01_SCENE_DECISION_INTAKE_V1.yaml          (three-stage schema + quarantined candidates)
  - the seven frozen local candidate packages  (R20/Link1/Link2/C9/gripper/platform/rigid-link)

Emits (append-only, new files only) into _work/claude_takeover_closure_v1/03_m01/:
  M01_OPERATIONAL_ASSET_MATRIX_V1.csv
  M01_STAGE_BINDING_V1.json
  M01_PAIR_POLICY_V1.csv
  M01_MOTION_CERTIFICATES_V1.json
  M01_PAIR_ORACLE_V1.json
  M01_CONTINUOUS_EDGE_GATE_V1.json
  M01_BOUNDED_PATH_GATE_V1.json

Authority ceiling: RESEARCH_LEVEL_CANDIDATE_BINDING_ONLY. No production system
registry row is added, no pair query is executed, UNKNOWN never becomes ALLOW,
and the parent Gate A / TMG-4 / G12 state is not modified.
"""
import csv
import hashlib
import json
import os
import sys
from collections import Counter

ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
ODR = os.path.join(ROOT, "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr")
OUTDIR = os.path.join(ROOT, "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/claude_takeover_closure_v1/03_m01")

REGISTRY = os.path.join(ODR, "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json")
READINESS = os.path.join(ODR, "ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_OPERATIONAL_ASSET_READINESS_V1.csv")

CANDIDATE_PACKAGES = {
    "R20_ROOT_STATIC": "ODR60_OPTION_A_ROUTE_C_R121_OPERATIONAL_COLLISION_CANDIDATE_V1",
    "LINK1_B6": "ODR60_OPTION_A_ROUTE_C_R101_LINK1_B6_OPERATIONAL_COLLISION_CANDIDATE_V1",
    "LINK2_B12": "ODR60_OPTION_A_ROUTE_C_R95_LINK2_B12_OPERATIONAL_COLLISION_CANDIDATE_V1",
    "C9_ANALYTIC": "ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1",
    "GRIPPER_2P": "ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_V1",
    "FIXED_PLATFORM": "ODR60_OPTION_A_FIXED_PLATFORM_OPERATIONAL_COLLISION_CANDIDATE_V1",
    "RIGID_LINKS": "ODR60_OPTION_A_B601_RIGID_LINK_OPERATIONAL_PROXY_V1",
}

AUTH_HEADER = {
    "authority_ceiling": "RESEARCH_LEVEL_CANDIDATE_BINDING_ONLY__NO_PRODUCTION_REGISTRY_ROW_ADDED__NO_PAIR_QUERY_EXECUTED",
    "owner_directive": "CLAUDE CODE TAKEOVER DIRECTIVE (2026-08-28) Work Package B",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "fail_closed_invariants": [
        "UNKNOWN is never ALLOW",
        "candidate binding never rewrites the prebind gate or registry",
        "production pair/edge/path counts remain 0 until owner system revision",
    ],
}

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def jload(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def jdump(obj, path):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, sort_keys=True)

os.makedirs(OUTDIR, exist_ok=True)
reg = jload(REGISTRY)
objects = reg["objects"]
assert len(objects) == 150, f"registry object count {len(objects)} != 150"

readiness = {}
with open(READINESS, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        readiness[row["id"]] = row

# ---------------------------------------------------------------- candidate map
# object_id -> (package_key, gate_path, gate_sha, artifact_relpath)
candidate_geo = {}
package_pins = {}

def note_pkg(key):
    pdir = os.path.join(ODR, CANDIDATE_PACKAGES[key])
    gate = None
    for cand in ("05_results/LOCAL_CANDIDATE_GATE_V1.json",
                 "05_results/B601_RIGID_LINK_OPERATIONAL_PROXY_LOCAL_GATE_V1.json"):
        p = os.path.join(pdir, cand)
        if os.path.isfile(p):
            gate = p
            break
    if gate is None:
        hits = []
        res = os.path.join(pdir, "05_results")
        if os.path.isdir(res):
            hits = [f for f in os.listdir(res) if f.endswith("GATE_V1.json")]
        if hits:
            gate = os.path.join(res, sorted(hits)[0])
    package_pins[key] = {
        "package": os.path.relpath(pdir, ROOT).replace("\\", "/"),
        "gate_path": os.path.relpath(gate, ROOT).replace("\\", "/") if gate else None,
        "gate_sha256": sha256(gate) if gate else None,
    }
    return pdir

# Route-C batches: contract carries object_id -> output STEP
for key in ("R20_ROOT_STATIC", "LINK1_B6", "LINK2_B12"):
    pdir = note_pkg(key)
    cdir = os.path.join(pdir, "00_contract")
    contract = None
    for fn in os.listdir(cdir):
        if fn.endswith("CONTRACT_V1.json"):
            contract = jload(os.path.join(cdir, fn))
            break
    assert contract is not None, f"no contract in {key}"
    for o in contract["objects"]:
        step_rel = os.path.join("01_cad", o["output"])
        step_abs = os.path.join(pdir, step_rel)
        candidate_geo[o["object_id"]] = {
            "package": key,
            "geometry_type": "STEP_BREP_SINGLE_SOLID",
            "path": os.path.relpath(step_abs, ROOT).replace("\\", "/"),
            "sha256": sha256(step_abs),
            "frame": o.get("parent_frame"),
            "unit": "mm",
        }

# C9 analytic capsules: capsule index carries per-object entries
c9dir = note_pkg("C9_ANALYTIC")
c9idx = jload(os.path.join(c9dir, "05_results/C9_CAPSULE_INDEX_V1.json"))
c9_entries = c9idx.get("objects") or c9idx.get("entries") or []
c9_index_sha = sha256(os.path.join(c9dir, "05_results/C9_CAPSULE_INDEX_V1.json"))
if isinstance(c9_entries, dict):
    c9_items = list(c9_entries.items())
else:
    c9_items = [(e.get("object_id") or e.get("id"), e) for e in c9_entries]
for oid, entry in c9_items:
    if not oid:
        continue
    candidate_geo[oid] = {
        "package": "C9_ANALYTIC",
        "geometry_type": "ANALYTIC_CAPSULE_CHAIN_EFFECTIVE_RADIUS",
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/05_results/C9_CAPSULE_INDEX_V1.json",
        "sha256": c9_index_sha,
        "frame": (entry.get("host") or entry.get("parent_frame") if isinstance(entry, dict) else None),
        "unit": "mm",
    }

# Gripper 2P + fixed platform + rigid links: readiness ledger already lists the
# design assets; the candidate packages hold STEP-first re-emissions. Bind the
# package gate at object level via each package's contract if present.
for key in ("GRIPPER_2P", "FIXED_PLATFORM", "RIGID_LINKS"):
    pdir = note_pkg(key)
    cdir = os.path.join(pdir, "00_contract")
    contract = None
    if os.path.isdir(cdir):
        for fn in sorted(os.listdir(cdir)):
            if fn.endswith(".json") and "CONTRACT" in fn.upper():
                try:
                    c = jload(os.path.join(cdir, fn))
                except Exception:
                    continue
                if isinstance(c, dict) and "objects" in c:
                    contract = c
                    break
    ids = []
    if contract:
        for o in contract["objects"]:
            oid = o.get("object_id") or o.get("id")
            if oid:
                ids.append((oid, o))
    else:
        fallback = {
            "GRIPPER_2P": ["A::gripper_link", "A::gripper_left", "A::gripper_right"],
            "FIXED_PLATFORM": ["F::LOAD_BRIDGE", "F::M3R_STAGE_A", "F::M3R_STAGE_B"],
            "RIGID_LINKS": ["A::link1", "A::link2", "A::link3", "A::link4", "A::link5", "A::link6"],
        }
        ids = [(oid, {}) for oid in fallback[key]]
    for oid, o in ids:
        if oid in candidate_geo:
            continue
        candidate_geo[oid] = {
            "package": key,
            "geometry_type": "STEP_FIRST_LOCAL_CANDIDATE",
            "path": package_pins[key]["gate_path"],
            "sha256": package_pins[key]["gate_sha256"],
            "frame": o.get("parent_frame"),
            "unit": o.get("unit", "mm"),
        }

# ---------------------------------------------------------------- asset matrix
matrix_rows = []
tier_counter = Counter()
for o in objects:
    oid = o["object_id"]
    r = readiness.get(oid, {})
    cand = candidate_geo.get(oid)
    operational = r.get("operational_authority") == "true"
    if operational:
        tier = "SYSTEM_OPERATIONAL"
        src_path, src_sha = r.get("path", ""), r.get("hash", "")
        gtype = "OPERATIONAL_COLLISION_PROXY_NPZ"
        unit = r.get("units", "m")
        missing = ""
    elif cand:
        tier = "LOCAL_CANDIDATE_PASS_PENDING_OWNER_BINDING"
        src_path, src_sha = cand["path"], cand["sha256"]
        gtype = cand["geometry_type"]
        unit = cand["unit"]
        missing = "OWNER_SYSTEM_REGISTRY_REVISION_NOT_ISSUED"
    elif r.get("path"):
        tier = "DESIGN_ASSET_BOUND_NO_OPERATIONAL_PROMOTION"
        src_path, src_sha = r.get("path", ""), r.get("hash", "")
        gtype = "DESIGN_SOURCE_ASSET"
        unit = r.get("units", "")
        missing = r.get("blocker", "OPERATIONAL_NARROWPHASE_PROMOTION_ABSENT")
    else:
        tier = "MISSING_GEOMETRY_OR_AUTHORITY"
        src_path, src_sha, gtype, unit = "", "", "NONE", ""
        missing = r.get("blocker", "NO_SOURCE_ASSET_REGISTERED")
    tier_counter[tier] += 1
    matrix_rows.append({
        "object_id": oid,
        "logical_role": f"{o.get('category','?')}::{o.get('kind','?')}",
        "source_geometry_path": src_path,
        "source_sha256": src_sha,
        "geometry_type": gtype,
        "frame_id": o.get("parent_frame", ""),
        "frame_transform": o.get("pose_source", ""),
        "unit": unit,
        "operational_authority": tier,
        "candidate_package": cand["package"] if cand else "",
        "missing_reason": missing,
        "allowed_stages": o.get("active_when", ""),
    })

matrix_path = os.path.join(OUTDIR, "M01_OPERATIONAL_ASSET_MATRIX_V1.csv")
with open(matrix_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(matrix_rows[0].keys()))
    w.writeheader()
    for row in matrix_rows:
        w.writerow(row)

# ---------------------------------------------------------------- stage binding
def stage_universe_hash(stage_id, state_map):
    h = hashlib.sha256()
    h.update(stage_id.encode())
    for row in sorted(matrix_rows, key=lambda x: x["object_id"]):
        h.update(row["object_id"].encode())
        h.update((row["source_sha256"] or "NONE").encode())
    for k in sorted(state_map):
        h.update(f"{k}={state_map[k]}".encode())
    return h.hexdigest().upper()

ADJ = [
    ["A::base_link", "A::link1"], ["A::link1", "A::link2"], ["A::link2", "A::link3"],
    ["A::link3", "A::link4"], ["A::link4", "A::link5"], ["A::link5", "A::link6"],
    ["A::gripper_link", "A::link6"], ["A::gripper_left", "A::gripper_link"],
    ["A::gripper_link", "A::gripper_right"],
]

pre_state = {
    "gripper_joint1_m": 0.0, "gripper_joint2_m": 0.0,
    "solar_state": "SOLAR_STOWED",
    "solar_hdrm_state": "UNKNOWN_FAIL_CLOSED", "solar_latch_state": "UNKNOWN_FAIL_CLOSED",
    "arm_hdrm_state": "LOCKED", "target_present": False, "target_attached": False,
}
post_state = dict(pre_state)
post_state["arm_hdrm_state"] = "RELEASED"

def constant_stage(stage_id, state):
    uh = stage_universe_hash(stage_id, {k: str(v) for k, v in state.items()})
    bound = sum(1 for v in state.values() if v != "UNKNOWN_FAIL_CLOSED")
    return {
        "stage_id": stage_id,
        "kind": "CONSTANT_SCENE_EDGE",
        "instance_authority": "TAKEOVER_DIRECTIVE_CANDIDATE_BINDING__OWNER_RATIFIED_VALUES_FALSE",
        "values": state,
        "fields_candidate_bound": bound,
        "fields_total": len(state),
        "fields_unknown_fail_closed": [k for k, v in state.items() if v == "UNKNOWN_FAIL_CLOSED"],
        "active_objects": 150,
        "active_object_rule": "ALL_150_REGISTRY_OBJECTS__SOLAR_LEAVES_VIA_STOWED_SELECTOR__K_KEEPOUTS_NOT_ACTIVATED",
        "k_keepouts_activated": 0,
        "adjacent_exclusions": ADJ,
        "acm_rule": "REGISTRY_PAIR_POLICY_DEFAULT_FORBID__ADJ_01_09_ONLY_LEGAL_EXCLUSIONS",
        "manipulator_lock_state": state["arm_hdrm_state"],
        "route_c_state": "38_OF_121_R_OBJECTS_LOCAL_CANDIDATE__83_MISSING__C9_ANALYTIC_CANDIDATE",
        "g12_state": "FAIL_PENDING_RC4_READJUDICATION",
        "execution_mount_payload_sha256": "E20544EF880D1792EB3B616A4B74CBD635F130FC9AB5846C6A09E12EA6187B7D",
        "candidate_stage_universe_sha256": uh,
        "production_universe_hash_bound": False,
    }

stage_binding = dict(AUTH_HEADER)
stage_binding.update({
    "schema": "M01_STAGE_BINDING_V1",
    "binding_class": "CANDIDATE_STAGE_INSTANCES_UNDER_TAKEOVER_DIRECTIVE__NOT_PREBIND_GATE_OWNER_RATIFICATION",
    "prebind_gate_untouched": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json",
        "sha256": sha256(os.path.join(ODR, "ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json")),
        "its_stage_instances_bound_field_remains": "0_OF_3",
    },
    "value_source": "M01_SCENE_DECISION_INTAKE_V1.yaml candidate_suggestions block, promoted to DIRECTIVE-ORDERED candidate instances by the 2026-08-28 owner takeover directive section 5 ('Instantiate exactly three stage scenes'); solar_hdrm_state and solar_latch_state have no defined structured value anywhere and remain UNKNOWN_FAIL_CLOSED",
    "stages": [
        constant_stage("PRE_RELEASE_CONSTANT_SCENE", pre_state),
        {
            "stage_id": "RELEASE_EVENT_SCENE",
            "kind": "DISCRETE_EVENT_CONTRACT",
            "instance_authority": "TAKEOVER_DIRECTIVE_CANDIDATE_BINDING__OWNER_RATIFIED_VALUES_FALSE",
            "values": {
                "event_id": "ARM_HDRM_RELEASE_CANDIDATE_01",
                "event_time_or_ordering": "BETWEEN_PRE_AND_POST_CONSTANT_SCENES",
                "arm_hdrm_state_t0_minus": "LOCKED",
                "arm_hdrm_state_t0_plus": "RELEASED",
                "release_outcome": "RELEASED",
                "released_constraint_ids": "UNKNOWN_FAIL_CLOSED__ARM_HDRM_GEOMETRY_IN_MISSING_CATEGORY",
                "retained_constraint_ids": "UNKNOWN_FAIL_CLOSED__ARM_HDRM_GEOMETRY_IN_MISSING_CATEGORY",
                "failure_disposition": "UNKNOWN_ABORT",
            },
            "pre_scene_sha256": None,
            "post_scene_sha256": None,
            "note": "pre/post scene hashes are populated below after both constant stages are computed",
        },
        constant_stage("POST_RELEASE_CONSTANT_SCENE", post_state),
    ],
    "stage_instances_candidate_bound": 3,
    "stage_instances_production_bound": 0,
    "stage_instances_required": 3,
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
})
stage_binding["stages"][1]["pre_scene_sha256"] = stage_binding["stages"][0]["candidate_stage_universe_sha256"]
stage_binding["stages"][1]["post_scene_sha256"] = stage_binding["stages"][2]["candidate_stage_universe_sha256"]
jdump(stage_binding, os.path.join(OUTDIR, "M01_STAGE_BINDING_V1.json"))

# ---------------------------------------------------------------- pair policy
oids = sorted(o["object_id"] for o in objects)
adj_set = {tuple(sorted(p)) for p in ADJ}
tier_by_id = {row["object_id"]: row["operational_authority"] for row in matrix_rows}

def pair_state(a, b):
    ta, tb = tier_by_id[a], tier_by_id[b]
    if "MISSING" in ta or "MISSING" in tb:
        return "UNKNOWN_FAIL_CLOSED_MISSING_GEOMETRY"
    if ta == "SYSTEM_OPERATIONAL" and tb == "SYSTEM_OPERATIONAL":
        return "GEOMETRY_READY_QUERY_NOT_EXECUTED"
    if "DESIGN_ASSET" in ta or "DESIGN_ASSET" in tb:
        return "UNKNOWN_FAIL_CLOSED_DESIGN_ASSET_NOT_PROMOTED"
    return "CANDIDATE_GEOMETRY_READY_PENDING_OWNER_BINDING_QUERY_NOT_EXECUTED"

pair_path = os.path.join(OUTDIR, "M01_PAIR_POLICY_V1.csv")
counts = Counter()
n_pairs = 0
with open(pair_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["pair_id", "object_a", "object_b", "in_required_universe",
                "exclusion_rule", "policy_state", "required_clearance_mm", "verdict"])
    pid = 0
    for i in range(len(oids)):
        for j in range(i + 1, len(oids)):
            a, b = oids[i], oids[j]
            pid += 1
            key = tuple(sorted((a, b)))
            if key in adj_set:
                rule = "ADJ-%02d" % (sorted(adj_set).index(key) + 1)
                w.writerow([pid, a, b, "false", rule, "EXCLUDED_ADJACENT_JOINT", "", "EXCLUDED"])
                counts["EXCLUDED_ADJACENT_JOINT"] += 1
            else:
                st = pair_state(a, b)
                w.writerow([pid, a, b, "true", "", st, "NULL_OWNER_CLEARANCE_POLICY_NOT_ISSUED", "UNKNOWN"])
                counts[st] += 1
                n_pairs += 1

# ---------------------------------------------------------------- motion certificates
mc = dict(AUTH_HEADER)
precert_gate = os.path.join(ODR, "ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1/M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_GATE_V1.json")
batch_gate = os.path.join(ODR, "ODR60_OPTION_A_M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_V1/M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_GATE_V1.json")
mc.update({
    "schema": "M01_MOTION_CERTIFICATES_V1",
    "system_level_certificates": {
        "count": 1,
        "entries": [{
            "object_id": "A::base_link",
            "class": "GLOBAL_ZERO_MOTION",
            "source_gate": os.path.relpath(precert_gate, ROOT).replace("\\", "/"),
            "source_sha256": sha256(precert_gate),
        }],
    },
    "design_level_screening_bounds": {
        "count": 9,
        "scope": "NONBASE_B601_A_OBJECTS_FULL_Q_DOMAIN_RIGID_KINEMATIC_BOUNDS__NONOPERATIONAL",
        "source_gate": os.path.relpath(batch_gate, ROOT).replace("\\", "/"),
        "source_sha256": sha256(batch_gate),
    },
    "host_fixed_r_objects": {
        "rule": "HOST_FIXED_UNLESS_REGISTERED_OTHERWISE",
        "count_with_candidate_geometry": sum(1 for row in matrix_rows if row["object_id"].startswith("R::") and row["candidate_package"]),
        "motion_certificate_state": "REQUIRES_HOST_FRAME_ADAPTER_PER_BATCH__LINK1_JOINT1_AND_LINK2_JOINT1_JOINT2_ADAPTERS_LOCALLY_VALIDATED_IN_THEIR_PACKAGES__NOT_SYSTEM_PROMOTED",
    },
    "remaining_uncertified_objects": 149,
    "certificates_required_for_path_search": 150,
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
})
jdump(mc, os.path.join(OUTDIR, "M01_MOTION_CERTIFICATES_V1.json"))

# ---------------------------------------------------------------- pair oracle binding record
oracle_gate = os.path.join(ODR, "ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1/M01_SYSTEM_PAIR_ORACLE_BACKEND_GATE_V1.json")
po = dict(AUTH_HEADER)
po.update({
    "schema": "M01_PAIR_ORACLE_V1",
    "backend": {
        "package": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1",
        "gate_path": os.path.relpath(oracle_gate, ROOT).replace("\\", "/"),
        "gate_sha256": sha256(oracle_gate) if os.path.isfile(oracle_gate) else None,
        "validated_scope": "SYNTHETIC_HASH_BOUND_BREP_BOXES_ONLY__25_OF_25_CHECKS__ZERO_SYSTEM_QUERIES",
    },
    "binding_state": "ORACLE_IMPLEMENTED_AND_LOCALLY_VALIDATED__NOT_BOUND_TO_SYSTEM_UNIVERSE",
    "missing_inputs_for_execution": [
        "OWNER_CLEARANCE_POLICY_11166_ROWS_NOT_ISSUED",
        "OWNER_SYSTEM_REGISTRY_REVISION_NOT_ISSUED_FOR_59_LOCAL_CANDIDATES",
        "PRODUCTION_STAGE_UNIVERSE_HASHES_NOT_RATIFIED",
        "83_ROUTE_C_R_OBJECTS_AND_7_MISSING_CATEGORIES_HAVE_NO_GEOMETRY",
        "MIXED_REPRESENTATION_NARROWPHASE_ADMISSION_RULES_NOT_ISSUED (BRep STEP vs NPZ mesh vs analytic capsule vs FCStd state container)",
    ],
    "pair_queries_executed": 0,
    "pair_queries_required": 11166,
    "safe_pairs_certified": 0,
    "unknown_to_allow_conversions": 0,
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
})
jdump(po, os.path.join(OUTDIR, "M01_PAIR_ORACLE_V1.json"))

# ---------------------------------------------------------------- edge + path gates
edge = dict(AUTH_HEADER)
edge.update({
    "schema": "M01_CONTINUOUS_EDGE_GATE_V1",
    "verdict": "NO_EDGE_EVALUATED__PREREQUISITES_FAIL_CLOSED",
    "edges_certified": 0,
    "blocking_inputs": [
        "PAIR_ORACLE_NOT_BOUND_TO_SYSTEM_UNIVERSE",
        "CLEARANCE_POLICY_0_OF_11166",
        "MOTION_CERTIFICATES_1_OF_150",
        "STAGE_INSTANCES_CANDIDATE_ONLY_NOT_PRODUCTION_RATIFIED",
    ],
    "continuous_q_contract": {
        "fixed_start_name": "STOW",
        "fixed_goal_name": "RELEASE_CLEAR",
        "q_start_rad": [2.540711, -2.932153, -0.994838, -0.718081, -0.365716, -0.05236],
        "q_goal_rad": [-1.570796, -2.094395, -2.094395, -1.047198, -0.523599, 0.0],
        "source": "M01_THREE_STAGE_SCENE_SCHEMA_V2.json schema_contract.continuous_q_contract",
    },
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
})
jdump(edge, os.path.join(OUTDIR, "M01_CONTINUOUS_EDGE_GATE_V1.json"))

path_gate = dict(AUTH_HEADER)
path_gate.update({
    "schema": "M01_BOUNDED_PATH_GATE_V1",
    "verdict": "PATH_SEARCH_NOT_AUTHORIZED_NOT_EXECUTED__PREREQUISITES_ENUMERATED",
    "path_search_authorized": False,
    "path_search_executed": False,
    "path_exists": "UNKNOWN_NOT_EVALUATED",
    "no_path_is_a_valid_result": True,
    "prerequisites": {
        "operational_assets": f"{tier_counter['SYSTEM_OPERATIONAL']}/150 system, {tier_counter['LOCAL_CANDIDATE_PASS_PENDING_OWNER_BINDING']}/150 candidate-pending",
        "stage_bindings": "3/3 candidate, 0/3 production-ratified",
        "clearance_policy": "0/11166",
        "motion_certificates": "1/150",
        "pair_oracle": "implemented, unbound",
    },
    "historical_negative_preserved": {
        "v9f_straight_q_witness_mm": -17.313396996697108,
        "status": "HISTORICAL_NEGATIVE_ON_OLD_M01_STRAIGHT_Q_PATH__NOT_CURRENT_GEOMETRY_EVIDENCE",
    },
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
})
jdump(path_gate, os.path.join(OUTDIR, "M01_BOUNDED_PATH_GATE_V1.json"))

summary = {
    "asset_matrix_rows": len(matrix_rows),
    "tiers": dict(tier_counter),
    "pair_rows_total": n_pairs + counts["EXCLUDED_ADJACENT_JOINT"],
    "pair_required_universe": n_pairs,
    "pair_states": dict(counts),
    "stage_instances_candidate_bound": 3,
    "outputs": sorted(os.listdir(OUTDIR)),
}
print(json.dumps(summary, indent=1))
assert n_pairs == 11166, f"required pair universe {n_pairs} != 11166"
