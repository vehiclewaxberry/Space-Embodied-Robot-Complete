"""V2.2 物理架构统一构建器（366 显示轨）。

用法：python sw_v22_builder.py <stage>
  skeleton|structure|b601if|endeff|solar|gnc|prop|comm|thermal|top|states|all
新增能力：cut_circle_hole（真实穿舱孔，C1 实体开口）。
两轨纪律：全件 CLAIM 带 display_track_366;dynamics_SSOT_340.5_unchanged。
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import b3_lib.sw_core as core
from b3_lib.sw_core import (B3FailClosed, BuildLog, cast, connect,
                            create_offset_plane, get_com_member,
                            insert_components_identity, new_document,
                            rebuild_or_fail, rename_last_feature, save_as,
                            set_custom_properties)
from b3_lib.sw_part_factory import (FRONT, RIGHT, TOP, _m, build_x_extruded_part,
                                    yz_rect_to_sketch)

V22 = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2")
core.V2_ROOT = V22
core.LOG_DIR = V22 / "evidence" / "build_logs"
V20 = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_0")
S = yaml.safe_load((V22 / "automation/b5_build_spec.yaml").read_text(encoding="utf-8"))
P = S["params"]
TRACK = "display_track_366;dynamics_SSOT_340.5_unchanged"


def pr(oid, owner, sclass, ev, claim, parent, frame="CS_S", ifaces=""):
    return {"OBJECT_ID": oid, "SYSTEM_OWNER": owner, "PARENT_ID": parent,
            "STRUCT_CLASS": sclass, "STRUCTURE_CLASS": sclass,
            "REPRESENTATION_LAYER": "PHYSICAL_ARCHITECTURE_DISPLAY",
            "EVIDENCE_STATE": ev,
            "SOURCE_REFERENCE": "b5_build_spec.yaml + gate_0_ruling_record.yaml",
            "FRAME_ID": frame, "INTERFACE_IDS": ifaces,
            "MASS_OWNER": "NONE_DISPLAY_ONLY", "NO_DYNAMICS_USE": "true",
            "MANUFACTURING_AUTHORITY": "NONE", "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
            "CLAIM_LIMIT": claim + ";" + TRACK,
            "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;manufacturing;strength_claims"}


CL = "L1_functional_geometry;icd_params_pending;NO_STRENGTH_CLAIM;NO_DIRECT_SCALE"


def cut_circle_hole(model, log, plane_names, plane_off_mm, yc, zc, d_mm, depth_mm,
                    name, negative_dir):
    """在既有实体上开真实圆孔（C1 实体开口）。基面偏移创建→圆→FeatureCut3。"""
    create_offset_plane(model, log, plane_names, plane_off_mm,
                        f"PLN_{name}", flip=plane_off_mm < 0)
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(f"PLN_{name}", "PLANE", 0, 0, 0, False, 0, None, 0):
        log.fail("选择开孔基面失败", cut=name)
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreateCircleByRadius(_m(-zc), _m(yc), 0.0, _m(d_mm / 2))
    sk.InsertSketch(True)
    fm = model.FeatureManager
    # makepy 实测签名 26 参；探针结论：Dir 必须 False（True 恒 None），
    # 基面置于材料 +axis 外侧、Dir=False 即切入材料。
    f = fm.FeatureCut3(True, False, False, 0, 0, _m(depth_mm), 0.0,
                       False, False, False, False, 0.0, 0.0, False, False,
                       False, False, False, True, True, True, True, False,
                       0, 0.0, False)
    if f is None:
        log.fail("FeatureCut3 失败", cut=name)
    rename_last_feature(model, log, f"CUT_{name}")
    log.event("REAL_OPENING_CUT", name=name, d_mm=d_mm)


def box(sw, log, d, nm, rects, span, p):
    build_x_extruded_part(sw, log, d / f"{nm}.SLDPRT", nm, rects, span, p)


def asm_of(sw, log, mod_dir, asm_name, owner, parent="Spacecraft_Service_Vehicle_V2_2",
           extra=None):
    path = mod_dir / f"{asm_name}.SLDASM"
    if path.exists():
        log.event("SKIP_EXISTS", what=path.name)
        return
    parts = sorted((mod_dir / "parts").glob("*.SLDPRT"))
    m = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, m, parts)
    set_custom_properties(m, log, extra or pr(asm_name, owner, "MODULE",
                                              "DESIGN_PROPOSAL", CL, parent))
    rebuild_or_fail(m, log, asm_name)
    save_as(m, log, path)
    sw.CloseAllDocuments(True)


def stage_skeleton(sw, log):
    out = V22 / "00_Master_Skeleton/Master_Skeleton_V2_2.SLDPRT"
    if out.exists():
        log.event("SKIP_EXISTS", what=out.name)
        return
    m = new_document(sw, log, "part")
    for nm, off in [("PLANE_REAR_FACE", -183.0), ("PLANE_MID2", -61.0),
                    ("PLANE_MID1", 61.0), ("PLANE_TASK_FACE", 183.0),
                    ("PLANE_MOUNT_M_V22", 198.0), ("PLANE_PANEL_SPLIT", 61.0)]:
        create_offset_plane(m, log, RIGHT, off, nm, flip=off < 0)
    create_offset_plane(m, log, TOP, 113.15, "PLANE_SOLAR_ROOT_L")
    create_offset_plane(m, log, TOP, -113.15, "PLANE_SOLAR_ROOT_R", flip=True)
    sk = m.SketchManager
    sk.Insert3DSketch(True)
    hx, hy, hz = _m(183.0), _m(113.15), _m(113.15)
    c = [(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    for a, b in [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7),
                 (0, 4), (1, 5), (2, 6), (3, 7)]:
        sk.CreateLine(*c[a], *c[b])
    sk.Insert3DSketch(True)
    rename_last_feature(m, log, "SK3D_BODY_ENVELOPE_366")
    props = pr("V22-SKEL-000", "system_architecture", "REFERENCE",
               "EVIDENCE_BOUND", CL + ";gate0_366_ruling", "Spacecraft_Service_Vehicle_V2_2")
    set_custom_properties(m, log, props)
    mgr = m.Extension.CustomPropertyManager("")
    for k, v in P.items():
        mgr.Add3(f"PARAM_{k}", 30, str(v), 2)
    rebuild_or_fail(m, log, "skeleton_v22")
    save_as(m, log, out)
    sw.CloseDoc(get_com_member(m, "GetTitle"))
    log.event("V22_SKELETON_DONE")


def stage_structure(sw, log):
    d = V22 / "10_Primary_Structure/parts"
    d.mkdir(parents=True, exist_ok=True)
    for nm, fr in S["structure"]["frames"].items():
        ro = fr["radial_out"]
        cc, hh = (98.15 + ro) / 2, (ro - 98.15) / 2
        rects = [(0.0, cc, 98.15, hh), (0.0, -cc, 98.15, hh),
                 (cc, 0.0, hh, 98.15), (-cc, 0.0, hh, 98.15)]
        box(sw, log, d, nm, rects, fr["x"],
            pr(f"V22-{nm}", "primary_structure", "LOAD_PATH_INTENT",
               "DESIGN_PROPOSAL", CL, "SV22_Primary_Structure"))
    for nm, yc, zc in [("LNG_PY_PZ", 105.65, 105.65), ("LNG_PY_NZ", 105.65, -105.65),
                       ("LNG_NY_PZ", -105.65, 105.65), ("LNG_NY_NZ", -105.65, -105.65)]:
        box(sw, log, d, nm, [(yc, zc, 7.5, 7.5)], S["structure"]["longerons_x"],
            pr(f"V22-{nm}", "primary_structure", "LOAD_PATH_INTENT",
               "DESIGN_PROPOSAL", CL, "SV22_Primary_Structure"))
    for nm, dk in S["structure"]["decks"].items():
        path = d / f"{nm}.SLDPRT"
        if path.exists():
            log.event("PART_SKIP_EXISTS", part=nm)
            continue
        m = new_document(sw, log, "part")
        x0, x1 = dk["xc"] - dk["t"] / 2, dk["xc"] + dk["t"] / 2
        create_offset_plane(m, log, RIGHT, x0, f"PLN_{nm}_BASE", flip=x0 < 0)
        m.ClearSelection2(True)
        m.Extension.SelectByID2(f"PLN_{nm}_BASE", "PLANE", 0, 0, 0, False, 0, None, 0)
        sk = m.SketchManager
        sk.InsertSketch(True)
        sk.CreateCenterRectangle(*yz_rect_to_sketch(0.0, 0.0, 98.15, 98.15))
        sk.InsertSketch(True)
        from b3_lib.sw_part_factory import extrude_checked
        extrude_checked(m, log, dk["t"], "x", x0, x1, f"EX_{nm}", plane_off_mm=x0)
        for psg in S["structure"]["deck_passages"]:
            if psg["deck"] == nm:
                cut_circle_hole(m, log, RIGHT, x1 + 1.0, psg["yc"], psg["zc"],
                                psg["d"], dk["t"] + 2.0, f"{nm}_PASSAGE", True)
        set_custom_properties(m, log, pr(
            f"V22-{nm}", "primary_structure", "LOAD_PATH_INTENT_SHEAR_WEB",
            "DESIGN_PROPOSAL", CL + ";C1_real_opening_doubler_intent_registered",
            "SV22_Primary_Structure"))
        rebuild_or_fail(m, log, nm)
        save_as(m, log, path)
        sw.CloseDoc(get_com_member(m, "GetTitle"))
        log.event("PART_BUILT", part=nm)
    for pad in S["structure"]["node_pads"]:
        (y0, y1), (z0, z1) = pad["y"], pad["z"]
        box(sw, log, d, pad["id"],
            [((y0 + y1) / 2, (z0 + z1) / 2, (y1 - y0) / 2, (z1 - z0) / 2)], pad["x"],
            pr(f"V22-{pad['id']}", "primary_structure", "LOAD_PATH_INTENT",
               "DESIGN_PROPOSAL", CL + ";C2_C4_node_pad", "SV22_Primary_Structure",
               ifaces="IF-SA"))
    g = S["structure"]["gussets"]
    for k, (yc, zc) in enumerate(g["cells"]):
        box(sw, log, d, f"GUSSET_{k+1}", [(yc, zc, g["half"], g["half"])], g["x"],
            pr(f"V22-GUSSET-{k+1}", "primary_structure", "LOAD_PATH_INTENT",
               "DESIGN_PROPOSAL", CL, "SV22_Primary_Structure"))
    for nm, pn in S["structure"]["panels"].items():
        if pn["face"] in ("+Z", "-Z"):
            sign = 1 if pn["face"] == "+Z" else -1
            rects = [(0.0, sign * 111.65, 98.15, 1.5)]
        else:
            sign = 1 if pn["face"] == "+Y" else -1
            rects = [(sign * 111.65, 0.0, 1.5, 98.15)]
        box(sw, log, d, nm, rects, pn["x"],
            pr(f"V22-{nm}", "secondary_structure", "NON_STRUCTURAL_PANEL",
               "DESIGN_PROPOSAL", CL + ";removable;C3_split_61", "SV22_Primary_Structure"))
    asm_of(sw, log, V22 / "10_Primary_Structure", "SV22_Primary_Structure",
           "primary_structure")
    log.event("V22_STRUCTURE_DONE")


def stage_b601if(sw, log):
    d = V22 / "20_B601_Interface/parts"
    d.mkdir(parents=True, exist_ok=True)
    bi = S["b601_interface"]
    r = bi["BASE_ADAPTER_RING"]
    path = d / "BASE_ADAPTER_RING.SLDPRT"
    if not path.exists():
        m = new_document(sw, log, "part")
        x0, x1 = r["x"]
        create_offset_plane(m, log, RIGHT, x0, "PLN_ADAPTER_BASE")
        m.ClearSelection2(True)
        m.Extension.SelectByID2("PLN_ADAPTER_BASE", "PLANE", 0, 0, 0, False, 0, None, 0)
        sk = m.SketchManager
        sk.InsertSketch(True)
        sk.CreateCircleByRadius(0.0, 0.0, 0.0, _m(r["od"] / 2))
        sk.InsertSketch(True)
        from b3_lib.sw_part_factory import extrude_checked
        extrude_checked(m, log, x1 - x0, "x", x0, x1, "EX_ADAPTER", plane_off_mm=x0)
        cut_circle_hole(m, log, RIGHT, x1 + 1.0, 0.0, 0.0, r["id_ref"],
                        x1 - x0 + 2.0, "ADAPTER_BORE", True)
        cut_circle_hole(m, log, RIGHT, x1 + 1.0, 70.0, 0.0, 18.0,
                        x1 - x0 + 2.0, "CONNECTOR_WINDOW", True)
        set_custom_properties(m, log, pr(
            "V22-BIF-001", "robot_interface", "LOAD_PATH_INTENT", "DESIGN_PROPOSAL",
            CL + ";bolt_circle_pins_ICD_pending", "SV22_B601_Interface",
            frame="CS_M_V22", ifaces="IF-RM-001;IF-RM-002"))
        rebuild_or_fail(m, log, "BASE_ADAPTER_RING")
        save_as(m, log, path)
        sw.CloseDoc(get_com_member(m, "GetTitle"))
        log.event("PART_BUILT", part="BASE_ADAPTER_RING")
    ls = bi["LOAD_SPREADER"]
    path = d / "LOAD_SPREADER.SLDPRT"
    if not path.exists():
        m = new_document(sw, log, "part")
        x0, x1 = ls["x"]
        create_offset_plane(m, log, RIGHT, x0, "PLN_LS_BASE")
        m.ClearSelection2(True)
        m.Extension.SelectByID2("PLN_LS_BASE", "PLANE", 0, 0, 0, False, 0, None, 0)
        sk = m.SketchManager
        sk.InsertSketch(True)
        sk.CreateCenterRectangle(*yz_rect_to_sketch(0.0, 0.0, ls["sq"] / 2, ls["sq"] / 2))
        sk.InsertSketch(True)
        from b3_lib.sw_part_factory import extrude_checked
        extrude_checked(m, log, x1 - x0, "x", x0, x1, "EX_LS", plane_off_mm=x0)
        h = bi["HARNESS_PASSTHROUGH"]
        cut_circle_hole(m, log, RIGHT, x1 + 1.0, h["yc"], h["zc"], h["d"],
                        x1 - x0 + 2.0, "HARNESS_PASSTHROUGH", True)
        set_custom_properties(m, log, pr(
            "V22-BIF-002", "robot_interface", "LOAD_PATH_INTENT", "DESIGN_PROPOSAL",
            CL + ";C1_real_passthrough", "SV22_B601_Interface", frame="CS_M_V22"))
        rebuild_or_fail(m, log, "LOAD_SPREADER")
        save_as(m, log, path)
        sw.CloseDoc(get_com_member(m, "GetTitle"))
        log.event("PART_BUILT", part="LOAD_SPREADER")
    b = bi["BOSS"]
    box(sw, log, d, "BOSS", [(0.0, 0.0, b["d"] / 2)], b["x"],
        pr("V22-BIF-003", "robot_interface", "LOAD_PATH_INTENT", "EVIDENCE_BOUND",
           CL, "SV22_B601_Interface", frame="CS_M_V22"))
    for key, oid in [("ARM_CRADLE_MAIN", "V22-BIF-004"), ("ARM_CRADLE_TIP", "V22-BIF-005")]:
        c = bi[key]
        (y0, y1), (z0, z1) = c["y"], c["z"]
        box(sw, log, d, key, [((y0 + y1) / 2, (z0 + z1) / 2, (y1 - y0) / 2, (z1 - z0) / 2)],
            c["x"], pr(oid, "robot_interface", "LOAD_PATH_INTENT", "DESIGN_PROPOSAL",
                       CL + ";stowed_arm_pose_not_modeled;lock_release_ICD_pending",
                       "SV22_B601_Interface"))
    asm_of(sw, log, V22 / "20_B601_Interface", "SV22_B601_Interface", "robot_interface")
    log.event("V22_B601IF_DONE")


def stage_endeff(sw, log):
    d = V22 / "40_End_Effector_Module/parts"
    d.mkdir(parents=True, exist_ok=True)
    e = S["end_effector"]
    x = e["stack_x0"]
    for key in ("WRIST", "FT_SENSOR", "CAM_RING", "COMPLIANT"):
        c = e[key]
        box(sw, log, d, key, [(0.0, 0.0, c["d"] / 2)], [x, x + c["len"]],
            pr(f"V22-EE-{key}", "end_effector", "MECHANISM_DISPLAY",
               "DESIGN_PROPOSAL", CL + ";candidate_design_not_fact;anchor_display_only",
               "SV22_End_Effector", frame="E_virtual_display"))
        x += c["len"]
    f = e["FINGERS"]
    import math
    for i in range(f["n"]):
        ang = 2 * math.pi * i / f["n"]
        yc = f["root_r"] * math.cos(ang)
        zc = f["root_r"] * math.sin(ang)
        box(sw, log, d, f"FINGER_{i+1}", [(yc, zc, f["w"] / 2, f["t"] / 2)],
            [x, x + f["len"]],
            pr(f"V22-EE-F{i+1}", "end_effector", "MECHANISM_DISPLAY",
               "DESIGN_PROPOSAL", CL + ";capture_head_candidate", "SV22_End_Effector"))
    asm_of(sw, log, V22 / "40_End_Effector_Module", "SV22_End_Effector", "end_effector")
    log.event("V22_ENDEFF_DONE")


def stage_solar(sw, log):
    so = S["solar"]
    for side, ys in (("L", 1), ("R", -1)):
        d = V22 / f"50_Solar_Array_{'Left' if side=='L' else 'Right'}/parts"
        d.mkdir(parents=True, exist_ok=True)
        for state in ("deployed", "stowed"):
            w = so[f"wing_{state}"]
            (ya, yb) = w["y_abs"]
            y0, y1 = (ys * ya, ys * yb) if ys > 0 else (ys * yb, ys * ya)
            (z0, z1) = w["z"]
            nm = f"WING_{side}_{state.upper()}"
            box(sw, log, d, nm,
                [((y0 + y1) / 2, (z0 + z1) / 2, (y1 - y0) / 2, (z1 - z0) / 2)],
                w["x"], pr(f"V22-SW-{side}-{state[:3]}", "solar_array",
                           "MECHANISM_DISPLAY", "DESIGN_PROPOSAL",
                           CL + f";wing_{state};frame_border+cell_zone_next_pass;"
                           "mech_track_only_SSOT_single_panel_unchanged",
                           f"SV22_Solar_Array_{side}"))
        rb = so["ROOT_BRACKET"]
        base = rb["base"]
        y0 = ys * 113.15
        y1 = ys * (113.15 + base["y_out"])
        yy0, yy1 = min(y0, y1), max(y0, y1)
        box(sw, log, d, f"ROOT_BRACKET_BASE_{side}",
            [((yy0 + yy1) / 2, 0.0, (yy1 - yy0) / 2, (base["z"][1] - base["z"][0]) / 2)],
            base["x"], pr(f"V22-RB-{side}", "solar_array", "LOAD_PATH_INTENT",
                          "DESIGN_PROPOSAL", CL + ";C2_MID2_node_pad_attach",
                          f"SV22_Solar_Array_{side}", ifaces=f"IF-SA-{side}"))
        for k, ear in enumerate(rb["ears"]):
            ey0 = ys * (113.15 + base["y_out"])
            ey1 = ys * (113.15 + base["y_out"] + rb["ear_h"])
            e0, e1 = min(ey0, ey1), max(ey0, ey1)
            box(sw, log, d, f"HINGE_EAR_{side}_{k+1}",
                [((e0 + e1) / 2, 0.0, (e1 - e0) / 2, rb["ear_t"] / 2)], ear["x"],
                pr(f"V22-HE-{side}{k+1}", "solar_array", "MECHANISM_DISPLAY",
                   "DESIGN_PROPOSAL", CL + ";dual_ear_antitorsion",
                   f"SV22_Solar_Array_{side}"))
        hg = so["HINGE"]
        pin_y = ys * (113.15 + base["y_out"] + rb["ear_h"] - hg["pin_d"])
        for k, ear in enumerate(rb["ears"]):
            xc = sum(ear["x"]) / 2
            box(sw, log, d, f"HINGE_PIN_{side}_{k+1}",
                [(pin_y, 0.0, hg["pin_d"] / 2)],
                [xc - hg["pin_len"] / 2, xc + hg["pin_len"] / 2],
                pr(f"V22-HP-{side}{k+1}", "solar_array", "MECHANISM_DISPLAY",
                   "DESIGN_PROPOSAL", CL + ";pin_axis_display;dims_ICD_pending",
                   f"SV22_Solar_Array_{side}"))
            box(sw, log, d, f"TORSION_SPRING_{side}_{k+1}",
                [(pin_y, 0.0, hg["spring_d"] / 2)],
                [xc + hg["pin_len"] / 2, xc + hg["pin_len"] / 2 + hg["spring_len"]],
                pr(f"V22-TS-{side}{k+1}", "solar_array", "MECHANISM_DISPLAY",
                   "DESIGN_PROPOSAL", CL + ";spring_envelope_stiffness_UNKNOWN",
                   f"SV22_Solar_Array_{side}"))
        hd = so["HDRM"]
        for k, xs in enumerate(hd["stations_x"]):
            by = ys * (113.15 + hd["base_t"] / 2)
            byy0, byy1 = min(ys * 113.15, ys * (113.15 + hd["base_t"])), max(
                ys * 113.15, ys * (113.15 + hd["base_t"]))
            box(sw, log, d, f"HDRM_BASE_{side}_{k+1}",
                [((byy0 + byy1) / 2, -100.0, (byy1 - byy0) / 2, hd["base_sq"] / 2)],
                [xs - hd["base_sq"] / 2, xs + hd["base_sq"] / 2],
                pr(f"V22-HD-{side}{k+1}", "solar_array", "MECHANISM_DISPLAY",
                   "DESIGN_PROPOSAL",
                   CL + ";dual_HDRM_staggered_C5;release_mech_ICD_pending;"
                   "no_redundancy_reliability_claim", f"SV22_Solar_Array_{side}"))
        st = so["HARD_STOP"]
        box(sw, log, d, f"HARD_STOP_{side}",
            [(ys * (113.15 + base["y_out"] + 4.0), 30.0, st["t"] / 2, st["sq"] / 2)],
            [-64.0, -58.0],
            pr(f"V22-HS-{side}", "solar_array", "MECHANISM_DISPLAY",
               "DESIGN_PROPOSAL", CL + ";deploy_stop_display", f"SV22_Solar_Array_{side}"))
        asm_of(sw, log, V22 / f"50_Solar_Array_{'Left' if side=='L' else 'Right'}",
               f"SV22_Solar_Array_{side}", "solar_array")
    log.event("V22_SOLAR_DONE")


def stage_gnc(sw, log):
    d = V22 / "60_GNC_Sensor_Module/parts"
    d.mkdir(parents=True, exist_ok=True)
    for key in ("NAV_CAM", "RANGE_SENSOR", "STAR_TRACKER"):
        c = S["gnc_vision"][key]
        ax, ay, az = c["at"]
        bx, by, bz = c["body"]
        box(sw, log, d, key, [(ay, az, by / 2, bz / 2)], [ax - bx / 2, ax + bx / 2],
            pr(f"V22-GNC-{key}", "gnc_vision", "MECHANISM_DISPLAY", "DESIGN_PROPOSAL",
               CL + ";model_FOV_boresight_UNKNOWN;fov_cone=display_proposal",
               "SV22_GNC_Sensors"))
    path = d / "FOV_CONES_REF.SLDPRT"
    if not path.exists():
        m = new_document(sw, log, "part")
        sk = m.SketchManager
        import math
        for key in ("NAV_CAM", "STAR_TRACKER"):
            c = S["gnc_vision"][key]
            if "fov_cone" not in c:
                continue
            ax, ay, az = [_m(v) for v in c["at"]]
            L = _m(c["fov_cone"]["len"])
            r = L * math.tan(math.radians(c["fov_cone"]["half_deg_display"]))
            sk.Insert3DSketch(True)
            if c["axis"] == "+X":
                tip = (ax, ay, az)
                pts = [(ax + L, ay + r * math.cos(t), az + r * math.sin(t))
                       for t in [0, math.pi / 2, math.pi, 3 * math.pi / 2]]
            else:
                tip = (ax, ay, az)
                pts = [(ax + r * math.cos(t), ay + r * math.sin(t), az + L)
                       for t in [0, math.pi / 2, math.pi, 3 * math.pi / 2]]
            for p2 in pts:
                sk.CreateLine(*tip, *p2)
            for i in range(4):
                sk.CreateLine(*pts[i], *pts[(i + 1) % 4])
            sk.Insert3DSketch(True)
            rename_last_feature(m, log, f"SK3D_FOV_{key}")
        set_custom_properties(m, log, pr(
            "V22-GNC-FOV", "gnc_vision", "KEEPOUT_REFERENCE", "DESIGN_PROPOSAL",
            CL + ";not_calibration;display_half_angle_only", "SV22_GNC_Sensors"))
        rebuild_or_fail(m, log, "fov_cones")
        save_as(m, log, path)
        sw.CloseDoc(get_com_member(m, "GetTitle"))
    asm_of(sw, log, V22 / "60_GNC_Sensor_Module", "SV22_GNC_Sensors", "gnc_vision")
    log.event("V22_GNC_DONE")


def stage_prop(sw, log):
    d = V22 / "70_Propulsion_Module/parts"
    d.mkdir(parents=True, exist_ok=True)
    p = S["propulsion"]
    cm = p["corner_modules"]
    for k, (yc, zc) in enumerate(cm["corners"]):
        box(sw, log, d, f"THRUSTER_POD_{k+1}",
            [(yc, zc, cm["body_half"], cm["body_half"])], cm["x"],
            pr(f"V22-PROP-POD{k+1}", "propulsion", "MECHANISM_DISPLAY",
               "DESIGN_PROPOSAL", CL + ";propellant_thrust_count_not_issued",
               "SV22_Propulsion"))
        box(sw, log, d, f"NOZZLE_{k+1}_AX",
            [(yc, zc, 8.0)], [-191.0, -183.0],
            pr(f"V22-PROP-NZ{k+1}A", "propulsion", "MECHANISM_DISPLAY",
               "DESIGN_PROPOSAL", CL + ";nozzle_envelope", "SV22_Propulsion"))
    mt = p["MAIN_THRUSTER"]
    box(sw, log, d, "MAIN_THRUSTER", [(mt["yc"], mt["zc"], mt["d"] / 2)],
        [mt["at_x"] - mt["len"], mt["at_x"]],
        pr("V22-PROP-MAIN", "propulsion", "MECHANISM_DISPLAY", "DESIGN_PROPOSAL",
           CL + ";nozzle_envelope", "SV22_Propulsion"))
    tk = p["TANK"]
    box(sw, log, d, "TANK", [(0.0, 0.0, tk["d"] / 2)],
        [tk["xc"] - tk["len"] / 2, tk["xc"] + tk["len"] / 2],
        pr("V22-PROP-TANK", "propulsion", "MECHANISM_DISPLAY", "DESIGN_PROPOSAL",
           CL + ";tank_envelope;propellant_not_issued", "SV22_Propulsion"))
    vp = p["VALVE_PLATE"]
    box(sw, log, d, "VALVE_PLATE", [(0.0, vp["zc"], vp["sq"] / 2, 4.0)], vp["x"],
        pr("V22-PROP-VALVE", "propulsion", "MECHANISM_DISPLAY", "DESIGN_PROPOSAL",
           CL, "SV22_Propulsion"))
    asm_of(sw, log, V22 / "70_Propulsion_Module", "SV22_Propulsion", "propulsion")
    log.event("V22_PROP_DONE")


def stage_comm(sw, log):
    d = V22 / "80_Communication_Module/parts"
    d.mkdir(parents=True, exist_ok=True)
    sb = S["comm"]["SBAND_PATCH"]
    box(sw, log, d, "SBAND_PATCH", [(sb["at"][1], sb["at"][2], sb["sq"] / 2, sb["sq"] / 2)],
        [-183.0 - sb["t"], -183.0],
        pr("V22-COMM-SBAND", "communication", "MECHANISM_DISPLAY", "DESIGN_PROPOSAL",
           CL + ";no_link_budget_no_gain_claim", "SV22_Communication"))
    gp = S["comm"]["GNSS_PATCH"]
    box(sw, log, d, "GNSS_PATCH", [(gp["at"][1], 113.15 + gp["t"] / 2,
                                    gp["sq"] / 2, gp["t"] / 2)],
        [gp["at"][0] - gp["sq"] / 2, gp["at"][0] + gp["sq"] / 2],
        pr("V22-COMM-GNSS", "communication", "MECHANISM_DISPLAY", "DESIGN_PROPOSAL",
           CL, "SV22_Communication"))
    asm_of(sw, log, V22 / "80_Communication_Module", "SV22_Communication",
           "communication")
    log.event("V22_COMM_DONE")


def stage_thermal(sw, log):
    d = V22 / "90_Thermal_Exterior/parts"
    d.mkdir(parents=True, exist_ok=True)
    rd = S["thermal"]["RADIATOR_Z"]
    box(sw, log, d, "RADIATOR_PZ", [(0.0, 113.15 + rd["t"] / 2, rd["half_w"], rd["t"] / 2)],
        rd["x"], pr("V22-THM-RAD", "thermal", "MECHANISM_DISPLAY", "DESIGN_PROPOSAL",
                    CL + ";radiator_area_not_sized;MLI_zones_named_only",
                    "SV22_Thermal"))
    asm_of(sw, log, V22 / "90_Thermal_Exterior", "SV22_Thermal", "thermal")
    log.event("V22_THERMAL_DONE")


def stage_top(sw, log):
    top = V22 / "Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM"
    comps = [V22 / "00_Master_Skeleton/Master_Skeleton_V2_2.SLDPRT",
             V22 / "10_Primary_Structure/SV22_Primary_Structure.SLDASM",
             V22 / "20_B601_Interface/SV22_B601_Interface.SLDASM",
             V20 / "06_B601_Visual_Arm/SV2_B601_Visual_Arm.SLDASM",
             V22 / "40_End_Effector_Module/SV22_End_Effector.SLDASM",
             V22 / "50_Solar_Array_Left/SV22_Solar_Array_L.SLDASM",
             V22 / "50_Solar_Array_Right/SV22_Solar_Array_R.SLDASM",
             V22 / "60_GNC_Sensor_Module/SV22_GNC_Sensors.SLDASM",
             V22 / "70_Propulsion_Module/SV22_Propulsion.SLDASM",
             V22 / "80_Communication_Module/SV22_Communication.SLDASM",
             V22 / "90_Thermal_Exterior/SV22_Thermal.SLDASM"]
    missing = [str(p) for p in comps if not p.exists()]
    if missing:
        log.fail("组件缺失", missing=missing)
    if top.exists():
        log.event("SKIP_EXISTS", what=top.name)
        return
    m = new_document(sw, log, "assembly")
    asm = cast(m, "IAssemblyDoc")
    from b3_lib.sw_core import IDENT16, byref_i4, open_document
    mu = cast(get_com_member(sw, "GetMathUtility"), "IMathUtility")
    for prt in comps:
        open_document(sw, log, prt, read_only=True)
        title = get_com_member(m, "GetTitle")
        try:
            sw.ActivateDoc3(title, False, 0, 0)
        except TypeError:
            sw.ActivateDoc3(title, False, 0, byref_i4())
        c = asm.AddComponent5(str(prt), 0, "", False, "", 0.0, 0.0, 0.0)
        if c is None:
            log.fail("AddComponent5 失败", part=prt.name)
        c2 = cast(c, "IComponent2")
        data = list(IDENT16)
        if "B601_Visual_Arm" in str(prt):
            data[9] = P["B601_OFFSET_X"] / 1000.0    # +12.75mm 显示轨位移
        xf = mu.CreateTransform(data)
        try:
            c2.Transform2 = xf
        except Exception:
            c2.SetTransformAndSolve2(xf)
        log.event("COMPONENT_ADDED", part=prt.name,
                  offset_x_mm=(P["B601_OFFSET_X"] if "B601" in str(prt) else 0))
        sw.CloseDoc(prt.name)
    m.ClearSelection2(True)
    for c in asm.GetComponents(True) or []:
        cast(c, "IComponent2").Select4(True, None, False)
    asm.FixComponent()
    m.ClearSelection2(True)
    set_custom_properties(m, log, pr(
        "V22-TOP-000", "system_architecture", "TOP_ASSEMBLY", "DESIGN_PROPOSAL",
        CL + ";b601_inherited_offset_12.75;target_excluded", ""))
    rebuild_or_fail(m, log, "top_v22")
    save_as(m, log, top)
    sw.CloseAllDocuments(True)
    log.event("V22_TOP_DONE")


def stage_states(sw, log):
    from b3_lib.sw_core import activate_configuration, open_document, save
    top = V22 / "Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM"
    m = open_document(sw, log, top)
    asm = cast(m, "IAssemblyDoc")
    cfg_mgr = get_com_member(m, "ConfigurationManager")
    existing = m.GetConfigurationNames
    if callable(existing):
        existing = existing()
    existing = set(existing or ())
    plan = {"STOWED": ("stowed", "stowed"), "DEPLOYED_NOMINAL": ("deployed", "deployed"),
            "DEPLOY_FAILED_BOTH": ("stowed", "stowed"), "L_FAIL": ("stowed", "deployed"),
            "R_FAIL": ("deployed", "stowed"), "PARTIAL": ("none", "none"),
            "SERVICE": ("deployed", "deployed"),
            "CAPTURE_SAFE": ("deployed", "deployed")}
    notes = {"PARTIAL": "展开角UNKNOWN双抑制", "CAPTURE_SAFE":
             S["capture_safe_semantic"], "DEPLOY_FAILED_BOTH": "故障场景入口"}
    for cname, (lmode, rmode) in plan.items():
        if cname not in existing:
            if cfg_mgr.AddConfiguration2(cname, notes.get(cname, ""), "", 0, "",
                                         notes.get(cname, ""), True) is None:
                log.fail("AddConfiguration2 失败", config=cname)
        activate_configuration(m, log, cname)
        for c in asm.GetComponents(False) or []:
            c2 = cast(c, "IComponent2")
            nm = c2.Name2
            for side, mode in (("L", lmode), ("R", rmode)):
                if f"WING_{side}_DEPLOYED" in nm:
                    c2.SetSuppression2(0 if mode in ("stowed", "none") else 2)
                elif f"WING_{side}_STOWED" in nm:
                    c2.SetSuppression2(0 if mode in ("deployed", "none") else 2)
        rebuild_or_fail(m, log, f"state_{cname}")
        log.event("STATE_SET", config=cname, L=lmode, R=rmode)
    activate_configuration(m, log, "DEPLOYED_NOMINAL")
    save(m, log)
    sw.CloseAllDocuments(True)
    log.event("V22_STATES_DONE", states=len(plan))


STAGES = {"skeleton": stage_skeleton, "structure": stage_structure,
          "b601if": stage_b601if, "endeff": stage_endeff, "solar": stage_solar,
          "gnc": stage_gnc, "prop": stage_prop, "comm": stage_comm,
          "thermal": stage_thermal, "top": stage_top, "states": stage_states}


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    log = BuildLog(f"b5_{stage}")
    sw = connect(log)
    sw.CloseAllDocuments(True)
    if stage == "all":
        for name, fn in STAGES.items():
            fn(sw, log)
    else:
        STAGES[stage](sw, log)
    print(f"B5_STAGE_{stage.upper()}_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
