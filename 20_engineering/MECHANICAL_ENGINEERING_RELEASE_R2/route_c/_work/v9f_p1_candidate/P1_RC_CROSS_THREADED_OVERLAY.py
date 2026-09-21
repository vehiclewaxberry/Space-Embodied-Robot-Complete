#!/usr/bin/env python3
"""Non-authoritative P1 acceleration candidate for the V9F FULL evaluator.

This file never edits the active evaluator.  It reads one hash-pinned P0
source, mechanically lifts only the Route-C-hardware cross-clearance outer
q-loop into an ordered thread map, and writes any explicitly requested trial
outputs inside this candidate directory.

Default invocation performs static and synthetic self-tests only::

    python -B P1_RC_CROSS_THREADED_OVERLAY.py --self-test

The FULL candidate is deliberately guarded and was not run during creation.
It has no Gate/release authority until an independent dynamic field-by-field
comparison against the sequential P0 FULL output is complete.
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
from typing import Any, Callable, Iterable, Sequence, TypeVar

import numpy as np
import yaml


T = TypeVar("T")
R = TypeVar("R")

CANDIDATE_DIR = Path(__file__).resolve().parent
ROUTE_C_DIR = CANDIDATE_DIR.parents[1]
ACTIVE_EVALUATOR = ROUTE_C_DIR / "ROUTE_C_EXACT_SWEEP_V9F.py"

EXPECTED_ACTIVE_SHA256 = (
    "9F26AC9A8DE5E2EEB57103F07B769EB43AC30A8FBAFD90FE8DF5D501FA8C8A7F"
)
EXPECTED_RC_LOOP_SHA256 = (
    "5C871E440D66F8548DF9EDADF0F3C09CA5398943442D3F114488376D1FC0018D"
)
EXPECTED_RUN_MISSION_SHA256 = (
    "DF97E02A4B37A43A5D8541D4CC4A85E8AF83860023B8829112AEF268206309A9"
)
EXPECTED_MISSION_CONTRACT_SHA256 = (
    "C06A40DE171F0517ACB34CCC14C918A9A4252F7B55A425B2CBAC95229B44A98A"
)

RC_LOOP_START = "        for q in mission_q_samples:\n"
RC_LOOP_END = (
    "        note(\"RC cross-clearance worst %.3f mm over %d evals\" "
    "% (rc_worst, rc_evals))\n"
)
BASE_LOOKUP_LINE = "            base = _base_kinematics(q)\n"
RUN_MISSION_START = "    def run_mission(max_step):\n"
RUN_MISSION_END = "    note(\"running mission sweep (nominal step)...\")\n"
MISSION_RESULT_LINE = "                r = eval_clearance(q)\n"
MISSION_BATCH_LINE = (
    "            p1_mission_results = _p1_eval_batch(\n"
    "                eval_clearance, _base_kinematics, eval_cache,\n"
    "                _q_round12_key, qa)\n"
)
EVAL_CACHE_PROLOGUE = (
    "        cache_key = (bool(pinch_only),) + _q_round12_key(q)\n"
    "        if cache_key in eval_cache:\n"
    "            return eval_cache[cache_key]\n"
    "        base = _base_kinematics(q)\n"
)
EVAL_CACHE_PROLOGUE_P1 = (
    "        cache_key = (bool(pinch_only),) + _q_round12_key(q)\n"
    "        if not _p1_worker_active() and cache_key in eval_cache:\n"
    "            return eval_cache[cache_key]\n"
    "        base = _p1_base_or_frozen(q, _base_kinematics)\n"
)
EVAL_CACHE_WRITE = "        eval_cache[cache_key] = result\n"
EVAL_CACHE_WRITE_P1 = (
    "        if not _p1_worker_active():\n"
    "            eval_cache[cache_key] = result\n"
)
AUTHORITY_LINE = "    authoritative = not FAST_MODE\n"
NONAUTHORITY_LINE = (
    "    authoritative = False  # P1 overlay is non-authoritative pending exact comparison\n"
)

OUT_SWEEP = CANDIDATE_DIR / "ROUTE_C_EXACT_SWEEP_V9F_P1_CANDIDATE.json"
OUT_LEDGER = CANDIDATE_DIR / "ROUTE_C_ROBUST_MARGIN_LEDGER_V9F_P1_CANDIDATE.csv"
OUT_GATE = CANDIDATE_DIR / "ROUTE_C_MISSION_COVERAGE_GATE_V9F_P1_CANDIDATE.json"
OUT_RECEIPT = CANDIDATE_DIR / "P1_CANDIDATE_EXECUTION_RECEIPT.json"
EXTERNAL_MANIFEST = CANDIDATE_DIR / "P1_CANDIDATE_MANIFEST.json"
MISSION_CONTRACT = (
    ROUTE_C_DIR.parents[1]
    / "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    / "ecr_b601_harness_rated_envelope"
    / "04_mission"
    / "B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml"
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _read_pinned_source() -> tuple[bytes, str]:
    data = ACTIVE_EVALUATOR.read_bytes()
    digest = _sha256_bytes(data)
    if digest != EXPECTED_ACTIVE_SHA256:
        raise RuntimeError(
            "active evaluator hash drift: expected %s, got %s"
            % (EXPECTED_ACTIVE_SHA256, digest)
        )
    source = data.decode("utf-8")
    if "\r\n" in source:
        raise RuntimeError("active evaluator newline drift: LF source required")
    return data, source


def _extract_rc_loop(source: str) -> tuple[int, int, str]:
    scope_anchor = source.index("running RC hardware cross-clearance")
    start = source.index(RC_LOOP_START, scope_anchor)
    end = source.index(RC_LOOP_END, start)
    block = source[start:end]
    digest = _sha256_bytes(block.encode("utf-8"))
    if digest != EXPECTED_RC_LOOP_SHA256:
        raise RuntimeError(
            "RC cross-loop drift: expected %s, got %s"
            % (EXPECTED_RC_LOOP_SHA256, digest)
        )
    if block.count(BASE_LOOKUP_LINE) != 1:
        raise RuntimeError("RC cross-loop base lookup count is not exactly one")
    return start, end, block


def _extract_run_mission(source: str) -> tuple[int, int, str]:
    start = source.index(RUN_MISSION_START)
    end = source.index(RUN_MISSION_END, start)
    block = source[start:end]
    digest = _sha256_bytes(block.encode("utf-8"))
    if digest != EXPECTED_RUN_MISSION_SHA256:
        raise RuntimeError(
            "run_mission drift: expected %s, got %s"
            % (EXPECTED_RUN_MISSION_SHA256, digest)
        )
    if block.count(MISSION_RESULT_LINE) != 1:
        raise RuntimeError("run_mission eval result line count is not exactly one")
    return start, end, block


def _rename_rc_accumulators(text: str) -> str:
    replacements = {
        "rc_worst": "local_rc_worst",
        "rc_rec": "local_rc_rec",
        "rc_evals": "local_rc_evals",
    }
    for old, new in replacements.items():
        text = re.sub(r"\b%s\b" % re.escape(old), new, text)
    return text


def transform_source(source: str) -> tuple[str, dict[str, Any]]:
    """Return a deterministic source overlay and its mechanical audit facts.

    The q-specific body is copied byte-for-byte from the pinned evaluator,
    except for three accumulator identifier renames.  Per-q operation order,
    obstacle order, candidate masks, signed-distance kernels, argmin calls and
    strict-less-than tie handling therefore remain unchanged.
    """

    mission_start, mission_end, original_mission_block = _extract_run_mission(source)
    if original_mission_block.count("            seg_where = None\n") != 1:
        raise RuntimeError("run_mission insertion anchor drift")
    mission_block = original_mission_block.replace(
        "            seg_where = None\n",
        "            seg_where = None\n" + MISSION_BATCH_LINE,
        1,
    ).replace(MISSION_RESULT_LINE, "                r = p1_mission_results[k]\n", 1)
    transformed = (
        source[:mission_start] + mission_block + source[mission_end:]
    )

    if transformed.count(EVAL_CACHE_PROLOGUE) != 1:
        raise RuntimeError("eval_clearance cache/base prologue drift")
    if transformed.count(EVAL_CACHE_WRITE) != 1:
        raise RuntimeError("eval_clearance cache write count drift")
    transformed = transformed.replace(
        EVAL_CACHE_PROLOGUE, EVAL_CACHE_PROLOGUE_P1, 1
    ).replace(EVAL_CACHE_WRITE, EVAL_CACHE_WRITE_P1, 1)

    start, end, original_block = _extract_rc_loop(transformed)
    body = original_block[len(RC_LOOP_START) :]
    if not body.startswith(BASE_LOOKUP_LINE):
        raise RuntimeError("unexpected RC cross-loop prologue")
    body = body[len(BASE_LOOKUP_LINE) :]
    body = _rename_rc_accumulators(body)

    worker_block = (
        "        def _p1_rc_cross_one_q(item):\n"
        "            q, base = item\n"
        "            local_rc_worst = math.inf\n"
        "            local_rc_rec = None\n"
        "            local_rc_evals = 0\n"
        + body
        + "            return local_rc_worst, local_rc_rec, local_rc_evals\n"
        "\n"
        "        # Base kinematics are built sequentially in the frozen q order.\n"
        "        # Thread workers receive immutable/read-only state and fields.\n"
        "        p1_rc_items = [(q, _base_kinematics(q))\n"
        "                       for q in mission_q_samples]\n"
        "        p1_rc_results = _p1_ordered_map(_p1_rc_cross_one_q, p1_rc_items)\n"
        "        for local_rc_worst, local_rc_rec, local_rc_evals in p1_rc_results:\n"
        "            rc_evals += int(local_rc_evals)\n"
        "            # Strict < preserves the sequential first-hit tie winner.\n"
        "            if local_rc_worst < rc_worst:\n"
        "                rc_worst = local_rc_worst\n"
        "                rc_rec = local_rc_rec\n"
    )
    transformed = transformed[:start] + worker_block + transformed[end:]

    if transformed.count(AUTHORITY_LINE) != 1:
        raise RuntimeError("authority assignment count drift")
    transformed = transformed.replace(AUTHORITY_LINE, NONAUTHORITY_LINE, 1)

    audit = {
        "active_source_sha256": _sha256_bytes(source.encode("utf-8")),
        "original_rc_loop_sha256": _sha256_bytes(original_block.encode("utf-8")),
        "original_run_mission_sha256": _sha256_bytes(
            original_mission_block.encode("utf-8")
        ),
        "transformed_source_sha256": _sha256_bytes(transformed.encode("utf-8")),
        "rc_loop_replacements": 1,
        "mission_outer_loop_replacements": 1,
        "eval_cache_worker_isolation_replacements": 2,
        "authority_demotion_replacements": 1,
        "scientific_constant_edits": 0,
        "sampling_rule_edits": 0,
        "threshold_edits": 0,
    }
    return transformed, audit


def ordered_map(
    fn: Callable[[T], R], items: Sequence[T], workers: int
) -> list[R]:
    """Ordered, fail-propagating thread map used by the source overlay."""

    if workers < 1:
        raise ValueError("workers must be >= 1")
    if workers == 1:
        return [fn(item) for item in items]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="v9f-p1") as pool:
        # Executor.map yields in input order.  Any worker exception propagates
        # while materialising this list; no reducer/output is then accepted.
        return list(pool.map(fn, items, chunksize=1))


_P1_THREAD_STATE = threading.local()
_P1_CACHE_MISS = object()


def _worker_active() -> bool:
    return bool(getattr(_P1_THREAD_STATE, "active", False))


def _base_or_frozen(q: Any, fallback: Callable[[Any], Any]) -> Any:
    if not _worker_active():
        return fallback(q)
    actual = np.ascontiguousarray(np.asarray(q, dtype=float)).tobytes()
    expected = getattr(_P1_THREAD_STATE, "q_bytes", None)
    if expected is None or actual != expected:
        raise RuntimeError("P1 mission worker q/base binding mismatch")
    base = getattr(_P1_THREAD_STATE, "base", None)
    if base is None:
        raise RuntimeError("P1 mission worker missing frozen base")
    return base


def mission_eval_batch(
    eval_fn: Callable[[Any], Any],
    base_fn: Callable[[Any], Any],
    eval_cache: dict[Any, Any],
    key_fn: Callable[[Any], tuple[Any, ...]],
    qa: Sequence[Any],
    workers: int,
) -> list[Any]:
    """Evaluate one mission segment in parallel without shared cache writes.

    Cache lookup and base construction occur sequentially in frozen q order.
    Workers receive an exact q/base pair through thread-local storage and the
    transformed evaluator suppresses cache reads/writes while active.  Results
    are returned in q order, then committed to eval_cache in that same order.
    """

    items: list[tuple[Any, Any, Any, bool]] = []
    cache_keys: list[Any] = []
    for q_raw in qa:
        q = np.asarray(q_raw, dtype=float)
        cache_key = (False,) + tuple(key_fn(q))
        cached = eval_cache.get(cache_key, _P1_CACHE_MISS)
        if cached is _P1_CACHE_MISS:
            base = base_fn(q)
            items.append((q, base, None, False))
        else:
            items.append((q, None, cached, True))
        cache_keys.append(cache_key)

    def invoke(item: tuple[Any, Any, Any, bool]) -> Any:
        q, base, cached, is_cached = item
        if is_cached:
            return cached
        _P1_THREAD_STATE.active = True
        _P1_THREAD_STATE.q_bytes = np.ascontiguousarray(q).tobytes()
        _P1_THREAD_STATE.base = base
        try:
            return eval_fn(q)
        finally:
            for attr in ("base", "q_bytes", "active"):
                if hasattr(_P1_THREAD_STATE, attr):
                    delattr(_P1_THREAD_STATE, attr)

    results = ordered_map(invoke, items, workers)
    if len(results) != len(cache_keys):
        raise RuntimeError("P1 mission ordered-map cardinality mismatch")
    for cache_key, result in zip(cache_keys, results):
        eval_cache[cache_key] = result
    return results


def _reduce_rc_results(
    results: Iterable[tuple[float, Any, int]]
) -> tuple[float, Any, int]:
    """Frozen sequential reducer: strict < and exact integer count sum."""

    worst = math.inf
    record = None
    count = 0
    for local_worst, local_record, local_count in results:
        count += int(local_count)
        if local_worst < worst:
            worst = local_worst
            record = local_record
    return worst, record, count


def _ast_constant_assignments(tree: ast.AST) -> dict[str, str]:
    names = {
        "BUNDLE_R",
        "BEND_LIMIT",
        "SAMPLE_DS",
        "MAX_DQ_STEP",
        "EXACT_HORIZON",
        "RC_SAMPLE_ALLOW",
        "DQ_TRACK",
        "DQ_ENCCAL",
        "DQ_TOTAL",
        "D_INSTALL",
        "D_GEOM",
        "D_THERM",
        "D_MESH",
        "J4_INTERFACE_ARCLENGTH_WINDOW_MM",
    }
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in names:
                out[target.id] = ast.dump(node.value, include_attributes=False)
            elif (
                isinstance(target, ast.Tuple)
                and isinstance(node.value, ast.Tuple)
                and len(target.elts) == len(node.value.elts)
            ):
                for target_item, value_item in zip(target.elts, node.value.elts):
                    if isinstance(target_item, ast.Name) and target_item.id in names:
                        out[target_item.id] = ast.dump(
                            value_item, include_attributes=False
                        )
    return out


def _static_equivalence_checks(original: str, transformed: str) -> dict[str, Any]:
    orig_tree = ast.parse(original, filename=str(ACTIVE_EVALUATOR))
    cand_tree = ast.parse(transformed, filename=str(ACTIVE_EVALUATOR))
    orig_constants = _ast_constant_assignments(orig_tree)
    cand_constants = _ast_constant_assignments(cand_tree)
    if orig_constants != cand_constants or len(orig_constants) != 14:
        raise AssertionError("scientific constant AST drift")

    invariant_fragments = [
        "sample_segment( qf, qt, math.radians(1.0))",
        "np.unique(np.round(np.array(mission_q_samples), 6), axis=0)",
        "_conservative_aabb_candidates(",
        "fld.signed_clearance_batch(Pl, RC_SAMPLE_ALLOW)",
        "solar_field.signed_clearance_batch(",
        "bus_field.signed_clearance_batch(",
        "k = int(np.argmin(c[ok]))",
    ]
    original_normalized = re.sub(r"\s+", " ", original)
    transformed_normalized = re.sub(r"\s+", " ", transformed)
    fragment_counts: dict[str, int] = {}
    for fragment in invariant_fragments:
        before = original_normalized.count(fragment)
        after = transformed_normalized.count(fragment)
        if before != after or before <= 0:
            raise AssertionError("invariant fragment drift: %s" % fragment)
        fragment_counts[fragment] = before

    if transformed.count("_p1_ordered_map(_p1_rc_cross_one_q, p1_rc_items)") != 1:
        raise AssertionError("ordered map injection count drift")
    if transformed.count("_p1_eval_batch(") != 1:
        raise AssertionError("mission ordered batch injection count drift")
    if transformed.count("r = p1_mission_results[k]") != 1:
        raise AssertionError("mission ordered result consumption missing")
    if transformed.count("r = eval_clearance(q)") != original.count(
        "r = eval_clearance(q)"
    ) - 1:
        raise AssertionError("non-mission eval_clearance call count drift")
    if transformed.count("if local_rc_worst < rc_worst:") != 1:
        raise AssertionError("strict ordered tie reducer missing")
    if "ProcessPoolExecutor" in transformed:
        raise AssertionError("unexpected process-pool semantics")
    return {
        "scientific_constant_assignments": len(orig_constants),
        "invariant_fragment_counts": fragment_counts,
        "ordered_map_injections": 1,
        "mission_ordered_batch_injections": 1,
        "mission_result_ordered_consumers": 1,
        "strict_tie_reducers": 1,
    }


def _synthetic_order_and_tie_checks(workers: int) -> dict[str, Any]:
    # Completion order is intentionally the reverse of input order.
    data = [
        (0, 4.0, "q0", 11, 0.040),
        (1, -2.0, "q1-first-tie", 13, 0.030),
        (2, -2.0, "q2-second-tie", 17, 0.020),
        (3, 1.0, "q3", 19, 0.010),
    ]

    def worker(item: tuple[int, float, str, int, float]) -> tuple[float, str, int]:
        _idx, value, record, count, delay = item
        time.sleep(delay)
        return value, record, count

    sequential = [worker(x) for x in data]
    parallel = ordered_map(worker, data, workers)
    if parallel != sequential:
        raise AssertionError("ordered map changed per-q result sequence")
    seq_reduced = _reduce_rc_results(sequential)
    par_reduced = _reduce_rc_results(parallel)
    if seq_reduced != par_reduced:
        raise AssertionError("parallel reducer differs from sequential reducer")
    if par_reduced != (-2.0, "q1-first-tie", 60):
        raise AssertionError("strict first-hit tie or comparison-count rule drift")

    def fail_worker(item: int) -> int:
        if item == 2:
            raise RuntimeError("synthetic fail-closed worker")
        return item

    propagated = False
    try:
        ordered_map(fail_worker, [0, 1, 2, 3], workers)
    except RuntimeError as exc:
        propagated = str(exc) == "synthetic fail-closed worker"
    if not propagated:
        raise AssertionError("worker exception was not propagated fail-closed")
    return {
        "ordered_result_match": True,
        "strict_first_hit_tie_record": par_reduced[1],
        "comparison_count_sum": par_reduced[2],
        "worker_exception_propagates": True,
    }


def _synthetic_mission_cache_checks(workers: int) -> dict[str, Any]:
    cache: dict[Any, Any] = {(False, 0.0): {"q": 0.0, "count": 5}}
    base_calls: list[float] = []

    def key_fn(q: Any) -> tuple[float]:
        return (round(float(np.asarray(q)[0]), 12),)

    def base_fn(q: Any) -> dict[str, float]:
        value = float(np.asarray(q)[0])
        base_calls.append(value)
        return {"base": value * 10.0}

    def eval_fn(q: Any) -> dict[str, float]:
        value = float(np.asarray(q)[0])
        base = _base_or_frozen(q, base_fn)
        time.sleep(0.005 * (3.0 - value))
        return {"q": value, "base": base["base"], "count": value + 7.0}

    qa = np.array([[0.0], [1.0], [2.0], [1.0]])
    results = mission_eval_batch(eval_fn, base_fn, cache, key_fn, qa, workers)
    expected = [
        {"q": 0.0, "count": 5},
        {"q": 1.0, "base": 10.0, "count": 8.0},
        {"q": 2.0, "base": 20.0, "count": 9.0},
        {"q": 1.0, "base": 10.0, "count": 8.0},
    ]
    if results != expected:
        raise AssertionError("mission batch changed ordered/cached results")
    if base_calls != [1.0, 2.0, 1.0]:
        raise AssertionError("mission base precompute order/cache contract drift")
    if cache[(False, 1.0)] != expected[-1] or cache[(False, 2.0)] != expected[2]:
        raise AssertionError("mission cache ordered commit mismatch")
    if _worker_active():
        raise AssertionError("mission worker thread-local state leaked to parent")
    return {
        "ordered_results_match": True,
        "preexisting_cache_hit_preserved": True,
        "duplicate_q_deterministic": True,
        "base_precompute_order": base_calls,
        "cache_commit_order": [0.0, 1.0, 2.0],
        "thread_local_state_cleared": True,
    }


def _assert_resolved_output_isolation() -> dict[str, Any]:
    candidate_root = CANDIDATE_DIR.resolve()
    active_outputs = {
        (ROUTE_C_DIR / "ROUTE_C_EXACT_SWEEP_V9F.json").resolve(),
        (ROUTE_C_DIR / "ROUTE_C_ROBUST_MARGIN_LEDGER_V9F.csv").resolve(),
        (ROUTE_C_DIR / "ROUTE_C_MISSION_COVERAGE_GATE_V9F.json").resolve(),
    }
    resolved: dict[str, str] = {}
    for path in (OUT_SWEEP, OUT_LEDGER, OUT_GATE, OUT_RECEIPT):
        target = path.resolve()
        if target.parent != candidate_root:
            raise AssertionError("candidate output escapes resolved candidate directory")
        if target in active_outputs:
            raise AssertionError("candidate output aliases resolved active output")
        resolved[path.name] = str(target)
    return {
        "candidate_root": str(candidate_root),
        "resolved_outputs": resolved,
        "active_output_alias_count": 0,
        "pass": True,
    }


def _audit_mission_round12_batch_keys() -> dict[str, Any]:
    if _sha256_path(MISSION_CONTRACT) != EXPECTED_MISSION_CONTRACT_SHA256:
        raise RuntimeError("mission contract hash drift before P1 key audit")
    with MISSION_CONTRACT.open("r", encoding="utf-8") as stream:
        contract = yaml.safe_load(stream)
    states = {name: value["q_rad"] for name, value in contract["states"].items()}
    reports: dict[str, Any] = {}
    for step_deg in (0.25, 0.125):
        total = 0
        distinct_collision_count = 0
        exact_duplicate_count = 0
        per_segment = []
        step_rad = math.radians(step_deg)
        for segment in contract["segments"]:
            q_from = states[segment["from"]]
            q_to = states[segment["to"]]
            if segment["from"] == segment["to"]:
                qa = np.array([q_from], dtype=float)
            else:
                dq = [abs(b - a) for a, b in zip(q_from, q_to)]
                n = max(1, int(math.ceil(max(dq) / step_rad)))
                ts = np.linspace(0.0, 1.0, n + 1)
                qa = (
                    np.asarray(q_from, dtype=float)[None, :]
                    + (
                        np.asarray(q_to, dtype=float)
                        - np.asarray(q_from, dtype=float)
                    )[None, :]
                    * ts[:, None]
                )
            seen: dict[tuple[float, ...], bytes] = {}
            segment_exact_duplicates = 0
            segment_distinct_collisions = 0
            for q in qa:
                key = tuple(round(float(value), 12) for value in q)
                payload = np.ascontiguousarray(q).tobytes()
                previous = seen.get(key)
                if previous is None:
                    seen[key] = payload
                elif previous == payload:
                    segment_exact_duplicates += 1
                else:
                    segment_distinct_collisions += 1
            total += len(qa)
            exact_duplicate_count += segment_exact_duplicates
            distinct_collision_count += segment_distinct_collisions
            per_segment.append(
                {
                    "segment": segment["id"],
                    "samples": int(len(qa)),
                    "exact_duplicate_count": segment_exact_duplicates,
                    "distinct_round12_collision_count": segment_distinct_collisions,
                }
            )
        if distinct_collision_count or exact_duplicate_count:
            raise RuntimeError(
                "mission batch key contract unsafe at %.3f deg: exact=%d distinct=%d"
                % (step_deg, exact_duplicate_count, distinct_collision_count)
            )
        reports["%.3f_deg" % step_deg] = {
            "total_samples": total,
            "exact_duplicate_count": exact_duplicate_count,
            "distinct_round12_collision_count": distinct_collision_count,
            "per_segment": per_segment,
            "pass": True,
        }
    return {
        "mission_contract_sha256": EXPECTED_MISSION_CONTRACT_SHA256,
        "steps": reports,
        "pass": True,
    }


def self_test(workers: int) -> dict[str, Any]:
    manifest_audit = _verify_external_manifest()
    _data, source = _read_pinned_source()
    transformed, transform_audit = transform_source(source)
    compile(transformed, str(ACTIVE_EVALUATOR), "exec")
    static = _static_equivalence_checks(source, transformed)
    synthetic = _synthetic_order_and_tie_checks(workers)
    mission_synthetic = _synthetic_mission_cache_checks(workers)
    mission_key_audit = _audit_mission_round12_batch_keys()

    # Execution outputs must never alias any active evaluator output.
    output_isolation = _assert_resolved_output_isolation()

    return {
        "schema": "ROUTE_C_V9F_P1_STATIC_EQUIVALENCE_SELF_TEST_V1",
        "status": "PASS_STATIC_AND_SYNTHETIC_ONLY__DYNAMIC_FULL_EQUIVALENCE_NOT_PROVEN",
        "workers_used_for_synthetic_test": workers,
        "external_manifest_audit": manifest_audit,
        "transform_audit": transform_audit,
        "static_checks": static,
        "synthetic_checks": synthetic,
        "mission_synthetic_checks": mission_synthetic,
        "mission_round12_batch_key_audit": mission_key_audit,
        "output_isolation": output_isolation,
        "full_sweep_executed": False,
        "gate_credit": False,
        "release_credit": False,
    }


def _strict_json_load(path: Path) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate JSON key %r in %s" % (key, path))
            out[key] = value
        return out

    def reject_constant(token: str) -> None:
        raise ValueError("non-finite JSON token %s in %s" % (token, path))

    with path.open("r", encoding="utf-8", newline="") as stream:
        value = json.load(
            stream, object_pairs_hook=no_duplicates, parse_constant=reject_constant
        )
    if not isinstance(value, dict):
        raise ValueError("expected JSON object in %s" % path)
    return value


def _verify_external_manifest() -> dict[str, Any]:
    manifest = _strict_json_load(EXTERNAL_MANIFEST)
    if manifest.get("schema") != "ROUTE_C_V9F_P1_CANDIDATE_MANIFEST_V1":
        raise RuntimeError("P1 external manifest schema mismatch")
    wrapper_entry = manifest.get("files", {}).get(Path(__file__).name)
    if not isinstance(wrapper_entry, dict):
        raise RuntimeError("P1 external manifest does not bind wrapper")
    expected_wrapper = str(wrapper_entry.get("sha256", "")).upper()
    actual_wrapper = _sha256_path(Path(__file__).resolve())
    if expected_wrapper != actual_wrapper:
        raise RuntimeError(
            "P1 wrapper hash drift: expected %s, got %s"
            % (expected_wrapper, actual_wrapper)
        )
    if (
        str(manifest.get("active_evaluator_sha256", "")).upper()
        != EXPECTED_ACTIVE_SHA256
        or str(manifest.get("rc_cross_loop_sha256", "")).upper()
        != EXPECTED_RC_LOOP_SHA256
        or str(manifest.get("run_mission_loop_sha256", "")).upper()
        != EXPECTED_RUN_MISSION_SHA256
        or str(manifest.get("mission_contract_sha256", "")).upper()
        != EXPECTED_MISSION_CONTRACT_SHA256
        or _sha256_path(MISSION_CONTRACT) != EXPECTED_MISSION_CONTRACT_SHA256
    ):
        raise RuntimeError("P1 external manifest scientific-source pin drift")
    return {
        "manifest_path": str(EXTERNAL_MANIFEST.resolve()),
        "manifest_sha256": _sha256_path(EXTERNAL_MANIFEST),
        "wrapper_path": str(Path(__file__).resolve()),
        "wrapper_sha256": actual_wrapper,
        "match": True,
    }


def _write_json_atomic(path: Path, obj: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(
        obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    )
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
    os.replace(tmp, path)


def _mark_candidate_nonauthoritative(
    path: Path, workers: int, transform_audit: dict[str, Any]
) -> None:
    obj = _strict_json_load(path)
    obj["authoritative"] = False
    obj["execution_mode"] = "FULL_P1_ACCELERATION_CANDIDATE_VALIDATION"
    obj["authority_scope"] = (
        "NON_AUTHORITATIVE_ACCELERATION_EQUIVALENCE_CANDIDATE__NO_GATE_OR_RELEASE_CREDIT"
    )
    obj["next_stage_authorized"] = False
    obj["release_credit"] = False
    binding = _verify_external_manifest()
    obj["p1_acceleration_candidate"] = {
        "method": (
            "ORDERED_THREAD_MAP_OVER_MISSION_NOMINAL_REFINEMENT_Q_AND_"
            "RC_CROSS_Q_OUTER_LOOPS"
        ),
        "worker_count": workers,
        "active_source_sha256": transform_audit["active_source_sha256"],
        "original_rc_loop_sha256": transform_audit["original_rc_loop_sha256"],
        "original_run_mission_sha256": transform_audit[
            "original_run_mission_sha256"
        ],
        "transformed_source_sha256": transform_audit["transformed_source_sha256"],
        "wrapper_sha256": binding["wrapper_sha256"],
        "external_manifest_sha256": binding["manifest_sha256"],
        "mission_contract_sha256": EXPECTED_MISSION_CONTRACT_SHA256,
        "dynamic_equivalence_status": "PENDING_SEQUENTIAL_P0_FULL_COMPARISON",
        "gate_credit": False,
        "release_credit": False,
    }
    _write_json_atomic(path, obj)


def _assert_nonauthoritative_output(path: Path) -> dict[str, Any]:
    obj = _strict_json_load(path)
    checks = {
        "authoritative_false": obj.get("authoritative") is False,
        "next_stage_authorized_false": obj.get("next_stage_authorized") is False,
        "release_credit_false": obj.get("release_credit") is False,
        "candidate_metadata_present": isinstance(
            obj.get("p1_acceleration_candidate"), dict
        ),
    }
    if not all(checks.values()):
        raise RuntimeError("candidate authority demotion assertion failed: %r" % checks)
    return {"path": str(path.resolve()), "checks": checks, "pass": True}


def run_candidate(workers: int) -> int:
    if os.environ.get("RC_P1_ACCEPT_NONAUTHORITATIVE") != "YES":
        raise RuntimeError(
            "set RC_P1_ACCEPT_NONAUTHORITATIVE=YES to acknowledge no Gate credit"
        )
    if os.environ.get("RC_FAST", "0") == "1" or os.environ.get(
        "RC_FAST_OUTPUT_TAG", ""
    ):
        raise RuntimeError("P1 overlay accepts FULL mode only; FAST/tag is forbidden")
    # Re-run the complete wrapper preflight at the actual execution entry.
    # This binds the wrapper itself and rechecks ordered return, first-hit tie,
    # exact count sum, exception propagation and resolved output isolation.
    runtime_preflight = self_test(workers)
    outputs = (OUT_SWEEP, OUT_LEDGER, OUT_GATE, OUT_RECEIPT)
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise RuntimeError("refusing to overwrite candidate outputs: %s" % existing)

    _data, source = _read_pinned_source()
    transformed, transform_audit = transform_source(source)
    _static_equivalence_checks(source, transformed)
    code = compile(transformed, str(ACTIVE_EVALUATOR), "exec")
    namespace: dict[str, Any] = {
        "__name__": "__v9f_p1_embedded__",
        "__file__": str(ACTIVE_EVALUATOR),
    }
    exec(code, namespace)
    namespace["_p1_ordered_map"] = lambda fn, items: ordered_map(fn, items, workers)
    namespace["_p1_eval_batch"] = lambda eval_fn, base_fn, cache, key_fn, qa: (
        mission_eval_batch(eval_fn, base_fn, cache, key_fn, qa, workers)
    )
    namespace["_p1_worker_active"] = _worker_active
    namespace["_p1_base_or_frozen"] = _base_or_frozen
    namespace["OUT_SWEEP"] = str(OUT_SWEEP)
    namespace["OUT_LEDGER"] = str(OUT_LEDGER)
    namespace["OUT_GATE"] = str(OUT_GATE)
    namespace["main"]()

    for output in (OUT_SWEEP, OUT_LEDGER, OUT_GATE):
        if not output.is_file() or output.stat().st_size <= 0:
            raise RuntimeError("candidate output missing or empty: %s" % output)
    _mark_candidate_nonauthoritative(OUT_SWEEP, workers, transform_audit)
    _mark_candidate_nonauthoritative(OUT_GATE, workers, transform_audit)
    authority_assertions = [
        _assert_nonauthoritative_output(OUT_SWEEP),
        _assert_nonauthoritative_output(OUT_GATE),
    ]
    manifest_audit = _verify_external_manifest()
    receipt = {
        "schema": "ROUTE_C_V9F_P1_CANDIDATE_EXECUTION_RECEIPT_V1",
        "status": "NON_AUTHORITATIVE__DYNAMIC_EQUIVALENCE_PENDING",
        "worker_count": workers,
        "wrapper_binding": manifest_audit,
        "runtime_preflight_status": runtime_preflight["status"],
        "runtime_output_isolation": runtime_preflight["output_isolation"],
        "runtime_synthetic_checks": runtime_preflight["synthetic_checks"],
        "runtime_mission_synthetic_checks": runtime_preflight[
            "mission_synthetic_checks"
        ],
        "runtime_mission_round12_batch_key_audit": runtime_preflight[
            "mission_round12_batch_key_audit"
        ],
        "authority_assertions": authority_assertions,
        "transform_audit": transform_audit,
        "outputs": {
            path.name: {"sha256": _sha256_path(path), "bytes": path.stat().st_size}
            for path in (OUT_SWEEP, OUT_LEDGER, OUT_GATE)
        },
        "next_stage_authorized": False,
        "gate_credit": False,
        "release_credit": False,
    }
    _write_json_atomic(OUT_RECEIPT, receipt)
    return 0


def _parse_workers(raw: str) -> int:
    if re.fullmatch(r"[1-8]", raw) is None:
        raise argparse.ArgumentTypeError("workers must be an integer from 1 to 8")
    return int(raw)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--self-test", action="store_true")
    action.add_argument("--run-nonauthoritative", action="store_true")
    parser.add_argument(
        "--workers",
        type=_parse_workers,
        default=_parse_workers(os.environ.get("RC_P1_WORKERS", "4")),
    )
    args = parser.parse_args(argv)
    if args.run_nonauthoritative:
        return run_candidate(args.workers)
    result = self_test(args.workers)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
