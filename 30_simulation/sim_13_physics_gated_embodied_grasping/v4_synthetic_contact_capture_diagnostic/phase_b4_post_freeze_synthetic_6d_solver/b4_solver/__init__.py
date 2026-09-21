"""Post-freeze synthetic six-constraint acquisition/propagation diagnostics.

This package is deliberately isolated from the frozen B4 contract package.
Nothing here is a physical gripper, latch, release, current-system, or NC19
implementation.
"""

from .constraint_solver import (
    AcquisitionResult,
    ActiveRunResult,
    SnapshotTransform,
    SolverError,
    acquisition_projection,
    build_snapshot,
    certify_earliest_clearance,
    execute_run,
    extract_frozen_primary_event,
    run_negative_controls,
    verify_bound_sources,
)

__all__ = [
    "AcquisitionResult",
    "ActiveRunResult",
    "SnapshotTransform",
    "SolverError",
    "acquisition_projection",
    "build_snapshot",
    "certify_earliest_clearance",
    "execute_run",
    "extract_frozen_primary_event",
    "run_negative_controls",
    "verify_bound_sources",
]
