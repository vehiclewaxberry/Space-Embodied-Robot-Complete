#!/usr/bin/env python3
"""Fail-closed validation for the Route-C official-source refresh."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5]
INPUT = HERE / "ROUTE_C_OFFICIAL_SOURCE_REFRESH_V1.yaml"
OUTPUT = HERE / "ROUTE_C_OFFICIAL_SOURCE_REFRESH_VALIDATION_V1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> None:
    refresh = load_yaml(INPUT)
    registry_pin = refresh["base_registry"]
    gate_pin = refresh["base_admission_gate"]
    registry_path = ROOT / registry_pin["path"]
    gate_path = ROOT / gate_pin["path"]
    registry = load_yaml(registry_path)
    gate = load_yaml(gate_path)

    checks: list[dict[str, Any]] = []

    def check(identifier: str, name: str, value: bool) -> None:
        checks.append({"id": identifier, "name": name, "pass": bool(value)})

    check("RCS-V01", "base registry byte and hash pin exact", registry_path.stat().st_size == registry_pin["bytes"] and digest(registry_path) == registry_pin["sha256"])
    check("RCS-V02", "base admission Gate byte and hash pin exact", gate_path.stat().st_size == gate_pin["bytes"] and digest(gate_path) == gate_pin["sha256"])
    check(
        "RCS-V03",
        "base registry independently remains 0 AVAILABLE and 13 HOLD",
        registry["summary"]["entries_total"] == 13
        and registry["summary"]["value_non_null"] == 0
        and registry["summary"]["status_AVAILABLE"] == 0
        and registry["summary"]["status_HOLD"] == 13
        and all(row["value"] is None and row["status"] == "HOLD" for row in registry["registry_entries"]),
    )
    check(
        "RCS-V04",
        "base admission Gate independently remains 2/8 and CAD unauthorized",
        gate["current_evaluation"]["tally"] == {
            "conditions_total": 8,
            "pass": 2,
            "fail": 6,
            "pass_ids": ["C2-ADM-01", "C2-ADM-07"],
            "fail_ids": ["C2-ADM-02", "C2-ADM-03", "C2-ADM-04", "C2-ADM-05", "C2-ADM-06", "C2-ADM-08"],
        }
        and gate["current_evaluation"]["ROUTE_C_CAD_AUTHORIZED"] is False,
    )
    records = refresh["official_source_records"]
    check("RCS-V05", "exact four official manufacturer records", [row["id"] for row in records] == ["SRC-E2M-06", "SRC-TSUBAKI-PVDF", "SRC-CF9-UL", "SRC-TECASINT-8591"])
    check("RCS-V06", "all source URLs are HTTPS manufacturer domains", all(row["url"].startswith("https://") and any(domain in row["url"] for domain in ("igus.com", "tsubakimoto.co.jp", "ensingerplastics.com")) for row in records))
    e2 = records[0]["catalog_fact_snapshot"]
    check("RCS-V07", "E2 Micro Series 06 screening dimensions exact", e2["inner_height_mm"] == 10.5 and e2["inner_width_range_mm"] == [6.0, 64.0] and e2["bend_radius_options_mm"] == [18.0, 28.0, 38.0] and e2["pitch_mm"] == 20.0)
    cf9 = records[2]["catalog_fact_snapshot"]
    check("RCS-V08", "CF9 dynamic evidence remains family-level", cf9["stated_e_chain_lifetime_double_strokes"] == [5000000, 7500000, 10000000] and cf9["minimum_e_chain_bend_radius_factor_d_by_lifetime"] == [5.0, 6.0, 7.0] and records[2]["candidate_status"] == "PRODUCT_FAMILY_DYNAMIC_EVIDENCE_ONLY")
    tec = records[3]["catalog_fact_snapshot"]
    check("RCS-V09", "TECASINT record remains single-material screening", tec["coefficient_of_friction_range"] == [0.14, 0.22] and records[3]["candidate_status"] == "SINGLE_MATERIAL_SCREENING_ONLY")
    effects = refresh["field_effects"]
    check("RCS-V10", "only P04/P06/P10/P12 receive screening-source links", [row["id"] for row in effects] == ["P04", "P06", "P10", "P12"])
    check("RCS-V11", "all affected field values remain null HOLD with no promotion", all(row["registry_value"] is None and row["registry_status"] == "HOLD" and row["promotion"] == "NONE" for row in effects))
    decision = refresh["decision"]
    check("RCS-V12", "decision remains fail-closed", decision["fields_promoted_to_AVAILABLE"] == 0 and decision["registry_value_non_null_after"] == 0 and decision["registry_status_AVAILABLE_after"] == 0 and decision["registry_status_HOLD_after"] == 13 and decision["exact_parts_selected"] == 0 and decision["owner_accepted"] is False and decision["ROUTE_C_CAD_AUTHORIZED"] is False and decision["geometry_execution_authorized"] is False and decision["next_stage_authorized"] is False and decision["release_credit"] is False)

    passed = sum(row["pass"] for row in checks)
    result = {
        "schema": "ROUTE_C_OFFICIAL_SOURCE_REFRESH_VALIDATION_V1",
        "generated_date_local": "2026-08-24",
        "input_path": INPUT.name,
        "input_sha256": digest(INPUT),
        "checks": checks,
        "summary": {"passed": passed, "total": len(checks), "failed": [row["id"] for row in checks if not row["pass"]]},
        "verdict": "PASS_FAIL_CLOSED_SOURCE_REFRESH_VALIDATION" if passed == len(checks) else "FAIL_SOURCE_REFRESH_VALIDATION",
        "ROUTE_C_CAD_AUTHORIZED": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result["summary"] | {"verdict": result["verdict"]}, ensure_ascii=False, indent=2))
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

