"""Hash-locked import of the prior frozen evaluator/work-energy implementation."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types
from typing import Any

from .strict_json import file_sha256


FROZEN_RELATIVE_ROOT = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic/"
    "phase_b4g_r2_post_freeze_numerical_preflight_execution/r2_preflight"
)
FROZEN_SOURCE_SHA256 = {
    "strict_json.py": "E62BD2557B69F7573911B95EA70689CA86FDD9BBE3F40FA531B6B8432E8EF50F",
    "metrics.py": "2435948352B09594F49124ED0F8F21428A41C8EDB71DD576D324111A3568BC2D",
    "rehydrator.py": "27DABAD5B7A509E540AEBA4E35EEC03D4E464A36159EE06814EEA9F4160F70C1",
    "schedule.py": "3AF70B9E7560A97D46450CE5DC144A11570BA8BD9A59A63C4E290713C989A338",
    "work_energy.py": "F0F7B9090CA2C640A7C1DDD880A32F0CD6108B9D648573335A944FC514665C35",
    "evaluator.py": "D88B3830732931F0116B64ED8754CB5178E87A87291A0AA469374B00154F6C11",
}
NAMESPACE = "_sim13_b4g_r2_frozen_production"


class ProductionAPIError(RuntimeError):
    pass


def project_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if candidate.is_dir() and (candidate / "PROJECT_MAP.md").is_file() and (candidate / "30_simulation").is_dir():
            return candidate
    raise ProductionAPIError("PROJECT_ROOT_NOT_FOUND")


def verify_frozen_sources() -> dict[str, str]:
    root = project_root() / FROZEN_RELATIVE_ROOT
    observed: dict[str, str] = {}
    for name, expected in FROZEN_SOURCE_SHA256.items():
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ProductionAPIError(f"FROZEN_PRODUCTION_SOURCE_MISSING:{name}")
        digest = file_sha256(path)
        if digest != expected:
            raise ProductionAPIError(f"FROZEN_PRODUCTION_SOURCE_DRIFT:{name}")
        observed[name] = digest
    return observed


def load_production_modules() -> dict[str, Any]:
    verify_frozen_sources()
    root = project_root() / FROZEN_RELATIVE_ROOT
    if NAMESPACE not in sys.modules:
        namespace = types.ModuleType(NAMESPACE)
        namespace.__path__ = [str(root)]
        namespace.__package__ = NAMESPACE
        sys.modules[NAMESPACE] = namespace
    modules = {}
    for name in ("strict_json", "metrics", "rehydrator", "schedule", "work_energy", "evaluator"):
        modules[name] = importlib.import_module(f"{NAMESPACE}.{name}")
    forbidden = sorted(name for name in sys.modules if "b4g_solver" in name or "b4_solver" in name)
    if forbidden:
        raise ProductionAPIError(f"FORBIDDEN_SOLVER_IMPORT_OBSERVED:{forbidden}")
    return modules


__all__ = ["FROZEN_RELATIVE_ROOT", "FROZEN_SOURCE_SHA256", "ProductionAPIError", "load_production_modules", "verify_frozen_sources"]
