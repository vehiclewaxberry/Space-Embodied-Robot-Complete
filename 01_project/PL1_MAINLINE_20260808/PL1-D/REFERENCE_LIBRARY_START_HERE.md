# REFERENCE LIBRARY — START HERE

**Library**: `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY` · logical name `SPACE_ROBOTICS_OPEN_SOURCE_SIM_REFERENCE_LIBRARY` (ROOT B)
**Size**: 17,527 files (17,523 imported artifacts + 4 PL1 root indexes, verified 2026-08-08) · **Status**: reference-only, read-only
**Drafted by**: PL1-D recon, 2026-08-08 · **Installed as the library entry doc by PL1-G consolidation, 2026-08-08** (SSOT registers installed alongside: `OPEN_SOURCE_PROJECT_REGISTER.csv`, `DYNAMICS_SIMULATION_LIBRARY_INDEX.csv`, `CAD_DONOR_REGISTER.csv` — all at this root)

---

## 1. What this library is

The single, only reference library of the SEI / B601 6R space-manipulator project (ROOT A = `F:\China Graduate Future Flight Vehicle Innovation Competition`). It merged two retired roots:

- `REFLIB1_*` ← former `F:\space_robotics_references` (8 cloned upstream repos, indexed 2026-07-27 in `REFLIB1__root_/REFERENCE_INDEX.json`)
- `REFLIB2_*` ← former `F:\SPACE_ROBOTICS_PUBLIC_REFERENCE_20260805` (23 NASA/ESA/arXiv documents + 10 repo clones, ingested 2026-08-05, manifests in `REFLIB2_00_manifest/`)

It contains **papers & standards, open-source projects, dynamics/simulation codes, and CAD donor references** — nothing here is project engineering truth. The project's authorities (accepted URDF, geometry SSOT, gate JSONs, CM rulings) live in ROOT A and `F:\SEI_PROJECT_ARCHIVE`, never here.

## 2. Logical map R1–R7 (physical names stay stable)

| Role | What | Where (physical) |
|---|---|---|
| R1 PAPERS_STANDARDS | 10 NASA NTRS, 7 ESA CSD-2026, 4 arXiv, tool docs, reading notes | `REFLIB2_01_*`, `REFLIB2_02_*`, `REFLIB2_03_*/.../{papers,docs}`, `REFLIB2_07_*` |
| R2 OPEN_SOURCE_PROJECTS | astrobee, isaac, int-ball2 ×2, space-ros, space_robotics_bench, spaceros_demos | `REFLIB2_04_*/.../repos/`, `REFLIB1_space_robotics_bench`, `REFLIB1_spaceros_demos` |
| R3 DYNAMICS_SIMULATION_LIBRARY | Physical: EXUDYN, SPART, SpaceDyn (+python), debris-capture sim, spacedyn demo, basilisk, ANCF_beam. Registered external-to-B: Chrono; SpaceRobotEnv; zero-arm MuJoCo TD3 teaching case | `REFLIB1_{EXUDYN,SPART,SpaceDyn,SpaceDyn_python,MATLAB_*,spacedyn_*}`, `REFLIB2_03_*/repos/basilisk`, `REFLIB2_06_*/repos/ANCF_beam`; external pointers: ROOT A `80_third_party/{vendor/chrono,external/.../SpaceRobotEnv}` and `F:\Robotic arm\zero-robotic-arm\5. Deep_LR` |
| R4 CAD_DONOR_REFERENCE | oresat_structure (mass-list logic only) | `REFLIB1_oresat_structure` |
| R5 DATASETS | speedplusbaseline code (dataset NOT downloaded) | `REFLIB2_05_*` |
| R6 TOOL_EXAMPLES | freecad.robotcad, FreeCAD_Assembly4.1, ingestion scripts | `REFLIB2_04_*/repos/{freecad.robotcad,FreeCAD_Assembly4.1}`, `REFLIB1__tools`, `REFLIB2_00_manifest/tools` |
| R7 CAE_REFERENCE | external affiliate: `F:\Mechanical structure modeling and simulation` (not inside ROOT B) | external |
| Governance | master index, hash manifest, license register, reuse matrix, crosswalk, adversarial review, TOP-12/20 | `REFLIB2_00_manifest`, `REFLIB2_08_*`, `REFLIB2_09_*`, `REFLIB2_*.md/`, `REFLIB1__root_` |

