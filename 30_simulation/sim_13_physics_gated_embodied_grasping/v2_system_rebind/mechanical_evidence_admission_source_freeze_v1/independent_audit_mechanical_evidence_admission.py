"""Independent read-only audit; intentionally does not import mechanical_admission."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[3]
BINDINGS = PACKAGE_ROOT / "contracts" / "MECHANICAL_EVIDENCE_SOURCE_BINDINGS_V1.json"
OUTPUT = PACKAGE_ROOT / "evidence" / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_INDEPENDENT_AUDIT_V1.json"


class _UniqueLoader(yaml.SafeLoader):
    pass


def _unique_yaml_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_yaml_mapping)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _strict_json(payload: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key}")
            result[key] = value
        return result
    return json.loads(payload.decode("utf-8"), object_pairs_hook=unique, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def _canonical_path(relative: str) -> Path:
    pure = PurePosixPath(relative)
    if not isinstance(relative, str) or pure.is_absolute() or pure.as_posix() != relative or any(part in ("", ".", "..") for part in pure.parts) or "\\" in relative or ":" in relative:
        raise ValueError("noncanonical path")
    path = PROJECT_ROOT.joinpath(*pure.parts)
    cursor = PROJECT_ROOT
    for part in pure.parts:
        cursor = cursor / part
        stat = cursor.lstat()
        if cursor.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & 0x400):
            raise ValueError("symlink/reparse path")
    if path.resolve(strict=True).relative_to(PROJECT_ROOT.resolve()).as_posix() != relative:
        raise ValueError("path alias")
    return path


def _load_sources():
    binding_payload = BINDINGS.read_bytes()
    binding = _strict_json(binding_payload)
    sources = {}
    receipts = []
    for spec in binding["artifacts"]:
        path = _canonical_path(spec["path"])
        payload = path.read_bytes()
        if len(payload) != spec["bytes"] or _sha(payload) != spec["sha256"]:
            raise ValueError(f"binding mismatch: {spec['id']}")
        if spec["format"] == "JSON":
            document = _strict_json(payload)
        elif spec["format"] == "YAML":
            document = yaml.load(payload.decode("utf-8"), Loader=_UniqueLoader)
        elif spec["format"] == "URDF_XML":
            document = ET.fromstring(payload)
        else:
            document = None
        expected_schema = spec.get("expected_schema")
        if expected_schema is not None and document.get("schema") != expected_schema:
            raise ValueError(f"schema mismatch: {spec['id']}")
        sources[spec["id"]] = document
        receipts.append({"id": spec["id"], "path": spec["path"], "bytes": len(payload), "sha256": _sha(payload)})
    for relative in binding["required_absent_paths"]:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
            raise ValueError("invalid absence path")
        if PROJECT_ROOT.joinpath(*pure.parts).exists():
            raise ValueError("required absence exists")
    return binding, sources, receipts


def build_audit() -> dict:
    binding, source, receipts = _load_sources()
    frame = source["frame_tree"]
    boundary = source["rebind_boundary"]
    selected = frame["mode_topology"]["EXPLICIT_STRUCTURE_PLUS_RESIDUAL"]
    urdf = source["b601_urdf"]
    urdf_links = urdf.findall("link")
    urdf_joints = urdf.findall("joint")
    urdf_mass = sum(float(link.find("./inertial/mass").attrib["value"]) for link in urdf_links)
    b601_joint_names = [joint.attrib["name"] for joint in urdf_joints]
    separation = boundary["selected_system_contract"]["mass_authority_separation"]
    trajectory = source["trajectory_contract"]
    collision = source["collision_audit"]
    contact = source["contact_contract"]
    gripper = source["gripper_interface"]
    checks = {
        "all_27_sources_path_bytes_sha_bound": len(receipts) == 27,
        "topology_19_16_3_18": tuple(selected[k] for k in ("total_links", "physical_links", "frame_only_links", "joints")) == (19, 16, 3, 18),
        "joint_types_10_6_2_and_actuated_8": selected["joint_type_counts"] == {"fixed": 10, "revolute": 6, "prismatic": 2} and selected["actuated_dof"] == 8,
        "B601_10_links_9_joints_ordered": len(urdf_links) == 10 and b601_joint_names == ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint", "gripper_joint1", "gripper_joint2"],
        "B601_mass_exact": abs(urdf_mass - 4.695555949342986) <= 1e-12,
        "D_M_numeric_equal_semantic_distinct": frame["canonical_absolute_frames_in_spacecraft_bus_S"]["D_BUS_MATE_PHYSICAL"]["T_S_frame"] == frame["canonical_absolute_frames_in_spacecraft_bus_S"]["M_DYNAMICS_NONPHYSICAL"]["T_S_frame"] and frame["canonical_absolute_frames_in_spacecraft_bus_S"]["M_DYNAMICS_NONPHYSICAL"]["semantic_alias_permitted"] is False,
        "physical_path_excludes_M": boundary["frame_and_load_path_contract"]["physical_path"] == ["spacecraft_bus", "D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN", "load_bridge_candidate", "m3r_lumped_link", "base_link"],
        "mass_anti_double_count": abs(separation["residual_bus_mass_kg"] + separation["explicit_structure_mass_kg"] - separation["recomposed_bus_mass_kg"]) <= 1e-12 and boundary["selected_system_contract"]["total_mass_kg"] != separation["prohibited_double_count_total_kg"],
        "mesh_diagnostic_not_collision_authority": len([key for key in source if key.startswith("mesh_")]) == 10 and collision["narrow_phase_available"] is False and collision["system_collision_release"] is False,
        "urdf_velocity_not_physical": gripper["model_layer"]["urdf_velocity_limit_literal_m_s"] == 15.0 and gripper["model_layer"]["role"] == "MODEL_LIMIT_ONLY" and gripper["physical_actuator_layer"]["rated_speed_m_s"] is None,
        "contact_stays_null_and_unauthorized": contact["normal_contact"]["normal_stiffness_N_per_m"]["estimate"] is None and contact["physical_contact_kernel_authorized"] is False,
        "candidate_trajectory_not_release": len(trajectory["segments"]) == 8 and all(item["status"] == "UNKNOWN" and item["released_for_mission_gate"] is False for item in trajectory["segments"]),
        "system_urdf_and_interface_absent": len(binding["required_absent_paths"]) == 2,
    }
    passed = all(checks.values())
    return {
        "schema": "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_INDEPENDENT_AUDIT_V1",
        "independent_audit_pass": passed,
        "audit_status": "PASS_INDEPENDENT_SOURCE_ONLY_AUDIT" if passed else "FAIL_INDEPENDENT_SOURCE_ONLY_AUDIT",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "source_receipt_count": len(receipts),
        "imports_production_evaluator": False,
        "system_urdf_available": False,
        "current_system_bound": False,
        "physical_contact_ready": False,
        "dynamics_capture_entry_authorized": False,
        "next_stage_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = build_audit()
    if not document["independent_audit_pass"]:
        return 1
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes((json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"))
    print(f"independent_audit={document['audit_status']} checks={document['checks_passed']}/{document['checks_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
