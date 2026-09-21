# B5.1 current status

Generated UTC: `2026-07-28T12:18:16.359053+00:00`

Final verdict: `B51_REVISE_INTERFACE_COLLISION`

## 已读取真值

- canonical V2.2/B5.0 input lock and native cold-reopen containment;
- accepted URDF mass `4.6955559493429862 kg` and 6R+1 fixed+2P joint contract;
- canonical H10 exact-BREP audit and the 28-row disposition ledger;
- articulation evidence selected from `07_VERIFICATION/articulation/B51_SEGMENT_CHAIN_6R_20260728T005.json`, `07_VERIFICATION/articulation/B51_SEGMENT_CHAIN_6R_20260728T003.json`, `07_VERIFICATION/articulation/B51_SEGMENT_CHAIN_6R_20260728T004_ABORTED.json`, `07_VERIFICATION/articulation/B51_T003_OFF_AXIS_STATE_DIAGNOSTIC.json`.

## 创建资产

- `03_ARTICULATION/B51_CAD_URDF_KINEMATIC_CONSISTENCY.json`
- `03_ARTICULATION/B51_JOINT_MATE_REGISTER.csv`
- `03_ARTICULATION/B51_RANDOM_POSE_VERIFICATION.csv`
- `07_VERIFICATION/B51_GATE.json`
- `08_DELIVERY/B51_DELIVERY_GAP_REGISTER.md`
- `B51_CURRENT_STATUS.md`

## 发现问题

- G2 remains a controlling failure: all 28 H10 rows are open and 8 are
  classified `UNACCEPTABLE_COLLISION`.
- The B5.1 longeron datum differs from the canonical datum by
  `4.0 mm`; both saddle
  candidates remain `3.0 mm`
  from canonical primary structure.
- T005 reached its first random pose but failed after mate rebuild. The separate
  T003 read-only state diagnostic records 10/10 legal directions, 2/2
  illegal-limit rejections and 6/6 off-axis rejections; only document reopen
  recovered post-rebuild FK, and that result is diagnostic only. No accepted
  full 6R run is available, and 2P/native limit mates also remain HOLD.
- Continuous clearance and structural preliminary analyses remain not run.

## Gate

- G0: `PASS`
- G1: `HOLD_HUMAN_DECISION_REQUIRED`
- G2: `FAIL_GEOMETRY_REDESIGN_REQUIRED`
- G3: `HOLD_NO_ACCEPTED_6R_RUN_2P_AND_NATIVE_LIMIT_MATES_MISSING`
- G4: `HOLD_PHYSICAL_RESTRAINT_AND_RELEASE_INTERFACE`
- G5: `HOLD_NOT_RUN`
- G6: `HOLD_NOT_RUN`
- G7: `HOLD_PARTIAL_DIGITAL_THREAD`

No `COMPLETE`, `FLIGHT_READY`, or `MANUFACTURING_READY` claim is authorized.

## 下一动作

Correct the canonical installation datum, rebuild the native adapter and
double-saddle interfaces, and close all 28 H10 records before continuous
clearance or structural analysis is admitted.
