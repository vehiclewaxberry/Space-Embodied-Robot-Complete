from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path

import psutil
import yaml


ROOT = Path(__file__).resolve().parents[1]
CLOSURE = ROOT / "09_DELIVERY" / "B51R1_AUTONOMOUS_G1A_CLOSURE_20260801"
VERIFY = ROOT / "07_VERIFICATION" / "AUTONOMOUS" / "G1A"
QUORUM_INPUT = CLOSURE / "B51R1_G1A_QUORUM_VERDICT_INPUT.json"
PRELOCK = CLOSURE / "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json"
PREAUDIT = VERIFY / "B51R1_G1A_PREQUORUM_MACHINE_AUDIT.json"
DISPOSITIONS = CLOSURE / "B51R1_AUTONOMOUS_FINDING_DISPOSITION_REGISTER_V2.csv"
CLAIMS = CLOSURE / "B51R1_AUTONOMOUS_CLAIM_MATRIX_V2.csv"
MANIFEST = CLOSURE / "B51R1_AUTONOMOUS_EXPECTED_ARTIFACT_MANIFEST_V3.csv"
COMPOSITION = CLOSURE / "B51R1_PHASE2_CURRENT_GATE_COMPOSITION.json"
LEDGER = CLOSURE / "B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json"
RESOLUTION = CLOSURE / "B51R1_G1A_EVIDENCE_PATH_RESOLUTION_RECEIPT.json"
QUORUM_RECEIPT = CLOSURE / "B51R1_G1A_MULTIAGENT_QUORUM_RECEIPT.json"
FINAL_LOCK = CLOSURE / "B51R1_PHASE2A_INPUT_LOCK_V3_FINAL.json"
G1A_RECEIPT = CLOSURE / "B51R1_G1A_MACHINE_RATIFICATION_RECEIPT.json"
G1B_RECEIPT = CLOSURE / "B51R1_G1B_STANDING_SESSION_ADMISSION.json"
FINAL_RESOLUTION = CLOSURE / "B51R1_G1A_EVIDENCE_PATH_RESOLUTION_FINAL_RECEIPT.json"
FINAL_AUDIT = VERIFY / "B51R1_G1A_G1B_FINAL_MACHINE_AUDIT.json"
INDEX = CLOSURE / "B51R1_G1A_G1B_CLOSURE_INDEX.json"
EXPECTED_PRELOCK_SHA = "EC66827B1794E2CAC84A12D9E10F26173335D1F9E0C50EFE0D078746FC32CEE4"
CHARTER_PATH = (
    ROOT
    / "00_BASELINE/AUTHORIZATION_PACKAGE/"
    "B51R1_AUTONOMOUS_LOOP_MULTIAGENT_ENGINEERING_PACKAGE_INTAKE_20260801/"
    "CONTENTS/B51R1_AUTONOMOUS_LOOP_MULTIAGENT_ENGINEERING_PACKAGE/"
    "B51R1_AUTONOMOUS_ENGINEERING_CHARTER.yaml"
)
CHARTER_SHA = "142FE0800F1D10D75E32DFD7BF58BECEE25E0C86A67FB782CF8D333942099BC3"
STAGE_A = ROOT / "02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT"
STAGE_A_SHA = "5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B"
FINAL_SKELETON = ROOT / "02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT"


def now() -> str:
    return datetime.now().astimezone().isoformat()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def record(path: Path, role: str, mode: str = "READ_ONLY_HASH_GUARD") -> dict:
    return {
        "path": rel(path),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "role": role,
        "mode": mode,
    }


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sw_processes() -> list[dict]:
    return [
        process.info
        for process in psutil.process_iter(["pid", "name"])
        if (process.info.get("name") or "").lower() == "sldworks.exe"
    ]


