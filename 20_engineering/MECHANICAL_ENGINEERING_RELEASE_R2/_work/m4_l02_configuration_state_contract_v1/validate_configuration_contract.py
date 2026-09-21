#!/usr/bin/env python3
"""Independent validator for the append-only M4-L02 configuration contract.

This module intentionally does not import the builder.  It re-reads every
source and generated artifact with duplicate-key and non-finite-number guards,
then recomputes the contract checks from those bytes.
"""

from __future__ import annotations

import argparse
import ast
import copy
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

import numpy as np
import yaml


PACKAGE = Path(__file__).resolve().parent
WORKSPACE = PACKAGE.parents[3]


# Effective contract literals come only from the side-effect-free third layer.
# The validator deliberately imports no builder module or builder function.
from frozen_contract_v1 import (  # noqa: E402
    CONFIG_NAMES,
    CORE_FILES,
    EXPECTED_ARM_HDRM_NULL,
    EXPECTED_DESIGN_CHECK_KEYS,
    EXPECTED_DYNAMICS_USES,
    EXPECTED_MANIFEST_FILES,
    EXPECTED_MANIFEST_ROLES,
    EXPECTED_PINS,
    EXPECTED_SOLAR_HDRM_NULL,
    EXPECTED_SOLAR_LATCH_NULL,
    GATE_FILE,
    JOINT_LIMITS,
    LEGACY_NAMES,
    M5_NAMES,
    MANIFEST_FILE,
    NEGATIVE_CONTROL_IDS,
    NEGATIVE_FILE,
    Q_HOME,
    Q_PREGRASP,
    Q_SERVICE,
    Q_STOW,
    SPEC_FILE,
    SPEC_SCHEMA,
    VERDICT,
)


