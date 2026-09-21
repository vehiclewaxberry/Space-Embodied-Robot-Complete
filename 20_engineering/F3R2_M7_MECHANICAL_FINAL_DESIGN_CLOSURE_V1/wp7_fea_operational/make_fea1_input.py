# -*- coding: utf-8 -*-
"""
FEA-1 M3R interface operational-load model -- parametric Abaqus .inp generator.

M7 / WP7 (FEA_OPERATIONAL). Level-1 interface idealization, hand-written
structured C3D8R lattice. Everything declared in ASSUMPTION_REGISTER below is
also echoed into each deck header and into FEA1_EVIDENCE_V1.json.

Model stack (local frame = M3R_LOCAL, z from bridge bus face toward B601):
    z [ 0.00, 10.75]  LOAD BRIDGE  160x160x10.75, centre hole dia 40 (stepped)
    z [10.75, 22.75]  STAGE B      160x160x12 annular plate, bore dia 100,
                                   centre web r<50 kept in top layer (4.0 mm
                                   modelled vs 5.595 real, declared)
    z [22.75, 30.75]  STAGE A      ring OD150/ID40 x 8.0 uniform

Joints (no contact, no preload, no friction -- CDR joint-mechanics HOLD):
    bridge<->StageB : 4x M6 @ (+/-70,+/-70), kinematic-coupling bolt disks
    StageA<->StageB : 8x M5 @ r=62.5, ang 22.5+45k deg, coupling disks
    arm base load   : RP at (0,0,30.75) rigid spider onto 4x M4 as-built
                      centres (A-011, M3R_STAGE_A_PARAMETER_TABLE)
    bus side        : ENCASTRE at z=0  (BC-BUS-001 stiffness HOLD inherited)

Units: N, mm, MPa, tonne. Linear static (NLGEOM off).
Python: host CPython >=3.9, stdlib only.
"""

import hashlib
import json
import math
import os

# ----------------------------------------------------------------------------
# Pinned source values (read-only baselines). Paths+hashes recorded separately
# in the policy yaml / evidence json by run_fea1_matrix.py.
# ----------------------------------------------------------------------------

GEOM = {
    # load bridge (M6 wp1 LOAD_BRIDGE_DATUMS_V1.yaml / execution plan contract)
    "bridge_half": 80.0,          # 160 mm square
    "bridge_z": (0.0, 10.75),     # x_S 185.25 -> 196.0 mapped to local z
    "bridge_hole_r": 20.0,        # centre passage dia 40
    # Stage B (M3R_STAGE_B_PARAMETER_TABLE REVB2)
    "stageb_z": (10.75, 22.75),
    "stageb_bore_r": 50.0,        # central bore dia 100
    "stageb_web_layers_from_top": 1,  # r<50 web kept in top layer only
    # Stage A (M3R_STAGE_A_PARAMETER_TABLE REVB)
    "stagea_z": (22.75, 30.75),   # 8.0 mm total (2.405 proud + 5.595 recessed)
    "stagea_r_out": 75.0,         # OD 150
    "stagea_r_in": 20.0,          # central passage dia 40
    # patterns
    "m6_centres": [(70.0, 70.0), (70.0, -70.0), (-70.0, 70.0), (-70.0, -70.0)],
    "m5_radius": 62.5,
    "m5_start_deg": 22.5,
    "m5_count": 8,
    "m4_centres_asbuilt": [       # A-011 FROZEN as-built centres, M3R local xy
        (15.494, 42.4393),
        (-42.5096, 15.3917),
        (-15.4621, -42.612),
        (42.5416, -15.5644),
    ],
    # bolt-disk load-diffusion radii (declared assumption; auto-grow rule below)
    "r_b_m6": 12.0,
    "r_b_m5": 10.0,
    "r_b_m4": 10.0,
}

MATERIALS = {
    # M6 wp4 PROTOTYPE_MATERIAL_LIBRARY_V2.yaml, classification PROTOTYPE_CANDIDATE.
    # Poisson ratio 0.33 is NOT in the library -> POISSON_ASSUMPTION (declared).
    "AL6061_T6_CAND": {"E_MPa": 68300.0, "nu": 0.33, "rho_t_mm3": 2.7e-9,
                       "yield_typ_MPa": 276.0,
                       "source": "PMAT-AL6061-T6-SHEET-PLATE"},
    "AL7075_T651_CAND": {"E_MPa": 71000.0, "nu": 0.33, "rho_t_mm3": 2.8e-9,
                         "yield_typ_MPa": 503.0,
                         "source": "PMAT-AL7075-T651-SHEET-PLATE"},
}

