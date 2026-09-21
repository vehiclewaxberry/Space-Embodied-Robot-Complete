"""POSEMAP-02 S5：集成 staging 七态（5 几何态 + PARTIAL/SERVICE=null）。

复用（只读，不修改 110）：
- 110/staging/layout_staging.py 的 build_revised_primary_structure /
  build_legacy_device_references / build_solar（冻结平台与翼位姿真值源）
替换（单一表示纪律，不与 110 同类模块共存）：
- 110 prior B601 mount 代理 → 本任务 B601_MOUNT_MODULE（FK 真值）
- 110 arm_stow 种子版布局（鞍高 z=145 假设）→ 本任务 B601_STOW_SUPPORT
  （鞍高由 LOD2 STOW 实体实测 z_bottom 主鞍 156.45 / 腕鞍 140.02 导出）
- 110 B601 AABB q0 代理 → 本任务 LOD2 臂（STOW / Q0 按态）
态语义继承 110/design/state_policy.json（太阳翼角与 claim limit 原样），
STOWED 由 HOLD_B601_HIFI_ABSENT 升级为 LOD2_STOW@CANDIDATE_HOLD。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from build123d import Compound, export_step

HERE = Path(__file__).resolve().parent.parent
V22 = HERE.parent
sys.path.insert(0, str(HERE / "src"))
from build_lod2_arm import build_arm, fk_frames
from build_mount_support_capture import (arm_underside, build_mount,
                                          build_support)
from urdf_frame_map_and_stow_fit import parse_chain

NOW = datetime.now(timezone.utc).isoformat()
STAGING_110 = V22 / "110_Layout_and_Deployment_01/staging/layout_staging.py"

STATES = {  # id: (solar_L, solar_R, arm_rep)   角度=110 冻结策略原样
    "STOWED": (0.0, 0.0, "STOW"),
    "DEPLOYED_NOMINAL": (90.0, 90.0, "Q0"),
    "DEPLOY_FAILED_BOTH": (0.0, 0.0, "Q0"),
    "L_FAIL": (0.0, 90.0, "Q0"),
    "R_FAIL": (90.0, 0.0, "Q0"),
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def legacy_devices_without_capture_stack(ls):
    """EE 单一表示纪律：剔除 110 继承的旧捕获末端显示栈（FIDELITY_CAPTURE_*，
    X 480-580）——本任务状态里 EE 表示 = LOD2 夹爪（唯一）。其余继承件
    （含星敏冲突见证件）原样保留。"""
    src = ls.build_legacy_device_references()
    kept = [c for c in list(src.children)
            if "FIDELITY_CAPTURE_" not in str(getattr(c, "label", ""))]
    n_dropped = len(list(src.children)) - len(kept)
    comp = Compound(children=kept,
                    label=src.label + f"_EE_STACK_FILTERED_{n_dropped}")
    return comp, n_dropped


def main():
    ls = _load("layout_staging_110", STAGING_110)
    joints, order = parse_chain()
    stow = json.loads((HERE / "design/b601_stow_joint_vector.json")
                      .read_text(encoding="utf-8"))
    arms = {"STOW": build_arm(fk_frames(joints, order,
                                         np.array(stow["q_rad"], float))),
            "Q0": build_arm(fk_frames(joints, order, np.zeros(6)))}
    arm_stow_solids = arms["STOW"]
    main_c = arm_underside(arm_stow_solids, 40.0, 90.0,
                           ("G6_WRIST_LINK", "G6_J5_MOTOR"))
    wrist_c = arm_underside(arm_stow_solids, -150.0, -110.0,
                            ("G8_RAIL", "G8_FINGER"))

    (HERE / "staging").mkdir(exist_ok=True)
    policy = {"schema_version": "1.0",
              "policy_id": "POSEMAP02_STATE_POLICY", "generated_utc": NOW,
              "inherits": "110/design/state_policy.json（太阳翼角与 claim_limit 原样）",
              "representation_invariant": "LOD2 臂与 AABB q0 代理不得同时出现；"
                                           "每态只允许一种 B601 表示",
              "single_representation_substitutions": [
                  "110 prior B601 mount → B601_MOUNT_MODULE（本任务）",
                  "110 arm_stow 种子布局(z=145) → B601_STOW_SUPPORT（FK 实测鞍高）",
                  "110 AABB q0 proxy → LOD2 臂",
                  "110 旧捕获末端显示栈 FIDELITY_CAPTURE_*(X480-580) → 剔除"
                  "（EE 表示 = LOD2 夹爪唯一；捕获头候选为独立模块不入态）"],
              "states": {}}
    for sid, (l_deg, r_deg, rep) in STATES.items():
        legacy, _nd = legacy_devices_without_capture_stack(ls)
        children = [ls.build_revised_primary_structure(),
                    legacy,
                    ls.build_solar(l_deg, r_deg, f"POSEMAP02_{sid}"),
                    Compound(children=build_mount(),
                             label="MOD_B601_MOUNT_MODULE_POSEMAP02"),
                    Compound(children=build_support(dict(main_c), dict(wrist_c)),
                             label="MOD_B601_STOW_SUPPORT_POSEMAP02"),
                    Compound(children=arms[rep],
                             label=f"MOD_B601_LOD2_{rep}")]
        comp = Compound(children=children, label=f"POSEMAP02_STATE_{sid}")
        path = HERE / f"staging/state_{sid}_LOD2.step"
        export_step(comp, str(path))
        bb = comp.bounding_box()
        policy["states"][sid] = {
            "solar_left_deg": l_deg, "solar_right_deg": r_deg,
            "b601_representation": f"LOD2_{rep}",
            "geometry_binding": f"staging/{path.name}",
            "status": ("CANDIDATE_HOLD_STOW_VECTOR" if sid == "STOWED"
                        else "DIAGNOSTIC_ONLY"),
            "claim_limit": ("收拢向量 CANDIDATE_HOLD，走廊违规 F2 已登记；"
                             "无强度/资格权威" if sid == "STOWED"
                             else "静态命名位姿，无工作空间/连续净空/故障概率权威"),
            "bbox_mm": {"min": [round(bb.min.X, 2), round(bb.min.Y, 2),
                                 round(bb.min.Z, 2)],
                        "max": [round(bb.max.X, 2), round(bb.max.Y, 2),
                                 round(bb.max.Z, 2)]}}
        print(sid, policy["states"][sid]["bbox_mm"])
    for sid, status in (("PARTIAL", "UNKNOWN_HOLD"),
                        ("SERVICE", "PENDING_RATIFICATION_HOLD")):
        policy["states"][sid] = {"solar_left_deg": None, "solar_right_deg": None,
                                  "b601_representation": None,
                                  "geometry_binding": None, "status": status,
                                  "claim_limit": "fail-closed：无几何绑定（继承 110 语义）"}
    (HERE / "design/state_policy_posemap02.json").write_text(
        json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    print("states written:", len(STATES), "+2 null")


if __name__ == "__main__":
    main()
