"""Executed source-only mutation controls for the raw-evidence boundary."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Any, Callable
from unittest.mock import patch

import numpy as np

from .adapter import (
    AdapterError,
    COMMON_DONOR_RELATIVE_PATH,
    COMMON_DONOR_PROJECTION_SHA256,
    OUTCOME_A0,
    OUTCOME_COMMON,
    OUTCOME_NO_REMOVAL,
    aggregate_g12_raw,
    common_donor_projection,
    derive_fresh_acquisition_observation,
    evaluate_a0_bookend_raw,
    evaluate_a0_bookend_pair,
    evaluate_common_propagation_raw_triplet,
    evaluate_fresh_alpha16_raw,
    evaluate_fresh_acquisition_raw_triplet,
    evaluate_g12_raw_pair,
    load_bound_case,
)
from .fixture_factory import write_case
from .production_api import project_root as production_project_root
from .runner_guard import RunnerAuthorizationError, run_registered_vnext


NEGATIVE_CONTROL_IDS = (
    "RA-NC01-NPZ-HASH-DRIFT", "RA-NC02-NPZ-BYTES-DRIFT", "RA-NC03-ABSOLUTE-PATH",
    "RA-NC04-PATH-TRAVERSAL", "RA-NC05-PATH-ALIAS", "RA-NC06-SYMLINK-REPARSE",
    "RA-NC07-SIDECAR-EXTRA-KEY", "RA-NC08-SIDECAR-MISSING-KEY", "RA-NC09-DUPLICATE-JSON-KEY",
    "RA-NC10-NULL-JSON", "RA-NC11-NPZ-EXTRA-ARRAY", "RA-NC12-NPZ-MISSING-ARRAY",
    "RA-NC13-FLOAT32", "RA-NC14-BIG-ENDIAN", "RA-NC15-OBJECT-PICKLE", "RA-NC16-STRING-DTYPE",
    "RA-NC17-NAN", "RA-NC18-INFINITY", "RA-NC19-EMPTY-TIME", "RA-NC20-NONMONOTONIC-TIME",
    "RA-NC21-SHAPE", "RA-NC22-ACQUISITION-COUNT", "RA-NC23-REMOVAL-COUNT",
    "RA-NC24-OUTCOME-COUNT-CONTRADICTION", "RA-NC25-ACQUISITION-INDEX", "RA-NC26-REMOVAL-INDEX",
    "RA-NC27-WINDOW-END", "RA-NC28-SIDECAR-ACQUISITION-FORGERY", "RA-NC29-SIDECAR-REMOVAL-FORGERY",
    "RA-NC30-STAGE-CODE0", "RA-NC31-STAGE-WRONG-ORDER", "RA-NC32-NONFINAL-FRACTIONAL",
    "RA-NC33-FINAL-STEP-TOO-LARGE", "RA-NC34-FINAL-STEP-NONPOSITIVE", "RA-NC35-G04-REPORTED-POWER",
    "RA-NC36-G04-TERMINAL-CANCELLATION", "RA-NC37-G04-EMPTY-HISTORY", "RA-NC38-G06-STAGE-WORK-SHORTCUT",
    "RA-NC39-G06-STAGE-POWER", "RA-NC40-POST-WORK-CARRY", "RA-NC41-POST-COMMAND",
    "RA-NC42-POST-STAGE-DOMAIN", "RA-NC43-POST-P-BOUNDS", "RA-NC44-POST-JACOBIAN-OPENING-SIGN",
    "RA-NC45-POST-CONTINUOUS-CLEARANCE", "RA-NC46-POST-ZERO-JUMP", "RA-NC47-POST-5MS-HORIZON",
    "RA-NC48-G12-ONE-SIDE-FINITE", "RA-NC49-G12-BOTH-NO-EVENT-ELIGIBLE", "RA-NC50-COMMON-FRESH-CREDIT",
    "RA-NC51-UNAUTHORIZED-RUNNER", "RA-NC52-LEGACY-B4G-IMPERSONATION", "RA-NC53-SCHEDULE-INDEX",
    "RA-NC54-MATRIX-ROW-HASH", "RA-NC55-SOURCE-HASHES", "RA-NC56-ROLE-CREDIT",
    "RA-NC57-G12-NONREFERENCE-STEP", "RA-NC58-G12-RAW-REUSE-36", "RA-NC59-A0-NONZERO-WORK",
    "RA-NC60-A0-FAKE-CAPTURE-EVENT",
    "RA-NC61-POST-6MS-HORIZON", "RA-NC62-ACQUISITION-NONZERO-INDEX",
    "RA-NC63-ACTIVE-INTERVAL-LEDGER-FALSE", "RA-NC64-POST-P-REDUNDANCY",
    "RA-NC65-POSTLOAD-ARRAY-MUTATION", "RA-NC66-POSTLOAD-SIDECAR-MUTATION",
    "RA-NC67-SCHEDULE-INDEX-BOOL", "RA-NC68-TRIPLET-RAW-REUSE",
    "RA-NC69-G06-RAW-RESIDUAL-FORGERY", "RA-NC70-POST-SAMPLE-P-BOUNDS",
    "RA-NC71-ACQUISITION-TIME-BOOL", "RA-NC72-ACQUISITION-TIME-INT",
    "RA-NC73-A0-GAP-PAYLOAD-MISMATCH", "RA-NC74-A0-STAGE-PAYLOAD-MISMATCH",
    "RA-NC75-COMMON-INTERIOR-DIVERGENCE", "RA-NC76-ALPHA16-NONP-FULL-CREDIT",
    "RA-NC77-ALPHA16-CONTACT-MOMENTUM-FULL-CREDIT",
    "RA-NC78-COMMON-DONOR-INITIAL-DRIFT", "RA-NC79-COMMON-DONOR-CERTIFICATE-FORGERY",
    "RA-NC80-COMMON-DONOR-BEFORE-AFTER-DRIFT",
    "RA-NC81-G12-AGGREGATE-ONE-SIDE-FINITE",
    "RA-NC82-COMMON-DONOR-CACHE-POISON",
    "RA-NC83-COMMON-DONOR-SOURCE-DRIFT",
    "RA-NC84-G12-REPACKED-IDENTICAL-NUMERIC-PAYLOAD",
    "RA-NC85-POST-GAP-BELOW-1E-6",
    "RA-NC86-POST-GAP-RATE-BELOW-MINUS-1E-6",
)


def _expect_loader_reject(
    root: Path,
    *,
    array_mutator: Callable[[dict[str, np.ndarray]], None] | None = None,
    sidecar_mutator: Callable[[dict[str, Any]], None] | None = None,
    outcome: str = "FINITE_BILATERAL_REMOVAL_OBSERVED",
    post_write: Callable[[Path, str], None] | None = None,
) -> str:
    horizon_s = 0.08 if outcome == OUTCOME_NO_REMOVAL else 0.0025
    relative = write_case(
        root,
        array_mutator=array_mutator,
        sidecar_mutator=sidecar_mutator,
        outcome=outcome,
        horizon_s=horizon_s,
    )
    if post_write:
        post_write(root, relative)
    try:
        load_bound_case(root, relative)
    except AdapterError as exc:
        return str(exc)
    raise AssertionError("MUTATION_SURVIVED_RAW_LOADER")


def _eval_false(root: Path, mutator: Callable[[dict[str, np.ndarray]], None]) -> str:
    case = load_bound_case(root, write_case(root, array_mutator=mutator))
    result = evaluate_fresh_alpha16_raw(case)
    if result.get("g04_g06_raw_subpredicates_pass") is not False:
        raise AssertionError("MUTATION_SURVIVED_G04_G06")
    return result["status"]


def _g12_false(root: Path, mutator: Callable[[dict[str, np.ndarray]], None]) -> str:
    rk = load_bound_case(root / "rk", write_case(root / "rk", method="rk4", step_s=0.0000625, horizon_s=0.000125, array_mutator=mutator))
    mp = load_bound_case(root / "mp", write_case(root / "mp", method="midpoint", step_s=0.0000625, horizon_s=0.000125))
    result = evaluate_g12_raw_pair(rk, mp)
    if result.get("partial_post_checks_pass") is not False:
        raise AssertionError("MUTATION_SURVIVED_G12_RAW_RECOMPUTATION")
    return result["evaluation_status"]


def _controls(base: Path) -> list[Callable[[], str]]:
    return [
        lambda: _expect_loader_reject(base / "01", sidecar_mutator=lambda s: s.__setitem__("npz_sha256", "A" * 64)),
        lambda: _expect_loader_reject(base / "02", sidecar_mutator=lambda s: s.__setitem__("npz_bytes", s["npz_bytes"] + 1)),
        lambda: _expect_loader_reject(base / "03", sidecar_mutator=lambda s: s.__setitem__("npz_relative_path", "C:/raw.npz")),
        lambda: _expect_loader_reject(base / "04", sidecar_mutator=lambda s: s.__setitem__("npz_relative_path", "../raw.npz")),
        lambda: _expect_loader_reject(base / "05", post_write=_hardlink_alias),
        lambda: _expect_loader_reject(base / "06", post_write=_symlink_alias),
        lambda: _expect_loader_reject(base / "07", sidecar_mutator=lambda s: s.__setitem__("forged", True)),
        lambda: _expect_loader_reject(base / "08", sidecar_mutator=lambda s: s.pop("matrix_row_sha256")),
        lambda: _expect_loader_reject(base / "09", post_write=_duplicate_json),
        lambda: _expect_loader_reject(base / "10", post_write=_null_json),
        lambda: _expect_loader_reject(base / "11", array_mutator=lambda a: a.__setitem__("extra", np.zeros(1, dtype="<f8"))),
        lambda: _expect_loader_reject(base / "12", array_mutator=lambda a: a.pop("stage_augmented_W_act_J")),
        lambda: _expect_loader_reject(base / "13", array_mutator=lambda a: a.__setitem__("time_s", a["time_s"].astype("<f4"))),
        lambda: _expect_loader_reject(base / "14", array_mutator=lambda a: a.__setitem__("time_s", a["time_s"].astype(">f8"))),
        lambda: _expect_loader_reject(base / "15", array_mutator=lambda a: a.__setitem__("time_s", np.asarray([object()] * len(a["time_s"]), dtype=object))),
        lambda: _expect_loader_reject(base / "16", array_mutator=lambda a: a.__setitem__("time_s", np.asarray(["x"] * len(a["time_s"])))),
        lambda: _expect_loader_reject(base / "17", array_mutator=lambda a: a["time_s"].__setitem__(1, np.nan)),
        lambda: _expect_loader_reject(base / "18", array_mutator=lambda a: a["time_s"].__setitem__(1, np.inf)),
        lambda: _expect_loader_reject(base / "19", array_mutator=lambda a: a.__setitem__("time_s", np.empty(0, dtype="<f8"))),
        lambda: _expect_loader_reject(base / "20", array_mutator=lambda a: a["time_s"].__setitem__(1, a["time_s"][0])),
        lambda: _expect_loader_reject(base / "21", array_mutator=lambda a: a.__setitem__("service_state_29", a["service_state_29"][:, :28])),
        lambda: _expect_loader_reject(base / "22", array_mutator=lambda a: a["acquisition_event_count"].__setitem__((), 0)),
        lambda: _expect_loader_reject(base / "23", array_mutator=lambda a: a["bilateral_removal_event_count"].__setitem__((), 0)),
        lambda: _expect_loader_reject(base / "24", outcome=OUTCOME_NO_REMOVAL, array_mutator=lambda a: a["bilateral_removal_event_count"].__setitem__((), 1)),
        lambda: _expect_loader_reject(base / "25", array_mutator=lambda a: a["acquisition_event_sample_index"].__setitem__(0, -1)),
        lambda: _expect_loader_reject(base / "26", array_mutator=lambda a: a["bilateral_removal_active_sample_index"].__setitem__(0, 0)),
        lambda: _expect_loader_reject(base / "27", array_mutator=lambda a: a["saved_window_end_index"].__setitem__((), 0)),
        lambda: _expect_loader_reject(base / "28", sidecar_mutator=lambda s: s.__setitem__("acquisition_time_s", 9.0)),
        lambda: _expect_loader_reject(base / "29", sidecar_mutator=lambda s: s.__setitem__("removal_time_s", s["removal_time_s"] + 1e-6)),
        lambda: _expect_loader_reject(base / "30", array_mutator=lambda a: a["stage_code"].__setitem__(0, 0)),
        lambda: _expect_loader_reject(base / "31", array_mutator=lambda a: a["stage_code"].__setitem__(0, 2)),
        lambda: _expect_loader_reject(base / "32", array_mutator=lambda a: a["time_s"].__setitem__(1, a["time_s"][1] - 1e-5)),
        lambda: _expect_loader_reject(base / "33", array_mutator=lambda a: a["time_s"].__setitem__(-1, a["time_s"][-2] + 0.0003)),
        lambda: _expect_loader_reject(base / "34", array_mutator=lambda a: a["time_s"].__setitem__(-1, a["time_s"][-2])),
        lambda: _eval_false(base / "35", lambda a: a["sample_power_reported_W"].__setitem__(1, 99.0)),
        lambda: _eval_false(base / "36", lambda a: a["signed_W_act_J"].__setitem__(1, a["signed_W_act_J"][1] + 1e-3)),
        lambda: _expect_loader_reject(base / "37", array_mutator=lambda a: a.__setitem__("time_s", np.empty(0, dtype="<f8"))),
        lambda: _eval_false(base / "38", lambda a: a["stage_augmented_W_act_J"].fill(0.0)),
        lambda: _eval_false(base / "39", lambda a: a["stage_power_W"].__setitem__(0, 99.0)),
        lambda: _g12_false(base / "40", lambda a: a["post_signed_W_act_J"].__setitem__(0, 99.0)),
        lambda: _g12_false(base / "41", lambda a: a["post_command_Q_14"].__setitem__((0, 0), 1.0)),
        lambda: _g12_false(base / "42", lambda a: a["post_stage_domain_and_sign_pass"].__setitem__(0, False)),
        lambda: _g12_false(base / "43", _post_p_outside_with_redundancy),
        lambda: _g12_false(base / "44", lambda a: a["post_stage_gap_jacobian_P"].__setitem__((0, 0, 0), -1.0)),
        lambda: _g12_false(base / "45", lambda a: a["post_left_gap_m"].fill(-1e-4)),
        lambda: _g12_false(base / "46", lambda a: a["post_service_state_29"].__setitem__((0, 0), 99.0)),
        lambda: _expect_loader_reject(base / "47", array_mutator=_short_post_horizon),
        lambda: _one_side_g12(base / "48"),
        lambda: _both_no_event_g12(base / "49"),
        lambda: _common_fresh_credit(base / "50"),
        _unauthorized_runner,
        lambda: _expect_loader_reject(base / "52", array_mutator=lambda a: a.pop("sample_power_reported_W")),
        lambda: _expect_loader_reject(base / "53", sidecar_mutator=lambda s: s.__setitem__("schedule_index", 77)),
        lambda: _expect_loader_reject(base / "54", sidecar_mutator=lambda s: s.__setitem__("matrix_row_sha256", "A" * 64)),
        lambda: _expect_loader_reject(base / "55", sidecar_mutator=lambda s: s["source_hashes"].__setitem__("matrix_sha256", "A" * 64)),
        lambda: _expect_loader_reject(base / "56", sidecar_mutator=lambda s: s.__setitem__("registered_roles", ["G12_FRESH_REFERENCE"])),
        lambda: _nonreference_g12(base / "57"),
        lambda: _reused_raw_aggregate(base / "58"),
        lambda: _a0_nonzero(base / "59"),
        lambda: _expect_loader_reject(base / "60", outcome=OUTCOME_A0, array_mutator=_a0_fake_event),
        lambda: _expect_loader_reject(base / "61", array_mutator=_long_post_horizon),
        lambda: _expect_loader_reject(base / "62", array_mutator=lambda a: a["acquisition_event_sample_index"].__setitem__(0, 1)),
        lambda: _expect_loader_reject(base / "63", array_mutator=lambda a: a["active_interval_ledger_certified"].__setitem__(0, False)),
        lambda: _expect_loader_reject(base / "64", array_mutator=lambda a: a["post_stage_P_coordinates_m"].__setitem__((0, 0), 0.031)),
        lambda: _postload_array_immutable(base / "65"),
        lambda: _postload_sidecar_immutable(base / "66"),
        lambda: _expect_loader_reject(base / "67", sidecar_mutator=lambda s: s.__setitem__("schedule_index", True)),
        lambda: _triplet_raw_reuse(base / "68"),
        lambda: _eval_false(base / "69", lambda a: a["energy_minus_work_residual_J"].__setitem__(0, 1.0)),
        lambda: _g12_false(base / "70", lambda a: a["post_service_state_29"][:, 13:15].fill(0.08)),
        lambda: _expect_loader_reject(base / "71", sidecar_mutator=lambda s: s.__setitem__("acquisition_time_s", False)),
        lambda: _expect_loader_reject(base / "72", sidecar_mutator=lambda s: s.__setitem__("acquisition_time_s", 0)),
        lambda: _a0_pair_numeric_mismatch(base / "73", lambda a: a["left_gap_m"].__setitem__(0, 999.0)),
        lambda: _a0_pair_numeric_mismatch(base / "74", lambda a: a["stage_gap_jacobian_P"].__setitem__((0, 0, 0), 999.0)),
        lambda: _common_interior_divergence(base / "75"),
        lambda: _alpha_partial_credit_guard(base / "76", lambda a: a["command_Q_14"].__setitem__((0, 0), 999.0)),
        lambda: _alpha_partial_credit_guard(base / "77", lambda a: (a["contact_force_N"].__setitem__(0, 999.0), a["total_linear_momentum_N_s"].__setitem__((1, 0), 999.0))),
        lambda: _expect_common_loader_reject(base / "78", array_mutator=lambda a: a["service_state_29"].__setitem__((0, 0), 999.0)),
        lambda: _expect_common_loader_reject(base / "79", sidecar_mutator=lambda s: s.__setitem__("common_donor_certificate_sha256", "A" * 64)),
        lambda: _expect_common_loader_reject(base / "80", sidecar_mutator=lambda s: s["common_donor_hashes_after"].__setitem__("group_sha256", "A" * 64)),
        lambda: _g12_aggregate_one_side(base / "81"),
        lambda: _common_donor_cache_poison(base / "82"),
        lambda: _common_donor_source_drift(base / "83"),
        lambda: _g12_repacked_identical_numeric_payload(base / "84"),
        lambda: _g12_false(base / "85", lambda a: (a["post_left_gap_m"].fill(5.0e-7), a["left_gap_m"].__setitem__(-1, 5.0e-7))),
        lambda: _g12_false(base / "86", lambda a: (a["post_left_gap_rate_m_s"].fill(-2.0e-6), a["left_gap_rate_m_s"].__setitem__(-1, -2.0e-6))),
    ]


def _hardlink_alias(root: Path, relative: str) -> None:
    path = root / Path(relative).with_suffix(".npz")
    original = path.with_name("original.npz")
    path.replace(original)
    os.link(original, path)


def _symlink_alias(root: Path, relative: str) -> None:
    path = root / Path(relative).with_suffix(".npz")
    original = path.with_name("original_symlink_target.npz")
    path.replace(original)
    try:
        os.symlink(original, path)
    except OSError:
        os.link(original, path)


def _duplicate_json(root: Path, relative: str) -> None:
    path = root / relative
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"schema":', '"schema":"FORGED","schema":', 1), encoding="utf-8")


def _null_json(root: Path, relative: str) -> None:
    path = root / relative
    value = json.loads(path.read_text(encoding="utf-8"))
    value["forged_null"] = None
    path.write_text(json.dumps(value), encoding="utf-8")


def _short_post_horizon(arrays: dict[str, np.ndarray]) -> None:
    arrays["post_time_s"][:] = arrays["post_time_s"][0] + np.linspace(0.0, 0.004, len(arrays["post_time_s"]))
    # Keep stage time schema aligned so only the frozen 5 ms predicate kills it.
    codes = arrays["post_stage_code"]
    times: list[float] = []
    for left, right in zip(arrays["post_time_s"], arrays["post_time_s"][1:]):
        h = float(right - left)
        times.extend([float(left), float(left + 0.5 * h), float(left + 0.5 * h), float(right)])
    arrays["post_stage_time_s"][:] = times


def _long_post_horizon(arrays: dict[str, np.ndarray]) -> None:
    arrays["post_time_s"][:] = arrays["post_time_s"][0] + np.linspace(0.0, 0.006, len(arrays["post_time_s"]))
    times: list[float] = []
    for left, right in zip(arrays["post_time_s"], arrays["post_time_s"][1:]):
        h = float(right - left)
        times.extend([float(left), float(left + 0.5 * h), float(left + 0.5 * h), float(right)])
    arrays["post_stage_time_s"][:] = times


def _post_p_outside_with_redundancy(arrays: dict[str, np.ndarray]) -> None:
    arrays["post_stage_P_coordinates_m"][0, 0] = 0.08
    arrays["post_stage_service_state_29"][0, 13] = 0.08


def _postload_array_immutable(root: Path) -> str:
    case = load_bound_case(root, write_case(root))
    try:
        case.arrays["time_s"].setflags(write=True)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("POSTLOAD_ARRAY_WRITEABLE_REENABLED")


def _postload_sidecar_immutable(root: Path) -> str:
    case = load_bound_case(root, write_case(root))
    try:
        case.sidecar["source_hashes"]["matrix_sha256"] = "A" * 64
    except TypeError as exc:
        return str(exc)
    raise AssertionError("POSTLOAD_NESTED_SIDECAR_MUTATED")


def _triplet_raw_reuse(root: Path) -> str:
    case = load_bound_case(root, write_case(root, command_duration_s=0.01))
    result = evaluate_fresh_acquisition_raw_triplet([case, case, case])
    if result.get("raw_triplet_binding_evaluable") is True:
        raise AssertionError("REUSED_RAW_TRIPLET_ACCEPTED")
    return result["status"]


def _a0_pair_numeric_mismatch(root: Path, mutator: Callable[[dict[str, np.ndarray]], None]) -> str:
    pre = load_bound_case(root / "pre", write_case(root / "pre", outcome=OUTCOME_A0, horizon_s=0.0005, bookend_sentinel="PRE"))
    post = load_bound_case(root / "post", write_case(root / "post", outcome=OUTCOME_A0, horizon_s=0.0005, bookend_sentinel="POST", array_mutator=mutator))
    result = evaluate_a0_bookend_pair(pre, post)
    if result.get("source_only_candidate_predicate_pass") is not False:
        raise AssertionError("A0_INCOMPLETE_NUMERIC_PROJECTION_ACCEPTED")
    return result["status"]


def _common_interior_divergence(root: Path) -> str:
    cases = []
    for index, step in enumerate((0.00025, 0.000125, 0.0000625)):
        mutator = None
        if step == 0.0000625:
            mutator = lambda arrays: arrays["service_state_29"].__setitem__((4, 0), 1000.0)
        lane_root = root / str(index)
        cases.append(load_bound_case(
            lane_root,
            write_case(
                lane_root, step_s=step, outcome=OUTCOME_COMMON,
                horizon_s=0.005, command_duration_s=0.005, array_mutator=mutator,
            ),
        ))
    result = evaluate_common_propagation_raw_triplet(cases)
    if result.get("source_only_candidate_predicate_pass") is not False:
        raise AssertionError("COMMON_INTERIOR_DIVERGENCE_ACCEPTED")
    return result["status"]


def _alpha_partial_credit_guard(root: Path, mutator: Callable[[dict[str, np.ndarray]], None]) -> str:
    case = load_bound_case(root, write_case(root, array_mutator=mutator))
    result = evaluate_fresh_alpha16_raw(case)
    if (
        result.get("g04_g06_raw_subpredicates_pass") is not True
        or result.get("source_only_candidate_predicate_pass") is not False
        or result.get("full_raw_integrity_recomputed") is not False
    ):
        raise AssertionError("ALPHA16_PARTIAL_WORK_CHECKS_UPGRADED_TO_FULL_CREDIT")
    return result["status"]


def _expect_common_loader_reject(
    root: Path,
    *,
    array_mutator: Callable[[dict[str, np.ndarray]], None] | None = None,
    sidecar_mutator: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    relative = write_case(
        root,
        outcome=OUTCOME_COMMON,
        horizon_s=0.005,
        command_duration_s=0.005,
        array_mutator=array_mutator,
        sidecar_mutator=sidecar_mutator,
    )
    try:
        load_bound_case(root, relative)
    except AdapterError as exc:
        return str(exc)
    raise AssertionError("COMMON_DONOR_MUTATION_SURVIVED_LOADER")


def _g12_aggregate_one_side(root: Path) -> str:
    cases = []
    ordinal = 0
    for method in ("rk4", "midpoint"):
        for alpha in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0):
            for duration in (0.005, 0.01, 0.02):
                ordinal += 1
                no_event = method == "midpoint" and alpha == 0.5 and duration == 0.005
                outcome = OUTCOME_NO_REMOVAL if no_event else "FINITE_BILATERAL_REMOVAL_OBSERVED"
                horizon = 0.08 if no_event else 0.000125
                lane_root = root / str(ordinal)

                def tag(arrays: dict[str, np.ndarray], value: float = ordinal * 1e-9) -> None:
                    arrays["target_state_13"][:, 0] += value
                    arrays["post_target_state_13"][:, 0] += value
                    arrays["post_stage_target_state_13"][:, 0] += value

                cases.append(load_bound_case(
                    lane_root,
                    write_case(
                        lane_root,
                        method=method,
                        step_s=0.0000625,
                        alpha=alpha,
                        command_duration_s=duration,
                        outcome=outcome,
                        horizon_s=horizon,
                        array_mutator=tag,
                    ),
                ))
    result = aggregate_g12_raw(cases)
    if result.get("raw_registry_structurally_valid") is not True:
        raise AssertionError("CONTROL_BASELINE_36_RAW_NOT_STRUCTURALLY_VALID")
    if result.get("raw_pair_outcomes_valid") is not False or result.get("source_only_registry_valid") is not False:
        raise AssertionError("G12_AGGREGATE_ONE_SIDE_FAILURE_WAS_UPGRADED")
    return result["status"]


def _common_donor_cache_poison(root: Path) -> str:
    donor = common_donor_projection()
    blocked = 0
    try:
        donor.service_state_29[0] = 999.0
    except TypeError:
        blocked += 1
    try:
        donor.acquisition_time_s = 999.0
    except AttributeError:
        blocked += 1
    current = common_donor_projection()
    if blocked != 2 or current.projection_sha256 != COMMON_DONOR_PROJECTION_SHA256:
        raise AssertionError("COMMON_DONOR_CACHE_POISON_SURVIVED")
    case = load_bound_case(
        root,
        write_case(root, outcome=OUTCOME_COMMON, horizon_s=0.005, command_duration_s=0.005),
    )
    if float(case.arrays["time_s"][0]) != current.acquisition_time_s:
        raise AssertionError("COMMON_DONOR_RAW_CHANGED_AFTER_POISON_ATTEMPT")
    return "NO_SUCCESS_CACHE_IMMUTABLE_DONOR_PROJECTION_AND_CANONICAL_RAW_PRESERVED"


def _common_donor_source_drift(root: Path) -> str:
    case_root = root / "case"
    relative = write_case(
        case_root, outcome=OUTCOME_COMMON, horizon_s=0.005, command_duration_s=0.005,
    )
    donor_root = root / "donor_root"
    donor_root.mkdir(parents=True, exist_ok=True)
    donor_copy = donor_root / "donor.json"
    shutil.copyfile(production_project_root() / COMMON_DONOR_RELATIVE_PATH, donor_copy)
    with donor_copy.open("ab") as stream:
        stream.write(b"\n")
    from . import adapter as adapter_module
    with (
        patch.object(adapter_module, "project_root", return_value=donor_root),
        patch.object(adapter_module, "COMMON_DONOR_RELATIVE_PATH", "donor.json"),
    ):
        try:
            load_bound_case(case_root, relative)
        except AdapterError as exc:
            return str(exc)
    raise AssertionError("DRIFTED_COMMON_DONOR_SOURCE_INHERITED_STALE_SUCCESS")


def _g12_repacked_identical_numeric_payload(root: Path) -> str:
    cases = []
    ordinal = 0
    for method in ("rk4", "midpoint"):
        for alpha in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0):
            for duration in (0.005, 0.01, 0.02):
                ordinal += 1
                lane_root = root / str(ordinal)
                relative = write_case(
                    lane_root,
                    method=method,
                    step_s=0.0000625,
                    alpha=alpha,
                    command_duration_s=duration,
                    horizon_s=0.000125,
                )
                sidecar_path = lane_root / relative
                npz_path = sidecar_path.with_suffix(".npz")
                with npz_path.open("ab") as stream:
                    stream.write(f"R2_NUMERIC_REPACK_{ordinal:02d}".encode("ascii"))
                sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
                payload = npz_path.read_bytes()
                sidecar["npz_bytes"] = len(payload)
                sidecar["npz_sha256"] = hashlib.sha256(payload).hexdigest().upper()
                sidecar_path.write_text(
                    json.dumps(sidecar, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
                cases.append(load_bound_case(lane_root, relative))
    result = aggregate_g12_raw(cases)
    if result.get("source_only_registry_valid") is True:
        raise AssertionError("REPACKED_IDENTITY_NEUTRAL_NUMERIC_REUSE_ACCEPTED")
    return result["status"]


def _one_side_g12(root: Path) -> str:
    rk = load_bound_case(root / "rk", write_case(root / "rk", method="rk4", step_s=0.0000625, horizon_s=0.000125))
    mp = load_bound_case(root / "mp", write_case(root / "mp", method="midpoint", step_s=0.0000625, horizon_s=0.08, outcome=OUTCOME_NO_REMOVAL))
    status = evaluate_g12_raw_pair(rk, mp)["evaluation_status"]
    if not status.startswith("FAIL_G12_ONE_SIDE"):
        raise AssertionError("ONE_SIDE_FINITE_WAS_NOT_FAILED")
    return status


def _both_no_event_g12(root: Path) -> str:
    rk = load_bound_case(root / "rk", write_case(root / "rk", method="rk4", step_s=0.0000625, horizon_s=0.08, outcome=OUTCOME_NO_REMOVAL))
    mp = load_bound_case(root / "mp", write_case(root / "mp", method="midpoint", step_s=0.0000625, horizon_s=0.08, outcome=OUTCOME_NO_REMOVAL))
    result = evaluate_g12_raw_pair(rk, mp)
    if result["eligible"] is not False or result["applicability"] != "NOT_APPLICABLE":
        raise AssertionError("BOTH_NO_EVENT_BECAME_ELIGIBLE")
    return result["evaluation_status"]


def _common_fresh_credit(root: Path) -> str:
    case = load_bound_case(root, write_case(root, outcome=OUTCOME_COMMON, horizon_s=0.005, command_duration_s=0.005))
    try:
        derive_fresh_acquisition_observation(case)
    except AdapterError as exc:
        return str(exc)
    raise AssertionError("COMMON_RAW_RECEIVED_FRESH_CREDIT")


def _unauthorized_runner() -> str:
    try:
        run_registered_vnext()
    except RunnerAuthorizationError as exc:
        return str(exc)
    raise AssertionError("UNAUTHORIZED_RUNNER_SUCCEEDED")


def _nonreference_g12(root: Path) -> str:
    case = load_bound_case(root, write_case(root, method="rk4", step_s=0.00025))
    result = evaluate_g12_raw_pair(case, case)
    if result.get("raw_pair_binding_evaluable") is True:
        raise AssertionError("NONREFERENCE_G12_ROLE_ACCEPTED")
    return result["evaluation_status"]


def _reused_raw_aggregate(root: Path) -> str:
    case = load_bound_case(root, write_case(root, method="rk4", step_s=0.0000625, horizon_s=0.000125))
    result = aggregate_g12_raw([case] * 36)
    if result.get("source_only_registry_valid") is True:
        raise AssertionError("REUSED_RAW_REGISTRY_ACCEPTED")
    return result["status"]


def _a0_nonzero(root: Path) -> str:
    case = load_bound_case(root, write_case(root, outcome=OUTCOME_A0, horizon_s=0.0005, array_mutator=lambda a: a["signed_W_act_J"].__setitem__(0, 1.0)))
    result = evaluate_a0_bookend_raw(case)
    if result["source_only_candidate_predicate_pass"] is not False:
        raise AssertionError("A0_NONZERO_WORK_ACCEPTED")
    return result["status"]


def _a0_fake_event(arrays: dict[str, np.ndarray]) -> None:
    arrays["acquisition_event_count"][()] = 1


def run_all_negative_controls(package_root: Path) -> dict[str, Any]:
    with TemporaryDirectory(prefix=".r2_raw_nc_", dir=package_root) as directory:
        base = Path(directory)
        controls = _controls(base)
        if len(controls) != len(NEGATIVE_CONTROL_IDS):
            raise RuntimeError("NEGATIVE_CONTROL_IMPLEMENTATION_COUNT_DRIFT")
        records: list[dict[str, Any]] = []
        for control_id, control in zip(NEGATIVE_CONTROL_IDS, controls):
            try:
                witness = control()
                records.append({"id": control_id, "status": "KILLED_SOURCE_ONLY", "witness": witness})
            except Exception as exc:  # fail closed; freeze refuses any error record
                records.append({"id": control_id, "status": "CONTROL_ERROR", "witness": f"{type(exc).__name__}:{exc}"})
    killed = sum(record["status"] == "KILLED_SOURCE_ONLY" for record in records)
    return {
        "schema": "SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_ONLY_NEGATIVE_CONTROLS_V1",
        "registered_count": len(NEGATIVE_CONTROL_IDS),
        "executed_count": len(records),
        "killed_count": killed,
        "all_killed": killed == len(NEGATIVE_CONTROL_IDS),
        "records": records,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
    }


__all__ = ["NEGATIVE_CONTROL_IDS", "run_all_negative_controls"]
