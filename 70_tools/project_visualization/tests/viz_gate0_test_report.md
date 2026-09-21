# VIZ-Gate 0 acceptance test report

- repo commit at run: `e473867`
- run time: 2026-07-14 23:33:08 (local)
- suite: 70_tools/project_visualization/tests (6 tests, no pytest)
- result: **6/6 PASS**

| test | result | wall [s] |
|---|---|---:|
| test_asset_units | PASS | 2.7 |
| test_scene_transforms | PASS | 0.1 |
| test_fk_render_alignment | PASS | 0.2 |
| test_replay_numeric_consistency | PASS | 0.0 |
| test_status_semantics | PASS | 0.5 |
| test_dashboard_contract | PASS | 0.5 |

## test_asset_units — PASS

- rows=45, all units fields non-empty
- usable_for_render consistent (35 usable rows, all exist on disk)
- 15 render meshes all declared in meters
- base_link.STL z_max=0.0826 m vs joint1 offset 0.0847 m -> ratio 0.976 (order 1, not 1000)
- link2.STL x_span=0.3210 m vs joint3 offset 0.2640 m -> ratio 1.216 (order 1, not 1000)

## test_scene_transforms — PASS

- 16 rotation matrices checked: max|R^T R - I| = 5.55e-16 (< 1e-12), max|det-1| = 6.66e-16 (right-handed)
- T_SM vs SSOT sec 3.1: t_doc=[185.25, 0.0, 0.0] mm (diff 0.0e+00 m), quat=[0.70710678,0.0,0.70710678,0.0] (R diff 2.8e-16)

## test_fk_render_alignment — PASS

- configs checked: 22 (q=0 + E1.5 selected q + 20 random in-limit, seed 20260714)
- max position error: 0.000000 mm (< 1 mm)
- max orientation error: 0.000002 deg (< 0.1 deg)
- T_SM yaml-vs-b601_model max abs diff: 6.12e-17

## test_replay_numeric_consistency — PASS

- 44/44 keyframe rows match=True (exact contract)
- 6 videos covered exactly once: anim_v01_target_tumble(7), anim_v02_b601_approach(7), anim_v03_base_reaction(6), anim_v04_capture_impulse(8), anim_v05_flex_diagnostic(8), anim_v06_gate_explanation(8)

## test_status_semantics — PASS

- recount tally 3/3/66/0 (UNCLASSIFIED 0), on-disk CSV agrees (72 rows), gate state_counts SAFE 0 / UNKNOWN 3 / UNSAFE 69 self-consistent
- dashboard: no non-zero VERIFIED_SAFE claim; REPEAT_E1_5 banner present; DIAGNOSTIC marker present; all four reason classes named
- static scan: 0 external src/href/script/@import/url() targets in dashboard AND explorer (fully offline)

## test_dashboard_contract — PASS

- 6/6 MP4 payloads embedded byte-for-byte as data URIs
- interactive explorer payload embedded and hydrated; parent Plotly is reused, avoiding both an over-limit URL and duplicate parsing
- strict single-file scan: 17 fetch targets, all data URIs
- frame registry 10 rows; required I/S/B/M/E/T/G1-G3 present, unit quaternions valid, B/M SSOT naming explicit
- v05 source guard: read-only existing PNG/CSV evidence; no flexible solver imports/calls and no fabricated deformation time history
