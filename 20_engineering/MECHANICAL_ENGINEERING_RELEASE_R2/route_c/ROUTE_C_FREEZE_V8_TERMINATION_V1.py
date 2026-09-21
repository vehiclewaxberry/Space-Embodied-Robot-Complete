#!/usr/bin/env python3
"""Freeze the bounded V8 Route-C redesign termination state.

This writer is intentionally fail-closed.  It emits no mission Gate, TMG-2
rebaseline, system-binding Gate, handoff PASS, or release credit.  It only
records the hash-bound early-rejection evidence, conservative candidate
accounting, visual scope, and the Owner decision now required.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


EXPECTED_SHA256 = {
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_INPUT_MANIFEST_V1.json": "6FC247608661C256850BAABDE906C4D03A7A1DE3BF62B8214B21E4D5C309C8AA",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/B601_ROUTE_C_BUILD_V8.py": "A901EA3873F16315FFE3A6495335DB9CCC8157986F1F784D8B55E10187A4BA43",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.FCStd": "BEB26BAB6A5500BDEED62A1D3C0BD8F48023EDF2D840FB68B16AD2A6F4BA29AA",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step": "CF06397029EDAB6476630DE33B396CE838A308E6BFF2D95D7E225E725A963215",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/V8_LOOP1_EARLY_REJECTION_V1.json": "1F9ABBB2CC7B7CF17570A1002AA249D96C78C885985461AF56293CB31FECD439",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/ROUTE_C_SWEEP_MESH_PACK_V8/MANIFEST.json": "C4F46688BE14D3859E899EB79C1BE265DC34679972B8F1CB65E4B7F82F34E699",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/B601_ROUTE_C_BUILD_V8.py": "B81808C5E5638B5F2F3A6A6758AFF4EAB34C6B06AE1873F66B34CFA43D1D3E67",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.FCStd": "AED4D06085541CF2490079CF4EA41A762E4F707EFD0F02E9ED91ADADD4A28513",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step": "1A9D18907A21CA1A8342D27AF2CD29D3C79A3D1BFC9FCEC039DC1144905CCAE5",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/ROUTE_C_STOW_SITE_FAST_CHECK_V8.json": "13AF67D7D9DDE436E4D94EE5D56C54BB96CD1D544868D2DE4BB3EE84009EBE58",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/ROUTE_C_SWEEP_MESH_PACK_V8/MANIFEST.json": "90F57B94D27B51F8DDE259078BB38D5D3E56CA8F0D2434F2F948ECEFFE706DE5",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/B601_ROUTE_C_BUILD_V8.py": "D0C0D1E60EFD0F58D7639F5F28E4B93D26B4BE897569A01EFFBB3941750C235E",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.FCStd": "CF5F93986B9380AD165E2C446D47D8771F5E9561F0805361E40510FDB7C7A306",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step": "45B0AA524E9BABCF5B4DB7F213ABB8D6FFF5227E72426D75F5EC229E2ED4FEF0",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/ROUTE_C_STOW_SITE_FAST_CHECK_V8.json": "C1C05DC4044B9604D9518C8BC3AF7592AD3AE4C1B36D1FCFE34A8F091DF36A67",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/ROUTE_C_SWEEP_MESH_PACK_V8/MANIFEST.json": "B21BFB3ECBDB568E03CB5DC9636B61261A85DD625BC055B9E1BBC5352E3F75B8",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_BUILD_V8.py": "78874967B781D12F0E37F077804A2B8EEA43EFC8DBDE867CF9C6FAD2D677E0E9",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.FCStd": "E842ACF96165DBA95BB3301572975E9F2AD70D3B5AC69CC33CBBBC93CF2F3A44",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step": "C9D7028C2DEFC305612FAF700FB6AC75F7B8E01182D23ACEBF9D03E4E9E8F8F3",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_BUILD_RECEIPT_V8.json": "BD122C4AE8F9BBAD81A95A6A7D0EC26A0F66E5A1627CF7A19B6F7CC92F6A3454",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_HARNESS_CENTERLINE_V8.json": "164C4E18CEBE2A91831728BC5BC35EE076F4E60A4404C8731FEC8E5B3B2D1702",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V8.csv": "5D801D9B51DA3DA55F341F350000F1B31AAB06061296257B3AF2EE77005EA2C3",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V8.json": "A2127665D719F93C69B52BA105E9B33717C1EAFAE6CDEF4C558119A07DFE336B",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_SWEEP_MESH_PACK_V8/MANIFEST.json": "9A50BF1D165ACBAD600C91D5EB82998DB7D3832AE5831B00589FAC18236E27D2",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_EXACT_SWEEP_V1.py": "CA8FB76CA6241B5B50201BC68CC8379C5196162301088AE9CBCBC9379301FBE5",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_STOW_SITE_FAST_CHECK_V8.json": "9DF6DA1ECEF490ABE85078D516F0FB7919F85CD9CECD93FB50373C6277C791D2",
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_fastcheck_scratch/sweep_scratch.json": "1F73F91D24BFF31346D98C6697C3DD0E186D9036F7B3BCB32A97A9770C9846B0",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM": "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step": "A7549D0E913584FA4AF894A710F5CE9DF363722FD7F4F863B1C3B3FF2B4653C2",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/11_screenshots/RAW/S01_DEPLOYED_NOMINAL_ISO.png": "884AF8549C09617E962445246D3AEAA2DA379EEC613A30CC7E25565B43094874",
    "40_evidence/artifacts/visualization/figures/fig_v01_system_assembly_isometric.png": "07EE73F09627C77D529F0547F27E2C8EBF0C9D0FF2A324FCB82F6E241D6874F0",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def verify_pins() -> dict[str, dict[str, object]]:
    verified: dict[str, dict[str, object]] = {}
    failures: list[str] = []
    for rel, expected in EXPECTED_SHA256.items():
        path = ROOT / rel
        if not path.is_file():
            failures.append(f"missing: {rel}")
            continue
        actual = sha256(path)
        if actual != expected:
            failures.append(f"hash mismatch: {rel}: {actual} != {expected}")
        verified[rel] = {
            "sha256": actual,
            "bytes": path.stat().st_size,
            "match": actual == expected,
        }
    if failures:
        raise SystemExit("\n".join(failures))
    return verified


def load_json(rel: str) -> dict:
    with (ROOT / rel).open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def state_by_id(fastcheck: dict, state_id: str) -> dict:
    matches = [row for row in fastcheck["key_states"] if row["state_id"] == state_id]
    if len(matches) != 1:
        raise SystemExit(f"expected one state {state_id}, found {len(matches)}")
    return matches[0]


def write_json(path: Path, payload: dict) -> dict[str, object]:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}


def main() -> int:
    pins = verify_pins()
    current = load_json("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_STOW_SITE_FAST_CHECK_V8.json")
    loop2 = load_json("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/ROUTE_C_STOW_SITE_FAST_CHECK_V8.json")
    candidate3_pre = load_json("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/ROUTE_C_STOW_SITE_FAST_CHECK_V8.json")
    scratch = load_json("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_fastcheck_scratch/sweep_scratch.json")

    if current["summary"]["key_states_unsafe_count"] != 10 or len(current["key_states"]) != 10:
        raise SystemExit("current V8 must retain 10/10 unsafe mandatory key states")
    if current["next_stage_authorized"] or current["release_credit"]:
        raise SystemExit("current V8 unexpectedly carries authorization or release credit")
    if not current["summary"]["clamp_and_guide_support_bore_axis_pass"]:
        raise SystemExit("expected local clamp/guide bore-axis predicate to pass")
    if not current["summary"]["d3_open_sector_retention_pass"]:
        raise SystemExit("expected local D3 retention predicate to pass")
    if not scratch["predicates"]["pinch"]["pass"] or scratch["predicates"]["pinch"]["worst_mm_gated"] <= 0:
        raise SystemExit("expected local D2 pinch predicate to pass with positive margin")
    if not scratch["predicates"]["d3_open_sector_retention"]["pass"]:
        raise SystemExit("expected local D3 retention predicate to pass in scratch evidence")
    if scratch["predicates"]["rc_hardware_cross_clearance"]["evaluated"]:
        raise SystemExit("early-filter scratch must not masquerade as a completed RC hardware cross-clearance Gate")
    if scratch["predicates"]["rc_hardware_cross_clearance"]["pass"]:
        raise SystemExit("NOT_EVALUATED RC hardware cross-clearance must remain fail-closed")

    stow = state_by_id(current, "ARM_STOWED_ONORBIT_C05")
    release = state_by_id(current, "ARM_RELEASE_CLEAR")
    home = state_by_id(current, "Q_DEPLOYED_HOME")
    if release["detail"]["field"] != "rc:RC-CLP-J4-MOV" or release["clearance_mm_raw"] >= 0:
        raise SystemExit("binding J4 moving-clamp penetration is absent")
    if home["detail"]["field"] != "rc:RC-CHN-L3-BASE" or home["clearance_mm_raw"] >= 0:
        raise SystemExit("binding L3 channel-base penetration is absent")

    common = {
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "authority": "HASH_BOUND_BOUNDED_DESIGN_LOOP_RECORD__NOT_A_RELEASE_GATE",
        "owner_limits": {
            "technically_distinct_candidate_limit_per_defect": 3,
            "material_build_to_sweep_loop_limit": 4,
            "mandatory_coverage": "ODR-54 complete mission-rated envelope",
        },
        "fail_closed_invariants": [
            "UNKNOWN is never PASS",
            "null is never coerced to zero",
            "raw solid penetration cannot be allowlisted by Euclidean proximity alone",
            "an early-filter PASS for one predicate is not a mission Gate PASS",
            "a rejected geometry is not propagated into TMG-2 or Sim13 as an accepted design",
        ],
    }

    history = {
        "schema": "ROUTE_C_V8_REDESIGN_HISTORY_V1",
        **common,
        "scope": "Owner-authorized bounded V8 local redesign for D1/D2/D3 only",
        "candidate_and_loop_accounting": {
            "material_build_to_sweep_states_observed": 4,
            "material_loop_budget_exhausted": True,
            "named_candidate_labels_observed": 3,
            "three_technically_distinct_concepts_proven": False,
            "conservative_reason": "Loop-1 was dominated by an over-broad alternate-host assignment; Loop-2 and Candidate-3 remain within the same full 9 mm bundle plus R55 external-standoff family. The J3 boundary correction is a host-boundary remediation, not a new heterogeneous concept.",
            "local_external_guided_architecture_infeasibility_proven": False,
        },
        "loops": [
            {
                "loop": 1,
                "candidate": "V8_LOOP1_D1A_D2A_D3A",
                "status": "REJECTED",
                "physical_concept_credit": "NOT_COUNTED_AS_HETEROGENEOUS_CONCEPT_IN_CONSERVATIVE_AUDIT",
                "binding_result": {
                    "field": "gripper_right",
                    "raw_mm": -5.318,
                    "gated_mm": -12.826,
                    "interpretation": "complete post-M4 high bypass was incorrectly evaluated with an unbounded alternate link3 host; physical host split was required",
                },
                "pins": {
                    "builder": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/B601_ROUTE_C_BUILD_V8.py"],
                    "fcstd": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.FCStd"],
                    "step": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step"],
                    "mesh_manifest": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/ROUTE_C_SWEEP_MESH_PACK_V8/MANIFEST.json"],
                    "rejection_record": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop1_early_rejected/V8_LOOP1_EARLY_REJECTION_V1.json"],
                },
            },
            {
                "loop": 2,
                "candidate": "V8_LOOP2_R55_HIGH_BYPASS",
                "status": "REJECTED",
                "physical_concept_credit": "R55_EXTERNAL_STANDOFF_FAMILY",
                "key_states_unsafe": loop2["summary"]["key_states_unsafe_count"],
                "worst_gated_mm": loop2["summary"]["other_key_states_worst_gated_mm"],
                "binding_result": "east/high leg intersects J5 high-bypass/return hardware",
                "pins": {
                    "builder": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/B601_ROUTE_C_BUILD_V8.py"],
                    "fcstd": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.FCStd"],
                    "step": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step"],
                    "mesh_manifest": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/ROUTE_C_SWEEP_MESH_PACK_V8/MANIFEST.json"],
                    "fastcheck": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_loop2_early_rejected/ROUTE_C_STOW_SITE_FAST_CHECK_V8.json"],
                },
            },
            {
                "loop": 3,
                "candidate": "V8_CANDIDATE3_R55_SOUTH_OUTBOARD_PRE_J3_BOUNDARY",
                "status": "REJECTED_PENDING_HOST_BOUNDARY_REMEDIATION",
                "physical_concept_credit": "SAME_R55_EXTERNAL_STANDOFF_FAMILY_AS_LOOP2_WITH_DIFFERENT_WAYPOINTS",
                "key_states_unsafe": candidate3_pre["summary"]["key_states_unsafe_count"],
                "worst_gated_mm": candidate3_pre["summary"]["other_key_states_worst_gated_mm"],
                "findings": [
                    "true J4 moving-clamp penetration already present",
                    "old J2 mandrel negative was a host-ownership false collision",
                ],
                "pins": {
                    "builder": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/B601_ROUTE_C_BUILD_V8.py"],
                    "fcstd": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.FCStd"],
                    "step": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step"],
                    "mesh_manifest": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/ROUTE_C_SWEEP_MESH_PACK_V8/MANIFEST.json"],
                    "fastcheck": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/v8_candidate3_pre_j3_host_boundary_fix/ROUTE_C_STOW_SITE_FAST_CHECK_V8.json"],
                },
            },
            {
                "loop": 4,
                "candidate": "V8_CANDIDATE3_POST_J3_PHYSICAL_HOST_BOUNDARY",
                "status": "CANDIDATE_REJECTED_WITH_MACHINE_EVIDENCE",
                "physical_concept_credit": "HOST_BOUNDARY_REMEDIATION_ONLY__NOT_A_NEW_HETEROGENEOUS_CONCEPT",
                "key_states_unsafe": current["summary"]["key_states_unsafe_count"],
                "worst_gated_mm": current["summary"]["other_key_states_worst_gated_mm"],
                "positive_changes": [
                    "J3/J2 false collision removed by physical RC-CLP-J3-HOST-BOUNDARY and section ownership split",
                    f"D2 local pinch predicate passes in the early filter with {scratch['predicates']['pinch']['worst_mm_gated']} mm gated margin",
                    f"D3 open-sector retention predicate passes with {scratch['predicates']['d3_open_sector_retention']['max_free_span_mm']} mm maximum free span against {scratch['predicates']['d3_open_sector_retention']['p13_max_spacing_mm']} mm",
                    f"minimum build bend radius remains {scratch['centerline_verification']['bend_radius_analytic_mm']} mm",
                ],
                "binding_true_penetrations": [
                    {
                        "state": release["state_id"],
                        "segment": release["detail"]["segment"],
                        "section_index": release["detail"]["section_index"],
                        "obstacle": release["detail"]["field"],
                        "raw_mm": release["clearance_mm_raw"],
                        "gated_mm": release["clearance_mm_gated"],
                        "independent_inside_depth_mm": -release["clearance_mm_raw"] - 4.5,
                        "allowlist_disposition": "FORBIDDEN_NOT_COLOCATED_WITH_THIS_CABLE_STATION",
                    },
                    {
                        "state": home["state_id"],
                        "segment": home["detail"]["segment"],
                        "section_index": home["detail"]["section_index"],
                        "obstacle": home["detail"]["field"],
                        "raw_mm": home["clearance_mm_raw"],
                        "gated_mm": home["clearance_mm_gated"],
                        "independent_inside_depth_mm": -home["clearance_mm_raw"] - 4.5,
                        "allowlist_disposition": "FORBIDDEN_REMOTE_ARC_LENGTH_CROSSING",
                    },
                ],
                "pins": {
                    "builder": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_BUILD_V8.py"],
                    "fcstd": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.FCStd"],
                    "step": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step"],
                    "build_receipt": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_BUILD_RECEIPT_V8.json"],
                    "centerline": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_HARNESS_CENTERLINE_V8.json"],
                    "hardware_register": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V8.csv"],
                    "mass_candidate": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V8.json"],
                    "mesh_manifest": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_SWEEP_MESH_PACK_V8/MANIFEST.json"],
                    "fastcheck": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_STOW_SITE_FAST_CHECK_V8.json"],
                    "evaluator": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_EXACT_SWEEP_V1.py"],
                    "scratch": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_fastcheck_scratch/sweep_scratch.json"],
                },
            },
        ],
        "full_exact_mission_sweep": {
            "executed_for_current_candidate": False,
            "reason": "lexicographic early rejection: 10/10 mandatory key states are UNSAFE and raw solid penetrations are already proven",
            "forbidden_inference": "absence of a new full-sweep file is not a PASS and cannot prove whole-architecture infeasibility",
        },
        "verdict": "V8_CANDIDATE_3_REJECTED__BOUNDED_BUILD_SWEEP_BUDGET_EXHAUSTED__ARCHITECTURE_INFEASIBILITY_NOT_PROVEN",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }

    termination = {
        "schema": "ROUTE_C_V8_LOOP_TERMINATION_RECORD_V1",
        **common,
        "candidate": "V8_CANDIDATE3_POST_J3_PHYSICAL_HOST_BOUNDARY",
        "candidate_status": "CANDIDATE_REJECTED_WITH_MACHINE_EVIDENCE",
        "mandatory_key_states": {"evaluated": 10, "unsafe": 10, "safe": 0},
        "raw_solid_penetrations_proven": True,
        "local_positive_results": {
            "D2": "LOCAL_EARLY_FILTER_PASS_ONLY",
            "D3": "LOCAL_EARLY_FILTER_PASS_ONLY",
            "J3_host_boundary": "FALSE_COLLISION_REMOVED_WITH_PHYSICAL_BOUNDARY",
        },
        "loop_budget_exhausted": True,
        "three_heterogeneous_candidate_premise_satisfied": False,
        "local_external_guided_architecture_infeasibility_proven": False,
        "architecture_escalation_gate_emitted": False,
        "architecture_escalation_gate_block_reason": "The Owner directive requires technically distinct candidate evidence before the local architecture can be declared infeasible; that premise is not met.",
        "mission_gate_emitted": False,
        "tmg2_mass_propagation_run_for_rejected_geometry": False,
        "sim13_rebind_attempted": False,
        "owner_decision_required": {
            "reason": "Additional work needs a reset/extension of the bounded loop budget and selection of a genuinely heterogeneous physical concept.",
            "recommended": "AUTHORIZE_SEGMENTED_CONSTRAINED_MOVING_CARRIER_WITH_LOW_PROFILE_TWO_PLANE_SADDLE_AS_ONE_NEW_BOUNDED_CANDIDATE",
            "alternatives": [
                "AUTHORIZE_LARGER_EXTERNAL_CARRIER_OR_STANDOFF_AS_A_NEW_ARCHITECTURE_BRANCH",
                "KEEP_ROUTE_C_AND_TMG4_ON_HOLD",
                "OWNER_ONLY_MISSION_ENVELOPE_REDUCTION",
                "OWNER_ONLY_VENDOR_HOLLOW_SHAFT_OR_SLIP_RING_INTEGRATION",
            ],
        },
        "verdict": "STOP_FAIL_CLOSED__OWNER_DECISION_REQUIRED_FOR_NEW_HETEROGENEOUS_CANDIDATE_OR_CONTINUED_HOLD",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }

    predecessor = ROOT / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_TERMINAL_CURRENT_FRONTIER_V1.json"
    frontier = {
        "schema": "ROUTE_C_TERMINAL_CURRENT_FRONTIER_V2",
        **common,
        "supersedes_frontier_only": {
            "path": predecessor.relative_to(ROOT).as_posix(),
            "sha256": sha256(predecessor),
            "note": "V1 remains immutable historical frontier; V2 is additive and does not rewrite the historical release Gate.",
        },
        "system_architecture_unchanged": {
            "planned_system": "12U service spacecraft plus deployable solar arrays plus side-mounted B601 six-axis manipulator plus end effector",
            "frozen_spacecraft_or_arm_geometry_modified_by_v8": False,
            "route_c_scope": "local B601 external cable dress-pack hardware only",
            "route_c_v8_integrated_into_system_baseline": False,
        },
        "visual_scope_control": {
            "system_assembly_native_candidate": {
                "path": "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM",
                "sha256": EXPECTED_SHA256["20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM"],
                "authority": "CURRENT_MACHINE_SELECTED_MECHANICAL_CANDIDATE__PENDING_HUMAN_REVIEW",
            },
            "system_assembly_review_step": {
                "path": "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step",
                "sha256": EXPECTED_SHA256["20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step"],
                "honest_label": "same geometry as the hash-bound deployed-nominal export; not a fresh F3R2 export",
            },
            "system_assembly_review_image": {
                "path": "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/11_screenshots/RAW/S01_DEPLOYED_NOMINAL_ISO.png",
                "sha256": EXPECTED_SHA256["20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/11_screenshots/RAW/S01_DEPLOYED_NOMINAL_ISO.png"],
            },
            "system_scenario_reference_image": {
                "path": "40_evidence/artifacts/visualization/figures/fig_v01_system_assembly_isometric.png",
                "sha256": EXPECTED_SHA256["40_evidence/artifacts/visualization/figures/fig_v01_system_assembly_isometric.png"],
                "authority": "LIMITED_FROZEN_GEOMETRY_SCENE__DYNAMICS_ADMISSIBILITY_NOT_ESTABLISHED",
            },
            "route_c_v8_review_step": {
                "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step",
                "sha256": EXPECTED_SHA256["20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V8.step"],
                "scope": "REJECTED_LOCAL_HARNESS_AND_GUIDE_SUBASSEMBLY_ONLY",
                "forbidden_labels": ["spacecraft assembly", "integrated satellite", "released B601 system"],
            },
        },
        "current_route_c_state": {
            "lineage_baseline": "V7_DESIGN_CANDIDATE__NOT_A_GATE_PASS",
            "latest_candidate": "V8_CANDIDATE3_POST_J3_PHYSICAL_HOST_BOUNDARY",
            "latest_candidate_disposition": "REJECTED",
            "mandatory_key_states_unsafe": 10,
            "binding_worst_gated_mm": current["summary"]["other_key_states_worst_gated_mm"],
            "loop_budget_exhausted": True,
            "architecture_infeasibility_proven": False,
        },
        "downstream_state": {
            "route_c_mission_gate": "NOT_EMITTED_FOR_REJECTED_V8_GEOMETRY",
            "tmg2_reopen": "NOT_EVALUATED_NO_ACCEPTED_FINAL_ROUTE_C_GEOMETRY_AND_NO_APPROVED_NUMERICAL_ACCEPTANCE_RULE",
            "sim13_system_binding": "FAIL_CLOSED_FINAL_ROUTE_C_GATE_NOT_PASS",
            "mechanical_to_embodied_handoff": "NOT_12_OF_12",
            "operational_release": "NOT_AUTHORIZED",
        },
        "required_owner_action": termination["owner_decision_required"],
        "frontier_verdict": "V8_REJECTED__LOOP_BUDGET_EXHAUSTED__NO_ARCHITECTURE_INFEASIBILITY_PROOF__OWNER_DECISION_REQUIRED__NO_RELEASE_CREDIT",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }

    outputs = []
    outputs.append(write_json(HERE / "ROUTE_C_V8_REDESIGN_HISTORY_V1.json", history))
    outputs.append(write_json(HERE / "ROUTE_C_V8_LOOP_TERMINATION_RECORD_V1.json", termination))
    outputs.append(write_json(HERE / "ROUTE_C_TERMINAL_CURRENT_FRONTIER_V2.json", frontier))
    print(json.dumps({"pins_verified": len(pins), "outputs": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
