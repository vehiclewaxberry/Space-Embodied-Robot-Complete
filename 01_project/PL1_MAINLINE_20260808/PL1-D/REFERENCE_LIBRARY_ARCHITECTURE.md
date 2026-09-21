# REFERENCE_LIBRARY_ARCHITECTURE.md

**Agent**: PL1-D (SEI-PL1-PROJECT-MAINLINE-RECONSTRUCTION) · **Date**: 2026-08-08
**Scope**: `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY` (ROOT B, 17,527 physical files = 17,523 imported artifacts + 4 installed root indexes, verified 2026-08-08)
**Nature**: The reconstruction inventory was read-only; PL1-G subsequently installed four root entry/index files. No imported artifact was moved, renamed, or modified. The R1–R7 architecture remains an INDEX overlay; physical `REFLIB1_*` / `REFLIB2_*` names stay stable.

---

## 1. What ROOT B physically is

ROOT B is the merge of two former roots (both now retired, verified absent on disk):

| Former root | Now at | Content |
|---|---|---|
| `F:\space_robotics_references` (15 GB corpus, indexed 2026-07-27) | `REFLIB1_*` | 8 cloned upstream repos + local demo + license notes + tools |
| `F:\SPACE_ROBOTICS_PUBLIC_REFERENCE_20260805` (2.5 GB ingestion) | `REFLIB2_*` | 23 documents (NASA/ESA/arXiv) + 10 cloned repos (1 failed) + manifest/crosswalk/adversarial review |

Physical top level (verified 2026-08-08):

```
REFLIB1_EXUDYN/EXUDYN                        REFLIB2_00_manifest/00_manifest
REFLIB1_MATLAB_space_debri_capturing_sim/... REFLIB2_01_nasa_mechanical/01_nasa_mechanical        (10 NTRS PDF + .meta.json)
REFLIB1_SPART/SPART                          REFLIB2_02_esa_isam_2026/02_esa_isam_2026            (7 ESA CSD2026 PDF + _pages/)
REFLIB1_SpaceDyn/SpaceDyn                    REFLIB2_03_space_dynamics/03_space_dynamics          (papers/ docs/ repos/basilisk)
REFLIB1_SpaceDyn_python/SpaceDyn_python      REFLIB2_04_robotics_software/04_robotics_software    (repos: 7)
REFLIB1__root_/ (REFERENCE_INDEX.json,       REFLIB2_05_perception_datasets/05_perception_datasets (repos/speedplusbaseline)
  LICENSE_NOTES_FOR_STUDENT_USE.md,          REFLIB2_06_flexible_multibody/06_flexible_multibody   (repos/ANCF_beam; chrono ABSENT)
  MATLAB_MCP_SETUP_STATUS_20260729.md)       REFLIB2_07_reading_notes/07_reading_notes            (4 .md)
REFLIB1__tools/_tools (clone/build scripts)  REFLIB2_08_project_crosswalk/08_project_crosswalk    (3 .md + 1 .csv)
REFLIB1_oresat_structure/oresat_structure    REFLIB2_09_adversarial_reviews/09_adversarial_reviews (1 .md)
REFLIB1_space_robotics_bench/...             REFLIB2_PUBLIC_REFERENCE_INGESTION_REPORT.md/        (dir wrapping 1 .md)
REFLIB1_spacedyn_freefloating_demo/...       REFLIB2_TOP_12_GITHUB_PROJECTS.md/                   (dir wrapping 1 .md)
REFLIB1_spaceros_demos/spaceros_demos        REFLIB2_TOP_20_ACTIONABLE_REFERENCES.md/             (dir wrapping 1 .md)
```

**Physical quirks an agent must know**
- All ROOT B repos are **.git-stripped working-tree copies**. `find -maxdepth 3 -name .git` returns nothing. Repo identity = commit SHA recorded in `REFLIB1__root_/REFERENCE_INDEX.json` and `REFLIB2_00_manifest/00_manifest/*`. You cannot `git log` inside ROOT B.
- The three top-level `REFLIB2_*.md` entries are **directories**, each wrapping exactly one `.md` file of a shorter name (consolidation artifact). Open e.g. `REFLIB2_TOP_12_GITHUB_PROJECTS.md/TOP_12_GITHUB_PROJECTS.md`.
- Every REFLIB1 repo carries a project-authored `SUMMARY.md` (2026-07-28) — read it first, then cross-check the worktree (per `knowledge/B_assets_and_conventions.md` convention).
- `chrono` is referenced in REFLIB2 manifests but **physically absent** (clone failed, curl 56; adjudicated REJECT + NOT_USABLE_OFFLINE). The only real chrono clone on disk is inside ROOT A (`80_third_party/vendor/chrono@24c78cf8`) — see HOLD-3.

