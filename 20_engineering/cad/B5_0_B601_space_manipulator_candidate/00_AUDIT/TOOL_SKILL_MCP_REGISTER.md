# Tool, Skill and MCP Register

## Native SolidWorks writer

- SolidWorks: 2024 SP5, `32.5.0.0048`
- COM ProgID: `SldWorks.Application.32`
- COM CLSID: `{afbec3b2-b1a6-4908-b608-d97d2aab5498}`
- Python: 3.13.9 x64
- PyWin32: 311 with SolidWorks 32.0 makepy cache
- .NET interop:
  - `SolidWorks.Interop.sldworks 32.5.0.48`
  - `SolidWorks.Interop.swconst 32.5.0.48`
- Status: `AVAILABLE_WITH_EARLY_BOUND_EXCLUSIVE_WRITER`

PowerShell dynamic COM is rejected because setting `Visible` reproduced `TYPE_E_ELEMENTNOTFOUND`.

## Templates

The writer must hash-pin:

- `gb_part.prtdot`: expected SHA prefix `5DA21678`
- `gb_assembly.asmdot`: expected SHA prefix `37DED926`
- `gb_a3.drwdot`: expected SHA prefix `B376D09B`

The exact resolved paths and full hashes are captured by the tool smoke.

Correct SolidWorks template preference enums are:

- part: `8`
- assembly: `9`
- drawing: `10`

Old V2.2 values `24/25/26` are not reused.

## CAD tools

- `cad:cad` skill:
  - STEP-first inspection;
  - deterministic refs/facts/planes/positioning;
  - mandatory snapshots;
  - STEP to STL derivation.
- `cad:cad-viewer`:
  - live visual handoff for explicit STEP/STL/URDF artifacts.
- OCP/build123d/trimesh:
  - installed and available for cold-read, geometry inspection and derived meshes.

Native SolidWorks remains required for the requested SLDPRT/SLDASM/SLDDRW source files. STEP is the primary cross-tool validated handoff.

## URDF tools

- `cad:urdf` skill:
  - design/frame ledger;
  - source generator;
  - generation-time graph, axis, inertial and mesh validation.
- Existing accepted consumer:
  - `30_simulation/sim_05_free_floating_arm/b601_model.py`
- Existing checks:
  - `test_urdf_structure.py`
- Project-level CAD→URDF/MJCF/USD/Isaac converter:
  - `NOT_FOUND`

## ROS2, Isaac Sim and MuJoCo

Runtime usability must be detected before Phase 5. Their absence is a tool `HOLD`, not evidence that the CAD phase failed.

## Online and third-party sources

No public web source is admitted automatically. Any later source must record URL, version/commit, license and use. Unknown commercial CAD is prohibited.

## Writer safety rules

1. Precondition: `SLDWORKS.exe` count is zero.
2. Start an exclusive early-bound SolidWorks instance; never attach with `GetActiveObject`.
3. Write only below the candidate root.
4. Save-return code is not sufficient: also inspect error/warning, file existence, size and hash.
5. Exit SolidWorks in `finally`.
6. Cold reopen in a fresh instance.
7. Reject references outside the candidate root.
8. Export STEP; verify with OCP/CAD CLI.
9. Derive STL from the verified STEP.
10. Require no stale `~$` files and a final process count of zero.
