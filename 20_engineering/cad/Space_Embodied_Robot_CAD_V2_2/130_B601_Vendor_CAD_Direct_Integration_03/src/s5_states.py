"""VENDOR-CAD-03 S5b：七态（5 几何态轻量上下文 + 双文件绑定 + 2 null）。

真实厂商臂 STEP 为 252MB/位姿（抽取去实例化膨胀）——态文件不烘焙臂几何，
采用双文件绑定：state = 轻量上下文 STEP（平台+器件+翼+适配器+支承）+
design/state_policy_vendorcad03.json 中的臂引用（文件+位姿+恒等放置）。
单一表示纪律沿用 120（EE 栈过滤等）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from build123d import Compound, export_step

HERE = Path(__file__).resolve().parent.parent
V22 = HERE.parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(V22 / "120_B601_Geometry_and_PoseMap_02/src"))
import s4_repose as s4
from s4c_adapter_support import (build_adapter, build_support, contact_all,
                                  stow_vertices)

NOW = datetime.now(timezone.utc).isoformat()
STAGING_110 = V22 / "110_Layout_and_Deployment_01/staging/layout_staging.py"

STATES = {"STOWED": (0.0, 0.0, "STOW"),
          "DEPLOYED_NOMINAL": (90.0, 90.0, "Q0"),
          "DEPLOY_FAILED_BOTH": (0.0, 0.0, "Q0"),
          "L_FAIL": (0.0, 90.0, "Q0"),
          "R_FAIL": (90.0, 0.0, "Q0")}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def legacy_filtered(ls):
    src = ls.build_legacy_device_references()
    kept = [c for c in list(src.children)
            if "FIDELITY_CAPTURE_" not in str(getattr(c, "label", ""))]
    return Compound(children=kept, label=src.label + "_EE_STACK_FILTERED")


def main():
    ls = _load("ls110", STAGING_110)
    clock = s4._clock_deg()
    sv = stow_vertices()
    windows = {"MAIN": (10.0, 60.0), "GRIP": (-100.0, -40.0)}
    main_c = contact_all(sv, *windows["MAIN"])
    grip_c = contact_all(sv, *windows["GRIP"])

    (HERE / "staging").mkdir(exist_ok=True)
    policy = {"schema_version": "1.0",
              "policy_id": "VENDORCAD03_STATE_POLICY", "generated_utc": NOW,
              "binding_mode": "TWO_FILE（上下文 STEP + 臂引用；臂不烘焙，252MB）",
              "inherits": "110 state_policy 太阳翼角/claim_limit + 120 单一表示替换",
              "arm_files": {"STOW": "cad/B601_VENDOR_STOW.step",
                             "Q0": "cad/B601_VENDOR_Q0.step",
                             "placement": "IDENTITY（臂 STEP 已在 CS_S）",
                             "adapter_clock_deg": clock},
              "states": {}}
    for sid, (l_deg, r_deg, rep) in STATES.items():
        children = [ls.build_revised_primary_structure(),
                    legacy_filtered(ls),
                    ls.build_solar(l_deg, r_deg, f"VENDORCAD03_{sid}"),
                    Compound(children=build_adapter(clock),
                             label="MOD_B601_SPACECRAFT_ADAPTER"),
                    Compound(children=build_support(dict(main_c), dict(grip_c),
                                                     windows),
                             label="MOD_B601_STOW_SUPPORT_V2")]
        comp = Compound(children=children, label=f"VENDORCAD03_CTX_{sid}")
        path = HERE / f"staging/state_{sid}_CONTEXT.step"
        export_step(comp, str(path))
        bb = comp.bounding_box()
        policy["states"][sid] = {
            "solar_left_deg": l_deg, "solar_right_deg": r_deg,
            "b601_representation": f"VENDOR_REAL_{rep}",
            "context_step": f"staging/{path.name}",
            "arm_ref": policy["arm_files"]["STOW" if rep == "STOW" else "Q0"],
            "status": ("CANDIDATE_HOLD_STOW_VECTOR_V2" if sid == "STOWED"
                        else "DIAGNOSTIC_ONLY"),
            "context_bbox_mm": [round(v, 2) for v in
                                 (bb.min.X, bb.min.Y, bb.min.Z,
                                  bb.max.X, bb.max.Y, bb.max.Z)]}
        print(sid, policy["states"][sid]["context_bbox_mm"])
    for sid, st in (("PARTIAL", "UNKNOWN_HOLD"),
                    ("SERVICE", "PENDING_RATIFICATION_HOLD")):
        policy["states"][sid] = {"solar_left_deg": None, "solar_right_deg": None,
                                  "b601_representation": None,
                                  "context_step": None, "arm_ref": None,
                                  "status": st,
                                  "claim_limit": "fail-closed：无几何绑定"}
    (HERE / "design/state_policy_vendorcad03.json").write_text(
        json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    print("states:", len(STATES), "+2 null")


if __name__ == "__main__":
    main()
