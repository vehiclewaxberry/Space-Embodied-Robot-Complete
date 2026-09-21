# -*- coding: utf-8 -*-
"""Reissue SOLAR_ARRAY_R2_BUILD_REPORT as V2 with self-reference-excluded hashing.

ODR-49 execution (KIMI M7 swarm Wave-4a, agent A6).

Defect being repaired (CM/manifest class, NOT geometry):
  SOLAR_ARRAY_R2_BUILD_REPORT_V1.json carries
  hashes["SOLAR_ARRAY_R2_BUILD_REPORT_V1.json"] = AFE4CA26...
  i.e. a hash of an earlier byte state of the report itself (see
  build_solar_array_r2.py lines ~297-303: write -> hash -> insert self-entry
  -> write again).  A self-entry can never match the final bytes.

V2 policy (same as e21/V5 manifests and 02_bridge):
  the report carries NO hash of itself; downstream consumers pin its sha256
  after emission.

Read-only on V1 and on the two pinned artifacts.  Pure stdlib.  Run:
  python -B build_solar_array_r2_report_v2.py
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # repo root: <root>/20_engineering/F3R2.../ecr_solar_array_r2

V1_PATH = HERE / "SOLAR_ARRAY_R2_BUILD_REPORT_V1.json"
V2_PATH = HERE / "SOLAR_ARRAY_R2_BUILD_REPORT_V2.json"
V2_MD_PATH = HERE / "SOLAR_ARRAY_R2_BUILD_REPORT_V2.md"
FCSTD_PATH = HERE / "SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd"
STEP_PATH = HERE / "SOLAR_ARRAY_R2_CANDIDATE_V1.step"
ODR_PATH = (ROOT / "20_engineering" / "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
            / "00_authority"
            / "M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml")

V1_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V1.json"
ODR_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml"

EXPECTED_V1_BYTES = 11019
EXPECTED_V1_SHA256 = "6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586"
EXPECTED_FCSTD_SHA256 = "9D4D249A5D4EED7BDD8F3C08EC96737884A19523782112B1E72AD9EA0A1B65AB"
EXPECTED_STEP_SHA256 = "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"

ODR_WAIT_SECONDS = 240
ODR_POLL_SECONDS = 5

WAVE = ("KIMI M7 机械终局接管 swarm Wave-4a "
        "(ODR-45..49 owner decisions + R2 full-flex closure)")

SELF_HASH_POLICY = ("SELF_REFERENCE_EXCLUDED - this file carries no hash of "
                    "itself; downstream consumers pin its sha256 after "
                    "emission (same policy as e21/V5 manifests and 02_bridge)")

# Fields excluded from the V1<->V2 payload-equality proof.  These are header
# fields, the V1 hashes self-entry, the proof itself, or V2-only closure /
# fail-closed-footer fields absent from V1.  Everything else - the full
# engineering payload (class, parameters, stack_metrics, protrusion_note,
# mass_model_candidate, shape_metrics, clearance_pairs, clearance_summary,
# outputs, hashes of the two real artifacts, scope_guard) - is inside the
# compared set and must hash identically.
PAYLOAD_FIELD_EXCLUSION_SET = [
    "schema",
    "generated_local",
    "generated_clock_source",
    "generator",
    "authority",
    "supersedes",
    "self_hash_policy",
    "report_self_reference_excluded",
    "report_self_sha256",
    "hashes.SOLAR_ARRAY_R2_BUILD_REPORT_V1.json",
    "reissue_proof",
    "v1_integrity",
    "oi_r1_01_disposition",
    "nonclaims",
    "next_stage_authorized",
    "release_credit",
]

V1_SELF_HASH_KEY = "SOLAR_ARRAY_R2_BUILD_REPORT_V1.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def local_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def fail(msg: str) -> None:
    print("A6_V2_BUILD_ABORT: %s" % msg)
    sys.exit(1)


def wait_for_odr() -> None:
    deadline = time.time() + ODR_WAIT_SECONDS
    while not ODR_PATH.is_file():
        if time.time() >= deadline:
            fail("ODR-45..49 authority record not found after %ds: %s"
                 % (ODR_WAIT_SECONDS, ODR_PATH))
        time.sleep(ODR_POLL_SECONDS)


def canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def payload_view(report: dict) -> dict:
    """Deep copy minus the exclusion set (top-level fields + V1 hashes
    self-entry)."""
    view = copy.deepcopy(report)
    for key in PAYLOAD_FIELD_EXCLUSION_SET:
        if "." in key:
            continue  # nested exclusion handled below
        view.pop(key, None)
    if isinstance(view.get("hashes"), dict):
        view["hashes"].pop(V1_SELF_HASH_KEY, None)
    return view


def main() -> None:
    wait_for_odr()

    odr_bytes = ODR_PATH.stat().st_size
    odr_sha256 = sha256_of(ODR_PATH)

    v1_recomputed_before = sha256_of(V1_PATH)
    v1_bytes = V1_PATH.stat().st_size
    if v1_bytes != EXPECTED_V1_BYTES:
        fail("V1 bytes %d != expected %d" % (v1_bytes, EXPECTED_V1_BYTES))
    if v1_recomputed_before != EXPECTED_V1_SHA256:
        fail("V1 sha256 %s != expected %s"
             % (v1_recomputed_before, EXPECTED_V1_SHA256))

    fcstd_sha256 = sha256_of(FCSTD_PATH)
    step_sha256 = sha256_of(STEP_PATH)
    if fcstd_sha256 != EXPECTED_FCSTD_SHA256:
        fail("FCStd sha256 mismatch: %s" % fcstd_sha256)
    if step_sha256 != EXPECTED_STEP_SHA256:
        fail("step sha256 mismatch: %s" % step_sha256)

    v1 = json.loads(V1_PATH.read_text(encoding="utf-8"))

    # Byte-identical check: V1 pins must equal the recomputed artifact hashes.
    v1_hashes = v1["hashes"]
    if v1_hashes.get(FCSTD_PATH.name) != fcstd_sha256:
        fail("V1 FCStd pin != recomputed hash")
    if v1_hashes.get(STEP_PATH.name) != step_sha256:
        fail("V1 step pin != recomputed hash")
    if v1_hashes.get(V1_SELF_HASH_KEY) == EXPECTED_V1_SHA256:
        fail("V1 self-entry unexpectedly matches; defect premise broken")

    generated_local = local_now()

    v2 = {
        "schema": "SOLAR_ARRAY_R2_BUILD_REPORT_V2",
        "generated_local": generated_local,
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "generator": ("%s - A6 build_solar_array_r2_report_v2.py: reissue "
                      "SOLAR_ARRAY_R2_BUILD_REPORT as V2 with "
                      "self-reference-excluded hashing per ODR-49" % WAVE),
        "authority": ("ODR-49; authority_record=%s; "
                      "authority_record_sha256=%s; authority_record_bytes=%d"
                      % (ODR_REL, odr_sha256, odr_bytes)),
        "supersedes": ("SOLAR_ARRAY_R2_BUILD_REPORT_V1.json (V1 remains on "
                       "disk byte-untouched; V2 is the reissued registration "
                       "per ODR-49; defect class CM/manifest, not geometry)"),
        # ---- engineering payload: preserved byte-semantically from V1 ----
        "class": v1["class"],
        "parameters": v1["parameters"],
        "stack_metrics": v1["stack_metrics"],
        "protrusion_note": v1["protrusion_note"],
        "mass_model_candidate": v1["mass_model_candidate"],
        "shape_metrics": v1["shape_metrics"],
        "clearance_pairs": v1["clearance_pairs"],
        "clearance_summary": v1["clearance_summary"],
        "outputs": v1["outputs"],
        "hashes": {
            FCSTD_PATH.name: v1_hashes[FCSTD_PATH.name],
            STEP_PATH.name: v1_hashes[STEP_PATH.name],
        },
        "scope_guard": v1["scope_guard"],
        # ---- self-hash policy (e21/V5/02_bridge convention) ----
        "self_hash_policy": SELF_HASH_POLICY,
        "report_self_reference_excluded": True,
        "report_self_sha256": None,
        # ---- proof + integrity + closure evidence + footer (filled below) --
        "reissue_proof": None,
        "v1_integrity": None,
        "oi_r1_01_disposition": ("REISSUED_PER_ODR49__PAYLOAD_EQUALITY_PROVEN__"
                                 "FORMAL_CLOSURE_IN_CM_REFRESH"),
        "nonclaims": [
            "V2 is a CM/manifest reissue only: NOT a geometry change "
            "(SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd / .step bytes and all "
            "shape_metrics / clearance_pairs content unchanged from V1)",
            "NOT a mass-model change: mass_model_candidate carried verbatim; "
            "still an areal-density ENGINEERING_CANDIDATE, NOT a measured "
            "mass; the forbidden 3 x 0.3483933 kg legacy rescale remains "
            "unused",
            "Does NOT close anything else: MODE_FLIGHT protrusion HOLD per "
            "ODR-18 item 4 / ODR-19 carried verbatim in protrusion_note; "
            "24.000 kg whole-sat mass closure remains OPEN pending R2-WI-05",
            "OI-R1-01 formal closure is registered by the CM agent's OPEN "
            "ITEMS register refresh in a later wave; oi_r1_01_disposition "
            "here is evidence, not the register act",
            "candidate != authority; test PASS != gate PASS; this reissue "
            "grants no release credit and authorizes no next stage",
        ],
        "next_stage_authorized": False,
        "release_credit": False,
    }

    # ---- payload-equality proof (computed before emission) -----------------
    v1_payload_sha256 = hashlib.sha256(
        canonical_bytes(payload_view(v1))).hexdigest().upper()
    v2_payload_sha256 = hashlib.sha256(
        canonical_bytes(payload_view(v2))).hexdigest().upper()
    if v1_payload_sha256 != v2_payload_sha256:
        fail("payload digests differ: V1=%s V2=%s"
             % (v1_payload_sha256, v2_payload_sha256))

    v2["reissue_proof"] = {
        "method": ("deep-copy parsed V1 and V2 JSON; drop the fields listed "
                   "in payload_field_exclusion_set (top-level) and the V1 "
                   "hashes self-entry hashes.SOLAR_ARRAY_R2_BUILD_REPORT_V1."
                   "json (V2 carries no self-entry); canonicalize via "
                   "json.dumps(sort_keys=True, separators=(',', ':'), "
                   "ensure_ascii=False) encoded UTF-8; sha256 over canonical "
                   "bytes; assert equality"),
        "payload_field_exclusion_set": PAYLOAD_FIELD_EXCLUSION_SET,
        "exclusion_set_extension_note": ("v1_integrity, oi_r1_01_disposition, "
                                         "nonclaims, next_stage_authorized "
                                         "and release_credit are V2-only "
                                         "closure-evidence / fail-closed-"
                                         "footer fields absent from V1; they "
                                         "are excluded so the comparison "
                                         "covers exactly the engineering "
                                         "payload carried over from V1"),
        "canonicalization": ("json.dumps(obj, sort_keys=True, "
                             "separators=(',', ':'), ensure_ascii=False)."
                             "encode('utf-8')"),
        "v1_payload_sha256": v1_payload_sha256,
        "v2_payload_sha256": v2_payload_sha256,
        "payload_equality_asserted": True,
        "assertion_result": "PASS_PAYLOAD_IDENTICAL_AFTER_EXCLUSION_SET",
        "artifact_hash_recheck": {
            FCSTD_PATH.name: {
                "v1_pin": v1_hashes[FCSTD_PATH.name],
                "recomputed": fcstd_sha256,
                "match": v1_hashes[FCSTD_PATH.name] == fcstd_sha256,
            },
            STEP_PATH.name: {
                "v1_pin": v1_hashes[STEP_PATH.name],
                "recomputed": step_sha256,
                "match": v1_hashes[STEP_PATH.name] == step_sha256,
            },
        },
        "v1_self_entry_defect": {
            "v1_hashes_self_entry_value": v1_hashes.get(V1_SELF_HASH_KEY),
            "v1_actual_sha256": EXPECTED_V1_SHA256,
            "can_never_match": True,
            "root_cause": ("build_solar_array_r2.py lines ~297-303: report "
                           "written, hashed, self-entry inserted, written "
                           "again - recorded hash covers the pre-insertion "
                           "byte state"),
            "defect_class": "CM/manifest, not geometry",
        },
    }

    v1_recomputed_after = sha256_of(V1_PATH)
    v2["v1_integrity"] = {
        "path": V1_REL,
        "bytes": v1_bytes,
        "sha256": EXPECTED_V1_SHA256,
        "recomputed_before": v1_recomputed_before,
        "recomputed_after": v1_recomputed_after,
        "verdict": ("UNTOUCHED" if (v1_recomputed_before
                                    == v1_recomputed_after
                                    == EXPECTED_V1_SHA256
                                    and v1_bytes == EXPECTED_V1_BYTES)
                    else "VIOLATED"),
    }
    if v2["v1_integrity"]["verdict"] != "UNTOUCHED":
        fail("V1 integrity verdict is not UNTOUCHED")

    V2_PATH.write_text(json.dumps(v2, indent=2), encoding="utf-8")

    # ---- post-write verification ------------------------------------------
    v2_disk = json.loads(V2_PATH.read_text(encoding="utf-8"))
    v1_disk_digest = hashlib.sha256(
        canonical_bytes(payload_view(json.loads(
            V1_PATH.read_text(encoding="utf-8"))))).hexdigest().upper()
    v2_disk_digest = hashlib.sha256(
        canonical_bytes(payload_view(v2_disk))).hexdigest().upper()
    if v1_disk_digest != v2_disk_digest:
        fail("post-write payload digests differ")
    v1_post = sha256_of(V1_PATH)
    if v1_post != EXPECTED_V1_SHA256:
        fail("V1 changed during the run: %s" % v1_post)

    md = build_md(v2, v1_payload_sha256, v2_payload_sha256,
                  odr_sha256, odr_bytes)
    V2_MD_PATH.write_text(md, encoding="utf-8")

    print("A6_V2_BUILD_OK")
    print("V2_JSON %s bytes=%d sha256=%s"
          % (V2_PATH, V2_PATH.stat().st_size, sha256_of(V2_PATH)))
    print("V2_MD %s bytes=%d sha256=%s"
          % (V2_MD_PATH, V2_MD_PATH.stat().st_size, sha256_of(V2_MD_PATH)))
    print("V1_PAYLOAD_SHA256 %s" % v1_payload_sha256)
    print("V2_PAYLOAD_SHA256 %s" % v2_payload_sha256)
    print("V1_POST_RUN_SHA256 %s (UNTOUCHED)" % v1_post)
    print("ODR_PIN %s bytes=%d" % (odr_sha256, odr_bytes))


def build_md(v2: dict, v1_payload_sha256: str, v2_payload_sha256: str,
             odr_sha256: str, odr_bytes: int) -> str:
    rp = v2["reissue_proof"]
    vi = v2["v1_integrity"]
    nonclaims = "\n".join("- %s" % n for n in v2["nonclaims"])
    return """# SOLAR_ARRAY_R2_BUILD_REPORT_V2 — ODR-49 reissue (self-reference-excluded hashing)

