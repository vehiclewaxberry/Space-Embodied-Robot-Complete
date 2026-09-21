# -*- coding: utf-8 -*-
"""G2 shared environment: paths, SW session discipline, wing/config contracts.

Session discipline exists because D-F3R1-07 proved a stale SolidWorks session
fabricates BOTH failures (phantom AddMate err=5 on valid selections) and defects
(phantom 649 interferences). Every WRITE run must start from a process count of
zero and end at zero.
"""
import json
import math
import subprocess
import time

import numpy as np
import pythoncom
from win32com.client import VARIANT

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss

NC = F3R1 / "03_native_cad"
G2DIR = F3R1 / "04_configurations" / "G2"
G2DIR.mkdir(parents=True, exist_ok=True)

V2_MATED = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V2_MATED.SLDASM"
V3_CONF = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM"
G0_FROZEN = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM"
AUTHORITY = G2DIR / "F3R1_G2_CONFIG_ANGLE_AUTHORITY.json"

G1_POST_SHA_PREFIX = "E752FFC4CEFAC1D8"
G0_SHA_PREFIX = "5F1CB650F1E88ABF"

gm = swc.get_com_member

# Real hinge axes measured from the donor (Hinge_Pin_Left/Right, r=4.000,
# axis +/-X). Wing rotation for PARTIAL is taken about THESE axes, not invented.
HINGE = {"L": {"y_mm": 143.15, "z_mm": 0.0},
         "R": {"y_mm": -143.15, "z_mm": 0.0}}

# Which donor panel body represents which authoritative angle.
# 0 deg -> the STOWED solid; 90 deg -> the DEPLOYED solid. Intermediate angles
# are produced by ROTATING the DEPLOYED solid about the real hinge axis.
PANELS = {("L", 0.0): "WING_L_STOWED-1", ("L", 90.0): "WING_L_DEPLOYED-1",
          ("R", 0.0): "WING_R_STOWED-1", ("R", 90.0): "WING_R_DEPLOYED-1"}
ALL_PANELS = ["WING_L_STOWED-1", "WING_L_DEPLOYED-1",
              "WING_R_STOWED-1", "WING_R_DEPLOYED-1"]

SW_SUPPRESSED, SW_RESOLVED = 0, 2      # IComponent2.SetSuppression2 (D-NATIVE-03)


def load_authority():
    d = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    return d, {c["name"]: c for c in d["configurations"]}


def sw_process_count():
    """Number of live SLDWORKS.exe processes (PowerShell; tasklist hangs here)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process SLDWORKS -ErrorAction SilentlyContinue |"
             " Measure-Object).Count"],
            capture_output=True, text=True, timeout=90)
        return int((out.stdout or "0").strip() or 0)
    except Exception:
        return -1


def kill_sw(log, wait=22):
    """Close every existing session, confirm 0, then allow the COM server to
    release (connecting too early raises 服务器执行失败 -2146959355)."""
    before = sw_process_count()
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process SLDWORKS -ErrorAction SilentlyContinue |"
                    " Stop-Process -Force"],
                   capture_output=True, text=True, timeout=120)
    time.sleep(3)
    after = sw_process_count()
    log.ev("SW_SESSION_CLEARED", before=before, after=after)
    if after not in (0, -1):
        raise RuntimeError("SolidWorks still running after kill: %s" % after)
    time.sleep(wait)
    return {"processes_before": before, "processes_after": after}


def fresh_session(log, tag):
    """Discipline per D-F3R1-07: clear -> confirm 0 -> start exactly one."""
    rec = kill_sw(log)
    app = ss.connect(log)
    rec["tag"] = tag
    rec["processes_during"] = sw_process_count()
    rec["revision"] = str(gm(app, "RevisionNumber"))
    log.ev("SW_SESSION_STARTED", **{k: rec[k] for k in
                                    ("tag", "processes_during", "revision")})
    return app, rec


# ---------- transform helpers (VARIANT-typed; a raw list silently corrupts) ----

def make_transform(app, t16):
    data = [float(v) for v in t16]
    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data)
    mu = swc.cast(gm(app, "GetMathUtility"), "IMathUtility")
    xf = mu.CreateTransform(typed)
    if xf is None:
        raise RuntimeError("CreateTransform returned None")
    back = [float(v) for v in gm(xf, "ArrayData")]
    if max(abs(a - b) for a, b in zip(back, data)) > 1e-12:
        raise RuntimeError("CreateTransform SAFEARRAY readback mismatch")
    return xf


def t16_of(c2):
    t = gm(c2, "Transform2")
    return [float(v) for v in gm(t, "ArrayData")] if t is not None else None


def t16_to_mat(t16):
    """SW ArrayData(16, metres) -> 4x4 homogeneous in mm."""
    R = np.array([[t16[0], t16[3], t16[6]],
                  [t16[1], t16[4], t16[7]],
                  [t16[2], t16[5], t16[8]]], dtype=float)
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = np.array(t16[9:12], dtype=float) * 1000.0
    return T


def mat_to_t16(T):
    """4x4 (mm) -> SW ArrayData 16 (metres)."""
    R = T[:3, :3]
    return [R[0, 0], R[1, 0], R[2, 0],
            R[0, 1], R[1, 1], R[2, 1],
            R[0, 2], R[1, 2], R[2, 2],
            T[0, 3] / 1000.0, T[1, 3] / 1000.0, T[2, 3] / 1000.0,
            1.0, 0.0, 0.0, 0.0]


def rot_about_x_through(point_yz_mm, angle_deg):
    """Rotation about an X-parallel axis passing through (y,z) -- the REAL hinge
    axis geometry (Hinge_Pin_L/R: axis +/-X at y=+/-143.15, z=0)."""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    Rx = np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]],
                  dtype=float)
    y0, z0 = float(point_yz_mm[0]), float(point_yz_mm[1])
    Tm = np.eye(4)
    Tm[1, 3], Tm[2, 3] = -y0, -z0
    Tp = np.eye(4)
    Tp[1, 3], Tp[2, 3] = y0, z0
    return Tp @ Rx @ Tm


def top_children(model):
    conf = gm(model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    out = {}
    for c in gm(rootc, "GetChildren") or []:
        k = swc.cast(c, "IComponent2")
        out[str(gm(k, "Name2"))] = k
    return out


def delta_t16(a, b):
    """(max translation mm, rotation deg) between two ArrayData rows."""
    if a is None or b is None:
        return (float("inf"), float("inf"))
    Ra = np.array(a[:9], float).reshape(3, 3).T
    Rb = np.array(b[:9], float).reshape(3, 3).T
    dt = float(np.abs(np.array(a[9:12]) * 1000 - np.array(b[9:12]) * 1000).max())
    c = max(-1.0, min(1.0, (np.trace(Ra.T @ Rb) - 1.0) / 2.0))
    return dt, float(math.degrees(math.acos(c)))


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
    rows = []
    for s in mate_features(model):
        rows.append({"name": str(gm(s, "Name")),
                     "type": str(gm(s, "GetTypeName2")),
                     "suppressed": bool(gm(s, "IsSuppressed"))})
    return rows
