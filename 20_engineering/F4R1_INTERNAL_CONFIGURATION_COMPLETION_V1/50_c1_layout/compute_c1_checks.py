#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_c1_checks.py — F4R1 C1 质量/CG/惯量机器核算
=====================================================
DESIGN_RESEARCH_CANDIDATE — 不改写任何冻结文件, 只读验证 + 输出 CG_INERTIA_CHECK_V1.json

方法说明 (method):
1. 输入: EQUIPMENT_LIST_V1.yaml (受控 YAML 子集, 内置小解析器, 仅用标准库),
   MASS_BUDGET_V1.csv, FROZEN_MASS_EXTRACT_C01.json (冻结 C01 提取, 含源 sha256 前12位).
2. 完整性: 对两个冻结源文件实测 sha256, 与 extract 记录值比对, 不一致即 FAIL 退出.
3. 质量预算核算: 重算 SUBTOTAL/TOTAL/RECON 各行并与 CSV 记录比对 (tol 1e-6 kg);
   V2 placeholder 9 行合计必须等于新设备小计; 调和未解释项必须为 0.
4. CG/惯量合成 (S frame, 原点=12U几何中心, 单位 m/kg):
   - 设备按均质长方体近似: 自身惯量 Ixx=m/12*(ey^2+ez^2) 等, 平行移轴至 S 原点.
   - 冻结 C01 聚合体在场景 A/B 中作为单一刚体 (质量+CG+关于系统 CG 的完整惯量张量).
   - 场景 A (CARVE_OUT, 主读法): 总质量恒 31.022865 kg —— 新增设备质量视作从 FRZ-BUS
     包络块中"切出"(切出块按位于 bus CG 的质点近似, 自身惯量忽略, 聚合体保留全张量,
     该近似使惯量略偏保守), 再加到指定位置. 对应 M1 读法 A: 31.02 kg 已隐含设备分摊.
   - 场景 B (ADDITIVE, 上限读法): 冻结聚合体 + 新增设备直接相加 = 36.659865 kg.
     对应 M1 读法 B: C01 行项目无设备行, 设备另加.
   - 场景 CDS_VARIANT: 自下而上真实构建 = ST-STRUCT-REAL(2.0 kg, B1 表3) + EQ-SEC-STRUCT
     + 冻结成员(臂/M3R/桥/双帆板, 按质点近似, 仅惯量信息性输出受影响) + 全部新设备.
5. CDS CG 包络: CDS Rev14.1 原点=几何中心, Z=纵轴 ±7 cm, X/Y ±4.5 cm;
   S frame x=纵轴 -> 映射为 S_x ±70 mm, S_y ±45 mm, S_z ±45 mm (见 extract 注记).
6. 配重迭代 (确定性): 仅当场景 CG 超差时启动; 旋钮限定为 mid/rear 舱内设备 x 向位置
   (治理约束), 按质量降序逐个向有益方向以 0.25 mm 步进推移至舱内边界, 每步复算;
   y/z 不受 x 旋钮影响, 若 y/z 超差则记 NOT_ADDRESSABLE. 全部旋钮耗尽仍超差 -> INFEASIBLE.
7. 输出 CG_INERTIA_CHECK_V1.json (本脚本唯一写文件).

