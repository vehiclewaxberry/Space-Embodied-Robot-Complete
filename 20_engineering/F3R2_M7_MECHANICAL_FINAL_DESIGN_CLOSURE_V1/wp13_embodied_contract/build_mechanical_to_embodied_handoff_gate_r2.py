#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M7 / WP13 - MECHANICAL_TO_EMBODIED_HANDOFF_GATE_R2 builder     (ODR-16 + ECR-SOLAR-ARRAY-R2)

R2 rerun of the machine-check handoff gate against the R2 binding documents
(EMBODIED_MECHANICAL_CONTRACT_R2.yaml + MECH_DYNAMICS_INTERFACE_V5_R2.yaml +
WP2 SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml).  The 11 checks are IDENTICAL
in logic to the frozen V1 gate builder; only the document paths are repointed.
The frozen V1 gate (builder + JSON) is not modified by this script.

Discipline (identical to the contract builder):
* every number in the output JSON is recomputed from the source files at run
  time - nothing is hand-transcribed;
* sources are pinned by sha256 (first 16 hex chars reported as evidence);
* UNKNOWN is never PASS: any file that cannot be loaded, or any quantity that
  cannot be computed, turns its check into FAIL with a stated reason, and the
  overall verdict can then never be PASS.
"""

import datetime
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET

import yaml

PROJECT_ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
M7_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
M7_ROOT = os.path.join(PROJECT_ROOT, M7_REL.replace("/", os.sep))
OUT_DIR = os.path.join(M7_ROOT, "wp13_embodied_contract")
OUT_PATH = os.path.join(OUT_DIR, "MECHANICAL_TO_EMBODIED_HANDOFF_GATE_R2.json")
TZ8 = datetime.timezone(datetime.timedelta(hours=8))

CONTRACT_REL = f"{M7_REL}/wp13_embodied_contract/EMBODIED_MECHANICAL_CONTRACT_R2.yaml"
V4_REL = f"{M7_REL}/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V5_R2.yaml"
URDF_REL = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
MASS_REL = f"{M7_REL}/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
CALIB_REL = f"{M7_REL}/wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml"

CONTRACT_SECTIONS = ("kinematics", "dynamics", "collision", "grasp", "flexibility", "failure_states")
ENVELOPE_FIELDS = ("source", "authority_level", "confidence", "nominal", "uncertainty",
                   "calibration_required")
REQUIRED_FAILURE_STATES = ("LEFT_PANEL_FAIL", "RIGHT_PANEL_FAIL", "BOTH_PANEL_FAIL",
                           "GRIPPER_JAM", "CONTACT_ABORT", "JOINT_LIMIT",
                           "ARM_EMERGENCY_STOP")
ARM_REVOLUTE_JOINTS = ("joint1", "joint2", "joint3", "joint4", "joint5", "joint6")


# ---------------------------------------------------------------------------
# IO helpers (long-path safe, everything read as bytes then decoded)
# ---------------------------------------------------------------------------
def longpath(p):
    p = os.path.abspath(p)
    return "\\\\?\\" + p if os.name == "nt" and not p.startswith("\\\\?\\") else p


def apath(rel):
    return os.path.join(PROJECT_ROOT, rel.replace("/", os.sep))


def read_bytes(rel):
    with open(longpath(apath(rel)), "rb") as fh:
        return fh.read()


def sha256_hex(rel):
    return hashlib.sha256(read_bytes(rel)).hexdigest().upper()


def load_yaml(rel):
    return yaml.safe_load(read_bytes(rel).decode("utf-8"))


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ---------------------------------------------------------------------------
# Check implementations.  Each returns (pass_bool, evidence_dict).
# Any exception is caught by the runner and converted to FAIL (unknown != pass)
# ---------------------------------------------------------------------------
def check_asset_hashes_matched(contract, **_):
    reg = contract.get("source_register")
    if not isinstance(reg, list) or not reg:
        return False, {"reason": "contract source_register missing or empty"}
    entries = []
    mismatches = []
    zero_byte = []
    missing = []
    for e in reg:
        rel = e.get("path")
        rec = {"role": e.get("role"), "path": rel,
               "declared_sha256_16": str(e.get("sha256", ""))[:16],
               "declared_bytes": e.get("bytes")}
        try:
            actual = sha256_hex(rel)
            size = os.path.getsize(longpath(apath(rel)))
            rec["actual_sha256_16"] = actual[:16]
            rec["actual_bytes"] = size
            rec["hash_match"] = (actual == str(e.get("sha256", "")).upper())
            rec["bytes_match"] = (size == e.get("bytes"))
            rec["non_zero"] = size > 0
            if not rec["hash_match"]:
                mismatches.append(rel)
            if not rec["non_zero"]:
                zero_byte.append(rel)
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
            missing.append(rel)
        entries.append(rec)
    ok = not mismatches and not zero_byte and not missing
    return ok, {
        "files_in_register": len(reg),
        "files_hash_matched": sum(1 for r in entries if r.get("hash_match")),
        "hash_mismatches": mismatches,
        "zero_byte_files": zero_byte,
        "unreadable_files": missing,
        "entries": entries,
    }


def check_frame_tree_matched(contract, v4, urdf_root, **_):
    ev = {}
    problems = []

    # --- M frame (ODR-01): V4 declaration ---
    m_def = v4["frame_authority"]["m_frame_definition"]
    t_sm = [float(x) for x in m_def["t_sm_mm"]]
    rot = m_def["rotation"]
    ev["v4_m_frame"] = {"t_sm_mm": t_sm, "rotation": rot,
                        "chain_text": m_def.get("chain")}
    if not (len(t_sm) == 3 and abs(t_sm[0] - 185.25) < 1e-9
            and abs(t_sm[1]) < 1e-12 and abs(t_sm[2]) < 1e-12):
        problems.append(f"V4 t_sm_mm {t_sm} != [185.25, 0, 0] per ODR-01")
    if rot != "RY_PLUS_90_DEG":
        problems.append(f"V4 rotation {rot!r} != RY_PLUS_90_DEG per ODR-01")

    # --- same M frame carried by the contract (consistency V4 <-> contract) ---
    c_frame = contract["dynamics"]["mounting"]["M3R"]["dynamics_frame"]
    c_nom = c_frame["nominal"]
    c_t = [float(x) for x in c_nom["T_SM_mm"]]
    c_rot = c_nom["rotation"]
    ev["contract_m_frame"] = {"T_SM_mm": c_t, "rotation": c_rot,
                              "authority_level": c_frame.get("authority_level")}
    if c_t != t_sm or c_rot != rot:
        problems.append(f"contract M frame {c_t}/{c_rot} inconsistent with V4 {t_sm}/{rot}")

    # --- V4 explicitly forbids the geometric feature stack as a dynamics frame
    stack = v4["frame_authority"].get("physical_feature_stack", {}).get("stations_mm", {})
    ev["v4_physical_feature_stack_mm"] = stack
    ev["v4_stack_rule"] = v4["frame_authority"].get("physical_feature_stack", {}).get("rule")

    # --- ROOT/BUS anchor: the S frame both sides of the interface ---
    s_v4 = v4["design_mass_model_binding"]["reference_frame"]
    s_contract = contract["dynamics"]["configurations"]["C01"]["center_of_mass"]["reference_frame"]
    ev["root_bus_frame"] = {"v4_reference_frame": s_v4,
                            "contract_reference_frame": s_contract}
    if s_v4 != s_contract:
        problems.append(f"ROOT/BUS reference frame mismatch: V4 {s_v4!r} vs contract {s_contract!r}")

    # --- B601 -> EE segment: URDF tree is a single chain rooted at base_link,
    #     and the contract grasp (EE) frame is the URDF gripper_joint frame ---
    links = [l.get("name") for l in urdf_root.findall("link")]
    joints = urdf_root.findall("joint")
    child_of = {}
    for j in joints:
        child_of[j.find("child").get("link")] = j.find("parent").get("link")
    roots = [l for l in links if l not in child_of]
    ev["urdf_tree"] = {"links": len(links), "root_links": roots}
    if roots != ["base_link"]:
        problems.append(f"URDF root links {roots} != ['base_link']")
    # walk EE (gripper_link) back to base_link
    chain = []
    node = "gripper_link"
    while node in child_of:
        chain.append(node)
        node = child_of[node]
    chain.append(node)
    ev["ee_to_root_chain"] = list(reversed(chain))
    if node != "base_link":
        problems.append(f"EE grasp frame does not reach base_link; stopped at {node!r}")

    gf = contract["grasp"]["frames"]["grasp_frame"]
    gj = next((j for j in joints if j.get("name") == "gripper_joint"), None)
    gj_o = [float(x) for x in gj.find("origin").get("xyz").split()]
    gj_r = [float(x) for x in gj.find("origin").get("rpy").split()]
    ev["grasp_frame_vs_urdf"] = {
        "contract_origin_xyz_m": gf["origin_xyz_m"], "urdf_origin_xyz_m": gj_o,
        "contract_origin_rpy_rad": gf["origin_rpy_rad"], "urdf_origin_rpy_rad": gj_r,
        "contract_parent": gf["parent"],
        "urdf_parent": gj.find("parent").get("link"),
    }
    if (gf["parent"] != gj.find("parent").get("link")
            or [float(x) for x in gf["origin_xyz_m"]] != gj_o
            or [float(x) for x in gf["origin_rpy_rad"]] != gj_r):
        problems.append("contract grasp_frame does not match URDF gripper_joint frame")

    ev["frame_chain_verified"] = "ROOT(S/spacecraft_assembly_frame)->BUS(M3R)->M(T_SM per ODR-01)->B601(base_link)->EE(gripper_link grasp_frame)"
    ev["problems"] = problems
    return not problems, ev


def check_urdf_topology_matched(contract, urdf_root, **_):
    links = urdf_root.findall("link")
    joints = urdf_root.findall("joint")
    by_type = {}
    for j in joints:
        by_type[j.get("type")] = by_type.get(j.get("type"), 0) + 1
    live = {"links": len(links), "joints": len(joints),
            "revolute": by_type.get("revolute", 0), "fixed": by_type.get("fixed", 0),
            "prismatic": by_type.get("prismatic", 0)}
    declared = {k: contract["kinematics"]["topology"][k]
                for k in ("links", "joints", "revolute", "fixed", "prismatic")}
    problems = []
    if live != declared:
        problems.append(f"topology counts differ: live {live} vs contract {declared}")

    c_joints = contract["kinematics"]["joints"]
    live_names = [j.get("name") for j in joints]
    if set(live_names) != set(c_joints.keys()):
        problems.append(f"joint name sets differ: live-only {set(live_names) - set(c_joints)}, "
                        f"contract-only {set(c_joints) - set(live_names)}")
    per_joint = {}
    for j in joints:
        name = j.get("name")
        cj = c_joints.get(name, {})
        rec = {
            "type_live": j.get("type"), "type_contract": cj.get("type"),
            "parent_live": j.find("parent").get("link"), "parent_contract": cj.get("parent"),
            "child_live": j.find("child").get("link"), "child_contract": cj.get("child"),
        }
        rec["match"] = (rec["type_live"] == rec["type_contract"]
                        and rec["parent_live"] == rec["parent_contract"]
                        and rec["child_live"] == rec["child_contract"])
        if not rec["match"]:
            problems.append(f"joint {name}: {rec}")
        per_joint[name] = rec
    return not problems, {
        "live_counts": live, "contract_counts": declared,
        "joints_compared": len(per_joint),
        "joints_matched": sum(1 for r in per_joint.values() if r["match"]),
        "per_joint": per_joint, "problems": problems,
    }


def check_design_mass_model_loadable(**_):
    doc = load_yaml(MASS_REL)
    cfgs = doc.get("configurations", [])
    problems = []
    per_cfg = {}
    if len(cfgs) != 9:
        problems.append(f"expected 9 configurations, loaded {len(cfgs)}")
    for c in cfgs:
        cid = c.get("configuration_id")
        issues = []
        m = c.get("mass", {})
        if not is_num(m.get("value_kg")):
            issues.append("mass.value_kg not numeric")
        if not (is_num(m.get("standard_uncertainty_kg")) and m["standard_uncertainty_kg"] >= 0):
            issues.append("mass.standard_uncertainty_kg missing/negative")
        cm = c.get("center_of_mass", {})
        xyz = cm.get("xyz_m")
        if not (isinstance(xyz, list) and len(xyz) == 3 and all(is_num(v) for v in xyz)):
            issues.append("center_of_mass.xyz_m not 3 numerics")
        suc = cm.get("standard_uncertainty_xyz_m")
        if not (isinstance(suc, list) and len(suc) == 3
                and all(is_num(v) and v >= 0 for v in suc)):
            issues.append("center_of_mass.standard_uncertainty_xyz_m missing/negative")
        inr = c.get("inertia", {})
        comp = inr.get("components_kg_m2", {})
        need = ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")
        if not all(is_num(comp.get(k)) for k in need):
            issues.append("inertia.components_kg_m2 incomplete")
        # ODR-07 semantics: reported per-component standard uncertainties must
        # be non-negative (sigma_i = sqrt(C[i,i]))
        sig = inr.get("standard_uncertainty_components_kg_m2", {})
        neg = {k: sig.get(k) for k in need
               if not (is_num(sig.get(k)) and sig.get(k) >= 0)}
        if neg:
            issues.append(f"negative/missing reported component sigma (ODR-07): {neg}")
        per_cfg[cid] = {
            "name": c.get("name"),
            "mass_kg": m.get("value_kg"),
            "mass_sigma_kg": m.get("standard_uncertainty_kg"),
            "min_reported_inertia_sigma": min((sig.get(k) for k in need
                                               if is_num(sig.get(k))), default=None),
            "issues": issues,
        }
        problems.extend(f"{cid}: {i}" for i in issues)
    return not problems, {
        "source": MASS_REL, "source_sha256_16": sha256_hex(MASS_REL)[:16],
        "configurations_loaded": len(cfgs),
        "configuration_ids": [c.get("configuration_id") for c in cfgs],
        "per_configuration": per_cfg, "problems": problems,
    }


def check_collision_meshes_loadable(contract, urdf_root, **_):
    urdf_dir = os.path.dirname(apath(URDF_REL))
    meshes = {}
    for l in urdf_root.findall("link"):
        for kind in ("visual", "collision"):
            m = l.find(f"{kind}/geometry/mesh")
            if m is not None:
                meshes.setdefault(m.get("filename"), set()).add(f"{l.get('name')}:{kind}")
    problems = []
    entries = {}
    for fn in sorted(meshes):
        p = os.path.join(urdf_dir, fn.replace("/", os.sep))
        rec = {"referenced_by": sorted(meshes[fn])}
        try:
            size = os.path.getsize(longpath(p))
            rec["bytes"] = size
            rec["non_zero"] = size > 0
            if size == 0:
                problems.append(f"{fn}: zero bytes")
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
            problems.append(f"{fn}: not loadable ({exc})")
        entries[fn] = rec
    phantom = contract["collision"].get("CRITICAL_phantom_base_plate", {})
    phantom_status = phantom.get("status")
    if phantom_status != "OPEN_DECLARED":
        problems.append(f"WP11-F-01 phantom base plate not DECLARED OPEN in contract "
                        f"(collision.CRITICAL_phantom_base_plate.status = {phantom_status!r})")
    return not problems, {
        "unique_mesh_files_referenced": len(entries),
        "meshes": entries,
        "declared_open_item_WP11_F_01": {
            "finding": phantom.get("finding"),
            "status": phantom_status,
            "trigger": phantom.get("trigger"),
            "note": "declared open item, reported not hidden: loadability of the "
                    "on-disk meshes is checked above; the phantom base plate "
                    "content of base_link.STL is a declared OPEN item pending "
                    "re-export through D_i",
        },
        "problems": problems,
    }


def check_accepted_configurations_loadable(urdf_root, **_):
    calib = load_yaml(CALIB_REL)
    voc = calib.get("validated_over_configurations")
    if not isinstance(voc, dict) or not voc:
        return False, {"reason": "validated_over_configurations missing/empty in calibration file"}
    # live URDF limits for the 6 arm revolute joints
    limits = {}
    for j in urdf_root.findall("joint"):
        if j.get("name") in ARM_REVOLUTE_JOINTS:
            lim = j.find("limit")
            limits[j.get("name")] = (float(lim.get("lower")), float(lim.get("upper")))
    if set(limits) != set(ARM_REVOLUTE_JOINTS):
        return False, {"reason": f"URDF revolute limits incomplete: {sorted(limits)}"}
    problems = []
    per_cfg = {}
    for name, entry in voc.items():
        q = entry.get("q_rad")
        issues = []
        if not (isinstance(q, list) and len(q) == 6 and all(is_num(v) for v in q)):
            issues.append(f"q_rad not 6 numerics: {q!r}")
        else:
            for i, jn in enumerate(ARM_REVOLUTE_JOINTS):
                lo, hi = limits[jn]
                if not (lo - 1e-9 <= q[i] <= hi + 1e-9):
                    issues.append(f"q_rad[{i}]={q[i]} outside {jn} limits [{lo}, {hi}]")
        per_cfg[name] = {"q_rad_len": len(q) if isinstance(q, list) else None,
                         "inside_joint_limits_recomputed": not issues,
                         "declared_inside_joint_limits": entry.get("inside_joint_limits"),
                         "issues": issues}
        problems.extend(f"{name}: {i}" for i in issues)
    return not problems, {
        "source": CALIB_REL, "source_sha256_16": sha256_hex(CALIB_REL)[:16],
        "configurations_loaded": len(voc),
        "configuration_names": sorted(voc),
        "urdf_limits_used_rad": {k: list(v) for k, v in limits.items()},
        "per_configuration": per_cfg, "problems": problems,
    }


def check_failure_states_enumerable(contract, **_):
    fs = contract.get("failure_states", {})
    present = [s for s in REQUIRED_FAILURE_STATES if s in fs]
    missing = [s for s in REQUIRED_FAILURE_STATES if s not in fs]
    return not missing, {
        "required_states": list(REQUIRED_FAILURE_STATES),
        "present": present, "missing": missing,
        "all_keys_in_section": sorted(k for k in fs if not k.startswith("_")),
    }


def check_grasp_frames_defined(contract, **_):
    frames = contract["grasp"].get("frames", {})
    problems = []
    ev = {}
    gf = frames.get("grasp_frame")
    if gf is None:
        problems.append("grasp.frames.grasp_frame missing")
    else:
        o = gf.get("origin_xyz_m")
        r = gf.get("origin_rpy_rad")
        ev["grasp_frame"] = {"origin_xyz_m": o, "origin_rpy_rad": r,
                             "authority_level": gf.get("authority_level")}
        if not (isinstance(o, list) and len(o) == 3 and all(is_num(v) for v in o)):
            problems.append("grasp_frame.origin_xyz_m not 3 numerics")
        if not (isinstance(r, list) and len(r) == 3 and all(is_num(v) for v in r)):
            problems.append("grasp_frame.origin_rpy_rad not 3 numerics")
    for side in ("contact_left", "contact_right"):
        cf = frames.get(side)
        if cf is None:
            problems.append(f"grasp.frames.{side} missing")
            continue
        st = cf.get("status")
        ev[side] = {"definition": cf.get("definition"), "status": st,
                    "contact_patch_geometry": cf.get("contact_patch_geometry")}
        # HOLD status acceptable only when explicitly declared (fail-closed),
        # i.e. status present and names the HOLD; a silent null/absent status
        # would hide the unknown
        if not (isinstance(st, str) and st.startswith("HOLD")):
            problems.append(f"{side}.status {st!r} is not an explicitly declared HOLD")
    return not problems, {"frames": ev, "problems": problems,
                          "note": "definitional presence + fail-closed declaration checked; "
                                  "measurement completeness is NOT required by this gate"}


def check_flex_interface_defined(contract, **_):
    flex = contract.get("flexibility", {})
    sp = flex.get("solar_panel", {})
    problems = []
    mc = sp.get("mode_count")
    ev_mc = None
    if not (isinstance(mc, dict) and is_num(mc.get("nominal")) and mc.get("authority_level")):
        problems.append("solar_panel.mode_count missing nominal/authority")
    else:
        ev_mc = {"nominal": mc["nominal"], "authority_level": mc["authority_level"]}
    fq = sp.get("frequency_hz")
    ev_fq = None
    env = fq.get("uncertainty", {}).get("envelope_hz") if isinstance(fq, dict) else None
    if not (isinstance(fq, dict) and is_num(fq.get("nominal"))
            and isinstance(env, list) and len(env) == 2 and all(is_num(v) for v in env)):
        problems.append("solar_panel.frequency_hz missing nominal or uncertainty.envelope_hz")
    else:
        ev_fq = {"nominal": fq["nominal"], "envelope_hz": env,
                 "authority_level": fq.get("authority_level")}
    dz = sp.get("damping_zeta")
    ev_dz = None
    if not isinstance(dz, dict):
        problems.append("solar_panel.damping_zeta entry missing")
    else:
        ev_dz = {"authority_level": dz.get("authority_level"),
                 "nominal": dz.get("nominal"),
                 "finding": dz.get("CONTRACT_FINDING")}
        if not dz.get("authority_level"):
            problems.append("damping_zeta carries no declared authority_level")
    hinge = flex.get("hinge")
    ev_hinge = None
    if not isinstance(hinge, dict) or not hinge:
        problems.append("flexibility.hinge missing")
    else:
        ev_hinge = {"entries": sorted(hinge.keys()),
                    "authorities": {k: v.get("authority_level") for k, v in hinge.items()
                                    if isinstance(v, dict) and "authority_level" in v}}
    return not problems, {
        "mode_count": ev_mc, "frequency_hz": ev_fq, "damping_zeta": ev_dz,
        "hinge": ev_hinge, "problems": problems,
        "note": "PROVISIONAL / HOLD authority classes are acceptable when explicitly "
                "declared; this gate checks definitional machine-readability only",
    }


def check_uncertainty_fields_machine_readable(contract, **_):
    # Contract's own envelope discriminator (identical to the builder/ledger):
    # a dict holding BOTH 'nominal' and 'authority_level' is a quantity envelope
    envelopes = []
    bare_nominal_dicts = []

    def sweep(node, path=""):
        if isinstance(node, dict):
            if "nominal" in node and "authority_level" in node:
                envelopes.append((path.lstrip("."), node))
            elif "nominal" in node:
                bare_nominal_dicts.append(path.lstrip("."))
            for k, v in node.items():
                sweep(v, path + "." + str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                sweep(v, f"{path}[{i}]")

    for sec in CONTRACT_SECTIONS:
        sweep(contract.get(sec), sec)

    incomplete = []
    for path, node in envelopes:
        missing = [f for f in ENVELOPE_FIELDS if f not in node]
        if missing:
            incomplete.append({"quantity": path, "missing_fields": missing,
                               "authority_level": node.get("authority_level")})

    au = contract.get("authority_and_uncertainty", {})
    ledger = au.get("ledger", [])
    ledger_paths = sorted(e.get("quantity") for e in ledger)
    envelope_paths = sorted(p for p, _ in envelopes)
    count_consistent = (len(envelopes) == len(ledger) == au.get("quantity_count"))
    paths_consistent = (envelope_paths == ledger_paths)

    problems = []
    if incomplete:
        problems.append(f"{len(incomplete)} envelope(s) lack required ODR-15 fields")
    if not count_consistent:
        problems.append(f"envelope count {len(envelopes)} != ledger {len(ledger)} "
                        f"!= quantity_count {au.get('quantity_count')}")
    if not paths_consistent:
        problems.append("ledger quantity paths do not match walked envelope paths")

    return not problems, {
        "envelopes_walked": len(envelopes),
        "ledger_entries": len(ledger),
        "declared_quantity_count": au.get("quantity_count"),
        "count_consistent_with_ledger": count_consistent,
        "paths_consistent_with_ledger": paths_consistent,
        "required_fields_per_envelope": list(ENVELOPE_FIELDS),
        "incomplete_envelopes": incomplete,
        "bare_nominal_dicts_excluded": {
            "paths": bare_nominal_dicts,
            "note": "dicts holding a 'nominal' KEY but no 'authority_level' are not "
                    "quantity envelopes under the contract's own discriminator "
                    "(e.g. flexibility.solar_panel.frequency_hz.uncertainty.cases, "
                    "where 'nominal' is a case LABEL). Excluded from the field check, "
                    "reported for transparency.",
        },
        "problems": problems,
    }


def check_unknown_remains_fail_closed(contract, **_):
    problems = []
    cc_flag = contract.get("consumer_contract", {}).get("unknown_is_fail_closed")
    gs_flag = contract.get("grasp", {}).get("states", {}).get("unknown_is_fail_closed")
    if cc_flag is not True:
        problems.append(f"consumer_contract.unknown_is_fail_closed = {cc_flag!r}")
    if gs_flag is not True:
        problems.append(f"grasp.states.unknown_is_fail_closed = {gs_flag!r}")

    au = contract.get("authority_and_uncertainty", {})
    ledger = au.get("ledger", [])
    nulls = [e for e in ledger if e.get("nominal_is_null")]
    if not (len(nulls) > 0):
        problems.append("ledger contains zero null-nominal entries; the fail-closed "
                        "discipline is untestable / suspiciously absent")
    if len(nulls) != au.get("null_nominal_count"):
        problems.append(f"recomputed null_nominal_count {len(nulls)} != declared "
                        f"{au.get('null_nominal_count')}")

    # Every null-nominal entry must carry an authority class that disclaims
    # knowledge (HOLD/PROVISIONAL family) - never a class implying the value
    # is known (accepted/measured/derived/model).
    knowledge_free = []
    knowledge_implying = []
    for e in nulls:
        al = str(e.get("authority_level") or "")
        if ("HOLD" in al) or ("PROVISIONAL" in al):
            knowledge_free.append(e["quantity"])
        else:
            knowledge_implying.append({"quantity": e["quantity"], "authority_level": al})
    if knowledge_implying:
        problems.append(f"{len(knowledge_implying)} null-nominal ledger entr(y/ies) carry "
                        f"a non-HOLD/PROVISIONAL authority class")

    return not problems, {
        "consumer_contract_unknown_is_fail_closed": cc_flag,
        "grasp_states_unknown_is_fail_closed": gs_flag,
        "null_nominal_entries_recomputed": len(nulls),
        "null_nominal_count_declared": au.get("null_nominal_count"),
        "null_nominals_with_fail_closed_authority": knowledge_free,
        "null_nominals_with_knowledge_implying_authority": knowledge_implying,
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def main():
    os.makedirs(longpath(OUT_DIR), exist_ok=True)

    # Load shared inputs once; a load failure here is reported inside every
    # check that needed the input (UNKNOWN is never PASS).
    load_errors = {}
    contract = v4 = None
    urdf_root = None
    try:
        contract = load_yaml(CONTRACT_REL)
    except Exception as exc:
        load_errors["contract"] = f"{type(exc).__name__}: {exc}"
    try:
        v4 = load_yaml(V4_REL)
    except Exception as exc:
        load_errors["v4"] = f"{type(exc).__name__}: {exc}"
    try:
        urdf_root = ET.fromstring(read_bytes(URDF_REL).decode("utf-8"))
    except Exception as exc:
        load_errors["urdf"] = f"{type(exc).__name__}: {exc}"

    shared = {"contract": contract, "v4": v4, "urdf_root": urdf_root}
    pins = {}
    for name, rel in (("contract", CONTRACT_REL), ("v4", V4_REL), ("urdf", URDF_REL),
                      ("mass_model", MASS_REL), ("calibration", CALIB_REL)):
        try:
            pins[name] = {"path": rel, "sha256_16": sha256_hex(rel)[:16]}
        except Exception as exc:
            pins[name] = {"path": rel, "error": f"{type(exc).__name__}: {exc}"}

    checks_spec = [
        ("asset_hashes_matched", check_asset_hashes_matched, ("contract",)),
        ("frame_tree_matched", check_frame_tree_matched, ("contract", "v4", "urdf_root")),
        ("urdf_topology_matched", check_urdf_topology_matched, ("contract", "urdf_root")),
        ("design_mass_model_loadable", check_design_mass_model_loadable, ()),
        ("collision_meshes_loadable", check_collision_meshes_loadable, ("contract", "urdf_root")),
        ("accepted_configurations_loadable", check_accepted_configurations_loadable, ("urdf_root",)),
        ("failure_states_enumerable", check_failure_states_enumerable, ("contract",)),
        ("grasp_frames_defined", check_grasp_frames_defined, ("contract",)),
        ("flex_interface_defined", check_flex_interface_defined, ("contract",)),
        ("uncertainty_fields_machine_readable", check_uncertainty_fields_machine_readable, ("contract",)),
        ("unknown_remains_fail_closed", check_unknown_remains_fail_closed, ("contract",)),
    ]

    results = {}
    for name, fn, needs in checks_spec:
        missing_inputs = [n for n in needs if shared.get(n) is None]
        if missing_inputs:
            results[name] = {
                "pass": False,
                "reason": "required input(s) could not be loaded: "
                          + ", ".join(f"{n} ({load_errors.get(n, 'not loaded')})"
                                      for n in missing_inputs),
            }
            continue
        try:
            ok, evidence = fn(**{n: shared[n] for n in needs})
            results[name] = {"pass": bool(ok), "evidence": evidence}
        except Exception as exc:
            results[name] = {"pass": False,
                             "reason": f"check could not be computed: "
                                       f"{type(exc).__name__}: {exc}"}

    failing = [n for n, r in results.items() if not r["pass"]]
    verdict = ("MECHANICAL_TO_EMBODIED_HANDOFF_FAIL" if failing
               else "MECHANICAL_TO_EMBODIED_HANDOFF_PASS")

    gate = {
        "schema": "MECHANICAL_TO_EMBODIED_HANDOFF_GATE_R2",
        "generated_local": datetime.datetime.now(TZ8).isoformat(),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "authority_basis": ["ODR-16", "ECR-SOLAR-ARRAY-R2 (ODR-19..ODR-34)"],
        "supersedes": "MECHANICAL_TO_EMBODIED_HANDOFF_GATE.json (V1 gate, frozen, unmodified)",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "role": ("machine-check that the downstream consumer (Sim16 / Physics-Gated RL) "
                 "can actually load and reason about the mechanical assets; does not "
                 "restate the 18 mechanical criteria"),
        "contract_under_test": pins["contract"],
        "source_pins": pins,
        "input_load_errors": load_errors,
        "checks": results,
        "checks_total": len(results),
        "checks_passed": sum(1 for r in results.values() if r["pass"]),
        "checks_failed": len(failing),
        "failing_checks": failing,
        "verdict": verdict,
    }

    with open(longpath(OUT_PATH), "w", encoding="utf-8") as fh:
        json.dump(gate, fh, indent=2, ensure_ascii=False)

    print("WROTE", OUT_PATH)
    print("verdict:", verdict)
    for n, r in results.items():
        print(f"  {'PASS' if r['pass'] else 'FAIL'}  {n}")
        if not r["pass"]:
            ev = r.get("evidence", {})
            for p in (ev.get("problems") or [r.get("reason", "")]):
                print("        -", p)
    return 0 if not failing else 1


if __name__ == "__main__":
    sys.exit(main())
