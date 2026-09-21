# ODR-60 Option A — M01 scene and collision prebind V1

This append-only package converts the latest accepted Option-A selection, the exact
12-decimal execution mount, the 10/10 B601 collision-frame ledger, and the current
150-object collision registry into two bounded intake artifacts.  It does **not**
modify or reissue any parent Gate.

## Outputs

- `M01_SCENE_DECISION_INTAKE_V1.yaml` explicitly carries every V2 PRE/EVENT/POST
  field.  All authoritative values remain `null`, so the accounting stays 0/3 stage
  instances and 0/9 legacy required values.  A separate
  `candidate_suggestions_not_authority` block is only an engineering hypothesis and
  is forbidden from filling an instance without Owner-ratified values and reissued
  per-stage object/pair-universe hashes.
- `M01_OPERATIONAL_ASSET_READINESS_V1.csv` contains 167 unique rows: 150 objects in
  the current pair universe, 10 non-active K-class virtual keepout candidates, and
  all 7 known missing object/authority categories.  Literal `null` cells are
  intentional unknowns, not zeroes or empty authorization.
- `M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json` is the structural package Gate.
- `M01_SCENE_AND_COLLISION_PREBIND_SHA256_V1.csv` binds every package file except
  itself, avoiding a circular digest.

`closed=true` and `operational_authority=true` are asset-level statements only.  At
the frozen inputs, exactly 1/150 active rows (`A::base_link`) has that status.  It
does not imply a runtime pose, a safe pair, a certified edge, or M01 readiness.

## Fail-closed boundary

The package performs only metadata parsing and byte/hash verification.  It does not
load FCStd/STEP/STL/PLY/NPY/NPZ geometry, call a CAD kernel, evaluate any of the
11,166 required pairs, certify a continuous edge, or run a path planner.  Therefore:

- stage instances = 0/3;
- system pair queries = 0/11,166;
- path search authorized/executed = false/false;
- next-stage and release credit = false/false.

The 10 K rows remain outside the current 150-object pair universe until explicit
solar state/latch/HDRM authority activates them and a new universe hash is issued.
The 7 missing-category rows remain explicit debits.

## Reproduction

From the repository root:

```powershell
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/build_m01_scene_and_collision_prebind.py --write
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/build_m01_scene_and_collision_prebind.py --check
python -m pytest -q -p no:cacheprovider 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/test_m01_scene_and_collision_prebind.py
```
