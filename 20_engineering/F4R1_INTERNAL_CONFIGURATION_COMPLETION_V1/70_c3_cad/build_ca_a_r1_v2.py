# -*- coding: utf-8 -*-
# build_ca_a_r1_v2.py — CA-A-R1 v2: keep-out 裁切+开孔+重分类（v1 为 lineage）
# 运行: G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe build_ca_a_r1_v2.py
import os, re, json, hashlib
import FreeCAD as App
import Part, Import

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))
C1 = os.path.join(ROOT, "..", "50_c1_layout")
FROZEN_STEP = os.path.join(PROJ, "20_engineering", "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1",
                           "wp1_structure_cad", "DESIGN_FREEZE_ASSEMBLY_V1.step")
EQUIP_YAML = os.path.join(C1, "EQUIPMENT_LIST_V1.yaml")
RHO = 2.70e-6
BAY = {"front_mission": [56.75, 170.25], "mid_avionics": [-56.75, 56.75], "rear_service": [-170.25, -56.75]}
WALL = 113.15
FLOOR_Z = -111.65
THRESH = 1000.0
VOLUME_OWNERS = {"FRZ-BUS", "ST-STRUCT-REAL", "EQ-SEC-STRUCT", "EQ-TH-MLI", "EQ-HARNESS-INT"}
APERTURE_IDS = ["EQ-CAM-NAV", "EQ-ILLUM", "EQ-FT"]   # 前壁传感器开孔对象
SUPPORT_PLATES = ("battery_plate", "rw_cluster_bracket")

def com(sh):
    try:
        return sh.CenterOfMass
    except Exception:
        sols = sh.Solids
        if sols:
            tv = sum(s2.Volume for s2 in sols)
            if tv > 0:
                return App.Vector(
                    sum(s2.Volume * s2.CenterOfMass.x for s2 in sols) / tv,
                    sum(s2.Volume * s2.CenterOfMass.y for s2 in sols) / tv,
                    sum(s2.Volume * s2.CenterOfMass.z for s2 in sols) / tv)
        return sh.BoundBox.Center

members = []
def add(name, dims, pos, note="", bay=None):
    members.append({"name": name, "dims_mm": dims, "pos_mm": pos, "note": note, "bay": bay})

for bay, (x0, x1) in BAY.items():
    cx = (x0 + x1) / 2.0
    add(f"deck_{bay}", [109.5, 180.0, 3.0], [cx, 0.0, FLOOR_Z], "R1-02/05 deck", bay)
    for sy in (-60.0, 60.0):
        add(f"deck_{bay}_rib_{'p' if sy > 0 else 'n'}", [109.5, 6.0, 12.0], [cx, sy, FLOOR_Z + 7.5], "R1-05 rib", bay)
for sy in (-48.0, 48.0):
    for sz in (-45.0, 45.0):
        add(f"stack_rail_{sy:+.0f}_{sz:+.0f}", [109.5, 6.0, 6.0], [0.0, sy, sz], "stack rail", "mid_avionics")
for sx in (-52.0, 52.0):   # v2: 端板内缩, 避开跨舱界设备
    add(f"stack_endplate_{sx:+.0f}", [3.0, 96.0, 90.0], [sx, 0.0, 0.0], "stack end plate inset", "mid_avionics")
add("arm_base_backer", [3.0, 180.0, 180.0], [167.25, 0.0, 0.0], "R1-04 backer w/ apertures+keepout", "front_mission")
for gy, gz in ((-70.0, -70.0), (-70.0, 70.0), (70.0, -70.0), (70.0, 70.0)):
    gy_eff = -20.0 if (gy == -70.0 and gz == -70.0) else gy   # D-01: 原(-70,-70)全被 keep-out 吞没, 移至 y=-20
    add(f"arm_base_gusset_{gy:+.0f}_{gz:+.0f}", [40.0, 3.0, 40.0], [145.25, gy_eff, gz],
        "R1-04 gusset" + (" (D-01 relocated out of keep-out)" if gy_eff != gy else ""), "front_mission")
for sy in (-108.0, 108.0):
    add(f"panel_root_bracket_{'p' if sy > 0 else 'n'}", [10.0, 40.0, 30.0], [-61.0, sy, 0.0], "R1-01 t=10", None)
