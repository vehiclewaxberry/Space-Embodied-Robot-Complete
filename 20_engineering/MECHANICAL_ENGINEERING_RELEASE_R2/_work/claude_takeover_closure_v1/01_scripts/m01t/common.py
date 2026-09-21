"""Common helpers: paths, hashing, deterministic JSON."""
import hashlib
import json
import os

ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
REL = "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"
TK = f"{REL}/_work/claude_takeover_closure_v1"
ODR = f"{REL}/_work/odr"
M01_OUT = f"{TK}/03_m01"
WP_OUT = f"{TK}/03_work_packages"
RUN_ID = "R2_TERMINAL_CONVERGENCE_20260828_R1"


def abspath(rel):
    return os.path.join(ROOT, rel.replace("/", os.sep))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def sha256_rel(rel):
    return sha256_file(abspath(rel))


def jload(rel):
    with open(abspath(rel), "r", encoding="utf-8") as f:
        return json.load(f)


def jdump(obj, rel):
    ap = abspath(rel)
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, sort_keys=True)


def canonical_sha256(obj):
    payload = (json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def pin(rel):
    ap = abspath(rel)
    ok = os.path.isfile(ap)
    return {"path": rel, "exists": ok,
            "sha256": sha256_file(ap) if ok else None,
            "bytes": os.path.getsize(ap) if ok else None}