# ----------------------------------------------------------------------------
# Quasi-static load policy (DYNAMIC_FACTOR_ASSUMPTION, declared, research-bound).
# F_eq = DAF * J / dt_contact ;  M_eq = DAF * C / dt_contact + F_eq * L_grasp
# ----------------------------------------------------------------------------

POLICY = {
    "daf": 2.0,                 # suddenly-applied-load classical bound (ASSUMPTION)
    "dt_contact_s": 0.1,        # no contact-duration authority exists (ASSUMPTION)
    "r_eff_arm_m": 0.7,         # B601-class reach for arm inertia equivalence (ASSUMPTION)
    "estop_factor": 2.0,        # e-stop = estop_factor x maneuver (declared policy)
    "arm_mass_kg": 4.695555949342986,   # L0 URDF authority (never overridden)
    "quintic_dq_rad": math.radians(60.0),   # LC-010 q2 +60 deg (governs q3 -40)
    "quintic_T_s": 8.0,
    "quintic_peak_acc_factor": 5.7735027,   # max of 60t-180t^2+120t^3 on [0,1]
}

CAPTURE_ENVELOPE = {
    # CDR DERIVED_CAPTURE_LOAD_ENVELOPE_V1.csv worst rows (max impulse anchor)
    "CAPTURE_22KG_QS":  {"J_N_s": 0.360622,  "C_N_m_s": 0.00152744, "L_m": 0.25173,
                         "row": "CAP22_030"},
    "CAPTURE_150KG_QS": {"J_N_s": 0.677633,  "C_N_m_s": 0.130197,   "L_m": 1.21521,
                         "row": "CAP150_030"},
}

MESH_LEVELS = {
    # MEMORY_GATE_ADAPTATION: draft 4/2/1 mm seeds are infeasible under the
    # <=4000 C3D8R bound (1.3 GiB available). Levels below keep every deck
    # comfortably under the cap; convergence is judged on the global maxima
    # trend across these three levels.
    "COARSE": {"n_xy": 10},   # 16.0 mm
    "MEDIUM": {"n_xy": 16},   # 10.0 mm
    "FINE":   {"n_xy": 20},   #  8.0 mm
}

ASSUMPTION_REGISTER = [
    "LINEAR_STATIC_SMALL_DISPLACEMENT (NLGEOM off; loads are milli-g level)",
    "BUS_SIDE_ENCASTRE_ASSUMPTION: BC-BUS-001 bus stiffness authority is HOLD; "
    "z=0 face fully clamped = stiff-boundary design bound",
    "BOLT_DISK_KINEMATIC_COUPLING_ASSUMPTION: M6/M5/M4 joints modelled as rigid "
    "coupling disks (r_b=12/10/10 mm, auto-grow to >=1 node/face, recorded); "
    "no preload, no friction, no slip",
    "ARM_BASE_RIGID_SPIDER_ASSUMPTION: B601 base flange stiffness >> 8 mm ring; "
    "single RP spider onto 4 as-built M4 disks; sensitivity covered by the "
    "3-level mesh convergence series (CDR rigid_spider rule)",
    "NO_CONTACT_NO_PRELOAD_NO_FRICTION: CDR joint mechanics HOLD; faces outside "
    "bolt disks untied (separation/interpenetration possible; Level-1 bound)",
    "STAGE_B_IDEALIZED_ANNULAR_PLATE: pocket/recess not resolved; bore dia100 "
    "through bottom 2 layers; centre web r<50 modelled 4.0 mm (real 5.595)",
    "STAGE_A_IDEALIZED_UNIFORM_RING: OD150/ID40 x 8.0 uniform; spigot, recess, "
    "counterbores not resolved",
    "BRIDGE_CORNER_RADIUS_OMITTED: R4 corners modelled square; all boundaries "
    "stepped at element corners",
    "SMALL_HOLES_NOT_CUT: dia6.6/5.5/4.6 holes represented by coupling disks, "
    "not voids (locally stiffer); hole-edge peak stress NOT qualified here",
    "POISSON_ASSUMPTION: nu=0.33 for both Al candidates (not in M6 library)",
    "MATERIALS_CANDIDATE: 6061-T6 / 7075-T651 elastic constants from M6 WP4 "
    "library, classification PROTOTYPE_CANDIDATE; margins DESIGN_INDICATIVE only",
    "DYNAMIC_FACTOR_ASSUMPTION: quasi-static equivalence F_eq=DAF*J/dt, "
    "DAF=2.0, dt=0.1 s; both declared assumptions, research-bound",
    "LOAD_DIRECTION_ASSUMPTION: transverse +y force plus bending moment about "
    "+z; worst-axis alignment declared (near-axisymmetric stack)",
    "MEMORY_GATE_MESH_ADAPTATION: seeds 16/10/8 mm replace draft 4/2/1 mm; "
    "<=4000 C3D8R; 6.7 mm ligament NOT resolved with 3 elements; convergence "
    "assessed on global maxima trend only",
    "ARM_LOADS_BOUNDED_BY_ASSUMPTION: quintic peak accel from LC-010 "
    "trajectory x r_eff=0.7 m; e-stop = 2x maneuver; arm inertia tensor not "
    "reduced (arm cases shown to be non-governing)",
]


