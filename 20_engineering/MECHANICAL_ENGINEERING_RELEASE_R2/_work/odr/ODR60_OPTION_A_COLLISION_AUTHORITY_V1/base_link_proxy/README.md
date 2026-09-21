# B601 base_link operational collision authority V1

This directory closes only WP11-F-01 for the `base_link` collision representation. The accepted URDF remains frozen and authoritative for kinematics, topology, joint limits, mass, and inertia. The filtered B50 STEP controls physical geometry.

## Fixed artifact contract and current HOLD

- `BASE_LINK_OPERATIONAL_COLLISION_V1.npz`: canonical machine authority (`vertices_m`, `faces`, `solid_ids`, `units`, `frame`).
- `BASE_LINK_OPERATIONAL_COLLISION_V1.stl`: deterministic binary compatibility/display sidecar; coordinates are metres.
- `BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V1.json`: source pins, frame contract, BRep/mesh metrics, and fail-closed gate.
- `BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V1.json`: independent load/replay validation report.

Current machine truth is `BASE_LINK_OPERATIONAL_COLLISION_HOLD_DIAGNOSTIC_V1.json`: all three attempted closure routes fail, so the NPZ, STL, and PASS receipt are intentionally absent. The validation report checks that absence and preserves `proxy_pass=false`.

## Reproduction

Use UTF-8 Python mode because the workspace contains non-ASCII paths and the host's legacy code-page selection can otherwise misdecode unrelated catalog sources.

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
python generate_base_link_operational_collision.py --emit
python generate_base_link_operational_collision.py --verify-existing
python validate_base_link_operational_collision.py --write-report
python -m pytest -q test_base_link_operational_collision.py
```

The generator is single-process and rejects source-hash drift, frame drift, geometry defects, plate-region contamination, and output overwrite unless `--replace` is explicit. It never opens the raw accepted-URDF `base_link.STL`; that mesh's known hash is used only as a forbidden-output sentinel.

No command in this directory runs Route-C trajectory or path search.
