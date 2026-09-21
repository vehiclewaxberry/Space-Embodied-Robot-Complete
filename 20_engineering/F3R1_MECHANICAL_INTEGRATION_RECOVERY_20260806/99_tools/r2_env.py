# -*- coding: utf-8 -*-
"""F3R2 terminal-closure shared environment.

Writes ONLY into 20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/.
Reuses the proven G2 primitives (VARIANT transforms, session discipline,
AddMate success==1) and the protected-hash guard.
"""
import csv
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import pythoncom
from win32com.client import VARIANT

from f3r1_env import F3R1, REPO, ENG, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss

# ---------------- F3R2 tree ----------------
F3R2 = ENG / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
NC2 = F3R2 / "03_native_cad"
CFG2 = F3R2 / "04_configurations"
CLR2 = F3R2 / "05_clearance"
SUP2 = F3R2 / "06_supports"
HDRM2 = F3R2 / "07_hdrm"
CAM2 = F3R2 / "08_camera_harness"
THREAD2 = F3R2 / "10_digital_thread"
SHOT2 = F3R2 / "11_screenshots"
REVIEW2 = F3R2 / "12_human_review"
GATE2 = F3R2 / "13_gate"
PKG2 = F3R2 / "14_package"
CC2 = F3R2 / "15_change_control"
for d in (NC2, CFG2, CLR2, SUP2, HDRM2, CAM2, THREAD2, SHOT2, REVIEW2,
          GATE2, PKG2, CC2):
    d.mkdir(parents=True, exist_ok=True)

# ---------------- inputs (read-only upstream) ----------------
V3_SRC = (F3R1 / "03_native_cad"
          / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM")
V3_SHA_PREFIX = "19D85E9C703BEC107396"
BASELINE = NC2 / "F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM"
AUTHORITY = (F3R1 / "04_configurations" / "G2"
             / "F3R1_G2_CONFIG_ANGLE_AUTHORITY.json")
URDF = (REPO / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf")
URDF_SHA = "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4"

CONFIGS = ["STOWED_ENGINEERING_CANDIDATE", "SOLAR_DEPLOY_ARM_LOCKED",
           "DEPLOYED_NOMINAL", "L_FAIL", "R_FAIL", "DEPLOY_FAILED_BOTH",
           "PARTIAL", "SERVICE"]

gm = swc.get_com_member
SW_SUPPRESSED, SW_RESOLVED = 0, 2
SW_ADD_MATE_NO_ERROR = 1
SW_COINCIDENT, SW_CONCENTRIC, SW_PARALLEL = 0, 1, 3
SW_DISTANCE, SW_ANGLE = 5, 6
SW_ALIGN_ALIGNED, SW_ALIGN_ANTI, SW_ALIGN_NONE = 0, 1, 2

HINGE = {"L": {"y_mm": 143.15, "z_mm": 0.0, "r_pin": 4.000, "r_bore": 4.200},
         "R": {"y_mm": -143.15, "z_mm": 0.0, "r_pin": 4.000, "r_bore": 4.200}}
WING_PANELS = ["WING_L_STOWED-1", "WING_L_DEPLOYED-1",
               "WING_R_STOWED-1", "WING_R_DEPLOYED-1"]


# ---------------- session discipline (D-F3R1-07) ----------------
def sw_count():
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process SLDWORKS -ErrorAction SilentlyContinue |"
             " Measure-Object).Count"],
            capture_output=True, text=True, timeout=90)
        return int((out.stdout or "0").strip() or 0)
    except Exception:
        return -1


def kill_sw(log, wait=24):
    before = sw_count()
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process SLDWORKS -ErrorAction SilentlyContinue |"
                    " Stop-Process -Force"],
                   capture_output=True, text=True, timeout=120)
    time.sleep(3)
    after = sw_count()
    log.ev("SW_CLEARED", before=before, after=after)
    if after not in (0, -1):
        raise RuntimeError("SolidWorks still alive: %s" % after)
    time.sleep(wait)
    return {"before": before, "after": after}


def fresh(log, tag):
    rec = kill_sw(log)
    app = ss.connect(log)
    rec.update({"tag": tag, "during": sw_count(),
                "revision": str(gm(app, "RevisionNumber"))})
    log.ev("SW_STARTED", **{k: rec[k] for k in ("tag", "during", "revision")})
    return app, rec


# ---------------- transforms ----------------
def make_transform(app, t16):
    data = [float(v) for v in t16]
    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data)
    mu = swc.cast(gm(app, "GetMathUtility"), "IMathUtility")
    xf = mu.CreateTransform(typed)
    if xf is None:
        raise RuntimeError("CreateTransform returned None")
    back = [float(v) for v in gm(xf, "ArrayData")]
    if max(abs(a - b) for a, b in zip(back, data)) > 1e-12:
        raise RuntimeError("CreateTransform readback mismatch")
    return xf


def t16_of(c2):
    t = gm(c2, "Transform2")
    return [float(v) for v in gm(t, "ArrayData")] if t is not None else None


