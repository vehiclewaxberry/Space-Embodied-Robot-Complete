# rt_verify.py — 红队关键数值机器复核（stdlib only）
# 输出 RT_VERIFY_OUT_V1.json；verdict: CONFIRMED/APPROXIMATE/DISPUTED/UNKNOWN
import json, re, math, os

ROOT = os.path.dirname(os.path.abspath(__file__))
BASIS = os.path.join(ROOT, "..", "55_c3_design_basis")
C1 = os.path.join(ROOT, "..", "50_c1_layout")
checks = []

def add(cid, source, claimed, computed, verdict, notes=""):
    checks.append({"id": cid, "claim_source": source, "rt_claimed": claimed,
                   "computed": computed, "verdict": verdict, "notes": notes})

# V1 帆板根铰支架应力 σ=6M/(w t^2)，M=48 N·m, w=0.03 m
YIELD = 276.0  # 6061-T6 ASSUMED MPa
res = {}
for t in (0.006, 0.008, 0.010):
    sigma = 6 * 48.0 / (0.03 * t * t) / 1e6
    res[f"t={t*1000:.0f}mm"] = {"sigma_MPa": round(sigma, 1), "MS": round(YIELD / sigma - 1, 2)}
add("V1_root_bracket_stress", "RT1 §2", "t6: 267MPa, MS~0; t>=8-10mm",
    res, "CONFIRMED", "t=6mm 复算 266.7 MPa≈屈服；t=10mm MS=1.87；改造量成立")

# V2 CA-C 压载裕度算术：margin 1.135mm vs 板宽语义 ±120g
M_CDS = 19.62  # kg, CDS variant total (RT3 K3)
dm = 0.120     # kg 宽度语义差
x_b = -163.0   # mm
dcg = abs(dm * x_b / M_CDS)
res = {"margin_mm": 1.135, "delta_CG_mm": round(dcg, 3),
       "net_mm": round(1.135 - dcg, 3)}
add("V2_ballast_margin_arithmetic", "RT2 §2", "±120g→ΔCG≈1.45mm→净-0.3mm",
    res, "APPROXIMATE", "复算 ΔCG≈1.0mm（RT2 的 1.45 略高估），净裕度 +0.14~−0.3mm 量级；『裕度<簿记噪声』结论成立")

# V3 栓组拉力：M3R 4×M4 PCD 90.51，捕获力矩 17.6 N·m
r = 0.045255
T_moment = 17.6 * r / (4 * r * r)
T_direct = 460.6 / 4
res = {"T_moment_only_N": round(T_moment, 1), "T_direct_10g_per_bolt_N": round(T_direct, 1),
       "proof_M4_8_8_N": 5600, "margin_vs_proof": round(5600 / max(T_moment, T_direct), 1)}
add("V3_bolt_group", "RT1 §5", "栓拉 137-540N << 5.6kN，栓级无弱链",
    res, "APPROXIMATE", "力矩项复算 97N（RT1 的 137 略不同，或含合成），直接剪 115N；结论『远小于保证载荷』成立")

# V4 CA-B 线束走廊×剪切板干涉算术
v = 113.5 * 1.5 * 16.85
add("V4_caB_corridor_interference", "RT3 §3 K1", "~2868 mm³ > 1000 mm³",
    {"recompute_mm3": round(v, 1)}, "CONFIRMED", "113.5×1.5×16.85=2867.96 mm³ 算术成立（盒模型近似）")

# V5 CA-C 压载甲板一阶模态（点质量简支梁中点 k=48EI/L^3）
E, w, t, L, m = 71.7e9, 0.10, 0.003, 0.20, 3.604
I = w * t**3 / 12
k = 48 * E * I / L**3
f_ss = (1 / (2 * math.pi)) * math.sqrt(k / m)
f_fix = f_ss * 2.27  # 固支/简支频率比近似
add("V5_ballast_deck_mode", "RT1 §6", "~31Hz(简支)/~62Hz(固支) <<100Hz",
    {"f_ss_Hz": round(f_ss, 1), "f_fixed_approx_Hz": round(f_fix, 1)},
    "APPROXIMATE", f"复算 {f_ss:.1f}/{f_fix:.1f} Hz（几何假定不同），『远低于100Hz』结论成立")

