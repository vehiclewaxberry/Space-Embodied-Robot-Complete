# M4-L01/L02 configuration geometry execution matrix V1

## Engineering ruling

This append-only package closes a **source-only configuration-to-geometry execution contract**. It does not create a new CAD result and does not alter any parent Gate.

- Configuration-current STEP buildable now: **0/9** (`C01`–`C09`).
- Current complete integrated geometry: **0/9**.
- Deterministic non-current diagnostic recipe: **1**, `D01_R2_SOLAR_B601_FIXED_Q0_DIAGNOSTIC`.
- CAD kernel loaded in this package run: **false**.
- STEP generated in this package run: **false**.
- Fresh CAD run, configuration, collision, contact, mass, production, operational and release authority: **all false**.

The package therefore advances the digital mock-up by freezing the exact next executable recipe and every known blocker, without calling fixed `q0` geometry the current `C01` configuration.

## C01–C09 execution matrix

| ID | Authoritative arm state | Can generate current STEP now? | Principal missing authority |
|---|---|---:|---|
| C01 | `q_home=[-1.570796,-2.094395,-1.047198,0,-0.523599,0] rad` | No | Articulatable per-link B601 physical B-rep at `q_home`; configured STEP and snapshot review. The available complete arm is fixed `q0`, so `STATIC_CAD_Q0_CANNOT_STAND_IN_FOR_C01_QHOME`. |
| C02 | `q_home` | No | Left attached-stuck Solar R2 transform/geometry plus articulatable B601 at `q_home`. |
| C03 | `q_home` | No | Right attached-stuck Solar R2 transform/geometry plus articulatable B601 at `q_home`. |
| C04 | `q_home` | No | Both attached-stuck Solar R2 transforms/geometries plus articulatable B601 at `q_home`. |
| C05 | null | No | Ratified stow `q6`; disposition of the 567.734 mm end-effector mismatch; support contact; Solar state. |
| C06 | null | No | Owner-ratified task-ready `q6`; Solar state. |
| C07 | null | No | Ratified pregrasp `q6`; gripper joint state; Solar state. |
| C08 | null | No | Ratified capture `q6`; gripper state; `T_S_TARGET_22KG`; contact interface; controlled target geometry; Solar state. |
| C09 | null | No | Ratified capture `q6`; gripper state; `T_S_TARGET_150KG`; contact interface; controlled debris shell geometry; E15 disposition; Solar state. |

The candidate vectors recorded for `C05`–`C09` remain explicitly non-authoritative. Target attachment transforms, arm HDRM placement, Solar HDRM hardware placement and gripper joint states remain null.

## Deterministic D01 recipe

`D01` is a diagnostic fixed-snapshot branch, not `C01` and not configuration credit.

| Item | Frozen contract |
|---|---|
| Root / length unit | spacecraft frame `S` / mm |
| Retained master leaves | indices `1–6, 27, 28, 41` = 9 solids |
| Solar R2 leaves | deployed indices `7–12` = 6 solids; indices `19–22` remain HDRM keepouts, not hardware |
| B601 | complete B50 monolithic fixed-`q0` STEP = 388 shapes by its pinned CAD inspection receipt |
| Placement | `T_S_B601_ARM_BASE = Ry(+90 deg) * Rz(+25.000014 deg)`, translation `[208,0,0] mm` |
| Expected assembly | 403 leaf solids in 3 intermediate groups |
| Expected bbox in `S` | min `[-230.25,-715.4,-274.86072587989787] mm`; max `[488.533214,715.4,285.63229786565915] mm`; tolerance 0.1 mm |
| Datum | installed B601 min-x = M3R outer face x = 210.405 mm; tolerance 0.01 mm |

The master selection deliberately removes legacy Solar R1 leaves, axis/frame witness solids and the detached palm, while retaining the bus/core, the already-installed two-solid M3R, and the load bridge. The Solar R2 source is authored in `S` and uses identity placement. The B601 placement is frozen in `FRAME_PLACEMENT_LEDGER_V1.yaml`; no transform is inferred from visual alignment.

## Pinned sources and limits

`SOURCE_AUTHORITY_LOCK_V1.json` binds 37 source files by path, byte count and SHA-256. The principal geometry sources are:

- `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/04_MASTER_GEOMETRY.step`
- `20_engineering/cad/B5_0_B601_space_manipulator_candidate/03_CAD/native_runs/B50_NATIVE_20260727T2214Z/30_exports/B50_B601_ENGINEERING_ARM_Q0.step`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step`
- `20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_WORKING.step`
- `20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/01_native_cad/gripper_r1/B601_GRIPPER_PALM_RAIL_SLOT_R1.step`
- `20_engineering/config/geometry/target_models_v1.yaml`
- `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/m4_l02_configuration_state_contract_v1/R2_CONFIGURATION_STATE_VECTOR_CONTRACT_V1.yaml`

The B601 file is a monolithic visual/assembly reference: it retains no movable degrees of freedom and grants no contact or manufacturing authority. Solar R2 is an engineering candidate; its HDRM architecture is unselected. M3R is a working detailed design under existing fit-up/release holds. The gripper R1 palm has no arbitrary configured full B-rep/placement authority and is not duplicated into D01 because the B50 fixed snapshot already contains its legacy visual gripper. Target assets remain low-confidence proxies in independent frames `T` and `D`; they are excluded from D01.

## STEP-first execution and visual review

`source_only_step_generator_v1.py` has no top-level CAD imports. A future fresh runner must first pass all pinned-source checks and present a fresh run ID plus either at least 6 GiB available memory or a run-bound Owner Override with the required risk acknowledgement. Only then can it import OCP/build123d and call `gen_step()`.

No memory measurement, Owner Override, CAD import or STEP write was attempted here. Consequently the four planned snapshots (isometric, opposite isometric, top and front) are registered but intentionally unexecuted. After a separately authorized STEP run, those views must verify three-leaf Solar deployment on both sides, complete arm installation, M3R/arm datum, arm clocking, absence of duplicated components and absence of legacy witnesses.

## Reproduction

Run from this directory with the workspace Python:

```powershell
python -B build_execution_matrix.py
python -B run_negative_controls.py
python -B build_execution_matrix.py
python -B validate_execution_matrix.py
python -B -m pytest -q -p no:cacheprovider tests/test_execution_matrix.py
```

The first build may be a 29/30 HOLD if the negative-control receipt does not yet exist. The final build consumes the 36/36 receipt and must reach 30/30 while retaining every authority boundary as false. The self-excluded manifest controls every local file except itself and rejects extra files.

## Claim boundary

Passing this package Gate means only that the source audit, configuration matrix, state/geometry crosswalk, D01 source-only recipe, placement/count/bbox contract, execution preflight, negative controls and manifest are internally consistent. It does **not** mean a current C01–C09 STEP exists, D01 has been executed, the memory gate passed, target/HDRM/contact geometry is resolved, or any collision, mass, production, operational, next-stage or release authority was granted.
