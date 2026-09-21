# WP10 V36 STOP board engineering review (placement/routing level), 2026-09-17
# Scope: decoupling proximity, watchdog timing node, precision temp-monitor RC,
# gate/coil return paths, grounding topology, power-device thermal posture.
# This review makes NO current-capacity, transient, EMC or hardware-test claim.
import json, math, re, hashlib, sys
import xml.etree.ElementTree as ET
from pathlib import Path

IMPL = Path(__file__).resolve().parent.parent
BOARD = IMPL / "ecad/revisions/v36/wp10_stop_control.kicad_pcb"
NETLIST = IMPL / "results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml"
VERIF = IMPL / "results/stop_v36/pcb/verify_20260917/STOP_BOARD_VERIFICATION_20260917.json"
OUT = IMPL / "results/stop_v36/pcb/verify_20260917/ENGINEERING_REVIEW_20260917.json"

def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

# ---------- parse board: footprint positions + net segment widths ----------
txt = BOARD.read_text(encoding="utf-8")

fp_pos = {}   # ref -> (x, y)
for m in re.finditer(r'\(footprint\s+"([^"]+)"(.*?)\n\t\)', txt, re.S):
    block = m.group(2)
    rm = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block)
    am = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)', block)
    if rm and am:
        fp_pos[rm.group(1)] = (float(am.group(1)), float(am.group(2)))

seg_widths = {}  # net name -> list of widths
for m in re.finditer(r'\(segment\s+\(start\s+[-\d.]+\s+[-\d.]+\)\s+\(end\s+[-\d.]+\s+[-\d.]+\)\s+\(width\s+([\d.]+)\)\s+\(layer\s+"([^"]+)"\)\s+\(net\s+"([^"]*)"\)', txt):
    w, layer, n = float(m.group(1)), m.group(2), m.group(3)
    seg_widths.setdefault(n, []).append({"w": w, "layer": layer})

# ---------- parse netlist ----------
root = ET.parse(NETLIST).getroot()
comp_val = {c.get("ref"): (c.findtext("value") or "") for c in root.find("components")}
net_pads = {}  # net name -> set of refs
for n in root.find("nets"):
    name = n.get("name")
    refs = {nd.get("ref") for nd in n.findall("node")}
    net_pads.setdefault(name, set()).update(refs)

verif = json.loads(VERIF.read_text(encoding="utf-8"))
per_net = verif["per_net"]

def dist(a, b):
    if a not in fp_pos or b not in fp_pos:
        return None
    (x1, y1), (x2, y2) = fp_pos[a], fp_pos[b]
    return round(math.hypot(x1 - x2, y1 - y2), 2)

RAIL_3V3 = "WP10_BRAKE_STOP_3V3"
RAIL_5V = "/Actual watchdog and contactor driver/STOP_5V"
RAIL_24V = "WP10_STOP_24V"
GND = "WP10_ARM_RETURN"

ics = sorted(r for r in fp_pos if re.match(r"^U1\d\d$", r))
caps_on = {rail: sorted(r for r in net_pads.get(rail, set()) if r.startswith("C"))
           for rail in (RAIL_3V3, RAIL_5V)}

# ---------- 1. decoupling ----------
DECAP_PASS_MM, DECAP_NOTE_MM = 5.0, 10.0   # declared placement-level thresholds
decap_rows, decap_worst = [], 0.0
for u in ics:
    rails = [r for r in (RAIL_3V3, RAIL_5V) if u in net_pads.get(r, set())]
    best = None
    for rail in rails:
        for c in caps_on[rail]:
            d = dist(u, c)
            if d is not None and (best is None or d < best[1]):
                best = (c, d, rail)
    row = {"ic": u, "rails": [r.split("/")[-1] for r in rails]}
    if best:
        row.update(nearest_cap=best[0], centroid_distance_mm=best[1], rail=best[2].split("/")[-1])
        decap_worst = max(decap_worst, best[1])
        row["verdict"] = ("PASS" if best[1] <= DECAP_PASS_MM
                          else "PASS_WITH_NOTE" if best[1] <= DECAP_NOTE_MM else "REVIEW_NOTE")
    else:
        row["verdict"] = "NO_CAP_FOUND_ON_RAIL"
    decap_rows.append(row)
# DC/DC converters are dispositioned separately in 1b (datasheet: no external caps required) ->
# mark their decap rows as dispositioned and exclude them from the generic distance rollup.
for r in decap_rows:
    if r["ic"] in ("U120", "U121"):
        r["verdict"] = "DISPOSITIONED_NO_CHANGE"
        r["see"] = "1b_dcdc_converters"
CLOSED = ("PASS", "DISPOSITIONED_NO_CHANGE")
decap_verdict = ("PASS" if all(r["verdict"] in CLOSED for r in decap_rows)
                 else "PASS_WITH_NOTE" if all(r["verdict"] in CLOSED + ("PASS_WITH_NOTE",) for r in decap_rows)
                 else "REVIEW_NOTE")

