"""M6 independent fail-closed validator. Does not import the builder.

Checks:
 1. M6 output manifest hashes (recompute every file).
 2. Every WP receipt.json parses and its declared outputs hash-match.
 3. Baseline pin set unchanged (hashes pinned by M4/M5/CDR/SIM15 gates).
 4. Cross-WP reconciliation: zero missing references.
 5. Gate/token semantic consistency (FEA=0, HOLDs retained, tokens issued).
 6. Structural content spot checks (row counts, record counts, HOLD flags).
Run: python validate_m6_release.py
"""
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

import yaml

M6 = Path(__file__).resolve().parents[1]
PROJECT = M6.parents[1]
REL = "12_release"

results = []


def check(cid, title, fn):
    try:
        details = fn() or {}
        results.append({"id": cid, "title": title, "passed": True, "errors": [], "details": details})
    except Exception as e:  # noqa: BLE001 - fail-closed recorder
        results.append({"id": cid, "title": title, "passed": False, "errors": [str(e)], "details": {}})


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_manifest():
    return json.loads((M6 / REL / "M6_OUTPUT_MANIFEST_V1.json").read_text(encoding="utf-8"))


def c_manifest_hashes():
    m = load_manifest()
    bad = []
    for r in m["files"]:
        p = M6 / r["path"]
        if not p.is_file() or sha256(p) != r["sha256"] or p.stat().st_size != r["bytes"]:
            bad.append(r["path"])
    assert not bad, f"manifest mismatch: {bad}"
    assert m["file_count"] == len(m["files"]) >= 30, "suspiciously small manifest"
    return {"files_verified": m["file_count"], "bytes": m["total_bytes"]}


def c_receipts():
    n, files_seen = 0, 0
    for rp in sorted(M6.glob("wp*/receipt.json")):
        d = json.loads(rp.read_text(encoding="utf-8"))
        n += 1
        text = rp.read_text(encoding="utf-8")
        assert "sha256" in text, f"{rp} lacks hash records"
        # every declared existing output path with a hash must verify
        def walk(node):
            nonlocal files_seen
            if isinstance(node, dict):
                path = node.get("path") or node.get("file")
                h = node.get("sha256")
                if isinstance(path, str) and isinstance(h, str) and len(h) == 64:
                    p = Path(path)
                    if not p.is_absolute():
                        p = (rp.parent / path)
                        if not p.is_file():
                            p = M6 / path
                        if not p.is_file():
                            p = PROJECT / path
                    if p.is_file() and str(p.resolve()).startswith(str(M6.resolve())):
                        files_seen += 1
                        assert sha256(p) == h.upper(), f"receipt hash drift: {path}"
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(d)
    assert n == 7, f"expected 7 WP receipts, found {n}"
    return {"receipts": n, "receipt_hash_records_verified": files_seen}


