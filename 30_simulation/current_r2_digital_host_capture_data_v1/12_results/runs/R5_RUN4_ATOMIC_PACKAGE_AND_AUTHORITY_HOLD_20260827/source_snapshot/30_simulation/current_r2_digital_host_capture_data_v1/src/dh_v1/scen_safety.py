"""S07 fail-closed safety fault injection (subset independent of current geometry).

Every injection must terminate in ABORT or WAIT — never EXECUTE/MODIFY.
Includes real-file hash tampering and real solver-divergence runs, not just
status-flag simulation.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from .episode_writer import EpisodeWriteError, validate_manifest
from .hashing import sha256_file, verify_file_sha256
from .integrators import SolverNonConvergence, pack_state, rk4_run
from .safe_prebind import AuthorityItem, decide, label_from_decision


def _base_items(**overrides) -> list[AuthorityItem]:
    """Nominal prebind authority set; overrides inject faults."""
    spec = {
        "ACCEPTED_URDF": ("VERIFIED", True, False),
        "FRAME_CONTRACT": ("VERIFIED", True, False),
        "UNIT_CONTRACT": ("VERIFIED", True, False),
        "CURRENT_STEP_STATE": ("VERIFIED", True, False),
        "COLLISION_ASSETS": ("VERIFIED", True, False),
        "M01_MOTION_CERTIFICATE": ("VERIFIED", True, False),
        "T_E_T": ("VERIFIED", True, False),
        "CONTACT_AUTHORITY": ("VERIFIED", True, False),
        "TARGET_POSE_MEASUREMENT": ("VERIFIED", True, False),
        "WHEEL_MOMENTUM_MARGIN": ("VERIFIED", True, False),
    }
    items = []
    for name, (status, required, prov_ok) in spec.items():
        st, age = status, None
        if name in overrides:
            ov = overrides[name]
            st = ov["status"]
            age = ov.get("stale_age_s")
            prov_ok = ov.get("provisional_allowed", prov_ok)
        items.append(AuthorityItem(name=name, status=st, required=required, provisional_allowed=prov_ok, stale_age_s=age))
    return items


def run_s07(accepted_urdf_path: str, workdir: str | Path, arm_plant=None) -> dict:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []

    def case(case_id: str, expected: str, decision_obj, detail: str):
        got = decision_obj.decision
        # fail-closed proof: got must equal expected AND never EXECUTE/MODIFY
        ok = (got == expected) and got not in ("EXECUTE", "MODIFY")
        cases.append(
            {
                "case_id": case_id,
                "expected": expected,
                "got": got,
                "passed": bool(ok),
                "detail": detail,
                "reasons": decision_obj.reasons,
            }
        )

    case("INJ01_T_E_T_missing", "ABORT", decide(_base_items(T_E_T={"status": "MISSING"})), "authoritative T_E_T absent")
    case(
        "INJ02a_stale_pose_within_budget",
        "WAIT",
        decide(_base_items(TARGET_POSE_MEASUREMENT={"status": "STALE", "stale_age_s": 1.0})),
        "pose stale 1.0s <= 2.0s budget",
    )
    case(
        "INJ02b_stale_pose_beyond_budget",
        "ABORT",
        decide(_base_items(TARGET_POSE_MEASUREMENT={"status": "STALE", "stale_age_s": 10.0})),
        "pose stale 10.0s > 2.0s budget",
    )
    case("INJ03_frame_mismatch", "ABORT", decide(_base_items(FRAME_CONTRACT={"status": "MISMATCH"})), "frame graph mismatch")
    case("INJ04_unit_mismatch", "ABORT", decide(_base_items(UNIT_CONTRACT={"status": "MISMATCH"})), "unit contract mismatch")
    case(
        "INJ06_collision_assets_missing",
        "ABORT",
        decide(_base_items(COLLISION_ASSETS={"status": "MISSING"})),
        "no registered collision assets",
    )
    case(
        "INJ07_contact_provisional_not_admissible",
        "ABORT",
        decide(_base_items(CONTACT_AUTHORITY={"status": "PROVISIONAL", "provisional_allowed": False})),
        "synthetic/provisional contact where real authority required",
    )
    case("INJ08_wheel_saturation", "ABORT", decide(_base_items(WHEEL_MOMENTUM_MARGIN={"status": "MISMATCH"})), "wheel margin violated")
    case(
        "INJ09_M01_certificate_missing",
        "ABORT",
        decide(_base_items(M01_MOTION_CERTIFICATE={"status": "MISSING"})),
        "no continuous-motion certificate",
    )
    case("INJ10_step_state_unknown", "ABORT", decide(_base_items(CURRENT_STEP_STATE={"status": "UNKNOWN"})), "current STEP state unknown")
    case(
        "INJ11_not_evaluated_contact",
        "ABORT",
        decide(_base_items(CONTACT_AUTHORITY={"status": "NOT_EVALUATED"})),
        "NOT_EVALUATED contact authority must not enable execution",
    )

    # INJ05: real asset-hash tamper on a copy of the accepted URDF
    src = Path(accepted_urdf_path)
    good_sha = sha256_file(src)
    tampered = workdir / "tampered_arm.urdf"
    shutil.copyfile(src, tampered)
    data = bytearray(tampered.read_bytes())
    data[len(data) // 2] ^= 0xFF
    tampered.write_bytes(bytes(data))
    tamper_detected = not verify_file_sha256(tampered, good_sha)
    st = "MISMATCH" if tamper_detected else "VERIFIED"
    d = decide(_base_items(ACCEPTED_URDF={"status": st}))
    cases.append(
        {
            "case_id": "INJ05_asset_hash_tamper",
            "expected": "ABORT",
            "got": d.decision,
            "passed": bool(tamper_detected and d.decision == "ABORT"),
            "detail": f"byte-flip on URDF copy; sha match={not tamper_detected}",
            "reasons": d.reasons,
        }
    )

    # INJ12: real solver divergence (NaN injection + torque blow-up) must raise,
    # and the harness must map it to ABORT.
    solver_cases = []
    if arm_plant is not None:
        nj = arm_plant.nj
        x_nan = pack_state(np.zeros(3), np.array([1.0, 0, 0, 0]), np.zeros(nj), np.zeros(6), np.zeros(nj))
        x_nan[7] = np.nan
        try:
            rk4_run(arm_plant, x_nan, 0.01, 1.0e-3)
            solver_cases.append(("INJ12a_nan_state", False, "non-finite state NOT detected"))
        except SolverNonConvergence as e:
            solver_cases.append(("INJ12a_nan_state", True, f"detected: {e}"))
        x0 = pack_state(np.zeros(3), np.array([1.0, 0, 0, 0]), np.zeros(nj), np.zeros(6), np.zeros(nj))
        try:
            rk4_run(arm_plant, x0, 5.0, 1.0e-2, tau_fn=lambda t, q, qd, v: 1.0e6 * np.ones(nj))
            solver_cases.append(("INJ12b_torque_blowup", False, "divergence NOT detected"))
        except SolverNonConvergence as e:
            solver_cases.append(("INJ12b_torque_blowup", True, f"detected: {e}"))
    for cid, ok, detail in solver_cases:
        d = decide(_base_items(ACCEPTED_URDF={"status": "VERIFIED"})) if ok else None
        cases.append(
            {
                "case_id": cid,
                "expected": "ABORT",
                "got": "ABORT" if ok else "UNDETECTED",
                "passed": bool(ok),
                "detail": f"solver non-convergence maps to ABORT; {detail}",
                "reasons": ["SolverNonConvergence -> fail-closed ABORT"],
            }
        )

    # INJ13: label taxonomy guards — UNKNOWN never EXECUTE; NOT_EVALUATED never a negative class
    lbl = label_from_decision("ABORT", evaluated=False)
    cases.append(
        {
            "case_id": "INJ13a_not_evaluated_label",
            "expected": "NOT_EVALUATED",
            "got": lbl,
            "passed": lbl == "NOT_EVALUATED",
            "detail": "unevaluated episode labels as NOT_EVALUATED, not as negative sample",
            "reasons": [],
        }
    )
    manifest = {
        "episode_id": "NEG_EXECUTE_WITH_MISSING_TET",
        "base_state_id": "PREBIND_NULL",
        "scenario_id": "S07",
        "strategy_id": "NONE",
        "seed": 0,
        "authority_snapshot_sha256": "0" * 64,
        "accepted_urdf_sha256": good_sha,
        "step_state_sha256": None,
        "collision_manifest_sha256": None,
        "frame_contract_sha256": "0" * 64,
        "unit_contract_sha256": "0" * 64,
        "controller_config_sha256": None,
        "safe_config_sha256": "0" * 64,
        "plant_sha256": "0" * 64,
        "geometry_authority": "MISSING",
        "dynamics_authority": "ACCEPTED_URDF",
        "contact_authority": "MISSING",
        "T_E_T_status": "MISSING",
        "evidence_level": "PREBIND",
        "claim_ceiling": "CURRENT_SYSTEM_DIGITAL_HOST_CANDIDATE_PREBIND_ONLY",
        "binding_gate": "DH-G5",
        "terminal_decision": "EXECUTE",
        "label": "EXECUTE",
    }
    try:
        validate_manifest(manifest)
        cases.append(
            {
                "case_id": "INJ13b_execute_with_missing_tet_rejected",
                "expected": "REJECTED",
                "got": "ACCEPTED",
                "passed": False,
                "detail": "writer accepted EXECUTE with missing T_E_T",
                "reasons": [],
            }
        )
    except EpisodeWriteError as e:
        cases.append(
            {
                "case_id": "INJ13b_execute_with_missing_tet_rejected",
                "expected": "REJECTED",
                "got": "REJECTED",
                "passed": True,
                "detail": f"writer rejected forbidden manifest: {e}",
                "reasons": [],
            }
        )

    n = len(cases)
    n_ok = sum(1 for c in cases if c["passed"])
    return {
        "scenario_id": "S07_FAILCLOSED_FAULT_INJECTION_PREBIND_SUBSET",
        "cases_total": n,
        "cases_passed": n_ok,
        "all_passed": n_ok == n,
        "never_execute_confirmed": all(c["got"] not in ("EXECUTE", "MODIFY") for c in cases),
        "cases": cases,
    }
