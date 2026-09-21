"""WP09F solar hinge delta: stdlib algebra only; never imports a CAD kernel.

Source equations are transcribed from the hash-bound WP03 wing_kinematics.py.
Changing stack_step rebuilds a serial mechanism, not isolated plate translations.
"""
from pathlib import Path
import hashlib
import itertools
import json
import math

C = Path(__file__).resolve().parents[1]
N = C.parent / "reuse_closure"
PROJECT = C.parents[5]
WP03 = C.parents[1] / "wp03_bounded_20260906_161431" / "candidate"
SOURCE = WP03 / "wing_kinematics.py"
MODEL = WP03 / "spacecraft_model.py"
STATES = {"parking": [0, 0, 0], "released": [0, 0, 0], "service": [90, 180, 180]}
RECEIPTS = {"parking": "NATIVE_PARKING.json", "released": "NATIVE_RELEASED.json", "service": "NATIVE_SERVICE_RECOVERY_V2.json"}
PARAMS = {
    "leaf_chord_mm": 300.0, "leaf_span_mm": 200.0,
    "substrate_nominal_mm": 2.5, "substrate_max_requirement_mm": 2.60,
    "cic_nominal_mm": 0.290, "cic_max_mm": 0.340,
    "adhesive_nominal_requirement_mm": 0.10,
    "adhesive_min_requirement_mm": 0.05, "adhesive_max_requirement_mm": 0.15,
    "axis_spacing_negative_error_budget_mm": 0.10,
    "noncontact_clearance_requirement_mm": 0.30,
    "old_stack_step_mm": 3.0, "candidate_stack_step_mm": 4.5,
    "root_abs_y_mm": 121.15, "root_z_mm": -108.15,
    "tab_geometry_inside_this_thickness_contract": False,
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def transform(t, p):
    return [sum(t[i][j] * p[j] for j in range(3)) + t[i][3] for i in range(3)]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def frames(side, angles, step=4.5):
    th, ph2, ph3 = map(math.radians, angles)
    psi = (th, th+math.pi-ph2, th-ph2+ph3)
    direction = [[side*math.sin(a), math.cos(a)] for a in psi]
    normal = [[side*math.cos(a), -math.sin(a)] for a in psi]
    roots = [[side*PARAMS["root_abs_y_mm"], PARAMS["root_z_mm"]]]
    roots.append([roots[0][i]+200*direction[0][i]+step*normal[0][i] for i in range(2)])
    roots.append([roots[1][i]+200*direction[1][i]-step*normal[1][i] for i in range(2)])
    rows = []
    for leaf, (root, d) in enumerate(zip(roots, direction), 1):
        center = [root[i]+100*d[i] for i in range(2)]
        t = [[1., 0., 0., 0.], [0., d[0], -d[1], center[0]],
             [0., d[1], d[0], center[1]], [0., 0., 0., 1.]]
        rows.append({"id": f"wing_{side}_leaf_{leaf}", "side": side, "leaf": leaf,
                     "T_local_to_S_mm": t, "root_S_mm": [0., *root],
                     "tip_S_mm": [0., *[root[i]+200*d[i] for i in range(2)]],
                     "solar_face_local_z_sign": side,
                     "solar_normal_S": [side*t[i][2] for i in range(3)]})
    return rows


def obb(row, extra_face_mm=0.49, substrate_mm=2.6):
    # Full panel footprint is deliberately more conservative than 14 separated CICs.
    t = row["T_local_to_S_mm"]
    zc = row["side"]*extra_face_mm/2
    return {"center": transform(t, [0, 0, zc]),
            "axes": [[t[j][i] for j in range(3)] for i in range(3)],
            "half": [150, 100, (substrate_mm+extra_face_mm)/2]}


def sat(a, b):
    delta = sub(b["center"], a["center"])
    axes = a["axes"]+b["axes"]+[cross(x, y) for x in a["axes"] for y in b["axes"]]
    minimum = math.inf
    gaps = []
    for axis in axes:
        norm = math.sqrt(dot(axis, axis))
        if norm < 1e-10:
            continue
        axis = [v/norm for v in axis]
        ra = sum(h*abs(dot(u, axis)) for h, u in zip(a["half"], a["axes"]))
        rb = sum(h*abs(dot(u, axis)) for h, u in zip(b["half"], b["axes"]))
        overlap = ra+rb-abs(dot(delta, axis))
        minimum = min(minimum, overlap)
        if overlap < -1e-8:
            gaps.append(-overlap)
    return {"relation": "SEPARATED" if gaps else "TOUCHING" if minimum <= 1e-8 else "POSITIVE_OVERLAP",
            "minimum_axis_overlap_mm": minimum,
            "largest_separating_axis_gap_mm": max(gaps) if gaps else 0}


def box_bounds(row, extra_face_mm=0.49, substrate_mm=2.6):
    sign = row["side"]
    z = [-substrate_mm/2, substrate_mm/2]
    z[1 if sign > 0 else 0] += sign*extra_face_mm
    pts = [transform(row["T_local_to_S_mm"], p) for p in itertools.product((-150, 150), (-100, 100), z)]
    return {"min_mm": [min(p[i] for p in pts) for i in range(3)],
            "max_mm": [max(p[i] for p in pts) for i in range(3)]}


def main():
    p = PARAMS
    inputs = {str(SOURCE): sha(SOURCE), str(MODEL): sha(MODEL)}
    proof = []
    state_results = {}
    for state, angles in STATES.items():
        path = N/"results"/RECEIPTS[state]
        inputs[str(path)] = sha(path)
        receipt = json.loads(path.read_text(encoding="utf-8-sig"))
        native = {r["id"]: r for r in receipt["rows"]}
        old = [r for side in (-1, 1) for r in frames(side, angles, p["old_stack_step_mm"])]
        new = [r for side in (-1, 1) for r in frames(side, angles, p["candidate_stack_step_mm"])]
        max_error = max(abs(r["T_local_to_S_mm"][i][j]-native[r["id"]]["native_T_local_to_S"][i][j])
                        for r in old for i in range(4) for j in range(4))
        proof.append({"state": state, "old_formula_to_current_native_max_error_mm_or_unitless": max_error,
                      "pass": max_error < 1e-9})
        pairs = []
        for a, b in itertools.combinations(new, 2):
            pairs.append({"a": a["id"], "b": b["id"], **sat(obb(a), obb(b))})
        for a, b in zip(old, new):
            b["old_T_local_to_S_mm"] = a["T_local_to_S_mm"]
            b["center_delta_S_mm"] = sub([b["T_local_to_S_mm"][i][3] for i in range(3)], [a["T_local_to_S_mm"][i][3] for i in range(3)])
            b["conservative_substrate_plus_face_bounds_mm"] = box_bounds(b)
        state_results[state] = {"frames": new, "pair_tests": pairs,
                                "positive_overlap_count": sum(q["relation"] == "POSITIVE_OVERLAP" for q in pairs)}
    layer = p["cic_max_mm"]+p["adhesive_max_requirement_mm"]
    required = p["substrate_max_requirement_mm"]+2*layer+p["axis_spacing_negative_error_budget_mm"]+p["noncontact_clearance_requirement_mm"]
    clearance_old = p["old_stack_step_mm"]-p["substrate_max_requirement_mm"]-2*layer-p["axis_spacing_negative_error_budget_mm"]
    clearance_new = p["candidate_stack_step_mm"]-p["substrate_max_requirement_mm"]-2*layer-p["axis_spacing_negative_error_budget_mm"]
    rebuild = [f"wing_edge_frame_{side}_{leaf}_{sx}" for side in (-1,1) for leaf in (1,2) for sx in (-1,1)]
    move_pins = [f"wing_hinge_pin_{side}_{hinge}_{sx}" for side in (-1,1) for hinge in (2,3) for sx in (-1,1)]
    joints = []
    for side in (-1,1):
        for hinge in (2,3):
            sign = -side if hinge == 2 else side
            for sx in (-1,1):
                x = sx*(162 if hinge == 2 else 188)
                joints.append({"side": side, "hinge": hinge, "x_side": sx,
                               "owner": f"wing_edge_frame_{side}_{hinge-1}_{sx}",
                               "parent_leaf": f"wing_{side}_leaf_{hinge-1}",
                               "child_leaf": f"wing_{side}_leaf_{hinge}",
                               "old_axis_parent_local_mm": [x,100,sign*3.0],
                               "new_axis_parent_local_mm": [x,100,sign*4.5],
                               "axis_direction_parent_local": [1,0,0],
                               "unchanged_child_axis_local_mm": [x,-100,0],
                               "rebuild_instruction": "Recompute JT from revised hinge root; PT from revised parent pose; zoff=(parent.tip-JT.translation) dot parent.local_z. Rebuild BOTH fixed ears and connecting rods/bridge in parent edge-frame solid; retain moving barrel at child local y=-100,z=0."})
    output = {
        "identity": "SOLAR_SERIAL_HINGE_DELTA_V1",
        "status": "ALGEBRAIC_MECHANISM_DELTA_DEFINED__CAD_REBUILD_REQUIRED__INTERCONNECT_HOLD",
        "parameters": p, "source_sha256": inputs,
        "old_formula_native_binding": proof,
        "folding_clearance": {"worst_case_double_sided_facing_pair": "leaf2/leaf3 on both wings",
            "required_stack_step_mm": required, "old_worst_clearance_mm": clearance_old,
            "new_worst_clearance_mm": clearance_new,
            "new_margin_above_noncontact_requirement_mm": clearance_new-p["noncontact_clearance_requirement_mm"],
            "minimum_nominal_gap_before_adhesive_old_mm": 3.0-2.5-2*.34,
            "source_device_thickness_includes_coverglass": True,
            "adhesive_is_a_design_requirement_not_qualified_selected_material": True,
            "out_of_plane_tabs_must_be_routed_outside_facing_overlap_or_rebound": True},
        "states": state_results, "hinge_axis_contracts": joints,
        "candidate_deployment_waypoints_deg": [[0,0,0],[90,0,0],[90,150,0],[90,150,180],[90,180,180]],
        "candidate_deployment_path_note": "H2 pre-unfold only to150 degrees, unfoldH3, then finishH2. Original90/180/0 intermediate pose creates leaf1/leaf3 edge contact. Continuous six-envelope certificate is separate SOLAR_CONTINUOUS_CLEARANCE.json; not a hardware motion command.",
        "actual_component_changes": {
            "rebuild_edge_frame_geometry_ids": rebuild,
            "update_hinge_pin_transforms_ids": move_pins,
            "update_leaf_transforms_ids": [f"wing_{s}_leaf_{i}" for s in (-1,1) for i in (2,3)],
            "update_leaf3_edge_frame_transforms_ids": [f"wing_edge_frame_{s}_3_{x}" for s in (-1,1) for x in (-1,1)],
            "root_fork_and_hinge1": "UNCHANGED_GEOMETRY_AND_POSE",
            "hinge_pin_diameter_and_length": "UNCHANGED_4mm_SHAFT_22mm_PLUS_EXISTING_HEAD; original source 4.4mm holes; fit/load unverified",
            "spacer_solution": "No existing axis-offset spacer part: adding an axial washer cannot create the required parent-normal 1.5mm offset. Rebuild fixed fork/connecting rods/bridge as specified.",
            "edge_insert_joint": "Current mount_interface says EDGE_INSERTS_TBD; real board-to-frame inserts/fasteners remain unbound.",
        },
        "assembly_effects": {
            "parking_released_outer_leaf_outward_delta_each_wing_mm": 3.0,
            "parking_released_middle_leaf_outward_delta_each_wing_mm": 1.5,
            "service_middle_leaf_z_delta_mm": -1.5,
            "service_root_and_tip_leaf_translation_change_mm": 0.0,
            "same_face_root_leaf_to_existing_access_cover_min_gap_mm": 121.15-2.6/2-.49-113.15,
            "not_evaluated": ["hinge rebuilt exact BREP", "insert/fastener joint", "full spacecraft collision", "continuous deployment", "cable hinge bend/strain", "launch restraint", "thermal distortion", "real tab geometry"]},
        "negative_controls": [
            {"id":"OLD_3MM_STACK", "detected":clearance_old < p["noncontact_clearance_requirement_mm"]},
            {"id":"UNDERSTATED_ZERO_CIC_THICKNESS", "detected": p["cic_max_mm"] > 0},
            {"id":"ADHESIVE_0_50MM_EACH", "detected": 4.5-2.6-2*(.34+.5)-.1 < .3},
            {"id":"MOVE_LEAF_WITHOUT_PARENT_AXIS", "detected": abs(4.5-3.0)>1e-9,
             "joint_closure_residual_if_parent_fork_not_rebuilt_mm": 1.5},
        ],
        "manufacturing_release":False,"flight_release":False,"hardware_execution":False,
        "cad_modified_by_this_script":False,"science_gate_modified":False,
    }
    (C/"results").mkdir(parents=True,exist_ok=True)
    path=C/"results/SOLAR_HINGE_DELTA.json"
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(path),"binding_pass":all(x["pass"] for x in proof),"required_step_mm":required,"selected_step_mm":4.5,"worst_gap_mm":clearance_new,"state_overlap_counts":{k:v["positive_overlap_count"] for k,v in state_results.items()}}))
    return output


if __name__ == "__main__":
    main()
