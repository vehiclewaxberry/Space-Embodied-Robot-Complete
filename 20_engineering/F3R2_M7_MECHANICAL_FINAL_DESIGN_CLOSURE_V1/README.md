# F3R2 M7 Mechanical Final Design Closure V1

Owner-directed loop (directive dated 2026-08-21/22): close every internally
closable mechanical-design HOLD and drive the product to

    MECHANICAL_ENGINEERING_DESIGN_RELEASED   (Gate A)

while keeping

    MECHANICAL_FLIGHT_QUALIFICATION_RELEASED (Gate B) = HOLD

This loop converts the wide, shallow M4/M5/M6 candidate assets into a narrow,
deep, source-bound product definition: geometry, configurations, design mass
model, materials, tolerance allocation, fasteners, mechanisms, harness,
operational loads, operational structural verification, drawings, BOM, and the
MECH-RL interface.

## Owner decisions frozen this loop

See `00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml` (ODR-01..ODR-06),
including: M-frame authority = T_SM=[185.25,0,0] mm + Ry(90°); panel failure =
attached-stuck, never jettison unless a jettison mechanism is later designed;
SolidWorks native line permanently off critical path; native V5 gripper
interference findings superseded by neutral R1 authority; M3R 0.7619 kg =
design-budget authority; operational-loads FEA authorized, launch-qualification
FEA remains HOLD (no launcher ICD).

## Layout

- `00_authority/` — owner decisions, phase boundary, execution plan
- `wp1_structure_cad/` — product structure, design-freeze assembly, harness routing
- `wp2_design_mass/` — nine-configuration DESIGN mass/CoM/inertia model
- `wp3_tolerance_alloc/` — 14-chain tolerance allocation
- `wp4_fastener_design/` — M3R + product fastener design and schedules
- `wp5_mechanisms/` — HDRM / solar hinge / gripper engineering packs
- `wp6_material_selection/` — DESIGN_APPROVED material register
- `wp7_fea_operational/` — operational structural verification (Abaqus batch)
- `wp8_thermal/` — thermo-elastic ΔT sensitivity envelopes
- `wp9_release_package/` — drawings, BOM V3, schedules, assembly, inspection
- `wp10_mech_rl_v4/` — dynamics/RL interface upgrade
- `12_release/` — M7 gate, manifest, Gate A scorecard, summary
- `99_tools/` — builders, validators, solver probes

## Standing rules (unchanged from M4–M6)

Fail-closed; no zero-fill; candidate≠authority; design≠flight-qualified;
unknowns stay null+HOLD where a physical/external input is genuinely absent;
L0 URDF masses never overridden; launch qualification stays HOLD; every
artifact carries schema/generated_local/source_register with SHA-256 pins.
FreeCAD: single-process Owner Override (WP1 only). Abaqus: batch-only,
no CAE GUI, model sizes bounded by the failed 6 GiB memory gate
(available ≈1.3 GiB at loop start).
