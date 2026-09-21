"""Fail-closed future consumer plan validator and permanent source lock."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .bridge import CrossbindRecord
from .constants import CHANNELS, SOURCE_PIN_BY_ID
from .receipt import ReceiptError, validate_system_binding_v3


class PolicyError(ValueError):
    """Consumer attempted to bypass or dilute the unique bridge."""


PLAN_KEYS = frozenset(
    (
        "schema",
        "bridge_sha256",
        "bridge_semantic_digest",
        "crossbind_record_digest",
        "source_domain",
        "target_domain",
        "channels",
        "mass_inertia_binding_sha256",
        "legacy_sources_consumed",
        "physical_load_path_frame",
        "collision_geometry_source_frame",
        "nonphysical_reporting_frame",
        "semantic_alias_permitted",
        "branch_delta",
        "mech_dynamics_interface_schema",
        "embodied_mechanical_contract_schema",
        "candidate_release_claimed",
        "legacy_v2_urdf_only_receipt_sufficient",
    )
)
CHANNEL_KEYS = frozenset(
    (
        "bridge_lineage_count",
        "consumer_numeric_application_count",
        "direction",
        "bridge_sha256",
        "bridge_semantic_digest",
        "application_site",
        "induced_operator",
        "reference_point_policy",
    )
)

CHANNEL_CONTRACTS = {
    "frame": {
        "consumer_numeric_application_count": 1,
        "application_site": "CONSUMER_SYSTEM_BOUNDARY",
        "induced_operator": "RIGID_POSE_AND_POINT_TRANSFORM",
        "reference_point_policy": "B601_A0_ORIGIN",
    },
    "mass": {
        "consumer_numeric_application_count": 0,
        "application_site": "UPSTREAM_BRIDGED_LEDGER__CONSUMER_BIND_ONLY",
        "induced_operator": "MASS_INVARIANT_PLUS_CG_RIGID_REEXPRESSION_FROZEN_IN_LEDGER",
        "reference_point_policy": "PER_CONFIGURATION_SYSTEM_CG_AS_DECLARED_IN_BRIDGED_LEDGER",
    },
    "inertia": {
        "consumer_numeric_application_count": 0,
        "application_site": "UPSTREAM_BRIDGED_LEDGER__CONSUMER_BIND_ONLY",
        "induced_operator": "R_I_RT_PLUS_PARALLEL_AXIS_FROZEN_IN_BRIDGED_LEDGER",
        "reference_point_policy": "PER_CONFIGURATION_SYSTEM_CG_AS_DECLARED_IN_BRIDGED_LEDGER",
    },
    "wrench": {
        "consumer_numeric_application_count": 1,
        "application_site": "CONSUMER_SYSTEM_BOUNDARY",
        "induced_operator": "DUAL_ADJOINT_WITH_DECLARED_APPLICATION_POINT",
        "reference_point_policy": "FUTURE_INTERFACE_DECLARED_APPLICATION_POINT__NO_DEFAULT_ORIGIN",
    },
    "collision_geometry": {
        "consumer_numeric_application_count": 1,
        "application_site": "CONSUMER_SYSTEM_BOUNDARY",
        "induced_operator": "RIGID_TRANSFORM_ALL_COLLISION_GEOMETRY_FRAMES",
        "reference_point_policy": "D_BUS_MATE_PHYSICAL_TO_ODR01_DYNAMICS",
    },
}

BRANCH_DELTA_RECORD = {
    "value": 0.3688895107529362,
    "unit": "deg",
    "frames": {"from": "ODR01_DIRECT_LEGACY_LANE", "to": "WP11_PHYSICAL_BRIDGED_LANE"},
    "reference_point": "E21_M07_PEAK_BASE_ATTITUDE_DEVIATION",
    "uncertainty": {"standard_uncertainty": None, "status": "UNKNOWN", "distribution": None, "degrees_of_freedom": None},
    "authority": "E21_BRIDGED_ARM_PLACEMENT_GATE_V2_RELATIONSHIP_TO_LEGACY_TWO_LANE_VALUES",
    "status": "HISTORICAL_DETERMINISTIC_FRAME_CONSUMPTION_DIFFERENCE_NOT_RANDOM_UNCERTAINTY",
    "source_field": "E21_BRIDGED_ARM_PLACEMENT_GATE_V2.relationship_to_legacy_two_lane_values.bridged_minus_reference_odr01_deg",
}


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], code: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise PolicyError(f"{code}:missing={sorted(expected-actual)}:extra={sorted(actual-expected)}")


def make_valid_plan(record: CrossbindRecord) -> dict[str, Any]:
    channels = {}
    for name in CHANNELS:
        channels[name] = {
            "bridge_lineage_count": 1,
            "direction": "PHYSICAL_TO_DYNAMICS",
            "bridge_sha256": SOURCE_PIN_BY_ID["PHYSICAL_DYNAMICS_BRIDGE"]["sha256"],
            "bridge_semantic_digest": record.bridge_semantic_digest,
            **CHANNEL_CONTRACTS[name],
        }
    return {
        "schema": "MPI_BRIDGE_TO_SIM13_CONSUMER_PLAN_V1",
        "bridge_sha256": SOURCE_PIN_BY_ID["PHYSICAL_DYNAMICS_BRIDGE"]["sha256"],
        "bridge_semantic_digest": record.bridge_semantic_digest,
        "crossbind_record_digest": record.crossbind_record_digest,
        "source_domain": "WP11_PHYSICAL_INSTALLATION_AUTHORITY",
        "target_domain": "ODR01_DYNAMICS_FRAME_AUTHORITY",
        "channels": channels,
        "mass_inertia_binding_sha256": SOURCE_PIN_BY_ID["BRIDGED_MASS_INERTIA"]["sha256"],
        "legacy_sources_consumed": [],
        "physical_load_path_frame": "D_BUS_MATE_PHYSICAL",
        "collision_geometry_source_frame": "D_BUS_MATE_PHYSICAL",
        "nonphysical_reporting_frame": "M_DYNAMICS_NONPHYSICAL",
        "semantic_alias_permitted": False,
        "branch_delta": deepcopy(BRANCH_DELTA_RECORD),
        "mech_dynamics_interface_schema": "MECH_DYNAMICS_INTERFACE_V6_CANDIDATE",
        "embodied_mechanical_contract_schema": "EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE",
        "candidate_release_claimed": False,
        "legacy_v2_urdf_only_receipt_sufficient": False,
    }


def validate_consumer_plan(plan: Mapping[str, Any], record: CrossbindRecord) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        raise PolicyError("PLAN_NOT_OBJECT")
    _exact_keys(plan, PLAN_KEYS, "PLAN_KEYSET")
    if plan["schema"] != "MPI_BRIDGE_TO_SIM13_CONSUMER_PLAN_V1":
        raise PolicyError("WRONG_PLAN_SCHEMA")
    bridge_sha = SOURCE_PIN_BY_ID["PHYSICAL_DYNAMICS_BRIDGE"]["sha256"]
    if plan["bridge_sha256"] != bridge_sha:
        raise PolicyError("WRONG_BRIDGE_SHA")
    if plan["bridge_semantic_digest"] != record.bridge_semantic_digest:
        raise PolicyError("WRONG_BRIDGE_SEMANTIC_DIGEST")
    if plan["crossbind_record_digest"] != record.crossbind_record_digest:
        raise PolicyError("WRONG_CROSSBIND_RECORD_DIGEST")
    if plan["source_domain"] != "WP11_PHYSICAL_INSTALLATION_AUTHORITY":
        raise PolicyError("ODR01_WP11_SOURCE_DOMAIN_MIX")
    if plan["target_domain"] != "ODR01_DYNAMICS_FRAME_AUTHORITY":
        raise PolicyError("ODR01_WP11_TARGET_DOMAIN_MIX")
    channels = plan["channels"]
    if not isinstance(channels, Mapping) or frozenset(channels) != frozenset(CHANNELS):
        raise PolicyError("SELECTIVE_CHANNEL_CONSUMPTION")
    for name in CHANNELS:
        item = channels[name]
        if not isinstance(item, Mapping):
            raise PolicyError(f"CHANNEL_NOT_OBJECT:{name}")
        _exact_keys(item, CHANNEL_KEYS, f"CHANNEL_KEYSET:{name}")
        if type(item["bridge_lineage_count"]) is not int:
            raise PolicyError(f"INVALID_BRIDGE_LINEAGE_COUNT_TYPE:{name}")
        if item["bridge_lineage_count"] == 0:
            raise PolicyError(f"BRIDGE_SKIPPED:{name}")
        if item["bridge_lineage_count"] != 1:
            raise PolicyError(f"BRIDGE_NOT_EXACTLY_ONCE:{name}")
        if item["direction"] != "PHYSICAL_TO_DYNAMICS":
            raise PolicyError(f"INVERSE_BRIDGE_FORBIDDEN:{name}")
        if item["bridge_sha256"] != bridge_sha or item["bridge_semantic_digest"] != record.bridge_semantic_digest:
            raise PolicyError(f"CHANNEL_BRIDGE_MISMATCH:{name}")
        expected_channel = CHANNEL_CONTRACTS[name]
        if type(item["consumer_numeric_application_count"]) is not int:
            raise PolicyError(f"INVALID_CONSUMER_NUMERIC_APPLICATION_COUNT_TYPE:{name}")
        if item["consumer_numeric_application_count"] != expected_channel["consumer_numeric_application_count"]:
            raise PolicyError(f"NUMERIC_BRIDGE_APPLICATION_SITE_OR_COUNT_MISMATCH:{name}")
        if item["application_site"] != expected_channel["application_site"]:
            raise PolicyError(f"NUMERIC_BRIDGE_APPLICATION_SITE_OR_COUNT_MISMATCH:{name}")
        if item["induced_operator"] != expected_channel["induced_operator"]:
            raise PolicyError(f"WRONG_INDUCED_BRIDGE_OPERATOR:{name}")
        if item["reference_point_policy"] != expected_channel["reference_point_policy"]:
            raise PolicyError(f"WRONG_REFERENCE_POINT_POLICY:{name}")
    if plan["mass_inertia_binding_sha256"] != SOURCE_PIN_BY_ID["BRIDGED_MASS_INERTIA"]["sha256"]:
        raise PolicyError("UNBRIDGED_V3_R2_MASS_WITH_BRIDGED_DYNAMICS")
    if not isinstance(plan["legacy_sources_consumed"], list) or plan["legacy_sources_consumed"]:
        if not isinstance(plan["legacy_sources_consumed"], list):
            raise PolicyError("LEGACY_SOURCES_NOT_EMPTY_LIST")
        raise PolicyError("ODR01_WP11_MIX_AVERAGE_OR_SELECTIVE_CONSUMPTION")
    if plan["physical_load_path_frame"] == "M_DYNAMICS_NONPHYSICAL":
        raise PolicyError("M_DYNAMICS_NONPHYSICAL_USED_AS_LOAD_PATH")
    if plan["physical_load_path_frame"] != "D_BUS_MATE_PHYSICAL":
        raise PolicyError("INVALID_PHYSICAL_LOAD_PATH_FRAME")
    if plan["collision_geometry_source_frame"] != "D_BUS_MATE_PHYSICAL":
        raise PolicyError("COLLISION_GEOMETRY_NOT_FROM_PHYSICAL_DATUM")
    if plan["nonphysical_reporting_frame"] != "M_DYNAMICS_NONPHYSICAL":
        raise PolicyError("NONPHYSICAL_REPORTING_FRAME_DRIFT")
    if plan["semantic_alias_permitted"] is not False:
        raise PolicyError("NUMERIC_EQUALITY_USED_AS_SEMANTIC_ALIAS")
    delta = plan["branch_delta"]
    if not isinstance(delta, Mapping):
        raise PolicyError("BRANCH_DELTA_NOT_QUANTITY_RECORD")
    if delta.get("value") != BRANCH_DELTA_RECORD["value"]:
        raise PolicyError("BRANCH_DELTA_VALUE_DRIFT")
    if not isinstance(delta.get("uncertainty"), Mapping) or delta["uncertainty"].get("standard_uncertainty") is not None:
        raise PolicyError("BRANCH_DELTA_MISLABELED_RANDOM_UNCERTAINTY")
    if dict(delta) != BRANCH_DELTA_RECORD:
        raise PolicyError("BRANCH_DELTA_CLASSIFICATION_DRIFT")
    if plan["mech_dynamics_interface_schema"] != "MECH_DYNAMICS_INTERFACE_V6_CANDIDATE":
        raise PolicyError("INTERFACE_SOURCE_SCHEMA_DRIFT")
    if plan["embodied_mechanical_contract_schema"] != "EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE":
        raise PolicyError("EMBODIED_SOURCE_SCHEMA_DRIFT")
    if plan["candidate_release_claimed"] is not False:
        raise PolicyError("V6_R3_CANDIDATE_MASQUERADES_AS_RELEASE")
    if plan["legacy_v2_urdf_only_receipt_sufficient"] is not False:
        raise PolicyError("LEGACY_V2_URDF_ONLY_RECEIPT_INSUFFICIENT")
    return {
        "valid": True,
        "channels_bound": len(CHANNELS),
        "bridge_lineage_applications_per_channel": 1,
        "consumer_numeric_applications": {name: CHANNEL_CONTRACTS[name]["consumer_numeric_application_count"] for name in CHANNELS},
        "source_lock": True,
        "runtime_credit": False,
    }


def admit_consumer(
    plan: Mapping[str, Any],
    receipt: bytes | None,
    record: CrossbindRecord,
    *,
    environment: Mapping[str, Any],
    receipt_validation_kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        validate_consumer_plan(plan, record)
    except PolicyError as exc:
        return {"allowed": False, "reason": str(exc), "bridge_applications_executed": 0, "release_credit": False}
    if receipt is None:
        return {"allowed": False, "reason": "SYSTEM_BINDING_V3_PRODUCTION_COMPOSITE_ABSENT", "bridge_applications_executed": 0, "release_credit": False}
    if receipt_validation_kwargs is None:
        return {"allowed": False, "reason": "SYSTEM_BINDING_V3_VALIDATION_CONTEXT_ABSENT", "bridge_applications_executed": 0, "release_credit": False}
    try:
        receipt_result = validate_system_binding_v3(receipt, record, **dict(receipt_validation_kwargs))
    except ReceiptError as exc:
        return {"allowed": False, "reason": str(exc), "bridge_applications_executed": 0, "release_credit": False}
    return {
        "allowed": False,
        "reason": "SYNTHETIC_SIGNED_COMPOSITION_FIXTURE_SOURCE_LOCK",
        "bridge_applications_executed": 0,
        "release_credit": False,
        "production_authenticated_receipt_present": False,
        "v3_nonce_consumed_on_successful_fixture_verification": receipt_result["v3_nonce_consumed"],
    }
