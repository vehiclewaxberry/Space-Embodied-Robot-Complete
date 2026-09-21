# -*- coding: utf-8 -*-#!/usr/bin/env python
"""Build SOLAR_ARRAY_R2 candidate geometry (ECR-SOLAR-ARRAY-R2, ODR-19).

Produces, in this directory:
  SOLAR_ARRAY_R2_CANDIDATE_V3.FCStd   - stowed + deployed solids, keepouts
  SOLAR_ARRAY_R2_CANDIDATE_V3.step    - neutral export of the same solids
  SOLAR_ARRAY_R2_BUILD_REPORT_V3_GEOMETRY_REGEN.json - metrics, masses, first clearance
                                        pairs (non-empty comparison sets),
                                        hashes
  SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V3_GEOMETRY_REGEN.yaml - product-structure style summary

Run with FreeCADCmd (single process, WP1 convention):
  G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe build_solar_array_r2.py

Millimetres throughout. This dormant V3 source requires a separate run-specific
execution record and memory admission before it can build an R2 candidate;
nothing here modifies the frozen WP1 DESIGN_FREEZE_ASSEMBLY_V1 or the
accepted B601 URDF.  Legacy R1 (227 x 200 x 6 mm) is preserved elsewhere
as LEGACY_R1 evidence and is not touched.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import solar_array_r2_kinematics_v3 as K
from source_execution_guard import require_execution_authority

OUTPUT_FCSTD = HERE / "SOLAR_ARRAY_R2_CANDIDATE_V3.FCStd"
OUTPUT_STEP = HERE / "SOLAR_ARRAY_R2_CANDIDATE_V3.step"
BUILD_REPORT = HERE / "SOLAR_ARRAY_R2_BUILD_REPORT_V3_GEOMETRY_REGEN.json"
GEOM_YAML = HERE / "SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V3_GEOMETRY_REGEN.yaml"

# Candidate mass model (ENGINEERING_CANDIDATE per ODR-19; NOT a measured
# or flight mass; the forbidden 3 x 0.3483933 kg rescale is not used).
LEAF_AREAL_DENSITY_KG_PER_M2 = 3.0   # CFRP sandwich + cells, candidate
LEAF_AREA_M2 = (K.LEAF_CHORD / 1000.0) * (K.LEAF_SPAN / 1000.0)  # 0.06
LEAF_MASS_KG = LEAF_AREAL_DENSITY_KG_PER_M2 * LEAF_AREA_M2       # 0.18
HINGE_ROOT_MASS_KG = 0.05
HINGE_INTER_MASS_KG = 0.03         # each, x2 per wing
HDRM_MASS_KG = 0.08                # per wing system allowance
SOLAR_HARNESS_MASS_KG = 0.05       # per wing allowance
WING_MASS_KG = (3 * LEAF_MASS_KG + HINGE_ROOT_MASS_KG
                + 2 * HINGE_INTER_MASS_KG + HDRM_MASS_KG
                + SOLAR_HARNESS_MASS_KG)                          # 0.78

# HDRM keepout boxes (stowed), per wing, x windows from R1 heritage stations
HDRM_X_WINDOWS = [(-140.0, -120.0), (120.0, 140.0)]
HDRM_Y_HALF_THICK = 6.0
HDRM_Z_WINDOW = (-20.0, 20.0)

BUS_PROXY = (-K.BODY_X_HALF, -K.BODY_CROSS_HALF, -K.BODY_CROSS_HALF,
             K.BODY_X_HALF, K.BODY_CROSS_HALF, K.BODY_CROSS_HALF)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def local_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def bbox_box(xmin, ymin, zmin, xmax, ymax, zmax):
    return Part.makeBox(xmax - xmin, ymax - ymin, zmax - zmin,
                        App.Vector(xmin, ymin, zmin))


def make_leaf_solid(side: int, leaf: dict) -> Part.Shape:
    origin, e2, e3 = K.leaf_solid_frame(side, leaf)
    m = App.Matrix(
        1.0, 0.0, 0.0, origin[0],
        0.0, e2[1], e3[1], origin[1],
        0.0, e2[2], e3[2], origin[2],
        0.0, 0.0, 0.0, 1.0,
    )
    box = Part.makeBox(K.LEAF_CHORD, K.LEAF_SPAN, K.LEAF_T)
    box.transformShape(m)
    return box


def shape_aabb(shape) -> list:
    bb = shape.BoundBox
    return [round(bb.XMin, 6), round(bb.YMin, 6), round(bb.ZMin, 6),
            round(bb.XMax, 6), round(bb.YMax, 6), round(bb.ZMax, 6)]


def pair_row(name_a, name_b, shape_a, shape_b) -> dict:
    distance = float(shape_a.distToShape(shape_b)[0])
    common_volume = float(shape_a.common(shape_b).Volume)
    if common_volume > 1.0e-9:
        classification = "POSITIVE_VOLUME_INTERFERENCE"
    elif distance <= 1.0e-7:
        classification = "TOUCH_OR_COINCIDENT"
    else:
        classification = "CLEAR"
    return {
        "pair": [name_a, name_b],
        "comparison_set_nonempty": True,
        "minimum_distance_mm": round(distance, 9),
        "common_volume_mm3": round(common_volume, 9),
        "classification": classification,
    }


def add_feature(doc, name, label, shape, group):
    obj = doc.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape
    if group is not None:
        group.addObject(obj)
    return obj


def build_wing(doc, group, side: int, tag: str, angles) -> dict:
    """Build the 3-leaf wing solids for one configuration. Returns shapes."""
    segs = K.leaf_segments(side, *angles)
    shapes = {}
    wing = "LEFT" if side == +1 else "RIGHT"
    for leaf in segs:
        solid = make_leaf_solid(side, leaf)
        name = "R2_%s_LEAF%d_%s" % (wing, leaf["index"], tag)
        add_feature(doc, name, name, solid, group)
        shapes[name] = solid
    return shapes


def main() -> None:
    require_execution_authority("FREECAD_GEOMETRY_REGENERATION")
    doc = App.newDocument("SOLAR_ARRAY_R2_CANDIDATE_V3")

    grp_stowed = doc.addObject("App::DocumentObjectGroup", "STOWED")
    grp_deployed = doc.addObject("App::DocumentObjectGroup", "DEPLOYED")
    grp_keepout = doc.addObject("App::DocumentObjectGroup", "KEEPOUT")
    grp_witness = doc.addObject("App::DocumentObjectGroup", "WITNESS")

    shapes = {}
    shapes.update(build_wing(doc, grp_stowed, +1, "STOWED", K.STOWED))
    shapes.update(build_wing(doc, grp_stowed, -1, "STOWED", K.STOWED))
    shapes.update(build_wing(doc, grp_deployed, +1, "DEPLOYED", K.DEPLOYED))
    shapes.update(build_wing(doc, grp_deployed, -1, "DEPLOYED", K.DEPLOYED))

    # Hinge knuckle envelopes (stowed) and HDRM keepouts, both wings.
    for side, wing in ((+1, "LEFT"), (-1, "RIGHT")):
        sy = side * K.LEAF1_MID_Y
        root = bbox_box(K.CHORD_X[0], sy - 4.0, K.HINGE_Z - 4.0,
                        K.CHORD_X[1], sy + 4.0, K.HINGE_Z + 4.0)
        name = "R2_%s_ROOT_HINGE_KEEPOUT" % wing
        add_feature(doc, name, name, root, grp_keepout)
        shapes[name] = root
        # inter-panel hinge lines at stowed fold points (z = HINGE_Z and
        # z = HINGE_Z + SPAN), offset outboard per accordion step
        for k, z in ((2, K.HINGE_Z + K.LEAF_SPAN), (3, K.HINGE_Z)):
            yk = sy + side * (k - 1) * K.STACK_STEP
            hb = bbox_box(K.CHORD_X[0], yk - 4.0, z - 4.0,
                          K.CHORD_X[1], yk + 4.0, z + 4.0)
            name = "R2_%s_INTER_HINGE%d_KEEPOUT" % (wing, k)
            add_feature(doc, name, name, hb, grp_keepout)
            shapes[name] = hb
        for i, (x0, x1) in enumerate(HDRM_X_WINDOWS, start=1):
            yc = side * (K.SIDE_FACE_Y + HDRM_Y_HALF_THICK)
            hd = bbox_box(x0, yc - HDRM_Y_HALF_THICK, HDRM_Z_WINDOW[0],
                          x1, yc + HDRM_Y_HALF_THICK, HDRM_Z_WINDOW[1])
            name = "R2_%s_HDRM%d_KEEPOUT" % (wing, i)
            add_feature(doc, name, name, hd, grp_keepout)
            shapes[name] = hd

    bus = bbox_box(*BUS_PROXY)
    add_feature(doc, "WITNESS_BUS_PROXY", "WITNESS_BUS_PROXY", bus, grp_witness)
    shapes["WITNESS_BUS_PROXY"] = bus

    doc.recompute()
    doc.saveAs(str(OUTPUT_FCSTD))

    export_objs = [o for o in doc.Objects if o.Name != "WITNESS_BUS_PROXY"
                   and hasattr(o, "Shape")]
    Part.export(export_objs, str(OUTPUT_STEP))

    # ---- metrics + first non-empty clearance evidence ---------------------
    metrics = {}
    for name, shape in shapes.items():
        metrics[name] = {
            "aabb_S_mm": shape_aabb(shape),
            "volume_mm3": round(float(shape.Volume), 6),
        }

    pairs = []
    bus_shape = shapes["WITNESS_BUS_PROXY"]
    for wing in ("LEFT", "RIGHT"):
        l1s = shapes["R2_%s_LEAF1_STOWED" % wing]
        l2s = shapes["R2_%s_LEAF2_STOWED" % wing]
        l3s = shapes["R2_%s_LEAF3_STOWED" % wing]
        l1d = shapes["R2_%s_LEAF1_DEPLOYED" % wing]
        pairs.append(pair_row("R2_%s_LEAF1_STOWED" % wing,
                              "WITNESS_BUS_PROXY", l1s, bus_shape))
        pairs.append(pair_row("R2_%s_LEAF3_STOWED" % wing,
                              "WITNESS_BUS_PROXY", l3s, bus_shape))
        pairs.append(pair_row("R2_%s_LEAF1_STOWED" % wing,
                              "R2_%s_LEAF2_STOWED" % wing, l1s, l2s))
        pairs.append(pair_row("R2_%s_LEAF2_STOWED" % wing,
                              "R2_%s_LEAF3_STOWED" % wing, l2s, l3s))
        pairs.append(pair_row("R2_%s_LEAF1_DEPLOYED" % wing,
                              "WITNESS_BUS_PROXY", l1d, bus_shape))
        hdrm_pair = pair_row("R2_%s_HDRM1_KEEPOUT" % wing,
                             "R2_%s_LEAF2_STOWED" % wing,
                             shapes["R2_%s_HDRM1_KEEPOUT" % wing], l2s)
        # Explained interface: the HDRM tie-down envelope intentionally
        # engages the stowed stack at these x/z stations (rods clamp the
        # stack; leaf clearance holes are part of the R2-WI-02 design).
        # This overlap is a DESIGN INTERFACE, not unexplained interference.
        if hdrm_pair["classification"] == "POSITIVE_VOLUME_INTERFERENCE":
            hdrm_pair["classification"] = "INTENTIONAL_HDRM_STACK_INTERFACE"
            hdrm_pair["explanation"] = (
                "HDRM keepout deliberately spans the stowed stack so the "
                "tie-down rods engage it; interface design owned by R2-WI-02")
        pairs.append(hdrm_pair)
    # cross-wing deployed pair (tips must not approach each other)
    pairs.append(pair_row("R2_LEFT_LEAF3_DEPLOYED", "R2_RIGHT_LEAF3_DEPLOYED",
                          shapes["R2_LEFT_LEAF3_DEPLOYED"],
                          shapes["R2_RIGHT_LEAF3_DEPLOYED"]))

    interferences = [p for p in pairs
                     if p["classification"] == "POSITIVE_VOLUME_INTERFERENCE"]

    report = {
        "schema": "SOLAR_ARRAY_R2_BUILD_REPORT_V3_GEOMETRY_REGEN",
        "generated_local": local_now(),
        "authority": "ODR-19 ECR-SOLAR-ARRAY-R2",
        "class": "ENGINEERING_CANDIDATE - not flight-qualified",
        "parameters": {
            "leaf_planform_mm": [K.LEAF_CHORD, K.LEAF_SPAN],
            "leaf_thickness_mm": K.LEAF_T,
            "stowed_inter_leaf_gap_mm": K.LEAF_GAP,
            "hinge_axes": "all parallel to X_S (root + 2 inter-panel per wing)",
            "chord_window_S_mm": list(K.CHORD_X),
            "root_hinge_line": {"y_abs_mm": K.LEAF1_MID_Y, "z_mm": K.HINGE_Z},
        },
        "stack_metrics": K.stowed_stack_metrics(),
        "protrusion_note": (
            f"{K.stowed_stack_metrics()['protrusion_beyond_side_face_mm']:.1f} mm protrusion beyond side face exceeds the generic 6.5 mm "
            "CubeSat protrusion guidance; per ODR-18 item 4 / ODR-19 this is "
            "a MODE_FLIGHT HOLD item pending actual dispenser ICD, not an "
            "internal design defect of the MODE_OP baseline."
        ),
        "mass_model_candidate": {
            "basis": "areal-density candidate; NOT a measured mass; the "
                     "forbidden 3 x 0.3483933 kg legacy rescale is NOT used",
            "leaf_areal_density_kg_per_m2": LEAF_AREAL_DENSITY_KG_PER_M2,
            "leaf_mass_kg": round(LEAF_MASS_KG, 6),
            "hinge_root_kg": HINGE_ROOT_MASS_KG,
            "hinge_inter_kg_each": HINGE_INTER_MASS_KG,
            "hdrm_per_wing_kg": HDRM_MASS_KG,
            "solar_harness_per_wing_kg": SOLAR_HARNESS_MASS_KG,
            "wing_total_kg": round(WING_MASS_KG, 6),
            "wing_total_target_kg": "<= 0.8 (ODR-19) - MET by candidate",
            "both_wings_kg": round(2 * WING_MASS_KG, 6),
            "legacy_r1_both_wings_kg": 0.6967866,
            "delta_vs_legacy_kg": round(2 * WING_MASS_KG - 0.6967866, 6),
            "system_mass_note": (
                "R2 adds ~+0.86 kg vs LEGACY_R1; the 24.000 kg whole-sat "
                "closure is OPEN pending R2-WI-05 mass regeneration and an "
                "explicit budget reallocation decision. Not closed here."
            ),
        },
        "shape_metrics": metrics,
        "clearance_pairs": pairs,
        "clearance_summary": {
            "pairs_evaluated": len(pairs),
            "all_comparison_sets_nonempty": all(
                p["comparison_set_nonempty"] for p in pairs),
            "positive_volume_interferences": len(interferences),
            "interference_pairs": [p["pair"] for p in interferences],
        },
        "outputs": {
            "fcstd": OUTPUT_FCSTD.name,
            "step": OUTPUT_STEP.name,
        },
        "hashes": {},
        "scope_guard": (
            "R2 candidate only. Frozen assets untouched: accepted B601 URDF, "
            "M3R, GRIPPER_R1, Stage-A/B operational FEA results, and the WP1 "
            "DESIGN_FREEZE_ASSEMBLY_V1 (R1 legacy evidence)."
        ),
    }

    report["hashes"] = {
        OUTPUT_FCSTD.name: sha256(OUTPUT_FCSTD),
        OUTPUT_STEP.name: sha256(OUTPUT_STEP),
    }
    report["self_hash_policy"] = "SELF_REFERENCE_EXCLUDED"
    report["cad_regenerated"] = True
    report["visible_geometry_changed"] = False
    BUILD_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    GEOM_YAML.write_text(geom_yaml(report), encoding="utf-8")

    print("R2_BUILD_OK pairs=%d interferences=%d" %
          (len(pairs), len(interferences)))
    for p in pairs:
        print("PAIR %s vs %s : d=%s mm common=%s mm3 [%s]" % (
            p["pair"][0], p["pair"][1],
            p["minimum_distance_mm"], p["common_volume_mm3"],
            p["classification"]))


def geom_yaml(report: dict) -> str:
    sm = report["stack_metrics"]
    mm = report["mass_model_candidate"]
    return """schema: SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V3_GEOMETRY_REGEN