## 2. Logical map R1–R7 (ROLE → ACTUAL PATH; physical names unchanged)

| Logical role | Content | ACTUAL PHYSICAL PATH (do not rename) |
|---|---|---|
| **R1 PAPERS_STANDARDS** | 10 NASA NTRS PDFs, 7 ESA Clean Space Days 2026 PDFs (+ `_pages/` HTML provenance), 4 arXiv preprints (+`.meta.xml`), SPART readthedocs PDF, SpaceDyn homepage capture, 4 reading notes | `REFLIB2_01_nasa_mechanical/01_nasa_mechanical/` · `REFLIB2_02_esa_isam_2026/02_esa_isam_2026/` · `REFLIB2_03_space_dynamics/03_space_dynamics/{papers,docs}/` · `REFLIB2_07_reading_notes/07_reading_notes/` |
| **R2 OPEN_SOURCE_PROJECTS** | Platform/software repos: astrobee, isaac, int-ball2_simulator, int-ball2_isaac_sim, space-ros, space_robotics_bench, spaceros_demos | `REFLIB2_04_robotics_software/04_robotics_software/repos/{astrobee,isaac,int-ball2_simulator,int-ball2_isaac_sim,space-ros}` · `REFLIB1_space_robotics_bench/space_robotics_bench` · `REFLIB1_spaceros_demos/spaceros_demos` |
| **R3 DYNAMICS_SIMULATION_LIBRARY** | Physical ROOT B: EXUDYN, SPART, SpaceDyn (MATLAB), SpaceDyn_python, MATLAB_space_debri_capturing_sim, spacedyn_freefloating_demo (local), basilisk, ANCF_beam. Registered external-to-B references: Chrono (ROOT A), SpaceRobotEnv (ROOT A + identical `F:\Robotic arm` duplicate), zero-robotic-arm MuJoCo TD3 teaching case (`5. Deep_LR`) | `REFLIB1_EXUDYN/EXUDYN` · `REFLIB1_SPART/SPART` · `REFLIB1_SpaceDyn/SpaceDyn` · `REFLIB1_SpaceDyn_python/SpaceDyn_python` · `REFLIB1_MATLAB_space_debri_capturing_sim/...` · `REFLIB1_spacedyn_freefloating_demo/...` · `REFLIB2_03_space_dynamics/03_space_dynamics/repos/basilisk` · `REFLIB2_06_flexible_multibody/06_flexible_multibody/repos/ANCF_beam` · external pointers in the installed registers |
| **R4 CAD_DONOR_REFERENCE** | oresat_structure (CubeSat SolidWorks, mass-list logic only). External registered donors (outside ROOT B): `F:\Robotic arm\High_performance_robotics_arm`, `F:\Robotic arm\zero-robotic-arm` | `REFLIB1_oresat_structure/oresat_structure` (+ external paths registered in `OPEN_SOURCE_PROJECT_REGISTER.csv`) |
| **R5 DATASETS** | speedplusbaseline CODE ONLY — SPEED+ dataset itself was never downloaded (license/volume NOT_VERIFIED) | `REFLIB2_05_perception_datasets/05_perception_datasets/repos/speedplusbaseline` |
| **R6 TOOL_EXAMPLES** | FreeCAD utilities (freecad.robotcad, FreeCAD_Assembly4.1), library maintenance scripts | `REFLIB2_04_robotics_software/04_robotics_software/repos/{freecad.robotcad,FreeCAD_Assembly4.1}` · `REFLIB1__tools/_tools` · `REFLIB2_00_manifest/00_manifest/tools` |
| **R7 CAE_REFERENCE** | External affiliate, NOT inside ROOT B: `F:\Mechanical structure modeling and simulation` (642 files, general CAE learning library, mostly non-SEI; owned by PL1-F recon) | external |
| **Governance/index layer** (not a role, spans R1–R6) | Master index, hash manifest, license register, reuse matrix, crosswalk, adversarial review, ingestion report, TOP-12/TOP-20, REFERENCE_INDEX.json, license notes | `REFLIB2_00_manifest/00_manifest/` · `REFLIB2_08_project_crosswalk/08_project_crosswalk/` · `REFLIB2_09_adversarial_reviews/09_adversarial_reviews/` · `REFLIB2_*.md/` (3 wrapper dirs) · `REFLIB1__root_/` |

