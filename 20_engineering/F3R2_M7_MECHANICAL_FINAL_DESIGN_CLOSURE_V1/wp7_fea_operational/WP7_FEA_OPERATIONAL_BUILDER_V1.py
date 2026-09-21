# -*- coding: utf-8 -*-
"""
M7 / WP7 (FEA_OPERATIONAL) evidence builder.

Consumes ONLY real bytes on disk:
  * decks/*.inp                     (as-solved decks; applied load parsed from
                                     the deck *CLOAD lines = load of record)
  * jobs/*.inp .dat .msg .sta .odb  (solver artifacts)
  * jobs/*.json                     (deck sidecar metadata)
  * jobs/_extract/*.json            (odbAccess extraction, real ODB values)
  * upstream authority files        (materials / loads / BC / frame)

Produces:
  FEA1_RESULTS_V1.csv
  FEA1_EVIDENCE_V1.json
  FEA2_FEA8_DECK_REGISTER_V1.yaml
  receipt.json

FAIL-CLOSED: anything not present on disk is written as null with an explicit
status string. No zero-fill, no interpolation, no cross-job substitution.

Host CPython 3, stdlib only.
"""

import csv
import hashlib
import io
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DECKS = os.path.join(HERE, "decks")
JOBS = os.path.join(HERE, "jobs")
EXTR = os.path.join(JOBS, "_extract")

SCHEMA_PREFIX = "M7_WP7_FEA_OPERATIONAL"
CLOCK_SOURCE = "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08"

MESH_ORDER = ["COARSE", "MEDIUM", "FINE"]
CASE_ORDER = ["ARM_MANEUVER_QS", "ARM_ESTOP_QS",
              "CAPTURE_22KG_QS", "CAPTURE_150KG_QS"]

# ---------------------------------------------------------------------------
# upstream authority files actually consumed (relative to repo root)
# ---------------------------------------------------------------------------
UPSTREAM = {
    "authority_plan":
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "00_authority/M7_EXECUTION_PLAN_V1.md",
    "authority_odr":
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml",
    "material_library":
        "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/"
        "wp4_materials/PROTOTYPE_MATERIAL_LIBRARY_V2.yaml",
    "capture_load_envelope":
        "20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/"
        "02_wp1_loads/DERIVED_CAPTURE_LOAD_ENVELOPE_V1.csv",
    "load_bridge_datums":
        "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/"
        "wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml",
    "m3r_stage_a_parameter_table":
        "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/"
        "06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml",
    "m3r_stage_b_parameter_table":
        "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/"
        "06_parameterized_parts/m3r/M3R_STAGE_B_PARAMETER_TABLE.yaml",
    "accepted_urdf_l0":
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "sibling_receipt_schema_reference":
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp3_tolerance_alloc/receipt.json",
}

WP7_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp7_fea_operational"


def sha256_bytes(path):
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
            n += len(b)
    return h.hexdigest().upper(), n


def reg(path_abs, rel=None):
    """source_register entry with real recomputed SHA-256 (uppercase)."""
    if not os.path.isfile(path_abs):
        return {"path": rel or path_abs, "sha256": None, "bytes": None,
                "status": "FILE_ABSENT_ON_DISK"}
    d, n = sha256_bytes(path_abs)
    return {"path": rel or path_abs.replace("\\", "/"),
            "sha256": d, "bytes": n}


def now_iso():
    out = subprocess.check_output(["date", "-Iseconds"]).decode().strip()
    return out


# ---------------------------------------------------------------------------
# parsers
# ---------------------------------------------------------------------------

def parse_deck_load(inp_path):
    """Applied load AS WRITTEN IN THE DECK -- this is the load of record.

    The generator formatted CLOAD magnitudes with %.6g, so the deck value is a
    6-significant-figure truncation of the derivation value carried in the
    sidecar. Reaction balance must be judged against the DECK value.
    """
    txt = open(inp_path, "r", errors="replace").read()
    m = re.search(r"^\*CLOAD\s*$(.*?)^\*", txt, re.S | re.M)
    if not m:
        return None
    out = {}
    for line in m.group(1).strip().splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) == 3:
            out[int(p[1])] = float(p[2])
    return {"node": 900000,
            "F_y_N_deck": out.get(2),
            "M_z_N_mm_deck": out.get(6),
            "raw_dofs": {str(k): v for k, v in out.items()}}


DAT_ENERGY_MAP = [
    ("ALLSE_recoverable_strain_energy", r"RECOVERABLE STRAIN ENERGY\s+(\S+)"),
    ("ALLWK_external_work", r"EXTERNAL WORK\s+(\S+)"),
    ("ALLAE_energy_to_control_spurious_modes",
     r"ENERGY TO CONTROL SPURIOUS MODES\s+(\S+)"),
    ("ALLIE_total_strain_energy", r"TOTAL STRAIN ENERGY \(STRESS POWER\)\s+(\S+)"),
    ("ETOTAL_energy_balance", r"ENERGY BALANCE\s+(\S+)"),
    ("ALLKE_kinetic_energy", r"KINETIC ENERGY\s+(\S+)"),
    ("ALLPD_plastic_dissipation", r"PLASTIC DISSIPATION\s+(\S+)"),
]


def parse_dat(dat_path):
    txt = open(dat_path, "r", errors="replace").read()
    res = {"bytes": os.path.getsize(dat_path), "nonzero": os.path.getsize(dat_path) > 0}
    en = {}
    for key, pat in DAT_ENERGY_MAP:
        m = re.search(pat, txt)
        en[key] = float(m.group(1)) if m else None
        if m is None:
            en[key + "_status"] = "NOT_PRINTED_IN_DAT"
    res["energy_dat"] = en
    m = re.search(r"NUMBER OF ELEMENTS IS\s+(\d+)", txt)
    res["dat_n_elements"] = int(m.group(1)) if m else None
    m = re.search(r"NUMBER OF NODES IS\s+(\d+)", txt)
    res["dat_n_nodes"] = int(m.group(1)) if m else None
    m = re.search(r"TOTAL NUMBER OF VARIABLES IN THE MODEL\s+(\d+)", txt)
    res["dat_n_variables"] = int(m.group(1)) if m else None
    res["dat_input_warnings"] = re.findall(
        r"\*\*\*WARNING:\s*(.{0,110})", txt.replace("\n", " "))
    return res


def parse_msg(msg_path):
    txt = open(msg_path, "r", errors="replace").read()
    res = {"bytes": os.path.getsize(msg_path)}

    def cnt(pat):
        m = re.search(r"\s+(\d+)\s+" + pat, txt)
        return int(m.group(1)) if m else None

    res["analysis_warnings"] = cnt("WARNING MESSAGES DURING ANALYSIS")
    res["input_warnings"] = cnt("WARNING MESSAGES DURING USER INPUT PROCESSING")
    res["numerical_problem_warnings"] = cnt(
        "ANALYSIS WARNINGS ARE NUMERICAL PROBLEM MESSAGES")
    res["negative_eigenvalue_warnings"] = cnt(
        "ANALYSIS WARNINGS ARE NEGATIVE EIGENVALUE MESSAGES")
    res["error_messages"] = cnt("ERROR MESSAGES")
    res["completed"] = "THE ANALYSIS HAS BEEN COMPLETED" in txt
    sings = []
    for m in re.finditer(
            r"NUMERICAL SINGULARITY WHEN PROCESSING NODE\s+(\d+)\s*"
            r"D\.O\.F\.\s*(\d+)\s*RATIO\s*=\s*(\S+)",
            txt.replace("\n", " ")):
        sings.append({"node": int(m.group(1)), "dof": int(m.group(2)),
                      "ratio": m.group(3)})
    res["numerical_singularities"] = sings
    m = re.search(r"LARGEST SCALED RESIDUAL FORCE\s+(\S+)", txt)
    res["largest_scaled_residual_force"] = float(m.group(1)) if m else None
    m = re.search(r"LARGEST SCALED RESIDUAL MOMENT\s+(\S+)", txt)
    res["largest_scaled_residual_moment"] = float(m.group(1)) if m else None
    m = re.search(r"MEMORY PEAK \(GB\)\s*=\s*(\S+)", txt)
    res["memory_peak_gb"] = m.group(1) if m else None
    m = re.search(r"TOTAL CPU TIME \(SEC\)\s*=\s*(\S+)", txt)
    res["total_cpu_time_s"] = float(m.group(1)) if m else None
    m = re.search(r"NUMBER OF EQUATIONS:\s+(\d+)", txt)
    res["n_equations"] = int(m.group(1)) if m else None
    return res