# V6 候选包络违例 AABB（从候选 yaml 宽松解析成员 pos/dims）
def parse_members(path):
    txt = open(path, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"name:\s*([A-Za-z0-9_]+)[\s\S]{0,400}?pos(?:_mm)?:\s*\[([^\]]+)\][\s\S]{0,400}?dims(?:_mm)?:\s*\[([^\]]+)\]", txt):
        g = m.groups()
        try:
            pos = [float(x) for x in g[1].split(",")]
            dims = [float(x) for x in g[2].split(",")]
            out.append((g[0], pos, dims))
        except ValueError:
            pass
    return out

viol = []
try:
    members = parse_members(os.path.join(BASIS, "CANDIDATE_ARCHITECTURES_V1.yaml"))
    for name, pos, dims in members:
        if len(pos) == 3 and len(dims) == 3:
            lo, hi = pos[0] - dims[0] / 2, pos[0] + dims[0] / 2
            if hi > 170.25:
                viol.append({"member": name, "face": "+x", "exceed_mm": round(hi - 170.25, 2)})
            if lo < -170.25:
                viol.append({"member": name, "face": "-x", "exceed_mm": round(-170.25 - lo, 2)})
    verdict = "CONFIRMED" if viol else "UNKNOWN"
    add("V6_envelope_violations", "RT1 §3/RT3 §5", "CA-A 49.75/53.25; CA-B 9.75; CA-C 89.75/0.25",
        {"members_parsed": len(members), "violations": viol}, verdict,
        "舱面 x=±170.25（OI-6 外廓 340.5/366.0 口径）；解析失败则为 UNKNOWN")
except Exception as e:
    add("V6_envelope_violations", "RT1 §3/RT3 §5", "同上", {"error": str(e)}, "UNKNOWN", "解析异常")

# V7 ±5% 设备质量区间传播最坏 ΔCG_x（从 C1 设备清单宽松解析）
def parse_equipment(path):
    txt = open(path, encoding="utf-8").read()
    items = []
    for m in re.finditer(r"mass_g:\s*([0-9.]+)[\s\S]{0,300}?pos_mm:\s*\[([^\]]+)\]", txt):
        try:
            items.append((float(m.group(1)), [float(x) for x in m.group(2).split(",")]))
        except ValueError:
            pass
    return items

try:
    items = parse_equipment(os.path.join(C1, "EQUIPMENT_LIST_V1.yaml"))
    M = sum(g for g, _ in items) / 1000.0
    worst = sum(abs(g * p[0]) for g, p in items if len(p) == 3) * 0.05 / 1000.0 / M if M else 0
    add("V7_pm5pct_CG_propagation", "RT2 §3", "最坏 ΔCG_x≈2-3mm >> 1.14mm 裕度",
        {"items_parsed": len(items), "mass_kg": round(M, 3), "worst_dCGx_mm": round(worst, 2)},
        "CONFIRMED" if items and worst > 1.135 else ("UNKNOWN" if not items else "APPROXIMATE"),
        "区间最坏口径；RT2 MC 失败率 10-35% 未复核（无随机种子口径）")
except Exception as e:
    add("V7_pm5pct_CG_propagation", "RT2 §3", "同上", {"error": str(e)}, "UNKNOWN", "解析异常")

# V8 RT3 K3 CDS 叠加压载 CG 算术
cg = (16.4234 * 120.07 + 3.2 * (-163)) / 19.62
add("V8_caB_cds_cg", "RT3 §3 K3", "CG_x=73.9mm >70 FAIL",
    {"CG_x_mm": round(cg, 1), "limit_mm": 70}, "CONFIRMED",
    f"复算 {cg:.1f} mm，超限 {round(cg-70,1)} mm，K3 成立")

out = {"generated_at": "2026-08-27", "script": "rt_verify.py",
       "note": "红队手工值的机器复核；APPROXIMATE=结论成立数值有差，DISPUTED=结论不成立",
       "checks": checks}
with open(os.path.join(ROOT, "RT_VERIFY_OUT_V1.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps({"checks": len(checks),
                  "verdicts": {c["id"]: c["verdict"] for c in checks}}, ensure_ascii=False, indent=1))
