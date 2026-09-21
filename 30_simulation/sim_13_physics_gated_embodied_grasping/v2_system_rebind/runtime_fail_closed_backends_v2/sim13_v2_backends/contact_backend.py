"""Authoritative narrow-phase contact backend (WO-NC19).

The backend binds three hash-pinned sources:

1. the emitted Unified R2 URDF (gripper prismatic joints and stroke);
2. ``DESIGN_CONTACT_MODEL_V1.yaml`` (BOUNDED_PROVISIONAL envelope -- every
   numeric parameter used here must sit inside its declared [lower, upper]
   band; a null, absent, or out-of-band parameter maps to UNKNOWN, and UNKNOWN
   masks every non-ABORT request to the canonical ABORT);
3. the released narrow-phase contact-geometry artifact emitted by
   ``emit_released_contact_geometry_v1.py`` (derived, not measured).

The narrow phase is an exact analytic two-pad grasp model: each finger pad is
a plane whose position along the closing axis is an affine function of its
prismatic coordinate, and the target is a plate of released half-thickness.
Signed gap and penetration depth are exact; the normal force follows the
contract's Hertz-family model ``F_n = k_n * penetration^exponent`` with the
nominal in-envelope parameters, and tangential feasibility is checked against
the static-friction cone.  Overlapping geometry that produces no contact-state
update is a backend defect and is flagged ``CONTACT_DETECTION_FAILURE``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .canonical import canonical_digest, sha256_bytes


BACKEND_ID = "SIM13_V2_NARROW_PHASE_CONTACT_BACKEND_V1"
BACKEND_SCOPE = (
    "BOUNDED_PROVISIONAL_NARROW_PHASE_DETECTION_NOT_CONTINUOUS_CONTACT_DYNAMICS"
)
CONTACT_MODEL_RELATIVE_PATH = (
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/"
    "DESIGN_CONTACT_MODEL_V1.yaml"
)
EXPECTED_CONTACT_MODEL_BYTES = 9131
EXPECTED_CONTACT_MODEL_SHA256 = (
    "E57C799768BFDAB5DF22A3B834F6C8B9F8232D046A46774D24CA1FBB3DB879AD"
)
GEOMETRY_SCHEMA = "SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1"
GEOMETRY_CLASS = "BOUNDED_PROVISIONAL_DERIVED_NOT_MEASURED"

STATE_UNKNOWN = "UNKNOWN"
STATE_NO_CONTACT = "NO_CONTACT"
STATE_CONTACT = "CONTACT"
OUTCOME_ABORT = "MASK_TO_ABORT_ONLY"


class ContactSourceError(RuntimeError):
    """Raised when a pinned contact source is absent or hash-drifted."""


class ContactEnvelopeError(ValueError):
    """Raised when inputs leave the DESIGN_CONTACT_MODEL_V1 envelope."""


@dataclass(frozen=True)
class EnvelopeBand:
    nominal: float
    lower: float
    upper: float

    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper


@dataclass(frozen=True)
class PadState:
    finger_id: str
    slide_m: float
    signed_gap_m: float
    penetration_m: float
    contact: bool
    normal_force_N: float


@dataclass(frozen=True)
class ContactUpdate:
    state: str
    reason_code: str
    pads: tuple[PadState, ...]
    total_normal_force_N: float
    friction_cone_satisfied: bool | None
    envelope: Mapping[str, Any]

    @property
    def contact_state_updated(self) -> bool:
        return self.state == STATE_CONTACT and any(p.contact for p in self.pads)


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContactEnvelopeError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ContactEnvelopeError(f"{field} must be finite")
    return result


def _band(node: Any, field: str) -> EnvelopeBand:
    if not isinstance(node, Mapping):
        raise ContactEnvelopeError(f"{field} band missing")
    nominal = node.get("nominal")
    lower = node.get("lower")
    upper = node.get("upper")
    band = EnvelopeBand(
        _finite(nominal, f"{field}.nominal"),
        _finite(lower, f"{field}.lower"),
        _finite(upper, f"{field}.upper"),
    )
    if band.lower > band.nominal or band.nominal > band.upper:
        raise ContactEnvelopeError(f"{field} band ordering invalid")
    return band


class NarrowPhaseContactBackend:
    """Hash-bound two-pad narrow-phase detector within the contact envelope."""

    def __init__(
        self,
        *,
        project_root: str | Path,
        contact_geometry: Mapping[str, Any],
        contact_model_path: str | Path | None = None,
    ) -> None:
        root = Path(project_root).resolve()
        self.project_root = root
        model_path = (
            Path(contact_model_path).resolve()
            if contact_model_path is not None
            else (root / CONTACT_MODEL_RELATIVE_PATH).resolve()
        )
        self.contact_model_path = model_path
        if not model_path.is_file():
            raise ContactSourceError("DESIGN_CONTACT_MODEL_V1_SOURCE_MISSING")
        model_bytes = model_path.read_bytes()
        if (
            len(model_bytes) != EXPECTED_CONTACT_MODEL_BYTES
            or sha256_bytes(model_bytes) != EXPECTED_CONTACT_MODEL_SHA256
        ):
            raise ContactSourceError("DESIGN_CONTACT_MODEL_V1_HASH_DRIFT")
        document = yaml.safe_load(model_bytes.decode("utf-8"))
        if not isinstance(document, Mapping) or document.get("schema") != "DESIGN_CONTACT_MODEL_V1":
            raise ContactSourceError("DESIGN_CONTACT_MODEL_V1_SCHEMA_DRIFT")
        if document.get("class") != "BOUNDED_PROVISIONAL__NOT_A_MEASUREMENT__NOT_AS_BUILT":
            raise ContactSourceError("DESIGN_CONTACT_MODEL_V1_CLASS_DRIFT")
        self.contact_model = document
        self.contact_model_sha256 = sha256_bytes(model_bytes)

        if not isinstance(contact_geometry, Mapping):
            raise ContactSourceError("CONTACT_GEOMETRY_MALFORMED")
        if (
            contact_geometry.get("schema") != GEOMETRY_SCHEMA
            or contact_geometry.get("class") != GEOMETRY_CLASS
        ):
            raise ContactSourceError("CONTACT_GEOMETRY_SCHEMA_OR_CLASS_DRIFT")
        provenance = contact_geometry.get("provenance", {})
        if provenance.get("design_contact_model_v1_sha256") != self.contact_model_sha256:
            raise ContactSourceError("CONTACT_GEOMETRY_PROVENANCE_DRIFT")
        self.geometry = contact_geometry

        normal = document["normal_contact"]
        tangential = document["tangential_contact"]
        actuator = document["gripper_actuator"]
        geometry_contract = document["contact_geometry"]
        self.bands = {
            "normal_stiffness_N_per_m": _band(
                normal["normal_stiffness_N_per_m"], "normal_stiffness"
            ),
            "exponent": _band(normal["exponent"], "exponent"),
            "static_friction": _band(tangential["static_friction"], "static_friction"),
            "stroke_m": _band(actuator["stroke_m"], "stroke"),
            "first_contact_closing_velocity_mps": _band(
                actuator["first_contact_closing_velocity_mps"], "closing_velocity"
            ),
            "effective_area_m2": _band(
                geometry_contract["effective_area_m2"], "effective_area"
            ),
            "initial_gap_m": _band(geometry_contract["initial_gap_m"], "initial_gap"),
        }
        self._verify_geometry_against_envelope()

    def _verify_geometry_against_envelope(self) -> None:
        pads = self.geometry.get("pads")
        target = self.geometry.get("target_plate")
        if not isinstance(pads, Mapping) or set(pads) != {"left", "right"}:
            raise ContactSourceError("CONTACT_GEOMETRY_PADS_MALFORMED")
        if not isinstance(target, Mapping):
            raise ContactSourceError("CONTACT_GEOMETRY_TARGET_MALFORMED")
        stroke = self.bands["stroke_m"].nominal
        gap = self.bands["initial_gap_m"].nominal
        for name in ("left", "right"):
            pad = pads[name]
            if pad.get("face_normal_gripper_link") not in ([0.0, -1.0, 0.0], [0.0, 1.0, 0.0]):
                raise ContactSourceError("CONTACT_GEOMETRY_PAD_NORMAL_MALFORMED")
            open_face = _finite(pad.get("open_face_position_m"), f"{name}.open_face_position_m")
            if abs(abs(open_face) - stroke) > 1.0e-12:
                raise ContactSourceError("CONTACT_GEOMETRY_PAD_STROKE_INCONSISTENT")
        half_thickness = _finite(
            target.get("half_thickness_m"), "target.half_thickness_m"
        )
        expected_half = stroke - gap
        if abs(half_thickness - expected_half) > 1.0e-12:
            raise ContactSourceError("CONTACT_GEOMETRY_TARGET_GAP_INCONSISTENT")

    def _envelope_inputs(self, q_left: float, q_right: float) -> None:
        stroke = self.bands["stroke_m"]
        for value, field in ((q_left, "q_left"), (q_right, "q_right")):
            slide = _finite(value, field)
            if not (0.0 <= slide <= stroke.upper):
                raise ContactEnvelopeError(f"{field} outside prismatic stroke envelope")

    def detect(self, q_left: float, q_right: float) -> ContactUpdate:
        """Exact narrow-phase update; raises ContactEnvelopeError out-of-envelope."""

        self._envelope_inputs(q_left, q_right)
        stroke = self.bands["stroke_m"].nominal
        half_thickness = _finite(
            self.geometry["target_plate"]["half_thickness_m"], "half_thickness"
        )
        stiffness = self.bands["normal_stiffness_N_per_m"].nominal
        exponent = self.bands["exponent"].nominal
        mu_static = self.bands["static_friction"].nominal

        pads: list[PadState] = []
        for finger_id, slide, sign in (
            ("left", float(q_left), +1.0),
            ("right", float(q_right), -1.0),
        ):
            face = sign * (stroke - slide)
            signed_gap = abs(face) - half_thickness
            penetration = max(0.0, -signed_gap)
            contact = penetration > 0.0
            normal_force = stiffness * (penetration ** exponent) if contact else 0.0
            pads.append(
                PadState(
                    finger_id=finger_id,
                    slide_m=slide,
                    signed_gap_m=signed_gap,
                    penetration_m=penetration,
                    contact=contact,
                    normal_force_N=normal_force,
                )
            )
        any_contact = any(pad.contact for pad in pads)
        total_normal = sum(pad.normal_force_N for pad in pads)
        friction_limit = mu_static * total_normal
        state = STATE_CONTACT if any_contact else STATE_NO_CONTACT
        reason = (
            "CONTACT_STATE_UPDATED_NARROW_PHASE" if any_contact else "CLEARANCE_POSITIVE_NO_CONTACT"
        )
        return ContactUpdate(
            state=state,
            reason_code=reason,
            pads=tuple(pads),
            total_normal_force_N=total_normal,
            friction_cone_satisfied=(True if any_contact else None),
            envelope={
                "friction_tangential_limit_N": friction_limit,
                "static_friction_nominal": mu_static,
                "normal_stiffness_nominal_N_per_m": stiffness,
                "exponent_nominal": exponent,
                "bounded_provisional_class": True,
            },
        )

    def detect_fail_closed(self, q_left: float, q_right: float) -> ContactUpdate:
        """UNKNOWN-mapping wrapper: out-of-envelope never raises to the caller."""

        try:
            return self.detect(q_left, q_right)
        except ContactEnvelopeError as exc:
            return ContactUpdate(
                state=STATE_UNKNOWN,
                reason_code=f"CONTACT_ENVELOPE_UNKNOWN_MASKS_TO_ABORT:{exc}",
                pads=(),
                total_normal_force_N=0.0,
                friction_cone_satisfied=None,
                envelope={"bounded_provisional_class": True},
            )


class BrokenContactDetector:
    """Negative-control fixture: overlapping geometry with no contact update."""

    def __init__(self, backend: NarrowPhaseContactBackend) -> None:
        self._backend = backend

    def detect(self, q_left: float, q_right: float) -> ContactUpdate:
        nominal = self._backend.detect(q_left, q_right)
        return ContactUpdate(
            state=STATE_NO_CONTACT,
            reason_code="BROKEN_DETECTOR_REPORTS_NO_UPDATE",
            pads=tuple(
                PadState(
                    finger_id=pad.finger_id,
                    slide_m=pad.slide_m,
                    signed_gap_m=pad.signed_gap_m,
                    penetration_m=pad.penetration_m,
                    contact=False,
                    normal_force_N=0.0,
                )
                for pad in nominal.pads
            ),
            total_normal_force_N=0.0,
            friction_cone_satisfied=None,
            envelope=nominal.envelope,
        )


def audit_detector_consistency(
    authoritative: ContactUpdate, candidate: ContactUpdate
) -> Mapping[str, Any]:
    """Flag a candidate that misses contact under proven geometric overlap."""

    overlap = any(pad.penetration_m > 0.0 for pad in authoritative.pads)
    candidate_missed = overlap and not candidate.contact_state_updated
    return {
        "authoritative_overlap": overlap,
        "authoritative_contact_state_updated": authoritative.contact_state_updated,
        "candidate_contact_state_updated": candidate.contact_state_updated,
        "contact_detection_failure": candidate_missed,
        "reason_code": (
            "CONTACT_DETECTION_FAILURE" if candidate_missed else "DETECTOR_CONSISTENT"
        ),
    }


def build_validation_receipt(
    backend: NarrowPhaseContactBackend,
    *,
    geometry_record: Mapping[str, Any],
) -> Mapping[str, Any]:
    gap = backend.bands["initial_gap_m"].nominal
    clearance = backend.detect(gap * 0.5, gap * 0.5)
    touch = backend.detect(gap, gap)
    overlap = backend.detect(gap + 1.0e-3, gap + 1.0e-3)
    broken = BrokenContactDetector(backend).detect(gap + 1.0e-3, gap + 1.0e-3)
    consistency = audit_detector_consistency(overlap, broken)
    out_of_envelope = backend.detect_fail_closed(
        backend.bands["stroke_m"].upper + 1.0e-3, gap
    )
    checks = {
        "clearance_configuration_reports_no_contact": (
            clearance.state == STATE_NO_CONTACT
            and clearance.contact_state_updated is False
        ),
        "touch_configuration_at_zero_penetration": (
            touch.state == STATE_NO_CONTACT
            and all(pad.penetration_m == 0.0 for pad in touch.pads)
        ),
        "overlap_configuration_updates_contact_state": (
            overlap.state == STATE_CONTACT and overlap.contact_state_updated is True
        ),
        "normal_force_follows_hertz_contract": math.isclose(
            overlap.total_normal_force_N,
            2.0
            * backend.bands["normal_stiffness_N_per_m"].nominal
            * (1.0e-3 ** backend.bands["exponent"].nominal),
            rel_tol=1.0e-12,
            abs_tol=0.0,
        ),
        "broken_detector_flagged_contact_detection_failure": (
            consistency["contact_detection_failure"] is True
            and consistency["reason_code"] == "CONTACT_DETECTION_FAILURE"
        ),
        "out_of_envelope_maps_unknown_to_abort_only": (
            out_of_envelope.state == STATE_UNKNOWN
            and out_of_envelope.reason_code.startswith(
                "CONTACT_ENVELOPE_UNKNOWN_MASKS_TO_ABORT"
            )
        ),
    }
    return {
        "schema": "SIM13_V2_CONTACT_BACKEND_VALIDATION_RECEIPT_V1",
        "backend_id": BACKEND_ID,
        "backend_scope": BACKEND_SCOPE,
        "design_contact_model": {
            "path": CONTACT_MODEL_RELATIVE_PATH,
            "bytes": EXPECTED_CONTACT_MODEL_BYTES,
            "sha256": backend.contact_model_sha256,
            "class": "BOUNDED_PROVISIONAL__NOT_A_MEASUREMENT__NOT_AS_BUILT",
        },
        "released_contact_geometry": dict(geometry_record),
        "clearance_update_sha256": canonical_digest(_update_as_dict(clearance)),
        "overlap_update_sha256": canonical_digest(_update_as_dict(overlap)),
        "overlap_penetration_m": [pad.penetration_m for pad in overlap.pads],
        "overlap_total_normal_force_N": overlap.total_normal_force_N,
        "broken_detector_audit": dict(consistency),
        "out_of_envelope_reason": out_of_envelope.reason_code,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _update_as_dict(update: ContactUpdate) -> Mapping[str, Any]:
    return {
        "state": update.state,
        "reason_code": update.reason_code,
        "total_normal_force_N": update.total_normal_force_N,
        "friction_cone_satisfied": update.friction_cone_satisfied,
        "pads": [
            {
                "finger_id": pad.finger_id,
                "slide_m": pad.slide_m,
                "signed_gap_m": pad.signed_gap_m,
                "penetration_m": pad.penetration_m,
                "contact": pad.contact,
                "normal_force_N": pad.normal_force_N,
            }
            for pad in update.pads
        ],
    }


__all__ = [
    "BACKEND_ID",
    "BACKEND_SCOPE",
    "BrokenContactDetector",
    "CONTACT_MODEL_RELATIVE_PATH",
    "ContactEnvelopeError",
    "ContactSourceError",
    "ContactUpdate",
    "EXPECTED_CONTACT_MODEL_BYTES",
    "EXPECTED_CONTACT_MODEL_SHA256",
    "GEOMETRY_CLASS",
    "GEOMETRY_SCHEMA",
    "NarrowPhaseContactBackend",
    "OUTCOME_ABORT",
    "PadState",
    "STATE_CONTACT",
    "STATE_NO_CONTACT",
    "STATE_UNKNOWN",
    "audit_detector_consistency",
    "build_validation_receipt",
]
