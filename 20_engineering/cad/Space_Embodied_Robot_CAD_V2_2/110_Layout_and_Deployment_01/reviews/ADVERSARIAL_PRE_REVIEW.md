# V22-LAYOUT-AND-DEPLOYMENT-01 adversarial pre-review

Review role: independent hostile reviewer  
Review scope: new isolated `110_Layout_and_Deployment_01/solar/` and
`110_Layout_and_Deployment_01/arm_stow/` artifacts only  
Baseline authority: user decision text plus the read-only
`100_Mechanical_Continuation` interface and configuration registries  
Initial disposition: `HOLD_PENDING_ARTIFACT_INSPECTION`

## Fail-closed rules

1. Geometry presence is not clearance, motion, load-path, strength, release,
   tolerance, manufacturability, reliability, configuration, BOM, or mass proof.
2. A finite set of deployment poses is not a continuous swept-volume proof.
3. A visually touching solid is not a joint or a structural load path.
4. A static STEP label is not a native SolidWorks mate, suppression state, or
   configuration readback.
5. The accepted B601 URDF remains the only kinematic and mass authority. Any
   arm envelope or pose geometry generated here is a design proposal unless
   its transform is derived from and traced to that accepted URDF.
6. `PARTIAL` remains angle `UNKNOWN`; the sampled 5/15/30/60 degree poses are
   validation samples, not a definition of `PARTIAL`.
7. `SERVICE` remains pending human ratification. No sampled arm pose or static
   staging view may silently define it.

## Adversarial questions and counterexamples

| Topic | Counterexample that defeats a superficial PASS | Minimum evidence needed for anything above HOLD |
|---|---|---|
| Hinge axis | Two pin-shaped cylinders can be parallel to X but have different Y/Z centers or not share the panel-root kinematic axis. | Extracted axis vectors and centers for both sides and both hinge stations; coaxiality or explicit shared-axis construction. |
| Stowed containment | The panel face can be within `abs(Y)<=113.15` while a lug, pin, stop, HDRM, cassette lip, or fastener envelope remains outside. | Whole-subassembly bounds and per-component extrema, not panel-only bounds. |
| Cell-face orientation | Mirroring the same transform can leave one deployed cell normal at `-Z`, or leave cells outward in stow. | Signed face normals for left and right at 0 and 90 degrees. |
| Hinge torsional lever arm | Two hinge stations near the panel center can satisfy “dual hinge” while providing negligible X separation against a 227 mm panel. | Measured station separation and ratio to panel X span; the proposed 60–75% span is a design target, not qualified strength. |
| Cassette structural closure | A cassette may visually intersect MID2 or a lower longeron without a bracket, continuous material path, joint, or fastener interface. | Named continuous geometry path plus joint/fastener proposal; strength still remains HOLD without loads/analysis. |
| HDRM load path | HDRM rods can terminate on cosmetic side/back plates, leaving launch restraint outside the primary frame. | Each fixed-side restraint traced to a frame/longeron through named solids and proposed joint interfaces. |
| Sweep sampling | Collision can occur at 8 degrees or 47 degrees while all 0/5/15/30/60/90 samples are clear. | Continuous swept solid or bounded adaptive collision search; sampled-only work must retain HOLD for continuous clearance. |
| Arm crossbeams | A crossbeam can float, end short of the longerons, or merely overlap them without attachment geometry. | End-coordinate measurements against both upper longerons and explicit connection/bracket/interface labels. |
| Arm corridor | The declared central keepout can be clear while a camera, radiator, antenna, harness loop, saddle, or HDRM intrudes between sampled sections. | Intersection checks against every physical device/envelope at the same configuration; unknown B601 LOD1 still limits contact and released motion claims. |
| q0 / pose authority | A visually plausible proxy can be placed by hand and then described as q0. | URDF hash, named joints, exact joint values, and a reproducible forward-kinematics transform chain. |
| Mass/configuration | STEP volumes or labels can be totaled or toggled and presented as authoritative vehicle mass/configuration. | Native configuration and property readback for configuration claims; mass must remain excluded except accepted URDF authority. |
| Deployed tip | Moving the hinge inboard can preserve a nominal `313.15 mm` number only by changing panel radial length, introducing a root offset, or allowing a gap/overlap. | Coordinate equation and measured root/tip frames at 90 degrees for both wings. |

## Preliminary gate posture

| Gate | Preliminary status | Reason |
|---|---:|---|
| `SOLAR-LAYOUT-TRADE-01` | `REVISE` | The recessed lower-book concept is promising, but it must preserve the prior negative external-hanging result and not promote target dimensions to qualified interfaces. |
| `SOLAR-CASSETTE-01` | `HOLD` | Structural closure to MID2/lower longerons and HDRM reaction paths require artifact evidence. |
| `SOLAR-KINEMATIC-01` | `HOLD` | Discrete poses alone cannot prove continuous clearance or release reliability. |
| `ARM-STOW-LAYOUT-02` | `HOLD` | Crossbeam connectivity, device-corridor intersections, arm pose authority, and support-contact authority require artifact evidence. |
| `ARM-SOLAR-CLEARANCE-01` | `HOLD` | B601 LOD1, PRE_CAPTURE, and SERVICE authority are not presently available. |
| `LAYOUT-STAGING-ASSEMBLY-01` | `HOLD` | Static STEP can stage geometry but cannot prove seven native configurations, mass exclusion, or BOM semantics. |

This pre-review intentionally does not accept the design from screenshots or
file presence. Final gate status will follow direct inspection of the generated
source, STEP facts, validation JSON, and snapshots.
