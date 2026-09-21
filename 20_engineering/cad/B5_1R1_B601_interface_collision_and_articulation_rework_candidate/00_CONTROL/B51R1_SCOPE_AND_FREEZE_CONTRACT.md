# B5.1R1 scope and freeze contract

## Authorized in this increment

- Read frozen B5.1 and canonical inputs.
- Create additive B5.1R1 research records.
- Perform source, provenance, exact-BREP-result, topology, and test-contract
  analysis.
- Preserve missing values as `UNKNOWN`, `TBD`, `HOLD`, or `NOT_RUN`.
- Define the next human Gate and falsifiable exit criteria.

## Frozen and read-only

- The complete `B5_1_B601_interface_closure_candidate` parent tree.
- V2.0, V2.1, V2.2, and V2.2 native accepted/candidate trees.
- The accepted B601 URDF and vendor STEP.
- B5.0 evidence and accepted artifacts.
- Simulation, competition, hardware, and external-assembly Gate files.
- Parent H9, H10, G2, G3, G4, G5, G6, and G7 verdicts.

The parent Gate hash is checked against
`DD4286A1826AD6F47AEF81C3685A047786430A6F5BB31D797C206A5A2A91F8D0`.
Hash drift is a hard stop, not an instruction to refresh this lock silently.

## Not authorized

- Translating B5.1 geometry to hide the datum conflict.
- Adding a `3 mm` shim or cutting a panel without an approved load-path
  architecture.
- Opening and saving native CAD, rewriting references, or generating a new
  STEP.
- Selecting H9 Mode A/Mode B, adapter A/B/C, HDRM hardware, material,
  thickness, fastener, preload, stiffness, load, tolerance, or qualification
  values.
- Running FEA, continuous clearance, Isaac, MuJoCo, hardware motion, or dataset
  generation.
- Upgrading any Gate to PASS, or claiming physical attachment, launch
  qualification, manufacturing readiness, or flight readiness.

## CAD-skill visual validation boundary

This increment changes no visible geometry and creates no STEP. Snapshot review
is therefore not applicable to this increment. When Phase 1 is authorized and a
STEP or native CAD file is created or changed, deterministic inspection,
geometry checks, and required snapshots become mandatory before any visual or
geometric claim.

## Stop and rollback

All B5.1R1 files are additive. If a locked input drifts or an authority conflict
cannot be adjudicated, stop with `B51R1_BLOCKED_PARENT_BASELINE_DRIFT` or
`HUMAN_ADJUDICATION_REQUIRED`; do not edit or delete the conflicting evidence.

