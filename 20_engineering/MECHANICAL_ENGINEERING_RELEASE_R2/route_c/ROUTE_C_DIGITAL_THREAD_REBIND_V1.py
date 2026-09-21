# ROUTE_C_DIGITAL_THREAD_REBIND_V1.py
# Stage RC-6 of R2 terminal dual-lane closure, lane A2.
# Emits the three digital-thread REBIND CANDIDATES into route_c/ (nothing
# overwritten; release-root 06/15/16 and the F3R2 bridge stay frozen):
#   UNIFIED_R2_SYSTEM_INTERFACE_V2.yaml      (delta candidate vs release-root 15)
#   EMBODIED_MECHANICAL_CONTRACT_R4.yaml     (delta candidate vs release-root 16)
#   MECH_DYNAMICS_INTERFACE_V7.yaml          (delta candidate vs release-root 06)
# plus the five new HARNESS_* machine states with UNKNOWN -> ABORT policy.
#
# Deterministic: all values read from the RC-4/RC-5 machine artifacts; no wall
# clock; fixed key order.
#
# Run: python ROUTE_C_DIGITAL_THREAD_REBIND_V1.py   (from this directory)

import hashlib
import json
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
REL = "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"

# RC-6 consumes the FINAL RC-4 gate/sweep artifacts.  Default VF (final gate);
# overridable for replay against earlier variant gates.
GATE_VARIANT = os.environ.get("RC_GATE_VARIANT", "VF").upper()
P_GATE = os.path.join(HERE, "ROUTE_C_MISSION_COVERAGE_GATE_%s.json" % GATE_VARIANT)
P_SWEEP = os.path.join(HERE, "ROUTE_C_EXACT_SWEEP_%s.json" % GATE_VARIANT)
P_MASS = os.path.join(HERE, "B601_ROUTE_C_MASS_PROPERTIES_V1.yaml")
P_DELTA = os.path.join(HERE, "B601_ROUTE_C_MASS_DELTA_BY_LINK_V1.yaml")
P_TORQUE = os.path.join(HERE, "B601_ROUTE_C_JOINT_TORQUE_ENVELOPE_V1.yaml")
P_NINE = os.path.join(HERE, "ROUTE_C_NINE_CONFIG_MASS_PROPAGATION_CANDIDATE_V1.json")

OUT_UIF = os.path.join(HERE, "UNIFIED_R2_SYSTEM_INTERFACE_V2.yaml")
OUT_EMC = os.path.join(HERE, "EMBODIED_MECHANICAL_CONTRACT_R4.yaml")
OUT_MDI = os.path.join(HERE, "MECH_DYNAMICS_INTERFACE_V7.yaml")

