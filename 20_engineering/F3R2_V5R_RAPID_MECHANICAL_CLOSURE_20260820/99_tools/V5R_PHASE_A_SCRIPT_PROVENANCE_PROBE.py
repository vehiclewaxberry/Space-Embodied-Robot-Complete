r"""Phase A probe - identify WHICH byte-exact script produced the last Loop1E 61836.

The failure receipt records the traceback (path + line numbers) but no script
SHA-256, so provenance cannot be read directly. Two independent lines of
evidence are combined here:

  1. Traceback line fingerprint. CPython reports the line number of the failing
     statement. If a candidate file has the reported statement at the reported
     line for ALL frames in the chain, that file is byte-compatible with the run.

  2. __pycache__ header. A .pyc embeds the source size and mtime it was compiled
     from (PEP 552 timestamp invalidation). This is independent of filename and
     of anything a human could have edited afterwards.

Prints a matrix; asserts nothing. Read-only.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import struct
import sys

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
V5 = os.path.join(ROOT, r"20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")

# frame chain from V5_LOOP1E_FAIL_20260813T154720.118687Z.json
EXPECTED_FRAMES = {
    3509: "build = build_top(sw, staging_path, audit[\"frame_contracts\"], local_arm, base, types, pythoncom)",
    3013: "motion_contract, suppressed_whitelist = build_motion_contract(model, components, local_arm, frame_audit, base, types, pythoncom)",
    2807: "\"expected_link6_to_gripper_transform_16\": relative_transform(link6, gripper, base, types, pythoncom),",
    2613: "inverse_raw = first_transform.IInverse()",
}

CANDIDATES = {
    "99_tools_canonical": {
        "src": os.path.join(V5, r"99_tools\F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py"),
        "pyc": os.path.join(V5, r"99_tools\__pycache__\F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.cpython-313.pyc"),
    },
    "root_stray": {
        "src": os.path.join(ROOT, "70_tools/legacy_f3r2_root_scripts/F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py"),
        "pyc": os.path.join(ROOT, r"__pycache__\F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.cpython-313.pyc"),
    },
}


def utc(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> int:
    for name, paths in CANDIDATES.items():
        src, pyc = paths["src"], paths["pyc"]
        print(f"=== {name}")
        if not os.path.exists(src):
            print("  src MISSING")
            continue

        st = os.stat(src)
        print(f"  src            : {src}")
        print(f"  src_sha256     : {sha256(src)}")
        print(f"  src_size       : {st.st_size}")
        print(f"  src_mtime_utc  : {utc(st.st_mtime)}")

        # evidence 1: traceback line fingerprint
        with open(src, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        hits, total = 0, len(EXPECTED_FRAMES)
        for lineno, expected in sorted(EXPECTED_FRAMES.items(), reverse=True):
            actual = lines[lineno - 1].strip() if lineno - 1 < len(lines) else "<past EOF>"
            ok = actual == expected.strip()
            hits += ok
            print(f"    line {lineno:>5}: {'MATCH  ' if ok else 'DIFFER '} {actual[:90]}")
        print(f"  frame_fingerprint: {hits}/{total}")

        # evidence 2: pyc header
        if os.path.exists(pyc):
            with open(pyc, "rb") as fh:
                _magic, _flags, mtime, size = struct.unpack("<4sIII", fh.read(16))
            print(f"  pyc            : {pyc}")
            print(f"  pyc_mtime_utc  : {utc(os.stat(pyc).st_mtime)}")
            print(f"  pyc_embeds_size: {size}   (src {st.st_size})  -> {'MATCH' if size == st.st_size else 'DIFFER'}")
            print(f"  pyc_embeds_mt  : {utc(mtime)}   -> {'MATCH' if mtime == int(st.st_mtime) else 'DIFFER'}")
        else:
            print("  pyc            : ABSENT")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
