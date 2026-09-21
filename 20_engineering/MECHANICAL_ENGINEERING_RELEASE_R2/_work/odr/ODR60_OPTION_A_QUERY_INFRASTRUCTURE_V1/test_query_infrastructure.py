import hashlib
import importlib.util
import inspect
import json
import math
from pathlib import Path
import sys
import tempfile


HERE = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ADAPTER = _load("odr60_exact_q_adapter", "exact_q_trace_adapter.py")
EDGE = _load("odr60_continuous_edge", "continuous_edge_certificate.py")


def test_frozen_v9f_static_audit_passes_without_geometry_execution():
    result = ADAPTER.static_audit_frozen_v9f()
    assert result["pass"] is True
    assert result["current_geometry_loaded"] is False
    assert result["exact_q_query_executed"] is False
    assert result["scope"] == "ROUTE_C_HARNESS_POINTWISE_MESH_CLEARANCE_ONLY"
    assert result["complete_system_collision"] is False
    assert result["v2_base_link_operational_proxy_bound"] is False
    assert result["accepted_run_authority_pin_present"] is False
    assert result["current_exact_q_execution_admitted"] is False
    assert result["path_search_executed"] is False
    assert result["source"]["sha256"] == ADAPTER.V9F_SOURCE_SHA256


def test_trace_capture_calls_local_query_once_and_prevents_all_declared_writes():
    with tempfile.TemporaryDirectory(prefix="odr60_trace_", dir=HERE) as temp_dir:
        temp_path = Path(temp_dir)
        sweep = temp_path / "sweep.json"
        ledger = temp_path / "ledger.json"
        gate = temp_path / "gate.json"
        fixture = temp_path / "fixture_evaluator.py"
        fixture.write_text(
        """
import math
OUT_SWEEP = r'%s'
OUT_LEDGER = r'%s'
OUT_GATE = r'%s'
class Arm:
    rev = [
        {'name': 'joint1', 'lo': -3.0, 'hi': 3.0},
        {'name': 'joint2', 'lo': -3.0, 'hi': 3.0},
        {'name': 'joint3', 'lo': -3.0, 'hi': 3.0},
        {'name': 'joint4', 'lo': -3.0, 'hi': 3.0},
        {'name': 'joint5', 'lo': -3.0, 'hi': 3.0},
        {'name': 'joint6', 'lo': -3.0, 'hi': 3.0},
    ]
def main():
    arm = Arm()
    calls = []
    def eval_clearance(q, pinch_only=False):
        calls.append(tuple(q))
        return {
            'clearance': 2.0,
            'clearance_raw': 3.0,
            'detail': {'field': 'synthetic'},
            'pinch': {j['name']: 4.0 for j in arm.rev},
            'comparison_counts': {'total': 1},
        }
    own_best_global = 1.5
    own_detail_global = {'field': 'synthetic-own-host'}
    own_pinch = {j['name']: 3.0 for j in arm.rev}
    own_clearance_comparison_count = 2
    def run_mission(step):
        return {'unexpected': True}
    MAX_DQ_STEP = 0.1
    m_nom = run_mission(MAX_DQ_STEP)
    with open(OUT_SWEEP, 'w') as stream:
        stream.write('forbidden')
    with open(OUT_LEDGER, 'w') as stream:
        stream.write('forbidden')
    with open(OUT_GATE, 'w') as stream:
        stream.write('forbidden')
""" % (sweep, ledger, gate),
            encoding="utf-8",
        )
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest().upper()
        result = ADAPTER._capture_main_local_query(
            fixture, digest, [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        )
        assert result["query_valid"] is True
        assert result["result"]["clearance"] == 1.5
        assert result["result"]["limiting_class"] == "POSE_INVARIANT_OWN_HOST"
        assert result["result"]["comparison_counts"][
            "total_including_pose_invariant_own_host"
        ] == 3
        assert result["adapter_execution"][
            "declared_output_artifacts_unchanged_during_main_before_capture"
        ] is True
        assert "NOT_A_PROOF_OF_ZERO_UNDECLARED" in result["adapter_execution"][
            "side_effect_claim_scope"
        ]
        core = dict(result)
        core.pop("adapter_execution")
        core.pop("adapter_query_receipt_sha256")
        assert core["core_result_sha256"] == ADAPTER._canonical_sha256(
            core, {"core_result_sha256"}
        )
        assert result["adapter_query_receipt_sha256"] == ADAPTER._canonical_sha256(
            result, {"adapter_query_receipt_sha256"}
        )
        assert result["complete_system_collision"] is False
        assert result["continuous_edge_evaluated"] is False
        assert result["geometry_authority_limits"][
            "v2_base_link_operational_proxy_bound"
        ] is False
        assert not sweep.exists() and not ledger.exists() and not gate.exists()


def test_current_query_rejects_absent_authority_before_geometry_import():
    parameters = inspect.signature(ADAPTER.evaluate_frozen_v9f_exact_q).parameters
    assert "memory_gate_passed" not in parameters
    assert "execution_authority_token" not in parameters
    assert "low_memory_owner_override_token" not in parameters
    try:
        ADAPTER.evaluate_frozen_v9f_exact_q(
            [0.0] * 6,
            run_id="synthetic-denied",
        )
    except ADAPTER.ExactQAuthorityError as exc:
        assert "hash-bound" in str(exc)
    else:
        raise AssertionError("authority failure was not fail-closed")


def test_hash_bound_run_admission_computes_memory_gate_and_requires_single_run_override():
    root = ADAPTER.workspace_root()
    saved = (
        ADAPTER.ACCEPTED_OWNER_AUTHORITY_RECEIPT_REL,
        ADAPTER.ACCEPTED_OWNER_AUTHORITY_RECEIPT_SHA256,
        ADAPTER.ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_REL,
        ADAPTER.ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_SHA256,
    )
    with tempfile.TemporaryDirectory(prefix="odr60_authority_", dir=HERE) as temp_dir:
        temp_path = Path(temp_dir)
        nonce = "A" * 32
        authority_path = temp_path / "authority.json"
        authority_path.write_text(
            json.dumps(
                {
                    "schema": ADAPTER.OWNER_AUTHORITY_SCHEMA,
                    "decision_id": "ODR-60",
                    "decision_token": ADAPTER.OWNER_OPTION_A_DECISION_TOKEN,
                    "owner_approved": True,
                    "run_id": "SYNTHETIC_RUN_1",
                    "execution_scope": (
                        "READ_ONLY_SINGLE_POSE_LEGACY_V9F_LOCAL_HARNESS_QUERY"
                    ),
                    "single_run_only": True,
                    "single_use_nonce": nonce,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        ADAPTER.ACCEPTED_OWNER_AUTHORITY_RECEIPT_REL = authority_path.relative_to(root)
        ADAPTER.ACCEPTED_OWNER_AUTHORITY_RECEIPT_SHA256 = hashlib.sha256(
            authority_path.read_bytes()
        ).hexdigest().upper()
        ADAPTER.ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_REL = None
        ADAPTER.ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_SHA256 = None
        try:
            nominal = ADAPTER._validate_current_run_admission(
                "SYNTHETIC_RUN_1", 7.0
            )
            assert nominal["memory_gate_passed"] is True
            assert nominal["owner_override_used"] is False

            try:
                ADAPTER._validate_current_run_admission("SYNTHETIC_RUN_1", 1.0)
            except ADAPTER.ExactQAuthorityError as exc:
                assert "override" in str(exc)
            else:
                raise AssertionError("low memory ran without a hash-bound override")

            override_path = temp_path / "override.json"
            override_path.write_text(
                json.dumps(
                    {
                        "schema": ADAPTER.LOW_MEMORY_OVERRIDE_SCHEMA,
                        "run_id": "SYNTHETIC_RUN_1",
                        "owner_approved": True,
                        "override_token": ADAPTER.LOW_MEMORY_OVERRIDE_TOKEN,
                        "risk_acknowledged": True,
                        "memory_gate_passed": False,
                        "owner_override_used": True,
                        "single_use_nonce": nonce,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            ADAPTER.ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_REL = (
                override_path.relative_to(root)
            )
            ADAPTER.ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_SHA256 = hashlib.sha256(
                override_path.read_bytes()
            ).hexdigest().upper()
            overridden = ADAPTER._validate_current_run_admission(
                "SYNTHETIC_RUN_1", 1.0
            )
            assert overridden["memory_gate_passed"] is False
            assert overridden["owner_override_used"] is True
            assert overridden["memory_status"].startswith("OWNER_OVERRIDE_LOW_MEMORY")
        finally:
            (
                ADAPTER.ACCEPTED_OWNER_AUTHORITY_RECEIPT_REL,
                ADAPTER.ACCEPTED_OWNER_AUTHORITY_RECEIPT_SHA256,
                ADAPTER.ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_REL,
                ADAPTER.ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_SHA256,
            ) = saved


def _bound(coefficient: float = 1.0):
    return EDGE.CertifiedJointLipschitzBound(
        coefficients_mm_per_coordinate=(coefficient,),
        source_id="SYNTHETIC_PROOF_FIXTURE",
        source_sha256="A" * 64,
    )


def test_continuous_edge_certifies_safe_constant_clearance():
    result = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 3.0},
        motion_bound=_bound(1.0),
        required_clearance_mm=0.5,
    )
    assert result["status"] == EDGE.SAFE
    assert result["certified_leaf_count"] == 1
    assert result["sample_count"] == 3
    assert result["path_search_authorized"] is False


def test_continuous_edge_finds_midpoint_collision_witness():
    result = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda q: {
            "status": "PASS",
            "clearance_mm": abs(q[0] - 0.5) - 0.1,
            "witness": "synthetic_midpoint",
        },
        motion_bound=_bound(1.0),
    )
    assert result["status"] == EDGE.UNSAFE
    assert result["unsafe_witness"]["q"] == [0.5]
    assert result["unsafe_witness"]["witness"] == "synthetic_midpoint"


def test_continuous_edge_recursion_finds_quarter_point_collision():
    result = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda q: {
            "status": "PASS",
            "clearance_mm": abs(q[0] - 0.25) - 0.02,
            "witness": "synthetic_quarter_point",
        },
        motion_bound=_bound(1.0),
    )
    assert result["status"] == EDGE.UNSAFE
    assert result["unsafe_witness"]["q"] == [0.25]
    assert result["unsafe_witness"]["witness"] == "synthetic_quarter_point"


def test_continuous_edge_unknown_is_never_safe():
    missing_bound = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 10.0},
        motion_bound=None,
    )
    assert missing_bound["status"] == EDGE.UNKNOWN
    assert missing_bound["sample_count"] == 0

    unknown_oracle = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "UNKNOWN", "clearance_mm": None},
        motion_bound=_bound(),
    )
    assert unknown_oracle["status"] == EDGE.UNKNOWN
    assert unknown_oracle["next_stage_authorized"] is False


