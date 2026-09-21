#!/usr/bin/env python3
"""Fixed-boundary I/O primitives for the preauthorization readiness package.

All production writers in this package use :func:`write_fixed_json`.  The
writer has no caller-selected directory or filename capability.
"""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import os
import stat
import uuid
from pathlib import Path
from typing import Any, Iterator, Sequence


TOOL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOL_DIR.parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / "40_evidence/artifacts/authorization_readiness/unified_r2_v2"

FIXED_OUTPUT_NAMES = {
    "PREAUTHORIZATION_READINESS_CURRENT_V1.json",
    "PREAUTHORIZATION_READINESS_OWNER_ASSESSMENT_V1.json",
    "PREAUTHORIZATION_READINESS_VERIFICATION_V1.json",
    "PREAUTHORIZATION_READINESS_SELF_TEST_V1.json",
    "PREAUTHORIZATION_READINESS_VALIDATION_V1.json",
    "PREAUTHORIZATION_READINESS_INDEPENDENT_AUDIT_V1.json",
    "PREAUTHORIZATION_READINESS_PYTEST_V1.json",
    "PREAUTHORIZATION_READINESS_ACYCLIC_MANIFEST_V1.json",
    "PREAUTHORIZATION_READINESS_GATE_V1.json",
}

MAX_READ_BYTES = 1024 * 1024
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF


