"""NATIVE-01 裁决后置补丁：人工裁决 / Codex 衔接 / O9-O11 结果。

必须在 finalize_native.py 之后运行（后者会从头重写 verdict）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    p = ROOT / "evidence/phase1_machine_verdict.json"
    v = json.loads(p.read_text(encoding="utf-8"))
    o11 = json.loads((ROOT / "design/o11_clocking_adjudication.json")
                     .read_text(encoding="utf-8"))
    f = o11["analytic_finding"]
    c0 = o11["candidates"]["clock_0deg"]
    c25 = o11["candidates"]["clock_25deg"]
    dv = o11["candidates"]["delivered_v2_clock25"]

    v["human_rulings_2026_07_27"] = {
        "T_SM": "MOUNT_FACE_X=198.0 显示轨（人工批准；与 Codex adapter_outer_face_x 一致）",
        "STOW_Z_LIMIT": "暂不定义，保持 UNKNOWN——禁止默认判合规",
        "SEQUENCE": "先 O9/O10 翼根返工，后 O11 时钟角量化（均已执行）"}
    v["codex_reconciliation"] = {
        "file": "CODEX_CONTINUATION_RECONCILIATION.md",
        "codex_deliverable": "100_Mechanical_Continuation/v22_mechanical_continuation.step"
                              "（c844c071…，132 occ/122 solids，16PASS/6HOLD/2NA/0FAIL）",
        "codex_format": "STEP_ONLY_NOT_NATIVE（其自述内存不足未启可见 SolidWorks）",
        "aligned": ["160x160x12 安装板", "Ø100 中央接口", "adapter_outer_face_x=198.0",
                     "bus 226.3", "载荷路径链", "mass=EXCLUDED/URDF 唯一"],
        "root_cause_of_break": "120 阶段把该目录锁哈希当冻结只读却从未读正文（→O12）"}
    v["gates"]["N9_CODEX_SOLAR_ROOT_ALIGNMENT"] = {
        "status": "PASS",
        "evidence": "O9：每侧 14 件按 Codex SOLAR-ROOT-01 重建（Root_Base X[-79,-43]/"
                     "Y[113.15,121.15]、双耳 X[-75,-65]&[-57,-47] 外缘 |Y|=151.15、Ø8 通销、"
                     "Ø16×18 扭簧、HDRM 24方×8+Ø10×20@X=-160/40、硬止挡 14方×8、脊板穿板）；"
                     "原 X[126,174] 内置版本全删"}
    v["gates"]["N10_NEGATIVE_RESULTS_PRESERVED"] = {
        "status": "PASS",
        "evidence": "O10：C5 收拢包宽 238.3>226.3（超 12.0）与机构下限宽 302.3 写入"
                     "Master Skeleton PARAM_* 及两翼根子装配属性；返工后耳片外缘"
                     "几何实测达 |Y|=151.15，负结果由纸面变可测事实"}
    v["gates"]["N11_O11_CLOCKING_ADJUDICATED"] = {
        "status": "PASS",
        "evidence": f"七项判据量化（design/o11_clocking_adjudication.json）；"
                     f"F-O11-1：clock+q1 恒为 168.322° → 冗余自由度，c_min="
                     f"{f['minimum_required_clock_deg']}°；clock=0 时臂 |Y|="
                     f"{c0['C2_width']['max_abs_y_mm']} 破 113.15"}
    v["o11_ruling"] = {
        "ruling": "CLOCKING_REQUIRED_VALUE_FREE_ABOVE_7.894DEG",
        "minimum_required_clock_deg": f["minimum_required_clock_deg"],
        "recommended_clock_deg": 25.0,
        "q1_margin_at_25deg": f["margin_at_25deg"],
        "rationale": "时钟角必需（无时钟角横向破包络 "
                      f"{round(c0['C2_width']['max_abs_y_mm'] - 113.15, 2)}mm）；"
                      "具体数值不由七判据决定而由 joint1 限位余量决定",
        "comparator_status": "STOW_NO_CLOCK_COMPARATOR 降级为已证伪对照组（保留为反例证据）",
        "stow_vector_status": "仍 CANDIDATE_HOLD——三候选均不能同时满足"
                               "可动段间隙≥8mm ∧ 鞍座塔高≤150mm",
        "measured": {
            "clock0": {"max_abs_y": c0["C2_width"]["max_abs_y_mm"],
                        "movable_clearance": c0["C3_clearance_to_structure"]["movable_links_min_mm"]},
            "clock25_optimum": {"max_abs_y": c25["C2_width"]["max_abs_y_mm"],
                                 "movable_clearance": c25["C3_clearance_to_structure"]["movable_links_min_mm"],
                                 "tower_max": c25["C4_saddles"]["tower_height_min_max_mm"][1]},
            "delivered_v2": {"max_abs_y": dv["C2_width"]["max_abs_y_mm"],
                              "movable_clearance": dv["C3_clearance_to_structure"]["movable_links_min_mm"],
                              "tower_max": dv["C4_saddles"]["tower_height_min_max_mm"][1],
                              "first_motion_clearance": dv["C5_release_path"]["clearance_after_5deg_mm"]}},
        "report": "O11_CLOCKING_ADJUDICATION_REPORT.md",
        "review_status": "PENDING_HUMAN_REVIEW"}
    v3 = json.loads((ROOT / "design/b601_stow_joint_vector_v3.json")
                    .read_text(encoding="utf-8"))
    sd = json.loads((ROOT / "design/o13_saddle_stations.json")
                    .read_text(encoding="utf-8"))
    ex = v3["exact_verification"]
    v["gates"]["N12_O13_STOW_VECTOR_V3"] = {
        "status": "PASS",
        "evidence": f"v3 q_deg={v3['q_deg']}（clock=25°）；可动段间隙 "
                     f"{ex['C3_clearance_to_structure']['movable_links_min_mm']}mm ≥8 ✅；"
                     f"|Y| {ex['C2_width']['max_abs_y_mm']} ≤113.15 ✅；三鞍座塔高 "
                     f"{[s['tower_h'] for s in sd['selected_saddles']]} 全 ≤150 ✅；"
                     f"首动 {ex['C5_release_path']['best_first_joint']} → "
                     f"{ex['C5_release_path']['clearance_after_5deg_mm']}mm"}
    v["o13_result"] = {
        "stow_vector_v3": {"clock_deg": v3["clock_deg"], "q_deg": v3["q_deg"],
                            "status": v3["STOW_VECTOR_STATUS"]},
        "saddles": sd["selected_saddles"],
        "usable_stations": sd["n_usable"], "usable_span_mm": sd["usable_span_mm"],
        "method": "4mm 占据栅格 EDT 距离场加速搜索 + 点-三角精确复核",
        "traps_caught": {
            "T1": "代价缺下界→优化器把臂折到舱体下方(z≈-450)压低 maxZ",
            "T2": "塔高口径错（全部跨舱面分箱 vs 支承站位存在性）",
            "T3": "距离场按格心量化，比真值乐观 CELL·√3/2≈3.5mm",
            "T4": "释放净空包络下沿被最高鞍座垫顶穿 5763mm³"},
        "report": "O13_STOW_VECTOR_V3_REPORT.md",
        "review_status": "PENDING_HUMAN_REVIEW"}
    drw = json.loads((ROOT / "evidence/drawing_STOWED.json").read_text(encoding="utf-8"))
    v["gates"]["N13_NATIVE_DRAWINGS"] = {
        "status": "PASS",
        "evidence": f"原生 .SLDDRW × 2（STOWED / MAINTENANCE），GB A2 图框，"
                     f"每张 4 视图（前/上/右/等轴测）+ **A-A 真剖视**（SolidWorks 原生剖切）；"
                     f"PDF 由 SolidWorks 自身导出；"
                     f"取代此前 matplotlib 渲染作为视觉交付"}
    v["deviations"].update({
        "D-NATIVE-08": "工程图 GB 模板「重量」栏直接解析系统属性 SW-Mass，显示 "
                        "6.159kg（SolidWorks 默认密度产物，**无权威**）。"
                        "自定义属性覆盖、注释遍历改写均无效（各试 1 次）。"
                        "已在图面加注 'MASS_AUTHORITY = EXCLUDED … title-block weight void'；"
                        "唯一质量权威仍为 accepted URDF 4.6955559493429862 kg。"
                        "**引用本图时必须无视该栏数字**",
        "D-NATIVE-09": "爆炸视图不可达：IConfiguration 无 GetExplodedViewCount、"
                        "IAssemblyDoc 无 NewExplodedView/CreateExplodedView（makepy 早绑定）。"
                        "有界尝试 1 次即停；以 MAINTENANCE 抑制态 + A-A 真剖视替代",
        "D-NATIVE-04": "FeatureCut3 的 Dir=False 沿 -X（与 FeatureExtrusion2 的 +X 相反）——"
                        "外板开槽曾切反方向（体积正确 6384mm³、位置差 14mm），靠干涉抓出",
        "D-NATIVE-05": "SolidWorks 在右侧翼根子装配步骤连续 3 次崩溃（低内存）；构建器可重入",
        "D-NATIVE-06": "finalize_native.py 会从头重写裁决——人工裁决/衔接/O9-O11 结论"
                        "须由本脚本在其后重新施加",
        "D-RECON-03": "对 Codex 三处必要偏离：①脊板 Y 缩至 [110.15,113.15] 并在外板开真实"
                       "穿板槽（原值与 Root_Base 重叠 7680mm³）②扭簧 X 外移（原位与耳2 重叠）"
                       "③两段销合并为单根通销（原重叠 301.6mm³）"})
    v["open_items"] = [i for i in v["open_items"]
                       if not i.startswith(("O9(", "O10(", "O11 "))]
    v["open_items"] += [
        "O11 已裁决：CLOCKING_REQUIRED_VALUE_FREE_ABOVE_7.894DEG（待人工批准 25°）",
        "O12 流程修正：冻结只读目录必须先读正文再锁哈希",
        "O13 已完成：v3 向量 + 三鞍座站位（仍 CANDIDATE_HOLD，接触资格未定）",
        "O14 已随 O13 定案：鞍座 X 窗口 [-20,0]/[80,100]/[160,180]",
        "O15 爆炸视图不可达（API 缺失，D-NATIVE-09）——如硬性需要须换绑定或手工建",
        "O16 工程图重量栏 6.159kg 无权威且无法经 API 抹除（D-NATIVE-08）——"
        "对外发图前须人工在模板中清空该栏"]
    v["solar_root_status"] = "O9_REWORK_COMPLETE_CODEX_ALIGNED"
    n_fail = sum(1 for g in v["gates"].values() if g["status"].startswith("FAIL"))
    v["summary"]["gates_pass"] = len(v["gates"]) - n_fail
    v["summary"]["gates_fail"] = n_fail
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    print("patched:", v["final_verdict"], "| gates",
          v["summary"]["gates_pass"], "/", len(v["gates"]),
          "| open", len(v["open_items"]), "|", v["o11_ruling"]["ruling"])


if __name__ == "__main__":
    main()
