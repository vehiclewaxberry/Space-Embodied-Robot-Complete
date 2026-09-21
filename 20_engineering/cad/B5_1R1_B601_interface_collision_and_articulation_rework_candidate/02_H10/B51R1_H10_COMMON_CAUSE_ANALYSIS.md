# H10 common-cause analysis and row-closure contract

Parent ledger:

- path:
  `B5_1_B601_interface_closure_candidate/02_INTERFACE/B51_INTERFERENCE_DISPOSITION_LEDGER.csv`
- SHA-256:
  `773E904CB1CFF9F85EC03D44E74BA1D51D32F45B39DAACA3E171D9C18EB561AD`
- rows: `28`
- `UNACCEPTABLE_COLLISION`: `8`
- `INTENDED_BOLTED_LAP`: `20`
- parent exact common volume, minimum distance, local evidence, and replacement
  part fields populated: `0/28`
- R1 rows closed in this increment: `0/28`

## Common-cause clusters

| Cluster | Parent rows | Diagnostic interpretation |
|---|---|---|
| `RC-H10-A` | V14-01..04 | legacy full-area spreader collides with four front-frame regions |
| `RC-H10-B` | V14-05..16 | adapter laps were authored without canonical primary-face and layer semantics |
| `RC-H10-C` | V14-17..19 | G07 crossbeam-to-primary laps lack a named, qualified interface |
| `RC-H10-D` | V14-20..21 | G07 legacy crossbeam intrudes into deck/panel regions |
| `RC-H10-E` | V14-22..26 | G08 crossbeam-to-primary laps lack a named, qualified interface |
| `RC-H10-F` | V14-27..28 | G08 legacy crossbeam intrudes into deck/panel regions |

Common-cause grouping is planning credit only. It cannot close any individual
row.

## Per-row evidence required

Every inherited row must retain:

- parent row ID, classification, source solids, and legacy AABB value;
- selected configuration and both old occurrence paths;
- root-cause cluster and responsible R1 part;
- explicit geometry action;
- pre-change exact common volume and minimum/signed distance;
- post-change exact common volume and minimum/signed distance;
- before/after local images with the same camera, section, and labels;
- replacement occurrence and part SHA-256;
- named datum/contact-face references;
- closure status, reviewer, and authorization.

For `UNACCEPTABLE_COLLISION`, closure requires zero post-change exact common
volume plus an authorized positive-clearance threshold. That threshold is
currently `UNKNOWN`; it must not be invented.

For `INTENDED_BOLTED_LAP`, closure requires zero unintended common volume,
source-bound mating faces, qualified contact area and edge margin, and a named
fastener/bond/load-transfer definition. Zero distance and zero common volume
alone provide no attachment credit.

Obsolete V2.2 mount/support occurrences must be explicitly suppressed,
excluded, or mapped to a replacement. In particular, the reported
`9680.832 mm3` G08-to-obsolete-support overlap cannot be silently counted
either as an R1 collision or as a cleared replacement.

## Exit condition

`H10_28_OF_28_CLOSED` is permitted only after all 28 rows have complete,
hash-bound before/after evidence and no `UNKNOWN`, `TBD`, `OPEN`, or
unauthorized clearance threshold in a closure-critical field. Until then:

`H10 = HOLD_28_ROWS_OPEN / G2 = FAIL_GEOMETRY_REDESIGN_REQUIRED`

