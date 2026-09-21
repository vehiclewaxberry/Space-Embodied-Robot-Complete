#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Derive DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml from V1 + ODR-07.

ODR-07 rules that a component-level inertia "standard uncertainty" must not be
rotated component-wise the way an inertia tensor is; a COVARIANCE must be
propagated instead. That is an amendment of the declared uncertainty POLICY, so
it is recorded in the policy file (the uncertainty SSOT), not only in the
consuming artifact.

The V2 policy is generated from the V1 policy dictionary so that every numeric
class value is provably carried over unchanged:

  * source_classes                 must be identical to V1 (asserted)
  * component_quantity_class_map   must be identical to V1 (asserted)
  * rules P1..P8                   carried verbatim; P9 is added
  * V1 is NOT modified; it stays on disk and is pinned here by sha256+bytes

Nothing here is a measurement. All uncertainties remain declared Type-B
engineering assignments, PENDING_CALIBRATION.
"""
from __future__ import annotations

import copy
import hashlib
import os
import subprocess
from pathlib import Path

import yaml

WP2 = Path(__file__).resolve().parent
M7 = WP2.parent
WORKSPACE = M7.parents[1]
V1_PATH = WP2 / "DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml"
V2_PATH = WP2 / "DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml"
CONTRACT_PATH = M7 / "00_authority/M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml"
ODR_PATH = M7 / "00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml"


def hb(path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return {
        "path": path.relative_to(WORKSPACE).as_posix(),
        "sha256": digest.hexdigest().upper(),
        "bytes": size,
    }


def now_local() -> str:
    return subprocess.check_output(["date", "-Iseconds"]).decode().strip()


def main() -> None:
    v1 = yaml.safe_load(open(V1_PATH, encoding="utf-8"))
    out = copy.deepcopy(v1)

    out["schema"] = "M7_DESIGN_MASS_UNCERTAINTY_POLICY_V2"
    out["generated_local"] = now_local()
    out["generated_clock_source"] = "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08"
    out["supersedes"] = {
        **hb(V1_PATH),
        "reason": (
            "ODR-07 (WP2-AUD-02): the V1 policy declared the per-class standard "
            "uncertainty inputs (rules P5/P7) but never declared how an "
            "uncertainty transforms under a component-to-S frame rotation. The "
            "consuming aggregator therefore rotated the standard-uncertainty "
            "matrix component-wise like an inertia tensor, which produced 44 "
            "negative entries in 11 component records. V2 adds rule P9 "
            "(covariance propagation) and the required check set. No class "
            "value, no rule P1..P8 text and no class map entry changed."
        ),
        "v1_status_after_this_issue": "SUPERSEDED_FOR_UNCERTAINTY_FRAME_TRANSFORMATION_SEMANTICS_ONLY",
    }
    out["status"] = "ACTIVE_DECLARED_ENGINEERING_POLICY_PENDING_CALIBRATION"

    out["authority_basis"] = list(v1["authority_basis"]) + [
        "ODR-07: component inertia uncertainty is propagated as a COVARIANCE "
        "(C_global = T(R) C_local T(R)^T); reported per-component standard "
        "uncertainties are sigma_i = sqrt(C_global[i,i]) and are non-negative; "
        "abs(), clipping to zero and deletion of entries are forbidden "
        "remediations"
    ]

    out["policy_rules"] = list(v1["policy_rules"]) + [
        {
            "rule_id": "P9_UNCERTAINTY_UNDER_FRAME_ROTATION_IS_A_COVARIANCE",
            "statement": (
                "An inertia standard uncertainty is a non-negative magnitude and "
                "MUST NOT be rotated component-wise the way an inertia tensor is. "
                "When a component tensor is expressed in a rotated frame "
                "(I_S = R I_local R^T), the associated uncertainty is transformed "
                "as a covariance of the six independent tensor components: "
                "C_global = T(R) C_local T(R)^T, where T(R) is the 6x6 linear map "
                "induced by R on the component vector [Ixx,Iyy,Izz,Ixy,Ixz,Iyz] of "
                "a symmetric second-order tensor. Off-diagonal entries of "
                "C_global are covariances and MAY legitimately be negative. The "
                "reported per-component standard uncertainties are "
                "sigma_i = sqrt(C_global[i,i]) and are therefore non-negative by "
                "construction. Because the map is exactly linear, this is an "
                "exact propagation of the declared inputs, not a first-order "
                "approximation."
            ),
            "declared_input_covariance": (
                "C_local = diag(u(Ixx)^2, u(Iyy)^2, u(Izz)^2, u(Ixy)^2, u(Ixz)^2, "
                "u(Iyz)^2) with the u() values from rule P7 evaluated in the "
                "component source frame. The input covariance is DIAGONAL because "
                "rule P8 declares component quantities uncorrelated; no "
                "correlation data exists anywhere in the input chain, so inventing "
                "off-diagonal input correlations is forbidden (fail-closed). Any "
                "off-diagonal entry appearing in C_global is therefore rotation-"
                "induced correlation, which is a real statistical consequence of "
                "changing frame."
            ),
            "forbidden_remediations": [
                "abs(rotated_uncertainty_matrix)",
                "clipping negative entries to zero",
                "deleting the offending entries",
                "reporting a rotated standard-uncertainty matrix as if it were a covariance",
            ],
            "forbidden_remediation_rationale": (
                "Taking absolute values, clipping or deleting destroys the "
                "statistical meaning of the covariance and converts a real "
                "finding into a fabricated PASS (ODR-07)."
            ),
            "required_checks_per_component_record": [
                "covariance_symmetric",
                "covariance_positive_semidefinite",
                "variance_diagonal_nonnegative",
                "reported_sigma_nonnegative",
            ],
            "data_structure_required_in_consumers": {
                "inertia_uncertainty": {
                    "covariance_matrix": "SIGNED_OFF_DIAGONAL_ALLOWED",
                    "component_standard_uncertainty": ["Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"],
                }
            },
            "relation_to_P5": (
                "P5 governs the CONFIGURATION level: a numerical central-difference "
                "Jacobian of the full aggregation chain already handles the frame "
                "rotation correctly, so configuration-level standard uncertainties "
                "were never affected by the defect. P9 governs the reported "
                "COMPONENT level, where the defect occurred."
            ),
        }
    ]

    out["covariance_semantics"] = {
        "component_vector_order": ["Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"],
        "induced_map_definition": (
            "T(R)[:,k] = comp6(R E_k R^T) with the symmetric basis "
            "E_1=e1e1^T, E_2=e2e2^T, E_3=e3e3^T, E_4=e1e2^T+e2e1^T, "
            "E_5=e1e3^T+e3e1^T, E_6=e2e3^T+e3e2^T and "
            "comp6(M)=[M00,M11,M22,M01,M02,M12]; then comp6(R I R^T) = T(R) comp6(I) "
            "exactly for every symmetric I."
        ),
        "reported_sigma_definition": "sigma_i = sqrt(C_global[i,i])",
        "off_diagonal_sign": "SIGNED_COVARIANCE_NEGATIVE_ALLOWED",
        "diagonal_sign": "VARIANCE_NON_NEGATIVE_REQUIRED",
        "special_case_note": (
            "Every component-to-S rotation used in the current M7 design "
            "(panel deployed/stowed, target capture poses) is a SIGNED PERMUTATION "
            "matrix, so T(R) is also a signed permutation and T(R) C_local T(R)^T "
            "stays exactly diagonal. For this specific data set the "
            "covariance-derived sigma therefore coincides numerically with the "
            "magnitude of the V1 rotated entries. That coincidence is a property "
            "of these transforms, NOT of the method: for a general rotation the "
            "covariance-derived sigma differs from abs(R U R^T), and the "
            "implementation is required to demonstrate that difference on a "
            "generic rotation (method-discrimination test) so that the fix cannot "
            "be mistaken for, or degenerate into, the forbidden abs() remediation."
        ),
    }

    out["uncertainty_model"] = dict(v1["uncertainty_model"])
    out["uncertainty_model"]["component_frame_transformation"] = (
        "COVARIANCE_C_GLOBAL_EQ_T_R_C_LOCAL_T_R_TRANSPOSE_PER_P9"
    )
    out["uncertainty_model"]["reported_component_sigma"] = "SQRT_OF_COVARIANCE_DIAGONAL"
    out["uncertainty_model"]["component_input_covariance"] = "DIAGONAL_INDEPENDENCE_DECLARED_P8"

    out["prohibitions"] = list(v1["prohibitions"]) + [
        "DO_NOT_ROTATE_A_STANDARD_UNCERTAINTY_MATRIX_COMPONENT_WISE",
        "DO_NOT_ABS_CLIP_OR_DELETE_A_NEGATIVE_COVARIANCE_ENTRY",
        "DO_NOT_INVENT_INPUT_CORRELATIONS_NO_CALIBRATION_DATA_EXISTS",
    ]

    # source register: carry V1 entries, add byte sizes, add the ODR-07 authority
    sr = {}
    for key, rec in v1["source_register"].items():
        path = WORKSPACE / rec["path"]
        fresh = hb(path)
        if fresh["sha256"] != rec["sha256"].upper():
            raise SystemExit(
                f"FAIL-CLOSED: {key} sha256 drift, V1 policy pinned "
                f"{rec['sha256']} but disk has {fresh['sha256']}"
            )
        sr[key] = fresh
    sr["m7_terminal_closure_contract"] = hb(CONTRACT_PATH)
    sr["design_mass_uncertainty_policy_v1_superseded"] = hb(V1_PATH)
    out["source_register"] = sr
    out["policy_builder"] = {
        "path": Path(__file__).resolve().relative_to(WORKSPACE).as_posix(),
        "note": "regenerate with: python <this file>",
    }

    # provable carry-over of every numeric class value
    assert out["source_classes"] == v1["source_classes"], "source class values must not change"
    assert out["component_quantity_class_map"] == v1["component_quantity_class_map"]
    assert out["policy_rules"][:8] == v1["policy_rules"], "rules P1..P8 must be verbatim"

    with open(V2_PATH, "w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(out, handle, sort_keys=False, allow_unicode=True, width=100)

    print("WROTE", V2_PATH, os.path.getsize(V2_PATH), "bytes")
    print("source_classes identical to V1:", out["source_classes"] == v1["source_classes"])
    print("rules:", [r["rule_id"] for r in out["policy_rules"]])


if __name__ == "__main__":
    main()
