"""Independent R01 exported-STEP review; never imports candidate PASS functions.

The default command validates JSON identities only. Geometry is an explicit,
serial operation: --execute-geometry. Results are scoped and fail closed;
this program cannot close R01's material/preload/strength/hardware parent ticket.

Author/reviewer interface (adaptation is kept in normalize_contract only):
  step: {path, sha256}; units: mm; coordinate_frame: S
  instances: [{instance_id, step_label, role}]
  connections: [{connection_id, body_ids, origin_mm, axis,
                 fasteners: {screw, washer_head, washer_nut, nut},
                 bearing_faces: [{part_a, part_b, point_mm, normal,
                                  outer_radius_mm, supported_inner_radius_mm}],
                 paths: [{path_id, kind, moving_id, direction, travel_mm,
                          present_instance_ids, absent_instance_ids,
                          allowed_target_ids, radius_mm?, start_mm?, end_mm?}]}]
  context: {required_instance_ids, excluded_scope}

Paths are exact translational swept envelopes only. Arbitrary, rotating, or
incompletely specified paths remain UNKNOWN. Sweep shape is constructed by
this reviewer from the moving part's final STEP bounding box and translation,
or from a declared cylindrical tool envelope; this is conservative for material.
"""
from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
import math
import sys
import time
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
REVIEW = Path(__file__).resolve().parent
LIN_TOL = 1e-4
VOL_TOL = 1e-5
AREA_TOL = 1e-4
HOLE_RADIUS = 1.7
DESIGN_REVIEW_TARGET = "R01_CANDIDATE_2_WITH_EXPLICIT_THERMAL_AND_LEGACY_SCREW_RELIEFS"
ROLES_NOT_STATIC = {"TOOL_SWEEP", "INSERTION_SWEEP", "FUNCTIONAL_ENVELOPE", "VIEW_ONLY"}


def progress(stage, **details):
    """Flush bounded stage diagnostics without querying OS memory services."""
    print(json.dumps({"review_progress": stage, "monotonic_s": round(time.monotonic(), 3),
                      **details}, ensure_ascii=False, allow_nan=False), flush=True)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def vec(v):
    out = tuple(float(x) for x in v)
    if len(out) != 3 or not all(math.isfinite(x) for x in out):
        raise ValueError("Expected finite 3-vector")
    return out


def plus(a, b):
    return tuple(x + y for x, y in zip(a, b))


def scale(a, s):
    return tuple(x * s for x in a)


def minus(a, b):
    return plus(a, scale(b, -1))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def unit(v):
    v = vec(v)
    length = norm(v)
    if length < 1e-12:
        raise ValueError("Zero direction")
    return scale(v, 1 / length)


def axis_distance(point, origin, axis):
    d = minus(point, origin)
    return norm(minus(d, scale(axis, dot(d, axis))))


def resolve_path(value, contract_path):
    p = Path(value)
    return p if p.is_absolute() else (contract_path.parent / p).resolve()


def imported_label(label):
    # build123d.import_step's documented local implementation sanitizes these.
    # Preserve instance IDs in reports; this mapping is only for imported labels.
    return str(label).translate(str.maketrans(" .()", "____"))


def normalize_contract(raw):
    """Only maps serialization, never changes geometry or manufactures evidence."""
    if raw.get("schema") != "R01_CONNECTIONS_V1":
        return raw
    data = {"schema": raw["schema"], "run_id": raw.get("run_id"),
            "configuration": raw.get("configuration"), "units": raw.get("units"),
            "coordinate_frame": raw.get("frame"),
            "step": {"path": raw["step_path"], "sha256": raw["step_sha256"]},
            "instances": [], "connections": [], "additional_steps": [],
            "context": raw.get("context", {})}
    steps = {str(raw["step_path"])}
    for row in raw.get("instances", []):
        data["instances"].append({**row, "instance_id": row["id"], "step_label": row.get("label", row["id"])})
        path = row.get("step_path")
        if path and str(path) not in steps:
            data["additional_steps"].append({"path": path, "sha256": row.get("step_sha256")})
            steps.add(str(path))
    all_ids = {r["instance_id"] for r in data["instances"] if r.get("role") not in ROLES_NOT_STATIC}
    for row in raw.get("connections", []):
        c = {**row, "connection_id": row["id"], "body_ids": [r["id"] for r in row["members"]],
             "origin_mm": row["axis_point_S_mm"], "axis": row["axis_S"],
             "fasteners": row["hardware"], "bearing_faces": [], "paths": []}
        for b in row.get("bearing_planes", []):
            c["bearing_faces"].append({"part_a": b["hardware_id"], "part_b": b["member_id"],
                "point_mm": b["point_S_mm"], "normal": b["normal_S"],
                "outer_radius_mm": b["annulus_outer_d_mm"] / 2,
                "supported_inner_radius_mm": b["annulus_inner_d_mm"] / 2})
        for p in row.get("tool_paths", []):
            absent = set(p.get("assembly_absent_ids", []))
            c["paths"].append({"path_id": p["id"], "kind": "CYLINDRICAL_TOOL",
                "start_mm": p["start_S_mm"], "end_mm": p["end_S_mm"],
                "radius_mm": p["outer_d_mm"] / 2, "inner_radius_mm": p.get("inner_d_mm", 0) / 2,
                "present_instance_ids": sorted(all_ids - absent), "absent_instance_ids": sorted(absent),
                "allowed_target_ids": p.get("allowed_contact_ids", [])})
        for p in row.get("insertion_paths", []):
            absent = set(p.get("assembly_absent_ids", []))
            c["paths"].append({"path_id": p["id"], "kind": "AXIAL_FASTENER_TRANSLATION",
                "moving_id": p["moving_id"], "direction": p["direction_S"], "travel_mm": p["travel_mm"],
                "present_instance_ids": sorted(all_ids - absent), "absent_instance_ids": sorted(absent),
                "allowed_target_ids": p.get("allowed_contact_ids", [])})
        data["connections"].append(c)
    return data