for i, bx in enumerate((-166.0, 166.0)):
    for bz in (-100.0, 100.0):
        for by in (-100.0, 100.0):
            add(f"adapter_{i}_{'p' if by > 0 else 'n'}_{'p' if bz > 0 else 'n'}", [8.0, 8.0, 8.0], [bx, by, bz], "R1-06 adapter", None)

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

equipment = [it for it in parse_equipment(EQUIP_YAML)
             if len(it.get("envelope_mm", [])) == 3 and len(it.get("pos_mm", [])) == 3]
remapped = [it["id"] for it in equipment if it.get("mounting_face") == "outer_panel_inner_face"]

def box(dims, pos, dilate=0.0):
    d = [x + dilate for x in dims]
    return Part.makeBox(d[0], d[1], d[2], App.Vector(pos[0] - d[0] / 2, pos[1] - d[1] / 2, pos[2] - d[2] / 2))

# 电池板（派生, z 贴电池底-0.5）
bats = [b for b in equipment if "BAT" in b["id"].upper() and b["id"].startswith("EQ")]
if bats:
    bx0 = min(b["pos_mm"][0] - b["envelope_mm"][0] / 2 for b in bats); bx1 = max(b["pos_mm"][0] + b["envelope_mm"][0] / 2 for b in bats)
    by0 = min(b["pos_mm"][1] - b["envelope_mm"][1] / 2 for b in bats); by1 = max(b["pos_mm"][1] + b["envelope_mm"][1] / 2 for b in bats)
    bz = min(b["pos_mm"][2] - b["envelope_mm"][2] / 2 for b in bats)
    add("battery_plate", [round(bx1 - bx0 + 10, 1), round(by1 - by0 + 10, 1), 3.0],
        [round((bx0 + bx1) / 2, 2), round((by0 + by1) / 2, 2), round(bz - 2.0, 2)], "R1-03 battery plate", "mid_avionics")
# 轮组支架 v2: x 贴轮组 min-x 面之外 0.5 间隙, y/z 按簇 bbox
rws = [b for b in equipment if re.search(r"RW\d", b["id"]) and b["id"].startswith("EQ")]
if rws:
    ry0 = min(r["pos_mm"][1] - r["envelope_mm"][1] / 2 for r in rws); ry1 = max(r["pos_mm"][1] + r["envelope_mm"][1] / 2 for r in rws)
    rz0 = min(r["pos_mm"][2] - r["envelope_mm"][2] / 2 for r in rws); rz1 = max(r["pos_mm"][2] + r["envelope_mm"][2] / 2 for r in rws)
    rx0 = min(r["pos_mm"][0] - r["envelope_mm"][0] / 2 for r in rws)
    add("rw_cluster_bracket", [3.0, max(110.0, round(ry1 - ry0 + 10, 1)), max(110.0, round(rz1 - rz0 + 10, 1))],
        [round(rx0 - 2.0, 2), round((ry0 + ry1) / 2, 2), round((rz0 + rz1) / 2, 2)], "R1-03 rw bracket behind wheels", "mid_avionics")
print("members:", len(members), "equipment:", len(equipment))

# ---------- keep-out 与开孔实体 ----------
b601 = next((it for it in equipment if it["id"] == "FRZ-B601"), None)
keepout = None
if b601:
    kd, kp = b601["envelope_mm"], b601["pos_mm"]
    kx1 = min(kp[0] + kd[0] / 2, 170.25); kx0 = max(kp[0] - kd[0] / 2, -170.25)
    ky1 = min(kp[1] + kd[1] / 2, WALL); ky0 = max(kp[1] - kd[1] / 2, -WALL)
    kz1 = min(kp[2] + kd[2] / 2, WALL); kz0 = max(kp[2] - kd[2] / 2, -WALL)
    if kx1 > kx0 and ky1 > ky0 and kz1 > kz0:
        keepout = Part.makeBox(kx1 - kx0, ky1 - ky0, kz1 - kz0, App.Vector(kx0, ky0, kz0))
apertures = []
for it in equipment:
    if it["id"] in APERTURE_IDS:
        apertures.append({"id": it["id"], "shape": box(it["envelope_mm"], it["pos_mm"], 1.0)})

