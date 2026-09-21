"""Lossless scene-reference pruning and byte-exact GLB buffer deduplication.

Pure standard-library streaming; never loads CAD, NumPy, a renderer or COM.
Preserves every live primitive attribute, index, material and node transform.
No decimation, coordinate conversion, quantization, welding or LOD change.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time
import traceback

RUN = Path(__file__).resolve().parents[1]
SOURCE = RUN/"viewer/WP07_SERVICE_BREP_REVIEW_V3.glb"
SOURCE_SHA = "344589b4aad41b2a0167fad707ed4b044ae7d0e6061818d551d13ded4755367b"
PRIOR = RUN/"viewer/REVIEW_GLB_V3_RESULT.json"
MANIFEST = RUN/"results/INTEGRATION_MANIFEST.json"
TARGET = RUN/"viewer/WP07_SERVICE_BREP_REVIEW_V4_COMPACT.glb"
REPORT = RUN/"viewer/REVIEW_GLB_V4_COMPACT_RESULT.json"
CHUNK = 1024*1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def header(path):
    with Path(path).open("rb") as stream:
        magic, version, total = struct.unpack("<4sII", stream.read(12))
        require(magic == b"glTF" and version == 2 and total == Path(path).stat().st_size, "Invalid GLB header")
        length, kind = struct.unpack("<I4s", stream.read(8))
        require(kind == b"JSON" and length % 4 == 0, "Expected aligned JSON chunk")
        model = json.loads(stream.read(length))
        size, kind = struct.unpack("<I4s", stream.read(8))
        require(kind == b"BIN\0" and size % 4 == 0 and stream.tell()+size == total, "Expected one final aligned BIN chunk")
        require(len(model["buffers"]) == 1 and "uri" not in model["buffers"][0], "Expected one internal buffer")
        require(0 <= size-model["buffers"][0]["byteLength"] <= 3, "BIN/buffer length mismatch")
        return model, stream.tell(), size


def closure(model):
    require(model["asset"]["version"] == "2.0" and len(model["scenes"]) == 1 and model.get("scene", 0) == 0,
            "This bounded compactor requires one active scene")
    require(not any(model.get(k) for k in ("images", "textures", "skins", "animations", "cameras", "extensionsUsed", "extensionsRequired", "extensions")),
            "Unreviewed non-static/textured/extended GLB")
    nodes = set()
    todo = list(model["scenes"][0]["nodes"])
    while todo:
        index = todo.pop()
        require(isinstance(index, int) and 0 <= index < len(model["nodes"]), "Invalid node index")
        if index in nodes:
            raise ValueError("Repeated node or cycle in single-scene tree")
        nodes.add(index)
        node = model["nodes"][index]
        require(not any(k in node for k in ("skin", "camera", "weights", "extensions")), "Unsupported node references")
        todo.extend(node.get("children", []))
    meshes = {model["nodes"][n]["mesh"] for n in nodes if "mesh" in model["nodes"][n]}
    accessors, materials = set(), set()
    semantics = {}
    for mesh in meshes:
        row = model["meshes"][mesh]
        require(set(row) <= {"name", "primitives", "extras"}, "Unsupported mesh references")
        for primitive in row["primitives"]:
            require(set(primitive) <= {"attributes", "indices", "material", "mode", "extras"}, "Unsupported primitive references")
            require(primitive.get("mode", 4) == 4 and "indices" in primitive, "Expected indexed triangle primitives")
            require("POSITION" in primitive["attributes"] and "NORMAL" in primitive["attributes"], "Position/normal stream missing")
            for semantic, index in primitive["attributes"].items():
                accessors.add(index)
                semantics.setdefault(semantic, set()).add(index)
            accessors.add(primitive["indices"])
            semantics.setdefault("INDICES", set()).add(primitive["indices"])
            materials.add(primitive["material"])
    views = set()
    for index in accessors:
        a = model["accessors"][index]
        require("bufferView" in a and not any(k in a for k in ("sparse", "extensions")), "Unsupported accessor storage")
        views.add(a["bufferView"])
    for index in views:
        v = model["bufferViews"][index]
        require(v.get("buffer", 0) == 0 and not v.get("extensions"), "Unsupported buffer view")
        require(v.get("byteOffset", 0) >= 0 and v["byteLength"] > 0 and
                v.get("byteOffset", 0)+v["byteLength"] <= model["buffers"][0]["byteLength"], "Buffer view outside source BIN")
    return dict(nodes=nodes, meshes=meshes, accessors=accessors, views=views, materials=materials, semantics=semantics)


def instances(model, live):
    rows = {}
    for index in live["nodes"]:
        node = model["nodes"][index]
        name = node.get("extras", {}).get("instance_id")
        if name is not None:
            require(name not in rows, "Duplicate instance identity")
            rows[name] = index
    return rows


def stream_digest(stream, offset, length):
    stream.seek(offset)
    h = hashlib.sha256()
    left = length
    while left:
        block = stream.read(min(CHUNK, left))
        require(bool(block), "Unexpected BIN EOF")
        h.update(block)
        left -= len(block)
    return h.hexdigest()


def same_bytes(a, ao, b, bo, length):
    a.seek(ao)
    b.seek(bo)
    left = length
    while left:
        size = min(CHUNK, left)
        x, y = a.read(size), b.read(size)
        require(len(x) == len(y) == size, "Unexpected BIN EOF during equality check")
        if x != y:
            return False
        left -= size
    return True


def count_triangles(model, live):
    def mesh_count(index):
        total = 0
        for p in model["meshes"][index]["primitives"]:
            n = model["accessors"][p["indices"]]["count"]
            require(n % 3 == 0, "Index count is not a triangle list")
            total += n//3
        return total
    return dict(live_mesh_triangles=sum(mesh_count(i) for i in live["meshes"]),
                instantiated_triangles=sum(mesh_count(model["nodes"][i]["mesh"]) for i in live["nodes"] if "mesh" in model["nodes"][i]),
                mesh_occurrence_count=sum("mesh" in model["nodes"][i] for i in live["nodes"]))


def write_glb(model, blobs, source_offset, binary_length):
    encoded = json.dumps(model, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    encoded += b" "*((-len(encoded)) % 4)
    pad = (-binary_length) % 4
    with TARGET.open("xb") as output, SOURCE.open("rb") as source:
        output.write(struct.pack("<4sII", b"glTF", 2, 28+len(encoded)+binary_length+pad))
        output.write(struct.pack("<I4s", len(encoded), b"JSON"))
        output.write(encoded)
        output.write(struct.pack("<I4s", binary_length+pad, b"BIN\0"))
        cursor = 0
        for blob in blobs:
            output.write(b"\0"*(blob["target_offset"]-cursor))
            source.seek(source_offset+blob["source_offset"])
            left = blob["bytes"]
            while left:
                block = source.read(min(CHUNK, left))
                require(bool(block), "Unexpected BIN EOF during copy")
                output.write(block)
                left -= len(block)
            cursor = blob["target_offset"]+blob["bytes"]
        require(cursor == binary_length, "Incorrect compact BIN length")
        output.write(b"\0"*pad)


def main():
    for path in (TARGET, REPORT):
        require(not path.exists(), "Refuse overwrite: " + str(path))
    started = time.monotonic()
    report = dict(schema="WP07_LOSSLESS_GLB_COMPACT_V4", status="RUNNING", state="service",
        started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), source_sha256_before={},
        scope="Exact live scene-reference pruning and streamed byte deduplication of the accepted V3 display GLB. "
              "All referenced vertex attributes (including CAD edge attributes), indices, triangle order, "
              "primitive/material relationships and 597 instance frames are unchanged.",
        rendered=False, snapshot_reviewed=False, cad_or_com_executed=False, decimation=False,
        coordinate_quantization=False, attributes_removed=[], exact_brep_equivalence_claimed=False,
        collision_verified=False, physical_assembly_completed=False, manufacturing_release=False)
    inputs = report["source_sha256_before"]
    def bind(path, expected=None):
        path = Path(path).resolve()
        digest = sha(path)
        require(expected is None or digest == expected, "Input SHA mismatch: " + str(path))
        inputs[str(path)] = digest
        return digest
    def save():
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    with REPORT.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False)
    try:
        bind(__file__)
        bind(SOURCE, SOURCE_SHA)
        bind(PRIOR)
        prior = read(PRIOR)
        require(prior["status"] == "PASS_DISPLAY_REVIEW_ONLY" and prior["output"]["sha256"] == SOURCE_SHA,
                "V3 display pass not bound to source GLB")
        require(prior["instance_count"] == 597 and prior["arm_body_count"] == 391 and prior["failed_bounds_count"] == 0,
                "Unexpected V3 scope")
        require(prior["mesh_bbox_tolerance_mm"] == 2.0, "Original display tolerance changed")
        bind(prior["input_snapshot"]["path"], prior["input_snapshot"]["sha256"])
        bind(prior["legacy_v1"]["report"])
        report["legacy_v1"] = prior["legacy_v1"]
        manifest_sha = bind(MANIFEST)
        require(prior["source_sha256"][str(MANIFEST.resolve())] == manifest_sha, "V3 integration identity binding changed")
        manifest = read(MANIFEST)
        expected_ids = {r["id"] for r in manifest["states"]["service"]["instances"]}
        require(len(expected_ids) == 597, "Manifest instance set changed")
        failed_snapshot = RUN/"logs/snapshot_service.run.json"
        if failed_snapshot.is_file():
            report["prior_snapshot_attempt"] = dict(path=str(failed_snapshot), sha256=bind(failed_snapshot),
                                                    scope="Preserved actual V3 snapshot resource-limit result, not a produced image")
        model, bin_offset, bin_length = header(SOURCE)
        live = closure(model)
        source_ids = instances(model, live)
        require(set(source_ids) == expected_ids, "Source live instance identities differ")
        report["before"] = dict(file_bytes=SOURCE.stat().st_size, declared_binary_bytes=model["buffers"][0]["byteLength"],
            array_counts={key: len(model[key]) for key in ("nodes", "meshes", "accessors", "bufferViews", "materials")},
            live_counts={key: len(live[key]) for key in ("nodes", "meshes", "accessors", "views", "materials")},
            referenced_view_bytes=sum(model["bufferViews"][i]["byteLength"] for i in live["views"]),
            semantic_bytes={name: sum(model["bufferViews"][model["accessors"][i]["bufferView"]]["byteLength"] for i in indices)
                            for name, indices in live["semantics"].items()},
            **count_triangles(model, live))
        compact = copy.deepcopy(model)
        node_map = {old: i for i, old in enumerate(sorted(live["nodes"]))}
        mesh_map = {old: i for i, old in enumerate(sorted(live["meshes"]))}
        material_map = {old: i for i, old in enumerate(sorted(live["materials"]))}
        blob_buckets, blobs, view_blob = {}, [], {}
        binary_length = 0
        with SOURCE.open("rb") as source, SOURCE.open("rb") as comparison:
            for index in sorted(live["views"]):
                view = model["bufferViews"][index]
                offset, length = view.get("byteOffset", 0), view["byteLength"]
                digest = stream_digest(source, bin_offset+offset, length)
                key = (length, digest)
                match = None
                for candidate in blob_buckets.get(key, []):
                    if same_bytes(source, bin_offset+offset, comparison, bin_offset+blobs[candidate]["source_offset"], length):
                        match = candidate
                        break
                if match is None:
                    binary_length += (-binary_length) % 4
                    match = len(blobs)
                    blobs.append(dict(representative_source_view=index, source_offset=offset, target_offset=binary_length,
                                      bytes=length, sha256=digest))
                    blob_buckets.setdefault(key, []).append(match)
                    binary_length += length
                view_blob[index] = match
        # Views merge only when their complete metadata and exact data match;
        # metadata-incompatible views may share the same unchanged BIN byte range.
        views, view_map, seen_views = [], {}, {}
        for index in sorted(live["views"]):
            view = copy.deepcopy(model["bufferViews"][index])
            view["buffer"] = 0
            view["byteOffset"] = blobs[view_blob[index]]["target_offset"]
            key = canonical(view)
            if key not in seen_views:
                seen_views[key] = len(views)
                views.append(view)
            view_map[index] = seen_views[key]
        accessors, accessor_map, seen_accessors = [], {}, {}
        for index in sorted(live["accessors"]):
            accessor = copy.deepcopy(model["accessors"][index])
            accessor["bufferView"] = view_map[accessor["bufferView"]]
            key = canonical(accessor)
            if key not in seen_accessors:
                seen_accessors[key] = len(accessors)
                accessors.append(accessor)
            accessor_map[index] = seen_accessors[key]
        meshes = []
        for index in sorted(live["meshes"]):
            mesh = copy.deepcopy(model["meshes"][index])
            for p in mesh["primitives"]:
                p["attributes"] = {name: accessor_map[i] for name, i in p["attributes"].items()}
                p["indices"] = accessor_map[p["indices"]]
                p["material"] = material_map[p["material"]]
            meshes.append(mesh)
        nodes = []
        for index in sorted(live["nodes"]):
            node = copy.deepcopy(model["nodes"][index])
            if "children" in node:
                node["children"] = [node_map[i] for i in node["children"]]
            if "mesh" in node:
                node["mesh"] = mesh_map[node["mesh"]]
            nodes.append(node)
        compact.update(nodes=nodes, meshes=meshes, accessors=accessors, bufferViews=views,
            materials=[copy.deepcopy(model["materials"][i]) for i in sorted(live["materials"])],
            buffers=[dict(byteLength=binary_length)])
        compact["scenes"][0]["nodes"] = [node_map[i] for i in model["scenes"][0]["nodes"]]
        compact["asset"]["generator"] = "WP07 V4 exact live-scene byte compactor; source V3 preserved"
        report["deduplication"] = dict(method="SHA256+length candidates followed by actual streamed byte equality; complete metadata retained",
            byte_exact_unique_ranges=len(blobs), unique_payload_bytes=sum(b["bytes"] for b in blobs),
            compact_binary_bytes=binary_length, alignment_padding_bytes=binary_length-sum(b["bytes"] for b in blobs),
            source_view_to_compact_view={str(k): v for k, v in view_map.items()},
            source_accessor_to_compact_accessor={str(k): v for k, v in accessor_map.items()}, canonical_ranges=blobs)
        save()
        write_glb(compact, blobs, bin_offset, binary_length)
        actual, new_offset, new_length = header(TARGET)
        require(actual == compact, "Output JSON roundtrip mismatch")
        live_after = closure(actual)
        actual_ids = instances(actual, live_after)
        require(set(actual_ids) == expected_ids, "Output changed 597 instance identities")
        # Verify every retained view against actual output BIN, not an in-memory
        # reconstructed array. This preserves the complete POSITION/NORMAL/index
        # byte streams as well as their count/type/offset/normalized metadata.
        with SOURCE.open("rb") as before, TARGET.open("rb") as after:
            for old in sorted(live["views"]):
                a, b = model["bufferViews"][old], actual["bufferViews"][view_map[old]]
                require(a["byteLength"] == b["byteLength"], "View size changed")
                require(same_bytes(before, bin_offset+a.get("byteOffset", 0), after,
                                   new_offset+b.get("byteOffset", 0), a["byteLength"]), "View bytes changed")
            for old in sorted(live["accessors"]):
                expected = copy.deepcopy(model["accessors"][old])
                expected["bufferView"] = view_map[expected["bufferView"]]
                require(actual["accessors"][accessor_map[old]] == expected, "Accessor semantics changed")
        for old in sorted(live["nodes"]):
            expected = copy.deepcopy(model["nodes"][old])
            if "children" in expected:
                expected["children"] = [node_map[i] for i in expected["children"]]
            if "mesh" in expected:
                expected["mesh"] = mesh_map[expected["mesh"]]
            require(actual["nodes"][node_map[old]] == expected, "Node frame/metadata/child order changed")
        for old in sorted(live["meshes"]):
            expected = copy.deepcopy(model["meshes"][old])
            for p in expected["primitives"]:
                p["attributes"] = {k: accessor_map[v] for k, v in p["attributes"].items()}
                p["indices"] = accessor_map[p["indices"]]
                p["material"] = material_map[p["material"]]
            require(actual["meshes"][mesh_map[old]] == expected, "Primitive order/topology/material assignment changed")
        for old in sorted(live["materials"]):
            require(actual["materials"][material_map[old]] == model["materials"][old], "Material changed")
        triangles = count_triangles(actual, live_after)
        require(all(triangles[k] == report["before"][k] for k in triangles), "Triangle/occurrence count changed")
        require(all(sha(path) == digest for path, digest in inputs.items()), "Source input changed during compaction")
        report.update(status="PASS_EXACT_DISPLAY_COMPACTION", source_hashes_unchanged=True,
            output=dict(path=str(TARGET), bytes=TARGET.stat().st_size, sha256=sha(TARGET)),
            after=dict(array_counts={key: len(actual[key]) for key in ("nodes", "meshes", "accessors", "bufferViews", "materials")},
                       declared_binary_bytes=actual["buffers"][0]["byteLength"], **triangles),
            instance_count=len(actual_ids), source_frames_and_hierarchy_preserved=True, all_referenced_view_bytes_identical=True,
            all_accessor_semantics_preserved=True, all_primitive_attributes_preserved=True, all_live_materials_preserved=True,
            live_triangles_and_index_order_preserved=True, removed_file_bytes=SOURCE.stat().st_size-TARGET.stat().st_size,
            file_size_reduction_percent=100*(1-TARGET.stat().st_size/SOURCE.stat().st_size),
            mesh_bbox_tolerance_mm=2.0, mesh_bbox_tolerance_kind="DISPLAY_ONLY_NOT_BREP_CLEARANCE",
            display_bounds_basis="All vertex bytes and the complete hierarchy/transforms are identical, so V3 actual world bounds are preserved exactly; no new tolerance applied.",
            inherited_v3_world_bbox_checks=prior["world_bbox_checks"], failed_bounds_count=0,
            elapsed_seconds=time.monotonic()-started, completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        save()
        print(json.dumps({k: report[k] for k in ("status", "output", "before", "after", "file_size_reduction_percent", "instance_count", "elapsed_seconds")}, ensure_ascii=False))
        return 0
    except Exception as exc:
        report.update(status="FAIL_COMPACTION", error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc(),
                      completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-started)
        if TARGET.exists():
            report["partial_or_unverified_output"] = dict(path=str(TARGET), bytes=TARGET.stat().st_size, sha256=sha(TARGET))
        save()
        print(json.dumps(dict(status=report["status"], error=report["error"])), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
