# ODR60 Option A — M01 rigid-kinematic motion-certificate batch V1

## Engineering ruling

This is an append-only, fail-closed package. It does **not** modify or reissue the parent M01 Gate, the accepted B601 URDF, the collision registry, any scene instance, or the earlier `A::base_link` certificate.

The frozen evidence supports the following maximum claim:

- the current registry contains 150 unique active objects;
- collision-frame registrations exist for the 10 `A::` B601 objects;
- only `A::base_link` has an operational collision asset, and that object already has a separate append-only zero-motion certificate;
- the remaining nine `A::` objects have frame-bound **design-screening** surfaces, but `operational_narrowphase_promoted=false` and `runtime_object_pose_bound=false`;
- therefore this batch derives nine conservative full-accepted-q-domain **candidate** coefficient vectors and emits **zero** new system motion certificates.

The parent contract snapshot remains 0/150. The previously issued append-only `A::base_link` certificate is observed, not reissued, so the effective observed append-only total remains 1/150. Scene values remain 0/30, stage instances 0/3, clearance-policy rows and pair queries 0/11166, edges 0, and path/next-stage/release authorities remain false.

## Conservative bound

For a design-screening surface rigidly registered to a B601 link, the package parses every binary PLY vertex and computes its maximum link-frame radius. For a revolute ancestor joint `k`, it uses

```text
L_candidate[k] = ceil_1e-9_mm(
    full_locus_surface_radius
    + sum(norm(downstream URDF joint-origin translations))
)
```

The finger full-locus radius additionally includes the complete schema type-domain travel envelope, 0–0.0715 m. No Owner-selected finger value is consumed. The triangle inequality and revolute arc-length inequality make the coefficient conservative over the full accepted six-joint box. It is intentionally looser than a configuration-dependent Jacobian bound.

The builder and the standalone validator now also prove two spatial preconditions directly from the frozen sources. All 10 current `A::` collision registrations must be finite legal SE(3) records and, for this link-local design asset set, must be exact identity registrations (`accepted_urdf_registration_frame == asset_storage_frame`, identity rotation, zero translation in metres). For both fingers, the prismatic axis is parsed from the accepted URDF, required finite and unit length, rotated from the joint frame into `gripper_link`, and compared with the registered parent-frame direction. The 0–0.0715 m limits are independently parsed from the URDF and must exactly equal the registered domain; the resulting 0.0715 m full-travel envelope is added to the link-frame asset radius exactly once. Transform, axis norm, axis direction, and limit mutations are mandatory fail-closed controls.

These coefficients bind only the selected M5 design-screening surface sets. They are not `OBJECT_MOTION_BOUND_CERTIFICATE_V1` records and may not be loaded by the system edge oracle. Operational collision-asset promotion, runtime pose binding, separate independent issuance, pair derates, and pair queries remain mandatory.

## Artifacts

- `M01_RIGID_KINEMATIC_MOTION_ELIGIBILITY_MATRIX_V1.csv`: 150-row object-by-object eligibility and blocker matrix.
- `A_B601_RIGID_KINEMATIC_CANDIDATE_BOUNDS_V1.json`: nine candidate vectors with asset/frame/q/scene-type input bindings.
- `M01_RIGID_KINEMATIC_SYSTEM_CERTIFICATE_BATCH_V1.json`: deliberately empty system-certificate batch.
- `INDEPENDENT_RIGID_KINEMATIC_RECOMPUTE_V1.json`: standalone reparse/recompute and mutation-control receipt.
- `M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_GATE_V1.json`: append-only machine Gate.
- `M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_PACKAGE_SHA256_V1.csv`: exact, unique, no-extra payload manifest.
- `STANDALONE_RELEASE_VALIDATION_RECEIPT_V1.json`: non-authoritative runtime validation receipt; explicitly self-excluded to avoid a circular manifest hash.

The standalone validator owns a separate frozen source ledger and does not import or execute the builder. It independently parses the URDF, PLY files, registry, readiness CSV, collision registrations, scene schema, prior certificate, Gate and manifest. JSON duplicate keys and NaN/Inf are rejected, numeric booleans are rejected, all nine vectors are exactly recomputed, and mutation controls must reject every authority/count/hash/numeric escape.

## Rebuild and verify

Run from the project root:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_V1/build_m01_rigid_kinematic_motion_cert_batch.py
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_V1/validate_m01_rigid_kinematic_motion_cert_batch.py --release
python -B -m pytest -q -p no:cacheprovider --basetemp "$env:TEMP/m01_rigid_kinematic_motion_cert_batch_pytest" 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_V1/test_m01_rigid_kinematic_motion_cert_batch.py
```

Any frozen-source drift, extra package file/directory, manifest mismatch, geometry mutation, coefficient reduction, authority escalation, boolean-as-number substitution, or non-finite JSON value fails closed.
