"""STEP generator for the B5.1 G07 main-arm double-triangle saddle."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from b51_geometry_common import (  # noqa: E402
    MAIN_SADDLE,
    assert_bounds_and_validity,
    assert_pairwise_no_volume_overlap,
    build_saddle,
)


def gen_step():
    model = build_saddle(MAIN_SADDLE)
    assert_bounds_and_validity(model, MAIN_SADDLE.x_window)
    assert_pairwise_no_volume_overlap(model)
    return model
