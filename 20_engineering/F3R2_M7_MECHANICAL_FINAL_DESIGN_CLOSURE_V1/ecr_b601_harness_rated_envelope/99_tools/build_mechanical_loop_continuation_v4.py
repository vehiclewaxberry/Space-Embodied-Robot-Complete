"""Build Mechanical Loop Engineering Continuation V4 from V3 and e20.

V4 carries one, and only one, new closed engineering state: the independent
surrogate-mass-branch sim11 coupled arm-only diagnostic execution.  The e20
mass completion is deliberately artificial and non-release.  This builder
therefore copies every V3 release-state field unchanged before adding the one
new diagnostic-only state.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ECR_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ECR_ROOT / "14_loop_continuation_v4"
GENERATED_LOCAL = "2026-08-23T23:45:00+08:00"

NEW_CLOSED_STATE = (
    "independent_surrogate_mass_branch_sim11_coupled_arm_only_"
    "diagnostic_execution_closed"
)
EXPECTED_VERDICT = (
    "MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_INDEPENDENT_SURROGATE_MASS_"
    "BRANCH_SIM11_COUPLED_ARM_ONLY_DIAGNOSTIC_EXECUTION_CLOSED__M4_SYSTEM_"
    "MASS_INERTIA_E15_PHYSICAL_MOUNT_CONTACT_ATTACHED_CAD_MISSION_PRODUCTION_"
    "AND_FLIGHT_HOLD"
)
URDF_SHA = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
SOLAR_SHA = "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"


# The three e20 hashes are replaced only after e20 has emitted its final Gate,
# validation, and manifest.  binding_records() fails closed while any pin is
# stale or incomplete.
SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "loop_v3_gate",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/13_loop_continuation_v3/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V3.json",
        "A10FF303EE2B58DBA47339C2DC4267343CC934328C526FD9011D7C7A84869D8C",
    ),
    (
        "loop_v3_validation",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/13_loop_continuation_v3/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V3.json",
        "9BA7A42B66AA57A237916E17619F5726EB18E412DD4A82D432AD3DE6C90A8F0C",
    ),
    (
        "loop_v3_manifest",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/13_loop_continuation_v3/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V3.json",
        "0985FA10922A51738CAF79433FE759A2ADD435A6D11196F852D5CDEBF9347ED2",
    ),
    (
        "e20_gate",
        "30_simulation/e20_b601_independent_mass_branch_coupled_diagnostics/"
        "results/E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_GATE_V1.json",
        "3D33FA30D058AE80310DBE5C0BA5F2402B84BF7F20CA14E9118F8EA1D33F24DA",
    ),
    (
        "e20_validation",
        "30_simulation/e20_b601_independent_mass_branch_coupled_diagnostics/"
        "results/E20_VALIDATION_V1.json",
        "7B10735922BD83DC8F69ED5C8A8C9B527707313A1CFC69A375C2575DD1A2083E",
    ),
    (
        "e20_manifest",
        "30_simulation/e20_b601_independent_mass_branch_coupled_diagnostics/"
        "results/E20_OUTPUT_MANIFEST_V1.json",
        "2EFE3C31F3CB411298A03C60CFBFD1A227F363237B7B80C44591D61F6EE3E776",
    ),
    (
        "e15_ancf_gate",
        "30_simulation/e15_ancf_certification/results/gate_summary.json",
        "AAB4D609E219279C2563C8A38743AC1784BBF16DE399D5B8798439B0AC2DCA80",
    ),
    (
        "sim11_historical_gate",
        "30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json",
        "9309F5325271BF5EFDAA7ECAC2BCF20B4FECA3FCA771D22391A7D7D576F9366F",
    ),
    (
        "m7_owner_decision_register",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml",
        "F5B1572C0CFCEC35C40F262A3D7386AFA91DEC09DA94FE31FD03F5C04956F8B6",
    ),
    (
        "m7_wp2_system_mass_properties_v2",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml",
        "151474DCD2F4EDDFC0C4417FCE7237557B5DE10BE77DB8617F5EDA3329ADF42B",
    ),
    (
        "m4_named_pose_revalidation",
        "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/"
        "11_validation/B601_NAMED_POSE_REVALIDATION_V1.json",
        "68D0356F889E5888399631E6C735D404140AC5933B7FA172AB1F9E26BA26B844",
    ),
    (
        "accepted_urdf",
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        URDF_SHA,
    ),
    (
        "solar_r2",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step",
        SOLAR_SHA,
    ),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def load_json(relative: str) -> Any:
    return json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))


def source_path(name: str) -> str:
    for source_name, relative, _ in SOURCES:
        if source_name == name:
            return relative
    raise KeyError(name)


def values_for_key(node: Any, key: str) -> list[Any]:
    values: list[Any] = []
    if isinstance(node, Mapping):
        for candidate_key, value in node.items():
            if candidate_key == key:
                values.append(value)
            values.extend(values_for_key(value, key))
    elif isinstance(node, list):
        for value in node:
            values.extend(values_for_key(value, key))
    return values


def uniform_semantic(node: Any, key: str) -> Any:
    """Return a required semantic value and reject conflicting duplicates."""

    values = values_for_key(node, key)
    if not values:
        raise RuntimeError(f"required e20 semantic missing: {key}")
    canonical = json.dumps(values[0], sort_keys=True, ensure_ascii=False)
    if any(
        json.dumps(value, sort_keys=True, ensure_ascii=False) != canonical
        for value in values[1:]
    ):
        raise RuntimeError(f"conflicting e20 semantic values: {key}")
    return copy.deepcopy(values[0])


def binding_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name, relative, expected in SOURCES:
        if not expected or expected.startswith("PENDING_"):
            raise RuntimeError(f"{name} is not hash pinned")
        path = PROJECT_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"{name} source missing: {relative}")
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"{name} hash mismatch: {actual}")
        records.append(
            {
                "name": name,
                "path": relative,
                "sha256": actual,
                "bytes": path.stat().st_size,
            }
        )
    return records


def require_e20_semantics(e20: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        NEW_CLOSED_STATE: True,
        "mass_completion_rule": "UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE",
        "bus_only_mass_and_inertia_scaled": True,
        "mount_frame_model": "M_DYNAMICS_LEGACY_NUMERICAL",
        "physical_mount_frame_applied": False,
        "physical_mount_transform": None,
        "m4_digital_prototype_installation_dynamics_claimed": False,
        "current_M7_unique_dynamics_M_consumed": False,
        "current_M7_design_dynamics_closure_claimed": False,
        "scene_A2_invoked": False,
        "contact_window_invoked": False,
        "attached_target_propagated": False,
        "selected_mass_branch": None,
        "physical_contact_ready": False,
        "mission_release_ready": False,
        "mechanical_design_released": False,
        "production_dynamics_ready": False,
        "hardware_motion_ready": False,
        "flight_qualification_ready": False,
    }
    observed = {key: uniform_semantic(e20, key) for key in expected}
    if observed != expected:
        raise RuntimeError(f"e20 scope semantic mismatch: {observed!r}")
    if e20.get("gate") != "HOLD":
        raise RuntimeError("e20 overall gate is not HOLD")
    if e20.get("next_stage_authorized") is not False:
        raise RuntimeError("e20 next stage authority changed")
    if e20.get("release_credit") is not False:
        raise RuntimeError("e20 release credit changed")
    if e20.get("testing_pass_grants_authority") is not False:
        raise RuntimeError("e20 test-authority boundary changed")
    return observed


def build_gate() -> dict[str, Any]:
    bindings = binding_records()
    v3 = load_json(source_path("loop_v3_gate"))
    v3_validation = load_json(source_path("loop_v3_validation"))
    e20 = load_json(source_path("e20_gate"))
    e20_validation = load_json(source_path("e20_validation"))
    e20_manifest = load_json(source_path("e20_manifest"))
    e15 = load_json(source_path("e15_ancf_gate"))
    sim11 = load_json(source_path("sim11_historical_gate"))

    if (
        v3["gate"] != "HOLD"
        or v3["next_stage_authorized"] is not False
        or v3["release_credit"] is not False
    ):
        raise RuntimeError("V3 HOLD semantics changed")
    if not v3_validation["verdict"].startswith("PASS_"):
        raise RuntimeError("V3 validation is not PASS")
    e20_semantics = require_e20_semantics(e20)
    if (
        e20_validation["positive_passed"] != e20_validation["positive_total"]
        or e20_validation["negative_rejected"]
        != e20_validation["negative_total"]
        or not e20_validation["verdict"].startswith("PASS_")
    ):
        raise RuntimeError("e20 independent validation is incomplete")
    if (
        e20_manifest["gate"] != "HOLD"
        or e20_manifest["next_stage_authorized"] is not False
        or e20_manifest["release_credit"] is not False
    ):
        raise RuntimeError("e20 manifest authority boundary changed")
    if e15["overall"] != "REPEAT_ANCF_CERTIFICATION":
        raise RuntimeError("e15 certification debt changed")
    if e15["cross_solver_diagnostic"]["all_lt_5pct"] is not False:
        raise RuntimeError("e15 cross-solver debt was silently cleared")
    if e15["final_candidate_cross_solver"]["available"] is not False:
        raise RuntimeError("e15 final candidate was silently created")
    if sim11["verdict"] != "SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS":
        raise RuntimeError("sim11 provisional verdict changed")
    if sim11["PROVISIONAL_PARAMS"] is not True:
        raise RuntimeError("sim11 provisional parameters were promoted")

    current_release = copy.deepcopy(v3["current_release"])
    if NEW_CLOSED_STATE in current_release:
        raise RuntimeError("V3 already contains the V4-only state")
    current_release[NEW_CLOSED_STATE] = True

    prior_false_keys = sorted(
        key for key, value in v3["current_release"].items() if value is False
    )
    facts = [
        {
            "id": "LC4-01",
            "name": "V3_CONTINUATION_IS_HASH_BOUND_AND_REMAINS_HOLD",
            "observed": True,
            "evidence": {
                "verdict": v3["verdict"],
                "gate": v3["gate"],
                "next_stage_authorized": v3["next_stage_authorized"],
                "release_credit": v3["release_credit"],
            },
        },
        {
            "id": "LC4-02",
            "name": "E20_INDEPENDENT_SURROGATE_BRANCH_DIAGNOSTIC_EXECUTION_CLOSED",
            "observed": True,
            "evidence": {
                "e20_verdict": e20["verdict"],
                NEW_CLOSED_STATE: e20_semantics[NEW_CLOSED_STATE],
                "gate": e20["gate"],
                "next_stage_authorized": e20["next_stage_authorized"],
                "release_credit": e20["release_credit"],
            },
        },
        {
            "id": "LC4-03",
            "name": "E20_INDEPENDENT_FAIL_CLOSED_VALIDATION_COMPLETE",
            "observed": True,
            "evidence": {
                "verdict": e20_validation["verdict"],
                "checks": (
                    f"{e20_validation['positive_passed']}/"
                    f"{e20_validation['positive_total']}"
                ),
                "negative_controls": (
                    f"{e20_validation['negative_rejected']}/"
                    f"{e20_validation['negative_total']}"
                ),
            },
        },
        {
            "id": "LC4-04",
            "name": "BUS_ONLY_SCALAR_MASS_COMPLETION_IS_AN_ARTIFICIAL_SURROGATE",
            "observed": True,
            "evidence": {
                "mass_completion_rule": e20_semantics["mass_completion_rule"],
                "bus_only_mass_and_inertia_scaled": e20_semantics[
                    "bus_only_mass_and_inertia_scaled"
                ],
                "released_system_mass_cg_inertia_authority": False,
                "branch_selection_or_averaging_credit": False,
            },
        },
        {
            "id": "LC4-05",
            "name": "M_DYNAMICS_IS_ODR01_DYNAMICS_CONVENTION_WITHOUT_PHYSICAL_ENTITY",
            "observed": True,
            "evidence": {
                "mount_frame_model": e20_semantics["mount_frame_model"],
                "m7_odr01_dynamics_T_SM_translation_mm": [185.25, 0.0, 0.0],
                "m7_odr01_dynamics_T_SM_rotation": "Ry(+90deg)",
                "numerically_matches_odr01_dynamics_convention": True,
                "current_M7_unique_dynamics_M_consumed": e20_semantics[
                    "current_M7_unique_dynamics_M_consumed"
                ],
                "current_M7_design_dynamics_closure_claimed": e20_semantics[
                    "current_M7_design_dynamics_closure_claimed"
                ],
                "cad_geometry_mount_context_x_mm": 208.0,
                "cad_geometry_mount_context_clock_deg": 25.000014,
                "dynamics_and_cad_geometry_contexts_separate": True,
                "physical_mount_frame_applied": e20_semantics[
                    "physical_mount_frame_applied"
                ],
                "physical_mount_transform": e20_semantics[
                    "physical_mount_transform"
                ],
                "m4_digital_prototype_installation_dynamics_claimed": (
                    e20_semantics[
                        "m4_digital_prototype_installation_dynamics_claimed"
                    ]
                ),
                "m7_frame_to_mass_reconciliation_state": (
                    "M7_FRAME_TO_MASS_RECONCILIATION_NOT_EVALUATED_IN_E20"
                ),
            },
        },
        {
            "id": "LC4-06",
            "name": "E20_REMAINS_ARM_ONLY_WITHOUT_CONTACT_OR_ATTACHED_TARGET",
            "observed": True,
            "evidence": {
                "scene_A2_invoked": e20_semantics[
                    "scene_A2_invoked"
                ],
                "contact_window_invoked": e20_semantics["contact_window_invoked"],
                "attached_target_propagated": e20_semantics[
                    "attached_target_propagated"
                ],
                "physical_contact_ready": e20_semantics["physical_contact_ready"],
            },
        },
        {
            "id": "LC4-07",
            "name": "E15_ANCF_CERTIFICATION_DEBT_REMAINS_REPEAT",
            "observed": True,
            "evidence": {
                "overall": e15["overall"],
                "max_relative_difference": e15["cross_solver_diagnostic"][
                    "max_relative_difference"
                ],
                "gate_limit": e15["final_candidate_cross_solver"]["gate_limit"],
                "final_candidate_available": e15[
                    "final_candidate_cross_solver"
                ]["available"],
            },
        },
        {
            "id": "LC4-08",
            "name": "SIM11_PANEL_AND_CONTACT_PARAMETERS_REMAIN_PROVISIONAL",
            "observed": True,
            "evidence": {
                "verdict": sim11["verdict"],
                "PROVISIONAL_PARAMS": sim11["PROVISIONAL_PARAMS"],
                "e15_repeat_not_cleared_by_local_solver_checks": True,
            },
        },
        {
            "id": "LC4-09",
            "name": "V3_STATE_TRANSITION_HAS_EXACTLY_ONE_NEW_TRUE_FIELD",
            "observed": True,
            "evidence": {
                "existing_current_release_key_count": len(v3["current_release"]),
                "existing_fields_changed": [],
                "new_true_fields": [NEW_CLOSED_STATE],
                "prior_false_fields_preserved": prior_false_keys,
            },
        },
        {
            "id": "LC4-10",
            "name": "IMMUTABLE_ASSETS_UNCHANGED_AND_NO_NEW_GEOMETRY",
            "observed": True,
            "evidence": {
                "accepted_urdf_sha256": URDF_SHA,
                "solar_r2_sha256": SOLAR_SHA,
                "new_geometry_count": 0,
            },
        },
    ]

    return {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4",
        "generated_local": GENERATED_LOCAL,
        "authority_scope": (
            "HASH_BOUND_INDEPENDENT_SURROGATE_MASS_BRANCH_SIM11_COUPLED_"
            "ARM_ONLY_DIAGNOSTIC_EXECUTION_CONTINUATION__NON_M4_INSTALLATION_"
            "PRE_CONTACT_PRE_ATTACHED_PRE_CAD_PRE_MISSION_PRE_PRODUCTION"
        ),
        "decision_rule": "Authority > later evidence > independent reproduction > opinion",
        "fail_closed_invariants": [
            "the only V3-to-V4 closed state is the explicitly named independent surrogate diagnostic execution",
            "V3 false null and HOLD states remain unchanged",
            "the bus-only uniform-density scalar completion is an artificial surrogate and not released system mass CG or inertia",
            "M_DYNAMICS has the ODR-01 dynamics-convention role but no physical-entity semantics and is not equivalent to the separate CAD geometry mount context",
            "M7 ODR-01 nevertheless retains T_SM 185.25 mm plus Ry90 as the current dynamics convention while the 208 mm plus 25 degree value is a separate CAD geometry mount context",
            "e20 does not evaluate which transform WP2 V2 used for each S-frame arm mass-property placement and creates no M7 current-design mass-dynamics upgrade",
            "the physical B601 mount transform remains null and was not applied",
            "e20 arm-only lanes contain no contact window target attachment lock or recovery",
            "the two mass branches remain separate model sensitivities and are not uncertainty samples",
            "e15 remains REPEAT_ANCF_CERTIFICATION and sim11 panel/contact parameters remain provisional",
            "test PASS is not mechanical CAD mission production hardware or flight release",
            "accepted URDF and Solar R2 remain immutable",
        ],
        "input_bindings": bindings,
        "facts": facts,
        "facts_total": len(facts),
        "facts_confirmed": sum(fact["observed"] for fact in facts),
        "state_transition": {
            "from_schema": v3["schema"],
            "prior_gate": v3["gate"],
            "existing_current_release_fields_preserved_exactly": True,
            "existing_current_release_fields_changed": [],
            "only_new_closed_state": NEW_CLOSED_STATE,
            "only_new_closed_state_value": True,
            "additional_authority_created": False,
        },
        "current_release": current_release,
        "bounded_diagnostic_lane": {
            "state": (
                "HASH_BOUND_INDEPENDENT_SURROGATE_MASS_BRANCH_SIM11_COUPLED_"
                "ARM_ONLY_DIAGNOSTIC_EXECUTION_CLOSED"
            ),
            "allowed": [
                "reproduce each e20 mass branch and trajectory lane independently",
                "use branch-local coupled observations only as surrogate model sensitivity",
                "retain exact hashes and rerun after any input solver or adapter change",
                "use the result to prioritize physical mass mount panel and ANCF evidence closure",
            ],
            "not_allowed": [
                "select merge average or uncertainty-combine the two mass branches",
                "claim an M4 system mass center of mass inertia or installation dynamics result",
                "treat M_DYNAMICS as the physical B601 mount",
                "attach a target invoke contact lock or form a mission sequence",
                "authorize CAD production dynamics hardware motion manufacturing or flight",
            ],
        },
        "surrogate_model_boundary": {
            "mass_completion_rule": e20_semantics["mass_completion_rule"],
            "bus_only_mass_and_inertia_scaled": e20_semantics[
                "bus_only_mass_and_inertia_scaled"
            ],
            "mass_completion_is_artificial_scalar_surrogate": True,
            "released_system_mass_cg_inertia_authority": False,
            "mount_frame_model": e20_semantics["mount_frame_model"],
            "physical_mount_frame_applied": e20_semantics[
                "physical_mount_frame_applied"
            ],
            "physical_mount_transform": e20_semantics["physical_mount_transform"],
            "m4_digital_prototype_installation_dynamics_claimed": e20_semantics[
                "m4_digital_prototype_installation_dynamics_claimed"
            ],
            "m7_current_design_mass_dynamics_claimed": False,
            "e20_current_M7_unique_dynamics_M_consumed": e20_semantics[
                "current_M7_unique_dynamics_M_consumed"
            ],
            "e20_current_M7_design_dynamics_closure_claimed": e20_semantics[
                "current_M7_design_dynamics_closure_claimed"
            ],
            "acceptance_threshold_authority": None,
            "mechanical_design_release_credit": False,
        },
        "upstream_consistency_hold": {
            "state": "M7_FRAME_TO_MASS_RECONCILIATION_NOT_EVALUATED_IN_E20",
            "m7_odr01_dynamics_T_SM_translation_mm": [185.25, 0.0, 0.0],
            "m7_odr01_dynamics_T_SM_rotation": "Ry(+90deg)",
            "m_dynamics_physical_entity": False,
            "cad_geometry_mount_context_x_mm": 208.0,
            "cad_geometry_mount_context_clock_deg": 25.000014,
            "contexts_are_separate": True,
            "open_question": (
                "which controlled transform each WP2 V2 configuration used for "
                "S-frame B601 COM and inertia placement"
            ),
            "independent_configuration_recomputation_completed_in_e20": False,
            "reconciliation_closed": False,
            "m7_current_design_mass_dynamics_upgrade": False,
            "required_next_evidence": "E21_FRAME_TO_MASS_RECONCILIATION",
            "source_binding_names": [
                "m7_owner_decision_register",
                "m7_wp2_system_mass_properties_v2",
                "m4_named_pose_revalidation",
            ],
        },
        "preserved_holds": {
            "e15_ancf_certification": e15["overall"],
            "sim11_panel_and_contact_parameters_provisional": sim11[
                "PROVISIONAL_PARAMS"
            ],
            "physical_contact_ready": False,
            "attached_target_recovery_ready": False,
            "released_combined_mass_properties_ready": False,
            "cad_generation_authorized": False,
            "mission_trajectory_release_ready": False,
            "production_dynamics_ready": False,
            "hardware_motion_ready": False,
            "flight_qualification_ready": False,
            "m7_frame_to_mass_reconciliation": (
                "M7_FRAME_TO_MASS_RECONCILIATION_NOT_EVALUATED_IN_E20"
            ),
        },
        "blocking_fronts": copy.deepcopy(v3["blocking_fronts"]),
        "shortest_engineering_sequence": [
            "replace the artificial scalar completion with a formally selected full-system mass CG inertia branch and uncertainty record",
            "execute e21 to reconcile ODR-01 T_SM dynamics convention, the separate CAD geometry mount context, and every WP2 V2 S-frame arm COM-inertia placement before any M7 current-design mass-dynamics claim",
            "replace provisional panel mass modes EI damping and contact-window inputs with controlled evidence and repeat e15 certification",
            "Owner disposes ODR-42 and closes MPI-01 through MPI-08 before Route-C CAD",
            "close actuator contact lock target state attached recovery and mission guards independently before any end-to-end claim",
            "issue separate production binding only after full-path mechanical gates close",
        ],
        "verdict": EXPECTED_VERDICT,
        "gate": "HOLD",
        "testing_pass_grants_authority": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "required_owner_statement": v3["required_owner_statement"],
        "prohibition": (
            "No M4 system mass-CG-inertia or installation-dynamics claim, no M7 "
            "current-design mass-dynamics or frame-to-mass reconciliation claim, "
            "physical contact, attached-target recovery, Route-C CAD, mission, "
            "production binding, hardware motion, manufacturing release, or "
            "flight claim from V4."
        ),
    }


def build_brief(gate: Mapping[str, Any]) -> str:
    fact_by_id = {fact["id"]: fact for fact in gate["facts"]}
    e20_validation = fact_by_id["LC4-03"]["evidence"]
    e15 = fact_by_id["LC4-07"]["evidence"]
    return f"""# 机械 Loop Engineering 续接裁决 V4

