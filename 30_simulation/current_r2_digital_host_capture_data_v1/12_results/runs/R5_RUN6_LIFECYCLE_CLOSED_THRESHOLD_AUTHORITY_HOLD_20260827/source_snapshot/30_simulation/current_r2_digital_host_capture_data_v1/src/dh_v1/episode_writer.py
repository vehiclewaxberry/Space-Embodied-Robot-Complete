"""Deterministic episode writer (H5 layer).

Every run — including failures and negative controls — is persisted with full
hash provenance. Failed episodes are never deleted. Missing authorities are
written as explicit null + status, never fabricated.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .hashing import sha256_canonical_json, sha256_file
from .safe_prebind import DECISIONS

LABELS = ("EXECUTE", "MODIFY", "ABORT", "UNKNOWN", "NOT_EVALUATED")

MANIFEST_REQUIRED = [
    "episode_id",
    "base_state_id",
    "scenario_id",
    "strategy_id",
    "seed",
    "authority_snapshot_sha256",
    "accepted_urdf_sha256",
    "step_state_sha256",
    "collision_manifest_sha256",
    "frame_contract_sha256",
    "unit_contract_sha256",
    "controller_config_sha256",
    "safe_config_sha256",
    "plant_sha256",
    "geometry_authority",
    "dynamics_authority",
    "contact_authority",
    "T_E_T_status",
    "evidence_level",
    "claim_ceiling",
    "binding_gate",
    "terminal_decision",
    "label",
]


class EpisodeWriteError(RuntimeError):
    pass


def validate_manifest(manifest: dict) -> None:
    missing = [k for k in MANIFEST_REQUIRED if k not in manifest]
    if missing:
        raise EpisodeWriteError(f"episode manifest missing required fields: {missing}")
    if manifest["label"] not in LABELS:
        raise EpisodeWriteError(f"label {manifest['label']!r} not in {LABELS}")
    if manifest["terminal_decision"] not in DECISIONS + ("NONE",):
        raise EpisodeWriteError(f"terminal_decision {manifest['terminal_decision']!r} invalid")
    # fail-closed pairings that must never occur
    if manifest["label"] == "EXECUTE" and manifest["T_E_T_status"] in ("MISSING", "UNKNOWN"):
        raise EpisodeWriteError("EXECUTE label with missing/unknown T_E_T is forbidden")
    if manifest["terminal_decision"] == "EXECUTE" and manifest["contact_authority"] in (
        "MISSING",
        "UNKNOWN",
        "NOT_EVALUATED",
    ):
        raise EpisodeWriteError("EXECUTE decision without contact authority is forbidden")


class EpisodeWriter:
    def __init__(self, episodes_root: str | Path):
        self.root = Path(episodes_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        manifest: dict,
        authority_snapshot: dict,
        resolved_config: dict,
        input_hashes: list[dict],
        timeseries=None,  # pandas.DataFrame or None
        events: list[dict] | None = None,
        metrics: dict | None = None,
        safety_decision: dict | None = None,
        gate_result: dict | None = None,
        failure_context: dict | None = None,
        stdout_text: str = "",
    ) -> Path:
        manifest = dict(manifest)
        manifest.setdefault("authority_snapshot_sha256", sha256_canonical_json(authority_snapshot))
        validate_manifest(manifest)
        ep_dir = self.root / manifest["episode_id"]
        if ep_dir.exists():
            raise EpisodeWriteError(f"episode dir already exists (immutable episodes): {ep_dir}")
        ep_dir.mkdir(parents=True)

        def _dump_json(name: str, obj) -> Path:
            p = ep_dir / name
            p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            return p

        written: list[Path] = []
        written.append(_dump_json("RUN_MANIFEST.json", manifest))
        written.append(_dump_json("AUTHORITY_SNAPSHOT.json", authority_snapshot))

        import yaml

        p_cfg = ep_dir / "RESOLVED_CONFIG.yaml"
        p_cfg.write_text(yaml.safe_dump(resolved_config, sort_keys=False, allow_unicode=True), encoding="utf-8")
        written.append(p_cfg)

        p_ih = ep_dir / "INPUT_HASHES.csv"
        with open(p_ih, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["path", "sha256", "role", "status"])
            w.writeheader()
            for row in input_hashes:
                w.writerow(
                    {
                        "path": row.get("path", ""),
                        "sha256": row.get("sha256", ""),
                        "role": row.get("role", ""),
                        "status": row.get("status", ""),
                    }
                )
        written.append(p_ih)

        p_ts = ep_dir / "TIMESERIES.parquet"
        if timeseries is not None:
            timeseries.to_parquet(p_ts, index=False)
        else:
            import pandas as pd

            pd.DataFrame({"t": []}).to_parquet(p_ts, index=False)
        written.append(p_ts)

        p_ev = ep_dir / "EVENTS.jsonl"
        with open(p_ev, "w", encoding="utf-8") as f:
            for ev in events or []:
                f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
        written.append(p_ev)

        written.append(_dump_json("METRICS.json", metrics or {}))
        written.append(_dump_json("SAFETY_DECISION.json", safety_decision or {"decision": "NOT_EVALUATED"}))
        written.append(_dump_json("GATE_RESULT.json", gate_result or {"gate": "NONE"}))
        written.append(
            _dump_json("FAILURE_CONTEXT.json", failure_context or {"failed": False, "failure_reason": None})
        )
        p_log = ep_dir / "STDOUT.log"
        p_log.write_text(stdout_text, encoding="utf-8")
        written.append(p_log)

        p_hm = ep_dir / "HASH_MANIFEST.csv"
        with open(p_hm, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["file", "sha256"])
            for p in written:
                w.writerow([p.name, sha256_file(p)])
        return ep_dir
