from __future__ import annotations

from pathlib import Path

from sim13_v3.source_model import read_only_current_system_records


def test_current_system_records_are_read_only_hashes_not_solver_inputs():
    records = read_only_current_system_records()
    assert len(records) == 4
    assert all(record["bytes"] > 0 for record in records)
    assert all(len(record["sha256"]) == 64 for record in records)


def test_no_unified_builder_or_generation_call_in_v3_runtime_modules():
    package = Path(__file__).resolve().parents[1] / "sim13_v3"
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(package.glob("*.py"))
    )
    forbidden_call_fragments = ("._build_robot(", ".gen_urdf(")
    assert all(fragment not in runtime_text for fragment in forbidden_call_fragments)

