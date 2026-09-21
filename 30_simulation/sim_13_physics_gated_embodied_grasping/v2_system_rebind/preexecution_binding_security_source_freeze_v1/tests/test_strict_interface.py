from __future__ import annotations

import copy
import json

import pytest

from preexec_security.interface_contract import parse_interface_candidate, synthetic_interface_candidate
from preexec_security.strict_json import (
    MAX_JSON_BYTES,
    MAX_JSON_COMPLEXITY_UNITS,
    MAX_JSON_DEPTH,
    MAX_JSON_NUMBER_CHARS,
    MAX_JSON_STRING_CHARS,
    MAX_JSON_TOTAL_STRING_CHARS,
    StrictJSONError,
    canonical_json_bytes,
    loads_strict,
    validate_json_domain,
)


def _bytes(document: object) -> bytes:
    return json.dumps(document, separators=(",", ":"), allow_nan=False).encode("utf-8")


def test_strict_json_rejects_duplicate_nonfinite_and_bom() -> None:
    with pytest.raises(StrictJSONError, match="DUPLICATE_KEY"):
        loads_strict(b'{"x":1,"x":2}')
    with pytest.raises(StrictJSONError, match="NON_FINITE"):
        loads_strict(b'{"x":NaN}')
    with pytest.raises(StrictJSONError, match="NON_FINITE"):
        loads_strict(b'{"x":1e999}')
    with pytest.raises(StrictJSONError, match="BOM"):
        loads_strict(b"\xef\xbb\xbf{}")


def test_strict_json_byte_limit_has_an_exact_adjacent_boundary() -> None:
    exact = b"null" + b" " * (MAX_JSON_BYTES - 4)
    assert loads_strict(exact) is None
    with pytest.raises(StrictJSONError, match="JSON_BYTE_LIMIT_EXCEEDED"):
        loads_strict(exact + b" ")


@pytest.mark.parametrize(
    "payload",
    [
        b"[" * 1200 + b"0" + b"]" * 1200,
        b'{"x":' * 1200 + b"0" + b"}" * 1200,
    ],
)
def test_strict_json_rejects_1200_level_arrays_and_objects_before_decode(payload: bytes) -> None:
    with pytest.raises(StrictJSONError, match="JSON_DEPTH_LIMIT_EXCEEDED"):
        loads_strict(payload)


def test_strict_json_depth_limit_has_an_exact_adjacent_boundary() -> None:
    exact_array = b"[" * MAX_JSON_DEPTH + b"0" + b"]" * MAX_JSON_DEPTH
    exact_object = b'{"x":' * MAX_JSON_DEPTH + b"0" + b"}" * MAX_JSON_DEPTH
    assert loads_strict(exact_array) is not None
    assert loads_strict(exact_object) is not None
    with pytest.raises(StrictJSONError, match="JSON_DEPTH_LIMIT_EXCEEDED"):
        loads_strict(b"[" + exact_array + b"]")
    with pytest.raises(StrictJSONError, match="INVALID_JSON_STRUCTURE"):
        loads_strict(b"]" * 1200 + b"[" * 1200 + b"0" + b"]" * 1200)


def test_strict_json_integer_digit_limit_preempts_interpreter_digit_limit() -> None:
    assert loads_strict(("9" * MAX_JSON_NUMBER_CHARS).encode("ascii")) > 0
    with pytest.raises(StrictJSONError, match="INTEGER_DIGIT_LIMIT_EXCEEDED"):
        loads_strict(("9" * (MAX_JSON_NUMBER_CHARS + 1)).encode("ascii"))
    with pytest.raises(StrictJSONError, match="INTEGER_DIGIT_LIMIT_EXCEEDED"):
        loads_strict(b"9" * 5000)


