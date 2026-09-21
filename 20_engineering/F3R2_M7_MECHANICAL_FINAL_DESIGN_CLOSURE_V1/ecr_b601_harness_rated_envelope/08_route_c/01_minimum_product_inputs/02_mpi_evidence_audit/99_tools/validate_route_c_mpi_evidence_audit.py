from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


PACKAGE_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/"
    "02_mpi_evidence_audit"
)
REPORT_NAME = "ROUTE_C_MPI_EVIDENCE_AUDIT_VALIDATION_V1.json"


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    raise RuntimeError("Repository root not found")


ROOT = find_repo_root()
OUT = ROOT / PACKAGE_REL


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_json(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def load_yaml(name: str) -> dict:
    return yaml.safe_load((OUT / name).read_text(encoding="utf-8"))


def is_unknown_record(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    if "value" in record:
        value_is_null = record["value"] is None
    elif "minimum" in record and "maximum" in record:
        value_is_null = record["minimum"] is None and record["maximum"] is None
    else:
        return False
    has_mandatory = all(key in record for key in ["unit", "source_revision", "owner", "controlled"])
    has_uncertainty = "uncertainty" in record or "bounded_tolerance" in record
    return value_is_null and has_mandatory and has_uncertainty and record["controlled"] is False


def walk_unknown_records(value):
    if isinstance(value, dict):
        if "value" in value or ("minimum" in value and "maximum" in value):
            yield value
        for child in value.values():
            yield from walk_unknown_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_unknown_records(child)


def policy_accepts(bundle: dict) -> bool:
    gate = bundle["gate"]
    audit = bundle["audit"]
    contract = bundle["contract"]
    templates = bundle["templates"]
    if gate.get("gate") != "HOLD" or gate.get("next_stage_authorized") is not False:
        return False
    if gate.get("criteria_controlled") != 0 or gate.get("criteria_total") != 8:
        return False
    if gate.get("cad_generation_authorized") is not False or gate.get("cad_assets_created") != 0:
        return False
    if audit.get("summary", {}).get("criteria_controlled") != 0:
        return False
    if any(item.get("controlled") for item in audit.get("audits", [])):
        return False
    if audit.get("mpi07_urdf_local_kinematics", {}).get("installation_icd_closed") is not False:
        return False
    if gate.get("e17_mission_segments_released") != 0:
        return False
    if gate.get("route_b_seed_inheritance_allowed") is not False:
        return False
    if contract.get("cad_generation_authorized") is not False:
        return False
    route_b = contract.get("route_b_quarantine", {})
    if route_b.get("overall_diameter_mm_10") != "FORBIDDEN_TO_INHERIT":
        return False
    if route_b.get("legacy_radius_mm_25") != "FORBIDDEN_TO_INHERIT":
        return False
    if route_b.get("terminal_requirement_mm_30") != "FORBIDDEN_TO_INHERIT_AS_SELECTED_PRODUCT_LIMIT":
        return False
    if route_b.get("cut_length_mm_4001_158") != "FORBIDDEN_TO_INHERIT":
        return False
    for template in templates.values():
        if template.get("release_credit") is not False or template.get("next_stage_authorized") is not False:
            return False
        records = list(walk_unknown_records(template))
        if not records or not all(is_unknown_record(record) for record in records):
            return False
    return True


def main() -> None:
    checks = []
    negative_controls = []

    def check(check_id: str, condition: bool, detail: str) -> None:
        checks.append({"id": check_id, "pass": bool(condition), "detail": detail})

    def negative(control_id: str, mutate, detail: str) -> None:
        candidate = copy.deepcopy(bundle)
        mutate(candidate)
        rejected = not policy_accepts(candidate)
        negative_controls.append({"id": control_id, "pass": rejected, "detail": detail})

    required_files = [
        "ROUTE_C_MPI_EVIDENCE_AUDIT_AUTHORITY_CONTRACT_V1.json",
        "ROUTE_C_MPI_EVIDENCE_AUDIT_V1.json",
        "B601_ELECTRICAL_AND_DATA_ICD_OWNER_INPUT_TEMPLATE_V1.yaml",
        "WIRE_LIST_PINOUT_OWNER_INPUT_TEMPLATE_V1.yaml",
        "INSTALLED_CONSTRUCTION_OWNER_INPUT_TEMPLATE_V1.yaml",
        "INSTALLATION_ICD_OWNER_INPUT_TEMPLATE_V1.yaml",
        "MISSION_LIFE_ALLOCATION_OWNER_INPUT_TEMPLATE_V1.yaml",
        "ROUTE_C_MPI_EVIDENCE_GATE_V1.json",
        "ROUTE_C_MPI_EVIDENCE_AUDIT_OUTPUT_MANIFEST_V1.json",
        "README.md",
    ]
    for index, name in enumerate(required_files, start=1):
        check(f"FILE-{index:02d}", (OUT / name).is_file(), name)

    contract = load_json(required_files[0])
    audit = load_json(required_files[1])
    template_names = required_files[2:7]
    templates = {name: load_yaml(name) for name in template_names}
    gate = load_json(required_files[7])
    manifest = load_json(required_files[8])
    bundle = {"contract": contract, "audit": audit, "templates": templates, "gate": gate}

    check("SCHEMA-01", contract.get("schema") == "ROUTE_C_MPI_EVIDENCE_AUDIT_AUTHORITY_CONTRACT_V1", "authority schema")
    check("SCHEMA-02", audit.get("schema") == "ROUTE_C_MPI_EVIDENCE_AUDIT_V1", "audit schema")
    check("SCHEMA-03", gate.get("schema") == "ROUTE_C_MPI_EVIDENCE_GATE_V1", "gate schema")
    check("SCHEMA-04", manifest.get("schema") == "ROUTE_C_MPI_EVIDENCE_AUDIT_OUTPUT_MANIFEST_V1", "manifest schema")
    check("AUTH-01", contract.get("mutation_authority") is False, "read-only evidence audit")
    check("AUTH-02", contract.get("cad_generation_authorized") is False, "no CAD authority")
    check("AUTH-03", contract.get("accepted_urdf_mutation_authorized") is False, "accepted URDF immutable")
    check("AUTH-04", contract.get("release_authority") is False, "no release authority")
    check("AUTH-05", contract.get("unit_and_uncertainty_policy", {}).get("unknown_value") is None, "unknown stays null")
    check("AUTH-06", contract.get("unit_and_uncertainty_policy", {}).get("zero_substitution_for_unknown") == "PROHIBITED", "no silent zero")

    expected_sources = {
        "minimum_input_register", "product_source_register", "product_input_gate", "rfi_requirements", "rfi_gate",
        "vendor_rebot_b601_dm_bom_readme", "hardware_component_plan", "harness_routing",
        "joint_interface_control_documents", "accepted_urdf", "e17_gate", "route_b_rejected_product_definition",
    }
    check("BIND-01", set(contract.get("source_bindings", {})) == expected_sources, "all required source bindings present")
    for index, (source_id, item) in enumerate(contract.get("source_bindings", {}).items(), start=2):
        source_path = ROOT / item["path"]
        check(f"BIND-{index:02d}A", source_path.is_file(), f"{source_id} exists")
        check(f"BIND-{index:02d}B", sha256(source_path) == item["sha256"], f"{source_id} hash matches")

    check("AUDIT-01", len(audit.get("audits", [])) == 8, "eight MPI rows")
    check("AUDIT-02", [item["id"] for item in audit["audits"]] == [f"MPI-{i:02d}" for i in range(1, 9)], "MPI IDs ordered")
    check("AUDIT-03", all(item.get("controlled") is False for item in audit["audits"]), "0/8 controlled")
    check("AUDIT-04", audit.get("summary", {}).get("criteria_controlled") == 0, "summary controlled count")
    check("AUDIT-05", audit.get("summary", {}).get("criteria_hold") == 8, "summary hold count")
    check("AUDIT-06", audit.get("summary", {}).get("next_stage_authorized") is False, "summary no next stage")
    check("AUDIT-07", audit.get("summary", {}).get("cad_assets_created") == 0, "no CAD assets")
    check("AUDIT-08", len(audit.get("evidence_class_non_equivalence", [])) == 5, "five non-equivalent evidence classes")
    check("AUDIT-09", all(item.get("mpi_closure_credit") is False for item in audit["evidence_class_non_equivalence"]), "no false closure credit")

    quarantine = audit.get("route_b_values_not_inherited", [])
    expected_quarantine = [(10.0, "mm"), (25.0, "mm"), (30.0, "mm"), (4001.158, "mm")]
    check("RB-01", [(item["value"], item["unit"]) for item in quarantine] == expected_quarantine, "Route-B values explicitly enumerated")
    check("RB-02", all(item.get("inherited") is False for item in quarantine), "Route-B values quarantined")

    urdf_binding = contract["source_bindings"]["accepted_urdf"]
    check("URDF-01", urdf_binding["sha256"] == "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164", "accepted URDF frozen hash")
    robot = ET.parse(ROOT / urdf_binding["path"]).getroot()
    urdf_names = [node.attrib["name"] for node in robot.findall("joint") if node.attrib["name"] in {f"joint{i}" for i in range(1, 7)}]
    check("URDF-02", urdf_names == [f"joint{i}" for i in range(1, 7)], "accepted J1..J6 present")
    local = audit.get("mpi07_urdf_local_kinematics", {})
    check("URDF-03", local.get("joint_count") == 6, "six local joint records")
    check("URDF-04", local.get("credit") == "LOCAL_KINEMATIC_REFERENCE_ONLY", "local-only authority")
    check("URDF-05", local.get("installation_icd_closed") is False, "installation ICD remains open")
    check("URDF-06", all(j.get("installation_icd_credit") is False for j in local.get("joints", [])), "no per-joint installation credit")
    check("URDF-07", all(j.get("local_authority") == "ACCEPTED_URDF_KINEMATICS_ONLY" for j in local.get("joints", [])), "joint authority labelled")

    expected_template_mpis = {
        template_names[0]: ["MPI-01", "MPI-02"],
        template_names[1]: ["MPI-03", "MPI-04"],
        template_names[2]: ["MPI-05", "MPI-06"],
        template_names[3]: ["MPI-07"],
        template_names[4]: ["MPI-08"],
    }
    for index, (name, template) in enumerate(templates.items(), start=1):
        records = list(walk_unknown_records(template))
        check(f"TPL-{index:02d}A", template.get("covered_mpis") == expected_template_mpis[name], f"{name} MPI mapping")
        check(f"TPL-{index:02d}B", template.get("template_state") == "UNFILLED_HOLD", f"{name} unfilled")
        check(f"TPL-{index:02d}C", template.get("release_credit") is False, f"{name} no release credit")
        check(f"TPL-{index:02d}D", template.get("next_stage_authorized") is False, f"{name} no next stage")
        check(f"TPL-{index:02d}E", len(records) > 0, f"{name} contains owner input records")
        check(f"TPL-{index:02d}F", all(is_unknown_record(record) for record in records), f"{name} null/unit/source/owner/uncertainty policy")

    install = templates[template_names[3]]
    check("INST-01", set(install.get("installation_nodes", {})) == {"HN-00", "HN-01", "HN-02", "HN-03"}, "HN-00..HN-03 templates")
    check("INST-02", install.get("accepted_urdf_local_kinematic_reference", {}).get("status") == "J1_TO_J6_LOCAL_KINEMATICS_AVAILABLE__NO_INSTALLATION_ICD_CREDIT", "URDF boundary in installation template")
    life = templates[template_names[4]]
    check("LIFE-01", life.get("e17_boundary", {}).get("segments_total") == 8, "eight mission segments recognized")
    check("LIFE-02", life.get("e17_boundary", {}).get("segments_released") == 0, "zero released segments")
    check("LIFE-03", life.get("e17_boundary", {}).get("release_credit") is False, "E17 no life credit")

    check("GATE-01", gate.get("gate") == "HOLD", "gate HOLD")
    check("GATE-02", gate.get("criteria_total") == 8, "gate total 8")
    check("GATE-03", gate.get("criteria_controlled") == 0, "gate controlled 0")
    check("GATE-04", gate.get("criteria_hold") == 8, "gate hold 8")
    check("GATE-05", gate.get("next_stage_authorized") is False, "next stage false")
    check("GATE-06", gate.get("cad_generation_authorized") is False, "CAD false")
    check("GATE-07", gate.get("cad_assets_created") == 0, "CAD count zero")
    check("GATE-08", gate.get("route_b_seed_inheritance_allowed") is False, "Route-B inheritance false")
    check("GATE-09", gate.get("e17_mission_segments_total") == 8 and gate.get("e17_mission_segments_released") == 0, "E17 0/8")
    check("GATE-10", gate.get("mpi07_local_kinematics_available") is True and gate.get("mpi07_installation_icd_closed") is False, "MPI-07 split authority")
    check("GATE-11", sha256(OUT / "ROUTE_C_MPI_EVIDENCE_AUDIT_V1.json") == gate.get("audit_binding", {}).get("sha256"), "gate binds audit")

    manifest_map = {item["path"]: item for item in manifest.get("files", [])}
    check("MAN-01", len(manifest_map) == 11, "manifest binds 11 files")
    for index, item in enumerate(manifest.get("files", []), start=2):
        path = ROOT / item["path"]
        check(f"MAN-{index:02d}A", path.is_file(), f"manifest file exists: {item['path']}")
        check(f"MAN-{index:02d}B", sha256(path) == item["sha256"], f"manifest hash: {item['path']}")

    check("POLICY-BASE", policy_accepts(bundle), "baseline fail-closed package accepted")

    negative("NC-01", lambda b: b["gate"].update({"gate": "PASS"}), "Directory/package existence cannot promote gate to PASS")
    negative("NC-02", lambda b: b["gate"].update({"criteria_controlled": 8}), "RFI package cannot claim 8/8 controlled")
    negative("NC-03", lambda b: b["audit"]["audits"][0].update({"controlled": True}), "Upstream vendor BOM cannot close MPI-01")
    negative("NC-04", lambda b: b["audit"]["mpi07_urdf_local_kinematics"].update({"installation_icd_closed": True}), "J1..J6 URDF kinematics cannot close MPI-07")
    negative("NC-05", lambda b: b["gate"].update({"e17_mission_segments_released": 8}), "Eight segment names/seeds cannot masquerade as released segments")
    negative("NC-06", lambda b: b["gate"].update({"next_stage_authorized": True}), "Next stage cannot be authorized")
    negative("NC-07", lambda b: b["gate"].update({"cad_generation_authorized": True}), "CAD authorization cannot be inferred")
    negative("NC-08", lambda b: b["gate"].update({"cad_assets_created": 1}), "No CAD artifact may be claimed")
    negative("NC-09", lambda b: b["gate"].update({"route_b_seed_inheritance_allowed": True}), "Route-B seed inheritance rejected")
    negative("NC-10", lambda b: b["contract"]["route_b_quarantine"].update({"overall_diameter_mm_10": "INHERIT"}), "OD 10 mm cannot be inherited")
    negative("NC-11", lambda b: b["contract"]["route_b_quarantine"].update({"legacy_radius_mm_25": "INHERIT"}), "R25 cannot be inherited")
    negative("NC-12", lambda b: b["contract"]["route_b_quarantine"].update({"terminal_requirement_mm_30": "SELECTED_PRODUCT_LIMIT"}), "R30 cannot become selected product authority")
    negative("NC-13", lambda b: b["contract"]["route_b_quarantine"].update({"cut_length_mm_4001_158": "INHERIT"}), "4001.158 mm cannot be inherited")
    negative("NC-14", lambda b: b["templates"][template_names[0]]["electrical_loads"]["bus_supply_voltage"].pop("unit"), "Missing unit rejected")
    negative("NC-15", lambda b: b["templates"][template_names[0]]["electrical_loads"]["arm_peak_current"].pop("owner"), "Missing owner rejected")
    negative("NC-16", lambda b: b["templates"][template_names[1]]["required_global_inputs"]["voltage_drop_limit"].pop("source_revision"), "Missing source revision rejected")
    negative("NC-17", lambda b: b["templates"][template_names[2]]["selected_construction"]["finished_bundle_outer_diameter"].pop("uncertainty"), "Missing uncertainty rejected")
    negative("NC-18", lambda b: b["templates"][template_names[2]]["selected_construction"]["finished_bundle_od_tolerance"].pop("bounded_tolerance"), "Missing bounded tolerance rejected")
    negative("NC-19", lambda b: b["templates"][template_names[4]]["global_factors"]["qualification_life_factor"].update({"value": 0}), "Unknown life factor cannot be silently zero")
    negative("NC-20", lambda b: b["templates"][template_names[3]].update({"release_credit": True}), "Unfilled installation template cannot receive release credit")
    negative("NC-21", lambda b: b["contract"].update({"cad_generation_authorized": True}), "Authority contract cannot authorize CAD")

    passed = sum(item["pass"] for item in checks)
    negative_passed = sum(item["pass"] for item in negative_controls)
    all_pass = passed == len(checks) and negative_passed == len(negative_controls)
    report = {
        "schema": "ROUTE_C_MPI_EVIDENCE_AUDIT_VALIDATION_V1",
        "generated_local": "2026-08-23T17:36:00+08:00",
        "validator": "INDEPENDENT_STATIC_AND_NEGATIVE_CONTROL_VALIDATOR",
        "all_pass": all_pass,
        "checks_total": len(checks),
        "checks_passed": passed,
        "negative_controls_total": len(negative_controls),
        "negative_controls_passed": negative_passed,
        "checks": checks,
        "negative_controls": negative_controls,
        "gate_observed": gate.get("gate"),
        "criteria_controlled_observed": gate.get("criteria_controlled"),
        "criteria_total_observed": gate.get("criteria_total"),
        "next_stage_authorized_observed": gate.get("next_stage_authorized"),
        "package_hashes": {
            "authority_contract_sha256": sha256(OUT / required_files[0]),
            "audit_sha256": sha256(OUT / required_files[1]),
            "gate_sha256": sha256(OUT / required_files[7]),
            "manifest_sha256": sha256(OUT / required_files[8]),
        },
    }
    (OUT / REPORT_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "all_pass": all_pass,
        "checks": f"{passed}/{len(checks)}",
        "negative_controls": f"{negative_passed}/{len(negative_controls)}",
        "report_sha256": sha256(OUT / REPORT_NAME),
    }, ensure_ascii=False, indent=2))
    if not all_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
