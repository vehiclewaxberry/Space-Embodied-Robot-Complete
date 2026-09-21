from __future__ import annotations

from pathlib import Path

import pytest

from r2_preflight.negative_controls import (
    NEGATIVE_CONTROL_IDS,
    RUNTIME_DEPENDENT,
    STRUCTURAL_SIGNATURE_ONLY,
    build_negative_control_evidence,
)
from r2_preflight.strict_json import canonical_bytes


@pytest.fixture(scope="module")
def nc_evidence(project_root: Path, package_root: Path, donor):
    return build_negative_control_evidence(
        project_root=project_root,
        package_root=package_root,
        donor=donor,
        source_inventory_sha256="0" * 64,
    )


def test_negative_control_inventory_exact(nc_evidence) -> None:
    assert len(NEGATIVE_CONTROL_IDS) == len(set(NEGATIVE_CONTROL_IDS)) == 46
    assert [row["id"] for row in nc_evidence["controls"]] == list(NEGATIVE_CONTROL_IDS)
    assert nc_evidence["registered_count"] == 46
    assert nc_evidence["implemented_count"] == 46
    assert nc_evidence["source_only_executed_count"] == 46
    assert nc_evidence["killed_count"] == 46
    assert nc_evidence["source_only_negative_controls_implemented"] is True
    assert nc_evidence["source_only_negative_controls_executed"] is True
    assert nc_evidence["source_only_negative_controls_killed"] is True
    assert nc_evidence["r2_execution_negative_controls_executed"] is False
    assert nc_evidence["r2_numerical_preflight_executed"] is False
    assert nc_evidence["r2_runtime_trajectory_evaluated"] is False
    assert nc_evidence["trajectory_count"] == 0


@pytest.mark.parametrize("control_id", NEGATIVE_CONTROL_IDS)
def test_each_registered_source_only_mutation_is_killed(control_id: str, nc_evidence) -> None:
    row = next(item for item in nc_evidence["controls"] if item["id"] == control_id)
    assert set(row) == {
        "id", "status", "implemented", "source_only_executed", "killed",
        "r2_runtime_trajectory_evaluated", "fixture_class", "witness",
        "implementation_sha256",
    }
    assert row["implemented"] is True
    assert row["source_only_executed"] is True
    assert row["killed"] is True
    assert row["r2_runtime_trajectory_evaluated"] is False
    assert row["fixture_class"] == "SOURCE_ONLY_SYNTHETIC_MUTATION"
    assert isinstance(row["witness"], str) and len(row["witness"]) >= 8
    assert len(row["implementation_sha256"]) == 64
    if control_id in STRUCTURAL_SIGNATURE_ONLY:
        assert row["status"] == "STRUCTURAL_SOURCE_SIGNATURE_KILLED"
    elif control_id in RUNTIME_DEPENDENT:
        assert row["status"] == "SOURCE_ONLY_MUTATION_KILLED_RUNTIME_NOT_EVALUATED"
    else:
        assert row["status"] == "SOURCE_ONLY_MUTATION_KILLED"


def test_negative_control_evidence_builder_is_deterministic(
    nc_evidence, project_root: Path, package_root: Path, donor
) -> None:
    repeated = build_negative_control_evidence(
        project_root=project_root,
        package_root=package_root,
        donor=donor,
        source_inventory_sha256="0" * 64,
    )
    assert canonical_bytes(repeated) == canonical_bytes(nc_evidence)
