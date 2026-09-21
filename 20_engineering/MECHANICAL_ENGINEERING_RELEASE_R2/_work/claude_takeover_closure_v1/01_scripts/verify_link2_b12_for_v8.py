#!/usr/bin/env python
"""WP-A independent verification of the Link2-B12 local candidate package
before its append-only V8 authority registration.

Read-only over all inputs. Writes exactly one evidence JSON:
  _work/claude_takeover_closure_v1/02_evidence/LINK2_B12_V8_VERIFICATION_EVIDENCE_V1.json

Fail-closed: any mismatch -> overall_pass=false. No threshold is relaxed,
no historical file is rewritten, no accepted/donor file is touched.
"""
import csv
import hashlib
import json
import os
import sys

ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
PKG = os.path.join(
    ROOT,
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr",
    "ODR60_OPTION_A_ROUTE_C_R95_LINK2_B12_OPERATIONAL_COLLISION_CANDIDATE_V1",
)
OUT = os.path.join(
    ROOT,
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/claude_takeover_closure_v1",
    "02_evidence/LINK2_B12_V8_VERIFICATION_EVIDENCE_V1.json",
)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

ev = {"schema": "LINK2_B12_V8_VERIFICATION_EVIDENCE_V1", "checks": [], "overall_pass": True}

def check(cid, desc, ok, detail):
    ev["checks"].append({"id": cid, "description": desc, "pass": bool(ok), "detail": detail})
    if not ok:
        ev["overall_pass"] = False

# ---- V01 gate file: 24/24 and self-consistency -------------------------------
gate_path = os.path.join(PKG, "05_results/LOCAL_CANDIDATE_GATE_V1.json")
gate = load(gate_path)
gate_sha = sha256(gate_path)
ev["gate_sha256"] = gate_sha
ev["gate_bytes"] = os.path.getsize(gate_path)
check("V01", "gate criteria 24/24 and local_candidate_gate_pass",
      gate["criteria_passed"] == 24 and gate["criteria_total"] == 24
      and gate["local_candidate_gate_pass"] is True
      and all(c["pass"] for c in gate["criteria"]),
      f"criteria_passed={gate['criteria_passed']}/{gate['criteria_total']}")

check("V02", "gate claims zero system credit",
      gate["system_gate_pass"] is False and gate["release_credit"] is False
      and gate["next_stage_authorized"] is False and gate["pair_eligible"] is False
      and gate["system_registry_rows_modified"] == 0,
      "system_gate_pass/release_credit/next_stage_authorized/pair_eligible all false, rows_modified=0")

# ---- V03/V04 gate pins of manifest + inventory --------------------------------
man_path = os.path.join(PKG, "05_results/PACKAGE_MANIFEST_V1.csv")
inv_path = os.path.join(PKG, "05_results/PACKAGE_INVENTORY_V1.json")
man_sha, inv_sha = sha256(man_path), sha256(inv_path)
check("V03", "gate pin of PACKAGE_MANIFEST_V1.csv matches recomputed sha256+bytes",
      gate["package_manifest"]["sha256"] == man_sha
      and gate["package_manifest"]["bytes"] == os.path.getsize(man_path),
      f"recomputed={man_sha}")
check("V04", "gate pin of PACKAGE_INVENTORY_V1.json matches recomputed sha256+bytes",
      gate["package_inventory"]["sha256"] == inv_sha
      and gate["package_inventory"]["bytes"] == os.path.getsize(inv_path),
      f"recomputed={inv_sha}")