def test_continuous_edge_exhaustion_returns_unknown_not_safe():
    result = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 0.1},
        motion_bound=_bound(100.0),
        max_depth=2,
        minimum_joint_span=0.0,
    )
    assert result["status"] == EDGE.UNKNOWN
    assert result["reason"] == "MAX_RECURSION_DEPTH_WITHOUT_CERTIFICATE"
    assert result["unknown_is_never_safe"] is True


def test_threshold_contact_and_numerical_reserve_are_not_safe():
    contact = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 0.0},
        motion_bound=_bound(0.0),
    )
    assert contact["status"] == EDGE.UNSAFE
    assert contact["threshold_contact_is_never_safe"] is True

    reserve = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 0.1},
        motion_bound=_bound(0.0),
        numerical_reserve_mm=0.1,
    )
    assert reserve["status"] == EDGE.UNSAFE


def test_relative_motion_bound_uses_both_object_contributions():
    # Synthetic per-object coefficients 2 and 3 mm/rad are deliberately summed
    # into the certified relative coefficient 5 mm/rad.  A one-sided value
    # would incorrectly certify the root interval.
    result = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 2.1},
        motion_bound=_bound(2.0 + 3.0),
        max_depth=0,
    )
    assert result["status"] == EDGE.UNKNOWN
    assert result["reason"] == "MAX_RECURSION_DEPTH_WITHOUT_CERTIFICATE"


