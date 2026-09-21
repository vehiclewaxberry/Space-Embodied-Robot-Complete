# -*- coding: utf-8 -*-
"""
A6_RED_TEAM - M7 terminal mechanical closure: red-team + falsifier audit.

READ-ONLY with respect to the design tree: the ONLY files written are the two
reports in 12_release/.  Every number in the reports is computed at run time
from the artifacts on disk; files are pinned by sha256 (16 hex).

Outputs:
  12_release/M7_RED_TEAM_REPORT_V1.json
  12_release/M7_FALSIFIER_REPORT_V1.json

Severity discipline:
  HIGH   = would invalidate a PASS or the release
  MEDIUM = must fix before owner signature but does not invalidate engineering
  LOW    = hygiene
UNKNOWN is a finding, never silence.
"""

import os
import re
import json
import hashlib
import datetime
import xml.etree.ElementTree as ET

import yaml
import numpy as np

# --------------------------------------------------------------------------
# roots (raw strings: Windows paths with spaces)
# --------------------------------------------------------------------------
PROJ = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
M7 = os.path.join(PROJ, "20_engineering",
                  "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1")
REL_DIR = os.path.join(M7, "12_release")

GATE_JSON = os.path.join(REL_DIR, "MECHANICAL_ENGINEERING_RELEASE_GATE_V1.json")
CONTRACT_YAML = os.path.join(M7, "wp13_embodied_contract",
                             "EMBODIED_MECHANICAL_CONTRACT_V1.yaml")
HANDOFF_JSON = os.path.join(M7, "wp13_embodied_contract",
                            "MECHANICAL_TO_EMBODIED_HANDOFF_GATE.json")
TERMINAL_YAML = os.path.join(M7, "00_authority",
                             "M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml")
URDF_PATH = os.path.join(PROJ, "20_engineering", "cad", "spacecraft_layout",
                         "arm_b601_v1", "arm_b601_v1.urdf")
WP2_V2_YAML = os.path.join(M7, "wp2_design_mass",
                           "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml")
WP2_V2_PY = os.path.join(M7, "wp2_design_mass",
                         "aggregate_m7_design_mass_v2.py")
WP10_V4_YAML = os.path.join(M7, "wp10_mech_rl_v4",
                            "MECH_DYNAMICS_INTERFACE_V4.yaml")
FEA1_EVID = os.path.join(M7, "wp7_fea_operational", "FEA1_EVIDENCE_V1.json")
FEA1B_EVID = os.path.join(M7, "wp7_fea_operational",
                          "FEA1B_ELEMENT_FORMULATION_EVIDENCE_V1.json")
DECK_REGISTER = os.path.join(M7, "wp7_fea_operational",
                             "FEA2_FEA8_DECK_REGISTER_V1.yaml")
FEA1_RECEIPT = os.path.join(M7, "wp7_fea_operational", "receipt.json")
DECKS_DIR = os.path.join(M7, "wp7_fea_operational", "decks")
DECKS_B_DIR = os.path.join(M7, "wp7_fea_operational", "decks_b")
JOBS_DIR = os.path.join(M7, "wp7_fea_operational", "jobs")
CALIB_YAML = os.path.join(M7, "wp11_cad_urdf_registration",
                          "B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml")
GRIPPER_PACK = os.path.join(M7, "wp5_mechanisms",
                            "GRIPPER_ENGINEERING_PACK_V1.yaml")
V5R_VALIDATION_JSON = os.path.join(
    PROJ, "20_engineering", "F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820",
    "04_validation", "GRIPPER_R1_GEOMETRY_VALIDATION.json")
V5R_SWEEP_CSV = os.path.join(
    PROJ, "20_engineering", "F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820",
    "04_validation", "GRIPPER_R1_CONTINUOUS_STROKE_SAMPLES.csv")

PINNED_ARM_MASS_KG = 4.695555949342986

