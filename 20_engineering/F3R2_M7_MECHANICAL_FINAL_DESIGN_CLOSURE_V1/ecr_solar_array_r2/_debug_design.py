# -*- coding: utf-8 -*-
"""Debug: per-connector diagnostics at one pose for the harness design."""
import math
import sys
from pathlib import Path

import numpy as np
import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sweep_b601_harness_full_fk as H


def main():
    q6 = [0.0] * 6
    if len(sys.argv) > 2:
        q6 = [float(x) for x in sys.argv[2].split(",")]
    mount_rows = H.load_mount()
    arm = H.ArmModel(H.URDF, mount_rows)
    fields_local = {}
    verts_local = {}
    for l in H.ARM_LINKS:
        tris = H.mesh_tris(H.STL_DIR / (l + ".STL"))
        fields_local[l] = H.TriField(l, tris)
        V = tris.reshape(-1, 3)
        verts_local[l] = np.unique(np.round(V, 3), axis=0)
    rail_verts = []
    for rp in H.RAIL_STEPS:
        rail_verts.append(H.shape_tris(Part.read(str(rp)), 0.3).reshape(-1, 3))
    rail_verts = np.vstack(rail_verts)
    rail_fields = []
    for rp in H.RAIL_STEPS:
        rail_fields.append(H.TriField(rp.stem, H.shape_tris(Part.read(str(rp)), 0.3)))
    bus = H.BoxField("BUS_PROXY", (-170.25, -113.15, -113.15),
                     (170.25, 113.15, 113.15))
    design = H.HarnessDesign(arm, verts_local, rail_verts,
                             fields_local=fields_local,
                             rail_fields=rail_fields, bus_field=bus)
    print("crossings:")
    for jn, c in design.crossings.items():
        print("  %-7s r=%7.2f alpha=%7.1f s=%6.1f house=%s" % (
            jn, c["radius"], math.degrees(c["alpha"]), c["station"],
            None if c["housing_radius"] is None else round(c["housing_radius"], 2)))
    for name, sp in sorted(design.spans.items()):
        print("SPAN %-8s L=%7.1f R=%7.2f dm=%7.2f" % (
            name, sp[1], sp[2], sp[3]))
    for name, (fam, ctrl) in sorted(design._span_debug.items()):
        if name in ("link1", "link4", "link5"):
            print("CTRL", name, fam, "n=%d" % len(ctrl))
            for c in ctrl:
                print("   ", c)
    P, L, Rmin, Rwhere, secs = design.build(q6)
    conns, fillets, trims, nodes = design.last_build
    print("total L=%.1f Rmin=%.2f (%s)  npts=%d" % (L, Rmin, Rwhere, len(P)))
    TS = arm.fk_S(q6)
    for i, c in enumerate(conns):
        pts, Ll, Rc = c.sample()
        info = "%2d %-14s L=%8.1f R=%8.2f" % (
            i, getattr(c, "label", c.kind), Ll, Rc)
        Rd = H.discrete_radius(pts)
        im = int(np.argmin(Rd))
        print(info, " Rmin_at=%s" % np.round(pts[min(im + 1, len(pts) - 1)], 1))
        # min clearance of this connector vs every arm link
        worst = (1e9, None)
        for lname in H.ARM_LINKS:
            T = TS[lname]
            Pl = (pts - T[:3, 3]) @ T[:3, :3]
            fld = fields_local[lname]
            lb = fld.aabb_lb(Pl)
            idx = np.where(lb < 30.0)[0]
            if len(idx) == 0:
                continue
            for ii in idx:
                d, exact = fld.min_dist(Pl[ii])
                if exact and d < worst[0]:
                    worst = (d, lname)
        print(info, " worst_d=%8.2f vs %s" % (worst[0], worst[1]))
    for ni, f in sorted(fillets.items()):
        print("fillet node %2d: R=%7.2f trim=%6.2f L=%6.2f" % (ni, f[2], f[3], f[1]))


if __name__ == "__main__" or (len(sys.argv) > 1 and Path(sys.argv[1]).stem == __name__):
    main()