def compute_case_loads():
    """Return {case_id: dict(F_N, M_N_m, ...)} from pinned constants."""
    out = {}
    qacc = (POLICY["quintic_peak_acc_factor"] * POLICY["quintic_dq_rad"]
            / POLICY["quintic_T_s"] ** 2)
    a_eq = qacc * POLICY["r_eff_arm_m"]
    f_man = POLICY["arm_mass_kg"] * a_eq
    out["ARM_MANEUVER_QS"] = {
        "F_N": f_man, "M_N_m": f_man * POLICY["r_eff_arm_m"],
        "derivation": "m_arm*(quintic q2_acc_max*r_eff); M=F*r_eff",
        "q2_acc_max_rad_s2": qacc, "a_eq_m_s2": a_eq,
        "source_class": "DERIVED_TRAJECTORY_PLUS_ASSUMPTION",
    }
    out["ARM_ESTOP_QS"] = {
        "F_N": f_man * POLICY["estop_factor"],
        "M_N_m": f_man * POLICY["estop_factor"] * POLICY["r_eff_arm_m"],
        "derivation": "estop_factor(2.0, declared) x ARM_MANEUVER_QS",
        "source_class": "ASSUMPTION_POLICY",
    }
    for cid, env in CAPTURE_ENVELOPE.items():
        f = POLICY["daf"] * env["J_N_s"] / POLICY["dt_contact_s"]
        m = f * env["L_m"] + POLICY["daf"] * env["C_N_m_s"] / POLICY["dt_contact_s"]
        out[cid] = {
            "F_N": f, "M_N_m": m,
            "derivation": "F=DAF*J/dt; M=F*L_grasp+DAF*C/dt (envelope row %s)"
                          % env["row"],
            "source_class": "DERIVED_ENVELOPE_PLUS_ASSUMPTION_POLICY",
        }
    return out


