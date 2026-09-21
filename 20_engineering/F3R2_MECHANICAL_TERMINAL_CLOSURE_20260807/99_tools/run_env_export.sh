#!/bin/sh
# F3R2 environment-mesh export driver.
# usage: run_env_export.sh <TAG> <STEP_BASENAME> [DEFLECTION]
# One FreeCAD process per STEP: this machine silently exits FreeCAD if a single
# process imports several 126 MB STEP files.
set -e
R2="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
ST="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/04_configurations/G2/step"
FC="G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe"

TAG="$1"
STEPNAME="$2"
DEF="${3:-0.4}"

export F3R2_STEP="$ST/$STEPNAME"
export F3R2_OUTDIR="$R2/05_clearance/mesh"
export F3R2_TAG="$TAG"
export F3R2_DEFLECTION="$DEF"

mkdir -p "$R2/99_tools/logs"
"$FC" "$R2/99_tools/fc_export_env_mesh.py" > "$R2/99_tools/logs/fc_env_$TAG.txt" 2>&1
echo "exit=$?"
tr '\r' '\n' < "$R2/99_tools/logs/fc_env_$TAG.txt" | grep -v '%' | tail -12