## 唯一合法增量

- e20 已完成两个人工标量质量分支、两条 arm-only 轨迹的四条互不串接 sim11 耦合诊断；独立验证为 `{e20_validation['checks']}`，负控为 `{e20_validation['negative_controls']}`。
- 本轮唯一新增闭合状态是 `{NEW_CLOSED_STATE}=true`。V3 已有 `current_release` 字段逐项原值保留；总体 Gate、next-stage 与 release-credit 仍为 `HOLD/false/false`。
- 该闭合只说明哈希绑定的数值诊断可复现，不授予任何机械、任务、生产、硬件或飞行权限。

机器裁决：`{gate['verdict']}`

## 模型边界

- 质量补全规则为 `UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE`：只调整 sim11 bus 的质量和惯量，保持其既有几何与质心；这是人工标量敏感性模型，不是 M4 全系统质量、质心或惯量。
- e20 数值安装系为 `M_DYNAMICS_LEGACY_NUMERICAL`，数值上与 M7 ODR-01 的当前 dynamics convention `T_SM=[185.25,0,0] mm + Ry(90 deg)` 相同；但 e20 明确没有消费 current-M7 unique dynamics M，也没有形成 current-M7 design dynamics closure。该 M frame 本身没有物理实体。`208 mm + 25.000014 deg` 是与 dynamics M 分离的 CAD/几何 mount context，不能互相替代。
- e20 未检查 WP2 V2 各配置在 S 系汇总 B601 COM/惯量时实际采用哪套受控变换；因此 `M7_FRAME_TO_MASS_RECONCILIATION_NOT_EVALUATED_IN_E20`，不能据此升级 M7/current-design mass dynamics。
- 两个质量分支没有被选择、合并、平均或解释为测量不确定度。e20 未执行 contact window、目标附着、锁定、恢复或任务段。

