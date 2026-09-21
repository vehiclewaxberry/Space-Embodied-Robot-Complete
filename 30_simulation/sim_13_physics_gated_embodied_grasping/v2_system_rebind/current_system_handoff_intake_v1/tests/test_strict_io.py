from __future__ import annotations

import pytest

from current_handoff.strict_io import (
    IntakeError,
    REQUIRED_ABSENT_PATHS_EXACT,
    load_default_snapshot,
    require_exact_keys,
    strict_json_bytes,
    validate_project_relative_path,
)


def test_default_snapshot_reads_all_sources_once():
    snapshot = load_default_snapshot()
    assert len(snapshot.artifacts) == 15
    assert all(artifact.read_count == 1 for artifact in snapshot.artifacts.values())


def test_default_snapshot_preserves_required_absences():
    snapshot = load_default_snapshot()
    assert snapshot.required_absent_paths == REQUIRED_ABSENT_PATHS_EXACT
    assert all(not snapshot.project_root.joinpath(*path.split("/")).exists() for path in snapshot.required_absent_paths)


def test_duplicate_json_key_rejected():
    with pytest.raises(IntakeError, match="duplicate") as caught:
        strict_json_bytes(b'{"a":1,"a":2}')
    assert caught.value.classification == "MALFORMED"


@pytest.mark.parametrize("token", [b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}', b'{"x":-1e999}'])
def test_nonfinite_json_rejected(token):
    with pytest.raises(IntakeError) as caught:
        strict_json_bytes(token)
    assert caught.value.classification == "MALFORMED"


def test_exact_key_guard_rejects_extra():
    with pytest.raises(IntakeError, match="extra"):
        require_exact_keys({"a": 1, "b": 2}, {"a"}, "fixture")


@pytest.mark.parametrize(
    "path",
    [
        "/absolute.json",
        "C:/absolute.json",
        "../traversal.json",
        "a//b.json",
        "a/./b.json",
        "a\\b.json",
        "Desktop/ghost.STL",
        "safe/NUL.json",
        "safe/control\x00.json",
        "safe/trailing. ",
    ],
)
def test_unsafe_paths_rejected(path):
    with pytest.raises(IntakeError) as caught:
        validate_project_relative_path(path)
    assert caught.value.classification == "MALFORMED"


def test_canonical_repository_path_accepted():
    result = validate_project_relative_path("20_engineering/example/source.json")
    assert result.as_posix() == "20_engineering/example/source.json"


def test_loaded_documents_are_deeply_immutable():
    parsed = load_default_snapshot().artifacts["e15_gate"].parsed
    with pytest.raises(TypeError):
        parsed["overall"] = "PASS"