def expected_connections():
    """Independent original-ticket design constants, not author self-reports."""
    rows = []
    for deck, z in (("lower", -99.65), ("upper", -10.0)):
        for side in (-1, 1):
            for x in (-150.0, -50.0, 50.0, 140.0):
                segment = 0 if x < 20 else 1
                origin = (x, side * 92.65, z)
                rows.append({"key": f"deck_{deck}_{side}_{x:g}",
                             "axis": (0.0, 0.0, 1.0), "origin": origin,
                             "holes": [(f"{deck}_equipment_deck", -1.5, 1.5),
                                       (f"{deck}_deck_angle_{side}_{segment}", -4.5, -1.5)]})
            zh = -94.15 if deck == "lower" else -18.5
            for x in (-130.0, -70.0, 60.0, 130.0):
                segment = 0 if x < 20 else 1
                # Axis points from the inner angle towards the outer shear web.
                rows.append({"key": f"web_{deck}_{side}_{x:g}",
                             "axis": (0.0, float(side), 0.0),
                             "origin": (x, side * 101.15, zh),
                             "holes": [(f"{deck}_deck_angle_{side}_{segment}", -3.0, 0.0),
                                       (f"shear_web_{side}", 0.0, 2.0)]})
    return rows


def check_contract(data, contract_path):
    checks = []
    def add(name, ok, **extra):
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", **extra})
    add("units_mm_and_frame_S", data.get("units") == "mm" and data.get("coordinate_frame") == "S")
    add("physical_configuration_not_exploded", bool(data.get("configuration")) and "explod" not in str(data.get("configuration", "")).lower())
    instances = data.get("instances", [])
    ids = [r.get("instance_id") for r in instances]
    labels = [imported_label(r.get("step_label", r.get("instance_id"))) for r in instances]
    add("instance_ids_nonempty_unique", bool(ids) and all(ids) and len(ids) == len(set(ids)))
    add("step_labels_nonempty_unique", bool(labels) and all(labels) and len(labels) == len(set(labels)))
    required_bodies = {h[0] for e in expected_connections() for h in e["holes"]}
    add("original_12_changed_bodies_present", required_bodies <= set(ids), missing=sorted(required_bodies - set(ids)))
    connections = data.get("connections", [])
    cids = [r.get("connection_id") for r in connections]
    add("32_unique_connections", len(cids) == 32 and len(set(cids)) == 32 and all(cids))
    used, matched = set(), {}
    for expected in expected_connections():
        bodyset = {r[0] for r in expected["holes"]}
        matches = []
        for row in connections:
            try:
                axis = unit(row["axis"])
                if (set(row["body_ids"]) == bodyset
                        and abs(abs(dot(axis, expected["axis"])) - 1) < LIN_TOL
                        and axis_distance(vec(row["origin_mm"]), expected["origin"], expected["axis"]) < LIN_TOL):
                    matches.append(row)
            except (KeyError, ValueError, TypeError):
                pass
        ok = len(matches) == 1
        add("connection_identity:" + expected["key"], ok, matches=[x.get("connection_id") for x in matches])
        if ok:
            row = matches[0]
            matched[expected["key"]] = row
            add("hole_diameter:" + expected["key"], abs(float(row.get("hole_diameter_mm", 3.4)) - 3.4) < LIN_TOL)
            hardware = row.get("fasteners", {})
            fids = [hardware.get(k) for k in ("screw", "washer_head", "washer_nut", "nut")]
            add("four_distinct_hardware:" + expected["key"],
                all(fids) and len(set(fids)) == 4 and set(fids) <= set(ids) and not (used & set(fids)), ids=fids)
            used.update(x for x in fids if x)
            expected_members = {r[0] for r in expected["holes"]}
            contact_members = {r.get("part_b") for r in row.get("bearing_faces", [])}
            add("both_members_have_bearing_contract:" + expected["key"], contact_members == expected_members)
    add("128_distinct_named_hardware", len(used) == 128, actual=len(used))
    files = [data.get("step", {})] + data.get("additional_steps", [])
    for entry in files:
        try:
            p = resolve_path(entry["path"], contract_path)
            actual = sha256(p)
            add("step_hash:" + p.name, actual == entry.get("sha256"), path=str(p), actual_sha256=actual)
        except Exception as exc:
            add("step_hash", False, error=str(exc))
    return checks, matched