class SafeIOError(RuntimeError):
    """Fail-closed path, handle, identity, or persistence error."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def assert_no_reparse_components(path: Path, stop_at: Path | None = None) -> None:
    """Reject symlinks/reparse points in every existing lexical component."""

    absolute = path.absolute()
    stop = stop_at.absolute() if stop_at is not None else None
    current = absolute
    while True:
        if current.exists() or current.is_symlink():
            if _is_reparse(current):
                raise SafeIOError(f"REPARSE_OR_SYMLINK_COMPONENT_DENIED:{current}")
        if stop is not None and current == stop:
            break
        if current.parent == current:
            if stop is not None:
                raise SafeIOError("STOP_BOUNDARY_NOT_REACHED")
            break
        current = current.parent


def _normalized_windows_final_path(text: str) -> Path:
    value = text
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value)


if os.name == "nt":
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    GENERIC_READ = 0x80000000
    FILE_READ_ATTRIBUTES = 0x0080
    FILE_SHARE_READ = 0x00000001
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetFileAttributesW.restype = wintypes.DWORD


def _windows_open_handle(path: Path, *, directory: bool) -> Any:
    flags = FILE_FLAG_OPEN_REPARSE_POINT | (FILE_FLAG_BACKUP_SEMANTICS if directory else FILE_FLAG_SEQUENTIAL_SCAN)
    access = FILE_READ_ATTRIBUTES if directory else GENERIC_READ | FILE_READ_ATTRIBUTES
    handle = kernel32.CreateFileW(
        str(path),
        access,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        flags,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise SafeIOError(f"WINDOWS_SECURE_HANDLE_OPEN_FAILED:{ctypes.get_last_error()}:{path}")
    return handle


def _windows_handle_info(handle: Any) -> tuple[int, int, int, int, int, int]:
    record = BY_HANDLE_FILE_INFORMATION()
    if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(record)):
        raise SafeIOError(f"WINDOWS_HANDLE_INFO_FAILED:{ctypes.get_last_error()}")
    return (
        int(record.dwFileAttributes),
        int(record.dwVolumeSerialNumber),
        int(record.nFileIndexHigh),
        int(record.nFileIndexLow),
        int(record.nFileSizeHigh),
        int(record.nFileSizeLow),
    )


def _windows_final_path(handle: Any) -> Path:
    required = kernel32.GetFinalPathNameByHandleW(handle, None, 0, 0)
    if not required:
        raise SafeIOError(f"WINDOWS_FINAL_PATH_SIZE_FAILED:{ctypes.get_last_error()}")
    buffer = ctypes.create_unicode_buffer(required + 1)
    written = kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if not written or written >= len(buffer):
        raise SafeIOError(f"WINDOWS_FINAL_PATH_FAILED:{ctypes.get_last_error()}")
    return _normalized_windows_final_path(buffer.value).resolve(strict=True)


@contextlib.contextmanager
def _held_input_parent(path: Path, roots: Sequence[Path]) -> Iterator[dict[str, Any]]:
    """Hold and revalidate the input parent directory for the entire read.

    The file itself is still opened with no-follow semantics below.  This
    second handle closes the parent-directory rename/delete gap on Windows
    and records an independently stable parent identity on POSIX.
    """

    parent = path.absolute().parent
    assert_no_reparse_components(parent)
    allowed_real = [root.resolve(strict=True) for root in roots]

    if os.name == "nt":
        handle = _windows_open_handle(parent, directory=True)
        metadata: dict[str, Any] = {
            "parent_handle_method": "WINDOWS_CREATEFILE_DIRECTORY_NO_REPARSE_NO_SHARE_WRITE_DELETE",
            "parent_final_handle_path": None,
            "parent_directory_handle_stable": False,
        }
        try:
            before = _windows_handle_info(handle)
            if before[0] & FILE_ATTRIBUTE_REPARSE_POINT:
                raise SafeIOError("INPUT_PARENT_HANDLE_REPARSE_POINT_DENIED")
            final_parent = _windows_final_path(handle)
            if not any(_is_relative_to(final_parent, root) for root in allowed_real):
                raise SafeIOError("INPUT_PARENT_FINAL_HANDLE_PATH_OUTSIDE_FIXED_ROOT")
            metadata["parent_final_handle_path"] = str(final_parent)
            yield metadata
            after = _windows_handle_info(handle)
            final_after = _windows_final_path(handle)
            if before != after or final_after != final_parent:
                raise SafeIOError("INPUT_PARENT_HANDLE_IDENTITY_CHANGED_DURING_READ")
            metadata["parent_directory_handle_stable"] = True
        finally:
            kernel32.CloseHandle(handle)
        return

    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise SafeIOError("SECURE_INPUT_PARENT_HANDLE_CAPABILITY_UNAVAILABLE")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(parent, flags)
    metadata = {
        "parent_handle_method": "POSIX_O_DIRECTORY_O_NOFOLLOW_STABLE_FD",
        "parent_final_handle_path": None,
        "parent_directory_handle_stable": False,
    }
    try:
        before = os.fstat(fd)
        proc_link = Path(f"/proc/self/fd/{fd}")
        if not proc_link.exists():
            raise SafeIOError("POSIX_PARENT_FINAL_HANDLE_PATH_CAPABILITY_UNAVAILABLE")
        final_parent = proc_link.resolve(strict=True)
        if not any(_is_relative_to(final_parent, root) for root in allowed_real):
            raise SafeIOError("INPUT_PARENT_FINAL_HANDLE_PATH_OUTSIDE_FIXED_ROOT")
        metadata["parent_final_handle_path"] = str(final_parent)
        yield metadata
        after = os.fstat(fd)
        final_after = proc_link.resolve(strict=True)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino) or final_after != final_parent:
            raise SafeIOError("INPUT_PARENT_HANDLE_IDENTITY_CHANGED_DURING_READ")
        metadata["parent_directory_handle_stable"] = True
    finally:
        os.close(fd)


@contextlib.contextmanager
def _held_output_directory() -> Iterator[Path]:
    """Hold the exact evidence directory against rename/delete while writing."""

    if not EVIDENCE_ROOT.is_dir():
        raise SafeIOError("EVIDENCE_ROOT_MUST_PREEXIST")
    expected = (
        PROJECT_ROOT
        / "40_evidence/artifacts/authorization_readiness/unified_r2_v2"
    ).absolute()
    if EVIDENCE_ROOT.absolute() != expected:
        raise SafeIOError("EVIDENCE_ROOT_NOT_FIXED_EXPECTED_PATH")
    assert_no_reparse_components(EVIDENCE_ROOT)
    project_real = PROJECT_ROOT.resolve(strict=True)
    root_real = EVIDENCE_ROOT.resolve(strict=True)
    if not _is_relative_to(root_real, project_real) or root_real != expected.resolve(strict=True):
        raise SafeIOError("EVIDENCE_ROOT_REALPATH_OUTSIDE_PROJECT_OR_DRIFTED")

    if os.name == "nt":
        handle = _windows_open_handle(EVIDENCE_ROOT, directory=True)
        try:
            info = _windows_handle_info(handle)
            if info[0] & FILE_ATTRIBUTE_REPARSE_POINT:
                raise SafeIOError("EVIDENCE_ROOT_HANDLE_IS_REPARSE_POINT")
            if _windows_final_path(handle) != root_real:
                raise SafeIOError("EVIDENCE_ROOT_FINAL_HANDLE_PATH_DRIFT")
            yield root_real
            if _windows_handle_info(handle)[:4] != info[:4] or _windows_final_path(handle) != root_real:
                raise SafeIOError("EVIDENCE_ROOT_HANDLE_IDENTITY_CHANGED")
        finally:
            kernel32.CloseHandle(handle)
        return

    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise SafeIOError("SECURE_DIRECTORY_HANDLE_CAPABILITY_UNAVAILABLE")
    try:
        import fcntl
    except ImportError as exc:
        raise SafeIOError("DIRECTORY_LOCK_CAPABILITY_UNAVAILABLE") from exc
    fd = os.open(root_real, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        before = os.fstat(fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield root_real
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise SafeIOError("EVIDENCE_ROOT_DIRECTORY_IDENTITY_CHANGED")
        os.fsync(fd)
    finally:
        os.close(fd)


def _secure_read_windows(path: Path, roots: Sequence[Path], max_bytes: int) -> tuple[bytes, dict[str, Any]]:
    attributes = kernel32.GetFileAttributesW(str(path))
    if attributes == INVALID_FILE_ATTRIBUTES:
        raise SafeIOError(f"INPUT_ATTRIBUTES_UNAVAILABLE:{ctypes.get_last_error()}")
    if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
        raise SafeIOError("INPUT_REPARSE_POINT_DENIED")
    handle = _windows_open_handle(path, directory=False)
    fd: int | None = None
    try:
        before = _windows_handle_info(handle)
        if before[0] & FILE_ATTRIBUTE_REPARSE_POINT:
            raise SafeIOError("INPUT_HANDLE_REPARSE_POINT_DENIED")
        final_path = _windows_final_path(handle)
        allowed_real = [root.resolve(strict=True) for root in roots]
        if not any(_is_relative_to(final_path, root) for root in allowed_real):
            raise SafeIOError("INPUT_FINAL_HANDLE_PATH_OUTSIDE_FIXED_ROOT")
        import msvcrt

        # open_osfhandle transfers this exact no-follow handle to the CRT.  All
        # reads, fstat calls, Win32 identity checks, and final-path checks below
        # therefore operate on one and the same kernel file object.
        fd = msvcrt.open_osfhandle(int(handle), os.O_RDONLY | getattr(os, "O_BINARY", 0))
        live_handle = msvcrt.get_osfhandle(fd)
        fd_before = os.fstat(fd)
        chunks = []
        total = 0
        while True:
            block = os.read(fd, min(1024 * 1024, max_bytes + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            if total > max_bytes:
                raise SafeIOError("INPUT_EXCEEDS_MAX_BYTES")
        payload = b"".join(chunks)
        fd_after = os.fstat(fd)
        if (
            fd_before.st_dev,
            fd_before.st_ino,
            fd_before.st_size,
            fd_before.st_mtime_ns,
        ) != (
            fd_after.st_dev,
            fd_after.st_ino,
            fd_after.st_size,
            fd_after.st_mtime_ns,
        ):
            raise SafeIOError("INPUT_FSTAT_IDENTITY_CHANGED_DURING_READ")
        after = _windows_handle_info(live_handle)
        if before != after or _windows_final_path(live_handle) != final_path:
            raise SafeIOError("INPUT_HANDLE_IDENTITY_CHANGED_DURING_READ")
        return payload, {
            "method": "WINDOWS_SINGLE_CREATEFILE_HANDLE_NO_REPARSE_NO_SHARE_WRITE_DELETE",
            "final_handle_path": str(final_path),
            "handle_identity_stable": True,
            "bytes": len(payload),
        }
    finally:
        if fd is not None:
            os.close(fd)
        else:
            kernel32.CloseHandle(handle)


def _secure_read_posix(path: Path, roots: Sequence[Path], max_bytes: int) -> tuple[bytes, dict[str, Any]]:
    if not hasattr(os, "O_NOFOLLOW"):
        raise SafeIOError("POSIX_O_NOFOLLOW_UNAVAILABLE")
    lexical = path.absolute()
    allowed_real = [root.resolve(strict=True) for root in roots]
    if not any(_is_relative_to(lexical, root.absolute()) for root in roots):
        raise SafeIOError("INPUT_LEXICAL_PATH_OUTSIDE_FIXED_ROOT")
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(lexical, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise SafeIOError("INPUT_NOT_REGULAR_FILE")
        proc_link = Path(f"/proc/self/fd/{fd}")
        if not proc_link.exists():
            raise SafeIOError("POSIX_FINAL_HANDLE_PATH_CAPABILITY_UNAVAILABLE")
        final_path = proc_link.resolve(strict=True)
        if not any(_is_relative_to(final_path, root) for root in allowed_real):
            raise SafeIOError("INPUT_FINAL_HANDLE_PATH_OUTSIDE_FIXED_ROOT")
        chunks = []
        total = 0
        while True:
            block = os.read(fd, min(1024 * 1024, max_bytes + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            if total > max_bytes:
                raise SafeIOError("INPUT_EXCEEDS_MAX_BYTES")
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise SafeIOError("INPUT_FSTAT_IDENTITY_CHANGED_DURING_READ")
        if proc_link.resolve(strict=True) != final_path:
            raise SafeIOError("INPUT_FINAL_HANDLE_PATH_CHANGED_DURING_READ")
        payload = b"".join(chunks)
        return payload, {
            "method": "POSIX_O_NOFOLLOW_STABLE_FD",
            "final_handle_path": str(final_path),
            "handle_identity_stable": True,
            "bytes": len(payload),
        }
    finally:
        os.close(fd)


def secure_read_bytes(path: Path, *, allowed_roots: Sequence[Path], max_bytes: int = MAX_READ_BYTES) -> tuple[bytes, dict[str, Any]]:
    """Read one stable no-follow handle whose final path stays in fixed roots."""

    if not allowed_roots:
        raise SafeIOError("NO_FIXED_INPUT_ROOT")
    lexical = path.absolute()
    for root in allowed_roots:
        if not root.is_dir():
            raise SafeIOError(f"FIXED_INPUT_ROOT_MISSING:{root}")
        assert_no_reparse_components(root)
    if not any(_is_relative_to(lexical, root.absolute()) for root in allowed_roots):
        raise SafeIOError("INPUT_LEXICAL_PATH_OUTSIDE_FIXED_ROOT")
    assert_no_reparse_components(lexical)
    with _held_input_parent(lexical, allowed_roots) as parent_meta:
        if os.name == "nt":
            payload, metadata = _secure_read_windows(lexical, allowed_roots, max_bytes)
        else:
            payload, metadata = _secure_read_posix(lexical, allowed_roots, max_bytes)
    metadata.update(parent_meta)
    return payload, metadata


def write_fixed_json(filename: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist one allowlisted evidence JSON with exclusive temp and post-check."""

    if filename not in FIXED_OUTPUT_NAMES or Path(filename).name != filename:
        raise SafeIOError("OUTPUT_FILENAME_NOT_FIXED_ALLOWLISTED")
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    expected_sha = sha256_bytes(encoded)
    with _held_output_directory() as root_real:
        path = EVIDENCE_ROOT / filename
        if path.parent.resolve(strict=True) != root_real:
            raise SafeIOError("OUTPUT_PARENT_HANDLE_BOUNDARY_DRIFT")
        if path.exists() and _is_reparse(path):
            raise SafeIOError("OUTPUT_TARGET_REPARSE_POINT_DENIED")
        temporary = EVIDENCE_ROOT / f".{filename}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        if temporary.parent.resolve(strict=True) != root_real:
            raise SafeIOError("TEMP_OUTPUT_PARENT_BOUNDARY_DRIFT")
        try:
            with temporary.open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            if _is_reparse(temporary):
                raise SafeIOError("TEMP_OUTPUT_REPARSE_POINT_DENIED")
            os.replace(temporary, path)
            # A second stable handle verifies the bytes actually present after replace.
            observed, meta = secure_read_bytes(path, allowed_roots=[EVIDENCE_ROOT], max_bytes=len(encoded) + 1)
            if observed != encoded or sha256_bytes(observed) != expected_sha:
                raise SafeIOError("POST_WRITE_BYTE_OR_HASH_VERIFICATION_FAILED")
            if os.name != "nt":
                descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            return {
                "path": str(path),
                "bytes": len(encoded),
                "sha256": expected_sha,
                "post_write_handle": meta,
            }
        finally:
            if temporary.exists() and not _is_reparse(temporary):
                try:
                    temporary.unlink()
                except OSError:
                    pass