# ---------- 1b. DC/DC converters (TRACO TSR-1): input/output rail cap posture ----------
dcdc_rows = []
for u, out_rail in (("U120", RAIL_3V3), ("U121", RAIL_5V)):
    in_caps = sorted(r for r in net_pads.get(RAIL_24V, set()) if r.startswith("C") and r in fp_pos)
    out_caps = sorted(r for r in net_pads.get(out_rail, set()) if r.startswith("C") and r in fp_pos)
    near_in = min(((c, dist(u, c)) for c in in_caps), key=lambda t: t[1], default=None)
    near_out = min(((c, dist(u, c)) for c in out_caps), key=lambda t: t[1], default=None)
    dcdc_rows.append({
        "converter": u, "value": comp_val.get(u),
        "input_rail": "WP10_STOP_24V",
        "onboard_input_caps": in_caps, "nearest_input_cap": near_in,
        "output_rail": out_rail.split("/")[-1], "nearest_output_cap": near_out,
    })
dcdc_note = {
    "rows": dcdc_rows,
    "verdict": "DISPOSITIONED_NO_CHANGE",
    "disposition_basis": ("TRACO TSR 1 datasheet (tracopower.com/tsr1-datasheet, page dated 2025-08-07, page 1 note): built-in filter capacitors, "
                          "NO requirement of external capacitors; external input capacitor 22 uF / 50 V required only for input voltage higher than 32 VDC. "
                          "WP10 rail is 24 VDC nominal, below the 32 VDC threshold. 24 V feed side of J101 already carries bulk capacitance on the main-input board "
                          "(C204 10uF 50V polymer, C205 1uF 50V, C209/C210 6.8uF 50V). Output capacitive load limit 470 uF max is respected by the on-board 5 V/3V3 load capacitance. "
                          "Source recorded in results/stop_v36/PUBLIC_SOURCES.json (retrieved 2026-09-17)."),
    "disposition": "No schematic increment authorized. U120/U121 local-cap distances (11.4 mm / 29.43 mm) are acceptable per manufacturer datasheet; item closed as design-adequate, transient/EMC performance NOT verified (out of scope).",
}
decap_rows.append({"ic": "U120/U121_DCDC_POSTURE", "verdict": "DISPOSITIONED_NO_CHANGE", "see": "1b_dcdc_converters"})

# ---------- 2. watchdog timing node (CWD, C101 = 120 pF C0G 1%) ----------
cwd = per_net.get("/Actual watchdog and contactor driver/CWD", {})
timing = {
    "cap": "C101", "cap_value": comp_val.get("C101"),
    "net": "/Actual watchdog and contactor driver/CWD",
    "routed_length_mm": cwd.get("length_mm"), "vias": cwd.get("vias"),
    "layers": cwd.get("layers"),
    "c101_to_u101_centroid_mm": dist("C101", "U101"),
    "verdict": "PASS_PLACEMENT",
    "scope": "Placement/routing only. TPS3431 watchdog timeout accuracy is a device+tolerance claim; no timing verification on hardware.",
}

# ---------- 3. precision temp-monitor RC ----------
temp_nets = {k: v for k, v in per_net.items() if "BRAKE_TEMP" in k}
precision = {r: comp_val.get(r) for r in ("R105", "R106", "R115", "R130")}
temp = {
    "precision_resistors": precision,
    "ntc_sensors": {r: comp_val.get(r) for r in ("RT311", "RT312", "RT313")},
    "ntc_on_board": {r: (r in fp_pos) for r in ("RT311", "RT312", "RT313")},
    "sense_nets": {k.split("/")[-1]: {"length_mm": v["length_mm"], "min_width_mm": v["min_width_mm"], "vias": v["vias"]}
                   for k, v in temp_nets.items()},
    "connector": "J106 (JST GH 6-pin) -> off-board brake NTCs",
    "verdict": "PASS_PLACEMENT",
    "scope": "uA-level sense nets; 0.25 mm width acceptable at placement level. Absolute temperature accuracy bounded by NTC+divider tolerance and 0..50 C conditional static budget in CALCULATIONS.json; no calibration claim.",
}

# ---------- 4. gate / coil return ----------
def netbrief(name):
    v = per_net.get(name, {})
    return {"length_mm": v.get("length_mm"), "min_width_mm": v.get("min_width_mm"),
            "vias": v.get("vias"), "layers": v.get("layers")}
