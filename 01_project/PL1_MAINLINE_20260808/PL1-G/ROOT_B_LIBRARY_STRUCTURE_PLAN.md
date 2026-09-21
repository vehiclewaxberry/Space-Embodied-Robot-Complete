# ROOT_B_LIBRARY_STRUCTURE_PLAN.md — PL1-G (Task 2.3)

- **Date**: 2026-08-08 · **Scope**: ROOT B = `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY` (17,527 physical files = 17,523 imported artifacts + 4 root indexes; 3,745,466,618 B / 3.488238 GiB, verified after index synchronization)
- **Logical name**: `SPACE_ROBOTICS_OPEN_SOURCE_SIM_REFERENCE_LIBRARY` · **Physical name stays** `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY`
- **Core decision (ratifying PL1-D's recommendation)**: the R1–R7 structure is an **INDEX OVERLAY on the existing `REFLIB1_*` / `REFLIB2_*` physical names — ZERO physical moves/renames**. Every manifest hash path, both ingestion indexes, and ROOT A's `PROJECT_START_HERE.md` already point at the physical names; renaming would invalidate hash manifests for zero gain. If a future consolidation wants physical R-dirs, it must run as a new CM wave with full hash re-verification.

## 1. R1–R7 logical overlay (ROLE → ACTUAL PHYSICAL PATH; names unchanged)

| Logical role | Content | ACTUAL PHYSICAL PATH (do not rename) |
|---|---|---|
| **R1 PAPERS_STANDARDS** | 10 NASA NTRS PDFs, 7 ESA Clean Space Days 2026 PDFs (+`_pages/` provenance), 4 arXiv preprints (+`.meta.xml`), SPART readthedocs PDF, SpaceDyn homepage capture, 4 reading notes | `REFLIB2_01_nasa_mechanical/01_nasa_mechanical/` · `REFLIB2_02_esa_isam_2026/02_esa_isam_2026/` · `REFLIB2_03_space_dynamics/03_space_dynamics/{papers,docs}/` · `REFLIB2_07_reading_notes/07_reading_notes/` |
| **R2 OPEN_SOURCE_PROJECTS** | astrobee, isaac, int-ball2_simulator, int-ball2_isaac_sim, space-ros, space_robotics_bench, spaceros_demos | `REFLIB2_04_robotics_software/04_robotics_software/repos/{astrobee,isaac,int-ball2_simulator,int-ball2_isaac_sim,space-ros}` · `REFLIB1_space_robotics_bench/space_robotics_bench` · `REFLIB1_spaceros_demos/spaceros_demos` |
| **R3 DYNAMICS_SIMULATION_LIBRARY** | Physical ROOT B: EXUDYN, SPART, SpaceDyn (MATLAB), SpaceDyn_python, MATLAB_space_debri_capturing_sim, spacedyn_freefloating_demo (local teaching), basilisk, ANCF_beam. Registered external-to-B: Chrono (ROOT A; physical B clone absent), SpaceRobotEnv (ROOT A + identical `F:\Robotic arm` duplicate), zero-arm MuJoCo TD3 teaching case (`F:\Robotic arm\zero-robotic-arm\5. Deep_LR`) | `REFLIB1_EXUDYN/EXUDYN` · `REFLIB1_SPART/SPART` · `REFLIB1_SpaceDyn/SpaceDyn` · `REFLIB1_SpaceDyn_python/SpaceDyn_python` · `REFLIB1_MATLAB_space_debri_capturing_sim/...` · `REFLIB1_spacedyn_freefloating_demo/...` · `REFLIB2_03_space_dynamics/03_space_dynamics/repos/basilisk` · `REFLIB2_06_flexible_multibody/06_flexible_multibody/repos/ANCF_beam` · external pointers in root registers |
| **R4 CAD_DONOR_REFERENCE** | oresat_structure (CubeSat SolidWorks; mass-list logic only; license refined to CERN-OHL-S-v2). Registered EXTERNAL donors (not inside ROOT B): `F:\Robotic arm\High_performance_robotics_arm`, `F:\Robotic arm\zero-robotic-arm`; 2 optional CAE-lib small copies pending license review (CAD-D10/D11) | `REFLIB1_oresat_structure/oresat_structure` (+ external paths registered in `OPEN_SOURCE_PROJECT_REGISTER.csv`) |
| **R5 DATASETS** | speedplusbaseline CODE ONLY — SPEED+ dataset never downloaded (license/volume NOT_VERIFIED) | `REFLIB2_05_perception_datasets/05_perception_datasets/repos/speedplusbaseline` |
| **R6 TOOL_EXAMPLES** | freecad.robotcad (LGPL-2.1+; **highest-risk item — never install into the pinned authoritative FreeCAD env**), FreeCAD_Assembly4.1 (LGPL-2.1), library ingestion scripts | `REFLIB2_04_robotics_software/04_robotics_software/repos/{freecad.robotcad,FreeCAD_Assembly4.1}` · `REFLIB1__tools/_tools` · `REFLIB2_00_manifest/00_manifest/tools` |
| **R7 CAE_REFERENCE** | External affiliate, NOT inside ROOT B: `F:\Mechanical structure modeling and simulation` (642 files / 130,787,610,910 B / 121.805455 GiB; general CAE learning library; NON_SEI_GENERAL_CAE_LIBRARY; 26 index_only / 2 exclude / 2 optional copy_to_B) | external (stays in place) |
| **Governance/index layer** (spans R1–R6) | Master index, hash manifest, license register, reuse matrix, crosswalk, adversarial review, ingestion report, TOP-12/TOP-20, REFERENCE_INDEX.json, license notes; **PL1-G-installed entry doc + registers at root** | `REFLIB2_00_manifest/00_manifest/` · `REFLIB2_08_project_crosswalk/` · `REFLIB2_09_adversarial_reviews/` · `REFLIB2_*.md/` (3 wrapper dirs) · `REFLIB1__root_/` · root: `REFERENCE_LIBRARY_START_HERE.md`, `OPEN_SOURCE_PROJECT_REGISTER.csv`, `DYNAMICS_SIMULATION_LIBRARY_INDEX.csv`, `CAD_DONOR_REGISTER.csv` |

## 2. Identity & usage contract (restated, in force)

- All ROOT B repos are **.git-stripped working-tree copies**; identity = commit SHA in `REFLIB1__root_/REFERENCE_INDEX.json` and `REFLIB2_00_manifest/00_manifest/*`. No git operations inside ROOT B.
- ROOT B **never owns project authority**; no number from here enters SSOT/CAD/URDF/gate JSONs. Runtime dependency of ROOT A on ROOT B = **0** (verified by PL1-C and PL1-D independently, 2026-08-08).
- Repo-level verdicts already adjudicated (`GITHUB_REPOSITORY_REUSE_MATRIX.csv`, 19/19): zero lines of code intake recommended before 2026-09-01.
- The 3 top-level `REFLIB2_*.md` entries are **directories** wrapping one `.md` each (consolidation artifact) — documented so agents don't get confused.

## 3. Open HOLDs on the library (needs-human)

1. **License-UNKNOWN (8 items)**: SpaceDyn, space-ros, ANCF_beam, High_performance_robotics_arm, reBotArmController_ROS2, spacedyn_freefloating_demo, Pendulum-DDPG, REFLIB ingestion toolset → read methods only, copy nothing. Chrono's clean ROOT A checkout verifies BSD-3-Clause and is no longer a license HOLD.
2. **HOLD-2 (basilisk skew)**: ROOT A vendor `6b9c222f` vs ROOT B manifest-recorded `27eb48a2` — pick one reference of record.
3. **HOLD-3 (chrono inversion)**: ROOT B clone empty; only usable clone sits inside ROOT A vendor `24c78cf8` (BSD-3-Clause verified). This remains a location/index HOLD, not a license HOLD.
4. **Doc hygiene**: ROOT A `knowledge/B_assets_and_conventions.md` + `B_cubesat_structure_practice.md` cite retired `F:\space_robotics_references\...` paths (Stage 1 fix, REQUIRES HUMAN APPROVAL).
5. **Correction landed**: oresat_structure license = CERN-OHL-S v2 (`LICENSE/cern_ohl_s_v2.pdf`); the 2026-07-27 `REFERENCE_INDEX.json` entry `UNKNOWN_LICENSE` is outdated — index entry update is a Stage 1 item (REQUIRES HUMAN APPROVAL).

## 4. Entry points installed by PL1-G (2026-08-08)

- `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY\REFERENCE_LIBRARY_START_HERE.md` (from PL1-D draft, consistency-reviewed)
- `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY\OPEN_SOURCE_PROJECT_REGISTER.csv` (PL1-D, 27 data rows; all `runtime_dependency=false`)
- `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY\DYNAMICS_SIMULATION_LIBRARY_INDEX.csv` (PL1-C register, 52 data rows; includes external SpaceRobotEnv and zero-arm MuJoCo teaching pointers)
- `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY\CAD_DONOR_REGISTER.csv` (PL1-F, 15 data rows; includes F3R1/F3R2 current-state anchors)
