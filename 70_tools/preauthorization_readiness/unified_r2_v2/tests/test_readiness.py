from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


TOOL_DIR = Path(__file__).resolve().parents[1]
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))
SPEC = importlib.util.spec_from_file_location("preauth_readiness_under_test", TOOL_DIR / "preauthorization_readiness.py")
assert SPEC is not None and SPEC.loader is not None
readiness = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = readiness
SPEC.loader.exec_module(readiness)
import safe_io


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def owner_payload(now: datetime, *, ack=readiness.LOW_MEMORY_ACK) -> dict:
    return {
        "schema": readiness.OWNER_SCHEMA,
        "record_type": "DIRECT_OWNER_SOURCE_NOT_MACHINE_AUTHORIZATION",
        "origin": "USER_OR_OWNER_DIRECT_EXPORT",
        "owner_role_assertion": "PROJECT_OWNER",
        "owner_statement_utc": readiness._utc_text(now),
        "decisions": {
            "odr_gpt_07": {
                "decision_id": "ODR-GPT-07",
                "decision": "APPROVE",
                "selected_option": "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE",
                "request_sha256": readiness.REQUESTS["ODR-GPT-07"]["sha256"],
            },
            "odr_gpt_08": {
                "decision_id": "ODR-GPT-08",
                "decision": "APPROVE",
                "selected_option": "A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR",
                "request_sha256": readiness.REQUESTS["ODR-GPT-08"]["sha256"],
            },
            "c01_unified_r2_research_candidate": {
                "decision_id": "C01-UNIFIED-R2-RESEARCH-CANDIDATE",
                "decision": "APPROVE",
                "configuration": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT",
                "selected_bus_mass_mode": "EXPLICIT_STRUCTURE_PLUS_RESIDUAL",
                "route_c_exclusion_accepted_for_this_sim_candidate": True,
                "route_c_cad_authorized": False,
                "scope": ["ANALYSIS_ONLY", "RESEARCH_CANDIDATE", "NON_PRODUCTION"],
                "production_dynamics_authorized": False,
                "physical_contact_authorized": False,
                "sim13_rebind_authorized": False,
                "next_stage_authorized": False,
                "release_credit": False,
                "low_memory_risk_ack": ack,
            },
        },
    }


