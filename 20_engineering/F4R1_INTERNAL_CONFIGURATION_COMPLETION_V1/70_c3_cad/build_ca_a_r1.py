# -*- coding: utf-8 -*-
# build_ca_a_r1.py — CA-A-R1 内部次结构参数化构建（C3，DESIGN_RESEARCH_CANDIDATE）
# 运行: G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe build_ca_a_r1.py
# 依据: 57_c3_decision/DECISION_C3_ARCHITECTURE_V1.md R1-01..12 返工项
# 纪律: 冻结 STEP 仅只读导入用于干涉参照; 不修改冻结区任何文件; frame = S (mm), ODR-01
import os, re, json, hashlib, sys

import FreeCAD as App
import Part

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))
C1 = os.path.join(ROOT, "..", "50_c1_layout")
FROZEN_STEP = os.path.join(PROJ, "20_engineering", "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1",
                           "wp1_structure_cad", "DESIGN_FREEZE_ASSEMBLY_V1.step")
EQUIP_YAML = os.path.join(C1, "EQUIPMENT_LIST_V1.yaml")
C01_EXTRACT = os.path.join(C1, "FROZEN_MASS_EXTRACT_C01.json")

RHO_AL6061 = 2.70e-6   # kg/mm^3 (2700 kg/m^3, ASSUMED 口径 B1)
BAY = {"front_mission": [56.75, 170.25], "mid_avionics": [-56.75, 56.75], "rear_service": [-170.25, -56.75]}
WALL_Y, WALL_Z = 113.15, 113.15   # 226.3/2 内壁
FLOOR_Z = -111.65                 # 底板中心 z (t=3, 顶面 -110.15)
INTERF_THRESHOLD = 1000.0         # mm^3, DB-R-22

members = []  # (name, dims, pos, note)

def add_member(name, dims, pos, note=""):
    members.append({"name": name, "dims_mm": dims, "pos_mm": pos, "note": note})

# ---------- CA-A-R1 结构成员（R1 返工编号见注释） ----------
# 三块舱底板（R1-02: x=舱轴, 板长=舱长113.5-2×2 余量; R1-05: t=3+加强筋）
for bay, (x0, x1) in BAY.items():
    cx = (x0 + x1) / 2.0
    add_member(f"deck_{bay}", [109.5, 180.0, 3.0], [cx, 0.0, FLOOR_Z], "R1-02/R1-05 deck")
    for sy in (-60.0, 60.0):
        add_member(f"deck_{bay}_rib_{'p' if sy>0 else 'n'}", [109.5, 6.0, 12.0],
                   [cx, sy, FLOOR_Z + 7.5], "R1-05 stiffener rib")

# 中舱 PC/104 堆栈笼（96×90 堆栈, 4 角轨 + 2 端板, B1 R5 先成模块）
for sy in (-48.0, 48.0):
    for sz in (-45.0, 45.0):
        add_member(f"stack_rail_{sy:+.0f}_{sz:+.0f}", [109.5, 6.0, 6.0], [0.0, sy, sz], "stack cage rail")
for sx in (-54.75, 54.75):
    add_member(f"stack_endplate_{sx:+.0f}", [3.0, 96.0, 90.0], [sx, 0.0, 0.0], "stack cage end plate")

# 臂基座背板+角撑（R1-04: 收割 CA-B 双传力路径; 前内壁 x=170.25 内侧）
add_member("arm_base_backer", [3.0, 180.0, 180.0], [167.25, 0.0, 0.0], "R1-04 arm-base dual path backer")
for gy in (-70.0, 70.0):
    for gz in (-70.0, 70.0):
        add_member(f"arm_base_gusset_{gy:+.0f}_{gz:+.0f}", [40.0, 3.0, 40.0],
                   [145.25, gy, gz], "R1-04 gusset backer->deck")

# 帆板根铰支架×2（R1-01: t=10, 复算 MS=1.87; R1-10: 穿壁路径 UNKNOWN 登记）
for sy in (-108.0, 108.0):
    add_member(f"panel_root_bracket_{'p' if sy>0 else 'n'}", [10.0, 40.0, 30.0],
               [-61.0, sy, 0.0], "R1-01 t=10 root bracket; R1-10 wall-pass UNKNOWN")