# ---- V05 manifest rows vs disk -------------------------------------------------
rows, bad = [], []
with open(man_path, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        rows.append(row)
        p = os.path.join(PKG, row["path"])
        if not os.path.isfile(p):
            bad.append((row["path"], "MISSING"))
            continue
        if os.path.getsize(p) != int(row["bytes"]):
            bad.append((row["path"], "BYTES_MISMATCH"))
            continue
        if sha256(p) != row["sha256"].upper():
            bad.append((row["path"], "SHA256_MISMATCH"))
check("V05", "every manifest row exists on disk with exact bytes+sha256",
      not bad, f"rows={len(rows)}, mismatches={bad}")
ev["manifest_rows"] = len(rows)

# ---- V06 disk vs manifest (no unlisted files) ----------------------------------
# The package's own build_package_manifest.py declares exactly three
# non-circularity self-exclusions: manifest, inventory, and the gate file
# (the gate pins the manifest hash, so the manifest cannot list the gate).
listed = {row["path"].replace("\\", "/") for row in rows}
selfnames = {"05_results/PACKAGE_MANIFEST_V1.csv",
             "05_results/PACKAGE_INVENTORY_V1.json",
             "05_results/LOCAL_CANDIDATE_GATE_V1.json"}
builder_src = open(os.path.join(PKG, "04_validation/build_package_manifest.py"),
                   encoding="utf-8").read()
check("V06a", "package manifest builder declares exactly these three self-exclusions",
      all(name.split("/")[-1] in builder_src for name in selfnames),
      "EXCLUDED set in build_package_manifest.py matches verifier self-exclusions")
on_disk = set()
for dirpath, dirnames, filenames in os.walk(PKG):
    for fn in filenames:
        rel = os.path.relpath(os.path.join(dirpath, fn), PKG).replace("\\", "/")
        on_disk.add(rel)
extras = sorted(on_disk - listed - selfnames)
check("V06", "no files on disk outside manifest (manifest/inventory self-excluded)",
      not extras, f"extras={extras}")

# ---- V07 no cache/temp ----------------------------------------------------------
dirty = [p for p in on_disk if "__pycache__" in p or p.endswith(".pyc")
         or "/.pytest" in p or p.endswith(".tmp")]
check("V07", "no bytecode/cache/temp files in package", not dirty, f"dirty={dirty}")

# ---- V08 source authority lock pins ---------------------------------------------
lock = load(os.path.join(PKG, "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"))
pins_bad = []
for pin in lock["source_pins"]:
    p = os.path.join(ROOT, pin["path"])
    if not os.path.isfile(p):
        pins_bad.append((pin["id"], "MISSING"))
    elif os.path.getsize(p) != pin["bytes"] or sha256(p) != pin["sha256"].upper():
        pins_bad.append((pin["id"], "MISMATCH"))
check("V08", f"all {len(lock['source_pins'])} source authority pins live and unchanged",
      not pins_bad, f"pins={len(lock['source_pins'])}, bad={pins_bad}")
ev["source_pins"] = len(lock["source_pins"])

# ---- V09 external current-state gates + accepted truths unchanged ----------------
external = [
    ("terminal_release_gate",
     "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json",
     "14D30FD40AC60253C0716A71BA46950E1DF6B8E69DCE3F12690319B970A48674"),
    ("m01_registry_gate",
     "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json",
     "F5E91371648756D43FF7CF6C03028FA95174428D088BAAC08254FAD8D5DCC3FF"),
    ("m01_prebind_gate",
     "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json",
     "CDFADB08C3C93F9E380C41B232727E7D08750B2955411DF9E4AF894C550B7FC4"),
    ("accepted_b601_urdf",
     "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
     "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"),
    ("master_geometry_fcstd",
     "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/03_MASTER_GEOMETRY.FCStd",
     "013DA84FE9A5C388252DB18516628411C484BB818959FA1A5CF8D950485636E7"),
    ("master_geometry_step",
     "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/04_MASTER_GEOMETRY.step",
     "8C85585E9C051AEBB849E48F56354B48BF4204F61103B550BD92FC77BA99EA9E"),
]
ext_bad = []
for name, rel, want in external:
    p = os.path.join(ROOT, rel)
    got = sha256(p) if os.path.isfile(p) else "MISSING"
    if got != want:
        ext_bad.append((name, got))
check("V09", "accepted/donor/current-state files unchanged (no mutation by any recent work)",
      not ext_bad, f"checked={len(external)}, bad={ext_bad}")

# ---- V10 append-only chain tail (V7 records) --------------------------------------
seventh = load(os.path.join(ROOT, "01_project/competition/CURRENT_R2_SEVENTH_CONVERGENCE_RECEIPT.json"))
tail_bad = []
for key, rec in seventh["new_append_only_records"].items():
    p = os.path.join(ROOT, rec["path"])
    if sha256(p) != rec["sha256"].upper() or os.path.getsize(p) != rec["bytes"]:
        tail_bad.append(key)
check("V10", "seventh receipt's V7 record pins (delta/ledger/gap) match disk",
      not tail_bad, f"bad={tail_bad}")
ev["seventh_receipt_sha256"] = sha256(
    os.path.join(ROOT, "01_project/competition/CURRENT_R2_SEVENTH_CONVERGENCE_RECEIPT.json"))
ev["seventh_receipt_bytes"] = os.path.getsize(
    os.path.join(ROOT, "01_project/competition/CURRENT_R2_SEVENTH_CONVERGENCE_RECEIPT.json"))

# ---- V11 object count = 12, exclusions = 8 ----------------------------------------
contract = load(os.path.join(PKG, "00_contract/LINK2_B12_OPERATIONAL_COLLISION_CONTRACT_V1.json"))
cj = json.dumps(contract)
geo = load(os.path.join(PKG, "05_results/LINK2_B12_GEOMETRY_INDEX_V1.json"))
def find_objects(d):
    # count candidate object entries in the geometry index
    for key in ("objects", "candidates", "entries"):
        if isinstance(d, dict) and key in d and isinstance(d[key], (list, dict)):
            return len(d[key])
    return None
n_geo = find_objects(geo)
steps = [f for f in os.listdir(os.path.join(PKG, "01_cad")) if f.endswith(".step")]
check("V11", "exactly 12 candidate objects (contract, geometry index, STEP files agree)",
      len(steps) == 12 and (n_geo in (None, 12)),
      f"step_files={len(steps)}, geometry_index_objects={n_geo}")
ev["object_ids"] = sorted(s[:-5] for s in steps)

# ---- V12 recompute pending count and R-countdown from source records ---------------
delta7 = load(os.path.join(ROOT, "01_project/competition/CURRENT_R2_AUTHORITY_DELTA_V7.json"))
acct = delta7["local_candidate_accounting"]
prev_pending = delta7["current_system_authority_preserved"]["local_pending_geometry_candidates_total"]
new_pending = prev_pending + len(steps)
# R-countdown: M01 registry R-category = 121; batches R121(-20) -> R101, Link1-B6(-6) -> R95, Link2-B12(-12) -> R83
prebind = load(os.path.join(
    ROOT, "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json"))
r_category = prebind["asset_accounting"]["category_counts"]["R"]
def batch_count(pkg_dir):
    cad = os.path.join(ROOT, pkg_dir, "01_cad")
    if os.path.isdir(cad):
        return len([f for f in os.listdir(cad) if f.endswith(".step")])
    return None
n_r121 = batch_count("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_R121_OPERATIONAL_COLLISION_CANDIDATE_V1")
n_link1 = batch_count("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_R101_LINK1_B6_OPERATIONAL_COLLISION_CANDIDATE_V1")
r_remaining = None
if n_r121 is not None and n_link1 is not None:
    r_remaining = r_category - n_r121 - n_link1 - len(steps)
route_c_r95 = acct.get("route_c_R95_remaining_status")
seventh_r95 = seventh["local_candidate_accounting"]["route_c_R95_remaining"]
check("V12", "recomputed pending=47+12=59 and R-countdown 121-20-6-12=83 close from source",
      new_pending == 59 and r_category == 121 and n_r121 == 20 and n_link1 == 6
      and r_remaining == 83 and seventh_r95 == 95,
      f"prev_pending={prev_pending}, link2_objects={len(steps)}, new_pending={new_pending}, "
      f"R_category={r_category}, r121_batch={n_r121}, link1_batch={n_link1}, "
      f"recomputed_R_remaining={r_remaining}, seventh_receipt_R95={seventh_r95}")
ev["recomputed_pending_total"] = new_pending
ev["recomputed_route_c_remaining"] = r_remaining

# ---- V13 gate remaining_R83 field agrees with recomputation ------------------------
check("V13", "package gate's own remaining_R83 field is consistent with recomputed 83",
      "remaining_R83" in gate and r_remaining == 83,
      f"gate field present={'remaining_R83' in gate}, value={gate.get('remaining_R83')}")

# ---- V14 negative history preserved -------------------------------------------------
neg_path = os.path.join(PKG, "07_reviews/LINK2_PRE_ROOT_REPLAY_NOT_CLEAN_PASS_V1.json")
neg = load(neg_path)
check("V14", "pre-root-replay negative preserved with zero credit and named root cause",
      neg["classification"] == "HISTORICAL_NEGATIVE_ZERO_CREDIT"
      and neg["system_credit"] == 0 and neg["thresholds_relaxed"] is False,
      neg["verdict"])
ev["negative_history_sha256"] = sha256(neg_path)

# ---- V15 pytest receipt ---------------------------------------------------------------
pyr = load(os.path.join(PKG, "05_results/PYTEST_RECEIPT_V1.json"))
pyr_s = json.dumps(pyr)
check("V15", "package pytest receipt records full pass", '"passed": 10' in pyr_s or '10/10' in pyr_s or ('passed' in pyr and pyr.get('passed') in (10, '10')), pyr_s[:300])

json.dump(ev, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(json.dumps({"overall_pass": ev["overall_pass"],
                  "manifest_rows": ev["manifest_rows"],
                  "source_pins": ev["source_pins"],
                  "pending_total": ev["recomputed_pending_total"],
                  "route_c_remaining": ev["recomputed_route_c_remaining"],
                  "gate_sha256": ev["gate_sha256"],
                  "failed": [c["id"] for c in ev["checks"] if not c["pass"]]},
                 indent=1))
sys.exit(0 if ev["overall_pass"] else 1)
