"""Independent stdlib-only audit of the B4G-R2 tooling source freeze.

The audit deliberately does not import the validator, tests, ``r2_preflight``,
or any historical numerical module.  Matrix, blocked schedule, donor group,
canonical hashes, inventory, governance, and negative-control evidence are
rederived here.  No physics or trajectory is evaluated.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
SOURCE_BINDINGS = HERE / "contracts/PHASE_B4G_R2_EXECUTION_SOURCE_BINDINGS_V1.json"
FREEZE_CONTRACT = HERE / "contracts/PHASE_B4G_R2_EXECUTION_TOOLING_FREEZE_CONTRACT_V1.json"
GOVERNANCE = HERE / "contracts/PHASE_B4G_R2_EXECUTION_GOVERNANCE_V1.json"
NC_CONTRACT = HERE / "contracts/PHASE_B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROL_EVIDENCE_CONTRACT_V1.json"
NC_EVIDENCE = HERE / "evidence/SIM13_V4B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROLS_V1.json"
MANIFEST = HERE / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1.json"
VALIDATION = HERE / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_VALIDATION_V1.json"
OUTPUT = HERE / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT_V1.json"
GATE_OUTPUT = HERE / "results/SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_GATE_V1.json"
TERMINAL_OUTPUT = HERE / "results/SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json"

MATRIX_SHA256 = "D7B23B92DA46A6F9E96CF856914C7D5AECAD26240141C7F2B637A2AF119B7BEB"
SCHEDULE_SHA256 = "259EB3A99C0C0A45A6C80AEB979E2F15F3023804128517192C24D1B8A8F20EC7"
SCHEDULE_SEED = 20260825
DONOR_RAW_BYTES = 69249
DONOR_RAW_SHA256 = "5DF0C19A71180E1BD91816235AAD50108613C2BC0F99F950018D786119CF9D4F"
DONOR_PAYLOAD_BYTES = 31092
DONOR_PAYLOAD_SHA256 = "DA3E10D7D30DFD9BABFB71BF055D62A1BD06CF8DE3023E463A649FF92A952D15"
COMMON_GROUP_BYTES = 1317
COMMON_GROUP_SHA256 = "396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444"
RAW_INVENTORY_SHA256 = "916F395EFEEEE3C234C7D3F361BFFB6134D060577A05ADEE0166F8F19CD43DD5"
EXPECTED_CRITICAL_ROOTS = {
    "r2_contract_gate": "8DB747F8C57F898B25B15273C691A1007F4E452EB688865EEFAE2BA81E4A0298",
    "r2_contract_terminal": "286088014FD4B84263C17521E24224B8338B42214440DF8ED1593BE29A666C07",
    "b4g_active_source_freeze_terminal": "B22C4D5B4C0E15FF58484D252A2316E6B42458423079E2324D6455CC09EF3464",
    "b4g_active_invalidation": "2743FBD314CCA3EAA6FB5F4985DF8F65697E5BD968DE6DEB2AD58F0521FAB1D9",
    "b4g_r1_failure_closure_gate": "AE7E81F66CF6A5EC218CBB8E3FC4A1EC923A49E2CF0CAFC6681EEC449D855C68",
    "b4g_r1_terminal": "A1B2BD2FC051DC3CB853B7B081E0B56DB5776A48DEB7318E656F396ABAA516EC",
}
HEX64 = set("0123456789ABCDEF")

LANES = (
    ("RK4_H_MS_0P25", "rk4", 0.00025),
    ("RK4_H_MS_0P125", "rk4", 0.000125),
    ("RK4_H_MS_0P0625", "rk4", 0.0000625),
    ("MIDPOINT_H_MS_0P25", "midpoint", 0.00025),
    ("MIDPOINT_H_MS_0P125", "midpoint", 0.000125),
    ("MIDPOINT_H_MS_0P0625", "midpoint", 0.0000625),
)
FORBIDDEN_SUFFIXES = {".npz", ".csv", ".urdf", ".step", ".stp", ".pyc", ".tmp"}
FORBIDDEN_DIRECTORIES = {"__pycache__", ".pytest_cache", "raw", "raw_cases"}
FORBIDDEN_FILENAME_SUBSTRINGS = {"solver"}
FORBIDDEN_IMPORT_TOKENS = {"b4g_solver", "b4_solver", "full_floating", "campaign", "forced_retraction"}


class IndependentAuditError(RuntimeError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IndependentAuditError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _reject_constant(token: str) -> None:
    raise IndependentAuditError(f"NONFINITE_JSON_TOKEN:{token}")


def _validate_tree(value: Any, *, allow_null: bool = False, pointer: str = "") -> None:
    if value is None:
        if allow_null:
            return
        raise IndependentAuditError(f"NULL_JSON_LEAF:{pointer or '/'}")
    if isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise IndependentAuditError(f"NONFINITE_JSON_NUMBER:{pointer or '/'}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_tree(item, allow_null=allow_null, pointer=f"{pointer}/{index}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise IndependentAuditError(f"NONSTRING_JSON_KEY:{pointer or '/'}")
            escaped = key.replace("~", "~0").replace("/", "~1")
            _validate_tree(item, allow_null=allow_null, pointer=f"{pointer}/{escaped}")
        return
    raise IndependentAuditError(f"NON_JSON_TYPE:{pointer or '/'}:{type(value).__name__}")


def load(path: Path, *, allow_null: bool = False) -> Any:
    if not path.is_file() or path.is_symlink():
        raise IndependentAuditError(f"REGULAR_JSON_FILE_REQUIRED:{path}")
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=_reject_constant,
    )
    _validate_tree(value, allow_null=allow_null)
    return value


def canonical_bytes(value: Any) -> bytes:
    _validate_tree(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    _validate_tree(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _source_candidates(package_root: Path) -> Iterable[Path]:
    root = Path(package_root).resolve()
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.suffix.lower() in {".py", ".md", ".ini"}:
            yield path
    for subtree, suffixes in (("r2_preflight", {".py"}), ("contracts", {".json"}), ("tests", {".py"})):
        base = root / subtree
        if not base.exists():
            continue
        for path in sorted(base.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file() and path.suffix.lower() in suffixes:
                yield path


def local_inventory(package_root: Path) -> list[dict[str, Any]]:
    root = Path(package_root).resolve()
    rows: list[dict[str, Any]] = []
    for path in _source_candidates(root):
        if _is_link_or_reparse(path):
            raise IndependentAuditError(f"LOCAL_SOURCE_LINK_OR_REPARSE:{path}")
        rows.append({"path": path.resolve().relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    rows.sort(key=lambda row: row["path"])
    if not rows or len({row["path"] for row in rows}) != len(rows):
        raise IndependentAuditError("EMPTY_OR_DUPLICATE_LOCAL_SOURCE_INVENTORY")
    return rows


def _alpha_token(alpha: float | int) -> str:
    return "0P5" if float(alpha) == 0.5 else str(int(alpha))


def _fresh_a1_id(lane: str, alpha: float | int, duration_ms: int) -> str:
    return f"FRESH__{lane}__A1__A_{_alpha_token(alpha)}__T_MS_{duration_ms}"


def independent_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane, method, step_s in LANES:
        for sentinel in ("PRE", "POST"):
            rows.append({
                "case_id": f"FRESH__{lane}__A0__{sentinel}", "execution_family": "FRESH", "roles": ["A0_BOOKEND"],
                "lane_id": lane, "method": method, "step_s": step_s, "arm": "A0", "sentinel": sentinel,
                "alpha": "NOT_APPLICABLE_A0", "command_duration_s": "NOT_APPLICABLE_A0",
                "initial_state": "LANE_SPECIFIC_FRESH_B3", "g12_credit": False, "selector_input": False,
            })
        for duration in (5, 10, 20):
            roles = ["FRESH_ALPHA16_PROPAGATION"]
            if duration == 10:
                roles.append("FRESH_ACQ_OBSERVATION")
            if step_s == 0.0000625:
                roles.append("G12_FRESH_REFERENCE")
            rows.append({
                "case_id": _fresh_a1_id(lane, 16, duration), "execution_family": "FRESH", "roles": roles,
                "lane_id": lane, "method": method, "step_s": step_s, "arm": "A1", "sentinel": "NOT_APPLICABLE_A1",
                "alpha": 16.0, "command_duration_s": duration / 1000, "initial_state": "LANE_SPECIFIC_FRESH_B3",
                "g12_credit": step_s == 0.0000625, "selector_input": step_s == 0.0000625,
            })
        if step_s == 0.0000625:
            for alpha in (0.5, 1, 2, 4, 8):
                for duration in (5, 10, 20):
                    rows.append({
                        "case_id": _fresh_a1_id(lane, alpha, duration), "execution_family": "FRESH", "roles": ["G12_FRESH_REFERENCE"],
                        "lane_id": lane, "method": method, "step_s": step_s, "arm": "A1", "sentinel": "NOT_APPLICABLE_A1",
                        "alpha": float(alpha), "command_duration_s": duration / 1000, "initial_state": "LANE_SPECIFIC_FRESH_B3",
                        "g12_credit": True, "selector_input": True,
                    })
        for duration in (5, 10, 20):
            rows.append({
                "case_id": f"COMMON_PROP__{lane}__A_16__T_MS_{duration}", "execution_family": "COMMON_PROP",
                "roles": ["COMMON_PROPAGATION_DIAGNOSTIC"], "lane_id": lane, "method": method, "step_s": step_s,
                "arm": "A1", "sentinel": "NOT_APPLICABLE_A1", "alpha": 16.0, "command_duration_s": duration / 1000,
                "initial_state": f"COMMON_STATE_GROUP_{COMMON_GROUP_SHA256}", "g12_credit": False, "selector_input": False,
            })
    return sorted(rows, key=lambda row: row["case_id"])


def independent_schedule() -> list[str]:
    def key(namespace: str, item: str) -> str:
        return hashlib.sha256(f"{SCHEDULE_SEED}|{namespace}|{item}".encode("utf-8")).hexdigest()

    result: list[str] = []
    nonreference = sorted((lane for lane, _, step in LANES if step != 0.0000625), key=lambda lane: key("NONREFERENCE_LANE_ORDER", lane))
    for lane in nonreference:
        result.append(f"FRESH__{lane}__A0__PRE")
        cases = [_fresh_a1_id(lane, 16, duration) for duration in (5, 10, 20)]
        result.extend(sorted(cases, key=lambda case: key(f"FRESH_LANE__{lane}", case)))
        result.append(f"FRESH__{lane}__A0__POST")
    references = tuple(lane for lane, _, step in LANES if step == 0.0000625)
    result.extend(sorted((f"FRESH__{lane}__A0__PRE" for lane in references), key=lambda case: key("REFERENCE_A0_PRE", case)))
    levels = [(alpha, duration) for alpha in (0.5, 1, 2, 4, 8, 16) for duration in (5, 10, 20)]
    levels.sort(key=lambda item: key("G12_LEVEL", f"{item[0]}|{item[1]}"))
    for alpha, duration in levels:
        pair = [_fresh_a1_id(lane, alpha, duration) for lane in references]
        result.extend(sorted(pair, key=lambda case: key(f"G12_PAIR__{_alpha_token(alpha)}__{duration}", case)))
    result.extend(sorted((f"FRESH__{lane}__A0__POST" for lane in references), key=lambda case: key("REFERENCE_A0_POST", case)))
    durations = sorted((5, 10, 20), key=lambda duration: key("COMMON_DURATION", str(duration)))
    for duration in durations:
        block = [f"COMMON_PROP__{lane}__A_16__T_MS_{duration}" for lane, _, _ in LANES]
        result.extend(sorted(block, key=lambda case: key(f"COMMON_DURATION__{duration}", case)))
    return result


def _row_by_id(bindings: dict[str, Any], identifier: str) -> dict[str, Any]:
    rows = [row for row in bindings["sources"] if row["id"] == identifier]
    if len(rows) != 1:
        raise IndependentAuditError(f"SOURCE_ID_CARDINALITY:{identifier}")
    return rows[0]


def _source_bindings_check(bindings: dict[str, Any]) -> dict[str, Any]:
    rows = bindings.get("sources", [])
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    valid = True
    for row in rows:
        raw_path = Path(row["path"])
        path = (PROJECT_ROOT / raw_path).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
            contained = not raw_path.is_absolute() and not any(part in {"", ".", ".."} for part in raw_path.parts)
        except ValueError:
            contained = False
        valid = bool(valid and contained and set(row) == {"id", "path", "role", "bytes", "sha256"} and path.is_file() and not _is_link_or_reparse(path) and path.stat().st_size == row["bytes"] and sha(path) == row["sha256"])
    policy = bindings.get("execution_authority_policy", {})
    valid = bool(valid and len(rows) == 22 and len(ids) == len(set(ids)) and policy.get("bound_direct_owner_source_id") == "NOT_AVAILABLE_NO_EXECUTION_AUTHORITY" and policy.get("current_execution_authorized") is False)
    return {"passed": valid, "source_count": len(rows), "unique_ids": len(set(ids))}


def _critical_binding_roots_check(bindings: dict[str, Any]) -> dict[str, Any]:
    contract = load(FREEZE_CONTRACT)
    roots = contract["frozen_parent_roots"]
    mapping = {
        "r2_contract_gate": "r2_contract_gate_sha256",
        "r2_contract_terminal": "r2_contract_terminal_sha256",
        "b4g_active_source_freeze_terminal": "b4g_active_source_freeze_terminal_sha256",
        "b4g_active_invalidation": "b4g_active_invalidation_sha256",
        "b4g_r1_failure_closure_gate": "b4g_r1_gate_sha256",
        "b4g_r1_terminal": "b4g_r1_terminal_sha256",
    }
    observed = {source_id: _row_by_id(bindings, source_id)["sha256"] for source_id in mapping}
    contract_roots = {source_id: roots[contract_key] for source_id, contract_key in mapping.items()}
    passed = observed == contract_roots == EXPECTED_CRITICAL_ROOTS
    donor = _row_by_id(bindings, "common_prop_donor_raw_slot_052")
    passed = bool(passed and donor["bytes"] == DONOR_RAW_BYTES and donor["sha256"] == DONOR_RAW_SHA256)
    return {"passed": passed, "critical_root_count": len(mapping), "observed": observed, "literal_expected": EXPECTED_CRITICAL_ROOTS}


def _raw_inventory_check(bindings: dict[str, Any]) -> dict[str, Any]:
    spec = bindings["preserved_raw_inventory"]
    raw_path = Path(spec["path"])
    root = (PROJECT_ROOT / raw_path).resolve()
    try:
        root.relative_to(PROJECT_ROOT.resolve())
        contained = not raw_path.is_absolute() and not any(part in {"", ".", ".."} for part in raw_path.parts)
    except ValueError:
        contained = False
    if not contained or not root.is_dir() or _is_link_or_reparse(root):
        return {"passed": False, "reason": "RAW_ROOT_PATH_INVALID_MISSING_LINK_OR_ESCAPING"}
    paths = sorted((path for path in root.iterdir() if path.is_file()), key=lambda path: path.name)
    rows = [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)} for path in paths]
    observed = {
        "json_count": sum(path.suffix.lower() == ".json" for path in paths), "npz_count": sum(path.suffix.lower() == ".npz" for path in paths),
        "file_count": len(paths), "canonical_sha256": canonical_hash(rows), "no_links": not any(_is_link_or_reparse(path) for path in paths),
    }
    expected = {"json_count": 144, "npz_count": 120, "file_count": 264, "canonical_sha256": RAW_INVENTORY_SHA256, "no_links": True}
    bound = {key: spec[key] for key in ("json_count", "npz_count", "file_count", "canonical_sha256")}
    bound["no_links"] = True
    return {"passed": observed == expected == bound, "observed": observed, "expected": expected}


def _parent_semantics_check(bindings: dict[str, Any]) -> dict[str, Any]:
    r2 = load(PROJECT_ROOT / _row_by_id(bindings, "r2_contract_gate")["path"])
    r1 = load(PROJECT_ROOT / _row_by_id(bindings, "b4g_r1_failure_closure_gate")["path"], allow_null=True)
    invalidation = load(PROJECT_ROOT / _row_by_id(bindings, "b4g_active_invalidation")["path"])
    b4g_terminal = load(PROJECT_ROOT / _row_by_id(bindings, "b4g_active_source_freeze_terminal")["path"])
    passed = bool(
        r2.get("status") == "PASS_PHASE_B4G_R2_NUMERICAL_PREFLIGHT_CONTRACT_ONLY"
        and r2.get("required_false", {}).get("r2_numerical_preflight_executed") is False
        and r2.get("required_false", {}).get("next_stage_authorized") is False
        and r1.get("status") == "PASS_PHASE_B4G_R1_REGISTERED_FAILURE_CLOSURE_CONTRACT_ONLY"
        and r1.get("original_b4g_final_credit") is False
        and r1.get("b4g_scientific_gate_pass") is False
        and r1.get("required_false", {}).get("current_system_bound") is False
        and invalidation.get("active") is True
        and invalidation.get("raw_case_and_diagnostic_evidence_preserved") is True
        and b4g_terminal.get("self_excluded") is True
        and b4g_terminal.get("acyclic") is True
        and b4g_terminal.get("source_count") == 52
    )
    return {
        "passed": passed,
        "r2_status": r2.get("status", "MISSING"),
        "r1_status": r1.get("status", "MISSING"),
        "invalidation_active": invalidation.get("active", False),
        "b4g_source_terminal_acyclic": b4g_terminal.get("acyclic", False),
    }


def _number_array(value: Any, length: int) -> bool:
    return isinstance(value, list) and len(value) == length and all(isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item)) for item in value)


def _hex64(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(character in HEX64 for character in value)


def _donor_check(bindings: dict[str, Any]) -> dict[str, Any]:
    row = _row_by_id(bindings, "common_prop_donor_raw_slot_052")
    path = PROJECT_ROOT / row["path"]
    outer = load(path, allow_null=True)
    provenance = outer["event_provenance"]
    payload = provenance["acquisition_certificate_payload"]
    acquisition = payload["acquisition"]
    event = payload["event"]
    reduced = acquisition["z_plus_reduced"]
    group = {
        "schema": "B4G_R2_COMMON_INITIAL_STATE_GROUP_V1",
        "donor_acquisition_certificate_sha256": provenance["acquisition_certificate_sha256"],
        "acquisition_time_s": acquisition["acquisition_time_s"],
        "service": {
            "base_position_inertial_m": event["service"]["base_position_inertial_m"],
            "base_quaternion_body_to_inertial_wxyz": event["service"]["base_quaternion_body_to_inertial_wxyz"],
            "joint_coordinates_mixed": event["service"]["joint_coordinates_mixed"],
            "post_acquisition_eta_mixed": reduced[:14],
        },
        "target": {
            "position_inertial_m": event["target"]["position_inertial_m"],
            "quaternion_body_to_inertial_wxyz": event["target"]["quaternion_body_to_inertial_wxyz"],
            "post_acquisition_twist_inertial_mixed": reduced[14:20],
        },
    }
    shapes = bool(
        _number_array(reduced, 20)
        and _number_array(group["service"]["base_position_inertial_m"], 3)
        and _number_array(group["service"]["base_quaternion_body_to_inertial_wxyz"], 4)
        and _number_array(group["service"]["joint_coordinates_mixed"], 8)
        and _number_array(group["service"]["post_acquisition_eta_mixed"], 14)
        and _number_array(group["target"]["position_inertial_m"], 3)
        and _number_array(group["target"]["quaternion_body_to_inertial_wxyz"], 4)
        and _number_array(group["target"]["post_acquisition_twist_inertial_mixed"], 6)
    )
    binding = bindings["common_donor_binding"]
    passed = bool(
        path.stat().st_size == DONOR_RAW_BYTES and sha(path) == DONOR_RAW_SHA256
        and provenance["acquisition_certificate_sha256"] == DONOR_PAYLOAD_SHA256
        and len(canonical_bytes(payload)) == DONOR_PAYLOAD_BYTES and canonical_hash(payload) == DONOR_PAYLOAD_SHA256
        and len(canonical_bytes(group)) == COMMON_GROUP_BYTES and canonical_hash(group) == COMMON_GROUP_SHA256
        and binding["payload_canonical_bytes"] == DONOR_PAYLOAD_BYTES and binding["payload_sha256"] == DONOR_PAYLOAD_SHA256
        and binding["group_canonical_bytes"] == COMMON_GROUP_BYTES and binding["group_sha256"] == COMMON_GROUP_SHA256
        and shapes
    )
    return {"passed": passed, "payload_sha256": canonical_hash(payload), "group_sha256": canonical_hash(group), "shape_contract_pass": shapes}


def _artifact_and_import_guard() -> dict[str, Any]:
    violations: list[str] = []
    forbidden_imports: list[dict[str, str]] = []
    for path in HERE.rglob("*"):
        relative = path.relative_to(HERE).as_posix()
        if _is_link_or_reparse(path):
            violations.append(f"LINK_OR_REPARSE:{relative}")
        if path.is_dir() and path.name.lower() in FORBIDDEN_DIRECTORIES:
            violations.append(f"FORBIDDEN_DIRECTORY:{relative}")
        if path.is_file() and (path.suffix.lower() in FORBIDDEN_SUFFIXES or any(token in path.name.lower() for token in FORBIDDEN_FILENAME_SUBSTRINGS)):
            violations.append(f"FORBIDDEN_FILE:{relative}")
    for path in _source_candidates(HERE):
        if path.suffix.lower() != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            for module in modules:
                if any(token in module for token in FORBIDDEN_IMPORT_TOKENS):
                    forbidden_imports.append({"path": path.relative_to(HERE).as_posix(), "module": module})
    validator_tree = ast.parse((HERE / "validate_phase_b4g_r2_execution_source_freeze.py").read_text(encoding="utf-8"))
    audit_tree = ast.parse((HERE / "independent_audit_phase_b4g_r2_execution_source_freeze.py").read_text(encoding="utf-8"))
    def imported_names(tree: ast.AST) -> list[str]:
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
        return names
    validator_imports = imported_names(validator_tree)
    audit_imports = imported_names(audit_tree)
    independent = bool(
        not any("independent_audit" in name or name.startswith("tests") for name in validator_imports)
        and not any("validate_phase" in name or name.startswith("tests") or name.startswith("r2_preflight") for name in audit_imports)
    )
    return {"passed": not violations and not forbidden_imports and independent, "violations": sorted(violations), "forbidden_imports": forbidden_imports, "validator_audit_independent": independent}


def _manifest_check() -> dict[str, Any]:
    manifest = load(MANIFEST)
    inventory = local_inventory(HERE)
    paths = [row["path"] for row in manifest.get("sources", [])]
    passed = bool(
        manifest.get("schema") == "SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1"
        and manifest.get("self_excluded") is True and manifest.get("acyclic") is True and manifest.get("terminal_excluded") is True
        and manifest.get("sources") == inventory and manifest.get("source_count") == len(inventory)
        and manifest.get("source_inventory_sha256") == canonical_hash(inventory)
        and all(not path.startswith("evidence/") and not path.startswith("results/") for path in paths)
    )
    return {"passed": passed, "source_count": len(inventory), "source_inventory_sha256": canonical_hash(inventory)}


def _nc_check() -> dict[str, Any]:
    if not NC_EVIDENCE.is_file() or _is_link_or_reparse(NC_EVIDENCE):
        return {"passed": False, "reason": "NC_EVIDENCE_MISSING_OR_LINK"}
    try:
        contract = load(NC_CONTRACT)
        evidence = load(NC_EVIDENCE)
    except Exception as exc:
        return {"passed": False, "reason": f"NC_EVIDENCE_STRICT_JSON_FAILURE:{type(exc).__name__}"}
    controls = evidence.get("controls", [])
    ids = [row.get("id") for row in controls if isinstance(row, dict)]
    registered = contract["registered_ids"]
    ids_are_strings = all(isinstance(identifier, str) for identifier in ids)
    unique_id_count = len(set(ids)) if ids_are_strings else -1
    allowed = set(contract["allowed_statuses"])
    structural = set(contract["structural_source_signature_only_ids"])
    exact_keys = set(contract["control_exact_keys"])
    rows_pass = bool(isinstance(controls, list) and len(controls) == 46 and ids_are_strings and ids == registered and unique_id_count == 46)
    if rows_pass:
        for row in controls:
            rows_pass = bool(
                rows_pass and set(row) == exact_keys and isinstance(row["status"], str) and row["status"] in allowed
                and (row["status"] == "STRUCTURAL_SOURCE_SIGNATURE_KILLED") == (row["id"] in structural)
                and row["implemented"] is True and row["source_only_executed"] is True and row["killed"] is True
                and row["r2_runtime_trajectory_evaluated"] is False
                and row["fixture_class"] == contract["per_control_fixture_class_exact"]
                and type(row["witness"]) is str and bool(row["witness"])
                and _hex64(row["implementation_sha256"])
            )
    required = contract["top_level_required"]
    manifest = load(MANIFEST)
    manifest_rows = {row["path"]: row for row in manifest["sources"]}
    implementation = evidence.get("implementation_files", [])
    binding = contract["implementation_binding"]
    implementation_paths = [row.get("path") for row in implementation if isinstance(row, dict)] if isinstance(implementation, list) else []
    implementation_pass = bool(
        isinstance(implementation, list)
        and len(implementation) == binding["file_count"]
        and all(type(path) is str for path in implementation_paths)
        and len(set(implementation_paths)) == binding["file_count"]
        and _hex64(evidence.get("implementation_sha256"))
    )
    if implementation_pass:
        for row in implementation:
            if not isinstance(row, dict) or set(row) != set(binding["record_exact_keys"]):
                implementation_pass = False
                break
            relative = Path(row["path"])
            path = (HERE / relative).resolve()
            try:
                path.relative_to(HERE.resolve())
                contained = not relative.is_absolute() and not any(part in {"", ".", ".."} for part in relative.parts)
            except ValueError:
                contained = False
            implementation_pass = bool(
                implementation_pass and contained and path.is_file() and not _is_link_or_reparse(path)
                and type(row["bytes"]) is int and path.stat().st_size == row["bytes"]
                and _hex64(row["sha256"]) and sha(path) == row["sha256"]
                and manifest_rows.get(row["path"]) == row
            )
        implementation_pass = bool(
            implementation_pass
            and canonical_hash(implementation) == evidence["implementation_sha256"]
            and all(isinstance(row, dict) and row.get("implementation_sha256") == evidence["implementation_sha256"] for row in controls)
        )
    top_pass = bool(
        set(evidence) == set(contract["evidence_exact_keys"])
        and evidence.get("schema") == contract["evidence_schema"]
        and evidence.get("scope") == contract["evidence_scope_exact"]
        and evidence.get("registered_count") == 46
        and all(evidence.get(key) == value and type(evidence.get(key)) is type(value) for key, value in required.items())
        and evidence.get("source_inventory_sha256") == manifest["source_inventory_sha256"]
    )
    return {
        "passed": rows_pass and top_pass and implementation_pass,
        "row_count": len(controls) if isinstance(controls, list) else -1,
        "unique_id_count": unique_id_count,
        "rows_pass": rows_pass,
        "top_level_pass": top_pass,
        "implementation_binding_pass": implementation_pass,
        "evidence_sha256": canonical_hash(evidence),
    }


def _matrix_schedule_check() -> dict[str, Any]:
    matrix = independent_matrix()
    schedule = independent_schedule()
    fresh = [row for row in matrix if row["execution_family"] == "FRESH"]
    common = [row for row in matrix if row["execution_family"] == "COMMON_PROP"]
    passed = bool(
        len(matrix) == len(schedule) == 78 and len(fresh) == 60 and len(common) == 18
        and canonical_hash(matrix) == MATRIX_SHA256 and canonical_hash(schedule) == SCHEDULE_SHA256
        and set(schedule) == {row["case_id"] for row in matrix}
        and all(row["g12_credit"] is False and row["selector_input"] is False for row in common)
    )
    return {"passed": passed, "matrix_sha256": canonical_hash(matrix), "schedule_sha256": canonical_hash(schedule), "case_count": len(matrix)}


def _governance_check() -> dict[str, Any]:
    governance = load(GOVERNANCE)
    freeze_contract = load(FREEZE_CONTRACT)
    false = governance["required_false"]
    zero = governance["required_zero"]
    statuses = freeze_contract["exact_statuses"]
    replay = freeze_contract["validator_and_audit_independence"]
    passed = bool(
        all(value is False for value in false.values())
        and all(type(value) is int and value == 0 for value in zero.values())
        and governance["gate_status_exact"] == statuses["pass"]
        and governance["partial_gate_status_exact"] == statuses["partial"]
        and governance["failure_gate_status_exact"] == statuses["failure"]
        and governance["execution_readiness_status_exact"] == statuses["execution_readiness"]
        and governance["authorized_execution_path_status_exact"] == statuses["authorized_execution_path_status"]
        and governance["authorization_boundary"]["bound_direct_owner_source_id"] == "NOT_AVAILABLE_NO_EXECUTION_AUTHORITY"
        and governance["authorization_boundary"]["successful_authorization_path_implemented_in_this_version"] is False
        and replay.get("standalone_default_mode") == "READ_ONLY_RECEIPT_VERIFY"
        and replay.get("receipt_write_requires_explicit_cli_flag") == "--write-receipt"
        and replay.get("receipt_write_flag_abbreviation_allowed") is False
        and replay.get("freeze_internal_receipt_generation_is_explicit") is True
        and replay.get("validator_audit_pytest_replay_must_preserve_all_package_bytes") is True
        and replay.get("read_only_replay_captures_after_delta_on_subcommand_failure") is True
        and replay.get("read_only_replay_revalidates_gate_and_terminal_hash_chain") is True
    )
    return {"passed": passed, "false_count": len(false), "zero_count": len(zero)}


def _execution_guard_hold_check() -> dict[str, Any]:
    governance = load(GOVERNANCE)
    boundary = governance["authorization_boundary"]
    expected_names = boundary["no_success_path_function_names"]
    expected_error = boundary["required_fail_closed_exception"]
    path = HERE / "r2_preflight/execution_guard.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    details: dict[str, bool] = {}
    for name in expected_names:
        node = functions.get(name)
        body = [] if node is None else list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        exact_raise = False
        if len(body) == 1 and isinstance(body[0], ast.Raise) and isinstance(body[0].exc, ast.Call):
            call = body[0].exc
            exact_raise = bool(
                isinstance(call.func, ast.Name) and call.func.id == "ExecutionAuthorizationError"
                and len(call.args) == 1 and isinstance(call.args[0], ast.Constant) and call.args[0].value == expected_error
            )
        details[name] = exact_raise
    return {"passed": len(details) == 3 and all(details.values()), "functions": details}


def _negative_control_registration_check(bindings: dict[str, Any]) -> dict[str, Any]:
    parent = load(PROJECT_ROOT / _row_by_id(bindings, "r2_governance_negative_controls")["path"])
    local = load(NC_CONTRACT)
    registered = local["registered_ids"]
    passed = bool(parent.get("negative_control_count") == 46 and parent.get("negative_controls") == registered and len(registered) == len(set(registered)) == 46)
    return {"passed": passed, "parent_count": parent.get("negative_control_count", -1), "local_count": len(registered)}


def _validator_receipt_check() -> dict[str, Any]:
    if not VALIDATION.is_file() or _is_link_or_reparse(VALIDATION):
        return {"passed": False, "reason": "VALIDATION_RECEIPT_MISSING_OR_LINK"}
    value = load(VALIDATION)
    replay_rows = [row for row in value.get("checks", []) if row.get("id") == "R2SV09_SOURCE_ONLY_NEGATIVE_CONTROLS_EXACT_46"]
    replay = replay_rows[0].get("detail", {}) if len(replay_rows) == 1 else {}
    evidence_sha256 = canonical_hash(load(NC_EVIDENCE)) if NC_EVIDENCE.is_file() else "MISSING"
    passed = bool(
        value.get("schema") == "SIM13_V4B4G_R2_EXECUTION_SOURCE_VALIDATION_V1"
        and value.get("status") == "PASS_R2_EXECUTION_SOURCE_VALIDATION"
        and value.get("score", {}).get("fail") == 0
        and value.get("source_freeze_pass_eligible") is True
        and value.get("r2_numerical_preflight_executed") is False
        and value.get("r2_execution_negative_controls_executed") is False
        and value.get("trajectory_count") == 0
        and replay.get("passed") is True
        and replay.get("replay_exact") is True
        and replay.get("actual_control_count") == 46
        and replay.get("actual_killed_count") == 46
        and replay.get("expected_evidence_sha256") == replay.get("observed_evidence_sha256") == evidence_sha256
    )
    return {"passed": passed, "status": value.get("status", "MISSING"), "validator_replay_exact": replay.get("replay_exact", False), "evidence_sha256": evidence_sha256}


def _all_local_json_no_null() -> dict[str, Any]:
    failures: list[str] = []
    checked = 0
    # Audit is generated before Gate/terminal. Exclude its own receipt and the
    # exact downstream pair so standalone verification observes the same set.
    excluded = {OUTPUT.resolve(), GATE_OUTPUT.resolve(), TERMINAL_OUTPUT.resolve()}
    for path in HERE.rglob("*.json"):
        if path.resolve() in excluded:
            continue
        try:
            load(path)
        except Exception:
            failures.append(path.relative_to(HERE).as_posix())
        checked += 1
    return {"passed": not failures, "checked": checked, "failures": sorted(failures)}


def audit(*, write_output: bool = False, output_path: Path = OUTPUT) -> dict[str, Any]:
    bindings = load(SOURCE_BINDINGS)
    checks: list[dict[str, Any]] = []
    def add(check_id: str, detail: dict[str, Any]) -> None:
        checks.append({"id": check_id, "pass": detail.get("passed") is True, "detail": detail})

    add("R2SA01_LOCAL_MANIFEST_INDEPENDENTLY_REHASHED", _manifest_check())
    add("R2SA02_RECURSIVE_ARTIFACT_IMPORT_AND_INDEPENDENCE_GUARD", _artifact_and_import_guard())
    add("R2SA03_EXTERNAL_SOURCE_BINDINGS_INDEPENDENTLY_REHASHED", _source_bindings_check(bindings))
    add("R2SA04_RAW_INVENTORY_INDEPENDENTLY_REHASHED", _raw_inventory_check(bindings))
    add("R2SA05_PARENT_CONTRACT_ONLY_AND_INVALIDATION_ACTIVE", _parent_semantics_check(bindings))
    add("R2SA06_DONOR_PAYLOAD_AND_GROUP_INDEPENDENTLY_DERIVED", _donor_check(bindings))
    add("R2SA07_MATRIX_AND_SCHEDULE_INDEPENDENTLY_DERIVED", _matrix_schedule_check())
    add("R2SA08_GOVERNANCE_FALSE_AND_ZERO_FLAGS_EXACT", _governance_check())
    add("R2SA09_SOURCE_ONLY_NEGATIVE_CONTROLS_EXACT_46", _nc_check())
    add("R2SA10_VALIDATOR_RECEIPT_CONSISTENT_WITH_INDEPENDENT_RESULT", _validator_receipt_check())
    add("R2SA11_LOCAL_JSON_STRICT_NO_NULL", _all_local_json_no_null())
    add("R2SA12_EXECUTION_GUARD_HAS_NO_SUCCESS_PATH", _execution_guard_hold_check())
    add("R2SA13_NEGATIVE_CONTROL_REGISTRATION_MATCHES_PARENT", _negative_control_registration_check(bindings))
    add("R2SA14_CRITICAL_PARENT_ROOT_HASHES_LITERAL_MATCH", _critical_binding_roots_check(bindings))
    failed = [row["id"] for row in checks if row["pass"] is not True]
    result = {
        "schema": "SIM13_V4B4G_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT_V1",
        "status": "PASS_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT" if not failed else "FAIL_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT",
        "scope": "STDLIB_ONLY_INDEPENDENT_SOURCE_AUDIT_NO_VALIDATOR_IMPORT_NO_TEST_IMPORT_NO_PHYSICS_NO_TRAJECTORY",
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "independent_source_freeze_pass_eligible": not failed,
        "r2_numerical_preflight_executed": False,
        "r2_execution_negative_controls_executed": False,
        "trajectory_count": 0,
        "authorized_execution_path_status": "NOT_VALIDATED_NO_DIRECT_OWNER_SOURCE",
    }
    if write_output:
        write_json(output_path, result)
    return result


def _existing_receipt_matches(result: dict[str, Any], output_path: Path = OUTPUT) -> bool:
    try:
        return bool(
            output_path.is_file()
            and not _is_link_or_reparse(output_path)
            and load(output_path) == result
        )
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only independent R2 source-freeze audit",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--write-receipt",
        action="store_true",
        help="explicitly generate the audit receipt; default only verifies the frozen receipt",
    )
    args = parser.parse_args(argv)
    try:
        result = audit(write_output=args.write_receipt)
    except Exception as exc:
        print({"status": "FAIL_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT_EXCEPTION", "error": str(exc)})
        return 1
    receipt_match = args.write_receipt or _existing_receipt_matches(result)
    status = result["status"] if receipt_match else "FAIL_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT_RECEIPT_DRIFT"
    print({"status": status, "score": result["score"], "mode": "WRITE_RECEIPT" if args.write_receipt else "READ_ONLY_RECEIPT_VERIFY", "receipt_match": receipt_match})
    return 0 if result["independent_source_freeze_pass_eligible"] is True and receipt_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