def write_owner(tmp_path: Path, data: dict, name: str = "direct_owner.json") -> tuple[Path, str]:
    path = tmp_path / name
    payload = (json.dumps(data, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    path.write_bytes(payload)
    return path, sha(payload)


def build_ready_report(direct_root: Path, now: datetime, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    source, digest = write_owner(direct_root, owner_payload(now, ack=None))
    return readiness.build_readiness_report(
        owner_source=source,
        expected_source_sha256=digest,
        valid_for_seconds=7200,
        now=now,
    )


def set_nested(payload: dict, path: tuple[str, ...], value) -> None:
    cursor = payload
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 8, 24, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def tmp_path() -> Path:
    """Use a private attachment-root temp because the host pytest temp ACL is broken."""

    base = Path.home() / ".codex/attachments/_preauth_readiness_test_tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / uuid.uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        resolved = path.resolve()
        if resolved.parent == base.resolve() and resolved.exists():
            shutil.rmtree(resolved)
        try:
            base.rmdir()
        except OSError:
            pass


@pytest.fixture
def direct_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(readiness, "ALLOWED_OWNER_SOURCE_ROOTS", [tmp_path])
    return tmp_path


def test_request_07_pin_matches():
    assert readiness._request_statuses()["ODR-GPT-07"]["pass"] is True


def test_request_08_pin_matches():
    assert readiness._request_statuses()["ODR-GPT-08"]["pass"] is True


def test_generator_source_and_input_pins_match():
    assert all(item["pass"] for item in readiness._source_statuses().values())


def test_current_report_is_exact_no_direct_owner_denial():
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    assert report["summary"]["state"] == "DENY_NO_DIRECT_OWNER_SOURCE"


def test_current_report_has_no_authority_effect():
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    assert report["summary"] == {
        "state": "DENY_NO_DIRECT_OWNER_SOURCE",
        "authority_effect": "NONE",
        "execution_authorized": False,
        "target_authorization_written": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "owner_accepted": False,
        "owner_identity_verified": False,
        "tooling_credit_only": True,
    }


def test_odr_intents_do_not_imply_c01():
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    c01 = report["decision_readiness"]["c01_unified_r2_research_candidate"]
    assert c01["state"] == "DENY_MISSING_C01_INDEPENDENT_INTENT_SECTION"
    assert report["checks"]["odr_07_and_08_do_not_imply_c01"] is True


@pytest.mark.parametrize("value", [0, -1, 7201, "bad", 1.5, True])
def test_invalid_validity_windows_fail_closed(value):
    assert readiness._validity_status(value)[0] is False


@pytest.mark.parametrize("value", [1, 60, 7200, "7200"])
def test_valid_integer_windows_are_preview_only(value):
    passed, normalized, state = readiness._validity_status(value)
    assert passed is True
    assert 1 <= normalized <= 7200
    assert state == "VALID_PREVIEW_WINDOW"


def test_workspace_owner_source_is_rejected(now):
    source = readiness.PROJECT_ROOT / "01_project/competition/机械终局LoopEngineering进展裁决_20260824.md"
    _, provenance = readiness._read_direct_owner_source(source, readiness._sha256_file(source), now)
    assert provenance["status"] == "DENY_OWNER_SOURCE_PATH_OUTSIDE_DIRECT_ATTACHMENT_BOUNDARY"


def test_hash_mismatch_is_rejected(direct_root, now):
    source, _ = write_owner(direct_root, owner_payload(now))
    _, provenance = readiness._read_direct_owner_source(source, "0" * 64, now)
    assert provenance["status"] == "DENY_OWNER_SOURCE_HASH_MISMATCH"


def test_reparse_or_symlink_detection_fails_closed(direct_root, now, monkeypatch):
    source, digest = write_owner(direct_root, owner_payload(now))
    monkeypatch.setattr(
        readiness,
        "secure_read_bytes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(safe_io.SafeIOError("REPARSE_OR_SYMLINK_COMPONENT_DENIED")),
    )
    _, provenance = readiness._read_direct_owner_source(source, digest, now)
    assert provenance["status"] == "DENY_REPARSE_OR_SYMLINK_OWNER_SOURCE"


def test_duplicate_json_key_is_rejected(direct_root, now):
    source = direct_root / "duplicate.json"
    payload = (
        '{"schema":"DIRECT_OWNER_INTENT_SOURCE_V1","schema":"DIRECT_OWNER_INTENT_SOURCE_V1",'
        '"record_type":"DIRECT_OWNER_SOURCE_NOT_MACHINE_AUTHORIZATION","origin":"USER_OR_OWNER_DIRECT_EXPORT",'
        '"owner_role_assertion":"PROJECT_OWNER","owner_statement_utc":"'
        + readiness._utc_text(now)
        + '","decisions":{}}\n'
    ).encode("utf-8")
    source.write_bytes(payload)
    _, provenance = readiness._read_direct_owner_source(source, sha(payload), now)
    assert provenance["status"] == "DENY_OWNER_SOURCE_PARSE"
    assert provenance["failure_detail_class"] == "DuplicateKeyError"


def test_stale_owner_source_is_rejected(direct_root, now):
    source, digest = write_owner(direct_root, owner_payload(now - timedelta(seconds=7201)))
    _, provenance = readiness._read_direct_owner_source(source, digest, now)
    assert provenance["status"] == "DENY_STALE_OR_FUTURE_OWNER_SOURCE"


def test_future_owner_source_is_rejected(direct_root, now):
    source, digest = write_owner(direct_root, owner_payload(now + timedelta(seconds=301)))
    _, provenance = readiness._read_direct_owner_source(source, digest, now)
    assert provenance["status"] == "DENY_STALE_OR_FUTURE_OWNER_SOURCE"


def test_request_or_template_shape_is_rejected(direct_root, now):
    data = owner_payload(now)
    data["record_type"] = "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD"
    source, digest = write_owner(direct_root, data)
    _, provenance = readiness._read_direct_owner_source(source, digest, now)
    assert provenance["status"] == "DENY_REQUEST_TEMPLATE_SELF_OR_NONOWNER_SOURCE"


def test_extra_top_level_field_is_rejected(direct_root, now):
    data = owner_payload(now)
    data["owner_accepted"] = True
    source, digest = write_owner(direct_root, data)
    _, provenance = readiness._read_direct_owner_source(source, digest, now)
    assert provenance["status"] == "DENY_OWNER_SOURCE_TOP_LEVEL_SCHEMA_OR_EXTRA_FIELDS"


def test_known_stale_external_hash_is_rejected(direct_root, now, monkeypatch):
    source, digest = write_owner(direct_root, owner_payload(now))
    monkeypatch.setattr(readiness, "KNOWN_STALE_EXTERNAL_SOURCE_HASHES", {digest})
    _, provenance = readiness._read_direct_owner_source(source, digest, now)
    assert provenance["status"] == "DENY_KNOWN_STALE_PREDECESSOR_SOURCE"


def test_valid_direct_source_only_reaches_issuer_review_not_execution(direct_root, now, monkeypatch):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    source, digest = write_owner(direct_root, owner_payload(now, ack=None))
    report = readiness.build_readiness_report(
        owner_source=source,
        expected_source_sha256=digest,
        valid_for_seconds=7200,
        now=now,
    )
    assert report["summary"]["state"] == "STRUCTURALLY_READY_FOR_AUTHENTICATED_ISSUER_REVIEW__IDENTITY_UNVERIFIED__NO_AUTHORITY_CREATED"
    assert report["summary"]["execution_authorized"] is False
    assert report["summary"]["target_authorization_written"] is False
    assert report["summary"]["owner_accepted"] is False
    assert report["owner_source_provenance"]["identity_authentication_status"] == "OUT_OF_SCOPE_REQUIRES_FUTURE_ISSUER"


def test_low_memory_requires_exact_ack(direct_root, now, monkeypatch):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (5.0, "TEST_LOW_MEMORY"))
    source, digest = write_owner(direct_root, owner_payload(now, ack=None))
    report = readiness.build_readiness_report(
        owner_source=source, expected_source_sha256=digest, valid_for_seconds=7200, now=now
    )
    assert report["summary"]["state"] == "DENY_INCOMPLETE_NEGATIVE_OR_CONFLICTING_INDEPENDENT_OWNER_INTENTS"
    assert report["decision_readiness"]["c01_unified_r2_research_candidate"]["checks"]["low_memory_ack"] is False
    assert report["memory_preview"]["memory_gate_passed"] is False


def test_low_memory_exact_ack_is_readiness_only(direct_root, now, monkeypatch):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (5.0, "TEST_LOW_MEMORY"))
    source, digest = write_owner(direct_root, owner_payload(now, ack=readiness.LOW_MEMORY_ACK))
    report = readiness.build_readiness_report(
        owner_source=source, expected_source_sha256=digest, valid_for_seconds=7200, now=now
    )
    assert report["summary"]["state"] == "STRUCTURALLY_READY_FOR_AUTHENTICATED_ISSUER_REVIEW__IDENTITY_UNVERIFIED__NO_AUTHORITY_CREATED"
    assert report["memory_preview"]["memory_gate_passed"] is False
    assert report["memory_preview"]["owner_override_effect_created"] is False
    assert "run_id" not in report["ephemeral_preview"]
    assert "override_id" not in report["memory_preview"]


def test_unknown_memory_requires_exact_ack(direct_root, now, monkeypatch):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (None, "TEST_UNKNOWN"))
    source, digest = write_owner(direct_root, owner_payload(now, ack=None))
    report = readiness.build_readiness_report(
        owner_source=source, expected_source_sha256=digest, valid_for_seconds=7200, now=now
    )
    assert report["memory_preview"]["low_memory_ack_required_at_preview"] is True
    assert report["decision_readiness"]["c01_unified_r2_research_candidate"]["state"].startswith("DENY_")


