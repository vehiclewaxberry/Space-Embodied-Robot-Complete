"""Build the current mechanical-loop stage gate without mutating any baseline.

This integrator binds the scoped M4 release, the later M7/Route-B negative
evidence, the Route-C authorization-front package, and the Sim13 downstream
binding audit.  A PASS from either package validator is an integrity result;
it is never promoted to a mechanical or dynamics release.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
BASE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope"
)
OUT_REL = f"{BASE_REL}/10_loop_integration"

INPUTS = {
    "m4_release_gate": (
        "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/"
        "12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json"
    ),
    "m7_release_gate": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "12_release/MECHANICAL_ENGINEERING_RELEASE_GATE_V1.json"
    ),
    "route_b_terminal_gate": f"{BASE_REL}/07_release/B601_HARNESS_TERMINAL_GATE_V1.json",
    "handoff_v2_gate": f"{BASE_REL}/07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json",
    "route_c_cad_entry_gate": f"{BASE_REL}/08_route_c/ROUTE_C_CAD_ENTRY_GATE_V1.json",
    "route_c_validation": f"{BASE_REL}/08_route_c/ROUTE_C_PRELIMINARY_VALIDATION_V1.json",
    "sim13_binding_audit_gate": (
        f"{BASE_REL}/09_downstream_rebind/"
        "SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json"
    ),
    "sim13_binding_validation": (
        f"{BASE_REL}/09_downstream_rebind/"
        "SIM13_CURRENT_BINDING_AUDIT_VALIDATION_REPORT_V1.json"
    ),
    "accepted_urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
}

EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_SIM13_VERDICT = (
    "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(relative_path: str) -> dict[str, Any]:
    return json.loads((REPO / relative_path).read_text(encoding="utf-8"))


def write_json(relative_path: str, value: Any) -> None:
    path = REPO / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def bind_inputs() -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for name, relative_path in INPUTS.items():
        path = REPO / relative_path
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"required input is missing or empty: {relative_path}")
        bindings.append(
            {
                "name": name,
                "path": relative_path,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return bindings


def build_gate() -> dict[str, Any]:
    m4 = read_json(INPUTS["m4_release_gate"])
    m7 = read_json(INPUTS["m7_release_gate"])
    route_b = read_json(INPUTS["route_b_terminal_gate"])
    handoff = read_json(INPUTS["handoff_v2_gate"])
    route_c = read_json(INPUTS["route_c_cad_entry_gate"])
    route_c_validation = read_json(INPUTS["route_c_validation"])
    sim13 = read_json(INPUTS["sim13_binding_audit_gate"])
    sim13_validation = read_json(INPUTS["sim13_binding_validation"])

    criterion_09 = next(
        item for item in m7["criteria"] if str(item.get("id")) == "09"
    )
    g12 = next(item for item in handoff["checks"] if item.get("id") == "G12")
    m4_tokens = m4["release_tokens"]
    sim_authority = sim13["current_authority"]

    facts = [
        {
            "id": "LG-01",
            "name": "M4_IS_SCOPED_WORKING_RELEASE_ONLY",
            "observed": (
                m4_tokens["digital_prototype"]["issued"] is True
                and m4_tokens["structural_entry"]["issued"] is False
                and m4_tokens["production_contact_rl"]["issued"] is False
            ),
            "evidence": {
                "overall_status": m4["overall_status"],
                "digital_prototype_status": m4_tokens["digital_prototype"]["status"],
                "structural_entry": m4_tokens["structural_entry"]["status"],
                "production_contact_rl": m4_tokens["production_contact_rl"]["status"],
            },
        },
        {
            "id": "LG-02",
            "name": "M7_MAIN_GATE_REMAINS_UNRELEASED",
            "observed": (
                m7["next_stage_authorized"] is False
                and criterion_09["state"] == "HOLD"
                and m7["terminal_release_condition"]["all_met"] is False
            ),
            "evidence": {
                "overall_gate_a_shape": m7["overall_gate_a_shape"],
                "criterion_09": criterion_09["state"],
                "next_stage_authorized": m7["next_stage_authorized"],
            },
        },
        {
            "id": "LG-03",
            "name": "ROUTE_B_REJECTED_AND_MECHANICAL_NOT_RELEASED",
            "observed": (
                route_b["route_b"] == "REJECTED"
                and route_b["mechanical_design"] == "NOT_RELEASED"
                and route_b["next_stage_authorized"] is False
            ),
            "evidence": {
                "route_b": route_b["route_b"],
                "route_c": route_b["route_c"],
                "internal_mechanical_hold_count": route_b["internal_mechanical_hold_count"],
            },
        },
        {
            "id": "LG-04",
            "name": "CURRENT_HANDOFF_FAILS_G12",
            "observed": (
                handoff["checks_passed"] == 11
                and handoff["checks_total"] == 12
                and handoff["verdict"] == "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL"
                and g12["pass"] is False
            ),
            "evidence": {
                "passed": handoff["checks_passed"],
                "total": handoff["checks_total"],
                "failing_checks": handoff["failing_checks"],
            },
        },
        {
            "id": "LG-05",
            "name": "ROUTE_C_AUTHORIZATION_FRONT_PACKAGE_VALID_BUT_CAD_ENTRY_HOLD",
            "observed": (
                route_c_validation["package_integrity_pass"] is True
                and route_c_validation["checks_passed"]
                == route_c_validation["checks_total"]
                and route_c["gate"] == "HOLD"
                and route_c["next_stage_authorized"] is False
            ),
            "evidence": {
                "validation": route_c_validation["verdict"],
                "checks": (
                    f'{route_c_validation["checks_passed"]}/'
                    f'{route_c_validation["checks_total"]}'
                ),
                "detailed_design_start_blockers": route_c["detailed_design_start_blockers"],
            },
        },
        {
            "id": "LG-06",
            "name": "SIM13_CURRENT_PRODUCTION_BINDING_INVALIDATED",
            "observed": (
                sim13["verdict"] == EXPECTED_SIM13_VERDICT
                and sim13["verdict_issued"] is True
                and sim13["next_stage_authorized"] is False
                and sim13_validation["verdict"] == "PASS"
                and sim13_validation["checks_passed"] == sim13_validation["checks_total"]
                and sim13_validation["negative_controls_passed"]
                == sim13_validation["negative_controls_total"]
            ),
            "evidence": {
                "verdict": sim13["verdict"],
                "checks": (
                    f'{sim13_validation["checks_passed"]}/'
                    f'{sim13_validation["checks_total"]}'
                ),
                "negative_controls": (
                    f'{sim13_validation["negative_controls_passed"]}/'
                    f'{sim13_validation["negative_controls_total"]}'
                ),
            },
        },
        {
            "id": "LG-07",
            "name": "ACCEPTED_URDF_UNCHANGED",
            "observed": sha256_file(REPO / INPUTS["accepted_urdf"])
            == EXPECTED_URDF_SHA256,
            "evidence": {"sha256": sha256_file(REPO / INPUTS["accepted_urdf"])},
        },
    ]

    facts_confirmed = sum(bool(item["observed"]) for item in facts)
    facts_all_confirmed = facts_confirmed == len(facts)
    current_release = {
        "route_c_parametric_cad_entry_ready": False,
        "mechanical_design_released": False,
        "production_dynamics_ready": False,
        "physical_contact_ready": False,
        "physics_gated_rl_ready": False,
        "hardware_motion_ready": False,
        "diagnostic_kinematic_research_only": (
            m4_tokens["bounded_diagnostic_dynamics"]["issued"] is True
            and sim_authority["diagnostic_kinematic_bootstrap_only"] is True
        ),
        "abort_always_available": sim_authority["abort_always_available"] is True,
        "flight_qualification_ready": False,
    }

    generated_local = route_c_validation["generated_local"]
    return {
        "schema": "MECHANICAL_LOOP_ENGINEERING_STAGE_GATE_V1",
        "generated_local": generated_local,
        "generated_clock_source": "LATEST_BOUND_ROUTE_C_VALIDATION_TIMESTAMP",
        "authority_scope": "CURRENT_STAGE_INTEGRATION__NO_NEW_DESIGN_AUTHORITY",
        "decision_rule": "Authority > later evidence > independent reproduction > opinion",
        "fail_closed_invariants": [
            "UNKNOWN is never PASS",
            "package integrity PASS is not a physical release",
            "a historical PASS cannot override newer contradictory machine evidence",
            "user intent is not silently converted into an Owner decision record",
        ],
        "input_bindings": bind_inputs(),
        "facts": facts,
        "facts_total": len(facts),
        "facts_confirmed": facts_confirmed,
        "current_release": current_release,
        "verdict": (
            "MECHANICAL_LOOP_ENGINEERING_PRE_CAD_HOLD_WITH_ACTIONABLE_ROUTE_C_"
            "PACKAGE_AND_SIM13_FAIL_CLOSED_SUPERSESSION"
            if facts_all_confirmed
            else "MECHANICAL_LOOP_ENGINEERING_INPUT_INTEGRITY_HOLD"
        ),
        "authorization_front_package_complete": facts_all_confirmed,
        "next_executable_actions_without_new_authority": [
            "Owner disposition of the hash-bound ODR-42 request",
            "acquire and configuration-control minimum cable, connector, interface and life inputs",
            "preserve diagnostic-only Sim13/Sim14 research and ABORT semantics",
        ],
        "one_pass_sequence_after_required_authority_and_inputs": [
            "C2 separately versioned STEP-first Route-C parametric design",
            "C3 release all eight continuous mission trajectories",
            "C4 exact coupled mission-first predicate; full hardware range only if explicitly required",
            "C5 recompute Route-C and nine-configuration mass/CG/inertia plus restoring loads",
            "C6 close abrasion, TVAC, flex-life and post-install electrical verification plan/evidence",
            "C7 issue a new hash-bound interface and runtime harness gate with negative controls",
            "independently pass mechanical handoff, physical-contact and production-dynamics gates",
        ],
        "explicit_noninheritance": [
            "Route-B 0.68406762184 kg diagnostic mass",
            "Route-B 10 mm bundle OD seed",
            "Route-B 30 mm bend-radius seed",
            "Route-B 4001.158 mm cut-length seed",
            "historical Sim13 V1 production-binding label beyond its kinematic bootstrap scope",
        ],
        "next_stage_authorized": False,
        "required_owner_action": (
            "Issue an independent ODR-42 disposition referencing the current request hash; "
            "APPROVE_BOUNDED_DETAILED_DESIGN is required before geometry creation."
        ),
        "prohibition": (
            "No Route-C CAD/STEP generation, production dynamics, physical-contact RL, "
            "hardware motion, manufacturing release or flight claim from this gate."
        ),
    }


def main() -> None:
    gate_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_STAGE_GATE_V1.json"
    manifest_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_OUTPUT_MANIFEST_V1.json"
    write_json(gate_rel, build_gate())
    manifest = {
        "schema": "MECHANICAL_LOOP_ENGINEERING_OUTPUT_MANIFEST_V1",
        "hash_algorithm": "SHA-256",
        "outputs": [
            {
                "path": gate_rel,
                "sha256": sha256_file(REPO / gate_rel),
                "bytes": (REPO / gate_rel).stat().st_size,
            }
        ],
        "sources": [
            {
                "path": f"{BASE_REL}/99_tools/build_mechanical_loop_stage_gate.py",
                "sha256": sha256_file(Path(__file__).resolve()),
                "bytes": Path(__file__).resolve().stat().st_size,
            },
            {
                "path": f"{BASE_REL}/99_tools/validate_mechanical_loop_stage_gate.py",
                "sha256": sha256_file(
                    REPO / f"{BASE_REL}/99_tools/validate_mechanical_loop_stage_gate.py"
                ),
                "bytes": (
                    REPO / f"{BASE_REL}/99_tools/validate_mechanical_loop_stage_gate.py"
                ).stat().st_size,
            },
        ],
        "output_count": 1,
        "source_count": 2,
        "validation_report_excluded_to_avoid_recursive_hash": True,
    }
    write_json(manifest_rel, manifest)
    built_gate = read_json(gate_rel)
    print(
        json.dumps(
            {
                "verdict": built_gate["verdict"],
                "facts": f'{built_gate["facts_confirmed"]}/{built_gate["facts_total"]}',
                "gate_sha256": sha256_file(REPO / gate_rel),
                "manifest_sha256": sha256_file(REPO / manifest_rel),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
