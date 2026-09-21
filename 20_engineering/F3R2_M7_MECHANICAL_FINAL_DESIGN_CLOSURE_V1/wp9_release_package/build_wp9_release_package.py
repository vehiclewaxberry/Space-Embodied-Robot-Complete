#!/usr/bin/env python3
"""WP9_RELEASE_PACKAGE builder - M7 engineering release package (document level).

Fail-closed rules honored:
- Baseline files are read-only; this script writes ONLY into wp9_release_package/.
- Sibling M7 WP outputs are referenced by M7_EXECUTION_PLAN_V1 contract paths only;
  hashes are marked PENDING_SIBLING_HASH (integration backfills them).
- No zero-fill: unknowns stay UNSPECIFIED_HOLD / null.
- L0 URDF masses never overridden; candidate rows never promoted to released rows.
- Pure text/python; no FreeCAD, no Abaqus (memory gate 6 GiB failed).
"""
import csv
import hashlib
import io
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
M7_DIR = os.path.dirname(HERE)
PROJ = os.path.abspath(os.path.join(M7_DIR, "..", ".."))

M7 = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
WP9 = M7 + "/wp9_release_package"
M4 = "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1"
M5 = "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1"
M6 = "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1"
CDR = "20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821"
V5R = "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
M3DD = "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1"
TERM = "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
SIM13 = "30_simulation/sim_13_physics_gated_embodied_grasping"

GEN_LOCAL = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")

# M7 sibling contract paths (M7_EXECUTION_PLAN_V1.md; hashes pending integration)
C_WP1_STRUCT = M7 + "/wp1_structure_cad/PRODUCT_STRUCTURE_V1.yaml"
C_WP1_ASSY_FCSTD = M7 + "/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.FCStd"
C_WP1_ASSY_STEP = M7 + "/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.step"
C_WP1_HARNESS = M7 + "/wp1_structure_cad/HARNESS_ROUTING_V1.yaml"
C_WP1_KEEPOUT = M7 + "/wp1_structure_cad/KEEP_OUT_REGISTER_V1.yaml"
C_WP1_SUPPORT = M7 + "/wp1_structure_cad/SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml"
C_WP2_MASS = M7 + "/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml"
C_WP2_POLICY = M7 + "/wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml"
C_WP3_CHAINS = M7 + "/wp3_tolerance_alloc/TOLERANCE_CHAIN_REGISTER_V1.yaml"
C_WP3_RESULTS = M7 + "/wp3_tolerance_alloc/TOLERANCE_ALLOCATION_RESULTS_V1.yaml"
C_WP3_SCHEME = M7 + "/wp3_tolerance_alloc/DRAWING_TOLERANCE_SCHEME_V1.csv"
C_WP4_M3R = M7 + "/wp4_fastener_design/M3R_FASTENER_DESIGN_V1.yaml"
C_WP4_SCHED = M7 + "/wp4_fastener_design/FASTENER_SCHEDULE_V1.csv"
C_WP4_TORQUE = M7 + "/wp4_fastener_design/TORQUE_PRELOAD_SCHEDULE_V1.csv"
C_WP4_CHECKS = M7 + "/wp4_fastener_design/FASTENER_ANALYTIC_CHECKS_V1.csv"
C_WP5_HDRM = M7 + "/wp5_mechanisms/HDRM_ENGINEERING_PACK_V1.yaml"
C_WP5_HINGE = M7 + "/wp5_mechanisms/SOLAR_HINGE_DEPLOYMENT_PACK_V1.yaml"
C_WP5_GRIPPER = M7 + "/wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V1.yaml"
C_WP5_XREF = M7 + "/wp5_mechanisms/MECHANISM_VERIFICATION_CROSSREF_V1.csv"
C_WP6_MAT = M7 + "/wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1.yaml"
C_WP6_PROC = M7 + "/wp6_material_selection/PROCESS_AND_FINISH_REGISTER_V1.csv"
C_WP7_EVID = M7 + "/wp7_fea_operational/FEA1_EVIDENCE_V1.json"
C_WP7_RESULTS = M7 + "/wp7_fea_operational/FEA1_RESULTS_V1.csv"
C_WP7_DECKS = M7 + "/wp7_fea_operational/FEA2_FEA8_DECK_REGISTER_V1.yaml"
C_WP8_SENS = M7 + "/wp8_thermal/THERMO_ELASTIC_SENSITIVITY_V1.yaml"
C_WP8_ENV = M7 + "/wp8_thermal/THERMO_ELASTIC_ENVELOPE_V1.csv"
C_WP10_IF = M7 + "/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V4.yaml"
PEND = "PENDING_SIBLING_HASH"

# Existing baseline inputs (read-only) hashed into source_register
INPUTS = [
    M7 + "/README.md",
    M7 + "/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml",
    M7 + "/00_authority/M7_EXECUTION_PLAN_V1.md",
    CDR + "/01_wp0_requirements/MECHANICAL_SYSTEM_REQUIREMENTS_SPEC_V1.yaml",
    CDR + "/01_wp0_requirements/MECHANICAL_VERIFICATION_CONTROL_DOCUMENT_V1.csv",
    CDR + "/01_wp0_requirements/MECHANICAL_CRITICAL_ITEMS_REGISTER_V1.csv",
    CDR + "/01_wp0_requirements/HOLD_TO_REQUIREMENT_TRACEABILITY_V1.csv",
    M4 + "/09_drawings/D01_DIGITAL_PROTOTYPE_INTERFACE_LAYOUT_DRAFT.svg",
    M4 + "/09_drawings/D02_INTERFACE_STATION_SCHEDULE_V1.csv",
    M4 + "/09_drawings/D03_COMPONENT_DRAWING_CROSS_REFERENCE_V1.csv",
    M4 + "/09_drawings/DIGITAL_PROTOTYPE_DRAWING_INDEX_V1.csv",
    M4 + "/10_BOM/DIGITAL_PROTOTYPE_BOM_V1.csv",
    M4 + "/10_BOM/BOM_SCOPE_AND_NONCLAIMS.md",
    M6 + "/wp6_drawings_bom/DIGITAL_PROTOTYPE_BOM_V2_CANDIDATE.csv",
    M6 + "/wp6_drawings_bom/INTERFACE_STATION_SCHEDULE_V2.csv",
    M6 + "/wp6_drawings_bom/DIGITAL_PROTOTYPE_DRAWING_INDEX_V2.csv",
    M6 + "/wp6_drawings_bom/BOM_SCOPE_AND_NONCLAIMS_V2.md",
    M6 + "/wp1_load_bridge/D04_LOAD_BRIDGE_INTERFACE_DRAFT.svg",
    M6 + "/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml",
    M6 + "/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml",
    M6 + "/wp3_tolerance/HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1.yaml",
    V5R + "/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json",
    M3DD + "/06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml",
    M3DD + "/06_parameterized_parts/m3r/M3R_STAGE_B_PARAMETER_TABLE.yaml",
    M3DD + "/10_bom/M3R_BOM_V2.csv",
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
]
L0_URDF_EXPECTED_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_text(name, content):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return path


def write_csv(name, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return write_text(name, buf.getvalue())


SVG_DEFS = """  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#22303c"/>
    </marker>
    <style>
      .title{font:700 28px Arial;fill:#102a43}.h{font:700 18px Arial;fill:#102a43}
      .t{font:15px Arial;fill:#243b53}.small{font:13px Arial;fill:#486581}
      .dim{stroke:#22303c;stroke-width:1.5;marker-end:url(#arrow);marker-start:url(#arrow)}
      .datum{stroke:#d64545;stroke-width:2;stroke-dasharray:7 5}.hold{fill:#fff4e6;stroke:#d97706;stroke-width:2;stroke-dasharray:8 5}
      .bus{fill:#d9eaf7;stroke:#1f5f8b;stroke-width:2}.m3r{fill:#d9f2e6;stroke:#24734b;stroke-width:2}
      .witness{stroke:#744fc6;stroke-width:5;fill:none}.panel{fill:#e7e3fa;stroke:#5b44a8;stroke-width:2}
      .cand{fill:#ffe1c2;stroke:#b3541e;stroke-width:2.5}
      .flange{fill:#ececec;stroke:#6b7280;stroke-width:2;stroke-dasharray:5 4}
      .hidden{stroke:#486581;stroke-width:1.5;stroke-dasharray:6 4;fill:none}
      .hole{fill:white;stroke:#24734b;stroke-width:2}
      .holeB{fill:white;stroke:#1f5f8b;stroke-width:2}
    </style>
  </defs>
"""

BANNER = "DESIGN RELEASE CANDIDATE \u00b7 NOT TO SCALE \u00b7 NOT FOR MANUFACTURE \u00b7 NO FLIGHT OR QUALIFICATION CLAIM"

# M3R Stage A as-built M4-class axis centres (M3R_STAGE_A_PARAMETER_TABLE.yaml A-011, FROZEN),
# mm in M3R_LOCAL; svg plan view: scale 2.0 px/mm, centre (420,500), y up -> svg y down.
M4_CENTRES = [(15.494, 42.4393), (-42.5096, 15.3917), (-15.4621, -42.612), (42.5416, -15.5644)]
M5_ANGLES = [22.5 + 45.0 * k for k in range(8)]


def mm2px(x, y, cx=420.0, cy=500.0, s=2.0):
    return (cx + s * x, cy - s * y)


def svg_header(title, banner):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">\n'
        + SVG_DEFS
        + '  <rect x="8" y="8" width="1384" height="884" fill="white" stroke="#102a43" stroke-width="2"/>\n'
        + f'  <text x="40" y="55" class="title">{title}</text>\n'
        + f'  <text x="40" y="82" class="h" fill="#d64545">{banner}</text>\n'
    )


def build_d05():
    s = svg_header("D05 \u2014 M3R STAGE A INTERFACE RING (Rev-B)", BANNER)
    s += '  <text x="60" y="118" class="h">Plan view in M3R_LOCAL (looking -Z; +Z toward B601) \u2014 2.0 px/mm</text>\n'
    # outer body r150, hidden features, central passage
    s += '  <circle cx="420" cy="500" r="150" class="m3r"/>\n'
    s += '  <circle cx="420" cy="500" r="100.6" class="hidden"/>\n'
    s += '  <circle cx="420" cy="500" r="99.6" class="hidden"/>\n'
    s += '  <circle cx="420" cy="500" r="40" class="hidden"/>\n'
    s += '  <text x="548" y="428" class="small">OD 150.0 (A-001)</text>\n'
    s += '  <text x="500" y="392" class="small">skirt ID 100.6 (A-006)</text>\n'
    s += '  <text x="376" y="466" class="small">passage 40.0 (A-007)</text>\n'
    s += '  <text x="180" y="646" class="small">spigot dia 99.6 (A-005, hidden)</text>\n'
    # 8x M5 interstage clearance holes r62.5 start 22.5 deg
    import math
    for a in M5_ANGLES:
        x = 62.5 * math.cos(math.radians(a))
        y = 62.5 * math.sin(math.radians(a))
        px, py = mm2px(x, y)
        s += f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="5.5" class="hole"/>\n'
    s += '  <text x="522" y="350" class="small">8x dia 5.5 M5 interstage @ R62.5, start 22.5\u00b0 (A-015..018)</text>\n'
    # 4x M4-class pattern: as-built centres, clearance 4.6 + cbore 7.5 dashed
    pts = []
    for x, y in M4_CENTRES:
        px, py = mm2px(x, y)
        pts.append((px, py))
        s += f'  <circle cx="{px:.2f}" cy="{py:.2f}" r="7.5" class="hidden"/>\n'
        s += f'  <circle cx="{px:.2f}" cy="{py:.2f}" r="4.6" class="holeB"/>\n'
    poly = " ".join(f"{px:.2f},{py:.2f}" for px, py in [pts[0], pts[1], pts[2], pts[3], pts[0]])
    s += f'  <polygon points="{poly}" fill="none" stroke="#1f5f8b" stroke-width="1.5" stroke-dasharray="6 4"/>\n'
    s += '  <text x="470" y="250" class="small">4x M4-class (HM4-75) dia 4.6 thru + dia 7.5 cbore x 4.5 deep</text>\n'
    s += '  <text x="470" y="272" class="small">as-built centres (A-011); nominal 64 x 64 square clocked 25.000014\u00b0</text>\n'
    s += '  <text x="470" y="294" class="small">best-fit PCD 90.509642 mm; pattern centre YZ (0.015994151, -0.086366070)</text>\n'
    # dowel clearance candidate at (55,0)
    px, py = mm2px(55.0, 0.0)
    s += f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="4.1" fill="none" stroke="#b3541e" stroke-width="2" stroke-dasharray="4 3"/>\n'
    s += '  <text x="540" y="510" class="small">dowel clearance dia 4.1 @ (55.0, 0.0) \u2014 CANDIDATE (A-019/020)</text>\n'
    # section view
    s += '  <text x="850" y="118" class="h">Axial section schematic (8 px/mm axial)</text>\n'
    s += '  <rect x="880" y="180" width="300" height="44.8" class="m3r"/>\n'
    s += '  <rect x="880" y="180" width="300" height="19.2" fill="#b8e4cf" stroke="#24734b" stroke-width="2"/>\n'
    s += '  <text x="900" y="170" class="small">proud flange 2.405 (A-002) + recess 5.595 (A-003) = 8.0 total (A-004)</text>\n'
    s += '  <line x1="880" y1="140" x2="880" y2="260" class="datum"/>\n'
    s += '  <text x="700" y="135" class="small">208.0 physical install face (M3R_LOCAL z=0)</text>\n'
    s += '  <line x1="1180" y1="140" x2="1180" y2="260" class="datum"/>\n'
    s += '  <text x="1060" y="128" class="small">210.405 screw-end plane</text>\n'
    s += '  <line x1="880" y1="290" x2="1180" y2="290" class="dim"/>\n'
    s += '  <text x="990" y="312" class="small">2.405</text>\n'
    # facts panel
    s += '  <rect x="850" y="360" width="520" height="250" fill="#f0f7ff" stroke="#1f5f8b" stroke-width="2"/>\n'
    s += '  <text x="868" y="390" class="h">DESIGN DATA (sources: M3R_STAGE_A_PARAMETER_TABLE.yaml)</text>\n'
    s += '  <text x="868" y="418" class="small">\u2022 volume 127784.800333 mm3 (A-022, DERIVED, independent reopen)</text>\n'
    s += '  <text x="868" y="442" class="small">\u2022 material-derived mass 345.018961 g \u2014 INACTIVE, not budget, not measured (A-023)</text>\n'
    s += '  <text x="868" y="466" class="small">\u2022 M3R assembly mass authority 0.7619 kg DESIGN_BUDGET conf B (ODR-05);</text>\n'
    s += '  <text x="880" y="488" class="small">stage split PENDING_SIBLING_HASH wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml</text>\n'
    s += '  <text x="868" y="512" class="small">\u2022 material AL6061-T6 CANDIDATE \u2192 binding PENDING_SIBLING_HASH wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1.yaml</text>\n'
    s += '  <text x="868" y="536" class="small">\u2022 tolerances \u2192 binding PENDING_SIBLING_HASH wp3_tolerance_alloc/DRAWING_TOLERANCE_SCHEME_V1.csv</text>\n'
    s += '  <text x="868" y="560" class="small">\u2022 fasteners/preload \u2192 binding PENDING_SIBLING_HASH wp4_fastener_design/M3R_FASTENER_DESIGN_V1.yaml</text>\n'
    s += '  <text x="868" y="584" class="small">\u2022 M6 WC stackup evidence: wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml</text>\n'
    # boundary box
    s += '  <rect x="850" y="640" width="520" height="200" fill="#fff7ed" stroke="#d64545" stroke-width="2"/>\n'
    s += '  <text x="868" y="670" class="h">RELEASE BOUNDARY</text>\n'
    s += '  <text x="868" y="698" class="small">\u2022 ALL_MANUFACTURING_TOLERANCES_HOLD \u2192 WP3 contract (not on this sheet)</text>\n'
    s += '  <text x="868" y="722" class="small">\u2022 physical fitup HOLD; no FEA/MoS claim on this sheet</text>\n'
    s += '  <text x="868" y="746" class="small">\u2022 no procurement, manufacturing, flight, or qualification claim</text>\n'
    s += '  <text x="868" y="770" class="small">\u2022 candidate \u2260 authority; design \u2260 flight-qualified</text>\n'
    s += '  <text x="868" y="794" class="small">\u2022 L0 URDF mass never overridden (MSR-STR-001)</text>\n'
    s += '  <text x="40" y="880" class="small">Units: mm. Frame authority: ODR-01 (T_SM=[185.25,0,0] mm + Ry(90\u00b0)); feature stations are a geometric stack only. Generated: ' + GEN_LOCAL + '</text>\n'
    s += '</svg>\n'
    return s


