"""Phase-B3 synthetic branched dual-contact soft-capture diagnostic."""

from .branched_model import BranchedGripperServiceModel
from .dual_contact_kernel import (
    DualContactConfig,
    DualContactHistory,
    deterministic_dual_contact_scenario,
    integrate_dual_contact,
    summarize_dual_contact_history,
)

__all__ = (
    "BranchedGripperServiceModel",
    "DualContactConfig",
    "DualContactHistory",
    "deterministic_dual_contact_scenario",
    "integrate_dual_contact",
    "summarize_dual_contact_history",
)
