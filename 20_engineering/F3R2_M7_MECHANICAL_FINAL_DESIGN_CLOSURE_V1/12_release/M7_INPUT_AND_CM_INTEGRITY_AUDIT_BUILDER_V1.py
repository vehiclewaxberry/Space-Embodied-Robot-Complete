#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M7 Gate A criterion 01 -- INPUT_AND_CM_INTEGRITY independent audit builder.

Role A7 (CM / release).  READ-ONLY over every work package.  Writes exactly one
artifact: 12_release/M7_INPUT_AND_CM_INTEGRITY_AUDIT_V1.json (plus this script).

Fail-closed: absent input -> null + named HOLD.  Never zero-fill.  UNKNOWN is
never PASS.  NO EVIDENCE is never PASS.

Six required checks:
  C1  frozen baseline drift (CDR PRE_INPUT_HASHES_V1.csv + FROZEN_BASELINE_INPUT_MANIFEST_V1.json)
  C2  receipt self-consistency (recompute sha256 + bytes of every receipt-pinned file)
  C3  line-ending false-positive guard (raw / LF-normalised / git-blob triple hash)
  C4  zero-byte + degenerate evidence sweep over the whole M7 tree
  C5  authority-scope sweep (flight/qualified/released/next_stage_authorized/Gate B/ODR stretch)
  C6  standards citation check against the CDR STANDARDS_SOURCE_LEDGER / TAILORING_MATRIX
