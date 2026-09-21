# build_master_skeleton.py — create B51R1_MASTER_SKELETON_FREECAD.FCStd (native, datum-only).
# Runs inside FreeCADCmd. Zero solids, zero mass, no donor-face references.
import os, sys, json, math
import FreeCAD as App

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common

DOC_NAME = "B51R1_MASTER_SKELETON_FREECAD"
OUT_FCSTD = os.path.join(fc_common.FA_ROOT, "01_skeleton", DOC_NAME + ".FCStd")

NUMERIC_PARAMS = [
    ("BUS_ENVELOPE_Y", 226.3), ("C5_STOWED_PACK_WIDTH", 238.3),
    ("SOLAR_ROOT_MECH_MIN_WIDTH", 302.3), ("MOUNT_FACE_X", 198.0),
    ("T_SM_DYNAMICS_X", 185.25), ("X_INTERFACE_REF", 183.0),
    ("LONGERON_AXIS_Y", 101.65), ("LOAD_LAYER_Y", 110.15),
    ("PANEL_LAYER_Y", 113.15), ("HISTORICAL_Y", 105.65),
    ("B601_INTERFACE_DIA", 100.0), ("BASE_PLATE_LX", 160.0),
    ("BASE_PLATE_LY", 160.0), ("BASE_PLATE_T", 12.0),
    ("CLOCK_A0_DEG", 25.0), ("CLOCK_MIN_DEG", 7.894),
    ("GRIPPER_P_TRAVEL", 71.5),
    ("STOW_Q1_DEG", 145.572), ("STOW_Q2_DEG", -168.0), ("STOW_Q3_DEG", -57.0),
    ("STOW_Q4_DEG", -41.143), ("STOW_Q5_DEG", -20.954), ("STOW_Q6_DEG", -3.0),
    ("SADDLE_AFT_X_MIN", -20.0), ("SADDLE_AFT_X_MAX", 0.0),
    ("SADDLE_AFT_CONTACT_Z", 261.08), ("SADDLE_AFT_TOWER_H", 147.93),
    ("SADDLE_AFT_Y_MIN", -71.33), ("SADDLE_AFT_Y_MAX", 77.7),
    ("SADDLE_MID_X_MIN", 80.0), ("SADDLE_MID_X_MAX", 100.0),
    ("SADDLE_MID_CONTACT_Z", 214.92), ("SADDLE_MID_TOWER_H", 101.77),
    ("SADDLE_MID_Y_MIN", 7.72), ("SADDLE_MID_Y_MAX", 87.87),
    ("SADDLE_FWD_X_MIN", 160.0), ("SADDLE_FWD_X_MAX", 180.0),
    ("SADDLE_FWD_CONTACT_Z", 209.42), ("SADDLE_FWD_TOWER_H", 96.27),
    ("SADDLE_FWD_Y_MIN", 2.99), ("SADDLE_FWD_Y_MAX", 80.11),
    ("MIN_MOVABLE_CLEARANCE", 8.0), ("ARM_TOTAL_MASS_KG", 4.6955559493429862),
    ("BCD_FLANGE", 130.0), ("CORNER_PATTERN", 140.0),
]
STRING_PARAMS = [("STOW_Z_LIMIT", "UNKNOWN")]

