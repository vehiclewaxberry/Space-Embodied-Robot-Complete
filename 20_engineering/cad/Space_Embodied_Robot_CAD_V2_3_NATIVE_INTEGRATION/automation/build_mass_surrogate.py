"""
Build B601_MASS_SURROGATE: 10 link parts with URDF mass properties.

Strategy: Create each link as a cube with side = (mass / default_density)^(1/3).
The default density in SolidWorks gb_part template was measured at 500 kg/m3.
This gives exact mass readback.

COM/inertia from URDF stored as custom properties only (cube geometry
cannot represent arbitrary COM/inertia tensors).
"""
import win32com.client
from win32com.client import gencache, VARIANT
import pythoncom
import os, json, time, subprocess, math
from pathlib import Path
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

_sw_mod = gencache.EnsureModule("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)

def cast(obj, iface):
    if obj is None: return None
    try:
        klass = getattr(_sw_mod, iface)
        ole = obj._oleobj_.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
        return klass(ole)
    except: return obj

IDENT16 = [1.0,0,0, 0,1.0,0, 0,0,1.0, 0,0,0, 1.0,0,0,0]

V23 = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION")
MASS_DIR = V23 / "03_B601_Three_Representations" / "B601_MASS_SURROGATE"
EV_DIR = V23 / "evidence" / "stage2_b601_three_rep"
PART_TMPL = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot"
ASM_TMPL = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot"
URDF_PATH = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf")
URDF_SHA = "1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164"

# Measured default density from gb_part template (0.0005 kg for 10mm cube = 500 kg/m3)
DEFAULT_DENSITY = 500.0  # kg/m3

# Parse URDF
tree = ET.parse(URDF_PATH)
root = tree.getroot()
links_data = []
for link_el in root.findall("link"):
    name = link_el.get("name")
    iner = link_el.find("inertial")
    if iner is None: continue
    org = iner.find("origin")
    xyz = [float(v) for v in org.get("xyz").split()]
    mass = float(iner.find("mass").get("value"))
    ie = iner.find("inertia")
    inertia = {k: float(ie.get(k)) for k in ["ixx","ixy","ixz","iyy","iyz","izz"]}
    # Compute cube side for target mass at default density
    vol = mass / DEFAULT_DENSITY  # m^3
    side = vol ** (1.0/3.0)  # m
    links_data.append({"name": name, "mass": mass, "com": xyz, "inertia": inertia,
                       "cube_side_m": side, "cube_vol_m3": vol})

def get_sw():
    try:
        sw = win32com.client.GetActiveObject("SldWorks.Application")
    except:
        sw = win32com.client.Dispatch("SldWorks.Application")
        time.sleep(3)
    sw = cast(sw, "ISldWorks")
    sw.Visible = True
    sw.UserControl = True
    return sw

def close_all(sw):
    for _ in range(20):
        d = sw.ActiveDoc
        if d is None: break
        try: sw.CloseDoc(cast(d, "IModelDoc2").GetTitle())
        except: break

sw = get_sw()
close_all(sw)
print("SW: %s" % sw.RevisionNumber())

created_parts = []

for idx, ld in enumerate(links_data):
    fname = "MASS_%s.SLDPRT" % ld["name"]
    fpath = str(MASS_DIR / fname)

    # Skip if already exists (reentrant)
    if os.path.exists(fpath):
        print("  SKIP (exists): %s" % fname)
        # Still need readback - open and check
        try:
            prt = sw.OpenDoc6(fpath, 1, 0, "", 0, 0)
            if isinstance(prt, tuple): prt = prt[0]
            model = cast(prt if prt else sw.ActiveDoc, "IModelDoc2")
            mp = model.Extension.CreateMassProperty()
            rb_mass = mp.Mass if mp else -1
            sw.CloseDoc(model.GetTitle())
            created_parts.append({
                "link": ld["name"], "file": fname,
                "urdf_mass_kg": ld["mass"], "readback_mass_kg": rb_mass,
                "mass_error_kg": abs(rb_mass - ld["mass"]),
                "reused": True
            })
            print("    readback=%.10f err=%.2e" % (rb_mass, abs(rb_mass - ld["mass"])))
        except Exception as e:
            created_parts.append({"link": ld["name"], "file": fname, "error": str(e), "reused": True})
            print("    readback failed: %s" % e)
        continue

    try:
        sw.NewDocument(PART_TMPL, 0, 0, 0)
        model = cast(sw.ActiveDoc, "IModelDoc2")
        ext = model.Extension

        ext.SelectByID2("\u524d\u89c6\u57fa\u51c6\u9762", "PLANE", 0, 0, 0, False, 0, None, 0)
        model.SketchManager.InsertSketch(True)

        hs = ld["cube_side_m"] / 2  # half-side
        model.SketchManager.CreateCenterRectangle(0, 0, 0, hs, hs, 0)
        model.SketchManager.InsertSketch(True)

        model.FeatureManager.FeatureExtrusion2(
            True, False, False, 6, 0, hs, 0, False, False, False,
            False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
        model.ForceRebuild3(True)

        # Custom properties
        mgr = ext.CustomPropertyManager("")
        cx, cy, cz = ld["com"]
        i = ld["inertia"]
        props = [
            ("OBJECT_ID", "MASS_%s" % ld["name"]),
            ("REPRESENTATION_LAYER", "L3_MASS_SURROGATE"),
            ("MASS_AUTHORITY", "ACCEPTED_URDF"),
            ("KINEMATIC_AUTHORITY", "NONE_FOR_THIS_REPRESENTATION"),
            ("GEOMETRY_AUTHORITY", "CARRIER_ONLY"),
            ("URDF_SHA256", URDF_SHA),
            ("URDF_LINK_NAME", ld["name"]),
            ("URDF_MASS_KG", "%.15g" % ld["mass"]),
            ("URDF_COM_XYZ_M", "%s,%s,%s" % (cx, cy, cz)),
            ("URDF_IXX", "%.15g" % i["ixx"]),
            ("URDF_IXY", "%.15g" % i["ixy"]),
            ("URDF_IXZ", "%.15g" % i["ixz"]),
            ("URDF_IYY", "%.15g" % i["iyy"]),
            ("URDF_IYZ", "%.15g" % i["iyz"]),
            ("URDF_IZZ", "%.15g" % i["izz"]),
            ("CUBE_SIDE_M", "%.15g" % ld["cube_side_m"]),
            ("CUBE_VOLUME_M3", "%.15g" % ld["cube_vol_m3"]),
            ("ASSUMED_DENSITY_KG_M3", "%.15g" % DEFAULT_DENSITY),
            ("MASS_METHOD", "VOLUME_SIZED_AT_DEFAULT_DENSITY"),
            ("COM_INERTIA_NOTE", "COM/inertia in properties only; cube COM/MOI != URDF"),
            ("LICENSE_CLASS", "E3_INTERNAL_RESEARCH_ONLY"),
        ]
        for pn, pv in props:
            mgr.Add3(pn, 30, pv, 2)

        model.Extension.SaveAs2(fpath, 0, 1, None, "", False, 0, 0)

        mp = ext.CreateMassProperty()
        rb_mass = mp.Mass if mp else -1

        sw.CloseDoc(model.GetTitle())
        err = abs(rb_mass - ld["mass"])
        created_parts.append({
            "link": ld["name"], "file": fname,
            "urdf_mass_kg": ld["mass"], "readback_mass_kg": rb_mass,
            "cube_side_mm": ld["cube_side_m"] * 1000,
            "mass_error_kg": err, "reused": False
        })
        print("  OK: %s side=%.3fmm urdf=%.6f rb=%.10f err=%.2e" %
              (fname, ld["cube_side_m"]*1000, ld["mass"], rb_mass, err))

    except Exception as e:
        created_parts.append({"link": ld["name"], "error": str(e), "reused": False})
        print("  ERR: %s: %s" % (ld["name"], e))
        # Reconnect if COM died
        try: close_all(sw)
        except: pass
        try:
            sw = get_sw()
            close_all(sw)
        except:
            print("  FATAL: Cannot reconnect to SolidWorks")
            break

# Count how many parts were successfully created
ok_parts = [p for p in created_parts if "error" not in p]
print("\nParts: %d/%d created" % (len(ok_parts), len(links_data)))

if len(ok_parts) < 10:
    print("Not all parts created - skipping assembly")
    result = {
        "step": "MASS_SURROGATE_PARTS_ONLY",
        "utc": datetime.now(timezone.utc).isoformat(),
        "parts": created_parts,
        "parts_ok": len(ok_parts),
        "status": "PARTIAL"
    }
    with open(str(EV_DIR / "mass_surrogate_readback.json"), "w") as f:
        json.dump(result, f, indent=2)
    exit(0 if len(ok_parts) > 0 else 1)

# ---- Assembly ----
print("\nBuilding MASS_SURROGATE assembly...")
close_all(sw)

asm_path = MASS_DIR / "B601_MASS_SURROGATE.SLDASM"
if asm_path.exists():
    os.remove(asm_path)

sw.NewDocument(ASM_TMPL, 0, 0, 0)
asm_model = cast(sw.ActiveDoc, "IModelDoc2")
asm_doc = cast(asm_model, "IAssemblyDoc")
asm_title = asm_model.GetTitle()
asm_model.Extension.SaveAs2(str(asm_path), 0, 1, None, "", False, 0, 0)

mu = cast(sw.GetMathUtility(), "IMathUtility")
xf = mu.CreateTransform(IDENT16)

comps = []
for ld in links_data:
    prt_path = str(MASS_DIR / ("MASS_%s.SLDPRT" % ld["name"]))
    prt_fname = "MASS_%s.SLDPRT" % ld["name"]
    try:
        r = sw.OpenDoc6(prt_path, 1, 2, "", 0, 0)
    except:
        continue
    try:
        sw.ActivateDoc3(asm_title, False, 0, 0)
    except:
        pass
    c = asm_doc.AddComponent5(prt_path, 0, "", False, "", 0.0, 0.0, 0.0)
    if c:
        c2 = cast(c, "IComponent2")
        try: c2.Transform2 = xf
        except: pass
        comps.append(c2)
        print("  Inserted: %s" % ld["name"])
    sw.CloseDoc(prt_fname)

asm_model.ClearSelection2(True)
for c2 in comps:
    c2.Select4(True, None, False)
asm_doc.FixComponent()
asm_model.ClearSelection2(True)
asm_model.ForceRebuild3(True)

mgr = asm_model.Extension.CustomPropertyManager("")
for pn, pv in [
    ("OBJECT_ID", "B601_MASS_SURROGATE"),
    ("REPRESENTATION_LAYER", "L3_MASS_SURROGATE"),
    ("MASS_AUTHORITY", "ACCEPTED_URDF"),
    ("KINEMATIC_AUTHORITY", "NONE_FOR_THIS_REPRESENTATION"),
    ("GEOMETRY_AUTHORITY", "CARRIER_ONLY"),
    ("URDF_SHA256", URDF_SHA),
    ("EXPECTED_TOTAL_MASS_KG", "4.695555949342986"),
    ("LICENSE_CLASS", "E3_INTERNAL_RESEARCH_ONLY"),
]:
    mgr.Add3(pn, 30, pv, 2)

asm_model.Save3(1, 0, 0)

mp = asm_model.Extension.CreateMassProperty()
total_mass = mp.Mass if mp else -1
error_kg = abs(total_mass - 4.695555949342986)

all_c = asm_doc.GetComponents(True)
n = len(all_c) if all_c else 0

print("\nMASS_SURROGATE: %d comps, total=%.15g kg, err=%.3e" % (n, total_mass, error_kg))

sw.CloseDoc(asm_title)

result = {
    "step": "MASS_SURROGATE",
    "utc": datetime.now(timezone.utc).isoformat(),
    "assembly": str(asm_path),
    "parts": created_parts,
    "components": n,
    "total_mass_kg": total_mass,
    "expected_mass_kg": 4.695555949342986,
    "error_kg": error_kg,
    "tolerance_1e9_met": error_kg <= 1e-9,
    "default_density_kg_m3": DEFAULT_DENSITY,
    "mass_method": "VOLUME_SIZED_CUBE_AT_DEFAULT_DENSITY",
    "com_inertia_note": "COM and inertia stored in custom properties only",
    "status": "PASS" if n == 10 else "COUNT_%d" % n
}
with open(str(EV_DIR / "mass_surrogate_readback.json"), "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
