"""CTRL-02 parameter loading and frozen-input verification."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
REPO = MODULE.parent.parent
CFG_PATH = REPO / "20_engineering" / "config" / "attitude_stab" / "attitude_stab_v0.yaml"


def _bytes_for_hash(path: Path, mode: str) -> bytes:
    data = path.read_bytes()
    if mode == "normalized_lf":
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if mode != "raw":
        raise ValueError(f"unsupported hash_mode={mode}")
    return data


def sha256_file(path: Path, mode: str = "raw") -> str:
    return hashlib.sha256(_bytes_for_hash(path, mode)).hexdigest()


def load_config(verify_hashes: bool = True) -> dict:
    with CFG_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    report = {}
    for key, spec in cfg["frozen_inputs"].items():
        path = REPO / spec["path"]
        mode = spec.get("hash_mode", "raw")
        actual = sha256_file(path, mode)
        actual_raw = sha256_file(path, "raw")
        actual_normalized = sha256_file(path, "normalized_lf")
        expected = str(spec["sha256"]).lower()
        match = actual == expected
        report[key] = {
            "path": spec["path"],
            "hash_mode": mode,
            "expected": expected,
            "actual": actual,
            "actual_raw": actual_raw,
            "actual_normalized_lf": actual_normalized,
            "match": match,
        }
        if verify_hashes and not match:
            raise RuntimeError(f"frozen input hash drift: {spec['path']}")

    registry_spec = cfg["frozen_inputs"]["threshold_registry"]
    with (REPO / registry_spec["path"]).open(encoding="utf-8") as f:
        registry = yaml.safe_load(f)
    thresholds = registry["thresholds"]
    gates = cfg["gates"]
    exact_pairs = (
        ("base_attitude_change_max_deg", "base_attitude_change_max_deg"),
        ("post_capture_rate_max_dps", "post_capture_rate_max_dps"),
        ("external_removal_capacity_Nms", "wheel_momentum_max_Nms"),
        ("thruster_impulse_max_Ns", "thruster_impulse_max_Ns"),
        ("propellant_budget_max_g", "propellant_budget_max_g"),
    )
    for cfg_key, registry_key in exact_pairs:
        if abs(float(gates[cfg_key]) - float(thresholds[registry_key]["value"])) > 1e-12:
            raise RuntimeError(f"threshold drift: {cfg_key} != registry.{registry_key}")

    if cfg["policy"]["thresholds_widened"] is not False:
        raise RuntimeError("thresholds_widened must remain false")
    if cfg["policy"]["flex_in_absolute_criteria"] is not False:
        raise RuntimeError("FLEX must not enter absolute criteria")

    cfg["_hash_report"] = report
    cfg["_registry"] = registry
    cfg["_config_path"] = os.path.relpath(CFG_PATH, REPO).replace("\\", "/")
    return cfg