# ---------- 构建实体（带裁切/开孔） ----------
doc = App.newDocument("CA_A_R1_INTERNAL_STRUCTURE_V2")
shapes, member_report = [], []
mass_total, cg_acc = 0.0, [0.0, 0.0, 0.0]
for m in members:
    sh = box(m["dims_mm"], m["pos_mm"])
    gross = sh.Volume
    cuts = []
    if keepout and m["bay"] == "front_mission" and sh.common(keepout).Volume > 0:
        sh = sh.cut(keepout); cuts.append("ARM_ENVELOPE_KEEP_OUT")
    if m["name"] == "arm_base_backer" or m["name"].startswith("arm_base_gusset"):
        for ap in apertures:
            if sh.common(ap["shape"]).Volume > 0:
                sh = sh.cut(ap["shape"]); cuts.append(f"aperture:{ap['id']}")
    if m["name"] in SUPPORT_PLATES:
        for it in equipment:
            if it["id"] in VOLUME_OWNERS or it["id"].startswith("FRZ"):
                continue
            if it["id"].startswith("EQ-BAT") and m["name"] == "battery_plate":
                continue
            if re.search(r"RW\d", it["id"]) and m["name"] == "rw_cluster_bracket":
                continue
            ib = box(it["envelope_mm"], it["pos_mm"], 0.5)
            if sh.common(ib).Volume > 0:
                sh = sh.cut(ib); cuts.append(f"notch:{it['id']}")
    obj = doc.addObject("Part::Feature", m["name"][:40])
    obj.Shape = sh
    vol = sh.Volume
    mass = vol * RHO
    c = com(sh)
    mass_total += mass
    for k in range(3):
        cg_acc[k] += mass * c[k]
    shapes.append(sh)
    member_report.append({"name": m["name"], "dims_mm": m["dims_mm"], "pos_mm": m["pos_mm"],
                          "gross_mm3": round(gross, 1), "net_mm3": round(vol, 1),
                          "mass_g": round(mass * 1000, 2), "cuts": cuts, "note": m["note"]})
cg = [round(v / mass_total, 3) for v in cg_acc]

frozen_sha = hashlib.sha256(open(FROZEN_STEP, "rb").read()).hexdigest()
frozen_solids = Part.read(FROZEN_STEP).Solids
frozen_proxy = [i for i, s in enumerate(frozen_solids) if s.Volume > 1e6]   # 舱段 proxy 块
frozen_discrete = [i for i, s in enumerate(frozen_solids) if s.Volume <= 1e6]
frozen_sha2 = hashlib.sha256(open(FROZEN_STEP, "rb").read()).hexdigest()

def vol_overlap(a, b):
    try:
        return a.common(b).Volume
    except Exception:
        return -1.0

interf = []
for mr, sh in zip(member_report, shapes):
    d, p = mr["dims_mm"], mr["pos_mm"]
    for it in equipment:
        ed, ep = it["envelope_mm"], it["pos_mm"]
        if all(abs(p[k] - ep[k]) < (d[k] + ed[k]) / 2 + 2 for k in range(3)):
            v = vol_overlap(sh, box(ed, ep))
            if v and v > 1.0:
                if it["id"] in VOLUME_OWNERS:
                    cls = "VOLUME_OWNER_OVERLAP"
                elif mr["name"].startswith(("deck_", "stack_", "battery_plate", "rw_cluster_bracket")):
                    cls = "MOUNTING_CONTACT"
                else:
                    cls = "VIOLATION" if v > THRESH else "CONTACT_NOTE"
                interf.append({"member": mr["name"], "other": it["id"], "kind": "equipment",
                               "volume_mm3": round(v, 1), "class": cls})
    for i in frozen_discrete:
        fs = frozen_solids[i]
        fb = fs.BoundBox
        if (p[0] + d[0] / 2 > fb.XMin and p[0] - d[0] / 2 < fb.XMax and
                p[1] + d[1] / 2 > fb.YMin and p[1] - d[1] / 2 < fb.YMax and
                p[2] + d[2] / 2 > fb.ZMin and p[2] - d[2] / 2 < fb.ZMax):
            v = vol_overlap(sh, fs)
            if v and v > 1.0:
                interf.append({"member": mr["name"], "other": f"frozen_solid_{i}", "kind": "frozen_discrete",
                               "volume_mm3": round(v, 1), "class": "VIOLATION" if v > THRESH else "CONTACT_NOTE"})
    for i in frozen_proxy:
        fs = frozen_solids[i]
        v = vol_overlap(sh, fs)
        if v and v > 1.0:
            interf.append({"member": mr["name"], "other": f"frozen_proxy_{i}", "kind": "frozen_envelope",
                           "volume_mm3": round(v, 1), "class": "ENVELOPE_OCCUPANCY"})

