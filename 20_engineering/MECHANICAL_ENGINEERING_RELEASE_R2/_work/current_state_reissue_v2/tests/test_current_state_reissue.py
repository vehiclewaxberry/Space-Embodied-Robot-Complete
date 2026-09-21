from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from build_current_state_reissue import (
    GATE_NAME,
    INPUT_NAME,
    PACKAGE_NAME,
    PACKAGE_REL,
    SOURCE_SPECS,
    CurrentStateError,
    build_documents,
    strict_json_bytes,
    workspace_root,
    write_documents,
)
from validate_current_state_reissue import validate_package


LOCAL_FILES = (
    "README.md",
    "build_current_state_reissue.py",
    "validate_current_state_reissue.py",
    "tests/test_current_state_reissue.py",
)


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


@pytest.fixture
def staged() -> tuple[Path, Path]:
    real_root = workspace_root()
    base = real_root / PACKAGE_REL / ".test_tmp"
    base.mkdir(exist_ok=True)
    case_root = Path(tempfile.mkdtemp(prefix="c", dir=base))
    package = case_root / PACKAGE_REL
    package.mkdir(parents=True)
    try:
        for _source_id, rel, _role, _ceiling in SOURCE_SPECS:
            _copy_file(real_root / rel, case_root / rel)
        for rel in LOCAL_FILES:
            _copy_file(real_root / PACKAGE_REL / rel, package / rel)
        write_documents(build_documents(case_root, package), package)
        yield case_root, package
    finally:
        shutil.rmtree(case_root)
        try:
            base.rmdir()
        except OSError:
            pass


def _rewrite_json(path: Path, transform) -> None:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    transform(obj)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source(root: Path, source_id: str) -> Path:
    rel = next(row[1] for row in SOURCE_SPECS if row[0] == source_id)
    return root / rel


def test_positive_build_has_three_strict_layers(staged):
    _root, package = staged
    schemas = [
        strict_json_bytes((package / INPUT_NAME).read_bytes(), INPUT_NAME)["schema"],
        strict_json_bytes((package / GATE_NAME).read_bytes(), GATE_NAME)["schema"],
        strict_json_bytes((package / PACKAGE_NAME).read_bytes(), PACKAGE_NAME)["schema"],
    ]
    assert schemas == [
        "R2_CURRENT_STATE_INPUT_MANIFEST_V2",
        "R2_CURRENT_STATE_GATE_V2",
        "R2_CURRENT_STATE_PACKAGE_MANIFEST_V2",
    ]


def test_positive_validator_passes_22_checks(staged):
    root, package = staged
    result = validate_package(root, package)
    assert result["passed"] == result["total"] == 22
    assert result["source_count"] == 27


def test_positive_builder_is_byte_deterministic(staged):
    root, package = staged
    first = {name: (package / name).read_bytes() for name in (INPUT_NAME, GATE_NAME, PACKAGE_NAME)}
    second = build_documents(root, package)
    assert first == second


def test_positive_gate_has_28_true_checks(staged):
    _root, package = staged
    gate = json.loads((package / GATE_NAME).read_text(encoding="utf-8"))
    assert len(gate["checks"]) == 28
    assert all(gate["checks"].values())
    assert gate["summary"] == {"failed": [], "passed": 28, "total": 28}


def test_positive_all_generated_top_level_authority_flags_false(staged):
    _root, package = staged
    for name in (INPUT_NAME, GATE_NAME, PACKAGE_NAME):
        doc = json.loads((package / name).read_text(encoding="utf-8"))
        assert doc["next_stage_authorized"] is False
        assert doc["release_credit"] is False


def test_positive_package_manifest_excludes_itself(staged):
    _root, package = staged
    manifest = json.loads((package / PACKAGE_NAME).read_text(encoding="utf-8"))
    assert manifest["entry_count"] == 6
    assert all(not row["path"].endswith(PACKAGE_NAME) for row in manifest["package_entries"])


def test_negative_arbitrary_source_byte_tamper_fails(staged):
    root, package = staged
    path = _source(root, "terminal_release_sha256")
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(CurrentStateError):
        validate_package(root, package)


def test_negative_missing_source_fails(staged):
    root, package = staged
    _source(root, "m01_query_infrastructure_gate").unlink()
    with pytest.raises(CurrentStateError):
        validate_package(root, package)


