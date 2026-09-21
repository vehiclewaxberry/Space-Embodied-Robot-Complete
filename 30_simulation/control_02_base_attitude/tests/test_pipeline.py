"""End-to-end gate generation."""
from run_gates import main


def test_pipeline_generates_machine_gate():
    out = main()
    assert out["verdict"] in ("PASS", "REPEAT", "BLOCKED")
    assert out["verdict"] != "BLOCKED", out.get("blocked_reason")
    return 0.0 if out["verdict"] == "PASS" else 1.0
