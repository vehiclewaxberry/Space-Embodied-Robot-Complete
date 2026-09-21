from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

import b4g_validation.artifact_derivation as artifact_derivation
from b4g_validation.artifact_derivation import (
    ArtifactDerivationError,
    derive_nominal_payload,
    validate_nominal_payload_derivation,
)


PHASE_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = PHASE_ROOT / "contracts"


@pytest.fixture(scope="module")
def contracts() -> dict[str, object]:
    def load(name: str) -> dict:
        return json.loads((CONTRACT_ROOT / name).read_text(encoding="utf-8"))

    reference = load("PHASE_B4G_REFERENCE_FORCE_V1.json")
    return {
        "spec": load("PHASE_B4G_MUTATION_HARNESS_SPEC_V1.json"),
        "schedule": load("PHASE_B4G_REGISTERED_SCHEDULE_V1.json"),
        "governance": load("PHASE_B4G_GOVERNANCE_V1.json"),
        "bindings": load("PHASE_B4G_SOURCE_BINDINGS_V1.json"),
        "qref": reference["individual_finger_reference_force_N"],
    }


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    return path


def _record(role: str, path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "role": role,
        "path": path.resolve().as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
    }


def _manifest(tmp_path: Path) -> dict[str, object]:
    return _record(
        "EXECUTION_SOURCE_MANIFEST",
        _write_json(tmp_path / "source_manifest.json", {"schema": "TEST_SOURCE_MANIFEST"}),
    )


def _kwargs(tmp_path: Path, contracts: dict[str, object]) -> dict[str, object]:
    phase_root = tmp_path / "phase"
    phase_root.mkdir(parents=True, exist_ok=True)
    return {
        "project_root": tmp_path,
        "phase_root": phase_root,
        "source_bindings": contracts["bindings"],
        "mutation_spec": contracts["spec"],
        "frozen_schedule": contracts["schedule"],
        "governance": contracts["governance"],
        "frozen_q_ref": contracts["qref"],
    }


def test_nc01_is_derived_from_bound_source_bytes_and_forged_base_is_rejected(
    tmp_path: Path, contracts: dict[str, object],
) -> None:
    source = tmp_path / "bound.bin"
    source.write_bytes(b"frozen-parent\n")
    mutant = tmp_path / "mutant.bin"
    mutant.write_bytes(b"frozen-parent\x0b")
    records = [
        _manifest(tmp_path),
        _record("BOUND_PARENT_SOURCE", source),
        _record("MUTANT_RAW_BYTES", mutant),
    ]
    kwargs = _kwargs(tmp_path, contracts)
    source_record = records[1]
    kwargs["source_bindings"] = {
        "sources": [{
            "id": "b4f_audited_gate",
            "path": source_record["path"],
            "bytes": source_record["bytes"],
            "sha256": source_record["sha256"],
            "role": "TEST_BOUND_PARENT",
        }]
    }
    result = derive_nominal_payload("B4FNC01", records, **kwargs)
    assert result.derived_payload["source_record"] == result.derived_payload["candidate_record"]
    assert result.derived_payload["xor_mutation"] == {
        "applied": False,
        "byte_offset_from_end": 1,
        "xor_mask_hex": "00",
    }
    assert result.derived_mutant_payload["candidate_record"] == {
        key: records[2][key] for key in ("path", "bytes", "sha256")
    }
    assert result.derived_mutant_payload["xor_mutation"] == {
        "applied": True,
        "byte_offset_from_end": 1,
        "xor_mask_hex": "01",
    }
    validate_nominal_payload_derivation(
        "B4FNC01", result.derived_payload, records, **kwargs
    )
    forged = deepcopy(result.derived_payload)
    forged["candidate_record"]["sha256"] = "0" * 64
    with pytest.raises(ArtifactDerivationError, match="BASE_PAYLOAD_NOT_ARTIFACT_DERIVED"):
        validate_nominal_payload_derivation(
            "B4FNC01", forged, records, **kwargs
        )

    impostor = tmp_path / "self_hashed_impostor.bin"
    impostor.write_bytes(source.read_bytes())
    impostor_records = [records[0], _record("BOUND_PARENT_SOURCE", impostor), records[2]]
    with pytest.raises(ArtifactDerivationError, match="NC01_BOUND_PARENT_NOT_SOURCE_BINDING"):
        derive_nominal_payload("B4FNC01", impostor_records, **kwargs)


