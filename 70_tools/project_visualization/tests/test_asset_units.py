"""VIZ-Gate 0 acceptance test 1 -- asset units & render-usability consistency.

Checks (read-only):
  A. 40_evidence/artifacts/visualization/tables/asset_audit.csv exists, has the expected 45 rows,
     and every row has a non-empty units declaration.
  B. usable_for_render is internally consistent: a row can only be usable if
     the file exists; values are strictly 'yes'/'no'.
  C. every mesh actually consumed by the render pipeline (asset_type ==
     mesh_stl AND usable_for_render == yes) is declared in METERS
     (units field starts with the token 'm', never 'mm').
  D. B601 mesh scale is re-verified against the URDF INDEPENDENTLY of the
     audit CSV: bbox extents of base_link.STL / link2.STL are compared to the
     URDF joint offsets they must bracket -- ratio must be order 1
     (0.1 < ratio < 10), i.e. NOT the ~1000x of a mm-unit mesh.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "70_tools", "project_visualization", "src"))
import _viz_bootstrap as vb  # noqa: E402  (pins OMP/MKL=1 BEFORE numpy)

import csv                    # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

import numpy as np            # noqa: E402

AUDIT_CSV = os.path.join(vb.VIZ_TABLES_DIR, "asset_audit.csv")
EXPECTED_ROWS = 45


def _urdf_joint_xyz(urdf_path, joint_name):
    root = ET.parse(urdf_path).getroot()
    for je in root.findall("joint"):
        if je.get("name") == joint_name:
            o = je.find("origin")
            return np.array([float(v) for v in o.get("xyz").split()])
    raise KeyError(joint_name)


def main(verbose=True):
    details = []
    assert os.path.isfile(AUDIT_CSV), f"missing {AUDIT_CSV}"
    with open(AUDIT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # A. row count + units declared everywhere
    assert len(rows) == EXPECTED_ROWS, \
        f"asset_audit.csv rows {len(rows)} != {EXPECTED_ROWS}"
    for r in rows:
        assert r["units"].strip(), f"{r['asset_id']}: empty units field"
    details.append(f"rows={len(rows)}, all units fields non-empty")

    # B. usable_for_render consistency
    for r in rows:
        assert r["usable_for_render"] in ("yes", "no"), \
            f"{r['asset_id']}: bad usable_for_render={r['usable_for_render']!r}"
        if r["usable_for_render"] == "yes":
            assert r["exists"] == "yes", \
                f"{r['asset_id']}: usable_for_render=yes but exists={r['exists']}"
            assert os.path.isfile(os.path.join(REPO, r["path"])), \
                f"{r['asset_id']}: file vanished: {r['path']}"
    n_usable = sum(r["usable_for_render"] == "yes" for r in rows)
    details.append(f"usable_for_render consistent ({n_usable} usable rows, "
                   "all exist on disk)")

    # C. every render-consumed mesh declared in meters (token 'm', not 'mm')
    mesh_rows = [r for r in rows if r["asset_type"] == "mesh_stl"
                 and r["usable_for_render"] == "yes"]
    assert mesh_rows, "no usable mesh_stl rows found"
    for r in mesh_rows:
        tok = r["units"].split()[0].rstrip("(,;")
        assert tok == "m", \
            f"{r['asset_id']}: render mesh units token {tok!r} != 'm'"
    details.append(f"{len(mesh_rows)} render meshes all declared in meters")

    # D. independent B601 scale re-verification (mesh bbox vs URDF offsets)
    from mesh_utils import load_mesh
    checks = [
        # (mesh file, bbox quantity, URDF joint, offset component)
        ("base_link.STL", "z_max", "joint1", 2),
        ("link2.STL", "x_span", "joint3", 0),
    ]
    for fname, qty, joint, comp in checks:
        mesh = load_mesh(os.path.join(vb.MESH_DIR, fname))
        V = np.asarray(mesh.vertices, float)
        if qty == "z_max":
            extent = float(V[:, 2].max())
        else:
            extent = float(V[:, 0].max() - V[:, 0].min())
        off = abs(float(_urdf_joint_xyz(vb.URDF_PATH, joint)[comp]))
        ratio = extent / off
        assert 0.1 < ratio < 10.0, \
            (f"{fname}: bbox {qty}={extent:.4f} vs URDF {joint} offset "
             f"{off:.4f} -> ratio {ratio:.1f} (mm-unit mesh would be ~1000)")
        details.append(f"{fname} {qty}={extent:.4f} m vs {joint} offset "
                       f"{off:.4f} m -> ratio {ratio:.3f} (order 1, not 1000)")

    if verbose:
        for d in details:
            print("  " + d)
    return {"name": "test_asset_units", "pass": True, "details": details}


if __name__ == "__main__":
    print("test_asset_units:")
    main()
    print("PASS")
