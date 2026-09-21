# ASM-00 Interface SSOT Preflight

This directory contains the fail-closed ASM-00 authorization preflight, the
machine classification of RF-1/RF-2/RF-3, and the frozen nine-criterion
single-source success evaluator contract.

It does **not** contain an interface SSOT v1, an HAG-A approval, a scientific
ASM-00 qualification run, or any ASM-01/ASM-02 implementation.

## Reproduction

From the repository root:

```powershell
python 30_simulation/asm_00_interface_preflight/tests/run_all.py
python 30_simulation/asm_00_interface_preflight/src/run_gate_ag0.py `
  --repo-root . `
  --planning-root "F:\China Graduate Future Flight Vehicle Innovation Competition"
```

The second command writes:

- `results/asm_00_gate_check.json`
- `results/evidence_manifest.json`

The command is deterministic: it records no wall-clock timestamp and sorts all
JSON keys. Missing or unverifiable authorization, raw-hash drift, missing
critical interface fields, and any RF state other than `RESOLVED` fail closed.
