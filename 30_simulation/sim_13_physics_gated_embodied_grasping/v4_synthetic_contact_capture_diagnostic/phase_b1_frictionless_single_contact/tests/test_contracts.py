from __future__ import annotations

import hashlib
import json
from pathlib import Path

from b1_contact.contact_kernel import (
    CURRENT_SYSTEM_BOUND,
    DUAL_CONTACT_IMPLEMENTED,
    FORMAL_NC19_CREDIT,
    FRICTION_IMPLEMENTED,
    GRASP_SUCCESS_CLAIMED,
    LOCK_IMPLEMENTED,
    NEXT_STAGE_AUTHORIZED,
    PRODUCTION_CONTACT_BACKEND,
    RELEASE_AUTHORIZED,
    SOFT_CAPTURE_IMPLEMENTED,
    ContactConfig,
)


HERE = Path(__file__).resolve().parents[1]
PHASE_A = HERE.parent


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_provisional_si_parameters_and_rp_units_are_explicit():
    config = ContactConfig().validated()
    assert config.sphere_radius_m == 0.12
    assert config.normal_stiffness_n_m == 8_000.0
    assert config.normal_damping_n_s_m == 12.0
    contract = json.loads((HERE / "contracts/PHASE_B1_MODEL_CONTRACT_V1.json").read_text(encoding="utf-8"))
    assert contract["provisional_contact_values"]["status"] == "SYNTHETIC_PROVISIONAL_NOT_B601"
    assert contract["dimensional_partitions"]["R"]["effort"] == "N*m"
    assert contract["dimensional_partitions"]["P"]["effort"] == "N"
    assert contract["dimensional_partitions"]["mixed_P_H_norm_forbidden"] is True


def test_phase_a_public_model_and_audited_gate_are_exactly_hash_bound():
    contract = json.loads((HERE / "contracts/PHASE_B1_MODEL_CONTRACT_V1.json").read_text(encoding="utf-8"))
    upstream = contract["phase_a_v3_read_only_upstream"]
    assert _sha(PHASE_A / "sim13_v4a/full_floating.py") == upstream["public_model_sha256"]
    assert _sha(PHASE_A / "results/SIM13_V4A_PHASE_A_AUDITED_GATE_V3.json") == upstream["audited_gate_sha256"]


def test_all_formal_production_grasp_release_boundaries_remain_false():
    assert not any(
        (
            FRICTION_IMPLEMENTED,
            DUAL_CONTACT_IMPLEMENTED,
            SOFT_CAPTURE_IMPLEMENTED,
            LOCK_IMPLEMENTED,
            GRASP_SUCCESS_CLAIMED,
            CURRENT_SYSTEM_BOUND,
            PRODUCTION_CONTACT_BACKEND,
            FORMAL_NC19_CREDIT,
            RELEASE_AUTHORIZED,
            NEXT_STAGE_AUTHORIZED,
        )
    )
    governance = json.loads((HERE / "contracts/PHASE_B1_GOVERNANCE_CONTRACT_V1.json").read_text(encoding="utf-8"))
    assert not any(governance["authority"].values())
    assert governance["formal_sim13_v2_state"]["passed"] == 15
    assert governance["formal_sim13_v2_state"]["declared"] == 20


def test_no_urdf_interface_authorization_or_cache_artifact_exists():
    names = [path.relative_to(HERE).as_posix().lower() for path in HERE.rglob("*")]
    assert not any(name.endswith(".urdf") for name in names)
    assert not any("interface" in Path(name).name for name in names)
    assert not any("authorization" in Path(name).name for name in names)
    assert not any(part in {"__pycache__", ".pytest_cache"} for name in names for part in Path(name).parts)