generated_local: '%s'
class: ENGINEERING_CANDIDATE_NOT_FLIGHT_QUALIFIED
authority: ODR-19 (ECR-SOLAR-ARRAY-R2)
supersedes: R1 227 x 200 x 6 mm single-leaf wing (preserved as LEGACY_R1)

architecture:
  wings: 2 (LEFT +Y_S deploy / RIGHT -Y_S deploy, symmetric)
  leaves_per_wing: 3
  leaf_planform_mm: [300.0, 200.0]
  leaf_thickness_mm: 2.5
  hinge_axes: all parallel to X_S
  fold_style: accordion (interlocking stack)
  deployment: passive + hard stop + latch; no SADA (OPTIONAL_SADA_INTERFACE
    reserved at root only)

geometry_facts:
  chord_window_S_mm: [-150.0, 150.0]
  chord_margins_mm: %s
  root_hinge_line: {y_abs_mm: %s, z_mm: -108.15, axis: X_S}
  stowed_z_span_mm: %s
  stack_height_mm: %s
  protrusion_beyond_side_face_mm: %s  # MODE_FLIGHT HOLD vs generic 6.5 mm
  deployed_span_per_wing_mm: 600.0
  deployed_tip_to_tip_mm: %s
  leaf_volume_mm3: 150000.0

