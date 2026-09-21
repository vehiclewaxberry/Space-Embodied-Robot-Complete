# -*- coding: utf-8 -*-
"""
FEA-1B element-formulation closure deck generator -- M7 / WP7 (FEA_OPERATIONAL).

PURPOSE (ODR-11 layer 2 / ODR-12 mesh_credibility_pass)
-------------------------------------------------------
The FEA-1 baseline used C3D8R (reduced integration, 1 integration point,
hourglass control). Its artificial (hourglass) strain energy reached 80% of
internal energy at COARSE and 14% at FINE, and peak stress / displacement were
still rising +23% / +33% between the two finest levels. Stage A ring and the
Stage B load-diffusion plate are bending-dominated thin features carried by
only 2-3 elements through thickness, which is exactly where C3D8R hourglasses.

This generator rebuilds the SAME operational load cases on the SAME geometry
with C3D8I (incompatible-mode, fully integrated 2x2x2, no hourglass modes,
incompatible modes cure shear locking in bending). It writes THREE series:

  A) MESH_MATCHED   n_xy = 10 / 16 / 20, kz = 1
     Node-for-node, element-for-element identical to the FEA-1 COARSE / MEDIUM
     / FINE meshes. The ONLY difference from the baseline deck is the *ELEMENT
     TYPE keyword. This isolates the element-formulation delta with no
     confounding mesh change.

  B) THROUGH_THICKNESS  n_xy = 16 / 20 / 32, kz = 2 / 3 / 4
     Adds through-thickness element layers in the bending zones (kz multiplies
     the layer count of every z segment), i.e. a genuine 3-D h-refinement
     series instead of the baseline's in-plane-only refinement.

  C) CROSS_CHECK    C3D8 (fully integrated, NO incompatible modes) on the
     governing case, plus the 7075 material sensitivity, plus the
     load-traceability sensitivity deck (single-row-consistent CAP150_030).

The joint model, boundary condition, reference-point coupling, load values,
material cards, units and step definition are copied from the SOLVED FEA-1
decks bit-for-bit in structure. IMPORTANT: the solved FEA-1 decks use per-bolt
*COUPLING/*KINEMATIC with free reference nodes; the current repo copy of
make_fea1_input.py writes *MPC PIN instead and therefore does NOT regenerate
the solved decks (recorded as FEA1B-FIND-03). This generator deliberately
reproduces the SOLVED deck structure, because the comparison must isolate the
element formulation.

Pinned constants (GEOM / MATERIALS / POLICY / CAPTURE_ENVELOPE / case loads)
are IMPORTED from make_fea1_input so no load or dimension can drift.

Units: N, mm, MPa, tonne. Linear static (NLGEOM=NO). DESIGN_INDICATIVE only.
Python: host CPython >= 3.9, stdlib only.
"""

import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import make_fea1_input as F1  # noqa: E402  pinned GEOM/MATERIALS/POLICY/loads

GEOM = F1.GEOM
MATERIALS = F1.MATERIALS
POLICY = F1.POLICY

# ---------------------------------------------------------------------------
# reference nodes -- same roles as the solved FEA-1 decks, renumbered so that
# they can never collide with structural node ids at kz=4 / n_xy=32.
# ---------------------------------------------------------------------------
RP_ARM = 99000000
RP_M6_BASE = 99000100
RP_M5_BASE = 99000200

# ---------------------------------------------------------------------------
# geometry as z segments. Identical stack to FEA-1:
#   bridge   z 0.00 -> 10.75  SQ160 with dia-40 centre passage
#   stage B  z 10.75 -> 18.75 SQ160 with dia-100 bore   (annulus)
#   stage B  z 18.75 -> 22.75 SQ160 full                (centre web, 4.0 mm)
#   stage A  z 22.75 -> 30.75 ring OD150 / ID40
# base_layers reproduce the FEA-1 plane list exactly at kz = 1.
# ---------------------------------------------------------------------------
SEGMENTS = [
    ("EBRIDGE", 0.00, 10.75, "SQ160_H40", 2),
    ("ESTAGEB", 10.75, 18.75, "SQ160_H100", 2),
    ("ESTAGEB", 18.75, 22.75, "SQ160", 1),
    ("ESTAGEA", 22.75, 30.75, "RING", 2),
]
# a bolted interface (duplicated, coincident node plane) follows these segments
BREAK_AFTER_SEGMENT = (0, 2)

