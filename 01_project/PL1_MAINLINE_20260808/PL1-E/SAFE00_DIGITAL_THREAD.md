# SAFE00_DIGITAL_THREAD.md — SAFE-00 数字线程重建 (PL1-E)

- Scope: SAFE-00 runtime safety gate (`30_simulation/safety_00_runtime_gate/`), contract `safety-gate-v1`, policy `safety-gate-policy-v1.2` (`20_engineering/config/safety_gate/safety_policy_v1.yaml`, status FROZEN_FOR_SAFE_00_WAVE1).
- Verified at git HEAD `5c5adde` (branch `publication/stage3-integrity-closure`).
- Sources read: `src/safety_core.py` (931 lines), `src/run_gates.py`, `docs/safety_gate_contract.md`, `docs/safety_gate_design.md`, `README.md`, `task_current_state.md`, `results/safety_00_gate_check.json`, `results/evidence_manifest.json`, `baseline_reproduction.json`, `20_engineering/config/safety_gate/*` (3 schemas + policy + experiment_matrix_v1.yaml), plus the frozen upstream artifacts themselves.
- SAFE-00 nature (README §1): read-only consumer of existing simulation evidence; fail-closed runtime adjudication. It does NOT control the arm, does NOT generate trajectories, does NOT modify sim_01–12 or the frozen threshold registry.

---

## 1. INPUTS (what SAFE-00 actually reads — all re-read and re-hashed per call)

### 1.1 Per-call request/evidence (closed schemas, `20_engineering/config/safety_gate/`)

| Artifact | File | Notes |
|---|---|---|
| Safety request schema | `safety_request.schema.json` (7,418 B) | closed schema; unknown fields/prose conditions/legacy action vocab rejected at entry |
| Evidence bundle schema | `evidence_bundle.schema.json` (6,551 B) | provenance completeness enforced |
| Safety response schema | `safety_response.schema.json` (9,175 B) | output closed schema |
| Gate matrix | `experiment_matrix_v1.yaml` (2,299 B) | 16 preregistered cases: 2 normal / 12 bypass / 2 degradation |
| Policy | `safety_policy_v1.yaml` (5,515 B) | v1.2, frozen, `thresholds_widened=false` |

Request vocabulary (frozen): physical_state ∈ {SAFE, UNSAFE, UNKNOWN}; decision ∈ {ALLOW, MODIFY, WAIT, BACKOFF, ABORT}; task_action ∈ {APPROACH, CAPTURE, POST_CAPTURE_STABILIZE, DETUMBLE}; model_level ∈ {L0, L1, L2}.

### 1.2 Frozen upstream evidence (dynamics states & capture sim) — bound by hash in policy

