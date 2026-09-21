"""Exact 78-row matrix, blocked-order, role, and source-hash binding."""

from __future__ import annotations

from typing import Any

from .production_api import load_production_modules
from .strict_json import canonical_sha256


MATRIX_SHA256 = "D7B23B92DA46A6F9E96CF856914C7D5AECAD26240141C7F2B637A2AF119B7BEB"
SCHEDULE_SHA256 = "259EB3A99C0C0A45A6C80AEB979E2F15F3023804128517192C24D1B8A8F20EC7"
BACKEND_SOURCE_TERMINAL_SHA256 = "2CF4D4C5479485FFB579AC0E00FF59980665D73C4F9E23CA3FCCC45E58E6B634"
SOURCE_HASHES = {
    "matrix_sha256": MATRIX_SHA256,
    "schedule_sha256": SCHEDULE_SHA256,
    "backend_source_terminal_sha256": BACKEND_SOURCE_TERMINAL_SHA256,
    "common_donor_raw_sha256": "5DF0C19A71180E1BD91816235AAD50108613C2BC0F99F950018D786119CF9D4F",
    "common_donor_payload_sha256": "DA3E10D7D30DFD9BABFB71BF055D62A1BD06CF8DE3023E463A649FF92A952D15",
    "common_state_group_sha256": "396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444",
    "adapter_execution_terminal_preregistered": "NOT_AVAILABLE_SOURCE_FREEZE_ONLY_NO_DIRECT_OWNER_SOURCE",
}


def schedule_records() -> tuple[list[dict[str, Any]], list[str]]:
    schedule = load_production_modules()["schedule"]
    rows = schedule.expand_matrix()
    order = schedule.generate_schedule()
    if canonical_sha256(rows) != MATRIX_SHA256 or canonical_sha256(order) != SCHEDULE_SHA256:
        raise ValueError("FROZEN_MATRIX_OR_SCHEDULE_HASH_DRIFT")
    return rows, order


def expected_binding(case_id: str) -> dict[str, Any]:
    rows, order = schedule_records()
    matches = [row for row in rows if row["case_id"] == case_id]
    if len(matches) != 1 or order.count(case_id) != 1:
        raise ValueError("CASE_NOT_UNIQUE_IN_FROZEN_R2_MATRIX_AND_SCHEDULE")
    row = matches[0]
    return {
        "row": row,
        "schedule_index": order.index(case_id),
        "matrix_row_sha256": canonical_sha256(row),
        "source_hashes": dict(SOURCE_HASHES),
    }


__all__ = ["BACKEND_SOURCE_TERMINAL_SHA256", "MATRIX_SHA256", "SCHEDULE_SHA256", "SOURCE_HASHES", "expected_binding", "schedule_records"]
