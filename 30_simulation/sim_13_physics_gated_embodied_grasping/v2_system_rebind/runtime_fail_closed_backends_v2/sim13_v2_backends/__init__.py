"""Sim13 V2 runtime fail-closed production-intent backends (NC15/16/18/19/20).

Every backend in this package is fail-closed: UNKNOWN is never PASS, absent or
hash-drifted sources abort loading, and no module grants release credit.
"""

from __future__ import annotations

__all__ = [
    "canonical",
    "capability",
    "contact_backend",
    "dynamics_backend",
    "feasibility_evaluator",
    "runtime_gate_adapter",
    "snapshot_receipt",
]