class StrictDataError(ValueError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise StrictDataError(f"unhashable YAML key: {key!r}") from exc
        if duplicate:
            raise StrictDataError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def reject_nonfinite(value, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise StrictDataError(f"non-finite number at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, (str, int, float, bool)) and key is not None:
                raise StrictDataError(f"unsupported mapping key at {path}: {key!r}")
            reject_nonfinite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_nonfinite(child, f"{path}[{index}]")


def _pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise StrictDataError(f"duplicate JSON key: {key!r}")
        out[key] = value
    return out


def strict_json_loads(text: str):
    def reject_constant(token: str):
        raise StrictDataError(f"non-finite JSON token: {token}")

    try:
        value = json.loads(text, object_pairs_hook=_pairs_no_duplicates, parse_constant=reject_constant)
    except (json.JSONDecodeError, StrictDataError) as exc:
        raise StrictDataError(str(exc)) from exc
    reject_nonfinite(value)
    return value


def strict_yaml_loads(text: str):
    try:
        value = yaml.load(text, Loader=UniqueKeyLoader)
    except (yaml.YAMLError, StrictDataError) as exc:
        raise StrictDataError(str(exc)) from exc
    reject_nonfinite(value)
    return value


def read_json(path: Path):
    return strict_json_loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path):
    return strict_yaml_loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def canonical_json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def floats_equal(a, b, tol: float = 0.0) -> bool:
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(floats_equal(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(floats_equal(a[k], b[k], tol) for k in a)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    return a == b


def ieee754_binary64_equal(actual, expected) -> bool:
    """Require a real Python float and identical IEEE-754 binary64 bytes."""
    if type(actual) is not float or type(expected) is not float:  # bool/int are forbidden
        return False
    if not math.isfinite(actual) or not math.isfinite(expected):
        return False
    return struct.pack(">d", actual) == struct.pack(">d", expected)


def audit_binary64_tree(actual, expected, path: str = "$") -> tuple[bool, int, list[str]]:
    """Recursively compare numeric leaves, preserving container/key/type shape."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            return False, 0, [f"{path}:mapping_shape"]
        ok = True
        count = 0
        errors: list[str] = []
        for key in expected:
            child_ok, child_count, child_errors = audit_binary64_tree(
                actual[key], expected[key], f"{path}.{key}"
            )
            ok = ok and child_ok
            count += child_count
            errors.extend(child_errors)
        return ok, count, errors
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False, 0, [f"{path}:list_shape"]
        ok = True
        count = 0
        errors: list[str] = []
        for index, child in enumerate(expected):
            child_ok, child_count, child_errors = audit_binary64_tree(
                actual[index], child, f"{path}[{index}]"
            )
            ok = ok and child_ok
            count += child_count
            errors.extend(child_errors)
        return ok, count, errors
    if type(expected) is float:
        ok = ieee754_binary64_equal(actual, expected)
        return ok, 1, [] if ok else [f"{path}:binary64_or_type"]
    ok = type(actual) is type(expected) and actual == expected
    return ok, 0, [] if ok else [f"{path}:literal_or_type"]


def walk_key_values(value, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key, child
            yield from walk_key_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_key_values(child, f"{path}[{index}]")


def load_sources(workspace: Path = WORKSPACE):
    docs = {}
    for source_id, (rel, _, _, _) in EXPECTED_PINS.items():
        path = workspace / rel
        suffix = path.suffix.lower()
        if suffix == ".json":
            docs[source_id] = read_json(path)
        elif suffix in {".yaml", ".yml"}:
            docs[source_id] = read_yaml(path)
        elif suffix == ".urdf":
            docs[source_id] = ET.parse(path).getroot()
        else:
            docs[source_id] = None
    return docs


def read_geometry_csv(path: Path):
    text = path.read_text(encoding="utf-8")
    if "\r" in text:
        raise StrictDataError("geometry CSV must use canonical LF newlines")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise StrictDataError("duplicate or absent CSV field names")
    rows = list(reader)
    for row in rows:
        if None in row:
            raise StrictDataError("CSV row has surplus columns")
    return rows


def parse_bbox_cell(cell, path: str):
    if not isinstance(cell, str):
        raise StrictDataError(f"{path}: bbox cell must be a JSON string")
    value = strict_json_loads(cell)
    if not isinstance(value, list) or len(value) != 3 or any(type(item) is not float for item in value):
        raise StrictDataError(f"{path}: bbox must contain exactly three binary64 values")
    if not all(math.isfinite(item) for item in value):
        raise StrictDataError(f"{path}: bbox contains non-finite value")
    return value


def read_manifest_csv(path: Path):
    text = path.read_text(encoding="utf-8")
    if "\r" in text:
        raise StrictDataError("manifest CSV must use canonical LF newlines")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ["path", "bytes", "sha256", "role"]:
        raise StrictDataError(f"manifest header drift: {reader.fieldnames!r}")
    rows = list(reader)
    if any(None in row for row in rows):
        raise StrictDataError("manifest row has surplus columns")
    return rows


def load_core_docs(package: Path = PACKAGE):
    return {
        "source_lock": read_json(package / CORE_FILES["source_lock"]),
        "crosswalk": read_yaml(package / CORE_FILES["crosswalk"]),
        "state": read_yaml(package / CORE_FILES["state"]),
        "mass": read_yaml(package / CORE_FILES["mass"]),
        "geometry": read_geometry_csv(package / CORE_FILES["geometry"]),
        "dynamics": read_yaml(package / CORE_FILES["dynamics"]),
    }


def _result(ok: bool, detail):
    return {"pass": bool(ok), "detail": detail}


def _config_map(document, key: str = "configurations"):
    rows = document.get(key, [])
    return {row.get("configuration_id"): row for row in rows}


def _all_null_leaves(value) -> bool:
    if isinstance(value, dict):
        return all(_all_null_leaves(child) for child in value.values())
    if isinstance(value, list):
        return all(_all_null_leaves(child) for child in value)
    return value is None


def _unique_count(values) -> int:
    try:
        return len(set(values))
    except TypeError:
        return -1


def evaluate_core(docs, workspace: Path = WORKSPACE):
    checks = {}
    sources = load_sources(workspace)

    lock_rows = docs["source_lock"].get("sources", [])
    rows_are_mappings = isinstance(lock_rows, list) and all(isinstance(row, dict) for row in lock_rows)
    lock_map = {row.get("source_id"): row for row in lock_rows} if rows_are_mappings else {}
    lock_ids = [row.get("source_id") for row in lock_rows] if rows_are_mappings else []
    lock_paths = [row.get("path") for row in lock_rows] if rows_are_mappings else []
    expected_rows = [
        {
            "source_id": source_id,
            "path": rel,
            "bytes": expected_bytes,
            "sha256": expected_hash,
            "role": role,
            "match": True,
        }
        for source_id, (rel, expected_bytes, expected_hash, role) in EXPECTED_PINS.items()
    ]
    raw_rows_exact, _, raw_row_errors = audit_binary64_tree(
        lock_rows, expected_rows, "source_lock.sources"
    )
    raw_map_count_ok = (
        rows_are_mappings
        and raw_rows_exact
        and type(docs["source_lock"].get("source_count")) is int
        and len(lock_rows) == len(lock_map) == docs["source_lock"].get("source_count") == 20
        and len(lock_ids) == _unique_count(lock_ids) == 20
        and len(lock_paths) == _unique_count(lock_paths) == 20
        and docs["source_lock"].get("all_sources_match") is True
        and all(row.get("match") is True for row in lock_rows)
    )
    pins_ok = raw_map_count_ok and set(lock_map) == set(EXPECTED_PINS)
    pin_detail = {}
    for source_id, (rel, expected_bytes, expected_hash, role) in EXPECTED_PINS.items():
        path = workspace / rel
        actual = {
            "path": rel,
            "bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256(path) if path.exists() else None,
            "role": role,
        }
        row = lock_map.get(source_id, {})
        match = (
            path.exists()
            and actual["bytes"] == expected_bytes
            and actual["sha256"] == expected_hash
            and row.get("path") == rel
            and row.get("bytes") == expected_bytes
            and row.get("sha256") == expected_hash
            and row.get("role") == role
            and row.get("match") is True
        )
        pins_ok = pins_ok and match
        pin_detail[source_id] = {**actual, "expected_bytes": expected_bytes, "expected_sha256": expected_hash, "match": match}
    checks["CORE01_SOURCE_PINS_EXACT"] = _result(
        pins_ok,
        {
            "raw_row_count": len(lock_rows) if isinstance(lock_rows, list) else None,
            "map_count": len(lock_map),
            "declared_source_count": docs["source_lock"].get("source_count"),
            "unique_source_ids": _unique_count(lock_ids) if rows_are_mappings else 0,
            "unique_paths": _unique_count(lock_paths) if rows_are_mappings else 0,
            "all_sources_match": docs["source_lock"].get("all_sources_match"),
            "raw_row_type_or_value_errors": raw_row_errors,
            "sources": pin_detail,
        },
    )

    structured_ok = True
    structured_detail = {}
    for source_id, (rel, _, _, _) in EXPECTED_PINS.items():
        suffix = Path(rel).suffix.lower()
        if suffix in {".json", ".yaml", ".yml", ".urdf"}:
            structured_detail[source_id] = "STRICT_PARSE_PASS"
    try:
        reject_nonfinite({k: v for k, v in sources.items() if not isinstance(v, ET.Element)})
    except StrictDataError as exc:
        structured_ok = False
        structured_detail["error"] = str(exc)
    checks["CORE02_STRICT_SOURCE_PARSE_NO_DUPLICATE_OR_NONFINITE"] = _result(structured_ok, structured_detail)

    crosswalk = docs["crosswalk"]
    cross_rows = crosswalk.get("records", [])
    cross_map = {row.get("configuration_id"): row for row in cross_rows}
    cross_ok = (
        crosswalk.get("schema") == "R2_CONFIGURATION_CROSSWALK_V1"
        and len(cross_rows) == 9
        and set(cross_map) == set(CONFIG_NAMES)
        and len(cross_map) == len(cross_rows)
    )
    m4_map = _config_map(sources["m4_configuration_library"])
    m5_map = _config_map({"configurations": sources["m5_geometry_contract"].get("records", [])})
    m7_map = _config_map(sources["design_mass"])
    for cid in CONFIG_NAMES:
        row = cross_map.get(cid, {})
        cross_ok = cross_ok and row.get("contract_name") == CONFIG_NAMES[cid]
        cross_ok = cross_ok and row.get("m4_name") == m4_map[cid]["name"] == CONFIG_NAMES[cid]
        cross_ok = cross_ok and row.get("m4_legacy_alias") == m4_map[cid]["legacy_mapping"] == LEGACY_NAMES[cid]
        cross_ok = cross_ok and row.get("m5_diagnostic_name") == m5_map[cid]["name"] == M5_NAMES[cid]
        cross_ok = cross_ok and row.get("m7_design_mass_name") == m7_map[cid]["name"] == CONFIG_NAMES[cid]
        cross_ok = cross_ok and row.get("selected_current_r2") is (cid == "C01")
    checks["CORE03_CROSSWALK_EXACT_NINE_AND_ALIASES"] = _result(cross_ok, {cid: cross_map.get(cid) for cid in CONFIG_NAMES})

    mass_doc = docs["mass"]
    mass_rows = mass_doc.get("configurations", [])
    mass_map = {row.get("configuration_id"): row for row in mass_rows}
    mass_shape_ok = (
        mass_doc.get("schema") == "R2_NINE_CONFIGURATION_MASS_PROPERTY_VIEW_V1"
        and len(mass_rows) == 9
        and set(mass_map) == set(CONFIG_NAMES)
        and mass_doc.get("model_class") == "DESIGN_MODEL_CANDIDATE_ONLY_NOT_AS_BUILT"
    )
    checks["CORE04_MASS_VIEW_EXACT_NINE_DESIGN_CLASS"] = _result(mass_shape_ok, {"count": len(mass_rows), "ids": sorted(mass_map)})

    receipt_map = {row["configuration_id"]: row for row in sources["design_mass_receipt"]["per_configuration"]}
    mass_values_ok = True
    mass_value_detail = {}
    unique_core_leaf_count = 0
    receipt_recheck_count = 0
    mass_leaf_errors: list[str] = []
    physics_ok = True
    physics_detail = {}
    design_checks_ok = True
    ssot_min_eigenvalue_leaf_count = 0
    receipt_min_eigenvalue_recheck_count = 0
    for cid, source_row in m7_map.items():
        out = mass_map.get(cid, {})
        expected = {
            "mass_kg": source_row["mass"]["value_kg"],
            "mass_standard_uncertainty_kg": source_row["mass"]["standard_uncertainty_kg"],
            "cg_S_m": source_row["center_of_mass"]["xyz_m"],
            "cg_standard_uncertainty_S_m": source_row["center_of_mass"]["standard_uncertainty_xyz_m"],
            "inertia_about_system_cg_S_kg_m2": source_row["inertia"]["components_kg_m2"],
            "inertia_standard_uncertainty_components_kg_m2": source_row["inertia"]["standard_uncertainty_components_kg_m2"],
        }
        exact = True
        row_core_leaf_count = 0
        row_receipt_recheck_count = 0
        row_errors: list[str] = []
        for key, value in expected.items():
            key_ok, key_count, key_errors = audit_binary64_tree(
                out.get(key), value, f"mass.{cid}.{key}"
            )
            exact = exact and key_ok
            row_core_leaf_count += key_count
            row_errors.extend(key_errors)
        exact = exact and out.get("name") == CONFIG_NAMES[cid]
        exact = exact and out.get("reference_frame") == "S" and out.get("reference_point") == "system_center_of_mass"
        exact = exact and out.get("as_built_mass_kg") is None and out.get("as_built_cg_S_m") is None and out.get("as_built_inertia_kg_m2") is None
        receipt = receipt_map[cid]
        receipt_mass_ok, receipt_mass_count, receipt_mass_errors = audit_binary64_tree(
            out.get("mass_kg"), receipt["mass_kg"], f"receipt.{cid}.mass_kg"
        )
        receipt_cg_ok, receipt_cg_count, receipt_cg_errors = audit_binary64_tree(
            out.get("cg_S_m"), receipt["cg_S_m"], f"receipt.{cid}.cg_S_m"
        )
        exact = exact and receipt_mass_ok and receipt_cg_ok
        row_receipt_recheck_count += receipt_mass_count + receipt_cg_count
        row_errors.extend(receipt_mass_errors + receipt_cg_errors)
        mass_values_ok = mass_values_ok and exact
        unique_core_leaf_count += row_core_leaf_count
        receipt_recheck_count += row_receipt_recheck_count
        mass_leaf_errors.extend(row_errors)
        mass_value_detail[cid] = {
            "exact": exact,
            "unique_core_binary64_leaves_checked": row_core_leaf_count,
            "receipt_binary64_rechecks": row_receipt_recheck_count,
            "type_or_bit_errors": row_errors,
            "mass_kg": out.get("mass_kg"),
            "cg_S_m": out.get("cg_S_m"),
        }

        source_checks = source_row.get("checks", {})
        output_checks = out.get("design_checks_from_ssot")
        receipt_checks = receipt.get("checks", {})
        source_check_shape_ok = isinstance(source_checks, dict) and set(source_checks) == EXPECTED_DESIGN_CHECK_KEYS
        receipt_check_shape_ok = isinstance(receipt_checks, dict) and set(receipt_checks) == EXPECTED_DESIGN_CHECK_KEYS
        output_vs_source_ok, output_min_count, output_check_errors = audit_binary64_tree(
            output_checks, source_checks, f"mass.{cid}.design_checks_from_ssot"
        )
        output_vs_receipt_ok, receipt_min_count, receipt_check_errors = audit_binary64_tree(
            output_checks, receipt_checks, f"receipt.{cid}.checks"
        )
        check_fields_ok = (
            source_check_shape_ok
            and receipt_check_shape_ok
            and output_vs_source_ok
            and output_vs_receipt_ok
            and output_min_count == 1
            and receipt_min_count == 1
            and type(source_checks.get("min_eigenvalue_kg_m2")) is float
            and math.isfinite(source_checks.get("min_eigenvalue_kg_m2"))
            and source_checks.get("min_eigenvalue_kg_m2") > 0.0
            and all(
                source_checks.get(key) is True
                for key in EXPECTED_DESIGN_CHECK_KEYS
                if key != "min_eigenvalue_kg_m2"
            )
        )
        design_checks_ok = design_checks_ok and check_fields_ok
        ssot_min_eigenvalue_leaf_count += output_min_count
        receipt_min_eigenvalue_recheck_count += receipt_min_count

        comp = out.get("inertia_about_system_cg_S_kg_m2", {})
        try:
            matrix = np.array([
                [comp["Ixx"], comp["Ixy"], comp["Ixz"]],
                [comp["Ixy"], comp["Iyy"], comp["Iyz"]],
                [comp["Ixz"], comp["Iyz"], comp["Izz"]],
            ], dtype=float)
            eig = np.linalg.eigvalsh(matrix)
            sym = np.array_equal(matrix, matrix.T)
            pd = bool(np.all(eig > 0.0))
            triangle = bool(eig[0] + eig[1] + 1e-12 >= eig[2])
            finite = bool(np.isfinite(matrix).all() and np.isfinite(eig).all())
            per_ok = sym and pd and triangle and finite and check_fields_ok
        except (KeyError, TypeError, ValueError):
            eig = np.array([np.nan, np.nan, np.nan])
            per_ok = False
        physics_ok = physics_ok and per_ok
        physics_detail[cid] = {
            "pass": per_ok,
            "eigenvalues_kg_m2": eig.tolist(),
            "design_checks_exact": check_fields_ok,
            "ssot_min_eigenvalue_kg_m2": source_checks.get("min_eigenvalue_kg_m2"),
            "type_or_bit_errors": output_check_errors + receipt_check_errors,
        }
    mass_values_ok = (
        mass_values_ok
        and unique_core_leaf_count == 180
        and receipt_recheck_count == 36
        and not mass_leaf_errors
    )
    checks["CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED"] = _result(
        mass_values_ok,
        {
            "unique_core_binary64_leaves_checked": unique_core_leaf_count,
            "expected_unique_core": 180,
            "receipt_binary64_rechecks": receipt_recheck_count,
            "expected_receipt_rechecks": 36,
            "total_binary64_comparisons": unique_core_leaf_count + receipt_recheck_count,
            "configurations": mass_value_detail,
        },
    )
    design_checks_and_physics_ok = (
        design_checks_ok
        and physics_ok
        and ssot_min_eigenvalue_leaf_count == 9
        and receipt_min_eigenvalue_recheck_count == 9
    )
    checks["CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS"] = _result(
        design_checks_and_physics_ok,
        {
            "ssot_min_eigenvalue_binary64_leaves_checked": ssot_min_eigenvalue_leaf_count,
            "receipt_min_eigenvalue_binary64_rechecks": receipt_min_eigenvalue_recheck_count,
            "configurations": physics_detail,
        },
    )

    state_doc = docs["state"]
    state_rows = state_doc.get("configurations", [])
    state_map = {row.get("configuration_id"): row for row in state_rows}
    state_shape_ok = (
        state_doc.get("schema") == "R2_CONFIGURATION_STATE_VECTOR_CONTRACT_V1"
        and len(state_rows) == 9
        and set(state_map) == set(CONFIG_NAMES)
        and state_doc.get("continuous_state_order") == ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint1", "gripper_joint2"]
        and state_doc.get("q6_is_separate_from_discrete_state") is True
    )
    checks["CORE07_STATE_SCHEMA_NINE_AND_Q6_2P_DISCRETE_SEPARATION"] = _result(state_shape_ok, {"count": len(state_rows)})

    authority_q_ok = True
    q_detail = {}
    for cid, row in state_map.items():
        auth_q = row.get("authoritative_state", {}).get("q6_rad", {})
        candidate_q = row.get("non_authoritative_candidates", {}).get("q6_rad", {})
        if cid in {"C01", "C02", "C03", "C04"}:
            expected_value = Q_HOME
            expected_status = "AUTHORITY_BOUND_ACCEPTED_RUNTIME_DIGITAL_POSE"
            per_ok = floats_equal(auth_q.get("value"), expected_value, 0.0) and auth_q.get("status") == expected_status and candidate_q.get("value") is None
        else:
            expected_value = {"C05": Q_STOW, "C06": Q_SERVICE, "C07": Q_PREGRASP, "C08": Q_PREGRASP, "C09": Q_PREGRASP}[cid]
            per_ok = auth_q.get("value") is None and auth_q.get("status") == "UNKNOWN_NOT_AUTHORITY_BOUND"
            per_ok = per_ok and floats_equal(candidate_q.get("value"), expected_value, 0.0)
        values = auth_q.get("value") if auth_q.get("value") is not None else candidate_q.get("value")
        limits_ok = isinstance(values, list) and len(values) == 6 and all(lo <= float(q) <= hi for q, (lo, hi) in zip(values, JOINT_LIMITS))
        per_ok = per_ok and limits_ok
        authority_q_ok = authority_q_ok and per_ok
        q_detail[cid] = {"pass": per_ok, "authoritative": auth_q.get("value"), "candidate": candidate_q.get("value")}
    checks["CORE08_Q6_AUTHORITY_TIER_AND_EHW_LIMITS_EXACT"] = _result(authority_q_ok, q_detail)

    c01_conflict = state_map.get("C01", {}).get("representation_conflicts", {}).get("cad_static_pose_vs_configuration_pose", {})
    conflict_ok = (
        c01_conflict.get("configuration_semantic_q6_rad") == Q_HOME
        and c01_conflict.get("cad_static_representation_q6_rad") == [0.0] * 6
        and c01_conflict.get("resolved") is False
        and c01_conflict.get("effect") == "CURRENT_COMPLETE_CONFIGURATION_GEOMETRY_FALSE"
    )
    checks["CORE09_C01_QHOME_VS_CAD_Q0_CONFLICT_EXPLICIT"] = _result(conflict_ok, c01_conflict)

    holds_ok = (
        "567P734_MM" in state_map["C05"]["non_authoritative_candidates"]["q6_rad"]["status"]
        and state_map["C05"]["operational_state"] == "HOLD_ABORT_ONLY"
        and "RATIFICATION_HOLD" in state_map["C06"]["non_authoritative_candidates"]["q6_rad"]["status"]
        and all("DIAGNOSTIC_CANDIDATE" in state_map[cid]["non_authoritative_candidates"]["q6_rad"]["status"] for cid in ("C07", "C08", "C09"))
    )
    checks["CORE10_C05_C06_C07_C09_HOLDS_PRESERVED"] = _result(holds_ok, {cid: state_map[cid]["non_authoritative_candidates"]["q6_rad"]["status"] for cid in ("C05", "C06", "C07", "C08", "C09")})

    gripper_ok = True
    structured_unknown_ok = True
    target_transform_ok = True
    for row in state_rows:
        auth = row["authoritative_state"]
        gripper_ok = gripper_ok and auth["gripper_joint1_m"]["value"] is None and auth["gripper_joint2_m"]["value"] is None
        gripper_ok = gripper_ok and auth["gripper_joint1_m"]["allowed_domain_m"] == [0.0, 0.0715] and auth["gripper_joint2_m"]["allowed_domain_m"] == [0.0, 0.0715]
        structured_unknown_ok = structured_unknown_ok and auth.get("solar_hdrm_state") == EXPECTED_SOLAR_HDRM_NULL
        structured_unknown_ok = structured_unknown_ok and auth.get("solar_latch_state") == EXPECTED_SOLAR_LATCH_NULL
        structured_unknown_ok = structured_unknown_ok and auth.get("arm_hdrm_state") == EXPECTED_ARM_HDRM_NULL
        target_transform_ok = target_transform_ok and auth["target"]["attachment_transform_S_rows"]["value"] is None
    checks["CORE11_GRIPPER_2P_VALUES_ALL_NULL_DOMAIN_ONLY"] = _result(gripper_ok, {"configurations": len(state_rows)})
    checks["CORE12_SOLAR_HDRM_LATCH_AND_ARM_HDRM_STRUCTURED_NULL"] = _result(structured_unknown_ok, {"configurations": len(state_rows)})
    checks["CORE13_TARGET_ATTACHMENT_TRANSFORMS_AUTHORITATIVE_NULL"] = _result(target_transform_ok, {"configurations": len(state_rows)})

    solar_ok = True
    for cid in CONFIG_NAMES:
        solar = state_map[cid]["authoritative_state"]["solar"]
        if cid == "C01":
            solar_ok = solar_ok and solar["logical_state"]["value"] == "DEPLOYED_NOMINAL_FIXED_SNAPSHOT"
            solar_ok = solar_ok and solar["left_transform_S_rows"]["value"] == [[-1.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 0.1154], [0.0, 0.0, 1.0, -0.10815], [0.0, 0.0, 0.0, 1.0]]
            solar_ok = solar_ok and solar["right_transform_S_rows"]["value"] == [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, -0.1154], [0.0, 0.0, 1.0, -0.10815], [0.0, 0.0, 0.0, 1.0]]
        elif cid in {"C02", "C03", "C04"}:
            solar_ok = solar_ok and solar["logical_state"]["value"] == {"C02": "LEFT_FAIL", "C03": "RIGHT_FAIL", "C04": "BOTH_FAIL"}[cid]
            solar_ok = solar_ok and solar["failure_retention_semantics"]["value"] == "ATTACHED_STUCK__JETTISON_FORBIDDEN"
            solar_ok = solar_ok and solar["left_transform_S_rows"]["value"] is None and solar["right_transform_S_rows"]["value"] is None
        else:
            solar_ok = solar_ok and solar["logical_state"]["value"] is None and solar["left_transform_S_rows"]["value"] is None and solar["right_transform_S_rows"]["value"] is None
    checks["CORE14_SOLAR_AUTHORITY_BOUND_ONLY_WHERE_SUPPORTED"] = _result(solar_ok, {cid: state_map[cid]["authoritative_state"]["solar"] for cid in CONFIG_NAMES})

    target_ok = True
    target_detail = {}
    for cid in ("C08", "C09"):
        target = state_map[cid]["authoritative_state"]["target"]
        model = sources["target_models"]["target_satellite_v0" if cid == "C08" else "target_debris_v0"]
        expected_mass = 22.0 if cid == "C08" else 150.0
        expected_id = "TARGET_SATELLITE_22KG" if cid == "C08" else "TARGET_DEBRIS_150KG"
        per_ok = target["scenario_member"]["value"] is True and target["target_attached"]["value"] is True
        per_ok = per_ok and target["target_id"]["value"] == expected_id and target["design_mass_kg"]["value"] == expected_mass
        per_ok = per_ok and target["design_inertia_diag_kg_m2"]["value"] == model["inertia_diag_kgm2"]
        per_ok = per_ok and target["confidence"] == model["confidence"] and target["operational_attachment_authority"] is False
        target_ok = target_ok and per_ok
        target_detail[cid] = {"pass": per_ok, "target": target}
    checks["CORE15_C08_C09_TARGET_DESIGN_SEMANTICS_LOW_CONFIDENCE_NO_ATTACHMENT_AUTHORITY"] = _result(target_ok, target_detail)

    geometry_rows = docs["geometry"]
    geom_map = {row.get("configuration_id"): row for row in geometry_rows}
    geometry_shape_ok = len(geometry_rows) == 9 and set(geom_map) == set(CONFIG_NAMES) and len(geom_map) == 9
    current_complete = sum(row.get("current_complete_integrated_geometry") == "true" for row in geometry_rows)
    topology_candidate = sum(row.get("current_source_only_topology_candidate") == "true" for row in geometry_rows)
    diagnostic = sum(row.get("diagnostic_m5_geometry_present") == "true" for row in geometry_rows)
    collision = sum(row.get("released_collision_clear") == "true" for row in geometry_rows)
    geom_counts_ok = geometry_shape_ok and current_complete == 0 and topology_candidate == 1 and diagnostic == 9 and collision == 0
    geom_counts_ok = geom_counts_ok and geom_map["C01"]["current_source_only_topology_candidate"] == "true"
    geom_counts_ok = geom_counts_ok and all(geom_map[cid]["current_complete_integrated_geometry"] == "false" for cid in CONFIG_NAMES)
    checks["CORE16_GEOMETRY_CURRENT_COMPLETE_0_TOPOLOGY_1_DIAGNOSTIC_9_COLLISION_0"] = _result(geom_counts_ok, {"current_complete": current_complete, "source_only_topology": topology_candidate, "diagnostic": diagnostic, "released_collision": collision})

    m5_witness_ok = True
    bbox_detail = {}
    bbox_leaf_count = 0
    for cid, source_row in m5_map.items():
        out = geom_map[cid]
        path = workspace / source_row["snapshot"]["path"]
        per_ok = path.exists() and sha256(path) == source_row["snapshot"]["sha256"]
        per_ok = per_ok and out["diagnostic_snapshot_path"] == source_row["snapshot"]["path"]
        per_ok = per_ok and out["diagnostic_snapshot_sha256"] == source_row["snapshot"]["sha256"]
        bbox_errors = []
        try:
            bbox_min = parse_bbox_cell(out.get("diagnostic_bbox_min_S_m"), f"geometry.{cid}.bbox_min")
            bbox_max = parse_bbox_cell(out.get("diagnostic_bbox_max_S_m"), f"geometry.{cid}.bbox_max")
            min_ok, min_count, min_errors = audit_binary64_tree(
                bbox_min, source_row["bbox_S_m"][0], f"geometry.{cid}.bbox_min"
            )
            max_ok, max_count, max_errors = audit_binary64_tree(
                bbox_max, source_row["bbox_S_m"][1], f"geometry.{cid}.bbox_max"
            )
            bbox_errors.extend(min_errors + max_errors)
            bbox_leaf_count += min_count + max_count
            bbox_ok = min_ok and max_ok and min_count == max_count == 3
            bbox_ok = bbox_ok and all(lo <= hi for lo, hi in zip(bbox_min, bbox_max))
        except StrictDataError as exc:
            bbox_min = None
            bbox_max = None
            bbox_ok = False
            bbox_errors.append(str(exc))
        per_ok = per_ok and bbox_ok
        per_ok = per_ok and out["diagnostic_mass_properties_authority"] == "false"
        per_ok = per_ok and out["diagnostic_verified_system_collision_clear"] == "false"
        m5_witness_ok = m5_witness_ok and per_ok
        bbox_detail[cid] = {
            "pass": bbox_ok,
            "bbox_min_S_m": bbox_min,
            "bbox_max_S_m": bbox_max,
            "type_or_bit_errors": bbox_errors,
        }
    checks["CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED"] = _result(
        m5_witness_ok,
        {"count": len(m5_map), "bbox_binary64_leaves_checked": bbox_leaf_count, "expected": 54, "bbox": bbox_detail},
    )

    dynamics_doc = docs["dynamics"]
    dynamics_rows = dynamics_doc.get("records", [])
    dyn_map = {row.get("configuration_id"): row for row in dynamics_rows}
    dynamics_ok = len(dynamics_rows) == 9 and set(dyn_map) == set(CONFIG_NAMES)
    for cid, row in dyn_map.items():
        dynamics_ok = dynamics_ok and row.get("maximum_permitted_use") == EXPECTED_DYNAMICS_USES[cid]
        dynamics_ok = dynamics_ok and row.get("design_mass_property_loading_allowed") is True
        dynamics_ok = dynamics_ok and row.get("current_geometry_collision_allowed") is False
        dynamics_ok = dynamics_ok and row.get("target_attachment_plant_allowed") is False
        dynamics_ok = dynamics_ok and row.get("non_abort_operational_authority") is False
        dynamics_ok = dynamics_ok and row.get("parent_gate_credit") is False
    dynamics_ok = dynamics_ok and dynamics_doc.get("parent_dynamics_gate_reissued") is False and dynamics_doc.get("next_stage_authorized") is False
    checks["CORE18_DYNAMICS_USE_MATRIX_FAIL_CLOSED_NO_PARENT_CREDIT"] = _result(dynamics_ok, {cid: dyn_map.get(cid, {}).get("maximum_permitted_use") for cid in CONFIG_NAMES})

    parent_ok = (
        sources["release_gate"].get("next_stage_authorized") is False
        and sources["configuration_ref"].get("next_stage_authorized") is False
        and sources["system_interface"].get("next_stage_authorized") is False
        and sources["m01_scene_schema"].get("next_stage_authorized") is False
        and sources["m01_prebind_gate"].get("next_stage_authorized") is False
        and sources["m01_prebind_gate"]["scene_accounting"]["stage_instances_bound"] == 0
        and sources["m01_prebind_gate"]["system_execution_state"]["system_pair_queries_executed"] == 0
    )
    checks["CORE19_PARENT_RELEASE_M01_AND_EXECUTION_AUTHORITY_FALSE"] = _result(parent_ok, {"m01_stage_instances": sources["m01_prebind_gate"]["scene_accounting"]["stage_instances_bound"], "m01_queries": sources["m01_prebind_gate"]["system_execution_state"]["system_pair_queries_executed"]})

    top_expected = {
        "source_lock": {"authority_upgrade": False, "parent_gate_credit": False, "next_stage_authorized": False},
        "crosswalk": {"parent_gate_credit": False, "next_stage_authorized": False},
        "state": {"parent_gate_credit": False, "next_stage_authorized": False},
        "mass": {"authority_upgrade": False, "parent_gate_credit": False, "next_stage_authorized": False},
        "dynamics": {"parent_dynamics_gate_reissued": False, "next_stage_authorized": False, "release_credit": False},
    }
    top_ok = all(
        all(docs[doc_id].get(key) is expected for key, expected in expected_fields.items())
        for doc_id, expected_fields in top_expected.items()
    )
    false_only_keys = {
        "authority", "authority_upgrade", "parent_gate_credit", "parent_gate_reissued",
        "parent_dynamics_gate_reissued", "next_stage_authorized", "release_credit",
        "non_abort_operational_authority", "operational_attachment_authority",
        "current_geometry_collision_allowed", "target_attachment_plant_allowed",
        "production_complete_state_vector", "continuous_state_complete",
        "discrete_state_complete", "released_collision_clear",
    }
    boundary_violations = []
    for doc_id in ("source_lock", "crosswalk", "state", "mass", "dynamics"):
        for path, key, value in walk_key_values(docs[doc_id]):
            if key in false_only_keys and value is not False:
                boundary_violations.append(f"{doc_id}:{path}.{key}={value!r}")
    top_ok = top_ok and not boundary_violations
    checks["CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE"] = _result(
        top_ok, {"top_level": top_expected, "violations": boundary_violations}
    )

    name_ok = True
    name_detail = {}
    local_maps = {
        "crosswalk": {row["configuration_id"]: row.get("contract_name") for row in cross_rows},
        "state": {row["configuration_id"]: row.get("name") for row in state_rows},
        "mass": {row["configuration_id"]: row.get("name") for row in mass_rows},
        "geometry": {row["configuration_id"]: row.get("name") for row in geometry_rows},
        "dynamics": {row["configuration_id"]: row.get("name") for row in dynamics_rows},
    }
    for cid, expected_name in CONFIG_NAMES.items():
        values = {doc_id: mapping.get(cid) for doc_id, mapping in local_maps.items()}
        per_ok = all(value == expected_name for value in values.values())
        name_ok = name_ok and per_ok
        name_detail[cid] = {"expected": expected_name, "values": values, "pass": per_ok}
    checks["CORE21_CONFIGURATION_NAMES_EXACT_ACROSS_ALL_FIVE_LOCAL_VIEWS"] = _result(name_ok, name_detail)

    state_boundary_ok = True
    for row in state_rows:
        state_boundary_ok = state_boundary_ok and row.get("production_complete_state_vector") is False
        state_boundary_ok = state_boundary_ok and row.get("continuous_state_complete") is False
        state_boundary_ok = state_boundary_ok and row.get("discrete_state_complete") is False
        state_boundary_ok = state_boundary_ok and row["authoritative_state"]["target"].get("operational_attachment_authority") is False
        state_boundary_ok = state_boundary_ok and row.get("operational_state") in {"HOLD_ABORT_ONLY", "NOT_OPERATIONALLY_AUTHORIZED"}
    for row in dynamics_rows:
        state_boundary_ok = state_boundary_ok and row.get("non_abort_operational_authority") is False
        state_boundary_ok = state_boundary_ok and row.get("current_geometry_collision_allowed") is False
        state_boundary_ok = state_boundary_ok and row.get("target_attachment_plant_allowed") is False
    state_boundary_ok = state_boundary_ok and all(
        row.get("current_complete_integrated_geometry") == "false"
        and row.get("released_collision_clear") == "false"
        for row in geometry_rows
    )
    checks["CORE22_OPERATIONAL_PRODUCTION_COMPLETE_COLLISION_AND_ATTACHMENT_ALL_HELD"] = _result(
        state_boundary_ok, {"configurations": 9, "production_complete": 0, "operational": 0, "released_collision": 0}
    )

    partial_ids = [row["configuration_id"] for row in geometry_rows if row.get("current_partial_master_geometry") == "true"]
    partial_ok = partial_ids == ["C01"]
    partial_ok = partial_ok and geom_map["C01"]["current_complete_integrated_geometry"] == "false"
    partial_ok = partial_ok and geom_map["C01"]["current_source_only_topology_candidate"] == "true"
    partial_ok = partial_ok and "PARTIAL_41_SOLID_MASTER" in geom_map["C01"]["current_geometry_status"]
    partial_ok = partial_ok and all(
        geom_map[cid]["current_partial_master_geometry"] == "false" for cid in CONFIG_NAMES if cid != "C01"
    )
    checks["CORE23_PARTIAL_GEOMETRY_ISOLATED_TO_C01_AND_NEVER_COMPLETE"] = _result(
        partial_ok, {"partial_configuration_ids": partial_ids, "complete_count": current_complete}
    )

    claim_ok = all(
        row.get("maximum_claim") == "DESIGN_DYNAMICS_INPUT_CANDIDATE_ONLY__NOT_AS_BUILT_NOT_RELEASED"
        and row.get("model_class") == "DESIGN_MODEL_R2_CANDIDATE_ONLY"
        for row in mass_rows
    )
    claim_ok = claim_ok and all(
        row.get("maximum_permitted_use") == EXPECTED_DYNAMICS_USES[row["configuration_id"]]
        for row in dynamics_rows
    )
    claim_ok = claim_ok and geom_map["C01"]["maximum_claim"] == "SOURCE_ONLY_TOPOLOGY_AND_PARTIAL_STATIC_GEOMETRY_CANDIDATE__NO_COLLISION_CREDIT"
    claim_ok = claim_ok and all(
        geom_map[cid]["maximum_claim"] == "DIAGNOSTIC_GEOMETRY_WITNESS_ONLY__NO_CURRENT_GEOMETRY_CREDIT"
        for cid in CONFIG_NAMES if cid != "C01"
    )
    checks["CORE24_MAXIMUM_CLAIMS_REMAIN_NARROW_AND_CONFIGURATION_SPECIFIC"] = _result(
        claim_ok, {cid: dyn_map[cid]["maximum_permitted_use"] for cid in CONFIG_NAMES}
    )

    local_contract_ok = (
        docs["source_lock"].get("schema") == "SOURCE_AUTHORITY_LOCK_V1"
        and docs["source_lock"].get("policy") == "EXACT_BYTES_AND_SHA256__FAIL_CLOSED_ON_ANY_SOURCE_CHANGE"
        and docs["crosswalk"].get("explicit_nonclaim") == "IDENTITY_CROSSWALK_DOES_NOT_CREATE_GEOMETRY_COLLISION_OR_OPERATIONAL_AUTHORITY"
        and docs["state"].get("unknown_policy") == "UNKNOWN_PHYSICAL_VALUES_ARE_NULL__ZERO_FILL_FORBIDDEN"
        and docs["mass"].get("model_class") == "DESIGN_MODEL_CANDIDATE_ONLY_NOT_AS_BUILT"
        and docs["mass"].get("as_built_configuration_count") == 0
        and docs["state"].get("production_complete_state_vector_count") == 0
    )
    checks["CORE25_LOCAL_CONTRACT_AUTHORITY_TEXT_AND_ZERO_COUNTS_EXACT"] = _result(
        local_contract_ok,
        {"as_built": docs["mass"].get("as_built_configuration_count"), "production_complete": docs["state"].get("production_complete_state_vector_count")},
    )

    all_core = all(item["pass"] for item in checks.values())
    return {"checks": checks, "pass": all_core, "failed": [key for key, value in checks.items() if not value["pass"]]}


def artifact_metadata(package: Path, filenames) -> dict[str, dict]:
    return {
        filename: {
            "bytes": (package / filename).stat().st_size,
            "sha256": sha256(package / filename),
        }
        for filename in filenames
    }


def evaluate_gate_integrity(gate, core_check_ids, local_metadata, spec_metadata, negative_total: int):
    criteria = gate.get("criteria", []) if isinstance(gate, dict) else []
    spec_binding = gate.get("contract_spec_binding") if isinstance(gate, dict) else None
    expected_criterion_ids = list(core_check_ids) + ["GATE26_NEGATIVE_CONTROLS_ALL_CAUGHT"]
    expected_summary = {
        "source_pins": "20_OF_20",
        "configuration_ids": "9_OF_9",
        "design_mass_properties": "9_OF_9",
        "complete_current_geometry": "0_OF_9",
        "source_only_current_topology": "1_OF_9",
        "diagnostic_geometry_witnesses": "9_OF_9",
        "released_collision": "0_OF_9",
        "production_complete_state_vectors": "0_OF_9",
        "as_built_mass_properties": "0_OF_9",
        "negative_controls": f"{negative_total}_OF_{negative_total}",
    }
    expected_local_files = set(CORE_FILES.values()) | {NEGATIVE_FILE}
    local_bindings = gate.get("local_artifact_bindings", {}) if isinstance(gate, dict) else {}
    gate_ok = (
        isinstance(gate, dict)
        and gate.get("schema") == "M4_L02_CONFIGURATION_STATE_CONTRACT_GATE_V1"
        and gate.get("gate_verdict") == VERDICT
        and [row.get("id") for row in criteria if isinstance(row, dict)] == expected_criterion_ids
        and len(criteria) == len(expected_criterion_ids)
        and all(isinstance(row, dict) and row.get("status") == "PASS" for row in criteria)
        and gate.get("summary") == expected_summary
        and gate.get("parent_gate_credit") is False
        and gate.get("parent_gate_reissued") is False
        and gate.get("next_stage_authorized") is False
        and gate.get("release_credit") is False
        and isinstance(local_bindings, dict)
        and set(local_bindings) == expected_local_files
        and set(local_metadata) == expected_local_files
    )
    if gate_ok:
        gate_ok = all(local_bindings.get(filename) == local_metadata[filename] for filename in expected_local_files)
    expected_spec_binding = {
        "path": SPEC_FILE,
        "bytes": spec_metadata.get("bytes"),
        "sha256": spec_metadata.get("sha256"),
        "schema": SPEC_SCHEMA,
    }
    gate_ok = gate_ok and spec_binding == expected_spec_binding
    return _result(
        gate_ok,
        {
            "criterion_count": len(criteria),
            "expected_criterion_count": len(expected_criterion_ids),
            "local_binding_count": len(local_bindings) if isinstance(local_bindings, dict) else None,
            "expected_summary": expected_summary,
        },
    )


def evaluate_manifest_integrity(rows, artifact_meta):
    rows_are_mappings = isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
    paths = [row.get("path") for row in rows] if rows_are_mappings else []
    paths_are_unique_strings = rows_are_mappings and all(type(path) is str for path in paths) and _unique_count(paths) == len(paths)
    manifest_map = {row.get("path"): row for row in rows} if paths_are_unique_strings else {}
    expected_files = EXPECTED_MANIFEST_FILES
    manifest_ok = (
        rows_are_mappings
        and paths_are_unique_strings
        and len(rows) == len(manifest_map) == len(expected_files)
        and _unique_count(paths) == len(expected_files)
        and set(manifest_map) == expected_files
        and set(artifact_meta) == expected_files
        and set(EXPECTED_MANIFEST_ROLES) == expected_files
        and MANIFEST_FILE not in manifest_map
    )
    if manifest_ok:
        for rel in expected_files:
            row = manifest_map[rel]
            expected = artifact_meta[rel]
            row_ok = (
                set(row) == {"path", "bytes", "sha256", "role"}
                and row.get("path") == rel
                and row.get("bytes") == str(expected["bytes"])
                and row.get("sha256") == expected["sha256"]
                and row.get("role") == EXPECTED_MANIFEST_ROLES[rel]
            )
            manifest_ok = manifest_ok and row_ok
    return _result(
        manifest_ok,
        {
            "records": len(rows) if isinstance(rows, list) else None,
            "expected": len(expected_files),
            "unique": _unique_count(paths) if rows_are_mappings else 0,
            "roles_exact": manifest_ok,
            "self_excluded": MANIFEST_FILE not in manifest_map,
        },
    )


def run_negative_controls(package: Path = PACKAGE, workspace: Path = WORKSPACE):
    baseline = load_core_docs(package)
    controls = []

    def parser_control(control_id: str, title: str, parser, payload: str):
        caught = False
        error = None
        try:
            parser(payload)
        except StrictDataError as exc:
            caught = True
            error = str(exc)
        controls.append({"id": control_id, "title": title, "caught": caught, "expected_failed_check": "STRICT_PARSER", "observed": error})

    def mutation_control(control_id: str, title: str, mutate, expected_check: str):
        docs = copy.deepcopy(baseline)
        mutate(docs)
        result = evaluate_core(docs, workspace)
        caught = expected_check in result["failed"]
        controls.append({"id": control_id, "title": title, "caught": caught, "expected_failed_check": expected_check, "observed_failed_checks": [expected_check] if caught else []})

    parser_control("NC01_DUPLICATE_JSON_KEY", "duplicate JSON keys are rejected", strict_json_loads, '{"a":1,"a":2}')
    parser_control("NC02_NONFINITE_YAML", "YAML NaN is rejected", strict_yaml_loads, "a: .nan\n")
    mutation_control(
        "NC03_C05_CANDIDATE_Q_PROMOTION",
        "held C05 q6 cannot be promoted to authoritative state",
        lambda d: d["state"]["configurations"][4]["authoritative_state"]["q6_rad"].update({"value": Q_STOW, "status": "AUTHORITY_BOUND_ACCEPTED_RUNTIME_DIGITAL_POSE"}),
        "CORE08_Q6_AUTHORITY_TIER_AND_EHW_LIMITS_EXACT",
    )
    mutation_control(
        "NC04_C05_HOLD_REMOVAL",
        "C05 567.734 mm FK hold cannot be erased",
        lambda d: d["state"]["configurations"][4]["non_authoritative_candidates"]["q6_rad"].update({"status": "PASS"}),
        "CORE10_C05_C06_C07_C09_HOLDS_PRESERVED",
    )
    mutation_control(
        "NC05_C08_ATTACHMENT_TRANSFORM_PROMOTION",
        "display-only target transform cannot enter authoritative state",
        lambda d: d["state"]["configurations"][7]["authoritative_state"]["target"]["attachment_transform_S_rows"].update({"value": [[1, 0, 0, 1.24], [0, 1, 0, 0], [0, 0, 1, -0.1], [0, 0, 0, 1]]}),
        "CORE13_TARGET_ATTACHMENT_TRANSFORMS_AUTHORITATIVE_NULL",
    )
    mutation_control(
        "NC06_DIAGNOSTIC_GEOMETRY_PROMOTION",
        "M5 diagnostic geometry cannot be promoted to current integrated geometry",
        lambda d: d["geometry"][1].update({"current_complete_integrated_geometry": "true"}),
        "CORE16_GEOMETRY_CURRENT_COMPLETE_0_TOPOLOGY_1_DIAGNOSTIC_9_COLLISION_0",
    )
    mutation_control(
        "NC07_PARENT_GATE_CREDIT_TRUE",
        "configuration matrix cannot grant parent Gate credit",
        lambda d: d["dynamics"]["records"][0].update({"parent_gate_credit": True}),
        "CORE18_DYNAMICS_USE_MATRIX_FAIL_CLOSED_NO_PARENT_CREDIT",
    )
    mutation_control(
        "NC08_MASS_TAMPER",
        "mass-property view must remain bit-exact to V3_R2",
        lambda d: d["mass"]["configurations"][0].update({"mass_kg": d["mass"]["configurations"][0]["mass_kg"] + 1.0}),
        "CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED",
    )
    mutation_control(
        "NC09_SOURCE_HASH_TAMPER",
        "source lock hash tampering is detected",
        lambda d: d["source_lock"]["sources"][0].update({"sha256": "0" * 64}),
        "CORE01_SOURCE_PINS_EXACT",
    )
    mutation_control(
        "NC10_GRIPPER_ZERO_FILL",
        "unknown gripper state cannot be zero-filled",
        lambda d: d["state"]["configurations"][0]["authoritative_state"]["gripper_joint1_m"].update({"value": 0.0}),
        "CORE11_GRIPPER_2P_VALUES_ALL_NULL_DOMAIN_ONLY",
    )
    parser_control("NC11_NONFINITE_JSON_INFINITY", "JSON Infinity is rejected", strict_json_loads, '{"a":Infinity}')
    parser_control("NC12_DUPLICATE_YAML_KEY", "duplicate YAML keys are rejected", strict_yaml_loads, "a: 1\na: 2\n")
    mutation_control(
        "NC13_MASS_TYPE_DOWNCAST",
        "binary64 mass leaves cannot be downcast to integer",
        lambda d: d["mass"]["configurations"][0].update({"mass_kg": 31}),
        "CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED",
    )
    mutation_control(
        "NC14_MASS_ONE_ULP_TAMPER",
        "one-ULP mass changes are detected",
        lambda d: d["mass"]["configurations"][0].update({"mass_kg": math.nextafter(d["mass"]["configurations"][0]["mass_kg"], math.inf)}),
        "CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED",
    )
    mutation_control(
        "NC15_TOP_LEVEL_NEXT_STAGE_TRUE",
        "top-level next-stage authority cannot be promoted",
        lambda d: d["state"].update({"next_stage_authorized": True}),
        "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE",
    )
    mutation_control(
        "NC16_TOP_LEVEL_RELEASE_CREDIT_TRUE",
        "top-level release credit cannot be promoted",
        lambda d: d["dynamics"].update({"release_credit": True}),
        "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE",
    )
    mutation_control(
        "NC17_OPERATIONAL_AUTHORITY_TRUE",
        "non-abort operational authority cannot be promoted",
        lambda d: d["dynamics"]["records"][0].update({"non_abort_operational_authority": True}),
        "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE",
    )
    mutation_control(
        "NC18_PRODUCTION_COMPLETE_TRUE",
        "incomplete state vectors cannot be marked production complete",
        lambda d: d["state"]["configurations"][0].update({"production_complete_state_vector": True}),
        "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE",
    )
    mutation_control(
        "NC19_PARTIAL_GEOMETRY_SPREAD",
        "partial master geometry cannot spread beyond C01",
        lambda d: d["geometry"][1].update({"current_partial_master_geometry": "true"}),
        "CORE23_PARTIAL_GEOMETRY_ISOLATED_TO_C01_AND_NEVER_COMPLETE",
    )
    mutation_control(
        "NC20_CONFIGURATION_NAME_DRIFT",
        "configuration names must agree across every local view",
        lambda d: d["mass"]["configurations"][0].update({"name": "DEPLOYED_NOMINAL_DRIFT"}),
        "CORE21_CONFIGURATION_NAMES_EXACT_ACROSS_ALL_FIVE_LOCAL_VIEWS",
    )

    baseline_core_result = evaluate_core(baseline, workspace)
    baseline_gate = read_json(package / GATE_FILE)
    baseline_manifest = read_manifest_csv(package / MANIFEST_FILE)
    local_meta = artifact_metadata(package, list(CORE_FILES.values()) + [NEGATIVE_FILE])
    manifest_meta = artifact_metadata(package, EXPECTED_MANIFEST_FILES)
    spec_path = package / SPEC_FILE
    spec_meta = {"bytes": spec_path.stat().st_size, "sha256": sha256(spec_path)}
    baseline_gate_ok = evaluate_gate_integrity(
        baseline_gate, baseline_core_result["checks"], local_meta, spec_meta, len(NEGATIVE_CONTROL_IDS)
    )["pass"]
    baseline_manifest_ok = evaluate_manifest_integrity(baseline_manifest, manifest_meta)["pass"]

    def full_integrity_control(control_id: str, title: str, expected_check: str, mutate, layer: str):
        gate_candidate = copy.deepcopy(baseline_gate)
        manifest_candidate = copy.deepcopy(baseline_manifest)
        mutate(gate_candidate, manifest_candidate)
        if layer == "gate":
            candidate_ok = evaluate_gate_integrity(
                gate_candidate,
                baseline_core_result["checks"],
                local_meta,
                spec_meta,
                len(NEGATIVE_CONTROL_IDS),
            )["pass"]
            caught = baseline_gate_ok and not candidate_ok
        elif layer == "manifest":
            candidate_ok = evaluate_manifest_integrity(manifest_candidate, manifest_meta)["pass"]
            caught = baseline_manifest_ok and not candidate_ok
        else:
            raise AssertionError(layer)
        controls.append({
            "id": control_id,
            "title": title,
            "caught": caught,
            "expected_failed_check": expected_check,
            "observed_failed_checks": [expected_check] if caught else [],
        })

    full_integrity_control(
        "NC21_GATE_LOCAL_HASH_TAMPER", "Gate local artifact hash tampering is detected",
        "FULL27_GATE_COUNTS_FLAGS_SPEC_AND_LOCAL_BINDINGS",
        lambda g, m: g["local_artifact_bindings"][CORE_FILES["source_lock"]].update({"sha256": "0" * 64}),
        "gate",
    )
    full_integrity_control(
        "NC22_MANIFEST_EXTRA_ROW", "manifest extra rows are rejected",
        "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED",
        lambda g, m: m.append({"path": "EXTRA.txt", "bytes": "0", "sha256": "0" * 64, "role": "EXTRA"}),
        "manifest",
    )
    full_integrity_control(
        "NC23_MANIFEST_DUPLICATE_ROW", "manifest duplicate rows are rejected",
        "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED",
        lambda g, m: m.append(copy.deepcopy(m[0])),
        "manifest",
    )
    mutation_control(
        "NC24_SOURCE_PATH_TAMPER",
        "source lock paths cannot drift even when hash text is unchanged",
        lambda d: d["source_lock"]["sources"][0].update({"path": "../escape"}),
        "CORE01_SOURCE_PINS_EXACT",
    )
    full_integrity_control(
        "NC25_SPEC_BINDING_HASH_TAMPER", "frozen spec binding hash tampering is detected",
        "FULL27_GATE_COUNTS_FLAGS_SPEC_AND_LOCAL_BINDINGS",
        lambda g, m: g["contract_spec_binding"].update({"sha256": "0" * 64}),
        "gate",
    )
    mutation_control(
        "NC26_SOURCE_LOCK_DUPLICATE_ID",
        "duplicate source-lock IDs are rejected even when raw row count remains 20",
        lambda d: d["source_lock"]["sources"][1].update({"source_id": d["source_lock"]["sources"][0]["source_id"]}),
        "CORE01_SOURCE_PINS_EXACT",
    )
    mutation_control(
        "NC27_SOURCE_LOCK_DUPLICATE_PATH",
        "duplicate source-lock paths are rejected",
        lambda d: d["source_lock"]["sources"][1].update({"path": d["source_lock"]["sources"][0]["path"]}),
        "CORE01_SOURCE_PINS_EXACT",
    )
    mutation_control(
        "NC28_SOURCE_LOCK_COUNT_TAMPER",
        "source-lock declared count must be an exact integer equal to raw and mapped counts",
        lambda d: d["source_lock"].update({"source_count": 20.0}),
        "CORE01_SOURCE_PINS_EXACT",
    )
    mutation_control(
        "NC29_SOURCE_LOCK_ALL_MATCH_FALSE",
        "source-lock aggregate match flag must remain true",
        lambda d: d["source_lock"].update({"all_sources_match": False}),
        "CORE01_SOURCE_PINS_EXACT",
    )
    mutation_control(
        "NC30_STRUCTURED_NULL_EMPTY_MAPPING",
        "empty mappings cannot masquerade as structured unknown hardware state",
        lambda d: d["state"]["configurations"][0]["authoritative_state"]["solar_hdrm_state"].update({"value": {}}),
        "CORE12_SOLAR_HDRM_LATCH_AND_ARM_HDRM_STRUCTURED_NULL",
    )
    mutation_control(
        "NC31_GEOMETRY_BBOX_MALFORMED_JSON",
        "diagnostic bbox cells must be strict finite JSON binary64 triples",
        lambda d: d["geometry"][0].update({"diagnostic_bbox_min_S_m": "[0.0,NaN,1.0]"}),
        "CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED",
    )
    mutation_control(
        "NC32_GEOMETRY_BBOX_ONE_ULP_TAMPER",
        "one-ULP diagnostic bbox drift from M5 is detected",
        lambda d: d["geometry"][0].update({
            "diagnostic_bbox_min_S_m": json.dumps(
                [math.nextafter(parse_bbox_cell(d["geometry"][0]["diagnostic_bbox_min_S_m"], "nc32")[0], math.inf)]
                + parse_bbox_cell(d["geometry"][0]["diagnostic_bbox_min_S_m"], "nc32")[1:],
                separators=(",", ":"),
                allow_nan=False,
            )
        }),
        "CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED",
    )
    mutation_control(
        "NC33_DESIGN_CHECK_BOOLEAN_TAMPER",
        "every design_checks_from_ssot field is independently source-bound",
        lambda d: d["mass"]["configurations"][0]["design_checks_from_ssot"].update({"non_solar_members_carried_verbatim": False}),
        "CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS",
    )
    mutation_control(
        "NC34_MIN_EIGENVALUE_ONE_ULP_TAMPER",
        "one-ULP minimum-eigenvalue drift is detected",
        lambda d: d["mass"]["configurations"][0]["design_checks_from_ssot"].update({
            "min_eigenvalue_kg_m2": math.nextafter(
                d["mass"]["configurations"][0]["design_checks_from_ssot"]["min_eigenvalue_kg_m2"], math.inf
            )
        }),
        "CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS",
    )
    full_integrity_control(
        "NC35_MANIFEST_ROLE_TAMPER",
        "manifest roles are exact contract fields",
        "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED",
        lambda g, m: m[0].update({"role": "WRONG_ROLE"}),
        "manifest",
    )
    if [control["id"] for control in controls] != NEGATIVE_CONTROL_IDS:
        raise AssertionError("negative-control ID/order drift from frozen spec")
    passed = sum(control["caught"] for control in controls)
    return {
        "schema": "M4_L02_NEGATIVE_CONTROL_RESULTS_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "authority": "FALSIFICATION_EVIDENCE_ONLY__NO_PARENT_GATE_CREDIT",
        "controls": controls,
        "summary": {"passed": passed, "total": len(controls), "all_caught": passed == len(controls)},
        "next_stage_authorized": False,
        "release_credit": False,
    }


def validate_full(package: Path = PACKAGE, workspace: Path = WORKSPACE):
    core_docs = load_core_docs(package)
    core = evaluate_core(core_docs, workspace)
    checks = {key: value for key, value in core["checks"].items()}

    negative = read_json(package / NEGATIVE_FILE)
    expected_negative = run_negative_controls(package, workspace)
    negative_ok = (
        negative == expected_negative
        and negative.get("summary", {}).get("all_caught") is True
        and negative.get("summary", {}).get("passed") == len(NEGATIVE_CONTROL_IDS)
        and negative.get("next_stage_authorized") is False
        and negative.get("release_credit") is False
    )
    checks[f"FULL26_NEGATIVE_CONTROLS_{len(NEGATIVE_CONTROL_IDS)}_OF_{len(NEGATIVE_CONTROL_IDS)}_BYTE_SEMANTIC_MATCH"] = _result(negative_ok, negative.get("summary"))

    gate = read_json(package / GATE_FILE)
    spec_path = package / SPEC_FILE
    gate_check = evaluate_gate_integrity(
        gate,
        core["checks"],
        artifact_metadata(package, list(CORE_FILES.values()) + [NEGATIVE_FILE]),
        {"bytes": spec_path.stat().st_size, "sha256": sha256(spec_path)},
        len(NEGATIVE_CONTROL_IDS),
    )
    checks["FULL27_GATE_COUNTS_FLAGS_SPEC_AND_LOCAL_BINDINGS"] = gate_check

    manifest_path = package / MANIFEST_FILE
    rows = read_manifest_csv(manifest_path)
    manifest_check = evaluate_manifest_integrity(
        rows, artifact_metadata(package, EXPECTED_MANIFEST_FILES)
    )
    checks["FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED"] = manifest_check

    architecture_detail = {}
    architecture_ok = True
    forbidden_by_file = {
        "build_configuration_contract.py": {"validate_configuration_contract"},
        "validate_configuration_contract.py": {"build_configuration_contract"},
        SPEC_FILE: {"build_configuration_contract", "validate_configuration_contract"},
    }
    for filename, forbidden in forbidden_by_file.items():
        tree = ast.parse((package / filename).read_text(encoding="utf-8"), filename=filename)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        violations = sorted(name for name in imported if name.split(".")[0] in forbidden)
        per_ok = not violations
        architecture_ok = architecture_ok and per_ok
        architecture_detail[filename] = {"imports": sorted(imported), "forbidden_hits": violations, "pass": per_ok}
    checks["FULL29_BUILDER_VALIDATOR_SPEC_IMPORT_GRAPH_ACYCLIC"] = _result(architecture_ok, architecture_detail)

    all_pass = all(item["pass"] for item in checks.values())
    return {
        "schema": "M4_L02_CONFIGURATION_STATE_CONTRACT_VALIDATION_V1",
        "verdict": "PASS" if all_pass else "FAIL",
        "checks": checks,
        "summary": {"passed": sum(item["pass"] for item in checks.values()), "total": len(checks), "failed": [key for key, value in checks.items() if not value["pass"]]},
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-controls-json", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit full validation JSON")
    args = parser.parse_args(argv)
    if args.negative_controls_json:
        print(json.dumps(run_negative_controls(), sort_keys=True, ensure_ascii=False, allow_nan=False))
        return 0
    result = validate_full()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
    else:
        print(f"{result['verdict']} {result['summary']['passed']}/{result['summary']['total']}")
        if result["summary"]["failed"]:
            print("failed:", ", ".join(result["summary"]["failed"]))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
