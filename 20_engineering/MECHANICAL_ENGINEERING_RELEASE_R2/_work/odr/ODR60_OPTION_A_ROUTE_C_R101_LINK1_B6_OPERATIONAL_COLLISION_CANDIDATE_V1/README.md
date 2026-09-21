# Route-C R101 link1 B6 operational-collision candidate

This bounded package emits the six exact V9F physical Route-C objects currently mapped to `link1` as STEP-first, link1-local/q0 geometry plus runtime mesh sidecars and a side-effect-free joint1 pose adapter.

It does not modify the current M01 registry, run a pair query, create a SAFE edge, authorize a stage/path, close TMG-4 or G12, or earn release credit.

Build and deterministic replay:

```powershell
python 02_builder/build_link1_b6.py --write
python 02_builder/build_link1_b6.py --check
```

Independent validation and tests:

```powershell
python 04_validation/validate_link1_b6_independent.py --write
python 04_validation/run_negative_controls.py --write
python 04_validation/verify_fresh_process_determinism.py --write
python -m pytest -q 06_tests
```