运行: python compute_c1_checks.py   (Windows Git Bash, 仅标准库)
"""

import csv
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

EQUIPMENT_YAML = os.path.join(HERE, "EQUIPMENT_LIST_V1.yaml")
BUDGET_CSV = os.path.join(HERE, "MASS_BUDGET_V1.csv")
EXTRACT_JSON = os.path.join(HERE, "FROZEN_MASS_EXTRACT_C01.json")
OUT_JSON = os.path.join(HERE, "CG_INERTIA_CHECK_V1.json")

TOL_KG = 1e-6
CDS_TOL_MM = {"x": 70.0, "y": 45.0, "z": 45.0}  # CDS_Z(纵轴)=S_x ±7cm; CDS_X/Y=S_y/S_z ±4.5cm


# ---------- 受控 YAML 子集小解析器 (仅服务本目录 EQUIPMENT_LIST_V1.yaml) ----------
def parse_scalar(text):
    text = text.strip()
    if text == "" or text == '""':
        return ""
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(p) for p in inner.split(",")]
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    if text in ("UNKNOWN", "null", "None"):
        return text if text == "UNKNOWN" else None
    try:
        if any(c in text for c in (".", "e", "E")) and not text.lstrip("-").isalpha():
            return float(text)
        return int(text)
    except ValueError:
        return text


def load_equipment_yaml(path):
    """解析 frontmatter + `equipment:` 列表 (每项为 `- id:` 起始的 4 空格缩进键值块)。"""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    # 去 frontmatter
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1 :]
                break
    items, current, in_equipment = [], None, False
    for raw in lines:
        if raw.strip().startswith("#"):
            continue
        if raw.rstrip() == "equipment:":
            in_equipment = True
            continue
        if not in_equipment:
            continue
        if raw.startswith("  - "):
            if current is not None:
                items.append(current)
            current = {}
            first = raw[4:]
            if ":" in first:
                k, v = first.split(":", 1)
                current[k.strip()] = parse_scalar(v)
        elif raw.startswith("    ") and current is not None and ":" in raw:
            k, v = raw.strip().split(":", 1)
            current[k.strip()] = parse_scalar(v)
        elif raw and not raw.startswith(" "):
            break
    if current is not None:
        items.append(current)
    for it in items:
        for field in ("id", "mass_g", "pos_mm", "envelope_mm", "status"):
            if field not in it:
                raise ValueError("EQUIPMENT_LIST 缺字段 %s: %s" % (field, it.get("id")))
    return items


# ---------- 工具 ----------
def sha256_12(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def mat3_vec(t, v):
    return [sum(t[i][j] * v[j] for j in range(3)) for i in range(3)]


def inertia_point_shift(m, d):
    """质点平行移轴: m*(|d|^2 I3 - d d^T), d 单位 m。"""
    d2 = sum(x * x for x in d)
    return [
        [m * (d2 - d[0] * d[0]), -m * d[0] * d[1], -m * d[0] * d[2]],
        [-m * d[1] * d[0], m * (d2 - d[1] * d[1]), -m * d[1] * d[2]],
        [-m * d[2] * d[0], -m * d[2] * d[1], m * (d2 - d[2] * d[2])],
    ]


def mat3_add(a, b):
    return [[a[i][j] + b[i][j] for j in range(3)] for i in range(3)]


def cuboid_own_inertia(m_kg, envelope_mm):
    """均质长方体自身惯量 (关于自身质心), envelope 单位 mm -> m。"""
    ex, ey, ez = [v / 1000.0 for v in envelope_mm]
    return [
        [m_kg / 12.0 * (ey * ey + ez * ez), 0.0, 0.0],
        [0.0, m_kg / 12.0 * (ex * ex + ez * ez), 0.0],
        [0.0, 0.0, m_kg / 12.0 * (ex * ex + ey * ey)],
    ]


class Body:
    """name, mass kg, cg m (S frame), inertia about own cg (S frame)."""

    def __init__(self, name, m, cg, i_own=None):
        self.name = name
        self.m = m
        self.cg = list(cg)
        self.i_own = i_own if i_own is not None else [[0.0] * 3 for _ in range(3)]


def combine(bodies):
    """合成: 返回 (total_mass, cg_m, inertia_about_new_cg)。"""
    m_tot = sum(b.m for b in bodies)
    cg = [sum(b.m * b.cg[i] for b in bodies) / m_tot for i in range(3)]
    i_tot = [[0.0] * 3 for _ in range(3)]
    for b in bodies:
        d = [b.cg[i] - cg[i] for i in range(3)]
        i_tot = mat3_add(i_tot, mat3_add(b.i_own, inertia_point_shift(b.m, d)))
    return m_tot, cg, i_tot


def pos_m(item):
    return [v / 1000.0 for v in item["pos_mm"]]


def cg_margins(cg_m):
    cg_mm = [v * 1000.0 for v in cg_m]
    margins = {
        "x": CDS_TOL_MM["x"] - abs(cg_mm[0]),
        "y": CDS_TOL_MM["y"] - abs(cg_mm[1]),
        "z": CDS_TOL_MM["z"] - abs(cg_mm[2]),
    }
    passed = all(v >= 0.0 for v in margins.values())
    return cg_mm, margins, passed


# ---------- 主流程 ----------
def main():
    problems = []

    with open(EXTRACT_JSON, encoding="utf-8") as fh:
        extract = json.load(fh)

    # 1) 冻结源完整性
    source_integrity = {}
    for key, meta in extract["source_files"].items():
        p = os.path.join(REPO_ROOT, meta["path"].replace("/", os.sep))
        actual = sha256_12(p)
        ok = actual == meta["sha256_12"]
        source_integrity[key] = {
            "path": meta["path"],
            "expected_sha256_12": meta["sha256_12"],
            "actual_sha256_12": actual,
            "match": ok,
        }
        if not ok:
            problems.append("sha256 mismatch: %s" % meta["path"])
    if problems:
        print("FATAL: 冻结源哈希不匹配, 终止。")
        for pr in problems:
            print(" -", pr)
        sys.exit(2)

    # 2) 读设备清单与预算表
    equipment = load_equipment_yaml(EQUIPMENT_YAML)
    eq = {it["id"]: it for it in equipment}
    with open(BUDGET_CSV, encoding="utf-8") as fh:
        budget = {r["line_id"]: r for r in csv.DictReader(fh)}

    mass_check = {"details": [], "result": "pass"}
    check_tol = lambda name, got, want: (
        mass_check["details"].append({"row": name, "computed_kg": got, "csv_kg": want, "ok": abs(got - want) <= TOL_KG}),
        None if abs(got - want) <= TOL_KG else mass_check.update(result="fail"),
    )

    frz_ids = ["FRZ-BUS", "FRZ-B601", "FRZ-M3R", "FRZ-BRIDGE", "FRZ-SOLAR-L", "FRZ-SOLAR-R"]
    eq_ids = sorted(i for i in eq if i.startswith("EQ-"))
    eq_only = [i for i in eq_ids if i != "EQ-SEC-STRUCT"]

    # EQ 行 csv 与 yaml 质量一致
    for i in eq_ids + frz_ids + ["ST-STRUCT-REAL"]:
        check_tol(i, eq[i]["mass_g"] / 1000.0, float(budget[i]["mass_kg"]))

    frz_sum = sum(eq[i]["mass_g"] for i in frz_ids) / 1000.0
    check_tol("SUBTOTAL-FROZEN-C01", frz_sum, float(budget["SUBTOTAL-FROZEN-C01"]["mass_kg"]))
    check_tol("SUBTOTAL-FROZEN-C01 vs extract aggregate", frz_sum, extract["aggregate"]["mass_kg"])

    eq_sum = sum(eq[i]["mass_g"] for i in eq_only) / 1000.0
    sec_sum = eq["EQ-SEC-STRUCT"]["mass_g"] / 1000.0
    check_tol("SUBTOTAL-EQUIPMENT-NEW", eq_sum, float(budget["SUBTOTAL-EQUIPMENT-NEW"]["mass_kg"]))
    check_tol("SUBTOTAL-SECONDARY-NEW", sec_sum, float(budget["SUBTOTAL-SECONDARY-NEW"]["mass_kg"]))

    v2ph_sum = sum(float(v["mass_kg"]) for k, v in budget.items() if k.startswith("V2PH-"))
    check_tol("V2 placeholder 9 行合计 == 新设备小计", v2ph_sum, eq_sum)

    check_tol("TOTAL-DESIGN-POINT", frz_sum, float(budget["TOTAL-DESIGN-POINT"]["mass_kg"]))
    check_tol(
        "TOTAL-DESIGN-POINT-READING-B",
        frz_sum + eq_sum + sec_sum,
        float(budget["TOTAL-DESIGN-POINT-READING-B"]["mass_kg"]),
    )
    cds_base = (
        eq["ST-STRUCT-REAL"]["mass_g"] / 1000.0
        + sec_sum
        + sum(eq[i]["mass_g"] for i in ["FRZ-B601", "FRZ-M3R", "FRZ-BRIDGE", "FRZ-SOLAR-L", "FRZ-SOLAR-R"]) / 1000.0
        + eq_sum
    )
    check_tol("TOTAL-CDS-VARIANT", cds_base, float(budget["TOTAL-CDS-VARIANT"]["mass_kg"]))
    check_tol("MARGIN-CDS-15PCT", 0.15 * cds_base, float(budget["MARGIN-CDS-15PCT"]["mass_kg"]))
    check_tol("TOTAL-CDS-VARIANT-MARGINED", 1.15 * cds_base, float(budget["TOTAL-CDS-VARIANT-MARGINED"]["mass_kg"]))

    # 3) V3 R2 调和: 冻结行逐值一致; 未解释项 = 0
    members = extract["members"]
    member_by_frz = {
        "FRZ-BUS": "bus_primary_structure",
        "FRZ-B601": "b601_complete_arm_including_gripper_urdf_links",
        "FRZ-M3R": "m3r_stage_a_plus_stage_b_budget_envelope",
        "FRZ-BRIDGE": "spacecraft_load_bridge_candidate",
        "FRZ-SOLAR-L": "solar_array_r2_left",
        "FRZ-SOLAR-R": "solar_array_r2_right",
    }
    recon_rows = []
    unexplained = 0
    for fid, mkey in member_by_frz.items():
        delta = eq[fid]["mass_g"] / 1000.0 - members[mkey]["mass_kg"]
        recon_rows.append({"line": fid, "delta_kg": delta, "explained": abs(delta) <= TOL_KG})
        if abs(delta) > TOL_KG:
            unexplained += 1
    check_tol("RECON-UNEXPLAINED-COUNT", float(unexplained), float(budget["RECON-UNEXPLAINED-COUNT"]["mass_kg"]))

    # 4) 场景合成
    agg = extract["aggregate"]
    ia = agg["inertia_about_system_cg_S_kg_m2"]
    i_c01 = [  # 惯量积约定见 extract inertia_convention_note
        [ia["Ixx"], -ia["Ixy"], -ia["Ixz"]],
        [-ia["Ixy"], ia["Iyy"], -ia["Iyz"]],
        [-ia["Ixz"], -ia["Iyz"], ia["Izz"]],
    ]
    frozen_body = Body("C01_AGGREGATE", agg["mass_kg"], agg["cg_S_m"], i_c01)

    def eq_body(item, name=None):
        return Body(
            name or item["id"],
            item["mass_g"] / 1000.0,
            pos_m(item),
            cuboid_own_inertia(item["mass_g"] / 1000.0, item["envelope_mm"]),
        )

    new_eq_bodies = [eq_body(eq[i]) for i in eq_ids]  # 含 EQ-SEC-STRUCT
    carve_mass = sum(b.m for b in new_eq_bodies)
    carve_body = Body("CARVE_LUMP_FROM_BUS", carve_mass, members["bus_primary_structure"]["cg_S_m"])

    # 配重旋钮: (id, x_min, x_max) 舱内边界 - 半包络
    def knob_bounds(item, bay):
        lo, hi = extract["bay_bounds_mm"][bay]
        half = item["envelope_mm"][0] / 2.0
        return lo + half, hi - half

    knobs = []
    for kid in ["EQ-BAT1", "EQ-BAT2", "EQ-PROP-MIPS", "EQ-RADIO", "EQ-GPS-RCVR", "EQ-MAG"]:
        bay = eq[kid]["bay"]
        lo, hi = knob_bounds(eq[kid], bay)
        knobs.append({"id": kid, "x_min": lo, "x_max": hi})

    def run_iteration(base_bodies_fn, label):
        """确定性 x 向配重迭代: 返回 (bodies, iteration_log)。"""
        bodies = base_bodies_fn({k["id"]: eq[k["id"]]["pos_mm"][0] for k in knobs})
        _, _, passed = cg_margins(combine(bodies)[1])
        log = {"performed": False, "reason": "initial layout passes", "moves": [], "result": "NOT_REQUIRED"}
        if passed:
            return bodies, log
        log["performed"] = True
        log["reason"] = "initial CG out of CDS envelope"
        cur_x = {k["id"]: eq[k["id"]]["pos_mm"][0] for k in knobs}
        _, cg0, _ = combine(bodies)
        cg0_mm, m0, _ = cg_margins(cg0)
        if m0["y"] < 0 or m0["z"] < 0:
            log["note_yz"] = "y/z 超差不受 x 旋钮影响 (治理约束: 仅允许 mid/rear 舱内 x 向调整), 记 NOT_ADDRESSABLE"
        # x 方向目标: cg_x 超上限 -> 旋钮向 x_min 移; 反之向 x_max
        for k in sorted(knobs, key=lambda t: -eq[t["id"]]["mass_g"]):
            while True:
                bodies = base_bodies_fn(cur_x)
                m_tot, cg, _ = combine(bodies)
                _, mm, ok = cg_margins(cg)
                if ok:
                    log["result"] = "CONVERGED"
                    return bodies, log
                if mm["x"] >= 0:
                    break  # x 已回包络但 y/z 不可调, 继续无益
                direction = -1.0 if cg[0] * 1000.0 > CDS_TOL_MM["x"] else 1.0
                start_x = cur_x[k["id"]]
                target = k["x_min"] if direction < 0 else k["x_max"]
                moved = False
                x = start_x
                while (direction < 0 and x > target) or (direction > 0 and x < target):
                    x += direction * 0.25
                    x = max(k["x_min"], min(k["x_max"], x))
                    moved = True
                    cur_x[k["id"]] = x
                    bodies = base_bodies_fn(cur_x)
                    _, cg2, _ = combine(bodies)
                    _, mm2, ok2 = cg_margins(cg2)
                    if ok2:
                        break
                if moved:
                    bodies = base_bodies_fn(cur_x)
                    m_tot2, cg3, _ = combine(bodies)
                    cg3_mm, mm3, _ = cg_margins(cg3)
                    log["moves"].append({
                        "knob": k["id"],
                        "x_start_mm": round(start_x, 3),
                        "x_end_mm": round(cur_x[k["id"]], 3),
                        "delta_mm": round(cur_x[k["id"]] - start_x, 3),
                        "cg_after_mm": [round(v, 3) for v in cg3_mm],
                        "margins_after_mm": {a: round(b, 3) for a, b in mm3.items()},
                    })
                    if mm3["x"] >= 0 and mm3["y"] >= 0 and mm3["z"] >= 0:
                        log["result"] = "CONVERGED"
                        return bodies, log
                break  # 该旋钮已到边界
        bodies = base_bodies_fn(cur_x)
        _, cgF, _ = combine(bodies)
        cgF_mm, mmF, _ = cg_margins(cgF)
        log["result"] = "INFEASIBLE_WITHIN_X_KNOBS"
        log["residual_cg_mm"] = [round(v, 3) for v in cgF_mm]
        log["residual_margins_mm"] = {a: round(b, 3) for a, b in mmF.items()}
        return bodies, log

    def bodies_scenario_a(x_overrides):
        out = [frozen_body, Body("CARVE_NEG", -carve_body.m, carve_body.cg)]
        for b in new_eq_bodies:
            if b.name in x_overrides:
                b = Body(b.name, b.m, [x_overrides[b.name] / 1000.0] + b.cg[1:], b.i_own)
            out.append(b)
        return out

    def bodies_scenario_b(x_overrides):
        out = [frozen_body]
        for b in new_eq_bodies:
            if b.name in x_overrides:
                b = Body(b.name, b.m, [x_overrides[b.name] / 1000.0] + b.cg[1:], b.i_own)
            out.append(b)
        return out

    def bodies_scenario_cds(x_overrides):
        out = [eq_body(eq["ST-STRUCT-REAL"])]
        for fid, mkey in member_by_frz.items():
            if fid == "FRZ-BUS":
                continue  # 包络 proxy 被真实结构替换
            out.append(Body(fid, members[mkey]["mass_kg"], members[mkey]["cg_S_m"]))
        for b in new_eq_bodies:
            if b.name in x_overrides:
                b = Body(b.name, b.m, [x_overrides[b.name] / 1000.0] + b.cg[1:], b.i_own)
            out.append(b)
        return out

    scenarios = {}
    for label, fn in [
        ("SCENARIO_A_CARVE_OUT_READING_A", bodies_scenario_a),
        ("SCENARIO_B_ADDITIVE_READING_B", bodies_scenario_b),
        ("SCENARIO_CDS_VARIANT_24KG", bodies_scenario_cds),
    ]:
        bodies, it_log = run_iteration(fn, label)
        m_tot, cg, i_cg = combine(bodies)
        cg_mm, margins, passed = cg_margins(cg)
        scenarios[label] = {
            "total_mass_kg": m_tot,
            "cg_S_mm": cg_mm,
            "cds_envelope_mm": CDS_TOL_MM,
            "margins_mm": margins,
            "cg_pass": passed,
            "inertia_about_cg_S_kg_m2": {
                "Ixx": i_cg[0][0], "Iyy": i_cg[1][1], "Izz": i_cg[2][2],
                "Ixy": -i_cg[0][1], "Ixz": -i_cg[0][2], "Iyz": -i_cg[1][2],
            },
            "iteration": it_log,
        }

    # 5) CDS 质量线检查
    cds_mass = {
        "base_kg": cds_base,
        "margin_15pct_kg": 0.15 * cds_base,
        "margined_kg": 1.15 * cds_base,
        "limit_kg": 24.0,
        "pass": 1.15 * cds_base <= 24.0,
        "rule": "B1 R2 (CDS Table 1 + VMMO 15% margin)",
    }

    out = {
        "title": "F4R1 C1 CG/惯量/质量机器核算输出 V1",
        "generated_at": "2026-08-27",
        "status": "DESIGN_RESEARCH_CANDIDATE",
        "method": "见脚本头注释: 设备=均质长方体; 冻结 C01=单一刚体(场景A/B); 场景A切出块=质点近似; CDS_VARIANT 冻结成员=质点近似; 惯量输出信息性, CG 为 CDS 判据",
        "input_files": {
            "equipment_list": {"path": "EQUIPMENT_LIST_V1.yaml", "sha256_12": sha256_12(EQUIPMENT_YAML)},
            "mass_budget": {"path": "MASS_BUDGET_V1.csv", "sha256_12": sha256_12(BUDGET_CSV)},
            "frozen_extract": {"path": "FROZEN_MASS_EXTRACT_C01.json", "sha256_12": sha256_12(EXTRACT_JSON)},
        },
        "frozen_source_integrity": source_integrity,
        "mass_budget_check": mass_check,
        "v3_r2_reconciliation": {"rows": recon_rows, "unexplained_count": unexplained},
        "m1_finding": {
            "question": "31.0229 kg 是否已含内部设备?",
            "evidence": [
                "V3 R2 C01 行项目 = bus 23.3032134 + B601 4.6955559 + M3R 0.7619 + bridge 0.7021955 + solar 2x0.78, 无任何设备行 (REPO_ASSET_INVENTORY F2)",
                "bus 23.3032134 provenance = servicer_12U_v0 24kg 整星块模型减 2 帆板 (service_spacecraft_v1.yaml), 即 24kg 整星口径的拆分余额, 物理上隐含整星全部内容(含设备)",
                "02_PRODUCT_STRUCTURE.yaml 自述 bus 为 solid envelope proxy: no internal structure, no bays",
            ],
            "reading_A_implicit_inclusion": "主读法: 31.0229 kg 的 bus 包络块是 24 kg 整星口径拆分余额, 内部设备隐含于块内; 新增设备行是对块内质量的分摊说明, 不作加法 -> TOTAL_DESIGN_POINT = 31.0229 kg (ODR 主口径, ESPA 级登记)",
            "reading_B_additive": "次读法(上限): C01 行项目层面无设备行, 若把 bus 块当作纯结构则设备须另加 -> 36.6599 kg (声明上界, 不登记)",
            "decomposition_status": "UNKNOWN: 现有证据无法把 23.303 kg 块分解为结构/设备份额 (V2-UNK-007/008, GAP-MA-02 as-built 计量 HOLD); 双读法并列登记, 禁止猜测",
        },
        "basis_caveat": extract["basis_caveat"],
        "scenarios": scenarios,
        "cds_variant_mass_check": cds_mass,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print("== F4R1 C1 checks ==")
    print("mass_budget_check:", mass_check["result"])
    print("recon unexplained:", unexplained)
    for label, s in scenarios.items():
        print(
            "%s: mass=%.6f kg, CG_mm=[%.2f, %.2f, %.2f], margins_mm=[%.2f, %.2f, %.2f], cg_pass=%s, iter=%s"
            % (
                label,
                s["total_mass_kg"],
                s["cg_S_mm"][0],
                s["cg_S_mm"][1],
                s["cg_S_mm"][2],
                s["margins_mm"]["x"],
                s["margins_mm"]["y"],
                s["margins_mm"]["z"],
                s["cg_pass"],
                s["iteration"]["result"],
            )
        )
    print("CDS variant mass: %.6f kg (margined, limit 24.0) pass=%s" % (cds_mass["margined_kg"], cds_mass["pass"]))
    print("written:", OUT_JSON)
    if mass_check["result"] != "pass" or unexplained != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