MESH_LEVELS_B = {
    # id: (n_xy, kz, series)
    "L1_MM_COARSE": (10, 1, "MESH_MATCHED"),
    "L2_MM_MEDIUM": (16, 1, "MESH_MATCHED"),
    "L3_MM_FINE": (20, 1, "MESH_MATCHED"),
    "T2_TT_MEDIUM": (16, 2, "THROUGH_THICKNESS"),
    "T3_TT_FINE": (20, 3, "THROUGH_THICKNESS"),
    "T4_TT_ULTRA": (32, 4, "THROUGH_THICKNESS"),
    # --- Z series: through-thickness-only refinement at FIXED in-plane mesh.
    # n_xy is frozen at 20, so the staircase footprint, the discretized
    # volume, every bolt-disk node set and the arm-spider node set are BIT
    # IDENTICAL across the series. This is the only member of this model
    # family that is a true h-refinement of ONE structure, and it is therefore
    # the primary mesh-convergence series. (20,1) is L3_MM_FINE and (20,3) is
    # T3_TT_FINE -- the same decks serve both series, no duplicate run.
    "Z2_ZR_N20K2": (20, 2, "Z_REFINEMENT_FIXED_INPLANE"),
    "Z4_ZR_N20K4": (20, 4, "Z_REFINEMENT_FIXED_INPLANE"),
    "Z6_ZR_N20K6": (20, 6, "Z_REFINEMENT_FIXED_INPLANE"),
    # kz 8 and 12 are run for the GOVERNING case only, to test the Richardson
    # extrapolation made from kz = 3/4/6 against real solves (prediction, then
    # verification, not extrapolation asserted as fact).
    "Z8_ZR_N20K8": (20, 8, "Z_REFINEMENT_FIXED_INPLANE"),
    "Z12_ZR_N20K12": (20, 12, "Z_REFINEMENT_FIXED_INPLANE"),
}

Z_SERIES = [("L3_MM_FINE", 1), ("Z2_ZR_N20K2", 2), ("T3_TT_FINE", 3),
            ("Z4_ZR_N20K4", 4), ("Z6_ZR_N20K6", 6),
            ("Z8_ZR_N20K8", 8), ("Z12_ZR_N20K12", 12)]

ELEMENT_TYPES = {
    "C3D8I": "incompatible-mode 8-node hex, 2x2x2 full integration, no "
             "hourglass modes, incompatible modes relieve shear locking in "
             "bending-dominated thin features (PRIMARY choice)",
    "C3D8": "fully integrated 8-node hex, no incompatible modes -- retained "
            "only as an upper (shear-locking) bound cross-check",
}

ASSUMPTION_REGISTER_B = list(F1.ASSUMPTION_REGISTER) + [
    "ELEMENT_FORMULATION_CHANGE: C3D8R (1 IP + hourglass control) replaced by "
    "C3D8I (2x2x2 full integration + incompatible modes). No hourglass modes "
    "exist in C3D8I, so ALLAE must collapse to ~0; this is the acceptance test",
    "IP_COUNT_COMPARABILITY: C3D8R reports 1 centroidal integration point, so "
    "its 'peak von Mises' is already an element-average; C3D8I reports 8 Gauss "
    "points, whose peak is systematically above the element average in a "
    "bending field. C3D8R peak must therefore be compared against the C3D8I "
    "ELEMENT-AVERAGED value, not against the C3D8I peak IP value",
    "THROUGH_THICKNESS_REFINEMENT: kz multiplies the layer count of every z "
    "segment (bridge 2kz, stage B annulus 2kz, stage B web 1kz, stage A 2kz); "
    "kz=1 reproduces the FEA-1 plane list node-for-node",
    "STAIRCASE_BOUNDARY_SINGULARITY: the dia-40 / dia-100 / OD-150 circular "
    "boundaries are stepped at element corners, so each in-plane refinement "
    "level presents a DIFFERENT discrete re-entrant-corner set. Peak stress at "
    "those steps cannot converge by construction and is excluded from the "
    "region-stress convergence metric (fixed 10 mm geometric band)",
    "POINT_COUPLING_SINGULARITY: the arm-base RP kinematic coupling and the "
    "per-bolt kinematic couplings are point/patch constraints; peak stress in "
    "their immediate neighbourhood rises monotonically with refinement as a "
    "constraint singularity and is reported separately (ODR-11 singularity "
    "rule), with a fixed 15 mm exclusion radius for the far-field metric",
]