def test_strict_json_string_and_aggregate_string_limits_are_adjacent() -> None:
    exact_string = ('"' + "a" * MAX_JSON_STRING_CHARS + '"').encode("ascii")
    assert len(loads_strict(exact_string)) == MAX_JSON_STRING_CHARS
    with pytest.raises(StrictJSONError, match="JSON_STRING_CHARACTER_LIMIT_EXCEEDED"):
        loads_strict(('"' + "a" * (MAX_JSON_STRING_CHARS + 1) + '"').encode("ascii"))

    exact_total = ("[" + ",".join('"' + "a" * MAX_JSON_STRING_CHARS + '"' for _ in range(MAX_JSON_TOTAL_STRING_CHARS // MAX_JSON_STRING_CHARS)) + "]").encode("ascii")
    assert sum(len(item) for item in loads_strict(exact_total)) == MAX_JSON_TOTAL_STRING_CHARS
    over_total = exact_total[:-1] + b',"b"]'
    with pytest.raises(StrictJSONError, match="JSON_TOTAL_STRING_CHARACTER_LIMIT_EXCEEDED"):
        loads_strict(over_total)


def test_strict_json_node_complexity_limit_is_adjacent() -> None:
    exact = b"[" + b",".join([b"0"] * MAX_JSON_COMPLEXITY_UNITS) + b"]"
    assert len(loads_strict(exact)) == MAX_JSON_COMPLEXITY_UNITS
    over = exact[:-1] + b",0]"
    with pytest.raises(StrictJSONError, match="JSON_COMPLEXITY_LIMIT_EXCEEDED"):
        loads_strict(over)
    validate_json_domain([0] * MAX_JSON_COMPLEXITY_UNITS)
    with pytest.raises(StrictJSONError, match="JSON_NODE_LIMIT_EXCEEDED"):
        validate_json_domain([0] * (MAX_JSON_COMPLEXITY_UNITS + 1))


def test_strict_json_rejects_invalid_utf8_as_a_stable_domain_error() -> None:
    with pytest.raises(StrictJSONError, match="INVALID_UTF8"):
        loads_strict(b'"\xff"')
    with pytest.raises(StrictJSONError, match="INVALID_UTF8"):
        loads_strict('"\ud800"')
    with pytest.raises(StrictJSONError, match="INVALID_UTF8_STRING"):
        loads_strict(b'"\\ud800"')
    with pytest.raises(StrictJSONError, match="INVALID_UTF8_STRING"):
        canonical_json_bytes({"value": "\ud800"})


def test_synthetic_interface_candidate_is_strict_and_recursively_immutable() -> None:
    candidate = synthetic_interface_candidate()
    parsed = parse_interface_candidate(_bytes(candidate))
    assert parsed["whole_system_contract"]["links"] == 19
    assert parsed["authority"]["consumer_load_authorized"] is False
    with pytest.raises(TypeError):
        parsed["authority"]["consumer_load_authorized"] = True
    with pytest.raises(TypeError):
        parsed["accepted_b601_subtree"]["exact_semantic_fields"][0] = "forged"


def test_interface_rejects_extra_field_and_schema_drift() -> None:
    candidate = synthetic_interface_candidate()
    candidate["caller_pass"] = True
    with pytest.raises(StrictJSONError, match="KEY_SET_MISMATCH"):
        parse_interface_candidate(_bytes(candidate))
    candidate = synthetic_interface_candidate()
    candidate["schema"] = "MECH_RL_INTERFACE_V1"
    with pytest.raises(StrictJSONError, match="SCHEMA_MISMATCH"):
        parse_interface_candidate(_bytes(candidate))


@pytest.mark.parametrize("bad_path", ["a//b", "a/./b", "a/../b", "/a/b", "C:/a/b", "a\\b", "a\x00b"])
def test_interface_rejects_raw_path_ambiguity(bad_path: str) -> None:
    candidate = synthetic_interface_candidate()
    candidate["artifacts"]["system_urdf"]["path"] = bad_path
    with pytest.raises(StrictJSONError):
        parse_interface_candidate(_bytes(candidate))


def test_interface_rejects_duplicate_artifact_path_and_hash() -> None:
    candidate = synthetic_interface_candidate()
    candidate["artifacts"]["system_frame_tree"]["path"] = candidate["artifacts"]["system_urdf"]["path"]
    with pytest.raises(StrictJSONError, match="DUPLICATE_ARTIFACT_PATH"):
        parse_interface_candidate(_bytes(candidate))
    candidate = synthetic_interface_candidate()
    candidate["artifacts"]["system_frame_tree"]["sha256"] = candidate["artifacts"]["system_urdf"]["sha256"]
    with pytest.raises(StrictJSONError, match="DUPLICATE_ARTIFACT_SHA256"):
        parse_interface_candidate(_bytes(candidate))
    candidate = synthetic_interface_candidate()
    candidate["artifacts"]["system_urdf"]["path"] = "synthetic_fixture/alternate.urdf"
    with pytest.raises(StrictJSONError, match="SYSTEM_URDF_FIXED_PATH_MISMATCH"):
        parse_interface_candidate(_bytes(candidate))


def test_interface_rejects_nested_extra_and_duplicate_key_bytes() -> None:
    candidate = synthetic_interface_candidate()
    candidate["authority"]["forged"] = True
    with pytest.raises(StrictJSONError, match="KEY_SET_MISMATCH"):
        parse_interface_candidate(_bytes(candidate))
    text = _bytes(synthetic_interface_candidate()).decode("utf-8")
    text = text.replace('"schema":"MECH_RL_SYSTEM_INTERFACE_V2"', '"schema":"MECH_RL_SYSTEM_INTERFACE_V2","schema":"FORGED"', 1)
    with pytest.raises(StrictJSONError, match="DUPLICATE_KEY"):
        parse_interface_candidate(text.encode("utf-8"))
