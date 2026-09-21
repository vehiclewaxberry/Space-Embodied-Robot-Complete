# B51 Master Skeleton canonical deviation — HOLD

Status: `MASTER_SKELETON_NATIVE_PART_NOT_AUTHORIZED_FROM_CURRENT_DATUM_SET`

The current datum register and generated adapter/saddle STEP candidates were
derived from the legacy longeron-centre value `|Y|=|Z|=105.65 mm`.  The locked
canonical native V2.2 source states:

- longeron/frame centre: `101.65 mm`;
- primary-structure outer surface: `110.15 mm`;
- removable-panel outer surface: `113.15 mm`.

The current B5.1 saddle shoes start at `Z=113.15 mm`.  Exact BREP checks
therefore place both saddles on the removable-panel surface and `3.0 mm` away
from the primary load structure.  The native file
`B51_B601_INSTALLATION_MASTER_SKELETON.SLDPRT` has not been created because
freezing the incorrect `105.65 mm` datum into a native skeleton would propagate
the mismatch into every downstream part.

## Required redesign gate

1. Supersede, without deleting, the legacy `105.65 mm` datum with the
   canonical `101.65 mm` centre and `110.15 mm` load-surface definitions.
2. Decide whether the saddle uses a qualified panel penetration/cutout, an
   independent frame/longeron shoe, or another explicit load-transfer detail.
3. Preserve the `113.15 mm` panel surface as a separate occurrence; it must not
   be relabelled as primary structure.
4. Rebuild bridge/saddle parts from the corrected skeleton and rerun the
   append-only 28-row mapping and exact-BREP audit.
5. Only after those checks may a native Master Skeleton be authored and used
   as downstream position authority.

The 25-degree clock remains
`RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY`.  H9 remains
`HUMAN_DECISION_REQUIRED`.

