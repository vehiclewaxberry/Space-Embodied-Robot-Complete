# Sim13 V2 prebind receipt V1

- Date: 2026-08-24
- Validation: `30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/evidence/SIM13_V2_PREBIND_VALIDATION_V1.json` / `803388161591A67292283F374DE068D39722D89E964A77DDE1F011E3D5567DA6`
- Gate: `30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json` / `DBFFF803A656F4AD74934F0C886BC258E219CDC6904647D2855F15D2C3916906`
- Source manifest: `30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/evidence/SIM13_V2_PREBIND_SOURCE_SHA256_V1.csv` / `5EA4E337AAA21B2C4ED0CC5F0CBF2391F6BD2AC50CFC9FFF54640EE1869C2451`
- Negative-control evidence: `30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/evidence/SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1.json` / `C9DAEC35A677B945C09C1BD8D4EEB6401E04EB92D11473BBC68F4D0DFE4E243F`
- Unit tests: 62 passed
- Current runtime gates: PASS=0, FAIL=3, UNKNOWN=9
- Formal NC01--NC20 execution credit: 15/20 PASS, 5/20 dependency HOLD, 0/20 FAIL
- Dependency HOLD IDs: NC15, NC16, NC18, NC19, NC20
- Historical sim05/sim06/sim10 anchors: hash-pinned and verified; not inherited as Unified R2 PASS
- Current sim05/sim06/sim10 re-execution: HOLD_INPUT_PATH_OR_HASH_DRIFT
- Current ideal hard-lock calculation: momentum-limit diagnostic only; no contact force/time history
- Operational state: ABORT only; source-only analytic diagnostics
- URDF/interface emitted: no/no
- `next_stage_authorized`: false

This receipt records implementation readiness only. It is not Owner acceptance,
mechanical binding, contact authority, production dynamics release, training
authority, hardware-motion authority, or flight qualification.
