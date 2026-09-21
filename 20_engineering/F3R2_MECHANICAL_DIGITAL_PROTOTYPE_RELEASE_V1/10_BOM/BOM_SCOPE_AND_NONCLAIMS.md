# M4 digital-prototype BOM scope

`DIGITAL_PROTOTYPE_BOM_V1.csv` is an assembly completeness register for the competition digital prototype. It is not a procurement, manufacturing, flight, or launch BOM.

Every material, mass, tolerance, finish, supplier, and fastener field remains `UNSPECIFIED_HOLD`, `UNASSIGNED`, or `NOT_APPLICABLE` unless an active authority exists. Geometry volume must not be converted into mass. No supplier or vendor identity is inferred from a filename, model family name, or visual appearance.

The following gaps are release-blocking by design:

- The spacecraft-to-M3R load bridge is absent, so the structural load path is not geometrically continuous.
- The installed B601 object is a frame/axis witness, not physical arm hardware.
- Gripper R1 includes the palm only; separated finger and contact geometry are absent.
- The camera candidate pose was rejected because it penetrates the installed M3R B-rep.
- HDRM geometry is a nonphysical hidden skeleton with no frozen global transform.
- Target proxies are independent scenario assets with no frozen servicer-relative pose.

The BOM may be promoted only after each unresolved slot has a source-controlled part definition, frame placement, material/mass authority, interface and fastener definition, tolerance scheme, verification evidence, and an explicit release disposition.

