"""Strict JSON decoding and canonical hashing primitives.

The standard decoder silently accepts duplicate object names by retaining the
last value.  Authority, interface and receipt records must instead reject
duplicates, non-finite numbers and unexpected fields before any value is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any


class StrictJSONError(ValueError):
    """Raised when a JSON byte record is ambiguous or outside its schema."""


MAX_JSON_BYTES = 262_144
MAX_JSON_DEPTH = 64
MAX_JSON_COMPLEXITY_UNITS = 8_192
MAX_JSON_NODES = 8_193
MAX_JSON_STRING_CHARS = 16_384
MAX_JSON_TOTAL_STRING_CHARS = 131_072
MAX_JSON_NUMBER_CHARS = 256
_MAX_ABS_INTEGER = 10**MAX_JSON_NUMBER_CHARS


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise StrictJSONError(f"DUPLICATE_KEY:{key}")
        output[key] = value
    return output


def _reject_constant(value: str) -> None:
    raise StrictJSONError(f"NON_FINITE_NUMBER:{value}")


def _parse_bounded_int(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > MAX_JSON_NUMBER_CHARS:
        raise StrictJSONError("INTEGER_DIGIT_LIMIT_EXCEEDED")
    try:
        return int(token)
    except ValueError as exc:
        raise StrictJSONError("INVALID_INTEGER_LITERAL") from exc


def _parse_bounded_float(token: str) -> float:
    if len(token) > MAX_JSON_NUMBER_CHARS:
        raise StrictJSONError("NUMBER_CHARACTER_LIMIT_EXCEEDED")
    try:
        value = float(token)
    except ValueError as exc:
        raise StrictJSONError("INVALID_FLOAT_LITERAL") from exc
    if not math.isfinite(value):
        raise StrictJSONError(f"NON_FINITE_NUMBER:{token}")
    return value


def _preflight_json_text(text: str) -> None:
    """Bound depth and lexical complexity before the recursive stdlib parser."""

    containers: list[str] = []
    complexity = 0
    in_string = False
    escaped = False
    string_chars = 0
    total_string_chars = 0
    for character in text:
        if in_string:
            if escaped:
                escaped = False
                string_chars += 1
                total_string_chars += 1
            elif character == "\\":
                escaped = True
                string_chars += 1
                total_string_chars += 1
            elif character == '"':
                in_string = False
            else:
                string_chars += 1
                total_string_chars += 1
            if string_chars > MAX_JSON_STRING_CHARS:
                raise StrictJSONError("JSON_STRING_CHARACTER_LIMIT_EXCEEDED")
            if total_string_chars > MAX_JSON_TOTAL_STRING_CHARS:
                raise StrictJSONError("JSON_TOTAL_STRING_CHARACTER_LIMIT_EXCEEDED")
            continue
        if character == '"':
            in_string = True
            escaped = False
            string_chars = 0
        elif character in "[{":
            containers.append(character)
            complexity += 1
            if len(containers) > MAX_JSON_DEPTH:
                raise StrictJSONError("JSON_DEPTH_LIMIT_EXCEEDED")
        elif character in "]}":
            if not containers:
                raise StrictJSONError("INVALID_JSON_STRUCTURE")
            opener = containers.pop()
            if (opener, character) not in (("[", "]"), ("{", "}")):
                raise StrictJSONError("INVALID_JSON_STRUCTURE")
        elif character in ",:":
            complexity += 1
        if complexity > MAX_JSON_COMPLEXITY_UNITS:
            raise StrictJSONError("JSON_COMPLEXITY_LIMIT_EXCEEDED")
    if in_string or containers:
        raise StrictJSONError("INVALID_JSON_STRUCTURE")


def loads_strict(payload: bytes | str) -> Any:
    """Decode one UTF-8 JSON record without duplicate-key or NaN tolerance."""

    if isinstance(payload, bytes):
        if len(payload) > MAX_JSON_BYTES:
            raise StrictJSONError("JSON_BYTE_LIMIT_EXCEEDED")
        if payload.startswith(b"\xef\xbb\xbf"):
            raise StrictJSONError("UTF8_BOM_NOT_ALLOWED")
        try:
            text = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise StrictJSONError("INVALID_UTF8") from exc
    elif isinstance(payload, str):
        if len(payload) > MAX_JSON_BYTES:
            raise StrictJSONError("JSON_BYTE_LIMIT_EXCEEDED")
        try:
            encoded_length = len(payload.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as exc:
            raise StrictJSONError("INVALID_UTF8") from exc
        if encoded_length > MAX_JSON_BYTES:
            raise StrictJSONError("JSON_BYTE_LIMIT_EXCEEDED")
        text = payload
    else:
        raise TypeError("payload must be bytes or str")
    _preflight_json_text(text)
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_constant,
            parse_int=_parse_bounded_int,
            parse_float=_parse_bounded_float,
        )
    except StrictJSONError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictJSONError(f"INVALID_JSON:{exc.msg}") from exc
    except RecursionError as exc:
        raise StrictJSONError("JSON_RECURSION_LIMIT_EXCEEDED") from exc
    except ValueError as exc:
        # This catch is deliberately scoped to the stdlib decode call.  It
        # normalizes interpreter numeric conversion limits without masking
        # MemoryError, KeyboardInterrupt, or unrelated program defects.
        raise StrictJSONError("JSON_VALUE_LIMIT_EXCEEDED") from exc
    # CPython's JSON decoder maps an overflowing finite-looking literal such as
    # ``1e999`` to ``inf`` without invoking ``parse_constant``.  Walk the parsed
    # tree before returning so every decoding entry point rejects that form too.
    _assert_canonical_domain(value)
    return value


def require_exact_keys(
    mapping: Mapping[str, Any], expected: Iterable[str], *, path: str
) -> None:
    if not isinstance(mapping, Mapping):
        raise StrictJSONError(f"NOT_OBJECT:{path}")
    expected_set = set(expected)
    actual_set = set(mapping)
    extra = sorted(actual_set - expected_set)
    missing = sorted(expected_set - actual_set)
    if extra or missing:
        raise StrictJSONError(
            f"KEY_SET_MISMATCH:{path}:extra={extra}:missing={missing}"
        )


def _assert_canonical_domain(value: Any, path: str = "$") -> None:
    """Iteratively enforce the JSON domain and aggregate complexity bounds."""

    stack: list[tuple[Any, str, int]] = [(value, path, 0)]
    nodes = 0
    total_string_chars = 0
    while stack:
        item, item_path, container_depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise StrictJSONError("JSON_NODE_LIMIT_EXCEEDED")
        if item is None or isinstance(item, bool):
            continue
        if isinstance(item, str):
            if len(item) > MAX_JSON_STRING_CHARS:
                raise StrictJSONError(f"JSON_STRING_CHARACTER_LIMIT_EXCEEDED:{item_path}")
            try:
                item.encode("utf-8", errors="strict")
            except UnicodeEncodeError as exc:
                raise StrictJSONError(f"INVALID_UTF8_STRING:{item_path}") from exc
            total_string_chars += len(item)
            if total_string_chars > MAX_JSON_TOTAL_STRING_CHARS:
                raise StrictJSONError("JSON_TOTAL_STRING_CHARACTER_LIMIT_EXCEEDED")
            continue
        if isinstance(item, int):
            if abs(item) >= _MAX_ABS_INTEGER:
                raise StrictJSONError(f"INTEGER_DIGIT_LIMIT_EXCEEDED:{item_path}")
            continue
        if isinstance(item, float):
            if not math.isfinite(item):
                raise StrictJSONError(f"NON_FINITE_NUMBER:{item_path}")
            continue
        if isinstance(item, list):
            next_depth = container_depth + 1
            if next_depth > MAX_JSON_DEPTH:
                raise StrictJSONError(f"JSON_DEPTH_LIMIT_EXCEEDED:{item_path}")
            for index in range(len(item) - 1, -1, -1):
                stack.append((item[index], f"{item_path}[{index}]", next_depth))
            continue
        if isinstance(item, Mapping):
            next_depth = container_depth + 1
            if next_depth > MAX_JSON_DEPTH:
                raise StrictJSONError(f"JSON_DEPTH_LIMIT_EXCEEDED:{item_path}")
            entries = list(item.items())
            for key, child in reversed(entries):
                if not isinstance(key, str):
                    raise StrictJSONError(f"NON_STRING_KEY:{item_path}")
                nodes += 1
                if nodes > MAX_JSON_NODES:
                    raise StrictJSONError("JSON_NODE_LIMIT_EXCEEDED")
                if len(key) > MAX_JSON_STRING_CHARS:
                    raise StrictJSONError(f"JSON_STRING_CHARACTER_LIMIT_EXCEEDED:{item_path}/<key>")
                try:
                    key.encode("utf-8", errors="strict")
                except UnicodeEncodeError as exc:
                    raise StrictJSONError(f"INVALID_UTF8_STRING:{item_path}/<key>") from exc
                total_string_chars += len(key)
                if total_string_chars > MAX_JSON_TOTAL_STRING_CHARS:
                    raise StrictJSONError("JSON_TOTAL_STRING_CHARACTER_LIMIT_EXCEEDED")
                stack.append((child, f"{item_path}/{key}", next_depth))
            continue
        raise StrictJSONError(f"UNSUPPORTED_CANONICAL_TYPE:{item_path}:{type(item).__name__}")


def validate_json_domain(value: Any, *, path: str = "$") -> None:
    """Validate an in-memory value against the same bounded JSON domain.

    Public APIs which receive Python objects (rather than serialized bytes)
    use this entry point before semantic validation.  The implementation is
    iterative, so hostile nesting cannot reach Python's recursion limit.
    """

    _assert_canonical_domain(value, path)


def canonical_json_bytes(value: Any) -> bytes:
    _assert_canonical_domain(value)
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except RecursionError as exc:
        raise StrictJSONError("JSON_RECURSION_LIMIT_EXCEEDED") from exc
    except UnicodeEncodeError as exc:
        raise StrictJSONError("INVALID_UTF8_STRING") from exc
    if len(payload) > MAX_JSON_BYTES:
        raise StrictJSONError("JSON_BYTE_LIMIT_EXCEEDED")
    return payload


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


def deep_freeze(value: Any) -> Any:
    """Recursively freeze a verified JSON-domain value against later mutation."""

    _assert_canonical_domain(value)
    if isinstance(value, Mapping):
        return MappingProxyType({key: deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(deep_freeze(item) for item in value)
    return value


__all__ = [
    "MAX_JSON_BYTES",
    "MAX_JSON_COMPLEXITY_UNITS",
    "MAX_JSON_DEPTH",
    "MAX_JSON_NODES",
    "MAX_JSON_NUMBER_CHARS",
    "MAX_JSON_STRING_CHARS",
    "MAX_JSON_TOTAL_STRING_CHARS",
    "StrictJSONError",
    "canonical_digest",
    "canonical_json_bytes",
    "deep_freeze",
    "loads_strict",
    "require_exact_keys",
    "validate_json_domain",
]
