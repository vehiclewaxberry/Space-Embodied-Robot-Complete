"""B3-06a B601 视觉臂：10 link q0 轴对齐包络代理 → SV2_B601_Visual_Arm.SLDASM。

拓扑冻结 10 links / 9 joints；accepted URDF/STL 只读（11/11 哈希已核）；
表达=保守包络代理（A3 授权表达方式），非精确供应商几何；不产生质量/惯量。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, connect,
                            insert_components_identity, new_document,
                            rebuild_or_fail, save_as, set_custom_properties)
from b3_lib.sw_part_factory import build_x_extruded_part

BOXES = json.loads((V2_ROOT / "evidence/b3_06/b601_q0_boxes.json").read_text(encoding="utf-8"))
MOD = V2_ROOT / "06_B601_Visual_Arm"
PARTS_DIR = MOD / "parts"
ASM_PATH = MOD / "SV2_B601_Visual_Arm.SLDASM"

LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6",
         "gripper_link", "gripper_left", "gripper_right"]


def props_for(i, link):
    return {
        "OBJECT_ID": f"V2-B601-{i:02d}", "SYSTEM_OWNER": "b601_visual_arm",
        "PARENT_ID": "SV2_B601_Visual_Arm",
        "STRUCTURE_CLASS": "VISUAL_PROXY",
        "REPRESENTATION_LAYER": "AXIS_ALIGNED_BBOX_PROXY_Q0",
        "EVIDENCE_STATE": "EVIDENCE_BOUND",
        "SOURCE_REFERENCE": ("arm_b601_v1.urdf + meshes_b601_gripper/"
                             f"{link}.STL (hash 11/11 MATCH, b3_00)"),
        "FRAME_ID": "CS_A0", "INTERFACE_IDS": "IF-RM-002",
        "MASS_OWNER": "b601_urdf_owner_NOT_from_visual",
        "NO_DYNAMICS_USE": "true", "MANUFACTURING_AUTHORITY": "NONE",
        "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": ("conservative_envelope_not_exact_vendor_geometry;"
                        "q_zero_pose_only;no_mass_no_inertia_from_visual"),
        "URDF_LINK": link,
        "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;URDF_roundtrip;"
                             "contact_models",
    }


def main():
    log = BuildLog("b3_06_b601")
    if ASM_PATH.exists():
        log.fail("SV2_B601_Visual_Arm.SLDASM 已存在，禁止无条件覆盖")
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    sw = connect(log)
    sw.CloseAllDocuments(True)
    for i, link in enumerate(LINKS):
        box = BOXES["links"][link]["s_box_mm"]
        (x0, y0, z0), (x1, y1, z1) = box
        yc, zc = (y0 + y1) / 2, (z0 + z1) / 2
        hy, hz = (y1 - y0) / 2, (z1 - z0) / 2
        build_x_extruded_part(
            sw, log, PARTS_DIR / f"B601_{link}_bbox_q0.SLDPRT",
            f"B601_{link}_bbox_q0", [(yc, zc, hy, hz)], [x0, x1],
            props_for(i, link))
    asm_model = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, asm_model,
                               [PARTS_DIR / f"B601_{k}_bbox_q0.SLDPRT"
                                for k in LINKS])
    set_custom_properties(asm_model, log, {
        "OBJECT_ID": "V2-B601-000", "SYSTEM_OWNER": "b601_visual_arm",
        "PARENT_ID": "Spacecraft_Service_Vehicle_V2_0",
        "STRUCTURE_CLASS": "VISUAL_PROXY",
        "REPRESENTATION_LAYER": "AXIS_ALIGNED_BBOX_PROXY_Q0",
        "EVIDENCE_STATE": "EVIDENCE_BOUND",
        "SOURCE_REFERENCE": "accepted arm_b601_v1 (10_links_9_joints, READ_ONLY)",
        "FRAME_ID": "CS_A0", "INTERFACE_IDS": "IF-RM-002",
        "MASS_OWNER": "b601_urdf_owner_NOT_from_visual",
        "NO_DYNAMICS_USE": "true", "MANUFACTURING_AUTHORITY": "NONE",
        "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": "topology_frozen_10L9J;bbox_proxy_only;q_zero",
        "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;URDF_roundtrip"})
    rebuild_or_fail(asm_model, log, "b601_asm")
    save_as(asm_model, log, ASM_PATH)
    sw.CloseAllDocuments(True)

    ev = json.loads((V2_ROOT / "evidence/b3_00/B3_entry_verification.json")
                    .read_text(encoding="utf-8"))
    b601_rows = ev["checks"]["B601_ASSET_HASHES"]["rows"]
    reg = {
        "register_id": "SV2_B601_SOURCE_HASH_AND_TOPOLOGY",
        "topology": "10_links_9_joints_frozen",
        "links": LINKS,
        "joints": ["joint1..joint6 revolute", "gripper_joint fixed",
                   "gripper_joint1/2 prismatic locked capture-ready"],
        "pose": "q_zero",
        "representation": "axis_aligned_bbox_proxy_per_link_in_S_frame",
        "insertion_contract": "A0 == M (T_MA0 identity), T_SM = [185.25,0,0] R_y(+90)",
        "source_hashes_sha256": {r["relative_path"]: r["sha256"]
                                 for r in b601_rows},
        "hash_verification": "evidence/b3_00/B3_entry_verification.json (11/11 MATCH)",
        "box_derivation": "evidence/b3_06/b601_q0_boxes.json",
        "urdf_modified": False,
        "vendor_step_imported": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (MOD / "source_hash_and_topology_register.yaml").write_text(
        yaml.safe_dump(reg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    log.event("B3_06_B601_DONE", links=len(LINKS))
    print("B601_MODULE_BUILD_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
