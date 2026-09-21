# -*- coding: utf-8 -*-
"""R07-E3: 向 design_parameters.json 插入 retention_joints_r07_e3 参数块（保留 CRLF 行尾）。
两边同一保持器模块：
  边1（第4边）保持横梁→上纵梁：E1 式端面 Y 栓直连（M3 候选），z=103.65 居中于 5 mm 贴合带；
    不带防压套——贴合带顶 106.15 < E1 套所需孔位 z>=105.15+孔缘（两约束不可兼得），压溃控制 NOT_RUN 登记；
    横梁顶面 z>=106.15 被耳座占据，加高端面/顶盖板方案已否决（与耳座冲突）。
  边2（第5边）足叉→屋顶耳座：M4 候选竖栓链 自下（舱内）经横梁/耳座既有孔位带（新钻 x±5.5 对偶孔，
    既有中心孔留作备用登记）进入足叉脚座盲孔（打通至槽底，名义啮合 5）；
    头+垫圈在横梁底面下（舱内），槽内不留凸出（足叉轮毂 r10 干涉域 z>=125.15 已实读）；
    横向 Ø8.4 枢轴孔/销=运动铰（折叠释放用），脚座栓链=释放前保持，二者关系登记。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
P = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'

BLOCK = """  "retention_joints_r07_e3": {
    "status": "CANDIDATE_NOMINAL_GEOMETRY; material/grade/preload/locking/effective_thread_engagement/bearing_allowable/load_rating UNKNOWN",
    "provenance": {
      "ticket_id": "R07 connection_edges[3] 保持横梁→纵梁 与 connection_edges[4] 保持足叉→屋顶耳座 (POSITIVE_CONNECTION_UNDEFINED)",
      "issue_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json (R07 local_review connection_edges 第4/5边; snapshot sha256 fe90ef815f709cd8...)",
      "plan_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/WP03_NEXT_STAGE_MECHANICAL_PLAN_20260906.md Section 4.1 第3行：真实夹接件、足座匹配孔、紧固叠层、防转与装配路径",
      "run": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e3_retention_joints_20260918/",
      "authorized_scope": "仅 R07-E3 两边（同一保持器模块）digital_geometry 候选实体与登记；保持器机构功能（导杆/销俘获/止挡，§4.2）不属本工作包；父票 R07 不关闭；E4 与 A/B 支承不动"
    },
    "edge1_clamp": {
      "concept": "E1 式端面直连：每根保持横梁（k=0,1, x=-115/-40）两端各 2 枚 M3 候选 Y 栓（x=横梁心±4.5, z=103.65）自上纵梁外腹面穿双壁入横梁端面盲孔；TWO_BOLT_POSITIVE 防转",
      "hole_diameter_mm": 3.4,
      "hole_axis_S": [0, 1, 0],
      "bolt_z_S_mm": 103.65,
      "bolt_z_rationale": "贴合带 z∈[101.15,106.15]（横梁端面 10 厚 vs 纵梁面自 101.15 起）居中取 103.65；E1 防压套(OD4)要求栓位 z≥105.15 与孔缘闭合要求 z≤104.45 不可兼得 → 本边不带防压套，管壁压溃控制 NOT_RUN 登记；横梁顶面被耳座(z≥106.15)占据，端面加高/顶盖板方案否决",
      "beam_end_tapped_hole": {"diameter_mm": 3.4, "nominal_depth_mm": 10, "modeled_depth_mm": 12,
        "note": "THREADLESS_ENVELOPE：Ø3.4 光孔+Ø3 杆零干涉包络；底孔/攻丝/有效啮合 UNKNOWN"},
      "fastener_candidate": {"thread": "M3_UNSELECTED", "shank_diameter_mm": 3, "head_diameter_mm": 5.5, "head_height_mm": 3,
        "washer": {"outer_diameter_mm": 6, "inner_diameter_mm": 3.4, "thickness_mm": 0.5},
        "anti_crush_sleeve": "OMITTED_REGISTERED（见 bolt_z_rationale；压溃/预紧 UNKNOWN）",
        "material_grade_preload_locking_engagement": "UNKNOWN"},
      "groups": [
        {"id": "J01", "k": 0, "beam_x_mm": -115, "side_sy": 1, "mate_instance": "RB_longeron_1_1", "bolts": [{"x_S_mm": -119.5}, {"x_S_mm": -110.5}], "anti_rotation": "TWO_BOLT_POSITIVE"},
        {"id": "J02", "k": 0, "beam_x_mm": -115, "side_sy": -1, "mate_instance": "RB_longeron_-1_1", "bolts": [{"x_S_mm": -119.5}, {"x_S_mm": -110.5}], "anti_rotation": "TWO_BOLT_POSITIVE"},
        {"id": "J03", "k": 1, "beam_x_mm": -40, "side_sy": 1, "mate_instance": "RB_longeron_1_1", "bolts": [{"x_S_mm": -44.5}, {"x_S_mm": -35.5}], "anti_rotation": "TWO_BOLT_POSITIVE"},
        {"id": "J04", "k": 1, "beam_x_mm": -40, "side_sy": -1, "mate_instance": "RB_longeron_-1_1", "bolts": [{"x_S_mm": -44.5}, {"x_S_mm": -35.5}], "anti_rotation": "TWO_BOLT_POSITIVE"}
      ]
    },
    "edge2_foot": {
      "concept": "足叉脚座保持栓链：每足叉（k=0,1）2 枚 M4 候选竖栓（x=站心±5.5, y=-94.15）自舱内由下向上，经横梁新对偶孔→耳座新对偶孔→拧入足叉脚座盲孔（打通至槽底）；头+垫圈在横梁底面下；足叉槽内零凸出（轮毂 r10 干涉域 z≥125.15）",
      "hole_diameter_mm": 4.5,
      "hole_axis_S": [0, 0, 1],
      "bolt_y_S_mm": -94.15,
      "bolt_x_offset_mm": 5.5,
      "existing_center_hole": "横梁/耳座既有中心 Ø4.5 孔（x=站心）留作备用 UNUSED_EXISTING_SPARE；新孔 x±5.5 与其边缘距 1.0",
      "foot_tapped_hole": {"diameter_mm": 4.5, "nominal_engagement_mm": 5, "modeled_depth_mm": 7,
        "note": "脚座实体带 z∈[118.15,125.15]（7 厚，上至槽底）；打通至槽底，栓尖距槽底 2；THREADLESS_ENVELOPE；有效啮合 UNKNOWN；SHORT_ENGAGEMENT_5MM_REGISTERED"},
      "fastener_candidate": {"thread": "M4_UNSELECTED", "shank_diameter_mm": 4, "head_diameter_mm": 7, "head_height_mm": 4,
        "washer": {"outer_diameter_mm": 9, "inner_diameter_mm": 4.5, "thickness_mm": 1},
        "material_grade_preload_locking_engagement": "UNKNOWN"},
      "pivot_relationship": "横向 Ø8.4 枢轴孔+Ø8 销（z=135.15）= 运动铰（保持器折叠释放，§4.2 不属本包）；脚座栓链 = 释放前保持（发射/停放态锁定足叉于屋顶链）；栓链未拆则机构不可折——释放互锁顺序 INTERLOCK_REGISTERED",
      "groups": [
        {"id": "C01", "k": 0, "station_x_mm": -115, "bolts": [{"x_S_mm": -120.5}, {"x_S_mm": -109.5}], "anti_rotation": "TWO_BOLT_POSITIVE"},
        {"id": "C02", "k": 1, "station_x_mm": -40, "bolts": [{"x_S_mm": -45.5}, {"x_S_mm": -34.5}], "anti_rotation": "TWO_BOLT_POSITIVE"}
      ]
    },
    "registered_constraints": {
      "no_sleeve_rationale": "边1 不带防压套：贴合带顶 106.15 与套所需栓位 z≥105.15 冲突（E1 式套 OD4 需栓位 z≥105.15，孔缘闭合需 z≤104.45）",
      "lug_top_occupied": "横梁顶面 z≥106.15、y∈[87.15,101.15] 被耳座占据 → 端面加高/顶盖板/上夹角方案全部否决",
      "mast_hub_exclusion": "足叉槽内 z≥125.15 为轮毂 r10 干涉域（实读 mast bbox z 起 125.15）→ 边2 槽内不得有任何凸出；头/螺母只可置于横梁底面下",
      "e1_bolt_avoidance": "边1 栓位 x∈{-119.5,-110.5,-44.5,-35.5}, z=103.65 与 E1 梁栓(x∈{15.5,24.5,154.85}, z=105.3)/桥栓(x∈{146,154.85}, z=110.15) 无交叠",
      "threadless_envelope": "紧固件为无螺纹名义包络；材料/等级/预紧/防松/有效啮合 UNKNOWN，零填充禁止"
    }
  },
"""

ANCHOR = '  "physical_inputs_pending": ['

def main():
    raw = P.read_bytes().decode('utf-8')
    if '"retention_joints_r07_e3"' in raw:
        print('ALREADY_PRESENT'); return
    idx = raw.index(ANCHOR)
    eol = '\r\n' if '\r\n' in raw else '\n'
    block = BLOCK.replace('\n', eol)
    new = raw[:idx] + block + raw[idx:]
    json.loads(new)
    P.write_bytes(new.encode('utf-8'))
    print('INSERTED eol=%r bytes=%d' % (eol, len(new.encode('utf-8'))))
    data = json.loads(P.read_bytes().decode('utf-8'))
    e3 = data['retention_joints_r07_e3']
    print('edge1 groups:', len(e3['edge1_clamp']['groups']), 'edge2 groups:', len(e3['edge2_foot']['groups']))

if __name__ == '__main__':
    main()
