"""Repository path bootstrap and frozen read-only imports for CTRL-01."""
from __future__ import annotations

from pathlib import Path
import sys


MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parents[1]
CONFIG_PATH = REPO_ROOT / "20_engineering" / "config" / "control_scene" / "control_01_v0.yaml"
MATRIX_PATH = REPO_ROOT / "20_engineering" / "config" / "control_scene" / "experiment_matrix_v0.yaml"
RESULTS_DIR = MODULE_ROOT / "results"
DOCS_DIR = MODULE_ROOT / "docs"

_IMPORT_DIRS = (
    REPO_ROOT / "30_simulation" / "sim_11_coupled_dynamics" / "src",
    REPO_ROOT / "30_simulation" / "sim_05_free_floating_arm",
    REPO_ROOT / "30_simulation" / "common",
    REPO_ROOT / "30_simulation" / "sim_09_grasp_evaluator" / "src",
)
for _path in reversed(_IMPORT_DIRS):
    _value = str(_path)
    if _value not in sys.path:
        sys.path.insert(0, _value)

from b601_model import B601Arm, skew  # noqa: E402,F401
from coupled_dynamics import CoupledModel, quintic  # noqa: E402,F401
from rigid_body import load_object, qmult, q_to_R  # noqa: E402,F401
