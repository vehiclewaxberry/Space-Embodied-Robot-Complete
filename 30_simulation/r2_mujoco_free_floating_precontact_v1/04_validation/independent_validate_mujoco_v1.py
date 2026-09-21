"""Independent audit for the isolated R2 MuJoCo pre-contact package.

This validator deliberately does not import the candidate conversion/control
module.  It re-reads the pinned sources, URDF, emitted MJCF, Gate and package
manifest using only the Python standard library and the pinned MuJoCo runtime.
Its PASS is an evidence-integrity result, never an authority upgrade.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys
from typing import Any, Callable, Mapping, Sequence
import xml.etree.ElementTree as ET

import mujoco


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
AUTHORITY_DIR = PACKAGE_ROOT / "00_authority"
MODEL_DIR = PACKAGE_ROOT / "01_model"
RESULTS_DIR = PACKAGE_ROOT / "results"

CONTRACT_PATH = AUTHORITY_DIR / "R2_MUJOCO_FREE_FLOATING_PRECONTACT_CONTRACT_V1.json"
SOURCE_LOCK_PATH = AUTHORITY_DIR / "SOURCE_AUTHORITY_LOCK_V1.json"
GATE_PATH = RESULTS_DIR / "R2_MUJOCO_FREE_FLOATING_PRECONTACT_GATE_V1.json"
MANIFEST_PATH = RESULTS_DIR / "R2_MUJOCO_PACKAGE_MANIFEST_V1.json"
SHA_CSV_PATH = RESULTS_DIR / "R2_MUJOCO_SHA256_V1.csv"

LANES = (
    "LOCKED_2P_REDUCED_6R",
    "LOCKED_2P_EQUALITY_6R2P",
    "FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL",
)
R_JOINTS = tuple(f"joint{index}" for index in range(1, 7))
P_JOINTS = ("gripper_joint1", "gripper_joint2")


class ValidationError(RuntimeError):
    """A malformed or inconsistent audit input."""


def _reject_constant(token: str) -> None:
    raise ValidationError(f"NONFINITE_JSON_CONSTANT:{token}")


def _unique_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValidationError(f"DUPLICATE_JSON_KEY:{key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )
    if not isinstance(value, dict):
        raise ValidationError(f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationError("NONFINITE_REPORT_VALUE")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def resolve_project_path(path_text: str) -> Path:
    logical = PurePosixPath(path_text)
    if logical.is_absolute() or ".." in logical.parts or not logical.parts:
        raise ValidationError(f"UNSAFE_PROJECT_PATH:{path_text}")
    resolved = (PROJECT_ROOT / Path(*logical.parts)).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ValidationError(f"PROJECT_PATH_ESCAPE:{path_text}") from exc
    return resolved


class Group:
    """Small fail-closed check ledger with JSON-serializable details."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.checks: dict[str, bool] = {}
        self.details: dict[str, Any] = {}

    def check(self, name: str, condition: Any, detail: Any | None = None) -> None:
        self.checks[name] = condition is True or bool(condition)
        if detail is not None:
            self.details[name] = detail

    def result(self) -> dict[str, Any]:
        return {
            "checks": self.checks,
            "checks_passed": sum(self.checks.values()),
            "checks_total": len(self.checks),
            "all_pass": bool(self.checks) and all(self.checks.values()),
            "details": _json_safe(self.details),
        }


def _run_group(name: str, callback: Callable[[Group], None]) -> dict[str, Any]:
    group = Group(name)
    try:
        callback(group)
    except Exception as exc:  # fail closed while preserving the audit receipt
        group.check("group_execution", False)
        group.details["exception"] = f"{type(exc).__name__}:{exc}"
    return group.result()


