"""WP07 guide end capture candidate. Explicit calls only; import performs no CAD.

Root must execute under the run's memory/time guard. Source STEP parts remain
immutable. All returned geometry is in the inherited mast frame, millimetres.
Threads, material, preload, locking and load qualification remain UNKNOWN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = RUN / "inputs/RETENTION_DESIGN_CONTRACT.json"
CADGEN = Path("F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_contract(path=None):
    path = Path(path or DEFAULT_CONTRACT).resolve()
    c = json.loads(path.read_text(encoding="utf-8-sig"))
    if c["schema"] != "WP07_RETENTION_GUIDE_END_DESIGN_V1":
        raise ValueError("Unsupported design contract")
    for source, digest in c["source_inputs"].items():
        if sha(source) != digest:
            raise ValueError("Frozen input changed: " + source)
    for name, value in c["parameters"].items():
        if isinstance(value, (int, float)) and not math.isfinite(value):
            raise ValueError("Nonfinite parameter: " + name)
    return c, path


def _cad():
    sys.path.insert(0, str(CADGEN))
    import cadgen  # font guard before any build123d import
    # The cadgen scene reader writes sidecar caches; frozen source STEP is pure-read.
    from build123d import Solid, Plane, Location, import_step, export_step
    return Solid, Plane, Location, import_step, export_step


def build_station(station_index, contract_path=None):
    """Return {parts, metadata, placements}; creates geometry only when called.

    parts maps replacement/or new instance IDs to shapes in mast-local frame.
    placements maps state names to frozen millimetre T_S_mast matrices. Replace
    old IDs; do not append duplicate old mast/guide instances to the assembly.
    """
    c, cp = read_contract(contract_path)
    st = c["stations"][str(int(station_index))]
    p = c["parameters"]
    Solid, Plane, Location, import_step, _ = _cad()

    def cylinder(d, z0, z1, x=0, y=0):
        if z1 <= z0:
            raise ValueError("Cylinder interval must increase")
        return Solid.make_cylinder(d/2, z1-z0, Plane(origin=(x, y, z0)))

    def box(x0, x1, y0, y1, z0, z1):
        return Solid.make_box(x1-x0, y1-y0, z1-z0, Plane(origin=(x0, y0, z0)))

    def source(instance):
        row = st["states"]["parking"]["sources"][instance]
        if sha(row["path"]) != row["sha256"]:
            raise ValueError("Source STEP hash mismatch: " + instance)
        tree = import_step(row["path"])
        intrinsic = tree.global_location
        detached = type(tree)(tree.wrapped)
        if detached.parent is not None or getattr(detached, "children", ()):
            raise RuntimeError("Unsafe STEP hierarchy detachment")
        result = detached.located(intrinsic)
        if not result.is_valid or len(result.solids()) != 1:
            raise RuntimeError("Source must be one valid solid: " + instance)
        return result

    k = int(station_index)
    hi = st["guide_top_local_z_mm"]
    lo = hi - p["effective_guide_length_mm"]
    ear_h = p["ear_thickness_mm"]
    play = p["axial_capture_play_mm"]
    ear_z = [(lo, lo+ear_h), (hi-play-ear_h, hi-play)]
    mast_id = f"hold_fold_mast_{k}"
    mast = source(mast_id)
    for x in p["guide_axis_x_mm"]:
        xa, xb = ((p["ear_inner_x_abs_mm"], p["ear_outer_x_abs_mm"])
                  if x > 0 else (-p["ear_outer_x_abs_mm"], -p["ear_inner_x_abs_mm"]))
        for z0, z1 in ear_z:
            mast = mast + box(xa, xb, -p["ear_width_y_mm"]/2, p["ear_width_y_mm"]/2, z0, z1)
    for x in p["guide_axis_x_mm"]:
        for z0, z1 in ear_z:
            mast = mast - cylinder(p["guide_clearance_hole_d_mm"], z0-1, z1+1, x)
    parts = {mast_id: mast}
    provenance = {mast_id: {"kind": "REPLACEMENT_INTEGRAL_EARS", "source_id": mast_id}}
    for x in p["guide_axis_x_mm"]:
        key = str(int(x))
        rod_id = f"hold_shoe_guide_{k}_{key}"
        rod = source(rod_id)
        rod = rod + cylinder(p["lower_head_d_mm"], lo-p["lower_head_h_mm"], lo, x)
        rod = rod - cylinder(p["guide_thread_pilot_d_mm"], hi-p["guide_thread_pilot_depth_mm"], hi+1, x)
        parts[rod_id] = rod
        wh = p["retaining_washer_h_mm"]
        washer_id = f"WP07_guide_washer_{k}_{key}"
        washer = cylinder(p["retaining_washer_od_mm"], hi, hi+wh, x)
        washer = washer - cylinder(p["retaining_washer_id_mm"], hi-1, hi+wh+1, x)
        parts[washer_id] = washer
        screw_id = f"WP07_guide_screw_{k}_{key}"
        uh = hi+wh
        ht = uh+p["retaining_screw_head_h_mm"]
        screw = cylinder(p["retaining_screw_shank_d_mm"], uh-p["retaining_screw_underhead_length_mm"], uh, x)
        screw = screw + cylinder(p["retaining_screw_head_d_mm"], uh, ht, x)
        # Round driver socket is a declared candidate envelope, not ISO hex detail.
        screw = screw - cylinder(p["retaining_screw_socket_d_mm"], ht-p["retaining_screw_socket_depth_mm"], ht+1, x)
        parts[screw_id] = screw
        provenance[rod_id] = {"kind": "REPLACEMENT_HEADED_GUIDE", "source_id": rod_id}
        provenance[washer_id] = {"kind": "NEW_CUSTOM_NOMINAL_WASHER", "source_id": None}
        provenance[screw_id] = {"kind": "NEW_NOMINAL_SCREW_UNQUALIFIED_THREAD", "source_id": None}
    for instance, shape in parts.items():
        if not shape.is_valid or len(shape.solids()) != 1 or shape.volume <= 0:
            raise RuntimeError("Generated candidate is not one valid positive solid: " + instance)
    metadata = dict(schema="WP07_RETENTION_DETAIL_EMISSION_V1", status="CAD_CANDIDATE_NOT_VALIDATED",
                    station_index=k, contract_path=str(cp), contract_sha256=sha(cp),
                    producer_path=str(Path(__file__).resolve()), producer_sha256=sha(__file__),
                    parameters=p, guide_effective_interval_local_mm=[lo, hi],
                    headed_rod_total_length_mm=p["effective_guide_length_mm"]+p["lower_head_h_mm"],
                    assembly_envelope_axial_interval_local_mm=[lo-p["lower_head_h_mm"], hi+p["retaining_washer_h_mm"]+p["retaining_screw_head_h_mm"]],
                    provenance=provenance, source_inputs=c["source_inputs"],
                    caveat="Nominal captive geometry. True thread/strength/locking and whole-retention physical release remain UNKNOWN.")
    return dict(parts=parts, metadata=metadata,
                placements={state: row["T_S_mast"] for state, row in st["states"].items()})


def export_station(station_index, contract_path=None, output_dir=None):
    built = build_station(station_index, contract_path)
    *_, export_step = _cad()
    dest = Path(output_dir or RUN / f"results/retention_detail/station_{int(station_index)}").resolve()
    dest.mkdir(parents=True, exist_ok=True)
    rows = {}
    for instance, shape in built["parts"].items():
        path = dest / (instance + ".step")
        shape.label = instance
        export_step(shape, path)
        box = shape.bounding_box()
        replacement = built["metadata"]["provenance"][instance]["source_id"] is not None
        rows[instance] = dict(path=str(path), sha256=sha(path),
                              representation_role="PHYSICAL_GEOMETRY" if replacement else "SIMPLIFIED_PROXY",
                              product_role="MODIFIED_SOURCE_GEOMETRY" if replacement else "CUSTOM_NOMINAL_GEOMETRY",
                              geometry_status="NOMINAL_CANDIDATE_UNQUALIFIED",
                              actual_mass_kg=None,
                              local_bbox_mm=dict(min_mm=list(box.min), max_mm=list(box.max)),
                              T_S_local_by_state=built["placements"],
                              **built["metadata"]["provenance"][instance])
    receipt = {**built["metadata"], "parts": rows, "placements": built["placements"]}
    path = dest / "EMISSION_RECEIPT.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", type=int, choices=(0, 1), required=True)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(export_station(args.station, args.contract, args.output_dir))