def build_resolution(path: Path, layer: str, allowed_future: set[str] | None = None) -> dict:
    allowed_future = allowed_future or set()
    dispositions = read_csv(DISPOSITIONS)
    claims = read_csv(CLAIMS)
    rows_out = []
    for register, identity, field, source_rows in [
        (rel(DISPOSITIONS), "finding_id", "closure_evidence_path", dispositions),
        (rel(CLAIMS), "claim_id", "evidence", claims),
    ]:
        for row in source_rows:
            target_rel = row[field]
            if target_rel.lower() in {"", "null", "none"}:
                continue
            target = ROOT / Path(target_rel)
            if target.is_file():
                rows_out.append(
                    {
                        "source_register": register,
                        "source_id": row[identity],
                        "candidate_root_relative_path": target_rel,
                        "resolved_absolute_path": str(target.resolve()),
                        "resolution_state": "EXISTS_HASHED",
                        "bytes": target.stat().st_size,
                        "sha256": sha(target),
                    }
                )
            elif target_rel in allowed_future:
                rows_out.append(
                    {
                        "source_register": register,
                        "source_id": row[identity],
                        "candidate_root_relative_path": target_rel,
                        "resolved_absolute_path": str(target.resolve()),
                        "resolution_state": "EXPECTED_FUTURE_GATE_ARTIFACT",
                        "bytes": None,
                        "sha256": None,
                    }
                )
            else:
                raise FileNotFoundError(f"Final evidence target absent: {register}:{row[identity]}:{target_rel}")
    data = {
        "schema": "B51R1_G1A_EVIDENCE_PATH_RESOLUTION_RECEIPT_V2",
        "generated_at": now(),
        "status": "PASS_ALL_NON_NULL_PATHS_RESOLVED_OR_ENUMERATED_FUTURE",
        "path_base": "CANDIDATE_ROOT",
        "candidate_root": str(ROOT.resolve()),
        "graph_layer": layer,
        "resolved_rows": rows_out,
        "resolved_existing_count": sum(1 for row in rows_out if row["resolution_state"] == "EXISTS_HASHED"),
        "expected_future_count": sum(1 for row in rows_out if row["resolution_state"] == "EXPECTED_FUTURE_GATE_ARTIFACT"),
        "unresolved_unexpected_count": 0,
    }
    write_json(path, data)
    return data


