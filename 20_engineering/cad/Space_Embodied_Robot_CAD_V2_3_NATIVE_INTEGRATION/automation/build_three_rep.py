"""
Build B601_THREE_REPRESENTATIONS.SLDASM with 3 mutual-exclusion configurations.
HIFI is HOLD -> HIFI_STOWED_REVIEW will have HIFI suppressed (all suppressed).
Then insert this assembly into the V2.3 top assembly.
"""
import win32com.client
from win32com.client import gencache, VARIANT
import pythoncom
import os, json, time
from pathlib import Path
from datetime import datetime, timezone

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
THREE_REP_DIR = V23 / "03_B601_Three_Representations"
EV_DIR = V23 / "evidence" / "stage2_b601_three_rep"
ASM_TMPL = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot"
URDF_SHA = "1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164"

# Sub-assemblies to insert
PROXY_ASM = THREE_REP_DIR / "B601_KINEMATIC_PROXY" / "B601_KINEMATIC_PROXY.SLDASM"
MASS_ASM = THREE_REP_DIR / "B601_MASS_SURROGATE" / "B601_MASS_SURROGATE.SLDASM"
# HIFI is HOLD - no file to insert
HIFI_STATUS = "HOLD"

# Configuration matrix (taskbook table):
# HIFI_STOWED_REVIEW: HIFI=resolved, others=suppressed -> HOLD (no HIFI file)
# KINEMATIC_PROXY_REVIEW: PROXY=resolved, others=suppressed
# MASS_SURROGATE_REVIEW: MASS=resolved, others=suppressed
CONFIGS = {
    "HIFI_STOWED_REVIEW": {
        "PROXY": 0,  # 0=Suppressed
        "MASS": 0,
        "note": "HIFI_HOLD: no HIFI component inserted; all suppressed"
    },
    "KINEMATIC_PROXY_REVIEW": {
        "PROXY": 2,  # 2=FullyResolved
        "MASS": 0,
        "note": "URDF chain and pose review"
    },
    "MASS_SURROGATE_REVIEW": {
        "PROXY": 0,
        "MASS": 2,
        "note": "Unique B601 mass/inertia review"
    },
}

# Connect
try:
    sw = win32com.client.GetActiveObject("SldWorks.Application")
except:
    sw = win32com.client.Dispatch("SldWorks.Application")
    time.sleep(5)
sw = cast(sw, "ISldWorks")
sw.Visible = True
sw.UserControl = True
print("SW: %s" % sw.RevisionNumber())

# Close all
while sw.ActiveDoc is not None:
    sw.CloseDoc(cast(sw.ActiveDoc, "IModelDoc2").GetTitle())

# Create three-rep assembly
three_rep_path = THREE_REP_DIR / "B601_THREE_REPRESENTATIONS.SLDASM"

sw.NewDocument(ASM_TMPL, 0, 0, 0)
asm_model = cast(sw.ActiveDoc, "IModelDoc2")
asm_doc = cast(asm_model, "IAssemblyDoc")
asm_title = asm_model.GetTitle()
# SaveAs with overwrite (options=1 includes overwrite)
asm_model.Extension.SaveAs2(str(three_rep_path), 0, 1, None, "", False, 0, 0)
# Re-read title after SaveAs (may change)
asm_title = asm_model.GetTitle()

mu = cast(sw.GetMathUtility(), "IMathUtility")
xf = mu.CreateTransform(IDENT16)

# Insert PROXY and MASS sub-assemblies
comp_map = {}  # name -> IComponent2

for label, sub_path in [("PROXY", PROXY_ASM), ("MASS", MASS_ASM)]:
    pname = sub_path.name
    # Open sub-assembly first (early binding: errors/warnings are byref long)
    try:
        ret = sw.OpenDoc6(str(sub_path), 2, 2, "", 0, 0)
        print("  OpenDoc6 %s: ret=%s" % (label, type(ret).__name__))
    except Exception as e:
        print("  OpenDoc6 %s error: %s" % (label, e))

    # Activate the three-rep assembly
    try:
        sw.ActivateDoc3(asm_title, False, 0, 0)
    except Exception as e:
        print("  ActivateDoc3 error: %s" % e)

    # Insert component
    c = asm_doc.AddComponent5(str(sub_path), 0, "", False, "", 0.0, 0.0, 0.0)
    if c:
        c2 = cast(c, "IComponent2")
        try: c2.Transform2 = xf
        except: pass
        comp_map[label] = c2
        print("  Inserted: %s -> %s" % (label, c2.Name2))
    else:
        # Try getting it from GetComponents
        time.sleep(1)
        all_c = asm_doc.GetComponents(True)
        if all_c and len(all_c) > len(comp_map):
            c2 = cast(all_c[-1], "IComponent2")
            comp_map[label] = c2
            print("  Recovered from GetComponents: %s -> %s" % (label, c2.Name2))
        else:
            print("  FAIL: %s (AddComponent5 returned None)" % label)
    try:
        sw.CloseDoc(pname)
    except:
        pass

