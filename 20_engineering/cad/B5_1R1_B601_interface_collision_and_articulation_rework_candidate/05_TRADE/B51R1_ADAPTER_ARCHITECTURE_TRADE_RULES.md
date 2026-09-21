# Adapter architecture A/B/C trade rules

Status:

`TRADE_FRAME_READY / WEIGHTED_SCORE_DISABLED / NO_DOWNSELECT`

Evidence maturity and engineering merit are separate axes. Alternative A does
not win because an eight-solid STEP exists; B and C do not lose because their
geometry has not yet been authored.

## Alternatives

- A — reworked double-crossmember bridge. Current grade:
  `E2_VALID_STEP_CANDIDATE`; the independent D100 probe has zero common volume,
  but attachment and H10 closure are absent.
- B — front/rear primary-frame spanning architecture. Current grade:
  `E1_CONCEPT_ONLY`.
- C — local reinforced frame or load-bearing tube. Current grade:
  `E1_CONCEPT_ONLY`; it also requires explicit canonical-structure modification
  authority.

## Evidence grades

`E0_NONE`, `E1_CONCEPT`, `E2_VALID_STEP`, `E3_CANONICAL_EXACT_BREP`,
`E4_NATIVE_AND_READBACK`, `E5_ANALYSIS_WITH_APPROVED_INPUTS`.

## Mandatory veto criteria

- `H10_28_ROW_CLOSURE`
- `PRIMARY_STRUCTURE_6DOF_LOAD_PATH`
- `D100_PASSAGE_PRESERVED`
- `CANONICAL_STRUCTURE_MODIFICATION_AUTHORITY`

The remaining criteria are evaluated for Mode A and Mode B separately until H9
is decided. Static endpoint clearance cannot satisfy either continuous-sweep
criterion.

## Downselect Gate

No alternative may be ranked until:

1. H9 is decided, or all alternatives have comparable Mode A and Mode B
   evidence;
2. all three use the same corrected skeleton and comparable evidence grade;
3. D100, load path, tools, harness, and modification authority are evidenced;
4. each alternative has canonical exact-BREP results and an old-to-new
   occurrence map;
5. criteria, vetoes, and weights are human-authorized;
6. no unevaluated FEA or subjective mass claim is scored.

Until then every `weighted_score` is blank and
`score_authority=DISABLED`.