def test_missing_c01_section_denies_even_when_both_odrs_approve(direct_root, now, monkeypatch):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    data = owner_payload(now, ack=None)
    del data["decisions"]["c01_unified_r2_research_candidate"]
    source, digest = write_owner(direct_root, data)
    report = readiness.build_readiness_report(
        owner_source=source, expected_source_sha256=digest, valid_for_seconds=7200, now=now
    )
    assert report["owner_source_provenance"]["status"] == "DENY_OWNER_DECISION_KEYSET_MUST_BE_EXACT"
    assert report["decision_readiness"]["odr_gpt_07"]["source_section_present"] is False
    assert report["decision_readiness"]["odr_gpt_08"]["source_section_present"] is False
    assert report["decision_readiness"]["c01_unified_r2_research_candidate"]["state"] == "DENY_MISSING_C01_INDEPENDENT_INTENT_SECTION"
    assert report["summary"]["state"].startswith("DENY_")


def test_wrong_request_hash_denies(direct_root, now, monkeypatch):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    data = owner_payload(now, ack=None)
    data["decisions"]["odr_gpt_07"]["request_sha256"] = "0" * 64
    source, digest = write_owner(direct_root, data)
    report = readiness.build_readiness_report(
        owner_source=source, expected_source_sha256=digest, valid_for_seconds=7200, now=now
    )
    assert report["decision_readiness"]["odr_gpt_07"]["state"] == "DENY_REQUEST_HASH_DRIFT_OR_OWNER_BINDING_MISMATCH"


def test_negative_decision_does_not_become_readiness(direct_root, now, monkeypatch):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    data = owner_payload(now, ack=None)
    data["decisions"]["odr_gpt_08"]["decision"] = "REJECT"
    source, digest = write_owner(direct_root, data)
    report = readiness.build_readiness_report(
        owner_source=source, expected_source_sha256=digest, valid_for_seconds=7200, now=now
    )
    assert "NONAPPROVAL" in report["decision_readiness"]["odr_gpt_08"]["state"]
    assert report["summary"]["state"].startswith("DENY_")


@pytest.mark.parametrize(
    "decision_key,selected_option",
    [
        ("odr_gpt_07", "D_RETAIN_3_TO_5_MODE_CONTRACT_KEEP_HOLD"),
        ("odr_gpt_07", "F_REVISE_AND_RESUBMIT"),
        ("odr_gpt_07", "G_REJECT"),
        ("odr_gpt_08", "D_REVISE_AND_RESUBMIT"),
        ("odr_gpt_08", "E_REJECT"),
    ],
)
def test_negative_revise_or_hold_selected_option_never_becomes_readiness(
    direct_root, now, monkeypatch, decision_key, selected_option
):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    data = owner_payload(now, ack=None)
    data["decisions"][decision_key]["selected_option"] = selected_option
    source, digest = write_owner(direct_root, data)
    report = readiness.build_readiness_report(
        owner_source=source, expected_source_sha256=digest, valid_for_seconds=7200, now=now
    )
    decision = report["decision_readiness"][decision_key]
    assert decision["selected_option_is_negative_or_hold"] is True
    assert decision["affirmative_decision"] is False
    assert "NEGATIVE_OR_NONAPPROVAL" in decision["state"]
    assert report["summary"]["state"].startswith("DENY_")


@pytest.mark.parametrize(
    "field,value",
    [
        ("route_c_cad_authorized", True),
        ("production_dynamics_authorized", True),
        ("physical_contact_authorized", True),
        ("sim13_rebind_authorized", True),
        ("next_stage_authorized", True),
        ("release_credit", True),
    ],
)
def test_c01_prohibited_permission_conflicts_deny(direct_root, now, monkeypatch, field, value):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    data = owner_payload(now, ack=None)
    data["decisions"]["c01_unified_r2_research_candidate"][field] = value
    source, digest = write_owner(direct_root, data)
    report = readiness.build_readiness_report(
        owner_source=source, expected_source_sha256=digest, valid_for_seconds=7200, now=now
    )
    assert report["decision_readiness"]["c01_unified_r2_research_candidate"]["state"] == "DENY_C01_CONFLICT_NEGATION_OR_LOW_MEMORY_ACK_MISSING"


def test_runtime_hash_is_preview_only_and_nonreusable():
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    runtime = report["ephemeral_preview"]["runtime_hash"]
    assert runtime["preview_only"] is True
    assert runtime["runtime_code_sha256_preview"] is None
    assert runtime["status"] == "NOT_COMPUTED_BY_DESIGN_NONAUTHORITATIVE"
    assert runtime["reusable_by_future_issuer"] is False
    assert runtime["future_issuer_must_recompute_with_generator_in_same_loaded_instance_and_process"] is True
    assert all(
        runtime[key] is False
        for key in (
            "generator_source_loaded",
            "generator_source_imported",
            "generator_source_compiled",
            "generator_source_executed",
        )
    )


