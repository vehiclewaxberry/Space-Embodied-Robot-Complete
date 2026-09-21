"""VENDOR-CAD-03 S6b：机器校验链 V1-V12（fail-closed；负结果如实登记）。"""
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
import s4_repose as s4
from s4b_mesh_cache import SCRATCH
from s4c_adapter_support import (build_adapter, build_support, contact_all,
                                  stow_vertices)

NOW = datetime.now(timezone.utc).isoformat()
PLAT_Y = 113.15


def sha256(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def stream_find(p: Path, needles):
    hits = set()
    tail = b""
    with open(p, "rb") as f:
        while True:
            chunk = f.read(1 << 22)
            if not chunk:
                break
            buf = tail + chunk
            for n in needles:
                if n.encode() in buf:
                    hits.add(n)
            tail = buf[-64:]
    return sorted(hits)


def main():
    checks = {}
    sv = stow_vertices()
    allv = np.vstack(list(sv.values()))

    # V1 STOW 走廊（用户重定义：|Y|≤113.15 余量制；120 的 |Y|≤40 保留为负发现）
    max_y = float(np.abs(allv[:, 1]).max())
    checks["V1_STOW_FULLWIDTH_CORRIDOR"] = {
        "limit": "|Y|<=113.15（走廊重定义裁决 2026-07-27）",
        "measured_max_abs_y_mm": round(max_y, 2),
        "margin_mm": round(PLAT_Y - max_y, 2),
        "status": "PASS" if max_y <= PLAT_Y else "FAIL_RECORDED",
        "legacy_negative_finding": "120 MC1 |Y|≤40 FAIL_RECORDED 保留，不作为通过条件",
        "enabler": "适配器 25° 时钟角（消除 q1 限位强制平面倾斜）"}

    # V2 X 包络
    max_x = float(allv[:, 0].max())
    checks["V2_X_ENVELOPE"] = {"limit": "<=430", "measured_mm": round(max_x, 2),
                                "status": "PASS" if max_x <= 430 else "FAIL_RECORDED"}

    # V3 越顶舱面净空
    over = allv[allv[:, 0] < 183.0]
    min_z = float(over[:, 2].min())
    checks["V3_OVERTOP_CLEARANCE"] = {
        "deck_z": 113.15, "measured_min_z_mm": round(min_z, 2),
        "margin_mm": round(min_z - 113.15, 2),
        "status": "PASS" if min_z > 113.15 else "FAIL_RECORDED"}

    # V4/V12 支承包络 + 顶点级干涉分类
    windows = {"MAIN": (10.0, 60.0), "GRIP": (-100.0, -40.0)}
    main_c = contact_all(sv, *windows["MAIN"])
    grip_c = contact_all(sv, *windows["GRIP"])
    sup = build_support(dict(main_c), dict(grip_c), windows)
    sup_y = max(max(abs(s.bounding_box().min.Y), abs(s.bounding_box().max.Y))
                for s in sup)
    checks["V4_SUPPORT_ENVELOPE"] = {
        "limit": "|Y|<=113.15", "measured_mm": round(float(sup_y), 2),
        "status": "PASS" if sup_y <= PLAT_Y + 1e-6 else "FAIL_RECORDED"}
    intr = []
    for s in sup:
        bb = s.bounding_box()
        lo = np.array([bb.min.X, bb.min.Y, bb.min.Z])
        hi = np.array([bb.max.X, bb.max.Y, bb.max.Z])
        inside = int(np.sum(np.all((allv >= lo) & (allv <= hi), axis=1)))
        if inside:
            cls = ("INTENDED_CONTACT" if "CONTACT_PAD" in s.label
                    else "INTRUSION_RECORDED")
            intr.append({"solid": s.label, "arm_vertices_inside": inside,
                          "class": cls})
    real_intr = [i for i in intr if i["class"] == "INTRUSION_RECORDED"]
    checks["V12_SUPPORT_ARM_VERTEX_INTERFERENCE"] = {
        "method": "臂网格顶点 ∈ 支承实体 AABB（箱体为主，AABB≈紧）",
        "records": intr,
        "status": "PASS" if not real_intr else "FAIL_RECORDED"}

    # V5/V6 翼收拢宽 / 展开翼尖（110 冻结源）
    ls_spec = importlib.util.spec_from_file_location(
        "ls110", V22 / "110_Layout_and_Deployment_01/staging/layout_staging.py")
    ls = importlib.util.module_from_spec(ls_spec)
    ls_spec.loader.exec_module(ls)
    b0 = ls.build_solar(0.0, 0.0, "V5").bounding_box()
    b9 = ls.build_solar(90.0, 90.0, "V6").bounding_box()
    w0 = b9  # noqa placeholder avoided
    width0 = b0.max.Y - b0.min.Y
    checks["V5_STOWED_SOLAR_WIDTH"] = {
        "limit": "<=226.3", "measured_mm": round(float(width0), 2),
        "status": "PASS" if width0 <= 226.3 + 1e-6 else "FAIL_RECORDED"}
    checks["V6_DEPLOYED_TIPS"] = {
        "limit": "±310", "measured_mm": [round(float(b9.min.Y), 2),
                                          round(float(b9.max.Y), 2)],
        "status": ("PASS" if abs(b9.max.Y - 310) < 0.5 and abs(b9.min.Y + 310) < 0.5
                    else "FAIL_RECORDED")}

    # V7 L≠R
    hl = sha256(HERE / "staging/state_L_FAIL_CONTEXT.step")
    hr = sha256(HERE / "staging/state_R_FAIL_CONTEXT.step")
    checks["V7_LFAIL_NEQ_RFAIL"] = {"sha_L": hl[:16], "sha_R": hr[:16],
                                     "status": "PASS" if hl != hr else "FAIL_RECORDED"}

    # V8 质量排除（流式扫描本轮产物；URDF 总质量数字/DENSITY 不得出现）
    hits = {}
    for p in sorted((HERE / "cad").glob("*.step")) + sorted(
            (HERE / "staging").glob("*.step")):
        h = stream_find(p, ["DENSITY", "4.6955559"])
        if h:
            hits[p.name] = h
    checks["V8_MASS_EXCLUSION"] = {
        "rule": "MASS_AUTHORITY=EXCLUDED（URDF 唯一）",
        "hits": hits, "status": "PASS" if not hits else "FAIL_RECORDED"}

    # V9 权威哈希（登记厂商 STEP + accepted URDF）
    lock = json.loads((HERE / "validation/s0_input_lock.json")
                      .read_text(encoding="utf-8"))
    m1 = sha256(Path(lock["vendor_step"]["path"])) == lock["vendor_step"]["sha256"]
    m2 = sha256(Path(lock["accepted_urdf"]["path"])) == lock["accepted_urdf"]["sha256"]
    checks["V9_AUTHORITY_HASHES"] = {
        "vendor_step_match": m1, "accepted_urdf_match": m2,
        "status": "PASS" if (m1 and m2) else "FAIL_RECORDED"}

    # V10 时钟角一致性
    clock = s4._clock_deg()
    v2 = json.loads((HERE / "design/b601_stow_joint_vector_v2.json")
                    .read_text(encoding="utf-8"))
    checks["V10_CLOCKING_CONSISTENCY"] = {
        "adapter_json_deg": clock, "stow_v2_deg": v2["adapter_clock_deg"],
        "q1_deg": v2["q_deg"][0], "q1_limit_deg": 160.428,
        "q1_margin_deg": round(160.428 - abs(v2["q_deg"][0]), 2),
        "status": ("PASS" if clock == v2["adapter_clock_deg"]
                    and abs(v2["q_deg"][0]) < 160.428 else "FAIL_RECORDED")}

    # V11 EE 单一表示（上下文无捕获栈；臂=真实夹爪唯一）
    ee_hits = {}
    for p in sorted((HERE / "staging").glob("state_*_CONTEXT.step")):
        h = stream_find(p, ["FIDELITY_CAPTURE_", "CAP_INTERFACE_RING"])
        if h:
            ee_hits[p.name] = h
    checks["V11_EE_SINGLE_REPRESENTATION"] = {
        "hits": ee_hits, "status": "PASS" if not ee_hits else "FAIL_RECORDED"}

    # 设备搬移核查：舱顶器件 vs 臂越顶链（+5mm 膨胀盒）
    dev = ls.build_legacy_device_references()
    conflicts = []
    def walk(c):
        kids = list(getattr(c, "children", []) or [])
        if not kids:
            bb = c.bounding_box()
            lo = np.array([bb.min.X, bb.min.Y, bb.min.Z]) - 5
            hi = np.array([bb.max.X, bb.max.Y, bb.max.Z]) + 5
            n = int(np.sum(np.all((allv >= lo) & (allv <= hi), axis=1)))
            if n and bb.max.Z > 113.0:
                conflicts.append({"device": str(c.label),
                                   "arm_vertices_within_5mm": n})
        for k in kids:
            walk(k)
    walk(dev)
    checks["V13_TOP_EQUIPMENT_RELOCATION_CHECK"] = {
        "ruling": "扩大中央臂区并搬移顶部设备（用户 2026-07-27）——冲突清单如实登记，"
                    "110 冻结布局不静默改动，搬移需另行裁决",
        "conflicts": conflicts,
        "status": ("PASS_NO_RELOCATION_NEEDED" if not conflicts
                    else "RELOCATION_PROPOSAL_REQUIRED")}

    # V14 适配器/支承 vs 冻结主结构（自审 D 镜头补课：原验证链无此覆盖）
    def leaves(c, out):
        kids = list(getattr(c, "children", []) or [])
        if not kids:
            out.append(c)
        for k in kids:
            leaves(k, out)
    struct = []
    leaves(ls.build_revised_primary_structure(), struct)

    def bb6(s):
        b = s.bounding_box()
        return (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z)

    def ovol(a, b):
        o = [min(a[3 + i], b[3 + i]) - max(a[i], b[i]) for i in range(3)]
        return round(o[0] * o[1] * o[2], 1) if all(v > 0 for v in o) else 0.0
    adapter = build_adapter(clock)
    inter = []
    for m in adapter + sup:
        for p in struct:
            v = ovol(bb6(m), bb6(p))
            if v > 1000.0:
                lab = str(getattr(p, "label", "?"))
                cls = ("RESERVATION_PASSTHROUGH_EXPECTED"
                        if "NON_PHYSICAL" in m.label else
                        "UNADJUDICATED_INTERPENETRATION")
                inter.append({"module_solid": m.label, "structure": lab[:60],
                               "aabb_overlap_mm3": v, "class": cls})
    unadj = [i for i in inter if i["class"] == "UNADJUDICATED_INTERPENETRATION"]
    checks["V14_MODULE_VS_FROZEN_STRUCTURE"] = {
        "method": "AABB 粗判（箱体为主）；>1000mm³ 才登记",
        "records": inter, "unadjudicated_count": len(unadj),
        "status": "PASS" if not unadj else "FAIL_RECORDED",
        "note": "扩散板/载荷桥与前框、纵梁的接合面尚未做工程分模（贴合 vs 互穿）；"
                 "属接口未裁决，不得当作已验证连接"}

    n_fail = sum(1 for c in checks.values() if c["status"].startswith("FAIL"))
    out = {"validation_id": "VENDORCAD03_MACHINE_CHECKS", "generated_utc": NOW,
           "checks": checks,
           "summary": {"total": len(checks),
                        "pass": sum(1 for c in checks.values()
                                    if c["status"].startswith("PASS")),
                        "fail_recorded": n_fail,
                        "other": sum(1 for c in checks.values()
                                     if not c["status"].startswith(("PASS", "FAIL")))}}
    (HERE / "validation/machine_checks.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, c in checks.items():
        print(k, c["status"])
    print("SUMMARY", out["summary"])


if __name__ == "__main__":
    main()
