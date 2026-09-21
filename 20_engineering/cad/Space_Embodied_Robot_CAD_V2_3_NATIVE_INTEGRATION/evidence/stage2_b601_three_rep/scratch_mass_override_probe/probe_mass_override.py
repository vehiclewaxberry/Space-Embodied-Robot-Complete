"""
NATIVE-MECH-REAL-01 Stage 2 — Single-part native override probe.

Creates a scratch part, applies mass/COM/inertia overrides via
IMassProperty2 + IMassPropertyOverrideOptions, saves, closes,
reopens, and reads back. Every API return value is recorded.
"""

import json, os, sys, time, hashlib, datetime

# --- constants for the probe ---
PROBE_MASS_KG = 1.2345
PROBE_COM_M = [0.01, 0.02, 0.03]
PROBE_INERTIA_KG_M2 = {
    "ixx": 0.001, "ixy": 0.0001, "ixz": 0.0002,
    "iyy": 0.002, "iyz": 0.0003,
    "izz": 0.003
}
# Full 3x3 symmetric tensor (row-major)
PROBE_I9 = [
    PROBE_INERTIA_KG_M2["ixx"], PROBE_INERTIA_KG_M2["ixy"], PROBE_INERTIA_KG_M2["ixz"],
    PROBE_INERTIA_KG_M2["ixy"], PROBE_INERTIA_KG_M2["iyy"], PROBE_INERTIA_KG_M2["iyz"],
    PROBE_INERTIA_KG_M2["ixz"], PROBE_INERTIA_KG_M2["iyz"], PROBE_INERTIA_KG_M2["izz"],
]

PROBE_DIR = os.path.dirname(os.path.abspath(__file__))
PROBE_PART_NAME = "SCRATCH_MASS_OVERRIDE_PROBE"
PROBE_PART_PATH = os.path.join(PROBE_DIR, PROBE_PART_NAME + ".SLDPRT")

# SolidWorks constants
swDocPART = 1
swSaveAsCurrentVersion = 0
swSaveAsOptions_Silent = 1
swSaveAsOptions_SaveReferenced = 2
swCloseOptions_Silent = 1