PINS = [
    # (path relative to project root, sha256 pinned by an existing gate)
    ("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/02_parameterized_cad/SEI_DIGITAL_PROTOTYPE_V1.FCStd",
     "DEA1BC93AB182C0003B37B8B8D7D7BA2559AFB649769BDE59E52FAC0DB20D481"),
    ("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/02_parameterized_cad/SEI_DIGITAL_PROTOTYPE_V1.step",
     "0FA64971512FAAA0B1D8EB026D4449DD513340BE8F047554D370ED359CD28020"),
    ("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/08_simulation_assets/MECH_RL_INTERFACE_V2.yaml",
     "2A72F8B77220529B191BA6FE780924D2067195EC9CAF7A7EE5626A589B2E826F"),
    ("20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json",
     "2A99484C6CE55B402CB06380F5DCB71D5A8B4BA622A371EEF72F4EC69EF124FF"),
    ("20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml",
     "DA18F5A6E2F553FC709E90BA1035CDD7770A6FCEECA13EDC1FDB448CAF75838D"),
    ("20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/07_simulation_handoff/MECH_DYNAMICS_INTERFACE_V3.yaml",
     "88AE877677BBCE40BE6324AC884B91E0DF8B7862EB9074AD1D001B54FD7F3F79"),
    ("20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml",
     "1BF741A508AA6F263D81458184840F2AD6608652250256CE84D7F2656BD04B6B"),
    ("20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/06_structural_entry/M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1.json",
     "BB8C7587CEAC182AD3F15EAE887E43497FBA5C99C8425A41F1FFFD36CD00B5D5"),
    ("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/04_gates/MECH_Q0_REQUIREMENTS_AND_TAILORING_GATE.json",
     "85D0FB60B4900A4C32427F2569BC654B78081AE65673B94B14FB935540E048A8"),
    ("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/04_gates/MECH_Q1_LOAD_ENVIRONMENT_AUTHORITY_GATE.json",
     "DAA7855DF7D9901AF8851BA37C1590D89001E9006DCBCBB5A05AA5C065DBAD61"),
    ("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/04_gates/MECH_Q2_MASS_INTERFACE_AUTHORITY_GATE.json",
     "7239820C96A8F1D4E9064DABE8B12954A0A4368C7FAFEEE87A6045C8E28FFF07"),
    ("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
     "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"),
]


def c_baseline_pins():
    bad = []
    for rel, want in PINS:
        p = PROJECT / rel
        if not p.is_file():
            bad.append((rel, "missing"))
        elif sha256(p) != want:
            bad.append((rel, "hash drift"))
    assert not bad, f"baseline drift: {bad}"
    return {"pinned_baselines_verified_unchanged": len(PINS)}


def c_reconciliation():
    d = json.loads((M6 / REL / "M6_CROSS_WP_REFERENCE_RECONCILIATION_V1.json").read_text(encoding="utf-8"))
    assert d["status"] == "ALL_REFERENCES_VERIFIED", d["status"]
    for c in d["reference_checks"]:
        t = M6 / c["target"]
        assert t.is_file() and sha256(t) == c["sha256"], c["target"]
    return {"references_verified": d["verified_count"]}


def c_gate_semantics():
    g = json.loads((M6 / REL / "M6_CANDIDATE_AUTHORITY_CLOSURE_GATE_V1.json").read_text(encoding="utf-8"))
    assert g["memory_execution_record"]["memory_gate_passed"] is False
    for tok in g["release_tokens"].values():
        assert tok["issued"] is True and (M6 / tok["evidence"]).is_file()
    assert g["release_tokens"]["structural_entry_evidence_pack"]["formal_fea_run_count"] == 0
    assert len(g["retained_holds"]) >= 15
    joined = json.dumps(g)
    assert "\"formal_fea_authorized\": true" not in joined
    assert g["overall_status"] in {"PENDING_VALIDATION",
                                   "PASS_SCOPED_M6_CANDIDATE_CLOSURE_WITH_RETAINED_PHYSICAL_HOLDS"}
    for claim in ["MEMORY_GATE_PASS", "STRUCTURAL_ANALYSIS_READY",
                  "FLIGHT_OR_MANUFACTURING_RELEASE", "RL_POLICY_READY"]:
        assert claim in g["prohibited_claims"], f"missing prohibition: {claim}"
    for tok in g["release_tokens"].values():
        s = tok["status"]
        assert any(k in s for k in ("CANDIDATE", "DIAGNOSTIC", "DRAFT", "PENDING")), s
    return {"tokens": len(g["release_tokens"]), "retained_holds": len(g["retained_holds"])}


