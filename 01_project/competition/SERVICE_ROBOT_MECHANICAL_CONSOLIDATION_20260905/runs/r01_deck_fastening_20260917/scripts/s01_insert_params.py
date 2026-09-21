# -*- coding: utf-8 -*-
"""R01: 向 design_parameters.json 插入 deck_fastening_r01 参数块（保留 CRLF 行尾与 legacy 字段）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
P = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'

BLOCK = """  "deck_fastening_r01": {
    "status": "CANDIDATE_NOMINAL_GEOMETRY; material/grade/preload/locking/effective_engagement UNKNOWN",
    "provenance": {
      "ticket_id": "R01_DECK_ANGLE_FASTENER_MINIMUM_PROPOSAL_R1",
      "issue_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json (R01 first_candidate_ticket; snapshot sha256 fe90ef815f709cd8...)",
      "plan_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/WP03_NEXT_STAGE_MECHANICAL_PLAN_20260906.md Section 3.2",
      "run": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917/",
      "authorized_scope": "仅 digital_geometry / nominal_digital_assembly 子项候选实体；材料/载荷/有效啮合/预紧保持 UNKNOWN；父票不关闭"
    },
    "deck_hole_pattern": {
      "X_S_mm": [
        -150,
        -50,
        50,
        140
      ],
      "Y_S_mm": [
        -92.65,
        92.65
      ],
      "diameter_mm": 3.4,
      "axis_S": [
        0,
        0,
        1
      ],
      "hole_count_each_deck": 8,
      "same_axes_in_angle_horizontal_leg": true,
      "nominal_min_hole_material_to_angle_Y_edges_mm": 3.8,
      "x140_hole_material_to_x160_notch_mm": 9.8
    },
    "angle_to_shear_web_hole_pattern": {
      "X_S_mm_by_segment": [
        [
          -130,
          -70
        ],
        [
          60,
          130
        ]
      ],
      "Z_S_mm_by_deck": {
        "lower": -94.15,
        "upper": -18.5
      },
      "diameter_mm": 3.4,
      "axis_S": [
        0,
        1,
        0
      ],
      "quantity_pairs": 16
    },
    "deck_angle_fastener_candidate": {
      "thread": "M3_UNSELECTED",
      "underhead_length_mm": 12,
      "nominal_grip_mm": 6,
      "head_diameter_mm": 5.5,
      "washer_outer_diameter_max_mm": 6,
      "direction": "头位于甲板+Z，螺母在角材水平腿下；设备装入前装配",
      "material_grade_thread_engagement_preload_locking": "UNKNOWN"
    },
    "angle_web_fastener_candidate": {
      "thread": "M3_UNSELECTED",
      "underhead_length_mm": 10,
      "nominal_grip_mm": 5,
      "head_diameter_mm": 5.5,
      "washer_outer_diameter_max_mm": 6,
      "direction": "从剪力板外侧向内，侧盖安装前",
      "material_grade_thread_engagement_preload_locking": "UNKNOWN"
    },
    "legacy_deck_hole_pattern_superseded": {
      "X_S_mm": [
        -150,
        -50,
        50,
        150
      ],
      "Y_S_mm": [
        -89,
        89
      ],
      "diameter_mm": 3.4,
      "status": "SUPERSEDED_BY_deck_hole_pattern",
      "defect": "X=150,Y=±89 孔与 x=160 处 17×17 柱避口解析连通 0.2 mm，两甲板共四处破边（issues.json R01）",
      "superseded_in_run": "r01_deck_fastening_20260917"
    }
  },
"""

ANCHOR = '  "candidate_aluminum_density_kg_mm3": 2.7e-06,'

def main():
    raw = P.read_bytes().decode('utf-8')
    if '"deck_fastening_r01"' in raw:
        print('ALREADY_PRESENT'); return
    idx = raw.index(ANCHOR) + len(ANCHOR)
    # 保留锚点行原有的行尾（CRLF 或 LF）
    eol = '\r\n' if raw[idx:idx+2] == '\r\n' else '\n'
    block = BLOCK.replace('\n', eol)
    new = raw[:idx] + eol + block.rstrip('\r\n') + raw[idx:]
    # 校验：去行尾后是合法 JSON
    json.loads(new)
    P.write_bytes(new.encode('utf-8'))
    print('INSERTED eol=%r bytes=%d' % (eol, len(new.encode('utf-8'))))
    data = json.loads(P.read_bytes().decode('utf-8'))
    print('keys ok:', 'deck_fastening_r01' in data, data['deck_fastening_r01']['deck_hole_pattern']['X_S_mm'])

if __name__ == '__main__':
    main()
