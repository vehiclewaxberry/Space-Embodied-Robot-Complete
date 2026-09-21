"""STEP generator for the B5.1 G08 gripper double-triangle saddle."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from b51_geometry_common import (  # noqa: E402
    GRIP_SADDLE,
    assert_bounds_and_validity,
    assert_pairwise_no_volume_overlap,
    build_saddle,
)


def gen_step():
    model = build_saddle(GRIP_SADDLE)
    assert_bounds_and_validity(model, GRIP_SADDLE.x_window)
    assert_pairwise_no_volume_overlap(model)
    return model
