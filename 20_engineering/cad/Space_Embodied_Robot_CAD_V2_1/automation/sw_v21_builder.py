"""B4-1 统一构建器：骨架/主结构/甲板/分段面板/mount/太阳翼/顶装（分阶段可重入）。

用法：python sw_v21_builder.py <stage>
  skeleton | frame | decks | panels | mount | solar | top | all
铁律落地：SA 机构件零实体 named-only（H5）；V2.0 只读（B601 子装配跨目录引用原样继承）；
全件 15 属性 + STRUCT_CLASS；参数权威=System_Equations_V2_1.txt（PARAM_* 冗余）。
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, cast, connect,
                            create_offset_plane, get_com_member,
                            insert_components_identity, new_document,
                            rebuild_or_fail, rename_last_feature, save_as,
                            set_custom_properties)
import b3_lib.sw_core as core
from b3_lib.sw_part_factory import (RIGHT, TOP, FRONT, build_face_panel_part,
                                    build_x_extruded_part, _m)

V21 = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_1")
core.V2_ROOT = V21          # 日志与证据落 V2.1
core.LOG_DIR = V21 / "evidence" / "build_logs"
V20 = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_0")
SPEC = yaml.safe_load((V21 / "automation/b4_1_build_spec.yaml").read_text(encoding="utf-8"))

HB, NW = 113.15, 15.0
HIN = HB - NW


def props(oid, owner, sclass, evidence, claim, parent, frame="CS_S", ifaces=""):
    return {"OBJECT_ID": oid, "SYSTEM_OWNER": owner, "PARENT_ID": parent,
            "STRUCT_CLASS": sclass, "STRUCTURE_CLASS": sclass,
            "REPRESENTATION_LAYER": "SYSTEM_MECHANICAL_DISPLAY",
            "EVIDENCE_STATE": evidence,
            "SOURCE_REFERENCE": "b4_1_build_spec.yaml + human_conflict_rulings.yaml",
            "FRAME_ID": frame, "INTERFACE_IDS": ifaces,
            "MASS_OWNER": "NONE_DISPLAY_ONLY", "NO_DYNAMICS_USE": "true",
            "MANUFACTURING_AUTHORITY": "NONE", "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
            "CLAIM_LIMIT": claim,
            "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;manufacturing;strength_claims"}


CLAIM = "display_topology_only;sections_UNKNOWN;NO_STRENGTH_CLAIM;NO_DIRECT_SCALE"
PARAMS = {"BUS_L": 340.5, "BUS_W": 226.3, "BUS_H": 226.3, "FRAME_FRONT_X": 170.25,
          "FRAME_MID1_X": 56.75, "FRAME_MID2_X": -56.75, "FRAME_REAR_X": -170.25,
          "LONGERON_OFFSET_Y": 105.65, "LONGERON_OFFSET_Z": 105.65,
          "ARM_MOUNT_X": 185.25, "ARM_MOUNT_PLATE_SIZE": 160.0,
          "ARM_BOSS_D": 100.0,
          "PANEL_L": 200.0, "PANEL_W": 227.0, "PANEL_T": 6.0,
          "PANEL_ROOT_Y": 113.15, "SIDE_PANEL_SPLIT_X": 56.75,
          "STOW_OVERHANG_Z": -86.85}


def add_param_props(model, log):
    mgr = model.Extension.CustomPropertyManager("")
    for k, v in PARAMS.items():
        mgr.Add3(f"PARAM_{k}", 30, str(v), 2)
    for k in ("PANEL_HINGE_AXIS_Z", "PANEL_DEPLOY_ANGLE", "SA_ROOT_BRACKET_ENVELOPE",
              "HINGE_BLOCK_ENVELOPE", "HDRM_ENVELOPE", "SERVICE_PANEL_GAP",
              "HARNESS_CORRIDOR_W", "MAINTENANCE_CLEARANCE"):
        mgr.Add3(f"PARAM_{k}", 30, "UNKNOWN", 2)
    log.event("PARAM_PROPS_SET", frozen=len(PARAMS), unknown=8)


def zero_solid_ref_part(sw, log, out, name, anchor_mm, extra_props, plane=TOP,
                        plane_off_key=1):
    """零实体 owner 参考件：站位面+具名锚点+属性（H5 机构件表达）。"""
    if out.exists():
        model = core.open_document(sw, log, out)
        set_custom_properties(model, log, extra_props)
        core.save(model, log)
        sw.CloseAllDocuments(True)
        log.event("ZERO_SOLID_REF_PROPS_REFRESHED", part=out.name)
        return
    model = new_document(sw, log, "part")
    off = anchor_mm[plane_off_key]
    create_offset_plane(model, log, plane, off, f"PLN_{name}", flip=off < 0)
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(f"PLN_{name}", "PLANE", 0, 0, 0, False, 0, None, 0):
        log.fail("选择锚面失败", part=name)
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreatePoint(0.0, 0.0, 0.0)
    sk.InsertSketch(True)
    rename_last_feature(model, log, f"SK_{name}_ANCHOR")
    bodies = get_com_member(cast(model, "IPartDoc"), "GetBodies2", 0, True)
    if isinstance(bodies, tuple) and bodies:
        log.fail("零实体件出现实体", part=name)
    set_custom_properties(model, log, extra_props)
    rebuild_or_fail(model, log, name)
    save_as(model, log, out)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("ZERO_SOLID_REF_BUILT", part=name)


def stage_skeleton(sw, log):
    out = V21 / "00_Master_Skeleton/Master_Skeleton_V2_1.SLDPRT"
    if out.exists():
        model = core.open_document(sw, log, out)
        add_param_props(model, log)
        rebuild_or_fail(model, log, "skeleton_parameter_mirror_refresh")
        core.save(model, log)
        sw.CloseAllDocuments(True)
        log.event("SKELETON_PARAM_MIRROR_REFRESHED", what=out.name,
                  frozen=len(PARAMS), unknown=8)
        return
    model = new_document(sw, log, "part")
    create_offset_plane(model, log, RIGHT, -170.25, "PLANE_REAR_BODY_FACE", flip=True)
    create_offset_plane(model, log, RIGHT, -56.75, "PLANE_REAR_MID_BOUNDARY", flip=True)
    create_offset_plane(model, log, RIGHT, 56.75, "PLANE_MID_FRONT_BOUNDARY")
    create_offset_plane(model, log, RIGHT, 170.25, "PLANE_TASK_FACE")
    create_offset_plane(model, log, RIGHT, 185.25, "PLANE_MOUNT_M")
    create_offset_plane(model, log, TOP, 113.15, "PLANE_SOLAR_ROOT_L")
    create_offset_plane(model, log, TOP, -113.15, "PLANE_SOLAR_ROOT_R", flip=True)
    create_offset_plane(model, log, RIGHT, 56.75, "PLANE_SIDE_PANEL_SPLIT")
    create_offset_plane(model, log, FRONT, -113.15, "PLANE_STOW_OVERHANG_TOPEDGE",
                        flip=True)
    sk = model.SketchManager
    sk.Insert3DSketch(True)
    hx, hy, hz = _m(170.25), _m(113.15), _m(113.15)
    c = [(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    for a, b in [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7),
                 (0, 4), (1, 5), (2, 6), (3, 7)]:
        sk.CreateLine(*c[a], *c[b])
    sk.Insert3DSketch(True)
    rename_last_feature(model, log, "SK3D_BODY_ENVELOPE")
    # 节点垫站位锚点（C2）与收拢外悬 keepout 线框
    sk.Insert3DSketch(True)
    for st in SPEC["primary_structure"]["node_pads"]["stations"]:
        x = _m(sum(st["x_span_mm"]) / 2)
        y = _m(sum(st["y_span_mm"]) / 2)
        z = _m(sum(st["z_span_mm"]) / 2)
        sk.CreatePoint(x, y, z)
    sk.Insert3DSketch(True)
    rename_last_feature(model, log, "SK3D_NODE_PAD_STATIONS")
    sk.Insert3DSketch(True)
    for ysign in (1, -1):
        y = _m(ysign * 116.15)
        for (x0, z0, x1, z1) in [(-170.25, -113.15, 56.75, -113.15),
                                 (-170.25, -200.0, 56.75, -200.0),
                                 (-170.25, -113.15, -170.25, -200.0),
                                 (56.75, -113.15, 56.75, -200.0)]:
            sk.CreateLine(_m(x0), y, _m(z0), _m(x1), y, _m(z1))
    sk.Insert3DSketch(True)
    rename_last_feature(model, log, "SK3D_STOW_OVERHANG_KEEPOUT")
    set_custom_properties(model, log, props(
        "V21-SKEL-000", "system_architecture", "REFERENCE", "EVIDENCE_BOUND",
        CLAIM + ";equations_authority=System_Equations_V2_1.txt",
        "Spacecraft_Service_Vehicle_V2_1"))
    add_param_props(model, log)
    rebuild_or_fail(model, log, "skeleton_v21")
    save_as(model, log, out)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("B4_1_01_SKELETON_DONE")


def stage_frame(sw, log):
    d = V21 / "01_Primary_Frame/parts"
    d.mkdir(parents=True, exist_ok=True)
    FR = [(0.0, 105.65, HIN, 7.5), (0.0, -105.65, HIN, 7.5),
          (105.65, 0.0, 7.5, HIN), (-105.65, 0.0, 7.5, HIN)]
    FR_INSET = [(0.0, 104.15, HIN, 6.0), (0.0, -104.15, HIN, 6.0),
                (104.15, 0.0, 6.0, HIN), (-104.15, 0.0, 6.0, HIN)]
    frames = [("FRM_FRONT_TASK", [158.25, 170.25], FR, "LP_FRONT_FRAME"),
              ("FRM_REAR_BOUNDARY", [-170.25, -158.25], FR, "LP_REAR_FRAME"),
              ("FRM_MID_FRONT", [50.75, 62.75], FR_INSET, "LP_MID_FRONT_FRAME"),
              ("FRM_REAR_MID", [-62.75, -50.75], FR_INSET, "LP_REAR_MID_FRAME")]
    i = 1
    for nm, span, rects, lp in frames:
        build_x_extruded_part(sw, log, d / f"{nm}.SLDPRT", nm, rects, span,
                              props(f"V21-STR-{i:03d}", "primary_structure",
                                    "LOAD_PATH_INTENT", "DESIGN_PROPOSAL",
                                    CLAIM + f";load_path:{lp}", "SV21_Primary_Frame"))
        i += 1
    for nm, yc, zc in [("LNG_PY_PZ", 105.65, 105.65), ("LNG_PY_NZ", 105.65, -105.65),
                       ("LNG_NY_PZ", -105.65, 105.65), ("LNG_NY_NZ", -105.65, -105.65)]:
        build_x_extruded_part(sw, log, d / f"{nm}.SLDPRT", nm,
                              [(yc, zc, 7.5, 7.5)], [-170.25, 170.25],
                              props(f"V21-STR-{i:03d}", "primary_structure",
                                    "LOAD_PATH_INTENT", "DESIGN_PROPOSAL",
                                    CLAIM + ";load_path:LP_LONGERON_SET",
                                    "SV21_Primary_Frame"))
        i += 1
    for st in SPEC["primary_structure"]["node_pads"]["stations"]:
        (y0, y1), (z0, z1) = st["y_span_mm"], st["z_span_mm"]
        build_x_extruded_part(sw, log, d / f"{st['id']}.SLDPRT", st["id"],
                              [((y0 + y1) / 2, (z0 + z1) / 2, (y1 - y0) / 2, (z1 - z0) / 2)],
                              st["x_span_mm"],
                              props(f"V21-STR-{i:03d}", "primary_structure",
                                    "LOAD_PATH_INTENT", "DESIGN_PROPOSAL",
                                    CLAIM + ";C2_ruling_node_pad;IF-SA 载荷唯一入点",
                                    "SV21_Primary_Frame", ifaces="IF-SA-L;IF-SA-R"))
        i += 1
    g = SPEC["primary_structure"]["front_gussets"]
    for k, cell in enumerate(g["cells"]):
        nm = f"GUSSET_FRONT_{k+1}"
        build_x_extruded_part(sw, log, d / f"{nm}.SLDPRT", nm,
                              [(cell["yc"], cell["zc"], cell["hy"], cell["hz"])],
                              g["x_span_mm"],
                              props(f"V21-STR-{i:03d}", "primary_structure",
                                    "LOAD_PATH_INTENT", "DESIGN_PROPOSAL",
                                    CLAIM + ";PS-03_扩散段角撑(条件冻结H6)",
                                    "SV21_Primary_Frame"))
        i += 1
    asm = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, asm, sorted(d.glob("*.SLDPRT")))
    set_custom_properties(asm, log, props("V21-STR-000", "primary_structure",
                                          "LOAD_PATH_INTENT", "DESIGN_PROPOSAL", CLAIM,
                                          "Spacecraft_Service_Vehicle_V2_1"))
    rebuild_or_fail(asm, log, "primary_frame_asm")
    save_as(asm, log, V21 / "01_Primary_Frame/SV21_Primary_Frame.SLDASM")
    sw.CloseAllDocuments(True)
    log.event("B4_1_02_FRAME_DONE")


def stage_decks(sw, log):
    d = V21 / "02_Equipment_Decks/parts"
    d.mkdir(parents=True, exist_ok=True)
    for nm, xc in [("DECK_REAR_MID", -56.75), ("DECK_MID_FRONT", 56.75)]:
        build_x_extruded_part(sw, log, d / f"{nm}.SLDPRT", nm,
                              [(0.0, 0.0, HIN, HIN)], [xc - 4, xc + 4],
                              props(f"V21-DK-{1 if xc<0 else 2:03d}", "primary_structure",
                                    "LOAD_PATH_INTENT_SHEAR_WEB", "DESIGN_PROPOSAL",
                                    CLAIM + ";C1_ruling:开口走规则3通道逐口登记",
                                    "SV21_Equipment_Decks"))
    asm = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, asm, sorted(d.glob("*.SLDPRT")))
    set_custom_properties(asm, log, props("V21-DK-000", "primary_structure",
                                          "LOAD_PATH_INTENT_SHEAR_WEB", "DESIGN_PROPOSAL",
                                          CLAIM, "Spacecraft_Service_Vehicle_V2_1"))
    rebuild_or_fail(asm, log, "decks_asm")
    save_as(asm, log, V21 / "02_Equipment_Decks/SV21_Equipment_Decks.SLDASM")
    sw.CloseAllDocuments(True)
    log.event("B4_1_02_DECKS_DONE")


def stage_panels(sw, log):
    d = V21 / "03_Removable_Panels/parts"
    d.mkdir(parents=True, exist_ok=True)
    pnl_claim = CLAIM + ";removable;may_close_primary_path=false"
    for nm, face in [("PNL_TOP", "+Z"), ("PNL_BOTTOM", "-Z")]:
        build_face_panel_part(sw, log, d / f"{nm}.SLDPRT", nm, face,
                              props(f"V21-PNL-{nm}", "secondary_structure",
                                    "NON_STRUCTURAL_PANEL", "DESIGN_PROPOSAL",
                                    pnl_claim, "SV21_Removable_Panels"))
    for seg in SPEC["primary_structure"]["segmented_side_panels"].values():
        if not isinstance(seg, dict) or "face" not in seg:
            continue
    segs = {k: v for k, v in SPEC["primary_structure"]["segmented_side_panels"].items()
            if isinstance(v, dict) and "face" in v}
    for nm, seg in segs.items():
        x0, x1 = seg["x_span_mm"]
        xc, hx = (x0 + x1) / 2, (x1 - x0) / 2
        sign = 1 if seg["face"] == "+Y" else -1
        build_x_extruded_part(sw, log, d / f"{nm}.SLDPRT", nm,
                              [(sign * 111.65, 0.0, 1.5, HIN)], [x0, x1],
                              props(f"V21-PNL-{nm}", "secondary_structure",
                                    "NON_STRUCTURAL_PANEL", "DESIGN_PROPOSAL",
                                    pnl_claim + ";C3_ruling_MID1_split;"
                                    + ("fwd_any_wing_state" if "FWD" in nm
                                       else "aft_DEPLOYED_or_SERVICE_only"),
                                    "SV21_Removable_Panels"))
    asm = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, asm, sorted(d.glob("*.SLDPRT")))
    set_custom_properties(asm, log, props("V21-PNL-000", "secondary_structure",
                                          "NON_STRUCTURAL_PANEL", "DESIGN_PROPOSAL",
                                          pnl_claim, "Spacecraft_Service_Vehicle_V2_1"))
    rebuild_or_fail(asm, log, "panels_asm")
    save_as(asm, log, V21 / "03_Removable_Panels/SV21_Removable_Panels.SLDASM")
    sw.CloseAllDocuments(True)
    log.event("B4_1_02_PANELS_DONE")


def stage_mount(sw, log):
    d = V21 / "05_Robot_Mount_Module/parts"
    d.mkdir(parents=True, exist_ok=True)
    mnt = [("SV21_MNT_SERVICER_FLANGE", [(0.0, 0.0, 80.0, 80.0)], [170.25, 185.25],
            "bus_structure", "EVIDENCE_BOUND", "envelope_15x160x160"),
           ("SV21_MNT_ADAPTER_PLATE", [(0.0, 0.0, 80.0, 80.0)], [158.25, 170.25],
            "robot_adapter", "EVIDENCE_BOUND",
            "envelope_12x160x160;replaceable_sacrificial_interface(PS-03)"),
           ("SV21_MNT_ADAPTER_BOSS", [(0.0, 0.0, 50.0)], [143.25, 158.25],
            "robot_adapter", "EVIDENCE_BOUND", "envelope_D100x15"),
           ("SV21_MNT_RIB_SET", [(74.075, 0.0, 24.075, 5.0), (-74.075, 0.0, 24.075, 5.0),
                                 (0.0, 74.075, 5.0, 24.075), (0.0, -74.075, 5.0, 24.075)],
            [152.25, 158.25], "bus_structure", "DESIGN_PROPOSAL",
            "rib_proposal_suppressible")]
    for i, (nm, rects, span, owner, ev, note) in enumerate(mnt, 1):
        build_x_extruded_part(sw, log, d / f"{nm}.SLDPRT", nm, rects, span,
                              props(f"V21-MNT-{i:03d}", owner, "LOAD_PATH_INTENT", ev,
                                    CLAIM + ";" + note + ";NO_STRENGTH_CLAIM",
                                    "SV21_Robot_Mount_Module", frame="CS_M",
                                    ifaces="IF-RM-001;IF-RM-002"))
    asm = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, asm, sorted(d.glob("*.SLDPRT")))
    set_custom_properties(asm, log, props("V21-MNT-000", "robot_mount_module",
                                          "LOAD_PATH_INTENT", "DESIGN_PROPOSAL",
                                          CLAIM + ";NO_STRENGTH_CLAIM",
                                          "Spacecraft_Service_Vehicle_V2_1",
                                          frame="CS_M", ifaces="IF-RM-001;IF-RM-002"))
    rebuild_or_fail(asm, log, "mount_asm")
    save_as(asm, log, V21 / "05_Robot_Mount_Module/SV21_Robot_Mount_Module.SLDASM")
    sw.CloseAllDocuments(True)
    log.event("B4_1_02_MOUNT_DONE")


def stage_solar(sw, log):
    sm = SPEC["solar_mechanism"]
    for side in ("L", "R"):
        wd = V21 / f"08_Solar_Wing_{side}/parts"
        wd.mkdir(parents=True, exist_ok=True)
        for state in ("deployed", "stowed"):
            box = sm["wing_solid"][state][side]
            (x0, x1) = box["x_span_mm"]
            (y0, y1) = box["y_span_mm"]
            (z0, z1) = box["z_span_mm"]
            nm = f"SOLAR_WING_{side}_{state.upper()}"
            build_x_extruded_part(
                sw, log, wd / f"{nm}.SLDPRT", nm,
                [((y0 + y1) / 2, (z0 + z1) / 2, (y1 - y0) / 2, (z1 - z0) / 2)],
                [x0, x1],
                props(f"V21-SW-{side}-{state[:3].upper()}", "DEPLOYABLES_OWNER",
                      "NON_STRUCTURAL_PANEL", "EVIDENCE_BOUND",
                      CLAIM + ";wing_200x227x6_SSOT_frozen;dual_representation_"
                      + state + (";stow_topology_declared_fold_-Z"
                                 if state == "stowed" else ""),
                      f"SV21_Solar_Wing_{side}",
                      ifaces="IF-SA-" + side))
        rd = V21 / f"07_Solar_Array_Root_Module_{side}/parts"
        rd.mkdir(parents=True, exist_ok=True)
        ysign = 1 if side == "L" else -1
        for ref in sm["root_module_refs"]:
            nm = f"{ref}_{side}"
            zp = props(f"V21-SAR-{side}-{ref}", "DEPLOYABLES_OWNER",
                       "VOLUME_OWNER_REFERENCE", "UNKNOWN_BLOCKED",
                       "zero_solid_named_only(H5);mechanism_params_UNKNOWN;"
                       + ("C4_ruling_MID2_station" if "MID2" in ref else
                          "C4_ruling_REAR_station" if "REAR" in ref else
                          "C2_ruling_MID2_node_pad_attach"),
                       f"SV21_Solar_Array_Root_Module_{side}",
                       ifaces="IF-SA-" + side)
            zp["REPRESENTATION_LAYER"] = "OWNER_PLACEHOLDER_ZERO_SOLID"
            zero_solid_ref_part(sw, log, rd / f"{nm}.SLDPRT", nm,
                                (0, ysign * 113.15, 0), zp)
        for mod_dir, asm_name in [(V21 / f"07_Solar_Array_Root_Module_{side}",
                                   f"SV21_Solar_Array_Root_Module_{side}"),
                                  (V21 / f"08_Solar_Wing_{side}",
                                   f"SV21_Solar_Wing_{side}")]:
            asm_path = mod_dir / f"{asm_name}.SLDASM"
            if asm_path.exists():
                log.event("SKIP_EXISTS", what=asm_path.name)
                continue
            asm = new_document(sw, log, "assembly")
            insert_components_identity(sw, log, asm,
                                       sorted((mod_dir / "parts").glob("*.SLDPRT")))
            set_custom_properties(asm, log, props(
                asm_name, "DEPLOYABLES_OWNER", "DEPLOYABLE_MODULE",
                "DESIGN_PROPOSAL", CLAIM + ";mechanism_refs_zero_solid",
                "Spacecraft_Service_Vehicle_V2_1", ifaces="IF-SA-" + side))
            rebuild_or_fail(asm, log, asm_name)
            save_as(asm, log, asm_path)
            sw.CloseAllDocuments(True)
    log.event("B4_1_03_SOLAR_DONE")


def configure_wing_subassembly(sw, log, side):
    """Store representation suppression in the owning wing subassembly.

    Suppressing a nested component from the top assembly does not create a
    configuration-specific state in the child document.  Each wing therefore
    owns DEPLOYED/STOWED/NONE configurations, and the top assembly only selects
    the required referenced configuration.
    """
    path = V21 / f"08_Solar_Wing_{side}/SV21_Solar_Wing_{side}.SLDASM"
    model = core.open_document(sw, log, path)
    cfg_mgr = get_com_member(model, "ConfigurationManager")
    existing = model.GetConfigurationNames
    if callable(existing):
        existing = existing()
    existing = set(existing or ())
    for cname in ("DEPLOYED", "STOWED", "NONE"):
        if cname not in existing:
            if cfg_mgr.AddConfiguration2(
                    cname, f"{side} wing representation {cname}", "", 0, "",
                    "Reference representation only; not deployment validation",
                    True) is None:
                log.fail("翼子装配配置创建失败", side=side, config=cname)
        core.activate_configuration(model, log, cname)
        asm = cast(model, "IAssemblyDoc")
        for comp in asm.GetComponents(True) or []:
            c2 = cast(comp, "IComponent2")
            nm = c2.Name2
            want_suppressed = (
                cname == "NONE"
                or (cname == "DEPLOYED" and "_STOWED" in nm)
                or (cname == "STOWED" and "_DEPLOYED" in nm)
            )
            state = c2.SetSuppression2(0 if want_suppressed else 2)
            log.event("WING_REP_COMPONENT_STATE", side=side, config=cname,
                      component=nm, suppressed=want_suppressed,
                      return_value=str(state))
        rebuild_or_fail(model, log, f"wing_{side}_{cname}")
    core.activate_configuration(model, log, "DEPLOYED")
    core.save(model, log)
    sw.CloseAllDocuments(True)
    log.event("WING_REP_CONFIGS_DONE", side=side)


def stage_top(sw, log):
    top = V21 / "Assembly/Spacecraft_Service_Vehicle_V2_1.SLDASM"
    comps = [V21 / "00_Master_Skeleton/Master_Skeleton_V2_1.SLDPRT",
             V21 / "01_Primary_Frame/SV21_Primary_Frame.SLDASM",
             V21 / "02_Equipment_Decks/SV21_Equipment_Decks.SLDASM",
             V21 / "03_Removable_Panels/SV21_Removable_Panels.SLDASM",
             V21 / "05_Robot_Mount_Module/SV21_Robot_Mount_Module.SLDASM",
             V20 / "06_B601_Visual_Arm/SV2_B601_Visual_Arm.SLDASM",   # 原样继承（只读）
             V21 / "07_Solar_Array_Root_Module_L/SV21_Solar_Array_Root_Module_L.SLDASM",
             V21 / "07_Solar_Array_Root_Module_R/SV21_Solar_Array_Root_Module_R.SLDASM",
             V21 / "08_Solar_Wing_L/SV21_Solar_Wing_L.SLDASM",
             V21 / "08_Solar_Wing_R/SV21_Solar_Wing_R.SLDASM"]
    missing = [str(p) for p in comps if not p.exists()]
    if missing:
        log.fail("组件缺失", missing=missing)
    # The two representation-bearing subassemblies must own their child
    # suppression states before the top-level state family references them.
    configure_wing_subassembly(sw, log, "L")
    configure_wing_subassembly(sw, log, "R")
    if top.exists():
        model = core.open_document(sw, log, top)
        log.event("TOP_RESUME")
    else:
        model = new_document(sw, log, "assembly")
        insert_components_identity(sw, log, model, comps)
        set_custom_properties(model, log, props(
            "V21-TOP-000", "system_architecture", "TOP_ASSEMBLY", "DESIGN_PROPOSAL",
            CLAIM + ";b601_inherited_readonly_from_V2_0;target_excluded",
            "", ifaces="IF-RM-001;IF-RM-002;IF-SA-L;IF-SA-R"))
        rebuild_or_fail(model, log, "top_v21")
        save_as(model, log, top)
    # 七态配置族
    cfg_mgr = get_com_member(model, "ConfigurationManager")
    existing = model.GetConfigurationNames
    if callable(existing):
        existing = existing()
    existing = set(existing or ())
    states = SPEC["state_family"]
    for cname, sdef in states.items():
        if cname not in existing:
            if cfg_mgr.AddConfiguration2(cname, str(sdef.get("semantic", "")), "", 0,
                                         "", str(sdef.get("semantic", "")), True) is None:
                log.fail("AddConfiguration2 失败", config=cname)
        core.activate_configuration(model, log, cname)
        asm = cast(model, "IAssemblyDoc")
        # Top-level state owns only the referenced configuration of each wing
        # subassembly.  CompConfigProperties5 applies the setting to the active
        # top configuration and is the documented configuration-safe API.
        for c in asm.GetComponents(True) or []:
            c2 = cast(c, "IComponent2")
            nm = c2.Name2
            for side in ("L", "R"):
                if f"SV21_Solar_Wing_{side}" not in nm:
                    continue
                mode = sdef.get(side)
                ref_config = {
                    "deployed": "DEPLOYED",
                    "stowed": "STOWED",
                    "none": "NONE",
                }[mode]
                model.ClearSelection2(True)
                if not c2.Select4(True, None, False):
                    log.fail("翼子装配选择失败", config=cname, component=nm)
                ok = asm.CompConfigProperties5(
                    2, 0, True, True, ref_config, False, False)
                model.ClearSelection2(True)
                if not ok:
                    log.fail("翼子装配引用配置设置失败", config=cname,
                             component=nm, referenced_config=ref_config)
                log.event("TOP_WING_REFERENCED_CONFIG", config=cname,
                          component=nm, referenced_config=ref_config)
        rebuild_or_fail(model, log, f"state_{cname}")
        log.event("STATE_CONFIG_SET", config=cname, **{k: str(v) for k, v in sdef.items()})
    core.activate_configuration(model, log, "DEPLOYED_NOMINAL")
    core.save(model, log)
    sw.CloseAllDocuments(True)
    log.event("B4_1_04_TOP_DONE", states=len(states))


STAGES = {"skeleton": stage_skeleton, "frame": stage_frame, "decks": stage_decks,
          "panels": stage_panels, "mount": stage_mount, "solar": stage_solar,
          "top": stage_top}


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    log = BuildLog(f"b4_1_{stage}")
    sw = connect(log)
    sw.CloseAllDocuments(True)
    if stage == "all":
        for name, fn in STAGES.items():
            fn(sw, log)
    else:
        STAGES[stage](sw, log)
    print(f"B4_1_STAGE_{stage.upper()}_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
