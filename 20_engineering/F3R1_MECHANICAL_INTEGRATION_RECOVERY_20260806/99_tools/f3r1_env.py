# -*- coding: utf-8 -*-
"""F3R1 environment: paths, logging, protected-hash guard.

Every F3R1 CAD script imports this. It re-points b3_lib's log dir into the F3R1
workspace (b3_lib's default writes into the V2_0 evidence tree, which this ECR
must not touch) and provides the protected-asset guard used by PRE/POST checks.
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition")
ENG = REPO / "20_engineering"
F3R1 = ENG / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806"
LOGS = F3R1 / "99_tools" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

# --- make b3_lib importable and re-point its evidence dir into F3R1 ---
sys.path.insert(0, str(F3R1 / "99_tools"))
import b3_lib.sw_core as sw_core  # noqa: E402

sw_core.LOG_DIR = LOGS  # never write into V2_0 evidence

SW_EXE = r"F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe"

# --- protected assets: READ-ONLY truths (ECR-F3R1-001 section 2) ---
PROTECTED = {
    "accepted_b601_urdf": {
        "path": REPO / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "sha256": "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4",
    },
    "mass_inertia_budget": {
        "path": REPO / "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv",
        "sha256": "073C802527E35C9495188EEFD5D8BA51F524D326142CF2AB31E436BAD0899392",
    },
    "v2_2_native_donor_top": {
        "path": REPO / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
        "sha256": "30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A",
    },
    "b51_articulated_arm_donor": {
        "path": REPO / "20_engineering/cad/B5_1_B601_interface_closure_candidate/03_CAD/native_articulated/B51_ARTICULATED_20260728T008/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM",
        "sha256": "603B87BBD4398FDDB3F732FFBFA7E1C080ED91ED6E0A026D56CBDCBA08DE2E22",
    },
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()


def check_protected(tag):
    """Verify every protected asset digest; returns report dict; raises on drift."""
    rep = {"tag": tag, "utc": datetime.now(timezone.utc).isoformat(), "assets": {}}
    bad = []
    for name, spec in PROTECTED.items():
        p = spec["path"]
        if not p.is_file():
            rep["assets"][name] = {"status": "MISSING", "path": str(p)}
            bad.append(name)
            continue
        actual = sha256_file(p)
        ok = actual == spec["sha256"].upper()
        rep["assets"][name] = {"status": "MATCH" if ok else "DRIFT",
                               "declared": spec["sha256"].upper(), "actual": actual,
                               "path": str(p)}
        if not ok:
            bad.append(name)
    rep["verdict"] = "ALL_PROTECTED_UNCHANGED" if not bad else "PROTECTED_DRIFT_" + ",".join(bad)
    out = F3R1 / "00_authority" / f"F3R1_PROTECTED_CHECK_{tag}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, ensure_ascii=False)
    if bad:
        raise RuntimeError("PROTECTED ASSET DRIFT: %s" % bad)
    return rep


class JLog:
    """jsonl event logger for build scripts."""

    def __init__(self, name):
        self.path = LOGS / (name + ".jsonl")

    def ev(self, event, **kw):
        rec = {"utc": datetime.now(timezone.utc).isoformat(), "event": event}
        rec.update(kw)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        print("[%s] %s %s" % (time.strftime("%H:%M:%S"), event,
                              json.dumps(kw, ensure_ascii=False, default=str)[:220]))
