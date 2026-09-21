# Frozen baseline input audit

Baseline: `V5R_NEUTRAL_OPERATIONAL_MECHANICAL_BASELINE_V1`

This directory freezes the exact file inputs available to the mechanical CDR qualification-closure work. The audit is read-only with respect to the prior rapid round, sim13, the accepted URDF, and every referenced V5 donor/staging file.

## Result

- Bound inputs: **18**
- Owner-designated immutable files: **5**
- Existing and nonzero: **18 / 18**
- Byte-count matches: **18 / 18**
- SHA-256 matches: **18 / 18**
- Missing: **0**
- Zero-byte: **0**
- Hash drift: **0**
- Audit verdict: `FROZEN_BASELINE_INPUT_AUDIT_PASS_FORMAL_FEA_NOT_AUTHORIZED`
- `formal_fea_authorized: false`

This PASS means only that the named inputs were present, nonzero, and matched their pinned hashes. It does not authorize a formal FEA run, clear any qualification HOLD, or convert the package-level neutral composite into a monolithically integrated/native CAD baseline.

## Audit artifacts

| Artifact | SHA-256 |
|---|---|
| `00_authority/FROZEN_BASELINE_INPUT_MANIFEST_V1.json` | `ED7CF4519B3EDFEFC3CE20020CCE50543C0DFBFAC818A592DD83C81FDB75BDA3` |
| `00_authority/PRE_INPUT_HASHES_V1.csv` | `2FADEF55FF3F1FA0477C2DC6471B868C6B763E0D3D769EFE5F8A5D9DECE89F96` |

The JSON manifest is the machine-readable authority. The CSV is the flat PRE-hash ledger. The validation receipt summarizes the independent recheck after those two files were created.

## Owner-designated immutable anchors

| Role | Project-relative path | SHA-256 |
|---|---|---|
| V5 operational mechanical Gate | `20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/08_gate/V5_OPERATIONAL_MECHANICAL_GATE.json` | `E0369477D775182F40E38EE43AA6DED18D17A0F9FC83EA16034D14F022EB629E` |
| Neutral package validation | `20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/06_pack_and_go/NEUTRAL_PACKAGE_VALIDATION.json` | `CB6FD22F353241BF6F2D9F57C3D8D1A7D92A5C4782FFEFC8D946FD157B64AB29` |
| Gripper R1 geometry validation | `20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json` | `7BC0DF784B36159624A8A89B67207C54C5C9C780B103CB38658DE2D6BA845F47` |
| Production mechanical–RL interface | `20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/02_interfaces/MECH_RL_INTERFACE_V1.yaml` | `26E5A55570BE9E1DAF6683F76FB2A68D0265872EB5FB7C876E3324914DA36BB0` |
| sim13 environment-bootstrap Gate | `30_simulation/sim_13_physics_gated_embodied_grasping/evidence/SIM13_ENVIRONMENT_BOOTSTRAP_GATE.json` | `C224853EABBD00C9C14C812922E3B2A7E406AF43A81CF7CA6A307860A951466C` |

## Additional frozen inputs

The manifest also binds the accepted B601 URDF; neutral STEP/FCStd/visual/collision assets; neutral package manifest; M3R Rev-B2 combined/Stage-A/Stage-B STEP geometry; the V5 Loop1E Attempt-2 staging assembly; and the three V5 gripper donor parts.

## Recheck rule

Recompute every manifest entry before any downstream qualification calculation. A missing file, zero-byte file, byte-count mismatch, or SHA-256 mismatch is an immediate HOLD. Do not update the expected value in place and do not silently rebaseline.

Formal FEA remains unauthorized until a later explicit Gate sets `formal_fea_authorized: true`.
