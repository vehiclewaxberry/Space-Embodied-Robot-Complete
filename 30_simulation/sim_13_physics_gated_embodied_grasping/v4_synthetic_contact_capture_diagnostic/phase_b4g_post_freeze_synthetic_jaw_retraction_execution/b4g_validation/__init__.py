"""Independent, read-only validation for the frozen B4G evidence bundle."""

from .validator import ValidationReport, validate_b4g

__all__ = ["ValidationReport", "validate_b4g"]