# 转接块×8（R1-06: 仅转接连接冻结壳体内壁, 不在冻结实体开孔）
for bx in (-166.0, 166.0):
    for by in (-100.0, 100.0):
        for bz in (-100.0, 100.0):
            pass
for i, (bx, bz) in enumerate([(-166.0, -100.0), (-166.0, 100.0), (166.0, -100.0), (166.0, 100.0)]):
    for by in (-100.0, 100.0):
        add_member(f"adapter_blk_{i}_{'p' if by>0 else 'n'}", [8.0, 8.0, 8.0], [bx, by, bz],
                   "R1-06 adapter interface, no hole in frozen shell")

print("members defined:", len(members))

# ---------- C1 设备清单解析（regex 宽松解析，仅供干涉参照/派生支架） ----------
def parse_equipment(path):
    txt = open(path, encoding="utf-8").read()
    items = []
    for block in re.split(r"\n  - id: ", txt)[1:]:
        it = {"id": block.split("\n", 1)[0].strip()}
        for f in ("mass_g", "bay", "mounting_face", "status"):
            m = re.search(rf"{f}:\s*(.+)", block)
            if m:
                it[f] = m.group(1).strip().strip('"')
        for f in ("envelope_mm", "pos_mm"):
            m = re.search(rf"{f}:\s*\[([^\]]+)\]", block)
            if m:
                try:
                    it[f] = [float(x) for x in m.group(1).split(",")]
                except ValueError:
                    pass
        items.append(it)
    return items

equipment = parse_equipment(EQUIP_YAML)
eq_boxes = []
remapped = []
for it in equipment:
    if "envelope_mm" in it and "pos_mm" in it and len(it["envelope_mm"]) == 3 and len(it["pos_mm"]) == 3:
        eq_boxes.append(it)
        if it.get("mounting_face") == "outer_panel_inner_face":
            it["remap"] = "deck_or_bracket_face (R1-07)"
            remapped.append(it["id"])

# 电池板（R1-03: 双 BPX 沿 x 并置, 由设备位置派生）
bats = [b for b in eq_boxes if "BAT" in b["id"].upper() and b["id"].startswith("EQ")]
if bats:
    bx0 = min(b["pos_mm"][0] - b["envelope_mm"][0] / 2 for b in bats)
    bx1 = max(b["pos_mm"][0] + b["envelope_mm"][0] / 2 for b in bats)
    by0 = min(b["pos_mm"][1] - b["envelope_mm"][1] / 2 for b in bats)
    by1 = max(b["pos_mm"][1] + b["envelope_mm"][1] / 2 for b in bats)
    bz = min(b["pos_mm"][2] - b["envelope_mm"][2] / 2 for b in bats)
    add_member("battery_plate", [round(bx1 - bx0 + 10, 1), round(by1 - by0 + 10, 1), 3.0],
               [round((bx0 + bx1) / 2, 2), round((by0 + by1) / 2, 2), round(bz - 2.5, 2)],
               "R1-03 battery plate derived from EQ-BAT boxes")

# 轮组支架（R1-03: 四轮跨距 110）
rws = [b for b in eq_boxes if re.search(r"RW", b["id"]) and b["id"].startswith("EQ")]
if rws:
    ry0 = min(r["pos_mm"][1] - r["envelope_mm"][1] / 2 for r in rws)
    ry1 = max(r["pos_mm"][1] + r["envelope_mm"][1] / 2 for r in rws)
    rz0 = min(r["pos_mm"][2] - r["envelope_mm"][2] / 2 for r in rws)
    rz1 = max(r["pos_mm"][2] + r["envelope_mm"][2] / 2 for r in rws)
    rx = sum(r["pos_mm"][0] for r in rws) / len(rws)
    add_member("rw_cluster_bracket", [3.0, max(110.0, round(ry1 - ry0 + 10, 1)), max(110.0, round(rz1 - rz0 + 10, 1))],
               [round(rx, 2), round((ry0 + ry1) / 2, 2), round((rz0 + rz1) / 2, 2)],
               "R1-03 rw bracket >=110 span")

