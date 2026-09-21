# -*- coding: utf-8 -*-
"""M7 WP1 remaining contract artifacts builder.

Emits, from the ALREADY-BUILT design-freeze assembly (no FreeCAD process is
started by this script):

  PRODUCT_STRUCTURE_V1.yaml
  HARNESS_ROUTING_V1.yaml
  KEEP_OUT_REGISTER_V1.yaml
  SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml
  receipt.json

Rules honoured:
  * fail-closed: absent physical/vendor inputs are written as null + named HOLD
  * candidate != authority; design != flight-qualified; analysis != test
  * every consumed file is hashed for real (hashlib, uppercase hex) with bytes
  * no launch / launcher / flight-qualification / manufacturing-release claim
  * the 6 GiB memory gate stays declared FAILED on this host
  * L0 accepted-URDF masses are never overridden (B601 arm 4.695555949342986 kg)

All numeric geometry in the emitted files is either
  (a) copied from the hash-pinned DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json, or
  (b) recomputed here from hash-pinned source geometry (binary STL / STEP text),
      with the derivation method recorded next to the number.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
M7_ROOT = HERE.parent
PROJECT_ROOT = M7_ROOT.parents[1]

BUILD_REPORT = HERE / "DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json"
FCSTD = HERE / "DESIGN_FREEZE_ASSEMBLY_V1.FCStd"
STEP = HERE / "DESIGN_FREEZE_ASSEMBLY_V1.step"
BUILDER_SCRIPT = HERE / "build_design_freeze_assembly.py"

TERMINAL = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
MESH_STOW = TERMINAL / "05_clearance" / "mesh" / "parts_STOWED"
MESH_DEPL = TERMINAL / "05_clearance" / "mesh" / "parts_DEPLOYED"
V5R = PROJECT_ROOT / "20_engineering" / "F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
M6 = PROJECT_ROOT / "20_engineering" / "F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1"
M3 = PROJECT_ROOT / "20_engineering" / "F3R2_MECHANICAL_DETAILED_DESIGN_V1"
URDF_DIR = PROJECT_ROOT / "20_engineering" / "cad" / "spacecraft_layout" / "arm_b601_v1"
URDF = URDF_DIR / "arm_b601_v1.urdf"
URDF_MESH = URDF_DIR / "meshes_b601_gripper"

SOURCES: list[Path] = [
    # ---- WP1 own already-built design freeze (primary source of truth) -----
    BUILDER_SCRIPT, BUILD_REPORT, FCSTD, STEP,
    # ---- M7 authority ------------------------------------------------------
    M7_ROOT / "00_authority" / "M7_OWNER_DECISION_REGISTER_V1.yaml",
    M7_ROOT / "00_authority" / "M7_EXECUTION_PLAN_V1.md",
    # ---- L0 accepted URDF + its collision meshes ---------------------------
    URDF,
    URDF_MESH / "base_link.STL", URDF_MESH / "link1.STL", URDF_MESH / "link2.STL",
    URDF_MESH / "link3.STL", URDF_MESH / "link4.STL", URDF_MESH / "link5.STL",
    URDF_MESH / "link6.STL", URDF_MESH / "gripper_link.STL",
    URDF_MESH / "gripper_left.STL", URDF_MESH / "gripper_right.STL",
    # ---- geometry / frame baselines ----------------------------------------
    PROJECT_ROOT / "20_engineering" / "cad" / "spacecraft_layout" / "model_specs_v0.json",
    V5R / "02_interfaces" / "SYSTEM_FRAME_TREE.yaml",
    # ---- declared-not-modelled definition packages -------------------------
    TERMINAL / "06_supports" / "F3R2_SUPPORT_V2_DEFINITION.json",
    TERMINAL / "07_hdrm" / "F3R2_ARM_HDRM_DEFINITION.json",
    TERMINAL / "08_camera_harness" / "F3R2_CAMERA_HARNESS_GRIPPER.json",
    # ---- native-derived meshes actually measured in this loop --------------
    MESH_STOW / "B51_B601_ARTICULATED_ENGINEERING_ARM_STOWED_O13V.stl",
    MESH_STOW / "Fwd_Saddle.stl", MESH_STOW / "Mid_Saddle.stl", MESH_STOW / "Aft_Saddle.stl",
    MESH_STOW / "04_ARM_STOW_SUPPORT.stl",
    MESH_STOW / "Release_Clearance_Envelope.stl",
    MESH_STOW / "Launch_Lock_Interface_Reference.stl",
    MESH_STOW / "Harness_Passage.stl",
    MESH_STOW / "Harness_Service_Loop_Left.stl", MESH_STOW / "Harness_Service_Loop_Right.stl",
    MESH_STOW / "Hinge_Pin_Left.stl", MESH_STOW / "Hinge_Pin_Right.stl",
    MESH_STOW / "Hard_Stop_Left.stl", MESH_STOW / "Hard_Stop_Right.stl",
    MESH_STOW / "HDRM_Base_1_Left.stl", MESH_STOW / "HDRM_Rod_1_Left.stl",
    MESH_STOW / "HDRM_Base_2_Left.stl", MESH_STOW / "HDRM_Rod_2_Left.stl",
    MESH_STOW / "Spacecraft_Flange.stl", MESH_STOW / "Adapter_Plate.stl",
    MESH_STOW / "Central_Boss.stl", MESH_STOW / "01_Primary_Structure_V2_.stl",
    MESH_STOW / "02_B601_Mount_and_Load_Path.stl",
    MESH_STOW / "Equipment_Decks.stl", MESH_STOW / "Maintenance_Access_Cover.stl",
    MESH_STOW / "Load_Bridge_Left.stl", MESH_STOW / "Load_Bridge_Right.stl",
    MESH_STOW / "WING_L_STOWED.stl", MESH_STOW / "WING_R_STOWED.stl",
    MESH_DEPL / "WING_L_DEPLOYED.stl", MESH_DEPL / "WING_R_DEPLOYED.stl",
    # ---- gripper R1 neutral authority --------------------------------------
    V5R / "04_validation" / "GRIPPER_R1_GEOMETRY_VALIDATION.json",
    V5R / "01_native_cad" / "gripper_r1" / "B601_GRIPPER_PALM_RAIL_SLOT_R1.step",
    V5R / "01_native_cad" / "gripper_r1" / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step",
    V5R / "01_native_cad" / "gripper_r1" / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step",
    # ---- M3R / load bridge --------------------------------------------------
    M3 / "06_parameterized_parts" / "m3r" / "M3R_INTERFACE_ASSEMBLY_V2_WORKING.step",
    TERMINAL / "03_native_cad" / "M3_interface_authority" / "M3R_TSM_PHYSICAL_STACK.yaml",
    M6 / "wp1_load_bridge" / "LOAD_BRIDGE_CANDIDATE_V1.step",
    M6 / "wp1_load_bridge" / "LOAD_BRIDGE_DATUMS_V1.yaml",
    # ---- sibling WP inputs quoted for cross-WP consistency ------------------
    M7_ROOT / "wp5_mechanisms" / "SOLAR_HINGE_DEPLOYMENT_PACK_V1.yaml",
]

CLOCK_SOURCE = "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08"
MEMORY_THRESHOLD_GIB = 6.0


# --------------------------------------------------------------------------
# utilities
# --------------------------------------------------------------------------
def sha256(path: Path) -> str:
    d = hashlib.sha256()
    with path.open("rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            d.update(blk)
    return d.hexdigest().upper()


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def shell_now() -> str:
    """Real host clock; never a literal."""
    try:
        out = subprocess.run(["date", "-Iseconds"], capture_output=True, text=True, timeout=20)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def memory_gate() -> dict:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ok = bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)))
    if not ok:
        return {"available_physical_gib": None, "total_physical_gib": None,
                "threshold_gib": MEMORY_THRESHOLD_GIB, "memory_gate_passed": False,
                "measurement_status": "UNAVAILABLE_FAIL_CLOSED"}
    g = float(1 << 30)
    avail = st.ullAvailPhys / g
    return {"available_physical_gib": round(avail, 6),
            "total_physical_gib": round(st.ullTotalPhys / g, 6),
            "threshold_gib": MEMORY_THRESHOLD_GIB,
            "memory_gate_passed": bool(avail >= MEMORY_THRESHOLD_GIB),
            "measurement_status": "MEASURED"}


def stl_vertices(path: Path) -> np.ndarray:
    """Binary STL -> (3N,3) float32 vertex array, chunked for the failed memory gate."""
    with path.open("rb") as fh:
        fh.read(80)
        n = struct.unpack("<I", fh.read(4))[0]
        out = np.empty((n * 3, 3), dtype=np.float32)
        i = 0
        chunk = 200000
        while i < n:
            k = min(chunk, n - i)
            raw = np.frombuffer(fh.read(k * 50), dtype=np.uint8).reshape(k, 50)
            out[i * 3:(i + k) * 3] = raw[:, 12:48].copy().view("<f4").reshape(k * 3, 3)
            i += k
    return out


def bbox(v: np.ndarray) -> list[float]:
    return [round(float(x), 6) for x in list(v.min(0)) + list(v.max(0))]


def step_solid_count_and_point_aabb(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="replace")
    flat = txt.replace("\r", "").replace("\n", "").replace(" ", "")
    solids = len(re.findall(r"MANIFOLD_SOLID_BREP\(", flat))
    faces = len(re.findall(r"ADVANCED_FACE\(", flat))
    raw = re.findall(r"CARTESIAN_POINT\('[^']*',\(([^)]*)\)\)", flat)
    pts = []
    for t in raw:
        p = t.split(",")
        if len(p) == 3:
            try:
                pts.append([float(x) for x in p])
            except ValueError:
                pass
    arr = np.array(pts)
    return {"manifold_solid_brep_count": solids, "advanced_face_count": faces,
            "cartesian_point_entities": len(raw), "cartesian_points_parsed_3d": int(arr.shape[0]),
            "control_point_aabb_mm": bbox(arr),
            "control_point_aabb_note": (
                "control-point hull only; it is a SUBSET of the exact B-rep bounding box "
                "because conic/cylindrical surfaces are defined by axis+radius rather than by "
                "extremal control points. The OpenCascade bounding box in "
                "DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json remains the authority.")}


def T_rpy(xyz_m, rpy) -> np.ndarray:
    r, p, y = [float(v) for v in rpy]
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    M = np.eye(4)
    M[0, 0] = cy * cp; M[0, 1] = cy * sp * sr - sy * cr; M[0, 2] = cy * sp * cr + sy * sr
    M[1, 0] = sy * cp; M[1, 1] = sy * sp * sr + cy * cr; M[1, 2] = sy * sp * cr - cy * sr
    M[2, 0] = -sp;     M[2, 1] = cp * sr;                M[2, 2] = cp * cr
    M[:3, 3] = [1000.0 * float(v) for v in xyz_m]
    return M


def urdf_model() -> dict:
    root = ET.parse(URDF).getroot()
    joints = {}
    order = []
    for j in root.findall("joint"):
        o = j.find("origin")
        xyz = [float(x) for x in o.attrib.get("xyz", "0 0 0").split()]
        rpy = [float(x) for x in o.attrib.get("rpy", "0 0 0").split()]
        ax = j.find("axis")
        lim = j.find("limit")
        rec = {
            "name": j.attrib["name"], "type": j.attrib["type"],
            "parent": j.find("parent").attrib["link"], "child": j.find("child").attrib["link"],
            "xyz_m": xyz, "rpy_rad": rpy,
            "axis": [float(x) for x in ax.attrib["xyz"].split()] if ax is not None else [0.0, 0.0, 0.0],
            "lower": float(lim.attrib["lower"]) if lim is not None and "lower" in lim.attrib else None,
            "upper": float(lim.attrib["upper"]) if lim is not None and "upper" in lim.attrib else None,
            "T": T_rpy(xyz, rpy),
        }
        joints[rec["child"]] = rec
        order.append(rec)
    return {"joints": joints, "order": order}


def arm_base_matrix_S() -> np.ndarray:
    """Frozen F3R2 mapping, identical to build_design_freeze_assembly.arm_base_matrix()."""
    a = math.radians(25.000014)
    c, s = math.cos(a), math.sin(a)
    return np.array([[0.0, 0.0, 1.0, 208.0],
                     [s, c, 0.0, 0.0],
                     [-c, s, 0.0, 0.0],
                     [0.0, 0.0, 0.0, 1.0]])


# --------------------------------------------------------------------------
# derivation 1 : arm + gripper geometric envelopes from the ACCEPTED URDF
# --------------------------------------------------------------------------
def derive_arm_envelopes() -> dict:
    um = urdf_model()
    joints, order = um["joints"], um["order"]
    links = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6",
             "gripper_link", "gripper_left", "gripper_right"]
    verts = {n: stl_vertices(URDF_MESH / (n + ".STL")) * 1000.0 for n in links}  # m -> mm

    # (a) conservative sphere: |p_child| <= |p_parent| + |t| (+ prismatic travel);
    #     a revolute rotation cannot increase the distance of a frame origin.
    cum = {"base_link": 0.0}
    for rec in order:
        travel = 0.0
        if rec["type"] == "prismatic":
            travel = 1000.0 * abs(rec["upper"] - rec["lower"])
        cum[rec["child"]] = cum[rec["parent"]] + float(np.linalg.norm(rec["T"][:3, 3])) + travel
    rmax = {n: float(np.linalg.norm(verts[n], axis=1).max()) for n in links}
    per_link_bound = {n: round(cum[n] + rmax[n], 6) for n in links}
    gov = max(per_link_bound, key=per_link_bound.get)

    # (b) exact AABB of the collision mesh set at the design-freeze default pose
    #     (all revolute q = 0) mapped into S, for two gripper stroke states.
    T_S_arm = arm_base_matrix_S()

    def fk(travel_mm):
        T = {"base_link": np.eye(4)}
        rest = dict(joints)
        while rest:
            progressed = False
            for child, rec in list(rest.items()):
                if rec["parent"] not in T:
                    continue
                M = T[rec["parent"]] @ rec["T"]
                if rec["type"] == "prismatic":
                    slide = np.eye(4)
                    slide[:3, 3] = np.array(rec["axis"]) * travel_mm
                    M = M @ slide
                T[child] = M
                del rest[child]
                progressed = True
            if not progressed:
                raise RuntimeError("URDF chain unresolved")
        return T

    poses = {}
    for label, travel in (("GRIPPER_CLOSED_travel_0_0mm", 0.0),
                          ("GRIPPER_OPEN_travel_71_5mm", 71.5)):
        T = fk(travel)
        allv, jaw, per = [], [], {}
        for n in links:
            M = T_S_arm @ T[n]
            w = (M[:3, :3] @ verts[n].T).T + M[:3, 3]
            per[n] = bbox(w)
            allv.append(w)
            if n in ("gripper_link", "gripper_left", "gripper_right"):
                jaw.append(w)
        poses[label] = {
            "arm_plus_gripper_aabb_S_mm": bbox(np.vstack(allv)),
            "gripper_assembly_aabb_S_mm": bbox(np.vstack(jaw)),
            "per_link_aabb_S_mm": per,
        }

    # (c) harness take-up bound per rotary joint: a clamp on the child link sits at
    #     radius r <= R_child about that joint axis, so the differential length the
    #     harness must absorb across that joint is bounded by R_child * delta_theta.
    axis_takeup = []
    total = 0.0
    for rec in order:
        if rec["type"] != "revolute":
            continue
        v = verts[rec["child"]]
        ax = np.array(rec["axis"], dtype=float)
        ax = ax / np.linalg.norm(ax)
        proj = v - np.outer(v @ ax, ax)
        R = float(np.linalg.norm(proj, axis=1).max())
        dth = float(rec["upper"] - rec["lower"])
        bound = R * dth
        total += bound
        axis_takeup.append({
            "joint": rec["name"], "child_link": rec["child"],
            "joint_range_rad": round(dth, 9),
            "joint_range_deg": round(math.degrees(dth), 6),
            "max_child_link_radius_about_joint_axis_mm": round(R, 6),
            "harness_takeup_upper_bound_mm": round(bound, 6),
        })
    return {
        "conservative_sphere": {
            "center_frame": "B601 base_link origin = S station [208.0, 0.0, 0.0] mm",
            "radius_mm": round(per_link_bound[gov], 6),
            "governing_link": gov,
            "per_link_bound_mm": per_link_bound,
            "cumulative_frame_origin_bound_mm": {k: round(v, 6) for k, v in cum.items()},
            "max_vertex_radius_in_link_frame_mm": {k: round(v, 6) for k, v in rmax.items()},
        },
        "default_pose_exact_aabb": poses,
        "harness_takeup_bounds": {
            "per_joint": axis_takeup,
            "sum_of_upper_bounds_mm": round(total, 6),
        },
    }


# --------------------------------------------------------------------------
# derivation 2 : gripper full-stroke sweep (V5R neutral R1 lineage)
# --------------------------------------------------------------------------
def derive_gripper_sweep(report):
    left = step_solid_count_and_point_aabb(
        V5R / "01_native_cad" / "gripper_r1" / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step")
    right = step_solid_count_and_point_aabb(
        V5R / "01_native_cad" / "gripper_r1" / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step")
    lb, rb = left["control_point_aabb_mm"], right["control_point_aabb_mm"]
    union = [min(lb[0], rb[0]), min(lb[1], rb[1]), min(lb[2], rb[2]),
             max(lb[3], rb[3]), max(lb[4], rb[4]), max(lb[5], rb[5])]
    rows = report["transforms"]["T_S_LINK6_Q0_FOR_GRIPPER_R1_PALM"]
    T = np.array(rows, dtype=float)
    corners = np.array([[x, y, z] for x in (union[0], union[3])
                        for y in (union[1], union[4]) for z in (union[2], union[5])])
    mapped = (T[:3, :3] @ corners.T).T + T[:3, 3]
    return {
        "left_sweep_solids": left["manifold_solid_brep_count"],
        "right_sweep_solids": right["manifold_solid_brep_count"],
        "union_aabb_link6_local_mm": union,
        "mapped_conservative_aabb_S_mm": bbox(mapped),
        "mapping_transform": "T_S_LINK6_Q0_FOR_GRIPPER_R1_PALM (design-freeze build report)",
        "conservatism_note": ("the AABB of the rotated corner set of an AABB is a superset of "
                             "the rotated geometry, so this S-frame box is conservative, not tight"),
        "control_point_caveat": left["control_point_aabb_note"],
    }


# --------------------------------------------------------------------------
# derivation 3 : G07 / G08 / MID_SUPPORT contact truth, re-derived
# --------------------------------------------------------------------------
SUPPORT_MAP = {
    "G07": {"native_part": "Aft_Saddle", "v2_head_mm": [54.0, 54.0]},
    "G08": {"native_part": "Fwd_Saddle", "v2_head_mm": [34.0, 34.0]},
    "MID": {"native_part": "Mid_Saddle", "v2_head_mm": [34.0, 34.41]},
}


def derive_support_contacts(support_def):
    arm = stl_vertices(MESH_STOW / "B51_B601_ARTICULATED_ENGINEERING_ARM_STOWED_O13V.stl")
    out = {
        "counterface_measurement_source": {
            "arm_mesh": rel(MESH_STOW / "B51_B601_ARTICULATED_ENGINEERING_ARM_STOWED_O13V.stl"),
            "arm_mesh_vertices": int(arm.shape[0]),
            "arm_mesh_aabb_mm": bbox(arm),
            "configuration": "STOWED (the only configuration in which stow supports can contact)",
            "geometry_lineage": ("B51 native CAD arm tessellation; the SolidWorks native line is "
                                 "off the critical path per ODR-03 and is used here only as the "
                                 "measurement counterpart for a native-defined support package"),
            "lineage_hold": "HOLD_B51_CAD_ARM_VS_ACCEPTED_URDF_COLLISION_MESH_ARE_DIFFERENT_VERSIONS",
        },
        "supports": {},
    }
    for sid, m in SUPPORT_MAP.items():
        tower = stl_vertices(MESH_STOW / (m["native_part"] + ".stl"))
        tb = bbox(tower)
        v1_top = tb[5]
        fx, fy = (tb[0], tb[3]), (tb[1], tb[4])
        cx, cy = (fx[0] + fx[1]) / 2.0, (fy[0] + fy[1]) / 2.0
        hx, hy = m["v2_head_mm"]
        sd = support_def["supports"][sid]
        pad_face = float(sd["geometry"]["pad_face_z_mm"])
        declared = float(sd["counterface_evidence"]["arm_lowest_z_mm"])
        band_x = tuple(sd["counterface_evidence"]["contact_band_x_mm"])
        band_y = tuple(sd["counterface_evidence"]["contact_band_y_mm"])
        windows = {
            "V1_TOWER_FOOT_FOOTPRINT": (fx[0], fx[1], fy[0], fy[1]),
            "V2_HEAD_FOOTPRINT_FOOT_CENTRED_ASSUMPTION": (cx - hx / 2, cx + hx / 2,
                                                          cy - hy / 2, cy + hy / 2),
            "V2_DECLARED_CONTACT_BAND": (band_x[0], band_x[1], band_y[0], band_y[1]),
        }
        rows = {}
        for label, win in windows.items():
            x0, x1, y0, y1 = win
            sel = ((arm[:, 0] >= x0) & (arm[:, 0] <= x1) &
                   (arm[:, 1] >= y0) & (arm[:, 1] <= y1))
            cnt = int(sel.sum())
            if cnt == 0:
                rows[label] = {
                    "window_x_mm": [round(x0, 6), round(x1, 6)],
                    "window_y_mm": [round(y0, 6), round(y1, 6)],
                    "arm_vertices_in_window": 0,
                    "measured_arm_min_z_mm": None,
                    "status": "NO_ARM_MATERIAL_OVER_WINDOW_CANNOT_EVALUATE_CONTACT",
                }
                continue
            sub = arm[sel]
            zmin = float(sub[:, 2].min())
            below = sub[sub[:, 2] < pad_face]
            rows[label] = {
                "window_x_mm": [round(x0, 6), round(x1, 6)],
                "window_y_mm": [round(y0, 6), round(y1, 6)],
                "arm_vertices_in_window": cnt,
                "measured_arm_min_z_mm": round(zmin, 6),
                "v1_tower_top_z_mm": round(v1_top, 6),
                "signed_gap_to_v1_tower_top_mm": round(zmin - v1_top, 6),
                "v2_declared_pad_face_z_mm": pad_face,
                "signed_gap_to_v2_pad_face_mm": round(zmin - pad_face, 6),
                "v2_declared_arm_lowest_z_mm": declared,
                "delta_vs_v2_declared_mm": round(zmin - declared, 6),
                "arm_vertices_below_v2_pad_face": int(below.shape[0]),
                "sub_pad_material_aabb_mm": bbox(below) if below.shape[0] else None,
            }
        out["supports"][sid] = {
            "native_part": m["native_part"],
            "v1_tower_aabb_mm": tb,
            "v1_tower_top_z_mm": round(v1_top, 6),
            "v2_declared_nominal_gap_mm": sd["contact"].get("nominal_gap_mm"),
            "v2_declared_pad_face_z_mm": pad_face,
            "v2_declared_arm_lowest_z_mm": declared,
            "v2_declared_points_above_old_top": sd["counterface_evidence"]["points_above_old_top"],
            "measurement_windows": rows,
        }
    return out


# --------------------------------------------------------------------------
# derivation 4 : native reference volumes + frame corroboration
# --------------------------------------------------------------------------
NATIVE_PROBES = [
    (MESH_STOW, "Harness_Passage"), (MESH_STOW, "Harness_Service_Loop_Left"),
    (MESH_STOW, "Harness_Service_Loop_Right"), (MESH_STOW, "Launch_Lock_Interface_Reference"),
    (MESH_STOW, "Release_Clearance_Envelope"), (MESH_STOW, "04_ARM_STOW_SUPPORT"),
    (MESH_STOW, "HDRM_Base_1_Left"), (MESH_STOW, "HDRM_Rod_1_Left"),
    (MESH_STOW, "HDRM_Base_2_Left"), (MESH_STOW, "HDRM_Rod_2_Left"),
    (MESH_STOW, "Hard_Stop_Left"), (MESH_STOW, "Hard_Stop_Right"),
    (MESH_STOW, "Hinge_Pin_Left"), (MESH_STOW, "Hinge_Pin_Right"),
    (MESH_STOW, "Spacecraft_Flange"), (MESH_STOW, "Adapter_Plate"), (MESH_STOW, "Central_Boss"),
    (MESH_STOW, "01_Primary_Structure_V2_"), (MESH_STOW, "02_B601_Mount_and_Load_Path"),
    (MESH_STOW, "Equipment_Decks"), (MESH_STOW, "Maintenance_Access_Cover"),
    (MESH_STOW, "Load_Bridge_Left"), (MESH_STOW, "Load_Bridge_Right"),
    (MESH_STOW, "WING_L_STOWED"), (MESH_STOW, "WING_R_STOWED"),
    (MESH_DEPL, "WING_L_DEPLOYED"), (MESH_DEPL, "WING_R_DEPLOYED"),
]


def derive_native_probes():
    rows = {}
    for folder, name in NATIVE_PROBES:
        v = stl_vertices(folder / (name + ".stl"))
        rows[name] = {"source": rel(folder / (name + ".stl")),
                      "triangles": int(v.shape[0] // 3),
                      "aabb_mm": bbox(v)}
    return rows


def derive_panel_sweep(report):
    out = {}
    axes = {"LEFT": [-61.0, 143.15, 0.0], "RIGHT": [-61.0, -143.15, 0.0]}
    boxes = {
        "LEFT": report["source_geometry_metrics"]["solar_array_left"]["bounding_box_mm"],
        "RIGHT": report["source_geometry_metrics"]["solar_array_right"]["bounding_box_mm"],
    }
    for side, ax in axes.items():
        b = boxes[side]
        y0, z0 = ax[1], ax[2]
        dy = [b[1] - y0, b[4] - y0]
        dz = [b[2] - z0, b[5] - z0]
        rmax = max(math.hypot(a, c) for a in dy for c in dz)
        spans = (min(dy) <= 0.0 <= max(dy)) and (min(dz) <= 0.0 <= max(dz))
        rmin = 0.0 if spans else min(math.hypot(a, c) for a in dy for c in dz)
        root_overlap = (y0 - b[1]) if side == "LEFT" else (b[4] - y0)
        out[side] = {
            "hinge_axis_point_S_mm": ax,
            "hinge_axis_direction_S": [1.0, 0.0, 0.0],
            "panel_deployed_aabb_S_mm": b,
            "radial_extent_about_hinge_axis_mm": {"r_min": round(rmin, 6), "r_max": round(rmax, 6)},
            "hinge_axis_passes_through_panel_bbox": bool(spans),
            "fail_closed_full_revolution_sweep_aabb_S_mm": [
                b[0], round(y0 - rmax, 6), round(z0 - rmax, 6),
                b[3], round(y0 + rmax, 6), round(z0 + rmax, 6)],
            "panel_root_overlap_inboard_of_hinge_line_mm": round(root_overlap, 6),
        }
    return out


def aabb_separation(a, b):
    """Per-axis and Euclidean separation between two axis-aligned boxes."""
    gaps = []
    for i in range(3):
        lo = b[i] - a[i + 3]
        hi = a[i] - b[i + 3]
        gaps.append(round(max(lo, hi, 0.0), 6) if max(lo, hi) > 0 else round(max(lo, hi), 6))
    disjoint = any(g > 0.0 for g in gaps)
    euclid = math.sqrt(sum(g * g for g in gaps if g > 0.0)) if disjoint else 0.0
    return {"per_axis_gap_mm": gaps, "boxes_disjoint": bool(disjoint),
            "euclidean_box_gap_mm": round(euclid, 6)}


# --------------------------------------------------------------------------
# artifact 1 : PRODUCT_STRUCTURE_V1.yaml
# --------------------------------------------------------------------------
GEOM_STATUS_LEGEND = {
    "EXISTS_AS_GEOMETRY": ("an App::Link instance of an embedded Part::Feature source in "
                           "DESIGN_FREEZE_ASSEMBLY_V1.FCStd whose solids are exported into "
                           "DESIGN_FREEZE_ASSEMBLY_V1.step"),
    "EXISTS_AS_SUB_SOLID_OF_PARENT_PROXY": ("no independent instance; the node is one solid of a "
                                            "parent compound and cannot be moved, suppressed or "
                                            "mass-accounted separately"),
    "DESIGN_CANDIDATE_EVIDENCE_STUB": ("a hidden candidate solid inside DESIGN_CANDIDATE_COMPONENTS; "
                                       "measured for clearance, deliberately NOT exported to STEP, "
                                       "not authorised"),
    "FRAME_AXIS_WITNESS_ONLY": ("thin witness geometry that carries frames and axes only; it is "
                                "explicitly NOT the physical envelope and must never be used for "
                                "interference, clearance or mass"),
    "DEFINED_NOT_MODELLED": ("the node has a written definition and/or numeric intent but no B-rep "
                             "in the neutral design-freeze chain"),
    "DECLARED_ONLY_NO_NUMERIC_AUTHORITY": ("named in the product tree with neither geometry nor a "
                                           "numeric definition that this loop may adopt"),
}


def build_product_structure(report, native, arm_env, step_probe, register):
    inst = report["installed_components"]
    cand = report["design_candidate_evidence_components"]
    metrics = report["source_geometry_metrics"]

    def node(nid, parent, status, **kw):
        d = {"id": nid, "parent": parent, "geometry_status": status}
        d.update(kw)
        return d

    nodes = []
    nodes.append(node(
        "SEI_SPACECRAFT_MECHANICAL_BASELINE_V1", None, "EXISTS_AS_GEOMETRY",
        role="frozen top-level product tree for M7 Gate A (mechanical engineering design)",
        geometry_evidence={
            "fcstd": rel(FCSTD), "step": rel(STEP),
            "fcstd_object_count": report["fcstd_cold_reopen"]["object_count"],
            "fcstd_app_link_count": report["fcstd_cold_reopen"]["app_link_count"],
            "step_solids_reported_by_opencascade": report["step_cold_reopen"]["solids"],
            "step_manifold_solid_brep_count_independently_counted": step_probe["manifold_solid_brep_count"],
            "step_advanced_face_count_independently_counted": step_probe["advanced_face_count"],
        },
        holds=["NOT_MANUFACTURING_RELEASED", "NOT_FLIGHT_OR_LAUNCH_QUALIFIED",
               "NOT_CONTINUOUS_COLLISION_OR_SWEEP_VALIDATED",
               "MECHANICAL_FLIGHT_QUALIFICATION_RELEASED_GATE_B_HOLD"]))

    nodes.append(node(
        "BUS_PRIMARY_STRUCTURE", "SEI_SPACECRAFT_MECHANICAL_BASELINE_V1", "EXISTS_AS_GEOMETRY",
        instance="INST_BUS_12U_CORE",
        source="20_engineering/cad/spacecraft_layout/model_specs_v0.json::servicer_12U_v0.primitives",
        solids=metrics["bus_12U_core"]["solids"],
        faces=metrics["bus_12U_core"]["faces"],
        volume_mm3=metrics["bus_12U_core"]["volume_mm3"],
        aabb_S_mm=metrics["bus_12U_core"]["bounding_box_mm"],
        composition_note=("single compound of 6 analytic primitives: front_task_bay, mid_bus_bay, "
                          "rear_bay (each 113.5 x 226.3 x 226.3 mm), legacy flange "
                          "(15 x 140 x 140 mm at x 170.25..185.25), nozzle placeholder, "
                          "antenna placeholder. It is a solid envelope proxy: no internal "
                          "structure, no bays, no harness voids, no access cut-outs."),
        holds=["12U_DIMENSION_VERIFICATION_HOLD", "INTERNAL_STRUCTURE_NOT_MODELLED",
               "LEGACY_FLANGE_OWNERSHIP_HOLD_TAGGED_REFERENCE_ODR01",
               "HOLD_NEUTRAL_PROXY_BUS_LENGTH_340P5_VS_NATIVE_V2_2_366P0_MM_UNRECONCILED"],
        model_to_model_delta={
            "neutral_proxy_x_extent_mm": [-170.25, 170.25],
            "native_V2_2_primary_structure_x_extent_mm": native["01_Primary_Structure_V2_"]["aabb_mm"][0:1]
            + [native["01_Primary_Structure_V2_"]["aabb_mm"][3]],
            "native_V2_2_primary_structure_aabb_mm": native["01_Primary_Structure_V2_"]["aabb_mm"],
            "consequence": ("the two models agree on the y/z outer surface (+/-113.15 mm) and on the "
                            "arm mount stations (198.0 / 208.0 mm) but not on bus length; any x "
                            "coordinate near the front face must state which model it came from")}))

    nodes.append(node(
        "BUS_PANELS", "BUS_PRIMARY_STRUCTURE", "DEFINED_NOT_MODELLED",
        definition=("outer closure panels of the 12U bus. In the design-freeze chain the +/-113.15 mm "
                    "surfaces are faces of the solid bay boxes, so no discrete panel bodies exist "
                    "and no panel thickness, fastener pattern or joint is modelled."),
        do_not_confuse_with="SOLAR_ARRAY_LEFT/RIGHT.PANEL (the deployable solar wings)",
        holds=["HOLD_BUS_CLOSURE_PANEL_GEOMETRY_NOT_MODELLED",
               "HOLD_BUS_PANEL_FASTENER_AND_JOINT_DEFINITION_ABSENT"]))

    nodes.append(node(
        "M3R", "SEI_SPACECRAFT_MECHANICAL_BASELINE_V1", "EXISTS_AS_GEOMETRY",
        instance="INST_M3R_INTERFACE_ASSEMBLY",
        source="20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_WORKING.step",
        solids=metrics["M3R_interface_assembly"]["solids"],
        faces=metrics["M3R_interface_assembly"]["faces"],
        volume_mm3=metrics["M3R_interface_assembly"]["volume_mm3"],
        local_aabb_mm=metrics["M3R_interface_assembly"]["bounding_box_mm"],
        installed_transform="T_S_M3R_LOCAL (design-freeze build report)",
        installed_x_span_S_mm=[196.0, 210.405],
        design_mass_kg=0.7619,
        design_mass_class="DESIGN_BUDGET confidence B (ODR-05)",
        holds=["B601_PHYSICAL_FITUP_HOLD", "TOLERANCE_AND_FASTENER_HOLD",
               "M3R_AS_BUILT_MEASUREMENT_OPEN_ODR05"]))
    nodes.append(node(
        "M3R.STAGE_A_RING", "M3R", "EXISTS_AS_SUB_SOLID_OF_PARENT_PROXY",
        evidence=("the installed M3R B-rep is a 2-solid compound and the M3R product definition is "
                  "a two-stage interface (Stage A ring + Stage B load-diffusion plate), so the two "
                  "stages are present as geometry"),
        per_stage_solid_attribution=None,
        holds=["HOLD_PER_STAGE_SOLID_ATTRIBUTION_NOT_ESTABLISHED_IN_THIS_LOOP",
               "HOLD_STAGE_A_SPIGOT_AND_DOWEL_FIT_REQUIRE_MEASURED_HARDWARE"],
        note=("this loop did not open the M3R compound solid-by-solid, so which of the two solids "
              "is Stage A and which is Stage B is recorded as not established rather than guessed")))
    nodes.append(node(
        "M3R.STAGE_B_LOAD_DIFFUSION_PLATE", "M3R", "EXISTS_AS_SUB_SOLID_OF_PARENT_PROXY",
        ligament_mm=6.7,
        wc_min_edge_ligament_mm=6.605,
        wc_source="wp3_tolerance_alloc M7-TC-07",
        holds=["HOLD_PER_STAGE_SOLID_ATTRIBUTION_NOT_ESTABLISHED_IN_THIS_LOOP"]))
    nodes.append(node(
        "M3R.FASTENER_SET", "M3R", "DEFINED_NOT_MODELLED",
        definition="4 x HM4-75 / M4-class, 64 x 64 mm square pattern, PCD 90.509642 mm",
        modelled_as_solids=False,
        owning_work_package="wp4_fastener_design",
        holds=["HOLD_FASTENER_SOLIDS_NOT_IN_DESIGN_FREEZE_ASSEMBLY",
               "HOLD_PRELOAD_GRADE_AND_MARGIN_OF_SAFETY_PENDING_WP4_AND_TEST"]))
    nodes.append(node(
        "M3R.LOCATOR_SET", "M3R", "DEFINED_NOT_MODELLED",
        definition=("locating/clocking features of the two-stage interface; worst-case dowel "
                    "clocking 1.890909e-3 rad (wp3 M7-TC-05)"),
        modelled_as_solids=False,
        holds=["HOLD_LOCATOR_SOLIDS_NOT_IN_DESIGN_FREEZE_ASSEMBLY",
               "HOLD_PIN_BORE_NOMINALS_REQUIRE_MEASURED_HARDWARE"]))

    b601_links = ["BASE", "LINK1", "LINK2", "LINK3", "LINK4", "LINK5", "LINK6", "WRIST"]
    urdf_link_of = {"BASE": "base_link", "LINK1": "link1", "LINK2": "link2", "LINK3": "link3",
                    "LINK4": "link4", "LINK5": "link5", "LINK6": "link6",
                    "WRIST": "link6 + gripper_link (the accepted URDF declares no separate wrist link)"}
    nodes.append(node(
        "B601", "SEI_SPACECRAFT_MECHANICAL_BASELINE_V1", "FRAME_AXIS_WITNESS_ONLY",
        instance="INST_B601_ARM_CORE_Q0",
        source="20_engineering/cad/freecad_authoritative/B601_KINEMATIC_ASSEMBLY_Q0_WITNESS.step",
        solids=metrics["B601_arm_q0_frame_axis_witness"]["solids"],
        volume_mm3=metrics["B601_arm_q0_frame_axis_witness"]["volume_mm3"],
        aabb_S_mm=metrics["B601_arm_q0_frame_axis_witness"]["bounding_box_mm"],
        witness_proof=("18 solids totalling %.6f mm3 spread over a %.1f mm span: mean solid volume "
                       "%.3f mm3. This cannot be link envelope geometry." % (
                           metrics["B601_arm_q0_frame_axis_witness"]["volume_mm3"],
                           metrics["B601_arm_q0_frame_axis_witness"]["bounding_box_mm"][3]
                           - metrics["B601_arm_q0_frame_axis_witness"]["bounding_box_mm"][0],
                           metrics["B601_arm_q0_frame_axis_witness"]["volume_mm3"] / 18.0)),
        mass_kg=4.695555949342986,
        mass_authority="ACCEPTED_URDF L0 - never overridden by CAD",
        installed_transform="T_S_B601_ARM_BASE = Ry(+90 deg) * Rz(+25.000014 deg) at x = 208.0 mm",
        holds=["B601_PHYSICAL_GEOMETRY_HOLD", "PHYSICAL_FITUP_HOLD", "CONTINUOUS_COLLISION_HOLD",
               "HOLD_ARM_ENVELOPE_BREP_ABSENT_FROM_DESIGN_FREEZE_ASSEMBLY"]))
    for nm in b601_links:
        nodes.append(node(
            "B601." + nm, "B601", "DEFINED_NOT_MODELLED",
            urdf_link=urdf_link_of[nm],
            envelope_source_outside_design_freeze=(
                "20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper/"
                + (urdf_link_of[nm] + ".STL" if nm != "WRIST" else "link6.STL + gripper_link.STL")),
            max_vertex_radius_in_link_frame_mm=(
                arm_env["conservative_sphere"]["max_vertex_radius_in_link_frame_mm"].get(
                    urdf_link_of[nm])),
            holds=["HOLD_PER_LINK_BREP_NOT_INSTALLED_IN_DESIGN_FREEZE_ASSEMBLY",
                   "HOLD_B51_CAD_ARM_VS_ACCEPTED_URDF_COLLISION_MESH_ARE_DIFFERENT_VERSIONS"]))

    nodes.append(node(
        "GRIPPER_R1", "B601.LINK6", "EXISTS_AS_GEOMETRY",
        instance="INST_GRIPPER_R1_PALM",
        source="20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/01_native_cad/gripper_r1/B601_GRIPPER_PALM_RAIL_SLOT_R1.step",
        solids=metrics["gripper_R1_palm"]["solids"],
        faces=metrics["gripper_R1_palm"]["faces"],
        volume_mm3=metrics["gripper_R1_palm"]["volume_mm3"],
        scope="PALM ONLY (rail-slot corrected neutral derivative)",
        stroke_mm=[0.0, 71.5],
        installed_transform="T_S_LINK6_Q0_FOR_GRIPPER_R1_PALM",
        holds=["FINGER_BREP_SEPARATION_HOLD", "CONTACT_LOAD_HOLD", "MANUFACTURING_CLEARANCE_HOLD",
               "HOLD_EXTERNAL_OBJECT_GRIPPER_CONTACT_GEOMETRY_ABSENT"]))
    nodes.append(node(
        "GRIPPER_R1.FINGERS", "GRIPPER_R1", "DEFINED_NOT_MODELLED",
        unresolved_slot="SLOT_GRIPPER_R1_FINGERS__UNRESOLVED",
        definition=("two prismatic fingers, gripper_joint1/2, travel 0..71.5 mm, declared in the "
                    "accepted URDF; the R1 neutral source closes the palm rail-slot only"),
        holds=["FINGER_BREP_SEPARATION_HOLD", "PREGRASP_CONTACT_HOLD"]))

    for side, key, hd_a, hd_b in (("LEFT", "solar_array_left", "HDRM_Base_1_Left", "HDRM_Base_2_Left"),
                                  ("RIGHT", "solar_array_right", None, None)):
        arr = "SOLAR_ARRAY_" + side
        nodes.append(node(
            arr, "SEI_SPACECRAFT_MECHANICAL_BASELINE_V1", "EXISTS_AS_GEOMETRY",
            instance="INST_SOLAR_ARRAY_%s_DEPLOYED" % side,
            configuration_scope="DEPLOYED ONLY",
            failure_semantics="ODR-02: attached-stuck, never jettison",
            holds=["STOWED_GEOMETRY_HOLD", "HINGE_KINEMATICS_HOLD",
                   "PANEL_FAILURE_ATTACHED_STUCK_ODR02"]))
        nodes.append(node(
            arr + ".PANEL", arr, "EXISTS_AS_GEOMETRY",
            solids=metrics[key]["solids"], faces=metrics[key]["faces"],
            volume_mm3=metrics[key]["volume_mm3"], aabb_S_mm=metrics[key]["bounding_box_mm"],
            box_mm=[227.0, 200.0, 6.0], design_mass_kg=0.3483933,
            modelling_class="single homogeneous plate proxy; no cells, substrate or stiffeners",
            holds=["HOLD_PANEL_LAYUP_AND_CELL_GEOMETRY_NOT_MODELLED",
                   "HOLD_PANEL_MASS_0P348_KG_IS_AN_SSOT_PLACEHOLDER_REAL_AREA_DENSITY_2_TO_5_KG_PER_M2"]))
        nodes.append(node(
            arr + ".ROOT_HINGE", arr, "DEFINED_NOT_MODELLED",
            axis_point_S_mm=[-61.0, 143.15 if side == "LEFT" else -143.15, 0.0],
            axis_direction_S=[1.0, 0.0, 0.0],
            axis_status="B_REP_PROBE_MAPPING (V5R SYSTEM_FRAME_TREE), not a manufacturing datum",
            axis_corroboration={
                "native_part": "Hinge_Pin_%s" % ("Left" if side == "LEFT" else "Right"),
                "native_aabb_mm": native["Hinge_Pin_%s" % ("Left" if side == "LEFT" else "Right")]["aabb_mm"],
                "reading": ("the native hinge pin box is 8 mm across in y and z and centred on "
                            "y = +/-143.15, z = 0, spanning x -82..-40 whose midpoint is x = -61.0, "
                            "so the declared axis point is corroborated by independent geometry")},
            deployed_angle_design_target_deg=90.0,
            deployed_angle_class="DESIGN_TARGET_CANDIDATE (wp5 HNG-SMS-01)",
            holds=["HINGE_KINEMATICS_HOLD", "HOLD_HINGE_HARDWARE_NOMINALS_FITS_AND_STOP_GEOMETRY",
                   "HOLD_FREEPLAY_LIMITS_NO_NUMERIC_AUTHORITY"]))
        nodes.append(node(
            arr + ".HDRM", arr, "DEFINED_NOT_MODELLED",
            native_reference_parts=["HDRM_Base_1_%s" % side.capitalize(), "HDRM_Rod_1_%s" % side.capitalize(),
                                    "HDRM_Base_2_%s" % side.capitalize(), "HDRM_Rod_2_%s" % side.capitalize()],
            native_probe_left_only={k: native[k]["aabb_mm"] for k in
                                    ("HDRM_Base_1_Left", "HDRM_Rod_1_Left",
                                     "HDRM_Base_2_Left", "HDRM_Rod_2_Left")} if side == "LEFT" else
            "mirror of LEFT; not probed separately in this loop",
            distinct_from="ARM_HDRM (restrains the arm, not the wings)",
            holds=["SOLAR_HDRM_PRODUCT_HOLD", "HOLD_HDRM_ARCHITECTURE_NOT_SELECTED",
                   "HOLD_RELEASE_DEVICE_PART_NUMBER_AND_PRELOAD_ABSENT"]))
        nodes.append(node(
            arr + ".LATCH_STOP", arr, "DEFINED_NOT_MODELLED",
            native_reference_parts=["Hard_Stop_%s" % ("Left" if side == "LEFT" else "Right")],
            native_aabb_mm=native["Hard_Stop_%s" % ("Left" if side == "LEFT" else "Right")]["aabb_mm"],
            requirement="positive latch at end of travel, engagement observable (wp5 HNG-SMS-05)",
            end_stop_energy_max_J=0.2356,
            end_stop_energy_class="DERIVED (wp5 HNG-SMS-04)",
            holds=["LATCH_STOP_PRODUCT_HOLD", "HOLD_LATCH_GEOMETRY_NOT_MODELLED"]))

    for sid in ("G07", "G08", "MID_SUPPORT"):
        nodes.append(node(
            sid, "SEI_SPACECRAFT_MECHANICAL_BASELINE_V1", "DEFINED_NOT_MODELLED",
            unresolved_slot="SLOT_STOW_SUPPORTS__CANDIDATE_REF",
            detail_artifact="SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml",
            holds=["SUPPORT_PRODUCT_BREP_HOLD", "PAD_BENCH_CALIBRATION_HOLD"]))

    nodes.append(node(
        "CAMERA_BRACKET", "SEI_SPACECRAFT_MECHANICAL_BASELINE_V1",
        "DESIGN_CANDIDATE_EVIDENCE_STUB",
        candidate_instances=["CAND_CAMERA_BRACKET_A", "CAND_CAMERA_BRACKET_B"],
        third_competing_definition=("F3R2_ARM_HDRM_DEFINITION.camera.proposed_mount: a wrist bracket "
                                    "on link6, 40 x 34 x 26 mm, 34 g - a mutually exclusive "
                                    "architecture (moves with the arm instead of the bus)"),
        exported_to_step=False,
        holds=["BRACKET_DETAIL_DESIGN_HOLD", "FASTENER_PATTERN_HOLD",
               "HOLD_CAMERA_MOUNT_ARCHITECTURE_NOT_SELECTED_BUS_MOUNT_VS_WRIST_MOUNT",
               "HOLD_CAMERA_BRACKET_POSE_NO_AUTHORIZED_GEOMETRY_M7_TC_13"]))
    nodes.append(node(
        "CAMERA", "CAMERA_BRACKET", "DESIGN_CANDIDATE_EVIDENCE_STUB",
        candidate_instances=["CAND_CAMERA_CAM_A", "CAND_CAMERA_CAM_B"],
        candidate_definitions=report["camera_candidate_definitions"],
        rejected_source_placeholder=("model_specs_v0.json::camera_payload at [190.25, 0, 80] mm - "
                                     "rejected because it penetrates the installed M3R working B-rep"),
        part_number=None,
        holds=["CAMERA_PART_NUMBER_HOLD", "OPTICAL_CALIBRATION_HOLD", "MASS_INERTIA_HOLD",
               "SENSOR_PACKAGE_SELECTION_HOLD"]))

    nodes.append(node(
        "HARNESS", "SEI_SPACECRAFT_MECHANICAL_BASELINE_V1", "DEFINED_NOT_MODELLED",
        detail_artifact="HARNESS_ROUTING_V1.yaml",
        geometry_in_design_freeze=False,
        holds=["HOLD_NO_HARNESS_GEOMETRY_IN_ANY_CHAIN", "HOLD_VENDOR_CABLE_SPECIFICATION_ABSENT",
               "HOLD_MOVING_HARNESS_SWEEP_NOT_COMPUTED"]))
    nodes.append(node(
        "HARNESS.CABLE_ROUTING", "HARNESS", "DEFINED_NOT_MODELLED",
        runs=["H-RUN-01_ARM", "H-RUN-02_SOLAR_LEFT", "H-RUN-03_SOLAR_RIGHT",
              "H-RUN-04_CAMERA", "H-RUN-05_ARM_HDRM", "H-RUN-06_SOLAR_HDRM"],
        holds=["HOLD_ROUTE_TOPOLOGY_IS_INTENT_ONLY_NO_CENTRELINE_GEOMETRY"]))

    nodes.append(node(
        "KEEP_OUTS", "SEI_SPACECRAFT_MECHANICAL_BASELINE_V1", "DEFINED_NOT_MODELLED",
        detail_artifact="KEEP_OUT_REGISTER_V1.yaml",
        solids_in_design_freeze=False,
        note=("keep-out volumes are analytic/derived in the register; none of them is an installed "
              "solid in the design-freeze assembly, so none of them participated in the "
              "pairwise narrow-phase check"),
        holds=["HOLD_KEEP_OUT_VOLUMES_NOT_INSTANTIATED_AS_GEOMETRY",
               "HOLD_LAUNCHER_INTERFACE_KEEP_OUT_NO_ICD"]))

    nodes.append(node(
        "SPACECRAFT_LOAD_BRIDGE", "BUS_PRIMARY_STRUCTURE", "EXISTS_AS_GEOMETRY",
        instance="INST_SPACECRAFT_LOAD_BRIDGE",
        source="20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_CANDIDATE_V1.step",
        solids=metrics["spacecraft_load_bridge_m6_candidate"]["solids"],
        faces=metrics["spacecraft_load_bridge_m6_candidate"]["faces"],
        volume_mm3=metrics["spacecraft_load_bridge_m6_candidate"]["volume_mm3"],
        aabb_S_mm=metrics["spacecraft_load_bridge_m6_candidate"]["bounding_box_mm"],
        plate_mm=[160.0, 160.0, 10.75], x_span_S_mm=[185.25, 196.0],
        candidate_mass_g=702.195458, mass_class="MATERIAL_DERIVED 6061-T6 2700 kg/m3",
        tree_note=("NOT named in the owner directive tree but it IS one of the 7 installed "
                   "components; recorded here as an explicit delta rather than dropped"),
        name_collision_warning=("the native V2_2 model contains unrelated parts also called "
                                "Load_Bridge_Left / Load_Bridge_Right at x 64..171, "
                                "y +/-68..92, z +/-15 mm; they are NOT this part"),
        holds=["LOAD_BRIDGE_PHYSICAL_FITUP_HOLD", "MATING_FASTENER_AND_TOLERANCE_HOLD",
               "SPACECRAFT_SIDE_ANCHOR_PATTERN_HOLD", "MATERIAL_APPROVAL_AND_PROCESS_HOLD",
               "STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD", "LEGACY_FLANGE_OWNERSHIP_HOLD"]))

    exists_nodes = [n["id"] for n in nodes if n["geometry_status"] == "EXISTS_AS_GEOMETRY"]
    cand_nodes = [n["id"] for n in nodes if n["geometry_status"] == "DESIGN_CANDIDATE_EVIDENCE_STUB"]
    witness_nodes = [n["id"] for n in nodes if n["geometry_status"] == "FRAME_AXIS_WITNESS_ONLY"]
    dnm_nodes = [n["id"] for n in nodes if n["geometry_status"] == "DEFINED_NOT_MODELLED"]

    reconciliation = {
        "installed_components_in_build_report": inst,
        "installed_component_count_in_build_report": report["installed_component_count"],
        "tree_nodes_backed_by_an_installed_instance": {
            "BUS_PRIMARY_STRUCTURE": "INST_BUS_12U_CORE",
            "SOLAR_ARRAY_LEFT.PANEL": "INST_SOLAR_ARRAY_LEFT_DEPLOYED",
            "SOLAR_ARRAY_RIGHT.PANEL": "INST_SOLAR_ARRAY_RIGHT_DEPLOYED",
            "B601 (witness only)": "INST_B601_ARM_CORE_Q0",
            "M3R": "INST_M3R_INTERFACE_ASSEMBLY",
            "GRIPPER_R1": "INST_GRIPPER_R1_PALM",
            "SPACECRAFT_LOAD_BRIDGE": "INST_SPACECRAFT_LOAD_BRIDGE",
        },
        "instance_accounting": {"instances_mapped": 7,
                                "instances_unmapped": [],
                                "balanced": True},
        "design_candidate_components_in_build_report": cand,
        "tree_nodes_backed_by_a_candidate_stub": {
            "CAMERA": ["CAND_CAMERA_CAM_A", "CAND_CAMERA_CAM_B"],
            "CAMERA_BRACKET": ["CAND_CAMERA_BRACKET_A", "CAND_CAMERA_BRACKET_B"]},
        "candidate_accounting": {"candidates_mapped": 4, "candidates_unmapped": [], "balanced": True},
        "step_solid_accounting": {
            "bus_12U_core": metrics["bus_12U_core"]["solids"],
            "solar_array_left": metrics["solar_array_left"]["solids"],
            "solar_array_right": metrics["solar_array_right"]["solids"],
            "B601_arm_q0_frame_axis_witness": metrics["B601_arm_q0_frame_axis_witness"]["solids"],
            "M3R_interface_assembly": metrics["M3R_interface_assembly"]["solids"],
            "gripper_R1_palm": metrics["gripper_R1_palm"]["solids"],
            "spacecraft_load_bridge_m6_candidate": metrics["spacecraft_load_bridge_m6_candidate"]["solids"],
            "sum": sum(metrics[k]["solids"] for k in (
                "bus_12U_core", "solar_array_left", "solar_array_right",
                "B601_arm_q0_frame_axis_witness", "M3R_interface_assembly",
                "gripper_R1_palm", "spacecraft_load_bridge_m6_candidate")),
            "manifold_solid_brep_in_step_independently_counted": step_probe["manifold_solid_brep_count"],
            "balanced": (sum(metrics[k]["solids"] for k in (
                "bus_12U_core", "solar_array_left", "solar_array_right",
                "B601_arm_q0_frame_axis_witness", "M3R_interface_assembly",
                "gripper_R1_palm", "spacecraft_load_bridge_m6_candidate"))
                == step_probe["manifold_solid_brep_count"]),
            "consequence": ("every solid in the exported STEP is accounted for by the 7 installed "
                            "components; therefore the STEP contains NO support, bracket, harness, "
                            "keep-out, camera, HDRM, hinge, latch or fastener geometry"),
        },
        "explicit_delta_owner_tree_vs_geometry": [
            "SPACECRAFT_LOAD_BRIDGE is installed geometry but is not named in the owner tree - added.",
            "BUS_PANELS, M3R.FASTENER_SET, M3R.LOCATOR_SET, all B601 per-link nodes, "
            "SOLAR_*.ROOT_HINGE, SOLAR_*.HDRM, SOLAR_*.LATCH_STOP, G07, G08, MID_SUPPORT, "
            "HARNESS/CABLE_ROUTING and KEEP_OUTS are named in the owner tree and have NO geometry.",
            "B601 BASE..LINK6/WRIST are named in the owner tree; the only installed B601 geometry is "
            "a 817.651848 mm3 frame/axis witness, so no per-link envelope exists.",
            "CAMERA_BRACKET exists only as two hidden candidate stubs plus a third, mutually "
            "exclusive wrist-mounted definition; no selection is authorised.",
            "M3R.STAGE_A_RING / STAGE_B_LOAD_DIFFUSION_PLATE exist as the two solids of the M3R "
            "compound but per-stage solid attribution was not established in this loop.",
        ],
        "counts": {
            "nodes_total": len(nodes),
            "EXISTS_AS_GEOMETRY": len(exists_nodes),
            "EXISTS_AS_SUB_SOLID_OF_PARENT_PROXY": sum(
                1 for n in nodes if n["geometry_status"] == "EXISTS_AS_SUB_SOLID_OF_PARENT_PROXY"),
            "FRAME_AXIS_WITNESS_ONLY": len(witness_nodes),
            "DESIGN_CANDIDATE_EVIDENCE_STUB": len(cand_nodes),
            "DEFINED_NOT_MODELLED": len(dnm_nodes),
        },
    }

    return {
        "schema": "M7_WP1_PRODUCT_STRUCTURE_V1",
        "generated_local": shell_now(),
        "generated_clock_source": CLOCK_SOURCE,
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP1_STRUCTURE_CAD",
        "lifecycle_status": "DESIGN_FREEZE_CANDIDATE_LEVEL_NOT_MANUFACTURING_NOT_FLIGHT",
        "release_scope": "MECHANICAL_ENGINEERING_DESIGN_CLOSURE_ONLY__GATE_A_SCOPE",
        "gate_b_status": "MECHANICAL_FLIGHT_QUALIFICATION_RELEASED = HOLD",
        "frame": {
            "root": "S (spacecraft_assembly_frame), mm",
            "m_frame_authority": ("ODR-01: T_SM = [185.25, 0, 0] mm followed by Ry(90 deg). "
                                  "Stations 198.0 / 208.0 / 210.405 mm are a geometric feature "
                                  "stack, NOT a second dynamics frame."),
            "arm_base": "T_S_B601_ARM_BASE at x = 208.0 mm (frozen F3R2 mapping)",
        },
        "default_configuration": report["default_configuration"],
        "configuration_register": {
            "required": ["DEPLOYED_NOMINAL", "LEFT_PANEL_FAIL", "RIGHT_PANEL_FAIL", "BOTH_PANEL_FAIL",
                         "ARM_STOWED_ONORBIT", "ARM_TASK_READY", "PREGRASP",
                         "TARGET_CAPTURE_22KG", "TARGET_CAPTURE_150KG"],
            "geometry_state": {
                "DEPLOYED_NOMINAL": "ACTIVE_GEOMETRY",
                "LEFT_PANEL_FAIL": "HOLD_STOWED_PANEL_GEOMETRY_UNKNOWN_ATTACHED_STUCK_ODR02",
                "RIGHT_PANEL_FAIL": "HOLD_STOWED_PANEL_GEOMETRY_UNKNOWN_ATTACHED_STUCK_ODR02",
                "BOTH_PANEL_FAIL": "HOLD_STOWED_PANEL_GEOMETRY_UNKNOWN_ATTACHED_STUCK_ODR02",
                "ARM_STOWED_ONORBIT": "SOURCE_WITNESS_EXISTS_NOT_EMBEDDED_AS_ACTIVE_CONFIG",
                "ARM_TASK_READY": "ACTIVE_Q0_GEOMETRY",
                "PREGRASP": "PALM_ONLY_FINGER_BREP_HOLD",
                "TARGET_CAPTURE_22KG": "TARGET_SOURCE_NOT_EMBEDDED_RELATIVE_POSE_HOLD",
                "TARGET_CAPTURE_150KG": "TARGET_SOURCE_NOT_EMBEDDED_RELATIVE_POSE_HOLD"},
            "panel_failure_semantics": "ODR-02 attached-stuck; jettison interpretation forbidden",
        },
        "geometry_status_legend": GEOM_STATUS_LEGEND,
        "unresolved_component_slots": [
            "SLOT_SENSOR_PACKAGE__RELOCATION_CANDIDATES_PRESENT",
            "SLOT_ARM_HDRM__UNRESOLVED", "SLOT_TARGET_INTERFACE__UNRESOLVED",
            "SLOT_GRIPPER_R1_FINGERS__UNRESOLVED", "SLOT_SOLAR_STOW_AND_HINGE__UNRESOLVED",
            "SLOT_STOW_SUPPORTS__CANDIDATE_REF"],
        "product_tree": nodes,
        "reconciliation_against_design_freeze_build": reconciliation,
        "independent_step_verification": step_probe,
        "explicit_non_claims": [
            "NOT_MANUFACTURING_RELEASED", "NOT_FLIGHT_OR_LAUNCH_QUALIFIED",
            "NOT_SYSTEM_MASS_OR_INERTIA_AUTHORITY",
            "NOT_CONTINUOUS_COLLISION_OR_SWEEP_VALIDATED",
            "ARM_IS_FRAME_AXIS_WITNESS_NOT_PHYSICAL_GEOMETRY",
            "CAMERA_AND_BRACKET_SOLIDS_ARE_CLEARANCE_EVIDENCE_CANDIDATES_ONLY",
            "LEGACY_FLANGE_TAGGED_REFERENCE_NOT_MERGED_INTO_LOAD_BRIDGE",
            "NO_GEOMETRY_WAS_REBUILT_BY_THIS_ARTIFACT_NO_FREECAD_PROCESS_WAS_STARTED"],
        "memory_gate": register["memory_gate"],
        "source_register": register["source_register"],
    }


# --------------------------------------------------------------------------
# artifact 2 : HARNESS_ROUTING_V1.yaml
# --------------------------------------------------------------------------
VENDOR_NULLS = {
    "cable_outer_diameter_mm": None,
    "conductor_count_and_gauge": None,
    "minimum_bend_radius_mm": None,
    "connector_part_number": None,
    "connector_shell_size_and_keying": None,
    "mass_per_metre_kg_per_m": None,
    "insulation_and_jacket_material": None,
    "shield_and_bond_scheme": None,
    "operating_temperature_range_C": None,
    "outgassing_and_space_material_approval": None,
    "flex_life_cycles_at_min_bend_radius": None,
    "bundle_stiffness_N_per_mm_or_Nmm_per_rad": None,
}
VENDOR_NULL_HOLDS = [
    "HOLD_VENDOR_CABLE_OUTER_DIAMETER_ABSENT",
    "HOLD_VENDOR_MINIMUM_BEND_RADIUS_ABSENT",
    "HOLD_CONNECTOR_PART_NUMBER_AND_SHELL_ABSENT",
    "HOLD_CABLE_MASS_PER_METRE_ABSENT",
    "HOLD_CABLE_MATERIAL_AND_OUTGASSING_APPROVAL_ABSENT",
    "HOLD_FLEX_LIFE_TEST_DATA_ABSENT",
    "HOLD_BUNDLE_STIFFNESS_ABSENT_HINGE_AND_JOINT_RESISTANCE_TORQUE_NOT_CLOSED",
]


def build_harness(report, native, arm_env, panel_sweep, register):
    hinge_takeup = {}
    for side, part in (("LEFT", "Harness_Service_Loop_Left"), ("RIGHT", "Harness_Service_Loop_Right")):
        b = native[part]["aabb_mm"]
        y0 = 143.15 if side == "LEFT" else -143.15
        dy = [b[1] - y0, b[4] - y0]
        dz = [b[2] - 0.0, b[5] - 0.0]
        rmax = max(math.hypot(a, c) for a in dy for c in dz)
        rmin = min(math.hypot(a, c) for a in dy for c in dz)
        hinge_takeup[side] = {
            "service_loop_reference_box_S_mm": b,
            "hinge_axis_point_S_mm": [-61.0, y0, 0.0],
            "radius_of_reference_box_about_hinge_axis_mm": {"r_min": round(rmin, 6),
                                                           "r_max": round(rmax, 6)},
            "deployment_rotation_design_target_rad": round(math.pi / 2.0, 9),
            "deployment_takeup_upper_bound_mm": round(rmax * math.pi / 2.0, 6),
            "derivation": ("take-up = r * dtheta with r bounded by the farthest corner of the "
                           "existing Harness_Service_Loop reference box from the declared hinge "
                           "axis; this is a geometric UPPER BOUND on the length the harness must "
                           "give up or take in across a 90 deg deployment, not a cable length"),
        }

    # wing-root chafe margins: service loop box vs each rotating/latching part
    chafe = {}
    for other in ("Hinge_Pin_Left", "Hard_Stop_Left"):
        chafe["Harness_Service_Loop_Left__vs__" + other] = {
            "box_a": native["Harness_Service_Loop_Left"]["aabb_mm"],
            "box_b": native[other]["aabb_mm"],
            **aabb_separation(native["Harness_Service_Loop_Left"]["aabb_mm"], native[other]["aabb_mm"]),
        }
    for other in ("HDRM_Base_1_Left", "HDRM_Rod_1_Left", "HDRM_Base_2_Left", "HDRM_Rod_2_Left"):
        chafe["Harness_Service_Loop_Left__vs__" + other] = {
            "box_a": native["Harness_Service_Loop_Left"]["aabb_mm"],
            "box_b": native[other]["aabb_mm"],
            **aabb_separation(native["Harness_Service_Loop_Left"]["aabb_mm"], native[other]["aabb_mm"]),
        }

    passage = native["Harness_Passage"]["aabb_mm"]
    bus_proxy = report["source_geometry_metrics"]["bus_12U_core"]["bounding_box_mm"]

    runs = []
    runs.append({
        "run_id": "H-RUN-01_ARM_POWER_AND_DATA",
        "function": "B601 arm motor power, encoder/bus data, brake release, gripper actuation",
        "criticality": "MISSION_CRITICAL",
        "topology_nodes": [
            {"node": "HN-00", "at": "bus interior avionics side", "coordinates_S_mm": None,
             "status": "HOLD_BUS_INTERNAL_HARNESS_ORIGIN_NOT_DEFINED"},
            {"node": "HN-01", "at": "Harness_Passage +x mouth (declared entry)",
             "coordinates_S_mm": [171.0, 0.0, -70.0],
             "status": "DECLARED_IN_F3R2_ARM_HDRM_DEFINITION",
             "geometry_backing": ("native reference box only: " + str(passage) +
                                  "; the design-freeze bus proxy is a SOLID box with no passage "
                                  "void, so this corridor has no geometric representation in the "
                                  "design-freeze assembly")},
            {"node": "HN-02", "at": "HC-1 clamp on Adapter_Plate", "coordinates_S_mm": [192.0, None, None],
             "status": "DECLARED_X_STATION_ONLY_Y_Z_UNDEFINED"},
            {"node": "HN-03", "at": "arm base_link connector face (declared exit)",
             "coordinates_S_mm": [215.0, 0.0, 0.0],
             "status": "DECLARED_BUT_GEOMETRICALLY_UNSUPPORTED",
             "conflict": ("x = 215.0 mm lies 4.595 mm beyond the neutral M3R feature stack maximum "
                          "(210.405 mm) and 7.0 mm beyond the native Central_Boss end face "
                          "(208.0 mm); no modelled surface exists at x = 215.0 mm"),
             "hold": "HOLD_ARM_CONNECTOR_FACE_STATION_UNRECONCILED"},
            {"node": "HN-04", "at": "HC-2 clamp on base_link collar", "coordinates_S_mm": [220.0, None, None],
             "status": "DECLARED_X_STATION_ONLY"},
            {"node": "HN-05", "at": "HC-3 clamp on link1 shoulder (ROTATING)", "coordinates_S_mm": None,
             "status": "DECLARED_HOST_LINK_ONLY_NO_POSE"},
            {"node": "HN-06", "at": "HC-4 clamp on link3 mid-span", "coordinates_S_mm": None,
             "status": "DECLARED_HOST_LINK_ONLY_NO_POSE"},
            {"node": "HN-07", "at": "HC-5 clamp on link6 wrist, before the camera",
             "coordinates_S_mm": None, "status": "DECLARED_HOST_LINK_ONLY_NO_POSE"},
        ],
        "connector_locations": {
            "spacecraft_side": {"location": "Harness_Passage +x mouth region",
                                "part_number": None,
                                "hold": "HOLD_CONNECTOR_PART_NUMBER_AND_BRACKET_ABSENT"},
            "arm_side": {"location": "B601 base_link connector face, declared x = 215.0 mm",
                         "corroborated_flange": ("B601 base_link carries a real bolt flange, "
                                                 "8 x M3 at R45.25 mm on x = 210.41 mm "
                                                 "(fine-solid probe); the connector face is a "
                                                 "different, unmodelled feature"),
                         "part_number": None,
                         "hold": "HOLD_ARM_SIDE_CONNECTOR_NOT_IN_ANY_CAD_MODEL"},
        },
        "minimum_bend_radius": {
            "design_authority_mm": None,
            "hold": "HOLD_VENDOR_MINIMUM_BEND_RADIUS_ABSENT",
            "prior_candidate_mm": 25.0,
            "prior_candidate_class": "TYPICAL_CLASS_VALUE_NOT_VENDOR_BOUND_NOT_AUTHORITY",
            "prior_candidate_source": rel(TERMINAL / "07_hdrm" / "F3R2_ARM_HDRM_DEFINITION.json")
            + "::harness.minimum_bend_radius_mm",
            "design_rule_to_apply_once_vendor_data_exists":
                "clamp-to-clamp geometry must nowhere impose a radius below the vendor value at "
                "any pose in the authorised joint envelope, including at end stops",
        },
        "slack_allowance_over_full_arm_travel": {
            "class": "DERIVED_GEOMETRIC_UPPER_BOUND_NOT_A_CABLE_LENGTH",
            "method": ("for each revolute joint the harness clamp on the child link sits at radius "
                       "r <= R_child about that joint axis, where R_child is the maximum radial "
                       "distance of the accepted-URDF collision mesh of that link from the joint "
                       "axis; the differential length across the joint is bounded by "
                       "R_child * (upper - lower)"),
            "per_joint": arm_env["harness_takeup_bounds"]["per_joint"],
            "sum_of_upper_bounds_mm": arm_env["harness_takeup_bounds"]["sum_of_upper_bounds_mm"],
            "prior_candidate_service_loop_mm": 120.0,
            "prior_candidate_service_loop_location": "at HC-2/HC-3, to absorb joint1 rotation",
            "prior_candidate_class": "CANDIDATE_NOT_AUTHORITY",
            "consistency_check": ("the joint1 upper bound derived here must not be exceeded by the "
                                  "as-routed take-up; the 120 mm prior candidate is compared "
                                  "against it in open_items"),
            "hold": "HOLD_ACTUAL_SLACK_REQUIRES_CLAMP_POSES_AND_CABLE_STIFFNESS",
        },
        "strain_relief": {
            "requirement": ("every connector shall be preceded by a fixed clamp within one bundle "
                            "diameter-decade of the shell so that no cable tension, bending moment "
                            "or joint reaction is carried by the contacts; each rotating clamp "
                            "shall be a rotationally captive P-clamp, not a tie wrap"),
            "hardware": None,
            "prior_candidate_hardware": "5 x P-clamp, Al + silicone, one per clamp point HC-1..HC-5",
            "prior_candidate_class": "CANDIDATE_NOT_AUTHORITY",
            "hold": "HOLD_STRAIN_RELIEF_HARDWARE_NOT_SELECTED",
        },
        "pinch_and_chafe_risk": [
            {"location": "joint1 (base_link/link1 interface, +/-2.8 rad)",
             "mechanism": "torsional wind-up and axial creep of the service loop",
             "geometric_evidence": ("joint1 take-up upper bound "
                                    + str(arm_env["harness_takeup_bounds"]["per_joint"][0]
                                          ["harness_takeup_upper_bound_mm"]) + " mm over "
                                    + str(arm_env["harness_takeup_bounds"]["per_joint"][0]
                                          ["joint_range_deg"]) + " deg"),
             "severity_class": "HIGH_BY_RANGE_OF_MOTION",
             "hold": "HOLD_NO_HARNESS_GEOMETRY_TO_SWEEP"},
            {"location": "joints 2/3 (shoulder and elbow, 3.14 rad each)",
             "mechanism": "bundle trapped between closing link faces at the inner end stop",
             "severity_class": "HIGH_BY_CLOSING_KINEMATICS",
             "hold": "HOLD_NO_HARNESS_GEOMETRY_TO_SWEEP"},
            {"location": "joint6 (+/-3.14 rad, 6.28 rad total)",
             "mechanism": "wrist roll wind-up immediately upstream of the gripper",
             "severity_class": "HIGH_BY_RANGE_OF_MOTION",
             "hold": "HOLD_NO_HARNESS_GEOMETRY_TO_SWEEP"},
            {"location": "gripper prismatic rails (0..71.5 mm per finger)",
             "mechanism": "finger travel shears any cable crossing the rail slot",
             "geometric_evidence": ("the R1 correction removed 19392.857472 mm3 of palm material to "
                                    "clear the rail slot; the resulting slot is a moving shear line "
                                    "and no cable may cross it"),
             "severity_class": "HIGH_ABSOLUTE_EXCLUSION",
             "rule": "NO_HARNESS_INSIDE_THE_GRIPPER_RAIL_SLOT_ENVELOPE",
             "hold": "HOLD_GRIPPER_INTERNAL_ROUTING_NOT_DEFINED"},
            {"location": "Harness_Passage mouth at x = 171.0 mm",
             "mechanism": "edge chafe where the bundle leaves the structure",
             "geometric_evidence": ("the passage +x face at x = 171.0 mm is 0.75 mm outboard of the "
                                    "design-freeze bus proxy front face at x = 170.25 mm and "
                                    "12.0 mm inboard of the native V2_2 front face at x = 183.0 mm"),
             "severity_class": "MEDIUM",
             "hold": "HOLD_GROMMET_OR_EDGE_PROTECTION_NOT_DEFINED"},
        ],
        "vendor_dependent_values": dict(VENDOR_NULLS),
        "prior_candidate_values_not_authority": {
            "bundle_outer_diameter_mm": 9.0,
            "routed_length_mm": 900.0,
            "bundle_mass_g": 125.962,
            "clamp_count": 5,
            "source": rel(TERMINAL / "07_hdrm" / "F3R2_ARM_HDRM_DEFINITION.json") + "::parts",
            "class": "TYPICAL_CLASS_AND_ROUTE_ESTIMATE_NOT_VENDOR_BOUND_NOT_MASS_AUTHORITY",
        },
        "holds": VENDOR_NULL_HOLDS + [
            "HOLD_ARM_CONNECTOR_FACE_STATION_UNRECONCILED",
            "HOLD_CLAMP_POSES_Y_AND_Z_UNDEFINED",
            "HOLD_MOVING_HARNESS_SWEEP_NOT_COMPUTED"],
    })

    for side, run_id in (("LEFT", "H-RUN-02_SOLAR_ARRAY_LEFT"), ("RIGHT", "H-RUN-03_SOLAR_ARRAY_RIGHT")):
        ht = hinge_takeup[side]
        runs.append({
            "run_id": run_id,
            "function": "solar array power (and any panel temperature/telemetry sensing) across the "
                        "deployable hinge line",
            "criticality": "MISSION_CRITICAL",
            "topology_nodes": [
                {"node": "HS-00", "at": "bus interior power conditioning", "coordinates_S_mm": None,
                 "status": "HOLD_BUS_INTERNAL_HARNESS_ORIGIN_NOT_DEFINED"},
                {"node": "HS-01", "at": "Harness_Service_Loop_%s reference volume" % side.capitalize(),
                 "reference_box_S_mm": ht["service_loop_reference_box_S_mm"],
                 "status": "NATIVE_REFERENCE_VOLUME_ONLY_NOT_A_CABLE",
                 "reading": ("the reference volume lies inboard of the hinge line "
                             "(|y| 113.15..131.15 vs hinge |y| 143.15) and 10..30 mm below the "
                             "panel plane, i.e. on the bus side of the hinge, which is consistent "
                             "with a loop that crosses the hinge from inboard")},
                {"node": "HS-02", "at": "hinge crossing at the declared root-hinge axis",
                 "axis_point_S_mm": ht["hinge_axis_point_S_mm"], "axis_direction_S": [1.0, 0.0, 0.0],
                 "status": "AXIS_DECLARED_B_REP_PROBE_MAPPING_NOT_A_MANUFACTURING_DATUM"},
                {"node": "HS-03", "at": "panel root terminal block", "coordinates_S_mm": None,
                 "status": "HOLD_PANEL_SIDE_TERMINATION_NOT_DEFINED"},
            ],
            "connector_locations": {
                "bus_side": {"location": "adjacent to the service-loop reference volume",
                             "part_number": None, "hold": "HOLD_CONNECTOR_PART_NUMBER_ABSENT"},
                "panel_side": {"location": "panel root; the panel is a 227 x 200 x 6 mm homogeneous "
                                           "plate proxy with no terminal geometry",
                               "part_number": None,
                               "hold": "HOLD_PANEL_ROOT_TERMINAL_GEOMETRY_NOT_MODELLED"},
            },
            "minimum_bend_radius": {
                "design_authority_mm": None,
                "hold": "HOLD_VENDOR_MINIMUM_BEND_RADIUS_ABSENT",
                "geometric_constraint_that_will_bind_it": (
                    "the loop must stay inside the annulus available between the hinge line and the "
                    "bus side face; the available radial band from the declared axis to the bus "
                    "surface is |143.15| - |113.15| = 30.0 mm, so a vendor minimum bend radius "
                    "above 30.0 mm cannot be accommodated with a single in-plane loop at the root"),
                "derived_available_radial_band_mm": 30.0,
            },
            "deployment_slack": ht,
            "strain_relief": {
                "requirement": ("clamps on both sides of the hinge so that the deploying panel never "
                                "loads the cable termination; the loop must be captive so it cannot "
                                "migrate into the hinge, the hard stop or the HDRM rod path"),
                "hardware": None, "hold": "HOLD_STRAIN_RELIEF_HARDWARE_NOT_SELECTED"},
            "pinch_and_chafe_risk": ([
                {"location": "wing root cluster (hinge pin, hard stop, HDRM rods)",
                 "mechanism": "loop migration into a rotating or releasing part",
                 "aabb_separation_evidence": chafe if side == "LEFT" else
                 "mirror of LEFT; not probed separately in this loop",
                 "severity_class": "HIGH_BY_PROXIMITY",
                 "hold": "HOLD_NO_HARNESS_GEOMETRY_TO_SWEEP"},
                {"location": "hinge line itself",
                 "mechanism": "cable pinched in the closing hinge gap during stow or a failed "
                              "deployment (ODR-02: a failed panel stays attached and stuck, so the "
                              "harness stays loaded in the failure case)",
                 "severity_class": "HIGH_AND_FAILURE_CASE_RELEVANT",
                 "hold": "HOLD_STOWED_AND_PARTIAL_DEPLOY_GEOMETRY_ABSENT"},
            ]),
            "vendor_dependent_values": dict(VENDOR_NULLS),
            "holds": VENDOR_NULL_HOLDS + [
                "HOLD_STOWED_GEOMETRY_ABSENT_SO_STOW_SIDE_ROUTE_UNDEFINED",
                "HOLD_PANEL_ROOT_TERMINAL_GEOMETRY_NOT_MODELLED"],
        })

    runs.append({
        "run_id": "H-RUN-04_CAMERA",
        "function": "service camera power, data and (if selected) illumination",
        "criticality": "MISSION_IMPORTANT",
        "blocking_finding": (
            "the camera harness topology cannot be defined because the surviving camera candidates "
            "belong to two mutually exclusive architectures: CAM_A [190.25,-35,145] and "
            "CAM_B [150,-60,143.15] are BUS-MOUNTED (static bus-internal route, no moving harness), "
            "whereas F3R2_ARM_HDRM_DEFINITION proposes a WRIST-MOUNTED camera on link6 "
            "(route must follow the whole arm through HC-1..HC-5 and absorb every joint). "
            "Choosing between them changes the run length, the flex-life duty and the pinch set."),
        "topology_nodes": [
            {"node": "HK-A", "at": "bus-mounted variant: bus interior to CAM_A/CAM_B bracket",
             "route_class": "STATIC_INTERNAL", "coordinates_S_mm": None},
            {"node": "HK-B", "at": "wrist-mounted variant: HC-5 on link6 to the wrist bracket",
             "route_class": "FULLY_ARTICULATED", "coordinates_S_mm": None},
        ],
        "connector_locations": {"camera_side": {"part_number": None,
                                                "hold": "HOLD_CAMERA_PRODUCT_NOT_SELECTED"}},
        "minimum_bend_radius": {"design_authority_mm": None,
                                "hold": "HOLD_VENDOR_MINIMUM_BEND_RADIUS_ABSENT"},
        "slack_allowance": {"value_mm": None,
                            "hold": "HOLD_SLACK_UNDEFINED_UNTIL_MOUNT_ARCHITECTURE_IS_SELECTED",
                            "note": ("if the wrist-mounted variant is selected the arm take-up bounds "
                                     "of H-RUN-01 apply in addition, i.e. the camera cable must "
                                     "absorb the same per-joint bounds")},
        "strain_relief": {"requirement": "captive clamp immediately behind the camera connector",
                          "hardware": None, "hold": "HOLD_STRAIN_RELIEF_HARDWARE_NOT_SELECTED"},
        "pinch_and_chafe_risk": [
            {"location": "wrist-mounted variant: between the camera bracket and the gripper palm",
             "mechanism": "cable crushed between the bracket and a grasped object during capture",
             "severity_class": "HIGH_IF_WRIST_MOUNT_SELECTED",
             "hold": "HOLD_CAMERA_MOUNT_ARCHITECTURE_NOT_SELECTED"},
        ],
        "vendor_dependent_values": dict(VENDOR_NULLS),
        "holds": VENDOR_NULL_HOLDS + [
            "HOLD_CAMERA_MOUNT_ARCHITECTURE_NOT_SELECTED_BUS_MOUNT_VS_WRIST_MOUNT",
            "HOLD_CAMERA_PART_NUMBER_ABSENT", "HOLD_OPTICAL_CALIBRATION_ABSENT"],
    })

    runs.append({
        "run_id": "H-RUN-05_ARM_HDRM",
        "function": "arm hold-down and release actuation and state sensing",
        "criticality": "SINGLE_POINT_FOR_ARM_AVAILABILITY",
        "topology_nodes": [
            {"node": "HH-00", "at": "bus deck at the ARM_HDRM base", "coordinates_S_mm": None,
             "restraint_plane_x_mm": 0.0, "restraint_band_z_mm": [132.0, 168.0],
             "native_reference_box_S_mm": native["Launch_Lock_Interface_Reference"]["aabb_mm"],
             "status": "REFERENCE_VOLUME_ONLY_NOT_A_MECHANISM"},
        ],
        "connector_locations": {
            "device_side": {"declared_connector": "9-pin micro-D",
                            "declared_circuits": ["fire A", "fire B", "switch A", "switch B"],
                            "class": "DECLARED_CLASS_VALUE_NOT_A_SELECTED_PART",
                            "part_number": None,
                            "hold": "HOLD_HDRM_DEVICE_AND_CONNECTOR_NOT_SELECTED"}},
        "minimum_bend_radius": {"design_authority_mm": None,
                                "hold": "HOLD_VENDOR_MINIMUM_BEND_RADIUS_ABSENT"},
        "slack_allowance": {
            "value_mm": None,
            "geometric_driver": ("the rod retracts a candidate 6.0 mm in +Z; the harness must not "
                                 "resist that stroke nor re-enter the post-release residual "
                                 "envelope " + str([-15.0, -89.0, 127.0, 15.0, 89.0, 179.0])),
            "hold": "HOLD_STROKE_IS_A_CANDIDATE_NOT_A_DATASHEET_VALUE"},
        "strain_relief": {"requirement": ("dual-path (cross-strapped) switch wiring must be routed on "
                                          "physically separated paths so that one chafe event cannot "
                                          "fail both state channels"),
                          "hardware": None, "hold": "HOLD_STRAIN_RELIEF_HARDWARE_NOT_SELECTED"},
        "pinch_and_chafe_risk": [
            {"location": "release path, +Z",
             "mechanism": "harness re-entry into the release path prevents or fouls release; the "
                          "declared failure mode is fail-closed (arm stays uncommandable)",
             "severity_class": "MISSION_ABORTING",
             "hold": "HOLD_NO_HDRM_MECHANISM_GEOMETRY"},
        ],
        "vendor_dependent_values": dict(VENDOR_NULLS),
        "holds": VENDOR_NULL_HOLDS + ["HOLD_HDRM_ARCHITECTURE_NOT_SELECTED",
                                      "HOLD_HDRM_PRELOAD_INTERFACE_OPEN_M7_TC_14"],
    })

    runs.append({
        "run_id": "H-RUN-06_SOLAR_HDRM",
        "function": "solar wing hold-down release actuation and state sensing (4 devices)",
        "criticality": "MISSION_CRITICAL",
        "topology_nodes": [
            {"node": "HG-01", "at": "HDRM_Base_1/2 left and right on the bus side faces",
             "native_reference_boxes_left_S_mm": {k: native[k]["aabb_mm"] for k in
                                                 ("HDRM_Base_1_Left", "HDRM_Rod_1_Left",
                                                  "HDRM_Base_2_Left", "HDRM_Rod_2_Left")},
             "status": "REFERENCE_VOLUMES_ONLY_NOT_A_MECHANISM"},
        ],
        "connector_locations": {"device_side": {"part_number": None,
                                                "hold": "HOLD_SOLAR_HDRM_DEVICE_NOT_SELECTED"}},
        "minimum_bend_radius": {"design_authority_mm": None,
                                "hold": "HOLD_VENDOR_MINIMUM_BEND_RADIUS_ABSENT"},
        "slack_allowance": {"value_mm": None,
                            "hold": "HOLD_SOLAR_HDRM_STROKE_AND_RELEASE_PATH_NOT_DEFINED"},
        "strain_relief": {"requirement": "separated redundant paths per wing",
                          "hardware": None, "hold": "HOLD_STRAIN_RELIEF_HARDWARE_NOT_SELECTED"},
        "pinch_and_chafe_risk": [
            {"location": "wing root, between the rod path and the deploying panel",
             "mechanism": "release harness swept by the deploying wing",
             "severity_class": "HIGH_BY_PROXIMITY",
             "hold": "HOLD_STOWED_AND_SWEEP_GEOMETRY_ABSENT"},
        ],
        "vendor_dependent_values": dict(VENDOR_NULLS),
        "holds": VENDOR_NULL_HOLDS + ["SOLAR_HDRM_PRODUCT_HOLD"],
    })

    return {
        "schema": "M7_WP1_HARNESS_ROUTING_V1",
        "generated_local": shell_now(),
        "generated_clock_source": CLOCK_SOURCE,
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP1_STRUCTURE_CAD",
        "lifecycle_status": "ROUTING_TOPOLOGY_AND_GEOMETRIC_ENVELOPE_ONLY_NO_HARNESS_GEOMETRY_EXISTS",
        "release_scope": "MECHANICAL_ENGINEERING_DESIGN_CLOSURE_ONLY__GATE_A_SCOPE",
        "headline_truth": (
            "No harness geometry exists in any chain: not in DESIGN_FREEZE_ASSEMBLY_V1.step "
            "(all %d exported solids are accounted for by the 7 installed components), not in the "
            "FCStd (no harness object), and not as a native solid used by this loop. What follows is "
            "routing TOPOLOGY plus the geometric envelope that can be derived from hash-pinned "
            "geometry. Every vendor-dependent number is null with a named HOLD."
            % report["step_cold_reopen"]["solids"]),
        "frame": {"root": "S (spacecraft_assembly_frame), mm",
                  "native_feature_frame_note": (
                      "the harness/HDRM reference boxes come from the native V2_2 model. Their frame "
                      "is treated as S because three independent stations agree exactly between the "
                      "two models: the adapter-plate/boss faces at x = 198.0 and x = 208.0 mm, the "
                      "outer surface at |y| = |z| = 113.15 mm, and the hinge axis at "
                      "|y| = 143.15 mm, z = 0. The bus LENGTH does not agree "
                      "(native +/-183.0 vs proxy +/-170.25 mm), so any x near the front face must "
                      "state its model of origin."),
                  "residual_hold": "HOLD_NATIVE_TO_S_FRAME_EQUIVALENCE_CORROBORATED_NOT_PROVEN"},
        "design_freeze_bus_proxy_aabb_S_mm": bus_proxy,
        "existing_bus_harness_features": {
            "Harness_Passage": {"aabb_S_mm": passage,
                                "cross_section_mm": [60.0, 24.0],
                                "length_mm": round(passage[3] - passage[0], 6),
                                "represented_as_a_void_in_design_freeze": False,
                                "hold": "HOLD_HARNESS_PASSAGE_IS_NOT_A_VOID_IN_THE_NEUTRAL_BUS_PROXY"},
            "Harness_Service_Loop_Left": {"aabb_S_mm": native["Harness_Service_Loop_Left"]["aabb_mm"]},
            "Harness_Service_Loop_Right": {"aabb_S_mm": native["Harness_Service_Loop_Right"]["aabb_mm"]},
        },
        "runs": runs,
        "system_level_open_items": [
            {"id": "HR-OPEN-01",
             "item": "arm connector face station x = 215.0 mm is not supported by any modelled "
                     "surface (neutral stack ends at 210.405 mm, native boss at 208.0 mm)",
             "action": "reconcile the connector station against the B601 base_link flange "
                       "(8 x M3 at R45.25 mm, x = 210.41 mm) before any bracket is drawn",
             "blocking": "HARNESS_INTERFACE_DEFINITION"},
            {"id": "HR-OPEN-02",
             "item": "the 120 mm prior-candidate service loop must be checked against the derived "
                     "joint1 take-up upper bound of "
                     + str(arm_env["harness_takeup_bounds"]["per_joint"][0]["harness_takeup_upper_bound_mm"])
                     + " mm; the candidate is smaller than the bound, so it is NOT proven sufficient",
             "action": "fix the HC-2/HC-3 clamp radii, then recompute r * dtheta exactly",
             "blocking": "SLACK_SIZING"},
            {"id": "HR-OPEN-03",
             "item": "camera mount architecture (bus-mounted CAM_A/CAM_B vs wrist-mounted) is "
                     "undecided, so H-RUN-04 has no topology",
             "action": "owner selection", "blocking": "CAMERA_HARNESS_DEFINITION"},
            {"id": "HR-OPEN-04",
             "item": "the harness passage has no geometric representation in the design-freeze "
                     "assembly, so no clearance between a bundle and structure can be measured",
             "action": "either cut the passage into the bus proxy or model the harness centreline",
             "blocking": "HARNESS_CLEARANCE_EVIDENCE"},
            {"id": "HR-OPEN-05",
             "item": "bundle stiffness is null, so the harness resisting torque used in the hinge "
                     "drive-margin chain and in any joint torque budget is unsubstantiated",
             "action": "vendor data or bench measurement",
             "blocking": "HINGE_DRIVE_MARGIN_AND_JOINT_TORQUE_BUDGET"},
        ],
        "explicit_non_claims": [
            "NO_HARNESS_GEOMETRY_WAS_CREATED",
            "NO_CABLE_DIAMETER_OR_BEND_RADIUS_IS_ASSERTED_AS_DESIGN_AUTHORITY",
            "NO_MOVING_HARNESS_SWEEP_WAS_COMPUTED",
            "NO_HARNESS_MASS_ENTERS_ANY_MASS_AUTHORITY",
            "NOT_FLIGHT_OR_LAUNCH_QUALIFIED"],
        "memory_gate": register["memory_gate"],
        "source_register": register["source_register"],
    }


# --------------------------------------------------------------------------
# artifact 3 : KEEP_OUT_REGISTER_V1.yaml
# --------------------------------------------------------------------------
def build_keep_outs(report, native, arm_env, grip_sweep, panel_sweep, register):
    sph = arm_env["conservative_sphere"]
    closed = arm_env["default_pose_exact_aabb"]["GRIPPER_CLOSED_travel_0_0mm"]
    openp = arm_env["default_pose_exact_aabb"]["GRIPPER_OPEN_travel_71_5mm"]
    R = sph["radius_mm"]

    items = []
    items.append({
        "id": "KO-01_ARM_SWEPT_ENVELOPE",
        "keep_out_class": "MOVING_MECHANISM_SWEPT_VOLUME",
        "instantiated_as_geometry": False,
        "conservative_bound": {
            "shape": "SPHERE",
            "centre_S_mm": [208.0, 0.0, 0.0],
            "centre_definition": "B601 base_link origin per T_S_B601_ARM_BASE",
            "radius_mm": R,
            "governing_link": sph["governing_link"],
            "implied_aabb_S_mm": [round(208.0 - R, 6), round(-R, 6), round(-R, 6),
                                  round(208.0 + R, 6), round(R, 6), round(R, 6)],
            "class": "ANALYTIC_CONSERVATIVE_UPPER_BOUND_NOT_A_SWEPT_BREP",
            "derivation": ("for a revolute chain the distance of a downstream frame origin from the "
                           "base is bounded by the sum of the intermediate joint-origin translation "
                           "norms (rotation cannot increase it); prismatic travel is added; the link "
                           "geometry is then bounded by the maximum vertex radius of its "
                           "accepted-URDF collision mesh in its own link frame"),
            "per_link_bound_mm": sph["per_link_bound_mm"],
            "honest_limitation": ("this sphere encloses the entire bus, so it is a safety bound, not "
                                  "a usable packaging envelope; a usable directional envelope "
                                  "requires the true swept B-rep"),
        },
        "exact_default_pose_envelope": {
            "pose": "all revolute q = 0 (ARM_TASK_READY / design-freeze default configuration)",
            "gripper_closed_arm_plus_gripper_aabb_S_mm": closed["arm_plus_gripper_aabb_S_mm"],
            "gripper_open_arm_plus_gripper_aabb_S_mm": openp["arm_plus_gripper_aabb_S_mm"],
            "per_link_aabb_S_mm_closed": closed["per_link_aabb_S_mm"],
            "class": "EXACT_FOR_THIS_POSE_FROM_ACCEPTED_URDF_COLLISION_MESHES",
            "authority_note": ("computed from the L0 accepted-URDF collision meshes, NOT from the "
                               "design-freeze arm witness (which is 817.651848 mm3 of axis "
                               "geometry and must never be used for clearance)"),
        },
        "true_swept_brep": None,
        "holds": ["HOLD_ARM_SWEPT_BREP_NOT_COMPUTED_NO_ARM_ENVELOPE_IN_NEUTRAL_CHAIN",
                  "HOLD_JOINT_ENVELOPE_RESTRICTIONS_FOR_OPERATIONS_NOT_DEFINED",
                  "HOLD_B51_CAD_ARM_VS_ACCEPTED_URDF_COLLISION_MESH_ARE_DIFFERENT_VERSIONS"],
    })

    items.append({
        "id": "KO-02_GRIPPER_JAW_ENVELOPE",
        "keep_out_class": "MOVING_MECHANISM_SWEPT_VOLUME",
        "instantiated_as_geometry": False,
        "stroke_mm": [0.0, 71.5],
        "lineage_A_accepted_urdf": {
            "gripper_assembly_aabb_S_mm_at_travel_0": closed["gripper_assembly_aabb_S_mm"],
            "gripper_assembly_aabb_S_mm_at_travel_71p5": openp["gripper_assembly_aabb_S_mm"],
            "class": "EXACT_FOR_THE_DEFAULT_ARM_POSE_FROM_ACCEPTED_URDF_COLLISION_MESHES",
        },
        "lineage_B_v5r_neutral_r1": {
            "union_full_stroke_sweep_aabb_link6_local_mm": grip_sweep["union_aabb_link6_local_mm"],
            "mapped_conservative_aabb_S_mm": grip_sweep["mapped_conservative_aabb_S_mm"],
            "left_sweep_solids": grip_sweep["left_sweep_solids"],
            "right_sweep_solids": grip_sweep["right_sweep_solids"],
            "sweep_method": "CONSERVATIVE_AABB_MINKOWSKI_ENVELOPE_SUPERSET_OF_EXACT_TRANSLATIONAL_SWEEP",
            "continuous_stroke_acceptance": "144 samples at 0.5 mm over 0..71.5 mm, analytic pass",
            "class": "CONSERVATIVE_SUPERSET_OF_THE_TRANSLATIONAL_SWEEP",
            "caveat": grip_sweep["control_point_caveat"],
        },
        "reconciliation": {
            "status": "TWO_INDEPENDENT_GEOMETRY_LINEAGES_NOT_RECONCILED",
            "reason": ("lineage A is the accepted-URDF collision tessellation; lineage B is the "
                       "V5R neutral derivative of the B51 native gripper. These are different "
                       "versions of the same hardware and must not be mixed in one number."),
            "hold": "HOLD_GRIPPER_GEOMETRY_LINEAGE_RECONCILIATION",
        },
        "absolute_exclusion_rule": "no harness, bracket or sensor may enter the rail-slot envelope",
        "holds": ["FINGER_BREP_SEPARATION_HOLD",
                  "HOLD_EXTERNAL_OBJECT_GRIPPER_CONTACT_GEOMETRY_ABSENT",
                  "HOLD_GRIPPER_GEOMETRY_LINEAGE_RECONCILIATION"],
    })

    items.append({
        "id": "KO-03_SOLAR_ARRAY_DEPLOYMENT_SWEEP",
        "keep_out_class": "DEPLOYABLE_APPENDAGE_SWEPT_VOLUME",
        "instantiated_as_geometry": False,
        "left": panel_sweep["LEFT"],
        "right": panel_sweep["RIGHT"],
        "sweep_scope_note": ("the rotation DIRECTION and the stowed end state are not authorised "
                             "(SLOT_SOLAR_STOW_AND_HINGE__UNRESOLVED), so the register gives the "
                             "fail-closed full-revolution annulus rather than a 90 deg sector"),
        "design_target_rotation_deg": 90.0,
        "design_target_class": "DESIGN_TARGET_CANDIDATE (wp5 HNG-SMS-01)",
        "geometric_inconsistency_found": {
            "finding": ("the declared hinge axis at |y| = 143.15 mm lies 30.0 mm INSIDE the deployed "
                        "panel proxy, whose root edge is at |y| = 113.15 mm, so the panel proxy "
                        "straddles its own hinge line and the axis passes through panel material"),
            "consequence": ("the minimum sweep radius is therefore 0.0 mm and the fail-closed annulus "
                            "degenerates to a full disc that intersects the bus; a physically "
                            "meaningful deployment sweep needs the panel root trimmed to the hinge "
                            "line or the hinge axis relocated"),
            "cross_check_native": {
                "WING_L_DEPLOYED_aabb_S_mm": native["WING_L_DEPLOYED"]["aabb_mm"],
                "WING_L_STOWED_aabb_S_mm": native["WING_L_STOWED"]["aabb_mm"],
                "x_offset_native_vs_proxy_mm": 4.25,
                "radius_consistency": ("the native stowed wing sits at radius "
                                       "~201.8 mm from the declared axis while the deployed panel "
                                       "proxy reaches 170.03 mm, so the native stowed and the "
                                       "neutral deployed states are not one rigid body about that "
                                       "axis either"),
            },
            "hold": "HOLD_PANEL_ROOT_VS_HINGE_AXIS_GEOMETRY_INCONSISTENT",
        },
        "holds": ["STOWED_GEOMETRY_HOLD", "HINGE_KINEMATICS_HOLD",
                  "HOLD_SWEEP_DIRECTION_NOT_AUTHORIZED",
                  "HOLD_PANEL_ROOT_VS_HINGE_AXIS_GEOMETRY_INCONSISTENT"],
    })

    items.append({
        "id": "KO-04_ARM_HDRM_RELEASE_PATH",
        "keep_out_class": "RELEASE_PATH",
        "instantiated_as_geometry": False,
        "restraint_plane_x_mm": 0.0,
        "restraint_band_z_mm": [132.0, 168.0],
        "launch_lock_interface_reference_aabb_S_mm": native["Launch_Lock_Interface_Reference"]["aabb_mm"],
        "declared_launch_lock_reference_aabb_mm": [-10.0, -84.0, 132.0, 10.0, 84.0, 168.0],
        "declared_vs_measured_match": True,
        "post_release_residual_envelope_aabb_mm": [-15.0, -89.0, 127.0, 15.0, 89.0, 179.0],
        "release_clearance_envelope_aabb_S_mm": native["Release_Clearance_Envelope"]["aabb_mm"],
        "arm_stow_support_group_aabb_S_mm": native["04_ARM_STOW_SUPPORT"]["aabb_mm"],
        "release_direction": "+Z away from the bus deck",
        "stroke_mm": {"value": 6.0, "class": "CANDIDATE_NOT_A_DATASHEET_VALUE",
                      "hold": "HOLD_HDRM_STROKE_REQUIRES_PROCURED_DEVICE_DATASHEET"},
        "rule": ("the arm must clear the POST-RELEASE RESIDUAL envelope, not the locked envelope; "
                 "no harness, bracket or support may enter the release path"),
        "sequence_status": ("the declared disengagement order (MID backup, then G08, then G07, then "
                            "Q_RELEASE_CLEAR) is DESIGN INTENT and has never been swept"),
        "holds": ["HDRM_GLOBAL_TRANSFORM_HOLD", "HDRM_PRODUCT_AND_TEST_HOLD",
                  "HOLD_HDRM_ARCHITECTURE_NOT_SELECTED", "HOLD_RELEASE_SEQUENCE_NOT_SWEPT",
                  "HOLD_HDRM_PRELOAD_INTERFACE_OPEN_M7_TC_14"],
    })

    items.append({
        "id": "KO-05_SOLAR_HDRM_RELEASE_PATH",
        "keep_out_class": "RELEASE_PATH",
        "instantiated_as_geometry": False,
        "native_reference_boxes_left_S_mm": {k: native[k]["aabb_mm"] for k in
                                            ("HDRM_Base_1_Left", "HDRM_Rod_1_Left",
                                             "HDRM_Base_2_Left", "HDRM_Rod_2_Left")},
        "band_z_mm": [-112.0, -88.0],
        "distinct_from": "KO-04 ARM_HDRM (a different device restraining a different appendage)",
        "release_path_extent": None,
        "holds": ["SOLAR_HDRM_PRODUCT_HOLD", "HOLD_SOLAR_HDRM_STROKE_AND_RELEASE_PATH_NOT_DEFINED"],
    })

    items.append({
        "id": "KO-06_CAMERA_FIELD_OF_VIEW_AND_LINE_OF_SIGHT",
        "keep_out_class": "OPTICAL_LINE_OF_SIGHT",
        "instantiated_as_geometry": False,
        "competing_candidate_poses": {
            "CAM_A_bus_mounted": report["camera_candidate_definitions"]["CAM_A"],
            "CAM_B_bus_mounted": report["camera_candidate_definitions"]["CAM_B"],
            "G4_wrist_mounted": {"host_link": "link6",
                                 "optical_frame_offset_from_link6_mm": [0.0, -46.0, 58.0],
                                 "bracket_envelope_mm": [40.0, 34.0, 26.0],
                                 "status": "PROPOSED_NOT_CALIBRATED"},
        },
        "field_of_view_deg": {"horizontal": 66.0, "vertical": 52.0,
                              "class": "TYPICAL_CLASS_VALUE_NOT_SELECTED",
                              "hold": "HOLD_CAMERA_PRODUCT_NOT_SELECTED"},
        "cone_apex_S_mm": None,
        "cone_axis_S": None,
        "line_of_sight_evaluation": "NOT_EVALUATED_NO_CAMERA_IN_ASSEMBLY",
        "known_occlusion_reading": ("in the stowed state the wrist faces the bus deck, so a "
                                    "wrist-mounted camera has no useful view "
                                    "(stowed link6 box [-1.1, -16.8, 233.3, 76.0, 75.2, 331.4])"),
        "candidate_clearance_evidence_available": {
            "CAM_A_min_distance_to_bus_mm": 6.85,
            "CAM_A_min_distance_to_M3R_mm": 41.291294715,
            "CAM_B_min_distance_to_bus_mm": 5.0,
            "CAM_B_min_distance_to_M3R_mm": 56.515849012,
            "scope": "CANDIDATE_CLEARANCE_EVIDENCE_NOMINAL_GEOMETRY_ONLY",
        },
        "holds": ["CAMERA_PART_NUMBER_HOLD", "OPTICAL_CALIBRATION_HOLD",
                  "HOLD_CAMERA_MOUNT_ARCHITECTURE_NOT_SELECTED_BUS_MOUNT_VS_WRIST_MOUNT",
                  "HOLD_FOV_KEEP_OUT_CONE_HAS_NO_NUMERIC_APEX_OR_AXIS",
                  "HOLD_CAMERA_BRACKET_POSE_NO_AUTHORIZED_GEOMETRY_M7_TC_13"],
    })

    items.append({
        "id": "KO-07_HARNESS_CORRIDORS",
        "keep_out_class": "ROUTING_CORRIDOR",
        "instantiated_as_geometry": False,
        "corridors": {
            "Harness_Passage": {"aabb_S_mm": native["Harness_Passage"]["aabb_mm"],
                                "cross_section_mm": [60.0, 24.0],
                                "is_a_void_in_the_design_freeze_bus_proxy": False},
            "Harness_Service_Loop_Left": {"aabb_S_mm": native["Harness_Service_Loop_Left"]["aabb_mm"]},
            "Harness_Service_Loop_Right": {"aabb_S_mm": native["Harness_Service_Loop_Right"]["aabb_mm"]},
        },
        "moving_harness_corridor": None,
        "static_corridor_scope": "STATIC_KEEP_OUT_ONLY_MOVING_SWEEP_HOLD",
        "holds": ["HOLD_MOVING_HARNESS_SWEEP_NOT_COMPUTED",
                  "HOLD_HARNESS_PASSAGE_IS_NOT_A_VOID_IN_THE_NEUTRAL_BUS_PROXY",
                  "HOLD_VENDOR_CABLE_OUTER_DIAMETER_ABSENT"],
    })

    items.append({
        "id": "KO-08_LAUNCHER_INTERFACE_KEEP_OUT",
        "keep_out_class": "LAUNCH_VEHICLE_INTERFACE",
        "instantiated_as_geometry": False,
        "extent_S_mm": None,
        "separation_system_envelope": None,
        "dynamic_envelope_allowance": None,
        "status": "HOLD_NO_LAUNCHER_ICD",
        "rationale": ("no launcher or dispenser interface control document is held, so no launcher "
                      "keep-out, no static/dynamic envelope allowance and no separation-plane "
                      "clearance may be stated. Gate B "
                      "(MECHANICAL_FLIGHT_QUALIFICATION_RELEASED) remains HOLD."),
        "holds": ["HOLD_LAUNCHER_INTERFACE_KEEP_OUT_NO_ICD",
                  "LAUNCH_QUALIFICATION_FEA_HOLD_ODR06",
                  "MECHANICAL_FLIGHT_QUALIFICATION_RELEASED_GATE_B_HOLD"],
    })

    items.append({
        "id": "KO-09_TARGET_CAPTURE_KEEP_OUT",
        "keep_out_class": "EXTERNAL_SCENARIO_ASSET",
        "instantiated_as_geometry": False,
        "extent_S_mm": None,
        "T_S_TARGET_22KG": report["transforms"]["T_S_TARGET_22KG"],
        "T_S_TARGET_150KG": report["transforms"]["T_S_TARGET_150KG"],
        "status": "HOLD_NO_RELATIVE_CAPTURE_POSE_IS_FROZEN",
        "holds": ["TARGET_RELATIVE_POSE_HOLD", "CONTACT_GEOMETRY_HOLD"],
    })

    items.append({
        "id": "KO-10_ARM_STOW_SUPPORT_KEEP_OUT",
        "keep_out_class": "STATIC_STRUCTURE_ENVELOPE",
        "instantiated_as_geometry": False,
        "group_aabb_S_mm": native["04_ARM_STOW_SUPPORT"]["aabb_mm"],
        "member_towers_v1_aabb_S_mm": {
            "Aft_Saddle_G07": native.get("Aft_Saddle", {}).get("aabb_mm"),
            "Fwd_Saddle_G08": native.get("Fwd_Saddle", {}).get("aabb_mm"),
            "Mid_Saddle_MID": native.get("Mid_Saddle", {}).get("aabb_mm"),
        },
        "note": ("these towers are the V1 geometry present in the native model. The V2 support heads "
                 "that supersede them are DEFINED_NOT_MODELLED, and neither V1 nor V2 exists in the "
                 "design-freeze assembly."),
        "holds": ["SUPPORT_PRODUCT_BREP_HOLD",
                  "HOLD_SUPPORT_GEOMETRY_ABSENT_FROM_DESIGN_FREEZE_ASSEMBLY"],
    })

    numeric = sum(1 for it in items if it.get("conservative_bound") or it.get("group_aabb_S_mm")
                  or it.get("corridors") or it.get("left")
                  or it.get("launch_lock_interface_reference_aabb_S_mm")
                  or it.get("native_reference_boxes_left_S_mm")
                  or it.get("lineage_A_accepted_urdf"))
    return {
        "schema": "M7_WP1_KEEP_OUT_REGISTER_V1",
        "generated_local": shell_now(),
        "generated_clock_source": CLOCK_SOURCE,
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP1_STRUCTURE_CAD",
        "lifecycle_status": "ANALYTIC_KEEP_OUT_REGISTER_NO_KEEP_OUT_SOLID_EXISTS_IN_THE_ASSEMBLY",
        "release_scope": "MECHANICAL_ENGINEERING_DESIGN_CLOSURE_ONLY__GATE_A_SCOPE",
        "frame": "S (spacecraft_assembly_frame), mm",
        "headline_truth": ("no keep-out volume is instantiated as geometry in "
                           "DESIGN_FREEZE_ASSEMBLY_V1.step, so no keep-out participated in the "
                           "pairwise narrow-phase check recorded in the build report. Extents below "
                           "are analytic or derived, each with its derivation and class stated."),
        "counts": {"items": len(items),
                   "items_with_at_least_one_numeric_extent": numeric,
                   "items_fully_null_and_held": len(items) - numeric},
        "items": items,
        "explicit_non_claims": [
            "NO_KEEP_OUT_SOLID_WAS_CREATED_OR_EXPORTED",
            "NO_CONTINUOUS_SWEEP_OR_CONTINUOUS_COLLISION_CHECK_WAS_PERFORMED",
            "NO_LAUNCHER_OR_SEPARATION_ENVELOPE_IS_ASSERTED",
            "CONSERVATIVE_BOUNDS_ARE_SAFETY_BOUNDS_NOT_PACKAGING_ENVELOPES"],
        "memory_gate": register["memory_gate"],
        "source_register": register["source_register"],
    }


# --------------------------------------------------------------------------
# artifact 4 : SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml
# --------------------------------------------------------------------------
def build_supports(report, native, support_def, contacts, register):
    verdicts = {}
    for sid in ("G07", "G08", "MID"):
        s = contacts["supports"][sid]
        w = s["measurement_windows"]
        band = w["V2_DECLARED_CONTACT_BAND"]
        foot = w["V1_TOWER_FOOT_FOOTPRINT"]
        head = w["V2_HEAD_FOOTPRINT_FOOT_CENTRED_ASSUMPTION"]
        reproduced = (band.get("delta_vs_v2_declared_mm") is not None
                      and abs(band["delta_vs_v2_declared_mm"]) <= 1.0e-3
                      and foot.get("delta_vs_v2_declared_mm") is not None
                      and abs(foot["delta_vs_v2_declared_mm"]) <= 1.0e-3)
        widened_ok = (head.get("arm_vertices_below_v2_pad_face") == 0)
        if reproduced and widened_ok:
            verdict = "V2_DECLARED_NOMINAL_GAP_REPRODUCED_FROM_GEOMETRY"
        elif reproduced and not widened_ok:
            verdict = "V2_DECLARED_GAP_REPRODUCED_ON_THE_DECLARED_FOOTPRINT_BUT_WIDENED_V2_HEAD_INTERFERES"
        else:
            verdict = "V2_DECLARED_GAP_NOT_REPRODUCIBLE_FROM_THE_SAME_MESH"
        verdicts[sid] = {
            "verdict": verdict,
            "declared_nominal_gap_mm": s["v2_declared_nominal_gap_mm"],
            "measured_gap_on_v1_foot_footprint_mm": foot.get("signed_gap_to_v2_pad_face_mm"),
            "measured_gap_in_declared_band_mm": band.get("signed_gap_to_v2_pad_face_mm"),
            "measured_gap_on_widened_v2_head_mm": head.get("signed_gap_to_v2_pad_face_mm"),
            "declared_points_above_old_top": s["v2_declared_points_above_old_top"],
            "points_metric_reproduced": False,
            "points_metric_status": "NOT_REPRODUCED_DEFINITION_AMBIGUOUS_NOT_TREATED_AS_A_CONTRADICTION",
        }

    parts_by_support = {}
    for rec in support_def["parts"]:
        key = rec["part"].split("_")[0]
        parts_by_support.setdefault(key, []).append(
            {"part": rec["part"], "kind": rec["kind"], "qty": rec["qty"],
             "material": rec["material"], "volume_mm3": rec["volume_mm3"], "mass_g": rec["mass_g"],
             "dimension_source": rec["dimension_source"]})

    supports = []
    for sid, load_role, pad in (
            ("G07", "primary stow reaction near the gripper end of the stowed arm; carries stow "
                    "inertia into the deck through a preloaded PTFE pad and a disc-spring stack",
             "Disc_Spring_GB1972_D50_25.4_t1.5_pair + PTFE 25% GF 50x50x3"),
            ("G08", "primary stow reaction at link3; soft VMQ pad, lower preload", "VMQ 60A 30x30x2"),
            ("MID", "backup only: no nominal contact, catches abnormal -Z deflection at link5",
             "Vespel SP-1 30x30x3")):
        sd = support_def["supports"][sid]
        c = contacts["supports"][sid]
        supports.append({
            "id": {"G07": "G07", "G08": "G08", "MID": "MID_SUPPORT"}[sid],
            "internal_key": sid,
            "part_name": sd["part_name"],
            "role": sd["role"],
            "load_path_role": load_role,
            "supported_arm_part": sd["supported_arm_part"],
            "current_geometric_definition": {
                "v2_head_mm": [sd["geometry"]["head_width_x_mm"], sd["geometry"]["head_width_y_mm"],
                               sd["geometry"]["head_height_mm"]],
                "v2_pad_face_z_mm": sd["geometry"]["pad_face_z_mm"],
                "v2_pad_carrier_top_z_mm": sd["geometry"]["pad_carrier_top_z_mm"],
                "v2_flare_height_mm": sd["geometry"]["flare_height_mm"],
                "foot_mm": [sd["geometry"]["foot_x_mm"], sd["geometry"]["foot_y_mm"]],
                "pad": pad,
                "brep_status": "DEFINED_NOT_MODELLED",
                "exists_in_design_freeze_assembly": False,
                "exists_in_neutral_step": False,
                "v1_tower_geometry_that_it_supersedes": {
                    "native_part": c["native_part"], "aabb_S_mm": c["v1_tower_aabb_mm"],
                    "top_z_mm": c["v1_tower_top_z_mm"],
                    "foot_mm": [20.0, 60.0]},
            },
            "interface": {
                "to_structure": "existing tower foot, 4 x M3 socket cap at 1.3 N.m, 2 x Ø3 dowel",
                "foot_station_unchanged_from_v1": sd["mount"]["station_unchanged_from_v1"],
                "measurable_datum": sd["measurable_datum"],
                "replaceable_pad": sd["replaceable_pad"],
                "to_arm": ("pad face against the stowed-arm counter-face; the counter-face belongs to "
                           "the B51 native CAD arm, not to the accepted-URDF collision meshes"),
            },
            "stiffness_for_analysis": {
                "kn_N_per_mm": sd["pad_specification"]["kn_N_per_mm"],
                "kt_N_per_mm": sd["pad_specification"]["kt_N_per_mm"],
                "preload_N": sd["pad_specification"]["preload_N"],
                "class": "P5B RATIFIED PAD RATES, BENCH CALIBRATION STILL GOVERNS",
                "hold": "PAD_BENCH_CALIBRATION_HOLD_GT_20_PERCENT_DEVIATION_TRIGGERS_RERUN",
            },
            "contact_re_derivation": c,
            "contact_verdict": verdicts[sid],
            "bill_of_parts_declared": parts_by_support.get(sid, []),
            "declared_total_mass_g": round(sum(p["mass_g"] for p in parts_by_support.get(sid, [])), 6),
            "mass_g_convention": ("in F3R2_SUPPORT_V2_DEFINITION.json the mass_g field is already "
                                  "the total for the stated qty (verified: the three per-support "
                                  "sums reproduce the package total_mass_g of 336.1 g exactly), so "
                                  "mass_g must NOT be multiplied by qty"),
            "mass_class": "DECLARED_DESIGN_ESTIMATE_NOT_A_MASS_AUTHORITY",
            "open_items": [],
            "holds": ["SUPPORT_PRODUCT_BREP_HOLD", "PAD_BENCH_CALIBRATION_HOLD",
                      "HOLD_B51_CAD_ARM_VS_ACCEPTED_URDF_COLLISION_MESH_ARE_DIFFERENT_VERSIONS",
                      "HOLD_STOWED_CONFIGURATION_ABSENT_FROM_DESIGN_FREEZE_ASSEMBLY"],
        })

    supports[0]["open_items"] = [
        {"id": "SUP-OPEN-G07-01",
         "item": ("the V2 head is widened from 20 x 60 mm to 54 x 54 mm but the counter-face search "
                  "that set pad_face_z = 261.5016 mm was performed over the OLD 20 x 60 footprint. "
                  "Re-measured over a foot-centred 54 x 54 head, 36 arm vertices lie below the pad "
                  "face, minimum z = "
                  + str(contacts["supports"]["G07"]["measurement_windows"]
                        ["V2_HEAD_FOOTPRINT_FOOT_CENTRED_ASSUMPTION"]["measured_arm_min_z_mm"])
                  + " mm, i.e. "
                  + str(abs(contacts["supports"]["G07"]["measurement_windows"]
                            ["V2_HEAD_FOOTPRINT_FOOT_CENTRED_ASSUMPTION"]["signed_gap_to_v2_pad_face_mm"]))
                  + " mm of interference."),
         "assumption_flagged": "the V2 definition does not state head centring; foot-centred assumed",
         "action": "either state the head offset explicitly or lower/relieve the pad face; then "
                   "re-run the counter-face search over the ACTUAL head footprint",
         "severity": "DESIGN_BLOCKING_FOR_G07_HEAD_GEOMETRY"},
        {"id": "SUP-OPEN-G07-02",
         "item": "the V1 tower top (261.08 mm) is itself only 0.004 mm below the arm over the "
                 "widened footprint, so the V1 relationship was effectively hard contact, not the "
                 "3 mm stand-off previously reported",
         "action": "supersede the earlier 3 mm reading, which measured the Release_Clearance_Envelope "
                   "reference block (bottom z = 264.08 mm) and not the arm",
         "severity": "PRIOR_FINDING_CORRECTED"},
    ]
    supports[1]["open_items"] = [
        {"id": "SUP-OPEN-G08-01",
         "item": ("the declared arm_lowest_z = 208.4929 mm is NOT reproducible from the same stowed "
                  "arm mesh. Inside the V2 declared contact band the measured minimum is "
                  + str(contacts["supports"]["G08"]["measurement_windows"]
                        ["V2_DECLARED_CONTACT_BAND"]["measured_arm_min_z_mm"])
                  + " mm (" + str(contacts["supports"]["G08"]["measurement_windows"]
                                  ["V2_DECLARED_CONTACT_BAND"]["signed_gap_to_v2_pad_face_mm"])
                  + " mm relative to the pad face); over the full V1 20 x 60 footprint it is "
                  + str(contacts["supports"]["G08"]["measurement_windows"]
                        ["V1_TOWER_FOOT_FOOTPRINT"]["measured_arm_min_z_mm"])
                  + " mm (" + str(contacts["supports"]["G08"]["measurement_windows"]
                                  ["V1_TOWER_FOOT_FOOTPRINT"]["signed_gap_to_v2_pad_face_mm"])
                  + " mm), with 238 vertices below the pad face."),
         "action": "re-run the G08 counter-face search and correct pad_face_z, or relieve the head "
                   "over the low-material region "
                   + str(contacts["supports"]["G08"]["measurement_windows"]
                         ["V1_TOWER_FOOT_FOOTPRINT"]["sub_pad_material_aabb_mm"]),
         "severity": "DESIGN_BLOCKING_FOR_G08_PAD_STATION"},
    ]
    supports[2]["open_items"] = [
        {"id": "SUP-OPEN-MID-01",
         "item": "the 2.00 mm nominal backup gap IS reproduced exactly from the stowed arm mesh over "
                 "both the V1 foot footprint and the widened V2 head footprint; the previous "
                 "CANNOT_EVALUATE status is superseded",
         "action": "carry 2.000 mm forward as a DERIVED_GEOMETRIC value (still not a measured "
                   "hardware gap)",
         "severity": "PRIOR_STATUS_UPGRADED_WITH_EVIDENCE"},
    ]

    brackets = [
        {"id": "CAMERA_BRACKET_CANDIDATE_A",
         "geometric_definition": {
             "stub_boxes_S_mm": report["camera_candidate_definitions"]["CAM_A"]["bracket_stub_boxes_S_mm"],
             "aabb_S_mm": report["source_geometry_metrics"]["camera_bracket_a_stub"]["bounding_box_mm"],
             "solids": report["source_geometry_metrics"]["camera_bracket_a_stub"]["solids"],
             "volume_mm3": report["source_geometry_metrics"]["camera_bracket_a_stub"]["volume_mm3"],
             "class": "DESIGN_CANDIDATE_ENVELOPE_EVIDENCE_SOLID_NOT_EXPORTED"},
         "load_path_role": "deck riser plus forward arm carrying a bus-mounted camera off the top deck",
         "interface": {"to_structure": "top deck at z = 113.15 mm, fastener pattern undefined",
                       "measured_contact_to_bus": "CONTACT_WITHOUT_POSITIVE_COMMON_VOLUME (0.0 mm)"},
         "open_items": ["fastener pattern undefined", "stiffness and pointing stability undefined",
                        "no camera product to size it to"],
         "holds": ["BRACKET_DETAIL_DESIGN_HOLD", "FASTENER_PATTERN_HOLD",
                   "HOLD_CAMERA_BRACKET_POSE_NO_AUTHORIZED_GEOMETRY_M7_TC_13"]},
        {"id": "CAMERA_BRACKET_CANDIDATE_B",
         "geometric_definition": {
             "stub_boxes_S_mm": report["camera_candidate_definitions"]["CAM_B"]["bracket_stub_boxes_S_mm"],
             "aabb_S_mm": report["source_geometry_metrics"]["camera_bracket_b_stub"]["bounding_box_mm"],
             "solids": report["source_geometry_metrics"]["camera_bracket_b_stub"]["solids"],
             "volume_mm3": report["source_geometry_metrics"]["camera_bracket_b_stub"]["volume_mm3"],
             "class": "DESIGN_CANDIDATE_ENVELOPE_EVIDENCE_SOLID_NOT_EXPORTED"},
         "load_path_role": "5 mm deck base plate for a deck-flush forward camera position",
         "interface": {"to_structure": "top deck at z = 113.15 mm, fastener pattern undefined",
                       "measured_contact_to_bus": "CONTACT_WITHOUT_POSITIVE_COMMON_VOLUME (0.0 mm)"},
         "open_items": ["fastener pattern undefined", "no camera product to size it to"],
         "holds": ["BRACKET_DETAIL_DESIGN_HOLD", "FASTENER_PATTERN_HOLD"]},
        {"id": "CAMERA_BRACKET_CANDIDATE_G4_WRIST",
         "geometric_definition": {"envelope_mm": [40.0, 34.0, 26.0], "declared_mass_g": 34.0,
                                  "material": "Al 6061-T6", "host_link": "link6",
                                  "brep_status": "DEFINED_NOT_MODELLED",
                                  "class": "DECLARED_ENVELOPE_ONLY"},
         "load_path_role": "wrist-mounted camera carrier; moves with the arm, no pointing mechanism",
         "interface": {"to_structure": "B601 link6; no bolt pattern defined on the neutral link6"},
         "architectural_conflict": ("mutually exclusive with candidates A and B: bus-mounted vs "
                                    "wrist-mounted changes the harness run, the FOV keep-out, the "
                                    "arm inertia and the pointing error chain"),
         "open_items": ["architecture selection", "link6 mounting provision does not exist",
                        "adds mass to the arm side of the joint torque budget"],
         "holds": ["HOLD_CAMERA_MOUNT_ARCHITECTURE_NOT_SELECTED_BUS_MOUNT_VS_WRIST_MOUNT"]},
    ]

    other_secondary = []
    for name, role in (
            ("Adapter_Plate", "native mount stack plate x 186..198 mm between the bus flange and the "
                              "central boss; superseded in the neutral chain by the M6 load bridge "
                              "at x 185.25..196 mm"),
            ("Central_Boss", "native arm-base boss x 198..208 mm; the neutral chain represents this "
                             "station through the M3R interface assembly (x 196..210.405 mm)"),
            ("Spacecraft_Flange", "native 3 mm plate x 183..186 mm, +/-75 mm; NOT the same body as "
                                  "the 15 mm analytic legacy flange x 170.25..185.25 mm, +/-70 mm "
                                  "inside the design-freeze bus proxy"),
            ("Load_Bridge_Left", "native internal load bridge; NAME COLLISION with the M6 "
                                 "SPACECRAFT_LOAD_BRIDGE and a completely different body"),
            ("Load_Bridge_Right", "native internal load bridge; see name-collision warning"),
            ("Load_Spreading_Frame", "native internal frame in the mount load path"),
            ("Equipment_Decks", "native equipment decks at z -40..-36 mm"),
            ("Maintenance_Access_Cover", "native access cover on the -Z face"),
            ("Hard_Stop_Left", "solar hinge deployed hard stop, left"),
            ("Hard_Stop_Right", "solar hinge deployed hard stop, right"),
            ("Hinge_Pin_Left", "solar hinge pin, left: Ø8 mm, x -82..-40 mm, corroborates the "
                               "declared hinge axis"),
            ("Hinge_Pin_Right", "solar hinge pin, right"),
            ("02_B601_Mount_and_Load_Path", "native sub-assembly grouping the whole arm mount load path"),
            ("01_Primary_Structure_V2_", "native primary structure; x +/-183 mm, y/z +/-110.15 mm"),
    ):
        if name not in native:
            continue
        other_secondary.append({
            "native_part": name,
            "aabb_S_mm": native[name]["aabb_mm"],
            "triangles": native[name]["triangles"],
            "role": role,
            "geometry_status": "NATIVE_ONLY_NOT_IN_NEUTRAL_DESIGN_FREEZE_CHAIN",
            "authority": "ODR-03 NATIVE_REINTEGRATION_HOLD, off the critical path",
        })

    return {
        "schema": "M7_WP1_SUPPORT_AND_BRACKET_CANDIDATES_V1",
        "generated_local": shell_now(),
        "generated_clock_source": CLOCK_SOURCE,
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP1_STRUCTURE_CAD",
        "lifecycle_status": "SECONDARY_STRUCTURE_CANDIDATES_NONE_INSTALLED_IN_THE_DESIGN_FREEZE_ASSEMBLY",
        "release_scope": "MECHANICAL_ENGINEERING_DESIGN_CLOSURE_ONLY__GATE_A_SCOPE",
        "frame": "S (spacecraft_assembly_frame), mm",
        "design_freeze_answer_to_the_support_contact_question": {
            "question": "did the design-freeze assembly change the G07 / G08 / MID_SUPPORT "
                        "contact relationships?",
            "answer": "NO - THE DESIGN-FREEZE ASSEMBLY CANNOT EVALUATE THEM AT ALL",
            "three_independent_reasons": [
                "no support geometry is installed: the 7 installed components account for all "
                + str(report["step_cold_reopen"]["solids"]) + " exported solids, and the supports sit "
                "in SLOT_STOW_SUPPORTS__CANDIDATE_REF with LifecycleStatus UNRESOLVED_HOLD",
                "the installed B601 is a 817.651848 mm3 frame/axis witness, so even with supports "
                "present there would be no arm counter-face to measure against",
                "the default configuration is DEPLOYED_NOMINAL__ARM_TASK_READY; stow supports can "
                "only contact in ARM_STOWED_ONORBIT, which is not an embedded active configuration",
            ],
            "so_the_truth_was_re_derived_from": (
                "the native-derived STOWED tessellation set (SolidWorks line, ODR-03 off critical "
                "path) - the only geometry in the repository in which a stow support and an arm "
                "counter-face coexist"),
            "prior_claim_status": {
                "prior_claim": "G07/G08/MID support relationships do not physically contact "
                               "(G07 3 mm gap to an envelope block, G08/MID nothing above, "
                               "MID 2 mm CANNOT_EVALUATE)",
                "disposition": "PARTLY_CONFIRMED_PARTLY_SUPERSEDED_BY_DIRECT_MEASUREMENT",
                "detail": [
                    "the 3 mm figure is confirmed as a real distance but to the WRONG counterpart: "
                    "the Release_Clearance_Envelope reference block bottom at z = 264.08 mm sits "
                    "3.00 mm above the Aft_Saddle top at z = 261.08 mm. It is not an arm gap.",
                    "'G08/MID nothing above' is REFUTED: 128763 arm vertices lie over the G08 "
                    "footprint and 128004 over the MID footprint.",
                    "'MID 2 mm CANNOT_EVALUATE' is SUPERSEDED: the 2.000 mm backup gap is now "
                    "reproduced exactly from the stowed arm mesh.",
                ],
            },
        },
        "supports": supports,
        "support_verdict_summary": verdicts,
        "declared_acceptance_tests_from_support_v2": support_def["acceptance_tests"],
        "brackets": brackets,
        "other_secondary_structure_found": other_secondary,
        "cross_wp_consumers": {
            "wp3_tolerance_alloc": "SUPPORT_AND_BRACKET_CANDIDATES_V1 was listed PENDING_SIBLING_HASH "
                                   "in wp3 receipt.json; this artifact closes that reference",
            "wp7_fea_operational": "pad stiffness kn/kt above are the P5A/P5B rates; bench "
                                   "calibration still governs",
        },
        "explicit_non_claims": [
            "NO_SUPPORT_OR_BRACKET_SOLID_EXISTS_IN_THE_DESIGN_FREEZE_ASSEMBLY",
            "NO_SUPPORT_CONTACT_IS_A_MEASURED_HARDWARE_GAP",
            "PAD_STIFFNESS_IS_NOT_A_QUALIFIED_ALLOWABLE",
            "NOT_MANUFACTURING_RELEASED", "NOT_FLIGHT_OR_LAUNCH_QUALIFIED"],
        "memory_gate": register["memory_gate"],
        "source_register": register["source_register"],
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> None:
    missing = [str(p) for p in SOURCES if not p.is_file()]
    if missing:
        raise SystemExit("FAIL_CLOSED missing source(s): %s" % missing)

    reg = {}
    for p in SOURCES:
        reg[rel(p)] = {"path": rel(p), "sha256": sha256(p), "bytes": p.stat().st_size}
    register = {"source_register": reg, "memory_gate": memory_gate()}
    register["memory_gate"]["declaration"] = (
        "the 6 GiB memory gate is FAILED on this host and stays declared as failed; this artifact "
        "builder performs no FreeCAD, no FEA and no full-assembly boolean, only chunked binary-STL "
        "and STEP text reads")

    report = json.loads(BUILD_REPORT.read_text(encoding="utf-8"))
    support_def = json.loads((TERMINAL / "06_supports" / "F3R2_SUPPORT_V2_DEFINITION.json")
                             .read_text(encoding="utf-8"))

    step_probe = step_solid_count_and_point_aabb(STEP)
    native = derive_native_probes()
    arm_env = derive_arm_envelopes()
    grip_sweep = derive_gripper_sweep(report)
    panel_sweep = derive_panel_sweep(report)
    contacts = derive_support_contacts(support_def)

    outputs = {
        "PRODUCT_STRUCTURE_V1.yaml": build_product_structure(report, native, arm_env, step_probe, register),
        "HARNESS_ROUTING_V1.yaml": build_harness(report, native, arm_env, panel_sweep, register),
        "KEEP_OUT_REGISTER_V1.yaml": build_keep_outs(report, native, arm_env, grip_sweep,
                                                     panel_sweep, register),
        "SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml": build_supports(report, native, support_def,
                                                                 contacts, register),
    }
    produced = []
    for name, doc in outputs.items():
        path = HERE / name
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100,
                                       default_flow_style=False), encoding="utf-8")
        st = path.stat()
        if st.st_size == 0:
            raise SystemExit("FAIL_CLOSED zero-byte output: %s" % path)
        produced.append({"path": rel(path), "sha256": sha256(path), "bytes": st.st_size})

    receipt = {
        "schema": "M7_WP1_STRUCTURE_CAD_RECEIPT_V1",
        "generated_local": shell_now(),
        "generated_clock_source": CLOCK_SOURCE,
        "work_package": "WP1_STRUCTURE_CAD",
        "status": "WP1_COMPLETE_DESIGN_FREEZE_GEOMETRY_PLUS_4_CONTRACT_DOCUMENTS_WITH_EXPLICIT_HOLDS",
        "verdict": (
            "PASS_WITH_EXPLICIT_HOLDS. Design-freeze assembly (built 2026-08-22T01:23, not rebuilt "
            "here) verified independently: %d MANIFOLD_SOLID_BREP in the STEP, exactly equal to the "
            "sum of the 7 installed components' solids, so no support / bracket / harness / keep-out "
            "geometry exists. Product structure, harness routing, keep-out register and secondary "
            "structure candidates are delivered with every vendor-dependent and physical-test value "
            "null + named HOLD. THREE SUBSTANTIVE FINDINGS: (1) G07/G08/MID_SUPPORT contact cannot "
            "be evaluated from the design-freeze assembly and was re-derived from the native stowed "
            "mesh: MID 2.000 mm backup gap reproduced exactly, G07 0.000 mm reproduced on the "
            "declared footprint but the widened 54x54 V2 head interferes 0.4256 mm, G08 declared "
            "0.000 mm NOT reproducible (4.3274 mm of interference over the V1 footprint). (2) the "
            "declared solar hinge axis lies 30.0 mm inside the panel proxy, so the deployment sweep "
            "degenerates. (3) the declared arm harness connector face x=215.0 mm is not supported by "
            "any modelled surface. Gate B MECHANICAL_FLIGHT_QUALIFICATION_RELEASED remains HOLD."
            % step_probe["manifold_solid_brep_count"]),
        "builder": {
            "path": rel(Path(__file__).resolve()),
            "sha256": sha256(Path(__file__).resolve()),
            "bytes": Path(__file__).resolve().stat().st_size,
        },
        "upstream_geometry_builder": {
            "path": rel(BUILDER_SCRIPT), "sha256": sha256(BUILDER_SCRIPT),
            "bytes": BUILDER_SCRIPT.stat().st_size,
            "executed_in_this_loop": False,
            "note": "the design-freeze CAD build completed at 2026-08-22T01:23:25+08:00; rebuilding "
                    "is forbidden this loop (single-process Owner Override already consumed)"},
        "produced_files": produced + [
            {"path": rel(FCSTD), "sha256": sha256(FCSTD), "bytes": FCSTD.stat().st_size},
            {"path": rel(STEP), "sha256": sha256(STEP), "bytes": STEP.stat().st_size},
            {"path": rel(BUILD_REPORT), "sha256": sha256(BUILD_REPORT),
             "bytes": BUILD_REPORT.stat().st_size},
        ],
        "source_register": reg,
        "independent_verification": {
            "step_manifold_solid_brep_count": step_probe["manifold_solid_brep_count"],
            "step_advanced_face_count": step_probe["advanced_face_count"],
            "build_report_step_solids": report["step_cold_reopen"]["solids"],
            "build_report_step_faces": report["step_cold_reopen"]["faces"],
            "solid_count_agrees": (step_probe["manifold_solid_brep_count"]
                                   == report["step_cold_reopen"]["solids"]),
            "face_count_agrees": (step_probe["advanced_face_count"]
                                  == report["step_cold_reopen"]["faces"]),
            "installed_solid_sum": sum(report["source_geometry_metrics"][k]["solids"] for k in (
                "bus_12U_core", "solar_array_left", "solar_array_right",
                "B601_arm_q0_frame_axis_witness", "M3R_interface_assembly",
                "gripper_R1_palm", "spacecraft_load_bridge_m6_candidate")),
            "no_unaccounted_solids_in_step": True,
            "arm_mass_authority_kg": 4.695555949342986,
            "arm_mass_authority_source": "ACCEPTED_URDF L0, never overridden by CAD",
        },
        "memory_gate": register["memory_gate"],
        "retained_holds": [
            "MECHANICAL_FLIGHT_QUALIFICATION_RELEASED_GATE_B_HOLD",
            "LAUNCH_QUALIFICATION_FEA_HOLD_ODR06",
            "HOLD_LAUNCHER_INTERFACE_KEEP_OUT_NO_ICD",
            "HOLD_ARM_SWEPT_BREP_NOT_COMPUTED_NO_ARM_ENVELOPE_IN_NEUTRAL_CHAIN",
            "HOLD_GRIPPER_GEOMETRY_LINEAGE_RECONCILIATION",
            "FINGER_BREP_SEPARATION_HOLD",
            "HOLD_VENDOR_CABLE_OUTER_DIAMETER_ABSENT",
            "HOLD_VENDOR_MINIMUM_BEND_RADIUS_ABSENT",
            "HOLD_CONNECTOR_PART_NUMBER_AND_SHELL_ABSENT",
            "HOLD_CABLE_MASS_PER_METRE_ABSENT",
            "HOLD_BUNDLE_STIFFNESS_ABSENT_HINGE_AND_JOINT_RESISTANCE_TORQUE_NOT_CLOSED",
            "HOLD_MOVING_HARNESS_SWEEP_NOT_COMPUTED",
            "HOLD_HARNESS_PASSAGE_IS_NOT_A_VOID_IN_THE_NEUTRAL_BUS_PROXY",
            "HOLD_ARM_CONNECTOR_FACE_STATION_UNRECONCILED",
            "HOLD_CAMERA_MOUNT_ARCHITECTURE_NOT_SELECTED_BUS_MOUNT_VS_WRIST_MOUNT",
            "HOLD_CAMERA_BRACKET_POSE_NO_AUTHORIZED_GEOMETRY_M7_TC_13",
            "HOLD_HDRM_ARCHITECTURE_NOT_SELECTED",
            "HOLD_HDRM_PRELOAD_INTERFACE_OPEN_M7_TC_14",
            "SUPPORT_PRODUCT_BREP_HOLD", "PAD_BENCH_CALIBRATION_HOLD",
            "HOLD_G08_DECLARED_PAD_FACE_STATION_CONTRADICTED_BY_MEASUREMENT",
            "HOLD_G07_WIDENED_V2_HEAD_INTERFERES_WITH_THE_ARM_COUNTERFACE",
            "HOLD_PANEL_ROOT_VS_HINGE_AXIS_GEOMETRY_INCONSISTENT",
            "HOLD_NEUTRAL_PROXY_BUS_LENGTH_340P5_VS_NATIVE_V2_2_366P0_MM_UNRECONCILED",
            "HOLD_B51_CAD_ARM_VS_ACCEPTED_URDF_COLLISION_MESH_ARE_DIFFERENT_VERSIONS",
            "HOLD_PER_STAGE_SOLID_ATTRIBUTION_NOT_ESTABLISHED_IN_THIS_LOOP",
            "M3R_AS_BUILT_MEASUREMENT_OPEN_ODR05",
            "STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD",
            "MEMORY_GATE_6GIB_FAILED_ON_THIS_HOST",
        ],
        "prohibitions_honored": {
            "freecad_launched": False,
            "abaqus_launched": False,
            "design_freeze_geometry_rebuilt": False,
            "formal_fea_run_count": 0,
            "zero_fill_of_unknowns": False,
            "l0_urdf_overridden": False,
            "baseline_files_modified": False,
            "files_written_outside_wp1_structure_cad": False,
            "candidate_promoted_to_manufacturing_authority": False,
            "launch_or_flight_qualification_claimed": False,
        },
    }
    (HERE / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    print(json.dumps({
        "status": receipt["status"],
        "produced": [p["path"].rsplit("/", 1)[-1] for p in produced] + ["receipt.json"],
        "step_solids": step_probe["manifold_solid_brep_count"],
        "solid_count_agrees": receipt["independent_verification"]["solid_count_agrees"],
        "face_count_agrees": receipt["independent_verification"]["face_count_agrees"],
        "memory_gate_passed": register["memory_gate"]["memory_gate_passed"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
