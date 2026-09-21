"""Re-run Sim14 validation and verify the published evidence bindings."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


SIM14_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SIM14_ROOT.parents[1]
sys.path.insert(0, str(SIM14_ROOT))

from src.contracts import ExecutionMode, RuntimeGateSnapshot  # noqa: E402
from src.env import (  # noqa: E402
    ANCHOR_150KG,
    ANCHOR_22KG,
    M4DigitalPrototypeGraspingEnv,
)
from src.interface_loader import (  # noqa: E402
    DIAGNOSTIC_ACKNOWLEDGEMENT,
    load_mechanical_interface,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def capture_case(interface_path: Path, fixture_path: Path, anchor_id: str) -> dict[str, float]:
    env = M4DigitalPrototypeGraspingEnv(
        interface_path,
        execution_mode=ExecutionMode.BOUNDED_DIAGNOSTIC,
        diagnostic_fixture_path=fixture_path,
        diagnostic_acknowledgement=DIAGNOSTIC_ACKNOWLEDGEMENT,
        anchor_id=anchor_id,
    )
    env.reset(gates=RuntimeGateSnapshot.all_pass())
    env.step("MOVE_PREGRASP")
    env.step("DECLARE_CONTACT_CANDIDATE")
    observation, _, _, _, _ = env.step("CLOSE_GRIPPER")
    closure = observation["capture_closure"]
    return {
        "linear_residual_norm_kg_mps": closure["linear_residual_norm_kg_mps"],
        "angular_residual_norm_kg_m2ps": closure["angular_residual_norm_kg_m2ps"],
    }


def main() -> int:
    source_manifest_path = SIM14_ROOT / "evidence" / "SIM14_SOURCE_MANIFEST.json"
    gate_path = SIM14_ROOT / "evidence" / "SIM14_DYNAMICS_GRASPING_GATE.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    hash_mismatches: list[dict[str, str]] = []
    for item in source_manifest["artifacts"]:
        base = SIM14_ROOT if item["base"] == "SIM14_ROOT" else PROJECT_ROOT
        path = (base / item["path"]).resolve()
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != item["sha256"]:
            hash_mismatches.append(
                {"path": str(path), "expected": item["sha256"], "actual": actual}
            )
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SIM14_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    interface_path = (
        PROJECT_ROOT
        / "20_engineering"
        / "F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1"
        / "08_simulation_assets"
        / "MECH_RL_INTERFACE_V2.yaml"
    )
    fixture_path = SIM14_ROOT / "config" / "SIM14_DIAGNOSTIC_FIXTURE_V1.json"
    interface = load_mechanical_interface(interface_path)
    cases = {
        anchor: capture_case(interface_path, fixture_path, anchor)
        for anchor in (ANCHOR_22KG, ANCHOR_150KG)
    }
    residual_limit = float(gate["diagnostic_momentum_gate"]["absolute_residual_limit"])
    residuals_pass = all(
        result["linear_residual_norm_kg_mps"] <= residual_limit
        and result["angular_residual_norm_kg_m2ps"] <= residual_limit
        for result in cases.values()
    )
    passed = (
        test.returncode == 0
        and not hash_mismatches
        and residuals_pass
        and interface.production_ready is False
        and gate["production_dynamics_gate"] == "HOLD"
    )
    report = {
        "verdict": "PASS_DIAGNOSTIC_ONLY" if passed else "FAIL",
        "pytest_exit_code": test.returncode,
        "pytest_output": (test.stdout + test.stderr).strip(),
        "hash_mismatches": hash_mismatches,
        "production_interface_ready": interface.production_ready,
        "diagnostic_cases": cases,
        "production_dynamics_gate": gate["production_dynamics_gate"],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
