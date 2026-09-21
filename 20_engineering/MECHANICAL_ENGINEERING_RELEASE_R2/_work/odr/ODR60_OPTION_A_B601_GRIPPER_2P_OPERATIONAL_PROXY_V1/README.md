# ODR60 Option A — B601 Gripper 2P Operational Proxy V1

This package qualifies three **local, STEP-first collision-geometry candidates** for the accepted B601 2P gripper:

- palm: direct, byte-identical R1 STEP in `gripper_link`;
- left finger: 24 frozen B50 solids re-expressed once in `gripper_left`;
- right finger: 24 frozen B50 solids re-expressed once in `gripper_right`.

The three containers reopen as `12 + 24 + 24 = 60` closed, valid, positive-volume solids. The native lineage remains 57 physical bodies because the R1 palm rail-slot cut split the nine palm bodies into twelve output solids. No body was fused, filled, enveloped, deleted, duplicated, or reconstructed from STL.

## Authority boundary

This is a local candidate package only. It does **not**:

- resolve the Owner named-configuration-to-2P-travel conflict;
- confirm that all 24 bodies assigned to each finger move as one prismatic object;
- reissue the 150-object M01 registry or bind any of the three candidates;
- execute a system pair query, certify an edge, run path search, or issue SAFE;
- validate contact, strength, manufacturing clearance, as-built geometry, hardware effort/rate, or release readiness.

The accepted URDF remains the frame, mass, inertia, axis, and numeric travel-domain truth. Its literal `±1.5708 rad` joint origins are preserved; they are not idealized to `±π/2`. STEP uses millimetres, runtime PLY/NPZ/STL uses metres, and the scale is applied once.

## Reproduction

Run each geometry build or replay in a fresh CPython process because OCCT STEP product/occurrence counters are process-global:

```powershell
python 02_builder/build_gripper_2p_operational_proxy.py --check
python 04_validation/verify_fresh_process_determinism.py --check
python 04_validation/run_negative_controls.py --check
python 04_validation/validate_gripper_2p_operational_proxy_independent.py --check
pytest -q 06_tests/test_gripper_2p_operational_proxy.py
python 04_validation/finalize_gripper_2p_operational_proxy.py --check
```

The local Gate is `05_results/LOCAL_CANDIDATE_GATE_V1.json`. Always read its system-authority counters and HOLD fields together with its local criteria.
