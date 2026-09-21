from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
V22_VENDOR03 = (
    WORKSPACE_ROOT
    / "20_engineering"
    / "cad"
    / "Space_Embodied_Robot_CAD_V2_2"
    / "130_B601_Vendor_CAD_Direct_Integration_03"
)
MACHINE_CHECKS = V22_VENDOR03 / "validation" / "machine_checks.json"
ADAPTER_CLOCKING = V22_VENDOR03 / "design" / "adapter_clocking.json"
STOW_V2 = V22_VENDOR03 / "design" / "b601_stow_joint_vector_v2.json"
STOW_FAMILY = V22_VENDOR03 / "design" / "stow_family_study.json"
CONTACTS = V22_VENDOR03 / "design" / "stow_contact_registry.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"source is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_text_once(path: Path, text: str) -> None:
    if path.exists():
        raise RuntimeError(f"overwrite forbidden: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def proposed_class(module: str, structure: str) -> tuple[str, str]:
    if module == "ADP_SPREADER":
        return (
            "UNACCEPTABLE_COLLISION",
            "Remove legacy full-area spreader; replace with short pedestal and "
            "two datum-driven crossmembers.",
        )
    if module.startswith("ADP_LOAD_BRIDGE"):
        return (
            "INTENDED_BOLTED_LAP",
            "Replace undefined overlap with a discrete interface shoe and "
            "flush mating datum; hole/fastener selection remains TBD.",
        )
    if "DECK" in structure or "PANEL" in structure:
        return (
            "UNACCEPTABLE_COLLISION",
            "Reroute the independent saddle load path to the main frame or "
            "longeron and preserve deck/panel clearance.",
        )
    return (
        "INTENDED_BOLTED_LAP",
        "Replace the legacy crossbeam overlap with a named frame/longeron "
        "interface shoe and verify exact BREP contact.",
    )


def main() -> int:
    input_lock = load_json(CANDIDATE_ROOT / "00_AUDIT" / "B51_INPUT_LOCK.json")
    if not str(input_lock["status"]).startswith("B51_PHASE_A_INPUT_LOCK_PASS"):
        raise RuntimeError("Phase A input lock is not in a pass state")

    checks = load_json(MACHINE_CHECKS)
    clocking = load_json(ADAPTER_CLOCKING)
    stow = load_json(STOW_V2)
    family = load_json(STOW_FAMILY)
    contacts = load_json(CONTACTS)

    if float(clocking["clock_deg"]) != 25.0:
        raise RuntimeError("25 degree source value drifted")
    records = checks["checks"]["V14_MODULE_VS_FROZEN_STRUCTURE"]["records"]
    physical_records = [
        row
        for row in records
        if row["class"] == "UNADJUDICATED_INTERPENETRATION"
    ]
    if len(physical_records) != 28:
        raise RuntimeError(
            f"V14 physical record count {len(physical_records)} != 28"
        )

    requirements_root = CANDIDATE_ROOT / "01_REQUIREMENTS"
    interface_root = CANDIDATE_ROOT / "02_INTERFACE"
    gate_root = CANDIDATE_ROOT / "07_VERIFICATION"

    packaging_md = f"""# B5.1 H9 packaging mode decision

Status: `HUMAN_DECISION_REQUIRED`

The 25 degree base clock is ratified only as:

`RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY`

It is a fixed spacecraft-to-arm installation transform. It is not part of
joint1 zero and is not a flight-interface release.

## Evidence-bound benefit

- 0 degree family minimum max Z: 520.83 mm.
- 25 degree family minimum max Z: 365.65 mm.
- delivered STOW v2 conservative mesh max Z: 368.62 mm.
- delivered STOW STEP max Z: 361.34 mm.
- max absolute Y: 104.24 mm against the current 113.15 mm half-width
  condition; margin 8.91 mm.
- max X: 412.45 mm by mesh and 412.47 mm by STEP against the current
  430 mm engineering condition.
- joint1 remaining limit margin: 15.86 degrees.

The clocking benefit is approximately 155 mm of height reduction and removal
of joint1 saturation. It is not evidence that clocking is required to satisfy
the X/Y conditions.

## Mode A: `MODE_A_12U_DEPLOYER_COMPLIANT`

The current core structural-box proxy is 366 x 226.3 x 228.3 mm with
Z=[-113.15,115.15] mm. The delivered B601 STEP top exceeds that box top by
246.19 mm; the conservative mesh exceeds it by 253.47 mm.

Provisional result:

`ARCHITECTURE_NOT_PACKAGING_COMPLIANT_AGAINST_CURRENT_CORE_BOX_PROXY`

This is not a formal deployer verdict because no launcher/deployer ICD is
bound. The historic 238.3 > 226.3 mm and 302.3 > 226.3 mm solar negative
findings remain active.

## Mode B: `MODE_B_12U_CLASS_BUS_EXTERNAL_SERVICE_MODULE`

The current two-file STEP union is only a provisional envelope:

- X=[-213.00,412.47] mm
- Y=[-113.15,113.15] mm
- Z=[-115.00,361.34] mm
- size=625.47 x 226.30 x 476.34 mm
- conservative-mesh total height=483.62 mm

This union does not yet include every solar-wing negative envelope, launcher
interface, harness sweep, tolerance, or dynamic clearance. It is not the final
flight-vehicle envelope.

## Decision gate

Until an authorized human selects Mode A or Mode B and binds the applicable
launcher/deployer ICD, H9 remains HOLD. Mode B is the recommended engineering
continuation, not an automatically approved architecture.

Source hashes:

- adapter clocking: `{sha256_file(ADAPTER_CLOCKING)}`
- STOW v2: `{sha256_file(STOW_V2)}`
- STOW family: `{sha256_file(STOW_FAMILY)}`
"""
    write_text_once(
        requirements_root / "B51_PACKAGING_ENVELOPE_DECISION.md",
        packaging_md,
    )

    interface_md = """# B5.1 interface control drawing contract

Drawing level:

`ENGINEERING_DEFINITION_DRAWING_NOT_MANUFACTURING_RELEASE`

## Controlling datum chain

`CS_S -> TASK_FACE_X=183 -> B51 bridge adapter -> M_PLANE_X=198 -> A0`

The dynamics/PDR track at 185.25 mm and the V2.2 display track at 198.0 mm
remain separate. Their 12.75 mm difference must not be collapsed.

## Candidate load path

`B601 base wrench -> 25 degree top flange -> short center pedestal -> forward
and aft crossmembers -> named interface shoes -> main frames/longerons`

Decks, equipment panels, and exterior skins are excluded from the primary
load path.

## Frozen or admitted geometry

- task face X: 183.0 mm
- V2.2 display installation plane X: 198.0 mm
- dynamics/PDR interface coordinate X: 185.25 mm
- longeron reference centers: Y/Z = +/-105.65 mm
- MID1 frame: X=61.0 mm
- MID2 frame: X=-61.0 mm
- top installation reference: 160 x 160 mm
- central passage reservation: diameter 100 mm
- B5.1 clocking candidate: 25 degrees about the B601 A0/J1 axis

## Open physical fields

Bolt pattern, hole count and size, locating pins, interface shoes, material,
thickness qualification, tolerance, preload, locking, grounding, thermal
isolation, connector routing, tool clearance, six-dimensional load cases, and
launcher interface remain `UNKNOWN/TBD/HOLD`.
"""
    write_text_once(
        requirements_root / "B51_INTERFACE_CONTROL_DRAWING.md",
        interface_md,
    )

    main_contact = contacts["contacts"]["MAIN"]
    grip_contact = contacts["contacts"]["GRIP"]
    datum_yaml = f"""schema: SER_B51_MASTER_SKELETON_DATUM_REGISTER_V1
generated_utc: {utc_now()}
status: ENGINEERING_CANDIDATE_WITH_H9_H10_HOLDS
frames:
  CS_S:
    role: spacecraft_reference
  A0:
    role: accepted_B601_base_link
    mass_authority: accepted_URDF_only
  CLOCK25:
    parent: CS_S
    rotation_about_A0_J1_deg: 25.0
    status: RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY
planes_mm:
  TASK_FACE_X: 183.0
  DYNAMICS_PDR_M_X: 185.25
  V22_DISPLAY_M_X: 198.0
  MID1_X: 61.0
  MID2_X: -61.0
references_mm:
  longeron_center_abs_yz: 105.65
  installation_plane_yz: [160.0, 160.0]
  central_passage_diameter: 100.0
stow_contacts:
  G07_MAIN:
    x_window: [10.0, 60.0]
    z_bottom: {main_contact["z_bottom_mm"]}
    y_window: [{main_contact["y_min_mm"]}, {main_contact["y_max_mm"]}]
    status: CONTACT_QUALIFICATION_HOLD
  G08_GRIP:
    x_window: [-100.0, -40.0]
    z_bottom: {grip_contact["z_bottom_mm"]}
    y_window: [{grip_contact["y_min_mm"]}, {grip_contact["y_max_mm"]}]
    status: CHAIN_DERIVED_AND_CONTACT_QUALIFICATION_HOLD
"""
    write_text_once(
        requirements_root / "B51_MASTER_SKELETON_DATUM_REGISTER.yaml",
        datum_yaml,
    )

    ledger_path = (
        interface_root / "B51_INTERFERENCE_DISPOSITION_LEDGER.csv"
    )
    if ledger_path.exists():
        raise RuntimeError(f"overwrite forbidden: {ledger_path}")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_rows: list[dict[str, Any]] = []
    for index, row in enumerate(physical_records, start=1):
        category, action = proposed_class(
            row["module_solid"], row["structure"]
        )
        ledger_rows.append(
            {
                "id": f"V14-{index:02d}",
                "source_method": (
                    "LEGACY_AABB_COARSE_OVER_1000_MM3_NOT_EXACT_BREP"
                ),
                "module_solid": row["module_solid"],
                "structure_solid": row["structure"],
                "legacy_aabb_overlap_mm3": row["aabb_overlap_mm3"],
                "b51_proposed_class": category,
                "design_action": action,
                "exact_common_volume_mm3": "",
                "minimum_distance_mm": "",
                "local_screenshot": "",
                "replacement_part": "",
                "closure_status": (
                    "OPEN_REDESIGN_AND_EXACT_BREP_RECHECK_REQUIRED"
                ),
            }
        )
    with ledger_path.open("x", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(ledger_rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(ledger_rows)

    gate = {
        "schema": "SER_B51_PHASE_BC_GATE_V1",
        "generated_utc": utc_now(),
        "status": (
            "B51_PHASE_B_H9_HUMAN_DECISION_HOLD_"
            "PHASE_C_V14_SEED_LEDGER_COMPLETE"
        ),
        "clocking_25_deg": (
            "RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY"
        ),
        "h9": "HUMAN_DECISION_REQUIRED",
        "mode_a": (
            "ARCHITECTURE_NOT_PACKAGING_COMPLIANT_"
            "AGAINST_CURRENT_CORE_BOX_PROXY"
        ),
        "mode_b": "ENGINEERING_CONTINUATION_RECOMMENDED_NOT_RATIFIED",
        "v14_seed_records": len(ledger_rows),
        "v14_nonphysical_reservation_excluded": 1,
        "h10": "FAIL_RECORDED_ENGINEERING_DECOMPOSITION_REQUIRED",
        "required_before_h10_pass": [
            "Build the replacement bridge adapter and two independent saddles.",
            "Run exact BREP common-volume and minimum-distance checks.",
            "Attach a local image for every original V14 item.",
            "Set unadjudicated and unacceptable residual collisions to zero.",
        ],
        "source_contract": {
            "machine_checks_sha256": sha256_file(MACHINE_CHECKS),
            "adapter_clocking_sha256": sha256_file(ADAPTER_CLOCKING),
            "stow_v2_sha256": sha256_file(STOW_V2),
            "stow_family_sha256": sha256_file(STOW_FAMILY),
            "contacts_sha256": sha256_file(CONTACTS),
        },
        "artifacts": {
            "packaging_decision": (
                "01_REQUIREMENTS/B51_PACKAGING_ENVELOPE_DECISION.md"
            ),
            "interface_control": (
                "01_REQUIREMENTS/B51_INTERFACE_CONTROL_DRAWING.md"
            ),
            "datum_register": (
                "01_REQUIREMENTS/B51_MASTER_SKELETON_DATUM_REGISTER.yaml"
            ),
            "interference_ledger": (
                "02_INTERFACE/B51_INTERFERENCE_DISPOSITION_LEDGER.csv"
            ),
        },
        "next_gate": (
            "B51_NATIVE_MASTER_SKELETON_ARTICULATION_AND_INTERFACE_REDESIGN"
        ),
    }
    write_text_once(
        gate_root / "B51_PHASE_BC_GATE.json",
        json.dumps(gate, ensure_ascii=False, indent=2),
    )
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
