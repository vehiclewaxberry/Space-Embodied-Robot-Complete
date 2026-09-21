# B51 HDRM functional interface

Status: `FUNCTIONAL_ENVELOPE_ONLY_DEVICE_AND_RELEASE_PATH_HOLD`

The current G07 and G08 STEP candidates each contain one body labelled
`HDRM_CENTER_ENVELOPE_NON_PHYSICAL_HOLD`.  These bodies reserve volume only and
must be excluded from physical collision counts, BOM mass and load-path claims.

The eventual interface shall define:

- preload direction and reaction surface;
- positive release direction that exits the arm sweep;
- launch restraint in vertical, lateral and axial directions;
- electrical/pyrotechnic or non-explosive release boundary;
- released-item retention;
- independent release confirmation and arm-lift interlock;
- maintenance access and replacement direction.

No HDRM model, preload, stroke, released clearance, harness or sensor is
selected.  `G4` remains HOLD.

