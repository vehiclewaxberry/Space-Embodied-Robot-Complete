"""Source-only security contracts for the dormant Sim13 V2 system rebind.

Nothing in this package emits a URDF, loads a dynamics backend, or grants a
non-ABORT action.  The public functions are parsers and fail-closed contract
kernels exercised only with synthetic fixtures in this release.
"""

from .interface_contract import parse_interface_candidate
from .receipts import (
    ReplayStore,
    admit_backend_request,
    evaluate_receipt_bound_join,
    issue_synthetic_receipt,
    verify_receipt,
)
from .strict_json import canonical_digest, loads_strict
from .transaction_contract import validate_transaction_contract, validate_transition_trace
from .urdf_contract import build_synthetic_parser_fixture_bytes, validate_system_urdf_bytes

__all__ = [
    "ReplayStore",
    "admit_backend_request",
    "build_synthetic_parser_fixture_bytes",
    "canonical_digest",
    "evaluate_receipt_bound_join",
    "issue_synthetic_receipt",
    "loads_strict",
    "parse_interface_candidate",
    "validate_system_urdf_bytes",
    "validate_transaction_contract",
    "validate_transition_trace",
    "verify_receipt",
]
