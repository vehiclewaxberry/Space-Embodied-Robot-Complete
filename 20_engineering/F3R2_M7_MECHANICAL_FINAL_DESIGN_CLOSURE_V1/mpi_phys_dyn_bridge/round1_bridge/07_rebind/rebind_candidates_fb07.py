"""MPI-FB-07: digital-thread rebinding candidates (V6 / R3 CANDIDATE files).

Emits TWO NEW candidate files inside 07_rebind/:
  - MECH_DYNAMICS_INTERFACE_V6_CANDIDATE.yaml
  - EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE.yaml
Both are amendment-style candidates: the base documents (V5_R2 / R2) stay
byte-untouched; every section not explicitly replaced is inherited by
reference; all existing HOLDs are carried verbatim (machine-extracted from the
base files, never hand-transcribed). Pure python; read-only on upstream.
"""
import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.dont_write_bytecode = True

ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
BASE = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge"
OUT_DIR = BASE / "07_rebind"

BRIDGE_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"
LEDGER_CAND_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml"
FB03_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/03_validation/MPI03_BRIDGE_NUMERICAL_VALIDATION.json"
FB04_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/04_mass/MPI04_MASS_INERTIA_BRIDGE_VALIDATION.json"
FB05_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/05_e21_bridged/E21_BRIDGED_ARM_PLACEMENT_GATE_V2.json"
V5_R2_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V5_R2.yaml"
R2_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp13_embodied_contract/EMBODIED_MECHANICAL_CONTRACT_R2.yaml"
V5_GATE_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/15_loop_continuation_v5/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json"
E21_AUTHORITY_REL = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml"
V3_R2_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"


def sha256_file(rel) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest().upper()


