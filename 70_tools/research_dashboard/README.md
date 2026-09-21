# Research integration v1

This directory integrates the read-only P0-A, P0-B, and P0-C machine evidence
into a deterministic offline research dashboard. The final verdict is
`REPEAT_CORE`; this package does not authorize E2, G3, or HIL.

The integration keeps the two experiment populations separate:

- `P0-A-CORE-72`: 3 grasp points × 4 phases × 3 speeds × 2 task modes.
- `P0-C-SYNC-216`: the same design axes × 3 synchronization values (`alpha`).

The unified table always carries a campaign discriminator. It never fills
upstream-rejected values with zero, and it keeps candidate-level flexible
evidence as `UNKNOWN` until cross-solver certification is available.

## Build

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python 70_tools/research_dashboard/build_research_dashboard.py
```

The generated single-file dashboard is:

`40_evidence/artifacts/visualization/project_visualization_v1_research.html`

## Validate

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python 70_tools/research_dashboard/tests/run_all.py
```

The suite validates the frozen v0 hash and tag, VIZ 22/22 snapshot hashes,
29/29 freeze hashes, 45/45 audited assets, all three P0 accounting contracts,
the low-impulse Pareto choice, one-and-only-one verdict, disabled later-stage
authorization, source hashes, offline packaging, and two-run byte determinism.

Source-inventory fingerprints canonicalize CRLF/LF differences for text inputs
so a clean Windows checkout reproduces the same package. The accepted v0 HTML
is the exception: its published gate hash remains a raw-file-byte SHA-256. The
external v1 HTML is emitted with the repository's Windows CRLF convention;
files inside `70_tools/research_dashboard` remain LF.

No long-running ANCF solve is started by either command.
