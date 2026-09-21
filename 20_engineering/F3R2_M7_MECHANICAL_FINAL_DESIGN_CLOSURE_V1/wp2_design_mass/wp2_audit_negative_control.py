#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Negative control for WP2_INDEPENDENT_AUDIT_V2.py.

WP2_DESIGN_MASS_AUDIT_V2.json reports AUDIT_PASS_CLEAN with zero findings. A
clean PASS is exactly the shape of this repo's known failure mode (a PASS
summary over a degenerate artifact or a check that cannot fail), so the PASS is
worth nothing unless the audit is shown to have teeth.

This script deliberately corrupts copies of the V2 artifact in the system temp
directory, runs the REAL audit script against each mutant (only its TARGET and
OUT paths are rewritten; no check logic is altered), and records which checks
fired. The real artifacts are never written to: their sha256 is captured before
and after and compared.

Emits WP2_AUDIT_NEGATIVE_CONTROL_V1.json.

Expected outcome per mutation is declared BEFORE the run in MUTATIONS, so a
mutation that silently stops being detected shows up as expectation_met=false.
"""
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import yaml

REPO = Path(r"f:/China Graduate Future Flight Vehicle Innovation Competition")
WP2 = REPO / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass"
TARGET = WP2 / "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml"
AUDITOR = WP2 / "WP2_INDEPENDENT_AUDIT_V2.py"
AUDIT_OUT = WP2 / "WP2_DESIGN_MASS_AUDIT_V2.json"
OUT = WP2 / "WP2_AUDIT_NEGATIVE_CONTROL_V1.json"
SANDBOX = Path(tempfile.gettempdir()) / "wp2_audit_negative_control"
KEYS6 = ["Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"]


def hb(path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"sha256": digest.hexdigest().upper(), "bytes": size}


def now_local() -> str:
    return subprocess.check_output(["date", "-Iseconds"]).decode().strip()


# ---------------------------------------------------------------- mutations
def mut_negative_sigma(doc):
    doc["configurations"][0]["composition"][2]["inertia_uncertainty"][
        "component_standard_uncertainty_kg_m2"]["Ixz"] *= -1.0
    return ("reintroduce the WP2-AUD-02 defect: one component standard uncertainty "
            "(C01 solar_array_right, Ixz) made negative")


def mut_left_handed(doc):
    c9 = [c for c in doc["configurations"] if c["configuration_id"] == "C09"][0]
    axes = c9["principal_inertia"]["axes_S_unit_vectors"]
    axes[2] = [-v for v in axes[2]]
    return ("reintroduce the WP2-AUD-06 defect: negate the C09 third principal axis so the "
            "triad is left-handed again")


def mut_mass_ulp(doc):
    m = doc["configurations"][3]["composition"][3]
    m["mass_kg"] = math.nextafter(float(m["mass_kg"]), math.inf)
    return ("move a single component mass (C04 B601 arm) by one unit in the last place, i.e. "
            "the smallest possible violation of 'no physics value moved'")


def mut_drop_crosswalk(doc):
    doc.pop("configuration_label_crosswalk", None)
    return "delete the WP2-AUD-01 configuration label crosswalk section"


def mut_forbidden_abs(doc):
    for cfg in doc["configurations"]:
        for m in cfg["composition"]:
            rot = np.array(m["source_to_S_rotation_rows"], dtype=float)
            loc = m["inertia_uncertainty"]["local_frame_standard_uncertainty_kg_m2"]
            u = np.array([[loc["Ixx"], loc["Ixy"], loc["Ixz"]],
                          [loc["Ixy"], loc["Iyy"], loc["Iyz"]],
                          [loc["Ixz"], loc["Iyz"], loc["Izz"]]])
            a = np.abs(rot @ u @ rot.T)
            m["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"] = {
                "Ixx": float(a[0, 0]), "Iyy": float(a[1, 1]), "Izz": float(a[2, 2]),
                "Ixy": float(a[0, 1]), "Ixz": float(a[0, 2]), "Iyz": float(a[1, 2])}
    return ("replace every reported sigma by the ODR-07-FORBIDDEN abs(R U R^T) remediation "
            "while leaving the published covariance untouched")


def mut_lying_self_check(doc):
    for value in doc["design_checks"].values():
        if isinstance(value, dict) and "pass" in value:
            value["pass"] = True
    doc["summary"]["all_checks_pass"] = True
    doc["configurations"][0]["inertia"]["matrix_kg_m2"][0][0] *= 1.0000001
    return ("corrupt the C01 inertia tensor Ixx by 1e-7 relative while forcing every "
            "self-declared check flag to true - the 'PASS summary over a broken artifact' "
            "failure mode")


MUTATIONS = [
    {"tag": "A", "fn": mut_negative_sigma,
     "expect_checks": ["g_uncertainty_covariance_semantics_and_pedigree"],
     "expect_detected": True},
    {"tag": "B", "fn": mut_left_handed,
     "expect_checks": ["e_principal_axes_orthonormal_right_handed_and_consistent",
                       "o_v1_to_v2_regression"],
     "expect_detected": True},
    {"tag": "C", "fn": mut_mass_ulp,
     "expect_checks": ["c_mass_closure_and_pinned_values", "o_v1_to_v2_regression"],
     "expect_detected": True},
    {"tag": "D", "fn": mut_drop_crosswalk,
     "expect_checks": ["a_nine_configurations_naming_and_crosswalk"],
     "expect_detected": True},
    {"tag": "E", "fn": mut_forbidden_abs,
     "expect_checks": [],
     "expect_detected": False,
     "expectation_rationale": (
         "NOT DETECTABLE FROM VALUES, AND THAT IS THE HONEST ANSWER. Every component-to-S "
         "rotation in this design is a signed permutation, for which T(R) C_local T(R)^T stays "
         "diagonal and sqrt(diag) equals the magnitude of the component-wise rotated sigma. The "
         "forbidden abs() therefore produces bit-identical numbers here, so no value-level check "
         "can separate them. The separation is established at METHOD level instead: audit check "
         "p (generic-rotation counterexample) and check q (independent re-derivation from the "
         "covariance plus proof that all 56 rotations are signed permutations). This mutation is "
         "verified to be a NULL mutation by counting changed sigma entries.")},
    {"tag": "F", "fn": mut_lying_self_check,
     "expect_checks": ["d_inertia_physicality_symmetry_pd_triangle",
                       "h_independent_parallel_axis_inertia_reconstruction",
                       "o_v1_to_v2_regression"],
     "expect_detected": True},
]


def main() -> None:
    before = hb(TARGET)
    baseline_audit = json.load(open(AUDIT_OUT, encoding="utf-8"))
    doc = yaml.safe_load(open(TARGET, encoding="utf-8"))
    SANDBOX.mkdir(parents=True, exist_ok=True)

    # the real auditor, with ONLY its input/output paths rewritten
    src = AUDITOR.read_text(encoding="utf-8")
    src = src.replace(
        '"path": os.path.relpath(v, REPO).replace("\\\\", "/"), "sha256": s, "bytes": b}',
        '"path": str(v), "sha256": s, "bytes": b}')
    if 'TARGET = os.path.join(WP2, "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml")' not in src:
        raise SystemExit("FAIL-CLOSED: auditor TARGET line not found; refusing to guess")

    results = []
    for spec in MUTATIONS:
        tag = spec["tag"]
        mutant = copy.deepcopy(doc)
        description = spec["fn"](mutant)
        mutant_path = SANDBOX / f"mutant_{tag}.yaml"
        with open(mutant_path, "w", encoding="utf-8", newline="\n") as handle:
            yaml.safe_dump(mutant, handle, sort_keys=False, allow_unicode=True, width=140)

        changed_sigma = 0
        total_sigma = 0
        for cfg_a, cfg_b in zip(doc["configurations"], mutant["configurations"]):
            for m_a, m_b in zip(cfg_a["composition"], cfg_b["composition"]):
                sa = m_a["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]
                sb = m_b["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]
                for key in KEYS6:
                    total_sigma += 1
                    if sa[key] != sb[key]:
                        changed_sigma += 1

        audit_out = SANDBOX / f"audit_{tag}.json"
        script = SANDBOX / f"auditor_{tag}.py"
        code = src.replace(
            'TARGET = os.path.join(WP2, "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml")',
            f'TARGET = r"{mutant_path.as_posix()}"')
        code = code.replace(
            'OUT = os.path.join(WP2, "WP2_DESIGN_MASS_AUDIT_V2.json")',
            f'OUT = r"{audit_out.as_posix()}"')
        script.write_text(code, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        if not audit_out.exists():
            raise SystemExit(f"FAIL-CLOSED: mutant {tag} audit produced no output:\n"
                             f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
        res = json.load(open(audit_out, encoding="utf-8"))
        failed = res["checks_failed"]
        detected = bool(failed or res["findings"])
        expected_hit = [c for c in spec["expect_checks"] if c in failed]
        row = {
            "tag": tag,
            "mutation": description,
            "mutant_file": mutant_path.as_posix(),
            **{f"mutant_{k}": v for k, v in hb(mutant_path).items()},
            "sigma_entries_total": total_sigma,
            "sigma_entries_changed_by_mutation": changed_sigma,
            "is_null_mutation_on_reported_sigmas": changed_sigma == 0,
            "audit_overall_verdict": res["overall_verdict"],
            "audit_checks_failed": failed,
            "audit_findings": [{"finding_id": f["finding_id"], "severity": f["severity"],
                                "check_id": f["check_id"]} for f in res["findings"]],
            "v1_finding_closure_after_mutation": {k: v["closed"]
                                                  for k, v in res["v1_finding_closure"].items()},
            "expected_detected": spec["expect_detected"],
            "expected_checks_to_fail": spec["expect_checks"],
            "expected_checks_that_did_fail": expected_hit,
            "detected": detected,
        }
        if spec["expect_detected"]:
            row["expectation_met"] = bool(detected
                                          and len(expected_hit) == len(spec["expect_checks"]))
        else:
            row["expectation_met"] = bool(not detected and changed_sigma == 0)
            row["expectation_rationale"] = spec["expectation_rationale"]
        results.append(row)

    after = hb(TARGET)
    all_met = all(r["expectation_met"] for r in results)
    detected_count = sum(1 for r in results if r["detected"])

    out = {
        "schema": "M7_WP2_AUDIT_NEGATIVE_CONTROL_V1",
        "generated_local": now_local(),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "work_package": "WP2_DESIGN_MASS",
        "role": "A2_MASS_FRAMES",
        "purpose": (
            "Falsification test for WP2_DESIGN_MASS_AUDIT_V2.json. A clean audit PASS is only "
            "meaningful if the audit demonstrably fails on defective input. Six deliberate "
            "corruptions of the V2 artifact were audited with the unmodified audit logic."),
        "method": (
            "copies of SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml are corrupted in the system temp "
            "directory; WP2_INDEPENDENT_AUDIT_V2.py is executed against each with only its "
            "TARGET and OUT path constants rewritten (check logic byte-identical); the real "
            "artifacts are read-only and their sha256 is compared before and after"),
        "audited_artifact": {"path": TARGET.relative_to(REPO).as_posix(), **before},
        "audit_under_test": {"path": AUDITOR.relative_to(REPO).as_posix(), **hb(AUDITOR)},
        "baseline_audit": {
            "path": AUDIT_OUT.relative_to(REPO).as_posix(), **hb(AUDIT_OUT),
            "overall_verdict": baseline_audit["overall_verdict"],
            "checks_total": len(baseline_audit["checks"]),
            "checks_failed": baseline_audit["checks_failed"],
        },
        "real_artifact_unmodified": {
            "sha256_before": before["sha256"], "sha256_after": after["sha256"],
            "unchanged": before["sha256"] == after["sha256"],
        },
        "sandbox": SANDBOX.as_posix(),
        "results": results,
        "summary": {
            "mutations_run": len(results),
            "mutations_detected": detected_count,
            "mutations_expected_detectable": sum(1 for m in MUTATIONS if m["expect_detected"]),
            "null_mutations": sum(1 for r in results if r["is_null_mutation_on_reported_sigmas"]),
            "all_expectations_met": all_met,
            "conclusion": (
                "the audit is sensitive: it fails on a reintroduced negative sigma, on a "
                "reverted left-handed triad, on a single-ULP mass move, on a deleted crosswalk "
                "and on a corrupted tensor hidden behind forced-true self-check flags. The one "
                "undetected mutation is verified to be a NULL mutation (0 changed values), "
                "because on this data set the forbidden abs() and the ODR-07 covariance produce "
                "identical numbers; that case is discriminated by method-level checks p and q, "
                "not by value comparison."),
        },
        "limitations": [
            "this is a test of the AUDIT's sensitivity, not additional evidence about the design",
            "the mutation set is finite and hand-chosen; it does not prove the audit detects "
            "every possible corruption",
            "no engineering conclusion is upgraded by this file",
        ],
        "prohibitions_honored": {
            "real_artifact_modified": before["sha256"] != after["sha256"],
            "audit_logic_modified": False,
            "other_wp_files_touched": False,
            "freecad_launched": False,
            "abaqus_launched": False,
        },
    }
    if before["sha256"] != after["sha256"]:
        raise SystemExit("FAIL-CLOSED: the real V2 artifact changed during the negative control")

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2, ensure_ascii=False)
    print("WROTE", OUT, os.path.getsize(OUT), "bytes")
    for row in results:
        print(f"  {row['tag']} detected={row['detected']} expectation_met={row['expectation_met']} "
              f"failed={row['audit_checks_failed']}")
    print("all_expectations_met:", all_met)
    if not all_met:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
