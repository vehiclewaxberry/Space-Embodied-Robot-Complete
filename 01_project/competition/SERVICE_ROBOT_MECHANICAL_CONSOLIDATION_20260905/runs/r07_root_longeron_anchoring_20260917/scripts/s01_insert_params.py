# -*- coding: utf-8 -*-
"""R07-E1: 向 design_parameters.json 插入 root_anchoring_r07_e1 参数块（保留 CRLF 行尾）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
P = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'

BLOCK = """  "root_anchoring_r07_e1": {
    "status": "CANDIDATE_NOMINAL_GEOMETRY; material/grade/preload/locking/effective_thread_engagement/bearing_allowable/load_rating UNKNOWN",
    "provenance": {
      "ticket_id": "R07 connection_edges[0] 桥/上下横梁→主纵梁 (POSITIVE_CONNECTION_UNDEFINED)",
      "issue_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json (R07 local_review connection_edges 第1边; snapshot sha256 fe90ef815f709cd8...)",
      "plan_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/WP03_NEXT_STAGE_MECHANICAL_PLAN_20260906.md Section 3.5 (下一张主票 R07 根部锚固) 与 Section 4.1 第1行+逐边登记要求",
      "run": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917/",
      "authorized_scope": "仅 R07-E1 一边 digital_geometry / nominal_digital_assembly 候选实体与登记；载荷/强度/有效啮合/预紧/防松 UNKNOWN；父票 R07 不关闭；E2-E4 与 A/B 支承不动"
    },
    "concept": "每端跨接锚固：M3 贯穿螺栓（头+垫圈在纵梁外腹面 y=±113.15）经纵梁双壁+管内防压套，进入横梁/桥端面盲孔（对偶孔同轴 Y）；双栓组正向防转；x=160 站受端塞(x>=157)与 X164 Ø4.5 端塞对偶孔(E2)限制仅容 1 栓，防转由同站桥栓与既有 M6/贯通杆夹接链二级承担（滑移/残余转角 UNKNOWN）",
    "hole_diameter_mm": 3.4,
    "hole_axis_S": [0, 1, 0],
    "beam_end_tapped_hole": {
      "diameter_mm": 3.4,
      "nominal_depth_mm": 10,
      "modeled_depth_mm": 12,
      "note": "THREADLESS_ENVELOPE：按 Ø3.4 光孔+Ø3 杆零干涉包络建模；实际底孔/攻丝/有效啮合为制造与选型状态 UNKNOWN"
    },
    "fastener_candidate": {
      "thread": "M3_UNSELECTED",
      "shank_diameter_mm": 3,
      "underhead_length_mm": 22,
      "nominal_grip_mm": 12,
      "nominal_thread_engagement_mm": 8,
      "head_diameter_mm": 5.5,
      "head_height_mm": 3,
      "washer": {
        "outer_diameter_mm": 6,
        "inner_diameter_mm": 3.4,
        "thickness_mm": 0.5
      },
      "anti_crush_sleeve": {
        "outer_diameter_mm": 5,
        "inner_diameter_mm": 3.4,
        "length_mm": 8,
        "reduced_outer_diameter_mm": 4,
        "reduced_note": "x=154.85 站邻近端塞(x>=157)，套外径降至 4.0（壁 0.3 mm 候选薄壁，制造审查项；防压功能 UNKNOWN）"
      },
      "direction": "头+垫圈在纵梁外腹面，工具沿 Y 自外侧进入；杆经外壁-防压套-内壁进入横梁/桥端面孔；盲孔无需内侧通道",
      "material_grade_thread_engagement_preload_locking": "UNKNOWN"
    },
    "groups": [
      {"id": "G01", "member": "upper_beam", "beam_x_mm": 20, "end_y_S_mm": 101.15, "side_sy": 1, "longeron_sz": 1, "mate_instance": "RB_longeron_1_1", "bolts": [{"x_S_mm": 15.5, "z_S_mm": 104.15}, {"x_S_mm": 24.5, "z_S_mm": 104.15}], "anti_rotation": "TWO_BOLT_POSITIVE"},
      {"id": "G02", "member": "upper_beam", "beam_x_mm": 20, "end_y_S_mm": -101.15, "side_sy": -1, "longeron_sz": 1, "mate_instance": "RB_longeron_-1_1", "bolts": [{"x_S_mm": 15.5, "z_S_mm": 104.15}, {"x_S_mm": 24.5, "z_S_mm": 104.15}], "anti_rotation": "TWO_BOLT_POSITIVE"},
      {"id": "G03", "member": "upper_beam", "beam_x_mm": 160, "end_y_S_mm": 101.15, "side_sy": 1, "longeron_sz": 1, "mate_instance": "RB_longeron_1_1", "bolts": [{"x_S_mm": 154.85, "z_S_mm": 104.15, "sleeve_od_mm": 4}], "anti_rotation": "SINGLE_BOLT_PLUS_REGISTERED_SECONDARY; secondary=同站桥栓 G09@(154.85,110.15)+既有 M6 夹接@(160,±70)；滑移与残余转角 UNKNOWN"},
      {"id": "G04", "member": "upper_beam", "beam_x_mm": 160, "end_y_S_mm": -101.15, "side_sy": -1, "longeron_sz": 1, "mate_instance": "RB_longeron_-1_1", "bolts": [{"x_S_mm": 154.85, "z_S_mm": 104.15, "sleeve_od_mm": 4}], "anti_rotation": "SINGLE_BOLT_PLUS_REGISTERED_SECONDARY; secondary=同站桥栓 G10@(154.85,110.15)+既有 M6 夹接@(160,±70)；滑移与残余转角 UNKNOWN"},
      {"id": "G05", "member": "lower_beam", "beam_x_mm": 20, "end_y_S_mm": 101.15, "side_sy": 1, "longeron_sz": -1, "mate_instance": "RB_longeron_1_-1", "bolts": [{"x_S_mm": 15.5, "z_S_mm": -104.15}, {"x_S_mm": 24.5, "z_S_mm": -104.15}], "anti_rotation": "TWO_BOLT_POSITIVE"},
      {"id": "G06", "member": "lower_beam", "beam_x_mm": 20, "end_y_S_mm": -101.15, "side_sy": -1, "longeron_sz": -1, "mate_instance": "RB_longeron_-1_-1", "bolts": [{"x_S_mm": 15.5, "z_S_mm": -104.15}, {"x_S_mm": 24.5, "z_S_mm": -104.15}], "anti_rotation": "TWO_BOLT_POSITIVE"},
      {"id": "G07", "member": "lower_beam", "beam_x_mm": 160, "end_y_S_mm": 101.15, "side_sy": 1, "longeron_sz": -1, "mate_instance": "RB_longeron_1_-1", "bolts": [{"x_S_mm": 154.85, "z_S_mm": -104.15, "sleeve_od_mm": 4}], "anti_rotation": "SINGLE_BOLT_PLUS_REGISTERED_SECONDARY; secondary=既有贯通杆夹接链@(160,±94.15,柱+垫块 Z 向夹紧)；滑移与残余转角 UNKNOWN"},
      {"id": "G08", "member": "lower_beam", "beam_x_mm": 160, "end_y_S_mm": -101.15, "side_sy": -1, "longeron_sz": -1, "mate_instance": "RB_longeron_-1_-1", "bolts": [{"x_S_mm": 154.85, "z_S_mm": -104.15, "sleeve_od_mm": 4}], "anti_rotation": "SINGLE_BOLT_PLUS_REGISTERED_SECONDARY; secondary=既有贯通杆夹接链@(160,±94.15)；滑移与残余转角 UNKNOWN"},
      {"id": "G09", "member": "bridge", "beam_x_mm": null, "end_y_S_mm": 101.15, "side_sy": 1, "longeron_sz": 1, "mate_instance": "RB_longeron_1_1", "bolts": [{"x_S_mm": 146, "z_S_mm": 110.15}, {"x_S_mm": 154.85, "z_S_mm": 110.15, "sleeve_od_mm": 4}], "anti_rotation": "TWO_BOLT_POSITIVE"},
      {"id": "G10", "member": "bridge", "beam_x_mm": null, "end_y_S_mm": -101.15, "side_sy": -1, "longeron_sz": 1, "mate_instance": "RB_longeron_-1_1", "bolts": [{"x_S_mm": 146, "z_S_mm": 110.15}, {"x_S_mm": 154.85, "z_S_mm": 110.15, "sleeve_od_mm": 4}], "anti_rotation": "TWO_BOLT_POSITIVE"}
    ],
    "registered_constraints": {
      "x160_station_single_bolt_reason": "横梁端面 x∈[153,167] 内 Ø3.4 孔须避开端塞(x>=157)与 X164 Ø4.5 端塞对偶孔(E2 不动)：可用带仅 [153,157]，容 1 孔",
      "x150_vertical_hole_avoidance": "桥栓 x=146/154.85 避开纵梁 X150 Ø3.4 竖孔(孔缘 148.3..151.7)",
      "tie_rod_avoidance": "x=20 站栓位 15.5/24.5 避开 M4×228 贯通杆及其 Ø4.5 对偶孔(x 17.75..22.25)",
      "cover_and_mount_clearance": "栓头/垫圈 z=±104.15/110.15 位于检修盖(z∈[-90,90])与盖座(z=±75 带)之外，装拆免拆盖",
      "threadless_envelope": "紧固件为无螺纹名义包络；材料/等级/预紧/防松/有效啮合 UNKNOWN，零填充禁止"
    }
  },
"""

ANCHOR = '  "physical_inputs_pending": ['

def main():
    raw = P.read_bytes().decode('utf-8')
    if '"root_anchoring_r07_e1"' in raw:
        print('ALREADY_PRESENT'); return
    idx = raw.index(ANCHOR)
    eol = '\r\n' if '\r\n' in raw else '\n'
    block = BLOCK.replace('\n', eol)
    new = raw[:idx] + block + raw[idx:]
    json.loads(new)
    P.write_bytes(new.encode('utf-8'))
    print('INSERTED eol=%r bytes=%d' % (eol, len(new.encode('utf-8'))))
    data = json.loads(P.read_bytes().decode('utf-8'))
    e1 = data['root_anchoring_r07_e1']
    print('groups:', len(e1['groups']), 'bolts:', sum(len(g['bolts']) for g in e1['groups']))

if __name__ == '__main__':
    main()