def test_readiness_cannot_match_formal_authorization_shape():
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    assert report["formal_authorization_incompatibility"]["formal_schema_match"] is False
    assert "authority_flags" not in report
    assert "run_id" not in report
    assert report["summary"]["owner_accepted"] is False


def test_readiness_bytes_copied_to_target_name_cannot_match_frozen_v2_formal_shape(tmp_path):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    copied_target = tmp_path / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json"
    copied_target.write_bytes((json.dumps(report, sort_keys=True) + "\n").encode("utf-8"))
    copied = json.loads(copied_target.read_text(encoding="utf-8"))
    flags = copied.get("authority_flags")
    required_true = {
        "rebase_execution_authorized",
        "unified_r2_v2_generation_authorized",
        "system_urdf_generation_authorized",
        "route_c_exclusion_accepted_for_this_sim_candidate",
        "memory_admitted_for_this_execution",
    }
    formal_match = (
        copied.get("schema") == "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2"
        and copied.get("owner_accepted") is True
        and isinstance(flags, dict)
        and all(flags.get(key) is True for key in required_true)
        and flags.get("route_c_cad_authorized") is False
        and all(
            isinstance(copied.get(key), str) and bool(copied.get(key))
            for key in (
                "run_id",
                "issued_utc",
                "expires_utc",
                "source_sha256",
                "input_sha256",
                "runtime_code_sha256",
            )
        )
    )
    assert formal_match is False


def test_source_has_no_generator_or_private_builder_call_tokens():
    token_a = "gen_" + "urdf" + "("
    token_b = "_" + "build_robot" + "("
    for source in TOOL_DIR.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert token_a not in text
        assert token_b not in text


def test_cli_exposes_no_issuer_force_or_output_path_controls():
    help_text = readiness._make_parser().format_help()
    for token in ("issue ", "run ", "write-target", "--force", "--output"):
        assert token not in help_text


def test_fixed_output_guard_has_only_four_names(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "EVIDENCE_ROOT", tmp_path)
    assert {readiness._guarded_output_path(command).name for command in readiness.OUTPUT_NAMES} == set(
        readiness.OUTPUT_NAMES.values()
    )
    with pytest.raises(RuntimeError, match="OUTPUT_NAME_NOT_ALLOWLISTED"):
        readiness._guarded_output_path("issue")


def test_audit_write_observes_target_and_adjacent_state_unchanged():
    before = readiness.protected_state_snapshot()
    assert readiness.main(["audit-current"]) == 0
    after = readiness.protected_state_snapshot()
    assert before == after
    assert (readiness.EVIDENCE_ROOT / readiness.OUTPUT_NAMES["audit-current"]).is_file()


def test_verify_accepts_readiness_but_never_promotes(tmp_path):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    path = tmp_path / "readiness.json"
    raw = json.dumps(report).encode("utf-8")
    verification = readiness._verify_readiness_raw_bytes(raw, report_path=path)
    assert verification["structural_passed"] is True
    assert verification["live_readiness_passed"] is True
    assert verification["owner_intents_ready"] is False
    assert verification["signing_or_execution_ready"] is False
    assert verification["authority_effect"] == "NONE"
    assert verification["execution_authorized"] is False


def test_verify_legitimate_ready_requires_full_evidence_conjunction(
    direct_root, now, monkeypatch
):
    report = build_ready_report(direct_root, now, monkeypatch)
    verification = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=direct_root / "ready.json", now=now
    )
    assert verification["structural_passed"] is True
    assert verification["live_readiness_passed"] is True
    assert verification["owner_intents_ready"] is True
    assert verification["owner_identity_verified"] is False
    assert verification["signing_or_execution_ready"] is False
    assert verification["live_readiness_scope"] == (
        "ARTIFACT_TIME_WINDOW_ONLY__NOT_ISSUER_OR_EXECUTION_READINESS"
    )
    assert verification["owner_intent_evidence_checks"]
    assert all(verification["owner_intent_evidence_checks"].values())


def test_exact_ready_string_forged_onto_no_source_report_fails_conditional_schema(now, tmp_path):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200, now=now
    )
    report["summary"]["state"] = (
        "STRUCTURALLY_READY_FOR_AUTHENTICATED_ISSUER_REVIEW__IDENTITY_UNVERIFIED__NO_AUTHORITY_CREATED"
    )
    verification = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=tmp_path / "forged_ready.json", now=now
    )
    assert verification["checks"]["complete_json_schema"] is False
    assert verification["structural_passed"] is False
    assert verification["live_readiness_passed"] is False
    assert verification["owner_intents_ready"] is False


