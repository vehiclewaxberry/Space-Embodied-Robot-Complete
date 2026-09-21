from __future__ import annotations

from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

import audit_task_space_metric as audit


def test_fixed_source_lock_has_all_three_ledgers():
    lock = audit.load(audit.LOCK_PATH)
    assert lock["candidate_pin_count"] == 13
    assert lock["direct_source_pin_count"] == 7
    assert lock["parent_transitive_source_pin_count"] == 24
    assert all(audit.pin_matches(pin) for name in ("candidate_pins", "direct_source_pins", "parent_transitive_source_pins") for pin in lock[name])


def test_external_audit_recomputes_and_remains_fail_closed():
    receipt = audit.validate()
    assert receipt["all_pass"] is True
    assert receipt["passed"] == receipt["total"] == 14
    assert receipt["negative_controls"]["passed"] == receipt["negative_controls"]["total"] == 40
    assert list(receipt["recomputed_candidate_checks"]) == audit.load(audit.LOCK_PATH)["audit_semantic_profile"]["expected_candidate_checks"]
    assert all(receipt["recomputed_candidate_checks"].values())
    assert receipt["recomputed"]["synthetic_nonidentity_S_q"]["pass"] is True
    assert all(row["physical_urdf_reassembly"]["represented_mass_vs_1000x_kg_relative"] <= 1e-12 for row in receipt["recomputed"]["kilogram_gram_independent_reload"].values())
    assert receipt["truthful_gram_test_method"] == "IN_MEMORY_URDF_ALL_LINK_MASS_AND_INERTIA_X1000__URDF_TREE_DYNAMICS_REASSEMBLY"
    assert abs(receipt["recomputed"]["gram_source_audit"]["first_inertial_link_mass_ratio"] - 1000.0) <= 1e-12
    assert receipt["recomputed"]["gram_source_audit"]["xml_hashes_differ"] is True
    assert receipt["recomputed"]["gram_source_audit"]["temporary_file_created"] is False
    assert receipt["parent_control_gate_reissued"] is False
    assert receipt["collision_valid"] is False
    assert receipt["m01_path_bound"] is False
    assert receipt["safe_review_pass"] is False
    assert receipt["time_domain_tracking_executed"] is False
    assert receipt["hardware_valid"] is False
    assert receipt["next_stage_authorized"] is False
    assert receipt["release_credit"] is False


def test_external_audit_inventory_rejects_missing_and_extra_files():
    exact = set(audit.ALLOWED_AUDIT_FILES)
    assert audit.audit_inventory_exact(exact)
    missing_readme = exact - {"README.md"}
    assert not audit.audit_inventory_exact(missing_readme)
    assert not audit.audit_inventory_exact(exact | {"UNDECLARED_EXTRA.txt"})
