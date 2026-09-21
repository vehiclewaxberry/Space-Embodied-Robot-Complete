# V22 Solar Gate 1–3 Validation Report

## Post-adversarial revision notice

The current generator supports independent left/right angles and the repaired
moving ears, doublers and HDRM reservations. The hashes below and
`validation/validation_summary.json` supersede the original export hashes.
This remains a solar-subsystem report; the combined Gate 2 cassette
disposition is governed by the final layout report and remains structural and
internal-volume HOLD.

## Verdict

```text
SOLAR-LAYOUT-TRADE-01 = PASS_BASELINE_SELECTED_WITH_HOLDS
SOLAR-CASSETTE-01 = PASS_GEOMETRY_AND_LOAD_PATH_REFERENCE_ONLY
SOLAR-KINEMATIC-01 = PASS_DISCRETE_SAMPLES_WITH_HOLDS
COMBINED = PASS_GEOMETRY_AND_DISCRETE_KINEMATIC_DIAGNOSTIC_WITH_HOLDS
CAD_CLI_CHECKS = 26 PASS / 0 FAIL
PARTIAL_STATE_ANGLE = UNKNOWN
```

This verdict authorises an isolated layout baseline for later arm–solar
clearance work. It does not release a flight solar-array mechanism.

## Gate 1 ruling

- Baseline: `RECESSED_LOWER_BOOK_FOLD`.
- Rejected for packaging: `CURRENT_EXTERNAL_HANGING`.
- Growth option only: `TWO_PANEL_Z_FOLD`.
- The adversarial rationale is recorded in
  `SOLAR_LAYOUT_ADVERSARIAL_TRADE_01.md`.

## Generated STEP set

| Artifact | SHA-256 |
|---|---|
| `solar_deployment_pose_000deg.step` | `eeb4de592547c8cc0f5d11ae73a48cde29269f25c4ab4ac2c13d7b0763433a64` |
| `solar_deployment_pose_005deg.step` | `4fff551ed47e38761db970205b576a8edab82694569ec7b5248b486a4c710201` |
| `solar_deployment_pose_015deg.step` | `ef42f34c055ddfe4b0acd8c66e7c60ff5c1b84b22e93cf74b70f1e738d8dbae9` |
| `solar_deployment_pose_030deg.step` | `a394337465d45d38929106933b1e9747f5bfde441fe5c1d830790b6e51c2a5de` |
| `solar_deployment_pose_060deg.step` | `cc5c75141182447d1c95053186e4712c0b9bb7aecd36005ea5f6a7c49de36829` |
| `solar_deployment_pose_090deg.step` | `4dc87fd88cced03b19a7836b734a3159bfdd4fa59e3b2b0728c49fd0d9255299` |
| `solar_deployment_sweep_samples.step` | `23610932784a48cc5b7f5edc724209eb36433ccca91772efa52f82a84473be3b` |

Each pose STEP contains:

- 67 occurrences;
- 61 leaf occurrences;
- 65 shapes;
- 378 faces;
- 744 edges.

The labelled multi-pose diagnostic contains:

- 197 occurrences;
- 181 leaf occurrences;
- 205 shapes;
- 1218 faces;
- 2424 edges.

## Baseline refs/facts/planes/positioning

The installed CAD inspection tool reopened all seven STEP files with
`refs --facts --planes --positioning`.

| Sample | Overall world bounds, mm |
|---|---|
| 0° | `[-183,-113.15,-113.15] .. [183,113.15,113.15]` |
| 5° | `[-183,-130.419733,-113.15] .. [183,130.419733,113.15]` |
| 15° | `[-183,-164.661586,-113.15] .. [183,164.661586,113.15]` |
| 30° | `[-183,-212.598076,-113.15] .. [183,212.598076,113.15]` |
| 60° | `[-183,-284.705081,-113.15] .. [183,284.705081,113.15]` |
| 90° | `[-183,-310,-113.15] .. [183,310,113.15]` |
| all samples | `[-183,-310,-113.15] .. [183,310,113.15]` |

The 0° overall Y width is exactly `226.3 mm`; the transparent platform-side
limit witnesses terminate at `Y=±113.15`.

