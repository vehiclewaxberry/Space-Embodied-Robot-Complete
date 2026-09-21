"""Build e21 current-M7-R2 non-release diagnostics.

The module is fail-closed and deliberately narrow:
* accepted URDF is read-only;
* no stock sim11 configuration loader, legacy panel card, legacy FFR, A2,
  contact, target, collision or mission input is read;
* the two placement hypotheses are evaluated independently and never selected
  or averaged;
* current R2 wings enter the free-floating lanes only as deployed-locked rigid
  mass properties inside the V3_R2/C07 fixed residual;
* the fixed-base R2 ROM is a separate reproduction and never enters dynamics.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.integrate import solve_ivp

# This module dynamically executes the hash-bound sim05 parser.  Make the
# no-cache contract intrinsic rather than relying only on the documented -B.
sys.dont_write_bytecode = True


MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parents[1]
RESULTS_ROOT = MODULE_ROOT / "results"
PREFIX = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics"
GENERATED_LOCAL = "2026-08-23T15:00:00+08:00"
VERDICT = (
    "E21_M7_R2_MIXED_ARM_PLACEMENT_DETECTED__CURRENT_R2_RIGID_WING_"
    "FREE_FLOATING_ARM_ONLY_TWO_PLACEMENT_SENSITIVITY_AND_FIXED_BASE_ROM_"
    "REPRODUCTION_CLOSED__SINGLE_PLACEMENT_R2_FULL_FLEX_COUPLING_E15_"
    "HARNESS_CONTACT_MISSION_PRODUCTION_AND_FLIGHT_HOLD"
)

AUTHORITY_REL = f"{PREFIX}/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml"
CAMPAIGN_REL = f"{PREFIX}/config/E21_CURRENT_R2_RIGID_DIAGNOSTIC_CAMPAIGN_V1.yaml"
URDF_REL = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
M07_REL = "30_simulation/e17_b601_mission_trajectory_candidates/results/candidates/M07_22_ARM_ONLY_QUINTIC_V1.csv"
V2_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml"
V3_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
TRANSFORMS_REL = "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties/CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml"
MODES_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2_MODES.json"
FLEX_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml"
SOLAR_MASS_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json"
B601_MODEL_REL = "30_simulation/sim_05_free_floating_arm/b601_model.py"

STATIC_ARTIFACTS = (
    f"{PREFIX}/README.md",
    AUTHORITY_REL,
    CAMPAIGN_REL,
    f"{PREFIX}/docs/preregistration.md",
    f"{PREFIX}/docs/method_and_limitations.md",
    f"{PREFIX}/src/build_e21_diagnostics.py",
    f"{PREFIX}/tests/validate_e21_diagnostics.py",
)

PLACEMENTS = {
    "ODR01_DYNAMICS_T_SM": np.array(
        [[0.0, 0.0, 1.0, 0.18525],
         [0.0, 1.0, 0.0, 0.0],
         [-1.0, 0.0, 0.0, 0.0],
         [0.0, 0.0, 0.0, 1.0]], dtype=float),
    "WP11_PHYSICAL_GEOMETRY_CONTEXT": np.array(
        [[0.0, 0.0, 1.0, 0.208],
         [0.422618483193, 0.906307683772, 0.0, 0.0],
         [-0.906307683772, 0.422618483193, 0.0, 0.0],
         [0.0, 0.0, 0.0, 1.0]], dtype=float),
}


def project_path(relative: str) -> Path:
    return PROJECT_ROOT / Path(relative)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def load_yaml(relative: str) -> Any:
    return yaml.safe_load(project_path(relative).read_text(encoding="utf-8"))


def load_json(relative: str) -> Any:
    return json.loads(project_path(relative).read_text(encoding="utf-8"))


def result_rel(name: str) -> str:
    return f"{PREFIX}/results/{name}"


def artifact_record(relative: str, data: bytes | None = None) -> dict[str, Any]:
    blob = project_path(relative).read_bytes() if data is None else data
    return {"path": relative.replace("\\", "/"), "sha256": sha256_bytes(blob), "bytes": len(blob)}


def import_source(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, project_path(relative))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_input_manifest(campaign: dict[str, Any]) -> dict[str, Any]:
    records = []
    for row in campaign["source_register"]:
        path = project_path(row["path"])
        actual = sha256_file(path)
        expected = str(row["sha256"]).upper()
        if actual != expected:
            raise RuntimeError(f"source hash drift: {row['name']}: {actual} != {expected}")
        records.append({
            "name": row["name"], "path": row["path"], "sha256": actual,
            "expected_sha256": expected, "exact_hash_match": True,
            "bytes": path.stat().st_size, "role": row["role"],
        })

    e15 = load_json("30_simulation/e15_ancf_certification/results/gate_summary.json")
    handoff = load_json(
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp13_embodied_contract/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_R2.json"
    )
    contract_text = project_path(
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp13_embodied_contract/EMBODIED_MECHANICAL_CONTRACT_R2.yaml"
    ).read_text(encoding="utf-8")
    if e15["overall"] != "REPEAT_ANCF_CERTIFICATION":
        raise RuntimeError("e15 debt drift")
    if handoff["review_status"] != "PENDING_OWNER_REVIEW" or handoff["next_stage_authorized"] is not False:
        raise RuntimeError("R2 owner-review boundary drift")
    if "R2-HRN-04 closure attempt FAILED" not in contract_text:
        raise RuntimeError("R2-HRN-04 negative result boundary drift")
    return {
        "schema": "E21_INPUT_MANIFEST_V1", "generated_local": GENERATED_LOCAL,
        "record_count": len(records), "records": records,
        "all_exact_hash_match": all(r["exact_hash_match"] for r in records),
        "source_set_sha256": sha256_bytes(canonical_json_bytes(records)),
        "runtime_boundary": {
            "accepted_urdf_immutable": True,
            "legacy_r1_panel_card_read": False,
            "legacy_r1_panel_mass_read": False,
            "legacy_r1_ffr_constructed": False,
            "stock_sim11_config_loader_called": False,
            "scene_A2_read": False,
            "contact_metadata_read": False,
            "target_metadata_read": False,
            "target_attached": False,
        },
        "preserved_debts": {
            "e15": e15["overall"],
            "e15_cross_solver_max_relative_difference": e15["cross_solver_diagnostic"]["max_relative_difference"],
            "e15_gate_limit": e15["final_candidate_cross_solver"]["gate_limit"],
            "r2_harness_R2_HRN_04": "FAIL_REDESIGN_REQUIRED",
            "owner_review": handoff["review_status"],
            "next_stage_authorized": handoff["next_stage_authorized"],
        },
    }


def inertia_matrix(value: Any) -> np.ndarray:
    if isinstance(value, list):
        return np.asarray(value, dtype=float)
    return np.array([
        [value["Ixx"], value["Ixy"], value["Ixz"]],
        [value["Ixy"], value["Iyy"], value["Iyz"]],
        [value["Ixz"], value["Iyz"], value["Izz"]],
    ], dtype=float)


def steiner(mass: float, vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=float)
    return float(mass) * ((vector @ vector) * np.eye(3) - np.outer(vector, vector))


def combine_bodies(bodies: list[tuple[float, np.ndarray, np.ndarray]]) -> tuple[float, np.ndarray, np.ndarray]:
    mass = math.fsum(float(row[0]) for row in bodies)
    center = np.sum([float(m) * np.asarray(c, dtype=float) for m, c, _ in bodies], axis=0) / mass
    inertia = np.zeros((3, 3))
    for m, c, own in bodies:
        inertia += np.asarray(own, dtype=float) + steiner(m, np.asarray(c, dtype=float) - center)
    return float(mass), center, 0.5 * (inertia + inertia.T)


def arm_properties(b601, arm, q: np.ndarray, transform: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    base = arm.body["base_link"]
    bodies = [b601.transform_inertial(transform, base["mass"], base["cg"], base["I"])]
    for state in arm.link_com_states(q, T_base=transform):
        bodies.append((float(state["mass"]), np.asarray(state["c"], float), np.asarray(state["I"], float)))
    return combine_bodies(bodies)


def pose_vector(transform_ref: str, transform_card: dict[str, Any]) -> tuple[str, np.ndarray]:
    key = str(transform_ref).split(".")[-1]
    library = transform_card["transform_library"]["arm_named_pose_bindings"]
    if key not in library:
        raise RuntimeError(f"unresolved arm pose binding: {transform_ref}")
    return key, np.asarray(library[key]["q_rad"], dtype=float)


def build_placement_audit(b601, arm, campaign: dict[str, Any]) -> dict[str, Any]:
    thresholds = campaign["thresholds"]
    ledgers = {"V2": load_yaml(V2_REL), "V3_R2": load_yaml(V3_REL)}
    transform_card = load_yaml(TRANSFORMS_REL)
    ledger_results = []
    compact_rows: dict[str, dict[str, Any]] = {}
    for ledger_name, ledger in ledgers.items():
        configs = ledger["configurations"]
        rows = []
        if [c["configuration_id"] for c in configs] != [f"C{i:02d}" for i in range(1, 10)]:
            raise RuntimeError(f"{ledger_name} configuration set drift")
        for config in configs:
            arm_row = next(x for x in config["composition"] if x["component_id"] == "b601_complete_arm_including_gripper_urdf_links")
            pose_key, q = pose_vector(arm_row["transform_ref"], transform_card)
            ledger_mass = float(arm_row["mass_kg"])
            ledger_cg = np.asarray(arm_row["com_S_m"], dtype=float)
            ledger_I = inertia_matrix(arm_row["inertia_about_own_com_S_kg_m2"])
            evaluations = {}
            for placement_name, transform in PLACEMENTS.items():
                mass, cg, own_I = arm_properties(b601, arm, q, transform)
                mass_error = abs(mass - ledger_mass)
                cg_error = cg - ledger_cg
                inertia_error = own_I - ledger_I
                matched = (
                    mass_error <= 1.0e-12
                    and float(np.linalg.norm(cg_error)) <= float(thresholds["arm_context_match_cg_m"])
                    and float(np.max(np.abs(inertia_error))) <= float(thresholds["arm_context_match_inertia_kg_m2"])
                )
                evaluations[placement_name] = {
                    "selected": False,
                    "computed_mass_kg": mass,
                    "computed_cg_S_m": cg.tolist(),
                    "computed_inertia_about_arm_cg_S_kg_m2": own_I.tolist(),
                    "ledger_mass_error_kg": mass_error,
                    "ledger_cg_error_vector_m": cg_error.tolist(),
                    "ledger_cg_error_norm_mm": float(np.linalg.norm(cg_error) * 1.0e3),
                    "ledger_inertia_error_kg_m2": inertia_error.tolist(),
                    "ledger_inertia_max_abs_error_kg_m2": float(np.max(np.abs(inertia_error))),
                    "within_preregistered_context_match_tolerance": bool(matched),
                }
            matches = [name for name, ev in evaluations.items() if ev["within_preregistered_context_match_tolerance"]]
            classification = matches[0] if len(matches) == 1 else ("AMBIGUOUS_BOTH" if len(matches) == 2 else "NO_CONTEXT_MATCH")
            row = {
                "configuration_id": config["configuration_id"], "configuration_name": config["name"],
                "pose_binding": pose_key, "q_rad": q.tolist(),
                "ledger_arm_mass_kg": ledger_mass, "ledger_arm_cg_S_m": ledger_cg.tolist(),
                "ledger_arm_inertia_about_own_cg_S_kg_m2": ledger_I.tolist(),
                "placement_evaluations": evaluations,
                "context_match_classification": classification,
                "configuration_declared_wrong": False,
            }
            rows.append(row)
            compact_rows.setdefault(config["configuration_id"], {})[ledger_name] = {
                "mass": ledger_mass, "cg": ledger_cg.tolist(), "I": ledger_I.tolist(),
                "pose": pose_key, "classification": classification,
            }
        ledger_results.append({"ledger": ledger_name, "configuration_count": len(rows), "rows": rows})

    carried = []
    for cid, pair in compact_rows.items():
        v2, v3 = pair["V2"], pair["V3_R2"]
        carried.append({
            "configuration_id": cid,
            "mass_exact": v2["mass"] == v3["mass"],
            "cg_exact": v2["cg"] == v3["cg"],
            "inertia_exact": v2["I"] == v3["I"],
            "pose_binding_exact": v2["pose"] == v3["pose"],
            "classification_exact": v2["classification"] == v3["classification"],
        })
    classes = {
        row["context_match_classification"]
        for ledger in ledger_results for row in ledger["rows"]
    }
    mixed = (
        "ODR01_DYNAMICS_T_SM" in classes
        and "WP11_PHYSICAL_GEOMETRY_CONTEXT" in classes
        and "NO_CONTEXT_MATCH" not in classes
        and "AMBIGUOUS_BOTH" not in classes
    )
    return {
        "schema": "E21_NINE_CONFIGURATION_ARM_PLACEMENT_AUDIT_V1",
        "generated_local": GENERATED_LOCAL,
        "placement_hypotheses": {
            name: {"transform_S_A0_rows": matrix.tolist(), "selected": False}
            for name, matrix in PLACEMENTS.items()
        },
        "ledger_count": 2, "configuration_count_per_ledger": 9,
        "placement_evaluation_count": 36,
        "ledgers": ledger_results,
        "v2_to_v3_r2_non_solar_arm_carry_forward": carried,
        "all_arm_rows_carried_verbatim": all(
            row["mass_exact"] and row["cg_exact"] and row["inertia_exact"] and row["pose_binding_exact"]
            for row in carried
        ),
        "mixed_placement_context_detected": mixed,
        "single_current_dynamics_consumption_semantics_resolved": False,
        "ODR01_invalidated": False,
        "any_configuration_declared_wrong": False,
        "branch_selected": False,
        "branches_averaged": False,
        "branch_delta_is_uncertainty": False,
        "verdict": "MIXED_LEDGER_ARM_PLACEMENT_CONTEXT_DETECTED__CONSUMPTION_SEMANTICS_UNRESOLVED_HOLD",
    }


def quintic(t: float | np.ndarray, duration: float, q0: np.ndarray, q1: np.ndarray):
    time = np.asarray(t, dtype=float)
    x = np.clip(time / duration, 0.0, 1.0)
    s = 10.0 * x**3 - 15.0 * x**4 + 6.0 * x**5
    inside = (time >= 0.0) & (time <= duration)
    sd = np.where(inside, (30.0 * x**2 - 60.0 * x**3 + 30.0 * x**4) / duration, 0.0)
    sdd = np.where(inside, (60.0 * x - 180.0 * x**2 + 120.0 * x**3) / duration**2, 0.0)
    delta = q1 - q0
    if time.ndim == 0:
        return q0 + delta * s, delta * sd, delta * sdd
    return q0[None, :] + s[:, None] * delta, sd[:, None] * delta, sdd[:, None] * delta


class M07Trajectory:
    def __init__(self, q0: np.ndarray, q1: np.ndarray, duration: float):
        self.q0 = np.asarray(q0, dtype=float)
        self.q1 = np.asarray(q1, dtype=float)
        self.duration = float(duration)

    def __call__(self, time: float):
        return quintic(float(time), self.duration, self.q0, self.q1)


def read_m07(campaign: dict[str, Any]) -> tuple[M07Trajectory, dict[str, Any]]:
    rows = list(csv.DictReader(project_path(M07_REL).read_text(encoding="utf-8").splitlines()))
    if len(rows) != 451:
        raise RuntimeError("M07 row count drift")
    times = np.array([float(row["t_s"]) for row in rows])
    q = np.array([[float(row[f"joint{i}_q_rad"]) for i in range(1, 7)] for row in rows])
    qd = np.array([[float(row[f"joint{i}_dq_rad_s"]) for i in range(1, 7)] for row in rows])
    qdd = np.array([[float(row[f"joint{i}_ddq_rad_s2"]) for i in range(1, 7)] for row in rows])
    if any(row["authority_class"] != "NON_RELEASE_DIAGNOSTIC_CANDIDATE" or row["released_for_mission_gate"].lower() != "false" for row in rows):
        raise RuntimeError("M07 non-release boundary drift")
    trajectory = M07Trajectory(q[0], q[-1], times[-1])
    qr, qdr, qddr = quintic(times, trajectory.duration, trajectory.q0, trajectory.q1)
    checks = {
        "source": M07_REL, "row_count": len(rows), "duration_s": trajectory.duration,
        "q_start_rad": trajectory.q0.tolist(), "q_end_rad": trajectory.q1.tolist(),
        "time_grid_uniform_0p01_s": bool(np.max(np.abs(np.diff(times) - 0.01)) <= 1.0e-14),
        "max_abs_q_reconstruction_error_rad": float(np.max(np.abs(qr - q))),
        "max_abs_qd_reconstruction_error_rad_s": float(np.max(np.abs(qdr - qd))),
        "max_abs_qdd_reconstruction_error_rad_s2": float(np.max(np.abs(qddr - qdd))),
        "all_rows_non_release": True,
        "gripper_or_contact_fields_consumed": False,
        "target_metadata_consumed": False,
    }
    limits = campaign["thresholds"]
    checks["all_numeric_rows_reproduced"] = (
        checks["max_abs_q_reconstruction_error_rad"] <= limits["trajectory_q_rad"]
        and checks["max_abs_qd_reconstruction_error_rad_s"] <= limits["trajectory_qd_rad_s"]
        and checks["max_abs_qdd_reconstruction_error_rad_s2"] <= limits["trajectory_qdd_rad_s2"]
    )
    return trajectory, checks


def skew(vector: np.ndarray) -> np.ndarray:
    x, y, z = np.asarray(vector, dtype=float)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def qmult(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    ])


def quat_to_R(quat: np.ndarray) -> np.ndarray:
    w, x, y, z = np.asarray(quat, dtype=float) / np.linalg.norm(quat)
    return np.array([
        [1.0 - 2.0*(y*y + z*z), 2.0*(x*y - w*z), 2.0*(x*z + w*y)],
        [2.0*(x*y + w*z), 1.0 - 2.0*(x*x + z*z), 2.0*(y*z - w*x)],
        [2.0*(x*z - w*y), 2.0*(y*z + w*x), 1.0 - 2.0*(x*x + y*y)],
    ])


class RigidArmOnlyModel:
    """Minimum rigid subset of the hash-bound sim11 equation method."""

    def __init__(self, arm, mount: np.ndarray, residual: tuple[float, np.ndarray, np.ndarray]):
        self.arm = arm
        self.mount = np.asarray(mount, dtype=float).copy()
        self.residual = (float(residual[0]), np.asarray(residual[1], float).copy(), np.asarray(residual[2], float).copy())
        base = self.arm.body["base_link"]
        base_body = (
            float(base["mass"]),
            self.mount[:3, :3] @ np.asarray(base["cg"], float) + self.mount[:3, 3],
            self.mount[:3, :3] @ np.asarray(base["I"], float) @ self.mount[:3, :3].T,
        )
        self.fixed_bodies = [("r2_locked_fixed_residual", *self.residual), ("arm_base_link", *base_body)]

    def geometry(self, q: np.ndarray) -> dict[str, Any]:
        fk = self.arm.fk(q, T_base=self.mount)
        bodies = []
        for name, mass, center, inertia in self.fixed_bodies:
            bodies.append({"name": name, "m": mass, "c": center, "I": inertia, "k": 0, "Jv": None, "Jw": None})
        for k, state in enumerate(self.arm.link_com_states(q, T_base=self.mount), start=1):
            bodies.append({"name": state["name"], "m": float(state["mass"]), "c": state["c"], "I": state["I"],
                           "k": k, "Jv": state["Jv"], "Jw": state["Jw"]})
        mass_matrix = np.zeros((12, 12))
        momentum = np.zeros((6, 12))
        for body in bodies:
            V = np.zeros((3, 12)); W = np.zeros((3, 12))
            V[:, :3] = np.eye(3); V[:, 3:6] = -skew(body["c"])
            W[:, 3:6] = np.eye(3)
            if body["Jv"] is not None:
                V[:, 6:12] = body["Jv"]; W[:, 6:12] = body["Jw"]
            body["V"], body["W"] = V, W
            mV = body["m"] * V
            mass_matrix += V.T @ mV + W.T @ body["I"] @ W
            momentum[:3] += mV
            momentum[3:] += skew(body["c"]) @ mV + body["I"] @ W
        return {"fk": fk, "bodies": bodies, "M": 0.5*(mass_matrix + mass_matrix.T), "A": momentum}

    def bias(self, geo: dict[str, Any], velocity: np.ndarray) -> np.ndarray:
        vb, wb, qd = velocity[:3], velocity[3:6], velocity[6:12]
        wxv = np.cross(wb, vb)
        axes = geo["fk"]["joint_axes"]
        origins = geo["fk"]["joint_origins"]
        omega_prev = np.zeros((6, 3)); accum = np.zeros(3)
        for i in range(6):
            omega_prev[i] = accum
            accum = accum + axes[i] * qd[i]
        axis_rate = np.cross(omega_prev, axes)
        origin_rate = np.zeros((6, 3))
        for i in range(6):
            for j in range(i):
                origin_rate[i] += qd[j] * np.cross(axes[j], origins[i] - origins[j])
        result = np.zeros(12)
        for body in geo["bodies"]:
            k, center, inertia = body["k"], body["c"], body["I"]
            if k == 0:
                accel = wxv + np.cross(wb, np.cross(wb, center))
                hdot = np.cross(wb, inertia @ wb)
            else:
                wrel = axes[:k].T @ qd[:k]
                alpha_rel = axis_rate[:k].T @ qd[:k]
                cdot = body["Jv"] @ qd
                arel = np.zeros(3)
                for i in range(k):
                    arel += qd[i] * (
                        np.cross(axis_rate[i], center - origins[i])
                        + np.cross(axes[i], cdot - origin_rate[i])
                    )
                accel = wxv + np.cross(wb, np.cross(wb, center)) + 2.0*np.cross(wb, cdot) + arel
                ws = wb + wrel
                hdot = (
                    inertia @ alpha_rel + np.cross(wrel, inertia @ ws)
                    - inertia @ np.cross(wrel, ws) + np.cross(wb, inertia @ ws)
                )
            result += body["V"].T @ (body["m"] * accel) + body["W"].T @ hdot
        return result

    def base_velocity(self, geo: dict[str, Any], qd: np.ndarray) -> np.ndarray:
        return np.linalg.solve(geo["A"][:, :6], -(geo["A"][:, 6:12] @ qd))

    def accelerations_and_tau(self, geo: dict[str, Any], velocity: np.ndarray, qdd: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        mass = geo["M"]
        bias = self.bias(geo, velocity)
        acceleration = np.zeros(12)
        acceleration[:6] = np.linalg.solve(mass[:6, :6], -bias[:6] - mass[:6, 6:12] @ qdd)
        acceleration[6:12] = qdd
        tau = mass[6:12] @ acceleration + bias[6:12]
        return acceleration, tau

    def momentum_inertial(self, r: np.ndarray, quat: np.ndarray, geo: dict[str, Any], velocity: np.ndarray) -> np.ndarray:
        rotation = quat_to_R(quat)
        vb, wb, qd = velocity[:3], velocity[3:6], velocity[6:12]
        P = np.zeros(3); L = np.zeros(3)
        for body in geo["bodies"]:
            vrel = body["Jv"] @ qd if body["Jv"] is not None else np.zeros(3)
            wrel = body["Jw"] @ qd if body["Jw"] is not None else np.zeros(3)
            vS = vb + np.cross(wb, body["c"]) + vrel
            wS = wb + wrel
            rI = r + rotation @ body["c"]
            vI = rotation @ vS
            P += body["m"] * vI
            L += rotation @ body["I"] @ rotation.T @ (rotation @ wS) + body["m"] * np.cross(rI, vI)
        return np.concatenate([P, L])

    def system_mass_properties(self, q: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        geo = self.geometry(q)
        return combine_bodies([(b["m"], b["c"], b["I"]) for b in geo["bodies"]])

    def integrate(self, trajectory: M07Trajectory, *, rtol: float, atol: float, n_out: int) -> dict[str, Any]:
        def rhs(time: float, state: np.ndarray) -> np.ndarray:
            r, quat = state[:3], state[3:7]
            q, qd, qdd = trajectory(time)
            geo = self.geometry(q)
            base = self.base_velocity(geo, qd)
            velocity = np.concatenate([base, qd])
            _, tau = self.accelerations_and_tau(geo, velocity, qdd)
            qn = quat / np.linalg.norm(quat)
            derivative = np.zeros_like(state)
            derivative[:3] = quat_to_R(qn) @ base[:3]
            derivative[3:7] = 0.5 * qmult(qn, np.array([0.0, *base[3:6]]))
            derivative[7] = float(tau @ qd)
            return derivative

        y0 = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0])
        times = np.linspace(0.0, trajectory.duration, n_out)
        solution = solve_ivp(rhs, (0.0, trajectory.duration), y0, t_eval=times, method="Radau", rtol=rtol, atol=atol)
        if not solution.success:
            raise RuntimeError(solution.message)
        r = solution.y[:3].T
        qraw = solution.y[3:7].T
        qnorm_raw = np.linalg.norm(qraw, axis=1)
        quat = qraw / qnorm_raw[:, None]
        work = solution.y[7]
        Vb = np.zeros((n_out, 6)); energy = np.zeros(n_out); momentum = np.zeros((n_out, 6))
        tau = np.zeros((n_out, 6)); min_eig = np.full(n_out, np.inf); joints = np.zeros((n_out, 6))
        for index, time in enumerate(times):
            q, qd, qdd = trajectory(time); joints[index] = q
            geo = self.geometry(q)
            Vb[index] = self.base_velocity(geo, qd)
            velocity = np.concatenate([Vb[index], qd])
            _, tau[index] = self.accelerations_and_tau(geo, velocity, qdd)
            energy[index] = 0.5 * velocity @ (geo["M"] @ velocity)
            momentum[index] = self.momentum_inertial(r[index], quat[index], geo, velocity)
            min_eig[index] = float(np.linalg.eigvalsh(geo["M"])[0])
        attitude = np.degrees(2.0 * np.arccos(np.clip(np.abs(quat[:, 0]), 0.0, 1.0)))
        return {
            "t": times, "r": r, "quat": quat, "raw_quat_norm": qnorm_raw,
            "Vb": Vb, "E": energy, "W": work, "hI": momentum, "tau": tau,
            "dev_deg": attitude, "mass_matrix_min_eig": min_eig, "joints": joints,
            "nfev": int(solution.nfev), "initial_state_exact": y0.tolist(),
        }


def c07_total_properties() -> tuple[float, np.ndarray, np.ndarray, dict[str, Any]]:
    ledger = load_yaml(V3_REL)
    config = next(c for c in ledger["configurations"] if c["configuration_id"] == "C07")
    return (
        float(config["mass"]["value_kg"]),
        np.asarray(config["center_of_mass"]["xyz_m"], dtype=float),
        inertia_matrix(config["inertia"]["components_kg_m2"]),
        config,
    )


def invert_fixed_residual(b601, arm, q0: np.ndarray) -> tuple[tuple[float, np.ndarray, np.ndarray], dict[str, Any]]:
    total_m, total_cg, total_I, config = c07_total_properties()
    arm_m, arm_cg, arm_I = arm_properties(b601, arm, q0, PLACEMENTS["ODR01_DYNAMICS_T_SM"])
    total_I_origin = total_I + steiner(total_m, total_cg)
    arm_I_origin = arm_I + steiner(arm_m, arm_cg)
    residual_m = total_m - arm_m
    residual_cg = (total_m * total_cg - arm_m * arm_cg) / residual_m
    residual_I_origin = total_I_origin - arm_I_origin
    residual_I = 0.5 * ((residual_I_origin - steiner(residual_m, residual_cg)) + (residual_I_origin - steiner(residual_m, residual_cg)).T)
    residual = (float(residual_m), residual_cg, residual_I)
    re_m, re_cg, re_I = combine_bodies([residual, (arm_m, arm_cg, arm_I)])
    solar_rows = [x for x in config["composition"] if x["component_id"].startswith("solar_array_r2_")]
    solar_source = load_json(SOLAR_MASS_REL)["configurations"]["C07"]["both_wings"]
    record = {
        "schema": "E21_C07_R2_DEPLOYED_LOCKED_FIXED_RESIDUAL_V1",
        "generated_local": GENERATED_LOCAL,
        "source_configuration": "V3_R2/C07 PREGRASP",
        "source_total": {"mass_kg": total_m, "cg_S_m": total_cg.tolist(), "inertia_about_system_cg_S_kg_m2": total_I.tolist()},
        "subtracted_complete_arm_at_ODR01": {"mass_kg": arm_m, "cg_S_m": arm_cg.tolist(), "inertia_about_arm_cg_S_kg_m2": arm_I.tolist()},
        "fixed_residual": {
            "interpretation": "EQUIVALENT_FIXED_BUS_M3R_BRIDGE_AND_DEPLOYED_LOCKED_R2_WINGS",
            "mass_kg": residual_m, "cg_S_m": residual_cg.tolist(), "inertia_about_residual_cg_S_kg_m2": residual_I.tolist(),
            "inertia_min_eigenvalue_kg_m2": float(np.linalg.eigvalsh(residual_I)[0]),
            "uncertainty_propagated": None,
        },
        "reclosure": {
            "mass_error_kg": abs(re_m - total_m),
            "cg_error_norm_m": float(np.linalg.norm(re_cg - total_cg)),
            "inertia_max_abs_error_kg_m2": float(np.max(np.abs(re_I - total_I))),
        },
        "r2_wing_check": {
            "ledger_solar_component_mass_kg": math.fsum(float(x["mass_kg"]) for x in solar_rows),
            "solar_r2_mass_package_C07_both_wings_kg": float(solar_source["mass_kg"]),
            "deployed_locked_rigid_properties_in_residual": True,
            "legacy_r1_panel_card_or_mass_or_ffr_consumed": False,
        },
        "residual_shared_value_but_lane_model_objects_independent": True,
        "full_flexible_coupling_claimed": False,
    }
    return residual, record


def summarize_lane(lane: str, result: dict[str, Any], model: RigidArmOnlyModel, trajectory: M07Trajectory,
                   total_ref: tuple[float, np.ndarray, np.ndarray], campaign: dict[str, Any]) -> dict[str, Any]:
    dh = result["hI"] - result["hI"][0]
    audit = np.abs(result["W"] - (result["E"] - result["E"][0]))
    scale = max(float(np.max(np.abs(result["W"]))), float(np.max(np.abs(result["E"]))), 1.0e-300)
    initial = model.system_mass_properties(trajectory.q0)
    return {
        "schema": "E21_CURRENT_R2_RIGID_WING_FREE_FLOATING_ARM_ONLY_LANE_V1",
        "generated_local": GENERATED_LOCAL, "lane_id": lane,
        "placement_selected_for_project": False,
        "solver": {"mode": "reduced_momentum", "method": "Radau", "rtol": campaign["solver"]["rtol"],
                   "atol": campaign["solver"]["atol"], "output_samples": len(result["t"]), "nfev": result["nfev"]},
        "initial_state": {
            "position_m": [0.0, 0.0, 0.0], "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
            "total_inertial_momentum": [0.0]*6, "joint_work_J": 0.0,
            "source_lane": None, "state_transferred_from_other_lane": False,
        },
        "model_scope": {
            "configuration": "V3_R2/C07", "trajectory": "M07_ARM_ONLY",
            "r2_wings": "DEPLOYED_LOCKED_RIGID_MASS_PROPERTIES_IN_FIXED_RESIDUAL",
            "legacy_r1_panel_inputs_consumed": False, "target_attached": False,
            "contact": False, "collision": False, "full_R2_flexible_coupling": False,
        },
        "initial_mass_properties_vs_V3_R2_C07": {
            "computed_mass_kg": initial[0], "computed_cg_S_m": initial[1].tolist(),
            "computed_inertia_about_system_cg_S_kg_m2": initial[2].tolist(),
            "mass_error_kg": abs(initial[0] - total_ref[0]),
            "cg_error_norm_m": float(np.linalg.norm(initial[1] - total_ref[1])),
            "inertia_max_abs_error_kg_m2": float(np.max(np.abs(initial[2] - total_ref[2]))),
        },
        "metrics": {
            "peak_base_attitude_deviation_deg": float(np.max(result["dev_deg"])),
            "final_base_attitude_deviation_deg": float(result["dev_deg"][-1]),
            "peak_base_rate_rad_s": float(np.max(np.linalg.norm(result["Vb"][:, 3:6], axis=1))),
            "max_base_origin_shift_m": float(np.max(np.linalg.norm(result["r"], axis=1))),
            "final_base_position_m": result["r"][-1].tolist(),
            "joint_work_final_J": float(result["W"][-1]),
            "momentum_max_norm_dP": float(np.max(np.linalg.norm(dh[:, :3], axis=1))),
            "momentum_max_norm_dL": float(np.max(np.linalg.norm(dh[:, 3:], axis=1))),
            "energy_audit_relative": float(np.max(audit) / scale),
            "quaternion_norm_max_error_after_normalization": float(np.max(np.abs(np.linalg.norm(result["quat"], axis=1) - 1.0))),
            "quaternion_norm_max_error_before_output_normalization": float(np.max(np.abs(result["raw_quat_norm"] - 1.0))),
            "mass_matrix_min_eigenvalue": float(np.min(result["mass_matrix_min_eig"])),
        },
        "standard_uncertainty": None,
        "released": False,
    }


def history_bytes(lane: str, result: dict[str, Any]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow([
        "lane_id", "sample_index", "t_s", "base_x_m", "base_y_m", "base_z_m",
        "quat_w", "quat_x", "quat_y", "quat_z", "base_wx_rad_s", "base_wy_rad_s", "base_wz_rad_s",
        "base_dev_deg", "energy_J", "joint_work_J", "momentum_dP_norm", "momentum_dL_norm",
        *[f"joint{i}_q_rad" for i in range(1, 7)],
    ])
    dh = result["hI"] - result["hI"][0]
    for index, time in enumerate(result["t"]):
        writer.writerow([
            lane, index, f"{time:.12e}",
            *(f"{v:.16e}" for v in result["r"][index]),
            *(f"{v:.16e}" for v in result["quat"][index]),
            *(f"{v:.16e}" for v in result["Vb"][index, 3:6]),
            f"{result['dev_deg'][index]:.16e}", f"{result['E'][index]:.16e}", f"{result['W'][index]:.16e}",
            f"{np.linalg.norm(dh[index, :3]):.16e}", f"{np.linalg.norm(dh[index, 3:]):.16e}",
            *(f"{v:.16e}" for v in result["joints"][index]),
        ])
    return stream.getvalue().encode("utf-8")


def chain_kinetic_energy(dq: np.ndarray, include_inter_hinge_points: bool) -> float:
    leaf_mass, leaf_length, leaf_thickness = 0.18, 0.2, 0.0025
    inter_mass = 0.03
    inertia_leaf_com_x = leaf_mass / 12.0 * (leaf_length**2 + leaf_thickness**2)
    psi = [math.pi/2.0, math.pi/2.0, math.pi/2.0]
    dpsi = [dq[0], dq[0] + dq[1], dq[0] + dq[1] + dq[2]]
    directions = [(math.sin(p), math.cos(p)) for p in psi]
    derivatives = [(math.cos(p), -math.sin(p)) for p in psi]
    velocity_point = np.zeros(2)
    energy = 0.0
    endpoint_velocities = []
    for i in range(3):
        vcom = velocity_point + 0.5 * leaf_length * dpsi[i] * np.asarray(derivatives[i])
        energy += 0.5 * leaf_mass * float(vcom @ vcom) + 0.5 * inertia_leaf_com_x * dpsi[i]**2
        velocity_point = velocity_point + leaf_length * dpsi[i] * np.asarray(derivatives[i])
        endpoint_velocities.append(velocity_point.copy())
        _ = directions[i]
    if include_inter_hinge_points:
        for velocity in endpoint_velocities[:2]:
            energy += 0.5 * inter_mass * float(velocity @ velocity)
    return float(energy)


def rom_mass_matrix(include_inter_hinge_points: bool) -> np.ndarray:
    basis = np.eye(3)
    energies = [chain_kinetic_energy(v, include_inter_hinge_points) for v in basis]
    matrix = np.zeros((3, 3))
    for i in range(3):
        matrix[i, i] = 2.0 * energies[i]
    for i in range(3):
        for j in range(i + 1, 3):
            value = chain_kinetic_energy(basis[i] + basis[j], include_inter_hinge_points) - energies[i] - energies[j]
            matrix[i, j] = matrix[j, i] = value
    return matrix


def generalized_frequencies(mass: np.ndarray, stiffness: np.ndarray) -> list[float]:
    chol = np.linalg.cholesky(mass)
    inv = np.linalg.inv(chol)
    symmetric = inv @ stiffness @ inv.T
    values = np.linalg.eigvalsh(0.5 * (symmetric + symmetric.T))
    return [float(math.sqrt(value) / (2.0 * math.pi)) for value in values]


def build_rom_reproduction() -> dict[str, Any]:
    flex = load_yaml(FLEX_REL)
    published = load_json(MODES_REL)
    mass_leaf = rom_mass_matrix(False)
    mass_conflict = rom_mass_matrix(True)
    root = flex["leaf_L1_engineering_model"]["root_hinge_ktheta_Nm_per_rad"]
    inter = flex["leaf_L1_engineering_model"]["inter_panel_ktheta_Nm_per_rad"]
    cases = {
        "nominal": (root["nominal"], inter["nominal"]),
        "all_low": (root["low"], inter["low"]),
        "all_high": (root["high"], inter["high"]),
        "root_low_inter_high": (root["low"], inter["high"]),
        "root_high_inter_low": (root["high"], inter["low"]),
    }
    rows = []
    for name, (kr, ki) in cases.items():
        stiffness = np.diag([float(kr), float(ki), float(ki)])
        frequency = generalized_frequencies(mass_leaf, stiffness)
        conflict = generalized_frequencies(mass_conflict, stiffness)
        reference = [float(x) for x in published["modes_hz_per_case"][name]]
        rows.append({
            "case": name, "K_Nm_per_rad": stiffness.tolist(),
            "leaf_only_reproduced_hz": frequency, "published_hz": reference,
            "published_max_abs_error_hz": float(np.max(np.abs(np.asarray(frequency) - np.asarray(reference)))),
            "moving_inter_hinge_mass_conflict_hz": conflict,
            "conflict_minus_leaf_only_hz": (np.asarray(conflict) - np.asarray(frequency)).tolist(),
        })
    published_mass = np.asarray(published["mass_matrix_kgm2"], dtype=float)
    return {
        "schema": "E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1",
        "generated_local": GENERATED_LOCAL,
        "scope": "FIXED_BASE_FREE_VIBRATION_ONLY",
        "dof_per_wing": 3,
        "leaf_only": {
            "Mqq_kg_m2": mass_leaf.tolist(), "published_Mqq_kg_m2": published_mass.tolist(),
            "published_mass_matrix_max_abs_error_kg_m2": float(np.max(np.abs(mass_leaf - published_mass))),
            "stiffness_form": "diag(k_root,k_inter,k_inter)", "cases": rows,
        },
        "nonselecting_conflict_diagnostic": {
            "reason": "mass script assigns two 0.03 kg moving inter-hinge point masses absent from leaf-only ROM kinetic energy",
            "inter_hinge_point_mass_each_kg": 0.03, "moving_point_count_per_wing": 2,
            "Mqq_star_kg_m2": mass_conflict.tolist(),
            "Mqq_star_minus_leaf_only_kg_m2": (mass_conflict - mass_leaf).tolist(),
            "selected": False, "propagated_to_free_floating_dynamics": False,
            "dynamic_mass_allocation_frozen": False,
        },
        "damping_matrix": None, "participation_factors": None, "forced_response": None,
        "full_R2_flexible_coupling": "NOT_EVALUATED",
        "e15_cleared": False,
        "standard_uncertainty": None,
    }


def criterion(identifier: str, name: str, passed: bool, evidence: Any) -> dict[str, Any]:
    return {"id": identifier, "name": name, "status": "PASS" if passed else "FAIL", "passed": bool(passed), "evidence": evidence}


def build_all() -> dict[str, bytes]:
    authority = load_yaml(AUTHORITY_REL)
    campaign = load_yaml(CAMPAIGN_REL)
    if authority["gate"] != "HOLD" or authority["next_stage_authorized"] or authority["release_credit"]:
        raise RuntimeError("e21 authority must remain HOLD")
    input_manifest = build_input_manifest(campaign)
    b601 = import_source("e21_b601_model_runtime", B601_MODEL_REL)
    arm_for_audit = b601.B601Arm(str(project_path(URDF_REL)))
    placement_audit = build_placement_audit(b601, arm_for_audit, campaign)
    trajectory, trajectory_check = read_m07(campaign)
    residual, residual_record = invert_fixed_residual(b601, arm_for_audit, trajectory.q0)
    total_ref = c07_total_properties()[:3]

    lane_results: dict[str, dict[str, Any]] = {}
    lane_summaries: dict[str, dict[str, Any]] = {}
    for lane, transform in PLACEMENTS.items():
        # New URDF parse, arm object, model object and zero state for every lane.
        arm = b601.B601Arm(str(project_path(URDF_REL)))
        model = RigidArmOnlyModel(arm, transform.copy(), (residual[0], residual[1].copy(), residual[2].copy()))
        result = model.integrate(
            trajectory, rtol=float(campaign["solver"]["rtol"]), atol=float(campaign["solver"]["atol"]),
            n_out=int(campaign["solver"]["output_samples"]),
        )
        lane_results[lane] = result
        lane_summaries[lane] = summarize_lane(lane, result, model, trajectory, total_ref, campaign)

    odr = lane_summaries["ODR01_DYNAMICS_T_SM"]
    physical = lane_summaries["WP11_PHYSICAL_GEOMETRY_CONTEXT"]
    keys = ["peak_base_attitude_deviation_deg", "final_base_attitude_deviation_deg", "peak_base_rate_rad_s", "max_base_origin_shift_m", "joint_work_final_J"]
    cross_lane = {
        "schema": "E21_TWO_PLACEMENT_RIGID_DYNAMICS_SENSITIVITY_V1", "generated_local": GENERATED_LOCAL,
        "branches_selected": False, "branches_averaged": False, "branch_delta_is_uncertainty": False,
        "same_fixed_residual": True, "independent_model_objects": True, "independent_zero_initial_states": True,
        "state_transfer_between_lanes": False,
        "physical_context_minus_odr01": {key: float(physical["metrics"][key] - odr["metrics"][key]) for key in keys},
        "standard_uncertainty": None,
        "single_placement_consumption_semantics_resolved": False,
    }
    rom = build_rom_reproduction()
    limits = campaign["thresholds"]
    all_lanes = list(lane_summaries.values())
    odr_close = odr["initial_mass_properties_vs_V3_R2_C07"]
    rom_rows = rom["leaf_only"]["cases"]
    criteria = [
        criterion("E21-G01", "all source hashes exact", input_manifest["all_exact_hash_match"], input_manifest["record_count"]),
        criterion("E21-G02", "authority stays HOLD and non-release", authority["gate"] == "HOLD" and not authority["next_stage_authorized"] and not authority["release_credit"], authority["mandatory_holds"]),
        criterion("E21-G03", "both ledgers contain nine audited configurations", placement_audit["ledger_count"] == 2 and placement_audit["configuration_count_per_ledger"] == 9 and placement_audit["placement_evaluation_count"] == 36, placement_audit["placement_evaluation_count"]),
        criterion("E21-G04", "mixed arm placement context is detected without invalidating ODR-01", placement_audit["mixed_placement_context_detected"] and not placement_audit["ODR01_invalidated"] and not placement_audit["any_configuration_declared_wrong"], placement_audit["verdict"]),
        criterion("E21-G05", "placement branches are neither selected nor averaged nor uncertainty", not placement_audit["branch_selected"] and not placement_audit["branches_averaged"] and not placement_audit["branch_delta_is_uncertainty"], cross_lane),
        criterion("E21-G06", "V2 arm records carry verbatim into V3_R2", placement_audit["all_arm_rows_carried_verbatim"], placement_audit["v2_to_v3_r2_non_solar_arm_carry_forward"]),
        criterion("E21-G07", "all 451 M07 q qd qdd rows reproduce", trajectory_check["all_numeric_rows_reproduced"], trajectory_check),
        criterion("E21-G08", "fixed residual is positive and SPD", residual_record["fixed_residual"]["mass_kg"] > 0.0 and residual_record["fixed_residual"]["inertia_min_eigenvalue_kg_m2"] > 0.0, residual_record["fixed_residual"]),
        criterion("E21-G09", "current R2 deployed locked wing mass closes and no legacy panel input is consumed", abs(residual_record["r2_wing_check"]["ledger_solar_component_mass_kg"] - residual_record["r2_wing_check"]["solar_r2_mass_package_C07_both_wings_kg"]) <= 1.0e-12 and not residual_record["r2_wing_check"]["legacy_r1_panel_card_or_mass_or_ffr_consumed"], residual_record["r2_wing_check"]),
        criterion("E21-G10", "ODR01 lane initial mass properties close V3_R2 C07", odr_close["mass_error_kg"] <= limits["odr01_c07_mass_closure_kg"] and odr_close["cg_error_norm_m"] <= limits["odr01_c07_cg_closure_m"] and odr_close["inertia_max_abs_error_kg_m2"] <= limits["odr01_c07_inertia_closure_kg_m2"], odr_close),
        criterion("E21-G11", "physical-context lane preserves residual and reports V3_R2 delta", cross_lane["same_fixed_residual"] and physical["initial_mass_properties_vs_V3_R2_C07"]["cg_error_norm_m"] > 0.0, physical["initial_mass_properties_vs_V3_R2_C07"]),
        criterion("E21-G12", "lanes use independent models and zero states", cross_lane["independent_model_objects"] and cross_lane["independent_zero_initial_states"] and not cross_lane["state_transfer_between_lanes"], {k: cross_lane[k] for k in ("independent_model_objects", "independent_zero_initial_states", "state_transfer_between_lanes")}),
        criterion("E21-G13", "scope excludes target contact collision and full flexibility", all(not row["model_scope"]["target_attached"] and not row["model_scope"]["contact"] and not row["model_scope"]["collision"] and not row["model_scope"]["full_R2_flexible_coupling"] for row in all_lanes), [row["model_scope"] for row in all_lanes]),
        criterion("E21-G14", "both main lanes use reduced-momentum Radau at frozen tolerances", all(row["solver"]["mode"] == "reduced_momentum" and row["solver"]["method"] == "Radau" and row["solver"]["rtol"] <= 1.0e-9 and row["solver"]["atol"] <= 1.0e-11 for row in all_lanes), [row["solver"] for row in all_lanes]),
        criterion("E21-G15", "inertial momentum closes in both lanes", all(max(row["metrics"]["momentum_max_norm_dP"], row["metrics"]["momentum_max_norm_dL"]) <= limits["momentum_norm"] for row in all_lanes), [row["metrics"] for row in all_lanes]),
        criterion("E21-G16", "energy ledger closes in both lanes", all(row["metrics"]["energy_audit_relative"] <= limits["energy_audit_relative"] for row in all_lanes), [row["metrics"]["energy_audit_relative"] for row in all_lanes]),
        criterion("E21-G17", "output quaternions remain normalized", all(row["metrics"]["quaternion_norm_max_error_after_normalization"] <= limits["quaternion_norm_error"] for row in all_lanes), [row["metrics"]["quaternion_norm_max_error_after_normalization"] for row in all_lanes]),
        criterion("E21-G18", "mass matrix stays SPD in both lanes", all(row["metrics"]["mass_matrix_min_eigenvalue"] > limits["mass_matrix_min_eigenvalue"] for row in all_lanes), [row["metrics"]["mass_matrix_min_eigenvalue"] for row in all_lanes]),
        criterion("E21-G19", "leaf-only R2 ROM mass matrix reproduces", rom["leaf_only"]["published_mass_matrix_max_abs_error_kg_m2"] <= limits["rom_mass_matrix_kg_m2"], rom["leaf_only"]["published_mass_matrix_max_abs_error_kg_m2"]),
        criterion("E21-G20", "all five published R2 stiffness-case frequencies reproduce", len(rom_rows) == 5 and max(row["published_max_abs_error_hz"] for row in rom_rows) <= limits["rom_published_frequency_hz"], rom_rows),
        criterion("E21-G21", "moving inter-hinge mass conflict is nonzero and nonpropagated", np.max(np.abs(np.asarray(rom["nonselecting_conflict_diagnostic"]["Mqq_star_minus_leaf_only_kg_m2"]))) > 0.0 and not rom["nonselecting_conflict_diagnostic"]["selected"] and not rom["nonselecting_conflict_diagnostic"]["propagated_to_free_floating_dynamics"] and max(abs(v) for row in rom_rows for v in row["conflict_minus_leaf_only_hz"]) > limits["rom_conflict_frequency_delta_hz"], rom["nonselecting_conflict_diagnostic"]),
        criterion("E21-G22", "ROM does not construct damping participation or forced response", rom["damping_matrix"] is None and rom["participation_factors"] is None and rom["forced_response"] is None, {"damping_matrix": None, "participation_factors": None, "forced_response": None}),
        criterion("E21-G23", "all required HOLDs remain explicit", authority["mandatory_holds"]["r2_full_flexible_coupling"] == "NOT_EVALUATED" and authority["mandatory_holds"]["e15_ancf_certification"] == "REPEAT_ANCF_CERTIFICATION" and authority["mandatory_holds"]["r2_harness_R2_HRN_04"] == "FAIL_REDESIGN_REQUIRED" and authority["mandatory_holds"]["owner_review"] == "PENDING_OWNER_REVIEW" and authority["mandatory_holds"]["contact"].startswith("HOLD") and authority["mandatory_holds"]["mission_capture"].startswith("HOLD") and authority["mandatory_holds"]["production"] == "HOLD" and authority["mandatory_holds"]["flight"] == "HOLD", authority["mandatory_holds"]),
    ]
    all_pass = all(row["passed"] for row in criteria)
    gate = {
        "schema": "E21_DIAGNOSTIC_GATE_V1", "generated_local": GENERATED_LOCAL,
        "verdict": VERDICT if all_pass else "E21_REPEAT_DIAGNOSTIC_SUBCRITERIA__ALL_AUTHORITY_HOLDS_REMAIN",
        "overall": "HOLD", "diagnostic_subcriteria_all_pass": all_pass,
        "criteria": criteria, "criterion_counts": {"total": len(criteria), "pass": sum(r["passed"] for r in criteria), "fail": sum(not r["passed"] for r in criteria)},
        "scientific_scope": "CURRENT_R2_RIGID_WING_ARM_ONLY_PLACEMENT_SENSITIVITY_PLUS_FIXED_BASE_ROM_REPRODUCTION",
        "review_status": "PENDING_OWNER_REVIEW", "next_stage_authorized": False,
        "release_credit": False, "test_pass_grants_authority": False,
        "unknown_uncertainties_zero_filled": False,
        "mandatory_holds": authority["mandatory_holds"],
        "nonclaims": authority["nonclaims"],
    }

    outputs: dict[str, bytes] = {
        result_rel("E21_INPUT_MANIFEST_V1.json"): json_bytes(input_manifest),
        result_rel("E21_NINE_CONFIGURATION_ARM_PLACEMENT_AUDIT_V1.json"): json_bytes(placement_audit),
        result_rel("E21_M07_TRAJECTORY_RECONSTRUCTION_CHECK_V1.json"): json_bytes(trajectory_check),
        result_rel("E21_C07_R2_DEPLOYED_LOCKED_FIXED_RESIDUAL_V1.json"): json_bytes(residual_record),
        result_rel("E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_SUMMARY_V1.json"): json_bytes(odr),
        result_rel("E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_HISTORY_V1.csv"): history_bytes("ODR01_DYNAMICS_T_SM", lane_results["ODR01_DYNAMICS_T_SM"]),
        result_rel("E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_SUMMARY_V1.json"): json_bytes(physical),
        result_rel("E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_HISTORY_V1.csv"): history_bytes("WP11_PHYSICAL_GEOMETRY_CONTEXT", lane_results["WP11_PHYSICAL_GEOMETRY_CONTEXT"]),
        result_rel("E21_TWO_PLACEMENT_RIGID_DYNAMICS_SENSITIVITY_V1.json"): json_bytes(cross_lane),
        result_rel("E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json"): json_bytes(rom),
        result_rel("E21_DIAGNOSTIC_GATE_V1.json"): json_bytes(gate),
    }
    return outputs


def write_or_check(outputs: dict[str, bytes], check_only: bool) -> None:
    failures = []
    for relative, data in outputs.items():
        path = project_path(relative)
        if check_only:
            if not path.is_file() or path.read_bytes() != data:
                failures.append(relative)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if failures:
        raise SystemExit("E21_CHECK_ONLY_MISMATCH: " + ", ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    outputs = build_all()
    write_or_check(outputs, args.check_only)
    gate = json.loads(outputs[result_rel("E21_DIAGNOSTIC_GATE_V1.json")])
    print(f"E21_BUILD_OK criteria={gate['criterion_counts']['pass']}/{gate['criterion_counts']['total']} overall={gate['overall']}")


if __name__ == "__main__":
    main()
