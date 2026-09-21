"""Read-only independent fsum/parallel-axis audit of the actual candidate files.

No production module, CAD package or simulator is imported. This audit checks
declared atomic properties and provenance, not their physical accuracy.
"""
from pathlib import Path
import csv
import hashlib
import io
import json
import math
import sys

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parents[1]
HERE = RUN / "candidate"
OUT = RUN / "review/ROBOT_ACTUAL_LEDGER_RECHECK.json"
CHECKS = []
TOL = 1e-10  # Arithmetic audit tolerance only, not a scientific Gate.

def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))

def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def check(name, condition):
    CHECKS.append(dict(check=name, passed=bool(condition)))

def identity(rows):
    keys = ("id", "mass_owner", "product_role", "representation_role", "mass_source", "mass_kg", "arm_link")
    return digest(sorted(({k: r.get(k) for k in keys} for r in rows), key=lambda r: r["id"]))

def main():
    hp = HERE / "results/DYNAMICS_HANDOFF.json"
    bp = HERE / "BOM.csv"
    ip = HERE / "INTERFACES.csv"
    handoff = load(hp)
    paths = {s: HERE / "results" / f"{s}_instances.json" for s in ("parking", "released", "service")}
    receipts = {s: load(p) for s, p in paths.items()}
    required = {Path(p).resolve() for p in handoff["input_sha256"]}
    tracked = required | {hp, bp, ip, *paths.values()}
    old_sources = {}
    for d in receipts.values():
        required |= {(HERE / n).resolve() for n in d["dependency_sha256"]}
        required |= {Path(p).resolve() for p in d["geometry_sha256"]}
        required |= {Path(v["path"]).resolve() for v in d["composition"].values() if isinstance(v, dict) and "path" in v and "sha256" in v}
        oldpath = Path(d["composition"]["original_receipt"]["path"])
        old = load(oldpath)
        home = oldpath.parents[1]
        old_sources[str((home / "spacecraft_model.py").resolve())] = old["source_sha256"]
        old_sources.update({str((home / n).resolve()): h for n, h in old["dependency_sha256"].items()})
    tracked |= required | {Path(p) for p in old_sources}
    before = {str(p.resolve()): sha(p) for p in tracked}
    recorded = {str(Path(p).resolve()): h for p, h in handoff["input_sha256"].items()}
    check("all_recorded_handoff_hashes_match_actual_files", all(before[p] == h for p, h in recorded.items()))
    check("receipt_geometry_dependencies_and_composition_refs_are_direct_handoff_inputs", {str(p) for p in required} <= set(recorded))
    check("legacy_model_and_dependencies_still_match_original_receipts", all(before[p] == h for p, h in old_sources.items()))
    check("handoff_recorded_unchanged_inputs", handoff["source_files_unchanged"] is True)
    summaries = []
    states = {}
    for label, receipt in receipts.items():
        matches = [s for s in handoff["states"] if s["state"] == label]
        check(label + ":single_handoff_state", len(matches) == 1)
        state = matches[0]
        states[label] = state
        group = state["groups"]["ONBOARD_CANDIDATE"]
        atoms = group["mass_atoms"]
        unknown = group["unknown_mass_instances"]
        rows = receipt["instances"]
        owner_rows = {r["mass_owner"]: r for r in rows}
        atom_map = {a["mass_owner"]: a for a in atoms}
        unknown_map = {u["mass_owner"]: u for u in unknown}
        expected_positive = {r["mass_owner"] for r in rows if r.get("arm_link") or (r.get("mass_kg") is not None and r["mass_kg"] > 0)}
        expected_unknown = {r["mass_owner"] for r in rows if r.get("mass_kg") is None and not r.get("arm_link")}
        check(label + ":unique_instance_and_owner_coverage", len({r["id"] for r in rows}) == len(rows) == len(owner_rows) == group["instance_count"])
        check(label + ":known_unknown_unique_and_exhaustive", len(atom_map) == len(atoms) and len(unknown_map) == len(unknown) and set(atom_map) == expected_positive and set(unknown_map) == expected_unknown and not (set(atom_map) & set(unknown_map)) and len(atoms) + len(unknown) + len(state.get("zero_contribution_instances", [])) == len(rows))
        check(label + ":onboard_no_GSE_or_target", all(r["product_role"] == "ONBOARD_CANDIDATE" for r in rows) and state["mass_owner_values_by_role"]["ONBOARD_CANDIDATE"] == state["mass_owner_values"] and not any(v for k, v in state["mass_owner_values_by_role"].items() if k != "ONBOARD_CANDIDATE"))
        check(label + ":unknown_not_zero_and_known_properties_present", all(owner_rows[k]["mass_kg"] is None for k in expected_unknown) and not group["known_mass_missing_properties"])
        check(label + ":pose_binding", all(state[h] == receipt[r] for h, r in (("q_deg", "q_deg"), ("finger_mm", "finger_mm"), ("T_S_arm_base_mm", "T_S_arm_base"))))
        binding = dict(configuration=receipt["configuration"], view=receipt["view"], receipt_path=str(paths[label].resolve()), receipt_sha256=sha(paths[label]), instance_identity_sha256=identity(rows))
        check(label + ":receipt_identity_binding", handoff["receipt_bindings"][label] == binding)
        mass = math.fsum(a["mass_kg"] for a in atoms)
        com = [math.fsum(a["mass_kg"] * a["center_of_mass_S_m"][i] for a in atoms) / mass for i in range(3)]
        def component(a, i, j, origin):
            d = [a["center_of_mass_S_m"][k] - origin[k] for k in range(3)]
            return a["inertia_about_COM_S_kg_m2"][i][j] + a["mass_kg"] * ((math.fsum(v*v for v in d) if i == j else 0) - d[i] * d[j])
        ic = [[math.fsum(component(a, i, j, com) for a in atoms) for j in range(3)] for i in range(3)]
        io_ = [[math.fsum(component(a, i, j, [0, 0, 0]) for a in atoms) for j in range(3)] for i in range(3)]
        declared = group["allocated_complete_property_subset"]
        errors = dict(mass_kg=abs(mass - group["known_mass_kg"]), COM_m=max(abs(com[i] - declared["center_of_mass_S_m"][i]) for i in range(3)),
                      I_COM_kg_m2=max(abs(ic[i][j] - declared["inertia_about_COM_S_kg_m2"][i][j]) for i in range(3) for j in range(3)),
                      I_S_kg_m2=max(abs(io_[i][j] - declared["inertia_about_S_origin_S_kg_m2"][i][j]) for i in range(3) for j in range(3)))
        check(label + ":independent_fsum_parallel_axis_arithmetic", all(v <= TOL for v in errors.values()))
        check(label + ":per_owner_numeric_mass", all(abs(atom_map[k]["mass_kg"] - state["mass_owner_values"][k]) <= TOL for k in atom_map))
        arm = [a for a in atoms if a.get("arm_link")]
        arm_mass = math.fsum(a["mass_kg"] for a in arm)
        check(label + ":accepted_digital_arm_count_mass_once", len(arm) == 10 and len({a["arm_link"] for a in arm}) == 10 and all(a["mass_source"] == "SOURCE_DIGITAL" for a in arm) and abs(arm_mass - 4.695555949342986) <= 1e-12)
        old = load(receipt["composition"]["original_receipt"]["path"])
        old_arm = {r["id"]: r for r in old["instances"] if r.get("arm_link")}
        actual_arm = {r["id"]: {k: v for k, v in r.items() if k != "geometry_reuse"} for r in rows if r.get("arm_link")}
        check(label + ":reused_arm_properties_exactly_unchanged", old_arm == actual_arm)
        check(label + ":geometry_and_old_receipt_hashes_match", all(before[str(Path(p).resolve())] == h for p, h in receipt["geometry_sha256"].items()))
        interfaces = receipt["interfaces"]
        check(label + ":interface_identity_one_per_instance", len(interfaces) == len(rows) == len({v["instance"] for v in interfaces}) and {v["instance"] for v in interfaces} == {r["id"] for r in rows})
        index = load(receipt["composition"]["assembly_index"]["path"])
        check(label + ":scope_not_promoted", receipt["monolithic_complete_step_generated"] is False and receipt["composition_mode"] == "FRESH_NONARM_PLUS_HASH_LOCKED_UNCHANGED_ARM" and index["collision_credit"] is None and state["onboard_full_physical_mass_properties_complete"] is False)
        summaries.append(dict(state=label, instance_count=len(rows), positive_atoms=len(atoms), unknown_instances=len(unknown), known_mass_kg=mass, arm_mass_kg=arm_mass, COM_S_m=com, errors=errors))
    reference = states["service"]["mass_owner_values"]
    check("cross_state_owner_sets_and_values", all(set(s["mass_owner_values"]) == set(reference) and all(abs(s["mass_owner_values"][k] - reference[k]) <= TOL for k in reference) for s in states.values()))
    check("cross_state_same_allocated_mass", max(r["known_mass_kg"] for r in summaries) - min(r["known_mass_kg"] for r in summaries) <= TOL)
    bom = list(csv.DictReader(io.StringIO(bp.read_text(encoding="utf-8-sig"))))
    interfaces = list(csv.DictReader(io.StringIO(ip.read_text(encoding="utf-8-sig"))))
    service = {r["id"]: r for r in receipts["service"]["instances"]}
    check("BOM_and_interfaces_unique_complete_coverage", len(bom) == len(service) == len({r["id"] for r in bom}) == len(interfaces) == len({r["instance"] for r in interfaces}) and set(service) == {r["id"] for r in bom} == {r["instance"] for r in interfaces})
    row_ok = True
    allocated = []
    for row in bom:
        source = service[row["id"]]
        expected = reference.get(source["mass_owner"])
        field = row["allocated_dynamics_mass_kg"]
        if expected is None:
            row_ok &= field == ""
        else:
            value = float(field)
            row_ok &= abs(value - expected) <= 1e-12
            allocated.append(value)
        row_ok &= all(row[k] == str(source[k]) for k in ("id", "mass_owner", "product_role", "representation_role", "source_revision"))
        row_ok &= (row["mass_kg"] == "") if source.get("mass_kg") is None else abs(float(row["mass_kg"]) - source["mass_kg"]) <= 1e-12
        row_ok &= row["handoff_sha256"] == before[str(hp.resolve())] and row["receipt_sha256"] == before[str(paths["service"].resolve())]
        row_ok &= row["geometry_snapshot_sha256"] == digest(receipts["service"]["geometry_sha256"])
    check("BOM_every_row_identity_nulls_values_and_source_hashes", row_ok)
    bom_mass = math.fsum(allocated)
    check("BOM_allocated_only_sum_matches_HANDOFF", abs(bom_mass - states["service"]["groups"]["ONBOARD_CANDIDATE"]["known_mass_kg"]) <= TOL)
    after = {str(p.resolve()): sha(p) for p in tracked}
    check("all_actual_inputs_geometry_and_old_sources_unchanged_during_audit", before == after)
    result = dict(schema="WP04_INDEPENDENT_ACTUAL_LEDGER_RECHECK_V1", scope="Read-only actual final candidate ledger and source audit; independent stdlib fsum and parallel-axis arithmetic",
                  geometry_executed=False, dynamics_executed=False, physical_accuracy_verified=False, unknown_mass_bounds_established=False,
                  audit_roundoff_tolerance=TOL, tolerance_is_not_a_scientific_gate=True, checks=CHECKS,
                  all_passed=all(c["passed"] for c in CHECKS), states=summaries,
                  BOM=dict(rows=len(bom), interfaces=len(interfaces), allocated_sum_kg=bom_mass, raw_and_allocated_mass_columns_added=False),
                  handoff_recorded_input_count=len(recorded), total_direct_and_transitive_files_hashed=len(before),
                  input_sha256_before=before, input_sha256_after=after, audit_script_sha256=sha(__file__))
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps(dict(all_passed=result["all_passed"], checks=len(CHECKS), failed=[c["check"] for c in CHECKS if not c["passed"]], states=summaries, output=str(OUT)), ensure_ascii=False))
    raise SystemExit(0 if result["all_passed"] else 1)

if __name__ == "__main__":
    main()

