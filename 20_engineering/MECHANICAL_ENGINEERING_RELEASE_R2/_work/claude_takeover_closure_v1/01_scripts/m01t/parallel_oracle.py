"""Process-isolated endpoint oracle worker for the M01 takeover package.

The worker is deliberately kept separate from the top-level pair builder so
Windows ``spawn`` does not re-enter that builder in child processes.  It only
loads the current hash-bound Scene and evaluates one endpoint pair task.
"""
from .oracle import PoseContext, Scene, pair_query

_SCENE = None
_CONTEXTS = None


def init_worker(q_start, q_goal):
    global _SCENE, _CONTEXTS
    _SCENE = Scene()
    _CONTEXTS = {
        "PRE_RELEASE@q_start_STOW": PoseContext(_SCENE, q_start, 0.0, 0.0),
        "POST_RELEASE@q_goal_RELEASE_CLEAR": PoseContext(_SCENE, q_goal, 0.0, 0.0),
    }


def query_task(task):
    """Return ``(task_index, row)`` for deterministic ordered collection."""
    idx, config_name, object_a, object_b = task
    row = pair_query(
        _SCENE,
        _CONTEXTS[config_name],
        object_a,
        object_b,
        required_mm=0.0,
    )
    row["configuration_domain"] = "ENDPOINT_CONFIGURATION"
    row["stage"] = config_name
    row["task_index"] = idx
    return idx, row