def main() -> None:
    for protected, expected in [(CHARTER_PATH, CHARTER_SHA), (STAGE_A, STAGE_A_SHA)]:
        if not protected.is_file() or sha(protected) != expected:
            raise RuntimeError(f"Protected hash mismatch: {protected}")
    if FINAL_SKELETON.exists():
        raise RuntimeError("Final skeleton unexpectedly exists before S01")
    if sw_processes():
        raise RuntimeError("SolidWorks is running before G1B admission")
    if sha(PRELOCK) != EXPECTED_PRELOCK_SHA:
        raise RuntimeError("Prequorum input-lock hash changed")
    preaudit = read_json(PREAUDIT)
    if preaudit["overall"] != "PASS_PRE_FINAL_QUORUM_AUDIT" or preaudit["failures"]:
        raise RuntimeError("Prequorum machine audit is not PASS")

    quorum_input = read_json(QUORUM_INPUT)
    if quorum_input["prequorum_input_lock_sha256"] != EXPECTED_PRELOCK_SHA:
        raise RuntimeError("Quorum verdicts do not bind the current prelock")
    verdicts = quorum_input["verdicts"]
    identities = {row["canonical_agent_id"] for row in verdicts}
    role_to_verdicts: dict[str, list[dict]] = {}
    for verdict in verdicts:
        if verdict["decision"] not in {"PASS", "PASS_NO_VETO", "PASS_SCOPE_HASH"}:
            raise RuntimeError(f"Non-pass quorum verdict: {verdict}")
        for role in verdict["roles"]:
            role_to_verdicts.setdefault(role, []).append(verdict)
    if len(identities) < 5:
        raise RuntimeError("Strict distinct-agent quorum requires at least five identities in this run")
    if not {"A0", "A2", "A6", "A7"}.issubset(role_to_verdicts):
        raise RuntimeError("L2 A0+A2+A6 plus A7 no-veto is incomplete")
    l3_technical = {role for role in role_to_verdicts if role in {"A1", "A2", "A3", "A4", "A5"}}
    if len(l3_technical) < 3:
        raise RuntimeError("L3 three-of-A1..A5 role quorum is incomplete")
    if any(row["decision"] != "PASS_NO_VETO" for row in role_to_verdicts["A7"]):
        raise RuntimeError("A7 did not issue an explicit no-veto")

    quorum = {
        "schema": "B51R1_G1A_MULTIAGENT_QUORUM_RECEIPT_V2",
        "generated_at": now(),
        "status": "PASS_STRICT_DISTINCT_AGENT_QUORUM_NO_CURRENT_GATE_VETO",
        "authority_type": "OWNER_STANDING_DELEGATION",
        "delegation_charter": record(CHARTER_PATH, "STANDING_DELEGATION_CHARTER"),
        "prequorum_input_lock": record(PRELOCK, "PREQUORUM_HASH_GRAPH_ROOT"),
        "prequorum_machine_audit": record(PREAUDIT, "PREQUORUM_MACHINE_AUDIT"),
        "verdict_input": record(QUORUM_INPUT, "DISTINCT_AGENT_VERDICT_SET"),
        "distinct_agent_count": len(identities),
        "distinct_agent_ids": sorted(identities),
        "role_coverage": {role: [row["canonical_agent_id"] for row in values] for role, values in sorted(role_to_verdicts.items())},
        "l2_quorum": "PASS_A0_A2_A6_PLUS_A7_NO_VETO",
        "l3_quorum": f"PASS_{len(l3_technical)}_OF_A1_A2_A3_A4_A5_PLUS_A6_AND_A7_NO_VETO",
        "red_team_status": "PASS_NO_OPEN_CURRENT_GATE_CRITICAL_OR_HIGH",
        "solidworks_admission_at_receipt_time": False,
        "claim_limit": "G1A_QUORUM_ONLY_G1B_AND_NATIVE_CAD_NOT_YET_ISSUED",
    }
    write_json(QUORUM_RECEIPT, quorum)

    disposition_rows = read_csv(DISPOSITIONS)
    for row in disposition_rows:
        if row["a0_a6_disposition"] == "APPROVED_DEFERRED_HOLD_REGISTERED":
            continue
        row["technical_status"] = "CLOSED_BY_DISTINCT_AGENT_QUORUM_AND_HASH_GRAPH"
        row["a0_a6_disposition"] = "CLOSED"
        row["admission_effect"] = "NONE_AFTER_G1A_G1B_ISSUANCE"
    write_csv(DISPOSITIONS, disposition_rows)

    claim_rows = read_csv(CLAIMS)
    for row in claim_rows:
        if row["claim_id"] == "AUT-CLM-006":
            row["status"] = "PASS_DELEGATED_MACHINE_RATIFIED"
            row["allowed_wording"] = "G1A_PASS_DELEGATED_MACHINE_RATIFIED_AND_HASH_LOCKED"
        elif row["claim_id"] == "AUT-CLM-007":
            row["status"] = "PASS_STANDING_SESSION_ADMISSION"
            row["allowed_wording"] = "G1B_PASS_STANDING_SESSION_ADMISSION"
        elif row["claim_id"] == "AUT-CLM-008":
            row["status"] = "NOT_CREATED_S01_ADMITTED"
    write_csv(CLAIMS, claim_rows)

    composition = read_json(COMPOSITION)
    composition["generated_at"] = now()
    composition["status"] = "G1A_G1B_PASS_S01_ADMITTED_NATIVE_CAD_NOT_CREATED"
    composition["g1a"] = "PASS_DELEGATED_MACHINE_RATIFIED_AND_HASH_LOCKED"
    composition["g1b"] = "PASS_STANDING_SESSION_ADMISSION"
    composition["solidworks_process_count"] = 0
    composition["claim_limit"] = "S01_ADMITTED_FINAL_SKELETON_ABSENT_CARRIERS_0_OF_10_H10_0_OF_28_T005_NOT_RUN"
    write_json(COMPOSITION, composition)

    ledger = read_json(LEDGER)
    ledger["status"] = "ACTIVE_G1B_STANDING_SESSION_POOL"
    ledger["activated_at"] = now()
    ledger["consumed_since_activation"] = 0
    ledger["remaining"] = ledger["budget"]
    write_json(LEDGER, ledger)
    snapshot_path = CLOSURE / "B51R1_AUTONOMOUS_SESSION_POOL_ACTIVATION_SNAPSHOT.json"
    snapshot = dict(ledger)
    snapshot["schema"] = "B51R1_AUTONOMOUS_SESSION_POOL_ACTIVATION_SNAPSHOT_V1"
    snapshot["source_live_ledger"] = rel(LEDGER)
    snapshot["immutable_snapshot"] = True
    write_json(snapshot_path, snapshot)

    manifest_rows = read_csv(MANIFEST)
    for row in manifest_rows:
        if row["artifact_id"] == "G1A_PASS_RECEIPT":
            row.update({"current_count": "1", "current_status": "PASS_DELEGATED_MACHINE_RATIFIED", "artifact_type": "JSON"})
        elif row["artifact_id"] == "G1A_INPUT_LOCK_V2":
            row.update({"path_or_pattern": rel(FINAL_LOCK), "current_count": "1", "current_status": "PASS_FINAL_V3_HASH_LOCKED", "artifact_type": "JSON"})
        elif row["artifact_id"] == "G1B_PASS_ADMISSION":
            row.update({"current_count": "1", "current_status": "PASS_STANDING_SESSION_ADMISSION", "artifact_type": "JSON"})
        elif row["artifact_id"] == "AUT_EVIDENCE_PATH_RESOLUTION":
            row.update({"current_status": "CURRENT_HASHED_FINAL_V3_INPUT", "acceptance_boundary": "pre-issuance evidence graph locked by final V3; final post-issuance graph bound by closure index"})
    write_csv(MANIFEST, manifest_rows)

    # G1A/G1B receipt paths remain future at this pre-issuance layer. Recompute
    # all other path hashes after disposition, claim and manifest changes.
    build_resolution(
        RESOLUTION,
        "PRE_G1A_G1B_ISSUANCE_FINAL_V3_INPUT",
        {rel(G1A_RECEIPT), rel(G1B_RECEIPT)},
    )

    prelock = read_json(PRELOCK)
    excluded_dynamic = {rel(LEDGER)}
    items = []
    seen_paths = set()
    for old in prelock["locked_items"]:
        if old["path"] in excluded_dynamic:
            continue
        target = ROOT / Path(old["path"])
        item = record(target, old.get("role", "FINAL_V3_INPUT"), old.get("mode", "READ_ONLY_HASH_GUARD"))
        item["id"] = old["id"]
        items.append(item)
        seen_paths.add(item["path"])
    for item_id, target, role in [
        ("G1A_QUORUM_VERDICT_INPUT", QUORUM_INPUT, "DISTINCT_AGENT_VERDICT_SET"),
        ("G1A_MULTIAGENT_QUORUM_RECEIPT", QUORUM_RECEIPT, "FINAL_QUORUM_RECEIPT"),
        ("G1A_PREQUORUM_MACHINE_AUDIT", PREAUDIT, "PREQUORUM_MACHINE_AUDIT"),
        ("SESSION_POOL_ACTIVATION_SNAPSHOT", snapshot_path, "IMMUTABLE_SESSION_POOL_ACTIVATION"),
        ("G1A_EVIDENCE_RESOLUTION_PREISSUANCE", RESOLUTION, "PREISSUANCE_EVIDENCE_GRAPH"),
        ("G1A_FINALIZER_SOURCE", Path(__file__), "REPRODUCIBLE_FINALIZATION_SOURCE"),
    ]:
        if rel(target) in seen_paths:
            continue
        item = record(target, role, "ACTIVE_FINAL_EVIDENCE")
        item["id"] = item_id
        items.append(item)
        seen_paths.add(item["path"])
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)) or len(seen_paths) != len(items):
        raise RuntimeError("Final V3 lock IDs or paths are not unique")
    final_lock = {
        "schema": "B51R1_PHASE2A_INPUT_LOCK_V3_FINAL",
        "generated_at": now(),
        "status": "PASS_FINAL_HASH_LOCKED_AFTER_DISTINCT_AGENT_QUORUM",
        "authority_type": "OWNER_STANDING_DELEGATION",
        "source_prequorum_lock": record(PRELOCK, "PREQUORUM_HASH_GRAPH_ROOT"),
        "self_included": False,
        "dynamic_live_session_ledger_excluded": rel(LEDGER),
        "immutable_session_activation_snapshot": rel(snapshot_path),
        "locked_item_count": len(items),
        "locked_items": items,
    }
    write_json(FINAL_LOCK, final_lock)
    final_lock_sha = sha(FINAL_LOCK)
    (FINAL_LOCK.with_suffix(FINAL_LOCK.suffix + ".sha256")).write_text(final_lock_sha + "\n", encoding="utf-8", newline="\n")

    g1a = {
        "schema": "B51R1_G1A_MACHINE_RATIFICATION_RECEIPT_V2",
        "generated_at": now(),
        "status": "G1A_PASS_DELEGATED_MACHINE_RATIFIED_AND_HASH_LOCKED",
        "authority_type": "OWNER_STANDING_DELEGATION",
        "delegation_charter_path": rel(CHARTER_PATH),
        "delegation_charter_sha256": CHARTER_SHA,
        "agent_quorum": record(QUORUM_RECEIPT, "STRICT_DISTINCT_AGENT_QUORUM"),
        "red_team_status": "PASS_NO_OPEN_CURRENT_GATE_CRITICAL_OR_HIGH",
        "machine_evidence_paths": [
            record(PREAUDIT, "PREQUORUM_MACHINE_AUDIT"),
            record(FINAL_LOCK, "FINAL_V3_INPUT_LOCK"),
            record(RESOLUTION, "PREISSUANCE_EVIDENCE_GRAPH"),
            record(MANIFEST, "EXACT_ARTIFACT_MANIFEST"),
            record(DISPOSITIONS, "FINDING_DISPOSITION_REGISTER"),
        ],
        "input_lock_sha256": final_lock_sha,
        "solidworks_process_count": 0,
        "native_cad_created": False,
        "claim_limit": "G1A_PASS_ONLY_NATIVE_CAD_NOT_CREATED",
    }
    write_json(G1A_RECEIPT, g1a)

    g1b = {
        "schema": "B51R1_G1B_STANDING_SESSION_ADMISSION_V1",
        "generated_at": now(),
        "status": "G1B_PASS_STANDING_SESSION_ADMISSION",
        "authority_type": "OWNER_STANDING_DELEGATION",
        "g1a_receipt": record(G1A_RECEIPT, "G1A_MACHINE_RATIFICATION"),
        "g1a_receipt_sha256": sha(G1A_RECEIPT),
        "input_lock": record(FINAL_LOCK, "FINAL_V3_INPUT_LOCK"),
        "input_lock_sha256": final_lock_sha,
        "session_pool_activation_snapshot": record(snapshot_path, "IMMUTABLE_SESSION_POOL_ACTIVATION"),
        "session_pool_ledger": record(LEDGER, "LIVE_SESSION_POOL_AT_ADMISSION"),
        "session_pool_ledger_sha256": sha(LEDGER),
        "s01_prerequisite": "SATISFIED",
        "s01_authorized": True,
        "single_process_only": True,
        "visible_launch_budget": ledger["budget"],
        "remaining_before_s01": ledger["remaining"],
        "non_delegable_boundaries_retained": True,
        "claim_limit": "S01_ISOLATED_NATIVE_MASTER_SKELETON_SESSION_ONLY",
    }
    write_json(G1B_RECEIPT, g1b)

    build_resolution(FINAL_RESOLUTION, "POST_G1A_G1B_ISSUANCE")

    lock_failures = []
    for item in read_json(FINAL_LOCK)["locked_items"]:
        target = ROOT / Path(item["path"])
        if not target.is_file() or target.stat().st_size != item["bytes"] or sha(target) != item["sha256"]:
            lock_failures.append(item["id"])
    final_sw_processes = sw_processes()
    stage_a_unchanged = sha(STAGE_A) == STAGE_A_SHA
    final_skeleton_exists = FINAL_SKELETON.exists()
    final_status = (
        "PASS_G1A_G1B_S01_ADMITTED"
        if not lock_failures and not final_sw_processes and stage_a_unchanged and not final_skeleton_exists
        else "FAIL_CLOSED"
    )
    final_audit = {
        "schema": "B51R1_G1A_G1B_FINAL_MACHINE_AUDIT_V1",
        "generated_at": now(),
        "status": final_status,
        "final_lock": record(FINAL_LOCK, "FINAL_V3_INPUT_LOCK"),
        "locked_items": len(items),
        "lock_failures": lock_failures,
        "g1a": record(G1A_RECEIPT, "G1A_PASS_RECEIPT"),
        "g1b": record(G1B_RECEIPT, "G1B_PASS_RECEIPT"),
        "final_evidence_resolution": record(FINAL_RESOLUTION, "POSTISSUANCE_EVIDENCE_GRAPH"),
        "dispositions_closed": sum(1 for row in disposition_rows if row["a0_a6_disposition"] == "CLOSED"),
        "deferred_holds_retained": sum(1 for row in disposition_rows if row["a0_a6_disposition"] == "APPROVED_DEFERRED_HOLD_REGISTERED"),
        "stage_a_unchanged": stage_a_unchanged,
        "solidworks_processes": final_sw_processes,
        "final_skeleton_exists": final_skeleton_exists,
        "h10": composition["h10"],
        "t005": {key: composition["t005"][key] for key in ["A", "B", "C"]},
    }
    if final_audit["status"] != "PASS_G1A_G1B_S01_ADMITTED" or final_audit["final_skeleton_exists"]:
        write_json(FINAL_AUDIT, final_audit)
        raise RuntimeError("Final G1A/G1B audit failed closed")
    write_json(FINAL_AUDIT, final_audit)

    index_candidates = sorted(
        [path for path in CLOSURE.rglob("*") if path.is_file() and path not in {INDEX, INDEX.with_suffix(INDEX.suffix + ".sha256")}]
        + [PREAUDIT, FINAL_AUDIT]
    )
    index = {
        "schema": "B51R1_G1A_G1B_CLOSURE_INDEX_V1",
        "generated_at": now(),
        "status": "PASS_G1A_G1B_S01_ADMITTED_NATIVE_CAD_NOT_CREATED",
        "self_included": False,
        "items": [record(path, "CLOSURE_EVIDENCE") for path in index_candidates],
    }
    write_json(INDEX, index)
    index_sha = sha(INDEX)
    (INDEX.with_suffix(INDEX.suffix + ".sha256")).write_text(index_sha + "\n", encoding="utf-8", newline="\n")

    zip_path = ROOT / "09_DELIVERY/B51R1_AUTONOMOUS_G1A_G1B_CLOSURE_20260802.zip"
    if zip_path.exists():
        raise RuntimeError(f"Refusing to overwrite delivery ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in index_candidates + [INDEX, INDEX.with_suffix(INDEX.suffix + ".sha256")]:
            archive.write(path, rel(path))
    (zip_path.with_suffix(zip_path.suffix + ".sha256")).write_text(sha(zip_path) + "\n", encoding="utf-8", newline="\n")

    print(
        json.dumps(
            {
                "status": "G1A_G1B_PASS_S01_ADMITTED",
                "prelock_sha256": EXPECTED_PRELOCK_SHA,
                "final_lock_items": len(items),
                "final_lock_sha256": final_lock_sha,
                "g1a_sha256": sha(G1A_RECEIPT),
                "g1b_sha256": sha(G1B_RECEIPT),
                "final_audit_sha256": sha(FINAL_AUDIT),
                "delivery_zip": rel(zip_path),
                "delivery_zip_sha256": sha(zip_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
