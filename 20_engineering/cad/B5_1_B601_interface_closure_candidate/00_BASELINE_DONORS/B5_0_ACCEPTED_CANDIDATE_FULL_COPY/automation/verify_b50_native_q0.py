"""Cold-verify one immutable B5.0 native-q0 SolidWorks run.

This verifier never writes a CAD document.  It opens the native files with the
shared read-only SolidWorks session contract, checks that the eight registered
vendor reference parts remain self-contained, checks the fixed q0 assembly
against the accepted URDF transforms, checks the drawing model view, and reads
the final STEP independently with OCP.

The q0 assembly is a fixed geometry reference.  Passing this verifier is not
evidence of retained mechanism degrees of freedom, mass authority, strength,
clearance, tolerance, manufacturing readiness, or flight release.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
import traceback
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from sw_b50_core import (  # noqa: E402
    CANDIDATE_ROOT,
    Phase0Error,
    SolidWorksSession,
    artifact_record,
    get_com_member,
    is_within,
    require_within,
    sha256_file,
    utc_now,
    validate_run_id,
    write_json_once,
)


RUNS_ROOT = CANDIDATE_ROOT / "03_CAD" / "native_runs"
CHAIN_PATH = CANDIDATE_ROOT / "01_KINEMATICS" / "accepted_chain.json"
VENDOR_LEDGER_PATH = (
    CANDIDATE_ROOT / "02_DESIGN" / "vendor_registration_ledger.json"
)
WORKSPACE_ROOT = CANDIDATE_ROOT.parents[2]

EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_MASS_SOURCE = "4.6955559493429862"
EXPECTED_VENDOR_VERDICT = (
    "B5_0_VENDOR_LINKLOCAL_REGISTRATION_PASS_WITH_G05_G08_HOLD"
)

GROUP_LINK = {
    "G01": "link1",
    "G02": "link2",
    "G03": "link3",
    "G04": "link4",
    "G05": "link6",
    "G06": "base_link",
    "G07": "link5",
    "G08": "gripper_link",
}
GROUP_ORDER = ["G06", "G01", "G02", "G03", "G04", "G07", "G05", "G08"]
PART_STEM = {
    "G01": "B50_REF_link1_LINKLOCAL",
    "G02": "B50_REF_link2_LINKLOCAL",
    "G03": "B50_REF_link3_LINKLOCAL",
    "G04": "B50_REF_link4_LINKLOCAL",
    "G05": "B50_REF_link6_LINKLOCAL",
    "G06": "B50_REF_base_link_LINKLOCAL",
    "G07": "B50_REF_link5_LINKLOCAL",
    "G08": "B50_REF_gripper_detail_LINKLOCAL",
}

SKELETON_REL = Path("00_skeleton") / "B50_B601_MASTER_SKELETON.SLDPRT"
ASSEMBLY_REL = Path("20_assembly") / "B50_B601_ENGINEERING_ARM_Q0.SLDASM"
STEP_REL = Path("30_exports") / "B50_B601_ENGINEERING_ARM_Q0.step"
DRAWING_REL = Path("40_drawings") / "B50_B601_ENGINEERING_ARM_Q0.SLDDRW"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_root(run_id: str) -> Path:
    validate_run_id(run_id)
    return require_within(RUNS_ROOT / run_id, RUNS_ROOT, "native_run_root")


def _part_path(run_root: Path, group: str) -> Path:
    return (
        run_root
        / "10_vendor_reference_parts"
        / f"{PART_STEM[group]}.SLDPRT"
    )


def _required_paths(
    run_root: Path, build_attempt_id: str | None
) -> dict[str, Path]:
    assembly_receipt_name = "q0_assembly_build"
    if build_attempt_id:
        assembly_receipt_name = (
            f"{assembly_receipt_name}_{build_attempt_id}"
        )
    paths = {
        "skeleton": run_root / SKELETON_REL,
        "assembly": run_root / ASSEMBLY_REL,
        "drawing": run_root / DRAWING_REL,
        "step": run_root / STEP_REL,
        "skeleton_receipt": (
            run_root / "evidence" / "master_skeleton_build.json"
        ),
        "assembly_receipt": (
            run_root / "evidence" / f"{assembly_receipt_name}.json"
        ),
    }
    paths.update(
        {
            f"part_{group}": _part_path(run_root, group)
            for group in GROUP_ORDER
        }
    )
    paths.update(
        {
            f"part_receipt_{group}": (
                run_root / "evidence" / f"native_{group}_build.json"
            )
            for group in GROUP_ORDER
        }
    )
    return paths


def _vendor_items(vendor: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = {str(item["group"]): item for item in vendor["groups"]}
    if set(items) != set(GROUP_ORDER):
        raise Phase0Error(
            f"vendor group set drift: {sorted(items)} != {sorted(GROUP_ORDER)}"
        )
    for group, item in items.items():
        if item["accepted_link_frame"] != GROUP_LINK[group]:
            raise Phase0Error(f"{group} accepted-link mapping drift")
    return items


def _verify_source_contract() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]
]:
    for path in (CHAIN_PATH, VENDOR_LEDGER_PATH):
        if not path.is_file():
            raise Phase0Error(f"source-contract evidence is missing: {path}")
    chain = _load_json(CHAIN_PATH)
    vendor = _load_json(VENDOR_LEDGER_PATH)
    if str(chain["source"]["sha256"]).upper() != EXPECTED_URDF_SHA256:
        raise Phase0Error("accepted URDF hash drift in accepted_chain.json")
    if str(chain["mass"]["total_kg_source_decimal"]) != EXPECTED_MASS_SOURCE:
        raise Phase0Error("accepted mass source string drift")
    if vendor.get("verdict") != EXPECTED_VENDOR_VERDICT:
        raise Phase0Error("vendor link-local registration is not admitted")
    if vendor.get("hold_groups") != ["G05", "G08"]:
        raise Phase0Error("vendor hold-group contract drift")
    if vendor.get("b106") != "NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH":
        raise Phase0Error("B106 bounded-search status drift")
    items = _vendor_items(vendor)

    accepted_urdf = WORKSPACE_ROOT / Path(str(chain["source"]["path"]))
    if not accepted_urdf.is_file():
        raise Phase0Error(f"accepted URDF is missing: {accepted_urdf}")
    actual_urdf_hash = sha256_file(accepted_urdf)
    if actual_urdf_hash != EXPECTED_URDF_SHA256:
        raise Phase0Error(
            f"accepted URDF hash drift: {actual_urdf_hash} "
            f"!= {EXPECTED_URDF_SHA256}"
        )
    return chain, vendor, items, {
        "accepted_chain": artifact_record(CHAIN_PATH, CANDIDATE_ROOT),
        "vendor_registration_ledger": artifact_record(
            VENDOR_LEDGER_PATH, CANDIDATE_ROOT
        ),
        "accepted_urdf": {
            "path": accepted_urdf.relative_to(WORKSPACE_ROOT).as_posix(),
            "bytes": accepted_urdf.stat().st_size,
            "sha256": actual_urdf_hash,
            "editable": False,
        },
        "accepted_mass_source_decimal_kg": EXPECTED_MASS_SOURCE,
        "vendor_verdict": EXPECTED_VENDOR_VERDICT,
        "hold_groups": ["G05", "G08"],
        "b106": "NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH",
    }


def _assert_artifact_record(
    path: Path,
    run_root: Path,
    expected: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    actual = artifact_record(path, run_root)
    for key in ("path", "bytes", "sha256"):
        if actual[key] != expected.get(key):
            raise Phase0Error(
                f"{label} {key} drift: {actual[key]!r} "
                f"!= {expected.get(key)!r}"
            )
    return actual


def _verify_build_receipts(
    run_root: Path,
    paths: dict[str, Path],
    items: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    skeleton_receipt = _load_json(paths["skeleton_receipt"])
    if skeleton_receipt.get("status") != "B5_0_NATIVE_BUILD_PASS":
        raise Phase0Error("master-skeleton build receipt is not PASS")
    if skeleton_receipt.get("result", {}).get("verdict") != (
        "B5_0_MASTER_SKELETON_PASS"
    ):
        raise Phase0Error("master-skeleton verdict drift")
    skeleton_artifact = _assert_artifact_record(
        paths["skeleton"],
        run_root,
        skeleton_receipt["result"]["artifact"],
        "master skeleton",
    )

    part_records: dict[str, Any] = {}
    for group in GROUP_ORDER:
        receipt = _load_json(paths[f"part_receipt_{group}"])
        result = receipt.get("result", {})
        if receipt.get("status") != "B5_0_NATIVE_BUILD_PASS":
            raise Phase0Error(f"{group} native-part build receipt is not PASS")
        if result.get("verdict") != f"B5_0_NATIVE_{group}_PASS":
            raise Phase0Error(f"{group} native-part verdict drift")
        if int(result.get("expected_solid_body_count", -1)) != int(
            items[group]["output_stats"]["solid_count"]
        ):
            raise Phase0Error(f"{group} receipt body-count contract drift")
        if result.get("registration_status") != items[group]["status"]:
            raise Phase0Error(f"{group} receipt registration-status drift")
        part_records[group] = _assert_artifact_record(
            paths[f"part_{group}"],
            run_root,
            result["save"],
            f"{group} native part",
        )

    assembly_receipt = _load_json(paths["assembly_receipt"])
    result = assembly_receipt.get("result", {})
    if assembly_receipt.get("status") != "B5_0_NATIVE_BUILD_PASS":
        raise Phase0Error("q0 assembly build receipt is not PASS")
    if result.get("verdict") != "B5_0_NATIVE_Q0_ASSEMBLY_BUILD_PASS":
        raise Phase0Error("q0 assembly build verdict drift")
    if int(result.get("component_count", -1)) != 9:
        raise Phase0Error("q0 assembly receipt component count is not 9")
    if result.get("retained_mechanism_dof_claimed") is not False:
        raise Phase0Error("q0 assembly receipt incorrectly claims mechanism DOF")
    final_records = {
        "assembly": _assert_artifact_record(
            paths["assembly"], run_root, result["assembly"], "q0 assembly"
        ),
        "drawing": _assert_artifact_record(
            paths["drawing"], run_root, result["drawing"], "q0 drawing"
        ),
        "step": _assert_artifact_record(
            paths["step"], run_root, result["step"], "q0 STEP"
        ),
    }
    return {
        "master_skeleton": skeleton_artifact,
        "native_parts": part_records,
        "final_artifacts": final_records,
        "reconciliation": "PASS",
    }


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _external_reference_count(model: Any) -> int:
    errors: list[str] = []
    try:
        return int(model.ListExternalFileReferencesCount2())
    except Exception as exc:
        errors.append(f"ListExternalFileReferencesCount2:{exc!r}")
    try:
        return int(model.ListExternalFileReferencesCount(False))
    except Exception as exc:
        errors.append(f"ListExternalFileReferencesCount:{exc!r}")
    raise Phase0Error(
        "cannot obtain external-reference count: " + "; ".join(errors)
    )


def _auxiliary_external_reference_count(model: Any) -> int:
    try:
        return int(model.ListAuxiliaryExternalFileReferencesCount())
    except Exception as exc:
        raise Phase0Error(
            f"cannot obtain auxiliary external-reference count: {exc!r}"
        ) from exc


def _three_d_interconnect_features(
    session: SolidWorksSession, model: Any
) -> list[str]:
    names: list[str] = []
    feature = get_com_member(model, "FirstFeature")
    visited = 0
    while feature is not None and visited < 10000:
        cast_feature = session.cast(feature, "IFeature")
        try:
            if bool(get_com_member(cast_feature, "Is3DInterconnectFeature")):
                names.append(str(get_com_member(cast_feature, "Name")))
        except Exception:
            pass
        feature = get_com_member(cast_feature, "GetNextFeature")
        visited += 1
    if visited >= 10000:
        raise Phase0Error("feature traversal exceeded safety limit")
    return names


def _body_facts(session: SolidWorksSession, model: Any) -> dict[str, Any]:
    part = session.cast(model, "IPartDoc")
    bodies = _as_list(part.GetBodies2(0, False))
    boxes: list[list[float]] = []
    for raw_body in bodies:
        body = session.cast(raw_body, "IBody2")
        values = [
            float(value) * 1000.0
            for value in _as_list(get_com_member(body, "GetBodyBox"))
        ]
        if len(values) != 6:
            raise Phase0Error(
                f"body GetBodyBox returned {len(values)} values, expected 6"
            )
        boxes.append(values)
    if not boxes:
        bbox = None
    else:
        bbox = {
            "min": [
                min(box[index] for box in boxes) for index in range(3)
            ],
            "max": [
                max(box[index + 3] for box in boxes) for index in range(3)
            ],
        }
    return {"solid_body_count": len(bodies), "bounding_box_mm": bbox}


def _expected_part_properties(
    run_id: str, group: str, item: dict[str, Any]
) -> dict[str, str]:
    return {
        "OBJECT_ID": f"B50_VENDOR_REF_{GROUP_LINK[group]}",
        "REPRESENTATION_LAYER": "L1_VENDOR_REFERENCE_LINKLOCAL",
        "GEOMETRY_AUTHORITY": f"{PART_STEM[group]}.step",
        "SOURCE_STEP_SHA256": str(item["output"]["sha256"]),
        "SOURCE_REGISTRATION_METHOD": str(item["method"]),
        "SOURCE_REGISTRATION_STATUS": str(item["status"]),
        "ACCEPTED_LINK_FRAME": GROUP_LINK[group],
        "KINEMATICS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "MASS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "ACCEPTED_URDF_SHA256": EXPECTED_URDF_SHA256,
        "GEOMETRY_LICENSE": "CERN-OHL-W-2.0",
        "INTERNAL_RESEARCH_NO_REDISTRIBUTION": "TRUE",
        "MANUFACTURING_AUTHORITY": "NONE",
        "RUN_ID": run_id,
        "CLAIM_LIMIT": (
            "reference geometry only; no material, strength, fit, tolerance, "
            "environmental or flight authority"
        ),
    }


def _read_and_match_properties(
    session: SolidWorksSession,
    model: Any,
    expected: dict[str, str],
    label: str,
) -> dict[str, str | None]:
    actual = {
        name: session.read_text_property(model, name) for name in expected
    }
    mismatches = {
        name: {"actual": actual[name], "expected": expected_value}
        for name, expected_value in expected.items()
        if actual[name] != expected_value
    }
    if mismatches:
        raise Phase0Error(f"{label} custom-property mismatch: {mismatches}")
    return actual


def _verify_part(
    session: SolidWorksSession,
    run_root: Path,
    path: Path,
    run_id: str,
    group: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    before_hash = sha256_file(path)
    model, open_record = session.open_document(path, "part")
    try:
        facts = _body_facts(session, model)
        expected_count = int(item["output_stats"]["solid_count"])
        if facts["solid_body_count"] != expected_count:
            raise Phase0Error(
                f"{group} cold body count {facts['solid_body_count']} "
                f"!= registered {expected_count}"
            )
        external_count = _external_reference_count(model)
        auxiliary_count = _auxiliary_external_reference_count(model)
        if external_count != 0:
            raise Phase0Error(
                f"{group} retains {external_count} external references"
            )
        if auxiliary_count != 0:
            raise Phase0Error(
                f"{group} retains {auxiliary_count} auxiliary references"
            )
        interconnect = _three_d_interconnect_features(session, model)
        if interconnect:
            raise Phase0Error(
                f"{group} retains 3D Interconnect features: {interconnect}"
            )
        properties = _read_and_match_properties(
            session,
            model,
            _expected_part_properties(run_id, group, item),
            group,
        )
    finally:
        session.close_document(model)
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error(f"read-only {group} verification changed file hash")
    return {
        "open": open_record,
        "artifact": artifact_record(path, run_root),
        "expected_solid_body_count": expected_count,
        "facts": facts,
        "external_reference_count": external_count,
        "auxiliary_external_reference_count": auxiliary_count,
        "three_d_interconnect_features": interconnect,
        "custom_properties": properties,
        "registration_status": item["status"],
        "hash_unchanged": True,
    }


def _math_transform_data(matrix: list[list[float]]) -> list[float]:
    """Return SolidWorks row-vector ArrayData for p_A0 = R*p_link + t."""
    return [
        float(matrix[0][0]),
        float(matrix[1][0]),
        float(matrix[2][0]),
        float(matrix[0][1]),
        float(matrix[1][1]),
        float(matrix[2][1]),
        float(matrix[0][2]),
        float(matrix[1][2]),
        float(matrix[2][2]),
        float(matrix[0][3]),
        float(matrix[1][3]),
        float(matrix[2][3]),
        1.0,
        0.0,
        0.0,
        0.0,
    ]


def _max_abs_error(actual: list[float], expected: list[float]) -> float:
    if len(actual) != len(expected):
        raise Phase0Error(
            f"MathTransform length {len(actual)} != expected {len(expected)}"
        )
    return max(abs(float(a) - float(b)) for a, b in zip(actual, expected))


def _component_path(raw_path: str, assembly_path: Path) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = assembly_path.parent / path
    return path.resolve()


def _expected_assembly_properties(run_id: str) -> dict[str, str]:
    return {
        "OBJECT_ID": "B50_B601_ENGINEERING_ARM_Q0",
        "REPRESENTATION_LAYER": "L1_NATIVE_VENDOR_REFERENCE_ASSEMBLY",
        "CONFIGURATION_STATE": "Q0_ACCEPTED_URDF",
        "KINEMATICS_AUTHORITY": "ACCEPTED_URDF_TRANSFORMS_ONLY",
        "MECHANISM_DOF_AUTHORITY": "NONE_FIXED_Q0_REFERENCE",
        "MASS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "ACCEPTED_URDF_SHA256": EXPECTED_URDF_SHA256,
        "ACCEPTED_TOTAL_MASS_REFERENCE_KG": EXPECTED_MASS_SOURCE,
        "VENDOR_DIRECT_GROUPS": "G01;G02;G03;G04;G06;G07",
        "VENDOR_HOLD_GROUPS": "G05;G08",
        "G05_STATUS": "CHAIN_DERIVED_HOLD",
        "G08_STATUS": "CHAIN_DERIVED_HOLD",
        "B106_STATUS": "NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH",
        "RUN_ID": run_id,
        "CLAIM_LIMIT": (
            "fixed q0 geometry reference; no retained 6R mates, continuous "
            "clearance, material, mass, strength, tolerance or flight release"
        ),
    }


def _verify_assembly(
    session: SolidWorksSession,
    run_root: Path,
    path: Path,
    run_id: str,
    chain: dict[str, Any],
) -> dict[str, Any]:
    before_hash = sha256_file(path)
    model, open_record = session.open_document(path, "assembly")
    try:
        assembly = session.cast(model, "IAssemblyDoc")
        components = _as_list(assembly.GetComponents(True))
        if len(components) != 9:
            raise Phase0Error(
                f"q0 assembly must have 9 top-level components, got "
                f"{len(components)}"
            )
        expected_by_path: dict[Path, tuple[str, list[float]]] = {
            (run_root / SKELETON_REL).resolve(): (
                "MASTER_SKELETON",
                _math_transform_data(
                    [
                        [1.0, 0.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0, 0.0],
                        [0.0, 0.0, 1.0, 0.0],
                        [0.0, 0.0, 0.0, 1.0],
                    ]
                ),
            )
        }
        for group in GROUP_ORDER:
            expected_by_path[_part_path(run_root, group).resolve()] = (
                f"{group}_{GROUP_LINK[group]}",
                _math_transform_data(
                    chain["q0_frames_A0"][GROUP_LINK[group]]
                ),
            )

        component_records: list[dict[str, Any]] = []
        observed_paths: list[Path] = []
        for raw_component in components:
            component = session.cast(raw_component, "IComponent2")
            raw_path = str(get_com_member(component, "GetPathName") or "")
            if not raw_path:
                raise Phase0Error("assembly component has an empty path")
            component_path = _component_path(raw_path, path)
            observed_paths.append(component_path)
            if component_path not in expected_by_path:
                raise Phase0Error(
                    f"assembly references unexpected component: {component_path}"
                )
            if not is_within(component_path, run_root):
                raise Phase0Error(
                    f"assembly component escapes run root: {component_path}"
                )
            if component_path.suffix.lower() != ".sldprt":
                raise Phase0Error(
                    f"assembly component is not native SLDPRT: {component_path}"
                )
            if not component_path.is_file():
                raise Phase0Error(
                    f"assembly component file is missing: {component_path}"
                )
            fixed = bool(get_com_member(component, "IsFixed"))
            if not fixed:
                raise Phase0Error(
                    f"q0 reference component is not fixed: {component_path}"
                )
            transform = get_com_member(component, "Transform2")
            if transform is None:
                raise Phase0Error(
                    f"component has no Transform2: {component_path}"
                )
            actual_transform = [
                float(value)
                for value in _as_list(
                    get_com_member(transform, "ArrayData")
                )
            ]
            label, expected_transform = expected_by_path[component_path]
            max_error = _max_abs_error(actual_transform, expected_transform)
            component_records.append(
                {
                    "label": label,
                    "path": component_path.relative_to(run_root).as_posix(),
                    "fixed": fixed,
                    "math_transform_array": actual_transform,
                    "expected_math_transform_array": expected_transform,
                    "max_abs_error": max_error,
                }
            )

        if len(set(observed_paths)) != 9:
            raise Phase0Error("q0 assembly contains duplicate component paths")
        if set(observed_paths) != set(expected_by_path):
            missing = sorted(
                path.relative_to(run_root).as_posix()
                for path in set(expected_by_path) - set(observed_paths)
            )
            raise Phase0Error(
                f"q0 assembly is missing expected components: {missing}"
            )
        properties = _read_and_match_properties(
            session,
            model,
            _expected_assembly_properties(run_id),
            "q0 assembly",
        )
    finally:
        session.close_document(model)
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error("read-only q0 assembly verification changed file hash")
    return {
        "open": open_record,
        "artifact": artifact_record(path, run_root),
        "component_count": len(component_records),
        "all_components_native_sldprt": True,
        "all_components_inside_run_root": True,
        "all_components_fixed": True,
        "components": component_records,
        "max_transform_abs_error": max(
            record["max_abs_error"] for record in component_records
        ),
        "transform_contract": (
            "SolidWorks ArrayData stores R^T, translation in metres at "
            "indices 9..11, scale=1 at index 12"
        ),
        "custom_properties": properties,
        "retained_mechanism_dof_claimed": False,
        "hash_unchanged": True,
    }


def _expected_drawing_properties(run_id: str) -> dict[str, str]:
    return {
        "OBJECT_ID": "B50_B601_ENGINEERING_ARM_Q0_DRAWING",
        "DRAWING_STATUS": "ENGINEERING_REFERENCE_NOT_FOR_MANUFACTURE",
        "MASS_AUTHORITY": "EXCLUDED",
        "ACCEPTED_URDF_SHA256": EXPECTED_URDF_SHA256,
        "RUN_ID": run_id,
        "CLAIM_LIMIT": (
            "reference view only; dimensions and tolerances not released"
        ),
    }


def _verify_drawing(
    session: SolidWorksSession,
    run_root: Path,
    path: Path,
    expected_assembly: Path,
    run_id: str,
) -> dict[str, Any]:
    before_hash = sha256_file(path)
    model, open_record = session.open_document(path, "drawing")
    try:
        drawing = session.cast(model, "IDrawingDoc")
        sheet = session.cast(drawing.GetCurrentSheet(), "ISheet")
        views = _as_list(sheet.GetViews())
        if not views:
            raise Phase0Error("q0 drawing contains no views")
        view_records: list[dict[str, Any]] = []
        model_backed = 0
        for raw_view in views:
            view = session.cast(raw_view, "IView")
            referenced = str(
                get_com_member(view, "GetReferencedModelName") or ""
            ).strip()
            referenced_relative: str | None = None
            if referenced:
                referenced_path = _component_path(referenced, path)
                if referenced_path != expected_assembly.resolve():
                    raise Phase0Error(
                        f"drawing references unexpected model: {referenced_path}"
                    )
                if not is_within(referenced_path, run_root):
                    raise Phase0Error(
                        f"drawing model reference escapes run root: "
                        f"{referenced_path}"
                    )
                referenced_relative = referenced_path.relative_to(
                    run_root
                ).as_posix()
                model_backed += 1
            view_records.append(
                {
                    "name": str(get_com_member(view, "GetName2") or ""),
                    "type": int(view.Type),
                    "referenced_model": referenced_relative,
                }
            )
        if model_backed < 1:
            raise Phase0Error("q0 drawing has no model-backed view")
        properties = _read_and_match_properties(
            session,
            model,
            _expected_drawing_properties(run_id),
            "q0 drawing",
        )
    finally:
        session.close_document(model)
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error("read-only q0 drawing verification changed file hash")
    return {
        "open": open_record,
        "artifact": artifact_record(path, run_root),
        "view_count": len(view_records),
        "model_backed_view_count": model_backed,
        "views": view_records,
        "custom_properties": properties,
        "hash_unchanged": True,
    }


def _transform_point_mm(
    matrix: list[list[float]], point_mm: tuple[float, float, float]
) -> list[float]:
    return [
        sum(float(matrix[row][column]) * point_mm[column] for column in range(3))
        + float(matrix[row][3]) * 1000.0
        for row in range(3)
    ]


def _expected_step_bbox_mm(
    chain: dict[str, Any], items: dict[str, dict[str, Any]]
) -> dict[str, list[float]]:
    points: list[list[float]] = []
    for group in GROUP_ORDER:
        bbox = items[group]["output_stats"]["bbox_mm"]
        local_min = [float(value) for value in bbox["min"]]
        local_max = [float(value) for value in bbox["max"]]
        matrix = chain["q0_frames_A0"][GROUP_LINK[group]]
        for corner in itertools.product((0, 1), repeat=3):
            point = tuple(
                local_max[index] if corner[index] else local_min[index]
                for index in range(3)
            )
            points.append(_transform_point_mm(matrix, point))
    return {
        "min": [min(point[index] for point in points) for index in range(3)],
        "max": [max(point[index] for point in points) for index in range(3)],
    }


def _verify_step(
    path: Path,
    run_root: Path,
    chain: dict[str, Any],
    items: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    try:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer
    except Exception as exc:
        raise Phase0Error(f"OCP STEP reader is unavailable: {exc!r}") from exc

    before_hash = sha256_file(path)
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise Phase0Error(f"OCP STEP ReadFile failed with status {status!r}")
    transferred = int(reader.TransferRoots())
    shape = reader.OneShape()
    if transferred <= 0 or shape.IsNull():
        raise Phase0Error(
            f"OCP STEP transfer produced no valid shape: roots={transferred}"
        )

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        raise Phase0Error("OCP STEP bounding box is void")
    bounds = [float(value) for value in box.Get()]
    if len(bounds) != 6 or not all(math.isfinite(value) for value in bounds):
        raise Phase0Error(f"invalid OCP STEP bounding box: {bounds}")
    bbox = {"min": bounds[:3], "max": bounds[3:]}
    if any(
        bbox["max"][index] <= bbox["min"][index] for index in range(3)
    ):
        raise Phase0Error(f"degenerate OCP STEP bounding box: {bbox}")

    solid_count = 0
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid_count += 1
        explorer.Next()
    expected_solid_count = sum(
        int(items[group]["output_stats"]["solid_count"])
        for group in GROUP_ORDER
    )
    if solid_count != expected_solid_count:
        raise Phase0Error(
            f"final STEP solid count {solid_count} != registered body total "
            f"{expected_solid_count}"
        )

    expected_bbox = _expected_step_bbox_mm(chain, items)
    bbox_abs_errors = {
        "min": [
            abs(bbox["min"][index] - expected_bbox["min"][index])
            for index in range(3)
        ],
        "max": [
            abs(bbox["max"][index] - expected_bbox["max"][index])
            for index in range(3)
        ],
    }
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error("OCP STEP verification changed file hash")
    return {
        **artifact_record(path, run_root),
        "ocp_read": "PASS",
        "transferred_roots": transferred,
        "shape_is_null": False,
        "solid_count": solid_count,
        "expected_solid_count": expected_solid_count,
        "bbox_mm": bbox,
        "expected_bbox_from_registered_linklocal_and_q0_mm": expected_bbox,
        "bbox_abs_errors_mm": bbox_abs_errors,
        "max_bbox_abs_error_mm": max(
            bbox_abs_errors["min"] + bbox_abs_errors["max"]
        ),
        "hash_unchanged": True,
    }


def _cad_artifact_paths(paths: dict[str, Path]) -> dict[str, Path]:
    return {
        name: path
        for name, path in paths.items()
        if name in {"skeleton", "assembly", "drawing", "step"}
        or name.startswith("part_") and not name.startswith("part_receipt_")
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Cold-reopen and independently verify one immutable B5.0 native-q0 "
            "SolidWorks run."
        )
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--attempt-id",
        help=(
            "Optional additive verification-attempt suffix.  Existing evidence "
            "is never overwritten."
        ),
    )
    parser.add_argument(
        "--build-attempt-id",
        help=(
            "Append-only assembly-build receipt suffix to verify, for example "
            "attempt3. Omit only when q0_assembly_build.json is the admitted "
            "PASS receipt."
        ),
    )
    parser.add_argument(
        "--transform-tolerance",
        type=float,
        default=1.0e-9,
        help="Maximum accepted SolidWorks MathTransform absolute error.",
    )
    parser.add_argument(
        "--bbox-tolerance-mm",
        type=float,
        default=0.1,
        help=(
            "Maximum accepted OCP STEP bbox delta versus the registered "
            "link-local bboxes transformed by accepted q0."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report: dict[str, Any] = {
        "schema": "SER_B50_NATIVE_Q0_COLD_VERIFY_V1",
        "generated_utc": utc_now(),
        "run_id": args.run_id,
        "attempt_id": args.attempt_id or "initial",
        "build_attempt_id": args.build_attempt_id or "initial",
        "candidate_root": str(CANDIDATE_ROOT),
        "status": "B5_0_NATIVE_Q0_COLD_VERIFY_HOLD",
        "mass_authority": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "mechanism_dof_authority": "NONE_FIXED_Q0_REFERENCE",
        "checks": {},
        "tolerances": {
            "transform_abs": args.transform_tolerance,
            "step_bbox_mm": args.bbox_tolerance_mm,
        },
        "claim_limit": (
            "fixed q0 geometry reference only; no retained 6R mechanism, "
            "continuous clearance, material, mass, strength, tolerance, "
            "manufacturing or flight release"
        ),
    }
    run_root: Path | None = None
    report_path: Path | None = None
    session: SolidWorksSession | None = None
    initial_hashes: dict[str, str] = {}
    artifact_paths: dict[str, Path] = {}
    try:
        if args.transform_tolerance <= 0.0 or not math.isfinite(
            args.transform_tolerance
        ):
            raise Phase0Error("transform tolerance must be finite and positive")
        if args.bbox_tolerance_mm <= 0.0 or not math.isfinite(
            args.bbox_tolerance_mm
        ):
            raise Phase0Error("bbox tolerance must be finite and positive")
        if args.build_attempt_id:
            validate_run_id(args.build_attempt_id)

        run_root = _run_root(args.run_id)
        if not run_root.is_dir():
            raise Phase0Error(f"native run root does not exist: {run_root}")
        if args.attempt_id:
            validate_run_id(args.attempt_id)
            report_path = (
                run_root
                / "evidence"
                / f"native_q0_cold_verify_{args.attempt_id}.json"
            )
        else:
            report_path = (
                run_root / "evidence" / "native_q0_cold_verify.json"
            )
        if report_path.exists():
            raise Phase0Error(
                f"verification evidence exists; overwrite forbidden: "
                f"{report_path}"
            )

        paths = _required_paths(run_root, args.build_attempt_id)
        missing = {
            name: str(path)
            for name, path in paths.items()
            if not path.is_file()
        }
        if missing:
            raise Phase0Error(f"required native-q0 files are missing: {missing}")
        chain, _vendor, items, source_contract = _verify_source_contract()
        report["checks"]["source_contract"] = source_contract
        report["checks"]["build_receipts"] = _verify_build_receipts(
            run_root, paths, items
        )

        artifact_paths = _cad_artifact_paths(paths)
        initial_hashes = {
            name: sha256_file(path) for name, path in artifact_paths.items()
        }
        report["initial_artifact_hashes"] = initial_hashes

        with SolidWorksSession(run_root, visible=False) as session:
            report["session_start"] = session.info()
            report["checks"]["native_parts"] = {}
            for group in GROUP_ORDER:
                report["checks"]["native_parts"][group] = _verify_part(
                    session,
                    run_root,
                    paths[f"part_{group}"],
                    args.run_id,
                    group,
                    items[group],
                )
            report["checks"]["assembly"] = _verify_assembly(
                session,
                run_root,
                paths["assembly"],
                args.run_id,
                chain,
            )
            if (
                report["checks"]["assembly"]["max_transform_abs_error"]
                > args.transform_tolerance
            ):
                raise Phase0Error(
                    "q0 assembly transform tolerance exceeded: "
                    f"{report['checks']['assembly']['max_transform_abs_error']} "
                    f"> {args.transform_tolerance}"
                )
            report["checks"]["drawing"] = _verify_drawing(
                session,
                run_root,
                paths["drawing"],
                paths["assembly"],
                args.run_id,
            )
        report["session_end"] = session.info()

        report["checks"]["step"] = _verify_step(
            paths["step"], run_root, chain, items
        )
        if (
            report["checks"]["step"]["max_bbox_abs_error_mm"]
            > args.bbox_tolerance_mm
        ):
            raise Phase0Error(
                "final STEP bbox tolerance exceeded: "
                f"{report['checks']['step']['max_bbox_abs_error_mm']} mm "
                f"> {args.bbox_tolerance_mm} mm"
            )

        final_hashes = {
            name: sha256_file(path) for name, path in artifact_paths.items()
        }
        report["final_artifact_hashes"] = final_hashes
        if final_hashes != initial_hashes:
            raise Phase0Error(
                "cold verification changed one or more CAD/export hashes"
            )
        report["checks"]["all_artifact_hashes_unchanged"] = True
        report["status"] = (
            "B5_0_NATIVE_Q0_COLD_VERIFY_PASS_WITH_G05_G08_HOLD"
        )
    except Exception as exc:
        report["status"] = "B5_0_NATIVE_Q0_COLD_VERIFY_HOLD"
        report["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        if session is not None:
            report["session_end"] = session.info()
    finally:
        if initial_hashes and artifact_paths:
            try:
                observed_hashes = {
                    name: sha256_file(path)
                    for name, path in artifact_paths.items()
                    if path.is_file()
                }
                report["observed_artifact_hashes_at_exit"] = observed_hashes
                report["artifact_hashes_unchanged_at_exit"] = (
                    observed_hashes == initial_hashes
                )
                if observed_hashes != initial_hashes:
                    report["status"] = "B5_0_NATIVE_Q0_COLD_VERIFY_HOLD"
            except Exception as hash_exc:
                report["exit_hash_check_error"] = repr(hash_exc)
                report["status"] = "B5_0_NATIVE_Q0_COLD_VERIFY_HOLD"
        report["completed_utc"] = utc_now()
        if run_root is not None and report_path is not None:
            try:
                write_json_once(report_path, report, run_root)
            except Exception as evidence_exc:
                report["evidence_write_error"] = repr(evidence_exc)
                report["status"] = "B5_0_NATIVE_Q0_COLD_VERIFY_HOLD"
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return (
        0
        if report["status"]
        == "B5_0_NATIVE_Q0_COLD_VERIFY_PASS_WITH_G05_G08_HOLD"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
