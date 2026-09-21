# CAD brief — Route-C Link2-B12 local collision candidates

- Model: twelve independent Route-C physical objects hosted by B601 `link2`.
- Task type: read-only extraction of frozen V9F BRep followed by host-local STEP emission; no geometry redesign.
- Source: `B601_ROUTE_C_GUIDED_DRESS_PACK_V9F.FCStd`, where `obj.Shape` already embodies `Object.Placement`.
- Units and frames: source `A0@q=0`, mm; primary STEP `link2@q1=q2=0`, mm; runtime sidecars `link2`, m.
- Positioning: `p_link2 = inv(T_A0_link2(0,0)) · p_A0_source`; runtime `p_S = T_S_A0 · T_A0_link2(q1,q2) · p_link2`.
- Frozen set: four L2 channel pieces, three clamps, saddle plus liner, rail and two stops.
- Explicit exclusion: J3 carriage, J3 moving clamp and six E210 links; those require the separate J3 carriage law.
- Topology target: twelve one-root, valid, closed, positive-volume, single-solid STEP files.
- Source-placement audit: exactly seven selected source objects have nonidentity `Object.Placement`; no placement may be reapplied.
- Runtime target: 36 sidecars, all derived from cold-reopened primary STEP with one `0.001` mm-to-m scale.
- FK target: accepted URDF raw joint1/joint2 chain on the Cartesian grid q1 `-2.8`, `0`, `2.8` rad × q2 `-3.14`, `-1.57`, `0` rad (nine configurations); current exact 12dp mount consumed directly; independent numerical fault controls reject q1-ignored and q1-sign-reversed adapters.
- Validation: independent source re-extraction, bilateral BRep difference, runtime manifold and volume, independent URDF parsing/FK, negative controls, fresh processes, pytest, CAD refs and one reviewed isometric snapshot per STEP.
- Authority boundary: local `PENDING_OWNER_AND_SYSTEM_BINDING` candidates only; system remains 1/150 operational, 0/11166 pair queries, SAFE/edge 0, stage 0/3, path false, TMG4 HOLD, G12 FAIL, next/release false.