def c_wp1_geometry():
    r = json.loads((M6 / "wp1_load_bridge/receipt.json").read_text(encoding="utf-8"))
    for n in ["LOAD_BRIDGE_CANDIDATE_V1.FCStd", "LOAD_BRIDGE_CANDIDATE_V1.step",
              "LOAD_BRIDGE_DATUMS_V1.yaml", "FITUP_AND_FRAME_RECEIPT_V1.json"]:
        p = M6 / "wp1_load_bridge" / n
        assert p.is_file() and p.stat().st_size > 0, n
    fit = json.loads((M6 / "wp1_load_bridge/FITUP_AND_FRAME_RECEIPT_V1.json").read_text(encoding="utf-8"))
    blob = json.dumps(fit)
    assert "HOLD" in blob, "fitup receipt must retain HOLDs"
    d = yaml.safe_load((M6 / "wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml").read_text(encoding="utf-8"))
    assert "CANDIDATE" in yaml.dump(d), "datums must be candidate-marked"
    return {"wp1_files": 4}


def c_wp2_mass():
    d = yaml.safe_load((M6 / "wp2_mass_properties/SYSTEM_MASS_PROPERTIES_V4_DIAGNOSTIC.yaml").read_text(encoding="utf-8"))
    blob = yaml.dump(d)
    assert "release_aggregation_active: true" not in blob, "release aggregation must stay inactive"
    cfgs = [k for k in str(blob).split() if k.startswith("C0")]
    assert "C09" in blob and "C01" in blob, "nine configurations expected"
    t = yaml.safe_load((M6 / "wp2_mass_properties/CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml").read_text(encoding="utf-8"))
    assert "CANDIDATE" in yaml.dump(t), "transforms must be candidate-marked"
    return {"ledger_bytes": (M6 / "wp2_mass_properties/SYSTEM_MASS_PROPERTIES_V4_DIAGNOSTIC.yaml").stat().st_size}


