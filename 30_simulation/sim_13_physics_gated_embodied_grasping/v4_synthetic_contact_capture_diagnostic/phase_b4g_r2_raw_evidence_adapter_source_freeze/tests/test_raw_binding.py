from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

import r2_raw_adapter.adapter as adapter_module
from r2_raw_adapter.adapter import AdapterError, OUTCOME_A0, OUTCOME_COMMON, OUTCOME_NO_REMOVAL, load_bound_case
from r2_raw_adapter.array_contract import ARRAY_CONTRACT_DOCUMENT_SHA256, PROFILE_DEFINITIONS
from r2_raw_adapter.fixture_factory import write_case
from r2_raw_adapter.schedule_binding import schedule_records


def test_exact_finite_raw_load_and_immutable_arrays(tmp_path: Path) -> None:
    relative = write_case(tmp_path, horizon_s=0.0006)
    case = load_bound_case(tmp_path, relative)
    assert len(case.arrays) == 56
    assert case.array_contract_sha256 == case.sidecar["array_contract_sha256"]
    assert case.sidecar["array_contract_document_sha256"] == ARRAY_CONTRACT_DOCUMENT_SHA256
    assert case.arrays["time_s"].flags.writeable is False
    with pytest.raises(ValueError):
        case.arrays["time_s"].setflags(write=True)
    with pytest.raises((AttributeError, TypeError)):
        case.sidecar["registered_roles"].append("FORGED")
    with pytest.raises(TypeError):
        case.sidecar["source_hashes"]["matrix_sha256"] = "A" * 64
    binding = case.raw_binding()
    assert binding["sidecar_sha256"] == case.sidecar_sha256
    assert binding["sidecar_bytes"] == case.sidecar_bytes


@pytest.mark.parametrize("outcome", [OUTCOME_NO_REMOVAL, OUTCOME_COMMON, OUTCOME_A0])
def test_zero_length_event_and_post_arrays_without_null(tmp_path: Path, outcome: str) -> None:
    kwargs = {"outcome": outcome, "horizon_s": 0.0005}
    if outcome == OUTCOME_NO_REMOVAL:
        kwargs.update({"horizon_s": 0.08})
    if outcome == OUTCOME_COMMON:
        kwargs.update({"horizon_s": 0.005, "command_duration_s": 0.005})
    relative = write_case(tmp_path, **kwargs)
    case = load_bound_case(tmp_path, relative)
    assert int(case.arrays["bilateral_removal_event_count"]) == 0
    assert case.arrays["bilateral_removal_event_time_s"].shape == (0,)
    assert case.arrays["post_time_s"].shape == (0,)


def test_each_common_case_uncached_rehydrates_donor_before_and_after_npz(tmp_path: Path, monkeypatch) -> None:
    roots = [tmp_path / "one", tmp_path / "two"]
    relatives = [
        write_case(root, outcome=OUTCOME_COMMON, horizon_s=0.005, command_duration_s=0.005)
        for root in roots
    ]
    original = adapter_module.common_donor_projection
    calls = 0

    def counted():
        nonlocal calls
        calls += 1
        return original()

    monkeypatch.setattr(adapter_module, "common_donor_projection", counted)
    for root, relative in zip(roots, relatives):
        load_bound_case(root, relative)
    assert calls == 4


def test_legacy_b4g_keyset_cannot_impersonate_r2(tmp_path: Path) -> None:
    def mutate(arrays: dict[str, np.ndarray]) -> None:
        arrays.pop("stage_augmented_W_act_J")
    relative = write_case(tmp_path, array_mutator=mutate)
    with pytest.raises(AdapterError, match="EXACT_MEMBER_SET"):
        load_bound_case(tmp_path, relative)


@pytest.mark.parametrize(
    "mutator,pattern",
    [
        (lambda a: a.__setitem__("time_s", a["time_s"].astype(">f8")), "DTYPE_OR_ENDIAN"),
        (lambda a: a.__setitem__("time_s", a["time_s"].astype("<f4")), "DTYPE_OR_ENDIAN"),
        (lambda a: a.__setitem__("time_s", np.asarray(["x"] * len(a["time_s"]))), "DTYPE_OR_ENDIAN"),
        (lambda a: a.__setitem__("time_s", np.asarray([object()] * len(a["time_s"]), dtype=object)), "PICKLE_OBJECT"),
        (lambda a: a["time_s"].__setitem__(1, np.nan), "NONFINITE"),
        (lambda a: a["time_s"].__setitem__(1, np.inf), "NONFINITE"),
        (lambda a: a.__setitem__("service_state_29", a["service_state_29"][:, :28]), "SHAPE_INVALID"),
    ],
)
def test_dtype_endian_object_nonfinite_and_shape_rejected(tmp_path: Path, mutator, pattern: str) -> None:
    relative = write_case(tmp_path, array_mutator=mutator)
    with pytest.raises(AdapterError, match=pattern):
        load_bound_case(tmp_path, relative)


def test_nonmonotone_and_empty_time_rejected(tmp_path: Path) -> None:
    relative = write_case(tmp_path, array_mutator=lambda a: a["time_s"].__setitem__(1, a["time_s"][0]))
    with pytest.raises(AdapterError, match="STRICTLY_INCREASING"):
        load_bound_case(tmp_path, relative)
    other = tmp_path / "other"
    relative = write_case(other, array_mutator=lambda a: a.__setitem__("time_s", np.empty((0,), dtype="<f8")))
    with pytest.raises(AdapterError):
        load_bound_case(other, relative)


