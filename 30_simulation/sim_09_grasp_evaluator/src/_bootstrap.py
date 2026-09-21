"""sim_09 path/environment bootstrap.

MUST be imported BEFORE numpy in every sim_09 module / test / script:
  1. pins BLAS threading env vars (OMP/MKL/OPENBLAS = 1) -- MKL spin-wait lesson,
     see sim_07a header comment;
  2. puts the validated solver directories on sys.path so the adapter layer can
     IMPORT (never copy) the physics cores:
        30_simulation/common                     rigid_body, capture_impulse
        30_simulation/sim_05_free_floating_arm   b601_model, dynamics
        30_simulation/sim_07_ancf_flexible       ancf_beam, sim_07a_task_response
     plus this package directory itself (repo uses flat-module imports, no package
     installs).

Read-only contract: nothing outside this capsule, and nothing under
20_engineering/config/geometry/ or 01_project/, is modified.
"""
import os
import sys

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))

_SOLVER_DIRS = [
    HERE,
    os.path.join(REPO_ROOT, "30_simulation", "common"),
    os.path.join(REPO_ROOT, "30_simulation", "sim_05_free_floating_arm"),
    os.path.join(REPO_ROOT, "30_simulation", "sim_07_ancf_flexible"),
]
for _p in _SOLVER_DIRS:
    if _p not in sys.path:
        sys.path.insert(0, _p)

CONFIG_DIR = os.path.join(REPO_ROOT, "20_engineering", "config", "grasp_evaluator")
RESULTS_DIR = os.path.join(REPO_ROOT, "30_simulation", "sim_09_grasp_evaluator", "results")
