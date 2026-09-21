"""Command-line entry point for the ASM-00 fail-closed preflight gate."""

from __future__ import annotations

import argparse
from pathlib import Path

from asm00_gate import build_evidence_manifest, build_gate, write_json


DEFAULT_OWNED = Path("30_simulation/asm_00_interface_preflight")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify the unchanged ASM-00 draft and fail closed before "
            "scientific qualification when authorization or inputs are missing."
        )
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--planning-root", default=None)
    parser.add_argument(
        "--preflight-contract",
        default=str(DEFAULT_OWNED / "config/preflight_contract.yaml"),
    )
    parser.add_argument(
        "--ssot",
        default="10_research/on_orbit_assembly/interface_ssot_draft.yaml",
    )
    parser.add_argument(
        "--success-contract",
        default=str(
            DEFAULT_OWNED
            / "contracts/assembly_success_evaluator_v1.yaml"
        ),
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OWNED / "results/asm_00_gate_check.json"),
    )
    parser.add_argument(
        "--evidence-manifest",
        default=str(DEFAULT_OWNED / "results/evidence_manifest.json"),
    )
    return parser.parse_args()


def resolve_under(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    planning_root = (
        Path(args.planning_root).resolve()
        if args.planning_root
        else repo_root
    )
    preflight_contract = resolve_under(repo_root, args.preflight_contract)
    ssot = resolve_under(repo_root, args.ssot)
    success_contract = resolve_under(repo_root, args.success_contract)
    output = resolve_under(repo_root, args.output)
    evidence_manifest = resolve_under(repo_root, args.evidence_manifest)

    gate = build_gate(
        repo_root,
        planning_root,
        preflight_contract,
        ssot,
        success_contract,
    )
    write_json(output, gate)
    manifest = build_evidence_manifest(
        repo_root,
        planning_root,
        gate,
        output,
        evidence_manifest,
    )
    write_json(evidence_manifest, manifest)
    print(
        f"{gate['raw_verdict']} -> {gate['external_status']} "
        f"(qualification_granted={gate['interface_qualification_granted']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