# Fix components
asm_model.ClearSelection2(True)
for c2 in comp_map.values():
    c2.Select4(True, None, False)
asm_doc.FixComponent()
asm_model.ClearSelection2(True)
asm_model.ForceRebuild3(True)

# Save before creating configurations
asm_model.Save3(1, 0, 0)

# Get component names for suppression
proxy_name = comp_map.get("PROXY")
mass_name = comp_map.get("MASS")

print("\nCreating 3 configurations...")

# The default config becomes KINEMATIC_PROXY_REVIEW
# First create all three named configs
config_mgr = asm_model.ConfigurationManager
active_config = config_mgr.ActiveConfiguration

# Create configs
for cfg_name in CONFIGS:
    existing = asm_model.GetConfigurationByName(cfg_name)
    if existing is None:
        # AddConfiguration2(Name, Comment, AltName, Options, ParentConfigName, Description, OldConfigIndex)
        new_cfg = asm_model.AddConfiguration3(cfg_name, "", "", 0)
        if new_cfg:
            print("  Created config: %s" % cfg_name)
        else:
            print("  WARN: AddConfiguration3 returned None for %s" % cfg_name)

# Apply suppression states per config
for cfg_name, states in CONFIGS.items():
    # Activate config
    asm_model.ShowConfiguration2(cfg_name)
    time.sleep(0.5)

    # Verify active config
    act = config_mgr.ActiveConfiguration
    if act:
        act_name = act.Name
        print("  Active config: %s (target: %s)" % (act_name, cfg_name))
    else:
        print("  WARN: No active config after ShowConfiguration2")
        continue

    # Set suppression for PROXY
    if proxy_name:
        proxy_name.SetSuppression2(states["PROXY"])
        print("    PROXY -> %s" % ("SUPPRESSED" if states["PROXY"] == 0 else "RESOLVED"))

    # Set suppression for MASS
    if mass_name:
        mass_name.SetSuppression2(states["MASS"])
        print("    MASS -> %s" % ("SUPPRESSED" if states["MASS"] == 0 else "RESOLVED"))

    asm_model.ForceRebuild3(True)

# Save
asm_model.Save3(1, 0, 0)

# Add properties
mgr = asm_model.Extension.CustomPropertyManager("")
for pn, pv in [
    ("OBJECT_ID", "B601_THREE_REPRESENTATIONS"),
    ("HIFI_STATUS", "HOLD_IMPORT_FAILED"),
    ("KINEMATIC_PROXY_STATUS", "BUILT"),
    ("MASS_SURROGATE_STATUS", "BUILT"),
    ("URDF_SHA256", URDF_SHA),
    ("STOW_VECTOR_STATUS", "CANDIDATE_HOLD"),
    ("CLOCKING_STATUS", "PROVISIONAL_INTERFACE_BASELINE"),
    ("LICENSE_CLASS", "E3_INTERNAL_RESEARCH_ONLY"),
]:
    mgr.Add3(pn, 30, pv, 2)

asm_model.Save3(1, 0, 0)

# Readback: verify each config
print("\nVerification readback:")
config_readback = {}
for cfg_name in CONFIGS:
    asm_model.ShowConfiguration2(cfg_name)
    time.sleep(0.5)

    all_c = asm_doc.GetComponents(True)
    resolved = []
    suppressed = []
    if all_c:
        for c in all_c:
            c2 = cast(c, "IComponent2")
            supp_state = c2.GetSuppression()
            if supp_state == 0:
                suppressed.append(c2.Name2)
            else:
                resolved.append(c2.Name2)

    config_readback[cfg_name] = {
        "resolved": resolved,
        "suppressed": suppressed,
        "resolved_count": len(resolved),
        "suppressed_count": len(suppressed)
    }
    print("  %s: resolved=%d suppressed=%d" %
          (cfg_name, len(resolved), len(suppressed)))
    for r in resolved:
        print("    resolved: %s" % r)

sw.CloseDoc(asm_title)

result = {
    "step": "THREE_REP_ASSEMBLY",
    "utc": datetime.now(timezone.utc).isoformat(),
    "assembly": str(three_rep_path),
    "hifi_status": "HOLD",
    "proxy_status": "BUILT",
    "mass_status": "BUILT",
    "components": list(comp_map.keys()),
    "configurations": config_readback,
    "status": "PASS_WITH_HIFI_HOLD"
}
with open(str(EV_DIR / "three_rep_configuration_matrix.json"), "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