def _source_pin_group(group: Group, source_lock: Mapping[str, Any]) -> None:
    pins = source_lock.get("pins")
    group.check("schema", source_lock.get("schema") == "R2_MUJOCO_FREE_FLOATING_PRECONTACT_SOURCE_AUTHORITY_LOCK_V1")
    group.check("pins_nonempty", isinstance(pins, list) and bool(pins))
    if not isinstance(pins, list):
        return
    identifiers: set[str] = set()
    paths: set[str] = set()
    rows: list[dict[str, Any]] = []
    all_match = True
    for raw in pins:
        if not isinstance(raw, dict):
            raise ValidationError("SOURCE_PIN_NOT_OBJECT")
        identifier = raw.get("id")
        path_text = raw.get("path")
        if not isinstance(identifier, str) or not isinstance(path_text, str):
            raise ValidationError("SOURCE_PIN_ID_OR_PATH_INVALID")
        duplicate = identifier in identifiers or path_text in paths
        identifiers.add(identifier)
        paths.add(path_text)
        path = resolve_project_path(path_text)
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = sha256_file(path) if exists else None
        match = (
            not duplicate
            and exists
            and type(raw.get("bytes")) is int
            and actual_bytes == raw.get("bytes")
            and actual_sha == raw.get("sha256")
        )
        all_match = all_match and match
        rows.append(
            {
                "id": identifier,
                "path": path_text,
                "exists": exists,
                "duplicate": duplicate,
                "expected_bytes": raw.get("bytes"),
                "actual_bytes": actual_bytes,
                "expected_sha256": raw.get("sha256"),
                "actual_sha256": actual_sha,
                "match": match,
            }
        )
    group.check("unique_ids_and_paths", len(identifiers) == len(pins) and len(paths) == len(pins))
    group.check("all_bytes_and_sha256_match", all_match)
    group.check("mutation_authorized_false", source_lock.get("mutation_authorized") is False)
    group.check("parent_upgrade_authorized_false", source_lock.get("parent_gate_upgrade_authorized") is False)
    group.check("next_stage_authorized_false", source_lock.get("next_stage_authorized") is False)
    group.check("release_credit_false", source_lock.get("release_credit") is False)
    group.details["pins"] = rows


def _parse_urdf(source_lock: Mapping[str, Any]) -> dict[str, Any]:
    pins = {pin["id"]: pin for pin in source_lock["pins"]}
    path = resolve_project_path(pins["unified_r2_urdf"]["path"])
    robot = ET.fromstring(path.read_bytes())
    if robot.tag != "robot":
        raise ValidationError("URDF_ROOT_NOT_ROBOT")
    link_nodes = robot.findall("link")
    joint_nodes = robot.findall("joint")
    links: dict[str, ET.Element] = {}
    masses: dict[str, float] = {}
    for node in link_nodes:
        name = node.get("name", "")
        if not name or name in links:
            raise ValidationError(f"URDF_LINK_NAME_INVALID:{name}")
        links[name] = node
        inertial = node.find("inertial")
        if inertial is not None:
            mass_node = inertial.find("mass")
            if mass_node is None:
                raise ValidationError(f"URDF_INERTIAL_MASS_MISSING:{name}")
            mass = float(mass_node.get("value", "nan"))
            if not math.isfinite(mass) or mass <= 0.0:
                raise ValidationError(f"URDF_MASS_INVALID:{name}")
            masses[name] = mass
    children: set[str] = set()
    edges: list[tuple[str, str, str, str]] = []
    type_counts = {"fixed": 0, "revolute": 0, "prismatic": 0}
    joint_names: set[str] = set()
    for node in joint_nodes:
        name = node.get("name", "")
        kind = node.get("type", "")
        parent_node, child_node = node.find("parent"), node.find("child")
        if not name or name in joint_names or kind not in type_counts:
            raise ValidationError(f"URDF_JOINT_INVALID:{name}")
        if parent_node is None or child_node is None:
            raise ValidationError(f"URDF_JOINT_TREE_MISSING:{name}")
        parent = parent_node.get("link", "")
        child = child_node.get("link", "")
        if parent not in links or child not in links or child in children:
            raise ValidationError(f"URDF_JOINT_TREE_INVALID:{name}")
        joint_names.add(name)
        children.add(child)
        edges.append((name, kind, parent, child))
        type_counts[kind] += 1
    roots = set(links) - children
    return {
        "path": path,
        "links": links,
        "masses": masses,
        "edges": edges,
        "type_counts": type_counts,
        "roots": roots,
        "total_mass_kg": math.fsum(masses.values()),
    }


