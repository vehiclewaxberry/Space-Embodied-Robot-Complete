# Mechanical CDR Phase-1 Audit Summary

Date: 2026-08-21 (Asia/Shanghai)  
Baseline: `V5R_NEUTRAL_OPERATIONAL_MECHANICAL_BASELINE_V1`  
Working baseline: `MECHANICAL_CDR_REQUIREMENTS_LOADS_MASS_WORKING_BASELINE_ESTABLISHED_WITH_HOLDS`

## Executive verdict

The Q0-Q2 engineering architecture and evidence chain are established, but Q0, Q1, Q2 and the combined Phase-1 Gate are all `HOLD`. No `MECHANICAL_CDR_DESIGN_RELEASED`, qualification-ready, structural qualification, mechanism qualification or flight-acceptance token is issued.

```text
DIGITAL_OPERATIONAL_BASELINE = CLOSED
MECHANICAL_DETAIL_DESIGN = ACTIVE
MECHANICAL_CDR = NOT_YET_PASSED
STRUCTURAL_QUALIFICATION = HOLD
MECHANISM_QUALIFICATION = HOLD
FLIGHT_ACCEPTANCE = HOLD
```

Formal strength/MoS, buckling, modal-response, random-vibration and shock FEA remain unauthorized. No additional Native SolidWorks top-assembly attempt was performed or authorized.

## 1. Frozen inputs

- 18 inputs are bound by byte count and SHA-256; 5 are Owner-designated immutable files.
- Final recheck: 18/18 exist, are non-zero and match; missing `0`, zero-byte `0`, hash drift `0`.
- Production `MECH_RL_INTERFACE_V1`, Sim13 bootstrap gate, accepted B601 URDF, neutral geometry, M3R geometry, V5 staging and gripper donors remain unchanged.

## 2. HOLD-to-requirement mapping

- 62 requirements and 62 VCD rows form a one-to-one map.
- The 14 Owner task states are reproduced exactly; `PANEL_FAILURE_CASES` is only a derived grouping.
- 25/25 named rapid-baseline HOLDs and 11/11 named Sim13 HOLDs are mapped.
- The traceability register contains 46 rows; invalid requirement references: `0`.
- Thirty-six requirements retain explicit input-dependent criteria and therefore do not claim numerical release.

## 3. Standards tailoring