def build_d06():
    s = svg_header("D06 \u2014 M3R STAGE B LOAD DIFFUSION ADAPTER (Rev-B2)", BANNER)
    s += '  <text x="60" y="118" class="h">Plan view in M3R_LOCAL (looking -Z toward load bridge) \u2014 2.0 px/mm</text>\n'
    s += '  <rect x="260" y="340" width="320" height="320" rx="8" class="m3r"/>\n'
    s += '  <rect x="250" y="330" width="340" height="340" fill="none" stroke="#486581" stroke-width="1.5" stroke-dasharray="6 4"/>\n'
    s += '  <text x="596" y="336" class="small">max envelope 170 x 170 (B-005)</text>\n'
    s += '  <text x="596" y="500" class="small">160 x 160 R4 base (B-001/002)</text>\n'
    s += '  <circle cx="420" cy="500" r="150.4" class="hidden"/>\n'
    s += '  <circle cx="420" cy="500" r="100" class="hidden"/>\n'
    s += '  <text x="540" y="362" class="small">pocket OD 150.4 / ID 100.0 x 5.595 deep (B-007..009)</text>\n'
    s += '  <text x="330" y="506" class="small">bore 100.0</text>\n'
    import math
    for a in M5_ANGLES:
        x = 62.5 * math.cos(math.radians(a))
        y = 62.5 * math.sin(math.radians(a))
        px, py = mm2px(x, y)
        s += f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="5.5" class="hole"/>\n'
    s += '  <text x="180" y="300" class="small">8x dia 5.5 M5 interstage @ R62.5, start 22.5\u00b0 (B-011..014)</text>\n'
    for x, y in [(70, 70), (70, -70), (-70, 70), (-70, -70)]:
        px, py = mm2px(x, y)
        s += f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="30" class="hidden"/>\n'
        s += f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="6.6" class="holeB"/>\n'
    s += '  <text x="600" y="600" class="small">4x dia 6.6 M6 clearance @ (\u00b170, \u00b170) with R15 ears (B-004/015/016)</text>\n'
    s += '  <text x="600" y="622" class="small">M6 nominal hole-edge ligament 11.7 (B-018; NOT a worst-case margin)</text>\n'
    px, py = mm2px(55.0, 0.0)
    s += f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="none" stroke="#b3541e" stroke-width="2" stroke-dasharray="4 3"/>\n'
    s += '  <text x="540" y="530" class="small">dowel blind dia 4.0 x 5.5 deep @ (55.0, 0.0) \u2014 CANDIDATE (B-019..021)</text>\n'
    # section view
    s += '  <text x="850" y="118" class="h">Axial section schematic (8 px/mm axial)</text>\n'
    s += '  <rect x="880" y="180" width="320" height="96" class="m3r"/>\n'
    s += '  <rect x="880" y="180" width="320" height="44.8" fill="#b8e4cf" stroke="#24734b" stroke-width="2"/>\n'
    s += '  <text x="900" y="170" class="small">pocket 5.595 deep; remaining below pocket 6.405 (B-010); base 12.0 (B-003)</text>\n'
    s += '  <line x1="880" y1="140" x2="880" y2="300" class="datum"/>\n'
    s += '  <text x="700" y="135" class="small">208.0 top plane (z=0, install face)</text>\n'
    s += '  <line x1="1200" y1="140" x2="1200" y2="300" class="datum"/>\n'
    s += '  <text x="1060" y="128" class="small">196.0 bottom plane (z=-12.0, mate to bridge)</text>\n'
    s += '  <line x1="880" y1="316" x2="1200" y2="316" class="dim"/>\n'
    s += '  <text x="1020" y="338" class="small">12.0</text>\n'
    # facts panel
    s += '  <rect x="850" y="380" width="520" height="230" fill="#f0f7ff" stroke="#1f5f8b" stroke-width="2"/>\n'
    s += '  <text x="868" y="410" class="h">DESIGN DATA (sources: M3R_STAGE_B_PARAMETER_TABLE.yaml)</text>\n'
    s += '  <text x="868" y="438" class="small">\u2022 volume 161966.032228 mm3 (B-023, DERIVED, independent reopen)</text>\n'
    s += '  <text x="868" y="462" class="small">\u2022 material-derived mass 437.308287 g \u2014 INACTIVE, not budget, not measured (B-024)</text>\n'
    s += '  <text x="868" y="486" class="small">\u2022 legacy M8 BCD130 pattern OMITTED / REJECTED for primary load (B-rejected-feature)</text>\n'
    s += '  <text x="868" y="510" class="small">\u2022 material AL6061-T6 CANDIDATE \u2192 binding PENDING_SIBLING_HASH wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1.yaml</text>\n'
    s += '  <text x="868" y="534" class="small">\u2022 M6 pattern position tolerance HOLD \u2192 PENDING_SIBLING_HASH wp3_tolerance_alloc/DRAWING_TOLERANCE_SCHEME_V1.csv</text>\n'
    s += '  <text x="868" y="558" class="small">\u2022 bridge-side fasteners \u2192 PENDING_SIBLING_HASH wp4_fastener_design/FASTENER_SCHEDULE_V1.csv</text>\n'
    s += '  <text x="868" y="582" class="small">\u2022 live mating load-bridge geometry: M6 candidate LOAD_BRIDGE_DATUMS_V1.yaml; WP1 owns authority</text>\n'
    # boundary box
    s += '  <rect x="850" y="640" width="520" height="200" fill="#fff7ed" stroke="#d64545" stroke-width="2"/>\n'
    s += '  <text x="868" y="670" class="h">RELEASE BOUNDARY</text>\n'
    s += '  <text x="868" y="698" class="small">\u2022 ALL_MANUFACTURING_TOLERANCES_HOLD; surface spec HOLD \u2192 WP3 contract</text>\n'
    s += '  <text x="868" y="722" class="small">\u2022 load-bridge physical fitup HOLD; no FEA/MoS claim on this sheet</text>\n'
    s += '  <text x="868" y="746" class="small">\u2022 no procurement, manufacturing, flight, or qualification claim</text>\n'
    s += '  <text x="868" y="770" class="small">\u2022 candidate \u2260 authority; design \u2260 flight-qualified</text>\n'
    s += '  <text x="868" y="794" class="small">\u2022 stage mass split PENDING_SIBLING_HASH wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml</text>\n'
    s += '  <text x="40" y="880" class="small">Units: mm. Frame authority: ODR-01. M6 hole pattern congruence with bridge by construction (max abs deviation 4.632e-10 mm, LOAD_BRIDGE_DATUMS_V1.yaml). Generated: ' + GEN_LOCAL + '</text>\n'
    s += '</svg>\n'
    return s


def build_d07():
    s = svg_header("D07 \u2014 HARNESS ROUTING SCHEMATIC", BANNER + " \u00b7 SCHEMATIC ONLY \u2014 NO GEOMETRIC AUTHORITY")
    # schematic chain: BUS -> central passage -> M3R -> B601 base -> arm -> gripper; branch to wings
    s += '  <text x="50" y="120" class="h">Logical routing graph (not a physical route; authority = WP1 contract)</text>\n'
    s += '  <rect x="60" y="180" width="200" height="90" class="bus"/>\n'
    s += '  <text x="90" y="218" class="h">BUS CORE</text>\n'
    s += '  <text x="82" y="242" class="small">avionics / power feeds</text>\n'
    s += '  <rect x="330" y="180" width="230" height="90" class="m3r"/>\n'
    s += '  <text x="352" y="212" class="h">M3R CENTRAL PASSAGE</text>\n'
    s += '  <text x="348" y="236" class="small">dia 40 through Stage A+B (A-007)</text>\n'
    s += '  <text x="348" y="256" class="small">bridge centre dia 40 (M6 candidate)</text>\n'
    s += '  <rect x="630" y="180" width="200" height="90" class="bus"/>\n'
    s += '  <text x="652" y="212" class="h">B601 ARM BASE</text>\n'
    s += '  <text x="648" y="236" class="small">x=208.0 mount; base loom egress</text>\n'
    s += '  <rect x="900" y="180" width="200" height="90" class="bus"/>\n'
    s += '  <text x="920" y="212" class="h">ARM LINK LOOMS</text>\n'
    s += '  <text x="916" y="236" class="small">joint-to-joint moving spans</text>\n'
    s += '  <rect x="1170" y="180" width="190" height="90" class="cand"/>\n'
    s += '  <text x="1190" y="212" class="h">GRIPPER R1</text>\n'
    s += '  <text x="1184" y="236" class="small">wrist-end service loop</text>\n'
    for x1, x2 in [(260, 330), (560, 630), (830, 900), (1100, 1170)]:
        s += f'  <line x1="{x1}" y1="225" x2="{x2}" y2="225" stroke="#22303c" stroke-width="2" marker-end="url(#arrow)"/>\n'
    # wing branch
    s += '  <rect x="330" y="330" width="230" height="80" class="panel"/>\n'
    s += '  <text x="360" y="362" class="h">HINGE L / R</text>\n'
    s += '  <text x="352" y="386" class="small">deployment moving span</text>\n'
    s += '  <rect x="630" y="330" width="200" height="80" class="panel"/>\n'
    s += '  <text x="655" y="362" class="h">SOLAR PANELS</text>\n'
    s += '  <text x="648" y="386" class="small">0.227 x 0.200 x 0.006 m box each</text>\n'
    s += '  <line x1="160" y1="270" x2="160" y2="370" stroke="#22303c" stroke-width="2"/>\n'
    s += '  <line x1="160" y1="370" x2="330" y2="370" stroke="#22303c" stroke-width="2" marker-end="url(#arrow)"/>\n'
    s += '  <line x1="560" y1="370" x2="630" y2="370" stroke="#22303c" stroke-width="2" marker-end="url(#arrow)"/>\n'
    # rules panel
    s += '  <rect x="60" y="460" width="640" height="330" fill="#f0f7ff" stroke="#1f5f8b" stroke-width="2"/>\n'
    s += '  <text x="78" y="490" class="h">ROUTING RULES / BINDINGS</text>\n'
    s += '  <text x="78" y="518" class="small">\u2022 routing authority: PENDING_SIBLING_HASH wp1_structure_cad/HARNESS_ROUTING_V1.yaml</text>\n'
    s += '  <text x="78" y="542" class="small">\u2022 keep-out authority: PENDING_SIBLING_HASH wp1_structure_cad/KEEP_OUT_REGISTER_V1.yaml</text>\n'
    s += '  <text x="78" y="566" class="small">\u2022 bend radius / strain relief / connector definition: TBD \u2192 WP1 contract</text>\n'
    s += '  <text x="78" y="590" class="small">\u2022 static OD9 keep-out exists (CDR CI-011); moving-sweep verification HOLD (MSR-MEC-010)</text>\n'
    s += '  <text x="78" y="614" class="small">\u2022 harness crosses M3R via central dia 40 passage; no other M3R penetration allowed</text>\n'
    s += '  <text x="78" y="638" class="small">\u2022 gripper service loop must respect stroke 0\u201371.5 mm (MSR-MEC-001 envelope)</text>\n'
    s += '  <text x="78" y="662" class="small">\u2022 panel-failure configs: attached-stuck semantics (ODR-02) \u2014 harness must not rely on jettison</text>\n'
    s += '  <text x="78" y="686" class="small">\u2022 dynamic sweep / wear / life: TEST_REQUIRED_HOLD (see VERIFICATION_MATRIX_V1.csv MSR-MEC-010)</text>\n'
    s += '  <text x="78" y="710" class="small">\u2022 no connector part numbers, wire gauges, or vendor data are claimed here</text>\n'
    s += '  <rect x="760" y="460" width="600" height="180" fill="#fff7ed" stroke="#d64545" stroke-width="2"/>\n'
    s += '  <text x="778" y="490" class="h">RELEASE BOUNDARY</text>\n'
    s += '  <text x="778" y="518" class="small">\u2022 schematic only; carries no geometry, length, or bend-radius authority</text>\n'
    s += '  <text x="778" y="542" class="small">\u2022 no manufacturing, procurement, flight, or qualification claim</text>\n'
    s += '  <text x="778" y="566" class="small">\u2022 moving harness hardware verification remains HOLD</text>\n'
    s += '  <text x="778" y="590" class="small">\u2022 integration backfills WP1 hashes into 12_release/M7_CROSS_WP_REFERENCE_RECONCILIATION_V1.json</text>\n'
    s += '  <text x="40" y="880" class="small">Generated: ' + GEN_LOCAL + '</text>\n'
    s += '</svg>\n'
    return s


def build_d08():
    s = svg_header("D08 \u2014 ASSEMBLY STACKUP (BUS \u2192 B601)", BANNER)
    s += '  <text x="50" y="118" class="h">Axial stack schematic (+X<tspan baseline-shift="sub">S</tspan> to the right) \u2014 12.5 px/mm from x=150 mm</text>\n'
    s += '  <line x1="120" y1="330" x2="1300" y2="330" stroke="#22303c" stroke-width="2" marker-end="url(#arrow)"/>\n'
    s += '  <text x="1308" y="337" class="t">+X<tspan baseline-shift="sub">S</tspan></text>\n'

    def X(v):
        return 150.0 + (v - 150.0) * 12.5
    # bars
    s += f'  <rect x="{X(150):.1f}" y="255" width="{X(170.25) - X(150):.1f}" height="150" class="bus"/>\n'
    s += f'  <text x="{X(152):.1f}" y="245" class="small">12U BUS PROXY (internal structure HOLD)</text>\n'
    s += f'  <rect x="{X(170.25):.1f}" y="265" width="{X(185.25) - X(170.25):.1f}" height="130" class="flange"/>\n'
    s += f'  <text x="{X(160):.1f}" y="435" class="small">legacy flange 170.25\u2013185.25 \u2014 EXCLUDED, ownership HOLD (mass assigned to BUS_PRIMARY_STRUCTURE with declared uncertainty)</text>\n'
    s += f'  <rect x="{X(185.25):.1f}" y="245" width="{X(196.0) - X(185.25):.1f}" height="170" class="cand"/>\n'
    s += f'  <text x="{X(183):.1f}" y="233" class="small">LOAD BRIDGE CANDIDATE 160x160x10.75 (M6 WP1 candidate; 6061-T6 2700 kg/m3; 702.195458 g MATERIAL_DERIVED)</text>\n'
    s += f'  <rect x="{X(196.0):.1f}" y="255" width="{X(208.0) - X(196.0):.1f}" height="150" class="m3r"/>\n'
    s += f'  <text x="{X(196.5):.1f}" y="245" class="small">STAGE B 12.0</text>\n'
    s += f'  <rect x="{X(208.0):.1f}" y="270" width="{X(210.405) - X(208.0):.1f}" height="120" fill="#b8e4cf" stroke="#24734b" stroke-width="2"/>\n'
    s += f'  <text x="{X(209):.1f}" y="258" class="small">STAGE A proud 2.405</text>\n'
    s += f'  <path d="M{X(210.405):.1f} 330 C1040 240,1140 240,1210 330" class="witness"/>\n'
    s += f'  <circle cx="{X(210.405):.1f}" cy="330" r="7" fill="#744fc6"/>\n'
    s += '  <text x="1040" y="222" class="small">B601 q0 frame/axis witness \u2014 physical arm B-rep not installed (WP1 owns design-freeze)</text>\n'
    # datum lines
    for v, lab, ty in [
        (170.25, "170.25 legacy flange inner face", 470),
        (185.25, "185.25 M dynamics / bus +X face / D_BRIDGE_BUS \u2014 frame authority ODR-01", 500),
        (196.0, "196.0 Stage B bottom / D_BRIDGE_M3R", 530),
        (198.0, "198.0 adapter plate external face (no geometry)", 560),
        (208.0, "208.0 physical install / arm base / M3R_LOCAL z=0", 590),
        (210.405, "210.405 screw-end plane (as-built)", 620),
    ]:
        s += f'  <line x1="{X(v):.1f}" y1="150" x2="{X(v):.1f}" y2="{ty}" class="datum"/>\n'
        s += f'  <text x="{X(v) - 130:.1f}" y="{ty + 18}" class="small">{lab}</text>\n'
    # dims
    s += f'  <line x1="{X(185.25):.1f}" y1="660" x2="{X(196.0):.1f}" y2="660" class="dim"/>\n'
    s += f'  <text x="{X(187):.1f}" y="682" class="small">10.75</text>\n'
    s += f'  <line x1="{X(196.0):.1f}" y1="700" x2="{X(208.0):.1f}" y2="700" class="dim"/>\n'
    s += f'  <text x="{X(199):.1f}" y="722" class="small">12.0</text>\n'
    s += f'  <line x1="{X(185.25):.1f}" y1="740" x2="{X(208.0):.1f}" y2="740" class="dim"/>\n'
    s += f'  <text x="{X(192):.1f}" y="762" class="small">22.75 (= 185.25 \u2192 208.0)</text>\n'
    # tolerance panel
    s += '  <rect x="850" y="440" width="520" height="250" fill="#f0f7ff" stroke="#1f5f8b" stroke-width="2"/>\n'
    s += '  <text x="868" y="470" class="h">STACKUP TOLERANCE EVIDENCE (M6, worst-case)</text>\n'
    s += '  <text x="868" y="498" class="small">\u2022 B601\u2013M3R WC min radial clearance 0.101015357 mm</text>\n'
    s += '  <text x="868" y="522" class="small">\u2022 Stage A\u2194B spigot WC 0.206 mm; skirt WC 0.207 mm</text>\n'
    s += '  <text x="868" y="546" class="small">\u2022 dowel clocking WC 1.8909e-3 rad; hinge tip sensitivity 0.2 mm/mrad</text>\n'
    s += '  <text x="868" y="570" class="small">\u2022 source: wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml (M6)</text>\n'
    s += '  <text x="868" y="594" class="small">\u2022 drawing tolerance scheme: PENDING_SIBLING_HASH wp3_tolerance_alloc/DRAWING_TOLERANCE_SCHEME_V1.csv</text>\n'
    s += '  <text x="868" y="618" class="small">\u2022 chain register: PENDING_SIBLING_HASH wp3_tolerance_alloc/TOLERANCE_CHAIN_REGISTER_V1.yaml (14 chains)</text>\n'
    s += '  <text x="868" y="642" class="small">\u2022 fastener/preload schedule: PENDING_SIBLING_HASH wp4_fastener_design/TORQUE_PRELOAD_SCHEDULE_V1.csv</text>\n'
    s += '  <text x="868" y="666" class="small">\u2022 assembly sequence: ASSEMBLY_PROCEDURE_V1.md (this WP)</text>\n'
    # boundary
    s += '  <rect x="850" y="710" width="520" height="130" fill="#fff7ed" stroke="#d64545" stroke-width="2"/>\n'
    s += '  <text x="868" y="740" class="h">RELEASE BOUNDARY</text>\n'
    s += '  <text x="868" y="768" class="small">\u2022 bus-side anchor pattern HOLD \u2014 bridge-to-bus joint not closed at hardware level</text>\n'
    s += '  <text x="868" y="792" class="small">\u2022 no FEA/MoS, no manufacturing, no flight or qualification claim</text>\n'
    s += '  <text x="868" y="816" class="small">\u2022 M frame (x=185.25, nonphysical) never aliased with physical stations (ODR-01)</text>\n'
    s += '  <text x="40" y="880" class="small">Units: mm. Stations: M6 wp6_drawings_bom/INTERFACE_STATION_SCHEDULE_V2.csv + M6 wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml. Generated: ' + GEN_LOCAL + '</text>\n'
    s += '</svg>\n'
    return s


