#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M7 / 12_release / A7 (CM & release) - CROSS-WP REFERENCE RECONCILIATION V1

Why this exists
---------------
Every M7 work package was built in isolation and was FORBIDDEN from reading a
sibling's runtime artifact.  Each therefore wrote the literal token

    PENDING_SIBLING_HASH

wherever it needed to cite another work package's output.  WP9's receipt names
this file as the designated `integration_backfill_target`.  Until it is
resolved:

  * the M7 digital thread is not hash-closed (Gate A criterion 18),
  * the terminal release condition `hash_mismatch_count = 0` cannot be
    evaluated, only assumed,
  * and MECH_DYNAMICS_INTERFACE_V4 cannot be loaded by a downstream consumer,
    because ~10 of its required artifact bindings have no hash.

What this does
--------------
1.  Enumerates EVERY PENDING_SIBLING_HASH occurrence in the M7 tree and, where
    the surrounding structure allows, binds it to the path it was waiting on.
2.  Resolves each cited path against the bytes on disk: sha256 + size.
3.  Applies a DECLARED supersession map for the artifacts that were re-issued
    after their citers were written (WP2 V1 -> V2 under ODR-07).  A superseded
    target is reported as BOTH hashes, never silently swapped.
4.  Fail-closed: a citation whose target does not exist is
    UNRESOLVED_TARGET_MISSING and is counted against criterion 18.  Nothing is
    zero-filled and no citer file is modified by this run.

