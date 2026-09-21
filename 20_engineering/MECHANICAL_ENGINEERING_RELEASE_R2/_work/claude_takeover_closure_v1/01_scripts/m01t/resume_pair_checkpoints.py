"""Low-memory, resumable driver for the M01-C endpoint oracle.

This driver deliberately does not import OCP, NumPy, or the Scene.  It rebuilds
the exact task order from the already emitted pair universe, invokes one
geometry worker at a time, and writes a checkpoint only after a clean worker
return with a complete task-index-ordered JSON payload.  An interrupted worker
is left uncheckpointed; it can never masquerade as a completed UNKNOWN result.
"""
import csv
import json
import math
import os
import subprocess
import sys


PROJECT_ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
M01_OUT = os.path.join(
    PROJECT_ROOT,
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/"
    "claude_takeover_closure_v1/03_m01",
)
PAIR_UNIVERSE = os.path.join(M01_OUT, "M01_PAIR_UNIVERSE_V1.csv")
CHECKPOINT_DIR = os.path.join(M01_OUT, ".m01_pair_oracle_checkpoints")
WORKER = os.path.join(
    PROJECT_ROOT,
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/"
    "claude_takeover_closure_v1/01_scripts/m01t/parallel_oracle_worker.py",
)
RUN_ID = "R2_TERMINAL_CONVERGENCE_20260828_R1"
PRE = "PRE_RELEASE@q_start_STOW"
POST = "POST_RELEASE@q_goal_RELEASE_CLEAR"
CHUNK_COUNT = int(os.environ.get("M01_T3_CHUNKS", "32"))


def dump_json(obj, path):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


def checkpoint_path(index):
    return os.path.join(CHECKPOINT_DIR, f"M01_PAIR_ORACLE_CHUNK_{index:04d}_V1.json")


def is_reusable(path, expected_indices):
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        rows = doc.get("rows")
        if (doc.get("schema") != "M01_PAIR_ORACLE_CHUNK_CHECKPOINT_V1"
                or doc.get("named_run_id") != RUN_ID
                or doc.get("task_indices") != expected_indices
                or not isinstance(rows, list)
                or len(rows) != len(expected_indices)
                or [row.get("task_index") for row in rows] != expected_indices):
            return False
        # Process-return/invalid-output placeholders are not measurements.
        for row in rows:
            reason = str(row.get("failure_reason") or "")
            if (reason.startswith("ORACLE_WORKER_PROCESS_FAILURE:")
                    or reason.startswith("ORACLE_WORKER_INVALID_JSON")):
                return False
        return True
    except Exception:
        return False


def build_tasks():
    required = []
    with open(PAIR_UNIVERSE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["in_required_universe"] == "true":
                required.append(row)
    if len(required) != 11166:
        raise RuntimeError(f"required pair count drift: {len(required)}")

    tasks = []
    task_index = 0
    for row in required:
        a, b = row["object_a"], row["object_b"]
        if row["relative_motion_class"] == "RELATIVE_STATIC":
            tasks.append([task_index, PRE, a, b])
            task_index += 1
        else:
            tasks.append([task_index, PRE, a, b])
            task_index += 1
            tasks.append([task_index, POST, a, b])
            task_index += 1
    if task_index != 20865:
        raise RuntimeError(f"task count drift: {task_index}")
    return tasks


def main():
    if CHUNK_COUNT != 32:
        raise RuntimeError("resume contract requires the existing 32-chunk layout")
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    tasks = build_tasks()
    chunk_size = max(1, math.ceil(len(tasks) / CHUNK_COUNT))
    chunks = [tasks[i:i + chunk_size] for i in range(0, len(tasks), chunk_size)]
    if len(chunks) != CHUNK_COUNT:
        raise RuntimeError(f"chunk count drift: {len(chunks)}")

    for index, chunk in enumerate(chunks):
        expected = [task[0] for task in chunk]
        path = checkpoint_path(index)
        if is_reusable(path, expected):
            print(json.dumps({"chunk": index, "status": "REUSED",
                              "rows": len(chunk)}, ensure_ascii=False), flush=True)
            continue

        print(json.dumps({"chunk": index, "status": "RUNNING",
                          "rows": len(chunk)}, ensure_ascii=False), flush=True)
        proc = subprocess.run(
            [sys.executable, WORKER],
            input=json.dumps(chunk, ensure_ascii=False),
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"worker failed for chunk {index}: returncode={proc.returncode}; "
                f"stderr={proc.stderr[-500:]}"
            )
        try:
            rows = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"worker invalid JSON for chunk {index}") from exc
        if (not isinstance(rows, list)
                or [row.get("task_index") for row in rows] != expected):
            raise RuntimeError(f"worker task index mismatch for chunk {index}")

        dump_json({
            "schema": "M01_PAIR_ORACLE_CHUNK_CHECKPOINT_V1",
            "named_run_id": RUN_ID,
            "chunk_index": index,
            "checkpoint_status": "COMPLETE",
            "task_indices": expected,
            "rows": rows,
        }, path)
        print(json.dumps({"chunk": index, "status": "COMPLETE",
                          "rows": len(rows)}, ensure_ascii=False), flush=True)

    print(json.dumps({"status": "ALL_32_CHECKPOINTS_COMPLETE",
                      "tasks": len(tasks)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
