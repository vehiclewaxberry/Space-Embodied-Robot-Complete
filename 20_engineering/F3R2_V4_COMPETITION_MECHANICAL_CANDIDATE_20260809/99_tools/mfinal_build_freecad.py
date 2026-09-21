# -*- coding: utf-8 -*-
"""Build the additive F3R2 V4 competition mechanical candidate.

This script intentionally does not edit the frozen F3R1/F3R2 SolidWorks
baselines.  It emits neutral FreeCAD/STEP/STL candidate geometry and measured
receipts only.  Native SolidWorks parts, mates, configurations, drawings and
cold-reopen evidence remain a separate release gate.

All dimensions are millimetres and all masses are provisional engineering
estimates based on the material densities declared below.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import FreeCAD
import Mesh
import Part


ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
F3R2 = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
V4 = ROOT / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
CAD = V4 / "02_neutral_cad"
VALIDATION = V4 / "10_validation"
BOM_DIR = V4 / "09_bom"

DENSITY = {
    "AL6061-T6": 2.70e-3,
    "AL7075-T6": 2.81e-3,
    "PTFE-25GF": 2.20e-3,
    "PTFE-FILLED-BRONZE": 8.80e-3,
    "VMQ-60A": 1.25e-3,
    "VESPEL-SP1": 1.43e-3,
}

RECEIPT = VALIDATION / "MFINAL_FREECAD_BUILD_RECEIPT.json"
MANIFEST = VALIDATION / "MFINAL_NEUTRAL_CAD_MANIFEST_SHA256.txt"
BOM = BOM_DIR / "MFINAL_PROVISIONAL_BOM.csv"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def ensure_dirs() -> None:
    for path in (
        CAD / "adapter",
        CAD / "wing_root",
        CAD / "supports",
        CAD / "camera_harness",
        CAD / "gripper",
        VALIDATION,
        BOM_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def rounded_square(width: float, corner_r: float, z0: float, height: float):
    half = width / 2.0
    core_x = Part.makeBox(
        width - 2.0 * corner_r,
        width,
        height,
        FreeCAD.Vector(-half + corner_r, -half, z0),
    )
    core_y = Part.makeBox(
        width,
        width - 2.0 * corner_r,
        height,
        FreeCAD.Vector(-half, -half + corner_r, z0),
    )
    shape = core_x.fuse(core_y)
    for x in (-half + corner_r, half - corner_r):
        for y in (-half + corner_r, half - corner_r):
            shape = shape.fuse(
                Part.makeCylinder(corner_r, height, FreeCAD.Vector(x, y, z0))
            )
    return shape.removeSplitter()


def box_center(cx: float, cy: float, z0: float, sx: float, sy: float, sz: float):
    return Part.makeBox(
        sx, sy, sz, FreeCAD.Vector(cx - sx / 2.0, cy - sy / 2.0, z0)
    )


def cut_z(shape, radius: float, x: float, y: float, z0: float, height: float):
    return shape.cut(Part.makeCylinder(radius, height, FreeCAD.Vector(x, y, z0)))


def x_cylinder(radius: float, x0: float, length: float, y: float, z: float):
    return Part.makeCylinder(
        radius,
        length,
        FreeCAD.Vector(x0, y, z),
        FreeCAD.Vector(1.0, 0.0, 0.0),
    )


def annulus_x(outer_r: float, inner_r: float, x0: float, length: float):
    return x_cylinder(outer_r, x0, length, 0.0, 0.0).cut(
        x_cylinder(inner_r, x0 - 0.1, length + 0.2, 0.0, 0.0)
    )


def rect_wire(cx: float, cy: float, z: float, sx: float, sy: float):
    points = [
        FreeCAD.Vector(cx - sx / 2.0, cy - sy / 2.0, z),
        FreeCAD.Vector(cx + sx / 2.0, cy - sy / 2.0, z),
        FreeCAD.Vector(cx + sx / 2.0, cy + sy / 2.0, z),
        FreeCAD.Vector(cx - sx / 2.0, cy + sy / 2.0, z),
    ]
    points.append(points[0])
    return Part.makePolygon(points)


def hollow_prism(cx, cy, z0, height, sx, sy, wall):
    outer = box_center(cx, cy, z0, sx, sy, height)
    inner = box_center(
        cx, cy, z0 - 0.1, sx - 2.0 * wall, sy - 2.0 * wall, height + 0.2
    )
    return outer.cut(inner)


def hollow_loft(cx, cy, z0, z1, bottom_xy, top_xy, wall):
    outer = Part.makeLoft(
        [
            rect_wire(cx, cy, z0, bottom_xy[0], bottom_xy[1]),
            rect_wire(cx, cy, z1, top_xy[0], top_xy[1]),
        ],
        True,
    )
    inner = Part.makeLoft(
        [
            rect_wire(
                cx,
                cy,
                z0 - 0.1,
                bottom_xy[0] - 2.0 * wall,
                bottom_xy[1] - 2.0 * wall,
            ),
            rect_wire(
                cx,
                cy,
                z1 + 0.1,
                top_xy[0] - 2.0 * wall,
                top_xy[1] - 2.0 * wall,
            ),
        ],
        True,
    )
    return outer.cut(inner)


def add_properties(obj, part_number, description, material, scope, holds):
    for prop, value in (
        ("PartNumber", part_number),
        ("Description", description),
        ("MaterialSpecification", material),
        ("ReleaseScope", scope),
        ("QualificationHolds", ";".join(holds)),
    ):
        obj.addProperty("App::PropertyString", prop, "MFINAL")
        setattr(obj, prop, value)


def shape_record(name, shape, material, scope, holds):
    volume = float(shape.Volume)
    density = DENSITY.get(material)
    return {
        "part_number": name,
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "volume_mm3": round(volume, 6),
        "material": material,
        "mass_g": round(volume * density, 6) if density else None,
        "scope": scope,
        "holds": list(holds),
        "bounds_mm": [
            round(shape.BoundBox.XMin, 6),
            round(shape.BoundBox.YMin, 6),
            round(shape.BoundBox.ZMin, 6),
            round(shape.BoundBox.XMax, 6),
            round(shape.BoundBox.YMax, 6),
            round(shape.BoundBox.ZMax, 6),
        ],
    }


def save_shape(out_dir, name, shape, material, description, scope, holds):
    shape.check(True)
    doc = FreeCAD.newDocument(name)
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Label = name
    obj.Shape = shape
    add_properties(obj, name, description, material, scope, holds)
    doc.recompute()
    fcstd = out_dir / f"{name}.FCStd"
    step = out_dir / f"{name}.step"
    stl = out_dir / f"{name}.stl"
    doc.saveAs(str(fcstd))
    Part.export([obj], str(step))
    Mesh.export([obj], str(stl))
    FreeCAD.closeDocument(doc.Name)
    record = shape_record(name, shape, material, scope, holds)
    record["outputs"] = [fcstd, step, stl]
    return record


def save_assembly(out_dir, name, entries, scope, holds):
    doc = FreeCAD.newDocument(name)
    objects = []
    for entry in entries:
        obj = doc.addObject("PartDesign::Feature", entry["name"])
        obj.Label = entry["name"]
        obj.Shape = entry["shape"]
        add_properties(
            obj,
            entry["name"],
            entry["description"],
            entry["material"],
            scope,
            holds,
        )
        objects.append(obj)
    doc.recompute()
    fcstd = out_dir / f"{name}.FCStd"
    step = out_dir / f"{name}.step"
    doc.saveAs(str(fcstd))
    Part.export(objects, str(step))
    FreeCAD.closeDocument(doc.Name)
    return [fcstd, step]


def build_adapter():
    out = CAD / "adapter"
    scope = "COMPETITION_PROTOTYPE_MANUFACTURING_CANDIDATE"
    holds = [
        "LIVE_LOAD_BRIDGE_INTERFACE_HOLD",
        "FASTENER_PRELOAD_AND_MOS_HOLD",
        "PHYSICAL_FITUP_HOLD",
        "SOLIDWORKS_NATIVE_RELEASE_HOLD",
    ]

    proud = 2.405
    recess = 5.595
    ring_outer_r = 75.0
    spigot_r = 49.8
    skirt_inner_r = 50.3
    m5_r = 62.5
    dowel_xy = (55.0, 0.0)

    flange = Part.makeCylinder(ring_outer_r, proud, FreeCAD.Vector(0, 0, 0))
    spigot = Part.makeCylinder(spigot_r, recess, FreeCAD.Vector(0, 0, -recess))
    skirt = Part.makeCylinder(
        ring_outer_r, recess, FreeCAD.Vector(0, 0, -recess)
    ).cut(
        Part.makeCylinder(
            skirt_inner_r, recess, FreeCAD.Vector(0, 0, -recess)
        )
    )
    ring = flange.fuse(spigot).fuse(skirt).removeSplitter()
    ring = cut_z(ring, 20.0, 0.0, 0.0, -6.0, 9.0)
    m4_centres = [
        (15.4940, 42.4393),
        (-42.5096, 15.3917),
        (-15.4621, -42.6120),
        (42.5416, -15.5644),
    ]
    for x, y in m4_centres:
        ring = cut_z(ring, 2.30, x, y, -6.0, 9.0)
        ring = cut_z(ring, 3.75, x, y, -2.095, 4.75)
    m5_centres = []
    for index in range(8):
        angle = math.radians(22.5 + 45.0 * index)
        xy = (m5_r * math.cos(angle), m5_r * math.sin(angle))
        m5_centres.append(xy)
        ring = cut_z(ring, 2.75, xy[0], xy[1], -6.0, 9.0)
    ring = cut_z(ring, 2.05, dowel_xy[0], dowel_xy[1], -6.0, 9.0)
    ring = ring.removeSplitter()

    # Rev B2 retains the 160 mm square datum but adds four integral R15 local
    # ears around the M6 axes.  This changes the minimum radial centre-to-edge
    # distance from 10.0 to 15.0 mm and the net hole-edge ligament from 6.7 to
    # 11.7 mm, without changing the selected 140 x 140 pattern.
    body = rounded_square(160.0, 4.0, -12.0, 12.0)
    m6_centres = [(-70.0, -70.0), (70.0, -70.0), (-70.0, 70.0), (70.0, 70.0)]
    for x, y in m6_centres:
        body = body.fuse(Part.makeCylinder(15.0, 12.0, FreeCAD.Vector(x, y, -12.0)))
    body = body.removeSplitter()
    body = cut_z(body, 50.0, 0.0, 0.0, -13.0, 14.0)
    pocket = Part.makeCylinder(75.2, recess + 0.1, FreeCAD.Vector(0, 0, -recess)).cut(
        Part.makeCylinder(50.0, recess + 0.1, FreeCAD.Vector(0, 0, -recess))
    )
    body = body.cut(pocket)
    for x, y in m6_centres:
        body = cut_z(body, 3.30, x, y, -13.0, 14.0)
    for x, y in m5_centres:
        body = cut_z(body, 2.75, x, y, -13.0, 14.0)
    body = cut_z(body, 2.0, dowel_xy[0], dowel_xy[1], -recess - 5.5, 5.6)
    body = body.removeSplitter()

    ring_name = "V4_B601_STAGE_A_INTERFACE_RING_REVB"
    body_name = "V4_B601_STAGE_B_LOAD_ADAPTER_REVB2"
    ring_rec = save_shape(
        out,
        ring_name,
        ring,
        "AL6061-T6",
        "Four-M4 as-built B601 ring; eight-M5 transition and asymmetric dowel",
        scope,
        holds,
    )
    body_rec = save_shape(
        out,
        body_name,
        body,
        "AL6061-T6",
        "M6 140x140 Stage-B adapter with four R15 local edge-margin ears",
        scope,
        holds,
    )
    assembly_outputs = save_assembly(
        out,
        "V4_B601_TWO_STAGE_ADAPTER_REVB2",
        [
            {"name": body_name, "shape": body, "material": "AL6061-T6", "description": "Stage B"},
            {"name": ring_name, "shape": ring, "material": "AL6061-T6", "description": "Stage A"},
        ],
        scope,
        holds,
    )
    common = body.common(ring).Volume
    distance = body.distToShape(ring)[0]
    return {
        "package": "M-FINAL-01",
        "revision": "RevB2 competition candidate",
        "parts": [ring_rec, body_rec],
        "assembly_outputs": assembly_outputs,
        "m4_centres_xy_mm": m4_centres,
        "m5_centres_xy_mm": [[round(x, 6), round(y, 6)] for x, y in m5_centres],
        "m6_centres_xy_mm": m6_centres,
        "m6_center_to_local_outer_edge_mm": 15.0,
        "m6_net_hole_edge_ligament_mm": 11.7,
        "m6_previous_net_hole_edge_ligament_mm": 6.7,
        "assembly_contact": {
            "minimum_distance_mm": round(distance, 9),
            "common_volume_mm3": round(common, 9),
            "pass": distance <= 1e-7 and common <= 1e-7,
        },
    }


def build_clevis(side: str):
    sign = 1.0 if side == "LEFT" else -1.0
    axis_y = sign * 143.15
    edge_y = sign * 113.15
    y_min, y_max = sorted((axis_y, edge_y))
    plate_ranges = [(-80.5, -75.5), (-64.5, -57.5), (-46.5, -41.5)]
    pieces = []
    for x0, x1 in plate_ranges:
        plate = Part.makeBox(
            x1 - x0,
            y_max - y_min,
            18.0,
            FreeCAD.Vector(x0, y_min, -9.0),
        )
        boss = x_cylinder(9.0, x0, x1 - x0, axis_y, 0.0)
        pieces.append(plate.fuse(boss))
    rail_y0 = edge_y if sign > 0 else edge_y - 7.0
    rail = Part.makeBox(
        39.0,
        7.0,
        6.0,
        FreeCAD.Vector(-80.5, rail_y0, -3.0),
    )
    clevis = rail
    for piece in pieces:
        clevis = clevis.fuse(piece)
    bore = x_cylinder(4.2, -83.0, 44.0, axis_y, 0.0)
    clevis = clevis.cut(bore).removeSplitter()
    return clevis


def build_wing_root():
    out = CAD / "wing_root"
    scope = "COMPETITION_PROTOTYPE_GEOMETRY_CANDIDATE"
    holds = [
        "WING_PANEL_NATIVE_BOOLEAN_INTEGRATION_HOLD",
        "HINGE_LOAD_AND_FIT_TOLERANCE_HOLD",
        "NATIVE_MOTION_AND_INTERFERENCE_HOLD",
        "TRANSPORT_POSE_AUTHORITY_HOLD",
    ]
    records = []
    assembly_entries = []
    for side in ("LEFT", "RIGHT"):
        shape = build_clevis(side)
        name = f"V4_WING_ROOT_THREE_WEB_CLEVIS_{side}"
        rec = save_shape(
            out,
            name,
            shape,
            "AL6061-T6",
            "Three-web double-shear carrier around the two existing root ears",
            scope,
            holds,
        )
        records.append(rec)
        assembly_entries.append(
            {"name": name, "shape": shape, "material": "AL6061-T6", "description": "Wing root clevis"}
        )

    spacer = annulus_x(9.0, 4.3, 0.0, 0.5)
    spacer_rec = save_shape(
        out,
        "V4_HINGE_AXIAL_SPACER",
        spacer,
        "PTFE-FILLED-BRONZE",
        "D18/D8.6 x 0.5 hinge spacer seed",
        scope,
        holds,
    )
    grommet = annulus_x(6.5, 4.0, 0.0, 8.0)
    grommet_rec = save_shape(
        out,
        "V4_WING_HARNESS_GROMMET",
        grommet,
        "VMQ-60A",
        "D13/D8 x 8 harness grommet seed",
        scope,
        holds,
    )
    stop_pad = Part.makeBox(14.0, 8.0, 3.0)
    stop_rec = save_shape(
        out,
        "V4_WING_STOP_PAD",
        stop_pad,
        "AL6061-T6",
        "14 x 8 x 3 hard-stop pad seed; configuration placement pending",
        scope,
        holds,
    )
    records.extend([spacer_rec, grommet_rec, stop_rec])
    assembly_outputs = save_assembly(
        out,
        "V4_WING_ROOT_CANDIDATE_SET",
        assembly_entries,
        scope,
        holds,
    )
    return {
        "package": "M-FINAL-02",
        "parts": records,
        "assembly_outputs": assembly_outputs,
        "hinge_axis": "spacecraft X",
        "hinge_axis_y_mm": [143.15, -143.15],
        "hinge_axis_z_mm": 0.0,
        "pin_diameter_mm": 8.0,
        "lug_bore_diameter_mm": 8.4,
        "ear_side_clearance_mm": 0.5,
        "three_web_rationale": "one 7-mm centre web serves the adjacent faces of both 10-mm ears; two independent 21-mm forks would overlap by 3 mm",
    }


SUPPORTS = {
    "G07": {
        "name": "V4_G07_PRIMARY_SUPPORT",
        "center": (-10.0, 3.19),
        "head": (54.0, 54.0),
        "head_bottom": 240.5016,
        "head_top": 252.5016,
        "flare_bottom": 214.5016,
        "carrier_top": 258.5016,
        "carrier": (54.0, 54.0, 4.0),
        "pad": (50.0, 50.0, 3.0, "PTFE-25GF"),
        "pad_face": 261.5016,
        "preload_N": 50.0,
        "gap_mm": 0.0,
    },
    "G08": {
        "name": "V4_G08_PRIMARY_SUPPORT",
        "center": (170.0, 41.55),
        "head": (34.0, 34.0),
        "head_bottom": 194.4929,
        "head_top": 206.4929,
        "flare_bottom": 168.4929,
        "carrier_top": 206.4929,
        "carrier": (34.0, 34.0, 4.0),
        "pad": (30.0, 30.0, 2.0, "VMQ-60A"),
        "pad_face": 208.4929,
        "preload_N": 25.0,
        "gap_mm": 0.0,
    },
    "MID": {
        "name": "V4_MID_BACKUP_SUPPORT",
        "center": (90.0, 47.80),
        "head": (34.0, 34.41),
        "head_bottom": 197.9189,
        "head_top": 209.9189,
        "flare_bottom": 171.9189,
        "carrier_top": 209.9189,
        "carrier": (34.0, 34.41, 4.0),
        "pad": (30.0, 30.0, 3.0, "VESPEL-SP1"),
        "pad_face": 212.9189,
        "preload_N": 0.0,
        "gap_mm": 2.0,
    },
}


def build_support_body(spec):
    cx, cy = spec["center"]
    deck_z = 113.15
    foot_t = 6.0
    # A 2-mm machined wall plus a 4-mm continuous head skin is retained as the
    # first mass-conscious competition prototype; final gauge is load-case and
    # modal-test controlled.
    wall = 2.0
    foot = box_center(cx, cy, deck_z, 20.0, 60.0, foot_t)
    tube_z0 = deck_z + foot_t
    tube_h = spec["flare_bottom"] - tube_z0
    tube = hollow_prism(cx, cy, tube_z0, tube_h, 20.0, 60.0, wall)
    flare = hollow_loft(
        cx,
        cy,
        spec["flare_bottom"],
        spec["head_bottom"],
        (20.0, 60.0),
        spec["head"],
        wall,
    )
    # For G08/MID the removable 4-mm carrier completes the declared 12-mm
    # head stack.  G07 keeps its 12-mm head and carries a compressed spring
    # stack plus a separate carrier above it.
    body_head_top = spec["head_top"] if spec["preload_N"] == 50.0 else spec["head_top"] - 4.0
    head = box_center(
        cx,
        cy,
        spec["head_bottom"],
        spec["head"][0],
        spec["head"][1],
        body_head_top - spec["head_bottom"],
    )
    head_height = body_head_top - spec["head_bottom"]
    head_pocket_height = max(0.0, head_height - 4.0)
    if head_pocket_height > 0.0:
        head = head.cut(
            box_center(
                cx,
                cy,
                spec["head_bottom"] - 0.1,
                spec["head"][0] - 2.0 * wall,
                spec["head"][1] - 2.0 * wall,
                head_pocket_height + 0.1,
            )
        )
    body = foot.fuse(tube).fuse(flare).fuse(head).removeSplitter()
    # Candidate-only foot pattern; exact released native station coordinates
    # still require direct measurement from the existing tower foot.
    mount_centres = []
    for dx in (-5.0, 5.0):
        for dy in (-22.0, 22.0):
            mount_centres.append((cx + dx, cy + dy))
            body = cut_z(body, 1.7, cx + dx, cy + dy, deck_z - 0.5, foot_t + 1.0)
    pin_centres = [(cx, cy - 15.0), (cx, cy + 15.0)]
    for x, y in pin_centres:
        body = cut_z(body, 1.5, x, y, deck_z - 0.5, foot_t + 1.0)
    return body.removeSplitter(), mount_centres, pin_centres


def build_supports():
    out = CAD / "supports"
    scope = "COMPETITION_PROTOTYPE_GEOMETRY_CANDIDATE"
    holds = [
        "EXACT_NATIVE_FOOT_HOLE_COORDINATE_MEASUREMENT_HOLD",
        "PAD_PRELOAD_BENCH_CALIBRATION_HOLD",
        "NATIVE_STOW_CONTACT_AND_INTERFERENCE_HOLD",
        "STRUCTURAL_LOAD_CASE_HOLD",
    ]
    records = []
    assembly_entries = []
    station_results = []
    for tag, spec in SUPPORTS.items():
        body, mount_centres, pin_centres = build_support_body(spec)
        body_rec = save_shape(
            out,
            spec["name"],
            body,
            "AL7075-T6",
            f"{tag} flared hollow support body with replaceable carrier interface",
            scope,
            holds,
        )
        carrier_z0 = spec["carrier_top"] - spec["carrier"][2]
        carrier = box_center(
            spec["center"][0],
            spec["center"][1],
            carrier_z0,
            spec["carrier"][0],
            spec["carrier"][1],
            spec["carrier"][2],
        )
        carrier_rec = save_shape(
            out,
            f"V4_{tag}_PAD_CARRIER",
            carrier,
            "AL6061-T6",
            f"{tag} removable pad carrier",
            scope,
            holds,
        )
        pad_z0 = spec["pad_face"] - spec["pad"][2]
        pad = box_center(
            spec["center"][0],
            spec["center"][1],
            pad_z0,
            spec["pad"][0],
            spec["pad"][1],
            spec["pad"][2],
        )
        pad_rec = save_shape(
            out,
            f"V4_{tag}_CONTACT_PAD",
            pad,
            spec["pad"][3],
            f"{tag} replaceable contact pad",
            scope,
            holds,
        )
        records.extend([body_rec, carrier_rec, pad_rec])
        for name, shape, material, description in (
            (spec["name"], body, "AL7075-T6", f"{tag} support body"),
            (f"V4_{tag}_PAD_CARRIER", carrier, "AL6061-T6", f"{tag} carrier"),
            (f"V4_{tag}_CONTACT_PAD", pad, spec["pad"][3], f"{tag} pad"),
        ):
            assembly_entries.append(
                {"name": name, "shape": shape, "material": material, "description": description}
            )
        station_results.append(
            {
                "station": tag,
                "center_xy_mm": list(spec["center"]),
                "mount_hole_centres_xy_mm": mount_centres,
                "locating_pin_centres_xy_mm": pin_centres,
                "pad_face_z_mm": spec["pad_face"],
                "nominal_gap_mm": spec["gap_mm"],
                "preload_N": spec["preload_N"],
                "foot_pattern_status": "ENGINEERING_CANDIDATE_PENDING_NATIVE_MEASUREMENT",
            }
        )
    assembly_outputs = save_assembly(
        out,
        "V4_STOW_SUPPORTS_G07_G08_MID_SET",
        assembly_entries,
        scope,
        holds,
    )
    return {
        "package": "M-FINAL-03",
        "parts": records,
        "assembly_outputs": assembly_outputs,
        "stations": station_results,
    }


def bezier_point(poles, t):
    u = 1.0 - t
    return tuple(
        u ** 3 * poles[0][i]
        + 3.0 * u * u * t * poles[1][i]
        + 3.0 * u * t * t * poles[2][i]
        + t ** 3 * poles[3][i]
        for i in range(3)
    )


def bezier_min_radius(poles):
    minimum = float("inf")
    minimum_t = None
    for idx in range(1001):
        t = idx / 1000.0
        u = 1.0 - t
        d1 = [
            3.0 * u * u * (poles[1][i] - poles[0][i])
            + 6.0 * u * t * (poles[2][i] - poles[1][i])
            + 3.0 * t * t * (poles[3][i] - poles[2][i])
            for i in range(3)
        ]
        d2 = [
            6.0 * u * (poles[2][i] - 2.0 * poles[1][i] + poles[0][i])
            + 6.0 * t * (poles[3][i] - 2.0 * poles[2][i] + poles[1][i])
            for i in range(3)
        ]
        cross = (
            d1[1] * d2[2] - d1[2] * d2[1],
            d1[2] * d2[0] - d1[0] * d2[2],
            d1[0] * d2[1] - d1[1] * d2[0],
        )
        n1 = math.sqrt(sum(v * v for v in d1))
        nc = math.sqrt(sum(v * v for v in cross))
        if nc > 0.0:
            radius = n1 ** 3 / nc
            if radius < minimum:
                minimum = radius
                minimum_t = t
    return minimum, minimum_t


def capsule_path(points, radius):
    shape = None
    for index in range(len(points) - 1):
        p0 = FreeCAD.Vector(*points[index])
        p1 = FreeCAD.Vector(*points[index + 1])
        vector = p1.sub(p0)
        direction = FreeCAD.Vector(vector)
        direction.normalize()
        segment = Part.makeCylinder(radius, vector.Length, p0, direction)
        shape = segment if shape is None else shape.fuse(segment)
    for point in points:
        sphere = Part.makeSphere(radius, FreeCAD.Vector(*point))
        shape = shape.fuse(sphere)
    return shape.removeSplitter()


def build_camera_harness():
    out = CAD / "camera_harness"
    scope = "PACKAGING_AND_COLLISION_ENVELOPE_ONLY"
    holds = [
        "CAMERA_MODEL_SELECTION_HOLD",
        "CAMERA_OPTICAL_CALIBRATION_HOLD",
        "CONNECTOR_AND_CLAMP_GEOMETRY_HOLD",
        "MOVING_HARNESS_SWEEP_HOLD",
    ]
    camera = box_center(0.0, -46.0, 45.0, 40.0, 34.0, 26.0)
    camera_rec = save_shape(
        out,
        "V4_CAMERA_SELECTION_KEEP_OUT_LINK6",
        camera,
        "NON_PHYSICAL",
        "40 x 34 x 26 camera packaging envelope; optical frame is not calibrated",
        scope,
        holds,
    )
    poles = [(171.0, 0.0, -70.0), (180.0, 0.0, -50.0), (195.0, 0.0, -32.0), (215.0, 0.0, 0.0)]
    points = [bezier_point(poles, idx / 32.0) for idx in range(33)]
    harness = capsule_path(points, 4.5)
    route_rec = save_shape(
        out,
        "V4_HARNESS_STATIC_ROUTE_OD9_KEEP_OUT",
        harness,
        "NON_PHYSICAL",
        "Static cubic-Bezier OD9 harness sweep from passage exit to arm entry",
        scope,
        holds,
    )
    min_radius, at_t = bezier_min_radius(poles)
    return {
        "package": "M-FINAL-05",
        "parts": [camera_rec, route_rec],
        "camera_optical_offset_link6_mm": [0.0, -46.0, 58.0],
        "camera_keepout_bounds_relative_link6_mm": [-20.0, -63.0, 45.0, 20.0, -29.0, 71.0],
        "harness_control_points_xyz_mm": poles,
        "harness_bundle_od_mm": 9.0,
        "computed_minimum_curve_radius_mm": round(min_radius, 6),
        "minimum_curve_radius_at_t": at_t,
        "required_minimum_bend_radius_mm": 25.0,
        "bend_radius_pass": min_radius >= 25.0,
        "classification": "NON_PHYSICAL_COLLISION_ENVELOPES",
    }


def build_hdrm_skeleton():
    """Emit only the P4D/P5B-controlled functional skeleton and sweep keepout.

    The working release axis is -X.  +Z is retained only as the ground
    removal/unlock direction.  Missing installation clocking, selected
    electromagnet and mating restraint geometry prohibit a physical part.
    """
    out = CAD / "hdrm"
    out.mkdir(parents=True, exist_ok=True)
    scope = "COMPETITION_HDRM_FUNCTIONAL_SKELETON_ONLY"
    holds = [
        "ELECTROMAGNET_PRODUCT_SELECTION_HOLD",
        "FLANGE_CLOCKING_AND_DOWEL_COORDINATE_HOLD",
        "MATING_RESTRAINT_BREP_HOLD",
        "FORCE_CURRENT_THERMAL_AND_RELEASE_TEST_HOLD",
        "NATIVE_RELEASED_FAILED_CONFIGURATION_HOLD",
    ]
    # Conservative union of the F3R2 measured station envelope, a 6-mm -X
    # release stroke and a 5-mm packaging margin.
    sweep = Part.makeBox(36.0, 178.0, 46.0, FreeCAD.Vector(-21.0, -89.0, 127.0))
    sweep_rec = save_shape(
        out,
        "V4_ARM_HDRM_RELEASE_SWEEP_KEEP_OUT",
        sweep,
        "NON_PHYSICAL",
        "Conservative -X release sweep keepout; not released hardware",
        scope,
        holds,
    )
    flange = Part.makeBox(10.0, 60.0, 60.0, FreeCAD.Vector(-5.0, -30.0, 120.0))
    flange_rec = save_shape(
        out,
        "V4_ARM_HDRM_60MM_FLANGE_SKELETON",
        flange,
        "NON_PHYSICAL",
        "60 x 60 x 10 interface envelope at temporary C_REF=(0,0,150)",
        scope,
        holds,
    )
    return {
        "package": "M-FINAL-04",
        "parts": [sweep_rec, flange_rec],
        "controlling_authority": "P4D -> P5B/P5D competition demonstrator chain",
        "preload_direction": "+X",
        "working_release_direction": "-X",
        "ground_removal_unlock_direction": "+Z",
        "release_stroke_mm": 6.0,
        "working_preload_N": 50.0,
        "procurement_capability_min_N": 60.0,
        "release_time_requirement_s": 0.5,
        "temporary_reference_center_xyz_mm": [0.0, 0.0, 150.0],
        "conservative_keepout_bounds_mm": [-21.0, -89.0, 127.0, 15.0, 89.0, 173.0],
        "physical_model_status": "HOLD_SKELETON_ONLY",
    }


def build_gripper_mesh_groups():
    out = CAD / "gripper"
    assignment = F3R2 / "08_camera_harness/F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"
    mesh_root = F3R2 / "05_clearance/mesh/gripper_solids_DEPLOYED"
    groups = {"gripper_link": [], "gripper_left": [], "gripper_right": []}
    volumes = {key: 0.0 for key in groups}
    with assignment.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            label = row["solid"]
            group = row["assigned_body"]
            if group not in groups:
                raise ValueError(f"unexpected gripper group: {group}")
            source = mesh_root / f"{label}.stl"
            if not source.is_file():
                raise FileNotFoundError(source)
            groups[group].append(source)
            volumes[group] += float(row["volume_mm3"])

    outputs = []
    group_records = []
    for group, sources in groups.items():
        name = f"V4_{group.upper()}_MESH_COMPONENT"
        doc = FreeCAD.newDocument(name)
        objects = []
        for source in sources:
            obj = doc.addObject("Mesh::Feature", source.stem)
            obj.Label = source.stem
            obj.Mesh = Mesh.Mesh(str(source))
            obj.addProperty("App::PropertyString", "AssignedComponent", "MFINAL")
            obj.AssignedComponent = group
            objects.append(obj)
        doc.recompute()
        fcstd = out / f"{name}.FCStd"
        stl = out / f"{name}.stl"
        doc.saveAs(str(fcstd))
        Mesh.export(objects, str(stl))
        FreeCAD.closeDocument(doc.Name)
        outputs.extend([fcstd, stl])
        group_records.append(
            {
                "component": group,
                "source_solids": len(sources),
                "source_volume_mm3": round(volumes[group], 6),
                "fcstd": fcstd,
                "stl": stl,
                "native_solid_status": "MESH_GROUP_ONLY_SOLIDWORKS_SAVE_BODIES_HOLD",
            }
        )
    return {
        "package": "M-FINAL-06",
        "groups": group_records,
        "outputs": outputs,
        "counts": {key: len(value) for key, value in groups.items()},
        "count_total": sum(len(value) for value in groups.values()),
        "volume_total_mm3": round(sum(volumes.values()), 6),
        "native_gate": "HOLD_SEPARATE_SLDPRT_SLDASM_PRISMATIC_MATES_REQUIRED",
    }


def serialise_paths(value):
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    if isinstance(value, dict):
        return {key: serialise_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialise_paths(item) for item in value]
    return value


def all_output_paths(packages):
    paths = []
    for package in packages:
        for part in package.get("parts", []):
            paths.extend(part.get("outputs", []))
        paths.extend(package.get("assembly_outputs", []))
        paths.extend(package.get("outputs", []))
        for group in package.get("groups", []):
            paths.extend([group["fcstd"], group["stl"]])
    unique = []
    seen = set()
    for path in paths:
        resolved = Path(path)
        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            unique.append(resolved)
    return unique


def write_bom(packages):
    rows = []
    for package in packages:
        for part in package.get("parts", []):
            rows.append(
                {
                    "work_package": package["package"],
                    "part_number": part["part_number"],
                    "quantity": 1,
                    "material": part["material"],
                    "volume_mm3": part["volume_mm3"],
                    "provisional_mass_g": "" if part["mass_g"] is None else part["mass_g"],
                    "release_scope": part["scope"],
                    "status": "NEUTRAL_GEOMETRY_BUILT",
                    "holds": ";".join(part["holds"]),
                }
            )
    for group in next(p for p in packages if p["package"] == "M-FINAL-06")["groups"]:
        rows.append(
            {
                "work_package": "M-FINAL-06",
                "part_number": f"V4_{group['component'].upper()}_MESH_COMPONENT",
                "quantity": 1,
                "material": "SOURCE_DONOR_MULTI_MATERIAL_UNKNOWN",
                "volume_mm3": group["source_volume_mm3"],
                "provisional_mass_g": "",
                "release_scope": "MESH_COMPONENT_BINDING_ONLY",
                "status": group["native_solid_status"],
                "holds": "MATERIAL_MASS_AND_NATIVE_PART_HOLD",
            }
        )
    fields = [
        "work_package",
        "part_number",
        "quantity",
        "material",
        "volume_mm3",
        "provisional_mass_g",
        "release_scope",
        "status",
        "holds",
    ]
    with BOM.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="replace only outputs owned by this builder")
    # FreeCADCmd keeps the script path in sys.argv.  Ignore that launcher
    # argument while still honoring this script's explicit --force flag.
    args, _launcher_args = parser.parse_known_args()
    if RECEIPT.exists() and not args.force:
        raise SystemExit(f"controlled output already exists: {RECEIPT}; use --force for an intentional rebuild")
    ensure_dirs()

    packages = [
        build_adapter(),
        build_wing_root(),
        build_supports(),
        build_hdrm_skeleton(),
        build_camera_harness(),
        build_gripper_mesh_groups(),
    ]
    bom_rows = write_bom(packages)
    outputs = all_output_paths(packages)
    outputs.append(BOM)
    missing = [str(path) for path in outputs if not path.is_file()]
    manifest_rows = []
    for path in sorted(outputs, key=lambda item: str(item).lower()):
        if path.is_file():
            manifest_rows.append(
                {
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                    "path": path.relative_to(V4).as_posix(),
                }
            )
    with MANIFEST.open("w", encoding="utf-8", newline="\n") as stream:
        for row in manifest_rows:
            stream.write(f"{row['sha256']}  {row['bytes']}  {row['path']}\n")

    physical_parts = [
        part
        for package in packages
        for part in package.get("parts", [])
        if part["material"] != "NON_PHYSICAL"
    ]
    invalid = [
        part["part_number"]
        for part in physical_parts
        if not part["valid"] or part["solids"] != 1
    ]
    provisional_mass = sum(part["mass_g"] or 0.0 for part in physical_parts)
    receipt = {
        "schema": "MFINAL_FREECAD_BUILD_RECEIPT_V1",
        "baseline": "F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809",
        "builder": "FreeCAD 1.1.3 / OpenCascade",
        "units": "mm; g",
        "source_f3r2": str(F3R2).replace("\\", "/"),
        "protected_baselines_modified": False,
        "packages": serialise_paths(packages),
        "bom_rows": len(bom_rows),
        "neutral_output_files": len(manifest_rows),
        "provisional_known_material_mass_g": round(provisional_mass, 6),
        "missing_outputs": missing,
        "invalid_single_solid_parts": invalid,
        "explicit_holds": [
            "ARM HDRM functional axis is resolved to -X, but product, clocking, mating geometry and test remain HOLD",
            "camera model and optical calibration not selected",
            "SolidWorks native parts/mates/configurations/drawings/cold reopen not run",
            "five service/manipulation poses require human authorization",
            "load cases, fastener preload, structural MoS and physical fit-up not closed",
            "flight/launch/vibration/thermal-vacuum qualification not claimed",
        ],
        "verdict": (
            "MFINAL_NEUTRAL_MECHANICAL_CANDIDATE_BUILD_PASS_WITH_NATIVE_AND_AUTHORITY_HOLDS"
            if not missing and not invalid and packages[0]["assembly_contact"]["pass"]
            and next(p for p in packages if p["package"] == "M-FINAL-05")["bend_radius_pass"]
            and next(p for p in packages if p["package"] == "M-FINAL-06")["count_total"] == 58
            else "MFINAL_NEUTRAL_MECHANICAL_CANDIDATE_BUILD_FAIL"
        ),
    }
    RECEIPT.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "verdict": receipt["verdict"],
        "neutral_output_files": receipt["neutral_output_files"],
        "bom_rows": receipt["bom_rows"],
        "provisional_known_material_mass_g": receipt["provisional_known_material_mass_g"],
        "receipt": str(RECEIPT),
    }, ensure_ascii=False, indent=2))
    return 0 if receipt["verdict"].endswith("HOLDS") else 1


raise SystemExit(main())
