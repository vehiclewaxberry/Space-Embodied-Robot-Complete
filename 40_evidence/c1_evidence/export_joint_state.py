# export_joint_state.py — apply state then export assembly STEP + record.
# Usage: FreeCADCmd export_joint_state.py <STATE_NAME>
import os, sys, json
import FreeCAD as App
import Import

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common, urdf_model
import apply_joint_state as ajs

ASM_PATH = os.path.join(fc_common.FA_ROOT, "04_assemblies", "B601_KINEMATIC_ASSEMBLY.FCStd")

def export_state(state_name):
    res = ajs.apply_state(state_name)
    # Kinematic assembly is datum-only (zero solids by design) -> export a NON-DESIGN
    # witness STEP: small marker spheres at each link frame + joint-axis stubs.
    import Part
    doc = App.openDocument(ASM_PATH)
    shapes = []
    model = urdf_model.parse_urdf()
    q = ajs.state_to_q(ajs.load_states()[state_name])
    fkq = urdf_model.fk(model, q)
    for lname in ajs.CHAIN:
        p = fkq[lname]
        shapes.append(Part.makeSphere(2.0, p.Base))
    by_child = {j["child"]: j for j in urdf_model.ordered_chain(model)}
    for lname in ajs.CHAIN:
        j = by_child.get(lname)
        if j is None or j["type"] not in ("revolute", "prismatic"):
            continue
        p = fkq[lname]
        axis = p.Rotation.multVec(App.Vector(*j["axis"]))
        shapes.append(Part.makeCylinder(0.8, 30.0, p.Base, axis))
    comp = Part.makeCompound(shapes)
    App.closeDocument(doc.Name)
    assert comp.Solids and len(comp.Solids) == len(shapes), "witness compound lost solids"
    out_step = os.path.join(fc_common.EXPORT_DIR, "B601_KINEMATIC_ASSEMBLY_%s_WITNESS.step" % state_name)
    comp.exportStep(out_step)
    res["step"] = out_step
    res["step_kind"] = "NON_DESIGN_WITNESS_FRAME_MARKERS (datum-only assembly has null shape by design)"
    res["step_sha256"] = fc_common.sha256_file(out_step)
    return res

if __name__ == "__main__" or True:
    args = fc_common.script_args()
    state_name = args[0] if args else "Q0"
    res = export_state(state_name)
    path = fc_common.write_json(res, "export_state_%s.json" % state_name)
    print("RESULT_JSON=" + path)
    print(json.dumps(res, indent=2, ensure_ascii=False))
