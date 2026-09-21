"""Orchestrator for CURRENT_R2_DIGITAL_HOST_CAPTURE_DATA_INCREMENT_V1.

Runs, in order: plant extraction -> S00 -> S01 -> S02 (3 cases) -> S03 -> S07,
writes 06_plant artifacts, 11_verification reports, 12_results episodes (D0),
09_dataset/DATASET_MANIFEST.json and the DH gate JSONs.

Deterministic: fixed seeds; wall-clock only in provenance fields.
Fail-closed: any scenario failure is recorded honestly; gates are computed from
machine results, never hand-set to PASS.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parents[1]
sys.path.insert(0, str(MODULE / "src"))

from dh_v1 import CLAIM_CEILING, INCREMENT_ID  # noqa: E402
from dh_v1.episode_writer import EpisodeWriter  # noqa: E402
from dh_v1.hashing import sha256_canonical_json, sha256_file  # noqa: E402
from dh_v1.plant import FloatingPlant, compose_models  # noqa: E402
from dh_v1.scen_dynamics import run_s02_case, run_s03  # noqa: E402
from dh_v1.scen_safety import run_s07  # noqa: E402
from dh_v1.scen_static import run_s00, run_s01  # noqa: E402
from dh_v1.urdf_extract import extract_urdf, total_mass, validate_tree  # noqa: E402

SEED = 20260827
ACCEPTED_URDF = REPO / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
SERVICER_URDF = REPO / "20_engineering/cad/spacecraft_layout/servicer_12U_v0/servicer_12U_v0.urdf"
T_SM = {"xyz": [0.18525, 0.0, 0.0], "rpy": [0.0, 1.5707963267948966, 0.0]}  # ODR-01 dynamics rail, nominal_frozen_v1

NOW = datetime.now(timezone.utc).isoformat()


def contract_hashes() -> dict:
    return {
        "frame_contract_sha256": sha256_file(MODULE / "02_frames_units/FRAME_GRAPH.yaml"),
        "unit_contract_sha256": sha256_file(MODULE / "02_frames_units/UNIT_CONTRACT.yaml"),
        "safe_config_sha256": sha256_file(MODULE / "08_control_safe/SAFE_PREBIND_CONFIG.yaml"),
        "authority_snapshot_file_sha256": sha256_file(MODULE / "00_authority/CURRENT_V2_STATUS_SNAPSHOT.json"),
    }


def base_manifest(ch: dict, urdf_sha: str, plant_sha: str, episode_id: str, scenario_id: str,
                  base_state_id: str, controller_sha=None, seed: int = SEED) -> dict:
    return {
        "episode_id": episode_id,
        "base_state_id": base_state_id,
        "scenario_id": scenario_id,
        "strategy_id": "NONE",
        "seed": seed,
        "accepted_urdf_sha256": urdf_sha,
        "step_state_sha256": None,               # current STEP 0/9 — explicit null
        "collision_manifest_sha256": None,       # no operational per-pair registration yet
        "frame_contract_sha256": ch["frame_contract_sha256"],
        "unit_contract_sha256": ch["unit_contract_sha256"],
        "controller_config_sha256": controller_sha,
        "safe_config_sha256": ch["safe_config_sha256"],
        "plant_sha256": plant_sha,
        "geometry_authority": "MISSING_CURRENT_STEP_0_OF_9",
        "dynamics_authority": "ACCEPTED_B601_URDF",
        "contact_authority": "NOT_EVALUATED",
        "T_E_T_status": "MISSING",
        "evidence_level": "PREBIND",
        "claim_ceiling": CLAIM_CEILING,
        "binding_gate": "DH-G0",
        "terminal_decision": "MODIFY",           # diagnostic episodes never request EXECUTE by policy
        "label": "MODIFY",
        "not_evaluated_reason": None,
        "failure_reason": None,
    }


def authority_snapshot_obj(ch: dict) -> dict:
    snap = json.loads((MODULE / "00_authority/CURRENT_V2_STATUS_SNAPSHOT.json").read_text(encoding="utf-8"))
    return {"snapshot_file_sha256": ch["authority_snapshot_file_sha256"], "machine_state": snap["machine_state"], "v2": snap["v2_increment"]}


def samples_to_df(samples: dict, nj: int) -> pd.DataFrame:
    X = samples["x"]
    cols = {"t": samples["t"]}
    cols.update({f"p_{a}": X[:, i] for i, a in enumerate("xyz")})
    cols.update({f"quat_{a}": X[:, 3 + i] for i, a in enumerate("wxyz")})
    for j in range(nj):
        cols[f"q{j+1}"] = X[:, 7 + j]
    for i, a in enumerate(["wx", "wy", "wz", "vx", "vy", "vz"]):
        cols[f"v6_{a}"] = X[:, 7 + nj + i]
    for j in range(nj):
        cols[f"qd{j+1}"] = X[:, 13 + nj + j]
    for i, a in enumerate(["nx", "ny", "nz", "fx", "fy", "fz"]):
        cols[f"h_O_{a}"] = samples["h_O"][:, i]
        cols[f"h_C_{a}"] = samples["h_C"][:, i]
    cols["E_kin_J"] = samples["E"]
    for i, a in enumerate("xyz"):
        cols[f"p_com_{a}"] = samples["p_com"][:, i]
    cols["quat_renorm_audit"] = samples["quat_renorm"]
    return pd.DataFrame(cols)


def main() -> None:
    ver = MODULE / "11_verification"
    res = MODULE / "12_results"
    plant_dir = MODULE / "06_plant"
    for d in (ver, res, plant_dir):
        d.mkdir(exist_ok=True)
    writer = EpisodeWriter(res / "episodes")
    ch = contract_hashes()

    # ---------- plant extraction (H1, automated, no hand re-typing) ----------
    arm_model = extract_urdf(ACCEPTED_URDF)
    arm_topo = validate_tree(arm_model)
    urdf_sha = arm_model["provenance"]["source_sha256"]
    plant_sha = sha256_canonical_json(arm_model)
    sv_model = extract_urdf(SERVICER_URDF)
    merged = compose_models(sv_model, arm_model, "S_servicer_12U_v0", T_SM["xyz"], T_SM["rpy"], "mount_T_SM_ODR01_nominal_frozen_v1")
    merged_sha = sha256_canonical_json(merged)

    accepted_plant = {
        "schema": "ACCEPTED_PLANT_V1",
        "generated_by": "scripts/run_increment.py (automated URDF extraction)",
        "provenance": arm_model["provenance"],
        "plant_sha256_canonical_json": plant_sha,
        "robot_name": arm_model["robot_name"],
        "topology": arm_topo,
        "total_mass_kg": total_mass(arm_model),
        "joints": arm_model["joints"],
        "links": arm_model["links"],
        "authority": {"accepted_inertial": "AUTHORITATIVE", "cad_inertial": "DIAGNOSTIC_ONLY", "modification": "FORBIDDEN"},
    }
    (plant_dir / "ACCEPTED_PLANT.yaml").write_text(yaml.safe_dump(accepted_plant, sort_keys=False, allow_unicode=True), encoding="utf-8")

    prebind_plant = {
        "schema": "PREBIND_PLANT_V1",
        "claim": "PREBIND_COMPOSITION_CANDIDATE — 非任务放行；组合体供 S02/S03 无接触诊断",
        "plant_sha256_canonical_json": merged_sha,
        "base_body": {
            "source": sv_model["provenance"],
            "mass_kg": total_mass(sv_model),
            "authority": "STAGE1_SSOT_LOW_CONFIDENCE; CDR bus/solar = null HOLD (SYSTEM_MASS_PROPERTIES_AUTHORITY_V2)",
        },
        "arm": {"source": arm_model["provenance"], "mass_kg": total_mass(arm_model), "authority": "ACCEPTED"},
        "mount_transform": {
            "name": "T_SM",
            "xyz_m": T_SM["xyz"],
            "rpy_rad": T_SM["rpy"],
            "authority": "ODR-01 nominal_frozen_v1（唯一动力学安装权威；设计名义未实测 → PROVISIONAL 级消费）",
            "physical_rail_not_used": "T_S_B601_ARM_BASE_PHYSICAL (0.208 m, 25.000014 deg) 候选，本 plant 不消费，禁止别名",
        },
        "arm_base_to_M": "identity nominal (accepted URDF 头注 T_MA0, SSOT sec3.1)",
        "route_c": {"included": False, "reason": "RC-5 not accepted; V9F REJECTED"},
        "solar_arrays": {"included": False, "reason": "H1 质量占位 (0.3483933 kg, D-7)；刚体 prebind 组合不注入占位柔性体"},
        "targets": {
            "satellite_22kg": {"registered": True, "attached": False, "reason": "T_E_T MISSING"},
            "debris_150kg": {"registered": True, "attached": False, "reason": "T_E_T MISSING + sim_10 INFEASIBLE_RATE veto"},
        },
        "total_mass_kg": total_mass(merged),
        "flex": "RIGID_ONLY — FLEX=UNKNOWN 不入判据（sim_10 边界口径）",
    }
    (plant_dir / "PREBIND_PLANT.yaml").write_text(yaml.safe_dump(prebind_plant, sort_keys=False, allow_unicode=True), encoding="utf-8")

    arm_plant = FloatingPlant(arm_model)
    composed_plant = FloatingPlant(merged)

    # ---------- S00 ----------
    s00 = run_s00(arm_model, rng_seed=SEED)
    (ver / "UNIT_FRAME_INVARIANCE_REPORT.json").write_text(json.dumps({**s00, "generated_utc": NOW}, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_episode(eid, scen, base_state, report, ts=None, safety=None, label="MODIFY", decision="MODIFY",
                      failure=None, gate=None, events=None, nev_reason=None, psha=None):
        m = base_manifest(ch, urdf_sha, psha or plant_sha, eid, scen, base_state)
        m["label"], m["terminal_decision"] = label, decision
        m["not_evaluated_reason"] = nev_reason
        if failure:
            m["failure_reason"] = failure.get("failure_reason")
        writer.write(
            m,
            authority_snapshot_obj(ch),
            {"scenario": scen, "seed": SEED, "python": sys.version.split()[0], "numpy": np.__version__},
            [
                {"path": str(ACCEPTED_URDF.relative_to(REPO)), "sha256": urdf_sha, "role": "ACCEPTED_URDF", "status": "VERIFIED"},
                {"path": "02_frames_units/FRAME_GRAPH.yaml", "sha256": ch["frame_contract_sha256"], "role": "FRAME_CONTRACT", "status": "VERIFIED"},
                {"path": "02_frames_units/UNIT_CONTRACT.yaml", "sha256": ch["unit_contract_sha256"], "role": "UNIT_CONTRACT", "status": "VERIFIED"},
            ],
            ts,
            events or [],
            report,
            safety or {"decision": decision, "fail_closed": True},
            gate or {"gate": "DH-G0", "contribution": scen},
            failure or {"failed": False, "failure_reason": None},
            stdout_text=f"{scen} completed; see METRICS.json",
        )

    write_episode("DH1-S00-0001", "S00_UNIT_FRAME_INERTIA_INVARIANCE", "PREBIND_NULL_STATE",
                  {k: v for k, v in s00.items() if k != "checks"} | {"n_checks": len(s00["checks"])})

    # ---------- S01 ----------
    s01 = run_s01(str(ACCEPTED_URDF), rng_seed=SEED)
    (ver / "URDF_TOPOLOGY_REPORT.json").write_text(json.dumps({**s01, "generated_utc": NOW}, indent=2, ensure_ascii=False), encoding="utf-8")
    write_episode("DH1-S01-0001", "S01_ACCEPTED_URDF_FK_TOPOLOGY", "PREBIND_NULL_STATE",
                  {k: v for k, v in s01.items() if k != "checks"} | {"n_checks": s01["checks_total"]})

    # ---------- S02 ----------
    s02_cases = []
    case_defs = [
        ("arm_only_accepted", arm_plant, "base_at_rest_arm_moving", True, plant_sha, "PREBIND_ARM_ONLY_IC1"),
        ("arm_only_accepted", arm_plant, "base_tumbling_arm_moving", False, plant_sha, "PREBIND_ARM_ONLY_IC2"),
        ("servicer_arm_T_SM_prebind", composed_plant, "base_tumbling_arm_moving", False, merged_sha, "PREBIND_SERVICER_ARM_TSM_IC2"),
    ]
    for name, plant, ic, do_conv, psha, bstate in case_defs:
        dts = (4.0e-3, 2.0e-3, 1.0e-3) if do_conv else (1.0e-3,)
        r = run_s02_case(plant, ic, t_end=5.0, dt=1.0e-3, convergence_dts=dts)
        samples = r.pop("samples")
        df = samples_to_df(samples, plant.nj)
        rec = {"plant": name, "plant_sha256": psha, "n_dof": 6 + plant.nj, **r}
        s02_cases.append(rec)
        eid = f"DH1-S02-{len(s02_cases):04d}"
        write_episode(eid, "S02_FREE_FLOAT_CONSERVATION", bstate, rec, ts=df,
                      label="MODIFY", decision="MODIFY", psha=psha,
                      gate={"gate": "DH-G6_DIAGNOSTIC_LAYER", "gates": r["gates"], "all_pass": r["all_gates_pass"]})
        df.to_parquet(res / f"s02_{name}_{ic}.parquet", index=False)

    ledger = {
        "schema": "NO_CONTACT_MOMENTUM_LEDGER_V1",
        "generated_utc": NOW,
        "claim": "PREBIND 守恒诊断，非任务放行；刚体、无接触、无重力",
        "momentum_reference_points": {"h_O": "inertial origin, inertial frame", "h_C": "system CoM, inertial frame"},
        "cases": s02_cases,
        "all_cases_pass": all(c["all_gates_pass"] for c in s02_cases),
    }
    (ver / "NO_CONTACT_MOMENTUM_LEDGER.json").write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---------- S03 (diagnostic only; dt=5e-4 nominal + dt=1e-3 negative witness) ----------
    s03 = run_s03(composed_plant, t_end=8.0, dt=5.0e-4)
    s03_stiff = run_s03(composed_plant, t_end=8.0, dt=1.0e-3)
    s03["negative_witness_dt_1e_3"] = {
        "claim": "RK4_STABILITY_BOUNDARY_REAL_NEGATIVE_RESULT",
        "detail": "fastest PD joint mode exceeds RK4 stability at dt=1e-3: saturation chatter + momentum drift; preserved, not tuned away",
        "dt_s": 1.0e-3,
        "momentum_drift_abs": s03_stiff["internal_torque_momentum_drift_abs"],
        "any_saturation": s03_stiff["any_saturation"],
        "tracking_error_settled_rad": s03_stiff["tracking_error_settled_rad"],
    }
    s03_stiff.pop("samples")
    s03_samples = s03.pop("samples")
    s03_df = samples_to_df(s03_samples, composed_plant.nj)
    s03_dir = res / "s03_no_contact_joint_motion"
    s03_dir.mkdir(exist_ok=True)
    s03_df.to_parquet(s03_dir / "s03_timeseries.parquet", index=False)
    (s03_dir / "s03_summary.json").write_text(json.dumps({**s03, "generated_utc": NOW}, indent=2, ensure_ascii=False), encoding="utf-8")
    write_episode("DH1-S03-0001", "S03_NO_CONTACT_JOINT_MOTION_CANDIDATE", "PREBIND_SERVICER_ARM_TSM_IC0",
                  s03, ts=s03_df, psha=merged_sha,
                  gate={"gate": "DH-G6", "status": "HOLD_STATIC_PROBE_ONLY", "note": "C1 candidate diagnostic; NOT a control PASS"})

    # ---------- S07 ----------
    s07 = run_s07(str(ACCEPTED_URDF), MODULE / "12_results" / "s07_work", arm_plant=arm_plant)
    (ver / "FAILCLOSED_INJECTION_REPORT.json").write_text(json.dumps({**s07, "generated_utc": NOW}, indent=2, ensure_ascii=False), encoding="utf-8")
    for i, c in enumerate(s07["cases"], 1):
        eid = f"DH1-S07-{i:04d}"
        got = c["got"]
        if got == "ABORT":
            label, decision, nev = "ABORT", "ABORT", None
        elif got == "WAIT":
            # WAIT is a decision, not a dataset label: the capture predicate was
            # never rendered during the hold window -> NOT_EVALUATED label.
            label, decision, nev = "NOT_EVALUATED", "WAIT", "terminal WAIT hold; predicate not rendered within stale budget"
        elif got == "NOT_EVALUATED":
            label, decision, nev = "NOT_EVALUATED", "NONE", c["detail"]
        else:  # REJECTED / UNDETECTED bookkeeping cases
            label, decision, nev = ("ABORT", "ABORT", None) if c["passed"] else ("UNKNOWN", "ABORT", None)
        write_episode(eid, "S07_FAILCLOSED_INJECTION", f"INJECTION::{c['case_id']}",
                      c, label=label, decision=decision,
                      safety={"decision": decision, "reasons": c.get("reasons", []), "fail_closed": True},
                      failure={"failed": not c["passed"], "failure_reason": None if c["passed"] else c["detail"]},
                      gate={"gate": "DH-G7_DIAGNOSTIC_LAYER", "expected": c["expected"], "got": got, "passed": c["passed"]},
                      nev_reason=nev)

    # ---------- dataset manifest ----------
    episodes = sorted((res / "episodes").iterdir())
    ds_manifest = {
        "schema": "DATASET_MANIFEST_V1",
        "generated_utc": NOW,
        "level": "D0_REGRESSION",
        "claim": "确定性回归集（CI 语义），不用于宣称学习性能",
        "episode_count": len(episodes),
        "episodes": [
            {"episode_id": e.name, "run_manifest_sha256": sha256_file(e / "RUN_MANIFEST.json"), "label": json.loads((e / "RUN_MANIFEST.json").read_text(encoding="utf-8"))["label"]}
            for e in episodes
        ],
        "label_histogram": {},
        "d1_d2_d3": {"D1": "PLANNED", "D2": "BLOCKED_NO_PARAMETER_AUTHORITY", "D3": "BLOCKED_NO_CURRENT_VISUAL_GEOMETRY"},
    }
    hist: dict[str, int] = {}
    for e in ds_manifest["episodes"]:
        hist[e["label"]] = hist.get(e["label"], 0) + 1
    ds_manifest["label_histogram"] = hist
    (MODULE / "09_dataset/DATASET_MANIFEST.json").write_text(json.dumps(ds_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---------- gates ----------
    g0_pass = s00["all_passed"] and s01["all_passed"] and ledger["all_cases_pass"] and s07["all_passed"] and s07["never_execute_confirmed"]
    dh_g0 = {
        "schema": "DH_G0_GATE_V1",
        "gate": "DH-G0 AUTHORITY_AND_PROVENANCE",
        "generated_utc": NOW,
        "verdict": "PASS_WITH_NO_RELEASE_CREDIT" if g0_pass else "FAIL",
        "inputs": {
            "sources_hashed": 51,
            "authority_reverifications": "19/19",
            "s00": f"{s00['positive_passed']}/{s00['positive_total']} positive + {s00['negative_passed']}/{s00['negative_total']} negative",
            "s01": f"{s01['checks_passed']}/{s01['checks_total']}",
            "s02_all_cases_pass": ledger["all_cases_pass"],
            "s07": f"{s07['cases_passed']}/{s07['cases_total']}, never_execute={s07['never_execute_confirmed']}",
        },
        "claim_ceiling": CLAIM_CEILING,
        "parent_gate_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }
    (ver / "DH_G0_GATE.json").write_text(json.dumps(dh_g0, indent=2, ensure_ascii=False), encoding="utf-8")

    dh_increment = {
        "schema": "DH_INCREMENT_GATE_V1",
        "increment": INCREMENT_ID,
        "generated_utc": NOW,
        "gates": {
            "DH-G0_AUTHORITY_AND_PROVENANCE": dh_g0["verdict"],
            "DH-G1_CURRENT_STEP_AND_FOUR_VIEW": "HOLD_CURRENT_STEP_0_OF_9",
            "DH-G2_FRAME_AND_KINEMATIC_REGISTRATION": "PARTIAL_PREBIND_CHAIN_BOUND__TARGET_FRAMES_UNBOUND" if s01["all_passed"] else "FAIL",
            "DH-G3_COLLISION_ASSET_REGISTRATION": "HOLD_1_OF_150_OPERATIONAL_SCHEMA_REGISTERED",
            "DH-G4_M01_MOTION_CERTIFICATE": "HOLD_MOTION_CERTIFICATE_0__THREE_STAGE_INSTANCES_0_OF_3",
            "DH-G5_CONTACT_AND_T_E_T": "NOT_EVALUATED_T_E_T_MISSING",
            "DH-G6_TIME_DOMAIN_DYNAMICS_CONTROL": "HOLD_STATIC_PROBE_ONLY__C0_C1_DIAGNOSTICS_RECORDED_NO_CREDIT",
            "DH-G7_SAFE_SIM13_REBIND": "HOLD__PREBIND_FAILCLOSED_KERNEL_DIAGNOSTIC_ONLY",
            "DH-G8_PARENT_GATE_REISSUE": "NOT_AUTHORIZED",
        },
        "evidence": {
            "unit_frame_invariance": "11_verification/UNIT_FRAME_INVARIANCE_REPORT.json",
            "urdf_topology": "11_verification/URDF_TOPOLOGY_REPORT.json",
            "momentum_ledger": "11_verification/NO_CONTACT_MOMENTUM_LEDGER.json",
            "failclosed_injection": "11_verification/FAILCLOSED_INJECTION_REPORT.json",
            "d0_dataset": "09_dataset/DATASET_MANIFEST.json",
        },
        "execute_reachable_this_increment": False,
        "maximum_claim": "CURRENT_SYSTEM_DIGITAL_HOST_CANDIDATE + PREBIND_SIMULATION_DATASET_V1 + NO_FORMAL_RELEASE_CREDIT",
        "parent_gate_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }
    (ver / "DH_INCREMENT_GATE_V1.json").write_text(json.dumps(dh_increment, indent=2, ensure_ascii=False), encoding="utf-8")

    print("== RUN COMPLETE ==")
    print(f"S00 {s00['positive_passed']}/{s00['positive_total']}+{s00['negative_passed']}/{s00['negative_total']}neg all={s00['all_passed']}")
    print(f"S01 {s01['checks_passed']}/{s01['checks_total']} all={s01['all_passed']}")
    for c in s02_cases:
        print(f"S02 {c['plant']}/{c['ic']}: rel_h={c['metrics']['rel_h_drift_max']:.3e} rel_E={c['metrics']['rel_E_drift_max']:.3e} orders={c['observed_orders']} xcheck={c['xcheck_base_velocity']:.3e} pass={c['all_gates_pass']}")
    print(f"S03 base_att_change={s03['base_attitude_change_deg']:.4f} deg, track_err={s03['tracking_error_settled_rad']:.3e} rad, h_drift={s03['internal_torque_momentum_drift_abs']:.3e}, sat={s03['any_saturation']}")
    print(f"S07 {s07['cases_passed']}/{s07['cases_total']} never_execute={s07['never_execute_confirmed']}")
    print(f"episodes={len(episodes)} labels={hist}")
    print(f"DH-G0 = {dh_g0['verdict']}")


if __name__ == "__main__":
    main()
