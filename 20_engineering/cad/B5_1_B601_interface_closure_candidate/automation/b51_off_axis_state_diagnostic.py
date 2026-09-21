"""Read-only diagnostic for solver state after B5.1 off-axis rejection tests."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import b51_build_articulated_segment_chain as chainmod  # noqa: E402
import b51_pose_write_order_diagnostic as orderdiag  # noqa: E402

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
    / "B51_T003_OFF_AXIS_STATE_DIAGNOSTIC.json"
)
Q_TEST = list(orderdiag.Q_TEST)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def open_maps(session: core.SolidWorksSession) -> tuple[Any, ...]:
    model, open_record = session.open_document(ASSEMBLY_PATH, "assembly")
    if open_record["warnings"] not in (None, 0):
        raise core.Phase0Error(f"diagnostic open warnings: {open_record}")
    assembly = session.cast(model, "IAssemblyDoc")
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("initial rebuild failed")
    segments = chainmod._map_reopened_segments(session, assembly, 6)
    visuals, _, _ = chainmod._nested_map(session, segments, 6)
    return model, assembly, segments, visuals, open_record


def exercise_constraints(
    session: core.SolidWorksSession,
    model: Any,
    segments: dict[str, Any],
    visuals: dict[str, Any],
    chain: dict[str, Any],
) -> dict[str, Any]:
    directions, summary = chainmod._exercise_q0_directions(
        session,
        model,
        segments,
        visuals,
        chain,
        6,
        delta_rad=chainmod.BUILD_SIGN_DELTA_RAD,
        phase="STATE_DIAGNOSTIC",
    )
    off_axis = [
        chainmod._off_axis_drive(
            session,
            model,
            segments,
            visuals,
            chain,
            6,
            index,
        )
        for index in range(1, 7)
    ]
    return {
        "direction_summary": summary,
        "direction_count": len(directions),
        "off_axis_count": len(off_axis),
        "off_axis_max_errors": [
            item["readback_after_rejection"]["max_abs_error"]
            for item in off_axis
        ],
    }


def random_write(
    session: core.SolidWorksSession,
    model: Any,
    assembly: Any,
    segments: dict[str, Any],
    visuals: dict[str, Any],
    chain: dict[str, Any],
) -> dict[str, Any]:
    expected = chainmod._fk_unbounded(chain, Q_TEST, 6)
    initial_suspend = bool(assembly.EnableAssemblyRebuild)
    if initial_suspend:
        raise core.Phase0Error(
            "unexpected suspended rebuild state before diagnostic write"
        )
    writes: list[dict[str, Any]] = []
    try:
        assembly.EnableAssemblyRebuild = True
        for index in range(1, 7):
            role = f"link{index}"
            target = expected[role]
            segments[role].Transform2 = (
                chainmod.legacy._math_transform(session, target)
            )
            actual = chainmod.legacy._component_array(segments[role])
            target_array = chainmod.legacy._matrix_array(target)
            writes.append(
                {
                    "role": role,
                    "immediate_max_abs_error": (
                        chainmod.legacy._max_error(
                            actual, target_array
                        )
                    ),
                }
            )
        pre_rebuild = chainmod._verify_pose(
            segments, visuals, expected, 6, tolerance=1.0
        )
    finally:
        assembly.EnableAssemblyRebuild = False
    if bool(assembly.EnableAssemblyRebuild):
        raise core.Phase0Error(
            "diagnostic rebuild remained suspended after write"
        )
    rebuild_ok = bool(model.ForceRebuild3(True))
    post_rebuild = chainmod._verify_pose(
        segments, visuals, expected, 6, tolerance=1.0
    )
    return {
        "write": {
            "order": list(range(1, 7)),
            "writes": writes,
            "rebuild_suspension_before": initial_suspend,
            "rebuild_suspension_during": True,
            "rebuild_suspension_after": bool(
                assembly.EnableAssemblyRebuild
            ),
            "rebuild_ok": rebuild_ok,
        },
        "pre_rebuild_readback": pre_rebuild,
        "post_rebuild_readback": post_rebuild,
        "pre_pass": pre_rebuild["max_abs_error"] <= 2.0e-7,
        "post_pass": post_rebuild["max_abs_error"] <= 2.0e-7,
        "pass": (
            pre_rebuild["max_abs_error"] <= 2.0e-7
            and post_rebuild["max_abs_error"] <= 2.0e-7
        ),
    }


def run_variant(
    session: core.SolidWorksSession,
    chain: dict[str, Any],
    *,
    name: str,
    recovery: str,
) -> dict[str, Any]:
    model, assembly, segments, visuals, open_record = open_maps(session)
    constraint_result = exercise_constraints(
        session, model, segments, visuals, chain
    )
    recovery_record: dict[str, Any]
    if recovery == "NONE":
        recovery_record = {"method": "NONE"}
    elif recovery == "EXPLICIT_Q0":
        recovery_record = {
            "method": "EXPLICIT_Q0_COORDINATED_RESET",
            "result": chainmod._apply_exact_pose(
                session,
                model,
                segments,
                visuals,
                chain,
                [0.0] * 6,
                6,
                "STATE_DIAGNOSTIC_Q0_RESET",
            ),
        }
    elif recovery == "DOCUMENT_REOPEN":
        session.close_all_documents()
        model, assembly, segments, visuals, reopen = open_maps(session)
        recovery_record = {
            "method": "READ_ONLY_DOCUMENT_REOPEN",
            "open": reopen,
        }
    else:
        raise ValueError(recovery)
    result = random_write(
        session,
        model,
        assembly,
        segments,
        visuals,
        chain,
    )
    session.close_all_documents()
    return {
        "name": name,
        "open": open_record,
        "constraint_sequence": constraint_result,
        "recovery": recovery_record,
        "random_pose": result,
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"append-only output already exists: {OUTPUT}")
    if not ASSEMBLY_PATH.is_file():
        raise RuntimeError(f"source assembly missing: {ASSEMBLY_PATH}")
    chain = chainmod.legacy._parse_urdf()
    chainmod._validate_q_vector_limits(chain, Q_TEST, 6)
    variants = []
    with core.SolidWorksSession(RUN_ROOT, visible=False) as session:
        session_start = session.info()
        for name, recovery in (
            ("NO_RECOVERY_AFTER_OFF_AXIS", "NONE"),
            ("EXPLICIT_Q0_AFTER_OFF_AXIS", "EXPLICIT_Q0"),
            ("DOCUMENT_REOPEN_AFTER_OFF_AXIS", "DOCUMENT_REOPEN"),
        ):
            variants.append(
                run_variant(
                    session, chain, name=name, recovery=recovery
                )
            )
    passing = [
        item["name"]
        for item in variants
        if item["random_pose"]["pass"]
    ]
    payload = {
        "schema": "SER_B51_T003_OFF_AXIS_STATE_DIAGNOSTIC_V1",
        "generated_utc": utc_now(),
        "status": (
            "SOLVER_STATE_RECOVERY_CANDIDATE_FOUND"
            if passing
            else "SOLVER_STATE_RECOVERY_VARIANTS_ALL_FAIL"
        ),
        "source_run": "B51_SEGMENT_CHAIN_6R_20260728T003",
        "source_open_mode": "READ_ONLY_NO_SAVE",
        "q_test_rad": Q_TEST,
        "session_start": session_start,
        "session_end": session.info(),
        "variants": variants,
        "passing_variants": passing,
        "claim_limit": (
            "Diagnostic only. Any recovery method still requires a new "
            "immutable 20-pose build and independent-process reopen."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "passing_variants": passing,
                "errors": {
                    item["name"]: item["random_pose"][
                        "post_rebuild_readback"
                    ][
                        "max_abs_error"
                    ]
                    for item in variants
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
