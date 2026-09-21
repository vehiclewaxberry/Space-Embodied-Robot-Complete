"""Final machine gate for the competition convergence evidence package.

The gate re-verifies frozen inputs, tests, deterministic replay records,
assembly-interface classification, ground-component stop state, and the
reader-facing report/PPT/video package.  It never runs a solver, emits a
command, or grants downstream authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from evidence_contract import (
    EvidenceError,
    deterministic_json_bytes,
    load_and_verify,
)


SCHEMA = "competition-convergence-gate-v1"
READY = "COMPETITION_DEMO_READY"
REPEAT = "COMPETITION_DEMO_REPEAT"
BLOCKED = "COMPETITION_DEMO_BLOCKED"
ASM_VERDICTS = {
    "ASM00_INTERFACE_QUALIFIED_WITH_PROVISIONAL_PARAMS",
    "ASM00_REPEAT_GEOMETRY",
    "ASM00_BLOCKED_BY_MISSING_PARAMETERS",
}
EXPECTED_ACTIONS = {
    "A_low": ("EXECUTE", False),
    "B_anchor": ("ABORT", False),
    "C_transition": ("MODIFY", False),
}
REQUIRED_RESEARCH_FILES = (
    "10_research/competition_convergence/mission_demo_contract.yaml",
    "10_research/competition_convergence/three_scenario_manifest.yaml",
    "10_research/competition_convergence/competition_claim_evidence_matrix.csv",
    "10_research/competition_convergence/digital_twin_replay_plan.md",
    "10_research/competition_convergence/hardware_component_plan.md",
    "10_research/competition_convergence/launch_manifest.md",
)
REQUIRED_REPLAY_FILES = (
    "replay_manifest.json",
    "scenario_A_low.json",
    "scenario_B_anchor.json",
    "scenario_C_transition.json",
)
REQUIRED_REPORT_ANCHORS = (
    "COMPETITION_DEMO_READY",
    "ASM00_BLOCKED_BY_MISSING_PARAMETERS",
    "A_low",
    "EXECUTE",
    "B_anchor",
    "ABORT",
    "C_transition",
    "MODIFY",
    "OFFLINE",
    "NO COMMAND OUTPUT",
    "_WITH_PROVISIONAL_PARAMS",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def repo_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {relative}") from exc
    return candidate


def file_record(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "raw_sha256": sha256(path),
    }


def inspect_pptx(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("PPTX missing")
    if path.stat().st_size < 100_000:
        raise ValueError("PPTX is unexpectedly small")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "ppt/presentation.xml" not in names:
            raise ValueError("PPTX lacks ppt/presentation.xml")
        slides = sorted(
            name
            for name in names
            if re.fullmatch(r"ppt/slides/slide[0-9]+\.xml", name)
        )
    if len(slides) != 9:
        raise ValueError(f"PPTX slide count {len(slides)} != 9")
    return {
        "slide_count": len(slides),
        "bytes": path.stat().st_size,
        "raw_sha256": sha256(path),
    }


def inspect_png(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"invalid PNG: {path}")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (1280, 720):
        raise ValueError(f"{path.name}: dimensions {(width, height)} != (1280, 720)")
    return {
        "width": width,
        "height": height,
        "bytes": len(data),
        "raw_sha256": hashlib.sha256(data).hexdigest(),
    }


def inspect_video(path: Path, ffprobe: str | None) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("MP4 missing")
    probe = (
        ffprobe
        or os.environ.get("FFPROBE_PATH")
        or shutil.which("ffprobe")
        or r"F:\ffmpeg-master-latest-win64-gpl-shared\bin\ffprobe.exe"
    )
    if not Path(probe).is_file() and not shutil.which(probe):
        raise ValueError(f"ffprobe unavailable: {probe}")
    result = subprocess.run(
        [
            probe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_name,codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise ValueError(f"ffprobe failed: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    video_streams = [
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "video"
    ]
    if len(video_streams) != 1:
        raise ValueError(f"video stream count {len(video_streams)} != 1")
    stream = video_streams[0]
    duration = float(payload.get("format", {}).get("duration", 0.0))
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    if duration < 35.0:
        raise ValueError(f"video duration {duration:.3f} s < 35 s")
    if (width, height) != (1920, 1080):
        raise ValueError(
            f"video dimensions {(width, height)} != (1920, 1080)"
        )
    if stream.get("codec_name") != "h264":
        raise ValueError(f"video codec {stream.get('codec_name')} != h264")
    return {
        "codec": stream["codec_name"],
        "duration_s": duration,
        "frame_rate": stream.get("r_frame_rate"),
        "width": width,
        "height": height,
        "bytes": path.stat().st_size,
        "raw_sha256": sha256(path),
    }


def run_gate(root: Path, ffprobe: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    research = root / "10_research" / "competition_convergence"
    delivery = root / "40_evidence" / "artifacts" / "competition_convergence"
    checks: list[dict[str, Any]] = []
    core_failures: list[str] = []
    delivery_failures: list[str] = []
    assets: dict[str, Any] = {}

    def check(
        check_id: str,
        category: str,
        passed: bool,
        observed: Any,
        required: Any,
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "category": category,
                "status": "PASS" if passed else "FAIL",
                "observed": observed,
                "required": required,
            }
        )
        if not passed:
            target = core_failures if category == "CORE" else delivery_failures
            target.append(check_id)

    for relative in REQUIRED_RESEARCH_FILES:
        path = repo_path(root, relative)
        passed = path.is_file() and path.stat().st_size > 0
        check(
            f"REQUIRED_FILE::{relative}",
            "CORE",
            passed,
            path.stat().st_size if path.is_file() else "MISSING",
            "NONEMPTY_FILE",
        )
        if passed:
            assets[relative] = file_record(root, path)

    live_report: dict[str, Any] | None = None
    try:
        _, _, live_report = load_and_verify(
            research / "mission_demo_contract.yaml",
            research / "three_scenario_manifest.yaml",
            root,
        )
        live_ok = (
            live_report.get("overall") == "PASS"
            and live_report.get("command_emitted") is False
            and live_report.get("git", {}).get("scope_violations") == []
        )
        check(
            "LIVE_EVIDENCE_CONTRACT",
            "CORE",
            live_ok,
            {
                "overall": live_report.get("overall"),
                "scope_violations": live_report.get("git", {}).get(
                    "scope_violations"
                ),
            },
            {"overall": "PASS", "scope_violations": []},
        )
    except (EvidenceError, OSError, ValueError) as exc:
        check(
            "LIVE_EVIDENCE_CONTRACT",
            "CORE",
            False,
            str(exc),
            "STRICT_LIVE_VERIFICATION_PASS",
        )

    stored_verification = research / "results" / "evidence_verification.json"
    try:
        stored_bytes = stored_verification.read_bytes()
        expected_bytes = deterministic_json_bytes(live_report) if live_report else b""
        stored_ok = bool(live_report) and stored_bytes == expected_bytes
        check(
            "STORED_VERIFICATION_MATCHES_LIVE",
            "CORE",
            stored_ok,
            sha256(stored_verification),
            hashlib.sha256(expected_bytes).hexdigest() if expected_bytes else "LIVE_REPORT",
        )
        if stored_verification.is_file():
            relative = stored_verification.relative_to(root).as_posix()
            assets[relative] = file_record(root, stored_verification)
    except OSError as exc:
        check(
            "STORED_VERIFICATION_MATCHES_LIVE",
            "CORE",
            False,
            str(exc),
            "BYTE_IDENTICAL_TO_LIVE_REPORT",
        )

    test_report_path = research / "results" / "test_report.json"
    try:
        tests = load_json(test_report_path)
        tests_ok = (
            tests.get("overall") == "PASS"
            and tests.get("tests_total") == 19
            and tests.get("tests_passed") == 19
            and tests.get("tests_failed") == 0
            and tests.get("tests_skipped") == 0
            and tests.get("red_team", {}).get("planned") == 15
            and tests.get("red_team", {}).get("passed") == 15
        )
        check(
            "COMPETITION_TESTS_AND_RED_TEAM",
            "CORE",
            tests_ok,
            {
                "overall": tests.get("overall"),
                "tests": f"{tests.get('tests_passed')}/{tests.get('tests_total')}",
                "red_team": f"{tests.get('red_team', {}).get('passed')}/15",
            },
            {"overall": "PASS", "tests": "19/19", "red_team": "15/15"},
        )
        assets[test_report_path.relative_to(root).as_posix()] = file_record(
            root, test_report_path
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        check(
            "COMPETITION_TESTS_AND_RED_TEAM",
            "CORE",
            False,
            str(exc),
            "19/19_AND_15/15",
        )

    replay_source = research / "results" / "replay"
    actions: dict[str, str] = {}
    replay_ok = True
    replay_observed: dict[str, Any] = {}
    try:
        replay_manifest = load_json(replay_source / "replay_manifest.json")
        replay_ok = (
            replay_manifest.get("deterministic") is True
            and replay_manifest.get("replay_mode") == "OFFLINE_DETERMINISTIC"
            and replay_manifest.get("command_emitted") is False
        )
        for scenario_id, (expected_action, expected_command) in EXPECTED_ACTIONS.items():
            filename = f"scenario_{scenario_id}.json"
            record = load_json(replay_source / filename)
            action = record.get("explanation", {}).get("display_action")
            command = record.get("command_emitted")
            actions[scenario_id] = str(action)
            if action != expected_action or command is not expected_command:
                replay_ok = False
        replay_observed = {
            "deterministic": replay_manifest.get("deterministic"),
            "replay_mode": replay_manifest.get("replay_mode"),
            "command_emitted": replay_manifest.get("command_emitted"),
            "actions": actions,
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        replay_ok = False
        replay_observed = {"error": str(exc)}
    check(
        "OFFLINE_REPLAY_EXACT_ACTIONS",
        "CORE",
        replay_ok,
        replay_observed,
        {
            "deterministic": True,
            "replay_mode": "OFFLINE_DETERMINISTIC",
            "command_emitted": False,
            "actions": {key: value[0] for key, value in EXPECTED_ACTIONS.items()},
        },
    )

    asm_path = (
        root
        / "30_simulation"
        / "asm_00_interface_preflight"
        / "results"
        / "asm_00_gate_check.json"
    )
    asm_external = "ASM00_BLOCKED_BY_MISSING_PARAMETERS"
    asm_observed: dict[str, Any] = {}
    try:
        asm = load_json(asm_path)
        asm_external = str(asm.get("external_status"))
        asm_ok = (
            asm_external in ASM_VERDICTS
            and asm.get("negative_results_preserved") is True
            and asm.get("next_stage_authorized") is False
            and asm.get("contract_freeze_completed") is True
            and asm.get("success_evaluator", {})
            .get("validation", {})
            .get("criterion_count")
            == 9
        )
        asm_observed = {
            "external_status": asm_external,
            "raw_verdict": asm.get("raw_verdict"),
            "criterion_count": asm.get("success_evaluator", {})
            .get("validation", {})
            .get("criterion_count"),
            "next_stage_authorized": asm.get("next_stage_authorized"),
        }
        check(
            "ASM00_SEPARATE_FAIL_CLOSED_CLASSIFICATION",
            "DELIVERY",
            asm_ok,
            asm_observed,
            {
                "external_status": sorted(ASM_VERDICTS),
                "criterion_count": 9,
                "next_stage_authorized": False,
            },
        )
        assets[asm_path.relative_to(root).as_posix()] = file_record(root, asm_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        check(
            "ASM00_SEPARATE_FAIL_CLOSED_CLASSIFICATION",
            "DELIVERY",
            False,
            str(exc),
            "EXACT_ASM00_EXTERNAL_VERDICT",
        )

    hardware_plan = research / "hardware_component_plan.md"
    hardware_text = (
        hardware_plan.read_text(encoding="utf-8")
        if hardware_plan.is_file()
        else ""
    )
    hardware_status = {
        "H0": "NOT_STARTED_BLOCKED_BY_MISSING_HAG_E",
        "H1": "NOT_STARTED_BLOCKED_BY_H0",
        "H2": "NOT_STARTED_BLOCKED_BY_H1_AND_ESTIMATOR_GATE",
        "B601_MOTION": "PROHIBITED",
    }
    hardware_ok = all(value in hardware_text for value in hardware_status.values())
    hardware_ok = hardware_ok and all(
        not (root / "hardware" / "qualification" / stage).exists()
        for stage in ("H0", "H1", "H2")
    )
    check(
        "GROUND_COMPONENT_STOP_STATE",
        "DELIVERY",
        hardware_ok,
        hardware_status,
        hardware_status,
    )

    artifact_replay = delivery / "replay"
    replay_copy_ok = True
    replay_copy_observed: dict[str, str] = {}
    for filename in REQUIRED_REPLAY_FILES:
        source = replay_source / filename
        target = artifact_replay / filename
        if not source.is_file() or not target.is_file():
            replay_copy_ok = False
            replay_copy_observed[filename] = "MISSING"
            continue
        source_hash = sha256(source)
        target_hash = sha256(target)
        replay_copy_observed[filename] = target_hash
        if source_hash != target_hash:
            replay_copy_ok = False
        assets[target.relative_to(root).as_posix()] = file_record(root, target)
    check(
        "DELIVERY_REPLAY_BYTE_IDENTITY",
        "DELIVERY",
        replay_copy_ok,
        replay_copy_observed,
        "BYTE_IDENTICAL_TO_VERIFIED_RESEARCH_REPLAY",
    )

    report_path = research / "competition_execution_report.md"
    report_ok = False
    report_missing: list[str] = []
    if report_path.is_file():
        report_text = report_path.read_text(encoding="utf-8")
        report_missing = [
            anchor for anchor in REQUIRED_REPORT_ANCHORS if anchor not in report_text
        ]
        report_ok = not report_missing
        assets[report_path.relative_to(root).as_posix()] = file_record(root, report_path)
    check(
        "EXECUTION_REPORT_BOUNDARIES",
        "DELIVERY",
        report_ok,
        {"missing_anchors": report_missing}
        if report_path.is_file()
        else "MISSING",
        {"missing_anchors": []},
    )

    pptx_path = delivery / "competition_mission_intelligence_demo.pptx"
    try:
        pptx = inspect_pptx(pptx_path)
        check("PPTX_PACKAGE", "DELIVERY", True, pptx, {"slide_count": 9})
        assets[pptx_path.relative_to(root).as_posix()] = file_record(root, pptx_path)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        check("PPTX_PACKAGE", "DELIVERY", False, str(exc), "VALID_9_SLIDE_PPTX")

    slides_dir = delivery / "slides"
    slide_records: dict[str, Any] = {}
    slides_ok = True
    for index in range(1, 10):
        path = slides_dir / f"slide-{index:02d}.png"
        try:
            slide_records[path.name] = inspect_png(path)
            assets[path.relative_to(root).as_posix()] = file_record(root, path)
        except (OSError, ValueError) as exc:
            slides_ok = False
            slide_records[path.name] = {"error": str(exc)}
    check(
        "PRESENTATION_RENDER_SET",
        "DELIVERY",
        slides_ok,
        {"count": sum("error" not in value for value in slide_records.values())},
        {"count": 9, "dimensions": "1280x720"},
    )

    video_path = delivery / "competition_mission_intelligence_demo.mp4"
    try:
        video = inspect_video(video_path, ffprobe)
        check(
            "VIDEO_PACKAGE",
            "DELIVERY",
            True,
            video,
            {"codec": "h264", "dimensions": "1920x1080", "duration_s_min": 35},
        )
        assets[video_path.relative_to(root).as_posix()] = file_record(root, video_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        check(
            "VIDEO_PACKAGE",
            "DELIVERY",
            False,
            str(exc),
            "H264_1920x1080_DURATION_GE_35S",
        )

    if core_failures:
        final_verdict = BLOCKED
    elif delivery_failures:
        final_verdict = REPEAT
    else:
        final_verdict = READY

    gate = {
        "schema_version": SCHEMA,
        "final_verdict": final_verdict,
        "competition_chain_independent_of_assembly_wave_a_pass": True,
        "assembly_wave_a_pass_required_for_competition_demo": False,
        "asm00_external_verdict": asm_external,
        "hardware_component_status": hardware_status,
        "scenario_actions": actions,
        "offline_replay": True,
        "real_time_synchronization": False,
        "command_emitted": False,
        "next_stage_authorized": False,
        "thresholds_widened": False,
        "core_failures": core_failures,
        "delivery_failures": delivery_failures,
        "checks_passed": sum(item["status"] == "PASS" for item in checks),
        "checks_total": len(checks),
        "checks": checks,
        "negative_results": {
            "safe00_review_status": "PENDING_REVIEW",
            "safe00_next_stage_authorized": False,
            "ctrl02_external_scope": "PASS_WITH_PROVISIONAL_SCOPE",
            "ctrl02_l0_hardware_stability": "NOT_EVALUATED_NO_ACTUATOR_DYNAMICS",
            "asm00": asm_external,
            "h0_h1_h2": "NOT_STARTED",
            "strategy_config_line_ending_observation": {
                "primary_integration_raw_sha256": "fb228cf1b832354b9cc8865724df356d5519e3602f6c31838687bb1d923fb66e",
                "agent_c_crlf_raw_sha256": "3660765e7839dcb95b858124b588519e53325cac92983324b500589e667c3fe1",
                "canonical_yaml_equal": True,
            },
        },
        "stop_rules": {
            "start_asm01_or_asm02": False,
            "start_vla": False,
            "start_wave_b": False,
            "start_hil": False,
            "move_b601": False,
        },
    }
    manifest = {
        "schema_version": "competition-evidence-asset-manifest-v1",
        "final_verdict": final_verdict,
        "asset_count": len(assets),
        "assets": {key: assets[key] for key in sorted(assets)},
        "presentation": {
            "slide_count": 9 if slides_ok else sum(
                "error" not in value for value in slide_records.values()
            ),
            "slide_records": slide_records,
        },
    }
    return gate, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument(
        "--output",
        default="10_research/competition_convergence/competition_gate_check.json",
        type=Path,
    )
    parser.add_argument(
        "--asset-manifest",
        default="40_evidence/artifacts/competition_convergence/evidence_asset_manifest.json",
        type=Path,
    )
    parser.add_argument("--ffprobe", default=None)
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Write a repeat/blocked preflight gate and return zero.",
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    asset_manifest = (
        args.asset_manifest
        if args.asset_manifest.is_absolute()
        else root / args.asset_manifest
    )
    gate, manifest = run_gate(root, args.ffprobe)
    output.parent.mkdir(parents=True, exist_ok=True)
    asset_manifest.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(deterministic_json_bytes(gate))
    asset_manifest.write_bytes(deterministic_json_bytes(manifest))
    print(
        f"{gate['final_verdict']} "
        f"checks={gate['checks_passed']}/{gate['checks_total']} "
        f"asm00={gate['asm00_external_verdict']}"
    )
    if args.allow_incomplete or gate["final_verdict"] == READY:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
