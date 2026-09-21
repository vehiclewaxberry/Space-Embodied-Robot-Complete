"""Hash-bound, no-CAD AABB cross-check of generated retention vs WP06 delta.

An axis-separated enclosing AABB proves separation. Overlap is NEEDS_BREP,
never collision or a geometric pass. Nothing is emitted from model source.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

RUN = Path(__file__).resolve().parents[1]
STATES = ("parking", "released", "service")


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


def rigid(value):
    require(isinstance(value, list) and len(value) == 4 and
            all(isinstance(row, list) and len(row) == 4 for row in value), "Expected 4x4 matrix")
    T = [[float(v) for v in row] for row in value]
    require(all(math.isfinite(x) for row in T for x in row), "Nonfinite matrix")
    require(max(abs(T[3][i] - int(i == 3)) for i in range(4)) <= 1e-12, "Invalid homogeneous row")
    require(max(abs(math.fsum(T[k][i] * T[k][j] for k in range(3)) - int(i == j))
                for i in range(3) for j in range(3)) <= 1e-10, "Matrix is not rigid")
    det = (T[0][0] * (T[1][1]*T[2][2] - T[1][2]*T[2][1])
           - T[0][1] * (T[1][0]*T[2][2] - T[1][2]*T[2][0])
           + T[0][2] * (T[1][0]*T[2][1] - T[1][1]*T[2][0]))
    require(abs(det - 1) <= 1e-10, "Matrix includes reflection/scale")
    return T


def bounds(value):
    require(isinstance(value, dict), "Missing actual bounds")
    a, b = value.get("min_mm"), value.get("max_mm")
    require(isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 3,
            "Expected finite 3D mm bounds")
    a, b = list(map(float, a)), list(map(float, b))
    require(all(math.isfinite(v) for v in a + b), "Nonfinite bounds")
    require(all(a[i] < b[i] for i in range(3)), "Nonpositive solid bounds")
    if "size_mm" in value:
        require(len(value["size_mm"]) == 3 and all(abs(float(value["size_mm"][i])-(b[i]-a[i])) <= 1e-7
                for i in range(3)), "Bounds size inconsistent")
    return dict(min_mm=a, max_mm=b, size_mm=[b[i]-a[i] for i in range(3)])


def world_bounds(local, T):
    local, T = bounds(local), rigid(T)
    points = [[math.fsum(T[i][j]*point[j] for j in range(3)) + T[i][3] for i in range(3)]
              for point in itertools.product(*zip(local["min_mm"], local["max_mm"]))]
    a, b = [min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]
    return bounds(dict(min_mm=a, max_mm=b))


def difference(a, b):
    a, b = bounds(a), bounds(b)
    return max(abs(a[k][i]-b[k][i]) for k in ("min_mm", "max_mm") for i in range(3))


def expected_retention_ids(k, p):
    return {f"hold_fold_mast_{k}",
            *[f"hold_shoe_guide_{k}_{int(x)}" for x in p["guide_axis_x_mm"]],
            *[f"WP07_guide_{role}_{k}_{int(x)}" for role in ("washer", "screw") for x in p["guide_axis_x_mm"]],
            *[f"WP07_lower_collar_{k}_{side}" for side in ("front", "rear")],
            *[f"WP07_lower_{role}_{k}_{int(x)}" for role in ("screw", "washer_outer", "washer_inner", "nut")
              for x in p["lower_collar_bolt_x_mm"]]}


def separation(a, b, tolerance):
    gaps = [max(b["min_mm"][i]-a["max_mm"][i], a["min_mm"][i]-b["max_mm"][i]) for i in range(3)]
    axes = ["XYZ"[i] for i in range(3) if gaps[i] > tolerance]
    return dict(status="SEPARATED_BY_AABB" if axes else "NEEDS_BREP",
                signed_axis_gaps_mm=gaps, separating_axes=axes,
                distance_lower_bound_mm=math.sqrt(math.fsum(max(0, x)**2 for x in gaps)),
                collision_conclusion="NO_COLLISION_BY_ENCLOSING_AABB" if axes else "NOT_DETERMINED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", choices=("0", "1", "all"), default="0")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    suffix = "ALL" if args.station == "all" else "STATION" + args.station
    output = (args.output or RUN / f"results/RETENTION_WP06_CROSS_{suffix}.json").resolve()
    require(output.is_relative_to((RUN / "results").resolve()), "Output must remain under run/results")
    require(not output.exists(), "Refuse overwrite; specify a new output for a later run")
    selected = (0, 1) if args.station == "all" else (int(args.station),)
    report = dict(schema="WP07_RETENTION_WP06_AABB_CROSS_V1", status="RUNNING",
        started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), units="mm", frame="S; +Z up",
        selected_stations=list(selected), source_sha256_before={}, source_sha256_after={},
        station_presence={}, stations={}, wp06_delta_world_bounds={}, comparisons=[],
        scope="Only generated retention parts versus 24 WP06 replaced/added parts in three static states. "
              "Enclosing AABB separation proves disjoint geometry; overlap needs BRep. No CAD kernel run. "
              "No coverage of other assembly parts, continuous paths, strength, physical assembly or manufacturing.",
        physical_assembly_completed=False, manufacturing_release=False, whole_system_collision_verified=False)
    snapshots = report["source_sha256_before"]
    def bind(path, expected=None):
        path = Path(path).resolve(); digest = sha(path)
        require(expected is None or digest.lower() == expected.lower(), "Source SHA mismatch: " + str(path))
        require(str(path) not in snapshots or snapshots[str(path)] == digest, "Input changed: " + str(path))
        snapshots[str(path)] = digest
        return digest
    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    save()
    try:
        bind(__file__)
        cp = RUN / "inputs/RETENTION_DESIGN_CONTRACT.json"; bind(cp); contract = read(cp)
        require(contract["schema"] == "WP07_RETENTION_GUIDE_END_DESIGN_V2" and contract["units"] == "mm",
                "Expected C02 millimetre contract")
        tolerance = float(contract["acceptance"]["linear_mm"])
        require(math.isfinite(tolerance) and tolerance > 0, "Missing positive contract linear tolerance")
        report["aabb_separation_padding_mm"] = tolerance
        for path, digest in contract["source_inputs"].items(): bind(path, digest)
        mp = RUN / "results/INTEGRATION_MANIFEST.json"; bind(mp); manifest = read(mp)
        require(manifest["units"] == "mm", "Integration units are not mm")
        changed, added = set(manifest["replaced_ids"]), set(manifest["added_ids"])
        require(len(changed) == 8 and len(added) == 16 and not changed & added, "Expected exact WP06 8+16 delta")
        delta_ids = changed | added
        local_ref = manifest["local_parts_receipt"]
        bind(local_ref["path"], local_ref["sha256"]); local = read(local_ref["path"])
        bind(local["source_path"], local["source_sha256"])
        report["wp06_delta_ids"] = sorted(delta_ids)
        for state in STATES:
            rows = manifest["states"][state]["instances"]
            by_id = {row["id"]: row for row in rows}
            require(len(rows) == len(by_id) == 597 and delta_ids <= set(by_id), "Integration instance set differs")
            report["wp06_delta_world_bounds"][state] = {}
            for name in sorted(delta_ids):
                row = by_id[name]; source = row["source_step"]; known = local["parts"][name]
                bind(source["path"], source["sha256"])
                require(known["sha256"] == source["sha256"] and
                        Path(known["path"]).resolve() == Path(source["path"]).resolve(), "WP06 source identity differs")
                facts = row["actual_source_facts"]
                require(facts["shape_valid"] is True and facts["solid_count"] == 1 and
                        math.isfinite(facts["volume_mm3"]) and facts["volume_mm3"] > 0, "WP06 actual facts invalid")
                require(difference(facts["bbox_mm"], known["facts"]["bbox_mm"]) <= tolerance,
                        "WP06 actual bounds differ from source readback receipt")
                world = world_bounds(facts["bbox_mm"], row["T_S_local"])
                require(difference(world, row["world_bounds_mm"]) <= tolerance and
                        difference(world, row["bounds_mm"]) <= tolerance, "WP06 world bounds or transform inconsistent")
                report["wp06_delta_world_bounds"][state][name] = dict(bbox_mm=world,
                    source_path=source["path"], source_sha256=source["sha256"],
                    T_S_local=row["T_S_local"], actual_source_bbox_mm=facts["bbox_mm"])
        for k in (0, 1):
            rp = RUN / f"results/retention_detail/station_{k}/EMISSION_RECEIPT.json"
            report["station_presence"][str(k)] = dict(receipt_path=str(rp),
                status="NOT_GENERATED" if not rp.is_file() else "SELECTED" if k in selected else "GENERATED_NOT_REQUESTED")
        for k in selected:
            rp = RUN / f"results/retention_detail/station_{k}/EMISSION_RECEIPT.json"
            if not rp.is_file():
                report["stations"][str(k)] = dict(status="NOT_GENERATED", geometry_used=False)
                continue
            bind(rp); emission = read(rp)
            require(emission["schema"] == "WP07_RETENTION_DETAIL_EMISSION_V2" and emission["station_index"] == k,
                    "Wrong generated station receipt")
            require(Path(emission["contract_path"]).resolve() == cp.resolve() and
                    emission["contract_sha256"] == snapshots[str(cp.resolve())], "Emission contract binding differs")
            bind(emission["producer_path"], emission["producer_sha256"])
            require(emission["parameters"] == contract["parameters"], "Generated parameters differ")
            require(set(emission["parts"]) == expected_retention_ids(k, contract["parameters"]) and
                    len(emission["parts"]) == contract["expected_local_output_per_station"]["total_parts"] == 17,
                    "Generated part set differs")
            # Existing independent actual STEP readback strengthens the emitted
            # shape-bound bbox. It is never recomputed from the producer source.
            check_path = rp.parent / "CHECK_local.json"
            actual_checks = None
            if check_path.is_file():
                bind(check_path); checks = read(check_path)
                require(Path(checks["receipt_path"]).resolve() == rp.resolve() and
                        checks["input_sha256"].get(str(rp.resolve())) == snapshots[str(rp.resolve())],
                        "Local STEP check not bound to this emission")
                actual_checks = {c["id"][6:]: c for c in checks["checks"] if c["id"].startswith("solid:")}
                require(set(actual_checks) == set(emission["parts"]), "Actual STEP facts missing")
            result = dict(status="MEASURED_AABB_INPUTS_BOUND", geometry_used=True, part_count=17,
                receipt_path=str(rp), receipt_sha256=snapshots[str(rp.resolve())],
                bounds_basis="Generated export receipt; matched independent STEP-readback facts" if actual_checks is not None
                            else "Generated export receipt bbox bound to actual STEP SHA; no independent readback facts available",
                state_world_bounds={})
            report["stations"][str(k)] = result
            for state in STATES:
                T = contract["stations"][str(k)]["states"][state]["T_S_mast"]
                rigid(T)
                require(emission["placements"][state] == T, "Emission mast transform differs")
                result["state_world_bounds"][state] = {}
                for name, part in emission["parts"].items():
                    bind(part["path"], part["sha256"])
                    require(Path(part["path"]).is_file() and Path(part["path"]).suffix.lower() in (".step", ".stp"),
                            "Actual generated STEP required")
                    require(part["T_S_local_by_state"][state] == T, "Part transform differs")
                    source_box = bounds(part["local_bbox_mm"])
                    if actual_checks is not None:
                        check = actual_checks[name]
                        require(check["status"] == "PASS" and check["shape_valid"] is True and check["solid_count"] == 1,
                                "Actual STEP readback solid is not valid")
                        require(checks["input_sha256"].get(str(Path(part["path"]).resolve())) == part["sha256"],
                                "Actual STEP check source SHA differs")
                        require(difference(source_box, check["bbox_mm"]) <= tolerance, "Emission/readback bbox differs")
                    world = world_bounds(source_box, T)
                    result["state_world_bounds"][state][name] = dict(bbox_mm=world, source_bbox_mm=source_box,
                        T_S_local=T, source_path=part["path"], source_sha256=part["sha256"])
                    for other in sorted(delta_ids):
                        other_row = report["wp06_delta_world_bounds"][state][other]
                        report["comparisons"].append(dict(station=k, state=state, retention_id=name, wp06_id=other,
                            retention_source_sha256=part["sha256"], wp06_source_sha256=other_row["source_sha256"],
                            **separation(world, other_row["bbox_mm"], tolerance)))
            require(sum(row["station"] == k for row in report["comparisons"]) == 17*24*3,
                    "Selected station pair coverage incomplete")
        report["source_sha256_after"] = {p: sha(p) for p in snapshots}
        require(report["source_sha256_after"] == snapshots, "Input hash changed during check")
        missing = [k for k in selected if report["stations"][str(k)]["status"] == "NOT_GENERATED"]
        overlaps = [p for p in report["comparisons"] if p["status"] == "NEEDS_BREP"]
        report.update(status="INCOMPLETE_NOT_GENERATED" if missing else "NEEDS_BREP" if overlaps else "PASS_SELECTED_STATION_AABB_SEPARATION",
            source_hashes_unchanged=True, pair_count=len(report["comparisons"]),
            separated_pair_count=len(report["comparisons"])-len(overlaps), needs_brep_count=len(overlaps),
            needs_brep_pairs=overlaps, missing_selected_stations=missing,
            completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        save()
        print(json.dumps(dict(status=report["status"], selected_stations=list(selected), pair_count=report["pair_count"],
                              needs_brep_count=len(overlaps), output=str(output))))
        return 0 if not missing and not overlaps else 2
    except Exception as exc:
        report.update(status="INCOMPLETE", error_type=type(exc).__name__, error=str(exc),
                      completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        save(); print(json.dumps(dict(status="INCOMPLETE", error=str(exc))), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