Human-readable companion to `SOLAR_ARRAY_R2_BUILD_REPORT_V2.json`. On any
conflict the structured JSON fields govern.

## Header

- schema: `SOLAR_ARRAY_R2_BUILD_REPORT_V2`
- generated_local: `{generated_local}`
- generated_clock_source: `HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08`
- generator: {generator}
- authority: ODR-49
  - authority_record: `{odr_rel}`
  - authority_record_sha256: `{odr_sha256}`
  - authority_record_bytes: {odr_bytes}
- supersedes: {supersedes}

## What changed vs V1 (CM/manifest defect repair only)

V1 (`SOLAR_ARRAY_R2_BUILD_REPORT_V1.json`, 11019 B, sha256
`6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586`) carried a
self-entry `hashes["SOLAR_ARRAY_R2_BUILD_REPORT_V1.json"] = AFE4CA26…` that
can never match the final file bytes (root cause: `build_solar_array_r2.py`
lines ~297-303 write → hash → insert self-entry → write again). V2 removes
the self-entry; the `hashes` block now contains ONLY the two real artifact
pins, byte-identical to V1:

- `SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd`: `{fcstd}`
- `SOLAR_ARRAY_R2_CANDIDATE_V1.step`: `{step}`

Both were recomputed from raw bytes during this build and match V1's pins
(see `reissue_proof.artifact_hash_recheck`).

