# e18 B601 mission input branches

This package closes the **machine-readable, hash-bound input branching** needed to
continue M01, M05_22, M06_22 and M07_22 without pretending that missing physical
authority has been supplied.

## Engineering disposition

- `M01` contains an 11.5 s, 0.01 s-grid, arm-only quintic candidate between the
  mandatory contract endpoints. The source STOW identity, HDRM product, release
  sweep and `release_confirmed` signal remain `HOLD`/`null`.
- `M05_22` contains two explicitly non-mergeable target-state branches: the Sim13
  kinematic bootstrap and the static scene-manifest display placement.
- `M06_22` contains 20 half-sine equal-impulse **solver stimuli**. Peak-force values
  are mathematical waveform amplitudes, never hardware/contact-force evidence.
  Physical duration, force, pressure, normal and lock fields remain empty/null.
- `M07_22` binds the existing 4.5 s arm-only trajectory, both C08 diagnostic mass
  branches, and the independent Sim15 0.01 m/s full-state diagnostic branch.
  The locked transform, contact normals and released mass/CG/inertia remain null.

The accepted B601 URDF is read-only and pinned to
`1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`.
No CAD, mesh, geometry, mission, physical-contact, hardware, production-dynamics or
flight authority is created by this package. A validator PASS proves package
integrity only.

## Reproduce

From the repository root:

```text
python 30_simulation/e18_b601_mission_input_branches/src/build_mission_input_branches.py
python 30_simulation/e18_b601_mission_input_branches/tests/validate_mission_input_branches.py
```

Authoritative machine results are in `results/`.

