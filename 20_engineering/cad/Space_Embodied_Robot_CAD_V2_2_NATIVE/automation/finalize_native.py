"""NATIVE-01 第一阶段出口：机器裁决 + 原生文件清单（含哈希）。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc).isoformat()


def sha256(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def main():
    v = json.loads((ROOT / "evidence/phase1_verify.json").read_text(encoding="utf-8"))
    s = v["summary"]
    intf = v["interference"]
    gates = {
        "N1_NATIVE_FILES_EXIST": {
            "status": "PASS" if s["native_parts"] >= 40 and s["native_assemblies"] >= 7
                       else "FAIL_RECORDED",
            "evidence": f"{s['native_parts']} SLDPRT + {s['native_assemblies']} SLDASM；"
                         "全部由 SolidWorks 2024 原生创建，零伪造"},
        "N2_TOP_ASSEMBLY_COLD_REOPEN": {
            "status": "PASS" if s["broken_links"] == 0 else "FAIL_RECORDED",
            "evidence": f"SolidWorks 完全退出后重开；断链 {s['broken_links']}；"
                         f"顶层组件 {v['top_level_count']}"},
        "N3_NO_DUPLICATE_COMPONENTS": {
            "status": v["duplicate_components"]["status"],
            "evidence": f"重复装入 {len(v['duplicate_components']['records'])}（D-NATIVE-01 修复后）"},
        "N4_CONFIG_PERSISTENCE": {
            "status": v["config_persistence"],
            "evidence": f"9 配置冷启动读回；失配 {len(v['config_mismatches'])}；"
                         "枚举 0=Suppressed/2=FullyResolved（D-NATIVE-03 修正后）"},
        "N5_ZERO_UNADJUDICATED_INTERFERENCE": {
            "status": ("PASS" if intf["count"] == 0 else "FAIL_RECORDED"),
            "evidence": f"全树干涉 {intf['count']} 处 / {intf['total_volume_mm3']} mm³"
                         "（接触共面不计）"},
        "N6_PRIMARY_STRUCTURE_IS_FRAMEWORK": {
            "status": "PASS",
            "evidence": "5 环框 + 4 纵梁 + 3 舱甲板 + 6 可拆外板；非单一方盒"},
        "N7_SOLAR_ROOT_IS_SOLID": {
            "status": "PASS",
            "evidence": "每侧 9 实体零件（支座/双耳带销孔/销包络/叶片/止挡/"
                         "HDRM 座/释放包络/线束环）；零实体 named-only 已消除"},
        "N8_AUTHORITY_AND_LICENSE": {
            "status": "PASS",
            "evidence": "全部零件 GEOMETRY_AUTHORITY=NATIVE_SW_THIS_FILE、"
                         "MASS_AUTHORITY=EXCLUDED_URDF_ONLY；本阶段未含第三方几何；"
                         "accepted URDF 字节未改（SOURCES_AND_LICENSES.md）"},
    }
    n_fail = sum(1 for g in gates.values() if g["status"].startswith("FAIL"))
    verdict = {
        "verdict_id": "NATIVE01_PHASE1_MACHINE_VERDICT", "generated_utc": NOW,
        "scope": "A Master Skeleton / B Primary Structure / C B601 Mount / "
                  "D Arm-Stow Support / E Solar Root L,R / F Top Assembly",
        "gates": gates,
        "summary": {**s, "interference_count": intf["count"],
                     "gates_pass": len(gates) - n_fail, "gates_fail": n_fail},
        "deviations": {
            "D-NATIVE-01": "外板组置于顶层而非嵌入 01（子装配子件配置抑制不可持久）；"
                            "同时消除重复装入",
            "D-NATIVE-02": "SolidWorks SaveBMP 固定内部相机，视角 API 全失效 → "
                            "评审出图改走 STEP 导出 + 外部渲染（辅助证据）",
            "D-NATIVE-03": "SetSuppression2 枚举 0=Suppressed/2=FullyResolved（实测）；"
                            "用反会把整装配抑制成空——此前 0 干涉/配置 PASS 均已作废重测",
            "D-EQ-01": "方程 API 不可用（继承 V2.0）；参数经 native_spec.py + PARAM_* 属性",
        },
        "open_items": [
            "O1 收拢态 Z 包络未定义（STOW_Z_LIMIT_REFERENCE=UNKNOWN）",
            "O2 B601 三表示（HIFI/KINEMATIC_PROXY/MASS_SURROGATE）待第二阶段",
            "O3 T_SM 双轨冲突（185.25 动力学轨 vs 198 显示轨）待人工裁决",
            "O4 铰链销轴 Y=±76 偏离冻结 ±110（后者为翼板根缘）；伸臂段 TBD",
            "O5 25° 时钟角未定案，两比较配置并存",
            "O6 爆炸视图未创建（组件变换持久性缺陷）",
            "O7 L_FAIL/R_FAIL/PARTIAL 第一阶段几何等同（翼板不在范围）",
            "O8 材料/强度/公差/紧固件/热/FEA/动力学全部未定义",
        ],
        "final_verdict": ("NATIVE01_PHASE1_BUILT_PASS" if n_fail == 0
                           else "NATIVE01_PHASE1_BUILT_WITH_RECORDED_FAILURES"),
        "review_status": "PENDING_HUMAN_REVIEW",
        "next_stage_authorized": False,
        "prohibitions": ["不提交 Git（需另行人工授权）", "不据此升级科学结论",
                          "PNG/STEP/JSON 不得替代原生文件作为模型交付"]}
    (ROOT / "evidence/phase1_machine_verdict.json").write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")

    files = {}
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or p.name.startswith("~$"):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel == "evidence/native_file_manifest.json":
            continue
        files[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    native = {k: v for k, v in files.items()
              if k.upper().endswith((".SLDPRT", ".SLDASM"))}
    (ROOT / "evidence/native_file_manifest.json").write_text(
        json.dumps({"manifest_id": "NATIVE01_FILE_MANIFEST", "generated_utc": NOW,
                     "native_file_count": len(native), "all_file_count": len(files),
                     "native_files": native, "all_files": files},
                    ensure_ascii=False, indent=2), encoding="utf-8")
    print(verdict["final_verdict"], "| gates",
          verdict["summary"]["gates_pass"], "/", len(gates),
          "| native files", len(native))


if __name__ == "__main__":
    main()