READY_BOOLEAN_DRIFTS = [
    (("owner_source_provenance", "present"), False),
    (("owner_source_provenance", "raw_bytes_parsed"), False),
    (("owner_source_provenance", "path_policy_pass"), False),
    (("owner_source_provenance", "reparse_or_symlink_detected"), True),
    (("owner_source_provenance", "source_freshness_pass"), False),
    (("owner_source_provenance", "source_schema_pass"), False),
    (("owner_source_provenance", "read_snapshot_stable"), False),
    (("checks", "direct_owner_source_parsed"), False),
    (("checks", "odr_gpt_07_independent_intent_ready"), False),
    (("checks", "odr_gpt_08_independent_intent_ready"), False),
    (("checks", "c01_independent_intent_ready"), False),
    (("checks", "request_hashes_match"), False),
    (("checks", "frozen_generator_source_and_inputs_match"), False),
    (("checks", "validity_window_is_positive_and_leq_7200_seconds"), False),
    (("checks", "runtime_hash_deliberately_not_computed"), False),
    (("checks", "generator_source_not_loaded_imported_compiled_or_executed"), False),
    (("checks", "protected_target_and_adjacent_state_observed_before_after_unchanged"), False),
    (("request_bindings", "ODR-GPT-07", "pass"), False),
    (("request_bindings", "ODR-GPT-08", "pass"), False),
    (("frozen_source_bindings", "generator_source", "pass"), False),
    (("frozen_source_bindings", "generator_inputs", "pass"), False),
    (("decision_readiness", "odr_gpt_07", "source_section_present"), False),
    (("decision_readiness", "odr_gpt_07", "decision_schema_pass"), False),
    (("decision_readiness", "odr_gpt_07", "request_binding_pass"), False),
    (("decision_readiness", "odr_gpt_07", "selected_option_registered"), False),
    (("decision_readiness", "odr_gpt_07", "selected_option_is_negative_or_hold"), True),
    (("decision_readiness", "odr_gpt_07", "affirmative_decision"), False),
    (("decision_readiness", "odr_gpt_08", "source_section_present"), False),
    (("decision_readiness", "odr_gpt_08", "decision_schema_pass"), False),
    (("decision_readiness", "odr_gpt_08", "request_binding_pass"), False),
    (("decision_readiness", "odr_gpt_08", "selected_option_registered"), False),
    (("decision_readiness", "odr_gpt_08", "selected_option_is_negative_or_hold"), True),
    (("decision_readiness", "odr_gpt_08", "affirmative_decision"), False),
    (("decision_readiness", "c01_unified_r2_research_candidate", "source_section_present"), False),
    (("decision_readiness", "c01_unified_r2_research_candidate", "decision_schema_pass"), False),
]
READY_BOOLEAN_DRIFTS.extend(
    (
        ("decision_readiness", "c01_unified_r2_research_candidate", "checks", key),
        False,
    )
    for key in (
        "affirmative_decision",
        "configuration_exact",
        "mass_mode_exact",
        "route_c_exclusion_exact_true",
        "route_c_cad_exact_false",
        "scope_exact",
        "production_dynamics_exact_false",
        "physical_contact_exact_false",
        "sim13_rebind_exact_false",
        "next_stage_exact_false",
        "release_credit_exact_false",
        "low_memory_ack",
    )
)


@pytest.mark.parametrize(
    "path,value",
    READY_BOOLEAN_DRIFTS,
    ids=lambda item: "_".join(item) if isinstance(item, tuple) else str(item).lower(),
)
def test_ready_nested_boolean_drift_fails_schema_and_all_readiness_dimensions(
    direct_root, now, monkeypatch, path, value
):
    report = build_ready_report(direct_root, now, monkeypatch)
    set_nested(report, path, value)
    verification = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=direct_root / "drift.json", now=now
    )
    assert verification["checks"]["complete_json_schema"] is False
    assert verification["structural_passed"] is False
    assert verification["live_readiness_passed"] is False
    assert verification["owner_intents_ready"] is False


@pytest.mark.parametrize(
    "decision_key,state",
    [
        ("odr_gpt_07", "DENY_FORGED_STATE"),
        ("odr_gpt_08", "READY_FOR_SEPARATE_C01_ISSUER_REVIEW"),
        ("c01_unified_r2_research_candidate", "READY_FOR_SEPARATE_DECISION_RECORD_REVIEW"),
    ],
)
def test_ready_decision_state_drift_fails_conditional_schema(
    direct_root, now, monkeypatch, decision_key, state
):
    report = build_ready_report(direct_root, now, monkeypatch)
    report["decision_readiness"][decision_key]["state"] = state
    verification = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=direct_root / "state_drift.json", now=now
    )
    assert verification["checks"]["complete_json_schema"] is False
    assert verification["structural_passed"] is False
    assert verification["live_readiness_passed"] is False
    assert verification["owner_intents_ready"] is False


@pytest.mark.parametrize(
    "missing_key",
    ["source_path", "actual_source_sha256", "owner_statement_utc", "secure_handle_read"],
)
def test_ready_provenance_required_field_missing_fails_conditional_schema(
    direct_root, now, monkeypatch, missing_key
):
    report = build_ready_report(direct_root, now, monkeypatch)
    del report["owner_source_provenance"][missing_key]
    verification = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=direct_root / "missing.json", now=now
    )
    assert verification["checks"]["complete_json_schema"] is False
    assert verification["structural_passed"] is False
    assert verification["live_readiness_passed"] is False
    assert verification["owner_intents_ready"] is False


@pytest.mark.parametrize(
    "path",
    [
        ("owner_source_provenance", "actual_source_sha256"),
        ("decision_readiness", "odr_gpt_07", "request_sha256_from_owner_source"),
        ("request_bindings", "ODR-GPT-08", "actual_sha256"),
    ],
)
def test_ready_cross_field_hash_drift_never_sets_owner_intents_ready(
    direct_root, now, monkeypatch, path
):
    report = build_ready_report(direct_root, now, monkeypatch)
    set_nested(report, path, "0" * 64)
    verification = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=direct_root / "hash_drift.json", now=now
    )
    assert verification["owner_intents_ready"] is False
    assert not (
        verification["structural_passed"]
        and verification["live_readiness_passed"]
        and verification["owner_intents_ready"]
    )


def test_ready_protected_before_after_content_drift_never_sets_owner_intents_ready(
    direct_root, now, monkeypatch
):
    report = build_ready_report(direct_root, now, monkeypatch)
    report["protected_state"]["after"]["active_run_lock"]["state"] = "FORGED_DIFFERENT"
    verification = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=direct_root / "protected_drift.json", now=now
    )
    assert verification["structural_passed"] is True
    assert verification["live_readiness_passed"] is True
    assert verification["owner_intents_ready"] is False


