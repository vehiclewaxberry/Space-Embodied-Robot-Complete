"""VIZ-Gate 0 acceptance test 3 -- render chain vs numerical-truth FK.

Reuses b601_renderer.fk_alignment_selftest: the INDEPENDENT visual transform
chain (own URDF parse / own rpy->R / own Rodrigues) is cross-checked against
30_simulation/sim_05_free_floating_arm/b601_model.B601Arm.fk (the numerical truth) at
q = 0, the E1.5 selected configuration, and 20 random in-limit configurations
(fixed seed 20260714 -> deterministic).

Criterion (VIZ-Gate 0): position error < 1 mm AND orientation error < 0.1 deg
over link1..link6 and the E convention frame, plus the YAML-vs-code T_SM
agreement embedded in the selftest.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "70_tools", "project_visualization", "src"))
import _viz_bootstrap  # noqa: E402, F401  (pins OMP/MKL=1 BEFORE numpy)


def main(verbose=True):
    from b601_renderer import fk_alignment_selftest

    rep = fk_alignment_selftest(n_random=20, seed=20260714, verbose=False)
    details = [
        f"configs checked: {rep['n_configs']} "
        "(q=0 + E1.5 selected q + 20 random in-limit, seed 20260714)",
        f"max position error: {rep['max_pos_err_mm']:.6f} mm (< 1 mm)",
        f"max orientation error: {rep['max_ori_err_deg']:.6f} deg (< 0.1 deg)",
        f"T_SM yaml-vs-b601_model max abs diff: "
        f"{rep['T_SM_yaml_vs_b601model_maxabs']:.2e}",
    ]
    assert rep["max_pos_err_mm"] < 1.0, details[1]
    assert rep["max_ori_err_deg"] < 0.1, details[2]
    assert rep["pass"], f"selftest reported fail: {rep}"

    if verbose:
        for d in details:
            print("  " + d)
    return {"name": "test_fk_render_alignment", "pass": True,
            "details": details, "report": rep}


if __name__ == "__main__":
    print("test_fk_render_alignment:")
    main()
    print("PASS")