def test_oracle_exception_nan_and_invalid_bound_fail_closed():
    def raising_oracle(_q):
        raise RuntimeError("synthetic")

    exception = EDGE.certify_linear_joint_edge(
        [0.0], [1.0], oracle=raising_oracle, motion_bound=_bound()
    )
    assert exception["status"] == EDGE.UNKNOWN
    assert exception["reason"] == "ORACLE_EXCEPTION_RuntimeError"

    nonfinite = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": math.nan},
        motion_bound=_bound(),
    )
    assert nonfinite["status"] == EDGE.UNKNOWN
    assert nonfinite["reason"] == "ORACLE_CLEARANCE_NONFINITE"

    invalid_bound = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 10.0},
        motion_bound=EDGE.CertifiedJointLipschitzBound(
            coefficients_mm_per_coordinate=(math.nan,),
            source_id="SYNTHETIC_INVALID",
            source_sha256="A" * 64,
        ),
    )
    assert invalid_bound["status"] == EDGE.UNKNOWN
    assert "BOUND_COEFFICIENT_NONFINITE_OR_NEGATIVE" in invalid_bound["bound_issues"]


def test_oracle_fail_with_positive_clearance_can_never_certify_safe():
    result = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {
            "status": "FAIL",
            "clearance_mm": 10.0,
            "reason": "SYNTHETIC_ORACLE_FAIL",
        },
        motion_bound=_bound(0.0),
    )
    assert result["status"] == EDGE.UNSAFE
    assert result["reason"] == "SYNTHETIC_ORACLE_FAIL"


