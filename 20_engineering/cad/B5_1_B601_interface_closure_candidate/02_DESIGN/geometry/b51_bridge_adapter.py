"""STEP generator for the B5.1 bridge-adapter engineering candidate."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from b51_geometry_common import (  # noqa: E402
    ADMITTED,
    assert_bounds_and_validity,
    assert_central_passage_clear,
    assert_pairwise_no_volume_overlap,
    build_bridge_adapter,
)


def gen_step():
    model = build_bridge_adapter()
    assert_bounds_and_validity(
        model,
        (ADMITTED["task_face_x_mm"], ADMITTED["mount_plane_x_mm"]),
    )
    assert_central_passage_clear(model)
    assert_pairwise_no_volume_overlap(model)
    return model
