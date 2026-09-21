"""Build source-bound, Excel-readable CSV lists for WP05 CAD candidates.

Standard library only: no SolidWorks, CAD, source edits, procurement quantity,
or manufacturing release. Each pose has its own 585-instance list. Canonical
geometry counts use the maximum across poses, never the sum across poses.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
STATES = ("parking", "released", "service")
ROLES = {"PHYSICAL_GEOMETRY", "SIMPLIFIED_PROXY", "FUNCTIONAL_ENVELOPE"}
SCOPE = "CAD_CANDIDATE_NOT_MANUFACTURING_BOM"
QUANTITY_SCOPE = "MAXIMUM_OF_SEPARATE_POSES_NOT_PROCUREMENT_QUANTITY"
INSTANCE_COLUMNS = (
    "state", "configuration", "original_instance_id", "representation_role",
    "product_role", "parent_assembly", "original_pn", "canonical_part_key",
    "native_relative_path", "native_sha256", "native_receipt_status",
    "native_geometry_receipt_status", "canonical_step_relative_path",
    "canonical_step_sha256", "geometry_source_basis", "upstream_geometry_path",
    "upstream_geometry_sha256", "supplier_name", "supplier_part_number",
    "supplier_source_reference", "supplier_evidence_status", "source_revision",
    "arm_link", "mount_interface", "allocated_mass_kg", "mass_source",
    "mass_value_status", "source_mass_kg", "digital_body_allocated_mass_kg",
    "digital_body_allocation_basis", "digital_body_mass_source", "digital_body_mass_owner",
    "digital_body_allocation_status", "digital_body_allocation_source_path",
    "digital_body_allocation_source_sha256", "digital_body_allocation_json_pointer",
    "qualification_status", "scope", "manufacturing_release",
)
CANONICAL_COLUMNS = (
    "canonical_part_key", "representation_role", "original_pn_values",
    "original_instance_ids", "native_relative_path", "native_sha256",
    "native_receipt_status", "native_geometry_receipt_status",
    "canonical_step_relative_path", "canonical_step_sha256", "geometry_source_basis",
    "upstream_geometry_path", "upstream_geometry_sha256", "supplier_name_values",
    "supplier_part_number_values", "supplier_source_reference_values",
    "supplier_evidence_status", "qty_parking", "qty_released", "qty_service",
    "qty_max_of_separate_states", "quantity_scope", "allocated_mass_value_set_kg",
    "mass_source_values", "unknown_mass_instances_parking", "unknown_mass_instances_released",
    "unknown_mass_instances_service", "digital_body_allocated_mass_value_set_kg",
    "digital_body_allocation_basis_values", "digital_body_mass_source_values",
    "digital_body_allocation_status_values", "digital_body_allocation_source_path",
    "digital_body_allocation_source_sha256", "digital_body_known_instances_parking",
    "digital_body_known_instances_released", "digital_body_known_instances_service",
    "digital_body_unknown_instances_parking", "digital_body_unknown_instances_released",
    "digital_body_unknown_instances_service", "qualification_status_values", "scope",
    "manufacturing_release",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def relative(path, root):
    p = Path(path).resolve()
    require(p.is_relative_to(root), "Package path escapes WP05: " + str(p))
    return p.relative_to(root).as_posix()


def text(value):
    return "" if value is None else str(value)


def values(rows, key):
    return " | ".join(sorted({text(r.get(key)) for r in rows if r.get(key) not in (None, "")}))


def explicit_source(row, part, key):
    """Only copy an explicit supplier field; do not infer a vendor from IDs."""
    return row[key] if key in row else part.get(key)


def mass_status(row):
    value = row.get("source_mass_kg")
    if value is None:
        return "UNKNOWN_VALUE_EMPTY"
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            "Invalid recorded mass for " + str(row.get("id")))
    if row.get("mass_source") in (None, "UNKNOWN"):
        return "SOURCE_DECLARED_UNKNOWN_VALUE_PRESERVED"
    return "EXPLICIT_SOURCE_ZERO_PRESERVED" if value == 0 else "SOURCE_ALLOCATION_ONLY_NOT_AS_BUILT"


def geometry_status(native):
    if native is None:
        return "NATIVE_IMPORT_MISSING"
    comparison = native.get("source_comparison", {})
    if comparison.get("pass") is True:
        return "SCALAR_SOURCE_COMPARISON_RECORDED_PASS"
    if comparison.get("roundtrip_validation", {}).get("status") == "PASS":
        return "SAME_KERNEL_ROUNDTRIP_RECORDED_PASS_SEE_INDEPENDENT_AUDIT"
    return comparison.get("status", "GEOMETRY_ACCEPTANCE_PENDING")


def normalized_hash_map(mapping):
    return {str(Path(p).resolve()).casefold():h.lower() for p,h in mapping.items()}


def load_digital_body_allocations(manifest):
    """Read actual per-ID mass atoms, bound to the same frozen source receipts.

    No aggregate total is used to populate a row. Arm allocations are checked
    against the hash-bound accepted URDF link mass, while original CAD source
    mass values remain separate and unchanged.
    """
    candidate = Path(manifest["source_candidate"]).resolve()
    old = candidate.parent
    handoff_path = candidate/"results/DYNAMICS_HANDOFF.json"
    audit_path = old/"review/ROBOT_ACTUAL_LEDGER_RECHECK.json"
    seal_path = old/"results/FINAL_ARTIFACT_MANIFEST.json"
    required_files = (handoff_path,audit_path,seal_path)
    absent = [str(p) for p in required_files if not p.is_file()]
    if absent:
        return {},dict(status="NOT_READ_REQUIRED_BINDING_FILE_ABSENT",missing_files=absent,input_sha256={})
    pinned = {}
    def pin(path, expected=None):
        path = Path(path).resolve()
        digest = sha256(path)
        require(expected is None or digest.lower() == str(expected).lower(), "Digital allocation source hash mismatch: "+str(path))
        pinned[str(path)] = digest
        return digest
    seal_hash = pin(seal_path)
    seal = read_json(seal_path)
    require(seal.get("schema") == "WP04_FINAL_ARTIFACT_MANIFEST_V1", "Unsupported WP04 final seal schema")
    sealed = {str((old/r["path"]).resolve()).casefold():r["sha256"] for r in seal["files"]}
    for path in (handoff_path,audit_path):
        require(str(path).casefold() in sealed, "Digital ledger/review is not in the final WP04 seal")
        pin(path,sealed[str(path).casefold()])
    handoff_hash = pinned[str(handoff_path)]
    handoff, review = read_json(handoff_path), read_json(audit_path)
    require(review.get("schema") == "WP04_INDEPENDENT_ACTUAL_LEDGER_RECHECK_V1"
            and review.get("all_passed") is True and review.get("checks")
            and all(c.get("passed") is True for c in review["checks"]), "Prior independent digital-body ledger review is not complete")
    require(review.get("input_sha256_before") == review.get("input_sha256_after"), "Prior independent ledger review source hashes disagree")
    review_inputs = normalized_hash_map(review["input_sha256_before"])
    require(review_inputs.get(str(handoff_path).casefold()) == handoff_hash, "Prior independent review does not bind this exact handoff")
    require(handoff.get("schema") == "WP03_DYNAMICS_HANDOFF_V1"
            and handoff.get("source_files_unchanged") is True
            and handoff.get("status") == "CANDIDATE_ALLOCATED_MASS_PROPERTIES_NO_QUALIFICATION_CREDIT", "Unexpected or promoted digital ledger status")
    require(handoff["units"]["mass"] == "kg", "Digital allocation mass units must be kg")
    handoff_inputs = normalized_hash_map(handoff["input_sha256"])
    manifest_inputs = normalized_hash_map(manifest["source_sha256_before"])
    for path,digest in handoff["input_sha256"].items():
        pin(path,digest)
    urdf_paths = [Path(p).resolve() for p in handoff["input_sha256"] if Path(p).name.lower() == "arm_b601_v1.urdf"]
    require(len(urdf_paths) == 1, "A unique accepted arm URDF source is required")
    urdf = ET.parse(urdf_paths[0]).getroot()
    urdf_masses = {link.attrib["name"]:float(link.find("inertial/mass").attrib["value"])
                   for link in urdf.findall("link") if link.find("inertial/mass") is not None}
    states = handoff.get("states")
    require(isinstance(states,list) and {s.get("state") for s in states} == set(STATES)
            and len(states) == 3, "Digital ledger must contain exactly the three source states")
    allocations, summaries = {},{}
    for state_index,state_data in enumerate(states):
        state = state_data["state"]
        receipt_path = candidate/"results"/(state+"_instances.json")
        key = str(receipt_path).casefold()
        require(key in handoff_inputs and key in manifest_inputs
                and handoff_inputs[key] == manifest_inputs[key], "WP05 and digital ledger bind different source instance receipts: "+state)
        binding = handoff["receipt_bindings"][state]
        require(Path(binding["receipt_path"]).resolve() == receipt_path
                and binding["receipt_sha256"] == handoff_inputs[key]
                and binding["configuration"] == manifest["states"][state]["configuration"], "Digital body pose receipt binding differs: "+state)
        receipt = read_json(receipt_path)
        original_rows = {r["id"]:r for r in receipt["instances"]}
        wp05_rows = {r["id"]:r for r in manifest["states"][state]["instances"]}
        require(len(original_rows) == len(wp05_rows) == 585 and set(original_rows) == set(wp05_rows), "Digital body instance coverage differs: "+state)
        for ident,current in wp05_rows.items():
            original = original_rows[ident]
            for a,b in (("T_S_local","T_S_local"),("representation_role","representation_role"),
                        ("product_role","product_role"),("arm_link","arm_link"),
                        ("source_revision","source_revision"),("pn","pn"),
                        ("source_mass_kg","mass_kg"),("mass_source","mass_source")):
                require(current.get(a) == original.get(b), "WP05 source metadata differs before mass join: "+state+":"+ident+":"+a)
        require(state_data["q_deg"] == manifest["states"][state]["q_deg"]
                and state_data["finger_mm"] == manifest["states"][state]["finger_mm"]
                and state_data["T_S_arm_base_mm"] == manifest["states"][state]["T_S_arm_base"], "Digital body pose differs: "+state)
        require(state_data.get("onboard_full_physical_mass_properties_complete") is False, "Digital mass ledger promoted to full physical mass")
        group = state_data["groups"]["ONBOARD_CANDIDATE"]
        atoms,unknown = group["mass_atoms"],group["unknown_mass_instances"]
        require(not state_data.get("zero_contribution_instances"), "Unexpected zero-contribution schema; no implicit zero conversion allowed")
        require(len(atoms)+len(unknown) == 585, "Digital allocation known/unknown coverage is not exhaustive")
        merged,owners = {},set()
        for kind,entries in (("mass_atoms",atoms),("unknown_mass_instances",unknown)):
            for index,entry in enumerate(entries):
                ident,owner = entry["id"],entry["mass_owner"]
                require(ident in original_rows and ident not in merged and owner not in owners, "Duplicate or unmapped digital mass ID/owner")
                original = original_rows[ident]
                require(original["mass_owner"] == owner, "Digital mass owner differs from frozen instance")
                for field in ("pn","product_role","representation_role","parent_assembly","mount_interface","source_revision"):
                    require(entry.get(field) == original.get(field), "Digital atom identity differs: "+ident+":"+field)
                mass = entry.get("mass_kg")
                if kind == "mass_atoms":
                    require(type(mass) in (int,float) and math.isfinite(mass) and mass > 0, "Invalid positive digital mass allocation")
                    require(abs(mass-state_data["mass_owner_values"][owner]) <= 1e-12, "Digital owner amount differs from atom")
                    if original.get("arm_link"):
                        link = original["arm_link"]
                        require(entry.get("arm_link") == link and entry.get("mass_source") == "SOURCE_DIGITAL", "Arm digital allocation link/source mismatch")
                        require(link in urdf_masses and abs(mass-urdf_masses[link]) <= 1e-12
                                and abs(mass-handoff["source_arm_bodies"][link]["mass_kg"]) <= 1e-12, "Arm mass atom differs from accepted URDF SSOT: "+link)
                    else:
                        require(original.get("mass_kg") is not None and abs(mass-original["mass_kg"]) <= 1e-12, "Nonarm digital atom changed source mass")
                    basis,status = entry.get("mass_basis"),"SOURCE_ALLOCATION_NOT_AS_BUILT"
                    require(isinstance(basis,str) and bool(basis), "Positive digital atom mass basis missing")
                else:
                    require(mass is None and original.get("mass_kg") is None and not original.get("arm_link"), "Unknown digital allocation was replaced by a value")
                    require(owner not in state_data["mass_owner_values"], "Unknown mass owner has a numeric allocation")
                    basis,status = entry.get("reason"),"UNKNOWN_MASS_NOT_ZERO"
                merged[ident] = dict(digital_body_allocated_mass_kg=mass,digital_body_allocation_basis=basis,
                    digital_body_mass_source=entry.get("mass_source"),digital_body_mass_owner=owner,
                    digital_body_allocation_status=status,digital_body_allocation_source_path=str(handoff_path),
                    digital_body_allocation_source_sha256=handoff_hash,
                    digital_body_allocation_json_pointer=f"/states/{state_index}/groups/ONBOARD_CANDIDATE/{kind}/{index}")
                owners.add(owner)
        require(set(merged) == set(original_rows), "Digital atom/unknown IDs do not cover the actual instance IDs")
        total = math.fsum(e["mass_kg"] for e in atoms)
        require(abs(total-group["known_mass_kg"]) <= 1e-10, "Per-ID digital allocations disagree with declared ledger aggregate")
        allocations[state] = merged
        summaries[state] = dict(positive_allocated_instances=len(atoms),unknown_instances=len(unknown),
            allocated_subset_mass_kg=total,arm_positive_instances=sum(bool(e.get("arm_link")) for e in atoms),
            arm_source_digital_mass_kg=math.fsum(e["mass_kg"] for e in atoms if e.get("arm_link")))
    require(all(sha256(p) == h for p,h in pinned.items()), "Frozen digital allocation input changed while reading")
    return allocations,dict(status="BOUND_PER_INSTANCE_LEDGER_READ",source_path=str(handoff_path),source_sha256=handoff_hash,
        prior_independent_review_path=str(audit_path),prior_independent_review_sha256=pinned[str(audit_path)],
        final_wp04_seal_path=str(seal_path),final_wp04_seal_sha256=seal_hash,
        accepted_arm_urdf_path=str(urdf_paths[0]),accepted_arm_urdf_sha256=pinned[str(urdf_paths[0])],
        input_sha256=pinned,state_summaries=summaries,
        scope="Hash-bound prior per-ID digital allocations; no aggregate-derived imputation and no as-built mass claim")


def assemble_rows(manifest, imports, root, allow_partial=False, digital_allocations=None):
    """Pure data transformation; the CLI separately binds files and hashes."""
    require(manifest.get("schema") == "WP05_SW_PART_SOURCE_V1", "Unexpected source schema")
    require(manifest.get("smoke") is False, "Smoke geometry is not a full BOM source")
    require(manifest.get("status") == "PASS_SOURCE_GEOMETRY_EXPORT_ONLY", "Final source export required")
    require(set(manifest.get("states", {})) == set(STATES), "All three states are required")
    parts = {p["part_key"]:p for p in manifest["parts"]}
    require(len(parts) == len(manifest["parts"]), "Duplicate canonical part key")
    native = {p["part_key"]:p for p in imports.get("parts", [])}
    require(len(native) == len(imports.get("parts", [])), "Duplicate native import key")
    require(not (set(native) - set(parts)), "Native imports contain unregistered canonical keys")
    missing = sorted(set(parts) - set(native))
    require(allow_partial or not missing, "Native imports incomplete; wait for completion or explicitly use --allow-partial")
    outputs, seen_ids, role_by_id = {}, None, None
    for state in STATES:
        data = manifest["states"][state]
        original = data["instances"]
        ids = {r["id"] for r in original}
        require(len(original) == len(ids) == 585, "Expected 585 unique instances in " + state)
        require(seen_ids is None or ids == seen_ids, "Instance IDs changed between states")
        seen_ids = ids
        roles = {r["id"]:r["representation_role"] for r in original}
        require(role_by_id is None or roles == role_by_id, "Representation roles changed between states")
        role_by_id = roles
        rows = []
        for r in original:
            p = parts[r["part_key"]]
            n = native.get(r["part_key"])
            require(r["representation_role"] in ROLES, "Unknown representation role")
            require(r["representation_role"] == p["representation_role"], "Canonical role mismatch")
            if n:
                require(n.get("source_sha256") == p["sha256"], "Native/source hash binding differs")
                require(Path(n["source"]).resolve() == Path(p["path"]).resolve(), "Native source path mismatch")
                require(n.get("representation_role") == r["representation_role"], "Native receipt role differs from instance role")
            upstream = p.get("source_geometry", p.get("source_step", {}))
            supplier = {k:explicit_source(r, p, k) for k in ("supplier_name", "supplier_part_number", "supplier_source_reference")}
            digital = (digital_allocations or {}).get(state,{}).get(r["id"])
            if digital is None:
                digital = dict(digital_body_allocated_mass_kg=None,digital_body_allocation_basis=None,
                    digital_body_mass_source=None,digital_body_mass_owner=None,digital_body_allocation_status="NOT_READ",
                    digital_body_allocation_source_path=None,digital_body_allocation_source_sha256=None,
                    digital_body_allocation_json_pointer=None)
            rows.append(dict(
                state=state, configuration=data.get("configuration"), original_instance_id=r["id"],
                representation_role=r["representation_role"], product_role=r.get("product_role"),
                parent_assembly=r.get("parent_assembly"), original_pn=r.get("pn"),
                canonical_part_key=r["part_key"],
                native_relative_path=relative(n["target"], root) if n else None,
                native_sha256=n.get("native_save", {}).get("sha256") if n else None,
                native_receipt_status=n.get("status") if n else "NATIVE_IMPORT_MISSING",
                native_geometry_receipt_status=geometry_status(n),
                canonical_step_relative_path=relative(p["path"], root), canonical_step_sha256=p["sha256"],
                geometry_source_basis=p.get("source_basis"), upstream_geometry_path=upstream.get("path"),
                upstream_geometry_sha256=upstream.get("sha256"), **supplier,
                supplier_evidence_status="EXPLICIT_SOURCE_FIELD_ONLY_UNVERIFIED" if any(supplier.values()) else "NOT_PROVIDED",
                source_revision=r.get("source_revision"), arm_link=r.get("arm_link"),
                mount_interface=r.get("mount_interface"), allocated_mass_kg=r.get("source_mass_kg"),
                mass_source=r.get("mass_source"), mass_value_status=mass_status(r),
                source_mass_kg=r.get("source_mass_kg"),**digital,
                qualification_status=r.get("qualification_status"), scope=SCOPE, manufacturing_release=False))
        outputs[state] = rows
    grouped = defaultdict(list)
    for rows in outputs.values():
        for row in rows:
            grouped[row["canonical_part_key"]].append(row)
    require(set(grouped) == set(parts), "Unreferenced canonical geometry in manifest")
    canonical = []
    for key in sorted(grouped):
        rows = grouped[key]
        sample = rows[0]
        counts = Counter(r["state"] for r in rows)
        unknown = Counter(r["state"] for r in rows if r["allocated_mass_kg"] is None or r["mass_source"] in (None,"UNKNOWN"))
        digital_known = Counter(r["state"] for r in rows if r["digital_body_allocated_mass_kg"] is not None)
        digital_unknown = Counter(r["state"] for r in rows if r["digital_body_allocation_status"] == "UNKNOWN_MASS_NOT_ZERO")
        canonical.append(dict(
            canonical_part_key=key, representation_role=sample["representation_role"],
            original_pn_values=values(rows,"original_pn"), original_instance_ids=values(rows,"original_instance_id"),
            **{field:sample[field] for field in ("native_relative_path", "native_sha256", "native_receipt_status",
               "native_geometry_receipt_status", "canonical_step_relative_path", "canonical_step_sha256",
               "geometry_source_basis", "upstream_geometry_path", "upstream_geometry_sha256")},
            supplier_name_values=values(rows,"supplier_name"), supplier_part_number_values=values(rows,"supplier_part_number"),
            supplier_source_reference_values=values(rows,"supplier_source_reference"),
            supplier_evidence_status=values(rows,"supplier_evidence_status"),
            **{"qty_"+s:counts[s] for s in STATES}, qty_max_of_separate_states=max(counts.values()),
            quantity_scope=QUANTITY_SCOPE, allocated_mass_value_set_kg=values(rows,"allocated_mass_kg"),
            mass_source_values=values(rows,"mass_source"),
            **{"unknown_mass_instances_"+s:unknown[s] for s in STATES},
            digital_body_allocated_mass_value_set_kg=values(rows,"digital_body_allocated_mass_kg"),
            digital_body_allocation_basis_values=values(rows,"digital_body_allocation_basis"),
            digital_body_mass_source_values=values(rows,"digital_body_mass_source"),
            digital_body_allocation_status_values=values(rows,"digital_body_allocation_status"),
            digital_body_allocation_source_path=sample["digital_body_allocation_source_path"],
            digital_body_allocation_source_sha256=sample["digital_body_allocation_source_sha256"],
            **{"digital_body_known_instances_"+s:digital_known[s] for s in STATES},
            **{"digital_body_unknown_instances_"+s:digital_unknown[s] for s in STATES},
            qualification_status_values=values(rows,"qualification_status"),scope=SCOPE,manufacturing_release=False))
    return outputs, canonical, missing


def csv_bytes(columns, rows):
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="raise", lineterminator="\r\n")
    writer.writeheader()
    writer.writerows({k:text(v) for k,v in row.items()} for row in rows)
    return stream.getvalue().encode("utf-8-sig")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT/"results/PARTS_SOURCE_MANIFEST_DEDUP.json")
    parser.add_argument("--imports", type=Path, default=ROOT/"results/NATIVE_IMPORTS.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT/"bom")
    parser.add_argument("--allow-partial", action="store_true", help="Keep missing native fields empty and explicitly mark partial output")
    parser.add_argument("--check-only", action="store_true", help="Validate source data and file hashes; create no output files")
    args = parser.parse_args(argv)
    root, destination = ROOT.resolve(), args.output_dir.resolve()
    require(destination.is_relative_to(root), "BOM output must stay inside WP05")
    input_hashes = {str(p.resolve()):sha256(p) for p in (args.manifest,args.imports)}
    manifest, imports = read_json(args.manifest),read_json(args.imports)
    require(imports.get("manifest_sha256") == input_hashes[str(args.manifest.resolve())], "Native imports bind another source manifest")
    digital_allocations,digital_binding = load_digital_body_allocations(manifest)
    rows, canonical, missing = assemble_rows(manifest,imports,root,args.allow_partial,digital_allocations)
    native_by_key = {p["part_key"]:p for p in imports.get("parts",[])}
    verified = []
    for p in manifest["parts"]:
        require(sha256(p["path"]) == p["sha256"], "Source STEP changed: "+p["part_key"])
        if p["part_key"] in native_by_key:
            n = native_by_key[p["part_key"]]
            require(sha256(n["target"]) == n["native_save"]["sha256"], "Native file changed: "+p["part_key"])
            verified.append(p["part_key"])
    require(all(sha256(p)==h for p,h in input_hashes.items()), "Input receipt changed while reading; rerun after the producer completes")
    artifacts = {"WP05_INSTANCES_"+s.upper()+".csv":csv_bytes(INSTANCE_COLUMNS,rows[s]) for s in STATES}
    artifacts["WP05_CANONICAL_PARTS.csv"] = csv_bytes(CANONICAL_COLUMNS,canonical)
    receipt = dict(schema="WP05_CAD_CANDIDATE_BOM_V2",generated_utc=datetime.now(timezone.utc).isoformat(),
        status="PARTIAL_NATIVE_CAD_CANDIDATE_LIST" if missing else "NATIVE_CAD_CANDIDATE_LISTS_GENERATED",
        script_sha256=sha256(__file__),input_sha256=input_hashes,encoding="UTF-8 with BOM",null_cell_policy="Empty cells preserve unknown/missing values; no zero imputation",
        instance_counts={s:len(rows[s]) for s in STATES},canonical_geometry_count=len(canonical),
        role_counts_by_state={s:dict(Counter(r["representation_role"] for r in rows[s])) for s in STATES},
        known_source_allocations_by_state={s:{"non_null_value_count":sum(r["allocated_mass_kg"] is not None for r in rows[s]),
            "null_value_count":sum(r["allocated_mass_kg"] is None for r in rows[s]),
            "sum_of_recorded_non_null_values_kg":math.fsum(r["allocated_mass_kg"] for r in rows[s] if r["allocated_mass_kg"] is not None),
            "scope":"Recorded instance allocations only, not the complete robot mass and not inferred from native material defaults"} for s in STATES},
        digital_body_allocation_binding=digital_binding,
        digital_body_allocations_by_state={s:{"non_null_value_count":sum(r["digital_body_allocated_mass_kg"] is not None for r in rows[s]),
            "unknown_value_count":sum(r["digital_body_allocation_status"] == "UNKNOWN_MASS_NOT_ZERO" for r in rows[s]),
            "not_read_count":sum(r["digital_body_allocation_status"] == "NOT_READ" for r in rows[s]),
            "sum_of_per_instance_digital_allocations_kg":math.fsum(r["digital_body_allocated_mass_kg"] for r in rows[s] if r["digital_body_allocated_mass_kg"] is not None) if digital_binding["status"] == "BOUND_PER_INSTANCE_LEDGER_READ" else None,
            "scope":"Prior hash-bound digital-body allocated subset, including per-link accepted URDF arm masses; unknown remainder stays empty and full physical mass is not established"} for s in STATES},
        mass_column_rule="allocated_mass_kg and its explicit source_mass_kg alias preserve the original geometry receipt field; digital_body_allocated_mass_kg is a separate per-ID digital-body ledger allocation. These columns are not added together.",
        native_files_hash_verified_count=len(verified),missing_native_part_keys=missing,
        output_files=[dict(file=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in artifacts.items()],
        quantity_rule="Per canonical geometry: max(qty_parking,qty_released,qty_service), never their sum. Summing maxima across pose-specific variants is not a procurement BOM.",
        pn_rule="Original PN text is preserved verbatim; historical size strings are not silently corrected or treated as the geometry authority.",
        supplier_rule="Only explicit supplier fields are copied; geometry provenance is recorded separately and is not proof of a supplier selection.",
        scope=SCOPE,manufacturing_release=False,physical_assembly_completed=False,all_mechanical_design_complete=False)
    if not args.check_only:
        destination.mkdir(parents=True,exist_ok=True)
        for name,data in artifacts.items():
            target=destination/name
            temporary=target.with_suffix(target.suffix+".tmp")
            temporary.write_bytes(data)
            os.replace(temporary,target)
        (destination/"NATIVE_BOM_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError,KeyError,TypeError,ValueError) as exc:
        print(json.dumps(dict(status="BOM_NOT_GENERATED",reason=str(exc),manufacturing_release=False),ensure_ascii=False),file=sys.stderr)
        sys.exit(2)
