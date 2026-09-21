#!/usr/bin/env python3
"""Hash-pinned reference-vs-P0 M01-midpoint exact benchmark.

Both sources execute in separate fresh subprocesses and are stopped by a
controlled sentinel immediately before the first mission sweep.  No active
source, input, evaluator output or full trajectory sweep is touched.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
ROUTE_C_DIR = HERE.parents[1]
REFERENCE_SOURCE = (
    ROUTE_C_DIR
    / "_work"
    / "v9f_evaluator_pre_redteam_fix"
    / "ROUTE_C_EXACT_SWEEP_V9F_PRE_PERFORMANCE_REFERENCE.py"
)
EXPECTED_REFERENCE_SHA256 = (
    "46732BB71605E6EE52488C6324FB47E5E7C009490A3E94F49DE95EC2B0DF6244"
)
OVERLAY_PATH = HERE / "P1_RC_CROSS_THREADED_OVERLAY.py"
BASE_BENCH_METHOD_PATH = HERE / "SINGLE_POSE_BENCHMARK.py"
EXPECTED_BASE_BENCH_METHOD_SHA256 = (
    "821FC648A3C758CC558D74583D062D8E56466361951DFCE5116DE1AE1DA78B1C"
)
EXISTING_P0_BENCHMARK = HERE / "P1_SINGLE_POSE_BENCHMARK.json"
EXPECTED_EXISTING_P0_FINGERPRINT = (
    "607BEF54C51C31A1C66619AE0A02026094C376942D47F659DCAB194DBB57A538"
)
OUT_BENCHMARK = HERE / "REFERENCE_VS_P0_SINGLE_POSE_BENCHMARK_V2.json"
HOOK_ANCHOR = '    note("running mission sweep (nominal step)...")\n'
HOOK_REPLACEMENT = (
    "    _reference_p0_single_pose_hook(\n"
    "        eval_clearance, eval_cache, states, segments)\n"
    "    raise _ReferenceP0BenchmarkStop()\n"
)
RESULT_PREFIX = "__V9F_REFERENCE_P0_RESULT__="


def _local_file_sha256(path: Path) -> str:
    """Independent helper binding; does not depend on the helper being checked."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _verify_base_helper() -> str:
    actual = _local_file_sha256(BASE_BENCH_METHOD_PATH)
    if actual != EXPECTED_BASE_BENCH_METHOD_SHA256:
        raise RuntimeError(
            "strict encoding helper hash drift: expected %s, got %s"
            % (EXPECTED_BASE_BENCH_METHOD_SHA256, actual)
        )
    return actual


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inject_hook(source: str, filename: str) -> str:
    if source.count(HOOK_ANCHOR) != 1:
        raise RuntimeError("pre-sweep hook anchor count drift for %s" % filename)
    injected = source.replace(HOOK_ANCHOR, HOOK_REPLACEMENT, 1)
    compile(injected, filename, "exec")
    return injected


class _ReferenceP0BenchmarkStop(Exception):
    pass


def _extract_negative_detail(result: dict[str, Any]) -> dict[str, Any]:
    detail = result.get("detail")
    if not isinstance(detail, dict):
        raise RuntimeError("negative result detail is absent")
    gated = float(result["clearance"])
    raw = float(result["clearance_raw"])
    if gated >= 0.0:
        raise RuntimeError("selected reference/P0 pose is not a negative witness")
    required = {
        "host",
        "alternate",
        "field",
        "point_A0_q0",
        "derate_mm",
        "segment",
        "section_index",
    }
    if not required.issubset(detail):
        raise RuntimeError("negative detail field set incomplete")
    return {
        "gated_clearance_mm": gated,
        "raw_clearance_mm": raw,
        "object_field": detail["field"],
        "host": detail["host"],
        "alternate_attachment": detail["alternate"],
        "point_A0_q0_mm": detail["point_A0_q0"],
        "derate_mm": detail["derate_mm"],
        "segment": detail["segment"],
        "section_index": detail["section_index"],
        "is_negative": True,
    }


def _extract_j4_checks(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "j4_dynamic_min_bend_radius_mm",
        "j4_carriage_center_x_mm",
        "j4_dynamic_exchange_length_residual_mm",
        "j4_follower_closure_residual_mm",
        "j4_stage_overlap_mm",
        "j4_hard_stop_margin_mm",
        "j4_annulus_guide_margin_rad",
        "j4_within_hardware_limits",
    ]
    missing = [key for key in keys if key not in result]
    if missing:
        raise RuntimeError("missing J4 checks: %r" % missing)
    return {key: result[key] for key in keys}


