"""Offline acceptance suite for the v1 research integration."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Callable


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "70_tools" / "research_dashboard"
HTML = ROOT / "40_evidence" / "artifacts" / "visualization" / "project_visualization_v1_research.html"
V0 = ROOT / "40_evidence" / "artifacts" / "visualization" / "project_visualization_v0.html"
PRE_REORG04_V0_SHA256 = "1f66454100afb0a66e31e042c52c6b2a570801b72217f8709a2b50ca225b3166"
PRE_REORG04_V0_BLOB_SHA256 = "f4647f13d4e8260c3a9271a9fdcb05c143876ae3f81110f7c5e9fd7fa6756a64"
V0_SHA256 = "83c67e63a90e23172c085577e2fb5ef01b2e31d0e812c9729d0a4ba281de57c7"
SYNC_DIGEST = "bd972b6908a821f0c4ade06e80b1cb066cdc13f46e9b6c50c2f23a1504eac0f0"
ALLOWED_VERDICTS = {"CORE_READY_FOR_E2", "REPEAT_CORE", "BLOCKED"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory_fingerprint(path: Path, mode: str) -> bytes:
    data = path.read_bytes()
    if mode == "CANONICAL_LF_TEXT_BYTES":
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if mode == "RAW_FILE_BYTES":
        return data
    raise AssertionError(f"unknown source fingerprint mode: {mode}")


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def read_csv(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def assert_true(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_deterministic_build() -> None:
    sys.path.insert(0, str(HERE))
    from build_research_dashboard import build

    first = build()
    first_bytes = HTML.read_bytes()
    second = build()
    assert_true(first == second, "dashboard SHA-256 differs across two builds")
    assert_true(first_bytes == HTML.read_bytes(), "dashboard bytes differ across two builds")
    manifest = read_json("70_tools/research_dashboard/results/run_manifest.json")
    expected = manifest["artifacts"]["40_evidence/artifacts/visualization/project_visualization_v1_research.html"]
    assert_true(first == expected == sha256(HTML), "dashboard manifest hash mismatch")


def test_v0_path_refrozen_and_tagged() -> None:
    assert_true(sha256(V0) == V0_SHA256, "REORG04-refrozen project_visualization_v0.html changed")
    tag_target = subprocess.check_output(
        ["git", "rev-list", "-n", "1", "viz-gate0-accepted-20260714"], cwd=ROOT, text=True
    ).strip()
    assert_true(tag_target == "6c15395f444f693adad6ff0dfc9a3cfc0b4cf310", "accepted tag moved")
    tagged_v0 = subprocess.check_output(
        ["git", "show", "viz-gate0-accepted-20260714:artifacts/visualization/project_visualization_v0.html"],
        cwd=ROOT,
    )
    # The accepted tag stores canonical LF bytes; the historical manifest keeps
    # the Windows CRLF checkout hash separately as PRE_REORG04_V0_SHA256.
    assert_true(hashlib.sha256(tagged_v0).hexdigest() == PRE_REORG04_V0_BLOB_SHA256, "pre-REORG04 v0 blob provenance changed")


def test_viz_freeze_29_of_29() -> None:
    rows = read_csv("40_evidence/artifacts/visualization/viz_gate0_freeze_manifest_20260714.csv")
    assert_true(len(rows) == 29, f"freeze manifest row count is {len(rows)}, expected 29")
    mismatches = []
    for row in rows:
        path = ROOT / row["path"]
        if not path.is_file() or sha256(path).upper() != row["sha256"].upper():
            mismatches.append(row["path"])
    assert_true(not mismatches, f"freeze hash mismatches: {mismatches}")


def test_viz_snapshot_22_of_22() -> None:
    rows = read_csv("40_evidence/artifacts/visualization/tables/gate_artifact_protection_manifest.csv")
    assert_true(len(rows) == 22, f"snapshot manifest row count is {len(rows)}, expected 22")
    snapshot_mismatches = []
    manifest_mismatches = []
    for row in rows:
        snapshot = ROOT / row["snapshot_path"].replace("\\", "/")
        if not snapshot.is_file() or sha256(snapshot).upper() != row["expected_sha256"].upper():
            snapshot_mismatches.append(row["snapshot_path"])
        if (
            row["actual_sha256"].upper() != row["expected_sha256"].upper()
            or row["match_expected"].lower() != "true"
            or row["snapshot_hash_match"].lower() != "true"
        ):
            manifest_mismatches.append(row["source_rel_path"])
    assert_true(not snapshot_mismatches, f"snapshot hash mismatches: {snapshot_mismatches}")
    assert_true(not manifest_mismatches, f"recorded source-to-snapshot mismatches: {manifest_mismatches}")


def test_viz_asset_paths_45_of_45() -> None:
    rows = read_csv("40_evidence/artifacts/visualization/tables/asset_audit.csv")
    assert_true(len(rows) == 45, f"asset audit row count is {len(rows)}, expected 45")
    missing = []
    for row in rows:
        path = ROOT / row["path"]
        if row["exists"].lower() != "yes" or not path.is_file():
            missing.append(row["asset_id"])
    assert_true(not missing, f"asset paths missing: {missing}")


def test_p0_a_gate_contract() -> None:
    gate = read_json("30_simulation/e15_core_coverage/results/core_gate_check.json")
    assert_true(gate["gate"] == "P0_A_CORE_COVERAGE_PASS", "P0-A evidence gate did not pass")
    assert_true(gate["row_count"] == gate["case_id_unique_count"] == 72, "P0-A is not 72 unique rows")
    assert_true(gate["evidence_missing_count"] == 0, "P0-A EVIDENCE_MISSING is not zero")
    assert_true(gate["safe_candidate_count"] == 0, "P0-A unexpectedly contains a safe candidate")
    assert_true(gate["state_counts"] == {
        "CORE_SAFE_FLEX_UNKNOWN": 0,
        "CORE_SAFE_FLEX_VALIDATED": 0,
        "CORE_UNSAFE": 6,
        "EVIDENCE_MISSING": 0,
        "GEOMETRY_INVALID": 66,
    }, "P0-A five-state accounting changed")


def test_p0_a_no_fake_downstream_zero() -> None:
    rows = read_csv("30_simulation/e15_core_coverage/results/core_evidence_72cases.csv")
    invalid = [row for row in rows if row["core_chain_applicable"] == "0"]
    assert_true(len(invalid) == 66, "P0-A invalid-row count changed")
    for row in invalid:
        assert_true(row["downstream_numeric_semantics"] == "NOT_APPLICABLE_NOT_MISSING", row["case_id"])
        assert_true(row["capture_impulse_stage_status"] == "NOT_RUN_DUE_TO_UPSTREAM_IK", row["case_id"])
        assert_true(row["capture_impulse_linear_norm_Ns"] == "", f"fake downstream value: {row['case_id']}")
        assert_true(row["post_capture_angular_velocity_dps"] == "", f"fake downstream value: {row['case_id']}")


def test_p0_b_fail_closed_contract() -> None:
    gate = read_json("30_simulation/e15_ancf_certification/results/gate_summary.json")
    history = read_csv("30_simulation/e15_ancf_certification/results/historical_classification.csv")
    assert_true(gate["overall"] == "REPEAT_ANCF_CERTIFICATION", "ANCF verdict changed")
    assert_true(gate["historical"]["total"] == gate["historical"]["unknown"] == 7, "ANCF 7/7 UNKNOWN changed")
    assert_true(gate["historical"]["silent_zero"] == 0, "ANCF silent zero detected")
    assert_true(gate["final_candidate_cross_solver"]["available"] is False, "final candidate was fabricated")
    assert_true(len(history) == 7 and all(row["state"] == "UNKNOWN" for row in history), "history not all UNKNOWN")
    assert_true(all(row["safety_evaluation_eligible"].strip().lower() in {"0", "false"} for row in history), "UNKNOWN case became eligible")


def test_p0_b_diagnostics_honest() -> None:
    gate = read_json("30_simulation/e15_ancf_certification/results/gate_summary.json")
    assert_true(gate["low_amplitude"]["required_completed_runs"] == gate["low_amplitude"]["required_runs"] == 6, "required anchors incomplete")
    assert_true(gate["low_amplitude"]["max_ancf_modal_trajectory_relative_difference"] < 0.001, "low-amplitude trajectory check regressed")
    assert_true(gate["cross_solver_diagnostic"]["max_relative_difference"] > 0.05, "repeat-driving diagnostic was hidden")
    assert_true(gate["cross_solver_diagnostic"]["all_lt_5pct"] is False, "cross-solver diagnostic incorrectly passes")


def test_p0_c_gate_contract() -> None:
    gate = read_json("30_simulation/e16_sync_capture/results/gate_check.json")
    accounting = gate["case_accounting"]
    assert_true(accounting["terminal_cases"] == 216, "P0-C terminal count changed")
    assert_true(accounting["dynamic_evaluated_cases"] == 18, "P0-C dynamic count changed")
    assert_true(accounting["upstream_rejected_cases"] == 198, "P0-C upstream count changed")
    assert_true(18 + 198 == 216, "P0-C accounting identity failed")
    assert_true(gate["formal_safe_cases"] == 0, "P0-C unexpectedly contains SAFE")
    assert_true(gate["determinism"]["rows_sha256"] == SYNC_DIGEST, "P0-C digest changed")


def test_p0_c_no_fake_downstream_zero() -> None:
    rows = read_csv("30_simulation/e16_sync_capture/results/sync_capture_216.csv")
    assert_true(len(rows) == len({row["case_id"] for row in rows}) == 216, "P0-C IDs are not 216 unique rows")
    rejected = [row for row in rows if row["dynamics_status"] != "EVALUATED"]
    assert_true(len(rejected) == 198, "P0-C rejected count changed")
    for row in rejected:
        assert_true(row["post_capture_omega_dps"] == "N/A", f"downstream rate not N/A: {row['case_id']}")
        assert_true(row["capture_impulse_linear_norm_Ns"] == "N/A", f"downstream impulse not N/A: {row['case_id']}")
        assert_true(row["classification"] == "GEOMETRY_INVALID", row["case_id"])


def test_campaign_discriminator_and_grain() -> None:
    rows = read_csv("70_tools/research_dashboard/tables/unified_campaign_map.csv")
    counts = Counter(row["campaign_discriminator"] for row in rows)
    assert_true(len(rows) == 288, "unified map is not 72 + 216 rows")
    assert_true(counts == {"CORE_COVERAGE": 72, "SYNCHRONIZED_CAPTURE": 216}, f"campaigns conflated: {counts}")
    core = [row for row in rows if row["campaign_discriminator"] == "CORE_COVERAGE"]
    assert_true(all(row["alpha"] == "N/A_NOT_APPLICABLE" for row in core), "P0-A was assigned synthetic alpha")


def test_low_impulse_pareto_and_selection() -> None:
    rows = read_csv("70_tools/research_dashboard/tables/sync_low_impulse_pareto.csv")
    front = [row for row in rows if row["strict_low_impulse_pareto"] == "true"]
    assert_true(len(rows) == 18 and len(front) == 1, "strict Pareto front changed")
    selected = front[0]
    assert_true(selected["case_id"] == "P1_tc00_v05mm_pose_6d_a1p0", "G2-Sync selection changed")
    assert_true(float(selected["alpha"]) == 1.0, "G2-Sync alpha is not 1")
    assert_true(selected["classification"] == "CORE_UNSAFE", "unsafe selection was relabeled")
    assert_true(selected["safe_claim_permitted"] == "false", "safe claim became permitted")


def test_case_r_case_f_separation() -> None:
    summary = read_json("70_tools/research_dashboard/results/research_integration_summary.json")
    assert_true("Rigid-body main line" in summary["case_models"]["case_r"], "Case R definition missing")
    assert_true("Flexible extension" in summary["case_models"]["case_f"], "Case F definition missing")
    assert_true("UNKNOWN" in summary["case_models"]["case_f"], "Case F UNKNOWN boundary lost")


def test_unique_verdict_and_authorization() -> None:
    summary = read_json("70_tools/research_dashboard/results/research_integration_summary.json")
    verdict = summary["final_verdict"]
    assert_true(verdict in ALLOWED_VERDICTS, f"invalid verdict: {verdict}")
    assert_true(verdict == "REPEAT_CORE", f"evidence does not support verdict: {verdict}")
    assert_true(all(value is False for value in summary["next_gate"]["authorization"].values()), "later stage was authorized")
    serialized = json.dumps(summary, sort_keys=True)
    assert_true("CORE_READY_FOR_E2" not in serialized and '"BLOCKED"' not in serialized, "multiple verdicts emitted")


def test_source_inventory_and_superseded_viz_note() -> None:
    inventory = read_json("70_tools/research_dashboard/results/input_source_inventory.json")["sources"]
    assert_true(len(inventory) >= 18, "source inventory is incomplete")
    for source in inventory:
        path = ROOT / source["path"]
        assert_true(path.is_file(), f"missing source: {source['path']}")
        fingerprint = inventory_fingerprint(path, source["fingerprint_mode"])
        assert_true(hashlib.sha256(fingerprint).hexdigest() == source["sha256"], f"source hash mismatch: {source['path']}")
        assert_true(len(fingerprint) == source["size_bytes"], f"source fingerprint size mismatch: {source['path']}")
    summary = read_json("70_tools/research_dashboard/results/research_integration_summary.json")
    note = summary["viz_gate_0"]["superseded_note"]
    assert_true(all(commit in note for commit in ("e765194", "86d50d1", "1cc3c2f")), "VIZ portability correction not recorded")
    assert_true(summary["viz_gate_0"]["portability_status"] == "CURRENT_PASS", "old VIZ note left as current blocker")


def test_manifest_artifact_hashes() -> None:
    manifest = read_json("70_tools/research_dashboard/results/run_manifest.json")
    mismatches = []
    for relative, expected in manifest["artifacts"].items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            mismatches.append(relative)
    assert_true(not mismatches, f"integration artifact hash mismatches: {mismatches}")


def test_html_contract_offline_and_interactive() -> None:
    text = HTML.read_text(encoding="utf-8")
    for required in (
        "Candidate Compare", "Why Not Safe", "Solver Diagnostics", "Research Campaign",
        'id="sceneCanvas"', 'id="paretoCanvas"', 'id="campaignFilter"', 'id="sourceRows"',
        "N/A", "UNKNOWN", "EVIDENCE_MISSING", "NOT AUTHORIZED", "REPEAT_CORE", "非物理轨迹",
        "speedNorm", "alphaSync", "selected.initial_linear_impulse_Ns", "selected.initial_angular_impulse_Nms",
    ):
        assert_true(required in text, f"HTML contract missing: {required}")
    assert_true("冻结候选驱动的三维投影与时序回放" not in text, "dashboard overclaims a physical evidence replay")
    assert_true(not re.search(r"https?://", text, flags=re.IGNORECASE), "dashboard contains network URL")
    assert_true(not re.search(r"<script[^>]+src=", text, flags=re.IGNORECASE), "dashboard has external script")
    link_targets = re.findall(r'<link[^>]+href="([^"]+)"', text, flags=re.IGNORECASE)
    assert_true(all(target.startswith("data:") for target in link_targets), "dashboard has external link dependency")
    payload_match = re.search(r'<script id="research-data" type="application/json">(.*?)</script>', text, flags=re.DOTALL)
    assert_true(payload_match is not None, "embedded evidence payload missing")
    payload = json.loads(payload_match.group(1))
    assert_true(len(payload["campaign_rows"]) == 288, "HTML does not embed all campaign rows")
    assert_true(len(payload["candidates"]) == 18, "HTML candidate payload changed")
    assert_true(payload["summary"]["final_verdict"] == "REPEAT_CORE", "HTML verdict mismatch")


TESTS: list[tuple[str, Callable[[], None]]] = [
    ("deterministic_build", test_deterministic_build),
    ("v0_path_refrozen_and_tagged", test_v0_path_refrozen_and_tagged),
    ("viz_freeze_29_of_29", test_viz_freeze_29_of_29),
    ("viz_snapshot_22_of_22", test_viz_snapshot_22_of_22),
    ("viz_asset_paths_45_of_45", test_viz_asset_paths_45_of_45),
    ("p0_a_gate_contract", test_p0_a_gate_contract),
    ("p0_a_no_fake_downstream_zero", test_p0_a_no_fake_downstream_zero),
    ("p0_b_fail_closed_contract", test_p0_b_fail_closed_contract),
    ("p0_b_diagnostics_honest", test_p0_b_diagnostics_honest),
    ("p0_c_gate_contract", test_p0_c_gate_contract),
    ("p0_c_no_fake_downstream_zero", test_p0_c_no_fake_downstream_zero),
    ("campaign_discriminator_and_grain", test_campaign_discriminator_and_grain),
    ("low_impulse_pareto_and_selection", test_low_impulse_pareto_and_selection),
    ("case_r_case_f_separation", test_case_r_case_f_separation),
    ("unique_verdict_and_authorization", test_unique_verdict_and_authorization),
    ("source_inventory_and_superseded_viz_note", test_source_inventory_and_superseded_viz_note),
    ("manifest_artifact_hashes", test_manifest_artifact_hashes),
    ("html_contract_offline_and_interactive", test_html_contract_offline_and_interactive),
]


def write_report(results: list[tuple[str, str, str]]) -> None:
    passed = sum(status == "PASS" for _, status, _ in results)
    lines = [
        "# Research integration offline acceptance",
        "",
        f"Result: **{passed}/{len(results)} PASS**",
        "",
        "| Check | Result | Detail |",
        "|---|---:|---|",
    ]
    for name, status, detail in results:
        lines.append(f"| `{name}` | {status} | {detail.replace('|', '/')} |")
    lines.extend(["", "The suite performs no long ANCF integration and does not authorize E2, G3, or HIL.", ""])
    (HERE / "tests" / "test_report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    (HERE / "tests" / "test_results.json").write_text(
        json.dumps(
            {"passed": passed, "total": len(results), "overall": "PASS" if passed == len(results) else "FAIL", "results": [
                {"name": name, "status": status, "detail": detail} for name, status, detail in results
            ]},
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    results: list[tuple[str, str, str]] = []
    for name, function in TESTS:
        try:
            function()
        except Exception as exc:  # noqa: BLE001 - report every gate failure
            results.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        else:
            results.append((name, "PASS", ""))
            print(f"PASS {name}")
    write_report(results)
    passed = sum(status == "PASS" for _, status, _ in results)
    print(json.dumps({"passed": passed, "total": len(results), "overall": "PASS" if passed == len(results) else "FAIL"}, sort_keys=True))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
