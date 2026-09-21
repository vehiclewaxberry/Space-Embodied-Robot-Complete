# V22 mechanical continuation independent validation

- Overall status: `HOLD`
- Machine verdict: `B601_RECOVERY02_HOLD_PLATFORM_MECHANICAL_CONTINUES`
- Validated UTC: `2026-07-26T12:56:12.173404+00:00`
- Scope: isolated STEP continuation only; canonical V2.2 top remained read-only.
- Gate counts: PASS=16, HOLD=6, FAIL=0, NOT_APPLICABLE=2.

## Gate results

| Gate | Status | Evidence-backed conclusion |
|---|---:|---|
| `REQUIRED_VALIDATION_INPUTS_PRESENT` | **PASS** | All independent validation inputs are present. |
| `PHASE_A_BASELINES_AND_FROZEN_ZONES_UNCHANGED` | **PASS** | All six captured source sets and their indexed manifests match Phase A. |
| `CANONICAL_V22_TOP_NO_WRITE` | **PASS** | Canonical top content, size, and mtime match Phase A; staging declares no write. |
| `ACCEPTED_URDF_MASS_AUTHORITY_UNCHANGED` | **PASS** | Accepted URDF hash matches and inertial masses sum exactly to 4.6955559493429862 kg. |
| `REGISTERED_VENDOR_STEP_UNCHANGED` | **PASS** | Exact registered vendor STEP still matches its captured SHA-256 and byte count. |
| `GENERATED_VISUAL_MASS_AUTHORITY_EXCLUDED` | **PASS** | Visual continuation and future B601 HIFI both exclude mass authority. |
| `CONFIGURATION_POLICY_SERVICE_PENDING_CAPTURE_SAFE_UNKNOWN` | **PASS** | SERVICE remains pending human ratification and CAPTURE_SAFE remains an unknown candidate. |
| `STEP_INDEPENDENT_REOPEN_VALID_SOLIDS` | **PASS** | Fresh isolated Python/OCP process reopened a valid positive-volume STEP compound. |
| `STEP_REQUIRED_MODULE_AND_INTERFACE_LABELS` | **PASS** | All required module/interface labels survived STEP export and reopen. |
| `STEP_BOUNDING_BOX_PLAUSIBLE_MM` | **PASS** | Millimetre-scale bounds are finite and plausible for the staged vehicle. |
| `B601_ICD_160X160X12_AND_D100_SUBSTANTIATED` | **PASS** | AST constants, interface registry, STEP plate bounds, and its X-axis cylindrical face independently substantiate the frozen ICD. |
| `B601_MOUNT_FOUR_WAY_WEB_GEOMETRY` | **PASS** | Four staging webs occupy X=171..183 mm and bridge the ±80 mm plate edges to the ±98.15 mm task-frame inner boundary. |
| `SOLAR_ROOT_NODE_SPINES_GEOMETRY_PRESENT` | **PASS** | Both staging-only node spines match the registered proposal envelopes. |
| `C5_NEGATIVE_RELATION_GEOMETRICALLY_PRESERVED` | **PASS** | Panel package remains 238.3 mm > 226.3 mm (12.0 mm over); solar-root mechanism lower-bound geometry remains 302.3 mm. |
| `STEP_SELF_CONTAINED_DEPENDENCY_CLOSURE` | **PASS** | The STEP reopened from an empty temporary working directory and contains no external-reference entities. |
| `PHASE_B_VISIBLE_RECOVERY_RESOURCE_GATE` | **HOLD** | Visible recovery remains deferred because one or more project-conservative resource thresholds are not met. |
| `B601_FULL_HIFI_358_COMPONENT_RECOVERY` | **HOLD** | Registered geometry is unchanged but no full 358-component HIFI recovery is claimed. |
| `SOLAR_ROOT_ENGINEERING_CLOSURE` | **HOLD** | Root geometry is present, but joints, loads, deployment clearance, and reliability remain unqualified. |
| `C5_PACKAGE_CLOSURE` | **HOLD** | The preserved 238.3 > 226.3 mm result is negative; no package closure is claimed. |
| `SOLIDWORKS_CONFIGURATION_READBACK` | **NOT_APPLICABLE** | Static STEP contains no native SolidWorks configuration/suppression semantics. |
| `SOLIDWORKS_BOM_AND_MASS_EXCLUSION_READBACK` | **NOT_APPLICABLE** | Static STEP cannot establish native BOM or property readback. |
| `STRUCTURAL_STRENGTH_AND_STIFFNESS_QUALIFICATION` | **HOLD** | No FEA, launch-load case, stiffness, or fatigue analysis was performed. |
| `MANUFACTURING_TOLERANCE_AND_RELEASE_QUALIFICATION` | **HOLD** | No manufacturing, tolerance, fastener, HDRM, or release qualification was performed. |
| `PHASE_A_EIGHT_JSONS_UNTOUCHED_BY_VALIDATOR` | **PASS** | All eight Phase-A JSON fingerprints are identical before and after validation reads. |

## Independent geometry facts

- STEP: `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\Space_Embodied_Robot_CAD_V2_2\100_Mechanical_Continuation\v22_mechanical_continuation.step`, SHA-256 `c844c07177daf7e7b96d332d5060cfcbffe2c5989ded04602f9ec0dffd7c4b42`, 122 positive-volume solids.
- Reopened bounds (mm): min `[-213.00000000000207, -151.15, -200.0]`, max `[580.0, 151.15, 140.0]`, size `[793.000000000002, 302.3, 340.0]`.
- Frozen B601 interface is supported by source constants, the interface registry, a 12×160×160 mm STEP plate bound, and an X-axis cylindrical face of radius 50 mm.
- C5 stays negative: panel package 238.3 mm exceeds the 226.3 mm bus width by 12.0 mm; root-mechanism lower-bound geometry is 302.3 mm wide.

## Phase-B visible-recovery resource gate

- Verdict: `DEFERRED_RESOURCE_GATE`. Available physical memory 2.254 GiB (threshold 4 GiB); commit headroom 3.273 GiB (threshold 8 GiB).
- Threshold authority: `PROJECT_CONSERVATIVE_RECOMMENDATION_NOT_VENDOR_SPEC`.
- Read-only capture only: no SolidWorks/sldProcMon process was started or stopped.

## Claim boundary

- `B601_FULL_HIFI_358_COMPONENT_ROUTE` remains HOLD; the registered vendor STEP is unchanged and is not embedded here.
- The accepted URDF remains the only kinematic/mass authority; the staged visual continuation declares mass authority excluded.
- SolidWorks configuration/BOM readback is NOT_APPLICABLE to this static STEP and was not claimed.
- Strength, stiffness, launch-load, release reliability, manufacturability, and tolerance qualification were not run and remain HOLD.
- `SOLAR-ROOT-01` engineering closure and `C5-PACKAGE-01` closure remain HOLD despite their geometry-presence checks passing.