def baseline_context_identity(data):
    """Independent old identity set, including equipment and existing hardware."""
    manifest_path = RUN / "inputs/INPUT_MANIFEST.json"
    state = data.get("context", {}).get("state", data.get("state", "service"))
    if state not in ("parking", "released", "service"):
        return {"status": "UNKNOWN", "reason": "No valid context physical state", "state": state}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    matches = [r for r in manifest["source_snapshot"] if Path(r["path"]).name == state + "_instances.json"]
    if len(matches) != 1:
        return {"status": "UNKNOWN", "reason": "Original state inventory absent or ambiguous", "state": state}
    source = matches[0]
    actual = sha256(source["path"])
    if actual != source["sha256"]:
        return {"status": "FAIL", "reason": "Original inventory hash drift", "state": state}
    old = json.loads(Path(source["path"]).read_text(encoding="utf-8-sig"))
    required = {r["id"] for r in old["instances"]
                if not r.get("arm_link") and r.get("representation_role") in ("PHYSICAL_GEOMETRY", "SIMPLIFIED_PROXY")}
    declared = {r["instance_id"] for r in data["instances"] if r.get("role") not in ROLES_NOT_STATIC}
    missing = sorted(required - declared)
    return {"status": "PASS" if not missing else "UNKNOWN", "state": state,
            "source_path": source["path"], "source_sha256": actual,
            "required_instance_ids": sorted(required), "missing_instance_ids": missing,
            "scope": "Original non-arm physical geometry plus proxies. Full arm and functional-space validation remain outside this R01 check."}


def bootstrap_cad_runtime():
    """Use the installed runtime's font guard, never its geometry/PASS helpers.

    build123d scans system fonts at import. This host has a malformed font;
    cadgen.__init__ installs its existing per-file scan guard before build123d
    imports. Nothing here invokes a candidate generator, author check, renderer,
    or cadgen acceptance algorithm, nor edits any system font or dependency.
    """
    import importlib
    import importlib.util
    if importlib.util.find_spec("cadgen") is None:
        runtime_src = Path(r"F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src")
        if not (runtime_src / "cadgen/__init__.py").is_file():
            raise RuntimeError("Installed CAD runtime bootstrap not found")
        sys.path.insert(0, str(runtime_src))
    cadgen = importlib.import_module("cadgen")
    font_scan = importlib.import_module("cadgen._internal.font_scan")
    return {"purpose": "Existing CAD runtime import/font compatibility only",
            "cadgen_path": str(Path(cadgen.__file__).resolve()),
            "cadgen_sha256": sha256(cadgen.__file__),
            "font_guard_path": str(Path(font_scan.__file__).resolve()),
            "font_guard_sha256": sha256(font_scan.__file__),
            "candidate_generator_imported": False, "author_pass_functions_used": False,
            "geometry_review_implementation": "This independent script; exported STEP readback using build123d/OCP primitives"}