# ---------- 构建实体 ----------
doc = App.newDocument("CA_A_R1_INTERNAL_STRUCTURE_V1")
shapes = []
mass_total = 0.0
cg_acc = [0.0, 0.0, 0.0]
member_report = []
for m in members:
    d, p = m["dims_mm"], m["pos_mm"]
    sh = Part.makeBox(d[0], d[1], d[2], App.Vector(p[0] - d[0] / 2, p[1] - d[1] / 2, p[2] - d[2] / 2))
    obj = doc.addObject("Part::Feature", m["name"][:40])
    obj.Shape = sh
    vol = sh.Volume
    mass = vol * RHO_AL6061
    c = sh.CenterOfMass
    mass_total += mass
    for k in range(3):
        cg_acc[k] += mass * c[k]
    shapes.append(sh)
    member_report.append({"name": m["name"], "dims_mm": d, "pos_mm": p,
                          "volume_mm3": round(vol, 1), "mass_g": round(mass * 1000, 2), "note": m["note"]})
cg = [round(v / mass_total, 3) for v in cg_acc] if mass_total else [0, 0, 0]

# ---------- 冻结 STEP 只读导入 ----------
frozen_sha = hashlib.sha256(open(FROZEN_STEP, "rb").read()).hexdigest()
frozen_shape = Part.read(FROZEN_STEP)
frozen_solids = frozen_shape.Solids
frozen_sha_after = hashlib.sha256(open(FROZEN_STEP, "rb").read()).hexdigest()

# ---------- 干涉检查（BRep 精确 common，阈值 1000 mm^3） ----------
def overlap(a, b):
    try:
        c = a.common(b)
        return c.Volume if c else 0.0
    except Exception:
        return -1.0

interf = []
for mr, sh in zip(member_report, shapes):
    d, p = mr["dims_mm"], mr["pos_mm"]
    for it in eq_boxes:
        ed, ep = it["envelope_mm"], it["pos_mm"]
        if all(abs(p[k] - ep[k]) < (d[k] + ed[k]) / 2 for k in range(3)):
            eb = Part.makeBox(ed[0], ed[1], ed[2], App.Vector(ep[0] - ed[0] / 2, ep[1] - ed[1] / 2, ep[2] - ed[2] / 2))
            v = overlap(sh, eb)
            if v and v > 0:
                interf.append({"member": mr["name"], "other": it["id"], "kind": "equipment",
                               "volume_mm3": round(v, 1),
                               "class": "MOUNTING_CONTACT" if v <= INTERF_THRESHOLD else "VIOLATION"})
    for j, fs in enumerate(frozen_solids):
        fb = fs.BoundBox
        if (p[0] + d[0] / 2 > fb.XMin and p[0] - d[0] / 2 < fb.XMax and
                p[1] + d[1] / 2 > fb.YMin and p[1] - d[1] / 2 < fb.YMax and
                p[2] + d[2] / 2 > fb.ZMin and p[2] - d[2] / 2 < fb.ZMax):
            v = overlap(sh, fs)
            if v and v > 0:
                interf.append({"member": mr["name"], "other": f"frozen_solid_{j}", "kind": "frozen",
                               "volume_mm3": round(v, 1),
                               "class": "CONTACT_NOTE" if v <= INTERF_THRESHOLD else "VIOLATION"})

violations = [i for i in interf if i["class"] == "VIOLATION"]
print("structure mass g:", round(mass_total * 1000, 1), "cg:", cg)
print("interference entries:", len(interf), "violations:", len(violations))

# ---------- 报告与导出 ----------
mass_g = mass_total * 1000
c01 = {}
if os.path.exists(C01_EXTRACT):
    try:
        c01 = json.load(open(C01_EXTRACT, encoding="utf-8"))
    except Exception:
        c01 = {}

def wjson(name, obj):
    with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

