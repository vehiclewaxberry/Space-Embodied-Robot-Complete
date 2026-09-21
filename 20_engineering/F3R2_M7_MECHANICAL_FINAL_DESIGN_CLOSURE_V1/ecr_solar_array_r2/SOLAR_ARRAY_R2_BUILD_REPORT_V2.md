# SOLAR_ARRAY_R2_BUILD_REPORT_V2 — ODR-49 reissue (self-reference-excluded hashing)

Human-readable companion to `SOLAR_ARRAY_R2_BUILD_REPORT_V2.json`. On any
conflict the structured JSON fields govern.

## Header

- schema: `SOLAR_ARRAY_R2_BUILD_REPORT_V2`
- generated_local: `2026-08-23T20:39:35.364228+08:00`
- generated_clock_source: `HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08`
- generator: KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure) - A6 build_solar_array_r2_report_v2.py: reissue SOLAR_ARRAY_R2_BUILD_REPORT as V2 with self-reference-excluded hashing per ODR-49
- authority: ODR-49
  - authority_record: `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml`
  - authority_record_sha256: `69473BC19E020C6422B23C1758CFC343874F641781C9782E982036614C0849B5`
  - authority_record_bytes: 26885
- supersedes: SOLAR_ARRAY_R2_BUILD_REPORT_V1.json (V1 remains on disk byte-untouched; V2 is the reissued registration per ODR-49; defect class CM/manifest, not geometry)

## What changed vs V1 (CM/manifest defect repair only)

V1 (`SOLAR_ARRAY_R2_BUILD_REPORT_V1.json`, 11019 B, sha256
`6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586`) carried a
self-entry `hashes["SOLAR_ARRAY_R2_BUILD_REPORT_V1.json"] = AFE4CA26…` that
can never match the final file bytes (root cause: `build_solar_array_r2.py`
lines ~297-303 write → hash → insert self-entry → write again). V2 removes
the self-entry; the `hashes` block now contains ONLY the two real artifact
pins, byte-identical to V1:

- `SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd`: `9D4D249A5D4EED7BDD8F3C08EC96737884A19523782112B1E72AD9EA0A1B65AB`
- `SOLAR_ARRAY_R2_CANDIDATE_V1.step`: `21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795`

Both were recomputed from raw bytes during this build and match V1's pins
(see `reissue_proof.artifact_hash_recheck`).

Self-hash policy (same as e21/V5 manifests and 02_bridge):
`SELF_REFERENCE_EXCLUDED - this file carries no hash of itself; downstream consumers pin its sha256 after emission (same policy as e21/V5 manifests and 02_bridge)`; `report_self_reference_excluded: true`;
`report_self_sha256: null`.

## Payload-equality proof

Exclusion set (header fields, V1 self-entry, proof itself, and V2-only
closure/footer fields): `schema`, `generated_local`,
`generated_clock_source`, `generator`, `authority`, `supersedes`,
`self_hash_policy`, `report_self_reference_excluded`, `report_self_sha256`,
`hashes.SOLAR_ARRAY_R2_BUILD_REPORT_V1.json`, `reissue_proof`,
`v1_integrity`, `oi_r1_01_disposition`, `nonclaims`,
`next_stage_authorized`, `release_credit`.

Canonicalization: `json.dumps(obj, sort_keys=True, separators=(',', ':'),
ensure_ascii=False).encode('utf-8')`.

- v1_payload_sha256: `AA5D3D0AF63CF8C9F06D76ED53F99F5FB6FF0BAF52FC40A92352BD0D1917F687`
- v2_payload_sha256: `AA5D3D0AF63CF8C9F06D76ED53F99F5FB6FF0BAF52FC40A92352BD0D1917F687`
- assertion_result: `PASS_PAYLOAD_IDENTICAL_AFTER_EXCLUSION_SET`

All engineering payload (geometry parameters, stack metrics, protrusion_note
MODE_FLIGHT HOLD per ODR-18 item 4 / ODR-19 carried verbatim, mass model
candidate, shape metrics, clearance pairs/summary, outputs, scope_guard) is
unchanged.

## V1 integrity

- path: `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V1.json` — bytes 11019, sha256 `6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586`
- recomputed_before: `6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586`
- recomputed_after: `6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586`
- verdict: **UNTOUCHED** (V1 remains on disk byte-untouched)

## Closure evidence

- oi_r1_01_disposition: `REISSUED_PER_ODR49__PAYLOAD_EQUALITY_PROVEN__FORMAL_CLOSURE_IN_CM_REFRESH`

## Fail-closed footer

- next_stage_authorized: **false**
- release_credit: **false**

Nonclaims:
- V2 is a CM/manifest reissue only: NOT a geometry change (SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd / .step bytes and all shape_metrics / clearance_pairs content unchanged from V1)
- NOT a mass-model change: mass_model_candidate carried verbatim; still an areal-density ENGINEERING_CANDIDATE, NOT a measured mass; the forbidden 3 x 0.3483933 kg legacy rescale remains unused
- Does NOT close anything else: MODE_FLIGHT protrusion HOLD per ODR-18 item 4 / ODR-19 carried verbatim in protrusion_note; 24.000 kg whole-sat mass closure remains OPEN pending R2-WI-05
- OI-R1-01 formal closure is registered by the CM agent's OPEN ITEMS register refresh in a later wave; oi_r1_01_disposition here is evidence, not the register act
- candidate != authority; test PASS != gate PASS; this reissue grants no release credit and authorizes no next stage
