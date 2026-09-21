# M6 digital-prototype BOM scope and nonclaims V2 (candidate extension)

`DIGITAL_PROTOTYPE_BOM_V2_CANDIDATE.csv` is a **candidate-class extension** of
the M4 assembly completeness register `DIGITAL_PROTOTYPE_BOM_V1.csv`. V1
remains the released working register of the M4 scoped release and is not
modified, superseded, or promoted by this file. V2 is not a procurement,
manufacturing, flight, or launch BOM.

Every V1 non-claim is preserved verbatim in effect:

- Every material, mass, tolerance, finish, supplier, and fastener field
  remains `UNSPECIFIED_HOLD`, `UNASSIGNED`, `TBD`, or `NOT_APPLICABLE` unless
  an active authority exists. No such authority was created in M6.
- Geometry volume must not be converted into mass. No candidate density is
  treated as measurement.
- No supplier or vendor identity is inferred from a filename, model family
  name, standard designation (e.g. HM4-75), or visual appearance.
- Candidate rows are not release rows. `CANDIDATE_GEOMETRY_PENDING_WP1`,
  `PROTOTYPE_CANDIDATE`, and `NEW_CANDIDATE_ROW` mark candidate class only;
  they create no release, no margin, and no authority.

## Changes in this round (M6 WP6)

- **DP-007 load bridge**: `geometry_status` upgraded from `absent` to
  `CANDIDATE_GEOMETRY_PENDING_WP1`; candidate path points at the WP1
  load-bridge workspace. `HARD_HOLD` (structural load path discontinuity) is
  retained until the WP1 candidate becomes authority through the M6 gate.
  `geometry_source` stays `no authorized geometry`.
- **DP-009 gripper fingers**: `HARD_HOLD` retained; candidate path added
  pointing to the M5 link-local diagnostic finger surface meshes (left/right
  `.ply`). These are diagnostic link-local surfaces, not separated working
  B-reps.
- **DP-010 sensor package**: `HARD_HOLD` retained; no M5/M6 candidate asset
  exists, recorded as `NONE__NO_M5_OR_M6_CANDIDATE_ASSET` (no zero-fill, no
  invented path).
- **DP-011 arm HDRM**: `HARD_HOLD` retained; candidate path added pointing to
  the M5 load-case register row LC-007 (functional-envelope hold retained).
- **DP-012 fastener group (new candidate row)**: 4 x HM4-75 class, B601 to
  M3R Stage A, 64 x 64 mm square pattern (equivalent PCD 90.509642 mm),
  as-built screw end faces measured at x = 210.405 mm; fastener bodies are
  not modeled. `material=PROTOTYPE_CANDIDATE` (A286 candidate, referencing the
  pending WP4 library `wp4_materials/PROTOTYPE_MATERIAL_LIBRARY_V2_CANDIDATE.yaml`).
  Selection, grade, length, washer, thread engagement, preload, tool access,
  and margin of safety remain unknown.
- **DP-013 clocking dowel (new candidate row)**: 1 x asymmetric
  anti-misassembly dowel candidate carried from the M3R detailed-design
  candidate register (blind hole diameter 4.0 mm, depth 5.5 mm, local xy
  55.0/0.0 mm). Diameter, material, fit class, insertion and removal remain
  `HOLD`; the feature is not promoted.
- New columns: `candidate_asset_path`, `v2_row_disposition`. All V1 rows are
  carried verbatim (`CARRIED_FROM_V1`).

The release-blocking gaps from V1 remain release-blocking:

- The spacecraft-to-M3R load bridge has no authorized geometry, so the
  structural load path is not geometrically continuous.
- The installed B601 object is a frame/axis witness, not physical arm
  hardware.
- Gripper R1 includes the palm only; separated finger and contact geometry
  are absent.
- The camera candidate pose was rejected because it penetrates the installed
  M3R B-rep; no replacement pose is authorized.
- HDRM geometry is a nonphysical hidden skeleton with no frozen global
  transform.
- Target proxies are independent scenario assets with no frozen
  servicer-relative pose.

The BOM may be promoted only after each unresolved slot has a
source-controlled part definition, frame placement, material/mass authority,
interface and fastener definition, tolerance scheme, verification evidence,
and an explicit release disposition. Nothing in this V2 file satisfies any of
those promotion conditions.
