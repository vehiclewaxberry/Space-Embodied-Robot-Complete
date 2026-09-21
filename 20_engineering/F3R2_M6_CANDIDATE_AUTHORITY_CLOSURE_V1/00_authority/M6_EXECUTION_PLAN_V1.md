# M6 Execution Plan V1

Date: 2026-08-21. Owner-authorized bounded loop.

## Inputs (read-only, hash-pinned baselines)

| Need | Path |
|---|---|
| M4 release tree | `20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/` |
| M4 master CAD (frozen) | `…/02_parameterized_cad/SEI_DIGITAL_PROTOTYPE_V1.FCStd` (+ `.step`) |
| M4 mass ledger | `…/03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml`, `CONFIGURATION_LIBRARY_V1.yaml` |
| M4 material library | `…/04_material_database/PROTOTYPE_MATERIAL_LIBRARY_V1.yaml` |
| M4 tolerance plans | `…/05_tolerance/*.yaml` |
| M4 drawings/BOM | `…/09_drawings/`, `…/10_BOM/` |
| M4 structural gate | `…/07_structural_model/STRUCTURAL_ANALYSIS_ENTRY_GATE.json` |
| M4 build/validate patterns | `…/02_parameterized_cad/M4_BUILD_DIGITAL_PROTOTYPE_V1.py`, `99_tools/` |
| M5 tree | `20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/` |
| M5 frame decision | `…/01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json` |
| M5 config contract + snapshots | `…/02_configurations/` |
| M5 loads | `…/03_load_authority/`, `…/04_joint_load_model/` |
| M5 interface | `…/07_simulation_handoff/MECH_DYNAMICS_INTERFACE_V3.yaml` |
| CDR Phase-1 tree | `20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/` |
| L0 URDF | `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` |
| Geometry SSOT | `20_engineering/config/geometry/arm_b601_v1.yaml`, `service_spacecraft_v1.yaml` |

## Known engineering facts to honor

- M3R mounting: 4× HM4-75/M4-class screw positions, 64×64 mm square pattern,
  equivalent PCD 90.509642 mm. x-stations: 185.25 (M frame, nonphysical),
  198.0 (plate outer face), 208.0 (physical mounting face), 210.405 mm
  (screw end faces). Legacy flange occupies x 170.25–185.25 mm with
  ambiguous ownership. Bus–M3R minimum gap 10.75 mm exposes the missing
  load bridge (not an assembly pass).
- Stage B nominal net hole-edge ligament 6.7 mm (= 160/2 − 70 − 6.6/2).
- B601 accepted mass 4.695555949 kg (L0, never overridden by CAD).
- M3R digital budget authority 0.7619 kg (BUDGETED, single active source).
- Gripper R1 neutral stroke 0–71.5 mm, 144 samples, 0 positive overlaps
  (neutral-only PASS); manufacturing clearance map is HOLD.
- M5 structural entry subgates: all HOLD/PENDING; formal FEA run count 0.

## Work packages

| WP | Scope | Writes under | FreeCAD |
|---|---|---|---|
| WP1 | Load-bridge candidate CAD + datums + fitup receipt | `wp1_load_bridge/` | YES (exclusive) |
| WP2 | 9-config candidate transforms + diagnostic mass/CG/inertia aggregation | `wp2_mass_properties/` | no |
| WP3 | Tolerance-chain numerics (3 chains) | `wp3_tolerance/` | no |
| WP4 | Material library V2 (sourced candidates) | `wp4_materials/` | no |
| WP5 | Structural entry evidence pack (no FEA) | `wp5_structural_entry/` | no |
| WP6 | Candidate drawings + BOM extension | `wp6_drawings_bom/` | no |
| WP7 | CDR Q0/Q1/Q2 closure-ready evidence packs | `wp7_cdr_evidence/` | no |

Integration (post-WP): output manifest + independent validator + M6 gate +
release summary into `12_release/`.

## Rules for every WP

1. Read inputs; never modify them. Write only inside your WP directory.
2. Every artifact carries schema, generated_local, source register with
   SHA-256 of every input used, and explicit HOLD/null for unknowns.
3. Candidate ≠ authority. Diagnostic ≠ released. No zero filling.
4. Report files written, hashes, and open HOLDs in a per-WP receipt JSON.
