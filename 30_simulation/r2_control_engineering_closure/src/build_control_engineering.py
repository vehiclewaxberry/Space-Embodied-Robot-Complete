"""Build the deterministic R2 control engineering candidate package."""
from __future__ import annotations

import argparse
from pathlib import Path

from control_engineering import (
    CONFIG_PATH,
    DEFAULT_REPO_ROOT,
    MODULE_ROOT,
    PHASE_CONTRACT_PATH,
    RESULTS_DIR,
    SUPERVISOR_CONTRACT_PATH,
    build_control_engineering_gate,
    build_ctrl01_causal_ledger,
    build_flex_robustness_gate,
    build_precontact_tracking_gate,
    build_supervisor_assessment,
    load_json_strict,
    pinned_path,
    validate_source_pins,
    write_json,
    write_manifest,
)


def build(repo_root: Path) -> dict:
    config = load_json_strict(CONFIG_PATH)
    phase_contract = load_json_strict(PHASE_CONTRACT_PATH)
    supervisor_contract = load_json_strict(SUPERVISOR_CONTRACT_PATH)
    source_binding = validate_source_pins(repo_root, config)
    write_json(RESULTS_DIR / "R2_CONTROL_SOURCE_BINDING_V1.json", source_binding)
    if not source_binding["pass"]:
        raise RuntimeError(
            "SOURCE_BINDING_FAIL_CLOSED:" + ",".join(source_binding["mismatches"])
        )

    classification = load_json_strict(
        pinned_path(repo_root, config, "ctrl01_failure_classification")
    )
    legacy_gate = load_json_strict(
        pinned_path(repo_root, config, "ctrl01_gate")
    )
    replay_audit = load_json_strict(
        pinned_path(repo_root, config, "migration_replay_audit")
    )
    causal_ledger = build_ctrl01_causal_ledger(
        classification,
        legacy_gate,
        replay_audit,
    )
    write_json(RESULTS_DIR / "CTRL01_R2_FAILURE_CAUSAL_LEDGER.json", causal_ledger)

    precontact_gate = build_precontact_tracking_gate(
        repo_root,
        config,
        source_binding,
    )
    write_json(
        RESULTS_DIR / "CTRL_R2_PRECONTACT_TRACKING_GATE_V1.json",
        precontact_gate,
    )

    rom = load_json_strict(pinned_path(repo_root, config, "round4_rom"))
    static_screen = load_json_strict(
        pinned_path(repo_root, config, "flex_static_screen")
    )
    e23_gate = load_json_strict(pinned_path(repo_root, config, "e23_gate"))
    flex_gate = build_flex_robustness_gate(
        rom,
        static_screen,
        e23_gate,
        supervisor_contract,
        source_binding,
    )
    write_json(
        RESULTS_DIR / "CTRL_R2_FLEX_ROBUSTNESS_GATE_V1.json",
        flex_gate,
    )

    ctrl02_gate = load_json_strict(
        pinned_path(repo_root, config, "ctrl02_gate")
    )
    safe_gate = load_json_strict(pinned_path(repo_root, config, "safe00_gate"))
    actuator_audit = load_json_strict(
        pinned_path(repo_root, config, "actuator_intake_audit")
    )
    contact_gate = load_json_strict(
        pinned_path(repo_root, config, "contact_gate")
    )
    supervisor_assessment = build_supervisor_assessment(
        supervisor_contract,
        ctrl02_gate,
        safe_gate,
        actuator_audit,
        contact_gate,
    )
    write_json(
        RESULTS_DIR / "CTRL_R2_SUPERVISOR_ASSESSMENT_V1.json",
        supervisor_assessment,
    )

    predevelopment_gate = load_json_strict(
        pinned_path(repo_root, config, "predevelopment_gate")
    )
    control_gate = build_control_engineering_gate(
        source_binding,
        causal_ledger,
        phase_contract,
        precontact_gate,
        flex_gate,
        supervisor_assessment,
        predevelopment_gate,
    )
    write_json(
        RESULTS_DIR / "R2_CONTROL_ENGINEERING_GATE_V1.json",
        control_gate,
    )

    manifest = write_manifest(
        MODULE_ROOT,
        RESULTS_DIR / "R2_CONTROL_ENGINEERING_SHA256_V1.csv",
    )
    return {
        "source_binding": source_binding,
        "causal_ledger": causal_ledger,
        "precontact_gate": precontact_gate,
        "flex_gate": flex_gate,
        "supervisor_assessment": supervisor_assessment,
        "control_gate": control_gate,
        "manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_REPO_ROOT,
    )
    args = parser.parse_args()
    result = build(args.repo_root.resolve())
    gate = result["control_gate"]
    print(gate["technical_verdict"])
    print(
        f"source_pins={result['source_binding']['match_count']}/"
        f"{result['source_binding']['pin_count']}"
    )
    print(f"manifest_files={result['manifest']['file_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