FAR_FIELD_RULE = {
    "bolt_centre_exclusion_radius_mm": 15.0,
    "stepped_boundary_exclusion_band_mm": 10.0,
    "stepped_radii_mm": [20.0, 50.0, 75.0],
    "note": "fixed geometric (NOT mesh-proportional) exclusion so the compared "
            "far-field region is the same physical volume at every level",
}


def m5_centres():
    return [(GEOM["m5_radius"] * math.cos(math.radians(GEOM["m5_start_deg"] + 45.0 * k)),
             GEOM["m5_radius"] * math.sin(math.radians(GEOM["m5_start_deg"] + 45.0 * k)))
            for k in range(GEOM["m5_count"])]


class MeshB:
    """Structured axis-aligned hex lattice with independent z refinement."""

    def __init__(self, n_xy, kz):
        self.n = n_xy
        self.kz = kz
        self.h = 160.0 / n_xy
        self.nodes = {}         # id -> (x, y, z)
        self.planes = []        # list of dicts: z, fps(list), lut{(ix,iy):nid}
        self.elements = {}      # id -> (elset, conn8)
        self.elsets = {"EBRIDGE": [], "ESTAGEB": [], "ESTAGEA": []}
        self.seg_plane_range = []   # per segment: (plane_lo_idx, plane_hi_idx)
        self._build()

    # -- footprints (identical predicates to FEA-1) --------------------------
    @staticmethod
    def _in_fp(fp, x, y):
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

    def _in_any_fp(self, fps, x, y):
        return any(self._in_fp(fp, x, y) for fp in fps)

    def _plane_spec(self):
        """Return ordered plane specs [(z, [footprints])] plus segment ranges."""
        specs = []          # (z, [fps])
        seg_range = []
        for si, (elset, z0, z1, fp, base) in enumerate(SEGMENTS):
            nz = base * self.kz
            zs = [z0 + (z1 - z0) * j / float(nz) for j in range(nz + 1)]
            if si == 0:
                start = 0
                for z in zs:
                    specs.append((z, [fp]))
            else:
                if (si - 1) in BREAK_AFTER_SEGMENT:
                    start = len(specs)
                    for z in zs:
                        specs.append((z, [fp]))
                else:
                    # continuous: share the previous top plane, union footprint
                    start = len(specs) - 1
                    specs[start][1].append(fp)
                    for z in zs[1:]:
                        specs.append((z, [fp]))
            seg_range.append((start, len(specs) - 1))
        return specs, seg_range

    def _build(self):
        half = GEOM["bridge_half"]
        specs, self.seg_plane_range = self._plane_spec()
        for pi, (z, fps) in enumerate(specs):
            lut = {}
            for iy in range(self.n + 1):
                for ix in range(self.n + 1):
                    x = -half + ix * self.h
                    y = -half + iy * self.h
                    if self._in_any_fp(fps, x, y):
                        nid = (pi + 1) * 1000000 + iy * 1000 + ix + 1
                        self.nodes[nid] = (x, y, z)
                        lut[(ix, iy)] = nid
            self.planes.append({"z": z, "fps": list(fps), "lut": lut})
        eid = 0
        for si, (elset, _z0, _z1, _fp, _base) in enumerate(SEGMENTS):
            plo, phi = self.seg_plane_range[si]
            for pj in range(plo, phi):
                lut_lo = self.planes[pj]["lut"]
                lut_hi = self.planes[pj + 1]["lut"]
                for iy in range(self.n):
                    for ix in range(self.n):
                        quad = [(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)]
                        if all(q in lut_lo and q in lut_hi for q in quad):
                            conn = [lut_lo[q] for q in quad] + [lut_hi[q] for q in quad]
                            eid += 1
                            self.elements[eid] = (elset, conn)
                            self.elsets[elset].append(eid)

    # -- topology helpers ----------------------------------------------------
    @property
    def p_bridge_top(self):
        return self.seg_plane_range[0][1]

    @property
    def p_stageb_bot(self):
        return self.seg_plane_range[1][0]

    @property
    def p_stageb_top(self):
        return self.seg_plane_range[2][1]

    @property
    def p_stagea_bot(self):
        return self.seg_plane_range[3][0]

    @property
    def p_stagea_top(self):
        return self.seg_plane_range[3][1]

    def centroid(self, eid):
        conn = self.elements[eid][1]
        return tuple(sum(self.nodes[n][k] for n in conn) / 8.0 for k in range(3))

    def volume(self, eid):
        """Elements are axis-aligned boxes by construction."""
        conn = self.elements[eid][1]
        xs = [self.nodes[n][0] for n in conn]
        ys = [self.nodes[n][1] for n in conn]
        zs = [self.nodes[n][2] for n in conn]
        return (max(xs) - min(xs)) * (max(ys) - min(ys)) * (max(zs) - min(zs))

    def disk_nodes(self, plane_idx, centre, radius):
        out = []
        for nid in self.planes[plane_idx]["lut"].values():
            x, y, _z = self.nodes[nid]
            if math.hypot(x - centre[0], y - centre[1]) <= radius:
                out.append(nid)
        return sorted(out)

    def fixed_nodes(self):
        return sorted(self.planes[0]["lut"].values())