def _name(model: mujoco.MjModel, object_type: Any, object_id: int) -> str:
    value = mujoco.mj_id2name(model, object_type, object_id)
    if value is None:
        raise ValidationError(f"UNNAMED_MUJOCO_OBJECT:{object_type}:{object_id}")
    return value


def _id(model: mujoco.MjModel, object_type: Any, name: str) -> int:
    value = int(mujoco.mj_name2id(model, object_type, name))
    if value < 0:
        raise ValidationError(f"MUJOCO_NAME_NOT_FOUND:{name}")
    return value


def _compile_lane(path: Path) -> tuple[mujoco.MjModel, mujoco.MjData]:
    xml_text = path.read_text(encoding="utf-8")
    model = mujoco.MjModel.from_xml_string(xml_text)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


def _model_group(group: Group, contract: Mapping[str, Any], source_lock: Mapping[str, Any]) -> None:
    expected_python = tuple(int(token) for token in contract["environment"]["python_major_minor"].split("."))
    group.check("python_major_minor_exact", sys.version_info[:2] == expected_python, list(sys.version_info[:2]))
    group.check("mujoco_python_version_exact", mujoco.__version__ == contract["environment"]["mujoco_version"], mujoco.__version__)
    group.check("mujoco_runtime_version_exact", mujoco.mj_versionString() == contract["environment"]["mujoco_version"], mujoco.mj_versionString())

    source_tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=str(Path(__file__)))
    imported_roots: set[str] = set()
    for node in ast.walk(source_tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    nonstandard_imports = imported_roots - set(sys.stdlib_module_names) - {"mujoco"}
    group.check("validator_imports_only_stdlib_and_mujoco", not nonstandard_imports, sorted(nonstandard_imports))

    urdf = _parse_urdf(source_lock)
    expected_model = contract["model"]
    group.check("urdf_root_exact", urdf["roots"] == {expected_model["root_link"]}, sorted(urdf["roots"]))
    group.check("urdf_link_count", len(urdf["links"]) == expected_model["source_links"], len(urdf["links"]))
    group.check("urdf_joint_count", len(urdf["edges"]) == expected_model["source_joints"], len(urdf["edges"]))
    group.check("urdf_physical_link_count", len(urdf["masses"]) == expected_model["physical_links"], len(urdf["masses"]))
    group.check(
        "urdf_frame_only_link_count",
        len(urdf["links"]) - len(urdf["masses"]) == expected_model["frame_only_links"],
        len(urdf["links"]) - len(urdf["masses"]),
    )
    group.check("urdf_joint_type_counts", urdf["type_counts"] == {"fixed": 10, "revolute": 6, "prismatic": 2}, urdf["type_counts"])
    mass_tolerance = float(contract["thresholds"]["total_mass_abs_kg"])
    group.check(
        "urdf_total_mass",
        abs(urdf["total_mass_kg"] - float(expected_model["total_mass_kg"])) <= mass_tolerance,
        {"urdf_kg": urdf["total_mass_kg"], "contract_kg": expected_model["total_mass_kg"]},
    )

    lane_details: dict[str, Any] = {}
    source_body_names = set(urdf["links"])
    contact_bit = int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
    for lane in LANES:
        path = MODEL_DIR / f"{lane}.xml"
        xml_root = ET.fromstring(path.read_bytes())
        option_flag = xml_root.find("./option/flag")
        xml_geoms = list(xml_root.iter("geom"))
        xml_contact_disabled = option_flag is not None and option_flag.get("contact") == "disable"
        xml_collision_bits_zero = bool(xml_geoms) and all(
            node.get("contype") == "0" and node.get("conaffinity") == "0"
            for node in xml_geoms
        )
        xml_contact_pairs_absent = xml_root.find("./contact") is None
        actuator = xml_root.find("./actuator")
        actuator_children = [] if actuator is None else list(actuator)
        xml_direct_motor_only = (
            len(actuator_children) == 6
            and all(node.tag == "motor" for node in actuator_children)
        )
        model, data = _compile_lane(path)
        body_names = {_name(model, mujoco.mjtObj.mjOBJ_BODY, index) for index in range(1, model.nbody)}
        joint_names = {_name(model, mujoco.mjtObj.mjOBJ_JOINT, index) for index in range(model.njnt)}
        free_id = _id(model, mujoco.mjtObj.mjOBJ_JOINT, expected_model["free_joint"])
        root_id = _id(model, mujoco.mjtObj.mjOBJ_BODY, expected_model["root_link"])
        expected_movable = set(R_JOINTS)
        if lane != "LOCKED_2P_REDUCED_6R":
            expected_movable.update(P_JOINTS)
        expected_joint_names = expected_movable | {expected_model["free_joint"]}

        topology_mismatches: list[dict[str, str]] = []
        for _, _, parent, child in urdf["edges"]:
            child_id = _id(model, mujoco.mjtObj.mjOBJ_BODY, child)
            actual_parent = _name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.body_parentid[child_id]))
            if actual_parent != parent:
                topology_mismatches.append({"child": child, "expected_parent": parent, "actual_parent": actual_parent})

        body_mass_max_abs = 0.0
        for body_name in source_body_names:
            body_id = _id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
            expected_mass = urdf["masses"].get(body_name, 0.0)
            body_mass_max_abs = max(body_mass_max_abs, abs(float(model.body_mass[body_id]) - expected_mass))
        total_mass = math.fsum(float(model.body_mass[index]) for index in range(model.nbody))
        all_contype_zero = all(int(value) == 0 for value in model.geom_contype)
        all_conaffinity_zero = all(int(value) == 0 for value in model.geom_conaffinity)
        q_dof = model.nv - 6

        lane_ok = (
            model.nbody == len(source_body_names) + 1
            and body_names == source_body_names
            and joint_names == expected_joint_names
            and int(model.jnt_type[free_id]) == int(mujoco.mjtJoint.mjJNT_FREE)
            and int(model.jnt_bodyid[free_id]) == root_id
            and q_dof == int(contract["lanes"][lane]["dof"])
            and model.nu == 6
            and not topology_mismatches
            and body_mass_max_abs <= float(contract["thresholds"]["link_mass_com_inertia_max_abs_si"])
            and abs(total_mass - float(expected_model["total_mass_kg"])) <= mass_tolerance
            and all(float(value) == 0.0 for value in model.opt.gravity)
            and int(model.opt.integrator) == int(mujoco.mjtIntegrator.mjINT_RK4)
            and xml_contact_disabled
            and xml_collision_bits_zero
            and xml_contact_pairs_absent
            and xml_direct_motor_only
            and bool(int(model.opt.disableflags) & contact_bit)
            and all_contype_zero
            and all_conaffinity_zero
            and data.ncon == 0
        )
        expected_neq = 2 if lane == "LOCKED_2P_EQUALITY_6R2P" else 0
        lane_ok = lane_ok and model.neq == expected_neq
        if lane == "LOCKED_2P_EQUALITY_6R2P":
            equality_names = {
                _name(model, mujoco.mjtObj.mjOBJ_EQUALITY, index)
                for index in range(model.neq)
            }
            lane_ok = lane_ok and equality_names == {
                "soft_lock_gripper_joint1",
                "soft_lock_gripper_joint2",
            }
        else:
            equality_names = set()
        lane_details[lane] = {
            "pass": lane_ok,
            "nq": model.nq,
            "nv": model.nv,
            "nbody": model.nbody,
            "njnt": model.njnt,
            "nu": model.nu,
            "neq": model.neq,
            "ngeom": model.ngeom,
            "ncon_after_forward": data.ncon,
            "joint_names": sorted(joint_names),
            "equality_names": sorted(equality_names),
            "total_mass_kg": total_mass,
            "body_mass_max_abs_kg": body_mass_max_abs,
            "topology_mismatches": topology_mismatches,
            "contact_disabled": bool(int(model.opt.disableflags) & contact_bit),
            "xml_contact_disabled": xml_contact_disabled,
            "xml_collision_bits_zero": xml_collision_bits_zero,
            "xml_contact_pairs_absent": xml_contact_pairs_absent,
            "xml_direct_motor_only": xml_direct_motor_only,
            "all_geom_contype_zero": all_contype_zero,
            "all_geom_conaffinity_zero": all_conaffinity_zero,
        }
        group.check(f"lane_{lane}", lane_ok)
    group.check("all_three_lanes_compiled", len(lane_details) == 3)
    group.check("target_absent_by_contract", expected_model.get("target_present") is False)
    group.check("collision_and_contact_contract_false", expected_model.get("collision_enabled") is False and expected_model.get("contact_enabled") is False)
    group.details["lanes"] = lane_details