def t16_to_mat(t16):
    R = np.array([[t16[0], t16[3], t16[6]],
                  [t16[1], t16[4], t16[7]],
                  [t16[2], t16[5], t16[8]]], dtype=float)
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = np.array(t16[9:12], dtype=float) * 1000.0
    return T


def mat_to_t16(T):
    R = T[:3, :3]
    return [R[0, 0], R[1, 0], R[2, 0], R[0, 1], R[1, 1], R[2, 1],
            R[0, 2], R[1, 2], R[2, 2],
            T[0, 3] / 1000.0, T[1, 3] / 1000.0, T[2, 3] / 1000.0,
            1.0, 0.0, 0.0, 0.0]


def delta_t16(a, b):
    if a is None or b is None:
        return (float("inf"), float("inf"))
    Ra = np.array(a[:9], float).reshape(3, 3).T
    Rb = np.array(b[:9], float).reshape(3, 3).T
    dt = float(np.abs(np.array(a[9:12]) * 1000 - np.array(b[9:12]) * 1000).max())
    c = max(-1.0, min(1.0, (np.trace(Ra.T @ Rb) - 1.0) / 2.0))
    return dt, float(math.degrees(math.acos(c)))


# ---------------- component tree ----------------
def top_children(model):
    conf = gm(model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    out = {}
    for c in gm(rootc, "GetChildren") or []:
        k = swc.cast(c, "IComponent2")
        out[str(gm(k, "Name2"))] = k
    return out


def walk_all(model, maxdepth=5):
    """[(leaf, full, comp)] over the whole tree of the ACTIVE configuration."""
    conf = gm(model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    out = []

    def rec(c2, d):
        for c in gm(c2, "GetChildren") or []:
            k = swc.cast(c, "IComponent2")
            full = str(gm(k, "Name2"))
            out.append((full.split("/")[-1], full, k))
            if d < maxdepth:
                rec(k, d + 1)
    rec(rootc, 0)
    return out


def bodies_of(c2):
    for meth, arg in (("GetBody", None), ("GetBodies2", 0), ("GetBodies2", 1)):
        try:
            r = gm(c2, meth) if arg is None else c2.GetBodies2(arg)
        except Exception:
            continue
        if r is None:
            continue
        if isinstance(r, (list, tuple)):
            if r:
                return list(r)
        else:
            return [r]
    return []


def mate_features(model):
    out = []
    feat = gm(model, "FirstFeature")
    while feat is not None:
        f = swc.cast(feat, "IFeature")
        if str(gm(f, "GetTypeName2")) == "MateGroup":
            sub = gm(f, "GetFirstSubFeature")
            while sub is not None:
                s = swc.cast(sub, "IFeature")
                out.append(s)
                sub = gm(s, "GetNextSubFeature")
        feat = gm(f, "GetNextFeature")
    return out


def mate_rows(model):
    return [{"name": str(gm(s, "Name")), "type": str(gm(s, "GetTypeName2")),
             "suppressed": bool(gm(s, "IsSuppressed"))}
            for s in mate_features(model)]


# ---------------- interference ----------------
REFERENCE_TOKENS = ("Reference", "Envelope", "REFERENCE", "ENVELOPE",
                    "Launch_Lock_Interface_Reference",
                    "Release_Clearance_Envelope", "Master_Skeleton")


def is_reference_only(leaf):
    return any(t in leaf for t in REFERENCE_TOKENS)


def interference_full(model, asm, log):
    """Whole-assembly native interference with per-pair detail + classification."""
    mgr = gm(asm, "InterferenceDetectionManager")
    if mgr is None:
        return {"status": "NO_MANAGER"}
    for p, v in (("TreatCoincidenceAsInterference", False),
                 ("TreatSubAssembliesAsComponents", False),
                 ("IncludeMultibodyPartInterferences", True),
                 ("MakeInterferingPartsTransparent", False),
                 ("ShowIgnoredInterferences", False)):
        try:
            setattr(mgr, p, v)
        except Exception as e:
            log.ev("IDM_PROP_SKIP", prop=p, err=str(e)[:80])
    items = []
    for r in list(mgr.GetInterferences() or []):
        try:
            it = swc.cast(r, "IInterference")
            vol = float(gm(it, "Volume")) * 1e9
            comps = [str(gm(swc.cast(c, "IComponent2"), "Name2"))
                     for c in list(gm(it, "GetComponents") or [])]
            leaves = [c.split("/")[-1] for c in comps]
            excl = None
            if any(is_reference_only(l) for l in leaves):
                excl = "REFERENCE_OR_ENVELOPE_BODY"
            items.append({"volume_mm3": round(vol, 5), "components": comps,
                          "leaves": leaves, "excluded_reason": excl})
        except Exception:
            continue
    items.sort(key=lambda d: -d["volume_mm3"])
    real = [i for i in items if i["excluded_reason"] is None]
    return {"status": "OK", "count_raw": len(items), "count_real": len(real),
            "total_volume_mm3": round(sum(i["volume_mm3"] for i in items), 5),
            "real_volume_mm3": round(sum(i["volume_mm3"] for i in real), 5),
            "items": items[:60]}


def load_authority():
    d = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    return d, {c["name"]: c for c in d["configurations"]}
