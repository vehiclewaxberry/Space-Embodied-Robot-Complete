#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the V5 native BOM seed from existing write-once receipts.

The output is a design-basis seed only.  It is not the released native BOM;
Loop3 generates the released `V5_NATIVE_TOP_BOM.csv` from the actual top
assembly.  This generator is COM-free and SolidWorks-free.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = RUN_ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
VALIDATION = RUN_ROOT / "13_validation"
LOOP1_RECEIPT = VALIDATION / "V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
LOOP1A_RECEIPT = VALIDATION / "V5_LOOP1A_SUBASSEMBLY_RECEIPT.json"
FASTENER_REGISTER = RUN_ROOT / "00_authority/V5_FASTENER_REGISTER.csv"
OUTPUT = RUN_ROOT / "08_bom/V5_NATIVE_BOM_SEED.csv"

COLUMNS = (
    "item_no",
    "component_name",
    "part_number",
    "revision",
    "quantity",
    "material",
    "native_path",
    "native_sha256",
    "configuration",
    "source_class",
    "provisional_mass_g",
    "release_scope",
    "status",
    "holds",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rows_from_loop1() -> List[Dict[str, Any]]:
    receipt = load_json(LOOP1_RECEIPT)
    rows = []
    for index, item in enumerate(receipt.get("native_parts", []), 1):
        target = Path(item["target"]["path"])
        name = target.stem
        role = item.get("role", "")
        if "STAGE_A" in role:
            material = "AL6061-T6"
            mass = "345.018961"
        elif "STAGE_B" in role:
            material = "AL6061-T6"
            mass = "437.308287"
        elif "CLEVIS_LEFT" in role:
            material = "AL6061-T6"
            mass = "30.577191"
        elif "CLEVIS_RIGHT" in role:
            material = "AL6061-T6"
            mass = "30.577191"
        elif "HINGE_AXIAL_SPACER" in role:
            material = "PTFE-FILLED-BRONZE"
            mass = "0.864076"
        elif "WING_HARNESS_GROMMET" in role:
            material = "VMQ-60A"
            mass = "0.824668"
        elif "WING_STOP_PAD" in role:
            material = "AL6061-T6"
            mass = "0.9072"
        elif "G07" in role:
            material = "AL7075-T6" if "PRIMARY" in role else ("PTFE-25GF" if "PAD" in role else "AL6061-T6")
            mass = {"PRIMARY": "169.244727", "PAD": "16.5", "CARRIER": "31.4928"}.get(next((k for k in ("PRIMARY", "PAD", "CARRIER") if k in role), ""), "")
        elif "G08" in role:
            material = "AL7075-T6" if "PRIMARY" in role else ("VMQ-60A" if "PAD" in role else "AL6061-T6")
            mass = {"PRIMARY": "97.826", "PAD": "2.25", "CARRIER": "12.4848"}.get(next((k for k in ("PRIMARY", "PAD", "CARRIER") if k in role), ""), "")
        elif "MID" in role:
            material = "AL7075-T6" if "BACKUP" in role else ("VESPEL-SP1" if "PAD" in role else "AL6061-T6")
            mass = {"BACKUP": "100.988186", "PAD": "3.861", "CARRIER": "12.635352"}.get(next((k for k in ("BACKUP", "PAD", "CARRIER") if k in role), ""), "")
        elif "HDRM" in role:
            material = "NON_PHYSICAL_ENVELOPE"
            mass = ""
        elif "CAMERA" in role or "HARNESS" in role:
            material = "NON_PHYSICAL_ENVELOPE"
            mass = ""
        else:
            material = "CANDIDATE"
            mass = ""
        rows.append(
            {
                "item_no": index,
                "component_name": name,
                "part_number": f"SEI-V5-{name}",
                "revision": "V5-A",
                "quantity": 1,
                "material": material,
                "native_path": posix(target),
                "native_sha256": item["target"]["sha256"],
                "configuration": "DEFAULT",
                "source_class": "CAD_VOLUME_DENSITY_V4" if mass else "ENVELOPE_OR_PENDING",
                "provisional_mass_g": mass,
                "release_scope": "COMPETITION_PROTOTYPE_MANUFACTURING_CANDIDATE",
                "status": "LOOP1_NATIVE_IMPORT_PASS",
                "holds": "NATIVE_MASS_MEASUREMENT_PENDING",
            }
        )
    return rows


def rows_from_loop1a() -> List[Dict[str, Any]]:
    receipt = load_json(LOOP1A_RECEIPT)
    rows = []
    start = 100
    for index, item in enumerate(receipt.get("subassemblies", []), start):
        target = Path(item["target"]["path"])
        rows.append(
            {
                "item_no": index,
                "component_name": target.stem,
                "part_number": f"SEI-V5-{target.stem}",
                "revision": "V5-A",
                "quantity": 1,
                "material": "ASSEMBLY",
                "native_path": posix(target),
                "native_sha256": item["target"]["sha256"],
                "configuration": "DEFAULT",
                "source_class": "NATIVE_ASSEMBLY",
                "provisional_mass_g": "",
                "release_scope": "COMPETITION_PROTOTYPE_MANUFACTURING_CANDIDATE",
                "status": "LOOP1A_COLD_REOPEN_PASS",
                "holds": "TOP_CONTEXT_VALIDATION_PENDING",
            }
        )
    diamond = receipt.get("diamond_locator")
    if diamond:
        target = Path(diamond["path"])
        rows.append(
            {
                "item_no": start + len(receipt.get("subassemblies", [])),
                "component_name": target.stem,
                "part_number": "SEI-V5-B601-DIAMOND-DOWEL-4MM",
                "revision": "V5-A",
                "quantity": 1,
                "material": "HARDENED_STAINLESS_CANDIDATE",
                "native_path": posix(target),
                "native_sha256": diamond["save"]["sha256"],
                "configuration": "DEFAULT",
                "source_class": "NATIVE_PART",
                "provisional_mass_g": "",
                "release_scope": "COMPETITION_PROTOTYPE_MANUFACTURING_CANDIDATE",
                "status": "LOOP1A_DIAMOND_LOCATOR_PASS",
                "holds": "PRESS_SLIP_PAIR_TBD",
            }
        )
    return rows


def rows_from_loop1b() -> List[Dict[str, Any]]:
    rows = []
    start = 200
    for index, checkpoint in enumerate(sorted(VALIDATION.glob("V5_LOOP1B_ARTIFACT_*.json")), start):
        payload = load_json(checkpoint)
        target = payload.get("target")
        if not target:
            continue
        path = Path(target["path"])
        rows.append(
            {
                "item_no": index,
                "component_name": path.stem,
                "part_number": f"SEI-V5-{path.stem}",
                "revision": "V5-A",
                "quantity": 1,
                "material": "DONOR_OR_CANDIDATE",
                "native_path": posix(path),
                "native_sha256": target["sha256"],
                "configuration": "DEFAULT",
                "source_class": "NATIVE_DONOR_ISOLATED",
                "provisional_mass_g": "",
                "release_scope": "COMPETITION_PROTOTYPE_GEOMETRY_CANDIDATE",
                "status": "LOOP1B_ARTIFACT_CHECKPOINT_PASS",
                "holds": "TRUE_HINGE_ASSEMBLY_PENDING",
            }
        )
    return rows


def rows_from_fasteners() -> List[Dict[str, Any]]:
    rows = []
    with FASTENER_REGISTER.open(encoding="utf-8-sig", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream), 300):
            rows.append(
                {
                    "item_no": index,
                    "component_name": row["fastener_id"],
                    "part_number": row["fastener_id"],
                    "revision": "V5-A",
                    "quantity": row["quantity"],
                    "material": row["grade_material"],
                    "native_path": "",
                    "native_sha256": "",
                    "configuration": "DEFAULT",
                    "source_class": "HANDBOOK_ESTIMATE",
                    "provisional_mass_g": "",
                    "release_scope": "COMPETITION_PROTOTYPE_MANUFACTURING_CANDIDATE",
                    "status": "PROTOTYPE_ASSEMBLY_PRELOAD_DEFINED",
                    "holds": "FORMAL_LAUNCH_FASTENER_MOS=HOLD",
                }
            )
    return rows


def main() -> None:
    rows = [*rows_from_loop1(), *rows_from_loop1a(), *rows_from_loop1b(), *rows_from_fasteners()]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite existing BOM seed: {OUTPUT}")
    with OUTPUT.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in COLUMNS})
    print(json.dumps({"verdict": "V5_NATIVE_BOM_SEED_WRITTEN", "path": posix(OUTPUT), "rows": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