DRAWING_INDEX_HEADER = [
    "drawing_id", "title", "file", "scale", "release_status", "manufacturing_use",
    "material_specification", "tolerance_specification", "owner_wp", "v3_note",
]
DRAWING_INDEX_ROWS = [
    ["D01", "Digital prototype interface axial layout",
     M4 + "/09_drawings/D01_DIGITAL_PROTOTYPE_INTERFACE_LAYOUT_DRAFT.svg",
     "NOT_TO_SCALE", "WORKING_DRAFT", "PROHIBITED", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "M4",
     "CARRIED_FROM_M4_UNCHANGED; superseded in role only where D08 restates the axial stack"],
    ["D02", "Authoritative axial station schedule",
     M4 + "/09_drawings/D02_INTERFACE_STATION_SCHEDULE_V1.csv",
     "DATA_TABLE", "WORKING_DRAFT", "PROHIBITED", "NOT_APPLICABLE", "NOT_APPLICABLE", "M4",
     "CARRIED_FROM_M4_UNCHANGED; M6 candidate extension at " + M6 + "/wp6_drawings_bom/INTERFACE_STATION_SCHEDULE_V2.csv does not modify D02"],
    ["D03", "Digital prototype component and drawing cross reference",
     M4 + "/09_drawings/D03_COMPONENT_DRAWING_CROSS_REFERENCE_V1.csv",
     "DATA_TABLE", "WORKING_DRAFT", "PROHIBITED", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "M4",
     "CARRIED_FROM_M4_UNCHANGED"],
    ["D04_LOAD_BRIDGE_INTERFACE_DRAFT", "Spacecraft to M3R load bridge interface draft",
     M6 + "/wp1_load_bridge/D04_LOAD_BRIDGE_INTERFACE_DRAFT.svg",
     "NOT_TO_SCALE", "CANDIDATE_NOT_AUTHORITY", "PROHIBITED", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "M6-WP1",
     "FILE_EXISTS_AT_M6_PATH (verified this loop); promotion to design authority via M7 WP1 contract "
     + C_WP1_ASSY_STEP + " " + PEND],
    ["D05_STAGE_A", "M3R Stage A interface ring (Rev-B) design sheet",
     WP9 + "/D05_STAGE_A.svg",
     "NOT_TO_SCALE", "DESIGN_RELEASE_CANDIDATE", "PROHIBITED",
     "AL6061-T6 CANDIDATE \u2192 " + PEND + " " + C_WP6_MAT,
     PEND + " " + C_WP3_SCHEME, "WP9",
     "NEW_THIS_WP; numeric basis M3R_STAGE_A_PARAMETER_TABLE.yaml; fasteners \u2192 " + PEND + " " + C_WP4_M3R],
    ["D06_STAGE_B", "M3R Stage B load diffusion adapter (Rev-B2) design sheet",
     WP9 + "/D06_STAGE_B.svg",
     "NOT_TO_SCALE", "DESIGN_RELEASE_CANDIDATE", "PROHIBITED",
     "AL6061-T6 CANDIDATE \u2192 " + PEND + " " + C_WP6_MAT,
     PEND + " " + C_WP3_SCHEME, "WP9",
     "NEW_THIS_WP; numeric basis M3R_STAGE_B_PARAMETER_TABLE.yaml; bridge-side fasteners \u2192 " + PEND + " " + C_WP4_SCHED],
    ["D07_HARNESS_ROUTING_SCHEMATIC", "Harness routing schematic (logical graph only)",
     WP9 + "/D07_HARNESS_ROUTING_SCHEMATIC.svg",
     "SCHEMATIC_NO_GEOMETRIC_AUTHORITY", "DESIGN_RELEASE_CANDIDATE", "PROHIBITED",
     "NOT_APPLICABLE", "NOT_APPLICABLE", "WP9",
     "NEW_THIS_WP; routing authority \u2192 " + PEND + " " + C_WP1_HARNESS + "; keep-out \u2192 " + PEND + " " + C_WP1_KEEPOUT],
    ["D08_ASSEMBLY_STACKUP", "Assembly stackup bus to B601 with station and tolerance evidence",
     WP9 + "/D08_ASSEMBLY_STACKUP.svg",
     "NOT_TO_SCALE", "DESIGN_RELEASE_CANDIDATE", "PROHIBITED",
     "SEE_D05_D06_AND_BOM_V3", PEND + " " + C_WP3_SCHEME, "WP9",
     "NEW_THIS_WP; stations per M6 INTERFACE_STATION_SCHEDULE_V2 + LOAD_BRIDGE_DATUMS_V1; WC numbers per M6 wp3_tolerance"],
]


# BOM V3: V2's 16 columns carried verbatim, then 7 V3 binding columns.
BOM_V3_HEADER = [
    "item_id", "quantity", "assembly_item", "component_or_slot", "geometry_source",
    "geometry_status", "material", "supplier_or_vendor", "mass", "tolerance",
    "finish", "fasteners", "procurement_status", "release_hold",
    "candidate_asset_path", "v2_row_disposition",
    "material_design_binding", "mass_design_value", "mass_design_class",
    "mass_design_binding", "fastener_design_binding", "v3_row_disposition", "v3_note",
]

BOM_V3_ROWS = [
    ["DP-001", "1", "12U bus core", "INST_BUS_12U_CORE", "model_specs_v0.json analytic primitives",
     "block proxy with legacy flange", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "NOT_A_PROCUREMENT_BOM",
     "internal structure and load bridge unknown", "NONE", "CARRIED_FROM_V1",
     PEND + " " + C_WP6_MAT + " (BUS_PRIMARY_STRUCTURE selection)",
     "23.303213400000 kg = 22.927194215348 bus-core diagnostic (no panels, no legacy flange) + 0.376019184652 legacy-flange diagnostic assigned to BUS_PRIMARY_STRUCTURE with declared uncertainty",
     "DESIGN_DIAGNOSTIC_CONTRACT_VALUE",
     "M7_EXECUTION_PLAN_V1 contract values; aggregation " + PEND + " " + C_WP2_MASS,
     "NOT_APPLICABLE",
     "MASS_BOUND_TO_CONTRACT__MATERIAL_PENDING_WP6",
     "Design diagnostic mass only; not as-built (MSR-STR-002 EXTERNAL_HOLD). NOT_A_PROCUREMENT_BOM. Internal structure HOLD retained."],
    ["DP-002", "1", "left solar array", "INST_SOLAR_ARRAY_LEFT_DEPLOYED", "model_specs_v0.json box primitive",
     "deployed proxy only", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "NOT_A_PROCUREMENT_BOM",
     "stowed geometry and hinge kinematics unknown", "NONE", "CARRIED_FROM_V1",
     PEND + " " + C_WP6_MAT + " (SOLAR_PANEL selection)",
     "0.3483933 kg (panel box 0.227 x 0.200 x 0.006 m)",
     "CONTRACT_VALUE",
     "M7_EXECUTION_PLAN_V1 contract value; nine-config aggregation " + PEND + " " + C_WP2_MASS,
     "NOT_APPLICABLE",
     "MASS_BOUND_TO_CONTRACT__STOWED_GEOMETRY_HOLD_RETAINED",
     "Stowed geometry / hinge kinematics: " + PEND + " " + C_WP1_STRUCT + " and " + C_WP5_HINGE + ". Mechanism qualification TEST_REQUIRED_HOLD (MSR-MEC-007)."],
    ["DP-003", "1", "right solar array", "INST_SOLAR_ARRAY_RIGHT_DEPLOYED", "model_specs_v0.json box primitive",
     "deployed proxy only", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "NOT_A_PROCUREMENT_BOM",
     "stowed geometry and hinge kinematics unknown", "NONE", "CARRIED_FROM_V1",
     PEND + " " + C_WP6_MAT + " (SOLAR_PANEL selection)",
     "0.3483933 kg (panel box 0.227 x 0.200 x 0.006 m)",
     "CONTRACT_VALUE",
     "M7_EXECUTION_PLAN_V1 contract value; nine-config aggregation " + PEND + " " + C_WP2_MASS,
     "NOT_APPLICABLE",
     "MASS_BOUND_TO_CONTRACT__STOWED_GEOMETRY_HOLD_RETAINED",
     "Same bindings as DP-002. Panel failure semantics attached-stuck, never jettison (ODR-02)."],
    ["DP-004", "1", "B601 arm system", "INST_B601_ARM_CORE_Q0", "B601_KINEMATIC_ASSEMBLY_Q0_WITNESS.step",
     "frame and axis witness only", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "NOT_A_PROCUREMENT_BOM",
     "physical arm B-rep and fitup unknown", "NONE", "CARRIED_FROM_V1",
     "NOT_APPLICABLE_L0_AUTHORITY (vendor product; no WP6 material substitution)",
     "4.695555949342986 kg",
     "ACCEPTED_URDF_L0",
     "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf SHA-256 pinned in receipt; never overridden (MSR-STR-001); design-mass use via " + PEND + " " + C_WP2_MASS,
     "arm-to-Stage-A group = DP-012",
     "L0_MASS_AUTHORITY_RETAINED",
     "Physical B-rep / fitup HOLD retained; WP1 design-freeze assembly is the design-level placement authority."],
    ["DP-005", "1", "M3R Stage A ring", "INST_M3R_INTERFACE_ASSEMBLY", "M3R_INTERFACE_ASSEMBLY_V2_WORKING.step",
     "working combined B-rep stage component", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "NOT_RELEASED",
     "fitup material tolerance and fastener authority unknown", "NONE", "CARRIED_FROM_V1",
     PEND + " " + C_WP6_MAT + " (M3R_STAGE_A; AL6061-T6 candidate per M3R_STAGE_A_PARAMETER_TABLE.yaml A-021)",
     "PART_OF_M3R_TOTAL 0.7619 kg DESIGN_BUDGET conf B (ODR-05); stage split " + PEND + " " + C_WP2_MASS,
     "DESIGN_BUDGET_ODR05__STAGE_SPLIT_PENDING_WP2",
     "ODR-05 + M7_EXECUTION_PLAN_V1 contract; inactive material-derived comparison 345.018961 g NOT used",
     PEND + " " + C_WP4_M3R,
     "MATERIAL_BOUND_PENDING_WP6__MASS_BOUND_ODR05__TOLERANCE_PENDING_WP3",
     "Drawing D05_STAGE_A (this WP). Tolerances " + PEND + " " + C_WP3_SCHEME + ". Fitup HOLD retained (MSR-INT-011)."],
    ["DP-006", "1", "M3R Stage B load diffusion plate", "INST_M3R_INTERFACE_ASSEMBLY", "M3R_INTERFACE_ASSEMBLY_V2_WORKING.step",
     "working combined B-rep stage component", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "NOT_RELEASED",
     "load bridge fitup material tolerance and fastener authority unknown", "NONE", "CARRIED_FROM_V1",
     PEND + " " + C_WP6_MAT + " (M3R_STAGE_B; AL6061-T6 candidate per M3R_STAGE_B_PARAMETER_TABLE.yaml B-022)",
     "PART_OF_M3R_TOTAL 0.7619 kg DESIGN_BUDGET conf B (ODR-05); stage split " + PEND + " " + C_WP2_MASS,
     "DESIGN_BUDGET_ODR05__STAGE_SPLIT_PENDING_WP2",
     "ODR-05 + M7_EXECUTION_PLAN_V1 contract; inactive material-derived comparison 437.308287 g NOT used",
     "interstage 8xM5 \u2192 " + PEND + " " + C_WP4_SCHED + "; bridge-side 4xM6 \u2192 " + PEND + " " + C_WP4_SCHED,
     "MATERIAL_BOUND_PENDING_WP6__MASS_BOUND_ODR05__TOLERANCE_PENDING_WP3",
     "Drawing D06_STAGE_B (this WP). Live mating bridge geometry carried as M6 candidate; WP1 owns authority."],
    ["DP-007", "1", "spacecraft to M3R load bridge", "SLOT_SPACECRAFT_LOAD_BRIDGE__UNRESOLVED", "no authorized geometry",
     "CANDIDATE_GEOMETRY_PENDING_WP1", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "HARD_HOLD",
     "structural load path discontinuity", M6 + "/wp1_load_bridge/ (candidate geometry and datums pending WP1)", "UPGRADED_TO_CANDIDATE_GEOMETRY_STATUS",
     PEND + " " + C_WP6_MAT + " (LOAD_BRIDGE; 6061-T6 2700 kg/m3 candidate per M6 LOAD_BRIDGE_DATUMS_V1.yaml)",
     "0.702195458 kg (160x160x10.75 mm plate, 4x dia 6.6 @ (\u00b170,\u00b170), centre dia 40)",
     "MATERIAL_DERIVED_CANDIDATE_NOT_HARDWARE_MASS",
     M6 + "/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml (measured:false, installed:false); design confirmation " + PEND + " " + C_WP1_ASSY_STEP,
     "4x M6 class co-bore candidate \u2192 " + PEND + " " + C_WP4_SCHED,
     "HARD_HOLD_RETAINED__CANDIDATE_CARRIED__BINDINGS_PENDING",
     "Bus-side anchor pattern HOLD (no authorized bus mating pattern); structural load path continuity HOLD; candidate \u2260 authority."],
    ["DP-008", "1", "gripper R1 palm", "INST_GRIPPER_R1_PALM", "B601_GRIPPER_PALM_RAIL_SLOT_R1.step",
     "palm-only working B-rep", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "NOT_RELEASED",
     "finger contact structural and manufacturing clearance unknown", "NONE", "CARRIED_FROM_V1",
     PEND + " " + C_WP6_MAT + " (GRIPPER_R1 selection)",
     "COVERED_BY_DP-004_L0__NO_SEPARATE_VALUE",
     "NO_ZERO_FILL",
     "B601 L0 URDF mass covers arm system incl. gripper envelope; no separate part mass asserted",
     "gripper fasteners TBD \u2192 " + PEND + " " + C_WP4_SCHED + "; engineering pack " + PEND + " " + C_WP5_GRIPPER,
     "NOT_RELEASED_RETAINED__BINDINGS_PENDING",
     "Neutral R1 sweep PASS (MSR-MEC-001); manufacturing clearance / min-wall EXTERNAL_HOLD (MSR-MEC-003/004)."],
    ["DP-009", "1 set", "gripper R1 separated fingers", "SLOT_GRIPPER_R1_FINGERS__UNRESOLVED", "no valid separated B-reps",
     "absent", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "HARD_HOLD",
     "contact geometry and pregrasp state unknown",
     M5 + "/01_geometry_authority/assets/b601_link_local_surfaces/B601_GRIPPER_R1_LEFT_FINGER_GRIPPER_LINK_LOCAL_M.ply; " + M5 + "/01_geometry_authority/assets/b601_link_local_surfaces/B601_GRIPPER_R1_RIGHT_FINGER_GRIPPER_LINK_LOCAL_M.ply (diagnostic link-local surface meshes; not separated B-reps)",
     "CARRIED_FROM_V1_WITH_CANDIDATE_PATH",
     "NONE__HARD_HOLD_RETAINED",
     "COVERED_BY_DP-004_L0__NO_SEPARATE_VALUE",
     "NO_ZERO_FILL",
     "NONE",
     "NONE__HARD_HOLD_RETAINED",
     "HARD_HOLD_RETAINED_NO_BINDING",
     "Diagnostic .ply surfaces are not working B-reps; no design binding created in M7 WP9."],
    ["DP-010", "1", "sensor package", "SLOT_SENSOR_PACKAGE__UNRESOLVED", "model_specs_v0.json rejected camera placeholder",
     "source available but not installed", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "HARD_HOLD",
     "source pose penetrates M3R and replacement pose is not authorized", "NONE__NO_M5_OR_M6_CANDIDATE_ASSET", "CARRIED_FROM_V1",
     "NONE__SELECTION_HOLD (MSR-MEC-009)",
     "UNSPECIFIED_HOLD",
     "NO_ZERO_FILL",
     "NONE",
     "mount fasteners TBD after camera selection; keep-out/support candidates " + PEND + " " + C_WP1_KEEPOUT + ", " + C_WP1_SUPPORT,
     "HARD_HOLD_RETAINED_NO_BINDING",
     "Camera product selection, mount, alignment, hand-eye calibration HOLD (MSR-MEC-009). D07 carries no camera route authority."],
    ["DP-011", "1", "arm HDRM", "SLOT_ARM_HDRM__UNRESOLVED", "nonphysical skeleton reference only",
     "not installed", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "HARD_HOLD",
     "global transform clocking product and functional evidence unknown",
     M5 + "/03_load_authority/M5_LOAD_CASE_MIGRATION_REGISTER_V1.csv (LC-007 hdrm_release; functional envelope hold retained)",
     "CARRIED_FROM_V1_WITH_CANDIDATE_PATH",
     "NONE__PRODUCT_SELECTION_HOLD",
     "UNSPECIFIED_HOLD",
     "NO_ZERO_FILL",
     "NONE",
     "HDRM fastener/install definition " + PEND + " " + C_WP5_HDRM,
     "HARD_HOLD_RETAINED__ENGINEERING_PACK_PENDING_WP5",
     "WP5 HDRM engineering pack is design analysis only; approved product selection and release test remain HOLD (MSR-MEC-008, MSR-OPS-005)."],
    ["DP-012", "4", "B601 to M3R Stage A fastener group 4 x HM4-75 class", "INST_M3R_INTERFACE_ASSEMBLY",
     "B601 as-built four-axis evidence; M5 pattern B601_TO_STAGE_A_4XM4_64MM 64 x 64 mm square; equivalent PCD 90.509642 mm",
     "as-built screw end faces measured at x 210.405 mm; fastener bodies not modeled", "PROTOTYPE_CANDIDATE", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "4 x HM4-75 class; grade length washer thread engagement and preload TBD", "NOT_RELEASED",
     "fastener selection preload tool access and margin of safety unknown; A286 material is candidate only pending WP4 library",
     M6 + "/wp4_materials/PROTOTYPE_MATERIAL_LIBRARY_V2_CANDIDATE.yaml (A286 entry pending WP4); " + M5 + "/04_joint_load_model/M5_FASTENER_GROUP_INFLUENCE_MATRIX_V1.csv",
     "NEW_CANDIDATE_ROW",
     PEND + " " + C_WP6_MAT + " (FASTENER class; A286 candidate carried)",
     "UNSPECIFIED_HOLD (fastener masses in schedule " + PEND + ")",
     "NO_ZERO_FILL",
     PEND + " " + C_WP2_MASS + " (if scheduled)",
     "FULLY_BOUND_TO_WP4: " + PEND + " " + C_WP4_M3R + "; " + C_WP4_SCHED + "; " + C_WP4_TORQUE + "; " + C_WP4_CHECKS,
     "BOUND_TO_WP4_CONTRACT__PENDING_SIBLING_HASH",
     "M6 WC radial clearance 0.101015357 mm evidence retained. Selection/grade/length/preload/MoS owned by WP4 contract; owner-authorized margin criteria absent (MSR-STR-007 design-level only)."],
    ["DP-013", "1", "M3R interstage clocking dowel asymmetric anti-misassembly candidate", "INST_M3R_INTERFACE_ASSEMBLY",
     "M3R detailed design candidate; blind hole diameter 4.0 mm depth 5.5 mm at local xy 55.0 0.0 mm",
     "candidate feature in working B-rep; diameter material and fit undefined", "UNSPECIFIED_HOLD", "UNASSIGNED", "UNSPECIFIED_HOLD",
     "UNSPECIFIED_HOLD", "UNSPECIFIED_HOLD", "NOT_APPLICABLE", "NOT_RELEASED",
     "dowel diameter material fit insertion and removal hold; candidate not promoted",
     M3DD + "/10_bom/M3R_BOM_V2.csv (row 6 INTERSTAGE_CLOCKING_DOWEL_TBD)",
     "NEW_CANDIDATE_ROW",
     PEND + " " + C_WP6_MAT + " (DOWEL selection)",
     "NEGLIGIBLE_NOT_ZERO_FILLED__NO_VALUE",
     "NO_ZERO_FILL",
     "NONE",
     "fit/tolerance \u2192 " + PEND + " " + C_WP3_CHAINS + " (dowel clocking WC 1.8909e-3 rad M6 evidence); part spec \u2192 " + PEND + " " + C_WP4_SCHED,
     "CANDIDATE_RETAINED__FIT_BINDING_PENDING_WP3_WP4",
     "Candidate not promoted; WC clocking evidence M6 wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml."],
    ["SCN-001", "1 reference", "target satellite 22 kg proxy", "TARGET_SATELLITE_22KG", "model_specs_v0.json millimetre primitives",
     "scenario asset not installed", "UNSPECIFIED_HOLD", "NOT_APPLICABLE", "ASSUMPTION_NOT_BREP_DERIVED",
     "NOT_APPLICABLE", "NOT_APPLICABLE", "NOT_APPLICABLE", "SCENARIO_REFERENCE_ONLY",
     "relative pose and contact interface unknown", "NONE", "CARRIED_FROM_V1",
     "NOT_APPLICABLE", "22 kg scenario anchor (CDR loads: impulses 0.0601233\u20130.360622 N\u00b7s @ 0.5 dps, DERIVED research-bound)",
     "SCENARIO_REFERENCE_ONLY",
     "NONE",
     "NOT_APPLICABLE",
     "CARRIED_SCENARIO_REFERENCE_ONLY",
     "Capture anchor values are DERIVED research-bound, not authorized loads (MSR-STR-003 EXTERNAL_HOLD)."],
    ["SCN-002", "1 reference", "target debris 150 kg proxy", "TARGET_DEBRIS_150KG", "model_specs_v0.json exact primitive compound",
     "scenario asset not installed", "UNSPECIFIED_HOLD", "NOT_APPLICABLE", "ASSUMPTION_NOT_BREP_DERIVED",
     "NOT_APPLICABLE", "NOT_APPLICABLE", "NOT_APPLICABLE", "SCENARIO_REFERENCE_ONLY",
     "relative pose and tangent marker bracket boolean union unknown", "NONE", "CARRIED_FROM_V1",
     "NOT_APPLICABLE", "150 kg scenario anchor (CDR loads: impulses 0.274973\u20130.677633 N\u00b7s @ 3 dps, DERIVED research-bound)",
     "SCENARIO_REFERENCE_ONLY",
     "NONE",
     "NOT_APPLICABLE",
     "CARRIED_SCENARIO_REFERENCE_ONLY",
     "Same boundary as SCN-001."],
]