def test_artifact_role_inventory_and_hash_are_fail_closed(
    tmp_path: Path, contracts: dict[str, object],
) -> None:
    schedule_path = _write_json(tmp_path / "schedule.json", contracts["schedule"])
    records = [_manifest(tmp_path), _record("FROZEN_REGISTERED_SCHEDULE", schedule_path)]
    nominal = derive_nominal_payload("B4FNC16", records, **_kwargs(tmp_path, contracts))
    assert nominal.derived_payload == {"schedule": contracts["schedule"]}

    missing = records[:-1]
    with pytest.raises(ArtifactDerivationError, match="ARTIFACT_ROLE_SET_MISMATCH"):
        derive_nominal_payload("B4FNC16", missing, **_kwargs(tmp_path, contracts))

    schedule_path.write_bytes(schedule_path.read_bytes() + b" ")
    with pytest.raises(ArtifactDerivationError, match="ARTIFACT_BYTE_COUNT_MISMATCH"):
        derive_nominal_payload("B4FNC16", records, **_kwargs(tmp_path, contracts))


@pytest.mark.parametrize("parent", ["B4FNC09", "B4FNC10"])
def test_classifier_nominal_is_rebuilt_from_hash_bound_fixture(
    tmp_path: Path, contracts: dict[str, object], parent: str,
) -> None:
    spec_path = _write_json(tmp_path / f"{parent}_spec.json", contracts["spec"])
    records = [_manifest(tmp_path), _record("FROZEN_CLASSIFIER_FIXTURE_CONTRACT", spec_path)]
    result = derive_nominal_payload(parent, records, **_kwargs(tmp_path, contracts))
    assert result.derived_payload["observed_finite_event"] is False
    assert result.derived_payload["classifier_mode"] == "BILATERAL_HERMITE_ALL_ROOT_EARLIEST_DWELL"
    assert result.derived_mutant_payload["observed_finite_event"] is True
    assert result.derived_mutant_payload["classifier_mode"] == (
        "SINGLE_SIDE_LEFT" if parent == "B4FNC09" else "ENDPOINT_ONLY"
    )


@pytest.mark.parametrize("parent,key", [("B4FNC19", "candidate"), ("B4FNC22", "report")])
def test_governance_payload_is_contract_derived(
    tmp_path: Path, contracts: dict[str, object], parent: str, key: str,
) -> None:
    governance_path = _write_json(tmp_path / f"{parent}_governance.json", contracts["governance"])
    records = [_manifest(tmp_path), _record("FROZEN_GOVERNANCE_CONTRACT", governance_path)]
    if parent == "B4FNC22":
        schedule_path = _write_json(tmp_path / "schedule.json", contracts["schedule"])
        records.append(_record("FROZEN_REGISTERED_SCHEDULE", schedule_path))
    result = derive_nominal_payload(parent, records, **_kwargs(tmp_path, contracts))
    value = result.derived_payload[key]
    assert all(value[field] is False for field in contracts["governance"]["required_false"])
    assert all(value[field] is None for field in contracts["governance"]["required_null_physical_inputs"])
    mutant = result.derived_mutant_payload[key]
    if parent == "B4FNC19":
        false_field = contracts["spec"]["deterministic_targets_and_amplitudes"]["nc19_required_false_fields"][0]
        assert mutant[false_field] is True
        type_swapped = deepcopy(result.derived_payload)
        type_swapped[key][false_field] = 0
        with pytest.raises(ArtifactDerivationError, match="BASE_PAYLOAD_NOT_ARTIFACT_DERIVED"):
            validate_nominal_payload_derivation(
                parent, type_swapped, records, **_kwargs(tmp_path, contracts)
            )
    else:
        assert mutant["reported_label"] == "minimum_required_force"