Self-hash policy (same as e21/V5 manifests and 02_bridge):
`{self_hash_policy}`; `report_self_reference_excluded: true`;
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

- v1_payload_sha256: `{v1_payload}`
- v2_payload_sha256: `{v2_payload}`
- assertion_result: `{assertion}`

All engineering payload (geometry parameters, stack metrics, protrusion_note
MODE_FLIGHT HOLD per ODR-18 item 4 / ODR-19 carried verbatim, mass model
candidate, shape metrics, clearance pairs/summary, outputs, scope_guard) is
unchanged.

## V1 integrity

- path: `{v1_path}` — bytes {v1_bytes}, sha256 `{v1_sha}`
- recomputed_before: `{v1_before}`
- recomputed_after: `{v1_after}`
- verdict: **{v1_verdict}** (V1 remains on disk byte-untouched)

## Closure evidence

- oi_r1_01_disposition: `{oi}`

## Fail-closed footer

- next_stage_authorized: **false**
- release_credit: **false**

Nonclaims:
{nonclaims}
""".format(
        generated_local=v2["generated_local"],
        generator=v2["generator"],
        odr_rel=ODR_REL,
        odr_sha256=odr_sha256,
        odr_bytes=odr_bytes,
        supersedes=v2["supersedes"],
        fcstd=v2["hashes"]["SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd"],
        step=v2["hashes"]["SOLAR_ARRAY_R2_CANDIDATE_V1.step"],
        self_hash_policy=v2["self_hash_policy"],
        v1_payload=v1_payload_sha256,
        v2_payload=v2_payload_sha256,
        assertion=rp["assertion_result"],
        v1_path=vi["path"],
        v1_bytes=vi["bytes"],
        v1_sha=vi["sha256"],
        v1_before=vi["recomputed_before"],
        v1_after=vi["recomputed_after"],
        v1_verdict=vi["verdict"],
        oi=v2["oi_r1_01_disposition"],
        nonclaims=nonclaims,
    )


if __name__ == "__main__":
    main()