def _gate_group(group: Group, contract: Mapping[str, Any]) -> None:
    gate = load_json(GATE_PATH)
    boundary = gate.get("authority_boundaries")
    group.check("schema", gate.get("schema") == "R2_MUJOCO_FREE_FLOATING_PRECONTACT_CROSS_SOLVER_DIAGNOSTIC_GATE_V1")
    group.check("maximum_claim_exact", gate.get("maximum_allowed_claim") == contract.get("maximum_legal_claim"))
    group.check("authority_mapping_exact", boundary == contract.get("authority_boundaries"))
    group.check("all_authority_values_literal_false", isinstance(boundary, dict) and bool(boundary) and all(value is False for value in boundary.values()))
    group.check("all_authority_flags_false_receipt", gate.get("all_authority_flags_false") is True)
    group.check("parent_next_stage_authorized_false", gate.get("parent_next_stage_authorized") is False)
    group.check("next_stage_authorized_false", gate.get("next_stage_authorized") is False)
    group.check("release_credit_false", gate.get("release_credit") is False)
    group.check("review_pending_owner", gate.get("review_status") == "PENDING_OWNER_REVIEW")
    group_pass = gate.get("group_pass")
    consistent = isinstance(group_pass, dict) and bool(group_pass) and gate.get("gate_pass") is all(group_pass.values())
    group.check("gate_group_reduction_consistent", consistent)
    if isinstance(group_pass, dict):
        group.check("group_counts_consistent", gate.get("groups_passed") == sum(value is True for value in group_pass.values()) and gate.get("groups_total") == len(group_pass))
    expected_claim = contract.get("maximum_legal_claim") if gate.get("gate_pass") is True else contract.get("repeat_required_claim")
    group.check("achieved_claim_consistent", gate.get("achieved_claim") == expected_claim)
    group.details["gate_pass"] = gate.get("gate_pass")
    group.details["achieved_claim"] = gate.get("achieved_claim")