## Targeted measurements

| Check | Selector relationship | Expected | Observed |
|---|---|---:|---:|
| Panel X span at 0° | `#o1.4.1.f1 → #o1.4.1.f2`, X | 227 | 227 |
| Panel thickness at 0° | `#o1.4.1.f3 → #o1.4.1.f4`, Y | 6 | 6 |
| Panel height at 0° | `#o1.4.1.f5 → #o1.4.1.f6`, Z | 200 | 200 |
| Hinge-station separation | `#o1.2.9 → #o1.2.13`, X | 149.82 | 149.82 |
| Panel radial length at 90° | `#o1.4.1.f5 → #o1.4.1.f6`, Y | 200 | 200 |
| Panel X span at 90° | `#o1.4.1.f1 → #o1.4.1.f2`, X | 227 | 227 |

The hinge-station separation is `66%` of panel X length and remains
`DESIGN_PROPOSAL_ONLY`.

## Targeted frames

- Stowed left/right panel outer faces:
  `Y=+113.0/-113.0`, normals `+Y/-Y`.
- Stowed cell faces:
  left normal `-Y`, right normal `+Y`.
- Left hinge-pin proposal `#o1.2.9`:
  centre `[-135.91,110,-105.65]`,
  bbox `26×6×6`, longest axis X.
- Left panel root face centre remained
  `[-61,110,-105.65]` at 0°, 30°, and 90°.
- Right panel root face centre at 90°:
  `[-61,-110,-105.65]`.
- 90° tip faces:
  left `Y=+310`, right `Y=-310`.
- 90° cell-face normals:
  both `+Z`, exposed-face coordinate `Z=-102.25`.

These frame checks close the visible pivot-drift and sign-convention questions
for the sampled rigid-body model only.

## Explicit 313.15 mm incompatibility

```text
hinge axis |Y| = 110.0 mm
panel radial length = 200.0 mm
actual 90-degree tip |Y| = 310.0 mm
legacy target |Y| = 313.15 mm
delta = -3.15 mm
status = HOLD_INTERFACE_RATIFICATION
```

The model does not hide this delta. Preserving 313.15 mm requires an
out-of-range hinge axis, a 3.15 mm offset mechanism, or a longer panel.

## Snapshot review

Twelve saved snapshots were reviewed:

- one isometric image for every discrete pose;
- front views of 0° and 90°;
- a 90° top view;
- isometric, top, and front views of the multi-pose diagnostic.

Observed:

- the two sides form a monotonic book-deployment sequence;
- both moving groups remain attached to their root in each sample;
- the 90° top view exposes both cell-face witnesses upward;
- the fan diagnostic shows no visible root drift or side-sign reversal.

The pivot finding was converted into deterministic frame checks at
0°/30°/90°. Snapshot details are in `validation/snapshot_review.json`.

The installed snapshot runtime initially pointed to a missing managed Chromium
binary. `validation/run_snapshot_with_system_chrome.py` reused the already
installed system Chrome without installing software or modifying the CAD
skill.

The governing post-repair sweep image is
`../snapshots/solar_sweep_repaired_iso_20260726T142704Z.png`.

## Viewer handoff

The installed `cad-viewer` skill was invoked. Its documented
`npm run agent:start` entry is absent from the bundled runtime package
(`package.json` provides only `start`/`serve`), so the already-running
package-provided `serve` runtime was used. HTTP directory activation and the
catalog response were both verified before handoff.

## Remaining HOLD/UNKNOWN

- `PARTIAL` angle remains `UNKNOWN`; samples do not redefine it.
- Continuous between-sample collision clearance is not established.
- Recessed-cassette internal bus-volume compatibility is not established.
- B601/arm–solar clearance is not evaluated in this isolated subtask.
- Hinge pin, lug, stop, spring, bearing, HDRM, latch, harness, tolerance, and
  material selections remain unknown or proposal-only.
- No strength, stiffness, mode, shock, release reliability, thermal,
  electrical, manufacturing, or flight-qualification claim is made.
- No purchased component and no native SolidWorks configuration was created.