def build_assembly_procedure():
    lines = []
    A = lines.append
    A("# M7 ASSEMBLY PROCEDURE V1 (DESIGN LEVEL)")
    A("")
    A("- schema: `M7_WP9_ASSEMBLY_PROCEDURE_V1`")
    A(f"- generated_local: `{GEN_LOCAL}`")
    A("- artifact_class: `DESIGN_PROCEDURE_DRAFT` \u2014 design-level master sequence for the engineering release package.")
    A("- **Not** a manufacturing work instruction, not a procurement release, not a flight or qualification document.")
    A("- Every torque / preload value is `PENDING_SIBLING_HASH` \u2192 `" + C_WP4_TORQUE + "` (WP4 contract). No torque value is invented here.")
    A("- Tolerances referenced to `PENDING_SIBLING_HASH` \u2192 `" + C_WP3_SCHEME + "`.")
    A("- Frame authority: ODR-01, T_SM = [185.25, 0, 0] mm + Ry(90\u00b0). Stations 198.0 / 208.0 / 210.405 mm are a geometric feature stack, not a second dynamics frame.")
    A("- source_register with SHA-256 pins: see `receipt.json`.")
    A("")
    A("## General rules")
    A("")
    A("- Fail-closed: any step whose datum, fastener, or inspection input is HOLD is executed only as a design review step, never on hardware.")
    A("- No zero-fill: unknown tool settings stay `TBD -> contract path`, never a guessed number.")
    A("- Candidate \u2260 authority; design \u2260 flight-qualified. L0 URDF masses never overridden.")
    A("- Witness column: W = QA witness point (design review), H = hold point (hardware execution blocked while HOLD stands).")
    A("- Records from every inspection column feed `VERIFICATION_MATRIX_V1.csv` and the INSPECTION_PLAN_V1 KC rows.")
    A("")
    A("## Master sequence")
    A("")
    A("| step | operation | datum | fastener | torque / preload | tool | inspection | witness |")
    A("|---|---|---|---|---|---|---|---|")
    rows = [
        ("AS-01 BUS",
         "Prepare bus primary structure; verify bus +X face reference; legacy flange (x 170.25\u2013185.25) excluded, ownership HOLD; internal structure HOLD",
         "bus +X face x=185.25 (= M dynamics station, nonphysical origin per ODR-01); D_BRIDGE_BUS",
         "none this step",
         "N/A",
         "CMM / surface plate (design: model review)",
         "face condition record; flatness criterion candidate " + PEND + " \u2192 WP3 scheme; KC-02, KC-14",
         "W"),
        ("AS-02 STAGE_A",
         "Present M3R Stage A ring (Rev-B); pre-install dimensional verification of D05 features",
         "M3R_LOCAL z=0 (x=208.0); pattern centre YZ (0.015994151, \u22120.086366070)",
         "none this step",
         "N/A",
         "CMM; pin gauges dia 4.6 / 5.5",
         "KC-01 pattern 64x64 / PCD 90.509642 / clocking 25.000014\u00b0; KC-13 thickness 8.0; per D05_STAGE_A.svg",
         "W"),
        ("AS-03 STAGE_B",
         "Mate Stage B (Rev-B2) to Stage A: spigot dia 99.6 engagement, annular skirt dia 100.6, 8x M5 interstage @ R62.5 start 22.5\u00b0, clocking dowel candidate @ (55.0, 0.0)",
         "Stage B top plane z=0; interstage pattern; dowel pair",
         "8x M5 class stack \u2192 " + PEND + " " + C_WP4_SCHED + "; dowel spec " + PEND + " \u2192 WP3/WP4",
         PEND + " \u2192 " + C_WP4_TORQUE,
         "hex driver + torque wrench (class)",
         "spigot WC 0.206 mm; skirt WC 0.207 mm; dowel clocking WC 1.8909e-3 rad (M6 evidence); KC-04/05/06",
         "W"),
        ("AS-04 LOAD_BRIDGE",
         "Set load bridge candidate (160x160x10.75, 4x dia 6.6 @ 140x140, centre dia 40) between bus face 185.25 and Stage B bottom 196.0",
         "D_BRIDGE_BUS (185.25) / D_BRIDGE_M3R (196.0); M6 hole pattern congruence by construction (max abs dev 4.632e-10 mm)",
         "4x M6 class co-bore candidate \u2192 " + PEND + " " + C_WP4_SCHED,
         PEND + " \u2192 " + C_WP4_TORQUE,
         "torque wrench (class); alignment pins",
         "KC-08 hole pattern / centre dia 40 / ligament 6.7 nominal; flatness criterion " + PEND + " \u2192 WP3 scheme",
         "H \u2014 bus-side anchor pattern HOLD: hardware execution blocked until authorized mating pattern exists"),
        ("AS-05 B601",
         "Mount B601 arm base onto Stage A at x=208.0; as-built 4x M4-class pattern; screw ends reference x=210.405",
         "M3R_LOCAL z=0; 64x64 mm square, PCD 90.509642, clocking 25.000014\u00b0",
         "4x HM4-75 class (DP-012) \u2192 " + PEND + " " + C_WP4_M3R,
         PEND + " \u2192 " + C_WP4_TORQUE,
         "torque wrench + hex driver (class); tool-access envelope " + PEND + " \u2192 WP4 design",
         "KC-01 pattern metrology; KC-03 WC min radial clearance 0.101015357 mm; KC-10 screw-end plane 210.405",
         "W (hardware fitup HOLD \u2014 MSR-INT-011)"),
        ("AS-06 HARNESS",
         "Route harness per design routing: bus \u2192 M3R central dia 40 passage \u2192 B601 base egress \u2192 arm link looms \u2192 gripper service loop; branch to hinge L/R",
         "routing graph D07 (schematic); authority " + PEND + " \u2192 " + C_WP1_HARNESS,
         "clamps / ties TBD \u2192 WP1 contract",
         "N/A (no threaded fastener torque; connector rules \u2192 WP1)",
         "routing tools per WP1; template gauges",
         "KC-11 bend radius / keep-out clearance; OD9 static keep-out; moving sweep HOLD (MSR-MEC-010)",
         "W"),
        ("AS-07 WING_HINGE",
         "Install solar wing hinges L/R per hinge design pack",
         "wing root interface \u2192 " + PEND + " " + C_WP5_HINGE + "; stowed geometry \u2192 " + PEND + " " + C_WP1_STRUCT,
         "hinge fasteners TBD \u2192 " + PEND + " " + C_WP4_SCHED,
         PEND + " \u2192 " + C_WP4_TORQUE,
         "torque wrench (class); angle readback jig",
         "KC-07 hinge tip sensitivity 0.2 mm/mrad; deployment clearance design review",
         "W (mechanism qualification HOLD \u2014 MSR-MEC-007)"),
        ("AS-08 HDRM",
         "Install arm HDRM restraint unit",
         "HDRM install definition \u2192 " + PEND + " " + C_WP5_HDRM,
         "per WP5 pack \u2192 " + PEND,
         PEND + " \u2192 " + C_WP4_TORQUE,
         "per WP5 pack",
         "release-function design review; post-release clearance check (design)",
         "H \u2014 product selection and release reliability HOLD (MSR-MEC-008 / MSR-OPS-005)"),
        ("AS-09 WING_PANEL",
         "Attach solar panels (each 0.3483933 kg, box 0.227 x 0.200 x 0.006 m) to hinges",
         "hinge interface per AS-07; panel failure semantics attached-stuck (ODR-02)",
         "panel fasteners TBD \u2192 " + PEND + " " + C_WP4_SCHED,
         PEND + " \u2192 " + C_WP4_TORQUE,
         "torque wrench (class)",
         "deployed/stowed clearance design review; stowed geometry " + PEND + " \u2192 WP1",
         "W"),
        ("AS-10 GRIPPER",
         "Assemble gripper R1 palm + fingers onto arm wrist end",
         "wrist interface per gripper engineering pack \u2192 " + PEND + " " + C_WP5_GRIPPER,
         "gripper fasteners TBD \u2192 " + PEND + " " + C_WP4_SCHED,
         PEND + " \u2192 " + C_WP4_TORQUE,
         "torque wrench (class)",
         "KC-09 stroke 0\u201371.5 mm no-binding check (design: neutral sweep PASS, 144 samples, zero overlap)",
         "H \u2014 separated finger B-reps HARD_HOLD (DP-009); contact validation HOLD (MSR-MEC-006)"),
        ("AS-11 CAMERA",
         "Mount service camera within authorized keep-out",
         "camera keep-out \u2192 " + PEND + " " + C_WP1_KEEPOUT + "; support candidates \u2192 " + PEND + " " + C_WP1_SUPPORT,
         "mount fasteners TBD after camera selection",
         PEND + " \u2192 " + C_WP4_TORQUE,
         "per mount design",
         "KC-12 keep-out / optical axis (design review only)",
         "H \u2014 camera selection / mount / hand-eye calibration HOLD (MSR-MEC-009)"),
        ("AS-12 ALIGNMENT_CHECK",
         "Final alignment verification: reassert datum chain, run full KC list, record as-left geometry",
         "root-to-M chain T_SM=[185.25,0,0] mm + Ry(90\u00b0) (ODR-01); D08 stackup stations",
         "N/A",
         "N/A",
         "CMM; metrology report template",
         "KC-01..KC-14 per INSPECTION_PLAN_V1.csv; results recorded against VERIFICATION_MATRIX_V1.csv",
         "W (design) / hardware metrology HOLD for flight credit"),
    ]
    for r in rows:
        A("| " + " | ".join(r) + " |")
    A("")
    A("## Blocking HOLD summary (hardware execution)")
    A("")
    A("- AS-04: bus-side anchor pattern undefined (LOAD_BRIDGE_DATUMS_V1.yaml `SPACECRAFT_SIDE_ANCHOR_PATTERN_HOLD`).")
    A("- AS-08: HDRM product selection + release reliability evidence absent.")
    A("- AS-10: gripper separated finger geometry absent (diagnostic .ply only).")
    A("- AS-11: camera product selection absent; rejected pose penetrated M3R, no replacement authorized.")
    A("- All steps: qualification / acceptance testing, launch loads, and launcher ICD remain HOLD (ODR-06 retained; Gate B).")
    A("")
    return "\n".join(lines)


