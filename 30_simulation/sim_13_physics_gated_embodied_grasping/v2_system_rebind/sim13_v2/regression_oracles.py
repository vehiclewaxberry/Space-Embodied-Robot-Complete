"""Historical regression oracles and an ideal Unified-R2 hard-lock limit.

The historical files are read as immutable byte snapshots and accepted only
when both byte count and SHA-256 match the embedded pins.  Their observations
remain historical anchors; they are not a current re-execution and do not grant
Unified-R2 dynamics, contact, or RL authority.

The current-model calculation combines mass properties already parsed by
``URDFTreeDynamics`` and evaluates only an instantaneous, perfectly plastic,
two-rigid-body hard lock.  It produces no contact force or time history.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .free_floating_dynamics import URDFTreeDynamics


HISTORICAL_ANCHOR_SCOPE = (
    "HASH_PINNED_HISTORICAL_STORAGE_RESOLUTION_ANCHORS_NOT_CURRENT_REEXECUTION_NOT_UNIFIED_R2_PASS"
)
HARD_LOCK_SCOPE = (
    "IDEAL_INSTANTANEOUS_TWO_RIGID_BODY_HARD_LOCK_MOMENTUM_LIMIT_"
    "NOT_CONTACT_FORCE_OR_TIME_HISTORY"
)
CURRENT_REEXECUTION_HOLD = "HOLD_INPUT_PATH_OR_HASH_DRIFT"
EXPLICIT_FIXTURE_NO_AUTHORITY = "EXPLICIT_FIXTURE_NO_AUTHORITY"
SOURCE_ONLY_SERVICE_AGGREGATE = "SOURCE_ONLY_UNIFIED_R2_IN_MEMORY_NOT_BOUND"


@dataclass(frozen=True)
class ArtifactPin:
    artifact_id: str
    relative_path: str
    bytes: int
    sha256: str
    optional: bool = False


HISTORICAL_ARTIFACT_PINS: tuple[ArtifactPin, ...] = (
    ArtifactPin(
        "sim05_base_attitude_csv",
        "30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv",
        69231,
        "D543FFF76F13F12C2A97F10D83C6D19A09CB8CF0AC4498832B1DBC5D93110C14",
    ),
    ArtifactPin(
        "sim06_capture_matrix_csv",
        "30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv",
        6431,
        "8CBAD84B8FF69FFCA6992CE29E95520BAE3C309260EC8C55083CBE62DFED5151",
    ),
    ArtifactPin(
        "sim10_gate_json",
        "30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json",
        5951,
        "4DBD8C91FF3455D5E5997A995AC385F02BBC1D2E379BBFE5C0563D41834DFC67",
    ),
    ArtifactPin(
        "e19_diagnostic_gate_json",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_DIAGNOSTIC_EVALUATION_GATE_V1.json",
        5425,
        "BEE6ED3D0DD7A73204536E2FFCF2840B5B066DB371DC15B40C98A128A230E439",
        optional=True,
    ),
)
_PIN_BY_ID = {pin.artifact_id: pin for pin in HISTORICAL_ARTIFACT_PINS}

SIM10_EXPECTED_THRESHOLD_REGISTRY_SHA256 = (
    "400BCEDCE5AF6AD5C4135E67F87BB524EE2FDAFB1C26AEAE07E495FF387B2873"
)
CURRENT_OBSERVED_THRESHOLD_REGISTRY_SHA256 = (
    "75AF082AB45A4029C753978686A41CF1DC49B72EE9418CF2E0F1127126D71C82"
)
THRESHOLD_REGISTRY_RELATIVE_PATH = (
    "30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml"
)

# These are the actual default paths encoded by the legacy modules after their
# ``..`` components are resolved from the current REORG04 namespace.  They are
# checked as paths only; the legacy modules themselves are never imported.
LEGACY_DEFAULT_INPUT_PATHS: Mapping[str, str] = {
    "sim05_b601_urdf_default": "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "common_rigid_body_mass_budget_default": (
        "docs/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv"
    ),
}


class RegressionOracleError(RuntimeError):
    """Raised when a supposedly frozen oracle cannot be trusted."""


@dataclass(frozen=True)
class ArtifactValidation:
    artifact_id: str
    relative_path: str
    optional: bool
    present: bool
    expected_bytes: int
    actual_bytes: int | None
    expected_sha256: str
    actual_sha256: str | None
    exact: bool
    status: str


@dataclass(frozen=True)
class HalfLastDigitCrosscheck:
    exact_value: float
    stored_text: str
    stored_value: float
    absolute_difference: float
    half_last_digit_tolerance: float
    within_tolerance: bool


@dataclass(frozen=True)
class ServiceRigidBodyAggregate:
    mass_kg: float
    com_root_m: np.ndarray
    inertia_about_com_root_kg_m2: np.ndarray
    physical_link_count: int
    authority_class: str = SOURCE_ONLY_SERVICE_AGGREGATE

    def __post_init__(self) -> None:
        if self.authority_class != SOURCE_ONLY_SERVICE_AGGREGATE:
            raise RegressionOracleError("service aggregate may not carry release authority")
        if not math.isfinite(self.mass_kg) or self.mass_kg <= 0.0:
            raise RegressionOracleError("service aggregate mass must be positive and finite")
        if isinstance(self.physical_link_count, bool) or self.physical_link_count < 1:
            raise RegressionOracleError("service aggregate must contain physical links")
        object.__setattr__(self, "com_root_m", _vector(self.com_root_m, 3, "service.com_root_m"))
        object.__setattr__(
            self,
            "inertia_about_com_root_kg_m2",
            _positive_definite_inertia(
                self.inertia_about_com_root_kg_m2,
                "service.inertia_about_com_root_kg_m2",
            ),
        )


@dataclass(frozen=True)
class ExplicitTargetFixture:
    fixture_id: str
    mass_kg: float
    com_root_m: np.ndarray
    inertia_about_com_root_kg_m2: np.ndarray
    linear_velocity_root_m_s: np.ndarray
    angular_velocity_root_rad_s: np.ndarray
    authority_class: str = EXPLICIT_FIXTURE_NO_AUTHORITY

    def __post_init__(self) -> None:
        if not self.fixture_id:
            raise RegressionOracleError("target fixture_id must be non-empty")
        if self.authority_class != EXPLICIT_FIXTURE_NO_AUTHORITY:
            raise RegressionOracleError("target fixtures may not carry authority")
        if not math.isfinite(self.mass_kg) or self.mass_kg <= 0.0:
            raise RegressionOracleError("target fixture mass must be positive and finite")
        com = _vector(self.com_root_m, 3, "target.com_root_m")
        inertia = _positive_definite_inertia(
            self.inertia_about_com_root_kg_m2, "target.inertia_about_com_root_kg_m2"
        )
        linear = _vector(self.linear_velocity_root_m_s, 3, "target.linear_velocity_root_m_s")
        angular = _vector(self.angular_velocity_root_rad_s, 3, "target.angular_velocity_root_rad_s")
        object.__setattr__(self, "com_root_m", com)
        object.__setattr__(self, "inertia_about_com_root_kg_m2", inertia)
        object.__setattr__(self, "linear_velocity_root_m_s", linear)
        object.__setattr__(self, "angular_velocity_root_rad_s", angular)


@dataclass(frozen=True)
class HardLockMomentumLimit:
    scope: str
    service_authority_class: str
    target_authority_class: str
    total_mass_kg: float
    combined_com_root_m: np.ndarray
    combined_linear_velocity_root_m_s: np.ndarray
    combined_inertia_about_com_root_kg_m2: np.ndarray
    combined_angular_velocity_root_rad_s: np.ndarray
    post_rate_dps: float
    linear_momentum_pre_kg_m_s: np.ndarray
    linear_momentum_post_kg_m_s: np.ndarray
    angular_momentum_pre_about_root_kg_m2_s: np.ndarray
    angular_momentum_post_about_root_kg_m2_s: np.ndarray
    linear_momentum_relative_residual: float
    angular_momentum_relative_residual: float
    kinetic_energy_pre_j: float
    kinetic_energy_post_j: float
    plastic_energy_loss_j: float
    plastic_energy_nonincrease: bool
    contact_force_available: bool = False
    contact_time_history_available: bool = False


def project_root_from_module() -> Path:
    return Path(__file__).resolve().parents[4]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def validate_artifact_payload(pin: ArtifactPin, payload: bytes | None) -> ArtifactValidation:
    """Validate one byte snapshot without touching the filesystem."""

    if payload is None:
        return ArtifactValidation(
            pin.artifact_id,
            pin.relative_path,
            pin.optional,
            False,
            pin.bytes,
            None,
            pin.sha256,
            None,
            False,
            "OPTIONAL_ABSENT" if pin.optional else "MISSING",
        )
    actual_bytes = len(payload)
    actual_sha = _sha256(payload)
    exact = actual_bytes == pin.bytes and actual_sha == pin.sha256
    return ArtifactValidation(
        pin.artifact_id,
        pin.relative_path,
        pin.optional,
        True,
        pin.bytes,
        actual_bytes,
        pin.sha256,
        actual_sha,
        exact,
        "EXACT" if exact else "BYTE_OR_SHA_MISMATCH",
    )


def validate_historical_artifacts(project_root: str | Path | None = None) -> dict[str, object]:
    """Audit all core pins and validate optional E19 whenever it is present."""

    root = Path(project_root) if project_root is not None else project_root_from_module()
    records: dict[str, ArtifactValidation] = {}
    for pin in HISTORICAL_ARTIFACT_PINS:
        path = root / pin.relative_path
        payload = path.read_bytes() if path.is_file() else None
        records[pin.artifact_id] = validate_artifact_payload(pin, payload)
    required = [record for record in records.values() if not record.optional]
    present = [record for record in records.values() if record.present]
    return {
        "scope": HISTORICAL_ANCHOR_SCOPE,
        "artifacts": records,
        "all_required_exact": all(record.exact for record in required),
        "all_present_artifacts_exact": all(record.exact for record in present),
        "historical_gate_preserved": records["sim10_gate_json"].exact,
        "unified_r2_pass_inherited": False,
    }


def _read_required_historical_payloads(root: Path) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    failures: list[str] = []
    for pin in HISTORICAL_ARTIFACT_PINS:
        path = root / pin.relative_path
        payload = path.read_bytes() if path.is_file() else None
        validation = validate_artifact_payload(pin, payload)
        if payload is not None:
            payloads[pin.artifact_id] = payload
        if (not pin.optional and not validation.exact) or (
            pin.optional and validation.present and not validation.exact
        ):
            failures.append(f"{pin.artifact_id}:{validation.status}")
    if failures:
        raise RegressionOracleError("historical artifact pin failure: " + ",".join(failures))
    return payloads


def half_last_digit_tolerance(stored_text: str) -> float:
    """Return half one unit in the last explicitly stored decimal digit."""

    try:
        value = Decimal(stored_text.strip())
    except InvalidOperation as exc:
        raise RegressionOracleError(f"invalid stored numeric text: {stored_text!r}") from exc
    if not value.is_finite():
        raise RegressionOracleError("stored numeric text must be finite")
    return float(Decimal("0.5") * (Decimal(10) ** value.as_tuple().exponent))


def half_last_digit_crosscheck(exact_value: float, stored_text: str) -> HalfLastDigitCrosscheck:
    if not math.isfinite(exact_value):
        raise RegressionOracleError("exact crosscheck value must be finite")
    try:
        stored_decimal = Decimal(stored_text.strip())
    except InvalidOperation as exc:
        raise RegressionOracleError(f"invalid stored numeric text: {stored_text!r}") from exc
    exact_decimal = Decimal(str(exact_value))
    difference = abs(exact_decimal - stored_decimal)
    tolerance = Decimal(str(half_last_digit_tolerance(stored_text)))
    return HalfLastDigitCrosscheck(
        float(exact_decimal),
        stored_text,
        float(stored_decimal),
        float(difference),
        float(tolerance),
        difference <= tolerance,
    )


def _csv_rows(payload: bytes, artifact_id: str) -> list[dict[str, str]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RegressionOracleError(f"{artifact_id} is not UTF-8 CSV") from exc
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not reader.fieldnames or not rows:
        raise RegressionOracleError(f"{artifact_id} has no parseable rows")
    return rows


def _unique_sim06_row(
    rows: Sequence[Mapping[str, str]], target: str, tumble_dps: str, v_app_mps: str
) -> Mapping[str, str]:
    matches = [
        row
        for row in rows
        if row.get("target") == target
        and Decimal(row.get("tumble_dps", "NaN")) == Decimal(tumble_dps)
        and Decimal(row.get("v_app_mps", "NaN")) == Decimal(v_app_mps)
    ]
    if len(matches) != 1:
        raise RegressionOracleError(
            f"expected exactly one sim06 row for {target}/{tumble_dps}/{v_app_mps}"
        )
    return matches[0]


def load_historical_regression_anchors(
    project_root: str | Path | None = None,
) -> dict[str, object]:
    """Parse hash-pinned stored anchors without invoking legacy model code."""

    root = Path(project_root) if project_root is not None else project_root_from_module()
    payloads = _read_required_historical_payloads(root)

    sim05_rows = _csv_rows(payloads["sim05_base_attitude_csv"], "sim05_base_attitude_csv")
    try:
        sim05_peak_text = max(sim05_rows, key=lambda row: float(row["base_dev_angle_deg"]))[
            "base_dev_angle_deg"
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise RegressionOracleError("sim05 peak column is invalid") from exc
    if sim05_peak_text != "19.199852":
        raise RegressionOracleError(f"sim05 stored peak drift: {sim05_peak_text}")

    sim06_rows = _csv_rows(payloads["sim06_capture_matrix_csv"], "sim06_capture_matrix_csv")
    sim06_keys = {
        "debris_3dps": ("target_debris_v0", "3", "0.01", "3.06333"),
        "satellite_3dps": ("target_satellite_v0", "3", "0.01", "1.38721"),
        "satellite_0p5dps": ("target_satellite_v0", "0.5", "0.01", "0.231202"),
    }
    sim06: dict[str, dict[str, object]] = {}
    for anchor_id, (target, tumble, v_app, expected_text) in sim06_keys.items():
        row = _unique_sim06_row(sim06_rows, target, tumble, v_app)
        actual_text = row.get("post_rate_full_dps", "")
        if actual_text != expected_text:
            raise RegressionOracleError(f"sim06 {anchor_id} stored anchor drift: {actual_text}")
        sim06[anchor_id] = {
            "target": target,
            "tumble_dps": float(tumble),
            "v_app_mps": float(v_app),
            "stored_post_rate_text_dps": actual_text,
            "stored_post_rate_dps": float(actual_text),
            "classification": "HISTORICAL_CSV_STORAGE_RESOLUTION_ANCHOR",
        }

    try:
        sim10_gate = json.loads(payloads["sim10_gate_json"].decode("utf-8-sig"))
        checks = sim10_gate["gates"]["X1_anchors_vs_sim06"]["checks"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RegressionOracleError("sim10 gate anchor structure is invalid") from exc
    expected_sim10 = {
        "debris_sim06": (3.0633304945807067, "INFEASIBLE_RATE", "debris_3dps"),
        "satellite_sim06": (1.3872061825379134, "WHEELS_ONLY_FEASIBLE", "satellite_3dps"),
    }
    sim10: dict[str, dict[str, object]] = {}
    for anchor_id, (expected_value, expected_region, sim06_id) in expected_sim10.items():
        matches = [entry for entry in checks if entry.get("anchor") == anchor_id]
        if len(matches) != 1:
            raise RegressionOracleError(f"sim10 anchor {anchor_id} is missing or duplicated")
        entry = matches[0]
        exact_value = float(entry.get("w_plus_dps"))
        region = entry.get("region")
        if exact_value != expected_value or region != expected_region:
            raise RegressionOracleError(f"sim10 exact anchor or region drift: {anchor_id}")
        crosscheck = half_last_digit_crosscheck(
            exact_value, str(sim06[sim06_id]["stored_post_rate_text_dps"])
        )
        if not crosscheck.within_tolerance:
            raise RegressionOracleError(f"sim10/sim06 half-last-digit crosscheck failed: {anchor_id}")
        sim10[anchor_id] = {
            "exact_post_rate_dps": exact_value,
            "region": region,
            "sim06_storage_anchor_id": sim06_id,
            "csv_crosscheck": crosscheck,
        }

    e19 = None
    if "e19_diagnostic_gate_json" in payloads:
        try:
            e19_gate = json.loads(payloads["e19_diagnostic_gate_json"].decode("utf-8-sig"))
            e19 = {
                "gate": e19_gate["gate"],
                "release_credit": e19_gate["release_credit"],
                "next_stage_authorized": e19_gate["next_stage_authorized"],
                "authority_scope": e19_gate["authority_scope"],
            }
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RegressionOracleError("optional E19 gate structure is invalid") from exc

    return {
        "scope": HISTORICAL_ANCHOR_SCOPE,
        "sim05": {
            "peak_base_deviation_text_deg": sim05_peak_text,
            "peak_base_deviation_deg": float(sim05_peak_text),
            "classification": "HISTORICAL_CSV_STORAGE_RESOLUTION_ANCHOR",
        },
        "sim06": sim06,
        "sim10": sim10,
        "sim10_historical_gate_verdict": sim10_gate.get("verdict"),
        "historical_gate_preserved": True,
        "unified_r2_pass_inherited": False,
        "e19_optional": e19,
    }


def audit_current_reexecution_inputs(
    project_root: str | Path | None = None,
) -> dict[str, object]:
    """Detect current path/hash blockers without importing broken legacy loaders."""

    root = Path(project_root) if project_root is not None else project_root_from_module()
    legacy = {
        key: {
            "relative_path": relative_path,
            "exists": (root / relative_path).is_file(),
        }
        for key, relative_path in LEGACY_DEFAULT_INPUT_PATHS.items()
    }
    registry_path = root / THRESHOLD_REGISTRY_RELATIVE_PATH
    actual_registry_hash = _sha256(registry_path.read_bytes()) if registry_path.is_file() else None
    registry_match = actual_registry_hash == SIM10_EXPECTED_THRESHOLD_REGISTRY_SHA256
    historical_audit = validate_historical_artifacts(root)
    input_ready = (
        all(item["exists"] for item in legacy.values())
        and registry_match
        and bool(historical_audit["all_required_exact"])
    )
    status = (
        "READY_FOR_EXPLICIT_REEXECUTION_NOT_EXECUTED"
        if input_ready
        else CURRENT_REEXECUTION_HOLD
    )
    return {
        "current_reexecution_status": status,
        "legacy_default_inputs": legacy,
        "legacy_default_path_missing": any(not item["exists"] for item in legacy.values()),
        "threshold_registry": {
            "relative_path": THRESHOLD_REGISTRY_RELATIVE_PATH,
            "exists": registry_path.is_file(),
            "expected_sha256": SIM10_EXPECTED_THRESHOLD_REGISTRY_SHA256,
            "actual_sha256": actual_registry_hash,
            "observed_current_sha256_pin": CURRENT_OBSERVED_THRESHOLD_REGISTRY_SHA256,
            "matches_sim10_frozen_expected": registry_match,
            "matches_observed_current_pin": (
                actual_registry_hash == CURRENT_OBSERVED_THRESHOLD_REGISTRY_SHA256
            ),
        },
        "historical_sim10_gate_preserved": historical_audit["artifacts"][
            "sim10_gate_json"
        ].exact,
        "historical_gate_is_current_reexecution": False,
        "unified_r2_pass_inherited": False,
    }


def _vector(values: Sequence[float], size: int, label: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise RegressionOracleError(f"{label} must be a finite {size}-vector")
    return result.copy()


def _positive_definite_inertia(values: Sequence[Sequence[float]], label: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (3, 3) or not np.all(np.isfinite(result)):
        raise RegressionOracleError(f"{label} must be a finite 3x3 matrix")
    if not np.allclose(result, result.T, atol=1.0e-13, rtol=0.0):
        raise RegressionOracleError(f"{label} must be symmetric")
    result = 0.5 * (result + result.T)
    if np.min(np.linalg.eigvalsh(result)) <= 0.0:
        raise RegressionOracleError(f"{label} must be positive definite")
    return result.copy()


def _steiner(mass_kg: float, displacement_m: np.ndarray) -> np.ndarray:
    return mass_kg * (
        float(displacement_m @ displacement_m) * np.eye(3)
        - np.outer(displacement_m, displacement_m)
    )


def combine_unified_r2_service_body(
    model: URDFTreeDynamics,
    q: Sequence[float] | Mapping[str, float] | None,
) -> ServiceRigidBodyAggregate:
    """Combine current in-memory V2 physical links about the system CoM."""

    if not isinstance(model, URDFTreeDynamics):
        raise RegressionOracleError("model must be a URDFTreeDynamics instance")
    bodies = model.body_kinematics(q)
    if not bodies:
        raise RegressionOracleError("current model contains no physical bodies")
    total_mass = float(sum(body.mass_kg for body in bodies))
    com = sum((body.mass_kg * body.com_root_m for body in bodies), np.zeros(3)) / total_mass
    inertia = np.zeros((3, 3))
    for body in bodies:
        displacement = body.com_root_m - com
        inertia += body.inertia_root_kg_m2 + _steiner(body.mass_kg, displacement)
    inertia = _positive_definite_inertia(inertia, "combined service inertia")
    return ServiceRigidBodyAggregate(
        total_mass,
        com,
        inertia,
        len(bodies),
    )


def ideal_two_body_hard_lock(
    service: ServiceRigidBodyAggregate,
    target: ExplicitTargetFixture,
    *,
    service_linear_velocity_root_m_s: Sequence[float] = (0.0, 0.0, 0.0),
    service_angular_velocity_root_rad_s: Sequence[float] = (0.0, 0.0, 0.0),
) -> HardLockMomentumLimit:
    """Evaluate the ideal plastic hard-lock momentum limit for two rigid bodies."""

    if service.authority_class != SOURCE_ONLY_SERVICE_AGGREGATE:
        raise RegressionOracleError("service aggregate carries an unexpected authority class")
    if target.authority_class != EXPLICIT_FIXTURE_NO_AUTHORITY:
        raise RegressionOracleError("target must remain an explicit no-authority fixture")
    service_linear = _vector(service_linear_velocity_root_m_s, 3, "service linear velocity")
    service_angular = _vector(service_angular_velocity_root_rad_s, 3, "service angular velocity")
    service_inertia = _positive_definite_inertia(
        service.inertia_about_com_root_kg_m2, "service inertia"
    )
    target_inertia = _positive_definite_inertia(
        target.inertia_about_com_root_kg_m2, "target inertia"
    )

    masses = np.array((service.mass_kg, target.mass_kg), dtype=float)
    positions = np.vstack((service.com_root_m, target.com_root_m))
    linear_velocities = np.vstack((service_linear, target.linear_velocity_root_m_s))
    angular_velocities = np.vstack((service_angular, target.angular_velocity_root_rad_s))
    inertias = (service_inertia, target_inertia)
    total_mass = float(np.sum(masses))
    combined_com = np.sum(masses[:, None] * positions, axis=0) / total_mass
    combined_linear_velocity = (
        np.sum(masses[:, None] * linear_velocities, axis=0) / total_mass
    )
    combined_inertia = np.zeros((3, 3))
    angular_momentum_com = np.zeros(3)
    for index in range(2):
        displacement = positions[index] - combined_com
        combined_inertia += inertias[index] + _steiner(masses[index], displacement)
        angular_momentum_com += inertias[index] @ angular_velocities[index]
        angular_momentum_com += masses[index] * np.cross(
            displacement, linear_velocities[index] - combined_linear_velocity
        )
    combined_inertia = _positive_definite_inertia(combined_inertia, "hard-lock inertia")
    combined_angular_velocity = np.linalg.solve(combined_inertia, angular_momentum_com)

    linear_pre = np.sum(masses[:, None] * linear_velocities, axis=0)
    linear_post = total_mass * combined_linear_velocity
    angular_pre_root = sum(
        (
            inertias[index] @ angular_velocities[index]
            + masses[index] * np.cross(positions[index], linear_velocities[index])
            for index in range(2)
        ),
        np.zeros(3),
    )
    angular_post_root = combined_inertia @ combined_angular_velocity + total_mass * np.cross(
        combined_com, combined_linear_velocity
    )
    energy_pre = float(
        sum(
            0.5 * masses[index] * linear_velocities[index] @ linear_velocities[index]
            + 0.5
            * angular_velocities[index]
            @ inertias[index]
            @ angular_velocities[index]
            for index in range(2)
        )
    )
    energy_post = float(
        0.5 * total_mass * combined_linear_velocity @ combined_linear_velocity
        + 0.5 * combined_angular_velocity @ combined_inertia @ combined_angular_velocity
    )
    energy_loss = energy_pre - energy_post
    tolerance = 1.0e-12 * max(abs(energy_pre), 1.0)
    if energy_loss < -tolerance:
        raise RegressionOracleError("ideal plastic hard lock increased kinetic energy")
    linear_residual = float(
        np.linalg.norm(linear_post - linear_pre) / max(np.linalg.norm(linear_pre), 1.0)
    )
    angular_residual = float(
        np.linalg.norm(angular_post_root - angular_pre_root)
        / max(np.linalg.norm(angular_pre_root), 1.0)
    )
    return HardLockMomentumLimit(
        HARD_LOCK_SCOPE,
        service.authority_class,
        target.authority_class,
        total_mass,
        combined_com,
        combined_linear_velocity,
        combined_inertia,
        combined_angular_velocity,
        float(np.rad2deg(np.linalg.norm(combined_angular_velocity))),
        linear_pre,
        linear_post,
        angular_pre_root,
        angular_post_root,
        linear_residual,
        angular_residual,
        energy_pre,
        energy_post,
        energy_loss,
        energy_loss >= -tolerance,
    )


def single_link_capture_sensitivity(
    model: URDFTreeDynamics,
    q: Sequence[float] | Mapping[str, float] | None,
    target: ExplicitTargetFixture,
    link_name: str,
    *,
    mass_scale: float = 1.01,
    inertia_scale: float = 1.01,
    com_delta_link_m: Sequence[float] = (0.0, 0.0, 0.0),
    service_linear_velocity_root_m_s: Sequence[float] = (0.0, 0.0, 0.0),
    service_angular_velocity_root_rad_s: Sequence[float] = (0.0, 0.0, 0.0),
) -> dict[str, object]:
    """Show whether one source-only service-link perturbation moves capture output."""

    baseline_service = combine_unified_r2_service_body(model, q)
    perturbed_model = model.perturbed_link_model(
        link_name,
        mass_scale=mass_scale,
        inertia_scale=inertia_scale,
        com_delta_link_m=com_delta_link_m,
    )
    perturbed_service = combine_unified_r2_service_body(perturbed_model, q)
    common = {
        "service_linear_velocity_root_m_s": service_linear_velocity_root_m_s,
        "service_angular_velocity_root_rad_s": service_angular_velocity_root_rad_s,
    }
    baseline = ideal_two_body_hard_lock(baseline_service, target, **common)
    perturbed = ideal_two_body_hard_lock(perturbed_service, target, **common)
    rate_delta = perturbed.post_rate_dps - baseline.post_rate_dps
    omega_delta = perturbed.combined_angular_velocity_root_rad_s - baseline.combined_angular_velocity_root_rad_s
    return {
        "scope": HARD_LOCK_SCOPE,
        "authority_class": "SOURCE_ONLY_SINGLE_LINK_CAPTURE_SENSITIVITY_NOT_GATE_EVIDENCE",
        "link_name": link_name,
        "baseline": baseline,
        "perturbed": perturbed,
        "post_rate_delta_dps": float(rate_delta),
        "omega_vector_delta_norm_rad_s": float(np.linalg.norm(omega_delta)),
        "capture_output_changed": bool(
            abs(rate_delta) > 0.0 or np.linalg.norm(omega_delta) > 0.0
        ),
    }


__all__ = [
    "ArtifactPin",
    "ArtifactValidation",
    "CURRENT_OBSERVED_THRESHOLD_REGISTRY_SHA256",
    "CURRENT_REEXECUTION_HOLD",
    "EXPLICIT_FIXTURE_NO_AUTHORITY",
    "ExplicitTargetFixture",
    "HARD_LOCK_SCOPE",
    "HISTORICAL_ANCHOR_SCOPE",
    "HISTORICAL_ARTIFACT_PINS",
    "HalfLastDigitCrosscheck",
    "HardLockMomentumLimit",
    "LEGACY_DEFAULT_INPUT_PATHS",
    "RegressionOracleError",
    "SIM10_EXPECTED_THRESHOLD_REGISTRY_SHA256",
    "SOURCE_ONLY_SERVICE_AGGREGATE",
    "ServiceRigidBodyAggregate",
    "THRESHOLD_REGISTRY_RELATIVE_PATH",
    "audit_current_reexecution_inputs",
    "combine_unified_r2_service_body",
    "half_last_digit_crosscheck",
    "half_last_digit_tolerance",
    "ideal_two_body_hard_lock",
    "load_historical_regression_anchors",
    "project_root_from_module",
    "single_link_capture_sensitivity",
    "validate_artifact_payload",
    "validate_historical_artifacts",
]