def build():
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    doc = App.newDocument(DOC_NAME)
    doc.Comment = "B5.1R1 Master Skeleton (FreeCAD native). Datum-only. Zero solid/mass. L1 authority."

    sheet = doc.addObject("Spreadsheet::Sheet", "SSOT_PARAMS")
    sheet.set("A1", "NAME"); sheet.set("B1", "VALUE"); sheet.set("C1", "UNIT"); sheet.set("D1", "ROLE")
    row = 2
    for name, val in NUMERIC_PARAMS:
        sheet.set("A%d" % row, name)
        sheet.set("B%d" % row, repr(val))
        sheet.set("C%d" % row, "mm" if "DEG" not in name and "KG" not in name else ("deg" if "DEG" in name else "kg"))
        sheet.setAlias("B%d" % row, name)
        row += 1
    for name, val in STRING_PARAMS:
        sheet.set("A%d" % row, name); sheet.set("B%d" % row, val)
        sheet.setAlias("B%d" % row, name)
        row += 1
    sheet.set("A%d" % row, "CLOCK_A0_RAD"); sheet.set("B%d" % row, "=CLOCK_A0_DEG*pi/180")
    sheet.setAlias("B%d" % row, "CLOCK_A0_RAD"); row += 1
    for tag in ("AFT", "MID", "FWD"):
        sheet.set("A%d" % row, "SADDLE_%s_X_CENTER" % tag)
        sheet.set("B%d" % row, "=(SADDLE_%s_X_MIN+SADDLE_%s_X_MAX)/2" % (tag, tag))
        sheet.setAlias("B%d" % row, "SADDLE_%s_X_CENTER" % tag); row += 1
        sheet.set("A%d" % row, "SADDLE_%s_Y_CENTER" % tag)
        sheet.set("B%d" % row, "=(SADDLE_%s_Y_MIN+SADDLE_%s_Y_MAX)/2" % (tag, tag))
        sheet.setAlias("B%d" % row, "SADDLE_%s_Y_CENTER" % tag); row += 1

    for mode in ("COMMON_CANONICAL", "MODE_A_EVALUATION", "MODE_B_EVALUATION"):
        ms = doc.addObject("Spreadsheet::Sheet", "PARAM_" + mode)
        ms.set("A1", "MODE_SET"); ms.set("B1", mode)
        ms.set("A2", "H9_STATUS"); ms.set("B2", "HUMAN_DECISION_REQUIRED_RETAIN_BOTH_MODES")

    root = doc.addObject("App::Part", "MS_ROOT")
    created = []

    def add_lcs(name, x=None, y=None, z=None, rot=None, expr=None):
        lcs = doc.addObject("App::LocalCoordinateSystem", name)
        if x is not None: lcs.Placement.Base.x = x
        if y is not None: lcs.Placement.Base.y = y
        if z is not None: lcs.Placement.Base.z = z
        if rot is not None: lcs.Placement.Rotation = rot
        if expr:
            for path, e in expr.items():
                lcs.setExpression(path, e)
        root.addObject(lcs)
        created.append(name)
        return lcs

    add_lcs("CS_SPACECRAFT_BODY")
    add_lcs("PLANE_X_INTERFACE_REF", expr={"Placement.Base.x": "SSOT_PARAMS.X_INTERFACE_REF"})
    add_lcs("PLANE_X_TSM_DYNAMICS", expr={"Placement.Base.x": "SSOT_PARAMS.T_SM_DYNAMICS_X"})
    add_lcs("PLANE_X_MOUNT_FACE", expr={"Placement.Base.x": "SSOT_PARAMS.MOUNT_FACE_X"})
    add_lcs("PLANE_LONGERON_PY", expr={"Placement.Base.y": "SSOT_PARAMS.LONGERON_AXIS_Y"})
    add_lcs("PLANE_LONGERON_NY", expr={"Placement.Base.y": "-SSOT_PARAMS.LONGERON_AXIS_Y"})
    add_lcs("PLANE_LOAD_LAYER", expr={"Placement.Base.y": "SSOT_PARAMS.LOAD_LAYER_Y"})
    add_lcs("PLANE_PANEL_LAYER", expr={"Placement.Base.y": "SSOT_PARAMS.PANEL_LAYER_Y"})
    add_lcs("PLANE_HISTORICAL_NO_DRIVE", expr={"Placement.Base.y": "SSOT_PARAMS.HISTORICAL_Y"})

    cs_b601 = add_lcs("CS_B601_BASE_FRAME",
                      rot=App.Rotation(App.Vector(1, 0, 0), 0.0),
                      expr={"Placement.Base.x": "SSOT_PARAMS.MOUNT_FACE_X",
                            "Placement.Rotation.Angle": "SSOT_PARAMS.CLOCK_A0_RAD"})
    add_lcs("AXIS_B601_INTERFACE_D100",
            expr={"Placement.Base.x": "SSOT_PARAMS.MOUNT_FACE_X"})

    circ = doc.addObject("Part::Circle", "INTF_CIRCLE_D100")
    circ.Radius = 50.0
    circ.setExpression("Radius", "SSOT_PARAMS.B601_INTERFACE_DIA/2")
    circ.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90))
    circ.setExpression("Placement.Base.x", "SSOT_PARAMS.MOUNT_FACE_X")
    root.addObject(circ); created.append("INTF_CIRCLE_D100")

    for tag in ("AFT", "MID", "FWD"):
        add_lcs("CS_SADDLE_%s" % tag,
                expr={"Placement.Base.x": "SSOT_PARAMS.SADDLE_%s_X_CENTER" % tag,
                      "Placement.Base.y": "SSOT_PARAMS.SADDLE_%s_Y_CENTER" % tag,
                      "Placement.Base.z": "SSOT_PARAMS.SADDLE_%s_CONTACT_Z" % tag})

    doc.recompute()
    doc.saveAs(OUT_FCSTD)

    solids = 0
    for o in doc.Objects:
        if hasattr(o, "Shape") and o.Shape and len(o.Shape.Solids) > 0:
            solids += len(o.Shape.Solids)
    App.closeDocument(DOC_NAME)
    return {"doc": DOC_NAME, "fcstd": OUT_FCSTD, "params": len(NUMERIC_PARAMS) + len(STRING_PARAMS),
            "datums": created, "solid_count": solids}

if __name__ == "__main__" or True:
    res = build()
    res["sha256"] = fc_common.sha256_file(OUT_FCSTD)
    path = fc_common.write_json(res, "build_master_skeleton_result.json")
    print("RESULT_JSON=" + path)
    print(json.dumps(res, indent=2, ensure_ascii=False))
