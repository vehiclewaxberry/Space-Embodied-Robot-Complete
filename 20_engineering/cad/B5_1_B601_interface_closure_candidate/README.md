# B5.1 B601 interface closure candidate

Task:

`COMP-PROT-03-A4-B5.1-B601-INTERFACE-CLOSURE-ARTICULATION-STOWAGE`

Current machine Gate: `B51_REVISE_INTERFACE_COLLISION`.

- Status: `B51_CURRENT_STATUS.md`
- Gate JSON: `07_VERIFICATION/B51_GATE.json`

This is an isolated engineering candidate. It does not overwrite V2.0, V2.1,
V2.2, the accepted B601 URDF, the vendor STEP, or the accepted B5.0 evidence.

Current authority boundaries:

- Kinematics, link mass, center of mass, and inertia: accepted B601 URDF only.
- Vendor CAD: geometry reference only.
- 25 degree base clocking: B5.1 engineering candidate only.
- Manufacturing, launch, strength, flight, and qualification authority: none.
- G05 and G08 geometry registration: `CHAIN_DERIVED_HOLD`.
- G08 two-prismatic-joint partition and zero calibration: HOLD until a
  traceable fixed-body/left-finger/right-finger partition exists.

All B5.1 writers must target this directory. The V2.2 donor was copied into
the isolated B5.1 baseline area; cold-reopen containment verified 56/56
references inside that copy. This grants reference-containment credit only.