def _manifest_group(group: Group) -> None:
    manifest = load_json(MANIFEST_PATH)
    group.check("schema", manifest.get("schema") == "R2_MUJOCO_PACKAGE_MANIFEST_V1")
    records = manifest.get("files")
    group.check("records_nonempty", isinstance(records, list) and bool(records))
    if not isinstance(records, list):
        return
    expected_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    all_match = True
    for raw in records:
        if not isinstance(raw, dict) or not isinstance(raw.get("path"), str):
            raise ValidationError("MANIFEST_RECORD_INVALID")
        path_text = raw["path"]
        duplicate = path_text in seen
        seen.add(path_text)
        path = resolve_project_path(path_text)
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = sha256_file(path) if exists else None
        match = (
            not duplicate
            and exists
            and type(raw.get("bytes")) is int
            and raw.get("bytes") == actual_bytes
            and raw.get("sha256") == actual_sha
        )
        all_match = all_match and match
        expected_rows.append({"path": path_text, "bytes": raw.get("bytes"), "sha256": raw.get("sha256")})
    group.check("records_unique", len(seen) == len(records))
    group.check("file_count_exact", manifest.get("file_count") == len(records))
    group.check("all_manifest_files_match", all_match)
    group.check("no_cache_or_venv_receipt", manifest.get("no_cache_or_venv") is True)
    group.check("no_cache_or_venv_paths", all("__pycache__" not in PurePosixPath(row["path"]).parts and ".venv" not in PurePosixPath(row["path"]).parts and not row["path"].endswith(".pyc") for row in expected_rows))
    group.check("next_stage_authorized_false", manifest.get("next_stage_authorized") is False)
    group.check("release_credit_false", manifest.get("release_credit") is False)

    actual_inventory = {
        path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file()
        and path not in {MANIFEST_PATH, SHA_CSV_PATH}
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }
    group.check(
        "manifest_inventory_exhaustive",
        seen == actual_inventory,
        {"missing_from_manifest": sorted(actual_inventory - seen), "stale_manifest_paths": sorted(seen - actual_inventory)},
    )

    with SHA_CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    normalized_csv = [
        {"path": row.get("path"), "bytes": int(row["bytes"]), "sha256": row.get("sha256")}
        for row in csv_rows
    ]
    normalized_manifest = [
        {"path": row["path"], "bytes": int(row["bytes"]), "sha256": row["sha256"]}
        for row in records
    ]
    group.check("sha_csv_matches_manifest_records", normalized_csv == normalized_manifest)