@pytest.mark.parametrize(
    "path,value",
    [
        (("owner_source_provenance", "present"), True),
        (("owner_source_provenance", "raw_bytes_parsed"), True),
        (("checks", "direct_owner_source_parsed"), True),
        (("decision_readiness", "odr_gpt_07", "source_section_present"), True),
        (("decision_readiness", "c01_unified_r2_research_candidate", "decision_schema_pass"), True),
    ],
)
def test_deny_no_source_requires_matching_negative_evidence(now, tmp_path, path, value):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200, now=now
    )
    set_nested(report, path, value)
    verification = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=tmp_path / "deny_drift.json", now=now
    )
    assert verification["checks"]["complete_json_schema"] is False
    assert verification["structural_passed"] is False
    assert verification["live_readiness_passed"] is False
    assert verification["owner_intents_ready"] is False


def test_verify_rejects_authorization_shaped_copy(tmp_path):
    path = tmp_path / "fake.json"
    raw = json.dumps(
        {
            "owner_accepted": True,
            "authority_flags": {"system_urdf_generation_authorized": True},
        }
    ).encode("utf-8")
    verification = readiness._verify_readiness_raw_bytes(raw, report_path=path)
    assert verification["structural_passed"] is False
    assert verification["live_readiness_passed"] is False
    assert verification["owner_intents_ready"] is False


def test_self_test_passes_and_keeps_target_absent():
    before = readiness.protected_state_snapshot()
    result = readiness._self_test_payload()
    after = readiness.protected_state_snapshot()
    assert result["summary"]["passed"] is True
    assert before == after


def test_json_schema_validates_current_report():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((TOOL_DIR / "PREAUTHORIZATION_READINESS_SCHEMA_V1.json").read_text(encoding="utf-8"))
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    jsonschema.Draft202012Validator(schema).validate(report)


def test_json_schema_validates_ready_owner_report(direct_root, now, monkeypatch):
    jsonschema = pytest.importorskip("jsonschema")
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    source, digest = write_owner(direct_root, owner_payload(now, ack=None))
    report = readiness.build_readiness_report(
        owner_source=source,
        expected_source_sha256=digest,
        valid_for_seconds=7200,
        now=now,
    )
    schema = json.loads(
        (TOOL_DIR / "PREAUTHORIZATION_READINESS_SCHEMA_V1.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(report)
    assert set(report["decision_readiness"]) == {
        "odr_gpt_07",
        "odr_gpt_08",
        "c01_unified_r2_research_candidate",
    }


def test_json_schema_validates_fail_closed_owner_denials(direct_root, now, monkeypatch):
    jsonschema = pytest.importorskip("jsonschema")
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    schema = json.loads(
        (TOOL_DIR / "PREAUTHORIZATION_READINESS_SCHEMA_V1.json").read_text(encoding="utf-8")
    )
    validator = jsonschema.Draft202012Validator(schema)

    valid_source, _ = write_owner(direct_root, owner_payload(now), "valid_for_mismatch.json")
    reports = [
        readiness.build_readiness_report(
            owner_source=valid_source,
            expected_source_sha256="0" * 64,
            valid_for_seconds=7200,
            now=now,
        )
    ]

    malformed = direct_root / "malformed.txt"
    malformed_raw = b'{"schema":'
    malformed.write_bytes(malformed_raw)
    reports.append(
        readiness.build_readiness_report(
            owner_source=malformed,
            expected_source_sha256=sha(malformed_raw),
            valid_for_seconds=7200,
            now=now,
        )
    )

    missing_c01 = owner_payload(now)
    del missing_c01["decisions"]["c01_unified_r2_research_candidate"]
    missing_source, missing_digest = write_owner(direct_root, missing_c01, "missing_c01.json")
    reports.append(
        readiness.build_readiness_report(
            owner_source=missing_source,
            expected_source_sha256=missing_digest,
            valid_for_seconds=7200,
            now=now,
        )
    )

    negative = owner_payload(now)
    negative["decisions"]["odr_gpt_08"]["selected_option"] = "E_REJECT"
    negative_source, negative_digest = write_owner(direct_root, negative, "negative.json")
    reports.append(
        readiness.build_readiness_report(
            owner_source=negative_source,
            expected_source_sha256=negative_digest,
            valid_for_seconds=7200,
            now=now,
        )
    )

    malformed_odr = owner_payload(now)
    malformed_odr["decisions"]["odr_gpt_07"]["selected_option"] = []
    malformed_odr_source, malformed_odr_digest = write_owner(
        direct_root, malformed_odr, "malformed_odr_type.json"
    )
    reports.append(
        readiness.build_readiness_report(
            owner_source=malformed_odr_source,
            expected_source_sha256=malformed_odr_digest,
            valid_for_seconds=7200,
            now=now,
        )
    )

    malformed_scope = owner_payload(now)
    malformed_scope["decisions"]["c01_unified_r2_research_candidate"]["scope"] = [
        {"not": "hashable"}
    ]
    malformed_scope_source, malformed_scope_digest = write_owner(
        direct_root, malformed_scope, "malformed_scope_type.json"
    )
    reports.append(
        readiness.build_readiness_report(
            owner_source=malformed_scope_source,
            expected_source_sha256=malformed_scope_digest,
            valid_for_seconds=7200,
            now=now,
        )
    )

    for report in reports:
        assert report["summary"]["state"].startswith("DENY_")
        validator.validate(report)


def test_verify_rejects_forged_ready_alias(now, tmp_path):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200, now=now
    )
    report["summary"]["state"] = "READY_FOR_EXECUTION"
    result = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=tmp_path / "forged_ready.json", now=now
    )
    assert result["structural_passed"] is False
    assert result["owner_intents_ready"] is False


