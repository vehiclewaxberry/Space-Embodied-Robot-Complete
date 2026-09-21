# -*- coding: utf-8 -*-
"""FreeCADCmd builder for the corrected F3R2 two-stage adapter Rev B.

The geometry is additive and lives only in the active F3R2 root.  It does not
edit the accepted URDF, donors, F3R1, the legacy FreeCAD adapter, or the frozen
operational baseline.  Units are millimetres in FreeCAD/OpenCascade.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import FreeCAD
import Part


F3R2 = Path(
    "F:/China Graduate Future Flight Vehicle Innovation Competition/"
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
)
OUT = F3R2 / "03_native_cad/M3_interface_authority/cad"
OUT.mkdir(parents=True, exist_ok=True)

DENSITY_G_MM3 = 2.70e-3  # AL6061-T6 engineering density

PROUD_FLANGE_T = 2.405
RECESSED_DEPTH = 5.595
RING_OUTER_R = 75.0
SPIGOT_R = 49.8
SKIRT_INNER_R = 50.3
BODY_BORE_R = 50.0
BODY_POCKET_OUTER_R = 75.2
M5_PATTERN_R = 62.5
DOWEL_XY = (55.0, 0.0)

RING_NAME = "B601_BASE_INTERFACE_RING_F3R2"
BODY_NAME = "B601_LOAD_SPREADING_ADAPTER_F3R2"
ASM_NAME = "B601_BASE_ADAPTER_F3R2"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def rounded_square(width: float, corner_r: float, z0: float, height: float):
    """Create a rounded-square prism centred on the origin."""
    half = width / 2.0
    core_x = Part.makeBox(width - 2 * corner_r, width, height,
                          FreeCAD.Vector(-half + corner_r, -half, z0))
    core_y = Part.makeBox(width, width - 2 * corner_r, height,
                          FreeCAD.Vector(-half, -half + corner_r, z0))
    shape = core_x.fuse(core_y)
    for x in (-half + corner_r, half - corner_r):
        for y in (-half + corner_r, half - corner_r):
            shape = shape.fuse(Part.makeCylinder(
                corner_r, height, FreeCAD.Vector(x, y, z0)))
    return shape.removeSplitter()


def cut_cyl(shape, radius, x, y, z0, height):
    return shape.cut(Part.makeCylinder(
        radius, height, FreeCAD.Vector(x, y, z0)))


def build_ring():
    # Only 2.405 mm may remain proud of the physical installation face. Rev A
    # put the R62.5 M5 holes through that thin flange alone. Rev B adds a
    # recessed annular skirt, received by a matching pocket in Stage B, so the
    # inter-stage fastener crosses the full 8.0 mm ring thickness.
    flange = Part.makeCylinder(
        RING_OUTER_R, PROUD_FLANGE_T, FreeCAD.Vector(0, 0, 0))
    spigot = Part.makeCylinder(
        SPIGOT_R, RECESSED_DEPTH, FreeCAD.Vector(0, 0, -RECESSED_DEPTH))
    skirt = Part.makeCylinder(
        RING_OUTER_R, RECESSED_DEPTH,
        FreeCAD.Vector(0, 0, -RECESSED_DEPTH)).cut(
            Part.makeCylinder(
                SKIRT_INNER_R, RECESSED_DEPTH,
                FreeCAD.Vector(0, 0, -RECESSED_DEPTH)))
    shape = flange.fuse(spigot).fuse(skirt).removeSplitter()
    shape = cut_cyl(shape, 20.0, 0, 0, -6.0, 9.0)

    # Corrected B601 as-built axis locations in spacecraft-clocked coordinates.
    m4_centres = [
        (15.4940, 42.4393),
        (-42.5096, 15.3917),
        (-15.4621, -42.6120),
        (42.5416, -15.5644),
    ]
    for x, y in m4_centres:
        shape = cut_cyl(shape, 2.30, x, y, -6.0, 9.0)
        # Top-side spotface/counterbore follows the vendor base-plate envelope.
        shape = cut_cyl(shape, 3.75, x, y, -2.095, 4.75)

    # New controlled inter-stage pattern. The first hole is the clocking datum.
    m5_centres = []
    for index in range(8):
        angle = math.radians(22.5 + 45.0 * index)
        x, y = M5_PATTERN_R * math.cos(angle), M5_PATTERN_R * math.sin(angle)
        m5_centres.append((x, y))
        shape = cut_cyl(shape, 2.75, x, y, -6.0, 9.0)
    # One asymmetric dowel candidate removes the 45-degree assembly ambiguity.
    # The ring gets a nominal 4.1 mm clearance; fit/tolerance remain a drawing
    # HOLD and are not implied by the STEP geometry.
    shape = cut_cyl(shape, 2.05, DOWEL_XY[0], DOWEL_XY[1], -6.0, 9.0)
    return shape.removeSplitter(), m4_centres, m5_centres


def build_body(m5_centres):
    shape = rounded_square(160.0, 4.0, -12.0, 12.0)
    # Existing installation passage receives the ring spigot with 0.2 mm
    # diametral radial clearance.
    shape = cut_cyl(shape, BODY_BORE_R, 0, 0, -13.0, 14.0)

    # Annular receiving pocket for the Rev-B ring skirt. Radial clearances are
    # 0.2 mm at both the central spigot and skirt OD. The remaining plate below
    # the pocket is 12 - 5.595 = 6.405 mm.
    pocket = Part.makeCylinder(
        BODY_POCKET_OUTER_R, RECESSED_DEPTH + 0.1,
        FreeCAD.Vector(0, 0, -RECESSED_DEPTH)).cut(
            Part.makeCylinder(
                BODY_BORE_R, RECESSED_DEPTH + 0.1,
                FreeCAD.Vector(0, 0, -RECESSED_DEPTH)))
    shape = shape.cut(pocket)

    # Selected spacecraft-side competition load pattern: four complete M6
    # clearance holes. The legacy M8 pattern is deliberately absent.
    m6_centres = [(-70.0, -70.0), (70.0, -70.0),
                  (-70.0, 70.0), (70.0, 70.0)]
    for x, y in m6_centres:
        shape = cut_cyl(shape, 3.30, x, y, -13.0, 14.0)

    # Rev B uses through M5 fasteners instead of relying on threads below a
    # deep pocket. Exact bolt length, grade, washers/nuts and preload stay TBD.
    for x, y in m5_centres:
        shape = cut_cyl(shape, 2.75, x, y, -13.0, 14.0)

    # Nominal 4.0 mm blind press-fit candidate, 5.5 mm engagement measured from
    # the pocket floor. STEP geometry carries no H7/m6 tolerance claim.
    shape = cut_cyl(
        shape, 2.0, DOWEL_XY[0], DOWEL_XY[1],
        -RECESSED_DEPTH - 5.5, 5.6)
    return shape.removeSplitter(), m6_centres


def add_properties(obj, part_number, description):
    obj.addProperty("App::PropertyString", "PartNumber", "F3R2")
    obj.PartNumber = part_number
    obj.addProperty("App::PropertyString", "Description", "F3R2")
    obj.Description = description
    obj.addProperty("App::PropertyString", "Material", "F3R2")
    obj.Material = "AL6061-T6"
    obj.addProperty("App::PropertyString", "ReleaseScope", "F3R2")
    obj.ReleaseScope = "COMPETITION_PROTOTYPE_MANUFACTURING_CANDIDATE"
    obj.addProperty("App::PropertyString", "Qualification", "F3R2")
    obj.Qualification = "NOT_FLIGHT_RELEASED; FORMAL_FASTENER_MOS_HOLD"


def save_part(name, shape, description):
    doc = FreeCAD.newDocument(name)
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Label = name
    obj.Shape = shape
    add_properties(obj, name, description)
    doc.recompute()
    fcstd = OUT / f"{name}.FCStd"
    step = OUT / f"{name}.step"
    doc.saveAs(str(fcstd))
    Part.export([obj], str(step))
    FreeCAD.closeDocument(doc.Name)
    return fcstd, step


def main():
    ring, m4_centres, m5_centres = build_ring()
    body, m6_centres = build_body(m5_centres)
    ring.check(True)
    body.check(True)

    ring_fc, ring_step = save_part(
        RING_NAME, ring,
        "Corrected four-M4 as-built B601 interface ring; eight-M5 transition"
    )
    body_fc, body_step = save_part(
        BODY_NAME, body,
        "M6 140x140 competition load-spreading body; legacy M8 omitted"
    )

    doc = FreeCAD.newDocument(ASM_NAME)
    body_obj = doc.addObject("PartDesign::Feature", BODY_NAME)
    body_obj.Label = BODY_NAME
    body_obj.Shape = body
    add_properties(body_obj, BODY_NAME, "Stage B load-spreading adapter")
    ring_obj = doc.addObject("PartDesign::Feature", RING_NAME)
    ring_obj.Label = RING_NAME
    ring_obj.Shape = ring
    add_properties(ring_obj, RING_NAME, "Stage A B601 interface ring")
    doc.recompute()
    asm_fc = OUT / f"{ASM_NAME}.FCStd"
    asm_step = OUT / f"{ASM_NAME}.step"
    doc.saveAs(str(asm_fc))
    Part.export([body_obj, ring_obj], str(asm_step))
    FreeCAD.closeDocument(doc.Name)

    common_volume = body.common(ring).Volume
    minimum_distance = body.distToShape(ring)[0]
    outputs = [ring_fc, ring_step, body_fc, body_step, asm_fc, asm_step]
    report = {
        "schema": "M3R_ADAPTER_FREECAD_BUILD_RECEIPT_V2",
        "revision": "B",
        "revision_reason": "replace 2.405-mm-only M5 bearing zone with recessed full-thickness skirt and add unique dowel candidate",
        "builder": "FreeCAD 1.1.3 / OpenCascade",
        "units": "mm",
        "parts": {
            RING_NAME: {
                "valid": bool(ring.isValid()),
                "solids": len(ring.Solids),
                "volume_mm3": round(ring.Volume, 6),
                "mass_g_AL6061": round(ring.Volume * DENSITY_G_MM3, 6),
                "m4_centres_xy_mm": m4_centres,
                "m5_clearance_centres_xy_mm": [
                    [round(x, 6), round(y, 6)] for x, y in m5_centres],
                "m5_bearing_thickness_mm": 8.0,
                "annular_skirt_outer_diameter_mm": 2.0 * RING_OUTER_R,
                "annular_skirt_inner_diameter_mm": 2.0 * SKIRT_INNER_R,
                "annular_skirt_depth_mm": RECESSED_DEPTH,
                "clocking_dowel_clearance_diameter_mm": 4.1,
                "clocking_dowel_center_xy_mm": list(DOWEL_XY),
            },
            BODY_NAME: {
                "valid": bool(body.isValid()),
                "solids": len(body.Solids),
                "volume_mm3": round(body.Volume, 6),
                "mass_g_AL6061": round(body.Volume * DENSITY_G_MM3, 6),
                "m6_clearance_centres_xy_mm": m6_centres,
                "m8_geometry_present": False,
                "m5_clearance_centres_xy_mm": [
                    [round(x, 6), round(y, 6)] for x, y in m5_centres],
                "m5_fastener_style": "THROUGH_FASTENER_CANDIDATE",
                "remaining_thickness_below_pocket_mm": 6.405,
                "receiving_pocket_outer_diameter_mm": 2.0 * BODY_POCKET_OUTER_R,
                "receiving_pocket_inner_diameter_mm": 2.0 * BODY_BORE_R,
                "receiving_pocket_depth_mm": RECESSED_DEPTH,
                "clocking_dowel_blind_hole_diameter_mm": 4.0,
                "clocking_dowel_engagement_mm": 5.5,
                "clocking_dowel_center_xy_mm": list(DOWEL_XY),
                "m6_center_to_outer_edge_mm": 10.0,
                "m6_nominal_net_edge_margin_mm": 6.7,
            },
        },
        "assembly_contact": {
            "minimum_distance_mm": round(minimum_distance, 9),
            "common_volume_mm3": round(common_volume, 9),
            "classification": (
                "CONTACT_WITHOUT_PENETRATION"
                if minimum_distance <= 1e-7 and common_volume <= 1e-7
                else "ASSEMBLY_GEOMETRY_FAIL"
            ),
        },
        "outputs": [
            {"path": str(path).replace("\\", "/"),
             "bytes": path.stat().st_size,
             "sha256": sha256(path)}
            for path in outputs
        ],
        "non_claims": [
            "NOT_OEM_INTERFACE_ICD",
            "NOT_FLIGHT_QUALIFIED",
            "NOT_LAUNCH_QUALIFIED",
            "FORMAL_FASTENER_MOS_HOLD",
            "CLOCKING_DOWEL_FIT_TOLERANCE_HOLD",
            "M6_EDGE_MARGIN_ANALYSIS_HOLD",
        ],
    }
    report["verdict"] = (
        "M3R_FREECAD_ADAPTER_BUILD_PASS"
        if all(v["valid"] and v["solids"] == 1 for v in report["parts"].values())
        and report["assembly_contact"]["classification"]
        == "CONTACT_WITHOUT_PENETRATION"
        else "M3R_FREECAD_ADAPTER_BUILD_FAIL"
    )
    receipt = OUT.parent / "M3R_ADAPTER_FREECAD_BUILD_RECEIPT.json"
    receipt.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["verdict"].endswith("PASS") else 1


# FreeCADCmd executes a passed script with its stem as ``__name__`` rather
# than CPython's usual ``__main__``.  Execute unconditionally when loaded as a
# console script; importing this file from normal project code is not supported.
raise SystemExit(main())
