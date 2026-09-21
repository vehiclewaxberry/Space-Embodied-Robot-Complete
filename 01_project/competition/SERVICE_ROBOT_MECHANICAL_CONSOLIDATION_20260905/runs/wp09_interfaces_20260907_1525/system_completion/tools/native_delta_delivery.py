"""Validate recorded native CAD evidence and create a whitelist-only delivery ZIP.

No SolidWorks, COM, OCC, process control, or geometry generation is used here.
Run only after the three integrations, six cold reads and physical relocation
have finished and C/cad has returned to its original location.
Missing or inconsistent evidence raises before publishing the delivery index.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parents[1]
D = C / "cad"
N = C.parent / "reuse_closure"
RESULTS = C / "results"
STATES = ("service", "parking", "released")
PART_STATUSES = {
    "NATIVE_PART_SAVED_CLOSED_REOPENED_VERIFIED_AND_CLOSED",
    "RECOVERED_OWN_SAVED_PART_COLD_GEOMETRY_VALIDATED",
}
COLD_STATUS = "PASS_COLD_NATIVE_DELTA_IDENTITIES_TRANSFORMS_LOCAL_DEPENDENCIES"
INTEGRATE_STATUS = "PASS_NATIVE_DELTA_SAVED_COLD_INSPECTION_PENDING"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    path = Path(path)
    require(path.is_file(), f"Missing file: {path}")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def same_file(path, expected):
    require(isinstance(expected, str) and len(expected) == 64,
            f"Missing SHA256 binding for {path}")
    actual = sha(path)
    require(actual == expected.lower(), f"SHA256 changed: {path}")
    return actual


def norm(path):
    return str(Path(path).resolve()).casefold()


def record(path):
    path = Path(path)
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def unique_by(rows, key, label):
    mapped = {row[key]: row for row in rows}
    require(len(mapped) == len(rows), f"Duplicate {label}")
    return mapped


def t16(T):
    require(len(T) == 4 and all(len(row) == 4 for row in T), "Invalid 4x4 matrix")
    return [T[i][j] for j in range(3) for i in range(3)] + [
        T[i][3] / 1000 for i in range(3)
    ] + [1., 0., 0., 0.]


def finite_number(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value), f"Non-finite or missing {label}")
    return float(value)


def bbox_error(a, b):
    require(len(a) == len(b) == 2 and all(len(v) == 3 for v in a + b),
            "Invalid bounding box")
    return max(abs(finite_number(a[i][k], "bbox") - finite_number(b[i][k], "bbox"))
               for i in range(2) for k in range(3))


def validate_parts(inputs, input_hash):
    expected = unique_by(inputs["parts"], "id", "part IDs")
    require(len(expected) == 138, "Expected exactly 138 new native part files")
    require(len({norm(p["native_path"]) for p in expected.values()}) == 138,
            "New native part paths must be unique")
    imports = []
    for path in sorted(RESULTS.glob("NATIVE_DELTA_IMPORT_*.json")):
        receipt = read(path)
        if receipt.get("input_manifest_sha256") == input_hash:
            imports.append((path, receipt))
    require(imports, "No bound native import receipts")
    proof = []
    for ident, item in expected.items():
        same_file(item["step_path"], item["source_sha256"])
        native_hash = sha(item["native_path"])
        require(Path(item["native_path"]).parent.resolve() == D.resolve(),
                f"New native path outside CAD directory: {ident}")
        candidates = []
        for path, receipt in imports:
            for part in receipt.get("parts", []):
                saved = part.get("native_save", {})
                if (part.get("id") == ident
                        and part.get("status") in PART_STATUSES
                        and part.get("source_sha256") == item["source_sha256"]
                        and saved.get("sha256") == native_hash
                        and norm(saved.get("path", "")) == norm(item["native_path"])
                        and "source_native_volume_error_mm3" in part):
                    candidates.append((path, receipt, part))
        require(candidates, f"No complete cold/volume receipt for {ident}")
        # A failed batch can contain fully completed parts. Only a completed
        # per-part record with matching source/native hashes receives credit.
        path, receipt, part = candidates[-1]
        cold = part["part_cold_reopen"]
        if "errors" in cold:
            require(cold["errors"] == 0, f"Part cold-open error: {ident}")
        if "warnings" in cold:
            require(cold["warnings"] == 0, f"Part cold-open warning: {ident}")
        facts = cold["facts"]
        require(facts["solid_count"] == 1 and facts["sheet_count"] == 0,
                f"Part body count mismatch: {ident}")
        require(len(facts["bodies"]) == 1, f"Missing cold body facts: {ident}")
        require(bbox_error(facts["bounds_mm"], item["expected_local_bbox_mm"]) <= 1e-4,
                f"Part bounds mismatch: {ident}")
        volume = finite_number(facts["volume_mm3"], f"cold volume {ident}")
        require(volume > 0, f"Nonpositive native solid volume: {ident}")
        err = abs(volume - item["expected_volume_mm3"])
        recorded_error = finite_number(part["source_native_volume_error_mm3"], ident)
        require(abs(err - recorded_error) <= max(1e-8, err * 1e-10),
                f"Recorded volume error mismatch: {ident}")
        frame = ident.startswith("wing_edge_frame_")
        if not frame:
            require(err <= max(1e-5, item["expected_volume_mm3"] * 1e-7),
                    f"Part volume tolerance exceeded: {ident}")
        for key in ("external_reference_count", "auxiliary_reference_count"):
            if key in part:
                require(part[key] == 0, f"Part references external files: {ident}")
        proof.append({
            "id": ident, "native": record(item["native_path"]),
            "source": record(item["step_path"]), "cold_receipt": record(path),
            "batch_status": receipt.get("status"), "part_status": part["status"],
            "source_native_volume_error_mm3": recorded_error,
            "cold_solid_count": 1, "cold_sheet_count": 0,
            "volume_basis": "SAME_KERNEL_FRAME_ROUNDTRIP_REQUIRED" if frame
                            else "COLD_NATIVE_SCALAR_MATCHES_SOURCE_TOLERANCE",
        })
    frame_path = RESULTS / "NATIVE_DELTA_FRAME_EQUIVALENCE.json"
    frame_receipt = read(frame_path)
    require(frame_receipt["status"] ==
            "PASS_8_NATIVE_ROUNDTRIPS_SAME_KERNEL_GEOMETRY_EQUIVALENCE",
            "Frame geometry equivalence has not passed")
    frames = unique_by(frame_receipt["rows"], "id", "frame IDs")
    frame_ids = {ident for ident in expected if ident.startswith("wing_edge_frame_")}
    require(set(frames) == frame_ids and len(frames) == 8, "Wrong frame equivalence membership")
    for ident, frame in frames.items():
        item = expected[ident]
        require(frame["pass_geometry_equivalence"] is True, f"Frame equivalence failed: {ident}")
        require(frame["source_sha256"] == item["source_sha256"]
                and norm(frame["source"]) == norm(item["step_path"])
                and norm(frame["native"]) == norm(item["native_path"]),
                f"Frame provenance mismatch: {ident}")
        for key in ("source", "native", "native_roundtrip", "old_source"):
            same_file(frame[key], frame[key + "_sha256"])
        require(frame["original_minus_native_solid_count"] == 0
                and frame["native_minus_original_solid_count"] == 0,
                f"Frame Boolean difference nonempty: {ident}")
        require(finite_number(frame["relative_volume_error"], ident) <=
                min(frame_receipt["relative_volume_tolerance"], 1e-7),
                f"Frame adaptive volume mismatch: {ident}")
    return expected, proof, record(frame_path)


def validate_cold(path, state, expected_rows, target, input_hash, relocated=False):
    receipt = read(path)
    require(receipt["status"] == COLD_STATUS, f"Cold read not passed: {path}")
    require(receipt["input_manifest_sha256"] == input_hash
            and receipt["mode"] == "cold" and receipt["state"] == state,
            f"Cold input/state mismatch: {path}")
    snapshot_path = RESULTS / "NATIVE_DELTA_IMPORTED_PARTS.json"
    same_file(snapshot_path, receipt["imported_parts_snapshot_sha256"])
    assembly_receipt_path = RESULTS / f"NATIVE_DELTA_INTEGRATE_{state}.json"
    require(norm(receipt["assembly_save_receipt"]) == norm(assembly_receipt_path),
            "Cold assembly-save receipt path mismatch")
    same_file(assembly_receipt_path, receipt["assembly_save_receipt_sha256"])
    save_receipt = read(assembly_receipt_path)
    require(save_receipt["status"] == INTEGRATE_STATUS
            and save_receipt["native_save"]["sha256"] == receipt["native_sha256"],
            "Cold assembly expected hash is not bound to completed integration")
    root = Path(receipt["root"])
    require(root.resolve() == (C / "d" if relocated else D).resolve(),
            f"Unexpected cold root: {root}")
    if relocated:
        require(norm(receipt["original_root"]) == norm(D)
                and receipt["original_root_absent_during_cold_open"] is True,
                "Relocation lacks recorded original-root absence during real cold open")
        require(D.is_dir() and not root.exists(), "Relocated CAD directory has not returned")
    require(receipt["open_errors"] == 0 and receipt["open_warnings"] == 0,
            f"Cold open reports errors/warnings: {path}")
    require(receipt["component_count"] == 873
            and receipt["expected_solids_hash_bound"] == 1254
            and receipt["external_dependency_count"] == 0
            and receipt["actual_all_body_readback_this_cold_open"] is False,
            f"Invalid cold count or evidence scope: {path}")
    require(receipt["open_documents_after"] == [], f"Owned CAD documents left open: {path}")
    same_file(target, receipt["native_sha256"])
    rows = unique_by(expected_rows, "id", "expected assembly IDs")
    observed = unique_by(receipt["components"], "id", "cold assembly IDs")
    recorded_rows = unique_by(receipt["rows"], "id", "cold planned IDs")
    require(len(rows) == 873 and set(rows) == set(observed) == set(recorded_rows),
            f"873 assembly ID membership mismatch: {state}")
    require(sum(row["expected_solids"] for row in rows.values()) == 1254,
            f"Inherited/current solid sum differs: {state}")
    max_transform_error = 0.0
    dependency_names = set()
    for ident, row in rows.items():
        part_path = D / Path(row["native_path"]).name
        actual_hash = sha(part_path)
        expected_hash = row.get("native_sha256")
        if expected_hash is not None:
            require(actual_hash == expected_hash, f"Retained part changed: {ident}")
        observation, cold_row = observed[ident], recorded_rows[ident]
        expected_recorded_path = root / part_path.name
        require(norm(observation["path"]) == norm(expected_recorded_path)
                and norm(cold_row["native_path"]) == norm(expected_recorded_path),
                f"Cold dependency path mismatch: {ident}")
        require(observation["sha256"] == cold_row["native_sha256"] == actual_hash,
                f"Cold part hash mismatch: {ident}")
        require(observation["fixed"] is True, f"Nonfixed component: {ident}")
        wanted = t16(row["T_S_local"])
        got = observation["transform_sw16"]
        require(len(got) == 16, f"Incomplete transform: {ident}")
        error = max(abs(finite_number(a, ident) - finite_number(b, ident))
                    for a, b in zip(got, wanted))
        require(error <= 1e-8, f"Native transform mismatch: {ident}")
        require(cold_row["T_S_local"] == row["T_S_local"],
                f"Cold transform contract changed: {ident}")
        max_transform_error = max(max_transform_error, error)
        dependency_names.add(part_path.name)
    hierarchy_path = RESULTS / 'NATIVE_DELTA_HIERARCHY_INPUTS.json'
    hierarchy = read(hierarchy_path)
    same_file(hierarchy_path, receipt['hierarchy_input_sha256'])
    require(save_receipt['hierarchy_input_sha256'] == receipt['hierarchy_input_sha256'], 'Hierarchy input binding differs')
    require(hierarchy['input_manifest_sha256'] == input_hash and hierarchy['imported_parts_snapshot_sha256'] == sha(snapshot_path), 'Hierarchy source snapshot differs')
    group_plan = unique_by(hierarchy['groups'], 'id', 'hierarchy group IDs')
    wanted_groups = hierarchy['states'][state]['groups']
    sealed_groups = unique_by(receipt['group_hash_seal'], 'id', 'sealed group IDs')
    require(receipt['group_hash_seal'] == save_receipt['group_hash_seal'] and set(sealed_groups) == set(wanted_groups), 'State group hash seal differs')
    parents = unique_by(receipt['parent_containers'], 'id', 'actual parent containers')
    require(set(parents) == set(wanted_groups) and receipt['top_level_container_count'] == receipt['recursive_container_count'] == len(wanted_groups) == 10, 'Container count or membership differs')
    identity = hierarchy['parent_transform_sw16']; group_leaf_ids = set()
    for ident in wanted_groups:
        group, frozen, actual = group_plan[ident], sealed_groups[ident], parents[ident]
        group_path = D / Path(group['path']).name
        same_file(group_path, frozen['sha256']); same_file(frozen['save_receipt'], frozen['save_receipt_sha256'])
        group_receipt = read(frozen['save_receipt'])
        require(group_receipt['status'] == 'PASS_FIXED_GROUP_NATIVE_SAVE_AND_COLD_READ' and group_receipt['hierarchy_input_sha256'] == sha(hierarchy_path), 'Group batch not completed or wrong source')
        matching = [g for g in group_receipt['groups'] if g['id'] == ident]
        require(len(matching) == 1, 'Duplicate/missing completed group record')
        gp = matching[0]
        require(gp['status'] == 'PASS_GROUP_SAVED_CLOSED_COLD_METADATA_AND_DEPENDENCIES' and gp['native_save']['sha256'] == frozen['sha256'] and gp['native_save']['errors'] == 0, 'Group save/cold proof not bound')
        planned = unique_by(group['rows'], 'id', 'group planned leaves')
        actual_group_leaves = unique_by(gp['cold_components'], 'id', 'group cold leaves')
        require(set(planned) == set(actual_group_leaves) and len(planned) == gp['leaf_count'] <= 96, 'Group leaf count or identity differs')
        require(not (group_leaf_ids & set(planned)), 'Leaf included by two group containers'); group_leaf_ids.update(planned)
        require(norm(actual['path']) == norm(root / group_path.name) and actual['fixed'] is True and actual['transform_sw16'] == identity, 'Actual parent identity/path differs')
        for leaf_id, leaf in planned.items():
            q, o, gcold = rows[leaf_id], observed[leaf_id], actual_group_leaves[leaf_id]
            require(o['parent_id'] == ident and o['parent_transform_sw16'] == identity, 'Actual leaf parent differs')
            require(leaf['T_S_local'] == q['T_S_local'] and leaf['native_sha256'] == q['native_sha256'] and norm(leaf['native_path']) == norm(q['native_path']), 'Group plan changes original native contract')
            require(gcold['sha256'] == q['native_sha256'] and gcold['fixed'] is True and len(gcold['transform_sw16']) == 16 and max(abs(finite_number(x, leaf_id)-finite_number(y, leaf_id)) for x,y in zip(gcold['transform_sw16'],t16(q['T_S_local']))) <= 1e-8, 'Group cold leaf proof differs')
        dependency_names.add(group_path.name)
    require(group_leaf_ids == set(rows), 'Hierarchy does not partition all 873 leaves')
    expected_paths = {norm(root / name) for name in dependency_names}
    require({norm(p) for p in receipt["dependencies"]} == expected_paths,
            f"Cold local dependencies differ from component membership: {state}")
    require(all(Path(p).resolve().parent == root.resolve()
                and Path(p).suffix.upper() in (".SLDPRT", ".SLDASM") for p in receipt["dependencies"]),
            f"Nonlocal or invalid hierarchy dependency: {state}")
    return receipt, dependency_names, {
        "state": state, "receipt": record(path), "root_at_cold_open": str(root),
        "component_count": 873, "expected_solids_hash_bound": 1254,
        "component_count_semantics": "LEAF_PART_INSTANCES_EXCLUDING_SUBASSEMBLY_CONTAINERS",
        "top_level_container_count": len(wanted_groups),
        "unique_dependency_count": len(dependency_names), "external_dependency_count": 0,
        "maximum_transform_error_sw16": max_transform_error,
        "physical_relocation": relocated,
        "original_root_absent_during_cold_open": True if relocated else None,
    }


def validate_parents(inputs):
    for path, digest in inputs["source_receipts_sha256"].items():
        same_file(path, digest)
    portable_path = RESULTS / "PORTABLE_DELIVERY.json"
    portable = read(portable_path)
    require(portable["status"] ==
            "PASS_PORTABLE_THREE_STATE_NATIVE_COPY_AND_PHYSICAL_RELOCATION_COLD_REOPEN",
            "Parent portable package is not accepted")
    package = Path(portable["package"])
    require(len(portable["package_files"]) == 513 and sum(Path(row['file']).suffix.upper() in ('.SLDPRT', '.SLDASM') for row in portable['package_files']) == 511, "Parent portable inventory differs: 511 native plus README and receipt")
    for row in portable["package_files"]:
        same_file(package / row["file"], row["sha256"])
    same_file(portable["archive"]["path"], portable["archive"]["sha256"])
    portable_inputs_path = RESULTS / "PORTABLE_INPUTS.json"
    pi = read(portable_inputs_path)
    for path, digest in pi["input_sha256"].items():
        same_file(path, digest)
    for row in pi["parts"]:
        same_file(row["source"], row["source_sha256"])
    for state in STATES:
        s = inputs["states"][state]
        same_file(s["parent_path"], s["parent_sha256"])
    manifest = N / "results/OUTPUT_SHA256.csv"
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        n_rows = list(csv.DictReader(stream))
    require(n_rows, "Empty sealed parent output manifest")
    for row in n_rows:
        path = (N / row["path"]).resolve()
        require(path.is_relative_to(N.resolve()), "Parent manifest path escapes parent root")
        same_file(path, row["sha256"])
        require(path.stat().st_size == int(row["bytes"]), f"Parent size changed: {path}")
    return {
        "status": "PASS_RECHECKED_PARENT_AND_PORTABLE_HASHES",
        "sealed_parent_output_count": len(n_rows), "sealed_parent_manifest": record(manifest),
        "parent_portable_files_unchanged": len(portable['package_files']), "parent_portable_native_files_unchanged": 511, "parent_source_parts_unchanged": len(pi["parts"]),
        "portable_receipt": record(portable_path), "portable_inputs": record(portable_inputs_path),
        "parent_archive_unchanged": record(portable["archive"]["path"]),
    }


def memory_receipts():
    runs = []
    required = {("integrate", state) for state in STATES} | {
        ("cold", state) for state in STATES} | {("cold", "relocated_" + state) for state in STATES}
    accepted = {}
    for path in sorted((C / "logs").glob("native_delta_*.run.json")):
        j = read(path)
        samples = j.get("samples", [])
        values = [finite_number(s["combined_rss_mib"], "combined RSS")
                  for s in samples if "combined_rss_mib" in s]
        command = j.get("command", [])
        mode_tag = None
        for i, arg in enumerate(command):
            if Path(arg).name == 'native_delta_view.py' and len(command) > i + 1:
                mode_tag = ('view', command[i + 1])
                break
            if Path(arg).name in ("native_delta_driver.py", "native_delta_hierarchy.py") and len(command) > i + 2:
                mode_tag = (command[i + 1], command[i + 2])
                break
        item = {
            "receipt": record(path), "status": j.get("status"),
            "returncode": j.get("returncode"), "mode_tag": mode_tag,
            "peak_combined_rss_mib": max(values) if values else None,
            "available_start_mib": j.get("available_start_mib"),
            "minimum_sampled_available_mib": min(s["available_mib"] for s in samples)
                                             if samples else None,
        }
        runs.append(item)
        if mode_tag in required and j.get("status") == "COMPLETED" and j.get("returncode") == 0:
            require(values and max(values) <= 1400, f"Missing/exceeded combined RAM guard: {path}")
            require(j["available_start_mib"] >= 2048
                    and all(s["available_mib"] >= 512 for s in samples),
                    f"Startup/runtime memory floor unmet: {path}")
            accepted[mode_tag] = item
    require(set(accepted) == required, f"Missing completed CAD run guards: {required - set(accepted)}")
    group_receipt_names = set()
    for state in STATES:
        integration = read(RESULTS / f'NATIVE_DELTA_INTEGRATE_{state}.json')
        group_receipt_names.update(Path(g['save_receipt']).name for g in integration['group_hash_seal'])
    group_guards = []
    for group_receipt_name in sorted(group_receipt_names):
        tag = group_receipt_name.removeprefix('NATIVE_DELTA_GROUPS_').removesuffix('.json')
        candidates = [x for x in runs if x['mode_tag'] == ('groups', tag) and x['status'] == 'COMPLETED' and x['returncode'] == 0]
        require(candidates, f'Missing completed group guard: {tag}')
        item = candidates[-1]
        require(item['peak_combined_rss_mib'] <= 1400 and item['available_start_mib'] >= 2048 and item['minimum_sampled_available_mib'] >= 512, 'Group guard limit failure')
        group_guards.append(item)
    peaks = [x["peak_combined_rss_mib"] for x in runs if x["peak_combined_rss_mib"] is not None]
    return {
        "combined_python_tree_and_owned_solidworks_rss_limit_mib": 1400,
        "startup_available_floor_mib": 2048, "runtime_available_floor_mib": 512,
        "peak_combined_rss_mib_all_recorded_attempts": max(peaks),
        "peak_combined_rss_mib_accepted_assembly_operations": max(
            x["peak_combined_rss_mib"] for x in accepted.values()),
        "accepted_assembly_operation_count": len(accepted), "runs": runs,
        "accepted_group_batch_guards": group_guards,
        "historical_failed_or_incomplete_runs_are_not_assembly_acceptance": True,
    }


def write_new_or_identical(path, data):
    if path.exists():
        require(path.read_bytes() == data, f"Refusing to overwrite different existing artifact: {path}")
    else:
        with path.open("xb") as stream:
            stream.write(data)


def main():
    index = RESULTS / "NATIVE_DELTA_DELIVERY.json"
    require(not index.exists(), "Delivery already sealed; preserve the existing index")
    require(D.is_dir() and not (C / "d").exists(), "CAD relocation must be finished before packaging")
    input_path = RESULTS / "NATIVE_DELTA_INPUTS.json"
    inputs, input_hash = read(input_path), sha(input_path)
    require(inputs["component_count"] == 873 and inputs["expected_solids"] == 1254,
            "Unexpected native delta input counts")
    require(inputs["whole_cic_package_geometry_known"] is False
            and inputs["manufacturing_release"] is False
            and inputs["continuous_mechanism_verified"] is False,
            "Input scope contradicts bounded native delivery")
    parts, part_proof, frame_proof = validate_parts(inputs, input_hash)
    snapshot_path = RESULTS / "NATIVE_DELTA_IMPORTED_PARTS.json"
    snapshot = read(snapshot_path)
    require(snapshot["status"] == "PASS_138_IMPORTED_PARTS_HASH_SNAPSHOT_SEALED"
            and snapshot["input_manifest_sha256"] == input_hash
            and snapshot["part_count"] == 138,
            "Imported-part sealed snapshot missing or invalid")
    sealed = unique_by(snapshot["parts"], "id", "sealed imported part IDs")
    require(set(sealed) == set(parts), "Sealed/imported part membership differs")
    for proof in part_proof:
        row = sealed[proof["id"]]
        require(row["native_sha256"] == proof["native"]["sha256"]
                and row["source_sha256"] == proof["source"]["sha256"],
                "Sealed part differs from original completed import receipt")
        same_file(row["native_path"], row["native_sha256"])
        same_file(row["import_receipt"], row["import_receipt_sha256"])
    # Assign expected new-part hashes from the sealed original save receipts,
    # never from freshly hashed current assembly dependencies.
    for state in STATES:
        for row in inputs["states"][state]["rows"]:
            if row.get("native_delta_part_id"):
                row["native_sha256"] = sealed[row["native_delta_part_id"]]["native_sha256"]
    parent_proof = validate_parents(inputs)
    archives, cold_proof, assembly_paths, views, all_dependencies = {}, [], {}, [], set()
    optional_view_status = {}
    rebuild_states = {}
    for state in STATES:
        s = inputs["states"][state]
        target = D / f"WP09D_{state.upper()}.SLDASM"
        require(norm(target) == norm(s["target_path"]), "Unexpected assembly filename")
        integration_path = RESULTS / f"NATIVE_DELTA_INTEGRATE_{state}.json"
        integration = read(integration_path)
        require(integration["status"] == INTEGRATE_STATUS
                and integration["input_manifest_sha256"] == input_hash
                and integration["imported_parts_snapshot_sha256"] == sha(snapshot_path)
                and integration["state"] == state and integration["mode"] == "integrate"
                and integration["component_count"] == 873 and integration["expected_solids"] == 1254
                and integration["open_documents_after"] == [],
                f"Integration not completed: {state}")
        require(norm(integration["native_save"]["path"]) == norm(target)
                and integration["native_save"]["ok"] is True
                and integration["native_save"]["errors"] == 0,
                f"Native assembly save failed: {state}")
        same_file(target, integration["native_save"]["sha256"])
        cold_path = RESULTS / f"NATIVE_DELTA_COLD_{state}.json"
        cold, deps, proof = validate_cold(cold_path, state, s["rows"], target, input_hash)
        rebuild_states[state] = {"pre_save": integration.get("pre_save_state"),
                                 "post_save": integration.get("post_save_state"),
                                 "cold": cold.get("cold_state_before_optional_view"),
                                 "explicit_force_rebuild_executed": False}
        proof["integration_receipt"] = record(integration_path)
        cold_proof.append(proof)
        all_dependencies.update(deps)
        assembly_paths[state] = str(target)
        archives[target.name] = target
        view_receipt_path = RESULTS / f'NATIVE_DELTA_VIEW_{state}.json'
        if not view_receipt_path.exists():
            optional_view_status[state] = {'status':'NOT_CAPTURED','does_not_change_native_cold_credit':True}
            continue
        view_receipt = read(view_receipt_path)
        if view_receipt['status'] != 'PASS_ACTUAL_NATIVE_LARGE_DESIGN_REVIEW_IMAGE':
            optional_view_status[state] = {'status':view_receipt['status'],'receipt':record(view_receipt_path),'does_not_change_native_cold_credit':True}
            continue
        require(view_receipt['status'] == 'PASS_ACTUAL_NATIVE_LARGE_DESIGN_REVIEW_IMAGE' and view_receipt['open_documents_after'] == [] and view_receipt['is_view_only'] is True, 'View-only native capture not passed')
        require(norm(view_receipt['cold_receipt']) == norm(cold_path) and view_receipt['cold_receipt_sha256'] == sha(cold_path), 'Independent view not bound to actual cold read')
        capture = view_receipt["native_view_capture"]
        proof['independent_view_receipt'] = record(view_receipt_path)
        require(capture.get("native_sha256") == integration["native_save"]["sha256"],
                f"Viewport not bound to saved native assembly: {state}")
        bmp = D / f"WP09D_{state.upper()}.bmp"
        require(capture["api_ok"] is True and norm(capture["path"]) == norm(bmp),
                f"No actual native viewport capture: {state}")
        require(bmp.is_file(), f"Missing native BMP: {state}")
        same_file(bmp, capture["sha256"])
        image_review_path = RESULTS / f'NATIVE_DELTA_VIEW_REVIEW_{state}.json'
        require(image_review_path.exists(), 'API success requires separate actual image inspection before model view credit')
        image_review = read(image_review_path)
        require(image_review['source_api_receipt_sha256'] == sha(view_receipt_path) and image_review['image_sha256'] == sha(bmp), 'Actual image inspection not bound to viewport file')
        if image_review['accepted_as_model_view'] is not True:
            optional_view_status[state] = {'status':image_review['status'],'api_receipt':record(view_receipt_path),'image_review_receipt':record(image_review_path),'does_not_change_native_cold_credit':True}
            continue
        optional_view_status[state] = {'status':'PASS_ACTUAL_NATIVE_LARGE_DESIGN_REVIEW_IMAGE','receipt':record(view_receipt_path)}
        views.append((state, bmp))
    relocated_proofs = []
    for state in STATES:
        relocated_path = RESULTS / f"NATIVE_DELTA_COLD_relocated_{state}.json"
        _, relocated_deps, relocated_proof = validate_cold(
            relocated_path, state, inputs["states"][state]["rows"],
            Path(assembly_paths[state]), input_hash, relocated=True)
        group_names = {Path(g['path']).name for g in read(RESULTS/f'NATIVE_DELTA_INTEGRATE_{state}.json')['group_hash_seal']}
        require(relocated_deps == {Path(row["native_path"]).name for row in inputs["states"][state]["rows"]} | group_names, "Relocation dependency membership changed")
        relocated_proofs.append(relocated_proof)
    relocated_proof = relocated_proofs[0]
    move_path = RESULTS / 'NATIVE_DELTA_RELOCATION.json'
    move = read(move_path)
    require(move['status'] == 'PASS_PHYSICAL_MOVE_COLD_READ_RETURN_ALL_BYTES_UNCHANGED', 'Physical move and return not completed')
    require(norm(move['original_root']) == norm(D) and norm(move['moved_root']) == norm(C / 'd'), 'Physical relocation roots differ')
    require([e['direction'] for e in move['events']] == ['forward', 'return'], 'Physical relocation event sequence differs')
    require(all(e['source_absent'] is True and e['all_files_byte_unchanged'] is True for e in move['events']), 'Move byte-preservation or source absence not recorded')
    for relative, digest in move['file_sha256_before'].items():
        path = (D / relative).resolve()
        require(path.is_relative_to(D.resolve()), 'Relocation manifest escapes CAD root')
        same_file(path, digest)
    require(len(move['file_sha256_before']) == move['events'][0]['file_count'] == move['events'][1]['file_count'], 'Relocation file count differs')
    memory = memory_receipts()
    for name in sorted(all_dependencies):
        path = D / name
        require(path.suffix.upper() in (".SLDPRT", ".SLDASM") and not name.startswith("D000_probe"),
                "Invalid native dependency in ZIP whitelist")
        archives[name] = path
    require({Path(p["native_path"]).name for p in parts.values()} <= all_dependencies,
            "A new validated native part is absent from all delivered assemblies")

    # All evidence gates above must pass before writing PNGs, README or archive.
    # BMP -> PNG is lossless and preserves the actual SolidWorks viewport pixels.
    from PIL import Image
    png_proof = []
    for state, bmp in views:
        png = bmp.with_suffix(".png")
        with Image.open(bmp) as source:
            source.load()
            require(source.size == (1600, 1200), f"Unexpected native viewport dimensions: {bmp}")
            rgb = source.convert("RGB")
            if not png.exists():
                rgb.save(png, "PNG")
            with Image.open(png) as converted:
                require(converted.size == rgb.size
                        and converted.convert("RGB").tobytes() == rgb.tobytes(),
                        f"PNG differs from actual BMP pixels: {png}")
            png_proof.append({"state": state, "source_bmp": record(bmp), "png": record(png),
                              "size_pixels": list(rgb.size), "lossless_pixel_equality": True})
        archives[png.name] = png
    readme = D / "README.md"
    readme_text = (
        "# WP09D 原生 SolidWorks 三态装配候选\n\n"
        "打开 WP09D_SERVICE.SLDASM、WP09D_PARKING.SLDASM 或 WP09D_RELEASED.SLDASM。"
        "将 ZIP 全部文件解压到同一个短目录；零件不可分开移动。建议完整路径少于 250 个字符。\n\n"
        "每态顶层 10 个固定子装配容器、递归 873 个叶部件；容器不重复计入叶部件。1254 个实体为当前装配成员结合零件证据的 SHA 绑定计数。"
        "138 个本轮原生零件逐一冷读实体/包围盒/体积；其中 8 个边框另通过同内核往返几何等价校核，"
        "保留 SolidWorks 标量体积差异。其他零件继承母版 SHA 证据，未重测全部 1254 个实体。\n\n"
        "三态已冷启动读取组件 ID、变换和本地依赖；三态另在原目录缺席时移至另一短目录逐态冷读，"
        "并将文件原样返回。冷读在隐藏文档会话内完成；如提供 PNG，则来自独立 SolidWorks Large Design Review 会话的实际视口 BMP 无损转换，图像不承担几何验证。可选图像失败不取消实际保存/冷读证据。\n\n"
        "保存使用每组最多 96 叶的两级固定子装配和 AvoidRebuildOnSave；子装配父变换全部为 identity，叶部件保留原 native T，并冷读核验完整父链。未执行强制全量特征重建。"
        "保存前后及冷读的实际 NeedsRebuild2/SaveFlag 记录于项目结果目录 results/NATIVE_DELTA_DELIVERY.json 的 rebuild_state_each。\n\n"
        "本包为固定姿态的结构候选，不具有连续运动、制造或飞行放行结论。"
        "太阳电池层仅表示玻璃占位投影；完整 CIC 引出片/互连包络未知。"
        "机电功能、全机构连续间隙及实物装配验证仍须按项目总体状态验收。\n"
    ).encode("utf-8")
    write_new_or_identical(readme, readme_text)
    archives[readme.name] = readme
    allowed_extensions = {".SLDASM", ".SLDPRT", ".PNG", ".MD"}
    require(all(Path(name).suffix.upper() in allowed_extensions for name in archives),
            "Non-delivery extension in archive whitelist")
    all_group_names = {Path(g['path']).name for s in STATES for g in read(RESULTS/f'NATIVE_DELTA_INTEGRATE_{s}.json')['group_hash_seal']}
    require({name for name in archives if name.upper().endswith(".SLDASM")} ==
            {f"WP09D_{s.upper()}.SLDASM" for s in STATES} | all_group_names, "Archive includes history assembly or misses group dependency")
    require({name for name in archives if Path(name).suffix.upper() in ('.SLDPRT', '.SLDASM')} <= set(move['file_sha256_before']), 'A packaged native file is absent from actual physical relocation manifest')
    require(len(archives) == len(all_dependencies) + 4 + len(views), "Unexpected archive inventory")
    file_proof = [{"file": name, "sha256": sha(path), "bytes": path.stat().st_size}
                  for name, path in sorted(archives.items())]
    archive = C / "mechanical/WP09D_NATIVE_873.zip"
    require(archive.parent.is_dir(), "Mechanical delivery folder missing")
    require(not archive.exists(), "Refusing to overwrite existing native delivery archive")
    temporary = archive.with_suffix(".zip.partial")
    require(not temporary.exists(), "Prior partial ZIP preserved; resolve it before retry")
    with ZipFile(temporary, "x", compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for name, path in sorted(archives.items()):
            z.write(path, arcname=name)
    with ZipFile(temporary) as z:
        require(z.testzip() is None, "ZIP CRC verification failed")
        require(set(z.namelist()) == set(archives) and len(z.namelist()) == len(archives),
                "ZIP inventory or duplicate entries mismatch")
        for row in file_proof:
            with z.open(row["file"]) as stream:
                require(hashlib.file_digest(stream, "sha256").hexdigest() == row["sha256"],
                        f"ZIP content hash mismatch: {row['file']}")
    # Recheck files and immutable parents after compression before publishing.
    for row in file_proof:
        same_file(archives[row["file"]], row["sha256"])
    validate_parents(inputs)
    same_file(input_path, input_hash)
    temporary.rename(archive)
    delivery = {
        "status": "PASS_873_FIXED_POSE_NATIVE_DELTA_AND_PHYSICAL_RELOCATION_DELIVERY",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "package_dir": str(D), "package_directory_contains_preserved_work_history": True,
        "archive_uses_verified_dependency_whitelist_only": True,
        "assembly_paths": assembly_paths, "component_count_each": 873,
        "component_count_semantics": "LEAF_PART_INSTANCES_EXCLUDING_SUBASSEMBLY_CONTAINERS",
        "top_level_container_count_each": 10, "hierarchy_depth": 2,
        "unique_fixed_subassembly_files_in_archive": len(all_group_names),
        "hierarchy_input": record(RESULTS/'NATIVE_DELTA_HIERARCHY_INPUTS.json'),
        "rebuild_state_each": rebuild_states,
        "expected_solids_each": 1254, "expected_solids_each_are_hash_bound": True,
        "unique_native_part_files_in_archive": sum(Path(n).suffix.upper()=='.SLDPRT' for n in all_dependencies),
        "new_unique_native_parts_individually_cold_read": 138,
        "actual_all_1254_body_readback": False,
        "body_credit": "138 unique new native files individually cold measured for solid count, bounds and volume; "
                       "8 frame scalar discrepancies separately resolved by same-kernel native-roundtrip geometry equivalence. "
                       "Retained native geometry inherits exact parent SHA evidence. All 873 current IDs, transforms and "
                       "local dependencies per state were read back. This is not a reread of all 1254 bodies.",
        "input_manifest": record(input_path), "imported_parts_snapshot": record(snapshot_path),
        "part_cold_proofs": part_proof,
        "frame_equivalence": frame_proof, "cold_receipts": cold_proof,
        "relocation": relocated_proof, "relocation_cold_receipts_each": relocated_proofs,
        "physical_move_return_receipt": record(move_path),
        "actual_relocated_cold_state_count": len(relocated_proofs), "parent_hash_preservation": parent_proof,
        "memory": memory, "png_paths": [p["png"]["path"] for p in png_proof],
        "optional_native_view_status_each": optional_view_status,
        "native_view_evidence": png_proof, "archive": record(archive),
        "archive_crc_verified": True, "archive_entry_sha256_verified": True,
        "archive_file_count": len(file_proof), "package_files": file_proof,
        "continuous_motion_verified": False, "mate_based_motion": False,
        "manufacturing_release": False, "flight_release": False,
        "whole_mechatronic_detailed_design_complete": False,
        "cic_role": "GLASS_FOOTPRINT_CIC_LAYER_PROXY",
        "whole_cic_package_geometry_known": False,
    }
    write_new_or_identical(index, (json.dumps(delivery, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"status": delivery["status"], "index": str(index),
                      "archive": delivery["archive"], "file_count": len(file_proof)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