| Input | Path | Hash binding (policy) | Expected verdict / value | Verified present at HEAD |
|---|---|---|---|---|
| Threshold registry | `30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml` | raw-byte sha256 `400bcedce5af6ad5c4135e67f87bb524ee2fdafb1c26aeae07e495ff387b2873` | — | yes (gate JSON GS-C: registry_actual == expected) |
| sim_10 gate (mission feasibility, ~9002 pt scan) | `30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json` | canonical JSON sha256 `74020b9c450d…02cbc0` | `SIM10_GATES_PASS`, scope GLOBAL_GATE_NON_SCENARIO (`sim10:GS1/GS2/GS3`) | yes (verdict field confirmed) |
| sim_11 gate (coupled dynamics, FFR+contact bandwidth) | `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json` | canonical `76c84922ea32…d97036f` | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`, GLOBAL (`sim11:G1/G4/G5`) | yes (PROVISIONAL_PARAMS=true confirmed) |
| sim_12 gate (strategy feasibility Ph1) | `30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json` | canonical `9f94c1c7b0e1…b07b4f46` | `SIM12_PHASE1_GATES_PASS`, scope SCENARIO_ROW | yes (verdict confirmed) |
| sim_12 strategy table (candidate row source) | `30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv` | table canonical `c36f71009f27…d328fa`; row `A_low\|S1_passive` canonical `ed770acd96a6…879deb77df7c` | required row values: feasibility=FEASIBLE, binding_gate=NONE, flex_energy=PROVISIONAL_NOT_EVALUATED | yes (policy binding; row read each call) |
| Case config | `20_engineering/config/strategy_feasibility/strategies_v0.yaml` | doc canonical `36fe301b36b3…e1597d4`; `cases.A_low` canonical `e55e530a79c9…33d0449` | pre-capture `omega_dps=0.5` (NOT post-capture 1.387206) | yes |
| Mass-ratio reference | `20_engineering/config/mission_feasibility/scan_v0.yaml` | doc canonical `ca7be9916fae…265c140e` | `mass_reference.servicer_bus_kg = 24.0` → mu=22/24 | yes |
| e15 ANCF certification gate | `30_simulation/e15_ancf_certification/results/gate_summary.json` | canonical `e28845a4835b…a1f81ca` | `REPEAT_ANCF_CERTIFICATION`, GLOBAL (`e15:overall`) | yes (policy-bound) |

Candidate binding (only registered candidate): `candidate_id=A_low-S1_passive`, task_action=CAPTURE, derived request: strategy_alpha(S1_passive)=0.0, lambda_actual=1.0 on grid 1.0, abs tol 1e-12; nominal state `G2_cubesat`, `omega_dps=0.5`, `mu=22/24`, `alpha=0`, `lambda=1`. Any mismatch in CSV row, case YAML, row ref, candidate ID or derived state → UNKNOWN/ABORT.

Level→artifact requirements (policy `required_artifacts_by_level`): L0 = [sim10, sim12]; L1 = [sim11, sim12]; L2 = [e15_ancf, sim12]. Certification: L0 CERTIFIED, L1 PROVISIONAL, L2 UNAVAILABLE (reason E15_REPEAT_ANCF_CERTIFICATION).

Time contract (all inside scenario_hash): `captured_at <= request.timestamp <= decision_time <= deadline/valid_until`; frozen limits: max_clock_skew_s=0, max_capture_age_s=2, max_request_to_decision_s=2, max_deadline_horizon_s=240, max_validity_horizon_s=300. Future data/illegal deadline → ABORT; expired but structurally legal evidence → WAIT.

---

## 2. DECISION LOGIC (`safety_core.py::decide(request, evidence)` → `_decide_verified`)

Fixed-order adjudication chain (design doc §裁决链, verified against code structure and contract doc):

1. **Closed-schema validation** of request and evidence (jsonschema Draft202012 + format checker; strict JSON loader rejects duplicate keys and NaN/Infinity; strict YAML loader rejects duplicate mapping keys).
2. **Scenario hash recomputation** over all decision fields of request + evidence (incl. every timestamp/deadline/validity).
3. **Temporal-order check** (capture/request/decision/deadline/validity chain above).
4. **Threshold registry re-read** as raw bytes; sha256 must equal frozen `400bcedc…` (no normalization; file never modified).
5. **Gate JSON re-read + canonical re-hash** (`CANONICAL_JSON_SHA256_V1`: sorted keys, compact separators, UTF-8; CRLF/indentation-insensitive, semantics-sensitive); verdicts must match expected values.
6. **Candidate row verification**: re-read sim_12 `strategy_results.csv` (table + row canonical hashes), `strategies_v0.yaml` (`cases.A_low`), `scan_v0.yaml` (24 kg mass reference); verify candidate ID, row ref, action, geometry class, pre-capture ω, mass ratio, strategy α/λ.
7. **Scope/model-level/certification/provisional/flex verification**: artifact scope (SCENARIO_ROW vs GLOBAL_GATE_NON_SCENARIO whitelist), model_level, certification status, provisional flags, flex status (FLEX=UNKNOWN never promotable).
8. **Layered adjudication**: domain membership (L0/L1/L2 domains over geometry_class/mu/omega/lambda/alpha[+T_c, f1 for L1/L2]), resource thresholds from registry, independent physics evidence, degradation-chain rules (no optimistic fallback; fallback target domain re-checked).
9. **Authorization**: only if physical_state=SAFE AND provenance complete AND caller injects ≥32-byte HMAC-SHA256 key + key ID → signed authorization bound to full response, key ID, not_before/expires_at and execution requirements. Missing/empty/short production key → fail-closed `AUTHORIZATION_KEY_UNAVAILABLE` (nominal SAFE request still ABORTs). Repo contains only public `TEST_VECTOR_SAFE00_V1` (tests/gates only; explicitly not a production secret).

Fail-closed invariants (machine-asserted in gate JSON): UNKNOWN never → ALLOW/MODIFY; stale evidence → WAIT/BACKOFF; L2 failure → no optimistic fallback; no provenance → no ALLOW.

Latency is excluded from the frozen gate JSON by design (no `perf_counter` reads in gate path); it lives only in `results/safety_00_latency_diagnostic.json`, excluded from the evidence manifest by explicit rule.

---

## 3. OUTPUTS

| Output | Where | Content |
|---|---|---|
| Safety response (per call) | in-memory / harness | closed-schema response: physical_state, decision, reason_code, provenance block (gate paths+hash modes+hashes+verdicts, artifact scope, row ref + structured row binding, model_level, certification, provisional_flags, flex_status, registry hash, scenario hash), optional HMAC authorization (not_before/expires_at/execution requirements) |
| Machine gate verdict | `results/safety_00_gate_check.json` | verdict=PASS; GS-A/GS-B/GS-C; 16-case table with per-case response sha256 + determinism flag; metrics; `next_stage_authorized=false`, `review_status=PENDING_REVIEW`, `thresholds_widened=false` |
| Determinism payload lock | task state + gate JSON | 16-case gate payload identical across two runs, raw sha256 `7a352fe3d511804da3c182ee6380e3c86003173796ab912f5390ec43bb66836c` |
| Test log | `results/safety_00_tests.log` | SAFE-00 47/47 machine checks (per task state LOOP-5); unit tests cover CSV/case-YAML tamper, checksum recompute, UNKNOWN+ALLOW, empty provenance, deadline overflow, bitwise rerun equality |
| Diagnostics (non-gate) | `results/safety_00_latency_diagnostic.json` | non-deterministic latency only, excluded from PASS/REPEAT/BLOCKED |
| Evidence manifest | `results/evidence_manifest.json` | full tracked inventory, logs, commands, hashes (LOOP-7 freeze) |

Decision semantics (frozen mapping): ALLOW = execute as requested (SAFE, authorized); MODIFY = execute with modification (exact-solver policy MOD-EXACT-SOLVER-V1); WAIT = stale/uncertain, re-evidence; BACKOFF = out of domain / unchecked fallback domain; ABORT = any integrity/schema/binding/authorization failure. Legacy vocab HOLD/INSUFFICIENT_EVIDENCE forbidden in contract enums (recommended mapping HOLD→WAIT etc., status PENDING_INTEGRATOR).

---

## 4. EXERCISING SIMULATION CASES

### 4.1 Preregistered gate matrix (16 cases, `experiment_matrix_v1.yaml`, all deterministic, all match)

- **Normal (2)**: `N1_NORMAL_ALLOW` → SAFE/ALLOW (reason AUTHORIZED_SAFE, response `369f469b…`); `N2_NORMAL_MODIFY` → SAFE/MODIFY (AUTHORIZED_WITH_MODIFICATION, `ec54a2e8…`).
- **Bypass/attack (12, 0 successes)**: B1 forged provenance → ABORT (GATE_ARTIFACT_HASH_MISMATCH); B2 stale evidence → WAIT (EVIDENCE_STALE); B3 out-of-domain → BACKOFF; B4 λ-rounding smuggling → ABORT (CANDIDATE_STATE_BINDING_MISMATCH); B5 provisional field missing → ABORT (REQUEST_SCHEMA_INVALID); B6 uncertified L2 → WAIT (L2_FAILED_NO_OPTIMISTIC_FALLBACK); B7 prose condition → ABORT; B8 wrong row ref → ABORT (CANDIDATE_ROW_BINDING_MISMATCH); B9 arbitrary candidate → ABORT (CANDIDATE_ID_MISMATCH); B10 future state → ABORT (TEMPORAL_ORDER_INVALID); B11 deadline rebind → ABORT (SCENARIO_HASH_MISMATCH); B12 no auth key → ABORT (AUTHORIZATION_KEY_UNAVAILABLE).
- **Degradation chain (2)**: D1 L2→L0 unchecked → BACKOFF (FALLBACK_DOMAIN_UNCHECKED); D2 L2→L1 rechecked → WAIT (L2_FAILED_NO_OPTIMISTIC_FALLBACK).

### 4.2 Baseline reproduction of the evidence chain (`baseline_reproduction.json`, executed 2026-07-19T02:14:30+08:00, baseline commit `926522f`)

- sim_05 free-floating arm: 22/22 PASS — supplies the B601 dynamics anchor (19.20° A0@M1 anchor reused by CTRL-02; SAFE-00 consumes sim_05-class dynamics only indirectly via gates).
- sim_10 mission feasibility: 6/6 PASS — global gate evidence.
- sim_11 coupled dynamics: 27/27 PASS — global gate evidence (PROVISIONAL).
- sim_12 strategy feasibility: 3/3 PASS — scenario-row evidence (candidate A_low|S1_passive).
- Frozen hash re-checks: threshold registry + sim_08 assumptions both match. Windows CRLF raw-byte drift observed on sim_12 artifacts, semantic content unchanged → policy v1.2 moved gate JSON binding to canonical semantics (registry stays raw-byte frozen).

### 4.3 Competition demo replay scenarios exercising the SAFE-00 binding (Lane C, offline, command_emitted=false)

- **A_low** (22 kg, 0.5 deg/s, PROVISIONAL_LOW_CONFIDENCE_MASS): sim_10 GLOBAL_ONLY, sim_12 exact hit A_low|S1_passive FEASIBLE, SAFE-00 candidate binding exact but Gate PENDING_REVIEW + next_stage_authorized=false → display EXECUTE as explanation-only recommendation (execution_authority=false).
- **B_anchor** (150 kg debris, 3 deg/s): sim_10 INFEASIBLE_RATE; all four sim_12 strategies INFEASIBLE → ABORT upstream; SAFE-00 NOT_APPLICABLE_UPSTREAM_ABORT (no request/response created).
- **C_transition** (48 kg, 2 deg/s, proof case): sim_12 S1 infeasible (wheel momentum), S3a feasible; SAFE-00 has no registered C_transition/S3a candidate → `authorized_candidate_binding=MISSING` → display MODIFY (= change candidate and re-enter authorization chain, not immediate execution).

---

## 5. LATEST GATE STATUS (as verified at HEAD)

- **Verdict: PASS** (`results/safety_00_gate_check.json`, content committed `284c882`, 2026-07-22 18:39 +0800).
- GS-A fail-closed hard rules: PASS (unknown_never_allow, stale→wait/backoff, l2_failure_no_optimistic_fallback, fallback_target_domain_rechecked, no_provenance_no_allow).
- GS-B bypass surface: PASS — 12 preregistered bypass cases, 0 successes.
- GS-C freeze lock: PASS — registry actual == expected `400bcedc…`; canonical hash mode; candidate row binding frozen; production HMAC key required; thresholds_widened=false.
- Metrics: unknown_allow_count=0; bypass_success_count=0; false_abort_rate=0.0; authorization_provenance_complete_rate=1.0.
- Determinism: same-input responses bitwise equal across 16 cases.
- **Gate ≠ authorization**: `review_status=PENDING_REVIEW` (LOOP-6 independent red team re-review outstanding), `next_stage_authorized=false`. Residual boundaries: sim_11 PROVISIONAL params; e15/L2 REPEAT_ANCF_CERTIFICATION; AG5 assembly-safety extension not implemented (Wave B, DAG blocker B7: Wave A produces physics verdicts only, no execution authorization).

---

## 6. THREAD INTEGRITY — broken / unverifiable links

| # | Link | State | Detail |
|---|---|---|---|
| T1 | Frozen evidence files (registry, 3 gate JSONs, strategy CSV, 2 config YAMLs, e15 summary) | **INTACT** | All present at HEAD; GS-C machine check confirms registry raw hash and canonical bindings at freeze time; paths re-verified to exist during this recon |
| T2 | SAFE-00 code → config/contracts (`20_engineering/config/safety_gate/`) | **INTACT** | All 5 files present (verified listing) |
| T3 | Upstream sim *reproduction* (re-running sim_05/sim_11/sim_12 to regenerate evidence) | **HOLD — broken at HEAD** | `sim_05_free_floating_arm/b601_model.py:39-40` computes URDF path `<repo_root>/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`; no top-level `cad/` exists post-REORG04; `B601Arm()` raises FileNotFoundError (verified by execution at HEAD). Actual URDF at `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` (sha256 prefix `1bc2b748…`, matches accepted truth). Frozen JSON/CSV evidence SAFE-00 consumes is unaffected, but any fresh reproduction of the underlying sims fails until the one-line path is fixed (not fixed here — read-only mandate; change touches frozen sim behavior → governance decision) |
| T4 | Production HMAC key availability | **INTACT by design (fail-closed)** | No production key in repo; nominal SAFE request without injected key → ABORT/AUTHORIZATION_KEY_UNAVAILABLE (B12 case proves it) |
| T5 | LOOP-6 independent review | **UNVERIFIED — PENDING_REVIEW** | No review record found in ROOT A (`08_REVIEWS/` empty at HEAD); implementer cannot self-certify; gate stays next_stage_authorized=false until external re-review |
| T6 | sim_11 provisional parameters / e15 L2 certification | **OPEN (declared, not broken)** | PROVISIONAL_PARAMS=true (panel modes, T_c); L2 UNAVAILABLE pending ANCF re-certification; both declared in policy certification block |
| T7 | Candidate coverage beyond A_low-S1_passive | **OPEN by design** | C_transition/S3a binding proven MISSING in demo replay; registering new candidates = preregistered new experiment + policy update (governance) |

Thread summary (one line): **mission input → sim_10 feasibility (global) + sim_12 strategy row (scenario) + sim_11/e15 global gates + frozen registry → SAFE-00 closed-schema request/evidence → 9-step fail-closed adjudication → SAFE/ALLOW|MODIFY with HMAC-signed authorization, else WAIT/BACKOFF/ABORT — all provenance-hashed, deterministic, and currently PASS-with-PENDING_REVIEW (no next-stage authorization).**