class GeometryReview:
    def __init__(self, data, contract_path):
        # Explicit full-geometry mode is the only place CAD libraries are loaded.
        from build123d import import_step, Solid, Box, Plane, Location
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
        from OCP.BRep import BRep_Tool
        self.Solid, self.Box, self.Plane, self.Location = Solid, Box, Plane, Location
        self.Adaptor = BRepAdaptor_Surface
        self.CYL, self.PLANE, self.BRep_Tool = GeomAbs_Cylinder, GeomAbs_Plane, BRep_Tool
        self.data, self.shapes, self.import_metadata = data, {}, []
        labels = {}
        for entry in [data["step"]] + data.get("additional_steps", []):
            path = resolve_path(entry["path"], contract_path)
            progress("step_import_start", path=str(path))
            root = import_step(path)
            progress("step_import_loaded", path=str(path))
            label_count_before = len(labels)
            def visit(node):
                children = list(getattr(node, "children", ()))
                if children:
                    for child in children:
                        visit(child)
                elif getattr(node, "label", ""):
                    label = node.label
                    if label in labels:
                        raise ValueError("Duplicate final STEP label: " + label)
                    # located() deepcopies the object's __dict__, including an
                    # anytree parent/siblings graph. Calling it on the imported
                    # node clones the whole assembly for EACH leaf. Capture the
                    # same global transform first; wrap only its TopoDS geometry
                    # with parent=None, then copy/place that isolated leaf.
                    global_location = node.global_location
                    detached = type(node)(node.wrapped)
                    if detached.parent is not None or getattr(detached, "children", ()):
                        raise ValueError("Geometry leaf failed to detach from assembly tree: " + label)
                    labels[label] = detached.located(global_location)
                    if len(labels) % 20 == 0:
                        progress("step_detach_progress", path=str(path), total_detached_labels=len(labels))
            visit(root)
            file_labels = len(labels) - label_count_before
            self.import_metadata.append({"path": str(path), "detached_leaf_count": file_labels,
                                         "method": "global_location captured; fresh TopoDS-only wrapper; located on detached wrapper"})
            progress("step_detach_done", path=str(path), detached_leaf_count=file_labels)
            # The original XDE/anytree import is no longer part of the review
            # state. Explicitly collect its parent/child cycles between files.
            del root
            gc.collect()
            progress("step_source_tree_released", path=str(path))
        for row in data["instances"]:
            label = imported_label(row.get("step_label", row["instance_id"]))
            if label not in labels:
                raise ValueError("Required final STEP label absent: " + label)
            self.shapes[row["instance_id"]] = labels[label]
        unused = sorted(set(labels) - {imported_label(r.get("step_label", r["instance_id"])) for r in data["instances"]})
        if unused:
            raise ValueError("Unregistered STEP bodies: " + repr(unused))
        progress("shape_registry_ready", instance_count=len(self.shapes))
        self.bounds = {key: self.get_bounds(shape) for key, shape in self.shapes.items()}
        progress("bounds_ready", instance_count=len(self.bounds))

    @staticmethod
    def get_bounds(shape):
        box = shape.bounding_box()
        return vec(box.min), vec(box.max)

    @staticmethod
    def volume(shape):
        return 0.0 if shape is None else sum(float(s.volume) for s in shape.solids())

    def overlap(self, a, b):
        amin, amax = self.get_bounds(a)
        bmin, bmax = self.get_bounds(b)
        if any(min(x, y) - max(u, v) <= LIN_TOL for x, y, u, v in zip(amax, bmax, amin, bmin)):
            return 0.0
        return self.volume(a & b)

    def cylinder(self, radius, origin, axis, lo, hi):
        return self.Solid.make_cylinder(radius, hi - lo,
                    self.Plane(origin=plus(origin, scale(axis, lo)), z_dir=axis))

    def annulus(self, inner, outer, origin, axis, lo, hi):
        return self.cylinder(outer, origin, axis, lo, hi) - self.cylinder(inner, origin, axis, lo, hi)

    def hole(self, shape, origin, axis, lo, hi, radius=HOLE_RADIUS):
        """Check actual exported hole, not merely the generator's nominal coordinates."""
        length = hi - lo
        area = 0.0
        radii = []
        for face in shape.faces():
            surf = self.Adaptor(face.wrapped, True)
            if surf.GetType() != self.CYL:
                continue
            cyl = surf.Cylinder()
            pos = (cyl.Location().X(), cyl.Location().Y(), cyl.Location().Z())
            direction = (cyl.Axis().Direction().X(), cyl.Axis().Direction().Y(), cyl.Axis().Direction().Z())
            if axis_distance(pos, origin, axis) > LIN_TOL or abs(abs(dot(direction, axis)) - 1) > LIN_TOL:
                continue
            if abs(cyl.Radius() - radius) <= LIN_TOL:
                area += float(face.area)
                radii.append(cyl.Radius())
        inner = self.cylinder(radius - .001, origin, axis, lo + .001, hi - .001)
        wall = self.annulus(radius + .001, radius + .051, origin, axis, lo + .001, hi - .001)
        void_overlap = self.overlap(shape, inner)
        wall_volume = self.volume(wall)
        material_volume = self.volume(shape & wall)
        expected_area = 2 * math.pi * radius * length
        ok = (bool(radii) and abs(area - expected_area) <= max(AREA_TOL, expected_area * 1e-6)
              and void_overlap <= VOL_TOL and abs(material_volume - wall_volume) <= max(VOL_TOL, wall_volume * 1e-5))
        return {"status": "PASS" if ok else "FAIL", "expected_radius_mm": radius, "wall_area_mm2": area,
                "expected_full_cylinder_area_mm2": expected_area, "radii_mm": radii,
                "hole_probe_material_mm3": void_overlap, "wall_probe_mm3": wall_volume,
                "wall_material_mm3": material_volume}

    def planar_faces(self, shape, point, normal):
        out = []
        for face in shape.faces():
            surf = self.Adaptor(face.wrapped, True)
            if surf.GetType() != self.PLANE:
                continue
            pl = surf.Plane()
            p = (pl.Location().X(), pl.Location().Y(), pl.Location().Z())
            d = (pl.Axis().Direction().X(), pl.Axis().Direction().Y(), pl.Axis().Direction().Z())
            if abs(dot(minus(p, point), normal)) < LIN_TOL and abs(abs(dot(d, normal)) - 1) < LIN_TOL:
                out.append(face)
        return out

    def bearing(self, row):
        a, b = self.shapes[row["part_a"]], self.shapes[row["part_b"]]
        point, normal = vec(row["point_mm"]), unit(row["normal"])
        faces_a, faces_b = self.planar_faces(a, point, normal), self.planar_faces(b, point, normal)
        contacts = []
        for fa in faces_a:
            for fb in faces_b:
                common = fa & fb
                contacts.append(0.0 if common is None else float(common.area))
        actual = sum(contacts)
        outer, inner = float(row["outer_radius_mm"]), float(row["supported_inner_radius_mm"])
        # M3 R01 washer OD is <= 6 mm; a source cannot relax the ticket's geometry.
        permitted = 0 < inner < outer <= 3.0 + LIN_TOL
        expected = math.pi * (outer * outer - inner * inner)
        ok = permitted and abs(actual - expected) <= max(AREA_TOL, expected * 1e-5)
        return {"status": "PASS" if ok else "FAIL", "actual_contact_area_mm2": actual,
                "nominal_supported_annulus_mm2": expected, "faces_a": len(faces_a), "faces_b": len(faces_b),
                "scope": "Nominal surface support only; not allowable bearing stress or preload."}

    def validity(self):
        rows = []
        progress("validity_start", instance_count=len(self.shapes))
        for key, shape in self.shapes.items():
            solids = list(shape.solids())
            valid = shape.is_valid and bool(solids) and all(s.volume > 0 for s in solids)
            closed = all(self.BRep_Tool.IsClosed_s(shell.wrapped) for shell in shape.shells())
            rows.append({"id": key, "status": "PASS" if valid and closed else "FAIL",
                         "solid_count": len(solids), "closed": closed, "volume_mm3": self.volume(shape)})
            if len(rows) % 25 == 0:
                progress("validity_progress", checked=len(rows), last_id=key)
        progress("validity_done", checked=len(rows))
        return rows

    def static_pairs(self):
        rows = []
        ids = [r["instance_id"] for r in self.data["instances"] if r.get("role") not in ROLES_NOT_STATIC]
        changed = {h[0] for e in expected_connections() for h in e["holes"]}
        for c in self.data["connections"]:
            changed.update(c.get("fasteners", {}).values())
        total = narrow = 0
        progress("affected_static_pairs_start", registered_instances=len(ids), affected_instances=len(changed))
        for i, ida in enumerate(ids):
            for idb in ids[i + 1:]:
                if ida not in changed and idb not in changed:
                    continue
                total += 1
                a, b = self.shapes[ida], self.shapes[idb]
                amin, amax = self.bounds[ida]
                bmin, bmax = self.bounds[idb]
                if any(min(x, y) - max(u, v) <= LIN_TOL for x, y, u, v in zip(amax, bmax, amin, bmin)):
                    continue
                narrow += 1
                if narrow == 1 or narrow % 50 == 0:
                    progress("affected_static_pairs_progress", broad_pairs=total, narrow_pairs=narrow, last_ids=[ida,idb])
                try:
                    v = self.overlap(a, b)
                    if v > VOL_TOL:
                        rows.append({"ids": [ida, idb], "status": "FAIL", "material_overlap_mm3": v})
                except Exception as exc:
                    rows.append({"ids": [ida, idb], "status": "ERROR", "error": str(exc)})
        progress("affected_static_pairs_done", broad_pairs=total, narrow_pairs=narrow, findings=len(rows))
        return {"status": "FAIL" if rows else "PASS", "expected_pair_count": total,
                "narrow_pair_count": narrow, "findings": rows,
                "scope": "Every registered affected-body or hardware pair; no positive-volume whitelist."}

    def pillar_notches(self):
        rows = []
        for deck, z in (("lower", -99.65), ("upper", -10.0)):
            shape = self.shapes[f"{deck}_equipment_deck"]
            for x in (20.0, 160.0):
                for y in (-94.15, 94.15):
                    # Original 14 mm pillar/spacer external section, including deck slab.
                    envelope = self.Box(14, 14, 3).moved(self.Location((x, y, z)))
                    notch = self.Box(17 - .002, 17 - .002, 3 - .002).moved(self.Location((x, y, z)))
                    v = self.overlap(shape, envelope)
                    nv = self.overlap(shape, notch)
                    rows.append({"id": f"{deck}:{x:g}:{y:g}", "status": "PASS" if v <= VOL_TOL and nv <= VOL_TOL else "FAIL",
                                 "pillar_envelope_overlap_mm3": v, "original_notch_overlap_mm3": nv,
                                 "scope": "Preserved nominal exclusion at deck; not pillar strength/fit verification."})
        return rows

    def preserved_dimensions(self):
        rows = []
        expected = {}
        for deck, z in (("lower", -99.65), ("upper", -10.0)):
            expected[f"{deck}_equipment_deck"] = ((-172, -98.15, z-1.5), (172, 98.15, z+1.5))
            for side in (-1, 1):
                for segment, (a, b) in enumerate(((-167, 11.5), (28.5, 151.5))):
                    ys = (87.15, 101.15) if side == 1 else (-101.15, -87.15)
                    zs = (z-4.5, z+9.5) if deck == "lower" else (z-15.5, z-1.5)
                    expected[f"{deck}_deck_angle_{side}_{segment}"] = ((a, ys[0], zs[0]), (b, ys[1], zs[1]))
        for side in (-1, 1):
            y = side * 102.15
            expected[f"shear_web_{side}"] = ((-172, y-1, -101.15), (172, y+1, 101.15))
        for key, target in expected.items():
            actual = self.bounds[key]
            delta = max(abs(a-b) for av, bv in zip(actual, target) for a,b in zip(av,bv))
            rows.append({"id": key, "status": "PASS" if delta < LIN_TOL else "FAIL",
                         "actual_bounds_mm": actual, "expected_bounds_mm": target, "max_delta_mm": delta})
        return rows

    def cylinder_axis_inventory(self, shape):
        """All cylindrical faces, without silently filtering unexpected radii."""
        found = set()
        for face in shape.faces():
            surf = self.Adaptor(face.wrapped, True)
            if surf.GetType() != self.CYL:
                continue
            cyl = surf.Cylinder()
            p = (cyl.Location().X(), cyl.Location().Y(), cyl.Location().Z())
            d = cyl.Axis().Direction()
            direction = (d.X(), d.Y(), d.Z())
            cardinal = next((i for i in range(3) if abs(abs(direction[i])-1) < LIN_TOL), None)
            if cardinal is None:
                found.add(("NONCARDINAL", *(round(x,5) for x in p), round(cyl.Radius(),5)))
            else:
                found.add(("XYZ"[cardinal], *(round(p[i],5) for i in range(3) if i != cardinal), round(cyl.Radius(),5)))
        return sorted(found)

    def deck_hole_axis_inventory(self):
        rows = []
        for deck in ("lower", "upper"):
            found = self.cylinder_axis_inventory(self.shapes[f"{deck}_equipment_deck"])
            expected = [("Z",x,y,HOLE_RADIUS) for x in (-150.0,-50.0,50.0,140.0) for y in (-92.65,92.65)]
            if deck == "lower":
                expected.append(("Z",-115.0,0.0,6.0))
            rows.append({"deck": deck, "status": "PASS" if set(found) == set(expected) else "FAIL",
                         "axis_key": "axis; two perpendicular coordinates in S mm; radius mm",
                         "actual_cylinder_axes": found, "expected_cylinder_axes": sorted(expected),
                         "scope": "Exactly 8 D3.4 fastening bores each; additionally one lower D12 thermal relief. No other cylindrical bore ignored."})
        return rows

    def angle_hole_axis_inventory(self):
        rows = []
        for deck in ("lower", "upper"):
            zh = -94.15 if deck == "lower" else -18.5
            for side in (-1,1):
                for segment in (0,1):
                    key = f"{deck}_deck_angle_{side}_{segment}"
                    xs = (-150.0,-50.0) if segment == 0 else (50.0,140.0)
                    wx = (-130.0,-70.0) if segment == 0 else (60.0,130.0)
                    expected = [("Z",x,side*92.65,HOLE_RADIUS) for x in xs]
                    expected += [("Y",x,zh,HOLE_RADIUS) for x in wx]
                    if deck == "lower":
                        legacy_xs = (-146.0,-86.0,-26.0) if segment == 0 else (34.0,94.0)
                        expected += [("Y",x,-94.0,HOLE_RADIUS) for x in legacy_xs]
                    actual = self.cylinder_axis_inventory(self.shapes[key])
                    rows.append({"id": key, "status": "PASS" if set(actual) == set(expected) else "FAIL",
                                 "actual_cylinder_axes": actual, "expected_cylinder_axes": sorted(expected)})
        return rows

    def explicit_relief_features(self):
        """Candidate-2 fixes derived from actual candidate-1 material failures."""
        rows = []
        deck = self.shapes["lower_equipment_deck"]
        thermal = self.hole(deck, (-115,0,-99.65), (0,0,1), -1.5,1.5, radius=6.0)
        body_id = "battery_thermal_link"
        if body_id in self.shapes:
            distance = float(deck.distance_to(self.shapes[body_id]))
            overlap = self.overlap(deck,self.shapes[body_id])
            clear_status = "PASS" if distance >= 1.0-LIN_TOL and overlap <= VOL_TOL else "FAIL"
        else:
            distance, overlap, clear_status = None, None, "UNKNOWN"
        rows.append({"id": "lower_deck_D12_battery_thermal_relief", **thermal,
                     "clearance_status": clear_status, "actual_distance_mm": distance, "overlap_mm3": overlap,
                     "required_nominal_radial_clearance_mm": 1.0,
                     "scope": "D10 nominal thermal-link proxy; thermal conduction, isolation, stress and actual strap shape remain UNKNOWN"})
        for side in (-1,1):
            for x in (-146.0,-86.0,-26.0,34.0,94.0):
                segment = 0 if x < 20 else 1
                member_id = f"lower_deck_angle_{side}_{segment}"
                member = self.shapes[member_id]
                h = self.hole(member, (x,side*101.15,-94), (0,side,0), -3,0)
                screw_id = f"shear_web_screw_{side}_{int(x-4)}_-94"
                if screw_id in self.shapes:
                    distance = float(member.distance_to(self.shapes[screw_id]))
                    overlap = self.overlap(member,self.shapes[screw_id])
                    clear_status = "PASS" if distance >= .2-LIN_TOL and overlap <= VOL_TOL else "FAIL"
                else:
                    distance, overlap, clear_status = None,None,"UNKNOWN"
                rows.append({"id": f"legacy_screw_relief_{side}_{x:g}", "member_id": member_id,
                             "screw_id": screw_id, **h, "clearance_status": clear_status,
                             "actual_distance_mm": distance, "overlap_mm3": overlap,
                             "required_nominal_radial_clearance_mm": .2,
                             "scope": "Geometric D3.4 relief of existing nominal D3 screw; new-hole strength/manufacturing allowables remain UNKNOWN"})
        return rows

    def path(self, row):
        """Conservative straight sweep; genuine omitted obstacles cannot be hidden."""
        present = row.get("present_instance_ids")
        if not present:
            return {"status": "UNKNOWN", "reason": "No explicit assembly-phase obstacle set"}
        absent = set(row.get("absent_instance_ids", []))
        targets = set(row.get("allowed_target_ids", []))
        if set(present) & absent or not (set(present) | absent | targets) <= set(self.shapes):
            return {"status": "FAIL", "reason": "Invalid/missing phase object identity"}
        moving = row.get("moving_id")
        if row["kind"] == "CYLINDRICAL_TOOL":
            start, end = vec(row["start_mm"]), vec(row["end_mm"])
            direction = unit(minus(end, start))
            outer, inner = float(row["radius_mm"]), float(row.get("inner_radius_mm", 0))
            if not (0 <= inner < outer):
                return {"status": "FAIL", "reason": "Invalid tool annulus"}
            swept = (self.cylinder(outer, start, direction, 0, norm(minus(end, start))) if inner == 0 else
                     self.annulus(inner, outer, start, direction, 0, norm(minus(end, start))))
            sweeps = [swept]
        elif row["kind"] == "AXIAL_FASTENER_TRANSLATION" and moving in self.shapes:
            direction = unit(row["direction"])
            distance = float(row["travel_mm"])
            if distance <= 0:
                return {"status": "FAIL", "reason": "Nonpositive declared travel"}
            part = self.shapes[moving]
            sweeps = [part]
            # The fasteners are axial prisms/cylinders. Sweep actual perpendicular
            # planar caps rather than an AABB that would fill the shaft clearance.
            for face in part.faces():
                surf = self.Adaptor(face.wrapped, True)
                if surf.GetType() == self.PLANE:
                    pl = surf.Plane()
                    d = (pl.Axis().Direction().X(), pl.Axis().Direction().Y(), pl.Axis().Direction().Z())
                    if abs(abs(dot(d, direction)) - 1) < LIN_TOL:
                        sweeps.append(self.Solid.extrude(face, scale(direction, distance)))
            if len(sweeps) == 1:
                return {"status": "UNKNOWN", "reason": "No axial cap representation for exact translational sweep"}
        elif row["kind"] == "AXIS_ALIGNED_TRANSLATION" and moving in self.shapes:
            direction = unit(row["direction"])
            if sum(abs(x) > LIN_TOL for x in direction) != 1:
                return {"status": "UNKNOWN", "reason": "Only axis-aligned conservative translation implemented"}
            distance = float(row["travel_mm"])
            lo, hi = self.bounds[moving]
            shift = scale(direction, distance)
            mn = tuple(min(a, a + b) for a, b in zip(lo, shift))
            mx = tuple(max(a, a + b) for a, b in zip(hi, shift))
            swept = self.Box(*minus(mx, mn)).moved(self.Location(scale(plus(mx, mn), .5)))
            sweeps = [swept]
        else:
            return {"status": "UNKNOWN", "reason": "Unsupported or absent explicit path envelope"}
        findings = []
        for obstacle in present:
            if obstacle == moving or obstacle in targets:
                continue
            volume = sum(self.overlap(s, self.shapes[obstacle]) for s in sweeps)
            if volume > VOL_TOL:
                findings.append({"obstacle": obstacle, "overlap_mm3": volume})
        return {"status": "FAIL" if findings else "PASS", "findings": findings,
                "scope": "Declared straight conservative envelope and phase; no supplier tool validation."}

    def negative_controls(self):
        """Review actual exported shapes with deliberate geometric defects in memory."""
        first = expected_connections()[0]
        body, lo, hi = first["holes"][1]
        original = self.shapes[body]
        plug = self.cylinder(HOLE_RADIUS, first["origin"], first["axis"], lo, hi)
        closed = original + plug
        missing = self.hole(closed, first["origin"], first["axis"], lo, hi)
        shifted = original.moved(self.Location((1, 0, 0)))
        axis = self.hole(shifted, first["origin"], first["axis"], lo, hi)
        # Reproduce original broken-edge counterexample analytically; only in memory.
        z = -99.65
        old = self.Box(344, 196.3, 3).moved(self.Location((0, 0, z)))
        for x in (20.0, 160.0):
            for y in (-94.15, 94.15):
                old = old - self.Box(17, 17, 7).moved(self.Location((x, y, z)))
        old = old - self.cylinder(HOLE_RADIUS, (150, 89, z), (0, 0, 1), -4, 4)
        broken = self.hole(old, (150, 89, z), (0, 0, 1), -1.5, 1.5)
        c = self.data["connections"][0]
        washer_id = c["fasteners"]["washer_head"]
        washer = self.shapes[washer_id]
        b = next(b for b in c["bearing_faces"] if b["part_a"] == washer_id)
        target = self.shapes[b["part_b"]]
        # Drive the actual exported head washer 0.25 mm into its actual member.
        # No artificial witness is needed and no candidate source is modified.
        collided = washer.moved(self.Location(scale(unit(b["normal"]), -.25)))
        volume = self.overlap(collided, target)
        results = [
            {"id": "filled_missing_mating_hole", "rejected": missing["status"] == "FAIL", "evidence": missing},
            {"id": "wrong_axis_position_1mm", "rejected": axis["status"] == "FAIL", "evidence": axis},
            {"id": "original_0p2mm_broken_edge", "rejected": broken["status"] == "FAIL", "evidence": broken,
             "fixture_source": "Independent analytic reconstruction of original deck dimensions; not a historical STEP replay"},
            {"id": "actual_washer_material_collision", "rejected": volume > VOL_TOL, "overlap_mm3": volume},
        ]
        return {"status": "PASS" if all(x["rejected"] for x in results) else "FAIL", "cases": results,
                "scope": "Reviewer sensitivity checks, not production hardware or authorization evidence."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=RUN / "results/r01_connections.json")
    parser.add_argument("--output", type=Path, default=REVIEW / "R01_REVIEW.json")
    parser.add_argument("--execute-geometry", action="store_true", help="Explicit serial OCC import/boolean review")
    args = parser.parse_args()
    started = time.monotonic()
    result = {"schema": "WP03_R01_INDEPENDENT_REVIEW_V1", "status": "NOT_RUN",
              "design_review_target": DESIGN_REVIEW_TARGET,
              "scope": "Original R01 nominal exported geometry/assembly subitems only",
              "parent_R01_closed": False, "R07_closed": False, "hardware_verified": False,
              "unknown": ["Supplier fastener/tool selection", "material_allowables", "thread_engagement_as_built",
                          "preload_and_locking", "strength_stiffness_fatigue", "physical_trial_assembly",
                          "thermal_relief_actual_strap_and_thermal_isolation", "deferred_equipment_adapter_cover_installation_paths"],
              "reviewer_source_sha256": sha256(__file__), "contract_path": str(args.contract)}
    try:
        result["contract_sha256"] = sha256(args.contract)
        data = normalize_contract(json.loads(args.contract.read_text(encoding="utf-8-sig")))
        result["contract_checks"], matched = check_contract(data, args.contract)
        result["baseline_context_identity"] = baseline_context_identity(data)
        contract_ok = all(r["status"] == "PASS" for r in result["contract_checks"])
        if not contract_ok:
            result["status"] = "CONTRACT_FAIL_GEOMETRY_NOT_RUN"
        elif not args.execute_geometry:
            result["status"] = "CONTRACT_PASS_GEOMETRY_NOT_RUN"
        else:
            progress("runtime_bootstrap_start")
            result["runtime_bootstrap"] = bootstrap_cad_runtime()
            progress("runtime_bootstrap_done")
            review = GeometryReview(data, args.contract)
            result["step_import_metadata"] = review.import_metadata
            result["validity"] = review.validity()
            result["holes"] = []
            result["bearing_faces"] = []
            result["paths"] = []
            for e in expected_connections():
                progress("connection_geometry_start", connection=e["key"])
                for body, lo, hi in e["holes"]:
                    result["holes"].append({"connection": e["key"], "body": body,
                                            **review.hole(review.shapes[body], e["origin"], e["axis"], lo, hi)})
                c = matched[e["key"]]
                if not c.get("bearing_faces"):
                    result["bearing_faces"].append({"connection": e["key"], "status": "UNKNOWN", "reason": "No bearing-face contract"})
                for bearing in c.get("bearing_faces", []):
                    result["bearing_faces"].append({"connection": e["key"], **bearing, **review.bearing(bearing)})
                if not c.get("paths"):
                    result["paths"].append({"connection": e["key"], "status": "UNKNOWN", "reason": "No insertion/tool path contract"})
                for path in c.get("paths", []):
                    result["paths"].append({"connection": e["key"], "path_id": path.get("path_id"), **review.path(path)})
                inserted_ids = {p.get("moving_id") for p in c.get("paths", [])
                                if p.get("kind") == "AXIAL_FASTENER_TRANSLATION"}
                # A screw/nut sweep does not demonstrate either washer can be
                # installed. Each of the four independently modelled parts needs
                # its own explicit assembly phase and reversible insertion path.
                for hardware_role in ("screw", "washer_head", "washer_nut", "nut"):
                    hardware_id = c["fasteners"][hardware_role]
                    if hardware_id not in inserted_ids:
                        result["paths"].append({"connection": e["key"], "moving_id": hardware_id,
                            "hardware_role": hardware_role, "status": "UNKNOWN",
                            "reason": "This standard part has no independently specified insertion path/assembly phase",
                            "scope": "Final fit and another part's insertion do not establish this part's installability"})
                progress("connection_geometry_done", connection=e["key"])
            progress("preserved_dimensions_start")
            result["preserved_dimensions"] = review.preserved_dimensions()
            result["deck_hole_axis_inventory"] = review.deck_hole_axis_inventory()
            result["angle_hole_axis_inventory"] = review.angle_hole_axis_inventory()
            result["explicit_relief_features"] = review.explicit_relief_features()
            result["pillar_notches"] = review.pillar_notches()
            progress("preserved_dimensions_and_notches_done")
            result["affected_static_pairs"] = review.static_pairs()
            progress("negative_controls_start")
            result["negative_controls"] = review.negative_controls()
            progress("negative_controls_done")
            required_context = set(result["baseline_context_identity"].get("required_instance_ids", []))
            result["context_coverage"] = {"status": "PASS" if required_context and required_context <= set(review.shapes) else "UNKNOWN",
                                          "required_ids": sorted(required_context), "missing": sorted(required_context - set(review.shapes)),
                                          "excluded_scope": data.get("context", {}).get("excluded_scope", [])}
            checks = [r["status"] for field in ("validity", "holes", "bearing_faces", "paths", "pillar_notches", "preserved_dimensions", "deck_hole_axis_inventory", "angle_hole_axis_inventory", "explicit_relief_features") for r in result[field]]
            checks += [r["clearance_status"] for r in result["explicit_relief_features"]]
            checks += [result[k]["status"] for k in ("affected_static_pairs", "negative_controls", "context_coverage", "baseline_context_identity")]
            result["status"] = ("SCOPED_GEOMETRY_REVIEW_FAIL" if any(s in ("FAIL", "ERROR") for s in checks)
                                else "SCOPED_GEOMETRY_REVIEW_WITH_UNKNOWN" if "UNKNOWN" in checks
                                else "SCOPED_NOMINAL_GEOMETRY_ASSEMBLY_PASS_PARENT_OPEN")
            if sha256(args.contract) != result["contract_sha256"]:
                result["status"] = "INPUT_DRIFT_FAIL"
            for entry in [data["step"]] + data.get("additional_steps", []):
                if sha256(resolve_path(entry["path"], args.contract)) != entry["sha256"]:
                    result["status"] = "INPUT_DRIFT_FAIL"
    except Exception as exc:
        import traceback
        result["status"] = "REVIEW_ERROR_FAIL_CLOSED"
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
    result["elapsed_s"] = time.monotonic() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output)}, ensure_ascii=False))
    return 1 if any(x in result["status"] for x in ("FAIL", "ERROR")) else 0


if __name__ == "__main__":
    sys.exit(main())