def test_drifted_generator_with_top_level_side_effect_is_never_executed(direct_root, monkeypatch):
    marker = direct_root / "forbidden_side_effect.marker"
    malicious = direct_root / "drifted_generator.py"
    malicious.write_text(
        "from pathlib import Path\n"
        + f"Path({str(marker)!r}).write_text('EXECUTED', encoding='utf-8')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(readiness, "GENERATOR_SOURCE", malicious)
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    assert report["summary"]["state"] == "DENY_FROZEN_SOURCE_OR_INPUT_HASH_DRIFT"
    assert marker.exists() is False
    assert report["ephemeral_preview"]["runtime_hash"]["generator_source_executed"] is False


def test_pin_then_source_swap_still_has_no_load_path(direct_root, monkeypatch):
    marker = direct_root / "swap_side_effect.marker"
    source = direct_root / "swap_generator.py"
    initial = b"VALUE = 1\n"
    source.write_bytes(initial)
    monkeypatch.setattr(readiness, "GENERATOR_SOURCE", source)
    monkeypatch.setattr(
        readiness,
        "EXPECTED_GENERATOR_SOURCE",
        {"bytes": len(initial), "sha256": sha(initial)},
    )
    assert readiness._source_statuses()["generator_source"]["pass"] is True
    source.write_text(
        "from pathlib import Path\n"
        + f"Path({str(marker)!r}).write_text('EXECUTED', encoding='utf-8')\n",
        encoding="utf-8",
    )
    preview = readiness._runtime_hash_preview()
    assert preview["status"] == "NOT_COMPUTED_BY_DESIGN_NONAUTHORITATIVE"
    assert marker.exists() is False
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200
    )
    assert report["summary"]["state"] == "DENY_FROZEN_SOURCE_OR_INPUT_HASH_DRIFT"
    assert marker.exists() is False


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_alias",
        "rename_c01",
        "extra_unknown",
    ],
)
def test_owner_decision_keyset_must_be_exact(direct_root, now, mutation):
    data = owner_payload(now)
    if mutation == "extra_alias":
        data["decisions"]["c01"] = data["decisions"]["c01_unified_r2_research_candidate"]
    elif mutation == "rename_c01":
        data["decisions"]["c01_candidate"] = data["decisions"].pop(
            "c01_unified_r2_research_candidate"
        )
    else:
        data["decisions"]["unexpected"] = {}
    source, digest = write_owner(direct_root, data)
    parsed, provenance = readiness._read_direct_owner_source(source, digest, now)
    assert parsed is None
    assert provenance["status"] == "DENY_OWNER_DECISION_KEYSET_MUST_BE_EXACT"


def test_verify_duplicate_key_raw_bytes_fail_structural(now, tmp_path):
    raw = (
        '{"schema":"PREAUTHORIZATION_READINESS_REPORT_V1",'
        '"schema":"PREAUTHORIZATION_READINESS_REPORT_V1"}'
    ).encode("utf-8")
    result = readiness._verify_readiness_raw_bytes(raw, report_path=tmp_path / "duplicate.json", now=now)
    assert result["structural_passed"] is False
    assert result["live_readiness_passed"] is False
    assert any("DuplicateKeyError" in error for error in result["errors"])


@pytest.mark.parametrize(
    "formal_key,value",
    [
        ("owner_accepted", True),
        ("authority_flags", {}),
        ("run_id", "FORBIDDEN"),
        ("issued_utc", "2026-08-24T08:00:00Z"),
        ("expires_utc", "2026-08-24T09:00:00Z"),
        ("source_sha256", "0" * 64),
        ("input_sha256", "0" * 64),
        ("runtime_code_sha256", "0" * 64),
    ],
)
def test_verify_rejects_every_formal_authorization_top_field(now, tmp_path, formal_key, value):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200, now=now
    )
    report[formal_key] = value
    result = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=tmp_path / "formal.json", now=now
    )
    assert result["structural_passed"] is False
    assert result["checks"]["exact_top_level_whitelist"] is False
    assert result["checks"]["no_formal_authorization_top_level_fields"] is False


def test_verify_rejects_arbitrary_extra_top_field(now, tmp_path):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200, now=now
    )
    report["unexpected"] = 1
    result = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=tmp_path / "extra.json", now=now
    )
    assert result["structural_passed"] is False
    assert result["checks"]["complete_json_schema"] is False


def test_verify_rejects_nested_additional_property(now, tmp_path):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=7200, now=now
    )
    report["summary"]["unexpected"] = False
    result = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=tmp_path / "nested.json", now=now
    )
    assert result["structural_passed"] is False
    assert result["checks"]["complete_json_schema"] is False


def test_verify_expired_preview_is_structural_but_not_live(now, tmp_path):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=60, now=now - timedelta(seconds=120)
    )
    result = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=tmp_path / "expired.json", now=now
    )
    assert result["structural_passed"] is True
    assert result["live_readiness_passed"] is False
    assert result["checks"]["preview_live_now_before_expiry"] is False


def test_verify_future_issued_preview_is_not_live(now, tmp_path):
    report = readiness.build_readiness_report(
        owner_source=None, expected_source_sha256=None, valid_for_seconds=60, now=now + timedelta(seconds=1)
    )
    result = readiness._verify_readiness_raw_bytes(
        json.dumps(report).encode("utf-8"), report_path=tmp_path / "future.json", now=now
    )
    assert result["structural_passed"] is True
    assert result["live_readiness_passed"] is False
    assert result["checks"]["preview_issued_not_future"] is False