## 仍未放行

- e15 仍为 `{e15['overall']}`：交叉求解最大相对差 `{e15['max_relative_difference']:.6%}` 高于 `{e15['gate_limit']:.2%}`，最终候选仍不存在。
- sim11 的板质量、模态、EI、阻尼与接触窗仍为 provisional；局部 Radau/BDF 数值一致性不能清除 e15 债务。
- `physical_contact_ready=false`、`attached_target_recovery_ready=false`、`cad_generation_authorized=false`、`mission_trajectory_release_ready=false`、`production_dynamics_ready=false`、`hardware_motion_ready=false`、`flight_qualification_ready=false`。

## 下一闭环

先由 e21 对拍 ODR-01 dynamics convention、独立 CAD/几何 mount context 与 WP2 V2 每个配置的 S 系 B601 COM/惯量放置，再形成正式选定、含不确定度的全系统质量属性分支；随后用受控板参数独立复算并重过 e15。ODR-42、MPI、接触/锁定、附着恢复和任务合同仍按既有顺序分别闭合。
"""


def script_records() -> list[dict[str, Any]]:
    scripts = [
        Path(__file__).resolve(),
        Path(__file__).resolve().with_name(
            "validate_mechanical_loop_continuation_v4.py"
        ),
    ]
    records = []
    for path in scripts:
        if not path.is_file():
            raise RuntimeError(f"required V4 script missing: {path}")
        records.append(
            {
                "name": path.stem,
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return records


def artifact_bytes() -> dict[Path, bytes]:
    gate = build_gate()
    gate_data = json_bytes(gate)
    brief_data = build_brief(gate).encode("utf-8")
    gate_path = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4.json"
    brief_path = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V4.md"
    manifest_path = (
        OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V4.json"
    )
    output_records = []
    for path, data in ((gate_path, gate_data), (brief_path, brief_data)):
        output_records.append(
            {
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256_bytes(data),
                "bytes": len(data),
            }
        )
    sources = binding_records() + script_records()
    manifest = {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V4",
        "generated_local": GENERATED_LOCAL,
        "outputs": output_records,
        "sources": sources,
        "output_count": len(output_records),
        "source_count": len(sources),
        "validation_report_excluded_to_avoid_self_hash": True,
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    return {
        gate_path: gate_data,
        brief_path: brief_data,
        manifest_path: json_bytes(manifest),
    }


def write_outputs() -> None:
    artifacts = artifact_bytes()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for path, data in artifacts.items():
        path.write_bytes(data)


def check_outputs() -> tuple[bool, list[str]]:
    mismatches = []
    for path, expected in artifact_bytes().items():
        if not path.is_file():
            mismatches.append(f"missing:{path.relative_to(PROJECT_ROOT).as_posix()}")
        elif path.read_bytes() != expected:
            mismatches.append(f"drift:{path.relative_to(PROJECT_ROOT).as_posix()}")
    return not mismatches, mismatches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.check_only:
        passed, mismatches = check_outputs()
        print(
            json.dumps(
                {"exact_reproduction": passed, "mismatches": mismatches},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if passed else 1
    write_outputs()
    gate = json.loads(
        (
            OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4.json"
        ).read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "verdict": gate["verdict"],
                "facts": f"{gate['facts_confirmed']}/{gate['facts_total']}",
                "gate": gate["gate"],
                "release_credit": gate["release_credit"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
