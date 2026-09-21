"""Exact expansion and blocked order for the frozen 78-case R2 matrix."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .strict_json import canonical_sha256, load_path


MATRIX_SHA256 = "D7B23B92DA46A6F9E96CF856914C7D5AECAD26240141C7F2B637A2AF119B7BEB"
SCHEDULE_SHA256 = "259EB3A99C0C0A45A6C80AEB979E2F15F3023804128517192C24D1B8A8F20EC7"
SCHEDULE_SEED = 20260825
COMMON_GROUP_SHA256 = "396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444"

LANES = (
    ("RK4_H_MS_0P25", "rk4", 0.00025),
    ("RK4_H_MS_0P125", "rk4", 0.000125),
    ("RK4_H_MS_0P0625", "rk4", 0.0000625),
    ("MIDPOINT_H_MS_0P25", "midpoint", 0.00025),
    ("MIDPOINT_H_MS_0P125", "midpoint", 0.000125),
    ("MIDPOINT_H_MS_0P0625", "midpoint", 0.0000625),
)


def _alpha_token(alpha: float | int) -> str:
    return "0P5" if float(alpha) == 0.5 else str(int(alpha))


def fresh_a1_id(lane_id: str, alpha: float | int, duration_ms: int) -> str:
    return f"FRESH__{lane_id}__A1__A_{_alpha_token(alpha)}__T_MS_{duration_ms}"


def expand_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane_id, method, step_s in LANES:
        for sentinel in ("PRE", "POST"):
            rows.append({
                "case_id": f"FRESH__{lane_id}__A0__{sentinel}",
                "execution_family": "FRESH", "roles": ["A0_BOOKEND"],
                "lane_id": lane_id, "method": method, "step_s": step_s,
                "arm": "A0", "sentinel": sentinel,
                "alpha": "NOT_APPLICABLE_A0", "command_duration_s": "NOT_APPLICABLE_A0",
                "initial_state": "LANE_SPECIFIC_FRESH_B3", "g12_credit": False, "selector_input": False,
            })
        for duration_ms in (5, 10, 20):
            roles = ["FRESH_ALPHA16_PROPAGATION"]
            if duration_ms == 10:
                roles.append("FRESH_ACQ_OBSERVATION")
            if step_s == 0.0000625:
                roles.append("G12_FRESH_REFERENCE")
            rows.append({
                "case_id": fresh_a1_id(lane_id, 16, duration_ms),
                "execution_family": "FRESH", "roles": roles,
                "lane_id": lane_id, "method": method, "step_s": step_s,
                "arm": "A1", "sentinel": "NOT_APPLICABLE_A1", "alpha": 16.0,
                "command_duration_s": duration_ms / 1000,
                "initial_state": "LANE_SPECIFIC_FRESH_B3",
                "g12_credit": step_s == 0.0000625, "selector_input": step_s == 0.0000625,
            })
        if step_s == 0.0000625:
            for alpha in (0.5, 1, 2, 4, 8):
                for duration_ms in (5, 10, 20):
                    rows.append({
                        "case_id": fresh_a1_id(lane_id, alpha, duration_ms),
                        "execution_family": "FRESH", "roles": ["G12_FRESH_REFERENCE"],
                        "lane_id": lane_id, "method": method, "step_s": step_s,
                        "arm": "A1", "sentinel": "NOT_APPLICABLE_A1", "alpha": float(alpha),
                        "command_duration_s": duration_ms / 1000,
                        "initial_state": "LANE_SPECIFIC_FRESH_B3", "g12_credit": True, "selector_input": True,
                    })
        for duration_ms in (5, 10, 20):
            rows.append({
                "case_id": f"COMMON_PROP__{lane_id}__A_16__T_MS_{duration_ms}",
                "execution_family": "COMMON_PROP", "roles": ["COMMON_PROPAGATION_DIAGNOSTIC"],
                "lane_id": lane_id, "method": method, "step_s": step_s,
                "arm": "A1", "sentinel": "NOT_APPLICABLE_A1", "alpha": 16.0,
                "command_duration_s": duration_ms / 1000,
                "initial_state": f"COMMON_STATE_GROUP_{COMMON_GROUP_SHA256}",
                "g12_credit": False, "selector_input": False,
            })
    return sorted(rows, key=lambda row: row["case_id"])


def generate_schedule(seed: int = SCHEDULE_SEED) -> list[str]:
    def key(namespace: str, item: str) -> str:
        return hashlib.sha256(f"{seed}|{namespace}|{item}".encode("utf-8")).hexdigest()

    ordered: list[str] = []
    nonreference = sorted(
        (lane for lane, _, step in LANES if step != 0.0000625),
        key=lambda lane: key("NONREFERENCE_LANE_ORDER", lane),
    )
    for lane in nonreference:
        ordered.append(f"FRESH__{lane}__A0__PRE")
        cases = [fresh_a1_id(lane, 16, duration) for duration in (5, 10, 20)]
        ordered.extend(sorted(cases, key=lambda case: key(f"FRESH_LANE__{lane}", case)))
        ordered.append(f"FRESH__{lane}__A0__POST")
    references = tuple(lane for lane, _, step in LANES if step == 0.0000625)
    ordered.extend(sorted((f"FRESH__{lane}__A0__PRE" for lane in references), key=lambda case: key("REFERENCE_A0_PRE", case)))
    levels = [(alpha, duration) for alpha in (0.5, 1, 2, 4, 8, 16) for duration in (5, 10, 20)]
    levels.sort(key=lambda item: key("G12_LEVEL", f"{item[0]}|{item[1]}"))
    for alpha, duration in levels:
        pair = [fresh_a1_id(lane, alpha, duration) for lane in references]
        ordered.extend(sorted(pair, key=lambda case: key(f"G12_PAIR__{_alpha_token(alpha)}__{duration}", case)))
    ordered.extend(sorted((f"FRESH__{lane}__A0__POST" for lane in references), key=lambda case: key("REFERENCE_A0_POST", case)))
    durations = sorted((5, 10, 20), key=lambda duration: key("COMMON_DURATION", str(duration)))
    for duration in durations:
        cases = [f"COMMON_PROP__{lane}__A_16__T_MS_{duration}" for lane, _, _ in LANES]
        ordered.extend(sorted(cases, key=lambda case: key(f"COMMON_DURATION__{duration}", case)))
    return ordered


def verify_frozen_matrix_and_schedule(contract_path: Path) -> dict[str, Any]:
    contract = load_path(contract_path)
    matrix = expand_matrix()
    schedule = generate_schedule(SCHEDULE_SEED)
    matrix_hash = canonical_sha256(matrix)
    schedule_hash = canonical_sha256(schedule)
    passed = bool(
        isinstance(contract, dict)
        and contract.get("case_count") == 78
        and contract.get("expanded_matrix_canonical_sha256") == matrix_hash == MATRIX_SHA256
        and contract.get("case_ids_canonical_sha256") == schedule_hash == SCHEDULE_SHA256
        and contract.get("case_ids_in_blocked_order") == schedule
        and len({row["case_id"] for row in matrix}) == 78
    )
    return {"passed": passed, "case_count": len(matrix), "matrix_sha256": matrix_hash, "schedule_sha256": schedule_hash}
