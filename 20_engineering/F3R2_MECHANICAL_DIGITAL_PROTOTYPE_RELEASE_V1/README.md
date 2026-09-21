# F3R2 Mechanical Digital Prototype Release V1

This workspace is the M4 controlled continuation of the M3 detailed-design
working baseline.  Its purpose is to establish a reproducible, versioned
mechanical digital prototype and a fail-closed exchange contract for bounded
dynamics/grasping research.

It is **not** a manufacturing, qualification, launcher-integration, or flight
release.  Formal FEA is prohibited until the structural-analysis entry gate is
explicitly passed by controlled load, material, boundary-condition, fastener,
contact, mass-property, and acceptance authorities.

Unknown values remain `null` with an explicit `HOLD`; no zero filling is
permitted.  The 6 GiB memory gate remains failed during this phase.  Any
FreeCAD execution is a bounded Owner Override run and must be recorded as such.

## Controlled state path

`M3_CONTROLLED_WORKING_BASELINE -> M4_DIGITAL_PROTOTYPE_WORKING_RELEASE`

From M4, two independently earned branches are tracked:

- `STRUCTURAL_ANALYSIS_READY` remains `HOLD` until the physical structural-entry
  authorities close.
- `SIM14_BOUNDED_DYNAMICS_READY` may pass only as a software/ideal-rigid-lock
  diagnostic; it does not depend on, or substitute for, structural release.

Production contact dynamics and physics-gated RL require the applicable
physical, structural, mass-property, contact, and validation gates to close.

## Release entry points

- `12_release/M4_RELEASE_SUMMARY.md` — engineering outcome, evidence and next loop.
- `12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json` — machine-readable scoped tokens and mandatory HOLDs.
- `12_release/M4_REQUIREMENTS_VERIFICATION_MATRIX_V1.csv` — requirement-to-evidence closure.
- `12_release/M4_NEXT_LOOP_ACTION_REGISTER_V1.yaml` — ordered M5 physical-authority backlog.
- `12_release/M4_OUTPUT_MANIFEST_V1.json` — final M4 and Sim14 output hashes.

The later states are earned independently.  A passed artifact-integrity test
does not imply that missing physical authorities have been closed.
