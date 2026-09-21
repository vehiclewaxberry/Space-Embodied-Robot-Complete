"""POSEMAP-02 S6：机器校验链（MC1-MC11，fail-closed，FAIL 如实登记不消解）。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
V22 = HERE.parent
sys.path.insert(0, str(HERE / "src"))
from build_lod2_arm import build_arm, fk_frames
from urdf_frame_map_and_stow_fit import parse_chain

NOW = datetime.now(timezone.utc).isoformat()


def sha256(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bb_tuple(s):
    bb = s.bounding_box()
    return (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z)


def aabb_overlap(a, b):
    ox = min(a[3], b[3]) - max(a[0], b[0])
    oy = min(a[4], b[4]) - max(a[1], b[1])
    oz = min(a[5], b[5]) - max(a[2], b[2])
    if ox > 0 and oy > 0 and oz > 0:
        return round(ox * oy * oz, 1)
    return 0.0


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    checks = {}
    joints, order = parse_chain()
    stow = json.loads((HERE / "design/b601_stow_joint_vector.json")
                      .read_text(encoding="utf-8"))
    arm_stow = build_arm(fk_frames(joints, order, np.array(stow["q_rad"], float)))
    central = [s for s in arm_stow
               if s.label.split("_")[0] in ("G4", "G5", "G6", "G7", "G8")]

    # MC1 收拢臂中央件走廊 |Y|≤40 —— 预期 FAIL（F1/F2 + 夹爪 154 宽固有）
    max_y = max(max(abs(bb_tuple(s)[1]), abs(bb_tuple(s)[4])) for s in central)
    checks["MC1_ARM_CENTRAL_CORRIDOR"] = {
        "limit": "|Y|<=40", "measured_max_abs_y_mm": round(max_y, 2),
        "status": "PASS" if max_y <= 40.0 else "FAIL_RECORDED",
        "root_cause": "F1 大臂-X后倾不可达 + F2 q1限位/腕部偏置 + 夹爪掌板 154mm 固有宽度；"
                       "URDF 运动学事实，非建模缺陷（stow JSON kinematic_findings）"}

    # MC2 支承模块 |Y|≤113.15
    from build_mount_support_capture import (arm_underside, build_mount,
                                              build_support)
    main_c = arm_underside(arm_stow, 40.0, 90.0, ("G6_WRIST_LINK", "G6_J5_MOTOR"))
    wrist_c = arm_underside(arm_stow, -150.0, -110.0, ("G8_RAIL", "G8_FINGER"))
    sup = build_support(dict(main_c), dict(wrist_c))
    sup_y = max(max(abs(bb_tuple(s)[1]), abs(bb_tuple(s)[4])) for s in sup)
    checks["MC2_SUPPORT_ENVELOPE"] = {
        "limit": "|Y|<=113.15", "measured_max_abs_y_mm": round(sup_y, 2),
        "status": "PASS" if sup_y <= 113.15 else "FAIL_RECORDED",
        "note": "主鞍座 +Y 钳口被包络裁剪弃用→顶部绑带 HOLD（contact registry）"}

    # MC3/MC4 太阳翼收拢宽度 / 展开翼尖（110 冻结源实测）
    ls = _load("ls110", V22 / "110_Layout_and_Deployment_01/staging/layout_staging.py")
    s0 = ls.build_solar(0.0, 0.0, "MC3")
    b0 = s0.bounding_box()
    w0 = b0.max.Y - b0.min.Y
    checks["MC3_STOWED_SOLAR_WIDTH"] = {
        "limit": "<=226.3", "measured_mm": round(w0, 2),
        "status": "PASS" if w0 <= 226.3 + 1e-6 else "FAIL_RECORDED"}
    s9 = ls.build_solar(90.0, 90.0, "MC4")
    b9 = s9.bounding_box()
    checks["MC4_DEPLOYED_TIPS"] = {
        "limit": "y=±310", "measured_mm": [round(b9.min.Y, 2), round(b9.max.Y, 2)],
        "status": ("PASS" if abs(b9.max.Y - 310.0) < 0.5
                    and abs(b9.min.Y + 310.0) < 0.5 else "FAIL_RECORDED")}

    # MC5 L_FAIL ≠ R_FAIL（文件哈希互异）
    hl = sha256(HERE / "staging/state_L_FAIL_LOD2.step")
    hr = sha256(HERE / "staging/state_R_FAIL_LOD2.step")
    checks["MC5_LFAIL_NEQ_RFAIL"] = {
        "sha256_L": hl[:16], "sha256_R": hr[:16],
        "status": "PASS" if hl != hr else "FAIL_RECORDED"}

    # MC6 质量排除：生成 STEP 无密度/质量实体，URDF 总质量数字不得出现
    mass_hits = []
    for p in sorted((HERE / "cad").glob("*.step")) + sorted(
            (HERE / "staging").glob("*.step")):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if "DENSITY" in txt.upper() or "4.6955559" in txt:
            mass_hits.append(p.name)
    checks["MC6_MASS_EXCLUSION"] = {
        "rule": "MASS_AUTHORITY=EXCLUDED（URDF 4.695555949342986 kg 唯一权威）",
        "density_or_mass_hits": mass_hits,
        "status": "PASS" if not mass_hits else "FAIL_RECORDED"}

    # MC7 权威哈希复核（G1 四项）
    pre = json.loads((HERE / "validation/frozen_zone_precheck.json")
                     .read_text(encoding="utf-8"))
    auth_paths = {
        "canonical_top": V22 / "Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM",
        "accepted_urdf": V22.parent / "spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "registered_step": Path(pre["hashes"]["registered_step"]["path"]),
        "scratch_native": Path(pre["hashes"]["scratch_native"]["path"])}
    match = {}
    for k, p in auth_paths.items():
        match[k] = (p.exists() and sha256(p) == pre["hashes"][k]["sha256"])
    checks["MC7_AUTHORITY_HASHES_UNCHANGED"] = {
        "match": match, "status": "PASS" if all(match.values()) else "FAIL_RECORDED"}

    # MC8 EE 互斥：候选捕获头(CAP_*)与 110 旧捕获显示栈(FIDELITY_CAPTURE_*)
    # 都不得出现在任何状态 STEP（EE 表示 = LOD2 夹爪唯一）
    cap_hits = []
    for p in sorted((HERE / "staging").glob("state_*.step")):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for marker in ("CAP_INTERFACE_RING", "FIDELITY_CAPTURE_"):
            if marker in txt:
                cap_hits.append(f"{p.name}:{marker}")
    checks["MC8_EE_MUTUAL_EXCLUSIVITY"] = {
        "rule": "B601 夹爪与捕获头二选一；旧 110 捕获显示栈已按单一表示纪律剔除",
        "capture_representation_hits": cap_hits,
        "status": "PASS" if not cap_hits else "FAIL_RECORDED"}

    # MC9 X 包络：STOW 臂 ≤430（厂商折叠参考），支承在 [-183, 198]
    arm_xmax = max(bb_tuple(s)[3] for s in arm_stow)
    sup_x = [min(bb_tuple(s)[0] for s in sup), max(bb_tuple(s)[3] for s in sup)]
    checks["MC9_X_ENVELOPE"] = {
        "arm_stow_max_x_mm": round(arm_xmax, 2), "arm_limit": 430.0,
        "support_x_range_mm": [round(v, 2) for v in sup_x],
        "support_limit": [-183.0, 198.0],
        "status": ("PASS" if arm_xmax <= 430.0 and sup_x[0] >= -183.0
                    and sup_x[1] <= 198.0 else "FAIL_RECORDED")}

    # MC10 越顶净空：跨舱面（X<183）中央件底高 > 平台顶 113.15
    over_deck = [s for s in central if bb_tuple(s)[0] < 183.0]
    min_z = min(bb_tuple(s)[2] for s in over_deck)
    checks["MC10_OVERTOP_CLEARANCE"] = {
        "deck_z_mm": 113.15, "measured_min_z_mm": round(min_z, 2),
        "margin_mm": round(min_z - 113.15, 2),
        "status": "PASS" if min_z > 113.15 else "FAIL_RECORDED"}

    # MC11 AABB 干涉分类：支承/安装 vs 臂（垫接触=预期；钳口 vs 非夹持件=违规）
    mnt = build_mount()
    pairs = []
    for s in sup + mnt:
        for a in arm_stow:
            v = aabb_overlap(bb_tuple(s), bb_tuple(a))
            if v <= 0:
                continue
            intended = ("CONTACT_PAD" in s.label and
                        any(a.label.startswith(p) for p in
                            ("G6_WRIST_LINK", "G6_J5_MOTOR", "G8_RAIL",
                             "G8_FINGER")))
            pairs.append({"support": s.label, "arm": a.label,
                          "aabb_overlap_mm3": v,
                          "class": ("INTENDED_CONTACT" if intended
                                     else "AABB_COARSE_REVIEW")})
        # 塔/钳口与非夹持件的粗判交由 AABB_COARSE_REVIEW 分类，精判待 L3
    viol = [p for p in pairs if p["class"] != "INTENDED_CONTACT"]
    checks["MC11_SUPPORT_ARM_INTERFERENCE"] = {
        "method": "AABB 粗判（LOD2 无精确布尔干涉权威）",
        "pairs": pairs,
        "coarse_review_count": len(viol),
        "status": "REGISTERED_COARSE_DIAGNOSTIC_NOT_A_GATE",
        "note": "登记器而非校验器（对抗评审 M3 裁定）：本检查按构造不可能 FAIL——"
                 "接触垫顶面与臂底切贴使 AABB 重叠恒为零，INTENDED_CONTACT 无法由"
                 "AABB 证实；真实干涉判定留待 L3 精判，不计入 PASS/FAIL 汇总"}

    n_fail = sum(1 for c in checks.values() if c["status"].startswith("FAIL"))
    out = {"validation_id": "POSEMAP02_MACHINE_CHECKS", "generated_utc": NOW,
           "checks": checks,
           "summary": {"total": len(checks),
                        "pass": sum(1 for c in checks.values()
                                    if c["status"].startswith("PASS")),
                        "fail_recorded": n_fail,
                        "diagnostic_not_gate": sum(
                            1 for c in checks.values()
                            if c["status"].startswith("REGISTERED"))}}
    (HERE / "validation/machine_checks.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, c in checks.items():
        print(k, c["status"])
    print("SUMMARY", out["summary"])


if __name__ == "__main__":
    main()