Full per-project register (upstream URL, commit, license, verdict): `OPEN_SOURCE_PROJECT_REGISTER.csv` (**this library root**; dynamics-focused view: `DYNAMICS_SIMULATION_LIBRARY_INDEX.csv`; CAD donors: `CAD_DONOR_REGISTER.csv`). Identity of every repo = the commit SHA recorded in the two index files; **ROOT B copies have no `.git`** — do not try to run git inside them.

## 3. How a project agent MAY use this library (reference-only)

- Read any code, PDF, or doc; cite methods and designs in the paper with the citation forms already prepared in `REFLIB2_08_project_crosswalk/.../EXTERNAL_SOURCE_TO_PROJECT_GATE_MATRIX.csv`.
- Use PDFs for narrative, trade-space, test-method, and lessons-learned material per `TOP_20_ACTIONABLE_REFERENCES` tiering.
- Run nothing into the project: sandbox execution (if ever authorized) must be fully isolated, and its output enters project evidence only through a new independent gate — it never inherits a PASS.
- Follow the per-repo verdicts in `GITHUB_REPOSITORY_REUSE_MATRIX.csv` (19/19 adjudicated; before 2026-09-01 the recommended code intake is **zero lines**).

## 4. How a project agent MAY NOT use it (runtime dependency ban)

- **No runtime dependency**: ROOT A code, configs, URDF, gates, or scripts must never read, import, `addpath`, or load anything under ROOT B. (Verified 2026-08-08: zero such references exist — keep it that way. The one allowed vendor pattern is ROOT A's *own* gitignored `80_third_party/vendor/`, e.g. the reBot-DevArm STEP referenced by `arm_b601_v1.yaml`.)
- **No authority**: no dimension, load, stiffness, modal, mass, or performance number from here may enter SSOT, CAD, URDF, or any `*_gate_check.json`.
- **No file copying into deliverables** without an explicit license verdict. License-HOLD items (8; no/unknown license → read methods only, copy nothing): SpaceDyn, space-ros, ANCF_beam, High_performance_robotics_arm, reBotArmController_ROS2, spacedyn_freefloating_demo, Pendulum-DDPG, REFLIB ingestion toolset. Chrono's ROOT A checkout verifies BSD-3-Clause and is not in this license-HOLD list.
- **Never install** `freecad.robotcad` or `FreeCAD_Assembly4.1` into the pinned authoritative FreeCAD environment; never round-trip URDF through external tools (accepted inertial is hash-protected).
- LGPL (SPART, both FreeCAD workbenches) and GPL (zero-robotic-arm) sources may be run/read as independent tools but their code never enters project source.

## 5. Reading order for a new agent

1. This file → 2. `OPEN_SOURCE_PROJECT_REGISTER.csv` (what exists, license, verdict) → 3. `REFLIB2_PUBLIC_REFERENCE_INGESTION_REPORT.md/` + `REFLIB2_TOP_12_GITHUB_PROJECTS.md/` + `REFLIB2_TOP_20_ACTIONABLE_REFERENCES.md/` (why) → 4. per-repo `SUMMARY.md` → 5. the worktree itself.

## 6. Known open items (tracked in `01_project\PL1_MAINLINE_20260808\PL1-G\NEW_CONTRADICTION_REGISTER.md`, ROOT A)

- **HOLD-1**: license-UNKNOWN projects listed in §4 (legal boundary: all-rights-reserved).
- **HOLD-2**: basilisk exists twice at different commits (ROOT A vendor `6b9c222f` vs ROOT B recorded `27eb48a2`) — pick one reference of record.
- **HOLD-3**: chrono clone in ROOT B failed (empty); the only usable clone sits inside ROOT A vendor (`24c78cf8`, BSD-3-Clause verified) — location/inverted-duplication HOLD, not a license HOLD.
- **Doc hygiene (minor)**: ROOT A `knowledge/B_assets_and_conventions.md` and `B_cubesat_structure_practice.md` still cite retired paths (`F:\space_robotics_references\...`); update to REFLIB paths. Not a runtime issue.
- **Refinement**: oresat_structure license = CERN-OHL-S-v2 (`LICENSE/cern_ohl_s_v2.pdf`); the 2026-07-27 index entry `UNKNOWN_LICENSE` is outdated.