class MeshBuilder:
    """Structured C3D8R lattice over 10 node planes (2 coincident pairs)."""

    # (name, z, footprint) -- footprints: SQ160_H40 / SQ160_H100 / SQ160 / RING
    PLANES = [
        ("p0", 0.0,    "SQ160_H40"),
        ("p1", 5.375,  "SQ160_H40"),
        ("p2", 10.75,  "SQ160_H40"),   # bridge top  (M6 joint, bridge side)
        ("p3", 10.75,  "SQ160_H100"),  # stage B bottom (M6 joint, stage B side)
        ("p4", 14.75,  "SQ160_H100"),
        ("p5", 18.75,  "SQ160"),       # centre web present above this plane
        ("p6", 22.75,  "SQ160"),       # stage B top (M5 joint, stage B side)
        ("p7", 22.75,  "RING"),        # stage A bottom (M5 joint, stage A side)
        ("p8", 26.75,  "RING"),
        ("p9", 30.75,  "RING"),        # stage A top (arm spider)
    ]
    LAYERS = [  # (plane_lo, plane_hi, zone elset)
        (0, 1, "EBRIDGE"), (1, 2, "EBRIDGE"),
        (3, 4, "ESTAGEB"), (4, 5, "ESTAGEB"), (5, 6, "ESTAGEB"),
        (7, 8, "ESTAGEA"), (8, 9, "ESTAGEA"),
    ]

    def __init__(self, n_xy):
        self.n = n_xy
        self.h = 160.0 / n_xy
        self.nodes = {}      # id -> (x, y, z)
        self.plane_ids = {}  # plane_idx -> {(ix, iy): node_id}
        self.elements = {}   # id -> (elset, [8 node ids], centroid)
        self.elsets = {"EBRIDGE": [], "ESTAGEB": [], "ESTAGEA": []}
        self._build()

    def _in_footprint(self, fp, x, y):
        r = math.hypot(x, y)
        if fp == "SQ160_H40":
            return r >= GEOM["bridge_hole_r"]
        if fp == "SQ160_H100":
            return r >= GEOM["stageb_bore_r"]
        if fp == "SQ160":
            return True
        if fp == "RING":
            return GEOM["stagea_r_in"] <= r <= GEOM["stagea_r_out"]
        raise ValueError(fp)

    def _build(self):
        half = GEOM["bridge_half"]
        for pi, (name, z, fp) in enumerate(self.PLANES):
            lut = {}
            for iy in range(self.n + 1):
                for ix in range(self.n + 1):
                    x = -half + ix * self.h
                    y = -half + iy * self.h
                    if self._in_footprint(fp, x, y):
                        nid = pi * 100000 + iy * 1000 + ix + 1
                        self.nodes[nid] = (x, y, z)
                        lut[(ix, iy)] = nid
            self.plane_ids[pi] = lut
        eid = 0
        for plo, phi, elset in self.LAYERS:
            lut_lo, lut_hi = self.plane_ids[plo], self.plane_ids[phi]
            for iy in range(self.n):
                for ix in range(self.n):
                    quad = [(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)]
                    if all(q in lut_lo and q in lut_hi for q in quad):
                        lo = [lut_lo[q] for q in quad]
                        hi = [lut_hi[q] for q in quad]
                        conn = lo + hi
                        eid += 1
                        cx = sum(self.nodes[n][0] for n in conn) / 8.0
                        cy = sum(self.nodes[n][1] for n in conn) / 8.0
                        cz = sum(self.nodes[n][2] for n in conn) / 8.0
                        self.elements[eid] = (elset, conn, (cx, cy, cz))
                        self.elsets[elset].append(eid)

    # -- joint node sets -----------------------------------------------------
    def disk_nodes(self, plane_idx, centre, radius):
        """Nodes on one plane within radius of centre (x,y)."""
        out = []
        for nid in self.plane_ids[plane_idx].values():
            x, y, _ = self.nodes[nid]
            if math.hypot(x - centre[0], y - centre[1]) <= radius:
                out.append(nid)
        return out

    def fixed_nodes(self):
        return sorted(self.plane_ids[0].values())

    def disk_pairs(self, plane_lo, plane_hi, centre, radius):
        """Coincident-lattice node pairs (lo,hi) within radius of centre."""
        lut_lo, lut_hi = self.plane_ids[plane_lo], self.plane_ids[plane_hi]
        out = []
        for key, nid_lo in lut_lo.items():
            nid_hi = lut_hi.get(key)
            if nid_hi is None:
                continue
            x, y, _ = self.nodes[nid_lo]
            if math.hypot(x - centre[0], y - centre[1]) <= radius:
                out.append((nid_lo, nid_hi))
        return out

    def nearest_element(self, elset, target):
        best, bd = None, None
        for eid in self.elsets[elset]:
            c = self.elements[eid][2]
            d = math.dist(c, target)
            if bd is None or d < bd:
                best, bd = eid, d
        return best