INSPECTION_HEADER = [
    "kc_id", "characteristic", "definition_source", "design_value", "unit",
    "measurement_method", "acceptance_criterion_candidate", "criterion_class",
    "linked_requirements", "linked_drawing", "evidence_or_contract_path", "status", "witness_required",
]
INSPECTION_ROWS = [
    ["KC-01", "M3R arm-side 4x M4-class pattern: 64x64 mm square, PCD, clocking, pattern centre",
     "M3R_STAGE_A_PARAMETER_TABLE.yaml A-011..A-014",
     "64 x 64; PCD 90.509642; clocking 25.000014 deg; centre YZ (0.015994151, -0.086366070)",
     "mm / deg",
     "CMM pattern measurement on as-machined Stage A + B601 base readback",
     "position per drawing tolerance scheme " + PEND,
     "CRITERION_CANDIDATE_PENDING_WP3",
     "MSR-STR-006; MSR-INT-010", "D05",
     C_WP3_SCHEME + " " + PEND, "DESIGN_DEFINED__HARDWARE_MEASUREMENT_HOLD", "W"],
    ["KC-02", "Axial station stack 185.25 / 196.0 / 198.0 / 208.0 / 210.405",
     M6 + "/wp6_drawings_bom/INTERFACE_STATION_SCHEDULE_V2.csv",
     "185.25; 196.0; 198.0; 208.0; 210.405", "mm",
     "CMM axial stations from bus +X datum",
     "station tolerance per scheme " + PEND,
     "CRITERION_CANDIDATE_PENDING_WP3",
     "MSR-INT-010; MSR-STR-006", "D08",
     M6 + "/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml", "DESIGN_DEFINED__HARDWARE_MEASUREMENT_HOLD", "W"],
    ["KC-03", "B601\u2013M3R worst-case minimum radial clearance",
     M6 + "/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml",
     "0.101015357", "mm",
     "component metrology + WC stackup recompute (design); feeler/pin check on hardware",
     "WC min radial clearance >= 0 retained; numeric criterion per scheme " + PEND,
     "CRITERION_CANDIDATE_PENDING_WP3",
     "MSR-STR-006; MSR-INT-011", "D05; D08",
     M6 + "/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml", "DESIGN_WC_EVIDENCE_EXISTS__HARDWARE_HOLD", "W"],
    ["KC-04", "Stage A\u2194B spigot fit (dia 99.6)",
     "M3R_STAGE_A_PARAMETER_TABLE.yaml A-005; M6 stackup",
     "spigot dia 99.6; WC clearance 0.206", "mm",
     "CMM bore/plug measurement",
     "WC 0.206 mm band retained; fit class per scheme " + PEND,
     "CRITERION_CANDIDATE_PENDING_WP3",
     "MSR-STR-006; MSR-STR-008", "D05; D06",
     M6 + "/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml", "DESIGN_WC_EVIDENCE_EXISTS__FIT_INSPECTION_HOLD", "W"],
    ["KC-05", "Stage A annular skirt fit (ID 100.6 vs pocket OD 150.4 / ID 100.0)",
     "M3R_STAGE_A_PARAMETER_TABLE.yaml A-006; M3R_STAGE_B_PARAMETER_TABLE.yaml B-007/008; M6 stackup",
     "skirt WC 0.207", "mm",
     "CMM annular features",
     "WC 0.207 mm band retained; criterion per scheme " + PEND,
     "CRITERION_CANDIDATE_PENDING_WP3",
     "MSR-STR-006; MSR-STR-008", "D05; D06",
     M6 + "/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml", "DESIGN_WC_EVIDENCE_EXISTS__FIT_INSPECTION_HOLD", "W"],
    ["KC-06", "Clocking dowel pair @ local (55.0, 0.0): dia 4.1 clearance (A) vs dia 4.0 x 5.5 blind (B)",
     "M3R_STAGE_A_PARAMETER_TABLE.yaml A-019/020; M3R_STAGE_B_PARAMETER_TABLE.yaml B-019..021",
     "dowel clocking WC 1.8909e-3", "rad",
     "pin gauge + CMM; insertion/removal trial (hardware)",
     "fit class + clocking criterion per " + PEND + " WP3 chains / WP4 schedule",
     "CRITERION_CANDIDATE_PENDING_WP3_WP4",
     "MSR-STR-008", "D05; D06",
     C_WP3_CHAINS + " " + PEND, "CANDIDATE_FEATURE__FIT_HOLD_RETAINED", "W"],
    ["KC-07", "Hinge deployment tip sensitivity",
     M6 + "/wp3_tolerance/HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1.yaml",
     "0.2", "mm/mrad",
     "angular readback + tip displacement measurement (design chain executed M6)",
     "deployment tip error budget per hinge pack " + PEND,
     "CRITERION_CANDIDATE_PENDING_WP5",
     "MSR-MEC-007", "D08",
     C_WP5_HINGE + " " + PEND, "DESIGN_CHAIN_EXECUTED__QUALIFICATION_HOLD", "W"],
    ["KC-08", "Load bridge plate: 160x160 R4, thickness 10.75, 4x dia 6.6 @ (\u00b170,\u00b170), centre dia 40, ligament",
     M6 + "/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml",
     "160 x 160 R4; 10.75; dia 6.6 x4; dia 40; ligament 6.7 nominal", "mm",
     "CMM plate metrology",
     "hole position / flatness per scheme " + PEND + "; ligament is nominal geometry, not a WC margin",
     "CRITERION_CANDIDATE_PENDING_WP3",
     "MSR-STR-006; MSR-INT-011", "D06; D08",
     M6 + "/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml", "CANDIDATE_GEOMETRY__HARDWARE_MEASUREMENT_HOLD", "W"],
    ["KC-09", "Gripper R1 stroke 0\u201371.5 mm internal zero-overlap",
     V5R + "/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json",
     "stroke 71.5; samples 144 @ 0.5; overlap 0", "mm",
     "design: neutral sweep PASS (hash-bound); hardware: stroke metrology + contact witness",
     "hardware criterion per gripper pack " + PEND,
     "DESIGN_PASS__HARDWARE_CRITERION_PENDING_WP5",
     "MSR-MEC-001; MSR-MEC-005", "D07",
     C_WP5_GRIPPER + " " + PEND, "DESIGN_PASS_EVIDENCE__HARDWARE_HOLD", "W"],
    ["KC-10", "B601 as-built screw-end plane preservation x=210.405",
     TERM + "/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml (via M6 schedule)",
     "210.405", "mm",
     "depth micrometer / CMM on assembled joint",
     "end-plane datum retained; tolerance per scheme " + PEND,
     "CRITERION_CANDIDATE_PENDING_WP3",
     "MSR-STR-006; MSR-STR-007", "D05; D08",
     M6 + "/wp6_drawings_bom/INTERFACE_STATION_SCHEDULE_V2.csv", "DESIGN_DEFINED__HARDWARE_MEASUREMENT_HOLD", "W"],
    ["KC-11", "Harness minimum bend radius and keep-out clearance (incl. OD9 static keep-out)",
     "CDR CI-011; WP1 contract",
     PEND + " (routing/bend values owned by WP1)", "mm",
     "template gauges + visual + routing record review",
     "zero prohibited contact over sweep; bend radius >= WP1 value " + PEND,
     "CRITERION_CANDIDATE_PENDING_WP1",
     "MSR-MEC-010", "D07",
     C_WP1_HARNESS + " " + PEND + "; " + C_WP1_KEEPOUT + " " + PEND, "DESIGN_PENDING_SIBLING__MOVING_SWEEP_HOLD", "W"],
    ["KC-12", "Camera mount keep-out conformance and optical axis",
     "CDR CI-012; WP1 contract",
     PEND + " (camera selection HOLD)", "mm",
     "CMM mount metrology + calibration target (hardware)",
     "keep-out conformance per WP1 register " + PEND + "; calibration residual criterion absent (HOLD)",
     "HOLD_NO_AUTHORIZED_CRITERION",
     "MSR-MEC-009", "D07",
     C_WP1_KEEPOUT + " " + PEND, "HOLD__CAMERA_SELECTION_ABSENT", "H"],
    ["KC-13", "Stage A/B axial thicknesses: Stage A 8.0 (2.405+5.595); Stage B 12.0, pocket 5.595, remaining 6.405",
     "M3R_STAGE_A_PARAMETER_TABLE.yaml A-002..004; M3R_STAGE_B_PARAMETER_TABLE.yaml B-003/009/010",
     "8.0; 12.0; 5.595; 6.405", "mm",
     "micrometer / CMM",
     "thickness tolerance per scheme " + PEND,
     "CRITERION_CANDIDATE_PENDING_WP3",
     "MSR-STR-006", "D05; D06",
     "M3R_STAGE_A/B_PARAMETER_TABLE.yaml", "DESIGN_DEFINED__HARDWARE_MEASUREMENT_HOLD", "W"],
    ["KC-14", "Bus +X face flatness and bridge anchor pattern",
     M6 + "/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml (SPACECRAFT_SIDE_ANCHOR_PATTERN_HOLD)",
     "anchor pattern null", "mm",
     "CMM face metrology (hardware)",
     "no criterion \u2014 anchor pattern undefined",
     "HOLD_NO_AUTHORIZED_PATTERN",
     "MSR-INT-011; MSR-STR-004", "D08",
     C_WP1_STRUCT + " " + PEND, "HARD_HOLD_RETAINED", "H"],
]


VM_HEADER = [
    "requirement_id", "family", "configurations", "verification_methods", "owner",
    "cdr_baseline_status", "m7_design_status", "evidence_existing",
    "evidence_m7_contract", "retained_hold", "flight_credit", "prototype_credit",
    "hash_backfill", "notes",
]

_SPEC = CDR + "/01_wp0_requirements/MECHANICAL_SYSTEM_REQUIREMENTS_SPEC_V1.yaml"
_VCD = CDR + "/01_wp0_requirements/MECHANICAL_VERIFICATION_CONTROL_DOCUMENT_V1.csv"
_TRA = CDR + "/01_wp0_requirements/HOLD_TO_REQUIREMENT_TRACEABILITY_V1.csv"
_CIR = CDR + "/01_wp0_requirements/MECHANICAL_CRITICAL_ITEMS_REGISTER_V1.csv"
_TAI = CDR + "/01_wp0_requirements/STANDARDS_TAILORING_MATRIX_V1.csv"
_LED = CDR + "/01_wp0_requirements/STANDARDS_SOURCE_LEDGER_V1.csv"
_GATE = V5R + "/08_gate/V5_OPERATIONAL_MECHANICAL_GATE.json"
_OHR = V5R + "/02_interfaces/OPEN_HOLD_REGISTER.csv"
_CFG = V5R + "/02_interfaces/CONFIGURATION_MATRIX.csv"
_MPT = V5R + "/02_interfaces/MASS_PROPERTIES_TABLE.csv"
_MRL = V5R + "/02_interfaces/MECH_RL_INTERFACE_V1.yaml"
_SFT = V5R + "/02_interfaces/SYSTEM_FRAME_TREE.yaml"
_TLB = V5R + "/02_interfaces/TOP_LEVEL_BOM.csv"
_ICL = V5R + "/02_interfaces/INTERFERENCE_CLASSIFICATION.csv"
_GRV = V5R + "/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json"
_NPV = V5R + "/06_pack_and_go/NEUTRAL_PACKAGE_VALIDATION.json"
_S13 = SIM13 + "/evidence/SIM13_ENVIRONMENT_BOOTSTRAP_GATE.json"
_URDF = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
_ODR = M7 + "/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml"
_PLAN = M7 + "/00_authority/M7_EXECUTION_PLAN_V1.md"
_VM9 = WP9 + "/VERIFICATION_MATRIX_V1.csv"
_BOM3 = WP9 + "/BOM_V3_DESIGN.csv"
_INSP = WP9 + "/INSPECTION_PLAN_V1.csv"
_ICD = WP9 + "/ICD_V3_DRAFT.yaml"
_D05 = WP9 + "/D05_STAGE_A.svg"
_D06 = WP9 + "/D06_STAGE_B.svg"
_D07 = WP9 + "/D07_HARNESS_ROUTING_SCHEMATIC.svg"
_D08 = WP9 + "/D08_ASSEMBLY_STACKUP.svg"

