# F3R2 M6 Candidate Authority Closure V1

This workspace is the owner-authorized continuation after the M4 scoped
digital-prototype release, the M5 geometry-and-loads closure, and the SIM15
diagnostic pass (all 2026-08-21).

Its purpose is to close, at **candidate / diagnostic level only**, the M5
register items that are digitally executable without physical hardware,
human review, or external ICDs:

- M5-A01: spacecraft-to-M3R load bridge candidate geometry and datums;
- M5-A03 (digital portion): nine-configuration candidate transforms and
  diagnostic mass/CG/inertia aggregation;
- M5-A05 (digital portion): source-classified diagnostic mass-property
  ledger upgrade with an explicit uncertainty model (no measured values);
- M5-A06 (digital portion): prototype material library extension with
  sourced product-form, process, and environment candidates;
- M5-A07 (digital portion): numeric execution of the B601-M3R, gripper-rail,
  and hinge tolerance chains;
- M5-A09 preparation: structural-analysis entry evidence pack (no FEA);
- CDR Phase-1 (Q0/Q1/Q2) closure-ready evidence packs (gates stay HOLD).

This is **not** a manufacturing, qualification, structural, or flight
release. Formal FEA remains prohibited; `formal_fea_run_count` stays 0.
Unknown values remain `null` with explicit `HOLD`; no zero filling.
CAD-derived and material-derived values never override the accepted URDF
(L0) masses. The 6 GiB memory gate remains failed; the only FreeCAD
execution permitted is the single bounded Owner Override run registered for
WP1.

## Layout

- `00_authority/` — phase boundary, execution plan, owner-override register
- `wp1_load_bridge/` — candidate load-bridge CAD, datums, fitup receipt
- `wp2_mass_properties/` — nine-configuration diagnostic aggregation
- `wp3_tolerance/` — executed tolerance-chain numerics
- `wp4_materials/` — prototype material library V2 (candidate-only)
- `wp5_structural_entry/` — structural entry evidence pack (no FEA)
- `wp6_drawings_bom/` — candidate drawing and BOM extensions
- `wp7_cdr_evidence/` — CDR Q0/Q1/Q2 closure-ready evidence packs
- `12_release/` — M6 gate, output manifest, release summary
- `99_tools/` — builders and independent validators

## Release entry points

- `12_release/M6_RELEASE_SUMMARY.md`
- `12_release/M6_CANDIDATE_AUTHORITY_CLOSURE_GATE_V1.json`
- `12_release/M6_OUTPUT_MANIFEST_V1.json`
