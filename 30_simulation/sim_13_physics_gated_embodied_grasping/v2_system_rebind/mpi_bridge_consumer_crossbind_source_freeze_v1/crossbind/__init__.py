"""Source-only MPI physical-to-dynamics consumer cross-binding contracts."""

from .bridge import build_crossbind_record, recompute_bridge
from .policy import PolicyError, admit_consumer, make_valid_plan, validate_consumer_plan
from .receipt import ReceiptError, make_synthetic_v3_fixture, validate_system_binding_v3
from .source_bundle import SourceBundleError, load_source_bundle

__all__ = [
    "PolicyError",
    "ReceiptError",
    "SourceBundleError",
    "admit_consumer",
    "build_crossbind_record",
    "load_source_bundle",
    "make_synthetic_v3_fixture",
    "make_valid_plan",
    "recompute_bridge",
    "validate_consumer_plan",
    "validate_system_binding_v3",
]

