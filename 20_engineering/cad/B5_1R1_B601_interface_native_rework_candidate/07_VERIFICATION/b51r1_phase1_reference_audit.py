"""Cold read-only reference audit for the B5.1R1 Phase 1 V2.2 working copy.

The exact 108-file frozen copy under ``00_BASELINE`` is never opened for
write.  A second working copy under ``01_MEASUREMENT`` is opened in a fresh,
exclusive SOLIDWORKS 2024 process.  The result records all resolved component
paths and all configuration-level containment checks.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = CANDIDATE_ROOT.parents[2]
PARENT_SCRIPT = (
    REPO_ROOT
    / "20_engineering"
    / "cad"
    / "B5_1_B601_interface_closure_candidate"
    / "automation"
    / "b51_phase_a_native_reference_isolation.py"
)
SOURCE_ROOT = (
    CANDIDATE_ROOT / "00_BASELINE" / "V2_2_NATIVE_CANONICAL_108_FILE_COPY"
)
COPY_ROOT = (
    CANDIDATE_ROOT / "01_MEASUREMENT" / "V2_2_NATIVE_REFERENCE_WORKING_COPY"
)
TOP_RELATIVE = Path("Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM")
OUTPUT = (
    CANDIDATE_ROOT
    / "01_MEASUREMENT"
    / "B51R1_V22_REFERENCE_CONTAINMENT_PRE_REPAIR.json"
)


def load_parent():
    spec = importlib.util.spec_from_file_location(
        "b51_parent_reference_isolation", PARENT_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load parent audit module: {PARENT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"append-only output already exists: {OUTPUT}")
    if not SOURCE_ROOT.is_dir() or not COPY_ROOT.is_dir():
        raise RuntimeError("source or working-copy directory is missing")

    parent = load_parent()
    parent.CANDIDATE_ROOT = CANDIDATE_ROOT
    parent.SOURCE_ROOT = SOURCE_ROOT
    parent.COPY_ROOT = COPY_ROOT
    parent.COPY_TOP = COPY_ROOT / TOP_RELATIVE
    parent.core.CANDIDATE_ROOT = CANDIDATE_ROOT
    parent.core.WRITER_MUTEX_NAME = (
        r"Local\SER_B51R1_PHASE1_SOLIDWORKS_WRITER"
    )

    result = parent.launch_retry(
        lambda: parent.audit_once("B51R1_PHASE1_COLD_REFERENCE_PRE_REPAIR"),
        "B51R1 Phase 1 cold reference audit",
    )
    result.update(
        {
            "schema": "SER_B51R1_PHASE1_REFERENCE_CONTAINMENT_V1",
            "task_id": "COMP-PROT-03-A4-B5.1R1-PHASE1",
            "frozen_source_root": str(SOURCE_ROOT.resolve()),
            "working_copy_root": str(COPY_ROOT.resolve()),
            "write_policy": (
                "READ_ONLY_AUDIT_EXACT_FROZEN_SOURCE_NEVER_OPENED_FOR_WRITE"
            ),
            "claim_limit": "REFERENCE_CONTAINMENT_ONLY",
        }
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "verdict": result["verdict"],
                "components_total": result["components_total"],
                "outside": len(result["resolved_outside_b51_copy"]),
                "unresolved": len(result["unresolved_components"]),
                "missing": len(result["missing_resolved_paths"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["verdict"] == "ISOLATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
