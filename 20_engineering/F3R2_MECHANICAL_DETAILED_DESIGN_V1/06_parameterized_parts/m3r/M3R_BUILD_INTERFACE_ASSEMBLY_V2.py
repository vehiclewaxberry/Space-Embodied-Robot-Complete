# -*- coding: utf-8 -*-
"""Rebuild the M3R two-stage Rev-B2 working interface from pinned parameters.

Run with FreeCADCmd.  This is a detailed-design working model generator, not a
manufacturing or flight release.  It performs no FEA and consumes no loads.
All geometry inputs are millimetres and are read from M3R_PARAMETER_DRIVER_V2.json.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import FreeCAD
import Part


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DRIVER = HERE / "M3R_PARAMETER_DRIVER_V2.json"
RECEIPT = HERE / "M3R_INTERFACE_ASSEMBLY_V2_BUILD_RECEIPT.json"
STAGE_A_FCSTD = HERE / "M3R_STAGE_A_REVB_WORKING.FCStd"
STAGE_A_STEP = HERE / "M3R_STAGE_A_REVB_WORKING.step"
STAGE_B_FCSTD = HERE / "M3R_STAGE_B_REVB2_WORKING.FCStd"
STAGE_B_STEP = HERE / "M3R_STAGE_B_REVB2_WORKING.step"
ASSEMBLY_FCSTD = HERE / "M3R_INTERFACE_ASSEMBLY_V2_WORKING.FCStd"
ASSEMBLY_STEP = HERE / "M3R_INTERFACE_ASSEMBLY_V2_WORKING.step"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def pin_sources(driver: dict) -> list[dict]:
    checked = []
    for pin in driver["source_hash_pins"]:
        path = ROOT / Path(pin["path"])
        if not path.is_file():
            raise RuntimeError(f"pinned source missing: {path}")
        actual = sha256(path)
        if actual != pin["sha256"]:
            raise RuntimeError(
                f"pinned source drift: {path}; expected {pin['sha256']}; actual {actual}"
            )
        checked.append({"path": pin["path"], "sha256": actual, "result": "MATCH"})
    return checked


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


def cut_z(shape, diameter: float, x: float, y: float, z0: float, height: float):
    return shape.cut(
        Part.makeCylinder(diameter / 2.0, height, FreeCAD.Vector(x, y, z0))
    )


def polar_pattern(radius: float, start_angle_deg: float, count: int) -> list[list[float]]:
    pitch = 360.0 / count
    return [
        [
            radius * math.cos(math.radians(start_angle_deg + pitch * index)),
            radius * math.sin(math.radians(start_angle_deg + pitch * index)),
        ]
        for index in range(count)
    ]


def build_stage_a(p: dict):
    proud = p["proud_thickness_mm"]
    recess = p["recess_depth_mm"]
    outer_r = p["outer_diameter_mm"] / 2.0
    spigot_r = p["spigot_diameter_mm"] / 2.0
    skirt_inner_r = p["annular_skirt_inner_diameter_mm"] / 2.0

    flange = Part.makeCylinder(outer_r, proud, FreeCAD.Vector(0.0, 0.0, 0.0))
    spigot = Part.makeCylinder(spigot_r, recess, FreeCAD.Vector(0.0, 0.0, -recess))
    skirt = Part.makeCylinder(
        outer_r, recess, FreeCAD.Vector(0.0, 0.0, -recess)
    ).cut(
        Part.makeCylinder(
            skirt_inner_r, recess, FreeCAD.Vector(0.0, 0.0, -recess)
        )
    )
    shape = flange.fuse(spigot).fuse(skirt).removeSplitter()
    shape = cut_z(
        shape,
        p["central_passage_diameter_mm"],
        0.0,
        0.0,
        -recess - 0.405,
        proud + recess + 1.0,
    )
    counterbore_bottom = proud - p["m4_counterbore_depth_from_top_mm"]
    for x, y in p["m4_centres_xy_mm"]:
        shape = cut_z(
            shape,
            p["m4_hole_diameter_mm"],
            x,
            y,
            -recess - 0.405,
            proud + recess + 1.0,
        )
        shape = cut_z(
            shape,
            p["m4_counterbore_diameter_mm"],
            x,
            y,
            counterbore_bottom,
            p["m4_counterbore_depth_from_top_mm"] + 0.25,
        )
    m5_centres = polar_pattern(
        p["m5_pattern_radius_mm"], p["m5_start_angle_deg"], p["m5_count"]
    )
    for x, y in m5_centres:
        shape = cut_z(
            shape,
            p["m5_hole_diameter_mm"],
            x,
            y,
            -recess - 0.405,
            proud + recess + 1.0,
        )
    shape = cut_z(
        shape,
        p["clocking_dowel_hole_diameter_mm"],
        p["clocking_dowel_center_xy_mm"][0],
        p["clocking_dowel_center_xy_mm"][1],
        -recess - 0.405,
        proud + recess + 1.0,
    )
    return shape.removeSplitter(), m5_centres


def build_stage_b(p: dict, m5_centres: list[list[float]]):
    thickness = p["base_thickness_mm"]
    shape = rounded_square(
        p["base_square_width_mm"], p["base_corner_radius_mm"], -thickness, thickness
    )
    for x, y in p["m6_centres_xy_mm"]:
        shape = shape.fuse(
            Part.makeCylinder(
                p["m6_local_ear_radius_mm"],
                thickness,
                FreeCAD.Vector(x, y, -thickness),
            )
        )
    shape = shape.removeSplitter()
    shape = cut_z(
        shape,
        p["central_bore_diameter_mm"],
        0.0,
        0.0,
        -thickness - 1.0,
        thickness + 2.0,
    )
    depth = p["receiving_pocket_depth_mm"]
    pocket = Part.makeCylinder(
        p["receiving_pocket_outer_diameter_mm"] / 2.0,
        depth + 0.1,
        FreeCAD.Vector(0.0, 0.0, -depth),
    ).cut(
        Part.makeCylinder(
            p["receiving_pocket_inner_diameter_mm"] / 2.0,
            depth + 0.1,
            FreeCAD.Vector(0.0, 0.0, -depth),
        )
    )
    shape = shape.cut(pocket)
    for x, y in p["m6_centres_xy_mm"]:
        shape = cut_z(
            shape,
            p["m6_hole_diameter_mm"],
            x,
            y,
            -thickness - 1.0,
            thickness + 2.0,
        )
    for x, y in m5_centres:
        shape = cut_z(
            shape,
            p["m5_hole_diameter_mm"],
            x,
            y,
            -thickness - 1.0,
            thickness + 2.0,
        )
    shape = cut_z(
        shape,
        p["clocking_dowel_hole_diameter_mm"],
        p["clocking_dowel_center_xy_mm"][0],
        p["clocking_dowel_center_xy_mm"][1],
        -depth - p["clocking_dowel_blind_depth_mm"],
        p["clocking_dowel_blind_depth_mm"] + 0.1,
    )
    return shape.removeSplitter()


def bounds(shape) -> list[float]:
    box = shape.BoundBox
    return [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]


def add_metadata(obj, part_number: str, driver_sha: str, source_sha: str) -> None:
    group = "M3R_Traceability"
    obj.addProperty("App::PropertyString", "PartNumber", group)
    obj.PartNumber = part_number
    obj.addProperty("App::PropertyString", "LifecycleStatus", group)
    obj.LifecycleStatus = "WORKING_DETAILED_DESIGN_NOT_RELEASED"
    obj.addProperty("App::PropertyString", "ParameterDriverSha256", group)
    obj.ParameterDriverSha256 = driver_sha
    obj.addProperty("App::PropertyString", "SourceGeometrySha256", group)
    obj.SourceGeometrySha256 = source_sha
    obj.addProperty("App::PropertyString", "MaterialStatus", group)
    obj.MaterialStatus = "AL6061-T6_CANDIDATE_NOT_APPROVED"
    obj.addProperty("App::PropertyStringList", "Holds", group)
    obj.Holds = [
        "AUTHORIZED_LOADS_HOLD",
        "FASTENER_PRELOAD_AND_MOS_HOLD",
        "ALL_MANUFACTURING_TOLERANCES_HOLD",
        "PHYSICAL_FITUP_HOLD",
        "MANUFACTURING_RELEASE_HOLD",
    ]


def save_part(path_fcstd: Path, path_step: Path, name: str, shape, driver_sha: str, source_sha: str):
    doc = FreeCAD.newDocument(name)
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Label = name
    obj.Shape = shape
    add_metadata(obj, name, driver_sha, source_sha)
    doc.recompute()
    # Save to a fresh staging name, then replace the controlled working file.
    # This keeps FreeCAD from depositing uncontrolled .FCBak files on rebuild.
    staged_fcstd = path_fcstd.with_name(path_fcstd.stem + ".new.FCStd")
    if staged_fcstd.exists():
        staged_fcstd.unlink()
    doc.saveAs(str(staged_fcstd))
    Part.export([obj], str(path_step))
    FreeCAD.closeDocument(doc.Name)
    staged_fcstd.replace(path_fcstd)


def save_assembly(stage_a, stage_b, driver: dict, driver_sha: str):
    name = "M3R_INTERFACE_ASSEMBLY_V2_WORKING"
    doc = FreeCAD.newDocument(name)
    config = doc.addObject("App::FeaturePython", "M3R_PARAMETER_AUTHORITY")
    config.addProperty("App::PropertyString", "LifecycleStatus", "M3R_Traceability")
    config.LifecycleStatus = driver["lifecycle_status"]
    config.addProperty("App::PropertyString", "ParameterDriver", "M3R_Traceability")
    config.ParameterDriver = DRIVER.name
    config.addProperty("App::PropertyString", "ParameterDriverSha256", "M3R_Traceability")
    config.ParameterDriverSha256 = driver_sha
    config.addProperty("App::PropertyString", "ActiveMassAuthority", "M3R_Traceability")
    config.ActiveMassAuthority = "761.9 g BUDGETED; NOT_MEASURED; NOT_INSTALLED"
    config.addProperty("App::PropertyStringList", "ExplicitNonClaims", "M3R_Traceability")
    config.ExplicitNonClaims = driver["non_claims"]

    entries = [
        (
            "M3R_STAGE_B_LOAD_ADAPTER_REVB2_WORKING",
            stage_b,
            driver["source_hash_pins"][3]["sha256"],
        ),
        (
            "M3R_STAGE_A_INTERFACE_RING_REVB_WORKING",
            stage_a,
            driver["source_hash_pins"][2]["sha256"],
        ),
    ]
    objects = []
    for part_number, shape, source_sha in entries:
        obj = doc.addObject("PartDesign::Feature", part_number)
        obj.Label = part_number
        obj.Shape = shape
        add_metadata(obj, part_number, driver_sha, source_sha)
        objects.append(obj)
    doc.recompute()
    staged_fcstd = ASSEMBLY_FCSTD.with_name(ASSEMBLY_FCSTD.stem + ".new.FCStd")
    if staged_fcstd.exists():
        staged_fcstd.unlink()
    doc.saveAs(str(staged_fcstd))
    Part.export(objects, str(ASSEMBLY_STEP))
    FreeCAD.closeDocument(doc.Name)
    staged_fcstd.replace(ASSEMBLY_FCSTD)


def assert_close(name: str, actual: float, expected: float, tolerance: float) -> None:
    if abs(actual - expected) > tolerance:
        raise RuntimeError(
            f"geometry regression {name}: expected {expected}, actual {actual}, tolerance {tolerance}"
        )


def output_record(path: Path) -> dict:
    item = path.stat()
    return {"path": path.name, "size_bytes": item.st_size, "sha256": sha256(path)}


def main() -> None:
    driver = json.loads(DRIVER.read_text(encoding="utf-8"))
    checked_sources = pin_sources(driver)
    driver_sha = sha256(DRIVER)
    stage_a, m5_centres = build_stage_a(driver["stage_A"])
    stage_b = build_stage_b(driver["stage_B"], m5_centres)
    if not stage_a.isValid() or not stage_b.isValid():
        raise RuntimeError("invalid output B-rep")

    expected = driver["expected_geometry"]
    assert_close("stage_A_volume_mm3", stage_a.Volume, expected["stage_A_volume_mm3"], 1.0e-6)
    assert_close("stage_B_volume_mm3", stage_b.Volume, expected["stage_B_volume_mm3"], 1.0e-6)
    distance = stage_a.distToShape(stage_b)[0]
    common = stage_a.common(stage_b).Volume
    assert_close(
        "stage_A_stage_B_minimum_distance_mm",
        distance,
        expected["stage_A_stage_B_minimum_distance_mm"],
        1.0e-7,
    )
    assert_close(
        "stage_A_stage_B_common_volume_mm3",
        common,
        expected["stage_A_stage_B_common_volume_mm3"],
        1.0e-7,
    )

    save_part(
        STAGE_A_FCSTD,
        STAGE_A_STEP,
        driver["stage_A"]["part_number"],
        stage_a,
        driver_sha,
        driver["source_hash_pins"][2]["sha256"],
    )
    save_part(
        STAGE_B_FCSTD,
        STAGE_B_STEP,
        driver["stage_B"]["part_number"],
        stage_b,
        driver_sha,
        driver["source_hash_pins"][3]["sha256"],
    )
    save_assembly(stage_a, stage_b, driver, driver_sha)

    # Cold reopen the generated native working documents.  This is a geometry
    # integrity check only and is not manufacturing-release evidence.
    cold_reopen = []
    for path in (STAGE_A_FCSTD, STAGE_B_FCSTD, ASSEMBLY_FCSTD):
        doc = FreeCAD.openDocument(str(path))
        shape_objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
        cold_reopen.append(
            {
                "path": path.name,
                "shape_objects": len(shape_objects),
                "all_shapes_valid": all(obj.Shape.isValid() for obj in shape_objects),
            }
        )
        FreeCAD.closeDocument(doc.Name)

    density = driver["material_candidate"]["density_g_per_mm3"]
    receipt = {
        "schema": "M3R_INTERFACE_ASSEMBLY_V2_BUILD_RECEIPT_V1",
        "builder": "FreeCADCmd / OpenCascade",
        "lifecycle_status": driver["lifecycle_status"],
        "parameter_driver": DRIVER.name,
        "parameter_driver_sha256": driver_sha,
        "source_pin_checks": checked_sources,
        "geometry": {
            "stage_A": {
                "valid": stage_a.isValid(),
                "solid_count": len(stage_a.Solids),
                "volume_mm3": round(stage_a.Volume, 6),
                "bounds_mm": [round(value, 6) for value in bounds(stage_a)],
                "material_derived_mass_g_inactive_comparison": round(stage_a.Volume * density, 6),
            },
            "stage_B": {
                "valid": stage_b.isValid(),
                "solid_count": len(stage_b.Solids),
                "volume_mm3": round(stage_b.Volume, 6),
                "bounds_mm": [round(value, 6) for value in bounds(stage_b)],
                "material_derived_mass_g_inactive_comparison": round(stage_b.Volume * density, 6),
            },
            "assembly_contact": {
                "minimum_distance_mm": round(distance, 9),
                "common_volume_mm3": round(common, 9),
                "classification": "CONTACT_WITHOUT_PENETRATION",
            },
            "m5_axis_sets_common_by_construction": True,
            "m5_centres_xy_mm": [[round(x, 6), round(y, 6)] for x, y in m5_centres],
            "m6_net_hole_edge_ligament_mm": expected["m6_net_hole_edge_ligament_mm"],
        },
        "mass_authority": {
            "active_assembly_budget_g": driver["active_mass_authority"]["assembly_budget_g"],
            "classification": "BUDGETED",
            "measured": False,
            "installed": False,
            "stage_allocation_g": None,
            "material_derived_total_g_inactive_comparison": round(
                (stage_a.Volume + stage_b.Volume) * density, 6
            ),
        },
        "cold_reopen": cold_reopen,
        "outputs": [
            output_record(path)
            for path in (
                STAGE_A_FCSTD,
                STAGE_A_STEP,
                STAGE_B_FCSTD,
                STAGE_B_STEP,
                ASSEMBLY_FCSTD,
                ASSEMBLY_STEP,
            )
        ],
        "formal_fea_performed": False,
        "explicit_holds": [
            "AUTHORIZED_LOADS_HOLD",
            "FASTENER_PRELOAD_AND_MOS_HOLD",
            "ALL_MANUFACTURING_TOLERANCES_HOLD",
            "PHYSICAL_FITUP_HOLD",
            "M6_LIVE_MATING_LOAD_BRIDGE_GEOMETRY_HOLD",
            "MANUFACTURING_RELEASE_HOLD",
            "FLIGHT_AND_LAUNCH_QUALIFICATION_HOLD",
        ],
        "verdict": "WORKING_PARAMETERIZED_GEOMETRY_BUILD_PASS_WITH_RELEASE_HOLDS",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# FreeCADCmd uses the script stem instead of ``__main__`` in some builds.
main()
