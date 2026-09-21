"""Independent bridge recomputation and immutable semantic record."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .constants import CHANNELS, MANDATORY_FALSE_FLAGS, SOURCE_PIN_BY_ID
from .source_bundle import SourceBundle
from .strict_io import canonical_json_bytes, deep_freeze, sha256_bytes


class BridgeError(ValueError):
    """Bridge derivation or authority semantics mismatch."""


def validate_crossbind_record_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Enforce the no-double-bridge wording and uncertainty classification."""

    try:
        consumer = payload["consumer_crossbind"]
        mass = payload["mass_inertia_binding"]
    except (KeyError, TypeError) as exc:
        raise BridgeError("CROSSBIND_RECORD_STRUCTURE_MISSING") from exc
    if consumer.get("lineage_rule") != "EACH_CHANNEL_HAS_THE_COMPLETE_PHYSICAL_TO_DYNAMICS_BRIDGE_LINEAGE_EXACTLY_ONCE":
        raise BridgeError("CROSSBIND_COMPLETE_LINEAGE_RULE_DRIFT")
    expected_numeric = "FRAME_WRENCH_COLLISION_APPLY_ONCE__MASS_INERTIA_BIND_UPSTREAM_BRIDGED_LEDGER_WITH_ZERO_CONSUMER_REAPPLICATION"
    if consumer.get("consumer_boundary_numeric_rule") != expected_numeric:
        raise BridgeError("CROSSBIND_NUMERIC_APPLICATION_WORDING_DRIFT")
    if "uncertainty" in mass:
        raise BridgeError("MASS_INERTIA_GENERIC_UNCERTAINTY_FIELD_FORBIDDEN")
    transform_uncertainty = mass.get("bridge_transform_uncertainty")
    if transform_uncertainty != {
        "standard_uncertainty": None,
        "status": "UNKNOWN",
        "distribution": None,
        "degrees_of_freedom": None,
    }:
        raise BridgeError("BRIDGE_TRANSFORM_UNCERTAINTY_DRIFT")
    if mass.get("member_mass_inertia_uncertainties") != "PRESERVED_VERBATIM_FROM_SYSTEM_MASS_PROPERTIES_BRIDGED_V1":
        raise BridgeError("MEMBER_MASS_INERTIA_UNCERTAINTY_PRESERVATION_DRIFT")
    return {
        "complete_lineage_exactly_once": True,
        "consumer_numeric_applications": {"frame": 1, "mass": 0, "inertia": 0, "wrench": 1, "collision_geometry": 1},
        "bridge_transform_uncertainty_status": "UNKNOWN",
        "member_uncertainties_preserved": True,
    }


def _matrix4(value: Any, field: str) -> list[list[float]]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise BridgeError(f"INVALID_MATRIX_SHAPE:{field}")
    rows: list[list[float]] = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            raise BridgeError(f"INVALID_MATRIX_SHAPE:{field}")
        rows.append([float(item) for item in row])
    return rows


