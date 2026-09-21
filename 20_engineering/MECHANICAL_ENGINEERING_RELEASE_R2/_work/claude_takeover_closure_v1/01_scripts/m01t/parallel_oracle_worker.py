"""Standalone subprocess worker for M01 endpoint pair queries.

The parent builder sends a JSON task list on stdin.  This file is intentionally
an executable worker rather than an imported module, so Windows process spawn
cannot re-enter the parent builder.  Any per-pair exception is returned as
UNKNOWN; it is never converted to SAFE/PASS.
"""
import json
import os
import sys

PROJECT_ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

from m01t.oracle import PoseContext, Scene, pair_query  # noqa: E402


def jsonable(value):
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def main():
    tasks = json.load(sys.stdin)
    q_start = [2.540711, -2.932153, -0.994838, -0.718081, -0.365716, -0.05236]
    q_goal = [-1.570796, -2.094395, -2.094395, -1.047198, -0.523599, 0.0]
    scene = Scene()
    contexts = {
        "PRE_RELEASE@q_start_STOW": PoseContext(scene, q_start, 0.0, 0.0),
        "POST_RELEASE@q_goal_RELEASE_CLEAR": PoseContext(scene, q_goal, 0.0, 0.0),
    }
    output = []
    for task in tasks:
        idx, config_name, object_a, object_b = task
        try:
            row = pair_query(scene, contexts[config_name], object_a, object_b, required_mm=0.0)
        except Exception as exc:  # fail closed at the pair boundary
            row = {
                "object_a": object_a,
                "object_b": object_b,
                "oracle_type": None,
                "exact_or_conservative": None,
                "result": "UNKNOWN",
                "minimum_distance_mm": None,
                "witness_a_S_mm": None,
                "witness_b_S_mm": None,
                "failure_reason": f"ORACLE_EXCEPTION_WORKER:{type(exc).__name__}",
                "rungs": [],
            }
        row["configuration_domain"] = "ENDPOINT_CONFIGURATION"
        row["stage"] = config_name
        row["task_index"] = idx
        output.append(jsonable(row))
    sys.stdout.write(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
