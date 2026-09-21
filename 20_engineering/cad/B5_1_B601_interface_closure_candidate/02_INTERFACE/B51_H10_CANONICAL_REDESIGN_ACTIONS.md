# B51 H10 canonical redesign actions

Status: `H10_CANONICAL_BREP_DIAGNOSTIC_FEASIBLE_GEOMETRY_REDESIGN_REQUIRED`

The inherited ledger retains all 28 records as open.  No row has been closed
or overwritten.  The reproducible diagnostic is
`07_VERIFICATION/interface/B51_CANONICAL_INTERFACE_BREP_AUDIT.json`.

## Confirmed findings

- Canonical `native_STOWED.step`: 73 solids, zero invalid solids.
- Bridge, G07 saddle and G08 saddle candidates: eight solids each, zero invalid
  solids.
- G07 saddle to canonical primary structure: `3.000000000000014 mm`.
- G08 saddle to canonical primary structure: `3.000000000000014 mm`.
- Both saddles to removable panels: `0.0 mm`.
- The datum-centre mismatch is `4.0 mm` (`105.65` versus `101.65 mm`).
- The old canonical occurrences `02_B601_Mount_and_Load_Path` and
  `04_ARM_STOW_SUPPORT` are replacement targets, not collision-clearance
  authorities for the new hardware.

## Closure work still required

1. Create a deterministic mapping from every legacy V14 module/structure pair
   to one new candidate child and one canonical target occurrence.
2. Rebuild both saddle base interfaces so their load path reaches a named
   frame/longeron, including any panel cutout or stand-off detail.
3. Separate physical bodies from the two
   `HDRM_CENTER_ENVELOPE_NON_PHYSICAL_HOLD` keepouts.
4. For every intended seat or lap, provide common-volume, minimum-distance,
   contact-area/coplanarity, assembly direction, edge margin and local image.
5. Eliminate all `UNACCEPTABLE_COLLISION` rows and leave no unadjudicated row.

Until those actions are evidenced, `G2=FAIL_GEOMETRY_REDESIGN_REQUIRED`.

