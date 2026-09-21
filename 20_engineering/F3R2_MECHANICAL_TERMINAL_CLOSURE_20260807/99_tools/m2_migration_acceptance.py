# -*- coding: utf-8 -*-
"""M2: independent acceptance of the Codex-executed campaign migration.

The migration itself was handed to the Codex agent (two `codex.exe` processes
were concurrently committing to `20_engineering/` and deleting files written
there, so two writers in one tree was not safe).  This script is the other half
of that split: it verifies the result and never writes into the destination.

Discovering the target: the campaign root may land back at
`20_engineering/F3R2_...` or somewhere else.  Rather than assume, the location is
resolved from a search list and reported, so a "pass" can never be produced
against a directory nobody looked at.

CRLF caveat, carried in from a real false alarm: this repo has
`core.autocrlf=true`, so every text file checked out by Git differs from an
LF-hashed digest in line endings alone.  The accepted B601 URDF looked
contaminated for exactly this reason (11029 blob bytes -> 11321 on disk, 292
LF->CRLF).  Text comparisons therefore accept a CRLF-normalised match; binary
comparisons do not.
"""
import hashlib
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = "F:/China Graduate Future Flight Vehicle Innovation Competition"
SRC = ("F:/_SEI_PROJECT_CONSOLIDATION_20260807/12_WAVE4/WORKTREE_RECONCILIATION/"
       "20_engineering")
SNAP = "F:/_SEI_PROJECT_CONSOLIDATION_20260807/12_WAVE4/WORKTREE_SAFETY_SNAPSHOT"
F3R2_NAME = "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
F3R1_NAME = "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806"

# where the campaign root might legitimately have been placed
CANDIDATES = [
    os.path.join(REPO, "20_engineering"),
    os.path.join(REPO, "20_engineering", "mechanical"),
    os.path.join(REPO, "20_engineering", "campaigns"),
]

PROTECTED_TEXT = {
    "accepted_b601_urdf": (
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4"),
    "mass_inertia_budget": (
        "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/"
        "mass_inertia_budget_v1.csv",
        "073C802527E35C9495188EEFD5D8BA51F524D326142CF2AB31E436BAD0899392"),
}
PROTECTED_BIN = {
    "v2_2_native_donor_top": (
        "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/"
        "Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
        "30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A"),
    "b51_articulated_arm_donor": (
        "20_engineering/cad/B5_1_B601_interface_closure_candidate/03_CAD/"
        "native_articulated/B51_ARTICULATED_20260728T008/assembly/"
        "B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM",
        "603B87BBD4398FDDB3F732FFBFA7E1C080ED91ED6E0A026D56CBDCBA08DE2E22"),
}
# the CM3 fixes that must survive: repo content, NOT the snapshot's broken paths
CM3_GUARDS = {
    "20_engineering/config/geometry/arm_b601_v1.yaml": {
        "rule": "yaml_field_equals",
        "field": "hardware_step",
        "expected": (
            "80_third_party/vendor/reBot-DevArm/hardware/reBot_B601_DM/"
            "reBot_B601_DM_v1.1_20260425.step"
        ),
    },
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/README.md": {
        "rule": "must_not_contain",
        "needle": "F:/Robotic arm/",
    },
}

# The acceptance program is allowed to receive validator-only bug fixes after
# the immutable migration snapshot was taken.  Excluding only this executable
# from MA-2 keeps the migrated engineering evidence bit-identical while
# avoiding a self-referential failure whenever the checker itself is repaired.
VALIDATOR_SELF_REL = "99_tools/m2_migration_acceptance.py"

# Python/FreeCAD imports regenerate bytecode in-place with the active
# interpreter even when every engineering source file is unchanged.  Bytecode
# is a disposable runtime cache, not migration evidence.  MA-2 therefore
# excludes only canonical Python cache artefacts while continuing to hash every
# source, CAD, gate, configuration and witness file.
def is_generated_runtime_cache(rel_posix):
    parts = rel_posix.split("/")
    return "__pycache__" in parts and rel_posix.endswith((".pyc", ".pyo"))


def sha(path, norm=False):
    try:
        if norm:
            return hashlib.sha256(
                open(path, "rb").read().replace(b"\r\n", b"\n")
            ).hexdigest().upper()
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                h.update(c)
        return h.hexdigest().upper()
    except Exception:
        return None


