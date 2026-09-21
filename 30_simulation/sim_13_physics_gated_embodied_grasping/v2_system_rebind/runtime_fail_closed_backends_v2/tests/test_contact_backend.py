"""NC19 backend tests: schema, nominal, malformed, missing/stale source,
UNKNOWN-out-of-envelope fail-closed, deterministic replay, read-only."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from sim13_v2_backends.contact_backend import (
    CONTACT_MODEL_RELATIVE_PATH,
    BrokenContactDetector,
    ContactEnvelopeError,
    ContactSourceError,
    NarrowPhaseContactBackend,
    audit_detector_consistency,
    build_validation_receipt,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
GEOMETRY_PATH = PACKAGE_ROOT / "assets" / "SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1.json"


def _geometry() -> dict:
    return json.loads(GEOMETRY_PATH.read_bytes().decode("utf-8"))


def _backend(project_root: Path) -> NarrowPhaseContactBackend:
    return NarrowPhaseContactBackend(
        project_root=project_root, contact_geometry=_geometry()
    )


def test_schema_and_envelope_bands(project_root):
    backend = _backend(project_root)
    assert backend.bands["stroke_m"].nominal == pytest.approx(0.0715)
    assert backend.bands["initial_gap_m"].nominal == pytest.approx(0.005)
    assert backend.bands["normal_stiffness_N_per_m"].lower == pytest.approx(1.0e5)
    assert backend.bands["normal_stiffness_N_per_m"].upper == pytest.approx(1.0e7)
    geometry = _geometry()
    assert geometry["schema"] == "SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1"
    assert geometry["class"] == "BOUNDED_PROVISIONAL_DERIVED_NOT_MEASURED"
    assert geometry["review_status"] == "PENDING_OWNER_REVIEW"


def test_nominal_clearance_touch_and_overlap(project_root):
    backend = _backend(project_root)
    gap = backend.bands["initial_gap_m"].nominal
    clearance = backend.detect(gap * 0.5, gap * 0.5)
    assert clearance.state == "NO_CONTACT"
    assert clearance.contact_state_updated is False
    touch = backend.detect(gap, gap)
    assert all(pad.penetration_m == 0.0 for pad in touch.pads)
    overlap = backend.detect(gap + 1.0e-3, gap + 1.0e-3)
    assert overlap.state == "CONTACT"
    assert overlap.contact_state_updated is True
    expected_force = 2.0 * 1.0e6 * (1.0e-3 ** 1.5)
    assert overlap.total_normal_force_N == pytest.approx(expected_force, rel=1.0e-12)


def test_broken_detector_flagged_contact_detection_failure(project_root):
    backend = _backend(project_root)
    gap = backend.bands["initial_gap_m"].nominal
    overlap = backend.detect(gap + 1.0e-3, gap + 1.0e-3)
    broken = BrokenContactDetector(backend).detect(gap + 1.0e-3, gap + 1.0e-3)
    audit = audit_detector_consistency(overlap, broken)
    assert audit["contact_detection_failure"] is True
    assert audit["reason_code"] == "CONTACT_DETECTION_FAILURE"


def test_malformed_inputs_rejected(project_root):
    backend = _backend(project_root)
    with pytest.raises(ContactEnvelopeError):
        backend.detect(float("nan"), 0.0)
    with pytest.raises(ContactEnvelopeError):
        backend.detect("left", 0.0)  # type: ignore[arg-type]


def test_out_of_envelope_maps_unknown_masks_to_abort(project_root):
    backend = _backend(project_root)
    update = backend.detect_fail_closed(
        backend.bands["stroke_m"].upper + 1.0e-6, 0.0
    )
    assert update.state == "UNKNOWN"
    assert update.reason_code.startswith("CONTACT_ENVELOPE_UNKNOWN_MASKS_TO_ABORT")


def test_missing_contact_model_source_rejected(project_root, tmp_path):
    with pytest.raises(ContactSourceError, match="DESIGN_CONTACT_MODEL_V1_SOURCE_MISSING"):
        NarrowPhaseContactBackend(
            project_root=project_root,
            contact_geometry=_geometry(),
            contact_model_path=tmp_path / "absent.yaml",
        )


def test_stale_contact_model_hash_rejected(project_root, tmp_path):
    source = project_root / CONTACT_MODEL_RELATIVE_PATH
    payload = bytearray(source.read_bytes())
    payload[-1] ^= 0x01
    tampered = tmp_path / "DESIGN_CONTACT_MODEL_V1.yaml"
    tampered.write_bytes(bytes(payload))
    with pytest.raises(ContactSourceError, match="DESIGN_CONTACT_MODEL_V1_HASH_DRIFT"):
        NarrowPhaseContactBackend(
            project_root=project_root,
            contact_geometry=_geometry(),
            contact_model_path=tampered,
        )


def test_malformed_or_drifted_geometry_rejected(project_root):
    geometry = _geometry()
    geometry["schema"] = "SIM13_V1_LEGACY_GEOMETRY"
    with pytest.raises(ContactSourceError, match="CONTACT_GEOMETRY_SCHEMA_OR_CLASS_DRIFT"):
        NarrowPhaseContactBackend(
            project_root=project_root, contact_geometry=geometry
        )
    geometry = _geometry()
    geometry["provenance"]["design_contact_model_v1_sha256"] = "0" * 64
    with pytest.raises(ContactSourceError, match="CONTACT_GEOMETRY_PROVENANCE_DRIFT"):
        NarrowPhaseContactBackend(
            project_root=project_root, contact_geometry=geometry
        )


def test_deterministic_replay_identical_updates(project_root):
    backend = _backend(project_root)
    gap = backend.bands["initial_gap_m"].nominal
    first = backend.detect(gap + 1.0e-3, gap + 1.0e-3)
    second = backend.detect(gap + 1.0e-3, gap + 1.0e-3)
    assert first == second


def test_backend_is_read_only(project_root):
    targets = [project_root / CONTACT_MODEL_RELATIVE_PATH, GEOMETRY_PATH]
    before = {path: path.read_bytes() for path in targets}
    backend = _backend(project_root)
    gap = backend.bands["initial_gap_m"].nominal
    backend.detect(gap + 1.0e-3, gap + 1.0e-3)
    build_validation_receipt(backend, geometry_record={"path": "x", "bytes": 0, "sha256": "0" * 64})
    after = {path: path.read_bytes() for path in targets}
    assert before == after
