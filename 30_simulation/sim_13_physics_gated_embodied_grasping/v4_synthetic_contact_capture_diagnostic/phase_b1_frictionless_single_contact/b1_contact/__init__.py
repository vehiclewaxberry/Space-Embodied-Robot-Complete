"""Phase-B1 synthetic frictionless single-contact diagnostic."""

from .contact_kernel import (
    ABORT_STATE,
    ContactConfig,
    ContactError,
    ContactHistory,
    ContactObservation,
    deterministic_contact_scenario,
    evaluate_contact,
    integrate_contact,
    no_contact_regression,
    run_negative_controls,
    summarize_history,
)

__all__ = (
    "ABORT_STATE",
    "ContactConfig",
    "ContactError",
    "ContactHistory",
    "ContactObservation",
    "deterministic_contact_scenario",
    "evaluate_contact",
    "integrate_contact",
    "no_contact_regression",
    "run_negative_controls",
    "summarize_history",
)
