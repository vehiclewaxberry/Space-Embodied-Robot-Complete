# -*- coding: utf-8 -*-
# KIMI M7 terminal takeover swarm - round0 handover receipt builder (read-only + writes only this output dir)
import hashlib, json, os
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
F = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
E21 = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics"
V5D = F + "/ecr_b601_harness_rated_envelope/15_loop_continuation_v5"
V4D = F + "/ecr_b601_harness_rated_envelope/14_loop_continuation_v4"
RCG = F + "/ecr_b601_harness_rated_envelope/08_route_c/02_pre_cad_parametric_guided_route_search/03_gate"
MPID = F + "/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/02_mpi_evidence_audit"
SOL = F + "/ecr_solar_array_r2"

def sha256_raw(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def sha256_lf(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest().upper()

def loadj(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)

spec = [
    ("v5_gate", V5D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json", "EB7F9AA14E5F455831711089D3ED3A2C5014783E5D103E144E164AFE9CC8379B", 19378, "V5 output manifest outputs[0]"),
    ("v5_brief", V5D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V5.md", "7AFEAE867908B306AD730C7A9AD7BD14720BE0845F6B6BD4BA1E54B203327AC6", 2562, "V5 output manifest outputs[1]"),
    ("v5_validation", V5D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V5.json", None, None, "无记录哈希：V5 manifest 声明 validation_report_excluded_to_avoid_self_hash=true"),
    ("v5_manifest", V5D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V5.json", None, None, "无记录哈希：manifest 即记录者自身"),
    ("v4_gate", V4D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4.json", "B1D73BBCA80D231BAEEF9DAC8A0A2BD43248760FAB94E70375F9433513B2601D", 19206, "V5 gate input_bindings"),
    ("v4_brief", V4D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V4.md", "B426041646CC1C154D1299E169A58C8D151E04C6DF45FE6D1158B32344A48A98", 2802, "V5 gate input_bindings"),
    ("v4_manifest", V4D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V4.json", "15BE7086FF2D469695C942B9B729001F3ACAB504F58CFC828EDEC21E7F4269FD", 5314, "V5 gate input_bindings"),
    ("v4_validation", V4D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V4.json", "3E3F8375C1543AA59C98E5F7EF7F7DB029288856B3798769102EEDA7738354D7", 22163, "V5 gate input_bindings"),
    ("e21_gate", E21 + "/results/E21_DIAGNOSTIC_GATE_V1.json", "B03B7C7AF571AA00FE3612756FFBBD99CB834B84377BA8DC2C213355C252616B", 22675, "V5 gate input_bindings"),
    ("e21_validation", E21 + "/results/E21_VALIDATION_V1.json", "AF681C99C4A32E7A04EB83435FF8B4743D1BABC3A26E522A824B12142DC45825", 10735, "V5 gate input_bindings"),
    ("e21_manifest", E21 + "/results/E21_OUTPUT_MANIFEST_V1.json", "8DA16F75AAE0AF359EEA597E1F279EEF8F6CEBBCA491DC4BF6D6F133810B580F", 5259, "V5 gate input_bindings"),
    ("route_c_precad_gate", RCG + "/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1.json", "B43745081B4D0F2250993EBDB89074054B4A755C8A21555F9A42F0C392BCADCF", 17306, "V5 gate input_bindings"),
    ("route_c_precad_validation", RCG + "/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_VALIDATION_V1.json", "84D89F631F7904DA955F7654AFE6DC06F8E5458A08AF410435808000A375FCAF", 32996, "V5 gate input_bindings"),
    ("route_c_precad_manifest", RCG + "/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_OUTPUT_MANIFEST_V1.json", "7AE5015ED5E2DDE4B4F6F950B49147521DDB5960DDAB7142F8D0D57C9F4D3F0E", 10859, "V5 gate input_bindings"),
    ("e21_authority_contract", E21 + "/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml", "7D2E0792B3FF6BAB9BD9AE11A605341B20BAAB821961A7BA8E119996D1515D81", 3053, "E21 output manifest"),
    ("e21_nine_config_audit", E21 + "/results/E21_NINE_CONFIGURATION_ARM_PLACEMENT_AUDIT_V1.json", "FCCE9EFBD4010201EFC08A3A01B95DA0676F6862C071BB40E4AC1AB6ADFC2129", 88834, "E21 output manifest"),
    ("e21_odr01_radau_summary", E21 + "/results/E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_SUMMARY_V1.json", "C575F1D4F4CDDBAE9890D44379A575E28817A2586D8741FA9FEDC044AD8C038C", 2586, "E21 output manifest"),
    ("accepted_urdf_b601", "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf", "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164", 11321, "wp11 receipt source_register / E21 input manifest / PROJECT_MODEL_TRUTH_HIERARCHY（raw CRLF）"),
    ("solar_r2_step", SOL + "/SOLAR_ARRAY_R2_CANDIDATE_V1.step", "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795", None, "SOLAR_ARRAY_R2_BUILD_REPORT_V1 hashes"),
    ("solar_r2_fcstd", SOL + "/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd", "9D4D249A5D4EED7BDD8F3C08EC96737884A19523782112B1E72AD9EA0A1B65AB", None, "SOLAR_ARRAY_R2_BUILD_REPORT_V1 hashes"),
    ("solar_r2_build_report", SOL + "/SOLAR_ARRAY_R2_BUILD_REPORT_V1.json", "AFE4CA26A2CC7A1838DEF4FAD3E068DB1F364F4265A85903D9407D462711CEC9", None, "build report 自记录哈希（hashes 块内自指条目）"),
    ("embodied_contract_r2", F + "/wp13_embodied_contract/EMBODIED_MECHANICAL_CONTRACT_R2.yaml", "5DDA627794A4B29D087D7489BECC7A98ED632BC6EAC0413CD9F7226C03AE1E7C", 95903, "E21 input manifest"),
    ("embodied_handoff_gate_r2", F + "/wp13_embodied_contract/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_R2.json", "AE6165EAFC02551D92B73707D41FE0D4A5A78704FBEA65D1FA49D10C7C9F5B22", 33959, "E21 input manifest"),
    ("mech_dynamics_interface_v5_r2", F + "/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V5_R2.yaml", "9B6D8025D3318A66AB7DD9BD15F7EEE2CDE31DD7A0A9A4FDB5CE4AEB60DE8203", 18869, "E21 input manifest"),
    ("route_c_mpi_evidence_gate", MPID + "/ROUTE_C_MPI_EVIDENCE_GATE_V1.json", "348C9D603F7249E938E5F398CDA53B28A2B1155AFF2330F147BD93372F236D50", 2981, "V2 gate mpi_gate / Route-C precad contract / MPI audit output manifest"),
    ("flexible_appendage_r2_modes", SOL + "/FLEXIBLE_APPENDAGE_R2_MODES.json", "E068DE078A0DC680A44807516733FDF018DD720B5F65636BB2B8D21E557593B6", 1345, "E21 input manifest"),
    ("flexible_appendage_r2", SOL + "/FLEXIBLE_APPENDAGE_R2.yaml", "A04ACFE440C636BB095585C74F71E3563FD35F6678FCFAA39355383A9BF6B3FD", 2707, "E21 input manifest"),
    ("system_mass_v3_r2", F + "/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml", "3FD2557318E98748A37927977FA2925C18803668FE16391D824C184F646486BB", 223714, "E21 input manifest"),
    ("m7_release_gate_v1", F + "/12_release/MECHANICAL_ENGINEERING_RELEASE_GATE_V1.json", "2D9C8580701BD087A2DB52F57AE9ED23A919DEBC7476727467214411F952859E", 48538, "10_loop_integration stage gate m7_release_gate"),
]

verification = []
for name, rel, exp, expb, src in spec:
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        verification.append({"name": name, "path": rel, "status": "MISSING", "expected_sha256": exp, "recorded_in": src})
        continue
    b = os.path.getsize(p)
    s = sha256_raw(p)
    if exp is None:
        st = "NO_RECORDED_HASH"
    elif s == exp.upper():
        st = "PASS"
    else:
        st = "DRIFT"
    row = {"name": name, "path": rel, "bytes": b, "sha256": s, "expected_sha256": exp, "recorded_in": src, "status": st}
    if expb is not None:
        row["expected_bytes"] = expb
        row["bytes_match"] = (b == expb)
    verification.append(row)

urdf_rel = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
urdf_lf = sha256_lf(os.path.join(ROOT, urdf_rel))
for row in verification:
    if row["name"] == "accepted_urdf_b601":
        row["sha256_lf_normalized"] = urdf_lf
        row["expected_sha256_lf_normalized"] = "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4"
        row["lf_recorded_in"] = "PROJECT_MODEL_TRUTH_HIERARCHY.yaml / PL1-B CURRENT_MECHANICAL_BASELINE_RULING.md"
        row["status_lf"] = "PASS" if urdf_lf == row["expected_sha256_lf_normalized"] else "DRIFT"

drift = [r for r in verification if r["status"] in ("DRIFT", "MISSING") or r.get("status_lf") == "DRIFT"]
n_pass = sum(1 for r in verification if r["status"] == "PASS")
n_nrh = sum(1 for r in verification if r["status"] == "NO_RECORDED_HASH")

v5 = loadj(V5D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json")
e21g = loadj(E21 + "/results/E21_DIAGNOSTIC_GATE_V1.json")
mpig = loadj(MPID + "/ROUTE_C_MPI_EVIDENCE_GATE_V1.json")
rg = loadj(F + "/12_release/MECHANICAL_ENGINEERING_RELEASE_GATE_V1.json")
odr = loadj(E21 + "/results/E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_SUMMARY_V1.json")
wp = loadj(E21 + "/results/E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_SUMMARY_V1.json")
sens = loadj(E21 + "/results/E21_TWO_PLACEMENT_RIGID_DYNAMICS_SENSITIVITY_V1.json")

def peak(d):
    return d.get("metrics", {}).get("peak_base_attitude_deviation_deg")

now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
receipt = {
    "schema": "KIMI_M7_TERMINAL_HANDOVER_RECEIPT_V1",
    "generated_local": now.isoformat(timespec="seconds"),
    "generator": "KIMI M7 机械终局接管 swarm round0 子代理（BASELINE+RECEIPT 任务）",
    "overall_status": "HASH_DRIFT_DETECTED" if drift else "BASELINE_VERIFIED_NO_DRIFT",
    "authority_basis": {
        "ODR-43_verbatim": "ODR-43 — B601_ARM_PLACEMENT_RULE: DUAL_FRAME_EXPLICIT_BRIDGE。WP11 physical installation = PHYSICAL_INSTALLATION_AUTHORITY；ODR-01 T_SM = DYNAMICS_FRAME_AUTHORITY。必须建立唯一显式桥接 T_PHYSICAL_TO_DYNAMIC；mass/CG/inertia/interface loads/CAD geometry/collision geometry 从物理安装系进入动力学系只能经此桥。禁止：二选一、按模块混用、取平均、把 0.36889° 差值当随机不确定度、静默替换坐标。",
        "ODR-44_verbatim": "ODR-44 — ODR-42: APPROVE_BOUNDED_DETAILED_DESIGN。冻结 accepted B601 URDF、Solar Array R2、M3R authority、Gripper R1 accepted geometry、existing M7 operational FEA evidence。MPI-01..MPI-08（本任务的安装桥接工作包）全部闭合后才允许建 Route-C independent versioned CAD candidate。",
        "v5_required_owner_statement_verbatim": v5["required_owner_statement"],
        "v5_required_owner_statement_source": V5D + "/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json",
    },
    "scope_compliance": "全程只读既有文件；仅在本回执输出目录写新文件；未修改/重生成 accepted URDF、Solar R2、任何上游 ledger 或 Gate JSON；未启动任何 CAD/FEA 进程；仅用 cpython 3.13 计算 sha256；未执行任何 git 写操作。",
    "baseline_verification": verification,
    "verification_summary": {"files_checked": len(verification), "pass": n_pass, "no_recorded_hash": n_nrh, "drift_or_missing": len(drift)},
    "drift_list": drift,
    "drift_analysis": "唯一 DRIFT 为 SOLAR_ARRAY_R2_BUILD_REPORT_V1.json 的自记录哈希（记录 AFE4CA26A2CC7A1838DEF4FAD3E068DB1F364F4265A85903D9407D462711CEC9，实测 6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586）。该条目是 hashes 块内的自指记录；已对 raw、LF 归一化、加尾换行、删自指键、自指置 null、自指清零、hashes 仅含两个工件等规范化形式逐一试算，均无法复现记录值，按 fail-closed 记为 DRIFT。同一 build report 内记录的两个真实工件（STEP=21FF77B8…、FCStd=9D4D249A…）复算均 PASS，V5 input_bindings 十条与 e21/wp11/CM 记录链全部 PASS，无证据表明任何 authority 工件被改动；建议上游以显式 self_hash_policy（参照 e21/V5 manifest 的 self-reference-excluded 做法）重签发该 build report 以闭合此 DRIFT。",
    "current_gate_state": {
        "mechanical_loop_v5": {"gate": v5["gate"], "next_stage_authorized": v5["next_stage_authorized"], "release_credit": v5["release_credit"], "released_segments": v5["released_segments"], "verdict": v5["verdict"]},
        "e21_diagnostic": {"overall": e21g.get("overall", e21g.get("gate")), "next_stage_authorized": e21g.get("next_stage_authorized"), "release_credit": e21g.get("release_credit")},
        "route_c_mpi_evidence": {"gate": mpig["gate"], "criteria_controlled": str(mpig["criteria_controlled"]) + "/" + str(mpig["criteria_total"]), "cad_generation_authorized": mpig["cad_generation_authorized"], "next_stage_authorized": mpig["next_stage_authorized"]},
        "m7_release_gate_v1": {"overall_gate_a_shape": rg["overall_gate_a_shape"], "review_status": rg["review_status"], "next_stage_authorized": rg["next_stage_authorized"]},
    },
    "handover_frontier": {
        "blocking_frontier_now": "B601 安装语义双轨：WP11 physical placement ↔ ODR-01 T_SM dynamics frame（frame-consumption ambiguity，非不确定度）",
        "sequence": [
            "installation bridge：建立唯一显式 T_PHYSICAL_TO_DYNAMIC 并闭合 MPI-01..MPI-08",
            "Route-C independent versioned CAD candidate（待 MPI 全闭合后才允许建）与 R2 full-flex / e15 重认证",
            "Terminal Gate",
        ],
        "e21_evidence": {
            "odr01_dynamics_t_sm_peak_base_attitude_deviation_deg": peak(odr),
            "wp11_physical_geometry_context_peak_base_attitude_deviation_deg": peak(wp),
            "physical_minus_odr01_delta_deg": sens["physical_context_minus_odr01"]["peak_base_attitude_deviation_deg"],
            "interpretation": "frame-consumption ambiguity, not statistical uncertainty（standard_uncertainty=null）",
            "sources": [
                E21 + "/results/E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_SUMMARY_V1.json",
                E21 + "/results/E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_SUMMARY_V1.json",
                E21 + "/results/E21_TWO_PLACEMENT_RIGID_DYNAMICS_SENSITIVITY_V1.json",
            ],
        },
        "frame_definitions_source": {
            "path": E21 + "/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml",
            "sha256": "7D2E0792B3FF6BAB9BD9AE11A605341B20BAAB821961A7BA8E119996D1515D81",
            "ODR01_DYNAMICS_T_SM": [[0, 0, 1, 0.18525], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]],
            "WP11_PHYSICAL_GEOMETRY_CONTEXT": [[0, 0, 1, 0.208], [0.422618483193, 0.906307683772, 0, 0], [-0.906307683772, 0.422618483193, 0, 0], [0, 0, 0, 1]],
        },
    },
    "next_stage_authorized": False,
    "release_credit": False,
    "prohibition_reminder": [
        "禁止二选一/按模块混用/两 frame 取平均/把 0.36889° 差值当随机不确定度/静默替换坐标",
        "MPI-01..MPI-08 未全部闭合前禁止建 Route-C independent versioned CAD candidate",
        "禁止静默复用旧 24 kg 质量模型或旧 Solar R1 柔性模型",
        "test PASS 不授予任何 authority",
    ],
}

out = os.path.join(os.path.dirname(__file__), "KIMI_M7_TERMINAL_HANDOVER_RECEIPT.json")
with open(out, "w", encoding="utf-8", newline="\n") as f:
    json.dump(receipt, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("WROTE", out)
print("overall_status:", receipt["overall_status"], "| pass:", n_pass, "| no_recorded:", n_nrh, "| drift:", len(drift))
print("odr01_peak:", peak(odr), "| wp11_peak:", peak(wp), "| delta:", sens["physical_context_minus_odr01"]["peak_base_attitude_deviation_deg"])
print("receipt sha256:", sha256_raw(out), "| bytes:", os.path.getsize(out))