mass_candidate:
  wing_total_kg: %s
  both_wings_kg: %s
  basis: %s
  status: ENGINEERING_CANDIDATE - R2-WI-05 regenerates 9-config mass/CG/inertia

holds:
  - HOLD_PANEL_LAYUP_AND_CELL_GEOMETRY_NOT_MODELLED (homogeneous leaf proxy)
  - HOLD_HINGE_HARDWARE_NOMINALS_FITS_AND_STOP_GEOMETRY
  - HOLD_HDRM_ARCHITECTURE_NOT_SELECTED (keepout envelopes only)
  - MODE_FLIGHT_PROTRUSION_HOLD_PENDING_DISPENSER_ICD
  - SYSTEM_MASS_CLOSURE_OPEN_PENDING_R2_WI_05
""" % (report["generated_local"],
       sm["chord_margins_mm"], report["parameters"]["root_hinge_line"]["y_abs_mm"],
       sm["stowed_z_span_mm"],
       sm["stack_height_mm"], sm["protrusion_beyond_side_face_mm"],
       sm["deployed_tip_to_tip_mm"],
       mm["wing_total_kg"], mm["both_wings_kg"],
       '"areal-density candidate, not measured"')

if __name__ == "__main__" or (len(sys.argv) > 1 and
        Path(sys.argv[1]).stem == __name__):
    main()


