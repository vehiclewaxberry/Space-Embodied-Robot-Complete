#!/usr/bin/env python3
"""Isolated one-pose P0/P1 benchmark; never enters a trajectory sweep.

The hash-pinned evaluator is compiled in memory.  A controlled callback and
sentinel are injected immediately before the first mission-sweep note.  P0 and
P1 execute in separate subprocesses with cold eval caches, at the midpoint of
M01.  No active evaluator source/input/output is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from typing import Any, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
OVERLAY_PATH = HERE / "P1_RC_CROSS_THREADED_OVERLAY.py"
OUT_BENCHMARK = HERE / "P1_SINGLE_POSE_BENCHMARK.json"
HOOK_ANCHOR = '    note("running mission sweep (nominal step)...")\n'
HOOK_REPLACEMENT = (
    "    _single_pose_benchmark_hook(\n"
    "        eval_clearance, _base_kinematics, eval_cache,\n"
    "        _q_round12_key, states, segments)\n"
    "    raise _SinglePoseBenchmarkStop()\n"
)
RESULT_PREFIX = "__V9F_SINGLE_POSE_RESULT__="


def _load_overlay() -> Any:
    spec = importlib.util.spec_from_file_location("v9f_p1_overlay_bench", OVERLAY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load P1 overlay")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _strict_encode(value: Any, stats: dict[str, int]) -> Any:
    stats["nodes"] += 1
    if isinstance(value, np.generic):
        value = value.item()
    if value is None:
        return {"$none": True}
    if isinstance(value, bool):
        stats["bools"] += 1
        return {"$bool": value}
    if isinstance(value, int):
        stats["ints"] += 1
        return {"$int": str(value)}
    if isinstance(value, float):
        stats["floats"] += 1
        return {"$float64_be": struct.pack(">d", value).hex().upper()}
    if isinstance(value, str):
        stats["strings"] += 1
        return {"$str": value}
    if isinstance(value, list):
        stats["lists"] += 1
        return {"$list": [_strict_encode(item, stats) for item in value]}
    if isinstance(value, tuple):
        stats["tuples"] += 1
        return {"$tuple": [_strict_encode(item, stats) for item in value]}
    if isinstance(value, dict):
        stats["dicts"] += 1
        if not all(isinstance(key, str) for key in value):
            raise TypeError("benchmark result contains a non-string dict key")
        return {
            "$dict": [
                [key, _strict_encode(value[key], stats)] for key in sorted(value)
            ]
        }
    raise TypeError("unsupported benchmark result type: %r" % type(value))


def _encode_result(value: Any) -> tuple[Any, dict[str, int], str]:
    stats = {
        "nodes": 0,
        "bools": 0,
        "ints": 0,
        "floats": 0,
        "strings": 0,
        "lists": 0,
        "tuples": 0,
        "dicts": 0,
    }
    encoded = _strict_encode(value, stats)
    payload = json.dumps(
        encoded, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return encoded, stats, _sha256_bytes(payload)


def _safe_json(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, dict):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    return value


def _inject_hook(source: str) -> str:
    if source.count(HOOK_ANCHOR) != 1:
        raise RuntimeError("single-pose hook anchor count drift")
    injected = source.replace(HOOK_ANCHOR, HOOK_REPLACEMENT, 1)
    compile(injected, "<v9f-single-pose-benchmark>", "exec")
    return injected


class _SinglePoseBenchmarkStop(Exception):
    pass


def _child(mode: str, workers: int) -> int:
    if os.environ.get("RC_FAST", "0") == "1" or os.environ.get(
        "RC_FAST_OUTPUT_TAG", ""
    ):
        raise RuntimeError("single-pose benchmark requires FULL constants and no FAST tag")
    overlay = _load_overlay()
    binding = overlay._verify_external_manifest()
    _data, active_source = overlay._read_pinned_source()
    if mode == "p0":
        source = active_source
        transformed_sha = None
    elif mode == "p1":
        source, transform_audit = overlay.transform_source(active_source)
        transformed_sha = transform_audit["transformed_source_sha256"]
    else:
        raise ValueError("unsupported child mode")
    source = _inject_hook(source)

    result_box: dict[str, Any] = {}
    process_wall_start = time.perf_counter()
    process_cpu_start = time.process_time()
    prepare_wall_start = time.perf_counter()
    prepare_cpu_start = time.process_time()
    namespace: dict[str, Any] = {
        "__name__": "__v9f_single_pose_embedded__",
        "__file__": str(overlay.ACTIVE_EVALUATOR),
        "_SinglePoseBenchmarkStop": _SinglePoseBenchmarkStop,
    }
    exec(compile(source, str(overlay.ACTIVE_EVALUATOR), "exec"), namespace)
    source_prepare_wall = time.perf_counter() - prepare_wall_start
    source_prepare_cpu = time.process_time() - prepare_cpu_start

    if mode == "p1":
        namespace["_p1_ordered_map"] = (
            lambda fn, items: overlay.ordered_map(fn, items, workers)
        )
        namespace["_p1_eval_batch"] = (
            lambda eval_fn, base_fn, cache, key_fn, qa: overlay.mission_eval_batch(
                eval_fn, base_fn, cache, key_fn, qa, workers
            )
        )
        namespace["_p1_worker_active"] = overlay._worker_active
        namespace["_p1_base_or_frozen"] = overlay._base_or_frozen

    init_wall_start = time.perf_counter()
    init_cpu_start = time.process_time()

    def hook(
        eval_clearance: Any,
        base_fn: Any,
        eval_cache: dict[Any, Any],
        key_fn: Any,
        states: dict[str, Any],
        segments: list[dict[str, Any]],
    ) -> None:
        init_wall = time.perf_counter() - init_wall_start
        init_cpu = time.process_time() - init_cpu_start
        segment = next(item for item in segments if item["id"] == "M01")
        q_from = np.asarray(states[segment["from"]], dtype=float)
        q_to = np.asarray(states[segment["to"]], dtype=float)
        q = 0.5 * (q_from + q_to)
        if eval_cache:
            raise RuntimeError("benchmark eval cache is not cold at hook")
        eval_wall_start = time.perf_counter()
        eval_cpu_start = time.process_time()
        if mode == "p0":
            result = eval_clearance(q)
        else:
            values = overlay.mission_eval_batch(
                eval_clearance, base_fn, eval_cache, key_fn, np.array([q]), workers
            )
            if len(values) != 1:
                raise RuntimeError("P1 single-pose batch cardinality mismatch")
            result = values[0]
        eval_wall = time.perf_counter() - eval_wall_start
        eval_cpu = time.process_time() - eval_cpu_start
        encoded, stats, fingerprint = _encode_result(result)
        cache_key = (False,) + tuple(key_fn(q))
        if cache_key not in eval_cache:
            raise RuntimeError("single-pose result was not committed to eval cache")
        result_box.update(
            {
                "mode": mode,
                "workers": workers if mode == "p1" else 1,
                "m01": {
                    "from": segment["from"],
                    "to": segment["to"],
                    "fraction": 0.5,
                    "q_rad": [float(value) for value in q],
                    "q_bytes_sha256": _sha256_bytes(
                        np.ascontiguousarray(q).tobytes()
                    ),
                },
                "timing_seconds": {
                    "source_prepare_wall": source_prepare_wall,
                    "source_prepare_cpu": source_prepare_cpu,
                    "initialization_to_pre_sweep_hook_wall": init_wall,
                    "initialization_to_pre_sweep_hook_cpu": init_cpu,
                    "single_pose_eval_wall": eval_wall,
                    "single_pose_eval_cpu": eval_cpu,
                },
                "result_fingerprint_sha256": fingerprint,
                "result_value_stats": stats,
                "result_strict_encoding": encoded,
                "result_summary": _safe_json(result),
                "eval_cache_entries_after": len(eval_cache),
                "active_source_sha256": overlay.EXPECTED_ACTIVE_SHA256,
                "wrapper_sha256": binding["wrapper_sha256"],
                "external_manifest_sha256": binding["manifest_sha256"],
                "transformed_source_sha256": transformed_sha,
                "full_sweep_executed": False,
                "active_output_written": False,
            }
        )

    namespace["_single_pose_benchmark_hook"] = hook
    try:
        namespace["main"]()
    except _SinglePoseBenchmarkStop:
        pass
    else:
        raise RuntimeError("benchmark sentinel did not stop before mission sweep")
    if not result_box:
        raise RuntimeError("benchmark hook did not produce a result")
    result_box["timing_seconds"]["child_total_wall"] = (
        time.perf_counter() - process_wall_start
    )
    result_box["timing_seconds"]["child_total_cpu"] = (
        time.process_time() - process_cpu_start
    )
    print(RESULT_PREFIX + json.dumps(result_box, sort_keys=True, allow_nan=False))
    return 0


def _run_child(mode: str, workers: int) -> tuple[dict[str, Any], dict[str, Any]]:
    env = os.environ.copy()
    env["RC_FAST"] = "0"
    env.pop("RC_FAST_OUTPUT_TAG", None)
    command = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--child-mode",
        mode,
        "--workers",
        str(workers),
    ]
    wall_start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(HERE),
        env=env,
        text=True,
        encoding="utf-8",
        errors="strict",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    orchestrator_wall = time.perf_counter() - wall_start
    if completed.returncode != 0:
        raise RuntimeError(
            "%s child failed rc=%d\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (mode, completed.returncode, completed.stdout, completed.stderr)
        )
    records = [
        line[len(RESULT_PREFIX) :]
        for line in completed.stdout.splitlines()
        if line.startswith(RESULT_PREFIX)
    ]
    if len(records) != 1:
        raise RuntimeError("%s child result record count=%d" % (mode, len(records)))
    return json.loads(records[0]), {
        "orchestrator_wall_seconds": orchestrator_wall,
        "stdout_line_count": len(completed.stdout.splitlines()),
        "stderr_bytes": len(completed.stderr.encode("utf-8")),
    }


def _first_mismatch(a: Any, b: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(a) is not type(b):
        return [{"path": path, "kind": "TYPE", "p0": type(a).__name__, "p1": type(b).__name__}]
    if isinstance(a, dict):
        if set(a) != set(b):
            return [{"path": path, "kind": "KEY_SET", "p0": sorted(a), "p1": sorted(b)}]
        for key in sorted(a):
            mismatch = _first_mismatch(a[key], b[key], path + "." + key)
            if mismatch:
                return mismatch
        return []
    if isinstance(a, list):
        if len(a) != len(b):
            return [{"path": path, "kind": "LENGTH", "p0": len(a), "p1": len(b)}]
        for index, (left, right) in enumerate(zip(a, b)):
            mismatch = _first_mismatch(left, right, "%s[%d]" % (path, index))
            if mismatch:
                return mismatch
        return []
    if a != b:
        return [{"path": path, "kind": "VALUE", "p0": a, "p1": b}]
    return []


def _write_json_atomic(path: Path, obj: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(
        obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    )
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
    os.replace(tmp, path)


def run_benchmark(workers: int) -> int:
    if OUT_BENCHMARK.exists():
        raise RuntimeError("refusing to overwrite existing benchmark JSON")
    overlay = _load_overlay()
    preflight = overlay.self_test(workers)
    p0, p0_process = _run_child("p0", workers)
    p1, p1_process = _run_child("p1", workers)
    mismatches = _first_mismatch(
        p0["result_strict_encoding"], p1["result_strict_encoding"]
    )
    q_equal = p0["m01"] == p1["m01"]
    strict_equal = not mismatches and q_equal
    if not strict_equal:
        raise RuntimeError("P0/P1 single-pose strict mismatch: %r" % mismatches[:1])

    p0_wall = p0["timing_seconds"]["single_pose_eval_wall"]
    p1_wall = p1["timing_seconds"]["single_pose_eval_wall"]
    p0_cpu = p0["timing_seconds"]["single_pose_eval_cpu"]
    p1_cpu = p1["timing_seconds"]["single_pose_eval_cpu"]
    benchmark = {
        "schema": "ROUTE_C_V9F_P1_SINGLE_POSE_BENCHMARK_V1",
        "authority": "NONAUTHORITATIVE_PERFORMANCE_DIAGNOSTIC_ONLY",
        "benchmark_method_sha256": _sha256_path(Path(__file__).resolve()),
        "bindings": {
            "active_evaluator_sha256": overlay.EXPECTED_ACTIVE_SHA256,
            "wrapper_sha256": p1["wrapper_sha256"],
            "external_manifest_sha256": p1["external_manifest_sha256"],
            "transformed_source_sha256": p1["transformed_source_sha256"],
            "mission_contract_sha256": overlay.EXPECTED_MISSION_CONTRACT_SHA256,
        },
        "preflight_status": preflight["status"],
        "selected_pose": p0["m01"],
        "measurement_definition": {
            "p0": "cold eval_cache direct eval_clearance(q)",
            "p1": "cold eval_cache mission_eval_batch([q]) including sequential base precompute, one ordered worker task, and cache commit",
            "initialization_stop": "controlled sentinel immediately before nominal mission sweep note",
            "process_isolation": "separate fresh subprocess per mode",
            "warmup": "none",
            "repetitions": 1,
        },
        "p0": {
            "timing_seconds": p0["timing_seconds"],
            "process_capture": p0_process,
            "result_fingerprint_sha256": p0["result_fingerprint_sha256"],
            "result_value_stats": p0["result_value_stats"],
            "result_summary": p0["result_summary"],
        },
        "p1": {
            "workers": workers,
            "timing_seconds": p1["timing_seconds"],
            "process_capture": p1_process,
            "result_fingerprint_sha256": p1["result_fingerprint_sha256"],
            "result_value_stats": p1["result_value_stats"],
            "result_summary": p1["result_summary"],
        },
        "strict_output_equivalence": {
            "equal": strict_equal,
            "q_equal": q_equal,
            "fingerprints_equal": (
                p0["result_fingerprint_sha256"] == p1["result_fingerprint_sha256"]
            ),
            "value_stats_equal": p0["result_value_stats"] == p1["result_value_stats"],
            "mismatch_count": len(mismatches),
            "first_mismatch": mismatches[0] if mismatches else None,
            "comparison": "recursive exact types; every float compared by IEEE-754 binary64 big-endian bytes",
        },
        "performance_ratio": {
            "p0_wall_over_p1_wall": p0_wall / p1_wall,
            "p0_cpu_over_p1_cpu": p0_cpu / p1_cpu,
            "interpretation": "single cold pose only; not a FULL-sweep speedup claim",
        },
        "full_sweep_executed": False,
        "active_source_modified": False,
        "active_input_modified": False,
        "active_output_written": False,
        "gate_credit": False,
        "release_credit": False,
        "next_stage_authorized": False,
        "verdict": "SINGLE_POSE_STRICT_EQUIVALENCE_PASS__PERFORMANCE_DIAGNOSTIC_ONLY",
    }
    _write_json_atomic(OUT_BENCHMARK, benchmark)
    print(json.dumps(benchmark["performance_ratio"], indent=2, sort_keys=True))
    print("WROTE %s" % OUT_BENCHMARK)
    return 0


def _workers(raw: str) -> int:
    value = int(raw)
    if value < 1 or value > 8:
        raise argparse.ArgumentTypeError("workers must be 1..8")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child-mode", choices=("p0", "p1"))
    parser.add_argument("--workers", type=_workers, default=4)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    if args.child_mode:
        return _child(args.child_mode, args.workers)
    if not args.run:
        parser.error("use --run (parent) or --child-mode p0|p1")
    return run_benchmark(args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
