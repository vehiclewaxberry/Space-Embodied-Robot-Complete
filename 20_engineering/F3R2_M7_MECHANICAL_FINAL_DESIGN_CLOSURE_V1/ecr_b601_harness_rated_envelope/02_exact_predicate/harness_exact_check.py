# -*- coding: utf-8 -*-
"""Public fail-closed API for the frozen R2-HRN-05 harness geometry kernel.

This module intentionally does not edit or fork the accepted URDF.  It wraps
the hash-bound V2 geometry evaluator and applies the terminal product's bend
requirement.  It must be executed inside FreeCAD's Python runtime.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import yaml


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
M7 = PACKAGE.parent
PROJECT = M7.parents[1]
PROBE_SOURCE = PACKAGE / "99_tools" / "probe_current_route_mission_states.py"
PIN_FILE = PACKAGE / "00_authority" / "ROUTE_B_FROZEN_INPUT_PINS_V1.yaml"
PIN_FILE_EXPECTED_SHA256 = "6BB8E9C5FF6910BE07D1720D320C4CB560A2CF07AD254DEB83E931AF4731C588"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _project_path(relative_path: str) -> Path:
    return PROJECT / relative_path.replace("\\", "/")


def verify_frozen_inputs() -> dict:
    """Compare frozen expected pins to independent live hashes.

    The pin-file hash is compiled into this evaluator, so editing both a
    dependency and its YAML expected value cannot silently manufacture PASS.
    The pinned V2 result in turn supplies the complete transitive geometry
    manifest (URDF, meshes, STEP witnesses and routing inputs).
    """
    receipt = {
        "pin_file": str(PIN_FILE),
        "pin_file_expected_sha256": PIN_FILE_EXPECTED_SHA256,
        "pin_file_actual_sha256": None,
        "pin_file_match": False,
        "checks": [],
        "integrity_ok": False,
    }
    if not PIN_FILE.is_file():
        receipt["error"] = "PIN_FILE_MISSING"
        return receipt
    receipt["pin_file_actual_sha256"] = _sha256(PIN_FILE)
    receipt["pin_file_match"] = receipt["pin_file_actual_sha256"] == PIN_FILE_EXPECTED_SHA256
    if not receipt["pin_file_match"]:
        receipt["error"] = "PIN_FILE_HASH_MISMATCH"
        return receipt

    pins = yaml.safe_load(PIN_FILE.read_text(encoding="utf-8"))
    for group_name in ("runtime_exact_dependencies", "mission_and_mass_dependencies"):
        for name, item in pins[group_name].items():
            path = _project_path(item["path"])
            actual = _sha256(path) if path.is_file() else None
            receipt["checks"].append({
                "group": group_name,
                "name": name,
                "path": item["path"],
                "expected_sha256": item["expected_sha256"],
                "actual_sha256": actual,
                "match": actual == item["expected_sha256"],
            })

    v2_item = pins["runtime_exact_dependencies"]["full_range_negative_result"]
    v2_path = _project_path(v2_item["path"])
    if v2_path.is_file() and _sha256(v2_path) == v2_item["expected_sha256"]:
        v2 = json.loads(v2_path.read_text(encoding="utf-8"))
        for relative_path, expected in v2.get("inputs_sha256", {}).items():
            path = _project_path(relative_path)
            actual = _sha256(path) if path.is_file() else None
            receipt["checks"].append({
                "group": "v2_transitive_geometry_inputs",
                "name": Path(relative_path).name,
                "path": relative_path.replace("\\", "/"),
                "expected_sha256": expected,
                "actual_sha256": actual,
                "match": actual == expected,
            })
    else:
        receipt["checks"].append({
            "group": "v2_transitive_geometry_inputs",
            "name": "manifest_unavailable",
            "path": v2_item["path"],
            "expected_sha256": v2_item["expected_sha256"],
            "actual_sha256": _sha256(v2_path) if v2_path.is_file() else None,
            "match": False,
        })

    receipt["checks_total"] = len(receipt["checks"])
    receipt["checks_passed"] = sum(bool(item["match"]) for item in receipt["checks"])
    receipt["mismatches"] = [item for item in receipt["checks"] if not item["match"]]
    receipt["integrity_ok"] = receipt["pin_file_match"] and not receipt["mismatches"]
    return receipt


def _load_probe_module():
    spec = importlib.util.spec_from_file_location("b601_route_b_probe", PROBE_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load exact probe source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HarnessExactEvaluator:
    """Stateful evaluator; geometry is loaded once and reused for many q calls."""

    def __init__(self, required_bend_radius_mm: float = 30.0):
        self.required_bend_radius_mm = float(required_bend_radius_mm)
        self.integrity_receipt = verify_frozen_inputs()
        self.integrity_ok = bool(self.integrity_receipt["integrity_ok"])
        self.probe = None
        self.kernel = None
        self.context = None
        self.hardware_limits = None
        if not self.integrity_ok:
            return
        self.probe = _load_probe_module()
        self.kernel = self.probe.load_kernel()
        self.context = self.probe.build_context(self.kernel)
        self.hardware_limits = np.asarray(
            [[joint["lo"], joint["hi"]] for joint in self.context["arm"].rev],
            dtype=float,
        )

    def check(self, q_rad, state_id: str = "QUERY") -> dict:
        if not self.integrity_ok:
            result = self._unknown(state_id, "FROZEN_INPUT_HASH_MISMATCH")
            result["integrity_receipt"] = self.integrity_receipt
            return result
        try:
            q = np.asarray(q_rad, dtype=float)
        except Exception as exc:
            return self._unknown(state_id, "Q_NOT_NUMERIC", str(exc))
        if q.shape != (6,) or not np.all(np.isfinite(q)):
            return self._unknown(state_id, "Q_NOT_SIX_FINITE_RADIANS")
        inside = bool(
            np.all(q >= self.hardware_limits[:, 0])
            and np.all(q <= self.hardware_limits[:, 1])
        )
        if not inside:
            return {
                "state_id": state_id,
                "q_rad": q.tolist(),
                "status": "UNSAFE",
                "reason": "HARDWARE_JOINT_LIMIT_VIOLATION",
                "required_action": "ABORT",
            }
        try:
            result = self.probe.evaluate_state(
                self.kernel, self.context, state_id, q.tolist()
            )
        except Exception as exc:
            return self._unknown(state_id, "EXACT_GEOMETRY_EVALUATION_ERROR", str(exc))

        bend_radius = result["margins"].get("bend_radius_mm")
        if bend_radius is None or not math.isfinite(float(bend_radius)):
            return self._unknown(state_id, "BEND_RADIUS_NOT_EVALUATED")
        result["margins"]["bend_radius_required_mm"] = self.required_bend_radius_mm
        result["margins"]["bend_margin_mm"] = (
            float(bend_radius) - self.required_bend_radius_mm
        )
        keys = (
            "clearance_mm",
            "bend_margin_mm",
            "pinch_mm",
            "length_margin_mm",
            "joint_limit_margin_rad",
        )
        known = all(
            result["margins"].get(key) is not None
            and math.isfinite(float(result["margins"][key]))
            for key in keys
        )
        safe = bool(
            known
            and all(float(result["margins"][key]) >= 0.0 for key in keys)
            and result.get("empty_comparison_sets", 1) == 0
        )
        result["status"] = "SAFE" if safe else ("UNSAFE" if known else "UNKNOWN")
        result["required_action"] = "ALLOW" if safe else "ABORT"
        result["predicate_version"] = "B601_HARNESS_EXACT_PREDICATE_V1"
        return result

    @staticmethod
    def _unknown(state_id: str, reason: str, detail: str | None = None) -> dict:
        out = {
            "state_id": state_id,
            "status": "UNKNOWN",
            "reason": reason,
            "required_action": "ABORT",
            "predicate_version": "B601_HARNESS_EXACT_PREDICATE_V1",
        }
        if detail:
            out["detail"] = detail
        return out


def harness_exact_check(q_rad, state_id: str = "QUERY") -> dict:
    """One-shot convenience entry point; batch users should reuse the class."""
    return HarnessExactEvaluator().check(q_rad, state_id=state_id)
