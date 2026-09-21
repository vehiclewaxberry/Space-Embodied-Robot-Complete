"""Adversarial source-only controls for bridge and signed composition security."""

from __future__ import annotations

import hashlib
import hmac
from copy import deepcopy
from typing import Any, Callable

from .bridge import (
    BridgeError,
    CrossbindRecord,
    recompute_bridge,
    validate_crossbind_record_payload,
)
from .constants import EXACT_DIRECTORY_ALLOWLIST, EXACT_FILE_ALLOWLIST
from .policy import PolicyError, make_valid_plan, validate_consumer_plan
from .receipt import (
    PRODUCTION_RECEIPT_KIND,
    ReceiptError,
    V3ReplayStore,
    _actual_preexec_modules,
    make_synthetic_v3_fixture,
    validate_system_binding_v3,
)
from .source_bundle import SourceBundle, SourceBundleError, verify_raw_against_pin
from .strict_io import StrictIOError, deep_thaw, validate_inventory_sets


def run_negative_controls(bundle: SourceBundle, record: CrossbindRecord) -> list[dict[str, Any]]:
    plan = make_valid_plan(record)
    fixture = make_synthetic_v3_fixture(record)
    _, strict = _actual_preexec_modules()
    controls: list[dict[str, Any]] = []

    def expect(control_id: str, expected_fragment: str, attack: Callable[[], Any]) -> None:
        try:
            attack()
        except (PolicyError, ReceiptError, SourceBundleError, BridgeError, StrictIOError) as exc:
            reason = str(exc)
            if expected_fragment not in reason:
                raise AssertionError(f"{control_id}:wrong_reason:{reason}") from exc
            controls.append({"id": control_id, "status": "PASS_REJECTED", "reason": reason})
            return
        raise AssertionError(f"{control_id}:ATTACK_ACCEPTED")

    def plan_attack(mutator: Callable[[dict[str, Any]], None]) -> Callable[[], Any]:
        def attack() -> Any:
            candidate = deepcopy(plan)
            mutator(candidate)
            return validate_consumer_plan(candidate, record)
        return attack

    expect("NC01_SKIP_FRAME_BRIDGE", "BRIDGE_SKIPPED:frame", plan_attack(lambda p: p["channels"]["frame"].update(bridge_lineage_count=0)))
    expect("NC02_INVERSE_MASS_BRIDGE", "INVERSE_BRIDGE_FORBIDDEN:mass", plan_attack(lambda p: p["channels"]["mass"].update(direction="DYNAMICS_TO_PHYSICAL")))
    expect("NC03_DOUBLE_INERTIA_LINEAGE", "BRIDGE_NOT_EXACTLY_ONCE:inertia", plan_attack(lambda p: p["channels"]["inertia"].update(bridge_lineage_count=2)))
    expect("NC04_SELECTIVE_CHANNEL_DROP", "SELECTIVE_CHANNEL_CONSUMPTION", plan_attack(lambda p: p["channels"].pop("wrench")))
    expect("NC05_ODR01_WP11_SOURCE_MIX", "ODR01_WP11_SOURCE_DOMAIN_MIX", plan_attack(lambda p: p.update(source_domain="ODR01_DIRECT")))
    expect("NC06_FRAME_AVERAGING", "ODR01_WP11_MIX_AVERAGE_OR_SELECTIVE_CONSUMPTION", plan_attack(lambda p: p.update(legacy_sources_consumed=["ODR01_DIRECT", "WP11_AVERAGED"])))
    expect("NC07_M_FRAME_LOAD_PATH", "M_DYNAMICS_NONPHYSICAL_USED_AS_LOAD_PATH", plan_attack(lambda p: p.update(physical_load_path_frame="M_DYNAMICS_NONPHYSICAL")))
    expect("NC08_UNBRIDGED_V3_R2_MASS", "UNBRIDGED_V3_R2_MASS_WITH_BRIDGED_DYNAMICS", plan_attack(lambda p: p.update(mass_inertia_binding_sha256="0" * 64)))
    expect("NC09_NUMERIC_SEMANTIC_ALIAS", "NUMERIC_EQUALITY_USED_AS_SEMANTIC_ALIAS", plan_attack(lambda p: p.update(semantic_alias_permitted=True)))
    expect("NC10_DELTA_AS_UNCERTAINTY", "BRANCH_DELTA_MISLABELED_RANDOM_UNCERTAINTY", plan_attack(lambda p: p["branch_delta"]["uncertainty"].update(standard_uncertainty=0.3688895107529362)))
    expect("NC11_CANDIDATE_AS_RELEASE", "V6_R3_CANDIDATE_MASQUERADES_AS_RELEASE", plan_attack(lambda p: p.update(candidate_release_claimed=True)))
    expect("NC12_V2_URDF_ONLY_SUFFICIENT", "LEGACY_V2_URDF_ONLY_RECEIPT_INSUFFICIENT", plan_attack(lambda p: p.update(legacy_v2_urdf_only_receipt_sufficient=True)))
    expect("NC13_WRONG_BRIDGE_SHA", "WRONG_BRIDGE_SHA", plan_attack(lambda p: p.update(bridge_sha256="0" * 64)))
    expect("NC14_WRONG_BRIDGE_SEMANTIC", "WRONG_BRIDGE_SEMANTIC_DIGEST", plan_attack(lambda p: p.update(bridge_semantic_digest="0" * 64)))
    expect("NC15_WRONG_CROSSBIND_RECORD_DIGEST", "WRONG_CROSSBIND_RECORD_DIGEST", plan_attack(lambda p: p.update(crossbind_record_digest="0" * 64)))
    expect("NC16_MASS_NUMERIC_REAPPLY", "NUMERIC_BRIDGE_APPLICATION_SITE_OR_COUNT_MISMATCH:mass", plan_attack(lambda p: p["channels"]["mass"].update(consumer_numeric_application_count=1)))
    expect("NC17_INERTIA_NUMERIC_REAPPLY", "NUMERIC_BRIDGE_APPLICATION_SITE_OR_COUNT_MISMATCH:inertia", plan_attack(lambda p: p["channels"]["inertia"].update(consumer_numeric_application_count=1)))
    expect("NC18_WRONG_WRENCH_OPERATOR", "WRONG_INDUCED_BRIDGE_OPERATOR:wrench", plan_attack(lambda p: p["channels"]["wrench"].update(induced_operator="ELEMENTWISE_ROTATION")))
    expect("NC19_BOOLEAN_LINEAGE_COUNT", "INVALID_BRIDGE_LINEAGE_COUNT_TYPE:frame", plan_attack(lambda p: p["channels"]["frame"].update(bridge_lineage_count=True)))
    expect("NC20_LEGACY_SOURCES_WRONG_TYPE", "LEGACY_SOURCES_NOT_EMPTY_LIST", plan_attack(lambda p: p.update(legacy_sources_consumed="")))
    expect("NC21_BOOLEAN_NUMERIC_COUNT", "INVALID_CONSUMER_NUMERIC_APPLICATION_COUNT_TYPE:mass", plan_attack(lambda p: p["channels"]["mass"].update(consumer_numeric_application_count=False)))

    record_payload = deep_thaw(record.payload)
    expect("NC22_RECORD_DOUBLE_APPLY_WORDING", "CROSSBIND_NUMERIC_APPLICATION_WORDING_DRIFT", lambda: validate_crossbind_record_payload({**record_payload, "consumer_crossbind": {**record_payload["consumer_crossbind"], "consumer_boundary_numeric_rule": "APPLY_ALL_AT_CONSUMER"}}))
    mass_with_bad_uncertainty = deepcopy(record_payload)
    mass_with_bad_uncertainty["mass_inertia_binding"]["uncertainty"] = {"standard_uncertainty": 0.0}
    expect("NC23_RECORD_MASS_GENERIC_UNCERTAINTY", "MASS_INERTIA_GENERIC_UNCERTAINTY_FIELD_FORBIDDEN", lambda: validate_crossbind_record_payload(mass_with_bad_uncertainty))

    def kwargs(store: V3ReplayStore | None = None) -> dict[str, Any]:
        return {
            "preexec_receipt_bytes_by_kind": fixture.preexec_receipt_bytes_by_kind,
            "expected_action": fixture.action,
            "expected_context": fixture.context,
            "trusted_now_unix_s": fixture.trusted_now_unix_s,
            "replay_store": store or V3ReplayStore(),
            "preexec_key": fixture.preexec_key,
            "v3_key": fixture.v3_key,
        }

    def resign_v3(mutator: Callable[[dict[str, Any]], None]) -> bytes:
        outer = strict.loads_strict(fixture.receipt_bytes)
        mutator(outer["body"])
        outer["signature_hmac_sha256"] = hmac.new(
            fixture.v3_key,
            strict.canonical_json_bytes(outer["body"]),
            hashlib.sha256,
        ).hexdigest().upper()
        return strict.canonical_json_bytes(outer)

    def validate_bytes(raw: bytes, *, override: dict[str, Any] | None = None) -> Any:
        call = kwargs()
        if override:
            call.update(override)
        return validate_system_binding_v3(raw, record, **call)

    expect("NC24_UNSIGNED_DICT_FAKE_AUTHENTICATED", "SERIALIZED_SIGNED_ENVELOPE_BYTES_REQUIRED", lambda: validate_system_binding_v3({"receipt_kind": "AUTHENTICATED"}, record, **kwargs()))
    expect("NC25_SIGNED_PRODUCTION_KIND_NO_PRODUCER", "NOT_IMPLEMENTED_NO_PRODUCER", lambda: validate_bytes(resign_v3(lambda b: b.update(receipt_kind=PRODUCTION_RECEIPT_KIND))))
    expect("NC26_OLD_V2_SINGLE_RECEIPT_AS_COMPOSITE", "KEY_SET_MISMATCH", lambda: validate_bytes(fixture.preexec_receipt_bytes_by_kind["SYSTEM_BINDING_V2"]))
    expect("NC27_V3_ACTION_REBIND", "V3_ACTION_REBIND", lambda: validate_bytes(resign_v3(lambda b: b["action"].update(strategy_id="S3a"))))
    expect("NC28_V3_CONTEXT_REBIND", "V3_CONTEXT_REBIND", lambda: validate_bytes(resign_v3(lambda b: b["context"].update(mission_phase_id="OTHER_PHASE"))))
    expect("NC29_CONFIGURATION_MAPPING_REBIND", "CONFIGURATION_MAPPING_MISMATCH", lambda: validate_bytes(resign_v3(lambda b: b["configuration_mapping"].update(v3_configuration_id="C09"))))
    expect("NC30_EPISODE_DROPPED", "KEY_SET_MISMATCH", lambda: validate_bytes(resign_v3(lambda b: b["context"].pop("episode_id"))))
    expect("NC31_AUTHORITY_EPOCH_DROPPED", "KEY_SET_MISMATCH", lambda: validate_bytes(resign_v3(lambda b: b["context"].pop("authority_epoch"))))
    expect("NC32_TARGET_CLASS_REBIND", "V3_CONTEXT_REBIND", lambda: validate_bytes(resign_v3(lambda b: b["context"].update(target_class="OTHER_TARGET"))))

    bad_signature_outer = strict.loads_strict(fixture.receipt_bytes)
    bad_signature_outer["signature_hmac_sha256"] = "0" * 64
    bad_signature = strict.canonical_json_bytes(bad_signature_outer)
    expect("NC33_BAD_V3_HMAC", "V3_SIGNATURE_INVALID", lambda: validate_bytes(bad_signature))

    bad_preexec = dict(fixture.preexec_receipt_bytes_by_kind)
    bad_outer = strict.loads_strict(bad_preexec["DYNAMICS_GATE_V2"])
    bad_outer["signature_hmac_sha256"] = "0" * 64
    bad_preexec["DYNAMICS_GATE_V2"] = strict.canonical_json_bytes(bad_outer)
    expect("NC34_BAD_PREEXEC_HMAC", "ATTESTATION_SIGNATURE_INVALID", lambda: validate_bytes(fixture.receipt_bytes, override={"preexec_receipt_bytes_by_kind": bad_preexec}))

    def preexec_digest_attack(kind: str, field: str) -> dict[str, bytes]:
        candidate = dict(fixture.preexec_receipt_bytes_by_kind)
        outer = strict.loads_strict(candidate[kind])
        outer["body"][field] = "0" * 64
        outer["signature_hmac_sha256"] = hmac.new(
            fixture.preexec_key,
            strict.canonical_json_bytes(outer["body"]),
            hashlib.sha256,
        ).hexdigest().upper()
        candidate[kind] = strict.canonical_json_bytes(outer)
        return candidate

    expect("NC35_MIXED_PREEXEC_ACTION", "ACTION_DIGEST_MISMATCH", lambda: validate_bytes(fixture.receipt_bytes, override={"preexec_receipt_bytes_by_kind": preexec_digest_attack("CONTACT_PREFLIGHT_V2", "action_digest")}))
    expect("NC36_MIXED_PREEXEC_CONTEXT", "CONTEXT_DIGEST_MISMATCH", lambda: validate_bytes(fixture.receipt_bytes, override={"preexec_receipt_bytes_by_kind": preexec_digest_attack("CONTACT_PREFLIGHT_V2", "context_digest")}))
    expect("NC37_RECEIPT_SET_ORDER_REBIND", "PREEXEC_ORDERED_RECEIPT_SET_MISMATCH", lambda: validate_bytes(resign_v3(lambda b: b["preexec_receipts"].reverse())))
    expect("NC38_RECEIPT_SET_SUBSTITUTION", "PREEXEC_ORDERED_RECEIPT_SET_MISMATCH", lambda: validate_bytes(resign_v3(lambda b: b["preexec_receipts"][0].update(sha256="0" * 64))))

    replay_store = V3ReplayStore()
    validate_system_binding_v3(fixture.receipt_bytes, record, **kwargs(replay_store))
    expect("NC39_SAME_V3_NONCE_REPLAY", "V3_REPLAY_NONCE", lambda: validate_system_binding_v3(fixture.receipt_bytes, record, **kwargs(replay_store)))
    if replay_store.seen_count != 1:
        raise AssertionError("NC39:REPLAY_STORE_COUNT_DRIFT")

    signature_failure_store = V3ReplayStore()
    expect("NC40_SIGNATURE_FAILURE_NONCE_NOT_CONSUMED", "V3_SIGNATURE_INVALID", lambda: validate_system_binding_v3(bad_signature, record, **kwargs(signature_failure_store)))
    if signature_failure_store.seen_count != 0:
        raise AssertionError("NC40:FAILED_SIGNATURE_CONSUMED_NONCE")
    semantic_failure_store = V3ReplayStore()
    expect("NC41_SEMANTIC_FAILURE_NONCE_NOT_CONSUMED", "CONFIGURATION_MAPPING_MISMATCH", lambda: validate_system_binding_v3(resign_v3(lambda b: b["configuration_mapping"].update(v3_configuration_id="C09")), record, **kwargs(semantic_failure_store)))
    if semantic_failure_store.seen_count != 0:
        raise AssertionError("NC41:FAILED_SEMANTIC_CONSUMED_NONCE")

    for number, field in enumerate(("intake_gate_sha256", "intake_terminal_sha256", "preexec_gate_sha256", "preexec_terminal_sha256"), start=42):
        expect(f"NC{number}_{field.upper()}_SUBSTITUTION", f"HASH_BINDING_MISMATCH:{field}", lambda field=field: validate_bytes(resign_v3(lambda b: b.update({field: "0" * 64}))))
    expect("NC46_BRIDGE_SEMANTIC_SUBSTITUTION", "HASH_BINDING_MISMATCH:bridge_semantic_digest", lambda: validate_bytes(resign_v3(lambda b: b.update(bridge_semantic_digest="0" * 64))))
    expect("NC47_CROSSBIND_RECORD_SUBSTITUTION", "HASH_BINDING_MISMATCH:crossbind_record_digest", lambda: validate_bytes(resign_v3(lambda b: b.update(crossbind_record_digest="0" * 64))))

    expect("NC48_EXPIRED_PREEXEC_FRESH_V3", "STALE_RECEIPT", lambda: validate_bytes(resign_v3(lambda b: b.update(issued_at_unix_s=1350.0, expires_at_unix_s=1500.0)), override={"trusted_now_unix_s": 1400.0}))
    expect("NC49_V3_WINDOW_OUTSIDE_PREEXEC_COMMON", "V3_WINDOW_NOT_CONTAINED_IN_PREEXEC_COMMON_WINDOW", lambda: validate_bytes(resign_v3(lambda b: b.update(expires_at_unix_s=1301.0))))
    expect("NC50_V3_WINDOW_OVER_5_MIN", "INVALID_V3_VALIDITY_WINDOW", lambda: validate_bytes(resign_v3(lambda b: b.update(expires_at_unix_s=1321.0))))

    lone_surrogate = b'{"body":{"context":"\\ud800"},"signature_hmac_sha256":"' + b"0" * 64 + b'"}'
    expect("NC51_LONE_SURROGATE", "INVALID_UTF8_STRING", lambda: validate_bytes(lone_surrogate))
    nonfinite = b'{"body":{"issued_at_unix_s":1e999},"signature_hmac_sha256":"' + b"0" * 64 + b'"}'
    expect("NC52_NONFINITE_1E999", "NON_FINITE_NUMBER", lambda: validate_bytes(nonfinite))
    duplicate = b'{"body":{},"body":{},"signature_hmac_sha256":"' + b"0" * 64 + b'"}'
    expect("NC53_DUPLICATE_JSON_KEY", "DUPLICATE_KEY", lambda: validate_bytes(duplicate))
    substituted_kind = dict(fixture.preexec_receipt_bytes_by_kind)
    substituted_kind["SYSTEM_BINDING_V2"] = fixture.preexec_receipt_bytes_by_kind["DYNAMICS_GATE_V2"]
    expect("NC54_PREEXEC_KIND_SUBSTITUTION", "RECEIPT_KIND_MISMATCH", lambda: validate_bytes(fixture.receipt_bytes, override={"preexec_receipt_bytes_by_kind": substituted_kind}))
    expect("NC55_LOW_LEVEL_ACTION_FIELD", "KEY_SET_MISMATCH", lambda: validate_bytes(resign_v3(lambda b: b["action"].update(joint_torque=[1.0]))))
    for number, field in enumerate(("urdf_sha256", "interface_sha256", "frame_tree_sha256", "owner_authority_sha256", "mass_inertia_binding_sha256"), start=56):
        expect(f"NC{number}_{field.upper()}_SUBSTITUTION", f"HASH_BINDING_MISMATCH:{field}", lambda field=field: validate_bytes(resign_v3(lambda b: b.update({field: "0" * 64}))))

    bridge_doc = deep_thaw(bundle["PHYSICAL_DYNAMICS_BRIDGE"].parsed)
    bridge_doc["T_PHYSICAL_TO_DYNAMIC"]["homogeneous_4x4"] = bridge_doc["T_DYNAMIC_TO_PHYSICAL_inverse_bridge"]["homogeneous_4x4"]
    expect("NC61_INVERSE_MATRIX_SUBSTITUTION", "PHYSICAL_TO_DYNAMICS_BRIDGE_MISMATCH", lambda: recompute_bridge(bridge_doc))
    source = bundle["PHYSICAL_DYNAMICS_BRIDGE"]
    expect("NC62_ONE_BYTE_SOURCE_MUTATION", "SOURCE_SHA_MISMATCH", lambda: verify_raw_against_pin(source.source_id, source.path, source.raw_bytes + b" ", source.sha256))
    exact_files = set(EXACT_FILE_ALLOWLIST)
    exact_dirs = set(EXACT_DIRECTORY_ALLOWLIST)
    expect("NC63_SHADOW_JSON", "EXTRA_FILE:shadow.json", lambda: validate_inventory_sets(exact_files | {"shadow.json"}, exact_dirs))
    expect("NC64_SHADOW_SDF", "FORBIDDEN_ASSET:shadow.sdf", lambda: validate_inventory_sets(exact_files | {"shadow.sdf"}, exact_dirs))
    expect("NC65_SHADOW_XACRO", "FORBIDDEN_ASSET:shadow.xacro", lambda: validate_inventory_sets(exact_files | {"shadow.xacro"}, exact_dirs))
    expect("NC66_CACHE_DIRECTORY", "FORBIDDEN_CACHE_DIRECTORY", lambda: validate_inventory_sets(exact_files, exact_dirs | {"__pycache__"}))
    expect("NC67_EXTRA_DIRECTORY", "EXTRA_DIRECTORY:shadow", lambda: validate_inventory_sets(exact_files, exact_dirs | {"shadow"}))
    return controls
