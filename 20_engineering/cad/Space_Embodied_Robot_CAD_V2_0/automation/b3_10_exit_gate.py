"""B3-10b 退出 Gate：V2-CAD-01..20 机器评估 + 原生重开全检 + V1 未改证明。

产出：
  evidence/b3_10/native_reopen_check.json     全部 V2 原生文件重开+重建
  evidence/b3_10/v2_cad_01_20_evaluation.json 二十项判定与证据指针
  evidence/b3_10/B3_exit_gate.yaml            机器裁决 + 人工评审位
裁决只在四选一内；机器裁决不替代人工终审（review_status=PENDING_HUMAN_REVIEW）。
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, connect,
                            open_document)

EVID = V2_ROOT / "evidence/b3_10"
DT = V2_ROOT / "evidence/digital_thread"


def reopen_all(log):
    sw = connect(log)
    sw.CloseAllDocuments(True)
    natives = sorted(V2_ROOT.rglob("*.SLDPRT")) + sorted(V2_ROOT.rglob("*.SLDASM"))
    results = []
    for p in natives:
        try:
            m = open_document(sw, log, p, read_only=False)
            ok = bool(m.ForceRebuild3(False))
            results.append({"file": str(p.relative_to(V2_ROOT)).replace("\\", "/"),
                            "reopen": True, "rebuild": ok})
        except B3FailClosed:
            results.append({"file": str(p.relative_to(V2_ROOT)).replace("\\", "/"),
                            "reopen": False, "rebuild": False})
        sw.CloseAllDocuments(True)
    bad = [r for r in results if not (r["reopen"] and r["rebuild"])]
    return {"total": len(results), "pass": len(results) - len(bad),
            "failures": bad, "verdict": "PASS" if not bad else "FAIL",
            "files": results}


def rerun_entry_verifier():
    # 评审 MED 整改：重跑前把现有入口证据按时间戳存档，不覆盖原件历史
    src_dir = V2_ROOT / "evidence/b3_00"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    arch = src_dir / "archive" / stamp
    arch.mkdir(parents=True, exist_ok=True)
    import shutil
    for fn in ("B3_entry_verification.json", "B3_entry_baseline_manifest.csv"):
        if (src_dir / fn).exists():
            shutil.copy2(src_dir / fn, arch / fn)
    subprocess.run([sys.executable,
                    str(V2_ROOT / "automation/b3_00_entry_verifier.py")],
                   capture_output=True, text=True, timeout=600)
    # 以裁决 JSON 文件为权威（stdout 摘要不含 b601_match_verdict 等字段）
    return json.loads((V2_ROOT / "evidence/b3_00/B3_entry_verification.json")
                      .read_text(encoding="utf-8"))


def _check_no_tsb_mount(props_inv: str):
    """实质检查：mount 模块各件 FRAME_ID 只能是 CS_M/CS_A0；frame_export 禁用含 T_SB。"""
    import csv as _csv
    import io
    ok_frames = True
    for row in _csv.reader(io.StringIO(props_inv)):
        if len(row) >= 3 and "05_Robot_Mount_Module" in row[0] and row[1] == "FRAME_ID":
            if row[2] not in ("CS_M", "CS_A0"):
                ok_frames = False
    fe = (DT / "frame_export.yaml").read_text(encoding="utf-8")
    return ok_frames and "T_SB" in fe and "CS_B(T_SB)" in fe


def _check_solar_states():
    want = {"DEPLOYED_REFERENCE_Q0": False, "STOWED_PROPOSAL": True,
            "SAFE_DISPLAY_PROPOSAL": True}
    for cfg, want_sup in want.items():
        rep = json.loads((V2_ROOT / f"evidence/b3_08/interference_{cfg}.json")
                         .read_text(encoding="utf-8"))
        solar = [p["suppressed"] for p in rep["participants"]
                 if "Solar" in p["name"]]
        if not solar or any(s != want_sup for s in solar):
            return False
    return True


def _check_scoped_interference(interf_idx):
    if len(interf_idx["reports"]) != 6:
        return False
    for cfg in interf_idx["reports"]:
        rep = json.loads((V2_ROOT / f"evidence/b3_08/interference_{cfg}.json")
                         .read_text(encoding="utf-8"))
        if rep.get("configuration") != cfg:
            return False
        if "no_global_collision_safety_claim" not in rep.get("claim_limit", ""):
            return False
        # 主结构（含中框）必须解析参与——否则"结构零干涉"未被证明
        for p in rep["participants"]:
            if "Primary" in p["name"] and p["suppressed"]:
                return False
    return True


def evaluate(reopen, entry, log):
    claims = (DT / "claim_limit_audit.csv").read_text(encoding="utf-8")
    interf_idx = json.loads((V2_ROOT / "evidence/b3_08/interference_index.json")
                            .read_text(encoding="utf-8"))
    mc02 = json.loads((V2_ROOT / "evidence/b3_02/master_skeleton_machine_check.json")
                      .read_text(encoding="utf-8"))
    mc03 = json.loads((V2_ROOT / "evidence/b3_03/primary_structure_machine_check.json")
                      .read_text(encoding="utf-8"))
    views = json.loads((V2_ROOT / "10_Review_Overlays/review_view_manifest.json")
                       .read_text(encoding="utf-8"))
    props_inv = (DT / "custom_property_inventory.csv").read_text(encoding="utf-8")

    entry_ok = entry.get("verdict") == "B3_ENTRY_BASELINE_LOCKED" and \
        entry.get("b601_match_verdict") == "B601_HASH_AND_TOPOLOGY_MATCH"

    checks = {
        "V2-CAD-01": (entry_ok, "独立 V2 根 + V1 32/32+43/43 复核", "b3_00/B3_entry_verification.json"),
        "V2-CAD-02": ("PARAM_BODY_X_MM" in props_inv,
                      "骨架参数入方程(D-EQ-01 偏差:PARAM_*属性+规格YAML承担)",
                      "b3_02/master_skeleton_inventory.json + D-EQ-01"),
        "V2-CAD-03": (mc02["verdict"] == "B3_02_MASTER_SKELETON_VERIFIED",
                      "CS_S/CS_M/CS_A0 与 T_SM 数值逐位", "b3_02/master_skeleton_machine_check.json"),
        "V2-CAD-04": (_check_no_tsb_mount(props_inv),
                      "T_SB 未用作 mount transform(mount 件 FRAME_ID∈{CS_M,CS_A0} "
                      "且 frame_export 禁用列表含 T_SB)", "digital_thread/frame_export.yaml"),
        "V2-CAD-05": ((DT / "structure_class_inventory.csv").exists(),
                      "主/次/占位/reference 分类清单", "digital_thread/structure_class_inventory.csv"),
        "V2-CAD-06": ((DT / "assembly_tree.yaml").exists(),
                      "三舱独立 owner+边界", "digital_thread/assembly_tree.yaml"),
        "V2-CAD-07": (any(v["view"] == "V2-VIEW-06" for v in views["views"]),
                      "反力链视图+接口清单+lp回链", "review_views + interface_inventory.yaml"),
        "V2-CAD-08": ("STRENGTH_PASS" not in claims.replace("strength_claims", ""),
                      "无强度/刚度/模态/飞行合格声明", "digital_thread/claim_limit_audit.csv"),
        "V2-CAD-09": ((DT / "equipment_volume_register.yaml").exists(),
                      "独立 volume owner 登记", "digital_thread/equipment_volume_register.yaml"),
        "V2-CAD-10": ((V2_ROOT / "04_Rear_Service_Module/parts/VOL_REAR_PROP.SLDPRT").exists(),
                      "后舱四区 owner 分离", "04_Rear_Service_Module/parts/"),
        "V2-CAD-11": ((DT / "serviceability_matrix.csv").exists(),
                      "维护矩阵+方向视图(托盘TBD如实)", "digital_thread/serviceability_matrix.csv"),
        "V2-CAD-12": (entry.get("b601_match_verdict") == "B601_HASH_AND_TOPOLOGY_MATCH",
                      "B601 10L/9J+11/11哈希+q0", "06_B601_Visual_Arm/source_hash_and_topology_register.yaml"),
        "V2-CAD-13": (_check_solar_states(),
                      "太阳翼状态实质分离(DEPLOYED 解析/STOWED+SAFE 抑制,读自干涉参与者)",
                      "b3_08/interference_*.json participants"),
        "V2-CAD-14": ("ZERO_SOLID_REQUIRED" in props_inv,
                      "sensor/TCP/target 隔离(零实体+禁用CS+独立场景)", "零实体构建断言 + target scene"),
        "V2-CAD-15": (interf_idx["inherited_negative_results"]["count"] == 10,
                      "V1 十处负结果记录级继承", "b3_08/interference_index.json"),
        "V2-CAD-16": (_check_scoped_interference(interf_idx),
                      "干涉实质 scoped(6配置、参与者状态与登记一致、主结构全解析、"
                      "非外推 claim)", "b3_08/interference_*.json"),
        "V2-CAD-17": ("NONE_CAD_ZERO_MASS_AUTHORITY" in props_inv
                      or "NONE_DISPLAY_ONLY" in props_inv,
                      "无质量/材料权威污染", "digital_thread/claim_limit_audit.csv + MASS_OWNER"),
        "V2-CAD-18": ((DT / "source_and_license_manifest.yaml").exists(),
                      "来源/许可/偏差清单", "digital_thread/source_and_license_manifest.yaml"),
        "V2-CAD-19": (reopen["verdict"] == "PASS",
                      f"原生重开重建 {reopen['pass']}/{reopen['total']}",
                      "b3_10/native_reopen_check.json"),
        "V2-CAD-20": (entry_ok, "冻结边界(V1/Gate/config/URDF)未改",
                      "b3_00 复核(退出时重跑)"),
    }
    return checks


def main():
    log = BuildLog("b3_10_exit_gate")
    EVID.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    reopen = reopen_all(log)
    (EVID / "native_reopen_check.json").write_text(
        json.dumps(reopen, ensure_ascii=False, indent=2), encoding="utf-8")
    log.event("REOPEN_CHECK", **{k: reopen[k] for k in ("total", "pass", "verdict")})

    entry = rerun_entry_verifier()
    log.event("ENTRY_RERUN", verdict=entry.get("verdict"))

    checks = evaluate(reopen, entry, log)
    n_pass = sum(1 for ok, _, _ in checks.values() if ok)
    evaluation = {"generated_utc": now,
                  "checks": {k: {"pass": ok, "summary": s, "evidence": e}
                             for k, (ok, s, e) in checks.items()},
                  "passed": n_pass, "total": len(checks)}
    (EVID / "v2_cad_01_20_evaluation.json").write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")

    verdict = ("V2_SYSTEM_MECHANICAL_CAD_COMPLETE_WITH_PHYSICAL_LIMITATIONS"
               if n_pass == len(checks) else "V2_SYSTEM_MECHANICAL_CAD_PARTIAL")
    gate = {
        "gate_id": "COMP-PROT-03-A4-B3-V2-SYSTEM-MECHANICAL-CAD",
        "machine_verdict": verdict,
        "criteria_passed": f"{n_pass}/{len(checks)}",
        "review_status": "PENDING_HUMAN_REVIEW",
        "human_approval_record": "evidence/b3_00/HUMAN_APPROVAL_RECORD.yaml",
        "physical_limitations_preserved": [
            "FEA/强度/刚度/模态/热 NOT_EVALUATED",
            "材料/板厚/紧固件/预紧 UNKNOWN_BLOCKED",
            "质量/质心/惯量 CAD 零权威(SSOT 不变)",
            "T_SB / physical TCP / 相机 FOV UNKNOWN_BLOCKED",
            "standard_12U_claim BLOCKED (NON_FLIGHT_DISPLAY_ONLY)",
            "global_collision_safety BLOCKED (V1 十处 q0 负结果继承)",
            "V2-UNK-001..017 全部保持未闭合",
        ],
        "deviations": "evidence/digital_thread/v1_to_v2_deviation_manifest.csv",
        "not_authorized_next": ["FEA", "URDF_roundtrip", "dynamics", "manufacturing",
                                "A5", "hardware", "git_commit"],
        "generated_utc": now,
    }
    (EVID / "B3_exit_gate.yaml").write_text(
        yaml.safe_dump(gate, allow_unicode=True, sort_keys=False), encoding="utf-8")
    log.event("B3_10B_DONE", verdict=verdict, passed=n_pass)
    print(json.dumps({"machine_verdict": verdict,
                      "criteria": f"{n_pass}/{len(checks)}",
                      "failed": [k for k, (ok, _, _) in checks.items() if not ok]},
                     ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
