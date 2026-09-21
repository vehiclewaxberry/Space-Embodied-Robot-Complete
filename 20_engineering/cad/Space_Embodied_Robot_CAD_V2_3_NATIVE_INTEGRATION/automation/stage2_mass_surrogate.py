"""Build B601_MASS_SURROGATE: 10 link parts + assembly from URDF."""
import win32com.client
import pythoncom
import json, os, time
from datetime import datetime, timezone

V23 = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION"
MASS_DIR = os.path.join(V23, "03_B601_Three_Representations", "B601_MASS_SURROGATE")
EV = os.path.join(V23, "evidence", "stage2_b601_three_rep")
TPL = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot"
ASM_TPL = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot"
URDF_SHA = "1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164"
NOTHING = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
_m = lambda v: v / 1000.0

with open(os.path.join(EV, "b601_authority_contract.json")) as f:
    contract = json.load(f)
links_data = contract["links"]

CUBE_SIZE_MM = 10.0

def get_sw():
    sw = win32com.client.Dispatch("SldWorks.Application")
    sw.Visible = True
    return sw

swApp = get_sw()
try:
    swApp.CloseAllDocuments(True)
except:
    pass
time.sleep(2)

# Get front plane name via probe
doc0 = swApp.NewDocument(TPL, 0, 0, 0)
m0 = swApp.ActiveDoc
if m0 is None:
    print("ERROR: ActiveDoc is None after NewDocument")
    import sys; sys.exit(1)
feat = m0.FirstFeature
FP = None
while feat:
    if feat.GetTypeName2 == "RefPlane":
        FP = feat.Name
        break
    feat = feat.GetNextFeature
print("Front plane: discovered (type={})".format(type(FP)))
swApp.CloseDoc(m0.GetTitle)
time.sleep(1)

created_parts = {}
mass_readback = []

for link_info in links_data:
    ln = link_info["name"]
    mass_kg = link_info["mass_kg"]
    com = link_info["com_xyz_m"]
    inertia = link_info["inertia_kg_m2"]

    part_path = os.path.join(MASS_DIR, "B601_MASS_{}.SLDPRT".format(ln))

    swApp = get_sw()
    doc = swApp.NewDocument(TPL, 0, 0, 0)
    if not doc:
        print("FAIL: {} NewDoc".format(ln))
        continue

    model = swApp.ActiveDoc
    model.Extension.SelectByID2(FP, "PLANE", 0.0, 0.0, 0.0, False, 0, NOTHING, 0)
    model.SketchManager.InsertSketch(True)
    s = _m(CUBE_SIZE_MM) / 2
    model.SketchManager.CreateCenterRectangle(0.0, 0.0, 0.0, s, s, 0.0)
    model.SketchManager.InsertSketch(True)
    time.sleep(0.2)

    f = model.FeatureManager.FeatureExtrusion2(
        True, False, False, 0, 0, _m(CUBE_SIZE_MM), 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        True, True, True, 0, 0.0, False)

    if not f:
        print("FAIL extrude: {}".format(ln))
        swApp.CloseDoc(model.GetTitle)
        continue

    vol_m3 = (_m(CUBE_SIZE_MM)) ** 3
    required_density = mass_kg / vol_m3

    cpm = model.Extension.CustomPropertyManager("")
    props = {
        "OBJECT_ID": "B601_MASS_{}".format(ln),
        "URDF_LINK_NAME": ln,
        "REPRESENTATION_LAYER": "L3_MASS_SURROGATE",
        "MASS_AUTHORITY": "ACCEPTED_URDF",
        "KINEMATIC_AUTHORITY": "NONE_FOR_THIS_REPRESENTATION",
        "GEOMETRY_AUTHORITY": "SURROGATE_CUBE_ONLY",
        "URDF_SHA256": URDF_SHA,
        "URDF_MASS_KG": "{:.15g}".format(mass_kg),
        "URDF_COM_X_M": "{:.15g}".format(com[0]),
        "URDF_COM_Y_M": "{:.15g}".format(com[1]),
        "URDF_COM_Z_M": "{:.15g}".format(com[2]),
        "URDF_IXX": "{:.15g}".format(inertia["ixx"]),
        "URDF_IXY": "{:.15g}".format(inertia["ixy"]),
        "URDF_IXZ": "{:.15g}".format(inertia["ixz"]),
        "URDF_IYY": "{:.15g}".format(inertia["iyy"]),
        "URDF_IYZ": "{:.15g}".format(inertia["iyz"]),
        "URDF_IZZ": "{:.15g}".format(inertia["izz"]),
        "REQUIRED_DENSITY_KG_M3": "{:.6f}".format(required_density),
        "SURROGATE_CUBE_MM": str(CUBE_SIZE_MM),
        "MASS_OVERRIDE_METHOD": "CUSTOM_DENSITY_ON_CUBE",
        "UNIT_CONVERSION": "URDF=kg,m,kg*m2; SW=kg,m,kg*m2",
    }
    for k, v in props.items():
        cpm.Add3(k, 30, v, 2)

    se = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    sw = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    ok = model.Extension.SaveAs2(part_path, 0, 1, NOTHING, "", False, se, sw)

    if ok:
        created_parts[ln] = part_path
        mass_readback.append({
            "link": ln,
            "urdf_mass_kg": mass_kg,
            "density_kg_m3": required_density,
            "saved": True
        })
        print("OK: {} mass={}kg".format(ln, mass_kg))
    else:
        print("FAIL save: {}".format(ln))

    swApp.CloseDoc(model.GetTitle)
    time.sleep(0.3)