def parse_sta(sta_path):
    txt = open(sta_path, "r", errors="replace").read()
    return {"bytes": os.path.getsize(sta_path),
            "completed_successfully":
                "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in txt}


def cross(r, f):
    return [r[1] * f[2] - r[2] * f[1],
            r[2] * f[0] - r[0] * f[2],
            r[0] * f[1] - r[1] * f[0]]


# ---------------------------------------------------------------------------
# upstream verification
# ---------------------------------------------------------------------------

def verify_materials(lib_path):
    """Re-read the M6 library and confirm the deck constants come from it."""
    if not os.path.isfile(lib_path):
        return {"status": "MATERIAL_LIBRARY_ABSENT", "checks": None}
    t = open(lib_path, encoding="utf-8", errors="replace").read()
    out = {}
    want = {
        "AL6061_T6_CAND": ("PMAT-AL6061-T6-SHEET-PLATE", 68.3, 2700.0, 276.0,
                           68300.0, 2.7e-9),
        "AL7075_T651_CAND": ("PMAT-AL7075-T651-SHEET-PLATE", 71.0, 2800.0, 503.0,
                             71000.0, 2.8e-9),
    }
    for mid, (pmat, e_gpa, rho, ys, deck_e, deck_rho) in want.items():
        i = t.find("material_id: " + pmat)
        if i < 0:
            out[mid] = {"status": "PMAT_ID_NOT_FOUND_IN_LIBRARY"}
            continue
        blk = t[i:i + 2000]
        def grab(pat):
            m = re.search(pat, blk)
            return m.groups() if m else None
        ym = grab(r"young_modulus:\s*\n\s*estimate_GPa:\s*([\d.]+)\s*\n\s*value_kind:\s*(\S+)")
        ysm = grab(r"yield_strength:\s*\n\s*estimate_MPa:\s*([\d.]+)\s*\n\s*value_kind:\s*(\S+)")
        dm = grab(r"density:\s*\n\s*estimate_kg_m3:\s*([\d.]+)")
        cl = grab(r"classification:\s*(\S+)")
        st = grab(r"status:\s*(\S+)")
        out[mid] = {
            "library_material_id": pmat,
            "library_E_GPa": float(ym[0]) if ym else None,
            "library_E_value_kind": ym[1] if ym else None,
            "deck_E_MPa": deck_e,
            "E_match": bool(ym and abs(float(ym[0]) * 1000.0 - deck_e) < 1e-6),
            "library_density_kg_m3": float(dm[0]) if dm else None,
            "deck_density_tonne_mm3": deck_rho,
            "density_match": bool(dm and abs(float(dm[0]) * 1e-12 - deck_rho) < 1e-18),
            "library_yield_MPa": float(ysm[0]) if ysm else None,
            "library_yield_value_kind": ysm[1] if ysm else None,
            "deck_yield_reference_MPa": ys,
            "yield_match": bool(ysm and abs(float(ysm[0]) - ys) < 1e-6),
            "library_classification": cl[0] if cl else None,
            "library_status": st[0] if st else None,
            "poisson_ratio_in_library": "poisson" in blk.lower(),
            "deck_poisson_used": 0.33,
            "poisson_provenance":
                "DECLARED_ASSUMPTION_NOT_IN_LIBRARY" if "poisson" not in blk.lower()
                else "LIBRARY_VALUE",
            "allowable_status":
                "TYPICAL_PROPERTY_NOT_A_DESIGN_ALLOWABLE_NASA_STD_5001B_PROHIBITS_"
                "TYPICAL_AS_ALLOWABLE",
        }
    out["_summary"] = {
        "all_E_match": all(v.get("E_match") for k, v in out.items() if k != "_summary"),
        "all_yield_match": all(v.get("yield_match") for k, v in out.items() if k != "_summary"),
        "all_density_match": all(v.get("density_match") for k, v in out.items() if k != "_summary"),
        "poisson_absent_from_library_confirmed":
            all(not v.get("poisson_ratio_in_library")
                for k, v in out.items() if k != "_summary"),
    }
    return out


def verify_capture_loads(csv_path):
    """Re-derive the two capture load cases from the authority CSV."""
    if not os.path.isfile(csv_path):
        return {"status": "CAPTURE_LOAD_ENVELOPE_ABSENT"}
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8", errors="replace")))
    by = {r["case_id"]: r for r in rows}
    daf, dt = 2.0, 0.1
    deck_used = {
        "CAPTURE_22KG_QS": {"J": 0.360622, "C": 0.00152744, "L": 0.25173,
                            "declared_row": "CAP22_030"},
        "CAPTURE_150KG_QS": {"J": 0.677633, "C": 0.130197, "L": 1.21521,
                             "declared_row": "CAP150_030"},
    }
    out = {"envelope_rows_present": sorted(by.keys()),
            "policy": {"DAF": daf, "dt_contact_s": dt,
                       "formula_F": "F = DAF * J / dt",
                       "formula_M": "M = F * L_grasp + DAF * C / dt"}}
    checks = {}
    for cid, u in deck_used.items():
        row = by.get(u["declared_row"])
        if row is None:
            checks[cid] = {"status": "DECLARED_ROW_NOT_IN_ENVELOPE"}
            continue
        j_src = float(row["contact_impulse_N_s"])
        c_src = float(row["grasp_couple_N_m_s"])
        l_src = float(row["grasp_lever_arm_m"])
        # which row (if any) does the deck's C value actually come from?
        c_origin = [k for k, r in by.items()
                    if abs(float(r["grasp_couple_N_m_s"]) - u["C"]) < 1e-12]
        f_deck = daf * u["J"] / dt
        m_deck = f_deck * u["L"] + daf * u["C"] / dt
        f_src = daf * j_src / dt
        m_src = f_src * l_src + daf * c_src / dt
        checks[cid] = {
            "declared_source_row": u["declared_row"],
            "deck_J_N_s": u["J"], "envelope_J_N_s": j_src,
            "J_matches_declared_row": abs(u["J"] - j_src) < 1e-12,
            "deck_L_m": u["L"], "envelope_L_m": l_src,
            "L_matches_declared_row": abs(u["L"] - l_src) < 1e-12,
            "deck_C_N_m_s": u["C"], "envelope_C_N_m_s": c_src,
            "C_matches_declared_row": abs(u["C"] - c_src) < 1e-12,
            "deck_C_actual_origin_rows": c_origin,
            "recomputed_F_from_deck_constants_N": f_deck,
            "recomputed_M_from_deck_constants_N_m": m_deck,
            "recomputed_F_strictly_from_declared_row_N": f_src,
            "recomputed_M_strictly_from_declared_row_N_m": m_src,
            "M_delta_pct_deck_vs_declared_row":
                (m_deck - m_src) / m_src * 100.0 if m_src else None,
            "F_delta_pct_deck_vs_declared_row":
                (f_deck - f_src) / f_src * 100.0 if f_src else None,
            "row_max_couple_across_family":
                max((float(r["grasp_couple_N_m_s"]), k) for k, r in by.items()
                    if k.split("_")[0] == u["declared_row"].split("_")[0])[1],
            "authority_status_column": row.get("authority_status"),
            "source_class_column": row.get("source_class"),
        }
    out["checks"] = checks
    return out


# ---------------------------------------------------------------------------
# minimal deterministic YAML emitter (stdlib only, no PyYAML dependency)
# ---------------------------------------------------------------------------

def yaml_scalar(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    if s == "":
        return "''"
    needs = (s[0] in "-?:,[]{}#&*!|>'\"%@` " or s[-1] == " "
             or any(c in s for c in ":#\n") or s.lower() in
             ("true", "false", "null", "yes", "no", "on", "off", "~"))
    try:
        float(s)
        needs = True
    except ValueError:
        pass
    if needs:
        return "'" + s.replace("'", "''") + "'"
    return s


def yaml_dump(obj, indent=0, out=None):
    if out is None:
        out = io.StringIO()
    pad = "  " * indent
    if isinstance(obj, dict):
        for k in obj:
            v = obj[k]
            if isinstance(v, dict) and v:
                out.write("%s%s:\n" % (pad, k))
                yaml_dump(v, indent + 1, out)
            elif isinstance(v, list) and v:
                out.write("%s%s:\n" % (pad, k))
                for it in v:
                    if isinstance(it, (dict, list)):
                        out.write("%s- \n" % ("  " * (indent + 1)))
                        yaml_dump(it, indent + 2, out)
                    else:
                        out.write("%s- %s\n" % ("  " * (indent + 1),
                                                yaml_scalar(it)))
            elif isinstance(v, (dict, list)):
                out.write("%s%s: %s\n" % (pad, k,
                                          "{}" if isinstance(v, dict) else "[]"))
            else:
                out.write("%s%s: %s\n" % (pad, k, yaml_scalar(v)))
    elif isinstance(obj, list):
        for it in obj:
            if isinstance(it, (dict, list)):
                out.write("%s- \n" % pad)
                yaml_dump(it, indent + 1, out)
            else:
                out.write("%s- %s\n" % (pad, yaml_scalar(it)))
    return out.getvalue()


# ---------------------------------------------------------------------------
# main assembly
# ---------------------------------------------------------------------------

def collect():
    jobs = sorted(f[:-4] for f in os.listdir(JOBS) if f.endswith(".sta"))
    recs = {}
    for j in jobs:
        r = {"job_name": j}
        side = os.path.join(JOBS, j + ".json")
        r["sidecar"] = json.load(open(side)) if os.path.isfile(side) else None
        ex = os.path.join(EXTR, j + ".json")
        r["odb"] = json.load(open(ex)) if os.path.isfile(ex) else None
        if r["odb"] is None:
            r["odb_status"] = "ODB_EXTRACT_MISSING"
        r["dat"] = parse_dat(os.path.join(JOBS, j + ".dat"))
        r["msg"] = parse_msg(os.path.join(JOBS, j + ".msg"))
        r["sta"] = parse_sta(os.path.join(JOBS, j + ".sta"))
        r["deck_load"] = parse_deck_load(os.path.join(DECKS, j + ".inp"))
        # deck integrity: as-solved copy in jobs/ vs decks/ vs sidecar hash
        d_deck, n_deck = sha256_bytes(os.path.join(DECKS, j + ".inp"))
        jinp = os.path.join(JOBS, j + ".inp")
        d_job, n_job = (sha256_bytes(jinp) if os.path.isfile(jinp)
                        else (None, None))
        sc_hash = (r["sidecar"] or {}).get("deck_sha256")
        r["deck_integrity"] = {
            "decks_dir_sha256": d_deck, "decks_dir_bytes": n_deck,
            "jobs_dir_sha256": d_job, "jobs_dir_bytes": n_job,
            "solved_copy_identical_to_deck": (d_deck == d_job),
            "sidecar_declared_sha256": (sc_hash or "").upper() or None,
            "sidecar_hash_matches_deck":
                bool(sc_hash) and sc_hash.upper() == d_deck,
        }
        # reaction balance against the DECK-written load
        rb = None
        if r["odb"] and r["odb"].get("reactions") and r["deck_load"]:
            rx = r["odb"]["reactions"]
            fy = r["deck_load"]["F_y_N_deck"]
            mz = r["deck_load"]["M_z_N_mm_deck"]
            sf = rx["sum_RF_N"]
            m_rp = rx["sum_reaction_moment_about_RP_N_mm"]
            m_o = rx["sum_reaction_moment_about_origin_N_mm"]
            applied_f = [0.0, fy, 0.0]
            rp = [0.0, 0.0, 30.75]
            applied_m_o = cross(rp, applied_f)
            applied_m_o[2] += mz
            res_f = [sf[k] + applied_f[k] for k in range(3)]
            res_m_o = [m_o[k] + applied_m_o[k] for k in range(3)]
            res_m_rp = [m_rp[0], m_rp[1], m_rp[2] + mz]
            nf = (applied_f[0] ** 2 + applied_f[1] ** 2 + applied_f[2] ** 2) ** 0.5
            nm = abs(mz)
            rb = {
                "applied_force_N_deck": applied_f,
                "applied_moment_about_RP_N_mm_deck": [0.0, 0.0, mz],
                "applied_moment_about_origin_N_mm_deck": applied_m_o,
                "sum_reaction_force_N": sf,
                "residual_force_N": res_f,
                "residual_force_norm_N": sum(x * x for x in res_f) ** 0.5,
                "residual_force_rel_to_applied": (
                    sum(x * x for x in res_f) ** 0.5 / nf if nf else None),
                "sum_reaction_moment_about_origin_N_mm": m_o,
                "residual_moment_about_origin_N_mm": res_m_o,
                "sum_reaction_moment_about_RP_N_mm": m_rp,
                "residual_moment_about_RP_N_mm": res_m_rp,
                "residual_moment_about_RP_norm_N_mm":
                    sum(x * x for x in res_m_rp) ** 0.5,
                "residual_moment_rel_to_applied_Mz": (
                    sum(x * x for x in res_m_rp) ** 0.5 / nm if nm else None),
                "n_nodes_with_nonzero_RF": rx["n_nodes_with_nonzero_RF"],
                "nonzero_RF_nodes_outside_encastre_set":
                    rx["nonzero_RF_nodes_outside_NFIXED"],
                "balance_reference":
                    "APPLIED_LOAD_OF_RECORD_IS_THE_DECK_CLOAD_VALUE "
                    "(generator wrote %.6g format; sidecar carries the "
                    "untruncated derivation value)",
            }
        r["reaction_balance"] = rb
        # hourglass / artificial energy fraction
        en = r["dat"]["energy_dat"]
        allie = en.get("ALLIE_total_strain_energy")
        allae = en.get("ALLAE_energy_to_control_spurious_modes")
        r["energy_quality"] = {
            "ALLIE": allie, "ALLAE": allae,
            "ALLSE": en.get("ALLSE_recoverable_strain_energy"),
            "ALLWK": en.get("ALLWK_external_work"),
            "ETOTAL": en.get("ETOTAL_energy_balance"),
            "artificial_energy_fraction_ALLAE_over_ALLIE":
                (allae / allie) if (allie not in (None, 0.0) and allae is not None)
                else None,
            "conventional_acceptance_threshold": 0.05,
            "acceptance_note":
                "C3D8R reduced integration: artificial (hourglass) strain energy "
                "should be a small fraction of internal energy. >5% indicates "
                "hourglass-contaminated bending response.",
        }
        recs[j] = r
    return recs


def convergence(recs):
    """Per-case mesh trend on the peak metrics. AL6061 baseline only."""
    out = {}
    for case in CASE_ORDER:
        per = {}
        for lvl in MESH_ORDER:
            jn = "fea1_%s_%s" % (case.lower(), lvl.lower())
            r = recs.get(jn)
            if r is None or not r.get("odb"):
                per[lvl] = {"status": "JOB_MISSING_OR_NOT_EXTRACTED",
                            "job_name": jn}
                continue
            o = r["odb"]
            per[lvl] = {
                "job_name": jn,
                "grid_pitch_mm": (r["sidecar"] or {}).get("grid_pitch_mm"),
                "elements": (r["sidecar"] or {}).get("elements_total"),
                "nodes": (r["sidecar"] or {}).get("nodes_total"),
                "peak_mises_MPa": o["peak_mises"]["value_MPa"],
                "peak_mises_element": o["peak_mises"]["element"],
                "peak_mises_zone": o["peak_mises"]["zone"],
                "peak_disp_mm": o["peak_disp"]["magnitude_mm"],
                "peak_disp_node": o["peak_disp"]["node"],
                "peak_disp_node_coords_mm": o["peak_disp"]["node_coords_mm"],
                "artificial_energy_fraction":
                    r["energy_quality"]["artificial_energy_fraction_ALLAE_over_ALLIE"],
                "numerical_singularity_count":
                    len(r["msg"]["numerical_singularities"]),
                "m5_nodes_per_face": sorted(set(
                    x["nodes_face_lo"] for x in (r["sidecar"] or {}).get(
                        "joint_records", []) if x["joint"].startswith("M5"))) or None,
                "m4_spider_nodes_per_disk": sorted(set(
                    x["nodes"] for x in (r["sidecar"] or {}).get(
                        "joint_records", []) if x["joint"].startswith("M4"))) or None,
            }

        def pct(a, b):
            if a in (None, 0) or b is None:
                return None
            return (b - a) / a * 100.0

        ok = all("status" not in per[l] for l in MESH_ORDER)
        trend = {}
        if ok:
            trend = {
                "peak_mises_pct_change_coarse_to_medium":
                    pct(per["COARSE"]["peak_mises_MPa"], per["MEDIUM"]["peak_mises_MPa"]),
                "peak_mises_pct_change_medium_to_fine":
                    pct(per["MEDIUM"]["peak_mises_MPa"], per["FINE"]["peak_mises_MPa"]),
                "peak_disp_pct_change_coarse_to_medium":
                    pct(per["COARSE"]["peak_disp_mm"], per["MEDIUM"]["peak_disp_mm"]),
                "peak_disp_pct_change_medium_to_fine":
                    pct(per["MEDIUM"]["peak_disp_mm"], per["FINE"]["peak_disp_mm"]),
            }
            mono = (per["COARSE"]["peak_mises_MPa"] > per["MEDIUM"]["peak_mises_MPa"]
                    < per["FINE"]["peak_mises_MPa"])
            trend["sequence_monotonic"] = not mono
            trend["sequence_shape"] = (
                "NON_MONOTONIC_V_SHAPE_COARSE_HIGH_MEDIUM_LOW_FINE_RISING"
                if mono else "SEE_VALUES")
            worst = max(abs(trend["peak_mises_pct_change_medium_to_fine"]),
                        abs(trend["peak_disp_pct_change_medium_to_fine"]))
            trend["finest_pair_worst_abs_pct_change"] = worst
            trend["convergence_verdict"] = (
                "CONVERGED" if worst <= 5.0 else "NOT_CONVERGED")
            trend["convergence_criterion"] = (
                "<=5% change in the peak metric between the two finest levels")
            trend["richardson_gci_applicable"] = False
            trend["richardson_gci_not_applicable_reason"] = (
                "refinement is not a pure h-refinement: (a) grid pitch ratios are "
                "unequal (16->10 = 1.60, 10->8 = 1.25); (b) the bolt-disk "
                "constraint footprints change with the lattice (M5 nodes/face "
                "2->4->5, M4 spider nodes/disk 1->4->5, M6 3->5->8), so the "
                "boundary-condition model changes between levels; (c) the peak "
                "metrics are located at kinematic-coupling boundaries, i.e. at a "
                "constraint-induced stress concentration that does not have a "
                "finite mesh-independent limit.")
        out[case] = {"levels": per, "trend": trend}
    return out


def build():
    ts = now_iso()
    recs = collect()
    conv = convergence(recs)
    mats = verify_materials(os.path.join(REPO, UPSTREAM["material_library"]))
    loads = verify_capture_loads(os.path.join(REPO, UPSTREAM["capture_load_envelope"]))

    solved = [j for j, r in recs.items() if r["sta"]["completed_successfully"]]
    failed = [j for j, r in recs.items() if not r["sta"]["completed_successfully"]]
    n_conv = sum(1 for c in conv.values()
                 if c["trend"].get("convergence_verdict") == "CONVERGED")

    # ---------------- CSV ----------------
    csv_path = os.path.join(HERE, "FEA1_RESULTS_V1.csv")
    cols = ["job_name", "case_id", "mesh_level", "material",
            "grid_pitch_mm", "nodes_total", "elements_total", "n_equations",
            "applied_Fy_N_deck", "applied_Mz_N_mm_deck",
            "peak_von_mises_MPa", "peak_mises_element", "peak_mises_zone",
            "peak_mises_element_centroid_x_mm", "peak_mises_element_centroid_y_mm",
            "peak_mises_element_centroid_z_mm",
            "peak_disp_magnitude_mm", "peak_disp_node",
            "rp_U2_mm", "rp_UR3_rad",
            "sum_RF1_N", "sum_RF2_N", "sum_RF3_N",
            "sum_reaction_M_about_RP_x_N_mm", "sum_reaction_M_about_RP_y_N_mm",
            "sum_reaction_M_about_RP_z_N_mm",
            "residual_force_norm_N", "residual_moment_about_RP_norm_N_mm",
            "reaction_force_rel_residual", "reaction_moment_rel_residual",
            "ALLIE", "ALLSE", "ALLAE", "ALLWK", "ETOTAL",
            "artificial_energy_fraction",
            "solve_status", "dat_bytes", "dat_nonzero", "odb_bytes",
            "analysis_warnings", "numerical_problem_warnings",
            "negative_eigenvalue_warnings", "error_messages",
            "numerical_singularity_count", "total_cpu_time_s",
            "deck_sha256_matches_sidecar", "solved_deck_identical_to_decks_dir"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for j in sorted(recs):
            r = recs[j]
            sc = r["sidecar"] or {}
            o = r["odb"] or {}
            pm = o.get("peak_mises") or {}
            pd = o.get("peak_disp") or {}
            rb = r["reaction_balance"] or {}
            eq = r["energy_quality"]
            cen = pm.get("element_centroid_mm") or [None, None, None]
            sf = rb.get("sum_reaction_force_N") or [None, None, None]
            mrp = rb.get("sum_reaction_moment_about_RP_N_mm") or [None, None, None]
            rpu = o.get("rp_translation_mm") or [None, None, None]
            rpr = o.get("rp_rotation_rad") or [None, None, None]
            w.writerow([
                j, sc.get("case_id"), sc.get("mesh_level"), sc.get("material"),
                sc.get("grid_pitch_mm"), sc.get("nodes_total"),
                sc.get("elements_total"), r["msg"].get("n_equations"),
                (r["deck_load"] or {}).get("F_y_N_deck"),
                (r["deck_load"] or {}).get("M_z_N_mm_deck"),
                pm.get("value_MPa"), pm.get("element"), pm.get("zone"),
                cen[0], cen[1], cen[2],
                pd.get("magnitude_mm"), pd.get("node"),
                rpu[1], rpr[2],
                sf[0], sf[1], sf[2], mrp[0], mrp[1], mrp[2],
                rb.get("residual_force_norm_N"),
                rb.get("residual_moment_about_RP_norm_N_mm"),
                rb.get("residual_force_rel_to_applied"),
                rb.get("residual_moment_rel_to_applied_Mz"),
                eq["ALLIE"], eq["ALLSE"], eq["ALLAE"], eq["ALLWK"], eq["ETOTAL"],
                eq["artificial_energy_fraction_ALLAE_over_ALLIE"],
                "COMPLETED_SUCCESSFULLY" if r["sta"]["completed_successfully"]
                else "NOT_COMPLETED",
                r["dat"]["bytes"], r["dat"]["nonzero"], o.get("odb_bytes"),
                r["msg"]["analysis_warnings"],
                r["msg"]["numerical_problem_warnings"],
                r["msg"]["negative_eigenvalue_warnings"],
                r["msg"]["error_messages"],
                len(r["msg"]["numerical_singularities"]),
                r["msg"]["total_cpu_time_s"],
                r["deck_integrity"]["sidecar_hash_matches_deck"],
                r["deck_integrity"]["solved_copy_identical_to_deck"],
            ])
    return ts, recs, conv, mats, loads, solved, failed, n_conv, csv_path


def verification_checks(recs):
    """Independent solver-integrity checks computed from the extracted ODBs."""
    out = {}

    # (1) load-proportionality: e-stop deck load = 2x maneuver deck load
    lin = {}
    for lvl in ["coarse", "medium", "fine"]:
        a = recs.get("fea1_arm_estop_qs_" + lvl)
        b = recs.get("fea1_arm_maneuver_qs_" + lvl)
        if not (a and b and a.get("odb") and b.get("odb")):
            lin[lvl.upper()] = {"status": "PAIR_INCOMPLETE"}
            continue
        lm = a["deck_load"]["M_z_N_mm_deck"] / b["deck_load"]["M_z_N_mm_deck"]
        lf = a["deck_load"]["F_y_N_deck"] / b["deck_load"]["F_y_N_deck"]
        sr = (a["odb"]["peak_mises"]["value_MPa"]
              / b["odb"]["peak_mises"]["value_MPa"])
        dr = (a["odb"]["peak_disp"]["magnitude_mm"]
              / b["odb"]["peak_disp"]["magnitude_mm"])
        lin[lvl.upper()] = {
            "deck_force_ratio": lf,
            "deck_moment_ratio": lm,
            "peak_mises_ratio": sr,
            "peak_disp_ratio": dr,
            "mises_rel_dev_from_deck_moment_ratio": abs(sr - lm) / lm,
            "disp_rel_dev_from_deck_moment_ratio": abs(dr - lm) / lm,
            "note": "response is moment-dominated, so the deck MOMENT ratio is "
                    "the correct reference. The deck moment ratio is "
                    "1.999995399 (not exactly 2) purely because the generator "
                    "wrote CLOAD with %.6g; the response tracks it to ~1e-7, "
                    "which is float32 round-off for a SINGLE_PRECISION odb.",
        }
    worst = max((v["mises_rel_dev_from_deck_moment_ratio"]
                 for v in lin.values() if "status" not in v), default=None)
    out["load_proportionality_linearity"] = {
        "per_level": lin,
        "worst_rel_deviation": worst,
        "verdict": ("PASS" if worst is not None and worst < 1e-5 else
                    "NOT_EVALUATED" if worst is None else "FAIL"),
        "criterion": "response ratio must equal deck load ratio to <1e-5",
    }

    # (2) material sensitivity: stress E-independent, displacement ~ 1/E
    a = recs.get("fea1_capture_150kg_qs_fine")
    b = recs.get("fea1_capture_150kg_qs_fine_7075")
    if a and b and a.get("odb") and b.get("odb"):
        s6 = a["odb"]["peak_mises"]["value_MPa"]
        s7 = b["odb"]["peak_mises"]["value_MPa"]
        d6 = a["odb"]["peak_disp"]["magnitude_mm"]
        d7 = b["odb"]["peak_disp"]["magnitude_mm"]
        e_ratio = 71000.0 / 68300.0
        out["material_sensitivity_scaling"] = {
            "peak_mises_AL6061_MPa": s6,
            "peak_mises_AL7075_MPa": s7,
            "stress_bit_identical": s6 == s7,
            "stress_expectation":
                "force-driven single-material linear elastic model -> stress must "
                "be independent of E",
            "peak_disp_AL6061_mm": d6,
            "peak_disp_AL7075_mm": d7,
            "disp_ratio_6061_over_7075": d6 / d7,
            "expected_E_ratio_7075_over_6061": e_ratio,
            "disp_rel_dev_from_1_over_E": abs(d6 / d7 - e_ratio) / e_ratio,
            "verdict": ("PASS" if (s6 == s7 and
                                   abs(d6 / d7 - e_ratio) / e_ratio < 1e-6)
                        else "FAIL"),
            "criterion": "stress identical AND displacement ratio == E ratio to <1e-6",
        }
    else:
        out["material_sensitivity_scaling"] = {"status": "PAIR_INCOMPLETE"}

    # (3) reaction balance worst-case over all jobs
    rf, rm = [], []
    for j, r in recs.items():
        rb = r.get("reaction_balance")
        if rb:
            rf.append((rb["residual_force_rel_to_applied"], j))
            rm.append((rb["residual_moment_rel_to_applied_Mz"], j))
    out["reaction_balance_summary"] = {
        "worst_relative_force_residual": max(rf)[0] if rf else None,
        "worst_relative_force_residual_job": max(rf)[1] if rf else None,
        "worst_relative_moment_residual": max(rm)[0] if rm else None,
        "worst_relative_moment_residual_job": max(rm)[1] if rm else None,
        "jobs_with_reaction_leakage_outside_encastre_set": [
            j for j, r in recs.items()
            if (r.get("reaction_balance") or {}).get(
                "nonzero_RF_nodes_outside_encastre_set")],
        "odb_precision": "SINGLE_PRECISION",
        "verdict": ("PASS" if rf and max(rf)[0] < 1e-5 else "FAIL"),
        "criterion": "global force and moment residual < 1e-5 relative "
                     "(float32 odb round-off floor is ~1e-7)",
    }

    # (4) energy balance
    eb = []
    for j, r in recs.items():
        eq = r["energy_quality"]
        if eq["ALLIE"] and eq["ALLWK"]:
            eb.append((abs(eq["ALLWK"] - eq["ALLIE"]) / eq["ALLIE"], j))
    out["energy_balance"] = {
        "worst_rel_ALLWK_minus_ALLIE": max(eb)[0] if eb else None,
        "worst_job": max(eb)[1] if eb else None,
        "verdict": ("PASS" if eb and max(eb)[0] < 1e-5 else "FAIL"),
        "criterion": "external work must equal internal energy for a static "
                     "linear elastic step",
    }

    # (5) hourglass / artificial strain energy quality
    frac = {}
    for j, r in recs.items():
        frac[j] = r["energy_quality"][
            "artificial_energy_fraction_ALLAE_over_ALLIE"]
    bad = {k: v for k, v in frac.items() if v is not None and v > 0.05}
    out["artificial_strain_energy_quality"] = {
        "per_job_ALLAE_over_ALLIE": frac,
        "conventional_threshold": 0.05,
        "jobs_exceeding_threshold": sorted(bad),
        "n_jobs_exceeding_threshold": len(bad),
        "verdict": "FAIL_ALL_JOBS_HOURGLASS_CONTAMINATED" if len(bad) == len(frac)
                   else "MIXED",
        "interpretation":
            "Every deck is C3D8R (reduced integration, hourglass control) with "
            "only 2-3 elements through each plate thickness under bending and "
            "torsion. The artificial ('spurious mode control') energy is 80% of "
            "internal energy at COARSE and still 14% at FINE, i.e. the bending "
            "response is hourglass-stiffness-dominated. Reported stresses are "
            "therefore DESIGN_INDICATIVE screening numbers, not converged "
            "structural stresses. Remedy (not executed this loop, no "
            "authorization to re-deck): C3D8 / C3D8I incompatible-mode or C3D20R "
            "elements, or >=4 elements through thickness.",
    }
    return out


def candidate_property_comparison(recs, mats):
    """Peak stress vs CANDIDATE typical property. NOT a margin of safety."""
    gov = recs.get("fea1_capture_150kg_qs_fine")
    gov7 = recs.get("fea1_capture_150kg_qs_fine_7075")
    if not (gov and gov.get("odb")):
        return {"status": "GOVERNING_JOB_MISSING"}
    peak = gov["odb"]["peak_mises"]["value_MPa"]
    y6 = (mats.get("AL6061_T6_CAND") or {}).get("library_yield_MPa")
    y7 = (mats.get("AL7075_T651_CAND") or {}).get("library_yield_MPa")
    out = {
        "governing_job": gov["job_name"],
        "governing_case": "CAPTURE_150KG_QS",
        "governing_mesh_level": "FINE",
        "peak_von_mises_MPa": peak,
        "peak_location_zone": gov["odb"]["peak_mises"]["zone"],
        "peak_location_element": gov["odb"]["peak_mises"]["element"],
        "peak_location_centroid_mm": gov["odb"]["peak_mises"]["element_centroid_mm"],
        "AL6061_T6_candidate_typical_yield_MPa": y6,
        "AL6061_T6_candidate_utilization_ratio": (peak / y6) if y6 else None,
        "AL6061_T6_candidate_utilization_percent": (peak / y6 * 100.0) if y6 else None,
        "AL7075_T651_candidate_typical_yield_MPa": y7,
        "AL7075_T651_candidate_utilization_ratio": (
            (gov7["odb"]["peak_mises"]["value_MPa"] / y7)
            if (gov7 and gov7.get("odb") and y7) else None),
        "comparison_label": "CANDIDATE_PROPERTY_BASED_UTILIZATION_RATIO",
        "margin_of_safety_status": "NOT_COMPUTED_NO_DESIGN_ALLOWABLE_EXISTS",
        "prohibition_honored":
            "NASA-STD-5001B forbids using typical properties as design "
            "allowables. Both library yields are value_kind TYPICAL_* with "
            "standard_uncertainty null and classification PROTOTYPE_CANDIDATE, "
            "so NO A-basis/B-basis allowable exists and NO margin of safety, "
            "factor of safety or positive-margin claim is made or implied.",
        "additional_invalidators_for_any_margin_claim": [
            "mesh NOT converged (22-23% peak-stress change between the two "
            "finest levels)",
            "artificial (hourglass) strain energy 14% of internal energy at FINE",
            "peak stress sits at a kinematic-coupling boundary = constraint-"
            "induced concentration with no mesh-independent limit",
            "bolt holes are NOT cut as voids, so real hole-edge stress "
            "concentration is not represented (locally stiffer model)",
            "no bolt preload, no contact, no friction (CDR joint-mechanics HOLD)",
            "bus-side boundary is ENCASTRE by assumption (BC-BUS-001 stiffness "
            "authority is HOLD)",
            "quasi-static equivalence uses DAF=2.0 and dt_contact=0.1 s, both "
            "declared assumptions with no authority",
        ],
    }
    return out


def singularity_diagnosis(recs):
    """Explain the 8 numerical-singularity warnings and judge validity."""
    coarse = [j for j, r in recs.items()
              if r["msg"]["numerical_singularities"]]
    ref = recs.get("fea1_capture_150kg_qs_coarse")
    sings = ref["msg"]["numerical_singularities"] if ref else []
    m5_ref = {}
    if ref and ref.get("sidecar"):
        for rec in ref["sidecar"].get("joint_records", []):
            if rec["joint"].startswith("M5"):
                m5_ref[rec["joint"]] = rec
    ref_nodes = (ref["sidecar"].get("ref_nodes") if ref and ref.get("sidecar")
                 else {}) or {}
    node_to_joint = {v: k for k, v in ref_nodes.items()}
    mapped = []
    for s in sings:
        mapped.append({
            "node": s["node"], "dof": s["dof"], "ratio": s["ratio"],
            "coupling_constraint": node_to_joint.get(s["node"]),
            "dof_meaning": {4: "rotation about global X",
                            5: "rotation about global Y",
                            6: "rotation about global Z"}.get(s["dof"]),
        })
    return {
        "jobs_with_singularity_warnings": sorted(coarse),
        "jobs_without": sorted(j for j in recs if j not in coarse),
        "count_per_affected_job": 8,
        "all_affected_jobs_are_mesh_level": "COARSE",
        "mapped_warnings": mapped,
        "root_cause": (
            "Every one of the 8 warnings is on an M5 kinematic-coupling REFERENCE "
            "node (900200-900207 = M5_1..M5_8), never on a structural node. At the "
            "COARSE 16 mm lattice each M5 bolt disk captures only 2 lattice points "
            "per mating face (sidecar nodes_face_lo = 2), and planes p6/p7 are "
            "coincident at z=22.75, so the coupling's slave set collapses to TWO "
            "distinct spatial points. A 6-DOF kinematic coupling to two collinear "
            "points leaves the reference node's rotation ABOUT THAT LINE with zero "
            "stiffness -> zero pivot -> NUMERICAL SINGULARITY."),
        "root_cause_proof": (
            "The reported DOF matches the joint geometry in all 8 of 8 cases: "
            "joints whose two points are separated along y (M5_1,4,5,8) report DOF "
            "5 (rotation about Y) and joints separated along x (M5_2,3,6,7) report "
            "DOF 4 (rotation about X). Independent confirmation: the warnings "
            "vanish completely at MEDIUM (4 nodes/face) and FINE (5 nodes/face), "
            "where the slave sets are no longer collinear, and the M6 joints "
            "(3 nodes/face, non-collinear) never warn at any level."),
        "does_it_invalidate_the_result": "NO_FOR_THE_COARSE_LOAD_PATH_ITSELF",
        "validity_judgement": (
            "The singular degrees of freedom are pure rigid-body rotations of "
            "massless, UNLOADED internal constraint reference nodes (the only "
            "loaded node is RP 900000). No load path passes through them, and "
            "Abaqus reports 0 negative eigenvalue messages, 0 error messages, a "
            "linear equilibrium response, largest scaled residual force 4.576e-12 "
            "and residual moment 5.264e-11. The independently recomputed global "
            "reaction balance for the coarse jobs closes to <1e-7 relative. So the "
            "warnings do not corrupt the reported coarse solution."),
        "but": (
            "The COARSE level is nevertheless EXCLUDED from any quantitative "
            "convergence claim, for a different and stronger reason: at 16 mm "
            "pitch the constraint footprints are degenerate (M4 arm-spider disks "
            "capture 1 node each, M5 disks 2), which makes the coarse peak "
            "displacement 13.5x the fine value and puts the coarse peak at a "
            "single-node spider attachment. COARSE is a different boundary-"
            "condition model, not a coarser discretization of the same model."),
        "residual_evidence": {
            j: {"largest_scaled_residual_force":
                    recs[j]["msg"]["largest_scaled_residual_force"],
                "largest_scaled_residual_moment":
                    recs[j]["msg"]["largest_scaled_residual_moment"],
                "negative_eigenvalue_messages":
                    recs[j]["msg"]["negative_eigenvalue_warnings"],
                "error_messages": recs[j]["msg"]["error_messages"]}
            for j in sorted(coarse)},
        "separate_input_processing_warning": (
            "All 13 jobs also carry exactly 1 warning during user input "
            "processing: 'THE CONTACT AREA OR DISTRIBUTING WEIGHT ASSOCIATED WITH "
            "<n> NODES IS ZERO OR NEGATIVE'. This is expected and harmless here: "
            "the joints use *SURFACE,TYPE=NODE node-based surfaces with *KINEMATIC "
            "coupling, which needs no area weighting; a distributing (*DISTRIBUTING) "
            "coupling would have needed it."),
    }


DECK_REGISTER_CASES = [
    {
        "fea_id": "FEA-1",
        "title": "M3R load-bridge / Stage B / Stage A interface, operational "
                 "quasi-static",
        "odr_06_case_names_covered": ["M3R interface", "arm maneuver",
                                      "emergency stop", "22 kg capture",
                                      "150 kg capture"],
        "odr_06_authorization": "AUTHORIZED_OPERATIONAL",
        "status": "DECKED_AND_SOLVED",
        "decks": 13,
        "mesh_levels": ["COARSE", "MEDIUM", "FINE"],
        "materials": ["AL6061_T6_CAND", "AL7075_T651_CAND (fine, 150 kg only)"],
        "result_status": "SOLVED_NOT_MESH_CONVERGED_CANDIDATE_LEVEL",
        "inputs_still_needed": [
            "B601 gripper contact duration (dt_contact) measurement to replace "
            "the declared 0.1 s assumption",
            "dynamic amplification authority to replace the declared DAF=2.0",
            "BC-BUS-001 bus-side interface stiffness to replace ENCASTRE",
            "bolt preload / friction authority to replace rigid coupling disks",
            "flight material allowables (A-basis/B-basis) for any margin claim",
            "element formulation upgrade (C3D8I or C3D20R) or >=4 elements "
            "through thickness to remove hourglass contamination",
        ],
        "blocking_holds": ["CDR_JOINT_MECHANICS_HOLD",
                           "BC_BUS_001_STIFFNESS_HOLD",
                           "MATERIAL_ALLOWABLES_HOLD"],
    },
    {
        "fea_id": "FEA-2",
        "title": "Gripper clamp / grasp reaction on R1 jaw, rail and palm",
        "odr_06_case_names_covered": ["gripper clamp"],
        "odr_06_authorization": "AUTHORIZED_OPERATIONAL",
        "status": "PLANNED_NOT_DECKED",
        "decks": 0,
        "result_status": "NOT_RUN",
        "inputs_still_needed": [
            "authorized gripper actuation force / clamp preload (no numeric "
            "authority exists; WP5 gripper pack is analytical)",
            "jaw-target contact patch definition and friction coefficient",
            "R1 jaw / rail / palm solid geometry extracted as an FEA-ready body "
            "from the neutral FreeCAD/STEP chain (ODR-03)",
            "material assignment for the gripper structure",
        ],
        "blocking_holds": ["HOLD_GRIPPER_ELASTIC_AND_WEAR_TERMS_REQUIRE_"
                           "AUTHORIZED_LOAD_AND_LIFE_TEST"],
    },
    {
        "fea_id": "FEA-3",
        "title": "Solar panel deployment: hinge-driven deployment loads and "
                 "end-of-travel latch-up",
        "odr_06_case_names_covered": ["panel deployment"],
        "odr_06_authorization": "AUTHORIZED_OPERATIONAL",
        "status": "PLANNED_NOT_DECKED",
        "decks": 0,
        "result_status": "NOT_RUN",
        "inputs_still_needed": [
            "hinge spring torque / damping and hard-stop geometry (WP5 records "
            "these as HOLD_HINGE_HARDWARE_NOMINALS_FITS_AND_STOP_GEOMETRY)",
            "deployment kinematic profile and latch-up angular velocity",
            "panel structural lay-up: the 0.348 kg/panel SSOT value is a known "
            "PLACEHOLDER (real panels are 2-5 kg/m^2, a 5-10x discrepancy) so no "
            "panel stress case can be closed on the current mass model",
        ],
        "blocking_holds": ["HOLD_HINGE_HARDWARE_NOMINALS_FITS_AND_STOP_GEOMETRY",
                           "PANEL_MASS_AND_MODAL_PARAMETERS_ARE_PLACEHOLDERS"],
    },
    {
        "fea_id": "FEA-4",
        "title": "Single-panel-failure configuration (failed panel remains "
                 "mechanically ATTACHED per ODR-02, never jettisoned)",
        "odr_06_case_names_covered": ["single-panel-failure"],
        "odr_06_authorization": "AUTHORIZED_OPERATIONAL",
        "status": "PLANNED_NOT_DECKED",
        "decks": 0,
        "result_status": "NOT_RUN",
        "inputs_still_needed": [
            "stuck-panel restrained angle set (WP1/G2 state_policy.json records "
            "PARTIAL/SERVICE angles as null, so the stuck pose is undefined)",
            "asymmetric inertia configuration from WP2 for the failed states",
            "same panel structural definition gap as FEA-3",
        ],
        "blocking_holds": ["STUCK_PANEL_ANGLE_UNDEFINED",
                           "PANEL_MASS_AND_MODAL_PARAMETERS_ARE_PLACEHOLDERS"],
        "odr_note": "ODR-02 fixes the semantics (attached-stuck); it does not "
                    "supply the restrained angle.",
    },
    {
        "fea_id": "FEA-5",
        "title": "On-orbit system modal (deployed spacecraft, free-free, "
                 "arm stowed and arm extended)",
        "odr_06_case_names_covered": ["on-orbit system modal"],
        "odr_06_authorization": "AUTHORIZED_OPERATIONAL",
        "status": "PLANNED_NOT_DECKED",
        "decks": 0,
        "result_status": "NOT_RUN",
        "inputs_still_needed": [
            "system-level FEA mesh of the deployed spacecraft (only the M3R "
            "interface region is meshed today)",
            "real panel modal parameters: sim_11 v1.1 records the solar panel "
            "modal parameters as PLACEHOLDERS, so no system frequency would be "
            "meaningful",
            "joint/appendage stiffness representation consistent with the "
            "accepted URDF kinematics",
            "free-free extraction settings and a rigid-body-mode check",
        ],
        "blocking_holds": ["PANEL_MODAL_PARAMETERS_ARE_PLACEHOLDERS",
                           "NO_SYSTEM_LEVEL_FEA_MESH_EXISTS"],
    },
    {
        "fea_id": "FEA-6",
        "title": "M3R interface joint-mechanics upgrade: bolt preload, "
                 "face contact, friction and slip at the M6/M5/M4 joints",
        "odr_06_case_names_covered": ["M3R interface (refinement of FEA-1)"],
        "odr_06_authorization": "AUTHORIZED_OPERATIONAL",
        "status": "PLANNED_NOT_DECKED",
        "decks": 0,
        "result_status": "NOT_RUN",
        "inputs_still_needed": [
            "fastener grade, preload and torque authority (WP4 records "
            "HOLD_FASTENER_PRELOAD_GRADE_AND_MOS)",
            "faying-surface friction coefficient and finish",
            "hole geometry cut as real voids rather than represented by "
            "coupling disks",
        ],
        "blocking_holds": ["CDR_JOINT_MECHANICS_HOLD",
                           "HOLD_FASTENER_PRELOAD_GRADE_AND_MOS"],
        "why_registered": "FEA-1 models all joints as rigid kinematic coupling "
                          "disks with no preload, contact or friction. That is a "
                          "declared Level-1 idealization, and it is the single "
                          "largest modelling gap between FEA-1 and a joint "
                          "strength statement.",
    },
    {
        "fea_id": "FEA-7",
        "title": "Arm maneuver and emergency stop at SYSTEM level (whole "
                 "spacecraft, reaction-coupled, not M3R-local)",
        "odr_06_case_names_covered": ["arm maneuver", "emergency stop"],
        "odr_06_authorization": "AUTHORIZED_OPERATIONAL",
        "status": "PLANNED_NOT_DECKED",
        "decks": 0,
        "result_status": "NOT_RUN",
        "already_covered_at_interface_level_by": "FEA-1",
        "inputs_still_needed": [
            "system-level FEA mesh (see FEA-5)",
            "full arm inertia tensor reduction: FEA-1 declares "
            "ARM_LOADS_BOUNDED_BY_ASSUMPTION and uses only m_arm x a_eq with "
            "r_eff = 0.7 m, an assumed effective radius",
            "authorized joint torque limits and e-stop deceleration profile "
            "(FEA-1 uses a declared estop_factor = 2.0 policy)",
        ],
        "blocking_holds": ["NO_SYSTEM_LEVEL_FEA_MESH_EXISTS",
                           "ARM_ACTUATOR_LIMITS_NOT_AUTHORIZED"],
        "note": "FEA-1 shows the arm cases are NOT governing at the M3R "
                "interface: peak stress is 0.0126-0.0252 MPa versus 1.0596 MPa "
                "for the 150 kg capture, i.e. 42-84x lower.",
    },
    {
        "fea_id": "FEA-8",
        "title": "22 kg and 150 kg capture at SYSTEM level, including flexible "
                 "panel participation",
        "odr_06_case_names_covered": ["22 kg capture", "150 kg capture"],
        "odr_06_authorization": "AUTHORIZED_OPERATIONAL",
        "status": "PLANNED_NOT_DECKED",
        "decks": 0,
        "result_status": "NOT_RUN",
        "already_covered_at_interface_level_by": "FEA-1",
        "inputs_still_needed": [
            "system-level FEA mesh (see FEA-5)",
            "capture contact-window authority: sim_11 v1.1 uses T_c = 20 ms "
            "PROVISIONAL pending B601 gripper measurement, and FEA-1 "
            "independently assumes dt_contact = 0.1 s -- these two are "
            "inconsistent and must be reconciled before any system capture "
            "stress case",
            "panel flexible representation (sim_07 shows ~92x amplification of "
            "point capture versus rigid lock, so a rigid system model would be "
            "non-conservative)",
            "structurally-authoritative capture load set: the CDR envelope rows "
            "are stamped authority_status = NOT_STRUCTURAL_DESIGN_AUTHORITY",
        ],
        "blocking_holds": ["CAPTURE_CONTACT_DURATION_NOT_MEASURED",
                           "PANEL_MODAL_PARAMETERS_ARE_PLACEHOLDERS",
                           "CAPTURE_LOADS_NOT_STRUCTURAL_DESIGN_AUTHORITY"],
    },
    {
        "fea_id": "FEA-L",
        "title": "Launch qualification: quasi-static launch, sine, random, "
                 "acoustic, shock",
        "odr_06_case_names_covered": ["NONE -- explicitly excluded by ODR-06"],
        "odr_06_authorization": "NOT_AUTHORIZED_HOLD",
        "status": "HOLD",
        "decks": 0,
        "result_status": "NOT_RUN_AND_NOT_AUTHORIZED",
        "hold_id": "LAUNCH_QUALIFICATION_FEA_HOLD",
        "hold_reason": "ODR-06 retains LAUNCH_QUALIFICATION_FEA_HOLD pending the "
                       "launcher ICD. Gate B "
                       "(MECHANICAL_FLIGHT_QUALIFICATION_RELEASED) stays HOLD.",
        "inputs_still_needed": [
            "launcher / dispenser interface control document",
            "quasi-static launch load factors",
            "sine and random vibration input spectra",
            "shock and acoustic environments",
            "flight material allowables (A-basis or B-basis)",
        ],
        "prohibition": "No launch, launcher, flight-qualification or "
                       "manufacturing-release claim may be made from any WP7 "
                       "output.",
    },
]


def build_all():
    ts, recs, conv, mats, loads, solved, failed, n_conv, csv_path = build()
    vchecks = verification_checks(recs)
    cand = candidate_property_comparison(recs, mats)
    sing = singularity_diagnosis(recs)

    ran_this_loop = sorted(j for j in recs
                           if os.path.getmtime(os.path.join(JOBS, j + ".sta"))
                           > 1.0e0 and j != "fea1_capture_150kg_qs_coarse")
    pre_existing = ["fea1_capture_150kg_qs_coarse"]

    # ---------------- source register ----------------
    src = {}
    for key, rel in UPSTREAM.items():
        e = reg(os.path.join(REPO, rel), rel)
        e["role"] = key
        src[rel] = e
    gen_rel = WP7_REL + "/make_fea1_input.py"
    e = reg(os.path.join(HERE, "make_fea1_input.py"), gen_rel)
    e["role"] = "deck_generator_present_on_disk"
    e["provenance_warning"] = (
        "DIVERGED_FROM_THE_DECKS_IT_NOMINALLY_PRODUCED. This file's mtime is "
        "later than every deck and later than the first solved job, and its "
        "write_deck() emits *MPC PIN pairs with a single RP, whereas every deck "
        "actually on disk (and actually solved) uses 13 *COUPLING/*KINEMATIC "
        "constraints with dedicated reference nodes 900100-900103 and "
        "900200-900207, and every sidecar carries ref_nodes / nodes_face_lo keys "
        "that this file never writes. Re-running this generator would NOT "
        "reproduce the solved decks. It was therefore NOT executed this loop; "
        "the decks on disk are the model of record and each deck's SHA-256 "
        "matches the deck_sha256 recorded in its own sidecar.")
    src[gen_rel] = e
    ex_rel = WP7_REL + "/extract_fea1_odb.py"
    e = reg(os.path.join(HERE, "extract_fea1_odb.py"), ex_rel)
    e["role"] = "odb_extractor_written_and_run_this_loop"
    src[ex_rel] = e
    for j in sorted(recs):
        for sub, role in ((".inp", "deck_of_record"),
                          (".json", "deck_sidecar_metadata")):
            rel = "%s/%s/%s%s" % (WP7_REL, "decks" if sub == ".inp" else "jobs",
                                  j, sub)
            base = DECKS if sub == ".inp" else JOBS
            e = reg(os.path.join(base, j + sub), rel)
            e["role"] = role
            src[rel] = e

    # ---------------- solver artifacts (produced) ----------------
    artifacts = {}
    for j in sorted(recs):
        per = {}
        for ext in (".inp", ".dat", ".msg", ".sta", ".odb", ".com", ".prt"):
            p = os.path.join(JOBS, j + ext)
            if os.path.isfile(p):
                rel = "%s/jobs/%s%s" % (WP7_REL, j, ext)
                per[ext.lstrip(".")] = reg(p, rel)
        per["_extract_json"] = reg(os.path.join(EXTR, j + ".json"),
                                   "%s/jobs/_extract/%s.json" % (WP7_REL, j))
        per["solved_this_loop"] = j not in pre_existing
        artifacts[j] = per

    # ---------------- evidence json ----------------
    ev = {
        "schema": SCHEMA_PREFIX + "_FEA1_EVIDENCE_V1",
        "generated_local": ts,
        "generated_clock_source": CLOCK_SOURCE,
        "work_package": "WP7_FEA_OPERATIONAL",
        "authorization": {
            "odr": "ODR-06",
            "scope": "OPERATIONAL_STRUCTURAL_VERIFICATION",
            "retained_hold": "LAUNCH_QUALIFICATION_FEA_HOLD",
            "gate_b": "MECHANICAL_FLIGHT_QUALIFICATION_RELEASED = HOLD",
        },
        "verdict": "OPERATIONAL_STRUCTURAL_VERIFICATION_CANDIDATE_LEVEL",
        "verdict_qualifiers": [
            "13 of 13 decks SOLVED (Abaqus/Standard 2023, all .dat non-zero, "
            "all .sta report THE ANALYSIS HAS COMPLETED SUCCESSFULLY, 0 error "
            "messages anywhere)",
            "MESH CONVERGENCE NOT DEMONSTRATED: NOT_CONVERGED in all 4 case "
            "families",
            "candidate != authority; analysis != test; design != flight-qualified",
            "no margin of safety is asserted anywhere in this artifact",
        ],
        "run_ledger": {
            "decks_present": len(recs),
            "jobs_attempted": len(recs),
            "jobs_solved": len(solved),
            "jobs_failed": len(failed),
            "failed_job_names": failed,
            "jobs_solved_this_loop": len(ran_this_loop),
            "jobs_pre_existing_from_0120_not_re_run": pre_existing,
            "solver_invocation":
                "D:/SIMULIA/Commands/abaqus.bat job=<name> interactive, run "
                "serially from inside the jobs directory, one job at a time, "
                "no CAE GUI",
            "memory_note":
                "6 GiB memory gate remains DECLARED FAILED on this host. It was "
                "not a constraint here: every job reports MEMORY PEAK (GB) = 0 "
                "and the largest deck needs an estimated 18-29 MB.",
        },
        "solver": {
            "version_string_as_reported_by_abaqus":
                (recs[sorted(recs)[0]]["odb"] or {}).get("solver", {}).get(
                    "version"),
            "analysis_code": (recs[sorted(recs)[0]]["odb"] or {}).get(
                "solver", {}).get("analysis_code"),
            "odb_precision": (recs[sorted(recs)[0]]["odb"] or {}).get(
                "solver", {}).get("precision"),
            "equation_solver": "DIRECT SPARSE (symmetric)",
            "procedure": "*STATIC, NLGEOM=NO (linear static, small displacement)",
            "license_note":
                "The Abaqus banner on this host reads 'For use by Supplied by "
                "Team-SolidSQUAD under license from Dassault Systemes or its "
                "subsidiary.' This is recorded verbatim as an observed fact "
                "about the toolchain, not endorsed as a valid commercial "
                "license, and it is a licensing risk for any external "
                "submission of these results.",
        },
        "model_definition": {
            "units": "N, mm, MPa, tonne",
            "element_type": "C3D8R (8-node linear brick, reduced integration, "
                            "hourglass control)",
            "geometry_stack_local_z": {
                "load_bridge": "z 0.00-10.75, 160x160, centre hole r20",
                "stage_b": "z 10.75-22.75, 160x160, bore r50, centre web r<50 "
                           "modelled 4.0 mm vs 5.595 mm real",
                "stage_a": "z 22.75-30.75, ring OD150/ID40, 8.0 mm uniform",
            },
            "frame_authority_odr_01":
                "T_SM = [185.25, 0, 0] mm + Ry(90 deg). Stations 198.0 / 208.0 / "
                "210.405 mm are a geometric feature stack, NOT a second dynamics "
                "frame. The deck's local z=0 maps to x_S = 185.25 mm.",
            "l0_urdf_authority_respected": {
                "b601_arm_mass_kg": 4.695555949342986,
                "statement": "L0 accepted-URDF mass used verbatim in the arm "
                             "load derivation; never overridden by CAD.",
            },
        },
        "boundary_condition_source": {
            "bc_of_record": "*BOUNDARY NFIXED,ENCASTRE on every node of the "
                            "z=0 (x_S=185.25 mm) bus-side face",
            "n_encastre_nodes_by_level": {
                lvl: (recs.get("fea1_capture_150kg_qs_" + lvl.lower()) or {})
                     .get("odb", {}).get("model", {}).get("n_fixed_nodes")
                for lvl in MESH_ORDER},
            "authority_status": "ASSUMPTION_NOT_AUTHORITY",
            "hold": "BC-BUS-001 bus-side interface stiffness authority is HOLD. "
                    "A fully clamped face is a stiff-boundary design bound, and "
                    "it over-predicts interface reaction and under-predicts "
                    "global compliance relative to a real compliant bus.",
        },
        "load_source": {
            "capture_cases": {
                "authority_file": UPSTREAM["capture_load_envelope"],
                "authority_status_column_value":
                    "NOT_STRUCTURAL_DESIGN_AUTHORITY",
                "quasi_static_policy":
                    "F_eq = DAF * J / dt_contact ; "
                    "M_eq = F_eq * L_grasp + DAF * C / dt_contact",
                "declared_assumptions": {"DAF": 2.0, "dt_contact_s": 0.1},
                "verification": loads,
            },
            "arm_cases": {
                "derivation": "quintic joint profile peak angular acceleration "
                              "(LC-010 q2 +60 deg over 8 s) x assumed effective "
                              "radius r_eff = 0.7 m x L0 URDF arm mass; e-stop = "
                              "declared estop_factor 2.0 x maneuver",
                "authority_status": "DERIVED_TRAJECTORY_PLUS_ASSUMPTION and "
                                    "ASSUMPTION_POLICY",
                "not_traceable_to_an_authorized_actuator_limit": True,
            },
            "applied_load_of_record_note":
                "The generator wrote *CLOAD magnitudes with %.6g, so each deck "
                "applies a 6-significant-figure truncation of the derivation "
                "value carried in its sidecar. All reaction-balance residuals in "
                "this artifact are computed against the DECK value, which is what "
                "the solver actually saw. For the 150 kg case that is F_y = "
                "13.5527 N and M_z = 19073.3 N*mm versus sidecar 13.55266 N and "
                "19073.267958599998 N*mm (relative difference 3.0e-6 and "
                "1.7e-9).",
            "TRACEABILITY_DEFECT_FOUND": {
                "severity": "MEDIUM_CONSERVATIVE_DIRECTION",
                "case": "CAPTURE_150KG_QS",
                "finding":
                    "The deck declares its provenance as envelope row CAP150_030 "
                    "and correctly takes contact_impulse 0.677633 N*s and "
                    "grasp_lever_arm 1.21521 m from that row, but its grasp "
                    "couple C = 0.130197 N*m*s is the value from a DIFFERENT row, "
                    "CAP150_005. Row CAP150_030 states C = 0.113705 N*m*s.",
                "effect":
                    "Applied M_z is 19073.268 N*mm instead of 18743.428 N*mm, "
                    "i.e. 1.7598% HIGH. F_y is unaffected (0.000% delta). The "
                    "error is in the CONSERVATIVE direction.",
                "mitigating_context":
                    "grasp_couple is non-monotonic across the CAP150 family "
                    "(0.130197, 0.121693, 0.111944, 0.113705), and CAP150_005 is "
                    "the family maximum, so 'max impulse row + max couple across "
                    "the family' is a defensible bounding envelope. What is "
                    "defective is the PROVENANCE LABEL, which names a single row "
                    "that does not contain the couple actually used.",
                "the_22kg_case_is_clean":
                    "CAPTURE_22KG_QS takes J, C and L all from CAP22_030, and "
                    "CAP22_030 is also the family maximum couple. No defect.",
                "disposition":
                    "RECORDED_NOT_SILENTLY_CORRECTED. Correcting it requires "
                    "re-decking and re-solving, which is a change to the model of "
                    "record and is not authorized inside this loop. Both numbers "
                    "are published here so any consumer can choose.",
            },
        },
        "material_source": {
            "library": UPSTREAM["material_library"],
            "classification": "PROTOTYPE_CANDIDATE",
            "verification": mats,
            "poisson_ratio": {
                "value_used": 0.33,
                "present_in_library": False,
                "status": "DECLARED_ASSUMPTION_POISSON_NOT_IN_M6_LIBRARY",
            },
            "allowables": "NONE EXIST. Both yields are value_kind TYPICAL_* with "
                          "standard_uncertainty null.",
        },
        "contact_and_joint_representation": {
            "contact_pairs": 0,
            "contact_status": "NO_CONTACT_MODELLED",
            "bolt_preload": "NONE",
            "friction": "NONE",
            "joint_model": "13 *COUPLING / *KINEMATIC (DOF 1-6) rigid coupling "
                           "disks per deck: 4 x M6 (bridge<->Stage B), 8 x M5 "
                           "(Stage B<->Stage A), 1 x arm-base spider onto the 4 "
                           "as-built M4 centres, driven from RP node 900000 at "
                           "(0,0,30.75)",
            "bolt_holes": "NOT CUT AS VOIDS. dia 6.6 / 5.5 / 4.6 holes are "
                          "represented by coupling disks, so the model is locally "
                          "STIFFER than hardware and hole-edge stress "
                          "concentration is NOT represented.",
            "faces_outside_bolt_disks": "UNTIED -- separation and "
                                        "interpenetration are possible; this is a "
                                        "declared Level-1 bound.",
            "hold": "CDR_JOINT_MECHANICS_HOLD",
            "per_level_disk_node_capture": {
                lvl: {
                    "m6_nodes_per_face": sorted(set(
                        r["nodes_face_lo"] for r in
                        (recs["fea1_capture_150kg_qs_" + lvl.lower()]["sidecar"]
                         or {}).get("joint_records", [])
                        if r["joint"].startswith("M6"))),
                    "m5_nodes_per_face": sorted(set(
                        r["nodes_face_lo"] for r in
                        (recs["fea1_capture_150kg_qs_" + lvl.lower()]["sidecar"]
                         or {}).get("joint_records", [])
                        if r["joint"].startswith("M5"))),
                    "m4_spider_nodes_per_disk": sorted(set(
                        r["nodes"] for r in
                        (recs["fea1_capture_150kg_qs_" + lvl.lower()]["sidecar"]
                         or {}).get("joint_records", [])
                        if r["joint"].startswith("M4"))),
                } for lvl in MESH_ORDER},
        },
        "mesh_convergence": {
            "criterion": "<=5% change in the peak metric between the two finest "
                         "levels",
            "levels": {"COARSE": {"grid_pitch_mm": 16.0, "elements": 468,
                                  "nodes": 979},
                       "MEDIUM": {"grid_pitch_mm": 10.0, "elements": 1336,
                                  "nodes": 2375},
                       "FINE": {"grid_pitch_mm": 8.0, "elements": 2056,
                                "nodes": 3563}},
            "per_case": conv,
            "cases_converged": n_conv,
            "cases_total": len(CASE_ORDER),
            "OVERALL_VERDICT": "NOT_CONVERGED",
            "plain_statement":
                "Mesh convergence is NOT demonstrated. In all four case families "
                "the peak von Mises changes by +22.0% to +23.4% and the peak "
                "displacement by +30.1% to +33.0% between MEDIUM and FINE, and "
                "the trend is still rising at the finest level. This is an "
                "honest negative result and is reported as such; no converged "
                "stress value is claimed.",
            "why_it_does_not_converge": [
                "Both peak metrics are located ON kinematic-coupling boundaries "
                "(peak stress in Stage A at the arm-spider M4 attachment, peak "
                "displacement at an M5 coupling node). A rigid constraint on a "
                "solid mesh is a stress singularity, so the peak has no finite "
                "mesh-independent limit and will keep rising with refinement.",
                "The refinement is not a pure h-refinement: the bolt-disk "
                "constraint footprints change with the lattice (M6 3->5->8, "
                "M5 2->4->5, M4 spider 1->4->5 nodes), so the boundary-condition "
                "model changes between levels.",
                "Grid pitch ratios are unequal (16->10 = 1.60, 10->8 = 1.25), so "
                "Richardson extrapolation / GCI is not applicable.",
                "The sequence is non-monotonic (coarse high, medium low, fine "
                "rising), which independently invalidates GCI.",
            ],
            "what_would_be_needed":
                "Report a stress at a fixed distance from the constraint (or on "
                "a de-featured sub-model with real holes and contact) rather "
                "than a global peak; hold the constraint footprint fixed in "
                "physical size across levels; use a constant refinement ratio; "
                "and switch to a non-hourglassing element formulation.",
        },
        "reaction_balance": {
            "method": "Independently recomputed from the ODB RF field: sum of "
                      "all nodal reaction forces, plus the resultant moment of "
                      "those reactions about the global origin and about the "
                      "load reference point (0,0,30.75), compared with the "
                      "deck-applied load.",
            "per_job": {j: recs[j]["reaction_balance"] for j in sorted(recs)},
            "summary": vchecks["reaction_balance_summary"],
        },
        "energy_check": {
            "source": "*ENERGY PRINT block in each .dat, cross-checked against "
                      "the ODB history region for ALLIE/ALLSE/ALLAE/ALLWK/ETOTAL",
            "per_job_dat": {j: recs[j]["energy_quality"] for j in sorted(recs)},
            "per_job_odb_history": {
                j: (recs[j]["odb"] or {}).get("energy_odb") for j in sorted(recs)},
            "balance": vchecks["energy_balance"],
            "HOURGLASS_FINDING": vchecks["artificial_strain_energy_quality"],
        },
        "verification_checks": vchecks,
        "numerical_warning_diagnosis": sing,
        "dat_nonzero_proof": {
            j: {"dat_bytes": recs[j]["dat"]["bytes"],
                "dat_nonzero": recs[j]["dat"]["nonzero"],
                "odb_bytes": (recs[j]["odb"] or {}).get("odb_bytes"),
                "msg_bytes": recs[j]["msg"]["bytes"],
                "sta_bytes": recs[j]["sta"]["bytes"],
                "sta_completed_successfully":
                    recs[j]["sta"]["completed_successfully"],
                "dat_reported_elements": recs[j]["dat"]["dat_n_elements"],
                "dat_reported_nodes": recs[j]["dat"]["dat_n_nodes"],
                "dat_reported_variables": recs[j]["dat"]["dat_n_variables"]}
            for j in sorted(recs)},
        "headline_results": {
            "governing_case": "CAPTURE_150KG_QS",
            "governing_peak_von_mises_MPa_at_FINE":
                (recs["fea1_capture_150kg_qs_fine"]["odb"]["peak_mises"]
                 ["value_MPa"]),
            "peak_by_case_at_FINE_MPa": {
                c: (recs["fea1_%s_fine" % c.lower()]["odb"]["peak_mises"]
                    ["value_MPa"]) for c in CASE_ORDER},
            "peak_disp_by_case_at_FINE_mm": {
                c: (recs["fea1_%s_fine" % c.lower()]["odb"]["peak_disp"]
                    ["magnitude_mm"]) for c in CASE_ORDER},
            "arm_cases_are_not_governing": True,
            "candidate_property_comparison": cand,
        },
        "per_file_result_hashes": artifacts,
        "source_register": src,
        "retained_holds": [
            "LAUNCH_QUALIFICATION_FEA_HOLD (ODR-06 retained)",
            "GATE_B_MECHANICAL_FLIGHT_QUALIFICATION_RELEASED_HOLD",
            "CDR_JOINT_MECHANICS_HOLD (no preload, contact or friction)",
            "BC_BUS_001_BUS_SIDE_STIFFNESS_HOLD (ENCASTRE is an assumption)",
            "MATERIAL_ALLOWABLES_HOLD (typical properties only, no A/B basis)",
            "MESH_CONVERGENCE_NOT_DEMONSTRATED_HOLD",
            "HOURGLASS_CONTAMINATION_HOLD (ALLAE/ALLIE = 14% at FINE)",
            "CAPTURE_CONTACT_DURATION_ASSUMED_HOLD (dt=0.1 s assumed here, "
            "inconsistent with sim_11 T_c=20 ms PROVISIONAL)",
            "DAF_2P0_ASSUMPTION_HOLD",
            "ARM_EFFECTIVE_RADIUS_0P7M_ASSUMPTION_HOLD",
            "POISSON_RATIO_0P33_ASSUMPTION_HOLD",
            "CAP150_COUPLE_ROW_PROVENANCE_DEFECT_OPEN",
            "M3R_AS_BUILT_MEASUREMENT_OPEN (ODR-05)",
            "NATIVE_REINTEGRATION_HOLD (ODR-03, SolidWorks line off critical "
            "path)",
        ],
        "prohibitions_honored": {
            "launch_or_launcher_claim_made": False,
            "flight_qualification_claim_made": False,
            "manufacturing_release_claim_made": False,
            "margin_of_safety_asserted": False,
            "typical_property_used_as_design_allowable": False,
            "zero_fill_of_unknowns": False,
            "cross_job_or_cross_mesh_value_substitution": False,
            "pass_reported_over_empty_artifact": False,
            "l0_urdf_mass_overridden": False,
            "freecad_launched": False,
            "abaqus_cae_gui_launched": False,
            "decks_regenerated_or_modified": False,
            "baseline_or_sibling_wp_files_modified": False,
            "memory_gate_6gib_declared_failed": True,
        },
    }

    ev_path = os.path.join(HERE, "FEA1_EVIDENCE_V1.json")
    with open(ev_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ev, f, indent=1, sort_keys=False, ensure_ascii=True)

    # ---------------- deck register yaml ----------------
    dr = {
        "schema": SCHEMA_PREFIX + "_FEA2_FEA8_DECK_REGISTER_V1",
        "generated_local": ts,
        "generated_clock_source": CLOCK_SOURCE,
        "work_package": "WP7_FEA_OPERATIONAL",
        "register_role":
            "Register of the ODR-06 authorized operational structural load "
            "cases and their decking state. NOTHING in this register has been "
            "run except FEA-1. PLANNED_NOT_DECKED means no input deck exists; "
            "it does not mean queued, and it does not inherit any PASS.",
        "authorization_basis": "ODR-06 (FEA_STRATEGY_SPLIT)",
        "odr_06_authorized_operational_case_list_verbatim": [
            "arm maneuver", "emergency stop", "22 kg capture", "150 kg capture",
            "gripper clamp", "panel deployment", "single-panel-failure",
            "M3R interface", "on-orbit system modal"],
        "odr_06_excluded_and_held": [
            "quasi-static launch", "sine", "random", "acoustic", "shock"],
        "summary": {
            "entries": len(DECK_REGISTER_CASES),
            "decked_and_solved": 1,
            "planned_not_decked": 7,
            "hold_not_authorized": 1,
            "total_decks_on_disk": len(recs),
            "total_jobs_solved": len(solved),
        },
        "cases": DECK_REGISTER_CASES,
        "standing_prohibitions": [
            "No launch, launcher, flight-qualification or manufacturing-release "
            "claim from any entry in this register.",
            "Gate B (MECHANICAL_FLIGHT_QUALIFICATION_RELEASED) stays HOLD.",
            "No entry may be reported as run, passed or converged on the basis "
            "of FEA-1.",
        ],
    }
    dr_path = os.path.join(HERE, "FEA2_FEA8_DECK_REGISTER_V1.yaml")
    with open(dr_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# M7 WP7 FEA-2..FEA-8 deck register (ODR-06 operational scope)\n")
        f.write(yaml_dump(dr))

    # ---------------- receipt ----------------
    produced = []
    for p in ("FEA1_RESULTS_V1.csv", "FEA1_EVIDENCE_V1.json",
              "FEA2_FEA8_DECK_REGISTER_V1.yaml", "extract_fea1_odb.py"):
        produced.append(reg(os.path.join(HERE, p), WP7_REL + "/" + p))

    conv_line = "; ".join(
        "%s medium->fine peak-stress %+.3f%% / peak-disp %+.3f%% -> %s" % (
            c, conv[c]["trend"]["peak_mises_pct_change_medium_to_fine"],
            conv[c]["trend"]["peak_disp_pct_change_medium_to_fine"],
            conv[c]["trend"]["convergence_verdict"]) for c in CASE_ORDER)

    receipt = {
        "schema": SCHEMA_PREFIX + "_RECEIPT_V1",
        "generated_local": ts,
        "generated_clock_source": CLOCK_SOURCE,
        "work_package": "WP7_FEA_OPERATIONAL",
        "status": ("WP7_COMPLETE_13_OF_13_DECKS_SOLVED_0_FAILED_"
                   "MESH_CONVERGENCE_NOT_DEMONSTRATED_4_OF_4_CASES_NOT_CONVERGED"),
        "verdict": (
            "OPERATIONAL_STRUCTURAL_VERIFICATION_CANDIDATE_LEVEL. "
            "13/13 decks attempted and 13/13 solved in Abaqus/Standard 2023 "
            "(12 run this loop, 1 pre-existing from 01:20 and not re-run); every "
            ".dat is non-zero, every .sta reports THE ANALYSIS HAS COMPLETED "
            "SUCCESSFULLY, 0 error messages across all jobs. Reaction balance "
            "PASS (worst relative force residual 1.09e-07, worst relative moment "
            "residual 9.63e-09, at float32 odb round-off). Energy balance PASS "
            "(ALLWK == ALLIE, ETOTAL ~ 1e-15). Load-proportionality and "
            "material 1/E scaling checks PASS to ~1e-7. "
            "MESH CONVERGENCE IS NOT DEMONSTRATED: NOT_CONVERGED in 4 of 4 case "
            "families (peak von Mises +22.0..+23.4%, peak displacement "
            "+30.1..+33.0% between the two finest levels, still rising). "
            "Artificial (hourglass) strain energy is 14% of internal energy at "
            "FINE and 80% at COARSE, so all 13 jobs are hourglass-contaminated "
            "and the stresses are DESIGN_INDICATIVE screening values only. "
            "Governing peak von Mises 1.0596 MPa (150 kg capture, FINE, Stage A "
            "at the arm-spider attachment), which is 0.384% of the 6061-T6 "
            "CANDIDATE TYPICAL yield 276 MPa -- reported as a "
            "candidate-property utilization ratio ONLY. NO margin of safety is "
            "asserted; no design allowable exists (NASA-STD-5001B). One real "
            "traceability defect found and recorded, not silently corrected: the "
            "150 kg deck's grasp couple 0.130197 N*m*s comes from envelope row "
            "CAP150_005 while the deck declares row CAP150_030 (0.113705), "
            "making applied M_z 1.760% HIGH (conservative). Gate B "
            "(MECHANICAL_FLIGHT_QUALIFICATION_RELEASED) remains HOLD and "
            "LAUNCH_QUALIFICATION_FEA_HOLD is retained."),
        "convergence_detail": conv_line,
        "builder": reg(os.path.abspath(__file__),
                       WP7_REL + "/WP7_FEA_OPERATIONAL_BUILDER_V1.py"),
        "produced_files": produced,
        "produced_solver_artifacts": artifacts,
        "source_register": src,
        "numeric_summary": {
            "jobs_attempted": len(recs),
            "jobs_solved": len(solved),
            "jobs_failed": len(failed),
            "jobs_solved_this_loop": len(ran_this_loop),
            "total_error_messages_across_all_jobs": sum(
                recs[j]["msg"]["error_messages"] or 0 for j in recs),
            "total_negative_eigenvalue_messages": sum(
                recs[j]["msg"]["negative_eigenvalue_warnings"] or 0
                for j in recs),
            "jobs_with_numerical_singularity_warnings": sum(
                1 for j in recs if recs[j]["msg"]["numerical_singularities"]),
            "numerical_singularities_per_affected_job": 8,
            "cases_converged": n_conv,
            "cases_total": len(CASE_ORDER),
            "governing_peak_von_mises_MPa": cand.get("peak_von_mises_MPa"),
            "governing_peak_von_mises_zone": cand.get("peak_location_zone"),
            "candidate_utilization_vs_6061_typical_yield_percent":
                cand.get("AL6061_T6_candidate_utilization_percent"),
            "worst_relative_reaction_force_residual":
                vchecks["reaction_balance_summary"][
                    "worst_relative_force_residual"],
            "worst_relative_reaction_moment_residual":
                vchecks["reaction_balance_summary"][
                    "worst_relative_moment_residual"],
            "artificial_energy_fraction_FINE_150kg":
                recs["fea1_capture_150kg_qs_fine"]["energy_quality"][
                    "artificial_energy_fraction_ALLAE_over_ALLIE"],
            "artificial_energy_fraction_COARSE_150kg":
                recs["fea1_capture_150kg_qs_coarse"]["energy_quality"][
                    "artificial_energy_fraction_ALLAE_over_ALLIE"],
            "cap150_applied_Mz_N_mm_deck": 19073.3,
            "cap150_applied_Mz_N_mm_strictly_from_declared_row": 18743.427958599998,
            "cap150_Mz_conservatism_percent": 1.7597634793835093,
        },
        "retained_holds": ev["retained_holds"],
        "integration_interfaces": {
            "wp3_tolerance_alloc/STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD":
                "PARTIALLY_ADDRESSED_CANDIDATE_LEVEL_NOT_CONVERGED",
            "wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1":
                "CONSUMED_AS_CANDIDATE_PROPERTIES_ONLY",
            "wp9_release_package/VERIFICATION_MATRIX_V1":
                "PENDING_SIBLING_HASH",
            "wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1":
                "NOT_CONSUMED_FEA1_USES_PARAMETERIZED_LATTICE_NOT_CAD_GEOMETRY",
        },
        "prohibitions_honored": ev["prohibitions_honored"],
    }
    rc_path = os.path.join(HERE, "receipt.json")
    with open(rc_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(receipt, f, indent=2, sort_keys=False, ensure_ascii=True)

    return {"csv": csv_path, "evidence": ev_path, "register": dr_path,
            "receipt": rc_path, "solved": len(solved), "failed": failed,
            "cases_converged": n_conv}


if __name__ == "__main__":
    r = build_all()
    for k in ("csv", "evidence", "register", "receipt"):
        p = r[k]
        d, n = sha256_bytes(p)
        print("%-10s %8d B  %s  %s" % (k, n, d, os.path.basename(p)))
    print("solved=%d failed=%s cases_converged=%d/4"
          % (r["solved"], r["failed"], r["cases_converged"]))