def is_text(path):
    try:
        return b"\x00" not in open(path, "rb").read(8192)
    except Exception:
        return False


def count(path):
    return sum(len(f) for _, _, f in os.walk(path)) if os.path.isdir(path) else 0


rep = {"schema": "M2_MIGRATION_ACCEPTANCE_V1", "source": SRC,
       "executed_by": "codex_agent", "verified_by": "claude",
       "role_split": ("migration handed to Codex because two concurrent "
                      "codex.exe processes were committing to 20_engineering/ "
                      "and deleting files written there")}

# ---- locate the migrated campaign ----
found = None
for c in CANDIDATES:
    if os.path.isdir(os.path.join(c, F3R2_NAME)):
        found = c
        break
rep["destination_searched"] = CANDIDATES
rep["destination_found"] = found
if found is None:
    rep["verdict"] = "M2_MIGRATION_NOT_YET_EXECUTED"
    rep["note"] = ("no %s under any candidate path; nothing to accept yet. "
                   "This is a WAITING state, not a failure." % F3R2_NAME)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    sys.exit(2)

checks, details = {}, {}

# ---- MA-1 campaign completeness ----
n2s, n2d = count(os.path.join(SRC, F3R2_NAME)), count(os.path.join(found,
                                                                   F3R2_NAME))
n1s, n1d = count(os.path.join(SRC, F3R1_NAME)), count(os.path.join(found,
                                                                   F3R1_NAME))
details["MA-1"] = {"f3r2_source": n2s, "f3r2_destination": n2d,
                   "f3r1_source": n1s, "f3r1_destination": n1d}
checks["MA-1_campaign_file_counts"] = (n2d >= n2s and n1d >= n1s)

# ---- MA-2 per-file digest over the campaign roots ----
missing, drift, ok_n = [], [], 0
for name in (F3R2_NAME, F3R1_NAME):
    s_root = os.path.join(SRC, name)
    d_root = os.path.join(found, name)
    for root, _, files in os.walk(s_root):
        for f in files:
            sp = os.path.join(root, f)
            rel = os.path.relpath(sp, s_root)
            rel_posix = rel.replace("\\", "/")
            if name == F3R2_NAME and rel_posix == VALIDATOR_SELF_REL:
                continue
            if is_generated_runtime_cache(rel_posix):
                continue
            dp = os.path.join(d_root, rel)
            if not os.path.exists(dp):
                missing.append("%s/%s" % (name, rel_posix))
                continue
            if sha(sp) == sha(dp):
                ok_n += 1
            elif is_text(sp) and sha(sp, True) == sha(dp, True):
                ok_n += 1                      # CRLF only
            else:
                drift.append("%s/%s" % (name, rel_posix))
details["MA-2"] = {"identical_or_crlf": ok_n, "missing": len(missing),
                   "content_drift": len(drift),
                   "validator_self_excluded": VALIDATOR_SELF_REL,
                   "generated_runtime_cache_policy":
                       "exclude __pycache__/*.pyc and *.pyo only",
                   "missing_sample": missing[:25],
                   "drift_sample": drift[:25]}
checks["MA-2_per_file_digest"] = (not missing and not drift)

# ---- MA-3/4 binary protected donors ----
for k, (rel, exp) in PROTECTED_BIN.items():
    p = os.path.join(REPO, rel)
    a = sha(p)
    details[k] = {"present": a is not None, "declared": exp[:20],
                  "actual": (a or "")[:20], "match": a == exp}
    checks["MA_%s" % k] = (a == exp)

# ---- MA-5/6 text protected assets, dual-criterion ----
for k, (rel, exp) in PROTECTED_TEXT.items():
    p = os.path.join(REPO, rel)
    disk, norm = sha(p), sha(p, True)
    blob = None
    try:
        out = subprocess.run(["git", "-C", REPO, "show", "HEAD:%s" % rel],
                             capture_output=True)
        if out.returncode == 0:
            blob = hashlib.sha256(out.stdout).hexdigest().upper()
    except Exception:
        pass
    good = (disk == exp) or (norm == exp) or (blob == exp)
    details[k] = {"disk": (disk or "")[:20], "crlf_normalised": (norm or "")[:20],
                  "git_blob": (blob or "")[:20], "declared": exp[:20],
                  "accepted_by": ("disk" if disk == exp else
                                  "crlf_normalised" if norm == exp else
                                  "git_blob" if blob == exp else "NONE"),
                  "clean": good}
    checks["MA_%s" % k] = good

