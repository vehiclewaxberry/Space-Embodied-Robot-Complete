"""VENDOR-CAD-03 终裁 + 产物清单（评审收口后最后运行）。

用法：python s7_finalize.py <review_conclusion> <high> <medium> <low>
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc).isoformat()


def sha256(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    concl, hi, med, lo = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    mc = json.loads((HERE / "validation/machine_checks.json").read_text(encoding="utf-8"))
    v2 = json.loads((HERE / "design/b601_stow_joint_vector_v2.json").read_text(encoding="utf-8"))
    gates = {
        "G1_INPUT_LOCK_NO_REDOWNLOAD": {"status": "PASS",
            "evidence": "s0_input_lock.json 逐位复核 + V9 收尾复核；登记源无换版"},
        "G2_STRUCTURED_EXTRACTION": {"status": "PASS",
            "evidence": "XCAF 8 语义组/389 实体；vendor_group_census.json"},
        "G3_GROUP_LINK_REGISTRATION": {"status": "PASS_WITH_CHAIN_DERIVED_HOLD",
            "evidence": "6 组 DIRECT(nn 1.6-2.5mm)+G05/G08 链推导(散布≤3.94mm)；"
                         "旋转一致性 7.3e-6"},
        "G4_DESKTOP_CLASSIFICATION": {"status": "PASS",
            "evidence": "base_classification.json：删 01_BASE_Plate(1 实体)/保留 69；"
                         "用户裁决表逐项执行"},
        "G5_ADAPTER_CLOCKING_DECISION": {"status": "PASS_PENDING_RATIFICATION",
            "evidence": "adapter_clocking.json 25°（q1 裕度 15.86°）；"
                         "使能 V1 全宽走廊 PASS；人工批准待定"},
        "G6_REPOSE_AND_STATES": {"status": "PASS",
            "evidence": "repose_report.json 内部一致性≤3.94mm；5 态双文件绑定+2 null；"
                         "单一表示纪律 V11"},
        "G7_MACHINE_VALIDATION": {"status": "PASS_WITH_RECORDED_FAIL",
            "evidence": f"{mc['summary']}；V12 第一版 3 侵入→支承 V2 清零；"
                         "V14（自审补课）28 处模块-主结构互穿 FAIL_RECORDED；"
                         "120 MC1 负发现保留"},
        "G8_ADVERSARIAL_REVIEW": {"status": "PARTIAL_SELF_AUDIT_ONLY",
            "evidence": f"独立评审 Workflow 五代理全部因会话用量上限失败（零产出）；"
                         f"改由交付者自审：{concl}（HIGH {hi}/MEDIUM {med}/LOW {lo}）；"
                         "reviews/SELF_AUDIT_REVIEW.md；独立评审待补（H8）"},
    }
    verdict = {
        "verdict_id": "V22_B601_VENDOR_CAD_INTEGRATION_03_MACHINE_VERDICT",
        "generated_utc": NOW,
        "gates": gates,
        "machine_checks_summary": mc["summary"],
        "stow_vector_v2": {"status": v2["STOW_VECTOR_STATUS"],
                            "q_deg": v2["q_deg"],
                            "adapter_clock_deg": v2["adapter_clock_deg"]},
        "engineering_holds": [
            "H1 收拢向量 v2=CANDIDATE_HOLD；25° 时钟角=DESIGN_PROPOSAL_PENDING_HUMAN_RATIFICATION",
            "H2 STOW_CONTACT_QUALIFICATION=HOLD（垫/预紧/HDRM 型号/绑带未定）",
            "H3 鞍座塔高 118-138mm 长细比/频率未评估",
            "H4 G05/G08 CHAIN_DERIVED（±3.9mm）；正式采信前厂商图纸复核",
            "H5 252MB/位姿 STEP 膨胀；XCAF 实例化瘦身另行任务",
            "H6 Q0 展开位形带 25° 时钟；工作空间偏转任务面影响未评估",
            "H7 视图=80k 三角子采样渲染；几何裁决不依赖视图",
            "H8 独立对抗评审未完成（用量上限）；现有为自审，独立性等级更低，须补做",
            "H9 收拢态 Z 包络未定义（F5）：臂高出整星盒顶 ~246mm，无判据可判合规",
            "H10 模块-主结构接口未裁决（V14 28 处互穿待工程分模）"],
        "self_audit_corrections": {
            "HIGH-1": "25° 时钟角'宽度必要性'论证被证伪→改写为高度收益（-155mm）；"
                       "adapter_clocking.json 保留 retracted_rationale 全文",
            "HIGH-2": "F5 收拢 Z 包络缺口登记为 UNKNOWN_HOLD",
            "MEDIUM-1": "补 V14 模块-主结构检查（FAIL_RECORDED 如实入档）",
            "MEDIUM-2": "设计记录与报告同步改写",
            "LOW-1..3": "412.45/412.47 口径注明、nn 区间改 1.57-2.50、独立性声明"},
        "review": {"file": "reviews/SELF_AUDIT_REVIEW.md",
                    "independence": "SELF_AUDIT_NOT_INDEPENDENT",
                    "independent_review_status": "FAILED_SESSION_LIMIT_PENDING_RERUN",
                    "conclusion": concl,
                    "findings": {"HIGH": hi, "MEDIUM": med, "LOW": lo}},
        "final_verdict": "B601_VENDOR_CAD_INTEGRATION_03_ACCEPT_WITH_ENGINEERING_HOLDS",
        "review_status": "PENDING_HUMAN_REVIEW",
        "next_stage_authorized": False,
        "prohibitions": ["不据此升级科学结论", "不提交 Git（需另行人工授权）",
                          "CANDIDATE_HOLD 角度不得写成 accepted joint vector",
                          "厂商几何不得对外分发（E3）"]}
    (HERE / "validation/machine_verdict.json").write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")

    entries = {}
    for p in sorted(HERE.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(HERE).as_posix()
        if rel == "validation/artifact_manifest.json":
            continue
        entries[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    (HERE / "validation/artifact_manifest.json").write_text(
        json.dumps({"manifest_id": "VENDORCAD03_ARTIFACT_MANIFEST",
                     "generated_utc": NOW, "file_count": len(entries),
                     "files": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("verdict:", verdict["final_verdict"], "| files:", len(entries))


if __name__ == "__main__":
    main()