def validate(*, require_results: bool = True) -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    source_lock = load_json(SOURCE_LOCK_PATH)
    groups = {
        "IV-G0_SOURCE_PINS": _run_group("IV-G0_SOURCE_PINS", lambda group: _source_pin_group(group, source_lock)),
        "IV-G1_URDF_MJCF_TOPOLOGY_MASS_NONCONTACT": _run_group(
            "IV-G1_URDF_MJCF_TOPOLOGY_MASS_NONCONTACT",
            lambda group: _model_group(group, contract, source_lock),
        ),
    }
    if require_results:
        groups["IV-G2_GATE_AUTHORITY_BOUNDARY"] = _run_group(
            "IV-G2_GATE_AUTHORITY_BOUNDARY", lambda group: _gate_group(group, contract)
        )
        groups["IV-G3_PACKAGE_MANIFEST"] = _run_group(
            "IV-G3_PACKAGE_MANIFEST", _manifest_group
        )
    group_pass = {name: result["all_pass"] for name, result in groups.items()}
    checks_total = sum(result["checks_total"] for result in groups.values())
    checks_passed = sum(result["checks_passed"] for result in groups.values())
    passed = bool(group_pass) and all(group_pass.values())
    return {
        "schema": "R2_MUJOCO_FREE_FLOATING_PRECONTACT_INDEPENDENT_VALIDATION_V1",
        "validation_scope": "FULL_PACKAGE" if require_results else "STATIC_SOURCE_AND_MJCF_ONLY",
        "candidate_core_imported": False,
        "runtime": {
            "python": sys.version.split()[0],
            "mujoco_python": mujoco.__version__,
            "mujoco_runtime": mujoco.mj_versionString(),
        },
        "groups": groups,
        "group_pass": group_pass,
        "groups_passed": sum(group_pass.values()),
        "groups_total": len(group_pass),
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "independent_validation_pass": passed,
        "authority_effect": "NONE_DIAGNOSTIC_ONLY",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Validate source pins and the three MJCF files before results exist.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the machine-readable validation receipt.",
    )
    args = parser.parse_args(argv)
    report = validate(require_results=not args.static_only)
    if args.output is not None:
        _write_report(args.output, report)
    print(json.dumps(_json_safe(report), indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if report["independent_validation_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