def build_joints(mesh):
    """Per-bolt kinematic-coupling node sets, FEA-1 auto-grow rule preserved."""
    records = []
    nsets = {}

    def make(tag, centres, r_b, plane_lo, plane_hi):
        for i, c in enumerate(centres):
            name = "%s_%d" % (tag, i + 1)
            r = r_b
            while True:
                lo = mesh.disk_nodes(plane_lo, c, r)
                hi = mesh.disk_nodes(plane_hi, c, r)
                if lo and hi:
                    break
                r *= 1.15
                if r > 25.0:
                    raise RuntimeError("bolt disk %s captures no node" % name)
            nsets["NS_" + name] = lo + hi
            # coplanarity / collinearity diagnosis (explains COARSE solver
            # singularity warnings on the free coupling reference nodes)
            pts = sorted(set((round(mesh.nodes[n][0], 6), round(mesh.nodes[n][1], 6))
                             for n in lo + hi))
            collinear = _collinear(pts)
            records.append({
                "joint": name, "centre_xy": list(c),
                "r_b_nominal_mm": r_b, "r_b_used_mm": round(r, 4),
                "nodes_face_lo": len(lo), "nodes_face_hi": len(hi),
                "auto_grown": r > r_b * 1.0001,
                "distinct_xy_points": len(pts),
                "coupled_set_collinear_in_xy": collinear,
                "expected_free_rotational_dof_singularity": collinear,
            })

    make("M6", GEOM["m6_centres"], GEOM["r_b_m6"],
         mesh.p_bridge_top, mesh.p_stageb_bot)
    make("M5", m5_centres(), GEOM["r_b_m5"],
         mesh.p_stageb_top, mesh.p_stagea_bot)

    spider = []
    for i, c in enumerate(GEOM["m4_centres_asbuilt"]):
        r = GEOM["r_b_m4"]
        while True:
            nd = mesh.disk_nodes(mesh.p_stagea_top, c, r)
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
    nsets["NS_ARM_SPIDER"] = sorted(set(spider))
    return records, nsets