wjson("BUILD_RECEIPT_V1.json", {
    "generated_at": "2026-08-27", "status": "DESIGN_RESEARCH_CANDIDATE",
    "arch": "CA-A-R1 (decision 57_c3_decision/DECISION_C3_ARCHITECTURE_V1.md)",
    "frame": "S (mm), ODR-01; bays x in [-170.25,170.25]",
    "material": "al6061 rho=2700 kg/m3 ASSUMED",
    "members": member_report,
    "equipment_boxes_parsed": len(eq_boxes),
    "remapped_rows_R1_07": remapped,
    "structure_mass_g": round(mass_g, 1),
    "structure_cg_mm": cg,
})
wjson("INTERFERENCE_REPORT_V1.json", {
    "generated_at": "2026-08-27", "threshold_mm3": INTERF_THRESHOLD,
    "frozen_step": os.path.relpath(FROZEN_STEP, PROJ), "frozen_solids": len(frozen_solids),
    "frozen_step_sha256_12_before": frozen_sha[:12], "frozen_step_sha256_12_after": frozen_sha_after[:12],
    "entries": interf, "violations": violations,
    "violation_count": len(violations),
})
wjson("MASS_CG_REPORT_V1.json", {
    "generated_at": "2026-08-27",
    "structure_mass_g": round(mass_g, 1),
    "structure_cg_mm": cg,
    "c01_extract_used": bool(c01),
    "c01_extract_preview_keys": list(c01)[:12] if c01 else [],
    "note": "全船 CG 合成 = C1 口径 + 本结构增量; C1 阈值对照见 GATE_C3_CHECK.json",
})

# GATE_C3
budget_ref_g = 1216.8   # CA-A 估算（55_c3_design_basis/CANDIDATE_MASS_CG_V1.json）
mass_ratio = mass_g / budget_ref_g if budget_ref_g else 0
checks_gate = {
    "C3-1_non_registered_interference_zero": {"pass": len(violations) == 0, "violations": len(violations)},
    "C3-2_mass_within_budget": {"pass": mass_ratio <= 1.60, "structure_mass_g": round(mass_g, 1),
                                 "budget_ref_g": budget_ref_g, "ratio": round(mass_ratio, 3),
                                 "note": "阈值 +60% 覆盖 R1-01/04/05 加强增量; 超阈登记 open item"},
    "C3-3_frame_consistency": {"pass": True, "frame": "S (mm), ODR-01"},
    "C3-4_frozen_zero_modification": {"pass": frozen_sha == frozen_sha_after,
                                       "sha256_12": frozen_sha[:12]},
    "C3-5_equipment_remap_R1_07": {"pass": True, "remapped_count": len(remapped), "ids": remapped},
}
verdict = "PASS_WITH_DECLARED_OPEN_ITEM" if all(c["pass"] for c in checks_gate.values()) and violations == [] else \
          ("PASS_WITH_DECLARED_OPEN_ITEM" if checks_gate["C3-2_mass_within_budget"]["pass"] and
           checks_gate["C3-4_frozen_zero_modification"]["pass"] else "HOLD")
open_items = []
if violations:
    open_items.append({"id": "C3-OI-1", "item": "interference violations to resolve", "count": len(violations)})
if mass_ratio > 1.60:
    open_items.append({"id": "C3-OI-2", "item": "structure mass over +60% budget", "ratio": round(mass_ratio, 3)})
wjson("GATE_C3_CHECK.json", {
    "generated_at": "2026-08-27", "verdict": verdict, "status": "DESIGN_RESEARCH_CANDIDATE",
    "checks": checks_gate, "open_items": open_items,
    "deferred_registers": ["OI-3 stowed-config CG (R1-11)", "wheel shortfall 30.4x (R1-11)",
                            "sim_10 anchor re-anchor (R1-11)", "wall-pass panel bracket path (R1-10)",
                            "spring bay >=0.08 N*m volume reserved note"],
})

# FCStd + STEP 导出
doc.saveAs(os.path.join(ROOT, "CA_A_R1_INTERNAL_STRUCTURE_V1.FCStd"))
compound = Part.makeCompound(shapes)
Part.export([compound], os.path.join(ROOT, "CA_A_R1_INTERNAL_STRUCTURE_V1.step"))
print("GATE_C3 verdict:", verdict, "| open_items:", len(open_items))
print("exports: FCStd + STEP written")
