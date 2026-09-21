"""VIZ-Gate 0 path/environment bootstrap.

MUST be imported BEFORE numpy in every project-visualization source module:
  1. pins BLAS threading env vars (OMP/MKL/OPENBLAS = 1) -- same MKL spin-wait
     lesson as sim_07a / sim_09 _bootstrap;
  2. puts the read-only truth sources on sys.path so this package can IMPORT
     (never copy) them:
        30_simulation/sim_09_grasp_evaluator/src
                                     adapters (scene placement), contract,
                                     target_propagation, evaluator defaults
        30_simulation/common                   rigid_body (mass/inertia budget loader)
        30_simulation/sim_05_free_floating_arm b601_model (FK numerical truth)

Read-only contract (VIZ-Gate 0 iron rule 1): nothing under 20_engineering/cad/,
30_simulation/, 01_project/, or 20_engineering/config/ outside the visualization
subtree is modified. E1.5 data is read ONLY from
40_evidence/artifacts/visualization/e15_gate_evidence_snapshot_20260714/.
"""
import os
import sys

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))

_TRUTH_DIRS = [
    HERE,
    os.path.join(REPO_ROOT, "30_simulation", "sim_09_grasp_evaluator", "src"),
    os.path.join(REPO_ROOT, "30_simulation", "common"),
    os.path.join(REPO_ROOT, "30_simulation", "sim_05_free_floating_arm"),
]
for _p in _TRUTH_DIRS:
    if _p not in sys.path:
        sys.path.insert(0, _p)

CAD_DIR = os.path.join(REPO_ROOT, "20_engineering", "cad", "spacecraft_layout")
ARM_DIR = os.path.join(CAD_DIR, "arm_b601_v1")
URDF_PATH = os.path.join(ARM_DIR, "arm_b601_v1.urdf")
MESH_DIR = os.path.join(ARM_DIR, "meshes_b601_gripper")
SNAPSHOT_DIR = os.path.join(REPO_ROOT, "40_evidence", "artifacts", "visualization",
                            "e15_gate_evidence_snapshot_20260714")
FRAME_TREE_YAML = os.path.join(REPO_ROOT, "20_engineering", "config", "geometry", "frame_tree_v1.yaml")
COORD_SSOT_MD = os.path.join(REPO_ROOT, "20_engineering", "stage1_spacecraft_layout",
                             "04_mass_inertia_budget",
                             "coordinate_frame_definition_v0.md")
MASS_BUDGET_CSV = os.path.join(REPO_ROOT, "20_engineering", "stage1_spacecraft_layout",
                               "04_mass_inertia_budget", "mass_inertia_budget_v1.csv")

VIZ_CONFIG_DIR = os.path.join(REPO_ROOT, "20_engineering", "config", "visualization")
VIZ_TABLES_DIR = os.path.join(REPO_ROOT, "40_evidence", "artifacts", "visualization", "tables")
VIZ_FIGURES_DIR = os.path.join(REPO_ROOT, "40_evidence", "artifacts", "visualization", "figures")
for _d in (VIZ_CONFIG_DIR, VIZ_TABLES_DIR, VIZ_FIGURES_DIR):
    os.makedirs(_d, exist_ok=True)


def repo_commit_short():
    """Runtime git commit (provenance stamp on every figure)."""
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=REPO_ROOT, capture_output=True, text=True,
                             timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"
