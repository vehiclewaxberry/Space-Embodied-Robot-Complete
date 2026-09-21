"""Read-only source checks and scalar necessary bounds; writes only this intake's check JSON.
No nozzle array is invented, no control command is generated, no CAD/physics Gate is modified.
"""
from pathlib import Path
from math import sqrt
import hashlib
import json
import datetime
import itertools

D = Path(__file__).resolve().parent


def main():
    manifest = json.loads((D / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    evidence = json.loads((D / "REVIEW_EVIDENCE.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, actual, expected):
        checks.append({"id": name, "pass": actual == expected, "actual": actual, "expected": expected})

    for item in manifest["documents"]:
        if item.get("status") == "FETCH_FAILED":
            check("missing_download_not_misrepresented_" + item["file"], (D / item["file"]).exists(), False)
        else:
            p = D / item["file"]
            check("source_sha_" + item["file"], hashlib.sha256(p.read_bytes()).hexdigest(), item["sha256"])
    check("exactly_two_formal_alternatives", len(evidence["formal_alternatives"]), 2)
    check("zero_full_public_icd_matches", sum(x["full_public_ICD_bound"] for x in evidence["candidate_interfaces"]), 0)
    check("C_POD_same_footer_conflict_recorded", evidence["conflicts"][0]["id"], "CPOD_SAME_PART_SAME_FOOTER_DIFFERENT_SPEC")
    h = evidence["historical_input_binding"]
    check("history_scan_hash_unchanged", hashlib.sha256(Path(h["file"]).read_bytes()).hexdigest(), h["sha256"])
    H = h["H_norm_Nms"]
    g0 = 9.80665
    Isp = 40.0
    budget_kg = h["propellant_budget_max_g"] / 1000
    T = h["t_detumble_max_s"]
    out = {
        "schema": "SEI_PROPULSION_PUBLIC_SELECTION_CHECKS_V1",
        "computed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "Evidence bookkeeping and necessary scalar bounds, not module qualification or operational capability evaluation.",
        "assumptions_for_compact_module_bound": [
            "All nozzle force application points lie within stated candidate envelope; catalogue drawings do not replace actual nozzle ICD.",
            "Net force is zero at every instant (balanced couples), or a fixed-attitude static allocation uses zero integrated net force.",
            "J_total is the sum of individual nonnegative scalar nozzle impulses, not impulse per nozzle.",
            "Reference translation cancels for zero resultant; moving a complete compact module outward does not enlarge its internal couple arm.",
            "Historic H norm, propellant budget and PROVISIONAL time window are sensitivity inputs, not validated current mission requirements.",
            "Isp=40 s is a catalogue reference; no usable-impulse margin, leakage, reserve, thermal or direction loss is credited.",
            "This bound does not exclude maneuvers with nonzero resultant forces and translation/orientation excursions."
        ],
        "formulas": {
            "R_box": "sqrt(Lx**2 + Ly**2 + Lz**2)/2",
            "angular_impulse_upper_bound": "H_max <= R_box * J_total",
            "required_scalar_impulse_lower_bound": "J_required >= H_norm / R_box",
            "required_propellant_at_reference_Isp": "m_required >= H_norm/(R_box*g0*Isp)",
            "required_effective_radius_at_budget": "r_required >= H_norm/(m_budget*g0*Isp)",
            "ideal_two_jet_force_lower_bound": "F_each >= H_norm/(2*r*T)"
        },
        "historical_reference": h,
        "g0_m_s2": g0,
        "catalogue_Isp_reference_s": Isp,
        "historical_budget_equivalent_impulse_Ns": budget_kg*g0*Isp,
        "effective_radius_required_by_historical_budget_m": H/(budget_kg*g0*Isp),
        "torque_required_at_3600s_Nm": H/T,
        "cases": []
    }
    for name, box, J in [("MiPS_X14029003_1", [.0890016, .0890016, .030], 44), ("C_POD_LOCKED", [.0985012, .094488, .101473], 174)]:
        R = sqrt(sum(x*x for x in box))/2
        out["cases"].append({
            "id": name, "envelope_m": box, "R_box_m": R, "catalogue_total_shared_impulse_Ns": J,
            "optimistic_H_upper_bound_full_catalogue_impulse_Nms": R*J,
            "passes_only_this_necessary_full_resource_bound": R*J >= H,
            "scalar_impulse_lower_bound_Ns": H/R,
            "propellant_lower_bound_at_40s_g": H/(R*g0*Isp)*1000,
            "H_upper_bound_at_historical_propellant_budget_Nms": R*budget_kg*g0*Isp,
            "passes_only_this_necessary_historical_budget_bound": R*budget_kg*g0*Isp >= H,
            "ideal_pair_force_each_required_at_3600s_N": H/(2*R*T),
            "actual_nozzle_allocation_feasible": None
        })
    allocation = evidence["limits"]["existing_shared_allocation_mm"]
    cpod_mm = [x*1000 for x in out["cases"][1]["envelope_m"]]
    fits = [p for p in itertools.permutations(cpod_mm) if all(a <= b for a,b in zip(p,allocation))]
    out["C_POD_axis_aligned_fits_existing_shared_box_count"] = len(fits)
    check("compact_old_MiPS_full_impulse_necessary_bound_fails", out["cases"][0]["passes_only_this_necessary_full_resource_bound"], False)
    check("compact_C_POD_full_impulse_necessary_bound_only_passes", out["cases"][1]["passes_only_this_necessary_full_resource_bound"], True)
    check("compact_C_POD_hist_budget_necessary_bound_fails", out["cases"][1]["passes_only_this_necessary_historical_budget_bound"], False)
    check("C_POD_no_axis_aligned_fit_old_shared_box", len(fits), 0)
    out["PERSEUS_power_branch_screen"] = {
        "conditional_reference_branch": "12 V regulated, 2 A continuous branch; actual current design binding belongs to parent EPS task",
        "branch_power_W": 24.0,
        "manufacturer_valve_opening_power_upper_exclusive_W": 30.0,
        "upper_envelope_current_A": 30.0/12.0,
        "can_cover_entire_published_opening_power_envelope_from_2A_only": False,
        "published_firing_power_upper_exclusive_W": 20.0,
        "firing_upper_envelope_current_A": 20.0/12.0,
        "actual_draw_A": None,
        "note": "Published <30W is not a measurement of exactly 30W; actual inrush duration/waveform and protection/hold-up must be obtained before branch verification.",
        "torque_reference_if_60s_prefiring_is_inside_3600s_window_Nm": H/(T-60)
    }
    check("hardware_actions_zero", evidence["limits"]["hardware_actions"], 0)
    check("supplier_contacts_zero", evidence["limits"]["supplier_contacts"], 0)
    out["checks"] = checks
    out["checks_passed"] = sum(x["pass"] for x in checks)
    out["checks_total"] = len(checks)
    out["status"] = "PASS_EVIDENCE_AND_NECESSARY_BOUND_CHECKS_ONLY" if all(x["pass"] for x in checks) else "FAIL_REVIEW_CHECKS"
    (D/"REVIEW_CHECK_RESULTS.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f'{out["status"]}: {out["checks_passed"]}/{out["checks_total"]}')
    if not all(x["pass"] for x in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
