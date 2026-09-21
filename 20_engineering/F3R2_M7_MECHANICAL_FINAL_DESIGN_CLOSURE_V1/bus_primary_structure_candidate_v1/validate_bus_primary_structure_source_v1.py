"""Independent static validator for the 340.5 mm bus-structure source package.

The validator deliberately does not import either the analytic builder or the guarded
CAD source.  It independently recomputes the nominal mass by closed-form volumes,
reconstructs the frozen M6 pattern transform, audits the CAD source AST, and checks
that source-only success has not been promoted into PRB-17/release authority.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
INPUT_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_DESIGN_INPUTS_V1.json"
SOURCE_PATH = PACKAGE / "bus_primary_structure_source_v1.py"
REPORT_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_ANALYTIC_REPORT_V1.json"
UNCERTAINTY_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_MASS_UNCERTAINTY_V1.json"
DECOMPOSITION_PATH = PACKAGE / "BUS_MASS_DECOMPOSITION_BRIDGE_V1.json"
GATE_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_SOURCE_GATE_V1.json"
DELTA_PATH = PACKAGE / "UNIFIED_R2_PREBIND_STRUCTURE_DELTA_V1.json"
REPRO_RECEIPT_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_REPRODUCIBILITY_RECEIPT_V1.json"
HASH_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_SHA256_V1.csv"
OUTPUT_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_STATIC_VALIDATION_V1.json"
CONTRACT_PATH = PACKAGE / "BUS_M3R_LOAD_PATH_CONTRACT_V1.md"
FASTENER_CSV_PATH = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp4_fastener_design/FASTENER_ANALYTIC_CHECKS_V1.csv"
FASTENER_YAML_PATH = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp4_fastener_design/M3R_FASTENER_DESIGN_V1.yaml"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _retained_negative_result_audit(inputs: dict, contract_text: str) -> dict:
    expected = inputs["retained_old_6061_negative_results"]
    yaml_text = FASTENER_YAML_PATH.read_text(encoding="utf-8")
    with FASTENER_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        raw_rows = list(csv.reader(handle))
    header_index = next(index for index, row in enumerate(raw_rows) if row and row[0] == "joint_id")
    header = raw_rows[header_index]
    rows = [dict(zip(header, row)) for row in raw_rows[header_index + 1 :] if len(row) == len(header)]
    audit_rows = []
    for name, item in expected.items():
        if name == "scope":
            continue
        source_ok = False
        evidence = None
        if item["source_kind"] == "M3R_FASTENER_DESIGN_V1_YAML":
            yaml_key = "separation" if item["check_id"] == "SEPARATION" else "bolt_tension_proof"
            evidence = f"{yaml_key}: {item['ratio']}"
            source_ok = evidence in yaml_text
        else:
            matches = [
                row for row in rows
                if row["joint_id"] == item["joint_id"]
                and row["case_id"] == "LC-014_CAPTURE_150KG"
                and row["case_variant"] == item["case_variant"]
                and row["check_id"] == item["check_id"]
                and "tc=5ms" in row["notes"]
            ]
            evidence = [row["demand_over_capacity"] for row in matches]
            source_ok = len(matches) == 1 and _close(float(matches[0]["demand_over_capacity"]), item["ratio"], 1.0e-12)
        contract_ok = item["contract_display"] in contract_text
        audit_rows.append(
            {
                "name": name,
                "source_kind": item["source_kind"],
                "source_evidence": evidence,
                "source_verified": source_ok,
                "contract_display": item["contract_display"],
                "contract_verified": contract_ok,
            }
        )
    return {"rows": audit_rows, "all_verified": len(audit_rows) == 6 and all(row["source_verified"] and row["contract_verified"] for row in audit_rows)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _close(a: float, b: float, tolerance: float = 1.0e-10) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def _mat_add(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[a[i][j] + b[i][j] for j in range(3)] for i in range(3)]


def _mat_sub(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[a[i][j] - b[i][j] for j in range(3)] for i in range(3)]


def _parallel_axis(mass: float, position: tuple[float, float, float]) -> list[list[float]]:
    x, y, z = position
    return [
        [mass * (y * y + z * z), -mass * x * y, -mass * x * z],
        [-mass * x * y, mass * (x * x + z * z), -mass * y * z],
        [-mass * x * z, -mass * y * z, mass * (x * x + y * y)],
    ]


def _independent_residual_properties(inputs: dict, report: dict) -> dict:
    boundary = inputs["mass_boundary"]
    total_mass = float(boundary["existing_bus_mass_budget_kg"])
    total_com = tuple(float(v) for v in boundary["existing_bus_com_S_m"])
    total_i_cg = [[float(v) for v in row] for row in boundary["existing_bus_inertia_about_com_S_kg_m2"]]
    structure_mass = float(report["mass_kg"])
    structure_com = tuple(float(v) for v in report["cg_S_m"])
    structure_i_cg = report["inertia_about_cg_S_kg_m2"]
    residual_mass = total_mass - structure_mass
    residual_com = tuple(
        (total_mass * total_com[i] - structure_mass * structure_com[i]) / residual_mass
        for i in range(3)
    )
    total_i_origin = _mat_add(total_i_cg, _parallel_axis(total_mass, total_com))
    structure_i_origin = _mat_add(
        structure_i_cg, _parallel_axis(structure_mass, structure_com)
    )
    residual_i_cg = _mat_sub(
        _mat_sub(total_i_origin, structure_i_origin),
        _parallel_axis(residual_mass, residual_com),
    )
    return {
        "mass_kg": residual_mass,
        "com_S_m": list(residual_com),
        "inertia_about_com_S_kg_m2": residual_i_cg,
    }


def _independent_closed_form_mass(inputs: dict) -> dict:
    """Recompute signed volumes without using builder primitives or implementation."""

    g = inputs["operational_geometry"]
    p = inputs["parameters"]
    rho_primary = float(inputs["materials"]["AL7075_T651_PRIMARY_CANDIDATE"]["density_kg_m3"])
    rho_secondary = float(inputs["materials"]["AL6061_T6_SECONDARY_CANDIDATE"]["density_kg_m3"])

    length = float(g["bus_body_length_mm"])
    cross = float(g["bus_cross_section_y_mm"])
    outer_half = cross / 2.0
    rail = float(p["rail_square_mm"])
    inner_half = float(p["frame_inner_half_span_mm"])
    frame_t = float(p["frame_axial_thickness_mm"])
    mid_outer_half = outer_half - float(p["mid_frame_outer_inset_mm"])
    web_half = float(p["front_spider_cross_web_width_mm"]) / 2.0

    rail_volume = 4.0 * length * rail * rail
    rear_slot = min(rail, outer_half - inner_half)
    rear_frame_volume = frame_t * (
        cross * cross - (2.0 * inner_half) ** 2 - 4.0 * rear_slot**2
    )
    mid_slot = min(rail, mid_outer_half - inner_half)
    one_mid_frame_volume = frame_t * (
        (2.0 * mid_outer_half) ** 2 - (2.0 * inner_half) ** 2 - 4.0 * mid_slot**2
    )
    front_passage_d = float(p["front_interface_central_passage_diameter_mm"])
    quadrant_window = inner_half - web_half
    front_backing_volume = frame_t * (
        cross * cross
        - 4.0 * quadrant_window**2
        - 4.0 * rail**2
        - math.pi * (front_passage_d / 2.0) ** 2
    )
    land_square = float(p["front_interface_land_local_square_mm"])
    land_t = float(p["front_interface_land_thickness_mm"])
    lightening_d = float(p["front_interface_lightening_hole_diameter_mm"])
    m6_d = float(p["front_interface_m6_clearance_hole_diameter_mm"])
    interface_land_volume = land_t * (
        land_square**2
        - math.pi * (front_passage_d / 2.0) ** 2
        - 4.0 * math.pi * (lightening_d / 2.0) ** 2
        - 4.0 * math.pi * (m6_d / 2.0) ** 2
    )
    primary_volume_mm3 = (
        rail_volume
        + rear_frame_volume
        + 2.0 * one_mid_frame_volume
        + front_backing_volume
        + interface_land_volume
    )

    deck_t = float(p["deck_thickness_mm"])
    deck_passage_d = float(p["deck_passage_diameter_mm"])
    two_deck_volume = 2.0 * deck_t * (
        (2.0 * inner_half) ** 2 - math.pi * (deck_passage_d / 2.0) ** 2
    )
    doubler_od = float(p["deck_doubler_outer_diameter_mm"])
    doubler_t = float(p["deck_doubler_thickness_mm"])
    four_doubler_volume = 4.0 * doubler_t * math.pi * (
        (doubler_od / 2.0) ** 2 - (deck_passage_d / 2.0) ** 2
    )
    panel_t = float(p["closure_panel_thickness_mm"])
    panel_length = length - 2.0 * frame_t
    panel_span = 2.0 * inner_half
    six_panel_volume = 4.0 * panel_length * panel_span * panel_t
    secondary_volume_mm3 = two_deck_volume + four_doubler_volume + six_panel_volume

    primary_mass = primary_volume_mm3 * 1.0e-9 * rho_primary
    secondary_mass = secondary_volume_mm3 * 1.0e-9 * rho_secondary
    return {
        "primary_volume_mm3": primary_volume_mm3,
        "secondary_volume_mm3": secondary_volume_mm3,
        "primary_mass_kg": primary_mass,
        "secondary_mass_kg": secondary_mass,
        "total_mass_kg": primary_mass + secondary_mass,
    }


def _independent_m6_points(inputs: dict) -> list[list[float]]:
    p = inputs["parameters"]
    g = inputs["operational_geometry"]
    x = float(g["body_x_range_mm"][1]) + float(p["front_interface_land_thickness_mm"])
    pitch = float(p["front_interface_m6_pattern_local_half_pitch_mm"])
    angle = math.radians(float(p["front_interface_pattern_clocking_deg"]))
    sine, cosine = math.sin(angle), math.cos(angle)
    centre_y = float(p["front_interface_pattern_center_y_mm"])
    centre_z = float(p["front_interface_pattern_center_z_mm"])
    rows = []
    for u in (-pitch, pitch):
        for v in (-pitch, pitch):
            y = centre_y + sine * u + cosine * v
            z = centre_z - cosine * u + sine * v
            rows.append([x, y, z])
    return sorted(rows, key=lambda row: (row[1], row[2]))


def _independent_lightening_points(inputs: dict) -> list[list[float]]:
    p = inputs["parameters"]
    g = inputs["operational_geometry"]
    x = float(g["body_x_range_mm"][1]) + float(p["front_interface_land_thickness_mm"])
    radius = float(p["front_interface_lightening_hole_radius_from_center_mm"])
    angle = math.radians(float(p["front_interface_pattern_clocking_deg"]))
    sine, cosine = math.sin(angle), math.cos(angle)
    centre_y = float(p["front_interface_pattern_center_y_mm"])
    centre_z = float(p["front_interface_pattern_center_z_mm"])
    rows = []
    for u, v in ((radius, 0.0), (-radius, 0.0), (0.0, radius), (0.0, -radius)):
        rows.append(
            [
                x,
                centre_y + sine * u + cosine * v,
                centre_z - cosine * u + sine * v,
            ]
        )
    return sorted(rows, key=lambda row: (row[1], row[2]))


def _independent_deck_passage_points(inputs: dict) -> list[list[float]]:
    p = inputs["parameters"]
    length = float(inputs["operational_geometry"]["bus_body_length_mm"])
    y = float(p["deck_passage_y_mm"])
    z = float(p["deck_passage_z_mm"])
    return [[-length / 6.0, y, z], [length / 6.0, y, z]]


def _ast_source_audit(source_text: str) -> dict:
    tree = ast.parse(source_text, filename=str(SOURCE_PATH))
    gen_functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "gen_step"
    ]
    zero_arg = bool(gen_functions) and not gen_functions[0].args.args and not gen_functions[0].args.kwonlyargs
    top_level_cad_import = any(
        (
            isinstance(node, ast.Import)
            and any(alias.name.split(".")[0] in {"build123d", "FreeCAD", "cadquery"} for alias in node.names)
        )
        or (
            isinstance(node, ast.ImportFrom)
            and (node.module or "").split(".")[0] in {"build123d", "FreeCAD", "cadquery"}
        )
        for node in tree.body
    )
    delayed_build123d_import = bool(gen_functions) and any(
        isinstance(node, ast.ImportFrom) and node.module == "build123d"
        for node in ast.walk(gen_functions[0])
    )
    guarded_main = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        for node in tree.body
    )
    forbidden_top_level_calls = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            forbidden_top_level_calls.append(ast.unparse(node.value.func))
    required_strings = [
        "BUS_PRIMARY_STRUCTURE_EXECUTION_AUTHORIZED",
        "BUS_PRIMARY_STRUCTURE_RUN_ID",
        "BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_ID",
        "BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_ISSUED_UTC",
        "BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_EXPIRES_UTC",
        "BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_RISK_ACK",
        "MEMORY_GATE_GIB = 6.0",
        "MAX_OVERRIDE_VALIDITY_SECONDS = 7200.0",
        "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK",
        "LOW_MEMORY_OVERRIDE_ALREADY_CONSUMED",
        "RUN_ID_ALREADY_CONSUMED",
        "marker.open(\"x\"",
        "RUN_CONSUMPTION_DIR",
        "ACTIVE_RUN_LOCK_PATH",
        "_acquire_single_cad_writer_lock",
        "ACTIVE_RUN_LOCK_PATH.open(\"x\"",
        "CAD_WRITER_ALREADY_ACTIVE_FAIL_CLOSED",
        "RETAIN_FOR_OWNER_INSPECTION_AND_MANUAL_CLEARANCE",
        "_release_single_cad_writer_lock(run_authority[\"run_id\"])",
        "ATTEMPT_INVALIDATION_PATH",
        "SOURCE_ONLY_GATE_INVALIDATED__POST_EXECUTION_REBUILD_AND_INDEPENDENT_REVIEW_REQUIRED",
        "PREIMPORT_AUTHORITY_RECORD_PATH",
        "_write_json(PREIMPORT_AUTHORITY_RECORD_PATH, record)",
        '"memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY"',
        '"memory_gate_passed": not below_gate',
        '"execution_authorized": True',
        '"source_sha256_preimport"',
        '"input_sha256_preimport"',
        "SOURCE_OR_INPUT_CHANGED_DURING_GENERATION_BEFORE_EXPORT",
        "SOURCE_OR_INPUT_CHANGED_DURING_GENERATION_AFTER_EXPORT",
        "Owner accepted elevated out-of-memory/process-instability risk",
        "GENERATION_NOT_AUTHORIZED_SOURCE_ONLY",
    ]
    preimport_write_index = source_text.find("_write_json(PREIMPORT_AUTHORITY_RECORD_PATH, record)")
    invalidation_write_index = source_text.find("ATTEMPT_INVALIDATION_PATH,\n        {")
    cad_import_index = source_text.find("from build123d import")
    return {
        "gen_step_zero_argument": zero_arg,
        "top_level_cad_import_absent": not top_level_cad_import,
        "delayed_build123d_import_present": delayed_build123d_import,
        "guarded_main_present": guarded_main,
        "forbidden_top_level_expression_calls": forbidden_top_level_calls,
        "required_fail_closed_tokens_present": all(token in source_text for token in required_strings),
        "forbidden_override_pass_tokens_absent": all(
            token not in source_text
            for token in ('"MEMORY_GATE_PASS"', '"TOOLING_GATE_PASS"', '"AVAILABLE_MEMORY_GE_6_GIB"')
        ),
        "preimport_authority_record_precedes_cad_import": (
            preimport_write_index >= 0
            and cad_import_index >= 0
            and preimport_write_index < cad_import_index
        ),
        "gate_invalidation_precedes_cad_import": (
            invalidation_write_index >= 0
            and cad_import_index >= 0
            and invalidation_write_index < cad_import_index
        ),
    }


def _source_pins_verified(inputs: dict) -> tuple[bool, list[dict]]:
    rows = []
    for pin in inputs["source_pins"]:
        path = ROOT / pin["path"]
        actual = _sha256(path) if path.is_file() else None
        verified = actual == pin["sha256"]
        rows.append({"path": pin["path"], "expected": pin["sha256"], "actual": actual, "verified": verified})
    return all(row["verified"] for row in rows), rows


def _hash_register_verified() -> tuple[bool, list[dict]]:
    if not HASH_PATH.is_file():
        return False, []
    rows = []
    with HASH_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            path = PACKAGE / row["path"]
            actual = _sha256(path) if path.is_file() else None
            rows.append(
                {
                    "path": row["path"],
                    "expected": row["sha256"],
                    "actual": actual,
                    "verified": actual == row["sha256"],
                }
            )
    return bool(rows) and all(row["verified"] for row in rows), rows


def validate() -> dict:
    inputs = _read_json(INPUT_PATH)
    report = _read_json(REPORT_PATH)
    uncertainty = _read_json(UNCERTAINTY_PATH)
    decomposition = _read_json(DECOMPOSITION_PATH)
    gate = _read_json(GATE_PATH)
    delta = _read_json(DELTA_PATH)
    reproducibility = _read_json(REPRO_RECEIPT_PATH)
    source_text = SOURCE_PATH.read_text(encoding="utf-8")
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    negative_result_audit = _retained_negative_result_audit(inputs, contract_text)
    solar_boundary = inputs["solar_r2_interface_boundary"]
    solar_reissue = solar_boundary["v3_source_metadata_reissue"]
    solar_drift = solar_boundary["legacy_downstream_configuration_drift"]
    solar_report = _read_json(ROOT / solar_reissue["report_path"])
    solar_validation = _read_json(ROOT / solar_reissue["validation_path"])
    bom_text = (ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp9_release_package/BOM_V3_DESIGN.csv").read_text(encoding="utf-8")
    wp6_text = (ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1.yaml").read_text(encoding="utf-8")
    solar_drift_machine_verified = (
        solar_reissue["validation_score"] == {"pass": 15, "total": 15}
        and solar_validation["summary"] == {"pass": 15, "total": 15, "failed": []}
        and solar_validation["effective_for_downstream_execution"] is False
        and solar_validation["next_stage_authorized"] is False
        and solar_validation["release_credit"] is False
        and _close(float(solar_report["mass_model_candidate"]["wing_total_kg"]), 0.78, 1.0e-12)
        and _close(float(solar_drift["bom_and_icd_mass_each_kg"]), 0.3483933, 1.0e-12)
        and _close(float(solar_drift["v3_mass_each_kg"]), 0.78, 1.0e-12)
        and _close(
            float(solar_drift["two_wing_delta_kg"]),
            2.0 * (0.78 - 0.3483933),
            1.0e-12,
        )
        and "0.3483933" in bom_text
        and "0.3483933" in wp6_text
        and "227" in wp6_text
        and "200" in wp6_text
        and "6" in wp6_text
        and "V3 source/metadata reissue is complete at 15/15" in inputs["known_configuration_drifts"]["Solar_R2"]
        and "0.8632134" in inputs["known_configuration_drifts"]["Solar_R2"]
    )

    mass = _independent_closed_form_mass(inputs)
    independent_points = _independent_m6_points(inputs)
    reported_points = report["derived_geometry"]["m6_hole_centres_S_at_D_BUS_MATE_mm"]
    point_residual = max(
        abs(independent_points[i][j] - reported_points[i][j])
        for i in range(4)
        for j in range(3)
    )
    independent_lightening_points = _independent_lightening_points(inputs)
    reported_lightening_points = report["derived_geometry"]["lightening_hole_centres_S_at_D_BUS_MATE_mm"]
    lightening_point_residual = max(
        abs(independent_lightening_points[i][j] - reported_lightening_points[i][j])
        for i in range(4)
        for j in range(3)
    )
    independent_deck_points = _independent_deck_passage_points(inputs)
    reported_deck_points = report["derived_geometry"]["deck_passage_centres_S_mm"]
    deck_point_residual = max(
        abs(independent_deck_points[i][j] - reported_deck_points[i][j])
        for i in range(2)
        for j in range(3)
    )
    frozen_bridge_points = [
        [185.25, -93.0088375365016, 33.7718779700000],
        [185.25, -33.8422498890000, -93.1111977575016],
        [185.25, 33.8742381910000, 92.9384656175016],
        [185.25, 93.0408258385016, -33.9446101100000],
    ]
    frozen_residual = max(
        abs(independent_points[i][j] - frozen_bridge_points[i][j])
        for i in range(4)
        for j in range(3)
    )
    ast_audit = _ast_source_audit(source_text)
    pins_ok, pin_rows = _source_pins_verified(inputs)
    hash_ok, hash_rows = _hash_register_verified()
    reproducibility_pairs = reproducibility["deterministic_rebuild_crosscheck"]["file_hash_pairs"]
    reproducibility_pairs_current = (
        len(reproducibility_pairs) == 6
        and len({row["path"] for row in reproducibility_pairs}) == 6
        and all(
            row["equal"] is True
            and row["run1_sha256"] == row["run2_sha256"]
            and (PACKAGE / row["path"]).is_file()
            and _sha256(PACKAGE / row["path"]) == row["run2_sha256"]
            for row in reproducibility_pairs
        )
    )

    inertia = report["inertia_about_cg_S_kg_m2"]
    inertia_symmetric = max(
        abs(inertia[i][j] - inertia[j][i]) for i in range(3) for j in range(3)
    ) <= 1.0e-12
    principal = report["principal_moments_kg_m2"]
    inertia_admissible = (
        inertia_symmetric
        and all(value > 0.0 for value in principal)
        and all(principal[i] <= sum(principal) - principal[i] + 1.0e-12 for i in range(3))
    )
    generated_cad = sorted(
        path.name
        for path in PACKAGE.iterdir()
        if path.suffix.lower() in {".step", ".stp", ".fcstd", ".iges", ".igs"}
    )
    execution_evidence = {
        "preimport_authority_record": (PACKAGE / "BUS_PRIMARY_STRUCTURE_PREIMPORT_AUTHORITY_RECORD_V1.json").is_file(),
        "generation_record": (PACKAGE / "BUS_PRIMARY_STRUCTURE_GENERATION_RECORD_V1.json").is_file(),
        "gate_invalidation_record": (PACKAGE / "BUS_PRIMARY_STRUCTURE_GATE_INVALIDATED_BY_EXECUTION_V1.json").is_file(),
        "run_consumption_records": sum(1 for _ in (PACKAGE / ".bus_primary_structure_run_consumption").glob("*.json")) if (PACKAGE / ".bus_primary_structure_run_consumption").is_dir() else 0,
        "override_consumption_records": sum(1 for _ in (PACKAGE / ".bus_primary_structure_override_consumption").glob("*.json")) if (PACKAGE / ".bus_primary_structure_override_consumption").is_dir() else 0,
        "active_cad_writer_lock": (PACKAGE / ".bus_primary_structure_active_run.lock").is_file(),
    }
    execution_attempt_present = any(bool(value) for value in execution_evidence.values())
    prebind_contract = inputs["prebind_authority"]
    upstream_frontier = _read_json(ROOT / prebind_contract["frontier_path"])
    upstream_gate = _read_json(ROOT / prebind_contract["gate_path"])
    upstream_prb17 = next(row for row in upstream_frontier["effective_criteria"] if row["id"] == "PRB-17")
    pattern_angle = math.radians(float(inputs["parameters"]["front_interface_pattern_clocking_deg"]))
    expected_pattern_transform = [
        [0.0, 0.0, 1.0, 185.25],
        [math.sin(pattern_angle), math.cos(pattern_angle), 0.0, float(inputs["parameters"]["front_interface_pattern_center_y_mm"])],
        [-math.cos(pattern_angle), math.sin(pattern_angle), 0.0, float(inputs["parameters"]["front_interface_pattern_center_z_mm"])],
        [0.0, 0.0, 0.0, 1.0],
    ]
    pattern_transform_residual = max(
        abs(
            float(inputs["operational_geometry"]["T_S_D_BUS_M6_PATTERN"][i][j])
            - expected_pattern_transform[i][j]
        )
        for i in range(4)
        for j in range(4)
    )
    screen = inputs["structural_screen_inputs"]
    half_sine = screen["half_sine_inputs"]
    independent_peak_force = math.pi * float(half_sine["impulse_Ns"]) / (2.0 * float(half_sine["contact_duration_s"]))
    independent_peak_couple = math.pi * float(half_sine["couple_impulse_Nms"]) / (2.0 * float(half_sine["contact_duration_s"]))
    independent_bending_moment = (
        independent_peak_force
        * (float(half_sine["base_lever_m"]) + float(half_sine["stage_b_to_bus_lever_offset_m"]))
        + independent_peak_couple
    )
    declared_cases = screen["same_case_peak_wrenches_at_stage_b_to_bus"]
    load_derivation_residual = max(
        abs(float(declared_cases["NORMAL_TENSION_BENDING"]["axial_force_N"]) - independent_peak_force),
        abs(float(declared_cases["NORMAL_TENSION_BENDING"]["bending_moment_Nm"]) - independent_bending_moment),
        abs(float(declared_cases["SHEAR_TORSION"]["transverse_force_N"]) - independent_peak_force),
        abs(float(declared_cases["SHEAR_TORSION"]["torsional_moment_Nm"]) - independent_peak_couple),
    )
    expected_labels = set(inputs["part_architecture"]["primary_members"] + inputs["part_architecture"]["secondary_members"])
    actual_labels = set(report["derived_geometry"]["physical_member_labels"])
    independent_residual = _independent_residual_properties(inputs, report)
    recorded_residual = decomposition["algebraic_residual_equipment_and_unmodelled_component"]
    residual_mass_error = abs(independent_residual["mass_kg"] - recorded_residual["mass_kg"])
    residual_com_error = max(
        abs(independent_residual["com_S_m"][i] - recorded_residual["com_S_m"][i])
        for i in range(3)
    )
    residual_inertia_error = max(
        abs(
            independent_residual["inertia_about_com_S_kg_m2"][i][j]
            - recorded_residual["inertia_about_com_S_kg_m2"][i][j]
        )
        for i in range(3)
        for j in range(3)
    )

    checks = {
        "V01_REQUIRED_SOURCE_ONLY_ARTIFACTS_PRESENT": all(
            path.is_file()
            for path in (
                INPUT_PATH,
                SOURCE_PATH,
                REPORT_PATH,
                UNCERTAINTY_PATH,
                DECOMPOSITION_PATH,
                GATE_PATH,
                DELTA_PATH,
                REPRO_RECEIPT_PATH,
            )
        ),
        "V02_ALL_24_UPSTREAM_SOURCE_PINS_HASH_VERIFIED": pins_ok and len(pin_rows) == 24,
        "V03_OPERATIONAL_TRACK_AND_FRAME_STATIONS_EXACT": (
            inputs["operational_geometry"]["body_x_range_mm"] == [-170.25, 170.25]
            and report["derived_geometry"]["frame_stations_x_mm"] == [-170.25, -56.75, 56.75, 170.25]
        ),
        "V04_UNNAMED_15MM_FRONT_GAP_EXPLICITLY_CLOSED": report["derived_geometry"]["front_transition_x_range_mm"] == [170.25, 185.25],
        "V05_PHYSICAL_AND_DYNAMICS_DATUMS_NOT_ALIASED_SEMANTICALLY": (
            inputs["operational_geometry"]["stations_x_mm"]["D_BUS_MATE_PHYSICAL"]
            == inputs["operational_geometry"]["stations_x_mm"]["M_DYNAMICS_NONPHYSICAL"]
            and inputs["operational_geometry"]["T_S_D_BUS_MATE_PHYSICAL"]
            == inputs["operational_geometry"]["T_S_M_DYNAMICS_NONPHYSICAL"]
            and inputs["operational_geometry"]["T_S_D_BUS_M6_PATTERN"]
            != inputs["operational_geometry"]["T_S_D_BUS_MATE_PHYSICAL"]
            and inputs["operational_geometry"]["T_S_D_BUS_MATE_PHYSICAL"][0][3] == 185.25
            and inputs["operational_geometry"]["T_S_M_DYNAMICS_NONPHYSICAL"][0][3] == 185.25
            and inputs["operational_geometry"]["T_S_D_BUS_MATE_PHYSICAL"][1][3] == 0.0
            and inputs["operational_geometry"]["T_S_D_BUS_MATE_PHYSICAL"][2][3] == 0.0
            and inputs["operational_geometry"]["T_S_M_DYNAMICS_NONPHYSICAL"][1][3] == 0.0
            and inputs["operational_geometry"]["T_S_M_DYNAMICS_NONPHYSICAL"][2][3] == 0.0
            and inputs["operational_geometry"]["T_S_D_BUS_M6_PATTERN"][1][3] == 0.015994151
            and inputs["operational_geometry"]["T_S_D_BUS_M6_PATTERN"][2][3] == -0.08636607
            and pattern_transform_residual <= 5.0e-13
            and "same numeric transform" in inputs["operational_geometry"]["coincident_datum_rule"]
            and "third physical subdatum" in inputs["operational_geometry"]["coincident_datum_rule"]
            and "never be aliased" in inputs["operational_geometry"]["coincident_datum_rule"]
        ),
        "V06_CAD_SOURCE_HAS_ZERO_ARGUMENT_GEN_STEP": ast_audit["gen_step_zero_argument"],
        "V07_CAD_KERNEL_IMPORT_DELAYED_AND_IMPORT_SIDE_EFFECT_FREE": (
            ast_audit["top_level_cad_import_absent"]
            and ast_audit["delayed_build123d_import_present"]
            and not ast_audit["forbidden_top_level_expression_calls"]
            and ast_audit["guarded_main_present"]
        ),
        "V08_MEMORY_GATE_OWNER_OVERRIDE_AND_RISK_RECORD_FAIL_CLOSED": (
            ast_audit["required_fail_closed_tokens_present"]
            and ast_audit["preimport_authority_record_precedes_cad_import"]
            and ast_audit["gate_invalidation_precedes_cad_import"]
            and ast_audit["forbidden_override_pass_tokens_absent"]
        ),
        "V09_NO_CAD_OR_EXECUTION_ATTEMPT_EVIDENCE_PRESENT": not generated_cad and not execution_attempt_present,
        "V10_CLOSED_FORM_MASS_MATCHES_ANALYTIC_REPORT": _close(mass["total_mass_kg"], report["mass_kg"], 1.0e-12),
        "V11_STRUCTURE_IS_DECOMPOSITION_INSIDE_BUS_BUDGET": (
            report["mass_boundary"]["m7_mass_ledger_mutated"] is False
            and report["mass_kg"] < report["mass_boundary"]["existing_bus_budget_kg"]
            and _close(
                report["mass_boundary"]["residual_bus_equipment_and_unmodelled_mass_budget_kg"],
                report["mass_boundary"]["existing_bus_budget_kg"] - report["mass_kg"],
                1.0e-12,
            )
            and residual_mass_error <= 1.0e-12
            and residual_com_error <= 1.0e-12
            and residual_inertia_error <= 1.0e-12
            and decomposition["recomposition_audit"]["residual_inertia_physically_admissible"] is True
            and decomposition["recomposition_audit"]["exact_within_1e_minus_12"] is True
            and _close(
                decomposition["explicit_structure_candidate"]["mass_standard_uncertainty_kg"],
                report["mass_kg"] * 0.15,
                1.0e-12,
            )
            and decomposition["explicit_structure_candidate"]["local_sensitivity_diagnostic_standard_uncertainty_kg"] > 0.0
            and recorded_residual["mass_standard_uncertainty_kg"] is None
            and decomposition["sim13_rebind_authorized"] is False
        ),
        "V12_PARAMETERIZED_OPENING_LOCATIONS_AND_M6_PATTERN_INDEPENDENTLY_REPRODUCED": (
            point_residual <= 1.0e-12
            and frozen_residual <= 1.0e-6
            and lightening_point_residual <= 1.0e-12
            and deck_point_residual <= 1.0e-12
            and inputs["parameters"]["front_interface_m6_clearance_hole_diameter_mm"] == 6.6
            and inputs["uncertainty_model"]["variables"]["m6_hole_diameter_mm"]["nominal"] == 6.645
            and inputs["uncertainty_model"]["variables"]["m6_hole_diameter_mm"]["half_width"] == 0.045
        ),
        "V13_MEMBER_TREE_MATCHES_8_PRIMARY_AND_12_SECONDARY_LABELS": actual_labels == expected_labels and len(actual_labels) == 20,
        "V14_INERTIA_ADMISSIBLE_AND_SAME_CASE_LOAD_DERIVATION_EXACT": (
            inertia_admissible
            and load_derivation_residual <= 1.0e-12
            and report["stiffness_screen"]["half_sine_load_derivation_audit"]["matches_declared_same_case_within_1e_minus_12"] is True
            and report["stiffness_screen"]["shear_torsion_screen"]["torsional_response"] == "UNKNOWN_NO_VALIDATED_TORSIONAL_LOAD_PATH_OR_TORSION_CONSTANT"
        ),
        "V15_GUM_MONTE_CARLO_CROSSCHECK_REPRODUCIBLE_CONTRACT": (
            uncertainty["monte_carlo"]["sample_count"] == 20000
            and uncertainty["monte_carlo"]["seed"] == 6013405
            and uncertainty["gum_linear"]["standard_uncertainty_kg"] > 0.0
            and uncertainty["monte_carlo"]["crosscheck_consistent_within_5_percent"] is True
            and _close(uncertainty["project_policy"]["standard_uncertainty_kg"], report["mass_kg"] * 0.15, 1.0e-12)
            and uncertainty["project_policy"]["downstream_value_controls"] is True
            and uncertainty["project_policy"]["local_gum_may_replace_project_policy"] is False
            and uncertainty["distribution_centre_exception"]["design_basic_mm"] == 6.6
            and uncertainty["distribution_centre_exception"]["uncertainty_distribution_centre_mm"] == 6.645
            and _close(uncertainty["distribution_centre_exception"]["interval_mm"][0], 6.6, 1.0e-12)
            and _close(uncertainty["distribution_centre_exception"]["interval_mm"][1], 6.69, 1.0e-12)
        ),
        "V16_SOURCE_GATE_IS_16_OF_16_WITHOUT_RELEASE_CREDIT": (
            gate["all_checks_passed"] is True
            and gate["score"] == {"passed": 16, "total": 16}
            and not any(bool(value) for value in gate["execution_evidence"].values())
            and gate["next_stage_authorized"] is False
            and gate["release_credit"] is False
        ),
        "V17_HASH_BOUND_UPSTREAM_PRB17_AND_EFFECTIVE_PREBIND_REMAIN_UNCHANGED": (
            upstream_frontier["effective_summary"] == prebind_contract["expected_effective_summary"]
            and {"state": upstream_prb17["state"], "pass": upstream_prb17["pass"]} == prebind_contract["expected_PRB_17"]
            and upstream_gate["package_validation"] == "PASS"
            and upstream_gate["technical_outcome"] == "HOLD"
            and upstream_gate["next_stage_authorized"] is False
            and upstream_gate["release_credit"] is False
            and delta["PRB_17"] == upstream_prb17["state"] == "HOLD"
            and delta["technical_definition_count"] == {"closed_or_candidate_defined": 7, "required": 8}
            and delta["prebind_count_change"] == 0
            and gate["effective_prebind_pass_count_before"] == upstream_frontier["effective_summary"]["pass"]
            and gate["effective_prebind_pass_count_after"] == upstream_frontier["effective_summary"]["pass"]
            and delta["execution_authority_created"] is False
            and all(
                hold in inputs["retained_holds"]
                for hold in (
                    "M4_M5_M6_ACTUAL_MIXED_MATERIAL_REBIND_AND_REANALYSIS_HOLD",
                    "BUS_STRUCTURE_TOLERANCE_ALLOCATION_CMM_AND_THERMAL_DEFORMATION_HOLD",
                    "BOM_DRAWING_MATERIAL_AND_SOLAR_CONFIGURATION_DRIFT_REISSUE_HOLD",
                    "LEGACY_FLANGE_OWNERSHIP_AND_MASS_ALLOCATION_HOLD",
                )
            )
            and set(inputs["known_configuration_drifts"]) == {
                "BOM_V3_DESIGN",
                "DRAWING_SET_INDEX_V1",
                "D05_STAGE_A_and_D06_STAGE_B",
                "BUS_or_DOWEL_material_selection",
                "Solar_R2",
            }
            and solar_drift_machine_verified
            and negative_result_audit["all_verified"]
            and "当前候选/设计选型 7075/6061 混材夹紧栈" in contract_text
            and "仅可作为未来版本化动力学/URDF 的候选输入" in contract_text
            and "当前不得进入 downstream execution" in contract_text
            and "动力学/URDF 可以消费本包" not in contract_text
        ),
        "V18_HASH_REGISTER_AND_REPRODUCIBILITY_RECEIPT_VERIFY": (
            hash_ok
            and reproducibility["unauthorized_dynamic_negative_control"]["exit_code"] == 1
            and reproducibility["unauthorized_dynamic_negative_control"]["expected_token_present"] is True
            and reproducibility["unauthorized_dynamic_negative_control"]["no_artifact_delta"] is True
            and reproducibility["deterministic_rebuild_crosscheck"]["consecutive_rebuilds_compared"] == 2
            and reproducibility["deterministic_rebuild_crosscheck"]["tracked_outputs"] == 6
            and reproducibility["deterministic_rebuild_crosscheck"]["hash_drift_count"] == 0
            and reproducibility_pairs_current
            and reproducibility["authorized_path_dynamically_exercised"] is False
            and reproducibility["step_or_fcstd_generated"] is False
            and reproducibility["next_stage_authorized"] is False
            and reproducibility["release_credit"] is False
        ),
    }
    passed = sum(bool(value) for value in checks.values())
    payload = {
        "schema": "BUS_PRIMARY_STRUCTURE_STATIC_VALIDATION_V1",
        "generated_date_local": "2026-08-24",
        "validator_independence": "DOES_NOT_IMPORT_ANALYTIC_BUILDER_OR_CAD_SOURCE",
        "checks": checks,
        "score": {"passed": passed, "total": len(checks)},
        "all_checks_passed": passed == len(checks),
        "verdict": (
            "PASS_INDEPENDENT_SOURCE_ONLY_VALIDATION_WITH_PRB17_HOLD"
            if passed == len(checks)
            else "HOLD_INDEPENDENT_VALIDATION_DEFECT"
        ),
        "independent_mass_recalculation": mass,
        "reported_mass_kg": report["mass_kg"],
        "mass_abs_residual_kg": abs(mass["total_mass_kg"] - report["mass_kg"]),
        "independent_bus_residual_recalculation": independent_residual,
        "bus_residual_record_abs_errors": {
            "mass_kg": residual_mass_error,
            "com_m": residual_com_error,
            "inertia_kg_m2": residual_inertia_error,
        },
        "m6_report_abs_residual_mm": point_residual,
        "m6_frozen_bridge_abs_residual_mm": frozen_residual,
        "lightening_hole_report_abs_residual_mm": lightening_point_residual,
        "deck_passage_report_abs_residual_mm": deck_point_residual,
        "D_BUS_M6_PATTERN_transform_max_abs_residual": pattern_transform_residual,
        "same_case_load_derivation_max_abs_residual": load_derivation_residual,
        "ast_audit": ast_audit,
        "generated_cad_files": generated_cad,
        "execution_evidence": execution_evidence,
        "upstream_prebind_evidence": {
            "effective_summary": upstream_frontier["effective_summary"],
            "PRB_17": {"state": upstream_prb17["state"], "pass": upstream_prb17["pass"]},
            "gate_package_validation": upstream_gate["package_validation"],
            "gate_technical_outcome": upstream_gate["technical_outcome"],
        },
        "source_pin_audit": pin_rows,
        "retained_old_6061_negative_result_audit": negative_result_audit,
        "solar_v3_and_legacy_configuration_drift_machine_verified": solar_drift_machine_verified,
        "hash_register_audit_before_validation_write": hash_rows,
        "authority_statement": "Static/source checks pass only the candidate-definition layer. PRB-17, STEP generation, manufacturing release, FEA qualification and downstream execution remain HOLD.",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"verdict": payload["verdict"], "score": payload["score"]}, sort_keys=True))
    return payload


if __name__ == "__main__":
    validate()