def _child(mode: str) -> int:
    if os.environ.get("RC_FAST", "0") == "1" or os.environ.get(
        "RC_FAST_OUTPUT_TAG", ""
    ):
        raise RuntimeError("reference/P0 benchmark requires FULL constants")
    helper_sha = _verify_base_helper()
    overlay = _load_module(OVERLAY_PATH, "v9f_overlay_reference_bench")
    base_method = _load_module(BASE_BENCH_METHOD_PATH, "v9f_base_bench_helpers")
    binding = overlay._verify_external_manifest()
    if mode == "reference":
        source_path = REFERENCE_SOURCE
        source_bytes = source_path.read_bytes()
        source_sha = base_method._sha256_bytes(source_bytes)
        if source_sha != EXPECTED_REFERENCE_SHA256:
            raise RuntimeError("reference evaluator hash drift")
        source = source_bytes.decode("utf-8")
        # The reference bytes originally executed from route_c before archival.
        # Preserve that runtime path basis so its frozen relative inputs resolve
        # exactly as they did in the running sequential reference process.
        runtime_file = overlay.ACTIVE_EVALUATOR
    elif mode == "p0":
        source_path = overlay.ACTIVE_EVALUATOR
        _source_bytes, source = overlay._read_pinned_source()
        source_sha = overlay.EXPECTED_ACTIVE_SHA256
        runtime_file = overlay.ACTIVE_EVALUATOR
    else:
        raise ValueError("unsupported child mode")
    source = _inject_hook(source, str(source_path))

    result_box: dict[str, Any] = {}
    total_wall_start = time.perf_counter()
    total_cpu_start = time.process_time()
    prepare_wall_start = time.perf_counter()
    prepare_cpu_start = time.process_time()
    namespace: dict[str, Any] = {
        "__name__": "__v9f_reference_p0_embedded__",
        "__file__": str(runtime_file),
        "_ReferenceP0BenchmarkStop": _ReferenceP0BenchmarkStop,
    }
    exec(compile(source, str(runtime_file), "exec"), namespace)
    source_prepare_wall = time.perf_counter() - prepare_wall_start
    source_prepare_cpu = time.process_time() - prepare_cpu_start
    init_wall_start = time.perf_counter()
    init_cpu_start = time.process_time()

    def hook(
        eval_clearance: Any,
        eval_cache: dict[Any, Any],
        states: dict[str, Any],
        segments: list[dict[str, Any]],
    ) -> None:
        init_wall = time.perf_counter() - init_wall_start
        init_cpu = time.process_time() - init_cpu_start
        if eval_cache:
            raise RuntimeError("benchmark eval cache is not cold")
        segment = next(item for item in segments if item["id"] == "M01")
        q_from = np.asarray(states[segment["from"]], dtype=float)
        q_to = np.asarray(states[segment["to"]], dtype=float)
        q = 0.5 * (q_from + q_to)
        eval_wall_start = time.perf_counter()
        eval_cpu_start = time.process_time()
        result = eval_clearance(q)
        eval_wall = time.perf_counter() - eval_wall_start
        eval_cpu = time.process_time() - eval_cpu_start
        encoded, stats, fingerprint = base_method._encode_result(result)
        if len(eval_cache) != 1:
            raise RuntimeError("expected one cold-cache result, got %d" % len(eval_cache))
        result_box.update(
            {
                "mode": mode,
                "source_path": str(source_path.resolve()),
                "runtime_virtual_file": str(runtime_file.resolve()),
                "source_sha256": source_sha,
                "m01": {
                    "from": segment["from"],
                    "to": segment["to"],
                    "fraction": 0.5,
                    "q_rad": [float(value) for value in q],
                    "q_bytes_sha256": base_method._sha256_bytes(
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
                "result_summary": base_method._safe_json(result),
                "negative_detail": base_method._safe_json(
                    _extract_negative_detail(result)
                ),
                "comparison_counts": base_method._safe_json(
                    result["comparison_counts"]
                ),
                "j4_checks": base_method._safe_json(_extract_j4_checks(result)),
                "active_evaluator_sha256": overlay.EXPECTED_ACTIVE_SHA256,
                "reference_evaluator_sha256": EXPECTED_REFERENCE_SHA256,
                "wrapper_sha256": binding["wrapper_sha256"],
                "external_manifest_sha256": binding["manifest_sha256"],
                "strict_encoding_helper_sha256": helper_sha,
                "full_sweep_executed": False,
                "active_output_written": False,
            }
        )

    namespace["_reference_p0_single_pose_hook"] = hook
    try:
        namespace["main"]()
    except _ReferenceP0BenchmarkStop:
        pass
    else:
        raise RuntimeError("pre-sweep benchmark sentinel did not fire")
    if not result_box:
        raise RuntimeError("pre-sweep hook did not produce result")
    result_box["timing_seconds"]["child_total_wall"] = (
        time.perf_counter() - total_wall_start
    )
    result_box["timing_seconds"]["child_total_cpu"] = (
        time.process_time() - total_cpu_start
    )
    print(RESULT_PREFIX + json.dumps(result_box, sort_keys=True, allow_nan=False))
    return 0


def _run_child(mode: str) -> tuple[dict[str, Any], dict[str, Any]]:
    env = os.environ.copy()
    env["RC_FAST"] = "0"
    env.pop("RC_FAST_OUTPUT_TAG", None)
    command = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--child-mode",
        mode,
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
    capture = {
        "orchestrator_wall_seconds": time.perf_counter() - wall_start,
        "return_code": completed.returncode,
        "stdout_line_count": len(completed.stdout.splitlines()),
        "stderr_bytes": len(completed.stderr.encode("utf-8")),
    }
    if completed.returncode != 0:
        raise RuntimeError(
            "%s child failed\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (mode, completed.stdout, completed.stderr)
        )
    records = [
        line[len(RESULT_PREFIX) :]
        for line in completed.stdout.splitlines()
        if line.startswith(RESULT_PREFIX)
    ]
    if len(records) != 1:
        raise RuntimeError("%s child result count=%d" % (mode, len(records)))
    return json.loads(records[0]), capture


def _collect_mismatches(
    left: Any, right: Any, path: str = "$", out: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    if out is None:
        out = []
    if type(left) is not type(right):
        out.append(
            {"path": path, "kind": "TYPE", "reference": type(left).__name__, "p0": type(right).__name__}
        )
        return out
    if isinstance(left, dict):
        if set(left) != set(right):
            out.append(
                {"path": path, "kind": "KEY_SET", "reference": sorted(left), "p0": sorted(right)}
            )
            return out
        for key in sorted(left):
            _collect_mismatches(left[key], right[key], path + "." + key, out)
        return out
    if isinstance(left, list):
        if len(left) != len(right):
            out.append(
                {"path": path, "kind": "LENGTH", "reference": len(left), "p0": len(right)}
            )
            return out
        for index, (a, b) in enumerate(zip(left, right)):
            _collect_mismatches(a, b, "%s[%d]" % (path, index), out)
        return out
    if left != right:
        out.append({"path": path, "kind": "VALUE", "reference": left, "p0": right})
    return out


def run_benchmark() -> int:
    if OUT_BENCHMARK.exists():
        raise RuntimeError("refusing to overwrite reference-vs-P0 benchmark")
    helper_sha = _verify_base_helper()
    overlay = _load_module(OVERLAY_PATH, "v9f_overlay_reference_parent")
    base_method = _load_module(BASE_BENCH_METHOD_PATH, "v9f_base_bench_parent")
    preflight = overlay.self_test(4)
    existing = json.load(EXISTING_P0_BENCHMARK.open("r", encoding="utf-8"))
    existing_fp = existing["p0"]["result_fingerprint_sha256"]
    if existing_fp != EXPECTED_EXISTING_P0_FINGERPRINT:
        raise RuntimeError("existing P0 benchmark fingerprint drift")

    reference, reference_capture = _run_child("reference")
    p0, p0_capture = _run_child("p0")
    mismatches = _collect_mismatches(
        reference["result_strict_encoding"], p0["result_strict_encoding"]
    )
    q_equal = reference["m01"] == p0["m01"] == existing["selected_pose"]
    reference_p0_equal = not mismatches and q_equal
    p0_replays_existing = p0["result_fingerprint_sha256"] == existing_fp
    all_equal = reference_p0_equal and p0_replays_existing

    benchmark = {
        "schema": "ROUTE_C_V9F_REFERENCE_VS_P0_SINGLE_POSE_BENCHMARK_V2",
        "authority": "NONAUTHORITATIVE_REFERENCE_EQUIVALENCE_DIAGNOSTIC_ONLY",
        "method_sha256": base_method._sha256_path(Path(__file__).resolve()),
        "bindings": {
            "reference_evaluator_sha256": EXPECTED_REFERENCE_SHA256,
            "reference_archive_path": str(REFERENCE_SOURCE.resolve()),
            "reference_runtime_virtual_file": reference["runtime_virtual_file"],
            "active_p0_evaluator_sha256": overlay.EXPECTED_ACTIVE_SHA256,
            "active_p0_source_path": p0["source_path"],
            "active_p0_runtime_virtual_file": p0["runtime_virtual_file"],
            "existing_p0_benchmark_sha256": base_method._sha256_path(
                EXISTING_P0_BENCHMARK
            ),
            "existing_p0_result_fingerprint_sha256": existing_fp,
            "wrapper_sha256": preflight["external_manifest_audit"]["wrapper_sha256"],
            "external_manifest_sha256": preflight["external_manifest_audit"]["manifest_sha256"],
            "mission_contract_sha256": overlay.EXPECTED_MISSION_CONTRACT_SHA256,
            "strict_encoding_helper_path": str(BASE_BENCH_METHOD_PATH.resolve()),
            "strict_encoding_helper_sha256": helper_sha,
        },
        "selected_pose": reference["m01"],
        "measurement_definition": {
            "reference": "hash-pinned pre-performance evaluator; cold direct eval_clearance(q)",
            "p0": "active P0 evaluator; cold direct eval_clearance(q)",
            "initialization_stop": "controlled sentinel immediately before nominal mission sweep note",
            "process_isolation": "separate fresh subprocess per source",
            "warmup": "none",
            "repetitions": 1,
        },
        "reference": {
            "timing_seconds": reference["timing_seconds"],
            "process_capture": reference_capture,
            "result_fingerprint_sha256": reference["result_fingerprint_sha256"],
            "result_value_stats": reference["result_value_stats"],
            "negative_detail": reference["negative_detail"],
            "comparison_counts": reference["comparison_counts"],
            "j4_checks": reference["j4_checks"],
            "result_summary": reference["result_summary"],
        },
        "p0": {
            "timing_seconds": p0["timing_seconds"],
            "process_capture": p0_capture,
            "result_fingerprint_sha256": p0["result_fingerprint_sha256"],
            "result_value_stats": p0["result_value_stats"],
            "negative_detail": p0["negative_detail"],
            "comparison_counts": p0["comparison_counts"],
            "j4_checks": p0["j4_checks"],
            "result_summary": p0["result_summary"],
        },
        "exact_typed_binary64_equivalence": {
            "equal": reference_p0_equal,
            "q_equal": q_equal,
            "result_fingerprints_equal": (
                reference["result_fingerprint_sha256"]
                == p0["result_fingerprint_sha256"]
            ),
            "value_stats_equal": (
                reference["result_value_stats"] == p0["result_value_stats"]
            ),
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "comparison": "complete recursive type tags; every float compared by IEEE-754 binary64 bytes",
        },
        "three_way_binding": {
            "reference_equals_new_p0": reference_p0_equal,
            "new_p0_replays_existing_p0_fingerprint": p0_replays_existing,
            "all_three_equal": all_equal,
        },
        "full_sweep_executed": False,
        "active_source_modified": False,
        "active_input_modified": False,
        "active_output_written": False,
        "gate_credit": False,
        "release_credit": False,
        "next_stage_authorized": False,
        "verdict": (
            "REFERENCE_P0_SINGLE_POSE_EXACT_EQUIVALENCE_V2_PASS__NO_GATE_CREDIT"
            if all_equal
            else "REFERENCE_P0_SINGLE_POSE_EXACT_MISMATCH__STOP"
        ),
    }
    base_method._write_json_atomic(OUT_BENCHMARK, benchmark)
    print(json.dumps(benchmark["exact_typed_binary64_equivalence"], indent=2, sort_keys=True))
    print("WROTE %s" % OUT_BENCHMARK)
    return 0 if all_equal else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child-mode", choices=("reference", "p0"))
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    if args.child_mode:
        return _child(args.child_mode)
    if not args.run:
        parser.error("use --run or --child-mode reference|p0")
    return run_benchmark()


if __name__ == "__main__":
    raise SystemExit(main())