def main():
    sha = {rel: sha256_file(rel) for rel in
           [BRIDGE_REL, LEDGER_CAND_REL, FB03_REL, FB04_REL, FB05_REL, V5_R2_REL, R2_REL, V5_GATE_REL,
            E21_AUTHORITY_REL, V3_R2_REL]}

    v5_gate = json.loads((ROOT / V5_GATE_REL).read_text(encoding="utf-8"))
    r2_doc = yaml.safe_load((ROOT / R2_REL).read_text(encoding="utf-8"))
    e21_contract = yaml.safe_load((ROOT / E21_AUTHORITY_REL).read_text(encoding="utf-8"))

    fail_closed_invariants = list(v5_gate["fail_closed_invariants"])            # verbatim machine extract
    r2_retained_holds = list(r2_doc["retained_holds"])                          # verbatim machine extract
    r2_prohibitions = list(r2_doc["prohibitions_honored"])                      # verbatim machine extract
    e21_mandatory_holds = dict(e21_contract["mandatory_holds"])                 # verbatim machine extract

    bridge_block = {
        "bridge_id": "T_PHYSICAL_TO_DYNAMIC",
        "path": BRIDGE_REL,
        "sha256": sha[BRIDGE_REL],
        "classification": "FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION_AND_MPI_FB08_GATE",
        "semantics": "unique explicit bridge per ODR-43; WP11 physical installation = PHYSICAL_INSTALLATION_AUTHORITY; "
                     "ODR-01 T_SM = DYNAMICS_FRAME_AUTHORITY; physical-installation quantities enter dynamics ONLY "
                     "through this bridge",
        "closed_form": "B = Trans(z_A0, +0.02275 m) . Rot(z_A0, +25.000014 deg)",
        "validation": [
            {"path": FB03_REL, "sha256": sha[FB03_REL], "role": "ROUNDTRIP_ORTHO_CHIRALITY_QUATERNION_VALIDATION"},
            {"path": FB04_REL, "sha256": sha[FB04_REL], "role": "MASS_CG_INERTIA_TRANSFORM_VALIDATION"},
            {"path": FB05_REL, "sha256": sha[FB05_REL], "role": "E21_SINGLE_CONSUMER_BRIDGED_RERUN"},
        ],
        "explicitly_not_in_bridge": [
            "M3R as-built datum 210.405 mm and yz pattern offsets (GEOMETRY rail; separate ruling required)",
            "M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json (composition convention pinned inside the bridge file)",
            "link-level D_i calibration (composes with this mount-level bridge, never substitutes)",
        ],
    }

    single_semantics = {
        "single_consumption_semantics": "PHYSICAL_AUTHORITY_BRIDGED_INTO_ODR01_DYNAMICS_FRAME",
        "resolved_by": "ODR-43 bridge (NOT by selection, NOT by averaging, NOT by uncertainty re-label)",
        "consumer_ambiguity_count": 0,
        "evidence": {"path": FB05_REL, "sha256": sha[FB05_REL]},
        "single_authoritative_m07_peak_base_attitude_deviation_deg": 29.41085537835705,
        "legacy_dual_lane_values_retained_as_evidence_not_anchors": {
            "odr01_lane_deg": 29.041965867604112,
            "wp11_lane_deg": 29.41085537835705,
            "delta_deg": 0.3688895107529362,
            "delta_nature": "frame-consumption difference carried explicitly by the bridge; standard_uncertainty=null",
        },
    }

    # ---------------- V6 candidate ------------------------------------------
    v6 = {
        "schema": "MECH_DYNAMICS_INTERFACE_V6_CANDIDATE",
        "candidate": True,
        "generated_local": "2026-08-23T20:00:00+08:00",
        "generator": "KIMI M7 Wave-2a AGENT-1 MPI-FB-07 (pure python; base files untouched)",
        "status": "CANDIDATE_ONLY__NOT_RELEASE_NOT_PRODUCTION_NOT_FLIGHT__PENDING_OWNER_REVIEW",
        "base_document": {
            "path": V5_R2_REL,
            "sha256": sha[V5_R2_REL],
            "inheritance_rule": "every section NOT listed under replaced_sections below is inherited with "
                                "byte-identical semantics from the base document; the base file is never modified",
            "relation_to_base": "BRIDGE_REBINDING_ONLY: adds the ODR-43 installation bridge binding and the "
                                "single-consumption semantics; changes nothing else",
        },
        "replaced_sections": {
            "frame_authority": {
                "classification": "DESIGN_AND_DYNAMICS_AUTHORITY",
                "carried_from_v5_r2": {
                    "m_frame_definition": "T_SM = [185.25, 0, 0] mm followed by Ry(90 deg) - ODR-01, UNCHANGED",
                    "physical_feature_stack": "198.0 / 208.0 / 210.405 mm stations remain a GEOMETRIC_FEATURE_STACK, "
                                              "must not become a second dynamics frame definition - UNCHANGED",
                },
                "new_in_this_candidate": {
                    "physical_installation_authority": "WP11 physical installation (208.0 mm + 25.000014 deg clocking "
                                                       "about +X_S) per ODR-43",
                    "dynamics_frame_authority": "ODR-01 T_SM - UNCHANGED",
                    "installation_bridge": bridge_block,
                    "single_consumption_semantics_block": single_semantics,
                },
            },
            "design_mass_model_binding": {
                "carried_from_v5_r2": "all member bindings, pinned constants and uncertainty policy UNCHANGED",
                "system_design_mass_properties_candidate_overlay": {
                    "path": LEDGER_CAND_REL,
                    "sha256": sha[LEDGER_CAND_REL],
                    "classification": "BRIDGED_CANDIDATE_LEDGER_SINGLE_CONSUMPTION_SEMANTICS",
                    "base_ledger": {"path": V3_R2_REL, "sha256": sha[V3_R2_REL],
                                    "note": "V3_R2 remains the accepted R2 design ledger; the candidate overlay "
                                            "never overwrites it (ODR-44)"},
                    "mass_invariant": "per-configuration candidate mass identical to V3_R2 with exact zero difference",
                },
            },
        },
        "sections_explicitly_untouched_by_reference": [
            "units", "failure_semantics", "joint_stiffness_candidate", "mechanism_parameters",
            "fea1_evidence_pointer", "diagnostic_load_anchors", "runtime_gates", "prohibitions",
            "required_acknowledgement", "source_register",
        ],
        "carried_verbatim_from_v5_gate": {
            "source": {"path": V5_GATE_REL, "sha256": sha[V5_GATE_REL]},
            "fail_closed_invariants": fail_closed_invariants,
        },
        "carried_verbatim_from_e21_authority": {
            "source": {"path": E21_AUTHORITY_REL, "sha256": sha[E21_AUTHORITY_REL]},
            "mandatory_holds": e21_mandatory_holds,
        },
        "standing_prohibitions_reaffirmed": [
            "no selection or averaging of the two placement frames",
            "no per-module frame mixing",
            "branch delta is not an uncertainty (standard_uncertainty stays null)",
            "no silent reuse of the legacy 24 kg mass model or the legacy R1 panel flexibility model",
            "no Route-C independent versioned CAD candidate before MPI-FB-01..08 all closed (ODR-44)",
            "accepted URDF / Solar R2 / M3R / Gripper R1 / M7 FEA evidence frozen (ODR-44)",
        ],
        "required_acknowledgement": "I_ACKNOWLEDGE_M7_V6_CANDIDATE_IS_A_BRIDGE_REBINDING_CANDIDATE_NOT_RELEASE_NOT_PRODUCTION_NOT_FLIGHT",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "source_register": [{"path": k, "sha256": v} for k, v in sha.items()],
    }

    # ---------------- R3 candidate ------------------------------------------
    r3 = {
        "schema": "EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE",
        "candidate": True,
        "generated_local": "2026-08-23T20:00:00+08:00",
        "generator": "KIMI M7 Wave-2a AGENT-1 MPI-FB-07 (pure python; base files untouched)",
        "status": "CANDIDATE_ONLY__NOT_RELEASE_NOT_PRODUCTION_NOT_FLIGHT__PENDING_OWNER_REVIEW",
        "base_document": {
            "path": R2_REL,
            "sha256": sha[R2_REL],
            "inheritance_rule": "every section NOT listed under replaced_sections below is inherited with "
                                "byte-identical semantics from the base R2 contract; the base file is never modified",
            "relation_to_base": "BRIDGE_REBINDING_ONLY: binds the ODR-43 mount-level installation bridge alongside "
                                "the existing link-level D_i calibration; changes nothing else",
        },
        "replaced_sections": {
            "authority_hierarchy": {
                "carried_from_r2": {
                    "kinematics": "ACCEPTED_URDF (L0) - UNCHANGED",
                    "mass_and_inertia_of_the_arm": "ACCEPTED_URDF (L0), never overridden - UNCHANGED",
                    "physical_geometry": "M7 CAD + SOLAR_ARRAY_R2_CANDIDATE_V1 - UNCHANGED",
                    "solar_flexibility": "FLEXIBLE_APPENDAGE_R2 (PROVISIONAL_DERIVED, ODR-21) - UNCHANGED",
                },
                "new_in_this_candidate": {
                    "system_mass_configurations_candidate_overlay": {
                        "path": LEDGER_CAND_REL,
                        "sha256": sha[LEDGER_CAND_REL],
                        "base": {"path": V3_R2_REL, "sha256": sha[V3_R2_REL]},
                        "note": "single-consumption-semantics bridged candidate; V3_R2 untouched",
                    },
                    "mount_level_installation_bridge": bridge_block,
                    "bridge_composition_rule": "the mount-level T_PHYSICAL_TO_DYNAMIC and the link-level D_i "
                                               "calibration COMPOSE (mount first, then per-link D_i); neither "
                                               "substitutes the other",
                    "single_consumption_semantics_block": single_semantics,
                },
            },
            "mounting_M3R_dynamics_frame_note": {
                "carried_from_r2": "T_SM = [185.25,0,0] mm + Ry(90 deg), EXACT_BY_DEFINITION, ODR-01 - UNCHANGED; "
                                   "the 198.0/208.0/210.405 mm feature stack warning is carried UNCHANGED",
                "new_in_this_candidate": "consumers needing the physical installation inside dynamics must apply "
                                         "the mount-level bridge (above); the M3R as-built datum 210.405 mm remains "
                                         "GEOMETRY-rail only and is NOT inside the bridge",
            },
        },
        "sections_explicitly_untouched_by_reference": [
            "consumer_contract", "kinematics", "dynamics", "collision", "grasp", "flexibility",
            "failure_states", "authority_and_uncertainty", "source_register",
        ],
        "carried_verbatim_from_r2_base": {
            "source": {"path": R2_REL, "sha256": sha[R2_REL]},
            "retained_holds": r2_retained_holds,
            "prohibitions_honored": r2_prohibitions,
        },
        "carried_verbatim_from_v5_gate": {
            "source": {"path": V5_GATE_REL, "sha256": sha[V5_GATE_REL]},
            "fail_closed_invariants": fail_closed_invariants,
        },
        "carried_verbatim_from_e21_authority": {
            "source": {"path": E21_AUTHORITY_REL, "sha256": sha[E21_AUTHORITY_REL]},
            "mandatory_holds": e21_mandatory_holds,
        },
        "standing_prohibitions_reaffirmed": [
            "no selection or averaging of the two placement frames",
            "no per-module frame mixing",
            "branch delta is not an uncertainty",
            "no silent reuse of the legacy 24 kg mass model or the legacy R1 panel flexibility model",
            "collision geometry still consumed THROUGH the calibration chain, never naive substitution",
            "no Route-C CAD before MPI-FB-01..08 all closed (ODR-44)",
        ],
        "required_acknowledgement": "I_ACKNOWLEDGE_R3_CANDIDATE_IS_A_BRIDGE_REBINDING_CANDIDATE_NOT_RELEASE_NOT_PRODUCTION_NOT_FLIGHT",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "source_register": [{"path": k, "sha256": v} for k, v in sha.items()],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    v6_path = OUT_DIR / "MECH_DYNAMICS_INTERFACE_V6_CANDIDATE.yaml"
    r3_path = OUT_DIR / "EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE.yaml"
    v6_path.write_bytes(yaml.safe_dump(v6, sort_keys=False, allow_unicode=True, width=200).encode("utf-8"))
    r3_path.write_bytes(yaml.safe_dump(r3, sort_keys=False, allow_unicode=True, width=200).encode("utf-8"))
    for p in (v6_path, r3_path):
        print("WROTE", p)
        print("sha256:", hashlib.sha256(p.read_bytes()).hexdigest().upper())

    # sentinel: base files must be untouched
    assert sha256_file(V5_R2_REL) == sha[V5_R2_REL]
    assert sha256_file(R2_REL) == sha[R2_REL]
    print("base files untouched: V5_R2 and R2 hashes unchanged")


if __name__ == "__main__":
    main()
