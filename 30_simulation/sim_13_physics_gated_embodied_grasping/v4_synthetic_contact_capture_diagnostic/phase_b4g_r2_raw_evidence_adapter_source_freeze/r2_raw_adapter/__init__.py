"""Source-only raw-evidence adapter for the frozen Sim13 B4G-R2 design.

The package parses already-existing evidence.  It never advances a state,
imports a solver, creates trajectory output, or grants scientific credit.
"""

from .adapter import (
    AdapterError,
    BoundRawCase,
    aggregate_g12_raw,
    derive_common_propagation_observation,
    derive_fresh_acquisition_observation,
    evaluate_a0_bookend_pair,
    evaluate_a0_bookend_raw,
    evaluate_fresh_alpha16_raw,
    evaluate_g12_raw_pair,
    load_bound_case,
    validate_raw_registry_structure,
)

__all__ = [
    "AdapterError",
    "BoundRawCase",
    "aggregate_g12_raw",
    "derive_common_propagation_observation",
    "derive_fresh_acquisition_observation",
    "evaluate_a0_bookend_pair",
    "evaluate_a0_bookend_raw",
    "evaluate_fresh_alpha16_raw",
    "evaluate_g12_raw_pair",
    "load_bound_case",
    "validate_raw_registry_structure",
]
