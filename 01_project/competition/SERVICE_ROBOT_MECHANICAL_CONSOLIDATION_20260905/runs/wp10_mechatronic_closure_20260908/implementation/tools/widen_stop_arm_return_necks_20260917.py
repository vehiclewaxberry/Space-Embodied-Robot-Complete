# Widen the three ARM_RETURN 0.25 mm pad-entry necks at J106 (JST GH 1.25 mm) to the
# 0.4 mm net main width. Routing-only change, no schematic/netlist impact.
# Evidence chain link: results/stop_v36/pcb/layout_20260916/return_repair_e/
# KiCad 10 python (pcbnew SWIG). Writes the board in place.
from pathlib import Path
import hashlib, json
import pcbnew as k

A = Path(__file__).resolve().parents[1]
BOARD = A / "ecad/revisions/v36/wp10_stop_control.kicad_pcb"
OUT = A / "results/stop_v36/pcb/layout_20260916/return_repair_e"
OUT.mkdir(parents=True, exist_ok=True)

UUIDS = {
    "0928a911-19b3-465c-815b-d1a249544b90",
    "17300401-4101-4698-91ae-c36b4528674c",
    "9db486a8-e2ec-47ca-822d-7406537b4ad5",
}
TARGET_NM = 400000  # 0.4 mm

plan = {
    "schema": "WP10_V36_STOP_NECK_WIDEN_PLAN",
    "date": "2026-09-17",
    "reason": "engineering review item 5 (grounding): remove the three 0.25 mm ARM_RETURN necks; widen to the 0.4 mm net main width",
    "segments": sorted(UUIDS),
    "target_width_mm": 0.4,
    "clearance_check": "worst post-widen clearance to adjacent J106 pad = 0.675 mm >= 0.5 mm board min_clearance",
    "whole_design_complete": False,
}
plan_path = OUT / "NECK_WIDEN_PLAN.json"
plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

before = sha(BOARD)
b = k.LoadBoard(str(BOARD))
changed = []
for t in b.GetTracks():
    if t.Type() == k.PCB_TRACE_T and str(t.m_Uuid.AsString()) in UUIDS:
        old = t.GetWidth()
        t.SetWidth(TARGET_NM)
        changed.append({"uuid": str(t.m_Uuid.AsString()), "old_width_nm": old, "new_width_nm": t.GetWidth()})
assert len(changed) == 3, f"expected 3 neck segments, matched {len(changed)}"
assert k.SaveBoard(str(BOARD), b), "SaveBoard failed"
after = sha(BOARD)
receipt = {
    "board_before_sha256": before,
    "board_after_sha256": after,
    "plan_sha256": sha(plan_path),
    "moved": 3,
    "detail": changed,
    "whole_design_complete": False,
}
(OUT / "ESCAPE_APPLIED.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt, indent=2))
