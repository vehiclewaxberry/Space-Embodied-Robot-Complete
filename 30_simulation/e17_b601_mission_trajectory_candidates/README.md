# e17 — B601 mission trajectory candidates

This isolated package converts the current eight-segment B601 mission contract
into auditable, **non-release** numerical seeds. It does not modify the accepted
URDF, does not create Route-C CAD, and does not upgrade any mission, collision,
harness, contact, SAFE-00, or hardware-motion gate.

Current scope:

- numerical arm-only quintic seeds: M02, M03, M04, M05_150 and M07_22;
- symbolic arm-hold/contact scaffold: M06_22, with physical timing and contact
  values left null;
- blocked and intentionally uninstantiated: M01 and M05_22;
- all eight mission segments remain `released_for_mission_gate=false`.

Run from the repository root:

```text
python 30_simulation/e17_b601_mission_trajectory_candidates/src/build_trajectory_candidates.py
python 30_simulation/e17_b601_mission_trajectory_candidates/tests/validate_trajectory_candidates.py
```

The phrase `NUMERIC_SEED_WELL_FORMED_ONLY` means only that deterministic sample
files match their declared quintic equations, endpoints, provisional class
limits and hashes. It is not a scientific or mechanical PASS.

Current independent result: 42/42 integrity checks and 10/10 negative controls
pass; the machine verdict is
`PASS_NUMERIC_SEED_INTEGRITY_ONLY__MISSION_RELEASE_REMAINS_HOLD`. The accepted
URDF hash remains
`1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`, and
this package contains zero geometry artifacts.
