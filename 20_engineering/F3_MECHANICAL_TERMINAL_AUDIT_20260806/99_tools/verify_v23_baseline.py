#!/usr/bin/env python3
"""Verify the V2_3 CAD baseline freeze manifest against on-disk files. READ-ONLY.

baseline_freeze_manifest.yaml declares source_root = Space_Embodied_Robot_CAD_V2_2_NATIVE
but is stored inside .._V2_3_NATIVE_INTEGRATION. This script hashes both candidate roots
so the audit can say which root the frozen digests actually describe, rather than
assuming.
"""
import hashlib
import json
import os
import re

REPO = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
CADDIR = os.path.join(REPO, "20_engineering", "cad")
V23 = os.path.join(CADDIR, "Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION")
MANIFEST = os.path.join(V23, "baseline_freeze_manifest.yaml")
OUT = os.path.join(REPO, "20_engineering", "F3_MECHANICAL_TERMINAL_AUDIT_20260806",
                   "00_authority", "F3_V23_BASELINE_VERIFY.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def parse_manifest(path):
    """Minimal parse: 'rel/path:' then indented 'sha256:' / 'bytes:'."""
    head, files = {}, {}
    cur = None
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            m = re.match(r"^(\w+):\s*(.*)$", line)
            if m and m.group(1) != "files":
                head[m.group(1)] = m.group(2).strip()
                continue
            m = re.match(r"^  (\S.*?):\s*$", line)
            if m:
                cur = m.group(1)
                files[cur] = {}
                continue
            m = re.match(r"^    (sha256|bytes):\s*(\S+)\s*$", line)
            if m and cur:
                files[cur][m.group(1)] = m.group(2)
    return head, files


def check_root(root, files):
    res = {"root": root, "root_exists": os.path.isdir(root),
           "MATCH": 0, "MISMATCH": 0, "MISSING": 0, "mismatched": [], "missing": []}
    if not res["root_exists"]:
        res["MISSING"] = len(files)
        return res
    for rel, meta in files.items():
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            res["MISSING"] += 1
            if len(res["missing"]) < 15:
                res["missing"].append(rel)
            continue
        if sha256(p) == meta.get("sha256"):
            res["MATCH"] += 1
        else:
            res["MISMATCH"] += 1
            if len(res["mismatched"]) < 15:
                res["mismatched"].append(
                    {"path": rel, "declared": meta.get("sha256"), "actual": sha256(p),
                     "declared_bytes": meta.get("bytes"),
                     "actual_bytes": os.path.getsize(p)})
    return res


def main():
    head, files = parse_manifest(MANIFEST)
    src_root_name = head.get("source_root", "")
    alt = os.path.join(CADDIR, src_root_name) if src_root_name else None

    rep = {
        "schema": "F3_V23_BASELINE_VERIFY_V1",
        "manifest": MANIFEST,
        "manifest_sha256": sha256(MANIFEST),
        "declared": {
            "source_root": src_root_name,
            "canonical_top": head.get("canonical_top"),
            "canonical_top_sha256": head.get("canonical_top_sha256"),
            "file_count": head.get("file_count"),
            "unchanged_proof": head.get("unchanged_proof"),
            "generated_utc": head.get("generated_utc"),
        },
        "manifest_entries_parsed": len(files),
        "roots": {},
    }

    for tag, root in [("V2_3_NATIVE_INTEGRATION", V23),
                      ("declared_source_root", alt)]:
        if root is None:
            continue
        rep["roots"][tag] = check_root(root, files)

    # canonical top, in whichever roots exist
    ct = head.get("canonical_top", "")
    rep["canonical_top_check"] = {}
    for tag, root in [("V2_3_NATIVE_INTEGRATION", V23),
                      ("declared_source_root", alt)]:
        if root is None:
            continue
        p = os.path.join(root, ct.replace("/", os.sep))
        rep["canonical_top_check"][tag] = (
            {"exists": False, "path": p} if not os.path.isfile(p) else
            {"exists": True, "path": p, "actual_sha256": sha256(p),
             "declared_sha256": head.get("canonical_top_sha256"),
             "match": sha256(p) == head.get("canonical_top_sha256"),
             "bytes": os.path.getsize(p)})

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, ensure_ascii=False)

    print("declared source_root = %r" % src_root_name)
    print("declared file_count  = %s ; parsed entries = %d"
          % (head.get("file_count"), len(files)))
    print("declared unchanged_proof = %s" % head.get("unchanged_proof"))
    for tag, r in rep["roots"].items():
        print("\n[%s] exists=%s" % (tag, r["root_exists"]))
        print("   MATCH=%d MISMATCH=%d MISSING=%d"
              % (r["MATCH"], r["MISMATCH"], r["MISSING"]))
        for m in r["mismatched"][:5]:
            print("     MISMATCH %s" % m["path"])
        for m in r["missing"][:5]:
            print("     MISSING  %s" % m)
    print("\ncanonical_top:")
    for tag, c in rep["canonical_top_check"].items():
        print("   [%s] %s" % (tag, c))
    print("\nwritten -> %s" % OUT)


if __name__ == "__main__":
    main()
