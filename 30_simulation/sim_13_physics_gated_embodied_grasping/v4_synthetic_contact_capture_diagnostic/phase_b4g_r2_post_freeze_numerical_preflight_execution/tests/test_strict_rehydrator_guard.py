from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from r2_preflight.execution_guard import (
    AuthorizationReceipt,
    ConsumedAuthorizationReceipt,
    ExecutionAuthorizationError,
    authorized_lazy_imports,
    consume_authorization,
    create_output_root_after_authorization,
    legacy_modules_loaded,
    _current_local_source_inventory,
    _verify_local_source_manifest,
)
from r2_preflight.rehydrator import (
    COMMON_GROUP_SHA256,
    DONOR_PAYLOAD_SHA256,
    RehydrationError,
    collect_mutable_ids,
    donor_immutability_guard,
    fixture_hashes,
    isolated_common_fixture,
    rehydrate_payload,
    to_payload,
)
from r2_preflight.strict_json import StrictJSONError, canonical_bytes, canonical_sha256, loads


@pytest.mark.parametrize("text", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":null}'])
def test_strict_json_rejects_ambiguous_or_nonfinite(text: str) -> None:
    with pytest.raises(StrictJSONError):
        loads(text)


def test_donor_complete_typed_roundtrip_and_group(donor) -> None:
    hashes = fixture_hashes(donor)
    assert hashes == {
        "payload_canonical_bytes": 31092,
        "payload_sha256": DONOR_PAYLOAD_SHA256,
        "group_canonical_bytes": 1317,
        "group_sha256": COMMON_GROUP_SHA256,
    }
    payload = to_payload(donor, include_matrices=True)
    assert len(canonical_bytes(payload)) == 31092
    assert canonical_sha256(payload) == DONOR_PAYLOAD_SHA256
    assert np.array_equal(donor.acquisition.eta_plus, donor.acquisition.z_plus_reduced[:14])
    assert donor.event.time_s == donor.acquisition.acquisition_time_s == donor.acquisition.snapshot.acquisition_time_s


def test_rehydrator_rejects_value_shape_type_and_partial_payload(donor) -> None:
    payload = to_payload(donor)
    mutations = []
    changed = deepcopy(payload); changed["event"]["service"]["base_position_inertial_m"][0] += 1e-12; mutations.append(changed)
    shaped = deepcopy(payload); shaped["acquisition"]["matrices"]["A"][0].pop(); mutations.append(shaped)
    typed = deepcopy(payload); typed["event"]["service"]["base_position_inertial_m"][0] = 1; mutations.append(typed)
    partial = deepcopy(payload); del partial["acquisition"]["matrices"]; mutations.append(partial)
    for value in mutations:
        with pytest.raises(RehydrationError):
            rehydrate_payload(value, DONOR_PAYLOAD_SHA256)


def test_rehydrator_consumes_nested_key_and_json_type_schema(donor) -> None:
    payload = to_payload(donor)
    metric_int = deepcopy(payload)
    metric_key = next(iter(metric_int["acquisition"]["metrics"]))
    metric_int["acquisition"]["metrics"][metric_key] = 0
    backend_extra = deepcopy(payload)
    backend_extra["acquisition"]["backend_provenance"]["hidden_backend_alias"] = "forbidden"
    criterion_int = deepcopy(payload)
    criterion_int["event"]["criteria"]["all_ledgers_closed"] = 1
    wrench_bool = deepcopy(payload)
    wrench_bool["acquisition"]["wrench_audit"]["contact_chord_unit_vector"][0] = False
    for value in (metric_int, backend_extra, criterion_int, wrench_bool):
        # Recompute the declared outer certificate so rejection proves the typed
        # nested schema, not merely the frozen donor hash, killed the mutation.
        with pytest.raises(RehydrationError):
            rehydrate_payload(value, canonical_sha256(value))


def test_float32_and_cross_case_mutable_identity_rejected(donor) -> None:
    first = isolated_common_fixture(donor)
    second = isolated_common_fixture(donor)
    assert not (collect_mutable_ids(donor) & collect_mutable_ids(first))
    assert not (collect_mutable_ids(first) & collect_mutable_ids(second))
    object.__setattr__(first.acquisition, "z_plus_reduced", first.acquisition.z_plus_reduced.astype(np.float32))
    with pytest.raises(RehydrationError):
        fixture_hashes(first)


def test_donor_guard_checks_finally_on_case_exception(donor) -> None:
    clone = isolated_common_fixture(donor)
    with pytest.raises(RehydrationError):
        with donor_immutability_guard(clone):
            clone.acquisition.z_plus_reduced[0] += 1e-9
            raise RuntimeError("synthetic case failure")


def test_guard_denies_before_import_and_output(package_root: Path) -> None:
    output = package_root / "NEVER_CREATED_TEST_OUTPUT"
    process = subprocess.run(
        [sys.executable, "-B", "-m", "r2_preflight.execution_guard", "--output-root", str(output)],
        cwd=package_root, text=True, capture_output=True, check=False,
    )
    assert process.returncode == 23
    assert "MISSING_SINGLE_EXECUTION_AUTHORIZATION" in process.stdout
    assert "legacy_modules_loaded': []" in process.stdout
    assert not output.exists()
    assert legacy_modules_loaded() == []


def test_forged_public_receipts_cannot_import_or_create(package_root: Path) -> None:
    output = package_root / "NEVER_CREATED_FORGED_RECEIPT_OUTPUT"
    receipt = AuthorizationReceipt("x", "0" * 64, 0, "0" * 64, "0" * 64, "x", "0" * 64)
    consumed = ConsumedAuthorizationReceipt(receipt, "0" * 64)
    calls = (
        lambda: consume_authorization(receipt, package_root=package_root),
        lambda: authorized_lazy_imports(consumed, package_root=package_root),
        lambda: create_output_root_after_authorization(consumed, output),
    )
    for call in calls:
        with pytest.raises(ExecutionAuthorizationError, match="EXECUTION_PATH_NOT_IMPLEMENTED"):
            call()
    assert not output.exists()
    assert legacy_modules_loaded() == []


def test_guard_independently_rebuilds_complete_source_manifest(package_root: Path) -> None:
    sources = _current_local_source_inventory(package_root)
    manifest = {
        "schema": "SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1",
        "scope": "LOCAL_SOURCE_AND_CONTRACT_BYTES_ONLY_NO_EXECUTION",
        "self_excluded": True,
        "acyclic": True,
        "terminal_excluded": True,
        "excluded_path_prefixes": ["evidence/", "results/"],
        "terminal_exclusion_rule": "TERMINAL_GENERATED_LAST_AND_RECORDS_GATE_ONLY",
        "source_count": len(sources),
        "sources": sources,
        "source_inventory_sha256": canonical_sha256(sources),
        "r2_numerical_preflight_executed": False,
        "trajectory_count": 0,
    }
    assert _verify_local_source_manifest(package_root, manifest) == sources
    forged = deepcopy(manifest)
    forged["sources"][0]["bytes"] += 1
    forged["source_inventory_sha256"] = canonical_sha256(forged["sources"])
    with pytest.raises(ExecutionAuthorizationError, match="CURRENT_INVENTORY_DRIFT"):
        _verify_local_source_manifest(package_root, forged)