def build_joint_records(mesh):
    """Bolt joints as PIN MPC pairs + arm spider nset; auto-grow recorded.

    Returns (records, mpc_pairs, spider_nodes).
    M6/M5 disks: PIN MPC between coincident lattice nodes of the two mating
    faces (translations tied; solid nodes carry no rotational DOF, so no
    degenerate ref-node rotations appear). Auto-grow r_b until >=1 pair.
    """
    records = []
    mpc_pairs = []

    def make(joint, centres, r_b, plane_lo, plane_hi):
        for i, c in enumerate(centres):
            name = "%s_%d" % (joint, i + 1)
            r = r_b
            while True:
                pairs = mesh.disk_pairs(plane_lo, plane_hi, c, r)
                if pairs:
                    break
                r *= 1.15
                if r > 25.0:
                    raise RuntimeError("bolt disk %s captures no pair" % name)
            for na, nb in pairs:
                mpc_pairs.append((na, nb, name))
            records.append({
                "joint": name, "centre_xy": list(c),
                "r_b_nominal_mm": r_b, "r_b_used_mm": round(r, 4),
                "pin_mpc_pairs": len(pairs),
                "auto_grown": r > r_b * 1.0001,
            })

    make("M6", GEOM["m6_centres"], GEOM["r_b_m6"], 2, 3)     # bridge<->stage B
    m5c = [(GEOM["m5_radius"] * math.cos(math.radians(GEOM["m5_start_deg"] + 45.0 * k)),
            GEOM["m5_radius"] * math.sin(math.radians(GEOM["m5_start_deg"] + 45.0 * k)))
           for k in range(GEOM["m5_count"])]
    make("M5", m5c, GEOM["r_b_m5"], 6, 7)                    # stage A<->stage B

    # arm-base spider: one RP coupled to the 4 as-built M4 disks on plane 9
    spider = []
    for i, c in enumerate(GEOM["m4_centres_asbuilt"]):
        r = GEOM["r_b_m4"]
        while True:
            nd = mesh.disk_nodes(9, c, r)
            if nd:
                break
            r *= 1.15
            if r > 25.0:
                raise RuntimeError("M4 disk %d captures no node" % (i + 1))
        spider.extend(nd)
        records.append({"joint": "M4_%d" % (i + 1), "centre_xy": list(c),
                        "r_b_nominal_mm": GEOM["r_b_m4"],
                        "r_b_used_mm": round(r, 4), "nodes": len(nd),
                        "auto_grown": r > GEOM["r_b_m4"] * 1.0001})
    return records, mpc_pairs, sorted(set(spider))


