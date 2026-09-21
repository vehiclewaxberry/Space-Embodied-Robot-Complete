# B601-SWAP-01 execution report

Machine verdict: B601_SWAP01_HOLD  
Subcode: HOLD_NO_FURTHER_IDENTICAL_RETRY

## Outcome

No B601_STOWED_HIFI.SLDPRT and no staging top assembly were created. The canonical V2.2 top assembly, ASSET-00 scratch assembly, accepted URDF/STL package, V2.0 terminal set, existing q0 proxy, and ASSET-00 evidence remain outside the write path.

## What passed

| Gate | Result | Evidence |
|---|---|---|
| Registered STEP hash | PASS | input_hashes.json |
| ASSET-00 scratch hash | PASS | input_hashes.json |
| Accepted URDF authority | PASS | input_hashes.json |
| Read-only exact STEP recovery | PASS, 358/358 components, zero unresolved/boxless | registered_step_recovery_probe.json |
| Save preference round trip | PASS and restored | mass_exclusion_check.json |
| V2.0 terminal manifest | 57/57 PASS | frozen_zone_recheck.json |
| Accepted B601 package | 12/12 PASS | frozen_zone_recheck.json |
| Canonical V2.2 top hash | PASS unchanged | frozen_zone_recheck.json |

## Why the build is on HOLD

The preserved ASSET-00 scratch SLDASM is not self-contained: it contains eight top components that point to missing spiop temporary assemblies, and all eight are boxless in the read-only probe. Re-importing the exact registered STEP is recoverable and has passed read-only inspection, but it is a recovery path rather than the literal scratch-only path.

The final controlled single-instance headless LoadFile4 call did not return within the declared ten-minute observation window. The Python controller was blocked, SolidWorks remained nominally responsive with near-idle CPU, and no STEP_LOADED_IN_MEMORY event or CAD output appeared. The execution was terminated at the observation limit. Windows supplied no new SolidWorks Application Error, WER report, crash dump, or application-hang record, so this is recorded as a headless COM no-return condition rather than a proven importer crash.

## Gates not run

- Multibody SaveAs3 and body-folder readback
- Split InsertMoveCopyBody2 rotation and translation bake
- Close, restart SolidWorks, and reopen persistence verification
- Identity top-level insertion
- Eight-configuration suppression round trip
- Envelope/BOM/mass-exclusion readback and before/after mass comparison
- Generated-part and staging-assembly dependency closure
- Final raw and annotated integration views

No screenshot or API True return was substituted for these missing gates.

## Configuration intent, not applied

STOWED and SERVICE are planned to use the static high-fidelity folded representation while suppressing the q0 proxy. The other six states retain the controlled q0/task proxy while suppressing the high-fidelity folded representation. CAPTURE_SAFE remains a candidate/UNKNOWN claim and is not upgraded.

## Mass authority

The accepted arm_b601_v1 URDF remains the sole authority for joints, mass, center of mass, and inertia. The STEP remains geometry-only. Because no high-fidelity component was inserted, this run introduced no duplicate mass, but artifact-level exclusion was not verified and therefore is not marked PASS.

## Frozen-zone result

V2.0 and the accepted B601 package passed their pinned hash manifests. The ASSET-00 scratch and canonical V2.2 top match their pre-run hashes. The ASSET-00 evidence tree and q0 directory have current tree snapshots but no independent pre-run seal, so zero-change remains UNKNOWN. V2.1 content re-hashing was blocked by the existing access-control seal and is reported as an access limitation, not silently treated as a content PASS.

## Required next gate

Do not repeat the identical headless call. A materially different attempt requires:

1. explicit human acceptance that exact registered STEP recovery is allowed because the preserved scratch is incomplete;
2. one visible SolidWorks instance with modal-window diagnosis and explicit PID binding;
3. sufficient physical and commit headroom;
4. pre/post LoadFile4 events plus an independent timeout witness;
5. the full persistence, identity-transform, mass-exclusion, dependency, configuration, and view gates in this evidence directory.

FIDELITY-01 remains blocked.