def test_owner_ready_expiry_is_capped_by_owner_statement_freshness(direct_root, now, monkeypatch):
    monkeypatch.setattr(readiness, "_available_memory_gib", lambda: (8.0, "TEST_HIGH_MEMORY"))
    owner_time = now - timedelta(seconds=7100)
    source, digest = write_owner(direct_root, owner_payload(owner_time, ack=None))
    report = readiness.build_readiness_report(
        owner_source=source,
        expected_source_sha256=digest,
        valid_for_seconds=7200,
        now=now,
    )
    expires = readiness._parse_utc(report["ephemeral_preview"]["expires_utc_preview"])
    assert expires == owner_time + timedelta(seconds=7200)
    assert (expires - now).total_seconds() == 100
    assert report["summary"]["state"] == "STRUCTURALLY_READY_FOR_AUTHENTICATED_ISSUER_REVIEW__IDENTITY_UNVERIFIED__NO_AUTHORITY_CREATED"


def test_secure_owner_read_uses_stable_no_share_handle(direct_root, now):
    source, digest = write_owner(direct_root, owner_payload(now))
    payload, meta = safe_io.secure_read_bytes(
        source, allowed_roots=[direct_root], max_bytes=readiness.MAX_OWNER_SOURCE_BYTES
    )
    assert sha(payload) == digest
    assert meta["handle_identity_stable"] is True
    assert meta["parent_directory_handle_stable"] is True
    assert Path(meta["parent_final_handle_path"]).resolve() == direct_root.resolve()
    assert "NO_REPARSE" in meta["method"] or "O_NOFOLLOW" in meta["method"]


def test_secure_owner_read_preserves_exact_crlf_raw_bytes(direct_root):
    source = direct_root / "raw_crlf.txt"
    expected = b'{"raw":"bytes"}\r\n'
    source.write_bytes(expected)
    observed, meta = safe_io.secure_read_bytes(source, allowed_roots=[direct_root])
    assert observed == expected
    assert meta["bytes"] == len(expected)


def test_safe_writer_missing_root_fails_without_creating_it(tmp_path, monkeypatch):
    fake_project = tmp_path / "missing_project"
    fake_project.mkdir()
    fake_root = fake_project / "40_evidence/artifacts/authorization_readiness/unified_r2_v2"
    monkeypatch.setattr(safe_io, "PROJECT_ROOT", fake_project)
    monkeypatch.setattr(safe_io, "EVIDENCE_ROOT", fake_root)
    with pytest.raises(safe_io.SafeIOError, match="MUST_PREEXIST"):
        safe_io.write_fixed_json("PREAUTHORIZATION_READINESS_OWNER_ASSESSMENT_V1.json", {"x": 1})
    assert fake_root.exists() is False


def test_safe_writer_reparse_root_negative_control_has_zero_write(tmp_path, monkeypatch):
    fake_project = tmp_path / "reparse_project"
    fake_root = fake_project / "40_evidence/artifacts/authorization_readiness/unified_r2_v2"
    fake_root.mkdir(parents=True)
    monkeypatch.setattr(safe_io, "PROJECT_ROOT", fake_project)
    monkeypatch.setattr(safe_io, "EVIDENCE_ROOT", fake_root)
    original_is_reparse = safe_io._is_reparse
    monkeypatch.setattr(
        safe_io,
        "_is_reparse",
        lambda path: True if path.absolute() == fake_root.absolute() else original_is_reparse(path),
    )
    before = sorted(item.relative_to(fake_root).as_posix() for item in fake_root.rglob("*"))
    with pytest.raises(safe_io.SafeIOError, match="REPARSE_OR_SYMLINK"):
        safe_io.write_fixed_json("PREAUTHORIZATION_READINESS_OWNER_ASSESSMENT_V1.json", {"x": 1})
    after = sorted(item.relative_to(fake_root).as_posix() for item in fake_root.rglob("*"))
    assert before == after == []


def test_safe_writer_actual_junction_or_symlink_root_has_zero_write(tmp_path, monkeypatch):
    fake_project = tmp_path / "actual_reparse_project"
    expected_parent = fake_project / "40_evidence/artifacts/authorization_readiness"
    expected_parent.mkdir(parents=True)
    real_target = tmp_path / "outside_reparse_target"
    real_target.mkdir()
    fake_root = expected_parent / "unified_r2_v2"
    if os.name == "nt":
        created = subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(fake_root), str(real_target)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        assert created.returncode == 0, created.stdout
    else:
        fake_root.symlink_to(real_target, target_is_directory=True)
    try:
        assert safe_io._is_reparse(fake_root) is True
        monkeypatch.setattr(safe_io, "PROJECT_ROOT", fake_project)
        monkeypatch.setattr(safe_io, "EVIDENCE_ROOT", fake_root)
        before = sorted(item.relative_to(real_target).as_posix() for item in real_target.rglob("*"))
        with pytest.raises(safe_io.SafeIOError, match="REPARSE_OR_SYMLINK"):
            safe_io.write_fixed_json(
                "PREAUTHORIZATION_READINESS_OWNER_ASSESSMENT_V1.json", {"x": 1}
            )
        after = sorted(item.relative_to(real_target).as_posix() for item in real_target.rglob("*"))
        assert before == after == []
    finally:
        if os.name == "nt":
            os.rmdir(fake_root)
        else:
            fake_root.unlink()


def test_all_four_production_writers_use_common_safe_io():
    for filename in (
        "preauthorization_readiness.py",
        "validate_release.py",
        "independent_audit.py",
        "build_release.py",
    ):
        tree = ast.parse((TOOL_DIR / filename).read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom) and node.module == "safe_io"
            for node in tree.body
        ), filename
