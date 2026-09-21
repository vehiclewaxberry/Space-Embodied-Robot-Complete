# WP2 V3 R2 CM-only reissue V2

## Scope

This directory repairs only the impossible self-reference in
`WP2_V3_R2_RECEIPT.json`.  It does not replace or rewrite that receipt,
`SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml`, either parent input, the Solar R2
geometry/mass model, or the V3 R2 aggregator.

The old receipt was emitted twice.  Its first emission contained an empty
`hashes` object; the builder hashed those bytes and then wrote the digest into
the same receipt.  The second emission therefore had different bytes.  The
recorded digest is exactly reproducible from the first CRLF emission, but it
cannot equal the final file's digest.

## Hash policy

The policy is `SELF_REFERENCE_EXCLUDED`:

- `WP2_CM_ONLY_RECEIPT_V2.json` pins every declared upstream source but does
  not claim a hash of itself or of downstream package members.
- `WP2_CM_REISSUE_GATE_V2.json` consumes the receipt and remains self-excluded.
- `WP2_CM_REISSUE_MANIFEST_V2.json` pins every other member of this directory
  and excludes only itself.
- `validate_cm_reissue_v2.py` independently recomputes all raw-byte SHA-256
  values, reconstructs the old builder's first emission, checks the
  non-self-reference payload digest, and checks package-member hashes.

No scientific payload is copied into the CM receipt.  The legacy receipt's
top-level object with only `hashes` removed is the preservation projection.
Its canonical digest is pinned, while the authoritative scientific file is
pinned by its raw-byte digest.

## Authority boundary

The package may close this one CM integrity defect at package scope.  It grants
no Owner acceptance, no next-stage authorization, no mechanical release, and
no manufacturing, qualification, launcher, or flight authority.  All existing
harness, full-flex, e15, calibration, as-built, and qualification holds remain.

Run the independent check from the repository root:

```text
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/cm_reissue_v2/validate_cm_reissue_v2.py
```

