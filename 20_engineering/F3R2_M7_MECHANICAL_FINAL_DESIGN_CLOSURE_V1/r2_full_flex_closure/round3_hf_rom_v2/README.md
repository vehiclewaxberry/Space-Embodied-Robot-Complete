# Solar R2 HF + five-mode ROM V2

This isolated package repairs the two demonstrated defects in the prior HF
candidate and closes the component-level HF/ROM evidence loop without changing
any frozen CAD, STEP, mass authority, e21 result, or older round.

Run from the project root:

```powershell
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/build_r2_hf_rom_v2.py
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/tests/independent_recompute.py
```

The builder writes only inside this directory. It models one deployed, latched
wing; LEFT and RIGHT use the same internal matrices and signed base-coupling
matrices. The technical Gate may pass with declared provisional physics, but it
never authorizes coupled dynamics, inherits no e15 result, grants no release
credit, and leaves Owner review pending.

The ROM also publishes all 183 reduced-HF coordinate semantics, modal
reconstruction operators for transverse nodes, bending slopes, hinge-relative
angles, torsion nodes and wing tip, plus a fail-closed quantitative small-angle
domain. The 0.05 rad / 0.03 m limits are `PROVISIONAL_DERIVED` kinematic bounds,
not material allowables or flight-qualification evidence.

Primary outputs:

- `R2_HF_MODEL_V2.yaml`
- `R2_HF_NUMERICAL_EVIDENCE_V2.json`
- `R2_FIVE_MODE_ROM_V2.json`
- `R2_FLEXIBILITY_VALIDITY_ENVELOPE_V2.json`
- `R2_HF_ROM_NUMERICAL_DATA_V2.npz`
- `tests/INDEPENDENT_RECOMPUTE_V2.json`
- `R2_FULL_FLEX_HF_ROM_GATE_V2.json`