def c_wp3_tolerance():
    rows = list(csv.reader((M6 / "wp3_tolerance/GRIPPER_CLEARANCE_SWEEP_V1.csv").read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 577, f"gripper sweep rows={len(rows)} (expect header+576)"
    rows2 = list(csv.reader((M6 / "wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.csv").read_text(encoding="utf-8").splitlines()))
    assert len(rows2) >= 18, f"stackup rows={len(rows2)}"
    v = yaml.safe_load((M6 / "wp3_tolerance/GRIPPER_CLEARANCE_SWEEP_VERDICT_V1.yaml").read_text(encoding="utf-8"))
    assert "HOLD" in yaml.dump(v)
    return {"sweep_rows": len(rows) - 1, "stackup_rows": len(rows2) - 1}


def c_wp4_materials():
    d = yaml.safe_load((M6 / "wp4_materials/PROTOTYPE_MATERIAL_LIBRARY_V2.yaml").read_text(encoding="utf-8"))
    mats = d.get("materials", [])
    assert len(mats) == 7, f"material records={len(mats)}"
    for m in mats:
        assert m.get("classification") == "PROTOTYPE_CANDIDATE", m.get("material_id")
    rows = list(csv.reader((M6 / "wp4_materials/MATERIAL_SOURCE_REGISTER_V2.csv").read_text(encoding="utf-8").splitlines()))
    assert len(rows) >= 20, f"source rows={len(rows)}"
    return {"materials": len(mats), "sources": len(rows) - 1}


def c_wp5_structural():
    for n in ["FEA1_M3R_INTERFACE_MODEL_PLAN_V1.yaml", "FEA2_B601_MODEL_PLAN_V1.yaml",
              "FEA3_SYSTEM_MODAL_MODEL_PLAN_V1.yaml", "FASTENER_GROUP_ANALYTIC_NOTE_V1.yaml",
              "STRUCTURAL_ENTRY_SUBGATE_EVIDENCE_MAP_V1.yaml"]:
        yaml.safe_load((M6 / "wp5_structural_entry" / n).read_text(encoding="utf-8"))
    rows = list(csv.reader((M6 / "wp5_structural_entry/FASTENER_GROUP_ANALYTIC_UNIT_LOAD_V1.csv").read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 25, f"fastener rows={len(rows)} (expect header+24)"
    m = yaml.safe_load((M6 / "wp5_structural_entry/STRUCTURAL_ENTRY_SUBGATE_EVIDENCE_MAP_V1.yaml").read_text(encoding="utf-8"))
    assert "HOLD" in yaml.dump(m) and "PASS" not in yaml.dump(m.get("subgate_status_after_m6", {})), "subgates stay HOLD"
    return {"fastener_unit_load_rows": len(rows) - 1}


def c_wp6_bom():
    rows = list(csv.reader((M6 / "wp6_drawings_bom/DIGITAL_PROTOTYPE_BOM_V2_CANDIDATE.csv").read_text(encoding="utf-8").splitlines()))
    assert len(rows) >= 15, f"BOM rows={len(rows)}"
    idx = (M6 / "wp6_drawings_bom/DIGITAL_PROTOTYPE_DRAWING_INDEX_V2.csv").read_text(encoding="utf-8")
    assert "D04" in idx and "CANDIDATE_PENDING" in idx
    assert (M6 / "wp1_load_bridge/D04_LOAD_BRIDGE_INTERFACE_DRAFT.svg").is_file()
    return {"bom_rows": len(rows) - 1}


def c_wp7_cdr():
    for n in ["Q0_CLOSURE_READINESS_V1.yaml", "Q1_CLOSURE_READINESS_V1.yaml", "Q2_CLOSURE_READINESS_V1.yaml"]:
        d = yaml.safe_load((M6 / "wp7_cdr_evidence" / n).read_text(encoding="utf-8"))
        blob = yaml.dump(d)
        assert "PENDING_OWNER_REVIEW" in blob and "HOLD" in blob, n
    return {"readiness_packs": 3}


def c_no_forbidden_artifacts():
    bad = []
    for p in M6.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".frd", ".dat", ".inp", ".odb", ".sim"}:
            bad.append(str(p.relative_to(M6)))
    assert not bad, f"FEA artifacts found: {bad}"
    return {"fea_artifacts_found": 0}


CHECKS = [
    ("M6-V-001", "M6 output manifest hashes", c_manifest_hashes),
    ("M6-V-002", "WP receipt integrity", c_receipts),
    ("M6-V-003", "baseline pins unchanged", c_baseline_pins),
    ("M6-V-004", "cross-WP reconciliation", c_reconciliation),
    ("M6-V-005", "gate token semantics", c_gate_semantics),
    ("M6-V-006", "WP1 load bridge geometry", c_wp1_geometry),
    ("M6-V-007", "WP2 nine-config diagnostic mass", c_wp2_mass),
    ("M6-V-008", "WP3 tolerance chains", c_wp3_tolerance),
    ("M6-V-009", "WP4 material library V2", c_wp4_materials),
    ("M6-V-010", "WP5 structural entry pack", c_wp5_structural),
    ("M6-V-011", "WP6 drawings and BOM", c_wp6_bom),
    ("M6-V-012", "WP7 CDR readiness packs", c_wp7_cdr),
    ("M6-V-013", "no FEA artifacts", c_no_forbidden_artifacts),
]

for cid, title, fn in CHECKS:
    check(cid, title, fn)

passed = sum(1 for r in results if r["passed"])
receipt = {
    "schema": "M6_VALIDATION_RECEIPT_V1",
    "validator": {"path": "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/99_tools/validate_m6_release.py",
                  "execution": "independent fail-closed validation; builder was not imported or modified"},
    "check_count": len(results),
    "pass_count": passed,
    "fail_count": len(results) - passed,
    "failed_check_ids": [r["id"] for r in results if not r["passed"]],
    "checks": results,
    "status": "PASS_SCOPED_M6_VALIDATION_EXPECTED_HOLDS_PRESERVED" if passed == len(results)
              else "FAIL_M6_VALIDATION",
}
out = M6 / REL / "M6_VALIDATION_RECEIPT_V1.json"
out.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"status": receipt["status"], "pass": passed, "of": len(results),
                  "failed": receipt["failed_check_ids"]}, indent=1))
sys.exit(0 if passed == len(results) else 1)