# row helper: (id, cfg, methods, owner, cdr_status, m7_status, ev_existing, ev_m7, retained, proto, notes)
VM_ROWS_RAW = [
    # ---- GOV ----
    ("MSR-GOV-001", "ALL", "I|R", "SYSTEMS_ENGINEERING_OWNER", "CANDIDATE_PASS_DOCUMENT_BOUNDARY",
     "PASS_EVIDENCE", [_SPEC, _TAI], "NONE",
     "NONE", "NO", "YES",
     "M7 keeps the same claim boundary; ODR register adds no ECSS/CDR/flight/qualification claim."),
    ("MSR-GOV-002", "ALL", "I|R", "STANDARDS_AND_CONFIGURATION_OWNER", "HOLD_CONTROLLED_COPIES_AND_CLAUSE_MAPPING",
     "EXTERNAL_HOLD", [_LED, _TAI], "NONE",
     "AUTHORIZED_CONTROLLED_COPIES + AUTHORIZED_TAILORING_RECORD absent", "NO", "LIMITED",
     "External controlled standard copies required; no URL-less compliance review possible."),
    ("MSR-GOV-003", "ALL", "I|R", "OWNER", "PASS_OWNER_TASK_LIST_REPRODUCED",
     "PASS_EVIDENCE", [_SPEC], "NONE",
     "NONE", "NO", "YES",
     "14/14 Owner task IDs reproduced; derived groupings excluded from count."),
    ("MSR-GOV-004", "ALL", "I|R", "CONFIGURATION_MANAGER", "HOLD_APPROVED_CONFIGURATION_MANAGEMENT_PLAN",
     "EXTERNAL_HOLD", [_VCD, _TRA], _ODR + " (hash discipline precedent)",
     "APPROVED_CONFIGURATION_MANAGEMENT_PLAN absent", "NO", "YES",
     "M7 artifacts are hash-pinned via source_register; the owner-approved CM plan remains an external input."),
    ("MSR-GOV-005", "ALL", "I|R", "PRODUCT_ASSURANCE_OWNER", "OPEN_HOLDS_TRACED_NOT_CLOSED",
     "PASS_EVIDENCE", [_TRA], _ODR,
     "out-of-scope HOLDs remain open and traced in this matrix", "NO", "LIMITED",
     "ODR-01..06 are owner-ruling closure records for in-scope HOLDs only; zero HOLDs closed by document creation alone."),
    ("MSR-GOV-006", "ALL", "I|R", "VERIFICATION_LEAD", "CANDIDATE_PASS_WP0_STRUCTURE_ONLY",
     "PASS_EVIDENCE", [_VCD], _VM9,
     "NONE", "NO", "YES",
     "Method/config/criterion/evidence/owner mapping complete; this matrix carries the M7 extension."),
    # ---- OPS ----
    ("MSR-OPS-001", "LAUNCH_STOWED", "A|I|T|R", "MECHANICAL_LEAD", "HOLD_HISTORICAL_ENVELOPE_EXCEEDANCE_132P72_MM",
     "EXTERNAL_HOLD", [_GATE], "NONE",
     "LAUNCHER_ICD_ENVELOPE; LAUNCH_LOADS; OWNER_DISPOSITION_132P72_MM", "NO", "NO",
     "No launcher ICD; historical 132.72 mm envelope exceedance undispositioned. Gate B scope."),
    ("MSR-OPS-002", "SEPARATION", "A|I|T|R", "SYSTEM_INTERFACE_OWNER", "HOLD_UNKNOWN_NO_ICD",
     "EXTERNAL_HOLD", [_TRA], "NONE",
     "SPACECRAFT_LAUNCHER_ICD; SEPARATION_LOADS; RELEASED_BODY_GEOMETRY", "NO", "NO",
     "No spacecraft-launcher ICD exists."),
    ("MSR-OPS-003", "POST_SEPARATION_SAFE", "A|D|R", "SYSTEMS_ENGINEERING_OWNER", "HOLD_REQUIREMENTS_NOT_AUTHORIZED",
     "EXTERNAL_HOLD", [_TRA], "NONE",
     "AUTHORIZED_POST_SEPARATION_SAFE_REQUIREMENTS absent", "NO", "NO",
     "Owner-authorized state constraints do not exist."),
    ("MSR-OPS-004", "SOLAR_ARRAY_DEPLOYMENT|DEPLOYED_NOMINAL", "A|T|D|R", "MECHANISMS_LEAD", "HOLD_MECHANISM_QUALIFICATION",
     "TEST_REQUIRED_HOLD", [_TRA], C_WP5_HINGE + " " + PEND + "; " + C_WP8_ENV + " " + PEND,
     "mechanism qualification test; authorized deployment loads/life/environment", "NO", "NO",
     "M7 WP5 hinge pack + WP8 thermal envelope are design analysis only; deployment qualification test remains."),
    ("MSR-OPS-005", "ARM_RELEASE", "A|T|D|R", "MECHANISMS_LEAD", "HOLD_HDRM_RELIABILITY",
     "TEST_REQUIRED_HOLD", [_GATE], C_WP5_HDRM + " " + PEND,
     "HDRM_PRODUCT_SELECTION; RELIABILITY_TARGET; release shock/clearance test", "NO", "NO",
     "WP5 HDRM engineering pack is design analysis; product selection and release test remain HOLD."),
    ("MSR-OPS-006", "ARM_TASK_READY", "I|D|R", "CAD_CONFIGURATION_OWNER", "ACCEPTED_SEMANTIC_ENUM_ONLY_GEOMETRIC_READBACK_HOLD",
     "ANALYTIC_CLOSED", [_CFG], C_WP1_STRUCT + " " + PEND + "; " + C_WP1_ASSY_STEP + " " + PEND + "; " + C_WP2_MASS + " " + PEND,
     "hardware demonstration and flight credit remain NO", "NO", "LIMITED",
     "Design-level activation/readback on neutral authority (ODR-03); readback records pending WP1 hash backfill at integration."),
    ("MSR-OPS-007", "ARM_MANEUVER", "A|T|D|R", "ROBOTICS_MECHANICAL_OWNER", "DERIVED_SIMULATION_EXISTS_MECHANICAL_LOAD_AUTHORITY_HOLD",
     "ANALYTIC_CLOSED", ["OWNER_TASK_STATUS_20260821", _S13], C_WP7_EVID + " " + PEND + "; " + C_WP1_HARNESS + " " + PEND + "; " + C_WP1_KEEPOUT + " " + PEND,
     "hardware trajectory test for flight; launch environments EXTERNAL (MSR-STR-003)", "NO", "NO",
     "Arm-maneuver operational FEA authorized by ODR-06; joint-load authority design-level via WP7 contract; harness sweep via WP1 contract."),
    ("MSR-OPS-008", "PREGRASP|GRIPPER_PREGRASP", "A|I|D|R", "GRIPPER_OWNER", "ACCEPTED_SEMANTIC_ENUM_AND_NEUTRAL_R1_GEOMETRY_PASS_HARDWARE_CONTACT_HOLD",
     "TEST_REQUIRED_HOLD", [_GRV], C_WP5_GRIPPER + " " + PEND,
     "CONTACT_DATUM_METROLOGY; APPROACH_CORRIDOR authority; target geometry", "NO", "LIMITED",
     "Neutral R1 geometry PASS stands; hardware contact datums unmeasured."),
    ("MSR-OPS-009", "CAPTURE|GRIPPER_PARTIAL|GRIPPER_CLOSED", "A|T|D|R", "GRIPPER_OWNER", "DERIVED_SIMULATION_ONLY_STRUCTURAL_CONTACT_LOAD_HOLD",
     "TEST_REQUIRED_HOLD", ["OWNER_TASK_STATUS_20260821", _S13], C_WP7_DECKS + " " + PEND + "; " + C_WP5_GRIPPER + " " + PEND,
     "representative capture test; CONTACT_FRICTION_AUTHORITY; MATERIAL_ALLOWABLES", "NO", "NO",
     "22 kg / 150 kg capture FEA decks authorized by ODR-06 (design-level); impulses DERIVED research-bound, not authorized loads."),
    ("MSR-OPS-010", "POST_CAPTURE_STABILIZATION", "A|T|D|R", "ROBOTICS_MECHANICAL_OWNER", "DERIVED_SIMULATION_ONLY_QUALIFICATION_HOLD",
     "TEST_REQUIRED_HOLD", ["OWNER_TASK_STATUS_20260821"], C_WP2_MASS + " " + PEND + "; " + C_WP10_IF + " " + PEND,
     "STABILITY_DEFINITION; measured/validated dynamic response", "NO", "NO",
     "Simulation-derived only; no measured response exists."),
    ("MSR-OPS-011", "SAFE_MODE", "A|D|R", "SYSTEM_SAFETY_OWNER", "SIM13_UNKNOWN_FAIL_CLOSED_MECHANICAL_REQUIREMENTS_HOLD",
     "EXTERNAL_HOLD", [_S13], "NONE",
     "SAFE_MODE_MECHANICAL_REQUIREMENTS authorization absent", "NO", "LIMITED",
     "SIM13 fail-closed bootstrap noted; mechanical safe-mode requirements not authorized."),
    ("MSR-OPS-012", "LEFT_PANEL_FAIL", "A|I|D|R", "MECHANICAL_LEAD", "ACCEPTED_SEMANTIC_ENUM_ONLY_PER_CONFIG_GEOMETRY_AND_LOAD_HOLD",
     "ANALYTIC_CLOSED", [_CFG], C_WP1_STRUCT + " " + PEND + "; " + C_WP2_MASS + " " + PEND + "; " + C_WP7_DECKS + " " + PEND,
     "flight load test; per-config hardware interference demo", "NO", "LIMITED",
     "ODR-02 attached-stuck semantics; nine-config design mass model + panel-failure FEA deck cover design level; WP1 interference records pending hash."),
    ("MSR-OPS-013", "RIGHT_PANEL_FAIL", "A|I|D|R", "MECHANICAL_LEAD", "ACCEPTED_SEMANTIC_ENUM_ONLY_PER_CONFIG_GEOMETRY_AND_LOAD_HOLD",
     "ANALYTIC_CLOSED", [_CFG], C_WP1_STRUCT + " " + PEND + "; " + C_WP2_MASS + " " + PEND + "; " + C_WP7_DECKS + " " + PEND,
     "flight load test; per-config hardware interference demo", "NO", "LIMITED",
     "Same basis as MSR-OPS-012."),
    ("MSR-OPS-014", "BOTH_PANEL_FAIL", "A|I|D|R", "MECHANICAL_LEAD", "ACCEPTED_SEMANTIC_ENUM_ONLY_PER_CONFIG_GEOMETRY_AND_LOAD_HOLD",
     "ANALYTIC_CLOSED", [_CFG], C_WP1_STRUCT + " " + PEND + "; " + C_WP2_MASS + " " + PEND + "; " + C_WP7_DECKS + " " + PEND,
     "flight load test; per-config hardware interference demo", "NO", "LIMITED",
     "Same basis as MSR-OPS-012."),
    # ---- STR ----
    ("MSR-STR-001", "ALL_B601_SIMULATION_CONFIGURATIONS", "I|R", "ROBOTICS_MODEL_OWNER", "PASS_SIMULATION_INTERFACE_ONLY_PHYSICAL_MASS_HOLD",
     "PASS_EVIDENCE", [_URDF, _MRL], _ODR,
     "physical mass reconciliation (see MSR-STR-002)", "NO", "YES",
     "L0 URDF SHA-256 re-verified this loop (see receipt.json l0_urdf_sha256_check); 4.695555949342986 kg never overridden."),
    ("MSR-STR-002", "ALL", "A|I|T|R", "MASS_PROPERTIES_OWNER", "HOLD_PHYSICAL_MASS_AND_INERTIA_RECONCILIATION",
     "EXTERNAL_HOLD", [_MPT], C_WP2_MASS + " " + PEND + " (design-level partial)",
     "AS_BUILT_MASS_MEASUREMENT; M3R as-built open (ODR-05 retained)", "NO", "NO",
     "WP2 design mass model is DESIGN class; as-built hardware reconciliation is an external measurement input."),
    ("MSR-STR-003", "ALL_LOAD_CASES", "A|R", "STRUCTURAL_DYNAMICS_OWNER", "HOLD_LOAD_AND_ENVIRONMENT_AUTHORITY",
     "EXTERNAL_HOLD", [_TAI], "NONE",
     "LAUNCHER_ICD; MISSION_ENVIRONMENT; authorized loads spec", "NO", "NO",
     "CDR operational loads (19 families / 21 cases / 13 combinations; capture impulses) are DERIVED research-bound, not an authorized loads spec."),
    ("MSR-STR-004", "ALL_LOAD_CASES", "A|T|R", "STRESS_LEAD", "HOLD_ALLOWABLES_FACTORS_LOADS_AND_ANALYSIS",
     "TEST_REQUIRED_HOLD", [_VCD], C_WP7_EVID + " " + PEND + "; " + C_WP7_RESULTS + " " + PEND,
     "MATERIAL_ALLOWABLES + FACTORS_OF_SAFETY (also external); flight load test; LAUNCH_QUALIFICATION_FEA_HOLD (ODR-06 retained)", "NO", "NO",
     "WP7 operational FEA covers ODR-06 cases at design level only; no flight margin credit."),
    ("MSR-STR-005", "M3R_REV_B2", "A|I|T|R", "M3R_OWNER", "HOLD_M3R_MASS_RECONCILIATION",
     "ANALYTIC_CLOSED", [TERM + "/03_native_cad/M3_interface_authority/M3R_ADAPTER_BOM_CANDIDATE.csv", "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/08_bom/V5_NATIVE_BOM_SEED.csv"],
     _ODR + "#ODR-05; " + C_WP2_MASS + " " + PEND + "; " + _BOM3,
     "M3R_AS_BUILT_MEASUREMENT_OPEN (ODR-05 retained)", "NO", "NO",
     "0.7619 kg DESIGN_BUDGET conf B is the single design authority; replaces 761.904197 g legacy and 782.327248 g provisional CAD-density values at design level."),
    ("MSR-STR-006", "M3R_REV_B2", "I|R", "M3R_OWNER", "HOLD_RELEASED_DATUM_AND_TOLERANCE_AUTHORITY",
     "ANALYTIC_CLOSED", [_GATE], C_WP3_SCHEME + " " + PEND + "; " + C_WP1_STRUCT + " " + PEND + "; " + _D05 + "; " + _D06 + "; " + _INSP + "#KC-01",
     "hardware datum inspection; owner drawing release signature", "NO", "LIMITED",
     "Stage A+B architecture and datums preserved on D05/D06; PCD 90.509642 / clocking 25.000014 deg reconciled; non-continuous mounting face retained."),
    ("MSR-STR-007", "M3R_REV_B2|ALL_LOAD_CASES", "A|I|T|R", "JOINTS_AND_FASTENERS_OWNER", "HOLD_M3R_FASTENER_MOS_AND_PRELOAD",
     "ANALYTIC_CLOSED", [_OHR], C_WP4_M3R + " " + PEND + "; " + C_WP4_TORQUE + " " + PEND + "; " + C_WP4_CHECKS + " " + PEND,
     "owner-authorized margin criteria absent; joint test for flight", "NO", "NO",
     "WP4 delivers design fastener spec + analytic checks with declared candidate factors; margins computed against candidate-class allowables only."),
    ("MSR-STR-008", "M3R_REV_B2", "A|I|T|R", "M3R_OWNER", "HOLD_M3R_LOCATING_DOWEL_FIT",
     "TEST_REQUIRED_HOLD", [_OHR], C_WP3_CHAINS + " " + PEND + "; " + _INSP + "#KC-06",
     "representative fit inspection; dowel spec release (diameter/material/fit/insertion/removal)", "NO", "NO",
     "M6 WC clocking 1.8909e-3 rad is design evidence; representative hardware fit inspection remains."),
    ("MSR-STR-009", "QUALIFICATION_CONFIGURATION|FLIGHT_CONFIGURATION", "A|I|T|R", "QUALIFICATION_LEAD", "HOLD_FLIGHT_STRUCTURE_QUALIFICATION",
     "EXTERNAL_HOLD", [_GATE], "NONE",
     "MODEL_PHILOSOPHY; TEST_LEVELS; qualification program; launcher ICD", "NO", "NOT_APPLICABLE",
     "Gate B scope; no qualification article or authorized test program exists."),
    # ---- MEC ----
    ("MSR-MEC-001", "GRIPPER_CLOSED|GRIPPER_PARTIAL|GRIPPER_PREGRASP|GRIPPER_OPEN", "A|I|R", "GRIPPER_OWNER", "PASS_NEUTRAL_R1_INTERNAL_SWEEP_ONLY",
     "PASS_EVIDENCE", [_GRV], _ODR + "#ODR-04",
     "flight credit NO; scope limited to internal sweep", "NO", "YES_LIMITED",
     "144 samples @ 0.5 mm over 0\u201371.5 mm, zero overlap, hash-bound R1 assets; ODR-04 supersedes the 36 legacy native findings."),
    ("MSR-MEC-002", "ALL_GRIPPER_CONFIGURATIONS", "I|D|R", "CAD_CONFIGURATION_OWNER", "HOLD_NATIVE_V5_GRIPPER_R1_REINTEGRATION",
     "EXTERNAL_HOLD", [_GATE], _ODR + "#ODR-03/ODR-04 (supersession recorded)",
     "NATIVE_R1_REINTEGRATION (permanent unless owner re-authorizes native line)", "NO", "NO",
     "Native line permanently off critical path (ODR-03); neutral R1 authority passes continuous stroke (ODR-04); no native credit claimed."),
    ("MSR-MEC-003", "ALL_GRIPPER_CONFIGURATIONS", "A|I|T|R", "GRIPPER_OWNER", "HOLD_GRIPPER_MANUFACTURING_CLEARANCE",
     "EXTERNAL_HOLD", [_OHR], C_WP3_CHAINS + " " + PEND + "; " + C_WP8_ENV + " " + PEND + " (design support)",
     "MINIMUM_CLEARANCE_REQUIREMENT (owner-authorized value absent); wear/contamination allowance", "NO", "NO",
     "WP3/WP8 supply WC + thermal sensitivity analysis; the authorized clearance limit is an external owner input."),
    ("MSR-MEC-004", "ALL_GRIPPER_CONFIGURATIONS", "A|I|R", "GRIPPER_OWNER", "HOLD_GRIPPER_MINIMUM_WALL_THICKNESS",
     "EXTERNAL_HOLD", [_GATE], C_WP5_GRIPPER + " " + PEND + " (design support)",
     "MINIMUM_WALL_REQUIREMENT authorized value; R1 metrology", "NO", "NO",
     "No owner-authorized minimum wall value exists."),
    ("MSR-MEC-005", "PREGRASP|CAPTURE|POST_CAPTURE_STABILIZATION|SAFE_MODE", "A|T|R", "GRIPPER_OWNER", "HOLD_GRIPPER_STRUCTURAL_STRENGTH",
     "TEST_REQUIRED_HOLD", [_OHR], C_WP5_GRIPPER + " " + PEND + "; " + C_WP7_DECKS + " " + PEND,
     "allowables; strength/stiffness/fatigue/life test", "NO", "NO",
     "Gripper-clamp FEA deck authorized by ODR-06 at design level; life and strength tests remain."),
    ("MSR-MEC-006", "PREGRASP|CAPTURE|POST_CAPTURE_STABILIZATION", "A|T|D|R", "GRIPPER_OWNER", "HOLD_GRIPPER_EXTERNAL_OBJECT_CONTACT_VALIDATION",
     "TEST_REQUIRED_HOLD", [_MRL, _S13], "NONE",
     "contact friction/compliance authority; target metrology; representative contact test", "NO", "NO",
     "Target proxies are scenario references (BOM V3 SCN rows); no contact authority."),
    ("MSR-MEC-007", "LAUNCH_STOWED|SOLAR_ARRAY_DEPLOYMENT|DEPLOYED_NOMINAL|LEFT_PANEL_FAIL|RIGHT_PANEL_FAIL|BOTH_PANEL_FAIL", "A|I|T|D|R", "SOLAR_ARRAY_MECHANISMS_OWNER", "HOLD_SOLAR_ARRAY_MECHANISM_QUALIFICATION",
     "TEST_REQUIRED_HOLD", ["OWNER_TASK_STATUS_20260821"], C_WP5_HINGE + " " + PEND + "; " + _INSP + "#KC-07",
     "mechanism qualification test; product selections; life/environment evidence", "NO", "NO",
     "Hinge tip sensitivity 0.2 mm/mrad chain executed in M6 (design); qualification test remains."),
    ("MSR-MEC-008", "LAUNCH_STOWED|SOLAR_ARRAY_DEPLOYMENT|ARM_RELEASE", "I|T|D|R", "MECHANISMS_LEAD", "HOLD_HDRM_RELIABILITY",
     "TEST_REQUIRED_HOLD", [_OHR], C_WP5_HDRM + " " + PEND,
     "HDRM product selection approval; release reliability/shock test evidence", "NO", "NO",
     "WP5 pack is engineering analysis; traceable test evidence absent."),
    ("MSR-MEC-009", "ARM_TASK_READY|ARM_MANEUVER|PREGRASP|CAPTURE", "A|I|T|R", "VISION_HARDWARE_OWNER", "HOLD_CAMERA_SELECTION_AND_CALIBRATION",
     "EXTERNAL_HOLD", [_MRL], C_WP1_KEEPOUT + " " + PEND + "; " + C_WP1_SUPPORT + " " + PEND + " (design support)",
     "CAMERA_SELECTION; mount drawing; hand-eye calibration criterion", "NO", "NO",
     "Rejected candidate pose penetrated M3R; no replacement authorized; WP1 provides keep-out/support candidates only."),
    ("MSR-MEC-010", "SOLAR_ARRAY_DEPLOYMENT|ARM_RELEASE|ARM_MANEUVER|PREGRASP|CAPTURE", "A|I|T|D|R", "HARNESS_MECHANICAL_OWNER", "HOLD_HARNESS_MOVING_SWEEP",
     "ANALYTIC_CLOSED", [_OHR], C_WP1_HARNESS + " " + PEND + "; " + C_WP1_KEEPOUT + " " + PEND + "; " + _D07,
     "wear / service-life / connector qualification test", "NO", "NO",
     "Design-level routing + sweep clearance via WP1 contract (D07 is schematic only); life criteria remain test-side."),
    # ---- INT ----
    ("MSR-INT-001", "DONOR_BASELINE", "I|R", "OWNER", "ACCEPTED_EXCEPTION_SCOPE_ONLY",
     "PASS_EVIDENCE", [_GATE], "NONE",
     "exception must never be reported as composite zero", "NO", "YES_LIMITED",
     "81 donor static rows preserved as signed scoped exception; WP9 artifacts do not launder them into any zero count."),
    ("MSR-INT-002", "DEPLOYED_NOMINAL_MAIN_NEUTRAL_ONLY", "I|R", "MECHANICAL_INTEGRATION_OWNER", "PASS_HASH_BOUND_MAIN_NEUTRAL_ONLY",
     "PASS_EVIDENCE", [_ICL], "NONE",
     "scope excludes all addenda and other configurations", "NO", "YES_LIMITED",
     "Historical zero result stays bound to the hash-identical main neutral geometry."),
    ("MSR-INT-003", "DEPLOYED_NOMINAL_COMPOSITE|ALL_RELEVANT_CONFIGURATIONS", "A|I|D|R", "MECHANICAL_INTEGRATION_OWNER", "HOLD_COMPOSITE_ADDENDA_PLACEMENT_AND_NARROW_PHASE",
     "ANALYTIC_CLOSED", [_GATE], C_WP1_ASSY_STEP + " " + PEND + "; " + C_WP1_STRUCT + " " + PEND,
     "reverts to HOLD if WP1 narrow-phase records absent at integration", "NO", "NO",
     "WP1 design-freeze assembly is the composite placement vehicle; narrow-phase verification records pending WP1 hash backfill."),
    ("MSR-INT-004", "ALL", "I|R", "CAD_CONFIGURATION_OWNER", "HOLD_MONOLITHIC_NEUTRAL_INTEGRATION",
     "ANALYTIC_CLOSED", [_OHR], C_WP1_ASSY_FCSTD + "/" + "step " + PEND + "; " + C_WP1_STRUCT + " " + PEND,
     "validation receipt acceptance at integration", "NO", "LIMITED",
     "WP1 integrated neutral assembly + PRODUCT_STRUCTURE occurrence manifest answer the monolithic-integration hold at design level (ODR-03 authority)."),
    ("MSR-INT-005", "ALL_NATIVE_CONFIGURATIONS", "I|D|R", "CAD_CONFIGURATION_OWNER", "HOLD_NATIVE_TOP_ASSEMBLY",
     "EXTERNAL_HOLD", [_GATE], _ODR + "#ODR-03",
     "NATIVE_REINTEGRATION_HOLD (permanent unless owner re-authorizes)", "NO", "NO",
     "SolidWorks native line permanently off critical path; neutral FreeCAD/STEP chain is the system geometry authority."),
    ("MSR-INT-006", "ALL_NATIVE_CONFIGURATIONS", "I|D|R", "CAD_CONFIGURATION_OWNER", "HOLD_LIGHTWEIGHT_SLDASM_NATIVE_VALIDATION",
     "EXTERNAL_HOLD", [_GATE], _ODR + "#ODR-03",
     "NATIVE_REINTEGRATION_HOLD (permanent unless owner re-authorizes)", "NO", "NO",
     "Same basis as MSR-INT-005."),
    ("MSR-INT-007", "DEPLOYED_NOMINAL|LEFT_PANEL_FAIL|RIGHT_PANEL_FAIL|BOTH_PANEL_FAIL|ARM_STOWED_ONORBIT|ARM_TASK_READY|GRIPPER_CLOSED|GRIPPER_PARTIAL|GRIPPER_PREGRASP|GRIPPER_OPEN", "I|D|R", "CAD_CONFIGURATION_OWNER", "HOLD_CONFIGURATION_NATIVE_READBACK",
     "ANALYTIC_CLOSED", [_CFG], C_WP1_STRUCT + " " + PEND + "; " + C_WP2_MASS + " " + PEND,
     "hardware readback for flight; native readback superseded by neutral authority (ODR-03)", "NO", "LIMITED",
     "10 semantic configurations realized on the neutral chain; nine-config design mass model via WP2; readback records pending sibling hashes."),
    ("MSR-INT-008", "ALL_10_ACCEPTED_SEMANTIC_CONFIGURATIONS", "A|I|R", "MECHANICAL_INTEGRATION_OWNER", "HOLD_PER_CONFIGURATION_BOUNDING_BOX",
     "ANALYTIC_CLOSED", [_CFG], C_WP1_ASSY_STEP + " " + PEND + "; " + C_WP2_MASS + " " + PEND,
     "flagged for Gate A review: no dedicated bbox contract output", "NO", "NO",
     "Bounding boxes measurable on WP1 design-freeze assembly at integration; flagged because no contract output pins them."),
    ("MSR-INT-009", "ALL_10_ACCEPTED_SEMANTIC_CONFIGURATIONS|APPROVED_TRANSITION_SWEEPS", "A|D|R", "MECHANICAL_INTEGRATION_OWNER", "HOLD_PER_CONFIGURATION_EXTERNAL_INTERFERENCE",
     "ANALYTIC_CLOSED", [_GATE], C_WP1_KEEPOUT + " " + PEND + "; " + C_WP1_ASSY_STEP + " " + PEND,
     "reverts to HOLD if WP1 per-config/sweep evidence absent at integration", "NO", "NO",
     "WP1 keep-out register + design-freeze assembly carry the design-level checks; continuous-sweep records pending WP1 hash backfill."),
    ("MSR-INT-010", "ALL", "I|T|R", "SYSTEM_INTERFACE_OWNER", "HOLD_ROOT_TO_M_FRAME_NOT_REASSERTED_BY_NEUTRAL_PACKAGE",
     "ANALYTIC_CLOSED", [_SFT], _ODR + "#ODR-01; " + C_WP1_ASSY_STEP + " " + PEND + "; " + _D08 + "; " + _ICD,
     "metrology for flight credit", "NO", "NO",
     "ODR-01: T_SM=[185.25,0,0] mm + Ry(90 deg) is the single root-to-M authority; stations 198.0/208.0/210.405 are a feature stack, never a second dynamics frame."),
    ("MSR-INT-011", "M3R_REV_B2", "I|T|D|R", "M3R_OWNER", "HOLD_M3R_PHYSICAL_FITUP",
     "TEST_REQUIRED_HOLD", [_MRL], C_WP4_M3R + " " + PEND + " (tool-access design)",
     "representative hardware fitup; tool access demonstration; minimum access clearances", "NO", "NO",
     "No representative hardware exists; tool-access envelopes designed in WP4 contract."),
    ("MSR-INT-012", "APPROVED_EXCHANGE_CONFIGURATION", "I|D|R", "CAD_CONFIGURATION_OWNER", "HOLD_PARASOLID_EXPORT_NOT_PRODUCED",
     "EXTERNAL_HOLD", [_OHR], "NONE",
     "OWNER_PARASOLID_REQUIREMENT decision (conditional)", "NO", "NO",
     "Conditional hold: activates only if the owner requires Parasolid exchange."),
    # ---- MAT ----
    ("MSR-MAT-001", "ALL_PHYSICAL_HARDWARE", "I|R", "MATERIALS_AND_PROCESSES_OWNER", "HOLD_MATERIAL_AND_PROCESS_AUTHORITY",
     "EXTERNAL_HOLD", [_TLB], C_WP6_MAT + " " + PEND + "; " + C_WP6_PROC + " " + PEND + "; " + _BOM3 + " (design-level partial)",
     "PROCUREMENT_RECORDS; supplier/lot traceability; released-BOM status", "NO", "NO",
     "BOM V3 binds DESIGN_APPROVED selections pending WP6 hash; traceable supplier/lot records are external procurement inputs."),
    ("MSR-MAT-002", "ALL_LOAD_CASES", "A|I|T|R", "MATERIALS_AND_PROCESSES_OWNER", "HOLD_MATERIAL_ALLOWABLES",
     "EXTERNAL_HOLD", [_TAI], "NONE",
     "APPROVED_ALLOWABLES_DATABASE absent", "NO", "NO",
     "WP4/WP7 use candidate-class properties with declared limits; no flight margin credit derivable."),
    ("MSR-MAT-003", "ALL_PHYSICAL_HARDWARE", "I|T|R", "MATERIALS_AND_PROCESSES_OWNER", "HOLD_MANUFACTURING_RELEASE",
     "EXTERNAL_HOLD", [_CIR], C_WP6_PROC + " " + PEND + " (design-level partial)",
     "approved materials/process/parts list; qualification records; manufacturing release not claimed", "NO", "NO",
     "No manufacturing release is claimed anywhere in M7."),
    ("MSR-MAT-004", "MANUFACTURE|ASSEMBLY|TEST|STORAGE|LAUNCH|OPERATION", "A|I|T|R", "PRODUCT_ASSURANCE_OWNER", "HOLD_CLEANLINESS_AND_CONTAMINATION_INPUTS",
     "EXTERNAL_HOLD", [_TAI], "NONE",
     "MISSION_CONTAMINATION_LIMITS; sensitive item list; cleanliness control plan", "NO", "NO",
     "No mission contamination limits exist."),
    ("MSR-MAT-005", "QUALIFICATION_ARTICLE|ACCEPTANCE_ARTICLE", "T|R", "TEST_AND_VERIFICATION_LEAD", "HOLD_THERMAL_TEST_INPUTS",
     "TEST_REQUIRED_HOLD", [_TAI], C_WP8_SENS + " " + PEND + " (design sensitivity only)",
     "authorized thermal test specification; test article", "NO", "NO",
     "WP8 gives thermo-elastic sensitivity envelopes (analysis); no thermal-vacuum/cycling test exists."),
    # ---- VER ----
    ("MSR-VER-001", "ALL", "I|R", "VERIFICATION_LEAD", "CANDIDATE_PASS_WP0_MAPPING_ONLY_PROGRAM_HOLD",
     "ANALYTIC_CLOSED", [_VCD], _VM9,
     "AUTHORIZED_VERIFICATION_PLAN remains an owner-level input (noted, not claimed)", "NO", "YES",
     "VCD 62/62 mapping carried; this matrix extends each row with M7 evidence and honest status; program authorization not claimed."),
    ("MSR-VER-002", "QUALIFICATION_CONFIGURATION|ACCEPTANCE_CONFIGURATION|PROTOFLIGHT_CONFIGURATION", "I|R", "TEST_AND_VERIFICATION_LEAD", "HOLD_TEST_LEVELS_AND_MODEL_PHILOSOPHY_AUTHORIZATION",
     "EXTERNAL_HOLD", [_TAI], "NONE",
     "MISSION_ENVIRONMENTS; MODEL_PHILOSOPHY; TEST_LEVELS authorization", "NO", "NO",
     "No signed model philosophy or test specification exists."),
    ("MSR-VER-003", "QUALIFICATION_ARTICLE|ACCEPTANCE_ARTICLE|FLIGHT_CONFIGURATION", "I|T|R", "PRODUCT_ASSURANCE_OWNER", "HOLD_QUALIFICATION_AND_ACCEPTANCE_EVIDENCE",
     "TEST_REQUIRED_HOLD", [_TRA], "NONE",
     "test reports; configuration records; NCR/anomaly dispositions", "NO", "NO",
     "No qualification or acceptance test evidence exists."),
    ("MSR-VER-004", "ALL_LIFECYCLE_STATES", "A|I|R", "DEPENDABILITY_OWNER", "CANDIDATE_CRITICAL_ITEM_REGISTER_ONLY_FMEA_HOLD",
     "ANALYTIC_CLOSED", [_CIR], _VM9,
     "AUTHORIZED_FMEA_SCOPE (formal FMEA/FMECA HOLD retained)", "NO", "LIMITED",
     "Critical-items screening register carried into M7 mapping; formal FMEA completion not claimed."),
    ("MSR-VER-005", "NEUTRAL_PACKAGE", "I|D|R", "CONFIGURATION_MANAGER", "PASS_RAPID_PACKAGE_ONLY_NOT_DESIGN_QUALIFICATION",
     "PASS_EVIDENCE", [_NPV, _GATE], "NONE",
     "not creditable for flight qualification", "NO", "YES_LIMITED",
     "Neutral package validation passed with zero missing/zero-byte/mismatch/unexpected; evidence-class labels preserved."),
    ("MSR-VER-006", "SIM13_BOOTSTRAP|ARM_MANEUVER|PREGRASP|CAPTURE|POST_CAPTURE_STABILIZATION", "A|I|T|D|R", "ROBOTICS_VERIFICATION_OWNER", "HOLD_CONTACT_FIDELITY_FLEXIBLE_BODY_TRAINING_HIL_AND_REAL_ROBOT",
     "TEST_REQUIRED_HOLD", [_S13], C_WP10_IF + " " + PEND + " (interface design only)",
     "contact/flexible-body/training/HIL/real-robot authorized gates", "NO", "BOOTSTRAP_ONLY",
     "WP10 upgrades the dynamics/RL interface design; higher-fidelity and real-hardware gates stay closed."),
]