def test_nc17_fallback_rebuilds_both_six_lane_formulae(
    tmp_path: Path, contracts: dict[str, object],
) -> None:
    spec_path = _write_json(tmp_path / "mutation_spec.json", contracts["spec"])
    schedule_path = _write_json(tmp_path / "schedule.json", contracts["schedule"])
    supplemental_path = _write_json(
        tmp_path / "a2_detector_trace.json",
        {"schema": "TEST_ONLY_ROLE_PRESENCE; semantic replay tested separately"},
    )
    records = [
        _manifest(tmp_path),
        _record("FROZEN_MUTATION_FALLBACK_CONTRACT", spec_path),
        _record("FROZEN_REGISTERED_SCHEDULE", schedule_path),
        _record("A2_DETECTOR_SIX_LANE_TRACE", supplemental_path),
    ]
    kwargs = _kwargs(tmp_path, contracts)
    _write_json(
        Path(kwargs["phase_root"]) / "results"
        / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json",
        {"selector": {"selected_parent_level": None}},
    )
    qref = float(contracts["qref"])
    half = derive_nominal_payload(
        "B4FNC17", records, subvariant_index=1, **kwargs
    )
    off = derive_nominal_payload(
        "B4FNC17", records, subvariant_index=2, **kwargs
    )
    assert len(half.derived_payload["lanes"]) == len(off.derived_payload["lanes"]) == 6
    assert half.derived_payload["lanes"][0]["right_Q_2"] == [2.0 * qref, qref]
    assert off.derived_payload["lanes"][0]["right_Q_2"] == [2.0 * qref, 0.0]
    assert half.derived_mutant_payload["lanes"][0]["right_Q_2"] == [2.0 * qref, 1.5 * qref]
    assert off.derived_mutant_payload["lanes"][0]["right_Q_2"] == [2.0 * qref, 0.5 * qref]

    _write_json(
        Path(kwargs["phase_root"]) / "results"
        / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json",
        {
            "selector": {
                "selected_parent_level": {
                    "alpha": 2.0, "command_duration_s": 0.01,
                }
            }
        },
    )
    with pytest.raises(
        ArtifactDerivationError,
        match="NC17_BRANCH_NOT_AUTHORIZED_BY_CAMPAIGN_SELECTOR",
    ):
        derive_nominal_payload(
            "B4FNC17", records, subvariant_index=1, **kwargs
        )


def _case_records(
    tmp_path: Path,
    *,
    case_id: str,
    schedule: dict,
    arrays: dict[str, np.ndarray],
    qref: float,
) -> list[dict[str, object]]:
    slot = next(row for row in schedule["slots"] if row["case_id"] == case_id)
    safe = "".join(character if character.isalnum() else "_" for character in case_id)
    stem = f"{int(slot['slot_index']):03d}__{safe}"
    raw_root = tmp_path / "phase" / "evidence" / "raw_cases"
    raw_root.mkdir(parents=True, exist_ok=True)
    npz_path = raw_root / f"{stem}.npz"
    np.savez(npz_path, **arrays)
    npz_record = _record("REGISTERED_CASE_RAW_NPZ", npz_path)
    metadata = {
        "case_id": case_id,
        "lane_id": slot["lane_id"],
        "arm": slot["arm"],
        "registered_slot": slot,
        "execution_status": "EXECUTED_FRESH_REGISTERED_SLOT",
        "event_provenance": {"acquisition_time_s": 0.25},
        "command_parameters": {"Q_ref_per_finger_N": qref},
        "npz_path": npz_path.resolve().as_posix(),
        "npz_bytes": npz_record["bytes"],
        "npz_sha256": npz_record["sha256"],
        "npz_arrays": sorted(arrays),
    }
    metadata_path = _write_json(raw_root / f"{stem}.json", metadata)
    return [
        _manifest(tmp_path),
        _record("REGISTERED_CASE_METADATA", metadata_path),
        npz_record,
    ]


def test_nc02_command_payload_comes_from_numeric_npz(
    tmp_path: Path, contracts: dict[str, object],
) -> None:
    case_id = contracts["spec"]["deterministic_targets_and_amplitudes"]["a0_slot"]
    arrays = {
        "time_s": np.asarray([0.25, 0.251]),
        "command_Q_14": np.zeros((2, 14)),
    }
    records = _case_records(
        tmp_path, case_id=case_id, schedule=contracts["schedule"], arrays=arrays,
        qref=float(contracts["qref"]),
    )
    result = derive_nominal_payload("B4FNC02", records, **_kwargs(tmp_path, contracts))
    assert result.derived_payload["observed_Q_14"] == [0.0] * 14
    assert result.derived_mutant_payload["observed_Q_14"][12] == float(contracts["qref"])
    forged = deepcopy(result.derived_payload)
    forged["observed_Q_14"][12] = float(contracts["qref"])
    with pytest.raises(ArtifactDerivationError, match="BASE_PAYLOAD_NOT_ARTIFACT_DERIVED"):
        validate_nominal_payload_derivation(
            "B4FNC02", forged, records, **_kwargs(tmp_path, contracts)
        )

    # A byte-identical coordinated copy is still not the registered raw slot.
    official_metadata = Path(str(records[1]["path"]))
    copied_metadata = tmp_path / "coordinated_copy.json"
    copied_metadata.write_bytes(official_metadata.read_bytes())
    copied_records = [records[0], _record("REGISTERED_CASE_METADATA", copied_metadata), records[2]]
    with pytest.raises(ArtifactDerivationError, match="CASE_ARTIFACT_NOT_OFFICIAL_RAW_SLOT_PATH"):
        derive_nominal_payload("B4FNC02", copied_records, **_kwargs(tmp_path, contracts))