- Fourteen sources and fourteen tailoring rows distinguish `STANDARD`, `HANDBOOK_GUIDANCE_ONLY` and `INDEPENDENT_CROSS_CHECK_ONLY`.
- ECSS is the candidate primary system; NASA-STD-5001B Change 3 is an independent cross-check only.
- Project-controlled standard copies: `0`; authorized clause mappings: `0`.
- ECSS-S-ST-00C Rev.2 (2025-11-21) and the extraction of tailoring to ECSS-S-ST-00-02 are recorded. The controlled ECSS-S-ST-00-02 text is not registered, so no ECSS compliance claim is made.
- Official references include [ECSS-E-ST-32C Rev.1](https://ecss.nl/standard/ecss-e-st-32c-rev-1-structural-general-requirements/), [ECSS-E-ST-10-02C Rev.1](https://ecss.nl/standard/ecss-e-st-10-02c-rev-1-verification-1-february-2018/), [ECSS-E-ST-10-03C Rev.1](https://ecss.nl/standard/ecss-e-st-10-03c-rev-1-testing-31-may-2022/), [ECSS-E-ST-33-01C Rev.2](https://ecss.nl/standard/ecss-e-st-33-01c-rev-2-1-march-2019-space-engineering-mechanisms/) and [NASA-STD-5001](https://standards.nasa.gov/standard/nasa/nasa-std-5001).

## 4. Load-case tree

- 19 canonical load families, 21 load cases, 13 load combinations and 9 boundary-condition records are cross-referentially closed.
- Authorized flight load cases: `0`; selected launcher/deployer ICD: none; separation ICD: none.
- The 22 kg / 0.5 deg/s and 150 kg / 3 deg/s capture anchors remain `DERIVED`, not structural-design authority.
- The eight capture anchors independently recalculate after a read-only input-path redirection, but the existing `sim_06` default mass-ledger path and solver/input hash chain are not directly reproducible. `LG-019` therefore remains a CRITICAL Q1/Q5 HOLD.
- Open load-source gaps: `19`.

## 5. M3R mass ruling

Exactly one active digital mass authority exists:

| Value | Class | Active | Scope |
|---:|---|:---:|---|
| 0.7619 kg (761.9 g) | BUDGETED | yes | Owner-frozen nominal Stage A + Stage B digital allocation only; not measured or installed |
| 0.761904197 kg | MATERIAL_DERIVED | no | legacy B-rep volume × assumed density comparison |
| 0.782327248 kg | MATERIAL_DERIVED | no | V5 comparison; native mass measurement pending |
| 1.2 kg | PROVISIONAL | no | superseded low-confidence block model |

Stage A, Stage B, fastener, locator and cable allocations are `null/HOLD`. The ruling removes double active truth but does not provide as-installed metrology.

## 6. Nine-configuration mass/inertia gap

`DEPLOYED_NOMINAL`, `LEFT_PANEL_FAIL`, `RIGHT_PANEL_FAIL`, `BOTH_PANEL_FAIL`, `ARM_STOWED_ONORBIT`, `ARM_TASK_READY`, `PREGRASP`, `POST_CAPTURE_22KG` and `POST_CAPTURE_150KG` all retain null system mass, CoM and inertia with `NOT_EVALUABLE_INPUT_AUTHORITY_MISSING`.

The accepted B601 URDF contributes a controlled digital-model mass of `4.695555949342986 kg`. Its standalone zero-joint equivalent inertia was recomputed; both actual matrices pass symmetry, positive-definiteness, principal-moment, triangle-inequality and frame checks. This result is not mapped to any of the nine named system configurations and is not a physical measurement.

## 7. Missing external authorities

The principal missing inputs are:

- selected launcher/deployer/separation system and controlled ICDs;
- authorized quasi-static, sine, random, acoustic, shock and operational load environments;
- approved load combinations, factors, uncertainty and conformity decision rules;
- controlled standards, project tailoring and numerical requirement acceptance limits;
- released materials, allowables, joint preload/contact/stiffness and tolerance inputs;
- M3R as-installed metrology and component mass/CoM/inertia;
- bus, solar-array and target mass properties and transforms;
- nine accepted B601 joint vectors and post-capture transforms;
- spacecraft assembly root to `M_FRAME` authority;
- Owner-approved mass-growth allowance and qualification-test/model philosophy.

## 8. Gate status

| Gate | Status | Pass token |
|---|---|---|
| Q0 Requirements and Tailoring | HOLD | not issued |
| Q1 Load Environment Authority | HOLD | not issued |
| Q2 Mass and Interface Authority | HOLD | not issued |
| Mechanical CDR Phase-1 | HOLD | not issued |

The machine validator passes artifact integrity; it does not convert any engineering gate to PASS.

## 9. Candidate critical parts for the later stage

Planning and input-definition work may proceed for:

`M3R_STAGE_A_RING`, `M3R_STAGE_B_LOAD_DIFFUSION_PLATE`, `B601_GRIPPER_PALM_RAIL_SLOT_R1`, `LEFT_WING_ROOT`, `RIGHT_WING_ROOT`, `HDRM_BRACKET_LEFT`, `HDRM_BRACKET_RIGHT`, `G07_SUPPORT`, `G08_SUPPORT`, `MID_SUPPORT`, `BUS_LOCAL_REINFORCEMENT`.

Native/parametric model build and formal analysis are not authorized by this Phase-1 Gate. The neutral system assembly remains the frozen digital geometry authority; no Native SolidWorks top-assembly rebuild is required or allowed here.

## 10. Structural-analysis readiness

`NOT READY / NOT AUTHORIZED`.

Only non-executing analysis planning, parameter-table preparation, material/joint/tolerance input definition, controlled-source acquisition and measurement planning are allowed. A later explicit gate must authorize formal FEA after Q0, Q1 and Q2 all issue PASS tokens and the required material/joint/model inputs are controlled.