def _collinear(pts):
    if len(pts) < 3:
        return True
    x0, y0 = pts[0]
    ux, uy = None, None
    for x, y in pts[1:]:
        dx, dy = x - x0, y - y0
        if abs(dx) + abs(dy) < 1e-9:
            continue
        if ux is None:
            ux, uy = dx, dy
            continue
        if abs(dx * uy - dy * ux) > 1e-6:
            return False
    return True


def nearest_element(mesh, elset, target):
    best, bd = None, None
    for eid in mesh.elsets[elset]:
        c = mesh.centroid(eid)
        d = math.dist(c, target)
        if bd is None or d < bd:
            best, bd = eid, d
    return best


def write_deck(path, mesh, records, nsets, case_id, case, level_id, level_spec,
               material_id, eltype):
    mat = MATERIALS[material_id]
    fixed = mesh.fixed_nodes()
    probes = {
        "EPROBE_M6_BRIDGE": nearest_element(mesh, "EBRIDGE", (63.0, 63.0, 10.75)),
        "EPROBE_BORE_STAGEB": nearest_element(
            mesh, "ESTAGEB",
            (50.0 * math.cos(math.radians(45)), 50.0 * math.sin(math.radians(45)), 17.0)),
        "EPROBE_M4_STAGEA": nearest_element(mesh, "ESTAGEA", (15.494, 42.4393, 30.75)),
        "EPROBE_HOLE_BRIDGE": nearest_element(mesh, "EBRIDGE", (20.0, 0.0, 5.0)),
    }

    lines = []
    A = lines.append
    A("*HEADING")
    A("FEA1B_M3R_INTERFACE  case=%s  mesh=%s  eltype=%s  material=%s"
      % (case_id, level_id, eltype, material_id))
    A("M7 WP7 FEA_OPERATIONAL element-formulation closure (ODR-11/ODR-12).")
    A("Units: N, mm, MPa, tonne. Linear static. DESIGN_INDICATIVE results only.")
    A("** ELEMENT_FORMULATION: %s -- %s" % (eltype, ELEMENT_TYPES[eltype]))
    A("** MESH_SERIES: %s  n_xy=%d (pitch %.6g mm)  kz=%d"
      % (level_spec[2], level_spec[0], mesh.h, level_spec[1]))
    for a in ASSUMPTION_REGISTER_B:
        A("** ASSUMPTION: " + a)
    A("** Case load: F_y=%.17g N, M_z=%.17g N*mm (%s)"
      % (case["F_N"], case["M_N_m"] * 1000.0, case["derivation"]))
    A("**")
    A("*NODE")
    for nid in sorted(mesh.nodes):
        x, y, z = mesh.nodes[nid]
        A("%d,%.6f,%.6f,%.6f" % (nid, x, y, z))
    A("%d,0.0,0.0,30.75" % RP_ARM)
    for i, c in enumerate(GEOM["m6_centres"]):
        A("%d,%.6f,%.6f,10.75" % (RP_M6_BASE + i, c[0], c[1]))
    for i, c in enumerate(m5_centres()):
        A("%d,%.6f,%.6f,22.75" % (RP_M5_BASE + i, c[0], c[1]))
    A("*ELEMENT,TYPE=%s,ELSET=EALL" % eltype)
    for eid in sorted(mesh.elements):
        A("%d,%s" % (eid, ",".join(str(n) for n in mesh.elements[eid][1])))
    for elset in ("EBRIDGE", "ESTAGEB", "ESTAGEA"):
        ids = mesh.elsets[elset]
        A("*ELSET,ELSET=%s" % elset)
        for i in range(0, len(ids), 16):
            A(",".join(str(e) for e in ids[i:i + 16]))
    A("*ELSET,ELSET=EPROBES")
    A(",".join(str(v) for v in probes.values()))
    A("*NSET,NSET=NFIXED")
    for i in range(0, len(fixed), 16):
        A(",".join(str(n) for n in fixed[i:i + 16]))
    A("*NSET,NSET=NRP")
    A("%d" % RP_ARM)
    for name in sorted(nsets):
        ids = nsets[name]
        A("*NSET,NSET=%s" % name)
        for i in range(0, len(ids), 16):
            A(",".join(str(n) for n in ids[i:i + 16]))
    A("*MATERIAL,NAME=%s" % material_id)
    A("*ELASTIC")
    A("%.1f,%.2f" % (mat["E_MPa"], mat["nu"]))
    A("*DENSITY")
    A("%.3e" % mat["rho_t_mm3"])
    for elset in ("EBRIDGE", "ESTAGEB", "ESTAGEA"):
        A("*SOLID SECTION,ELSET=%s,MATERIAL=%s" % (elset, material_id))
    A("*BOUNDARY")
    A("NFIXED,ENCASTRE")
    A("** joint couplings (bolt-disk rigid zones) -- identical to solved FEA-1")
    for name in sorted(nsets):
        A("*SURFACE,TYPE=NODE,NAME=S_%s" % name)
        A("%s," % name)
    for i in range(len(GEOM["m6_centres"])):
        A("*COUPLING,CONSTRAINT NAME=M6_%d,REF NODE=%d,SURFACE=S_NS_M6_%d"
          % (i + 1, RP_M6_BASE + i, i + 1))
        A("*KINEMATIC")
        A("1,6")
    for i in range(GEOM["m5_count"]):
        A("*COUPLING,CONSTRAINT NAME=M5_%d,REF NODE=%d,SURFACE=S_NS_M5_%d"
          % (i + 1, RP_M5_BASE + i, i + 1))
        A("*KINEMATIC")
        A("1,6")
    A("*COUPLING,CONSTRAINT NAME=ARM_SPIDER,REF NODE=%d,SURFACE=S_NS_ARM_SPIDER"
      % RP_ARM)
    A("*KINEMATIC")
    A("1,6")
    A("*STEP,NAME=QS_STEP,NLGEOM=NO")
    A("*STATIC")
    A("1.0,1.0")
    A("*CLOAD")
    A("%d,2,%.17g" % (RP_ARM, case["F_N"]))
    A("%d,6,%.17g" % (RP_ARM, case["M_N_m"] * 1000.0))
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

    zone_layers = {}
    for si, (elset, z0, z1, _fp, base) in enumerate(SEGMENTS):
        zone_layers.setdefault(elset, []).append(
            {"z0": z0, "z1": z1, "layers": base * mesh.kz,
             "dz_mm": (z1 - z0) / float(base * mesh.kz)})

    sidecar = {
        "case_id": case_id, "mesh_level": level_id, "material": material_id,
        "element_type": eltype,
        "element_type_rationale": ELEMENT_TYPES[eltype],
        "series": level_spec[2],
        "n_xy": level_spec[0], "kz": level_spec[1],
        "nodes_structural": len(mesh.nodes),
        "nodes_total_incl_reference": len(mesh.nodes) + 1 + 4 + GEOM["m5_count"],
        "elements_total": len(mesh.elements),
        "elements_per_zone": {k: len(v) for k, v in mesh.elsets.items()},
        "grid_pitch_mm": mesh.h,
        "z_layering": zone_layers,
        "n_planes": len(mesh.planes),
        "rp_node": RP_ARM,
        "ref_nodes_m6": [RP_M6_BASE + i for i in range(4)],
        "ref_nodes_m5": [RP_M5_BASE + i for i in range(GEOM["m5_count"])],
        "n_fixed_nodes": len(fixed),
        "probe_elements": probes,
        "joint_records": records,
        "spider_node_count": len(nsets["NS_ARM_SPIDER"]),
        "applied_load": {"F_y_N": case["F_N"], "M_z_N_mm": case["M_N_m"] * 1000.0,
                         "rp_coords": [0.0, 0.0, 30.75],
                         "derivation": case["derivation"],
                         "source_class": case.get("source_class")},
        "element_volume_total_mm3": sum(mesh.volume(e) for e in mesh.elements),
        "element_centroids_and_volumes_available_in": "geometry sidecar below",
        "far_field_rule": FAR_FIELD_RULE,
        "deck_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest().upper(),
        "deck_bytes": len(text.encode("utf-8")),
    }
    return sidecar


