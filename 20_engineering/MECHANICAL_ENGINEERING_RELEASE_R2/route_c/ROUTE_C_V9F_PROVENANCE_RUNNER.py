#!/usr/bin/env python3
"""Run a V9F FAST evaluator with source/output provenance bound in one receipt.

This wrapper executes the exact pinned evaluator bytes in a child interpreter.
For the archived reference, ``__file__`` is deliberately mapped to the active
Route-C directory so its original HERE-relative inputs and outputs retain the
same semantics as the historical launch.  Existing target outputs are moved to
a run-specific recoverable archive before launch; nothing is deleted.
"""

from __future__ import annotations

import argparse
import builtins
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
WORK = HERE / "_work" / "v9f_provenance_runs"
FAKE_EVALUATOR_PATH = HERE / "ROUTE_C_EXACT_SWEEP_V9F.py"

REFERENCE_SOURCE = (
    HERE
    / "_work"
    / "v9f_evaluator_pre_redteam_fix"
    / "ROUTE_C_EXACT_SWEEP_V9F_PRE_PERFORMANCE_REFERENCE.py"
)
P0_SOURCE = HERE / "ROUTE_C_EXACT_SWEEP_V9F.py"

ROLE = {
    "reference": {
        "receipt_role": "REFERENCE_FAST",
        "source": REFERENCE_SOURCE,
        "source_sha256": "46732BB71605E6EE52488C6324FB47E5E7C009490A3E94F49DE95EC2B0DF6244",
        "tag": "",
        "outputs": [
            "ROUTE_C_EXACT_SWEEP_V9F.json",
            "ROUTE_C_ROBUST_MARGIN_LEDGER_V9F.csv",
            "ROUTE_C_MISSION_COVERAGE_GATE_V9F.json",
        ],
        "receipt": "ROUTE_C_V9F_FAST_REFERENCE_RUN_RECEIPT.json",
    },
    "p0": {
        "receipt_role": "P0_FAST",
        "source": P0_SOURCE,
        "source_sha256": "9F26AC9A8DE5E2EEB57103F07B769EB43AC30A8FBAFD90FE8DF5D501FA8C8A7F",
        "tag": "P0_BENCH",
        "outputs": [
            "ROUTE_C_EXACT_SWEEP_V9F_P0_BENCH.json",
            "ROUTE_C_ROBUST_MARGIN_LEDGER_V9F_P0_BENCH.csv",
            "ROUTE_C_MISSION_COVERAGE_GATE_V9F_P0_BENCH.json",
        ],
        "receipt": "ROUTE_C_V9F_FAST_P0_BENCH_RUN_RECEIPT.json",
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolved_child(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def checked_paths(config: dict[str, Any], run_id: str) -> tuple[list[Path], Path, Path]:
    if re.fullmatch(r"[A-Z0-9_-]{1,64}", run_id) is None:
        raise ValueError("run-id must match [A-Z0-9_-]{1,64}")
    outputs = [HERE / name for name in config["outputs"]]
    receipt = HERE / config["receipt"]
    archive = WORK / run_id / "preexisting"
    for path in [*outputs, receipt, archive]:
        if not resolved_child(path, HERE):
            raise ValueError(f"path escapes Route-C directory: {path}")
    return outputs, receipt, archive


def isolate_preexisting(paths: list[Path], archive: Path) -> list[dict[str, str]]:
    archive.mkdir(parents=True, exist_ok=True)
    moved: list[dict[str, str]] = []
    for path in paths:
        if not path.exists():
            continue
        target = archive / path.name
        if target.exists():
            raise FileExistsError(f"archive target already exists: {target}")
        before = sha256_file(path)
        shutil.move(str(path), str(target))
        after = sha256_file(target)
        if before != after:
            raise RuntimeError(f"recoverable archive hash mismatch: {path.name}")
        moved.append(
            {
                "from": path.name,
                "to": str(target.relative_to(HERE)).replace("\\", "/"),
                "sha256": after,
            }
        )
    return moved


def child_exec(role_name: str) -> int:
    config = ROLE[role_name]
    source = Path(config["source"])
    source_bytes = source.read_bytes()
    actual = sha256_bytes(source_bytes)
    if actual != config["source_sha256"]:
        print(
            f"ABORT: {role_name} source SHA mismatch: {actual} != {config['source_sha256']}",
            flush=True,
        )
        return 3
    os.environ["RC_FAST"] = "1"
    if config["tag"]:
        os.environ["RC_FAST_OUTPUT_TAG"] = config["tag"]
    else:
        os.environ.pop("RC_FAST_OUTPUT_TAG", None)
    staging_text = os.environ.get("RC_PROVENANCE_STAGING_DIR", "")
    if not staging_text:
        print("ABORT: RC_PROVENANCE_STAGING_DIR is required", flush=True)
        return 3
    staging = Path(staging_text).resolve()
    if not resolved_child(staging, WORK):
        print("ABORT: staging directory escapes provenance work root", flush=True)
        return 3
    staging.mkdir(parents=True, exist_ok=True)
    output_map = {
        str((HERE / name).resolve()).casefold(): staging / name
        for name in config["outputs"]
    }
    real_open = builtins.open

    def provenance_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        try:
            resolved = str(Path(os.fspath(file)).resolve()).casefold()
        except (TypeError, ValueError, OSError):
            resolved = ""
        writing = any(flag in mode for flag in ("w", "a", "x", "+"))
        if writing and resolved in output_map:
            return real_open(output_map[resolved], mode, *args, **kwargs)
        return real_open(file, mode, *args, **kwargs)

    child_builtins = dict(vars(builtins))
    child_builtins["open"] = provenance_open
    namespace = {
        "__name__": "__main__",
        "__file__": str(FAKE_EVALUATOR_PATH),
        "__package__": None,
        "__cached__": None,
        "__builtins__": child_builtins,
    }
    code = compile(source_bytes, str(FAKE_EVALUATOR_PATH), "exec")
    exec(code, namespace, namespace)
    return 0


def parent_run(role_name: str, run_id: str, check_only: bool) -> int:
    config = ROLE[role_name]
    source = Path(config["source"])
    outputs, receipt_path, archive = checked_paths(config, run_id)
    if not source.is_file():
        print(f"ABORT: missing source: {source}", flush=True)
        return 3
    source_before = sha256_file(source)
    runner_before = sha256_file(Path(__file__).resolve())
    source_match = source_before == config["source_sha256"]
    if check_only:
        payload = {
            "role": role_name,
            "source": str(source.relative_to(HERE)).replace("\\", "/"),
            "source_sha256": source_before,
            "source_match": source_match,
            "outputs": [path.name for path in outputs],
            "receipt": receipt_path.name,
            "archive": str(archive.relative_to(HERE)).replace("\\", "/"),
            "runner_sha256": runner_before,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
        return 0 if source_match else 3
    if not source_match:
        print(
            f"ABORT: source SHA mismatch: {source_before} != {config['source_sha256']}",
            flush=True,
        )
        return 3

    run_dir = archive.parent
    if run_dir.exists():
        print(f"ABORT: immutable run-id directory already exists: {run_dir}", flush=True)
        return 4
    moved = isolate_preexisting([*outputs, receipt_path], archive)
    staging = run_dir / "staging"
    staging.mkdir(parents=True, exist_ok=False)
    log_path = run_dir / "child_stdout_stderr.log"
    start_utc = utc_now()
    command = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--child",
        role_name,
    ]
    env = os.environ.copy()
    env["RC_FAST"] = "1"
    if config["tag"]:
        env["RC_FAST_OUTPUT_TAG"] = config["tag"]
    else:
        env.pop("RC_FAST_OUTPUT_TAG", None)
    env["RC_PROVENANCE_STAGING_DIR"] = str(staging)

    with log_path.open("w", encoding="utf-8", newline="\n") as log_stream:
        process = subprocess.Popen(
            command,
            cwd=str(HERE),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log_stream.write(line)
            log_stream.flush()
        child_exit = process.wait()

    end_utc = utc_now()
    source_after = sha256_file(source)
    runner_after = sha256_file(Path(__file__).resolve())
    staged_outputs = [staging / path.name for path in outputs]
    staged_complete = all(path.is_file() and path.stat().st_size > 0 for path in staged_outputs)
    staged_output_hashes = {
        path.name: sha256_file(path)
        for path in staged_outputs
        if path.is_file() and path.stat().st_size > 0
    }
    prepublish_archive = run_dir / "concurrent_pre_publish"
    prepublish_moved: list[dict[str, str]] = []
    publish_performed = False
    if child_exit == 0 and staged_complete:
        prepublish_moved = isolate_preexisting(outputs, prepublish_archive)
        for staged, final in zip(staged_outputs, outputs):
            os.replace(staged, final)
        publish_performed = True
    output_complete = all(path.is_file() and path.stat().st_size > 0 for path in outputs)
    output_hashes = {
        path.name: sha256_file(path)
        for path in outputs
        if path.is_file() and path.stat().st_size > 0
    }
    staging_publish_hash_match = (
        staged_complete
        and publish_performed
        and output_complete
        and staged_output_hashes == output_hashes
    )
    complete = (
        child_exit == 0
        and staged_complete
        and publish_performed
        and output_complete
        and staging_publish_hash_match
        and source_before == source_after
        and runner_before == runner_after
    )
    receipt = {
        "schema": "ROUTE_C_V9F_PROVENANCE_RUN_RECEIPT_V1",
        "generated_utc": end_utc,
        "role": config["receipt_role"],
        "run_id": run_id,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "command": command,
        "cwd": str(HERE),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "fast_mode": True,
        "fast_output_tag": config["tag"],
        "source_path": str(source.relative_to(HERE)).replace("\\", "/"),
        "source_sha256": source_before,
        "source_sha256_after": source_after,
        "source_unchanged_across_run": source_before == source_after,
        "runner_path": Path(__file__).name,
        "runner_sha256": runner_before,
        "runner_sha256_after": runner_after,
        "runner_unchanged_across_run": runner_before == runner_after,
        "fake_evaluator_file_for_here_semantics": str(FAKE_EVALUATOR_PATH),
        "execution_mode": "PINNED_SOURCE_BYTES_COMPILE_EXEC_WITH_BUILTIN_OPEN_OUTPUT_REDIRECT",
        "isolated_staging_directory": str(staging.relative_to(HERE)).replace("\\", "/"),
        "staged_output_set_complete": staged_complete,
        "staged_output_sha256": staged_output_hashes,
        "publish_performed": publish_performed,
        "published_output_sha256": output_hashes,
        "staging_publish_hash_match": staging_publish_hash_match,
        "output_publish_from_isolated_staging": publish_performed,
        "preexisting_outputs_moved_to_archive": True,
        "preexisting_archive": str(archive.relative_to(HERE)).replace("\\", "/"),
        "preexisting_moved": moved,
        "concurrent_pre_publish_moved": prepublish_moved,
        "child_log": str(log_path.relative_to(HERE)).replace("\\", "/"),
        "child_log_sha256": sha256_file(log_path),
        "child_exit_code": child_exit,
        "output_set_complete": output_complete,
        "output_sha256": output_hashes,
        "completed": complete,
        "recoverability_scope": "LAUNCH_PREEXISTING_AND_PREPUBLISH_SNAPSHOTS__UNCOOPERATIVE_WRITER_RACE_NOT_CLAIMED",
        "authority": "EXECUTION_PROVENANCE_ONLY__NO_GEOMETRY_OR_RELEASE_CREDIT",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"receipt: {receipt_path.name}", flush=True)
    print(f"completed: {complete}", flush=True)
    return 0 if complete else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=sorted(ROLE))
    parser.add_argument("--run-id")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--child", choices=sorted(ROLE), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        return args
    if not args.role or not args.run_id:
        parser.error("--role and --run-id are required")
    return args


def main() -> int:
    args = parse_args()
    if args.child:
        return child_exec(args.child)
    return parent_run(args.role, args.run_id, args.check_only)


if __name__ == "__main__":
    sys.exit(main())