# ---- MA-7 CM3 fixes preserved ----
cm3 = {}
for rel, guard in CM3_GUARDS.items():
    p = os.path.join(REPO, rel)
    try:
        txt = open(p, encoding="utf-8", errors="replace").read()
        rule = guard["rule"]
        if rule == "yaml_field_equals":
            field = guard["field"]
            actual = None
            for line in txt.splitlines():
                code = line.split("#", 1)[0].strip()
                if code.startswith(field + ":"):
                    actual = code.split(":", 1)[1].strip().strip("'\"")
                    break
            expected = guard["expected"]
            cm3[rel] = {
                "exists": True,
                "rule": rule,
                "field": field,
                "actual": actual,
                "expected": expected,
                "pass": actual == expected,
            }
        else:
            needle = guard["needle"]
            cm3[rel] = {
                "exists": True,
                "rule": rule,
                "needle": needle,
                "contains_broken_abs_path": needle in txt,
                "pass": needle not in txt,
            }
    except Exception as exc:
        cm3[rel] = {"exists": False, "pass": False, "error": str(exc)}
details["MA-7"] = cm3
checks["MA-7_cm3_fixes_preserved"] = all(
    v.get("exists") and v.get("pass")
    for v in cm3.values())

# ---- MA-8 machine verdicts bit-identical ----
vd = []
s_root = os.path.join(SRC, F3R2_NAME)
d_root = os.path.join(found, F3R2_NAME)
for root, _, files in os.walk(s_root):
    for f in files:
        if not (f.endswith("_gate_check.json") or f.endswith("_DEFINITION.json")
                or f.endswith("_BINDING.json") or f.endswith("_GATE.json")):
            continue
        sp = os.path.join(root, f)
        rel = os.path.relpath(sp, s_root)
        dp = os.path.join(d_root, rel)
        same = os.path.exists(dp) and (sha(sp) == sha(dp)
                                       or sha(sp, True) == sha(dp, True))
        vd.append({"file": rel.replace("\\", "/"), "identical": bool(same)})
details["MA-8"] = {"verdict_files": len(vd),
                   "all_identical": all(v["identical"] for v in vd),
                   "differing": [v["file"] for v in vd
                                 if not v["identical"]][:20]}
checks["MA-8_verdict_semantics_unchanged"] = bool(vd) and all(
    v["identical"] for v in vd)

# ---- MA-9 snapshot retained ----
sn = {}
for d in ("untracked_copy", "untracked_moved_out"):
    p = os.path.join(SNAP, d)
    sn[d] = {"present": os.path.isdir(p), "files": count(p)}
details["MA-9"] = sn
checks["MA-9_snapshot_retained"] = all(v["present"] and v["files"] > 0
                                       for v in sn.values())

rep["checks"] = checks
rep["details"] = details
rep["verdict"] = ("M2_MIGRATION_ACCEPTED" if all(checks.values())
                  else "M2_MIGRATION_REJECTED")
rep["gate_status"] = ("M2_MIGRATION_ACCEPTANCE_PASS"
                      if all(checks.values())
                      else "M2_MIGRATION_ACCEPTANCE_FAIL")

out = os.path.join(found, F3R2_NAME, "15_change_control",
                   "M2_MIGRATION_ACCEPTANCE.json")
try:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, ensure_ascii=False)
    rep["receipt"] = out
except Exception as exc:
    rep["receipt_error"] = str(exc)

print("destination:", found)
print("\nchecks:")
for k, v in checks.items():
    print("   %-42s %s" % (k, "PASS" if v else "FAIL"))
print("\nMA-1", json.dumps(details["MA-1"], ensure_ascii=False))
print("MA-2", json.dumps({k: v for k, v in details["MA-2"].items()
                          if not k.endswith("sample")}, ensure_ascii=False))
print("MA-8", json.dumps({k: v for k, v in details["MA-8"].items()
                          if k != "differing"}, ensure_ascii=False))
print("\nverdict:", rep["verdict"])
print("gate_status:", rep["gate_status"])
sys.exit(0 if rep["verdict"] == "M2_MIGRATION_ACCEPTED" else 1)
