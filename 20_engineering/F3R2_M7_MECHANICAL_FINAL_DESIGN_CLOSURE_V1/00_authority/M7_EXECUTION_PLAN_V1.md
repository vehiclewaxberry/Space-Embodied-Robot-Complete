# M7 Execution Plan V1 — WP contracts and interface pinning

Date: 2026-08-22. Owner-directed final mechanical design closure.

## Confirmed tool paths (probed this loop)

- FreeCADCmd 1.1.3: `G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe`
  (WP1 exclusive, single process, Owner Override)
- Abaqus 2023 batch: `D:/SIMULIA/Commands/abaqus.bat job=<name> interactive`
  (WP7 exclusive; license verified on localhost Flexnet; micro-job COMPLETED
  with non-zero .dat/.odb; memory bound: single job, mesh ≤ ~4000 C3D8R)

## Contract values pinned for cross-WP consistency

These values are the only ones sibling WPs may quote before integration
backfill; they come from existing baselines and owner rulings:

- M frame authority: T_SM = [185.25, 0, 0] mm + Ry(90 deg) (ODR-01)
- Panel failure semantics: attached-stuck, never jettison (ODR-02)
- Neutral FreeCAD/STEP chain = system geometry authority (ODR-03)
- M3R design mass: 0.7619 kg, DESIGN_BUDGET, confidence B (ODR-05)
- B601 arm: 4.695555949342986 kg, ACCEPTED_URDF (L0, never overridden)
- Bus core (no panels, no legacy flange) diagnostic: 22.927194215348 kg
- Legacy flange diagnostic: 0.376019184652 kg → assigned to BUS_PRIMARY_STRUCTURE
  with declared uncertainty (ODR-01 scope note; mass allocation design ruling)
- Solar panel (each): 0.3483933 kg; panel box 0.227×0.200×0.006 m
- Load bridge candidate: 160×160×10.75 mm plate, x∈[185.25,196.0],
  4×⌀6.6 @ (±70,±70), center ⌀40, candidate mass 702.195458 g
  (MATERIAL_DERIVED, 6061-T6 2700 kg/m³), source:
  `20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/`
- M3R pattern: 4×HM4-75/M4-class, 64×64 mm square, PCD 90.509642 mm;
  x-stations 185.25/198.0/208.0/210.405 mm; Stage B ligament 6.7 mm
- Gripper R1: stroke 0–71.5 mm, 144 samples, neutral 0-overlap PASS
- M6 tolerance numbers: B601–M3R WC min radial clearance 0.101015357 mm;
  Stage A↔B spigot WC 0.206 mm; skirt WC 0.207 mm; dowel clocking WC
  1.8909e-3 rad; hinge tip sensitivity 0.2 mm/mrad
- CDR loads: 19 families / 21 cases / 13 combinations; capture anchor
  impulses 22 kg/0.5 dps: 0.0601233–0.360622 N·s; 150 kg/3 dps:
  0.274973–0.677633 N·s (DERIVED, research-bound)
- Operational FEA authorization: ODR-06 (launch FEA stays HOLD)

## WP output contracts (filenames each WP must produce)

| WP | Directory | Contract outputs |
|---|---|---|
| WP1 | wp1_structure_cad/ | PRODUCT_STRUCTURE_V1.yaml; DESIGN_FREEZE_ASSEMBLY_V1.FCStd/.step; HARNESS_ROUTING_V1.yaml; KEEP_OUT_REGISTER_V1.yaml; SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml; build script(s); receipt.json |
| WP2 | wp2_design_mass/ | DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml; aggregate_m7_design_mass.py; SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml (9 configs: mass, CoM, full tensor about system CoM in S, principal inertia+axes, uncertainty, pedigree); receipt.json |
| WP3 | wp3_tolerance_alloc/ | TOLERANCE_CHAIN_REGISTER_V1.yaml (14 chains); TOLERANCE_ALLOCATION_RESULTS_V1.yaml + .csv; DRAWING_TOLERANCE_SCHEME_V1.csv; receipt.json |
| WP4 | wp4_fastener_design/ | M3R_FASTENER_DESIGN_V1.yaml; FASTENER_SCHEDULE_V1.csv; TORQUE_PRELOAD_SCHEDULE_V1.csv; FASTENER_ANALYTIC_CHECKS_V1.csv; receipt.json |
| WP5 | wp5_mechanisms/ | HDRM_ENGINEERING_PACK_V1.yaml; SOLAR_HINGE_DEPLOYMENT_PACK_V1.yaml; GRIPPER_ENGINEERING_PACK_V1.yaml; MECHANISM_VERIFICATION_CROSSREF_V1.csv; receipt.json |
| WP6 | wp6_material_selection/ | DESIGN_MATERIAL_SELECTION_V1.yaml; PROCESS_AND_FINISH_REGISTER_V1.csv; receipt.json |
| WP7 | wp7_fea_operational/ | FEA1 input generator + .inp decks; FEA1_EVIDENCE_V1.json (mesh convergence 3 levels, reaction balance, energy check, solver version, result hashes, .dat non-zero proof); FEA1_RESULTS_V1.csv; FEA2_FEA8_DECK_REGISTER_V1.yaml; receipt.json |
| WP8 | wp8_thermal/ | THERMO_ELASTIC_SENSITIVITY_V1.yaml + THERMO_ELASTIC_ENVELOPE_V1.csv; receipt.json |
| WP9 | wp9_release_package/ | DRAWING_SET_INDEX_V1.csv (+ new draft SVGs); BOM_V3_DESIGN.csv; ASSEMBLY_PROCEDURE_V1.md; INSPECTION_PLAN_V1.csv; VERIFICATION_MATRIX_V1.csv; ICD_V3_DRAFT.yaml; receipt.json |
| WP10 | wp10_mech_rl_v4/ | MECH_DYNAMICS_INTERFACE_V4.yaml; SIM_COMPATIBILITY_NOTE_V1.md; receipt.json |

Sibling references are by these contract paths only; integration backfills
hashes into 12_release/M7_CROSS_WP_REFERENCE_RECONCILIATION_V1.json.

## Gate A scorecard mapping (12_release/M7_GATE_A_SCORECARD_V1.json)

geometry→WP1; configurations→WP2; mass/inertia design model→WP2;
frame authority→ODR-01+WP1; materials selected→WP6; tolerance allocation→WP3;
fasteners→WP4; gripper→WP5; hinges→WP5; HDRM design→WP5;
harness routing→WP1; drawings→WP9; BOM→WP9; operational FEA→WP7;
operational modes (mechanism analytical + thermal)→WP5+WP8;
MECH-RL interface→WP10.

Gate B (flight qualification) remains HOLD: launcher/separation ICD,
flight allowables, as-built mass, qualification/acceptance testing.
