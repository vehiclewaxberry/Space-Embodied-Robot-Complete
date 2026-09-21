"""B3-08b 范围化干涉检查：每个具名配置一份绑定报告（fail-open 禁止）。

规则：报告绑定 配置+B601 q0+显示状态+参与组件；不把单配置"无干涉"外推为全局安全；
V1 十处 q0 静态干涉为记录级继承负结果，V2 bbox 代理的结果差异不构成消解。
预期表达伪影：B601 相邻 link 的保守 bbox 在关节区互相重叠——如实记录并标注
representation_artifact_candidate，不隐藏、不 suppress 消除。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, activate_configuration,
                            cast, connect, get_com_member, open_document,
                            rebuild_or_fail)

TOP = V2_ROOT / "Assembly/Spacecraft_Service_Vehicle_V2_0.SLDASM"
EVID = V2_ROOT / "evidence/b3_08"
CONFIGS = ["STRUCTURAL_REVIEW", "SERVICE_ACCESS_REVIEW", "DEPLOYED_REFERENCE_Q0",
           "STOWED_PROPOSAL", "SAFE_DISPLAY_PROPOSAL", "EVIDENCE_STATE_REVIEW"]


def run_config(model, log, cname):
    activate_configuration(model, log, cname)
    rebuild_or_fail(model, log, f"cfg_{cname}")
    asm = cast(model, "IAssemblyDoc")
    idm = get_com_member(asm, "InterferenceDetectionManager")
    idm.TreatCoincidenceAsInterference = False
    idm.TreatSubAssembliesAsComponents = False
    idm.IncludeMultibodyPartInterferences = True
    ints = idm.GetInterferences
    if callable(ints):
        ints = ints()
    rows = []
    for it in ints or []:
        itf = cast(it, "IInterference")
        comps = get_com_member(itf, "Components")
        names = []
        for c in comps or []:
            names.append(cast(c, "IComponent2").Name2)
        vol = get_com_member(itf, "Volume")
        arm_pair = sum(1 for n in names if "B601_" in n) == 2
        rows.append({"components": names, "volume_m3": float(vol),
                     "classification": ("representation_artifact_candidate_"
                                        "bbox_proxy_joint_overlap" if arm_pair
                                        else "UNCLASSIFIED_REVIEW_REQUIRED")})
    try:
        idm.Done()
    except Exception:
        pass
    active_comps = []
    for c in asm.GetComponents(False) or []:
        c2 = cast(c, "IComponent2")
        active_comps.append({"name": c2.Name2,
                             "suppressed": bool(get_com_member(c2, "IsSuppressed"))})
    return {"configuration": cname, "b601_pose": "q_zero_frozen",
            "display_scope": "top_level_components_resolved",
            "participants": active_comps,
            "interference_count": len(rows), "interferences": rows,
            "claim_limit": ("scoped_to_this_configuration_and_pose_only;"
                            "no_global_collision_safety_claim;"
                            "bbox_proxy_conservative_representation")}


def main():
    log = BuildLog("b3_08_interference")
    EVID.mkdir(parents=True, exist_ok=True)
    sw = connect(log)
    sw.CloseAllDocuments(True)
    model = open_document(sw, log, TOP)
    index = {"generated_utc": datetime.now(timezone.utc).isoformat(),
             "inherited_negative_results": {
                 "id": "DEPLOYED_REFERENCE_Q0_STATIC_INTERFERENCE",
                 "count": 10, "classification": "NEGATIVE_RESULT",
                 "global_collision_safety": "BLOCKED",
                 "origin": "V1.0 evidence (32/32 frozen)",
                 "v2_note": ("V2 采用 bbox 代理表达，几何差异导致的结果差异"
                             "不构成对 V1 负结果的消解或改写")},
             "reports": {}}
    for cname in CONFIGS:
        rep = run_config(model, log, cname)
        (EVID / f"interference_{cname}.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        index["reports"][cname] = {"count": rep["interference_count"],
                                   "file": f"interference_{cname}.json"}
        log.event("INTERFERENCE_SCOPED", config=cname,
                  count=rep["interference_count"])
    activate_configuration(model, log, "DEPLOYED_REFERENCE_Q0")
    sw.CloseAllDocuments(True)
    (EVID / "interference_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    log.event("B3_08B_DONE")
    print("INTERFERENCE_SCOPED_OK",
          json.dumps({k: v["count"] for k, v in index["reports"].items()}))


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
