#!/usr/bin/env python3
"""F3 terminal-baseline SHA-256 recheck. READ-ONLY: opens files with mode 'rb' only.

Reads 10_submission/F3_P5_TERMINAL_MANIFEST_SHA256.txt, recomputes every listed
digest against the on-disk file, and emits 00_authority/F3_TERMINAL_SHA256_RECHECK.json.
No file under the frozen tree is written, moved or touched.
"""
import hashlib
import json
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FROZEN = os.path.join(BASE, "F3_P5_structural_closure_candidate")
MANIFEST = os.path.join(FROZEN, "10_submission", "F3_P5_TERMINAL_MANIFEST_SHA256.txt")
OUT = os.path.join(
    BASE, "F3_MECHANICAL_TERMINAL_AUDIT_20260806", "00_authority",
    "F3_TERMINAL_SHA256_RECHECK.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    entries = []
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line:
                continue
            # format: "<64-hex>  <relative/path>"
            parts = line.split(None, 1)
            if len(parts) != 2 or len(parts[0]) != 64:
                entries.append({"line": lineno, "status": "MALFORMED_LINE", "raw": line})
                continue
            declared, rel = parts[0], parts[1].strip()
            abspath = os.path.join(FROZEN, rel)
            rec = {"line": lineno, "path": rel, "declared_sha256": declared}
            if not os.path.isfile(abspath):
                rec.update(status="MISSING", actual_sha256=None, size_bytes=None)
            else:
                actual = sha256(abspath)
                rec.update(
                    status="MATCH" if actual == declared else "MISMATCH",
                    actual_sha256=actual,
                    size_bytes=os.path.getsize(abspath),
                    mtime_utc=__import__("datetime").datetime.utcfromtimestamp(
                        os.path.getmtime(abspath)).isoformat() + "Z",
                )
            entries.append(rec)

    counts = {}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1

    declared_count = len(entries)
    result = {
        "schema": "F3_TERMINAL_SHA256_RECHECK_V1",
        "audit_id": "F3_MECHANICAL_TERMINAL_STATE_AUDIT_AND_HUMAN_VISUAL_REVIEW",
        "manifest": os.path.relpath(MANIFEST, BASE).replace("\\", "/"),
        "manifest_sha256": sha256(MANIFEST),
        "claimed_file_count": 46,
        "manifest_line_count": declared_count,
        "counts": counts,
        "drift_detected": counts.get("MISMATCH", 0) > 0 or counts.get("MISSING", 0) > 0,
        "entries": entries,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)

    print("manifest_lines = %d (claimed 46)" % declared_count)
    for k in sorted(counts):
        print("  %-14s %d" % (k, counts[k]))
    print("drift_detected = %s" % result["drift_detected"])
    print("written -> %s" % OUT)
    return 0 if not result["drift_detected"] else 1


if __name__ == "__main__":
    sys.exit(main())
