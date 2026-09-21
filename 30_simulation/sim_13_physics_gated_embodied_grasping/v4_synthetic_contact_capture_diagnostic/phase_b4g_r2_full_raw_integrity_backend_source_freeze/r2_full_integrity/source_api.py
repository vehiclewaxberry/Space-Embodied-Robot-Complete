"""Hash-locked access to the frozen raw adapter and geometry-only replay.

No B3/B4/B4G solver module is imported.  The two reused packages are loaded
under private namespaces only after path, byte-count and SHA-256 checks.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sys
import types
from typing import Any


RAW_ADAPTER_RELATIVE_ROOT = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic/"
    "phase_b4g_r2_raw_evidence_adapter_source_freeze/r2_raw_adapter"
)
RAW_ADAPTER_SOURCE_BINDINGS = {
    "__init__.py": (928, "06ACB0329E3843994B314A8934BFDAE51077B2785D720E2A578E20D785F28349"),
    "adapter.py": (67513, "A971004A7F8DE355F07363A27D553D89E92662033948E1A7A1CC7542EC7F56F5"),
    "array_contract.py": (10063, "1BC6B1BB907904E86F0D90F300C3DD53B7137EA3DE67ECC9667E7E90DDB02013"),
    "fixture_factory.py": (12416, "818882C740810D88659FE35D798EC73D4831649448C6428062A2A90D94D0CBC0"),
    "path_binding.py": (4428, "41935DF81E0F6E22550B6858C6E043B58F8559F4AE807B002FC83A59DC5D54B5"),
    "production_api.py": (2852, "4A30466D94E4E3333825ABB8E69EB15B271390E81EDF2FE4BF054DC384A0E946"),
    "schedule_binding.py": (2090, "A87EC2F47C784A6437143FBED950E9224269C3FC64DB99041C759F09E8CFA6F3"),
    "strict_json.py": (3114, "1D76BD04C3B506DEFB9130D18D82CD66A96BB8A9E889E6E0AB8FA352EA8E2675"),
}
GEOMETRY_REPLAY_RELATIVE_PATH = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic/"
    "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/"
    "b4g_validation/geometry_replay.py"
)
GEOMETRY_REPLAY_BINDING = (
    31625,
    "3FE4B159F6A5885BBBFB783169A50E11FC948AEF7A507B0A0D3A89DB86DF0C65",
)
REFERENCE_FORCE_RELATIVE_PATH = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic/"
    "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/"
    "contracts/PHASE_B4G_REFERENCE_FORCE_V1.json"
)
REFERENCE_FORCE_BINDING = (
    1474,
    "E31ABDAEBC03FC71C40EB6274304395850A8B2E8DCB293569DDF1A5850C45AD7",
)
NUMERICAL_ACCEPTANCE_RELATIVE_PATH = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic/"
    "phase_b4g_r2_numerical_preflight_contract/contracts/"
    "PHASE_B4G_R2_NUMERICAL_ACCEPTANCE_V1.json"
)
NUMERICAL_ACCEPTANCE_BINDING = (
    16024,
    "4A81B9998638E23B024C0EFFF239F519FB9A872B87FF207A0148929ED9AC32B1",
)
B4F_MODEL_RELATIVE_PATH = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic/"
    "phase_b4f_synthetic_jaw_retraction_reachability_contract/contracts/"
    "PHASE_B4F_MODEL_AND_ENERGY_CONTRACT_V1.json"
)
B4F_MODEL_BINDING = (
    4501,
    "37DF6373B69EFCB3F434789C909347CEE209412A1D20D4392BAD649C705354CD",
)
B4F_NUMERICAL_RELATIVE_PATH = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic/"
    "phase_b4f_synthetic_jaw_retraction_reachability_contract/contracts/"
    "PHASE_B4F_NUMERICAL_ACCEPTANCE_V1.json"
)
B4F_NUMERICAL_BINDING = (
    3663,
    "1240AA92BE0AB110DC1C88D791F369FB5F8668535B5563797DB8AE1AD8517D73",
)
RAW_ARRAY_CONTRACT_RELATIVE_PATH = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic/"
    "phase_b4g_r2_raw_evidence_adapter_source_freeze/contracts/"
    "PHASE_B4G_R2_RAW_ARRAY_CONTRACT_V1.json"
)
RAW_ARRAY_CONTRACT_BINDING = (
    13426,
    "0DAD5B322A209C57230C8C9722F65329E5B457D6965CD7D33DB9167A686B9EF4",
)

RAW_NAMESPACE = "_sim13_b4g_r2_frozen_raw_adapter"
GEOMETRY_NAMESPACE = "_sim13_b4g_frozen_geometry_replay"
REFERENCE_Q_PER_FINGER_N = 0.024542335689275555


class SourceAPIError(RuntimeError):
    """A frozen source is missing, altered, or imports a forbidden solver."""


def project_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if candidate.is_dir() and (candidate / "PROJECT_MAP.md").is_file() and (candidate / "30_simulation").is_dir():
            return candidate
    raise SourceAPIError("PROJECT_ROOT_NOT_FOUND")


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _verify_file(relative_path: str, binding: tuple[int, str]) -> dict[str, Any]:
    root = project_root().resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SourceAPIError(f"SOURCE_PATH_ESCAPE:{relative_path}") from exc
    if path.is_symlink() or not path.is_file():
        raise SourceAPIError(f"SOURCE_MISSING_OR_SYMLINK:{relative_path}")
    actual = (path.stat().st_size, _digest(path))
    if actual != binding:
        raise SourceAPIError(f"SOURCE_BINDING_DRIFT:{relative_path}:{actual}")
    return {
        "path": relative_path,
        "bytes": actual[0],
        "sha256": actual[1],
    }


def verify_source_bindings() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for name, binding in sorted(RAW_ADAPTER_SOURCE_BINDINGS.items()):
        records.append(_verify_file(f"{RAW_ADAPTER_RELATIVE_ROOT}/{name}", binding))
    records.append(_verify_file(GEOMETRY_REPLAY_RELATIVE_PATH, GEOMETRY_REPLAY_BINDING))
    records.append(_verify_file(REFERENCE_FORCE_RELATIVE_PATH, REFERENCE_FORCE_BINDING))
    records.append(_verify_file(NUMERICAL_ACCEPTANCE_RELATIVE_PATH, NUMERICAL_ACCEPTANCE_BINDING))
    records.append(_verify_file(B4F_MODEL_RELATIVE_PATH, B4F_MODEL_BINDING))
    records.append(_verify_file(B4F_NUMERICAL_RELATIVE_PATH, B4F_NUMERICAL_BINDING))
    records.append(_verify_file(RAW_ARRAY_CONTRACT_RELATIVE_PATH, RAW_ARRAY_CONTRACT_BINDING))
    return {
        "passed": True,
        "source_count": len(records),
        "records": records,
        "solver_imported": False,
    }


def _private_package(namespace: str, root: Path) -> None:
    if namespace not in sys.modules:
        module = types.ModuleType(namespace)
        module.__path__ = [str(root)]
        module.__package__ = namespace
        sys.modules[namespace] = module


def _reject_solver_imports() -> None:
    forbidden = sorted(
        name for name in sys.modules
        if name.endswith("b4g_solver") or ".b4g_solver." in name
        or name.endswith("b4_solver") or ".b4_solver." in name
        or name.endswith("b3_contact") or ".b3_contact." in name
    )
    if forbidden:
        raise SourceAPIError(f"FORBIDDEN_SOLVER_IMPORT_OBSERVED:{forbidden}")


def load_raw_modules() -> dict[str, Any]:
    verify_source_bindings()
    root = project_root() / RAW_ADAPTER_RELATIVE_ROOT
    _private_package(RAW_NAMESPACE, root)
    modules = {
        name: importlib.import_module(f"{RAW_NAMESPACE}.{name}")
        for name in (
            "strict_json", "path_binding", "array_contract",
            "production_api", "schedule_binding", "adapter", "fixture_factory",
        )
    }
    _reject_solver_imports()
    return modules


def load_geometry_module() -> Any:
    verify_source_bindings()
    root = project_root() / Path(GEOMETRY_REPLAY_RELATIVE_PATH).parent
    _private_package(GEOMETRY_NAMESPACE, root)
    module = importlib.import_module(f"{GEOMETRY_NAMESPACE}.geometry_replay")
    module.validate_frozen_source_bindings(project_root())
    _reject_solver_imports()
    return module


def load_reference_force() -> dict[str, Any]:
    record = _verify_file(REFERENCE_FORCE_RELATIVE_PATH, REFERENCE_FORCE_BINDING)
    path = project_root() / REFERENCE_FORCE_RELATIVE_PATH
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SourceAPIError("REFERENCE_FORCE_PARSE_FAILED") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema") != "SIM13_V4B4G_REFERENCE_FORCE_V1"
        or value.get("individual_finger_reference_force_N") != REFERENCE_Q_PER_FINGER_N
        or value.get("registered_and_recomputed_opening_sign_left_right") != [1, 1]
        or value.get("physical_force_capacity_inferred") is not False
    ):
        raise SourceAPIError("REFERENCE_FORCE_SEMANTICS_DRIFT")
    return {"binding": record, "payload": value}


__all__ = [
    "REFERENCE_Q_PER_FINGER_N",
    "SourceAPIError",
    "load_geometry_module",
    "load_raw_modules",
    "load_reference_force",
    "project_root",
    "verify_source_bindings",
]
