from __future__ import annotations

from pathlib import Path

from sim13_v4a.full_floating import (
    CONTACT_IMPLEMENTED,
    CURRENT_SYSTEM_BOUND,
    FORMAL_NC19_CREDIT,
    PRODUCTION_BACKEND,
    SCOPE,
)


ROOT = Path(__file__).resolve().parents[1]


def test_phase_a_authority_and_contact_boundaries_remain_false() -> None:
    assert SCOPE == "SYNTHETIC_ONLY_FULL_FLOATING_NO_CONTACT_PHASE_A_DIAGNOSTIC"
    assert CONTACT_IMPLEMENTED is False
    assert CURRENT_SYSTEM_BOUND is False
    assert PRODUCTION_BACKEND is False
    assert FORMAL_NC19_CREDIT is False


def test_no_urdf_interface_or_authorization_artifact_exists() -> None:
    assert list(ROOT.rglob("*.urdf")) == []
    forbidden_names = {
        "MECH_RL_SYSTEM_INTERFACE_V2.yaml",
        "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json",
    }
    assert not any(path.name in forbidden_names for path in ROOT.rglob("*"))