def vm_rows():
    rows = []
    for (rid, cfg, meth, owner, cdr_st, m7_st, ev_e, ev_m7, retained, flight, proto, note) in VM_ROWS_RAW:
        fam = rid.split("-")[1]
        ev_existing = " | ".join(ev_e)
        if ev_m7 == "NONE":
            evm7 = "NONE"
            hb = "NOT_APPLICABLE"
        else:
            evm7 = ev_m7
            hb = PEND + " where M7 contract paths are cited"
        rows.append([rid, fam, cfg, meth, owner, cdr_st, m7_st, ev_existing, evm7,
                     retained, flight, proto, hb, note])
    return rows


def build_icd():
    return f"""schema: M7_WP9_ICD_V3_DRAFT
generated_local: '{GEN_LOCAL}'
title: Mechanical Interface Control Document V3 (DRAFT)
document_status: DRAFT_DESIGN_LEVEL_NOT_RELEASED
work_package: WP9_RELEASE_PACKAGE
claim_boundary: >-
  Design-level interface control draft for the M7 engineering release package.
  No manufacturing, procurement, launch, flight, or qualification authority is
  created or claimed. Candidate values are never promoted to released values;
  unknowns stay null + HOLD. Sibling M7 references are contract paths from
  M7_EXECUTION_PLAN_V1.md with hashes PENDING_SIBLING_HASH until the
  integration stage backfills 12_release/M7_CROSS_WP_REFERENCE_RECONCILIATION_V1.json.
frame_authority:
  ruling: ODR-01
  root_to_m_frame: 'T_SM = [185.25, 0, 0] mm followed by Ry(90 deg)'
  note: >-
    Feature stations 198.0 (plate outer face), 208.0 (physical mounting face)
    and 210.405 mm (screw end faces) are a geometric feature stack and never a
    second dynamics frame definition.
units: {{length: mm, angle: deg, mass: kg}}

interfaces:
  - interface_id: IF-01_M3R_ARM_SIDE
    name: B601 arm base to M3R Stage A
    status: DESIGN_DRAFT
    mating_parts: [B601 base plate (as-built), M3R_STAGE_A_INTERFACE_RING_REVB_WORKING]
    geometry:
      pattern: 4x M4-class (HM4-75) on 64 x 64 mm square, clocked 25.000014 deg
      pcd_mm: 90.509642
      pattern_centre_yz_mm: [0.015994151, -0.086366070]
      stage_a_od_mm: 150.0
      stage_a_thickness_mm: 8.0   # 2.405 proud + 5.595 recessed
      central_passage_dia_mm: 40.0
      clearance_hole_dia_mm: 4.6
      counterbore_dia_x_depth_mm: [7.5, 4.5]
      stations_mm: {{install_face: 208.0, screw_end_plane: 210.405}}
    sources:
      - {M3DD}/06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml
      - {TERM}/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml
    design_bindings:
      fasteners: PENDING_SIBLING_HASH {C_WP4_M3R}
      torque_preload: PENDING_SIBLING_HASH {C_WP4_TORQUE}
      tolerances: PENDING_SIBLING_HASH {C_WP3_SCHEME}
      drawing: {WP9}/D05_STAGE_A.svg
    retained_holds: [B601_PHYSICAL_FITUP_HOLD, FASTENER_MARGIN_CRITERIA_EXTERNAL, HARDWARE_DATUM_INSPECTION_HOLD]

  - interface_id: IF-02_M3R_INTERSTAGE
    name: M3R Stage A to Stage B
    status: DESIGN_DRAFT
    mating_parts: [M3R_STAGE_A_INTERFACE_RING_REVB_WORKING, M3R_STAGE_B_LOAD_ADAPTER_REVB2_WORKING]
    geometry:
      interstage_pattern: 8x dia 5.5 mm M5-class clearance @ R62.5 mm, start 22.5 deg
      spigot_dia_mm: 99.6
      skirt_inner_dia_mm: 100.6
      pocket_od_x_id_x_depth_mm: [150.4, 100.0, 5.595]
      clocking_dowel_candidate: {{clearance_dia_mm: 4.1, blind_dia_x_depth_mm: [4.0, 5.5], centre_xy_mm: [55.0, 0.0]}}
      wc_evidence: {{spigot_mm: 0.206, skirt_mm: 0.207, dowel_clocking_rad: 1.8909e-3}}
    sources:
      - {M3DD}/06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml
      - {M3DD}/06_parameterized_parts/m3r/M3R_STAGE_B_PARAMETER_TABLE.yaml
      - {M6}/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml
    design_bindings:
      fasteners: PENDING_SIBLING_HASH {C_WP4_SCHED}
      tolerances: PENDING_SIBLING_HASH {C_WP3_SCHEME}
      drawings: [{WP9}/D05_STAGE_A.svg, {WP9}/D06_STAGE_B.svg]
    retained_holds: [DOWEL_FIT_INSERTION_REMOVAL_HOLD, REPRESENTATIVE_FIT_INSPECTION_HOLD]

  - interface_id: IF-03_LOAD_BRIDGE
    name: spacecraft bus to M3R Stage B via load bridge (candidate)
    status: CANDIDATE_GEOMETRY__HARD_HOLD_RETAINED
    mating_parts: [12U bus +X face, LOAD_BRIDGE_CANDIDATE_V1, M3R_STAGE_B_LOAD_ADAPTER_REVB2_WORKING]
    geometry:
      plate_mm: [160.0, 160.0, 10.75]   # R4 rounded square, x in [185.25, 196.0]
      hole_pattern: 4x dia 6.6 mm through @ (+/-70, +/-70) local; centre dia 40.0 mm through
      nominal_hole_edge_ligament_mm: 6.7   # nominal geometry only, NOT a worst-case margin
      stage_b_m6_ligament_mm: 11.7         # B-018 nominal, NOT a worst-case margin
      candidate_mass_g: 702.195458          # MATERIAL_DERIVED 6061-T6 2700 kg/m3, not hardware mass
      bus_side_anchor_pattern: null         # HOLD - no authorized bus-side mating pattern
    sources:
      - {M6}/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml
      - {M6}/wp1_load_bridge/D04_LOAD_BRIDGE_INTERFACE_DRAFT.svg
    design_bindings:
      geometry_authority: PENDING_SIBLING_HASH {C_WP1_ASSY_STEP}
      fasteners: PENDING_SIBLING_HASH {C_WP4_SCHED}
      material: PENDING_SIBLING_HASH {C_WP6_MAT}
      drawing: {WP9}/D08_ASSEMBLY_STACKUP.svg
    retained_holds: [SPACECRAFT_SIDE_ANCHOR_PATTERN_HOLD, STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD,
                     LOAD_BRIDGE_PHYSICAL_FITUP_HOLD, LEGACY_FLANGE_OWNERSHIP_HOLD]

  - interface_id: IF-04_WING_ROOT_HINGE
    name: solar wing root hinge (L/R) to bus
    status: DESIGN_DRAFT__MECHANISM_HOLD
    geometry:
      panel_box_m: [0.227, 0.200, 0.006]
      panel_mass_each_kg: 0.3483933
      hinge_tip_sensitivity_mm_per_mrad: 0.2
      stowed_geometry: null               # pending WP1
    sources:
      - {M6}/wp3_tolerance/HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1.yaml
      - {M7}/00_authority/M7_EXECUTION_PLAN_V1.md
    design_bindings:
      mechanism_pack: PENDING_SIBLING_HASH {C_WP5_HINGE}
      structure: PENDING_SIBLING_HASH {C_WP1_STRUCT}
      thermal_envelope: PENDING_SIBLING_HASH {C_WP8_ENV}
    retained_holds: [MECHANISM_QUALIFICATION_TEST_HOLD, STOWED_GEOMETRY_PENDING_WP1]

  - interface_id: IF-05_HDRM
    name: arm hold-down and release mechanism
    status: HOLD_PRODUCT_SELECTION
    geometry: null                          # nonphysical skeleton reference only (M4/M5/M6)
    sources:
      - {M5}/03_load_authority/M5_LOAD_CASE_MIGRATION_REGISTER_V1.csv   # LC-007 hdrm_release
    design_bindings:
      engineering_pack: PENDING_SIBLING_HASH {C_WP5_HDRM}
    retained_holds: [HDRM_PRODUCT_SELECTION, RELEASE_RELIABILITY_SHOCK_TEST_HOLD,
                     GLOBAL_TRANSFORM_CLOCKING_PRODUCT_UNKNOWN]

  - interface_id: IF-06_GRIPPER
    name: gripper R1 at B601 wrist end
    status: DESIGN_DRAFT__HARDWARE_HOLD
    geometry:
      stroke_mm: [0.0, 71.5]
      neutral_sweep: 144 samples @ 0.5 mm, zero overlap, hash-bound R1 assets (PASS)
      separated_finger_breps: null          # HARD_HOLD (diagnostic .ply only)
    sources:
      - {V5R}/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json
      - {M5}/01_geometry_authority/assets/b601_link_local_surfaces/B601_GRIPPER_R1_LEFT_FINGER_GRIPPER_LINK_LOCAL_M.ply
      - {M5}/01_geometry_authority/assets/b601_link_local_surfaces/B601_GRIPPER_R1_RIGHT_FINGER_GRIPPER_LINK_LOCAL_M.ply
    design_bindings:
      engineering_pack: PENDING_SIBLING_HASH {C_WP5_GRIPPER}
      clearances: PENDING_SIBLING_HASH {C_WP3_CHAINS}
    retained_holds: [FINGER_SEPARATED_BREP_HARD_HOLD, CONTACT_DATUM_METROLOGY_HOLD,
                     MINIMUM_WALL_AUTHORIZED_VALUE_EXTERNAL, MANUFACTURING_CLEARANCE_LIMIT_EXTERNAL]

  - interface_id: IF-07_CAMERA
    name: service camera mount
    status: HOLD_SELECTION
    geometry: null                          # rejected candidate pose penetrated M3R; no replacement authorized
    sources:
      - {V5R}/02_interfaces/MECH_RL_INTERFACE_V1.yaml
    design_bindings:
      keep_out: PENDING_SIBLING_HASH {C_WP1_KEEPOUT}
      support_candidates: PENDING_SIBLING_HASH {C_WP1_SUPPORT}
    retained_holds: [CAMERA_SELECTION, MOUNT_ALIGNMENT, HAND_EYE_CALIBRATION]

  - interface_id: IF-08_HARNESS
    name: moving harness routing (bus, M3R passage, arm, wings, gripper)
    status: DESIGN_DRAFT__SWEEP_HOLD
    geometry:
      central_passage_dia_mm: 40.0          # only permitted M3R penetration
      schematic: {WP9}/D07_HARNESS_ROUTING_SCHEMATIC.svg   # schematic, no geometric authority
      static_keep_out: OD9 exists (CDR CI-011)
    design_bindings:
      routing_authority: PENDING_SIBLING_HASH {C_WP1_HARNESS}
      keep_out_authority: PENDING_SIBLING_HASH {C_WP1_KEEPOUT}
    retained_holds: [MOVING_SWEEP_VERIFICATION_HOLD, BEND_RADIUS_STRAIN_RELIEF_TBD,
                     WEAR_LIFE_TEST_HOLD]

  - interface_id: IF-09_KEEP_OUT
    name: system keep-out register
    status: DESIGN_DRAFT__PENDING_WP1
    design_bindings:
      register: PENDING_SIBLING_HASH {C_WP1_KEEPOUT}
    retained_holds: [PER_CONFIG_INTERFERENCE_RECORDS_PENDING_WP1_HASH]

source_register: see receipt.json (SHA-256 pinned)
"""