def log_step(log, step_name, result, detail=None):
    entry = {"step": step_name, "result": result}
    if detail is not None:
        entry["detail"] = detail
    log.append(entry)
    print(f"  [{result}] {step_name}" + (f" — {detail}" if detail else ""))
    return result

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def main():
    import win32com.client
    from win32com.client import VARIANT
    import pythoncom

    log = []
    result = {"probe": "SCRATCH_MASS_OVERRIDE_PROBE", "utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}

    # ---- Step 0: Connect to SolidWorks ----
    try:
        sw = win32com.client.Dispatch("SldWorks.Application")
        pid = sw.GetProcessID
        log_step(log, "com_connect", True, f"PID={pid}")
    except Exception as e:
        log_step(log, "com_connect", False, str(e))
        result["log"] = log
        result["status"] = "HOLD_COM_CONNECT_FAILED"
        return result

    # ---- Step 1: Create a new part ----
    try:
        # Get default part template (PREF 8 = swDefaultTemplatePart)
        template = sw.GetUserPreferenceStringValue(8)
        if not template or not os.path.exists(template):
            # Fallback to known path
            template = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot"
        log_step(log, "template_path", template is not None and template != "", str(template))

        new_doc = sw.NewDocument(template, 0, 0, 0)
        log_step(log, "new_document", new_doc is not None and new_doc != 0, f"type={type(new_doc)}")

        model = sw.ActiveDoc
        log_step(log, "active_doc", model is not None, str(model.GetTitle if model else "None"))
    except Exception as e:
        log_step(log, "create_part", False, str(e))
        result["log"] = log
        result["status"] = "HOLD_PART_CREATION_FAILED"
        return result

    # ---- Step 2: Add minimal geometry (10mm cube) so the part has a body ----
    try:
        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreateCornerRectangle(0, 0, 0, 0.01, 0.01, 0)
        model.SketchManager.InsertSketch(True)
        feat = model.FeatureManager.FeatureExtrusion2(
            True, False, False,  # sd, flip, dir
            0, 0,  # t1=blind, t2
            0.01, 0.01,  # depth1, depth2
            False, False, False, False,
            0, 0,  # draft1, draft2
            False, False, False, False,
            True, True, True,
            0, 0, False
        )
        log_step(log, "create_cube_geometry", feat is not None, f"feat={type(feat)}")
        model.ClearSelection2(True)
    except Exception as e:
        log_step(log, "create_cube_geometry", False, str(e))
        # Try saving even without geometry
        pass

    # ---- Step 3: Save as SLDPRT ----
    try:
        errors_ref = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings_ref = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        save_ok = model.Extension.SaveAs2(
            PROBE_PART_PATH, 0, swSaveAsOptions_Silent, None, "", False,
            errors_ref, warnings_ref
        )
        log_step(log, "save_as_initial", bool(save_ok),
                 f"path={PROBE_PART_PATH}, errors={errors_ref.value}, warnings={warnings_ref.value}")
    except Exception as e:
        log_step(log, "save_as_initial", False, str(e))
        result["log"] = log
        result["status"] = "HOLD_SAVE_FAILED"
        return result

    # ---- Step 4: Apply mass property overrides ----
    override_log = {}
    try:
        ext = model.Extension
        mp = ext.CreateMassProperty2
        log_step(log, "create_mass_property2", mp is not None, f"type={type(mp)}")

        # UseSystemUnits = True (kg, m, kg*m^2)
        mp.UseSystemUnits = True
        log_step(log, "set_use_system_units", True, "UseSystemUnits=True")

        # Get override options
        opt = mp.GetOverrideOptions()
        log_step(log, "get_override_options", opt is not None, f"type={type(opt)}")

        # Override Mass
        opt.OverrideMass = True
        set_mass_ok = opt.SetOverrideMassValue(PROBE_MASS_KG)
        override_log["set_mass"] = {"value": PROBE_MASS_KG, "return": set_mass_ok}
        log_step(log, "set_override_mass", bool(set_mass_ok), f"mass={PROBE_MASS_KG}, ret={set_mass_ok}")

        # Override Center of Mass
        opt.OverrideCenterOfMass = True
        # SetOverrideCenterOfMassValue(double[] comValues, string configName)
        set_com_ok = opt.SetOverrideCenterOfMassValue(PROBE_COM_M, "")
        override_log["set_com"] = {"value": PROBE_COM_M, "return": set_com_ok}
        log_step(log, "set_override_com", bool(set_com_ok), f"com={PROBE_COM_M}, ret={set_com_ok}")

        # Override Moments of Inertia
        opt.OverrideMomentsOfInertia = True
        # SetOverrideMomentsOfInertiaValue(int refFrame, double[] moiValues, string configName)
        # refFrame 0 = center of mass
        set_moi_ok = opt.SetOverrideMomentsOfInertiaValue(0, PROBE_I9, "")
        override_log["set_moi"] = {"value": PROBE_I9, "return": set_moi_ok}
        log_step(log, "set_override_moi", bool(set_moi_ok), f"I9={PROBE_I9}, ret={set_moi_ok}")

        # Apply override options
        # SetOverrideOptions(options, configOption, configNames)
        # configOption 1 = this configuration
        set_opt_ok = mp.SetOverrideOptions(opt, 1, None)
        override_log["set_override_options"] = {"return": set_opt_ok}
        log_step(log, "set_override_options", bool(set_opt_ok), f"ret={set_opt_ok}")

        # Recalculate
        recalc_ok = mp.Recalculate()
        override_log["recalculate"] = {"return": recalc_ok}
        log_step(log, "recalculate", bool(recalc_ok), f"ret={recalc_ok}")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log_step(log, "mass_override_api", False, f"{e}\n{tb}")
        override_log["exception"] = str(e)
        override_log["traceback"] = tb

    result["override_log"] = override_log

    # ---- Step 5: Pre-close readback ----
    pre_close_readback = {}
    try:
        mp2 = ext.CreateMassProperty2
        mp2.UseSystemUnits = True
        opt2 = mp2.GetOverrideOptions()

        pre_close_readback["override_mass_flag"] = bool(opt2.OverrideMass)
        pre_close_readback["override_com_flag"] = bool(opt2.OverrideCenterOfMass)
        pre_close_readback["override_moi_flag"] = bool(opt2.OverrideMomentsOfInertia)

        mass_val = opt2.GetOverrideMassValue
        pre_close_readback["override_mass_value"] = mass_val

        com_val = opt2.GetOverrideCenterOfMassValue("")
        pre_close_readback["override_com_value"] = list(com_val) if com_val else None

        moi_val = opt2.GetOverrideMomentsOfInertiaValue(0, "")
        pre_close_readback["override_moi_value"] = list(moi_val) if moi_val else None

        # Also read calculated values
        mp2.Recalculate()
        pre_close_readback["calculated_mass"] = mp2.Mass
        pre_close_readback["calculated_com"] = list(mp2.CenterOfMass) if mp2.CenterOfMass else None

        # MomentOfInertia returns array relative to output coordinate system
        try:
            moi_calc = mp2.GetMomentOfInertia(0)  # 0 = at COM
            pre_close_readback["calculated_moi"] = list(moi_calc) if moi_calc else None
        except:
            pre_close_readback["calculated_moi"] = "API_NOT_AVAILABLE"

        log_step(log, "pre_close_readback", True, json.dumps(pre_close_readback, indent=None))
    except Exception as e:
        import traceback
        log_step(log, "pre_close_readback", False, f"{e}\n{traceback.format_exc()}")
        pre_close_readback["error"] = str(e)

    result["pre_close_readback"] = pre_close_readback

    # ---- Step 6: Save and close ----
    try:
        save2_ok = model.Save3(swSaveAsOptions_Silent, errors_ref, warnings_ref)
        log_step(log, "save_before_close", bool(save2_ok),
                 f"ret={save2_ok}, errors={errors_ref.value}, warnings={warnings_ref.value}")
    except Exception as e:
        # Try alternative save
        try:
            save2_ok = model.Save()
            log_step(log, "save_before_close_alt", bool(save2_ok), str(save2_ok))
        except Exception as e2:
            log_step(log, "save_before_close", False, str(e2))

    try:
        sw.CloseDoc(model.GetTitle)
        log_step(log, "close_doc", True)
    except Exception as e:
        log_step(log, "close_doc", False, str(e))

    # ---- Step 7: Reopen without restarting SolidWorks ----
    time.sleep(1)  # brief pause

    post_reopen_readback = {}
    try:
        errors_ref2 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings_ref2 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        reopened = sw.OpenDoc6(
            PROBE_PART_PATH, swDocPART, 1, "", errors_ref2, warnings_ref2
        )
        log_step(log, "reopen_doc", reopened is not None,
                 f"errors={errors_ref2.value}, warnings={warnings_ref2.value}")

        model2 = sw.ActiveDoc
        ext2 = model2.Extension
        mp3 = ext2.CreateMassProperty2
        mp3.UseSystemUnits = True
        opt3 = mp3.GetOverrideOptions()

        post_reopen_readback["override_mass_flag"] = bool(opt3.OverrideMass)
        post_reopen_readback["override_com_flag"] = bool(opt3.OverrideCenterOfMass)
        post_reopen_readback["override_moi_flag"] = bool(opt3.OverrideMomentsOfInertia)

        mass_val3 = opt3.GetOverrideMassValue
        post_reopen_readback["override_mass_value"] = mass_val3

        com_val3 = opt3.GetOverrideCenterOfMassValue("")
        post_reopen_readback["override_com_value"] = list(com_val3) if com_val3 else None

        moi_val3 = opt3.GetOverrideMomentsOfInertiaValue(0, "")
        post_reopen_readback["override_moi_value"] = list(moi_val3) if moi_val3 else None

        mp3.Recalculate()
        post_reopen_readback["calculated_mass"] = mp3.Mass
        post_reopen_readback["calculated_com"] = list(mp3.CenterOfMass) if mp3.CenterOfMass else None

        try:
            moi_calc3 = mp3.GetMomentOfInertia(0)
            post_reopen_readback["calculated_moi"] = list(moi_calc3) if moi_calc3 else None
        except:
            post_reopen_readback["calculated_moi"] = "API_NOT_AVAILABLE"

        log_step(log, "post_reopen_readback", True, json.dumps(post_reopen_readback, indent=None))

        # Close the probe part
        sw.CloseDoc(model2.GetTitle)
        log_step(log, "close_probe_after_readback", True)

    except Exception as e:
        import traceback
        log_step(log, "post_reopen_readback", False, f"{e}\n{traceback.format_exc()}")
        post_reopen_readback["error"] = str(e)

    result["post_reopen_readback"] = post_reopen_readback

    # ---- Step 8: Compute SHA-256 of probe part ----
    if os.path.exists(PROBE_PART_PATH):
        result["probe_part_sha256"] = sha256_file(PROBE_PART_PATH)
    result["probe_part_path"] = PROBE_PART_PATH

    # ---- Step 9: Determine PASS/HOLD ----
    try:
        flags_persisted = (
            post_reopen_readback.get("override_mass_flag") == True and
            post_reopen_readback.get("override_com_flag") == True and
            post_reopen_readback.get("override_moi_flag") == True
        )
        mass_matches = abs(post_reopen_readback.get("override_mass_value", 0) - PROBE_MASS_KG) < 1e-12
        com_matches = all(
            abs(a - b) < 1e-12
            for a, b in zip(post_reopen_readback.get("override_com_value", [0,0,0]), PROBE_COM_M)
        )

        # Check inertia
        moi_rb = post_reopen_readback.get("override_moi_value", [0]*9)
        moi_matches = all(abs(a - b) < 1e-15 for a, b in zip(moi_rb, PROBE_I9)) if moi_rb and len(moi_rb) == 9 else False

        probe_pass = flags_persisted and mass_matches and com_matches and moi_matches

        result["probe_checks"] = {
            "flags_persisted": flags_persisted,
            "mass_matches": mass_matches,
            "com_matches": com_matches,
            "moi_matches": moi_matches,
            "mass_error": abs(post_reopen_readback.get("override_mass_value", 0) - PROBE_MASS_KG),
        }

        if probe_pass:
            result["status"] = "PASS_SINGLE_PART_PROBE"
        else:
            result["status"] = "HOLD_SINGLE_PART_PROBE_FAILED"
    except Exception as e:
        result["status"] = "HOLD_SINGLE_PART_PROBE_FAILED"
        result["probe_error"] = str(e)

    result["log"] = log

    # ---- Write result ----
    out_path = os.path.join(PROBE_DIR, "..", "mass_override_probe_readback.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nProbe result written to {out_path}")
    print(f"Status: {result['status']}")

    return result

if __name__ == "__main__":
    r = main()
    sys.exit(0 if r.get("status", "").startswith("PASS") else 1)
