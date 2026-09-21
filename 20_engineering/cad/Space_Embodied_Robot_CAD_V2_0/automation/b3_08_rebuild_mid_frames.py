"""B3-08 中框重建脚本（复现链补档——评审 MED 残留整改）。

当时以内联脚本执行（build_logs/b3_08_rebuild_mid_frames.jsonl 为原始日志），
本文件为其等价可复现固化版：删除并重建 FRM_REAR_MID / FRM_MID_FRONT 为
径向内缩条（外缘 110.15=侧板内面，D-V2-04）。同名重建，装配引用按文件名解析不断。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import B3FailClosed, BuildLog, V2_ROOT, connect
from b3_lib.sw_part_factory import build_x_extruded_part

HIN, OUT_R = 98.15, 110.15
C, H = (HIN + OUT_R) / 2, (OUT_R - HIN) / 2
RECTS = [(0.0, C, HIN, H), (0.0, -C, HIN, H), (C, 0.0, H, HIN), (-C, 0.0, H, HIN)]
CLAIM = ("display_topology_only;section_material_joints_UNKNOWN_BLOCKED;"
         "NO_STRENGTH_CLAIM;radial_outer_inset_to_panel_inner_110.15_D-V2-04")


def props(oid, lp, ifc=""):
    return {"OBJECT_ID": oid, "SYSTEM_OWNER": "primary_structure",
            "PARENT_ID": "SV2_Primary_Structure",
            "STRUCTURE_CLASS": "PRIMARY_PROPOSAL",
            "REPRESENTATION_LAYER": "SYSTEM_MECHANICAL_DISPLAY",
            "EVIDENCE_STATE": "DESIGN_PROPOSAL",
            "SOURCE_REFERENCE": "b3_build_spec.yaml structure_display_proposal; "
                                f"load_path:{lp}",
            "FRAME_ID": "CS_S", "INTERFACE_IDS": ifc,
            "MASS_OWNER": "NONE_DISPLAY_ONLY", "NO_DYNAMICS_USE": "true",
            "MANUFACTURING_AUTHORITY": "NONE",
            "EXECUTION_AUTHORITY": "DISPLAY_ONLY", "CLAIM_LIMIT": CLAIM,
            "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;manufacturing;"
                                 "strength_claims"}


def main():
    log = BuildLog("b3_08_rebuild_mid_frames")
    sw = connect(log)
    sw.CloseAllDocuments(True)
    for nm, span, oid, lp, ifc in [
        ("FRM_REAR_MID", [-62.75, -50.75], "V2-STR-007", "LP_REAR_MID_FRAME",
         "IF-SA-L;IF-SA-R"),
        ("FRM_MID_FRONT", [50.75, 62.75], "V2-STR-008", "LP_MID_FRONT_FRAME", "")]:
        p = V2_ROOT / f"01_Primary_Structure/parts/{nm}.SLDPRT"
        if p.exists():
            os.remove(p)
            log.event("OLD_FILE_REMOVED", part=nm)
        build_x_extruded_part(sw, log, p, nm, RECTS, span, props(oid, lp, ifc))
    sw.CloseAllDocuments(True)
    print("MID_FRAMES_REBUILT_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