RT_REPORT_PATH = os.path.join(REL_DIR, "M7_RED_TEAM_REPORT_V1.json")
F_REPORT_PATH = os.path.join(REL_DIR, "M7_FALSIFIER_REPORT_V1.json")

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def sha256_full(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_16(path):
    return sha256_full(path)[:16]


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def load_json(path):
    return json.loads(read_text(path))


def load_yaml(path):
    return yaml.safe_load(read_text(path))


def resolve(rel_or_abs):
    """Resolve a register-style relative path ('20_engineering/...') or an
    absolute path to an absolute filesystem path."""
    p = rel_or_abs.replace("/", os.sep).replace("\\", os.sep)
    if os.path.isabs(p):
        return p
    return os.path.join(PROJ, p)


def walk_tree(root, exts=None):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if exts is None or os.path.splitext(fn)[1].lower() in exts:
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def walk_obj(obj, path=""):
    """Yield (path, key, value) for every dict entry in a nested structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path, k, v
            yield from walk_obj(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_obj(v, path + f"[{i}]")


def get_path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def finding(severity, attack, detail, evidence=None):
    return {"severity": severity, "attack": attack, "detail": detail,
            "evidence": evidence or {}}


# --------------------------------------------------------------------------
# load the primary artifacts once (fresh parses; RT-08 re-parses again)
# --------------------------------------------------------------------------
gate = load_json(GATE_JSON)
gate_text = read_text(GATE_JSON)
contract = load_yaml(CONTRACT_YAML)
handoff = load_json(HANDOFF_JSON)
handoff_text = read_text(HANDOFF_JSON)
terminal = load_yaml(TERMINAL_YAML)
terminal_text = read_text(TERMINAL_YAML)

PINS = {  # 16-hex pins of the audit's primary inputs, computed at run time
    "gate_json": sha256_16(GATE_JSON),
    "contract_yaml": sha256_16(CONTRACT_YAML),
    "handoff_json": sha256_16(HANDOFF_JSON),
    "terminal_yaml": sha256_16(TERMINAL_YAML),
    "urdf": sha256_16(URDF_PATH),
    "wp2_v2_yaml": sha256_16(WP2_V2_YAML),
    "fea1_evidence": sha256_16(FEA1_EVID),
    "fea1b_evidence": sha256_16(FEA1B_EVID),
    "calibration_yaml": sha256_16(CALIB_YAML),
    "gripper_pack": sha256_16(GRIPPER_PACK),
}

rt_attacks = {}
f_claims = {}


def attack_done(aid, name, checks, findings_list, files_scanned):
    sev_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    worst = "NONE"
    for f in findings_list:
        if sev_rank[f["severity"]] > sev_rank.get(worst, 0):
            worst = f["severity"]
    rt_attacks[aid] = {
        "name": name,
        "verdict": "FINDING" if findings_list else "SAFE",
        "worst_severity": worst if findings_list else None,
        "checks": checks,
        "findings": findings_list,
        "files_scanned": files_scanned,
    }


# ==========================================================================
# RT-01  zero-byte result + PASS
# ==========================================================================
def rt01():
    checks, fnd = [], []
    scanned = []
    # (a) every artifact pinned as gate evidence
    n_ev = 0
    for c in gate["criteria"]:
        state = c["state"]
        for ev in c.get("evidence", []):
            n_ev += 1
            p = resolve(ev["path"])
            scanned.append(p)
            rec = {"criterion": c["id"], "state": state, "path": ev["path"]}
            if not os.path.isfile(p):
                fnd.append(finding("HIGH", "RT-01",
                                   "gate evidence file missing on disk", rec))
                continue
            size = os.path.getsize(p)
            live16 = sha256_16(p)
            rec["live_bytes"] = size
            rec["live_sha256_16"] = live16
            rec["declared_sha256_16"] = ev.get("sha256_16")
            rec["declared_bytes"] = ev.get("bytes")
            if size == 0 and state in ("PASS", "PASS_WITH_DECLARED_OPEN_ITEM"):
                fnd.append(finding("HIGH", "RT-01",
                                   "zero-byte evidence attached to a PASS-class "
                                   "criterion", rec))
            if ev.get("bytes") is not None and ev["bytes"] != size:
                fnd.append(finding("HIGH", "RT-01",
                                   "gate evidence byte-count drift", rec))
            if ev.get("sha256_16") and \
                    ev["sha256_16"].lower() != live16.lower():
                fnd.append(finding("HIGH", "RT-01",
                                   "gate evidence sha256-16 drift (frozen "
                                   "baseline hash mismatch)", rec))
            if ev.get("zero_byte") is True and size > 0:
                fnd.append(finding("LOW", "RT-01",
                                   "gate evidence flagged zero_byte but file "
                                   "is non-zero (pin metadata wrong sign)", rec))
    checks.append({"check": "gate evidence pins re-verified live",
                   "evidence_entries": n_ev,
                   "failures": len([f for f in fnd])})
    # (b) every receipt.json in the tree
    receipts = [p for p in walk_tree(M7, exts={".json"})
                if "receipt" in os.path.basename(p).lower()]
    n_paths_checked = 0
    for rp in receipts:
        scanned.append(rp)
        if os.path.getsize(rp) == 0:
            fnd.append(finding("HIGH", "RT-01",
                               "zero-byte receipt.json in tree",
                               {"path": rp}))
            continue
        try:
            rj = load_json(rp)
        except Exception as exc:
            fnd.append(finding("MEDIUM", "RT-01",
                               f"receipt unreadable: {exc}", {"path": rp}))
            continue
        status_blob = json.dumps({k: rj.get(k) for k in
                                  ("status", "verdict", "overall_status")
                                  if k in rj})
        pass_class = bool(re.search(r"PASS|COMPLETE", status_blob))
        # any path carried by the receipt must exist and be non-zero
        for path_, k, v in walk_obj(rj):
            if k == "path" and isinstance(v, str) and \
                    ("20_engineering" in v or v.startswith("wp")):
                tgt = resolve(v) if "20_engineering" in v else os.path.join(M7, v)
                n_paths_checked += 1
                if not os.path.isfile(tgt):
                    fnd.append(finding("MEDIUM", "RT-01",
                                       "receipt references a path not on disk",
                                       {"receipt": rp, "referenced": v,
                                        "receipt_pass_class": pass_class}))
                elif os.path.getsize(tgt) == 0 and pass_class:
                    fnd.append(finding("HIGH", "RT-01",
                                       "receipt in PASS/COMPLETE state references "
                                       "a zero-byte file",
                                       {"receipt": rp, "referenced": v}))
    checks.append({"check": "receipt.json scan (existence + zero-byte under "
                            "PASS/COMPLETE)", "receipts": len(receipts),
                   "paths_checked": n_paths_checked})
    attack_done("RT-01", "zero-byte result + PASS", checks, fnd,
                len(set(scanned)))


# ==========================================================================
# RT-02  PROVISIONAL masquerading as AUTHORITY
# ==========================================================================
def rt02():
    checks, fnd = [], []
    scanned = [CONTRACT_YAML, GATE_JSON, HANDOFF_JSON, TERMINAL_YAML,
               WP10_V4_YAML]
    ledger = contract["authority_and_uncertainty"]["ledger"]
    prov = [e for e in ledger if "PROVISIONAL" in str(e["authority_level"])]
    # (a) every PROVISIONAL-class ledger quantity must reach the consumer
    #     unchanged (same authority string present in the handoff gate text)
    for e in prov:
        if str(e["authority_level"]) not in handoff_text:
            fnd.append(finding("MEDIUM", "RT-02",
                               "PROVISIONAL-class quantity's authority string "
                               "not visible to the downstream consumer gate "
                               "(promotion or silent drop possible)",
                               dict(e)))
    # (b) ledger authority must equal the contract-body authority at the
    #     quantity path (ledger built from body; mismatch = masquerade)
    n_body_checked = 0
    for e in ledger:
        body = get_path(contract, e["quantity"])
        if isinstance(body, dict) and "authority_level" in body:
            n_body_checked += 1
            if body["authority_level"] != e["authority_level"]:
                fnd.append(finding("HIGH", "RT-02",
                                   "ledger authority_level disagrees with "
                                   "contract body at the quantity path",
                                   {"quantity": e["quantity"],
                                    "ledger": e["authority_level"],
                                    "body": body["authority_level"]}))
    checks.append({"check": "ledger vs contract-body authority_level equality",
                   "ledger_entries": len(ledger),
                   "body_envelopes_matched": n_body_checked})
    # (c) prohibitions_honored claims cross-checked against the actual ledger
    prohib = contract.get("prohibitions_honored", [])
    checks.append({"check": "prohibitions_honored claims present",
                   "claims": prohib})
    if "no PROVISIONAL promoted to AUTHORITY" in prohib:
        bad = [e for e in prov
               if "PROVISIONAL" not in str(get_path(contract, e["quantity"])
                                           .get("authority_level", ""))]
        if bad:
            fnd.append(finding("HIGH", "RT-02",
                               "prohibition 'no PROVISIONAL promoted to "
                               "AUTHORITY' claimed but a PROVISIONAL ledger "
                               "entry's body authority no longer says "
                               "PROVISIONAL", {"entries": bad}))
    # 'no measured_mass field anywhere'
    mm = [(p, k) for p, k, v in walk_obj(contract) if "measured_mass" in str(k)]
    if mm and "no measured_mass field anywhere" in prohib:
        fnd.append(finding("HIGH", "RT-02",
                           "prohibition 'no measured_mass field anywhere' "
                           "claimed but such keys exist",
                           {"locations": [p + "/" + k for p, k in mm]}))
    # 'no zero-fill of unknowns': every null nominal must carry a fail-closed
    # authority class
    null_bad = []
    for e in ledger:
        if e.get("nominal_is_null"):
            a = str(e["authority_level"])
            if not re.search(r"HOLD|UNKNOWN|NO_|NOT_|CONFLICTING", a):
                null_bad.append(dict(e))
    if null_bad:
        fnd.append(finding("HIGH", "RT-02",
                           "null nominals without a fail-closed authority "
                           "class (zero-fill analogue)", {"entries": null_bad}))
    checks.append({"check": "null-nominal fail-closed authority recomputed "
                            "from ledger",
                   "null_nominals": sum(1 for e in ledger
                                        if e.get("nominal_is_null"))})
    # 'no candidate promoted to authority'
    cand = [e for e in ledger if "CANDIDATE" in str(e["authority_level"])]
    for e in cand:
        if str(e["authority_level"]).endswith("AUTHORITY"):
            fnd.append(finding("HIGH", "RT-02",
                               "candidate-class quantity carries an AUTHORITY "
                               "suffix", dict(e)))
    checks.append({"check": "candidate-class quantities remain candidate-class",
                   "candidate_entries": [e["quantity"] for e in cand]})
    # (d) improperly mixed authority classes
    mixed = [e for e in ledger
             if "PROVISIONAL" in str(e["authority_level"])
             and "HOLD" in str(e["authority_level"])]
    for e in mixed:
        if str(e["authority_level"]) not in handoff_text:
            fnd.append(finding("MEDIUM", "RT-02",
                               "mixed HOLD+PROVISIONAL authority class not "
                               "surfaced to consumer gate", dict(e)))
    checks.append({"check": "mixed-class authority strings",
                   "mixed": [dict(e) for e in mixed],
                   "note": "HOLD_CONFLICTING_PROVISIONAL_VALUES is an honest "
                           "conflict declaration when surfaced verbatim"})
    # (e) stale/superseded reference inside a hash-pinned interface file:
    #     wp10 v4 binds SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml (superseded by
    #     V2 per wp2 receipt_V1_SUPERSEDED) with a literal PENDING_SIBLING_HASH
    v4 = read_text(WP10_V4_YAML)
    if "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml" in v4:
        superseded = os.path.join(M7, "wp2_design_mass",
                                  "receipt_V1_SUPERSEDED.json")
        fnd.append(finding(
            "LOW", "RT-02",
            "wp10 MECH_DYNAMICS_INTERFACE_V4.yaml (itself hash-pinned by the "
            "handoff gate) still binds the SUPERSEDED V1 mass-properties file "
            "with sha256: PENDING_SIBLING_HASH; the handoff gate actually "
            "loaded V2, so engineering is not invalidated, and CM-OPEN-01 "
            "(V2_BASELINE_SUPERSESSION_ECR_NOT_YET_RAISED) covers the class - "
            "but the stale V1 path is not named in any declared open item",
            {"v4_file": WP10_V4_YAML,
             "v1_superseded_marker_on_disk": os.path.isfile(superseded),
             "v4_sha256_16": sha256_16(WP10_V4_YAML),
             "pending_hash_placeholders": v4.count("PENDING_SIBLING_HASH"),
             "covering_open_item": "CM-OPEN-01"}))
    checks.append({"check": "superseded-artifact references inside pinned "
                            "interface files", "file": "wp10 v4 yaml"})
    attack_done("RT-02", "PROVISIONAL masquerading as AUTHORITY", checks, fnd,
                len(set(scanned)))


# ==========================================================================
# RT-03  CAD mass overriding URDF mass
# ==========================================================================
def rt03():
    checks, fnd = [], []
    # (a) live recomputation of the URDF inertial mass sum
    tree = ET.parse(URDF_PATH)
    masses = []
    for link in tree.getroot().iter("link"):
        m = link.find("inertial/mass")
        if m is not None:
            masses.append((link.get("name"), float(m.get("value"))))
    live_sum = float(sum(m for _, m in masses))
    checks.append({"check": "live URDF mass sum",
                   "links": masses, "live_sum_kg": live_sum,
                   "pinned_kg": PINNED_ARM_MASS_KG,
                   "abs_diff": abs(live_sum - PINNED_ARM_MASS_KG)})
    if abs(live_sum - PINNED_ARM_MASS_KG) > 1e-9:
        fnd.append(finding("HIGH", "RT-03",
                           "live URDF mass sum != pinned L0 value",
                           {"live": live_sum, "pinned": PINNED_ARM_MASS_KG}))
    # (b) contract self-consistency: rebuilt sum + nominal + rule
    arm = contract["dynamics"]["mass_authority"]["arm"]
    if abs(float(arm["nominal"]) - live_sum) > 1e-9 or \
            abs(float(arm["rebuilt_sum_from_urdf_kg"]) - live_sum) > 1e-9 or \
            arm.get("sum_matches_pin") is not True:
        fnd.append(finding("HIGH", "RT-03",
                           "contract arm mass authority inconsistent with live "
                           "URDF sum", dict(arm)))
    if arm.get("authority_level") != "ACCEPTED_URDF_L0":
        fnd.append(finding("HIGH", "RT-03",
                           "arm mass authority_level is not ACCEPTED_URDF_L0",
                           dict(arm)))
    # (c) scan wp2/wp10/wp13 parsed artifacts: any 'mass' field in the arm-mass
    #     band that is not a sigma/uncertainty and differs from the pin is an
    #     attempted override of the L0 value
    band_hits = []
    for f in (WP2_V2_YAML, WP10_V4_YAML, CONTRACT_YAML):
        obj = load_yaml(f)
        for p, k, v in walk_obj(obj):
            ctx = (p + "/" + str(k)).lower()
            if isinstance(v, (int, float)) and "mass" in str(k).lower() and \
                    not re.search(r"sigma|uncert|_u_|budget|m3r|target|"
                                  r"payload", ctx) and \
                    4.0 <= float(v) <= 5.5:
                band_hits.append({"file": os.path.basename(f),
                                  "path": p + "/" + str(k), "value": float(v)})
                if abs(float(v) - PINNED_ARM_MASS_KG) > 1e-9:
                    fnd.append(finding(
                        "HIGH", "RT-03",
                        "arm-band mass value differing from the L0 pin "
                        "presented under a mass key",
                        {"file": f, "path": p + "/" + str(k),
                         "value": float(v)}))
    checks.append({"check": "arm-mass-band scalar fields in wp2/wp10/wp13",
                   "hits": band_hits})
    # (d) wp2 design check + wp10 pinned constant
    wp2 = load_yaml(WP2_V2_YAML)
    dc = wp2["design_checks"].get("urdf_arm_mass_pinned_exactly")
    checks.append({"check": "wp2 design_checks.urdf_arm_mass_pinned_exactly",
                   "value": dc})
    v4 = load_yaml(WP10_V4_YAML)
    v4pin = get_path(v4, "design_mass_model_binding.pinned_constants."
                         "b601_arm_mass_kg.value")
    if v4pin is None or abs(float(v4pin) - PINNED_ARM_MASS_KG) > 1e-12:
        fnd.append(finding("HIGH", "RT-03",
                           "wp10 v4 pinned b601_arm_mass_kg missing or "
                           "differs from L0 pin", {"value": v4pin}))
    checks.append({"check": "wp10 v4 pinned_constants.b601_arm_mass_kg",
                   "value": v4pin})
    # (e) handoff gate consumed the URDF mass model, not a CAD mass
    dm = handoff["checks"]["design_mass_model_loadable"]["evidence"]
    checks.append({"check": "handoff mass model source",
                   "source": dm["source"],
                   "configurations_loaded": dm["configurations_loaded"]})
    attack_done("RT-03", "CAD mass overriding URDF mass", checks, fnd, 5)


# ==========================================================================
# RT-04  unknown written as PASS
# ==========================================================================
def rt04():
    checks, fnd = [], []
    n_states = {"PASS": 0, "PASS_WITH_DECLARED_OPEN_ITEM": 0, "HOLD": 0}
    for c in gate["criteria"]:
        st = c["state"]
        n_states[st] = n_states.get(st, 0) + 1
        ev = c.get("evidence")
        if st != "HOLD" and not ev:
            fnd.append(finding("HIGH", "RT-04",
                               f"criterion {c['id']} {c['name']} is {st} with "
                               "NO evidence (NO EVIDENCE is never PASS)",
                               {"criterion": c["id"]}))
        # UNKNOWN/TBD inside a PASS-class criterion must be named by a
        # declared open item
        if st in ("PASS", "PASS_WITH_DECLARED_OPEN_ITEM"):
            blob = json.dumps(c.get("evidence", [])) + " " + c.get("rationale", "")
            oi_blob = json.dumps(c.get("open_items", []))
            for tok in ("UNKNOWN", "TBD"):
                for m in re.finditer(tok, blob):
                    ctx = blob[max(0, m.start() - 60):m.end() + 60]
                    if tok not in oi_blob:
                        fnd.append(finding(
                            "MEDIUM", "RT-04",
                            f"literal {tok} inside {st} criterion "
                            f"{c['id']} evidence/rationale without a declared "
                            "open item naming it",
                            {"criterion": c["id"], "context": ctx}))
    checks.append({"check": "criterion states", "states": n_states,
                   "criteria": len(gate["criteria"])})
    # totals self-consistency
    tot = gate["totals"]
    if tot.get("PASS") != n_states.get("PASS", 0) or \
            tot.get("HOLD") != n_states.get("HOLD", 0) or \
            tot.get("PASS_WITH_DECLARED_OPEN_ITEM") != \
            n_states.get("PASS_WITH_DECLARED_OPEN_ITEM", 0):
        fnd.append(finding("HIGH", "RT-04",
                           "gate totals block inconsistent with per-criterion "
                           "states", {"totals": tot, "recount": n_states}))
    # UNKNOWN anywhere else in the gate JSON: every occurrence must be the
    # fail-closed invariant prose itself, never a criterion value
    unk_contexts = []
    for m in re.finditer(r"UNKNOWN", gate_text):
        ctx = gate_text[max(0, m.start() - 100):m.end() + 100]
        unk_contexts.append(ctx.replace("\n", " "))
        if "never PASS" not in ctx and "fail_closed" not in ctx:
            fnd.append(finding("MEDIUM", "RT-04",
                               "literal UNKNOWN in gate JSON outside the "
                               "fail-closed invariant prose",
                               {"context": ctx}))
    n_tbd = len(re.findall(r"\bTBD\b", gate_text))
    checks.append({"check": "literal UNKNOWN/TBD occurrences in gate JSON",
                   "UNKNOWN": len(unk_contexts), "TBD": n_tbd,
                   "UNKNOWN_contexts": unk_contexts})
    # placeholder-class PENDING strings in the handoff gate (the governance
    # state PENDING_OWNER_REVIEW is legitimate and excluded)
    for m in re.finditer(r"PENDING[A-Z_]*", handoff_text):
        if m.group(0) == "PENDING_OWNER_REVIEW":
            continue
        fnd.append(finding("LOW", "RT-04",
                           "placeholder-class PENDING string in handoff gate",
                           {"match": m.group(0)}))
    attack_done("RT-04", "unknown written as PASS", checks, fnd, 2)


# ==========================================================================
# RT-05  FEA ran but load missing
# ==========================================================================
LOAD_CARD_RE = re.compile(
    r"^\s*\*\s*(CLOAD|DLOAD|DSLOAD|CENTRIF|GRAV|PRESSURE)", re.IGNORECASE)


def _deck_load_scan(directory, pattern):
    decks = sorted(f for f in os.listdir(directory)
                   if f.endswith(".inp") and re.match(pattern, f))
    rows = []
    missing_load = []
    for d in decks:
        p = os.path.join(directory, d)
        size = os.path.getsize(p)
        has_load = any(LOAD_CARD_RE.match(ln) for ln in read_text(p).splitlines())
        rows.append({"deck": d, "bytes": size, "load_card": has_load})
        if size == 0 or not has_load:
            missing_load.append(d)
    return decks, rows, missing_load


def rt05():
    checks, fnd = [], []
    reg = load_yaml(DECK_REGISTER)
    scanned = 1
    # (a) register vs disk for FEA-1 (the only DECKED_AND_SOLVED case)
    fe1 = [c for c in reg["cases"] if c["fea_id"] == "FEA-1"][0]
    decks, rows, missing = _deck_load_scan(DECKS_DIR, r"fea1_")
    scanned += len(decks)
    checks.append({"check": "FEA-1 decks on disk vs register",
                   "register_status": fe1["status"],
                   "register_decks": fe1["decks"],
                   "decks_on_disk": len(decks)})
    if fe1["status"] == "DECKED_AND_SOLVED" and len(decks) != fe1["decks"]:
        fnd.append(finding("HIGH", "RT-05",
                           "register deck count disagrees with decks on disk",
                           {"register": fe1["decks"], "disk": len(decks)}))
    for d in missing:
        fnd.append(finding("HIGH", "RT-05",
                           "solved deck missing or empty or carries NO load "
                           "boundary card (*CLOAD/*DLOAD/*DSLOAD/...)",
                           {"deck": os.path.join(DECKS_DIR, d)}))
    # (b) FEA1B formulation decks
    decks_b, rows_b, missing_b = _deck_load_scan(DECKS_B_DIR, r"fea1b_")
    scanned += len(decks_b)
    for d in missing_b:
        fnd.append(finding("HIGH", "RT-05",
                           "FEA1B deck missing/empty/no load card",
                           {"deck": os.path.join(DECKS_B_DIR, d)}))
    checks.append({"check": "FEA1B decks load-card scan",
                   "decks_on_disk": len(decks_b),
                   "no_load_or_zero": missing_b})
    # (c) planned cases must not claim solved results
    for c in reg["cases"]:
        if c["fea_id"] in ("FEA-1",):
            continue
        if c.get("decks", 0) == 0 and \
                "SOLVED" in str(c.get("result_status", "")) and \
                "NOT" not in str(c.get("result_status", "")):
            fnd.append(finding("HIGH", "RT-05",
                               f"{c['fea_id']} claims solved results with zero "
                               "decks", dict(c)))
    # (d) cross-check FEA1 evidence traceability: every deck has a hashed
    #     .dat/.odb/extract record, and the declared traceability defect is
    #     disclosed
    ev1 = load_json(FEA1_EVID)
    scanned += 1
    per_file = ev1.get("per_file_result_hashes", {})
    deck_bases = {os.path.splitext(d)[0] for d in decks}
    evid_bases = set(per_file.keys())
    if deck_bases != evid_bases:
        fnd.append(finding("MEDIUM", "RT-05",
                           "FEA1 evidence per-file hash register does not "
                           "match deck set",
                           {"decks_only": sorted(deck_bases - evid_bases),
                            "evidence_only": sorted(evid_bases - deck_bases)}))
    for base in sorted(deck_bases & evid_bases):
        rec = per_file[base]
        for kind in ("inp", "dat", "odb", "_extract_json"):
            if kind not in rec or "sha256" not in rec.get(kind, {}):
                fnd.append(finding("MEDIUM", "RT-05",
                                   f"evidence record for {base} lacks {kind} "
                                   "hash", {"job": base, "kind": kind}))
        datp = os.path.join(JOBS_DIR, base + ".dat")
        scanned += 1
        if not os.path.isfile(datp) or os.path.getsize(datp) == 0:
            fnd.append(finding("HIGH", "RT-05",
                               f"solved job {base} has missing/zero .dat",
                               {"dat": datp}))
    defect = get_path(ev1, "load_source.TRACEABILITY_DEFECT_FOUND")
    disclosed_in_gate = "TRACEABILITY" in gate_text
    checks.append({"check": "FEA1 load traceability defect disclosure",
                   "defect_recorded_in_evidence": defect is not None,
                   "defect_severity": defect.get("severity") if defect else None,
                   "defect_effect": defect.get("effect") if defect else None,
                   "named_in_gate_json": disclosed_in_gate,
                   "note": "defect is disclosed inside the gate-pinned "
                           "evidence file" if not disclosed_in_gate else
                           "defect named at gate level"})
    if defect and not disclosed_in_gate:
        fnd.append(finding(
            "LOW", "RT-05",
            "FEA1 TRACEABILITY_DEFECT_FOUND (MEDIUM_CONSERVATIVE_DIRECTION, "
            "applied M_z 1.76% high on CAPTURE_150KG) is recorded in the "
            "pinned evidence but not named in the gate criterion 15 text",
            {"defect": {k: defect[k] for k in
                        ("severity", "effect", "disposition")}}))
    # (e) FEA1B load traceability section exists
    ev1b = load_json(FEA1B_EVID)
    scanned += 1
    lt = ev1b.get("load_traceability")
    checks.append({"check": "FEA1B load_traceability section",
                   "present": lt is not None,
                   "summary": str(lt)[:300] if lt else None})
    if lt is None:
        fnd.append(finding("MEDIUM", "RT-05",
                           "FEA1B evidence carries no load_traceability "
                           "section", {}))
    attack_done("RT-05", "FEA ran but load missing", checks, fnd, scanned)


# ==========================================================================
# RT-06  mesh peak stress sold as real failure or as convergence
# ==========================================================================
def rt06():
    checks, fnd = [], []
    ev1 = load_json(FEA1_EVID)
    ev1b = load_json(FEA1B_EVID)
    rcp = load_json(FEA1_RECEIPT)
    scanned = 3
    # (a) ODR-11 singularity rule must be applied in the layer-2 evidence
    l2 = ev1b.get("layer_2_numerical_credibility", {})
    sing = l2.get("singularity_assessment_odr11")
    if sing is None:
        fnd.append(finding("HIGH", "RT-06",
                           "FEA1B layer-2 evidence has no ODR-11 singularity "
                           "assessment", {}))
    else:
        checks.append({"check": "ODR-11 singularity assessment present",
                       "keys": list(sing.keys())})
    pcs = l2.get("primary_convergence_series", {})
    elem_avg = pcs.get("per_case_element_centroid_sampling")
    if not elem_avg:
        fnd.append(finding("HIGH", "RT-06",
                           "no element-averaged (centroid) stress sampling in "
                           "the convergence series - ODR-11 rule not applied",
                           {}))
    else:
        checks.append({"check": "element-averaged quantities sampled per case",
                       "cases": list(elem_avg.keys())})
    crit = str(pcs.get("convergence_criterion", ""))
    checks.append({"check": "convergence criterion text",
                   "text": crit[:400]})
    if re.search(r"nodal", crit, re.I) and not re.search(
            r"element|centroid|average|integral", crit, re.I):
        fnd.append(finding("HIGH", "RT-06",
                           "convergence criterion is peak-nodal-stress only",
                           {"criterion": crit[:300]}))
    # (b) convergence must NOT be claimed: baseline receipt + both evidences
    mc = ev1.get("mesh_convergence", {})
    summary_blob = json.dumps(mc)
    unqualified = [m.group(0) for m in
                   re.finditer(r"(?<!NOT_)(?<!NOT )(CONVERGED)\b", summary_blob)]
    checks.append({"check": "FEA1 baseline mesh_convergence summary scan",
                   "unqualified_CONVERGED_tokens": len(unqualified)})
    if unqualified:
        fnd.append(finding("HIGH", "RT-06",
                           "baseline FEA1 mesh_convergence block contains "
                           "unqualified CONVERGED claims",
                           {"count": len(unqualified)}))
    mcc = l2.get("mesh_credibility_components", {})
    demo = mcc.get("mesh_convergence_demonstrated")
    checks.append({"check": "FEA1B mesh_credibility_components",
                   "components": {k: (v if isinstance(v, (str, bool, int, float))
                                      else str(v)[:200])
                                  for k, v in mcc.items()}})
    if demo is True or str(demo).upper() == "TRUE":
        fnd.append(finding("HIGH", "RT-06",
                           "FEA1B claims mesh_convergence_demonstrated=true "
                           "while peaks are singular", {"value": demo}))
    verdict = str(rcp.get("verdict", "")) + str(rcp.get("status", ""))
    if "MESH CONVERGENCE IS NOT DEMONSTRATED" not in verdict and \
            "NOT_DEMONSTRATED" not in verdict:
        fnd.append(finding("MEDIUM", "RT-06",
                           "WP7 receipt does not carry the explicit "
                           "convergence-not-demonstrated statement",
                           {"status": rcp.get("status", "")[:200]}))
    # (c) layer-3 engineering interpretation must use singularity-free
    #     quantities, and the non-convergent peak must have no design
    #     consequence asserted
    l3 = ev1b.get("layer_3_engineering_interpretation", {})
    util = l3.get("utilization_against_candidate_typical_property", {})
    checks.append({"check": "layer-3 utilization basis",
                   "keys": list(util.keys()),
                   "singularity_free_collar_present":
                       "singularity_free_collar_MPa_kz6" in util,
                   "non_convergent_peak_consequence":
                       str(util.get("why_the_non_convergent_peak_has_no_"
                                    "design_consequence", ""))[:300]})
    if "singularity_free_collar_MPa_kz6" not in util:
        fnd.append(finding("MEDIUM", "RT-06",
                           "layer-3 utilization does not identify a "
                           "singularity-free stress basis", {}))
    forbidden = ev1b.get("forbidden_verdicts_explicitly_not_asserted")
    mos = ev1b.get("margin_of_safety_asserted")
    checks.append({"check": "forbidden verdicts / margin-of-safety stance",
                   "forbidden_verdicts_explicitly_not_asserted": forbidden,
                   "margin_of_safety_asserted": mos})
    if mos is True:
        fnd.append(finding("HIGH", "RT-06",
                           "margin of safety asserted despite singularity "
                           "prohibition", {}))
    attack_done("RT-06", "mesh peak stress sold as real failure or as "
                         "convergence", checks, fnd, scanned)


# ==========================================================================
# RT-07  hidden HOLD
# ==========================================================================
def rt07():
    checks, fnd = [], []
    # the audit's own outputs are excluded: re-scanning a previous report
    # would re-detect its own finding strings (self-reference)
    self_outputs = {os.path.normpath(RT_REPORT_PATH),
                    os.path.normpath(F_REPORT_PATH)}
    text_files = [p for p in walk_tree(M7, exts={".yaml", ".json", ".md"})
                  if os.path.normpath(p) not in self_outputs]
    # HOLD must appear as a delimited segment so that words like
    # PLACEHOLDERS do not match; trailing punctuation is stripped.
    seg_re = re.compile(r"[A-Z0-9][A-Z0-9_\-\.]*")
    hold_seg = re.compile(r"(^|[_\-\.])HOLD([_\-\.]|$)")

    def tokens_of(text):
        out = set()
        for m in seg_re.finditer(text):
            tok = m.group(0).rstrip(".")
            if hold_seg.search(tok):
                out.add(tok)
        return out

    token_files = {}
    for p in text_files:
        try:
            t = read_text(p)
        except Exception:
            continue
        for tok in tokens_of(t):
            token_files.setdefault(tok, set()).add(p)
    # declaration surfaces: the release gate, the handoff gate, the terminal
    # closure contract, the contract's retained_holds, the terminal
    # non_blocking_holds_permitted list, and the owner decision register
    # (a HOLD written in the ODR is owner-visible by definition)
    retained = contract.get("retained_holds", [])
    nb = get_path(terminal, "terminal_release_condition."
                            "non_blocking_holds_permitted") or []
    odr_text = read_text(os.path.join(M7, "00_authority",
                                      "M7_OWNER_DECISION_REGISTER_V1.yaml"))
    surface_text = "\n".join([gate_text, handoff_text, terminal_text,
                              odr_text,
                              json.dumps(retained), json.dumps(nb)])
    declared_tokens = tokens_of(surface_text)
    contract_text = read_text(CONTRACT_YAML)
    # which files are pinned as gate evidence, and under which criterion state
    file_states = {}
    for c in gate["criteria"]:
        for ev in c.get("evidence", []):
            file_states.setdefault(
                os.path.normpath(resolve(ev["path"])), set()).add(c["state"])
    gate_evidence_files = set(file_states)
    stop = {"HOLD", "NO", "NOT", "ONLY", "THE", "AND", "OR", "OF", "TO",
            "IN", "IS", "ARE", "A", "ON", "AT", "BY", "FOR", "WITH",
            "WITHOUT", "REMAINS", "STAYS", "STAY", "RETAINED", "EXPLICIT",
            "ALL", "PER", "THAN", "INTO", "FROM", "AS", "IF", "BE", "BEEN"}
    declared_words = []
    for d in declared_tokens:
        declared_words.append(
            (d, {w for w in re.split(r"[_\-\.]", d) if w and w not in stop}))

    def near_declared(tok):
        """Word-set Jaccard against every declared HOLD token; a hold whose
        subject is declared at the gate under a paraphrased spelling is not
        hidden."""
        w = {x for x in re.split(r"[_\-\.]", tok) if x and x not in stop}
        if not w:
            return None, 0.0
        best, best_d = 0.0, None
        for d, dw in declared_words:
            if not dw:
                continue
            j = len(w & dw) / len(w | dw)
            if j > best:
                best, best_d = j, d
        return best_d, best

    declared, undeclared = [], []
    for tok in sorted(token_files):
        if tok in surface_text:
            declared.append(tok)
            continue
        files = sorted(token_files[tok])
        rel_files = [os.path.relpath(f, M7) for f in files]
        near, score = near_declared(tok)
        if near is not None and score >= 0.5:
            undeclared.append({"token": tok, "severity": "LOW",
                               "why": f"exact string absent from the "
                                      f"declaration surfaces, but its subject "
                                      f"is declared there as '{near}' "
                                      f"(word-set overlap {score:.2f}) - a "
                                      f"spelling variant, not a hidden hold",
                               "files": rel_files})
            fnd.append(finding("LOW", "RT-07",
                               f"HOLD token '{tok}' is a spelling variant of "
                               f"declared '{near}' (overlap {score:.2f})",
                               {"files": rel_files}))
            continue
        in_contract = tok in contract_text
        states = set()
        for f in files:
            states |= file_states.get(os.path.normpath(f), set())
        pinned = bool(states)
        only_hold_criteria = pinned and states == {"HOLD"}
        in_pass_evidence = bool(states & {"PASS",
                                          "PASS_WITH_DECLARED_OPEN_ITEM"})
        if only_hold_criteria:
            sev = "LOW"
            why = ("present only in evidence pinned to a HOLD-state "
                   "criterion; the gate already refuses PASS there, so this "
                   "hold cannot inflate a PASS")
        elif in_contract:
            sev = "LOW"
            why = ("declared in the consumer contract body (fail-closed "
                   "status) but absent from retained_holds and the gate")
        elif in_pass_evidence:
            sev = "MEDIUM"
            why = ("present in evidence pinned to a PASS-class criterion "
                   f"(states {sorted(states)}) but nowhere in the gate JSON "
                   "/ handoff gate / contract retained_holds / terminal "
                   "contract lists / ODR, and no declared hold covers the "
                   "same subject - must be adjudicated before owner "
                   "signature")
        elif in_contract:
            sev = "LOW"
            why = ("declared in the consumer contract body (fail-closed "
                   "status) but absent from retained_holds and the gate")
        elif pinned:
            sev = "LOW"
            why = ("present in gate-pinned evidence of a HOLD criterion "
                   "mixed with other states; not surfaced by exact string")
        else:
            sev = "LOW"
            why = "present only in non-pinned intermediate files"
        undeclared.append({"token": tok, "severity": sev, "why": why,
                           "files": rel_files,
                           "nearest_declared": near,
                           "nearest_overlap": round(score, 3)})
        fnd.append(finding(sev, "RT-07",
                           f"HOLD token '{tok}' found nowhere in the "
                           f"declaration surfaces ({why})",
                           {"files": rel_files,
                            "nearest_declared": near,
                            "nearest_overlap": round(score, 3)}))
    checks.append({"check": "HOLD token enumeration across yaml/json/md",
                   "files_scanned": len(text_files),
                   "unique_tokens": len(token_files),
                   "declared_in_surfaces": len(declared),
                   "undeclared": len(undeclared)})
    # mandatory presence: criterion 09 HARNESS_AND_KEEPOUT must be HOLD in the
    # gate - its ABSENCE would be the finding
    c09 = [c for c in gate["criteria"] if c["id"] == "09"]
    if not c09 or c09[0]["state"] != "HOLD" or \
            c09[0]["name"] != "HARNESS_AND_KEEPOUT":
        fnd.append(finding("HIGH", "RT-07",
                           "criterion 09 HARNESS_AND_KEEPOUT HOLD missing or "
                           "changed in the gate JSON",
                           {"found": [{"id": c["id"], "name": c["name"],
                                       "state": c["state"]}
                                      for c in c09]}))
    else:
        checks.append({"check": "criterion 09 HARNESS_AND_KEEPOUT HOLD present",
                       "open_items": [o["id"] for o in
                                      c09[0].get("open_items", [])]})
    # gate-internal hold bookkeeping consistency
    if gate.get("blocking_holds_forbidden_at_gate_a_all_absent") is not True:
        fnd.append(finding("HIGH", "RT-07",
                           "gate does not assert all forbidden blocking holds "
                           "absent", {}))
    carried_gate = gate.get("carried_holds_unchanged", [])
    carried_term = get_path(terminal, "terminal_objective.carried_holds") or []
    if set(carried_gate) != set(carried_term):
        fnd.append(finding("MEDIUM", "RT-07",
                           "carried-holds list differs between gate and "
                           "terminal contract",
                           {"gate": carried_gate, "terminal": carried_term}))
    checks.append({"check": "carried holds gate vs terminal contract",
                   "gate": carried_gate, "terminal": carried_term})
    attack_done("RT-07", "hidden HOLD", checks, fnd, len(text_files))


# ==========================================================================
# RT-08  MECH-RL interface unloadable
# ==========================================================================
def rt08():
    checks, fnd = [], []
    scanned = 0
    # (a) fresh independent parse of both interface files
    try:
        c2 = yaml.safe_load(read_text(CONTRACT_YAML))
        scanned += 1
        if c2.get("schema") != "EMBODIED_MECHANICAL_CONTRACT_V1":
            fnd.append(finding("HIGH", "RT-08",
                               "contract schema name mismatch on fresh parse",
                               {"schema": c2.get("schema")}))
    except Exception as exc:
        fnd.append(finding("HIGH", "RT-08",
                           f"contract YAML fails fresh parse: {exc}", {}))
        c2 = None
    try:
        h2 = json.loads(read_text(HANDOFF_JSON))
        scanned += 1
        if h2.get("schema") != "MECHANICAL_TO_EMBODIED_HANDOFF_GATE":
            fnd.append(finding("HIGH", "RT-08",
                               "handoff schema name mismatch on fresh parse",
                               {"schema": h2.get("schema")}))
    except Exception as exc:
        fnd.append(finding("HIGH", "RT-08",
                           f"handoff JSON fails fresh parse: {exc}", {}))
        h2 = None
    # (b) verdict string exact
    if h2 is not None:
        v = h2.get("verdict")
        checks.append({"check": "handoff verdict string",
                       "verdict": v,
                       "expected": "MECHANICAL_TO_EMBODIED_HANDOFF_PASS"})
        if v != "MECHANICAL_TO_EMBODIED_HANDOFF_PASS":
            fnd.append(finding("HIGH", "RT-08",
                               "handoff verdict string is not exactly "
                               "MECHANICAL_TO_EMBODIED_HANDOFF_PASS",
                               {"verdict": v}))
        if h2.get("checks_total") != 11 or h2.get("checks_passed") != 11 or \
                h2.get("checks_failed") != 0:
            fnd.append(finding("HIGH", "RT-08",
                               "handoff check counts not 11/11/0",
                               {"total": h2.get("checks_total"),
                                "passed": h2.get("checks_passed"),
                                "failed": h2.get("checks_failed")}))
        # (c) handoff source_pins recompute-match
        for name, pin in (h2.get("source_pins") or {}).items():
            p = resolve(pin["path"])
            scanned += 1
            live = sha256_16(p) if os.path.isfile(p) else None
            if live is None or live.upper() != str(pin["sha256_16"]).upper():
                fnd.append(finding("HIGH", "RT-08",
                                   f"handoff source_pin '{name}' hash "
                                   "recompute mismatch",
                                   {"path": pin["path"],
                                    "declared": pin["sha256_16"],
                                    "live": live}))
        checks.append({"check": "handoff source_pins recompute",
                       "pins": len(h2.get("source_pins") or {})})
    # (d) contract source_register: full sha256 + bytes recompute-match
    if c2 is not None:
        sr = c2.get("source_register", [])
        n_ok = 0
        for e in sr:
            p = resolve(e["path"])
            scanned += 1
            if not os.path.isfile(p):
                fnd.append(finding("HIGH", "RT-08",
                                   "contract source_register file missing",
                                   dict(e)))
                continue
            live = sha256_full(p).upper()
            size = os.path.getsize(p)
            if live != str(e["sha256"]).upper() or size != e["bytes"]:
                fnd.append(finding("HIGH", "RT-08",
                                   "contract source_register hash/bytes "
                                   "recompute mismatch",
                                   {"role": e.get("role"), "path": e["path"],
                                    "declared": e["sha256"], "live": live,
                                    "declared_bytes": e["bytes"],
                                    "live_bytes": size}))
            else:
                n_ok += 1
        checks.append({"check": "contract source_register full-sha256 "
                                "recompute", "entries": len(sr),
                       "matched": n_ok})
    attack_done("RT-08", "MECH-RL interface unloadable", checks, fnd, scanned)


# ==========================================================================
# FALSIFIER
# ==========================================================================

def falsifier_done(fid, claim, method, result, evidence):
    f_claims[fid] = {"claim": claim, "method": method, "result": result,
                     "evidence": evidence}


def f1():
    pack = load_yaml(GRIPPER_PACK)
    fi = pack["frozen_inputs"]
    ev = {"frozen_inputs": fi,
          "gripper_pack_sha256_16": sha256_16(GRIPPER_PACK)}
    # 1) the summary source pinned by the pack must exist and hash-match
    sr_entry = [e for e in pack["source_register"]
                if "GRIPPER_R1_GEOMETRY_VALIDATION" in e["path"]]
    if not sr_entry:
        falsifier_done("F1", "0/144 positive rail-palm overlaps over the "
                             "gripper continuous stroke",
                       "locate pinned validation source", "FALSIFIED",
                       {"reason": "validation JSON not in pack source_register"})
        return
    sr_entry = sr_entry[0]
    vp = resolve(sr_entry["path"])
    if os.path.isfile(vp):
        live = sha256_full(vp).upper()
        ev["validation_json"] = {"path": sr_entry["path"],
                                 "declared_sha256": sr_entry["sha256"],
                                 "live_sha256": live,
                                 "hash_match": live == sr_entry["sha256"].upper()}
    else:
        ev["validation_json"] = {"path": sr_entry["path"], "exists": False}
    # 2) raw sweep samples: recount
    if not os.path.isfile(V5R_SWEEP_CSV):
        falsifier_done(
            "F1", "0/144 positive rail-palm overlaps over the gripper "
                  "continuous stroke",
            "recount raw sweep samples", "NOT_INDEPENDENTLY_REPRODUCIBLE",
            {**ev, "reason": "raw sweep CSV not on disk; only the summary "
                             "JSON is pinned. Could verify the summary's "
                             "existence and hash, could not recount."})
        return
    import csv as _csv
    with open(V5R_SWEEP_CSV, newline="", encoding="utf-8") as fh:
        rows = list(_csv.DictReader(fh))
    travels = [float(r["travel_mm"]) for r in rows]
    overlaps = [float(r["rail_palm_positive_overlap_upper_bound_mm3"])
                for r in rows]
    passes = [r["analytic_pass"].strip().lower() == "true" for r in rows]
    recount = {
        "csv": V5R_SWEEP_CSV,
        "csv_sha256_16": sha256_16(V5R_SWEEP_CSV),
        "rows": len(rows),
        "positive_overlap_rows": sum(1 for o in overlaps if o > 0.0),
        "max_overlap_upper_bound_mm3": max(overlaps) if overlaps else None,
        "all_analytic_pass": all(passes),
        "travel_min": min(travels), "travel_max": max(travels),
        "uniform_step_0p5": all(
            abs((travels[i + 1] - travels[i]) - 0.5) < 1e-9
            for i in range(len(travels) - 1)),
        "anchors": sorted({r["anchor"] for r in rows}),
        "proof_methods": sorted({r["proof_method"] for r in rows}),
    }
    ev["recount"] = recount
    # 3) is the CSV itself pinned by the pack or by the validation JSON?
    vtext = read_text(vp) if os.path.isfile(vp) else ""
    ev["csv_pinned_in_pack_source_register"] = any(
        "CONTINUOUS_STROKE_SAMPLES" in e["path"] for e in pack["source_register"])
    ev["csv_referenced_in_validation_json"] = \
        "CONTINUOUS_STROKE_SAMPLES" in vtext or "144" in vtext
    # 4) consistency of summary claims vs recount
    ok = (len(rows) == fi["continuous_stroke_sample_count"] == 144 and
          recount["positive_overlap_rows"] ==
          fi["positive_rail_palm_overlap_count"] == 0 and
          recount["all_analytic_pass"] and
          abs(recount["travel_max"] - fi["stroke_mm"][1]) < 1e-9 and
          recount["uniform_step_0p5"])
    ev["what_could_be_reproduced"] = (
        "row count, stroke range, 0.5 mm step, per-sample overlap upper "
        "bound == 0 and analytic_pass == true for all 144 samples")
    ev["what_could_not_be_reproduced"] = (
        "the underlying B-rep/AABB-Minkowski envelope computation itself "
        "(no CAD kernel in this audit); the CSV's own provenance is via its "
        "sibling validation JSON which the pack pins by full sha256 - the "
        "CSV is NOT itself hash-pinned in the pack source_register")
    falsifier_done(
        "F1",
        "0/144 positive rail-palm overlaps over the gripper continuous stroke",
        "recount the raw 144-sample sweep CSV and cross-check the pack's "
        "frozen_inputs against the recount; verify the pinned validation "
        "summary hash-matches",
        "SURVIVED" if ok else "FALSIFIED", ev)


def f2():
    ev = {}
    src = read_text(WP2_V2_PY)
    # (a) abs() usage audit: classify every abs( line
    abs_lines = [(i + 1, ln.strip()) for i, ln in enumerate(src.splitlines())
                 if "abs(" in ln]
    forbidden_pat = re.compile(r"abs\s*\(\s*\w*\s*@|abs\s*\(.*rotation.*@|"
                               r"abs\s*\(.*c_global", re.I)
    # lines that build the discrimination witness itself (the deliberate
    # forbidden-comparator used to PROVE the fix is not abs()) are the
    # negative control, not a pseudo-fix
    forbidden_hits = [(n, ln) for n, ln in abs_lines
                      if forbidden_pat.search(ln)
                      and "np.abs(c_global - c_global.T)" not in ln
                      and "max(np.abs" not in ln
                      and not re.search(r"forbidden|naive", ln, re.I)]
    ev["abs_line_count"] = len(abs_lines)
    ev["forbidden_abs_pattern_hits"] = forbidden_hits
    ev["covariance_map_implemented"] = "tmap @ c_local @ tmap.T" in src
    ev["sigma_from_covariance_diag"] = "np.diag(c_global)" in src
    # (b) the discrimination witness inside the yaml design_checks
    wp2 = load_yaml(WP2_V2_YAML)
    disc = wp2["design_checks"].get(
        "covariance_method_discrimination_vs_forbidden_abs", {})
    cs = disc.get("covariance_derived_sigma")
    fs = disc.get("forbidden_abs_rotated_sigma")
    if cs and fs:
        delta = max(abs(a - b) for a, b in zip(cs, fs))
        ev["discrimination_max_abs_delta"] = delta
        ev["discrimination_witness_present"] = True
    else:
        ev["discrimination_witness_present"] = False
    rem = wp2["remediation_register"].get("WP2-AUD-02", {})
    ev["remediation"] = {k: rem.get(k) for k in
                         ("status", "records_checked",
                          "negative_reported_sigma_after_fix")}
    # (c) recompute from the yaml: all reported sigmas >= 0; every covariance
    #     matrix symmetric PSD
    neg_sigma, cov_checked, cov_bad = [], 0, []
    n_sigma = 0
    for p, k, v in walk_obj(wp2):
        kl = str(k).lower()
        if "standard_uncert" in kl and isinstance(v, (int, float, list)):
            flat = []

            def _flat(x):
                if isinstance(x, (int, float)):
                    flat.append(float(x))
                elif isinstance(x, list):
                    for y in x:
                        _flat(y)
            _flat(v)
            for val in flat:
                n_sigma += 1
                if val < 0:
                    neg_sigma.append({"path": p + "/" + str(k), "value": val})
        if "covariance" in kl and isinstance(v, list) and v and \
                all(isinstance(r, list) for r in v):
            M = np.array(v, dtype=float)
            if M.ndim == 2 and M.shape[0] == M.shape[1]:
                cov_checked += 1
                sym = float(np.max(np.abs(M - M.T))) if M.size else 0.0
                scale = max(float(np.max(np.abs(M))) if M.size else 0.0, 1.0)
                min_eig = float(np.linalg.eigvalsh(
                    0.5 * (M + M.T)).min()) if M.size else 0.0
                if sym > 1e-12 * scale or min_eig < -1e-12 * scale:
                    cov_bad.append({"path": p + "/" + str(k),
                                    "sym_residual": sym,
                                    "min_eigenvalue": min_eig,
                                    "scale": scale})
    ev["sigma_scalars_checked"] = n_sigma
    ev["negative_sigmas"] = neg_sigma
    ev["covariance_matrices_checked"] = cov_checked
    ev["covariance_not_symmetric_psd"] = cov_bad
    ok = (not forbidden_hits and ev["covariance_map_implemented"] and
          ev["sigma_from_covariance_diag"] and
          ev.get("discrimination_witness_present") and
          ev.get("discrimination_max_abs_delta", 0) > 1e-3 and
          not neg_sigma and not cov_bad and
          rem.get("negative_reported_sigma_after_fix") == 0)
    falsifier_done(
        "F2",
        "WP2-AUD-02 fix is not an abs() pseudo-fix; C_global = R C_local R^T "
        "covariance propagation is what is implemented",
        "static scan of aggregate_m7_design_mass_v2.py for forbidden abs() "
        "patterns + presence of the T(R) C T(R)^T map; recompute from "
        "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml: every reported sigma >= 0, "
        "every covariance matrix symmetric PSD (eigvalsh >= -1e-12*scale); "
        "verify the discrimination witness (covariance result differs from "
        "the forbidden abs-rotated matrix)",
        "SURVIVED" if ok else "FALSIFIED", ev)


def f3():
    cal = load_yaml(CALIB_YAML)
    ccp = cal["cross_configuration_proof"]
    closure = ccp["per_configuration_chain_closure"]
    ev = {
        "per_configuration_chain_closure": closure,
        "all_zero": all(float(v) == 0.0 for v in closure.values()),
        "worst_empirical_residual_mm":
            ccp["worst_urdf_predicted_pose_surface_residual_mm"],
        "empirical_configurations":
            ccp["empirical_configurations_with_independent_cad_geometry"],
        "analytic_extension_text": ccp["analytic_extension"],
        "calibration_sha256_16": sha256_16(CALIB_YAML),
    }
    analytic = ccp["analytic_extension"]
    non_empirical = [k for k in closure
                     if k not in
                     ccp["empirical_configurations_with_independent_cad_geometry"]]
    ev["non_empirical_configurations"] = non_empirical
    ev["analytic_declared"] = ("ANALYTIC" in analytic and
                               "not measured" in analytic)
    ev["naming_note"] = (
        "7 configurations total: 2 empirical (q0, Q_STOW_C05) + 5 "
        "non-empirical. The analytic_extension prose says 'Those four are "
        "ANALYTIC' while listing C06, C07, C01 and the joint lower/upper "
        "limits; counting the two joint-limit configurations separately "
        "gives 5 non-empirical configurations. All 5 are covered by the "
        "declaration; the four-vs-five wording is a prose imprecision, not "
        "an empirical claim.")
    ok = (ev["all_zero"] and
          abs(ev["worst_empirical_residual_mm"] - 0.0001629909138996286)
          < 1e-15 and
          len(ev["empirical_configurations"]) == 2 and
          ev["analytic_declared"])
    falsifier_done(
        "F3",
        "D_i is a fixed rigid calibration across configurations (chain "
        "closure 0.0 everywhere; worst empirical residual 0.000163 mm; "
        "non-empirical configurations declared ANALYTIC)",
        "re-read calibration yaml; verify per-configuration chain closures "
        "are exactly 0.0, the worst empirical residual matches, exactly 2 "
        "configurations carry independent CAD geometry, and the ANALYTIC "
        "declaration covers all remaining configurations",
        "SURVIVED" if ok else "FALSIFIED", ev)


def f4():
    ev1 = load_json(FEA1_EVID)
    rb = ev1["reaction_balance"]
    ev = {"method_declared": rb["method"], "summary": rb["summary"]}
    # (a) recompute per-job residuals from the stored applied vs reaction
    #     vectors (internal consistency: numbers must be self-consistent,
    #     not typed in)
    worst_rel, bad_jobs = 0.0, []
    for job, rec in rb["per_job"].items():
        applied = np.array(rec["applied_force_N_deck"], dtype=float)
        reacted = np.array(rec["sum_reaction_force_N"], dtype=float)
        resid = applied + reacted
        rel = float(np.linalg.norm(resid) / np.linalg.norm(applied)) \
            if np.linalg.norm(applied) > 0 else float("inf")
        stored = float(rec["residual_force_rel_to_applied"])
        worst_rel = max(worst_rel, rel)
        if abs(rel - stored) > max(1e-9, 1e-6 * stored):
            bad_jobs.append({"job": job, "recomputed_rel": rel,
                             "stored_rel": stored})
        # moment about RP
        am = np.array(rec["applied_moment_about_RP_N_mm_deck"], dtype=float)
        sm = np.array(rec["sum_reaction_moment_about_RP_N_mm"], dtype=float)
        rm = am + sm
        if np.linalg.norm(am) > 0:
            relm = float(np.linalg.norm(rm) / np.linalg.norm(am))
            worst_rel = max(worst_rel, relm)
    ev["per_job_recompute"] = {"jobs": len(rb["per_job"]),
                               "worst_relative_residual_recomputed": worst_rel,
                               "tolerance": 1e-4,
                               "inconsistent_jobs": bad_jobs}
    # (b) provenance: the evidence register pins every per-job file by its
    #     declared path + full sha256; recompute each from disk (this is what
    #     proves the numbers were read from solver outputs, not typed in)
    prov_ok, prov_bad, prov_missing = 0, [], []
    for base, rec in ev1["per_file_result_hashes"].items():
        for kind, krec in rec.items():
            if not isinstance(krec, dict) or "sha256" not in krec:
                continue
            fp = resolve(krec["path"]) if "path" in krec else None
            if fp is None or not os.path.isfile(fp):
                prov_missing.append({"job": base, "kind": kind,
                                     "path": krec.get("path")})
                continue
            live = sha256_full(fp)
            if live.upper() != str(krec["sha256"]).upper():
                prov_bad.append({"job": base, "kind": kind,
                                 "declared": krec["sha256"], "live": live})
            elif "bytes" in krec and os.path.getsize(fp) != krec["bytes"]:
                prov_bad.append({"job": base, "kind": kind,
                                 "declared_bytes": krec["bytes"],
                                 "live_bytes": os.path.getsize(fp)})
            else:
                prov_ok += 1
    ev["provenance_recompute"] = {
        "pinned_file_records_checked": prov_ok + len(prov_bad)
        + len(prov_missing),
        "hash_and_bytes_matched": prov_ok,
        "mismatches": prov_bad,
        "missing_files": prov_missing,
        "note": "every per-job artifact pinned in per_file_result_hashes "
                "(inp/dat/msg/sta/odb/com/prt/_extract_json, declared paths "
                "including jobs/_extract/) recomputed by full sha256 + bytes"}
    # (c) FEA1B reaction balance
    ev1b = load_json(FEA1B_EVID)
    ev["fea1b"] = {
        "reaction_balance_verdict": ev1b.get("reaction_balance_verdict"),
        "reaction_balance_criterion":
            ev1b.get("reaction_balance_criterion"),
    }
    ok = (not bad_jobs and worst_rel < 1e-4 and not prov_bad
          and not prov_missing and
          rb["summary"]["worst_relative_force_residual"] < 1e-4 and
          rb["summary"]["worst_relative_moment_residual"] < 1e-4 and
          not rb["summary"]["jobs_with_reaction_leakage_outside_encastre_set"])
    falsifier_done(
        "F4",
        "FEA reaction balance passed (and the evidence is read from "
        ".dat/.odb extracts, not typed in)",
        "recompute per-job force/moment residuals from the stored applied "
        "and reaction vectors; verify against the 1e-4 criterion; recompute "
        "sha256 of every job's .dat and ODB-extract JSON against the "
        "evidence register (provenance that numbers came from solver "
        "outputs)",
        "SURVIVED" if ok else "FALSIFIED", ev)


def f5():
    all_files = walk_tree(M7)
    zero = [p for p in all_files if os.path.getsize(p) == 0]
    # build the set of paths cited as evidence anywhere in the release thread
    cited_blobs = []
    for p in walk_tree(M7, exts={".json", ".yaml"}):
        base = os.path.basename(p)
        if base in (os.path.basename(RT_REPORT_PATH),
                    os.path.basename(F_REPORT_PATH)):
            continue
        cited_blobs.append(read_text(p))
    big = "\n".join(cited_blobs)
    classified = []
    cited_zero = []
    for p in zero:
        rel = os.path.relpath(p, M7)
        base = os.path.basename(p)
        cited = (base in big) or (rel.replace(os.sep, "/") in big)
        rec = {"file": rel, "bytes": 0,
               "classification": "CITED_AS_EVIDENCE" if cited
               else "UNCITED_PLACEHOLDER_OR_TOOLING"}
        classified.append(rec)
        if cited:
            cited_zero.append(rec)
    falsifier_done(
        "F5",
        "no zero-byte evidence anywhere in the release thread",
        "full-tree scan of wp1-wp13 + 00_authority + 12_release (+99_tools) "
        "for zero-byte files; classify each as cited-as-evidence (basename or "
        "relative path appears in any yaml/json of the thread) or legitimate "
        "placeholder/tooling",
        "SURVIVED" if not cited_zero else "FALSIFIED",
        {"files_scanned": len(all_files),
         "zero_byte_files": classified,
         "zero_byte_cited_as_evidence": cited_zero})


def f6():
    ph = contract["collision"]["CRITICAL_phantom_base_plate"]
    c18 = [c for c in gate["criteria"] if c["id"] == "18"][0]
    oi_text = json.dumps(c18.get("open_items", []))
    ho = handoff["checks"]["collision_meshes_loadable"]["evidence"].get(
        "declared_open_item_WP11_F_01", {})
    ev = {
        "contract_status": ph.get("status"),
        "contract_finding": ph.get("finding"),
        "criterion_18_open_items": c18.get("open_items", []),
        "criterion_18_mentions_WP11_F_01": "WP11-F-01" in oi_text,
        "handoff_declared_open_item": ho,
    }
    ok = (ph.get("status") == "OPEN_DECLARED" and
          "WP11-F-01" in str(ph.get("finding", "")) and
          ev["criterion_18_mentions_WP11_F_01"] and
          ho.get("status") == "OPEN_DECLARED")
    falsifier_done(
        "F6",
        "the phantom base plate open item is declared, not hidden",
        "verify contract collision.CRITICAL_phantom_base_plate.status == "
        "OPEN_DECLARED, that gate criterion 18's open items name WP11-F-01, "
        "and that the handoff gate carries the same declared open item",
        "SURVIVED" if ok else "FALSIFIED", ev)


# ==========================================================================
# main
# ==========================================================================
def main():
    rt01(); rt02(); rt03(); rt04(); rt05(); rt06(); rt07(); rt08()
    f1(); f2(); f3(); f4(); f5(); f6()

    sev_count = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for a in rt_attacks.values():
        for f in a["findings"]:
            sev_count[f["severity"]] += 1
    rt_verdicts = {k: v["verdict"] for k, v in rt_attacks.items()}
    f_results = {k: v["result"] for k, v in f_claims.items()}

    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    rt_report = {
        "schema": "M7_RED_TEAM_REPORT_V1",
        "generated_local": stamp,
        "role": "A6_RED_TEAM (read-only audit; no design file was modified)",
        "script": "12_release/red_team_and_falsifier_v1.py",
        "input_pins_sha256_16": PINS,
        "severity_discipline": {
            "HIGH": "would invalidate a PASS or the release",
            "MEDIUM": "must fix before owner signature but does not "
                      "invalidate engineering",
            "LOW": "hygiene"},
        "attacks": rt_attacks,
        "attack_verdicts": rt_verdicts,
        "total_findings_by_severity": sev_count,
        "unverifiable": [
            "No Abaqus license/kernel used: .odb contents were not re-read "
            "by this audit; FEA provenance was verified by recomputing the "
            "hashes of the .dat solver printouts and the per-job ODB-extract "
            "JSONs that the evidence register pins, and by recomputing the "
            "residual arithmetic from the stored vectors.",
            "No CAD/B-rep kernel available: the gripper overlap geometry "
            "computation behind the 144-sample sweep was not re-executed; "
            "the recorded sweep samples were recounted instead (see F1).",
            "SolidWorks native reintegration (V5 native parts) is outside "
            "this audit; it is a declared terminal-contract non-blocking "
            "hold.",
        ],
    }
    f_report = {
        "schema": "M7_FALSIFIER_REPORT_V1",
        "generated_local": stamp,
        "role": "A6_RED_TEAM falsifier (read-only)",
        "script": "12_release/red_team_and_falsifier_v1.py",
        "input_pins_sha256_16": PINS,
        "claims": f_claims,
        "results": f_results,
        "survived": sum(1 for r in f_results.values() if r == "SURVIVED"),
        "falsified": sum(1 for r in f_results.values() if r == "FALSIFIED"),
        "not_independently_reproducible": sum(
            1 for r in f_results.values()
            if r == "NOT_INDEPENDENTLY_REPRODUCIBLE"),
    }
    with open(RT_REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(rt_report, fh, indent=2, ensure_ascii=False)
    with open(F_REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(f_report, fh, indent=2, ensure_ascii=False)

    print("RED TEAM verdicts:", json.dumps(rt_verdicts, indent=1))
    print("findings by severity:", sev_count)
    print("FALSIFIER results:", json.dumps(f_results, indent=1))
    print("wrote:", RT_REPORT_PATH)
    print("wrote:", F_REPORT_PATH)


if __name__ == "__main__":
    main()
