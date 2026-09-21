"""No-CAD cross check: both actual C03 stations and station 1 versus WP06 delta.

Requires both FINAL C03 local checks. Never loads producer/checker code, never
constructs geometry, and never promotes an overlapping AABB into collision or
clearance acceptance. All output is new and is limited to three static poses.
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
import traceback

RUN = Path(__file__).resolve().parents[1]
STATES = ("parking", "service", "released")
C03_CHECKER_SHA = "647884bb84b3bffe60e0597fb20f8b54f3dda2bb5e74d8df271ae29c34020c5d"
CONTRACT_SHA = "cd4b40745ca081ed7dfa2c89cd7f811a4998ca2baf832e1e73b50dfe2a87ba8c"


class NotReady(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bounds(value):
    lo, hi = value["min_mm"], value["max_mm"]
    require(len(lo) == len(hi) == 3 and all(math.isfinite(x) for x in lo+hi), "Invalid finite 3D mm bounds")
    require(all(lo[i] < hi[i] for i in range(3)), "Nonpositive solid AABB")
    size = [hi[i]-lo[i] for i in range(3)]
    if "size_mm" in value:
        require(len(value["size_mm"]) == 3 and max(abs(value["size_mm"][i]-size[i]) for i in range(3)) <= 1e-7,
                "AABB size inconsistent")
    return dict(min_mm=lo, max_mm=hi, size_mm=size)


def rigid(T):
    require(len(T) == 4 and all(len(row) == 4 for row in T), "Expected 4x4 matrix")
    require(all(math.isfinite(v) for row in T for v in row), "Nonfinite matrix")
    require(max(abs(T[3][j]-int(j == 3)) for j in range(4)) <= 1e-12, "Invalid homogeneous matrix row")
    require(max(abs(math.fsum(T[k][i]*T[k][j] for k in range(3))-int(i == j))
                for i in range(3) for j in range(3)) <= 1e-10, "Matrix rotation not orthonormal")
    det = (T[0][0]*(T[1][1]*T[2][2]-T[1][2]*T[2][1])
           - T[0][1]*(T[1][0]*T[2][2]-T[1][2]*T[2][0])
           + T[0][2]*(T[1][0]*T[2][1]-T[1][1]*T[2][0]))
    require(abs(det-1) <= 1e-10, "Matrix scales or reflects")
    return T


def world_bounds(local, T):
    local, T = bounds(local), rigid(T)
    points = [[math.fsum(T[i][j]*p[j] for j in range(3))+T[i][3] for i in range(3)]
              for p in itertools.product(*zip(local["min_mm"], local["max_mm"]))]
    return bounds(dict(min_mm=[min(p[i] for p in points) for i in range(3)],
                       max_mm=[max(p[i] for p in points) for i in range(3)]))


def difference(a, b):
    a, b = bounds(a), bounds(b)
    return max(abs(a[k][i]-b[k][i]) for k in ("min_mm", "max_mm") for i in range(3))


def separation(a, b, pad):
    a, b = bounds(a), bounds(b)
    gaps = [max(b["min_mm"][i]-a["max_mm"][i], a["min_mm"][i]-b["max_mm"][i]) for i in range(3)]
    axes = ["XYZ"[i] for i in range(3) if gaps[i] > pad]
    return dict(status="SEPARATED_BY_AABB" if axes else "NEEDS_BREP", signed_axis_gaps_mm=gaps,
        separating_axes=axes, distance_lower_bound_mm=math.sqrt(math.fsum(max(0.0, g)**2 for g in gaps)),
        collision_conclusion="NO_COLLISION_BY_ENCLOSING_AABB" if axes else "NOT_DETERMINED")


def expected_ids(k, p):
    return {f"hold_fold_mast_{k}", *[f"hold_shoe_guide_{k}_{int(x)}" for x in p["guide_axis_x_mm"]],
        *[f"WP07_guide_{role}_{k}_{int(x)}" for role in ("washer", "screw") for x in p["guide_axis_x_mm"]],
        *[f"WP07_lower_collar_{k}_{side}" for side in ("front", "rear")],
        *[f"WP07_lower_{role}_{k}_{int(x)}" for role in ("screw", "washer_outer", "washer_inner", "nut")
          for x in p["lower_collar_bolt_x_mm"]]}


class Audit:
    def __init__(self, report):
        self.report = report
        self.snapshots = report["source_sha256_before"]

    def bind(self, path, expected=None):
        path = Path(path).resolve()
        if not path.is_file():
            raise NotReady("Actual evidence file absent: " + str(path))
        digest = sha(path)
        require(expected is None or digest == expected, "Actual SHA mismatch: " + str(path))
        require(str(path) not in self.snapshots or self.snapshots[str(path)] == digest, "Input changed during reading")
        self.snapshots[str(path)] = digest
        return digest

    def load_station(self, k, cp, contract, tolerance):
        rp = RUN / f"results/retention_detail/station_{k}/EMISSION_RECEIPT.json"
        vp = RUN / f"results/retention_detail_c03/station_{k}/CHECK_local.json"
        self.bind(rp)
        emission = read(rp)
        require(emission["schema"] == "WP07_RETENTION_DETAIL_EMISSION_V2" and emission["station_index"] == k,
                "Wrong emission identity")
        require(Path(emission["contract_path"]).resolve() == cp.resolve() and emission["contract_sha256"] == CONTRACT_SHA,
                "Emission not bound to frozen contract")
        require(emission["parameters"] == contract["parameters"], "Emission parameters differ")
        self.bind(emission["producer_path"], emission["producer_sha256"])
        require(set(emission["parts"]) == expected_ids(k, contract["parameters"]) and len(emission["parts"]) == 17,
                "Expected exact 17 actual replacement/addition parts")
        if not vp.is_file():
            raise NotReady(f"Station {k} final C03 local check absent")
        checks = read(vp)
        require(checks["schema"] == "WP07_RETENTION_DETAIL_CHECK_C03" and checks["station_index"] == k
                and checks["mode"] == "local", "Wrong C03 local check identity")
        if checks["status"] == "RUNNING" or not checks.get("completed_utc"):
            raise NotReady(f"Station {k} C03 local is not final: {checks['status']}")
        require(checks["status"] == "PASS", f"Station {k} C03 local did not PASS")
        self.bind(vp)
        self.bind(checks["checker_path"], checks["checker_sha256"])
        require(checks["checker_sha256"] == C03_CHECKER_SHA, "Expected frozen final C03 checker")
        require(Path(checks["receipt_path"]).resolve() == rp.resolve(), "Local check bound to wrong emission")
        require(all(row["status"] == "PASS" for row in checks["checks"]), "Non-PASS C03 measurement")
        require(checks["counts"] == {"PASS": len(checks["checks"]), "FAIL": 0, "INCOMPLETE": 0}, "C03 check counts differ")
        end_gate = [row for row in checks["checks"] if row["id"] == "frozen_input_hashes_after_measurement"]
        require(len(end_gate) == 1 and end_gate[0]["status"] == "PASS", "Missing C03 final input hash check")
        for path, digest in checks["input_sha256"].items():
            self.bind(path, digest)
        require(checks["input_sha256"].get(str(rp.resolve())) == self.snapshots[str(rp.resolve())], "C03 emission SHA differs")
        actual = {row["id"][6:]: row for row in checks["checks"] if row["id"].startswith("solid:")}
        require(set(actual) == set(emission["parts"]), "C03 actual solid measurements incomplete")
        result = dict(status="FINAL_C03_LOCAL_PASS_ACTUAL_INPUTS_BOUND", station=k, part_count=17,
            emission_path=str(rp), emission_sha256=self.snapshots[str(rp.resolve())],
            c03_local_path=str(vp), c03_local_sha256=self.snapshots[str(vp.resolve())],
            c03_checker_sha256=C03_CHECKER_SHA, c03_counts=checks["counts"],
            bounds_basis="Final C03 independent actual STEP readback; checked against actual emission bounds and hashes",
            includes_replacements=3, includes_added_parts=14, state_world_bounds={})
        for state in STATES:
            T = rigid(contract["stations"][str(k)]["states"][state]["T_S_mast"])
            require(emission["placements"][state] == T, "Emission state transform differs")
            result["state_world_bounds"][state] = {}
            for name, part in emission["parts"].items():
                self.bind(part["path"], part["sha256"])
                require(Path(part["path"]).suffix.lower() in (".step", ".stp"), "Measured part must be actual STEP")
                require(checks["input_sha256"].get(str(Path(part["path"]).resolve())) == part["sha256"], "C03 STEP binding differs")
                require(part["T_S_local_by_state"][state] == T, "Part pose differs")
                fact = actual[name]
                require(fact["shape_valid"] is True and fact["solid_count"] == 1 and
                        math.isfinite(fact["volume_mm3"]) and fact["volume_mm3"] > 0, "Invalid actual C03 solid facts")
                source_box = bounds(fact["bbox_mm"])
                require(difference(source_box, part["local_bbox_mm"]) <= tolerance, "C03 measured bbox differs from emission")
                result["state_world_bounds"][state][name] = dict(bbox_mm=world_bounds(source_box, T),
                    source_bbox_mm=source_box, T_S_local=T, source_path=part["path"], source_sha256=part["sha256"])
        return result

    def load_wp06(self, tolerance):
        mp = RUN / "results/INTEGRATION_MANIFEST.json"
        self.bind(mp)
        manifest = read(mp)
        require(manifest["units"] == "mm", "Integration unit mismatch")
        replaced, added = set(manifest["replaced_ids"]), set(manifest["added_ids"])
        require(len(replaced) == 8 and len(added) == 16 and not replaced & added, "Expected WP06 8 replacement +16 new delta")
        names = replaced | added
        receipt = manifest["local_parts_receipt"]
        self.bind(receipt["path"], receipt["sha256"])
        local = read(receipt["path"])
        self.bind(local["source_path"], local["source_sha256"])
        result = {}
        for state in STATES:
            rows = manifest["states"][state]["instances"]
            by_id = {row["id"]: row for row in rows}
            require(len(rows) == len(by_id) == 597 and names <= set(by_id), "Frozen integration instance set differs")
            result[state] = {}
            for name in sorted(names):
                row, known = by_id[name], local["parts"][name]
                source = row["source_step"]
                self.bind(source["path"], source["sha256"])
                require(source["sha256"] == known["sha256"] and Path(source["path"]).resolve() == Path(known["path"]).resolve(),
                        "WP06 local source identity differs")
                facts = row["actual_source_facts"]
                require(facts["shape_valid"] is True and facts["solid_count"] == 1 and
                        math.isfinite(facts["volume_mm3"]) and facts["volume_mm3"] > 0, "Invalid WP06 actual source facts")
                require(difference(facts["bbox_mm"], known["facts"]["bbox_mm"]) <= tolerance, "WP06 local readback bounds differ")
                world = world_bounds(facts["bbox_mm"], row["T_S_local"])
                require(difference(world, row["world_bounds_mm"]) <= tolerance and difference(world, row["bounds_mm"]) <= tolerance,
                        "WP06 pose or world bounds mismatch")
                result[state][name] = dict(bbox_mm=world, source_path=source["path"], source_sha256=source["sha256"],
                    T_S_local=row["T_S_local"], source_bbox_mm=facts["bbox_mm"])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RUN/"results/RETENTION_BOTH_STATIONS_CROSS.json")
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to((RUN/"results").resolve()), "Output must remain under run/results")
    require(not output.exists(), "Refuse overwrite: choose a new --output for later execution")
    report = dict(schema="WP07_RETENTION_BOTH_STATIONS_CROSS_V1", status="INCOMPLETE", units="mm",
        started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), source_sha256_before={}, source_sha256_after={},
        stations={}, wp06_delta_world_bounds={}, comparisons=[], errors=[],
        scope="All 17 actual modified/new parts at station 0 versus all 17 at station 1 in three frozen poses; "
              "all 17 station 1 parts versus the 24 actual WP06 replacements/additions in the same three poses. "
              "AABB separation only. No continuous motion, other neighbours, strength, hardware assembly or manufacturing credit.",
        cad_or_com_executed=False, generated_source_used_as_geometry=False, bbox_overlap_is_collision=False,
        whole_system_collision_verified=False, physical_assembly_completed=False, manufacturing_release=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    audit = Audit(report)
    try:
        audit.bind(__file__)
        cp = RUN/"inputs/RETENTION_DESIGN_CONTRACT.json"
        audit.bind(cp, CONTRACT_SHA)
        contract = read(cp)
        require(contract["schema"] == "WP07_RETENTION_GUIDE_END_DESIGN_V2" and contract["units"] == "mm", "Expected mm contract")
        tolerance = contract["acceptance"]["linear_mm"]
        require(math.isfinite(tolerance) and tolerance > 0, "Missing positive numerical separation padding")
        report["aabb_separation_padding_mm"] = tolerance
        for path, digest in contract["source_inputs"].items():
            audit.bind(path, digest)
        for k in (0, 1):
            report["stations"][str(k)] = audit.load_station(k, cp, contract, tolerance)
        wp06 = audit.load_wp06(tolerance)
        report["wp06_delta_world_bounds"] = wp06
        for state in STATES:
            zero = report["stations"]["0"]["state_world_bounds"][state]
            one = report["stations"]["1"]["state_world_bounds"][state]
            for a, b in itertools.product(sorted(zero), sorted(one)):
                report["comparisons"].append(dict(group="STATION_0_VS_STATION_1", state=state,
                    a_id=a, b_id=b, a_source_sha256=zero[a]["source_sha256"], b_source_sha256=one[b]["source_sha256"],
                    **separation(zero[a]["bbox_mm"], one[b]["bbox_mm"], tolerance)))
            for a, b in itertools.product(sorted(one), sorted(wp06[state])):
                report["comparisons"].append(dict(group="STATION_1_VS_WP06_DELTA", state=state,
                    a_id=a, b_id=b, a_source_sha256=one[a]["source_sha256"], b_source_sha256=wp06[state][b]["source_sha256"],
                    **separation(one[a]["bbox_mm"], wp06[state][b]["bbox_mm"], tolerance)))
        groups = {}
        for group, expected in (("STATION_0_VS_STATION_1", 17*17*3), ("STATION_1_VS_WP06_DELTA", 17*24*3)):
            rows = [r for r in report["comparisons"] if r["group"] == group]
            require(len(rows) == expected, "Pair coverage incomplete: " + group)
            overlap = [r for r in rows if r["status"] == "NEEDS_BREP"]
            groups[group] = dict(pair_count=len(rows), separated_pair_count=len(rows)-len(overlap), needs_brep_count=len(overlap),
                minimum_distance_lower_bound_mm=min(r["distance_lower_bound_mm"] for r in rows))
        overlap = [r for r in report["comparisons"] if r["status"] == "NEEDS_BREP"]
        report.update(status="NEEDS_BREP" if overlap else "PASS_BOUNDED_AABB_SEPARATION", groups=groups,
            pair_count=len(report["comparisons"]), separated_pair_count=len(report["comparisons"])-len(overlap),
            needs_brep_count=len(overlap), needs_brep_pairs=overlap)
    except NotReady as exc:
        report.update(status="INCOMPLETE_FINAL_C03_LOCAL_REQUIRED")
        report["errors"].append(str(exc))
    except Exception as exc:
        report["status"] = "FAIL_INPUT_OR_COMPUTATION"
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["traceback"] = traceback.format_exc()
    finally:
        report["source_sha256_after"] = {p: sha(p) if Path(p).is_file() else None for p in audit.snapshots}
        report["source_hashes_unchanged"] = report["source_sha256_before"] == report["source_sha256_after"]
        if not report["source_hashes_unchanged"]:
            report["status"] = "FAIL_INPUT_OR_COMPUTATION"
            report["errors"].append("An input/script changed during cross check")
        report["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(dict(status=report["status"], pair_count=report.get("pair_count"), groups=report.get("groups"),
                         output=str(output), output_sha256=sha(output), errors=report["errors"]), ensure_ascii=False))
    return 0 if report["status"] == "PASS_BOUNDED_AABB_SEPARATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
