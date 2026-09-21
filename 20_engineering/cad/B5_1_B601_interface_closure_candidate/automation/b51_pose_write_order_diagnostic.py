"""Read-only SolidWorks diagnostic for T003 coordinated-pose solver snap.

The T003 pretest assembly is opened read-only.  Several top-level segment
Transform2 write orders are compared for the first deterministic random legal
q vector.  No native document is saved.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import b51_build_articulated_segment_chain as chainmod  # noqa: E402

core = chainmod.core
RUN_ROOT = (
    CANDIDATE_ROOT
    / "03_CAD"
    / "native_articulated"
    / "B51_SEGMENT_CHAIN_6R_20260728T003"
)
ASSEMBLY_PATH = (
    RUN_ROOT
    / "assembly"
    / "B51_B601_ARTICULATED_ENGINEERING_ARM_PRETEST.SLDASM"
)
OUTPUT = (
    CANDIDATE_ROOT
    / "07_VERIFICATION"
    / "articulation"
    / "B51_T003_POSE_WRITE_ORDER_DIAGNOSTIC.json"
)
Q_TEST = [
    0.027636394858497226,
    -0.66990466086214,
    -0.6105793310540046,
    -1.5127109592851438,
    -1.3629301337689044,
    -1.6719054180833184,
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def apply_pass(
    session: core.SolidWorksSession,
    model: Any,
    assembly: Any,
    segments: dict[str, Any],
    expected: dict[str, Any],
    order: list[int],
) -> dict[str, Any]:
    initial = bool(assembly.EnableAssemblyRebuild)
    writes: list[dict[str, Any]] = []
    try:
        assembly.EnableAssemblyRebuild = False
        for index in order:
            role = f"link{index}"
            target = expected[role]
            segments[role].Transform2 = chainmod.legacy._math_transform(
                session, target
            )
            actual = chainmod.legacy._component_array(segments[role])
            target_array = chainmod.legacy._matrix_array(target)
            writes.append(
                {
                    "role": role,
                    "immediate_max_abs_error": chainmod.legacy._max_error(
                        actual, target_array
                    ),
                }
            )
    finally:
        assembly.EnableAssemblyRebuild = initial
    rebuild_ok = bool(model.ForceRebuild3(True))
    return {"order": order, "writes": writes, "rebuild_ok": rebuild_ok}


def run_variant(
    session: core.SolidWorksSession,
    chain: dict[str, Any],
    *,
    name: str,
    pass_orders: list[list[int]],
) -> dict[str, Any]:
    model, open_record = session.open_document(ASSEMBLY_PATH, "assembly")
    assembly = session.cast(model, "IAssemblyDoc")
    if open_record["warnings"] not in (None, 0):
        raise core.Phase0Error(f"diagnostic open warnings: {open_record}")
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("diagnostic initial rebuild failed")
    segments = chainmod._map_reopened_segments(session, assembly, 6)
    visuals, _, _ = chainmod._nested_map(session, segments, 6)
    expected = chainmod._fk_unbounded(chain, Q_TEST, 6)
    passes: list[dict[str, Any]] = []
    for pass_index, order in enumerate(pass_orders, start=1):
        record = apply_pass(
            session, model, assembly, segments, expected, order
        )
        record["pass_index"] = pass_index
        record["readback"] = chainmod._verify_pose(
            segments,
            visuals,
            expected,
            6,
            tolerance=1.0,
        )
        passes.append(record)
    result = {
        "name": name,
        "open": open_record,
        "pass_orders": pass_orders,
        "passes": passes,
        "final_max_abs_error": passes[-1]["readback"]["max_abs_error"],
        "acceptance_tolerance": 2.0e-7,
        "pass": passes[-1]["readback"]["max_abs_error"] <= 2.0e-7,
    }
    session.close_all_documents()
    return result


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"append-only output already exists: {OUTPUT}")
    if not ASSEMBLY_PATH.is_file():
        raise RuntimeError(f"T003 pretest assembly missing: {ASSEMBLY_PATH}")
    chain = chainmod.legacy._parse_urdf()
    chainmod._validate_q_vector_limits(chain, Q_TEST, 6)
    proximal = list(range(1, 7))
    distal = list(range(6, 0, -1))
    variants = [
        ("PROXIMAL_ONE_PASS", [proximal]),
        ("DISTAL_ONE_PASS", [distal]),
        ("PROXIMAL_THREE_PASS", [proximal, proximal, proximal]),
        ("DISTAL_THREE_PASS", [distal, distal, distal]),
        ("ALTERNATING_DISTAL_PROXIMAL_DISTAL", [distal, proximal, distal]),
    ]
    results: list[dict[str, Any]] = []
    with core.SolidWorksSession(RUN_ROOT, visible=False) as session:
        session_start = session.info()
        for name, orders in variants:
            results.append(
                run_variant(
                    session,
                    chain,
                    name=name,
                    pass_orders=orders,
                )
            )
    successful = [
        item["name"] for item in results if item["pass"]
    ]
    payload = {
        "schema": "SER_B51_T003_POSE_WRITE_ORDER_DIAGNOSTIC_V1",
        "generated_utc": utc_now(),
        "status": (
            "POSE_WRITE_ORDER_CANDIDATE_FOUND"
            if successful
            else "POSE_WRITE_ORDER_VARIANTS_ALL_FAIL"
        ),
        "source_run": "B51_SEGMENT_CHAIN_6R_20260728T003",
        "source_assembly": str(ASSEMBLY_PATH.resolve()),
        "source_open_mode": "READ_ONLY_NO_SAVE",
        "q_test_rad": Q_TEST,
        "session_start": session_start,
        "session_end": session.info(),
        "variants": results,
        "successful_variants": successful,
        "claim_limit": (
            "Diagnostic only. A successful order must still be proven in a "
            "new immutable 20-pose build, saved configurations and cold "
            "process reopen."
        ),
    }
    write_json_once(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "successful_variants": successful,
                "errors": {
                    item["name"]: item["final_max_abs_error"]
                    for item in results
                },
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
