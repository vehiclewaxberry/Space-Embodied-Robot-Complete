"""Sim13 V3 Phase-A generic in-memory dynamics diagnostic.

This package is deliberately non-production and SYNTHETIC_ONLY.  It neither
builds nor loads the Unified-R2 current-system candidate.
"""

from pathlib import Path
import sys


_V3_ROOT = Path(__file__).resolve().parents[1]
_V2_ROOT = _V3_ROOT.parent / "v2_system_rebind"
if str(_V2_ROOT) not in sys.path:
    sys.path.insert(0, str(_V2_ROOT))

__all__ = (
    "ZeroMomentumReducedDynamics",
    "build_synthetic_8dof_model",
    "propagate_target_6dof",
)
