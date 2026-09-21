from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import pytest

from mechanical_admission.strict_io import (
    AdmissionError,
    strict_json_bytes,
    strict_yaml_bytes,
    validate_project_relative_path,
)


def test_all_sources_single_read_and_hash_bound(snapshot):
    assert len(snapshot.artifacts) == 27
    assert all(item.read_count == 1 for item in snapshot.artifacts.values())
    assert all(item.byte_count == len(item.payload) for item in snapshot.artifacts.values())
    assert all(len(item.sha256) == 64 and item.sha256 == item.sha256.upper() for item in snapshot.artifacts.values())


def test_nested_documents_are_recursively_immutable(snapshot):
    frame = snapshot.artifacts["frame_tree"].parsed
    assert isinstance(frame, MappingProxyType)
    with pytest.raises(TypeError):
        frame["status"] = "FORGED"
    with pytest.raises(TypeError):
        frame["frame_only_contract"]["links"][0] = "FORGED"


@pytest.mark.parametrize("path", ["C:/absolute.json", "../escape.json", "a/../b", "a\\b", "./a"])
def test_noncanonical_paths_rejected(path):
    with pytest.raises(AdmissionError):
        validate_project_relative_path(path)


def test_strict_parsers_reject_duplicate_keys_and_nonfinite():
    with pytest.raises(AdmissionError):
        strict_json_bytes(b'{"a":1,"a":2}')
    with pytest.raises(AdmissionError):
        strict_json_bytes(b'{"a":NaN}')
    with pytest.raises(AdmissionError):
        strict_yaml_bytes(b"a: 1\na: 2\n")
    with pytest.raises(AdmissionError):
        strict_yaml_bytes(b"a: .inf\n")


def test_required_runtime_artifacts_are_absent(snapshot):
    assert len(snapshot.required_absent_paths) == 2
    assert all(not (snapshot.project_root / Path(path)).exists() for path in snapshot.required_absent_paths)
