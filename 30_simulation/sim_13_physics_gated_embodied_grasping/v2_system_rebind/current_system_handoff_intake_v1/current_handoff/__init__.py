"""Fail-closed CURRENT_SYSTEM_HANDOFF_INTAKE_V1 source-freeze package."""

from .evaluator import evaluate_default_snapshot
from .strict_io import IntakeError, load_default_snapshot

__all__ = ["IntakeError", "evaluate_default_snapshot", "load_default_snapshot"]