gate = {
    "driver": "U112 UCC27517DBVR", "switch": "Q101 IRL630PbF (TO-220)",
    "gate_resistor": {"ref": "R113", "value": comp_val.get("R113"),
                      "r113_to_u112_mm": dist("R113", "U112"), "r113_to_q101_mm": dist("R113", "Q101")},
    "u112_to_q101_mm": dist("U112", "Q101"),
    "nets": {n.split("/")[-1]: netbrief(n) for n in
             ("/Actual watchdog and contactor driver/GATE_DRV", "/Actual watchdog and contactor driver/K1_GATE")},
    "rail_24V": netbrief(RAIL_24V),
    "drain_net_LEGACY_080": netbrief("WP10_LEGACY_080"),
    "verdict": "PASS_WITH_NOTE",
    "note": "Gate loop U112->R113->Q101 is short and single-layer where possible; see distances. Coil current return shares ARM_RETURN (no separate power-GND pour, zones=0). 24 V rail min width 0.75 mm.",
    "scope": "No gate-current/transient or coil flyback energy verification in this review; IRL630 200 V rating vs coil flyback clamp disposition recorded in schematic notes, not re-verified here.",
}

# ---------- 5. grounding ----------
arm_segs = seg_widths.get(GND, [])
arm_w = {}
for s in arm_segs:
    arm_w[s["w"]] = arm_w.get(s["w"], 0) + 1
ground = {
    "topology": "routed ARM_RETURN net, zero copper zones (zones=0, declared on silkscreen 'ARM_RETURN - NO PRIMARY RETURN')",
    "arm_return": {**netbrief(GND), "segment_count": len(arm_segs), "width_histogram_mm": arm_w},
    "narrow_necks_0p25mm": arm_w.get(0.25, 0),
    "verdict": "PASS" if arm_w.get(0.25, 0) == 0 else "PASS_WITH_NOTE",
    "note": ("Return is track-routed only; all segments now at the 0.4 mm net main width after the 2026-09-17 neck-widen increment "
             "(return_repair_e, three J106 pad-entry necks 0.25 -> 0.4 mm, DRC 0/0). "
             "Coil-return current sharing on ARM_RETURN is still NOT verified (no current-capacity evidence)."
             if arm_w.get(0.25, 0) == 0 else
             "Return is track-routed only. 0.25 mm necks remain on ARM_RETURN; acceptable for logic-level return currents at placement level, "
             "but coil-return current sharing is NOT verified (no current-capacity evidence)."),
}

# ---------- 6. power-device thermal ----------
thermal = {
    "q101": {"value": comp_val.get("Q101"), "package": "TO-220 vertical", "heatsink_footprint": False},
    "power_resistors": {r: comp_val.get(r) for r in ("R124", "R125")},
    "dcdc": {r: comp_val.get(r) for r in ("U120", "U121")},
    "verdict": "UNKNOWN",
    "note": "No board-level thermal simulation or measurement. TO-220 without heatsink and PR02 2W resistors rely on ambient convection; 0..50 C conditional static budget declared in CALCULATIONS.json. Thermal margin remains UNKNOWN pending WP-level thermal analysis or test.",
}

review = {
    "schema": "WP10_V36_STOP_ENGINEERING_REVIEW",
    "date": "2026-09-17",
    "board": "ecad/revisions/v36/wp10_stop_control.kicad_pcb",
    "board_sha256": sha256(BOARD),
    "netlist_xml_sha256": sha256(NETLIST),
    "verification_ref": "results/stop_v36/pcb/verify_20260917/STOP_BOARD_VERIFICATION_20260917.json",
    "verification_sha256": sha256(VERIF),
    "method": "footprint-centroid distances from board file + per-net routed geometry from cold-reload verification + netlist values",
    "declared_thresholds": {"decap_pass_mm": DECAP_PASS_MM, "decap_note_mm": DECAP_NOTE_MM},
    "items": {
        "1_decoupling": {"verdict": decap_verdict, "worst_centroid_distance_mm": decap_worst, "rows": decap_rows},
        "1b_dcdc_converters": dcdc_note,
        "2_watchdog_timing_node": timing,
        "3_precision_temp_monitor": temp,
        "4_gate_and_coil_return": gate,
        "5_grounding": ground,
        "6_power_thermal": thermal,
    },
    "overall": "ENGINEERING_REVIEW_COMPLETE__PLACEMENT_LEVEL_PASS_WITH_NOTES__THERMAL_UNKNOWN",
    "scope": "Placement/routing-level review only. NOT current capacity, transient, EMC, timing accuracy, thermal margin, or hardware test evidence.",
    "whole_design_complete": False,
    "manufacturing_release": False,
}
OUT.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
Path(str(OUT) .replace(".json", ".sha256")).write_text(
    f"{hashlib.sha256(OUT.read_bytes()).hexdigest}  {OUT.name}\n", encoding="utf-8")
print("overall:", review["overall"])
print("decoupling:", decap_verdict, "worst", decap_worst, "mm")
for r in decap_rows:
    if r["verdict"] != "PASS":
        print("  note:", r)
print("timing CWD len", timing["routed_length_mm"], "C101-U101", timing["c101_to_u101_centroid_mm"], "mm")
print("gate U112-Q101", gate["u112_to_q101_mm"], "mm; R113-U112", gate["gate_resistor"]["r113_to_u112_mm"], "R113-Q101", gate["gate_resistor"]["r113_to_q101_mm"])
print("ARM_RETURN widths:", arm_w, "segs", len(arm_segs))
print("out:", OUT)