def test_negative_duplicate_json_key_source_fails(staged):
    root, package = staged
    path = _source(root, "terminal_release_gate")
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("{", '{\n  "gate_a_pass": false,', 1), encoding="utf-8")
    with pytest.raises(CurrentStateError, match="duplicate JSON key"):
        build_documents(root, package)


def test_negative_baseline_self_defect_erasure_fails(staged):
    root, package = staged
    path = _source(root, "baseline_manifest_with_self_defect")
    original = path.read_bytes()
    actual_sha = __import__("hashlib").sha256(original).hexdigest().upper()
    actual_len = len(original)

    def edit(obj):
        row = next(row for row in obj["files"] if row["file"] == "01_BASELINE_MANIFEST.json")
        row["bytes"] = actual_len
        row["sha256"] = actual_sha

    _rewrite_json(path, edit)
    with pytest.raises(CurrentStateError, match="baseline .* defect disappeared"):
        build_documents(root, package)


def test_negative_route_c_witness_sign_change_fails(staged):
    root, package = staged
    path = _source(root, "route_c_m01_negative_witness")
    _rewrite_json(path, lambda obj: obj["witness"]["collision"].__setitem__("raw_clearance_mm", 0.01))
    with pytest.raises(CurrentStateError, match="raw penetration witness changed"):
        build_documents(root, package)


def test_negative_sim13_full_tmg6_promotion_fails(staged):
    root, package = staged
    path = _source(root, "sim13_post_terminal_backend_addendum")
    _rewrite_json(path, lambda obj: obj["lineage"].__setitem__("full_tmg6_reissue_executed", True))
    with pytest.raises(CurrentStateError, match="full TMG-6 unexpectedly reissued"):
        build_documents(root, package)


def test_negative_parent_dynamics_completion_fails(staged):
    root, package = staged
    path = _source(root, "parent_dynamics_engineering_gate")
    _rewrite_json(path, lambda obj: obj.__setitem__("dynamics_engineering_complete", True))
    with pytest.raises(CurrentStateError, match="parent dynamics unexpectedly complete"):
        build_documents(root, package)


def test_negative_dg3_parent_credit_fails(staged):
    root, package = staged
    path = _source(root, "dg3_candidate_gate")
    _rewrite_json(path, lambda obj: obj.__setitem__("parent_DG3_satisfied", True))
    with pytest.raises(CurrentStateError, match="DG3 parent unexpectedly satisfied"):
        build_documents(root, package)


def test_negative_dg4_physical_credit_fails(staged):
    root, package = staged
    path = _source(root, "dg4_candidate_gate")
    _rewrite_json(path, lambda obj: obj.__setitem__("physical_contact_ready", True))
    with pytest.raises(CurrentStateError, match="DG4 physical or parent authority inflated"):
        build_documents(root, package)


def test_negative_dg5_null_zero_fill_fails(staged):
    root, package = staged
    path = _source(root, "dg5_candidate_gate")
    _rewrite_json(path, lambda obj: obj.__setitem__("as_built_mass_properties", 0))
    with pytest.raises(CurrentStateError, match="zero-filled/invented"):
        build_documents(root, package)


def test_negative_v3_release_authority_fails(staged):
    root, package = staged
    path = _source(root, "digital_prototype_dynamics_entry_gate_v3")
    _rewrite_json(path, lambda obj: obj.__setitem__("next_stage_authorized", True))
    with pytest.raises(CurrentStateError, match="V3 authority inflated"):
        build_documents(root, package)


def test_negative_control_completion_fails(staged):
    root, package = staged
    path = _source(root, "parent_control_engineering_gate")
    _rewrite_json(path, lambda obj: obj.__setitem__("control_engineering_complete", True))
    with pytest.raises(CurrentStateError, match="parent control unexpectedly complete"):
        build_documents(root, package)


def test_negative_joint_ready_fails(staged):
    root, package = staged
    path = _source(root, "joint_dynamics_control_gate")
    _rewrite_json(path, lambda obj: obj.__setitem__("joint_system_ready", True))
    with pytest.raises(CurrentStateError, match="joint Gate unexpectedly ready"):
        build_documents(root, package)