def test_only_finite_final_interval_may_be_fractional(tmp_path: Path) -> None:
    case = load_bound_case(tmp_path, write_case(tmp_path, horizon_s=0.0006))
    assert case.arrays["time_s"][-1] - case.arrays["time_s"][-2] == pytest.approx(0.0001)
    bad = tmp_path / "bad"
    relative = write_case(bad, outcome=OUTCOME_NO_REMOVAL, horizon_s=0.0005, array_mutator=lambda a: a["time_s"].__setitem__(-1, a["time_s"][-1] - 1e-5))
    with pytest.raises(AdapterError, match="FRACTIONAL_FINAL"):
        load_bound_case(bad, relative)


def test_nonfinal_fractional_stage_code0_and_wrong_order_rejected(tmp_path: Path) -> None:
    relative = write_case(tmp_path, array_mutator=lambda a: a["time_s"].__setitem__(1, a["time_s"][1] - 1e-5))
    with pytest.raises(AdapterError, match="ONLY_FINAL"):
        load_bound_case(tmp_path, relative)
    code0 = tmp_path / "code0"
    relative = write_case(code0, array_mutator=lambda a: a["stage_code"].__setitem__(0, 0))
    with pytest.raises(AdapterError, match="STAGE_CODE_SEQUENCE"):
        load_bound_case(code0, relative)
    wrong = tmp_path / "wrong"
    relative = write_case(wrong, array_mutator=lambda a: a["stage_code"].__setitem__(0, 2))
    with pytest.raises(AdapterError, match="STAGE_CODE_SEQUENCE"):
        load_bound_case(wrong, relative)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda a: a["acquisition_event_count"].__setitem__((), 0),
        lambda a: a["bilateral_removal_event_count"].__setitem__((), 0),
        lambda a: a["acquisition_event_sample_index"].__setitem__(0, -1),
        lambda a: a["bilateral_removal_active_sample_index"].__setitem__(0, 0),
        lambda a: a["saved_window_end_index"].__setitem__((), 0),
        lambda a: a["bilateral_removal_event_time_s"].__setitem__(0, 0.0),
    ],
)
def test_event_count_index_time_and_window_contradictions_rejected(tmp_path: Path, mutator) -> None:
    relative = write_case(tmp_path, array_mutator=mutator)
    with pytest.raises(AdapterError):
        load_bound_case(tmp_path, relative)


def test_sidecar_forged_values_and_extra_post_bool_rejected(tmp_path: Path) -> None:
    relative = write_case(tmp_path, sidecar_mutator=lambda s: s.__setitem__("acquisition_time_s", 9.0))
    with pytest.raises(AdapterError, match="FINITE_REMOVAL_TIME|ACQUISITION_INDEX_TIME"):
        load_bound_case(tmp_path, relative)
    other = tmp_path / "other"
    relative = write_case(other, sidecar_mutator=lambda s: s.__setitem__("post_release_passed", True))
    with pytest.raises(AdapterError, match="EXACT_SCHEMA"):
        load_bound_case(other, relative)


@pytest.mark.parametrize("forged", [False, 0])
def test_acquisition_time_requires_exact_finite_float(tmp_path: Path, forged) -> None:
    relative = write_case(tmp_path, sidecar_mutator=lambda sidecar: sidecar.__setitem__("acquisition_time_s", forged))
    with pytest.raises(AdapterError, match="ROLE_OR_ALPHA_INVALID"):
        load_bound_case(tmp_path, relative)


def test_hash_bytes_absolute_traversal_and_case_alias_rejected(tmp_path: Path) -> None:
    relative = write_case(tmp_path, sidecar_mutator=lambda s: s.__setitem__("npz_sha256", "A" * 64))
    with pytest.raises(AdapterError, match="SHA256_BINDING"):
        load_bound_case(tmp_path, relative)
    for index, path_value in enumerate(("C:/raw.npz", "../raw.npz", "evidence/cases/ALIAS.npz")):
        root = tmp_path / f"p{index}"
        relative = write_case(root, sidecar_mutator=lambda s, value=path_value: s.__setitem__("npz_relative_path", value))
        with pytest.raises(AdapterError):
            load_bound_case(root, relative)


def test_hardlink_alias_rejected_and_symlink_when_supported(tmp_path: Path) -> None:
    relative = write_case(tmp_path)
    npz = tmp_path / Path(relative).with_suffix(".npz")
    original = npz.with_name("original.npz")
    npz.replace(original)
    os.link(original, npz)
    with pytest.raises(AdapterError, match="SINGLE_LINK"):
        load_bound_case(tmp_path, relative)


def test_contract_profiles_have_explicit_units_shapes_and_no_null() -> None:
    assert set(PROFILE_DEFINITIONS) == {"FRESH_FINITE_REMOVAL_V1", "FRESH_NO_REMOVAL_V1", "COMMON_PROPAGATION_V1", "A0_BOOKEND_V1"}
    for profile in PROFILE_DEFINITIONS.values():
        for spec in profile["arrays"].values():
            assert spec["dtype"] in {"<f8", "<i8", "|b1"}
            assert isinstance(spec["shape"], list)
            assert isinstance(spec["unit"], str) and spec["unit"]
    assert "null" not in json.dumps(PROFILE_DEFINITIONS).lower()


def test_json_bool_cannot_impersonate_integer_schedule_index(tmp_path: Path) -> None:
    rows, order = schedule_records()
    row = next(item for item in rows if item["case_id"] == order[1])
    relative = write_case(
        tmp_path,
        case_id=row["case_id"],
        method=row["method"],
        step_s=row["step_s"],
        alpha=row["alpha"],
        command_duration_s=row["command_duration_s"],
        horizon_s=2.0 * row["step_s"],
        sidecar_mutator=lambda sidecar: sidecar.__setitem__("schedule_index", True),
    )
    with pytest.raises(AdapterError, match="IDENTITY_PATH_HASH_OR_CONTRACT"):
        load_bound_case(tmp_path, relative)
