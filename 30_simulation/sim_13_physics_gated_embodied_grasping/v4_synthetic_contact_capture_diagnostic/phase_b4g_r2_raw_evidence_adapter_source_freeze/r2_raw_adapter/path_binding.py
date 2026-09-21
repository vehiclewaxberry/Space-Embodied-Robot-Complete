"""Lexically exact, link-free, single-read project-relative file access."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Final


MAX_BOUND_FILE_BYTES: Final[int] = 256 * 1024 * 1024
REPARSE_POINT: Final[int] = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class PathBindingError(ValueError):
    pass


@dataclass(frozen=True)
class SingleReadFile:
    relative_path: str
    resolved_path: Path
    payload: bytes
    byte_count: int


def _has_reparse_point(path: Path) -> bool:
    value = os.lstat(path)
    attributes = getattr(value, "st_file_attributes", 0)
    return bool(attributes & REPARSE_POINT)


def validate_relative_path(value: object, *, suffix: str) -> str:
    if type(value) is not str or not value or "\\" in value or ":" in value or "\x00" in value:
        raise PathBindingError("PROJECT_RELATIVE_POSIX_PATH_REQUIRED")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or pure.suffix.lower() != suffix.lower()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.as_posix() != value
    ):
        raise PathBindingError("NONCANONICAL_OR_ESCAPING_RELATIVE_PATH")
    return value


def single_read_project_file(project_root: Path, relative_path: object, *, suffix: str) -> SingleReadFile:
    relative = validate_relative_path(relative_path, suffix=suffix)
    try:
        root = project_root.resolve(strict=True)
    except OSError as exc:
        raise PathBindingError("PROJECT_ROOT_MISSING") from exc
    if not root.is_dir() or root.is_symlink() or _has_reparse_point(root):
        raise PathBindingError("PROJECT_ROOT_REGULAR_DIRECTORY_REQUIRED")
    if not (root / "PROJECT_MAP.md").is_file():
        raise PathBindingError("PROJECT_ROOT_MARKER_MISSING")
    lexical = root.joinpath(*PurePosixPath(relative).parts)
    cursor = root
    for part in PurePosixPath(relative).parts:
        cursor = cursor / part
        try:
            value = os.lstat(cursor)
        except OSError as exc:
            raise PathBindingError("BOUND_PATH_COMPONENT_MISSING") from exc
        if stat.S_ISLNK(value.st_mode) or _has_reparse_point(cursor):
            raise PathBindingError("SYMLINK_OR_REPARSE_POINT_FORBIDDEN")
    try:
        resolved = lexical.resolve(strict=True)
        actual_relative = resolved.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise PathBindingError("BOUND_PATH_ESCAPES_PROJECT_ROOT") from exc
    if actual_relative != relative:
        raise PathBindingError("PATH_ALIAS_OR_CASE_ALIAS_FORBIDDEN")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(resolved, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise PathBindingError("REGULAR_SINGLE_LINK_FILE_REQUIRED")
        if before.st_size <= 0 or before.st_size > MAX_BOUND_FILE_BYTES:
            raise PathBindingError("BOUND_FILE_SIZE_OUT_OF_RANGE")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                raise PathBindingError("BOUND_FILE_TRUNCATED_DURING_SINGLE_READ")
            chunks.append(block)
            remaining -= len(block)
        if os.read(descriptor, 1) != b"":
            raise PathBindingError("BOUND_FILE_GREW_DURING_SINGLE_READ")
        after = os.fstat(descriptor)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if identity_before != identity_after:
            raise PathBindingError("BOUND_FILE_CHANGED_DURING_SINGLE_READ")
        payload = b"".join(chunks)
        if len(payload) != before.st_size:
            raise PathBindingError("BOUND_FILE_BYTE_COUNT_MISMATCH")
        return SingleReadFile(relative, resolved, payload, len(payload))
    except OSError as exc:
        raise PathBindingError("BOUND_FILE_OPEN_OR_READ_FAILED") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


__all__ = ["PathBindingError", "SingleReadFile", "single_read_project_file", "validate_relative_path"]
