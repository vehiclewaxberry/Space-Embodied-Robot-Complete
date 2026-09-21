"""VIZ-Gate 0 acceptance test 2 -- scene transform validity + T_SM SSOT match.

Checks (read-only):
  A. EVERY rotation matrix used by the unified scene (frozen T_SM, all B601
     link poses at the E1.5 display configuration, the E convention frame,
     and the satellite/debris target placements from the read-only E0/E1.5
     placement chain) is orthonormal (max|R^T R - I| < 1e-12) and
     right-handed (det(R) = +1 within 1e-12).
  B. The frozen T_SM used by the renderer numerically matches the SSOT
     document section 3.1 (20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/coordinate_frame_definition_v0.md):
     translation [185.25, 0, 0] mm and quaternion [w,x,y,z] =
     [0.70710678, 0, 0.70710678, 0] are extracted from the document TEXT by
     regex (never hardcoded here) and compared against b601_renderer.load_T_SM.
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "70_tools", "project_visualization", "src"))
import _viz_bootstrap as vb  # noqa: E402  (pins OMP/MKL=1 BEFORE numpy)

import numpy as np           # noqa: E402

ORTHO_TOL = 1e-12
DET_TOL = 1e-12
T_SM_TOL = 1e-6   # SSOT quaternion is printed to 8 decimals -> ~1e-8 in R


def _check_R(name, R, log):
    R = np.asarray(R, float)
    ortho = float(np.max(np.abs(R.T @ R - np.eye(3))))
    det = float(np.linalg.det(R))
    assert ortho < ORTHO_TOL, f"{name}: |R^T R - I| = {ortho:.2e} >= {ORTHO_TOL}"
    assert abs(det - 1.0) < DET_TOL, f"{name}: det(R) = {det:.15f} != +1"
    log.append((name, ortho, det))


def _quat_to_R(w, x, y, z):
    n = np.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def main(verbose=True):
    import scene_assembly as sa
    from b601_renderer import load_T_SM

    details = []
    log = []

    # ---- A. all scene rotations orthonormal + right-handed ---------------
    T_SM = load_T_SM()
    _check_R("T_SM", T_SM[:3, :3], log)

    sel = sa.e15_selected_case()
    frames = sa.arm_frames(sel["q"])
    for ln, T in frames["links"].items():
        _check_R(f"arm:{ln}", T[:3, :3], log)
    _check_R("arm:T_E", frames["T_E"][:3, :3], log)

    sat = sa.satellite_scene()
    _check_R("satellite:T_S_T", sat["T_S_T"][:3, :3], log)
    _check_R("satellite:R_TS", sat["placement"]["R_TS"], log)

    deb = sa.debris_scene()
    _check_R("debris:T_S_D", deb["T_S_T"][:3, :3], log)
    _check_R("debris:R_TS", deb["placement"]["R_TS"], log)

    worst_o = max(o for _, o, _ in log)
    worst_d = max(abs(d - 1.0) for _, _, d in log)
    details.append(f"{len(log)} rotation matrices checked: "
                   f"max|R^T R - I| = {worst_o:.2e} (< 1e-12), "
                   f"max|det-1| = {worst_d:.2e} (right-handed)")

    # ---- B. T_SM vs SSOT section 3.1 (regex-extracted from the doc) ------
    with open(vb.COORD_SSOT_MD, encoding="utf-8") as f:
        doc = f.read()
    m_t = re.search(r"t_SM\s*=\s*\[([^\]]+)\]\s*mm", doc)
    assert m_t, "SSOT: t_SM = [...] mm pattern not found in section 3.1"
    t_doc_mm = np.array([float(v) for v in m_t.group(1).split(",")])
    m_q = re.search(r"\[w,x,y,z\]\s*=\s*\[([^\]]+)\]", doc)
    assert m_q, "SSOT: quaternion [w,x,y,z] = [...] pattern not found"
    qw, qx, qy, qz = [float(v) for v in m_q.group(1).split(",")]
    R_doc = _quat_to_R(qw, qx, qy, qz)

    dt = float(np.max(np.abs(T_SM[:3, 3] - t_doc_mm / 1000.0)))
    dR = float(np.max(np.abs(T_SM[:3, :3] - R_doc)))
    assert dt < 1e-12, f"T_SM translation vs SSOT: max diff {dt:.2e} m"
    assert dR < T_SM_TOL, f"T_SM rotation vs SSOT quat: max diff {dR:.2e}"
    details.append(f"T_SM vs SSOT sec 3.1: t_doc={t_doc_mm.tolist()} mm "
                   f"(diff {dt:.1e} m), quat=[{qw},{qx},{qy},{qz}] "
                   f"(R diff {dR:.1e})")

    if verbose:
        for d in details:
            print("  " + d)
    return {"name": "test_scene_transforms", "pass": True, "details": details}


if __name__ == "__main__":
    print("test_scene_transforms:")
    main()
    print("PASS")