def meta_yaml(schema, artifact, artifact_class, release_effect, notes, sources):
    lines = [
        f"schema: {schema}",
        f"artifact: {artifact}",
        f"artifact_class: {artifact_class}",
        f"generated_local: '{GEN_LOCAL}'",
        "generated_by_wp: WP9_RELEASE_PACKAGE",
        f"release_effect: {release_effect}",
        "notes:",
    ]
    for n in notes:
        lines.append(f"  - {n}")
    lines.append("source_register:")
    for rel in sources:
        lines.append(f"  - path: {rel}")
        lines.append(f"    sha256: {SOURCE_HASHES[rel]}")
    return "\n".join(lines) + "\n"


def build_receipt(outputs, urdf_check):
    return {
        "schema": "M7_WP9_RECEIPT_V1",
        "work_package": "WP9_RELEASE_PACKAGE",
        "artifact_class": "DESIGN_RELEASE_PACKAGE_DOCUMENT_LEVEL",
        "generated_local": GEN_LOCAL,
        "output_dir": WP9 + "/",
        "builder": WP9 + "/build_wp9_release_package.py",
        "compliance": {
            "baseline_files_modified": False,
            "write_scope": "only " + WP9 + "/",
            "freecad_launched": False,
            "abaqus_launched": False,
            "formal_fea_run_count": 0,
            "zero_fill_of_unknowns": False,
            "candidate_promoted_to_released": False,
            "cad_mass_override_of_urdf_l0": False,
            "procurement_or_manufacturing_release_claim": False,
            "sibling_reference_policy": "M7_EXECUTION_PLAN_V1 contract paths only; all sibling hashes PENDING_SIBLING_HASH; no sibling runtime artifact read",
            "memory_gate_6gib": "respected; pure text generation and sequential sha256 of small files",
        },
        "l0_urdf_sha256_check": urdf_check,
        "outputs": outputs,
        "source_register": [{"path": r, "sha256": SOURCE_HASHES[r]} for r in INPUTS],
        "pending_sibling_hash_contracts": [
            C_WP1_STRUCT, C_WP1_ASSY_FCSTD, C_WP1_ASSY_STEP, C_WP1_HARNESS, C_WP1_KEEPOUT,
            C_WP1_SUPPORT, C_WP2_MASS, C_WP2_POLICY, C_WP3_CHAINS, C_WP3_RESULTS, C_WP3_SCHEME,
            C_WP4_M3R, C_WP4_SCHED, C_WP4_TORQUE, C_WP4_CHECKS, C_WP5_HDRM, C_WP5_HINGE,
            C_WP5_GRIPPER, C_WP5_XREF, C_WP6_MAT, C_WP6_PROC, C_WP7_EVID, C_WP7_RESULTS,
            C_WP7_DECKS, C_WP8_SENS, C_WP8_ENV, C_WP10_IF,
        ],
        "integration_backfill_target": M7 + "/12_release/M7_CROSS_WP_REFERENCE_RECONCILIATION_V1.json",
        "holds_retained": [
            "BOM V3 HARD_HOLD rows retained: DP-007 (bus-side anchor pattern + structural load path continuity), DP-009 (gripper separated fingers), DP-010 (sensor package, no candidate asset), DP-011 (HDRM product/transform); DP-013 dowel candidate not promoted",
            "Gate B untouched: launch-qualification FEA HOLD (ODR-06 retained); MSR-STR-009 flight qualification EXTERNAL_HOLD; launcher/separation ICD absent",
            "M3R as-built measurement open (ODR-05 retained); MSR-STR-002 as-built reconciliation EXTERNAL_HOLD",
            "VERIFICATION_MATRIX_V1.csv: 21 EXTERNAL_HOLD + 15 TEST_REQUIRED_HOLD rows retained; 17 ANALYTIC_CLOSED rows are design-level only and contingent on integration hash backfill",
            "Native SolidWorks line permanently off critical path (ODR-03); MSR-INT-005/006, MSR-MEC-002 stay EXTERNAL_HOLD",
            "Camera selection (MSR-MEC-009), HDRM product selection (MSR-MEC-008), mechanism qualification tests, and all launch/qualification inputs remain external/test HOLDs",
            "No procurement or manufacturing release claim; BOM V3 is a design binding register, NOT_A_PROCUREMENT_BOM",
        ],
        "integration_notes": [
            "WP1: hash backfill for structure/assembly/harness/keep-out/support contract paths cited in DRAWING_SET_INDEX_V1.csv, BOM_V3_DESIGN.csv, ICD_V3_DRAFT.yaml, VERIFICATION_MATRIX_V1.csv",
            "WP2: stage-level M3R mass split (DP-005/DP-006) and nine-config aggregates cited as PENDING_SIBLING_HASH in BOM_V3_DESIGN.csv mass_design_binding",
            "WP3: DRAWING_TOLERANCE_SCHEME_V1.csv supplies the acceptance criteria referenced by INSPECTION_PLAN_V1.csv KC-01..KC-10/KC-13",
            "WP4: TORQUE_PRELOAD_SCHEDULE_V1.csv supplies every torque cell of ASSEMBLY_PROCEDURE_V1.md (all currently PENDING_SIBLING_HASH by design)",
            "WP6: DESIGN_MATERIAL_SELECTION_V1.yaml supplies material_design_binding targets in BOM_V3_DESIGN.csv",
            "Gate A scorecard: drawings and BOM rows map to WP9 per M7_EXECUTION_PLAN_V1.md",
        ],
    }


def main():
    global SOURCE_HASHES
    SOURCE_HASHES = {}
    missing = []
    for rel in INPUTS:
        ap = os.path.join(PROJ, rel.replace("/", os.sep))
        if not os.path.isfile(ap):
            missing.append(rel)
        else:
            SOURCE_HASHES[rel] = sha256_file(ap)
    if missing:
        raise SystemExit("FAIL-CLOSED: missing baseline inputs: " + "; ".join(missing))

    urdf_rel = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
    urdf_actual = SOURCE_HASHES[urdf_rel].upper()
    urdf_check = {
        "path": urdf_rel,
        "expected_sha256": L0_URDF_EXPECTED_SHA256,
        "actual_sha256": urdf_actual,
        "match": urdf_actual == L0_URDF_EXPECTED_SHA256,
        "note": "MSR-STR-001 authority re-verified read-only; file never modified",
    }

    artifacts = {}
    artifacts["D05_STAGE_A.svg"] = build_d05()
    artifacts["D06_STAGE_B.svg"] = build_d06()
    artifacts["D07_HARNESS_ROUTING_SCHEMATIC.svg"] = build_d07()
    artifacts["D08_ASSEMBLY_STACKUP.svg"] = build_d08()
    paths = [write_text(k, v) for k, v in artifacts.items()]

    paths.append(write_csv("DRAWING_SET_INDEX_V1.csv", DRAWING_INDEX_HEADER, DRAWING_INDEX_ROWS))
    paths.append(write_csv("BOM_V3_DESIGN.csv", BOM_V3_HEADER, BOM_V3_ROWS))
    paths.append(write_text("ASSEMBLY_PROCEDURE_V1.md", build_assembly_procedure()))
    paths.append(write_csv("INSPECTION_PLAN_V1.csv", INSPECTION_HEADER, INSPECTION_ROWS))
    paths.append(write_csv("VERIFICATION_MATRIX_V1.csv", VM_HEADER, vm_rows()))
    paths.append(write_text("ICD_V3_DRAFT.yaml", build_icd()))

    core_sources = [M7 + "/README.md", M7 + "/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml",
                    M7 + "/00_authority/M7_EXECUTION_PLAN_V1.md"]
    paths.append(write_text("DRAWING_SET_INDEX_V1.meta.yaml", meta_yaml(
        "M7_WP9_DRAWING_SET_INDEX_META_V1", "DRAWING_SET_INDEX_V1.csv (+ D05/D06/D07/D08 svg)",
        "DESIGN_RELEASE_CANDIDATE", "NONE_DESIGN_LEVEL_ONLY",
        ["D01/D02/D03 carried from M4 unchanged; D04 exists at M6 path and stays CANDIDATE until WP1 authority.",
         "New SVGs follow the D01/D04 style; every sheet carries DESIGN RELEASE CANDIDATE banner and a release boundary box.",
         "No manufacturing use; material/tolerance specs bind to WP6/WP3 contract paths with PENDING_SIBLING_HASH."],
        core_sources + [M4 + "/09_drawings/D01_DIGITAL_PROTOTYPE_INTERFACE_LAYOUT_DRAFT.svg",
                        M4 + "/09_drawings/DIGITAL_PROTOTYPE_DRAWING_INDEX_V1.csv",
                        M6 + "/wp6_drawings_bom/DIGITAL_PROTOTYPE_DRAWING_INDEX_V2.csv",
                        M6 + "/wp1_load_bridge/D04_LOAD_BRIDGE_INTERFACE_DRAFT.svg",
                        M3DD + "/06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml",
                        M3DD + "/06_parameterized_parts/m3r/M3R_STAGE_B_PARAMETER_TABLE.yaml",
                        M6 + "/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml",
                        M6 + "/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml"])))
    paths.append(write_text("BOM_V3_DESIGN.meta.yaml", meta_yaml(
        "M7_WP9_BOM_V3_META_V1", "BOM_V3_DESIGN.csv", "DESIGN_BINDING_REGISTER",
        "NONE_NOT_A_PROCUREMENT_BOM",
        ["V2's 16 columns carried verbatim; 7 V3 binding columns appended (material/mass/fastener bindings + disposition + note).",
         "Mass column binds only contract values (ODR-05 0.7619 kg; L0 4.695555949342986 kg; bus diagnostic 22.927194215348 + 0.376019184652 kg; panel 0.3483933 kg each; bridge 702.195458 g MATERIAL_DERIVED) and WP2 contract path.",
         "Material column binds WP6 contract path PENDING_SIBLING_HASH; fastener column binds WP4 contract paths PENDING_SIBLING_HASH.",
         "HARD_HOLD rows (DP-007/009/010/011) keep honest status; candidate rows never promoted; no zero-fill of unknown masses."],
        core_sources + [M4 + "/10_BOM/DIGITAL_PROTOTYPE_BOM_V1.csv", M4 + "/10_BOM/BOM_SCOPE_AND_NONCLAIMS.md",
                        M6 + "/wp6_drawings_bom/DIGITAL_PROTOTYPE_BOM_V2_CANDIDATE.csv",
                        M6 + "/wp6_drawings_bom/BOM_SCOPE_AND_NONCLAIMS_V2.md",
                        M3DD + "/10_bom/M3R_BOM_V2.csv",
                        M6 + "/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml",
                        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"])))
    paths.append(write_text("INSPECTION_PLAN_V1.meta.yaml", meta_yaml(
        "M7_WP9_INSPECTION_PLAN_META_V1", "INSPECTION_PLAN_V1.csv", "DESIGN_KC_REGISTER",
        "NONE_DESIGN_LEVEL_ONLY",
        ["14 key characteristics; acceptance criteria are CANDIDATE class pending WP3/WP4/WP5/WP1 contracts.",
         "Hardware measurement and fit inspection remain HOLD; KC-12/KC-14 are HOLD rows with no authorized criterion.",
         "M6 executed WC chains cited as design evidence (0.101015357 mm radial, 0.206/0.207 mm fits, 1.8909e-3 rad clocking, 0.2 mm/mrad hinge)."],
        core_sources + [M6 + "/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml",
                        M6 + "/wp3_tolerance/HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1.yaml",
                        M6 + "/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml",
                        M6 + "/wp6_drawings_bom/INTERFACE_STATION_SCHEDULE_V2.csv",
                        M3DD + "/06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml",
                        M3DD + "/06_parameterized_parts/m3r/M3R_STAGE_B_PARAMETER_TABLE.yaml",
                        V5R + "/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json",
                        CDR + "/01_wp0_requirements/MECHANICAL_CRITICAL_ITEMS_REGISTER_V1.csv"])))
    paths.append(write_text("VERIFICATION_MATRIX_V1.meta.yaml", meta_yaml(
        "M7_WP9_VERIFICATION_MATRIX_META_V1", "VERIFICATION_MATRIX_V1.csv", "DESIGN_VERIFICATION_MAP",
        "NONE_MAPPING_DOCUMENT",
        ["62/62 CDR requirements mapped; status enum: PASS_EVIDENCE(9) / ANALYTIC_CLOSED(17) / TEST_REQUIRED_HOLD(15) / EXTERNAL_HOLD(21).",
         "ANALYTIC_CLOSED = design-level closure contingent on integration hash backfill of cited M7 contract paths; rows name reversion rules where evidence is not yet pinned.",
         "Existing-evidence paths are M4/M5/V5R/CDR/SIM13 baselines; M7 evidence cites contract paths only (PENDING_SIBLING_HASH).",
         "flight_credit=NO on every row; Gate B remains HOLD."],
        core_sources + [CDR + "/01_wp0_requirements/MECHANICAL_SYSTEM_REQUIREMENTS_SPEC_V1.yaml",
                        CDR + "/01_wp0_requirements/MECHANICAL_VERIFICATION_CONTROL_DOCUMENT_V1.csv",
                        CDR + "/01_wp0_requirements/HOLD_TO_REQUIREMENT_TRACEABILITY_V1.csv"])))

    outputs = []
    for p in paths:
        rel = WP9 + "/" + os.path.basename(p)
        outputs.append({"path": rel, "sha256": sha256_file(p), "bytes": os.path.getsize(p)})

    receipt = build_receipt(outputs, urdf_check)
    write_text("receipt.json", json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print("WP9 build complete:", len(outputs), "artifacts + receipt.json")
    print("URDF L0 hash match:", urdf_check["match"])


if __name__ == "__main__":
    main()
