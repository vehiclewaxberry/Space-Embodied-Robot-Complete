"""Read actual reference STEP afresh and check four boards without generating CAD.

Root executes this checker under its CAD resource guard. Only build123d's plain
STEP reader is used: no cadgen geometry cache, generator call, exported source
rewrite, COM, ECAD edit, or new model geometry. Output refuses overwrite.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import sys
import traceback
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
HELPER = RUN / "candidate/pcb_reference_panels.py"
ENTRY = RUN / "candidate/pcb_reference_panels.step.py"
CONTRACT = RUN / "inputs/pcb_reference_contract.json"
STEP = RUN / "candidate/pcb_reference_panels.step"
OUTPUT = RUN / "results/PCB_REFERENCE_STEP_READBACK.json"
CADGEN = Path("F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src")
FROZEN_SOURCE_SHA = {
    str(HELPER): "8e6c19ee387b3ef22d6e3e9bfcf5bbf910fb51da0ce309b352062d150b1652c9",
    str(ENTRY): "479561d3608afdb697e69e2dc5373b54d1bf1b697a7d740f335b43db949ddd47",
    str(CONTRACT): "cc6339e208cfc750c9585510766819dcc1db46c3813b442e3072c743e3ab839c",
}


class Incomplete(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bind(path, snapshots, expected=None):
    path = Path(path).resolve()
    if not path.is_file():
        raise Incomplete("Actual evidence file absent: " + str(path))
    digest = sha(path)
    snapshots[str(path)] = digest
    require(expected is None or digest == expected, "Frozen source SHA mismatch: " + str(path))
    return digest


def bbox_error(actual, expected):
    require(len(actual) == len(expected) == 2 and all(len(row) == 3 for row in actual+expected), "Invalid bbox")
    require(all(math.isfinite(v) for row in actual+expected for v in row), "Nonfinite bbox")
    return max(abs(actual[j][i]-expected[j][i]) for j in (0, 1) for i in range(3))


def unique_bbox_match(actual_boxes, expected_boards, tolerance):
    """Board identity is proven by a bijection of world bounds, never leaf order."""
    pairs = []
    used = set()
    for board in expected_boards:
        errors = [bbox_error(a, board["display_bounds_mm"]) for a in actual_boxes]
        candidates = [i for i, error in enumerate(errors) if error <= tolerance]
        require(len(candidates) == 1, f"Board {board['card']['id']} has {len(candidates)} bbox matches: {errors}")
        index = candidates[0]
        require(index not in used, "Two board identities match the same actual solid")
        used.add(index)
        pairs.append(dict(board_id=board["card"]["id"], actual_solid_index=index,
                          bbox_max_error_mm=errors[index], all_candidate_bbox_errors_mm=errors))
    require(used == set(range(len(actual_boxes))), "Unmatched actual solid(s)")
    return pairs


def expected_inputs(report):
    for path, digest in FROZEN_SOURCE_SHA.items():
        bind(path, report["source_sha256_before"], digest)
    spec = importlib.util.spec_from_file_location("wp07_pcb_readback_static_expectations", HELPER)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    # Only this pure Python function is called. build_reference_set() and _cad()
    # are never called; neither generates shapes nor supplies measured evidence.
    contract, boards, static_receipt = helper.preflight(CONTRACT)
    require(not any(k in sys.modules for k in ("build123d", "OCP")),
            "Standalone checker expected to be CAD-free before STEP read")
    for path, digest in contract["source_inputs"].items():
        bind(path, report["source_sha256_before"], digest)
    report["expectation_provenance"] = dict(
        helper_path=str(HELPER), helper_sha256=report["source_sha256_before"][str(HELPER)],
        function="preflight", reused_algorithm="KiCad source re-extraction, edge chaining, analytic profile area and display bounds",
        algorithmically_independent_from_generator=False, freshly_imported_step_objects=True,
        generator_called=False, generated_in_memory_objects_reused=False,
        interpretation="Actual STEP geometry is independently read back; expected-value extraction shares the generator's pure computation helper.",
        static_preflight_status=static_receipt["status"])
    report["numerical_tolerances"] = contract["numerical_tolerances"]
    report["drill_scope"] = contract["drill_scope"]
    return contract, boards


class Kernel:
    def __init__(self):
        sys.path.insert(0, str(CADGEN))
        import cadgen  # font guard before build123d and OCP
        from build123d import import_step, Solid
        from OCP.BRep import BRep_Tool
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
        from OCP.TopExp import TopExp
        from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_SOLID
        from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
        import OCP
        self.import_step, self.Solid = import_step, Solid
        self.BRep_Tool, self.Surface = BRep_Tool, BRepAdaptor_Surface
        self.BRepGProp, self.GProps = BRepGProp, GProp_GProps
        self.CYL, self.PLANE = GeomAbs_Cylinder, GeomAbs_Plane
        self.TopExp, self.IndexMap = TopExp, TopTools_IndexedDataMapOfShapeListOfShape
        self.FACE, self.EDGE, self.SOLID = TopAbs_FACE, TopAbs_EDGE, TopAbs_SOLID
        doc = BRepGProp.VolumeProperties_s.__doc__ or ""
        require(all(k in doc for k in ("Eps", "OnlyClosed", "SkipShared")), "Missing adaptive volume integration overload")
        self.runtime = dict(ocp_version=getattr(OCP, "__version__", None),
            step_reader="build123d.import_step (plain, no cadgen sidecar/cache write)",
            volume_integration="BRepGProp.VolumeProperties_s(Eps=1e-13, OnlyClosed=True, SkipShared=False)",
            triangulated_volume=False, geometry_generation=False)

    @staticmethod
    def bounds(shape):
        b = shape.bounding_box()
        return [list(b.min), list(b.max)]

    def unowned_count(self, shape, kind, ancestor):
        mapping = self.IndexMap()
        self.TopExp.MapShapesAndAncestors_s(shape.wrapped, kind, ancestor, mapping)
        return sum(mapping.FindFromIndex(i).Extent() == 0 for i in range(1, mapping.Extent()+1))

    def load(self, path):
        tree = self.import_step(path)
        # Detach the root's native topology before applying its absolute placement.
        # locate() acts in place; no anytree deepcopy or guessed transformation.
        location = tree.global_location
        flat = type(tree)(tree.wrapped)
        require(flat.parent is None and not getattr(flat, "children", ()), "Unsafe root detachment")
        flat.locate(location)
        free_faces = self.unowned_count(flat, self.FACE, self.SOLID)
        free_edges = self.unowned_count(flat, self.EDGE, self.FACE)
        bodies = []
        for body in flat.solids():
            detached = self.Solid(body.wrapped)
            require(detached.parent is None and not getattr(detached, "children", ()), "Unsafe solid detachment")
            # TopExp's solids already carry accumulated world placement from flat.
            bodies.append(detached)
        stats = dict(solid_count=len(bodies), root_is_valid=bool(flat.is_valid),
                     free_faces_without_solid=free_faces, free_edges_without_face=free_edges,
                     bounds_mm=self.bounds(flat))
        del tree, flat
        return bodies, stats

    def solid_facts(self, body):
        valid = bool(body.is_valid)
        shells = body.shells()
        closed = bool(shells) and all(self.BRep_Tool.IsClosed_s(s.wrapped) for s in shells)
        facts = dict(is_valid=valid, closed_shells=closed, shell_count=len(shells),
                     solid_count=len(body.solids()), bbox_mm=self.bounds(body), volume_mm3=None)
        if not valid or not closed:
            return facts
        props = self.GProps()
        err = self.BRepGProp.VolumeProperties_s(body.wrapped, props, Eps=1e-13, OnlyClosed=True, SkipShared=False)
        value = float(props.Mass())
        require(math.isfinite(value) and isinstance(err, (int, float)) and math.isfinite(err) and err >= 0,
                "Adaptive volume integration returned nonfinite/invalid values")
        facts.update(volume_mm3=value, adaptive_integration_error_estimate=err)
        return facts

    def surfaces(self, body):
        cylinders, horizontal_planes = [], []
        for index, face in enumerate(body.faces()):
            surface = self.Surface(face.wrapped, True)
            if surface.GetType() == self.CYL:
                cylinder = surface.Cylinder()
                point, direction = cylinder.Axis().Location(), cylinder.Axis().Direction()
                cylinders.append(dict(face_index=index, axis_point_mm=[point.X(), point.Y(), point.Z()],
                    axis_dir=[direction.X(), direction.Y(), direction.Z()], diameter_mm=2*cylinder.Radius(),
                    area_mm2=face.area, bbox_mm=self.bounds(face),
                    u_bounds_rad=[surface.FirstUParameter(), surface.LastUParameter()]))
            elif surface.GetType() == self.PLANE:
                plane = surface.Plane()
                if abs(plane.Axis().Direction().Z()) >= 1-1e-10:
                    horizontal_planes.append(dict(face_index=index, bbox_mm=self.bounds(face), area_mm2=face.area,
                                                  inner_wire_count=len(face.inner_wires())))
        return cylinders, horizontal_planes


def check_board(kernel, body, actual, board, match, tolerance):
    card, spec = board["card"], board["spec"]
    row = dict(id=card["id"], status="RUNNING", actual_solid_index=match["actual_solid_index"],
        source_pcb_path=card["pcb_path"], source_pcb_sha256=card["pcb_sha256"],
        actual_solid=actual, expected_display_bounds_mm=board["display_bounds_mm"],
        expected_volume_mm3=board["expected_modeled_material_volume_mm3"],
        thickness_source_line=card["thickness_source_line"], source_thickness_mm=card["thickness_mm"],
        T_DISPLAY_LOCAL_mm=spec["T_DISPLAY_LOCAL_mm"], holes=[], errors=[])
    try:
        require(actual["is_valid"] and actual["closed_shells"] and actual["solid_count"] == 1, "Actual solid invalid/open")
        require(actual["volume_mm3"] is not None and actual["volume_mm3"] > 0, "Actual solid has nonpositive volume")
        row["volume_error_mm3"] = abs(actual["volume_mm3"]-row["expected_volume_mm3"])
        require(row["volume_error_mm3"] <= tolerance["volume_mm3"], "Analytic material volume mismatch")
        row["bbox_error_mm"] = bbox_error(actual["bbox_mm"], board["display_bounds_mm"])
        require(row["bbox_error_mm"] <= tolerance["linear_mm"], "Actual board bbox mismatch")
        row["measured_thickness_mm"] = actual["bbox_mm"][1][2]-actual["bbox_mm"][0][2]
        require(abs(row["measured_thickness_mm"]-card["thickness_mm"]) <= tolerance["linear_mm"], "Thickness mismatch")
        cylinders, planes = kernel.surfaces(body)
        row["actual_cylindrical_surfaces"] = cylinders
        T = spec["T_DISPLAY_LOCAL_mm"]
        z0, z1 = board["display_bounds_mm"][0][2], board["display_bounds_mm"][1][2]
        thickness = card["thickness_mm"]
        used_faces = set()
        for source in card["mounting_holes"]:
            # Independent direct calculation of source XY reflection and display T.
            x = source["center_pcb_mm"][0]+T[0][3]
            y = -source["center_pcb_mm"][1]+T[1][3]
            diameter = source["drill_mm"][0]
            hole = dict(reference=source["reference"], source_line=source["source_line"], source_pad_type=source["pad_type"],
                source_role_evidence=source["role_evidence"], source_center_pcb_mm=source["center_pcb_mm"],
                expected_center_display_mm=[x, y, z0], expected_diameter_mm=diameter, status="RUNNING")
            row["holes"].append(hole)
            try:
                candidates = [face for face in cylinders if
                    abs(face["axis_dir"][2]) >= 1-1e-10 and
                    math.hypot(face["axis_point_mm"][0]-x, face["axis_point_mm"][1]-y) <= tolerance["linear_mm"] and
                    abs(face["diameter_mm"]-diameter) <= tolerance["linear_mm"]]
                hole["matching_actual_faces"] = candidates
                require(len(candidates) == 1, "Hole cylindrical wall missing/ambiguous; no guessed seam merging")
                wall = candidates[0]
                require(wall["face_index"] not in used_faces, "Actual cylinder assigned to multiple source holes")
                used_faces.add(wall["face_index"])
                expected_area = math.pi*diameter*thickness
                hole["wall_area_error_mm2"] = abs(wall["area_mm2"]-expected_area)
                hole["wall_z_end_error_mm"] = max(abs(wall["bbox_mm"][0][2]-z0), abs(wall["bbox_mm"][1][2]-z1))
                require(hole["wall_area_error_mm2"] <= tolerance["area_mm2"], "Hole wall not a complete through-cylinder")
                require(hole["wall_z_end_error_mm"] <= tolerance["linear_mm"], "Hole wall does not span source thickness")
                hole["axis_void_samples"] = [dict(z_mm=z0+fraction*thickness,
                    inside_material=bool(body.is_inside((x, y, z0+fraction*thickness), tolerance=tolerance["linear_mm"])))
                    for fraction in (0.1, 0.5, 0.9)]
                require(not any(p["inside_material"] for p in hole["axis_void_samples"]), "Cylinder is material at its axis, not a hole")
                hole["status"] = "PASS"
            except Exception as exc:
                hole.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
        require(len(used_faces) == len(card["mounting_holes"]) and all(h["status"] == "PASS" for h in row["holes"]),
                "Not all source mechanical holes passed")
        # Also retain actual top/bottom planar profiles and inner-wire count.
        # This checks that six Edge.Cuts cutouts were not lost as bbox rectangles.
        profile_expected_area = row["expected_volume_mm3"]/thickness
        expected_inner_wires = len(board["loops"])-1+len(card["mounting_holes"])
        row["planar_end_faces"] = []
        for label, z in (("bottom", z0), ("top", z1)):
            matches = [p for p in planes if max(abs(p["bbox_mm"][j][2]-z) for j in (0, 1)) <= tolerance["linear_mm"]]
            item = dict(end=label, expected_z_mm=z, matches=matches, expected_area_mm2=profile_expected_area,
                        expected_inner_wire_count=expected_inner_wires)
            row["planar_end_faces"].append(item)
            require(len(matches) == 1, "Missing/split/ambiguous board planar end")
            require(abs(matches[0]["area_mm2"]-profile_expected_area) <= tolerance["area_mm2"], "Planar material area mismatch")
            require(matches[0]["inner_wire_count"] == expected_inner_wires, "Missing/additional actual inner cutouts/drills")
        row["status"] = "PASS"
    except Exception as exc:
        row["status"] = "FAIL"
        row["errors"].append(f"{type(exc).__name__}: {exc}")
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=Path, default=STEP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output, step = args.output.resolve(), args.step.resolve()
    require(output.is_relative_to((RUN/"results").resolve()), "Output must remain under run/results")
    require(not output.exists(), "Refuse overwrite; use --output with a new name for a later run")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(schema="WP07_PCB_REFERENCE_STEP_READBACK_V1", status="INCOMPLETE",
        started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), step_path=str(step), units="mm",
        classification="REFERENCE_UNSELECTED_BARE_PCB", boards=[], errors=[],
        source_sha256_before={}, source_sha256_after={}, source_files_unchanged=None,
        independent_geometry_readback=True, full_pointwise_edge_cuts_equivalence_proved=False,
        scope="Fresh actual STEP readback: unique world-bbox board match, closed valid positive solids, "
              "analytic material volume, thickness, source mechanical hole wall axes/diameters/full thickness, "
              "top/bottom profile area and number of inner wires. No CAD generator is invoked.",
        limitations=["Expected source profile extraction shares pure computation with the generator; not algorithmically independent.",
            "Matching bbox, volume, planar area and loop count is not full pointwise Edge.Cuts/material equivalence.",
            "The 26 modeled mechanical drills are included in 3649 total pad/via records; 3623 are not modeled.",
            "Cylinder axes are additionally sampled at three depths to distinguish void from an external boss; no continuous Boolean hole-volume test is claimed.",
            "Populated component height, copper, plating, microholes, standoffs, spacecraft fit, wiring and selected hardware remain outside this reference model."],
        selected_hardware=False, populated_height_mm=None, energization_allowed=False,
        manufacturing_release=False, electrical_completion=False, physical_assembly_fit_pass=False,
        fit_holds_unchanged=True, cad_cache_write=False, generator_called=False, snapshot_reviewed=False)
    # Reserve only our new report; preserve any previous run unchanged.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    try:
        bind(__file__, report["source_sha256_before"])
        contract, boards = expected_inputs(report)
        report["step_sha256"] = bind(step, report["source_sha256_before"])
        require(step.stat().st_size > 0, "Empty STEP")
        kernel = Kernel()
        report["runtime"] = kernel.runtime
        bodies, assembly_facts = kernel.load(step)
        report["actual_assembly"] = assembly_facts
        actual = [kernel.solid_facts(body) for body in bodies]
        report["actual_solid_inventory"] = actual
        require(assembly_facts["root_is_valid"], "Actual STEP root invalid")
        require(assembly_facts["solid_count"] == 4, "Actual STEP must contain exactly four solids")
        require(assembly_facts["free_faces_without_solid"] == 0 and assembly_facts["free_edges_without_face"] == 0,
                "Unexpected sheets/free edges in STEP")
        matches = unique_bbox_match([a["bbox_mm"] for a in actual], boards, contract["numerical_tolerances"]["linear_mm"])
        report["unique_board_match"] = matches
        for board, match in zip(boards, matches):
            i = match["actual_solid_index"]
            report["boards"].append(check_board(kernel, bodies[i], actual[i], board, match, contract["numerical_tolerances"]))
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        report["counts"] = dict(boards_checked=len(report["boards"]),
            boards_pass=sum(b["status"] == "PASS" for b in report["boards"]),
            mechanical_holes_checked=sum(len(b["holes"]) for b in report["boards"]),
            mechanical_holes_pass=sum(h["status"] == "PASS" for b in report["boards"] for h in b["holes"]))
        passed = report["counts"]["boards_pass"] == 4 and report["counts"]["mechanical_holes_pass"] == 26
        report["status"] = "PASS" if passed else "FAIL"
    except Incomplete as exc:
        report["status"] = "INCOMPLETE"
        report["errors"].append(str(exc))
    except Exception as exc:
        report["status"] = "FAIL"
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["traceback"] = traceback.format_exc()
    finally:
        after = {p: sha(p) if Path(p).is_file() else None for p in report["source_sha256_before"]}
        report["source_sha256_after"] = after
        report["source_files_unchanged"] = after == report["source_sha256_before"]
        if not report["source_files_unchanged"]:
            report["status"] = "FAIL"
            report["errors"].append("An actual input/script/STEP changed during readback")
        report["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(dict(status=report["status"], counts=report.get("counts"), output=str(output),
                         output_sha256=sha(output), errors=report["errors"]), ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
