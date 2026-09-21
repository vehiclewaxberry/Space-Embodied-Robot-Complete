"""Synthetic prebind runtime-guard diagnostic for Sim13.

Nothing in this package is a current-system, contact, production, or release
binding.  The only dynamics admitted here are the public V3 synthetic 6R+2P
fixture and its public reduced solver.
"""

DIAGNOSTIC_SCOPE = "SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY"
CURRENT_SYSTEM_BINDING_PASSED = False
RUNTIME_PRODUCTION_GATE_PASSED = False
CONTACT_GRASP_GATE_PASSED = False
RELEASE_CREDIT = False
NEXT_STAGE_AUTHORIZED = False

__all__ = (
    "CONTACT_GRASP_GATE_PASSED",
    "CURRENT_SYSTEM_BINDING_PASSED",
    "DIAGNOSTIC_SCOPE",
    "NEXT_STAGE_AUTHORIZED",
    "RELEASE_CREDIT",
    "RUNTIME_PRODUCTION_GATE_PASSED",
)
