"""Strict M4 mechanical-interface loader for Sim14.

Resolved artifacts are SHA-256 verified before use. Required artifacts with a
null hash remain explicit unresolved bindings; they are never silently skipped
when production readiness is evaluated.
"""
from __future__ import annotations

import hashlib
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


INTERFACE_SCHEMA_VERSION = "MECH_RL_INTERFACE_V2"
DIAGNOSTIC_SCHEMA_VERSION = "SIM14_DIAGNOSTIC_FIXTURE_V1"
DIAGNOSTIC_ACKNOWLEDGEMENT = (
    "I_ACKNOWLEDGE_DIAGNOSTIC_VALUES_ARE_NOT_MECHANICAL_AUTHORITY"
)
REQUIRED_CONFIGURATION_IDS = (
    "DEPLOYED_NOMINAL",
    "LEFT_PANEL_FAIL",
    "RIGHT_PANEL_FAIL",
    "BOTH_PANEL_FAIL",
    "ARM_STOWED_ONORBIT",
    "ARM_TASK_READY",
    "PREGRASP",
    "TARGET_CAPTURE_22KG",
    "TARGET_CAPTURE_150KG",
)
REQUIRED_ARTIFACT_IDS = (
    "accepted_b601_urdf",
    "m3r_working_step",
    "gripper_r1_step",
    "v5r_neutral_system_step",
    "v5r_collision_mesh",
    "master_fcstd",
    "master_step",
    "frame_tree",
    "configuration_library",
    "system_mass_properties",
    "collision_asset_register",
    "geometry_audit",
    "geometry_independent_validation",
    "mass_material_tolerance_mechanism_audit",
)
REQUIRED_CLOSURE_AUDIT_PATHS = (
    "01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml",
    "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml",
    "04_material_database/MATERIAL_PROCESS_CLOSURE_STATUS_V2.yaml",
    "04_material_database/PROTOTYPE_MATERIAL_LIBRARY_V1.yaml",
    "05_tolerance/GRIPPER_FUNCTIONAL_TOLERANCE_MAP_V1.yaml",
    "05_tolerance/HINGE_DEPLOYMENT_TOLERANCE_CHAIN_V1.yaml",
    "05_tolerance/INTERFACE_STACKUP_B601_M3R_V1.yaml",
    "05_tolerance/TOLERANCE_CLOSURE_EXECUTION_PLAN_V1.yaml",
    "06_mechanism/GRIPPER_R1_MECHANISM_RELEASE_STATUS_V2.yaml",
    "06_mechanism/HDRM_PROTOTYPE_CLOSURE_PLAN_V1.yaml",
    "06_mechanism/MECHANISM_STATUS_REGISTER_V1.yaml",
    "06_mechanism/MECHANISM_VERIFICATION_REQUIREMENTS_V1.csv",
)
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class InterfaceError(ValueError):
    """Base class for an invalid or incomplete Sim14 interface."""


class InterfaceSchemaError(InterfaceError):
    """Raised when the interface shape or semantics are invalid."""


class ArtifactHashMismatch(InterfaceError):
    """Raised when a resolved artifact no longer matches its binding."""


class DiagnosticAuthorizationError(InterfaceError):
    """Raised when a test fixture is requested without explicit acknowledgement."""


@dataclass(frozen=True)
class ArtifactBinding:
    artifact_id: str
    path: Path
    relative_path: str
    sha256: str | None
    size_bytes: int | None
    binding_required: bool
    authority_status: str

    @property
    def resolved(self) -> bool:
        return self.sha256 is not None and self.size_bytes is not None


@dataclass(frozen=True)
class MechanicalInterfaceBundle:
    manifest_path: Path
    manifest_sha256: str
    asset_root: Path
    artifacts: Mapping[str, ArtifactBinding]
    required_configurations: tuple[str, ...]
    declared_production_ready: bool
    blocker_codes: tuple[str, ...]
    computed_missing_authorities: tuple[str, ...]
    configuration_release_counts: Mapping[str, int]
    numeric_mass_diagnostic_available_count: int
    full_mass_properties_loader_ready_count: int
    closure_audited_artifact_count: int
    document: Mapping[str, Any]

    @property
    def unresolved_required_artifacts(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, binding in self.artifacts.items()
            if binding.binding_required and not binding.resolved
        )

    @property
    def production_ready(self) -> bool:
        return (
            self.declared_production_ready
            and not self.unresolved_required_artifacts
            and not self.computed_missing_authorities
            and not self.blocker_codes
            and self.full_mass_properties_loader_ready_count
            == len(self.required_configurations)
        )


@dataclass(frozen=True)
class DiagnosticRigidBody:
    mass_kg: float
    inertia_about_com_kg_m2: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    initial_position_m: tuple[float, float, float]
    initial_linear_velocity_mps: tuple[float, float, float]
    initial_angular_velocity_radps: tuple[float, float, float]
    evidence_class: str


@dataclass(frozen=True)
class DiagnosticAnchor:
    anchor_id: str
    target_kind: str
    body: DiagnosticRigidBody