**Recommendation to PL1-G**: keep the physical `REFLIB1_*` / `REFLIB2_*` names stable (every manifest hash path and the ROOT A `PROJECT_START_HERE.md` already point at them). Implement R1–R7 purely as the logical table above + `OPEN_SOURCE_PROJECT_REGISTER.csv` + the START_HERE entry doc. If a future consolidation wants physical R-dirs, do it as a new CM wave with hash re-verification — not by ad-hoc moves.

## 3. Authority & usage contract (already in force, restated)

- ROOT B **never owns project authority**. Its own manifests say so: no number from any artifact may enter SSOT/CAD/URDF/`*_gate_check.json` (`PUBLIC_REFERENCE_MASTER_INDEX.csv`, `prohibited_use` column, every row).
- Repo-level verdicts already adjudicated 2026-08-05 (`GITHUB_REPOSITORY_REUSE_MATRIX.csv`, 19/19 no UNSET): RUN_AS_SANDBOX_BENCHMARK ×2 (basilisk, SPART — both frozen in current window), READ_ONLY ×6, POST_COMPETITION ×3, REJECT ×8. **Zero lines of code recommended for integration before 2026-09-01.**
- License UNKNOWN / no-LICENSE (HOLD) items: **8 — SpaceDyn, space-ros, ANCF_beam, High_performance_robotics_arm, reBotArmController_ROS2, spacedyn_freefloating_demo, Pendulum-DDPG, ingestion toolset**. Chrono is no longer a license HOLD: the clean ROOT A checkout verifies BSD-3-Clause, although its external-to-B location remains HOLD-3. Refinement found by PL1-D: **oresat_structure is NOT license-unknown** — `LICENSE/cern_ohl_s_v2.pdf` = CERN-OHL-S v2 (the 2026-07-27 `REFERENCE_INDEX.json` said UNKNOWN_LICENSE; the file is a *directory* named `LICENSE`, which the earlier scan missed).
- MuJoCo examples: **no standalone MuJoCo worktree is physically stored inside ROOT B**. The installed registers point to (a) clean SpaceRobotEnv in ROOT A (`80_third_party/external/...`, identical duplicate in `F:\Robotic arm`) and (b) `F:\Robotic arm\zero-robotic-arm\5. Deep_LR` (fixed-base desktop 6R Gymnasium/MuJoCo/TD3 teaching case; not validated by its own README). Both are external reference/teaching assets, not project authority or runtime. Mandate coverage note: Isaac examples → `int-ball2_isaac_sim` + `space_robotics_bench`; ROS2 packages → `spaceros_demos`, `space-ros`, `reBotArmController_ROS2` (external); FreeCAD utilities → `freecad.robotcad`, `FreeCAD_Assembly4.1`.

## 4. Installed entry document

The entry doc is installed at `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY\REFERENCE_LIBRARY_START_HERE.md`, together with `OPEN_SOURCE_PROJECT_REGISTER.csv`, `DYNAMICS_SIMULATION_LIBRARY_INDEX.csv`, and `CAD_DONOR_REGISTER.csv`. It contains: (a) one-paragraph definition of the library and its two-source lineage; (b) the R1–R7 table from §2; (c) the reading order (START_HERE → register CSV → `REFERENCE_INDEX.json` / `PUBLIC_REFERENCE_MASTER_INDEX.csv` → per-repo `SUMMARY.md` → worktree); (d) the MAY/MAY-NOT contract (reference-only vs runtime-dependency ban, license-HOLD list, the freecad.robotcad environmental hazard, the "ROOT B never owns authority" rule); (e) pointer to the governance layer for verdicts and citation forms.
