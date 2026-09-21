"""Phase-B2 synthetic regularized-friction single-contact diagnostic."""

from .friction_kernel import (
    FrictionConfig,
    FrictionHistory,
    FrictionObservation,
    deterministic_friction_scenario,
    evaluate_friction_contact,
    integrate_friction_contact,
    no_contact_regression,
    run_negative_controls,
    summarize_friction_history,
)

__all__ = (
    "FrictionConfig",
    "FrictionHistory",
    "FrictionObservation",
    "deterministic_friction_scenario",
    "evaluate_friction_contact",
    "integrate_friction_contact",
    "no_contact_regression",
    "run_negative_controls",
    "summarize_friction_history",
)
