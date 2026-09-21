"""Source-only Sim13 V2 environment shell with hash-bound gate authority."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .authority_resolver import AuthorityResolution, AuthorityResolver
from .contracts import (
    HighLevelAction,
    enforce_fail_closed,
    parse_action,
    strategy_mask,
)
from .system_model import SystemModel, SystemState


def _authority_snapshot_digest(resolution: AuthorityResolution) -> str:
    document = {
        "config_sha256": resolution.config_sha256,
        "gates": resolution.snapshot.as_dict(),
        "artifacts": {
            name: {
                "path": str(item.path) if item.path is not None else None,
                "verified": item.verified,
                "reason_code": item.reason_code,
                "bytes": item.byte_count,
                "sha256": item.sha256,
            }
            for name, item in sorted(resolution.artifacts.items())
        },
    }
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


class Sim13V2Environment:
    """Gym-shaped prebind shell; it does not claim dynamics or contact readiness."""

    metadata = {
        "name": "sim13_v2_system_rebind_prebind",
        "contract_version": "SIM13_V2_RUNTIME_AUTHORITY_V1",
        "scope": "SOURCE_ONLY_PREBIND_NOT_BOUND_NOT_LOADED",
    }

    def __init__(self, *, seed: int = 0) -> None:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("seed must be an integer")
        self._resolver = AuthorityResolver()
        self._default_seed = seed
        self._seed = seed
        self._step_count = 0
        self._has_reset = False
        self._resolution: AuthorityResolution | None = None
        self._model: SystemModel | None = None
        self._model_error: str | None = None
        self._state: SystemState | None = None

    def reset(self, *, seed: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        selected_seed = self._default_seed if seed is None else seed
        if not isinstance(selected_seed, int) or isinstance(selected_seed, bool):
            raise ValueError("seed must be an integer")
        self._seed = selected_seed
        self._step_count = 0
        self._refresh_authority_and_model()
        self._has_reset = True
        return self._observation(), self._info()

    def action_mask(self) -> Mapping[str, dict[str, Any]]:
        self._refresh_authority_and_model()
        assert self._resolution is not None
        return {
            strategy: {
                "allowed": decision.allowed,
                "reason_codes": list(decision.reason_codes),
            }
            for strategy, decision in strategy_mask(self._resolution.snapshot).items()
        }

    def step(
        self,
        action: HighLevelAction | Mapping[str, Any],
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if not self._has_reset:
            raise RuntimeError("reset must be called before step")
        requested = parse_action(action)
        self._refresh_authority_and_model()
        assert self._resolution is not None
        shield = enforce_fail_closed(requested, self._resolution.snapshot)
        self._step_count += 1
        executed_abort = shield.executed_action.is_abort
        info = self._info()
        info.update(
            {
                "requested_action": shield.requested_action.as_dict(),
                "executed_action": shield.executed_action.as_dict(),
                "shield_intervened": shield.intervened,
                "shield_reason_codes": list(shield.reason_codes),
                "termination_reason": "ABORT" if executed_abort else "NONE",
            }
        )
        return self._observation(), 0.0, executed_abort, False, info

    def _refresh_authority_and_model(self) -> None:
        self._resolution = self._resolver.resolve()
        self._model = None
        self._model_error = None
        self._state = None
        artifact = self._resolution.system_urdf
        if artifact is None or not artifact.verified or artifact.payload is None or artifact.path is None:
            self._model_error = "SYSTEM_URDF_NOT_HASH_BOUND_AND_AVAILABLE"
            return
        try:
            self._model = SystemModel.from_xml_bytes(
                artifact.payload, artifact_root=artifact.path.parent
            )
            self._state = self._model.zero_state()
        except ValueError as exc:
            self._model_error = f"SYSTEM_URDF_MODEL_REJECTED:{exc}"

    def _observation(self) -> dict[str, Any]:
        if self._resolution is None:
            raise RuntimeError("environment must be reset first")
        joint_names = list(self._state.joint_names) if self._state else []
        q = list(self._state.q) if self._state else []
        dq = list(self._state.dq) if self._state else []
        return {
            "schema": "SIM13_V2_OBSERVATION_V1",
            "step_count": self._step_count,
            "authority_snapshot_sha256": _authority_snapshot_digest(self._resolution),
            "production_ready": False,
            "command_emitted": False,
            "system": {
                "status": (
                    "SYSTEM_URDF_PARSED_HASH_BOUND_NOT_CONSUMER_AUTHORIZED"
                    if self._model is not None
                    else "UNAVAILABLE_FAIL_CLOSED"
                ),
                "model_error": self._model_error,
                "expected_topology": {
                    "links": 19,
                    "joints": 18,
                    "physical_links": 16,
                    "frame_only_links": 3,
                    "movable_dof": 8,
                },
                "topology_link_count": (
                    len(self._model.link_names) if self._model is not None else None
                ),
                "topology_joint_count": (
                    len(self._model.joint_names) if self._model is not None else None
                ),
                "physical_link_count": (
                    len(self._model.physical_link_names) if self._model is not None else None
                ),
                "frame_only_link_count": (
                    len(self._model.frame_only_link_names) if self._model is not None else None
                ),
                "fixed_joint_names": (
                    list(self._model.fixed_joint_names) if self._model is not None else []
                ),
                "movable_joint_names": joint_names,
                "q": q,
                "dq": dq,
                "state_dimension": len(joint_names),
                "fixed_joints_excluded": True,
            },
            "collision": {
                "status": "UNKNOWN_NOT_EVALUATED",
                "detected": None,
                "clear": None,
                "operational_collision_authority": False,
            },
            "physics_gates": self._resolution.snapshot.as_dict(),
        }

    def _info(self) -> dict[str, Any]:
        if self._resolution is None:
            raise RuntimeError("environment must be reset first")
        return {
            "seed": self._seed,
            "step_count": self._step_count,
            "authority_config_path": str(self._resolution.config_path),
            "authority_config_sha256": self._resolution.config_sha256,
            "authority_config_valid": self._resolution.config_valid,
            "authority_scope": self._resolution.scope,
            "authority_errors": list(self._resolution.errors),
            "authority_artifacts": {
                name: {
                    "path": str(item.path) if item.path is not None else None,
                    "verified": item.verified,
                    "reason_code": item.reason_code,
                    "bytes": item.byte_count,
                    "sha256": item.sha256,
                }
                for name, item in sorted(self._resolution.artifacts.items())
            },
            "authority_snapshot_sha256": _authority_snapshot_digest(self._resolution),
            "gate_snapshot": self._resolution.snapshot.as_dict(),
            "execution_scope": "RUNTIME_CONTRACT_ONLY_NO_DYNAMICS_OR_CONTACT_CLAIM",
            "production_ready": False,
            "command_emitted": False,
        }


__all__ = ["Sim13V2Environment"]