@dataclass(frozen=True)
class DiagnosticFixture:
    path: Path
    sha256: str
    scope: str
    service_spacecraft: DiagnosticRigidBody
    anchors: Mapping[str, DiagnosticAnchor]


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in output:
            raise InterfaceSchemaError(f"duplicate mapping key: {key}")
        output[key] = loader.construct_object(value_node, deep=deep)
    return output


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _load_mapping(path: Path) -> Mapping[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise InterfaceSchemaError(f"cannot parse structured file {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise InterfaceSchemaError(f"structured root must be a mapping: {path}")
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InterfaceSchemaError(f"{label} must be a mapping")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise InterfaceSchemaError(f"{label} must be a sequence")
    return value


def _finite_vector(value: Any, length: int, label: str) -> tuple[float, ...]:
    raw = _sequence(value, label)
    if len(raw) != length:
        raise InterfaceSchemaError(f"{label} must contain {length} numbers")
    try:
        result = tuple(float(item) for item in raw)
    except (TypeError, ValueError) as exc:
        raise InterfaceSchemaError(f"{label} must contain numbers") from exc
    if not all(math.isfinite(item) for item in result):
        raise InterfaceSchemaError(f"{label} contains a non-finite value")
    return result


def _positive(value: Any, label: str) -> float:
    try:
        output = float(value)
    except (TypeError, ValueError) as exc:
        raise InterfaceSchemaError(f"{label} must be numeric") from exc
    if not math.isfinite(output) or output <= 0.0:
        raise InterfaceSchemaError(f"{label} must be finite and positive")
    return output


def _positive_definite_matrix3(
    value: Any,
    label: str,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    rows = _sequence(value, label)
    if len(rows) != 3:
        raise InterfaceSchemaError(f"{label} must contain three rows")
    matrix = tuple(
        _finite_vector(row, 3, f"{label}[{index}]")
        for index, row in enumerate(rows)
    )
    for i in range(3):
        for j in range(3):
            if not math.isclose(matrix[i][j], matrix[j][i], rel_tol=0.0, abs_tol=1e-12):
                raise InterfaceSchemaError(f"{label} must be symmetric")
    first_minor = matrix[0][0]
    second_minor = matrix[0][0] * matrix[1][1] - matrix[0][1] ** 2
    determinant = (
        matrix[0][0]
        * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )
    if first_minor <= 0.0 or second_minor <= 0.0 or determinant <= 0.0:
        raise InterfaceSchemaError(f"{label} must be positive definite")
    return matrix  # type: ignore[return-value]


def _resolve_under(root: Path, raw_path: Any, label: str) -> tuple[Path, str]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise InterfaceSchemaError(f"{label}.path must be a non-empty relative path")
    relative = Path(raw_path)
    if relative.is_absolute():
        raise InterfaceSchemaError(f"{label}.path must be relative")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise InterfaceSchemaError(f"{label}.path escapes asset_root") from exc
    return resolved, relative.as_posix()


def _load_artifact(
    artifact_id: str,
    raw: Any,
    asset_root: Path,
) -> ArtifactBinding:
    record = _mapping(raw, f"artifacts.{artifact_id}")
    path, relative = _resolve_under(
        asset_root, record.get("path"), f"artifacts.{artifact_id}"
    )
    required = record.get("binding_required")
    if not isinstance(required, bool):
        raise InterfaceSchemaError(
            f"artifacts.{artifact_id}.binding_required must be boolean"
        )
    status = record.get("authority_status")
    if not isinstance(status, str) or not status:
        raise InterfaceSchemaError(
            f"artifacts.{artifact_id}.authority_status must be non-empty"
        )
    expected_hash = record.get("sha256")
    if expected_hash is None:
        if "PENDING" not in status and "HOLD" not in status:
            raise InterfaceSchemaError(
                f"unresolved artifact {artifact_id} must carry PENDING or HOLD status"
            )
        return ArtifactBinding(
            artifact_id, path, relative, None, None, required, status
        )
    if not isinstance(expected_hash, str) or not _SHA256_RE.fullmatch(expected_hash):
        raise InterfaceSchemaError(
            f"artifacts.{artifact_id}.sha256 must be null or 64 hexadecimal characters"
        )
    if not path.is_file() or path.stat().st_size <= 0:
        raise InterfaceError(f"resolved artifact is missing or empty: {path}")
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash.upper():
        raise ArtifactHashMismatch(
            f"{artifact_id} SHA-256 mismatch: expected {expected_hash.upper()}, "
            f"got {actual_hash}"
        )
    return ArtifactBinding(
        artifact_id,
        path,
        relative,
        actual_hash,
        path.stat().st_size,
        required,
        status,
    )


def _validate_units(document: Mapping[str, Any]) -> None:
    units = _mapping(document.get("units"), "units")
    expected = {
        "length": "m",
        "mass": "kg",
        "inertia": "kg*m^2",
        "linear_velocity": "m/s",
        "angular_velocity": "rad/s",
        "force": "N",
        "torque": "N*m",
        "pressure": "Pa",
    }
    if dict(units) != expected:
        raise InterfaceSchemaError(f"units must be exactly {expected}")


def _validate_b601_urdf(path: Path, declared_mass: Any) -> None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise InterfaceSchemaError(f"invalid accepted B601 URDF: {path}") from exc
    links = root.findall("link")
    joints = root.findall("joint")
    if len(links) != 10 or len(joints) != 9:
        raise InterfaceSchemaError("accepted B601 URDF must remain 10 links / 9 joints")
    joint_counts: dict[str, int] = {}
    for joint in joints:
        joint_type = joint.attrib.get("type")
        if joint_type == "continuous":
            joint_type = "revolute"
        joint_counts[str(joint_type)] = joint_counts.get(str(joint_type), 0) + 1
    if joint_counts != {"revolute": 6, "fixed": 1, "prismatic": 2}:
        raise InterfaceSchemaError(f"accepted B601 topology changed: {joint_counts}")
    masses: list[float] = []
    for link in links:
        mass_node = link.find("./inertial/mass")
        if mass_node is None:
            raise InterfaceSchemaError("every B601 link must have an inertial mass")
        masses.append(_positive(mass_node.attrib.get("value"), "URDF link mass"))
    expected_mass = _positive(declared_mass, "mechanical_properties.b601.mass_kg")
    if not math.isclose(math.fsum(masses), expected_mass, rel_tol=0.0, abs_tol=1e-9):
        raise InterfaceSchemaError("declared B601 mass does not match accepted URDF")


def _validate_configuration_library(
    path: Path,
    expected_ids: tuple[str, ...],
    declared: Mapping[str, Any],
) -> Mapping[str, int]:
    document = _load_mapping(path)
    if document.get("schema_version") != "CONFIGURATION_LIBRARY_V1":
        raise InterfaceSchemaError("configuration library schema changed")
    if document.get("configuration_count") != 9:
        raise InterfaceSchemaError("configuration library must contain nine configurations")
    field_contract = _mapping(document.get("field_contract"), "field_contract")
    if field_contract.get("zero_fill_forbidden") is not True:
        raise InterfaceSchemaError("configuration library must forbid zero fill")
    if field_contract.get("diagnostic_value_is_release_value") is not False:
        raise InterfaceSchemaError("diagnostic values may not become release values")
    if (
        field_contract.get("required_inertia_reference_point")
        != "configuration_system_CG"
    ):
        raise InterfaceSchemaError(
            "configuration inertia reference point must be configuration_system_CG"
        )
    frame_resolution = str(field_contract.get("reference_frame_resolution"))
    if "spacecraft_assembly_frame" not in frame_resolution or "identity alias of S" not in frame_resolution:
        raise InterfaceSchemaError(
            "configuration frame contract must use the identity alias of S"
        )
    raw_configurations = _sequence(document.get("configurations"), "configurations")
    names: list[str] = []
    released_mass_count = 0
    released_cg_count = 0
    released_inertia_count = 0
    required_sections = {
        "mass",
        "cg",
        "inertia",
        "bbox",
        "frames",
        "collision",
        "confidence",
        "status",
    }
    for index, raw in enumerate(raw_configurations):
        record = _mapping(raw, f"configurations[{index}]")
        missing_sections = required_sections - set(record)
        if missing_sections:
            raise InterfaceSchemaError(
                f"configuration {index} lacks {sorted(missing_sections)}"
            )
        name = record.get("name")
        if not isinstance(name, str):
            raise InterfaceSchemaError(f"configuration {index} name is invalid")
        names.append(name)
        mass = _mapping(record["mass"], f"configurations[{index}].mass")
        cg = _mapping(record["cg"], f"configurations[{index}].cg")
        inertia = _mapping(record["inertia"], f"configurations[{index}].inertia")
        bbox = _mapping(record["bbox"], f"configurations[{index}].bbox")
        frames = _mapping(record["frames"], f"configurations[{index}].frames")
        if inertia.get("reference_point") != "configuration_system_CG":
            raise InterfaceSchemaError(
                f"configuration inertia reference point changed: {name}"
            )
        if any(
            section.get("reference_frame") != "spacecraft_assembly_frame"
            for section in (cg, inertia, bbox)
        ):
            raise InterfaceSchemaError(
                f"configuration property frame is not spacecraft_assembly_frame: {name}"
            )
        if frames.get("root") != "spacecraft_assembly_frame":
            raise InterfaceSchemaError(
                f"configuration frame root is not spacecraft_assembly_frame: {name}"
            )
        explicit_null_uncertainties = (
            (mass, "released_standard_uncertainty_kg"),
            (cg, "released_standard_uncertainty_xyz_m"),
            (inertia, "released_standard_uncertainty_matrix_kg_m2"),
        )
        if any(
            key not in section or section.get(key) is not None
            for section, key in explicit_null_uncertainties
        ):
            raise InterfaceSchemaError(
                f"configuration released uncertainty must be explicit null: {name}"
            )
        if mass.get("released_value_kg") is not None:
            released_mass_count += 1
        elif "HOLD" not in str(mass.get("status")):
            raise InterfaceSchemaError(f"null released mass lacks HOLD: {name}")
        if cg.get("released_xyz_m") is not None:
            released_cg_count += 1
        elif "HOLD" not in str(cg.get("status")):
            raise InterfaceSchemaError(f"null released center of mass lacks HOLD: {name}")
        if inertia.get("released_matrix_kg_m2") is not None:
            released_inertia_count += 1
        elif "HOLD" not in str(inertia.get("status")):
            raise InterfaceSchemaError(f"null released inertia lacks HOLD: {name}")
    if tuple(names) != expected_ids:
        raise InterfaceSchemaError("external configuration library names/order changed")
    counts = {
        "mass": released_mass_count,
        "center_of_mass": released_cg_count,
        "inertia": released_inertia_count,
    }
    declared_counts = {
        "mass": declared.get("complete_mass_count"),
        "center_of_mass": declared.get("complete_center_of_mass_count"),
        "inertia": declared.get("complete_inertia_count"),
    }
    if counts != declared_counts:
        raise InterfaceSchemaError(
            f"interface configuration counts {declared_counts} disagree with library {counts}"
        )
    summary = _mapping(document.get("summary"), "configuration summary")
    readiness_pairs = (
        (
            "numeric_mass_diagnostic_available_count",
            "numeric_mass_diagnostic_available_count",
        ),
        (
            "ready_for_full_mass_properties_diagnostic_loader_count",
            "full_mass_properties_loader_ready_count",
        ),
    )
    for summary_key, interface_key in readiness_pairs:
        if summary.get(summary_key) != declared.get(interface_key):
            raise InterfaceSchemaError(
                f"configuration summary {summary_key} disagrees with interface"
            )
    authorization = (
        "MASS_VALUE_WIRING_AND_RANGE_CHECK_ONLY_NOT_CG_INERTIA_BBOX_"
        "OR_COLLISION_LOADING"
    )
    if summary.get("diagnostic_mass_use_authorization") != authorization:
        raise InterfaceSchemaError(
            "configuration diagnostics exceed mass-value wiring/range checks"
        )
    if declared.get("diagnostic_mass_use_authorization") != authorization:
        raise InterfaceSchemaError(
            "interface diagnostic mass authorization does not match M4"
        )
    return counts


def _validate_uncertainty_subrecord(
    record: Mapping[str, Any],
    *,
    label: str,
    standard_uncertainty_key: str,
) -> None:
    required_keys = {
        standard_uncertainty_key,
        "distribution",
        "degrees_of_freedom",
        "source",
    }
    missing = required_keys - set(record)
    if missing:
        raise InterfaceSchemaError(
            f"{label} lacks uncertainty fields {sorted(missing)}"
        )
    for key in (
        standard_uncertainty_key,
        "distribution",
        "degrees_of_freedom",
    ):
        if record.get(key) is not None:
            raise InterfaceSchemaError(f"{label}.{key} must remain null/HOLD")
    if record.get("source") != "component_source_ref":
        raise InterfaceSchemaError(
            f"{label}.source must resolve through component_source_ref"
        )


def _validate_system_mass_ledger(path: Path) -> Mapping[str, int]:
    document = _load_mapping(path)
    if document.get("schema_version") != "SYSTEM_MASS_PROPERTIES_V3":
        raise InterfaceSchemaError("system mass ledger schema changed")
    if "HOLD" not in str(document.get("release_status")):
        raise InterfaceSchemaError("system mass ledger is not explicitly HOLD")
    contract = _mapping(document.get("aggregation_contract"), "aggregation_contract")
    required_controls = {
        "zero_fill_forbidden": True,
        "partial_component_release_aggregation_forbidden": True,
        "diagnostic_values_authoritative_for_simulation": False,
    }
    for key, expected in required_controls.items():
        if contract.get(key) is not expected:
            raise InterfaceSchemaError(f"aggregation_contract.{key} must be {expected}")
    if contract.get("target_frame") != "spacecraft_assembly_frame":
        raise InterfaceSchemaError(
            "system mass aggregation target must be spacecraft_assembly_frame"
        )
    required_uncertainty_inputs = (
        "estimate",
        "standard_uncertainty",
        "distribution",
        "degrees_of_freedom",
        "source",
    )
    if tuple(contract.get("required_uncertainty_inputs_per_quantity", ())) != (
        required_uncertainty_inputs
    ):
        raise InterfaceSchemaError(
            "system mass uncertainty input contract changed"
        )
    source_resolution = _mapping(
        contract.get("component_quantity_source_resolution"),
        "component_quantity_source_resolution",
    )
    if source_resolution.get("source_token") != "component_source_ref":
        raise InterfaceSchemaError("component uncertainty source token changed")
    if (
        source_resolution.get("resolves_to")
        != "component_records.<component_id>.source_ref"
    ):
        raise InterfaceSchemaError("component uncertainty source resolution changed")
    expected_sections = {
        "center_of_mass",
        "inertia_about_own_com",
        "zero_joint_diagnostic_properties",
        "named_pose_digital_properties",
    }
    if set(source_resolution.get("applies_to", ())) != expected_sections:
        raise InterfaceSchemaError("component uncertainty section coverage changed")

    source_register = _mapping(document.get("source_register"), "source_register")
    component_records = _mapping(
        document.get("component_records"), "component_records"
    )
    uncertainty_specs = {
        "center_of_mass": "standard_uncertainty_xyz_m",
        "inertia_about_own_com": "standard_uncertainty_matrix_kg_m2",
        "zero_joint_diagnostic_properties": "standard_uncertainty",
        "named_pose_digital_properties": "standard_uncertainty",
    }
    uncertainty_subrecord_count = 0
    for component_id, raw_component in component_records.items():
        component = _mapping(raw_component, f"component_records.{component_id}")
        source_ref = component.get("source_ref")
        if not isinstance(source_ref, str) or source_ref not in source_register:
            raise InterfaceSchemaError(
                f"component_records.{component_id}.source_ref is unresolved"
            )
        for section_name, standard_key in uncertainty_specs.items():
            if section_name not in component:
                continue
            section = _mapping(
                component[section_name],
                f"component_records.{component_id}.{section_name}",
            )
            _validate_uncertainty_subrecord(
                section,
                label=f"component_records.{component_id}.{section_name}",
                standard_uncertainty_key=standard_key,
            )
            uncertainty_subrecord_count += 1
    if uncertainty_subrecord_count != 14:
        raise InterfaceSchemaError(
            "system mass ledger must retain 14 CG/inertia uncertainty subrecords"
        )

    delivery = _mapping(
        document.get("nine_configuration_delivery"),
        "nine_configuration_delivery",
    )
    if delivery.get("configuration_count") != 9:
        raise InterfaceSchemaError("system mass ledger must track nine configurations")
    if any(
        delivery.get(key) != 0
        for key in (
            "released_mass_count",
            "released_center_of_mass_count",
            "released_inertia_count",
        )
    ):
        raise InterfaceSchemaError("released system property counts must remain zero in this M4 revision")
    numeric_mass_count = delivery.get("numeric_mass_diagnostic_available_count")
    full_loader_count = delivery.get("full_mass_properties_loader_ready_count")
    if numeric_mass_count != 9 or full_loader_count != 0:
        raise InterfaceSchemaError(
            "M4 permits nine mass diagnostics but zero full mass-property loaders"
        )
    authorization = str(delivery.get("diagnostic_use_authorization"))
    if authorization != (
        "MASS_VALUE_WIRING_AND_RANGE_CHECK_ONLY_NOT_CG_INERTIA_BBOX_"
        "OR_COLLISION_LOADING"
    ):
        raise InterfaceSchemaError(
            "system diagnostic authorization must remain mass-value-only"
        )
    return {
        "numeric_mass_diagnostic_available": numeric_mass_count,
        "full_mass_properties_loader_ready": full_loader_count,
        "uncertainty_subrecords": uncertainty_subrecord_count,
    }


def _validate_mass_material_tolerance_mechanism_audit(
    artifacts: Mapping[str, ArtifactBinding],
) -> int:
    binding = artifacts["mass_material_tolerance_mechanism_audit"]
    document = _load_mapping(binding.path)
    status = str(document.get("status"))
    if "PASS_FAIL_CLOSED" not in status or "M4_RELEASE_STILL_HOLD" not in status:
        raise InterfaceSchemaError(
            "M4 closure audit must pass integrity while preserving release HOLD"
        )
    raw_audited = _sequence(document.get("audited_artifacts"), "audited_artifacts")
    audited_paths: list[str] = []
    audited_by_path: dict[str, Mapping[str, Any]] = {}
    for index, raw_entry in enumerate(raw_audited):
        entry = _mapping(raw_entry, f"audited_artifacts[{index}]")
        relative = entry.get("path")
        if not isinstance(relative, str):
            raise InterfaceSchemaError(
                f"audited_artifacts[{index}].path must be relative"
            )
        if relative in audited_by_path:
            raise InterfaceSchemaError(f"duplicate closure-audit path: {relative}")
        audited_paths.append(relative)
        audited_by_path[relative] = entry
    if tuple(audited_paths) != REQUIRED_CLOSURE_AUDIT_PATHS:
        raise InterfaceSchemaError(
            "M4 closure audit must bind the exact ordered 13-artifact set"
        )

    m4_root = binding.path.parent.parent
    for relative in REQUIRED_CLOSURE_AUDIT_PATHS:
        entry = audited_by_path[relative]
        path, _ = _resolve_under(m4_root, relative, f"audit.{relative}")
        expected_hash = entry.get("sha256")
        if not isinstance(expected_hash, str) or not _SHA256_RE.fullmatch(
            expected_hash
        ):
            raise InterfaceSchemaError(f"invalid closure-audit SHA-256: {relative}")
        expected_bytes = entry.get("bytes")
        if not isinstance(expected_bytes, int) or expected_bytes <= 0:
            raise InterfaceSchemaError(f"invalid closure-audit byte count: {relative}")
        if not path.is_file():
            raise InterfaceError(f"closure-audit artifact missing: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash.upper():
            raise ArtifactHashMismatch(
                f"closure audit SHA-256 mismatch for {relative}: "
                f"expected {expected_hash.upper()}, got {actual_hash}"
            )
        if path.stat().st_size != expected_bytes:
            raise ArtifactHashMismatch(
                f"closure audit byte-count mismatch for {relative}: "
                f"expected {expected_bytes}, got {path.stat().st_size}"
            )

    cross_bindings = {
        "01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml": "frame_tree",
        "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml": "configuration_library",
        "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml": "system_mass_properties",
    }
    for relative, artifact_id in cross_bindings.items():
        nested_hash = str(audited_by_path[relative].get("sha256")).upper()
        if nested_hash != artifacts[artifact_id].sha256:
            raise InterfaceSchemaError(
                f"closure audit and interface disagree for {artifact_id}"
            )

    quality = _mapping(
        document.get("mass_property_quality_closure"),
        "mass_property_quality_closure",
    )
    required_quality_counts = {
        "configuration_inertia_reference_point_configuration_system_CG_count": 9,
        "system_CG_and_inertia_uncertainty_subrecord_count": 14,
        "null_distribution_count": 14,
        "null_degrees_of_freedom_count": 14,
        "component_source_ref_resolution_count": 14,
        "numeric_mass_diagnostic_available_count": 9,
        "full_mass_properties_diagnostic_loader_ready_count": 0,
    }
    for key, expected in required_quality_counts.items():
        if quality.get(key) != expected:
            raise InterfaceSchemaError(
                f"closure audit mass-property count {key} must be {expected}"
            )
    if quality.get("spacecraft_assembly_frame_identity_alias_to_S") != "PASS":
        raise InterfaceSchemaError("closure audit did not pass the assembly-frame alias")
    return len(raw_audited)


def _validate_geometry_safety_documents(artifacts: Mapping[str, ArtifactBinding]) -> None:
    frame_tree = _load_mapping(artifacts["frame_tree"].path)
    if frame_tree.get("schema") != "M4_DIGITAL_PROTOTYPE_FRAME_TREE_V1":
        raise InterfaceSchemaError("M4 frame-tree schema changed")
    if frame_tree.get("root_frame") != "S" or frame_tree.get("length_unit") != "mm":
        raise InterfaceSchemaError("M4 frame tree must remain rooted at S in millimetres")
    aliases = _mapping(frame_tree.get("frame_aliases"), "frame_aliases")
    assembly_alias = _mapping(
        aliases.get("spacecraft_assembly_frame"),
        "frame_aliases.spacecraft_assembly_frame",
    )
    identity4 = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    if (
        assembly_alias.get("canonical_frame") != "S"
        or assembly_alias.get("relation") != "IDENTITY_EQUIVALENCE"
        or assembly_alias.get("T_S_spacecraft_assembly_frame_rows") != identity4
        or assembly_alias.get("status")
        != "FROZEN_EXACT_ALIAS_NO_TRANSFORM_UNCERTAINTY"
    ):
        raise InterfaceSchemaError(
            "spacecraft_assembly_frame must remain the frozen identity alias of S"
        )
    semantics = _mapping(frame_tree.get("semantic_rulings"), "semantic_rulings")
    if semantics.get("unknown_transform_policy") != "null_transform_and_action_mask":
        raise InterfaceSchemaError("unknown M4 frame transforms must be null and action-masked")
    frames = _mapping(frame_tree.get("frames"), "frames")
    for frame_id in (
        "SENSOR_PACKAGE",
        "SPACECRAFT_LOAD_BRIDGE",
        "ARM_HDRM",
        "TARGET_SATELLITE_T",
        "TARGET_DEBRIS_D",
    ):
        record = _mapping(frames.get(frame_id), f"frames.{frame_id}")
        transform = record.get("T_S_child_rows")
        status = str(record.get("status"))
        if transform is not None or not (
            "HOLD" in status or "UNRESOLVED" in status
        ):
            raise InterfaceSchemaError(f"unresolved frame {frame_id} lost null/HOLD semantics")
    consumer_rules = tuple(
        str(item) for item in _sequence(frame_tree.get("consumer_rules"), "consumer_rules")
    )
    if not any("frame/axis witness" in rule for rule in consumer_rules):
        raise InterfaceSchemaError("frame tree must forbid B601 witness collision use")
    if not any(
        "spacecraft_assembly_frame and S as the same frame" in rule
        for rule in consumer_rules
    ):
        raise InterfaceSchemaError(
            "frame-tree consumer rules must preserve the spacecraft assembly alias"
        )

    collision = _load_mapping(artifacts["collision_asset_register"].path)
    if collision.get("schema") != "M4_DIGITAL_PROTOTYPE_COLLISION_ASSET_REGISTER_V1":
        raise InterfaceSchemaError("M4 collision-register schema changed")
    proxies = _mapping(collision.get("component_proxy_policy"), "component_proxy_policy")
    b601 = _mapping(proxies.get("INST_B601_ARM_CORE_Q0"), "B601 proxy policy")
    if b601.get("available") is not False:
        raise InterfaceSchemaError("B601 frame witness must not be an available collision proxy")
    prohibited = {str(item) for item in _sequence(b601.get("prohibited_use"), "B601 prohibited use")}
    if not {"broad_phase", "narrow_phase", "contact"}.issubset(prohibited):
        raise InterfaceSchemaError("B601 witness collision prohibitions are incomplete")
    action_rules = tuple(
        str(item)
        for item in _sequence(collision.get("action_mask_rules"), "action_mask_rules")
    )
    if not any("Mask capture/contact" in rule for rule in action_rules):
        raise InterfaceSchemaError("collision register must mask capture/contact")

    independent = _load_mapping(artifacts["geometry_independent_validation"].path)
    if independent.get("formal_FEA_performed") is not False:
        raise InterfaceSchemaError("Sim14 input may not imply formal FEA was performed")
    checks = _mapping(independent.get("checks"), "independent geometry checks")
    if not checks or not all(value is True for value in checks.values()):
        raise InterfaceSchemaError("independent geometry validation checks are not all true")
    verdict = str(independent.get("verdict"))
    if "PASS" not in verdict or "HOLDS" not in verdict:
        raise InterfaceSchemaError("independent geometry verdict must preserve release holds")


def _computed_missing_authorities(document: Mapping[str, Any]) -> tuple[str, ...]:
    props = _mapping(document.get("mechanical_properties"), "mechanical_properties")
    service = _mapping(props.get("service_spacecraft_system"), "service_spacecraft_system")
    target22 = _mapping(props.get("target_22kg_reference"), "target_22kg_reference")
    target150 = _mapping(props.get("target_150kg_reference"), "target_150kg_reference")
    contact = _mapping(document.get("contact"), "contact")
    kinematics = _mapping(document.get("kinematics"), "kinematics")
    collision = _mapping(document.get("collision"), "collision")
    configs = _mapping(document.get("configurations"), "configurations")
    checks = {
        "SERVICE_SYSTEM_MASS": service.get("mass_kg"),
        "SERVICE_SYSTEM_CENTER_OF_MASS": service.get("center_of_mass_m"),
        "SERVICE_SYSTEM_INERTIA": service.get("inertia_about_center_of_mass_kg_m2"),
        "TARGET_22KG_CONTROLLED_MASS": target22.get("mass_kg"),
        "TARGET_22KG_INERTIA": target22.get("inertia_about_center_of_mass_kg_m2"),
        "TARGET_150KG_CONTROLLED_MASS": target150.get("mass_kg"),
        "TARGET_150KG_INERTIA": target150.get("inertia_about_center_of_mass_kg_m2"),
        "NAMED_JOINT_VECTORS": kinematics.get("named_joint_vectors"),
        "ACTUATOR_TORQUE_LIMITS": kinematics.get("actuator_torque_limits_N_m"),
        "CONTACT_MODEL": contact.get("model"),
        "CONTACT_FRAMES": contact.get("contact_frames"),
        "GRIPPER_FORCE_LIMIT": contact.get("gripper_force_limit_N"),
        "CONTACT_FRICTION": contact.get("coefficient_of_friction"),
        "TARGET_PRESSURE_LIMIT": contact.get("target_contact_pressure_limit_Pa"),
        "CONTACT_RESTITUTION": contact.get("restitution_coefficient"),
    }
    missing = [name for name, value in checks.items() if value is None]
    if configs.get("complete_mass_count") != 9:
        missing.append("NINE_CONFIGURATION_MASS")
    if configs.get("complete_center_of_mass_count") != 9:
        missing.append("NINE_CONFIGURATION_CENTER_OF_MASS")
    if configs.get("complete_inertia_count") != 9:
        missing.append("NINE_CONFIGURATION_INERTIA")
    if collision.get("m4_component_collision_assets_complete") is not True:
        missing.append("M4_COMPONENT_COLLISION_ASSETS")
    if collision.get("narrow_phase_validated") is not True:
        missing.append("M4_NARROW_PHASE_VALIDATION")
    return tuple(missing)


def load_mechanical_interface(path: str | Path) -> MechanicalInterfaceBundle:
    manifest_path = Path(path).resolve()
    if manifest_path.name != "MECH_RL_INTERFACE_V2.yaml":
        raise InterfaceSchemaError("manifest must be named MECH_RL_INTERFACE_V2.yaml")
    if not manifest_path.is_file():
        raise InterfaceError(f"mechanical interface does not exist: {manifest_path}")
    document = _load_mapping(manifest_path)
    if document.get("schema_version") != INTERFACE_SCHEMA_VERSION:
        raise InterfaceSchemaError(
            f"schema_version must be {INTERFACE_SCHEMA_VERSION}"
        )
    _validate_units(document)
    raw_root = document.get("asset_root")
    if not isinstance(raw_root, str) or Path(raw_root).is_absolute():
        raise InterfaceSchemaError("asset_root must be a relative path")
    asset_root = (manifest_path.parent / raw_root).resolve()
    if not asset_root.is_dir():
        raise InterfaceError(f"asset_root does not exist: {asset_root}")
    raw_artifacts = _mapping(document.get("artifacts"), "artifacts")
    if set(raw_artifacts) != set(REQUIRED_ARTIFACT_IDS):
        raise InterfaceSchemaError(
            f"artifact IDs must be exactly {list(REQUIRED_ARTIFACT_IDS)}"
        )
    artifacts = {
        name: _load_artifact(name, raw_artifacts[name], asset_root)
        for name in REQUIRED_ARTIFACT_IDS
    }
    raw_urdf_binding = _mapping(
        raw_artifacts["accepted_b601_urdf"], "artifacts.accepted_b601_urdf"
    )
    normalized_expected = raw_urdf_binding.get("lf_normalized_sha256")
    if not isinstance(normalized_expected, str) or not _SHA256_RE.fullmatch(normalized_expected):
        raise InterfaceSchemaError("accepted B601 URDF LF-normalized hash is missing")
    normalized_actual = _sha256_bytes(
        artifacts["accepted_b601_urdf"].path.read_bytes().replace(b"\r\n", b"\n")
    )
    if normalized_actual != normalized_expected.upper():
        raise ArtifactHashMismatch(
            "accepted_b601_urdf LF-normalized SHA-256 mismatch: "
            f"expected {normalized_expected.upper()}, got {normalized_actual}"
        )
    configurations = _mapping(document.get("configurations"), "configurations")
    required_ids = tuple(
        str(item) for item in _sequence(
            configurations.get("required_ids"), "configurations.required_ids"
        )
    )
    if required_ids != REQUIRED_CONFIGURATION_IDS:
        raise InterfaceSchemaError(
            "configuration IDs or order differ from the M4 nine-configuration contract"
        )
    if configurations.get("required_count") != 9:
        raise InterfaceSchemaError("configurations.required_count must be 9")
    if (
        configurations.get("system_reference_frame")
        != "spacecraft_assembly_frame"
        or configurations.get("system_reference_frame_identity_alias") != "S"
        or configurations.get("required_inertia_reference_point")
        != "configuration_system_CG"
    ):
        raise InterfaceSchemaError(
            "interface configuration frame/reference-point contract changed"
        )
    configuration_release_counts = _validate_configuration_library(
        artifacts["configuration_library"].path,
        required_ids,
        configurations,
    )
    ledger_quality = _validate_system_mass_ledger(
        artifacts["system_mass_properties"].path
    )
    if (
        ledger_quality["numeric_mass_diagnostic_available"]
        != configurations.get("numeric_mass_diagnostic_available_count")
        or ledger_quality["full_mass_properties_loader_ready"]
        != configurations.get("full_mass_properties_loader_ready_count")
    ):
        raise InterfaceSchemaError(
            "configuration and system mass diagnostic readiness counts disagree"
        )
    quality_contract = _mapping(
        document.get("mass_property_quality_contract"),
        "mass_property_quality_contract",
    )
    if tuple(quality_contract.get("required_uncertainty_inputs_per_quantity", ())) != (
        "estimate",
        "standard_uncertainty",
        "distribution",
        "degrees_of_freedom",
        "source",
    ):
        raise InterfaceSchemaError("interface uncertainty input contract changed")
    expected_quality = {
        "source_token": "component_source_ref",
        "source_resolution": "component_records.<component_id>.source_ref",
        "cg_and_inertia_uncertainty_subrecord_count": 14,
        "null_distribution_count": 14,
        "null_degrees_of_freedom_count": 14,
        "resolved_component_source_count": 14,
        "zero_fill_forbidden": True,
    }
    for key, expected in expected_quality.items():
        if quality_contract.get(key) != expected:
            raise InterfaceSchemaError(
                f"mass_property_quality_contract.{key} must be {expected}"
            )
    if ledger_quality["uncertainty_subrecords"] != 14:
        raise InterfaceSchemaError("full M4 uncertainty subrecord closure is incomplete")
    closure_audited_artifact_count = (
        _validate_mass_material_tolerance_mechanism_audit(artifacts)
    )
    _validate_geometry_safety_documents(artifacts)
    properties = _mapping(document.get("mechanical_properties"), "mechanical_properties")
    b601 = _mapping(properties.get("b601"), "mechanical_properties.b601")
    _validate_b601_urdf(
        artifacts["accepted_b601_urdf"].path, b601.get("mass_kg")
    )
    safety = _mapping(document.get("safety_contract"), "safety_contract")
    required_safety = {
        "unknown_is_action_masked": True,
        "abort_always_available": True,
        "direct_joint_torque_output_forbidden": True,
        "mesh_mass_inference_forbidden": True,
        "unknown_uncertainty_zero_fill_forbidden": True,
    }
    for key, expected in required_safety.items():
        if safety.get(key) is not expected:
            raise InterfaceSchemaError(f"safety_contract.{key} must be {expected}")
    authority = _mapping(document.get("execution_authority"), "execution_authority")
    declared_ready = authority.get("production_dynamics_ready")
    if not isinstance(declared_ready, bool):
        raise InterfaceSchemaError("production_dynamics_ready must be boolean")
    blockers = tuple(
        str(item)
        for item in _sequence(authority.get("blockers"), "execution_authority.blockers")
    )
    missing = _computed_missing_authorities(document)
    unresolved = tuple(
        name
        for name, binding in artifacts.items()
        if binding.binding_required and not binding.resolved
    )
    if declared_ready and (blockers or missing or unresolved):
        raise InterfaceSchemaError(
            "production_dynamics_ready cannot be true while authorities are unresolved"
        )
    if declared_ready and ledger_quality["full_mass_properties_loader_ready"] != 9:
        raise InterfaceSchemaError(
            "production dynamics cannot be ready without nine full mass-property loaders"
        )
    return MechanicalInterfaceBundle(
        manifest_path=manifest_path,
        manifest_sha256=sha256_file(manifest_path),
        asset_root=asset_root,
        artifacts=artifacts,
        required_configurations=required_ids,
        declared_production_ready=declared_ready,
        blocker_codes=blockers,
        computed_missing_authorities=missing,
        configuration_release_counts=configuration_release_counts,
        numeric_mass_diagnostic_available_count=ledger_quality[
            "numeric_mass_diagnostic_available"
        ],
        full_mass_properties_loader_ready_count=ledger_quality[
            "full_mass_properties_loader_ready"
        ],
        closure_audited_artifact_count=closure_audited_artifact_count,
        document=document,
    )


def _diagnostic_body(value: Any, label: str) -> DiagnosticRigidBody:
    record = _mapping(value, label)
    evidence = record.get("evidence_class")
    if not isinstance(evidence, str) or "DIAGNOSTIC" not in evidence:
        raise InterfaceSchemaError(f"{label}.evidence_class must identify DIAGNOSTIC scope")
    inertia = _positive_definite_matrix3(
        record.get("inertia_about_com_kg_m2"), f"{label}.inertia"
    )
    return DiagnosticRigidBody(
        mass_kg=_positive(record.get("mass_kg"), f"{label}.mass_kg"),
        inertia_about_com_kg_m2=inertia,
        initial_position_m=_finite_vector(
            record.get("initial_position_m"), 3, f"{label}.initial_position_m"
        ),
        initial_linear_velocity_mps=_finite_vector(
            record.get("initial_linear_velocity_mps"),
            3,
            f"{label}.initial_linear_velocity_mps",
        ),
        initial_angular_velocity_radps=_finite_vector(
            record.get("initial_angular_velocity_radps"),
            3,
            f"{label}.initial_angular_velocity_radps",
        ),
        evidence_class=evidence,
    )


def load_diagnostic_fixture(
    path: str | Path,
    *,
    acknowledgement: str | None,
) -> DiagnosticFixture:
    if acknowledgement != DIAGNOSTIC_ACKNOWLEDGEMENT:
        raise DiagnosticAuthorizationError(
            "diagnostic mechanics require the exact non-authority acknowledgement"
        )
    fixture_path = Path(path).resolve()
    if not fixture_path.is_file():
        raise InterfaceError(f"diagnostic fixture does not exist: {fixture_path}")
    document = _load_mapping(fixture_path)
    if document.get("schema_version") != DIAGNOSTIC_SCHEMA_VERSION:
        raise InterfaceSchemaError(
            f"diagnostic schema must be {DIAGNOSTIC_SCHEMA_VERSION}"
        )
    if document.get("explicit_acknowledgement") != DIAGNOSTIC_ACKNOWLEDGEMENT:
        raise InterfaceSchemaError("diagnostic fixture acknowledgement changed")
    scope = document.get("scope")
    if not isinstance(scope, str) or "NOT_ENGINEERING_PREDICTION" not in scope:
        raise InterfaceSchemaError("diagnostic scope must forbid engineering prediction")
    units = _mapping(document.get("units"), "diagnostic units")
    expected_units = {
        "length": "m",
        "mass": "kg",
        "inertia": "kg*m^2",
        "linear_velocity": "m/s",
        "angular_velocity": "rad/s",
    }
    if dict(units) != expected_units:
        raise InterfaceSchemaError(f"diagnostic units must be exactly {expected_units}")
    uncertainty = _mapping(document.get("uncertainty_policy"), "uncertainty_policy")
    if uncertainty.get("standard_uncertainty") is not None:
        raise InterfaceSchemaError("diagnostic fixture may not invent an uncertainty")
    if uncertainty.get("zero_fill_forbidden") is not True:
        raise InterfaceSchemaError("diagnostic uncertainty zero fill must be forbidden")
    service = _diagnostic_body(
        document.get("service_spacecraft_fixture"), "service_spacecraft_fixture"
    )
    raw_anchors = _mapping(document.get("anchors"), "anchors")
    expected_anchor_ids = {"ANCHOR_22KG_0P5DPS", "ANCHOR_150KG_3DPS"}
    if set(raw_anchors) != expected_anchor_ids:
        raise InterfaceSchemaError(f"diagnostic anchors must be {expected_anchor_ids}")
    anchors: dict[str, DiagnosticAnchor] = {}
    for anchor_id, raw in raw_anchors.items():
        record = _mapping(raw, f"anchors.{anchor_id}")
        target_kind = record.get("target_kind")
        if not isinstance(target_kind, str) or not target_kind:
            raise InterfaceSchemaError(f"anchors.{anchor_id}.target_kind is invalid")
        anchors[str(anchor_id)] = DiagnosticAnchor(
            anchor_id=str(anchor_id),
            target_kind=target_kind,
            body=_diagnostic_body(record, f"anchors.{anchor_id}"),
        )
    return DiagnosticFixture(
        path=fixture_path,
        sha256=sha256_file(fixture_path),
        scope=scope,
        service_spacecraft=service,
        anchors=anchors,
    )


def validate_diagnostic_fixture_against_m4(
    interface: MechanicalInterfaceBundle,
    fixture: DiagnosticFixture,
) -> None:
    """Prove diagnostic numbers match the bound M4 non-release branches."""
    ledger = _load_mapping(interface.artifacts["system_mass_properties"].path)
    branches = _mapping(
        ledger.get("diagnostic_nonrelease_branches"),
        "diagnostic_nonrelease_branches",
    )
    branch_b = _mapping(
        branches.get("branch_B_bus_minus_legacy_flange_plus_m3r_plus_b601"),
        "branch_B_bus_minus_legacy_flange_plus_m3r_plus_b601",
    )
    branch_mass = _positive(
        branch_b.get("nominal_mass_sum_kg"), "branch B nominal mass"
    )
    if not math.isclose(
        fixture.service_spacecraft.mass_kg,
        branch_mass,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise InterfaceSchemaError("diagnostic service mass drifted from M4 Branch B")
    members = _sequence(branch_b.get("members"), "branch B members")
    if not any("m3r" in str(item).lower() for item in members):
        raise InterfaceSchemaError("M4 diagnostic Branch B must include M3R")
    if "PROVISIONAL" not in str(branch_b.get("status")):
        raise InterfaceSchemaError("M4 diagnostic Branch B must remain provisional")
    components = _mapping(ledger.get("component_records"), "component_records")
    scenario_map = {
        "ANCHOR_22KG_0P5DPS": "target_22kg_scenario",
        "ANCHOR_150KG_3DPS": "target_150kg_scenario",
    }
    configuration_document = _load_mapping(
        interface.artifacts["configuration_library"].path
    )
    configuration_by_name = {
        str(_mapping(raw, "configuration").get("name")): _mapping(
            raw, "configuration"
        )
        for raw in _sequence(
            configuration_document.get("configurations"), "configurations"
        )
    }
    capture_configuration_map = {
        "ANCHOR_22KG_0P5DPS": "TARGET_CAPTURE_22KG",
        "ANCHOR_150KG_3DPS": "TARGET_CAPTURE_150KG",
    }
    for anchor_id, component_id in scenario_map.items():
        component = _mapping(components.get(component_id), component_id)
        mass = _mapping(component.get("mass"), f"{component_id}.mass")
        inertia = _mapping(
            component.get("inertia_about_own_com"),
            f"{component_id}.inertia_about_own_com",
        )
        expected_mass = _positive(mass.get("estimate_kg"), f"{component_id}.mass")
        expected_inertia = _positive_definite_matrix3(
            inertia.get("matrix_kg_m2"), f"{component_id}.inertia"
        )
        body = fixture.anchors[anchor_id].body
        if not math.isclose(body.mass_kg, expected_mass, rel_tol=0.0, abs_tol=1e-12):
            raise InterfaceSchemaError(f"{anchor_id} diagnostic mass drifted from M4")
        capture_record = _mapping(
            configuration_by_name.get(capture_configuration_map[anchor_id]),
            capture_configuration_map[anchor_id],
        )
        capture_mass = _mapping(capture_record.get("mass"), "capture mass")
        if capture_mass.get("released_value_kg") is not None:
            raise InterfaceSchemaError("diagnostic capture configuration became released")
        branches_record = _mapping(
            capture_mass.get("diagnostic_branches"), "capture diagnostic branches"
        )
        expected_combined_mass = _positive(
            branches_record.get("m3r_B_value_kg"), "capture Branch B mass"
        )
        if not math.isclose(
            fixture.service_spacecraft.mass_kg + body.mass_kg,
            expected_combined_mass,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise InterfaceSchemaError(
                f"{anchor_id} total mass drifted from M4 capture Branch B"
            )
        for i in range(3):
            for j in range(3):
                if not math.isclose(
                    body.inertia_about_com_kg_m2[i][j],
                    expected_inertia[i][j],
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    raise InterfaceSchemaError(
                        f"{anchor_id} diagnostic inertia drifted from M4"
                    )


__all__ = [
    "ArtifactBinding",
    "ArtifactHashMismatch",
    "DIAGNOSTIC_ACKNOWLEDGEMENT",
    "DiagnosticAnchor",
    "DiagnosticAuthorizationError",
    "DiagnosticFixture",
    "DiagnosticRigidBody",
    "InterfaceError",
    "InterfaceSchemaError",
    "MechanicalInterfaceBundle",
    "REQUIRED_CONFIGURATION_IDS",
    "load_diagnostic_fixture",
    "load_mechanical_interface",
    "sha256_file",
    "validate_diagnostic_fixture_against_m4",
]
