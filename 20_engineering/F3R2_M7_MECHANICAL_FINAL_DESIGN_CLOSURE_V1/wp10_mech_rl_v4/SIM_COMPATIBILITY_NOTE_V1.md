# SIM_COMPATIBILITY_NOTE_V1 — MECH_DYNAMICS_INTERFACE_V4 vs V3, simulator impact ruling

- schema: SIM_COMPATIBILITY_NOTE_V1
- generated_local: 2026-08-22T00:46:25+08:00
- author_wp: WP10_MECH_RL_V4
- decision: **No Sim13 / Sim14 / Sim15 file is modified by this work package, and none needs to be.**

## 1. What V4 is

`MECH_DYNAMICS_INTERFACE_V4.yaml` (this directory) is an additive M7
design-authority layer written in the V3 pattern. It binds, by contract path,
the M7 design products that V3 did not yet have: the WP2 nine-configuration
design mass model, the WP4 M3R joint stiffness candidate, the WP5 mechanism
design targets, and the WP7 FEA-1 operational evidence. All sibling bindings
are `PENDING_SIBLING_HASH` until those WPs land and `12_release` backfills
hashes.

## 2. V3 ↔ V4 differences

| Aspect | V3 (M5 handoff) | V4 (M7 layer) |
|---|---|---|
| schema string | `MECH_DYNAMICS_INTERFACE_V3` | `MECH_DYNAMICS_INTERFACE_V4` (new) |
| location | M5 `07_simulation_handoff/` (read-only baseline) | M7 `wp10_mech_rl_v4/` |
| units contract | m/rad/kg/kg*m^2/N/N*m/N*s/N*m*s | identical, inherited unchanged |
| configuration ids | C01..C09 | C01..C09, identity authority = M5 configuration contract (hash-pinned) |
| artifact hash set | 13 hash-bound artifacts, all `required: true` | unchanged; V4 adds no artifact to V3's set |
| mass model | diagnostic only, system properties HOLD | design mass model binding added (WP2 path, `PENDING_SIBLING_HASH`, DESIGN_MASS_MODEL) |
| frame authority | unresolved alias HOLD | ODR-01 chain pinned: T_SM=[185.25,0,0] mm + Ry(90°); 198.0/208.0/210.405 mm stations = geometric feature stack only |
| panel failure semantics | semantics HOLD | ODR-02 attached-stuck; jettison forbidden; failed panel mass/inertia stay in system model |
| joint stiffness | not present | 4×HM4-75 group candidate (WP4 path, `CANDIDATE_STIFFNESS`, `PENDING_SIBLING_HASH`) |
| mechanism parameters | not present | hinge moment / gripper force / HDRM preload (WP5 paths, `DESIGN_TARGET`, `PENDING_SIBLING_HASH`) |
| structural evidence | `structural_analysis: HOLD` | ODR-06 split: operational FEA authorized, FEA-1 evidence pointer (WP7 path, `PENDING_SIBLING_HASH`); launch-qualification FEA stays HOLD |
| acknowledgement | `I_ACKNOWLEDGE_M5_VALUES_ARE_DIAGNOSTIC_...` | new: `I_ACKNOWLEDGE_M7_V4_VALUES_ARE_DESIGN_AUTHORITY_NOT_FLIGHT_QUALIFICATION_OR_PRODUCTION_DYNAMICS` |
| physics-gated RL / production dynamics | HOLD | HOLD (unchanged) |

Explicit non-replacement declaration: V4 does **not** replace, mutate, re-pin,
or extend V3's hash-bound diagnostic domain. V3 remains the only interface
Sim15 loads.

## 3. Sim15 loader ruling: no change required, no change permitted

Evidence from `30_simulation/sim_15_m5_geometry_gated_grasping/`:

- `src/authority.py:23` pins `INTERFACE_SCHEMA = "MECH_DYNAMICS_INTERFACE_V3"`;
  a document with `schema: MECH_DYNAMICS_INTERFACE_V4` raises `AuthorityError`
  at the schema check (`load_authority`, line 466-467) — fail-closed by design.
