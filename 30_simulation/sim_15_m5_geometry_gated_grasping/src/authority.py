"""Hash-bound loader for the M5-to-Sim15 diagnostic authority bundle.

The loader intentionally performs more than schema parsing.  It verifies every
artifact hash declared by ``MECH_DYNAMICS_INTERFACE_V3``, the frozen-input
manifest, and the geometry assets referenced by the M5 decision records.  It
also proves that physical contact, formal structural analysis, and production
dynamics remain closed before returning a bundle.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


INTERFACE_SCHEMA = "MECH_DYNAMICS_INTERFACE_V3"
ACKNOWLEDGEMENT = (
    "I_ACKNOWLEDGE_M5_VALUES_ARE_DIAGNOSTIC_NOT_PHYSICAL_CONTACT_OR_FLIGHT_AUTHORITY"
)
EXPECTED_CONFIGURATION_IDS = tuple(f"C{index:02d}" for index in range(1, 10))
EXPECTED_ARTIFACT_IDS = (
    "accepted_b601_urdf",
    "frozen_input_manifest",
    "mesh_frame_decision",
    "configuration_contract",
    "broadphase_audit",
    "load_authority_migration",
    "joint_load_model",
    "contact_parameter_contract",
    "structural_entry_gate",
    "sim14_fixture",
    "m4_mass_properties",
    "target_models",
    "solar_r2b_static_oracle",
)
EXPECTED_UNITS = {
    "length": "m",
    "angle": "rad",
    "mass": "kg",
    "inertia": "kg*m^2",
    "force": "N",
    "moment": "N*m",
    "impulse": "N*s",
    "couple_impulse": "N*m*s",
}
_SHA256_RE = re.compile(r"[0-9A-Fa-f]{64}")


class AuthorityError(RuntimeError):
    """Base error for a missing, malformed, or unsafe authority record."""


class ArtifactHashMismatch(AuthorityError):
    """Raised when a source no longer matches its declared SHA-256."""


@dataclass(frozen=True)
class ArtifactBinding:
    artifact_id: str
    path: Path
    expected_sha256: str
    actual_sha256: str
    required: bool

    @property
    def resolved(self) -> bool:
        return self.expected_sha256 == self.actual_sha256


@dataclass(frozen=True)
class AuthorityBundle:
    interface_path: Path
    interface_sha256: str
    project_root: Path
    m5_root: Path
    document: Mapping[str, Any]
    artifacts: Mapping[str, ArtifactBinding]
    frozen_input_manifest: Mapping[str, Any]
    mesh_frame_decision: Mapping[str, Any]
    configuration_contract: Mapping[str, Any]
    broadphase_audit: Mapping[str, Any]
    load_authority: Mapping[str, Any]
    joint_load_model: Mapping[str, Any]
    contact_contract: Mapping[str, Any]
    structural_gate: Mapping[str, Any]
    diagnostic_fixture: Mapping[str, Any]
    release_gate: Mapping[str, Any]
    nested_hash_verification_count: int
    frozen_input_verification_count: int
    physical_contact_ready: bool
    production_ready: bool
    physical_contact_hold_reasons: tuple[str, ...]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AuthorityError(f"{label} must be a mapping")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AuthorityError(f"{label} must be a list")
    return value


def _load_mapping(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise AuthorityError(f"authority file is missing: {path}")
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
        value = json.loads(text) if suffix == ".json" else yaml.safe_load(text)
    except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise AuthorityError(f"cannot parse authority file {path}: {exc}") from exc
    return _mapping(value, str(path))


def _find_project_root(interface_path: Path) -> Path:
    for candidate in (interface_path.parent, *interface_path.parents):
        if (candidate / "20_engineering").is_dir() and (
            candidate / "30_simulation"
        ).is_dir():
            return candidate.resolve()
    raise AuthorityError("cannot locate project root above the M5 interface")


def _safe_project_file(project_root: Path, raw_path: Any, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise AuthorityError(f"{label}.path must be a non-empty string")
    relative = Path(raw_path)
    if relative.is_absolute():
        raise AuthorityError(f"{label}.path must be project-root relative")
    resolved = (project_root / relative).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise AuthorityError(f"{label}.path escapes the project root") from exc
    if not resolved.is_file():
        raise AuthorityError(f"{label}.path is missing: {resolved}")
    return resolved


def _expected_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise AuthorityError(f"{label}.sha256 must be 64 hexadecimal characters")
    return value.upper()


def _verify_hash_record(
    project_root: Path,
    record: Mapping[str, Any],
    label: str,
) -> Path:
    path = _safe_project_file(project_root, record.get("path"), label)
    expected = _expected_hash(record.get("sha256"), label)
    actual = sha256_file(path)
    if actual != expected:
        raise ArtifactHashMismatch(
            f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    declared_bytes = record.get("bytes")
    if declared_bytes is not None and declared_bytes != path.stat().st_size:
        raise AuthorityError(
            f"{label} byte count mismatch: expected {declared_bytes}, "
            f"got {path.stat().st_size}"
        )
    return path


def _verify_frozen_manifest(
    manifest: Mapping[str, Any], project_root: Path
) -> int:
    if manifest.get("schema") != "M5_FROZEN_INPUT_MANIFEST_V1":
        raise AuthorityError("unexpected M5 frozen-input manifest schema")
    records = _sequence(manifest.get("records"), "frozen_input_manifest.records")
    if manifest.get("record_count") != len(records) or not records:
        raise AuthorityError("frozen-input record count is inconsistent")
    if manifest.get("status") != "PASS_ALL_INPUTS_PRESENT_AND_HASH_BOUND":
        raise AuthorityError("frozen-input manifest does not carry its PASS status")
    for index, raw in enumerate(records):
        _verify_hash_record(
            project_root,
            _mapping(raw, f"frozen_input_manifest.records[{index}]"),
            f"frozen_input_manifest.records[{index}]",
        )
    return len(records)


def _verify_mesh_assets(
    decision: Mapping[str, Any], project_root: Path
) -> int:
    if decision.get("schema") != "M5_B601_CAD_MESH_FRAME_DECISION_V1":
        raise AuthorityError("unexpected B601 mesh-frame decision schema")
    if decision.get("all_components_below_0p1mm") is not True:
        raise AuthorityError("mesh-frame registration gate is not passed")
    if decision.get("physical_clearance_or_metrology_claim") is not False:
        raise AuthorityError("mesh decision improperly claims physical clearance")
    if decision.get("status") != "PASS_SOURCE_BOUND_LINK_LOCALIZATION_FOR_DIGITAL_GEOMETRY":
        raise AuthorityError("mesh localization is not the scoped digital PASS")

    verified = 0
    components = _mapping(decision.get("components"), "mesh decision components")
    physical_links = tuple(name for name in components if name != "legacy_gripper_detail")
    if physical_links != ("base_link", "link1", "link2", "link3", "link4", "link5", "link6"):
        raise AuthorityError("unexpected B601 link-local component set")
    for name in physical_links:
        record = _mapping(components[name], f"components.{name}")
        registration = _mapping(
            record.get("independent_q0_to_stow_registration"),
            f"components.{name}.registration",
        )
        if registration.get("pass") is not True:
            raise AuthorityError(f"{name} inverse-localization registration failed")
        for key in ("local_surface", "conservative_broadphase_box"):
            asset = _mapping(record.get(key), f"components.{name}.{key}")
            if asset.get("units") != "m":
                raise AuthorityError(f"components.{name}.{key} is not in metres")
            _verify_hash_record(project_root, asset, f"components.{name}.{key}")
            verified += 1

    gripper = _mapping(decision.get("active_gripper_r1"), "active_gripper_r1")
    for name in ("palm", "left_finger", "right_finger"):
        record = _mapping(gripper.get(name), f"active_gripper_r1.{name}")
        for key in ("local_surface", "broadphase_box"):
            asset = _mapping(record.get(key), f"active_gripper_r1.{name}.{key}")
            if asset.get("units") != "m":
                raise AuthorityError(f"active_gripper_r1.{name}.{key} is not SI")
            _verify_hash_record(project_root, asset, f"active_gripper_r1.{name}.{key}")
            verified += 1
    motion = _mapping(gripper.get("motion_contract"), "active_gripper_r1.motion_contract")
    registration = _mapping(
        motion.get("frame_registration"),
        "active_gripper_r1.motion_contract.frame_registration",
    )
    if motion.get("corrected_frame_binding") != "gripper_link":
        raise AuthorityError("R1 gripper must bind to accepted URDF gripper_link")
    if registration.get("accepted_binding") != "gripper_link":
        raise AuthorityError("gripper frame registration accepted a different binding")
    if registration.get("gripper_link_registration_pass") is not True:
        raise AuthorityError("gripper_link absolute q0 registration did not pass")
    if registration.get("direct_link6_binding_rejected") is not True:
        raise AuthorityError("unsafe direct link6 gripper binding was not rejected")
    if float(registration.get("gripper_link_bbox_endpoint_max_abs_error_mm", math.inf)) > 0.001:
        raise AuthorityError("gripper_link q0 registration exceeds 0.001 mm")
    if float(registration.get("direct_link6_bbox_endpoint_max_abs_error_mm", -math.inf)) <= 100.0:
        raise AuthorityError("direct link6 rejection lacks the expected >100 mm separation")
    if motion.get("configuration_travel_authority") is not None:
        raise AuthorityError("gripper configuration travel authority must remain null/HOLD")
    return verified


def _verify_configuration_contract(
    contract: Mapping[str, Any], project_root: Path
) -> int:
    if contract.get("schema") != "M5_CONFIGURATION_GEOMETRY_CONTRACT_V1":
        raise AuthorityError("unexpected configuration geometry contract schema")
    if tuple(contract.get("required_ids", ())) != EXPECTED_CONFIGURATION_IDS:
        raise AuthorityError("M5 configuration identifiers changed")
    records = _sequence(contract.get("records"), "configuration_contract.records")
    if len(records) != 9 or contract.get("configuration_count") != 9:
        raise AuthorityError("M5 configuration count must remain exactly nine")
    if tuple(record.get("configuration_id") for record in records) != EXPECTED_CONFIGURATION_IDS:
        raise AuthorityError("M5 configuration order or identifiers changed")
    for index, raw in enumerate(records):
        record = _mapping(raw, f"configuration_contract.records[{index}]")
        if record.get("diagnostic_only") is not True:
            raise AuthorityError("all M5 snapshots must remain diagnostic-only")
        if record.get("contact_enabled") is not False:
            raise AuthorityError("M5 configuration may not enable physical contact")
        if record.get("mass_properties_authority") is not False:
            raise AuthorityError("M5 configuration may not claim mass-property authority")
        if record.get("finger_travel_configuration_authority") is not False:
            raise AuthorityError("M5 configuration may not claim finger-travel authority")
        if record.get("required_capture_gripper_travel_m") is not None:
            raise AuthorityError("required capture travel must remain null until ratified")
        for key in ("released_mass_kg", "released_cg_S_m", "released_inertia_S_kg_m2"):
            if record.get(key) is not None:
                raise AuthorityError(f"{record['configuration_id']}.{key} must remain null")
        snapshot = _mapping(record.get("snapshot"), f"{record['configuration_id']}.snapshot")
        _verify_hash_record(project_root, snapshot, f"{record['configuration_id']}.snapshot")
    if any(contract.get(key) != 0 for key in (
        "released_mass_count",
        "released_cg_count",
        "released_inertia_count",
        "verified_system_collision_count",
        "contact_enabled_count",
    )):
        raise AuthorityError("M5 physical release counts must remain zero")
    return len(records)


def _verify_fail_closed_documents(
    document: Mapping[str, Any],
    broadphase: Mapping[str, Any],
    load_authority: Mapping[str, Any],
    contact: Mapping[str, Any],
    structural: Mapping[str, Any],
    release_gate: Mapping[str, Any],
) -> tuple[bool, bool, tuple[str, ...]]:
    reasons: list[str] = []
    runtime = _mapping(document.get("runtime_gates"), "runtime_gates")
    geometry = _mapping(document.get("geometry_capabilities"), "geometry_capabilities")
    loads = _mapping(document.get("loads_capabilities"), "loads_capabilities")
    if runtime.get("geometry_diagnostic") != "PASS":
        raise AuthorityError("geometry diagnostic gate is not PASS")
    if geometry.get("narrow_phase_verified") is not True:
        reasons.append("NARROW_PHASE_NOT_VERIFIED")
    if geometry.get("contact_geometry_authorized") is not True:
        reasons.append("CONTACT_GEOMETRY_NOT_AUTHORIZED")
    if broadphase.get("narrow_phase_available") is not True:
        reasons.append("NARROW_PHASE_UNAVAILABLE")
    if broadphase.get("system_collision_release") is not True:
        reasons.append("SYSTEM_COLLISION_NOT_RELEASED")
    if runtime.get("physical_contact") != "PASS":
        reasons.append("INTERFACE_PHYSICAL_CONTACT_GATE_HOLD")
    if contact.get("physical_contact_kernel_authorized") is not True:
        reasons.append("PHYSICAL_CONTACT_KERNEL_NOT_AUTHORIZED")
    if contact.get("computed_contact_force_N") is not None:
        raise AuthorityError("contact contract contains an unauthorized computed force")
    if contact.get("computed_contact_pressure_Pa") is not None:
        raise AuthorityError("contact contract contains an unauthorized pressure")
    if load_authority.get("formal_loads_authorized") is not False:
        raise AuthorityError("M5 load migration unexpectedly authorizes physical loads")
    gap_closure = _mapping(load_authority.get("gap_closure"), "gap_closure")
    if gap_closure.get("LG-019_capture_impulse_reproducibility") != (
        "PENDING_SIM15_HASH_BOUND_RERUN"
    ):
        raise AuthorityError("M5 must leave LG-019 pending for Sim15 to close locally")
    replacement = _mapping(
        load_authority.get("replacement_boundary_contract"),
        "replacement_boundary_contract",
    )
    for key in (
        "T_M_DYNAMICS_FROM_SPACECRAFT_LOAD_BRIDGE_MATING_DATUM",
        "stiffness_6x6",
        "fastener_preload_N",
        "friction_coefficient",
    ):
        if replacement.get(key) is not None:
            raise AuthorityError(f"replacement boundary {key} must remain null/HOLD")
    if structural.get("gate_status") != "HOLD":
        raise AuthorityError("structural gate must remain HOLD")
    if structural.get("pass_token_issued") is not False:
        raise AuthorityError("structural PASS token was unexpectedly issued")
    if structural.get("formal_fea_authorized") is not False:
        raise AuthorityError("formal FEA was unexpectedly authorized")
    if structural.get("formal_fea_run_count") != 0:
        raise AuthorityError("formal FEA run count must remain zero")
    if loads.get("contact_force_time_history") is not False:
        raise AuthorityError("interface improperly claims a contact force history")
    if loads.get("physical_load_authority") is not False:
        raise AuthorityError("interface improperly claims physical load authority")
    if release_gate.get("physical_contact_parameters_ready") is not False:
        raise AuthorityError("M5 release gate unexpectedly claims contact readiness")
    if release_gate.get("structural_analysis_ready") is not False:
        raise AuthorityError("M5 release gate unexpectedly claims structural readiness")
    if release_gate.get("physics_gated_contact_rl_ready") is not False:
        raise AuthorityError("M5 release gate unexpectedly claims RL readiness")
    physical_ready = not reasons
    production_ready = (
        physical_ready
        and runtime.get("structural_analysis") == "PASS"
        and runtime.get("physics_gated_RL") == "PASS"
    )
    return physical_ready, production_ready, tuple(dict.fromkeys(reasons))


def _validate_joint_model(model: Mapping[str, Any]) -> None:
    if model.get("schema") != "M5_ANALYTIC_JOINT_LOAD_MODEL_V1":
        raise AuthorityError("unexpected analytic joint-load schema")
    units = _mapping(model.get("units"), "joint model units")
    expected = {"force": "N", "moment": "N*m", "coordinate": "m", "influence_moment_terms": "1/m"}
    if dict(units) != expected:
        raise AuthorityError("joint-load model units changed")
    if model.get("allowed_use") != "GEOMETRIC_WRENCH_DISTRIBUTION_SENSITIVITY_AND_SOFTWARE_VERIFICATION":
        raise AuthorityError("joint-load model allowed scope changed")
    uncertainty = _mapping(model.get("uncertainty"), "joint model uncertainty")
    if any(uncertainty.get(key) is not None for key in (
        "coordinate_standard_uncertainty_m", "distribution", "degrees_of_freedom"
    )):
        raise AuthorityError("joint geometry uncertainty may not be silently invented")


def _validate_fixture(fixture: Mapping[str, Any]) -> None:
    if fixture.get("schema_version") != "SIM14_DIAGNOSTIC_FIXTURE_V1":
        raise AuthorityError("unexpected diagnostic fixture schema")
    scope = str(fixture.get("scope", ""))
    if "NOT_ENGINEERING_PREDICTION" not in scope:
        raise AuthorityError("fixture must remain explicitly non-predictive")
    units = _mapping(fixture.get("units"), "diagnostic fixture units")
    expected = {
        "length": "m",
        "mass": "kg",
        "inertia": "kg*m^2",
        "linear_velocity": "m/s",
        "angular_velocity": "rad/s",
    }
    if dict(units) != expected:
        raise AuthorityError("diagnostic fixture is not strictly SI")
    uncertainty = _mapping(fixture.get("uncertainty_policy"), "uncertainty_policy")
    if uncertainty.get("standard_uncertainty") is not None:
        raise AuthorityError("diagnostic fixture may not invent uncertainty")
    if uncertainty.get("zero_fill_forbidden") is not True:
        raise AuthorityError("diagnostic fixture must forbid zero fill")


def _validate_release_gate(
    release_gate: Mapping[str, Any],
    interface_path: Path,
    interface_sha256: str,
) -> None:
    if release_gate.get("schema") != "M5_GEOMETRY_AND_LOADS_CLOSURE_GATE_V1":
        raise AuthorityError("unexpected M5 release-gate schema")
    critical = _mapping(release_gate.get("critical_evidence"), "critical_evidence")
    interface_record = _mapping(critical.get("interface"), "critical_evidence.interface")
    if _expected_hash(interface_record.get("sha256"), "critical_evidence.interface") != interface_sha256:
        raise ArtifactHashMismatch("M5 release gate does not bind the current interface")
    if Path(str(interface_record.get("path"))).as_posix() != interface_path.as_posix().split(
        "/China Graduate Future Flight Vehicle Innovation Competition/"
    )[-1]:
        # The hash is decisive; this check is deliberately tolerant of drive/path spelling.
        if not interface_path.as_posix().endswith(Path(str(interface_record.get("path"))).as_posix()):
            raise AuthorityError("M5 release gate points to a different interface path")
    if release_gate.get("next_stage_authorized") is not True:
        raise AuthorityError("M5 does not authorize the scoped Sim15 software stage")
    if release_gate.get("next_stage_scope") != (
        "SIM15_HASH_BOUND_DIAGNOSTIC_CAPTURE_IMPULSE_AND_JOINT_LOAD_SOFTWARE_ONLY"
    ):
        raise AuthorityError("M5 next-stage scope is not the bounded Sim15 scope")
    if release_gate.get("memory_gate_passed") is not False:
        raise AuthorityError("historical 6 GiB memory gate must not be relabelled PASS")
    if release_gate.get("owner_override_used") is not True:
        raise AuthorityError("bounded low-memory route lacks its Owner Override record")
    if release_gate.get("formal_fea_run_count") != 0:
        raise AuthorityError("M5 formal FEA count must remain zero")
    if release_gate.get("diagnostic_reproducibility_gap_closed_count") != 0:
        raise AuthorityError("M5 must not pre-claim Sim15 diagnostic reproducibility closure")


def load_authority(interface_path: str | Path) -> AuthorityBundle:
    """Load and verify the complete M5 diagnostic authority chain.

    The function never promotes a diagnostic value.  A returned bundle may be
    used for hash/schema validation, rigid plastic-capture impulse diagnostics,
    and analytic joint-load distribution only.
    """

    interface = Path(interface_path).resolve()
    document = _load_mapping(interface)
    if document.get("schema") != INTERFACE_SCHEMA:
        raise AuthorityError(f"interface schema must be {INTERFACE_SCHEMA}")
    if dict(_mapping(document.get("units"), "interface units")) != EXPECTED_UNITS:
        raise AuthorityError("MECH_DYNAMICS_INTERFACE_V3 unit contract changed")
    if document.get("required_acknowledgement") != ACKNOWLEDGEMENT:
        raise AuthorityError("diagnostic acknowledgement changed")
    if document.get("zero_fill_forbidden") is not True:
        raise AuthorityError("interface must forbid unknown-value zero fill")

    project_root = _find_project_root(interface)
    m5_root = interface.parent.parent.resolve()
    interface_sha = sha256_file(interface)
    raw_artifacts = _mapping(document.get("artifacts"), "artifacts")
    if tuple(raw_artifacts) != EXPECTED_ARTIFACT_IDS:
        raise AuthorityError("interface artifact identifiers or order changed")
    bindings: dict[str, ArtifactBinding] = {}
    for artifact_id in EXPECTED_ARTIFACT_IDS:
        record = _mapping(raw_artifacts[artifact_id], f"artifacts.{artifact_id}")
        if record.get("required") is not True:
            raise AuthorityError(f"artifacts.{artifact_id} must remain required")
        path = _safe_project_file(project_root, record.get("path"), f"artifacts.{artifact_id}")
        expected = _expected_hash(record.get("sha256"), f"artifacts.{artifact_id}")
        actual = sha256_file(path)
        if actual != expected:
            raise ArtifactHashMismatch(
                f"artifacts.{artifact_id} SHA-256 mismatch: expected {expected}, got {actual}"
            )
        bindings[artifact_id] = ArtifactBinding(
            artifact_id=artifact_id,
            path=path,
            expected_sha256=expected,
            actual_sha256=actual,
            required=True,
        )

    frozen = _load_mapping(bindings["frozen_input_manifest"].path)
    frozen_count = _verify_frozen_manifest(frozen, project_root)
    mesh = _load_mapping(bindings["mesh_frame_decision"].path)
    nested_count = _verify_mesh_assets(mesh, project_root)
    configurations = _load_mapping(bindings["configuration_contract"].path)
    nested_count += _verify_configuration_contract(configurations, project_root)
    broadphase = _load_mapping(bindings["broadphase_audit"].path)
    if broadphase.get("schema") != "M5_BROADPHASE_COLLISION_AUDIT_V1":
        raise AuthorityError("unexpected broadphase audit schema")
    load_migration = _load_mapping(bindings["load_authority_migration"].path)
    if load_migration.get("schema") != "M5_LOAD_AUTHORITY_MIGRATION_V1":
        raise AuthorityError("unexpected load-authority migration schema")
    joint_model = _load_mapping(bindings["joint_load_model"].path)
    _validate_joint_model(joint_model)
    contact = _load_mapping(bindings["contact_parameter_contract"].path)
    if contact.get("schema") != "M5_CONTACT_MODEL_PARAMETER_CONTRACT_V1":
        raise AuthorityError("unexpected contact-parameter schema")
    if contact.get("zero_fill_forbidden") is not True:
        raise AuthorityError("contact contract must forbid zero fill")
    structural = _load_mapping(bindings["structural_entry_gate"].path)
    fixture = _load_mapping(bindings["sim14_fixture"].path)
    _validate_fixture(fixture)
    release_path = m5_root / "12_release" / "M5_GEOMETRY_AND_LOADS_CLOSURE_GATE_V1.json"
    release_gate = _load_mapping(release_path)
    _validate_release_gate(release_gate, interface, interface_sha)
    physical_ready, production_ready, reasons = _verify_fail_closed_documents(
        document,
        broadphase,
        load_migration,
        contact,
        structural,
        release_gate,
    )
    if physical_ready or production_ready:
        raise AuthorityError(
            "this Sim15 revision is diagnostic-only and refuses a promoted physical/production bundle"
        )
    return AuthorityBundle(
        interface_path=interface,
        interface_sha256=interface_sha,
        project_root=project_root,
        m5_root=m5_root,
        document=document,
        artifacts=bindings,
        frozen_input_manifest=frozen,
        mesh_frame_decision=mesh,
        configuration_contract=configurations,
        broadphase_audit=broadphase,
        load_authority=load_migration,
        joint_load_model=joint_model,
        contact_contract=contact,
        structural_gate=structural,
        diagnostic_fixture=fixture,
        release_gate=release_gate,
        nested_hash_verification_count=nested_count,
        frozen_input_verification_count=frozen_count,
        physical_contact_ready=False,
        production_ready=False,
        physical_contact_hold_reasons=reasons,
    )


__all__ = [
    "ACKNOWLEDGEMENT",
    "ArtifactBinding",
    "ArtifactHashMismatch",
    "AuthorityBundle",
    "AuthorityError",
    "EXPECTED_ARTIFACT_IDS",
    "EXPECTED_CONFIGURATION_IDS",
    "INTERFACE_SCHEMA",
    "load_authority",
    "sha256_file",
]