def write_deck(path, mesh, records, mpc_pairs, spider_nodes, case_id, case,
               level_name, material_id):
    mat = MATERIALS[material_id]
    fixed = mesh.fixed_nodes()
    probes = {
        "EPROBE_M6_BRIDGE": mesh.nearest_element(
            "EBRIDGE", (63.0, 63.0, 10.75)),
        "EPROBE_BORE_STAGEB": mesh.nearest_element(
            "ESTAGEB", (50.0 * math.cos(math.radians(45)), 50.0 * math.sin(math.radians(45)), 17.0)),
        "EPROBE_M4_STAGEA": mesh.nearest_element(
            "ESTAGEA", (15.494, 42.4393, 30.75)),
        "EPROBE_HOLE_BRIDGE": mesh.nearest_element(
            "EBRIDGE", (20.0, 0.0, 5.0)),
    }
    rp = 900000

    lines = []
    A = lines.append
    A("*HEADING")
    A("FEA1_M3R_INTERFACE  case=%s  mesh=%s  material=%s" % (case_id, level_name, material_id))
    A("M7 WP7 FEA_OPERATIONAL -- operational on-orbit quasi-static screen.")
    A("Units: N, mm, MPa, tonne. Linear static. DESIGN_INDICATIVE results only.")
    for a in ASSUMPTION_REGISTER:
        A("** ASSUMPTION: " + a)
    A("** Case load: F_y=%.6g N, M_z=%.6g N*mm (%s)"
      % (case["F_N"], case["M_N_m"] * 1000.0, case["derivation"]))
    A("**")
    # nodes
    A("*NODE")
    for nid in sorted(mesh.nodes):
        x, y, z = mesh.nodes[nid]
        A("%d,%.6f,%.6f,%.6f" % (nid, x, y, z))
    A("%d,0.0,0.0,30.75" % rp)
    # elements
    A("*ELEMENT,TYPE=C3D8R,ELSET=EALL")
    for eid in sorted(mesh.elements):
        A("%d,%s" % (eid, ",".join(str(n) for n in mesh.elements[eid][1])))
    for name, ids in mesh.elsets.items():
        A("*ELSET,ELSET=%s" % name)
        for i in range(0, len(ids), 16):
            A(",".join(str(e) for e in ids[i:i + 16]))
    A("*ELSET,ELSET=EPROBES")
    A(",".join(str(v) for v in probes.values()))
    # nsets
    A("*NSET,NSET=NFIXED")
    for i in range(0, len(fixed), 16):
        A(",".join(str(n) for n in fixed[i:i + 16]))
    A("*NSET,NSET=NRP")
    A("%d" % rp)
    A("*NSET,NSET=NS_ARM_SPIDER")
    for i in range(0, len(spider_nodes), 16):
        A(",".join(str(n) for n in spider_nodes[i:i + 16]))
    # materials / sections
    A("*MATERIAL,NAME=%s" % material_id)
    A("*ELASTIC")
    A("%.1f,%.2f" % (mat["E_MPa"], mat["nu"]))
    A("*DENSITY")
    A("%.3e" % mat["rho_t_mm3"])
    for elset in ("EBRIDGE", "ESTAGEB", "ESTAGEA"):
        A("*SOLID SECTION,ELSET=%s,MATERIAL=%s" % (elset, material_id))
    # boundary
    A("*BOUNDARY")
    A("NFIXED,ENCASTRE")
    # bolt joints: PIN MPC between coincident lattice nodes of mating faces
    A("** bolt joints: PIN MPC pairs (translations tied per bolt disk)")
    A("*MPC")
    for na, nb, _j in mpc_pairs:
        A("PIN,%d,%d" % (na, nb))
    # arm-base load introduction spider (rigid flange idealization)
    A("*SURFACE,TYPE=NODE,NAME=S_ARM_SPIDER")
    A("NS_ARM_SPIDER,")
    A("*COUPLING,CONSTRAINT NAME=ARM_SPIDER,REF NODE=%d,SURFACE=S_ARM_SPIDER" % rp)
    A("*KINEMATIC")
    A("1,6")
    # step
    A("*STEP,NAME=QS_STEP,NLGEOM=NO")
    A("*STATIC")
    A("1.0,1.0")
    A("*CLOAD")
    A("%d,2,%.6g" % (rp, case["F_N"]))
    A("%d,6,%.6g" % (rp, case["M_N_m"] * 1000.0))
    A("*NODE PRINT,NSET=NFIXED")
    A("RF")
    A("*NODE PRINT,NSET=NRP")
    A("U")
    A("*EL PRINT,ELSET=EPROBES")
    A("S")
    A("*ENERGY PRINT")
    A("*OUTPUT,FIELD,VARIABLE=PRESELECT")
    A("*OUTPUT,HISTORY")
    A("*ENERGY OUTPUT")
    A("*END STEP")

    text = "\n".join(lines) + "\n"
    with open(path, "w", newline="\n") as f:
        f.write(text)

    sidecar = {
        "case_id": case_id, "mesh_level": level_name, "material": material_id,
        "nodes_total": len(mesh.nodes) + 1,
        "elements_total": len(mesh.elements),
        "elements_per_zone": {k: len(v) for k, v in mesh.elsets.items()},
        "grid_pitch_mm": mesh.h,
        "rp_node": rp,
        "pin_mpc_pair_count": len(mpc_pairs),
        "fixed_node_coords": {str(n): list(mesh.nodes[n]) for n in fixed},
        "probe_elements": probes,
        "joint_records": records,
        "applied_load": {"F_y_N": case["F_N"], "M_z_N_mm": case["M_N_m"] * 1000.0,
                         "rp_coords": [0.0, 0.0, 30.75]},
        "deck_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    return sidecar


def job_name(case_id, level_name, material_id):
    s = "fea1_%s_%s" % (case_id.lower(), level_name.lower())
    if material_id != "AL6061_T6_CAND":
        s += "_7075"
    return s


def build_all(deck_dir, sidecar_dir):
    os.makedirs(deck_dir, exist_ok=True)
    os.makedirs(sidecar_dir, exist_ok=True)
    cases = compute_case_loads()
    meshes = {lvl: MeshBuilder(spec["n_xy"]) for lvl, spec in MESH_LEVELS.items()}
    matrix = []
    for lvl in MESH_LEVELS:
        mesh = meshes[lvl]
        records, mpc_pairs, spider_nodes = build_joint_records(mesh)
        for cid, case in cases.items():
            mats = ["AL6061_T6_CAND"]
            # material sensitivity: governing case at fine mesh also in 7075
            if lvl == "FINE" and cid == "CAPTURE_150KG_QS":
                mats.append("AL7075_T651_CAND")
            for mid in mats:
                jn = job_name(cid, lvl, mid)
                deck = os.path.join(deck_dir, jn + ".inp")
                sc = write_deck(deck, mesh, records, mpc_pairs, spider_nodes,
                                cid, case, lvl, mid)
                sc["job_name"] = jn
                with open(os.path.join(sidecar_dir, jn + ".json"), "w") as f:
                    json.dump(sc, f, indent=1)
                matrix.append(sc)
    return matrix


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    m = build_all(os.path.join(here, "decks"), os.path.join(here, "jobs"))
    for sc in m:
        print("%-34s elems=%5d nodes=%5d pitch=%.2f" % (
            sc["job_name"], sc["elements_total"], sc["nodes_total"],
            sc["grid_pitch_mm"]))