def geometry_sidecar(mesh, level_id, records, nsets):
    """Mesh geometry needed by the extractor (centroids, volumes, regions)."""
    bolt_centres = ([tuple(c) for c in GEOM["m6_centres"]]
                    + [tuple(c) for c in m5_centres()]
                    + [tuple(c) for c in GEOM["m4_centres_asbuilt"]])
    rb = FAR_FIELD_RULE["bolt_centre_exclusion_radius_mm"]
    band = FAR_FIELD_RULE["stepped_boundary_exclusion_band_mm"]
    radii = FAR_FIELD_RULE["stepped_radii_mm"]
    els = {}
    for eid in sorted(mesh.elements):
        elset, _conn = mesh.elements[eid]
        cx, cy, cz = mesh.centroid(eid)
        vol = mesh.volume(eid)
        rc = math.hypot(cx, cy)
        near_bolt = any(math.hypot(cx - c[0], cy - c[1]) <= rb for c in bolt_centres)
        near_step = any(abs(rc - r) <= band for r in radii)
        els[str(eid)] = {
            "zone": elset,
            "c": [round(cx, 6), round(cy, 6), round(cz, 6)],
            "v": vol,
            "r": round(rc, 6),
            "far_field": (not near_bolt) and (not near_step),
            "near_bolt": near_bolt,
            "near_step": near_step,
        }
    return {
        "mesh_level": level_id,
        "grid_pitch_mm": mesh.h,
        "kz": mesh.kz,
        "n_planes": len(mesh.planes),
        "plane_z": [p["z"] for p in mesh.planes],
        "far_field_rule": FAR_FIELD_RULE,
        "spider_nodes": nsets["NS_ARM_SPIDER"],
        "fixed_nodes": mesh.fixed_nodes(),
        "elements": els,
        "n_far_field_elements": sum(1 for v in els.values() if v["far_field"]),
        "joint_records": records,
    }