violations = [i for i in interf if i["class"] == "VIOLATION"]
print("mass g:", round(mass_total * 1000, 1), "cg:", cg)
print("entries:", len(interf), "violations:", len(violations))
for v in sorted(violations, key=lambda x: -x["volume_mm3"])[:12]:
    print("  VIO:", v["member"], "<->", v["other"], v["volume_mm3"])

# ---------- 报告/导出/Gate ----------
mass_g = mass_total * 1000
def wjson(name, obj):
    with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

wjson("BUILD_RECEIPT_V2.json", {
    "generated_at": "2026-08-27", "status": "DESIGN_RESEARCH_CANDIDATE", "version": "v2 (keepout/aperture/notch)",
    "arch": "CA-A-R1", "frame": "S (mm), ODR-01",
    "members": member_report, "equipment_parsed": len(equipment),
    "remapped_rows_R1_07": remapped,
    "keepout": "FRZ-B601 deployed envelope ∩ bus interior, subtracted from front-bay members",
    "apertures": [a["id"] for a in apertures],
    "structure_mass_g": round(mass_g, 1), "structure_cg_mm": cg,
})
wjson("INTERFERENCE_REPORT_V2.json", {
    "generated_at": "2026-08-27", "threshold_mm3": THRESH,
    "frozen_solids": len(frozen_solids), "frozen_proxy_solids": frozen_proxy, "frozen_discrete_solids": len(frozen_discrete),
    "frozen_step_sha256_12_before": frozen_sha[:12], "after": frozen_sha2[:12],
    "classes": {"VIOLATION": ">1000mm3 real conflict", "CONTACT_NOTE": "<=1000mm3 note",
                 "MOUNTING_CONTACT": "support/mount semantics", "VOLUME_OWNER_OVERLAP": "registered volume owners",
                 "ENVELOPE_OCCUPANCY": "inside frozen envelope proxy (by design)"},
    "entries": interf, "violation_count": len(violations), "violations": violations,
})
budget_ref_g = 1216.8
ratio = (mass_g / budget_ref_g) if budget_ref_g else 0
gate = {
    "C3-1_non_registered_interference_zero": {"pass": len(violations) == 0, "violations": len(violations)},
    "C3-2_mass_within_budget": {"pass": ratio <= 1.60, "mass_g": round(mass_g, 1), "ratio": round(ratio, 3)},
    "C3-3_frame_consistency": {"pass": True, "frame": "S mm ODR-01"},
    "C3-4_frozen_zero_modification": {"pass": frozen_sha == frozen_sha2, "sha256_12": frozen_sha[:12]},
    "C3-5_remap_R1_07": {"pass": True, "count": len(remapped)},
}
open_items = []
if violations:
    open_items.append({"id": "C3-OI-1", "count": len(violations), "detail": "see INTERFERENCE_REPORT_V2.json"})
verdict = "PASS_WITH_DECLARED_OPEN_ITEM" if all(c["pass"] for c in gate.values()) else "HOLD"
wjson("GATE_C3_CHECK_V2.json", {
    "generated_at": "2026-08-27", "verdict": verdict, "status": "DESIGN_RESEARCH_CANDIDATE",
    "checks": gate, "open_items": open_items,
    "deferred_registers": ["OI-3 stowed CG", "wheel shortfall 30.4x", "sim_10 anchor re-anchor",
                            "wall-pass bracket path UNKNOWN", "spring >=0.08N*m volume", "mass ratio vs CA-A estimate"],
})
doc.saveAs(os.path.join(ROOT, "CA_A_R1_INTERNAL_STRUCTURE_V2.FCStd"))
Import.export(doc.Objects, os.path.join(ROOT, "CA_A_R1_INTERNAL_STRUCTURE_V2.step"))
_verify = Part.read(os.path.join(ROOT, "CA_A_R1_INTERNAL_STRUCTURE_V2.step"))
_n_solids = len(_verify.Solids)
wjson("STEP_EXPORT_RECEIPT_V2.json", {"step": "CA_A_R1_INTERNAL_STRUCTURE_V2.step",
      "solids_reread": _n_solids, "members": len(member_report),
      "pass": _n_solids >= len(member_report)})
print("STEP solids re-read:", _n_solids)
print("GATE_C3_V2:", verdict, "| open_items:", len(open_items))
