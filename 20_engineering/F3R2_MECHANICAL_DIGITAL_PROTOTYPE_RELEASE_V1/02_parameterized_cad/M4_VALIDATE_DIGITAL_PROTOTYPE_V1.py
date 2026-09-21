# -*- coding: utf-8 -*-
"""Independent cold-reopen and traceability validator for the M4 prototype.

Run with FreeCADCmd after the builder.  The validator does not edit the master
FCStd or STEP and does not perform FEA.
"""

from __future__ import annotations

import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App
import Part


HERE = Path(__file__).resolve().parent
M4_ROOT = HERE.parent
PROJECT_ROOT = M4_ROOT.parents[1]

FCSTD = HERE / "SEI_DIGITAL_PROTOTYPE_V1.FCStd"
STEP = HERE / "SEI_DIGITAL_PROTOTYPE_V1.step"
RECEIPT = HERE / "DIGITAL_PROTOTYPE_BUILD_RECEIPT_V1.json"
AUDIT = HERE / "DIGITAL_PROTOTYPE_GEOMETRY_AUDIT_V1.json"
PINS = HERE / "DIGITAL_PROTOTYPE_SOURCE_HASH_PINS_V1.json"
OUTPUT = HERE / "DIGITAL_PROTOTYPE_INDEPENDENT_VALIDATION_V1.json"

FRAME_TREE = M4_ROOT / "01_system_architecture" / "DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml"
ARCHITECTURE = M4_ROOT / "01_system_architecture" / "DIGITAL_PROTOTYPE_ASSEMBLY_ARCHITECTURE_V1.yaml"
COMPONENT_REGISTER = M4_ROOT / "01_system_architecture" / "DIGITAL_PROTOTYPE_COMPONENT_REGISTER_V1.csv"
COLLISION_REGISTER = HERE / "DIGITAL_PROTOTYPE_COLLISION_ASSET_REGISTER_V1.yaml"
DRAWING_INDEX = M4_ROOT / "09_drawings" / "DIGITAL_PROTOTYPE_DRAWING_INDEX_V1.csv"
DRAWING_SVG = M4_ROOT / "09_drawings" / "D01_DIGITAL_PROTOTYPE_INTERFACE_LAYOUT_DRAFT.svg"
BOM = M4_ROOT / "10_BOM" / "DIGITAL_PROTOTYPE_BOM_V1.csv"
BOM_SCOPE = M4_ROOT / "10_BOM" / "BOM_SCOPE_AND_NONCLAIMS.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def shape_metrics(shape) -> dict:
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "faces": len(shape.Faces),
        "volume_mm3": round(float(shape.Volume), 9),
        "bounding_box_mm": [
            round(box.XMin, 9),
            round(box.YMin, 9),
            round(box.ZMin, 9),
            round(box.XMax, 9),
            round(box.YMax, 9),
            round(box.ZMax, 9),
        ],
    }


def read_csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return next(csv.reader(stream))