FROZEN_REFS = {
    "unified_r2_system_interface_v1": "%s/15_UNIFIED_R2_SYSTEM_INTERFACE.yaml" % REL,
    "embodied_mechanical_contract_r2": "%s/16_EMBODIED_MECHANICAL_CONTRACT.yaml" % REL,
    "physical_dynamics_bridge_ref_v1": "%s/06_PHYSICAL_DYNAMICS_BRIDGE.yaml" % REL,
    "release_gate_historical": "%s/00_RELEASE_GATE.json" % REL,
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def ydump(obj):
    return yaml.safe_dump(json.loads(json.dumps(obj, default=str)),
                          sort_keys=False, allow_unicode=True)


def main():
    gate = json.load(open(P_GATE, encoding="utf-8"))
    sweep = json.load(open(P_SWEEP, encoding="utf-8"))
    mass = yaml.safe_load(open(P_MASS, encoding="utf-8"))
    torque = yaml.safe_load(open(P_TORQUE, encoding="utf-8"))
    nine = json.load(open(P_NINE, encoding="utf-8"))

    verdict = gate["verdict"]
    pins = {k: v for k, v in gate["source_bindings"].items()}

    route_c_artifacts = {
        "route_c_centerline_v2": {
            "path": "%s/route_c/B601_ROUTE_C_HARNESS_CENTERLINE_V2.json" % REL,
            "sha256": pins["centerline"]["sha256"],
            "classification": "DESIGN_CANDIDATE",
            "status": "CURRENT_ROUTE_C_CENTERLINE",
        },
        "route_c_clamp_guide_register_v2": {
            "path": "%s/route_c/B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V2.csv" % REL,
            "sha256": pins["clamp_register"]["sha256"],
            "classification": "DESIGN_CANDIDATE",
            "status": "CURRENT_ROUTE_C_CLAMP_REGISTER",
        },
        "route_c_guided_dress_pack_cad_v2": {
            "path": "%s/route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V2.FCStd" % REL,
            "sha256": sha256_file(os.path.join(HERE, "B601_ROUTE_C_GUIDED_DRESS_PACK_V2.FCStd")),
            "classification": "DESIGN_CANDIDATE",
            "status": "CURRENT_ROUTE_C_CAD (84 parts, build receipt B601_ROUTE_C_BUILD_RECEIPT_V2.json)",
        },
        "route_c_exact_sweep_v2": {
            "path": "%s/route_c/ROUTE_C_EXACT_SWEEP_V2.json" % REL,
            "sha256": sha256_file(P_SWEEP),
            "classification": "DESIGN_CANDIDATE_EVALUATION",
            "status": "RC-4 exact full-trajectory verification evidence",
        },
        "route_c_mission_coverage_gate_v2": {
            "path": "%s/route_c/ROUTE_C_MISSION_COVERAGE_GATE_V2.json" % REL,
            "sha256": sha256_file(P_GATE),
            "classification": "CANDIDATE_GATE",
            "status": verdict,
        },
        "route_c_mass_properties_v1": {
            "path": "%s/route_c/B601_ROUTE_C_MASS_PROPERTIES_V1.yaml" % REL,
            "sha256": sha256_file(P_MASS),
            "classification": "DESIGN_CANDIDATE",
            "status": "RC-5 per-link mass/CG/inertia delta",
        },
        "route_c_mass_delta_by_link_v1": {
            "path": "%s/route_c/B601_ROUTE_C_MASS_DELTA_BY_LINK_V1.yaml" % REL,
            "sha256": sha256_file(P_DELTA),
            "classification": "DESIGN_CANDIDATE",
            "status": "independent per-link delta layer, single consumption",
        },
        "route_c_joint_torque_envelope_v1": {
            "path": "%s/route_c/B601_ROUTE_C_JOINT_TORQUE_ENVELOPE_V1.yaml" % REL,
            "sha256": sha256_file(P_TORQUE),
            "classification": "PROVISIONAL_DERIVED",
            "status": "RC-5 harness resistance torque envelope vs URDF effort budget",
        },
        "route_c_nine_config_mass_propagation_candidate_v1": {
            "path": "%s/route_c/ROUTE_C_NINE_CONFIG_MASS_PROPAGATION_CANDIDATE_V1.json" % REL,
            "sha256": sha256_file(P_NINE),
            "classification": "DESIGN_CANDIDATE",
            "status": "candidate layer only; 07_SYSTEM_MASS_PROPERTIES.yaml NOT modified",
        },
        "route_c_physical_capability_registry_v2": {
            "path": "%s/route_c/ROUTE_C_PHYSICAL_CAPABILITY_REGISTRY_V2.yaml" % REL,
            "sha256": pins["capability_registry"]["sha256"],
            "classification": "DESIGN_CANDIDATE / PROVISIONAL_DERIVED / BOUNDED_DATASHEET_RANGE",
            "status": "P01-P13 closure, ODR-53 authority",
        },
    }

    harness_machine_states = {
        "_semantics": {
            "unknown_policy": "ABORT",
            "rule": "any harness machine-state evaluation returning UNKNOWN masks to ABORT (fail-closed); no harness state is ever auto-allowed",
            "evaluation_source": "ROUTE_C_MISSION_COVERAGE_GATE_V2.json predicates + ROUTE_C_JOINT_TORQUE_ENVELOPE_V1.yaml",
        },
        "HARNESS_ROUTE_C_GUIDE_LIMIT": {
            "meaning": "guided service-loop take-up demand reached the segment storage capacity",
            "trigger": "any per-segment take_up margin_mm < 0 (capacity - R*(traversed range + 2*dq_total) - thermal)",
            "thresholds": {t["joint"]: {"margin_mm": t["margin_mm"], "capacity_mm": t["capacity_mm"]}
                           for t in sweep["take_up"]},
            "action": "ABORT",
            "unknown_is_fail_closed": True,
        },
        "HARNESS_BEND_MARGIN_LOW": {
            "meaning": "minimum guide-enforced bend radius at or below the P06 dynamic allocation",
            "trigger": "min bend radius < 50.0 mm (allocation); 50.0 <= R < 51.2 mm is LOW_MARGIN (derated rule: manufacturing 0.5 + thermal 0.2 + liner wear 0.5)",
            "current_value_mm": sweep["predicates"]["bend_radius"]["min_mm"],
            "margin_mm": sweep["predicates"]["bend_radius"]["margin_mm"],
            "action": "ABORT",
            "unknown_is_fail_closed": True,
        },
        "HARNESS_PINCH_RISK": {
            "meaning": "cable-to-housing pinch margin negative inside a joint interface band",
            "trigger": "any joint-band pinch margin_mm_gated < 0",
            "thresholds": {p["joint"]: {"margin_mm": p["pinch_margin_mm_gated"],
                                        "horizon_lower_bound": p.get("margin_is_horizon_lower_bound", False)}
                           for p in sweep["pinch"]},
            "action": "ABORT",
            "unknown_is_fail_closed": True,
        },
        "HARNESS_GUIDE_TRAVEL_LIMIT": {
            "meaning": "J3 festoon carriage excursion reached a hard stop",
            "trigger": "festoon carriage demand >= 55.0 mm half-stroke hard stop (margin_mm < 0)",
            "thresholds": {"demand_mm": sweep["carrier_travel"]["demand_mm"],
                           "hard_stop_half_stroke_mm": 55.0,
                           "margin_mm": sweep["carrier_travel"]["margin_mm"]},
            "action": "ABORT",
            "unknown_is_fail_closed": True,
        },
        "HARNESS_ENVELOPE_VIOLATION": {
            "meaning": "cable tube (OD 9 mm) contacts a non-intended obstacle (vendor link shell, other-segment RC hardware, bus, solar wing, gripper rail) or unexplained penetration exists",
            "trigger": "mission clearance worst_mm_gated < 0 after MISSION_TRACKING_TUBE_CANDIDATE derate",
            "current_worst_mm_gated": sweep["predicates"]["clearance"]["worst_mm_gated"],
            "action": "ABORT",
            "unknown_is_fail_closed": True,
        },
    }

    # ---------------- UNIFIED_R2_SYSTEM_INTERFACE_V2 (candidate) ----------------
    uif = {
        "schema": "UNIFIED_R2_SYSTEM_INTERFACE_V2_CANDIDATE",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "candidate_status": "ADDITIVE_CANDIDATE_NOT_A_REPLACEMENT - release-root 15_UNIFIED_R2_SYSTEM_INTERFACE.yaml remains the frozen V1 interface; this V2 candidate adds the Route-C harness bindings after RC-4/RC-5 closure",
        "decision_rule": "Authority > Evidence > Independent reproduction > Agent opinion",
        "fail_closed_invariants": [
            "UNKNOWN is never PASS",
            "null is never zero-filled",
            "a test PASS is not a design Gate PASS",
            "hash_mismatch aborts consumption",
        ],
        "carried_v1_bindings": "all bindings of 15_UNIFIED_R2_SYSTEM_INTERFACE.yaml carried unchanged (accepted URDF, system URDF candidate, frame tree, MPI bridge, Solar R2, ROM, gripper R1, contact model, M3R ICD, nine-config mass, harness envelope legacy, collision broadphase, embodied contract, E22/E15 gates)",
        "superseded_slots": {
            "harness_rated_envelope": {
                "v1_value": "B601_HARNESS_RATED_ENVELOPE_V1.yaml (0/75 SAFE, fixed external dress)",
                "v2_candidate_value": "Route-C guided dress pack; see route_c_mission_coverage_gate_v2",
                "rule": "v1 remains the frozen negative-result anchor; v2 is a candidate, not an overwrite",
            },
            "harness_mission_coverage_gate": {
                "v1_value": "B601_HARNESS_MISSION_COVERAGE_GATE.json FAIL_AT_MANDATORY_KEY_STATES",
                "v2_candidate_value": "ROUTE_C_MISSION_COVERAGE_GATE_V2.json verdict=%s" % verdict,
                "rule": "v1 verdict preserved verbatim; v2 candidate additive",
            },
        },
        "route_c_bindings": route_c_artifacts,
        "route_c_disposition": {
            "selection": "ROUTE_C_GUIDED_DRESS_PACK_V2 mission-rated candidate",
            "basis": "ODR-42/52/53/54; mission coverage target E_MISSION_SUBSET_OF_E_ROUTE_C",
            "gate_verdict": verdict,
            "full_hardware_range": "DEFERRED_HOLD (not required per ODR-54)",
        },
        "harness_machine_states_added": list(harness_machine_states.keys())[1:],
        "failure_state_registry": {
            "carried": "UNKNOWN/ABORT_ONLY/HOLD/MEASUREMENT_PENDING/DEFERRED_HOLD semantics carried from V1",
            "added_harness_states": {k: v for k, v in harness_machine_states.items() if not k.startswith("_")},
        },
        "frozen_refs": FROZEN_REFS,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    with open(OUT_UIF, "w", encoding="utf-8", newline="\n") as f:
        f.write(ydump(uif))

    # ---------------- EMBODIED_MECHANICAL_CONTRACT_R4 (candidate) ----------------
    emc = {
        "schema": "EMBODIED_MECHANICAL_CONTRACT_R4_CANDIDATE",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "candidate_status": "ADDITIVE_CANDIDATE_NOT_A_REPLACEMENT - release-root 16_EMBODIED_MECHANICAL_CONTRACT.yaml (R2) remains the frozen contract of record; this R4 candidate adds the Route-C harness section after RC-4/RC-5 closure",
        "consumer_contract": {
            "required_acknowledgement": "I_ACKNOWLEDGE_THESE_ARE_DESIGN_LEVEL_MECHANICAL_VALUES_WITH_DECLARED_UNCERTAINTY_NOT_MEASURED_HARDWARE_AND_NOT_FLIGHT_QUALIFIED",
            "unknown_is_fail_closed": True,
            "null_means": "a physical or external input is genuinely absent. null is never a zero and never a default.",
            "bare_nominal_forbidden": True,
        },
        "carried_r2_sections": "kinematics/dynamics/collision/grasp/flexibility/failure_states/authority_and_uncertainty of the R2 contract carried unchanged; accepted URDF remains the kinematics and arm-inertials authority (bytes unchanged, sha256 pinned)",
        "harness_route_c": {
            "architecture": "ROUTE_C_SEGMENTED_GUIDED_DRESS_PACK_V2 (ODR-52): bus feedthrough -> J1 annular service loop -> link1 channel -> J2 guided U-loop -> link2 channel -> J3 carrier-hybrid -> link3 channel -> J4 omega loop -> link4 riser -> J5 wrist wrap -> J6 helical wrap -> wrist strain relief",
            "centerline": route_c_artifacts["route_c_centerline_v2"],
            "kinematic_attachment_model": sweep["kinematic_attachment_model"],
            "tracking_tube": sweep["tracking_tube_candidate"],
            "bundle": {
                "od_mm": 9.0,
                "installed_od_bounded_range_mm": [8.0, 10.0],
                "linear_density_g_per_m": {"nominal": 65.0, "bounded_range": [56.5, 72.5]},
                "authority": "PROVISIONAL_DERIVED (registry P09)",
            },
            "per_joint_loops": {
                t["joint"]: {
                    "loop_radius_mm": t["loop_radius_mm"],
                    "take_up_capacity_mm": t["capacity_mm"],
                    "take_up_margin_mm_mission": t["margin_mm"],
                    "take_up_margin_mm_full_range": t["margin_full_hardware_range_mm"],
                    "authority": "DESIGN_CANDIDATE",
                } for t in sweep["take_up"]
            },
            "j3_carrier": {
                "stroke_mm": 110.0,
                "hard_stop_half_stroke_mm": 55.0,
                "margin_mm_mission": sweep["carrier_travel"]["margin_mm"],
                "authority": "DESIGN_CANDIDATE (igus E2.10 class; TVAC applicability registered C6 hold)",
            },
            "bend_radius": {
                "min_mm": sweep["predicates"]["bend_radius"]["min_mm"],
                "limit_mm": 50.0,
                "derated_design_rule_mm": 51.2,
                "authority": "DESIGN_CANDIDATE",
            },
            "resistance_torque": {
                "per_joint": torque["per_joint"],
                "worst_fraction_of_budget": torque["worst_fraction_of_budget"],
                "unknown_components": torque["unknown_components"],
                "authority": "PROVISIONAL_DERIVED, confidence LOW",
            },
            "mass_delta_layer": {
                "ref": route_c_artifacts["route_c_mass_delta_by_link_v1"],
                "total_delta_kg": mass["totals"]["mass_g"] / 1000.0,
                "consumption_rule": "independent per-link delta layer; consumed exactly once; accepted URDF inertials unchanged; no double counting with any system interface",
            },
            "mission_coverage_gate": route_c_artifacts["route_c_mission_coverage_gate_v2"],
        },
        "failure_states_added": harness_machine_states,
        "authority_and_uncertainty_delta": {
            "new_quantities": "harness take-up margins, carrier travel margin, bend radius, pinch margins, resistance torque bounds, per-link mass deltas",
            "authority_levels": ["DESIGN_CANDIDATE", "PROVISIONAL_DERIVED", "BOUNDED_DATASHEET_RANGE"],
            "forbidden": ["MEASURED", "AS_BUILT", "FLIGHT_QUALIFIED"],
            "registered_holds": gate["declared_holds"],
        },
        "frozen_refs": FROZEN_REFS,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    with open(OUT_EMC, "w", encoding="utf-8", newline="\n") as f:
        f.write(ydump(emc))

    # ---------------- MECH_DYNAMICS_INTERFACE_V7 (candidate) ----------------
    mdi = {
        "schema": "MECH_DYNAMICS_INTERFACE_V7_CANDIDATE",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "candidate_status": "ADDITIVE_CANDIDATE_NOT_A_REPLACEMENT - release-root 06_PHYSICAL_DYNAMICS_BRIDGE.yaml and the frozen MPI bridge (CHECKPOINT_A_A02_PASS) remain the dynamics interface of record; this V7 candidate adds the Route-C harness dynamics layer",
        "bridge_carried": {
            "mpi_physical_to_dynamics_bridge": "B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml (CONFIRMED, CHECKPOINT_A_A02_PASS; T_PHYSICAL_TO_DYNAMIC pure z-screw 22.75 mm + 25.000014 deg)",
            "bridge_gate": "MPI_BRIDGE_GATE_V1.json PASS_9_OF_9",
        },
        "harness_dynamics_layer": {
            "mass": {
                "rule": "Route-C mass enters dynamics ONLY as the independent per-link delta layer B601_ROUTE_C_MASS_DELTA_BY_LINK_V1.yaml; accepted URDF bytes and inertials unchanged; each increment consumed exactly once; no double counting with the unified system interface or the nine-configuration model",
                "per_link_delta": mass["per_link_delta_urdf_frame"],
                "bus_mounted_group": "feedthrough channel + bus clamps, static in S (pose invariant), not a URDF arm member",
                "totals": mass["totals"],
                "nine_configuration_candidate": {
                    "ref": route_c_artifacts["route_c_nine_config_mass_propagation_candidate_v1"],
                    "envelope_evaluation": nine["envelope_evaluation"],
                    "rule": "candidate layer only; release-root 07_SYSTEM_MASS_PROPERTIES.yaml and V3_R2 are NOT modified",
                },
            },
            "joint_resistance_torque": {
                "ref": route_c_artifacts["route_c_joint_torque_envelope_v1"],
                "model": torque["model"],
                "per_joint": torque["per_joint"],
                "odr50_reopen_guard": torque["odr50_reopen_guard"],
                "unknown_components": torque["unknown_components"],
            },
            "harness_machine_states": harness_machine_states,
            "safety_rules": {
                "unknown_to_abort": "every harness machine-state evaluation returning UNKNOWN masks to ABORT (fail-closed); no harness state is auto-allowed",
                "envelope_interlock": "if ROUTE_C_MISSION_COVERAGE_GATE_V2 verdict is not a PASS form, arm mission tasks consuming harness safety must not be authorized (next_stage_authorized=false)",
                "tracking_tube": sweep["tracking_tube_candidate"],
            },
        },
        "consumption_contract": {
            "accepted_urdf": "sha256 pinned, bytes unchanged (modification FORBIDDEN)",
            "frozen_assets": "Solar R2 / M3R / Gripper R1 / MPI bridge / E23 / release-root files untouched",
            "no_git_mutation": True,
            "authority_levels": ["DESIGN_CANDIDATE", "PROVISIONAL_DERIVED", "BOUNDED_DATASHEET_RANGE"],
        },
        "frozen_refs": FROZEN_REFS,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    with open(OUT_MDI, "w", encoding="utf-8", newline="\n") as f:
        f.write(ydump(mdi))

    for p in (OUT_UIF, OUT_EMC, OUT_MDI):
        print(os.path.basename(p), sha256_file(p))
    print("REBIND_COMPLETE")


if __name__ == "__main__":
    main()
