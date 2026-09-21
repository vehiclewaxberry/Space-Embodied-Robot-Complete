# apply_joint_state.py — apply a named joint state to the kinematic assembly (FK-driven).
# Usage: FreeCADCmd apply_joint_state.py <STATE_NAME>
import os, sys, json, math
import FreeCAD as App

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common, urdf_model

ASM_PATH = os.path.join(fc_common.FA_ROOT, "04_assemblies", "B601_KINEMATIC_ASSEMBLY.FCStd")
STATES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "joint_states.json")
CHAIN = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6",
         "gripper_link", "gripper_left", "gripper_right"]

def load_states():
    with open(STATES_PATH, encoding="utf-8") as f:
        return json.load(f)["states"]

def state_to_q(state):
    q = {}
    for k, v in state.items():
        if k.startswith("_"):
            continue
        if k.startswith("gripper_joint"):
            q[k] = float(v) / 1000.0  # mm -> m (prismatic)
        else:
            q[k] = math.radians(float(v))
    return q

def apply_state(state_name):
    states = load_states()
    assert state_name in states, "unknown state %s" % state_name
    model = urdf_model.parse_urdf()
    q = state_to_q(states[state_name])
    fkq = urdf_model.fk(model, q)

    doc = App.openDocument(ASM_PATH)
    for lname in CHAIN:
        obj = doc.getObject("LINK_" + lname.upper())
        assert obj is not None, "missing link object for " + lname
        obj.Placement = fkq[lname]
    root = doc.getObject("B601_KINEMATIC_CHAIN")
    if "CURRENT_STATE" not in root.PropertiesList:
        root.addProperty("App::PropertyString", "CURRENT_STATE")
    root.CURRENT_STATE = state_name
    doc.recompute()
    doc.save()

    res = {"state": state_name, "tcp_mm": {}, "q_rad_m": {k: round(v, 9) for k, v in q.items()}}
    for lname in ("link6", "gripper_link", "gripper_left", "gripper_right"):
        p = fkq[lname].Base
        res["tcp_mm"][lname] = [round(p.x, 4), round(p.y, 4), round(p.z, 4)]
    App.closeDocument(doc.Name)
    return res

if __name__ == "__main__" or True:
    args = fc_common.script_args()
    state_name = args[0] if args else "Q0"
    res = apply_state(state_name)
    path = fc_common.write_json(res, "apply_state_%s.json" % state_name)
    print("RESULT_JSON=" + path)
    print(json.dumps(res, indent=2, ensure_ascii=False))