def main() -> None:
    required = [
        FCSTD,
        STEP,
        RECEIPT,
        AUDIT,
        PINS,
        FRAME_TREE,
        ARCHITECTURE,
        COMPONENT_REGISTER,
        COLLISION_REGISTER,
        DRAWING_INDEX,
        DRAWING_SVG,
        BOM,
        BOM_SCOPE,
    ]
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    pins = json.loads(PINS.read_text(encoding="utf-8"))

    expected_output_hashes = {
        record["path"]: record["sha256"] for record in receipt["outputs"]
    }
    observed_output_hashes = {
        path.relative_to(M4_ROOT).as_posix(): sha256(path)
        for path in (FCSTD, STEP, PINS, AUDIT)
    }

    doc = App.openDocument(str(FCSTD))
    try:
        links = [obj for obj in doc.Objects if obj.TypeId == "App::Link"]
        installed = [obj.Name for obj in links if obj.Name.startswith("INST_")]
        source_shapes = [
            obj
            for obj in doc.Objects
            if obj.Name.startswith("SRC_")
            and hasattr(obj, "Shape")
            and not obj.Shape.isNull()
        ]
        slots = sorted(obj.Name for obj in doc.Objects if obj.Name.startswith("SLOT_"))
        export_obj = doc.getObject("STEP_EXPORT_AGGREGATE")
        fcstd_metrics = {
            "object_count": len(doc.Objects),
            "app_part_count": sum(obj.TypeId == "App::Part" for obj in doc.Objects),
            "app_link_count": len(links),
            "installed_link_names": installed,
            "slot_names": slots,
            "all_links_internal": all(
                obj.LinkedObject is not None and obj.LinkedObject.Document is doc
                for obj in links
            ),
            "all_source_shapes_valid": all(obj.Shape.isValid() for obj in source_shapes),
            "source_shape_count": len(source_shapes),
            "export_composition": getattr(export_obj, "Composition", None),
        }
    finally:
        App.closeDocument(doc.Name)

    step_doc = App.newDocument("M4_INDEPENDENT_STEP_REOPEN")
    try:
        Part.insert(str(STEP), step_doc.Name)
        step_doc.recompute()
        step_shapes = [
            obj.Shape
            for obj in step_doc.Objects
            if hasattr(obj, "Shape")
            and not obj.Shape.isNull()
            and len(obj.Shape.Solids) > 0
        ]
        step_metrics = shape_metrics(Part.makeCompound(step_shapes))
        step_metrics["object_count"] = len(step_doc.Objects)
        step_metrics["shape_object_count"] = len(step_shapes)
    finally:
        App.closeDocument(step_doc.Name)

    source_pin_results = []
    for record in pins["records"]:
        source_path = PROJECT_ROOT / Path(record["path"])
        exists = source_path.is_file()
        observed_hash = sha256(source_path) if exists else None
        source_pin_results.append(
            {
                "path": record["path"],
                "exists": exists,
                "expected_sha256": record["sha256"],
                "observed_sha256": observed_hash,
                "match": exists and observed_hash == record["sha256"],
            }
        )

    frame_text = FRAME_TREE.read_text(encoding="utf-8")
    architecture_text = ARCHITECTURE.read_text(encoding="utf-8")
    collision_text = COLLISION_REGISTER.read_text(encoding="utf-8")
    ET.parse(DRAWING_SVG)

    expected_installed = sorted(
        [
            "INST_BUS_12U_CORE",
            "INST_SOLAR_ARRAY_LEFT_DEPLOYED",
            "INST_SOLAR_ARRAY_RIGHT_DEPLOYED",
            "INST_B601_ARM_CORE_Q0",
            "INST_M3R_INTERFACE_ASSEMBLY",
            "INST_GRIPPER_R1_PALM",
        ]
    )
    expected_slots = sorted(
        [
            "SLOT_SPACECRAFT_LOAD_BRIDGE__UNRESOLVED",
            "SLOT_SENSOR_PACKAGE__UNRESOLVED",
            "SLOT_ARM_HDRM__UNRESOLVED",
            "SLOT_TARGET_INTERFACE__UNRESOLVED",
            "SLOT_GRIPPER_R1_FINGERS__UNRESOLVED",
        ]
    )
    bus_m3r = next(
        row
        for row in audit["pairwise_narrow_phase_default_configuration"]
        if frozenset((row["component_a"], row["component_b"]))
        == frozenset(("INST_BUS_12U_CORE", "INST_M3R_INTERFACE_ASSEMBLY"))
    )

    checks = {
        "all_required_delivery_files_present": all(path.is_file() for path in required),
        "build_receipt_verdict_pass_with_holds": receipt["verdict"]
        == "M4_MASTER_DIGITAL_PROTOTYPE_BUILD_PASS_WITH_RELEASE_HOLDS",
        "builder_reported_all_geometry_checks_pass": receipt["all_geometry_checks_pass"] is True,
        "all_audit_checks_true": all(audit["checks"].values()),
        "receipt_output_hashes_match": observed_output_hashes == expected_output_hashes,
        "all_source_pin_hashes_match": all(row["match"] for row in source_pin_results),
        "fcstd_object_count_matches_receipt": fcstd_metrics["object_count"]
        == receipt["fcstd_cold_reopen"]["object_count"],
        "fcstd_has_five_App_Parts": fcstd_metrics["app_part_count"] == 5,
        "fcstd_has_six_internal_App_Links": fcstd_metrics["app_link_count"] == 6
        and fcstd_metrics["all_links_internal"],
        "fcstd_installed_set_exact": sorted(fcstd_metrics["installed_link_names"])
        == expected_installed,
        "fcstd_unresolved_slot_set_exact": fcstd_metrics["slot_names"] == expected_slots,
        "fcstd_all_embedded_source_shapes_valid": fcstd_metrics["all_source_shapes_valid"],
        "fcstd_export_composition_matches_six_links": fcstd_metrics["export_composition"]
        == "6_INSTALLED_LINKS_DEFAULT_CONFIGURATION",
        "step_reopens_valid": step_metrics["valid"],
        "step_has_40_solids": step_metrics["solids"] == 40,
        "step_metrics_match_build_receipt": all(
            step_metrics[key] == receipt["step_cold_reopen"][key]
            for key in ("valid", "solids", "faces", "volume_mm3", "bounding_box_mm")
        ),
        "bus_M3R_has_zero_common_volume": bus_m3r["common_volume_mm3"] == 0.0,
        "bus_M3R_gap_is_explicit_10_75_mm": bus_m3r["minimum_distance_mm"] == 10.75,
        "load_bridge_hold_present_in_frame_tree": "SPACECRAFT_LOAD_BRIDGE" in frame_text
        and "STRUCTURAL_LOAD_PATH" in frame_text,
        "M_vs_arm_base_distinction_present": "M_DYNAMICS_vs_B601_ARM_BASE_PHYSICAL" in frame_text,
        "architecture_prohibits_physical_B601_claim": "no_complete_physical_B601_geometry" in architecture_text,
        "collision_register_masks_frame_witness": "Never interpret the frame-axis witness" in collision_text,
        "owner_override_provenance_explicit": receipt["memory_gate"]["memory_gate_passed"] is False
        and receipt["memory_gate"]["owner_override_used"] is True
        and bool(receipt["memory_gate"].get("owner_override_source")),
        "drawing_index_header_valid": read_csv_header(DRAWING_INDEX)[0] == "drawing_id",
        "component_register_header_valid": read_csv_header(COMPONENT_REGISTER)[0]
        == "component_id",
        "BOM_header_valid": read_csv_header(BOM)[0] == "item_id",
        "no_FCBak_sidecars": not any(HERE.glob("*.FCBak")),
        "formal_FEA_not_performed": receipt["formal_fea_performed"] is False
        and audit["formal_fea_performed"] is False,
    }

    delivery_hashes = {
        path.relative_to(M4_ROOT).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in required
    }
    payload = {
        "schema": "M4_DIGITAL_PROTOTYPE_INDEPENDENT_VALIDATION_V1",
        "generated_utc": utc_now(),
        "validator": "FreeCADCmd_cold_reopen_plus_hash_and_document_checks",
        "fcstd": fcstd_metrics,
        "step": step_metrics,
        "bus_M3R_pair": bus_m3r,
        "source_pin_results": source_pin_results,
        "checks": checks,
        "delivery_hashes": delivery_hashes,
        "formal_FEA_performed": False,
        "known_release_holds": receipt["explicit_holds"],
        "verdict": "PASS_INDEPENDENT_DIGITAL_PROTOTYPE_VALIDATION_WITH_RELEASE_HOLDS"
        if all(checks.values())
        else "HOLD_INDEPENDENT_VALIDATION_FAILURE",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": payload["verdict"], "checks": checks}, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(2)


main()

