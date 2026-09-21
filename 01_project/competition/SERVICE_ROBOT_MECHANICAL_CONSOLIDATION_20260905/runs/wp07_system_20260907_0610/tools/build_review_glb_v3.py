"""Replace WP07 V1's legacy arm STL display with hash-bound WP01 BRep caches.

Root runs serially. No CAD/COM or tessellation. V1 failure remains immutable.
587 non-arm instance nodes and the complete V1 BIN prefix are preserved.
10 arm instance parents receive 391 body children from their exact source STEP
scene hierarchy. Mesh measurements are display checks, never BRep certification.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import mmap
from pathlib import Path
import struct
import sys

import numpy as np

RUN = Path(__file__).resolve().parents[1]
ROOT = next(p for p in RUN.parents if (p / "PROJECT_MAP.md").is_file())
W1 = ROOT / "20_engineering/service_robot_wp01_20260905"
OUT = RUN / "viewer"
LEGACY_SCRIPT = RUN / "tools/build_review_glb.py"
LEGACY_SHA = "416cf08ab4de8c02105d163bd949357c1116eabd61750a3b9092f651b80bc486"
V1_GLB = OUT / "WP07_SERVICE_REVIEW.glb"
V1_REPORT = OUT / "REVIEW_GLB_RESULT.json"
V1_ARCHIVE = OUT / "history/V1_FAILED_DISPLAY_BOUNDS/ARCHIVE_RECEIPT.json"
MANIFEST = RUN / "results/INTEGRATION_MANIFEST.json"
SOURCE_MAP = RUN / "inputs/REVIEW_GLB_ARM_SOURCE_MAP.json"
TOL_MM = 2.0
TRANSFORM_TOL = 1e-7  # Strictly bounds cached transform replay (translation mm).
SCOPE = ("Display tessellation only, all arm meshes from the exact source STEP "
         "hashes used by the native assembly. 587 non-arm V1 nodes are unchanged; "
         "10 source-bound arm parents contain 391 body meshes. The inherited <2 mm "
         "screen checks display scale/placement, not BRep identity, collision "
         "clearance, physical assembly, strength, threads or manufacturing release. "
         "V1's seven STL-versus-STEP failures remain preserved historical evidence.")


def load_helpers():
    digest = hashlib.sha256(LEGACY_SCRIPT.read_bytes()).hexdigest()
    if digest != LEGACY_SHA:
        raise ValueError("V1 helper script changed; review new version before use")
    spec = importlib.util.spec_from_file_location("wp07_review_v1_frozen_helpers", LEGACY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=["service"], default="service")
    parser.parse_args()
    helper = load_helpers()
    require, read, sha = helper.require, helper.read, helper.sha
    target = OUT / "WP07_SERVICE_BREP_REVIEW_V3.glb"
    receipt = OUT / "REVIEW_GLB_V3_RESULT.json"
    snapshot_path = OUT / "REVIEW_GLB_V3_INPUT_SNAPSHOT.json"
    for path in (target, receipt, snapshot_path):
        require(not path.exists(), "Refuse overwrite: " + str(path))
    report = dict(schema="WP07_SOURCE_BREP_CACHE_DISPLAY_V3", status="RUNNING",
        started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), state="service", scope=SCOPE,
        source_sha256={}, physical_assembly_completed=False, manufacturing_release=False,
        collision_verified=False, exact_brep_equivalence_claimed=False)
    inputs = report["source_sha256"]
    def bind(path, expected=None):
        path = Path(path).resolve(); digest = sha(path)
        require(expected is None or digest.lower() == expected.lower(), "SHA mismatch: " + str(path))
        require(str(path) not in inputs or inputs[str(path)] == digest, "Source changed: " + str(path))
        inputs[str(path)] = digest
        return digest
    def save():
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    save()
    try:
        bind(__file__); bind(LEGACY_SCRIPT, LEGACY_SHA); bind(SOURCE_MAP); source_map = read(SOURCE_MAP)
        bind(V1_REPORT); prior = read(V1_REPORT)
        require(prior["status"] == "FAIL_DISPLAY_BOUNDS" and prior["failed_bounds_count"] == 7,
                "Unexpected V1 outcome")
        v1_hash = bind(V1_GLB, prior["output"]["sha256"])
        bind(V1_ARCHIVE); archive = read(V1_ARCHIVE)
        require(archive["status"] == "PRESERVED_BYTE_IDENTICAL", "V1 failure archive missing")
        for item in archive["files"]:
            bind(item["archived_path"], item["sha256"])
        bind(MANIFEST); manifest = read(MANIFEST)
        rows = manifest["states"]["service"]["instances"]
        expected = {r["id"]: r for r in rows}
        arms = {r["id"]: r for r in rows if r.get("arm_link")}
        require(len(rows) == len(expected) == 597 and len(arms) == 10, "Integration identity/count mismatch")
        failed_v1 = [r for r in prior["world_bbox_checks"] if r["status"] != "PASS_DISPLAY_BOUNDS"]
        require(len(failed_v1) == 7 and all(r["id"] in arms for r in failed_v1), "V1 failure scope changed")
        nonarms = set(expected) - set(arms)
        require(len(nonarms) == 587 and all(r["status"] == "PASS_DISPLAY_BOUNDS"
                for r in prior["world_bbox_checks"] if r["id"] in nonarms), "V1 nonarm bounds not all PASS")
        cache_path = Path(source_map["assembly_cache"]["path"])
        bind(cache_path, source_map["assembly_cache"]["sha256"]); cache = read(cache_path)
        require(cache["units"] == "mm", "WP01 occurrence units differ")
        bind(source_map["assembly_step"]["path"], cache["stepHash"])
        old_receipt_path = Path(source_map["old_build_receipt"]["path"])
        bind(old_receipt_path, source_map["old_build_receipt"]["sha256"]); old_receipt = read(old_receipt_path)
        source_inputs_path = Path(source_map["source_inputs"]["path"])
        bind(source_inputs_path, source_map["source_inputs"]["sha256"])
        original_sources = {r["name"]: r for r in read(source_inputs_path)}
        groups = {}
        def find_groups(node):
            if node.get("name") in arms:
                require(node["name"] not in groups, "Duplicate arm group")
                groups[node["name"]] = node
            for child in node.get("children", []): find_groups(child)
        find_groups(cache["assembly"]["root"])
        require(set(groups) == set(arms), "Missing WP01 arm groups")
        occurrences = {r["id"]: r for r in cache["occurrences"]}
        require(len(occurrences) == len(cache["occurrences"]), "Duplicate cache occurrences")
        model, prefix_offset, prefix_length = helper.glb_header(V1_GLB)
        old_ids = helper.instance_map(model)
        require(set(old_ids) == set(expected), "V1 GLB/manifest instance mismatch")
        preserved = {name: copy.deepcopy(model["nodes"][old_ids[name]]) for name in nonarms}
        require(all(not any(k in n for k in ("matrix", "translation", "rotation", "scale"))
                    for n in model["nodes"] if "children" in n), "Transformed V1 parent group")
        segments, component_meshes, arm_bindings = [], {}, []
        binary_length = prefix_length
        all_body_paths = set()
        source_body_total = 0
        for instance in sorted(arms):
            row = arms[instance]; link = row["arm_link"]; info = source_map["links"][link]
            require(info["instance_id"] == instance and info["expected_solids"] == row["expected_solids"],
                    "Arm source map identity/count differs")
            source = row["source_step"]
            bind(source["path"], source["sha256"])
            require(source["sha256"] == info["source_step_sha256"] == original_sources[link]["sha256"],
                    "Arm source STEP hash differs")
            bind(W1 / original_sources[link]["copy"], source["sha256"])
            scene_path = Path(info["source_scene"]["path"])
            bind(scene_path, info["source_scene"]["sha256"]); scene = read(scene_path)
            require(scene["stepHash"] == source["sha256"], "Scene is not exact source STEP hash")
            leaves = {}
            def walk(node):
                if node.get("prototypeKey") is not None:
                    path = ".".join(map(str, node["path"][1:]))
                    require(path not in leaves, "Duplicate source scene leaf path")
                    leaves[path] = node
                for child in node.get("children", []): walk(child)
            for root in scene["roots"]: walk(root)
            group = groups[instance]
            require(len(group["leafPartIds"]) == len(leaves) == row["expected_solids"],
                    "Source/cache/native solid count mismatch: " + instance)
            require(group["id"] == info["cache_group_id"], "Cache group identity changed")
            prototypes = {r["key"]: r for r in scene["prototypes"]}
            # Bind original BRep prototype files too; they are not loaded by a kernel.
            for key in {n["prototypeKey"] for n in leaves.values()}:
                bind(scene_path.parent / prototypes[key]["file"])
            parent_index = old_ids[instance]
            parent = model["nodes"][parent_index]
            parent.pop("mesh", None)
            parent["matrix"] = helper.gltf_matrix(row["T_S_local"])
            parent["children"] = []
            parent["extras"] = dict(instance_id=instance, representation_role=row["representation_role"],
                display_geometry_basis="HASH_BOUND_SOURCE_STEP_BREP_TESSELLATION",
                source_step_sha256=source["sha256"], arm_link=link, source_body_count=row["expected_solids"],
                qualification_status="NOT_EVALUATED", mesh_bbox_tolerance_mm=TOL_MM)
            old_link = np.asarray(old_receipt["link_transforms"][link], dtype=float)
            max_error = 0.0; body_records = []
            for oid in group["leafPartIds"]:
                require(oid not in all_body_paths, "Body reused across arm groups")
                all_body_paths.add(oid)
                suffix = oid[len(group["id"]) + 1:]
                require(oid.startswith(group["id"] + ".") and suffix in leaves,
                        "No exact source leaf path: " + oid)
                leaf = leaves[suffix]; occurrence = occurrences[oid]
                intrinsic = np.asarray(leaf["transform"], dtype=float).reshape(4, 4)
                actual_old = np.asarray(occurrence["transform"], dtype=float).reshape(4, 4)
                error = float(np.max(np.abs(actual_old - old_link @ intrinsic)))
                require(error <= TRANSFORM_TOL, "Old cache/source transform replay differs: " + oid)
                max_error = max(max_error, error)
                cid = occurrence["component"]
                if cid not in component_meshes:
                    file = (cache_path.parent / cache["components"][cid]["glb"]).resolve()
                    require(file.is_relative_to(cache_path.parent.resolve()), "Component escapes cache")
                    digest = bind(file); data, offset, length = helper.glb_header(file)
                    require(len(data.get("nodes", [])) == len(data.get("meshes", [])) == 1,
                            "Expected single body component GLB")
                    require(not any(data.get(k) for k in ("images", "skins", "animations")), "Complex component GLB")
                    require(not any(k in data["nodes"][0] for k in ("matrix", "translation", "rotation", "scale")),
                            "Unexpected extra component transform")
                    padding = (-binary_length) % 4; binary_length += padding
                    base = binary_length; vo = len(model["bufferViews"]); ao = len(model["accessors"])
                    for view in data["bufferViews"]:
                        v = copy.deepcopy(view); require(v.get("buffer", 0) == 0, "Component buffer differs")
                        v["buffer"] = 0; v["byteOffset"] = base + v.get("byteOffset", 0)
                        model["bufferViews"].append(v)
                    for accessor in data["accessors"]:
                        a = copy.deepcopy(accessor)
                        require("sparse" not in a and "bufferView" in a, "Unsupported body accessor")
                        a["bufferView"] += vo; model["accessors"].append(a)
                    mesh = copy.deepcopy(data["meshes"][0]); mesh.pop("extensions", None)
                    for primitive in mesh["primitives"]:
                        primitive["attributes"] = {k: v + ao for k, v in primitive["attributes"].items()}
                        if "indices" in primitive: primitive["indices"] += ao
                        primitive.pop("material", None); primitive.pop("extensions", None)
                        require("targets" not in primitive, "Morph body unsupported")
                    component_meshes[cid] = (mesh, digest, str(file))
                    segments.append((file, offset, length, padding))
                    binary_length += length
                prototype, digest, file = component_meshes[cid]
                mesh = copy.deepcopy(prototype); mesh["name"] = instance + "__" + oid
                material = len(model["materials"])
                model["materials"].append(dict(name=instance + "_source_body",
                    pbrMetallicRoughness=dict(baseColorFactor=occurrence.get("color") or [.65, .67, .7, 1],
                                             metallicFactor=.4, roughnessFactor=.48), doubleSided=True))
                for primitive in mesh["primitives"]: primitive["material"] = material
                child = dict(name=instance + "__body_" + suffix, mesh=len(model["meshes"]),
                    matrix=helper.gltf_matrix(intrinsic), extras=dict(body_occurrence_id=oid,
                    parent_instance_id=instance, source_step_sha256=source["sha256"],
                    source_scene_path=leaf["path"], source_prototype_key=leaf["prototypeKey"],
                    component_glb_sha256=digest, representation="DISPLAY_BREP_TRIANGLES"))
                model["meshes"].append(mesh)
                parent["children"].append(len(model["nodes"])); model["nodes"].append(child)
                body_records.append(dict(body_occurrence_id=oid, source_scene_path=leaf["path"],
                    source_prototype_key=leaf["prototypeKey"], component=cid, glb_path=file, glb_sha256=digest,
                    source_local_transform_mm=leaf["transform"], old_cache_world_transform_mm=occurrence["transform"],
                    replay_max_abs_difference=error))
            require({oid[len(group["id"]) + 1:] for oid in group["leafPartIds"]} == set(leaves),
                    "Source body coverage incomplete")
            source_body_total += len(body_records)
            arm_bindings.append(dict(instance_id=instance, source_step=source, source_scene=str(scene_path),
                old_link_transform_mm=old_receipt["link_transforms"][link], new_link_transform_mm=row["T_S_local"],
                body_count=len(body_records), transform_replay_max_abs_difference=max_error, bodies=body_records))
        require(source_body_total == len(all_body_paths) == 391, "Expected all 391 arm source bodies")
        model["asset"]["generator"] = "WP07 V3 source-STEP-cache display compositor; no CAD kernel"
        model["scenes"][0]["name"] = "WP07 SERVICE BRep-source mesh review V3"
        model["nodes"][0]["name"] = "WP07_SERVICE_BREP_REVIEW_V3_DISPLAY_ONLY"
        model["nodes"][0]["extras"] = dict(scope=SCOPE, instance_count=597, arm_source_body_count=391,
            legacy_v1_status=prior["status"], legacy_v1_glb_sha256=v1_hash,
            integration_manifest_sha256=inputs[str(MANIFEST.resolve())], exact_brep_equivalence_claimed=False)
        model["buffers"] = [dict(byteLength=binary_length)]
        instance_ids = helper.instance_map(model)
        require(set(instance_ids) == set(expected), "Final 597 parent instance coverage differs")
        require(all(model["nodes"][instance_ids[name]] == preserved[name] for name in nonarms),
                "Nonarm node changed")
        require(set(instance_ids.values()) <= helper.reachable(model), "Unreachable instance")
        snapshot = dict(schema="WP07_BREP_CACHE_REVIEW_INPUT_V3", source_sha256=dict(inputs),
            scope=SCOPE, legacy_v1_failures=failed_v1, arm_bindings=arm_bindings,
            preserved_nonarm_ids=sorted(nonarms), preserved_v1_binary_prefix_bytes=prefix_length,
            transform_replay_tolerance=TRANSFORM_TOL, display_world_bbox_tolerance_mm=TOL_MM)
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        metadata = json.dumps(model, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        metadata += b" " * ((-len(metadata)) % 4); padding = (-binary_length) % 4
        with target.open("xb") as destination:
            destination.write(struct.pack("<4sII", b"glTF", 2, 28 + len(metadata) + binary_length + padding))
            destination.write(struct.pack("<I4s", len(metadata), b"JSON")); destination.write(metadata)
            destination.write(struct.pack("<I4s", binary_length + padding, b"BIN\0"))
            for file, offset, length, prefix in [(V1_GLB, prefix_offset, prefix_length, 0), *segments]:
                destination.write(b"\0" * prefix)
                with file.open("rb") as source:
                    source.seek(offset); remaining = length
                    while remaining:
                        block = source.read(min(1024 * 1024, remaining)); require(block, "Unexpected source BIN EOF")
                        destination.write(block); remaining -= len(block)
            destination.write(b"\0" * padding)
        reread, offset, _ = helper.glb_header(target)
        require(reread == model, "V3 JSON readback differs")
        ids = helper.instance_map(reread); require(len(ids) == 597, "V3 instance count differs")
        prefix_before, prefix_after = hashlib.sha256(), hashlib.sha256()
        with V1_GLB.open("rb") as a, target.open("rb") as b:
            a.seek(prefix_offset); b.seek(offset); remaining = prefix_length
            while remaining:
                size = min(remaining, 1024 * 1024)
                prefix_before.update(a.read(size)); prefix_after.update(b.read(size)); remaining -= size
        require(prefix_before.digest() == prefix_after.digest(), "V1 BIN prefix changed")
        measurements = []
        with target.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as binary:
            for name, i in sorted(ids.items()):
                parent = reread["nodes"][i]
                if name in arms:
                    parent_matrix = np.asarray(parent["matrix"]).reshape(4, 4).T
                    low, high, count = np.full(3, np.inf), np.full(3, -np.inf), 0
                    for child_index in parent["children"]:
                        child = reread["nodes"][child_index]
                        require(not child.get("children") and "mesh" in child, "Unexpected nested body node")
                        world = parent_matrix @ np.asarray(child["matrix"]).reshape(4, 4).T
                        probe = dict(mesh=child["mesh"], matrix=world.T.reshape(-1).tolist())
                        lo, hi, n = helper.mesh_world_bounds(reread, binary, offset, probe)
                        low = np.minimum(low, lo); high = np.maximum(high, hi); count += n
                    body_count = len(parent["children"])
                    require(body_count == expected[name]["expected_solids"], "Readback body count differs")
                else:
                    low, high, count = helper.mesh_world_bounds(reread, binary, offset, parent)
                    body_count = None
                ref = expected[name].get("world_bounds_mm", expected[name]["bounds_mm"])
                error = float(np.max(np.abs(np.asarray([low, high]) - np.asarray([ref["min_mm"], ref["max_mm"]]))))
                measurements.append(dict(id=name, status="PASS_DISPLAY_BOUNDS" if error < TOL_MM else "FAIL_DISPLAY_BOUNDS",
                    max_world_bbox_difference_mm=error, measured_mesh_bbox_mm=dict(min_mm=low.tolist(), max_mm=high.tolist()),
                    integration_bbox_mm=ref, position_values_measured=count, source_body_count=body_count,
                    geometry_basis="HASH_BOUND_BREP_CACHE" if name in arms else "V1_NONARM_UNCHANGED"))
        require(all(sha(p) == digest for p, digest in inputs.items()), "Source hash changed during V3 composition")
        failures = [r for r in measurements if r["status"] != "PASS_DISPLAY_BOUNDS"]
        report.update(status="PASS_DISPLAY_REVIEW_ONLY" if not failures else "FAIL_DISPLAY_BOUNDS",
            output=dict(path=str(target.resolve()), sha256=sha(target), bytes=target.stat().st_size),
            input_snapshot=dict(path=str(snapshot_path.resolve()), sha256=sha(snapshot_path)),
            instance_count=597, unchanged_nonarm_count=587, arm_instance_count=10, arm_body_count=391,
            appended_component_count=len(segments), appended_binary_bytes=binary_length-prefix_length,
            nonarm_nodes_identical=True, v1_bin_prefix_identical=True, source_hashes_unchanged=True,
            legacy_v1=dict(report=str(V1_REPORT), status=prior["status"], failed_bounds_count=7,
                           glb_sha256=v1_hash, failures=failed_v1, archive=str(V1_ARCHIVE)),
            mesh_bbox_tolerance_mm=TOL_MM, mesh_bbox_tolerance_kind="DISPLAY_ONLY_NOT_BREP_CLEARANCE",
            failed_bounds_count=len(failures), world_bbox_checks=measurements,
            arm_transform_bindings=[{k: v for k, v in x.items() if k != "bodies"} for x in arm_bindings],
            completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        save()
        print(json.dumps(dict(status=report["status"], output=str(target), failed_bounds_count=len(failures))))
        return 0 if not failures else 2
    except Exception as exc:
        report.update(status="INCOMPLETE", error_type=type(exc).__name__, error=str(exc),
                      completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        if target.exists(): report["partial_or_unverified_output"] = dict(path=str(target), sha256=sha(target))
        save(); print(json.dumps(dict(status="INCOMPLETE", error=str(exc))), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
