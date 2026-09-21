"""SERVICE display-only compositor: frozen WP04 BIN + identified WP06 meshes.

No CAD/COM/third-party generators. Root executes this file serially under guard.
Writes only new files in this run's viewer/. Does not edit a frozen cache.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
import sys

import numpy as np

RUN = Path(__file__).resolve().parents[1]
W4 = RUN.parent / "wp04_robot_assembly_20260906_175153"
W6 = RUN.parent / "wp06_side_joint_20260907_0233"
OUT = RUN / "viewer"
MANIFEST = RUN / "results/INTEGRATION_MANIFEST.json"
BRIEF = RUN / "inputs/REVIEW_GLB_INPUT_MAP.json"
OLD = W4 / "viewer/complete_service_robot.glb"
OLD_REPORT = W4 / "viewer/COMPLETE_GLB_EXPORT_RESULT.json"
OLD_SCENE = W4 / "viewer/scene.json"
W6_CACHE = W6 / "candidate/__cadgen__/models/wp06_side_joint.step/assembly.json"
LOCAL = W6 / "results/LOCAL_PARTS.json"
TOL_MM = 2.0  # W4/viewer/build_viewer.py existing display-only bound screen.
SCOPE = ("Display triangle meshes only. Frozen WP04 SERVICE geometry with the exact "
         "WP06 integration delta; 10 arms remain accepted URDF STL meshes. No new "
         "STEP/BRep validation, physical assembly, global collision, continuous "
         "motion, thread, strength or manufacturing-release credit.")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def glb_header(path):
    """Read JSON only; retain binary offset/length for streaming or mmap."""
    path = Path(path)
    with path.open("rb") as stream:
        magic, version, total = struct.unpack("<4sII", stream.read(12))
        require(magic == b"glTF" and version == 2 and total == path.stat().st_size,
                "Invalid GLB header: " + str(path))
        length, kind = struct.unpack("<I4s", stream.read(8))
        require(kind == b"JSON", "GLB first chunk is not JSON")
        model = json.loads(stream.read(length))
        binary_length, kind = struct.unpack("<I4s", stream.read(8))
        require(kind == b"BIN\0", "GLB needs one embedded BIN")
        offset = stream.tell()
        require(offset + binary_length == total, "Unexpected GLB chunks")
        require(len(model.get("buffers", [])) == 1 and
                "uri" not in model["buffers"][0], "External/multiple buffers unsupported")
        declared = model["buffers"][0]["byteLength"]
        require(0 <= binary_length - declared <= 3, "Invalid BIN padding")
    return model, offset, binary_length


def instance_map(model):
    pairs = [(n.get("extras", {}).get("instance_id"), i)
             for i, n in enumerate(model["nodes"])
             if n.get("extras", {}).get("instance_id")]
    require(len({x[0] for x in pairs}) == len(pairs), "Duplicate display instance IDs")
    return dict(pairs)


def gltf_matrix(row_major_mm):
    matrix = np.asarray(row_major_mm, dtype=float).reshape(4, 4).copy()
    require(np.isfinite(matrix).all(), "Nonfinite occurrence matrix")
    require(np.allclose(matrix[3], [0, 0, 0, 1], rtol=0, atol=1e-12),
            "Invalid homogeneous occurrence matrix")
    matrix[:3, 3] /= 1000.0
    return matrix.T.reshape(-1).tolist()


def reachable(model):
    result, active = set(), set()
    def visit(i):
        require(0 <= i < len(model["nodes"]), "Invalid node reference")
        require(i not in active, "Node cycle")
        if i in result:
            return
        active.add(i)
        for child in model["nodes"][i].get("children", []):
            visit(child)
        active.remove(i)
        result.add(i)
    for i in model["scenes"][model.get("scene", 0)]["nodes"]:
        visit(i)
    return result


def mesh_world_bounds(model, binary_map, binary_offset, node):
    """Read actual POSITION buffers in bounded chunks, never Python float lists."""
    transform = np.asarray(node["matrix"], dtype=float).reshape(4, 4).T
    low, high = np.full(3, np.inf), np.full(3, -np.inf)
    count = 0
    for primitive in model["meshes"][node["mesh"]]["primitives"]:
        accessor = model["accessors"][primitive["attributes"]["POSITION"]]
        require(accessor["componentType"] == 5126 and accessor["type"] == "VEC3"
                and "sparse" not in accessor, "Unsupported POSITION accessor")
        view = model["bufferViews"][accessor["bufferView"]]
        require(view.get("buffer", 0) == 0, "Nonembedded POSITION view")
        stride = view.get("byteStride", 12)
        n = accessor["count"]
        offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        end = offset + (n - 1) * stride + 12 if n else offset
        require(n > 0 and stride >= 12 and end <= model["buffers"][0]["byteLength"],
                "POSITION outside buffer")
        require(end <= view.get("byteOffset", 0) + view["byteLength"],
                "POSITION outside bufferView")
        vertices = np.ndarray((n, 3), dtype="<f4", buffer=binary_map,
                              offset=binary_offset + offset, strides=(stride, 4))
        for start in range(0, n, 32768):
            xyz = vertices[start:start + 32768].astype(np.float64)
            require(np.isfinite(xyz).all(), "Nonfinite vertex")
            world = xyz @ transform[:3, :3].T + transform[:3, 3]
            low = np.minimum(low, world.min(axis=0))
            high = np.maximum(high, world.max(axis=0))
            count += len(world)
            del xyz, world
        del vertices
    require(count > 0, "Instance has no vertices")
    return low * 1000, high * 1000, count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=["service"], default="service")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "WP07_SERVICE_REVIEW.glb"
    report_path = OUT / "REVIEW_GLB_RESULT.json"
    input_path = OUT / "REVIEW_GLB_INPUT_SNAPSHOT.json"
    for path in (target, report_path, input_path):
        require(not path.exists(), "Refuse overwrite: " + str(path))
    report = dict(schema="WP07_DISPLAY_MESH_REVIEW_V1", status="RUNNING",
                  started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), state=args.state,
                  scope=SCOPE, physical_assembly_completed=False,
                  manufacturing_release=False, global_collision_verified=False,
                  exact_brep_equivalence_claimed=False, source_sha256={}, checks=[])
    inputs = report["source_sha256"]
    def bind(path, expected=None):
        path = Path(path).resolve()
        digest = sha(path)
        require(expected is None or digest.lower() == expected.lower(),
                "Source hash mismatch: " + str(path))
        if str(path) in inputs:
            require(inputs[str(path)] == digest, "Source changed: " + str(path))
        inputs[str(path)] = digest
        return digest
    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                         allow_nan=False), encoding="utf-8")
    save()
    try:
        bind(__file__); bind(BRIEF)
        brief = read(BRIEF)
        old_receipt = read(OLD_REPORT); bind(OLD_REPORT)
        bind(OLD, old_receipt["output"]["sha256"])
        require(old_receipt["output"]["sha256"] == brief["baseline_glb_sha256"],
                "Unexpected frozen baseline GLB")
        old_snapshot = old_receipt["geometry_input_snapshot"]
        bind(old_snapshot["path"], old_snapshot["sha256"])
        bind(OLD_SCENE); scene = read(OLD_SCENE)
        require(scene["units"] == "metres" and scene["frame"] == "S; +Z up",
                "Unexpected viewer frame")
        old_rows = scene["states"]["service"]["occurrences"]
        require(len(old_rows) == 585 and len({r["id"] for r in old_rows}) == 585,
                "Expected 585 baseline scene instances")
        bind(MANIFEST); manifest = read(MANIFEST)
        require(manifest["units"] == "mm", "Integration units must be mm")
        rows = manifest["states"]["service"]["instances"]
        expected = {r["id"]: r for r in rows}
        require(len(rows) == len(expected) == 597, "Expected 597 integration instances")
        replaced, removed, added = (set(manifest[k]) for k in
                                   ("replaced_ids", "removed_ids", "added_ids"))
        require([len(replaced), len(removed), len(added)] == [8, 4, 16],
                "Unexpected integration delta")
        require(replaced == set(brief["replaced_ids"]) and removed == set(brief["removed_ids"])
                and added == set(brief["added_ids"]), "Delta differs from reviewed input map")
        require(not (replaced & removed or replaced & added or removed & added), "Delta sets overlap")
        bind(W6_CACHE, brief["wp06_cache_sha256"]); cache = read(W6_CACHE)
        require(cache["units"] == "mm", "WP06 occurrence units must be mm")
        bind(LOCAL); local = read(LOCAL)
        require(local["source_sha256"] == cache["stepHash"], "WP06 cache/part receipt source differs")
        bind(local["source_path"], cache["stepHash"])
        occurrences = {o["name"]: o for o in cache["occurrences"]}
        require(len(occurrences) == len(cache["occurrences"]) == 53, "WP06 cache identity ambiguity")
        require((replaced | added) <= set(occurrences), "Missing actual WP06 component mapping")
        for row in rows:
            ref = row["source_step"]
            bind(ref["path"], ref["sha256"])
        model, old_offset, old_bin_length = glb_header(OLD)
        require(not any(model.get(k) for k in ("skins", "animations", "images")),
                "Baseline has unsupported complex glTF features")
        old_ids = instance_map(model)
        require(len(old_ids) == 585 and set(old_ids) == {r["id"] for r in old_rows},
                "Baseline GLB/scene identity mismatch")
        require((set(old_ids) - removed) | added == set(expected), "597 identity equation failed")
        old_map = {r["id"]: r for r in old_rows}
        for name, i in old_ids.items():
            require(model["nodes"][i]["name"] == name, "Node name/instance mismatch")
            require(model["nodes"][i]["matrix"] == gltf_matrix(old_map[name]["matrix_mm"]),
                    "Baseline scene/GLB pose differs: " + name)
        retained = set(old_ids) - replaced - removed
        require(len(retained) == 573, "Expected 573 unchanged instances")
        original_nodes = {name: copy.deepcopy(model["nodes"][old_ids[name]]) for name in retained}
        # No parent transform may alter a per-instance matrix.
        group_indices = [i for i, n in enumerate(model["nodes"]) if "children" in n]
        require(all(not any(k in model["nodes"][i] for k in ("matrix", "translation", "rotation", "scale"))
                    for i in group_indices), "Transformed parent group unsupported")
        structure = [i for i in group_indices if model["nodes"][i].get("extras", {}).get("display_group") == "structure"]
        require(len(structure) == 1, "Missing structure display group")
        append_segments, appended_models, component_meshes = [], [], {}
        binary_size = old_bin_length
        mappings = []
        for name in sorted(replaced | added):
            row, occurrence = expected[name], occurrences[name]
            part = local["parts"][name]
            require(part["sha256"] == row["source_step"]["sha256"], "Local part identity differs: " + name)
            cid = occurrence["component"]
            if cid not in component_meshes:
                file = (W6_CACHE.parent / cache["components"][cid]["glb"]).resolve()
                require(file.is_relative_to(W6_CACHE.parent.resolve()), "Component path escaped cache")
                digest = bind(file)
                data, offset, length = glb_header(file)
                require(len(data.get("nodes", [])) == len(data.get("meshes", [])) == 1,
                        "Expected a single local component mesh")
                require(not any(data.get(k) for k in ("skins", "images", "animations")),
                        "Complex component glTF unsupported")
                require(not any(k in data["nodes"][0] for k in ("matrix", "translation", "rotation", "scale")),
                        "Component has additional unhandled transform")
                padding = (-binary_size) % 4
                binary_size += padding
                base = binary_size
                vo, ao = len(model["bufferViews"]), len(model["accessors"])
                for view in data["bufferViews"]:
                    v = copy.deepcopy(view)
                    require(v.get("buffer", 0) == 0, "Unexpected component buffer")
                    v["buffer"] = 0; v["byteOffset"] = base + v.get("byteOffset", 0)
                    model["bufferViews"].append(v)
                for accessor in data["accessors"]:
                    a = copy.deepcopy(accessor)
                    require("sparse" not in a and "bufferView" in a, "Unsupported accessor")
                    a["bufferView"] += vo; model["accessors"].append(a)
                mesh = copy.deepcopy(data["meshes"][0])
                mesh.pop("extensions", None)
                for primitive in mesh["primitives"]:
                    primitive["attributes"] = {k: v + ao for k, v in primitive["attributes"].items()}
                    if "indices" in primitive: primitive["indices"] += ao
                    primitive.pop("extensions", None); primitive.pop("material", None)
                    require("targets" not in primitive, "Morph targets unsupported")
                component_meshes[cid] = (mesh, digest)
                append_segments.append((file, offset, length, padding))
                appended_models.append(dict(component=cid, path=str(file), sha256=digest,
                                            bin_bytes=length, output_bin_offset=base))
                binary_size += length
            prototype, digest = component_meshes[cid]
            mesh = copy.deepcopy(prototype); mesh["name"] = name + "_WP06_cache_geometry"
            color = list(occurrence.get("color", [.6, .7, .8, 1]))
            material = len(model["materials"])
            model["materials"].append(dict(name=name + "_review",
                pbrMetallicRoughness=dict(baseColorFactor=color, metallicFactor=.28, roughnessFactor=.48),
                doubleSided=True))
            for primitive in mesh["primitives"]: primitive["material"] = material
            node = dict(name=name, mesh=len(model["meshes"]), matrix=gltf_matrix(occurrence["transform"]),
                        extras=dict(instance_id=name, representation_role=row["representation_role"],
                            part_number=row.get("pn"), mount_interface=row.get("mount_interface"),
                            mass_source=row.get("mass_source"), mass_kg=None,
                            qualification_status="NOT_EVALUATED", geometry_sha256=digest,
                            source_step_sha256=row["source_step"]["sha256"],
                            source_revision=row["source_revision"], display_geometry_basis="FROZEN_WP06_CACHE"))
            model["meshes"].append(mesh)
            if name in replaced:
                model["nodes"][old_ids[name]] = node
            else:
                model["nodes"][structure[0]]["children"].append(len(model["nodes"]))
                model["nodes"].append(node)
            mappings.append(dict(id=name, operation="REPLACE" if name in replaced else "ADD",
                                 cache_occurrence_id=occurrence["id"], component=cid,
                                 cache_transform_mm=occurrence["transform"], output_matrix_m=node["matrix"],
                                 component_glb_sha256=digest, source_step_sha256=row["source_step"]["sha256"]))
        # Delete nodes and reindex JSON references; old unreferenced BIN ranges are
        # intentionally retained to avoid touching any unchanged mesh bytes.
        deleted_indices = {old_ids[name] for name in removed}
        index_map = {}; remaining_nodes = []
        for i, node in enumerate(model["nodes"]):
            if i not in deleted_indices:
                index_map[i] = len(remaining_nodes); remaining_nodes.append(node)
        for node in remaining_nodes:
            if "children" in node:
                node["children"] = [index_map[i] for i in node["children"] if i not in deleted_indices]
        for scene_row in model["scenes"]:
            scene_row["nodes"] = [index_map[i] for i in scene_row["nodes"]]
        model["nodes"] = remaining_nodes
        model["asset"]["generator"] = "WP07 streamed display mesh compositor; no CAD kernel"
        model["scenes"][0]["name"] = "WP07 SERVICE review with WP06 delta"
        model["nodes"][0]["name"] = "WP07_SERVICE_REVIEW_DISPLAY_ONLY"
        model["nodes"][0]["extras"] = dict(scope=SCOPE, integration_manifest_sha256=inputs[str(MANIFEST.resolve())],
            retained_unchanged_instances=573, replaced_instances=8, removed_instances=4, added_instances=16,
            arm_representation="ACCEPTED_URDF_STL_UNCHANGED", exact_brep_equivalence_claimed=False)
        model["buffers"] = [dict(byteLength=binary_size)]
        output_ids = instance_map(model)
        require(set(output_ids) == set(expected), "Composed identity coverage failed")
        require(all(model["nodes"][output_ids[name]] == original_nodes[name] for name in retained),
                "Unchanged node was modified")
        require(set(output_ids.values()) <= reachable(model), "Unreachable display instance")
        snapshot = dict(schema="WP07_DISPLAY_COMPOSITION_INPUT_V1", state="service", scope=SCOPE,
                        units="metres", frame="S; +Z up", source_sha256=dict(inputs),
                        retained_ids=sorted(retained), removed_ids=sorted(removed), mappings=mappings,
                        appended_components=appended_models, original_bin_bytes=old_bin_length,
                        mesh_bbox_tolerance_mm=TOL_MM,
                        tolerance_basis="Inherited W4 build_viewer.py <2 mm display-scale bound screen; not engineering clearance")
        input_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        metadata = json.dumps(model, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        metadata += b" " * ((-len(metadata)) % 4)
        pad = (-binary_size) % 4
        with target.open("xb") as destination:
            destination.write(struct.pack("<4sII", b"glTF", 2, 28 + len(metadata) + binary_size + pad))
            destination.write(struct.pack("<I4s", len(metadata), b"JSON")); destination.write(metadata)
            destination.write(struct.pack("<I4s", binary_size + pad, b"BIN\0"))
            for file, offset, length, prefix in [(OLD, old_offset, old_bin_length, 0), *append_segments]:
                destination.write(b"\0" * prefix)
                with file.open("rb") as source:
                    source.seek(offset); remaining = length
                    while remaining:
                        block = source.read(min(1024 * 1024, remaining))
                        require(block, "Unexpected EOF streaming source BIN")
                        destination.write(block); remaining -= len(block)
            destination.write(b"\0" * pad)
        reread, offset, _ = glb_header(target)
        require(reread == model, "GLB JSON readback differs")
        out_ids = instance_map(reread)
        require(len(out_ids) == 597 and set(out_ids) == set(expected), "Readback identity coverage failed")
        baseline_bin = hashlib.sha256(); output_prefix = hashlib.sha256()
        with OLD.open("rb") as a, target.open("rb") as b:
            a.seek(old_offset); b.seek(offset); remaining = old_bin_length
            while remaining:
                size = min(1024 * 1024, remaining)
                baseline_bin.update(a.read(size)); output_prefix.update(b.read(size)); remaining -= size
        require(baseline_bin.digest() == output_prefix.digest(), "Frozen BIN prefix changed")
        bounds = []
        with target.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            for name, i in sorted(out_ids.items()):
                low, high, count = mesh_world_bounds(reread, mapped, offset, reread["nodes"][i])
                ref = expected[name].get("world_bounds_mm", expected[name]["bounds_mm"])
                target_bounds = np.asarray([ref["min_mm"], ref["max_mm"]], dtype=float)
                measured = np.asarray([low, high])
                error = float(np.max(np.abs(measured - target_bounds)))
                bounds.append(dict(id=name, status="PASS_DISPLAY_BOUNDS" if error < TOL_MM else "FAIL_DISPLAY_BOUNDS",
                    max_world_bbox_difference_mm=error, measured_mesh_bbox_mm=dict(min_mm=low.tolist(), max_mm=high.tolist()),
                    integration_bbox_mm=ref, position_values_measured=count,
                    arm_mesh_is_accepted_stl=bool(expected[name].get("arm_link"))))
        changed_inputs = [p for p, digest in inputs.items() if sha(p) != digest]
        require(not changed_inputs, "Inputs changed during composition: " + str(changed_inputs))
        failed = [r for r in bounds if r["status"] != "PASS_DISPLAY_BOUNDS"]
        report.update(status="PASS_DISPLAY_REVIEW_ONLY" if not failed else "FAIL_DISPLAY_BOUNDS",
            output=dict(path=str(target.resolve()), sha256=sha(target), bytes=target.stat().st_size),
            input_snapshot=dict(path=str(input_path.resolve()), sha256=sha(input_path)),
            instance_count=597, retained_count=573, replaced_count=8, removed_count=4, added_count=16,
            arm_count=sum(bool(r.get("arm_link")) for r in rows), unchanged_nodes_equal=True,
            old_bin_prefix_identical=True, old_bin_sha256=baseline_bin.hexdigest(),
            appended_component_count=len(append_segments), appended_payload_bytes=binary_size-old_bin_length,
            mesh_bbox_tolerance_mm=TOL_MM, mesh_bbox_tolerance_kind="DISPLAY_ONLY_NOT_BREP_CLEARANCE",
            failed_bounds_count=len(failed), world_bbox_checks=bounds,
            source_hashes_unchanged=True, completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        save()
        print(json.dumps(dict(status=report["status"], output=str(target),
                              instances=597, failed_bounds_count=len(failed))))
        return 0 if not failed else 2
    except Exception as exc:
        report.update(status="INCOMPLETE", error_type=type(exc).__name__, error=str(exc),
                      completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        if target.exists():
            report["partial_or_unverified_output"] = dict(path=str(target), sha256=sha(target), bytes=target.stat().st_size)
        save()
        print(json.dumps(dict(status="INCOMPLETE", error=str(exc))), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
