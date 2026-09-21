"""Frozen configuration, method contracts, and scope-neutral helpers."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from repo_imports import CONFIG_PATH, MATRIX_PATH


ALLOWED_METHODS = ("C0", "C1", "C2", "C3")
ALLOWED_TASK_MODES = ("pose_6d", "approach_5d")
GATE_RESULT_ENUM = ("PASS", "REPEAT", "BLOCKED")


class ControllerContractError(ValueError):
    """Contract refusal with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_config() -> dict[str, Any]:
    cfg = load_yaml(CONFIG_PATH)
    assert cfg["frozen_before_plant_runs"] is True
    assert cfg["gains_tuned_on_plant"] is False
    assert cfg["thresholds_widened"] is False
    return cfg


def load_matrix() -> dict[str, Any]:
    matrix = load_yaml(MATRIX_PATH)
    assert matrix["frozen_before_results"] is True
    return matrix


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_semantic_sha256(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class MethodContract:
    name: str
    task_mode: str
    uses_generalized_jacobian: bool
    uses_reference_feedforward: bool
    uses_reaction_nullspace: bool


def method_contract(method: str, task_mode: str, cfg: dict[str, Any]) -> MethodContract:
    if method not in ALLOWED_METHODS:
        raise ControllerContractError("UNKNOWN_METHOD", method)
    if task_mode not in ALLOWED_TASK_MODES:
        raise ControllerContractError("UNKNOWN_TASK_MODE", task_mode)
    if method == "C3" and task_mode != cfg["controller"]["c3_allowed_task"]:
        raise ControllerContractError(
            cfg["controller"]["c3_pose_6d_error_code"],
            "C3 is only defined for a rank-5 approach task on the 6R arm",
        )
    return MethodContract(
        name=method,
        task_mode=task_mode,
        uses_generalized_jacobian=method != "C0",
        uses_reference_feedforward=method in ("C2", "C3"),
        uses_reaction_nullspace=method == "C3",
    )


def joint_limits(arm) -> tuple[np.ndarray, np.ndarray]:
    lo = np.array([j["lower"] for j in arm.joints], dtype=float)
    hi = np.array([j["upper"] for j in arm.joints], dtype=float)
    return lo, hi


def exact_svd_projector(J: np.ndarray, rank_rtol: float) -> tuple[np.ndarray, int]:
    """Return I-J^+J using an un-damped SVD and the frozen rank tolerance."""
    _, singular, vt = np.linalg.svd(J, full_matrices=True)
    threshold = rank_rtol * singular[0] if singular.size else 0.0
    rank = int(np.sum(singular > threshold))
    row_basis = vt[:rank]
    projector = np.eye(J.shape[1]) - row_basis.T @ row_basis
    return projector, rank


def dls_pseudoinverse(J: np.ndarray, damping: float) -> np.ndarray:
    m = J.shape[0]
    return J.T @ np.linalg.solve(
        J @ J.T + float(damping) ** 2 * np.eye(m), np.eye(m)
    )


def reaction_map_about_base_origin(model, theta: np.ndarray, eta: np.ndarray) -> np.ndarray:
    """(H_bb^-1 H_bm)_angular,joint with H_bm about the base S origin."""
    momentum_map = model.momentum_matrix(theta, eta)
    hbb = momentum_map[:, :6]
    hbm_joint = momentum_map[:, 6:12]
    return np.linalg.solve(hbb, hbm_joint)[3:6, :]
