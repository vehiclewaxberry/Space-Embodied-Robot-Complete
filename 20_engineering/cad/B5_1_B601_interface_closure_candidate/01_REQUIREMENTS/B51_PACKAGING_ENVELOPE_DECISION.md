# B5.1 H9 packaging mode decision

Status: `HUMAN_DECISION_REQUIRED`

The 25 degree base clock is ratified only as:

`RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY`

It is a fixed spacecraft-to-arm installation transform. It is not part of
joint1 zero and is not a flight-interface release.

## Evidence-bound benefit

- 0 degree family minimum max Z: 520.83 mm.
- 25 degree family minimum max Z: 365.65 mm.
- delivered STOW v2 conservative mesh max Z: 368.62 mm.
- delivered STOW STEP max Z: 361.34 mm.
- max absolute Y: 104.24 mm against the current 113.15 mm half-width
  condition; margin 8.91 mm.
- max X: 412.45 mm by mesh and 412.47 mm by STEP against the current
  430 mm engineering condition.
- joint1 remaining limit margin: 15.86 degrees.

The clocking benefit is approximately 155 mm of height reduction and removal
of joint1 saturation. It is not evidence that clocking is required to satisfy
the X/Y conditions.

## Mode A: `MODE_A_12U_DEPLOYER_COMPLIANT`

The current core structural-box proxy is 366 x 226.3 x 228.3 mm with
Z=[-113.15,115.15] mm. The delivered B601 STEP top exceeds that box top by
246.19 mm; the conservative mesh exceeds it by 253.47 mm.

Provisional result:

`ARCHITECTURE_NOT_PACKAGING_COMPLIANT_AGAINST_CURRENT_CORE_BOX_PROXY`

This is not a formal deployer verdict because no launcher/deployer ICD is
bound. The historic 238.3 > 226.3 mm and 302.3 > 226.3 mm solar negative
findings remain active.

## Mode B: `MODE_B_12U_CLASS_BUS_EXTERNAL_SERVICE_MODULE`

The current two-file STEP union is only a provisional envelope:

- X=[-213.00,412.47] mm
- Y=[-113.15,113.15] mm
- Z=[-115.00,361.34] mm
- size=625.47 x 226.30 x 476.34 mm
- conservative-mesh total height=483.62 mm

This union does not yet include every solar-wing negative envelope, launcher
interface, harness sweep, tolerance, or dynamic clearance. It is not the final
flight-vehicle envelope.

## Decision gate

Until an authorized human selects Mode A or Mode B and binds the applicable
launcher/deployer ICD, H9 remains HOLD. Mode B is the recommended engineering
continuation, not an automatically approved architecture.

Source hashes:

- adapter clocking: `71A646543F6E4FF9B86C7BBBAA97A29DA37F5BFD8E1080C1A22977C0F82E2E1A`
- STOW v2: `90625CB31D7017AAF195B01902AAD0C783CB000D92BB19DFAA23962C73C08A1B`
- STOW family: `B27ACBBDA095D2E4DDA826ACF45CCEE92B0A855E766C6AA1493AB6F2FC595FB3`