def test_negative_historical_safe_authority_fails(staged):
    root, package = staged
    path = _source(root, "historical_safe00_gate")
    _rewrite_json(path, lambda obj: obj.__setitem__("next_stage_authorized", True))
    with pytest.raises(CurrentStateError, match="SAFE next stage unexpectedly true"):
        build_documents(root, package)


def test_negative_drawing_manufacturing_permission_fails(staged):
    root, package = staged
    path = _source(root, "l06_drawing_set_index")
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("PROHIBITED", "PERMITTED", 1), encoding="utf-8")
    with pytest.raises(CurrentStateError, match="no longer prohibit manufacturing"):
        build_documents(root, package)


def test_negative_d05_material_witness_erasure_fails(staged):
    root, package = staged
    path = _source(root, "l06_d05_stage_a")
    path.write_text(path.read_text(encoding="utf-8").replace("AL6061-T6 CANDIDATE", "AL7075-T651"), encoding="utf-8")
    with pytest.raises(CurrentStateError, match="SVG 6061 witness missing"):
        build_documents(root, package)


def test_negative_current_7075_selection_erasure_fails(staged):
    root, package = staged
    path = _source(root, "current_design_material_selection")
    text = path.read_text(encoding="utf-8")
    marker = "family_id: M3R_PRIMARY_STRUCTURE_STAGE_A_B"
    start = text.index(marker)
    end = text.index("family_id: GENERAL_BRACKETS_CAMERA_BRACKET_LOAD_BRIDGE")
    block = text[start:end].replace("PMAT-AL7075-T651-SHEET-PLATE", "PMAT-AL6061-T6-SHEET-PLATE")
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")
    with pytest.raises(CurrentStateError, match="7075-T651 selection missing"):
        build_documents(root, package)


def test_negative_input_manifest_extra_source_fails(staged):
    root, package = staged
    path = package / INPUT_NAME

    def edit(obj):
        obj["source_pins"].append(dict(obj["source_pins"][0], id="extra"))
        obj["source_count"] = 28

    _rewrite_json(path, edit)
    with pytest.raises(CurrentStateError):
        validate_package(root, package)


def test_negative_input_manifest_path_traversal_fails(staged):
    root, package = staged
    path = package / INPUT_NAME
    _rewrite_json(path, lambda obj: obj["source_pins"][0].__setitem__("path", "../escape.json"))
    with pytest.raises(CurrentStateError):
        validate_package(root, package)


def test_negative_gate_input_hash_tamper_fails(staged):
    root, package = staged
    path = package / GATE_NAME
    _rewrite_json(path, lambda obj: obj["input_manifest"].__setitem__("sha256", "0" * 64))
    with pytest.raises(CurrentStateError):
        validate_package(root, package)


def test_negative_gate_next_stage_true_fails(staged):
    root, package = staged
    path = package / GATE_NAME
    _rewrite_json(path, lambda obj: obj.__setitem__("next_stage_authorized", True))
    with pytest.raises(CurrentStateError):
        validate_package(root, package)


def test_negative_package_manifest_self_entry_fails(staged):
    root, package = staged
    path = package / PACKAGE_NAME

    def edit(obj):
        obj["package_entries"].append({"bytes": 0, "path": str(PACKAGE_REL / PACKAGE_NAME).replace("\\", "/"), "sha256": "0" * 64})
        obj["entry_count"] = 7

    _rewrite_json(path, edit)
    with pytest.raises(CurrentStateError):
        validate_package(root, package)


def test_negative_package_manifest_missing_entry_fails(staged):
    root, package = staged
    path = package / PACKAGE_NAME

    def edit(obj):
        obj["package_entries"].pop()
        obj["entry_count"] = 5

    _rewrite_json(path, edit)
    with pytest.raises(CurrentStateError):
        validate_package(root, package)


def test_negative_package_artifact_hash_tamper_fails(staged):
    root, package = staged
    readme = package / "README.md"
    readme.write_bytes(readme.read_bytes() + b"\n")
    with pytest.raises(CurrentStateError):
        validate_package(root, package)


def test_negative_generated_duplicate_key_fails(staged):
    root, package = staged
    path = package / GATE_NAME
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("{", '{\n  "release_credit": false,', 1), encoding="utf-8")
    with pytest.raises(CurrentStateError, match="duplicate JSON key"):
        validate_package(root, package)