def test_nc05_work_is_independently_integrated_and_self_hashed_forgery_fails(
    tmp_path: Path, contracts: dict[str, object],
) -> None:
    case_id = contracts["spec"]["deterministic_targets_and_amplitudes"]["default_registered_forced_slot"]
    service = np.zeros((2, 29))
    service[:, 27] = 1.0
    command = np.zeros((2, 14))
    command[1, 12] = 1.0
    work = np.asarray([0.0, 0.05])
    arrays = {
        "time_s": np.asarray([0.0, 0.1]),
        "service_state_29": service,
        "command_Q_14": command,
        "signed_W_act_J": work,
        "total_kinetic_energy_J": work.copy(),
        "energy_minus_work_residual_J": np.zeros(2),
    }
    records = _case_records(
        tmp_path, case_id=case_id, schedule=contracts["schedule"], arrays=arrays,
        qref=float(contracts["qref"]),
    )
    result = derive_nominal_payload("B4FNC05", records, **_kwargs(tmp_path, contracts))
    assert result.derived_payload["signed_W_act_J"] == [0.0, 0.05]
    assert result.derived_mutant_payload["signed_W_act_J"] == [0.0, 0.0]

    forged_arrays = deepcopy(arrays)
    forged_arrays["signed_W_act_J"] = np.asarray([0.0, 0.2])
    forged_arrays["total_kinetic_energy_J"] = np.asarray([0.0, 0.2])
    forged_root = tmp_path / "forged"
    forged_root.mkdir()
    forged_records = _case_records(
        forged_root, case_id=case_id, schedule=contracts["schedule"],
        arrays=forged_arrays, qref=float(contracts["qref"]),
    )
    with pytest.raises(ArtifactDerivationError, match="WORK_TRACE_QUADRATURE_MISMATCH"):
        derive_nominal_payload(
            "B4FNC05", forged_records, **_kwargs(forged_root, contracts)
        )


def test_finite_harness_top_precondition_cannot_substitute_for_raw_proof(
    tmp_path: Path, contracts: dict[str, object],
) -> None:
    spoof = {
        "schema": "SIM13_V4B4G_MUTATION_FINITE_HARNESS_RAW_V1",
        "harness_id": contracts["spec"]["finite_event_harness"]["id"],
        "finite_event_harness_contract": contracts["spec"]["finite_event_harness"],
        "Q_ref_N": contracts["qref"],
        "finite_event_harness_precondition": {
            "finite_removal_event": True,
            "abs_W_act_at_removal_J": 1.0,
            "post_release_passed": True,
            "passed": True,
        },
    }
    raw_path = _write_json(tmp_path / "spoof_raw.json", spoof)
    records = [_manifest(tmp_path), _record("EXECUTED_FINITE_HARNESS_RAW_OUTPUT", raw_path)]
    with pytest.raises(ArtifactDerivationError, match="FINITE_RAW_TOP_FIELD_SET"):
        derive_nominal_payload("B4FNC07", records, **_kwargs(tmp_path, contracts))


def test_immutable_b4e_parent_fixture_is_byte_bound(tmp_path: Path) -> None:
    source = (
        PHASE_ROOT.parent
        / "phase_b4_post_freeze_synthetic_6d_solver"
        / "evidence"
        / "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json"
    )
    destination = (
        tmp_path
        / "phase_b4_post_freeze_synthetic_6d_solver"
        / "evidence"
        / source.name
    )
    destination.parent.mkdir(parents=True)
    shutil.copyfile(source, destination)
    fixture, digest = artifact_derivation._load_bound_parent_fixture(tmp_path / "phase")
    assert fixture["schema"] == "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1"
    assert digest == "14DC9D22963D8F6930AF69FBFB0B0001DD4629DCFBDFFCFA3CE05FA1847C9FAB"

    data = bytearray(destination.read_bytes())
    data[-2] ^= 0x01
    destination.write_bytes(bytes(data))
    with pytest.raises(ArtifactDerivationError, match="FINITE_PARENT_FIXTURE_BYTE_BINDING"):
        artifact_derivation._load_bound_parent_fixture(tmp_path / "phase")