- The loader also pins the exact artifact identifier tuple **and order**
  (lines 28-42), the unit contract dict (lines 43-52), the V3 acknowledgement
  string (lines 24-26), `zero_fill_forbidden: true`, and verifies every
  artifact's SHA-256 against the V3 file's declared values (lines 476-499).
- It further enforces release-gate invariants (`memory_gate_passed` must be
  False, `formal_fea_run_count` must be 0, lines 446-453).
- The V3 file path is hard-referenced in `tests/conftest.py:22` and
  `tools/generate_baseline.py:32`, both pointing into the M5 baseline tree.

Consequences:

1. Sim15 continues to bind V3 at the M5 path; V3 is a read-only baseline and
   stays bit-identical (sha256 `88AE8776…`), so Sim15's hash chain is intact.
2. V4 lives at a new path under a new schema string; any accidental attempt to
   feed V4 to Sim15 fails closed, which is the desired behavior.
3. Therefore the Sim15 loader needs **no** modification for V4, and this WP
   modifies **no** Sim15 file.

## 4. Sim14 / Sim13 rulings

- Sim14 (`sim_14_m4_digital_prototype_grasping/src/interface_loader.py:20`)
  pins `INTERFACE_SCHEMA_VERSION = "MECH_RL_INTERFACE_V2"` and requires the
  filename `MECH_RL_INTERFACE_V2.yaml` (lines 907-908). V4 is not a V2
  manifest and is not a drop-in for Sim14; Sim14 is untouched.
- Sim13 (`sim_13_physics_gated_embodied_grasping/src/mechanical_asset_loader.py:24`)
  pins `MECH_RL_INTERFACE_V1` with a filename pin (lines 528-529) and a
  production-interface environment gate. Wiring V4 into Sim13 production is
  **forbidden**; Sim13 production binding via V4 remains prohibited, matching
  V4's own `prohibitions` block.

## 5. Integration path forward

1. WP2/WP4/WP5/WP7 land their contract outputs; `12_release` backfills hashes
   into `M7_CROSS_WP_REFERENCE_RECONCILIATION_V1.json` and V4's
   `PENDING_SIBLING_HASH` entries are resolved at integration time.
2. Any future consumer of V4 (e.g., a Sim16 dynamics loader) must be a **new**
   component that pins `MECH_DYNAMICS_INTERFACE_V4`, the V4 acknowledgement,
   and the backfilled hashes. Retrofitting Sim13/14/15 is out of scope and
   forbidden by this note.
3. Even after backfill, V4 values are design authority only: no flight,
   launch, qualification, production contact dynamics, flexible-body, trained
   RL policy, or HIL/real-robot claims.

## source_register

- `20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/07_simulation_handoff/MECH_DYNAMICS_INTERFACE_V3.yaml` — sha256 `88AE877677BBCE40BE6324AC884B91E0DF8B7862EB9074AD1D001B54FD7F3F79`
- `20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/08_simulation_assets/MECH_RL_INTERFACE_V2.yaml` — sha256 `2A72F8B77220529B191BA6FE780924D2067195EC9CAF7A7EE5626A589B2E826F`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml` — sha256 `F5B1572C0CFCEC35C40F262A3D7386AFA91DEC09DA94FE31FD03F5C04956F8B6`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_EXECUTION_PLAN_V1.md` — sha256 `AD406ACA2AB12FDC794E8BBAB8B32AD33AB1ECE6FEE3BF332049DE3951D8C68B`
- `30_simulation/sim_15_m5_geometry_gated_grasping/src/authority.py` (read-only inspection; file not modified)
- `30_simulation/sim_14_m4_digital_prototype_grasping/src/interface_loader.py` (read-only inspection; file not modified)
- `30_simulation/sim_13_physics_gated_embodied_grasping/src/mechanical_asset_loader.py` (read-only inspection; file not modified)