def traceability_case_variant(cases):
    """Single-row-consistent CAP150_030 load case (traceability sensitivity).

    The FEA-1 CAPTURE_150KG_QS deck combines J from envelope row CAP150_030
    (0.677633 N*s, the family maximum impulse) with C from row CAP150_005
    (0.130197 N*m*s, the family maximum grasp couple) while the deck comment
    declares only 'row CAP150_030'. Both numbers ARE the declared upper bounds
    of AUTHORIZED_MECHANICAL_LOADS_V1.yaml capture_150kg_anchor, so the applied
    load is a component-wise envelope, not a single row. This variant re-runs
    the same case with the row-consistent CAP150_030 couple so the effect of
    the 1.760% conservative M_z bias is measured, not argued.
    """
    env = F1.CAPTURE_ENVELOPE["CAPTURE_150KG_QS"]
    j = env["J_N_s"]                       # CAP150_030 impulse (unchanged)
    c_row030 = 0.113705                    # CAP150_030 grasp couple
    f = POLICY["daf"] * j / POLICY["dt_contact_s"]
    m = f * env["L_m"] + POLICY["daf"] * c_row030 / POLICY["dt_contact_s"]
    base = cases["CAPTURE_150KG_QS"]
    return {
        "F_N": f, "M_N_m": m,
        "derivation": "F=DAF*J/dt (CAP150_030 J=0.677633); "
                      "M=F*L_grasp+DAF*C/dt with ROW-CONSISTENT "
                      "CAP150_030 C=0.113705 (envelope-max C=0.130197 not used)",
        "source_class": "DERIVED_ENVELOPE_SINGLE_ROW_CONSISTENT",
        "delta_Mz_vs_envelope_pct": (base["M_N_m"] / m - 1.0) * 100.0,
    }


def job_name(case_id, level_id, material_id, eltype, suffix=""):
    s = "fea1b_%s_%s_%s" % (case_id.lower(), level_id.lower(), eltype.lower())
    if material_id != "AL6061_T6_CAND":
        s += "_7075"
    if suffix:
        s += "_" + suffix
    return s


