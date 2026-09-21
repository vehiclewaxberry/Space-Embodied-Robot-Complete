"""t7 -- determinism and hash sensitivity:

  D1 evaluate(candidate) called twice -> scenario_hash identical AND the full
     result structure identical bit for bit (provenance wall_time_ms is the
     only excluded field, see GraspEvaluationResult.canonical()).
  D2 perturbing ANY input by 1e-6 changes the scenario_hash
     (checked on v_app, q0[0], capture_time and tumble omega).

The flexible window is shortened (t_end 3 s) to keep the double evaluation
fast; determinism is integrator-independent of the window length.
"""
import _helpers
import numpy as np

from evaluator import evaluate, make_config

CFG_OVERRIDE = {"flexible": {"t_end_s": 3.0, "n_eval": 300}}


def _deep_compare(a, b, path="result"):
    """Max discrepancy between two canonical dicts; requires identical structure."""
    if isinstance(a, dict):
        assert isinstance(b, dict) and set(a) == set(b), f"{path}: key mismatch"
        return max((_deep_compare(a[k], b[k], f"{path}.{k}") for k in a), default=0.0)
    if isinstance(a, (list, tuple)):
        assert len(a) == len(b), f"{path}: length mismatch"
        return max((_deep_compare(x, y, f"{path}[{i}]")
                    for i, (x, y) in enumerate(zip(a, b))), default=0.0)
    if isinstance(a, float) and isinstance(b, float):
        if np.isnan(a) and np.isnan(b):
            return 0.0
        return abs(a - b)
    assert a == b, f"{path}: {a!r} != {b!r}"
    return 0.0


def run():
    cfg = make_config(CFG_OVERRIDE)
    cand1 = _helpers.nominal_candidate()
    cand2 = _helpers.nominal_candidate()
    assert cand1.scenario_hash == cand2.scenario_hash, "hash not reproducible"

    r1 = evaluate(cand1, cfg)
    r2 = evaluate(cand2, cfg)
    assert r1.scenario_hash == r2.scenario_hash
    worst = _deep_compare(r1.canonical(), r2.canonical())
    assert worst == 0.0, f"repeat evaluation differs bitwise: {worst:.3e}"

    # D2: 1e-6 input perturbations must all change the hash
    perturbed = [
        _helpers.nominal_candidate(v_app=0.01 + 1e-6),
        _helpers.nominal_candidate(t_c=1e-6),
        _helpers.nominal_candidate(omega_dps=3.0 + 1e-6),
        _helpers.nominal_candidate(q0=np.array([1e-6, -0.9, -1.2, -0.8, 0.2, 0.0])),
    ]
    changed = [p.scenario_hash != cand1.scenario_hash for p in perturbed]
    assert all(changed), f"hash blind to a 1e-6 perturbation: {changed}"

    return {"name": "t7_determinism", "passed": True, "worst_residual": worst,
            "hash": r1.scenario_hash,
            "n_perturbations_changing_hash": f"{sum(changed)}/{len(changed)}",
            "failure_codes_nominal": r1.failure_reason_codes,
            "admissibility_nominal": r1.admissibility_flags,
            "note": "double evaluation bitwise identical (wall_time_ms excluded); "
                    "hash sensitive to 1e-6 on v_app/t_c/omega/q0"}


if __name__ == "__main__":
    out = run()
    print("scenario_hash:", out["hash"])
    print("bitwise repeat diff:", out["worst_residual"])
    print("perturbations changing hash:", out["n_perturbations_changing_hash"])
    print("nominal failure codes:", out["failure_codes_nominal"])
    print("PASS | worst", f"{out['worst_residual']:.3e}")
