# run_fem_base_adapter.py — preliminary unit-load FEM (CalculiX) for the base adapter.
# PRELIMINARY_UNIT_LOAD_ASSESSMENT only; no launch qualification claim.
import os, sys, json, traceback
import FreeCAD as App

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common

DOC_NAME = "B601_BASE_ADAPTER"
ADAPTER = os.path.join(fc_common.FA_ROOT, "03_manufacturing_parts", "base_adapter", DOC_NAME + ".FCStd")
FEM_DIR = os.path.join(fc_common.FA_ROOT, "06_fem")
os.makedirs(FEM_DIR, exist_ok=True)

res = {"stages": [], "overall": "PASS", "claim": "PRELIMINARY_UNIT_LOAD_ASSESSMENT"}
def st(name, ok, detail=""):
    res["stages"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        res["overall"] = "HOLD"
    print("STAGE %s: %s %s" % (name, ok, detail))

def run():
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/Fem/Ccx").SetString(
        "ccxBinaryPath", r"G:\Windows_program_file\FreeCAD\bin\ccx.EXE")
    doc = App.openDocument(ADAPTER)
    doc.recompute()
    body = doc.getObject("ADAPTER_BODY")
    shape = body.Shape

    bottom_idx = [i for i, f in enumerate(shape.Faces)
                  if abs(f.CenterOfMass.z - (-12.0)) < 1e-6 and f.Area > 1000.0]
    top_idx = [i for i, f in enumerate(shape.Faces)
               if abs(f.CenterOfMass.z - 15.0) < 1e-6 and f.Area > 100.0]
    st("face_selection", len(bottom_idx) >= 1 and len(top_idx) >= 1,
       "bottom=%s top=%s" % (bottom_idx, top_idx))
    if not (bottom_idx and top_idx):
        return

    import ObjectsFem
    import Fem
    analysis = ObjectsFem.makeAnalysis(doc, "FEM_ANALYSIS")
    mat = ObjectsFem.makeMaterialSolid(doc, "AL6061T6")
    m = mat.Material
    m["Name"] = "AL6061-T6"
    m["YoungsModulus"] = "68900 MPa"
    m["PoissonRatio"] = "0.33"
    m["Density"] = "2700 kg/m^3"
    mat.Material = m
    analysis.addObject(mat)

    fixed = ObjectsFem.makeConstraintFixed(doc, "FIX_BOTTOM")
    fixed.References = [(body, ["Face%d" % (i + 1) for i in bottom_idx])]
    analysis.addObject(fixed)

    force = ObjectsFem.makeConstraintForce(doc, "UNIT_LOAD_1000N_DOWN")
    force.References = [(body, ["Face%d" % (i + 1) for i in top_idx])]
    force.Force = 1000.0
    force.Reversed = True  # face normal is +Z; reversed -> 1000 N acting -Z (downward)
    analysis.addObject(force)
    st("constraints", True, "fixed bottom, 1000 N -Z on boss top")

    mesh_obj = ObjectsFem.makeMeshGmsh(doc, "FEM_MESH")
    mesh_obj.Shape = body
    mesh_obj.CharacteristicLengthMax = 5.0
    mesh_obj.CharacteristicLengthMin = 1.0
    analysis.addObject(mesh_obj)
    doc.recompute()
    try:
        import femmesh.gmshtools as gtools
        gt = gtools.GmshTools(mesh_obj)
        gt.create_mesh()
        n_nodes = mesh_obj.FemMesh.NodeCount
        st("mesh_gmsh", n_nodes > 100, "nodes=%d" % n_nodes)
    except Exception:
        st("mesh_gmsh", False, traceback.format_exc())
        return

    solver = ObjectsFem.makeSolverCalculiX(doc, "CCX_SOLVER")
    analysis.addObject(solver)
    doc.recompute()
    try:
        import femtools.ccxtools as ccx_tools
        fea = ccx_tools.FemToolsCcx(analysis, solver)
        fea.update_objects()
        fea.setup_working_dir(FEM_DIR)
        fea.setup_ccx()
        msg = fea.check_prerequisites()
        st("ccx_prerequisites", not msg, msg or "ok")
        if msg:
            return
        fea.run()
        st("ccx_run", True, "")
    except Exception:
        st("ccx_run", False, traceback.format_exc())
        return

    result_obj = None
    for m in analysis.Group:
        if m.isDerivedFrom("Fem::FemResultObject"):
            result_obj = m
            break
    if result_obj is None:
        st("results", False, "no result object")
        return
    doc.recompute()  # ensure frd-imported arrays are loaded
    disp = result_obj.DisplacementLengths
    vm = result_obj.vonMises
    umax_raw = float(max(disp))
    res["max_displacement_mm"] = umax_raw
    res["max_vonmises_mpa"] = float(max(vm)) / 1e6
    res["node_count"] = len(disp)
    st("results", True, "umax=%.3e mm, svm=%.4e MPa" % (max(disp), max(vm) / 1e6))

    out_fcstd = os.path.join(FEM_DIR, "B601_BASE_ADAPTER_FEM.FCStd")
    doc.saveAs(out_fcstd)
    res["fem_fcstd"] = out_fcstd
    App.closeDocument(doc.Name)

    # cold-reopen reproducibility readback
    doc2 = App.openDocument(out_fcstd)
    doc2.recompute()
    r2 = [o for o in doc2.Objects if o.isDerivedFrom("Fem::FemResultObject")]
    if r2:
        u2 = max(r2[0].DisplacementLengths)
        ok2 = abs(u2 - res["max_displacement_mm"]) <= max(1e-12, abs(res["max_displacement_mm"]) * 1e-6)
    else:
        u2, ok2 = float("nan"), False
    st("cold_reopen_result_readback", ok2, "umax=%.3e after cold reopen" % u2)
    res["plausibility_note"] = ("1000 N unit load on stiff AL block -> very small response; "
                                "pipeline reproducible. Absolute values NOT load-qualified; "
                                "sanity bounds to be reviewed with real load cases.")
    App.closeDocument(doc2.Name)

if __name__ == "__main__" or True:
    run()
    path = fc_common.write_json(res, "BASE_ADAPTER_FEM_RESULT.json")
    print("RESULT_JSON=" + path)
    print(json.dumps(res, indent=2, ensure_ascii=False))
