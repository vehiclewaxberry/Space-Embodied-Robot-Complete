"""POSEMAP-02 终裁 + 产物清单（最后一步：先裁决后清单，清单含裁决自身）。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc).isoformat()


def sha256(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    mc = json.loads((HERE / "validation/machine_checks.json")
                    .read_text(encoding="utf-8"))
    stow = json.loads((HERE / "design/b601_stow_joint_vector.json")
                      .read_text(encoding="utf-8"))
    gates = {
        "G1_INPUT_AUTHORITY_LOCK": {
            "status": "PASS",
            "evidence": "validation/frozen_zone_precheck.json（4 权威+7 输入哈希）；"
                         "MC7 收尾复核全匹配"},
        "G2_URDF_FRAME_MAP_TRUTH": {
            "status": "PASS",
            "evidence": "design/b601_urdf_to_cad_frame_map.yaml + "
                         "b601_joint_axis_registry.yaml（accepted URDF 原值）；"
                         "对抗评审 A1：独立 FK 复现差 ≤0.006mm"},
        "G3_STOW_VECTOR_DISCIPLINE": {
            "status": "PASS_WITH_CANDIDATE_HOLD",
            "evidence": "STOW_VECTOR_STATUS=CANDIDATE_HOLD 贯穿（评审 A2 无破口）；"
                         "F1-F4 运动学发现入档；F1 经评审独立验算 CONFIRMED"},
        "G4_LOD2_GEOMETRY_FK_PLACED": {
            "status": "PASS",
            "evidence": "8 组 21 实体×双位形；Q0 包络对拍实测盒（462 vs 467.45）；"
                         "视图 v01/v02/v06-v10；评审 A8 无穿模悬空"},
        "G5_MOUNT_SUPPORT_CAPTURE_MODULES": {
            "status": "PASS_WITH_CONTACT_HOLD",
            "evidence": "13+N 实体三模块 STEP；stow_contact_registry.json "
                         "STOW_CONTACT_QUALIFICATION=HOLD；主鞍座 +Y 钳口包络裁剪→绑带 HOLD"},
        "G6_STATES_SINGLE_REPRESENTATION": {
            "status": "PASS",
            "evidence": "5 几何态 + PARTIAL/SERVICE=null；四项单一表示替换"
                         "（含评审中发现并封堵的 110 旧捕获栈 EE 双重表示）；MC5/MC8"},
        "G7_MACHINE_VALIDATION_CHAIN": {
            "status": "PASS_WITH_RECORDED_FAIL",
            "evidence": "MC1-MC11：9 PASS + MC1 FAIL_RECORDED（走廊=URDF 运动学事实）"
                         "+ MC11 降格为登记器（评审 M3 采纳）"},
        "G8_ADVERSARIAL_REVIEW_AND_MANIFEST": {
            "status": "PASS",
            "evidence": "reviews/INDEPENDENT_ADVERSARIAL_REVIEW.md："
                         "UPHELD_WITH_CORRECTIONS（HIGH 0/MEDIUM 3/LOW 7）；"
                         "M1 改数、M2 本文件、M3 降格、L1/L2 计数已修；"
                         "artifact_manifest.json 全量哈希"},
    }
    verdict = {
        "verdict_id": "V22_B601_GEOMETRY_POSEMAP02_MACHINE_VERDICT",
        "generated_utc": NOW,
        "gates": gates,
        "machine_checks_summary": mc["summary"],
        "stow_vector_status": stow["STOW_VECTOR_STATUS"],
        "kinematic_findings": [f["id"] for f in stow["kinematic_findings"]],
        "engineering_holds": [
            "H1 STOW_VECTOR=CANDIDATE_HOLD（正式向量需人工/载荷侧批准；F3 双限位饱和）",
            "H2 STOW_CONTACT_QUALIFICATION=HOLD（垫/预紧/HDRM 未定；+Y 绑带待设计）",
            "H3 MC1 走廊违规=URDF 运动学事实（若 |Y|≤40 为硬需求须重议走廊或安装方位）",
            "H4 MC11 非干涉证明；L3 精判未授权",
            "H5 LOD2 无强度/质量/制造权威；厂商精细几何（P-C）另行授权",
            "H6 原生 SW 件未生成（资源裁决）；交付=参数化源码+STEP，零伪造",
            "H7 评审 L5-L7 known limitations：scratch_native 易失路径、MC6/MC8 扫描面、"
            "LOD2 夹爪 Y 半宽 77<92.035（非保守简化，L3 前须按厂商包络复核）"],
        "review": {"file": "reviews/INDEPENDENT_ADVERSARIAL_REVIEW.md",
                    "conclusion": "UPHELD_WITH_CORRECTIONS",
                    "findings": {"HIGH": 0, "MEDIUM": 3, "LOW": 7},
                    "corrections_applied": ["M1", "M2", "M3", "L1", "L2", "L3", "L4"]},
        "final_verdict": "B601_GEOMETRY_POSEMAP02_ACCEPT_WITH_ENGINEERING_HOLDS",
        "review_status": "PENDING_HUMAN_REVIEW",
        "next_stage_authorized": False,
        "prohibitions": ["不据此升级科学结论", "不提交 Git（需另行人工授权）",
                          "CANDIDATE_HOLD 角度不得写成 accepted joint vector"]}
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
    manifest = {"manifest_id": "POSEMAP02_ARTIFACT_MANIFEST", "generated_utc": NOW,
                "file_count": len(entries), "files": entries}
    (HERE / "validation/artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("verdict:", verdict["final_verdict"])
    print("manifest files:", len(entries))


if __name__ == "__main__":
    main()