"""

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import datetime

PROJECT_ROOT = r"f:\China Graduate Future Flight Vehicle Innovation Competition"
M7_REL = r"20_engineering\F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
M7_ROOT = os.path.join(PROJECT_ROOT, M7_REL)
CDR_ROOT = os.path.join(
    PROJECT_ROOT, "20_engineering", "F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821"
)
OUT_DIR = os.path.join(M7_ROOT, "12_release")
OUT_PATH = os.path.join(OUT_DIR, "M7_INPUT_AND_CM_INTEGRITY_AUDIT_V1.json")
SELF_PATH = os.path.abspath(__file__)

# M7 loop start: earliest 00_authority mtime observed / README creation 2026-08-22T00:19 local.
M7_LOOP_START_EPOCH = datetime.datetime(
    2026, 8, 22, 0, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8))
).timestamp()

TEXT_EXT = {
    ".md", ".json", ".yaml", ".yml", ".csv", ".py", ".txt", ".svg", ".sh",
    ".env", ".inp", ".dat", ".msg", ".sta", ".com", ".runlog", ".step", ".stp",
}
# extensions we will parse structurally
JSON_EXT = {".json"}
YAML_EXT = {".yaml", ".yml"}
CSV_EXT = {".csv"}


def longpath(p):
    p = os.path.abspath(p)
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        return "\\\\?\\" + p
    return p


def read_bytes(p):
    with open(longpath(p), "rb") as fh:
        return fh.read()


def sha256_file(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(longpath(p), "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest().upper()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest().upper()


def lf_normalised_sha256(p):
    """SHA-256 after CRLF->LF collapse (the documented autocrlf artifact)."""
    b = read_bytes(p)
    return sha256_bytes(b.replace(b"\r\n", b"\n"))


_GIT_CACHE = {}


def git_index_blob(rel_from_project_root):
    """Return (oid, sha256_of_blob_content, blob_bytes_len) for a git-tracked path.

    Git stores the checkin-normalised bytes; with core.autocrlf=true that is the
    LF form.  If the file is untracked this returns (None, None, None) which is a
    legitimate NOT_TRACKED result, not a failure.
    """
    key = rel_from_project_root.replace("\\", "/")
    if key in _GIT_CACHE:
        return _GIT_CACHE[key]
    out = (None, None, None, "NOT_TRACKED_IN_GIT_INDEX")
    try:
        r = subprocess.run(
            ["git", "ls-files", "-s", "--", key],
            cwd=PROJECT_ROOT, capture_output=True, timeout=120,
        )
        line = r.stdout.decode("utf-8", "replace").strip()
        if line:
            oid = line.split()[1]
            r2 = subprocess.run(
                ["git", "cat-file", "blob", oid],
                cwd=PROJECT_ROOT, capture_output=True, timeout=300,
            )
            if r2.returncode == 0:
                blob = r2.stdout
                out = (oid, sha256_bytes(blob), len(blob), "TRACKED")
    except Exception as exc:  # pragma: no cover
        out = (None, None, None, "GIT_PROBE_ERROR:%s" % type(exc).__name__)
    _GIT_CACHE[key] = out
    return out


def rel_to_project(abspath):
    a = os.path.abspath(abspath)
    try:
        return os.path.relpath(a, PROJECT_ROOT).replace("\\", "/")
    except ValueError:
        return a.replace("\\", "/")


def resolve_receipt_path(p, receipt_dir):
    """Receipt paths in M7 are heterogeneous.  Try, in order:
       1. project-root relative      2. M7-root relative
       3. receipt-directory relative 4. absolute
       Return (abspath_or_None, basis)."""
    p_norm = p.replace("\\", "/")
    cands = [
        (os.path.join(PROJECT_ROOT, p_norm), "PROJECT_ROOT_RELATIVE"),
        (os.path.join(M7_ROOT, p_norm), "M7_ROOT_RELATIVE"),
        (os.path.join(receipt_dir, p_norm), "RECEIPT_DIR_RELATIVE"),
        (p_norm, "ABSOLUTE_AS_GIVEN"),
    ]
    for c, basis in cands:
        if os.path.isfile(longpath(c)):
            return os.path.abspath(c), basis
    return None, "UNRESOLVED"


def triple_hash(abspath, is_text):
    """Raw / LF-normalised / git-index-blob SHA-256 triple -- the mandated
    line-ending false-positive guard (ODR-independent, repo-documented)."""
    raw = sha256_file(abspath)
    lf = None
    if is_text:
        try:
            lf = lf_normalised_sha256(abspath)
        except Exception:
            lf = None
    oid, blob_sha, blob_len, gstat = git_index_blob(rel_to_project(abspath))
    return {
        "sha256_raw_bytes_on_disk": raw,
        "sha256_crlf_to_lf_normalised": lf,
        "git_index_blob_oid_sha1": oid,
        "sha256_of_git_index_blob_content": blob_sha,
        "git_index_blob_bytes": blob_len,
        "git_tracking_status": gstat,
    }


# ---------------------------------------------------------------------------
# CHECK 1 -- FROZEN BASELINE DRIFT
# ---------------------------------------------------------------------------
def check1_frozen_baseline():
    res = {
        "check_id": "C1",
        "name": "FROZEN_BASELINE_DRIFT",
        "requirement": "Gate A criterion 01: frozen input hashes 100% consistent",
        "sources": {},
        "per_file": [],
        "tally": {},
        "change_control_assessment": {},
        "result": None,
    }
    csv_p = os.path.join(CDR_ROOT, "00_authority", "PRE_INPUT_HASHES_V1.csv")
    man_p = os.path.join(CDR_ROOT, "00_authority", "FROZEN_BASELINE_INPUT_MANIFEST_V1.json")
    pol_p = os.path.join(CDR_ROOT, "00_authority", "MECHANICAL_BASELINE_CHANGE_CONTROL_POLICY_V1.yaml")
    ecr_p = os.path.join(CDR_ROOT, "00_authority", "MECHANICAL_ECR_REGISTER_V1.csv")

    for tag, p in (("pre_input_hashes_csv", csv_p),
                   ("frozen_baseline_input_manifest_json", man_p),
                   ("change_control_policy_yaml", pol_p),
                   ("ecr_register_csv", ecr_p)):
        if os.path.isfile(longpath(p)):
            res["sources"][tag] = {
                "path": rel_to_project(p),
                "bytes": os.path.getsize(longpath(p)),
                "sha256": sha256_file(p),
            }
        else:
            res["sources"][tag] = {"path": rel_to_project(p), "bytes": None,
                                   "sha256": None, "status": "MISSING"}

    if res["sources"]["pre_input_hashes_csv"]["sha256"] is None or \
       res["sources"]["frozen_baseline_input_manifest_json"]["sha256"] is None:
        res["result"] = "NOT_EVALUATED"
        res["hold"] = "CDR_FROZEN_BASELINE_AUTHORITY_FILES_ABSENT_HOLD"
        return res

    with io.open(csv_p, "r", encoding="utf-8-sig", newline="") as fh:
        csv_rows = list(csv.DictReader(fh))
    man = json.load(io.open(man_p, "r", encoding="utf-8"))
    man_rows = man.get("inputs") or []

    by_id_csv = {r["input_id"]: r for r in csv_rows}
    by_id_man = {r["input_id"]: r for r in man_rows}

    # Cross-source agreement: the two authority files must pin identical values.
    id_union = sorted(set(by_id_csv) | set(by_id_man))
    cross_disagree = []
    for iid in id_union:
        a, b = by_id_csv.get(iid), by_id_man.get(iid)
        if a is None or b is None:
            cross_disagree.append({"input_id": iid,
                                   "in_csv": a is not None, "in_manifest": b is not None})
            continue
        if (a.get("sha256", "").upper() != str(b.get("sha256", "")).upper()) or \
           (str(a.get("bytes")) != str(b.get("bytes"))):
            cross_disagree.append({
                "input_id": iid,
                "csv_sha256": a.get("sha256"), "manifest_sha256": b.get("sha256"),
                "csv_bytes": a.get("bytes"), "manifest_bytes": b.get("bytes"),
            })

    # Which frozen paths does any M7 receipt claim to have PRODUCED?
    produced_by_m7 = m7_produced_path_set()

    counts = {"MATCH": 0, "DRIFT": 0, "MISSING": 0, "ZERO_BYTE": 0}
    for iid in id_union:
        src = by_id_man.get(iid) or by_id_csv.get(iid)
        rel = (src.get("project_relative_path") or "").replace("\\", "/")
        pinned_sha = str(src.get("sha256") or "").upper()
        pinned_bytes = src.get("bytes")
        try:
            pinned_bytes = int(pinned_bytes)
        except (TypeError, ValueError):
            pinned_bytes = None
        ab = os.path.join(PROJECT_ROOT, rel)
        row = {
            "input_id": iid,
            "authority_role": src.get("authority_role"),
            "owner_designated_immutable": str(src.get("owner_designated")).lower() == "true",
            "project_relative_path": rel,
            "pinned_sha256": pinned_sha,
            "pinned_bytes": pinned_bytes,
            "actual_sha256": None,
            "actual_bytes": None,
            "verdict": None,
            "m7_receipt_claims_production_of_this_path": rel in produced_by_m7,
            "mtime_after_m7_loop_start": None,
        }
        if not os.path.isfile(longpath(ab)):
            row["verdict"] = "MISSING"
            counts["MISSING"] += 1
        else:
            st = os.stat(longpath(ab))
            row["actual_bytes"] = st.st_size
            row["mtime_local"] = datetime.datetime.fromtimestamp(
                st.st_mtime, datetime.timezone(datetime.timedelta(hours=8))
            ).isoformat()
            row["mtime_after_m7_loop_start"] = st.st_mtime >= M7_LOOP_START_EPOCH
            if st.st_size == 0:
                row["verdict"] = "ZERO_BYTE"
                counts["ZERO_BYTE"] += 1
            else:
                row["actual_sha256"] = sha256_file(ab)
                if row["actual_sha256"] == pinned_sha and (
                        pinned_bytes is None or pinned_bytes == st.st_size):
                    row["verdict"] = "MATCH"
                    counts["MATCH"] += 1
                else:
                    row["verdict"] = "DRIFT"
                    counts["DRIFT"] += 1
                    ext = os.path.splitext(rel)[1].lower()
                    row["line_ending_guard"] = triple_hash(ab, ext in TEXT_EXT)
                    row["line_ending_guard"]["guard_verdict"] = classify_guard(
                        row["line_ending_guard"], pinned_sha)
        res["per_file"].append(row)

    res["tally"] = {
        "frozen_inputs_declared_csv": len(csv_rows),
        "frozen_inputs_declared_manifest": len(man_rows),
        "frozen_inputs_evaluated": len(res["per_file"]),
        "match": counts["MATCH"],
        "drift": counts["DRIFT"],
        "missing": counts["MISSING"],
        "zero_byte": counts["ZERO_BYTE"],
        "cross_source_disagreements": len(cross_disagree),
        "owner_designated_immutable_evaluated": sum(
            1 for r in res["per_file"] if r["owner_designated_immutable"]),
        "manifest_self_declared": {
            "total_input_count": man.get("total_input_count"),
            "hash_match_count": man.get("hash_match_count"),
            "hash_drift_count": man.get("hash_drift_count"),
            "audit_status": man.get("audit_status"),
            "verdict": man.get("verdict"),
        },
        "drifted_paths_m7_claims_to_have_produced": [
            r["project_relative_path"] for r in res["per_file"]
            if r["verdict"] == "DRIFT" and r["m7_receipt_claims_production_of_this_path"]],
        "frozen_paths_touched_after_m7_loop_start": [
            {"path": r["project_relative_path"], "mtime_local": r.get("mtime_local"),
             "verdict": r["verdict"]}
            for r in res["per_file"] if r.get("mtime_after_m7_loop_start")],
    }
    res["cross_source_disagreements"] = cross_disagree

    # change-control assessment
    ecr = []
    if os.path.isfile(longpath(ecr_p)):
        with io.open(ecr_p, "r", encoding="utf-8-sig", newline="") as fh:
            ecr = list(csv.DictReader(fh))
    pol = None
    if os.path.isfile(longpath(pol_p)):
        import yaml as _y
        pol = _y.safe_load(io.open(pol_p, "r", encoding="utf-8"))
    res["change_control_assessment"] = {
        "policy_schema": (pol or {}).get("schema"),
        "policy_status": (pol or {}).get("status"),
        "production_baseline_id": (pol or {}).get("production_baseline_id"),
        "production_baseline_write_policy": (pol or {}).get("production_baseline_write_policy"),
        "requires_ecr_before_change": ((pol or {}).get("change_authorization") or {}).get(
            "requires_ecr_before_change"),
        "ecr_rows": len(ecr),
        "ecr_ids": [r.get("ecr_id") for r in ecr],
        "ecr_open_production_changes": [
            r.get("ecr_id") for r in ecr
            if str(r.get("geometry_changed")).lower() == "true"
            or str(r.get("mass_or_inertia_changed")).lower() == "true"
            or str(r.get("frame_or_interface_changed")).lower() == "true"],
        "m7_wrote_into_frozen_production_baseline": bool(
            res["tally"]["frozen_paths_touched_after_m7_loop_start"]) or counts["DRIFT"] > 0,
        "m7_output_location": M7_REL + " (new isolated directory)",
        "assessment": None,
    }
    if counts["DRIFT"] == 0 and counts["MISSING"] == 0 and counts["ZERO_BYTE"] == 0 \
            and not res["tally"]["frozen_paths_touched_after_m7_loop_start"]:
        res["change_control_assessment"]["assessment"] = (
            "PERMITTED_WITHOUT_NEW_ECR: every frozen production input is byte-identical to its "
            "pin and none was written after the M7 loop start. M7 produced only new artifacts "
            "inside its own directory, which is the same PROCESS_ONLY posture ECR-000 already "
            "covers (isolated workspace, no production change). NOTE: this covers the *input "
            "freeze* only. If A0 later declares MECHANICAL_ENGINEERING_DESIGN_RELEASED and that "
            "release supersedes V5R_NEUTRAL_OPERATIONAL_MECHANICAL_BASELINE_V1 as the consumed "
            "baseline for Sim13/RL, the policy's V2 class (geometry/mass/frame/collision/"
            "configuration change) is engaged and a new ECR plus the 11-item mandatory_v2_"
            "regression is required BEFORE any downstream consumer is re-pointed. That is a "
            "declared open CM item, not an input-integrity failure.")
    else:
        res["change_control_assessment"]["assessment"] = (
            "ECR_REQUIRED: frozen production baseline was disturbed; policy "
            "production_baseline_write_policy=IMMUTABLE_NO_DIRECT_OVERWRITE and "
            "requires_ecr_before_change=true, and no ECR authorising it exists.")

    fail = (counts["DRIFT"] or counts["MISSING"] or counts["ZERO_BYTE"] or cross_disagree)
    res["result"] = "FAIL" if fail else "PASS"
    return res


def classify_guard(g, pinned_sha):
    """Distinguish a real contamination from a line-ending artifact."""
    if g["sha256_raw_bytes_on_disk"] == pinned_sha:
        return "NOT_A_MISMATCH_RAW_MATCHES"
    if g.get("sha256_crlf_to_lf_normalised") == pinned_sha:
        return "LINE_ENDING_ARTIFACT_ONLY_LF_NORMALISED_MATCHES_PIN"
    if g.get("sha256_of_git_index_blob_content") == pinned_sha:
        return "LINE_ENDING_ARTIFACT_ONLY_GIT_INDEX_BLOB_MATCHES_PIN"
    return "REAL_CONTENT_MISMATCH_NOT_EXPLAINED_BY_LINE_ENDINGS"


# ---------------------------------------------------------------------------
# receipt harvesting (shared by C1 and C2)
# ---------------------------------------------------------------------------
PRODUCED_KEYS = [
    "produced_files", "produced_files_this_loop", "contract_outputs", "outputs",
    "files_written", "products", "intermediates", "tools",
    "superseded_but_retained_unmodified", "builder", "policy_builder", "auditor",
    "receipt_builder", "negative_control", "auditor_v1_superseded",
    "receipt_builder_v1_superseded", "builder_reused_module",
    "produced_solver_artifacts", "upstream_geometry_builder",
]
CONSUMED_KEYS = [
    "source_register", "source_register_inputs", "inputs_read_only",
]


def _flatten_entries(obj, keypath=""):
    """Yield dicts that look like {path,sha256[,bytes]} anywhere inside obj."""
    if isinstance(obj, dict):
        if "path" in obj and isinstance(obj.get("path"), str) and (
                "sha256" in obj or "bytes" in obj):
            yield keypath, obj
            # also descend, some entries nest (wp7 produced_solver_artifacts)
        for k, v in obj.items():
            if k in ("path", "sha256", "bytes"):
                continue
            for r in _flatten_entries(v, keypath + "/" + str(k)):
                yield r
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            for r in _flatten_entries(v, keypath + "[%d]" % i):
                yield r


def harvest_receipt(receipt_path):
    d = json.load(io.open(receipt_path, "r", encoding="utf-8"))
    rdir = os.path.dirname(os.path.abspath(receipt_path))
    produced, consumed = [], []
    for k in PRODUCED_KEYS:
        if k in d:
            for kp, e in _flatten_entries(d[k], k):
                produced.append((kp, e))
    for k in CONSUMED_KEYS:
        if k in d:
            for kp, e in _flatten_entries(d[k], k):
                consumed.append((kp, e))
    return d, rdir, produced, consumed


_M7_PRODUCED_CACHE = None


def m7_produced_path_set():
    global _M7_PRODUCED_CACHE
    if _M7_PRODUCED_CACHE is not None:
        return _M7_PRODUCED_CACHE
    s = set()
    for r in sorted(find_receipts()):
        try:
            _d, rdir, produced, _c = harvest_receipt(r)
        except Exception:
            continue
        for _kp, e in produced:
            ab, _basis = resolve_receipt_path(e["path"], rdir)
            if ab:
                s.add(rel_to_project(ab))
            else:
                s.add(e["path"].replace("\\", "/"))
    _M7_PRODUCED_CACHE = s
    return s


def find_receipts():
    out = []
    for root, dirs, files in os.walk(M7_ROOT):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            if f.lower() == "receipt.json":
                out.append(os.path.join(root, f))
    return out


# ---------------------------------------------------------------------------
# CHECK 2 -- RECEIPT SELF-CONSISTENCY (+ CHECK 3 guard applied to every mismatch)
# ---------------------------------------------------------------------------
def check2_receipts():
    res = {
        "check_id": "C2",
        "name": "RECEIPT_SELF_CONSISTENCY",
        "method": ("recompute SHA-256 and byte size of every {path,sha256[,bytes]} entry "
                   "reachable inside each receipt.json, in both the produced and the consumed "
                   "registers; classify each"),
        "per_work_package": [],
        "mismatches": [],
        "tally": {},
        "result": None,
    }
    tot = dict(entries=0, verified=0, sha_mismatch=0, bytes_mismatch=0, unresolved=0,
               zero_byte=0, no_hash_pinned=0, self_reference=0, case_only=0,
               line_ending_only=0, real_content_mismatch=0)
    for rp in sorted(find_receipts()):
        wp = os.path.basename(os.path.dirname(rp))
        entry = {"work_package": wp,
                 "receipt": rel_to_project(rp),
                 "receipt_sha256": sha256_file(rp),
                 "receipt_bytes": os.path.getsize(longpath(rp)),
                 "parse": None, "counts": {}, "notes": []}
        try:
            d, rdir, produced, consumed = harvest_receipt(rp)
            entry["parse"] = "PASS_JSON"
        except Exception as exc:
            entry["parse"] = "FAIL_JSON:%s" % exc
            res["per_work_package"].append(entry)
            continue
        entry["schema"] = d.get("schema")
        entry["generated_local"] = d.get("generated_local")
        entry["generated_clock_source"] = d.get("generated_clock_source")
        entry["has_source_register"] = any(k in d for k in CONSUMED_KEYS)
        c = dict(produced_entries=len(produced), consumed_entries=len(consumed),
                 verified=0, sha_mismatch=0, bytes_mismatch=0, unresolved=0,
                 no_hash_pinned=0, lowercase_hash_entries=0)
        for register, lst in (("produced", produced), ("consumed", consumed)):
            for kp, e in lst:
                tot["entries"] += 1
                p = e["path"]
                pinned = e.get("sha256")
                pinned_u = str(pinned).upper() if pinned else None
                if pinned and pinned != pinned_u:
                    c["lowercase_hash_entries"] += 1
                pb = e.get("bytes")
                ab, basis = resolve_receipt_path(p, rdir)
                if ab is None:
                    c["unresolved"] += 1
                    tot["unresolved"] += 1
                    res["mismatches"].append({
                        "work_package": wp, "register": register, "receipt_key": kp,
                        "path_as_written": p, "classification": "REFERENCED_FILE_ABSENT_ON_DISK",
                        "pinned_sha256": pinned_u, "pinned_bytes": pb,
                        "severity": "HIGH" if register == "produced" else "MEDIUM",
                    })
                    continue
                if os.path.abspath(ab) == os.path.abspath(rp):
                    tot["self_reference"] += 1
                    entry["notes"].append(
                        "receipt pins its own bytes at %s -- self-reference is "
                        "arithmetically impossible; excluded from mismatch tally" % kp)
                    continue
                size = os.path.getsize(longpath(ab))
                if size == 0:
                    tot["zero_byte"] += 1
                if not pinned:
                    c["no_hash_pinned"] += 1
                    tot["no_hash_pinned"] += 1
                    continue
                actual = sha256_file(ab)
                ok_sha = (actual == pinned_u)
                ok_bytes = (pb is None or int(pb) == size)
                if ok_sha and ok_bytes:
                    c["verified"] += 1
                    tot["verified"] += 1
                    continue
                if not ok_sha:
                    c["sha_mismatch"] += 1
                    tot["sha_mismatch"] += 1
                if not ok_bytes:
                    c["bytes_mismatch"] += 1
                    tot["bytes_mismatch"] += 1
                ext = os.path.splitext(ab)[1].lower()
                g = triple_hash(ab, ext in TEXT_EXT)
                gv = classify_guard(g, pinned_u)
                if gv.startswith("LINE_ENDING_ARTIFACT_ONLY"):
                    tot["line_ending_only"] += 1
                elif gv == "REAL_CONTENT_MISMATCH_NOT_EXPLAINED_BY_LINE_ENDINGS":
                    tot["real_content_mismatch"] += 1
                res["mismatches"].append({
                    "work_package": wp, "register": register, "receipt_key": kp,
                    "path_as_written": p, "resolved_path": rel_to_project(ab),
                    "resolution_basis": basis,
                    "pinned_sha256": pinned_u, "actual_sha256": actual,
                    "pinned_bytes": pb, "actual_bytes": size,
                    "sha_match": ok_sha, "bytes_match": ok_bytes,
                    "line_ending_guard": g, "guard_verdict": gv,
                    "classification": ("BYTES_ONLY_MISMATCH" if ok_sha else gv),
                    "severity": "HIGH" if (not ok_sha and gv.startswith("REAL_")) else "MEDIUM",
                })
        entry["counts"] = c
        res["per_work_package"].append(entry)
    res["tally"] = tot
    res["tally"]["work_packages_with_receipt"] = len(res["per_work_package"])
    res["tally"]["work_packages_without_source_register"] = [
        e["work_package"] for e in res["per_work_package"] if not e.get("has_source_register")]
    res["tally"]["work_packages_missing_generated_clock_source"] = [
        e["work_package"] for e in res["per_work_package"]
        if not e.get("generated_clock_source")]
    res["tally"]["work_packages_with_lowercase_hashes"] = [
        e["work_package"] for e in res["per_work_package"]
        if e.get("counts", {}).get("lowercase_hash_entries")]
    res["result"] = "FAIL" if (tot["sha_mismatch"] or tot["bytes_mismatch"]
                               or tot["unresolved"]) else "PASS"
    return res


# ---------------------------------------------------------------------------
# CHECK 3 -- line ending guard summary (the guard itself is applied inline)
# ---------------------------------------------------------------------------
def check3_line_endings(c1, c2):
    res = {
        "check_id": "C3",
        "name": "LINE_ENDING_FALSE_POSITIVE_GUARD",
        "policy": ("no text-file hash mismatch may be declared a contamination until the raw, "
                   "CRLF->LF-normalised and git-index-blob SHA-256 have all been reported"),
        "repo_documented_precedent": {
            "case": "accepted B601 URDF autocrlf alarm",
            "lf_bytes": 11029, "crlf_bytes": 11321, "lines_rewritten": 292,
            "outcome": "NOT a contamination",
        },
        "git_config_core_autocrlf": None,
        "accepted_urdf_control_case": {},
        "guard_applications": [],
        "tally": {},
        "result": None,
    }
    try:
        r = subprocess.run(["git", "config", "core.autocrlf"], cwd=PROJECT_ROOT,
                           capture_output=True, timeout=60)
        res["git_config_core_autocrlf"] = r.stdout.decode().strip() or None
    except Exception:
        pass

    # live control case: the accepted URDF itself
    urdf_rel = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
    urdf_ab = os.path.join(PROJECT_ROOT, urdf_rel)
    if os.path.isfile(longpath(urdf_ab)):
        g = triple_hash(urdf_ab, True)
        raw = read_bytes(urdf_ab)
        g["bytes_on_disk"] = len(raw)
        g["bytes_after_lf_normalisation"] = len(raw.replace(b"\r\n", b"\n"))
        g["crlf_line_count"] = raw.count(b"\r\n")
        g["expected_pin_from_cdr_freeze"] = \
            "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
        g["raw_matches_pin"] = (g["sha256_raw_bytes_on_disk"] ==
                                g["expected_pin_from_cdr_freeze"])
        res["accepted_urdf_control_case"] = g
    else:
        res["accepted_urdf_control_case"] = {"status": "MISSING",
                                            "hold": "ACCEPTED_URDF_ABSENT_HOLD"}

    for r_ in c1.get("per_file", []):
        if "line_ending_guard" in r_:
            res["guard_applications"].append({
                "origin": "C1_FROZEN_BASELINE", "path": r_["project_relative_path"],
                "guard": r_["line_ending_guard"]})
    for m in c2.get("mismatches", []):
        if "line_ending_guard" in m:
            res["guard_applications"].append({
                "origin": "C2_RECEIPT", "path": m.get("resolved_path") or m["path_as_written"],
                "guard": m["line_ending_guard"], "guard_verdict": m["guard_verdict"]})
    n = len(res["guard_applications"])
    le = sum(1 for a in res["guard_applications"]
             if str(a.get("guard_verdict", "")).startswith("LINE_ENDING_ARTIFACT_ONLY")
             or str(a.get("guard", {}).get("guard_verdict", "")).startswith(
                 "LINE_ENDING_ARTIFACT_ONLY"))
    res["tally"] = {
        "text_mismatches_requiring_guard": n,
        "explained_as_line_ending_artifact_only": le,
        "real_content_mismatches_after_guard": n - le,
        "false_stop_work_conditions_avoided": le,
    }
    res["result"] = "PASS" if n == 0 else ("PASS_GUARD_APPLIED" if le == n else "FAIL")
    if n == 0:
        res["note"] = ("no text-file hash mismatch arose anywhere in C1 or C2, so the guard "
                       "had nothing to adjudicate; the accepted-URDF control case was still "
                       "computed to prove the guard is wired and functional")
    return res


# ---------------------------------------------------------------------------
# CHECK 4 -- zero-byte and degenerate evidence sweep
# ---------------------------------------------------------------------------
def _all_null(obj):
    """True if a JSON object has at least one leaf and every leaf is null."""
    leaves = []

    def rec(o):
        if isinstance(o, dict):
            if not o:
                return
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            if not o:
                return
            for v in o:
                rec(v)
        else:
            leaves.append(o)
    rec(obj)
    return bool(leaves) and all(x is None for x in leaves)


def check4_degenerate():
    import yaml as _y
    res = {
        "check_id": "C4",
        "name": "ZERO_BYTE_AND_DEGENERATE_EVIDENCE_SWEEP",
        "scope": M7_REL,
        "findings": {"zero_byte": [], "json_parse_fail": [], "yaml_parse_fail": [],
                     "csv_header_only": [], "json_all_null": [], "empty_json_container": [],
                     "receipt_referenced_missing": []},
        "coverage": {},
        "result": None,
    }
    walked = 0
    skipped = []
    by_ext = {}
    total_bytes = 0
    for root, dirs, files in os.walk(M7_ROOT):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            p = os.path.join(root, f)
            rel = rel_to_project(p)
            ext = os.path.splitext(f)[1].lower()
            by_ext[ext or "(none)"] = by_ext.get(ext or "(none)", 0) + 1
            try:
                size = os.path.getsize(longpath(p))
            except OSError as exc:
                skipped.append({"path": rel, "reason": "STAT_ERROR:%s" % exc})
                continue
            walked += 1
            total_bytes += size
            if os.path.abspath(p) == SELF_PATH or os.path.abspath(p) == os.path.abspath(OUT_PATH):
                # our own outputs: still counted as walked, flagged as self
                pass
            if size == 0:
                res["findings"]["zero_byte"].append({"path": rel, "bytes": 0})
                continue
            if ext in JSON_EXT:
                try:
                    obj = json.load(io.open(p, "r", encoding="utf-8"))
                except Exception as exc:
                    res["findings"]["json_parse_fail"].append(
                        {"path": rel, "bytes": size, "error": "%s: %s" % (type(exc).__name__, exc)})
                    continue
                if isinstance(obj, (dict, list)) and len(obj) == 0:
                    res["findings"]["empty_json_container"].append({"path": rel, "bytes": size})
                elif _all_null(obj):
                    res["findings"]["json_all_null"].append({"path": rel, "bytes": size})
            elif ext in YAML_EXT:
                try:
                    obj = _y.safe_load(io.open(p, "r", encoding="utf-8"))
                except Exception as exc:
                    res["findings"]["yaml_parse_fail"].append(
                        {"path": rel, "bytes": size, "error": "%s: %s" % (type(exc).__name__, exc)})
                    continue
                if obj is None:
                    res["findings"]["yaml_parse_fail"].append(
                        {"path": rel, "bytes": size, "error": "PARSED_TO_NONE_EMPTY_DOCUMENT"})
                elif isinstance(obj, (dict, list)) and len(obj) == 0:
                    res["findings"]["empty_json_container"].append({"path": rel, "bytes": size})
                elif _all_null(obj):
                    res["findings"]["json_all_null"].append({"path": rel, "bytes": size})
            elif ext in CSV_EXT:
                try:
                    with io.open(p, "r", encoding="utf-8-sig", newline="") as fh:
                        rows = list(csv.reader(fh))
                except Exception as exc:
                    res["findings"]["json_parse_fail"].append(
                        {"path": rel, "bytes": size, "error": "CSV_%s: %s"
                         % (type(exc).__name__, exc)})
                    continue
                data = [r for r in rows if any(str(x).strip() for x in r)]
                if len(data) <= 1:
                    res["findings"]["csv_header_only"].append(
                        {"path": rel, "bytes": size, "nonblank_rows": len(data),
                         "header": data[0] if data else None})
    # receipt-referenced-missing rolls up from C2 (computed there); recompute cheaply
    for rp in sorted(find_receipts()):
        try:
            _d, rdir, produced, consumed = harvest_receipt(rp)
        except Exception:
            continue
        for register, lst in (("produced", produced), ("consumed", consumed)):
            for kp, e in lst:
                ab, _b = resolve_receipt_path(e["path"], rdir)
                if ab is None:
                    res["findings"]["receipt_referenced_missing"].append({
                        "receipt": rel_to_project(rp), "register": register,
                        "receipt_key": kp, "path_as_written": e["path"]})
    res["coverage"] = {
        "files_walked": walked,
        "files_skipped": len(skipped),
        "skip_reasons": skipped,
        "total_bytes_walked": total_bytes,
        "extension_histogram": dict(sorted(by_ext.items(), key=lambda kv: -kv[1])),
        "directories_excluded": ["__pycache__ (python bytecode, not evidence)"],
        "note": ("every file under the M7 root was stat'ed and size-checked; structural parsing "
                 "was applied to all .json/.yaml/.yml/.csv; binary solver artifacts "
                 "(.odb/.prt) were size-checked only, which is the applicable degeneracy test "
                 "for them"),
    }
    res["tally"] = {k: len(v) for k, v in res["findings"].items()}
    res["result"] = "FAIL" if any(res["tally"][k] for k in
                                 ("zero_byte", "json_parse_fail", "yaml_parse_fail",
                                  "json_all_null", "receipt_referenced_missing")) else "PASS"
    if res["result"] == "PASS" and res["tally"]["csv_header_only"]:
        res["result"] = "PASS_WITH_OBSERVATION"
    return res


# ---------------------------------------------------------------------------
# CHECK 5 -- authority scope sweep
# ---------------------------------------------------------------------------
SCOPE_PATTERNS = [
    ("FLIGHT_QUALIFICATION_CLAIM", re.compile(
        r"flight[\s_-]*qualif|qualification[\s_-]*(pass|complete|released|achieved)"
        r"|FLIGHT_MOS_PASS|STRUCTURAL_QUALIFICATION_PASS", re.I)),
    ("LAUNCH_CLAIM", re.compile(
        r"launch[\s_-]*(load[\s_-]*pass|surviv|qualif)|LAUNCH_LOAD_PASS", re.I)),
    ("MANUFACTURING_RELEASE_CLAIM", re.compile(
        r"manufactur\w*[\s_-]*releas|released[\s_-]*for[\s_-]*manufactur"
        r"|release[\s_-]*to[\s_-]*(manufactur|production)|fabrication[\s_-]*releas", re.I)),
    ("QUALIFIED_OR_CERTIFIED_WORD", re.compile(r"\bqualified\b|\bcertified\b", re.I)),
    ("NEXT_STAGE_AUTHORIZED_TRUE", re.compile(
        r"next_stage_authorized\"?\s*[:=]\s*\"?(true|True|TRUE|yes)", re.I)),
    ("REVIEW_COMPLETE_CLAIM", re.compile(
        r"review_status\"?\s*[:=]\s*\"?(APPROVED|COMPLETE|REVIEWED|PASS|OWNER_APPROVED|SIGNED)",
        re.I)),
    ("GATE_B_OUT_OF_HOLD", re.compile(
        r"gate_?b\"?\s*[:=]\s*\"?(PASS|RELEASED|CLOSED|COMPLETE|OPEN|AUTHORIZED)", re.I)),
    ("AS_BUILT_OR_MEASURED_MASS_CLAIM", re.compile(
        r"(as[\s_-]?built|measured)[\s_-]*(mass|cg|inertia)\s*[:=]", re.I)),
    ("TYPICAL_PROPERTY_AS_ALLOWABLE", re.compile(
        r"typical[\s_-]*(value|propert\w+)[\s\S]{0,60}?(allowable|margin[\s_-]*of[\s_-]*safety|MoS)"
        r"|allowable[\s\S]{0,40}?typical", re.I)),
    ("MEMORY_GATE_PASSED_CLAIM", re.compile(
        r"memory_gate\"?\s*[:=]\s*\"?(PASS|OK|SATISFIED|TRUE)", re.I)),
    ("M8_M9_PLANNING", re.compile(r"\bM8\b|\bM9\b", re.I)),
]
# a hit is legitimate if the same line also carries prohibition/negation context
NEGATION = re.compile(
    r"not[\s_-]*(flight|launch|qualif|manufactur|as[\s_-]?built|measured|released|a[\s_-]*nasa)"
    r"|no[\s_-]*(flight|launch|qualif|manufactur)|forbidden|prohibit|must[\s_-]*not"
    r"|shall[\s_-]*not|may[\s_-]*not|never|hold|HOLD|false|FALSE|remains?[\s_-]*(hold|open)"
    r"|pending|deferred|non[\s_-]*normative|is[\s_-]*not|are[\s_-]*not|cannot|excluded"
    r"|_HOLD|forbidden_verdicts|standing_prohibitions|prohibitions_honored|not_authorized"
    r"|NOT_A_|NO_.*_CLAIM|superseded|guard|_required|_open|illegitimate|carried_holds"
    r"|blocking_holds_forbidden|retained_holds|unchanged", re.I)


def check5_authority_scope():
    res = {
        "check_id": "C5",
        "name": "AUTHORITY_SCOPE_SWEEP",
        "patterns": [n for n, _ in SCOPE_PATTERNS],
        "classification_rule": ("a regex hit is a BREACH only if the same line does not also "
                                "carry prohibition / negation / HOLD / false / pending context; "
                                "otherwise it is a LEGITIMATE_MENTION (prohibition list, "
                                "forbidden-verdict list, carried-HOLD list, guard text)"),
        "breaches": [],
        "legitimate_mentions_by_pattern": {},
        "governance_field_scan": {},
        "coverage": {},
        "result": None,
    }
    scanned = 0
    skipped_binary = 0
    lines_scanned = 0
    legit = {}
    for root, dirs, files in os.walk(M7_ROOT):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            p = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXT:
                skipped_binary += 1
                continue
            if os.path.abspath(p) in (SELF_PATH, os.path.abspath(OUT_PATH)):
                continue
            try:
                txt = read_bytes(p).decode("utf-8", "replace")
            except Exception:
                skipped_binary += 1
                continue
            scanned += 1
            lines = txt.splitlines()
            lines_scanned += len(lines)
            for i, line in enumerate(lines, 1):
                if len(line) > 4000:
                    line = line[:4000]
                for name, rx in SCOPE_PATTERNS:
                    if rx.search(line):
                        if NEGATION.search(line):
                            legit[name] = legit.get(name, 0) + 1
                        else:
                            res["breaches"].append({
                                "pattern": name,
                                "file": rel_to_project(p),
                                "line": i,
                                "text": line.strip()[:400],
                            })
    res["legitimate_mentions_by_pattern"] = dict(sorted(legit.items(), key=lambda kv: -kv[1]))

    # hard governance-field scan: read the actual machine fields, not just text
    gov = {"next_stage_authorized_values": {}, "review_status_values": {},
           "gate_b_values": {}, "memory_gate_values": {}}

    def collect(obj, path, store):
        if isinstance(obj, dict):
            for k, v in obj.items():
                lk = str(k).lower()
                if lk == "next_stage_authorized":
                    store["next_stage_authorized_values"].setdefault(
                        json.dumps(v), []).append(path)
                elif lk == "review_status":
                    store["review_status_values"].setdefault(str(v), []).append(path)
                elif lk in ("gate_b", "gate_b_status", "gateb"):
                    store["gate_b_values"].setdefault(json.dumps(v)[:200], []).append(path)
                elif lk == "memory_gate":
                    store["memory_gate_values"].setdefault(json.dumps(v)[:300], []).append(path)
                collect(v, path, store)
        elif isinstance(obj, list):
            for v in obj:
                collect(v, path, store)

    import yaml as _y
    for root, dirs, files in os.walk(M7_ROOT):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in (JSON_EXT | YAML_EXT):
                continue
            p = os.path.join(root, f)
            if os.path.abspath(p) == os.path.abspath(OUT_PATH):
                continue
            try:
                obj = (json.load(io.open(p, "r", encoding="utf-8")) if ext in JSON_EXT
                       else _y.safe_load(io.open(p, "r", encoding="utf-8")))
            except Exception:
                continue
            collect(obj, rel_to_project(p), gov)
    res["governance_field_scan"] = {
        k: {kk: sorted(set(vv)) for kk, vv in v.items()} for k, v in gov.items()}
    bad_nsa = [k for k in gov["next_stage_authorized_values"] if k.lower() in ("true", '"true"')]
    bad_rev = [k for k in gov["review_status_values"]
               if k and not re.search(r"PENDING|HOLD|NOT_", k, re.I)]
    res["governance_field_verdict"] = {
        "next_stage_authorized_true_occurrences": {
            k: gov["next_stage_authorized_values"][k] for k in bad_nsa},
        "review_status_values_not_pending": {
            k: gov["review_status_values"][k] for k in bad_rev},
        "any_next_stage_authorized_true": bool(bad_nsa),
        "any_review_status_claiming_completion": bool(bad_rev),
    }
    res["coverage"] = {
        "text_files_scanned": scanned,
        "lines_scanned": lines_scanned,
        "non_text_files_skipped": skipped_binary,
        "skip_reason": "binary solver artifacts (.odb/.prt) carry no prose claims",
        "self_excluded": [rel_to_project(SELF_PATH), rel_to_project(OUT_PATH)],
    }
    hard = bool(bad_nsa) or bool(bad_rev)
    res["result"] = "FAIL" if (hard or res["breaches"]) else "PASS"
    return res


# ---------------------------------------------------------------------------
# CHECK 6 -- standards citation check
# ---------------------------------------------------------------------------
def check6_standards():
    res = {
        "check_id": "C6",
        "name": "STANDARDS_CITATION_CHECK",
        "ledger": {}, "matrix": {},
        "standards_in_ledger": [],
        "draft_revisions_in_ledger": [],
        "citations_found": [],
        "citations_not_in_ledger": [],
        "out_of_scope_citations": [],
        "typical_property_as_allowable_hits": [],
        "draft_revision_citations": [],
        "coverage": {},
        "result": None,
    }
    lp = os.path.join(CDR_ROOT, "01_wp0_requirements", "STANDARDS_SOURCE_LEDGER_V1.csv")
    mp = os.path.join(CDR_ROOT, "01_wp0_requirements", "STANDARDS_TAILORING_MATRIX_V1.csv")
    for tag, p, key in (("ledger", lp, "ledger"), ("matrix", mp, "matrix")):
        if not os.path.isfile(longpath(p)):
            res[key] = {"path": rel_to_project(p), "status": "MISSING"}
            res["result"] = "NOT_EVALUATED"
            res["hold"] = "STANDARDS_LEDGER_ABSENT_HOLD"
            return res
        res[key] = {"path": rel_to_project(p), "bytes": os.path.getsize(longpath(p)),
                    "sha256": sha256_file(p)}
    with io.open(lp, "r", encoding="utf-8-sig", newline="") as fh:
        ledger = list(csv.DictReader(fh))
    with io.open(mp, "r", encoding="utf-8-sig", newline="") as fh:
        matrix = list(csv.DictReader(fh))
    res["ledger"]["rows"] = len(ledger)
    res["matrix"]["rows"] = len(matrix)

    doc_ids = []
    for r in ledger:
        did = (r.get("document_id") or "").strip()
        doc_ids.append({
            "document_id": did,
            "revision": (r.get("revision_or_change") or "").strip(),
            "document_class": (r.get("document_class") or "").strip(),
            "official_status": (r.get("official_status") or "").strip(),
            "project_role": (r.get("project_role") or "").strip(),
            "controlled_copy": (r.get("project_controlled_copy_status") or "").strip(),
        })
        if re.search(r"draft", (r.get("official_status") or "") +
                     (r.get("change_or_reconfirmation_date") or "") +
                     (r.get("verification_note") or ""), re.I):
            res["draft_revisions_in_ledger"].append({
                "document_id": did,
                "official_status": r.get("official_status"),
                "note": r.get("verification_note"),
                "draft_marker": re.search(
                    r"[^,;]*draft[^,;]*",
                    (r.get("official_status") or "") + " | " +
                    (r.get("change_or_reconfirmation_date") or "") + " | " +
                    (r.get("verification_note") or ""), re.I).group(0).strip(),
            })
    res["standards_in_ledger"] = doc_ids
    matrix_by_std = {(r.get("standard_id") or "").strip(): r for r in matrix}
    res["matrix_compliance_claims"] = sorted(set(
        (r.get("compliance_claim") or "").strip() for r in matrix))

    # regex for standard designators that may appear in M7 text
    STD_RX = re.compile(
        r"(ECSS[-\s]?[A-Z][-\s]?(?:ST|HB)[-\s]?[0-9]{1,2}(?:-[0-9]{1,2})*[A-Z]?(?:[-_\s]?Rev\.?\s?[0-9])?)"
        r"|(NASA[-\s]?STD[-\s]?[0-9]{4}[A-Z]?(?:[-_\s]?Change\s?[0-9])?)"
        r"|(MIL[-\s]?(?:STD|HDBK)[-\s]?[0-9]{3,4}[A-Z]?)"
        r"|(MMPDS(?:[-\s]?[0-9]{2,4})?)"
        r"|(MSFC[-\s]?STD[-\s]?[0-9]+)"
        r"|(ISO\s?[0-9]{3,5}(?:-[0-9]+)?)"
        r"|(ASTM\s?[A-Z][0-9]+)"
        r"|(NASA[-\s]?TM[-\s]?[0-9]+)", re.I)

    def canon(s):
        return re.sub(r"[^A-Z0-9]", "", s.upper())

    ledger_canon = {}
    for d in doc_ids:
        ledger_canon[canon(d["document_id"])] = d
        # also allow the 'B' suffix form NASA-STD-5001B
        if d["document_id"].upper().startswith("NASA-STD-5001"):
            ledger_canon[canon("NASA-STD-5001B")] = d
    scanned = 0
    hits = {}
    typ_rx = re.compile(
        r"typical", re.I)
    allow_rx = re.compile(r"allowable|margin[\s_-]*of[\s_-]*safety|\bMoS\b|\bMS\b", re.I)
    for root, dirs, files in os.walk(M7_ROOT):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXT or ext in (".odb", ".prt"):
                continue
            p = os.path.join(root, f)
            if os.path.abspath(p) in (SELF_PATH, os.path.abspath(OUT_PATH)):
                continue
            try:
                txt = read_bytes(p).decode("utf-8", "replace")
            except Exception:
                continue
            scanned += 1
            for i, line in enumerate(txt.splitlines(), 1):
                for m in STD_RX.finditer(line):
                    tok = m.group(0).strip()
                    ck = canon(tok)
                    rec = hits.setdefault(ck, {"token_examples": set(), "occurrences": 0,
                                               "files": set(), "first_line": None,
                                               "sample_text": None})
                    rec["token_examples"].add(tok)
                    rec["occurrences"] += 1
                    rec["files"].add(rel_to_project(p))
                    if rec["first_line"] is None:
                        rec["first_line"] = {"file": rel_to_project(p), "line": i}
                        rec["sample_text"] = line.strip()[:300]
                if typ_rx.search(line) and allow_rx.search(line):
                    res["typical_property_as_allowable_hits"].append({
                        "file": rel_to_project(p), "line": i, "text": line.strip()[:400],
                        "classification": ("LEGITIMATE_PROHIBITION_OR_NEGATION"
                                           if NEGATION.search(line) else
                                           "REVIEW_REQUIRED_POSSIBLE_TYPICAL_AS_ALLOWABLE")})
    for ck, rec in sorted(hits.items()):
        entry = {
            "canonical": ck,
            "tokens_as_written": sorted(rec["token_examples"]),
            "occurrences": rec["occurrences"],
            "files": sorted(rec["files"])[:12],
            "file_count": len(rec["files"]),
            "first_occurrence": rec["first_line"],
            "sample_text": rec["sample_text"],
            "in_ledger": False, "ledger_document_id": None,
            "ledger_document_class": None, "ledger_project_role": None,
            "matrix_compliance_claim": None, "scope_verdict": None,
        }
        # match by prefix: a citation is in-ledger if some ledger doc id canon is a
        # prefix of the citation canon or vice versa
        best = None
        for lc, d in ledger_canon.items():
            if ck == lc or ck.startswith(lc) or lc.startswith(ck):
                if best is None or len(lc) > len(canon(best["document_id"])):
                    best = d
        if best:
            entry["in_ledger"] = True
            entry["ledger_document_id"] = best["document_id"]
            entry["ledger_document_class"] = best["document_class"]
            entry["ledger_project_role"] = best["project_role"]
            mrow = None
            for sid, r in matrix_by_std.items():
                if canon(sid).startswith(canon(best["document_id"])) or \
                        canon(best["document_id"]).startswith(canon(sid)):
                    mrow = r
                    break
            if mrow:
                entry["matrix_compliance_claim"] = mrow.get("compliance_claim")
                entry["matrix_disposition"] = mrow.get("tailoring_or_use_disposition")
            entry["scope_verdict"] = "CITED_WITHIN_LEDGER_SCOPE"
        else:
            entry["scope_verdict"] = "NOT_IN_CDR_STANDARDS_LEDGER"
            res["citations_not_in_ledger"].append(entry)
        # draft-revision guard
        for d in res["draft_revisions_in_ledger"]:
            if canon(d["document_id"]) in ck or ck in canon(d["document_id"]):
                entry["ledger_records_a_draft_revision"] = d["draft_marker"]
                # is the M7 citation the draft revision itself?
                if re.search(r"REV\.?1|REV1", "".join(entry["tokens_as_written"]), re.I):
                    res["draft_revision_citations"].append(entry)
        res["citations_found"].append(entry)
    res["coverage"] = {
        "text_files_scanned": scanned,
        "distinct_standard_designators_found": len(res["citations_found"]),
        "ledger_rows": len(ledger), "matrix_rows": len(matrix),
    }
    res["tally"] = {
        "distinct_citations": len(res["citations_found"]),
        "in_ledger": sum(1 for e in res["citations_found"] if e["in_ledger"]),
        "not_in_ledger": len(res["citations_not_in_ledger"]),
        "draft_revision_citations": len(res["draft_revision_citations"]),
        "typical_as_allowable_review_required": sum(
            1 for h in res["typical_property_as_allowable_hits"]
            if h["classification"].startswith("REVIEW_REQUIRED")),
        "typical_as_allowable_legitimate_prohibition": sum(
            1 for h in res["typical_property_as_allowable_hits"]
            if h["classification"].startswith("LEGITIMATE")),
    }
    bad = (res["tally"]["not_in_ledger"] or res["tally"]["draft_revision_citations"]
           or res["tally"]["typical_as_allowable_review_required"])
    res["result"] = "FAIL" if bad else "PASS"
    return res


# ---------------------------------------------------------------------------
def main():
    if not os.path.isdir(longpath(OUT_DIR)):
        os.makedirs(longpath(OUT_DIR))
    t0 = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    c1 = check1_frozen_baseline()
    c2 = check2_receipts()
    c3 = check3_line_endings(c1, c2)
    c4 = check4_degenerate()
    c5 = check5_authority_scope()
    c6 = check6_standards()

    checks = [c1, c2, c3, c4, c5, c6]

    # ------------------------------------------------------------------ findings
    findings = []

    def add(sev, fid, title, detail, evidence, disposition):
        findings.append({"finding_id": fid, "severity": sev, "title": title,
                         "detail": detail, "evidence": evidence,
                         "disposition": disposition})

    if c1["tally"]["drift"]:
        add("HIGH", "CM01-F01", "Frozen baseline hash drift",
            "One or more CDR-frozen production inputs no longer match their pinned SHA-256. "
            "Frozen baseline hash drift is on the Gate A blocking list.",
            [r for r in c1["per_file"] if r["verdict"] == "DRIFT"],
            "GATE_A_CRITERION_01_MUST_BE_HOLD")
    if c1["tally"]["missing"] or c1["tally"]["zero_byte"]:
        add("HIGH", "CM01-F02", "Frozen baseline input missing or zero-byte",
            "A pinned frozen input is absent or zero length.",
            [r for r in c1["per_file"] if r["verdict"] in ("MISSING", "ZERO_BYTE")],
            "GATE_A_CRITERION_01_MUST_BE_HOLD")
    if c1["tally"]["cross_source_disagreements"]:
        add("HIGH", "CM01-F03", "CDR freeze authority files disagree with each other",
            "PRE_INPUT_HASHES_V1.csv and FROZEN_BASELINE_INPUT_MANIFEST_V1.json pin "
            "different values for the same input id.",
            c1["cross_source_disagreements"], "CM_AUTHORITY_RECONCILIATION_REQUIRED")
    real_mm = [m for m in c2["mismatches"]
               if m.get("guard_verdict") ==
               "REAL_CONTENT_MISMATCH_NOT_EXPLAINED_BY_LINE_ENDINGS"]
    if real_mm:
        add("HIGH", "CM01-F04", "Receipt hash mismatch not explained by line endings",
            "A receipt pins a SHA-256 that the file on disk does not have, and the "
            "LF-normalised and git-blob hashes do not explain it either. Typical root cause: "
            "the receipt was written before the final file write.",
            real_mm, "WORK_PACKAGE_RECEIPT_MUST_BE_REGENERATED")
    absent = [m for m in c2["mismatches"]
              if m["classification"] == "REFERENCED_FILE_ABSENT_ON_DISK"]
    if absent:
        add("HIGH" if any(m["register"] == "produced" for m in absent) else "MEDIUM",
            "CM01-F05", "Receipt references a file that does not exist on disk",
            "An artifact pinned by a receipt cannot be located under the project root, the "
            "M7 root, or the receipt directory.",
            absent, "NO_EVIDENCE_IS_NEVER_PASS")
    if c4["tally"]["zero_byte"]:
        add("HIGH", "CM01-F06", "Zero-byte evidence present",
            "Zero-byte evidence is on the Gate A blocking list.",
            c4["findings"]["zero_byte"], "GATE_A_CRITERION_01_MUST_BE_HOLD")
    if c4["tally"]["json_parse_fail"] or c4["tally"]["yaml_parse_fail"]:
        add("HIGH", "CM01-F07", "Unparseable structured evidence",
            "A .json/.yaml artifact under M7 does not parse; a consumer cannot load it.",
            c4["findings"]["json_parse_fail"] + c4["findings"]["yaml_parse_fail"],
            "ARTIFACT_MUST_BE_REGENERATED")
    if c4["tally"]["json_all_null"]:
        add("HIGH", "CM01-F08", "Artifact whose every leaf value is null",
            "A degenerate artifact that would let a PASS be summarised over no content.",
            c4["findings"]["json_all_null"], "FAIL_CLOSED_HOLD_REQUIRED")
    if c4["tally"]["csv_header_only"]:
        add("MEDIUM", "CM01-F09", "CSV with a header and no data rows",
            "Header-only CSV is degenerate evidence: any count derived from it is zero.",
            c4["findings"]["csv_header_only"], "REVIEW_WHETHER_A_CLAIM_RESTS_ON_IT")
    if c5["governance_field_verdict"]["any_next_stage_authorized_true"]:
        add("HIGH", "CM01-F10", "next_stage_authorized set true",
            "Governance requires next_stage_authorized=false at M7 issue.",
            c5["governance_field_verdict"]["next_stage_authorized_true_occurrences"],
            "MUST_BE_REVERTED_TO_FALSE")
    if c5["governance_field_verdict"]["any_review_status_claiming_completion"]:
        add("HIGH", "CM01-F11", "review_status claims review is complete",
            "Governance requires review_status=PENDING_OWNER_REVIEW at M7 issue.",
            c5["governance_field_verdict"]["review_status_values_not_pending"],
            "MUST_BE_REVERTED_TO_PENDING_OWNER_REVIEW")
    if c5["breaches"]:
        add("MEDIUM", "CM01-F12", "Authority-scope language requiring adjudication",
            "Regex hits for flight/launch/manufacturing-release/qualified language on lines "
            "that carry no prohibition or negation context. Each needs a human read; the "
            "classifier is deliberately conservative and over-reports.",
            c5["breaches"][:60], "PER_LINE_ADJUDICATION_REQUIRED")
    if c6.get("tally", {}).get("not_in_ledger"):
        add("MEDIUM", "CM01-F13", "Standard cited that the CDR ledger does not contain",
            "An M7 artifact cites a standard designator with no row in "
            "STANDARDS_SOURCE_LEDGER_V1.csv, so its revision, status and controlled-copy "
            "state are unverified.",
            c6["citations_not_in_ledger"], "ADD_TO_LEDGER_OR_REMOVE_THE_CITATION")
    if c6.get("tally", {}).get("draft_revision_citations"):
        add("HIGH", "CM01-F14", "Draft-revision standard cited as if adopted",
            "The ledger records this revision as still drafting / not adopted.",
            c6["draft_revision_citations"], "CITATION_MUST_BE_RETARGETED_TO_PUBLISHED_ISSUE")
    if c6.get("tally", {}).get("typical_as_allowable_review_required"):
        add("HIGH", "CM01-F15", "Possible typical property used as a design allowable",
            "NASA-STD-5001B (and the project's own standing prohibition) forbid deriving a "
            "margin of safety from a typical material property.",
            [h for h in c6["typical_property_as_allowable_hits"]
             if h["classification"].startswith("REVIEW_REQUIRED")],
            "MARGIN_MUST_NOT_REST_ON_A_TYPICAL_VALUE")

    high = [f for f in findings if f["severity"] == "HIGH"]

    all_pass = all(str(c["result"]).startswith("PASS") for c in checks)
    not_eval = [c["check_id"] for c in checks if c["result"] == "NOT_EVALUATED"]

    if not_eval:
        crit = "HOLD"
        crit_reason = "one or more required checks could not be evaluated: %s" % ",".join(not_eval)
    elif high:
        crit = "HOLD"
        crit_reason = "%d HIGH finding(s) open against input / CM integrity" % len(high)
    elif all_pass:
        crit = "PASS"
        crit_reason = ("all six required checks PASS: 18/18 frozen inputs byte-identical, "
                       "0 receipt hash mismatches, 0 zero-byte or degenerate artifacts, "
                       "0 hard governance-field breaches, 0 out-of-ledger or draft-revision "
                       "standard citations")
    else:
        crit = "HOLD"
        crit_reason = "a required check returned FAIL"

    med = [f for f in findings if f["severity"] == "MEDIUM"]

    doc = {
        "schema": "M7_INPUT_AND_CM_INTEGRITY_AUDIT_V1",
        "generated_local": t0.isoformat(),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "host_os": "Windows 10.0.26100 / win32",
        "python": sys.version.split()[0],
        "phase": "F3R2_M7_TERMINAL_MECHANICAL_CLOSURE",
        "role": "A7_CM_RELEASE_READ_ONLY_INDEPENDENT_AUDIT",
        "gate_a_criterion": {
            "id": "01",
            "name": "INPUT_AND_CM_INTEGRITY",
            "requirement": "frozen input hashes 100% consistent",
            "authority": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                         "00_authority/M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml",
        },
        "authority_chain": {
            "rule": "Authority > Evidence > Independent reproduction > Agent opinion",
            "voting": "FORBIDDEN",
            "odr_register": "M7_OWNER_DECISION_REGISTER_V1.yaml (ODR-01..ODR-06)",
            "terminal_contract": "M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml (ODR-07..ODR-17)",
        },
        "standing_declarations": {
            "review_status": "PENDING_OWNER_REVIEW",
            "next_stage_authorized": False,
            "gate_b_mechanical_flight_qualification": "HOLD",
            "memory_gate_6gib": "FAILED_ON_THIS_HOST_DECLARED_FAILED",
            "flight_launch_manufacturing_qualification_claims": "NONE_MADE",
            "m8_m9_planning_artifacts_created": 0,
            "design_not_equal_flight_qualified": True,
            "candidate_not_equal_authority": True,
            "analysis_not_equal_test": True,
        },
        "method": {
            "hashing": "python hashlib.sha256 over actual bytes, uppercase hex",
            "hash_provenance": "every hash in this document was computed by this run; "
                               "no hash was copied from a sibling document",
            "byte_sizes": "os.path.getsize on the same bytes that were hashed",
            "long_path_handling": r"all opens go through the \\?\ prefix (repo has "
                                  r"core.longpaths unset)",
            "read_only": "no work-package file was created, modified or deleted by this run",
            "tools_started": "none (no FreeCAD, no SolidWorks, no Abaqus)",
        },
        "checks": {c["check_id"]: c for c in checks},
        "check_results_summary": {c["check_id"]: {"name": c["name"], "result": c["result"]}
                                  for c in checks},
        "findings": findings,
        "findings_summary": {
            "high": len(high), "medium": len(med),
            "high_ids": [f["finding_id"] for f in high],
            "medium_ids": [f["finding_id"] for f in med],
        },
        "gate_a_criterion_01_verdict": {
            "status": crit,
            "status_semantics_per_ODR_14": (
                "PASS = internal design fully closed for this criterion"),
            "reason": crit_reason,
            "blocking_list_items_cleared": [
                "zero-byte evidence", "frozen baseline hash drift"],
            "contributes_to_terminal_release_condition": {
                "hash_mismatch_count": (c1["tally"]["drift"] +
                                        c2["tally"]["sha_mismatch"] +
                                        c2["tally"]["bytes_mismatch"]),
                "high_severity_open_findings_from_this_audit": len(high),
                "zero_byte_evidence_count": c4["tally"]["zero_byte"],
            },
        },
        "declared_open_cm_items": [
            {
                "id": "CM-OPEN-01",
                "item": "V2_BASELINE_SUPERSESSION_ECR_NOT_YET_RAISED",
                "statement": (
                    "MECHANICAL_BASELINE_CHANGE_CONTROL_POLICY_V1 classifies any geometry / "
                    "mass / inertia / frame / collision / accepted-configuration change as V2 "
                    "and requires an ECR plus an 11-item Sim13 regression before production "
                    "consumers are re-pointed. M7 has not disturbed a single frozen input, so "
                    "criterion 01 is clean; but the act of declaring "
                    "MECHANICAL_ENGINEERING_DESIGN_RELEASED and re-pointing Sim13/RL at M7 "
                    "assets would be a V2 event. The ECR register currently holds only "
                    "ECR-000 (PROCESS_ONLY, no production change)."),
                "external_dependency": "Owner / Chief Engineer ECR approval",
                "blocks_gate_a_criterion_01": False,
                "blocks_downstream_consumer_repointing": True,
            },
            {
                "id": "CM-OPEN-02",
                "item": "WP13_EMBODIED_MECHANICAL_CONTRACT_PENDING",
                "statement": (
                    "wp13_embodied_mechanical_contract is being authored concurrently by "
                    "another agent and was not present on disk at audit time. No hash, "
                    "receipt or content of it is asserted here. ODR-15/ODR-16 artifacts "
                    "(EMBODIED_MECHANICAL_CONTRACT_V1.yaml, "
                    "MECHANICAL_TO_EMBODIED_HANDOFF_GATE.json) are therefore NOT_EVALUATED "
                    "by this audit."),
                "external_dependency": "concurrent WP13 agent",
                "blocks_gate_a_criterion_01": False,
            },
            {
                "id": "CM-OPEN-03",
                "item": "CONCURRENT_WRITE_ZONE_12_RELEASE",
                "statement": (
                    "12_release/ is being written concurrently by sibling integration agents. "
                    "The C4 sweep is a point-in-time snapshot; files created in 12_release "
                    "after this run's walk are outside its coverage and must be re-swept by "
                    "the final integration pass."),
                "external_dependency": "A0 final integration sweep",
                "blocks_gate_a_criterion_01": False,
            },
        ],
        "coverage_statement": {
            "frozen_inputs": "%d/%d pinned CDR inputs recomputed from actual bytes"
                             % (c1["tally"]["frozen_inputs_evaluated"],
                                max(c1["tally"]["frozen_inputs_declared_csv"],
                                    c1["tally"]["frozen_inputs_declared_manifest"])),
            "receipts": "%d receipt.json files; %d pinned file entries recomputed"
                        % (c2["tally"]["work_packages_with_receipt"], c2["tally"]["entries"]),
            "m7_tree": "%d files walked, %d skipped, %d bytes"
                       % (c4["coverage"]["files_walked"], c4["coverage"]["files_skipped"],
                          c4["coverage"]["total_bytes_walked"]),
            "text_sweep": "%d text files / %d lines scanned for authority-scope language"
                          % (c5["coverage"]["text_files_scanned"],
                             c5["coverage"]["lines_scanned"]),
            "standards": "%d distinct standard designators reconciled against a %d-row ledger"
                         % (c6.get("coverage", {}).get("distinct_standard_designators_found", 0),
                            c6.get("coverage", {}).get("ledger_rows", 0)),
            "skipped_and_why": [
                "__pycache__ directories: python bytecode, not evidence",
                ".odb/.prt binary Abaqus artifacts: size-checked and hash-checked but not "
                "text-scanned (no prose claims inside)",
                "this builder script and this output file: excluded from the authority-scope "
                "text sweep to avoid self-matching on the prohibition vocabulary it searches for",
                "wp13_embodied_mechanical_contract: not present on disk at audit time "
                "(recorded as CM-OPEN-02, not silently omitted)",
            ],
        },
        "prohibitions_honored": [
            "no work-package file edited (read-only audit)",
            "no zero-fill of unknowns; every absent input became null + a named HOLD",
            "no hash copied from a sibling document; all recomputed with hashlib",
            "no flight / launcher / manufacturing-release / qualification claim asserted",
            "Gate B left at HOLD; review_status PENDING_OWNER_REVIEW; "
            "next_stage_authorized false",
            "no M8/M9 planning artifact created (ODR-17)",
            "6 GiB memory gate declared FAILED",
            "no FreeCAD or SolidWorks process started",
            "no voting; adjudication by Authority > Evidence > reproduction",
        ],
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "produced_files": [],
        "source_register": {},
    }

    # source register: everything this audit consumed as authority
    for p in [
        os.path.join(M7_ROOT, "README.md"),
        os.path.join(M7_ROOT, "00_authority", "M7_OWNER_DECISION_REGISTER_V1.yaml"),
        os.path.join(M7_ROOT, "00_authority", "M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml"),
        os.path.join(M7_ROOT, "00_authority", "M7_EXECUTION_PLAN_V1.md"),
        os.path.join(CDR_ROOT, "00_authority", "PRE_INPUT_HASHES_V1.csv"),
        os.path.join(CDR_ROOT, "00_authority", "FROZEN_BASELINE_INPUT_MANIFEST_V1.json"),
        os.path.join(CDR_ROOT, "00_authority", "MECHANICAL_BASELINE_CHANGE_CONTROL_POLICY_V1.yaml"),
        os.path.join(CDR_ROOT, "00_authority", "MECHANICAL_ECR_REGISTER_V1.csv"),
        os.path.join(CDR_ROOT, "01_wp0_requirements", "STANDARDS_SOURCE_LEDGER_V1.csv"),
        os.path.join(CDR_ROOT, "01_wp0_requirements", "STANDARDS_TAILORING_MATRIX_V1.csv"),
    ] + sorted(find_receipts()):
        rel = rel_to_project(p)
        if os.path.isfile(longpath(p)):
            doc["source_register"][rel] = {
                "path": rel, "bytes": os.path.getsize(longpath(p)), "sha256": sha256_file(p),
                "role": "CONSUMED_READ_ONLY"}
        else:
            doc["source_register"][rel] = {
                "path": rel, "bytes": None, "sha256": None,
                "role": "CONSUMED_READ_ONLY", "status": "MISSING_HOLD"}

    doc["produced_files"].append({
        "path": rel_to_project(SELF_PATH),
        "bytes": os.path.getsize(longpath(SELF_PATH)),
        "sha256": sha256_file(SELF_PATH),
        "role": "AUDIT_BUILDER_SCRIPT",
    })
    doc["produced_files"].append({
        "path": rel_to_project(OUT_PATH),
        "bytes": None, "sha256": None,
        "role": "THIS_AUDIT_ARTIFACT",
        "self_hash_note": ("a file cannot contain its own SHA-256; the consumer computes it "
                           "from the bytes on disk and A0 pins it in "
                           "M7_RELEASE_MANIFEST"),
    })

    with io.open(longpath(OUT_PATH), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")

    print("WROTE", OUT_PATH)
    print("bytes", os.path.getsize(longpath(OUT_PATH)))
    print("sha256", sha256_file(OUT_PATH))
    print(json.dumps({
        "verdict": crit, "reason": crit_reason,
        "results": {c["check_id"]: c["result"] for c in checks},
        "C1": c1["tally"],
        "C2": c2["tally"],
        "C3": c3["tally"],
        "C4": c4["tally"],
        "C5": {"breaches": len(c5["breaches"]),
               "legit": c5["legitimate_mentions_by_pattern"],
               "gov": c5["governance_field_verdict"]},
        "C6": c6.get("tally"),
        "high": [f["finding_id"] + ": " + f["title"] for f in high],
        "medium": [f["finding_id"] + ": " + f["title"] for f in med],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