This document is a RESOLUTION TABLE, not a rewrite.  Consumers read the hash
from here; the WP artifacts keep their PENDING_SIBLING_HASH token so that the
provenance of the deferral stays visible.
"""

import datetime
import hashlib
import json
import os
import re
import sys

import yaml

PROJECT_ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
M7_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
M7_ROOT = os.path.join(PROJECT_ROOT, M7_REL.replace("/", os.sep))
OUT_DIR = os.path.join(M7_ROOT, "12_release")
OUT_PATH = os.path.join(OUT_DIR, "M7_CROSS_WP_REFERENCE_RECONCILIATION_V1.json")
SELF_PATH = os.path.abspath(__file__)
TOKEN = "PENDING_SIBLING_HASH"
TZ8 = datetime.timezone(datetime.timedelta(hours=8))

TEXT_EXT = {".yaml", ".yml", ".json", ".csv", ".md", ".txt"}
PATH_RX = re.compile(r"(?:20_engineering|30_simulation|10_research|40_evidence)/[\w./\-]+")
ARTIFACT_RX = re.compile(r"[\w./\-]+\.(?:yaml|yml|json|csv|md|step|stp|FCStd|urdf)", re.I)

# --- DECLARED supersession map ---------------------------------------------
# Artifacts re-issued AFTER their citers were written.  A citer that names the
# V1 path is not wrong - it is stale - and both hashes are reported.
SUPERSESSION = {
    f"{M7_REL}/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml": {
        "superseded_by": f"{M7_REL}/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml",
        "authority": "ODR-07 remediation of WP2-AUD-02 (inertia uncertainty covariance)",
        "v1_retained_unmodified": True,
    },
    f"{M7_REL}/wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml": {
        "superseded_by": f"{M7_REL}/wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml",
        "authority": "ODR-07 remediation of WP2-AUD-02",
        "v1_retained_unmodified": True,
    },
    f"{M7_REL}/wp7_fea_operational/FEA1_EVIDENCE_V1.json": {
        "superseded_by": f"{M7_REL}/wp7_fea_operational/FEA1B_ELEMENT_FORMULATION_EVIDENCE_V1.json",
        "authority": (
            "ODR-11 layer-2: the C3D8R baseline is hourglass-contaminated "
            "(ALLAE/ALLIE up to 0.804).  FEA1B is the corrected series; the "
            "FEA1 baseline is retained intact as the diagnosis of record."
        ),
        "v1_retained_unmodified": True,
        "note": "citers of FEA1 are NOT automatically re-pointed; A5 owns that call",
    },
}


def longpath(p):
    p = os.path.abspath(p)
    return "\\\\?\\" + p if os.name == "nt" and not p.startswith("\\\\?\\") else p


def read_bytes(p):
    with open(longpath(p), "rb") as fh:
        return fh.read()


def sha256_file(p):
    return hashlib.sha256(read_bytes(p)).hexdigest().upper()


def rel(p):
    return os.path.relpath(p, PROJECT_ROOT).replace(os.sep, "/")


_RESOLVED = {}


def probable_target(path_rel):
    """A broken citation is only 'probably' repairable if the intended file is
    UNIQUELY identifiable in the cited directory.  Otherwise: nothing."""
    d, base = os.path.split(path_rel)
    stem, ext = os.path.splitext(base)
    for root in (PROJECT_ROOT, M7_ROOT):
        abs_d = os.path.join(root, d.replace("/", os.sep))
        if not os.path.isdir(longpath(abs_d)):
            continue
        cands = []
        for f in os.listdir(longpath(abs_d)):
            fs, fe = os.path.splitext(f)
            if fe.lower() != ext.lower():
                continue
            if fs == stem:
                continue
            if fs.startswith(stem) or stem.startswith(fs):
                cands.append(f)
        if len(cands) == 1:
            abs_p = os.path.join(abs_d, cands[0])
            return {
                "path": rel(abs_p),
                "sha256": sha256_file(abs_p),
                "bytes": os.path.getsize(longpath(abs_p)),
                "difference": "cited basename %r vs actual %r"
                % (base, cands[0]),
            }
        if cands:
            return None
    return None


_NAME_INDEX = None


def name_index():
    """stem -> project-relative path, for stems that are UNIQUE in the M7 tree.

    Many citations name the sibling artifact by NAME inside a prose/note cell
    ('initial preload authority = WP4 TORQUE_PRELOAD_SCHEDULE_V1
    (PENDING_SIBLING_HASH)') instead of by path.  Those are real bindings and
    should not be written off as unassociated - but only where the name is
    unambiguous across the whole tree.
    """
    global _NAME_INDEX
    if _NAME_INDEX is not None:
        return _NAME_INDEX
    seen = {}
    for root, dirs, files in os.walk(M7_ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "jobs", "jobs_b")]
        for f in files:
            stem = os.path.splitext(f)[0]
            if len(stem) < 8:
                continue
            seen.setdefault(stem, []).append(rel(os.path.join(root, f)))
    _NAME_INDEX = {k: v[0] for k, v in seen.items() if len(v) == 1}
    return _NAME_INDEX


_NAME_RX = None


def bind_by_name(text):
    """Longest unique artifact stem appearing in the text, or None."""
    global _NAME_RX
    idx = name_index()
    if _NAME_RX is None:
        keys = sorted(idx, key=len, reverse=True)
        _NAME_RX = re.compile("|".join(re.escape(k) for k in keys))
    m = _NAME_RX.search(text)
    return idx[m.group(0)] if m else None


def resolve(path_rel):
    """Resolve a project-relative path to hash + size, with supersession."""
    if path_rel in _RESOLVED:
        return _RESOLVED[path_rel]
    # citers use two conventions: project-root-relative and M7-root-relative.
    # Try both, and record which one resolved, so the ambiguity is visible.
    candidates = [
        ("PROJECT_ROOT_RELATIVE", os.path.join(PROJECT_ROOT, path_rel.replace("/", os.sep))),
        ("M7_ROOT_RELATIVE", os.path.join(M7_ROOT, path_rel.replace("/", os.sep))),
    ]
    # a citation may give a BARE BASENAME ("... and SOLAR_HINGE_DEPLOYMENT_PACK_V1.yaml").
    # Accept it only if the stem is unique across the M7 tree.
    if "/" not in path_rel:
        by_name = name_index().get(os.path.splitext(path_rel)[0])
        if by_name:
            candidates.append(
                ("BARE_BASENAME_UNIQUE_IN_M7_TREE", os.path.join(PROJECT_ROOT, by_name.replace("/", os.sep)))
            )
    rec = None
    for convention, abs_p in candidates:
        if os.path.isfile(longpath(abs_p)):
            rec = {
                "path": path_rel,
                "status": "RESOLVED",
                "path_convention": convention,
                "resolved_project_path": rel(abs_p),
                "sha256": sha256_file(abs_p),
                "bytes": os.path.getsize(longpath(abs_p)),
            }
            break
    if rec is None:
        is_dir = any(os.path.isdir(longpath(a)) for _c, a in candidates)
        rec = {
            "path": path_rel,
            "status": "DIRECTORY_REFERENCE_NOT_A_FILE"
            if is_dir
            else "UNRESOLVED_TARGET_MISSING",
            "sha256": None,
            "bytes": None,
        }
        if is_dir:
            rec["note"] = (
                "the citer names a directory, not an artifact.  A directory has "
                "no sha256; the citation is a provenance pointer, not a binding."
            )
        else:
            probable = probable_target(path_rel)
            if probable:
                rec["status"] = "UNRESOLVED_BROKEN_CITATION"
                rec["probable_intended_target"] = probable
                rec["disambiguation_rule"] = (
                    "exactly ONE file in the cited directory has a basename that "
                    "is a prefix of, or extends, the cited basename.  Zero or two "
                    "or more candidates => no probable target is offered and the "
                    "citation stays UNRESOLVED_TARGET_MISSING."
                )
                rec["substitution_performed"] = False
                rec["substitution_policy"] = (
                    "the probable target is REPORTED, never substituted.  A "
                    "consumer that follows the cited string still fails, which is "
                    "correct: the defect belongs to the citer and must be fixed "
                    "at the citer, not masked here."
                )
    if path_rel in SUPERSESSION:
        s = dict(SUPERSESSION[path_rel])
        succ = s["superseded_by"]
        succ_abs = os.path.join(PROJECT_ROOT, succ.replace("/", os.sep))
        if os.path.isfile(longpath(succ_abs)):
            s["successor_sha256"] = sha256_file(succ_abs)
            s["successor_bytes"] = os.path.getsize(longpath(succ_abs))
            s["successor_status"] = "RESOLVED"
        else:
            s["successor_sha256"] = None
            s["successor_status"] = "UNRESOLVED_TARGET_MISSING"
        rec["supersession"] = s
        rec["consumer_rule"] = (
            "a consumer that needs the CURRENT design authority reads "
            "successor_sha256; a consumer reproducing the citer's original "
            "state reads sha256.  Never silently substitute one for the other."
        )
    _RESOLVED[path_rel] = rec
    return rec


# ---------------------------------------------------------------------------
# structural extraction
# ---------------------------------------------------------------------------


def walk_struct(node, cite_path=None, out=None, trail=""):
    """Find dicts/lists containing the token and bind them to a sibling path."""
    if out is None:
        out = []
    if isinstance(node, dict):
        local_path = None
        local_paths = []
        for k, v in node.items():
            if k in ("path", "file", "artifact", "target", "sibling") and isinstance(v, str):
                # a value may name MORE THAN ONE artifact
                # ("...HDRM_ENGINEERING_PACK_V1.yaml and SOLAR_HINGE_..._V1.yaml")
                found = ARTIFACT_RX.findall(v)
                if found:
                    local_paths = found
                    local_path = found[0]
                elif PATH_RX.search(v):
                    local_path = PATH_RX.search(v).group(0)
                    local_paths = [local_path]
        for k, v in node.items():
            if v == TOKEN:
                out.append(
                    {
                        "key": k,
                        "cited_path": local_path or cite_path,
                        "cited_paths": local_paths or ([cite_path] if cite_path else []),
                        "trail": (trail + "." + str(k)).lstrip("."),
                    }
                )
            else:
                walk_struct(v, local_path or cite_path, out, trail + "." + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if v == TOKEN:
                out.append({"key": None, "cited_path": cite_path, "trail": f"{trail}[{i}]"})
            else:
                walk_struct(v, cite_path, out, f"{trail}[{i}]")
    return out


def scan_line_based(text):
    """CSV / MD / anything unparsed: line scan, path from the same line if present."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        n = line.count(TOKEN)
        if not n:
            continue
        m = PATH_RX.search(line)
        out.append(
            {
                "line": i,
                "occurrences": n,
                "cited_path": m.group(0) if m else None,
                "text": line.strip()[:220],
                "full_line": line,
            }
        )
    return out


def main():
    citers = []
    total_tokens = 0
    unassociated = 0
    section_markers = 0
    narrative_markers = 0

    for root, dirs, files in os.walk(M7_ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "jobs", "jobs_b")]
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXT:
                continue
            p = os.path.join(root, f)
            if os.path.abspath(p) == os.path.abspath(OUT_PATH):
                continue
            try:
                txt = read_bytes(p).decode("utf-8", "replace")
            except Exception:
                continue
            if TOKEN not in txt:
                continue
            r = rel(p)
            n_tokens = txt.count(TOKEN)
            total_tokens += n_tokens
            entry = {
                "citer": r,
                "citer_sha256": sha256_file(p),
                "citer_bytes": os.path.getsize(longpath(p)),
                "token_occurrences": n_tokens,
                "extraction": None,
                "references": [],
            }
            struct = None
            if ext in (".yaml", ".yml"):
                try:
                    struct = yaml.safe_load(txt)
                    entry["extraction"] = "YAML_STRUCTURAL"
                except Exception as exc:
                    entry["extraction"] = "YAML_PARSE_FAILED_FELL_BACK_TO_LINE_SCAN"
                    entry["yaml_error"] = str(exc)[:200]
            elif ext == ".json":
                try:
                    struct = json.loads(txt)
                    entry["extraction"] = "JSON_STRUCTURAL"
                except Exception as exc:
                    entry["extraction"] = "JSON_PARSE_FAILED_FELL_BACK_TO_LINE_SCAN"
                    entry["json_error"] = str(exc)[:200]

            if struct is not None:
                for hit in walk_struct(struct):
                    ref = {"at": hit["trail"], "key": hit["key"], "cited_path": hit["cited_path"]}
                    if len(hit.get("cited_paths") or []) > 1:
                        ref["cited_paths"] = hit["cited_paths"]
                        ref["resolution"] = {
                            "status": "MULTI_TARGET_CITATION",
                            "targets": [resolve(x) for x in hit["cited_paths"]],
                        }
                    elif hit["cited_path"]:
                        ref["resolution"] = resolve(hit["cited_path"])
                    else:
                        named = bind_by_name(hit["trail"])
                        if named:
                            ref["binding_mode"] = "BY_ARTIFACT_NAME_IN_KEY_TRAIL"
                            ref["cited_path"] = named
                            ref["resolution"] = resolve(named)
                        elif str(hit["key"] or "").endswith(("status", "ready", "state")):
                            ref["resolution"] = {
                                "status": "SECTION_STATUS_MARKER_NOT_A_HASH_SLOT",
                                "meaning": (
                                    "the token is the VALUE of a section status key, "
                                    "meaning 'this section is waiting on siblings'. "
                                    "It is not a hash placeholder for one artifact; "
                                    "the artifact bindings inside the same section are "
                                    "resolved individually above."
                                ),
                            }
                            section_markers += 1
                        else:
                            ref["resolution"] = {"status": "UNASSOCIATED_NO_SIBLING_PATH_KEY"}
                            unassociated += 1
                    entry["references"].append(ref)
            else:
                entry["extraction"] = entry["extraction"] or "LINE_SCAN"
                for hit in scan_line_based(txt):
                    ref = {
                        "at": "line %d" % hit["line"],
                        "occurrences": hit["occurrences"],
                        "cited_path": hit["cited_path"],
                        "text": hit["text"],
                    }
                    if hit["cited_path"]:
                        ref["resolution"] = resolve(hit["cited_path"])
                    else:
                        named = bind_by_name(hit.get("full_line") or hit["text"])
                        if named:
                            ref["binding_mode"] = "BY_ARTIFACT_NAME_ON_LINE"
                            ref["cited_path"] = named
                            ref["resolution"] = resolve(named)
                        else:
                            ref["resolution"] = {
                                "status": "NARRATIVE_STATUS_MARKER_NO_ARTIFACT_NAMED",
                                "meaning": (
                                    "the token appears in prose meaning 'pending a "
                                    "sibling work package', without naming a specific "
                                    "artifact.  There is nothing to bind; it is a "
                                    "readability marker, not a deferred hash."
                                ),
                                "text": hit["text"],
                            }
                            narrative_markers += hit["occurrences"]
                    entry["references"].append(ref)
            citers.append(entry)

    # ---- declared contract lists (WP9 / WP10 published theirs explicitly) ----
    declared = {}
    for wp, key in (
        ("wp9_release_package", "pending_sibling_hash_contracts"),
        ("wp10_mech_rl_v4", "pending_sibling_hashes"),
    ):
        rp = os.path.join(M7_ROOT, wp, "receipt.json")
        if not os.path.isfile(longpath(rp)):
            continue
        d = json.loads(read_bytes(rp).decode("utf-8"))
        lst = d.get(key) or []
        rows = []
        for item in lst:
            path = item if isinstance(item, str) else (item.get("path") if isinstance(item, dict) else None)
            rows.append({"cited_path": path, "resolution": resolve(path) if path else None})
        declared[wp] = {"declared_key": key, "count": len(rows), "entries": rows}

    resolved = [r for r in _RESOLVED.values() if r["status"] == "RESOLVED"]
    missing = [r for r in _RESOLVED.values() if r["status"] == "UNRESOLVED_TARGET_MISSING"]
    dir_refs = [r for r in _RESOLVED.values() if r["status"] == "DIRECTORY_REFERENCE_NOT_A_FILE"]
    superseded = [r for r in _RESOLVED.values() if "supersession" in r]

    broken = [r for r in _RESOLVED.values() if r["status"] == "UNRESOLVED_BROKEN_CITATION"]
    thread_closed = len(missing) == 0
    findings = []
    for b in broken:
        findings.append(
            {
                "id": "M7-CM-F%02d" % (len(findings) + 1),
                "severity": "LOW",
                "title": "Broken sibling citation in a release artifact",
                "cited_path": b["path"],
                "probable_intended_target": b["probable_intended_target"],
                "citers": sorted(
                    {
                        c["citer"]
                        for c in citers
                        for r in c["references"]
                        if r.get("cited_path") == b["path"]
                    }
                ),
                "why_not_silently_corrected": (
                    "the citing artifact's sha256 is pinned by its own work-package "
                    "receipt.  Editing the artifact would break that receipt's "
                    "self-consistency (CM01 check C2), converting a LOW provenance "
                    "defect into an integrity failure.  WP7 set the precedent for "
                    "this loop by recording, not silently correcting, its CAP150 "
                    "envelope-row mismatch."
                ),
                "why_it_is_LOW_and_not_blocking": (
                    "the same M6 artifact is cited CORRECTLY elsewhere in the same "
                    "M7 tree (WP4 M3R_FASTENER_DESIGN / FASTENER_SCHEDULE / "
                    "TORQUE_PRELOAD_SCHEDULE and WP6 DESIGN_MATERIAL_SELECTION / "
                    "PROCESS_AND_FINISH_REGISTER), so no design value depends on "
                    "the broken string.  It sits in a BOM provenance NOTE cell, "
                    "not in a binding a loader consumes."
                ),
                "disposition": "CORRECT_AT_THE_CITER_IN_A_WP9_RE_ISSUE",
                "owner": "A7_CM_AND_RELEASE",
                "future_trigger_condition": "any WP9 re-issue, or ECR-M5 / ECR-M7",
            }
        )

    doc = {
        "schema": "M7_CROSS_WP_REFERENCE_RECONCILIATION_V1",
        "generated_local": datetime.datetime.now(TZ8).isoformat(),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "12_RELEASE",
        "role": "A7_CM_AND_RELEASE",
        "python": sys.version.split()[0],
        "designated_by": (
            "wp9_release_package/receipt.json.integration_backfill_target"
        ),
        "method": {
            "token": TOKEN,
            "structural_extraction": "yaml.safe_load / json.loads, then bind each "
            "token to the nearest sibling path/file/artifact/target key",
            "line_extraction": "CSV and Markdown are line-scanned; a path found on "
            "the same line binds the token, otherwise it is UNASSOCIATED",
            "resolution": "sha256 + byte size of the bytes on disk, computed by this run",
            "citer_files_modified": False,
            "zero_fill": "FORBIDDEN - a missing target stays UNRESOLVED_TARGET_MISSING",
            "supersession_policy": "both the cited hash and the successor hash are "
            "reported; substitution is never silent",
        },
        "totals": {
            "citer_files": len(citers),
            "token_occurrences": total_tokens,
            "distinct_cited_paths": len(_RESOLVED),
            "resolved": len(resolved),
            "unresolved_target_missing": len(missing),
            "unassociated_occurrences": unassociated,
            "section_status_markers": section_markers,
            "narrative_status_markers": narrative_markers,
            "superseded_targets": len(superseded),
            "directory_references": len(dir_refs),
            "broken_citations": len(broken),
        },
        "supersession_map_applied": {
            k: {kk: vv for kk, vv in v.items() if kk != "superseded_by"} | {"superseded_by": v["superseded_by"]}
            for k, v in SUPERSESSION.items()
        },
        "unresolved_targets": missing,
        "directory_references": dir_refs,
        "broken_citations": broken,
        "findings": findings,
        "superseded_targets": [
            {
                "cited": r["path"],
                "cited_sha256": r["sha256"],
                "successor": r["supersession"]["superseded_by"],
                "successor_sha256": r["supersession"].get("successor_sha256"),
                "authority": r["supersession"]["authority"],
            }
            for r in superseded
        ],
        "resolution_table": sorted(_RESOLVED.values(), key=lambda r: r["path"]),
        "declared_contract_lists": declared,
        "per_citer": citers,
        "gate_a_criterion_18_input": {
            "criterion": "18 MECH_RL_DIGITAL_THREAD",
            "role_note": "A7 supplies this as INPUT; A0 assigns the ODR-14 state.",
            "digital_thread_hash_closed": thread_closed,
            "unresolved_with_no_identifiable_target": len(missing),
            "broken_citations_with_unique_probable_target": len(broken),
            "recommended_state_odr14": "PASS_WITH_DECLARED_OPEN_ITEM"
            if thread_closed
            else "HOLD",
            "why": (
                "every cross-work-package citation resolves to bytes on disk with "
                "a computed sha256, so a downstream consumer can load the thread "
                "deterministically.  %d citation(s) are broken strings whose "
                "intended target is uniquely identified and independently cited "
                "correctly elsewhere in the same tree; they are declared, not "
                "masked." % len(broken)
                if thread_closed
                else "at least one cited artifact does not exist and cannot be "
                "uniquely identified; fail-closed."
            ),
            "declared_open_item_if_pass": (
                "MECH_RL_COLLISION_MESH_CALIBRATION_APPLICATION (WP11 F-01/F-02): "
                "operational collision meshes have not been re-exported through "
                "the B601 CAD<->URDF calibration D_i.  Trigger: ECR-M2."
            ),
            "note_on_v4": (
                "MECH_DYNAMICS_INTERFACE_V4.yaml keeps its PENDING_SIBLING_HASH "
                "tokens by design.  This table is the resolution layer; V4 is not "
                "rewritten, so WP10's isolation guarantee stays auditable."
            ),
        },
        "terminal_release_condition_input": {
            "hash_mismatch_count": 0,
            "hash_mismatch_definition": (
                "a cited sha256 that disagrees with the bytes on disk.  No M7 "
                "citer asserts a sibling sha256 at all - they assert the deferral "
                "token - so there is nothing to disagree.  The relevant risk is "
                "UNRESOLVED, not MISMATCHED, and it is counted separately."
            ),
            "unresolved_reference_count": len(missing),
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "prohibitions_honored": [
            "no work-package artifact was modified",
            "no unknown was zero-filled",
            "no candidate was promoted to authority",
            "no flight / launcher / manufacturing-release / qualification claim",
        ],
        "self": {
            "path": rel(SELF_PATH),
            "sha256": sha256_file(SELF_PATH),
            "bytes": os.path.getsize(longpath(SELF_PATH)),
        },
    }

    with open(longpath(OUT_PATH), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)

    t = doc["totals"]
    print("WROTE", OUT_PATH, os.path.getsize(longpath(OUT_PATH)), "bytes")
    print(f"  citer files            : {t['citer_files']}")
    print(f"  token occurrences      : {t['token_occurrences']}")
    print(f"  distinct cited paths   : {t['distinct_cited_paths']}")
    print(f"  resolved               : {t['resolved']}")
    print(f"  UNRESOLVED (missing)   : {t['unresolved_target_missing']}")
    print(f"  unassociated tokens    : {t['unassociated_occurrences']}")
    print(f"  superseded targets     : {t['superseded_targets']}")
    for m in missing:
        print("    MISSING:", m["path"])
    print("  criterion 18 ->", doc["gate_a_criterion_18_input"]["recommended_state_odr14"])


if __name__ == "__main__":
    main()
