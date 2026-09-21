"""Offline acceptance checks for the fail-closed ANCF certification package."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

import yaml


CERT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CERT_ROOT.parents[1]
RESULTS = CERT_ROOT / "results"
TABLES = CERT_ROOT / "tables"
REPORT = CERT_ROOT / "docs" / "ANCF_CERTIFICATION_REPORT_ZH.md"
TEST_REPORT = CERT_ROOT / "tests" / "test_report.md"
NUMERIC_METRICS = (
    "tip_peak_m", "root_moment_peak_Nm", "strain_energy_peak_J",
    "total_energy_peak_J",
)


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def test_config_contract():
    config = yaml.safe_load(
        (CERT_ROOT / "20_engineering" / "config" / "certification_v1.yaml").read_text(
            encoding="utf-8"))
    history = config["historical_rerun"]
    require(config["baseline_commit"] == "6c15395", "wrong frozen baseline")
    require(len(history["cases"]) == len(set(history["cases"])) == 7,
            "historical cases must be seven unique IDs")
    require(history["methods"] == ["Radau", "BDF"],
            "historical solver pair changed")
    require(float(history["max_wall_s_per_attempt"]) == 30.0,
            "historical wall limit changed")
    require(int(history["max_accepted_steps"]) == 100000,
            "historical accepted-step limit changed")
    require(int(history["max_nfev"]) == 2000000,
            "historical RHS-call limit changed")


def test_low_amplitude_anchors():
    rows = read_csv(RESULTS / "low_amplitude_runs.csv")
    required = [row for row in rows if row["required_anchor"] == "1"]
    diagnostic = [row for row in rows if row["required_anchor"] == "0"]
    expected = {(str(n), method) for n in (2, 4, 8)
                for method in ("Radau", "BDF")}
    require(len(rows) == 14, "anchor matrix must contain 14 runs")
    require({(row["n_elements"], row["method"]) for row in required} == expected,
            "required 3-mesh x 2-solver matrix incomplete")
    require(len(diagnostic) == 8, "diagnostic anchor count must be eight")
    require(all(row["classification"] == "COMPLETED" for row in rows),
            "an anchor did not complete")
    modal_max = max(float(row["ancf_modal_trajectory_relative_difference"])
                    for row in required)
    require(modal_max < 0.10, "ANCF-modal required-anchor gate failed")
    for row in rows:
        require(all(row[key] == "0" for key in (
            "training_eligible", "ranking_eligible",
            "safety_evaluation_eligible", "silent_zero")),
            f"diagnostic eligibility leaked: {row['experiment_id']}")
        require(all(math.isfinite(float(row[key])) for key in NUMERIC_METRICS),
                f"non-finite anchor metric: {row['experiment_id']}")


def test_cross_solver_diagnostic():
    rows = read_csv(TABLES / "cross_solver_differences.csv")
    gate = read_json(RESULTS / "gate_summary.json")
    require(len(rows) == 6, "expected six Radau/BDF diagnostic pairs")
    require(sum(int(row["strict_lt_5pct"]) for row in rows) == 5,
            "diagnostic pass/fail distribution changed")
    maximum = max(float(row["max_relative_difference"]) for row in rows)
    require(math.isclose(
        maximum, float(gate["cross_solver_diagnostic"]["max_relative_difference"]),
        rel_tol=1e-12), "cross-solver maximum disagrees with gate")
    require(maximum >= 0.05, "5% diagnostic exception was hidden")
    exception = [row for row in rows
                 if row["impulse_mode"] == "rectangular_pulse"
                 and math.isclose(float(row["pulse_duration_s"]), 0.01)]
    require(len(exception) == 1 and exception[0]["strict_lt_5pct"] == "0",
            "10 ms pulse exception is not preserved")
    require(gate["cross_solver_diagnostic"]["all_lt_5pct"] is False,
            "diagnostic cross-solver gate was falsely promoted")


def test_discretization_trends():
    rows = read_csv(TABLES / "discretization_trends.csv")
    newmark = sorted(
        read_csv(TABLES / "newmark_timestep_trend.csv"),
        key=lambda row: float(row["time_step_s"]), reverse=True)
    mesh = [float(row["relative_change"]) for row in rows
            if row["study_axis"] == "mesh"]
    pulse = [float(row["relative_change"]) for row in rows
             if row["study_axis"] == "impulse_duration_to_jump"]
    time_errors = [float(row["trajectory_relative_difference"])
                   for row in newmark]
    require(len(mesh) == 2 and mesh[1] < mesh[0],
            "mesh refinement trend is not observable")
    require(len(pulse) == 2 and pulse[1] < pulse[0],
            "finite-pulse trend does not approach velocity jump")
    require(len(time_errors) == 3 and all(
        later < earlier for earlier, later in zip(time_errors, time_errors[1:])),
        "Newmark fixed-step trend is not monotone")
    require(read_json(RESULTS / "gate_summary.json")["discretization"]["gate_pass"],
            "discretization gate disagrees with tables")


def test_historical_fail_closed():
    attempts = read_csv(RESULTS / "historical_attempts.csv")
    summary = read_csv(RESULTS / "historical_classification.csv")
    config = yaml.safe_load(
        (CERT_ROOT / "20_engineering" / "config" / "certification_v1.yaml").read_text(
            encoding="utf-8"))
    expected_pairs = {(case_id, method)
                      for case_id in config["historical_rerun"]["cases"]
                      for method in config["historical_rerun"]["methods"]}
    require(len(attempts) == 14, "historical attempt count must be 14")
    require({(row["case_id"], row["method"]) for row in attempts} == expected_pairs,
            "historical case/solver matrix incomplete")
    require(len(summary) == 7, "historical summary count must be seven")
    require(all(row["classification"] not in ("", "UNCLASSIFIED")
                and row["specific_classification"] not in ("", "UNCLASSIFIED")
                for row in attempts), "an attempt is unclassified")
    completed = [row for row in attempts if row["classification"] == "COMPLETED"]
    require(len(completed) == 1, "formal history should preserve one Radau completion")
    for row in attempts:
        require(all(row[key] == "0" for key in (
            "training_eligible", "ranking_eligible",
            "safety_evaluation_eligible", "silent_zero")),
            f"historical eligibility leaked: {row['case_id']} {row['method']}")
        if row["classification"] != "COMPLETED":
            require(all(row[metric] == "" for metric in NUMERIC_METRICS),
                    f"failed attempt contains physical metric: {row['case_id']} {row['method']}")
    require(all(row["current_classified"] == "1" for row in summary),
            "not all seven cases are classified")
    require(sum(int(row["classification_reproduced"]) for row in summary) == 6,
            "old broad-class reproduction count changed")
    require(all(row["state"] == "UNKNOWN" for row in summary),
            "a history case escaped UNKNOWN without paired convergence")
    require(all(row[key] == "0" for row in summary for key in (
        "training_eligible", "ranking_eligible",
        "safety_evaluation_eligible", "silent_zero")),
        "summary eligibility or silent-zero contract violated")


def test_final_gate_fail_closed():
    gate = read_json(RESULTS / "gate_summary.json")
    final = gate["final_candidate_cross_solver"]
    require(gate["overall"] == "REPEAT_ANCF_CERTIFICATION",
            "overall must remain REPEAT")
    require(final["available"] is False and final["gate_pass"] is False,
            "missing finalist was promoted")
    require(final["max_relative_difference"] is None,
            "missing finalist must have a null comparison")
    require(gate["historical"]["classified"] == 7
            and gate["historical"]["unknown"] == 7
            and gate["historical"]["unclassified"] == 0,
            "historical gate counts changed")
    require(gate["low_amplitude"]["gate_pass"] is True,
            "required low-amplitude gate should pass")


def test_frozen_input_integrity():
    inventory = read_json(RESULTS / "source_inventory.json")
    legacy = [item for item in inventory["files"]
              if item["matches_frozen_baseline"] is not None]
    require(len(legacy) == 6, "six frozen legacy inputs expected")
    require(all(item["matches_frozen_baseline"] is True for item in legacy),
            "a legacy input differs from baseline")
    config_items = [item for item in inventory["files"]
                    if item["path"].endswith("certification_v1.yaml")]
    require(len(config_items) == 1
            and config_items[0]["matches_frozen_baseline"] is None,
            "new config was misrepresented as a frozen input")
    protection = inventory["viz_protection_manifest"]
    require(protection["entries"] == 22
            and protection["manifest_declared_source_matches"] == 22
            and protection["manifest_declared_snapshot_matches"] == 22,
            "VIZ manifest declarations changed")
    require(protection["current_source_files_present"] == 0
            and protection["frozen_snapshot_blob_expected_matches"] == 14
            and protection["independent_recheck_all_pass"] is False,
            "VIZ baseline reproducibility discrepancy was hidden or changed")
    baseline = inventory["baseline_commit"]
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, "HEAD"],
        cwd=REPO_ROOT, check=False).returncode
    require(ancestor == 0, "certification branch is not based on frozen commit")
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=REPO_ROOT, text=True)
    paths = []
    for line in status.splitlines():
        path = line[3:].split(" -> ")[-1].replace("\\", "/")
        paths.append(path)
    require(all(path.startswith("30_simulation/e15_ancf_certification/") for path in paths),
            f"write escaped dedicated tree: {paths}")


def test_manifest_hashes_and_timing():
    manifest = read_json(RESULTS / "run_manifest.json")
    timing = read_json(RESULTS / "timing_summary.json")
    require(manifest["mode"] == "finalize", "last package action must be offline finalize")
    require(manifest["git_scope"]["scope_pass"] is True,
            "manifest scope gate failed")
    require(math.isclose(
        float(timing["total_formal_invocation_s"]),
        float(timing["anchor_invocation_s"]) + float(timing["historical_invocation_s"]),
        rel_tol=1e-12), "formal runtime total is inconsistent")
    require(timing["uncontrolled_prototypes_excluded"] is True,
            "timing provenance must exclude prototypes")
    required = {
        "results/gate_summary.json", "results/source_inventory.json",
        "results/timing_summary.json", "results/low_amplitude_runs.csv",
        "results/historical_attempts.csv",
        "results/historical_classification.csv",
        "tables/cross_solver_differences.csv",
        "tables/discretization_trends.csv",
        "tables/newmark_timestep_trend.csv",
        "docs/ANCF_CERTIFICATION_REPORT_ZH.md",
    }
    require(required.issubset(manifest["outputs"]),
            "manifest is missing required output hashes")
    for relative, expected in manifest["outputs"].items():
        path = CERT_ROOT / relative
        require(path.exists(), f"manifest output missing: {relative}")
        require(sha256_file(path) == expected,
                f"manifest hash mismatch: {relative}")


def test_report_semantics():
    text = REPORT.read_text(encoding="utf-8")
    for required in (
        "最终裁决：**REPEAT_ANCF_CERTIFICATION**",
        "7/7", "UNKNOWN", "生成时“源/快照 22/22”声明",
        "存在 0/22", "是 14/22", "不把表内声明冒充当前独立复核通过",
        "192.62 s", "不得进入 E2/G3/HIL", "5.63735%",
        "资源纪律更正", "每工况一个独立可杀子进程",
    ):
        require(required in text, f"report is missing: {required}")
    require("最终裁决：**PASS_ANCF_CERTIFICATION**" not in text,
            "report falsely claims overall PASS")


TESTS = (
    ("config_contract", test_config_contract),
    ("low_amplitude_anchors", test_low_amplitude_anchors),
    ("cross_solver_diagnostic", test_cross_solver_diagnostic),
    ("discretization_trends", test_discretization_trends),
    ("historical_fail_closed", test_historical_fail_closed),
    ("final_gate_fail_closed", test_final_gate_fail_closed),
    ("frozen_input_integrity", test_frozen_input_integrity),
    ("manifest_hashes_and_timing", test_manifest_hashes_and_timing),
    ("report_semantics", test_report_semantics),
)


def main():
    rows = []
    for name, test in TESTS:
        try:
            test()
            rows.append((name, "PASS", ""))
        except Exception as exc:  # collect every independent check
            rows.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))
    passed = sum(status == "PASS" for _, status, _ in rows)
    lines = [
        "# ANCF 认证离线验收测试",
        "",
        f"结果：**{passed}/{len(rows)} PASS**",
        "",
        "| 检查 | 结果 | 说明 |",
        "|---|---:|---|",
    ]
    for name, status, detail in rows:
        safe = detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{name}` | {status} | {safe} |")
    lines.extend([
        "",
        "该测试只读取冻结输入和已有数值结果；不启动 ANCF 长时积分。",
        "",
    ])
    TEST_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "passed": passed, "total": len(rows),
        "overall": "PASS" if passed == len(rows) else "FAIL",
        "results": [
            {"name": name, "status": status, "detail": detail}
            for name, status, detail in rows],
    }, ensure_ascii=False, indent=2))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