def build_all(deck_dir, side_dir):
    os.makedirs(deck_dir, exist_ok=True)
    os.makedirs(side_dir, exist_ok=True)
    cases = F1.compute_case_loads()
    cases_row030 = traceability_case_variant(cases)

    meshes, joints = {}, {}
    for lid, spec in MESH_LEVELS_B.items():
        m = MeshB(spec[0], spec[1])
        meshes[lid] = m
        joints[lid] = build_joints(m)
        with open(os.path.join(side_dir, "GEOM_%s.json" % lid), "w") as f:
            json.dump(geometry_sidecar(m, lid, joints[lid][0], joints[lid][1]),
                      f, indent=1, sort_keys=True)

    plan = []
    order = ["ARM_MANEUVER_QS", "ARM_ESTOP_QS", "CAPTURE_22KG_QS", "CAPTURE_150KG_QS"]
    # A) mesh-matched + B) through-thickness + Z) z-refinement, 4 cases, C3D8I
    for lid in ["L1_MM_COARSE", "L2_MM_MEDIUM", "L3_MM_FINE",
                "T2_TT_MEDIUM", "T3_TT_FINE", "T4_TT_ULTRA",
                "Z2_ZR_N20K2", "Z4_ZR_N20K4", "Z6_ZR_N20K6"]:
        for cid in order:
            plan.append((cid, cases[cid], lid, "AL6061_T6_CAND", "C3D8I", ""))
    # Z8/Z12: governing case only (Richardson verification)
    for lid in ["Z8_ZR_N20K8", "Z12_ZR_N20K12"]:
        plan.append(("CAPTURE_150KG_QS", cases["CAPTURE_150KG_QS"], lid,
                     "AL6061_T6_CAND", "C3D8I", ""))
    # C) cross-checks
    for lid in ["L1_MM_COARSE", "L2_MM_MEDIUM", "L3_MM_FINE", "Z4_ZR_N20K4"]:
        plan.append(("CAPTURE_150KG_QS", cases["CAPTURE_150KG_QS"], lid,
                     "AL6061_T6_CAND", "C3D8", ""))
    for lid in ["L3_MM_FINE", "T4_TT_ULTRA", "Z4_ZR_N20K4"]:
        plan.append(("CAPTURE_150KG_QS", cases["CAPTURE_150KG_QS"], lid,
                     "AL7075_T651_CAND", "C3D8I", ""))
        plan.append(("CAPTURE_150KG_QS", cases_row030, lid,
                     "AL6061_T6_CAND", "C3D8I", "row030"))

    matrix = []
    for cid, case, lid, mid, et, sfx in plan:
        jn = job_name(cid, lid, mid, et, sfx)
        recs, nsets = joints[lid]
        sc = write_deck(os.path.join(deck_dir, jn + ".inp"), meshes[lid], recs,
                        nsets, cid, case, lid, MESH_LEVELS_B[lid], mid, et)
        sc["job_name"] = jn
        sc["load_variant"] = sfx or "ENVELOPE_COMPONENTWISE_MAX"
        with open(os.path.join(side_dir, jn + ".json"), "w") as f:
            json.dump(sc, f, indent=1, sort_keys=True)
        matrix.append(sc)
    with open(os.path.join(side_dir, "_PLAN.json"), "w") as f:
        json.dump({"jobs": [s["job_name"] for s in matrix],
                   "levels": {k: list(v) for k, v in MESH_LEVELS_B.items()},
                   "cases": {k: {kk: vv for kk, vv in v.items()} for k, v in cases.items()},
                   "case_row030_variant": cases_row030},
                  f, indent=1, sort_keys=True)
    return matrix


if __name__ == "__main__":
    mtx = build_all(os.path.join(HERE, "decks_b"), os.path.join(HERE, "jobs_b"))
    seen = set()
    for sc in mtx:
        key = (sc["mesh_level"], sc["element_type"])
        tag = "" if key in seen else "  <-- new mesh/eltype"
        seen.add(key)
        print("%-58s el=%6d nd=%6d pitch=%6.3f kz=%d%s" % (
            sc["job_name"], sc["elements_total"], sc["nodes_structural"],
            sc["grid_pitch_mm"], sc["kz"], tag))
    print("total jobs: %d" % len(mtx))