def _rigid_inverse(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    rotation = [[matrix[i][j] for j in range(3)] for i in range(3)]
    translation = [matrix[i][3] for i in range(3)]
    out = [[0.0] * 4 for _ in range(4)]
    for i in range(3):
        for j in range(3):
            out[i][j] = rotation[j][i]
        out[i][3] = -sum(rotation[j][i] * translation[j] for j in range(3))
    out[3] = [0.0, 0.0, 0.0, 1.0]
    return out


def _matmul(left: Sequence[Sequence[float]], right: Sequence[Sequence[float]]) -> list[list[float]]:
    return [[sum(left[i][k] * right[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _max_abs(left: Sequence[Sequence[float]], right: Sequence[Sequence[float]]) -> float:
    return max(abs(left[i][j] - right[i][j]) for i in range(4) for j in range(4))


def recompute_bridge(bridge_document: Mapping[str, Any]) -> dict[str, Any]:
    semantics = bridge_document["frame_semantics"]
    convention = semantics["convention"]
    required = "row-major 4x4 homogeneous T_parent_child: p_parent = T_parent_child @ p_child"
    if required not in convention:
        raise BridgeError("ROW_MAJOR_PARENT_CHILD_SEMANTICS_MISSING")
    dynamics = _matrix4(semantics["T_S_A0_dynamics"]["transform_S_A0_rows_m"], "T_S_A0_dynamics")
    physical = _matrix4(semantics["T_S_A0_physical"]["transform_S_A0_rows_m"], "T_S_A0_physical")
    stored = _matrix4(bridge_document["T_PHYSICAL_TO_DYNAMIC"]["homogeneous_4x4"], "T_PHYSICAL_TO_DYNAMIC")
    inverse_stored = _matrix4(
        bridge_document["T_DYNAMIC_TO_PHYSICAL_inverse_bridge"]["homogeneous_4x4"],
        "T_DYNAMIC_TO_PHYSICAL_inverse_bridge",
    )
    derived = _matmul(_rigid_inverse(dynamics), physical)
    residual = _max_abs(derived, stored)
    exact = derived == stored
    if not exact or residual != 0.0:
        raise BridgeError(f"PHYSICAL_TO_DYNAMICS_BRIDGE_MISMATCH:{residual:.17g}")
    inverse_direction_residual = _max_abs(derived, inverse_stored)
    if inverse_direction_residual <= 1.0e-6:
        raise BridgeError("BRIDGE_DIRECTION_NOT_DISTINGUISHABLE")
    closure = _matmul(dynamics, stored)
    closure_residual = _max_abs(closure, physical)
    if closure_residual != 0.0:
        raise BridgeError(f"BRIDGE_CLOSURE_MISMATCH:{closure_residual:.17g}")
    uncertainty = {"standard_uncertainty": None, "status": "UNKNOWN", "distribution": None, "degrees_of_freedom": None}
    transform_meta = {
        "unit": {"rotation": "1", "translation": "m", "homogeneous_bottom_row": "1"},
        "frames": {"from": "A0_PHYSICAL_WP11", "to": "A0_DYNAMICS_ODR01"},
        "reference_point": "B601_A0_ORIGIN",
        "uncertainty": uncertainty,
        "authority": "ODR45_CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE",
        "status": "RECOMPUTED_FROM_PINNED_SOURCE_MATRICES",
    }
    return {
        "formula": "inv(T_S_A0_dynamics) @ T_S_A0_physical",
        "direction": "PHYSICAL_TO_DYNAMICS",
        "matrix_semantics": "ROW_MAJOR__p_parent=T_parent_child@p_child",
        "derived_matrix": {
            "value": derived,
            **transform_meta,
            "source_field": "inv(B601_PHYSICAL_DYNAMICS_BRIDGE_V1.frame_semantics.T_S_A0_dynamics.transform_S_A0_rows_m) @ B601_PHYSICAL_DYNAMICS_BRIDGE_V1.frame_semantics.T_S_A0_physical.transform_S_A0_rows_m",
        },
        "stored_matrix": {
            "value": stored,
            **transform_meta,
            "status": "FROZEN_SOURCE_MATRIX",
            "source_field": "B601_PHYSICAL_DYNAMICS_BRIDGE_V1.T_PHYSICAL_TO_DYNAMIC.homogeneous_4x4",
        },
        "exact_elementwise": exact,
        "max_abs_residual": {
            "value": residual,
            "unit": "1",
            "frames": {"from": "A0_PHYSICAL", "to": "A0_DYNAMICS"},
            "reference_point": "A0_HOMOGENEOUS_TRANSFORM",
            "uncertainty": {"standard_uncertainty": None, "status": "UNKNOWN", "distribution": None, "degrees_of_freedom": None},
            "authority": "ODR45_CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE",
            "status": "EXACT_RECOMPUTED_FROM_PINNED_MATRICES",
            "source_field": "B601_PHYSICAL_DYNAMICS_BRIDGE_V1.frame_semantics.*.transform_S_A0_rows_m",
        },
        "closure_max_abs": {
            "value": closure_residual,
            "unit": "1",
            "frames": {"from": "A0_PHYSICAL", "to": "SPACECRAFT_BUS_S"},
            "reference_point": "A0_HOMOGENEOUS_TRANSFORM",
            "uncertainty": {"standard_uncertainty": None, "status": "UNKNOWN", "distribution": None, "degrees_of_freedom": None},
            "authority": "ODR45_CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE",
            "status": "EXACT_RECOMPUTED",
            "source_field": "T_S_A0_dynamics @ T_PHYSICAL_TO_DYNAMIC == T_S_A0_physical",
        },
        "inverse_direction_max_abs_separation": {
            "value": inverse_direction_residual,
            "unit": "1",
            "frames": {"from": "A0_PHYSICAL_WP11", "to": "A0_DYNAMICS_ODR01"},
            "reference_point": "A0_HOMOGENEOUS_TRANSFORM",
            "uncertainty": uncertainty,
            "authority": "ODR45_CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE",
            "status": "DIRECTION_DISCRIMINATION_WITNESS",
            "source_field": "max_abs(T_PHYSICAL_TO_DYNAMIC - T_DYNAMIC_TO_PHYSICAL_inverse_bridge)",
        },
    }


def _find_odr45(owner_document: Mapping[str, Any]) -> Mapping[str, Any]:
    for decision in owner_document["decisions"]:
        if decision.get("id") == "ODR-45":
            return decision
    raise BridgeError("ODR45_MISSING")


def validate_source_semantics(bundle: SourceBundle) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, detail: Any) -> None:
        if not condition:
            raise BridgeError(f"SOURCE_SEMANTIC_CONFLICT:{check_id}:{detail}")
        checks.append({"id": check_id, "status": "PASS", "detail": detail})

    owner = bundle["OWNER_ODR45"].parsed
    odr45 = _find_odr45(owner)
    upgrade = odr45["structured_decomposition"]["bridge_status_upgrade"]
    check("S01_ODR45_CONFIRMS_BRIDGE", upgrade["to"] == "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE", upgrade["to"])
    check("S02_ODR45_UNIQUE_DIRECTION", odr45["structured_decomposition"]["unique_bridge"]["id"] == "T_PHYSICAL_TO_DYNAMICS", "PHYSICAL_TO_DYNAMICS")
    check("S03_OWNER_NO_RELEASE", owner["next_stage_authorized"] is False and owner["release_credit"] is False, "false/false")

    bridge = bundle["PHYSICAL_DYNAMICS_BRIDGE"].parsed
    check("S04_BRIDGE_FILE_REMAINS_FROZEN", bridge["status"] == "FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION_AND_MPI_FB08_GATE", bridge["status"])
    bridge_result = recompute_bridge(bridge)
    check("S05_BRIDGE_EXACT_RECOMPUTE", bridge_result["exact_elementwise"] and bridge_result["max_abs_residual"]["value"] == 0.0, 0.0)
    check("S06_BRIDGE_UNCERTAINTY_UNKNOWN", "standard_uncertainty remains null" in " ".join(bridge["forbidden"]), "null/UNKNOWN")

    mpi = bundle["MPI_BRIDGE_GATE"].parsed
    check("S07_MPI_GATE_PASS", mpi["mpi_gate"] == "PASS" and mpi["criterion_counts"] == {"total": 9, "pass": 9, "fail": 0}, "9/9")
    check("S08_MPI_NO_RELEASE", mpi["next_stage_authorized"] is False and mpi["release_credit"] is False, "false/false")

    e21 = bundle["E21_BRIDGED_CONSUMER_GATE"].parsed
    consumption = e21["consumption_semantics"]
    check("S09_E21_SINGLE_RULE", consumption["single_rule"] == "PHYSICAL_AUTHORITY_BRIDGED_INTO_DYNAMICS_FRAME", consumption["single_rule"])
    check("S10_E21_ZERO_AMBIGUITY", consumption["consumer_ambiguity_count"] == 0 and not consumption["frame_mixing"] and not consumption["averaging"], 0)
    check("S11_E21_DELTA_NOT_UNCERTAINTY", e21["single_authoritative_result"]["standard_uncertainty"] is None and not consumption["branch_delta_treated_as_uncertainty"], None)
    check("S12_E21_DELTA_EXACT", e21["relationship_to_legacy_two_lane_values"]["bridged_minus_reference_odr01_deg"] == 0.3688895107529362, "frame-consumption difference")

    mass = bundle["BRIDGED_MASS_INERTIA"].parsed
    check("S13_BRIDGED_MASS_GATE", mass["overall"] == "PASS" and mass["criterion_counts"] == {"total": 8, "pass": 8, "fail": 0}, "8/8")

    v6 = bundle["MECH_DYNAMICS_V6_CANDIDATE"].parsed
    r3 = bundle["EMBODIED_R3_CANDIDATE"].parsed
    check("S14_V6_CANDIDATE_ONLY", v6["candidate"] is True and "CANDIDATE_ONLY" in v6["status"] and v6["release_credit"] is False, v6["status"])
    check("S15_R3_CANDIDATE_ONLY", r3["candidate"] is True and "CANDIDATE_ONLY" in r3["status"] and r3["release_credit"] is False, r3["status"])

    frame_tree = bundle["UNIFIED_R2_FRAME_TREE"].parsed
    boundary = frame_tree["source_only_boundary"]
    check("S16_FRAME_TREE_SOURCE_LOCK", not any(boundary.values()), dict(boundary))
    frame_contract = frame_tree["frame_only_contract"]
    check("S17_D_M_DISTINCT_IDENTITIES", frame_contract["D_and_M_semantic_relation"] == "DISTINCT_IMMUTABLE_IDENTITIES__NEVER_ALIASES", frame_contract["D_and_M_semantic_relation"])
    check("S18_M_NOT_LOAD_PATH", "never through M_DYNAMICS_NONPHYSICAL" in frame_contract["load_path_rule"], frame_contract["load_path_rule"])

    source_gate = bundle["UNIFIED_R2_SOURCE_GATE"].parsed
    check("S19_URDF_NOT_EMITTED", source_gate["urdf_emitted"] is False, False)
    check("S20_SOURCE_GATE_NO_DYNAMICS_CONTACT", source_gate["production_dynamics_ready"] is False and source_gate["physical_contact_ready"] is False, "false/false")

    intake_gate = bundle["INTAKE_GATE"].parsed
    intake_terminal = bundle["INTAKE_TERMINAL"].parsed
    check("S21_INTAKE_HOLD", intake_gate["current_intake_status"] == "HOLD_INCOMPLETE" and intake_gate["release_credit"] is False, "HOLD_INCOMPLETE")
    check("S22_INTAKE_TERMINAL_BINDS_GATE", intake_terminal["gate"]["sha256"] == SOURCE_PIN_BY_ID["INTAKE_GATE"]["sha256"], intake_terminal["gate"]["sha256"])

    pre_gate = bundle["PREEXEC_GATE"].parsed
    pre_terminal = bundle["PREEXEC_TERMINAL"].parsed
    check("S23_PREEXEC_SOURCE_ONLY", pre_gate["status"] == "PASS_SOURCE_FREEZE_ONLY" and pre_gate["current_system_bound"] is False, pre_gate["status"])
    check("S24_PARENT_FORMAL_UNCHANGED", pre_gate["parent_formal_nc"] == {"passed": 15, "promoted": 0, "total": 20}, dict(pre_gate["parent_formal_nc"]))
    check("S25_NC18_NC19_HOLD", pre_terminal["remaining_holds"] == ("NC18", "NC19"), list(pre_terminal["remaining_holds"]))
    check("S26_PREEXEC_TERMINAL_BINDS_GATE", pre_terminal["gate"]["sha256"] == SOURCE_PIN_BY_ID["PREEXEC_GATE"]["sha256"], pre_terminal["gate"]["sha256"])
    return checks


def _quantity(
    *, value: Any, unit: Any, from_frame: str, to_frame: str, reference_point: str,
    authority: str, status: str, source_field: str,
) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "frames": {"from": from_frame, "to": to_frame},
        "reference_point": reference_point,
        "uncertainty": {
            "standard_uncertainty": None,
            "status": "UNKNOWN",
            "distribution": None,
            "degrees_of_freedom": None,
        },
        "authority": authority,
        "status": status,
        "source_field": source_field,
    }


@dataclass(frozen=True, slots=True)
class CrossbindRecord:
    payload: Mapping[str, Any]
    canonical_bytes: bytes
    bridge_semantic_digest: str
    crossbind_record_digest: str
    source_checks: tuple[Mapping[str, Any], ...]


def build_crossbind_record(bundle: SourceBundle) -> CrossbindRecord:
    checks = validate_source_semantics(bundle)
    bridge_doc = bundle["PHYSICAL_DYNAMICS_BRIDGE"].parsed
    bridge_result = recompute_bridge(bridge_doc)
    matrix = bridge_doc["T_PHYSICAL_TO_DYNAMIC"]["homogeneous_4x4"]
    bridge_semantic_payload = {
        "schema": "MPI_PHYSICAL_TO_DYNAMICS_BRIDGE_SEMANTICS_V1",
        "id": "T_PHYSICAL_TO_DYNAMIC",
        "direction": "PHYSICAL_TO_DYNAMICS",
        "matrix_semantics": "ROW_MAJOR__p_parent=T_parent_child@p_child",
        "from_frame": "A0_PHYSICAL_WP11",
        "to_frame": "A0_DYNAMICS_ODR01",
        "reference_point": "B601_A0_ORIGIN",
        "homogeneous_4x4": matrix,
        "source_sha256": bundle["PHYSICAL_DYNAMICS_BRIDGE"].sha256,
    }
    bridge_semantic_digest = sha256_bytes(canonical_json_bytes(bridge_semantic_payload))
    payload = {
        "schema": "MPI_BRIDGE_TO_SIM13_IMMUTABLE_CROSSBIND_RECORD_V1",
        "authority_resolution": {
            "owner_decision": "ODR-45",
            "effective_bridge_status": "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE",
            "frozen_bridge_file_status_preserved": bridge_doc["status"],
            "producer_gate": "MPI_BRIDGE_GATE_V1:PASS",
            "consumer_scope": "FUTURE_UNIFIED_R2_TO_SIM13_SOURCE_CONTRACT_ONLY",
        },
        "matrix_semantics": "ROW_MAJOR__p_parent=T_parent_child@p_child",
        "bridge": {
            "id": "T_PHYSICAL_TO_DYNAMIC",
            "direction": "PHYSICAL_TO_DYNAMICS",
            "transform": _quantity(
                value=matrix,
                unit={"rotation": "1", "translation": "m", "homogeneous_bottom_row": "1"},
                from_frame="A0_PHYSICAL_WP11",
                to_frame="A0_DYNAMICS_ODR01",
                reference_point="B601_A0_ORIGIN",
                authority="ODR45_CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE",
                status="CONFIRMED_BY_OWNER_OVERLAY__SOURCE_MATRIX_FROZEN",
                source_field="B601_PHYSICAL_DYNAMICS_BRIDGE_V1.T_PHYSICAL_TO_DYNAMIC.homogeneous_4x4",
            ),
            "clocking": _quantity(
                value=25.000014,
                unit="deg",
                from_frame="A0_PHYSICAL_WP11",
                to_frame="A0_DYNAMICS_ODR01",
                reference_point="B601_A0_ORIGIN__ABOUT_PLUS_Z_A0_DYNAMICS",
                authority="ODR45_CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE",
                status="DEFINITIONAL_BRIDGE_COMPONENT",
                source_field="B601_PHYSICAL_DYNAMICS_BRIDGE_V1.bridge_constant_ruling.unique_bridge_clocking_deg",
            ),
            "translation": _quantity(
                value=[0.0, 0.0, 0.022749999999999992],
                unit="m",
                from_frame="A0_PHYSICAL_WP11",
                to_frame="A0_DYNAMICS_ODR01",
                reference_point="B601_A0_ORIGIN",
                authority="ODR45_CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE",
                status="DEFINITIONAL_BRIDGE_COMPONENT",
                source_field="B601_PHYSICAL_DYNAMICS_BRIDGE_V1.T_PHYSICAL_TO_DYNAMIC.translation_m",
            ),
            "recomputation": bridge_result,
            "bridge_sha256": bundle["PHYSICAL_DYNAMICS_BRIDGE"].sha256,
            "bridge_semantic_digest": bridge_semantic_digest,
        },
        "mass_inertia_binding": {
            "sha256": bundle["BRIDGED_MASS_INERTIA"].sha256,
            "status": "BRIDGED_CANDIDATE_SINGLE_CONSUMPTION_SEMANTICS__NOT_RELEASE",
            "authority": "ODR45_PLUS_MPI_BRIDGE_GATE__CANDIDATE_OVERLAY_ONLY",
            "source_field": "SYSTEM_MASS_PROPERTIES_BRIDGED_V1",
            "bridge_transform_uncertainty": {"standard_uncertainty": None, "status": "UNKNOWN", "distribution": None, "degrees_of_freedom": None},
            "member_mass_inertia_uncertainties": "PRESERVED_VERBATIM_FROM_SYSTEM_MASS_PROPERTIES_BRIDGED_V1",
            "frames": {"from": "WP11_PHYSICAL_INSTALLATION", "to": "ODR01_DYNAMICS"},
            "reference_point": "PER_CONFIGURATION_SYSTEM_CG_AS_DECLARED_IN_SOURCE",
            "unit": {"mass": "kg", "center_of_mass": "m", "inertia": "kg*m^2"},
        },
        "consumer_crossbind": {
            "channels_exact": list(CHANNELS),
            "lineage_rule": "EACH_CHANNEL_HAS_THE_COMPLETE_PHYSICAL_TO_DYNAMICS_BRIDGE_LINEAGE_EXACTLY_ONCE",
            "consumer_boundary_numeric_rule": "FRAME_WRENCH_COLLISION_APPLY_ONCE__MASS_INERTIA_BIND_UPSTREAM_BRIDGED_LEDGER_WITH_ZERO_CONSUMER_REAPPLICATION",
            "source_domain": "WP11_PHYSICAL_INSTALLATION_AUTHORITY",
            "target_domain": "ODR01_DYNAMICS_FRAME_AUTHORITY",
            "collision_geometry_source_frame": "D_BUS_MATE_PHYSICAL",
            "physical_load_path_frame": "D_BUS_MATE_PHYSICAL",
            "nonphysical_reporting_frame": "M_DYNAMICS_NONPHYSICAL",
            "semantic_alias_permitted": False,
            "historical_branch_delta": _quantity(
                value=0.3688895107529362,
                unit="deg",
                from_frame="ODR01_DIRECT_LEGACY_LANE",
                to_frame="WP11_PHYSICAL_BRIDGED_LANE",
                reference_point="E21_M07_PEAK_BASE_ATTITUDE_DEVIATION",
                authority="E21_BRIDGED_ARM_PLACEMENT_GATE_V2_RELATIONSHIP_TO_LEGACY_TWO_LANE_VALUES",
                status="HISTORICAL_DETERMINISTIC_FRAME_CONSUMPTION_DIFFERENCE_NOT_RANDOM_UNCERTAINTY",
                source_field="E21_BRIDGED_ARM_PLACEMENT_GATE_V2.relationship_to_legacy_two_lane_values.bridged_minus_reference_odr01_deg",
            ),
        },
        "system_binding_v3": {
            "schema_frozen": True,
            "production_composite_producer_status": "NOT_IMPLEMENTED_NO_PRODUCER",
            "production_authenticated_receipt_present": False,
            "synthetic_signed_composition_fixture_only": True,
            "source_lock": True,
        },
        "prohibitions": [
            "NO_SKIP_INVERSE_OR_DOUBLE_BRIDGE_APPLICATION",
            "NO_ODR01_WP11_MIXING_AVERAGING_OR_SELECTIVE_CONSUMPTION",
            "NO_M_DYNAMICS_NONPHYSICAL_AS_PHYSICAL_LOAD_PATH",
            "NO_UNBRIDGED_V3_R2_MASS_WITH_BRIDGED_DYNAMICS",
            "NO_NUMERIC_EQUALITY_AS_SEMANTIC_ALIAS",
            "NO_0P3688895107529362_DEG_AS_RANDOM_UNCERTAINTY",
            "NO_V6_OR_R3_CANDIDATE_AS_RELEASE",
            "NO_LEGACY_V2_URDF_ONLY_RECEIPT_AS_SUFFICIENT_BINDING",
        ],
        "parent_and_runtime_state": {
            "formal_parent_nc": {"passed": 15, "total": 20, "promoted": 0},
            "remaining_holds": ["NC18", "NC19"],
            "intake_status": "HOLD_INCOMPLETE",
            "maximum_runtime_state": "SOURCE_LOCK_NO_CONSUMPTION",
            "flags": {flag: False for flag in MANDATORY_FALSE_FLAGS},
        },
        "source_receipts": [bundle[item_id].public_receipt() for item_id in bundle.receipts],
    }
    canonical = canonical_json_bytes(payload)
    frozen = deep_freeze(payload)
    validate_crossbind_record_payload(frozen)
    return CrossbindRecord(
        payload=frozen,
        canonical_bytes=canonical,
        bridge_semantic_digest=bridge_semantic_digest,
        crossbind_record_digest=sha256_bytes(canonical),
        source_checks=tuple(deep_freeze(check) for check in checks),
    )
