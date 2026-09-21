"""Independent raw-file recomputation for E23 evidence.

This script intentionally does not import e23_model or build_e23.  It checks the
source pins, spatial-mass assembly, full target tensor placement, Round3 coupled
SPD block, HF/ROM error arithmetic, Gate disposition and all Gate evidence hashes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

# These assignments deliberately precede every NumPy/SciPy import.  A second
# in-call threadpoolctl guard makes the result deterministic when this file is
# imported into a process that has already loaded a threaded BLAS runtime.
for _thread_env in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_env] = "1"

import numpy as np
import yaml
from scipy.linalg import block_diag, eigh
from threadpoolctl import threadpool_info, threadpool_limits

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

HERE = Path(__file__).resolve()
E22_DIR = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]
RESULTS = E22_DIR / "results"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def skew(v: np.ndarray) -> np.ndarray:
    x, y, z = np.asarray(v, float)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def inertia(v: dict[str, float]) -> np.ndarray:
    return np.array([[v["Ixx"], v["Ixy"], v["Ixz"]],
                     [v["Ixy"], v["Iyy"], v["Iyz"]],
                     [v["Ixz"], v["Iyz"], v["Izz"]]], float)


def spatial(m: float, c: np.ndarray, Icg: np.ndarray) -> np.ndarray:
    c = np.asarray(c, float)
    return np.block([[m*np.eye(3), -m*skew(c)],
                     [m*skew(c), Icg+m*((c@c)*np.eye(3)-np.outer(c, c))]])


def component_spatial(c: dict[str, Any]) -> np.ndarray:
    return spatial(float(c["mass_kg"]), np.asarray(c["com_S_m"], float),
                   np.asarray(c["inertia_about_own_com_S_kg_m2"], float))


def source_entry(doc: dict[str, Any], cid: str) -> dict[str, Any]:
    return next(x for x in doc["configurations"] if x["configuration_id"] == cid)


def bridge_entry(doc: dict[str, Any], cid: str) -> dict[str, Any]:
    return next(x for x in doc["configurations"] if x["configuration_id"] == cid)["bridged_candidate"]


def full_operators(semantics: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    """Rebuild the 183-DOF response operators from published DOF semantics."""
    nd = len(semantics)

    def row(index: int) -> np.ndarray:
        result = np.zeros(nd)
        result[index] = 1.0
        return result

    w_items = sorted((x for x in semantics if x["kind"] == "TRANSVERSE_W"),
                     key=lambda x: x["node"])
    theta_items = [x for x in semantics if x["kind"] == "BENDING_SLOPE_THETA"]
    torsion_items = sorted((x for x in semantics if x["kind"] == "TORSION_PHI"),
                           key=lambda x: x["node"])
    Rw = np.vstack([np.zeros(nd)]+[row(x["reduced_index_0based"]) for x in w_items])
    Rtheta = np.vstack([row(x["reduced_index_0based"]) for x in theta_items])
    Rtorsion = np.vstack([np.zeros(nd)]+[
        row(x["reduced_index_0based"]) for x in torsion_items
    ])
    by_node: dict[int, list[dict[str, Any]]] = {}
    for item in theta_items:
        by_node.setdefault(int(item["node"]), []).append(item)
    Rhinge = [row(by_node[0][0]["reduced_index_0based"])]
    for inode in (20, 40):
        left = next(x for x in by_node[inode] if x["side"] == "L")
        right = next(x for x in by_node[inode] if x["side"] == "R")
        Rhinge.append(row(right["reduced_index_0based"])-row(left["reduced_index_0based"]))
    Rtip = row(w_items[-1]["reduced_index_0based"])[None, :]
    return {
        "tip_peak_m": Rtip,
        "node_peak_m": Rw,
        "slope_peak_rad": Rtheta,
        "hinge_peak_rad": np.vstack(Rhinge),
        "torsion_peak_rad": Rtorsion,
    }


def undamped_half_sine_response(
    M: np.ndarray, K: np.ndarray, impulse: np.ndarray,
    operators: dict[str, np.ndarray], Tc: float = 0.020, post_s: float = 5.0,
) -> dict[str, float]:
    """Independent closed form for M qdd + K q = impulse*h(t), zeta=0."""
    with threadpool_limits(limits=1, user_api="blas"):
        eigenvalues, modes = eigh(K, M, driver="gvd", check_finite=True)
    if np.min(eigenvalues) <= 0.0:
        raise RuntimeError("independent dynamic recomputation found nonpositive eigenvalue")
    omega = np.sqrt(eigenvalues)
    forcing = modes.T@np.asarray(impulse, float)
    Omega = math.pi/Tc
    amplitude = math.pi/(2.0*Tc)
    coefficient = forcing*amplitude/(omega*omega-Omega*Omega)
    tc = np.linspace(0.0, Tc, 401)
    tp = np.linspace(0.0, post_s, 5001)
    yc = coefficient[:, None]*(
        np.sin(Omega*tc)[None, :]-(Omega/omega)[:, None]*np.sin(omega[:, None]*tc[None, :])
    )
    ydc = coefficient[:, None]*Omega*(
        np.cos(Omega*tc)[None, :]-np.cos(omega[:, None]*tc[None, :])
    )
    yT = yc[:, -1]
    ydT = ydc[:, -1]
    yp = yT[:, None]*np.cos(omega[:, None]*tp[None, :]) + \
         (ydT/omega)[:, None]*np.sin(omega[:, None]*tp[None, :])
    ydp = -yT[:, None]*omega[:, None]*np.sin(omega[:, None]*tp[None, :]) + \
          ydT[:, None]*np.cos(omega[:, None]*tp[None, :])
    y = np.hstack([yc, yp[:, 1:]])
    yd = np.hstack([ydc, ydp[:, 1:]])
    q = modes@y
    energy = 0.5*np.sum(yd*yd+(omega[:, None]*y)**2, axis=0)
    result = {name: float(np.max(np.abs(R@q))) for name, R in operators.items()}
    result["modal_energy_peak_J"] = float(np.max(energy))
    result["modal_energy_final_J"] = float(energy[-1])
    return result


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+"\n",
                    encoding="utf-8")


def write_package_manifest() -> dict[str, Any]:
    """Create the acyclic package-level reverse pin after independent evidence."""
    gate_path = RESULTS / "E23_R2_FULL_FLEX_COUPLED_GATE_V1.json"
    independent_path = RESULTS / "E23_INDEPENDENT_RECOMPUTE_V1.json"
    required = [
        gate_path,
        independent_path,
        RESULTS / "E23_SOURCE_AND_AUTHORITY_AUDIT_V1.json",
        RESULTS / "E23_R2_COUPLED_CASES_V1.json",
        RESULTS / "E23_R2_SENSITIVITY_AND_VALIDATION_V1.json",
        RESULTS / "R2_HF_TO_ROM_DYNAMIC_VALIDATION_V1.json",
        RESULTS / "E23_CASE_MATRIX_V1.csv",
    ]
    replay_path = RESULTS / "E23_DETERMINISM_REPLAY_V1.json"
    if replay_path.exists():
        required.append(replay_path)
    if not all(x.exists() for x in required):
        missing = [str(x) for x in required if not x.exists()]
        raise RuntimeError(f"PACKAGE_MANIFEST_MISSING_ASSET:{missing}")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    independent = json.loads(independent_path.read_text(encoding="utf-8"))
    manifest = {
        "schema": "E23_PACKAGE_MANIFEST_V1",
        "generation_order": "GATE_THEN_INDEPENDENT_THEN_PACKAGE_MANIFEST",
        "cycle_avoidance_contract": {
            "gate_self_reference": "EXCLUDED",
            "gate_excludes_post_generated_independent_report": True,
            "gate_excludes_post_generated_package_manifest": True,
            "package_manifest_reverse_pins_gate_and_independent": True,
            "package_manifest_self_reference": "EXCLUDED",
        },
        "package_assets": {
            str(x.relative_to(PROJECT_ROOT)).replace("\\", "/"): sha256(x)
            for x in required
        },
        "checkpoint_A_required_pins": {
            "gate": {"path": str(gate_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                     "sha256": sha256(gate_path)},
            "independent": {"path": str(independent_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                            "sha256": sha256(independent_path)},
            "package_manifest": {
                "path": str((RESULTS / "E23_PACKAGE_MANIFEST_V1.json").relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "sha256_policy": "COMPUTE_EXTERNALLY__SELF_REFERENCE_EXCLUDED",
            },
        },
        "red_team_falsifier_direct_gate_pins": {
            rel: gate["evidence_hashes"][rel]
            for rel in gate["evidence_hashes"] if "ROM5_DIMENSION_FALSIFIER_V1.json" in rel or
            "recompute_rom5_dimension_falsifier.py" in rel
        },
        "gate_evidence_hashes_verified_by_independent": next(
            x for x in independent["checks"] if x["id"] == "GATE_EVIDENCE_HASHES"
        )["pass"],
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(RESULTS / "E23_PACKAGE_MANIFEST_V1.json", manifest)
    return manifest


def main() -> int:
    cfg = yaml.safe_load((E22_DIR / "config" / "e23_config.yaml").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    blas_pools = [x for x in threadpool_info() if x.get("user_api") == "blas"]
    deterministic_pools = bool(blas_pools) and all(int(x.get("num_threads", 0)) == 1 for x in blas_pools)
    determinism_contract = {
        "contract": "BLAS threads=1; scipy.linalg.eigh generalized symmetric-definite driver=gvd",
        "threadpools": [{k: x.get(k) for k in ("internal_api", "prefix", "version", "num_threads")}
                        for x in blas_pools],
        "comparison_semantics": (
            "compare reconstructed physical time-response peaks; individual eigenvectors "
            "inside near-degenerate subspaces are not evidence observables"
        ),
        "pass": deterministic_pools,
    }

    pin_actual = {}
    for name, pin in cfg["source_pins"].items():
        actual = sha256(PROJECT_ROOT / pin["path"])
        pin_actual[name] = actual
        checks.append({"id": f"PIN_{name}", "pass": actual == str(pin["sha256"]).upper(),
                       "actual": actual, "expected": str(pin["sha256"]).upper()})

    source = yaml.safe_load((PROJECT_ROOT / cfg["source_pins"]["r2_mass_ledger"]["path"]).read_text(encoding="utf-8"))
    bridged = yaml.safe_load((PROJECT_ROOT / cfg["source_pins"]["bridged_r2_mass_ledger"]["path"]).read_text(encoding="utf-8"))
    records: dict[str, dict[str, Any]] = {}
    bridge_residual = 0.0
    for cid in ("C07", "C08", "C09"):
        s = source_entry(source, cid)
        b = bridge_entry(bridged, cid)
        Is = inertia(s["inertia_about_system_cg_S_kg_m2"])
        Ib = np.asarray(b["inertia_about_system_cg_S_kg_m2"], float)
        bridge_residual = max(
            bridge_residual,
            abs(float(s["mass"]["value_kg"])-float(b["mass_kg"])),
            float(np.max(np.abs(np.asarray(s["cg_S_m"], float)-np.asarray(b["cg_S_m"], float)))),
            float(np.max(np.abs(Is-Ib))),
        )
        records[cid] = {
            "source": s,
            "mass": float(b["mass_kg"]),
            "cg": np.asarray(b["cg_S_m"], float),
            "Icg": Ib,
            "Mbb": spatial(float(b["mass_kg"]), np.asarray(b["cg_S_m"], float), Ib),
        }
    checks.append({"id": "BRIDGE_ROWS_RECOMPUTED", "pass": bridge_residual <= 1.0e-12,
                   "max_abs_residual": bridge_residual})

    c07 = records["C07"]
    solar = [x for x in c07["source"]["composition"] if x["component_id"] in
             ("solar_array_r2_left", "solar_array_r2_right")]
    solar_mass = sum(float(x["mass_kg"]) for x in solar)
    c07_reassembled = sum((component_spatial(x) for x in c07["source"]["composition"]),
                          np.zeros((6, 6)))
    c07_residual = float(np.max(np.abs(c07_reassembled-c07["Mbb"])))
    checks.append({"id": "C07_COMPONENT_RECLOSE", "pass": c07_residual <= 1.0e-12 and abs(solar_mass-1.56) <= 1.0e-14,
                   "Mbb_max_abs": c07_residual, "solar_mass_kg": solar_mass})
    checks.append({"id": "DOUBLE_COUNT_NEGATIVE_CONTROL", "pass": abs((c07["mass"]+solar_mass)-c07["mass"]) > 1.0,
                   "classification": "DOUBLE_COUNT_SOLAR_R2", "wrong_mass_kg": c07["mass"]+solar_mass})

    Rflip = np.diag(np.asarray(cfg["physics"]["target_to_S_rotation_diag"], float))
    target_checks = {}
    for sid, sc in cfg["scenarios"].items():
        post = records[sc["post_configuration"]]
        component = next(x for x in post["source"]["composition"] if x["component_id"] == sc["target_component"])
        cad = json.loads((PROJECT_ROOT / cfg["source_pins"][
            "target_satellite_full_tensor" if sc["target_key"] == "target_satellite_v0" else
            "target_debris_full_tensor"]["path"]).read_text(encoding="utf-8"))
        target_I_S = Rflip @ inertia(cad["inertia_kg_m2_about_com"]) @ Rflip.T
        ledger_I_S = np.asarray(component["inertia_about_own_com_S_kg_m2"], float)
        post_residual = post["Mbb"]-c07["Mbb"]-component_spatial(component)
        item = {
            "mass_abs_kg": max(abs(float(sc["mass_kg"])-float(component["mass_kg"])),
                               abs(float(cad["mass_kg"])-float(component["mass_kg"]))),
            "Rflip_tensor_max_abs_kgm2": float(np.max(np.abs(target_I_S-ledger_I_S))),
            "post_spatial_max_abs_kgm2": float(np.max(np.abs(post_residual))),
            "CAD_frame_raw_Ixz_kgm2": float(cad["inertia_kg_m2_about_com"]["Ixz"]),
            "S_frame_Rflip_Ixz_kgm2": float(ledger_I_S[0, 2]),
        }
        item["pass"] = (item["mass_abs_kg"] <= 1.0e-12 and
                        item["Rflip_tensor_max_abs_kgm2"] <= 1.0e-12 and
                        item["post_spatial_max_abs_kgm2"] <= 1.0e-12)
        target_checks[sid] = item
    checks.append({"id": "TARGET_FULL_TENSOR_AND_POST_ASSEMBLY", "pass": all(x["pass"] for x in target_checks.values()),
                   "details": target_checks})

    mass_mutation = copy.deepcopy(target_checks)
    mass_mutation["TARGET_22KG_0P5DPS"]["mass_abs_kg"] = 1.0e-10
    tensor_mutation = copy.deepcopy(target_checks)
    tensor_mutation["TARGET_150KG_3DPS"]["Rflip_tensor_max_abs_kgm2"] = 1.0e-10
    mutation_rejected = (
        not all(x["mass_abs_kg"] <= 1.0e-12 and x["Rflip_tensor_max_abs_kgm2"] <= 1.0e-12
                and x["post_spatial_max_abs_kgm2"] <= 1.0e-12 for x in mass_mutation.values()) and
        not all(x["mass_abs_kg"] <= 1.0e-12 and x["Rflip_tensor_max_abs_kgm2"] <= 1.0e-12
                and x["post_spatial_max_abs_kgm2"] <= 1.0e-12 for x in tensor_mutation.values())
    )
    checks.append({"id": "TARGET_1E10_MUTATIONS_REJECTED", "pass": mutation_rejected})

    z = np.load(PROJECT_ROOT / cfg["source_pins"]["round4_rom_npz"]["path"])
    Mbq = np.block([[z["Gamma_t_L"].T, z["Gamma_t_R"].T],
                    [z["Gamma_r_L"].T, z["Gamma_r_R"].T]])
    Mqq = block_diag(z["Mrom"], z["Mrom"])
    Mc = np.block([[c07["Mbb"], Mbq], [Mbq.T, Mqq]])
    schur = Mqq-Mbq.T@np.linalg.solve(c07["Mbb"], Mbq)
    mass_metrics = {
        "min_eigenvalue": float(np.linalg.eigvalsh(Mc)[0]),
        "condition_number": float(np.linalg.cond(Mc)),
        "schur_min_eigenvalue": float(np.linalg.eigvalsh(schur)[0]),
    }
    checks.append({"id": "COUPLED_16X16_SPD", "pass": mass_metrics["min_eigenvalue"] > 0.0 and mass_metrics["schur_min_eigenvalue"] > 0.0,
                   "metrics": mass_metrics})

    hf_path = RESULTS / "R2_HF_TO_ROM_DYNAMIC_VALIDATION_V1.json"
    gate_path = RESULTS / "E23_R2_FULL_FLEX_COUPLED_GATE_V1.json"
    hf = json.loads(hf_path.read_text(encoding="utf-8"))
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    recomputed_errors = []
    error_arithmetic_residual = 0.0
    for wing in hf["wings"].values():
        full = wing["full_183dof_metrics"]
        seven = wing["truncation"]["7"]
        metrics = seven["metrics"]
        for key, value in metrics.items():
            if key.endswith("_time_s"):
                continue
            absolute = abs(float(value)-float(full[key]))
            relative = absolute/max(abs(float(full[key])), 1.0e-14)
            error_arithmetic_residual = max(
                error_arithmetic_residual,
                abs(absolute-float(seven["absolute_error_vs_183dof"][key])),
                abs(relative-float(seven["relative_error_vs_183dof"][key])),
            )
            recomputed_errors.append(relative)
    recomputed_hf_max = max(recomputed_errors)
    # L4 central scientific negative-result reproduction directly from NPZ.  It
    # does not consume any writer-produced response values as numerical inputs.
    rom_contract = json.loads((PROJECT_ROOT / cfg["source_pins"]["round4_rom_contract"]["path"]).read_text(encoding="utf-8"))
    operators_full = full_operators(rom_contract["reduced_hf_dof_semantics"])
    stored_order = np.asarray([0, 3, 4, 1, 5, 6, 2], int)
    Phi = z["Phi_rom"][:, stored_order]
    operators_rom = {name: R@Phi for name, R in operators_full.items()}
    Mrom = z["Mrom"][np.ix_(stored_order, stored_order)]
    Krom = z["Krom_NOMINAL"][np.ix_(stored_order, stored_order)]
    base_delta = np.asarray(hf["base_delta_twist_6"], float)
    dynamic_by_wing: dict[str, Any] = {}
    independent_max = 0.0
    writer_match_relative = 0.0
    for wing in ("L", "R"):
        forcing = -(z[f"Bt_{wing}"]@base_delta[:3]+z[f"Br_{wing}"]@base_delta[3:])
        full_ind = undamped_half_sine_response(z["M"], z["K_nominal"], forcing,
                                                operators_full)
        rom_ind = undamped_half_sine_response(Mrom, Krom, Phi.T@forcing,
                                               operators_rom)
        relative = {name: abs(rom_ind[name]-full_ind[name])/max(abs(full_ind[name]), 1.0e-14)
                    for name in full_ind}
        independent_max = max(independent_max, max(relative.values()))
        writer_full = hf["wings"][wing]["full_183dof_metrics"]
        writer_rom = hf["wings"][wing]["truncation"]["7"]["metrics"]
        for name in full_ind:
            writer_match_relative = max(
                writer_match_relative,
                abs(full_ind[name]-float(writer_full[name]))/max(abs(full_ind[name]), 1.0e-14),
                abs(rom_ind[name]-float(writer_rom[name]))/max(abs(rom_ind[name]), 1.0e-14),
            )
        dynamic_by_wing[wing] = {
            "full_183dof_metrics_independent": full_ind,
            "seven_mode_metrics_independent": rom_ind,
            "relative_error_independent": relative,
            "torsion_peak_full_rad": full_ind["torsion_peak_rad"],
            "torsion_peak_seven_mode_rad": rom_ind["torsion_peak_rad"],
            "torsion_peak_relative_error": relative["torsion_peak_rad"],
        }
    checks.append({
        "id": "HF_ROM_NPZ_DYNAMIC_RECOMPUTE",
        "pass": (deterministic_pools and independent_max <= 0.01 and
                 error_arithmetic_residual <= 1.0e-14 and
                 abs(recomputed_hf_max-float(hf["seven_mode_max_relative_error_vs_183dof"])) <= 1.0e-14 and
                 abs(independent_max-float(hf["seven_mode_max_relative_error_vs_183dof"])) <= 1.0e-10 and
                 writer_match_relative <= 1.0e-9 and
                 hf["linear_subset_verdict"] == "E15_R2_LINEAR_SUBSET_PASS" and
                 gate["technical_verdict"] == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS" and
                 gate["next_stage_authorized"] is False and gate["release_credit"] is False),
        "determinism_contract": determinism_contract,
        "arithmetic_max_abs_residual": error_arithmetic_residual,
        "seven_mode_max_relative_from_writer_arithmetic": recomputed_hf_max,
        "seven_mode_max_relative_independent": independent_max,
        "writer_response_match_relative_max": writer_match_relative,
        "wings": dynamic_by_wing,
    })
    evidence_hash_mismatch = []
    for rel, expected in gate["evidence_hashes"].items():
        actual = sha256(PROJECT_ROOT / rel)
        if actual != expected:
            evidence_hash_mismatch.append({"path": rel, "actual": actual, "expected": expected})
    checks.append({"id": "GATE_EVIDENCE_HASHES", "pass": not evidence_hash_mismatch,
                   "mismatches": evidence_hash_mismatch})

    passed = sum(int(x["pass"]) for x in checks)
    output = {
        "schema": "E23_INDEPENDENT_RECOMPUTE_V1",
        "independence": "raw YAML/JSON/NPZ recomputation; no import from e23_model/build_e23",
        "determinism_contract": determinism_contract,
        "checks": checks,
        "summary": {"passed": passed, "total": len(checks), "failed": [x["id"] for x in checks if not x["pass"]]},
        "key_metrics": {
            "C07_solar_mass_kg": solar_mass,
            "coupled_16x16": mass_metrics,
            "hf_to_rom_five_mode_max_relative_recomputed": recomputed_hf_max,
            "hf_to_rom_five_mode_max_relative_from_NPZ_dynamics": independent_max,
            "gate_sha256": sha256(gate_path),
        },
        "pass": passed == len(checks),
    }
    write_json(RESULTS / "E23_INDEPENDENT_RECOMPUTE_V1.json", output)
    write_package_manifest()
    print(json.dumps(output["summary"], indent=2))
    return 0 if output["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
