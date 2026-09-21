"""Reference PCB mechanical profiles only; importing this module does not load CAD.

Includes all source Edge.Cuts and 26 proven mounting/board-outline drills. The
other 3,623 pad/via drills, copper, plating, components and laminate details are
not modeled. These four boards remain REFERENCE_UNSELECTED_BARE_PCB; this is
neither a manufacturing PCB nor selected spacecraft electrical hardware.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
CONTRACT = RUN / "inputs/pcb_reference_contract.json"
CADGEN = Path("F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _load_parser(path):
    # Project-owned static KiCad parser. Its main() writes ECAD results and is
    # deliberately never called here. No KiCad or third-party source execution.
    spec = importlib.util.spec_from_file_location("wp07_pcb_reference_static_ecad", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _arc_mid(edge):
    center = edge["center_mm"]
    start = edge["start_mm"]
    a = math.atan2(start[1]-center[1], start[0]-center[0])
    a += math.radians(edge["sweep_deg"])/2
    r = edge["radius_mm"]
    return [center[0]+r*math.cos(a), center[1]+r*math.sin(a)]


def ordered_loops(edges, tolerance):
    """Sequence every source line/arc exactly once without snapping coordinates.

    Multiple loops are preserved. Largest enclosed area is the outer candidate;
    CAD must subsequently prove that all other loops are proper inner cutouts.
    Unsupported geometry, a branch, gap or ambiguous endpoint raises immediately.
    """
    require(bool(edges), "NOT_BUILT: no Edge.Cuts")
    for edge in edges:
        require(edge["kind"] in ("gr_line", "gr_arc"), "NOT_BUILT: unsupported Edge.Cuts kind")
        points = [edge["start_mm"], edge["end_mm"]]
        require(all(len(p) == 2 and all(math.isfinite(v) for v in p) for p in points), "Nonfinite edge")
        require(math.dist(*points) > tolerance, "Degenerate edge")
        if edge["kind"] == "gr_arc":
            c, r, sweep = edge["center_mm"], edge["radius_mm"], edge["sweep_deg"]
            require(math.isfinite(r) and r > 0 and 0 < abs(sweep) < 360, "Unsupported arc")
            require(max(abs(math.dist(p, c)-r) for p in points) <= tolerance, "Arc endpoint/radius mismatch")
            a = math.atan2(points[0][1]-c[1], points[0][0]-c[0])+math.radians(sweep)
            require(math.dist(points[1], [c[0]+r*math.cos(a), c[1]+r*math.sin(a)]) <= tolerance,
                    "Arc endpoint/sweep mismatch")
    for i, edge in enumerate(edges):
        for point in (edge["start_mm"], edge["end_mm"]):
            degree = sum(math.dist(point, other[k]) <= tolerance for other in edges
                         for k in ("start_mm", "end_mm"))
            require(degree == 2, f"NOT_BUILT: ambiguous/open Edge.Cuts at edge {i}")
    unused = set(range(len(edges)))
    loops = []
    while unused:
        index = min(unused)
        unused.remove(index)
        chain = [(index, False)]
        start, end = edges[index]["start_mm"], edges[index]["end_mm"]
        while math.dist(start, end) > tolerance:
            matches = [(j, rev) for j in unused for rev in (False, True)
                       if math.dist(end, edges[j]["end_mm" if rev else "start_mm"]) <= tolerance]
            require(len(matches) == 1, "NOT_BUILT: unclosed/branching Edge.Cuts")
            index, reverse = matches[0]
            unused.remove(index)
            chain.append((index, reverse))
            end = edges[index]["start_mm" if reverse else "end_mm"]
        terms = []
        for index, reverse in chain:
            edge = edges[index]
            s, e = edge["start_mm"], edge["end_mm"]
            term = s[0]*e[1]-s[1]*e[0]
            if edge["kind"] == "gr_arc":
                c = edge["center_mm"]
                term = c[0]*(e[1]-s[1])-c[1]*(e[0]-s[0])
                term += edge["radius_mm"]**2*math.radians(edge["sweep_deg"])
            terms.append((-1 if reverse else 1)*term/2)
        area = math.fsum(terms)
        require(abs(area) > tolerance*tolerance, "NOT_BUILT: zero enclosed area")
        loops.append(dict(edges=[dict(index=i, reverse=r) for i, r in chain],
                          source_signed_area_mm2=area))
    outer = max(range(len(loops)), key=lambda i: abs(loops[i]["source_signed_area_mm2"]))
    for i, loop in enumerate(loops):
        loop["role"] = "OUTER_CANDIDATE" if i == outer else "INNER_CUTOUT_CANDIDATE"
    return loops


def source_xy_to_local(point):
    # Preserve the source PCB origin. Flip source screen Y-down to CAD Y-up.
    # This is a documented 2D axis conversion, NOT a rigid 3D placement matrix.
    return (point[0], -point[1], 0.0)


def preflight(contract_path=None):
    """Standard-library-only source binding and profile checks; no CAD acceptance."""
    cp = Path(contract_path or CONTRACT).resolve()
    c = json.loads(cp.read_text(encoding="utf-8-sig"))
    require(c["schema"] == "WP07_PCB_REFERENCE_MECHANICAL_SOURCE_V1", "Unsupported contract")
    require(c["units"] == "mm" and c["classification"] == "REFERENCE_UNSELECTED_BARE_PCB", "Scope changed")
    require(c["selected_hardware"] is False and c["manufacturing_release"] is False, "Invalid reference scope")
    for path, digest in c["source_inputs"].items():
        require(sha(path) == digest, "Frozen source SHA mismatch: " + path)
    parser = _load_parser(c["static_parser_path"])
    cards = json.loads(Path(c["reference_cards_path"]).read_text(encoding="utf-8-sig"))["boards"]
    by_id = {card["id"]: card for card in cards}
    require(len(c["boards"]) == 4 and len({b["id"] for b in c["boards"]}) == 4, "Expected four unique boards")
    board_data = []
    for spec in c["boards"]:
        card = by_id[spec["id"]]
        require(spec["source_pcb_path"] == card["pcb_path"] and spec["source_pcb_sha256"] == card["pcb_sha256"],
                "Contract PCB identity changed")
        require(spec["source_thickness_mm"] == card["thickness_mm"] and spec["source_thickness_line"] == card["thickness_source_line"],
                "Contract thickness source changed")
        require(card["selected_for_wp07"] is False and card["populated_height_mm"] is None, "Selection scope changed")
        actual = parser.pcb_card(Path(card["pcb_path"]), Path(card["schematic_path"]), card["id"])
        for field in ("pcb_sha256", "schematic_sha256", "outline", "mounting_holes", "thickness_mm", "thickness_source_line"):
            require(actual[field] == card[field], f"Re-extraction mismatch: {card['id']} {field}")
        require(card["outline"]["static_outline_complete"], "NOT_BUILT: incomplete source outline")
        thickness = card["thickness_mm"]
        require(math.isfinite(thickness) and thickness > 0, "NOT_BUILT: missing/invalid thickness")
        loops = ordered_loops(card["outline"]["edges"], c["numerical_tolerances"]["source_endpoint_mm"])
        require(len(card["outline"]["edges"]) == spec["all_edge_cuts_records"], "Edge.Cuts count changed")
        require(len(loops) == spec["expected_closed_loops"], "Loop count changed")
        holes = card["mounting_holes"]
        require(len(holes) == spec["modeled_mounting_or_outline_drills"], "Hole count changed")
        tree = parser.parse_sexpr(Path(card["pcb_path"]))
        fps = parser.children(tree, "module")+parser.children(tree, "footprint")
        drilled = [(fp, pad) for fp in fps for pad in parser.children(fp, "pad") if parser.one(pad, "drill")]
        vias = parser.children(tree, "via")
        require(len(drilled) == spec["all_pad_drill_records"] and len(vias) == spec["all_via_records"], "Drill count changed")
        require(spec["unmodeled_drill_records"] == len(drilled)+len(vias)-len(holes), "Unmodeled drill count mismatch")
        for hole in holes:
            require(not hole["slot"] and len(hole["drill_mm"]) == 1 and hole["drill_mm"][0] > 0,
                    "NOT_BUILT: only explicit circular mechanical drills supported")
            matches = [(fp, pad) for fp, pad in drilled if pad.line == hole["source_line"]]
            require(len(matches) == 1, "Hole source line missing/ambiguous")
            fp, pad = matches[0]
            drill = parser.one(pad, "drill")
            require(len(drill) == 2 and float(drill[1]) == hole["drill_mm"][0],
                    "NOT_BUILT: offset/slot/unsupported drill must not be guessed")
            require(fp.line == hole["footprint_line"], "Hole footprint owner changed")
        transform = spec["T_DISPLAY_LOCAL_mm"]
        require(len(transform) == 4 and all(len(row) == 4 for row in transform), "Bad display matrix")
        require(all(math.isfinite(v) for row in transform for v in row), "Nonfinite display matrix")
        require(all(transform[i][j] == (1 if i == j else 0) for i in range(4) for j in range(4) if j < 3 or i == 3),
                "Only documented identity-rotation display translations allowed")
        lower, upper = card["outline"]["bounds_mm"]
        local_bounds = [[lower[0], -upper[1], 0.0], [upper[0], -lower[1], thickness]]
        world_bounds = [[row[i]+transform[i][3] for i in range(3)] for row in local_bounds]
        require(max(abs(world_bounds[0][i]-spec["display_xy_min_mm"][i]) for i in range(2)) < 1e-8,
                "Display placement doesn't match intended board minimum")
        outer_area = max(abs(l["source_signed_area_mm2"]) for l in loops)
        profile_area = 2*outer_area-math.fsum(abs(l["source_signed_area_mm2"]) for l in loops)
        hole_area = math.fsum(math.pi*(h["drill_mm"][0]/2)**2 for h in holes)
        require(profile_area > hole_area, "NOT_BUILT: nonpositive board area")
        board_data.append(dict(spec=spec, card=card, loops=loops, local_bounds_mm=local_bounds,
            display_bounds_mm=world_bounds, profile_area_mm2=profile_area,
            expected_modeled_material_volume_mm3=(profile_area-hole_area)*thickness))
        del tree, fps, drilled, vias
    require(sum(len(b["card"]["mounting_holes"]) for b in board_data) == 26, "Modeled mechanical drill scope changed")
    require(sum(b["spec"]["all_pad_drill_records"]+b["spec"]["all_via_records"] for b in board_data) == 3649,
            "Total source drill scope changed")
    require(sum(b["spec"]["unmodeled_drill_records"] for b in board_data) == 3623, "Unmodeled drill scope changed")
    for i, a in enumerate(board_data):
        for b in board_data[i+1:]:
            gaps = [max(a["display_bounds_mm"][0][k]-b["display_bounds_mm"][1][k],
                        b["display_bounds_mm"][0][k]-a["display_bounds_mm"][1][k]) for k in (0, 1)]
            require(max(gaps) >= c["display_minimum_separation_mm"]-1e-8, "Display boards overlap or spacing changed")
    for path, digest in c["source_inputs"].items():
        require(sha(path) == digest, "Source changed during preflight: " + path)
    return c, board_data, dict(schema="WP07_PCB_REFERENCE_STATIC_PREFLIGHT_V1",
        status="STATIC_SOURCE_PROFILE_CHECKS_PASS_CAD_NOT_EXECUTED", contract_path=str(cp),
        contract_sha256=sha(cp), helper_path=str(Path(__file__).resolve()), helper_sha256=sha(__file__),
        source_hashes=c["source_inputs"], classification=c["classification"],
        modeled_drills=26, all_pad_drill_and_via_records=3649, unmodeled_drill_records=3623,
        all_record_count_includes_modeled_26=True, geometry_validated=False,
        boards=[{k: v for k, v in board.items() if k not in ("card", "spec")} | {"id": board["card"]["id"]}
                for board in board_data])


def _cad():
    sys.path.insert(0, str(CADGEN))
    import cadgen  # font guard must precede build123d/OCP imports
    from build123d import Edge, Wire, Face, Solid, Plane, Location
    from cadgen.assembly import AssemblyHelper
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    return cadgen, Edge, Wire, Face, Solid, Plane, Location, AssemblyHelper, BRepAdaptor_Surface, GeomAbs_Cylinder


def build_reference_set(contract_path=None):
    """Explicit CAD call: returns (four-board display compound, actual build facts).

    No files are written. Root owns gen --write, independent STEP readback and
    snapshots. An assertion failure aborts the entire set; there is no bbox proxy.
    """
    c, boards, receipt = preflight(contract_path)
    cadgen, Edge, Wire, Face, Solid, Plane, Location, AssemblyHelper, Surface, CYL = _cad()
    t = c["numerical_tolerances"]
    asm = AssemblyHelper("REFERENCE_UNSELECTED_BARE_PCB")

    def volume(shape):
        return 0.0 if shape is None else math.fsum(s.volume for s in shape.solids())

    def bounds(shape):
        b = shape.bounding_box()
        return [list(b.min), list(b.max)]

    def check_shape(shape, expected_volume, expected_bounds, stage):
        require(shape is not None and shape.is_valid and len(shape.solids()) == 1, "Invalid/non-single solid: " + stage)
        # BRep validity + closed shell(s) + positive volume is required. Do not
        # infer physical laminate, material properties or manufacturing acceptance.
        from OCP.BRep import BRep_Tool
        shells = shape.shells()
        require(bool(shells) and all(BRep_Tool.IsClosed_s(shell.wrapped) for shell in shells), "Open/missing shell: " + stage)
        actual_volume = volume(shape)
        require(actual_volume > 0 and abs(actual_volume-expected_volume) <= t["volume_mm3"], "Volume mismatch: " + stage)
        actual_bounds = bounds(shape)
        require(max(abs(actual_bounds[j][i]-expected_bounds[j][i]) for j in (0, 1) for i in range(3)) <= t["linear_mm"],
                "Board bounds/thickness mismatch: " + stage)
        return dict(is_valid=True, closed_shells=True, solid_count=1, volume_mm3=actual_volume,
                    bbox_mm=actual_bounds, volume_error_mm3=abs(actual_volume-expected_volume))

    actual_boards = []
    for board in boards:
        card, spec = board["card"], board["spec"]
        edges = card["outline"]["edges"]
        wires = []
        for loop in board["loops"]:
            # Reflection reverses orientation. Force outer CCW and inner CW in
            # CAD XY without changing any coordinates or curve definitions.
            ordered = [(item["index"], item["reverse"]) for item in loop["edges"]]
            want_positive = loop["role"] == "OUTER_CANDIDATE"
            if (-loop["source_signed_area_mm2"] > 0) != want_positive:
                ordered = [(i, not reverse) for i, reverse in reversed(ordered)]
            cad_edges = []
            for index, reverse in ordered:
                edge = edges[index]
                first, last = edge["start_mm"], edge["end_mm"]
                if reverse:
                    first, last = last, first
                if edge["kind"] == "gr_line":
                    obj = Edge.make_line(source_xy_to_local(first), source_xy_to_local(last))
                else:
                    obj = Edge.make_three_point_arc(source_xy_to_local(first), source_xy_to_local(_arc_mid(edge)), source_xy_to_local(last))
                cad_edges.append(obj)
            wire = Wire(cad_edges)
            require(wire.is_closed and wire.is_valid, "CAD Edge.Cuts wire invalid: " + card["id"])
            wires.append((loop["role"], wire))
        outer = next(w for role, w in wires if role == "OUTER_CANDIDATE")
        inner = [w for role, w in wires if role != "OUTER_CANDIDATE"]
        face = Face(outer, inner)
        require(face.is_valid and len(face.inner_wires()) == len(inner), "Invalid/nested/missing profile cutout")
        require(abs(face.area-board["profile_area_mm2"]) <= t["area_mm2"], "Actual profile area mismatch")
        thickness = card["thickness_mm"]
        body = Solid.extrude(face, (0, 0, thickness))
        check_shape(body, board["profile_area_mm2"]*thickness, board["local_bounds_mm"], card["id"]+" before drills")
        hole_facts = []
        for hole in card["mounting_holes"]:
            x, y, _ = source_xy_to_local(hole["center_pcb_mm"])
            radius = hole["drill_mm"][0]/2
            tool = Solid.make_cylinder(radius, thickness+2, Plane(origin=(x, y, -1)))
            expected_removed = math.pi*radius*radius*thickness
            before = volume(body & tool)
            require(abs(before-expected_removed) <= t["volume_mm3"], "Mechanical hole not fully inside source material")
            body = body-tool
            require(body.is_valid and len(body.solids()) == 1, "Drill produced invalid/multiple solid")
            after = volume(body & tool)
            require(after <= t["volume_mm3"], "Actual hole cylinder still intersects board material")
            hole_facts.append(dict(source_line=hole["source_line"], reference=hole["reference"],
                pad_type=hole["pad_type"], role_evidence=hole["role_evidence"],
                center_source_xy_mm=hole["center_pcb_mm"], center_local_xy_mm=[x, y],
                source_diameter_mm=2*radius, removed_material_mm3=before, remaining_material_mm3=after))
        local_facts = check_shape(body, board["expected_modeled_material_volume_mm3"], board["local_bounds_mm"], card["id"])
        for hole in hole_facts:
            matches = []
            for cylinder_face in body.faces():
                surf = Surface(cylinder_face.wrapped, True)
                if surf.GetType() != CYL:
                    continue
                cylinder = surf.Cylinder()
                p, axis = cylinder.Axis().Location(), cylinder.Axis().Direction()
                if (abs(axis.Z()) >= 1-1e-10 and abs(p.X()-hole["center_local_xy_mm"][0]) <= t["linear_mm"]
                        and abs(p.Y()-hole["center_local_xy_mm"][1]) <= t["linear_mm"]
                        and abs(2*cylinder.Radius()-hole["source_diameter_mm"]) <= t["linear_mm"]):
                    matches.append(dict(diameter_mm=2*cylinder.Radius(), axis_point_mm=[p.X(), p.Y(), p.Z()],
                                        area_mm2=cylinder_face.area, bbox_mm=bounds(cylinder_face)))
            require(len(matches) == 1, "Actual hole cylindrical wall missing/ambiguous")
            wall = matches[0]
            require(abs(wall["area_mm2"]-math.pi*hole["source_diameter_mm"]*thickness) <= t["area_mm2"],
                    "Actual hole wall is not a complete through-cylinder")
            require(abs(wall["bbox_mm"][0][2]) <= t["linear_mm"] and abs(wall["bbox_mm"][1][2]-thickness) <= t["linear_mm"],
                    "Actual hole wall thickness mismatch")
            hole["actual_cylindrical_wall"] = wall
        # Each body is parentless until added; move in place avoids anytree copy.
        T = spec["T_DISPLAY_LOCAL_mm"]
        require(body.parent is None, "Unexpected parent before placement")
        body.move(Location((T[0][3], T[1][3], T[2][3])))
        display_facts = check_shape(body, board["expected_modeled_material_volume_mm3"], board["display_bounds_mm"], card["id"]+" display")
        asm.add(body, "REFERENCE_UNSELECTED_BARE_PCB", card["id"], color=cadgen.srgb(spec["display_color_srgb"]))
        actual_boards.append(dict(id=card["id"], source_pcb_path=card["pcb_path"], source_pcb_sha256=card["pcb_sha256"],
            thickness_source_line=card["thickness_source_line"], thickness_mm=thickness,
            local_facts=local_facts, display_facts=display_facts, actual_holes=hole_facts,
            closed_source_loops=len(wires), internal_edge_cuts=len(inner), T_DISPLAY_LOCAL_mm=T,
            selected_hardware=False, populated_height_mm=None, unmodeled_drill_records=spec["unmodeled_drill_records"]))
    for path, digest in c["source_inputs"].items():
        require(sha(path) == digest, "Source changed during CAD build: " + path)
    receipt.update(status="IN_MEMORY_MECHANICAL_REFERENCE_GEOMETRY_CHECKS_PASS", geometry_validated=True,
        step_readback_validated=False, snapshot_reviewed=False, actual_boards=actual_boards,
        source_files_unchanged=True, manufacturing_release=False, electrical_completion=False,
        populated_height_mm=None, spacecraft_placement_assigned=False)
    return asm.build(), receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-check", action="store_true", required=True)
    args = parser.parse_args()
    if args.static_check:
        print(json.dumps(preflight()[2], ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
