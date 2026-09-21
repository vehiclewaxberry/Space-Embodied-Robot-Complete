# ODR60 Option A — Route-C R121 operational-collision candidate umbrella

This package advances collision representation only. Phase A extracts the 20 root-static Route-C physical objects from the frozen V9F FCStd, maps the copied BReps from `A0@q=0` to spacecraft frame `S` with the exact current mount once, emits one primary STEP per object, and derives metre runtime sidecars from reopened STEP.

Current executable scope:

- R20 = 12 `base_link` objects + 8 `bus` objects;
- source frame = `A0 = B601 base_link at q=0`, millimetres;
- primary output = `S`, millimetres;
- runtime output = `S`, metres;
- source V9F FCStd is opened read-only and is never rebuilt or saved.

Remaining scope:

- R101 stays fail-closed until ordinary host-FK, J3 carriage and J4 telescope/follower motion adapters are independently frozen and validated;
- no current M01 registry admission, pair query, SAFE, edge, path, TMG-4, G12, next-stage or release credit is produced here.

Reproducible build:

```powershell
python 02_builder/build_route_c_root_static_r20.py --write
python 02_builder/build_route_c_root_static_r20.py --check
```

Use `--replace` only to reproduce generated package artifacts after an intentional contract or builder revision. The V9F straight-q negative witness at `-17.313396996697108 mm` remains immutable historical negative evidence.