def test_negative_required_clearance_is_rejected_and_negative_gap_never_safe():
    try:
        EDGE.certify_linear_joint_edge(
            [0.0],
            [1.0],
            oracle=lambda _q: {"status": "PASS", "clearance_mm": -1.0},
            motion_bound=_bound(0.0),
            required_clearance_mm=-2.0,
        )
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("negative required clearance was accepted")

    result = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": -1.0},
        motion_bound=_bound(0.0),
    )
    assert result["status"] == EDGE.UNSAFE


def test_non_numeric_oracle_and_bound_values_fail_closed():
    oracle = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": "bad"},
        motion_bound=_bound(),
    )
    assert oracle["status"] == EDGE.UNKNOWN
    assert oracle["reason"] == "ORACLE_CLEARANCE_NOT_NUMERIC"

    bound = EDGE.certify_linear_joint_edge(
        [0.0],
        [1.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 10.0},
        motion_bound=EDGE.CertifiedJointLipschitzBound(
            coefficients_mm_per_coordinate=("bad",),
            source_id="SYNTHETIC_INVALID",
            source_sha256="A" * 64,
        ),
    )
    assert bound["status"] == EDGE.UNKNOWN
    assert "BOUND_COEFFICIENT_NOT_NUMERIC" in bound["bound_issues"]


def _system_bound(**overrides):
    values = {
        "coefficients_mm_per_coordinate": (5.0,),
        "source_id": "SYNTHETIC_SYSTEM_PAIR_BOUND",
        "source_sha256": "1" * 64,
        "authority_class": "CERTIFIED_GEOMETRY_RELATIVE_MOTION_BOUND",
        "pair_id": "PAIR::A::B",
        "object_a_id": "A",
        "object_b_id": "B",
        "object_a_geometry_sha256": "2" * 64,
        "object_b_geometry_sha256": "3" * 64,
        "scene_state_sha256": "4" * 64,
        "acm_sha256": "5" * 64,
        "oracle_implementation_sha256": "6" * 64,
        "joint_coordinate_units": ("rad",),
        "q_domain_lower": (-1.0,),
        "q_domain_upper": (1.0,),
    }
    values.update(overrides)
    return EDGE.CertifiedJointLipschitzBound(**values)


def test_system_bound_requires_full_pair_geometry_scene_acm_oracle_and_domain_binding():
    missing = EDGE.certify_linear_joint_edge(
        [0.0],
        [0.5],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 10.0},
        motion_bound=EDGE.CertifiedJointLipschitzBound(
            coefficients_mm_per_coordinate=(1.0,),
            source_id="INCOMPLETE_SYSTEM_BOUND",
            source_sha256="A" * 64,
            authority_class="CERTIFIED_GEOMETRY_RELATIVE_MOTION_BOUND",
        ),
    )
    assert missing["status"] == EDGE.UNKNOWN
    assert "PAIR_ID_ABSENT" in missing["bound_issues"]
    assert "ORACLE_IMPLEMENTATION_SHA256_INVALID" in missing["bound_issues"]

    outside = EDGE.certify_linear_joint_edge(
        [0.0],
        [2.0],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 10.0},
        motion_bound=_system_bound(),
    )
    assert outside["status"] == EDGE.UNKNOWN
    assert "EDGE_ENDPOINT_OUTSIDE_CERTIFIED_Q_DOMAIN" in outside["bound_issues"]

    complete = EDGE.certify_linear_joint_edge(
        [0.0],
        [0.5],
        oracle=lambda _q: {"status": "PASS", "clearance_mm": 10.0},
        motion_bound=_system_bound(),
    )
    assert complete["status"] == EDGE.SAFE
    assert complete["certificate_scope"] == (
        "CERTIFIED_GEOMETRY_RELATIVE_MOTION_BOUND"
    )
    assert complete["motion_bound"]["pair_binding"]["pair_id"] == "PAIR::A::B"


def test_continuous_certificate_is_deterministic_json():
    kwargs = {
        "oracle": lambda q: {"status": "PASS", "clearance_mm": 4.0 + q[0]},
        "motion_bound": _bound(1.0),
        "required_clearance_mm": 0.25,
        "numerical_reserve_mm": 0.05,
    }
    first = EDGE.certify_linear_joint_edge([0.0], [1.0], **kwargs)
    second = EDGE.certify_linear_joint_edge([0.0], [1.0], **kwargs)
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )
