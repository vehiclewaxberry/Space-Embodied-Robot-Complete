# -*- coding: utf-8 -*-
"""Generate the WP1 document deliverables from the FreeCAD build-run receipt.

Reads wp1_load_bridge/LOAD_BRIDGE_BUILD_RUN_V1.json (produced by the single
Owner-Override FreeCADCmd run of build_load_bridge_candidate.py) and writes:

- LOAD_BRIDGE_DATUMS_V1.yaml          (datum / station / fit candidate register)
- FITUP_AND_FRAME_RECEIPT_V1.json     (assembly numeric receipt)
- LOAD_BRIDGE_DRAWING_TABLE_V1.csv    (drawing dimension table)
- D04_LOAD_BRIDGE_INTERFACE_DRAFT.svg (interface sketch, CANDIDATE marked)
- receipt.json                        (WP1 closeout receipt with SHA-256 pins)

Plain CPython, low memory, no FreeCAD.  All values are CANDIDATE class;
unknown values stay null with explicit HOLD; nothing is zero-filled.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
M6_ROOT = HERE.parent

BUILD_RUN = HERE / "LOAD_BRIDGE_BUILD_RUN_V1.json"
DATUMS_YAML = HERE / "LOAD_BRIDGE_DATUMS_V1.yaml"
FITUP_JSON = HERE / "FITUP_AND_FRAME_RECEIPT_V1.json"
DRAWING_CSV = HERE / "LOAD_BRIDGE_DRAWING_TABLE_V1.csv"
DRAWING_SVG = HERE / "D04_LOAD_BRIDGE_INTERFACE_DRAFT.svg"
RECEIPT = HERE / "receipt.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def local_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def fmt(value: float) -> str:
    """Deterministic compact decimal formatting."""
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return text if text else "0"


def main() -> None:
    build = json.loads(BUILD_RUN.read_text(encoding="utf-8"))
    gen = local_now()

    t_rows = build["frame"]["T_S_LOAD_BRIDGE_LOCAL_rows"]
    geom = build["bridge_geometry"]
    bbox = geom["metrics_S_frame"]["bounding_box_mm"]
    hole_s = geom["hole_centres_S_at_mate_plane_mm"]
    hole_local = geom["hole_centres_local_xy_mm"]
    mass = build["material_derived_mass_candidate"]
    checks = build["checks"]
    contact = build["nominal_contact_relations"]
    bus = build["bus_reference"]
    src_register = build["source_register"]

    # ------------------------------------------------------------------ YAML
    hole_names = ["H1", "H2", "H3", "H4"]
    hole_lines = []
    for name, loc, spos in zip(hole_names, hole_local, hole_s):
        hole_lines.append(
            f"""  - id: {name}
    type: THROUGH_CLEARANCE_HOLE
    diameter_mm: 6.6
    local_centre_xy_mm: [{fmt(loc[0])}, {fmt(loc[1])}]
    S_centre_at_mate_plane_mm: [{fmt(spos[0])}, {fmt(spos[1])}, {fmt(spos[2])}]
    axis_S: [1.0, 0.0, 0.0]
    classification: CANDIDATE
    mates_to: M3R_STAGE_B_M6_CLEARANCE_HOLE (B-015/B-016, working-loop FROZEN)"""
        )

    datums_text = f"""schema: LOAD_BRIDGE_DATUMS_V1
generated_local: '{gen}'
phase: M6_CANDIDATE_AUTHORITY_CLOSURE
work_package: WP1_LOAD_BRIDGE_CAD
lifecycle_status: CANDIDATE_NOT_AUTHORITY_NOT_RELEASED
length_unit: mm
bom_item:
  item_id: DP-007
  assembly_item: spacecraft to M3R load bridge
  m4_status: HARD_HOLD_ABSENT_NO_AUTHORIZED_GEOMETRY
  m6_candidate_status: CANDIDATE_GEOMETRY_PRESENT_AUTHORITY_HOLD_PRESERVED

frame:
  name: LOAD_BRIDGE_LOCAL
  definition: COINCIDENT_WITH_M3R_LOCAL
  parent_frame: S
  T_S_child_rows:
    - [{fmt(t_rows[0][0])}, {fmt(t_rows[0][1])}, {fmt(t_rows[0][2])}, {fmt(t_rows[0][3])}]
    - [{fmt(t_rows[1][0])}, {fmt(t_rows[1][1])}, {fmt(t_rows[1][2])}, {fmt(t_rows[1][3])}]
    - [{fmt(t_rows[2][0])}, {fmt(t_rows[2][1])}, {fmt(t_rows[2][2])}, {fmt(t_rows[2][3])}]
    - [{fmt(t_rows[3][0])}, {fmt(t_rows[3][1])}, {fmt(t_rows[3][2])}, {fmt(t_rows[3][3])}]
  local_z_range_mm: [-22.75, -12.0]
  authority: >-
    DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml::frames::M3R_LOCAL plus
    M3R_TSM_PHYSICAL_STACK.yaml (clocking 25.000014 deg about +X_S, pattern
    centre YZ [0.015994151, -0.086366070]). Frame-tree recompute residual
    {build['frame']['frame_tree_recompute_max_abs_residual']:.3e} mm.
  frame_semantics_hold: >-
    M_DYNAMICS (x=185.25, nonphysical dynamics origin) and
    B601_ARM_BASE_PHYSICAL (x=208.0) remain distinct frames; this register
    does not alias them.

station_bindings:
  bus_side_mate_face:
    x_S_mm: 185.25
    local_datum: D_BRIDGE_BUS (local z = -22.75)
    semantics: bus proxy +X outer face / legacy-flange outer face / M-frame station (nonphysical)
    bridge_entity: planar face of candidate bridge
    note: >-
      Legacy flange occupies x 170.25-185.25 with ambiguous ownership; it is
      NOT merged into bridge geometry or mass. Spacecraft-side anchor pattern
      and receptacle are null (HOLD).
  m3r_side_mate_face:
    x_S_mm: 196.0
    local_datum: D_BRIDGE_M3R (local z = -12.0)
    semantics: M3R Stage B spacecraft-side bottom face
    derivation: physical installation face 208.0 minus Stage B base thickness 12.0
    bridge_entity: planar face of candidate bridge
  physical_installation_face:
    x_S_mm: 208.0
    semantics: M3R local z=0 placement station (central boss physical installation face)
    note: bridge does not reach this station; Stage B occupies x 196.0-208.0
  adapter_plate_external_face:
    x_S_mm: 198.0
    semantics: existing load-spreading plate external face; no geometry entity in M4/M6
  fastener_end_plane:
    x_S_mm: 210.405
    semantics: four HM4-75 screw end faces (B601 side, not a bridge interface)

hole_datums:
{chr(10).join(hole_lines)}

central_passage:
  diameter_mm: 40.0
  type: THROUGH
  axis_S: [1.0, 0.0, 0.0]
  classification: CANDIDATE
  rationale: keeps the Stage A/B central 40 mm channel notionally open; a void cannot create interference

outline:
  shape: ROUNDED_SQUARE
  width_mm: 160.0
  corner_radius_mm: 4.0
  clocking: PATTERN_ALIGNED_WITH_M3R_25P000014_DEG
  classification: CANDIDATE
  nominal_hole_edge_ligament_mm: 6.7
  ligament_derivation: 160/2 - 70 - 6.6/2
  ligament_limitation: NOMINAL_GEOMETRY_ONLY_NOT_A_WORST_CASE_EDGE_MARGIN

interface_relations:
  to_bus_12U:
    relation: PLANAR_ABUTMENT_NOMINAL_BY_CONSTRUCTION at x_S = 185.25
    bus_proxy_face_source: model_specs_v0.json::servicer_12U_v0 (bus max x = {fmt(bus['bus_proxy_plus_x_face_x_mm'])})
    fastener_concept: CO-BORE_THROUGH_BOLT_CANDIDATE sharing the 4x dia 6.6 holes
    spacecraft_side_anchor_pattern: null
    spacecraft_side_status: HOLD_NO_AUTHORIZED_BUS_SIDE_MATING_PATTERN
    legacy_flange: EXCLUDED_OWNERSHIP_UNRESOLVED
  to_m3r_stage_b:
    relation: PLANAR_ABUTMENT_NOMINAL_BY_CONSTRUCTION at x_S = 196.0
    pattern: 4x M6 clearance dia 6.6 at 140x140 (centres +/-70,+/-70 local)
    pattern_congruence: BY_CONSTRUCTION_SAME_LOCAL_FRAME (measured max abs deviation {geom['hole_position_max_abs_dev_mm']:.3e} mm)
    stage_b_mate_plane_observations_readonly:
      - central receiving bore dia 100 open at mate plane (local z -12.0 to -5.595)
      - 8x M5 interstage hole openings at mate plane are covered by the bridge solid; tool access and assembly sequence remain HOLD
      - clocking dowel blind hole dia 4.0 at local (55.0, 0.0), depth 5.5, covered by the bridge solid; dowel fit HOLD
    load_path_position: between bus +X face and Stage B spacecraft primary pattern candidate

fit_candidates:
  - pair: BRIDGE_HOLE_6P6_vs_M6_FASTENER_SHAFT
    hole: dia 6.6 ISO 286-2 H11 candidate (+0.090/0 mm, 6-10 mm step)
    shaft: M6 ISO 286-2 h9 candidate (0/-0.036 mm, 6-10 mm step)
    clearance_mm: {{nominal: 0.6, min: 0.6, max: 0.726}}
    reference: ISO 273 free clearance for M6 is 6.6 (consistent note only)
    classification: CANDIDATE_FIT_UNVERIFIED_AGAINST_PROCUREMENT
  - pair: FACE_PAIR_FLATNESS_D_BRIDGE_BUS_vs_D_BRIDGE_M3R
    value: null
    classification: CANDIDATE_FIT
    status: HOLD_SURFACE_SPECIFICATION_HOLD
  - pair: HOLE_PATTERN_POSITION_BRIDGE_vs_STAGE_B
    value: null
    classification: CANDIDATE_FIT
    status: HOLD_M6_PATTERN_POSITION_TOLERANCE_HOLD
  - pair: CLOCKING_DOWEL_ENGAGEMENT
    value: null
    classification: CANDIDATE_FIT
    status: HOLD_CLOCKING_DOWEL_FIT_TOLERANCE_HOLD

material_derived_mass_candidate:
  classification: MATERIAL_DERIVED
  active: false
  measured: false
  installed: false
  volume_mm3: {fmt(mass['volume_mm3'])}
  density_estimate_kg_m3: {fmt(mass['density_estimate_kg_m3'])}
  density_source: PROTOTYPE_MATERIAL_LIBRARY_V1.yaml::PMAT-AL6061-T6-SHEET-PLATE
  mass_g: {fmt(mass['mass_g'])}
  mass_kg: {fmt(mass['mass_kg'])}
  limitations:
    - CANDIDATE_DENSITY_NOT_HARDWARE_MASS
    - EXCLUDED_FROM_M3R_BUDGET_0P7619_KG (mating spacecraft structure per M3R_MASS_RULING.json)
    - NEVER_OVERRIDES_L0_URDF_MASSES
    - LEGACY_FLANGE_NOT_INCLUDED

holds:
  - LOAD_BRIDGE_PHYSICAL_FITUP_HOLD
  - MATING_FASTENER_AND_TOLERANCE_HOLD
  - M6_PATTERN_POSITION_TOLERANCE_HOLD
  - SURFACE_SPECIFICATION_HOLD
  - SPACECRAFT_SIDE_ANCHOR_PATTERN_HOLD
  - CLOCKING_DOWEL_FIT_TOLERANCE_HOLD
  - MATERIAL_APPROVAL_AND_PROCESS_HOLD
  - AUTHORIZED_LOADS_HOLD
  - STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD (candidate geometry present; structural continuity not verified, no FEA)
  - LEGACY_FLANGE_OWNERSHIP_HOLD

source_register:
"""
    for rec in src_register:
        datums_text += f"  - path: {rec['path']}\n    sha256: {rec['sha256']}\n"
    DATUMS_YAML.write_text(datums_text, encoding="utf-8")

    # ------------------------------------------------------------------ fitup
    fitup = {
        "schema": "FITUP_AND_FRAME_RECEIPT_V1",
        "generated_local": gen,
        "phase": "M6_CANDIDATE_AUTHORITY_CLOSURE",
        "work_package": "WP1_LOAD_BRIDGE_CAD",
        "lifecycle_status": "CANDIDATE_NOMINAL_ASSEMBLY_NUMERICS_NOT_A_FITUP_RESULT",
        "physical_fitup_performed": False,
        "formal_fea_performed": False,
        "bridge_span": {
            "x_interval_S_mm": [bbox[0], bbox[3]],
            "span_mm": round(bbox[3] - bbox[0], 9),
            "equals_m4_m5_exposed_minimum_gap_mm": 10.75,
            "gap_semantics": "the 10.75 mm minimum gap is evidence of the missing load bridge, not an assembly pass conclusion",
            "bridge_thickness_mm": 10.75,
        },
        "nominal_contact_relations": {
            "bridge_vs_m3r_assembly": {
                **contact["bridge_vs_m3r"],
                "mate_plane_x_S_mm": 196.0,
                "note": "nominal face contact at the Stage B spacecraft-side bottom face; distance 0.0 and common volume 0.0 by construction and B-rep narrow phase",
            },
            "bridge_vs_bus_proxy_face": {
                **contact["bridge_vs_bus_proxy_face"],
                "mate_plane_x_S_mm": 185.25,
                "legacy_flange_x_extent_mm": bus["legacy_flange_x_extent_mm"],
                "legacy_flange_merged_into_bridge": False,
            },
            "bridge_vs_legacy_flange_region": {
                "classification": "NO_ENTRY_BY_CONSTRUCTION",
                "bridge_min_x_mm": bbox[0],
                "flange_max_x_mm": bus["legacy_flange_x_extent_mm"][1],
            },
        },
        "frame_consistency": {
            "T_S_LOAD_BRIDGE_LOCAL_rows": t_rows,
            "definition": "COINCIDENT_WITH_M3R_LOCAL",
            "frame_tree_recompute_max_abs_residual_mm": build["frame"][
                "frame_tree_recompute_max_abs_residual"
            ],
            "hole_axes_S": geom["hole_axes_S"],
            "hole_centres_S_at_mate_plane_mm": hole_s,
            "measured_m6_hole_faces_S": geom["measured_m6_hole_faces_S"],
            "hole_position_max_abs_dev_mm": geom["hole_position_max_abs_dev_mm"],
            "m3r_reference": {
                "min_x_S_mm": build["m3r_readonly_reference"]["metrics_S_frame"]["bounding_box_mm"][0],
                "volume_local_mm3": build["m3r_readonly_reference"]["metrics_local"]["volume_mm3"],
                "volume_matches_m3_receipt": checks["m3r_volume_matches_m3_receipt"],
            },
            "bus_proxy_plus_x_face_x_mm": bus["bus_proxy_plus_x_face_x_mm"],
        },
        "volume_and_mass_candidate": {
            "volume_mm3": geom["metrics_S_frame"]["volume_mm3"],
            "analytic_volume_mm3": geom["analytic_volume_mm3"],
            "volume_relative_error_vs_analytic": geom["volume_relative_error_vs_analytic"],
            "material_derived_mass_g": mass["mass_g"],
            "classification": "MATERIAL_DERIVED_CANDIDATE_INACTIVE_NOT_MEASURED",
        },
        "checks": checks,
        "fcstd_cold_reopen": build["fcstd_cold_reopen"],
        "step_cold_reopen": build["step_cold_reopen"],
        "memory_gate": build["memory_gate"],
        "owner_override": build["owner_override"],
        "source_register": src_register,
        "verdict": build["verdict"],
    }
    FITUP_JSON.write_text(
        json.dumps(fitup, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # ------------------------------------------------------------------ CSV
    rows = [
        ["feature_id", "description", "nominal_value", "unit", "tolerance_or_fit_class", "classification", "source"],
        ["LB-001", "outline square width", "160.0", "mm", "null (HOLD_ALL_MANUFACTURING_TOLERANCES)", "CANDIDATE", "matches Stage B B-001 footprint"],
        ["LB-002", "outline corner radius", "4.0", "mm", "null (HOLD)", "CANDIDATE", "matches Stage B B-002"],
        ["LB-003", "bridge thickness (x span)", "10.75", "mm", "null (HOLD)", "CANDIDATE", "196.0 - 185.25 station derivation; spans M4/M5 exposed minimum gap"],
        ["LB-004", "bus-side mate face station x_S", "185.25", "mm", "station frozen", "FROZEN_STATION", "M3R_TSM_PHYSICAL_STACK.yaml accepted_urdf_base_frame"],
        ["LB-005", "M3R-side mate face station x_S", "196.0", "mm", "station derived", "DERIVED_STATION", "208.0 installation face minus Stage B thickness 12.0"],
        ["LB-006", "M6 clearance hole diameter (4x)", "6.6", "mm", "ISO 286-2 H11 CANDIDATE_FIT (+0.090/0)", "CANDIDATE", "matches Stage B B-015"],
        ["LB-007", "hole pattern square spacing", "140.0", "mm", "position tolerance null (HOLD_M6_PATTERN_POSITION_TOLERANCE)", "CANDIDATE", "matches Stage B B-016 centres +/-70,+/-70"],
        ["LB-008", "nominal hole-edge ligament", "6.7", "mm", "nominal only, not worst case", "DERIVED", "160/2 - 70 - 6.6/2"],
        ["LB-009", "central through passage diameter", "40.0", "mm", "null (HOLD)", "CANDIDATE", "aligned with Stage A/B central passage"],
        ["LB-010", "pattern clocking about +X_S", "25.000014", "deg", "as-built datum", "FROZEN_AS_BUILT", "M3R_TSM_PHYSICAL_STACK.yaml pattern_clocking_about_x_deg"],
        ["LB-011", "pattern centre YZ offset", "0.015994151;-0.086366070", "mm", "as-built datum", "FROZEN_AS_BUILT", "M3R_TSM_PHYSICAL_STACK.yaml pattern_center_yz_mm"],
        ["LB-012", "bridge volume", fmt(mass["volume_mm3"]), "mm3", "B-rep measured", "DERIVED", "LOAD_BRIDGE_BUILD_RUN_V1.json"],
        ["LB-013", "material-derived mass candidate", fmt(mass["mass_g"]), "g", "MATERIAL_DERIVED only", "CANDIDATE_INACTIVE", "volume x 2700 kg/m3 PMAT-AL6061-T6-SHEET-PLATE"],
        ["LB-014", "M6 fastener shaft candidate", "6.0", "mm", "ISO 286-2 h9 CANDIDATE_FIT (0/-0.036)", "CANDIDATE_FIT", "reference only, fastener selection HOLD"],
        ["LB-015", "hole-shaft clearance", "0.600..0.726", "mm", "CANDIDATE_FIT", "CANDIDATE_FIT", "6.6 H11 vs 6.0 h9 arithmetic, unverified"],
        ["LB-016", "bridge YZ bbox half width (clocked)", fmt((bbox[4] - bbox[1]) / 2.0), "mm", "B-rep measured", "DERIVED", "support of clocked rounded square"],
    ]
    DRAWING_CSV.write_text(
        "\n".join(",".join(str(field) for field in row) for row in rows) + "\n",
        encoding="utf-8",
    )

    # ------------------------------------------------------------------ SVG
    # Axial schematic map: x 150..230 mm -> px 110..1290 (14.75 px/mm).
    def px(x_mm: float) -> float:
        return 110.0 + (x_mm - 150.0) * 14.75

    x_bus, x_m3r = 185.25, 196.0
    # Plan view: clocked rounded square, scale 1.4 px/mm, centred at (310, 715).
    import math

    ang = math.radians(25.000014)
    ca, sa = math.cos(ang), math.sin(ang)
    scale = 1.4
    cx0, cy0 = 310.0, 715.0

    def plan_pt(y_mm: float, z_mm: float) -> tuple[float, float]:
        # drawing plane: +y to the right, +z up (SVG y down)
        return (cx0 + y_mm * scale, cy0 - z_mm * scale)

    def rot(y: float, z: float) -> tuple[float, float]:
        # local (x_l, y_l) -> S (y, z): y_S = s*x_l + c*y_l ; z_S = -c*x_l + s*y_l
        return (sa * y + ca * z, -ca * y + sa * z)

    half, r = 80.0, 4.0
    a = half - r
    outline_pts = []
    # sample the rounded square in local coords, then rotate into S
    corners = [(a, a, 0.0), (-a, a, 90.0), (-a, -a, 180.0), (a, -a, 270.0)]
    # straight + arc sampling, CCW starting at right side bottom
    outline_pts.append((half, -a))
    outline_pts.append((half, a))
    for ccx, ccy, start in corners:
        for k in range(1, 6):
            t = math.radians(start + 18.0 * k)
            outline_pts.append((ccx + r * math.cos(t), ccy + r * math.sin(t)))
        if start == 0.0:
            outline_pts.append((a, half))
            outline_pts.append((-a, half))
        elif start == 90.0:
            outline_pts.append((-half, a))
            outline_pts.append((-half, -a))
        elif start == 180.0:
            outline_pts.append((-a, -half))
            outline_pts.append((a, -half))
        else:
            outline_pts.append((a, -half))
            outline_pts.append((half, -a))
    poly = []
    for lx, ly in outline_pts:
        yy, zz = rot(lx, ly)
        # pattern centre offset
        yy += 0.015994151
        zz += -0.086366070
        poly.append("{:.2f},{:.2f}".format(*plan_pt(yy, zz)))
    polygon = " ".join(poly)

    hole_marks = []
    for spos in hole_s:
        hx, hy = plan_pt(spos[1], spos[2])
        hole_marks.append(f'<circle cx="{hx:.2f}" cy="{hy:.2f}" r="{3.3 * scale:.2f}" fill="white" stroke="#b3541e" stroke-width="2"/>')
    cy, cz = plan_pt(0.015994151, -0.086366070)
    central = f'<circle cx="{cy:.2f}" cy="{cz:.2f}" r="{20.0 * scale:.2f}" fill="white" stroke="#b3541e" stroke-width="2" stroke-dasharray="6 4"/>'

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#22303c"/>
    </marker>
    <style>
      .title{{font:700 28px Arial;fill:#102a43}}.h{{font:700 18px Arial;fill:#102a43}}
      .t{{font:15px Arial;fill:#243b53}}.small{{font:13px Arial;fill:#486581}}
      .dim{{stroke:#22303c;stroke-width:1.5;marker-end:url(#arrow);marker-start:url(#arrow)}}
      .datum{{stroke:#d64545;stroke-width:2;stroke-dasharray:7 5}}
      .bus{{fill:#d9eaf7;stroke:#1f5f8b;stroke-width:2}}.m3r{{fill:#d9f2e6;stroke:#24734b;stroke-width:2}}
      .cand{{fill:#ffe1c2;stroke:#b3541e;stroke-width:2.5}}
      .flange{{fill:#ececec;stroke:#6b7280;stroke-width:2;stroke-dasharray:5 4}}
    </style>
  </defs>

  <rect x="8" y="8" width="1384" height="884" fill="white" stroke="#102a43" stroke-width="2"/>
  <text x="40" y="55" class="title">D04 — LOAD BRIDGE INTERFACE DRAFT</text>
  <text x="40" y="82" class="h" fill="#d64545">CANDIDATE GEOMETRY · NOT TO SCALE · NOT FOR MANUFACTURE · NOT AN AUTHORITY RELEASE</text>

  <text x="50" y="122" class="h">Axial station schematic (+X<tspan baseline-shift="sub">S</tspan> to the right)</text>
  <line x1="90" y1="290" x2="1300" y2="290" stroke="#22303c" stroke-width="2" marker-end="url(#arrow)"/>
  <text x="1308" y="297" class="t">+X<tspan baseline-shift="sub">S</tspan></text>

  <!-- bus proxy up to x=185.25 -->
  <rect x="{px(150.0):.1f}" y="215" width="{px(170.25) - px(150.0):.1f}" height="150" class="bus"/>
  <text x="{px(152.0):.1f}" y="250" class="h">12U BUS PROXY</text>
  <!-- legacy flange 170.25..185.25, ownership HOLD -->
  <rect x="{px(170.25):.1f}" y="225" width="{px(185.25) - px(170.25):.1f}" height="130" class="flange"/>
  <text x="{px(169.5):.1f}" y="215" class="small">legacy flange (HOLD, excluded)</text>
  <!-- load bridge candidate 185.25..196.0 -->
  <rect x="{px(185.25):.1f}" y="205" width="{px(196.0) - px(185.25):.1f}" height="170" class="cand"/>
  <text x="{px(183.2):.1f}" y="195" class="small">LOAD BRIDGE CANDIDATE</text>
  <!-- M3R Stage B 196..208 + Stage A boss 208..210.405 -->
  <rect x="{px(196.0):.1f}" y="220" width="{px(208.0) - px(196.0):.1f}" height="140" class="m3r"/>
  <rect x="{px(208.0):.1f}" y="245" width="{px(210.405) - px(208.0):.1f}" height="90" class="m3r"/>
  <text x="{px(197.0):.1f}" y="212" class="small">M3R Stage B (working B-rep)</text>
  <text x="{px(205.5):.1f}" y="240" class="small">Stage A</text>

  <line x1="{px(185.25):.1f}" y1="150" x2="{px(185.25):.1f}" y2="430" class="datum"/>
  <text x="{px(183.4):.1f}" y="140" class="small">185.25 bus face / M dynamics</text>
  <line x1="{px(196.0):.1f}" y1="150" x2="{px(196.0):.1f}" y2="430" class="datum"/>
  <text x="{px(194.6):.1f}" y="128" class="small">196.0 Stage B bottom (208.0 - 12.0)</text>
  <line x1="{px(198.0):.1f}" y1="150" x2="{px(198.0):.1f}" y2="430" class="datum"/>
  <text x="{px(198.2):.1f}" y="112" class="small">198.0 adapter face (no geometry)</text>
  <line x1="{px(208.0):.1f}" y1="150" x2="{px(208.0):.1f}" y2="430" class="datum"/>
  <text x="{px(206.8):.1f}" y="96" class="small">208.0 physical install face</text>
  <line x1="{px(210.405):.1f}" y1="150" x2="{px(210.405):.1f}" y2="430" class="datum"/>
  <text x="{px(209.2):.1f}" y="80" class="small">210.405 screw ends</text>

  <line x1="{px(185.25):.1f}" y1="455" x2="{px(196.0):.1f}" y2="455" class="dim"/>
  <text x="{px(186.6):.1f}" y="477" class="small">10.75 bridge span (= exposed minimum gap)</text>
  <line x1="{px(196.0):.1f}" y1="495" x2="{px(208.0):.1f}" y2="495" class="dim"/>
  <text x="{px(198.0):.1f}" y="517" class="small">12.0 Stage B</text>
  <line x1="{px(170.25):.1f}" y1="535" x2="{px(208.0):.1f}" y2="535" class="dim"/>
  <text x="{px(181.0):.1f}" y="557" class="small">37.75 legacy flange face to install face (context only)</text>

  <text x="490" y="592" class="h">Plan view at mate plane (looking -X<tspan baseline-shift="sub">S</tspan>)</text>
  <polygon points="{polygon}" fill="#ffe1c2" stroke="#b3541e" stroke-width="2.5"/>
  {chr(10).join('  ' + m for m in hole_marks)}
  {central}
  <text x="490" y="624" class="t">160x160 rounded square (R4); clocking 25.000014° about +X<tspan baseline-shift="sub">S</tspan></text>
  <text x="490" y="649" class="t">4x dia 6.6 through on 140x140 (±70, ±70 local)</text>
  <text x="490" y="674" class="t">nominal hole-edge ligament 6.7 (160/2 - 70 - 6.6/2)</text>
  <text x="490" y="699" class="t">central through passage dia 40 (dashed)</text>
  <text x="490" y="724" class="t">pattern centre YZ (0.015994151, -0.086366070)</text>

  <rect x="900" y="600" width="470" height="240" fill="#fff7ed" stroke="#d64545" stroke-width="2"/>
  <text x="918" y="630" class="h">CANDIDATE FITS / RELEASE BOUNDARY</text>
  <text x="918" y="658" class="small">• hole dia 6.6 H11 vs M6 h9: clearance 0.600..0.726 — CANDIDATE_FIT</text>
  <text x="918" y="682" class="small">• pattern position / flatness / dowel fits: null + HOLD</text>
  <text x="918" y="706" class="small">• mass {mass['mass_g']:.3f} g MATERIAL_DERIVED (2700 kg/m³ candidate)</text>
  <text x="918" y="730" class="small">• no manufacturing / procurement / flight / qualification claim</text>
  <text x="918" y="754" class="small">• no FEA, no MoS, no structural continuity claim</text>
  <text x="918" y="778" class="small">• legacy flange (x 170.25–185.25) excluded, ownership HOLD</text>
  <text x="918" y="802" class="small">• physical fitup not performed; DP-007 authority HOLD preserved</text>

  <text x="40" y="880" class="small">Units: mm. Datums and fits: LOAD_BRIDGE_DATUMS_V1.yaml. Numeric receipt: FITUP_AND_FRAME_RECEIPT_V1.json. Geometry authority frames: DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml (read-only).</text>
</svg>
"""
    DRAWING_SVG.write_text(svg, encoding="utf-8")

    # ------------------------------------------------------------------ receipt
    deliverables = [
        HERE / "build_load_bridge_candidate.py",
        HERE / "make_wp1_documents.py",
        BUILD_RUN,
        HERE / "LOAD_BRIDGE_CANDIDATE_V1.FCStd",
        HERE / "LOAD_BRIDGE_CANDIDATE_V1.step",
        DATUMS_YAML,
        FITUP_JSON,
        DRAWING_CSV,
        DRAWING_SVG,
    ]
    receipt = {
        "schema": "M6_WP1_LOAD_BRIDGE_RECEIPT_V1",
        "generated_local": gen,
        "phase": "M6_CANDIDATE_AUTHORITY_CLOSURE",
        "work_package": "WP1_LOAD_BRIDGE_CAD",
        "status": "COMPLETE_CANDIDATE_LAYER_CLOSED_AUTHORITY_HOLDS_PRESERVED",
        "bom_item": "DP-007",
        "freecad_used": True,
        "freecad_execution": "SINGLE_FREECADCMD_PROCESS_OWNER_OVERRIDE_WP1_EXCLUSIVE",
        "freecad_version": build["builder"]["freecad_version"],
        "formal_fea_authorized": False,
        "formal_fea_run_count": 0,
        "memory_gate": build["memory_gate"],
        "owner_override": build["owner_override"],
        "build_verdict": build["verdict"],
        "key_results": {
            "bridge_x_span_mm": [bbox[0], bbox[3]],
            "bridge_thickness_mm": 10.75,
            "outline_mm": "160x160 rounded square R4, clocked 25.000014 deg about +X_S",
            "holes": "4x dia 6.6 through at local (+/-70,+/-70); central dia 40 through",
            "nominal_hole_edge_ligament_mm": 6.7,
            "volume_mm3": geom["metrics_S_frame"]["volume_mm3"],
            "material_derived_mass_g": mass["mass_g"],
            "bridge_m3r_min_distance_mm": contact["bridge_vs_m3r"]["minimum_distance_mm"],
            "bridge_m3r_common_volume_mm3": contact["bridge_vs_m3r"]["common_volume_mm3"],
            "hole_position_max_abs_dev_mm": geom["hole_position_max_abs_dev_mm"],
            "checks_passed": f"{sum(1 for v in checks.values() if v)}/{len(checks)}",
        },
        "deliverables": [
            {
                "path": path.relative_to(M6_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in deliverables
        ],
        "holds_preserved": [
            "LOAD_BRIDGE_PHYSICAL_FITUP_HOLD (no physical fitup performed)",
            "MATING_FASTENER_AND_TOLERANCE_HOLD",
            "M6_PATTERN_POSITION_TOLERANCE_HOLD",
            "SURFACE_SPECIFICATION_HOLD",
            "SPACECRAFT_SIDE_ANCHOR_PATTERN_HOLD (bus-side mating pattern null)",
            "CLOCKING_DOWEL_FIT_TOLERANCE_HOLD",
            "MATERIAL_APPROVAL_AND_PROCESS_HOLD",
            "AUTHORIZED_LOADS_HOLD (no load cases authorized; no FEA)",
            "STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD (candidate geometry only)",
            "LEGACY_FLANGE_OWNERSHIP_HOLD (x 170.25-185.25 excluded from bridge geometry and mass)",
            "M_DYNAMICS vs B601_ARM_BASE_PHYSICAL alias reconciliation HOLD (frames kept distinct)",
            "M5 structural entry subgates remain HOLD; CDR Phase-1 Q0/Q1/Q2 remain HOLD",
        ],
        "rules_honored": [
            "no baseline file modified; writes confined to wp1_load_bridge/",
            "no zero fill; unknown values kept null with explicit HOLD",
            "candidate != authority; diagnostic != released; nothing promoted",
            "no FEA; formal_fea_run_count remains 0",
            "no RL training; no manufacturing/procurement/launch/flight/qualification claims",
            "L0 URDF mass 4.695555949 kg referenced, never overridden",
            "legacy flange never merged into bridge geometry or mass",
            "single FreeCAD process only (WP1-exclusive Owner Override); memory gate FAIL recorded",
            "mass is MATERIAL_DERIVED candidate only (density x volume, sourced candidate density)",
        ],
        "source_register": src_register,
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "deliverables": len(deliverables)}, ensure_ascii=False))


main()