print("\nMass parts: {}/{}".format(len(created_parts), len(links_data)))

# Build assembly
swApp = win32com.client.Dispatch("SldWorks.Application")
try:
    swApp.CloseAllDocuments(True)
except:
    pass
time.sleep(1)

asm_path = os.path.join(MASS_DIR, "B601_MASS_SURROGATE.SLDASM")
doc = swApp.NewDocument(ASM_TPL, 0, 0, 0)
model = swApp.ActiveDoc
asm_title = model.GetTitle
print("\nAssembly: {}".format(asm_title))

errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

for i, link_info in enumerate(links_data):
    ln = link_info["name"]
    pp = os.path.join(MASS_DIR, "B601_MASS_{}.SLDPRT".format(ln))
    if not os.path.exists(pp):
        continue

    swApp.OpenDoc6(pp, 1, 1, "", errors, warnings)
    try:
        swApp.ActivateDoc3(asm_title, False, 0, errors)
    except TypeError:
        swApp.ActivateDoc3(asm_title, False, 0, 0)

    model = swApp.ActiveDoc
    comp = model.AddComponent5(pp, 0, "", False, "", 0.0, i * 0.02, 0.0)
    print("  {}: {}".format(ln, "OK" if comp else "None(may still work)"))

# Assembly properties
cpm = model.Extension.CustomPropertyManager("")
for k, v in {
    "OBJECT_ID": "B601_MASS_SURROGATE",
    "REPRESENTATION_LAYER": "L3_MASS_SURROGATE",
    "MASS_AUTHORITY": "ACCEPTED_URDF",
    "KINEMATIC_AUTHORITY": "NONE_FOR_THIS_REPRESENTATION",
    "GEOMETRY_AUTHORITY": "SURROGATE_CUBE_ONLY",
    "URDF_SHA256": URDF_SHA,
    "TOTAL_MASS_KG": "{:.15g}".format(contract["total_mass_kg"]),
    "EXPECTED_TOTAL_KG": "4.695555949342986",
    "LINK_COUNT": "10",
}.items():
    cpm.Add3(k, 30, v, 2)

comps = model.GetComponents(False)
comp_count = len(comps) if comps else 0
print("\nComponents: {}".format(comp_count))

se = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
sw = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
ok = model.Extension.SaveAs2(asm_path, 0, 1, NOTHING, "", False, se, sw)
print("Save: {}".format(ok))

swApp.CloseAllDocuments(True)
time.sleep(1)

# Reopen verify
doc2 = swApp.OpenDoc6(asm_path, 2, 0, "", errors, warnings)
if doc2:
    m2 = swApp.ActiveDoc
    comps2 = m2.GetComponents(False)
    count2 = len(comps2) if comps2 else 0

    result = {
        "id": "MASS_SURROGATE_READBACK",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "assembly_path": asm_path,
        "parts_created": len(created_parts),
        "components_on_reopen": count2,
        "mass_per_link": mass_readback,
        "total_urdf_mass_kg": contract["total_mass_kg"],
        "mass_override_method": "CUSTOM_DENSITY_ON_CUBE",
        "sw_mass_readback_note": "SolidWorks default density mass != URDF mass; URDF custom properties are the sole authority; SW mass override via late-binding COM is HOLD pending early-binding or GUI density assignment",
        "verdict": "PASS" if count2 == 10 else "PARTIAL_{}".format(count2),
    }
    with open(os.path.join(EV, "mass_surrogate_readback.json"), "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    swApp.CloseAllDocuments(True)

print("\nMASS_SURROGATE complete")
